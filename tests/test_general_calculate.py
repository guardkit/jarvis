"""Tests for ``jarvis.tools.general.calculate`` (TASK-J002-011).

Covers the ten acceptance criteria for the safe-arithmetic tool defined in
``docs/design/FEAT-JARVIS-002/contracts/API-tools.md`` §1.4 and DDR-007:

- AC-001: ``calculate(expression: str) -> str`` decorated with
  ``@tool(parse_docstring=True)``.
- AC-002: Docstring matches API-tools.md §1.4 (preserves the description,
  argument schema, and the four documented error-string forms).
- AC-003: Uses ``asteval.Interpreter`` (DDR-007) and rejects ``__import__``,
  ``open``, ``lambda``, function definitions.
- AC-004: Supports the documented operators and functions.
- AC-005: Rejects unsafe tokens with the
  ``ERROR: unsafe_expression — disallowed token: <token>`` form.
- AC-006: Returns ``ERROR: division_by_zero`` for zero-division shapes.
- AC-007: Returns ``ERROR: overflow — result exceeds float range`` for
  expressions that overflow the IEEE-754 float range.
- AC-008: Returns ``ERROR: parse_error — <detail>`` for malformed input.
- AC-009: Pre-processes ``X% of Y`` → ``X/100 * Y`` and returns the result.
- AC-010: Never raises; all internal errors are converted to structured
  strings.
"""

from __future__ import annotations

import math

import pytest
from langchain_core.tools.structured import StructuredTool

from jarvis.tools.general import calculate


def _calc(expression: str) -> str:
    """Invoke the LangChain-wrapped ``calculate`` tool and return the result."""
    result = calculate.invoke({"expression": expression})
    assert isinstance(result, str), (
        f"calculate must return str (ADR-ARCH-021); got {type(result).__name__}"
    )
    return result


# ---------------------------------------------------------------------------
# AC-001 — `@tool(parse_docstring=True)` decoration
# ---------------------------------------------------------------------------
class TestAC001ToolDecoration:
    """``calculate`` is exposed as a LangChain ``StructuredTool`` named
    ``calculate``, with a single ``expression: str`` argument."""

    def test_calculate_is_a_structured_tool(self) -> None:
        assert isinstance(calculate, StructuredTool)

    def test_calculate_tool_name(self) -> None:
        assert calculate.name == "calculate"

    def test_calculate_args_schema_exposes_expression(self) -> None:
        schema = calculate.args_schema.model_json_schema()
        assert "expression" in schema["properties"]
        assert schema["properties"]["expression"]["type"] == "string"
        assert schema["required"] == ["expression"]

    def test_calculate_arg_has_description_from_docstring(self) -> None:
        # ``parse_docstring=True`` lifts the Args block into the schema.
        schema = calculate.args_schema.model_json_schema()
        desc = schema["properties"]["expression"].get("description", "")
        assert "mathematical expression" in desc.lower()
        assert "+ - * / ** %" in desc


# ---------------------------------------------------------------------------
# AC-002 — Docstring matches API-tools.md §1.4
# ---------------------------------------------------------------------------
class TestAC002DocstringContent:
    """The tool description must preserve the canonical phrases from
    API-tools.md §1.4 so the reasoning model receives the same guidance the
    contract documents."""

    def test_description_lead_sentence(self) -> None:
        assert calculate.description.startswith(
            "Evaluate a mathematical expression safely and return the result."
        )

    def test_description_contains_use_guidance(self) -> None:
        desc = calculate.description
        assert "Use this tool for ANY arithmetic" in desc
        assert "You are bad at arithmetic; the tool is not." in desc
        assert (
            "Do NOT use it for" in desc
            and "symbolic manipulation" in desc
        )

    def test_description_contains_cost_latency_callout(self) -> None:
        assert "Near-zero cost, <10ms latency. No network I/O." in calculate.description

    def test_arg_description_lists_operators_and_functions(self) -> None:
        schema = calculate.args_schema.model_json_schema()
        desc = schema["properties"]["expression"]["description"]
        assert "Supported operators: + - * / ** %" in desc
        assert "and parentheses" in desc
        assert (
            "Supported functions: sqrt, log, exp, sin, cos, tan, abs, min, max, round"
            in desc
        )
        assert "Variables are NOT supported" in desc

    def test_underlying_function_docstring_documents_error_forms(self) -> None:
        # The Returns section is preserved on the underlying function so
        # consumers reading the source see the four canonical error strings.
        doc = calculate.func.__doc__ or ""
        assert "ERROR: unsafe_expression — disallowed token: <token>" in doc
        assert "ERROR: parse_error — <detail>" in doc
        assert "ERROR: division_by_zero" in doc
        assert "ERROR: overflow — result exceeds float range" in doc


