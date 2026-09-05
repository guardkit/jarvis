"""Tests for the approval-card truth lane (options card 2026-07-30).

Three behaviours, one jarvis lane:

* **R1-A — provenance on the pause card.** ``build_pause_blocks`` and the
  ``_render`` text rendering both carry the build id and the reference —
  the 07-27 junk approvals carried ``smoke-…`` references that were on
  the wire but never rendered; a junk card must be visibly junk. Since
  the 2026-09-05 words rewrite they render as ONE muted context line,
  ``Build {build_id} · reference {correlation_id}``, not as two lines of
  prose.
* **R3-A — strip-on-terminal.** A terminal build notification
  (``build_cancelled`` / ``build_complete`` / ``build_failed``) looks up
  the retained pause message and ``chat.update``s the card: action
  surface removed, stamped e.g. "This build was cancelled at HH:MM by
  {cancelled_by}" (time from the retained ``completed_at``).
* **R3-B — answer the tap.** A bounded TTL map ``build_id ->
  (terminal_state, at, by)`` (``terminal_builds.TerminalBuildRegistry``)
  is written by the notification sink and consulted by the reply handler
  BETWEEN first-click-wins and the NATS publish: on a hit nothing is
  published and the card answers honestly ("your tap was not
  recorded."). Post-restart the map is empty and behaviour degrades to
  today's — covered explicitly below.

Plain pytest only, no live Slack/NATS anywhere (AsyncWebClient and the
publisher seam are mocks). Time-dependent behaviour patches the
injectable ``_monotonic`` aliases (``terminal_builds._monotonic`` /
``slack_notifier._monotonic``), NEVER ``time.monotonic``.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.infrastructure.slack_notifier import (
    SlackNotifier,
    build_pause_blocks,
)
from jarvis.infrastructure.slack_reply import build_reply_handler
from jarvis.infrastructure.terminal_builds import (
    TerminalBuildRegistry,
    render_local_hhmm,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COMPLETED_AT = datetime(2026, 7, 30, 14, 7, tzinfo=UTC)
_HHMM = render_local_hhmm(_COMPLETED_AT)  # oracle uses the same local shift
_OPERATOR = "U0OPERATOR"


class FakeClock:
    """Injectable monotonic clock for TTL tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make_notifier(
    registry: TerminalBuildRegistry | None = None,
) -> tuple[SlackNotifier, AsyncMock]:
    """A SlackNotifier with a fully mocked AsyncWebClient (no network)."""
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        notifier = SlackNotifier(
            bot_token="xoxb-test",
            channel_id="C123456",
            terminal_registry=registry,
        )
    mock_client.chat_postMessage.return_value = {"ok": True, "ts": "1720.0001"}
    mock_client.chat_update.return_value = {"ok": True}
    return notifier, mock_client


def _pause_notification(
    build_id: str | None = "build-abc123",
    *,
    correlation_id: str = "corr-pause-1",
) -> ForgeNotification:
    approval_subject = f"agents.approval.forge.{build_id}" if build_id else None
    return ForgeNotification(
        event_type="build_paused",
        correlation_id=correlation_id,
        feature_id="FEAT-ABC1",
        completed_at=_COMPLETED_AT,
        build_id=build_id,
        approval_subject=approval_subject,
        rationale="Coach flagged a wiring risk",
        stage_label="autobuild",
        coach_score=0.42,
        gate_mode="MANDATORY_HUMAN_APPROVAL",
    )


def _terminal_notification(
    event_type: str = "build_cancelled",
    *,
    build_id: str | None = "build-abc123",
    cancelled_by: str | None = "U0CANCEL",
    reason: str | None = "operator cancel",
) -> ForgeNotification:
    return ForgeNotification(
        event_type=event_type,  # type: ignore[arg-type]
        correlation_id="corr-term-1",
        feature_id="FEAT-ABC1",
        completed_at=_COMPLETED_AT,
        build_id=build_id,
        cancelled_by=cancelled_by if event_type == "build_cancelled" else None,
        reason=reason if event_type == "build_cancelled" else None,
    )


