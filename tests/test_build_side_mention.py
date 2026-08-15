"""The build-side mention lane (2026-08-15) — the owner is told, by name.

**The live defect this covers.** Planning run ``71c5e49a`` / build
``build-FEAT-D9A6-20260815104250``: the owner drives features from Slack,
the planning-side notifications @-mention him (``planning_notifier``
renders ``payload.target_user``), but the BUILD-side line mentioned
nobody. jarvis stamped the already-tapped gate card ("This build completed
at 12:02") and posted a bare ``[12:02] Pipeline FEAT-D9A6: build-complete
(PASSED)``. Nobody noticed for an hour — and nothing on that line said
what state the code was in or that the merge word was the next act.

**What is fenced here.**

* The mention chain, all four rungs: planning target (same
  correlation_id) → gate clicker (same build_id) → a SOLE configured
  operator → nobody. Never an invented id, never a multi-member config
  constant.
* Terminal events only. ``build_started`` stays unmentioned: mentioning
  progress trains the reader to ignore the mention.
* The finished-build sentence: how much passed, where the code is, and
  that the merge word is the owner's. Honest on partial failure, honest
  when forge sent no branch (never derive one).
* DDR-007 never-raise: a registry that throws costs the message its
  mention, never the message.

**Deliberately NOT here: any approval surface.** The merge card belongs to
the conductor, which is parked. This lane adds one plain sentence and no
button — a test asserting the absence of an actions block is below.

**One note on the plain-name fence.** The real branch name is
``autobuild/FEAT-D9A6``, and "autobuild" is a codename the phrase-book
bars from Slack surfaces. It is payload data (a forge-authored git ref),
not template text — the same class as a stage label — so it is relayed
verbatim, exactly as ``tests/test_plain_name_slack_surfaces.py`` describes
in its template-vs-payload note.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.infrastructure import planning_notifier as pn
from jarvis.infrastructure.build_audience import BuildAudienceRegistry
from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
)
from jarvis.infrastructure.slack_notifier import SlackNotifier
from jarvis.infrastructure.slack_reply import build_reply_handler

_AT = datetime(2026, 8, 15, 12, 2, tzinfo=UTC)
_HHMM = _AT.astimezone().strftime("%H:%M")
_CORR = "corr-d9a6"
_BUILD = "build-FEAT-D9A6-20260815104250"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _notifier(
    *,
    audience: BuildAudienceRegistry | None = None,
    operator_ids: frozenset[str] = frozenset(),
) -> SlackNotifier:
    """A SlackNotifier with a fully mocked web client — no network."""
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_cls.return_value = AsyncMock()
        return SlackNotifier(
            bot_token="xoxb-test",
            channel_id="C123456",
            audience=audience,
            operator_ids=operator_ids,
        )


def _complete(**overrides: Any) -> ForgeNotification:
    fields: dict[str, Any] = {
        "event_type": "build_complete",
        "correlation_id": _CORR,
        "feature_id": "FEAT-D9A6",
        "completed_at": _AT,
        "build_id": _BUILD,
        "branch": "autobuild/FEAT-D9A6",
        "repo": "api_test",
        "tasks_completed": 4,
        "tasks_failed": 0,
        "tasks_total": 4,
    }
    fields.update(overrides)
    return ForgeNotification(**fields)


# ---------------------------------------------------------------------------
# The registry itself — bounded, total, and unfussy about falsy input.
# ---------------------------------------------------------------------------


class TestBuildAudienceRegistry:
    def test_records_and_answers_both_maps(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        registry.record_gate_clicker(_BUILD, "U0CLICK")
        assert registry.planning_target(_CORR) == "U0RICH"
        assert registry.gate_clicker(_BUILD) == "U0CLICK"

    def test_the_two_maps_never_answer_each_other(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        assert registry.gate_clicker(_CORR) is None
        assert registry.planning_target(_BUILD) is None

    @pytest.mark.parametrize(
        ("key", "member"),
        (("", "U0RICH"), (None, "U0RICH"), (_CORR, ""), (_CORR, None)),
    )
    def test_falsy_key_or_member_is_never_recorded(
        self, key: str | None, member: str | None
    ) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(key, member)
        registry.record_gate_clicker(key, member)
        assert registry.planning_target(key or _CORR) is None
        assert registry.gate_clicker(key or _BUILD) is None

    def test_misses_answer_none(self) -> None:
        registry = BuildAudienceRegistry()
        assert registry.planning_target("never-seen") is None
        assert registry.gate_clicker("never-seen") is None

    def test_cap_evicts_the_eldest_recording(self) -> None:
        registry = BuildAudienceRegistry(max_entries=3)
        for i in range(5):
            registry.record_planning_target(f"c-{i}", f"U-{i}")
        assert registry.planning_target("c-0") is None
        assert registry.planning_target("c-1") is None
        assert registry.planning_target("c-4") == "U-4"

    def test_re_record_refreshes_eviction_order_and_value(self) -> None:
        registry = BuildAudienceRegistry(max_entries=2)
        registry.record_planning_target("c-a", "U-A")
        registry.record_planning_target("c-b", "U-B")
        registry.record_planning_target("c-a", "U-A2")  # moves c-a to the back
        registry.record_planning_target("c-c", "U-C")  # evicts c-b, not c-a
        assert registry.planning_target("c-a") == "U-A2"
        assert registry.planning_target("c-b") is None
        assert registry.planning_target("c-c") == "U-C"


# ---------------------------------------------------------------------------
# The mention chain — a, b, c, d.
# ---------------------------------------------------------------------------


class TestMentionChain:
    def test_a_planning_target_for_the_same_correlation_wins(self) -> None:
        """Rung (a) — and it OUTRANKS both later rungs, which are also set."""
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        registry.record_gate_clicker(_BUILD, "U0CLICK")
        text = _notifier(audience=registry, operator_ids=frozenset({"U0SOLE"}))._render(_complete())
        assert text.startswith("<@U0RICH> ")

    def test_b_gate_clicker_for_the_same_build_when_no_planning_target(self) -> None:
        """Rung (b) — and it outranks the sole-operator fallback."""
        registry = BuildAudienceRegistry()
        registry.record_gate_clicker(_BUILD, "U0CLICK")
        text = _notifier(audience=registry, operator_ids=frozenset({"U0SOLE"}))._render(_complete())
        assert text.startswith("<@U0CLICK> ")

    def test_a_does_not_leak_across_correlations(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target("some-other-run", "U0RICH")
        text = _notifier(audience=registry)._render(_complete())
        assert "<@" not in text

    def test_b_does_not_leak_across_builds(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_gate_clicker("build-someone-elses", "U0CLICK")
        text = _notifier(audience=registry)._render(_complete())
        assert "<@" not in text

    def test_c_sole_operator_is_mentioned(self) -> None:
        """Rung (c) — exactly one allowlist member is unambiguous."""
        text = _notifier(operator_ids=frozenset({"U0SOLE"}))._render(_complete())
        assert text.startswith("<@U0SOLE> ")

    def test_d_two_operators_mention_nobody(self) -> None:
        """Rung (d) — a multi-member allowlist is config, not a fact about THIS build."""
        text = _notifier(operator_ids=frozenset({"U0ONE", "U0TWO"}))._render(_complete())
        assert "<@" not in text

    def test_d_empty_allowlist_and_empty_registry_mention_nobody(self) -> None:
        text = _notifier(audience=BuildAudienceRegistry())._render(_complete())
        assert "<@" not in text
        assert text.startswith(f"[{_HHMM}] Pipeline FEAT-D9A6:")

    def test_d_unwired_registry_mentions_nobody(self) -> None:
        assert "<@" not in _notifier()._render(_complete())

    def test_build_failed_gains_the_mention_and_keeps_its_reason(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(
            _complete(event_type="build_failed", failure_reason="a required check did not pass")
        )
        assert text == (
            f"<@U0RICH> [{_HHMM}] Pipeline FEAT-D9A6: build-failed (a required check did not pass)"
        )

    def test_build_cancelled_gains_the_mention(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_gate_clicker(_BUILD, "U0CLICK")
        text = _notifier(audience=registry)._render(
            _complete(event_type="build_cancelled", cancelled_by="rich", reason="superseded")
        )
        assert text.splitlines()[0] == (f"<@U0CLICK> [{_HHMM}] Pipeline FEAT-D9A6: build-cancelled")

    @pytest.mark.parametrize("event_type", ("build_started", "build_queued", "stage_complete"))
    def test_non_terminal_events_are_never_mentioned(self, event_type: str) -> None:
        """Progress is not a request. Mentioning it trains the reader to ignore it."""
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        registry.record_gate_clicker(_BUILD, "U0CLICK")
        notification = _complete(
            event_type=event_type,
            stage_label="plan-complete" if event_type == "stage_complete" else None,
            status="PASSED" if event_type == "stage_complete" else None,
        )
        text = _notifier(audience=registry, operator_ids=frozenset({"U0SOLE"}))._render(
            notification
        )
        assert "<@" not in text


# ---------------------------------------------------------------------------
# The finished-build sentence.
# ---------------------------------------------------------------------------


class TestBuildCompleteSpeaksPlainly:
    def test_the_whole_line_branch_and_repo(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        assert _notifier(audience=registry)._render(_complete()) == (
            f"<@U0RICH> [{_HHMM}] Pipeline FEAT-D9A6: build complete — 4 of 4 tasks "
            "passed the checker. The code is on branch autobuild/FEAT-D9A6 in api_test. "
            "Nothing merges on its own — the merge word is yours."
        )

    def test_branch_only_omits_the_repo_clause(self) -> None:
        text = _notifier()._render(_complete(repo=None))
        assert "The code is on branch autobuild/FEAT-D9A6. Nothing merges" in text
        assert " in " not in text.split("The code is on")[1]

    def test_unknown_branch_is_said_honestly_never_derived(self) -> None:
        """jarvis must NEVER invent a branch name — forge fills this field."""
        text = _notifier()._render(_complete(branch=None))
        assert "The code is on the build's branch in api_test." in text
        assert "FEAT-D9A6" not in text.split("The code is on")[1]

    def test_unknown_branch_and_repo(self) -> None:
        text = _notifier()._render(_complete(branch=None, repo=None))
        assert "The code is on the build's branch. Nothing merges on its own" in text

    def test_partial_failure_is_reported_honestly(self) -> None:
        text = _notifier()._render(_complete(tasks_completed=3, tasks_failed=1))
        assert "3 of 4 tasks passed the checker" in text
        assert "ready" not in text.lower()
        assert "PASSED" not in text

    def test_a_single_task_is_singular(self) -> None:
        text = _notifier()._render(_complete(tasks_completed=1, tasks_failed=0, tasks_total=1))
        assert "1 of 1 task passed the checker" in text

    def test_missing_counts_omit_the_clause_entirely(self) -> None:
        text = _notifier()._render(
            _complete(tasks_completed=None, tasks_failed=None, tasks_total=None)
        )
        assert "tasks passed" not in text
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-D9A6: build complete. The code is on branch "
            "autobuild/FEAT-D9A6 in api_test. Nothing merges on its own — "
            "the merge word is yours."
        )

    def test_the_merge_word_is_always_named(self) -> None:
        for overrides in ({}, {"branch": None}, {"repo": None}, {"tasks_total": None}):
            text = _notifier()._render(_complete(**overrides))
            assert text.endswith("Nothing merges on its own — the merge word is yours."), text

    def test_pr_url_and_summary_still_follow_on_their_own_lines(self) -> None:
        text = _notifier()._render(
            _complete(pr_url="https://example.invalid/pr/1", summary="one file changed")
        )
        lines = text.splitlines()
        assert lines[1] == "PR: https://example.invalid/pr/1"
        assert lines[2] == "Summary: one file changed"

    @pytest.mark.asyncio
    async def test_the_posted_message_carries_no_action_surface(self) -> None:
        """The merge card is the conductor's, and the conductor is parked."""
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        notifier = _notifier(audience=registry)
        client = AsyncMock()
        notifier._client = client

        await notifier.start()
        try:
            await notifier.notify(_complete())
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
        finally:
            await notifier.stop()

        kwargs = client.chat_postMessage.await_args.kwargs
        assert "blocks" not in kwargs
        assert kwargs["mrkdwn"] is False
        assert kwargs["text"].startswith("<@U0RICH> ")


