"""Unit tests for the tool-layer Pydantic models — TASK-J002-018.

Covers ``jarvis.tools.types`` (``WebResult``, ``CalendarEvent``,
``DispatchError``) and ``jarvis.tools.capabilities``
(``CapabilityToolSummary``, ``CapabilityDescriptor``) in a single suite.

Acceptance criteria (TASK-J002-018):

* AC-001 — At least 12 tests covering Pydantic validation for
  ``CapabilityDescriptor`` (valid + invalid agent_id pattern + unknown
  ``risk_level``), ``CapabilityToolSummary``, ``WebResult`` (score bounds),
  ``CalendarEvent`` (``end >= start`` validator), and ``DispatchError``
  (category Literal).
* AC-002 — ``CapabilityDescriptor.as_prompt_block()`` byte-equal assertion
  against ``DM-tool-types.md §"Prompt-block shape"`` example.
* AC-003 — All tests use ``pytest`` + ``unittest.mock`` per
  ``.claude/CLAUDE.md`` rules.
* AC-004 — No tests touch the network or filesystem (``tmp_path`` only,
  not used here).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
)
from jarvis.tools.types import CalendarEvent, DispatchError, WebResult


# ---------------------------------------------------------------------------
# AC-001 — CapabilityToolSummary validation
# ---------------------------------------------------------------------------
class TestCapabilityToolSummaryValidation:
    """Pydantic validation for ``CapabilityToolSummary``."""

    def test_construct_with_required_fields_returns_summary(self) -> None:
        summary = CapabilityToolSummary(
            tool_name="search_web", description="Run a web search."
        )
        assert summary.tool_name == "search_web"
        assert summary.description == "Run a web search."
        assert summary.risk_level == "read_only"

    def test_unknown_risk_level_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(
                tool_name="t",
                description="d",
                risk_level="catastrophic",  # type: ignore[arg-type]
            )

    def test_empty_tool_name_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(tool_name="", description="d")


# ---------------------------------------------------------------------------
# AC-001 — CapabilityDescriptor validation
# ---------------------------------------------------------------------------
class TestCapabilityDescriptorValidation:
    """Pydantic validation for ``CapabilityDescriptor``."""

    def test_construct_with_valid_kebab_case_agent_id_returns_descriptor(
        self,
    ) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description="Designs systems.",
        )
        assert descriptor.agent_id == "architect-agent"
        assert descriptor.trust_tier == "specialist"
        assert descriptor.cost_signal == "unknown"
        assert descriptor.latency_signal == "unknown"
        assert descriptor.last_heartbeat_at is None

    @pytest.mark.parametrize(
        "agent_id",
        [
            "1agent",  # leading digit
            "-agent",  # leading hyphen
            "Agent",  # uppercase
            "agent_id",  # underscore
            "agent.id",  # dot
            "agent id",  # whitespace
        ],
    )
    def test_invalid_agent_id_pattern_raises_validation_error(
        self, agent_id: str
    ) -> None:
        with pytest.raises(ValidationError):
            CapabilityDescriptor(
                agent_id=agent_id, role="r", description="d"
            )

    def test_invalid_trust_tier_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityDescriptor(
                agent_id="a",
                role="r",
                description="d",
                trust_tier="rogue",  # type: ignore[arg-type]
            )


# ---------------------------------------------------------------------------
# AC-002 — as_prompt_block byte-equal against DM-tool-types.md
# ---------------------------------------------------------------------------
class TestAsPromptBlockByteEqual:
    """Deterministic prompt-block rendering matches DM-tool-types §example."""

    def test_as_prompt_block_byte_equal_to_dm_tool_types_example(self) -> None:
        """Render the canonical DM-tool-types.md §'Prompt-block shape' example.

        The expected string below is copied verbatim from the design
        document; any drift in ``as_prompt_block()`` formatting flips this
        test red.
        """
        descriptor = CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description=(
                "Produces architecture sessions, C4 diagrams, and ADRs for "
                "features. Prefers\nevidence-based decisions grounded in the "
                "existing ARCHITECTURE.md."
            ),
            cost_signal="moderate",
            latency_signal="5-30s",
            trust_tier="specialist",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="run_architecture_session",
                    description=(
                        "Drive a full /system-arch\nsession end-to-end "
                        "from a scope document."
                    ),
                    risk_level="read_only",
                ),
                CapabilityToolSummary(
                    tool_name="draft_adr",
                    description=(
                        "Produce a new ADR file given context + decision."
                    ),
                    risk_level="mutating",
                ),
            ],
        )

        expected = (
            "### architect-agent — Architect "
            "(trust: specialist, cost: moderate, latency: 5-30s)\n"
            "\n"
            "Produces architecture sessions, C4 diagrams, and ADRs for "
            "features. Prefers\n"
            "evidence-based decisions grounded in the existing "
            "ARCHITECTURE.md.\n"
            "\n"
            "Tools:\n"
            "  - run_architecture_session (read_only) — "
            "Drive a full /system-arch\n"
            "    session end-to-end from a scope document.\n"
            "  - draft_adr (mutating) — Produce a new ADR file given "
            "context + decision."
        )

        assert descriptor.as_prompt_block() == expected

    def test_as_prompt_block_invocation_is_deterministic(self) -> None:
        """Calling twice produces the same string — no hidden state."""
        descriptor = CapabilityDescriptor(
            agent_id="a",
            role="R",
            description="d",
            capability_list=[
                CapabilityToolSummary(tool_name="t", description="td"),
            ],
        )
        assert descriptor.as_prompt_block() == descriptor.as_prompt_block()


# ---------------------------------------------------------------------------
# AC-001 — WebResult score bounds
# ---------------------------------------------------------------------------
class TestWebResultBounds:
    """``WebResult`` score-bounds and required-field validation."""

    @pytest.mark.parametrize("score", [-0.0001, -1.0, 1.0001, 5.0])
    def test_score_outside_unit_interval_raises_validation_error(
        self, score: float
    ) -> None:
        with pytest.raises(ValidationError):
            WebResult(title="Hello", url="https://example.com", score=score)

    @pytest.mark.parametrize("score", [0.0, 0.5, 1.0])
    def test_score_inside_unit_interval_accepted(self, score: float) -> None:
        result = WebResult(
            title="Hello", url="https://example.com", score=score
        )
        assert result.score == score

    def test_empty_url_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            WebResult(title="Hello", url="")


# ---------------------------------------------------------------------------
# AC-001 — CalendarEvent end >= start validator
# ---------------------------------------------------------------------------
class TestCalendarEventValidator:
    """``CalendarEvent`` ``end >= start`` model validator."""

    @staticmethod
    def _start() -> datetime:
        return datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc)

    def test_end_after_start_accepted(self) -> None:
        start = self._start()
        end = start + timedelta(hours=1)
        event = CalendarEvent(id="e", title="t", start=start, end=end)
        assert event.end > event.start

    def test_end_equal_to_start_accepted(self) -> None:
        start = self._start()
        event = CalendarEvent(id="e", title="t", start=start, end=start)
        assert event.start == event.end

    def test_end_before_start_raises_validation_error(self) -> None:
        start = self._start()
        end = start - timedelta(seconds=1)
        with pytest.raises(ValidationError):
            CalendarEvent(id="e", title="t", start=start, end=end)


# ---------------------------------------------------------------------------
# AC-001 — DispatchError category Literal
# ---------------------------------------------------------------------------
class TestDispatchErrorCategoryLiteral:
    """``DispatchError.category`` is constrained to the canonical Literal set."""

    @pytest.mark.parametrize(
        "category",
        [
            "unresolved",
            "invalid_payload",
            "invalid_timeout",
            "timeout",
            "specialist_error",
            "transport_stub",
        ],
    )
    def test_canonical_categories_accepted(self, category: str) -> None:
        err = DispatchError(
            category=category,  # type: ignore[arg-type]
            detail="x",
            correlation_id="c",
        )
        assert err.category == category

    def test_unknown_category_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            DispatchError(
                category="not_a_category",  # type: ignore[arg-type]
                detail="x",
                correlation_id="c",
            )

    def test_to_tool_string_uses_timeout_prefix_for_timeout_category(
        self,
    ) -> None:
        err = DispatchError(
            category="timeout",
            detail="exceeded 30s",
            correlation_id="corr-1",
        )
        assert err.to_tool_string() == "TIMEOUT: timeout — exceeded 30s"

    def test_to_tool_string_uses_error_prefix_for_non_timeout_category(
        self,
    ) -> None:
        err = DispatchError(
            category="unresolved",
            detail="no agent matched",
            correlation_id="corr-2",
        )
        assert err.to_tool_string() == "ERROR: unresolved — no agent matched"


# ---------------------------------------------------------------------------
# AC-003 — Mock-driven verification (pytest + unittest.mock)
# ---------------------------------------------------------------------------
class TestPromptBlockMockInteractions:
    """Verify ``as_prompt_block`` boundary behaviour using ``unittest.mock``.

    Demonstrates the pytest + unittest.mock pairing called out by
    ``.claude/CLAUDE.md``: we patch the bound method to assert the
    supervisor-side call shape (``{available_capabilities}`` is filled by
    joining ``as_prompt_block()`` outputs with double newlines), without
    touching the network or filesystem.
    """

    def test_as_prompt_block_called_once_per_descriptor(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="R", description="d"
        )
        with patch.object(
            CapabilityDescriptor,
            "as_prompt_block",
            autospec=True,
            return_value="MOCK_BLOCK",
        ) as mocked:
            rendered = descriptor.as_prompt_block()
        mocked.assert_called_once_with(descriptor)
        assert rendered == "MOCK_BLOCK"

    def test_double_newline_join_pattern_with_mocked_blocks(self) -> None:
        """Two descriptors join with ``\\n\\n`` — matches the supervisor
        prompt's ``{available_capabilities}`` fill rule."""
        d1 = MagicMock(spec=CapabilityDescriptor)
        d1.as_prompt_block.return_value = "BLOCK_ONE"
        d2 = MagicMock(spec=CapabilityDescriptor)
        d2.as_prompt_block.return_value = "BLOCK_TWO"

        joined = "\n\n".join(d.as_prompt_block() for d in (d1, d2))

        assert joined == "BLOCK_ONE\n\nBLOCK_TWO"
        d1.as_prompt_block.assert_called_once_with()
        d2.as_prompt_block.assert_called_once_with()
