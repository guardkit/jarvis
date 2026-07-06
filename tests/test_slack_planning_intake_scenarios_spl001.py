"""TASK-SPL-J03 — FEAT-SPL-001 scenario + contract tests (plain pytest).

Plain pytest only — NO pytest-bdd ``.feature`` glue (operator decision
2026-07-03). One test class per spec scenario in
``features/feat-spl-001-slack-planning-intake/feat-spl-001-slack-planning-intake.feature``
(18 scenarios; the length Scenario Outline collapses into one parametrized
class), plus the G2-style contract class validating the published wire bytes
against the *installed* ``nats_core`` models.

System under test = the intake path delivered by TASK-SPL-J01
(``slack_planning_intake.py``) riding the shared Socket Mode client as wired
by TASK-SPL-J02 (``slack_reply.py`` request-type router + union gate). Tests
are fully hermetic: Socket Mode requests are ``SimpleNamespace`` envelopes
driven through ``SlackSocketModeReplyClient._on_request``, the Slack
``AsyncWebClient`` is an ``AsyncMock``, and the JetStream publisher is either
a ``MagicMock`` seam (scenario classes) or the real
``NatsPlanningQueuedPublisher`` over a fake JetStream (contract class). The
only real third-party dependency exercised is the installed ``nats_core``.

"Verbatim" = verbatim-modulo-the-contract's-outer-whitespace-strip
(TASK-REV-3240 F10): ``PlanningQueuedPayload`` strips ``request_text``.

Scenario→class map (spec order):

 1. Idea queued for planning              → ``TestPlanningIdeaQueued``
 2. In-thread ack with correlation id     → ``TestInThreadAcknowledgement``
 3. Traceable to originating message      → ``TestTraceability``
 4. Verbatim without any reasoning        → ``TestVerbatimNoReasoning``
 5. Valid against installed contract      → ``TestPlanningQueuedEnvelopeContract`` (G2)
 6. Ideas of any practical length (x3)    → ``TestIdeaLengthBoundaries``
 7. Whitespace-only not queued            → ``TestWhitespaceOnlyDiscarded``
 8. Unauthorized member ignored           → ``TestUnauthorizedOriginatorIgnored``
 9. Other channel ignored                 → ``TestOtherChannelIgnored``
10. Bot-authored ignored (self-ack)       → ``TestBotAuthoredIgnored``
11. Thread reply not intake               → ``TestThreadReplyNotIntake``
12. Edit/delete notifications (x2)        → ``TestEditDeleteNotIntake``
13. Unconfigured intake no-op             → ``TestUnconfiguredIntakeNoOp``
14. Pipeline outage failure notice        → ``TestPipelineOutageFailureNotice``
15. Redelivered event queued once         → ``TestRedeliveredEventOnce`` (listener-driven)
16. Failed ack does not undo              → ``TestFailedAckDoesNotUndo``
17. Reconnect exactly once                → ``TestReconnectExactlyOnce``
18. Approval buttons coexist              → ``TestApprovalButtonsCoexist``

Collect-only count guard (TASK-SPL-J03 AC): this module defines exactly
**22** tests. Verify with::

    .venv/bin/python -m pytest \\
        tests/test_slack_planning_intake_scenarios_spl001.py --collect-only -q

Live-only facts explicitly OUT of this suite (TASK-SPL-J04's operator
checklist, TASK-REV-3240 RISK-3): (1) the Slack app manifest actually carries
the message.channels/message.groups subscriptions and the bot is in the
channel; (2) real Socket Mode co-delivers events_api + interactive envelopes
on the one shared connection; (3) the real redelivery dedup key (stable
event_id vs channel:ts fallback); (4) Slack's behavior at its own maximum
message length. The reconnect scenario is proven hermetically as
registration-once + dedup-holds; the SDK's auto_reconnect invariant stays a
docstring-pinned code-inspection fact per JNB-104.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.slack_planning_intake import (
    NatsPlanningQueuedPublisher,
    PlanningIntakeHandler,
)
from jarvis.infrastructure.slack_reply import (
    SlackSocketModeReplyClient,
    build_reply_handler,
)

_JAMES = "U0JAMES"
_CHANNEL = "C0PLANNING"
_TS = "1751795701.000200"
_OPERATOR = "U0OPERATOR"


# ---------------------------------------------------------------------------
# Helpers (self-contained — no cross-test-module import coupling)
# ---------------------------------------------------------------------------


def _message_envelope_payload(
    *,
    user: str | None = _JAMES,
    text: str | None = "Add PDF export to the reporting dashboard",
    channel: str = _CHANNEL,
    ts: str = _TS,
    event_id: str | None = "Ev00000001",
    **event_extra: Any,
) -> dict[str, Any]:
    """A synthetic Slack ``events_api`` envelope payload (event_callback)."""
    event: dict[str, Any] = {"type": "message", "channel": channel, "ts": ts}
    if user is not None:
        event["user"] = user
    if text is not None:
        event["text"] = text
    event.update(event_extra)
    payload: dict[str, Any] = {"type": "event_callback", "event": event}
    if event_id is not None:
        payload["event_id"] = event_id
    return payload


def _make_client(
    *,
    intake_publisher: Any | None = None,
    approval_handler: Any | None = None,
    web_client: Any | None = "default",
) -> tuple[SlackSocketModeReplyClient, Any, Any]:
    """A shared client with a REAL intake handler over a mock publisher seam."""
    publisher = intake_publisher
    if publisher is None:
        publisher = MagicMock()
        publisher.publish = AsyncMock()
    wc = AsyncMock() if web_client == "default" else web_client
    intake = PlanningIntakeHandler(
        channel_id=_CHANNEL,
        originator_ids=frozenset({_JAMES}),
        publisher=publisher,
        web_client=wc,
    )
    client = SlackSocketModeReplyClient(
        app_token="xapp-test",
        handler=approval_handler,
        web_client=wc,
        events_handler=intake,
    )
    return client, publisher, wc


async def _deliver(
    client: SlackSocketModeReplyClient,
    payload: dict[str, Any],
    *,
    req_type: str = "events_api",
    envelope_id: str = "env-1",
) -> AsyncMock:
    """Drive one Socket Mode request through the shared listener."""
    socket_client = MagicMock()
    socket_client.send_socket_mode_response = AsyncMock()
    req = SimpleNamespace(type=req_type, envelope_id=envelope_id, payload=payload)
    await client._on_request(socket_client, req)
    return socket_client.send_socket_mode_response


def _published(publisher: Any) -> dict[str, Any]:
    assert publisher.publish.await_count == 1
    return publisher.publish.await_args.kwargs


# ---------------------------------------------------------------------------
# Scenario 1 — A planning idea posted in the channel is queued for planning
# ---------------------------------------------------------------------------


class TestPlanningIdeaQueued:
    @pytest.mark.asyncio
    async def test_channel_message_becomes_exactly_one_planning_request(self) -> None:
        client, publisher, _ = _make_client()
        ack = await _deliver(client, _message_envelope_payload())
        ack.assert_awaited_once()  # ack-first discipline holds on the shared listener
        kwargs = _published(publisher)
        payload = kwargs["payload"]
        assert payload.stage == "planning"
        assert payload.request_text == "Add PDF export to the reporting dashboard"
        assert payload.originating_user == _JAMES
        assert payload.triggered_by == "jarvis"
        assert payload.originating_adapter == "slack"


# ---------------------------------------------------------------------------
# Scenario 2 — In-thread acknowledgement carrying the correlation identifier
# ---------------------------------------------------------------------------


class TestInThreadAcknowledgement:
    @pytest.mark.asyncio
    async def test_ack_is_threaded_on_the_original_and_carries_the_correlation_id(
        self,
    ) -> None:
        client, publisher, wc = _make_client()
        await _deliver(client, _message_envelope_payload())
        correlation_id = _published(publisher)["payload"].correlation_id
        wc.chat_postMessage.assert_awaited_once()
        kwargs = wc.chat_postMessage.await_args.kwargs
        assert kwargs["channel"] == _CHANNEL
        assert kwargs["thread_ts"] == _TS  # in-thread, nowhere else
        assert correlation_id in kwargs["text"]


# ---------------------------------------------------------------------------
# Scenario 3 — Traceable back to the originating Slack message
# ---------------------------------------------------------------------------


class TestTraceability:
    @pytest.mark.asyncio
    async def test_subject_parent_and_timestamps_pin_the_originating_message(self) -> None:
        client, publisher, _ = _make_client()
        await _deliver(client, _message_envelope_payload())
        kwargs = _published(publisher)
        payload = kwargs["payload"]
        assert kwargs["subject"] == f"pipeline.planning-queued.{payload.correlation_id}"
        assert payload.parent_request_id == _TS
        assert payload.requested_at.timestamp() == pytest.approx(1751795701.0002)
        assert payload.queued_at >= payload.requested_at


# ---------------------------------------------------------------------------
# Scenario 4 — Intake publishes the idea verbatim without any reasoning
# ---------------------------------------------------------------------------


class TestVerbatimNoReasoning:
    @pytest.mark.asyncio
    async def test_text_is_published_verbatim_and_nothing_else_is_invoked(self) -> None:
        # "No reasoning" hermetic proof: the intake path touches ONLY the
        # publisher and the web client — no supervisor, no DeepAgents graph,
        # no enrichment. Verbatim = modulo the contract's outer strip (F10).
        client, publisher, wc = _make_client()
        text = "  build a  thing — exactly as   typed  "
        await _deliver(client, _message_envelope_payload(text=text))
        payload = _published(publisher)["payload"]
        assert payload.request_text == text.strip()
        assert payload.target_repo is None  # ASSUM-004 — never parsed from text
        # Only two side-effect surfaces exist on the handler; both accounted,
        # and the web client saw NOTHING but the threaded ack:
        assert publisher.publish.await_count == 1
        assert wc.chat_postMessage.await_count == 1
        assert all(name == "chat_postMessage" for name, _, _ in wc.method_calls)


# ---------------------------------------------------------------------------
# Scenario 5 (G2) — Valid against the installed event contract
# ---------------------------------------------------------------------------


class TestPlanningQueuedEnvelopeContract:
    """Round-trips the REAL publisher's wire bytes through installed nats_core."""

    async def _capture_wire_bytes(self) -> tuple[str, bytes]:
        js = SimpleNamespace(publish=AsyncMock())
        nats_client = SimpleNamespace(js=js)
        client, _, _ = _make_client(
            intake_publisher=NatsPlanningQueuedPublisher(nats_client)  # type: ignore[arg-type]
        )
        await _deliver(client, _message_envelope_payload())
        subject, raw = js.publish.await_args.args
        return subject, raw

    @pytest.mark.asyncio
    async def test_wire_bytes_round_trip_through_installed_nats_core(self) -> None:
        from nats_core import EventType, MessageEnvelope
        from nats_core.events import PlanningQueuedPayload

        subject, raw = await self._capture_wire_bytes()
        envelope = MessageEnvelope.model_validate_json(raw)
        assert envelope.event_type == EventType.PLANNING_QUEUED  # recognised event
        assert envelope.source_id == "jarvis"
        reconstructed = PlanningQueuedPayload.model_validate(envelope.payload)
        assert reconstructed.stage == "planning"
        assert reconstructed.originating_user == _JAMES
        assert reconstructed.retry_count == 0
        assert reconstructed.target_repo is None
        assert subject == f"pipeline.planning-queued.{reconstructed.correlation_id}"
        assert envelope.correlation_id == reconstructed.correlation_id

    @pytest.mark.asyncio
    async def test_originating_adapter_is_explicitly_present_in_the_wire_bytes(self) -> None:
        # F4: the wire layer skips its required-when-jarvis validator when
        # the field is omitted — so the contract pin is on the RAW bytes,
        # never validator-inferred.
        _, raw = await self._capture_wire_bytes()
        wire = json.loads(raw)
        assert wire["payload"]["originating_adapter"] == "slack"


