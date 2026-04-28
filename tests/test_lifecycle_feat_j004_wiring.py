"""Tests for TASK-J004-013 — lifecycle startup + shutdown wiring (FEAT-JARVIS-004).

Acceptance criteria covered:

    AC-001: Startup wiring matches design §8 sequence exactly.
    AC-002: ``NATSClient.connect`` returning ``None`` does NOT block startup;
            ``capabilities_registry`` falls back to ``StubCapabilitiesRegistry``;
            ``heartbeat_task = None``.
    AC-003: ``GraphitiClient.connect`` failure does NOT block startup;
            ``routing_history_writer`` is constructed with
            ``graphiti_client=None`` (degraded mode).
    AC-004: ``AppState`` gains the four new fields (frozen dataclass).
    AC-005: ``assemble_tool_list`` accepts and propagates the three new
            kwargs to ``tools/dispatch.py`` module attributes.
    AC-006: Shutdown order matches the 8-step sequence; each step
            independently failure-tolerant.
    AC-007: Heartbeat task cancellation produces no traceback.

Tests are purely unit-level — every transport seam (NATS, Graphiti,
fleet registration, capabilities registry) is patched so the suite runs
without an in-process broker or graph store.
"""

from __future__ import annotations

import asyncio
import dataclasses
import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.dispatch_semaphore import DispatchSemaphore
from jarvis.infrastructure.lifecycle import AppState
from jarvis.infrastructure.routing_history import RoutingHistoryWriter
from jarvis.tools import dispatch as _dispatch_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def stub_registry_config() -> JarvisConfig:
    """A ``JarvisConfig`` whose ``stub_capabilities_path`` resolves to a
    real on-disk YAML so the StubCapabilitiesRegistry path can construct."""
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists()

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def patched_supervisor() -> Any:
    """Patches around build_supervisor so the lifecycle returns deterministically."""
    return MagicMock()


# ---------------------------------------------------------------------------
# AC-004 — AppState gains the four new fields (frozen dataclass)
# ---------------------------------------------------------------------------
class TestAC004AppStateExtensions:
    """``AppState`` gains nats_client, graphiti_client, routing_history_writer,
    fleet_heartbeat_task, capabilities_registry as declared dataclass fields."""

    def test_nats_client_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "nats_client" in field_names

    def test_graphiti_client_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "graphiti_client" in field_names

    def test_routing_history_writer_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "routing_history_writer" in field_names

    def test_fleet_heartbeat_task_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "fleet_heartbeat_task" in field_names

    def test_capabilities_registry_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "capabilities_registry" in field_names

    def test_appstate_remains_frozen(self) -> None:
        """The dataclass is still frozen — the four new fields cannot mutate."""
        params = AppState.__dataclass_params__  # type: ignore[attr-defined]
        assert params.frozen is True


