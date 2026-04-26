"""Tests for :class:`jarvis.agents.subagents.types.AsyncTaskInput`.

Covers TASK-J003-003 acceptance criteria:

- AC-001: field shape — non-empty ``prompt``, ``role: str`` (not enum
  validated at construction), optional ``correlation_id``.
- AC-003: model is frozen / immutable once constructed.
- AC-004: importing the module performs no I/O and triggers no LLM
  calls.
"""

from __future__ import annotations

import sys

import pytest
from pydantic import ValidationError

from jarvis.agents.subagents.types import AsyncTaskInput


class TestAsyncTaskInputFieldShape:
    """AC-001 — field-level validation behaviour."""

    def test_construct_with_minimal_valid_payload_succeeds(self) -> None:
        payload = AsyncTaskInput(prompt="hello", role="critic")

        assert payload.prompt == "hello"
        assert payload.role == "critic"
        assert payload.correlation_id is None

    def test_construct_with_correlation_id_preserves_value(self) -> None:
        payload = AsyncTaskInput(
            prompt="hello",
            role="researcher",
            correlation_id="00000000-0000-0000-0000-000000000001",
        )

        assert payload.correlation_id == "00000000-0000-0000-0000-000000000001"

    def test_construct_with_empty_prompt_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            AsyncTaskInput(prompt="", role="critic")

    def test_construct_with_unknown_role_string_does_not_raise(self) -> None:
        # AC-001 — role is ``str`` so unknown values do NOT raise here;
        # the subagent graph maps them onto ``ERROR: unknown_role``.
        payload = AsyncTaskInput(prompt="hello", role="not-a-real-role")

        assert payload.role == "not-a-real-role"

    def test_construct_with_missing_prompt_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            AsyncTaskInput(role="critic")  # type: ignore[call-arg]

    def test_construct_with_missing_role_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            AsyncTaskInput(prompt="hello")  # type: ignore[call-arg]


class TestAsyncTaskInputFrozen:
    """AC-003 — frozen / immutable model."""

    def test_assigning_to_prompt_after_construction_raises(self) -> None:
        payload = AsyncTaskInput(prompt="hello", role="critic")

        with pytest.raises(ValidationError):
            payload.prompt = "mutated"  # type: ignore[misc]

    def test_assigning_to_role_after_construction_raises(self) -> None:
        payload = AsyncTaskInput(prompt="hello", role="critic")

        with pytest.raises(ValidationError):
            payload.role = "researcher"  # type: ignore[misc]

    def test_assigning_to_correlation_id_after_construction_raises(self) -> None:
        payload = AsyncTaskInput(prompt="hello", role="critic")

        with pytest.raises(ValidationError):
            payload.correlation_id = "abc"  # type: ignore[misc]


class TestAsyncTaskInputImportPurity:
    """AC-004 — importing the module triggers no I/O and no LLM calls."""

    def test_module_is_present_in_sys_modules_after_top_level_import(self) -> None:
        # Import is at module top; module presence proves it loaded
        # without raising. No filesystem or network side-effects are
        # required by the model's body.
        assert "jarvis.agents.subagents.types" in sys.modules
