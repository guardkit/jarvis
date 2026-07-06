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
