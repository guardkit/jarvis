"""End-to-end write-seam boundary test: RoutingHistoryWriter → FleetMemoryClient.

FEAT-MEM-09 §3 contract: wire a *real* :class:`FleetMemoryClient` (not a
recording double, not a MagicMock) into the :class:`RoutingHistoryWriter` and
stub only the external NATS publish edge. This exercises the full write path —
redaction at the write boundary, the real ``build_memory_episode`` construction,
and the fire-and-forget submission — proving the writer and the fleet-memory
client integrate, without a live broker.

The recording-double tests in ``test_routing_history_writer.py`` cover the
writer's own logic in isolation; this file is the integration evidence that the
seam the writer actually talks to in production builds + publishes a real
episode.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.fleet_memory.client import FleetMemoryClient
from jarvis.infrastructure.fleet_memory.publisher import PublishSummary
from jarvis.infrastructure.routing_history import (
    REDACTION_PLACEHOLDER,
    ConcurrentWorkloadSnapshot,
    JarvisRoutingHistoryEntry,
    RoutingHistoryWriter,
)

_HAS_NATS_CORE = importlib.util.find_spec("nats_core") is not None

# The client resolves ``publish_episodes`` into its own namespace, so the
# boundary patch targets the client module (see test_fleet_memory_client.py).
_PUBLISH_EDGE = "jarvis.infrastructure.fleet_memory.client.publish_episodes"

pytestmark = pytest.mark.skipif(
    not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed"
)


def _enabled_config(traces_dir: Path) -> JarvisConfig:
    with patch.dict("os.environ", {}, clear=True):
        return JarvisConfig(
            llama_swap_base_url="http://fake-endpoint",
            fleet_memory_enabled=True,
            jarvis_traces_dir=traces_dir,
        )


def _entry(*, reasoning: str) -> JarvisRoutingHistoryEntry:
    return JarvisRoutingHistoryEntry(
        decision_id="11111111-2222-4333-8444-555555555555",
        session_id="sess-1",
        timestamp=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        supervisor_tool_call_sequence=[],
        capability_snapshot_hash="0" * 64,
        subagent_type="specialist",
        subagent_task_id="corr-1",
        subagent_final_state="success",
        wall_clock_ms=10,
        total_cost_usd=0.0,
        outcome_type="success",
        local_time_of_day="12:00",
        concurrent_workload=ConcurrentWorkloadSnapshot(
            in_flight_dispatches=0, in_flight_watchers=0, in_flight_subagents=0
        ),
        supervisor_reasoning_summary=reasoning,
    )


class TestWriterFleetMemoryBoundary:
    """The writer publishes a real ``document`` episode via the real client."""

    async def test_specialist_dispatch_publishes_document_episode(
        self, tmp_path: Path
    ) -> None:
        client = FleetMemoryClient(_enabled_config(tmp_path / "traces"))
        writer = RoutingHistoryWriter(client, client._config)

        with patch(
            _PUBLISH_EDGE,
            new=AsyncMock(return_value=PublishSummary(1, 0, {})),
        ) as mock_pub:
            await writer.write_specialist_dispatch(_entry(reasoning="ok"))
            await writer.flush(timeout=5.0)

        mock_pub.assert_awaited()
        episodes = mock_pub.call_args.args[0]
        ep = episodes[0]
        assert ep.project_id == "jarvis"
        assert ep.episode_type == "document"
        assert ep.content_format == "markdown"
        # The published body is the full routing-history entry JSON.
        body = json.loads(ep.body)
        assert body["decision_id"] == "11111111-2222-4333-8444-555555555555"
        assert body["subagent_type"] == "specialist"
        # No local offload happened — the client was present and published.
        assert not list((tmp_path / "traces").glob("*.json"))

    async def test_redaction_runs_before_publish(self, tmp_path: Path) -> None:
        """A secret in a human-shaped field is redacted in the published body."""
        client = FleetMemoryClient(_enabled_config(tmp_path / "traces"))
        writer = RoutingHistoryWriter(client, client._config)
        secret = "sk-ABCDEFGHIJKLMNOP1234"

        with patch(
            _PUBLISH_EDGE,
            new=AsyncMock(return_value=PublishSummary(1, 0, {})),
        ) as mock_pub:
            await writer.write_specialist_dispatch(
                _entry(reasoning=f"chose specialist using {secret}")
            )
            await writer.flush(timeout=5.0)

        ep = mock_pub.call_args.args[0][0]
        assert secret not in ep.body
        assert REDACTION_PLACEHOLDER in ep.body
