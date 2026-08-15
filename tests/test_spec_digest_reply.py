"""The spec digest card's reply path — the tap, the note, and the sign-in answer.

Machine chain, stage 2 (2026-08-14). These tests pin what actually reaches the
wire when the owner answers a spec digest card:

* "Yes" publishes ONE ``approve``, carrying whatever the card was told about
  signing in as a per-item value;
* "Send a note" collects plain English in a modal and publishes it VERBATIM as
  a ``reject`` with a note — the literal the digest door reads as "rewrite the
  spec", never as "cancel the run";
* the note modal's submission is HANDLED. It used to be dropped with no log at
  all, which is how a typed note could vanish between a person and the machine;
* "Show the worked examples" opens a read-only view and publishes nothing.

Fully hermetic — AsyncMock web client, MagicMock publisher, no Slack, no NATS.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.infrastructure import assumption_dialogue as ad
from jarvis.infrastructure.slack_reply import build_reply_handler
from jarvis.infrastructure.spec_texts import SpecTextRegistry
from tests.test_spec_digest_card import make_digest_details

_OPERATOR = "U_RICH"
_SUBJECT = "agents.approval.forge.plan-cid123"
_CHANNEL = "C_PLANNING"
_TS = "1700000000.500000"
_REQUEST_ID = "req-1"


def _card_blocks(**kwargs: Any) -> list[dict[str, Any]]:
    return ad.build_dialogue_blocks(
        make_digest_details(**kwargs),
        correlation_id="cid123",
        request_id=_REQUEST_ID,
        approval_subject=_SUBJECT,
    )


def _value(assumption_id: str = ad.DIGEST_CARD_ID) -> str:
    return ad.build_item_value(
        correlation_id="cid123",
        request_id=_REQUEST_ID,
        assumption_id=assumption_id,
        cycle=None,
        approval_subject=_SUBJECT,
    )


def _click(
    action_id: str,
    *,
    user_id: str = _OPERATOR,
    value: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    trigger_id: str | None = "trigger-1",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "block_actions",
        "user": {"id": user_id},
        "channel": {"id": _CHANNEL},
        "container": {"type": "message", "channel_id": _CHANNEL, "message_ts": _TS},
        "message": {"blocks": blocks if blocks is not None else _card_blocks()},
        "actions": [{"action_id": action_id, "value": value or _value()}],
    }
    if trigger_id is not None:
        payload["trigger_id"] = trigger_id
    return payload


def _note_submission(
    note: str,
    *,
    user_id: str = _OPERATOR,
    callback_id: str = ad.NOTE_MODAL_CALLBACK_ID,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = (
        metadata
        if metadata is not None
        else {
            "correlation_id": "cid123",
            "request_id": _REQUEST_ID,
            "cycle": None,
            "approval_subject": _SUBJECT,
            "channel": _CHANNEL,
            "message_ts": _TS,
        }
    )
    return {
        "type": "view_submission",
        "user": {"id": user_id},
        "view": {
            "callback_id": callback_id,
            "private_metadata": json.dumps(meta, separators=(",", ":")),
            "state": {
                "values": {"spec_digest_note_input": {"spec_digest_note_value": {"value": note}}}
            },
        },
    }


def _make_handler(*, spec_texts: SpecTextRegistry | None = None):
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web = AsyncMock()
    handler = build_reply_handler(
        operator_ids=frozenset({_OPERATOR}),
        publisher=publisher,
        web_client=web,
        spec_texts=spec_texts,
    )
    # The authoritative re-fetch: unless a test says otherwise, Slack's copy of
    # the message is the card as posted.
    web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": _card_blocks()}]})
    return handler, publisher, web


def _published(publisher: MagicMock) -> Any:
    return publisher.publish.await_args.kwargs["payload"]


# ---------------------------------------------------------------------------
# Saying yes to the spec
# ---------------------------------------------------------------------------
class TestSayingYes:
    @pytest.mark.asyncio
    async def test_one_approve_reaches_the_wire(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        assert publisher.publish.await_count == 1
        response = _published(publisher)
        assert response.request_id == _REQUEST_ID
        assert response.decision == "approve"
        assert response.decided_by == _OPERATOR
        assert response.notes is None
        assert publisher.publish.await_args.kwargs["subject"] == _SUBJECT + ".response"

    @pytest.mark.asyncio
    async def test_a_second_tap_publishes_nothing(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_a_stranger_cannot_answer_the_card(self) -> None:
        handler, publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, user_id="U_STRANGER"))
        publisher.publish.assert_not_awaited()
        web.chat_postEphemeral.assert_awaited()

    @pytest.mark.asyncio
    async def test_the_card_says_what_happens_next(self) -> None:
        handler, _publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        text = web.chat_update.await_args.kwargs["text"]
        assert "nothing is built until you give the go-ahead" in text

    @pytest.mark.asyncio
    async def test_a_malformed_control_value_is_dropped(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, value="not json"))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_publish_failure_leaves_the_card_answerable(self) -> None:
        handler, publisher, _web = _make_handler()
        publisher.publish.side_effect = RuntimeError("broker down")
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        publisher.publish.side_effect = None
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        assert publisher.publish.await_count == 2


# ---------------------------------------------------------------------------
# The sign-in question — answered on the card, carried by the yes
# ---------------------------------------------------------------------------
class TestTheSignInAnswer:
    @staticmethod
    def _handler_with_sign_in():
        handler, publisher, web = _make_handler()
        blocks = _card_blocks(sign_in=True)
        web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": blocks}]})
        return handler, publisher, web, blocks

    @pytest.mark.asyncio
    async def test_answering_it_publishes_nothing(self) -> None:
        handler, publisher, web, blocks = self._handler_with_sign_in()
        await handler.handle_block_actions(
            _click(ad.ACTION_DIGEST_SIGN_IN_AGREE, value=_value("sign-in"), blocks=blocks)
        )
        publisher.publish.assert_not_awaited()
        web.chat_update.assert_awaited()

    @pytest.mark.asyncio
    async def test_agreeing_then_saying_yes_carries_accepted(self) -> None:
        handler, publisher, web, blocks = self._handler_with_sign_in()
        await handler.handle_block_actions(
            _click(ad.ACTION_DIGEST_SIGN_IN_AGREE, value=_value("sign-in"), blocks=blocks)
        )
        answered = web.chat_update.await_args.kwargs["blocks"]
        web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": answered}]})
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, blocks=answered))
        response = _published(publisher)
        assert response.decision == "approve"
        assert [(d.assumption_id, d.disposition) for d in response.dispositions] == [
            ("sign-in", "accepted")
        ]

    @pytest.mark.asyncio
    async def test_disagreeing_carries_rejected(self) -> None:
        handler, publisher, web, blocks = self._handler_with_sign_in()
        await handler.handle_block_actions(
            _click(ad.ACTION_DIGEST_SIGN_IN_DISAGREE, value=_value("sign-in"), blocks=blocks)
        )
        answered = web.chat_update.await_args.kwargs["blocks"]
        web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": answered}]})
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, blocks=answered))
        response = _published(publisher)
        assert [(d.assumption_id, d.disposition) for d in response.dispositions] == [
            ("sign-in", "rejected")
        ]

    @pytest.mark.asyncio
    async def test_an_unanswered_question_sends_no_item(self) -> None:
        """Saying yes to the spec with nothing said about signing in."""
        handler, publisher, _web, blocks = self._handler_with_sign_in()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, blocks=blocks))
        assert _published(publisher).dispositions is None

    @pytest.mark.asyncio
    async def test_answering_it_after_the_card_is_answered_is_dropped(self) -> None:
        handler, publisher, web, blocks = self._handler_with_sign_in()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, blocks=blocks))
        web.chat_update.reset_mock()
        await handler.handle_block_actions(
            _click(ad.ACTION_DIGEST_SIGN_IN_AGREE, value=_value("sign-in"), blocks=blocks)
        )
        web.chat_update.assert_not_awaited()
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_the_answer_is_read_from_the_authoritative_message(self) -> None:
        """Not from the click's own possibly-stale snapshot."""
        handler, publisher, web, blocks = self._handler_with_sign_in()
        answered = ad.apply_sign_in_answer(blocks, item_id="sign-in", disposition="rejected")
        web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": answered}]})
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE, blocks=blocks))
        assert _published(publisher).dispositions[0].disposition == "rejected"


