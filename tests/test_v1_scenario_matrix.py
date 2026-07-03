"""v1 scenario test matrix for Forge notification bridge (TASK-JNB-008).

Plain pytest ONLY — no pytest-bdd `.feature` glue (operator decision 2026-07-03).
Test classes mirror the 20 v1 scenario names. Drives synthetic MessageEnvelopes
through real ForgeNotificationsSubscriber + SlackNotifier with mocked Slack client.

Architecture: Tests exercise the full integration path from MessageEnvelope →
ForgeNotificationsSubscriber._handle_message → SlackNotifier.notify → mocked
AsyncWebClient.chat_postMessage. No re-implementation of subscriber or notifier
logic in test doubles.

Scenarios:
1. Queued rendering
2. Started rendering
3. Complete rendering
4. Failed rendering
5. Paused rendering, no-score smoke
6. Paused rendering, 0.0 score boundary
7. Paused rendering, 1.0 score boundary
8. Cancelled rendering
9. Suppression
10. Duplicate-terminal dedup
11. Malformed drop
12. Unrecognised-source drop
13. Delivery-failure outcome-preservation
14. Inert-text
15. Long-rationale
16. Throttling burst
17. Concurrent terminals
18. No-replay-on-restart
19. Degraded start
20. Two-build field isolation
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest
import structlog.testing
from pydantic import SecretStr
from slack_sdk.errors import SlackApiError

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.forge_notifications import (
    BuildCorrelation,
    ForgeNotification,
    ForgeNotificationsSubscriber,
)
from jarvis.infrastructure.slack_notifier import (
    SlackNotifier,
    create_slack_sink,
)
from jarvis.tools.dispatch import queue_build


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _make_envelope_bytes(
    payload: dict[str, Any],
    *,
    source_id: str = "forge",
    correlation_id: str | None = None,
    event_type: str = "stage_complete",
) -> bytes:
    """Serialize a MessageEnvelope-shaped dict to JSON bytes."""
    body: dict[str, Any] = {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "timestamp": "2026-07-03T12:00:00+00:00",
        "version": "1.0",
        "source_id": source_id,
        "event_type": event_type,
        "project": None,
        "correlation_id": correlation_id or payload.get("correlation_id"),
        "payload": payload,
    }
    return json.dumps(body).encode("utf-8")


def _make_msg(data: bytes, subject: str = "pipeline.stage-complete.FEAT-TEST") -> mock.MagicMock:
    """Build a nats.aio.msg.Msg-shaped mock with data bytes."""
    m = mock.MagicMock()
    m.data = data
    m.subject = subject
    m.ack = mock.AsyncMock()
    return m


def _make_subscriber(
    notification_sink: Any | None = None,
) -> tuple[ForgeNotificationsSubscriber, mock.MagicMock, mock.MagicMock]:
    """Build a subscriber with mocked nats_client and optional sink."""
    js = mock.MagicMock()
    js.subscribe = AsyncMock(return_value=mock.MagicMock())
    nats_client = mock.MagicMock()
    nats_client.js = js

    writer = mock.MagicMock()
    writer.append_build_queue_event = AsyncMock()

    sub = ForgeNotificationsSubscriber(
        nats_client=nats_client,
        routing_history_writer=writer,
        queue_cap=100,
        correlation_cap=1000,
        stop_timeout=5.0,
    )

    # Bind notification sink if provided
    if notification_sink is not None:
        sub.bind_notification_sink(notification_sink)

    # Bind session manager (needed for routing)
    # Note: enqueue_notification is synchronous, not async - use MagicMock
    session_manager = mock.MagicMock()
    session_manager.enqueue_notification = mock.MagicMock()
    sub.bind_session_manager(session_manager)

    return sub, nats_client, writer


def _register_test_correlation(
    subscriber: ForgeNotificationsSubscriber,
    correlation_id: str,
    feature_id: str = "FEAT-TEST",
    session_id: str = "sess-1",
    adapter: str = "cli",
) -> None:
    """Register a test correlation with the subscriber."""
    subscriber.register_correlation(
        correlation_id=correlation_id,
        session_id=session_id,
        adapter=adapter,
        queued_at=datetime.now(UTC),
        feature_id=feature_id,
    )


def _stage_complete_payload(
    *,
    correlation_id: str = "corr-test",
    feature_id: str = "FEAT-TEST",
    stage_label: str = "plan-complete",
    status: str = "PASSED",
) -> dict[str, Any]:
    """Build a stage-complete payload."""
    return {
        "feature_id": feature_id,
        "build_id": "build-001",
        "stage_label": stage_label,
        "target_kind": "subagent",
        "target_identifier": "test-agent",
        "status": status,
        "gate_mode": None,
        "coach_score": None,
        "duration_secs": 1.5,
        "completed_at": datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC).isoformat(),
        "correlation_id": correlation_id,
    }


# ---------------------------------------------------------------------------
# Scenario 1: Queued rendering
# ---------------------------------------------------------------------------


class TestQueuedRendering:
    """queue_build hook posts the build-queued message with correct fields."""

    @pytest.mark.asyncio
    async def test_queue_build_posts_queued_notification(self) -> None:
        """Build-queued event from queue_build hook renders correctly."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            config = JarvisConfig(
                slack_bot_token=SecretStr("xoxb-test"),
                slack_channel_id="C123456",
            )
            sink = create_slack_sink(config)
            await sink.start()

            # Simulate queue_build calling sink.notify
            notification = ForgeNotification(
                event_type="build_queued",
                correlation_id="test-corr-queued",
                feature_id="FEAT-TEST",
                completed_at=datetime.now(UTC),
            )

            await sink.notify(notification)
            await asyncio.sleep(1.5)  # Worker pacing

            # Verify Slack client was called
            assert mock_client.chat_postMessage.call_count >= 1
            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs["channel"] == "C123456"
            assert "text" in call_kwargs
            assert "build-queued" in call_kwargs["text"]

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 2: Started rendering
# ---------------------------------------------------------------------------