# ---------------------------------------------------------------------------
# Scenario 6 (outline) — Ideas of any practical length are queued verbatim
# ---------------------------------------------------------------------------


class TestIdeaLengthBoundaries:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "idea",
        [
            pytest.param("y", id="single-character"),
            pytest.param("An idea. " * 334, id="multi-paragraph-3000-chars"),
            pytest.param("x" * 40_000, id="slack-maximum-length"),
        ],
    )
    async def test_idea_is_queued_verbatim(self, idea: str) -> None:
        client, publisher, _ = _make_client()
        await _deliver(client, _message_envelope_payload(text=idea))
        assert _published(publisher)["payload"].request_text == idea.strip()


# ---------------------------------------------------------------------------
# Scenario 7 — A whitespace-only message is not queued
# ---------------------------------------------------------------------------


class TestWhitespaceOnlyDiscarded:
    @pytest.mark.asyncio
    async def test_no_queue_no_ack_and_a_metadata_only_discard_record(self) -> None:
        client, publisher, wc = _make_client()
        with capture_logs() as logs:
            await _deliver(client, _message_envelope_payload(text="  \n\t "))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()
        discards = [e for e in logs if e["event"] == "planning_intake_blank_dropped"]
        assert len(discards) == 1
        assert "text" not in discards[0]  # metadata only (F6)


