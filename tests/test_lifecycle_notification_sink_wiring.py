"""Tests for TASK-JNB-003 — lifecycle wiring for the notification sink.

Acceptance criteria covered:

    AC-001: ``build_app_state`` constructs a real SlackNotifier when both
            ``JARVIS_SLACK_BOT_TOKEN`` and ``JARVIS_SLACK_CHANNEL_ID`` are
            set, and a logged no-op sink otherwise; construction never raises
            for any settings permutation.
    AC-002: The constructed sink is bound to ForgeNotificationsSubscriber via
            ``bind_notification_sink()`` and installed as the
            ``tools/dispatch.py`` module-level ``_notification_sink`` snapshot,
            so subscriber events and the ``queue_build`` queued hook flow
            through the same instance.
    AC-003: Start ordering: the notifier is started before the subscriber
            binds/starts; stop ordering: the notifier stops after the
            subscriber, with a best-effort bounded drain of queued messages.
    AC-004: NATS down at startup preserves the existing DDR-021 soft-fail
            behaviour with the notifier idle; the supervisor does not crash.
    AC-005: Slack config missing (either or both env vars unset) yields the
            logged no-op sink; the supervisor boots cleanly and all notify
            paths remain no-ops.
    AC-006: Supervisor boots cleanly in all degraded permutations: NATS up/down
            crossed with Slack config present/absent (four permutations, none
            crash).
    AC-007: Wiring tests mirror the existing ``forge_subscriber`` lifecycle
            tests in structure and placement.
    AC-008: A synthetic queued + started + complete sequence through the fully
            wired path produces exactly three ``chat.postMessage`` calls on a
            mocked Slack client.
    AC-009: All modified files pass project-configured lint/format checks with
            zero errors.

Tests are unit-level — every transport seam is patched so the suite runs
without an in-process broker or live Slack API.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import io
from pathlib import Path
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


@pytest.fixture()
def stub_registry_config_with_slack() -> JarvisConfig:
    """A ``JarvisConfig`` with Slack credentials set."""
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists()

    with patch.dict(
        "os.environ",
        {
            "JARVIS_SLACK_BOT_TOKEN": "xoxb-fake-token",
            "JARVIS_SLACK_CHANNEL_ID": "C12345678",
        },
        clear=True,
    ):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
        )
    cfg.validate_provider_keys()
    return cfg


# ---------------------------------------------------------------------------
# AC-001 / AC-005 — AppState gains the notification_sink field
# ---------------------------------------------------------------------------
class TestAppStateNotificationSinkField:
    """``AppState`` declares ``notification_sink`` as a field."""

    def test_notification_sink_field_present(self) -> None:
        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "notification_sink" in field_names

    def test_notification_sink_default_is_none(self) -> None:
        config = MagicMock(spec=JarvisConfig)
        state = AppState(
            config=config,
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
            capability_registry=[],
        )
        assert state.notification_sink is None


# ---------------------------------------------------------------------------
# AC-001 / AC-002 / AC-005 — happy-path startup wiring (Slack configured)
# ---------------------------------------------------------------------------
class TestBuildAppStateNotificationSinkHappyPath:
    """When Slack config is present, the lifecycle constructs + starts + binds the sink."""

    @pytest.mark.asyncio
    async def test_sink_constructed_started_and_bound_with_slack(
        self, stub_registry_config_with_slack: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_live_registry = MagicMock()
        fake_live_registry.snapshot = MagicMock(return_value=[])
        fake_live_registry.close = AsyncMock()
        fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock()
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock()

        fake_sink = MagicMock()
        fake_sink.start = AsyncMock()
        fake_sink.stop = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_memory",
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
            ),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=fake_sink,
            ) as mock_create_sink,
        ):
            state = await build_app_state(stub_registry_config_with_slack)

        # AC-001: constructed when Slack config is set. Approval-card
        # truth R3-B: lifecycle also threads the shared terminal-state
        # registry into the sink factory.
        from unittest.mock import ANY

        from jarvis.infrastructure.terminal_builds import TerminalBuildRegistry

        mock_create_sink.assert_called_once_with(
            stub_registry_config_with_slack, terminal_registry=ANY
        )
        assert isinstance(
            mock_create_sink.call_args.kwargs["terminal_registry"], TerminalBuildRegistry
        )

        # AC-002: sink is bound to the subscriber
        fake_subscriber.bind_notification_sink.assert_called_once_with(fake_sink)

        # AC-002: sink is snapshotted into dispatch module (verified indirectly
        # via assemble_tool_list call in lifecycle)
        assert state.notification_sink is fake_sink

        # AC-003: sink.start() called
        fake_sink.start.assert_awaited_once()

        # Cleanup the heartbeat task we scheduled
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task

    @pytest.mark.asyncio
    async def test_sink_constructed_as_noop_when_slack_missing(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """AC-005: No Slack config yields NoOpSink."""
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_live_registry = MagicMock()
        fake_live_registry.snapshot = MagicMock(return_value=[])
        fake_live_registry.close = AsyncMock()
        fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock()
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock()

        fake_noop_sink = MagicMock()
        fake_noop_sink.start = AsyncMock()
        fake_noop_sink.stop = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_memory",
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
            ),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=fake_noop_sink,
            ) as mock_create_sink,
        ):
            state = await build_app_state(stub_registry_config)

        # AC-005: NoOpSink constructed when Slack config is missing
        # (the R3-B terminal registry rides along on every permutation).
        from unittest.mock import ANY

        mock_create_sink.assert_called_once_with(stub_registry_config, terminal_registry=ANY)
        assert state.notification_sink is fake_noop_sink

        # Cleanup the heartbeat task
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task


# ---------------------------------------------------------------------------
# AC-004 / AC-006 — NATS-down soft-fail path
# ---------------------------------------------------------------------------
class TestBuildAppStateNotificationSinkNatsDown:
    """When NATS is down, the sink is still constructed and started."""

    @pytest.mark.asyncio
    async def test_nats_none_still_constructs_sink(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """AC-004: NATS down preserves DDR-021 soft-fail with notifier idle."""
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_sink = MagicMock()
        fake_sink.start = AsyncMock()
        fake_sink.stop = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_memory",
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
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=fake_sink,
            ) as mock_create_sink,
        ):
            state = await build_app_state(stub_registry_config)

        # AC-004: Sink is still constructed and started even when NATS is down
        mock_create_sink.assert_called_once()
        fake_sink.start.assert_awaited_once()
        assert state.notification_sink is fake_sink
        # Lifecycle still completes
        assert state.session_manager is not None


# ---------------------------------------------------------------------------
# AC-006 — All four degraded permutations boot cleanly
# ---------------------------------------------------------------------------
class TestDegradedPermutations:
    """AC-006: Supervisor boots cleanly in all NATS x Slack permutations."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "nats_available,slack_available",
        [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    async def test_all_permutations_boot_cleanly(
        self, nats_available: bool, slack_available: bool
    ) -> None:
        """AC-006: All four permutations boot without crash."""
        from jarvis.infrastructure.lifecycle import build_app_state

        project_root = Path(__file__).resolve().parent.parent
        stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"

        env_dict: dict[str, str] = {}
        if slack_available:
            env_dict["JARVIS_SLACK_BOT_TOKEN"] = "xoxb-fake"
            env_dict["JARVIS_SLACK_CHANNEL_ID"] = "C123"

        with patch.dict("os.environ", env_dict, clear=True):
            config = JarvisConfig(
                stub_capabilities_path=stub_path,
                llama_swap_base_url="http://fake:9000",
                graphiti_endpoint=None,
            )

        fake_nats = MagicMock() if nats_available else None
        if nats_available:
            fake_nats.drain = AsyncMock()

        fake_sink = MagicMock()
        fake_sink.start = AsyncMock()
        fake_sink.stop = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_memory",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.register_on_fleet",
                new=AsyncMock(),
            )
            if nats_available
            else contextlib.nullcontext(),
            patch(
                "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
                new=AsyncMock(
                    return_value=MagicMock(
                        snapshot=MagicMock(return_value=[]),
                        close=AsyncMock(),
                        subscribe_updates=AsyncMock(),
                    )
                ),
            )
            if nats_available
            else contextlib.nullcontext(),
            patch(
                "jarvis.infrastructure.lifecycle.heartbeat_loop",
                new=AsyncMock(),
            )
            if nats_available
            else contextlib.nullcontext(),
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
                return_value=MagicMock(
                    start=AsyncMock(),
                    stop=AsyncMock(),
                    bind_session_manager=MagicMock(),
                    bind_notification_sink=MagicMock(),
                ),
            )
            if nats_available
            else contextlib.nullcontext(),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=fake_sink,
            ),
        ):
            state = await build_app_state(config)

        # AC-006: All permutations boot successfully
        assert state.session_manager is not None
        assert state.notification_sink is not None

        # Cleanup
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task


