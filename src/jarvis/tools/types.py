"""Tool-layer Pydantic models for the jarvis tools package.

Defines the structured types surfaced by Jarvis tools and the internal
``DispatchError`` sentinel rendered into ADR-ARCH-021-compliant error
strings at the tool boundary.

Per DM-tool-types and FEAT-JARVIS-002:

- :class:`WebResult` — single web-search result returned by ``search_web``.
- :class:`CalendarEvent` — single calendar event returned by
  ``get_calendar_events``.
- :class:`DispatchError` — internal structured representation of a dispatch
  failure. Tools convert it into ``"ERROR: <category> — <detail>"`` (or
  ``"TIMEOUT: ..."`` for the ``timeout`` category) per ADR-ARCH-021.

All models set ``ConfigDict(extra="ignore")`` for forward compatibility
with evolving manifest payloads, and validate at construction per the
fleet-wide D22 / ADR-ARCH-021 boundary rule.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CalendarEvent",
    "DispatchError",
    "WebResult",
]


class WebResult(BaseModel):
    """A single web-search result surfaced by ``search_web``.

    Attributes:
        title: Page title from the search result.
        url: Fully-qualified URL.
        snippet: Short extract or description from the search provider.
        score: Relevance score (0.0–1.0) if the provider supplies one;
            0.0 otherwise.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    snippet: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)


class CalendarEvent(BaseModel):
    """A single calendar event surfaced by ``get_calendar_events``.

    Phase 2 only constructs these in tests — the real provider lands in
    v1.5.

    Attributes:
        id: Stable event identifier from the source provider.
        title: Event title.
        start: Event start time (UTC).
        end: Event end time (UTC). Must be ``>= start``.
        location: Optional physical / virtual location string.
        description: Optional free-text body.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _end_must_not_precede_start(self) -> CalendarEvent:
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self


class DispatchError(BaseModel):
    """Internal structured representation of a dispatch failure.

    Tools convert this into a single-line error string at the tool
    boundary per ADR-ARCH-021 — never raised across the supervisor's
    reasoning loop.

    Attributes:
        category: One of ``unresolved``, ``invalid_payload``,
            ``invalid_timeout``, ``timeout``, ``specialist_error``, or
            ``transport_stub``.
        detail: Human-readable context.
        agent_id: Resolved agent if known; ``None`` if resolution failed.
        tool_name: Requested ``tool_name`` if set.
        correlation_id: Correlation ID assigned even on failure so the
            event remains traceable.
    """

    model_config = ConfigDict(extra="ignore")

    category: Literal[
        "unresolved",
        "invalid_payload",
        "invalid_timeout",
        "timeout",
        "specialist_error",
        "transport_stub",
    ]
    detail: str
    agent_id: str | None = None
    tool_name: str | None = None
    correlation_id: str

    def to_tool_string(self) -> str:
        """Render the ADR-ARCH-021-compliant single-line error string.

        Timeouts use the ``TIMEOUT:`` prefix; all other categories use
        ``ERROR:``. The em-dash separator is intentional and matches the
        prompt-facing convention in ADR-ARCH-021.
        """
        prefix = "TIMEOUT" if self.category == "timeout" else "ERROR"
        return f"{prefix}: {self.category} — {self.detail}"
