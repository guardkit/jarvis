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
* TASK-JNB-103 adds the approval surface: an
  :class:`ApprovalRequestsSubscriber` on ``agents.approval.forge.>``
  (AGENTS stream — limits retention, overlap legal; never the PIPELINE
  stream), a TTL-bounded in-memory pending-approval map keyed by
  ``build_id`` (DDR-027 — lost on restart by design; forge
  boot-reconcile re-emits repopulate it), and Block Kit
  Approve/Reject buttons on the pause message whose ``value`` JSON
  carries ``{request_id, build_id, correlation_id, approval_subject}``
  (the BUTTON_METADATA contract consumed by TASK-JNB-104).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
from typing import TYPE_CHECKING, Any, Protocol

import structlog
from pydantic import ValidationError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from nats.aio.msg import Msg

    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.forge_notifications import ForgeNotification
    from jarvis.infrastructure.nats_client import NATSClient

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

# Slack's hard limit on a Block Kit action value (TASK-JNB-103 /
# BUTTON_METADATA contract with TASK-JNB-104): value JSON must stay
# strictly under this many characters or the button falls back to the
# v1 text-only pause message.
_SLACK_ACTION_VALUE_LIMIT = 2000

# Block Kit section text objects cap at 3000 chars; rationale text is
# chunked below that with headroom for the "Rationale: " prefix.
_RATIONALE_CHUNK_CHARS = 2900

# Default TTL for a captured approval request when the payload carries a
# non-positive timeout — mirrors ApprovalRequestPayload's own 300s default.
_DEFAULT_APPROVAL_TTL_SECONDS = 300.0

# TTL bound on the posted pause-message registry (DDR-027 — in-process,
# monotonic clock, evict-on-insert). Records exist so a defer-refreshed
# request_id can chat.update the exact posted message in place; an hour
# comfortably outlives any live approval window (forge-side enforcement
# is authoritative — a record evicted early is a UX-only risk).
_PAUSE_REGISTRY_TTL_SECONDS = 3600.0

# Injectable monotonic-clock seam. Tests MUST patch this alias
# (jarvis.infrastructure.slack_notifier._monotonic) instead of
# time.monotonic — patching the shared stdlib attribute freezes
# asyncio's event-loop clock and hangs the whole test process.
_monotonic = time.monotonic


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
# §1b — Approval capture state + Block Kit pause rendering (TASK-JNB-103)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class PendingApproval:
    """One captured, not-yet-rendered forge approval request.

    Stored in ``SlackNotifier._pending_approvals`` keyed by ``build_id``
    until the matching ``build_paused`` notification arrives (or the TTL
    expires). All state is in-process and in-memory per DDR-027 — a
    jarvis restart loses the map by design; the text-only fallback covers
    pauses whose requests were lost, and forge boot-reconcile re-emits
    (absorbed by the request_id dedup) repopulate it.
    """

    request_id: str
    build_id: str
    correlation_id: str | None
    approval_subject: str
    ttl_seconds: float
    captured_at_mono: float

    def expires_at(self) -> float:
        """Monotonic deadline after which this entry is stale."""
        return self.captured_at_mono + self.ttl_seconds


@dataclasses.dataclass
class _PauseMessageRecord:
    """Registry entry for a posted pause message (keyed by ``build_id``).

    Tracks the Slack message ``ts`` so a defer-refreshed ``request_id``
    (or a request arriving after its pause — the pause-before-request
    ordering) can ``chat.update`` the exact message in place instead of
    posting a second actionable message.

    ``ts is None`` marks a post still in flight: the worker writes the
    record synchronously *before* awaiting ``chat.postMessage`` (the C1
    TOCTOU guard from the Phase 2.5B review), so a concurrent capture
    mutates this record instead of the pending map and the worker's
    post-await reconcile step converges the posted message onto the
    settled state.
    """

    notification: ForgeNotification
    request_id: str | None
    buttoned: bool
    value_json: str | None
    ts: str | None
    posted_at_mono: float

    def expires_at(self) -> float:
        """Monotonic deadline after which this record is dropped."""
        return self.posted_at_mono + _PAUSE_REGISTRY_TTL_SECONDS


