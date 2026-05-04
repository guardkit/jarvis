"""Soft-fail tests: Graphiti unavailable — DDR-019 invariants (TASK-J004-016).

Asserts the supervisor's Graphiti-down behaviour:

* Startup against an unreachable Graphiti endpoint still produces a usable
  :class:`AppState` — the process does not exit / crash.
* ``state.graphiti_client is None``; the
  :class:`~jarvis.infrastructure.routing_history.RoutingHistoryWriter` is
  still constructed (degraded mode).
* Real dispatch round-trips succeed when NATS is up — Graphiti soft-fail
  must not break the dispatch contract.
* DDR-019 ratchet: the writer emits ``WARN routing_history_write_failed``
  exactly once on the first attempted write; subsequent writes are silent.
* Recovery: a fresh ``build_app_state`` call after Graphiti is reconfigured
  produces a writer with a connected client (no ratchet carry-over).

The ``WARN routing_history_write_failed`` log line is asserted via
``caplog.records`` filtered on ``logger == "jarvis.infrastructure.routing_history"``
and ``level == WARNING`` — never via stderr / stdout matching.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.lifecycle import AppState, build_app_state
from jarvis.infrastructure.routing_history import (
    ConcurrentWorkloadSnapshot,
    JarvisRoutingHistoryEntry,
    RoutingHistoryWriter,
)
from jarvis.tools import dispatch as dispatch_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
)
from jarvis.tools.dispatch import dispatch_by_capability

ROUTING_HISTORY_LOGGER = "jarvis.infrastructure.routing_history"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _stub_yaml_path() -> Path:
    return _project_root() / "src" / "jarvis" / "config" / "stub_capabilities.yaml"


@pytest.fixture()
def graphiti_unreachable_config(tmp_path: Path) -> JarvisConfig:
    """A :class:`JarvisConfig` whose Graphiti endpoint is set but unreachable."""
    stub_path = _stub_yaml_path()
    assert stub_path.exists()

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint="bolt://203.0.113.2:7687",
            jarvis_traces_dir=tmp_path / "traces",
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def basic_config(tmp_path: Path) -> JarvisConfig:
    """A :class:`JarvisConfig` with no graphiti_endpoint configured."""
    stub_path = _stub_yaml_path()
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
            jarvis_traces_dir=tmp_path / "traces",
        )
    cfg.validate_provider_keys()
    return cfg


def _make_entry(
    decision_id: str = "11111111-2222-4333-8444-555555555555",
    subagent_task_id: str = "corr-graphiti-down",
) -> JarvisRoutingHistoryEntry:
    """Construct a minimum-valid routing-history entry."""
    return JarvisRoutingHistoryEntry(
        decision_id=decision_id,
        session_id="sess-graphiti-down",
        timestamp=datetime.now(UTC),
        supervisor_tool_call_sequence=[],
        capability_snapshot_hash="0" * 64,
        subagent_type="specialist",
        subagent_task_id=subagent_task_id,
        subagent_final_state="success",
        wall_clock_ms=42,
        total_cost_usd=0.0,
        outcome_type="success",
        local_time_of_day="12:00",
        concurrent_workload=ConcurrentWorkloadSnapshot(
            in_flight_dispatches=0,
            in_flight_watchers=0,
            in_flight_subagents=0,
        ),
        supervisor_reasoning_summary="ok",
    )


def _routing_history_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Filter caplog records to the routing-history logger at WARNING+."""
    return [
        record
        for record in caplog.records
        if record.name == ROUTING_HISTORY_LOGGER and record.levelno == logging.WARNING
    ]


def _assert_process_alive(state: AppState) -> None:
    """Sanity check at the tail of every scenario — DDR-019 soft-fail invariant."""
    assert state is not None
    assert isinstance(state, AppState)
    assert state.supervisor is not None