# ---------------------------------------------------------------------------
# DDR-007 — never raise.
# ---------------------------------------------------------------------------


class TestMentionLookupNeverRaises:
    class _ExplodingRegistry:
        def planning_target(self, correlation_id: str | None) -> str | None:
            raise RuntimeError("registry is on fire")

        def gate_clicker(self, build_id: str | None) -> str | None:  # pragma: no cover
            raise RuntimeError("registry is on fire")

    def test_render_survives_a_throwing_registry(self) -> None:
        text = _notifier(audience=self._ExplodingRegistry())._render(_complete())  # type: ignore[arg-type]
        assert "<@" not in text
        assert "build complete" in text

    @pytest.mark.asyncio
    async def test_the_message_still_posts_unmentioned(self) -> None:
        notifier = _notifier(audience=self._ExplodingRegistry())  # type: ignore[arg-type]
        client = AsyncMock()
        notifier._client = client

        await notifier.start()
        try:
            await notifier.notify(_complete())
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
        finally:
            await notifier.stop()

        assert client.chat_postMessage.await_count == 1
        text = client.chat_postMessage.await_args.kwargs["text"]
        assert "<@" not in text
        assert "the merge word is yours" in text


# ---------------------------------------------------------------------------
# The two writers.
# ---------------------------------------------------------------------------