async def _buttoned_pause(
    notifier: SlackNotifier,
    build_id: str = "build-abc123",
    request_id: str = "apr-001",
) -> None:
    """Capture a request then deliver its pause → one buttoned card."""
    await notifier.capture_approval_request(
        request_id=request_id,
        build_id=build_id,
        correlation_id="corr-req-1",
        approval_subject=f"agents.approval.forge.{build_id}",
        timeout_seconds=300,
    )
    await notifier._deliver_pause_message(_pause_notification(build_id))


def _section_texts(blocks: list[dict[str, Any]]) -> list[str]:
    return [
        b["text"]["text"]
        for b in blocks
        if b.get("type") == "section" and isinstance(b.get("text"), dict)
    ]


def _context_texts(blocks: list[dict[str, Any]]) -> list[str]:
    """Every muted context line on the card (provenance lives here now)."""
    return [
        element["text"]
        for b in blocks
        if b.get("type") == "context"
        for element in b.get("elements", [])
        if isinstance(element, dict) and isinstance(element.get("text"), str)
    ]


def _actions_in(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "actions"]


def _button_value_json(
    build_id: str = "build-abc123",
    request_id: str = "apr-001",
) -> str:
    import json

    return json.dumps(
        {
            "request_id": request_id,
            "build_id": build_id,
            "correlation_id": "corr-1",
            "approval_subject": f"agents.approval.forge.{build_id}",
        },
        separators=(",", ":"),
    )


def _click_payload(
    *,
    build_id: str = "build-abc123",
    request_id: str = "apr-001",
    action_id: str = "forge_approve",
    user_id: str = _OPERATOR,
) -> dict[str, Any]:
    return {
        "type": "block_actions",
        "user": {"id": user_id},
        "channel": {"id": "C123456"},
        "container": {
            "type": "message",
            "channel_id": "C123456",
            "message_ts": "1720.0001",
        },
        "message": {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "plain_text", "text": "build-paused", "emoji": False},
                },
                {"type": "actions", "block_id": "forge_approval", "elements": []},
            ]
        },
        "actions": [
            {
                "action_id": action_id,
                "block_id": "forge_approval",
                "value": _button_value_json(build_id, request_id),
            }
        ],
    }


def _make_handler(
    registry: TerminalBuildRegistry | None,
) -> tuple[Any, MagicMock, AsyncMock]:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web_client = AsyncMock()
    handler = build_reply_handler(
        operator_ids=frozenset({_OPERATOR}),
        publisher=publisher,
        web_client=web_client,
        terminal_registry=registry,
    )
    return handler, publisher, web_client


# ---------------------------------------------------------------------------
# TerminalBuildRegistry — the R3-B bounded TTL map
# ---------------------------------------------------------------------------


class TestTerminalBuildRegistry:
    """Bounded TTL map build_id -> (terminal_state, at, by)."""

    def test_record_and_get_round_trip(self) -> None:
        registry = TerminalBuildRegistry()
        registry.record(
            "build-abc123",
            terminal_state="build_cancelled",
            at=_COMPLETED_AT,
            by="U0CANCEL",
        )
        rec = registry.get("build-abc123")
        assert rec is not None
        assert rec.terminal_state == "build_cancelled"
        assert rec.at == _COMPLETED_AT
        assert rec.by == "U0CANCEL"

    def test_miss_returns_none(self) -> None:
        assert TerminalBuildRegistry().get("build-unknown") is None

    def test_falsy_build_id_is_ignored(self) -> None:
        registry = TerminalBuildRegistry()
        registry.record("", terminal_state="build_cancelled", at=_COMPLETED_AT)
        assert registry.get("") is None

    def test_entries_expire_after_ttl(self) -> None:
        clock = FakeClock()
        with patch("jarvis.infrastructure.terminal_builds._monotonic", clock):
            registry = TerminalBuildRegistry(ttl_seconds=100.0)
            registry.record("build-abc123", terminal_state="build_cancelled", at=_COMPLETED_AT)
            clock.advance(99.0)
            assert registry.get("build-abc123") is not None
            clock.advance(2.0)
            assert registry.get("build-abc123") is None

    def test_max_entries_evicts_eldest_recording(self) -> None:
        registry = TerminalBuildRegistry(max_entries=2)
        registry.record("build-1", terminal_state="build_complete", at=_COMPLETED_AT)
        registry.record("build-2", terminal_state="build_complete", at=_COMPLETED_AT)
        registry.record("build-3", terminal_state="build_complete", at=_COMPLETED_AT)
        assert registry.get("build-1") is None
        assert registry.get("build-2") is not None
        assert registry.get("build-3") is not None

    def test_overwrite_updates_state_and_eviction_order(self) -> None:
        registry = TerminalBuildRegistry(max_entries=2)
        registry.record("build-1", terminal_state="build_complete", at=_COMPLETED_AT)
        registry.record("build-2", terminal_state="build_complete", at=_COMPLETED_AT)
        # Re-recording build-1 moves it to the back of eviction order.
        registry.record(
            "build-1",
            terminal_state="build_cancelled",
            at=_COMPLETED_AT,
            by="U0CANCEL",
        )
        registry.record("build-3", terminal_state="build_complete", at=_COMPLETED_AT)
        assert registry.get("build-2") is None
        rec = registry.get("build-1")
        assert rec is not None
        assert rec.terminal_state == "build_cancelled"