def _build_button_value(
    request_id: str,
    build_id: str,
    correlation_id: str,
    approval_subject: str,
) -> str | None:
    """Encode the BUTTON_METADATA value JSON for TASK-JNB-104.

    Exactly four keys, compact encoding (no pretty-printing, no extra
    keys — producer contract in the task file). Returns ``None`` when the
    encoded value would reach Slack's 2000-character action value limit,
    in which case the caller falls back to the v1 text-only message
    rather than posting a broken button.
    """
    value = json.dumps(
        {
            "request_id": request_id,
            "build_id": build_id,
            "correlation_id": correlation_id,
            "approval_subject": approval_subject,
        },
        separators=(",", ":"),
    )
    if len(value) >= _SLACK_ACTION_VALUE_LIMIT:
        logger.warning(
            "slack_approval_button_value_oversized",
            request_id=request_id,
            build_id=build_id,
            value_length=len(value),
            limit=_SLACK_ACTION_VALUE_LIMIT,
        )
        return None
    return value


def _plain_text_section(text: str) -> dict[str, Any]:
    """One Block Kit section whose text object is inert ``plain_text``."""
    return {
        "type": "section",
        "text": {"type": "plain_text", "text": text, "emoji": False},
    }


def build_pause_blocks(
    notification: ForgeNotification,
    button_value: str | None = None,
) -> list[dict[str, Any]]:
    """Render a ``build_paused`` notification as Block Kit blocks.

    All operator-visible text renders as ``plain_text`` objects only —
    no mrkdwn interpretation, so rationale and failure strings arrive
    inert. Mirrors the v1 text rendering shape from
    :meth:`SlackNotifier._render` (which remains byte-identical for the
    text-only fallback path — deliberate divergence, do not merge the
    two).

    Args:
        notification: The pause notification to render.
        button_value: Pre-encoded BUTTON_METADATA value JSON. When
            provided, an ``actions`` block with Approve/Reject buttons is
            appended; when ``None``, the v1 CLI hint line is rendered
            instead.

    Returns:
        Block Kit blocks list suitable for ``chat.postMessage`` /
        ``chat.update``.
    """
    local_completed_at = (
        notification.completed_at.astimezone()
        if notification.completed_at.tzinfo is not None
        else notification.completed_at
    )
    hhmm = local_completed_at.strftime("%H:%M")

    blocks: list[dict[str, Any]] = [
        _plain_text_section(f"[{hhmm}] Forge {notification.feature_id}: build-paused")
    ]

    if notification.stage_label:
        blocks.append(_plain_text_section(f"Stage: {notification.stage_label}"))

    if notification.coach_score is None:
        # ADR-ARCH-033 — None is the live default and must render, not raise.
        score_text = "score unavailable"
    else:
        score_text = f"{notification.coach_score:.2f}"
    blocks.append(_plain_text_section(f"Coach score: {score_text}"))

    if notification.rationale:
        rationale = notification.rationale
        for start in range(0, len(rationale), _RATIONALE_CHUNK_CHARS):
            chunk = rationale[start : start + _RATIONALE_CHUNK_CHARS]
            prefix = "Rationale: " if start == 0 else ""
            blocks.append(_plain_text_section(f"{prefix}{chunk}"))

    if button_value is None:
        blocks.append(_plain_text_section("Use CLI to approve or reject this build."))
    else:
        blocks.append(
            {
                "type": "actions",
                "block_id": "forge_approval",
                "elements": [
                    {
                        "type": "button",
                        "action_id": "forge_approve",
                        "text": {
                            "type": "plain_text",
                            "text": "Approve",
                            "emoji": False,
                        },
                        "style": "primary",
                        "value": button_value,
                    },
                    {
                        "type": "button",
                        "action_id": "forge_reject",
                        "text": {
                            "type": "plain_text",
                            "text": "Reject",
                            "emoji": False,
                        },
                        "style": "danger",
                        "value": button_value,
                    },
                ],
            }
        )

    return blocks


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
        "_pause_messages",
        "_pending_approvals",
        "_queue",
        "_queue_maxsize",
        "_seen_request_ids",
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
        self._queue: asyncio.Queue[ForgeNotification] = asyncio.Queue(maxsize=queue_maxsize)
        self._started = False
        self._worker_task: asyncio.Task[None] | None = None
        # Dedup map: key -> monotonic timestamp (TASK-JNB-006)
        self._dedup_map: dict[tuple[str, ...], float] = {}
        # TASK-JNB-103 approval state — all in-process, in-memory,
        # TTL-bounded via the monotonic clock with evict-on-insert
        # (DDR-027; a restart loses all three maps by design).
        # Pending approval requests awaiting their pause, keyed by build_id.
        self._pending_approvals: dict[str, PendingApproval] = {}
        # request_id -> monotonic expiry; absorbs forge boot-reconcile
        # re-emits so an identical request_id never yields a second
        # actionable message.
        self._seen_request_ids: dict[str, float] = {}
        # Posted pause messages keyed by build_id, so defer-refresh /
        # late-request paths can chat.update the exact message in place.
        self._pause_messages: dict[str, _PauseMessageRecord] = {}

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
        now_mono = _monotonic()

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

        TASK-JNB-103: ``build_paused`` notifications route through
        :meth:`_deliver_pause_message` (Block Kit buttons when a pending
        approval was captured for the build; v1 text-only fallback
        otherwise). All other event types keep the v1 plain-text path
        byte-identical.
        """
        while True:
            try:
                notification = await self._queue.get()

                if notification.event_type == "build_paused":
                    await self._deliver_pause_message(notification)
                else:
                    text = self._render(notification)
                    await self._post_with_retry(notification, text=text)

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

    async def _post_with_retry(
        self,
        notification: ForgeNotification,
        *,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> Any | None:
        """Deliver one ``chat.postMessage`` with the 429 retry budget.

        The TASK-JNB-006 delivery loop, extracted verbatim so the pause
        path (blocks) and the plain-text path share one 429/backoff
        implementation. Never raises; returns the Slack response on
        success and ``None`` when delivery failed or the retry budget
        was exhausted.
        """
        from slack_sdk.errors import SlackApiError

        # Budget = initial attempt + MAX_RETRIES
        attempts_left = _MAX_429_RETRIES + 1

        while attempts_left > 0:
            try:
                kwargs: dict[str, Any] = {
                    "channel": self._channel_id,
                    "text": text,
                    "mrkdwn": False,
                }
                if blocks is not None:
                    kwargs["blocks"] = blocks
                return await self._client.chat_postMessage(**kwargs)

            except SlackApiError as exc:
                # 429 rate limit handling (TASK-JNB-006 AC-006)
                if exc.response.status_code == 429:
                    attempts_left -= 1

                    if attempts_left > 0:
                        # Honour Retry-After header. Servers may send an
                        # HTTP-date instead of delta-seconds (RFC 9110);
                        # a malformed value must not raise out of this
                        # except handler (review finding — a sibling
                        # except clause cannot catch it).
                        retry_after = exc.response.headers.get("Retry-After")
                        try:
                            delay = float(retry_after) if retry_after else 1.0
                        except (TypeError, ValueError):
                            delay = 1.0
                        logger.warning(
                            "slack_429_backoff",
                            correlation_id=notification.correlation_id,
                            feature_id=notification.feature_id,
                            retry_after=delay,
                            retries_left=attempts_left - 1,
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
                        return None
                else:
                    # Non-429 SlackApiError — log and drop
                    logger.warning(
                        "slack_delivery_failed",
                        correlation_id=notification.correlation_id,
                        feature_id=notification.feature_id,
                        error=str(exc),
                        error_class=type(exc).__name__,
                    )
                    return None

            except Exception as exc:
                # Defensive catch-all — any other exception logs and drops
                logger.warning(
                    "slack_delivery_unexpected_error",
                    correlation_id=notification.correlation_id,
                    feature_id=notification.feature_id,
                    error=str(exc),
                    error_class=type(exc).__name__,
                )
                return None

        return None

    # ------------------------------------------------------------------
    # TASK-JNB-103 — approval capture + pause message delivery
    # ------------------------------------------------------------------

    async def capture_approval_request(
        self,
        *,
        request_id: str,
        build_id: str,
        correlation_id: str | None,
        approval_subject: str,
        timeout_seconds: float,
    ) -> None:
        """Capture one forge approval request; never raises (DDR-007).

        Called by :class:`ApprovalRequestsSubscriber` from the JetStream
        callback. All map mutations happen synchronously (no ``await``
        between read and write — the C1 TOCTOU guard); the only awaits
        are the wrapped Slack side-effects issued after state settles.

        Convergence rules (task ACs):

        * ``request_id`` already seen → drop (boot-reconcile re-emit;
          no second actionable message).
        * A pause message already posted for ``build_id``:

          - buttoned → defer-refresh: ``chat.update`` replaces the
            buttons in place (operator never holds a stale button);
          - text-only → upgrade: ``chat.update`` adds the buttons
            (pause-before-request ordering converges on one buttoned
            message);
          - post still in flight (``ts is None``) → mutate the record
            only; the worker's post-await reconcile converges.

          In all three cases the request is ALSO parked in the pending
          map: jarvis cannot distinguish a defer-refresh of the current
          pause from the NEXT gate's request arriving early (multi-gate
          builds), so the next ``build_paused`` supersedes this record
          and consumes the parked entry; a pure defer-refresh's entry
          harmlessly TTL-expires.

        * Otherwise (request-before-pause) → store in the pending map;
          the coming pause renders the buttons.
        """
        try:
            self._sweep_approval_state()
            now_mono = _monotonic()

            if request_id in self._seen_request_ids:
                logger.debug(
                    "slack_approval_request_deduped",
                    request_id=request_id,
                    build_id=build_id,
                )
                return

            ttl = (
                float(timeout_seconds)
                if timeout_seconds and timeout_seconds > 0
                else _DEFAULT_APPROVAL_TTL_SECONDS
            )
            self._seen_request_ids[request_id] = now_mono + ttl

            record = self._pause_messages.get(build_id)
            if record is not None:
                value = _build_button_value(
                    request_id=request_id,
                    build_id=build_id,
                    correlation_id=(correlation_id or record.notification.correlation_id),
                    approval_subject=(
                        approval_subject or record.notification.approval_subject or ""
                    ),
                )
                if value is None:
                    # Oversized value JSON — cannot render a valid button;
                    # the posted message stays as-is (text-only fallback
                    # semantics; forge-side CLI approval still works).
                    return

                was_buttoned = record.buttoned
                # Synchronous mutation before any await (C1).
                record.request_id = request_id
                record.buttoned = True
                record.value_json = value
                # ALSO park the request (multi-gate review fix): if this
                # is really the NEXT gate's request arriving before its
                # own build_paused (jarvis cannot distinguish that from a
                # defer-refresh of the current pause), the coming pause
                # supersedes this record and consumes the pending entry
                # to button the fresh message. For a pure defer-refresh
                # the entry harmlessly TTL-expires.
                self._pending_approvals[build_id] = PendingApproval(
                    request_id=request_id,
                    build_id=build_id,
                    correlation_id=correlation_id,
                    approval_subject=approval_subject,
                    ttl_seconds=ttl,
                    captured_at_mono=now_mono,
                )

                if record.ts is not None:
                    await self._update_pause_message(record)
                # ts is None → post in flight; _deliver_pause_message's
                # reconcile step issues the chat.update once ts lands.
                logger.info(
                    "slack_approval_buttons_refreshed"
                    if was_buttoned
                    else "slack_pause_message_upgraded_with_buttons",
                    request_id=request_id,
                    build_id=build_id,
                    in_flight=record.ts is None,
                )
                return

            # Request-before-pause: park it for the coming pause message.
            # A prior pending entry for the same build (defer-refresh
            # before any pause was posted) is simply replaced.
            self._pending_approvals[build_id] = PendingApproval(
                request_id=request_id,
                build_id=build_id,
                correlation_id=correlation_id,
                approval_subject=approval_subject,
                ttl_seconds=ttl,
                captured_at_mono=now_mono,
            )
            logger.info(
                "slack_approval_request_captured",
                request_id=request_id,
                build_id=build_id,
                ttl_seconds=ttl,
            )
        except Exception as exc:
            # DDR-007 backstop — capture failures must never propagate
            # into the JetStream callback.
            logger.warning(
                "slack_approval_capture_failed",
                request_id=request_id,
                build_id=build_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _deliver_pause_message(self, notification: ForgeNotification) -> None:
        """Post one pause message — buttoned when a pending approval joins.

        The join is purely on ``build_id`` (BuildPausedPayload carries no
        attempt_count, so jarvis can never derive request_id itself). A
        pending-map hit renders Block Kit Approve/Reject buttons; a miss
        (never captured, TTL-expired, or already consumed) posts the v1
        text-only message unchanged.

        C1 ordering: the pending entry is consumed and the registry
        record written *before* the ``chat.postMessage`` await; after the
        post, :meth:`_reconcile_pause_message` converges the message if a
        concurrent capture mutated the record mid-flight.
        """
        self._sweep_approval_state()
        text = self._render(notification)
        build_id = notification.build_id

        # TASK-SPL003-J02 — suppress the binary pause mirror for planning
        # checkpoints. forge Mode P also publishes a
        # ``pipeline.build-paused.FEAT-PLANNING`` mirror; rendering it as a
        # binary Approve/Reject message is exactly the approve-all rubber-stamp
        # scenario 15 forbids. The per-assumption dialogue (rendered from the
        # ApprovalRequestPayload at capture time) is the ONLY planning surface.
        # Detected on the build_id / feature_id, never posted for a checkpoint.
        if (build_id is not None and build_id.startswith("plan-")) or (
            notification.feature_id == "FEAT-PLANNING"
        ):
            logger.debug(
                "planning_pause_mirror_suppressed",
                build_id=build_id,
                feature_id=notification.feature_id,
                correlation_id=notification.correlation_id,
            )
            return

        if build_id is None:
            # No join key — defensive; render the v1 fallback verbatim.
            await self._post_with_retry(notification, text=text)
            return

        # A new pause supersedes any previously posted pause message for
        # this build (multi-gate / wave-gated builds — review finding):
        # the old message's buttons are stripped with one chat.update so
        # the operator can never act on a superseded gate, and this pause
        # becomes the registry anchor. The record is popped synchronously
        # before the await (C1).
        superseded = self._pause_messages.pop(build_id, None)
        if superseded is not None and superseded.buttoned and superseded.ts is not None:
            superseded.buttoned = False
            superseded.value_json = None
            await self._update_pause_message(superseded)

        # Pop the pending join AFTER the supersede await so a capture
        # landing during that await is still picked up by this pause.
        pending = self._pending_approvals.pop(build_id, None)

        value: str | None = None
        if pending is not None:
            value = _build_button_value(
                request_id=pending.request_id,
                build_id=build_id,
                correlation_id=(pending.correlation_id or notification.correlation_id),
                approval_subject=(pending.approval_subject or notification.approval_subject or ""),
            )

        if value is not None and pending is not None:
            record = _PauseMessageRecord(
                notification=notification,
                request_id=pending.request_id,
                buttoned=True,
                value_json=value,
                ts=None,
                posted_at_mono=_monotonic(),
            )
            self._pause_messages[build_id] = record
            blocks = build_pause_blocks(notification, button_value=value)
            response = await self._post_with_retry(notification, text=text, blocks=blocks)
            await self._settle_pause_post(
                build_id,
                record,
                response,
                posted_request_id=pending.request_id,
                posted_buttoned=True,
            )
            return

        # Text-only fallback (v1 message unchanged) — no request captured
        # for this pause (never arrived, TTL-expired, or oversized value).
        record = _PauseMessageRecord(
            notification=notification,
            request_id=None,
            buttoned=False,
            value_json=None,
            ts=None,
            posted_at_mono=_monotonic(),
        )
        self._pause_messages[build_id] = record
        response = await self._post_with_retry(notification, text=text)
        await self._settle_pause_post(
            build_id,
            record,
            response,
            posted_request_id=None,
            posted_buttoned=False,
        )

    async def _settle_pause_post(
        self,
        build_id: str,
        record: _PauseMessageRecord,
        response: Any | None,
        *,
        posted_request_id: str | None,
        posted_buttoned: bool,
    ) -> None:
        """Record the posted ``ts`` and reconcile mid-flight mutations.

        If a concurrent :meth:`capture_approval_request` changed the
        record's ``request_id`` / ``buttoned`` state while the post was
        in flight, one ``chat.update`` brings the posted message onto the
        settled state (C1 reconcile). A failed post drops the record so a
        later request cannot target a message that never landed — and
        returns any consumed approval to the pending map (review
        finding: the failed post must not permanently lose the request;
        the dedup entry is cleared so a forge boot-reconcile re-emit can
        also re-capture it).
        """
        if response is None:
            if self._pause_messages.get(build_id) is record:
                del self._pause_messages[build_id]
            if record.request_id is not None and record.value_json is not None:
                self._repark_lost_approval(build_id, record)
            logger.warning(
                "slack_pause_message_post_failed",
                build_id=build_id,
                request_id=record.request_id,
            )
            return

        ts: str | None = None
        try:
            ts = response.get("ts")
        except Exception:  # pragma: no cover - defensive on exotic mocks
            ts = None
        record.ts = ts

        if ts is None:
            return

        if record.request_id != posted_request_id or record.buttoned != posted_buttoned:
            await self._update_pause_message(record)

    async def _update_pause_message(self, record: _PauseMessageRecord) -> None:
        """``chat.update`` a posted pause message in place; never raises.

        Single attempt, no retry budget (C2): a missed update leaves a
        briefly-stale button, which is a UX-only risk — forge-side
        window/expiry enforcement safely refuses it (task constraint:
        jarvis must not enforce expiry beyond the TTL map).
        """
        if record.ts is None:
            return
        blocks = build_pause_blocks(
            record.notification,
            button_value=record.value_json if record.buttoned else None,
        )
        try:
            await self._client.chat_update(
                channel=self._channel_id,
                ts=record.ts,
                text=self._render(record.notification),
                blocks=blocks,
            )
        except Exception as exc:
            logger.warning(
                "slack_pause_button_update_failed",
                build_id=record.notification.build_id,
                request_id=record.request_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    def _repark_lost_approval(self, build_id: str, record: _PauseMessageRecord) -> None:
        """Return a consumed approval to the pending map after a lost post.

        Reconstructs the :class:`PendingApproval` from the record's value
        JSON (the four BUTTON_METADATA fields are self-contained) with the
        request's *remaining* TTL, and clears the request_id dedup entry
        so a boot-reconcile re-emit can also re-capture it. Best-effort —
        never raises (DDR-007).
        """
        try:
            request_id = record.request_id
            value_json = record.value_json
            if request_id is None or value_json is None:
                return
            meta = json.loads(value_json)
            expiry = self._seen_request_ids.pop(request_id, None)
            now_mono = _monotonic()
            ttl_remaining = (expiry - now_mono) if expiry is not None else 0.0
            if ttl_remaining <= 0:
                return
            self._pending_approvals[build_id] = PendingApproval(
                request_id=request_id,
                build_id=build_id,
                correlation_id=meta.get("correlation_id"),
                approval_subject=meta.get("approval_subject", ""),
                ttl_seconds=ttl_remaining,
                captured_at_mono=now_mono,
            )
            logger.info(
                "slack_approval_request_reparked",
                request_id=request_id,
                build_id=build_id,
                ttl_remaining=ttl_remaining,
            )
        except Exception as exc:  # pragma: no cover - defensive backstop
            logger.warning(
                "slack_approval_repark_failed",
                build_id=build_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    def _sweep_approval_state(self) -> None:
        """Evict expired entries from all three approval maps.

        Evict-on-insert with the monotonic clock (DDR-027) — called from
        both entry points (capture and pause delivery) so no map depends
        on the other path's traffic to stay bounded.
        """
        now_mono = _monotonic()

        for key in [
            k for k, pending in self._pending_approvals.items() if now_mono >= pending.expires_at()
        ]:
            del self._pending_approvals[key]

        for req_id in [
            r for r, expires_at in self._seen_request_ids.items() if now_mono >= expires_at
        ]:
            del self._seen_request_ids[req_id]

        for key in [k for k, rec in self._pause_messages.items() if now_mono >= rec.expires_at()]:
            del self._pause_messages[key]

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
        now_mono = _monotonic()
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

        if event_type == "build_queued":
            # Intake event (TASK-JNB-006)
            return f"[{hhmm}] Forge {feature_id}: build-queued"

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
# §2b — ApprovalRequestsSubscriber (TASK-JNB-103)
# ---------------------------------------------------------------------------


def _get_approval_request_subject() -> str:
    """Lazy-derive ``agents.approval.forge.>`` from ``nats_core.Topics``.

    Substitutes ``forge`` for ``{agent_id}`` and the NATS ``>`` wildcard
    for ``{task_id}`` in ``Topics.Agents.APPROVAL_REQUEST``
    (``agents.approval.{agent_id}.{task_id}``). Imported lazily so
    schema-only consumers of this module never pull the ``nats_core`` /
    ``nats`` import chain (same rationale as
    ``forge_notifications._get_lifecycle_subjects``).
    """
    from nats_core import Topics

    return Topics.Agents.APPROVAL_REQUEST.replace("{agent_id}", "forge").replace("{task_id}", ">")


def _get_deliver_policy_new() -> Any:
    """Lazy-load ``nats.js.api.DeliverPolicy.NEW``.

    The AGENTS stream uses **limits** retention (unlike the workqueue
    PIPELINE stream whose code=10101 rejection forced
    ``DeliverPolicy.ALL`` on the forge subscriber — see the rationale
    block in ``forge_notifications.py``). Limits retention accepts
    ``NEW``, which reinstates the genuine DDR-027 no-replay semantics:
    a jarvis restart loses the in-memory pending map by design, replay
    of stale approval requests would only resurrect dead buttons, and
    forge boot-reconcile re-emits (absorbed by the request_id dedup)
    repopulate live state.
    """
    from nats.js.api import DeliverPolicy

    return DeliverPolicy.NEW


class ApprovalRequestsSubscriber:
    """Ephemeral push consumer on ``agents.approval.forge.>`` (AGENTS stream).

    The only new jarvis-side NATS consumer added by TASK-JNB-103. Binds
    the AGENTS stream where limits retention makes consumer overlap
    legal — it must never touch (or rebind) the PIPELINE stream's single
    ephemeral consumer (workqueue err_code 10100).

    Auto-ack, matching :class:`ForgeNotificationsSubscriber`'s
    convention — the handler never calls ``msg.ack()`` because
    ``manual_ack=False`` is the default and the JetStream context acks
    each delivery once the callback returns.

    Behaviour invariants:

    * ``start()`` idempotent; ``stop()`` bounded at ``stop_timeout``
      seconds and never raises.
    * The handler never raises into the JetStream callback (DDR-007):
      malformed envelopes/payloads log WARNING and continue.
    * Subject gate: only exact 4-token subjects
      (``agents.approval.forge.{build_id}``) are consumed. 5-token
      ``.response`` subjects — which the ``>`` wildcard also matches at
      the wire level, including TASK-JNB-104's own future publishes —
      are skipped structurally. (NATS subject tokens cannot contain
      ``.``, so a ``build_id`` can never split into extra tokens.)
    * ``build_id`` is the 4th subject token — ``ApprovalRequestPayload``
      carries no build_id field; the subject template
      ``agents.approval.forge.{build_id}`` is the join contract (it is
      also exactly the ``approval_subject`` forge places on
      ``BuildPausedPayload``).
    """

    __slots__ = (
        "_nats_client",
        "_notifier",
        "_planning_renderer",
        "_started",
        "_stop_timeout",
        "_subscription",
    )

    def __init__(
        self,
        nats_client: NATSClient,
        notifier: SlackNotifier | None,
        *,
        planning_renderer: Any | None = None,
        stop_timeout: float = 5.0,
    ) -> None:
        """Construct the subscriber.

        Args:
            nats_client: A connected :class:`NATSClient` whose ``js``
                property exposes the JetStream context. The subscriber
                does not own the connection.
            notifier: The live :class:`SlackNotifier` receiving captured
                *build-pause* approval requests, or ``None`` when only the
                planning dialogue (TASK-SPL003-J02) is configured (a NoOp
                forge sink has no button surface to feed). Build-pause
                capture is skipped when this is ``None``.
            planning_renderer: Optional
                :class:`~jarvis.infrastructure.assumption_dialogue.PlanningCheckpointRenderer`
                (TASK-SPL003-J02). When present, a planning-assumption
                checkpoint (``details.checkpoint_type`` starts ``product_docs``)
                is rendered as a per-assumption dialogue at capture time and
                the request is NOT parked in ``_pending_approvals`` — the
                build-pause path stays byte-for-byte unchanged for every
                non-planning request.
            stop_timeout: Maximum seconds :meth:`stop` waits for the
                unsubscribe before returning unconditionally.
        """
        self._nats_client = nats_client
        self._notifier = notifier
        self._planning_renderer = planning_renderer
        self._stop_timeout = stop_timeout
        self._subscription: Any = None
        self._started = False

    async def start(self) -> None:
        """Subscribe to ``agents.approval.forge.>`` (idempotent)."""
        if self._started:
            return

        subject = _get_approval_request_subject()
        self._subscription = await self._nats_client.js.subscribe(
            subject,
            cb=self._on_message,
            ordered_consumer=False,
            deliver_policy=_get_deliver_policy_new(),
        )
        self._started = True
        logger.info("approval_requests_subscribed", subject=subject)

    async def stop(self) -> None:
        """Unsubscribe within ``stop_timeout``; never raises."""
        if not self._started:
            return

        sub = self._subscription
        self._started = False
        self._subscription = None

        if sub is None:
            return

        try:
            await asyncio.wait_for(sub.unsubscribe(), timeout=self._stop_timeout)
        except TimeoutError:
            logger.warning(
                "approval_requests_stop_timeout",
                timeout=self._stop_timeout,
            )
        except Exception as exc:
            logger.warning(
                "approval_requests_stop_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _on_message(self, msg: Msg) -> None:
        """JetStream callback — never raises (DDR-007)."""
        try:
            await self._handle_message(msg)
        except Exception as exc:
            # Defensive backstop mirroring
            # ForgeNotificationsSubscriber._on_message: every legitimate
            # drop path inside _handle_message already logs and returns.
            logger.warning(
                "approval_request_dropped_handler_error",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _handle_message(self, msg: Msg) -> None:
        """Validate and capture one approval request. Never raises.

        Drop conditions (all WARNING-or-debug + continue, DDR-007):

        * Non-4-token subject (``.response`` traffic, unexpected shapes)
          → debug, skip.
        * Malformed envelope → WARN ``approval_request_dropped_malformed``.
        * ``event_type != approval_request`` → debug, skip (the wildcard
          legally matches other agents-domain traffic shapes).
        * Malformed ``ApprovalRequestPayload`` → WARN
          ``approval_request_dropped_bad_payload``.
        """
        # Local import keeps schema-only consumers free of the nats_core
        # import chain (schema-import-isolation invariant).
        from nats_core import MessageEnvelope

        tokens = msg.subject.split(".")
        if len(tokens) != 4:
            # 5-token subjects are approval *responses*
            # (agents.approval.forge.{build_id}.response) — never a
            # request; skipping on token count keeps TASK-JNB-104's own
            # publishes out of this handler structurally.
            logger.debug(
                "approval_request_skipped_subject",
                subject=msg.subject,
            )
            return

        try:
            envelope = MessageEnvelope.model_validate_json(msg.data)
        except (ValidationError, ValueError) as exc:
            logger.warning(
                "approval_request_dropped_malformed",
                subject=msg.subject,
                error_class=type(exc).__name__,
                error=str(exc),
            )
            return

        if envelope.event_type != "approval_request":
            logger.debug(
                "approval_request_skipped_event_type",
                subject=msg.subject,
                event_type=str(envelope.event_type),
            )
            return

        from nats_core.events import ApprovalRequestPayload

        try:
            payload = ApprovalRequestPayload.model_validate(envelope.payload)
        except ValidationError as exc:
            logger.warning(
                "approval_request_dropped_bad_payload",
                subject=msg.subject,
                error_class=type(exc).__name__,
                error=str(exc),
            )
            return

        # TASK-SPL003-J02 — planning-assumption checkpoint branch. Detection is
        # by ``details.checkpoint_type`` (ASSUM-002), never by parsing the
        # ``plan-<cid>`` run-id out of the subject. A planning checkpoint is
        # rendered at CAPTURE TIME (this is the only place ``payload.details``,
        # where the assumptions live, is available — ``capture_approval_request``
        # discards it) as a per-assumption dialogue, and the request is NEVER
        # parked in ``_pending_approvals``. Everything below stays byte-for-byte
        # unchanged for non-planning requests (the ~112 build-pause tests).
        from jarvis.infrastructure.assumption_dialogue import is_planning_checkpoint

        if is_planning_checkpoint(payload.details):
            if self._planning_renderer is not None:
                # render() never raises (DDR-007).
                await self._planning_renderer.render(
                    details=payload.details,
                    correlation_id=envelope.correlation_id,
                    request_id=payload.request_id,
                    approval_subject=msg.subject,
                )
            else:
                logger.debug(
                    "approval_request_planning_no_renderer",
                    subject=msg.subject,
                    correlation_id=envelope.correlation_id,
                )
            return

        # Build-pause capture path. Skipped when no forge sink is wired (a
        # planning-only deployment): the request simply is not captured.
        if self._notifier is None:
            logger.debug(
                "approval_request_no_sink_dropped",
                subject=msg.subject,
                correlation_id=envelope.correlation_id,
            )
            return

        # capture_approval_request never raises (DDR-007).
        await self._notifier.capture_approval_request(
            request_id=payload.request_id,
            build_id=tokens[3],
            correlation_id=envelope.correlation_id,
            approval_subject=msg.subject,
            timeout_seconds=float(payload.timeout_seconds),
        )


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
    "ApprovalRequestsSubscriber",
    "NoOpSink",
    "NotificationSink",
    "PendingApproval",
    "SlackNotifier",
    "build_pause_blocks",
    "create_slack_sink",
]
