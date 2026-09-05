"""The queue commands Rich types in the planning channel (Lane B, stage one).

Binding spec 2026-09-05, contracts 1, 2, 3 and the jarvis half of contract 10.

Jarvis recognises the SHAPE of a command, forwards it on today's wire with
one extra field, and posts nothing of its own — the forge owns the queue and
answers in the thread. Everything the grammar does not match is a planning
sentence and behaves exactly as it did before this lane.

No live Slack and no broker anywhere: the web client is an ``AsyncMock`` and
the publisher seam is mocked. The only real third-party dependency exercised
is the installed ``nats_core`` package, so the payload assertions are a true
round trip through ``PlanningQueuedPayload`` (``extra="allow"``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure import planning_intake_grammar as grammar
from jarvis.infrastructure.planning_intake_grammar import (
    INVALID_TARGET_NAME_REPLY,
    USAGE_REFUSAL,
    is_allowed_target_name,
    parse_queue_message,
)
from jarvis.infrastructure.slack_planning_intake import PlanningIntakeHandler

_JAMES = "U0JAMES"
_CHANNEL = "C0PLANNING"
_TS = "1751795701.000200"


def _message_event(text: str, *, event_id: str = "Ev00000001") -> dict[str, Any]:
    return {
        "type": "event_callback",
        "event_id": event_id,
        "event": {
            "type": "message",
            "channel": _CHANNEL,
            "ts": _TS,
            "user": _JAMES,
            "text": text,
        },
    }


def _make_handler() -> tuple[PlanningIntakeHandler, MagicMock, AsyncMock]:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web_client = AsyncMock()
    handler = PlanningIntakeHandler(
        channel_id=_CHANNEL,
        originator_ids=frozenset({_JAMES}),
        publisher=publisher,
        web_client=web_client,
    )
    return handler, publisher, web_client


def _published_payload(publisher: MagicMock) -> Any:
    assert publisher.publish.await_count == 1
    return publisher.publish.await_args.kwargs["payload"]


# ---------------------------------------------------------------------------
# The grammar table, row by row (spec contract 3)
# ---------------------------------------------------------------------------


class TestTheGrammarTable:
    """Every row of the spec's table, and the shape it is forwarded as."""

    @pytest.mark.parametrize(
        ("message", "expected"),
        [
            ("queue", {"verb": "list"}),
            ("next: add PDF export", {"verb": "add_front", "sentence": "add PDF export"}),
            (
                "before #12: add PDF export",
                {"verb": "add_before", "id": 12, "sentence": "add PDF export"},
            ),
            ("#12 next", {"verb": "promote", "id": 12}),
            ("#12 after #14", {"verb": "link", "id": 12, "after": 14}),
            ("keep 9", {"verb": "keep", "id": 9}),
            ("drop 9", {"verb": "drop", "id": 9}),
            ("keep #9", {"verb": "keep", "id": 9}),
            ("drop #9", {"verb": "drop", "id": 9}),
        ],
    )
    def test_each_row_forwards_its_flat_command(
        self, message: str, expected: dict[str, Any]
    ) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "command"
        assert parsed.command == expected

    @pytest.mark.parametrize(
        "message",
        ["QUEUE", "Next: add PDF export", "BEFORE #12: add PDF export", "#12 NEXT", "Keep 9"],
    )
    def test_the_first_token_is_matched_case_insensitively(self, message: str) -> None:
        assert parse_queue_message(message).shape == "command"

    def test_an_invisible_trailing_space_is_still_a_command(self) -> None:
        # A trailing space typed into Slack must not silently become a
        # planning run (the JNB-107 lesson).
        assert parse_queue_message("queue  ").command == {"verb": "list"}

    def test_a_command_sentence_is_trimmed(self) -> None:
        assert parse_queue_message("next:   add PDF export  ").command == {
            "verb": "add_front",
            "sentence": "add PDF export",
        }

    @pytest.mark.parametrize(
        ("message", "kind", "sentence"),
        [
            ("fix: the login button is dead", "fix", "the login button is dead"),
            ("question: which repo holds the cards", "question", "which repo holds the cards"),
            ("FIX: the login button is dead", "fix", "the login button is dead"),
        ],
    )
    def test_a_kind_prefix_is_a_sentence_with_its_kind_set(
        self, message: str, kind: str, sentence: str
    ) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "sentence"
        assert parsed.kind == kind
        assert parsed.sentence == sentence

    def test_bare_next_is_refused_in_one_line(self) -> None:
        parsed = parse_queue_message("next")
        assert parsed.shape == "refusal"
        assert parsed.command is None
        assert parsed.refusal_text == 'Did you mean "next: <sentence>" or "#12 next"?'


