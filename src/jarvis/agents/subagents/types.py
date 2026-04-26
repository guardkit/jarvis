"""Subagent-layer types for the Jarvis reasoner subagent.

Defines the closed role-mode enum and the structured input contract for
the ``jarvis-reasoner`` AsyncSubAgent surfaced through DeepAgents'
``start_async_task(name="jarvis-reasoner", input=...)``.

Per DM-subagent-types sections 1-2, DDR-011, and TASK-J003-002 / TASK-J003-003:

- :class:`RoleName` — closed three-member role enum (DDR-011). Adding a
  member is a conscious schema change requiring a DDR.
- :class:`AsyncTaskInput` — input payload for the reasoner subagent.

The :class:`AsyncTaskInput` task-spec deliberately keeps ``role`` as a
plain ``str`` rather than a :class:`RoleName` enum field so that
*unknown* role values flow through to the subagent graph's first node
(which maps them onto the structured ``ERROR: unknown_role — …`` return
value per ADR-ARCH-021 and ASSUM-004) rather than raising
``ValidationError`` at the input boundary. Membership validation against
:class:`RoleName` is therefore the *graph's* responsibility, not this
model's.

This module performs no I/O at import and makes no LLM calls.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["AsyncTaskInput", "RoleName"]


class RoleName(str, Enum):
    """Closed enumeration of role modes for the ``jarvis-reasoner`` subagent.

    Per DDR-011 and design.md §4: membership is closed for v1. Additions
    are non-breaking but require commit-message justification; removals
    or renames require a new DDR. The enum is ``str``-valued so
    :func:`@tool(parse_docstring=True) <langchain_core.tools.tool>`
    argument coercion works with literal strings supplied by the
    reasoning model and ``RoleName.CRITIC.value == "critic"`` round-trips
    cleanly through JSON payloads.

    Default Python enum behaviour applies: ``RoleName("")`` (or any
    non-member string) raises :class:`ValueError`. There is intentionally
    no ``__missing__`` override — the subagent graph catches the raise
    and maps it onto the structured ``unknown_role`` error branch per
    ADR-ARCH-021 and ASSUM-004.
    """

    CRITIC = "critic"
    RESEARCHER = "researcher"
    PLANNER = "planner"


class AsyncTaskInput(BaseModel):
    """Input payload for the ``jarvis-reasoner`` AsyncSubAgent.

    Serialised to the DeepAgents ``AsyncSubAgentMiddleware`` ``input``
    dict at the supervisor → subagent boundary.

    Attributes:
        prompt: Full instruction for the subagent. Must be a non-empty
            string (Pydantic enforces ``min_length=1``).
        role: Role mode selecting the subagent's system prompt. Typed as
            a plain ``str`` here — validation against :class:`RoleName`
            is performed at the subagent graph's first node so unknown
            values reach the ``unknown_role`` error branch instead of
            raising at construction.
        correlation_id: UUID-string from the originating session, or
            ``None`` if the subagent should generate one. Optional at
            the input boundary; always present in internal state.
    """

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1)
    role: str
    correlation_id: str | None = None
