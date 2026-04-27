"""Closed dispatch-layer enums and frontier-escalation telemetry models.

This module is the single source of truth for the routing / escalation
contract surfaced into FEAT-JARVIS-004's ``jarvis_routing_history``
ingest path. Per DDR-011 and design.md §4 + §8 (Frontier escalation
contract), each member is a conscious schema change requiring a DDR.

Per DM-subagent-types §6 and ADR-ARCH-029 (redaction posture):

- :class:`FrontierTarget` — closed two-member enum identifying which
  cloud frontier provider was invoked.
- :class:`FrontierEscalationContext` — frozen Pydantic model carrying
  the structured fields recorded for every frontier escalation. It
  intentionally omits the instruction body — only ``instruction_length``
  is recorded so downstream telemetry cannot leak the prompt.
- :func:`log_frontier_escalation` — the canonical structured-INFO
  emitter. ADR-ARCH-030 (budget tracing) requires a stable
  ``model_alias="cloud-frontier"`` tag on every record.

The module performs **no** I/O at import time and makes **no** LLM
calls — it is a pure types + helper module.
"""

from __future__ import annotations

from enum import StrEnum
from logging import INFO, Logger
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "FrontierEscalationContext",
    "FrontierTarget",
    "log_frontier_escalation",
]


class FrontierTarget(StrEnum):
    """Closed enumeration of supported cloud frontier providers.

    Per DDR-011 and design.md §4: adding a member is a conscious schema
    change that requires a DDR. The enum is ``str``-valued (via
    :class:`enum.StrEnum`, the canonical 3.11+ form for the legacy
    ``(str, Enum)`` mix-in) so
    :func:`@tool(parse_docstring=True) <langchain_core.tools.tool>`
    argument coercion works with literal strings supplied by the
    reasoning model.
    """

    GEMINI_3_1_PRO = "GEMINI_3_1_PRO"
    OPUS_4_7 = "OPUS_4_7"


class FrontierEscalationContext(BaseModel):
    """Structured record of a single frontier escalation attempt.

    Frozen by construction so callers cannot mutate the record after it
    has been emitted to the logging pipeline. Per ADR-ARCH-029 the
    instruction body is **never** stored on this model — only its length
    is captured.

    Attributes:
        target: Which cloud frontier provider was selected for this
            escalation.
        session_id: Active Jarvis session identifier.
        correlation_id: Per-call correlation ID, present even on failure
            so the routing-history ingest path can stitch the record
            back to the originating dispatch.
        adapter: The adapter implementation responsible for invoking the
            target (e.g. provider client name).
        instruction_length: Length, in characters, of the redacted
            instruction body. Constrained to ``>= 0`` so downstream
            histograms cannot record a negative bucket.
        outcome: Closed Literal of escalation outcomes. Adding a member
            is a conscious schema change.
    """

    model_config = ConfigDict(frozen=True)

    target: FrontierTarget
    session_id: str
    correlation_id: str
    adapter: str
    instruction_length: int = Field(ge=0)
    outcome: Literal[
        "success",
        "config_missing",
        "attended_only",
        "provider_unavailable",
        "degraded_empty",
    ]


def log_frontier_escalation(ctx: FrontierEscalationContext, logger: Logger) -> None:
    """Emit one structured INFO record for a frontier escalation.

    Per ADR-ARCH-030 (budget tracing) the record carries the stable
    ``model_alias="cloud-frontier"`` tag so the downstream ingest path
    can bucket frontier spend independently of the local model fleet.

    The record contains exactly the six fields of ``ctx`` plus the
    model-alias tag. The instruction body is **never** included — only
    ``ctx.instruction_length`` (per ADR-ARCH-029).

    Args:
        ctx: The frozen :class:`FrontierEscalationContext` to log.
        logger: The stdlib :class:`logging.Logger` instance the caller
            wants the record routed through. The helper does not create
            its own logger so test suites can inject a mock without
            patching module-level state.
    """
    logger.log(
        INFO,
        "frontier_escalation",
        extra={
            "model_alias": "cloud-frontier",
            "target": ctx.target.value,
            "session_id": ctx.session_id,
            "correlation_id": ctx.correlation_id,
            "adapter": ctx.adapter,
            "instruction_length": ctx.instruction_length,
            "outcome": ctx.outcome,
        },
    )