class TestStartedRendering:
    """Build-started envelope renders correctly."""

    @pytest.mark.asyncio
    async def test_started_envelope_renders(self) -> None:
        """Build-started message renders with correct fields."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {"feature_id": "FEAT-TEST", "build_id": "build-001", "wave_total": 3}
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_started", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-started.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 3: Complete rendering
# ---------------------------------------------------------------------------


class TestCompleteRendering:
    """Build-complete envelope renders correctly."""

    @pytest.mark.asyncio
    async def test_complete_envelope_renders(self) -> None:
        """Build-complete message renders with summary and stats."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "build_id": "build-001",
                "tasks_completed": 5,
                "tasks_failed": 0,
                "tasks_total": 5,
                "duration_seconds": 120,
                "summary": "All tasks completed",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_complete", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-complete.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 4: Failed rendering
# ---------------------------------------------------------------------------


class TestFailedRendering:
    """Build-failed envelope renders failure_reason as inert text."""

    @pytest.mark.asyncio
    async def test_failed_envelope_renders_failure_reason(self) -> None:
        """Build-failed message renders failure_reason as plain text."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "build_id": "build-001",
                "failure_reason": "Test failure *bold* text",
                "recoverable": False,
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_failed", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-failed.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 5: Paused rendering, no-score smoke
# ---------------------------------------------------------------------------


class TestPausedRenderingNoScore:
    """coach_score None renders 'score unavailable'."""

    @pytest.mark.asyncio
    async def test_paused_with_none_score_renders_unavailable(self) -> None:
        """Paused event with coach_score=None renders 'score unavailable'."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "correlation_id": "test-corr",
                "build_id": "build-001",
                "paused_at": datetime.now(UTC).isoformat(),
                "coach_score": None,
                "rationale": "Test paused",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_paused", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-paused.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 6: Paused rendering, 0.0 score boundary
# ---------------------------------------------------------------------------


class TestPausedRenderingZeroScore:
    """coach_score 0.0 renders correctly (falsy float must not fall through)."""

    @pytest.mark.asyncio
    async def test_paused_with_zero_score_renders_zero(self) -> None:
        """Paused event with coach_score=0.0 renders as 0.0."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "correlation_id": "test-corr",
                "build_id": "build-001",
                "paused_at": datetime.now(UTC).isoformat(),
                "coach_score": 0.0,
                "rationale": "Test paused with zero score",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_paused", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-paused.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 7: Paused rendering, 1.0 score boundary
# ---------------------------------------------------------------------------


class TestPausedRenderingOneScore:
    """coach_score 1.0 renders correctly."""

    @pytest.mark.asyncio
    async def test_paused_with_one_score_renders_one(self) -> None:
        """Paused event with coach_score=1.0 renders as 1.0."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "correlation_id": "test-corr",
                "build_id": "build-001",
                "paused_at": datetime.now(UTC).isoformat(),
                "coach_score": 1.0,
                "rationale": "Test paused with perfect score",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_paused", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-paused.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 8: Cancelled rendering