# ---------------------------------------------------------------------------
# AC-004 — Operators, parentheses, and function allow-list
# ---------------------------------------------------------------------------
class TestAC004OperatorsAndFunctions:
    """All documented operators and functions evaluate to numeric strings."""

    @pytest.mark.parametrize(
        "expr,expected",
        [
            ("1 + 2", "3"),
            ("10 - 4", "6"),
            ("6 * 7", "42"),
            ("12 / 4", "3"),
            ("2 ** 8", "256"),
            ("17 % 5", "2"),
            ("(1 + 2) * (3 + 4)", "21"),
        ],
    )
    def test_operators(self, expr: str, expected: str) -> None:
        assert _calc(expr) == expected

    def test_sqrt(self) -> None:
        out = _calc("sqrt(2)")
        # ``f"{result:g}"`` keeps six significant figures by default.
        assert out.startswith("1.4142")

    def test_log_exp(self) -> None:
        # log(exp(1)) == 1.0 exactly under math semantics.
        out = _calc("log(exp(1))")
        assert float(out) == pytest.approx(1.0, rel=1e-9)

    def test_trig(self) -> None:
        assert float(_calc("sin(0)")) == pytest.approx(0.0, abs=1e-9)
        assert float(_calc("cos(0)")) == pytest.approx(1.0, abs=1e-9)
        assert float(_calc("tan(0)")) == pytest.approx(0.0, abs=1e-9)

    def test_abs_min_max_round(self) -> None:
        assert _calc("abs(-7)") == "7"
        assert _calc("min(3, 1, 2)") == "1"
        assert _calc("max(3, 1, 2)") == "3"
        assert _calc("round(3.7)") == "4"


# ---------------------------------------------------------------------------
# AC-003 + AC-005 — Unsafe tokens are rejected with structured errors
# ---------------------------------------------------------------------------
class TestAC005UnsafeExpression:
    """Pre-filter rejects ``__import__``, ``open``, ``lambda``, function /
    class definitions, and assignment before the expression reaches the
    interpreter (DDR-007 §Decision-1)."""

    @pytest.mark.parametrize(
        "expr,token",
        [
            ("__import__('os').getcwd()", "__import__"),
            ("open('/etc/passwd')", "open"),
            ("lambda x: x", "lambda"),
            ("def f(): return 1", "def"),
            ("class Foo: pass", "class"),
            ("import os", "import"),
            ("x = 1", "="),
            ("(1).__class__", "__"),
        ],
    )
    def test_rejects_unsafe_token(self, expr: str, token: str) -> None:
        out = _calc(expr)
        assert out.startswith("ERROR: unsafe_expression — disallowed token: ")
        assert token in out

    def test_unsafe_error_format_is_single_line(self) -> None:
        out = _calc("__import__('os')")
        assert "\n" not in out

    def test_newline_in_expression_is_rejected(self) -> None:
        out = _calc("1 + 1\nimport os")
        assert out.startswith("ERROR: unsafe_expression — disallowed token: ")


