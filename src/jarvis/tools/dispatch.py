"""Dispatch tool primitives — capability-driven dispatch and build queueing.

This module hosts the two dispatch tools (``dispatch_by_capability`` and
``queue_build``) that connect Jarvis to the NATS event bus. In Phase 2
(FEAT-JARVIS-002) the real publish call is **stubbed**: the dispatch tools
construct real ``nats_core`` envelopes (``CommandPayload`` /
``BuildQueuedPayload`` / ``MessageEnvelope``) and then ``logger.info`` the
envelope contents instead of invoking ``nats.request(...)`` /
``js.publish(...)``. Phase 3 (FEAT-JARVIS-004 and FEAT-JARVIS-005) will
replace those log lines with real NATS round-trips without touching tool
docstrings or return shapes.

SWAP POINT
==========

DDR-009 names this module as the **single seam** through which Phase 3
features replace the stub transport with real NATS round-trips. The seam
has three named anchors that downstream features grep for and replace
verbatim:

1. ``_stub_response_hook`` — a module-level ``Callable`` attribute that
   test fixtures write to in order to simulate ``success`` / ``timeout`` /
   ``specialist_error`` round-trip outcomes. **FEAT-JARVIS-004 replaces
   ``_stub_response_hook`` with a real NATS request/reply round-trip**
   (``await nats.request(...)`` on the ``agents.command.{agent_id}``
   subject), removing the indirection entirely.

2. ``LOG_PREFIX_DISPATCH`` — string constant whose value is the grep
   anchor used by every ``logger.info`` line emitted from
   ``dispatch_by_capability``. FEAT-JARVIS-004 replaces those log calls
   with ``await nats.request(...)``.

3. ``LOG_PREFIX_QUEUE_BUILD`` — string constant whose value is the grep
   anchor used by every ``logger.info`` line emitted from ``queue_build``.
   FEAT-JARVIS-005 replaces those log calls with
   ``await js.publish(...)`` on the ``pipeline.build-queued.{x}`` subject.

Grep invariant (asserted by TASK-J002-021)
------------------------------------------
A grep for the values of ``LOG_PREFIX_DISPATCH`` and
``LOG_PREFIX_QUEUE_BUILD`` rooted at ``src/jarvis/`` returns exactly **two**
lines pre-feature wiring (the two constant definitions in this module) and
exactly **four** lines once TASK-J002-013 and TASK-J002-014 land (the two
constant definitions + one ``logger.info`` usage in each of the two
dispatch tools). Drift in this count signals an unauthorised second swap
point and fails CI.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, TypeAlias

from langchain_core.tools import tool
from nats_core import EventType, MessageEnvelope, Topics
from nats_core.events import BuildQueuedPayload, CommandPayload, ResultPayload
from pydantic import ValidationError

from jarvis.tools._correlation import new_correlation_id
from jarvis.tools.capabilities import CapabilityDescriptor
from jarvis.tools.dispatch_types import (
    FrontierEscalationContext,
    FrontierTarget,
    log_frontier_escalation,
)

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
# SWAP POINT — log prefixes (see module docstring).
#
# These two string constants are the DDR-009 grep anchors. Every
# ``logger.info`` call emitted from a dispatch tool MUST use one of these
# constants as the leading literal — never a hard-coded string — so that
# the grep-count invariant (TASK-J002-021) holds across rebases.
# ---------------------------------------------------------------------------
LOG_PREFIX_DISPATCH: str = "JARVIS_DISPATCH_STUB"
LOG_PREFIX_QUEUE_BUILD: str = "JARVIS_QUEUE_BUILD_STUB"


# ---------------------------------------------------------------------------
# SWAP POINT — stub response shape.
#
# ``StubResponse`` is the typed contract returned by ``_stub_response_hook``
# under the Phase 2 stub transport. The three variants are encoded as a
# tagged-tuple union so consumers can pattern-match on the leading literal:
#
#     match hook(command):
#         case ("success", result):    ...
#         case ("timeout",):           ...
#         case ("specialist_error", reason): ...
#
# Phase 3 (FEAT-JARVIS-004) removes the hook entirely; this alias is the
# stub-only contract and disappears with the swap.
# ---------------------------------------------------------------------------
# NOTE: Retain ``TypeAlias`` (PEP 613) form rather than the ``type`` keyword
# (PEP 695). The TASK-J002-007 swap-point contract tests call
# ``typing.get_args(dispatch.StubResponse)`` and require the result to expose
# the three Union variants directly. ``type`` keyword aliases produce a
# ``TypeAliasType`` whose variants are only accessible via ``__value__``,
# which would silently break those tests.
StubResponse: TypeAlias = (  # noqa: UP040 — see preceding comment.
    tuple[Literal["success"], ResultPayload]
    | tuple[Literal["timeout"]]
    | tuple[Literal["specialist_error"], str]
)


# ---------------------------------------------------------------------------
# SWAP POINT — stub response hook (see module docstring).
#
# Default ``None`` means "use the canned ``("success", ResultPayload(...))``
# fallback inside ``dispatch_by_capability``". Test fixtures (and only test
# fixtures) write a callable here to simulate timeouts and specialist
# errors.
#
# FEAT-JARVIS-004 replaces this attribute with a real NATS request/reply
# round-trip and deletes the alias.
# ---------------------------------------------------------------------------
_stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None


# ---------------------------------------------------------------------------
# Capability registry binding.
#
# ``assemble_tool_list`` (TASK-J002-015) snapshots a ``list[CapabilityDescriptor]``
# into this module-level attribute at startup, providing the resolution
# catalogue for ``dispatch_by_capability``. The default is an empty list
# so a bare import of this module yields a tool that returns the
# ``ERROR: unresolved`` form for every dispatch — never raises.
#
# Snapshot isolation (ASSUM-006): assemble_tool_list MUST assign a fresh
# ``list(...)`` copy here, not the operator's mutable registry reference.
# ---------------------------------------------------------------------------
_capability_registry: list[CapabilityDescriptor] = []


def _resolve_agent_id(
    tool_name: str,
    intent_pattern: str | None,
    registry: list[CapabilityDescriptor],
) -> str | None:
    """Resolve ``tool_name`` (and optional ``intent_pattern``) to an agent_id.

    Resolution order — AC-003 of TASK-J002-013:

    1. **Exact match**: first descriptor whose ``capability_list`` contains a
       :class:`CapabilityToolSummary` with ``tool_name`` equal to the
       requested name. Iterates descriptors in lexicographic ``agent_id``
       order so ties are deterministic.
    2. **Intent fallback**: if ``intent_pattern`` is non-empty and no exact
       match was found, return the lexicographically-first descriptor whose
       ``role`` or ``description`` contains ``intent_pattern`` as a
       substring (case-sensitive — patterns are operator-curated tokens).
    3. ``None`` if no rule resolves.

    Args:
        tool_name: Requested ToolCapability name.
        intent_pattern: Optional intent-pattern fallback token.
        registry: Snapshot of capability descriptors.

    Returns:
        ``agent_id`` of the resolved specialist or ``None``.
    """
    sorted_descriptors = sorted(registry, key=lambda d: d.agent_id)

    for descriptor in sorted_descriptors:
        for cap in descriptor.capability_list:
            if cap.tool_name == tool_name:
                return descriptor.agent_id

    if intent_pattern:
        for descriptor in sorted_descriptors:
            if intent_pattern in descriptor.role or intent_pattern in descriptor.description:
                return descriptor.agent_id

    return None


@tool(parse_docstring=True)
def dispatch_by_capability(
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

    In Phase 2 the transport is stubbed: the tool builds a real CommandPayload
    per nats-core, logs it, and returns a canned ResultPayload JSON for tests.
    FEAT-JARVIS-004 replaces the stub with real NATS round-trips without
    changing this docstring.

    Cost depends on the resolved specialist; latency is capped by
    timeout_seconds. Moderate cost (~$0.10-$2 per dispatch, specialist-
    dependent); 5-60s typical wall-clock.

    Args:
        tool_name: The ToolCapability.name to invoke (e.g.
                   ``run_architecture_session``). Required.
        payload_json: JSON string matching the tool's parameters schema as
                     declared in its ToolCapability.parameters. Must be a JSON
                     object literal (starts with ``{``). The tool does NOT
                     validate your payload against the schema in Phase 2 — the
                     specialist will.
        intent_pattern: Optional intent pattern (e.g. ``architecture.generate``)
                       used only when no exact tool match is found.
        timeout_seconds: How long to wait for the specialist's reply, between
                        5 and 600. Default 60. Timeout returns a structured
                        TIMEOUT error; it does NOT cancel the specialist — the
                        result may still appear in NATS after timeout
                        (Phase 3+).

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
          - ``DEGRADED: transport_stub — (Phase 2 stub, real NATS arrives in FEAT-JARVIS-004)``
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

    # ----- Resolve agent_id -------------------------------------------------
    agent_id = _resolve_agent_id(tool_name, intent_pattern, _capability_registry)
    if agent_id is None:
        return (
            f"ERROR: unresolved — no capability matches "
            f"tool_name={tool_name} intent_pattern={intent_pattern}"
        )

    # ----- Build real nats-core payload + envelope --------------------------
    try:
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
    except ValidationError as exc:
        return f"ERROR: validation — {exc.errors()[0].get('msg', str(exc))}"
    except (TypeError, ValueError) as exc:
        return f"ERROR: validation — {exc}"

    # ----- Emit the single grep-anchor log line -----------------------------
    # The leading literal in the format string is intentionally the anchor
    # value (not the symbol) so grep-driven swap workflows in FEAT-JARVIS-004
    # and the TASK-J002-021 invariant test see exactly 4 lines in this file.
    # The constant/value equivalence is pinned by test_tools_dispatch_contract.
    topic = f"agents.command.{agent_id}"
    payload_bytes = len(envelope.model_dump_json().encode("utf-8"))
    logger.info(
        "JARVIS_DISPATCH_STUB tool_name=%s agent_id=%s correlation_id=%s topic=%s payload_bytes=%d",
        tool_name,
        agent_id,
        correlation_id,
        topic,
        payload_bytes,
    )

    # ----- Stub response hook dispatch --------------------------------------
    hook = _stub_response_hook
    if hook is None:
        canned = ResultPayload(
            command=tool_name,
            result={"stub": True, "tool_name": tool_name},
            correlation_id=correlation_id,
            success=True,
        )
        return canned.model_dump_json()

    try:
        response = hook(command)
    except Exception as exc:
        # Boundary-guard per AC-013: dispatch_by_capability never raises.
        return f"ERROR: specialist_error — agent_id={agent_id} detail={exc}"

    match response:
        case ("success", ResultPayload() as result):
            return result.model_dump_json()
        case ("timeout",):
            return (
                f"TIMEOUT: agent_id={agent_id} tool_name={tool_name} "
                f"timeout_seconds={timeout_seconds}"
            )
        case ("specialist_error", str() as reason):
            return f"ERROR: specialist_error — agent_id={agent_id} detail={reason}"
        case _:
            return (
                f"ERROR: specialist_error — agent_id={agent_id} "
                f"detail=invalid stub response: {response!r}"
            )


@tool(parse_docstring=True)
def queue_build(
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

    In Phase 2 the transport is stubbed: the tool builds a real
    BuildQueuedPayload per nats-core, logs it, and returns a canned ACK.
    FEAT-JARVIS-005 replaces the stub with a real
    pipeline.build-queued.{feature_id} JetStream publish without changing this
    docstring.

    Fire-and-forget. Near-zero publish latency when real; Forge may take hours
    to complete the build — you will receive pipeline.* progress events via
    notifications in FEAT-JARVIS-005. Do not await completion.

    Args:
        feature_id: FEAT-XXX identifier matching ``^FEAT-[A-Z0-9]{3,12}$``.
        feature_yaml_path: Path to the feature YAML spec, relative to the
                           repo root (e.g. ``features/feat-jarvis-002/....yaml``).
        repo: GitHub org/repo, e.g. ``guardkit/jarvis`` or ``appmilla/forge``.
              Must match ``^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$``.
        branch: Base branch to branch from. Default ``main``.
        originating_adapter: Which Jarvis adapter the human used. One of
                            ``terminal``, ``voice-reachy``, ``telegram``,
                            ``slack``, ``dashboard``, ``cli-wrapper``.
                            Default ``terminal`` (CLI). ``triggered_by`` is
                            always set to ``jarvis`` by this tool.
        correlation_id: Stable ID for tracing. Auto-generated if omitted.
        parent_request_id: The Jarvis dispatch message ID that spawned this
                          build, for progress-event correlation. Optional.

    Returns:
        JSON string of the QueueBuildAck on success:
          ``{"feature_id": str, "correlation_id": str,
             "queued_at": ISO8601,
             "publish_target": "pipeline.build-queued.{feature_id}",
             "status": "queued"}``
        OR a structured error:
          - ``ERROR: invalid_feature_id — must match FEAT-XXX pattern, got <value>``
          - ``ERROR: invalid_repo — must be org/name format, got <value>``
          - ``ERROR: invalid_adapter — <value> not in allowed list``
          - ``ERROR: validation — <pydantic detail>``
          - ``DEGRADED: transport_stub — (Phase 2 stub, real publish arrives in FEAT-JARVIS-005)``
    """
    # ----- Validate feature_id ---------------------------------------------
    if not isinstance(feature_id, str) or not _FEATURE_ID_PATTERN.match(feature_id):
        return f"ERROR: invalid_feature_id — must match FEAT-XXX pattern, got {feature_id}"

    # ----- Validate repo ----------------------------------------------------
    if not isinstance(repo, str) or not _REPO_PATTERN.match(repo):
        return f"ERROR: invalid_repo — must be org/name format, got {repo}"

    # ----- Validate originating_adapter ------------------------------------
    if originating_adapter not in _ALLOWED_ADAPTERS:
        return f"ERROR: invalid_adapter — {originating_adapter} not in allowed list"

    # ----- Build real nats-core payload + envelope ------------------------
    resolved_correlation_id = correlation_id or new_correlation_id()
    requested_at = _now_utc()
    queued_at = requested_at  # Phase 2: stub publishes immediately.

    try:
        payload = BuildQueuedPayload(
            feature_id=feature_id,
            repo=repo,
            branch=branch,
            feature_yaml_path=feature_yaml_path,
            triggered_by="jarvis",
            originating_adapter=originating_adapter,  # type: ignore[arg-type]
            correlation_id=resolved_correlation_id,
            parent_request_id=parent_request_id,
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
        return f"ERROR: validation — {exc.errors()[0].get('msg', str(exc))}"
    except (TypeError, ValueError) as exc:
        return f"ERROR: validation — {exc}"

    # ----- Subject from canonical Topics template -------------------------
    subject = Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)
    payload_bytes = len(envelope.model_dump_json().encode("utf-8"))

    # ----- SWAP POINT — exactly one logger.info per call ------------------
    #
    # FEAT-JARVIS-005 replaces this single line with:
    #   await js.publish(
    #       subject=Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id),
    #       payload=envelope.model_dump_json().encode(),
    #   )
    # Tool docstring and return shape stay identical. The leading literal is
    # the anchor value so the TASK-J002-021 grep invariant pins this line.
    logger.info(
        "JARVIS_QUEUE_BUILD_STUB feature_id=%s repo=%s correlation_id=%s topic=%s payload_bytes=%d",
        feature_id,
        repo,
        resolved_correlation_id,
        subject,
        payload_bytes,
    )

    # ----- QueueBuildAck JSON ---------------------------------------------
    ack = {
        "feature_id": feature_id,
        "correlation_id": resolved_correlation_id,
        "queued_at": queued_at.isoformat(),
        "publish_target": subject,
        "status": "queued",
    }
    return json.dumps(ack)


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