# ---------------------------------------------------------------------------
# R1-A — provenance on the pause card (blocks + text fallback)
# ---------------------------------------------------------------------------


class TestPauseCardProvenance:
    """Both identifiers stay on the card so junk traffic is visibly junk."""

    def test_blocks_render_build_and_reference_in_one_muted_line(self) -> None:
        blocks = build_pause_blocks(_pause_notification("build-abc123"))
        assert "Build build-abc123 · reference corr-pause-1" in _context_texts(blocks)

    def test_junk_smoke_correlation_is_visible_on_the_card(self) -> None:
        # The 07-27 junk approvals: the smoke- discriminator was on the
        # wire and simply never rendered. It must render now.
        blocks = build_pause_blocks(
            _pause_notification("build-abc123", correlation_id="smoke-1f2e3d")
        )
        assert "Build build-abc123 · reference smoke-1f2e3d" in _context_texts(blocks)

    def test_no_build_id_keeps_the_reference_alone(self) -> None:
        blocks = build_pause_blocks(_pause_notification(None))
        assert "Reference corr-pause-1" in _context_texts(blocks)
        assert not any(t.startswith("Build ") for t in _context_texts(blocks))

    def test_provenance_sections_are_plain_text(self) -> None:
        blocks = build_pause_blocks(_pause_notification("build-abc123"))
        for block in blocks:
            if block.get("type") in ("section", "header"):
                assert block["text"]["type"] == "plain_text"
            if block.get("type") == "context":
                for element in block["elements"]:
                    assert element["type"] == "plain_text"

    def test_provenance_renders_before_buttons_and_keeps_actions(self) -> None:
        value = _button_value_json()
        blocks = build_pause_blocks(_pause_notification("build-abc123"), button_value=value)
        assert len(_actions_in(blocks)) == 1
        provenance_at = next(i for i, b in enumerate(blocks) if b.get("type") == "context")
        actions_at = next(i for i, b in enumerate(blocks) if b.get("type") == "actions")
        assert provenance_at < actions_at

    def test_text_rendering_carries_build_and_reference(self) -> None:
        notifier, _ = _make_notifier()
        text = notifier._render(_pause_notification("build-abc123", correlation_id="smoke-9z"))
        lines = text.split("\n")
        assert "Build build-abc123 · reference smoke-9z" in lines

    def test_text_rendering_without_build_id_keeps_the_reference(self) -> None:
        notifier, _ = _make_notifier()
        text = notifier._render(_pause_notification(None))
        lines = text.split("\n")
        assert "Reference corr-pause-1" in lines
        assert not any(line.startswith("Build build-") for line in lines)


# ---------------------------------------------------------------------------
# R3-A — strip-on-terminal (the retained pause card is stamped)
# ---------------------------------------------------------------------------


