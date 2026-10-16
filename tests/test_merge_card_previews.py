"""Merge cards Forge describes: kept true in Slack (previews design, 16 October 2026).

The Jarvis half of the previews design of 16 October 2026 (preview expiry, Rebuild, slots):

* the ``merge_card`` block on a build-paused payload is typed through
  nats-core's ``MergeCard``; a bad block is dropped and the card is handled
  the old way;
* the durable card file: written atomically, read back after a restart,
  pruned 24 hours after a decided description or after 15 days;
* applying descriptions: an older revision is ignored, the same revision is
  applied when the drawing differs, a failed ``chat.update`` is tried again
  on the next description, and an update for a different offer or candidate
  is refused;
* a card Jarvis has no record of is posted as a replacement whose buttons
  answer the original offer (no new approval request);
* the click latch: a refused Approve followed by Reject reaches Forge;
* buttons keep the synthetic ``merge-FEAT-…`` id, so a finished build's
  first and replacement cards can both be tapped;
* the Rebuild preview press sends ``defer`` / ``rebuild-preview`` and shows
  "Rebuilding the preview…" with Reject only;
* the wording for each status, "Approved by …" / "Rejected by …" included.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from nats_core.events import MergeCard
from structlog.testing import capture_logs

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import merge_cards as merge_cards_module
from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
)
from jarvis.infrastructure.merge_cards import (
    DECIDED_KEEP_SECONDS,
    MAX_AGE_SECONDS,
    MergeCardEntry,
    MergeCardStore,
    content_digest,
    resolve_merge_card_path,
)
from jarvis.infrastructure.slack_notifier import (
    ACTION_REBUILD_PREVIEW,
    REBUILD_PREVIEW_NOTES,
    SlackNotifier,
    build_merge_card_message,
)
from jarvis.infrastructure.slack_reply import build_reply_handler
from jarvis.infrastructure.terminal_builds import TerminalBuildRegistry

_HOST_APP = "preview.example.test"
_HOST_EVIDENCE = "evidence.example.test"
_HOSTS = frozenset({_HOST_APP, _HOST_EVIDENCE})
_APP_URL = f"https://{_HOST_APP}:8950/?preview=tok-secret-123"
_REPORT_URL = f"https://{_HOST_EVIDENCE}/factory-evidence/p/f/sha/run-1/report/index.html"
_MEDIA_URL = f"https://{_HOST_EVIDENCE}/factory-evidence/p/f/sha/run-1/journey.webm"

_FEATURE = "FEAT-PV16"
_SYNTHETIC = f"merge-{_FEATURE}"
_REAL_BUILD = "build-FEAT-PV16-20261016"
_REQUEST = f"merge-{_REAL_BUILD}"
_SUBJECT = f"agents.approval.forge.merge-{_FEATURE}"
_CORR = "corr-pv16"
_CANDIDATE = "a" * 40
_OPERATOR = "U0OPERATOR"
_CHANNEL = "C123456"


@pytest.fixture(autouse=True)
def _utc_local_time() -> Iterator[None]:
    """Pin the host's local zone so the rendered times are deterministic."""
    old = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = old
        time.tzset()


def _evidence(state: str = "ready", **overrides: Any) -> dict[str, Any]:
    created = datetime.now(UTC) - timedelta(hours=1)
    data: dict[str, Any] = {
        "state": state,
        "app_url": _APP_URL if state == "ready" else None,
        "report_url": _REPORT_URL,
        "media_urls": [_MEDIA_URL],
        "diagnostics_url": None,
        "failure_reason": None if state == "ready" else "the preview's time ran out",
        "candidate_sha": _CANDIDATE,
        "candidate_tree": "b" * 40,
        "preview_tree": "c" * 40,
        "run_id": "run-1",
        "created_at": created.isoformat(),
        "app_expires_at": (created + timedelta(hours=24)).isoformat(),
        "evidence_expires_at": (created + timedelta(days=14)).isoformat(),
        "outcome": {"passed": 3, "failed": 0, "skipped": 1, "flaky": None},
    }
    data.update(overrides)
    return data


_STATUS_TEXT = {
    "ready": None,
    "rebuilding": "Rebuilding the preview for the same build.",
    "ended": "Preview expired at 14:07 UTC.",
    "failed": "Preview not started: both preview slots are in use by FEAT-A and FEAT-B.",
    "decided": "Approved by rich.",
}


def _card(status: str = "ready", revision: int = 1, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "request_id": _REQUEST,
        "build_id": _REAL_BUILD,
        "correlation_id": _CORR,
        "approval_subject": _SUBJECT,
        "candidate_sha": _CANDIDATE,
        "status": status,
        "status_text": _STATUS_TEXT[status],
        "rebuild_offered": status in ("ended", "failed"),
        "revision": revision,
        "words": "Every task passed its checks. The branch joins main cleanly.",
    }
    if status == "decided":
        data["decision"] = "approve"
        data["decided_by"] = _OPERATOR
    data.update(overrides)
    return data


_EVIDENCE_STATE = {
    "ready": "ready",
    "rebuilding": "ended",
    "ended": "ended",
    "failed": "failed",
    "decided": "ready",
}


