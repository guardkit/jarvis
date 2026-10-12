"""Preview and test evidence on the merge card (web-readiness W7).

Covers the Jarvis half of the review-evidence contract:

* projection — ``review_evidence`` on a build-paused payload reaches
  ``ForgeNotification`` typed as nats-core's ``ReviewEvidence`` (sink and
  CLI paths); a bad record is dropped without costing the card;
* rendering — the plain-English evidence line, URL buttons for a ready
  preview, Diagnostics and Reject-only for a failed one, unknown counts
  said as unknown, and links outside the host allow-list dropped with a
  warning;
* unchanged — a card without evidence renders byte-for-byte as before
  (goldens captured from the code before this change);
* reply path — a link click is acknowledged and ignored: nothing is
  published, nothing is marked decided, it is not an unknown action, and
  Approve still works afterwards; a Reject-only card still rejects.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from nats_core.events import ReviewEvidence
from pydantic import ValidationError
from structlog.testing import capture_logs

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
)
from jarvis.infrastructure.slack_notifier import (
    PREVIEW_LINK_ACTION_IDS,
    SlackNotifier,
    build_pause_blocks,
)
from jarvis.infrastructure.slack_reply import build_reply_handler

_HOST_APP = "preview.example.test"
_HOST_EVIDENCE = "evidence.example.test"
_HOSTS = frozenset({_HOST_APP, _HOST_EVIDENCE})
_APP_URL = f"https://{_HOST_APP}:8950/?preview=tok-secret-123"
_REPORT_URL = f"https://{_HOST_EVIDENCE}/factory-evidence/p/f/sha/run-1/report/index.html"
_MEDIA_URL = f"https://{_HOST_EVIDENCE}/factory-evidence/p/f/sha/run-1/journey.webm"
_DIAG_URL = f"https://{_HOST_EVIDENCE}/factory-evidence/p/f/sha/run-1/trace.zip"

_BUILD_ID = "build-FEAT-GOLD1-1"
_SUBJECT = f"agents.approval.forge.{_BUILD_ID}"
_VALUE = json.dumps(
    {
        "request_id": "apr-1",
        "build_id": _BUILD_ID,
        "correlation_id": "corr-golden-1",
        "approval_subject": _SUBJECT,
    },
    separators=(",", ":"),
)
_OPERATOR = "U0OPERATOR"


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
    created = datetime(2026, 10, 12, 14, 0, tzinfo=UTC)
    data: dict[str, Any] = {
        "state": state,
        "app_url": _APP_URL if state == "ready" else None,
        "report_url": _REPORT_URL,
        "media_urls": [_MEDIA_URL],
        "diagnostics_url": _DIAG_URL if state == "failed" else None,
        "failure_reason": "the preview does not enforce its link" if state == "failed" else None,
        "candidate_sha": "a" * 40,
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


def _notification(evidence: dict[str, Any] | None = None) -> ForgeNotification:
    return ForgeNotification(
        event_type="build_paused",
        correlation_id="corr-golden-1",
        feature_id="FEAT-GOLD1",
        completed_at=datetime(2026, 10, 12, 14, 0, tzinfo=UTC),
        build_id=_BUILD_ID,
        coach_score=0.91,
        rationale="Every task passed its checks. Ready to merge.",
        approval_subject=_SUBJECT,
        stage_label="the merge-ready checkpoint",
        # A dict on purpose: the field types it through nats-core's model.
        review_evidence=evidence,  # type: ignore[arg-type]
    )


def _actions(blocks: list[dict[str, Any]], block_id: str) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "actions" and b.get("block_id") == block_id]


def _section_texts(blocks: list[dict[str, Any]]) -> list[str]:
    return [b["text"]["text"] for b in blocks if b.get("type") == "section"]


def _make_notifier(hosts: frozenset[str] = _HOSTS) -> tuple[SlackNotifier, AsyncMock]:
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        notifier = SlackNotifier(
            bot_token="xoxb-test", channel_id="C123456", evidence_link_hosts=hosts
        )
    mock_client.chat_postMessage.return_value = {"ok": True, "ts": "1720.0001"}
    mock_client.chat_update.return_value = {"ok": True}
    return notifier, mock_client


# ---------------------------------------------------------------------------
# Unchanged: cards without evidence, byte for byte (goldens from before W7)
# ---------------------------------------------------------------------------

_GOLDEN_HEAD = (
    '[{"type": "header", "text": {"type": "plain_text", "text": "Ready to merge and deploy'
    '{settled}", "emoji": false}}, {"type": "context", "elements": [{"type": "plain_text", '
    '"text": "FEAT-GOLD1", "emoji": false}]}, {"type": "section", "text": {"type": '
    '"plain_text", "text": "Every task passed its checks. Ready to merge.", "emoji": false}}, '
    '{"type": "section", "text": {"type": "plain_text", "text": "Checker score: 0.91", '
    '"emoji": false}}, {"type": "context", "elements": [{"type": "plain_text", "text": '
    '"Build build-FEAT-GOLD1-1 \\u00b7 reference corr-golden-1", "emoji": false}]}, '
)
_GOLDEN_VALUE = (
    '"{\\"request_id\\":\\"apr-1\\",\\"build_id\\":\\"build-FEAT-GOLD1-1\\",'
    '\\"correlation_id\\":\\"corr-golden-1\\",\\"approval_subject\\":'
    '\\"agents.approval.forge.build-FEAT-GOLD1-1\\"}"'
)
_GOLDEN_BUTTONED = (
    _GOLDEN_HEAD.replace("{settled}", " \\u2014 your press")
    + '{"type": "actions", "block_id": "forge_approval", "elements": [{"type": "button", '
    '"action_id": "forge_approve", "text": {"type": "plain_text", "text": "Approve", '
    '"emoji": false}, "style": "primary", "value": '
    + _GOLDEN_VALUE
    + '}, {"type": "button", "action_id": "forge_reject", "text": {"type": "plain_text", '
    '"text": "Reject", "emoji": false}, "style": "danger", "value": ' + _GOLDEN_VALUE + "}]}]"
)
_GOLDEN_TEXT_ONLY = (
    _GOLDEN_HEAD.replace("{settled}", " \\u2014 your press")
    + '{"type": "section", "text": {"type": "plain_text", "text": '
    '"Use CLI to approve or reject this build.", "emoji": false}}]'
)
_GOLDEN_SETTLED = (
    _GOLDEN_HEAD.replace("{settled}", "")
    + '{"type": "section", "text": {"type": "plain_text", "text": '
    '"This build finished at 14:07.", "emoji": false}}]'
)
_GOLDEN_RENDER = (
    "Ready to merge and deploy — your press\nFEAT-GOLD1\n"
    "Every task passed its checks. Ready to merge.\nChecker score: 0.91\n"
    "Build build-FEAT-GOLD1-1 · reference corr-golden-1\n"
    "Use CLI to approve or reject this build."
)


class TestCardsWithoutEvidenceUnchanged:
    @pytest.mark.parametrize("hosts", [frozenset(), _HOSTS])
    def test_buttoned_card_is_byte_identical(self, hosts: frozenset[str]) -> None:
        blocks = build_pause_blocks(_notification(), button_value=_VALUE, link_hosts=hosts)
        assert json.dumps(blocks) == _GOLDEN_BUTTONED

    def test_text_only_card_is_byte_identical(self) -> None:
        blocks = build_pause_blocks(_notification(), link_hosts=_HOSTS)
        assert json.dumps(blocks) == _GOLDEN_TEXT_ONLY

    def test_settled_card_is_byte_identical(self) -> None:
        blocks = build_pause_blocks(
            _notification(),
            button_value=_VALUE,
            status_line="This build finished at 14:07.",
            link_hosts=_HOSTS,
        )
        assert json.dumps(blocks) == _GOLDEN_SETTLED

    def test_text_render_is_byte_identical(self) -> None:
        notifier, _ = _make_notifier()
        assert notifier._render(_notification()) == _GOLDEN_RENDER


# ---------------------------------------------------------------------------
# Rendering with evidence
# ---------------------------------------------------------------------------


class TestReadyEvidenceCard:
    def test_evidence_line_counts_and_both_expiry_times(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence()), button_value=_VALUE, link_hosts=_HOSTS
        )
        assert (
            "Preview ready. Tests: passed 3, failed 0, skipped 1, flaky unknown.\n"
            "Preview and Approve available until Tue 13 Oct 14:00 UTC · "
            "report and video kept until 26 Oct.\n"
            "The links work only on the tailnet."
        ) in _section_texts(blocks)

    def test_link_buttons_then_unchanged_decision_buttons(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence()), button_value=_VALUE, link_hosts=_HOSTS
        )
        (links,) = _actions(blocks, "forge_preview_links")
        assert [(e["action_id"], e["text"]["text"], e["url"]) for e in links["elements"]] == [
            ("forge_preview_open", "Try the app", _APP_URL),
            ("forge_preview_report", "Test report", _REPORT_URL),
            ("forge_preview_media", "Screenshots / video", _MEDIA_URL),
        ]
        # URL buttons carry no decision value.
        assert all("value" not in e for e in links["elements"])
        # Approve and Reject are exactly the pre-W7 buttons, after the links.
        (decision,) = _actions(blocks, "forge_approval")
        assert blocks.index(links) < blocks.index(decision)
        golden = json.loads(_GOLDEN_BUTTONED)[-1]
        assert decision == golden

    def test_unknown_counts_said_as_unknown_never_zero(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence(outcome={})), button_value=_VALUE, link_hosts=_HOSTS
        )
        text = "\n".join(_section_texts(blocks))
        assert "Tests: passed unknown, failed unknown, skipped unknown, flaky unknown." in text

    def test_settled_card_keeps_the_words_but_drops_the_links(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence()),
            button_value=_VALUE,
            status_line="This build finished at 14:07.",
            link_hosts=_HOSTS,
        )
        assert not [b for b in blocks if b.get("type") == "actions"]
        assert any(t.startswith("Preview ready.") for t in _section_texts(blocks))

    def test_text_render_carries_the_evidence_words(self) -> None:
        notifier, _ = _make_notifier()
        text = notifier._render(_notification(_evidence()))
        assert "Preview ready. Tests: passed 3, failed 0, skipped 1, flaky unknown." in text
        assert text.endswith("Use CLI to approve or reject this build.")
        assert _APP_URL not in text


class TestFailedEvidenceCard:
    def test_reason_diagnostics_and_reject_only(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence("failed")), button_value=_VALUE, link_hosts=_HOSTS
        )
        text = "\n".join(_section_texts(blocks))
        assert "Preview could not be prepared: the preview does not enforce its link" in text
        assert "Approve is not offered for this build." in text
        assert "diagnostics kept until 26 Oct." in text
        (links,) = _actions(blocks, "forge_preview_links")
        action_ids = [e["action_id"] for e in links["elements"]]
        assert action_ids[0] == "forge_preview_diagnostics"
        assert links["elements"][0]["text"]["text"] == "Diagnostics"
        assert "forge_preview_open" not in action_ids
        (decision,) = _actions(blocks, "forge_approval")
        assert [e["action_id"] for e in decision["elements"]] == ["forge_reject"]
        # The Reject-only card carries the very same decision value.
        assert decision["elements"][0]["value"] == _VALUE
        assert "Approve" not in json.dumps(decision)

    def test_long_reason_is_cut_inside_the_section_limit(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence("failed", failure_reason="x" * 5000)),
            button_value=_VALUE,
            link_hosts=_HOSTS,
        )
        assert all(len(text) < 3000 for text in _section_texts(blocks))
        assert "x" * 999 + "…" in "\n".join(_section_texts(blocks))

    def test_failed_never_offers_the_app_even_if_sent(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence("failed", app_url=_APP_URL)),
            button_value=_VALUE,
            link_hosts=_HOSTS,
        )
        assert _APP_URL not in json.dumps(blocks)

    def test_text_only_failed_card_says_reject_only(self) -> None:
        blocks = build_pause_blocks(_notification(_evidence("failed")), link_hosts=_HOSTS)
        assert _section_texts(blocks)[-1] == "Use CLI to reject this build."
        notifier, _ = _make_notifier()
        assert notifier._render(_notification(_evidence("failed"))).endswith(
            "Use CLI to reject this build."
        )

    @pytest.mark.asyncio
    async def test_delivered_card_has_no_approve(self) -> None:
        notifier, client = _make_notifier()
        await notifier.capture_approval_request(
            request_id="apr-1",
            build_id=_BUILD_ID,
            correlation_id="corr-golden-1",
            approval_subject=_SUBJECT,
            timeout_seconds=300,
        )
        await notifier._deliver_pause_message(_notification(_evidence("failed")))
        blocks = client.chat_postMessage.await_args.kwargs["blocks"]
        assert "forge_approve" not in json.dumps(blocks)
        (decision,) = _actions(blocks, "forge_approval")
        assert [e["action_id"] for e in decision["elements"]] == ["forge_reject"]


class TestHostAllowList:
    def test_link_on_another_host_is_dropped_with_a_warning(self) -> None:
        evil = "https://elsewhere.example.test/report/index.html"
        with capture_logs() as logs:
            blocks = build_pause_blocks(
                _notification(_evidence(report_url=evil)),
                button_value=_VALUE,
                link_hosts=_HOSTS,
            )
        (links,) = _actions(blocks, "forge_preview_links")
        assert [e["action_id"] for e in links["elements"]] == [
            "forge_preview_open",
            "forge_preview_media",
        ]
        assert evil not in json.dumps(blocks)
        dropped = [e for e in logs if e["event"] == "slack_preview_link_dropped"]
        assert len(dropped) == 1
        assert dropped[0]["log_level"] == "warning"
        assert dropped[0]["link"] == "forge_preview_report"
        assert dropped[0]["host"] == "elsewhere.example.test"

    def test_empty_allow_list_means_no_link_buttons_and_logs_each(self) -> None:
        with capture_logs() as logs:
            blocks = build_pause_blocks(_notification(_evidence()), button_value=_VALUE)
        assert not _actions(blocks, "forge_preview_links")
        assert "tailnet" not in "\n".join(_section_texts(blocks))
        dropped = [e for e in logs if e["event"] == "slack_preview_link_dropped"]
        assert {e["link"] for e in dropped} == {
            "forge_preview_open",
            "forge_preview_report",
            "forge_preview_media",
        }
        # The app link's token never reaches the log.
        assert "tok-secret-123" not in repr(logs)
        # Approve and Reject are still there.
        assert _actions(blocks, "forge_approval")

    def test_host_match_ignores_case_and_port(self) -> None:
        blocks = build_pause_blocks(
            _notification(_evidence(app_url="https://PREVIEW.example.test:8951/?preview=t")),
            button_value=_VALUE,
            link_hosts=_HOSTS,
        )
        (links,) = _actions(blocks, "forge_preview_links")
        assert links["elements"][0]["action_id"] == "forge_preview_open"

    def test_setting_parses_comma_separated_hosts(self) -> None:
        config = JarvisConfig(
            slack_evidence_link_hosts=" Preview.example.test, ,evidence.example.test "
        )
        assert config.resolve_evidence_link_hosts() == _HOSTS
        assert JarvisConfig().resolve_evidence_link_hosts() == frozenset()

    def test_setting_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JARVIS_SLACK_EVIDENCE_LINK_HOSTS", "preview.example.test")
        config = JarvisConfig()
        assert config.resolve_evidence_link_hosts() == frozenset({"preview.example.test"})

    def test_sink_factory_passes_the_hosts(self) -> None:
        from pydantic import SecretStr

        from jarvis.infrastructure.slack_notifier import create_slack_sink

        config = JarvisConfig(
            slack_bot_token=SecretStr("xoxb-test"),
            slack_channel_id="C1",
            slack_evidence_link_hosts="preview.example.test",
        )
        with patch("slack_sdk.web.async_client.AsyncWebClient"):
            sink = create_slack_sink(config)
        assert isinstance(sink, SlackNotifier)
        assert sink._evidence_link_hosts == frozenset({"preview.example.test"})


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


def _subscriber() -> tuple[ForgeNotificationsSubscriber, AsyncMock, Mock]:
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
    session_manager = Mock()
    session_manager.enqueue_notification = Mock()
    subscriber.bind_session_manager(session_manager)
    subscriber.register_correlation(
        correlation_id="pause-corr-w7",
        session_id="session-1",
        adapter="cli",
        queued_at=datetime.now(UTC),
        feature_id="FEAT-W7PV",
    )
    return subscriber, sink.notify, session_manager


def _pause_msg(payload_extra: dict[str, Any]) -> Mock:
    payload = {
        "feature_id": "FEAT-W7PV",
        "build_id": "build-FEAT-W7PV-1",
        "correlation_id": "pause-corr-w7",
        "stage_label": "the merge-ready checkpoint",
        "gate_mode": "MANDATORY_HUMAN_APPROVAL",
        "coach_score": None,
        "rationale": "Ready to merge",
        "approval_subject": "agents.approval.forge.build-FEAT-W7PV-1",
        "paused_at": "2026-10-12T14:00:00+00:00",
        **payload_extra,
    }
    envelope = {
        "event_type": "build_paused",
        "source_id": "forge",
        "correlation_id": "pause-corr-w7",
        "timestamp": "2026-10-12T14:00:00Z",
        "payload": payload,
    }
    msg = Mock()
    msg.data = json.dumps(envelope).encode()
    return msg


class TestProjection:
    @pytest.mark.asyncio
    async def test_pause_payload_evidence_reaches_sink_and_cli(self) -> None:
        subscriber, notify, session_manager = _subscriber()
        await subscriber._handle_message(_pause_msg({"review_evidence": _evidence()}))
        assert notify.await_args is not None
        sink_notification = notify.await_args.args[0]
        assert isinstance(sink_notification.review_evidence, ReviewEvidence)
        assert sink_notification.review_evidence.app_url == _APP_URL
        assert sink_notification.review_evidence.preview_tree == "c" * 40
        cli_notification = session_manager.enqueue_notification.call_args.args[1]
        assert cli_notification.review_evidence == sink_notification.review_evidence

    @pytest.mark.asyncio
    async def test_old_payload_without_evidence_projects_none(self) -> None:
        subscriber, notify, _ = _subscriber()
        await subscriber._handle_message(_pause_msg({}))
        assert notify.await_args is not None
        assert notify.await_args.args[0].review_evidence is None

    @pytest.mark.asyncio
    async def test_bad_evidence_is_dropped_but_the_card_still_goes(self) -> None:
        subscriber, notify, _ = _subscriber()
        with capture_logs() as logs:
            await subscriber._handle_message(
                _pause_msg({"review_evidence": _evidence(app_url=None)})
            )
        assert notify.await_args is not None
        notification = notify.await_args.args[0]
        assert notification.review_evidence is None
        assert notification.rationale == "Ready to merge"
        assert any(
            e["event"] == "forge_notification_review_evidence_dropped"
            and e["log_level"] == "warning"
            for e in logs
        )

    def test_model_types_a_dict_and_rejects_a_bad_one(self) -> None:
        notification = _notification(_evidence())
        assert isinstance(notification.review_evidence, ReviewEvidence)
        with pytest.raises(ValidationError):
            _notification(_evidence(candidate_sha="nope"))


# ---------------------------------------------------------------------------
# Reply path: link clicks are no-ops
# ---------------------------------------------------------------------------


def _handler() -> tuple[Any, MagicMock, AsyncMock]:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    web_client = AsyncMock()
    handler = build_reply_handler(
        operator_ids=frozenset({_OPERATOR}), publisher=publisher, web_client=web_client
    )
    return handler, publisher, web_client


def _click(
    blocks: list[dict[str, Any]], action_id: str, *, user_id: str = _OPERATOR
) -> dict[str, Any]:
    element = next(
        e
        for b in blocks
        if b.get("type") == "actions"
        for e in b["elements"]
        if e["action_id"] == action_id
    )
    action: dict[str, Any] = {"action_id": action_id, "type": "button"}
    if "value" in element:
        action["value"] = element["value"]
    if "url" in element:
        action["url"] = element["url"]
    return {
        "type": "block_actions",
        "user": {"id": user_id},
        "container": {"type": "message", "channel_id": "C123456", "message_ts": "1720.0001"},
        "channel": {"id": "C123456"},
        "message": {"blocks": blocks},
        "actions": [action],
    }


class TestLinkClicksAreNoOps:
    def test_the_four_link_action_ids(self) -> None:
        assert {
            "forge_preview_open",
            "forge_preview_report",
            "forge_preview_media",
            "forge_preview_diagnostics",
        } == PREVIEW_LINK_ACTION_IDS

    @pytest.mark.asyncio
    async def test_link_clicks_leave_approval_state_and_approve_still_works(self) -> None:
        handler, publisher, web_client = _handler()
        ready = build_pause_blocks(
            _notification(_evidence()), button_value=_VALUE, link_hosts=_HOSTS
        )
        failed = build_pause_blocks(
            _notification(_evidence("failed")), button_value=_VALUE, link_hosts=_HOSTS
        )
        clicks = [
            _click(ready, "forge_preview_open"),
            _click(ready, "forge_preview_report"),
            _click(ready, "forge_preview_media"),
            _click(failed, "forge_preview_diagnostics"),
        ]
        with capture_logs() as logs:
            for payload in clicks:
                await handler.handle_block_actions(payload)

        publisher.publish.assert_not_awaited()
        web_client.chat_update.assert_not_awaited()
        web_client.chat_postEphemeral.assert_not_awaited()
        assert handler._decided_request_ids == set()
        assert not handler._decision_lock.locked()
        events = {e["event"] for e in logs}
        assert "slack_reply_unknown_action_dropped" not in events
        assert "slack_reply_malformed_value_dropped" not in events

        # The card is still decidable: Approve publishes exactly once.
        await handler.handle_block_actions(_click(ready, "forge_approve"))
        publisher.publish.assert_awaited_once()
        kwargs = publisher.publish.await_args.kwargs
        assert kwargs["subject"] == f"{_SUBJECT}.response"
        assert kwargs["payload"].decision == "approve"
        assert kwargs["payload"].request_id == "apr-1"

    @pytest.mark.asyncio
    async def test_link_click_by_a_reader_who_may_not_decide_is_not_refused(self) -> None:
        handler, publisher, web_client = _handler()
        ready = build_pause_blocks(
            _notification(_evidence()), button_value=_VALUE, link_hosts=_HOSTS
        )
        await handler.handle_block_actions(
            _click(ready, "forge_preview_report", user_id="U0READER")
        )
        publisher.publish.assert_not_awaited()
        web_client.chat_postEphemeral.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reject_only_card_still_rejects(self) -> None:
        handler, publisher, _ = _handler()
        failed = build_pause_blocks(
            _notification(_evidence("failed")), button_value=_VALUE, link_hosts=_HOSTS
        )
        await handler.handle_block_actions(_click(failed, "forge_preview_diagnostics"))
        await handler.handle_block_actions(_click(failed, "forge_reject"))
        publisher.publish.assert_awaited_once()
        kwargs = publisher.publish.await_args.kwargs
        assert kwargs["subject"] == f"{_SUBJECT}.response"
        assert kwargs["payload"].decision == "reject"
        assert kwargs["payload"].decided_by == _OPERATOR
        assert kwargs["correlation_id"] == "corr-golden-1"