class TestStripOnTerminal:
    """A terminal notification strips the retained card's action surface."""

    @pytest.mark.asyncio
    async def test_cancel_strips_buttons_and_stamps_card(self) -> None:
        notifier, client = _make_notifier()
        await _buttoned_pause(notifier)
        client.chat_update.reset_mock()

        await notifier._stamp_terminal_pause_message(_terminal_notification())

        assert notifier._pause_messages == {}
        kwargs = client.chat_update.await_args.kwargs
        assert kwargs["ts"] == "1720.0001"
        blocks = kwargs["blocks"]
        assert _actions_in(blocks) == []
        texts = _section_texts(blocks)
        assert f"This build was cancelled at {_HHMM} by U0CANCEL" in texts
        # A terminal card offers no approval affordance of any kind.
        assert "Use CLI to approve or reject this build." not in texts
        assert f"This build was cancelled at {_HHMM} by U0CANCEL" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_cancel_without_actor_stamps_without_by_clause(self) -> None:
        notifier, client = _make_notifier()
        await _buttoned_pause(notifier)
        client.chat_update.reset_mock()

        await notifier._stamp_terminal_pause_message(_terminal_notification(cancelled_by=None))

        texts = _section_texts(client.chat_update.await_args.kwargs["blocks"])
        assert f"This build was cancelled at {_HHMM}" in texts

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("event_type", "expected"),
        [
            ("build_complete", "This build completed at"),
            ("build_failed", "This build failed at"),
        ],
    )
    async def test_complete_and_failed_also_strip(self, event_type: str, expected: str) -> None:
        notifier, client = _make_notifier()
        await _buttoned_pause(notifier)
        client.chat_update.reset_mock()

        await notifier._stamp_terminal_pause_message(_terminal_notification(event_type))

        assert notifier._pause_messages == {}
        blocks = client.chat_update.await_args.kwargs["blocks"]
        assert _actions_in(blocks) == []
        assert f"{expected} {_HHMM}" in _section_texts(blocks)

    @pytest.mark.asyncio
    async def test_text_only_retained_card_is_stamped_too(self) -> None:
        notifier, client = _make_notifier()
        # Pause with no captured request → text-only card, still retained.
        await notifier._deliver_pause_message(_pause_notification())
        client.chat_update.reset_mock()

        await notifier._stamp_terminal_pause_message(_terminal_notification())

        texts = _section_texts(client.chat_update.await_args.kwargs["blocks"])
        assert f"This build was cancelled at {_HHMM} by U0CANCEL" in texts
        assert "Use CLI to approve or reject this build." not in texts

    @pytest.mark.asyncio
    async def test_no_retained_card_is_a_silent_no_op(self) -> None:
        notifier, client = _make_notifier()

        await notifier._stamp_terminal_pause_message(_terminal_notification())

        client.chat_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_worker_stamps_then_posts_the_terminal_line(self) -> None:
        notifier, client = _make_notifier()
        await _buttoned_pause(notifier)
        client.chat_postMessage.reset_mock()
        client.chat_update.reset_mock()

        await notifier.start()
        try:
            await notifier.notify(_terminal_notification())
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
        finally:
            await notifier.stop()

        # The strip chat.update happened AND the terminal text still posted.
        assert client.chat_update.await_count == 1
        assert _actions_in(client.chat_update.await_args.kwargs["blocks"]) == []
        assert "build-cancelled" in client.chat_postMessage.await_args.kwargs["text"]

    @pytest.mark.asyncio
    async def test_late_capture_cannot_rebutton_a_stamped_card(self) -> None:
        notifier, client = _make_notifier()
        await _buttoned_pause(notifier)
        await notifier._stamp_terminal_pause_message(_terminal_notification())
        client.chat_update.reset_mock()

        # A boot-reconcile re-emit landing after the terminal stamp: the
        # registry record is gone, so the capture parks in the pending
        # map instead of chat.updating buttons back onto the dead card.
        await notifier.capture_approval_request(
            request_id="apr-002",
            build_id="build-abc123",
            correlation_id="corr-req-2",
            approval_subject="agents.approval.forge.build-abc123",
            timeout_seconds=300,
        )

        client.chat_update.assert_not_awaited()
        assert "build-abc123" in notifier._pending_approvals

    @pytest.mark.asyncio
    async def test_stamp_failure_never_raises(self) -> None:
        from slack_sdk.errors import SlackApiError

        notifier, client = _make_notifier()
        await _buttoned_pause(notifier)
        client.chat_update.side_effect = SlackApiError(
            message="message_not_found",
            response=MagicMock(status_code=404),
        )

        with capture_logs() as logs:
            await notifier._stamp_terminal_pause_message(_terminal_notification())

        assert any(log["event"] == "slack_pause_button_update_failed" for log in logs)


