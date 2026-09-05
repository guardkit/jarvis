"""Tests for TASK-SPL-J01 — Slack planning intake handler + settings.

Plain pytest only — NO pytest-bdd ``.feature`` glue (operator decision
2026-07-03). Unit coverage for every gate arm, the dedup race posture, the
ASSUM-008 field mapping, and the publish-failure / ack-failure branches
(TASK-SPL-J01 acceptance criteria; TASK-REV-3240 findings F3-F6, F10-F12).

"Verbatim" throughout means verbatim-modulo-the-contract's-outer-whitespace-
strip (F10): ``PlanningQueuedPayload`` strips ``request_text`` on validation,
so assertions compare against the stripped text.

No live Slack or NATS anywhere: the web client and the JetStream context are
AsyncMock; the publisher seam is mocked for behavior tests. The only real
third-party dependency exercised is the installed ``nats_core`` package
(payload construction inside the handler; envelope wrapping in the publisher
tests).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr
from structlog.testing import capture_logs

from jarvis.infrastructure import slack_planning_intake as spi
from jarvis.infrastructure.slack_planning_intake import (
    NatsPlanningQueuedPublisher,
    PlanningIntakeHandler,
    create_slack_planning_intake_handler,
    parse_originator_ids,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_JAMES = "U0JAMES"
_CHANNEL = "C0PLANNING"
_TS = "1751795701.000200"


def _message_event(
    *,
    user: str | None = _JAMES,
    text: str | None = "Add PDF export to the reporting dashboard",
    channel: str = _CHANNEL,
    ts: str = _TS,
    event_id: str | None = "Ev00000001",
    event_type: str = "message",
    **event_extra: Any,
) -> dict[str, Any]:
    event: dict[str, Any] = {"type": event_type, "channel": channel, "ts": ts}
    if user is not None:
        event["user"] = user
    if text is not None:
        event["text"] = text
    event.update(event_extra)
    payload: dict[str, Any] = {"type": "event_callback", "event": event}
    if event_id is not None:
        payload["event_id"] = event_id
    return payload


def _make_handler(
    *,
    channel: str = _CHANNEL,
    originators: frozenset[str] = frozenset({_JAMES}),
    web_client: Any | None = "default",
) -> tuple[PlanningIntakeHandler, MagicMock, Any]:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    wc = AsyncMock() if web_client == "default" else web_client
    handler = PlanningIntakeHandler(
        channel_id=channel,
        originator_ids=originators,
        publisher=publisher,
        web_client=wc,
    )
    return handler, publisher, wc


def _published_payload(publisher: MagicMock) -> Any:
    assert publisher.publish.await_count == 1
    return publisher.publish.await_args.kwargs["payload"]


# ---------------------------------------------------------------------------
# parse_originator_ids
# ---------------------------------------------------------------------------


class TestParseOriginatorIds:
    def test_parse_with_none_returns_empty(self) -> None:
        assert parse_originator_ids(None) == frozenset()

    def test_parse_with_blank_returns_empty(self) -> None:
        assert parse_originator_ids("  ") == frozenset()

    def test_parse_single_id_strips_whitespace(self) -> None:
        # The JNB-107 lesson: a trailing space must not refuse every post.
        assert parse_originator_ids(" U0JAMES ") == frozenset({"U0JAMES"})

    def test_parse_comma_separated_allow_list(self) -> None:
        assert parse_originator_ids("U0JAMES, U0RICH,") == frozenset({"U0JAMES", "U0RICH"})


# ---------------------------------------------------------------------------
# _requested_at_from_ts
# ---------------------------------------------------------------------------


class TestRequestedAtFromTs:
    def test_valid_epoch_string_converts_to_utc(self) -> None:
        parsed = spi._requested_at_from_ts(_TS)
        assert parsed.timestamp() == pytest.approx(1751795701.0002)
        assert parsed.tzinfo is not None

    @pytest.mark.parametrize("bad_ts", [None, "", "not-a-number", "1e999"])
    def test_malformed_ts_falls_back_to_now(self, bad_ts: str | None) -> None:
        parsed = spi._requested_at_from_ts(bad_ts)
        assert parsed.tzinfo is not None  # UTC-now fallback, never raises


# ---------------------------------------------------------------------------
# Gate arms (F3 order)
# ---------------------------------------------------------------------------


class TestGateArms:
    @pytest.mark.asyncio
    async def test_non_message_event_type_is_ignored(self) -> None:
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(_message_event(event_type="reaction_added"))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_message_in_another_channel_is_ignored_with_no_reply(self) -> None:
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(_message_event(channel="C0OTHER"))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_realistic_self_ack_is_dropped_without_a_refusal_record(self) -> None:
        # F3: modern bot posts are SUBTYPE-FREE — bot_id set, user = the
        # bot's own user id, thread_ts present (the ack is threaded). The
        # fixture must not lean on subtype="bot_message".
        handler, publisher, wc = _make_handler()
        self_ack = _message_event(
            user="U0JARVISBOT",
            text="Queued for planning · `corr-1`",
            bot_id="B0JARVIS",
            app_id="A0JARVIS",
            thread_ts=_TS,
        )
        with capture_logs() as logs:
            await handler.handle_message_event(self_ack)
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()
        assert not [e for e in logs if e["event"] == "planning_intake_unauthorized_dropped"]

    @pytest.mark.asyncio
    async def test_top_level_bot_post_is_dropped_by_bot_gate_alone(self) -> None:
        # Even a TOP-LEVEL bot post (no thread_ts) must be caught by the
        # bot_id gate before the identity gate — no spurious refusal.
        handler, publisher, _ = _make_handler()
        bot_post = _message_event(user="U0OTHERBOT", bot_id="B0OTHER")
        with capture_logs() as logs:
            await handler.handle_message_event(bot_post)
        publisher.publish.assert_not_awaited()
        assert not [e for e in logs if e["event"] == "planning_intake_unauthorized_dropped"]

    @pytest.mark.asyncio
    async def test_subtyped_edit_notification_is_not_intake(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(subtype="message_changed"))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_thread_reply_is_not_intake(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(thread_ts="1751795000.000100"))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unauthorized_member_is_refused_at_info_with_no_reply(self) -> None:
        handler, publisher, wc = _make_handler()
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event(user="U0STRANGER"))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()
        refusals = [e for e in logs if e["event"] == "planning_intake_unauthorized_dropped"]
        assert len(refusals) == 1
        assert refusals[0]["log_level"] == "info"  # F11 — not WARN

    @pytest.mark.asyncio
    async def test_missing_user_field_is_dropped_never_crashes_or_passes(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(user=None))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_whitespace_only_message_is_discarded_with_log_and_no_ack(self) -> None:
        handler, publisher, wc = _make_handler()
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event(text="   \n\t "))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()
        assert [e for e in logs if e["event"] == "planning_intake_blank_dropped"]

    @pytest.mark.asyncio
    async def test_missing_text_field_is_discarded(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(text=None))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_allow_list_admits_any_configured_originator(self) -> None:
        handler, publisher, _ = _make_handler(originators=frozenset({_JAMES, "U0RICH"}))
        await handler.handle_message_event(_message_event(user="U0RICH"))
        publisher.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# Happy path: publish + field mapping (ASSUM-008, F4) + in-thread ack
# ---------------------------------------------------------------------------


class TestQueueAndAck:
    @pytest.mark.asyncio
    async def test_authorized_message_publishes_exactly_one_planning_request(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event())
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_payload_field_mapping_matches_the_contract(self) -> None:
        handler, publisher, _ = _make_handler()
        text = "Add PDF export to the reporting dashboard"
        await handler.handle_message_event(_message_event(text=text))
        kwargs = publisher.publish.await_args.kwargs
        payload = kwargs["payload"]
        assert payload.stage == "planning"
        assert payload.request_text == text  # verbatim (already stripped input)
        assert payload.triggered_by == "jarvis"
        assert payload.originating_adapter == "slack"  # F4 — explicit, never omitted
        assert payload.originating_user == _JAMES
        assert payload.parent_request_id == _TS
        # No "target:" first line in this sentence, so no repository is named
        # and the forge uses its default (binding spec 2026-09-05, rule 1).
        assert payload.target_repo is None
        assert payload.retry_count == 0
        assert payload.requested_at.timestamp() == pytest.approx(1751795701.0002)
        assert payload.queued_at >= payload.requested_at

    @pytest.mark.asyncio
    async def test_subject_and_payload_carry_the_same_correlation_id(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event())
        kwargs = publisher.publish.await_args.kwargs
        assert kwargs["subject"] == f"pipeline.planning-queued.{kwargs['payload'].correlation_id}"
        assert kwargs["correlation_id"] == kwargs["payload"].correlation_id

    @pytest.mark.asyncio
    async def test_verbatim_means_modulo_outer_strip(self) -> None:
        # F10: the installed contract strips request_text on validation.
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(text="  keep  inner   spacing  "))
        assert _published_payload(publisher).request_text == "keep  inner   spacing"

    @pytest.mark.asyncio
    async def test_single_character_idea_is_queued(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(text="y"))
        assert _published_payload(publisher).request_text == "y"

    @pytest.mark.asyncio
    async def test_long_idea_is_queued_untruncated(self) -> None:
        handler, publisher, _ = _make_handler()
        long_text = "x" * 40_000  # Slack's own max length is the only bound
        await handler.handle_message_event(_message_event(text=long_text))
        assert _published_payload(publisher).request_text == long_text

    @pytest.mark.asyncio
    async def test_ack_is_threaded_on_the_original_message_with_correlation_id(self) -> None:
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(_message_event())
        correlation_id = _published_payload(publisher).correlation_id
        wc.chat_postMessage.assert_awaited_once()
        kwargs = wc.chat_postMessage.await_args.kwargs
        assert kwargs["channel"] == _CHANNEL
        assert kwargs["thread_ts"] == _TS
        assert correlation_id in kwargs["text"]

    @pytest.mark.asyncio
    async def test_none_web_client_still_publishes_with_ack_as_noop(self) -> None:
        handler, publisher, _ = _make_handler(web_client=None)
        await handler.handle_message_event(_message_event())
        publisher.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# The "target:" first line — which repository the sentence is built in
# (binding spec 2026-09-05, rules 1 and 2)
# ---------------------------------------------------------------------------


class TestTheTargetToken:
    """The token names a repository; jarvis parses the syntax and nothing else.

    Both shapes travel: ``org/name`` and the short name on its own. The forge
    resolves the short name against its configured checkouts and refuses a
    name it does not know out loud (spec 2026-09-05, rules 3 and 4), so jarvis
    must not filter either shape out at the wire.
    """

    @pytest.mark.asyncio
    async def test_target_token_sets_target_repo(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(
            _message_event(text="target: guardkit/study-tutor\nAdd PDF export to the dashboard")
        )
        assert _published_payload(publisher).target_repo == "guardkit/study-tutor"

    @pytest.mark.asyncio
    async def test_target_token_is_stripped_from_request_text(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(
            _message_event(text="target: guardkit/study-tutor\nAdd PDF export to the dashboard")
        )
        payload = _published_payload(publisher)
        assert payload.request_text == "Add PDF export to the dashboard"
        assert "target:" not in payload.request_text

    @pytest.mark.asyncio
    async def test_a_short_name_travels_to_the_forge(self) -> None:
        """The short name is the one a person actually types.

        It must reach the forge, which is the only side that knows the
        configured checkouts and can either resolve it or say, in the thread,
        that it does not know the name (spec 2026-09-05, rules 3 and 4). A
        wire refusal here would drop the sentence with no reply at all.
        """
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(
            _message_event(text="target: study-tutor\nAdd PDF export")
        )
        payload = _published_payload(publisher)
        assert payload.target_repo == "study-tutor"
        assert payload.request_text == "Add PDF export"
        assert wc.chat_postMessage.await_args.kwargs["text"] == (
            f"Queued for study-tutor · `{payload.correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_an_unknown_short_name_is_still_published_not_dropped(self) -> None:
        """Jarvis does not judge the name; the forge refuses it out loud."""
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(_message_event(text="target: nowhere\nAdd PDF export"))
        assert _published_payload(publisher).target_repo == "nowhere"
        wc.chat_postMessage.assert_awaited()

    @pytest.mark.asyncio
    async def test_multiword_first_line_is_not_a_target(self) -> None:
        # "target: improve the login flow" is a sentence, not a repository.
        handler, publisher, _ = _make_handler()
        text = "target: improve the login flow"
        await handler.handle_message_event(_message_event(text=text))
        payload = _published_payload(publisher)
        assert payload.target_repo is None
        assert payload.request_text == text

    @pytest.mark.asyncio
    async def test_ack_names_the_repo(self) -> None:
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(
            _message_event(text="target: guardkit/study-tutor\nAdd PDF export")
        )
        correlation_id = _published_payload(publisher).correlation_id
        assert wc.chat_postMessage.await_args.kwargs["text"] == (
            f"Queued for guardkit/study-tutor · `{correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_ack_without_a_token_is_unchanged(self) -> None:
        handler, publisher, wc = _make_handler()
        await handler.handle_message_event(_message_event())
        correlation_id = _published_payload(publisher).correlation_id
        assert wc.chat_postMessage.await_args.kwargs["text"] == (
            f"Queued for planning · `{correlation_id}`"
        )

    @pytest.mark.asyncio
    async def test_a_target_line_with_nothing_else_is_refused_as_blank(self) -> None:
        handler, publisher, wc = _make_handler()
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event(text="target: guardkit/study-tutor"))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()
        assert [e for e in logs if e["event"] == "planning_intake_blank_dropped"]

    @pytest.mark.asyncio
    async def test_the_word_further_down_the_message_is_not_a_target(self) -> None:
        handler, publisher, _ = _make_handler()
        text = "Add PDF export\ntarget: guardkit/study-tutor"
        await handler.handle_message_event(_message_event(text=text))
        payload = _published_payload(publisher)
        assert payload.target_repo is None
        assert payload.request_text == text


class TestParseTargetToken:
    """The grammar itself — first line, case-insensitive, exactly one word."""

    def test_no_token_returns_the_text_unchanged(self) -> None:
        assert spi.parse_target_token("just an idea") == (None, "just an idea")

    def test_prefix_is_case_insensitive(self) -> None:
        assert spi.parse_target_token("TARGET:  study-tutor\nbody") == (
            "study-tutor",
            "body",
        )

    def test_an_org_slash_name_is_one_token(self) -> None:
        assert spi.parse_target_token("target: guardkit/api_test\nbody") == (
            "guardkit/api_test",
            "body",
        )

    def test_the_colon_alone_is_not_a_target(self) -> None:
        assert spi.parse_target_token("target:\nbody") == (None, "target:\nbody")

    def test_a_lone_target_line_leaves_a_blank_sentence(self) -> None:
        assert spi.parse_target_token("target: study-tutor") == ("study-tutor", "")

    def test_the_rest_of_the_message_keeps_its_own_line_breaks(self) -> None:
        parsed = spi.parse_target_token("target: t\nline one\n\nline two")
        assert parsed == ("t", "line one\n\nline two")

    def test_a_word_that_merely_starts_with_target_is_not_the_prefix(self) -> None:
        text = "targeting: the wrong thing\nbody"
        assert spi.parse_target_token(text) == (None, text)


# ---------------------------------------------------------------------------
# Dedup (F5 / ASSUM-005)
# ---------------------------------------------------------------------------


class TestDedup:
    @pytest.mark.asyncio
    async def test_redelivered_event_publishes_exactly_once_and_logs_duplicate(self) -> None:
        handler, publisher, _ = _make_handler()
        event = _message_event()
        await handler.handle_message_event(event)
        with capture_logs() as logs:
            await handler.handle_message_event(event)
        assert publisher.publish.await_count == 1
        assert [e for e in logs if e["event"] == "planning_intake_duplicate_dropped"]

    @pytest.mark.asyncio
    async def test_dedup_falls_back_to_channel_and_ts_without_event_id(self) -> None:
        handler, publisher, _ = _make_handler()
        await handler.handle_message_event(_message_event(event_id=None))
        await handler.handle_message_event(_message_event(event_id=None))
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_mark_happens_before_the_publish_await(self) -> None:
        # F5: a redelivery dispatched concurrently must find the mark
        # already set even while the original's publish is still awaited.
        handler, publisher, _ = _make_handler()
        release = __import__("asyncio").Event()

        async def _slow_publish(**_: Any) -> None:
            await release.wait()

        publisher.publish = AsyncMock(side_effect=_slow_publish)
        event = _message_event()
        loop = __import__("asyncio")
        first = loop.get_event_loop().create_task(handler.handle_message_event(event))
        await loop.sleep(0)  # let the first task run up to its publish await
        second = loop.get_event_loop().create_task(handler.handle_message_event(event))
        await loop.sleep(0)
        release.set()
        await first
        await second
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_expired_entry_admits_the_event_again(self) -> None:
        handler, publisher, _ = _make_handler()
        clock = {"now": 1000.0}
        with patch.object(spi, "_monotonic", lambda: clock["now"]):
            await handler.handle_message_event(_message_event())
            clock["now"] += spi._DEDUP_TTL_SECONDS + 1
            await handler.handle_message_event(_message_event())
        assert publisher.publish.await_count == 2

    @pytest.mark.asyncio
    async def test_cap_evicts_oldest_deadline_entry(self) -> None:
        handler, _, _ = _make_handler()
        clock = {"now": 1000.0}
        with patch.object(spi, "_monotonic", lambda: clock["now"]):
            for i in range(spi._DEDUP_MAX_ENTRIES):
                clock["now"] += 0.001
                await handler.handle_message_event(
                    _message_event(event_id=f"Ev{i:07d}", ts=f"{1751795701 + i}.0001")
                )
            assert len(handler._seen_events) == spi._DEDUP_MAX_ENTRIES
            clock["now"] += 0.001
            await handler.handle_message_event(_message_event(event_id="EvOVERFLOW"))
        assert len(handler._seen_events) == spi._DEDUP_MAX_ENTRIES
        assert "Ev0000000" not in handler._seen_events  # oldest deadline evicted
        assert "EvOVERFLOW" in handler._seen_events


# ---------------------------------------------------------------------------
# Failure branches (Group D scenarios 1 and 3)
# ---------------------------------------------------------------------------


class TestFailureBranches:
    @pytest.mark.asyncio
    async def test_publish_failure_posts_threaded_failure_notice_and_never_raises(self) -> None:
        handler, publisher, wc = _make_handler()
        publisher.publish = AsyncMock(side_effect=TimeoutError("transport down"))
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event())
        assert [e for e in logs if e["event"] == "planning_intake_publish_failed"]
        wc.chat_postMessage.assert_awaited_once()
        kwargs = wc.chat_postMessage.await_args.kwargs
        assert kwargs["thread_ts"] == _TS
        assert "repost" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_publish_failure_unmarks_dedup_so_a_redelivery_can_retry(self) -> None:
        handler, publisher, _ = _make_handler()
        publisher.publish = AsyncMock(side_effect=[TimeoutError("down"), None])
        event = _message_event()
        await handler.handle_message_event(event)
        await handler.handle_message_event(event)  # redelivery retries
        assert publisher.publish.await_count == 2

    @pytest.mark.asyncio
    async def test_failed_ack_does_not_undo_the_queued_request(self) -> None:
        handler, publisher, wc = _make_handler()
        wc.chat_postMessage = AsyncMock(side_effect=RuntimeError("slack down"))
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event())
        publisher.publish.assert_awaited_once()
        assert [e for e in logs if e["event"] == "planning_intake_ack_failed"]
        # The request stays marked: the SAME event redelivered is a duplicate.
        await handler.handle_message_event(_message_event())
        assert publisher.publish.await_count == 1

    @pytest.mark.asyncio
    async def test_handler_backstop_never_raises_on_malformed_payload(self) -> None:
        handler, _, _ = _make_handler()
        with capture_logs() as logs:
            await handler.handle_message_event({"event": "not-a-dict"})  # type: ignore[dict-item]
        assert [e for e in logs if e["event"] == "planning_intake_handler_error"]


# ---------------------------------------------------------------------------
# Log hygiene (F6) — no path ever logs the message text
# ---------------------------------------------------------------------------


class TestLogHygiene:
    _SECRET = "sk-SECRET-do-not-log-1234567890"

    def _assert_no_text_in_logs(self, logs: list[dict[str, Any]]) -> None:
        for entry in logs:
            assert self._SECRET not in json.dumps(entry, default=str)

    @pytest.mark.asyncio
    async def test_happy_path_logs_carry_metadata_only(self) -> None:
        handler, _, _ = _make_handler()
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event(text=self._SECRET))
        self._assert_no_text_in_logs(logs)
        queued = [e for e in logs if e["event"] == "planning_intake_queued"]
        assert queued and queued[0]["text_length"] == len(self._SECRET)

    @pytest.mark.asyncio
    async def test_refusal_duplicate_and_failure_paths_never_log_text(self) -> None:
        handler, publisher, _ = _make_handler()
        with capture_logs() as logs:
            # refusal
            await handler.handle_message_event(_message_event(user="U0STRANGER", text=self._SECRET))
            # duplicate
            event = _message_event(text=self._SECRET)
            await handler.handle_message_event(event)
            await handler.handle_message_event(event)
            # publish failure
            publisher.publish = AsyncMock(side_effect=TimeoutError("down"))
            await handler.handle_message_event(
                _message_event(event_id="Ev-fail", ts="1751795999.1", text=self._SECRET)
            )
        self._assert_no_text_in_logs(logs)


# ---------------------------------------------------------------------------
# NatsPlanningQueuedPublisher (envelope + bounded publish)
# ---------------------------------------------------------------------------


class TestNatsPlanningQueuedPublisher:
    def _payload(self) -> Any:
        from nats_core.events import PlanningQueuedPayload

        return PlanningQueuedPayload(
            request_text="idea",
            triggered_by="jarvis",
            originating_adapter="slack",
            originating_user=_JAMES,
            correlation_id="corr-42",
            requested_at="2026-07-06T10:00:00Z",
            queued_at="2026-07-06T10:00:01Z",
        )

    @pytest.mark.asyncio
    async def test_publish_wraps_payload_in_planning_queued_envelope(self) -> None:
        from nats_core import EventType, MessageEnvelope

        js = SimpleNamespace(publish=AsyncMock())
        nats_client = SimpleNamespace(js=js)
        publisher = NatsPlanningQueuedPublisher(nats_client)  # type: ignore[arg-type]
        await publisher.publish(
            subject="pipeline.planning-queued.corr-42",
            payload=self._payload(),
            correlation_id="corr-42",
        )
        subject, raw = js.publish.await_args.args
        assert subject == "pipeline.planning-queued.corr-42"
        envelope = MessageEnvelope.model_validate_json(raw)
        assert envelope.event_type == EventType.PLANNING_QUEUED
        assert envelope.source_id == "jarvis"
        assert envelope.correlation_id == "corr-42"
        assert envelope.payload["originating_adapter"] == "slack"

    @pytest.mark.asyncio
    async def test_publish_timeout_raises_to_caller(self) -> None:
        import asyncio

        async def _hang(*_: Any, **__: Any) -> None:
            await asyncio.sleep(60)

        js = SimpleNamespace(publish=AsyncMock(side_effect=_hang))
        nats_client = SimpleNamespace(js=js)
        publisher = NatsPlanningQueuedPublisher(nats_client, timeout_seconds=0.01)  # type: ignore[arg-type]
        with pytest.raises(TimeoutError):
            await publisher.publish(
                subject="pipeline.planning-queued.corr-42",
                payload=self._payload(),
                correlation_id="corr-42",
            )


# ---------------------------------------------------------------------------
# Factory no-op gates + startup echo (F1/F7)
# ---------------------------------------------------------------------------


def _config(
    *,
    planning_channel: str | None = _CHANNEL,
    originator: str | None = _JAMES,
    bot_token: str | None = "xoxb-token",
    notification_channel: str | None = "C0NOTIFY",
) -> Any:
    return SimpleNamespace(
        slack_planning_channel_id=planning_channel,
        slack_planning_originator_user_id=originator,
        slack_bot_token=SecretStr(bot_token) if bot_token else None,
        slack_channel_id=notification_channel,
        pipeline_publish_timeout_seconds=5,
    )


class TestFactory:
    def test_all_configured_returns_handler_and_echoes_config(self) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(
                _config(), SimpleNamespace(js=None), AsyncMock()
            )
        assert isinstance(handler, PlanningIntakeHandler)
        configured = [e for e in logs if e["event"] == "slack_planning_intake_configured"]
        assert configured and configured[0]["channel_id"] == _CHANNEL
        assert configured[0]["originator_ids"] == [_JAMES]

    @pytest.mark.parametrize(
        ("kwargs", "expected_missing"),
        [
            ({"planning_channel": None}, "slack_planning_channel_id"),
            ({"originator": None}, "slack_planning_originator_user_id"),
            ({"originator": " , "}, "slack_planning_originator_user_id"),
        ],
    )
    def test_missing_planning_keys_no_op_names_the_key(
        self, kwargs: dict[str, Any], expected_missing: str
    ) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(
                _config(**kwargs), SimpleNamespace(js=None), AsyncMock()
            )
        assert handler is None
        noops = [e for e in logs if e["event"] == "slack_planning_intake_no_op"]
        assert noops and expected_missing in noops[0]["reason"]

    def test_both_planning_keys_missing_names_both(self) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(
                _config(planning_channel=None, originator=None),
                SimpleNamespace(js=None),
                AsyncMock(),
            )
        assert handler is None
        reason = next(e for e in logs if e["event"] == "slack_planning_intake_no_op")["reason"]
        assert "slack_planning_channel_id" in reason
        assert "slack_planning_originator_user_id" in reason

    def test_missing_bot_token_no_ops(self) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(
                _config(bot_token=None), SimpleNamespace(js=None), None
            )
        assert handler is None
        no_op = next(e for e in logs if e["event"] == "slack_planning_intake_no_op")
        assert "slack_bot_token" in no_op["reason"]

    def test_missing_nats_no_ops(self) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(_config(), None, AsyncMock())
        assert handler is None
        no_op = next(e for e in logs if e["event"] == "slack_planning_intake_no_op")
        assert "NATS" in no_op["reason"]

    def test_planning_channel_equal_to_notification_channel_warns(self) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(
                _config(notification_channel=_CHANNEL),
                SimpleNamespace(js=None),
                AsyncMock(),
            )
        assert handler is not None  # loud, not fatal
        assert [
            e for e in logs if e["event"] == "planning_intake_channel_matches_notification_channel"
        ]

    def test_comma_separated_originators_reach_the_handler(self) -> None:
        handler = create_slack_planning_intake_handler(
            _config(originator="U0JAMES,U0RICH"), SimpleNamespace(js=None), AsyncMock()
        )
        assert handler is not None
        assert handler._originator_ids == frozenset({"U0JAMES", "U0RICH"})

    def test_publisher_timeout_comes_from_config(self) -> None:
        config = _config()
        config.pipeline_publish_timeout_seconds = 9
        handler = create_slack_planning_intake_handler(
            config, SimpleNamespace(js=None), AsyncMock()
        )
        assert handler is not None
        assert handler._publisher._timeout_seconds == 9.0  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Settings fields (JarvisConfig integration)
# ---------------------------------------------------------------------------


class TestSettingsFields:
    def test_planning_fields_default_to_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        config = JarvisConfig(_env_file=None)
        assert config.slack_planning_channel_id is None
        assert config.slack_planning_originator_user_id is None

    def test_planning_fields_read_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from jarvis.config.settings import JarvisConfig

        monkeypatch.setenv("JARVIS_SLACK_PLANNING_CHANNEL_ID", "C0PLANNING")
        monkeypatch.setenv("JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID", "U0JAMES")
        config = JarvisConfig(_env_file=None)
        assert config.slack_planning_channel_id == "C0PLANNING"
        assert config.slack_planning_originator_user_id == "U0JAMES"


# ---------------------------------------------------------------------------
# TASK-SPL-J02 — union gate (F1) + request-type routing on the shared client
# ---------------------------------------------------------------------------


def _env_config(**env: str) -> Any:
    from jarvis.config.settings import JarvisConfig

    with patch.dict("os.environ", env, clear=True):
        return JarvisConfig(_env_file=None)


_BASE_ENV = {
    "JARVIS_SLACK_BOT_TOKEN": "xoxb-t",
    "JARVIS_SLACK_APP_TOKEN": "xapp-t",
}
_REPLY_ENV = {"JARVIS_SLACK_OPERATOR_USER_ID": "U0OPERATOR"}
_PLANNING_ENV = {
    "JARVIS_SLACK_PLANNING_CHANNEL_ID": _CHANNEL,
    "JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID": _JAMES,
}


class TestUnionGateFactory:
    """The four config permutations (TASK-REV-3240 F1, confirmed HIGH)."""

    def test_both_features_configured_registers_both_handlers(self) -> None:
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(**_BASE_ENV, **_REPLY_ENV, **_PLANNING_ENV)
        client = create_slack_reply_client(config, MagicMock())
        assert client is not None
        assert client._handler is not None
        assert client._events_handler is not None

    def test_reply_only_runs_with_intake_as_its_own_logged_no_op(self) -> None:
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(**_BASE_ENV, **_REPLY_ENV)
        with capture_logs() as logs:
            client = create_slack_reply_client(config, MagicMock())
        assert client is not None
        assert client._handler is not None
        assert client._events_handler is None
        assert [e for e in logs if e["event"] == "slack_planning_intake_no_op"]
        # The reply path itself must NOT have logged a no-op.
        assert not [e for e in logs if e["event"] == "slack_reply_no_op"]

    def test_intake_only_runs_with_operator_id_unset(self) -> None:
        # F1's exact failure permutation: operator id unset must NOT kill
        # a fully configured planning intake.
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(**_BASE_ENV, **_PLANNING_ENV)
        with capture_logs() as logs:
            client = create_slack_reply_client(config, MagicMock())
        assert client is not None
        assert client._handler is None
        assert client._events_handler is not None
        reply_noops = [e for e in logs if e["event"] == "slack_reply_no_op"]
        assert len(reply_noops) == 1
        assert "slack_operator_user_id" in reply_noops[0]["reason"]

    def test_neither_feature_configured_returns_none_with_final_reason(self) -> None:
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(**_BASE_ENV)
        with capture_logs() as logs:
            client = create_slack_reply_client(config, MagicMock())
        assert client is None
        reasons = [e["reason"] for e in logs if e["event"] == "slack_reply_no_op"]
        assert any("no Slack Socket Mode feature configured" in r for r in reasons)

    def test_shared_prerequisites_still_gate_everything(self) -> None:
        # Planning fully configured but no app token: no connection at all.
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(
            JARVIS_SLACK_BOT_TOKEN="xoxb-t",
            **_PLANNING_ENV,
        )
        assert create_slack_reply_client(config, MagicMock()) is None

    def test_intake_only_with_nats_down_returns_none(self) -> None:
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(**_BASE_ENV, **_PLANNING_ENV)
        assert create_slack_reply_client(config, None) is None


class TestRequestRouting:
    """One connection, one ack, per-feature dispatch (F2)."""

    def _client(
        self,
        *,
        approval_handler: Any | None = "default",
        intake_handler: Any | None = "default",
    ) -> tuple[Any, Any, Any, AsyncMock]:
        from jarvis.infrastructure.slack_reply import SlackSocketModeReplyClient

        approval = MagicMock() if approval_handler == "default" else approval_handler
        if approval is not None:
            approval.handle_block_actions = AsyncMock()
        intake = MagicMock() if intake_handler == "default" else intake_handler
        if intake is not None:
            intake.handle_message_event = AsyncMock()
        client = SlackSocketModeReplyClient(
            app_token="xapp-test",
            handler=approval,
            web_client=AsyncMock(),
            events_handler=intake,
        )
        socket_client = MagicMock()
        socket_client.send_socket_mode_response = AsyncMock()
        return client, approval, intake, socket_client

    @pytest.mark.asyncio
    async def test_events_api_routes_to_intake_with_exactly_one_ack(self) -> None:
        client, approval, intake, socket_client = self._client()
        req = SimpleNamespace(type="events_api", envelope_id="env-e1", payload=_message_event())
        await client._on_request(socket_client, req)
        intake.handle_message_event.assert_awaited_once_with(req.payload)
        approval.handle_block_actions.assert_not_awaited()
        assert socket_client.send_socket_mode_response.await_count == 1

    @pytest.mark.asyncio
    async def test_interactive_routes_to_approval_handler_only(self) -> None:
        client, approval, intake, socket_client = self._client()
        payload = {"type": "block_actions", "user": {"id": "U0OPERATOR"}}
        req = SimpleNamespace(type="interactive", envelope_id="env-i1", payload=payload)
        await client._on_request(socket_client, req)
        approval.handle_block_actions.assert_awaited_once_with(payload)
        intake.handle_message_event.assert_not_awaited()
        assert socket_client.send_socket_mode_response.await_count == 1

    @pytest.mark.asyncio
    async def test_events_api_without_intake_handler_is_acked_and_dropped(self) -> None:
        client, approval, _, socket_client = self._client(intake_handler=None)
        req = SimpleNamespace(type="events_api", envelope_id="env-e2", payload=_message_event())
        await client._on_request(socket_client, req)
        approval.handle_block_actions.assert_not_awaited()
        socket_client.send_socket_mode_response.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_interactive_without_approval_handler_is_acked_and_dropped(self) -> None:
        # The intake-only permutation must never crash on a stray click.
        client, _, intake, socket_client = self._client(approval_handler=None)
        req = SimpleNamespace(
            type="interactive", envelope_id="env-i2", payload={"type": "block_actions"}
        )
        await client._on_request(socket_client, req)  # must not raise
        intake.handle_message_event.assert_not_awaited()
        socket_client.send_socket_mode_response.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_request_type_is_acked_only(self) -> None:
        client, approval, intake, socket_client = self._client()
        req = SimpleNamespace(type="slash_commands", envelope_id="env-x1", payload={})
        await client._on_request(socket_client, req)
        approval.handle_block_actions.assert_not_awaited()
        intake.handle_message_event.assert_not_awaited()
        socket_client.send_socket_mode_response.assert_awaited_once()


# ---------------------------------------------------------------------------
# Review fixes (spl001-build-review): SPL-R1 channel strip, SPL-REV-F2
# ValidationError backstop, SEC-1 safe error detail, lifecycle start smoke
# ---------------------------------------------------------------------------


class TestChannelIdStripped:
    def test_trailing_space_in_channel_id_does_not_kill_intake(self) -> None:
        # Review SPL-R1 (confirmed MEDIUM): the JNB-107 verbatim-config
        # lesson applied to the channel key — a mis-copied trailing space
        # must not silently drop every legitimate post.
        handler = create_slack_planning_intake_handler(
            _config(planning_channel=f"{_CHANNEL} "), SimpleNamespace(js=None), AsyncMock()
        )
        assert handler is not None
        assert handler._channel_id == _CHANNEL

    def test_whitespace_only_channel_id_is_a_no_op_not_a_dead_handler(self) -> None:
        with capture_logs() as logs:
            handler = create_slack_planning_intake_handler(
                _config(planning_channel="   "), SimpleNamespace(js=None), AsyncMock()
            )
        assert handler is None
        noop = next(e for e in logs if e["event"] == "slack_planning_intake_no_op")
        assert "slack_planning_channel_id" in noop["reason"]


class TestValidationErrorBackstop:
    _SECRET = "sk-BACKSTOP-SECRET-999"

    def _real_validation_error(self) -> Exception:
        from pydantic import BaseModel, ValidationError

        class _Probe(BaseModel):
            x: int

        try:
            _Probe(x=self._SECRET)  # type: ignore[arg-type]
        except ValidationError as exc:
            return exc
        raise AssertionError("expected ValidationError")

    @pytest.mark.asyncio
    async def test_construction_validation_error_is_a_logged_metadata_discard(self) -> None:
        # Review SPL-REV-F2: the defensive backstop branch had no coverage.
        # No natural input reaches it today (blank text is pre-filtered), so
        # the payload class is patched to raise a REAL ValidationError.
        handler, publisher, wc = _make_handler()
        err = self._real_validation_error()
        with (
            patch(
                "nats_core.events.PlanningQueuedPayload",
                MagicMock(side_effect=err),
            ),
            capture_logs() as logs,
        ):
            await handler.handle_message_event(_message_event(text=self._SECRET))
        publisher.publish.assert_not_awaited()
        wc.chat_postMessage.assert_not_awaited()
        discards = [e for e in logs if e["event"] == "planning_intake_invalid_dropped"]
        assert len(discards) == 1
        assert discards[0]["text_length"] == len(self._SECRET)
        assert self._SECRET not in json.dumps(list(logs), default=str)
        # The dedup mark is KEPT: a redelivery would fail identically.
        with patch(
            "nats_core.events.PlanningQueuedPayload",
            MagicMock(side_effect=err),
        ):
            await handler.handle_message_event(_message_event(text=self._SECRET))
        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_publisher_side_validation_error_never_leaks_text_into_logs(self) -> None:
        # Review SEC-1: an in-publisher pydantic error string embeds input
        # values; _safe_error_detail must suppress it on the publish-failure
        # WARNING (and the failure notice must still post).
        handler, publisher, wc = _make_handler()
        publisher.publish = AsyncMock(side_effect=self._real_validation_error())
        with capture_logs() as logs:
            await handler.handle_message_event(_message_event(text=self._SECRET))
        failures = [e for e in logs if e["event"] == "planning_intake_publish_failed"]
        assert len(failures) == 1
        assert "detail suppressed" in failures[0]["error"]
        assert self._SECRET not in json.dumps(list(logs), default=str)
        wc.chat_postMessage.assert_awaited_once()  # failure notice still posted


class TestIntakeOnlyClientLifecycle:
    @pytest.mark.asyncio
    async def test_intake_only_client_starts_and_stops_cleanly(self) -> None:
        # Review SPL-REV-F3 / house SPL-R2: close the lifecycle chain for
        # the intake-only permutation — the factory-built client must
        # actually start (register exactly one listener) and stop.
        from jarvis.infrastructure.slack_reply import create_slack_reply_client

        config = _env_config(**_BASE_ENV, **_PLANNING_ENV)
        client = create_slack_reply_client(config, MagicMock())
        assert client is not None
        fake_sdk_client = MagicMock()
        fake_sdk_client.socket_mode_request_listeners = []
        fake_sdk_client.connect = AsyncMock()
        fake_sdk_client.close = AsyncMock()
        with patch(
            "slack_sdk.socket_mode.aiohttp.SocketModeClient",
            return_value=fake_sdk_client,
        ):
            await client.start()
        assert len(fake_sdk_client.socket_mode_request_listeners) == 1
        await client.stop()
        fake_sdk_client.close.assert_awaited_once()
