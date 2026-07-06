"""TASK-JNB-108 — forge-subscriber PIPELINE bind retry on the boot restart race.

A fast restart (``systemctl restart``, ``RestartSec`` crash-loop, deploy)
SIGINTs the old process and starts the successor ~1s later. The predecessor's
ephemeral PIPELINE consumer can still be registered broker-side when the
successor binds; the workqueue stream then rejects the identical lifecycle
filter with ``err_code=10100 'filtered consumer not unique on workqueue
stream'``. Before this task the lifecycle soft-fail (DDR-021) nulled the
subscriber with no retry, leaving every build-lifecycle phone notification
silently dead until a manual restart.

Acceptance criteria (task file AC-5):

* AC-5a — first bind raises 10100, a background retry succeeds → subscriber
  active, ``jarvis_forge_subscriber_started`` emitted, sink receives a
  lifecycle event end-to-end through the freshly-bound consumer.
* AC-5b — all retries raise 10100 → ``jarvis_forge_subscriber_degraded``
  (level=error) emitted, supervisor boot completes anyway.
* AC-5c — non-10100 startup errors keep today's single-shot soft-fail
  (no retry storm on auth / deliver-policy failures).

Plus AC-1 (retry runs as a background task, never blocks boot; the subscriber
stays wired) and the shutdown cancellation that keeps a pending background bind
from outliving teardown.

Every transport seam is patched — no in-process broker. The module-level
``FORGE_SUBSCRIBER_BIND_RETRY_DELAYS_SECONDS`` is monkeypatched to zero-delay
so the background task completes without wall-clock sleeps.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nats.js.errors import BadRequestError
from structlog.testing import capture_logs

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.forge_notifications import ForgeNotificationsSubscriber

LIFECYCLE = "jarvis.infrastructure.lifecycle"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _config() -> JarvisConfig:
    """A ``JarvisConfig`` whose stub-capabilities YAML resolves on disk."""
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists()
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            fleet_memory_enabled=False,
        )
    cfg.validate_provider_keys()
    return cfg


def _overlap_error() -> BadRequestError:
    """The exact JetStream rejection the boot restart race produces."""
    return BadRequestError(
        code=400,
        err_code=10100,
        description="filtered consumer not unique on workqueue stream",
    )


def _events(logs: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """All captured structlog entries whose ``event`` == ``name``."""
    return [entry for entry in logs if entry.get("event") == name]


def _lifecycle_patches(fake_nats: Any, fake_subscriber: Any) -> list[Any]:
    """The seam patches shared by every lifecycle-level test here.

    Mirrors ``test_lifecycle_forge_subscriber_wiring.py`` so the retry
    behaviour is exercised through the real ``build_app_state`` wiring with
    only the transports faked out.
    """
    fake_live_registry = MagicMock()
    fake_live_registry.snapshot = MagicMock(return_value=[])
    fake_live_registry.close = AsyncMock()
    fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

    return [
        patch("sys.stderr", new=io.StringIO()),
        patch(
            "jarvis.infrastructure.lifecycle._connect_nats",
            new=AsyncMock(return_value=fake_nats),
        ),
        patch(
            "jarvis.infrastructure.lifecycle._connect_memory",
            new=AsyncMock(return_value=None),
        ),
        patch("jarvis.infrastructure.lifecycle.register_on_fleet", new=AsyncMock()),
        patch(
            "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
            new=AsyncMock(return_value=fake_live_registry),
        ),
        patch("jarvis.infrastructure.lifecycle.heartbeat_loop", new=AsyncMock()),
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
    ]


@contextlib.contextmanager
def _lifecycle_env(fake_nats: Any, fake_subscriber: Any, *, delays: Any = None) -> Any:
    """Enter every lifecycle seam patch (+ optional retry-delay override) and
    yield the captured structlog entries.

    Parenthesised ``with`` groups cannot ``*``-unpack a list of context
    managers, so the shared patch set is entered through an
    :class:`contextlib.ExitStack` here instead.
    """
    with contextlib.ExitStack() as stack:
        # ``build_app_state`` step 1 calls ``configure()`` →
        # ``structlog.configure()``, which would clobber the processor
        # ``capture_logs`` installs. No-op it so the captured entries survive;
        # the event-emitting production paths (7d block + retry task) are
        # untouched.
        stack.enter_context(
            patch("jarvis.infrastructure.lifecycle.configure", MagicMock())
        )
        if delays is not None:
            stack.enter_context(
                patch(
                    "jarvis.infrastructure.lifecycle."
                    "FORGE_SUBSCRIBER_BIND_RETRY_DELAYS_SECONDS",
                    delays,
                )
            )
        for cm in _lifecycle_patches(fake_nats, fake_subscriber):
            stack.enter_context(cm)
        yield stack.enter_context(capture_logs())


async def _cleanup(state: Any) -> None:
    """Cancel any background tasks the lifecycle scheduled for a test."""
    for task in (state.fleet_heartbeat_task, state.forge_subscriber_retry_task):
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


# ---------------------------------------------------------------------------
# AC-1 / AC-5a — boot race schedules a background retry that recovers
# ---------------------------------------------------------------------------
class TestBootRaceSchedulesRetry:
    @pytest.mark.asyncio
    async def test_first_bind_10100_schedules_retry_and_boot_completes(self) -> None:
        """First bind rejected with 10100 → boot completes, subscriber stays
        wired, a background retry task is scheduled (AC-1)."""
        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_subscriber = MagicMock()
        # Boot bind raises 10100; the background retry then succeeds.
        fake_subscriber.start = AsyncMock(side_effect=[_overlap_error(), None])
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock()

        with _lifecycle_env(fake_nats, fake_subscriber, delays=(0.0,)) as logs:
            from jarvis.infrastructure.lifecycle import build_app_state

            state = await build_app_state(_config())

            # AC-1: boot completed without blocking on the retry.
            assert state.session_manager is not None
            # Subscriber is retained (NOT nulled) so downstream wiring holds.
            assert state.forge_subscriber is fake_subscriber
            fake_subscriber.bind_session_manager.assert_called_once_with(
                state.session_manager
            )
            # A background retry task was scheduled.
            assert state.forge_subscriber_retry_task is not None

            # AC-1 / DDR-021 (non-blocking): at boot-return the retry MUST NOT
            # have run yet — only the synchronous boot attempt fired and the
            # task is still pending. There is no ``await`` between the
            # ``create_task`` and ``return state`` in ``build_app_state``, so a
            # correct implementation is provably here with await_count == 1.
            # A regression that inlined ``await`` on the retry task (blocking
            # supervisor boot for the full ~30s backoff — the exact violation
            # this task exists to prevent) would leave await_count == 2 /
            # task-done at return and trip these two assertions.
            assert fake_subscriber.start.await_count == 1
            assert state.forge_subscriber_retry_task.done() is False

            # Let the background retry run to completion.
            await state.forge_subscriber_retry_task
            await _cleanup(state)

        # The boot-path failure is a transient WARN flagged as scheduled.
        boot_warn = _events(logs, "jarvis_forge_subscriber_start_failed")
        assert any(
            e.get("retry") == "scheduled" and e.get("attempt") == 1 for e in boot_warn
        )
        # start() called twice: boot attempt + one successful retry.
        assert fake_subscriber.start.await_count == 2
        # The retry recovered → started event with the boot-race marker.
        started = _events(logs, "jarvis_forge_subscriber_started")
        assert any(
            e.get("recovered_after_boot_race") is True and e.get("attempt") == 2
            for e in started
        )
        # No degradation — the surface recovered.
        assert _events(logs, "jarvis_forge_subscriber_degraded") == []


# ---------------------------------------------------------------------------
# AC-5a — end-to-end: after the retry binds, a lifecycle event reaches the sink
# ---------------------------------------------------------------------------
class TestEndToEndSinkAfterRetry:
    @pytest.mark.asyncio
    async def test_lifecycle_event_reaches_sink_through_retried_consumer(self) -> None:
        """A real subscriber whose first bind races 10100 delivers a
        build-lifecycle event to the sink once the retry binds (AC-5a)."""
        from jarvis.infrastructure.lifecycle import _retry_forge_subscriber_bind

        captured_cb: dict[str, Any] = {}

        async def _subscribe(*args: Any, **kwargs: Any) -> Any:
            # First bind loses the race; second bind wins and we capture the
            # callback the freshly-bound consumer will deliver through.
            if _subscribe.calls == 0:
                _subscribe.calls += 1
                raise _overlap_error()
            _subscribe.calls += 1
            captured_cb["cb"] = kwargs["cb"]
            return MagicMock()

        _subscribe.calls = 0

        js = MagicMock()
        js.subscribe = AsyncMock(side_effect=_subscribe)
        nats_client = MagicMock()
        nats_client.js = js

        writer = MagicMock()
        writer.append_build_queue_event = AsyncMock()

        subscriber = ForgeNotificationsSubscriber(
            nats_client=nats_client,
            routing_history_writer=writer,
        )
        sink = MagicMock()
        sink.notify = AsyncMock()
        subscriber.bind_notification_sink(sink)
        subscriber.bind_session_manager(MagicMock())

        # Boot-path bind loses the race.
        with pytest.raises(BadRequestError):
            await subscriber.start()

        # Background retry wins on the next attempt.
        await _retry_forge_subscriber_bind(
            subscriber,
            delays=(0.0,),
            queue_cap=100,
            correlation_cap=1000,
        )
        assert js.subscribe.await_count == 2
        assert subscriber._started is True

        # Drive a build-lifecycle envelope through the consumer the retry bound.
        cb = captured_cb["cb"]
        envelope = {
            "message_id": "11111111-1111-1111-1111-111111111111",
            "timestamp": "2026-07-06T15:13:47+00:00",
            "version": "1.0",
            "source_id": "forge",
            "event_type": "build_started",
            "project": None,
            "correlation_id": "corr-jnb108",
            "payload": {
                "feature_id": "FEAT-J108",
                "build_id": "build-jnb108",
                "wave_total": 3,
            },
        }
        msg = MagicMock()
        msg.data = json.dumps(envelope).encode("utf-8")
        msg.ack = AsyncMock()

        await cb(msg)

        # Sink received the lifecycle event end-to-end (correlation-independent
        # fan-out fires even without a registered correlation).
        sink.notify.assert_awaited_once()
        delivered = sink.notify.await_args.args[0]
        assert delivered.event_type == "build_started"
        assert delivered.feature_id == "FEAT-J108"


# ---------------------------------------------------------------------------
# AC-5b — all retries exhausted → loud terminal degradation, boot still up
# ---------------------------------------------------------------------------
class TestRetryExhaustedDegrades:
    @pytest.mark.asyncio
    async def test_all_retries_10100_emit_degraded_and_boot_completes(self) -> None:
        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock(side_effect=_overlap_error())
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock()

        with _lifecycle_env(fake_nats, fake_subscriber, delays=(0.0, 0.0)) as logs:
            from jarvis.infrastructure.lifecycle import build_app_state

            state = await build_app_state(_config())

            # AC-5b: supervisor boot completes anyway.
            assert state.session_manager is not None
            assert state.forge_subscriber_retry_task is not None

            # AC-1 / DDR-021 (non-blocking): the background retries have NOT
            # run at boot-return time — only the synchronous boot attempt.
            assert fake_subscriber.start.await_count == 1
            assert state.forge_subscriber_retry_task.done() is False

            await state.forge_subscriber_retry_task
            await _cleanup(state)

        # Loud terminal degradation at ERROR level naming the consequence.
        degraded = _events(logs, "jarvis_forge_subscriber_degraded")
        assert len(degraded) == 1
        entry = degraded[0]
        assert entry["log_level"] == "error"
        assert entry["reason"] == "pipeline_bind_retries_exhausted"
        assert "OFF until restart" in entry["consequence"]
        # boot attempt (1) + two background retries (delays len 2) = 3 binds.
        assert fake_subscriber.start.await_count == 3
        # Never claimed success.
        assert _events(logs, "jarvis_forge_subscriber_started") == []


# ---------------------------------------------------------------------------
# AC-2 — a NON-10100 error appearing mid-retry degrades loudly (no storm)
# ---------------------------------------------------------------------------
class TestNonOverlapErrorDuringRetry:
    """The boot bind raced 10100 (retry scheduled), but a *later* attempt
    hits a different failure (broker gone / auth / 10101). The retry stops —
    no storm — and degrades loudly with a distinct reason (AC-2/AC-5c)."""

    @pytest.mark.asyncio
    async def test_non_overlap_error_mid_retry_degrades_without_storm(self) -> None:
        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_subscriber = MagicMock()
        # Boot bind races 10100 → retry scheduled; the first retry then hits a
        # *different*, permanent failure.
        fake_subscriber.start = AsyncMock(
            side_effect=[_overlap_error(), RuntimeError("nats: broker gone")]
        )
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock()

        # Two delays available, but the mid-retry non-overlap error must stop
        # after the first retry — proving there is no storm.
        with _lifecycle_env(fake_nats, fake_subscriber, delays=(0.0, 0.0)) as logs:
            from jarvis.infrastructure.lifecycle import build_app_state

            state = await build_app_state(_config())
            assert state.session_manager is not None  # boot completed
            await state.forge_subscriber_retry_task
            await _cleanup(state)

        # Stopped after boot attempt + exactly one retry (no storm through the
        # second available delay).
        assert fake_subscriber.start.await_count == 2
        # Exactly one degraded event, at ERROR, with the mid-retry reason —
        # NOT the exhaustion reason.
        degraded = _events(logs, "jarvis_forge_subscriber_degraded")
        assert len(degraded) == 1
        assert degraded[0]["log_level"] == "error"
        assert degraded[0]["reason"] == "non_overlap_error_during_retry"
        assert "OFF until restart" in degraded[0]["consequence"]
        # Never claimed success, never reported exhaustion.
        assert _events(logs, "jarvis_forge_subscriber_started") == []
        assert all(
            e.get("reason") != "pipeline_bind_retries_exhausted" for e in degraded
        )


# ---------------------------------------------------------------------------
# AC-5c — non-10100 startup errors keep the single-shot soft-fail
# ---------------------------------------------------------------------------
class TestNon10100SingleShot:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc",
        [
            RuntimeError("nats: authorization violation"),
            BadRequestError(
                code=400,
                err_code=10101,
                description="consumer must be deliver all on workqueue stream",
            ),
        ],
        ids=["auth_failure", "deliver_policy_10101"],
    )
    async def test_non_overlap_error_single_shot_softfail(
        self, exc: Exception
    ) -> None:
        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_subscriber = MagicMock()
        fake_subscriber.start = AsyncMock(side_effect=exc)
        fake_subscriber.stop = AsyncMock()
        fake_subscriber.bind_session_manager = MagicMock()
        fake_subscriber.bind_notification_sink = MagicMock()

        with _lifecycle_env(fake_nats, fake_subscriber) as logs:
            from jarvis.infrastructure.lifecycle import build_app_state

            state = await build_app_state(_config())
            await _cleanup(state)

        # Today's behaviour: subscriber nulled, no retry task, no storm.
        assert state.forge_subscriber is None
        assert state.forge_subscriber_retry_task is None
        assert fake_subscriber.start.await_count == 1
        # A single-shot soft-fail WARN with no retry marker.
        warns = _events(logs, "jarvis_forge_subscriber_start_failed")
        assert len(warns) == 1
        assert "retry" not in warns[0]
        # Never escalates to the degraded surface.
        assert _events(logs, "jarvis_forge_subscriber_degraded") == []


# ---------------------------------------------------------------------------
# Shutdown — a pending retry task is cancelled before the subscriber stops
# ---------------------------------------------------------------------------
class TestShutdownCancelsRetryTask:
    @pytest.mark.asyncio
    async def test_shutdown_cancels_pending_retry_task(self) -> None:
        from jarvis.infrastructure.lifecycle import AppState, shutdown

        started = asyncio.Event()

        async def _never_binds() -> None:
            started.set()
            await asyncio.sleep(3600)

        retry_task = asyncio.create_task(_never_binds())
        await started.wait()

        forge_subscriber = MagicMock()
        forge_subscriber.stop = AsyncMock()

        store = MagicMock()
        store.close = MagicMock()

        state = AppState(
            config=MagicMock(spec=JarvisConfig),
            supervisor=MagicMock(),
            store=store,
            session_manager=MagicMock(),
            forge_subscriber=forge_subscriber,
            forge_subscriber_retry_task=retry_task,
        )

        with patch("sys.stderr", new=io.StringIO()):
            await shutdown(state)

        # The pending background bind was cancelled …
        assert retry_task.cancelled()
        # … and the subscriber stop path still ran (cancel precedes stop).
        forge_subscriber.stop.assert_awaited_once()
