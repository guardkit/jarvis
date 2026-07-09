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


# ---------------------------------------------------------------------------
# TASK-SPL003-J03a — click engine + structured dispositions
# ---------------------------------------------------------------------------

_OP = "U_RICH"


class _FakeSlack:
    """A mutable-message fake: conversations_history returns the current blocks,
    chat_update mutates them — models the Slack message-as-state (ADR-ARCH-004)."""

    def __init__(self, blocks: list[dict[str, Any]]) -> None:
        self.blocks = blocks
        self.web = AsyncMock()
        self.web.conversations_history = AsyncMock(side_effect=self._history)
        self.web.chat_update = AsyncMock(side_effect=self._update)
        self.web.chat_postEphemeral = AsyncMock()

    async def _history(self, **_: Any) -> dict[str, Any]:
        return {"messages": [{"blocks": self.blocks}]}

    async def _update(
        self, *, channel: str, ts: str, text: str, blocks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.blocks = blocks
        return {"ok": True}


def _make_dialogue_handler(
    fake: _FakeSlack, *, operator_ids: frozenset[str] | None = None
) -> tuple[Any, AsyncMock]:
    from jarvis.infrastructure.slack_reply import build_reply_handler

    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    handler = build_reply_handler(
        operator_ids=(operator_ids if operator_ids is not None else frozenset({_OP})),
        publisher=publisher,
        web_client=fake.web,
    )
    return handler, publisher


def _dialogue_render(n: int = 3, **kw: Any) -> list[dict[str, Any]]:
    return ad.build_dialogue_blocks(
        make_details(n, **kw),
        correlation_id="cid123",
        request_id="req-1",
        approval_subject=_SUBJECT,
    )


def _click(
    action_id: str,
    *,
    assumption_id: str = "A1",
    request_id: str = "req-1",
    approval_subject: str = _SUBJECT,
    cycle: int = 1,
    user_id: str = _OP,
    channel: str = "C1",
    message_ts: str = "1720.1",
    overflow: bool = False,
) -> dict[str, Any]:
    value = json.dumps(
        {
            "correlation_id": "cid123",
            "request_id": request_id,
            "assumption_id": assumption_id,
            "cycle": cycle,
            "approval_subject": approval_subject,
        },
        separators=(",", ":"),
    )
    action: dict[str, Any] = {"action_id": action_id, "block_id": f"{assumption_id}::act"}
    if overflow:
        action["type"] = "overflow"
        action["selected_option"] = {"value": value}
    else:
        action["value"] = value
    return {
        "type": "block_actions",
        "user": {"id": user_id},
        "container": {"channel_id": channel, "message_ts": message_ts},
        "channel": {"id": channel},
        "actions": [action],
    }


def _published(publisher: AsyncMock) -> Any:
    return publisher.publish.await_args.kwargs["payload"]


def _dispo_map(payload: Any) -> dict[str, Any]:
    return {d.assumption_id: d for d in (payload.dispositions or [])}


class TestJ03aApproveEach:
    @pytest.mark.asyncio
    async def test_approving_each_publishes_one_decision_distinct_dispositions(self) -> None:
        """@smoke — approve one-by-one → exactly one decision, per-item accepted."""
        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)

        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A2"))
        publisher.publish.assert_not_awaited()  # incomplete → no publish

        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A3"))
        publisher.publish.assert_awaited_once()
        payload = _published(publisher)
        assert payload.decision == "approve"
        assert payload.decided_by == _OP
        dispo = _dispo_map(payload)
        assert set(dispo) == {"A1", "A2", "A3"}
        assert all(d.disposition == "accepted" for d in dispo.values())
        # published subject is {approval_subject}.response
        assert publisher.publish.await_args.kwargs["subject"] == _SUBJECT + ".response"


class TestJ03aDeferAndMixed:
    @pytest.mark.asyncio
    async def test_defer_one_approve_rest_asks_another_cycle(self) -> None:
        """@key-example — defer one → decision=defer, that item deferred, rest kept."""
        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler.handle_block_actions(_click(ad.ACTION_DEFER, assumption_id="A2"))
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A3"))
        payload = _published(publisher)
        assert payload.decision == "defer"
        dispo = _dispo_map(payload)
        assert dispo["A2"].disposition == "deferred"
        assert dispo["A1"].disposition == "accepted"
        assert dispo["A3"].disposition == "accepted"

    @pytest.mark.asyncio
    async def test_dispositions_keyed_by_assumption_id(self) -> None:
        """@key-example — every disposition keyed by its assumption identifier."""
        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)
        for aid in ("A1", "A2", "A3"):
            await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id=aid))
        dispo = _dispo_map(_published(publisher))
        assert sorted(dispo) == ["A1", "A2", "A3"]


class TestJ03aAuthorization:
    @pytest.mark.asyncio
    async def test_click_outside_allowlist_refused_nothing_published(self) -> None:
        """@negative — non-member click refused with a private notice, no publish."""
        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(
            _click(ad.ACTION_APPROVE, assumption_id="A1", user_id="U_STRANGER")
        )
        publisher.publish.assert_not_awaited()
        fake.web.chat_postEphemeral.assert_awaited()  # ephemeral refusal
        # no disposition recorded — the message was never chat.updated
        fake.web.chat_update.assert_not_awaited()


