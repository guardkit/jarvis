"""Contract tests for the dispatch swap-point seam.

Originally TASK-J002-007 owned this surface. TASK-J004-011 retired the
dispatch-side anchors (``_stub_response_hook``, ``LOG_PREFIX_DISPATCH``,
``StubResponse``); TASK-J005-005 retires the queue_build half
(``LOG_PREFIX_QUEUE_BUILD`` + the matching ``logger.info`` line) by
swapping the stub for a real ``js.publish(...)`` round-trip.
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
# Retired-anchor assertions (TASK-J004-011 + TASK-J005-005) — both swaps done.
# ---------------------------------------------------------------------------
class TestDispatchAnchorsRetired:
    """Phase 2 dispatch + queue_build anchors are deleted as of TASK-J005-005."""

    def test_log_prefix_dispatch_removed(self) -> None:
        assert not hasattr(dispatch, "LOG_PREFIX_DISPATCH")

    def test_stub_response_hook_removed(self) -> None:
        assert not hasattr(dispatch, "_stub_response_hook")

    def test_stub_response_alias_removed(self) -> None:
        assert not hasattr(dispatch, "StubResponse")

    def test_log_prefix_queue_build_removed(self) -> None:
        # TASK-J005-005: real JetStream publish — anchor is retired.
        assert not hasattr(dispatch, "LOG_PREFIX_QUEUE_BUILD")

    def test_new_swap_point_attributes_present(self) -> None:
        assert hasattr(dispatch, "_nats_client")
        assert hasattr(dispatch, "_routing_history_writer")
        assert hasattr(dispatch, "_dispatch_semaphore")
        assert hasattr(dispatch, "_forge_subscriber")
        assert hasattr(dispatch, "_jarvis_config")


# ---------------------------------------------------------------------------
# Module docstring — calls out the FEAT-JARVIS-004 + FEAT-JARVIS-005 swaps
# and does not inline the literal anchor strings.
# ---------------------------------------------------------------------------
class TestModuleDocstring:
    def test_docstring_references_feat_jarvis_004_swap(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "FEAT-JARVIS-004" in doc
        assert "round-trip" in doc.lower()
        assert "NATS" in doc

    def test_docstring_references_feat_jarvis_005_swap(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "FEAT-JARVIS-005" in doc
        assert "JetStream" in doc

    def test_docstring_does_not_inline_grep_anchor_strings(self) -> None:
        doc = inspect.getdoc(dispatch) or ""
        assert "JARVIS_DISPATCH" + "_STUB" not in doc
        assert "JARVIS_QUEUE_BUILD" + "_STUB" not in doc


# ---------------------------------------------------------------------------
# Both anchors are now retired from the source tree.
# ---------------------------------------------------------------------------
class TestAnchorsRetiredInSource:
    @staticmethod
    def _grep(token: str) -> subprocess.CompletedProcess[str]:
        src_jarvis = _project_root() / "src" / "jarvis"
        return subprocess.run(
            ["grep", "-rIn", token, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_dispatch_anchor_no_longer_in_source_tree(self) -> None:
        token = "JARVIS_DISPATCH" + "_STUB"
        result = self._grep(token)
        if result.returncode == 0:
            pytest.fail("JARVIS_DISPATCH_STUB anchor must be retired — found:\n" + result.stdout)
        assert result.returncode == 1

    def test_queue_build_anchor_no_longer_in_source_tree(self) -> None:
        token = "JARVIS_QUEUE_BUILD" + "_STUB"
        result = self._grep(token)
        if result.returncode == 0:
            pytest.fail("JARVIS_QUEUE_BUILD_STUB anchor must be retired — found:\n" + result.stdout)
        assert result.returncode == 1