# ---------------------------------------------------------------------------
# A command begun and not finished (coach ruling, 2026-09-05 evening)
# ---------------------------------------------------------------------------


class TestAHalfTypedCommandIsRefusedNotFiled:
    """``next:`` and ``before #12:`` with nothing after them.

    Before this fix each became an ordinary planning sentence, so a typo
    started a real build whose entire request text was ``next:``. Both now
    get the same one-line usage reply as bare ``next`` and publish nothing.
    """

    @pytest.mark.parametrize(
        "message",
        [
            "next:",
            "next: ",
            "next:   ",
            "next:\t",
            "NEXT:",
            "Next: ",
            "before #12:",
            "before #12: ",
            "before #12:   ",
            "BEFORE #12:",
            "before   #7:",
            "before #123456:",
        ],
    )
    def test_it_is_refused_with_the_usage_line_and_nothing_is_forwarded(self, message: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "refusal"
        assert parsed.command is None
        assert parsed.sentence == ""
        assert parsed.kind is None
        assert parsed.refusal_text == USAGE_REFUSAL

    def test_the_reply_is_the_same_line_bare_next_gets(self) -> None:
        bare = parse_queue_message("next").refusal_text
        assert parse_queue_message("next:").refusal_text == bare
        assert parse_queue_message("before #12:").refusal_text == bare
        assert bare == 'Did you mean "next: <sentence>" or "#12 next"?'


# ---------------------------------------------------------------------------
# The whole table at once: only the two half-typed rows changed
# ---------------------------------------------------------------------------

#: Every shape the grammar has an opinion about, with the outcome it must
#: produce. The two ``refusal`` rows carrying no sentence are the only rows
#: this fix changed; every other row is pinned here exactly as it behaved
#: before, so the fix cannot have moved anything else.
_WHOLE_TABLE: list[tuple[str, str, dict[str, Any] | None, str | None]] = [
    # verb rows — unchanged
    ("queue", "command", {"verb": "list"}, None),
    ("next: add PDF export", "command", {"verb": "add_front", "sentence": "add PDF export"}, None),
    (
        "before #12: add PDF export",
        "command",
        {"verb": "add_before", "id": 12, "sentence": "add PDF export"},
        None,
    ),
    ("#12 next", "command", {"verb": "promote", "id": 12}, None),
    ("#12 after #14", "command", {"verb": "link", "id": 12, "after": 14}, None),
    ("keep 9", "command", {"verb": "keep", "id": 9}, None),
    ("drop #9", "command", {"verb": "drop", "id": 9}, None),
    # kind prefixes — unchanged
    ("fix: the login button is dead", "sentence", None, "fix"),
    ("question: which repo holds the cards", "sentence", None, "question"),
    # the refusals: bare next as before, the two half-typed rows are the fix
    ("next", "refusal", None, None),
    ("next:", "refusal", None, None),
    ("before #12:", "refusal", None, None),
    # near misses that must stay ordinary prose — unchanged
    ("next up: the reporting dashboard", "sentence", None, None),
    ("next : add PDF export", "sentence", None, None),
    ("next:add PDF export", "sentence", None, None),
    ("nextly", "sentence", None, None),
    ("before 12:", "sentence", None, None),
    ("before #12", "sentence", None, None),
    ("before #12:x", "sentence", None, None),
    ("beforehand #12:", "sentence", None, None),
    ("question:", "sentence", None, None),
    ("queue the next feature please", "sentence", None, None),
    ("Add PDF export to the reporting dashboard", "sentence", None, None),
]


class TestTheWholeTableIsUnchangedApartFromTheFix:
    @pytest.mark.parametrize(("message", "shape", "command", "kind"), _WHOLE_TABLE)
    def test_each_row_lands_where_it_always_did(
        self, message: str, shape: str, command: dict[str, Any] | None, kind: str | None
    ) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == shape
        assert parsed.command == command
        assert parsed.kind == kind
        if shape == "refusal":
            assert parsed.refusal_text == USAGE_REFUSAL
        else:
            assert parsed.refusal_text is None

    def test_only_two_rows_are_refusals_beyond_bare_next(self) -> None:
        refused = [row[0] for row in _WHOLE_TABLE if row[1] == "refusal"]
        assert refused == ["next", "next:", "before #12:"]


# ---------------------------------------------------------------------------
# Everything else is a sentence (spec contract 3, "prose is untouched")
# ---------------------------------------------------------------------------


class TestAnythingElseIsASentence:
    """The table test: no ordinary post may be swallowed by the grammar."""

    @pytest.mark.parametrize(
        "message",
        [
            "Add PDF export to the reporting dashboard",
            "queue the next feature please",  # starts with the word, is prose
            "the queue",
            "queueing is hard",
            "next up: the reporting dashboard",  # not the "next:" shape
            "next : add PDF export",  # space before the colon
            "next:add PDF export",  # no space after the colon
            "before 12: add PDF export",  # no hash
            "before #12 add PDF export",  # no colon
            "#12next",
            "#12 nextish",
            "12 next",  # no hash
            "#twelve next",
            "#12 after 14",  # second hash missing
            "#12 after",
            "keep everything",
            "drop the whole idea",
            "keep 9 rows",
            "drop9",
            "fix the login button",  # no colon
            "fix:the login button",  # no space
            "question:",
            "nextly",
            "queue\nand a second line",
            "next: line one\nline two",  # a command is one line
            "",
            "   ",
        ],
    )
    def test_a_non_matching_message_stays_a_sentence(self, message: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "sentence"
        assert parsed.command is None
        assert parsed.kind is None
        # Byte-for-byte: the sentence path must not change what is forwarded.
        assert parsed.sentence == message


# ---------------------------------------------------------------------------
# The allowed characters in a typed repository name
# ---------------------------------------------------------------------------


class TestTheAllowedRepositoryNameCharacters:
    @pytest.mark.parametrize(
        "name", ["api_test", "study-tutor", "guardkit/study-tutor", "a.b_c-1", "X"]
    )
    def test_an_allowed_name_passes(self, name: str) -> None:
        assert is_allowed_target_name(name)

    @pytest.mark.parametrize(
        "name", ["api test", "guardkit/study/tutor", "repo!", "repo:name", "", "/name", "name/"]
    )
    def test_a_name_outside_the_set_is_refused(self, name: str) -> None:
        assert not is_allowed_target_name(name)

    def test_the_local_copy_matches_the_wire(self) -> None:
        """The set is the wire's set — pinned so the two cannot drift."""
        from nats_core.events._pipeline import PLANNING_TARGET_REPO_PATTERN

        assert grammar._ALLOWED_TARGET_NAME_RE.pattern == PLANNING_TARGET_REPO_PATTERN.pattern


# ---------------------------------------------------------------------------
# What the handler does with a command (spec contracts 1 and 2)
# ---------------------------------------------------------------------------


class TestTheHandlerForwardsACommand:
    @pytest.mark.asyncio
    async def test_the_command_travels_as_a_flat_field_on_the_payload(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event("#12 after #14"))
        payload = _published_payload(publisher)
        # A true round trip through the model: extra="allow" keeps the field.
        assert payload.queue_command == {"verb": "link", "id": 12, "after": 14}
        assert payload.model_dump(mode="json")["queue_command"] == {
            "verb": "link",
            "id": 12,
            "after": 14,
        }
        # Flat — no nested "args" object (spec contract 2).
        assert "args" not in payload.queue_command

    @pytest.mark.asyncio
    async def test_the_raw_message_travels_as_the_request_text(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event("next: add PDF export"))
        payload = _published_payload(publisher)
        assert payload.request_text == "next: add PDF export"
        assert payload.queue_command["sentence"] == "add PDF export"

    @pytest.mark.asyncio
    async def test_a_command_gets_its_own_correlation_id_and_thread(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event("queue"))
        payload = _published_payload(publisher)
        assert payload.correlation_id
        assert publisher.publish.await_args.kwargs["correlation_id"] == payload.correlation_id
        # The Slack ts registers the thread the forge's reply lands in.
        assert payload.parent_request_id == _TS
        assert payload.originating_user == _JAMES

    @pytest.mark.asyncio
    async def test_jarvis_posts_nothing_for_a_command(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("queue"))
        publisher.publish.assert_awaited_once()
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_target_line_applies_to_a_command_sentence(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("target: api_test\nnext: add PDF export"))
        payload = _published_payload(publisher)
        assert payload.target_repo == "api_test"
        assert payload.queue_command == {"verb": "add_front", "sentence": "add PDF export"}
        assert payload.request_text == "next: add PDF export"
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message", ["next:", "before #12:"])
    async def test_a_half_typed_command_is_answered_and_nothing_is_published(
        self, message: str
    ) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event(message))
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_count == 1
        posted = web_client.chat_postMessage.await_args.kwargs
        assert posted["text"] == USAGE_REFUSAL
        assert posted["thread_ts"] == _TS
        assert posted["channel"] == _CHANNEL

    @pytest.mark.asyncio
    async def test_a_half_typed_command_under_a_target_line_publishes_nothing(self) -> None:
        # The target line is parsed first, so the message left for the
        # grammar is the half-typed command on its own.
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("target: api_test\nnext:"))
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_args.kwargs["text"] == USAGE_REFUSAL

    @pytest.mark.asyncio
    async def test_bare_next_is_answered_and_nothing_is_published(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("next"))
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_count == 1
        posted = web_client.chat_postMessage.await_args.kwargs
        assert posted["text"] == USAGE_REFUSAL
        assert posted["thread_ts"] == _TS
        assert posted["channel"] == _CHANNEL


