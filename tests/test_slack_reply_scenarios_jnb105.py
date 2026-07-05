"""TASK-JNB-105 — v1.1 reply-path scenario tests (plain pytest).

Plain pytest only — NO pytest-bdd ``.feature`` glue (operator decision
2026-07-03; eliminates a known silent-false-green class). Each test class
below mirrors one of the six spec scenarios named in TASK-JNB-105's Test
Requirements, plus a contract class that validates the published envelope
against the *installed* ``nats_core`` ``ApprovalResponsePayload`` model.

System under test = the reply path delivered by TASK-JNB-104
(``src/jarvis/infrastructure/slack_reply.py``). This task tests that
implementation as delivered — it does NOT redesign it (JNB-105 Implementation
Notes). Tests are fully hermetic: the Slack ``AsyncWebClient`` surface is an
``AsyncMock``, the JetStream publisher is either a ``MagicMock`` seam (scenario
classes) or the real ``NatsApprovalResponsePublisher`` over a fake JetStream
(contract class). The only real third-party dependency exercised is the
installed ``nats_core`` package, used to validate the wire bytes.

Scenario→class map (JNB-105 Test Requirements 1-6 + contract):

1. Unauthorized responder refusal   → ``TestUnauthorizedResponderRefusal``
2. Duplicate click single-publish   → ``TestDuplicateClickSinglePublish``
3. Approve one, not another         → ``TestApproveOneNotAnother`` (G1)
4. Unrecognised decision …          → ``TestUnrecognisedDecisionNeverOfferedNorPublished``
5. Buttons disabled after decision  → ``TestButtonsDisabledAfterDecision``
6. Reply after ended (stale)        → ``TestReplyAfterEnded`` (reconciled — see class docstring)
   contract                         → ``TestReplyPathEnvelopeContract`` (G2)

Collect-only count guard (JNB-105 AC): this module defines exactly **10**
tests. Verify with::

    .venv/bin/python -m pytest tests/test_slack_reply_scenarios_jnb105.py --collect-only -q

A mismatch against 9 is a hard failure — this is the silently-uncollected-test
guard that motivated dropping pytest-bdd.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.infrastructure.slack_notifier import build_pause_blocks
from jarvis.infrastructure.slack_reply import (
    _ACTION_DECISIONS,
    NatsApprovalResponsePublisher,
    SlackSocketModeReplyClient,
    build_reply_handler,
)

_OPERATOR = "U0OPERATOR"

# JNB-105 contract AC: forge compares decided_by against expected_approver by
# exact string equality, so the contract test pins the verbatim round-trip.
_DECIDED_BY = "rich-slack-operator"


# ---------------------------------------------------------------------------
# Helpers (self-contained — no cross-test-module import coupling)
# ---------------------------------------------------------------------------


def _button_value(
    *,
    request_id: str = "apr-001",
    build_id: str = "build-abc123",
    correlation_id: str = "corr-1",
    approval_subject: str = "agents.approval.forge.build-abc123",
) -> str:
    """Compact BUTTON_METADATA value JSON (the TASK-JNB-103 producer contract)."""
    return json.dumps(
        {
            "request_id": request_id,
            "build_id": build_id,
            "correlation_id": correlation_id,
            "approval_subject": approval_subject,
        },
        separators=(",", ":"),
    )


def _original_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "section",
            "text": {"type": "plain_text", "text": "build-paused", "emoji": False},
        },
        {"type": "actions", "block_id": "forge_approval", "elements": []},
    ]


def _click_payload(
    *,
    user_id: str = _OPERATOR,
    action_id: str = "forge_approve",
    value: str | None = None,
    channel_id: str | None = "C123456",
    message_ts: str = "1720.0001",
    blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """A synthetic Slack ``block_actions`` interaction payload."""
    payload: dict[str, Any] = {
        "type": "block_actions",
        "user": {"id": user_id},
        "container": {
            "type": "message",
            "channel_id": channel_id,
            "message_ts": message_ts,
        },
        "message": {"blocks": blocks if blocks is not None else _original_blocks()},
        "actions": [
            {
                "action_id": action_id,
                "block_id": "forge_approval",
                "value": value if value is not None else _button_value(),
            }
        ],
    }
    if channel_id is not None:
        payload["channel"] = {"id": channel_id}
    return payload


def _make_handler(
    *,
    operator: str | None = _OPERATOR,
    decided_by: str | None = "jarvis-op",
) -> tuple[Any, MagicMock, AsyncMock, Any]:
    """Handler over a ``MagicMock`` publisher seam + ``AsyncMock`` web client."""
    settings = SimpleNamespace(
        slack_operator_user_id=operator,
        slack_decided_by=decided_by,
    )
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web_client = AsyncMock()
    handler = build_reply_handler(settings=settings, publisher=publisher, web_client=web_client)
    return handler, publisher, web_client, settings


def _actions_in(blocks: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [b for b in (blocks or []) if b.get("type") == "actions"]


# ---------------------------------------------------------------------------
# 1. Unauthorized responder refusal
# ---------------------------------------------------------------------------


class TestUnauthorizedResponderRefusal:
    """A ``block_actions`` from a non-operator: WARN + ephemeral, zero publishes."""

    @pytest.mark.asyncio
    async def test_wrong_user_warns_refuses_and_publishes_nothing(self) -> None:
        handler, publisher, web_client, _ = _make_handler()

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload(user_id="U0INTRUDER"))

        publisher.publish.assert_not_awaited()
        web_client.chat_postEphemeral.assert_awaited_once()
        assert web_client.chat_postEphemeral.await_args.kwargs["user"] == "U0INTRUDER"
        web_client.chat_update.assert_not_awaited()
        # The AC binds a WARNING (not just the event name).
        assert any(
            log["event"] == "slack_reply_unauthorized_click" and log["log_level"] == "warning"
            for log in logs
        )


# ---------------------------------------------------------------------------
# 2. Duplicate click single-publish
# ---------------------------------------------------------------------------


class TestDuplicateClickSinglePublish:
    """Two identical authorized clicks: both acked, published exactly once.

    JNB-105 scenario 2 binds BOTH halves — "exactly one publish" AND "both
    clicks are acked". The ack lives only in
    ``SlackSocketModeReplyClient._on_request`` (not in the bare handler), so
    this drives the duplicate deliveries through the registered listener with
    an ack-capturing SDK client — the mandated mocking strategy.
    """

    @pytest.mark.asyncio
    async def test_both_duplicate_clicks_acked_and_published_once(self) -> None:
        handler, publisher, _, _ = _make_handler()
        reply_client = SlackSocketModeReplyClient(
            app_token="xapp-test", handler=handler, web_client=AsyncMock()
        )

        sdk_client = MagicMock()
        sdk_client.send_socket_mode_response = AsyncMock()
        value = _button_value()
        # Two deliveries of the same button (e.g. a missed-ack redelivery):
        # distinct envelope ids, identical button value.
        req1 = SimpleNamespace(
            type="interactive", envelope_id="env-1", payload=_click_payload(value=value)
        )
        req2 = SimpleNamespace(
            type="interactive", envelope_id="env-2", payload=_click_payload(value=value)
        )

        await reply_client._on_request(sdk_client, req1)
        await reply_client._on_request(sdk_client, req2)

        # Both envelopes acked …
        assert sdk_client.send_socket_mode_response.await_count == 2
        # … but the decision is published exactly once (first-click-wins).
        publisher.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# 3. Approve one, not another (G1)
# ---------------------------------------------------------------------------


class TestApproveOneNotAnother:
    """Two paused builds with distinct metadata; approving A never touches B."""

    @pytest.mark.asyncio
    async def test_approving_build_a_publishes_only_a_and_leaves_b_live(self) -> None:
        handler, publisher, web_client, _ = _make_handler()

        build_a_value = _button_value(
            request_id="apr-A",
            build_id="build-A",
            correlation_id="corr-A",
            approval_subject="agents.approval.forge.build-A",
        )
        # Build B exists concurrently with its own live buttons on a separate
        # Slack message (distinct message_ts). The operator taps A only.
        b_request_id = "apr-B"
        b_subject = "agents.approval.forge.build-B"
        b_message_ts = "1720.BBBB"

        await handler.handle_block_actions(
            _click_payload(value=build_a_value, message_ts="1720.AAAA")
        )

        # Exactly one publish, routed to A with A's request_id + correlation_id.
        publisher.publish.assert_awaited_once()
        kwargs = publisher.publish.await_args.kwargs
        assert kwargs["subject"] == "agents.approval.forge.build-A.response"
        assert kwargs["correlation_id"] == "corr-A"
        assert kwargs["payload"].request_id == "apr-A"

        # Nothing references build B.
        assert kwargs["subject"] != b_subject + ".response"
        assert kwargs["payload"].request_id != b_request_id

        # B's buttons remain live: the handler only ever updates the message it
        # received the click on (A's message_ts) — it never issues a chat.update
        # against B's message.
        updated_ts = {call.kwargs.get("ts") for call in web_client.chat_update.await_args_list}
        assert b_message_ts not in updated_ts
        assert updated_ts <= {"1720.AAAA"}


# ---------------------------------------------------------------------------
# 4. Unrecognised decision never offered nor published
# ---------------------------------------------------------------------------


class TestUnrecognisedDecisionNeverOfferedNorPublished:
    """Only approve/reject are recognised; any other decision publishes nothing."""

    @pytest.mark.asyncio
    async def test_unknown_decision_publishes_nothing(self) -> None:
        handler, publisher, _, _ = _make_handler()

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload(action_id="forge_escalate"))

        publisher.publish.assert_not_awaited()
        assert any(log["event"] == "slack_reply_unknown_action_dropped" for log in logs)

    def test_reply_path_recognises_only_approve_and_reject(self) -> None:
        # Consumer-side pin: the reply path offers/accepts exactly the two
        # action_ids TASK-JNB-103 places on the buttons — a third decision is
        # neither routable nor publishable.
        assert _ACTION_DECISIONS == {"forge_approve": "approve", "forge_reject": "reject"}

    def test_rendered_pause_blocks_offer_only_approve_and_reject(self) -> None:
        # Producer-side "never offered": the rendered Block Kit pause message
        # (TASK-JNB-103, in this task's SUT scope) exposes an actions block with
        # EXACTLY the two action_ids — a third button would be offered here.
        notification = ForgeNotification(
            correlation_id="corr-1",
            feature_id="FEAT-BF39",
            completed_at=datetime(2026, 7, 5, 12, 0, tzinfo=UTC),
        )
        blocks = build_pause_blocks(notification, button_value=_button_value())

        actions = _actions_in(blocks)
        assert len(actions) == 1
        elements = actions[0]["elements"]
        assert [el["action_id"] for el in elements] == ["forge_approve", "forge_reject"]


# ---------------------------------------------------------------------------
# 5. Buttons disabled after decision
# ---------------------------------------------------------------------------


class TestButtonsDisabledAfterDecision:
    """After an authorized decision, chat.update replaces the buttons in place."""

    @pytest.mark.asyncio
    async def test_authorized_decision_disables_buttons_in_place(self) -> None:
        handler, _, web_client, _ = _make_handler()

        await handler.handle_block_actions(_click_payload(action_id="forge_approve"))

        # Final chat.update is the success update: interactive actions removed,
        # decided rendering shown.
        final_kwargs = web_client.chat_update.await_args.kwargs
        assert _actions_in(final_kwargs["blocks"]) == []
        joined = " ".join(b["text"]["text"] for b in final_kwargs["blocks"] if b.get("text"))
        assert "Decision recorded: approve" in joined


# ---------------------------------------------------------------------------
# 6. Reply after ended (stale buttons) — RECONCILED (Rich, 2026-07-05, Option A)
# ---------------------------------------------------------------------------


class TestReplyAfterEnded:
    """A well-formed authorized click for an ended/expired build still publishes.

    JNB-105's original scenario 6 assumed a jarvis-local refusal for a
    ``request_id`` absent from a pending map. The delivered JNB-104 reply path
    has NO pending map (``ApprovalReplyHandler.__slots__`` carries none, and
    ``create_slack_reply_client`` passes none): it publishes self-containedly
    from the button value JSON. This is the deliberate DDR-027 posture — handoff
    §6 "old buttons after a jarvis restart still work; the reply path needs no
    in-memory state to publish" — with forge (TASK-JNB-106) as the authoritative
    refuser (correlation mismatch / request_id 300s dedup / expected_approver).

    So this test asserts the DELIVERED behaviour: the stale click STILL
    publishes. Staleness enforcement is forge-side, not jarvis-side.
    """

    @pytest.mark.asyncio
    async def test_wellformed_stale_click_still_publishes_forge_is_authoritative(self) -> None:
        handler, publisher, _, _ = _make_handler()

        # A request_id no pending map ever knew about (the build has ended). A
        # fresh handler has never seen it, yet the click is well-formed and
        # authorized — the handler publishes and lets forge refuse if stale.
        stale_value = _button_value(
            request_id="apr-ended-999",
            build_id="build-ended",
            correlation_id="corr-ended",
            approval_subject="agents.approval.forge.build-ended",
        )

        await handler.handle_block_actions(_click_payload(value=stale_value))

        publisher.publish.assert_awaited_once()
        kwargs = publisher.publish.await_args.kwargs
        assert kwargs["subject"] == "agents.approval.forge.build-ended.response"
        assert kwargs["payload"].request_id == "apr-ended-999"


# ---------------------------------------------------------------------------
# Contract — wire bytes validate against the installed nats_core model (G2)
# ---------------------------------------------------------------------------


class TestReplyPathEnvelopeContract:
    """Drive an authorized click through the REAL publisher + fake JetStream,
    then validate the captured wire bytes against the installed ``nats_core``
    ``ApprovalResponsePayload`` / ``MessageEnvelope`` models."""

    @staticmethod
    def _wired() -> tuple[Any, MagicMock, Any]:
        settings = SimpleNamespace(
            slack_operator_user_id=_OPERATOR,
            slack_decided_by=_DECIDED_BY,
        )
        fake_nats = MagicMock()
        fake_nats.js.publish = AsyncMock()
        publisher = NatsApprovalResponsePublisher(fake_nats)
        web_client = AsyncMock()
        handler = build_reply_handler(settings=settings, publisher=publisher, web_client=web_client)
        return handler, fake_nats, settings

    @pytest.mark.asyncio
    async def test_approve_bytes_validate_and_decided_by_verbatim(self) -> None:
        from nats_core import EventType, MessageEnvelope
        from nats_core.events import ApprovalResponsePayload

        handler, fake_nats, settings = self._wired()

        await handler.handle_block_actions(
            _click_payload(
                action_id="forge_approve",
                value=_button_value(
                    request_id="apr-777",
                    build_id="build-xyz",
                    correlation_id="corr-777",
                    approval_subject="agents.approval.forge.build-xyz",
                ),
            )
        )

        fake_nats.js.publish.assert_awaited_once()
        subject, data = fake_nats.js.publish.await_args.args
        assert subject == "agents.approval.forge.build-xyz.response"

        # Validate the envelope + payload against the INSTALLED nats_core models.
        envelope = MessageEnvelope.model_validate_json(data)
        assert envelope.event_type == EventType.APPROVAL_RESPONSE
        assert envelope.correlation_id == "corr-777"

        payload = ApprovalResponsePayload.model_validate(envelope.payload)
        assert payload.request_id == "apr-777"
        assert payload.decision in {"approve", "reject"}
        assert payload.decision == "approve"
        # decided_by must equal settings.slack_decided_by VERBATIM (forge
        # compares it against expected_approver by exact string equality).
        assert payload.decided_by == settings.slack_decided_by == _DECIDED_BY

    @pytest.mark.asyncio
    async def test_reject_bytes_validate_against_installed_nats_core(self) -> None:
        from nats_core import MessageEnvelope
        from nats_core.events import ApprovalResponsePayload

        handler, fake_nats, settings = self._wired()

        await handler.handle_block_actions(
            _click_payload(
                action_id="forge_reject",
                value=_button_value(
                    request_id="apr-888",
                    build_id="build-zzz",
                    correlation_id="corr-888",
                    approval_subject="agents.approval.forge.build-zzz",
                ),
            )
        )

        fake_nats.js.publish.assert_awaited_once()
        subject, data = fake_nats.js.publish.await_args.args
        assert subject == "agents.approval.forge.build-zzz.response"

        envelope = MessageEnvelope.model_validate_json(data)
        payload = ApprovalResponsePayload.model_validate(envelope.payload)
        assert payload.request_id == "apr-888"
        assert payload.decision == "reject"
        assert payload.decided_by == settings.slack_decided_by == _DECIDED_BY
