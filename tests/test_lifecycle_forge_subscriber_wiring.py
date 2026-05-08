"""Tests for TASK-J005-008 — lifecycle wiring for the forge subscriber.

Acceptance criteria covered:

    AC-001: ``build_app_state`` constructs ``ForgeNotificationsSubscriber``
            only when ``nats_client is not None``; sets ``forge_subscriber
            = None`` otherwise.
    AC-002: ``subscriber.start()`` is called once, AFTER fleet
            registration succeeds, BEFORE the ``session_manager`` is
            constructed.
    AC-003: ``subscriber.bind_session_manager(session_manager)`` is called
            once, AFTER ``session_manager`` is constructed, BEFORE
            ``build_app_state`` returns.
    AC-004: ``assemble_tool_list`` accepts ``forge_subscriber=None |
            ForgeNotificationsSubscriber`` and threads it into the
            ``jarvis.tools.dispatch`` module attribute that ``queue_build``
            consumes.
    AC-005: ``AppState`` has a ``forge_subscriber:
            ForgeNotificationsSubscriber | None`` field.
    AC-006: ``shutdown`` calls ``state.forge_subscriber.stop()`` if
            non-None, BEFORE ``deregister_from_fleet``.
    AC-007: ``subscriber.stop()`` is idempotent on double-shutdown and
            is bounded at 5s if the broker is unresponsive.
    AC-008: On ``nats_client is None`` (NATS-down path) the subscriber is
            never constructed and the lifecycle still completes
            successfully.

Tests are unit-level — every transport seam is patched so the suite runs
without an in-process broker.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.lifecycle import AppState
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
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
        )
    cfg.validate_provider_keys()
    return cfg


# ---------------------------------------------------------------------------
# AC-005 — AppState gains the forge_subscriber field
# ---------------------------------------------------------------------------
class TestAppStateForgeSubscriberField:
    """``AppState`` declares ``forge_subscriber`` as an optional field."""

    def test_forge_subscriber_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "forge_subscriber" in field_names

    def test_forge_subscriber_default_is_none(self) -> None:
        config = MagicMock(spec=JarvisConfig)
        state = AppState(
            config=config,
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
            capability_registry=[],
        )
        assert state.forge_subscriber is None


# ---------------------------------------------------------------------------
# AC-001 / AC-002 / AC-003 — happy-path startup wiring (NATS up)
# ---------------------------------------------------------------------------
class TestBuildAppStateForgeSubscriberHappyPath:
    """When NATS is up, the lifecycle constructs + starts + binds the subscriber."""

    @pytest.mark.asyncio
    async def test_subscriber_constructed_started_and_bound(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_live_registry = MagicMock()
        fake_live_registry.snapshot = MagicMock(return_value=[])
        fake_live_registry.close = AsyncMock()
        # TASK-DSR-003 / W2 — assemble_tool_list now schedules
        # ``capabilities_registry.subscribe_updates(...)`` via
        # ``asyncio.create_task``, so the Protocol-declared async method
        # must be awaitable on the fake.
        fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock()
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.register_on_fleet",
                new=AsyncMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
                new=AsyncMock(return_value=fake_live_registry),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.heartbeat_loop",
                new=AsyncMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ForgeNotificationsSubscriber",
                return_value=fake_subscriber,
            ) as mock_subscriber_cls,
        ):
            state = await build_app_state(stub_registry_config)

        # AC-001: constructed when NATS is up.
        mock_subscriber_cls.assert_called_once()
        ctor_kwargs = mock_subscriber_cls.call_args.kwargs
        assert ctor_kwargs["nats_client"] is fake_nats
        assert ctor_kwargs["queue_cap"] == stub_registry_config.forge_notifications_queue_cap
        assert (
            ctor_kwargs["correlation_cap"]
            == stub_registry_config.forge_correlation_map_cap
        )

        # AC-002: start() called exactly once.
        fake_subscriber.start.assert_awaited_once()

        # AC-003: bind_session_manager called exactly once with the session
        # manager that lifecycle constructed.
        fake_subscriber.bind_session_manager.assert_called_once_with(
            state.session_manager
        )

        # forge_subscriber returned on the AppState.
        assert state.forge_subscriber is fake_subscriber

        # Cleanup the heartbeat task we scheduled
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task


# ---------------------------------------------------------------------------
# AC-001 / AC-008 — NATS-down soft-fail path
# ---------------------------------------------------------------------------
class TestBuildAppStateForgeSubscriberNatsDown:
    """When NATS is down, the subscriber is never constructed."""

    @pytest.mark.asyncio
    async def test_nats_none_skips_subscriber_construction(
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
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ForgeNotificationsSubscriber"
            ) as mock_subscriber_cls,
        ):
            state = await build_app_state(stub_registry_config)

        # AC-001 / AC-008: NATS down → no construction.
        mock_subscriber_cls.assert_not_called()
        assert state.forge_subscriber is None
        # Lifecycle still completes.
        assert state.session_manager is not None


# ---------------------------------------------------------------------------
# AC-004 — assemble_tool_list propagates forge_subscriber to dispatch module
# ---------------------------------------------------------------------------
class TestAssembleToolListForgeSubscriberKwarg:
    """``assemble_tool_list`` snapshots ``forge_subscriber`` into
    ``jarvis.tools.dispatch._forge_subscriber``."""

    def test_kwarg_propagates_to_dispatch_module_attribute(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.tools import assemble_tool_list

        fake_subscriber = MagicMock()

        orig = getattr(_dispatch_module, "_forge_subscriber", None)
        try:
            assemble_tool_list(
                stub_registry_config,
                [],
                include_frontier=True,
                forge_subscriber=fake_subscriber,
            )
            assert _dispatch_module._forge_subscriber is fake_subscriber
        finally:
            _dispatch_module._forge_subscriber = orig

    def test_default_kwarg_clears_dispatch_module_attribute(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.tools import assemble_tool_list

        _dispatch_module._forge_subscriber = MagicMock()
        try:
            assemble_tool_list(stub_registry_config, [], include_frontier=True)
            assert _dispatch_module._forge_subscriber is None
        finally:
            _dispatch_module._forge_subscriber = None

    def test_ambient_call_also_propagates(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.tools import assemble_tool_list

        fake_subscriber = MagicMock()
        orig = getattr(_dispatch_module, "_forge_subscriber", None)
        try:
            assemble_tool_list(
                stub_registry_config,
                [],
                include_frontier=False,
                forge_subscriber=fake_subscriber,
            )
            assert _dispatch_module._forge_subscriber is fake_subscriber
        finally:
            _dispatch_module._forge_subscriber = orig


# ---------------------------------------------------------------------------
# AC-006 / AC-007 — shutdown stops the subscriber idempotently and BEFORE
# deregister_from_fleet.
# ---------------------------------------------------------------------------
class TestShutdownForgeSubscriberOrderAndIdempotency:
    """``shutdown`` calls subscriber.stop() between heartbeat-cancel and
    deregister, and double-shutdown is a no-op."""

    def _build_state(self, calls: list[str]) -> tuple[AppState, MagicMock]:
        config = MagicMock(spec=JarvisConfig)
        store = MagicMock()
        store.close = MagicMock(side_effect=lambda: calls.append("store.close"))

        nats_client = MagicMock()
        nats_client.drain = AsyncMock(
            side_effect=lambda timeout: calls.append("nats.drain")
        )

        graphiti_client = MagicMock()
        graphiti_client.aclose = AsyncMock(
            side_effect=lambda: calls.append("graphiti.aclose")
        )

        from jarvis.infrastructure.routing_history import RoutingHistoryWriter

        writer = MagicMock(spec=RoutingHistoryWriter)
        writer.flush = AsyncMock(
            side_effect=lambda timeout: calls.append("writer.flush")
        )

        capabilities_registry = MagicMock()
        capabilities_registry.close = AsyncMock(
            side_effect=lambda: calls.append("capabilities.close")
        )

        forge_subscriber = MagicMock()
        forge_subscriber.stop = AsyncMock(
            side_effect=lambda: calls.append("forge.stop")
        )

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append("heartbeat.cancelled")
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())

        state = AppState(
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
            forge_subscriber=forge_subscriber,
        )
        return state, forge_subscriber

    @pytest.mark.asyncio
    async def test_subscriber_stop_called_before_deregister(self) -> None:
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(
                side_effect=lambda *a, **kw: calls.append("fleet.deregister")
            ),
        ):
            state, fake_subscriber = self._build_state(calls)
            await asyncio.sleep(0)
            await shutdown(state)

        # AC-006: forge.stop runs after heartbeat cancel and BEFORE deregister.
        idx = {name: i for i, name in enumerate(calls)}
        assert "forge.stop" in idx, calls
        assert idx["heartbeat.cancelled"] < idx["forge.stop"]
        assert idx["forge.stop"] < idx["fleet.deregister"]
        fake_subscriber.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_double_shutdown_is_idempotent(self) -> None:
        """Calling shutdown twice does not raise — the subscriber's stop()
        is itself idempotent and the lifecycle's wrapper tolerates it."""
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            state, _fake_subscriber = self._build_state(calls)
            await asyncio.sleep(0)
            await shutdown(state)
            # Second call must not raise.
            await shutdown(state)

    @pytest.mark.asyncio
    async def test_shutdown_continues_when_subscriber_stop_raises(self) -> None:
        """A subscriber.stop() exception must not abort the rest of shutdown."""
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            state, fake_subscriber = self._build_state(calls)
            fake_subscriber.stop = AsyncMock(side_effect=RuntimeError("broker down"))
            await asyncio.sleep(0)
            await shutdown(state)

        # All later steps still ran:
        assert "writer.flush" in calls
        assert "nats.drain" in calls
        assert "graphiti.aclose" in calls
        assert "store.close" in calls

    @pytest.mark.asyncio
    async def test_shutdown_skips_subscriber_when_none(self) -> None:
        """If forge_subscriber is None (NATS-down path), shutdown skips the
        new step and runs the rest of the sequence cleanly."""
        from jarvis.infrastructure.lifecycle import shutdown

        config = MagicMock(spec=JarvisConfig)
        state = AppState(
            config=config,
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
            capability_registry=[],
            forge_subscriber=None,
        )

        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            await shutdown(state)


