"""Tests for TASK-J002-010: ``get_calendar_events`` Phase 2 stub.

Each test class targets a specific acceptance criterion from the task
description. The tests exercise both the public ``StructuredTool`` surface
(``get_calendar_events.invoke({...})``) and the underlying function
(``get_calendar_events.func(...)``) so that the never-raises invariant
(AC-006) holds end-to-end, even on inputs that pydantic would reject at
the schema layer.
"""

from __future__ import annotations

import inspect
import json
import pathlib
import re
import typing

import pytest

from jarvis.tools import general
from jarvis.tools.general import (
    _ALLOWED_WINDOWS,
    CalendarWindow,
    get_calendar_events,
)

# ---------------------------------------------------------------------------
# Module locations used by the docstring byte-for-byte assertion (AC-002).
# ---------------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_CONTRACT_PATH = (
    _REPO_ROOT
    / "docs"
    / "design"
    / "FEAT-JARVIS-002"
    / "contracts"
    / "API-tools.md"
)


# ===========================================================================
# AC-001: src/jarvis/tools/general.py exposes get_calendar_events decorated
# with @tool(parse_docstring=True).
# ===========================================================================


class TestAC001ToolExposed:
    """``get_calendar_events`` is exported from ``jarvis.tools.general``."""

    def test_module_exports_tool(self) -> None:
        """The tool must be reachable via ``jarvis.tools.general``."""
        assert hasattr(general, "get_calendar_events")
        assert "get_calendar_events" in general.__all__

    def test_tool_name_is_get_calendar_events(self) -> None:
        """The langchain ``StructuredTool.name`` matches the function name."""
        assert get_calendar_events.name == "get_calendar_events"

    def test_tool_is_structured_tool(self) -> None:
        """The decorator output is a langchain StructuredTool."""
        from langchain_core.tools import BaseTool

        assert isinstance(get_calendar_events, BaseTool)

    def test_default_window_is_today(self) -> None:
        """Calling with no arguments uses the documented default window."""
        result = get_calendar_events.invoke({})
        assert result == "[]"

    def test_underlying_function_signature_uses_str_returntype(self) -> None:
        """The underlying function returns ``str`` per AC-001."""
        sig = inspect.signature(get_calendar_events.func)
        assert sig.return_annotation in {str, "str"}


# ===========================================================================
# AC-002: Docstring matches API-tools.md §1.3 byte-for-byte; argument type
# annotation is Literal["today","tomorrow","this_week"].
# ===========================================================================


class TestAC002DocstringAndAnnotation:
    """The docstring is the contract surface — it must match byte-for-byte."""

    def test_argument_annotation_is_literal_today_tomorrow_this_week(
        self,
    ) -> None:
        """The ``window`` parameter is annotated with the documented Literal."""
        hints = typing.get_type_hints(get_calendar_events.func)
        window_hint = hints["window"]
        # Literal[...] equality compares by member set.
        assert window_hint == typing.Literal["today", "tomorrow", "this_week"]

    def test_module_exports_calendar_window_literal_alias(self) -> None:
        """A ``Literal["today","tomorrow","this_week"]`` alias is present."""
        assert CalendarWindow == typing.Literal["today", "tomorrow", "this_week"]

    def test_docstring_matches_api_tools_md_section_1_3_byte_for_byte(
        self,
    ) -> None:
        """The docstring text is lifted verbatim from API-tools.md §1.3."""
        contract = _CONTRACT_PATH.read_text(encoding="utf-8")

        # Pull the §1.3 fenced ```python``` block and extract the docstring
        # between the first triple-quoted line and the closing triple-quote.
        match = re.search(
            r"### 1\.3 `get_calendar_events.*?```python\n(.*?)```",
            contract,
            re.DOTALL,
        )
        assert match is not None, "API-tools.md §1.3 block not found"
        block = match.group(1)

        ds_match = re.search(r'"""(.*?)"""', block, re.DOTALL)
        assert ds_match is not None, "Docstring not found inside §1.3 block"
        contract_docstring = ds_match.group(1).strip()

        actual_docstring = (get_calendar_events.func.__doc__ or "").strip()
        assert actual_docstring == contract_docstring


# ===========================================================================
# AC-003: Returns JSON "[]" (Phase 2 stub) for any valid window.
# ===========================================================================