# ---------------------------------------------------------------------------
# AC-002 — NATSClient.connect returning None → soft-fail
# ---------------------------------------------------------------------------
class TestAC002NatsSoftFail:
    """When ``NATSClient.connect`` returns ``None``, the lifecycle uses the
    Stub capabilities registry and ``fleet_heartbeat_task is None``."""

    @pytest.mark.asyncio
    async def test_nats_none_uses_stub_registry_and_no_heartbeat(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.capabilities_registry import StubCapabilitiesRegistry
        from jarvis.infrastructure.lifecycle import build_app_state

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
            patch("jarvis.infrastructure.lifecycle.build_supervisor", return_value=MagicMock()),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.nats_client is None
        assert state.fleet_heartbeat_task is None
        assert isinstance(state.capabilities_registry, StubCapabilitiesRegistry)


# ---------------------------------------------------------------------------
# AC-003 — Graphiti soft-fail
# ---------------------------------------------------------------------------
class TestAC003GraphitiSoftFail:
    """When Graphiti soft-fails, the writer is still constructed but with
    ``graphiti_client=None`` (degraded mode)."""

    @pytest.mark.asyncio
    async def test_graphiti_none_writer_in_degraded_mode(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state

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
            patch("jarvis.infrastructure.lifecycle.build_supervisor", return_value=MagicMock()),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.graphiti_client is None
        assert isinstance(state.routing_history_writer, RoutingHistoryWriter)
        # The writer must report the unavailable graphiti when called.
        # Force a write — should not raise; it should warn-and-no-op.
        from jarvis.infrastructure.routing_history import (
            ConcurrentWorkloadSnapshot,
            JarvisRoutingHistoryEntry,
        )

        entry = JarvisRoutingHistoryEntry(
            decision_id="11111111-2222-4333-8444-555555555555",
            session_id="s",
            timestamp=__import__("datetime").datetime.now(__import__("datetime").UTC),
            supervisor_tool_call_sequence=[],
            capability_snapshot_hash="0" * 64,
            subagent_type="specialist",
            subagent_task_id="t",
            subagent_final_state="success",
            wall_clock_ms=1,
            total_cost_usd=0.0,
            outcome_type="success",
            local_time_of_day="09:00",
            concurrent_workload=ConcurrentWorkloadSnapshot(
                in_flight_dispatches=0,
                in_flight_watchers=0,
                in_flight_subagents=0,
            ),
            supervisor_reasoning_summary="ok",
        )
        # No exception expected — writer is in degraded mode.
        await state.routing_history_writer.write_specialist_dispatch(entry)


# ---------------------------------------------------------------------------
# AC-001 — happy-path startup wiring (NATS up + Graphiti up)
# ---------------------------------------------------------------------------
class TestAC001StartupHappyPath:
    """When both transports come up, the lifecycle wires the live registry,
    schedules a heartbeat task, and registers on the fleet."""

    @pytest.mark.asyncio
    async def test_nats_up_graphiti_up_full_wiring(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()
        fake_graphiti = MagicMock()
        fake_graphiti.aclose = AsyncMock()

        fake_live_registry = MagicMock()
        fake_live_registry.snapshot = MagicMock(return_value=[])
        fake_live_registry.close = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=fake_graphiti),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.register_on_fleet",
                new=AsyncMock(),
            ) as mock_register,
            patch(
                "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
                new=AsyncMock(return_value=fake_live_registry),
            ) as mock_create_live,
            patch(
                "jarvis.infrastructure.lifecycle.heartbeat_loop",
                new=AsyncMock(),
            ),
            patch("jarvis.infrastructure.lifecycle.build_supervisor", return_value=MagicMock()),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.nats_client is fake_nats
        assert state.graphiti_client is fake_graphiti
        assert state.capabilities_registry is fake_live_registry
        assert state.fleet_heartbeat_task is not None
        assert isinstance(state.fleet_heartbeat_task, asyncio.Task)
        mock_register.assert_awaited_once()
        mock_create_live.assert_awaited_once()

        # Cleanup the heartbeat task we scheduled
        state.fleet_heartbeat_task.cancel()
        try:
            await state.fleet_heartbeat_task
        except (asyncio.CancelledError, Exception):
            pass


# ---------------------------------------------------------------------------
# AC-005 — assemble_tool_list propagates the three new kwargs to dispatch
# ---------------------------------------------------------------------------
class TestAC005AssembleToolListPropagatesDispatchKwargs:
    """``assemble_tool_list`` snapshots nats_client / writer / semaphore into
    ``jarvis.tools.dispatch`` module attributes."""

    def test_kwargs_propagate_to_dispatch_module_attributes(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.tools import assemble_tool_list

        fake_nats = MagicMock()
        fake_writer = MagicMock(spec=RoutingHistoryWriter)
        fake_sem = DispatchSemaphore(cap=4)

        # Save originals so the test does not poison sibling tests.
        orig_nats = _dispatch_module._nats_client
        orig_writer = _dispatch_module._routing_history_writer
        orig_sem = _dispatch_module._dispatch_semaphore
        try:
            assemble_tool_list(
                stub_registry_config,
                [],
                include_frontier=True,
                nats_client=fake_nats,
                routing_history_writer=fake_writer,
                dispatch_semaphore=fake_sem,
            )
            assert _dispatch_module._nats_client is fake_nats
            assert _dispatch_module._routing_history_writer is fake_writer
            assert _dispatch_module._dispatch_semaphore is fake_sem
        finally:
            _dispatch_module._nats_client = orig_nats
            _dispatch_module._routing_history_writer = orig_writer
            _dispatch_module._dispatch_semaphore = orig_sem

    def test_default_kwargs_clear_dispatch_module_attributes(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """Calling without the new kwargs explicitly resets dispatch deps to None
        — protects against stale wiring leaking between processes."""
        from jarvis.tools import assemble_tool_list

        # Pre-populate with stubs so we can verify the reset.
        _dispatch_module._nats_client = MagicMock()
        _dispatch_module._routing_history_writer = MagicMock()
        _dispatch_module._dispatch_semaphore = DispatchSemaphore(cap=4)

        try:
            assemble_tool_list(stub_registry_config, [], include_frontier=True)
            assert _dispatch_module._nats_client is None
            assert _dispatch_module._routing_history_writer is None
            assert _dispatch_module._dispatch_semaphore is None
        finally:
            _dispatch_module._nats_client = None
            _dispatch_module._routing_history_writer = None
            _dispatch_module._dispatch_semaphore = None


# ---------------------------------------------------------------------------
# AC-006 — shutdown order + each-step failure tolerance
# ---------------------------------------------------------------------------
class TestAC006ShutdownOrderAndFailureTolerance:
    """Shutdown sequence runs in declared order and tolerates step failures."""

    def _build_state_with_recording_calls(self, calls: list[str]) -> AppState:
        """Build a synthetic AppState whose teardown methods append to ``calls``."""
        config = MagicMock(spec=JarvisConfig)
        store = MagicMock()
        store.close = MagicMock(side_effect=lambda: calls.append("store.close"))

        nats_client = MagicMock()
        nats_client.drain = AsyncMock(side_effect=lambda timeout: calls.append("nats.drain"))

        graphiti_client = MagicMock()
        graphiti_client.aclose = AsyncMock(side_effect=lambda: calls.append("graphiti.aclose"))

        writer = MagicMock(spec=RoutingHistoryWriter)
        writer.flush = AsyncMock(side_effect=lambda timeout: calls.append("writer.flush"))

        capabilities_registry = MagicMock()
        capabilities_registry.close = AsyncMock(
            side_effect=lambda: calls.append("capabilities.close"),
        )

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append("heartbeat.cancelled")
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())

        return AppState(
            config=config,
            supervisor=MagicMock(),
            store=store,
            session_manager=MagicMock(),
            capability_registry=[],
            llamaswap_adapter=None,
            nats_client=nats_client,
            graphiti_client=graphiti_client,
            routing_history_writer=writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=capabilities_registry,
        )

    @pytest.mark.asyncio
    async def test_shutdown_runs_in_declared_order(self) -> None:
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(side_effect=lambda *a, **kw: calls.append("fleet.deregister")),
        ):
            state = self._build_state_with_recording_calls(calls)
            # Yield once so the heartbeat task starts running and enters its
            # try/except block — without this the cancel arrives before the
            # task body ever executes and our "heartbeat.cancelled" sentinel
            # never lands.
            await asyncio.sleep(0)
            await shutdown(state)

        # Required ordering invariants from design §8:
        # 1) heartbeat cancelled BEFORE deregister
        # 2) deregister BEFORE capabilities.close
        # 3) capabilities.close BEFORE writer.flush
        # 4) writer.flush BEFORE nats.drain
        # 5) nats.drain BEFORE graphiti.aclose
        # 6) graphiti.aclose BEFORE store.close
        idx = {name: i for i, name in enumerate(calls)}
        assert idx["heartbeat.cancelled"] < idx["fleet.deregister"]
        assert idx["fleet.deregister"] < idx["capabilities.close"]
        assert idx["capabilities.close"] < idx["writer.flush"]
        assert idx["writer.flush"] < idx["nats.drain"]
        assert idx["nats.drain"] < idx["graphiti.aclose"]
        assert idx["graphiti.aclose"] < idx["store.close"]

    @pytest.mark.asyncio
    async def test_shutdown_continues_when_a_step_raises(self) -> None:
        """If ``deregister_from_fleet`` raises, the rest of the sequence still runs."""
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(side_effect=RuntimeError("broker offline")),
        ):
            state = self._build_state_with_recording_calls(calls)
            await asyncio.sleep(0)
            await shutdown(state)

        # All later steps still ran:
        assert "capabilities.close" in calls
        assert "writer.flush" in calls
        assert "nats.drain" in calls
        assert "graphiti.aclose" in calls
        assert "store.close" in calls

    @pytest.mark.asyncio
    async def test_shutdown_disarms_layer2_hooks_and_dispatch_deps(self) -> None:
        from jarvis.infrastructure.lifecycle import shutdown

        # Pre-arm dispatch deps to verify they get cleared.
        _dispatch_module._current_session_hook = lambda: None
        _dispatch_module._async_subagent_frame_hook = lambda: None
        _dispatch_module._nats_client = MagicMock()
        _dispatch_module._routing_history_writer = MagicMock()
        _dispatch_module._dispatch_semaphore = DispatchSemaphore(cap=4)

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            state = self._build_state_with_recording_calls(calls)
            await shutdown(state)

        assert _dispatch_module._current_session_hook is None
        assert _dispatch_module._async_subagent_frame_hook is None
        assert _dispatch_module._nats_client is None
        assert _dispatch_module._routing_history_writer is None
        assert _dispatch_module._dispatch_semaphore is None