# ---------------------------------------------------------------------------
# R3-B — the sink writes terminal truth into the shared registry
# ---------------------------------------------------------------------------


class TestSinkWritesTerminalRegistry:
    """notify() records terminal events before any delivery gating."""

    @pytest.mark.asyncio
    async def test_cancel_notification_records_terminal_state(self) -> None:
        registry = TerminalBuildRegistry()
        notifier, _ = _make_notifier(registry)
        await notifier.start()
        try:
            await notifier.notify(_terminal_notification())
        finally:
            await notifier.stop()

        rec = registry.get("build-abc123")
        assert rec is not None
        assert rec.terminal_state == "build_cancelled"
        assert rec.at == _COMPLETED_AT
        assert rec.by == "U0CANCEL"

    @pytest.mark.asyncio
    async def test_records_even_when_sink_not_started(self) -> None:
        # Truth-recording must not depend on Slack delivery state: a
        # dropped notification still answers later taps.
        registry = TerminalBuildRegistry()
        notifier, _ = _make_notifier(registry)

        await notifier.notify(_terminal_notification("build_failed", cancelled_by=None))

        rec = registry.get("build-abc123")
        assert rec is not None
        assert rec.terminal_state == "build_failed"
        assert rec.by is None

    @pytest.mark.asyncio
    async def test_pause_events_are_not_recorded(self) -> None:
        registry = TerminalBuildRegistry()
        notifier, _ = _make_notifier(registry)

        await notifier.notify(_pause_notification())

        assert registry.get("build-abc123") is None

    @pytest.mark.asyncio
    async def test_unwired_registry_is_a_no_op(self) -> None:
        notifier, _ = _make_notifier(None)
        # Must not raise (DDR-007) with no registry present.
        await notifier.notify(_terminal_notification())


# ---------------------------------------------------------------------------
# R3-B — the reply handler answers a tap racing a terminal state
# ---------------------------------------------------------------------------


class TestTapAfterTerminal:
    """The tap-races-terminal answer: honest card, nothing published."""

    @pytest.mark.asyncio
    async def test_tap_on_cancelled_build_publishes_nothing(self) -> None:
        registry = TerminalBuildRegistry()
        registry.record(
            "build-abc123",
            terminal_state="build_cancelled",
            at=_COMPLETED_AT,
            by="U0CANCEL",
        )
        handler, publisher, web_client = _make_handler(registry)

        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_not_awaited()
        kwargs = web_client.chat_update.await_args.kwargs
        expected = f"This build was already cancelled at {_HHMM} — your tap was not recorded."
        assert kwargs["text"] == expected
        assert _actions_in(kwargs["blocks"]) == []
        assert expected in _section_texts(kwargs["blocks"])

    @pytest.mark.asyncio
    async def test_tap_stays_unmarked_and_repeat_taps_reanswer(self) -> None:
        registry = TerminalBuildRegistry()
        registry.record("build-abc123", terminal_state="build_cancelled", at=_COMPLETED_AT)
        handler, publisher, web_client = _make_handler(registry)

        await handler.handle_block_actions(_click_payload())
        await handler.handle_block_actions(_click_payload())

        # Nothing was recorded, so first-click-wins must NOT be marked —
        # both taps get the honest answer, neither publishes.
        assert handler._decided_request_ids == set()
        publisher.publish.assert_not_awaited()
        assert web_client.chat_update.await_count == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("terminal_state", "expected_prefix"),
        [
            ("build_complete", "This build already completed at"),
            ("build_failed", "This build already failed at"),
        ],
    )
    async def test_complete_and_failed_wording(
        self, terminal_state: str, expected_prefix: str
    ) -> None:
        registry = TerminalBuildRegistry()
        registry.record("build-abc123", terminal_state=terminal_state, at=_COMPLETED_AT)
        handler, publisher, web_client = _make_handler(registry)

        await handler.handle_block_actions(_click_payload(action_id="forge_reject"))

        publisher.publish.assert_not_awaited()
        assert web_client.chat_update.await_args.kwargs["text"] == (
            f"{expected_prefix} {_HHMM} — your tap was not recorded."
        )

    @pytest.mark.asyncio
    async def test_expired_entry_degrades_to_publish(self) -> None:
        clock = FakeClock()
        with patch("jarvis.infrastructure.terminal_builds._monotonic", clock):
            registry = TerminalBuildRegistry(ttl_seconds=100.0)
            registry.record("build-abc123", terminal_state="build_cancelled", at=_COMPLETED_AT)
            clock.advance(101.0)
            handler, publisher, web_client = _make_handler(registry)

            await handler.handle_block_actions(_click_payload())

        # TTL expired → consult misses → today's behaviour: publish +
        # "Decision recorded" success update.
        publisher.publish.assert_awaited_once()
        assert "apr-001" in handler._decided_request_ids
        final_text = web_client.chat_update.await_args.kwargs["text"]
        assert final_text == "Decision recorded: approve"

    @pytest.mark.asyncio
    async def test_empty_map_post_restart_degrades_to_publish(self) -> None:
        # The documented restart degrade: a fresh (empty) registry is
        # exactly the post-restart state — the tap publishes as today.
        handler, publisher, _ = _make_handler(TerminalBuildRegistry())

        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_awaited_once()
        assert "apr-001" in handler._decided_request_ids

    @pytest.mark.asyncio
    async def test_unwired_registry_degrades_to_publish(self) -> None:
        handler, publisher, _ = _make_handler(None)

        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_different_build_terminal_does_not_block_this_tap(self) -> None:
        registry = TerminalBuildRegistry()
        registry.record("build-other", terminal_state="build_cancelled", at=_COMPLETED_AT)
        handler, publisher, _ = _make_handler(registry)

        await handler.handle_block_actions(_click_payload(build_id="build-abc123"))

        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_duplicate_click_check_still_precedes_terminal_consult(self) -> None:
        # A request already decided in-process stays a silent duplicate
        # drop even if the build later turns terminal — the recorded
        # decision was real, the card already says so.
        registry = TerminalBuildRegistry()
        handler, publisher, web_client = _make_handler(registry)
        await handler.handle_block_actions(_click_payload())
        assert publisher.publish.await_count == 1
        registry.record("build-abc123", terminal_state="build_cancelled", at=_COMPLETED_AT)
        web_client.chat_update.reset_mock()

        await handler.handle_block_actions(_click_payload())

        assert publisher.publish.await_count == 1
        web_client.chat_update.assert_not_awaited()