# ---------------------------------------------------------------------------
# The note channel
# ---------------------------------------------------------------------------
class TestTheNoteChannel:
    @pytest.mark.asyncio
    async def test_the_control_opens_a_modal_and_publishes_nothing(self) -> None:
        handler, publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_NOTE))
        publisher.publish.assert_not_awaited()
        view = web.views_open.await_args.kwargs["view"]
        assert view["callback_id"] == ad.NOTE_MODAL_CALLBACK_ID

    @pytest.mark.asyncio
    async def test_the_modal_carries_the_routing_it_needs_to_answer_the_card(self) -> None:
        handler, _publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_NOTE))
        meta = json.loads(web.views_open.await_args.kwargs["view"]["private_metadata"])
        assert meta["request_id"] == _REQUEST_ID
        assert meta["approval_subject"] == _SUBJECT
        assert meta["channel"] == _CHANNEL
        assert meta["message_ts"] == _TS

    @pytest.mark.asyncio
    async def test_a_submitted_note_reaches_the_wire_verbatim(self) -> None:
        """The whole channel: his words, unsummarised, on the field that carries them."""
        note = "The version should come from the running image, not a file on disk."
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(_note_submission(note))
        assert publisher.publish.await_count == 1
        response = _published(publisher)
        assert response.notes == note
        assert response.decision == "reject"
        assert response.decided_by == _OPERATOR
        assert response.request_id == _REQUEST_ID

    @pytest.mark.asyncio
    async def test_the_submission_is_not_silently_dropped(self) -> None:
        """The defect this test exists for: a note modal used to hit an early return."""
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(_note_submission("please rename the endpoint"))
        publisher.publish.assert_awaited()

    @pytest.mark.asyncio
    async def test_the_card_says_the_note_is_with_the_machine(self) -> None:
        handler, _publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission("rename it"))
        text = web.chat_update.await_args.kwargs["text"]
        assert "rewrite the spec" in text

    @pytest.mark.asyncio
    async def test_a_stranger_cannot_send_a_note(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(_note_submission("hi", user_id="U_STRANGER"))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_an_empty_note_is_never_published(self) -> None:
        """Nothing to rewrite from; the modal's input is required, so this is a stale path."""
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(_note_submission("   "))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_incomplete_routing_is_dropped(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(
            _note_submission("rename it", metadata={"request_id": "", "approval_subject": ""})
        )
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_the_edit_modal_still_works(self) -> None:
        """The other submission on the same handler must be untouched."""
        handler, publisher, web = _make_handler()
        from tests.test_assumption_dialogue_render import make_details

        blocks = ad.build_dialogue_blocks(
            make_details(1),
            correlation_id="cid123",
            request_id=_REQUEST_ID,
            approval_subject=_SUBJECT,
        )
        web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": blocks}]})
        payload = {
            "type": "view_submission",
            "user": {"id": _OPERATOR},
            "view": {
                "callback_id": ad.EDIT_MODAL_CALLBACK_ID,
                "private_metadata": json.dumps(
                    {
                        "correlation_id": "cid123",
                        "request_id": _REQUEST_ID,
                        "assumption_id": "A1",
                        "cycle": 1,
                        "approval_subject": _SUBJECT,
                        "channel": _CHANNEL,
                        "message_ts": _TS,
                    }
                ),
                "state": {
                    "values": {"spl3_edit_input": {"spl3_edit_value": {"value": "new text"}}}
                },
            },
        }
        await handler.handle_view_submission(payload)
        assert publisher.publish.await_count == 1
        assert _published(publisher).dispositions[0].disposition == "modified"

    @pytest.mark.asyncio
    async def test_an_unknown_modal_publishes_nothing(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(_note_submission("x", callback_id="other_modal"))
        publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# One click deeper
# ---------------------------------------------------------------------------
class TestShowTheWorkedExamples:
    @pytest.mark.asyncio
    async def test_it_opens_the_read_only_view_and_publishes_nothing(self) -> None:
        store = SpecTextRegistry()
        store.record(request_id=_REQUEST_ID, feature="version-endpoint", spec_text="Feature: v")
        handler, publisher, web = _make_handler(spec_texts=store)
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_SHOW_SPEC))
        publisher.publish.assert_not_awaited()
        view = web.views_open.await_args.kwargs["view"]
        assert view["callback_id"] == ad.SPEC_MODAL_CALLBACK_ID
        assert "submit" not in view
        assert "Feature: v" in json.dumps(view)

    @pytest.mark.asyncio
    async def test_examples_no_longer_held_are_answered_honestly(self) -> None:
        """A restart empties the store; the button says so rather than opening empty."""
        handler, _publisher, web = _make_handler(spec_texts=SpecTextRegistry())
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_SHOW_SPEC))
        assert "no longer to hand" in json.dumps(web.views_open.await_args.kwargs["view"])

    @pytest.mark.asyncio
    async def test_an_unwired_store_answers_honestly_too(self) -> None:
        handler, _publisher, web = _make_handler(spec_texts=None)
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_SHOW_SPEC))
        assert "no longer to hand" in json.dumps(web.views_open.await_args.kwargs["view"])

    @pytest.mark.asyncio
    async def test_a_stranger_never_sees_the_spec(self) -> None:
        store = SpecTextRegistry()
        store.record(request_id=_REQUEST_ID, feature="f", spec_text="Feature: secret")
        handler, _publisher, web = _make_handler(spec_texts=store)
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_SHOW_SPEC, user_id="U_STRANGER"))
        web.views_open.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_missing_trigger_never_raises(self) -> None:
        handler, _publisher, web = _make_handler(spec_texts=SpecTextRegistry())
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_SHOW_SPEC, trigger_id=None))
        web.views_open.assert_not_awaited()


# ---------------------------------------------------------------------------
# The assumption dialogue is untouched
# ---------------------------------------------------------------------------
class TestTheAssumptionDialogueIsUntouched:
    @pytest.mark.asyncio
    async def test_a_binary_click_on_a_planning_subject_is_still_ignored(self) -> None:
        handler, publisher, _web = _make_handler()
        payload = _click("forge_approve")
        payload["actions"][0]["value"] = json.dumps(
            {
                "request_id": _REQUEST_ID,
                "build_id": "plan-cid123",
                "correlation_id": "cid123",
                "approval_subject": _SUBJECT,
            }
        )
        await handler.handle_block_actions(payload)
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_an_unknown_action_is_still_dropped(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click("something_nobody_registered"))
        publisher.publish.assert_not_awaited()