def _notification(
    status: str = "ready",
    revision: int = 1,
    *,
    evidence: dict[str, Any] | None | bool = True,
    **card_overrides: Any,
) -> ForgeNotification:
    if evidence is True:
        evidence = _evidence(_EVIDENCE_STATE[status])
    return ForgeNotification(
        event_type="build_paused",
        correlation_id=_CORR,
        feature_id=_FEATURE,
        completed_at=datetime.now(UTC),
        build_id=_SYNTHETIC,
        coach_score=None,
        rationale="The old card body.",
        approval_subject=_SUBJECT,
        stage_label="the merge-ready checkpoint",
        review_evidence=evidence or None,  # type: ignore[arg-type]
        merge_card=_card(status, revision, **card_overrides),  # type: ignore[arg-type]
    )


def _make_notifier(
    store: MergeCardStore | None = None,
) -> tuple[SlackNotifier, AsyncMock, MergeCardStore]:
    store = store if store is not None else MergeCardStore(None)
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        notifier = SlackNotifier(
            bot_token="xoxb-test",
            channel_id=_CHANNEL,
            evidence_link_hosts=_HOSTS,
            merge_cards=store,
        )
    posted = iter(f"1720.{n:04d}" for n in range(1, 100))
    mock_client.chat_postMessage.side_effect = lambda **_: {"ok": True, "ts": next(posted)}
    mock_client.chat_update.return_value = {"ok": True}
    return notifier, mock_client, store


def _handler(
    store: MergeCardStore | None,
    terminal_registry: TerminalBuildRegistry | None = None,
) -> tuple[Any, MagicMock, AsyncMock]:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web_client = AsyncMock()
    web_client.chat_update.return_value = {"ok": True}
    handler = build_reply_handler(
        operator_ids=frozenset({_OPERATOR}),
        publisher=publisher,
        web_client=web_client,
        terminal_registry=terminal_registry,
        merge_cards=store,
    )
    return handler, publisher, web_client


def _posted_blocks(client: AsyncMock, index: int = -1) -> list[dict[str, Any]]:
    return client.chat_postMessage.await_args_list[index].kwargs["blocks"]


def _decision_ids(blocks: list[dict[str, Any]]) -> list[str]:
    return [
        e["action_id"]
        for b in blocks
        if b.get("type") == "actions" and str(b.get("block_id")).startswith("forge_approval")
        for e in b["elements"]
    ]


def _link_ids(blocks: list[dict[str, Any]]) -> list[str]:
    return [
        e["action_id"]
        for b in blocks
        if b.get("type") == "actions" and b.get("block_id") == "forge_preview_links"
        for e in b["elements"]
    ]


def _texts(blocks: list[dict[str, Any]]) -> str:
    return "\n".join(b["text"]["text"] for b in blocks if b.get("type") == "section")


def _click(blocks: list[dict[str, Any]], action_id: str, *, ts: str) -> dict[str, Any]:
    block = next(
        b
        for b in blocks
        if b.get("type") == "actions" and any(e["action_id"] == action_id for e in b["elements"])
    )
    element = next(e for e in block["elements"] if e["action_id"] == action_id)
    return {
        "type": "block_actions",
        "user": {"id": _OPERATOR},
        "container": {"type": "message", "channel_id": _CHANNEL, "message_ts": ts},
        "channel": {"id": _CHANNEL},
        "message": {"blocks": blocks},
        "actions": [
            {
                "action_id": action_id,
                "block_id": block["block_id"],
                "type": "button",
                "value": element["value"],
            }
        ],
    }


def _published(publisher: MagicMock) -> list[tuple[str, Any]]:
    return [(c.kwargs["subject"], c.kwargs["payload"]) for c in publisher.publish.await_args_list]


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def _subscriber() -> tuple[ForgeNotificationsSubscriber, AsyncMock]:
    nats_client = Mock()
    nats_client.js = Mock()
    writer = Mock()
    writer.append_build_queue_event = AsyncMock()
    subscriber = ForgeNotificationsSubscriber(
        nats_client=nats_client, routing_history_writer=writer
    )
    sink = MagicMock()
    sink.notify = AsyncMock()
    subscriber.bind_notification_sink(sink)
    return subscriber, sink.notify


def _pause_msg(payload_extra: dict[str, Any]) -> Mock:
    payload = {
        "feature_id": _FEATURE,
        "build_id": _SYNTHETIC,
        "correlation_id": _CORR,
        "stage_label": "the merge-ready checkpoint",
        "gate_mode": "MANDATORY_HUMAN_APPROVAL",
        "coach_score": None,
        "rationale": "Ready to merge",
        "approval_subject": _SUBJECT,
        "paused_at": "2026-10-16T14:00:00+00:00",
        **payload_extra,
    }
    envelope = {
        "event_type": "build_paused",
        "source_id": "forge",
        "correlation_id": _CORR,
        "timestamp": "2026-10-16T14:00:00Z",
        "payload": payload,
    }
    msg = Mock()
    msg.data = json.dumps(envelope).encode()
    return msg


