"""Unit tests for the FEAT-SPL-003 J01 notification return channel.

Hermetic — no live Slack/NATS. Covers ``post_threaded`` (429 budget), dedup on
``message_id``, rendering (ASSUM-013), the manual-ack contract, and the factory
no-op gates.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from jarvis.infrastructure import planning_notifier as pn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _envelope_bytes(
    *,
    message: str = "Planning handoff ready",
    level: str = "info",
    correlation_id: str = "cid-123",
    message_id: str | None = None,
    parent_request_id: str | None = None,
    thread_ts: str | None = None,
    target_user: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    event_type: str = "notification",
) -> bytes:
    """Build real MessageEnvelope+NotificationPayload wire bytes."""
    from nats_core import EventType, MessageEnvelope
    from nats_core.events import NotificationPayload

    payload = NotificationPayload(
        message=message,
        level=level,  # type: ignore[arg-type]
        adapter="slack",
        correlation_id=correlation_id,
        parent_request_id=parent_request_id,
        thread_ts=thread_ts,
        target_user=target_user,
        blocks=blocks,
    )
    kwargs: dict[str, Any] = {
        "source_id": "forge",
        "event_type": EventType(event_type),
        "correlation_id": correlation_id,
        "payload": payload.model_dump(mode="json"),
    }
    if message_id is not None:
        kwargs["message_id"] = message_id
    return MessageEnvelope(**kwargs).model_dump_json().encode("utf-8")


class FakeMsg:
    """Minimal JetStream Msg double: data + subject + manual-ack surface."""

    def __init__(self, data: bytes, *, num_delivered: int = 1) -> None:
        self.data = data
        self.subject = "jarvis.notification.slack"
        self.metadata = SimpleNamespace(num_delivered=num_delivered)
        self.ack = mock.AsyncMock()
        self.nak = mock.AsyncMock()


def _consumer(web_client: Any) -> pn.PlanningNotificationConsumer:
    return pn.PlanningNotificationConsumer(
        mock.MagicMock(),  # nats_client (unused by _handle)
        channel_id="C-PLAN",
        web_client=web_client,
    )


# ---------------------------------------------------------------------------
# post_threaded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_threaded_threads_when_thread_ts_present() -> None:
    web = mock.AsyncMock()
    await pn.post_threaded(web, channel="C1", text="hi", thread_ts="123.45")
    kwargs = web.chat_postMessage.call_args.kwargs
    assert kwargs["channel"] == "C1"
    assert kwargs["thread_ts"] == "123.45"


@pytest.mark.asyncio
async def test_post_threaded_top_level_when_no_thread_ts() -> None:
    web = mock.AsyncMock()
    await pn.post_threaded(web, channel="C1", text="hi")
    assert "thread_ts" not in web.chat_postMessage.call_args.kwargs


@pytest.mark.asyncio
async def test_post_threaded_none_client_is_noop() -> None:
    assert await pn.post_threaded(None, channel="C1", text="hi") is None


@pytest.mark.asyncio
async def test_post_threaded_retries_on_429_then_succeeds() -> None:
    from slack_sdk.errors import SlackApiError

    resp_429 = SimpleNamespace(status_code=429, headers={"Retry-After": "0"})
    web = mock.AsyncMock()
    web.chat_postMessage.side_effect = [
        SlackApiError("rate limited", resp_429),
        {"ok": True, "ts": "9.9"},
    ]
    out = await pn.post_threaded(web, channel="C1", text="hi", correlation_id="cid")
    assert out == {"ok": True, "ts": "9.9"}
    assert web.chat_postMessage.await_count == 2


@pytest.mark.asyncio
async def test_post_threaded_returns_none_on_429_budget_exhausted() -> None:
    from slack_sdk.errors import SlackApiError

    resp_429 = SimpleNamespace(status_code=429, headers={"Retry-After": "0"})
    web = mock.AsyncMock()
    web.chat_postMessage.side_effect = SlackApiError("rate limited", resp_429)
    out = await pn.post_threaded(web, channel="C1", text="hi")
    assert out is None
    # initial attempt + _MAX_429_RETRIES
    assert web.chat_postMessage.await_count == pn._MAX_429_RETRIES + 1


@pytest.mark.asyncio
async def test_post_threaded_returns_none_on_non_429_error() -> None:
    from slack_sdk.errors import SlackApiError

    resp = SimpleNamespace(status_code=500, headers={})
    web = mock.AsyncMock()
    web.chat_postMessage.side_effect = SlackApiError("boom", resp)
    assert await pn.post_threaded(web, channel="C1", text="hi") is None


# ---------------------------------------------------------------------------
# rendering (ASSUM-013)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_render_posts_the_factory_words_with_no_bare_id_line() -> None:
    """The tracking id is never a line of body text (rule 2, 2026-09-05)."""
    web = mock.AsyncMock()
    c = _consumer(web)
    await c._handle(FakeMsg(_envelope_bytes(message="all done", correlation_id="cid-xyz")))
    kwargs = web.chat_postMessage.call_args.kwargs
    assert kwargs["text"] == "all done"  # byte-identical to the factory's words
    assert "cid-xyz" not in kwargs["text"]
    assert kwargs["text"].splitlines() == ["all done"]


@pytest.mark.asyncio
async def test_render_carries_the_correlation_id_in_a_context_block() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    await c._handle(FakeMsg(_envelope_bytes(message="all done", correlation_id="cid-xyz")))
    blocks = web.chat_postMessage.call_args.kwargs["blocks"]
    assert blocks[0] == {"type": "section", "text": {"type": "mrkdwn", "text": "all done"}}
    assert blocks[-1] == {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": "`cid-xyz`"}],
    }


@pytest.mark.asyncio
async def test_render_mentions_target_user_and_severity_prefix() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    await c._handle(
        FakeMsg(_envelope_bytes(level="error", target_user="U-RICH", message="escalated"))
    )
    text = web.chat_postMessage.call_args.kwargs["text"]
    assert text.startswith("<@U-RICH> ")
    assert "❌" in text


@pytest.mark.asyncio
async def test_render_passes_blocks_through() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "x"}}]
    await c._handle(FakeMsg(_envelope_bytes(blocks=blocks)))
    posted = web.chat_postMessage.call_args.kwargs["blocks"]
    # The factory's own blocks arrive untouched; the id follows as the
    # small muted line, exactly as it does for a plain message.
    assert posted[:-1] == blocks
    assert posted[-1]["type"] == "context"


@pytest.mark.asyncio
async def test_render_degrades_to_plain_text_for_a_very_long_message() -> None:
    """Too long for one section block: post the words, drop the block kit."""
    web = mock.AsyncMock()
    c = _consumer(web)
    long_message = "x" * (pn._SECTION_TEXT_LIMIT + 1)
    await c._handle(FakeMsg(_envelope_bytes(message=long_message)))
    kwargs = web.chat_postMessage.call_args.kwargs
    assert kwargs["text"] == long_message
    assert "blocks" not in kwargs


# ---------------------------------------------------------------------------
# dedup on message_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dedup_keyed_on_message_id_renders_once() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    data = _envelope_bytes(message_id="mid-1")
    m1, m2 = FakeMsg(data), FakeMsg(data)
    await c._handle(m1)
    await c._handle(m2)
    assert web.chat_postMessage.await_count == 1
    m1.ack.assert_awaited()
    m2.ack.assert_awaited()  # duplicate is acked, not redelivered


@pytest.mark.asyncio
async def test_distinct_message_ids_same_correlation_both_render() -> None:
    # The never-drop guard: a burst shares correlation_id but has distinct
    # message_ids — both must render (message_id key, not correlation+ts).
    web = mock.AsyncMock()
    c = _consumer(web)
    await c._handle(FakeMsg(_envelope_bytes(correlation_id="cid", message_id="a")))
    await c._handle(FakeMsg(_envelope_bytes(correlation_id="cid", message_id="b")))
    assert web.chat_postMessage.await_count == 2


# ---------------------------------------------------------------------------
# manual-ack contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_post_acks() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    m = FakeMsg(_envelope_bytes())
    await c._handle(m)
    m.ack.assert_awaited_once()
    m.nak.assert_not_awaited()


@pytest.mark.asyncio
async def test_transient_post_failure_naks_for_redelivery() -> None:
    web = mock.AsyncMock()
    web.chat_postMessage.return_value = None  # post_threaded returns None on failure
    with mock.patch.object(pn, "post_threaded", new=mock.AsyncMock(return_value=None)):
        c = _consumer(web)
        m = FakeMsg(_envelope_bytes(message_id="mid"), num_delivered=1)
        await c._handle(m)
    m.nak.assert_awaited_once()
    m.ack.assert_not_awaited()
    # un-marked so redelivery is not treated as a duplicate
    assert "mid" not in c._seen


@pytest.mark.asyncio
async def test_post_failure_gives_up_after_max_deliver() -> None:
    with mock.patch.object(pn, "post_threaded", new=mock.AsyncMock(return_value=None)):
        c = _consumer(mock.AsyncMock())
        m = FakeMsg(_envelope_bytes(), num_delivered=pn._MAX_DELIVER)
        await c._handle(m)
    m.ack.assert_awaited_once()  # loud give-up, acked (no storm)
    m.nak.assert_not_awaited()


@pytest.mark.asyncio
async def test_malformed_envelope_is_skipped_and_acked() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    m = FakeMsg(b"{not json")
    await c._handle(m)
    web.chat_postMessage.assert_not_awaited()
    m.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_notification_event_type_is_acked_and_skipped() -> None:
    web = mock.AsyncMock()
    c = _consumer(web)
    # A build_started envelope on this subject (defensive): acked, not rendered.
    m = FakeMsg(_envelope_bytes(event_type="build_started"))
    await c._handle(m)
    web.chat_postMessage.assert_not_awaited()
    m.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_handler_error_is_swallowed_and_acked() -> None:
    c = _consumer(mock.AsyncMock())
    m = FakeMsg(_envelope_bytes())
    # __slots__ makes instance methods read-only; patch at the class level.
    with mock.patch.object(
        pn.PlanningNotificationConsumer,
        "_handle",
        new=mock.AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await c._on_message(m)  # must not raise (DDR-007)
    m.ack.assert_awaited_once()


# ---------------------------------------------------------------------------
# factory no-op gates
# ---------------------------------------------------------------------------


def _config(**over: Any) -> Any:
    base = {
        "slack_planning_channel_id": "C-PLAN",
        "slack_bot_token": SimpleNamespace(get_secret_value=lambda: "xoxb-token"),
    }
    base.update(over)
    return SimpleNamespace(**base)


def test_factory_none_when_nats_unavailable() -> None:
    assert pn.create_planning_notification_consumer(_config(), None) is None


def test_factory_none_when_no_planning_channel() -> None:
    cfg = _config(slack_planning_channel_id=None)
    assert pn.create_planning_notification_consumer(cfg, mock.MagicMock()) is None


def test_factory_none_when_no_bot_token() -> None:
    cfg = _config(slack_bot_token=SimpleNamespace(get_secret_value=lambda: ""))
    assert pn.create_planning_notification_consumer(cfg, mock.MagicMock()) is None


def test_factory_builds_consumer_when_configured() -> None:
    cfg = _config()
    c = pn.create_planning_notification_consumer(cfg, mock.MagicMock())
    assert isinstance(c, pn.PlanningNotificationConsumer)
    assert c._channel_id == "C-PLAN"


def test_factory_strips_channel_whitespace() -> None:
    cfg = _config(slack_planning_channel_id="  C-PLAN  ")
    c = pn.create_planning_notification_consumer(cfg, mock.MagicMock())
    assert c is not None and c._channel_id == "C-PLAN"


# ---------------------------------------------------------------------------
# start()/stop() — subscribe args
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_subscribes_ephemeral_new_manual_ack() -> None:
    from nats.js.api import DeliverPolicy

    nats_client = mock.MagicMock()
    nats_client.js.subscribe = mock.AsyncMock(return_value=SimpleNamespace())
    c = pn.PlanningNotificationConsumer(nats_client, channel_id="C", web_client=mock.AsyncMock())
    await c.start()
    kwargs = nats_client.js.subscribe.call_args.kwargs
    assert nats_client.js.subscribe.call_args.args[0] == "jarvis.notification.slack"
    assert kwargs["manual_ack"] is True
    assert kwargs["ordered_consumer"] is False
    assert kwargs["deliver_policy"] == DeliverPolicy.NEW
    # idempotent
    await c.start()
    assert nats_client.js.subscribe.await_count == 1


@pytest.mark.asyncio
async def test_stop_unsubscribes() -> None:
    sub = SimpleNamespace(unsubscribe=mock.AsyncMock())
    nats_client = mock.MagicMock()
    nats_client.js.subscribe = mock.AsyncMock(return_value=sub)
    c = pn.PlanningNotificationConsumer(nats_client, channel_id="C", web_client=mock.AsyncMock())
    await c.start()
    await c.stop()
    sub.unsubscribe.assert_awaited_once()


def test_json_envelope_roundtrips_through_installed_nats_core() -> None:
    # Guard the fixture builder against contract drift.
    from nats_core import MessageEnvelope

    env = MessageEnvelope.model_validate_json(_envelope_bytes(message_id="x"))
    assert env.message_id == "x"
    assert json.loads(env.model_dump_json())["payload"]["adapter"] == "slack"
