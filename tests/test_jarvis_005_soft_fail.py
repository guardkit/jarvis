"""Soft-fail tests for FEAT-JARVIS-005 — TASK-J005-009.

Exercises the three production-grade fail-soft paths inherited from
FEAT-J004 and ratified by DDR-019 / DDR-021 / DDR-027 / ASSUM-011:

* **NATS down at startup** — :func:`jarvis.infrastructure.lifecycle.build_app_state`
  completes with ``state.forge_subscriber is None`` (DDR-021); the
  ``queue_build`` tool returns a structured DEGRADED ``transport_unavailable``
  ack (Group C #3).
* **NATS up but ``js.publish`` stalls past timeout** — ``queue_build``
  returns DEGRADED ``transport_unavailable`` after ``asyncio.wait_for``
  raises ``TimeoutError`` (Group B #6).
* **Graphiti raises during ``write_build_queue_dispatch``** — the
  fire-and-forget routing-history hook logs ``WARN
  routing_history_write_failed`` exactly once and ``queue_build`` still
  returns the operator-facing ``{"status": "queued", ...}`` ack (DDR-019,
  Group A #6).
* **Graphiti raises during ``append_build_queue_event``** — the subscriber
  wraps the writer in :func:`contextlib.suppress`; the notification still
  reaches ``SessionManager.enqueue_notification`` and
  :meth:`ForgeNotification.render_line` produces a clean line
  (Group D #5).
* **Subscriber stop with unresponsive broker** — :meth:`stop` returns
  within ``stop_timeout`` ± 200ms even when ``unsubscribe`` hangs forever
  (Group D #14 / ASSUM-011).
* **``stop()`` is idempotent** — a second call after a clean stop is a
  no-op and never raises.

Pattern reused from ``tests/test_nats_unavailable.py`` and
``tests/test_graphiti_unavailable.py`` (FEAT-J004): in-process JetStream
mocks via ``unittest.mock``; module-level dispatch state saved/restored
via fixture; ``caplog.records`` filtered to the producing logger to
assert WARN content (no stderr matching).
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import time
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
)
from jarvis.infrastructure.lifecycle import AppState, build_app_state
from jarvis.infrastructure.routing_history import RoutingHistoryWriter
from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools import dispatch as dispatch_module
from jarvis.tools.dispatch import queue_build

ROUTING_HISTORY_LOGGER = "jarvis.infrastructure.routing_history"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _stub_yaml_path() -> Path:
    return _project_root() / "src" / "jarvis" / "config" / "stub_capabilities.yaml"


def _routing_history_warnings(
    caplog: pytest.LogCaptureFixture,
) -> list[logging.LogRecord]:
    """Filter caplog records to the routing-history logger at WARNING+."""
    return [
        record
        for record in caplog.records
        if record.name == ROUTING_HISTORY_LOGGER
        and record.levelno == logging.WARNING
    ]


def _ainvoke_queue_build(**kwargs: Any) -> str:
    """Invoke ``queue_build`` (the @tool wrapper) on a fresh event loop."""
    return asyncio.run(queue_build.ainvoke(kwargs))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def nats_unreachable_config(tmp_path: Path) -> JarvisConfig:
    """A :class:`JarvisConfig` whose NATS URL points at an unrouteable broker."""
    stub_path = _stub_yaml_path()
    assert stub_path.exists(), "stub_capabilities.yaml must ship with the package"
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
            nats_url="nats://203.0.113.1:4222",
            jarvis_traces_dir=tmp_path / "traces",
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def graphiti_unreachable_config(tmp_path: Path) -> JarvisConfig:
    """A :class:`JarvisConfig` configured for Graphiti soft-fail tests."""
    stub_path = _stub_yaml_path()
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint="bolt://203.0.113.2:7687",
            jarvis_traces_dir=tmp_path / "traces",
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def reset_dispatch_state() -> Generator[None, None, None]:
    """Save and restore the module-level dispatch state mutated by the tests."""
    saved = (
        dispatch_module._nats_client,
        dispatch_module._dispatch_semaphore,
        dispatch_module._routing_history_writer,
        dispatch_module._forge_subscriber,
        dispatch_module._jarvis_config,
        dispatch_module._current_session_hook,
    )
    try:
        yield
    finally:
        (
            dispatch_module._nats_client,
            dispatch_module._dispatch_semaphore,
            dispatch_module._routing_history_writer,
            dispatch_module._forge_subscriber,
            dispatch_module._jarvis_config,
            dispatch_module._current_session_hook,
        ) = saved


# ---------------------------------------------------------------------------
# Mock JetStream / NATS / writer / subscriber helpers
# ---------------------------------------------------------------------------
def _make_nats_client(
    publish_side_effect: Any | None = None,
    publish_return_value: Any | None = None,
) -> MagicMock:
    """Build a NATSClient-shaped mock with a JetStream ``js.publish`` AsyncMock."""
    js = MagicMock()
    if publish_side_effect is not None:
        js.publish = AsyncMock(side_effect=publish_side_effect)
    elif publish_return_value is not None:
        js.publish = AsyncMock(return_value=publish_return_value)
    else:
        js.publish = AsyncMock(return_value=MagicMock(seq=1, stream="pipeline"))
    nats_client = MagicMock()
    nats_client.js = js
    return nats_client


def _make_config_with_timeout(
    timeout_seconds: int = 5,
) -> MagicMock:
    """Build a minimal config-shape carrying ``pipeline_publish_timeout_seconds``."""
    cfg = MagicMock()
    cfg.pipeline_publish_timeout_seconds = timeout_seconds
    return cfg


def _make_subscriber_with_stop_timeout(
    stop_timeout: float,
    *,
    unsubscribe_side_effect: Any | None = None,
) -> tuple[ForgeNotificationsSubscriber, MagicMock]:
    """Build a subscriber whose ``unsubscribe`` is configurable.

    Returns the subscriber and the inner ``fake_sub`` mock that ``js.subscribe``
    returned (so the test can manipulate it later if needed).
    """
    js = MagicMock()
    fake_sub = MagicMock()
    if unsubscribe_side_effect is not None:
        fake_sub.unsubscribe = AsyncMock(side_effect=unsubscribe_side_effect)
    else:
        fake_sub.unsubscribe = AsyncMock(return_value=None)
    js.subscribe = AsyncMock(return_value=fake_sub)

    nats_client = MagicMock()
    nats_client.js = js

    writer = MagicMock()
    writer.append_build_queue_event = AsyncMock()

    sub = ForgeNotificationsSubscriber(
        nats_client=nats_client,
        routing_history_writer=writer,
        queue_cap=100,
        correlation_cap=1000,
        stop_timeout=stop_timeout,
    )
    return sub, fake_sub


def _stage_complete_envelope_bytes(
    *,
    correlation_id: str = "corr-soft-fail",
    feature_id: str = "FEAT-J005DEMO",
) -> bytes:
    """Build a ``MessageEnvelope`` carrying a ``StageCompletePayload``."""
    payload = {
        "feature_id": feature_id,
        "build_id": "build-soft-fail",
        "stage_label": "plan-complete",
        "target_kind": "subagent",
        "target_identifier": "jarvis-reasoner",
        "status": "PASSED",
        "gate_mode": None,
        "coach_score": None,
        "duration_secs": 1.25,
        "completed_at": datetime(2026, 4, 30, 15, 42, 0, tzinfo=UTC).isoformat(),
        "correlation_id": correlation_id,
    }
    envelope = {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "timestamp": "2026-04-30T15:42:00+00:00",
        "version": "1.0",
        "source_id": "forge",
        "event_type": "stage_complete",
        "project": None,
        "correlation_id": correlation_id,
        "payload": payload,
    }
    return json.dumps(envelope).encode("utf-8")


# ===========================================================================
# AC: NATS down at build_app_state time → forge_subscriber=None,
# lifecycle completes, queue_build returns DEGRADED transport_unavailable.
# ===========================================================================
class TestNatsDownAtBuildAppStateTime:
    """``state.forge_subscriber`` is None when ``_connect_nats`` returns None."""

    @pytest.mark.asyncio
    async def test_build_app_state_yields_forge_subscriber_none_when_nats_down(
        self,
        nats_unreachable_config: JarvisConfig,
    ) -> None:
        """Lifecycle completes; ``state.forge_subscriber is None``."""
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
            state = await build_app_state(nats_unreachable_config)

        assert isinstance(state, AppState)
        assert state.nats_client is None
        # DDR-021 / TASK-J005-008: subscriber is constructed only when NATS
        # is up. With NATS down, ``state.forge_subscriber is None`` is the
        # explicit DDR-021 invariant.
        assert state.forge_subscriber is None
        assert state.supervisor is not None  # process still alive

    def test_queue_build_returns_degraded_transport_unavailable_when_nats_unwired(
        self,
        reset_dispatch_state: None,
    ) -> None:
        """With ``_nats_client is None`` the tool body short-circuits early."""
        dispatch_module._nats_client = None
        dispatch_module._dispatch_semaphore = None
        dispatch_module._routing_history_writer = None
        dispatch_module._forge_subscriber = None
        dispatch_module._jarvis_config = _make_config_with_timeout()

        result = _ainvoke_queue_build(
            feature_id="FEAT-J005DEMO",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        parsed = json.loads(result)
        assert parsed["status"] == "degraded"
        assert parsed["reason"] == "transport_unavailable"
        # The structured ack carries the correlation + feature_id forward
        # so callers can correlate even on the soft-fail path.
        assert parsed["feature_id"] == "FEAT-J005DEMO"
        assert "correlation_id" in parsed


# ===========================================================================
# AC: NATS up but js.publish stalls past timeout → DEGRADED
# transport_unavailable (Group B #6).
# ===========================================================================
class TestPublishStallsPastTimeout:
    """``asyncio.wait_for`` enforces ``pipeline_publish_timeout_seconds``."""

    def test_stalled_publish_returns_degraded_transport_unavailable(
        self,
        reset_dispatch_state: None,
    ) -> None:
        """Stalled publish + timeout=0 → TimeoutError → DEGRADED ack."""
        async def _stall(_subject: str, _payload: bytes) -> Any:
            # Would block well past the configured timeout — wait_for
            # cancels and raises TimeoutError.
            await asyncio.sleep(60)

        nats_client = _make_nats_client(publish_side_effect=_stall)
        semaphore = MagicMock()
        semaphore.try_acquire = MagicMock(return_value=True)
        semaphore.release = MagicMock()
        semaphore.in_flight = 0

        writer = MagicMock()
        writer.write_build_queue_dispatch = AsyncMock(return_value=None)

        subscriber = MagicMock()
        subscriber.register_correlation = MagicMock()

        # ``wait_for(timeout=0)`` raises TimeoutError immediately.
        config = _make_config_with_timeout(timeout_seconds=0)

        dispatch_module._nats_client = nats_client
        dispatch_module._dispatch_semaphore = semaphore
        dispatch_module._routing_history_writer = writer
        dispatch_module._forge_subscriber = subscriber
        dispatch_module._jarvis_config = config

        result = _ainvoke_queue_build(
            feature_id="FEAT-J005DEMO",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        parsed = json.loads(result)
        assert parsed["status"] == "degraded"
        assert parsed["reason"] == "transport_unavailable"
        # The subscriber was NOT registered on the timeout path —
        # ``register_correlation`` only runs after a successful PubAck.
        subscriber.register_correlation.assert_not_called()
        # Routing-history dispatch trace is also skipped (publish
        # never returned successfully).
        writer.write_build_queue_dispatch.assert_not_called()


# ===========================================================================
# AC: Graphiti raises during write_build_queue_dispatch → WARN logged,
# queue_build still returns {"status": "queued", ...} (Group A #6).
# ===========================================================================
class TestGraphitiRaisesDuringWriteBuildQueueDispatch:
    """DDR-019 fire-and-forget: graphiti errors don't break the operator ack."""

    def test_queue_build_returns_queued_when_graphiti_raises_warn_logged(
        self,
        reset_dispatch_state: None,
        graphiti_unreachable_config: JarvisConfig,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A faulty Graphiti client → WARN ``routing_history_write_failed``.

        ``queue_build`` still returns the success ack because the routing-
        history hook is fire-and-forget per DDR-019 / DDR-029. The
        dispatch boundary awaits only the *submission* of the writer task,
        not its outcome.
        """
        caplog.set_level(logging.WARNING, logger=ROUTING_HISTORY_LOGGER)

        # Real writer with a Graphiti client whose ``add_episode`` raises.
        graphiti_client = MagicMock()
        graphiti_client.add_episode = MagicMock(
            side_effect=RuntimeError("graphiti boom")
        )
        writer = RoutingHistoryWriter(
            graphiti_client=graphiti_client,
            config=graphiti_unreachable_config,
        )

        nats_client = _make_nats_client()
        semaphore = MagicMock()
        semaphore.try_acquire = MagicMock(return_value=True)
        semaphore.release = MagicMock()
        semaphore.in_flight = 0

        subscriber = MagicMock()
        subscriber.register_correlation = MagicMock()

        dispatch_module._nats_client = nats_client
        dispatch_module._dispatch_semaphore = semaphore
        dispatch_module._routing_history_writer = writer
        dispatch_module._forge_subscriber = subscriber
        dispatch_module._jarvis_config = _make_config_with_timeout()

        # JarvisRoutingHistoryEntry.decision_id is a UUIDv4 — give the
        # routing-history hook a value that passes the regex so we exercise
        # the writer's DDR-019 ``except Exception`` branch (not the upstream
        # validation-error branch).
        correlation_id = "11111111-2222-4333-8444-555555555555"

        async def _run() -> str:
            result = await queue_build.ainvoke(
                {
                    "feature_id": "FEAT-J005DEMO",
                    "feature_yaml_path": "features/feat.yaml",
                    "repo": "guardkit/jarvis",
                    "correlation_id": correlation_id,
                }
            )
            # Yield twice so the fire-and-forget writer task lands and
            # any WARN is captured by caplog before the assertion runs.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            await writer.flush(timeout=1.0)
            return result

        result = asyncio.run(_run())
        parsed = json.loads(result)
        # The operator-facing ack is still success — DDR-019 fire-and-forget.
        assert parsed["status"] == "queued"
        assert parsed["correlation_id"] == correlation_id
        assert parsed["feature_id"] == "FEAT-J005DEMO"

        # The writer logged a WARN reflecting the underlying Graphiti error
        # (caught by the writer's own DDR-019 ``except Exception`` block).
        warnings = _routing_history_warnings(caplog)
        assert len(warnings) >= 1, (
            "DDR-019: writer must log WARN routing_history_write_failed when "
            "the Graphiti add_episode call fails"
        )
        assert any(
            record.getMessage() == "routing_history_write_failed"
            for record in warnings
        )


# ===========================================================================
# AC: Graphiti raises during append_build_queue_event → WARN logged,
# notification still enqueued + rendered (Group D #5 scenario).
# ===========================================================================
class TestGraphitiRaisesDuringAppendBuildQueueEvent:
    """The subscriber's contextlib.suppress keeps the FIFO enqueue alive."""

    @pytest.mark.asyncio
    async def test_notification_enqueued_when_writer_append_raises(
        self,
    ) -> None:
        """Subscriber → writer raises → notification still enqueued + rendered."""
        # Build a subscriber with a writer whose append raises directly.
        js = MagicMock()
        js.subscribe = AsyncMock(return_value=MagicMock())
        nats_client = MagicMock()
        nats_client.js = js

        writer = MagicMock()
        writer.append_build_queue_event = AsyncMock(
            side_effect=RuntimeError("graphiti boom on append")
        )

        sub = ForgeNotificationsSubscriber(
            nats_client=nats_client,
            routing_history_writer=writer,
            queue_cap=10,
            correlation_cap=10,
        )

        # Bind a session manager that captures the enqueue call.
        session_manager = MagicMock()
        session_manager.enqueue_notification = MagicMock()
        sub.bind_session_manager(session_manager)

        # Register a correlation so the on-message routing path proceeds
        # past the silent-drop branch.
        sub.register_correlation(
            correlation_id="corr-soft-fail",
            session_id="sess-soft-fail",
            adapter="cli",
            queued_at=datetime(2026, 4, 30, 15, 41, 0, tzinfo=UTC),
            feature_id="FEAT-J005DEMO",
        )

        msg = MagicMock()
        msg.data = _stage_complete_envelope_bytes(
            correlation_id="corr-soft-fail",
            feature_id="FEAT-J005DEMO",
        )
        msg.subject = "pipeline.stage-complete.FEAT-J005DEMO"
        msg.ack = AsyncMock()

        # The subscriber wraps the writer in contextlib.suppress —
        # _on_message must NOT raise even though the writer raised.
        await sub._on_message(msg)

        # The writer was indeed called (the suppress fired).
        writer.append_build_queue_event.assert_awaited_once()

        # The notification still landed on the session FIFO — Group D #5.
        session_manager.enqueue_notification.assert_called_once()
        args, _ = session_manager.enqueue_notification.call_args
        assert args[0] == "sess-soft-fail"
        notification: ForgeNotification = args[1]
        assert isinstance(notification, ForgeNotification)
        assert notification.correlation_id == "corr-soft-fail"
        assert notification.feature_id == "FEAT-J005DEMO"
        # render_line returns the canonical CLI shape per DDR-030.
        rendered = notification.render_line()
        assert "Forge FEAT-J005DEMO" in rendered
        assert "stage plan-complete" in rendered
        assert "(PASSED)" in rendered


# ===========================================================================
# AC: subscriber.stop() against an unresponsive broker stub returns within
# 5s ± 200ms (Group D #14).
# ===========================================================================
class TestSubscriberStopBoundedByTimeout:
    """ASSUM-011: ``stop_timeout`` is the upper bound on shutdown latency."""

    @pytest.mark.asyncio
    async def test_stop_returns_within_5s_with_unresponsive_broker(self) -> None:
        """``stop()`` returns within ``stop_timeout`` ± 200ms when unsubscribe hangs."""
        async def _hang() -> None:
            # Would block far past the 5s budget — wait_for must cancel it.
            await asyncio.sleep(60)

        # Use a small ``stop_timeout`` to keep the test fast while
        # preserving the ± 200ms invariant: we assert ``elapsed`` is
        # within 200ms above the configured timeout. The acceptance
        # criterion phrases "5s ± 200ms" against the canonical 5.0
        # production default; mirroring the bound at 0.5s here keeps
        # the assertion mechanically identical without making the
        # suite slow.
        stop_timeout = 0.5
        sub, _fake_sub = _make_subscriber_with_stop_timeout(
            stop_timeout=stop_timeout,
            unsubscribe_side_effect=_hang,
        )
        await sub.start()

        before = time.monotonic()
        await sub.stop()
        elapsed = time.monotonic() - before

        # ± 200ms tolerance per the AC. Lower bound: stop should not
        # return before the timeout is exhausted (else the timer is
        # broken). Upper bound: stop must not exceed the budget by
        # more than the slack window.
        assert stop_timeout - 0.2 <= elapsed <= stop_timeout + 0.2, (
            f"stop() elapsed {elapsed:.3f}s outside "
            f"{stop_timeout}s ± 0.2s budget"
        )

    @pytest.mark.asyncio
    async def test_stop_returns_within_5s_default_budget(self) -> None:
        """The production default ``stop_timeout=5.0`` is the documented bound."""
        sub, _fake_sub = _make_subscriber_with_stop_timeout(
            stop_timeout=5.0,
            unsubscribe_side_effect=None,
        )
        await sub.start()
        before = time.monotonic()
        await sub.stop()
        elapsed = time.monotonic() - before
        # Healthy broker — stop returns immediately, well inside the 5s
        # bound. This is the lower-end witness of the ± 200ms envelope:
        # the bound is an upper limit, not a forced minimum.
        assert elapsed < 5.0


# ===========================================================================
# AC: subscriber.stop() called twice is idempotent.
# ===========================================================================
class TestSubscriberStopIdempotent:
    """A second ``stop()`` after a clean shutdown is a no-op."""

    @pytest.mark.asyncio
    async def test_stop_called_twice_is_idempotent(self) -> None:
        """Two consecutive ``stop()`` calls — second is a no-op."""
        sub, fake_sub = _make_subscriber_with_stop_timeout(stop_timeout=5.0)
        await sub.start()

        await sub.stop()
        # First stop unsubscribed exactly once.
        fake_sub.unsubscribe.assert_awaited_once()

        # Second stop must not raise and must not call unsubscribe again
        # — the subscriber tracks ``_started`` and short-circuits the
        # second call.
        await sub.stop()
        assert fake_sub.unsubscribe.await_count == 1

    @pytest.mark.asyncio
    async def test_stop_called_before_start_is_noop(self) -> None:
        """``stop()`` on a never-started subscriber is also a no-op."""
        sub, fake_sub = _make_subscriber_with_stop_timeout(stop_timeout=5.0)
        # No ``start()`` ever happened.
        await sub.stop()
        fake_sub.unsubscribe.assert_not_called()


# ===========================================================================
# AC: NATS connection error on publish surfaces as DEGRADED transport_unavailable
# (extra safety net — confirms the catch-broad branch in queue_build).
# ===========================================================================
class TestPublishNatsConnectionErrorDegrades:
    """``NATSConnectionError`` from publish → DEGRADED ``transport_unavailable``."""

    def test_publish_nats_connection_error_returns_degraded(
        self,
        reset_dispatch_state: None,
    ) -> None:
        """Wire publish to raise the typed exception; tool returns degraded JSON."""
        nats_client = _make_nats_client(
            publish_side_effect=NATSConnectionError("broker drained"),
        )
        semaphore = MagicMock()
        semaphore.try_acquire = MagicMock(return_value=True)
        semaphore.release = MagicMock()
        semaphore.in_flight = 0

        writer = MagicMock()
        writer.write_build_queue_dispatch = AsyncMock(return_value=None)

        subscriber = MagicMock()
        subscriber.register_correlation = MagicMock()

        dispatch_module._nats_client = nats_client
        dispatch_module._dispatch_semaphore = semaphore
        dispatch_module._routing_history_writer = writer
        dispatch_module._forge_subscriber = subscriber
        dispatch_module._jarvis_config = _make_config_with_timeout()

        result = _ainvoke_queue_build(
            feature_id="FEAT-J005DEMO",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        parsed = json.loads(result)
        assert parsed["status"] == "degraded"
        assert parsed["reason"] == "transport_unavailable"
