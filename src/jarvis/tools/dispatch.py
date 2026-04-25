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
from collections.abc import Callable
from typing import Literal, TypeAlias

from langchain_core.tools import tool
from nats_core import EventType, MessageEnvelope
from nats_core.events import CommandPayload, ResultPayload
from pydantic import ValidationError

from jarvis.tools._correlation import new_correlation_id
from jarvis.tools.capabilities import CapabilityDescriptor

logger = logging.getLogger(__name__)

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
StubResponse: TypeAlias = (
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
            if (
                intent_pattern in descriptor.role
                or intent_pattern in descriptor.description
            ):
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
    timeout_seconds. Moderate cost (~$0.10–$2 per dispatch, specialist-
    dependent); 5–60s typical wall-clock.

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
        return (
            f"ERROR: invalid_timeout — timeout_seconds must be 5..600, "
            f"got {timeout_seconds!r}"
        )
    if timeout_seconds < 5 or timeout_seconds > 600:
        return (
            f"ERROR: invalid_timeout — timeout_seconds must be 5..600, "
            f"got {timeout_seconds}"
        )

    # ----- Validate payload_json is a JSON object literal -------------------
    stripped = payload_json.lstrip() if isinstance(payload_json, str) else ""
    if not stripped.startswith("{"):
        return (
            "ERROR: invalid_payload — payload_json is not a JSON object literal"
        )
    try:
        parsed_args = json.loads(payload_json)
    except (ValueError, TypeError):
        return (
            "ERROR: invalid_payload — payload_json is not a JSON object literal"
        )
    if not isinstance(parsed_args, dict):
        return (
            "ERROR: invalid_payload — payload_json is not a JSON object literal"
        )

    # ----- Resolve agent_id -------------------------------------------------
    agent_id = _resolve_agent_id(
        tool_name, intent_pattern, _capability_registry
    )
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
    topic = f"agents.command.{agent_id}"
    payload_bytes = len(envelope.model_dump_json().encode("utf-8"))
    logger.info(
        "%s tool_name=%s agent_id=%s correlation_id=%s topic=%s payload_bytes=%d",
        LOG_PREFIX_DISPATCH,
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
    except Exception as exc:  # noqa: BLE001 — boundary-guard per AC: never raise
        return (
            f"ERROR: specialist_error — agent_id={agent_id} detail={exc}"
        )

    match response:
        case ("success", ResultPayload() as result):
            return result.model_dump_json()
        case ("timeout",):
            return (
                f"TIMEOUT: agent_id={agent_id} tool_name={tool_name} "
                f"timeout_seconds={timeout_seconds}"
            )
        case ("specialist_error", str() as reason):
            return (
                f"ERROR: specialist_error — agent_id={agent_id} "
                f"detail={reason}"
            )
        case _:
            return (
                f"ERROR: specialist_error — agent_id={agent_id} "
                f"detail=invalid stub response: {response!r}"
            )


__all__ = [
    "LOG_PREFIX_DISPATCH",
    "LOG_PREFIX_QUEUE_BUILD",
    "StubResponse",
    "_stub_response_hook",
    "_capability_registry",
    "dispatch_by_capability",
]
