"""Dispatch tool primitives — capability-driven dispatch and build queueing.

This module hosts the two dispatch tools (``dispatch_by_capability`` and
``queue_build``) that connect Jarvis to the NATS event bus.

* ``dispatch_by_capability`` — **FEAT-JARVIS-004 (TASK-J004-011)**: real
  NATS request/reply round-trip via ``NATSClient.request`` per design §8.
  The Phase 2 stub callable + ``logger.info`` log anchor are **retired**;
  module-level dependencies are now ``_nats_client``,
  ``_routing_history_writer``, ``_dispatch_semaphore``, and
  ``_capability_registry`` (see API-internal §7). Tool docstring and
  return shape stay byte-identical to Phase 2 — the reasoning model's view
  is unchanged across the swap.

* ``queue_build`` — **FEAT-JARVIS-005 (TASK-J005-005)**: real JetStream
  publish on ``pipeline.build-queued.{feature_id}`` per ADR-SP-014
  Pattern A and design.md §8. The Phase 2 stub callable +
  ``logger.info`` log anchor + queue-build grep token are
  **retired**; module-level dependencies for this tool are
  ``_nats_client``, ``_routing_history_writer``, ``_dispatch_semaphore``,
  ``_forge_subscriber`` and ``_jarvis_config`` (see API-internal §7).

The Phase 2 anchors on both halves of the seam have been retired:

* The dispatch-side Phase 2 anchors (the swap-point log-prefix constant,
  the test stub-response hook, and the ``StubResponse`` alias) were
  removed by TASK-J004-011.
* The queue-build-side Phase 2 anchor (the queue-build log-prefix
  constant and the associated ``logger.info`` line) was removed by
  TASK-J005-005.

Their absence is asserted by the (flipped) TASK-J002-021 grep invariant
landing in TASK-J004-020 / TASK-J005-011 (``test_no_phase_2_stub_anchors``
in ``test_no_retired_roster_strings`` and the
``tests/test_phase2_stubs_retired.py`` module).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from langchain_core.tools import tool
from nats_core import EventType, MessageEnvelope, Topics
from nats_core.events import BuildQueuedPayload, CommandPayload, ResultPayload
from pydantic import ValidationError

# ``Session`` is imported at runtime (not under TYPE_CHECKING) so the Layer 2
# resolver-hook annotations resolve cleanly under ``typing.get_type_hints``,
# which is exercised by ``test_tools_dispatch_contract`` for the swap-point
# seam. ``jarvis.sessions.session`` only depends on ``jarvis.shared.constants``
# so this introduces no import cycle with ``jarvis.tools``.
from jarvis.sessions.session import Session
from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools._correlation import new_correlation_id
from jarvis.tools.capabilities import CapabilityDescriptor
from jarvis.tools.dispatch_types import (
    FrontierEscalationContext,
    FrontierTarget,
    log_frontier_escalation,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.dispatch_semaphore import DispatchSemaphore
    from jarvis.infrastructure.forge_notifications import ForgeNotificationsSubscriber
    from jarvis.infrastructure.nats_client import NATSClient
    from jarvis.infrastructure.routing_history import RoutingHistoryWriter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-private validation patterns (kept aligned with nats_core.events
# but enforced at the tool boundary so we render ADR-ARCH-021-compliant
# error strings before the pydantic constructor runs).
# ---------------------------------------------------------------------------
_FEATURE_ID_PATTERN = re.compile(r"^FEAT-[A-Z0-9]{3,12}$")
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_ALLOWED_ADAPTERS: frozenset[str] = frozenset(
    {"terminal", "telegram", "dashboard", "voice-reachy", "slack", "cli-wrapper"}
)


def _now_utc() -> datetime:
    """Return a timezone-aware UTC ``datetime`` for envelope timestamps."""
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Phase-2 swap-point anchor retirement.
#
# The DDR-009 grep token used by the Phase 2 ``queue_build`` stub (the
# queue-build log-prefix constant) was retired by TASK-J005-005 — the
# tool now performs a real ``js.publish(...)`` round-trip and emits no
# anchor log line. The dispatch-side anchor was retired by TASK-J004-011.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DDR-031 — Session.adapter → BuildQueuedPayload.OriginatingAdapter map.
#
# The Session.adapter StrEnum (``cli`` / ``telegram`` / ``dashboard`` /
# ``reachy``) and the nats-core OriginatingAdapter Literal
# (``terminal`` / ``telegram`` / ``dashboard`` / ``voice-reachy`` /
# ``slack`` / ``cli-wrapper``) overlap but do not align by string. The
# closed mapping below is consumed by :func:`_resolve_originating_adapter`
# to project a Session into the wire-side adapter id at queue time per
# DDR-031.
# ---------------------------------------------------------------------------
_SESSION_ADAPTER_TO_ORIGINATING: dict[str, str] = {
    "cli": "terminal",
    "telegram": "telegram",
    "dashboard": "dashboard",
    "reachy": "voice-reachy",
}


# Default per-publish timeout when no JarvisConfig is wired (DDR-025).
_DEFAULT_PIPELINE_PUBLISH_TIMEOUT_SECONDS: int = 5


# ---------------------------------------------------------------------------
# Capability registry binding.
#
# ``assemble_tool_list`` (TASK-J002-015 + TASK-J004-013) snapshots a
# ``list[CapabilityDescriptor]`` into this module-level attribute at startup,
# providing the resolution catalogue for ``dispatch_by_capability``. The
# default is an empty list so a bare import of this module yields a tool
# that returns the ``ERROR: unresolved`` form for every dispatch — never
# raises.
#
# Snapshot isolation (ASSUM-006): assemble_tool_list MUST assign a fresh
# ``list(...)`` copy here, not the operator's mutable registry reference.
# ---------------------------------------------------------------------------
_capability_registry: list[CapabilityDescriptor] = []


# ---------------------------------------------------------------------------
# FEAT-JARVIS-004 dispatch dependencies — module-level swap points populated
# by ``assemble_tool_list`` at lifecycle startup (TASK-J004-013).
#
# Defaults are ``None`` so a bare import of this module never raises:
#
# * If ``_dispatch_semaphore`` is ``None`` the tool degrades gracefully —
#   no semaphore guard is applied (Phase-1 import-only invariant).
# * If ``_nats_client`` is ``None`` the tool returns the
#   ``DEGRADED: transport_unavailable`` structured error (DDR-021 soft-fail).
# * If ``_routing_history_writer`` is ``None`` the trace-write step is
#   skipped — the dispatch decision is still served, only the trace is
#   missing (Graphiti-degraded path).
#
# Production wiring assigns a connected ``NATSClient``, a configured
# ``DispatchSemaphore`` (DDR-020 cap=8), and a ``RoutingHistoryWriter``
# (which itself may carry a degraded Graphiti client per DDR-019).
# ---------------------------------------------------------------------------
_nats_client: NATSClient | None = None
_routing_history_writer: RoutingHistoryWriter | None = None
_dispatch_semaphore: DispatchSemaphore | None = None

# ---------------------------------------------------------------------------
# FEAT-JARVIS-005 (TASK-J005-008) — forge subscriber dependency.
#
# Snapshotted by ``assemble_tool_list`` at lifecycle startup so the
# ``queue_build`` tool body (TASK-J005-005) can call
# ``register_correlation`` immediately after a successful
# ``js.publish(...)`` PubAck. ``None`` means the subscriber was not wired
# (NATS soft-fail — DDR-021); the dispatch tool degrades by skipping the
# correlation register step rather than raising.
# ---------------------------------------------------------------------------
_forge_subscriber: ForgeNotificationsSubscriber | None = None

# ---------------------------------------------------------------------------
# TASK-JNB-002 — NotificationSink snapshot (mirrors _forge_subscriber pattern)
# ---------------------------------------------------------------------------
# Module-level snapshot for the bound NotificationSink (SlackNotifier in
# TASK-JNB-003). Wired via a setter from lifecycle.build_app_state, mirroring
# the existing _forge_subscriber / _nats_client pattern. Consumed by queue_build
# to fire build_queued notifications after PubAck/register_correlation (AC-010).

_notification_sink: Any = None


# ---------------------------------------------------------------------------
# FEAT-JARVIS-005 (TASK-J005-005 / TASK-J005-008) — JarvisConfig snapshot.
#
# ``queue_build`` reads ``pipeline_publish_timeout_seconds`` (DDR-025) from
# this module-level handle. ``None`` is the Phase-1 import-only default;
# :func:`_resolve_publish_timeout` falls back to
# :data:`_DEFAULT_PIPELINE_PUBLISH_TIMEOUT_SECONDS` so a bare import never
# raises.
# ---------------------------------------------------------------------------
_jarvis_config: JarvisConfig | None = None


# ---------------------------------------------------------------------------
# Retry-with-redirect policy (DDR-017): one redirect after a timeout or
# specialist_error reply. ``MAX_REDIRECTS = 1`` ⇒ at most 2 attempts per
# dispatch invocation. The lexicographic resolution order in
# :func:`_resolve_agent_id` is the determinism invariant — the integration
# tests in TASK-J004-015 pin the redirect target.
# ---------------------------------------------------------------------------
MAX_REDIRECTS: int = 1


def _resolve_agent_id(
    tool_name: str,
    intent_pattern: str | None,
    registry: list[CapabilityDescriptor],
    *,
    exclude: set[str] | None = None,
) -> str | None:
    """Resolve ``tool_name`` (and optional ``intent_pattern``) to an agent_id.

    Resolution order — AC-003 of TASK-J002-013, extended for retry-with-redirect
    in TASK-J004-011 via the ``exclude`` parameter:

    1. **Exact match**: first descriptor whose ``capability_list`` contains a
       :class:`CapabilityToolSummary` with ``tool_name`` equal to the
       requested name. Iterates descriptors in lexicographic ``agent_id``
       order so ties are deterministic (DDR-017 determinism invariant).
    2. **Intent fallback**: if ``intent_pattern`` is non-empty and no exact
       match was found, return the lexicographically-first descriptor whose
       ``role`` or ``description`` contains ``intent_pattern`` as a
       substring (case-sensitive — patterns are operator-curated tokens).
    3. ``None`` if no rule resolves (or every candidate is in ``exclude``).

    Args:
        tool_name: Requested ToolCapability name.
        intent_pattern: Optional intent-pattern fallback token.
        registry: Snapshot of capability descriptors.
        exclude: Optional set of ``agent_id`` values to skip. Used by the
            retry-with-redirect loop in :func:`dispatch_by_capability` to
            prevent repeating an attempt against the same specialist; the
            set is mutated by the caller after each attempt. ``None`` (the
            default) is treated as the empty set.

    Returns:
        ``agent_id`` of the resolved specialist or ``None``.
    """
    skip = exclude or set()
    sorted_descriptors = sorted(registry, key=lambda d: d.agent_id)

    for descriptor in sorted_descriptors:
        if descriptor.agent_id in skip:
            continue
        for cap in descriptor.capability_list:
            if cap.tool_name == tool_name:
                return descriptor.agent_id

    if intent_pattern:
        for descriptor in sorted_descriptors:
            if descriptor.agent_id in skip:
                continue
            if intent_pattern in descriptor.role or intent_pattern in descriptor.description:
                return descriptor.agent_id

    return None


def _capability_snapshot_hash(registry: list[CapabilityDescriptor]) -> str:
    """SHA-256 of the deterministic ``agent_id``-sorted snapshot.

    Used as the ``capability_snapshot_hash`` field on the routing-history
    entry. We hash ``agent_id`` only (not the full descriptor) so the hash
    captures *fleet membership* — the per-capability metadata is already
    persisted via ``alternatives_considered`` when the supervisor
    eventually wires that capture path. The hash format is the standard
    64-char lowercase hex digest matching the schema's regex.
    """
    sorted_ids = sorted(d.agent_id for d in registry)
    raw = "\n".join(sorted_ids).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _build_command_envelope(
    tool_name: str,
    parsed_args: dict[str, object],
    correlation_id: str,
) -> tuple[CommandPayload, MessageEnvelope]:
    """Construct the ``CommandPayload`` + ``MessageEnvelope`` pair.

    Centralises the shape so the retry-with-redirect loop reuses the same
    payload bytes per attempt. ``source_id="jarvis"`` is set on every
    emitted envelope per the task's AC-003.
    """
    command = CommandPayload(
        command=tool_name,
        args=parsed_args,
        correlation_id=correlation_id,
    )
    envelope = MessageEnvelope(
        source_id="jarvis",
        event_type=EventType.COMMAND,
        correlation_id=correlation_id,
        payload=command.model_dump(mode="json"),
    )
    return command, envelope


def _fire_and_forget_trace(entry_kwargs: dict[str, object]) -> None:
    """Fire-and-forget submission of a routing-history entry.

    DDR-019: the dispatch tool never awaits the writer's coroutine; the
    writer's WARN log is the only failure surface. We resolve the writer
    via the module-level ``_routing_history_writer`` so test fixtures can
    swap it without touching the call site.

    The function silently returns when:

    * the writer is ``None`` (dispatch is wired without persistence —
      Phase-1 import-only invariant),
    * the routing-history schema rejects the entry kwargs (degraded
      branch — we'd rather lose a trace than break the dispatch contract),
    * ``asyncio.create_task`` cannot be scheduled because the function
      is being called from a synchronous context (defensive — the
      production caller is always inside the async dispatch loop).
    """
    writer = _routing_history_writer
    if writer is None:
        return

    # Lazy import to keep the dispatch module's import graph stable for
    # Phase-1 import-graph tests (the routing_history module pulls in
    # pydantic schemas that aren't on the import-time hot path).
    from jarvis.infrastructure.routing_history import JarvisRoutingHistoryEntry

    try:
        entry = JarvisRoutingHistoryEntry.model_validate(entry_kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "dispatch_trace_validation_failed",
            extra={
                "reason": type(exc).__name__,
                "detail": str(exc),
            },
        )
        return

    try:
        coro = writer.write_specialist_dispatch(entry)
        # DDR-019: the dispatch boundary intentionally drops the task ref.
        # The writer's own ``_pending_tasks`` set keeps the task alive until
        # ``flush()`` drains them on shutdown.
        asyncio.create_task(coro)  # noqa: RUF006
    except RuntimeError:
        # No running event loop — should not happen from the async dispatch
        # body, but if a caller invokes ``dispatch_by_capability`` from a
        # sync wrapper we silently drop the trace rather than crash.
        return


@tool(parse_docstring=True)
async def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str | None = None,
    timeout_seconds: int = 60,
) -> str:
    """Dispatch work to a specialist agent by capability name, not agent name.

    Resolution order:
      1. Exact match on a registered ToolCapability.name across the catalogue.
      2. If no exact match, match IntentCapability.pattern (if intent_pattern
         is provided) with highest confidence wins.
      3. If still unresolved, returns ``ERROR: unresolved``. Reason the
         response yourself — do not retry the same dispatch with a different
         tool_name unless the user confirms.

    Use this tool when the user asks for work that falls under a specialist
    agent's description (e.g. "ask the architect for a C4 diagram", "have
    product-owner review this spec"). Check the capability catalogue first —
    injected at session start under "## Available Capabilities" — to find the
    tool_name you need. Do NOT pass agent IDs; pass capability names.

    Cost depends on the resolved specialist; latency is capped by
    timeout_seconds. Moderate cost (~$0.10-$2 per dispatch, specialist-
    dependent); 5-60s typical wall-clock.

    Args:
        tool_name: The ToolCapability.name to invoke (e.g.
                   ``run_architecture_session``). Required.
        payload_json: JSON string matching the tool's parameters schema as
                     declared in its ToolCapability.parameters. Must be a JSON
                     object literal (starts with ``{``). The tool does NOT
                     validate your payload against the schema — the
                     specialist will.
        intent_pattern: Optional intent pattern (e.g. ``architecture.generate``)
                       used only when no exact tool match is found.
        timeout_seconds: How long to wait for the specialist's reply, between
                        5 and 600. Default 60. Timeout returns a structured
                        TIMEOUT error; it does NOT cancel the specialist — the
                        result may still appear in NATS after timeout.

    Returns:
        JSON string of the specialist's ResultPayload on success:
          ``{"command": str, "result": {...}, "correlation_id": str,
             "success": true}``
        OR a structured error:
          - ``ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>``
          - ``ERROR: invalid_payload — payload_json is not a JSON object literal``
          - ``ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>``
          - ``TIMEOUT: agent_id=<id> tool_name=<x> timeout_seconds=<n>``
          - ``ERROR: specialist_error — agent_id=<id> detail=<reason>``
          - ``DEGRADED: dispatch_overloaded — wait and retry``
          - ``DEGRADED: transport_unavailable — NATS connection failed``
    """
    # ----- Per-call correlation id (ASSUM-001 — one CSPRNG read per call) ---
    correlation_id = new_correlation_id()

    # ----- Validate timeout_seconds -----------------------------------------
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool):
        return f"ERROR: invalid_timeout — timeout_seconds must be 5..600, got {timeout_seconds!r}"
    if timeout_seconds < 5 or timeout_seconds > 600:
        return f"ERROR: invalid_timeout — timeout_seconds must be 5..600, got {timeout_seconds}"

    # ----- Validate payload_json is a JSON object literal -------------------
    stripped = payload_json.lstrip() if isinstance(payload_json, str) else ""
    if not stripped.startswith("{"):
        return "ERROR: invalid_payload — payload_json is not a JSON object literal"
    try:
        parsed_args = json.loads(payload_json)
    except (ValueError, TypeError):
        return "ERROR: invalid_payload — payload_json is not a JSON object literal"
    if not isinstance(parsed_args, dict):
        return "ERROR: invalid_payload — payload_json is not a JSON object literal"

    # ----- Semaphore (DDR-020 — synchronous overflow check) -----------------
    semaphore = _dispatch_semaphore
    sem_acquired = False
    if semaphore is not None:
        sem_acquired = semaphore.try_acquire()
        if not sem_acquired:
            # Overflow — surface DEGRADED synchronously per DDR-020. No
            # trace is written (the request never reached the wire).
            return "DEGRADED: dispatch_overloaded — wait and retry"

    # Snapshot the registry once so concurrent rebinding does not
    # corrupt the resolution loop (ASSUM-006).
    registry_snapshot = list(_capability_registry)
    snapshot_hash = _capability_snapshot_hash(registry_snapshot)
    started_at = _now_utc()
    started_monotonic = time.monotonic()

    visited: set[str] = set()
    attempts: list[dict[str, object]] = []
    attempt_index = 0

    # The default "outcome" for every early-return guard below — the trace
    # writer captures these structured outcomes per design §8.
    last_agent_id: str | None = None

    try:
        while attempt_index <= MAX_REDIRECTS:
            agent_id = _resolve_agent_id(
                tool_name,
                intent_pattern,
                registry_snapshot,
                exclude=visited,
            )
            if agent_id is None:
                # First-attempt unresolved vs. exhausted-after-redirect.
                outcome: Literal["unresolved", "exhausted"] = (
                    "exhausted" if attempts else "unresolved"
                )
                _fire_and_forget_trace(
                    _build_trace_kwargs(
                        correlation_id=correlation_id,
                        timestamp=started_at,
                        snapshot_hash=snapshot_hash,
                        attempts=attempts,
                        chosen_agent_id=None,
                        outcome=outcome,
                        outcome_detail={
                            "tool_name": tool_name,
                            "intent_pattern": intent_pattern,
                            "visited": sorted(visited),
                        },
                        wall_clock_ms=_elapsed_ms(started_monotonic),
                        in_flight=_in_flight_or_zero(semaphore),
                    )
                )
                if outcome == "exhausted":
                    return (
                        f"TIMEOUT: agent_id={last_agent_id} tool_name={tool_name} "
                        f"exhausted attempts={len(attempts)}"
                    )
                return (
                    f"ERROR: unresolved — no capability matches "
                    f"tool_name={tool_name} intent_pattern={intent_pattern}"
                )

            visited.add(agent_id)
            last_agent_id = agent_id

            try:
                _command, envelope = _build_command_envelope(tool_name, parsed_args, correlation_id)
            except ValidationError as exc:
                # Boundary guard — payload schema mismatch surfaces as a
                # structured error and skips the trace write.
                return f"ERROR: validation — {exc.errors()[0].get('msg', str(exc))}"
            except (TypeError, ValueError) as exc:
                return f"ERROR: validation — {exc}"

            client = _nats_client
            if client is None:
                # No transport wired — DDR-021 soft-fail. We still write a
                # trace so the operator sees the diagnostic.
                _fire_and_forget_trace(
                    _build_trace_kwargs(
                        correlation_id=correlation_id,
                        timestamp=started_at,
                        snapshot_hash=snapshot_hash,
                        attempts=attempts,
                        chosen_agent_id=None,
                        outcome="transport_unavailable",
                        outcome_detail={
                            "agent_id": agent_id,
                            "reason": "nats_client_unwired",
                        },
                        wall_clock_ms=_elapsed_ms(started_monotonic),
                        in_flight=_in_flight_or_zero(semaphore),
                    )
                )
                return "DEGRADED: transport_unavailable — NATS connection failed"

            subject = Topics.Agents.COMMAND.format(agent_id=agent_id)
            payload_bytes = envelope.model_dump_json().encode("utf-8")
            attempt_started = time.monotonic()

            try:
                reply = await asyncio.wait_for(
                    client.request(subject, payload_bytes, timeout=timeout_seconds),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                attempts.append(
                    {
                        "agent_id": agent_id,
                        "attempt_index": attempt_index,
                        "reason_skipped": "timeout",
                        "detail": None,
                        "duration_ms": _elapsed_ms(attempt_started),
                    }
                )
                attempt_index += 1
                continue
            except NATSConnectionError as exc:
                _fire_and_forget_trace(
                    _build_trace_kwargs(
                        correlation_id=correlation_id,
                        timestamp=started_at,
                        snapshot_hash=snapshot_hash,
                        attempts=attempts,
                        chosen_agent_id=None,
                        outcome="transport_unavailable",
                        outcome_detail={
                            "agent_id": agent_id,
                            "reason": type(exc).__name__,
                            "detail": str(exc),
                        },
                        wall_clock_ms=_elapsed_ms(started_monotonic),
                        in_flight=_in_flight_or_zero(semaphore),
                    )
                )
                return "DEGRADED: transport_unavailable — NATS connection failed"

            # Decode the specialist's reply.
            reply_body = getattr(reply, "data", None)
            if reply_body is None:
                attempts.append(
                    {
                        "agent_id": agent_id,
                        "attempt_index": attempt_index,
                        "reason_skipped": "specialist_error",
                        "detail": "empty reply body",
                        "duration_ms": _elapsed_ms(attempt_started),
                    }
                )
                attempt_index += 1
                continue

            try:
                result = ResultPayload.model_validate_json(reply_body)
            except ValidationError as exc:
                attempts.append(
                    {
                        "agent_id": agent_id,
                        "attempt_index": attempt_index,
                        "reason_skipped": "specialist_error",
                        "detail": _truncate(str(exc), 512),
                        "duration_ms": _elapsed_ms(attempt_started),
                    }
                )
                attempt_index += 1
                continue

            if result.success:
                outcome_success: Literal["success", "redirected"] = (
                    "success" if attempt_index == 0 else "redirected"
                )
                _fire_and_forget_trace(
                    _build_trace_kwargs(
                        correlation_id=correlation_id,
                        timestamp=started_at,
                        snapshot_hash=snapshot_hash,
                        attempts=attempts,
                        chosen_agent_id=agent_id,
                        outcome=outcome_success,
                        outcome_detail={
                            "final_attempt_index": attempt_index,
                            "final_agent_id": agent_id,
                        },
                        wall_clock_ms=_elapsed_ms(started_monotonic),
                        in_flight=_in_flight_or_zero(semaphore),
                    )
                )
                return result.model_dump_json()

            # ResultPayload with success=False → record reason and continue.
            failure_detail = _extract_specialist_error(result)
            attempts.append(
                {
                    "agent_id": agent_id,
                    "attempt_index": attempt_index,
                    "reason_skipped": "specialist_error",
                    "detail": _truncate(failure_detail, 512),
                    "duration_ms": _elapsed_ms(attempt_started),
                }
            )
            attempt_index += 1

        # Loop exit: every attempt timed out or returned a non-success
        # specialist reply. Per design §8, surface as exhausted (TIMEOUT).
        _fire_and_forget_trace(
            _build_trace_kwargs(
                correlation_id=correlation_id,
                timestamp=started_at,
                snapshot_hash=snapshot_hash,
                attempts=attempts,
                chosen_agent_id=None,
                outcome="exhausted",
                outcome_detail={
                    "tool_name": tool_name,
                    "attempts": len(attempts),
                },
                wall_clock_ms=_elapsed_ms(started_monotonic),
                in_flight=_in_flight_or_zero(semaphore),
            )
        )
        return (
            f"TIMEOUT: agent_id={last_agent_id} tool_name={tool_name} "
            f"exhausted attempts={len(attempts)}"
        )
    finally:
        # Semaphore is released in EVERY outcome path per AC-008 of this
        # task — success, timeout, exhausted, transport_unavailable,
        # unresolved, validation-error, and any unexpected exception.
        if sem_acquired and semaphore is not None:
            semaphore.release()


def _build_trace_kwargs(
    *,
    correlation_id: str,
    timestamp: datetime,
    snapshot_hash: str,
    attempts: list[dict[str, object]],
    chosen_agent_id: str | None,
    outcome: str,
    outcome_detail: dict[str, object],
    wall_clock_ms: int,
    in_flight: int,
) -> dict[str, object]:
    """Build the ``JarvisRoutingHistoryEntry`` kwargs for a dispatch decision.

    The dispatch tool does not have direct access to the active session
    (the supervisor's ``Session`` lives one level up the call stack), so
    the structural fields that require a session context use the
    ``correlation_id`` as the session marker. FEAT-JARVIS-008 will plumb
    the real session_id once the learning subsystem is wired.

    Mapping from dispatch outcomes to ``subagent_final_state``:

    * ``success`` / ``redirected`` → ``"success"``.
    * ``timeout`` / ``exhausted`` → ``"timeout"``.
    * ``transport_unavailable`` / ``unresolved`` / ``specialist_error``
      → ``"error"``.
    """
    if outcome in ("success", "redirected"):
        final_state: Literal["success", "error", "timeout", "cancelled"] = "success"
    elif outcome in ("timeout", "exhausted"):
        final_state = "timeout"
    else:
        final_state = "error"

    return {
        "decision_id": correlation_id,
        "surface": "jarvis",
        # session_id placeholder — see docstring above. Non-empty so the
        # ``min_length=1`` validator passes.
        "session_id": f"dispatch:{correlation_id}",
        "timestamp": timestamp,
        "supervisor_tool_call_sequence": [],
        "priors_retrieved": [],
        "capability_snapshot_hash": snapshot_hash,
        "subagent_type": "specialist",
        "subagent_task_id": correlation_id,
        "subagent_trace_ref": None,
        "subagent_final_state": final_state,
        "model_calls": [],
        "wall_clock_ms": wall_clock_ms,
        "total_cost_usd": 0.0,
        "outcome_type": outcome,
        "outcome_detail": outcome_detail,
        "human_response_type": None,
        "human_response_text": None,
        "human_response_latency_ms": None,
        "project_id": None,
        "local_time_of_day": timestamp.astimezone(UTC).strftime("%H:%M"),
        "recent_session_refs": [],
        "concurrent_workload": {
            "in_flight_dispatches": in_flight,
            "in_flight_watchers": 0,
            "in_flight_subagents": 0,
        },
        "chosen_specialist_id": chosen_agent_id,
        "chosen_subagent_name": None,
        "alternatives_considered": [],
        "attempts": attempts,
        "supervisor_reasoning_summary": "dispatch_by_capability",
    }


def _extract_specialist_error(result: ResultPayload) -> str:
    """Pull a human-readable error string off a failed ``ResultPayload``.

    The ``ResultPayload`` schema doesn't pin a specific error-key location
    so we look at ``result.error`` first (the convention adopted by the
    nats-core specialists) and fall back to a JSON dump of ``result.result``.
    """
    if isinstance(result.result, dict):
        for key in ("error", "reason", "detail", "message"):
            value = result.result.get(key)
            if isinstance(value, str) and value:
                return value
    try:
        return json.dumps(result.result)[:512]
    except (TypeError, ValueError):
        return "specialist returned success=False with unserialisable result"


def _truncate(value: str, max_length: int) -> str:
    """Helper for fitting strings into ``RedirectAttempt.detail`` (max 512)."""
    if len(value) <= max_length:
        return value
    return value[: max_length - 1] + "…"


def _elapsed_ms(started_monotonic: float) -> int:
    """Convert ``time.monotonic`` start to integer milliseconds elapsed."""
    elapsed = time.monotonic() - started_monotonic
    return max(0, int(elapsed * 1000))


def _in_flight_or_zero(semaphore: DispatchSemaphore | None) -> int:
    """Read ``semaphore.in_flight`` or ``0`` when no semaphore is wired."""
    if semaphore is None:
        return 0
    return semaphore.in_flight


# ---------------------------------------------------------------------------
# queue_build helpers — DDR-031 adapter resolution + ADR-ARCH-021 structured
# error renderers + DDR-029 fire-and-forget routing-history hook.
# ---------------------------------------------------------------------------


def _resolve_originating_adapter(arg_value: str | None) -> str | None:
    """Return the wire-side ``OriginatingAdapter`` for the active session.

    Implements DDR-031: when a :class:`Session` is currently driving a
    supervisor turn, its ``Session.adapter`` is projected through
    :data:`_SESSION_ADAPTER_TO_ORIGINATING` and that value is authoritative
    — the reasoning model's ``originating_adapter`` argument is silently
    ignored (Group D #4 security scenario). When no session is active the
    argument is used as a fallback after validating it against the
    :class:`nats_core.events.OriginatingAdapter` literal members.

    Returns ``None`` when neither path yields a valid adapter id.
    """
    session = _resolve_current_session()
    if session is not None:
        adapter_value = getattr(session, "adapter", None)
        if adapter_value is not None:
            mapped = _SESSION_ADAPTER_TO_ORIGINATING.get(str(adapter_value))
            if mapped is not None:
                return mapped
    if isinstance(arg_value, str) and arg_value in _ALLOWED_ADAPTERS:
        return arg_value
    return None


def _resolve_publish_timeout() -> int:
    """Return ``pipeline_publish_timeout_seconds`` from the wired config.

    Falls back to :data:`_DEFAULT_PIPELINE_PUBLISH_TIMEOUT_SECONDS` when no
    :class:`JarvisConfig` is wired (Phase-1 import-only invariant) or the
    field cannot be coerced to a positive ``int``. Never raises.
    """
    config = _jarvis_config
    if config is None:
        return _DEFAULT_PIPELINE_PUBLISH_TIMEOUT_SECONDS
    value = getattr(config, "pipeline_publish_timeout_seconds", None)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return _DEFAULT_PIPELINE_PUBLISH_TIMEOUT_SECONDS


def _queue_build_validation_error(
    reason: str,
    detail: str,
    *,
    correlation_id: str,
    feature_id: str,
) -> str:
    """Render a ``status='validation_error'`` JSON string per ADR-ARCH-021."""
    return json.dumps(
        {
            "status": "validation_error",
            "reason": reason,
            "detail": detail,
            "correlation_id": correlation_id,
            "feature_id": feature_id,
        }
    )


def _queue_build_degraded_error(
    reason: str,
    detail: str,
    *,
    correlation_id: str,
    feature_id: str,
) -> str:
    """Render a ``status='degraded'`` JSON string per ADR-ARCH-021."""
    return json.dumps(
        {
            "status": "degraded",
            "reason": reason,
            "detail": detail,
            "correlation_id": correlation_id,
            "feature_id": feature_id,
        }
    )


def _fire_and_forget_build_queue_trace(
    *,
    correlation_id: str,
    session_id: str | None,
    timestamp: datetime,
    feature_id: str,
    adapter: str,
    subject: str,
    in_flight: int,
) -> None:
    """Submit a ``forge_build_queue`` routing-history entry fire-and-forget.

    DDR-019 / DDR-029: ``queue_build`` schedules the writer's coroutine via
    :func:`asyncio.create_task` and drops the task reference. The writer's
    ``_pending_tasks`` set keeps the task alive until ``flush()`` drains it
    on shutdown.

    Silently returns when the writer is unwired, the schema rejects the
    synthesised entry, or no event loop is running — we'd rather lose a
    trace than break the dispatch contract.
    """
    writer = _routing_history_writer
    if writer is None:
        return

    # Lazy import keeps the dispatch import graph stable for Phase-1
    # import-graph tests (the routing_history module pulls in pydantic
    # schemas that aren't on the import-time hot path).
    from jarvis.infrastructure.routing_history import JarvisRoutingHistoryEntry

    snapshot_hash = _capability_snapshot_hash([])

    session_marker = (
        session_id
        if isinstance(session_id, str) and session_id
        else f"queue_build:{correlation_id}"
    )

    entry_kwargs: dict[str, object] = {
        "decision_id": correlation_id,
        "surface": "jarvis",
        "session_id": session_marker,
        "timestamp": timestamp,
        "supervisor_tool_call_sequence": [],
        "priors_retrieved": [],
        "capability_snapshot_hash": snapshot_hash,
        "subagent_type": "forge_build_queue",
        "subagent_task_id": correlation_id,
        "subagent_trace_ref": None,
        "subagent_final_state": "success",
        "model_calls": [],
        "wall_clock_ms": 0,
        "total_cost_usd": 0.0,
        "outcome_type": "success",
        "outcome_detail": {
            "feature_id": feature_id,
            "adapter": adapter,
            "subject": subject,
        },
        "human_response_type": None,
        "human_response_text": None,
        "human_response_latency_ms": None,
        "project_id": None,
        "local_time_of_day": timestamp.astimezone(UTC).strftime("%H:%M"),
        "recent_session_refs": [],
        "concurrent_workload": {
            "in_flight_dispatches": in_flight,
            "in_flight_watchers": 0,
            "in_flight_subagents": 0,
        },
        "chosen_specialist_id": None,
        "chosen_subagent_name": None,
        "alternatives_considered": [],
        "attempts": [],
        "supervisor_reasoning_summary": "queue_build",
    }

    try:
        entry = JarvisRoutingHistoryEntry.model_validate(entry_kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(
            "queue_build_trace_validation_failed",
            extra={
                "reason": type(exc).__name__,
                "detail": str(exc),
                "correlation_id": correlation_id,
            },
        )
        return

    try:
        coro = writer.write_build_queue_dispatch(entry)
        # DDR-019: drop the task reference; writer keeps it alive.
        asyncio.create_task(coro)  # noqa: RUF006
    except RuntimeError:
        # No running event loop (sync-context call) — silently drop the
        # trace rather than raise out of the dispatch boundary.
        return


@tool(parse_docstring=True)
async def queue_build(
    feature_id: str,
    feature_yaml_path: str,
    repo: str,
    branch: str = "main",
    originating_adapter: str = "terminal",
    correlation_id: str | None = None,
    parent_request_id: str | None = None,
) -> str:
    """Queue a Forge build for an already-planned feature. Pattern A per
    ADR-SP-014: Jarvis publishes and walks away; Forge consumes from JetStream.

    Use this tool when the user has a feature spec already produced (via
    /feature-spec and /feature-plan) and says "build it" or equivalent. Do NOT
    use it to kick off planning — that is not a Forge responsibility. If the
    user asks you to plan, route to the architect or product-owner specialist
    via dispatch_by_capability instead.

    Fire-and-forget. Near-zero publish latency under healthy transport;
    Forge may take hours to complete the build — you will receive
    pipeline.* progress events via notifications. Do not await completion.

    Args:
        feature_id: FEAT-XXX identifier matching ``^FEAT-[A-Z0-9]{3,12}$``.
        feature_yaml_path: Path to the feature YAML spec, relative to the
                           repo root (e.g. ``features/feat-jarvis-002/....yaml``).
        repo: GitHub org/repo, e.g. ``guardkit/jarvis`` or ``appmilla/forge``.
              Must match ``^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$``.
        branch: Base branch to branch from. Default ``main``.
        originating_adapter: Fallback adapter label used only when no Session
                            is active (DDR-031). When a Session is active,
                            its ``Session.adapter`` is authoritative and the
                            reasoning model's argument is silently ignored.
                            One of ``terminal``, ``voice-reachy``,
                            ``telegram``, ``slack``, ``dashboard``,
                            ``cli-wrapper``. Default ``terminal``.
                            ``triggered_by`` is always set to ``jarvis``.
        correlation_id: Stable ID for tracing. Auto-generated if omitted.
        parent_request_id: The Jarvis dispatch message ID that spawned this
                          build, for progress-event correlation. Optional.

    Returns:
        JSON string of the QueueBuildAck on success:
          ``{"feature_id": str, "correlation_id": str,
             "queued_at": ISO8601,
             "publish_target": "pipeline.build-queued.{feature_id}",
             "status": "queued"}``
        OR a structured error per ADR-ARCH-021 (always JSON, never raises):
          - ``{"status": "validation_error", "reason": "invalid_feature_id", ...}``
          - ``{"status": "validation_error", "reason": "invalid_repo", ...}``
          - ``{"status": "validation_error", "reason": "invalid_adapter", ...}``
          - ``{"status": "validation_error", "reason": "validation", ...}``
          - ``{"status": "degraded", "reason": "transport_unavailable", ...}``
          - ``{"status": "degraded", "reason": "dispatch_capacity_saturated", ...}``
    """
    # ----- Resolve correlation id once so every error path carries it -------
    resolved_correlation_id = correlation_id or new_correlation_id()
    requested_at = _now_utc()

    # ----- Validate feature_id ---------------------------------------------
    if not isinstance(feature_id, str) or not _FEATURE_ID_PATTERN.match(feature_id):
        return _queue_build_validation_error(
            "invalid_feature_id",
            f"must match FEAT-XXX pattern, got {feature_id!r}",
            correlation_id=resolved_correlation_id,
            feature_id=feature_id if isinstance(feature_id, str) else "",
        )

    # ----- Validate repo ----------------------------------------------------
    if not isinstance(repo, str) or not _REPO_PATTERN.match(repo):
        return _queue_build_validation_error(
            "invalid_repo",
            f"must be org/name format, got {repo!r}",
            correlation_id=resolved_correlation_id,
            feature_id=feature_id,
        )

    # ----- Resolve originating adapter (DDR-031) ----------------------------
    # Session.adapter (when present) authoritatively overrides any value
    # the reasoning model passed; the arg is fallback-only when no session
    # is active. Group D #4 security scenario.
    resolved_adapter = _resolve_originating_adapter(originating_adapter)
    if resolved_adapter is None:
        return _queue_build_validation_error(
            "invalid_adapter",
            f"{originating_adapter!r} not in allowed list",
            correlation_id=resolved_correlation_id,
            feature_id=feature_id,
        )

    # ----- Acquire dispatch_semaphore (DDR-020 reuse) ----------------------
    semaphore = _dispatch_semaphore
    sem_acquired = False
    if semaphore is not None:
        sem_acquired = semaphore.try_acquire()
        if not sem_acquired:
            return _queue_build_degraded_error(
                "dispatch_capacity_saturated",
                "queue_build dispatch slot saturated; wait and retry",
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )

    try:
        # ----- Resolve session metadata for parent_request_id fallback ----
        session = _resolve_current_session()
        resolved_parent_request_id = parent_request_id
        if resolved_parent_request_id is None and session is not None:
            metadata = getattr(session, "metadata", None) or {}
            session_parent = metadata.get("parent_request_id")
            if isinstance(session_parent, str) and session_parent:
                resolved_parent_request_id = session_parent

        queued_at = _now_utc()

        # ----- Build real nats-core payload + envelope -------------------
        try:
            payload = BuildQueuedPayload(
                feature_id=feature_id,
                repo=repo,
                branch=branch,
                feature_yaml_path=feature_yaml_path,
                triggered_by="jarvis",
                originating_adapter=resolved_adapter,  # type: ignore[arg-type]
                correlation_id=resolved_correlation_id,
                parent_request_id=resolved_parent_request_id,
                requested_at=requested_at,
                queued_at=queued_at,
            )
            envelope = MessageEnvelope(
                source_id="jarvis",
                event_type=EventType.BUILD_QUEUED,
                correlation_id=resolved_correlation_id,
                payload=payload.model_dump(mode="json"),
            )
        except ValidationError as exc:
            detail = exc.errors()[0].get("msg", str(exc))
            return _queue_build_validation_error(
                "validation",
                str(detail),
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )
        except (TypeError, ValueError) as exc:
            return _queue_build_validation_error(
                "validation",
                str(exc),
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )

        # ----- Subject from canonical Topics template --------------------
        subject = Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)
        payload_bytes = envelope.model_dump_json().encode("utf-8")

        # ----- Resolve transport — degrade when NATS not wired -----------
        client = _nats_client
        if client is None:
            return _queue_build_degraded_error(
                "transport_unavailable",
                "NATS connection unavailable",
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )

        try:
            js = client.js
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "queue_build_jetstream_unavailable",
                extra={
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                    "correlation_id": resolved_correlation_id,
                },
            )
            return _queue_build_degraded_error(
                "transport_unavailable",
                f"JetStream context unavailable: {type(exc).__name__}",
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )

        # ----- Real JetStream publish with bounded timeout (DDR-025) -----
        timeout_seconds = _resolve_publish_timeout()
        try:
            await asyncio.wait_for(
                js.publish(subject, payload_bytes),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            logger.warning(
                "queue_build_publish_timeout",
                extra={
                    "feature_id": feature_id,
                    "correlation_id": resolved_correlation_id,
                    "timeout_seconds": timeout_seconds,
                    "subject": subject,
                },
            )
            return _queue_build_degraded_error(
                "transport_unavailable",
                f"PubAck timeout after {timeout_seconds}s",
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )
        except NATSConnectionError as exc:
            logger.warning(
                "queue_build_publish_failed",
                extra={
                    "feature_id": feature_id,
                    "correlation_id": resolved_correlation_id,
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                },
            )
            return _queue_build_degraded_error(
                "transport_unavailable",
                f"NATS publish failed: {exc}",
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )
        except Exception as exc:
            # Boundary guard per ADR-ARCH-021: queue_build never raises.
            logger.warning(
                "queue_build_publish_failed",
                extra={
                    "feature_id": feature_id,
                    "correlation_id": resolved_correlation_id,
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                },
            )
            return _queue_build_degraded_error(
                "transport_unavailable",
                f"NATS publish failed: {type(exc).__name__}",
                correlation_id=resolved_correlation_id,
                feature_id=feature_id,
            )

        # ----- Register correlation with the forge subscriber ------------
        # DDR-028: bounded LRU map; idempotent re-register is overwrite.
        session_id = session.session_id if session is not None else None
        subscriber = _forge_subscriber
        if subscriber is not None:
            try:
                subscriber.register_correlation(
                    resolved_correlation_id,
                    session_id,
                    resolved_adapter,
                    queued_at,
                    feature_id,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "queue_build_register_correlation_failed",
                    extra={
                        "reason": type(exc).__name__,
                        "detail": str(exc),
                        "correlation_id": resolved_correlation_id,
                    },
                )

        # ----- Fire-and-forget routing-history write (DDR-019/DDR-029) ---
        _fire_and_forget_build_queue_trace(
            correlation_id=resolved_correlation_id,
            session_id=session_id,
            timestamp=queued_at,
            feature_id=feature_id,
            adapter=resolved_adapter,
            subject=subject,
            in_flight=_in_flight_or_zero(semaphore),
        )

        # ----- TASK-JNB-002: Fire build_queued notification (AC-010) -----
        # Per AC-010, queue_build fires a build_queued notification immediately
        # after the PubAck/register_correlation block. Per DDR-007, sink
        # failures are WARNING-only and never alter the returned QueueBuildAck.
        # Per AC-011, error paths (above returns) emit nothing to the sink.
        if _notification_sink is not None:
            try:
                # Import locally to avoid top-level dependency on infrastructure
                from jarvis.infrastructure.forge_notifications import ForgeNotification

                build_queued_notification = ForgeNotification(
                    event_type="build_queued",  # type: ignore[arg-type]
                    correlation_id=resolved_correlation_id,
                    feature_id=feature_id,
                    completed_at=queued_at,
                )
                await _notification_sink.notify(build_queued_notification)
            except Exception as exc:
                # DDR-007: sink failures are WARNING-only, never propagate
                logger.warning(
                    "queue_build_notification_sink_error",
                    extra={
                        "reason": type(exc).__name__,
                        "detail": str(exc),
                        "correlation_id": resolved_correlation_id,
                        "feature_id": feature_id,
                    },
                )

        # ----- QueueBuildAck JSON ----------------------------------------
        ack = {
            "feature_id": feature_id,
            "correlation_id": resolved_correlation_id,
            "queued_at": queued_at.isoformat(),
            "publish_target": subject,
            "status": "queued",
        }
        return json.dumps(ack)
    finally:
        if sem_acquired and semaphore is not None:
            semaphore.release()


# ---------------------------------------------------------------------------
# escalate_to_frontier — DDR-014 Layer 1 (TASK-J003-010)
#
# Layer 1 carries the tool body, docstring contract, and config / provider
# branches. Layer 2 (executor attended-only assertion) lands in
# TASK-J003-011 and Layer 3 (tool-registry absence) in TASK-J003-012 — this
# tool intentionally has no runtime context awareness; the surrounding
# layers enforce the constitutional gates.
#
# Per ADR-ARCH-029 (redaction posture) and the AC of TASK-J003-010, the
# instruction body MUST never appear in any log record or returned error
# string. The structured INFO record carries ``instruction_length`` only.
# ---------------------------------------------------------------------------

# Frontier-call session placeholder. Layer 2 (TASK-J003-011) plugs a
# real session resolver via ``_current_session_hook`` below; the placeholder
# remains the value used in the structured log records so the
# ``FrontierEscalationContext.session_id`` constraint stays satisfied without
# leaking caller state into telemetry (ADR-ARCH-029).
_FRONTIER_SESSION_PLACEHOLDER: str = "frontier-call"

# Provider model aliases — closed map keyed by FrontierTarget.
_GEMINI_MODEL: str = "gemini-3.1-pro"
_OPUS_MODEL: str = "claude-opus-4-7"

# Adapter labels surfaced into FrontierEscalationContext.adapter for
# budget-trace bucketing per ADR-ARCH-030.
_GEMINI_ADAPTER: str = "google-genai"
_OPUS_ADAPTER: str = "anthropic"


# ---------------------------------------------------------------------------
# DDR-014 Layer 2 — executor assertion (TASK-J003-011).
#
# Two detection paths run BEFORE any provider SDK call so a rejection never
# triggers outbound HTTP traffic:
#
#   1. Adapter check via ``_current_session_hook`` →
#      ``Session.adapter`` ∈ ``ATTENDED_ADAPTER_IDS``.
#   2. Caller-frame check via ``_async_subagent_frame_hook`` (preferred,
#      ``AsyncSubAgentMiddleware`` metadata) with the session-state
#      ``metadata['currently_in_subagent']`` flag as the F6/Finding-F6
#      fallback per ASSUM-FRONTIER-CALLER-FRAME.
#
# Production wiring lands in ``jarvis.infrastructure.lifecycle.startup`` —
# the lifecycle module assigns these hooks to a ``SessionManager``-backed
# resolver and (when DeepAgents 0.5.3 exposes the metadata) the middleware
# probe. Until either hook is wired, Layer 2 is a no-op so Layer 1 unit
# tests for the tool body keep passing without setup.
# ---------------------------------------------------------------------------

# ADR-ARCH-016 consumer-surface list. Held as a frozenset of adapter-id
# strings rather than ``Adapter`` enum members so duck-typed mocks (and the
# session-state fallback path) compare cleanly against the value reported on
# ``Session.adapter`` (a ``StrEnum`` whose ``str(...)`` is the lower-case
# alias).
ATTENDED_ADAPTER_IDS: frozenset[str] = frozenset({"telegram", "cli", "dashboard", "reachy"})


# Module-level resolver hooks. Defaulting to ``None`` keeps Layer 2 inert
# until ``jarvis.infrastructure.lifecycle.startup`` wires the production
# resolvers; Layer-2 unit tests assign these directly via monkeypatch.
_current_session_hook: Callable[[], Session | None] | None = None
_async_subagent_frame_hook: Callable[[], bool | None] | None = None


def _resolve_current_session() -> Session | None:
    """Resolve the currently-active :class:`Session` via the registered hook.

    Returns ``None`` when no hook is wired or the hook raised — the
    surrounding Layer-2 logic treats both as "no attended session" (which
    causes a rejection) rather than allowing a hook misconfiguration to
    silently bypass the gate.
    """
    hook = _current_session_hook
    if hook is None:
        return None
    try:
        return hook()
    except Exception:
        # Boundary guard — Layer 2 must never raise out of the tool body.
        return None


def _is_async_subagent_frame() -> bool:
    """Return ``True`` if the call is in an :class:`AsyncSubAgent` frame.

    Two-path detection per DDR-014 + Finding F6:

    1. **Middleware metadata** via ``_async_subagent_frame_hook``. The hook
       is expected to return ``True``/``False`` when
       ``AsyncSubAgentMiddleware`` exposes the answer, or ``None`` when the
       metadata is unavailable in the running DeepAgents version
       (ASSUM-FRONTIER-CALLER-FRAME). A raised exception is treated as
       "unable to answer" and the session-state fallback runs.
    2. **Session-state fallback** via the active session's
       ``metadata['currently_in_subagent']`` flag. Used when the middleware
       layer cannot answer — this is the resilience path Finding F6 calls
       out: if one detection path fails the other must still hold.

    Either path returning ``True`` triggers a Layer-2 rejection in
    :func:`_check_attended_only`.
    """
    middleware_hook = _async_subagent_frame_hook
    if middleware_hook is not None:
        try:
            result = middleware_hook()
        except Exception:
            result = None
        # An explicit boolean from the middleware is authoritative — it
        # has direct visibility into the call frame and supersedes the
        # session-state fallback. Only when the metadata is genuinely
        # unavailable (``None`` or raised) does the fallback path run.
        if result is True:
            return True
        if result is False:
            return False

    # Session-state fallback (Finding F6).
    session = _resolve_current_session()
    if session is not None:
        metadata = getattr(session, "metadata", None) or {}
        if metadata.get("currently_in_subagent") is True:
            return True

    return False


def _check_attended_only(
    target: FrontierTarget,
    correlation_id: str,
    instruction_length: int,
    adapter_label: str,
) -> str | None:
    """Layer 2 executor assertion — attended-only / non-subagent gate.

    Returns a structured ``ERROR: attended_only — …`` string when the call
    must be rejected, else ``None``. Both detection paths fire before any
    provider SDK call (AC-004), and every rejection emits exactly one
    structured INFO record with ``outcome="attended_only"`` (AC-007).

    The function is a no-op when neither resolver hook is wired, so Layer 1
    tests that exercise the tool body without a session manager continue to
    reach the provider/config branches.
    """
    if _current_session_hook is None and _async_subagent_frame_hook is None:
        # Layer 2 is dormant — production startup wires the hooks; tests
        # for Layer 1 exercise the body directly.
        return None

    # ---- Path A — adapter check ------------------------------------------
    session = _resolve_current_session()
    if session is None:
        adapter_id = "unknown"
    else:
        adapter_value = getattr(session, "adapter", None)
        adapter_id = str(adapter_value) if adapter_value is not None else "unknown"

    if adapter_id not in ATTENDED_ADAPTER_IDS:
        _emit_frontier_log(
            target,
            correlation_id,
            adapter_label,
            instruction_length,
            "attended_only",
        )
        return (
            "ERROR: attended_only — escalate_to_frontier cannot be invoked "
            f"from {adapter_id} adapter"
        )

    # ---- Path B — caller-frame check -------------------------------------
    # Attended adapter passed; the spoofed-ambient case (attended session
    # with an in-progress async-subagent frame) is the security-critical
    # branch — the frame check OVERRIDES the attended-adapter pass.
    if _is_async_subagent_frame():
        _emit_frontier_log(
            target,
            correlation_id,
            adapter_label,
            instruction_length,
            "attended_only",
        )
        return (
            "ERROR: attended_only — escalate_to_frontier cannot be invoked "
            "from async-subagent frame"
        )

    return None


def _emit_frontier_log(
    target: FrontierTarget,
    correlation_id: str,
    adapter: str,
    instruction_length: int,
    outcome: Literal[
        "success",
        "config_missing",
        "attended_only",
        "provider_unavailable",
        "degraded_empty",
    ],
) -> None:
    """Emit one structured INFO record via :func:`log_frontier_escalation`.

    Centralised so every successful and degraded branch of
    ``escalate_to_frontier`` routes through a single call site — the
    one-log-per-call invariant (AC-008) is therefore enforced by
    construction.
    """
    ctx = FrontierEscalationContext(
        target=target,
        session_id=_FRONTIER_SESSION_PLACEHOLDER,
        correlation_id=correlation_id,
        adapter=adapter,
        instruction_length=instruction_length,
        outcome=outcome,
    )
    log_frontier_escalation(ctx, logger)


def _escalate_gemini(
    instruction: str,
    instruction_length: int,
    correlation_id: str,
) -> str:
    """Gemini branch of ``escalate_to_frontier``.

    Reads ``GOOGLE_API_KEY`` directly (the SDK reads the same env var
    natively, so this aligns with operator expectations) and invokes the
    ``gemini-3.1-pro`` model via :class:`google.genai.Client`. All error
    paths produce a structured string per ADR-ARCH-021.
    """
    target = FrontierTarget.GEMINI_3_1_PRO
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        _emit_frontier_log(
            target,
            correlation_id,
            _GEMINI_ADAPTER,
            instruction_length,
            "config_missing",
        )
        return "ERROR: config_missing — GOOGLE_API_KEY not set"

    try:
        # Lazy import: the SDK is in `[providers]` extras only, and tests
        # patch ``google.genai.Client`` directly. Importing at module
        # scope would couple a Phase-1 import-graph test to the optional
        # extras and surface SDK warnings during unrelated test runs.
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=instruction,
        )
        text = getattr(response, "text", None) or ""
    except Exception as exc:
        # Boundary guard per AC-010: escalate_to_frontier never raises.
        # The ``<short reason>`` is the exception class name — chosen so
        # AC-009 (instruction body never echoed) holds even when the SDK
        # embeds caller input in its error messages.
        _emit_frontier_log(
            target,
            correlation_id,
            _GEMINI_ADAPTER,
            instruction_length,
            "provider_unavailable",
        )
        return f"DEGRADED: provider_unavailable — {type(exc).__name__}"

    if not text:
        _emit_frontier_log(
            target,
            correlation_id,
            _GEMINI_ADAPTER,
            instruction_length,
            "degraded_empty",
        )
        return "DEGRADED: provider_unavailable — empty response"

    _emit_frontier_log(
        target,
        correlation_id,
        _GEMINI_ADAPTER,
        instruction_length,
        "success",
    )
    return text


def _escalate_opus(
    instruction: str,
    instruction_length: int,
    correlation_id: str,
) -> str:
    """Opus branch of ``escalate_to_frontier``.

    Reads ``ANTHROPIC_API_KEY`` directly and invokes
    ``claude-opus-4-7`` via :class:`anthropic.Anthropic`. The Anthropic
    SDK returns ``response.content`` as a list of content blocks; the
    text we surface is the first block's ``.text``. Empty content list
    or empty text both map to the ``degraded_empty`` outcome.
    """
    target = FrontierTarget.OPUS_4_7
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        _emit_frontier_log(
            target,
            correlation_id,
            _OPUS_ADAPTER,
            instruction_length,
            "config_missing",
        )
        return "ERROR: config_missing — ANTHROPIC_API_KEY not set"

    try:
        # Lazy import: keeps the dispatch module's import graph stable
        # for the existing import-graph test, and lets unit tests patch
        # ``anthropic.Anthropic`` without first paying the SDK's import
        # cost.
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=_OPUS_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": instruction}],
        )
        content = getattr(response, "content", None) or []
        text = ""
        if content:
            first = content[0]
            text = getattr(first, "text", None) or ""
    except Exception as exc:
        # Boundary guard per AC-010 — see _escalate_gemini for the
        # rationale on why we use ``type(exc).__name__`` rather than
        # ``str(exc)`` in the DEGRADED string.
        _emit_frontier_log(
            target,
            correlation_id,
            _OPUS_ADAPTER,
            instruction_length,
            "provider_unavailable",
        )
        return f"DEGRADED: provider_unavailable — {type(exc).__name__}"

    if not text:
        _emit_frontier_log(
            target,
            correlation_id,
            _OPUS_ADAPTER,
            instruction_length,
            "degraded_empty",
        )
        return "DEGRADED: provider_unavailable — empty response"

    _emit_frontier_log(
        target,
        correlation_id,
        _OPUS_ADAPTER,
        instruction_length,
        "success",
    )
    return text


@tool(parse_docstring=True)
def escalate_to_frontier(
    instruction: str,
    target: FrontierTarget = FrontierTarget.GEMINI_3_1_PRO,
) -> str:
    """ATTENDED-ONLY — cloud escape hatch. \
Never invoke from ambient, learning, or async-subagent contexts.

    Sends ``instruction`` to a cloud frontier model (Gemini 3.1 Pro by
    default; Opus 4.7 as the alternate target) and returns the model's
    response text as a string. Reserved for the rare case where a user
    has explicitly asked for a frontier-quality answer in an attended
    adapter session. Layers 2 + 3 (TASK-J003-011 / -012) enforce the
    attended-only gate at the executor and tool-registry levels — this
    tool body intentionally trusts that envelope.

    Out-of-enum ``target`` values are rejected at argument coercion by
    ``@tool(parse_docstring=True)`` before this function runs, so no
    provider is contacted on bad input. Per ADR-ARCH-021 the function
    never raises: every error path produces a structured string. Per
    ADR-ARCH-029 the instruction body is never logged or echoed in any
    error / degraded return string — only ``len(instruction)`` is
    recorded as ``instruction_length`` on the structured INFO trace
    emitted via :func:`log_frontier_escalation` with the budget-trace
    tag ``model_alias="cloud-frontier"`` (ADR-ARCH-030).

    Cost is high (cloud frontier models are an order of magnitude more
    expensive than the local fleet); latency is provider-bound.

    Args:
        instruction: The free-form prompt to forward to the cloud
                    frontier provider. Required. Treated as opaque text
                    — no template substitution, no validation, no
                    redaction is performed inside this tool.
        target: Closed enum selecting the cloud frontier provider.
               ``GEMINI_3_1_PRO`` routes through ``google_genai`` to the
               ``gemini-3.1-pro`` model; ``OPUS_4_7`` routes through
               ``anthropic`` to ``claude-opus-4-7``. Default
               ``GEMINI_3_1_PRO``.

    Returns:
        The provider's response text on success, OR a structured error /
        degraded string:

          - ``ERROR: config_missing — GOOGLE_API_KEY not set``
          - ``ERROR: config_missing — ANTHROPIC_API_KEY not set``
          - ``DEGRADED: provider_unavailable — <short reason>``
          - ``DEGRADED: provider_unavailable — empty response``
    """
    correlation_id = new_correlation_id()
    instruction_length = len(instruction) if isinstance(instruction, str) else 0

    # Pick the provider-side adapter tag used in the structured log records.
    # On out-of-enum ``target`` values pydantic coercion already raised, but
    # the gemini label is the safe default for the defensive fallthrough at
    # the end of this function.
    adapter_label = _OPUS_ADAPTER if target is FrontierTarget.OPUS_4_7 else _GEMINI_ADAPTER

    # Layer 2 — executor assertion. Runs before any provider call so that
    # a rejection produces no outbound HTTP attempt (DDR-014, AC-004). The
    # assertion is dormant when no resolver hooks are wired (e.g. Layer 1
    # unit tests of the tool body itself).
    rejection = _check_attended_only(
        target,
        correlation_id,
        instruction_length,
        adapter_label,
    )
    if rejection is not None:
        return rejection

    if target is FrontierTarget.GEMINI_3_1_PRO:
        return _escalate_gemini(instruction, instruction_length, correlation_id)
    if target is FrontierTarget.OPUS_4_7:
        return _escalate_opus(instruction, instruction_length, correlation_id)

    # Defensive fallthrough: pydantic coercion already rejects out-of-enum
    # values before the body runs, but ADR-ARCH-021 forbids raising even
    # in unreachable branches. mypy correctly identifies this as
    # statically unreachable given the closed two-member ``FrontierTarget``
    # — the ignore is intentional and load-bearing if a future DDR adds a
    # third member that isn't yet routed.
    return "ERROR: config_missing — unknown frontier target"  # type: ignore[unreachable]


__all__ = [
    "ATTENDED_ADAPTER_IDS",
    "MAX_REDIRECTS",
    "_async_subagent_frame_hook",
    "_capability_registry",
    "_current_session_hook",
    "_dispatch_semaphore",
    "_forge_subscriber",
    "_jarvis_config",
    "_nats_client",
    "_routing_history_writer",
    "dispatch_by_capability",
    "escalate_to_frontier",
    "queue_build",
]