class TestAC003ValidWindowReturnsEmptyJsonList:
    """Valid windows return the empty JSON array ``"[]"``."""

    @pytest.mark.parametrize("window", ["today", "tomorrow", "this_week"])
    def test_valid_window_returns_empty_json_array(self, window: str) -> None:
        """Each documented window yields the empty-list JSON literal."""
        result = get_calendar_events.invoke({"window": window})
        assert result == "[]"

    @pytest.mark.parametrize("window", ["today", "tomorrow", "this_week"])
    def test_func_direct_call_for_valid_windows(self, window: str) -> None:
        """The underlying function (bypassing pydantic) also returns ``"[]"``."""
        assert get_calendar_events.func(window) == "[]"


# ===========================================================================
# AC-004: Rejects invalid window with the structured error string listing
# the allowed windows.
# ===========================================================================


class TestAC004InvalidWindowReturnsStructuredError:
    """Invalid windows are rejected with the documented error string."""

    @pytest.mark.parametrize(
        "bad_window",
        ["next_year", "yesterday", "", "TODAY", "this-week", "today "],
    )
    def test_invalid_window_returns_structured_error(
        self, bad_window: str
    ) -> None:
        """Direct call (bypassing pydantic) returns the structured error."""
        result = get_calendar_events.func(bad_window)

        # ADR-ARCH-021 prefix and category.
        assert result.startswith(
            "ERROR: invalid_window — must be one of today/tomorrow/this_week, got "
        )
        # The bad value is echoed back to aid model-side recovery.
        assert result.endswith(f"got {bad_window}")

    def test_error_string_lists_each_allowed_window(self) -> None:
        """Each allowed window appears verbatim in the error message."""
        result = get_calendar_events.func("nope")
        for window in _ALLOWED_WINDOWS:
            assert window in result


# ===========================================================================
# AC-005: Returned shape is a JSON array of CalendarEvent-shaped dicts.
# ===========================================================================


class TestAC005JsonArrayShape:
    """The stub return value is a JSON array (zero-length, but still array)."""

    @pytest.mark.parametrize("window", ["today", "tomorrow", "this_week"])
    def test_result_parses_as_json_array(self, window: str) -> None:
        """``json.loads`` of the result yields a Python ``list``."""
        result = get_calendar_events.invoke({"window": window})
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert parsed == []

    def test_result_uses_compact_empty_list_literal(self) -> None:
        """Phase 2 stub returns the canonical ``"[]"`` form."""
        assert get_calendar_events.invoke({"window": "today"}) == "[]"


# ===========================================================================
# AC-006: Never raises.
# ===========================================================================


class TestAC006NeverRaises:
    """The underlying function never raises, regardless of input."""

    @pytest.mark.parametrize(
        "bad_input",
        [
            "not_a_window",
            "",
            "TODAY",
            "today\x00",
            "today; rm -rf /",
            " " * 10,
            "𠮷",  # non-ASCII
        ],
    )
    def test_func_returns_string_for_pathological_inputs(
        self, bad_input: str
    ) -> None:
        """Calling ``.func`` on weird input always returns a string."""
        result = get_calendar_events.func(bad_input)
        assert isinstance(result, str)
        assert result.startswith("ERROR: invalid_window —")

    def test_func_does_not_raise_on_non_string_input(self) -> None:
        """Even a non-string sneak-in returns a structured error string."""
        # The annotation is Literal[str], but defensive code still handles
        # the impossible case where someone bypasses typing entirely.
        result = get_calendar_events.func(None)  # type: ignore[arg-type]
        assert isinstance(result, str)
        assert result.startswith("ERROR: invalid_window —")


# ===========================================================================
# AC-007 is checked by the project's lint/format CI step (ruff + mypy);
# this test merely asserts the file is importable cleanly so that any
# syntax / typing regression is caught at unit-test time too.
# ===========================================================================


class TestAC007ModuleImportsCleanly:
    """The module loads without error and exposes the expected symbols."""

    def test_module_imports(self) -> None:
        """``import jarvis.tools.general`` succeeds."""
        import jarvis.tools.general as mod  # noqa: F401 — explicit import

    def test_all_contains_expected_symbols(self) -> None:
        """``__all__`` covers at least the new symbol from this task."""
        assert "get_calendar_events" in general.__all__