# ---------------------------------------------------------------------------
# AC-002 — assemble_tool_list propagates notification_sink to dispatch module
# ---------------------------------------------------------------------------
class TestAssembleToolListNotificationSinkKwarg:
    """``assemble_tool_list`` snapshots ``notification_sink`` into
    ``jarvis.tools.dispatch._notification_sink``."""

    def test_kwarg_propagates_to_dispatch_module_attribute(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.tools import assemble_tool_list

        fake_sink = MagicMock()

        orig = getattr(_dispatch_module, "_notification_sink", None)
        try:
            assemble_tool_list(
                stub_registry_config,
                [],
                include_frontier=True,
                notification_sink=fake_sink,
            )
            assert _dispatch_module._notification_sink is fake_sink
        finally:
            _dispatch_module._notification_sink = orig

    def test_default_kwarg_clears_dispatch_module_attribute(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.tools import assemble_tool_list

        _dispatch_module._notification_sink = MagicMock()
        try:
            assemble_tool_list(stub_registry_config, [], include_frontier=True)
            assert _dispatch_module._notification_sink is None
        finally:
            _dispatch_module._notification_sink = None

    def test_ambient_call_also_propagates(self, stub_registry_config: JarvisConfig) -> None:
        from jarvis.tools import assemble_tool_list

        fake_sink = MagicMock()
        orig = getattr(_dispatch_module, "_notification_sink", None)
        try:
            assemble_tool_list(
                stub_registry_config,
                [],
                include_frontier=False,
                notification_sink=fake_sink,
            )
            assert _dispatch_module._notification_sink is fake_sink
        finally:
            _dispatch_module._notification_sink = orig


# ---------------------------------------------------------------------------
# AC-003 — shutdown stops the sink idempotently and AFTER the subscriber
# ---------------------------------------------------------------------------
class TestShutdownNotificationSinkOrderAndIdempotency:
    """``shutdown`` calls sink.stop() after subscriber.stop()."""

    def _build_state(self, calls: list[str]) -> tuple[AppState, MagicMock]:
        config = MagicMock(spec=JarvisConfig)
        store = MagicMock()
        store.close = MagicMock(side_effect=lambda: calls.append("store.close"))

        nats_client = MagicMock()
        nats_client.drain = AsyncMock(side_effect=lambda timeout: calls.append("nats.drain"))

        memory_client = MagicMock()
        memory_client.close = AsyncMock(side_effect=lambda: calls.append("memory.close"))

        from jarvis.infrastructure.routing_history import RoutingHistoryWriter

        writer = MagicMock(spec=RoutingHistoryWriter)
        writer.flush = AsyncMock(side_effect=lambda timeout: calls.append("writer.flush"))

        capabilities_registry = MagicMock()
        capabilities_registry.close = AsyncMock(
            side_effect=lambda: calls.append("capabilities.close")
        )

        forge_subscriber = MagicMock()
        forge_subscriber.stop = AsyncMock(side_effect=lambda: calls.append("forge.stop"))

        notification_sink = MagicMock()
        notification_sink.stop = AsyncMock(side_effect=lambda: calls.append("sink.stop"))

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
            memory_client=memory_client,
            routing_history_writer=writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=capabilities_registry,
            forge_subscriber=forge_subscriber,
            notification_sink=notification_sink,
        )
        return state, notification_sink

    @pytest.mark.asyncio
    async def test_sink_stop_called_after_subscriber(self) -> None:
        """AC-003: sink.stop() runs AFTER subscriber.stop()."""
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(side_effect=lambda *a, **kw: calls.append("fleet.deregister")),
        ):
            state, fake_sink = self._build_state(calls)
            await asyncio.sleep(0)
            await shutdown(state)

        # AC-003: sink.stop runs after subscriber.stop and before fleet.deregister
        idx = {name: i for i, name in enumerate(calls)}
        assert "sink.stop" in idx, calls
        assert idx["forge.stop"] < idx["sink.stop"]
        assert idx["sink.stop"] < idx["fleet.deregister"]
        fake_sink.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_double_shutdown_is_idempotent(self) -> None:
        """Calling shutdown twice does not raise — the sink's stop()
        is itself idempotent and the lifecycle's wrapper tolerates it."""
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            state, _fake_sink = self._build_state(calls)
            await asyncio.sleep(0)
            await shutdown(state)
            # Second call must not raise
            await shutdown(state)

    @pytest.mark.asyncio
    async def test_shutdown_continues_when_sink_stop_raises(self) -> None:
        """A sink.stop() exception must not abort the rest of shutdown."""
        from jarvis.infrastructure.lifecycle import shutdown

        calls: list[str] = []
        with patch(
            "jarvis.infrastructure.lifecycle.deregister_from_fleet",
            new=AsyncMock(),
        ):
            state, fake_sink = self._build_state(calls)
            fake_sink.stop = AsyncMock(side_effect=RuntimeError("sink error"))
            await asyncio.sleep(0)
            await shutdown(state)

        # All later steps still ran
        assert "writer.flush" in calls
        assert "nats.drain" in calls
        assert "memory.close" in calls
        assert "store.close" in calls