# Frontier-call session placeholder. Layer 2 (TASK-J003-011) will plug a
# real session-id resolver into the executor wrapper; Layer 1 records a
# stable placeholder so the FrontierEscalationContext field constraint
# (`session_id: str`) is satisfied without leaking caller state.
_FRONTIER_SESSION_PLACEHOLDER: str = "frontier-call"

# Provider model aliases — closed map keyed by FrontierTarget.
_GEMINI_MODEL: str = "gemini-3.1-pro"
_OPUS_MODEL: str = "claude-opus-4-7"

# Adapter labels surfaced into FrontierEscalationContext.adapter for
# budget-trace bucketing per ADR-ARCH-030.
_GEMINI_ADAPTER: str = "google-genai"
_OPUS_ADAPTER: str = "anthropic"


def _emit_frontier_log(
    target: FrontierTarget,
    correlation_id: str,
    adapter: str,
    instruction_length: int,
    outcome: Literal[
        "success",
        "config_missing",
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

    if target is FrontierTarget.GEMINI_3_1_PRO:
        return _escalate_gemini(instruction, instruction_length, correlation_id)
    if target is FrontierTarget.OPUS_4_7:
        return _escalate_opus(instruction, instruction_length, correlation_id)

    # Defensive fallthrough: pydantic coercion already rejects out-of-enum
    # values before the body runs, but ADR-ARCH-021 forbids raising even
    # in unreachable branches.
    return "ERROR: config_missing — unknown frontier target"


__all__ = [
    "LOG_PREFIX_DISPATCH",
    "LOG_PREFIX_QUEUE_BUILD",
    "StubResponse",
    "_capability_registry",
    "_stub_response_hook",
    "dispatch_by_capability",
    "escalate_to_frontier",
    "queue_build",
]
