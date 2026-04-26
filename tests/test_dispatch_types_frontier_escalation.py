"""Unit tests for ``FrontierEscalationContext`` — TASK-J003-004.

Covers ``jarvis.tools.dispatch_types``:

* AC-001 — ``FrontierEscalationContext`` exposes the six required fields
  with the closed ``outcome`` Literal and ``instruction_length >= 0``.
* AC-002 — Model is frozen (``ConfigDict(frozen=True)``); mutating any
  field raises ``ValidationError``.
* AC-003 — No instruction body field — the model schema contains exactly
  the six declared fields and nothing called ``instruction``,
  ``instruction_body``, ``body``, or ``prompt``.
* AC-004 — ``log_frontier_escalation`` emits one INFO record carrying
  ``model_alias="cloud-frontier"`` and all six context fields, and the
  instruction body is never present in the record.
* AC-005 — Importing the module triggers no I/O and no LLM construction.
"""

from __future__ import annotations

import importlib
import logging
from typing import get_args
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from jarvis.tools.dispatch_types import (
    FrontierEscalationContext,
    FrontierTarget,
    log_frontier_escalation,
)


# ---------------------------------------------------------------------------
# AC-001 — Field schema
# ---------------------------------------------------------------------------
class TestFrontierEscalationContextSchema:
    """Field-level validation of ``FrontierEscalationContext``."""

    def _kwargs(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "target": FrontierTarget.GEMINI_3_1_PRO,
            "session_id": "sess-1",
            "correlation_id": "corr-1",
            "adapter": "anthropic-cloud",
            "instruction_length": 42,
            "outcome": "success",
        }
        base.update(overrides)
        return base

    def test_construct_with_required_fields_returns_context(self) -> None:
        ctx = FrontierEscalationContext(**self._kwargs())
        assert ctx.target is FrontierTarget.GEMINI_3_1_PRO
        assert ctx.session_id == "sess-1"
        assert ctx.correlation_id == "corr-1"
        assert ctx.adapter == "anthropic-cloud"
        assert ctx.instruction_length == 42
        assert ctx.outcome == "success"

    @pytest.mark.parametrize(
        "outcome",
        [
            "success",
            "config_missing",
            "attended_only",
            "provider_unavailable",
            "degraded_empty",
        ],
    )
    def test_canonical_outcomes_accepted(self, outcome: str) -> None:
        ctx = FrontierEscalationContext(
            **self._kwargs(outcome=outcome)  # type: ignore[arg-type]
        )
        assert ctx.outcome == outcome

    def test_unknown_outcome_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            FrontierEscalationContext(
                **self._kwargs(outcome="not_a_known_outcome")  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("length", [0, 1, 100, 100_000])
    def test_non_negative_instruction_length_accepted(self, length: int) -> None:
        ctx = FrontierEscalationContext(**self._kwargs(instruction_length=length))
        assert ctx.instruction_length == length

    @pytest.mark.parametrize("length", [-1, -100, -1_000_000])
    def test_negative_instruction_length_raises_validation_error(self, length: int) -> None:
        with pytest.raises(ValidationError):
            FrontierEscalationContext(**self._kwargs(instruction_length=length))

    def test_target_must_be_frontier_target_member(self) -> None:
        with pytest.raises(ValidationError):
            FrontierEscalationContext(
                **self._kwargs(target="some-unknown-target")  # type: ignore[arg-type]
            )

    def test_target_accepts_string_value_form(self) -> None:
        """Strings matching enum values coerce to enum members."""
        ctx = FrontierEscalationContext(
            **self._kwargs(target="OPUS_4_7")  # type: ignore[arg-type]
        )
        assert ctx.target is FrontierTarget.OPUS_4_7


# ---------------------------------------------------------------------------
# AC-002 — Model frozen
# ---------------------------------------------------------------------------
class TestFrontierEscalationContextFrozen:
    """``ConfigDict(frozen=True)`` — mutation raises."""

    def _ctx(self) -> FrontierEscalationContext:
        return FrontierEscalationContext(
            target=FrontierTarget.OPUS_4_7,
            session_id="sess-x",
            correlation_id="corr-x",
            adapter="adapter-x",
            instruction_length=1,
            outcome="success",
        )

    def test_model_config_marks_model_as_frozen(self) -> None:
        assert FrontierEscalationContext.model_config.get("frozen") is True

    def test_assigning_to_field_raises_validation_error(self) -> None:
        ctx = self._ctx()
        with pytest.raises(ValidationError):
            ctx.session_id = "different"  # type: ignore[misc]

    def test_assigning_to_outcome_raises_validation_error(self) -> None:
        ctx = self._ctx()
        with pytest.raises(ValidationError):
            ctx.outcome = "config_missing"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-003 — No instruction-body field
# ---------------------------------------------------------------------------
class TestNoInstructionBodyField:
    """Redaction posture — instruction body must never appear on the model."""

    EXPECTED_FIELDS: frozenset[str] = frozenset(
        {
            "target",
            "session_id",
            "correlation_id",
            "adapter",
            "instruction_length",
            "outcome",
        }
    )

    BANNED_FIELDS: frozenset[str] = frozenset(
        {"instruction", "instruction_body", "body", "prompt", "text"}
    )

    def test_model_fields_match_expected_six(self) -> None:
        actual = set(FrontierEscalationContext.model_fields.keys())
        assert actual == self.EXPECTED_FIELDS

    def test_no_banned_field_is_present(self) -> None:
        actual = set(FrontierEscalationContext.model_fields.keys())
        assert actual.isdisjoint(self.BANNED_FIELDS)

    def test_outcome_literal_has_exactly_five_canonical_members(self) -> None:
        outcome_field = FrontierEscalationContext.model_fields["outcome"]
        members = set(get_args(outcome_field.annotation))
        assert members == {
            "success",
            "config_missing",
            "attended_only",
            "provider_unavailable",
            "degraded_empty",
        }


# ---------------------------------------------------------------------------
# AC-004 — log_frontier_escalation emits structured INFO
# ---------------------------------------------------------------------------
class TestLogFrontierEscalation:
    """``log_frontier_escalation`` shape and redaction guarantees."""

    def _ctx(self, **overrides: object) -> FrontierEscalationContext:
        kwargs: dict[str, object] = {
            "target": FrontierTarget.GEMINI_3_1_PRO,
            "session_id": "sess-1",
            "correlation_id": "corr-1",
            "adapter": "google-cloud",
            "instruction_length": 256,
            "outcome": "success",
        }
        kwargs.update(overrides)
        return FrontierEscalationContext(**kwargs)

    def test_emits_one_info_record_via_logger_log(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_frontier_escalation(self._ctx(), logger)
        logger.log.assert_called_once()
        args, _ = logger.log.call_args
        assert args[0] == logging.INFO

    def test_record_carries_model_alias_cloud_frontier_tag(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_frontier_escalation(self._ctx(), logger)
        _, kwargs = logger.log.call_args
        extra = kwargs["extra"]
        assert extra["model_alias"] == "cloud-frontier"

    def test_record_carries_all_six_context_fields(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        ctx = self._ctx(
            outcome="degraded_empty",
            instruction_length=99,
            adapter="gemini-cloud",
            correlation_id="corr-zzz",
            session_id="sess-zzz",
            target=FrontierTarget.OPUS_4_7,
        )
        log_frontier_escalation(ctx, logger)
        _, kwargs = logger.log.call_args
        extra = kwargs["extra"]
        assert extra["target"] == "OPUS_4_7"
        assert extra["session_id"] == "sess-zzz"
        assert extra["correlation_id"] == "corr-zzz"
        assert extra["adapter"] == "gemini-cloud"
        assert extra["instruction_length"] == 99
        assert extra["outcome"] == "degraded_empty"

    @pytest.mark.parametrize(
        "banned_key",
        ["instruction", "instruction_body", "body", "prompt", "text"],
    )
    def test_record_never_carries_instruction_body_keys(self, banned_key: str) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_frontier_escalation(self._ctx(), logger)
        _, kwargs = logger.log.call_args
        extra = kwargs["extra"]
        assert banned_key not in extra

    def test_record_event_name_is_frontier_escalation(self) -> None:
        logger = MagicMock(spec=logging.Logger)
        log_frontier_escalation(self._ctx(), logger)
        args, _ = logger.log.call_args
        assert args[1] == "frontier_escalation"


# ---------------------------------------------------------------------------
# AC-005 — No I/O at import; no LLM calls
# ---------------------------------------------------------------------------
class TestImportPurity:
    """Module is a pure types + helper module."""

    def test_reimport_makes_no_filesystem_or_network_call(self) -> None:
        with (
            patch("builtins.open") as open_mock,
            patch("socket.socket") as socket_mock,
        ):
            importlib.reload(importlib.import_module("jarvis.tools.dispatch_types"))
        open_mock.assert_not_called()
        socket_mock.assert_not_called()

    def test_module_exposes_only_documented_public_surface(self) -> None:
        import jarvis.tools.dispatch_types as mod

        assert set(mod.__all__) == {
            "FrontierTarget",
            "FrontierEscalationContext",
            "log_frontier_escalation",
        }
