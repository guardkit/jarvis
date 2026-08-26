"""Slack Socket Mode reply path for forge approvals (TASK-JNB-104).

The Slack→forge direction of the FEAT-BF39 phone-approval loop —
``slack_notifier.py`` owns the forge→Slack direction (notify + capture +
Block Kit buttons); this module consumes those buttons' clicks:

* :func:`parse_button_value` — validates the BUTTON_METADATA value JSON
  produced by TASK-JNB-103 (``{request_id, build_id, correlation_id,
  approval_subject}``).
* :class:`ApprovalReplyHandler` (via :func:`build_reply_handler`) — the
  ``block_actions`` handler: operator-allowlist authorization, local
  first-click-wins, ``ApprovalResponsePayload`` publish to
  ``approval_subject + ".response"`` (``decided_by`` = the actual clicker's
  Slack member id — TASK-JNB-110), and in-place ``chat.update``s.
* :class:`NatsApprovalResponsePublisher` — envelope + CORE publish +
  flush (TASK-JNB-111: the AGENTS stream is ``no_ack: true``, so a
  ``js.publish`` would store the message but time out waiting for a
  PubAck that never comes — every live tap "failed" while actually
  delivering; forge's own ApprovalPublisher uses core publish for the
  same reason). Publish only — this module never creates any NATS
  consumer, and specifically never touches the PIPELINE stream's single
  ephemeral consumer.
* :class:`SlackSocketModeReplyClient` — lifecycle wrapper around
  slack-sdk's aiohttp ``SocketModeClient`` (outbound WebSocket — no
  public endpoint), constructed in ``lifecycle.build_app_state``.

Behaviour invariants (task ACs + Phase 2.5B review C1/C2):

* Every Socket Mode envelope is acked immediately — before any
  authorization, parsing, or publish work.
* The SOLE Slack-side authorization gate is allowlist membership:
  ``payload["user"]["id"] in operator_ids`` (TASK-JNB-110 — the singular
  ``slack_operator_user_id`` folds into that set); a non-member is WARN +
  ephemeral refusal, nothing published. Authorization ("who MAY decide")
  is separate from identity ("who DID"): the published ``decided_by`` is
  the clicker's own member id, a factual claim, never a config constant.
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

# Stdlib-only module — safe on the cold import path (unlike the
# nats_core / slack-sdk chains, which stay lazily imported below).
from jarvis.infrastructure.spec_texts import SpecTextRegistry
from jarvis.infrastructure.terminal_builds import (
    TerminalBuildRecord,
    TerminalBuildRegistry,
    render_local_hhmm,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.build_audience import BuildAudienceRegistry
    from jarvis.infrastructure.nats_client import NATSClient
    from jarvis.infrastructure.slack_planning_intake import PlanningIntakeHandler

logger = structlog.get_logger(__name__)

# The two action_ids TASK-JNB-103 places on the pause message buttons.
_ACTION_DECISIONS: dict[str, str] = {
    "forge_approve": "approve",
    "forge_reject": "reject",
}

# The exact BUTTON_METADATA keys (producer contract, TASK-JNB-103).
_BUTTON_VALUE_KEYS = ("request_id", "build_id", "correlation_id", "approval_subject")

# Bounded flush timeout — mirrors the DDR-025 bounded-transport posture
# used by ``jarvis.tools.dispatch.queue_build``. Bounds the core-publish
# flush round-trip (TASK-JNB-111), not a PubAck wait (the AGENTS stream
# is no-ack; there is no PubAck to wait for).
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
    """Core-publish-backed :class:`ApprovalResponsePublisher`.

    Wraps the response payload in the canonical ``MessageEnvelope``
    (``source_id="jarvis"``, ``event_type="approval_response"``, the
    request's ``correlation_id``) and publishes with CORE publish +
    bounded flush — NOT ``js.publish`` (TASK-JNB-111). The AGENTS stream
    is ``no_ack: true`` (``agents.>`` carries request-reply chat traffic
    where PubAcks would collide with replies): a JetStream publish to it
    is STORED but never acked, so ``js.publish`` always times out and
    the handler mis-reported every delivered decision as a failure.
    Core publish + flush is the fleet convention for ``agents.>``
    (forge's ApprovalPublisher does the same); the wire bytes and
    subject are identical — JetStream still captures the message.

    The AGENTS stream is limits-retention, so a publish-only interaction
    is always legal (no consumer is created anywhere in this module).
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
        """Publish; raises on any transport failure (caller handles).

        ``nc.publish`` buffers locally (raises only on a closed/broken
        connection); the bounded ``flush`` round-trips the server so a
        success return means the broker actually received the bytes.
        """
        # Local imports keep the nats_core chain off this module's cold
        # import path (schema-import-isolation convention).
        from nats_core import EventType, MessageEnvelope

        envelope = MessageEnvelope(
            source_id="jarvis",
            event_type=EventType.APPROVAL_RESPONSE,
            correlation_id=correlation_id,
            payload=payload.model_dump(mode="json"),
        )
        nc = self._nats_client.client
        await nc.publish(subject, envelope.model_dump_json().encode("utf-8"))
        await asyncio.wait_for(nc.flush(), timeout=_PUBLISH_TIMEOUT_SECONDS)


# ---------------------------------------------------------------------------
# Reply handler
# ---------------------------------------------------------------------------


class ApprovalReplyHandler:
    """Processes ``block_actions`` interaction payloads (post-ack).

    Never raises (DDR-007). Constructed via :func:`build_reply_handler`.
    """

    __slots__ = (
        "_audience",
        "_decided_request_ids",
        "_decision_lock",
        "_operator_ids",
        "_publisher",
        "_spec_texts",
        "_terminal_registry",
        "_web_client",
    )

    def __init__(
        self,
        *,
        operator_ids: frozenset[str],
        publisher: ApprovalResponsePublisher,
        web_client: Any | None = None,
        terminal_registry: TerminalBuildRegistry | None = None,
        spec_texts: SpecTextRegistry | None = None,
        audience: BuildAudienceRegistry | None = None,
    ) -> None:
        """See :func:`build_reply_handler` (the public factory)."""
        self._operator_ids = operator_ids
        self._publisher = publisher
        self._web_client = web_client
        # Machine chain stage 2: the worked examples behind a spec digest card,
        # written by the checkpoint renderer. None = unwired → "Show the worked
        # examples" answers honestly that they are not to hand.
        self._spec_texts = spec_texts
        # Approval-card truth R3-B: shared terminal-state registry, READ
        # side (the notification sink writes it). None = unwired →
        # every consult misses (today's behaviour).
        self._terminal_registry = terminal_registry
        # Build-side mention lane (2026-08-15): WRITE side. Whoever taps
        # this build's gate asked for the build, so the terminal build
        # line @-mentions them. None = unwired → nothing recorded.
        self._audience = audience
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
        # Allowlist membership (TASK-JNB-110): identity says who DID, this
        # gate says who MAY. An empty allowlist (no operator configured)
        # refuses everyone; a falsy user_id can never be a member.
        if not user_id or user_id not in self._operator_ids:
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

        # --- 2a. SPL-003 dialogue routing (TASK-SPL003-J03a) ------------
        # Per-assumption clicks and the whole-run cancel/zero-assumption
        # approve go to the dialogue engine (which takes the decision lock
        # itself). ``assumption_edit`` opens the J03b modal (routed there);
        # until J03b lands it falls through to the unknown-action drop.
        from jarvis.infrastructure.assumption_dialogue import (
            ACTION_APPROVE,
            ACTION_CANCEL,
            ACTION_DEFER,
            ACTION_DIGEST_APPROVE,
            ACTION_DIGEST_NOTE,
            ACTION_DIGEST_SHOW_SPEC,
            ACTION_DIGEST_SIGN_IN_AGREE,
            ACTION_DIGEST_SIGN_IN_DISAGREE,
            ACTION_EDIT,
            ACTION_WHOLE_APPROVE,
        )

        if action_id == ACTION_EDIT:
            # Open the modal BEFORE any lock (arch F4 — trigger_id ~3s TTL).
            await self._handle_edit_open(payload, action, user_id)
            return
        # --- 2b. Spec digest card (machine chain, stage 2) ---------------
        # Both modal openers run BEFORE any lock, for the same trigger_id TTL
        # reason as the edit modal above.
        if action_id == ACTION_DIGEST_NOTE:
            await self._handle_digest_note_open(payload, action)
            return
        if action_id == ACTION_DIGEST_SHOW_SPEC:
            await self._handle_digest_show_spec(payload, action)
            return
        if action_id in (ACTION_DIGEST_SIGN_IN_AGREE, ACTION_DIGEST_SIGN_IN_DISAGREE):
            await self._handle_digest_sign_in(payload, action, action_id)
            return
        if action_id == ACTION_DIGEST_APPROVE:
            await self._handle_digest_approve(payload, action, user_id)
            return
        if action_id in (ACTION_APPROVE, ACTION_DEFER, ACTION_CANCEL, ACTION_WHOLE_APPROVE):
            await self._handle_dialogue_click(payload, action, action_id, user_id)
            return

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

        # Belt-and-braces with J02's mirror suppression: a binary
        # forge_approve/forge_reject click on a planning (``plan-``) subject is
        # ignored — planning decisions travel only through the per-assumption
        # dialogue, never a binary approve/reject (scenario 15).
        if button["approval_subject"].startswith("agents.approval.forge.plan-"):
            logger.info(
                "slack_reply_binary_plan_click_ignored",
                action_id=action_id,
                approval_subject=button["approval_subject"],
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

            # --- 3a. Terminal-truth consult (approval-card truth R3-B) ---
            # Between first-click-wins and the publish: a tap on a build
            # jarvis has already seen reach a terminal state (cancelled /
            # complete / failed) is answered honestly on the card and
            # NEVER published — forge would only drop the response
            # silently (no active waiter) while the success update lied
            # "Decision recorded". The request stays UN-marked:
            # nothing was recorded, so a repeat tap re-answers, and after
            # registry TTL expiry — or a jarvis restart, which empties
            # the in-process map (DDR-027) — behaviour degrades exactly
            # to today's publish path.
            terminal = (
                self._terminal_registry.get(button["build_id"])
                if self._terminal_registry is not None
                else None
            )
            if terminal is not None:
                status = _already_terminal_text(terminal)
                logger.info(
                    "slack_reply_tap_after_terminal",
                    request_id=request_id,
                    build_id=button["build_id"],
                    terminal_state=terminal.terminal_state,
                    decision=decision,
                )
                await self._update_message(
                    payload,
                    blocks=_blocks_with_status(
                        (payload.get("message") or {}).get("blocks"), status
                    ),
                    text=status,
                    log_event="slack_reply_terminal_update_failed",
                )
                return

            self._decided_request_ids.add(request_id)

            # --- 3b. Identity — the ACTUAL clicker (TASK-JNB-110) ---------
            # ``decided_by`` is a factual claim about who clicked, not a
            # config constant. It is the interaction payload's user id,
            # already proven a member of the operator allowlist by step 1,
            # so it is always a non-empty string here (no unset guard is
            # needed — the old ``slack_reply_decided_by_unset`` path is
            # gone). Forge's build-gate ``expected_approver`` is now set to
            # this same member id, so the audit trail and the gate agree.
            decided_by = user_id

            # Build-side mention lane: remember who asked for this build,
            # so the notification sink can name them when it ends. Never
            # raises — a registry failure must not cost the tap.
            self._record_gate_clicker(button.get("build_id"), user_id)

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
                # The clicker's Slack member id, verbatim — no trimming,
                # casing, or normalisation. Forge compares it to the run's
                # ``expected_approver`` (now a member id) by exact equality.
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

    def _record_gate_clicker(self, build_id: str | None, user_id: str) -> None:
        """Record ``build_id -> clicker`` for the build-side mention. Never raises."""
        if self._audience is None:
            return
        try:
            self._audience.record_gate_clicker(build_id, user_id)
        except Exception as exc:  # pragma: no cover - defensive backstop
            logger.warning(
                "slack_reply_audience_record_failed",
                build_id=build_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # SPL-003 per-assumption dialogue engine (TASK-SPL003-J03a)
    # ------------------------------------------------------------------

    async def _handle_dialogue_click(
        self,
        payload: dict[str, Any],
        action: dict[str, Any],
        action_id: str | None,
        user_id: str,
    ) -> None:
        """Handle one per-assumption dialogue click (post-auth). Never raises.

        The Slack message IS the dialogue state (ADR-ARCH-004 — jarvis keeps no
        pending-dialogue map). Under the handler-wide ``_decision_lock`` this
        re-derives per-item state from the AUTHORITATIVE re-fetched message (not
        the possibly-stale inbound snapshot — two concurrent final clicks each
        carry a stale copy and the checkpoint would otherwise never publish),
        applies this click, and publishes exactly ONE aggregate
        ``ApprovalResponsePayload`` when the last undecided item is decided.
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        raw_value = _extract_action_value(action)
        try:
            button = ad.parse_item_value(raw_value)
        except ValueError as exc:
            logger.warning(
                "dialogue_click_malformed_value_dropped",
                action_id=action_id,
                error=str(exc),
            )
            return

        approval_subject = str(button["approval_subject"])
        request_id = str(button["request_id"])
        assumption_id = str(button["assumption_id"])
        correlation_id = button["correlation_id"] or None

        container = payload.get("container") or {}
        channel_id = (payload.get("channel") or {}).get("id") or container.get("channel_id")
        message_ts = container.get("message_ts")

        async with self._decision_lock:
            # Whole-run terminal clicks publish immediately (guarded by
            # first-publish-wins on request_id): cancel is a reject abort,
            # the zero-assumption whole-approve an approve.
            if action_id == ad.ACTION_CANCEL:
                blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
                dispositions = self._dispositions_from_state(ad.parse_dialogue_blocks(blocks))
                await self._publish_dialogue_decision(
                    request_id=request_id,
                    approval_subject=approval_subject,
                    correlation_id=correlation_id,
                    decided_by=user_id,
                    decision="reject",
                    dispositions=dispositions,
                )
                await self._dialogue_status_update(
                    channel_id, message_ts, payload, "Planning run cancelled."
                )
                return

            if action_id == ad.ACTION_WHOLE_APPROVE:
                await self._publish_dialogue_decision(
                    request_id=request_id,
                    approval_subject=approval_subject,
                    correlation_id=correlation_id,
                    decided_by=user_id,
                    decision="approve",
                    dispositions=[],
                )
                await self._dialogue_status_update(
                    channel_id, message_ts, payload, "Checkpoint approved."
                )
                return

            disposition = "accepted" if action_id == ad.ACTION_APPROVE else "deferred"

            blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
            state = ad.parse_dialogue_blocks(blocks)
            current = state.get(assumption_id)
            if current is not None and current["disposition"] != "undecided":
                # The authoritative message already records a decision for this
                # item — idempotent under redelivery / a double-click.
                logger.info(
                    "dialogue_item_already_decided",
                    assumption_id=assumption_id,
                    request_id=request_id,
                )
                return

            updated = ad.apply_disposition(
                blocks, assumption_id=assumption_id, disposition=disposition
            )
            await self._chat_update_blocks(
                channel_id,
                message_ts,
                updated,
                text=f"Recorded {disposition} for {assumption_id}",
            )

            # Completeness gate — no decision published while any item undecided.
            if not ad.is_complete(updated):
                return

            final_state = ad.parse_dialogue_blocks(updated)
            await self._publish_dialogue_decision(
                request_id=request_id,
                approval_subject=approval_subject,
                correlation_id=correlation_id,
                decided_by=user_id,
                decision=ad.aggregate_decision(final_state),
                dispositions=self._dispositions_from_state(final_state),
            )

    @staticmethod
    def _dispositions_from_state(state: dict[str, dict[str, Any]]) -> list[Any]:
        """Build ``AssumptionDisposition`` models for every DECIDED item."""
        from nats_core.events import AssumptionDisposition

        out: list[Any] = []
        for assumption_id, item in state.items():
            if item["disposition"] == "undecided":
                continue
            out.append(
                AssumptionDisposition(
                    assumption_id=assumption_id,
                    disposition=item["disposition"],
                    edit_delta=item.get("edit_delta"),
                )
            )
        return out

    async def _publish_dialogue_decision(
        self,
        *,
        request_id: str,
        approval_subject: str,
        correlation_id: str | None,
        decided_by: str,
        decision: str,
        dispositions: list[Any],
        notes: str | None = None,
    ) -> bool:
        """Publish exactly one aggregate decision (first-publish-wins).

        ``notes`` carries the owner's own words VERBATIM — never summarised,
        never reworded. It is the spec digest card's note channel (the field has
        always existed on the wire and the pipeline has always read it); every
        other caller omits it and publishes exactly what it published before.
        """
        if request_id in self._decided_request_ids:
            logger.info("dialogue_duplicate_publish_dropped", request_id=request_id)
            return False
        self._decided_request_ids.add(request_id)

        from nats_core.events import ApprovalResponsePayload

        response = ApprovalResponsePayload(
            request_id=request_id,
            decision=decision,  # type: ignore[arg-type]
            decided_by=decided_by,
            notes=notes,
            dispositions=dispositions or None,
        )
        subject = approval_subject + ".response"
        try:
            await self._publisher.publish(
                subject=subject,
                payload=response,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.warning(
                "dialogue_publish_failed",
                request_id=request_id,
                subject=subject,
                error_class=type(exc).__name__,
                error=str(exc),
            )
            self._decided_request_ids.discard(request_id)
            return False
        logger.info(
            "dialogue_decision_published",
            request_id=request_id,
            decision=decision,
            subject=subject,
            n_dispositions=len(dispositions),
            decided_by=decided_by,
        )
        return True

    async def _fetch_dialogue_blocks(
        self,
        channel_id: str | None,
        message_ts: str | None,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Re-fetch the AUTHORITATIVE message blocks (ASSUM-004, race-safe F4).

        Falls back to the inbound snapshot only when no web client / channel /
        ts is available (a degraded no-Slack path); the authoritative fetch is
        what makes concurrent final clicks converge instead of stalling.
        """
        if self._web_client is not None and channel_id and message_ts:
            try:
                resp = await self._web_client.conversations_history(
                    channel=channel_id,
                    latest=message_ts,
                    inclusive=True,
                    limit=1,
                )
                messages = resp["messages"]
                if messages:
                    return messages[0].get("blocks") or []
            except Exception as exc:
                logger.warning(
                    "dialogue_history_fetch_failed",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
        return (payload.get("message") or {}).get("blocks") or []

    async def _chat_update_blocks(
        self,
        channel_id: str | None,
        message_ts: str | None,
        blocks: list[dict[str, Any]],
        *,
        text: str,
    ) -> None:
        """``chat.update`` the dialogue message with new blocks; WARNING-only."""
        if self._web_client is None or not channel_id or not message_ts:
            return
        try:
            await self._web_client.chat_update(
                channel=channel_id, ts=message_ts, text=text, blocks=blocks
            )
        except Exception as exc:
            logger.warning(
                "dialogue_chat_update_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _dialogue_status_update(
        self,
        channel_id: str | None,
        message_ts: str | None,
        payload: dict[str, Any],
        status: str,
    ) -> None:
        """Replace the dialogue's action controls with a plain status line."""
        blocks = (payload.get("message") or {}).get("blocks")
        if blocks is None and self._web_client is not None and channel_id and message_ts:
            blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
        remaining = [b for b in (blocks or []) if b.get("type") != "actions"]
        remaining.append(
            {
                "type": "section",
                "text": {"type": "plain_text", "text": status, "emoji": False},
            }
        )
        await self._chat_update_blocks(channel_id, message_ts, remaining, text=status)

    # ------------------------------------------------------------------
    # SPL-003 edit modal (TASK-SPL003-J03b)
    # ------------------------------------------------------------------

    async def _handle_edit_open(
        self, payload: dict[str, Any], action: dict[str, Any], user_id: str
    ) -> None:
        """Open the edit modal for an assumption (pre-lock — trigger TTL). Never raises."""
        from jarvis.infrastructure import assumption_dialogue as ad

        raw_value = _extract_action_value(action)
        try:
            button = ad.parse_item_value(raw_value)
        except ValueError as exc:
            logger.warning("dialogue_edit_malformed_value_dropped", error=str(exc))
            return

        trigger_id = payload.get("trigger_id")
        if self._web_client is None or not trigger_id:
            logger.warning("dialogue_edit_no_trigger_or_client")
            return

        assumption_id = str(button["assumption_id"])
        container = payload.get("container") or {}
        channel_id = (payload.get("channel") or {}).get("id") or container.get("channel_id")
        message_ts = container.get("message_ts")

        message_blocks = (payload.get("message") or {}).get("blocks")
        prefill = ad.extract_assumption_text(message_blocks, assumption_id)
        private_metadata = json.dumps(
            {
                "correlation_id": button["correlation_id"],
                "request_id": button["request_id"],
                "assumption_id": assumption_id,
                "cycle": button["cycle"],
                "approval_subject": button["approval_subject"],
                "channel": channel_id,
                "message_ts": message_ts,
            },
            separators=(",", ":"),
        )
        view = ad.build_edit_modal(
            assumption_id=assumption_id, prefill=prefill, private_metadata=private_metadata
        )
        try:
            await self._web_client.views_open(trigger_id=trigger_id, view=view)
        except Exception as exc:
            logger.warning(
                "dialogue_edit_modal_open_failed",
                assumption_id=assumption_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def handle_view_submission(self, payload: dict[str, Any]) -> None:
        """Handle one edit-modal submission. Never raises (DDR-007)."""
        try:
            await self._handle_view_submission(payload)
        except Exception as exc:
            logger.warning(
                "dialogue_view_submission_error",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _handle_view_submission(self, payload: dict[str, Any]) -> None:
        from jarvis.infrastructure import assumption_dialogue as ad

        view = payload.get("view") or {}
        callback_id = view.get("callback_id")
        # Two modals submit here, and a submission that matches neither is
        # dropped — but SAID, not silently: an unrecognised callback id used to
        # return with no log at all, which is how a note could vanish between a
        # person typing it and the machine hearing it.
        if callback_id not in (ad.EDIT_MODAL_CALLBACK_ID, ad.NOTE_MODAL_CALLBACK_ID):
            logger.info("view_submission_unknown_callback_dropped", callback_id=callback_id)
            return

        user_id = (payload.get("user") or {}).get("id")
        # Authorization parity with block_actions (the sole Slack-side gate):
        # only allowlist members can record a decision.
        if not user_id or user_id not in self._operator_ids:
            logger.warning("dialogue_edit_unauthorized_submission", user_id=user_id)
            return

        if callback_id == ad.NOTE_MODAL_CALLBACK_ID:
            await self._handle_digest_note_submission(payload, view, user_id)
            return

        try:
            meta = json.loads(view.get("private_metadata") or "")
        except (TypeError, ValueError):
            logger.warning("dialogue_edit_bad_private_metadata")
            return

        assumption_id = str(meta.get("assumption_id") or "")
        request_id = str(meta.get("request_id") or "")
        approval_subject = str(meta.get("approval_subject") or "")
        correlation_id = meta.get("correlation_id") or None
        channel_id = meta.get("channel")
        message_ts = meta.get("message_ts")
        edit_delta = ad.read_edit_submission(view)

        if not assumption_id or not request_id or not approval_subject:
            logger.warning("dialogue_edit_incomplete_metadata", request_id=request_id)
            return

        async with self._decision_lock:
            blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
            state = ad.parse_dialogue_blocks(blocks)
            current = state.get(assumption_id)
            if current is not None and current["disposition"] != "undecided":
                logger.info(
                    "dialogue_item_already_decided",
                    assumption_id=assumption_id,
                    request_id=request_id,
                )
                return

            updated = ad.apply_disposition(
                blocks,
                assumption_id=assumption_id,
                disposition="modified",
                edit_delta=edit_delta,
            )
            await self._chat_update_blocks(
                channel_id,
                message_ts,
                updated,
                text=f"Recorded edit for {assumption_id}",
            )

            if not ad.is_complete(updated):
                return

            final_state = ad.parse_dialogue_blocks(updated)
            await self._publish_dialogue_decision(
                request_id=request_id,
                approval_subject=approval_subject,
                correlation_id=correlation_id,
                decided_by=user_id,
                decision=ad.aggregate_decision(final_state),
                dispositions=self._dispositions_from_state(final_state),
            )

    # ------------------------------------------------------------------
    # The spec digest card (machine chain, stage 2)
    # ------------------------------------------------------------------

    @staticmethod
    def _digest_click(
        payload: dict[str, Any], action: dict[str, Any]
    ) -> tuple[dict[str, Any], str | None, str | None] | None:
        """Decode one digest-card click → (routing ids, channel, message ts).

        ``None`` when the control's value is unreadable — the click is dropped
        with a log entry and never propagates (DDR-007).
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        try:
            button = ad.parse_item_value(_extract_action_value(action))
        except ValueError as exc:
            logger.warning("digest_click_malformed_value_dropped", error=str(exc))
            return None
        container = payload.get("container") or {}
        channel_id = (payload.get("channel") or {}).get("id") or container.get("channel_id")
        message_ts = container.get("message_ts")
        return button, channel_id, message_ts

    async def _handle_digest_note_open(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Open the note box (pre-lock — trigger TTL). Never raises.

        The owner's red pen is a plain-English sentence, so the click collects
        one instead of publishing anything: nothing reaches the wire until the
        modal is submitted.
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        decoded = self._digest_click(payload, action)
        if decoded is None:
            return
        button, channel_id, message_ts = decoded

        trigger_id = payload.get("trigger_id")
        if self._web_client is None or not trigger_id:
            logger.warning("digest_note_no_trigger_or_client")
            return

        private_metadata = json.dumps(
            {
                "correlation_id": button["correlation_id"],
                "request_id": button["request_id"],
                "cycle": button["cycle"],
                "approval_subject": button["approval_subject"],
                "channel": channel_id,
                "message_ts": message_ts,
            },
            separators=(",", ":"),
        )
        try:
            await self._web_client.views_open(
                trigger_id=trigger_id,
                view=ad.build_note_modal(private_metadata=private_metadata),
            )
        except Exception as exc:
            logger.warning(
                "digest_note_modal_open_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _handle_digest_show_spec(
        self, payload: dict[str, Any], action: dict[str, Any]
    ) -> None:
        """Open the read-only worked-examples view (pre-lock). Never raises.

        One click deeper, and never the ask: this view decides nothing, has no
        submit control, and publishes nothing. When the examples are no longer
        to hand (a restart emptied the in-process store) the view says so
        plainly rather than opening empty.
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        decoded = self._digest_click(payload, action)
        if decoded is None:
            return
        button, _channel_id, _message_ts = decoded

        trigger_id = payload.get("trigger_id")
        if self._web_client is None or not trigger_id:
            logger.warning("digest_show_spec_no_trigger_or_client")
            return

        record = (
            self._spec_texts.get(str(button["request_id"]))
            if self._spec_texts is not None
            else None
        )
        if record is None:
            logger.info(
                "digest_show_spec_not_held",
                request_id=button["request_id"],
            )
            view = ad.build_spec_unavailable_modal()
        else:
            view = ad.build_spec_modal(feature=record.feature, spec_text=record.spec_text)
        try:
            await self._web_client.views_open(trigger_id=trigger_id, view=view)
        except Exception as exc:
            logger.warning(
                "digest_show_spec_modal_open_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    async def _handle_digest_sign_in(
        self, payload: dict[str, Any], action: dict[str, Any], action_id: str
    ) -> None:
        """Record the sign-in answer ON the card. Publishes nothing. Never raises.

        The answer is written into the message the same way every other decided
        item is, so it survives a restart in the only place that survives one —
        the message itself. Saying yes to the spec is what carries it to the
        wire, as a per-item value.
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        decoded = self._digest_click(payload, action)
        if decoded is None:
            return
        button, channel_id, message_ts = decoded
        request_id = str(button["request_id"])
        item_id = str(button["assumption_id"])
        disposition = "accepted" if action_id == ad.ACTION_DIGEST_SIGN_IN_AGREE else "rejected"

        async with self._decision_lock:
            if request_id in self._decided_request_ids:
                # The card is already answered — the question went with it.
                logger.info("digest_sign_in_after_decision_dropped", request_id=request_id)
                return
            blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
            updated = ad.apply_sign_in_answer(blocks, item_id=item_id, disposition=disposition)
            await self._chat_update_blocks(
                channel_id,
                message_ts,
                updated,
                text="Your answer about signing in is recorded on the card.",
            )
            logger.info(
                "digest_sign_in_answer_recorded",
                request_id=request_id,
                item_id=item_id,
                disposition=disposition,
            )

    async def _handle_digest_approve(
        self, payload: dict[str, Any], action: dict[str, Any], user_id: str
    ) -> None:
        """Publish the owner's yes to the spec. Never raises.

        Carries whatever the card was told about signing in as a per-item value
        — read out of the message, which is the authoritative copy. An
        unanswered sign-in question sends no item at all, which the pipeline
        reads as agreement, exactly as the card's own fine print says.
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        decoded = self._digest_click(payload, action)
        if decoded is None:
            return
        button, channel_id, message_ts = decoded

        async with self._decision_lock:
            blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
            state = ad.parse_dialogue_blocks(blocks)
            published = await self._publish_dialogue_decision(
                request_id=str(button["request_id"]),
                approval_subject=str(button["approval_subject"]),
                correlation_id=button["correlation_id"] or None,
                decided_by=user_id,
                decision="approve",
                dispositions=self._dispositions_from_state(state),
            )
            if not published:
                return
            await self._dialogue_status_update(
                channel_id,
                message_ts,
                payload,
                (
                    "You said yes to the spec. The task plan and the quality "
                    "checklist are next — nothing is built until you give the "
                    "go-ahead."
                ),
            )

    async def _handle_digest_note_submission(
        self, payload: dict[str, Any], view: dict[str, Any], user_id: str
    ) -> None:
        """Send the owner's note to the machine, verbatim. Never raises.

        ``reject`` is the wire's own literal and the only one that carries a
        note; the spec digest door branches on it itself. A note normally
        means REWRITE THE SPEC FROM THIS — but a note whose FIRST WORD is
        "reject" (any capitalisation) is the owner calling the run off, and
        the machine cancels the run instead of redrafting. The note goes out
        verbatim either way — the machine is the one deciding — and only the
        in-card status line differs, so what the card says matches what the
        machine will do. A note with no words is not sent: there would be
        nothing to rewrite from.
        """
        from jarvis.infrastructure import assumption_dialogue as ad

        try:
            meta = json.loads(view.get("private_metadata") or "")
        except (TypeError, ValueError):
            logger.warning("digest_note_bad_private_metadata")
            return

        request_id = str(meta.get("request_id") or "")
        approval_subject = str(meta.get("approval_subject") or "")
        correlation_id = meta.get("correlation_id") or None
        channel_id = meta.get("channel")
        message_ts = meta.get("message_ts")
        if not request_id or not approval_subject:
            logger.warning("digest_note_incomplete_metadata", request_id=request_id)
            return

        note = ad.read_note_submission(view).strip()
        if not note:
            # Only reachable from a stale or hand-made submission: the modal's
            # input is required.
            logger.warning("digest_note_empty_dropped", request_id=request_id)
            return

        async with self._decision_lock:
            blocks = await self._fetch_dialogue_blocks(channel_id, message_ts, payload)
            state = ad.parse_dialogue_blocks(blocks)
            published = await self._publish_dialogue_decision(
                request_id=request_id,
                approval_subject=approval_subject,
                correlation_id=correlation_id,
                decided_by=user_id,
                decision="reject",
                dispositions=self._dispositions_from_state(state),
                notes=note,
            )
            if not published:
                return
            # The machine reads a note whose first word is "reject" as the
            # owner cancelling the run, so the card must not promise a
            # rewrite that will never come.
            first_word = note.split(None, 1)[0].rstrip(".,:;!?-\u2013\u2014").lower()
            if first_word == "reject":
                status_line = (
                    "You said reject, so this run will be cancelled and "
                    "nothing will be built. Send a fresh sentence whenever "
                    "you are ready to start again."
                )
            else:
                status_line = (
                    "Your note is with the machine. It will rewrite the spec "
                    "from it and come back with a fresh list."
                )
            await self._dialogue_status_update(
                channel_id,
                message_ts,
                payload,
                status_line,
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
                # Plain-name sweep (factory phrase-book, ratified 2026-07-31):
                # the refusal a Slack reader sees says "build approvals", not
                # the "forge" codename.
                text=("You are not authorized to decide build approvals from Slack."),
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


def _extract_action_value(action: dict[str, Any]) -> str:
    """The clicked control's ``value`` — button or overflow (SPL-003 J03a).

    A plain button carries ``value`` directly; an overflow menu (the
    ``planning_cancel`` abort) carries it under ``selected_option.value``.
    """
    if action.get("type") == "overflow":
        return str((action.get("selected_option") or {}).get("value") or "")
    return str(action.get("value") or "")


def _already_terminal_text(record: TerminalBuildRecord) -> str:
    """The honest answer to a tap on an already-terminal build (R3-B).

    Time is the retained terminal event's ``completed_at`` rendered as
    local HH:MM — the same stamp the R3-A card update shows.
    """
    hhmm = render_local_hhmm(record.at)
    if record.terminal_state == "build_cancelled":
        return f"This build was already cancelled at {hhmm} — your tap was not recorded."
    if record.terminal_state == "build_complete":
        return f"This build already completed at {hhmm} — your tap was not recorded."
    return f"This build already failed at {hhmm} — your tap was not recorded."


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
    operator_ids: frozenset[str],
    publisher: ApprovalResponsePublisher,
    web_client: Any | None = None,
    terminal_registry: TerminalBuildRegistry | None = None,
    spec_texts: SpecTextRegistry | None = None,
    audience: BuildAudienceRegistry | None = None,
) -> ApprovalReplyHandler:
    """Public factory for :class:`ApprovalReplyHandler`.

    Args:
        operator_ids: The resolved allowlist of Slack member ids permitted
            to decide approvals (the AUTHORIZATION gate). Normally
            :meth:`JarvisConfig.resolve_operator_allowlist`. Empty means the
            handler refuses every click — but the factory
            :func:`create_slack_reply_client` short-circuits to a logged
            no-op before building a handler in that case (TASK-JNB-110).
        publisher: The :class:`ApprovalResponsePublisher` seam.
        web_client: Optional Slack ``AsyncWebClient`` for ``chat.update``
            / ``chat.postEphemeral``. ``None`` degrades those to logged
            no-ops (intentional — see module docstring C2 note).
        terminal_registry: Shared terminal-state registry (approval-card
            truth R3-B) written by the notification sink; the handler
            consults it before publishing so a tap on an already-terminal
            build is answered honestly instead of published into forge's
            silent drop. ``None`` (unwired) keeps today's behaviour.
        spec_texts: Shared store of the worked examples behind a spec digest
            card, written by the planning checkpoint renderer; read when the
            owner asks to see them. ``None`` (unwired) makes that one button
            answer honestly that they are not to hand.
        audience: Shared who-to-tell registry (build-side mention lane);
            the handler WRITES ``build_id -> clicker`` so the notification
            sink can @-mention the person who asked for the build when it
            ends. ``None`` (unwired) records nothing.

    Returns:
        A ready :class:`ApprovalReplyHandler`.
    """
    return ApprovalReplyHandler(
        operator_ids=operator_ids,
        publisher=publisher,
        web_client=web_client,
        terminal_registry=terminal_registry,
        spec_texts=spec_texts,
        audience=audience,
    )


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

    TASK-SPL-J02: this client now hosts BOTH Slack Socket Mode features —
    the approval reply path (``interactive`` requests → ``handler``) and
    planning intake (``events_api`` requests → ``events_handler``,
    FEAT-SPL-001). One connection per process is the only correct Slack
    topology (Slack load-balances envelope deliveries across an app's open
    connections, and this listener acks every envelope — a second
    connection would ack-and-drop the other feature's traffic). Routing
    happens INSIDE the single ack-first :meth:`_on_request`; exactly one
    ack per envelope. Either handler may be ``None`` (that feature
    unconfigured — the factory's union gate); the class name is kept for
    diff-minimality while the JNB-107 live validation is pending.
    """

    __slots__ = (
        "_app_token",
        "_client",
        "_events_handler",
        "_handler",
        "_started",
        "_stop_timeout",
        "_web_client",
    )

    def __init__(
        self,
        *,
        app_token: str,
        handler: ApprovalReplyHandler | None,
        web_client: Any,
        events_handler: PlanningIntakeHandler | None = None,
        stop_timeout: float = _DEFAULT_STOP_TIMEOUT,
    ) -> None:
        self._app_token = app_token
        self._handler = handler
        self._events_handler = events_handler
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
            # Request-type router (TASK-SPL-J02): one connection, one ack,
            # then per-feature dispatch. Both handlers are None-safe — an
            # unconfigured feature's requests are acked and dropped.
            if req.type == "interactive":
                if self._handler is None:
                    return
                payload = req.payload or {}
                ptype = payload.get("type")
                if ptype == "block_actions":
                    # handle_block_actions never raises (DDR-007).
                    await self._handler.handle_block_actions(payload)
                elif ptype == "view_submission":
                    # TASK-SPL003-J03b — the edit-modal submission (previously
                    # dropped). Acked upstream already; never raises (DDR-007).
                    await self._handler.handle_view_submission(payload)
                else:
                    return
            elif req.type == "events_api":
                if self._events_handler is None:
                    return
                # handle_message_event never raises (DDR-007).
                await self._events_handler.handle_message_event(req.payload or {})
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


def _warn_deprecated_identity_settings(config: JarvisConfig) -> None:
    """Emit TASK-JNB-110 deprecation notices for superseded identity config.

    ``JARVIS_SLACK_DECIDED_BY`` is now IGNORED — decided_by is the clicker's
    member id — so a still-set value is a WARNING (a real behaviour change the
    operator must act on). The singular ``JARVIS_SLACK_OPERATOR_USER_ID`` is
    still honoured (folded into the allowlist), so its supersession is a
    gentler info-level notice. Both fire regardless of whether the reply path
    is otherwise configured, so the signal is never swallowed by an early
    no-op return.
    """
    if config.slack_decided_by:
        logger.warning(
            "slack_reply_decided_by_deprecated",
            detail=(
                "JARVIS_SLACK_DECIDED_BY is deprecated and IGNORED (TASK-JNB-110): "
                "decided_by is now the actual clicker's Slack member id, not a "
                "config constant. Remove it from your environment; set forge's "
                "approval.expected_approver to the approver's Slack member id."
            ),
        )
    if config.slack_operator_user_id:
        logger.info(
            "slack_reply_operator_user_id_deprecated",
            detail=(
                "JARVIS_SLACK_OPERATOR_USER_ID (singular) is deprecated "
                "(TASK-JNB-110); prefer the comma-separated allowlist "
                "JARVIS_SLACK_OPERATOR_USER_IDS. The singular value is still "
                "honoured as one allowlist entry."
            ),
        )


def create_slack_reply_client(
    config: JarvisConfig,
    nats_client: NATSClient | None,
    *,
    terminal_registry: TerminalBuildRegistry | None = None,
    spec_texts: SpecTextRegistry | None = None,
    audience: BuildAudienceRegistry | None = None,
) -> SlackSocketModeReplyClient | None:
    """Create the shared Socket Mode client, or a logged no-op (``None``).

    Union gate (TASK-SPL-J02 / TASK-REV-3240 F1): the ONE Socket Mode
    connection is constructed when the shared prerequisites are met AND at
    least one hosted feature is fully configured. Each feature is gated by
    its OWN settings and logs its OWN no-op reason — an unset operator id
    must never silently kill planning intake, and unset planning keys must
    never touch the approval reply path.

    Shared prerequisites (each logged as ``slack_reply_no_op``):

    * ``slack_app_token`` unset — no Socket Mode surface at all.
    * ``slack_bot_token`` unset — no web client for chat.* calls (and no
      button/ack surface exists either).
    * ``nats_client is None`` — nothing to publish to (DDR-021-style soft
      degradation).

    Per-feature gates:

    * Approval reply path (``interactive``): an EMPTY operator allowlist
      (:meth:`~jarvis.config.settings.JarvisConfig.resolve_operator_allowlist`
      — neither ``slack_operator_user_ids`` nor the deprecated singular
      ``slack_operator_user_id`` set) → ``slack_reply_no_op`` and no
      interactive handler.
    * Planning intake (``events_api``, FEAT-SPL-001): its factory
      (:func:`~jarvis.infrastructure.slack_planning_intake.create_slack_planning_intake_handler`)
      logs ``slack_planning_intake_no_op`` naming the missing key(s).

    Neither feature configured → ``None`` (no connection).
    The supervisor starts and runs normally in every no-op permutation.

    TASK-JNB-110 deprecations (emitted before any early return so operators
    always see them): ``JARVIS_SLACK_DECIDED_BY`` is now ignored (a WARNING),
    and the singular ``JARVIS_SLACK_OPERATOR_USER_ID`` is superseded by the
    plural allowlist (an info-level notice — the value is still honoured).
    """
    _warn_deprecated_identity_settings(config)

    app_token_secret = config.slack_app_token
    app_token = app_token_secret.get_secret_value() if app_token_secret is not None else None
    operator_ids = config.resolve_operator_allowlist()
    bot_token_secret = config.slack_bot_token
    bot_token = bot_token_secret.get_secret_value() if bot_token_secret is not None else None

    if not app_token:
        logger.info(
            "slack_reply_no_op",
            reason="slack_app_token not configured; Slack Socket Mode disabled",
        )
        return None
    if not bot_token:
        logger.info(
            "slack_reply_no_op",
            reason="slack_bot_token not configured; Slack Socket Mode disabled",
        )
        return None
    if nats_client is None:
        logger.info(
            "slack_reply_no_op",
            reason="NATS unavailable; Slack Socket Mode disabled",
        )
        return None

    from slack_sdk.web.async_client import AsyncWebClient

    from jarvis.infrastructure.slack_planning_intake import (
        create_slack_planning_intake_handler,
    )

    web_client = AsyncWebClient(token=bot_token)

    handler: ApprovalReplyHandler | None = None
    if operator_ids:
        handler = build_reply_handler(
            operator_ids=operator_ids,
            publisher=NatsApprovalResponsePublisher(nats_client),
            web_client=web_client,
            terminal_registry=terminal_registry,
            spec_texts=spec_texts,
            audience=audience,
        )
    else:
        logger.info(
            "slack_reply_no_op",
            reason=(
                "no slack_operator_user_ids configured (and no deprecated "
                "slack_operator_user_id); approval reply path disabled"
            ),
        )

    events_handler = create_slack_planning_intake_handler(config, nats_client, web_client)

    if handler is None and events_handler is None:
        logger.info(
            "slack_reply_no_op",
            reason=(
                "no Slack Socket Mode feature configured (approval reply "
                "path and planning intake both disabled); connection not started"
            ),
        )
        return None

    return SlackSocketModeReplyClient(
        app_token=app_token,
        handler=handler,
        web_client=web_client,
        events_handler=events_handler,
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