# ===========================================================================
# AC: startup against an unreachable Graphiti endpoint still produces a state
# ===========================================================================
class TestStartupGraphitiUnreachable:
    """Lifecycle returns a usable :class:`AppState` even when Graphiti is unreachable."""

    @pytest.mark.asyncio
    async def test_startup_with_unreachable_graphiti_still_starts(
        self,
        graphiti_unreachable_config: JarvisConfig,
    ) -> None:
        """``build_app_state`` returns; ``state.graphiti_client is None``."""
        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(graphiti_unreachable_config)

        assert state.graphiti_client is None
        _assert_process_alive(state)

    @pytest.mark.asyncio
    async def test_routing_history_writer_in_degraded_mode(
        self,
        graphiti_unreachable_config: JarvisConfig,
    ) -> None:
        """Writer is constructed but holds ``graphiti_client=None`` — degraded mode."""
        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(graphiti_unreachable_config)

        writer = state.routing_history_writer
        assert isinstance(writer, RoutingHistoryWriter)
        # The private attribute is the most reliable signal that the writer
        # is in DDR-019 degraded mode.
        assert writer._graphiti_client is None
        _assert_process_alive(state)


# ===========================================================================
# AC: real dispatch round-trips succeed when only Graphiti is degraded
# ===========================================================================
class TestDispatchSucceedsWhenGraphitiDown:
    """NATS up + Graphiti down: dispatches succeed end-to-end (traces lost)."""

    @pytest.mark.asyncio
    async def test_dispatches_succeed_when_graphiti_down(
        self,
        graphiti_unreachable_config: JarvisConfig,
    ) -> None:
        """A real round-trip returns the specialist's success payload."""
        from nats_core.events import ResultPayload

        # Wire a deterministic capability registry.
        saved_reg = dispatch_module._capability_registry
        dispatch_module._capability_registry = [
            CapabilityDescriptor(
                agent_id="product-owner",
                role="Product Owner",
                description="Reviews specs against acceptance criteria.",
                capability_list=[
                    CapabilityToolSummary(
                        tool_name="review_spec",
                        description="Review a feature spec",
                        risk_level="read_only",
                    ),
                ],
            ),
        ]

        # NATS client returns a successful ResultPayload reply.
        async def _request(subject: str, payload: bytes, *, timeout: float) -> Any:
            del subject, payload, timeout
            success_body = ResultPayload(
                command="review_spec",
                result={"verdict": "ok"},
                correlation_id=None,
                success=True,
            )
            return MagicMock(data=success_body.model_dump_json().encode("utf-8"))

        nats_client = MagicMock()
        nats_client.request = AsyncMock(side_effect=_request)

        # Writer in degraded mode (Graphiti unwired) — same shape as lifecycle.
        writer = RoutingHistoryWriter(
            graphiti_client=None,
            config=graphiti_unreachable_config,
        )

        saved_nats = dispatch_module._nats_client
        saved_writer = dispatch_module._routing_history_writer
        saved_sem = dispatch_module._dispatch_semaphore
        dispatch_module._nats_client = nats_client
        dispatch_module._routing_history_writer = writer
        dispatch_module._dispatch_semaphore = None

        try:
            result = await dispatch_by_capability.ainvoke(
                {"tool_name": "review_spec", "payload_json": "{}"}
            )
            # Yield twice so the fire-and-forget trace task runs to completion
            # — the writer's degraded-mode WARN must not be observable as an
            # exception leaking out of dispatch.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            dispatch_module._capability_registry = saved_reg
            dispatch_module._nats_client = saved_nats
            dispatch_module._routing_history_writer = saved_writer
            dispatch_module._dispatch_semaphore = saved_sem

        # The dispatch tool returns the JSON-serialised ResultPayload on success.
        assert "DEGRADED" not in result
        import json as _json
        parsed = _json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "review_spec"