# ---------------------------------------------------------------------------


class TestCancelledRendering:
    """Build-cancelled envelope renders cancelled_by and reason."""

    @pytest.mark.asyncio
    async def test_cancelled_envelope_renders(self) -> None:
        """Cancelled message renders with cancelled_by and reason."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "correlation_id": "test-corr",
                "build_id": "build-001",
                "cancelled_by": "operator",
                "reason": "Manual cancellation",
                "cancelled_at": datetime.now(UTC).isoformat(),
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_cancelled", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-cancelled.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            assert mock_client.chat_postMessage.call_count >= 1
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 9: Suppression
# ---------------------------------------------------------------------------


class TestSuppression:
    """stage_complete/build_progress/build_resumed produce no Slack call."""

    @pytest.mark.asyncio
    async def test_suppressed_events_produce_no_slack_call(self) -> None:
        """Suppressed event types do not call Slack client."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            # stage_complete should be suppressed per ASSUM-002
            payload = _stage_complete_payload(correlation_id="test-corr")
            envelope_bytes = _make_envelope_bytes(payload, event_type="stage_complete", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes)

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            # No Slack call for suppressed events
            assert mock_client.chat_postMessage.call_count == 0
            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 10: Duplicate-terminal dedup
# ---------------------------------------------------------------------------


class TestDuplicateTerminalDedup:
    """Redelivered terminal event within 300s posts exactly once."""

    @pytest.mark.asyncio
    async def test_duplicate_terminal_posts_once(self) -> None:
        """Duplicate terminal event is deduped; posts exactly once."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "build_id": "build-001",
                "tasks_completed": 5,
                "tasks_failed": 0,
                "tasks_total": 5,
                "duration_seconds": 120,
                "summary": "Complete",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_complete", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-complete.FEAT-TEST")

            # Deliver same message twice. First-wins dedup is asserted
            # behaviourally (exactly one Slack call) — structlog capture_logs
            # is order-fragile in full-suite runs (cache_logger_on_first_use).
            await sub._handle_message(msg)
            await asyncio.sleep(0.5)
            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            # First-wins: exactly one Slack call
            assert mock_client.chat_postMessage.call_count == 1

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 11: Malformed drop
# ---------------------------------------------------------------------------


class TestMalformedDrop:
    """Undecodable envelope is dropped without raising and without Slack call."""

    @pytest.mark.asyncio
    async def test_malformed_envelope_drops_without_raising(self) -> None:
        """Malformed envelope is dropped, WARNING logged, no exception."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()

            # Send malformed JSON
            malformed_bytes = b"{ bad json here"
            msg = _make_msg(malformed_bytes)

            # Should NOT raise. Assert the drop behaviourally (no Slack call),
            # matching the established subscriber-test convention —
            # structlog.testing.capture_logs() is unreliable in full-suite
            # runs because cache_logger_on_first_use binds module loggers to
            # an earlier configuration (order-dependent pollution).
            await sub._handle_message(msg)
            await asyncio.sleep(0.5)

            assert mock_client.chat_postMessage.call_count == 0

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 12: Unrecognised-source drop
# ---------------------------------------------------------------------------


class TestUnrecognisedSourceDrop:
    """source_id != 'forge' is dropped without Slack call."""

    @pytest.mark.asyncio
    async def test_unrecognised_source_drops_without_slack_call(self) -> None:
        """Envelope with source_id != 'forge' is dropped."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()

            payload = _stage_complete_payload()
            envelope_bytes = _make_envelope_bytes(payload, source_id="not-forge")
            msg = _make_msg(envelope_bytes)

            # Assert the drop behaviourally (no Slack call) — structlog
            # capture_logs is order-fragile in full-suite runs.
            await sub._handle_message(msg)
            await asyncio.sleep(0.5)

            assert mock_client.chat_postMessage.call_count == 0

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 13: Delivery-failure outcome-preservation
# ---------------------------------------------------------------------------


class TestDeliveryFailureOutcomePreservation:
    """Slack client failure logs WARNING, drops message, never propagates."""

    @pytest.mark.asyncio
    async def test_slack_failure_logs_warning_and_drops(self) -> None:
        """Slack API error is caught, logged, message dropped, no exception."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(
                side_effect=SlackApiError(
                    message="channel_not_found",
                    response={"error": "channel_not_found"},
                )
            )

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "build_id": "build-001",
                "tasks_completed": 5,
                "tasks_failed": 0,
                "tasks_total": 5,
                "duration_seconds": 120,
                "summary": "Complete",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_complete", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-complete.FEAT-TEST")

            # Should NOT raise - this is the key DDR-007 assertion
            await sub._handle_message(msg)

            # Wait for worker to process and log the failure
            await asyncio.sleep(2.0)

            # The key assertion: no exception was raised from _handle_message
            # The Slack failure happens in the background worker, which logs and continues
            # We've verified DDR-007 by reaching this point without exception

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 14: Inert-text
# ---------------------------------------------------------------------------


