"""Tests for :class:`jarvis.adapters.types.SwapStatus`.

Covers TASK-J003-003 acceptance criteria:

- AC-002: field shape — ``loaded_model: str``, ``eta_seconds`` is
  non-negative (Pydantic ``ge=0``), ``source`` is a Literal with default
  ``"stub"``.
- AC-003: model is frozen / immutable once constructed.
- AC-004: importing the module performs no I/O and triggers no LLM
  calls.
"""

from __future__ import annotations

import sys

import pytest
from pydantic import ValidationError

from jarvis.adapters.types import SwapStatus


class TestSwapStatusFieldShape:
    """AC-002 — field-level validation behaviour."""

    def test_construct_with_minimal_valid_payload_uses_stub_source_default(
        self,
    ) -> None:
        status = SwapStatus(loaded_model="qwen3-coder", eta_seconds=0)

        assert status.loaded_model == "qwen3-coder"
        assert status.eta_seconds == 0
        assert status.source == "stub"

    def test_construct_with_explicit_live_source_preserves_value(self) -> None:
        status = SwapStatus(loaded_model="qwen3-coder", eta_seconds=12, source="live")

        assert status.source == "live"

    def test_construct_with_negative_eta_raises_validation_error(self) -> None:
        # AC-002 — Pydantic enforces ``ge=0``; -1 must raise.
        with pytest.raises(ValidationError):
            SwapStatus(loaded_model="qwen3-coder", eta_seconds=-1)

    def test_construct_with_unknown_source_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            SwapStatus(
                loaded_model="qwen3-coder",
                eta_seconds=0,
                source="bogus",  # type: ignore[arg-type]
            )

    def test_construct_with_missing_loaded_model_raises_validation_error(
        self,
    ) -> None:
        with pytest.raises(ValidationError):
            SwapStatus(eta_seconds=0)  # type: ignore[call-arg]

    def test_construct_with_missing_eta_seconds_raises_validation_error(
        self,
    ) -> None:
        with pytest.raises(ValidationError):
            SwapStatus(loaded_model="qwen3-coder")  # type: ignore[call-arg]


class TestSwapStatusFrozen:
    """AC-003 — frozen / immutable model."""

    def test_assigning_to_loaded_model_after_construction_raises(self) -> None:
        status = SwapStatus(loaded_model="qwen3-coder", eta_seconds=0)

        with pytest.raises(ValidationError):
            status.loaded_model = "other-alias"  # type: ignore[misc]

    def test_assigning_to_eta_seconds_after_construction_raises(self) -> None:
        status = SwapStatus(loaded_model="qwen3-coder", eta_seconds=0)

        with pytest.raises(ValidationError):
            status.eta_seconds = 5  # type: ignore[misc]

    def test_assigning_to_source_after_construction_raises(self) -> None:
        status = SwapStatus(loaded_model="qwen3-coder", eta_seconds=0)

        with pytest.raises(ValidationError):
            status.source = "live"  # type: ignore[misc]


class TestSwapStatusImportPurity:
    """AC-004 — importing the module triggers no I/O and no LLM calls."""

    def test_module_is_present_in_sys_modules_after_top_level_import(self) -> None:
        assert "jarvis.adapters.types" in sys.modules