class TestProjection:
    @pytest.mark.asyncio
    async def test_merge_card_block_reaches_the_sink_typed(self) -> None:
        subscriber, notify = _subscriber()
        await subscriber._handle_message(
            _pause_msg({"merge_card": _card("ended", 4), "review_evidence": _evidence("ended")})
        )
        notification = notify.await_args.args[0]
        assert isinstance(notification.merge_card, MergeCard)
        assert notification.merge_card.revision == 4
        assert notification.merge_card.build_id == _REAL_BUILD
        assert notification.build_id == _SYNTHETIC
        assert notification.review_evidence.state == "ended"

    @pytest.mark.asyncio
    async def test_older_payload_without_the_block_projects_none(self) -> None:
        subscriber, notify = _subscriber()
        await subscriber._handle_message(_pause_msg({}))
        assert notify.await_args.args[0].merge_card is None

    @pytest.mark.asyncio
    async def test_bad_block_is_dropped_and_the_card_still_goes(self) -> None:
        from jarvis.infrastructure import forge_notifications

        subscriber, notify = _subscriber()
        # The module logger is patched rather than captured: an earlier test
        # in a full run can leave structlog caching its loggers, which
        # capture_logs then cannot see.
        with patch.object(forge_notifications, "logger") as logger:
            await subscriber._handle_message(
                _pause_msg({"merge_card": _card("ready", 1, candidate_sha="not-a-sha")})
            )
        assert notify.await_args.args[0].merge_card is None
        dropped = [
            c
            for c in logger.warning.call_args_list
            if c.args and c.args[0] == "forge_notification_merge_card_dropped"
        ]
        assert dropped and dropped[0].kwargs["errors"][0]["loc"] == "candidate_sha"


# ---------------------------------------------------------------------------
# The durable card file
# ---------------------------------------------------------------------------


def _entry(**overrides: Any) -> MergeCardEntry:
    data: dict[str, Any] = {
        "request_id": _REQUEST,
        "build_id": _REAL_BUILD,
        "correlation_id": _CORR,
        "candidate_sha": _CANDIDATE,
        "channel": _CHANNEL,
        "ts": "1720.0001",
        "revision": 3,
        "displayed": "d" * 64,
        "created_at": time.time(),
    }
    data.update(overrides)
    return MergeCardEntry(**data)


class TestMergeCardStore:
    def test_survives_a_restart(self, tmp_path: Path) -> None:
        path = tmp_path / "state" / "merge-cards.json"
        MergeCardStore(path).put(_entry())
        reloaded = MergeCardStore(path).get(_REQUEST)
        assert reloaded == _entry(created_at=reloaded.created_at)
        document = json.loads(path.read_text())
        assert document["version"] == 1
        assert set(document["cards"]) == {_REQUEST}
        # Written atomically: no temporary file is left beside it.
        assert [p.name for p in path.parent.iterdir()] == ["merge-cards.json"]

    def test_unreadable_file_starts_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "merge-cards.json"
        path.write_text("{not json")
        with capture_logs() as logs:
            store = MergeCardStore(path)
        assert not store.knows(_REQUEST)
        assert any(e["event"] == "merge_card_store_unreadable" for e in logs)

    def test_unwritable_path_is_logged_never_raised(self, tmp_path: Path) -> None:
        blocker = tmp_path / "a-file"
        blocker.write_text("")
        store = MergeCardStore(blocker / "merge-cards.json")
        with capture_logs() as logs:
            store.put(_entry())
        assert store.knows(_REQUEST)
        assert any(e["event"] == "merge_card_store_write_failed" for e in logs)

    def test_pruned_a_day_after_decided_or_after_fifteen_days(self, tmp_path: Path) -> None:
        path = tmp_path / "merge-cards.json"
        now = 2_000_000_000.0
        with patch.object(merge_cards_module, "_wall_now", lambda: now):
            store = MergeCardStore(path)
            store.put(
                _entry(
                    request_id="decided-old",
                    created_at=now - 7200,
                    decided_at=now - DECIDED_KEEP_SECONDS,
                )
            )
            store.put(_entry(request_id="decided-new", created_at=now - 7200, decided_at=now - 60))
            store.put(_entry(request_id="too-old", created_at=now - MAX_AGE_SECONDS))
            store.put(_entry(request_id="open", created_at=now - 3600))
            assert not store.knows("decided-old")
            assert not store.knows("too-old")
            assert store.knows("decided-new") and store.knows("open")
        with patch.object(merge_cards_module, "_wall_now", lambda: now + DECIDED_KEEP_SECONDS):
            assert not MergeCardStore(path).knows("decided-new")

    def test_where_the_file_goes(self, tmp_path: Path) -> None:
        explicit = JarvisConfig(slack_merge_card_path=tmp_path / "cards.json")
        assert resolve_merge_card_path(explicit) == tmp_path / "cards.json"
        beside = JarvisConfig(slack_heartbeat_path=Path("/var/lib/jarvis/slack-heartbeat.json"))
        assert resolve_merge_card_path(beside) == Path("/var/lib/jarvis/merge-cards.json")
        assert resolve_merge_card_path(JarvisConfig()) is None


# ---------------------------------------------------------------------------
# The drawing, by status
# ---------------------------------------------------------------------------