# ---------------------------------------------------------------------------
# AC-006 — Division by zero
# ---------------------------------------------------------------------------
class TestAC006DivisionByZero:
    @pytest.mark.parametrize("expr", ["1/0", "10 / 0", "(2 + 3) / (5 - 5)", "5 % 0"])
    def test_returns_division_by_zero(self, expr: str) -> None:
        assert _calc(expr) == "ERROR: division_by_zero"


# ---------------------------------------------------------------------------
# AC-007 — Overflow (result exceeds the IEEE-754 float range)
# ---------------------------------------------------------------------------
class TestAC007Overflow:
    @pytest.mark.parametrize("expr", ["10.0 ** 500", "exp(1000)"])
    def test_returns_overflow(self, expr: str) -> None:
        assert _calc(expr) == "ERROR: overflow — result exceeds float range"


# ---------------------------------------------------------------------------
# AC-008 — Parse errors
# ---------------------------------------------------------------------------
class TestAC008ParseError:
    @pytest.mark.parametrize("expr", ["1 +", "((1+2)", "sqrt(", "1 + + 2 *"])
    def test_returns_parse_error(self, expr: str) -> None:
        out = _calc(expr)
        assert out.startswith("ERROR: parse_error — ")
        # One-line, non-empty detail.
        assert "\n" not in out
        assert len(out) > len("ERROR: parse_error — ")


# ---------------------------------------------------------------------------
# AC-009 — Percentage shorthand: ``X% of Y`` → ``X/100 * Y``
# ---------------------------------------------------------------------------
class TestAC009PercentageShorthand:
    def test_basic_percentage(self) -> None:
        # 15 / 100 * 847 ≈ 127.05 (with floating-point noise smoothed by :g).
        out = _calc("15% of 847")
        assert float(out) == pytest.approx(15 / 100 * 847, rel=1e-9)

    def test_percentage_returns_clean_string(self) -> None:
        # The default ``f"{x:g}"`` strips trailing zeros / IEEE noise.
        out = _calc("15% of 847")
        assert "e" not in out  # no scientific notation for everyday values
        assert math.isclose(float(out), 127.05, rel_tol=1e-9)

    def test_decimal_percentage(self) -> None:
        # 12.5 / 100 * 80 == 10
        out = _calc("12.5% of 80")
        assert float(out) == pytest.approx(10.0, rel=1e-9)

    def test_modulo_operator_unaffected_by_percent_shorthand(self) -> None:
        # ``X % Y`` (without "of") is the modulo operator and must remain so.
        assert _calc("17 % 5") == "2"


# ---------------------------------------------------------------------------
# AC-010 — Tool boundary never raises; returns structured strings
# ---------------------------------------------------------------------------
class TestAC010NeverRaises:
    @pytest.mark.parametrize(
        "expr",
        [
            "",  # empty
            "   ",  # whitespace-only
            "this is not math at all",  # gibberish
            "1 / 0",
            "10.0 ** 500",
            "lambda x: x",
            "1 +",
            "[1, 2, 3]",
            "{'a': 1}",
            "True",
        ],
    )
    def test_never_raises_for_pathological_inputs(self, expr: str) -> None:
        # The contract is "always returns a string" — any internal raise is a
        # bug. We assert no exception leaks; the value just has to be a str.
        try:
            out = calculate.invoke({"expression": expr})
        except Exception as exc:  # pragma: no cover — failure path
            pytest.fail(f"calculate raised {type(exc).__name__}: {exc}")
        assert isinstance(out, str)
        assert out != ""

    def test_non_string_argument_returns_error_string(self) -> None:
        # The schema rejects non-strings before we get to the body, but the
        # tool wrapper must surface a string in any case the caller sees.
        # ``StructuredTool.invoke`` raises a pydantic ValidationError on the
        # wrong type — that's the schema's job, not the body's. So we only
        # verify the body itself never raises by calling the underlying func.
        out = calculate.func("")  # type: ignore[arg-type]
        assert isinstance(out, str)
        assert out.startswith("ERROR: ")