def _planning_envelope_bytes(*, correlation_id: str, target_user: str | None) -> bytes:
    from nats_core import EventType, MessageEnvelope
    from nats_core.events import NotificationPayload

    payload = NotificationPayload(
        message="Planning handoff ready",
        level="info",
        adapter="slack",
        correlation_id=correlation_id,
        target_user=target_user,
    )
    return (
        MessageEnvelope(
            source_id="forge",
            event_type=EventType("notification"),
            correlation_id=correlation_id,
            payload=payload.model_dump(mode="json"),
        )
        .model_dump_json()
        .encode("utf-8")
    )


class _FakeMsg:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.subject = "jarvis.notification.slack"
        self.metadata = SimpleNamespace(num_delivered=1)
        self.ack = AsyncMock()
        self.nak = AsyncMock()


class TestPlanningNotifierRecordsTheTarget:
    @pytest.mark.asyncio
    async def test_target_user_is_recorded_against_the_correlation(self) -> None:
        registry = BuildAudienceRegistry()
        consumer = pn.PlanningNotificationConsumer(
            MagicMock(), channel_id="C-PLAN", web_client=AsyncMock(), audience=registry
        )
        await consumer._handle(
            _FakeMsg(_planning_envelope_bytes(correlation_id=_CORR, target_user="U0RICH"))
        )
        assert registry.planning_target(_CORR) == "U0RICH"

    @pytest.mark.asyncio
    async def test_no_target_user_records_nothing(self) -> None:
        registry = BuildAudienceRegistry()
        consumer = pn.PlanningNotificationConsumer(
            MagicMock(), channel_id="C-PLAN", web_client=AsyncMock(), audience=registry
        )
        await consumer._handle(
            _FakeMsg(_planning_envelope_bytes(correlation_id=_CORR, target_user=None))
        )
        assert registry.planning_target(_CORR) is None

    @pytest.mark.asyncio
    async def test_a_throwing_registry_never_costs_the_notification(self) -> None:
        class Exploding:
            def record_planning_target(self, *_: Any) -> None:
                raise RuntimeError("registry is on fire")

        web = AsyncMock()
        consumer = pn.PlanningNotificationConsumer(
            MagicMock(),
            channel_id="C-PLAN",
            web_client=web,
            audience=Exploding(),  # type: ignore[arg-type]
        )
        msg = _FakeMsg(_planning_envelope_bytes(correlation_id=_CORR, target_user="U0RICH"))
        await consumer._handle(msg)
        assert web.chat_postMessage.await_count == 1
        msg.ack.assert_awaited_once()