class TestDrawing:
    def _draw(self, notification: ForgeNotification) -> tuple[list[dict[str, Any]], str]:
        value = json.dumps({"request_id": _REQUEST, "build_id": _SYNTHETIC})
        return build_merge_card_message(notification, value, link_hosts=_HOSTS)

    def test_ready(self) -> None:
        blocks, text = self._draw(_notification("ready"))
        assert _decision_ids(blocks) == ["forge_approve", "forge_reject"]
        assert _link_ids(blocks) == [
            "forge_preview_open",
            "forge_preview_report",
            "forge_preview_media",
        ]
        assert "Every task passed its checks." in _texts(blocks)
        assert "The old card body." not in text
        assert "Preview ready." in _texts(blocks)
        block_id = next(
            b["block_id"]
            for b in blocks
            if b.get("type") == "actions" and b["block_id"].startswith("forge_approval")
        )
        assert block_id.startswith("forge_approval.preview.ready.")

    def test_rebuilding_offers_reject_only(self) -> None:
        blocks, _ = self._draw(_notification("rebuilding", evidence=None))
        assert _decision_ids(blocks) == ["forge_reject"]
        assert "Rebuilding the preview for the same build." in _texts(blocks)

    def test_ended_keeps_report_and_video_and_offers_rebuild(self) -> None:
        blocks, _ = self._draw(_notification("ended"))
        assert _decision_ids(blocks) == [ACTION_REBUILD_PREVIEW, "forge_reject"]
        assert _link_ids(blocks) == ["forge_preview_report", "forge_preview_media"]
        assert "Preview expired at 14:07 UTC." in _texts(blocks)

    def test_ended_without_forge_words_says_when(self) -> None:
        blocks, _ = self._draw(_notification("ended", status_text=None))
        assert "Preview stopped: the preview's time ran out" in _texts(blocks)

    def test_failed_slots_busy_without_evidence(self) -> None:
        blocks, _ = self._draw(_notification("failed", evidence=None))
        assert _decision_ids(blocks) == [ACTION_REBUILD_PREVIEW, "forge_reject"]
        assert "both preview slots are in use" in _texts(blocks)

    def test_rebuilt_three_times_offers_reject_only(self) -> None:
        blocks, _ = self._draw(_notification("ended", rebuild_offered=False))
        assert _decision_ids(blocks) == ["forge_reject"]

    @pytest.mark.parametrize(
        ("decision", "verb"), [("approve", "Approved"), ("reject", "Rejected")]
    )
    def test_decided_says_who_and_has_no_buttons(self, decision: str, verb: str) -> None:
        blocks, text = self._draw(_notification("decided", decision=decision))
        assert _decision_ids(blocks) == []
        assert _link_ids(blocks) == []
        mention = [
            b for b in blocks if b.get("type") == "section" and b["text"]["type"] == "mrkdwn"
        ]
        assert [b["text"]["text"] for b in mention] == [f"{verb} by <@{_OPERATOR}>."]
        assert f"{verb} by <@{_OPERATOR}>." in text
        assert blocks[0]["text"]["text"] == "Ready to merge and deploy"

    def test_decided_by_a_name_stays_plain_text(self) -> None:
        blocks, _ = self._draw(_notification("decided", decided_by="rich <!here>"))
        assert not [
            b for b in blocks if b.get("type") == "section" and b["text"]["type"] == "mrkdwn"
        ]
        assert "Approved by rich <!here>." in _texts(blocks)

    def test_buttons_carry_the_synthetic_card_id(self) -> None:
        notifier, client, _ = _make_notifier()
        asyncio.run(notifier._deliver_merge_card(_notification("ended")))
        values = {
            e["value"]
            for b in _posted_blocks(client)
            if b.get("type") == "actions"
            for e in b["elements"]
            if "value" in e
        }
        assert len(values) == 1
        assert json.loads(values.pop()) == {
            "request_id": _REQUEST,
            "build_id": _SYNTHETIC,
            "correlation_id": _CORR,
            "approval_subject": _SUBJECT,
        }


# ---------------------------------------------------------------------------
# Applying descriptions
# ---------------------------------------------------------------------------