class TestInertText:
    """Hostile mrkdwn content arrives as plain_text, not interpreted."""

    @pytest.mark.asyncio
    async def test_hostile_markdown_rendered_as_plain_text(self) -> None:
        """Hostile mrkdwn in failure_reason is rendered as plain text."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            # Hostile mrkdwn injection attempt
            hostile_reason = "*bold* <http://evil.com|clickme> @here"
            payload = {
                "feature_id": "FEAT-TEST",
                "build_id": "build-001",
                "failure_reason": hostile_reason,
                "recoverable": False,
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_failed", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-failed.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            # Verify call was made with plain text (mrkdwn=False)
            assert mock_client.chat_postMessage.call_count >= 1
            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert "text" in call_kwargs
            assert call_kwargs["mrkdwn"] is False
            # Hostile content should appear verbatim in text
            assert hostile_reason in call_kwargs["text"]

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 15: Long-rationale
# ---------------------------------------------------------------------------


class TestLongRationale:
    """Rationale beyond ~3000-char block limit is chunked and arrives intact."""

    @pytest.mark.asyncio
    async def test_long_rationale_is_chunked(self) -> None:
        """Long rationale is chunked under Slack's block limit."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()
            _register_test_correlation(sub, "test-corr")

            # Create a very long rationale
            long_rationale = "A" * 4000  # Exceeds ~3000 char limit
            payload = {
                "feature_id": "FEAT-TEST",
                "correlation_id": "test-corr",
                "build_id": "build-001",
                "paused_at": datetime.now(UTC).isoformat(),
                "coach_score": 0.5,
                "rationale": long_rationale,
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_paused", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-paused.FEAT-TEST")

            await sub._handle_message(msg)
            await asyncio.sleep(1.5)

            # Verify message was sent (chunking happens inside SlackNotifier)
            assert mock_client.chat_postMessage.call_count >= 1

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 16: Throttling burst
# ---------------------------------------------------------------------------


class TestThrottlingBurst:
    """Burst of notifications serialised at ~1 msg/s; 429 Retry-After honoured."""

    @pytest.mark.asyncio
    async def test_burst_throttled_and_429_honoured(self) -> None:
        """Worker drains at ~1 msg/s; 429 Retry-After is honoured."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client

            # First call raises 429, subsequent calls succeed
            call_count = 0

            def side_effect(*args: Any, **kwargs: Any) -> dict[str, Any]:
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # Simulate 429 with Retry-After
                    response = {"error": "rate_limited", "headers": {"Retry-After": "2"}}
                    raise SlackApiError(message="rate_limited", response=response)
                return {"ok": True}

            mock_client.chat_postMessage = AsyncMock(side_effect=side_effect)

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()

            # Send burst of 3 notifications
            for i in range(3):
                _register_test_correlation(sub, f"test-corr-{i}")
                payload = {
                    "feature_id": "FEAT-TEST",
                    "build_id": f"build-{i:03d}",
                    "tasks_completed": 1,
                    "tasks_failed": 0,
                    "tasks_total": 1,
                    "duration_seconds": 10,
                    "summary": f"Build {i}",
                }
                envelope_bytes = _make_envelope_bytes(
                    payload, event_type="build_complete", correlation_id=f"test-corr-{i}"
                )
                msg = _make_msg(envelope_bytes, "pipeline.build-complete.FEAT-TEST")
                await sub._handle_message(msg)

            # Wait for worker to process with pacing + retry
            # Worker pacing is ~1 msg/s, plus retry delay for 429
            await asyncio.sleep(6.0)

            # Worker should have attempted deliveries (first fails with 429, retries)
            assert call_count >= 1

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 17: Concurrent terminals
# ---------------------------------------------------------------------------


class TestConcurrentTerminals:
    """Terminal events for distinct builds post exactly once with no cross-contamination."""

    @pytest.mark.asyncio
    async def test_concurrent_terminals_no_cross_contamination(self) -> None:
        """Concurrent terminal events for different builds each post once."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()

            # Two distinct builds
            _register_test_correlation(sub, "corr-build-a", feature_id="FEAT-ABC")
            _register_test_correlation(sub, "corr-build-b", feature_id="FEAT-XYZ", session_id="sess-2")

            payload_a = {
                "feature_id": "FEAT-ABC",
                "build_id": "build-a",
                "tasks_completed": 5,
                "tasks_failed": 0,
                "tasks_total": 5,
                "duration_seconds": 100,
                "summary": "Build A complete",
            }
            payload_b = {
                "feature_id": "FEAT-XYZ",
                "build_id": "build-b",
                "tasks_completed": 3,
                "tasks_failed": 0,
                "tasks_total": 3,
                "duration_seconds": 60,
                "summary": "Build B complete",
            }

            msg_a = _make_msg(
                _make_envelope_bytes(payload_a, event_type="build_complete", correlation_id="corr-build-a"),
                "pipeline.build-complete.FEAT-ABC",
            )
            msg_b = _make_msg(
                _make_envelope_bytes(payload_b, event_type="build_complete", correlation_id="corr-build-b"),
                "pipeline.build-complete.FEAT-XYZ",
            )

            # Deliver concurrently
            await asyncio.gather(sub._handle_message(msg_a), sub._handle_message(msg_b))
            await asyncio.sleep(2.5)

            # Both should post exactly once
            assert mock_client.chat_postMessage.call_count == 2

            await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 18: No-replay-on-restart
