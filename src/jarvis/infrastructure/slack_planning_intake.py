"""Slack planning intake for the Sovereign Planning Loop (TASK-SPL-J01).

FEAT-SPL-001: a free-text message posted by an identity-pinned originator in
the dedicated planning channel becomes a ``PlanningQueuedPayload`` published
to ``pipeline.planning-queued.{correlation_id}`` on the PIPELINE stream, with
a best-effort in-thread acknowledgement. Jarvis does NO reasoning on this
path — the DeepAgents graph never sees intake (SPL scope §5); forge Mode P
(FEAT-SPL-002) is the consumer, per Pattern A (publish and walk away,
ADR-SP-014).

The module mirrors ``slack_reply.py``'s shapes: a never-raises handler class,
a publisher Protocol seam, and a no-op factory. It rides the same Socket Mode
connection as the approval reply path — TASK-SPL-J02 routes ``events_api``
requests here from inside the single ack-first listener.

Behaviour invariants (TASK-REV-3240 findings F3-F6, F10-F12):

* Gate order is load-bearing (F3): event-type -> channel -> bot/subtype
  (DEBUG drop — modern bot posts are SUBTYPE-FREE with ``bot_id`` set, so the
  bot gate keys on ``bot_id``/``app_id`` presence and runs BEFORE the
  identity gate; jarvis's own acks must never be counted as refusals) ->
  thread (top-level only) -> originator identity (the ONLY refusal log, at
  INFO — channel messages are a member-triggerable flood vector, F11) ->
  blank text -> dedup -> ValidationError backstop.
* Dedup check-and-mark is synchronous — no ``await`` between them (F5): the
  SDK dispatches each WS message as its own task, so a Socket Mode
  redelivery can run concurrently with the original. The entry is un-marked
  ONLY on publish failure (nothing was locally confirmed queued) — the
  JNB-104 discard-on-publish-failure posture. NB the un-mark helps only the
  narrow not-yet-acked redelivery window (ack failure/reconnect): ack-first
  means Slack normally never redelivers, so the PRIMARY recovery is the
  in-thread failure notice inviting a repost. A ``ValidationError`` keeps
  the mark (a redelivery would fail identically). State is in-process and
  lost on restart by design (ADR-ARCH-004 / ASSUM-005). At-least-once
  caveat: a bounded-timeout publish "failure" may still have durably landed
  on the stream (the PUB frame can flush before the local cancel), so a
  repost after the failure notice can yield two planning runs with
  different correlation ids — ``parent_request_id`` (the Slack ts) is the
  stable key Mode P can dedup on if this ever bites (FEAT-SPL-002 note).
* ``originating_adapter="slack"`` is hard-coded (F4): the wire layer
  verifiably skips its required-when-jarvis validator when the field is
  omitted, so jarvis must never rely on it.
* Log hygiene (F6): no log record on any path carries the message text —
  records are metadata-only ({channel, ts, user_id, event_id,
  correlation_id, text_length, reason}). ``request_text`` goes to JetStream
  verbatim (modulo the contract's outer-whitespace strip, F10) and nowhere
  else. Exception detail is rendered via :func:`_safe_error_detail`, which
  suppresses pydantic ``ValidationError`` bodies (they embed input values,
  i.e. the message text) and caps everything else.

* Event naming: factory-level events mirror the ``slack_reply`` factory
  convention (``slack_planning_intake_no_op`` / ``_configured``); runtime
  handler events use the feature prefix (``planning_intake_*``).
* DDR-007/C2: nothing raises into the Socket Mode client. The publish is
  authoritative; the threaded ack and the publish-failure notice are each
  independently wrapped best-effort ``chat.postMessage`` calls, and success
  is never acked before the publish returns (an acked-but-unqueued idea
  would be a silent loss).
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from jarvis.tools._correlation import new_correlation_id

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.nats_client import NATSClient

logger = structlog.get_logger(__name__)

# Dedup window — matches Slack's practical Socket Mode redelivery window and
# the JNB-103 precedent (slack_notifier._DEDUP_TTL_SECONDS).
_DEDUP_TTL_SECONDS = 300.0

# Hard cap on the dedup map (evict-oldest-deadline past this) — bounded
# in-process state per ADR-ARCH-004; a module constant, not config (JNB-103
# precedent).
_DEDUP_MAX_ENTRIES = 1000

# Fallback publish timeout — the factory injects
# ``config.pipeline_publish_timeout_seconds`` (DDR-025); this default only
# covers direct construction in tests.
_DEFAULT_PUBLISH_TIMEOUT_SECONDS = 5.0

# Injectable monotonic-clock seam. Tests MUST patch this alias
# (jarvis.infrastructure.slack_planning_intake._monotonic) instead of
# time.monotonic — patching the shared stdlib attribute freezes asyncio's
# event-loop clock and hangs the whole test process.
_monotonic = time.monotonic


def parse_originator_ids(raw: str | None) -> frozenset[str]:
    """Parse the configured originator member id(s) into a frozenset.

    Allow-list-ready (TASK-REV-3240 / ASSUM-001 hedge): the setting accepts a
    comma-separated list, though v1 is documented and operated as a single
    id. Blank segments are dropped; surrounding whitespace is stripped (the
    JNB-107 lesson — a mis-copied trailing space must not silently refuse
    every post).

    Args:
        raw: The raw ``slack_planning_originator_user_id`` setting value.

    Returns:
        The parsed member ids; empty when the setting is unset or blank.
    """
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _safe_error_detail(exc: BaseException) -> str:
    """Exception detail that can never leak the message text (F6).

    pydantic ``ValidationError`` messages embed the offending INPUT values —
    for this module that means ``request_text`` — so they are reduced to
    their error count; everything else (transport/timeout/slack-sdk errors,
    which carry no user text on this path) is rendered and capped.
    """
    from pydantic import ValidationError

    if isinstance(exc, ValidationError):
        return f"{exc.error_count()} validation error(s); detail suppressed (log hygiene)"
    return str(exc)[:500]


def _requested_at_from_ts(ts: str | None) -> datetime:
    """UTC datetime from a Slack epoch-string ``ts``, UTC-now on failure.

    Slack timestamps are strings like ``"1751795701.000200"``. Defensive per
    the never-raises discipline (F12) — a malformed ts must not cost the
    intake, so the fallback is the observation time.
    """
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError, OSError):
        return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Publisher seam
# ---------------------------------------------------------------------------


class PlanningQueuedPublisher(Protocol):
    """Seam for publishing a planning-queued request to the fleet bus."""

    async def publish(
        self,
        *,
        subject: str,
        payload: Any,
        correlation_id: str,
    ) -> None:
        """Publish one ``PlanningQueuedPayload`` to ``subject``.

        Raises on failure — the handler's publish-failure path needs to
        observe the error to un-mark dedup and post the failure notice.
        """
        ...


class NatsPlanningQueuedPublisher:
    """JetStream-backed :class:`PlanningQueuedPublisher`.

    Wraps the payload in the canonical ``MessageEnvelope``
    (``source_id="jarvis"``, ``event_type="planning_queued"``) and publishes
    with a bounded timeout (DDR-025). The timeout comes from
    ``config.pipeline_publish_timeout_seconds`` via the factory — NOT from
    ``dispatch._resolve_publish_timeout`` (a private seam of that module).
    Publish-only: this module never creates any NATS consumer.
    """

    __slots__ = ("_nats_client", "_timeout_seconds")

    def __init__(
        self,
        nats_client: NATSClient,
        *,
        timeout_seconds: float = _DEFAULT_PUBLISH_TIMEOUT_SECONDS,
    ) -> None:
        self._nats_client = nats_client
        self._timeout_seconds = timeout_seconds

    async def publish(
        self,
        *,
        subject: str,
        payload: Any,
        correlation_id: str,
    ) -> None:
        """Publish; raises on any transport failure (caller handles)."""
        # Local imports keep the nats_core chain off this module's cold
        # import path (schema-import-isolation convention).
        from nats_core import EventType, MessageEnvelope

        envelope = MessageEnvelope(
            source_id="jarvis",
            event_type=EventType.PLANNING_QUEUED,
            correlation_id=correlation_id,
            payload=payload.model_dump(mode="json"),
        )
        await asyncio.wait_for(
            self._nats_client.js.publish(subject, envelope.model_dump_json().encode("utf-8")),
            timeout=self._timeout_seconds,
        )


# ---------------------------------------------------------------------------
# Intake handler
# ---------------------------------------------------------------------------


class PlanningIntakeHandler:
    """Processes ``events_api`` message envelopes (post-ack).

    Never raises (DDR-007). Constructed via
    :func:`create_slack_planning_intake_handler`.
    """

    __slots__ = (
        "_channel_id",
        "_originator_ids",
        "_publisher",
        "_seen_events",
        "_web_client",
    )

    def __init__(
        self,
        *,
        channel_id: str,
        originator_ids: frozenset[str],
        publisher: PlanningQueuedPublisher,
        web_client: Any | None = None,
    ) -> None:
        """See :func:`create_slack_planning_intake_handler` (the factory)."""
        self._channel_id = channel_id
        self._originator_ids = originator_ids
        self._publisher = publisher
        self._web_client = web_client
        # Dedup map: event key -> monotonic expiry deadline. In-process only
        # (ADR-ARCH-004/ASSUM-005); a restart inside Slack's redelivery
        # window may re-queue one event — accepted, low-stakes.
        self._seen_events: dict[str, float] = {}

    async def handle_message_event(self, payload: dict[str, Any]) -> None:
        """Handle one ``events_api`` envelope payload. Never raises."""
        try:
            await self._handle(payload)
        except Exception as exc:
            # DDR-007 backstop — a handler bug must not reach the Socket
            # Mode client or the supervisor loop.
            logger.warning(
                "planning_intake_handler_error",
                error_class=type(exc).__name__,
                error=_safe_error_detail(exc),
            )

    async def _handle(self, payload: dict[str, Any]) -> None:
        event = payload.get("event") or {}
        if event.get("type") != "message":
            return

        channel = event.get("channel")
        ts = event.get("ts")
        event_id = payload.get("event_id")

        # --- 1. Channel gate — one dedicated intake surface --------------
        if channel != self._channel_id:
            return

        # --- 2. Bot/subtype gate — loop prevention, BEFORE identity (F3) -
        # Modern bot-token posts (including jarvis's own threaded acks)
        # arrive subtype-free with bot_id set; subtyped events cover edits,
        # deletions, and legacy bot_message. DEBUG — never a "refusal".
        if event.get("subtype") or event.get("bot_id") or event.get("app_id"):
            logger.debug(
                "planning_intake_bot_or_subtype_dropped",
                channel=channel,
                ts=ts,
                event_id=event_id,
                subtype=event.get("subtype"),
            )
            return

        # --- 3. Thread gate — top-level messages only (ASSUM-006) --------
        # Thread conversation becomes meaningful with FEAT-SPL-003's
        # assumption dialogue, not here.
        if event.get("thread_ts"):
            return

        # --- 4. Originator identity gate — the ONLY refusal log (F3/F11) -
        # event["user"] is set server-side by Slack from the authenticated
        # session; missing user is a drop, never a crash or a pass.
        user_id = event.get("user")
        if not user_id or user_id not in self._originator_ids:
            logger.info(
                "planning_intake_unauthorized_dropped",
                user_id=user_id,
                channel=channel,
                ts=ts,
                event_id=event_id,
            )
            return

        # --- 5. Blank-text pre-check (F10) --------------------------------
        # The contract rejects blank request_text; filter it here so the
        # outcome is a clean logged discard, not a ValidationError.
        text = event.get("text") or ""
        if not text.strip():
            logger.info(
                "planning_intake_blank_dropped",
                user_id=user_id,
                channel=channel,
                ts=ts,
                event_id=event_id,
            )
            return

        # --- 6. Dedup — synchronous check-and-mark, no await between (F5) -
        dedup_key = event_id or f"{channel}:{ts}"
        if not self._mark_if_new(dedup_key):
            logger.info(
                "planning_intake_duplicate_dropped",
                event_id=dedup_key,
                channel=channel,
                ts=ts,
            )
            return

        # --- 7. Payload construction (ASSUM-008 field mapping) ------------
        from nats_core import Topics
        from nats_core.events import PlanningQueuedPayload
        from pydantic import ValidationError

        correlation_id = new_correlation_id()
        try:
            planning = PlanningQueuedPayload(
                request_text=text,
                target_repo=None,
                triggered_by="jarvis",
                # Explicit constant (F4): the wire layer skips its
                # required-when-jarvis validator when this field is omitted.
                originating_adapter="slack",
                originating_user=user_id,
                correlation_id=correlation_id,
                parent_request_id=ts,
                requested_at=_requested_at_from_ts(ts),
                # Stamped at construction, microseconds before the publish
                # call — the closest the immutable wire bytes can get to the
                # contract's "when published".
                queued_at=datetime.now(UTC),
            )
        except ValidationError as exc:
            # Backstop — a redelivery would fail identically, so the dedup
            # mark stays. Metadata only (F6).
            logger.info(
                "planning_intake_invalid_dropped",
                event_id=dedup_key,
                channel=channel,
                ts=ts,
                user_id=user_id,
                text_length=len(text),
                reason=type(exc).__name__,
            )
            return

        # --- 8. Publish (authoritative), then best-effort ack -------------
        subject = Topics.Pipeline.PLANNING_QUEUED.format(correlation_id=correlation_id)
        try:
            await self._publisher.publish(
                subject=subject,
                payload=planning,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            # Nothing was queued: un-mark so a Slack redelivery may retry
            # (JNB-104 discard-on-publish-failure posture), then tell the
            # originator in-thread — a silent loss is the one unacceptable
            # outcome (spec Group D scenario 1).
            logger.warning(
                "planning_intake_publish_failed",
                subject=subject,
                correlation_id=correlation_id,
                event_id=dedup_key,
                error_class=type(exc).__name__,
                error=_safe_error_detail(exc),
            )
            self._seen_events.pop(dedup_key, None)
            await self._post_thread(
                channel=channel,
                thread_ts=ts,
                text=(
                    "Planning intake could not queue this idea (the pipeline "
                    "is unavailable). Please repost it later."
                ),
                log_event="planning_intake_failure_notice_failed",
            )
            return

        logger.info(
            "planning_intake_queued",
            subject=subject,
            correlation_id=correlation_id,
            channel=channel,
            ts=ts,
            user_id=user_id,
            event_id=dedup_key,
            text_length=len(text),
        )

        # Ack AFTER the publish returned — never before (an acked-but-
        # unqueued idea would be a silent loss). Best-effort: a failed ack
        # never undoes the queued request (spec Group D scenario 3).
        await self._post_thread(
            channel=channel,
            thread_ts=ts,
            text=f"Queued for planning · `{correlation_id}`",
            log_event="planning_intake_ack_failed",
        )

    # ------------------------------------------------------------------
    # Dedup map — bounded, monotonic, evict-on-insert (JNB-103 precedent)
    # ------------------------------------------------------------------

    def _mark_if_new(self, key: str) -> bool:
        """Synchronous check-and-mark; True when ``key`` is fresh."""
        now = _monotonic()
        expired = [k for k, deadline in self._seen_events.items() if deadline <= now]
        for stale in expired:
            del self._seen_events[stale]
        if key in self._seen_events:
            return False
        if len(self._seen_events) >= _DEDUP_MAX_ENTRIES:
            oldest = min(self._seen_events, key=self._seen_events.__getitem__)
            del self._seen_events[oldest]
        self._seen_events[key] = now + _DEDUP_TTL_SECONDS
        return True

    # ------------------------------------------------------------------
    # Slack side-effects — independently wrapped (C2)
    # ------------------------------------------------------------------

    async def _post_thread(
        self,
        *,
        channel: str | None,
        thread_ts: str | None,
        text: str,
        log_event: str,
    ) -> None:
        """One independently wrapped threaded ``chat.postMessage``.

        A ``None`` web client is a SILENT no-op (the factory already logged
        that configuration state at startup); an unresolvable channel/ts or
        a failed post is a logged no-op. The publish never depends on Slack
        UI calls succeeding (C2).
        """
        if self._web_client is None:
            return
        if not channel or not thread_ts:
            logger.warning(log_event, detail="channel or thread_ts unresolved")
            return
        try:
            await self._web_client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=text,
            )
        except Exception as exc:
            logger.warning(
                log_event,
                channel=channel,
                thread_ts=thread_ts,
                error_class=type(exc).__name__,
                error=_safe_error_detail(exc),
            )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_slack_planning_intake_handler(
    config: JarvisConfig,
    nats_client: NATSClient | None,
    web_client: Any | None,
) -> PlanningIntakeHandler | None:
    """Create the planning intake handler, or a logged no-op (``None``).

    No-op conditions (each logged with its reason, DDR-021 posture —
    TASK-REV-3240 F1: intake's availability depends ONLY on its own
    configuration, never on the approval reply path's operator id):

    * ``slack_planning_channel_id`` or ``slack_planning_originator_user_id``
      unset/blank — the feature's own gate.
    * ``slack_bot_token`` unset — no Socket Mode surface exists (and no web
      client for the in-thread ack contract).
    * ``nats_client is None`` — nothing to publish to.

    Args:
        config: The live :class:`JarvisConfig`.
        nats_client: The shared NATS client, or ``None`` when unavailable.
        web_client: The shared Slack ``AsyncWebClient`` (built by the
            connection factory from ``slack_bot_token``), or ``None`` —
            acks then degrade to logged no-ops while publishes still run.

    Returns:
        A ready :class:`PlanningIntakeHandler`, or ``None``.
    """
    # Strip once (review SPL-R1 — the JNB-107 verbatim-config lesson applied
    # to the channel too): a mis-copied trailing space would otherwise pass
    # every factory gate, echo invisibly in the startup log, and silently
    # drop every legitimate post at the (deliberately silent) channel gate.
    channel_id = (config.slack_planning_channel_id or "").strip() or None
    originator_ids = parse_originator_ids(config.slack_planning_originator_user_id)

    if not channel_id or not originator_ids:
        missing = []
        if not channel_id:
            missing.append("slack_planning_channel_id")
        if not originator_ids:
            missing.append("slack_planning_originator_user_id")
        logger.info(
            "slack_planning_intake_no_op",
            reason=f"{' and '.join(missing)} not configured; planning intake disabled",
        )
        return None

    bot_token = config.slack_bot_token
    if bot_token is None or not bot_token.get_secret_value():
        logger.info(
            "slack_planning_intake_no_op",
            reason="slack_bot_token not configured; planning intake disabled",
        )
        return None

    if nats_client is None:
        logger.info(
            "slack_planning_intake_no_op",
            reason="NATS unavailable; planning intake disabled",
        )
        return None

    # Config-drift guard (F7): intake in the notification channel would turn
    # every top-level operator message beside approval posts into a planning
    # run. Loud, not fatal — the operator may genuinely want one channel.
    if channel_id == config.slack_channel_id:
        logger.warning(
            "planning_intake_channel_matches_notification_channel",
            channel_id=channel_id,
            detail=(
                "JARVIS_SLACK_PLANNING_CHANNEL_ID equals JARVIS_SLACK_CHANNEL_ID; "
                "planning intake and forge notifications share a surface"
            ),
        )

    publisher = NatsPlanningQueuedPublisher(
        nats_client,
        timeout_seconds=float(config.pipeline_publish_timeout_seconds),
    )
    handler = PlanningIntakeHandler(
        channel_id=channel_id,
        originator_ids=originator_ids,
        publisher=publisher,
        web_client=web_client,
    )
    # Startup echo (F7): a mis-copied channel or member id fails silently
    # otherwise — the JNB-107 verbatim-identity lesson.
    logger.info(
        "slack_planning_intake_configured",
        channel_id=channel_id,
        originator_ids=sorted(originator_ids),
    )
    return handler


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "NatsPlanningQueuedPublisher",
    "PlanningIntakeHandler",
    "PlanningQueuedPublisher",
    "create_slack_planning_intake_handler",
    "parse_originator_ids",
]