class TestApplyingDescriptions:
    @pytest.mark.asyncio
    async def test_first_description_posts_and_records_the_card(self, tmp_path: Path) -> None:
        notifier, client, _store = _make_notifier(MergeCardStore(tmp_path / "cards.json"))
        await notifier._deliver_merge_card(_notification("ready", 1))
        client.chat_postMessage.assert_awaited_once()
        assert client.chat_postMessage.await_args.kwargs["channel"] == _CHANNEL
        entry = MergeCardStore(tmp_path / "cards.json").get(_REQUEST)
        assert entry is not None
        assert (entry.ts, entry.revision, entry.build_id) == ("1720.0001", 1, _REAL_BUILD)

    @pytest.mark.asyncio
    async def test_same_description_twice_changes_nothing(self) -> None:
        notifier, client, _ = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(_notification("ready", 1))
        client.chat_postMessage.assert_awaited_once()
        client.chat_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_newer_description_edits_the_same_message(self) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(_notification("ended", 2))
        client.chat_postMessage.assert_awaited_once()
        client.chat_update.assert_awaited_once()
        kwargs = client.chat_update.await_args.kwargs
        assert (kwargs["channel"], kwargs["ts"]) == (_CHANNEL, "1720.0001")
        assert _decision_ids(kwargs["blocks"]) == [ACTION_REBUILD_PREVIEW, "forge_reject"]
        assert store.get(_REQUEST).revision == 2

    @pytest.mark.asyncio
    async def test_stale_ready_after_ended_is_ignored(self) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(_notification("ended", 3))
        client.chat_update.reset_mock()
        with capture_logs() as logs:
            await notifier._deliver_merge_card(_notification("ready", 2))
        client.chat_update.assert_not_awaited()
        assert store.get(_REQUEST).revision == 3
        assert any(e["event"] == "slack_merge_card_stale_ignored" for e in logs)

    @pytest.mark.asyncio
    async def test_same_revision_with_a_different_drawing_is_applied(self) -> None:
        """Jarvis's own "Rebuilding…" goes back to the truth on the next sweep."""
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ended", 5))
        ended_blocks = _posted_blocks(client)
        handler, publisher, _web_client = _handler(store)
        await handler.handle_block_actions(
            _click(ended_blocks, ACTION_REBUILD_PREVIEW, ts="1720.0001")
        )
        publisher.publish.assert_awaited_once()

        # The press was lost: Forge's next sweep describes the same revision.
        await notifier._deliver_merge_card(_notification("ended", 5))
        client.chat_update.assert_awaited_once()
        restored = client.chat_update.await_args.kwargs["blocks"]
        assert _decision_ids(restored) == [ACTION_REBUILD_PREVIEW, "forge_reject"]
        # And once it shows the truth again, a further sweep changes nothing.
        await notifier._deliver_merge_card(_notification("ended", 5))
        client.chat_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_edit_is_tried_again_on_the_next_description(self) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        posted_digest = store.get(_REQUEST).displayed
        client.chat_update.side_effect = RuntimeError("slack is down")
        with capture_logs() as logs:
            await notifier._deliver_merge_card(_notification("ended", 2))
        assert any(e["event"] == "slack_merge_card_update_failed" for e in logs)
        assert store.get(_REQUEST).displayed == posted_digest

        client.chat_update.side_effect = None
        await notifier._deliver_merge_card(_notification("ended", 2))
        assert client.chat_update.await_count == 2
        assert store.get(_REQUEST).displayed != posted_digest
        await notifier._deliver_merge_card(_notification("ended", 2))
        assert client.chat_update.await_count == 2

    @pytest.mark.asyncio
    async def test_a_message_gone_from_slack_is_replaced(self) -> None:
        from slack_sdk.errors import SlackApiError

        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        client.chat_update.side_effect = SlackApiError(
            "gone", {"ok": False, "error": "message_not_found"}
        )
        await notifier._deliver_merge_card(_notification("ended", 2))
        assert client.chat_postMessage.await_count == 2
        assert store.get(_REQUEST).ts == "1720.0002"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "override",
        [{"build_id": "build-FEAT-PV16-other"}, {"correlation_id": "corr-other"}],
    )
    async def test_description_for_another_offer_is_refused(self, override: dict[str, Any]) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        with capture_logs() as logs:
            await notifier._deliver_merge_card(_notification("ended", 2, **override))
        client.chat_update.assert_not_awaited()
        assert store.get(_REQUEST).revision == 1
        assert any(e["event"] == "slack_merge_card_refused" for e in logs)

    @pytest.mark.asyncio
    async def test_a_different_candidate_commit_is_refused(self) -> None:
        notifier, client, _ = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        with capture_logs() as logs:
            await notifier._deliver_merge_card(
                _notification("ended", 2, evidence=_evidence("ended", candidate_sha="e" * 40))
            )
            await notifier._deliver_merge_card(
                _notification("ended", 2, evidence=None, candidate_sha="f" * 40)
            )
        client.chat_update.assert_not_awaited()
        refused = [e for e in logs if e["event"] == "slack_merge_card_refused"]
        assert len(refused) == 2

    @pytest.mark.asyncio
    async def test_two_offers_for_one_feature_and_commit_stay_separate(self) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(
            _notification(
                "ready",
                1,
                request_id="merge-build-FEAT-PV16-second",
                build_id="build-FEAT-PV16-second",
            )
        )
        assert client.chat_postMessage.await_count == 2
        assert store.get(_REQUEST).ts == "1720.0001"
        assert store.get("merge-build-FEAT-PV16-second").ts == "1720.0002"

    @pytest.mark.asyncio
    async def test_decided_card_with_no_record_is_not_reposted(self) -> None:
        notifier, client, _ = _make_notifier()
        await notifier._deliver_merge_card(_notification("decided", 7))
        client.chat_postMessage.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_late_description_never_reopens_a_decided_card(self) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(_notification("decided", 3))
        assert store.get(_REQUEST).decided_at is not None
        client.chat_update.reset_mock()
        await notifier._deliver_merge_card(_notification("ready", 2))
        client.chat_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_an_update_waits_for_a_click_on_the_card(self) -> None:
        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        async with store.lock:
            task = asyncio.create_task(notifier._deliver_merge_card(_notification("ended", 2)))
            await asyncio.sleep(0.01)
            client.chat_update.assert_not_awaited()
        await task
        client.chat_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_merge_cards_skip_the_five_minute_filter(self) -> None:
        notifier, _, _ = _make_notifier()
        notifier._started = True
        await notifier.notify(_notification("ready", 1))
        await notifier.notify(_notification("ready", 1))
        assert notifier._queue.qsize() == 2

    @pytest.mark.asyncio
    async def test_the_worker_routes_merge_cards(self) -> None:
        notifier, client, store = _make_notifier()
        with patch("jarvis.infrastructure.slack_notifier._WORKER_PACING_DELAY", 0):
            await notifier.start()
            await notifier.notify(_notification("ready", 1))
            for _ in range(50):
                if store.knows(_REQUEST):
                    break
                await asyncio.sleep(0.01)
            await notifier.stop()
        assert store.knows(_REQUEST)
        assert _decision_ids(_posted_blocks(client)) == ["forge_approve", "forge_reject"]


# ---------------------------------------------------------------------------
# Restart, replacement cards and clicks
# ---------------------------------------------------------------------------


