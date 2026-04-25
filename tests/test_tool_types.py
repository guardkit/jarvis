"""Tests for jarvis.tools.types — WebResult, CalendarEvent, DispatchError.

Covers acceptance criteria for TASK-J002-004:
  AC-001: WebResult schema and field constraints.
  AC-002: CalendarEvent schema + end >= start validator.
  AC-003: DispatchError schema + to_tool_string() rendering per
          ADR-ARCH-021.
  AC-004: All three models use ConfigDict(extra="ignore").
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from jarvis.tools.types import CalendarEvent, DispatchError, WebResult


# ---------------------------------------------------------------------------
# AC-001: WebResult
# ---------------------------------------------------------------------------
class TestWebResult:
    """WebResult field constraints."""

    def test_minimal_construction(self) -> None:
        result = WebResult(title="Hello", url="https://example.com")
        assert result.title == "Hello"
        assert result.url == "https://example.com"
        assert result.snippet == ""
        assert result.score == 0.0

    def test_full_construction(self) -> None:
        result = WebResult(
            title="Hello",
            url="https://example.com",
            snippet="An example page",
            score=0.75,
        )
        assert result.snippet == "An example page"
        assert result.score == 0.75

    def test_title_min_length(self) -> None:
        with pytest.raises(ValidationError):
            WebResult(title="", url="https://example.com")

    def test_url_min_length(self) -> None:
        with pytest.raises(ValidationError):
            WebResult(title="Hello", url="")

    def test_score_lower_bound(self) -> None:
        with pytest.raises(ValidationError):
            WebResult(title="Hello", url="https://example.com", score=-0.1)

    def test_score_upper_bound(self) -> None:
        with pytest.raises(ValidationError):
            WebResult(title="Hello", url="https://example.com", score=1.1)

    def test_score_inclusive_bounds(self) -> None:
        WebResult(title="Hello", url="https://example.com", score=0.0)
        WebResult(title="Hello", url="https://example.com", score=1.0)


# ---------------------------------------------------------------------------
# AC-002: CalendarEvent
# ---------------------------------------------------------------------------
class TestCalendarEvent:
    """CalendarEvent schema and end-after-start validator."""

    def _start(self) -> datetime:
        return datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)

    def test_minimal_construction(self) -> None:
        start = self._start()
        end = start + timedelta(hours=1)
        event = CalendarEvent(id="evt-1", title="Standup", start=start, end=end)
        assert event.id == "evt-1"
        assert event.title == "Standup"
        assert event.start == start
        assert event.end == end
        assert event.location is None
        assert event.description is None

    def test_full_construction(self) -> None:
        start = self._start()
        end = start + timedelta(hours=1)
        event = CalendarEvent(
            id="evt-1",
            title="Standup",
            start=start,
            end=end,
            location="Zoom",
            description="Daily sync",
        )
        assert event.location == "Zoom"
        assert event.description == "Daily sync"

    def test_end_equal_to_start_is_allowed(self) -> None:
        start = self._start()
        event = CalendarEvent(id="evt-1", title="Instant", start=start, end=start)
        assert event.start == event.end

    def test_end_before_start_rejected(self) -> None:
        start = self._start()
        end = start - timedelta(seconds=1)
        with pytest.raises(ValidationError):
            CalendarEvent(id="evt-1", title="Bad", start=start, end=end)


# ---------------------------------------------------------------------------
# AC-003: DispatchError
# ---------------------------------------------------------------------------
class TestDispatchError:
    """DispatchError schema and to_tool_string rendering."""

    def test_minimal_construction(self) -> None:
        err = DispatchError(
            category="unresolved",
            detail="No agent matched",
            correlation_id="corr-1",
        )
        assert err.category == "unresolved"
        assert err.detail == "No agent matched"
        assert err.correlation_id == "corr-1"
        assert err.agent_id is None
        assert err.tool_name is None

    def test_invalid_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DispatchError(
                category="not_a_category",  # type: ignore[arg-type]
                detail="x",
                correlation_id="c",
            )

    @pytest.mark.parametrize(
        "category",
        [
            "unresolved",
            "invalid_payload",
            "invalid_timeout",
            "specialist_error",
            "transport_stub",
        ],
    )
    def test_to_tool_string_error_prefix(self, category: str) -> None:
        err = DispatchError(
            category=category,  # type: ignore[arg-type]
            detail="something went wrong",
            correlation_id="corr-1",
        )
        assert err.to_tool_string() == f"ERROR: {category} — something went wrong"

    def test_to_tool_string_timeout_prefix(self) -> None:
        err = DispatchError(
            category="timeout",
            detail="exceeded 30s",
            correlation_id="corr-2",
        )
        assert err.to_tool_string() == "TIMEOUT: timeout — exceeded 30s"

    def test_optional_fields_round_trip(self) -> None:
        err = DispatchError(
            category="specialist_error",
            detail="boom",
            agent_id="architect-agent",
            tool_name="run_architecture_session",
            correlation_id="corr-3",
        )
        assert err.agent_id == "architect-agent"
        assert err.tool_name == "run_architecture_session"


# ---------------------------------------------------------------------------
# AC-004: ConfigDict(extra="ignore") on all three models
# ---------------------------------------------------------------------------
class TestExtraIgnore:
    """All three models tolerate (and ignore) unexpected fields."""

    def test_web_result_extra_ignored(self) -> None:
        result = WebResult(
            title="Hello",
            url="https://example.com",
            unexpected="ignored",  # type: ignore[call-arg]
        )
        assert not hasattr(result, "unexpected")
        assert WebResult.model_config.get("extra") == "ignore"

    def test_calendar_event_extra_ignored(self) -> None:
        start = datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)
        event = CalendarEvent(
            id="evt-1",
            title="Standup",
            start=start,
            end=start,
            unexpected="ignored",  # type: ignore[call-arg]
        )
        assert not hasattr(event, "unexpected")
        assert CalendarEvent.model_config.get("extra") == "ignore"

    def test_dispatch_error_extra_ignored(self) -> None:
        err = DispatchError(
            category="unresolved",
            detail="no match",
            correlation_id="c",
            unexpected="ignored",  # type: ignore[call-arg]
        )
        assert not hasattr(err, "unexpected")
        assert DispatchError.model_config.get("extra") == "ignore"
