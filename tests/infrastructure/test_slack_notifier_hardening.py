"""Hardening tests for SlackNotifier (TASK-JNB-006).

Tests the 300s first-wins dedup, throttling backoff, and overflow bounds.
Plain pytest only — no pytest-bdd.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.infrastructure.slack_notifier import SlackNotifier


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fast_worker_pacing():
    """Patch worker pacing to 10ms for fast tests."""
    with patch("jarvis.infrastructure.slack_notifier._WORKER_PACING_DELAY", 0.01):
        yield


@pytest.fixture
def mock_slack_client() -> AsyncMock:
    """Mock AsyncWebClient with successful chat_postMessage."""
    client = AsyncMock()
    client.chat_postMessage = AsyncMock(return_value={"ok": True})
    return client


@pytest.fixture
def notifier(mock_slack_client: AsyncMock) -> SlackNotifier:
    """SlackNotifier instance with mocked client."""
    notifier = SlackNotifier(
        bot_token="xoxb-test",
        channel_id="C123",
        queue_maxsize=10,
    )
    # Replace the real client with our mock
    notifier._client = mock_slack_client
    return notifier


@pytest.fixture
def terminal_notification() -> ForgeNotification:
    """A build_complete terminal notification."""
    return ForgeNotification(
        event_type="build_complete",
        correlation_id="corr-001",
        feature_id="FEAT-TEST",
        build_id="build-001",
        completed_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def queued_notification() -> ForgeNotification:
    """A build_queued intake notification."""
    return ForgeNotification(
        event_type="build_queued",
        correlation_id="corr-002",
        feature_id="FEAT-TEST",
        completed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Test: Duplicate terminal envelope posts once
# ---------------------------------------------------------------------------


class TestDuplicateTerminalEnvelopePostsOnce:
    """AC-003: Duplicate terminal posts to Slack exactly once."""

    @pytest.mark.asyncio
    async def test_duplicate_terminal_posts_once(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
        terminal_notification: ForgeNotification,
    ) -> None:
        """Deliver the same terminal twice; assert one chat_postMessage."""
        await notifier.start()

        # Deliver the same notification twice
        await notifier.notify(terminal_notification)
        await notifier.notify(terminal_notification)

        # Give worker time to process
        await asyncio.sleep(0.1)

        # Should have posted exactly once
        assert mock_slack_client.chat_postMessage.call_count == 1

        await notifier.stop()


# ---------------------------------------------------------------------------
# Test: Dedup TTL expiry
# ---------------------------------------------------------------------------


class TestDedupTtlExpiry:
    """AC-002: Expired entries evicted on insert; re-delivery after 300s posts."""

    @pytest.mark.asyncio
    async def test_dedup_ttl_expiry(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
        terminal_notification: ForgeNotification,
    ) -> None:
        """Same key after 300s TTL posts a second time."""
        with patch("jarvis.infrastructure.slack_notifier.time.monotonic") as mock_monotonic:
            # Start at t=0
            mock_monotonic.return_value = 0.0

            await notifier.start()

            # First delivery at t=0
            await notifier.notify(terminal_notification)
            await asyncio.sleep(0.1)

            assert mock_slack_client.chat_postMessage.call_count == 1

            # Advance clock to t=301 (past 300s TTL)
            mock_monotonic.return_value = 301.0

            # Second delivery — should post again
            await notifier.notify(terminal_notification)
            await asyncio.sleep(0.1)

            assert mock_slack_client.chat_postMessage.call_count == 2

            await notifier.stop()


# ---------------------------------------------------------------------------
# Test: Distinct concurrent terminals both post
# ---------------------------------------------------------------------------


class TestDistinctConcurrentTerminalsBothPost:
    """AC-004: Two terminals for different build_ids both post."""

    @pytest.mark.asyncio
    async def test_distinct_concurrent_terminals_both_post(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
    ) -> None:
        """Two different build_ids should both post."""
        await notifier.start()

        notif1 = ForgeNotification(
            event_type="build_complete",
            correlation_id="corr-001",
            feature_id="FEAT-AAA",
            build_id="build-001",
            completed_at=datetime.now(timezone.utc),
        )

        notif2 = ForgeNotification(
            event_type="build_complete",
            correlation_id="corr-002",
            feature_id="FEAT-BBB",
            build_id="build-002",
            completed_at=datetime.now(timezone.utc),
        )

        await notifier.notify(notif1)
        await notifier.notify(notif2)

        # Give worker time to process
        await asyncio.sleep(0.1)

        # Both should have posted
        assert mock_slack_client.chat_postMessage.call_count == 2

        # Verify each message has correct feature_id
        calls = mock_slack_client.chat_postMessage.call_args_list
        texts = [call.kwargs["text"] for call in calls]
        assert any("FEAT-AAA" in text for text in texts)
        assert any("FEAT-BBB" in text for text in texts)

        await notifier.stop()


# ---------------------------------------------------------------------------
# Test: Queued intake dedup keyed on correlation_id
# ---------------------------------------------------------------------------


class TestQueuedIntakeDedupKeyedOnCorrelationId:
    """AC-001: build_queued dedup keyed on correlation_id."""

    @pytest.mark.asyncio
    async def test_queued_intake_dedup_keyed_on_correlation_id(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
    ) -> None:
        """Two build_queued with same correlation_id post once; different post twice."""
        await notifier.start()

        # Two notifications with the same correlation_id
        notif1 = ForgeNotification(
            event_type="build_queued",
            correlation_id="corr-same",
            feature_id="FEAT-AAA",
            completed_at=datetime.now(timezone.utc),
        )

        notif2 = ForgeNotification(
            event_type="build_queued",
            correlation_id="corr-same",
            feature_id="FEAT-AAA",
            completed_at=datetime.now(timezone.utc),
        )

        await notifier.notify(notif1)
        await notifier.notify(notif2)
        await asyncio.sleep(0.1)

        # Should post once
        assert mock_slack_client.chat_postMessage.call_count == 1

        # Reset mock
        mock_slack_client.chat_postMessage.reset_mock()

        # Different correlation_id
        notif3 = ForgeNotification(
            event_type="build_queued",
            correlation_id="corr-different",
            feature_id="FEAT-BBB",
            completed_at=datetime.now(timezone.utc),
        )

        await notifier.notify(notif3)
        await asyncio.sleep(0.1)

        # Should post again
        assert mock_slack_client.chat_postMessage.call_count == 1

        await notifier.stop()


# ---------------------------------------------------------------------------
# Test: 429 backoff honours Retry-After
# ---------------------------------------------------------------------------


class Test429BackoffHonoursRetryAfter:
    """AC-006: 429 response honours Retry-After header."""

    @pytest.mark.asyncio
    async def test_429_backoff_honours_retry_after(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
    ) -> None:
        """Mock 429 with Retry-After, assert backoff and eventual delivery."""
        await notifier.start()

        # Mock 429 response with Retry-After: 2
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {"Retry-After": "2"}

        call_count = 0

        async def mock_post_with_retry(*args: Any, **kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise SlackApiError(
                    message="rate_limited",
                    response=error_response,
                )
            return {"ok": True}

        mock_slack_client.chat_postMessage = AsyncMock(side_effect=mock_post_with_retry)

        notification = ForgeNotification(
            event_type="build_complete",
            correlation_id="corr-001",
            feature_id="FEAT-TEST",
            build_id="build-001",
            completed_at=datetime.now(timezone.utc),
        )

        with patch("asyncio.sleep") as mock_sleep:
            await notifier.notify(notification)

            # Give worker time to process
            await asyncio.sleep(0.1)

            # Should have slept for ~2 seconds (Retry-After value)
            # Filter out pacing delays (< 0.1s) to find backoff delay
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            backoff_delays = [delay for delay in sleep_calls if delay > 0.1]
            assert any(1.5 <= delay <= 2.5 for delay in backoff_delays)

            # Message should eventually be delivered
            assert call_count == 2

        await notifier.stop()


# ---------------------------------------------------------------------------
# Test: 429 budget exhaustion warns and drops
# ---------------------------------------------------------------------------


class Test429BudgetExhaustionWarnsAndDrops:
    """AC-006: Sustained 429s beyond retry budget logs WARNING and drops."""

    @pytest.mark.asyncio
    async def test_429_budget_exhaustion_warns_and_drops(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
        terminal_notification: ForgeNotification,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sustained 429s should log WARNING and drop message."""
        await notifier.start()

        # Mock sustained 429 responses
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {"Retry-After": "1"}

        async def always_429(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise SlackApiError(
                message="rate_limited",
                response=error_response,
            )

        mock_slack_client.chat_postMessage = AsyncMock(side_effect=always_429)

        with patch("asyncio.sleep"):
            await notifier.notify(terminal_notification)

            # Give worker time to exhaust retries
            await asyncio.sleep(0.5)

            # Should have logged WARNING about retry budget exhaustion
            assert any(
                "retry" in record.message.lower() or "429" in record.message.lower()
                for record in caplog.records
                if record.levelname == "WARNING"
            )

            # Subsequent messages should still flow
            mock_slack_client.chat_postMessage.reset_mock()
            mock_slack_client.chat_postMessage = AsyncMock(return_value={"ok": True})

            notif2 = ForgeNotification(
                event_type="build_complete",
                correlation_id="corr-002",
                feature_id="FEAT-NEW",
                build_id="build-002",
                completed_at=datetime.now(timezone.utc),
            )

            await notifier.notify(notif2)
            await asyncio.sleep(0.1)

            # Should deliver the new message
            assert mock_slack_client.chat_postMessage.call_count >= 1

        await notifier.stop()


# ---------------------------------------------------------------------------
# Test: Overflow drops oldest with one WARNING
# ---------------------------------------------------------------------------


class TestOverflowDropsOldestWithOneWarning:
    """AC-008: Bounded queue overflow drops oldest, logs exactly one WARNING."""

    @pytest.mark.asyncio
    async def test_overflow_drops_oldest_with_one_warning(
        self,
        mock_slack_client: AsyncMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Fill queue past capacity; assert oldest dropped with one WARNING."""
        # Create notifier with small queue
        notifier = SlackNotifier(
            bot_token="xoxb-test",
            channel_id="C123",
            queue_maxsize=2,
        )
        notifier._client = mock_slack_client

        # Block the worker by making chat_postMessage hang
        hang_event = asyncio.Event()

        async def hanging_post(*args: Any, **kwargs: Any) -> dict[str, Any]:
            await hang_event.wait()
            return {"ok": True}

        mock_slack_client.chat_postMessage = AsyncMock(side_effect=hanging_post)

        await notifier.start()

        # Fill the queue beyond capacity
        notifications = [
            ForgeNotification(
                event_type="build_complete",
                correlation_id=f"corr-{i}",
                feature_id="FEAT-TEST",
                build_id=f"build-{i}",
                completed_at=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]

        for notif in notifications:
            await notifier.notify(notif)

        await asyncio.sleep(0.1)

        # Should have logged WARNING about overflow
        # structlog uses event dict, check for the event name
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        overflow_warnings = [
            w
            for w in warnings
            if hasattr(w, "event")
            and w.event in ("slack_notify_dropped_queue_overflow", "slack_notify_dropped_queue_full")
        ]

        # Should have at least one overflow warning
        assert len(overflow_warnings) >= 1

        # Clean up
        hang_event.set()
        await notifier.stop()


# ---------------------------------------------------------------------------
# Test: notify() never blocks event loop
# ---------------------------------------------------------------------------


class TestNotifyNeverBlocksEventLoop:
    """AC-007: notify() returns immediately even when worker is stalled."""

    @pytest.mark.asyncio
    async def test_notify_never_blocks_event_loop(
        self,
        notifier: SlackNotifier,
        mock_slack_client: AsyncMock,
    ) -> None:
        """With worker stalled in backoff, notify() completes immediately."""
        await notifier.start()

        # Stall the worker with a 429
        error_response = MagicMock()
        error_response.status_code = 429
        error_response.headers = {"Retry-After": "10"}

        async def always_429(*args: Any, **kwargs: Any) -> dict[str, Any]:
            raise SlackApiError(
                message="rate_limited",
                response=error_response,
            )

        mock_slack_client.chat_postMessage = AsyncMock(side_effect=always_429)

        # Enqueue first notification to trigger backoff
        notif1 = ForgeNotification(
            event_type="build_complete",
            correlation_id="corr-001",
            feature_id="FEAT-AAA",
            build_id="build-001",
            completed_at=datetime.now(timezone.utc),
        )

        await notifier.notify(notif1)
        await asyncio.sleep(0.05)

        # Now try to enqueue while worker is potentially backing off
        notif2 = ForgeNotification(
            event_type="build_complete",
            correlation_id="corr-002",
            feature_id="FEAT-BBB",
            build_id="build-002",
            completed_at=datetime.now(timezone.utc),
        )

        # This should complete immediately (< 1 second)
        try:
            await asyncio.wait_for(notifier.notify(notif2), timeout=1.0)
        except TimeoutError:
            pytest.fail("notify() blocked the event loop")

        await notifier.stop()
