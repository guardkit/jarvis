"""FEAT-SPL-003 J01 — lifecycle wiring for the planning notification consumer.

Covers the AppState field, the shutdown stop (block 1b4), and its
failure-tolerance. The build-block gating (nats + planning channel + bot token)
is exercised by the factory tests in ``test_planning_notifier.py``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.infrastructure.lifecycle import AppState, shutdown


def _minimal_state(**over: object) -> AppState:
    base: dict[str, object] = {
        "config": MagicMock(),
        "supervisor": MagicMock(),
        "store": MagicMock(),
        "session_manager": MagicMock(),
    }
    base.update(over)
    return AppState(**base)  # type: ignore[arg-type]


def test_appstate_has_planning_notification_consumer_field_defaulting_none() -> None:
    state = _minimal_state()
    assert state.planning_notification_consumer is None


@pytest.mark.asyncio
async def test_shutdown_stops_the_consumer() -> None:
    consumer = MagicMock()
    consumer.stop = AsyncMock()
    state = _minimal_state(planning_notification_consumer=consumer)
    await shutdown(state)
    consumer.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_tolerates_a_consumer_stop_that_raises() -> None:
    consumer = MagicMock()
    consumer.stop = AsyncMock(side_effect=RuntimeError("broker gone"))
    state = _minimal_state(planning_notification_consumer=consumer)
    # Belt-and-braces: the stop is wrapped; shutdown must not raise.
    await shutdown(state)
    consumer.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_noop_when_consumer_absent() -> None:
    state = _minimal_state(planning_notification_consumer=None)
    await shutdown(state)  # must not raise