class TestReplyHandlerRecordsTheClicker:
    @staticmethod
    def _click(user_id: str = "U0CLICK") -> dict[str, Any]:
        value = json.dumps(
            {
                "request_id": "apr-001",
                "build_id": _BUILD,
                "correlation_id": _CORR,
                "approval_subject": "agents.approval.forge.build-gate",
            }
        )
        return {
            "type": "block_actions",
            "user": {"id": user_id},
            "channel": {"id": "C123456"},
            "container": {"channel_id": "C123456", "message_ts": "1720.0001"},
            "message": {"blocks": []},
            "actions": [{"action_id": "forge_approve", "value": value}],
        }

    @pytest.mark.asyncio
    async def test_the_actual_clicker_is_recorded_against_the_build(self) -> None:
        registry = BuildAudienceRegistry()
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        handler = build_reply_handler(
            operator_ids=frozenset({"U0CLICK"}),
            publisher=publisher,
            web_client=AsyncMock(),
            audience=registry,
        )

        await handler.handle_block_actions(self._click())

        assert registry.gate_clicker(_BUILD) == "U0CLICK"
        # And it is the SAME id the decision published (never a config constant).
        assert publisher.publish.await_args.kwargs["payload"].decided_by == "U0CLICK"

    @pytest.mark.asyncio
    async def test_an_unauthorized_click_records_nobody(self) -> None:
        registry = BuildAudienceRegistry()
        publisher = MagicMock()
        publisher.publish = AsyncMock()
        handler = build_reply_handler(
            operator_ids=frozenset({"U0CLICK"}),
            publisher=publisher,
            web_client=AsyncMock(),
            audience=registry,
        )

        await handler.handle_block_actions(self._click(user_id="U0STRANGER"))

        assert registry.gate_clicker(_BUILD) is None

    @pytest.mark.asyncio
    async def test_a_throwing_registry_never_costs_the_tap(self) -> None:
        class Exploding:
            def record_gate_clicker(self, *_: Any) -> None:
                raise RuntimeError("registry is on fire")

        publisher = MagicMock()
        publisher.publish = AsyncMock()
        handler = build_reply_handler(
            operator_ids=frozenset({"U0CLICK"}),
            publisher=publisher,
            web_client=AsyncMock(),
            audience=Exploding(),  # type: ignore[arg-type]
        )

        await handler.handle_block_actions(self._click())

        publisher.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# The wire projection — the counts and the branch actually arrive.
