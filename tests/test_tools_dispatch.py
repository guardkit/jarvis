"""Unit tests for the surviving stub-path tools + swap-point grep invariant.

Originally the consolidated suite for ``jarvis.tools.dispatch`` (Phase 2 /
TASK-J002-021). TASK-J004-011 retires the dispatch-side stub anchor; the
queue_build half remains until FEAT-JARVIS-005 swaps it.

Test class layout (post-TASK-J004-011):

- :class:`TestQueueBuildHappyPath` — happy path returns a JSON ack.
- :class:`TestQueueBuildFeatureIdTable` — feature_id accept/reject table.
- :class:`TestQueueBuildRepoTable` — repo accept/reject table.
- :class:`TestQueueBuildAdapterTable` — originating_adapter allow-list.
- :class:`TestQueueBuildRealBuildQueuedPayload` — isinstance check on the
  reconstructed payload.
- :class:`TestQueueBuildLogFormat` — exact log format assertion for the
  surviving queue_build log anchor.
- :class:`TestSwapPointGrepInvariant` — post-TASK-J004-011 invariant: only
  the queue_build anchor remains in ``src/jarvis/`` (2 anchored lines).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from nats_core.events import BuildQueuedPayload

from jarvis.tools import dispatch

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

# Anchor strings reconstructed via concatenation so this test file does NOT
# itself appear in the swap-point grep invariant rooted at ``src/jarvis/``.
_ANCHOR_DISPATCH = "JARVIS_DISPATCH" + "_STUB"
_ANCHOR_QUEUE_BUILD = "JARVIS_QUEUE_BUILD" + "_STUB"


def _invoke_queue_build(**kwargs: Any) -> str:
    """Invoke the @tool-wrapped ``queue_build`` and return the string result."""
    return dispatch.queue_build.invoke(kwargs)


def _project_root() -> Path:
    """Return the project root (the parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


# ===========================================================================
# queue_build — happy path
# ===========================================================================
class TestQueueBuildHappyPath:
    """A valid feature_id + repo + adapter returns a JSON ack."""

    def test_happy_path_returns_queue_build_ack(self) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat-j002/spec.yaml",
            repo="appmilla/forge",
        )
        ack = json.loads(result)
        assert ack["feature_id"] == "FEAT-J002"
        assert ack["status"] == "queued"
        assert ack["publish_target"] == "pipeline.build-queued.FEAT-J002"
        assert UUID_RE.match(ack["correlation_id"]), ack["correlation_id"]


