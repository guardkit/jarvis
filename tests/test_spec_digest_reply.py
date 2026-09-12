"""The spec digest card's reply path — the tap, the note, and the sign-in answer.

Machine chain, stage 2 (2026-08-14). These tests pin what actually reaches the
wire when the owner answers a spec digest card:

* "Yes" publishes ONE ``approve``, carrying whatever the card was told about
  signing in as a per-item value;
* "No" publishes the SAME decision a typed "reject" publishes — the machine is
  told the run is off in the words it has always read, so nothing changed on
  the far side (2026-09-12);
* "Send a note" collects plain English in a modal and publishes it VERBATIM as
  a ``reject`` with a note — the literal the digest door reads as "rewrite the
  spec", never as "cancel the run" — and the card then keeps the note in its
  status line, whole, and says what happens next (2026-09-06);
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


def _sent_line(note: str) -> str:
    """The status line after a plain note, verbatim from the lane spec (rule 22)."""
    return (
        f'Your note was sent: "{note}". The machine is rewriting the spec from it '
        "and will post a fresh list in this thread. If it cannot honour the note "
        "it will say so here, and a new sentence starts a fresh run."
    )


# The reject-note line keeps its wording; pinned so a change is a deliberate one.
_REJECT_LINE = (
    "You said reject, so this run will be cancelled and nothing will be built. "
    "Send a fresh sentence whenever you are ready to start again."
)


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
# Saying no to the spec
# ---------------------------------------------------------------------------
class TestSayingNo:
    """The button that declines a spec.

    On 2026-09-12 a spec that had already been decided against held the
    planning queue for its full hour because the card offered no way to say
    no; the owner guessed at typing a note beginning "reject", which worked.
    The button is that same decision, not a new one: the same words on the
    wire, and the same sentence back.
    """

    @pytest.mark.asyncio
    async def test_one_reject_reaches_the_wire(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        assert publisher.publish.await_count == 1
        response = _published(publisher)
        assert response.request_id == _REQUEST_ID
        assert response.decision == "reject"
        assert response.decided_by == _OPERATOR
        assert publisher.publish.await_args.kwargs["subject"] == _SUBJECT + ".response"

    @pytest.mark.asyncio
    async def test_the_note_is_the_word_the_machine_reads_as_call_it_off(self) -> None:
        """The machine splits on a FIRST WORD of "reject"; the button sends it."""
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        notes = _published(publisher).notes
        assert notes is not None
        assert notes.split(None, 1)[0].lower() == "reject"

    @pytest.mark.asyncio
    async def test_the_button_and_the_typed_reject_send_the_same_decision(self) -> None:
        """THE POINT OF THE LANE: forge needs no change, because the payload is
        the one it already handles. Asserted on the payload itself — decision,
        note, routing and per-item answers — never on any log wording."""
        typed_handler, typed_publisher, _tw = _make_handler()
        await typed_handler.handle_view_submission(_note_submission("reject"))
        typed = _published(typed_publisher)

        button_handler, button_publisher, _bw = _make_handler()
        await button_handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        tapped = _published(button_publisher)

        assert tapped.model_dump() == typed.model_dump()
        assert (
            button_publisher.publish.await_args.kwargs == typed_publisher.publish.await_args.kwargs
        )

    @pytest.mark.asyncio
    async def test_the_card_says_the_same_sentence_either_way(self) -> None:
        """Nothing new to learn: the words after the button are the words after
        the typed reject."""
        typed_handler, _tp, typed_web = _make_handler()
        await typed_handler.handle_view_submission(_note_submission("reject"))
        typed_line = typed_web.chat_update.await_args.kwargs["text"]

        handler, _publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        assert web.chat_update.await_args.kwargs["text"] == typed_line
        assert typed_line == _REJECT_LINE

    @pytest.mark.asyncio
    async def test_the_buttons_are_replaced_by_that_one_line(self) -> None:
        handler, _publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        blocks = web.chat_update.await_args.kwargs["blocks"]
        assert not [b for b in blocks if b.get("type") == "actions"]
        assert blocks[-1] == {
            "type": "section",
            "text": {"type": "plain_text", "text": _REJECT_LINE, "emoji": False},
        }

    @pytest.mark.asyncio
    async def test_a_second_tap_publishes_nothing(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_saying_no_after_saying_yes_publishes_nothing(self) -> None:
        """First answer wins, whichever answer it was."""
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_APPROVE))
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        assert publisher.publish.await_count == 1
        assert _published(publisher).decision == "approve"

    @pytest.mark.asyncio
    async def test_a_stranger_cannot_say_no(self) -> None:
        handler, publisher, web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE, user_id="U_STRANGER"))
        publisher.publish.assert_not_awaited()
        web.chat_postEphemeral.assert_awaited()

    @pytest.mark.asyncio
    async def test_a_malformed_control_value_is_dropped(self) -> None:
        handler, publisher, _web = _make_handler()
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE, value="not json"))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_publish_failure_leaves_the_card_answerable(self) -> None:
        handler, publisher, _web = _make_handler()
        publisher.publish.side_effect = RuntimeError("broker down")
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        publisher.publish.side_effect = None
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE))
        assert publisher.publish.await_count == 2

    @pytest.mark.asyncio
    async def test_a_sign_in_answer_on_the_card_rides_along_as_it_does_when_typed(
        self,
    ) -> None:
        """Whatever the card was told is carried exactly as the typed route
        carries it — the two payloads stay identical with the question answered."""
        blocks = _card_blocks(sign_in=True)
        answered = ad.apply_sign_in_answer(blocks, item_id="sign-in", disposition="accepted")

        typed_handler, typed_publisher, typed_web = _make_handler()
        typed_web.conversations_history = AsyncMock(
            return_value={"messages": [{"blocks": answered}]}
        )
        await typed_handler.handle_view_submission(_note_submission("reject"))

        handler, publisher, web = _make_handler()
        web.conversations_history = AsyncMock(return_value={"messages": [{"blocks": answered}]})
        await handler.handle_block_actions(_click(ad.ACTION_DIGEST_DECLINE, blocks=answered))

        assert _published(publisher).model_dump() == _published(typed_publisher).model_dump()
        assert [(d.assumption_id, d.disposition) for d in _published(publisher).dispositions] == [
            ("sign-in", "accepted")
        ]


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
    async def test_the_card_keeps_the_note_and_says_what_happens_next(self) -> None:
        """2026-09-06: the card showed the rewrite promise and then nothing, and
        with the note gone from the card Rich read it as having had no way to
        send one. The status line now carries the note, whole and in quotes,
        and says where the fresh list will land and what to do if the machine
        cannot honour the note. The words are the lane spec's (rule 22)."""
        handler, _publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission("rename it"))
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _sent_line("rename it")

    @pytest.mark.asyncio
    async def test_the_status_line_is_the_card_with_its_buttons_swapped_for_that_line(
        self,
    ) -> None:
        """Nothing else on the card moves: every block but the buttons stays,
        in order and byte for byte, and the one new block is a plain-text
        section carrying the status line. No new buttons (rule 24)."""
        handler, _publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission("rename it"))
        blocks = web.chat_update.await_args.kwargs["blocks"]
        original = _card_blocks()
        assert [b for b in original if b.get("type") == "actions"], "the card had buttons"
        kept = [b for b in original if b.get("type") != "actions"]
        assert blocks[:-1] == kept
        assert blocks[-1] == {
            "type": "section",
            "text": {"type": "plain_text", "text": _sent_line("rename it"), "emoji": False},
        }
        assert not [b for b in blocks if b.get("type") == "actions"]
        assert "button" not in json.dumps(blocks)

    @pytest.mark.asyncio
    async def test_a_note_with_quotes_in_it_is_shown_whole_inside_the_quotes(self) -> None:
        note = 'call the field "domain", not "email_domain", and keep the "total" row'
        handler, publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission(note))
        assert _published(publisher).notes == note
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _sent_line(note)
        assert f'Your note was sent: "{note}". ' in text

    @pytest.mark.asyncio
    async def test_a_multi_line_note_is_shown_whole_with_its_line_breaks(self) -> None:
        note = "Two things:\n- the count must include inactive users\n- sort by domain"
        handler, publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission(note))
        assert _published(publisher).notes == note
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _sent_line(note)
        assert note in text
        block_text = web.chat_update.await_args.kwargs["blocks"][-1]["text"]["text"]
        assert block_text == text

    @pytest.mark.asyncio
    async def test_a_long_note_is_never_cut_short(self) -> None:
        note = " ".join(f"sentence {n} of the note" for n in range(1, 121))
        assert len(note) > 2000
        handler, publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission(note))
        assert _published(publisher).notes == note
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _sent_line(note)
        assert note in text
        assert "..." not in text and "\u2026" not in text

    @pytest.mark.asyncio
    async def test_the_note_is_shown_as_sent_after_the_modal_trimmed_it(self) -> None:
        """What the card quotes is what went out on the wire: the same trimmed words."""
        handler, publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission("  rename it \n"))
        assert _published(publisher).notes == "rename it"
        assert web.chat_update.await_args.kwargs["text"] == _sent_line("rename it")

    def test_the_reject_form_is_unchanged(self) -> None:
        """Rule 22's second half: the form a note is typed into keeps its words."""
        view = ad.build_note_modal(private_metadata="{}")
        assert view["title"]["text"] == "Send a note"
        assert view["submit"]["text"] == "Send"
        assert view["close"]["text"] == "Cancel"
        (field,) = view["blocks"]
        assert field["label"]["text"] == "What should be different?"
        assert field["hint"]["text"] == (
            "Say it however you would say it out loud. The machine "
            "rewrites the spec from this and comes back with a fresh list."
        )

    @pytest.mark.asyncio
    async def test_a_note_starting_with_reject_still_reaches_the_wire_verbatim(self) -> None:
        """The machine decides what a reject means; jarvis only carries the words."""
        note = "reject - I messed up the original sentence"
        handler, publisher, _web = _make_handler()
        await handler.handle_view_submission(_note_submission(note))
        assert publisher.publish.await_count == 1
        response = _published(publisher)
        assert response.decision == "reject"
        assert response.notes == note

    @pytest.mark.asyncio
    async def test_the_card_says_the_run_will_be_cancelled_on_a_reject_note(self) -> None:
        """A note starting with the word reject cancels the run, so the card
        must not promise a rewrite that will never come."""
        handler, _publisher, web = _make_handler()
        await handler.handle_view_submission(
            _note_submission("Reject: I typed the wrong sentence")
        )
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _REJECT_LINE
        assert "rewrite the spec" not in text
        assert "rewriting the spec" not in text
        assert "Your note was sent" not in text

    @pytest.mark.asyncio
    async def test_a_bare_reject_note_says_cancelled_too(self) -> None:
        handler, publisher, web = _make_handler()
        await handler.handle_view_submission(_note_submission("reject"))
        assert _published(publisher).notes == "reject"
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _REJECT_LINE

    @pytest.mark.asyncio
    async def test_a_note_merely_containing_reject_still_says_rewrite(self) -> None:
        """Only the FIRST word means cancel."""
        handler, _publisher, web = _make_handler()
        await handler.handle_view_submission(
            _note_submission("please reject unknown formats with a 400")
        )
        text = web.chat_update.await_args.kwargs["text"]
        assert text == _sent_line("please reject unknown formats with a 400")
        assert "cancelled" not in text

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
