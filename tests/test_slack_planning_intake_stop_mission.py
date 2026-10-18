"""Stopping a mission with one Slack line (missions design, section 11, 18 October 2026).

``stop mission m-3fa21c`` is forwarded as one queue command, verb
``stop-mission``, with the mission id lower-cased, on today's wire. Jarvis
checks the shape only and posts nothing of its own: the forge decides whether
the person may stop the mission and answers in the thread. ``stop mission``
with no id, or with an ``m-`` word that is not an id, gets one usage line back
and nothing is published. Other prose beginning ``stop mission`` stays a
sentence.

No live Slack and no broker: the web client is an ``AsyncMock`` and the
publisher seam is mocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.infrastructure.planning_intake_grammar import (
    STOP_MISSION_USAGE_REFUSAL,
    parse_queue_message,
)
from jarvis.infrastructure.slack_planning_intake import PlanningIntakeHandler

_RICH = "U0RICH"
_CHANNEL = "C0PLANNING"
_TS = "1760780000.000500"


def _message_event(text: str, *, user: str = _RICH) -> dict[str, Any]:
    return {
        "type": "event_callback",
        "event_id": "Ev00000901",
        "event": {"type": "message", "channel": _CHANNEL, "ts": _TS, "user": user, "text": text},
    }


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


class TestTheStopShape:
    @pytest.mark.parametrize(
        "text",
        ["stop mission m-3fa21c", "  Stop   Mission   M-3FA21C  ", "STOP MISSION m-3Fa21c"],
    )
    def test_a_stop_is_one_command_with_the_id_lower_cased(self, text: str) -> None:
        parsed = parse_queue_message(text)
        assert parsed.shape == "command"
        assert parsed.command == {"verb": "stop-mission", "mission_id": "m-3fa21c"}

    @pytest.mark.parametrize(
        "text",
        [
            "stop mission",
            "stop mission m-",
            "stop mission m-3fa21",
            "stop mission m-3fa21cc",
            "stop mission m-3fa21g",
        ],
    )
    def test_a_stop_without_a_usable_id_gets_the_usage_line(self, text: str) -> None:
        parsed = parse_queue_message(text)
        assert parsed.shape == "refusal"
        assert parsed.refusal_text == STOP_MISSION_USAGE_REFUSAL

    @pytest.mark.parametrize(
        "text",
        [
            "stop mission creep on the notes page",
            "stop mission m-3fa21c and start another",
            "please stop mission m-3fa21c",
        ],
    )
    def test_other_prose_stays_a_sentence(self, text: str) -> None:
        parsed = parse_queue_message(text)
        assert parsed.shape == "sentence"
        assert parsed.sentence == text


class TestTheHandlerForwardsAStop:
    @pytest.mark.asyncio
    async def test_it_is_forwarded_as_one_queue_command_and_jarvis_posts_nothing(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("stop mission m-3fa21c"))
        assert publisher.publish.await_count == 1
        payload = publisher.publish.await_args.kwargs["payload"]
        assert payload.queue_command == {"verb": "stop-mission", "mission_id": "m-3fa21c"}
        assert payload.model_dump(mode="json")["queue_command"]["verb"] == "stop-mission"
        assert payload.originating_user == _RICH
        assert payload.parent_request_id == _TS
        web_client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_stop_without_an_id_is_answered_and_nothing_is_published(self) -> None:
        handler, publisher, web_client = _make_handler()
        await handler.handle_message_event(_message_event("stop mission"))
        publisher.publish.assert_not_awaited()
        posted = web_client.chat_postMessage.await_args.kwargs
        assert posted["text"] == STOP_MISSION_USAGE_REFUSAL
        assert posted["thread_ts"] == _TS
