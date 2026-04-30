"""Routing-history wire schema and writer for ``jarvis_routing_history`` entries.

This module is the persistence boundary between the Jarvis supervisor's
in-memory dispatch decisions and the durable, queryable Graphiti knowledge
graph. It exposes a frozen Pydantic schema (:class:`JarvisRoutingHistoryEntry`
and its helper types) describing the wire shape of every routing-history
record, plus :class:`RoutingHistoryWriter` which redacts human-shaped fields
at the write boundary, optionally offloads oversized inline trace payloads
to the local trace store, and submits the entry as a fire-and-forget
Graphiti ``add_episode`` call.

Origin
------
Authored under **FEAT-JARVIS-004** (Phase 3 — Fleet Integration), Group A.2.
The schema was promoted to authoritative status for v1+ per DDR-018, and the
write path was constrained to fire-and-forget semantics per DDR-019 so a
degraded Graphiti instance never propagates back into the dispatch hot path.

Design references
-----------------
All paths below resolve to files in this repository and are verified to be
readable as part of the docstring contract.

* :doc:`docs/design/FEAT-JARVIS-004/design.md` — feature-level design doc
  describing the dispatch + routing-history pipeline this module implements.
* :doc:`docs/design/FEAT-JARVIS-004/models/DM-routing-history.md` —
  authoritative field definitions, regex patterns, and Literal members for
  the entry schema. See §6 for the schema-evolution rules.
* `DDR-018 — JarvisRoutingHistoryEntry schema authoritative
  <../../../docs/design/FEAT-JARVIS-004/decisions/DDR-018-routing-history-schema-authoritative.md>`_
  — additions are append-only; renames or type changes require a
  ``schema_version`` marker at the change point.
* `DDR-019 — Per-dispatch fire-and-forget Graphiti writes; WARN on failure
  <../../../docs/design/FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md>`_
  — failures log ``WARN routing_history_write_failed reason=<err>`` and
  never raise; the supervisor stays up when Graphiti is degraded.
* `DDR-023 — Trace-file collision policy: WARN + preserve original
  <../../../docs/design/FEAT-JARVIS-004/decisions/DDR-023-trace-file-collision-warn-and-preserve.md>`_
  — pre-existing trace files at the same path are preserved (no overwrite);
  the Graphiti write is also skipped for that record because the entity
  needs a :class:`TraceRef` the writer cannot construct without on-disk
  content.
* `ADR-ARCH-029 — Personal-use compliance posture
  <../../../docs/architecture/decisions/ADR-ARCH-029-personal-use-compliance-posture.md>`_
  — informs the redaction stance: redaction runs at the **write boundary**
  inside :meth:`RoutingHistoryWriter.write_specialist_dispatch`, *not*
  inside Pydantic validators on the frozen entry.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from jarvis.config.settings import JarvisConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redaction configuration (ADR-ARCH-029 / DDR-018)
# ---------------------------------------------------------------------------

REDACTION_PLACEHOLDER = "***REDACTED***"
"""Token substituted in for any matched secret pattern at the write boundary."""

# The four token classes from ADR-ARCH-029 + DDR-018:
#   - API keys: ``sk-...``-prefixed and similar high-entropy bearer prefixes.
#   - JWT tokens: standard three-segment ``eyJ...``-prefixed encoding.
#   - NATS credentials: ``NKEY``-prefixed lines from ``.creds`` files.
#   - Email addresses: RFC-loose ``local@domain.tld`` form.
_REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # API keys — match common bearer prefixes followed by >=16 token chars.
    re.compile(r"(?:sk|xai|pk|rk|gsk)-[A-Za-z0-9_\-]{16,}"),
    # JWT tokens — three base64url segments separated by ``.``.
    re.compile(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    # NATS NKEY — uppercase base32-style strings starting with NKEY/NSEED/etc.
    # NATS user nkeys are 56-char base32 strings; we use a 32+ length floor
    # to also cover seeds and operator keys without false-positives on enum
    # constants.
    re.compile(r"\b(?:NKEY|NSEED|SU|SO|SA|SUA)[A-Z2-7]{20,}\b"),
    # Email — RFC-loose; covers operator usernames and notification CCs.
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
)


def _redact_text(value: str) -> str:
    """Replace any matched secret pattern with :data:`REDACTION_PLACEHOLDER`.

    Returns the input unchanged when no pattern matches; allocates a new
    string only on a positive match. Operates on substrings so a single
    field that contains a secret embedded in surrounding prose still
    redacts only the secret portion (and any other matches in the same
    string).
    """
    for pattern in _REDACTION_PATTERNS:
        value = pattern.sub(REDACTION_PLACEHOLDER, value)
    return value


def _redact_recursive(payload: Any) -> Any:
    """Walk a JSON-shaped payload redacting every string in place-of-copy.

    Lists are rebuilt; dicts are rebuilt; scalars are passed through
    unmodified except for ``str`` which is run through :func:`_redact_text`.
    The caller passes ``entry.model_dump(mode='json')`` output, so the
    frozen ``JarvisRoutingHistoryEntry`` itself is never mutated — the
    seam-test invariant.
    """
    if isinstance(payload, str):
        return _redact_text(payload)
    if isinstance(payload, dict):
        return {key: _redact_recursive(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_redact_recursive(item) for item in payload]
    return payload

# ---------------------------------------------------------------------------
# §1 — DispatchOutcome closed Literal
# ---------------------------------------------------------------------------

DispatchOutcome = Literal[
    "success",
    "redirected",
    "timeout",
    "specialist_error",
    "exhausted",
    "transport_unavailable",
    "unresolved",
]
"""Closed enumeration of dispatch outcomes — see DM-routing-history.md §1."""


# ---------------------------------------------------------------------------
# §4 — Helper types (declared first so JarvisRoutingHistoryEntry can reference)
# ---------------------------------------------------------------------------


class TraceRef(BaseModel):
    """Pointer to an oversized trace component on the local trace store.

    ADR-FLEET-001 §"Large traces" + DDR-018: when a trace component exceeds
    16KB JSON-encoded, the writer offloads the payload and stores only this
    reference (path + content hash + size).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    path: str = Field(
        description="Absolute path to the trace file.",
    )
    content_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the file contents at write time.",
    )
    size_bytes: int = Field(ge=0)