class TestJ03aCompletenessGate:
    @pytest.mark.asyncio
    async def test_no_publish_while_any_undecided(self) -> None:
        """@negative — completeness is the anti-rubber-stamp enforcement point."""
        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A2"))
        publisher.publish.assert_not_awaited()
        # A3 still undecided in the authoritative message
        assert ad.parse_dialogue_blocks(fake.blocks)["A3"]["disposition"] == "undecided"


class TestJ03aRestartSurvival:
    @pytest.mark.asyncio
    async def test_prompt_decidable_after_restart(self) -> None:
        """@edge — decide two pre-restart, third post-restart (fresh handler);
        the published decision carries all three, earlier two preserved exactly."""
        fake = _FakeSlack(_dialogue_render(3))
        handler1, _ = _make_dialogue_handler(fake)
        await handler1.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler1.handle_block_actions(_click(ad.ACTION_DEFER, assumption_id="A2"))

        # "Restart": a brand-new handler with empty first-click-wins state,
        # re-deriving purely from the (mutated) authoritative message.
        handler2, publisher2 = _make_dialogue_handler(fake)
        await handler2.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A3"))
        publisher2.publish.assert_awaited_once()
        dispo = _dispo_map(_published(publisher2))
        assert dispo["A1"].disposition == "accepted"
        assert dispo["A2"].disposition == "deferred"
        assert dispo["A3"].disposition == "accepted"


class TestJ03aConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_final_clicks_publish_once(self) -> None:
        """Two concurrent final clicks do not stall or double-publish."""
        import asyncio

        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A2"))
        # Two near-simultaneous clicks on the final item.
        await asyncio.gather(
            handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A3")),
            handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A3")),
        )
        publisher.publish.assert_awaited_once()


class TestJ03aStaleAndEscalated:
    @pytest.mark.asyncio
    async def test_stale_click_published_faithfully_no_local_refusal(self) -> None:
        """@regression — jarvis has no pending map; a well-formed authorized
        click is published faithfully (forge is the authoritative refuser)."""
        fake = _FakeSlack(_dialogue_render(1))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        publisher.publish.assert_awaited_once()  # published, not locally refused

    @pytest.mark.asyncio
    async def test_escalated_publishes_faithfully(self) -> None:
        """@edge — escalated checkpoint: jarvis publishes; identity is forge's gate."""
        blocks = _dialogue_render(2, checkpoint_type="product_docs_escalated", attempt_count=3)
        fake = _FakeSlack(blocks)
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A2"))
        payload = _published(publisher)
        assert payload.decided_by == _OP
        assert payload.decision == "approve"


class TestJ03aVocabularyAndCancel:
    @pytest.mark.asyncio
    async def test_dispositions_vocabulary_only_accepted_or_deferred(self) -> None:
        """Published dispositions ∈ {accepted, deferred}; never confirmed/overridden."""
        fake = _FakeSlack(_dialogue_render(2))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_APPROVE, assumption_id="A1"))
        await handler.handle_block_actions(_click(ad.ACTION_DEFER, assumption_id="A2"))
        for d in _published(publisher).dispositions:
            assert d.disposition in ("accepted", "deferred")

    @pytest.mark.asyncio
    async def test_cancel_publishes_reject(self) -> None:
        """The whole-run cancel abort publishes decision=reject."""
        fake = _FakeSlack(_dialogue_render(3))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(_click(ad.ACTION_CANCEL, overflow=True))
        publisher.publish.assert_awaited_once()
        assert _published(publisher).decision == "reject"

    @pytest.mark.asyncio
    async def test_whole_checkpoint_approve_publishes_approve(self) -> None:
        """Zero-assumption whole-checkpoint approve → decision=approve, no dispositions."""
        fake = _FakeSlack(_dialogue_render(0))
        handler, publisher = _make_dialogue_handler(fake)
        await handler.handle_block_actions(
            _click(ad.ACTION_WHOLE_APPROVE, assumption_id=ad.WHOLE_CHECKPOINT_ID)
        )
        payload = _published(publisher)
        assert payload.decision == "approve"
        assert payload.dispositions is None

    @pytest.mark.asyncio
    async def test_binary_forge_click_on_plan_subject_ignored(self) -> None:
        """A binary forge_approve on a plan- subject is ignored (belt-and-braces)."""
        fake = _FakeSlack(_dialogue_render(1))
        handler, publisher = _make_dialogue_handler(fake)
        value = json.dumps(
            {
                "request_id": "req-1",
                "build_id": "plan-cid123",
                "correlation_id": "cid123",
                "approval_subject": _SUBJECT,
            },
            separators=(",", ":"),
        )
        payload = {
            "type": "block_actions",
            "user": {"id": _OP},
            "container": {"channel_id": "C1", "message_ts": "1720.1"},
            "channel": {"id": "C1"},
            "actions": [
                {"action_id": "forge_approve", "block_id": "forge_approval", "value": value}
            ],
        }
        await handler.handle_block_actions(payload)
        publisher.publish.assert_not_awaited()