# ---------------------------------------------------------------------------
# Scenario 8 — A message from anyone other than the authorized originator
# ---------------------------------------------------------------------------


class TestUnauthorizedOriginatorIgnored:
    @pytest.mark.asyncio
    async def test_no_queue_no_reply_and_an_info_refusal_record(self) -> None:
        client, publisher, wc = _make_client()
        with capture_logs() as logs:
            await _deliver(client, _message_envelope_payload(user="U0STRANGER"))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()  # silent-ignore (ASSUM-002)
        refusals = [e for e in logs if e["event"] == "planning_intake_unauthorized_dropped"]
        assert len(refusals) == 1
        assert refusals[0]["log_level"] == "info"  # F11 flood posture
        assert refusals[0]["user_id"] == "U0STRANGER"


# ---------------------------------------------------------------------------
# Scenario 9 — A message in a channel other than the planning channel
# ---------------------------------------------------------------------------


class TestOtherChannelIgnored:
    @pytest.mark.asyncio
    async def test_no_queue_and_no_reply_of_any_kind(self) -> None:
        client, publisher, wc = _make_client()
        await _deliver(client, _message_envelope_payload(channel="C0ELSEWHERE"))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 10 — Bot-authored messages ignored, including Jarvis's own acks
# ---------------------------------------------------------------------------