class ToolCallRecord(BaseModel):
    """One supervisor tool-call within the decision sequence."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    tool_name: str = Field(min_length=1)
    args_summary: str = Field(
        max_length=512,
        description="Truncated, redaction-processed args summary.",
    )
    result_summary: str = Field(
        max_length=512,
        description="Truncated, redaction-processed result summary.",
    )
    duration_ms: int = Field(ge=0)


class ModelCallRecord(BaseModel):
    """One supervisor-side model invocation during dispatch."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    model_id: str = Field(min_length=1)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class CapabilityDescriptorRef(BaseModel):
    """Lightweight reference to a CapabilityDescriptor seen but not chosen."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    agent_id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    role: str = Field(min_length=1)
    tool_name_match: bool = Field(
        description=(
            "True if the descriptor's capability_list contained the requested "
            "tool_name."
        ),
    )
    intent_pattern_match: bool = Field(
        description=(
            "True if the descriptor's role/description matched the "
            "intent_pattern (when provided)."
        ),
    )


class ConcurrentWorkloadSnapshot(BaseModel):
    """Workload at decision time — feeds DDR-020 capacity diagnostics."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    in_flight_dispatches: int = Field(
        ge=0, description="Held by dispatch_semaphore."
    )
    in_flight_watchers: int = Field(
        ge=0, description="Pattern B watchers."
    )
    in_flight_subagents: int = Field(
        ge=0, description="AsyncSubAgent invocations."
    )


# ---------------------------------------------------------------------------
# §2 — RedirectAttempt
# ---------------------------------------------------------------------------


class RedirectAttempt(BaseModel):
    """One attempt within a ``dispatch_by_capability`` invocation."""

    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(
        pattern=r"^[a-z][a-z0-9-]*$",
        description="The specialist agent_id this attempt targeted.",
    )
    attempt_index: int = Field(
        ge=0,
        description=(
            "0-indexed position within the dispatch (0 = original, "
            "1 = first redirect)."
        ),
    )
    reason_skipped: Literal["timeout", "specialist_error", "transport_error"] = Field(
        description="Why this attempt didn't succeed.",
    )
    detail: str | None = Field(
        default=None,
        max_length=512,
        description=(
            "Truncated, redaction-processed detail. None for timeouts."
        ),
    )
    duration_ms: int = Field(
        ge=0,
        description="Wall-clock time the supervisor spent on this attempt.",
    )