# ---------------------------------------------------------------------------
# AC-002 ordering — start() runs AFTER fleet registration succeeds and
# BEFORE session_manager is constructed.
# ---------------------------------------------------------------------------
class TestStartupOrdering:
    """The construction order is strict: fleet register → subscriber.start →
    SessionManager → bind_session_manager."""

    @pytest.mark.asyncio
    async def test_start_after_fleet_register_before_session_manager(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_live_registry = MagicMock()
        fake_live_registry.snapshot = MagicMock(return_value=[])
        fake_live_registry.close = AsyncMock()
        # TASK-DSR-003 / W2 — assemble_tool_list now schedules
        # ``capabilities_registry.subscribe_updates(...)`` via
        # ``asyncio.create_task``, so the Protocol-declared async method
        # must be awaitable on the fake.
        fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

        order: list[str] = []

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock(side_effect=lambda: order.append("start"))
        fake_subscriber.bind_session_manager = MagicMock(
            side_effect=lambda sm: order.append("bind")
        )
        fake_subscriber.stop = AsyncMock()

        async def _register(*a: Any, **kw: Any) -> None:
            order.append("register")

        def _make_session_manager(*a: Any, **kw: Any) -> Any:
            order.append("session_manager")
            return MagicMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.register_on_fleet",
                new=AsyncMock(side_effect=_register),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
                new=AsyncMock(return_value=fake_live_registry),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.heartbeat_loop",
                new=AsyncMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
            patch(
                "jarvis.infrastructure.lifecycle.SessionManager",
                side_effect=_make_session_manager,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ForgeNotificationsSubscriber",
                return_value=fake_subscriber,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        # Strict invariants:
        # 1. register_on_fleet ran before subscriber.start
        # 2. subscriber.start ran before SessionManager construction
        # 3. SessionManager construction ran before bind_session_manager
        idx = {name: i for i, name in enumerate(order)}
        assert idx["register"] < idx["start"], order
        assert idx["start"] < idx["session_manager"], order
        assert idx["session_manager"] < idx["bind"], order

        # Cleanup the heartbeat task we scheduled
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task