# ---------------------------------------------------------------------------
# Lifecycle wiring — ONE registry shared by sink and reply handler
# ---------------------------------------------------------------------------


class TestSharedSeamWiring:
    """The same registry instance reaches both constructors."""

    def test_sink_write_is_visible_to_handler_consult(self) -> None:
        # End-to-end over the seam without lifecycle: one registry, the
        # sink records, the handler's consult sees it.
        registry = TerminalBuildRegistry()
        notifier, _ = _make_notifier(registry)
        handler, _, _ = _make_handler(registry)

        notifier._record_terminal_state(_terminal_notification())

        assert handler._terminal_registry is registry
        assert registry.get("build-abc123") is not None

    def test_lifecycle_passes_one_registry_to_both_factories(self) -> None:
        import inspect

        from jarvis.infrastructure import lifecycle as lc

        # Both factories accept the seam parameter...
        assert "terminal_registry" in inspect.signature(lc.create_slack_sink).parameters
        assert "terminal_registry" in inspect.signature(lc.create_slack_reply_client).parameters
        # ...and build_app_state wires the SAME instance into each (source
        # inspection keeps this cheap — no full lifecycle boot needed).
        source = inspect.getsource(lc.build_app_state)
        assert "terminal_registry = TerminalBuildRegistry()" in source
        # Pinned call shapes moved 2026-08-15 (build-side mention lane): both
        # factories gained a SECOND shared seam, ``audience`` — the
        # who-to-tell registry. The terminal_registry assertions are unchanged
        # in substance; only the surrounding argument list grew.
        sink_call = (
            "create_slack_sink(\n"
            "        config, terminal_registry=terminal_registry, audience=audience_registry\n"
            "    )"
        )
        assert sink_call in source
        reply_call = (
            "create_slack_reply_client(\n"
            "        config,\n"
            "        nats_client,\n"
            "        terminal_registry=terminal_registry,\n"
            "        spec_texts=spec_texts,\n"
            "        audience=audience_registry,\n"
            "    )"
        )
        assert reply_call in source