# ---------------------------------------------------------------------------


class TestBuildCompletePayloadProjection:
    @staticmethod
    def _envelope(**payload_overrides: Any) -> bytes:
        payload: dict[str, Any] = {
            "feature_id": "FEAT-D9A6",
            "build_id": _BUILD,
            "repo": "api_test",
            "branch": "autobuild/FEAT-D9A6",
            "tasks_completed": 4,
            "tasks_failed": 0,
            "tasks_total": 4,
            "duration_seconds": 120,
            "summary": "four tasks, no failures",
        }
        payload.update(payload_overrides)
        return json.dumps(
            {
                "message_id": "11111111-1111-1111-1111-111111111111",
                "timestamp": "2026-08-15T12:02:00+00:00",
                "source_id": "forge",
                "event_type": "build_complete",
                "correlation_id": _CORR,
                "payload": payload,
            }
        ).encode("utf-8")

    @staticmethod
    def _subscriber(sink: Any) -> ForgeNotificationsSubscriber:
        subscriber = ForgeNotificationsSubscriber(
            nats_client=MagicMock(),
            routing_history_writer=MagicMock(),
        )
        subscriber.bind_session_manager(MagicMock())
        subscriber.bind_notification_sink(sink)
        return subscriber

    @pytest.mark.asyncio
    async def test_counts_branch_and_repo_reach_the_sink(self) -> None:
        seen: list[ForgeNotification] = []

        class Sink:
            async def notify(self, notification: ForgeNotification) -> None:
                seen.append(notification)

        subscriber = self._subscriber(Sink())
        msg = MagicMock()
        msg.data = self._envelope()
        await subscriber._handle_message(msg)

        assert len(seen) == 1
        assert seen[0].branch == "autobuild/FEAT-D9A6"
        assert seen[0].repo == "api_test"
        assert (seen[0].tasks_completed, seen[0].tasks_failed, seen[0].tasks_total) == (4, 0, 4)

    @pytest.mark.asyncio
    async def test_blank_branch_and_repo_normalise_to_none_not_a_dropped_event(self) -> None:
        """An empty string from forge must not trip min_length and lose the message."""
        seen: list[ForgeNotification] = []

        class Sink:
            async def notify(self, notification: ForgeNotification) -> None:
                seen.append(notification)

        subscriber = self._subscriber(Sink())
        msg = MagicMock()
        msg.data = self._envelope(branch="", repo="   ")
        await subscriber._handle_message(msg)

        assert len(seen) == 1
        assert seen[0].branch is None
        assert seen[0].repo is None


# ---------------------------------------------------------------------------
# The whole path, in one process — planning mention in, build mention out.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_planning_target_learned_on_one_subscriber_mentions_on_the_other() -> None:
    """jarvis-serve-nats runs both notifiers in ONE process — this is the seam."""
    registry = BuildAudienceRegistry()

    consumer = pn.PlanningNotificationConsumer(
        MagicMock(), channel_id="C-PLAN", web_client=AsyncMock(), audience=registry
    )
    await consumer._handle(
        _FakeMsg(_planning_envelope_bytes(correlation_id=_CORR, target_user="U0RICH"))
    )

    notifier = _notifier(audience=registry)
    client = AsyncMock()
    notifier._client = client

    await notifier.start()
    try:
        await notifier.notify(_complete())
        for _ in range(200):
            if client.chat_postMessage.await_count:
                break
            await asyncio.sleep(0.01)
    finally:
        await notifier.stop()

    assert client.chat_postMessage.await_args.kwargs["text"] == (
        f"<@U0RICH> [{_HHMM}] Pipeline FEAT-D9A6: build complete — 4 of 4 tasks "
        "passed the checker. The code is on branch autobuild/FEAT-D9A6 in api_test. "
        "Nothing merges on its own — the merge word is yours."
    )