# ---------------------------------------------------------------------------
# §3 — JarvisRoutingHistoryEntry (full schema)
# ---------------------------------------------------------------------------


class JarvisRoutingHistoryEntry(BaseModel):
    """ADR-FLEET-001-shaped trace record for one Jarvis dispatch decision.

    Authoritative for v1+ per DDR-018. Additions are append-only via
    ADR-FLEET-00X — never overwrite or rename existing fields. ``frozen=True``
    enforces immutability post-construction; updates from FEAT-J005
    stage-complete events go on the **edges**, not the entry.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    # ── §1 Decision identity (ADR-FLEET-001 §"Required fields" #1) ──────────
    decision_id: str = Field(
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        ),
        description="UUIDv4 — unique per decision.",
    )
    surface: Literal["jarvis"] = "jarvis"
    session_id: str = Field(
        min_length=1,
        description=(
            "Session correlation ID — Session.session_id (FEAT-J003 review F5)."
        ),
    )
    timestamp: datetime = Field(
        description="ISO 8601, UTC, timezone-aware.",
    )

    # ── §2 Reasoning context ────────────────────────────────────────────────
    supervisor_tool_call_sequence: list[ToolCallRecord] | TraceRef = Field(
        description=(
            "Inline list of {tool_name, args, result_summary} dicts when "
            "JSON-encoded payload is <=16KB; TraceRef pointing to "
            "~/.jarvis/traces/{date}/{decision_id}.json otherwise. "
            "ADR-FLEET-001 §'Large traces' filesystem offload."
        ),
    )
    priors_retrieved: list[str] = Field(
        default_factory=list,
        description=(
            "Graph entity IDs retrieved into the system prompt at decision "
            "time. Empty list in v1 (learning isn't reading); populated when "
            "FEAT-JARVIS-008 lands."
        ),
    )
    capability_snapshot_hash: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description=(
            "SHA-256 of the {available_capabilities} prompt block as rendered "
            "at decision time. Lets future analyses reconstruct the catalogue "
            "Jarvis saw without storing the full block per record."
        ),
    )

    # ── §3 Subagent delegation ──────────────────────────────────────────────
    subagent_type: Literal[
        "specialist",
        "forge_build_queue",
        "jarvis_reasoner",
    ]
    subagent_task_id: str = Field(
        min_length=1,
        description=(
            "For specialist: nats-core correlation_id. "
            "For forge_build_queue: BuildQueuedPayload.correlation_id. "
            "For jarvis_reasoner: thread_id."
        ),
    )
    subagent_trace_ref: TraceRef | None = Field(
        default=None,
        description=(
            "Optional reference to LangSmith trace or NATS dispatch ref. "
            "When the inline payload exceeds 16KB it points to the offload "
            "path."
        ),
    )
    subagent_final_state: Literal["success", "error", "timeout", "cancelled"]

    # ── §4 Resource cost ────────────────────────────────────────────────────
    model_calls: list[ModelCallRecord] = Field(
        default_factory=list,
        description=(
            "Reasoning-side model calls during dispatch (excluding the "
            "specialist's own internal model usage — that's their trace)."
        ),
    )
    wall_clock_ms: int = Field(
        ge=0,
        description="End-to-end time the supervisor spent on this decision.",
    )
    total_cost_usd: float = Field(
        ge=0.0,
        description=(
            "Summed cost of model_calls. 0.0 for pure-local dispatches "
            "(no cloud LLM use)."
        ),
    )

    # ── §5 Outcome ──────────────────────────────────────────────────────────
    outcome_type: DispatchOutcome
    outcome_detail: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Structured outcome metadata. Free-shape dict — keys vary by "
            "outcome_type. e.g. for 'redirected': "
            "{'final_attempt_index': 1, 'final_agent_id': 'product-owner'}."
        ),
    )

    # ── §6 Human response (populated later if Rich redirects) ───────────────
    human_response_type: (
        Literal["confirm", "reject", "redirect", "ignore", "override"] | None
    ) = None
    human_response_text: str | None = Field(
        default=None,
        max_length=4096,
        description=(
            "Free-text response when Rich engages mid-conversation. Captured "
            "as-is per ADR-FLEET-001 §6, redaction processor applied at write "
            "time per ADR-ARCH-029."
        ),
    )
    human_response_latency_ms: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Time from notification/pause to Rich's response. None for "
            "unattended/dispatch-only flows."
        ),
    )

    # ── §7 Environmental context ────────────────────────────────────────────
    project_id: str | None = Field(
        default=None,
        description=(
            "Pulled from session metadata when the session is project-scoped; "
            "None for general-purpose chat sessions."
        ),
    )
    local_time_of_day: str = Field(
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
        description="Local HH:MM, used for time-pattern detection.",
    )
    recent_session_refs: list[str] = Field(
        default_factory=list,
        max_length=10,
        description=(
            "Last 10 session_id references (sequence-pattern detection)."
        ),
    )
    concurrent_workload: ConcurrentWorkloadSnapshot = Field(
        description=(
            "{in_flight_dispatches: int, in_flight_watchers: int, "
            "in_flight_subagents: int} at decision time. Helps diagnose "
            "degraded-mode edge cases (e.g. semaphore overflow)."
        ),
    )

    # ── Jarvis-specific extensions (per ADR-FLEET-001 'per-group' clause) ───
    chosen_specialist_id: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9-]*$",
        description=(
            "agent_id of the specialist that ultimately replied (or None for "
            "unresolved/exhausted/transport_unavailable). Distinct from "
            "subagent_task_id which is the correlation."
        ),
    )
    chosen_subagent_name: str | None = Field(
        default=None,
        description=(
            "When subagent_type='jarvis_reasoner', the AsyncSubAgent name "
            "('jarvis-reasoner'); None otherwise. Reserved for future use."
        ),
    )
    alternatives_considered: list[CapabilityDescriptorRef] = Field(
        default_factory=list,
        description=(
            "Capability descriptors the supervisor saw in the catalogue but "
            "didn't pick. Each is a {agent_id, role, tool_name_match: bool, "
            "intent_pattern_match: bool} ref. Joins on chosen_specialist_id "
            "give the full picture."
        ),
    )
    attempts: list[RedirectAttempt] = Field(
        default_factory=list,
        description=(
            "Ordered list of redirect attempts. Length 0 on first-attempt "
            "success; length 1+ when retry-with-redirect fired."
        ),
    )
    supervisor_reasoning_summary: str = Field(
        max_length=1024,
        description=(
            "The supervisor's own rationale for the dispatch — a summary "
            "extracted from the tool-call sequence. Truncated to 1024 chars; "
            "redaction-processed."
        ),
    )


# ---------------------------------------------------------------------------
# §5 — RoutingHistoryWriter (DDR-018 + DDR-019 + DDR-023)
# ---------------------------------------------------------------------------

# Filesystem-offload threshold (DDR-018 / ADR-FLEET-001 §"Large traces").
# JSON payload of (supervisor_tool_call_sequence + subagent_trace_ref) is
# offloaded to ``~/.jarvis/traces/{date}/{decision_id}.json`` when its
# byte length exceeds this bound.
_OFFLOAD_THRESHOLD_BYTES = 16 * 1024


class GraphitiClientProtocol(Protocol):
    """Duck-typed surface the writer needs from a Graphiti client.

    The real client lives behind FEAT-JARVIS-004 wave 1; this protocol
    exists so the writer can be unit-tested without importing the SDK
    and so the Optional[None] startup-soft-fail path is type-checked.
    """

    async def add_episode(
        self,
        *,
        name: str,
        episode_body: str,
        source_description: str = ...,
        reference_time: datetime | None = ...,
    ) -> Any: ...


class RoutingHistoryWriter:
    """Fire-and-forget Graphiti writer for ``jarvis_routing_history``.

    DDR-019: failures log ``WARN routing_history_write_failed reason=…``
    and never raise — the supervisor stays up when Graphiti is degraded.

    DDR-018: oversized inline payloads are offloaded to the local trace
    store as flat JSON files; the entity itself stores only a
    :class:`TraceRef` pointer.

    DDR-023: pre-existing trace files at the same path are preserved
    (no overwrite). The Graphiti write is *also* skipped for that record
    because the entity needs a TraceRef the writer cannot construct
    without on-disk content.

    ADR-ARCH-029: redaction runs at the **write boundary**, not in a
    Pydantic validator. The frozen entry is never mutated — redaction
    operates on a ``model_dump(mode='json')`` copy.

    The writer creates one :class:`asyncio.Task` per Graphiti
    submission (the dispatch boundary owns the fire-and-forget); the
    method awaits the *submission*, not the round-trip.
    :meth:`flush` drains the in-flight set with a bounded timeout on
    shutdown.
    """

    def __init__(
        self,
        graphiti_client: GraphitiClientProtocol | None,
        config: JarvisConfig,
    ) -> None:
        """Build the writer.

        ``graphiti_client`` is ``None`` when Graphiti was unreachable at
        startup (DDR-019 startup soft-fail). In that mode, every write
        method is a no-op; the first call emits one ``WARN`` and
        subsequent calls are silent (no log spam).
        """
        self._graphiti_client = graphiti_client
        self._config = config
        self._graphiti_unavailable_warned: bool = False
        self._pending_tasks: set[asyncio.Task[Any]] = set()
        # DDR-029 §50 / DDR-018 — per-correlation monotonic edge counter.
        # Populated by ``write_build_queue_dispatch`` (registers correlation
        # at seq=0) and incremented by ``append_build_queue_event`` after
        # each successful submission. Membership in this dict is the
        # writer's "is this correlation known?" check.
        self._correlation_edge_seq: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public writer surface — API-internal.md §4
    # ------------------------------------------------------------------

    async def write_specialist_dispatch(
        self, entry: JarvisRoutingHistoryEntry
    ) -> None:
        """Persist a ``subagent_type='specialist'`` routing-history entry.

        Side-effect ordering (DDR-018 + DDR-019):

        1. Redact ``human_response_text``, ``supervisor_reasoning_summary``
           and every ``ToolCallRecord.{args_summary,result_summary}`` per
           ADR-ARCH-029. The same redaction is also applied to the file-side
           offload payload.
        2. JSON-encode ``supervisor_tool_call_sequence`` +
           ``subagent_trace_ref``.
        3. If the encoded payload exceeds 16KB, offload to
           ``~/.jarvis/traces/{date}/{decision_id}.json`` (mode 0700 dir,
           mode 0600 file) and replace both fields with a
           :class:`TraceRef` pointer.
        4. Submit Graphiti ``add_episode`` via :func:`asyncio.create_task`
           — fire-and-forget; this method awaits the *submission*.
        5. Any failure logs ``WARN routing_history_write_failed
           reason=<err>`` and is swallowed.
        """
        if self._graphiti_client is None:
            self._warn_graphiti_unavailable_once()
            return

        try:
            await self._write_entry(entry)
        except Exception as exc:  # DDR-019: fire-and-forget — never raise
            logger.warning(
                "routing_history_write_failed",
                extra={"reason": type(exc).__name__, "detail": str(exc)},
            )

    async def write_build_queue_dispatch(
        self, entry: JarvisRoutingHistoryEntry
    ) -> None:
        """Persist a ``subagent_type='forge_build_queue'`` routing-history entry.

        Mirrors :meth:`write_specialist_dispatch` (DDR-018 + DDR-019);
        the only difference is the ``subagent_type`` discriminator.
        Side-effect ordering:

        1. Redact human-shaped fields per ADR-ARCH-029 (delegated to
           :meth:`_write_entry`).
        2. JSON-encode ``supervisor_tool_call_sequence`` +
           ``subagent_trace_ref`` and offload above 16KB.
        3. Register ``entry.subagent_task_id`` in the per-correlation
           edge-seq map at seq=0 so subsequent
           :meth:`append_build_queue_event` calls can find it.
        4. Submit Graphiti ``add_episode`` via :func:`asyncio.create_task`
           (fire-and-forget — caller used ``asyncio.create_task`` at the
           ``queue_build`` boundary; this method awaits the *submission*).
        5. Failures log ``WARN routing_history_write_failed
           reason=<err>`` per DDR-019 and are swallowed — the writer
           never raises.
        """
        if self._graphiti_client is None:
            self._warn_graphiti_unavailable_once()
            return

        # Register the correlation BEFORE submitting so that a
        # stage-complete event racing the dispatch entry can still find
        # the parent. setdefault preserves an existing seq counter when
        # the same entry is replayed.
        self._correlation_edge_seq.setdefault(entry.subagent_task_id, 0)

        try:
            await self._write_entry(entry)
        except Exception as exc:  # DDR-019: fire-and-forget — never raise
            logger.warning(
                "routing_history_write_failed",
                extra={"reason": type(exc).__name__, "detail": str(exc)},
            )

    async def append_build_queue_event(
        self, correlation_id: str, event: dict[str, Any]
    ) -> None:
        """Append a ``stage_complete`` Graphiti edge for ``correlation_id``.

        DDR-029: each ``pipeline.stage-complete.*`` event lands as one
        append-only Graphiti edge against the originating
        :class:`JarvisRoutingHistoryEntry`. The entry stays
        ``frozen=True`` per DDR-018 — never mutated, never overwritten.
        Multiple events for the same ``correlation_id`` produce
        multiple distinct edges (one per call), each with a monotonic
        ``seq`` suffix so Graphiti entity names don't collide.

        Side-effect ordering:

        1. If the writer was constructed with ``graphiti_client=None``
           (DDR-019 startup soft-fail), emit the once-per-instance
           ``graphiti_unavailable`` WARN and return.
        2. If ``correlation_id`` is unknown (no
           :meth:`write_build_queue_dispatch` ever registered it — e.g.
           the correlation was evicted from DDR-028's bounded map),
           log ``WARN routing_history_append_failed
           reason=unknown_correlation`` and return.
        3. Redact ``event`` via the same recursive processor used by
           :meth:`write_specialist_dispatch` (ADR-ARCH-029); operates
           on a deep copy so the caller's dict is never mutated.
        4. Submit Graphiti ``add_episode`` with
           ``source_description='jarvis-routing-history-edge'`` and
           ``name='stage_complete:{correlation_id}:{seq}'`` — see
           DDR-029 §4 for the naming convention.
        5. Increment the per-correlation seq after successful
           submission scheduling.
        6. Any failure logs ``WARN routing_history_append_failed
           reason=<err>`` (DDR-019) and is swallowed.
        """
        if self._graphiti_client is None:
            self._warn_graphiti_unavailable_once()
            return

        if correlation_id not in self._correlation_edge_seq:
            # The correlation was never registered (or was evicted from
            # the DDR-028 bounded map). Drop silently with a WARN so the
            # subscriber doesn't hang on a missing parent entry.
            logger.warning(
                "routing_history_append_failed",
                extra={
                    "reason": "unknown_correlation",
                    "correlation_id": correlation_id,
                },
            )
            return

        try:
            # Redact-on-copy. The caller's dict (and the original
            # StageCompletePayload it came from) stays untouched.
            redacted_event = _redact_recursive(event)

            seq = self._correlation_edge_seq[correlation_id]
            edge_name = f"stage_complete:{correlation_id}:{seq}"

            # Pull a reference_time when the payload carries one. Both
            # the FEAT-J005 StageCompletePayload contract and the
            # ForgeNotification shape use ``completed_at``; we accept
            # either an ISO-8601 str or a ``datetime`` object.
            reference_time: datetime | None = None
            completed_at = redacted_event.get("completed_at")
            if isinstance(completed_at, datetime):
                reference_time = completed_at
            elif isinstance(completed_at, str):
                with contextlib.suppress(ValueError):
                    reference_time = datetime.fromisoformat(completed_at)

            assert self._graphiti_client is not None  # checked above
            episode_body = json.dumps(
                redacted_event, sort_keys=True, default=str
            )
            coro = self._graphiti_client.add_episode(
                name=edge_name,
                episode_body=episode_body,
                source_description="jarvis-routing-history-edge",
                reference_time=reference_time,
            )
            task = asyncio.create_task(coro)
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

            # Increment AFTER the submission task is scheduled so a
            # raised exception leaves the seq untouched (the next call
            # retries with the same seq, which is what we want).
            self._correlation_edge_seq[correlation_id] = seq + 1
        except Exception as exc:  # DDR-019: WARN-only, never raise
            logger.warning(
                "routing_history_append_failed",
                extra={
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                    "correlation_id": correlation_id,
                },
            )

    async def flush(self, *, timeout: float = 5.0) -> None:
        """Drain in-flight submission tasks; bounded by ``timeout``.

        DDR-019: on overflow log ``WARN routing_history_flush_timeout``
        and abandon the still-pending tasks. Never raises — shutdown
        must not be blocked by a degraded persistence layer.
        """
        pending = {task for task in self._pending_tasks if not task.done()}
        if not pending:
            return

        try:
            _, still_pending = await asyncio.wait(
                pending,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED,
            )
        except Exception as exc:  # DDR-019: never raise on shutdown
            logger.warning(
                "routing_history_flush_timeout",
                extra={
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                    "in_flight": len(pending),
                },
            )
            return

        if still_pending:
            logger.warning(
                "routing_history_flush_timeout",
                extra={
                    "in_flight": len(still_pending),
                    "timeout_seconds": timeout,
                },
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _warn_graphiti_unavailable_once(self) -> None:
        """Emit ``WARN`` exactly once per writer instance."""
        if self._graphiti_unavailable_warned:
            return
        logger.warning(
            "routing_history_write_failed",
            extra={"reason": "graphiti_unavailable"},
        )
        self._graphiti_unavailable_warned = True

    async def _write_entry(self, entry: JarvisRoutingHistoryEntry) -> None:
        """Inline-or-offload write path. Caller wraps the broad catch."""
        # 1. Dump-and-redact a deep copy. The frozen entry stays pristine.
        data = entry.model_dump(mode="json")
        data = _redact_recursive(data)

        # 2. Encode the offload-candidate component.
        offload_payload = {
            "supervisor_tool_call_sequence": data.get(
                "supervisor_tool_call_sequence"
            ),
            "subagent_trace_ref": data.get("subagent_trace_ref"),
        }
        encoded = json.dumps(
            offload_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")

        # 3. Offload when the encoded payload exceeds the 16KB threshold.
        if len(encoded) > _OFFLOAD_THRESHOLD_BYTES:
            offloaded = self._offload_to_filesystem(entry, encoded)
            if offloaded is None:
                # DDR-023 collision: do not call add_episode.
                return
            trace_ref_dict = offloaded.model_dump(mode="json")
            data["supervisor_tool_call_sequence"] = trace_ref_dict
            data["subagent_trace_ref"] = trace_ref_dict

        # 4. Submit Graphiti ``add_episode`` — fire-and-forget.
        assert self._graphiti_client is not None  # checked by caller
        coro = self._graphiti_client.add_episode(
            name=f"jarvis_routing_history:{entry.decision_id}",
            episode_body=json.dumps(data, sort_keys=True),
            source_description="jarvis-routing-history",
            reference_time=entry.timestamp,
        )
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    def _offload_to_filesystem(
        self, entry: JarvisRoutingHistoryEntry, encoded: bytes
    ) -> TraceRef | None:
        """Write ``encoded`` to ``~/.jarvis/traces/{date}/{decision_id}.json``.

        Creates the parent directory lazily with mode 0700 and the file
        with mode 0600. Returns the resulting :class:`TraceRef`.

        DDR-023 collision policy: when the target path already exists,
        log ``WARN`` with ``reason=trace_file_exists``, preserve the
        original, and return ``None`` so the caller skips the Graphiti
        submission.
        """
        date_str = entry.timestamp.strftime("%Y-%m-%d")
        traces_root = Path(self._config.jarvis_traces_dir)
        traces_dir = traces_root / date_str
        file_path = traces_dir / f"{entry.decision_id}.json"

        if file_path.exists():
            logger.warning(
                "routing_history_write_failed",
                extra={
                    "reason": "trace_file_exists",
                    "path": str(file_path),
                },
            )
            return None

        # Create the per-day directory with mode 0700. ``mkdir(mode=…)``
        # is umask-sensitive on POSIX, so chmod again after creation to
        # guarantee the bit pattern even when the parent already existed.
        traces_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        # On platforms where chmod is unsupported (Windows) we accept
        # whatever mkdir produced. Tests run on POSIX so the assertion
        # holds where it matters.
        with contextlib.suppress(OSError):
            traces_dir.chmod(0o700)

        file_path.write_bytes(encoded)
        with contextlib.suppress(OSError):
            file_path.chmod(0o600)

        content_sha256 = hashlib.sha256(encoded).hexdigest()
        return TraceRef(
            path=str(file_path),
            content_sha256=content_sha256,
            size_bytes=len(encoded),
        )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "REDACTION_PLACEHOLDER",
    "CapabilityDescriptorRef",
    "ConcurrentWorkloadSnapshot",
    "DispatchOutcome",
    "GraphitiClientProtocol",
    "JarvisRoutingHistoryEntry",
    "ModelCallRecord",
    "RedirectAttempt",
    "RoutingHistoryWriter",
    "ToolCallRecord",
    "TraceRef",
]