# ===========================================================================
# AC: DDR-019 soft-fail offload — per-write local file + structured WARN
# (TASK-FRR-003 superseded the original "WARN once, then silent" ratchet —
# the dedup left every subsequent trace dropped on the floor. The writer
# now offloads each entry to ``<traces_dir>/<correlation_id>.json`` and
# emits one ``routing_history_offloaded_locally`` event per write so
# the audit-trail count matches the on-disk file count.)
# ===========================================================================
class TestRatchetWarnOnceThenSilent:
    """Each soft-fail write produces a local offload file + a per-write WARN.

    The class name is preserved to keep ``git log -L`` and grep-anchored
    runbooks pointing at the same place; the contract this class
    asserts has changed (see TASK-FRR-003).
    """

    @pytest.mark.asyncio
    async def test_warn_once_then_silent_ratchet(
        self,
        graphiti_unreachable_config: JarvisConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Three writes against a degraded writer: three offload events + three files."""
        caplog.set_level(logging.WARNING, logger=ROUTING_HISTORY_LOGGER)

        writer = RoutingHistoryWriter(
            graphiti_client=None,
            config=graphiti_unreachable_config,
        )

        n = 3
        for i in range(n):
            await writer.write_specialist_dispatch(
                _make_entry(
                    decision_id=f"00000000-1111-4222-8333-{i:012d}",
                    subagent_task_id=f"corr-{i:08d}-aaaa-bbbb-cccc-dddddddddddd",
                )
            )

        warnings = _routing_history_warnings(caplog)
        offloaded = [
            rec
            for rec in warnings
            if rec.getMessage() == "routing_history_offloaded_locally"
        ]
        # AC: per-write structured event — one event per write, not a single
        # warn-once dedup. The on-disk file count must match this number
        # (FEAT-JARVIS-INTERNAL-001-FRR / TASK-FRR-003).
        assert len(offloaded) == n, (
            f"Expected {n} routing_history_offloaded_locally events, "
            f"got {len(offloaded)}"
        )
        # Each event carries the correlation_id, traces_dir, path, and
        # graphiti_error so on-call can correlate locally-offloaded
        # traces with their dispatch.
        for record in offloaded:
            assert getattr(record, "correlation_id", None) is not None
            assert getattr(record, "traces_dir", None) is not None
            assert getattr(record, "path", None) is not None
            assert getattr(record, "graphiti_error", None) is not None

        # n distinct files should land on disk.
        traces_dir = graphiti_unreachable_config.jarvis_traces_dir
        assert traces_dir.exists()
        files = sorted(traces_dir.glob("*.json"))
        assert len(files) == n, (
            f"Expected {n} offload files on disk, got {len(files)}"
        )


# ===========================================================================
# AC: recovery on the next startup after Graphiti is reconfigured
# ===========================================================================
class TestRecoveryOnRestart:
    """A fresh lifecycle wires a connected Graphiti client; ratchet does not carry."""

    @pytest.mark.asyncio
    async def test_recovery_on_next_startup_after_graphiti_reconfigured(
        self,
        graphiti_unreachable_config: JarvisConfig,
        basic_config: JarvisConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Startup #1 is degraded; startup #2 (with a fake client) is healthy."""
        caplog.set_level(logging.WARNING, logger=ROUTING_HISTORY_LOGGER)

        # ---- Startup #1: Graphiti unreachable -------------------------------
        # ``configure()`` is patched out so it does not clear pytest's caplog
        # handler from the root logger (the production logging-config helper
        # rebuilds the handler list on every call — see
        # ``jarvis.infrastructure.logging.configure`` — which would silently
        # detach the test capture).
        with (
            patch("sys.stderr", new=io.StringIO()),
            patch("jarvis.infrastructure.lifecycle.configure"),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state1 = await build_app_state(graphiti_unreachable_config)

        assert state1.graphiti_client is None
        # First startup's writer is in degraded mode — exercise it once so the
        # WARN-once ratchet fires on instance #1.
        await state1.routing_history_writer.write_specialist_dispatch(_make_entry())
        startup1_warnings = _routing_history_warnings(caplog)
        assert len(startup1_warnings) == 1

        # ---- Startup #2: Graphiti reconfigured + reachable ------------------
        fake_graphiti = MagicMock()
        fake_graphiti.add_episode = AsyncMock(return_value=None)
        fake_graphiti.aclose = AsyncMock()

        caplog.clear()
        with (
            patch("sys.stderr", new=io.StringIO()),
            patch("jarvis.infrastructure.lifecycle.configure"),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=fake_graphiti),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state2 = await build_app_state(basic_config)

        # Recovery: the new writer holds the live client.
        assert state2.graphiti_client is fake_graphiti
        # The writer object is fresh — the per-instance ratchet did not carry.
        assert state2.routing_history_writer._graphiti_client is fake_graphiti

        # Driving a write goes through to graphiti, not the WARN path.
        await state2.routing_history_writer.write_specialist_dispatch(_make_entry())
        # Yield so the fire-and-forget add_episode task lands.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        startup2_warnings = _routing_history_warnings(caplog)
        assert len(startup2_warnings) == 0
        fake_graphiti.add_episode.assert_awaited()