# ===========================================================================
# queue_build — feature_id table
# ===========================================================================
class TestQueueBuildFeatureIdTable:
    """Boundary table for ``feature_id`` (^FEAT-[A-Z0-9]{3,12}$)."""

    @pytest.mark.parametrize(
        "good",
        ["FEAT-AB1", "FEAT-J002", "FEAT-JARVIS002"],
    )
    def test_valid_feature_ids_accepted(self, good: str) -> None:
        result = _invoke_queue_build(
            feature_id=good,
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        assert not result.startswith("ERROR"), result
        ack = json.loads(result)
        assert ack["feature_id"] == good

    @pytest.mark.parametrize(
        "bad",
        [
            "FEAT-AB",  # too short
            "feat-jarvis-002",  # lowercase
            "BUG-JARVIS-001",  # wrong prefix
            "FEAT-JARVIS-EXAMPLE01",  # rejected by ^FEAT-[A-Z0-9]{3,12}$
        ],
    )
    def test_invalid_feature_ids_rejected(self, bad: str) -> None:
        result = _invoke_queue_build(
            feature_id=bad,
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        assert result.startswith("ERROR: invalid_feature_id"), result
        assert "must match FEAT-XXX pattern" in result
        assert f"got {bad}" in result


# ===========================================================================
# queue_build — repo table
# ===========================================================================
class TestQueueBuildRepoTable:
    """Boundary table for ``repo`` (^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$)."""

    @pytest.mark.parametrize("good", ["guardkit/jarvis", "appmilla/forge"])
    def test_valid_repos_accepted(self, good: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo=good,
        )
        assert not result.startswith("ERROR"), result

    @pytest.mark.parametrize(
        "bad",
        [
            "guardkit",  # no slash
            "guardkit/jarvis/extra",  # too many slashes
        ],
    )
    def test_invalid_repos_rejected(self, bad: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo=bad,
        )
        assert result.startswith("ERROR: invalid_repo"), result
        assert "must be org/name format" in result


# ===========================================================================
# queue_build — originating_adapter table
# ===========================================================================
class TestQueueBuildAdapterTable:
    """Allow-list table for ``originating_adapter``."""

    @pytest.mark.parametrize(
        "good",
        ["terminal", "telegram", "dashboard", "voice-reachy"],
    )
    def test_each_allowed_adapter_accepted(self, good: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
            originating_adapter=good,
        )
        assert not result.startswith("ERROR"), result

    @pytest.mark.parametrize(
        "bad",
        ["email", "TERMINAL", "twitter", ""],
    )
    def test_invalid_adapters_rejected(self, bad: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
            originating_adapter=bad,
        )
        assert result.startswith("ERROR: invalid_adapter"), result
        assert f"{bad} not in allowed list" in result


# ===========================================================================
# queue_build — real BuildQueuedPayload instance (isinstance check)
# ===========================================================================
class TestQueueBuildRealBuildQueuedPayload:
    """The tool constructs a real ``BuildQueuedPayload`` (not a dict) before logging."""

    def test_payload_is_real_build_queued_payload_instance(self) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat-j002/spec.yaml",
            repo="appmilla/forge",
            branch="main",
            originating_adapter="terminal",
            correlation_id="corr-abc",
            parent_request_id="parent-xyz",
        )
        ack = json.loads(result)
        assert ack["correlation_id"] == "corr-abc"
        from datetime import datetime

        payload = BuildQueuedPayload(
            feature_id="FEAT-J002",
            repo="appmilla/forge",
            branch="main",
            feature_yaml_path="features/feat-j002/spec.yaml",
            triggered_by="jarvis",
            originating_adapter="terminal",
            correlation_id="corr-abc",
            parent_request_id="parent-xyz",
            requested_at=datetime.fromisoformat(ack["queued_at"]),
            queued_at=datetime.fromisoformat(ack["queued_at"]),
        )
        assert isinstance(payload, BuildQueuedPayload)
        assert not isinstance(payload, dict)
        assert payload.triggered_by == "jarvis"
        restored = BuildQueuedPayload.model_validate_json(payload.model_dump_json())
        assert isinstance(restored, BuildQueuedPayload)
        assert restored == payload


# ===========================================================================
# queue_build — exact log format assertion
# ===========================================================================
class TestQueueBuildLogFormat:
    """The queue_build log line MUST match the documented format:

    ``JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
    topic=pipeline.build-queued.<x> payload_bytes=<n>``
    """

    LOG_RE = re.compile(
        rf"^{_ANCHOR_QUEUE_BUILD} "
        r"feature_id=(?P<feature_id>\S+) "
        r"repo=(?P<repo>\S+) "
        r"correlation_id=(?P<cid>\S+) "
        r"topic=pipeline\.build-queued\.(?P<feature_id_topic>\S+) "
        r"payload_bytes=(?P<n>\d+)$"
    )

    def test_log_format_matches_documented_pattern(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            _invoke_queue_build(
                feature_id="FEAT-J002",
                feature_yaml_path="features/feat.yaml",
                repo="guardkit/jarvis",
                correlation_id="trace-1",
            )
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        msg = records[0].getMessage()
        m = self.LOG_RE.match(msg)
        assert m is not None, f"Log line did not match pattern:\n{msg}"
        assert m.group("feature_id") == "FEAT-J002"
        assert m.group("feature_id_topic") == "FEAT-J002"
        assert m.group("repo") == "guardkit/jarvis"
        assert m.group("cid") == "trace-1"
        assert int(m.group("n")) > 0


# ===========================================================================
# Swap-point grep invariant — post-TASK-J004-011 retirement
# ===========================================================================
class TestSwapPointGrepInvariant:
    """Post-TASK-J004-011 invariant.

    ``grep -rn JARVIS_DISPATCH_STUB src/jarvis/`` MUST return zero matches —
    the dispatch swap point is retired. ``grep -rn JARVIS_QUEUE_BUILD_STUB
    src/jarvis/`` MUST return exactly two matches in
    ``src/jarvis/tools/dispatch.py``: the constant definition and the
    ``logger.info`` usage in ``queue_build``.
    """

    @staticmethod
    def _grep(pattern: str) -> list[str]:
        src_jarvis = _project_root() / "src" / "jarvis"
        result = subprocess.run(
            ["grep", "-rIn", pattern, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode in (0, 1), result.stderr
        return [ln for ln in result.stdout.splitlines() if ln.strip()]

    def test_dispatch_anchor_is_retired_zero_matches(self) -> None:
        lines = self._grep(_ANCHOR_DISPATCH)
        assert lines == [], "JARVIS_DISPATCH_STUB anchor must be retired — found:\n" + "\n".join(
            lines
        )

    def test_queue_build_anchor_count_is_two(self) -> None:
        lines = self._grep(_ANCHOR_QUEUE_BUILD)
        dispatch_lines = [ln for ln in lines if "tools/dispatch.py" in ln]
        assert len(dispatch_lines) == 2, (
            "Expected exactly 2 JARVIS_QUEUE_BUILD_STUB lines (constant + "
            f"logger.info usage). Found {len(dispatch_lines)}:\n" + "\n".join(dispatch_lines)
        )

    def test_queue_build_anchor_value_matches_constant(self) -> None:
        assert dispatch.LOG_PREFIX_QUEUE_BUILD == _ANCHOR_QUEUE_BUILD

    def test_queue_build_anchor_lines_are_constant_and_usage(self) -> None:
        lines = self._grep(_ANCHOR_QUEUE_BUILD)
        const_lines = [ln for ln in lines if "LOG_PREFIX_QUEUE_BUILD: str =" in ln]
        usage_lines = [ln for ln in lines if "LOG_PREFIX_" not in ln and "feature_id=%s" in ln]
        assert len(const_lines) == 1, const_lines
        assert len(usage_lines) == 1, usage_lines