class TestRestartAndReplacement:
    @pytest.mark.asyncio
    async def test_after_a_restart_the_file_finds_the_same_message(self, tmp_path: Path) -> None:
        path = tmp_path / "merge-cards.json"
        first, first_client, _ = _make_notifier(MergeCardStore(path))
        await first._deliver_merge_card(_notification("ready", 1))
        first_client.chat_postMessage.assert_awaited_once()

        # A new process: memory empty, only the file holds the card.
        second, client, _store = _make_notifier(MergeCardStore(path))
        await second._deliver_merge_card(_notification("ended", 2))
        client.chat_postMessage.assert_not_awaited()
        client.chat_update.assert_awaited_once()
        assert client.chat_update.await_args.kwargs["ts"] == "1720.0001"

    @pytest.mark.asyncio
    async def test_missing_card_is_replaced_with_buttons_for_the_original_offer(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        # Forge's sweep describes a card this Jarvis has no record of.
        await notifier._deliver_merge_card(_notification("ready", 6))
        client.chat_postMessage.assert_awaited_once()
        handler, publisher, _ = _handler(store)
        await handler.handle_block_actions(
            _click(_posted_blocks(client), "forge_approve", ts="1720.0001")
        )
        [(subject, payload)] = _published(publisher)
        # Answers the ORIGINAL offer: its request id on its own reply subject.
        assert subject == f"{_SUBJECT}.response"
        assert (payload.request_id, payload.decision) == (_REQUEST, "approve")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("which", ["first", "replacement"])
    @pytest.mark.parametrize(
        ("status", "action_id", "decision"),
        [
            ("ready", "forge_approve", "approve"),
            ("ready", "forge_reject", "reject"),
            ("ended", ACTION_REBUILD_PREVIEW, "defer"),
        ],
    )
    async def test_a_finished_builds_cards_can_be_tapped(
        self, which: str, status: str, action_id: str, decision: str
    ) -> None:
        terminal = TerminalBuildRegistry()
        # Every merge card belongs to a finished build.
        terminal.record(_REAL_BUILD, terminal_state="build_complete", at=datetime.now(UTC), by=None)
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification(status, 1))
        if which == "replacement":
            # Its message is gone (deleted in Slack): only the reference goes.
            store.clear_message(_REQUEST)
            await notifier._deliver_merge_card(_notification(status, 2))
        ts = store.get(_REQUEST).ts
        handler, publisher, _ = _handler(store, terminal_registry=terminal)
        await handler.handle_block_actions(_click(_posted_blocks(client), action_id, ts=ts))
        [(_, payload)] = _published(publisher)
        assert (payload.request_id, payload.decision) == (_REQUEST, decision)


# ---------------------------------------------------------------------------
# The click latch and the Rebuild press
# ---------------------------------------------------------------------------