class TestBotAuthoredIgnored:
    @pytest.mark.asyncio
    async def test_realistic_self_ack_event_is_dropped_without_a_refusal(self) -> None:
        # Realistic fixture (F3): modern bot posts are SUBTYPE-FREE — bot_id
        # and app_id set, user = the bot's own user id, threaded like the
        # real ack. NOT subtype="bot_message" (legacy-only).
        client, publisher, wc = _make_client()
        self_ack = _message_envelope_payload(
            user="U0JARVISBOT",
            text="Queued for planning · `corr-1`",
            bot_id="B0JARVIS",
            app_id="A0JARVIS",
            thread_ts=_TS,
        )
        with capture_logs() as logs:
            await _deliver(client, self_ack)
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()  # no further reply — no loop
        assert not [e for e in logs if e["event"] == "planning_intake_unauthorized_dropped"]


# ---------------------------------------------------------------------------
# Scenario 11 — A reply inside a thread is not planning intake
# ---------------------------------------------------------------------------


class TestThreadReplyNotIntake:
    @pytest.mark.asyncio
    async def test_authorized_thread_reply_is_not_queued(self) -> None:
        client, publisher, _ = _make_client()
        await _deliver(client, _message_envelope_payload(thread_ts="1751795000.000100"))
        publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 12 — Message edit and delete notifications are not intake
# ---------------------------------------------------------------------------


class TestEditDeleteNotIntake:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("subtype", ["message_changed", "message_deleted"])
    async def test_subtyped_notification_is_not_queued(self, subtype: str) -> None:
        client, publisher, _ = _make_client()
        await _deliver(client, _message_envelope_payload(subtype=subtype))
        publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# Scenario 13 — Planning intake left unconfigured disables intake only
# ---------------------------------------------------------------------------


class TestUnconfiguredIntakeNoOp:
    def test_intake_no_ops_while_the_approval_reply_path_is_unaffected(self) -> None:
        from jarvis.config.settings import JarvisConfig
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        env = {
            "JARVIS_SLACK_BOT_TOKEN": "xoxb-t",
            "JARVIS_SLACK_APP_TOKEN": "xapp-t",
            "JARVIS_SLACK_OPERATOR_USER_ID": _OPERATOR,
            # no planning keys
        }
        with patch.dict("os.environ", env, clear=True):
            config = JarvisConfig(_env_file=None)
        with capture_logs() as logs:
            client = create_slack_reply_client(config, MagicMock())
        assert client is not None  # jarvis starts normally
        assert client._handler is not None  # reply path unaffected
        assert client._events_handler is None  # intake disabled
        noops = [e for e in logs if e["event"] == "slack_planning_intake_no_op"]
        assert len(noops) == 1  # its own logged no-op reason


# ---------------------------------------------------------------------------
# Scenario 14 — A pipeline outage produces an in-thread failure notice
# ---------------------------------------------------------------------------


class TestPipelineOutageFailureNotice:
    @pytest.mark.asyncio
    async def test_failure_notice_is_threaded_invites_repost_and_never_raises(self) -> None:
        publisher = MagicMock()
        publisher.publish = AsyncMock(side_effect=TimeoutError("pipeline unavailable"))
        client, _, wc = _make_client(intake_publisher=publisher)
        await _deliver(client, _message_envelope_payload())  # must not raise
        wc.chat_postMessage.assert_awaited_once()
        kwargs = wc.chat_postMessage.await_args.kwargs
        assert kwargs["thread_ts"] == _TS
        assert "repost" in kwargs["text"]


# ---------------------------------------------------------------------------
# Scenario 15 — A redelivered message event is queued exactly once
# ---------------------------------------------------------------------------