# ---------------------------------------------------------------------------
# The sentence path is unchanged (spec contract 1)
# ---------------------------------------------------------------------------


class TestTheSentencePathIsUnchanged:
    @pytest.mark.asyncio
    async def test_a_sentence_still_gets_its_acknowledgement(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("Add PDF export to the dashboard"))
        payload = _published_payload(publisher)
        assert payload.request_text == "Add PDF export to the dashboard"
        assert not hasattr(payload, "queue_command")
        assert web_client.chat_postMessage.await_args.kwargs["text"] == (
            f"Sent to the factory · `{payload.correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_a_kind_prefix_travels_as_an_extra_field(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("fix: the login button is dead"))
        payload = _published_payload(publisher)
        assert payload.kind == "fix"
        assert payload.request_text == "the login button is dead"
        assert not hasattr(payload, "queue_command")
        # A sentence, so the acknowledgement stays exactly as it was.
        assert web_client.chat_postMessage.await_args.kwargs["text"] == (
            f"Sent to the factory · `{payload.correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_an_ordinary_sentence_carries_no_kind(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event("Add PDF export"))
        assert not hasattr(_published_payload(publisher), "kind")


# ---------------------------------------------------------------------------
# The invalid repository name reply (spec contract 3, last rule)
# ---------------------------------------------------------------------------


class TestTheInvalidNameReply:
    @pytest.mark.asyncio
    async def test_a_name_outside_the_allowed_set_is_answered_not_dropped(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(
            _message_event("target: guardkit/study/tutor\nAdd PDF export")
        )
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_count == 1
        posted = web_client.chat_postMessage.await_args.kwargs
        assert posted["text"] == INVALID_TARGET_NAME_REPLY
        assert posted["thread_ts"] == _TS

    def test_the_reply_names_the_allowed_characters_in_one_sentence(self) -> None:
        assert INVALID_TARGET_NAME_REPLY.count(".") == 1  # one sentence
        for word in ("letters", "digits", "underscores", "hyphens", "slash"):
            assert word in INVALID_TARGET_NAME_REPLY

    @pytest.mark.asyncio
    async def test_the_refusal_is_logged_without_the_message_text(self) -> None:
        handler, _, _ = _make_handler()
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event("target: repo:name\nAdd PDF export"))
        refusals = [e for e in logs if e["event"] == "planning_intake_target_name_refused"]
        assert len(refusals) == 1
        assert "Add PDF export" not in repr(refusals[0])

    @pytest.mark.asyncio
    async def test_an_allowed_name_is_published_as_before(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event("target: api_test\nAdd PDF export"))
        assert _published_payload(publisher).target_repo == "api_test"
