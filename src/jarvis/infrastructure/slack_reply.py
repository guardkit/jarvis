"""Slack Socket Mode reply path for forge approvals (TASK-JNB-104).

The Slack→forge direction of the FEAT-BF39 phone-approval loop —
``slack_notifier.py`` owns the forge→Slack direction (notify + capture +
Block Kit buttons); this module consumes those buttons' clicks:

* :func:`parse_button_value` — validates the BUTTON_METADATA value JSON
  produced by TASK-JNB-103 (``{request_id, build_id, correlation_id,
  approval_subject}``).
* :class:`ApprovalReplyHandler` (via :func:`build_reply_handler`) — the
  ``block_actions`` handler: operator-member-id authorization, local
  first-click-wins, ``ApprovalResponsePayload`` publish to
  ``approval_subject + ".response"``, and in-place ``chat.update``s.
* :class:`NatsApprovalResponsePublisher` — envelope + JetStream publish
  (AGENTS stream, limits retention — publish only; this module never
  creates any NATS consumer, and specifically never touches the PIPELINE
  stream's single ephemeral consumer).
* :class:`SlackSocketModeReplyClient` — lifecycle wrapper around
  slack-sdk's aiohttp ``SocketModeClient`` (outbound WebSocket — no
  public endpoint), constructed in ``lifecycle.build_app_state``.

Behaviour invariants (task ACs + Phase 2.5B review C1/C2):

* Every Socket Mode envelope is acked immediately — before any
  authorization, parsing, or publish work.
* The SOLE Slack-side authorization gate is
  ``payload["user"]["id"] == settings.slack_operator_user_id``; a
  mismatch is WARN + ephemeral refusal, nothing published.
* Local first-click-wins is a client-side courtesy only; forge's
  ``request_id`` dedup remains the authoritative guard (DDR-027 — this
  state is in-process and lost on restart by design). The
  check-and-mark is synchronous (no ``await`` between them): the SDK
  dispatches each WS message via ``asyncio.ensure_future``, so a
  double-click is two concurrent tasks.
* Jarvis implements NO approval-window/expiry checks — enforcement is
  exclusively forge-side; a stale click is safely refused there.
* DDR-007: nothing raises into the Socket Mode client or the supervisor
  event loop. EVERY ``chat.*`` call (ephemeral refusal,
  optimistic-disable, success-update, failure-restore) and the ack
  itself is independently wrapped → WARNING; a failure in one never
  short-circuits a later required step. Consequence (intentional): a
  ``None`` web client degrades to logged no-ops while authorization +
  publish still execute.
* C1 (review): if the publish SUCCEEDED but the success-path
  ``chat.update`` fails → WARNING only, first-click-wins stays marked,
  and the original blocks are NEVER restored (re-enabling a button for
  an already-recorded decision would reintroduce double-publish risk).
  The restore branch fires only on publish failure. The guarantee holds
  ACROSS concurrently dispatched clicks too: the whole decision sequence
  runs under a handler-wide ``asyncio.Lock``, so a failed attempt's
  restore always completes before a retry's publish begins.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.nats_client import NATSClient

logger = structlog.get_logger(__name__)

# The two action_ids TASK-JNB-103 places on the pause message buttons.
_ACTION_DECISIONS: dict[str, str] = {
    "forge_approve": "approve",
    "forge_reject": "reject",
}

# The exact BUTTON_METADATA keys (producer contract, TASK-JNB-103).
_BUTTON_VALUE_KEYS = ("request_id", "build_id", "correlation_id", "approval_subject")

# Bounded publish timeout — mirrors the DDR-025 posture used by
# ``jarvis.tools.dispatch.queue_build``.
_PUBLISH_TIMEOUT_SECONDS = 5.0

# Bounded Socket Mode close timeout.
_DEFAULT_STOP_TIMEOUT = 5.0

# Bounded first-connect timeout (review fix — CRITICAL): slack-sdk's
# aiohttp SocketModeClient.connect() is a ``while True`` retry loop that
# catches EVERY exception (invalid_auth included) and never raises, so an
# unbounded await would hang build_app_state forever on a bad app token
# or a Slack outage. Bounding it turns the failure into an observable
# TimeoutError the lifecycle's DDR-021 soft-fail branch can catch.
_CONNECT_TIMEOUT_SECONDS = 15.0


def parse_button_value(value: str) -> dict[str, str]:
    """Parse and validate the BUTTON_METADATA value JSON.

    The value is produced by TASK-JNB-103's Block Kit buttons and carries
    exactly ``{request_id, build_id, correlation_id, approval_subject}``.
    ``request_id`` and ``approval_subject`` are load-bearing (publish
    routing) and must be non-empty strings.

    Args:
        value: The raw ``value`` string from the clicked button action.

    Returns:
        The parsed dict with the four contract keys.

    Raises:
        ValueError: On unparseable JSON, a non-object payload, missing
            keys, or empty load-bearing fields. Callers catch this and
            drop the click with a log entry (DDR-007) — it never
            propagates further.
    """
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"button value is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("button value JSON is not an object")

    missing = [key for key in _BUTTON_VALUE_KEYS if key not in parsed]
    if missing:
        raise ValueError(f"button value JSON missing keys: {missing}")

    result = {key: parsed[key] for key in _BUTTON_VALUE_KEYS}

    for load_bearing in ("request_id", "approval_subject"):
        field = result[load_bearing]
        if not isinstance(field, str) or not field:
            raise ValueError(f"button value JSON field {load_bearing!r} must be a non-empty string")

    return result


# ---------------------------------------------------------------------------
# Publisher seam
# ---------------------------------------------------------------------------


class ApprovalResponsePublisher(Protocol):
    """Seam for publishing an approval response to the fleet bus."""

    async def publish(
        self,
        *,
        subject: str,
        payload: Any,
        correlation_id: str | None,
    ) -> None:
        """Publish one ``ApprovalResponsePayload`` to ``subject``.

        Raises on failure — the handler's publish-failure path needs to
        observe the error to re-enable the buttons.
        """
        ...


class NatsApprovalResponsePublisher:
    """JetStream-backed :class:`ApprovalResponsePublisher`.

    Wraps the response payload in the canonical ``MessageEnvelope``
    (``source_id="jarvis"``, ``event_type="approval_response"``, the
    request's ``correlation_id``) and publishes with a bounded timeout —
    the same convention as ``jarvis.tools.dispatch.queue_build``. The
    AGENTS stream is limits-retention, so a publish-only interaction is
    always legal (no consumer is created anywhere in this module).
    """

    __slots__ = ("_nats_client",)

    def __init__(self, nats_client: NATSClient) -> None:
        self._nats_client = nats_client

    async def publish(
        self,
        *,
        subject: str,
        payload: Any,
        correlation_id: str | None,
    ) -> None:
        """Publish; raises on any transport failure (caller handles)."""
        # Local imports keep the nats_core chain off this module's cold
        # import path (schema-import-isolation convention).
        from nats_core import EventType, MessageEnvelope

        envelope = MessageEnvelope(
            source_id="jarvis",
            event_type=EventType.APPROVAL_RESPONSE,
            correlation_id=correlation_id,
            payload=payload.model_dump(mode="json"),
        )
        await asyncio.wait_for(
            self._nats_client.js.publish(subject, envelope.model_dump_json().encode("utf-8")),
            timeout=_PUBLISH_TIMEOUT_SECONDS,
        )


# ---------------------------------------------------------------------------
# Reply handler
# ---------------------------------------------------------------------------


class ApprovalReplyHandler:
    """Processes ``block_actions`` interaction payloads (post-ack).

    Never raises (DDR-007). Constructed via :func:`build_reply_handler`.
    """

    __slots__ = (
        "_decided_request_ids",
        "_decision_lock",
        "_publisher",
        "_settings",
        "_web_client",
    )

    def __init__(
        self,
        *,
        settings: Any,
        publisher: ApprovalResponsePublisher,
        web_client: Any | None = None,
    ) -> None:
        """See :func:`build_reply_handler` (the public factory)."""
        self._settings = settings
        self._publisher = publisher
        self._web_client = web_client
        # First-click-wins state — in-process only (DDR-027); forge's
        # request_id dedup is the authoritative backstop after restart.
        self._decided_request_ids: set[str] = set()
        # Serializes the decision sequence (check/mark → publish →
        # update/restore) across concurrently dispatched clicks (review
        # fix): the SDK schedules one task per WS message, and without
        # this a failed attempt's restore chat.update could land AFTER a
        # concurrent retry's durable publish — re-displaying live buttons
        # for an already-recorded decision. The Socket Mode ack happens
        # upstream in _on_request, so holding the lock here never
        # threatens the ack deadline.
        self._decision_lock = asyncio.Lock()

    async def handle_block_actions(self, payload: dict[str, Any]) -> None:
        """Handle one authorized-or-not button click. Never raises."""
        try:
            await self._handle_block_actions(payload)
        except Exception as exc:
            # DDR-007 backstop — a handler bug must not reach the Socket
            # Mode client or the supervisor loop.
            logger.warning(
                "slack_reply_handler_error",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _handle_block_actions(self, payload: dict[str, Any]) -> None:
        user_id = (payload.get("user") or {}).get("id")

        # --- 1. Authorization — the SOLE Slack-side gate ----------------
        operator_id = self._settings.slack_operator_user_id
        if not operator_id or user_id != operator_id:
            logger.warning(
                "slack_reply_unauthorized_click",
                user_id=user_id,
            )
            await self._send_ephemeral_refusal(payload, user_id)
            return

        # --- 2. Extract + validate the clicked action -------------------
        actions = payload.get("actions") or []
        action = actions[0] if actions else {}
        action_id = action.get("action_id")
        decision = _ACTION_DECISIONS.get(action_id or "")
        if decision is None:
            logger.warning(
                "slack_reply_unknown_action_dropped",
                action_id=action_id,
            )
            return

        try:
            button = parse_button_value(action.get("value") or "")
        except ValueError as exc:
            logger.warning(
                "slack_reply_malformed_value_dropped",
                action_id=action_id,
                error=str(exc),
            )
            return

        request_id = button["request_id"]

        # The decision sequence (check/mark → publish → update/restore)
        # is serialized across concurrently dispatched clicks (review
        # fix): without the lock, a failed attempt's restore chat.update
        # could land AFTER a concurrent retry's durable publish and
        # re-display live buttons for an already-recorded decision.
        async with self._decision_lock:
            # --- 3. First-click-wins (check-and-mark under the lock) -----
            # Courtesy only — forge's request_id dedup is authoritative
            # (DDR-027).
            if request_id in self._decided_request_ids:
                logger.info(
                    "slack_reply_duplicate_click_dropped",
                    request_id=request_id,
                    decision=decision,
                )
                return
            self._decided_request_ids.add(request_id)

            # --- 3b. decided_by presence guard ----------------------------
            # The no-op factory gate is app_token/operator_id only (task
            # AC); an unset decided_by fails loud here instead — forge
            # would refuse the response anyway (expected_approver
            # mismatch).
            decided_by = self._settings.slack_decided_by
            if not decided_by:
                logger.warning(
                    "slack_reply_decided_by_unset",
                    request_id=request_id,
                    detail=(
                        "JARVIS_SLACK_DECIDED_BY is not configured; "
                        "refusing to publish an approval response"
                    ),
                )
                self._decided_request_ids.discard(request_id)
                return

            # --- 4. Optimistic disable (independent wrap — C2) ------------
            # Skipped when the interaction payload carries no
            # message.blocks (review fix): we could not restore what we
            # cannot rebuild, so the buttons stay live during the publish
            # — first-click-wins still guards the client side and forge
            # dedups the wire.
            original_blocks = (payload.get("message") or {}).get("blocks")
            if original_blocks:
                await self._update_message(
                    payload,
                    blocks=_blocks_with_status(original_blocks, f"Recording {decision}…"),
                    text=f"Recording {decision}…",
                    log_event="slack_reply_optimistic_update_failed",
                )

            # --- 5. Publish -----------------------------------------------
            from nats_core.events import ApprovalResponsePayload

            response = ApprovalResponsePayload(
                request_id=request_id,
                decision=decision,  # type: ignore[arg-type]
                # Verbatim — no trimming, casing, or normalisation. Must
                # string-equal forge's expected_approver (config contract).
                decided_by=decided_by,
            )
            subject = button["approval_subject"] + ".response"

            try:
                await self._publisher.publish(
                    subject=subject,
                    payload=response,
                    correlation_id=button["correlation_id"] or None,
                )
            except Exception as exc:
                # Publish failure: WARNING, un-mark first-click-wins so
                # the operator can retry, and restore the ORIGINAL blocks
                # (buttons re-enabled). This is the ONLY branch that
                # restores (C1); with no original blocks nothing was
                # disabled, so there is nothing to restore.
                logger.warning(
                    "slack_reply_publish_failed",
                    request_id=request_id,
                    subject=subject,
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
                self._decided_request_ids.discard(request_id)
                if original_blocks:
                    await self._update_message(
                        payload,
                        blocks=original_blocks,
                        text=("Approval buttons re-enabled after a publish failure."),
                        log_event="slack_reply_restore_update_failed",
                    )
                return

            logger.info(
                "slack_reply_decision_published",
                request_id=request_id,
                decision=decision,
                subject=subject,
            )

            # --- 6. Success update (C1: never restore from here) ----------
            # The decision is durably published: even if this chat.update
            # fails, first-click-wins stays marked and the buttons are
            # never re-enabled.
            await self._update_message(
                payload,
                blocks=_blocks_with_status(
                    original_blocks,
                    f"Decision recorded: {decision} (by {decided_by})",
                ),
                text=f"Decision recorded: {decision}",
                log_event="slack_reply_success_update_failed",
            )

    # ------------------------------------------------------------------
    # Slack side-effects — every call independently wrapped (C2)
    # ------------------------------------------------------------------

    async def _send_ephemeral_refusal(self, payload: dict[str, Any], user_id: str | None) -> None:
        """Best-effort ephemeral refusal; WARNING-only on any failure."""
        if self._web_client is None or not user_id:
            return
        channel_id = (payload.get("channel") or {}).get("id") or (
            payload.get("container") or {}
        ).get("channel_id")
        if not channel_id:
            logger.warning(
                "slack_reply_refusal_channel_unresolved",
                user_id=user_id,
            )
            return
        try:
            await self._web_client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=("You are not authorized to decide forge approvals from Slack."),
            )
        except Exception as exc:
            logger.warning(
                "slack_reply_refusal_failed",
                user_id=user_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _update_message(
        self,
        payload: dict[str, Any],
        *,
        blocks: list[dict[str, Any]] | None,
        text: str,
        log_event: str,
    ) -> None:
        """One independently wrapped ``chat.update``; WARNING-only.

        A ``None`` web client (or unresolvable channel/ts) degrades to a
        logged no-op — authorization + publish never depend on Slack UI
        updates succeeding (C2).
        """
        if self._web_client is None:
            return
        container = payload.get("container") or {}
        channel_id = (payload.get("channel") or {}).get("id") or container.get("channel_id")
        ts = container.get("message_ts")
        if not channel_id or not ts:
            logger.warning(log_event, detail="channel or message_ts unresolved")
            return
        try:
            kwargs: dict[str, Any] = {
                "channel": channel_id,
                "ts": ts,
                "text": text,
            }
            if blocks is not None:
                kwargs["blocks"] = blocks
            await self._web_client.chat_update(**kwargs)
        except Exception as exc:
            logger.warning(
                log_event,
                error_class=type(exc).__name__,
                error=str(exc),
            )


def _blocks_with_status(
    original_blocks: list[dict[str, Any]] | None, status_text: str
) -> list[dict[str, Any]]:
    """Replace any actions block with a plain_text status section.

    Renders from Slack's own served copy of the message (the interaction
    payload's ``message.blocks``) rather than re-deriving via
    ``slack_notifier`` — the served copy is the source of truth for what
    the operator is looking at.
    """
    status_section = {
        "type": "section",
        "text": {"type": "plain_text", "text": status_text, "emoji": False},
    }
    if not original_blocks:
        return [status_section]
    replaced = [b for b in original_blocks if b.get("type") != "actions"]
    replaced.append(status_section)
    return replaced


def build_reply_handler(
    *,
    settings: Any,
    publisher: ApprovalResponsePublisher,
    web_client: Any | None = None,
) -> ApprovalReplyHandler:
    """Public factory for :class:`ApprovalReplyHandler`.

    Args:
        settings: Any object exposing ``slack_operator_user_id`` and
            ``slack_decided_by`` (normally :class:`JarvisConfig`).
        publisher: The :class:`ApprovalResponsePublisher` seam.
        web_client: Optional Slack ``AsyncWebClient`` for ``chat.update``
            / ``chat.postEphemeral``. ``None`` degrades those to logged
            no-ops (intentional — see module docstring C2 note).

    Returns:
        A ready :class:`ApprovalReplyHandler`.
    """
    return ApprovalReplyHandler(settings=settings, publisher=publisher, web_client=web_client)


# ---------------------------------------------------------------------------
# Socket Mode lifecycle client
# ---------------------------------------------------------------------------


class SlackSocketModeReplyClient:
    """Lifecycle wrapper around slack-sdk's aiohttp ``SocketModeClient``.

    Outbound WebSocket — no public endpoint. Reconnects are owned by the
    SDK (``auto_reconnect_enabled``): the listener list lives on the
    client OBJECT and ``connect()`` only replaces the session, so the
    one-time registration in :meth:`start` can never duplicate handlers
    across reconnects — do not "helpfully" re-register on reconnect.
    First-click-wins state lives on the handler instance, outside the
    SDK client, so it survives reconnects within the process.
    """

    __slots__ = (
        "_app_token",
        "_client",
        "_handler",
        "_started",
        "_stop_timeout",
        "_web_client",
    )

    def __init__(
        self,
        *,
        app_token: str,
        handler: ApprovalReplyHandler,
        web_client: Any,
        stop_timeout: float = _DEFAULT_STOP_TIMEOUT,
    ) -> None:
        self._app_token = app_token
        self._handler = handler
        self._web_client = web_client
        self._stop_timeout = stop_timeout
        self._client: Any = None
        self._started = False

    async def start(self) -> None:
        """Construct, register the listener, and connect (idempotent)."""
        if self._started:
            return

        # Lazy import — slack-sdk's socket-mode aiohttp client (and its
        # aiohttp dependency chain) stays off the cold import path.
        from slack_sdk.socket_mode.aiohttp import SocketModeClient

        self._client = SocketModeClient(
            app_token=self._app_token,
            web_client=self._web_client,
        )
        # Registration MUST precede connect(): process_messages() starts
        # in the SDK client's __init__, so connecting first would open a
        # window where deliveries find zero listeners.
        self._client.socket_mode_request_listeners.append(self._on_request)
        # Bounded connect (review fix — CRITICAL): the SDK's connect() is
        # an infinite retry loop that never raises (it swallows
        # invalid_auth and network errors alike), so an unbounded await
        # would wedge build_app_state forever on a bad app token or a
        # Slack outage. On timeout/failure the SDK client is closed
        # (its __init__ already spawned process_messages and an aiohttp
        # session) and the error re-raised so the lifecycle's DDR-021
        # soft-fail branch fires as designed.
        try:
            await asyncio.wait_for(self._client.connect(), timeout=_CONNECT_TIMEOUT_SECONDS)
        except BaseException:
            client, self._client = self._client, None
            try:
                await asyncio.wait_for(client.close(), timeout=self._stop_timeout)
            except Exception as exc:
                logger.warning(
                    "slack_reply_connect_cleanup_failed",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
            raise
        self._started = True
        logger.info("slack_reply_socket_mode_started")

    async def stop(self) -> None:
        """Close the Socket Mode session; bounded, never raises."""
        if not self._started:
            return
        self._started = False
        client = self._client
        self._client = None
        if client is None:
            return
        try:
            await asyncio.wait_for(client.close(), timeout=self._stop_timeout)
        except TimeoutError:
            logger.warning("slack_reply_stop_timeout", timeout=self._stop_timeout)
        except Exception as exc:
            logger.warning(
                "slack_reply_stop_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
        logger.info("slack_reply_socket_mode_stopped")

    async def _on_request(self, client: Any, req: Any) -> None:
        """Socket Mode listener — acks FIRST, then routes. Never raises."""
        # --- Ack immediately, before ANY authorization/parse/publish ----
        # Independently wrapped (C2) so an ack failure mid-reconnect is
        # observable rather than silent.
        try:
            from slack_sdk.socket_mode.response import SocketModeResponse

            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))
        except Exception as exc:
            logger.warning(
                "slack_reply_ack_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

        try:
            if req.type != "interactive":
                return
            payload = req.payload or {}
            if payload.get("type") != "block_actions":
                return
            # handle_block_actions never raises (DDR-007).
            await self._handler.handle_block_actions(payload)
        except Exception as exc:
            # Defensive backstop — the SDK's own listener catch-all would
            # swallow this anyway; logging here keeps the failure visible
            # on jarvis's structured log surface.
            logger.warning(
                "slack_reply_listener_error",
                error_class=type(exc).__name__,
                error=str(exc),
            )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_slack_reply_client(
    config: JarvisConfig,
    nats_client: NATSClient | None,
) -> SlackSocketModeReplyClient | None:
    """Create the Socket Mode reply client, or a logged no-op (``None``).

    No-op conditions (each logged with its reason):

    * ``slack_app_token`` or ``slack_operator_user_id`` unset — the task's
      own no-op gate.
    * ``slack_bot_token`` unset — no web client for chat.update /
      ephemeral refusals (and no button surface exists either, since the
      notifier is a NoOpSink in that configuration).
    * ``nats_client is None`` — nothing to publish decisions to
      (DDR-021-style soft degradation).

    The supervisor starts and runs normally in every no-op permutation.
    """
    app_token_secret = config.slack_app_token
    app_token = app_token_secret.get_secret_value() if app_token_secret is not None else None
    operator_id = config.slack_operator_user_id
    bot_token_secret = config.slack_bot_token
    bot_token = bot_token_secret.get_secret_value() if bot_token_secret is not None else None

    if not app_token or not operator_id:
        logger.info(
            "slack_reply_no_op",
            reason=(
                "slack_app_token or slack_operator_user_id not configured; "
                "Slack reply path disabled"
            ),
        )
        return None
    if not bot_token:
        logger.info(
            "slack_reply_no_op",
            reason="slack_bot_token not configured; Slack reply path disabled",
        )
        return None
    if nats_client is None:
        logger.info(
            "slack_reply_no_op",
            reason="NATS unavailable; Slack reply path disabled",
        )
        return None

    from slack_sdk.web.async_client import AsyncWebClient

    web_client = AsyncWebClient(token=bot_token)
    handler = build_reply_handler(
        settings=config,
        publisher=NatsApprovalResponsePublisher(nats_client),
        web_client=web_client,
    )
    return SlackSocketModeReplyClient(
        app_token=app_token,
        handler=handler,
        web_client=web_client,
    )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

__all__ = [
    "ApprovalReplyHandler",
    "ApprovalResponsePublisher",
    "NatsApprovalResponsePublisher",
    "SlackSocketModeReplyClient",
    "build_reply_handler",
    "create_slack_reply_client",
    "parse_button_value",
]
