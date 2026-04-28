"""Contract tests for the dispatch swap-point seam.

Originally TASK-J002-007 owned this surface. TASK-J004-011 retires the
dispatch-side anchors (``_stub_response_hook``, ``LOG_PREFIX_DISPATCH``,
``StubResponse``) — only the queue-build half of the seam remains until
FEAT-JARVIS-005 retires that too.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from jarvis.tools import dispatch


def _project_root() -> Path:
    """Return the project root (the parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Retired-anchor assertions (TASK-J004-011) — the dispatch swap is done.
# ---------------------------------------------------------------------------
class TestDispatchAnchorsRetired:
    """Phase 2 dispatch anchors are deleted as of TASK-J004-011."""

    def test_log_prefix_dispatch_removed(self) -> None:
        assert not hasattr(dispatch, "LOG_PREFIX_DISPATCH")

    def test_stub_response_hook_removed(self) -> None:
        assert not hasattr(dispatch, "_stub_response_hook")

    def test_stub_response_alias_removed(self) -> None:
        assert not hasattr(dispatch, "StubResponse")

    def test_new_swap_point_attributes_present(self) -> None:
        assert hasattr(dispatch, "_nats_client")
        assert hasattr(dispatch, "_routing_history_writer")
        assert hasattr(dispatch, "_dispatch_semaphore")


# ---------------------------------------------------------------------------
# Queue-build anchor — survives until FEAT-JARVIS-005 retires it.
# ---------------------------------------------------------------------------
class TestQueueBuildAnchor:
    def test_log_prefix_queue_build_value(self) -> None:
        assert dispatch.LOG_PREFIX_QUEUE_BUILD == "JARVIS_QUEUE_BUILD" + "_STUB"

    def test_log_prefix_queue_build_is_string(self) -> None:
        assert isinstance(dispatch.LOG_PREFIX_QUEUE_BUILD, str)


# ---------------------------------------------------------------------------
# Module docstring — calls out the FEAT-JARVIS-004 swap, names the surviving
# queue-build anchor, and does not inline the literal anchor strings.
# ---------------------------------------------------------------------------
class TestModuleDocstring:
    def test_docstring_references_feat_jarvis_004_swap(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "FEAT-JARVIS-004" in doc
        assert "round-trip" in doc.lower()
        assert "NATS" in doc

    def test_docstring_names_remaining_queue_build_anchor(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "LOG_PREFIX_QUEUE_BUILD" in doc

    def test_docstring_does_not_inline_grep_anchor_strings(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "JARVIS_DISPATCH" + "_STUB" not in doc
        assert "JARVIS_QUEUE_BUILD" + "_STUB" not in doc


# ---------------------------------------------------------------------------
# Grep-count invariant for the surviving anchor only.
#
# TASK-J002-021 originally pinned 4 lines (2 constants + 2 logger.info
# usages). After TASK-J004-011 the dispatch half is retired, leaving 2
# anchored lines (queue_build constant + queue_build logger.info usage).
# ---------------------------------------------------------------------------
class TestQueueBuildGrepCount:
    @staticmethod
    def _grep_anchors() -> list[str]:
        src_jarvis = _project_root() / "src" / "jarvis"
        token = "JARVIS_QUEUE_BUILD" + "_STUB"
        result = subprocess.run(
            ["grep", "-rIn", token, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode in (0, 1), result.stderr
        return [ln for ln in result.stdout.splitlines() if ln.strip()]

    def test_dispatch_anchor_no_longer_in_source_tree(self) -> None:
        src_jarvis = _project_root() / "src" / "jarvis"
        token = "JARVIS_DISPATCH" + "_STUB"
        result = subprocess.run(
            ["grep", "-rIn", token, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )
        # grep returncode 1 == no matches.
        if result.returncode == 0:
            pytest.fail("JARVIS_DISPATCH_STUB anchor must be retired — found:\n" + result.stdout)
        assert result.returncode == 1

    def test_queue_build_anchor_count_is_two(self) -> None:
        lines = self._grep_anchors()
        dispatch_lines = [ln for ln in lines if "tools/dispatch.py" in ln]
        # 2 lines: constant definition + logger.info usage in queue_build.
        assert len(dispatch_lines) == 2, (
            "src/jarvis/tools/dispatch.py must contain exactly 2 "
            "JARVIS_QUEUE_BUILD_STUB lines. Found:\n" + "\n".join(dispatch_lines)
        )