class TestClicks:
    @pytest.mark.asyncio
    async def test_refused_approve_then_reject_reaches_forge(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ready", 1))
        ready = _posted_blocks(client)
        handler, publisher, _web_client = _handler(store)

        await handler.handle_block_actions(_click(ready, "forge_approve", ts="1720.0001"))
        # Before Forge answers, a second tap is still a duplicate.
        await handler.handle_block_actions(_click(ready, "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["approve"]

        # An older or same-revision description never clears the latch.
        await notifier._deliver_merge_card(_notification("ready", 1))
        await handler.handle_block_actions(_click(ready, "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["approve"]

        # Forge refuses the Approve: the counter moves on, the card is undecided.
        await notifier._deliver_merge_card(_notification("ended", 2))
        restored = client.chat_update.await_args.kwargs["blocks"]
        assert _decision_ids(restored) == [ACTION_REBUILD_PREVIEW, "forge_reject"]
        await handler.handle_block_actions(_click(restored, "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["approve", "reject"]

    @pytest.mark.asyncio
    async def test_decided_description_keeps_the_latch(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ready", 1))
        ready = _posted_blocks(client)
        handler, publisher, _ = _handler(store)
        await handler.handle_block_actions(_click(ready, "forge_approve", ts="1720.0001"))
        await notifier._deliver_merge_card(_notification("decided", 2))
        assert "Approved by" in json.dumps(client.chat_update.await_args.kwargs["blocks"])
        await handler.handle_block_actions(_click(ready, "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["approve"]

    @pytest.mark.asyncio
    async def test_click_messages_count_as_what_the_card_shows(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ready", 1))
        handler, _, web_client = _handler(store)
        await handler.handle_block_actions(
            _click(_posted_blocks(client), "forge_approve", ts="1720.0001")
        )
        last = web_client.chat_update.await_args.kwargs
        assert store.get(_REQUEST).displayed == content_digest(last["blocks"], last["text"])

    @pytest.mark.asyncio
    async def test_rebuild_sends_defer_and_shows_rebuilding_with_reject_only(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ended", 3))
        handler, publisher, web_client = _handler(store)
        await handler.handle_block_actions(
            _click(_posted_blocks(client), ACTION_REBUILD_PREVIEW, ts="1720.0001")
        )
        [(subject, payload)] = _published(publisher)
        assert subject == f"{_SUBJECT}.response"
        assert (payload.request_id, payload.decision, payload.notes) == (
            _REQUEST,
            "defer",
            REBUILD_PREVIEW_NOTES,
        )
        assert payload.decided_by == _OPERATOR
        assert publisher.publish.await_args.kwargs["correlation_id"] == _CORR

        shown = web_client.chat_update.await_args.kwargs
        assert shown["text"] == "Rebuilding the preview…"
        assert "Rebuilding the preview…" in _texts(shown["blocks"])
        assert _decision_ids(shown["blocks"]) == ["forge_reject"]
        # The report and video stay while the preview is rebuilt.
        assert _link_ids(shown["blocks"]) == ["forge_preview_report", "forge_preview_media"]
        assert store.get(_REQUEST).displayed == content_digest(shown["blocks"], shown["text"])

        # Not a decision: Reject still goes through afterwards.
        assert not store.is_latched(_REQUEST)
        await handler.handle_block_actions(_click(shown["blocks"], "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["defer", "reject"]

    @pytest.mark.asyncio
    async def test_rebuild_publish_failure_restores_the_card(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ended", 3))
        ended = _posted_blocks(client)
        handler, publisher, web_client = _handler(store)
        publisher.publish.side_effect = RuntimeError("bus down")
        await handler.handle_block_actions(_click(ended, ACTION_REBUILD_PREVIEW, ts="1720.0001"))
        assert web_client.chat_update.await_args.kwargs["blocks"] == ended

    @pytest.mark.asyncio
    async def test_rebuild_after_a_recorded_decision_is_dropped(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ended", 3))
        ended = _posted_blocks(client)
        handler, publisher, _ = _handler(store)
        await handler.handle_block_actions(_click(ended, "forge_reject", ts="1720.0001"))
        await handler.handle_block_actions(_click(ended, ACTION_REBUILD_PREVIEW, ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["reject"]

    @pytest.mark.asyncio
    async def test_cards_without_a_record_keep_todays_latch(self) -> None:
        handler, publisher, _ = _handler(MergeCardStore(None))
        notifier, client, _ = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        blocks = _posted_blocks(client)
        await handler.handle_block_actions(_click(blocks, "forge_approve", ts="1720.0001"))
        await handler.handle_block_actions(_click(blocks, "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["approve"]
        assert _REQUEST in handler._decided_request_ids


class TestWiring:
    def test_handler_click_lock_is_the_store_lock(self) -> None:
        store = MergeCardStore(None)
        handler, _, _ = _handler(store)
        assert handler._decision_lock is store.lock

    def test_sink_factory_passes_the_store(self) -> None:
        from pydantic import SecretStr

        from jarvis.infrastructure.slack_notifier import create_slack_sink

        store = MergeCardStore(None)
        config = JarvisConfig(slack_bot_token=SecretStr("xoxb-test"), slack_channel_id=_CHANNEL)
        sink = create_slack_sink(config, merge_cards=store)
        assert isinstance(sink, SlackNotifier)
        assert sink._merge_cards is store


class TestOlderCardWithAnEndedPreview:
    """An unreadable block leaves the older card path; an ended preview is not approvable."""

    def test_ended_evidence_without_the_block_offers_reject_only(self) -> None:
        from jarvis.infrastructure.slack_notifier import build_pause_blocks

        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id=_CORR,
            feature_id=_FEATURE,
            completed_at=datetime.now(UTC),
            build_id=_SYNTHETIC,
            rationale="Ready to merge",
            approval_subject=_SUBJECT,
            stage_label="the merge-ready checkpoint",
            review_evidence=_evidence("ended"),  # type: ignore[arg-type]
        )
        value = json.dumps({"request_id": _REQUEST})
        blocks = build_pause_blocks(notification, button_value=value, link_hosts=_HOSTS)
        assert _decision_ids(blocks) == ["forge_reject"]
        assert "Preview stopped: the preview's time ran out" in _texts(blocks)


class TestCoachFindings:
    """Independent coach review of 4477503 (16 October 2026), findings 2 and 3."""

    @pytest.mark.asyncio
    async def test_a_clicked_card_is_not_redrawn_at_the_same_revision(self) -> None:
        """Coach scratch test s1, now asserting the fix.

        Approve is pressed at revision 4. A sweep at the SAME revision, still
        undecided (it ran before Forge recorded the press), used to redraw live
        Approve/Reject while the click latch stayed, so a tap on them was
        silently dropped. Now the card keeps the click message until a newer
        revision arrives, which clears the click and redraws.
        """
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ready", 4))
        ready = _posted_blocks(client)
        handler, publisher, web_client = _handler(store)
        await handler.handle_block_actions(_click(ready, "forge_approve", ts="1720.0001"))
        assert len(_published(publisher)) == 1
        shown = web_client.chat_update.await_args.kwargs
        assert "Decision recorded: approve" in _texts(shown["blocks"])

        with capture_logs() as logs:
            await notifier._deliver_merge_card(_notification("ready", 4))
        client.chat_update.assert_not_awaited()
        assert store.get(_REQUEST).displayed == content_digest(shown["blocks"], shown["text"])
        assert any(e["event"] == "slack_merge_card_redraw_held_while_clicked" for e in logs)

        # A newer undecided revision (Forge refused the press) clears the click
        # and redraws, and the restored buttons work.
        await notifier._deliver_merge_card(_notification("ready", 5))
        restored = client.chat_update.await_args.kwargs["blocks"]
        assert _decision_ids(restored) == ["forge_approve", "forge_reject"]
        await handler.handle_block_actions(_click(restored, "forge_reject", ts="1720.0001"))
        assert [p.decision for _, p in _published(publisher)] == ["approve", "reject"]

    @pytest.mark.asyncio
    async def test_a_newer_decided_description_still_redraws_a_clicked_card(self) -> None:
        store = MergeCardStore(None)
        notifier, client, _ = _make_notifier(store)
        await notifier._deliver_merge_card(_notification("ready", 4))
        handler, _, _ = _handler(store)
        await handler.handle_block_actions(
            _click(_posted_blocks(client), "forge_approve", ts="1720.0001")
        )
        await notifier._deliver_merge_card(_notification("decided", 5))
        assert "Approved by" in json.dumps(client.chat_update.await_args.kwargs["blocks"])
        assert store.is_latched(_REQUEST)

    @pytest.mark.asyncio
    async def test_a_decided_card_whose_message_is_gone_is_never_reposted(self) -> None:
        """Coach scratch test s4, now asserting the fix."""
        from slack_sdk.errors import SlackApiError

        notifier, client, store = _make_notifier()
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(_notification("decided", 3))
        client.chat_update.side_effect = SlackApiError(
            "gone", {"ok": False, "error": "message_not_found"}
        )
        await notifier._deliver_merge_card(_notification("decided", 3, decided_by="U0OTHER"))
        assert client.chat_postMessage.await_count == 1
        # The record stays as a placeholder at the decided revision.
        assert store.get(_REQUEST).revision == 3
        # A late, older, undecided description arrives out of order.
        await notifier._deliver_merge_card(_notification("ready", 2))
        assert client.chat_postMessage.await_count == 1
        # And the next sweep of the decided card does not try the edit again.
        calls = client.chat_update.await_count
        await notifier._deliver_merge_card(_notification("decided", 3, decided_by="U0OTHER"))
        assert client.chat_update.await_count == calls


class TestTheRecordOutlivesTheMessage:
    """Codex implementation review round 1, R1 (16 October 2026).

    The store keeps each card's identity and highest accepted revision
    whether or not a Slack message exists; a missing message only clears the
    message reference, and a card first heard of already decided is kept as a
    placeholder. Each test reloads the store from its file between
    descriptions, as a restart would.
    """

    @staticmethod
    def _restart(path: Path) -> tuple[SlackNotifier, AsyncMock, MergeCardStore]:
        return _make_notifier(MergeCardStore(path))

    @pytest.mark.asyncio
    async def test_gone_message_and_failed_replacement_keep_the_revision(
        self, tmp_path: Path
    ) -> None:
        from slack_sdk.errors import SlackApiError

        path = tmp_path / "merge-cards.json"
        notifier, client, store = self._restart(path)
        await notifier._deliver_merge_card(_notification("ready", 1))
        await notifier._deliver_merge_card(_notification("ended", 3))

        # A new process. Slack says the message is gone, and the replacement
        # post fails too.
        notifier, client, store = self._restart(path)
        client.chat_update.side_effect = SlackApiError(
            "gone", {"ok": False, "error": "message_not_found"}
        )
        client.chat_postMessage.side_effect = RuntimeError("slack is down")
        stopped = "Preview stopped: to make room for FEAT-C."
        await notifier._deliver_merge_card(_notification("ended", 4, status_text=stopped))
        client.chat_update.assert_awaited_once()
        entry = store.get(_REQUEST)
        assert entry is not None
        assert (entry.revision, entry.ts) == (4, None)

        # Another restart; a delayed, older "ready" arrives. It is stale.
        notifier, client, store = self._restart(path)
        with capture_logs() as logs:
            await notifier._deliver_merge_card(_notification("ready", 2))
        client.chat_postMessage.assert_not_awaited()
        assert any(e["event"] == "slack_merge_card_stale_ignored" for e in logs)

        # The next description at the accepted revision posts the replacement.
        await notifier._deliver_merge_card(_notification("ended", 4, status_text=stopped))
        client.chat_postMessage.assert_awaited_once()
        assert _decision_ids(_posted_blocks(client)) == [ACTION_REBUILD_PREVIEW, "forge_reject"]
        assert MergeCardStore(path).get(_REQUEST).ts == "1720.0001"

    @pytest.mark.asyncio
    async def test_a_card_first_heard_of_as_decided_is_a_placeholder(self, tmp_path: Path) -> None:
        path = tmp_path / "merge-cards.json"
        notifier, client, store = self._restart(path)
        await notifier._deliver_merge_card(_notification("decided", 5))
        client.chat_postMessage.assert_not_awaited()
        entry = store.get(_REQUEST)
        assert entry is not None
        assert (entry.revision, entry.ts) == (5, None)
        assert entry.decided_at is not None

        notifier, client, store = self._restart(path)
        await notifier._deliver_merge_card(_notification("ready", 3))
        await notifier._deliver_merge_card(_notification("decided", 5))
        client.chat_postMessage.assert_not_awaited()
        client.chat_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_failed_first_post_keeps_the_revision(self, tmp_path: Path) -> None:
        path = tmp_path / "merge-cards.json"
        notifier, client, store = self._restart(path)
        client.chat_postMessage.side_effect = RuntimeError("slack is down")
        await notifier._deliver_merge_card(_notification("ended", 3))
        assert store.get(_REQUEST).revision == 3

        notifier, client, store = self._restart(path)
        await notifier._deliver_merge_card(_notification("ready", 2))
        client.chat_postMessage.assert_not_awaited()
        await notifier._deliver_merge_card(_notification("ended", 3))
        client.chat_postMessage.assert_awaited_once()

    def test_an_old_record_without_a_message_still_reads(self, tmp_path: Path) -> None:
        path = tmp_path / "merge-cards.json"
        store = MergeCardStore(path)
        store.put(_entry(channel="", ts=None, displayed=""))
        assert MergeCardStore(path).get(_REQUEST).ts is None