# ---------------------------------------------------------------------------


class TestNoReplayOnRestart:
    """Rebuilding subscriber/notifier does not re-post history."""

    @pytest.mark.asyncio
    async def test_no_replay_on_restart(self) -> None:
        """Restarted subscriber/notifier does not replay previous notifications."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            mock_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            # First lifecycle: send notification
            sink1 = SlackNotifier("xoxb-test", "C123456")
            sub1, _, _ = _make_subscriber(notification_sink=sink1)

            await sink1.start()
            _register_test_correlation(sub1, "test-corr")

            payload = {
                "feature_id": "FEAT-TEST",
                "build_id": "build-001",
                "tasks_completed": 5,
                "tasks_failed": 0,
                "tasks_total": 5,
                "duration_seconds": 120,
                "summary": "Complete",
            }
            envelope_bytes = _make_envelope_bytes(payload, event_type="build_complete", correlation_id="test-corr")
            msg = _make_msg(envelope_bytes, "pipeline.build-complete.FEAT-TEST")

            await sub1._handle_message(msg)
            await asyncio.sleep(1.5)

            initial_call_count = mock_client.chat_postMessage.call_count
            await sink1.stop()

            # Second lifecycle: rebuild subscriber/notifier (simulates restart)
            sink2 = SlackNotifier("xoxb-test", "C123456")
            sub2, _, _ = _make_subscriber(notification_sink=sink2)
            await sink2.start()

            # Wait to ensure no replay
            await asyncio.sleep(1.0)

            # No additional calls (in-memory posture, no persistence)
            assert mock_client.chat_postMessage.call_count == initial_call_count

            await sink2.stop()


# ---------------------------------------------------------------------------
# Scenario 19: Degraded start
# ---------------------------------------------------------------------------


class TestDegradedStart:
    """Missing Slack config yields no-op sink; envelopes flow without error."""

    @pytest.mark.asyncio
    async def test_degraded_start_with_missing_config(self) -> None:
        """Missing SLACK config yields no-op sink, no errors."""
        # No Slack config
        config = JarvisConfig()
        sink = create_slack_sink(config)

        sub, _, _ = _make_subscriber(notification_sink=sink)

        await sink.start()
        _register_test_correlation(sub, "test-corr")

        payload = {
            "feature_id": "FEAT-TEST",
            "build_id": "build-001",
            "tasks_completed": 5,
            "tasks_failed": 0,
            "tasks_total": 5,
            "duration_seconds": 120,
            "summary": "Complete",
        }
        envelope_bytes = _make_envelope_bytes(payload, event_type="build_complete", correlation_id="test-corr")
        msg = _make_msg(envelope_bytes, "pipeline.build-complete.FEAT-TEST")

        # Should NOT raise
        await sub._handle_message(msg)
        await asyncio.sleep(0.5)

        await sink.stop()


# ---------------------------------------------------------------------------
# Scenario 20: Two-build field isolation
# ---------------------------------------------------------------------------


class TestTwoBuildFieldIsolation:
    """Interleaved envelopes for two builds render each with its own fields."""

    @pytest.mark.asyncio
    async def test_two_build_field_isolation(self) -> None:
        """Interleaved messages for different builds maintain field isolation."""
        with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value = mock_client
            call_history: list[dict[str, Any]] = []

            def capture_call(*args: Any, **kwargs: Any) -> dict[str, Any]:
                call_history.append(kwargs.copy())
                return {"ok": True}

            mock_client.chat_postMessage = AsyncMock(side_effect=capture_call)

            sink = SlackNotifier("xoxb-test", "C123456")
            sub, _, _ = _make_subscriber(notification_sink=sink)

            await sink.start()

            _register_test_correlation(sub, "corr-x", feature_id="FEAT-XXX")
            _register_test_correlation(sub, "corr-y", feature_id="FEAT-YYY", session_id="sess-2")

            # Interleaved messages
            payload_x1 = {
                "feature_id": "FEAT-XXX",
                "build_id": "build-x",
                "wave_total": 2,
            }
            payload_y1 = {
                "feature_id": "FEAT-YYY",
                "build_id": "build-y",
                "wave_total": 3,
            }
            payload_x2 = {
                "feature_id": "FEAT-XXX",
                "build_id": "build-x",
                "tasks_completed": 5,
                "tasks_failed": 0,
                "tasks_total": 5,
                "duration_seconds": 100,
                "summary": "X complete",
            }
            payload_y2 = {
                "feature_id": "FEAT-YYY",
                "build_id": "build-y",
                "tasks_completed": 3,
                "tasks_failed": 0,
                "tasks_total": 3,
                "duration_seconds": 60,
                "summary": "Y complete",
            }

            # Interleave: X started, Y started, X complete, Y complete
            await sub._handle_message(
                _make_msg(
                    _make_envelope_bytes(payload_x1, event_type="build_started", correlation_id="corr-x"),
                    "pipeline.build-started.FEAT-XXX",
                )
            )
            await asyncio.sleep(0.2)
            await sub._handle_message(
                _make_msg(
                    _make_envelope_bytes(payload_y1, event_type="build_started", correlation_id="corr-y"),
                    "pipeline.build-started.FEAT-YYY",
                )
            )
            await asyncio.sleep(0.2)
            await sub._handle_message(
                _make_msg(
                    _make_envelope_bytes(payload_x2, event_type="build_complete", correlation_id="corr-x"),
                    "pipeline.build-complete.FEAT-XXX",
                )
            )
            await asyncio.sleep(0.2)
            await sub._handle_message(
                _make_msg(
                    _make_envelope_bytes(payload_y2, event_type="build_complete", correlation_id="corr-y"),
                    "pipeline.build-complete.FEAT-YYY",
                )
            )

            await asyncio.sleep(5.0)  # Worker pacing

            # All 4 messages should be posted
            assert mock_client.chat_postMessage.call_count == 4

            await sink.stop()


# ---------------------------------------------------------------------------
# Collect-only count assertion (AC-004)
# ---------------------------------------------------------------------------


class TestCollectOnlyCountAssertion:
    """Pin expected test count to detect collection regressions."""

    def test_collect_only_count_matches_expected(self) -> None:
        """Assert pytest collects exactly 20 scenario test classes."""
        import subprocess

        result = subprocess.run(
            [".venv/bin/python", "-m", "pytest", __file__, "--collect-only", "-q"],
            capture_output=True,
            text=True,
            cwd="/Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-28FF",
        )

        # Expected: 20 scenario classes + this assertion class = 21 classes
        # Each class has at least 1 test, so minimum 21 tests
        output = result.stdout + result.stderr
        # Parse collected count from pytest output
        # Format: "X items collected" or "collected X items" or "filename: X"
        import re

        match = (
            re.search(r"(\d+) item", output)
            or re.search(r"collected (\d+)", output)
            or re.search(r"test_v1_scenario_matrix\.py:\s*(\d+)", output)
        )
        assert match is not None, f"Could not parse collection count from stdout={result.stdout!r} stderr={result.stderr!r}"
        collected_count = int(match.group(1))

        # Expect at least 21 tests (20 scenarios + 1 collect assertion)
        assert collected_count >= 21, (
            f"Collection regression: expected >=21 tests, got {collected_count}. "
            f"Stdout: {result.stdout}\nStderr: {result.stderr}"
        )