class TestRedeliveredEventOnce:
    @pytest.mark.asyncio
    async def test_two_deliveries_yield_two_acks_and_one_publish(self) -> None:
        # Listener-driven (JNB-105 scenario-2 precedent): both envelopes are
        # acked — Socket Mode redelivery hygiene — but only one planning
        # request reaches the pipeline.
        client, publisher, _ = _make_client()
        payload = _message_envelope_payload()
        ack1 = await _deliver(client, payload, envelope_id="env-a")
        with capture_logs() as logs:
            ack2 = await _deliver(client, payload, envelope_id="env-b")
        ack1.assert_awaited_once()
        ack2.assert_awaited_once()
        assert publisher.publish.await_count == 1
        assert [e for e in logs if e["event"] == "planning_intake_duplicate_dropped"]


# ---------------------------------------------------------------------------
# Scenario 16 — A failed acknowledgement post does not undo the queued request
# ---------------------------------------------------------------------------


class TestFailedAckDoesNotUndo:
    @pytest.mark.asyncio
    async def test_queue_stands_ack_failure_is_logged_and_jarvis_keeps_running(
        self,
    ) -> None:
        wc = AsyncMock()
        wc.chat_postMessage = AsyncMock(side_effect=RuntimeError("slack down"))
        client, publisher, _ = _make_client(web_client=wc)
        with capture_logs() as logs:
            await _deliver(client, _message_envelope_payload())  # must not raise
        publisher.publish.assert_awaited_once()
        assert [e for e in logs if e["event"] == "planning_intake_ack_failed"]


# ---------------------------------------------------------------------------
# Scenario 17 — Messages arriving after a Socket Mode reconnect
# ---------------------------------------------------------------------------


class TestReconnectExactlyOnce:
    @pytest.mark.asyncio
    async def test_registration_happens_once_and_a_post_reconnect_message_queues_once(
        self,
    ) -> None:
        # Reconnects are SDK-owned (auto_reconnect replaces the session, not
        # the listener list) — the hermetic invariant is registration-once
        # across start() calls plus dedup holding on the handler instance.
        client, publisher, wc = _make_client()
        fake_sdk_client = MagicMock()
        fake_sdk_client.socket_mode_request_listeners = []
        fake_sdk_client.connect = AsyncMock()
        with patch(
            "slack_sdk.socket_mode.aiohttp.SocketModeClient",
            return_value=fake_sdk_client,
        ):
            await client.start()
            await client.start()  # idempotent — never re-registers
        assert len(fake_sdk_client.socket_mode_request_listeners) == 1
        ack = await _deliver(client, _message_envelope_payload())
        ack.assert_awaited_once()
        assert publisher.publish.await_count == 1
        # 'exactly one acknowledgement should be posted in the thread' —
        # asserted literally (review SPL-REV-F1).
        assert wc.chat_postMessage.await_count == 1
        assert wc.chat_postMessage.await_args.kwargs["thread_ts"] == _TS


# ---------------------------------------------------------------------------
# Scenario 18 — Approval button clicks continue to work with intake active
# ---------------------------------------------------------------------------


class TestApprovalButtonsCoexist:
    @pytest.mark.asyncio
    async def test_click_publishes_the_decision_and_never_a_planning_request(
        self,
    ) -> None:
        # Both REAL handlers on the one shared client: a click routes to the
        # approval path exactly as before; no planning request is queued.
        approval_publisher = MagicMock()
        approval_publisher.publish = AsyncMock()
        settings = SimpleNamespace(slack_operator_user_id=_OPERATOR, slack_decided_by="rich")
        wc = AsyncMock()
        approval_handler = build_reply_handler(
            settings=settings, publisher=approval_publisher, web_client=wc
        )
        client, intake_publisher, _ = _make_client(approval_handler=approval_handler, web_client=wc)
        click = {
            "type": "block_actions",
            "user": {"id": _OPERATOR},
            "container": {"type": "message", "channel_id": "C123", "message_ts": "1720.1"},
            "message": {"blocks": []},
            "actions": [
                {
                    "action_id": "forge_approve",
                    "value": json.dumps(
                        {
                            "request_id": "apr-1",
                            "build_id": "b-1",
                            "correlation_id": "corr-1",
                            "approval_subject": "agents.approval.forge.b-1",
                        }
                    ),
                }
            ],
        }
        ack = await _deliver(client, click, req_type="interactive")
        ack.assert_awaited_once()
        approval_publisher.publish.assert_awaited_once()  # decision published as before
        intake_publisher.publish.assert_not_awaited()  # never a planning request