# ---------------------------------------------------------------------------
# AC-003 — Start ordering: notifier starts before subscriber
# ---------------------------------------------------------------------------
class TestStartupOrdering:
    """The construction order is strict: sink.start → subscriber.bind_notification_sink
    → subscriber.start."""

    @pytest.mark.asyncio
    async def test_sink_start_before_subscriber_start(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_live_registry = MagicMock()
        fake_live_registry.snapshot = MagicMock(return_value=[])
        fake_live_registry.close = AsyncMock()
        fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

        order: list[str] = []

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock(side_effect=lambda: order.append("subscriber.start"))
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock(
            side_effect=lambda s: order.append("bind_sink")
        )
        fake_subscriber.stop = AsyncMock()

        fake_sink = MagicMock()
        fake_sink.start = AsyncMock(side_effect=lambda: order.append("sink.start"))
        fake_sink.stop = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_memory",
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
                "jarvis.infrastructure.lifecycle.SessionManager",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ForgeNotificationsSubscriber",
                return_value=fake_subscriber,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=fake_sink,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        # Strict invariants:
        # 1. sink.start ran before bind_notification_sink
        # 2. bind_notification_sink ran before subscriber.start
        idx = {name: i for i, name in enumerate(order)}
        assert idx["sink.start"] < idx["bind_sink"], order
        assert idx["bind_sink"] < idx["subscriber.start"], order

        # Cleanup
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task


# ---------------------------------------------------------------------------
# AC-008 — Synthetic queued + started + complete sequence produces three
# chat.postMessage calls
# ---------------------------------------------------------------------------
class TestSyntheticNotificationSequence:
    """AC-008: Full wired path from notifications to Slack client."""

    @pytest.mark.asyncio
    async def test_three_events_produce_three_slack_messages(self) -> None:
        """A synthetic queued + started + complete sequence produces exactly
        three chat.postMessage calls on a mocked Slack client."""
        from datetime import UTC, datetime

        from jarvis.infrastructure.forge_notifications import ForgeNotification
        from jarvis.infrastructure.slack_notifier import SlackNotifier

        # Create a mock Slack client that tracks postMessage calls
        mock_slack_client = MagicMock()
        mock_slack_client.chat_postMessage = AsyncMock()

        # Create a real SlackNotifier with the mocked Slack client
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C12345678",
            queue_maxsize=10,
            stop_timeout=1.0,
        )
        # Replace the client with our mock
        notifier._client = mock_slack_client

        # Start the notifier so the worker begins draining the queue
        await notifier.start()

        try:
            # Create three synthetic notifications
            now = datetime.now(UTC)

            notification_queued = ForgeNotification(
                event_type="build_queued",
                correlation_id="corr-123",
                feature_id="FEAT-TEST",
                completed_at=now,
            )

            notification_started = ForgeNotification(
                event_type="build_started",
                correlation_id="corr-123",
                feature_id="FEAT-TEST",
                completed_at=now,
            )

            notification_complete = ForgeNotification(
                event_type="build_complete",
                correlation_id="corr-123",
                feature_id="FEAT-TEST",
                completed_at=now,
                pr_url="https://github.com/test/repo/pull/123",
                summary="Test build completed successfully",
            )

            # Send all three notifications through the notifier
            await notifier.notify(notification_queued)
            await notifier.notify(notification_started)
            await notifier.notify(notification_complete)

            # Give the worker time to drain the queue. The worker paces at
            # ~1 msg/s (TASK-JNB-006 AC-005), so three messages need >2s —
            # poll with a bounded deadline instead of a fixed nap.
            for _ in range(120):
                if mock_slack_client.chat_postMessage.await_count >= 3:
                    break
                await asyncio.sleep(0.05)

            # AC-008: Verify exactly three chat.postMessage calls
            assert mock_slack_client.chat_postMessage.await_count == 3, (
                f"Expected 3 Slack messages, got {mock_slack_client.chat_postMessage.await_count}"
            )

            # Verify the calls were made with correct parameters
            calls = mock_slack_client.chat_postMessage.await_args_list
            assert len(calls) == 3

            # Each call should have channel, text, and mrkdwn=False
            for call in calls:
                kwargs = call.kwargs
                assert kwargs["channel"] == "C12345678"
                assert "text" in kwargs
                assert kwargs["mrkdwn"] is False

        finally:
            # Stop the notifier
            await notifier.stop()
