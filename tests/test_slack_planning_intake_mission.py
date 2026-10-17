"""Starting a mission with one Slack message (missions design, 17 October 2026, section 1).

A message whose first line, after any ``target:`` line, is ``mission: <title>``
and whose every following non-blank line is one feature —
``<key>[ (needs <key>[, <key>…])][ [no sign-in]]: <sentence>`` — is forwarded as
one queue command, verb ``mission``, on today's wire. Jarvis checks the shape
only and posts nothing of its own; the forge checks the meaning and answers in
the thread. A mission with a line jarvis cannot read gets one usage line back
and nothing is published. A sentence that merely mentions a mission stays a
sentence.

No live Slack and no broker: the web client is an ``AsyncMock`` and the
publisher seam is mocked. The payload assertions are a true round trip through
the installed ``nats_core`` ``PlanningQueuedPayload``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.infrastructure.planning_intake_grammar import (
    BUILD_USAGE_REFUSAL,
    MISSION_USAGE_REFUSAL,
    parse_queue_message,
)
from jarvis.infrastructure.slack_planning_intake import PlanningIntakeHandler

_RICH = "U0RICH"
_CHANNEL = "C0PLANNING"
_TS = "1760700000.000400"

# The design's own example, byte for byte (section 1).
_DESIGN_MESSAGE = (
    "target: react-go-notes-fixture\n"
    "mission: Tags for notes\n"
    "A: Store tags on notes in the database and return them from the notes API\n"
    "B (needs A): Let the user add and remove tags on a note in the web app\n"
    "C (needs A): Filter the notes list by tag\n"
    "D (needs B, C) [no sign-in]: Show a tag cloud on the notes page"
)
_DESIGN_MISSION_TEXT = _DESIGN_MESSAGE.partition("\n")[2]

_DESIGN_COMMAND = {
    "verb": "mission",
    "title": "Tags for notes",
    "features": [
        {
            "key": "A",
            "needs": [],
            "no_sign_in": False,
            "sentence": "Store tags on notes in the database and return them from the notes API",
        },
        {
            "key": "B",
            "needs": ["A"],
            "no_sign_in": False,
            "sentence": "Let the user add and remove tags on a note in the web app",
        },
        {
            "key": "C",
            "needs": ["A"],
            "no_sign_in": False,
            "sentence": "Filter the notes list by tag",
        },
        {
            "key": "D",
            "needs": ["B", "C"],
            "no_sign_in": True,
            "sentence": "Show a tag cloud on the notes page",
        },
    ],
}


def _message_event(
    text: str, *, event_id: str = "Ev00000201", user: str = _RICH, **event: Any
) -> dict[str, Any]:
    body = {
        "type": "message",
        "channel": _CHANNEL,
        "ts": _TS,
        "user": user,
        "text": text,
    }
    body.update(event)
    return {"type": "event_callback", "event_id": event_id, "event": body}


def _make_handler() -> tuple[PlanningIntakeHandler, MagicMock, AsyncMock]:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web_client = AsyncMock()
    handler = PlanningIntakeHandler(
        channel_id=_CHANNEL,
        originator_ids=frozenset({_RICH}),
        publisher=publisher,
        web_client=web_client,
    )
    return handler, publisher, web_client


def _published_payload(publisher: MagicMock) -> Any:
    assert publisher.publish.await_count == 1
    return publisher.publish.await_args.kwargs["payload"]


# ---------------------------------------------------------------------------
# The shape
# ---------------------------------------------------------------------------


class TestTheMissionShape:
    def test_the_design_example_is_one_mission_command(self) -> None:
        parsed = parse_queue_message(_DESIGN_MISSION_TEXT)
        assert parsed.shape == "command"
        assert parsed.command == _DESIGN_COMMAND
        assert parsed.refusal_text is None

    def test_keys_are_upper_cased_and_spacing_is_forgiven(self) -> None:
        parsed = parse_queue_message(
            "  Mission:   Tags for notes  \n"
            "\n"
            "  foundation1 :  Store tags  \n"
            "\n"
            "b2(NEEDS foundation1 ,FOUNDATION1)[No Sign-In]:Add tags: in the web app\n"
        )
        assert parsed.command == {
            "verb": "mission",
            "title": "Tags for notes",
            "features": [
                {"key": "FOUNDATION1", "needs": [], "no_sign_in": False, "sentence": "Store tags"},
                {
                    "key": "B2",
                    # Repeats and unknown keys are the forge's to refuse.
                    "needs": ["FOUNDATION1", "FOUNDATION1"],
                    "no_sign_in": True,
                    "sentence": "Add tags: in the web app",
                },
            ],
        }

    def test_a_twelve_character_key_is_allowed(self) -> None:
        parsed = parse_queue_message("mission: M\nABCDEFGHIJ12: one feature")
        assert parsed.command["features"][0]["key"] == "ABCDEFGHIJ12"

    def test_a_key_that_only_contains_target_is_allowed(self) -> None:
        parsed = parse_queue_message("mission: M\nTARGETS: one\nT: two")
        assert [f["key"] for f in parsed.command["features"]] == ["TARGETS", "T"]

    def test_non_ascii_letters_in_a_sentence_are_kept(self) -> None:
        parsed = parse_queue_message("mission: Café tags\nA: Show the \u212a and \u017f signs")
        assert parsed.command["title"] == "Café tags"
        assert parsed.command["features"][0]["sentence"] == "Show the \u212a and \u017f signs"

    def test_the_meaning_is_left_to_the_forge(self) -> None:
        # An unknown key, a cycle and a repeated key are all well-formed
        # lines; jarvis forwards them and the forge answers.
        parsed = parse_queue_message("mission: M\nA (needs B): one\nB (needs A): two\nA: three")
        assert parsed.shape == "command"
        assert [f["key"] for f in parsed.command["features"]] == ["A", "B", "A"]


class TestAMalformedMissionGetsTheUsageLine:
    @pytest.mark.parametrize(
        "message",
        [
            # no title, or no features
            "mission:",
            "mission:   ",
            "mission: Tags for notes",
            "mission: Tags for notes\n\n   \n",
            "mission:\nA: Store tags",
            # a bad key
            "mission: M\nA-1: Store tags",
            "mission: M\nFEAT-1A2B: Store tags",
            "mission: M\nABCDEFGHIJKLM: thirteen characters",
            "mission: M\nfirst feature: two words",
            "mission: M\nÄ: not ascii",
            "mission: M\n: no key",
            # look-alike letters that case-folding would let through
            "mission: M\n\u212aEY: Kelvin sign",
            "mission: M\n\u017fTORE: long s",
            "mission: M\nL\u0131ST: dotless i",
            "mission: M\nB (needs \u212a): Kelvin sign in needs",
            # a target line typed under the mission line
            "mission: M\ntarget: react-go-notes-fixture\nA: Store tags",
            "mission: M\nA: Store tags\nTARGET: react-go-notes-fixture",
            # a sentence that is only a non-ASCII space
            "mission: M\nA:\u00a0\nB: y",
            # a missing colon or sentence
            "mission: M\nA Store tags",
            "mission: M\nA:",
            "mission: M\nA:    ",
            "mission: M\nB (needs A) Add tags",
            # needs written wrongly
            "mission: M\nB (needs): Add tags",
            "mission: M\nB (needs A,): Add tags",
            "mission: M\nB (needs A B): Add tags",
            "mission: M\nB (needs A-1): Add tags",
            "mission: M\nB (need A): Add tags",
            "mission: M\nB (needs A: Add tags",
            "mission: M\nB needs A: Add tags",
            # [no sign-in] written wrongly or in the wrong place
            "mission: M\nB [no sign-in] (needs A): Add tags",
            "mission: M\nB [no signin]: Add tags",
            # one good line does not excuse a bad one
            "mission: M\nA: Store tags\nB (needs A) Add tags",
            "mission: M\nA: Store tags\nthen show them on the page",
        ],
    )
    def test_it_is_refused_with_one_line_and_nothing_is_forwarded(self, message: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "refusal"
        assert parsed.command is None
        assert parsed.sentence == ""
        assert parsed.refusal_text == MISSION_USAGE_REFUSAL

    def test_the_usage_line_names_the_shape(self) -> None:
        assert MISSION_USAGE_REFUSAL == (
            'Did you mean "mission: <title>" and then one line per feature, '
            'such as "B (needs A) [no sign-in]: <sentence>"?'
        )


class TestOtherMessagesAreNotMissions:
    @pytest.mark.parametrize(
        "message",
        [
            "our mission is to make notes faster",
            "Our mission: make notes faster",
            "missions: let the user group notes",
            "mission statement page for the website",
            "mission control: show the build list",
            "the mission: A: tags",
            # the mission line not at the top
            "Add tags to notes\nmission: Tags for notes\nA: Store tags",
            "fix: the mission page crashes",
            # look-alike letters do not make the first line a mission
            "mi\u017f\u017fion: Tags for notes\nA: Store tags",
            "m\u0131ssion: Tags for notes\nA: Store tags",
        ],
    )
    def test_a_sentence_mentioning_a_mission_stays_a_sentence(self, message: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "sentence"
        assert parsed.command is None
        assert parsed.refusal_text is None

    def test_the_mission_word_inside_a_sentence_is_kept_byte_for_byte(self) -> None:
        message = "our mission is to make notes faster"
        assert parse_queue_message(message).sentence == message

    @pytest.mark.parametrize(
        ("message", "verb"),
        [
            ("next: mission: Tags for notes", "add_front"),
            ("before #3: mission: Tags", "add_before"),
            ("queue", "list"),
            ("build: FEAT-1A2B from mission/m-3fa21c", "build"),
        ],
    )
    def test_other_commands_are_unchanged(self, message: str, verb: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "command"
        assert parsed.command["verb"] == verb

    def test_a_half_typed_build_is_still_the_build_usage_line(self) -> None:
        assert parse_queue_message("build: FEAT-1A2B").refusal_text == BUILD_USAGE_REFUSAL


# ---------------------------------------------------------------------------
# What the handler does with it
# ---------------------------------------------------------------------------


class TestTheHandlerForwardsAMission:
    @pytest.mark.asyncio
    async def test_it_is_forwarded_as_one_queue_command_and_jarvis_posts_nothing(
        self,
    ) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event(_DESIGN_MESSAGE))
        payload = _published_payload(publisher)
        assert payload.queue_command == _DESIGN_COMMAND
        assert payload.model_dump(mode="json")["queue_command"] == _DESIGN_COMMAND
        assert payload.target_repo == "react-go-notes-fixture"
        # The message as typed, after the target line (as for every command).
        assert payload.request_text == _DESIGN_MISSION_TEXT
        assert payload.triggered_by == "jarvis"
        assert payload.originating_adapter == "slack"
        assert payload.originating_user == _RICH
        assert payload.parent_request_id == _TS
        assert publisher.publish.await_args.kwargs["subject"] == (
            f"pipeline.planning-queued.{payload.correlation_id}"
        )
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_without_a_target_line_the_forge_applies_its_default(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(_DESIGN_MISSION_TEXT))
        payload = _published_payload(publisher)
        assert payload.target_repo is None
        assert payload.queue_command == _DESIGN_COMMAND

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "message",
        [
            "target: react-go-notes-fixture\nmission: Tags for notes",
            "target: react-go-notes-fixture\nmission: Tags\nA-1: Store tags",
            "mission: Tags\nB (needs A,): Add tags",
            "mission: Tags\nA Store tags",
            "mission:\nA: Store tags",
        ],
    )
    async def test_a_malformed_mission_is_answered_and_nothing_is_published(
        self, message: str
    ) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event(message))
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_count == 1
        posted = web_client.chat_postMessage.await_args.kwargs
        assert posted["text"] == MISSION_USAGE_REFUSAL
        assert posted["thread_ts"] == _TS
        assert posted["channel"] == _CHANNEL

    @pytest.mark.asyncio
    async def test_a_sentence_mentioning_a_mission_gets_its_acknowledgement(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(
            _message_event("target: api_test\nour mission is to make notes faster")
        )
        payload = _published_payload(publisher)
        assert payload.request_text == "our mission is to make notes faster"
        assert not hasattr(payload, "queue_command")
        assert web_client.chat_postMessage.await_args.kwargs["text"] == (
            f"Sent to the factory · `{payload.correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_someone_else_cannot_start_a_mission(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event(_DESIGN_MESSAGE, user="U0SOMEONE"))
        publisher.publish.assert_not_awaited()
        web_client.chat_postMessage.assert_not_awaited()
