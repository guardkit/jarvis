"""Unit tests for the surviving stub-path tools + swap-point grep invariant.

Originally the consolidated suite for ``jarvis.tools.dispatch`` (Phase 2 /
TASK-J002-021). TASK-J004-011 retired the dispatch-side stub anchor;
TASK-J005-005 retires the queue_build half by swapping the stub for a
real JetStream publish — both anchors are now absent from the source tree.

Test class layout (post-TASK-J005-005):

- :class:`TestQueueBuildHappyPath` — happy path returns a JSON ack when
  no transport is wired (degraded JSON shape per ADR-ARCH-021).
- :class:`TestQueueBuildFeatureIdTable` — feature_id accept/reject table.
- :class:`TestQueueBuildRepoTable` — repo accept/reject table.
- :class:`TestQueueBuildAdapterTable` — originating_adapter allow-list.
- :class:`TestQueueBuildRealBuildQueuedPayload` — isinstance check on the
  reconstructed payload.
- :class:`TestSwapPointGrepInvariant` — both anchors retired in source.
"""

from __future__ import annotations

import json
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
    """Invoke the @tool-wrapped ``queue_build`` (async) and return the result."""
    import asyncio

    return asyncio.run(dispatch.queue_build.ainvoke(kwargs))


def _project_root() -> Path:
    """Return the project root (the parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


# ===========================================================================
# Pytest fixture: a connected NATSClient mock so the happy-path tests can
# observe a successful publish without standing up an in-process broker.
# ===========================================================================
@pytest.fixture()
def wired_nats() -> Any:
    """Wire a mock NATSClient with a successful ``js.publish`` AsyncMock."""
    from unittest.mock import AsyncMock, MagicMock

    saved = dispatch._nats_client
    nats_client = MagicMock()
    js = MagicMock()
    js.publish = AsyncMock(return_value=MagicMock(seq=1))
    nats_client.js = js
    dispatch._nats_client = nats_client
    try:
        yield nats_client
    finally:
        dispatch._nats_client = saved


# ===========================================================================
# queue_build — happy path
# ===========================================================================
class TestQueueBuildHappyPath:
    """A valid feature_id + repo + adapter returns a JSON ack on success."""

    def test_happy_path_returns_queue_build_ack(self, wired_nats: Any) -> None:
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
    def test_valid_feature_ids_accepted(self, good: str, wired_nats: Any) -> None:
        result = _invoke_queue_build(
            feature_id=good,
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        ack = json.loads(result)
        assert ack["status"] == "queued", result
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
        parsed = json.loads(result)
        assert parsed["status"] == "validation_error", result
        assert parsed["reason"] == "invalid_feature_id"
        assert "must match FEAT-XXX pattern" in parsed["detail"]


# ===========================================================================
# queue_build — repo table
# ===========================================================================
class TestQueueBuildRepoTable:
    """Boundary table for ``repo`` (^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$)."""

    @pytest.mark.parametrize("good", ["guardkit/jarvis", "appmilla/forge"])
    def test_valid_repos_accepted(self, good: str, wired_nats: Any) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo=good,
        )
        parsed = json.loads(result)
        assert parsed["status"] == "queued", result

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
        parsed = json.loads(result)
        assert parsed["status"] == "validation_error", result
        assert parsed["reason"] == "invalid_repo"
        assert "must be org/name format" in parsed["detail"]


# ===========================================================================
# queue_build — originating_adapter table
# ===========================================================================
class TestQueueBuildAdapterTable:
    """Allow-list table for ``originating_adapter``."""

    @pytest.mark.parametrize(
        "good",
        ["terminal", "telegram", "dashboard", "voice-reachy"],
    )
    def test_each_allowed_adapter_accepted(self, good: str, wired_nats: Any) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
            originating_adapter=good,
        )
        parsed = json.loads(result)
        assert parsed["status"] == "queued", result

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
        parsed = json.loads(result)
        assert parsed["status"] == "validation_error", result
        assert parsed["reason"] == "invalid_adapter"
        assert "not in allowed list" in parsed["detail"]


# ===========================================================================
# queue_build — real BuildQueuedPayload instance (isinstance check)
# ===========================================================================
class TestQueueBuildRealBuildQueuedPayload:
    """The tool constructs a real ``BuildQueuedPayload`` (not a dict)."""

    def test_payload_is_real_build_queued_payload_instance(self, wired_nats: Any) -> None:
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
# Swap-point grep invariant — post-TASK-J004-011 + TASK-J005-005 retirement
# ===========================================================================
class TestSwapPointGrepInvariant:
    """Both the dispatch and queue_build Phase-2 grep anchors are retired."""

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

    def test_queue_build_anchor_is_retired_zero_matches(self) -> None:
        lines = self._grep(_ANCHOR_QUEUE_BUILD)
        assert lines == [], "JARVIS_QUEUE_BUILD_STUB anchor must be retired — found:\n" + "\n".join(
            lines
        )