# ---------------------------------------------------------------------------
# AC-007 — heartbeat task cancellation produces no traceback
# ---------------------------------------------------------------------------
class TestAC007HeartbeatCancellationClean:
    """Cancelling the heartbeat task during shutdown does not leak a traceback."""

    @pytest.mark.asyncio
    async def test_cancellation_handled_silently(self) -> None:
        from jarvis.infrastructure.lifecycle import shutdown

        async def _heartbeat() -> None:
            # Mirror the production heartbeat_loop CancelledError contract:
            # log INFO + re-raise. Here we just re-raise so asyncio records
            # the cancellation cleanly.
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                raise

        loop = asyncio.get_event_loop()
        task = loop.create_task(_heartbeat())

        config = MagicMock(spec=JarvisConfig)
        state = AppState(
            config=config,
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
            capability_registry=[],
            fleet_heartbeat_task=task,
        )

        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            await shutdown(state)

        assert task.cancelled() or task.done()


# ---------------------------------------------------------------------------
# Seam test from task spec — writer.flush bounded at <= 5.0s
# ---------------------------------------------------------------------------
class TestSeamRoutingHistoryWriterFlushBounded:
    """``shutdown`` calls ``writer.flush(timeout<=5.0)`` per DDR-019 contract."""

    @pytest.mark.asyncio
    async def test_lifecycle_calls_writer_flush_with_bounded_timeout(self) -> None:
        from jarvis.infrastructure.lifecycle import shutdown

        writer = MagicMock(spec=RoutingHistoryWriter)
        writer.flush = AsyncMock()

        config = MagicMock(spec=JarvisConfig)
        state = AppState(
            config=config,
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
            capability_registry=[],
            routing_history_writer=writer,
        )

        await shutdown(state)

        writer.flush.assert_awaited_once()
        _, kwargs = writer.flush.call_args
        assert "timeout" in kwargs and kwargs["timeout"] <= 5.0, (
            "lifecycle must bound writer.flush at <= 5.0s per DDR-019"
        )
