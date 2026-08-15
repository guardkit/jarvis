"""jarvis.notification.slack return channel for the Sovereign Planning Loop.

FEAT-SPL-003 (TASK-SPL003-J01) — the *first deliverable*. forge Mode P
core-publishes ``NotificationPayload`` to ``jarvis.notification.slack``
(``forge/src/forge/cli/_serve_planning.py``); before this consumer, jarvis had
no subscriber anywhere, so the JARVIS stream (``jarvis.>``, limits retention,
1h / 1000 msgs) let every planning notification to the human evaporate unread.

This module renders each notification into the *originating Slack thread* and
degrades to a top-level planning-channel post when no thread anchor is present —
**never dropping** a valid notification. It ships and works against the live
forge today: forge currently emits a bare ``NotificationPayload`` (no anchor),
so the degrade path is the live path until the forge half (TASK-SPL003F-001)
projects ``parent_request_id`` / ``target_user`` into outbound payloads.

Design (DD-SPL003-1 round-trip; jarvis holds **zero** mapping state — the thread
anchor travels in the payload, projected from forge SQLite ``planning_runs``):

* **Ephemeral NEW push consumer** (ASSUM-007 override → DDR-027 pattern, NOT
  durable). The JARVIS stream is limits-retention, so ``DeliverPolicy.NEW``
  overlap is legal (contrast the workqueue PIPELINE stream's ``ALL`` story in
  ``forge_notifications.py``). Restart-survival is by construction: a fresh
  consumer threads correctly off the next payload's own anchor.
* **Manual ack, ack-after-post** (build-time refinement R2 of ASSUM-007): an
  auto-ack-on-delivery consumer would lose a valid notification whose Slack post
  transiently fails. Instead: ``msg.ack()`` after a successful post or a
  logged-skip of a malformed message; ``msg.nak()`` (bounded by ``_MAX_DELIVER``)
  on a transient post failure so JetStream redelivers within the retention
  window; ack + loud ERROR on redelivery exhaustion. Never a silent drop, no
  redelivery storm. Still ephemeral / NEW — no durable replay across restart.
* **Best-effort in-process dedup** keyed on the envelope's globally-unique
  ``message_id`` (build-time refinement R1 of ASSUM-008): a burst shares
  ``correlation_id``, so keying on ``correlation_id + timestamp`` could drop a
  distinct notification (never-drop + burst-order violation). ``message_id`` is
  uuid4 and redelivery-stable — perfect dedup, never a false drop.
* **Ordering**: each delivery is processed to completion (awaited post) before
  the next; posts are never fanned into ``asyncio.create_task`` — so a burst for
  one run renders in publication order.
* **Never raises** (DDR-007): a handler bug logs and the message is acked (a
  poison message must not wedge the consumer).

No reasoning anywhere on this path — render and post only (intake-only discipline
extended to output, ASSUM-013).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.build_audience import BuildAudienceRegistry
    from jarvis.infrastructure.nats_client import NATSClient

logger = structlog.get_logger(__name__)

# 429 retry budget for the shared threaded-post helper (JNB-006 parity).
_MAX_429_RETRIES = 3

# Redelivery bound for a valid-but-unpostable notification (never-drop within
# retention, no storm). ack + ERROR once ``num_delivered`` reaches this.
_MAX_DELIVER = 5

# Delay before a NAK'd notification is redelivered.
_NAK_DELAY_SECONDS = 5.0

# Dedup window / cap (JNB-103 / intake precedent).
_DEDUP_TTL_SECONDS = 300.0
_DEDUP_MAX_ENTRIES = 1000

# Severity prefix from NotificationPayload.level (ASSUM-013).
_LEVEL_PREFIX: dict[str, str] = {"info": "", "warning": "⚠️ ", "error": "❌ "}

# Injectable monotonic-clock seam — tests patch THIS alias, never time.monotonic
# (patching the stdlib attribute freezes the event-loop clock; intake precedent).
_monotonic = time.monotonic


def _notification_subject() -> str:
    """Lazy-derive ``jarvis.notification.slack`` from ``nats_core.Topics``.

    Imported lazily so schema-only consumers of this module never pull the
    ``nats_core`` / ``nats`` import chain (schema-import-isolation convention).
    """
    from nats_core import Topics

    return Topics.Jarvis.NOTIFICATION.format(adapter="slack")


def _deliver_policy_new() -> Any:
    """Lazy-load ``nats.js.api.DeliverPolicy.NEW`` (ASSUM-007 ephemeral NEW)."""
    from nats.js.api import DeliverPolicy

    return DeliverPolicy.NEW


async def post_threaded(
    web_client: Any,
    *,
    channel: str,
    text: str,
    thread_ts: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    mrkdwn: bool = True,
    correlation_id: str | None = None,
) -> Any | None:
    """One ``chat.postMessage`` with the 429/``Retry-After`` budget.

    The shared threaded-post primitive for FEAT-SPL-003 (J01/J02/J03) — unlike
    ``SlackNotifier._post_with_retry`` it is parameterised on ``channel`` **and**
    ``thread_ts`` (that method hardcodes the forge-notification channel and
    cannot thread). Never raises; returns the Slack response on success and
    ``None`` when delivery failed or the retry budget was exhausted.

    Args:
        web_client: A Slack ``AsyncWebClient`` (or ``None`` → logged no-op).
        channel: Target channel id.
        text: Fallback / body text.
        thread_ts: Thread timestamp to reply into, or ``None`` for a top-level
            post (the degrade path).
        blocks: Optional Block Kit blocks (``text`` remains the fallback).
        mrkdwn: Slack markdown rendering for the text body.
        correlation_id: For log correlation only.

    Returns:
        The Slack response on success, or ``None`` on any failure.
    """
    if web_client is None:
        return None
    if not channel:
        logger.warning("planning_notification_post_no_channel", correlation_id=correlation_id)
        return None

    from slack_sdk.errors import SlackApiError

    attempts_left = _MAX_429_RETRIES + 1
    while attempts_left > 0:
        try:
            kwargs: dict[str, Any] = {"channel": channel, "text": text, "mrkdwn": mrkdwn}
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            if blocks is not None:
                kwargs["blocks"] = blocks
            return await web_client.chat_postMessage(**kwargs)
        except SlackApiError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 429:
                attempts_left -= 1
                if attempts_left > 0:
                    retry_after = exc.response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else 1.0
                    except (TypeError, ValueError):
                        delay = 1.0
                    logger.warning(
                        "planning_notification_429_backoff",
                        correlation_id=correlation_id,
                        retry_after=delay,
                        retries_left=attempts_left - 1,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        "planning_notification_429_budget_exhausted",
                        correlation_id=correlation_id,
                        error=str(exc),
                    )
                    return None
            else:
                logger.warning(
                    "planning_notification_post_failed",
                    correlation_id=correlation_id,
                    error=str(exc),
                    error_class=type(exc).__name__,
                )
                return None
        except Exception as exc:  # pragma: no cover - defensive catch-all
            logger.warning(
                "planning_notification_post_unexpected_error",
                correlation_id=correlation_id,
                error=str(exc),
                error_class=type(exc).__name__,
            )
            return None
    return None


class PlanningNotificationConsumer:
    """Ephemeral NEW push consumer on ``jarvis.notification.slack``.

    Never raises into the JetStream callback (DDR-007). Constructed via
    :func:`create_planning_notification_consumer`.
    """

    __slots__ = (
        "_audience",
        "_channel_id",
        "_nats_client",
        "_seen",
        "_started",
        "_stop_timeout",
        "_subscription",
        "_web_client",
    )

    def __init__(
        self,
        nats_client: NATSClient,
        *,
        channel_id: str,
        web_client: Any,
        stop_timeout: float = 5.0,
        audience: BuildAudienceRegistry | None = None,
    ) -> None:
        """See :func:`create_planning_notification_consumer` (the factory)."""
        self._nats_client = nats_client
        self._channel_id = channel_id
        self._web_client = web_client
        # Build-side mention lane (2026-08-15): this consumer is the only
        # place in jarvis that ever learns which member id the owner is
        # for a given run — forge puts it on ``target_user``. Recording it
        # here is what lets the BUILD-side line (a different subscriber,
        # same process) @-mention the same person when the build ends.
        # ``None`` (unwired) records nothing; build lines then fall
        # through the rest of the mention chain.
        self._audience = audience
        self._stop_timeout = stop_timeout
        self._subscription: Any = None
        self._started = False
        # Dedup: message_id -> monotonic expiry. In-process only (ADR-ARCH-004);
        # a duplicate arriving after a restart may re-render — accepted (ASSUM-008).
        self._seen: dict[str, float] = {}

    async def start(self) -> None:
        """Subscribe (idempotent) — ephemeral NEW push, manual ack."""
        if self._started:
            return
        subject = _notification_subject()
        self._subscription = await self._nats_client.js.subscribe(
            subject,
            cb=self._on_message,
            manual_ack=True,
            ordered_consumer=False,
            deliver_policy=_deliver_policy_new(),
        )
        self._started = True
        logger.info("planning_notification_consumer_subscribed", subject=subject)

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
                "planning_notification_consumer_stop_timeout", timeout=self._stop_timeout
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "planning_notification_consumer_stop_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _on_message(self, msg: Any) -> None:
        """JetStream callback — never raises (DDR-007)."""
        try:
            await self._handle(msg)
        except Exception as exc:
            # A handler bug must not wedge the consumer. Ack so the poison
            # message is not redelivered forever; the failure is logged loudly.
            logger.warning(
                "planning_notification_handler_error",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            await self._safe_ack(msg)

    async def _handle(self, msg: Any) -> None:
        # Local imports keep the nats_core chain off the cold import path.
        from nats_core import MessageEnvelope
        from nats_core.events import NotificationPayload
        from pydantic import ValidationError

        # --- parse envelope + payload (malformed → logged skip + ack) --------
        try:
            envelope = MessageEnvelope.model_validate_json(msg.data)
        except (ValidationError, ValueError) as exc:
            logger.warning(
                "planning_notification_skipped",
                reason="malformed_envelope",
                error_class=type(exc).__name__,
            )
            await self._safe_ack(msg)
            return

        if str(getattr(envelope.event_type, "value", envelope.event_type)) != "notification":
            # The subject is exact, but be defensive: ack + skip non-notifications.
            await self._safe_ack(msg)
            return

        try:
            payload = NotificationPayload.model_validate(envelope.payload)
        except ValidationError as exc:
            logger.warning(
                "planning_notification_skipped",
                reason="malformed_payload",
                correlation_id=envelope.correlation_id,
                error_class=type(exc).__name__,
            )
            await self._safe_ack(msg)
            return

        # --- dedup on the globally-unique message_id (R1) --------------------
        key = envelope.message_id or f"{envelope.correlation_id}:{envelope.timestamp}"
        if not self._mark_if_new(key):
            logger.info(
                "planning_notification_duplicate_dropped",
                message_id=key,
                correlation_id=envelope.correlation_id,
            )
            await self._safe_ack(msg)
            return

        # --- remember who this run's notifications speak to (mention lane) --
        self._record_audience(payload, envelope)

        # --- render + post (thread when anchored, else degrade top-level) ----
        thread_ts = payload.parent_request_id or payload.thread_ts
        text, blocks = self._render(payload)
        response = await post_threaded(
            self._web_client,
            channel=self._channel_id,
            text=text,
            thread_ts=thread_ts,
            blocks=blocks,
            correlation_id=payload.correlation_id,
        )

        if response is None:
            # Valid notification, post failed: NAK for redelivery (never drop),
            # bounded so a permanently-unpostable message can't storm.
            num_delivered = self._num_delivered(msg)
            if num_delivered >= _MAX_DELIVER:
                logger.error(
                    "planning_notification_delivery_exhausted",
                    correlation_id=payload.correlation_id,
                    message_id=key,
                    num_delivered=num_delivered,
                    detail="giving up after max redeliveries; message not rendered",
                )
                await self._safe_ack(msg)
            else:
                # Un-mark so the redelivery is not treated as a duplicate.
                self._seen.pop(key, None)
                await self._safe_nak(msg)
            return

        logger.info(
            "planning_notification_rendered",
            correlation_id=payload.correlation_id,
            threaded=bool(thread_ts),
            channel=self._channel_id,
        )
        await self._safe_ack(msg)

    def _record_audience(self, payload: Any, envelope: Any) -> None:
        """Record ``correlation_id -> target_user`` for the build-side mention.

        Never raises (DDR-007): a registry failure must not cost the
        operator the notification that is about to post. A payload with no
        ``target_user``, or no correlation to key on, is a silent no-op —
        the registry's own write guard covers both, this wrapper covers a
        registry that throws.
        """
        if self._audience is None:
            return
        try:
            correlation_id = payload.correlation_id or getattr(envelope, "correlation_id", None)
            self._audience.record_planning_target(correlation_id, payload.target_user)
        except Exception as exc:  # pragma: no cover - defensive backstop
            logger.warning(
                "planning_notification_audience_record_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    def _render(self, payload: Any) -> tuple[str, list[dict[str, Any]] | None]:
        """Build (text, blocks) for a notification (ASSUM-013 copy).

        Severity prefix from level, the message verbatim (no jarvis reasoning),
        the correlation id in monospace, an optional @-mention of ``target_user``.
        ``payload.blocks`` pass through when present (text remains the fallback).
        """
        prefix = _LEVEL_PREFIX.get(str(payload.level), "")
        mention = f"<@{payload.target_user}> " if payload.target_user else ""
        text = f"{mention}{prefix}{payload.message}\n`{payload.correlation_id}`"
        blocks = payload.blocks if payload.blocks else None
        return text, blocks

    # ------------------------------------------------------------------
    # Dedup — bounded, monotonic, evict-on-insert (intake precedent)
    # ------------------------------------------------------------------

    def _mark_if_new(self, key: str) -> bool:
        now = _monotonic()
        expired = [k for k, deadline in self._seen.items() if deadline <= now]
        for stale in expired:
            del self._seen[stale]
        if key in self._seen:
            return False
        if len(self._seen) >= _DEDUP_MAX_ENTRIES:
            oldest = min(self._seen, key=self._seen.__getitem__)
            del self._seen[oldest]
        self._seen[key] = now + _DEDUP_TTL_SECONDS
        return True

    # ------------------------------------------------------------------
    # Manual-ack helpers — never raise
    # ------------------------------------------------------------------

    @staticmethod
    def _num_delivered(msg: Any) -> int:
        try:
            return int(msg.metadata.num_delivered)
        except Exception:  # pragma: no cover - defensive
            return 1

    @staticmethod
    async def _safe_ack(msg: Any) -> None:
        try:
            await msg.ack()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("planning_notification_ack_failed", error=str(exc))

    @staticmethod
    async def _safe_nak(msg: Any) -> None:
        try:
            await msg.nak(delay=_NAK_DELAY_SECONDS)
        except TypeError:  # pragma: no cover - older nats-py without delay kwarg
            try:
                await msg.nak()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("planning_notification_nak_failed", error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("planning_notification_nak_failed", error=str(exc))


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_planning_notification_consumer(
    config: JarvisConfig,
    nats_client: NATSClient | None,
    *,
    audience: BuildAudienceRegistry | None = None,
) -> PlanningNotificationConsumer | None:
    """Create the notification consumer, or a logged no-op (``None``).

    No-op conditions (each logged; DDR-021 posture; the consumer's availability
    depends ONLY on its own config, independent of the forge-notification sink —
    arch F2: the planning dialogue must not go dark when only the planning
    channel is configured):

    * ``nats_client is None`` — nothing to consume.
    * ``slack_planning_channel_id`` unset/blank — no render target.
    * ``slack_bot_token`` unset — no web client for ``chat.*``.

    Returns:
        A ready :class:`PlanningNotificationConsumer`, or ``None``.
    """
    if nats_client is None:
        logger.info(
            "planning_notification_consumer_no_op",
            reason="NATS unavailable; planning notification consumer disabled",
        )
        return None

    channel_id = (config.slack_planning_channel_id or "").strip() or None
    if not channel_id:
        logger.info(
            "planning_notification_consumer_no_op",
            reason="slack_planning_channel_id not configured; disabled",
        )
        return None

    bot_token = config.slack_bot_token
    if bot_token is None or not bot_token.get_secret_value():
        logger.info(
            "planning_notification_consumer_no_op",
            reason="slack_bot_token not configured; disabled",
        )
        return None

    from slack_sdk.web.async_client import AsyncWebClient

    web_client = AsyncWebClient(token=bot_token.get_secret_value())
    consumer = PlanningNotificationConsumer(
        nats_client,
        channel_id=channel_id,
        web_client=web_client,
        audience=audience,
    )
    logger.info("planning_notification_consumer_configured", channel_id=channel_id)
    return consumer


__all__ = [
    "PlanningNotificationConsumer",
    "create_planning_notification_consumer",
    "post_threaded",
]
