"""FEAT-SPL-003 J01 scenario tests — the notification return channel.

Each test maps to a Gherkin scenario in
``features/feat-spl-003-assumption-dialogue/feat-spl-003-assumption-dialogue.feature``
(the @task:TASK-SPL003-J01 set). Fully hermetic: a FakeMsg drives the consumer's
``_handle`` and an AsyncMock web client records posts. No live Slack/NATS.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from jarvis.infrastructure import planning_notifier as pn

# Reuse the wire-bytes + FakeMsg helpers from the unit module.
from tests.test_planning_notifier import FakeMsg, _envelope_bytes

_SCENARIO_COUNT = 6


def _consumer(web_client: Any) -> pn.PlanningNotificationConsumer:
    return pn.PlanningNotificationConsumer(
        mock.MagicMock(), channel_id="C-PLAN", web_client=web_client
    )


@pytest.mark.asyncio
async def test_planned_handoff_renders_into_originating_thread() -> None:
    """@smoke — A planned handoff notification is rendered into the originating thread."""
    web = mock.AsyncMock()
    c = _consumer(web)
    await c._handle(
        FakeMsg(
            _envelope_bytes(
                message="Planning run reached its planned handoff",
                correlation_id="cid-handoff",
                parent_request_id="1751795701.000200",
            )
        )
    )
    assert web.chat_postMessage.await_count == 1
    kwargs = web.chat_postMessage.call_args.kwargs
    assert kwargs["thread_ts"] == "1751795701.000200"  # posted as a thread reply
    assert kwargs["channel"] == "C-PLAN"
    assert "Planning run reached its planned handoff" in kwargs["text"]  # verbatim
    assert "`cid-handoff`" in kwargs["text"]  # correlation id present


@pytest.mark.asyncio
async def test_notification_without_anchor_degrades_to_channel_never_dropped() -> None:
    """@negative — degrades to the channel and is never dropped."""
    web = mock.AsyncMock()
    c = _consumer(web)
    m = FakeMsg(_envelope_bytes(message="status update", correlation_id="cid-deg"))
    await c._handle(m)
    kwargs = web.chat_postMessage.call_args.kwargs
    assert "thread_ts" not in kwargs  # top-level post
    assert kwargs["channel"] == "C-PLAN"
    assert "`cid-deg`" in kwargs["text"]  # traceable by hand
    m.ack.assert_awaited_once()  # not dropped: rendered + acked


@pytest.mark.asyncio
async def test_malformed_notification_skipped_consumer_keeps_running() -> None:
    """@negative — A malformed notification is skipped and the consumer keeps running."""
    web = mock.AsyncMock()
    c = _consumer(web)
    bad = FakeMsg(b"{ this is not valid json")
    await c._handle(bad)
    bad.ack.assert_awaited_once()
    assert web.chat_postMessage.await_count == 0

    good = FakeMsg(_envelope_bytes(message="next one", message_id="mid-good"))
    await c._handle(good)
    assert web.chat_postMessage.await_count == 1  # subsequent notification renders


@pytest.mark.asyncio
async def test_duplicate_delivery_renders_only_once() -> None:
    """@edge-case — A duplicate delivery of the same notification renders only once."""
    web = mock.AsyncMock()
    c = _consumer(web)
    data = _envelope_bytes(message="dup", message_id="mid-dup")
    await c._handle(FakeMsg(data))
    await c._handle(FakeMsg(data))  # same message_id, quick succession
    assert web.chat_postMessage.await_count == 1


@pytest.mark.asyncio
async def test_thread_mapping_survives_a_jarvis_restart() -> None:
    """@smoke @edge-case — The thread mapping survives a Jarvis restart.

    A FRESH consumer instance (no retained jarvis state — restart by
    construction) threads correctly using the anchor from the payload itself,
    not anything jarvis remembered.
    """
    web = mock.AsyncMock()
    fresh_consumer_after_restart = _consumer(web)  # brand-new instance, empty _seen
    await fresh_consumer_after_restart._handle(
        FakeMsg(
            _envelope_bytes(
                message="post-restart notification",
                correlation_id="cid-restart",
                parent_request_id="1751000000.000100",
            )
        )
    )
    kwargs = web.chat_postMessage.call_args.kwargs
    assert kwargs["thread_ts"] == "1751000000.000100"  # anchor from payload, not memory


@pytest.mark.asyncio
async def test_burst_of_notifications_all_render_in_order() -> None:
    """@edge-case — A burst of notifications for the same run all render in order."""
    web = mock.AsyncMock()
    c = _consumer(web)
    order = ["first", "second", "third", "fourth"]
    for i, msg in enumerate(order):
        await c._handle(
            FakeMsg(_envelope_bytes(message=msg, correlation_id="cid-burst", message_id=f"mid-{i}"))
        )
    posted = [call.kwargs["text"] for call in web.chat_postMessage.call_args_list]
    assert len(posted) == len(order)
    for msg, text in zip(order, posted, strict=True):
        assert msg in text  # every notification appeared, in publication order


def test_scenario_count_guard() -> None:
    """Collect-only pin: the six J01 scenarios are all present."""
    import tests.test_planning_notifier_scenarios_spl003 as mod

    scenario_tests = [
        n for n in dir(mod) if n.startswith("test_") and n != "test_scenario_count_guard"
    ]
    assert len(scenario_tests) == _SCENARIO_COUNT
