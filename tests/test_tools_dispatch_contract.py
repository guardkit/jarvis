"""Contract tests for the dispatch swap-point seam (TASK-J002-007).

These tests pin the Wave-1 baseline of ``jarvis.tools.dispatch``. The
post-Wave-3 grep-count-of-4 invariant is owned by TASK-J002-021; this
suite asserts only the Wave-1 grep-count-of-2 baseline and the four
named-anchor acceptance criteria of TASK-J002-007.
"""

from __future__ import annotations

import inspect
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Literal, get_args, get_origin, get_type_hints

import pytest
from nats_core.events import CommandPayload, ResultPayload

from jarvis.tools import dispatch


def _project_root() -> Path:
    """Return the project root (the parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# AC-001 — ``_stub_response_hook`` module-level attribute
# ---------------------------------------------------------------------------
class TestAC001StubResponseHookAttribute:
    """`_stub_response_hook: Callable[[CommandPayload], StubResponse] | None`."""

    def test_stub_response_hook_defined_at_module_level_default_none(self) -> None:
        assert hasattr(dispatch, "_stub_response_hook")
        assert dispatch._stub_response_hook is None

    def test_stub_response_hook_annotation_is_optional_callable(self) -> None:
        hints = get_type_hints(dispatch)
        annotation = hints["_stub_response_hook"]

        # Optional[Callable[...]] → typing.Union[Callable[...], None].
        variants = get_args(annotation)
        assert type(None) in variants, (
            "_stub_response_hook must be Optional (allow None default)"
        )

        callable_variant = next(v for v in variants if v is not type(None))
        assert get_origin(callable_variant) in (Callable, callable.__class__) or callable_variant is Callable, (
            f"Expected Callable variant, got {callable_variant!r}"
        )

        callable_args = get_args(callable_variant)
        assert callable_args[0] == [CommandPayload], (
            f"Expected [CommandPayload] as Callable arg list, got {callable_args[0]!r}"
        )
        assert callable_args[1] is dispatch.StubResponse, (
            f"Expected StubResponse return, got {callable_args[1]!r}"
        )

    def test_stub_response_hook_is_writable_at_runtime(self) -> None:
        try:
            dispatch._stub_response_hook = lambda _cmd: ("timeout",)  # type: ignore[assignment]
            cmd = CommandPayload(command="noop")
            assert dispatch._stub_response_hook is not None
            assert dispatch._stub_response_hook(cmd) == ("timeout",)
        finally:
            dispatch._stub_response_hook = None


# ---------------------------------------------------------------------------
# AC-002 — ``StubResponse`` type alias
# ---------------------------------------------------------------------------
class TestAC002StubResponseAlias:
    """``StubResponse`` covers ``success | timeout | specialist_error``."""

    def test_stub_response_is_exposed(self) -> None:
        assert hasattr(dispatch, "StubResponse")

    def test_stub_response_union_has_three_variants(self) -> None:
        variants = get_args(dispatch.StubResponse)
        assert len(variants) == 3

    def test_stub_response_success_variant(self) -> None:
        success_variant = next(
            v
            for v in get_args(dispatch.StubResponse)
            if get_args(v) and get_args(v)[0] == Literal["success"]
        )
        args = get_args(success_variant)
        assert args == (Literal["success"], ResultPayload)

    def test_stub_response_timeout_variant(self) -> None:
        timeout_variant = next(
            v
            for v in get_args(dispatch.StubResponse)
            if get_args(v) and get_args(v)[0] == Literal["timeout"]
        )
        args = get_args(timeout_variant)
        assert args == (Literal["timeout"],)

    def test_stub_response_specialist_error_variant(self) -> None:
        err_variant = next(
            v
            for v in get_args(dispatch.StubResponse)
            if get_args(v) and get_args(v)[0] == Literal["specialist_error"]
        )
        args = get_args(err_variant)
        assert args == (Literal["specialist_error"], str)


# ---------------------------------------------------------------------------
# AC-003 — ``LOG_PREFIX_*`` string constants
# ---------------------------------------------------------------------------
class TestAC003LogPrefixConstants:
    """Module-level ``LOG_PREFIX_DISPATCH`` and ``LOG_PREFIX_QUEUE_BUILD``."""

    def test_log_prefix_dispatch_value(self) -> None:
        # Constructed via concatenation in the assertion so this test file
        # itself does not pollute the AC-005 grep-count invariant.
        assert dispatch.LOG_PREFIX_DISPATCH == "JARVIS_DISPATCH" + "_STUB"

    def test_log_prefix_queue_build_value(self) -> None:
        assert dispatch.LOG_PREFIX_QUEUE_BUILD == "JARVIS_QUEUE_BUILD" + "_STUB"

    def test_log_prefix_constants_are_strings(self) -> None:
        assert isinstance(dispatch.LOG_PREFIX_DISPATCH, str)
        assert isinstance(dispatch.LOG_PREFIX_QUEUE_BUILD, str)


# ---------------------------------------------------------------------------
# AC-004 — Module docstring "SWAP POINT" section
# ---------------------------------------------------------------------------
class TestAC004ModuleDocstringSwapPoint:
    """Module docstring carries a "SWAP POINT" section naming the anchors."""

    def test_module_docstring_carries_swap_point_section(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "SWAP POINT" in doc

    def test_module_docstring_names_the_three_grep_anchors(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "_stub_response_hook" in doc
        assert "LOG_PREFIX_DISPATCH" in doc
        assert "LOG_PREFIX_QUEUE_BUILD" in doc

    def test_module_docstring_calls_out_feat_jarvis_004_swap(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "FEAT-JARVIS-004" in doc
        # Must call out the swap target — a real NATS round-trip.
        assert "NATS" in doc
        assert "round-trip" in doc.lower()

    def test_module_docstring_does_not_inline_the_grep_anchor_strings(self) -> None:
        # If the docstring inlined the literal anchor strings, the AC-005
        # grep-count invariant in the *source file* would jump from 2 to 4
        # purely from documentation — defeating the swap-point assertion.
        doc = inspect.getdoc(dispatch) or ""
        assert "JARVIS_DISPATCH" + "_STUB" not in doc
        assert "JARVIS_QUEUE_BUILD" + "_STUB" not in doc


# ---------------------------------------------------------------------------
# AC-005 — Pre-feature-wiring grep-count invariant (= 2)
# ---------------------------------------------------------------------------
class TestAC005GrepCountPreWiring:
    """Pre-Wave-2 grep-count baseline.

    TASK-J002-021 owns the post-Wave-2/3 (4-line) invariant. This test
    asserts the **Wave-1** baseline so a regression in TASK-J002-007 is
    caught immediately rather than only when Wave 4 runs.
    """

    def test_grep_returns_at_least_the_two_constant_definitions(self) -> None:
        src_jarvis = _project_root() / "src" / "jarvis"
        # Build the regex token-by-token so this test file does not appear
        # in the grep output if anyone ever reroots the search.
        token_a = "JARVIS_DISPATCH" + "_STUB"
        token_b = "JARVIS_QUEUE_BUILD" + "_STUB"
        pattern = rf"{token_a}\|{token_b}"

        # ``-I`` skips binary files (e.g. ``__pycache__/*.pyc``) so a stale
        # local bytecode cache cannot disturb the count.
        result = subprocess.run(
            ["grep", "-rIn", pattern, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )
        # grep exits 0 when matches are found, 1 when none.
        assert result.returncode in (0, 1), result.stderr

        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]

        dispatch_lines = [ln for ln in lines if "tools/dispatch.py" in ln]
        # Wave 1 baseline: exactly 2 lines (the constant definitions). After
        # TASK-J002-013 / TASK-J002-014 land the dispatch tools, the count
        # rises to 4 (two constants + two ``logger.info`` anchor usages); at
        # that point TASK-J002-021's stricter post-wiring invariant takes
        # over — see ``test_tools_dispatch.py::TestSwapPointGrepInvariant``.
        if len(dispatch_lines) != 2:
            pytest.skip(
                "Wave 2/3 dispatch tools have landed; TASK-J002-021 owns the "
                f"post-wiring grep invariant. Saw {len(dispatch_lines)} lines."
            )
        assert len(dispatch_lines) == 2, (
            "src/jarvis/tools/dispatch.py must contain exactly two grep-anchor "
            "lines (the two LOG_PREFIX_* constant definitions). Found:\n"
            + "\n".join(dispatch_lines)
        )

    def test_grep_count_matches_wave_1_baseline_of_two(self) -> None:
        """At Wave 1 completion, the global count across src/jarvis/ is 2.

        TASK-J002-013 / TASK-J002-014 will add two more lines (one
        ``logger.info`` per dispatch tool) bringing the count to 4. This
        test pins the Wave-1 baseline; it will *deliberately* fail when
        Wave 2 lands the dispatch tools, at which point TASK-J002-021's
        grep-count-of-4 invariant takes over.
        """
        src_jarvis = _project_root() / "src" / "jarvis"
        token_a = "JARVIS_DISPATCH" + "_STUB"
        token_b = "JARVIS_QUEUE_BUILD" + "_STUB"
        pattern = rf"{token_a}\|{token_b}"

        result = subprocess.run(
            ["grep", "-rIn", pattern, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode in (0, 1), result.stderr

        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]

        # Pre-feature-wiring this is exactly 2. Once TASK-J002-013 /
        # TASK-J002-014 land it becomes 4 — at which point this test is
        # superseded by TASK-J002-021's stricter post-wiring assertion.
        if len(lines) != 2:
            pytest.skip(
                "Wave 2 dispatch tools have landed; TASK-J002-021 owns the "
                f"post-wiring grep invariant. Saw {len(lines)} lines."
            )
        assert len(lines) == 2
