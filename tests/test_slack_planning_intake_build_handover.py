"""Handing the factory a feature planned elsewhere: ``build: FEAT-XXXX from <branch>``.

Register-projects design (5 October 2026), part 3, and its Slack acceptance
checks. Jarvis recognises the shape and forwards it as one more queue command
on today's wire — verb ``build`` with the feature and branch, and the
``target:`` name exactly as typed — and posts nothing of its own: the forge
resolves the repository and answers in the thread. A ``build:`` with a part
missing gets one usage line and publishes nothing. Everything else, including
prose that begins with "build", stays a sentence exactly as before.

No live Slack and no broker: the web client is an ``AsyncMock`` and the
publisher seam is mocked. The payload assertions are a true round trip
through the installed ``nats_core`` ``PlanningQueuedPayload``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.infrastructure import planning_intake_grammar as grammar
from jarvis.infrastructure.planning_intake_grammar import (
    BUILD_USAGE_REFUSAL,
    USAGE_REFUSAL,
    is_allowed_branch_name,
    parse_queue_message,
)
from jarvis.infrastructure.slack_planning_intake import PlanningIntakeHandler

_RICH = "U0RICH"
_CHANNEL = "C0PLANNING"
_TS = "1759660000.000300"


def _message_event(
    text: str, *, event_id: str = "Ev00000101", user: str = _RICH, **event: Any
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


_BUILD = {"verb": "build", "feature_id": "FEAT-1A2B", "branch": "prepared/FEAT-1A2B"}


# ---------------------------------------------------------------------------
# The shape
# ---------------------------------------------------------------------------


class TestTheBuildShape:
    def test_the_design_example_is_one_build_command(self) -> None:
        parsed = parse_queue_message("build: FEAT-1A2B from prepared/FEAT-1A2B")
        assert parsed.shape == "command"
        assert parsed.command == _BUILD
        assert parsed.refusal_text is None

    @pytest.mark.parametrize(
        "message",
        [
            "BUILD: FEAT-1A2B FROM prepared/FEAT-1A2B",
            "Build: feat-1a2b from prepared/FEAT-1A2B",
            "build:\tFEAT-1A2B\tfrom\tprepared/FEAT-1A2B",
            "build:   FEAT-1A2B   from   prepared/FEAT-1A2B  ",
        ],
    )
    def test_it_is_matched_case_insensitively_and_ignores_outer_space(self, message: str) -> None:
        # The feature id goes on the wire in the one form the wire accepts;
        # the branch is passed exactly as typed (git branch names are
        # case-sensitive).
        assert parse_queue_message(message).command == _BUILD

    @pytest.mark.parametrize(
        "branch",
        ["main", "prepared/FEAT-1A2B", "feature/users_v2", "release-1.2", "a/b/c"],
    )
    def test_any_branch_git_allows_is_carried_as_typed(self, branch: str) -> None:
        parsed = parse_queue_message(f"build: FEAT-ABC from {branch}")
        assert parsed.command == {"verb": "build", "feature_id": "FEAT-ABC", "branch": branch}

    def test_the_feature_id_rule_is_the_wires(self) -> None:
        """The local copy is pinned to nats-core so the two cannot drift."""
        from nats_core.events._pipeline import FEATURE_ID_PATTERN

        assert grammar._FEATURE_ID_RE.pattern == FEATURE_ID_PATTERN.pattern


class TestAHalfTypedBuildGetsTheUsageLine:
    @pytest.mark.parametrize(
        "message",
        [
            "build:",
            "build: ",
            "BUILD:",
            "build: FEAT-1A2B",
            "build: FEAT-1A2B from",
            "build: FEAT-1A2B from ",
            "build: from prepared/FEAT-1A2B",
            "build: from",
            # a feature id the wire cannot carry
            "build: FEAT-12 from main",
            "build: FEAT-1A2B3C4D5E6F7 from main",
            "build: FEAT-1A-2B from main",
            # a branch git would refuse
            "build: FEAT-1A2B from -main",
            "build: FEAT-1A2B from a..b",
            "build: FEAT-1A2B from main.lock",
            "build: FEAT-1A2B from bad:branch",
            "build: FEAT-1A2B from main/",
            # more than one branch word, or a command over two lines
            "build: FEAT-1A2B from main and then deploy",
            "build: FEAT-1A2B\nfrom main",
            # no space after the colon
            "build:FEAT-1A2B from main",
        ],
    )
    def test_it_is_refused_with_one_line_and_nothing_is_forwarded(self, message: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "refusal"
        assert parsed.command is None
        assert parsed.sentence == ""
        assert parsed.refusal_text == BUILD_USAGE_REFUSAL

    def test_the_usage_line_names_the_shape(self) -> None:
        assert BUILD_USAGE_REFUSAL == 'Did you mean "build: FEAT-XXXX from <branch>"?'

    def test_the_next_usage_line_is_unchanged(self) -> None:
        assert parse_queue_message("next:").refusal_text == USAGE_REFUSAL


class TestProseThatBeginsWithBuildIsASentence:
    @pytest.mark.parametrize(
        "message",
        [
            "build a users page",
            "build the reporting dashboard from the old one",
            "Build: a users page with paging",
            "build: the login form, please",
            "building: FEAT-1A2B from main",
            "rebuild: FEAT-1A2B from main",
            "build FEAT-1A2B from main",  # no colon
            "please build: FEAT-1A2B from main",
        ],
    )
    def test_it_stays_a_sentence_byte_for_byte(self, message: str) -> None:
        parsed = parse_queue_message(message)
        assert parsed.shape == "sentence"
        assert parsed.command is None
        assert parsed.sentence == message


class TestTheBranchRule:
    @pytest.mark.parametrize(
        "name", ["main", "prepared/FEAT-1A2B", "a.b", "v1.2.3", "x@y", "feature/a-b_c"]
    )
    def test_names_git_allows(self, name: str) -> None:
        assert is_allowed_branch_name(name)

    @pytest.mark.parametrize(
        "name",
        [
            "",
            "@",
            "-x",
            "/x",
            "x/",
            "x.",
            "a..b",
            "a@{b",
            "a//b",
            ".hidden",
            "a/.hidden",
            "x.lock",
            "a/x.lock/b",
            "a b",
            "a~b",
            "a^b",
            "a:b",
            "a?b",
            "a*b",
            "a[b",
            "a\\b",
            "a\x7fb",
        ],
    )
    def test_names_git_refuses(self, name: str) -> None:
        assert not is_allowed_branch_name(name)


# ---------------------------------------------------------------------------
# What the handler does with it
# ---------------------------------------------------------------------------


class TestTheHandlerForwardsAHandOver:
    @pytest.mark.asyncio
    async def test_it_is_forwarded_as_one_queue_command_and_jarvis_posts_nothing(
        self,
    ) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(
            _message_event("build: FEAT-1A2B from prepared/FEAT-1A2B")
        )
        payload = _published_payload(publisher)
        assert payload.queue_command == _BUILD
        assert payload.model_dump(mode="json")["queue_command"] == _BUILD
        assert payload.request_text == "build: FEAT-1A2B from prepared/FEAT-1A2B"
        # No target line: the forge applies its default.
        assert payload.target_repo is None
        assert payload.triggered_by == "jarvis"
        assert payload.originating_adapter == "slack"
        assert payload.originating_user == _RICH
        # The Slack message is the thread the forge answers in.
        assert payload.parent_request_id == _TS
        assert publisher.publish.await_args.kwargs["subject"] == (
            f"pipeline.planning-queued.{payload.correlation_id}"
        )
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", ["api_test", "guardkit/api_test", "nowhere"])
    async def test_the_target_travels_exactly_as_typed(self, target: str) -> None:
        # Jarvis resolves nothing — a short name, a canonical name, and a name
        # the factory has never heard of all travel unchanged.
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(
            _message_event(f"target: {target}\nbuild: FEAT-1A2B from prepared/FEAT-1A2B")
        )
        payload = _published_payload(publisher)
        assert payload.target_repo == target
        assert payload.queue_command == _BUILD
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message", ["build:", "build: FEAT-1A2B", "build: FEAT-1A2B from"])
    async def test_a_half_typed_build_is_answered_and_nothing_is_published(
        self, message: str
    ) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event(message))
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_count == 1
        posted = web_client.chat_postMessage.await_args.kwargs
        assert posted["text"] == BUILD_USAGE_REFUSAL
        assert posted["thread_ts"] == _TS
        assert posted["channel"] == _CHANNEL

    @pytest.mark.asyncio
    async def test_a_half_typed_build_under_a_target_line_publishes_nothing(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("target: api_test\nbuild: FEAT-1A2B"))
        publisher.publish.assert_not_awaited()
        assert web_client.chat_postMessage.await_args.kwargs["text"] == BUILD_USAGE_REFUSAL

    @pytest.mark.asyncio
    async def test_prose_beginning_with_build_is_a_sentence_with_its_acknowledgement(
        self,
    ) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("build a users page"))
        payload = _published_payload(publisher)
        assert payload.request_text == "build a users page"
        assert not hasattr(payload, "queue_command")
        assert web_client.chat_postMessage.await_args.kwargs["text"] == (
            f"Sent to the factory · `{payload.correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_a_duplicate_delivery_is_dropped(self) -> None:
        handler, publisher, web_client = _make_handler()
        event = _message_event("build: FEAT-1A2B from prepared/FEAT-1A2B")
        await handler.handle_message_event(event)
        await handler.handle_message_event(event)
        publisher.publish.assert_awaited_once()
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_someone_else_cannot_hand_over_a_build(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(
            _message_event("build: FEAT-1A2B from prepared/FEAT-1A2B", user="U0SOMEONE")
        )
        publisher.publish.assert_not_awaited()
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_reply_in_a_thread_is_not_a_hand_over(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(
            _message_event(
                "build: FEAT-1A2B from prepared/FEAT-1A2B", thread_ts="1759650000.000100"
            )
        )
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_another_channel_is_ignored(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(
            _message_event("build: FEAT-1A2B from prepared/FEAT-1A2B", channel="C0OTHER")
        )
        publisher.publish.assert_not_awaited()
