"""Slack notification sink for Forge build events (TASK-JNB-001).

Implements a ``NotificationSink`` protocol consumed by
``ForgeNotificationsSubscriber`` (TASK-JNB-002) and wired in
``lifecycle.build_app_state`` (TASK-JNB-003). Provides:

* Bounded ``asyncio.Queue`` drained by a single worker task posting
  plain-text ``chat.postMessage`` (mrkdwn disabled).
* ``start()``/``stop()`` lifecycle with bounded shutdown (does not hang on
  full or stuck queue).
* ``notify()`` never raises; every delivery failure logs at WARNING and
  processing continues (DDR-007).
* No-op sink factory when ``slack_bot_token`` or ``slack_channel_id`` is
  unset — no Slack client constructed, no network calls.

Architecturally, the Slack sender lives inside the jarvis supervisor
process — not a separate adapter process. The sink protocol defined here
is the seam consumed downstream — TASK-JNB-002 binds it into
``ForgeNotificationsSubscriber``, and TASK-JNB-003 constructs it in
``lifecycle.build_app_state`` only when both config fields are set.

References
----------
* Design document:
  ``docs/design/FEAT-28FF/design.md`` (checkpoint rendering slice).
* DDR-007: never-raise contract — sink failures must not propagate into
  JetStream callback or ``queue_build``.
* DDR-027: no replay — all sink state is in-process and in-memory.

Notes
-----
* Messages are plain text (mrkdwn disabled) so payload strings arrive
  inert.
* Optional fields (pr_url, summary, failure_reason) render gracefully
  when ``None``.
* The checkpoint slice implemented here: queued, build-started,
  build-complete, build-failed. Additional rendering (pause, cancelled)
  and 429 backoff land in TASK-JNB-005/006.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.forge_notifications import ForgeNotification

logger = structlog.get_logger(__name__)

# Default queue capacity per DDR-007 (bounded queue, drop on overflow)
_DEFAULT_QUEUE_MAXSIZE = 100

# Default stop timeout (seconds) — stop() returns within this bound even
# if queue is full or worker is stuck
_DEFAULT_STOP_TIMEOUT = 5.0

# Dedup TTL (TASK-JNB-006 ASSUM-006) — 300s first-wins window
_DEDUP_TTL_SECONDS = 300.0

# 429 retry budget — maximum retry attempts per message
_MAX_429_RETRIES = 3

# Worker pacing — target ~1 msg/s
_WORKER_PACING_DELAY = 1.0


# ---------------------------------------------------------------------------
# §1 — NotificationSink protocol
# ---------------------------------------------------------------------------


class NotificationSink(Protocol):
    """Protocol for notification sinks consumed by ForgeNotificationsSubscriber.

    Defines the seam TASK-JNB-002 binds into the subscriber. Implementations
    MUST satisfy the never-raise contract (DDR-007): ``notify()`` never
    propagates exceptions to the caller under any failure condition.
    """

    async def notify(self, notification: ForgeNotification) -> None:
        """Enqueue a notification for delivery.

        Never raises (DDR-007). If the sink is stopped, full, or encounters
        a delivery error, the failure is logged at WARNING and the call
        returns normally.

        Args:
            notification: The :class:`ForgeNotification` to deliver.
        """
        ...

    async def start(self) -> None:
        """Start the sink's delivery worker (idempotent).

        For the Slack sink, this launches the worker task that drains the
        queue. For the no-op sink, this is a no-op.
        """
        ...

    async def stop(self) -> None:
        """Stop the sink and perform bounded shutdown.

        Returns within ``stop_timeout`` seconds even if the queue is full
        or the worker is stuck. Never raises.
        """
        ...


# ---------------------------------------------------------------------------
# §2 — Slack sink implementation
# ---------------------------------------------------------------------------


class SlackNotifier:
    """Slack notification sink with bounded queue and single worker.

    Satisfies the ``NotificationSink`` protocol. Posts plain-text
    ``chat.postMessage`` with mrkdwn disabled. Never raises from
    ``notify()`` (DDR-007).
    """

    __slots__ = (
        "_bot_token",
        "_channel_id",
        "_client",
        "_dedup_map",
        "_queue",
        "_queue_maxsize",
        "_started",
        "_stop_timeout",
        "_worker_task",
    )

    def __init__(
        self,
        bot_token: str,
        channel_id: str,
        *,
        queue_maxsize: int = _DEFAULT_QUEUE_MAXSIZE,
        stop_timeout: float = _DEFAULT_STOP_TIMEOUT,
    ) -> None:
        """Construct the Slack notifier.

        Args:
            bot_token: Slack bot token (xoxb-...). Assumed pre-validated.
            channel_id: Slack channel ID (C...).
            queue_maxsize: Bound on the asyncio.Queue. Defaults to 100.
            stop_timeout: Maximum seconds :meth:`stop` will wait before
                returning unconditionally.
        """
        from slack_sdk.web.async_client import AsyncWebClient

        self._bot_token = bot_token
        self._channel_id = channel_id
        self._queue_maxsize = queue_maxsize
        self._stop_timeout = stop_timeout
        self._client = AsyncWebClient(token=bot_token)
        self._queue: asyncio.Queue[ForgeNotification] = asyncio.Queue(
            maxsize=queue_maxsize
        )
        self._started = False
        self._worker_task: asyncio.Task[None] | None = None
        # Dedup map: key -> monotonic timestamp (TASK-JNB-006)
        self._dedup_map: dict[tuple[str, ...], float] = {}

    async def notify(self, notification: ForgeNotification) -> None:
        """Enqueue a notification; never raises (DDR-007).

        Implements dedup (TASK-JNB-006 ASSUM-006): first-wins 300s TTL keyed
        on (event_type, build_id, stage_label) for stream events and
        ('build_queued', correlation_id) for intake events.

        If the queue is full, drops the oldest queued message with WARNING.
        If the sink is not started, logs WARNING and drops.
        """
        if not self._started:
            logger.warning(
                "slack_notify_dropped_not_started",
                correlation_id=notification.correlation_id,
                feature_id=notification.feature_id,
            )
            return

        # Dedup check: evict expired entries then check for duplicate
        self._evict_expired_dedup_entries()

        dedup_key = self._make_dedup_key(notification)
        now_mono = time.monotonic()

        if dedup_key in self._dedup_map:
            # Duplicate within TTL — drop silently
            logger.debug(
                "slack_notify_dropped_duplicate",
                correlation_id=notification.correlation_id,
                feature_id=notification.feature_id,
                dedup_key=dedup_key,
            )
            return

        # Record this notification in the dedup map
        self._dedup_map[dedup_key] = now_mono

        try:
            # put_nowait raises QueueFull if at capacity
            self._queue.put_nowait(notification)
        except asyncio.QueueFull:
            # Drop oldest message from queue (TASK-JNB-006 AC-008)
            try:
                oldest = self._queue.get_nowait()
                logger.warning(
                    "slack_notify_dropped_queue_overflow",
                    dropped_correlation_id=oldest.correlation_id,
                    dropped_feature_id=oldest.feature_id,
                    queue_maxsize=self._queue_maxsize,
                )
                # Try to enqueue the new notification
                self._queue.put_nowait(notification)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                # Fallback: log and drop new notification
                logger.warning(
                    "slack_notify_dropped_queue_full",
                    correlation_id=notification.correlation_id,
                    feature_id=notification.feature_id,
                    queue_maxsize=self._queue_maxsize,
                )

    async def start(self) -> None:
        """Launch the worker task (idempotent)."""
        if self._started:
            return

        self._started = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info(
            "slack_notifier_started",
            channel_id=self._channel_id,
            queue_maxsize=self._queue_maxsize,
        )

    async def stop(self) -> None:
        """Stop the worker within ``stop_timeout``; never raises.

        Cancels the worker task and waits up to ``stop_timeout`` for it
        to finish. If the worker doesn't finish in time, returns anyway.
        """
        if not self._started:
            return

        self._started = False
        worker = self._worker_task
        self._worker_task = None

        if worker is None:
            return

        worker.cancel()

        try:
            await asyncio.wait_for(worker, timeout=self._stop_timeout)
        except TimeoutError:
            logger.warning(
                "slack_notifier_stop_timeout",
                timeout=self._stop_timeout,
            )
        except asyncio.CancelledError:
            # Expected when worker is cancelled
            pass
        except Exception as exc:
            logger.warning(
                "slack_notifier_stop_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

        logger.info("slack_notifier_stopped")

    async def _worker(self) -> None:
        """Worker loop: drain the queue and post to Slack.

        Runs until cancelled. Every delivery failure logs at WARNING and
        continues — the worker never stops on error (DDR-007).

        Implements (TASK-JNB-006):
        - ~1 msg/s pacing
        - 429 handling with Retry-After honour and bounded retry budget
        """
        from slack_sdk.errors import SlackApiError

        while True:
            try:
                notification = await self._queue.get()
                text = self._render(notification)

                # Deliver with retry budget for 429 responses
                retries_left = _MAX_429_RETRIES
                delivered = False

                while retries_left > 0 and not delivered:
                    try:
                        await self._client.chat_postMessage(
                            channel=self._channel_id,
                            text=text,
                            mrkdwn=False,
                        )
                        delivered = True

                    except SlackApiError as exc:
                        # 429 rate limit handling (TASK-JNB-006 AC-006)
                        if exc.response.status_code == 429:
                            retries_left -= 1

                            if retries_left > 0:
                                # Honour Retry-After header
                                retry_after = exc.response.headers.get("Retry-After")
                                delay = float(retry_after) if retry_after else 1.0
                                logger.warning(
                                    "slack_429_backoff",
                                    correlation_id=notification.correlation_id,
                                    feature_id=notification.feature_id,
                                    retry_after=delay,
                                    retries_left=retries_left,
                                )
                                await asyncio.sleep(delay)
                            else:
                                # Budget exhausted
                                logger.warning(
                                    "slack_429_budget_exhausted",
                                    correlation_id=notification.correlation_id,
                                    feature_id=notification.feature_id,
                                    error=str(exc),
                                )
                                break
                        else:
                            # Non-429 SlackApiError — log and drop
                            logger.warning(
                                "slack_delivery_failed",
                                correlation_id=notification.correlation_id,
                                feature_id=notification.feature_id,
                                error=str(exc),
                                error_class=type(exc).__name__,
                            )
                            break

                    except Exception as exc:
                        # Defensive catch-all — any other exception logs and drops
                        logger.warning(
                            "slack_delivery_unexpected_error",
                            correlation_id=notification.correlation_id,
                            feature_id=notification.feature_id,
                            error=str(exc),
                            error_class=type(exc).__name__,
                        )
                        break

                # Worker pacing: ~1 msg/s (TASK-JNB-006 AC-005)
                await asyncio.sleep(_WORKER_PACING_DELAY)

            except asyncio.CancelledError:
                # Worker is stopping
                break
            except Exception as exc:
                # Defensive backstop — should never reach here
                logger.warning(
                    "slack_worker_unexpected_error",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )

    def _make_dedup_key(self, notification: ForgeNotification) -> tuple[str, ...]:
        """Construct dedup key per TASK-JNB-006 ASSUM-006.

        For build_queued (intake): ('build_queued', correlation_id)
        For stream events: (event_type, build_id, stage_label or '')

        Args:
            notification: The notification to key.

        Returns:
            Dedup key tuple.
        """
        if notification.event_type == "build_queued":
            return ("build_queued", notification.correlation_id)

        # Stream events (build_started, build_complete, build_failed, stage_complete)
        build_id = notification.build_id or ""
        stage_label = notification.stage_label or ""
        return (notification.event_type, build_id, stage_label)

    def _evict_expired_dedup_entries(self) -> None:
        """Evict expired entries from dedup map (TASK-JNB-006 AC-002).

        Uses monotonic clock with 300s TTL. Eviction happens on insert
        (called from notify()).
        """
        now_mono = time.monotonic()
        expired_keys = [
            key
            for key, timestamp in self._dedup_map.items()
            if (now_mono - timestamp) >= _DEDUP_TTL_SECONDS
        ]
        for key in expired_keys:
            del self._dedup_map[key]

    def _render(self, notification: ForgeNotification) -> str:
        """Render a ForgeNotification into plain-text Slack message.

        Implements the checkpoint slice: queued, build-started,
        build-complete, build-failed. Mirrors the canonical CLI rendering
        from ``ForgeNotification.render_line()`` but adapts for Slack
        (full timestamp, optional fields).

        Args:
            notification: The notification to render.

        Returns:
            Plain-text message string.
        """
        feature_id = notification.feature_id
        event_type = notification.event_type

        # Format timestamp as HH:MM (local time)
        local_completed_at = (
            notification.completed_at.astimezone()
            if notification.completed_at.tzinfo is not None
            else notification.completed_at
        )
        hhmm = local_completed_at.strftime("%H:%M")

        if event_type == "stage_complete":
            # Checkpoint slice: specifically the "queued" stage
            stage_label = notification.stage_label or "unknown"
            status = notification.status or "UNKNOWN"
            return f"[{hhmm}] Forge {feature_id}: stage {stage_label} ({status})"

        if event_type == "build_started":
            base = f"[{hhmm}] Forge {feature_id}: build-started (RUNNING)"
            if notification.pr_url:
                return f"{base}\nPR: {notification.pr_url}"
            return base

        if event_type == "build_complete":
            # Include pr_url and summary when present (AC-008)
            base = f"[{hhmm}] Forge {feature_id}: build-complete (PASSED)"
            parts = [base]

            if notification.pr_url:
                parts.append(f"PR: {notification.pr_url}")
            if notification.summary:
                parts.append(f"Summary: {notification.summary}")

            return "\n".join(parts) if len(parts) > 1 else base

        if event_type == "build_failed":
            reason = notification.failure_reason or "unknown"
            return f"[{hhmm}] Forge {feature_id}: build-failed ({reason})"

        if event_type == "build_paused":
            # TASK-JNB-005: Pause rendering
            # Format: stage, rationale, coach_score, CLI hint
            parts = [f"[{hhmm}] Forge {feature_id}: build-paused"]

            # Stage
            if notification.stage_label:
                parts.append(f"Stage: {notification.stage_label}")

            # Coach score
            if notification.coach_score is None:
                score_text = "score unavailable"
            else:
                # Defensive rendering: out-of-range scores render as text, never rejected
                score_text = f"{notification.coach_score:.2f}"
            parts.append(f"Coach score: {score_text}")

            # Rationale (verbatim plain text)
            if notification.rationale:
                # Chunk rationales > 3000 chars for Block Kit compatibility
                # In plain text mode, we just include the full rationale
                # but note that actual Block Kit would need chunking
                parts.append(f"Rationale: {notification.rationale}")

            # CLI hint for v1 (v1.1 will use buttons per TASK-JNB-103)
            parts.append("Use CLI to approve or reject this build.")

            return "\n".join(parts)

        if event_type == "build_cancelled":
            # TASK-JNB-005: Cancelled rendering
            # Format: cancelled_by, reason
            parts = [f"[{hhmm}] Forge {feature_id}: build-cancelled"]

            if notification.cancelled_by:
                parts.append(f"Cancelled by: {notification.cancelled_by}")

            if notification.reason:
                parts.append(f"Reason: {notification.reason}")

            return "\n".join(parts)

        # Fallback (should not reach here given the event_type Literal)
        return f"[{hhmm}] Forge {feature_id}: {event_type}"


# ---------------------------------------------------------------------------
# §3 — No-op sink
# ---------------------------------------------------------------------------


class NoOpSink:
    """No-op notification sink when Slack config is absent.

    Satisfies the ``NotificationSink`` protocol but performs no network
    calls. Logs at INFO when constructed so operators can see the no-op
    choice in startup logs.
    """

    async def notify(self, notification: ForgeNotification) -> None:
        """No-op: notification is dropped silently."""
        pass

    async def start(self) -> None:
        """No-op: nothing to start."""
        pass

    async def stop(self) -> None:
        """No-op: nothing to stop."""
        pass


# ---------------------------------------------------------------------------
# §4 — Factory
# ---------------------------------------------------------------------------


def create_slack_sink(
    config: JarvisConfig,
    *,
    queue_maxsize: int = _DEFAULT_QUEUE_MAXSIZE,
    stop_timeout: float = _DEFAULT_STOP_TIMEOUT,
) -> NotificationSink:
    """Create a Slack notification sink from JarvisConfig.

    Returns a no-op sink when ``slack_bot_token`` or ``slack_channel_id``
    is unset — no Slack client is constructed and no network calls occur.

    Args:
        config: The application configuration.
        queue_maxsize: Bound on the asyncio.Queue. Defaults to 100.
        stop_timeout: Maximum seconds ``stop()`` will wait before
            returning unconditionally.

    Returns:
        A :class:`NotificationSink` implementation. Either a live
        :class:`SlackNotifier` or a :class:`NoOpSink`.
    """
    bot_token_secret = config.slack_bot_token
    channel_id = config.slack_channel_id

    # Extract the raw token from SecretStr if present
    bot_token_value: str | None = None
    if bot_token_secret is not None:
        bot_token_value = bot_token_secret.get_secret_value()

    # No-op sink when either field is unset or empty
    if not bot_token_value or not channel_id:
        logger.info(
            "slack_sink_no_op",
            reason=(
                "slack_bot_token or slack_channel_id not configured; Slack notifications disabled"
            ),
        )
        return NoOpSink()

    return SlackNotifier(
        bot_token=bot_token_value,
        channel_id=channel_id,
        queue_maxsize=queue_maxsize,
        stop_timeout=stop_timeout,
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "NoOpSink",
    "NotificationSink",
    "SlackNotifier",
    "create_slack_sink",
]
