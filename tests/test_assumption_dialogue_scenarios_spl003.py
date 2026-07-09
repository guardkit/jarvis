"""FEAT-SPL-003 scenario suite — the .feature scenarios, hermetic.

This file carries the per-task scenario halves of the assumption-dialogue
feature, driven by synthetic ``ApprovalRequestPayload.details`` fixtures (forge
does not yet project assumptions — ASSUM-014 / TASK-SPL003F-001; live E2E is
J05). Sections:

* ``TestJ02Render...`` — TASK-SPL003-J02 render scenarios + the capture-time
  branch and the ``plan-`` binary-mirror suppression.
* ``TestJ03a...`` — TASK-SPL003-J03a click-engine / disposition scenarios.
* ``TestJ03bEdit...`` — TASK-SPL003-J03b modal scenarios.

No live Slack/NATS anywhere — AsyncMock web clients and synthetic envelopes.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from jarvis.infrastructure import assumption_dialogue as ad
from jarvis.infrastructure.assumption_dialogue import PlanningCheckpointRenderer
from jarvis.infrastructure.slack_notifier import ApprovalRequestsSubscriber
from tests.test_assumption_dialogue_render import make_details

_SUBJECT = "agents.approval.forge.plan-cid123"
_CHANNEL = "C_PLANNING"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approval_msg(details: dict[str, Any], *, subject: str = _SUBJECT) -> SimpleNamespace:
    envelope = {
        "source_id": "forge",
        "event_type": "approval_request",
        "correlation_id": "cid123",
        "payload": {
            "request_id": "req-1",
            "agent_id": "forge",
            "action_description": "Planning checkpoint approval required",
            "risk_level": "medium",
            "details": details,
            "timeout_seconds": 300,
        },
    }
    return SimpleNamespace(subject=subject, data=json.dumps(envelope).encode())


def _renderer() -> tuple[PlanningCheckpointRenderer, AsyncMock]:
    web = AsyncMock()
    web.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1700000000.500000"})
    return PlanningCheckpointRenderer(channel_id=_CHANNEL, web_client=web), web


def _posted_blocks(web: AsyncMock) -> list[list[dict[str, Any]]]:
    return [call.kwargs["blocks"] for call in web.chat_postMessage.await_args_list]


def _sections(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "section"]


# ---------------------------------------------------------------------------
# TASK-SPL003-J02 — render scenarios
# ---------------------------------------------------------------------------


class TestJ02RenderPerAssumptionPrompt:
    @pytest.mark.asyncio
    async def test_checkpoint_renders_per_assumption_prompt_in_thread(self) -> None:
        """@smoke — decision prompt in the originating thread; each item its own."""
        renderer, web = _renderer()
        details = make_details(3, parent_request_id="1700000000.000100")
        await renderer.render(
            details=details, correlation_id="cid123", request_id="req-1", approval_subject=_SUBJECT
        )
        assert web.chat_postMessage.await_count == 1
        call = web.chat_postMessage.await_args
        assert call.kwargs["channel"] == _CHANNEL
        assert call.kwargs["thread_ts"] == "1700000000.000100"
        blocks = call.kwargs["blocks"]
        item_sections = [b for b in _sections(blocks) if b["block_id"] in ("A1", "A2", "A3")]
        assert len(item_sections) == 3
        # each item offers exactly approve/edit/defer
        for aid in ("A1", "A2", "A3"):
            act = next(b for b in blocks if b.get("block_id") == f"{aid}::act")
            assert [el["action_id"] for el in act["elements"]] == [
                ad.ACTION_APPROVE,
                ad.ACTION_EDIT,
                ad.ACTION_DEFER,
            ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("count", [1, 16])
    async def test_every_assumption_is_own_item_regardless_of_count(self, count: int) -> None:
        """@boundary Scenario Outline — 1 and 16 both render N decidable items."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(count),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        all_ids: set[str] = set()
        for blocks in _posted_blocks(web):
            all_ids |= {b["block_id"] for b in _sections(blocks) if b["block_id"].startswith("A")}
        assert all_ids == {f"A{i + 1}" for i in range(count)}

    @pytest.mark.asyncio
    async def test_large_checkpoint_continues_across_messages_same_thread(self) -> None:
        """@boundary — > one message continues in the same thread; none dropped."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(16, parent_request_id="1700000000.000100"),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert web.chat_postMessage.await_count == 2
        for call in web.chat_postMessage.await_args_list:
            assert call.kwargs["thread_ts"] == "1700000000.000100"
        all_ids: set[str] = set()
        for blocks in _posted_blocks(web):
            all_ids |= {b["block_id"] for b in _sections(blocks) if b["block_id"].startswith("A")}
        assert all_ids == {f"A{i + 1}" for i in range(16)}

    @pytest.mark.asyncio
    async def test_third_cycle_renders_normal_prompt(self) -> None:
        """@boundary — the third dialogue cycle is still a normal per-item prompt."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(2, cycle=3, attempt_count=2),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        header = next(
            b
            for b in web.chat_postMessage.await_args.kwargs["blocks"]
            if b.get("block_id") == "spl3hdr"
        )
        assert "cycle 3" in header["text"]["text"]
        assert "<@" not in header["text"]["text"]

    @pytest.mark.asyncio
    async def test_cycle_cap_escalates_to_rich(self) -> None:
        """@boundary @negative — cap reached escalates to Rich, no fourth prompt."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(
                2, checkpoint_type="product_docs_escalated", cycle=3, attempt_count=3
            ),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        header = next(
            b
            for b in web.chat_postMessage.await_args.kwargs["blocks"]
            if b.get("block_id") == "spl3hdr"
        )
        assert "<@U_RICH>" in header["text"]["text"]

    @pytest.mark.asyncio
    async def test_zero_assumption_single_whole_approval(self) -> None:
        """@boundary — zero assumptions → one whole-checkpoint approval only."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(0),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        blocks = web.chat_postMessage.await_args.kwargs["blocks"]
        action_ids = [
            el["action_id"] for b in blocks for el in b.get("elements") or [] if "action_id" in el
        ]
        assert action_ids == [ad.ACTION_WHOLE_APPROVE]

    @pytest.mark.asyncio
    async def test_prompt_never_offers_approve_all(self) -> None:
        """@negative — no approve-all control anywhere in the prompt."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(4),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        blocks = web.chat_postMessage.await_args.kwargs["blocks"]
        action_ids = [el.get("action_id") for b in blocks for el in b.get("elements") or []]
        assert ad.ACTION_WHOLE_APPROVE not in action_ids

    @pytest.mark.asyncio
    async def test_open_questions_render_as_items_not_questions(self) -> None:
        """@negative — open questions → confidence-tagged decidable items."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(
                2, texts=["REST or gRPC?", "Postgres ok?"], confidences=["low", "low"]
            ),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        blocks = web.chat_postMessage.await_args.kwargs["blocks"]
        assert not any(b.get("type") == "input" for b in blocks)
        for aid in ("A1", "A2"):
            assert any(b.get("block_id") == f"{aid}::act" for b in blocks)

    @pytest.mark.asyncio
    async def test_revision_cycle_rerenders_same_thread_with_cycle(self) -> None:
        """@key-example — a revision cycle re-renders in the same thread + cycle no."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(2, cycle=2, parent_request_id="1700000000.000100"),
            correlation_id="cid123",
            request_id="req-2",
            approval_subject=_SUBJECT,
        )
        call = web.chat_postMessage.await_args
        assert call.kwargs["thread_ts"] == "1700000000.000100"
        header = next(b for b in call.kwargs["blocks"] if b.get("block_id") == "spl3hdr")
        assert "cycle 2" in header["text"]["text"]

    @pytest.mark.asyncio
    async def test_no_thread_anchor_degrades_top_level(self) -> None:
        """A checkpoint without a parent_request_id posts top-level (never dropped)."""
        renderer, web = _renderer()
        await renderer.render(
            details=make_details(1, parent_request_id=None),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert web.chat_postMessage.await_count == 1
        assert web.chat_postMessage.await_args.kwargs.get("thread_ts") is None


# ---------------------------------------------------------------------------
# TASK-SPL003-J02 — subscriber capture-time branch + mirror suppression
# ---------------------------------------------------------------------------


class TestJ02SubscriberBranch:
    @pytest.mark.asyncio
    async def test_planning_checkpoint_renders_and_never_captured(self) -> None:
        """Planning checkpoint routes to the renderer; not parked in pending."""
        notifier = AsyncMock()
        renderer = AsyncMock()
        sub = ApprovalRequestsSubscriber(
            nats_client=SimpleNamespace(js=None),
            notifier=notifier,
            planning_renderer=renderer,
        )
        await sub._handle_message(_approval_msg(make_details(3)))
        renderer.render.assert_awaited_once()
        assert renderer.render.await_args.kwargs["details"]["checkpoint_type"] == "product_docs"
        assert renderer.render.await_args.kwargs["approval_subject"] == _SUBJECT
        notifier.capture_approval_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_planning_request_still_captured_unchanged(self) -> None:
        """A build-gate approval still flows to capture_approval_request."""
        notifier = AsyncMock()
        renderer = AsyncMock()
        sub = ApprovalRequestsSubscriber(
            nats_client=SimpleNamespace(js=None),
            notifier=notifier,
            planning_renderer=renderer,
        )
        details = {"checkpoint_type": "build_gate"}
        msg = _approval_msg(details, subject="agents.approval.forge.build-abc123")
        await sub._handle_message(msg)
        renderer.render.assert_not_called()
        notifier.capture_approval_request.assert_awaited_once()
        assert notifier.capture_approval_request.await_args.kwargs["build_id"] == "build-abc123"

    @pytest.mark.asyncio
    async def test_planning_checkpoint_no_renderer_drops_without_capture(self) -> None:
        """Planning-only-unconfigured: no renderer → skip, never capture."""
        notifier = AsyncMock()
        sub = ApprovalRequestsSubscriber(
            nats_client=SimpleNamespace(js=None),
            notifier=notifier,
            planning_renderer=None,
        )
        await sub._handle_message(_approval_msg(make_details(3)))
        notifier.capture_approval_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_sink_planning_only_deployment_skips_build_capture(self) -> None:
        """notifier=None (planning-only): a build-gate request is skipped, no crash."""
        renderer = AsyncMock()
        sub = ApprovalRequestsSubscriber(
            nats_client=SimpleNamespace(js=None),
            notifier=None,
            planning_renderer=renderer,
        )
        msg = _approval_msg(
            {"checkpoint_type": "build_gate"}, subject="agents.approval.forge.build-x"
        )
        await sub._handle_message(msg)  # must not raise
        renderer.render.assert_not_called()


class TestJ02MirrorSuppression:
    @pytest.mark.asyncio
    async def test_plan_build_paused_mirror_not_posted(self) -> None:
        """The binary plan- build-paused mirror posts NOTHING (scenario 15)."""
        from jarvis.infrastructure.slack_notifier import SlackNotifier
        from tests.test_slack_approval_buttons import _pause_notification

        notifier = SlackNotifier(bot_token="xoxb-test", channel_id="C_X")
        notifier._client = AsyncMock()
        note = _pause_notification(
            build_id="plan-cid123",
            feature_id="FEAT-PLANNING",
            approval_subject=_SUBJECT,
        )
        await notifier._deliver_pause_message(note)
        notifier._client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_planning_pause_still_posts(self) -> None:
        """A normal build pause is unaffected by the suppression."""
        from jarvis.infrastructure.slack_notifier import SlackNotifier
        from tests.test_slack_approval_buttons import _pause_notification

        notifier = SlackNotifier(bot_token="xoxb-test", channel_id="C_X")
        notifier._client = AsyncMock()
        notifier._client.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1.0"})
        note = _pause_notification(
            build_id="build-abc123",
            feature_id="FEAT-ABC1",
            approval_subject="agents.approval.forge.build-abc123",
        )
        await notifier._deliver_pause_message(note)
        notifier._client.chat_postMessage.assert_awaited()
