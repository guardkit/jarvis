"""Tests for TASK-JNB-103 — approval-request capture + Block Kit buttons.

Plain pytest only — NO pytest-bdd ``.feature`` glue (operator decision
2026-07-03). Test classes mirror the task's spec scenario names.

Coverage (mapped to TASK-JNB-103 acceptance criteria):

* AC — settings fields exist under the ``JARVIS_`` prefix
* AC — subscriber on ``agents.approval.forge.>`` captures request_id +
  timeout into a TTL-bounded pending map keyed by build_id; ``.response``
  subjects skipped structurally
* AC — request_id dedup, including boot-reconcile re-emits
* AC — build_id join proven for two concurrently paused builds
* AC — exactly one actionable message per request_id
* AC — TTL expiry → text-only fallback, never a dead button
* AC — button value JSON shape (4 keys, compact, < 2000 chars)
* AC — defer-refresh chat.update replaces buttons in place
* AC — text-only v1 fallback posted unchanged when nothing captured
* AC — request/pause ordering tolerance (both directions converge)
* AC — plain_text-only rendering (no mrkdwn interpretation)
* AC — DDR-007: subscriber/rendering failures WARN + continue

Plus the C1 (Phase 2.5B review) concurrency reconcile path: a capture
landing while the pause post is in flight converges via one chat.update.

Time-dependent behaviour is driven by patching the module's injectable
``_monotonic`` alias (NEVER ``time.monotonic`` — freezing the stdlib
attribute hangs the event loop; see the note in slack_notifier.py).
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.infrastructure.slack_notifier import (
    ApprovalRequestsSubscriber,
    SlackNotifier,
    _build_button_value,
    build_pause_blocks,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeClock:
    """Injectable monotonic clock for TTL tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def clock() -> Any:
    fake = FakeClock()
    with patch("jarvis.infrastructure.slack_notifier._monotonic", fake):
        yield fake


def _make_notifier() -> tuple[SlackNotifier, AsyncMock]:
    """A SlackNotifier with a fully mocked AsyncWebClient (no network)."""
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        notifier = SlackNotifier(bot_token="xoxb-test", channel_id="C123456")
    mock_client.chat_postMessage.return_value = {"ok": True, "ts": "1720.0001"}
    mock_client.chat_update.return_value = {"ok": True}
    return notifier, mock_client


def _make_subscriber(notifier: SlackNotifier) -> ApprovalRequestsSubscriber:
    return ApprovalRequestsSubscriber(nats_client=MagicMock(), notifier=notifier)


def _request_msg(
    subject: str,
    request_id: str = "apr-001",
    *,
    correlation_id: str | None = "corr-req-1",
    timeout_seconds: int = 300,
    event_type: str = "approval_request",
    payload: dict[str, Any] | None = None,
    data: bytes | None = None,
) -> SimpleNamespace:
    """A synthetic JetStream message carrying an ApprovalRequest envelope."""
    if data is None:
        envelope = {
            "source_id": "forge",
            "event_type": event_type,
            "correlation_id": correlation_id,
            "payload": (
                payload
                if payload is not None
                else {
                    "request_id": request_id,
                    "agent_id": "forge",
                    "action_description": "Quality gate approval required",
                    "risk_level": "medium",
                    "details": {},
                    "timeout_seconds": timeout_seconds,
                }
            ),
        }
        data = json.dumps(envelope).encode()
    return SimpleNamespace(subject=subject, data=data)


def _pause_notification(
    build_id: str | None = "build-abc123",
    *,
    feature_id: str = "FEAT-ABC1",
    correlation_id: str = "corr-pause-1",
    approval_subject: str | None = None,
    rationale: str | None = "Coach flagged a wiring risk",
    stage_label: str | None = "autobuild",
    coach_score: float | None = 0.42,
) -> ForgeNotification:
    if approval_subject is None and build_id is not None:
        approval_subject = f"agents.approval.forge.{build_id}"
    return ForgeNotification(
        event_type="build_paused",
        correlation_id=correlation_id,
        feature_id=feature_id,
        completed_at=datetime.now(UTC),
        build_id=build_id,
        approval_subject=approval_subject,
        rationale=rationale,
        stage_label=stage_label,
        coach_score=coach_score,
        gate_mode="MANDATORY_HUMAN_APPROVAL",
    )


def _actions_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "actions"]


def _button_value_from_blocks(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    actions = _actions_blocks(blocks)
    assert len(actions) == 1, "expected exactly one actions block"
    value = actions[0]["elements"][0]["value"]
    return json.loads(value)


async def _capture(
    subscriber: ApprovalRequestsSubscriber,
    build_id: str,
    request_id: str,
    **kwargs: Any,
) -> None:
    await subscriber._on_message(
        _request_msg(f"agents.approval.forge.{build_id}", request_id, **kwargs)
    )


# ---------------------------------------------------------------------------
# Settings fields (AC-001)
# ---------------------------------------------------------------------------


class TestApprovalSettingsFields:
    """The Slack reply-path pydantic-settings fields under JARVIS_ prefix.

    TASK-JNB-110: ``slack_operator_user_ids`` (plural allowlist) is the
    canonical authorization field; ``slack_operator_user_id`` (singular) and
    ``slack_decided_by`` remain loadable but are DEPRECATED.
    """

    def test_fields_load_from_env(self) -> None:
        from pydantic import SecretStr

        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {
                "JARVIS_SLACK_APP_TOKEN": "xapp-test-token",
                "JARVIS_SLACK_OPERATOR_USER_IDS": "U0RICH,U0JAMES",
                # Deprecated fields still parse (retained for migration).
                "JARVIS_SLACK_OPERATOR_USER_ID": "U0EXAMPLE",
                "JARVIS_SLACK_DECIDED_BY": "Jarvis-Operator",
            },
            clear=True,
        ):
            config = JarvisConfig()

        assert isinstance(config.slack_app_token, SecretStr)
        assert config.slack_app_token.get_secret_value() == "xapp-test-token"
        assert config.slack_operator_user_ids == "U0RICH,U0JAMES"
        assert config.slack_operator_user_id == "U0EXAMPLE"
        assert config.slack_decided_by == "Jarvis-Operator"

    def test_fields_default_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig()

        assert config.slack_app_token is None
        assert config.slack_operator_user_ids is None
        assert config.slack_operator_user_id is None
        assert config.slack_decided_by is None

    def test_resolve_operator_allowlist_merges_plural_and_deprecated_singular(
        self,
    ) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {
                "JARVIS_SLACK_OPERATOR_USER_IDS": " U0RICH , U0JAMES ,",
                "JARVIS_SLACK_OPERATOR_USER_ID": "U0LEGACY",
            },
            clear=True,
        ):
            config = JarvisConfig()

        # Blank-stripped, deprecated singular folded in.
        assert config.resolve_operator_allowlist() == frozenset(
            {"U0RICH", "U0JAMES", "U0LEGACY"}
        )

    def test_resolve_operator_allowlist_empty_when_unset(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig()

        assert config.resolve_operator_allowlist() == frozenset()

    def test_resolve_operator_allowlist_blank_and_comma_only_is_empty(self) -> None:
        # The blank-stripping guard the code calls out: an empty value or a
        # stray-comma value must NOT smuggle an empty id into the allowlist
        # (an empty id would never match a click and would blur the no-op gate).
        from jarvis.config.settings import JarvisConfig

        for value in ("", "   ", ",", " , , "):
            with patch.dict(
                "os.environ",
                {"JARVIS_SLACK_OPERATOR_USER_IDS": value},
                clear=True,
            ):
                config = JarvisConfig()
            assert config.resolve_operator_allowlist() == frozenset(), repr(value)

    def test_app_token_masked_in_repr(self) -> None:
        from pydantic import SecretStr

        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(slack_app_token=SecretStr("xapp-secret"))
        assert "xapp-secret" not in repr(config)


# ---------------------------------------------------------------------------
# Approval-request capture
# ---------------------------------------------------------------------------


class TestApprovalRequestCapture:
    """Subscriber captures request_id + timeout keyed by build_id."""

    @pytest.mark.asyncio
    async def test_request_captured_into_pending_map(self) -> None:
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=120)

        pending = notifier._pending_approvals["build-abc123"]
        assert pending.request_id == "apr-001"
        assert pending.build_id == "build-abc123"
        assert pending.correlation_id == "corr-req-1"
        assert pending.approval_subject == "agents.approval.forge.build-abc123"
        assert pending.ttl_seconds == 120.0

    @pytest.mark.asyncio
    async def test_response_subject_never_captured(self) -> None:
        """5-token .response subjects are skipped structurally."""
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await subscriber._on_message(
            _request_msg("agents.approval.forge.build-abc123.response", "apr-001")
        )

        assert notifier._pending_approvals == {}

    @pytest.mark.asyncio
    async def test_non_approval_event_type_skipped(self) -> None:
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await subscriber._on_message(
            _request_msg(
                "agents.approval.forge.build-abc123",
                "apr-001",
                event_type="status",
                payload={"whatever": True},
            )
        )

        assert notifier._pending_approvals == {}

    @pytest.mark.asyncio
    async def test_build_id_taken_from_fourth_subject_token(self) -> None:
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-zz9", "apr-zz9")

        assert "build-zz9" in notifier._pending_approvals


# ---------------------------------------------------------------------------
# request_id dedup (including boot-reconcile re-emits)
# ---------------------------------------------------------------------------


class TestRequestIdDedup:
    """A re-emitted identical request_id yields no second actionable message."""

    @pytest.mark.asyncio
    async def test_reemit_before_pause_keeps_single_pending_entry(self) -> None:
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=300)
        # Re-emit with a different timeout: if dedup failed, the overwrite
        # would be visible as a changed TTL on the single map slot.
        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=999)

        assert len(notifier._pending_approvals) == 1
        entry = notifier._pending_approvals["build-abc123"]
        assert entry.request_id == "apr-001"
        assert entry.ttl_seconds == 300.0  # first capture wins verbatim

    @pytest.mark.asyncio
    async def test_boot_reconcile_reemit_after_post_produces_no_second_message(
        self,
    ) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))
        assert client.chat_postMessage.await_count == 1

        # forge boot-reconcile re-emits the identical request_id
        await _capture(subscriber, "build-abc123", "apr-001")

        assert client.chat_postMessage.await_count == 1
        client.chat_update.assert_not_awaited()
        assert notifier._pending_approvals == {}


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------


class TestTtlExpiry:
    """Stale pending entries drop; a late pause renders the fallback."""

    @pytest.mark.asyncio
    async def test_pause_after_expiry_renders_text_only_fallback(self, clock: FakeClock) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=300)
        clock.advance(301.0)

        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        kwargs = client.chat_postMessage.await_args.kwargs
        assert "blocks" not in kwargs
        assert "Use CLI to approve or reject this build." in kwargs["text"]
        assert notifier._pending_approvals == {}

    @pytest.mark.asyncio
    async def test_pause_within_ttl_renders_buttons(self, clock: FakeClock) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=300)
        clock.advance(299.0)

        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        kwargs = client.chat_postMessage.await_args.kwargs
        value = _button_value_from_blocks(kwargs["blocks"])
        assert value["request_id"] == "apr-001"


# ---------------------------------------------------------------------------
# build_id join — two concurrently paused builds
# ---------------------------------------------------------------------------


class TestBuildIdJoin:
    """Each pause message carries only its own build's button metadata."""

    @pytest.mark.asyncio
    async def test_two_concurrent_pauses_carry_distinct_metadata(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-aaa", "apr-aaa", correlation_id="corr-a")
        await _capture(subscriber, "build-bbb", "apr-bbb", correlation_id="corr-b")

        await notifier._deliver_pause_message(
            _pause_notification("build-aaa", correlation_id="corr-pause-a")
        )
        await notifier._deliver_pause_message(
            _pause_notification("build-bbb", correlation_id="corr-pause-b")
        )

        assert client.chat_postMessage.await_count == 2
        values = [
            _button_value_from_blocks(c.kwargs["blocks"])
            for c in client.chat_postMessage.await_args_list
        ]
        by_build = {v["build_id"]: v for v in values}
        assert by_build["build-aaa"]["request_id"] == "apr-aaa"
        assert by_build["build-aaa"]["correlation_id"] == "corr-a"
        assert by_build["build-aaa"]["approval_subject"] == ("agents.approval.forge.build-aaa")
        assert by_build["build-bbb"]["request_id"] == "apr-bbb"
        assert by_build["build-bbb"]["correlation_id"] == "corr-b"
        assert by_build["build-bbb"]["approval_subject"] == ("agents.approval.forge.build-bbb")


# ---------------------------------------------------------------------------
# Defer-refresh — chat.update replaces buttons in place
# ---------------------------------------------------------------------------


class TestDeferRefreshChatUpdate:
    """A refreshed request_id updates the existing message, never posts anew."""

    @pytest.mark.asyncio
    async def test_refreshed_request_id_updates_buttons_in_place(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))
        posted_ts = "1720.0001"

        # forge defer mints a refreshed request_id for the same build
        await _capture(subscriber, "build-abc123", "apr-002")

        assert client.chat_postMessage.await_count == 1  # no second message
        client.chat_update.assert_awaited_once()
        update_kwargs = client.chat_update.await_args.kwargs
        assert update_kwargs["ts"] == posted_ts
        value = _button_value_from_blocks(update_kwargs["blocks"])
        assert value["request_id"] == "apr-002"
        assert value["build_id"] == "build-abc123"

    @pytest.mark.asyncio
    async def test_refresh_before_any_pause_replaces_pending_entry(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001")
        await _capture(subscriber, "build-abc123", "apr-002")

        assert notifier._pending_approvals["build-abc123"].request_id == "apr-002"

        await notifier._deliver_pause_message(_pause_notification("build-abc123"))
        value = _button_value_from_blocks(client.chat_postMessage.await_args.kwargs["blocks"])
        assert value["request_id"] == "apr-002"
        client.chat_update.assert_not_awaited()


# ---------------------------------------------------------------------------
# Text-only fallback
# ---------------------------------------------------------------------------


class TestTextOnlyFallback:
    """No captured request → the v1 text-only pause message, unchanged."""

    @pytest.mark.asyncio
    async def test_fallback_posts_v1_text_verbatim(self) -> None:
        notifier, client = _make_notifier()
        completed = datetime(2026, 7, 5, 10, 30, tzinfo=UTC)
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="corr-pause-1",
            feature_id="FEAT-ABC1",
            completed_at=completed,
            build_id="build-abc123",
            approval_subject="agents.approval.forge.build-abc123",
            rationale="Coach flagged a wiring risk",
            stage_label="autobuild",
            coach_score=0.42,
            gate_mode="MANDATORY_HUMAN_APPROVAL",
        )

        await notifier._deliver_pause_message(notification)

        # Explicit expected shape (NOT notifier._render — a
        # self-referential oracle would stay green if _render broke).
        # Words rewritten 2026-09-05: a headline that says what is being
        # asked, the feature, the pipeline's own sentence, the score, and
        # one muted provenance line. No status line, no stage name, no
        # identifiers as prose.
        expected = (
            "Build paused — waiting for your go-ahead\n"
            "FEAT-ABC1\n"
            "Coach flagged a wiring risk\n"
            "Checker score: 0.42\n"
            "Build build-abc123 · reference corr-pause-1\n"
            "Use CLI to approve or reject this build."
        )
        kwargs = client.chat_postMessage.await_args.kwargs
        assert "blocks" not in kwargs
        assert kwargs["text"] == expected
        assert kwargs["mrkdwn"] is False

    @pytest.mark.asyncio
    async def test_fallback_when_notification_has_no_build_id(self) -> None:
        notifier, client = _make_notifier()

        await notifier._deliver_pause_message(_pause_notification(build_id=None))

        kwargs = client.chat_postMessage.await_args.kwargs
        assert "blocks" not in kwargs
        assert notifier._pause_messages == {}


# ---------------------------------------------------------------------------
# Ordering tolerance
# ---------------------------------------------------------------------------


class TestOrderingTolerance:
    """Request→pause and pause→request converge on one buttoned message."""

    @pytest.mark.asyncio
    async def test_request_before_pause_posts_one_buttoned_message(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        assert client.chat_postMessage.await_count == 1
        value = _button_value_from_blocks(client.chat_postMessage.await_args.kwargs["blocks"])
        assert value["request_id"] == "apr-001"
        client.chat_update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_pause_before_request_upgrades_fallback_in_place(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await notifier._deliver_pause_message(_pause_notification("build-abc123"))
        assert "blocks" not in client.chat_postMessage.await_args.kwargs

        await _capture(subscriber, "build-abc123", "apr-001")

        # No second message; the fallback was upgraded via chat.update
        assert client.chat_postMessage.await_count == 1
        client.chat_update.assert_awaited_once()
        update_kwargs = client.chat_update.await_args.kwargs
        assert update_kwargs["ts"] == "1720.0001"
        value = _button_value_from_blocks(update_kwargs["blocks"])
        assert value["request_id"] == "apr-001"
        assert value["build_id"] == "build-abc123"


# ---------------------------------------------------------------------------
# Button value JSON — BUTTON_METADATA producer contract
# ---------------------------------------------------------------------------


class TestButtonValueJson:
    """value JSON carries exactly the 4 contract keys within Slack limits."""

    def test_value_has_exactly_four_keys_and_round_trips(self) -> None:
        value = _build_button_value(
            request_id="apr-001",
            build_id="build-abc123",
            correlation_id="corr-1",
            approval_subject="agents.approval.forge.build-abc123",
        )
        assert value is not None
        parsed = json.loads(value)
        assert sorted(parsed.keys()) == [
            "approval_subject",
            "build_id",
            "correlation_id",
            "request_id",
        ]
        assert parsed["request_id"] == "apr-001"
        assert len(value) < 2000

    def test_value_is_compact_no_pretty_printing(self) -> None:
        value = _build_button_value(
            request_id="r",
            build_id="b",
            correlation_id="c",
            approval_subject="s",
        )
        assert value is not None
        assert ": " not in value
        assert ", " not in value
        assert "\n" not in value

    def test_max_size_ids_stay_under_limit(self) -> None:
        """The TASK-JNB-104 seam-test sizing must produce a valid value."""
        value = _build_button_value(
            request_id="apr-" + "a" * 60,
            build_id="build-" + "b" * 250,
            correlation_id="corr-" + "c" * 250,
            approval_subject="agents.approval.forge." + "b" * 250,
        )
        assert value is not None
        assert len(value) < 2000

    def test_oversized_value_returns_none(self) -> None:
        value = _build_button_value(
            request_id="apr-001",
            build_id="build-abc123",
            correlation_id="c" * 2000,
            approval_subject="agents.approval.forge.build-abc123",
        )
        assert value is None

    @pytest.mark.asyncio
    async def test_oversized_value_falls_back_to_text_only_post(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001", correlation_id="c" * 2000)
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        kwargs = client.chat_postMessage.await_args.kwargs
        assert "blocks" not in kwargs

    def test_both_buttons_carry_identical_value(self) -> None:
        notification = _pause_notification("build-abc123")
        value = _build_button_value(
            request_id="apr-001",
            build_id="build-abc123",
            correlation_id="corr-1",
            approval_subject="agents.approval.forge.build-abc123",
        )
        assert value is not None
        blocks = build_pause_blocks(notification, button_value=value)
        actions = _actions_blocks(blocks)[0]
        approve, reject = actions["elements"]
        assert approve["action_id"] == "forge_approve"
        assert reject["action_id"] == "forge_reject"
        assert approve["value"] == reject["value"] == value


# ---------------------------------------------------------------------------
# plain_text-only rendering
# ---------------------------------------------------------------------------


class TestPlainTextOnlyRendering:
    """All operator-visible text renders as plain_text objects — no mrkdwn."""

    def test_all_text_objects_are_plain_text_with_buttons(self) -> None:
        notification = _pause_notification(
            "build-abc123",
            rationale="*bold* `code` <http://x|link> & injection attempt",
        )
        value = _build_button_value(
            request_id="apr-001",
            build_id="build-abc123",
            correlation_id="corr-1",
            approval_subject="agents.approval.forge.build-abc123",
        )
        blocks = build_pause_blocks(notification, button_value=value)

        for block in blocks:
            if block.get("text"):
                assert block["text"]["type"] == "plain_text"
        actions = _actions_blocks(blocks)[0]
        for element in actions["elements"]:
            assert element["text"]["type"] == "plain_text"

    def test_rationale_renders_verbatim_in_plain_text(self) -> None:
        rationale = "*not-bold* verbatim rationale"
        blocks = build_pause_blocks(_pause_notification(rationale=rationale))
        joined = " ".join(b["text"]["text"] for b in blocks if b.get("text"))
        assert rationale in joined

    def test_long_rationale_chunked_within_block_kit_limits(self) -> None:
        rationale = "r" * 7000
        blocks = build_pause_blocks(_pause_notification(rationale=rationale))
        for block in blocks:
            if block.get("text"):
                assert len(block["text"]["text"]) <= 3000
        joined = "".join(b["text"]["text"] for b in blocks if b.get("text"))
        assert "r" * 7000 in joined


# ---------------------------------------------------------------------------
# C1 — concurrent capture while the pause post is in flight
# ---------------------------------------------------------------------------


class TestConcurrentCaptureAndPost:
    """A capture landing mid-post converges via the reconcile chat.update."""

    @pytest.mark.asyncio
    async def test_refresh_during_buttoned_post_reconciles_to_new_request(
        self,
    ) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        release = asyncio.Event()

        async def slow_post(**kwargs: Any) -> dict[str, Any]:
            await release.wait()
            return {"ok": True, "ts": "1720.0001"}

        client.chat_postMessage.side_effect = slow_post

        await _capture(subscriber, "build-abc123", "apr-001")
        post_task = asyncio.create_task(
            notifier._deliver_pause_message(_pause_notification("build-abc123"))
        )
        await asyncio.sleep(0.01)  # let the post reach the awaited client call

        # Refreshed request_id arrives while chat.postMessage is in flight
        await _capture(subscriber, "build-abc123", "apr-002")
        client.chat_update.assert_not_awaited()  # ts not landed yet

        release.set()
        await post_task

        assert client.chat_postMessage.await_count == 1
        client.chat_update.assert_awaited_once()
        value = _button_value_from_blocks(client.chat_update.await_args.kwargs["blocks"])
        assert value["request_id"] == "apr-002"
        # apr-002 stays parked as the multi-gate hedge: jarvis cannot
        # distinguish a defer-refresh from the next gate's early request,
        # so the entry either buttons the next pause or TTL-expires.
        assert notifier._pending_approvals["build-abc123"].request_id == "apr-002"

    @pytest.mark.asyncio
    async def test_capture_during_text_only_post_upgrades_after_settle(
        self,
    ) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        release = asyncio.Event()

        async def slow_post(**kwargs: Any) -> dict[str, Any]:
            await release.wait()
            return {"ok": True, "ts": "1720.0002"}

        client.chat_postMessage.side_effect = slow_post

        post_task = asyncio.create_task(
            notifier._deliver_pause_message(_pause_notification("build-abc123"))
        )
        await asyncio.sleep(0.01)

        await _capture(subscriber, "build-abc123", "apr-001")

        release.set()
        await post_task

        assert client.chat_postMessage.await_count == 1
        client.chat_update.assert_awaited_once()
        update_kwargs = client.chat_update.await_args.kwargs
        assert update_kwargs["ts"] == "1720.0002"
        value = _button_value_from_blocks(update_kwargs["blocks"])
        assert value["request_id"] == "apr-001"


# ---------------------------------------------------------------------------
# Worker path — end-to-end through notify()
# ---------------------------------------------------------------------------


class TestWorkerDeliversPauseMessages:
    """build_paused routes through the worker to the buttoned post."""

    @pytest.mark.asyncio
    async def test_notify_build_paused_posts_buttons_via_worker(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001")

        await notifier.start()
        try:
            await notifier.notify(_pause_notification("build-abc123"))
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
            assert client.chat_postMessage.await_count == 1
            value = _button_value_from_blocks(client.chat_postMessage.await_args.kwargs["blocks"])
            assert value["request_id"] == "apr-001"
        finally:
            await notifier.stop()

    @pytest.mark.asyncio
    async def test_non_pause_events_keep_v1_text_path(self) -> None:
        notifier, client = _make_notifier()

        await notifier.start()
        try:
            await notifier.notify(
                ForgeNotification(
                    event_type="build_complete",
                    correlation_id="corr-9",
                    feature_id="FEAT-ABC9",
                    completed_at=datetime.now(UTC),
                )
            )
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
            kwargs = client.chat_postMessage.await_args.kwargs
            assert "blocks" not in kwargs
            # Pinned string moved 2026-08-15 (build-side mention lane):
            # was "build-complete (PASSED)".
            assert "build complete" in kwargs["text"]
        finally:
            await notifier.stop()


# ---------------------------------------------------------------------------
# DDR-007 — never raise into the JetStream callback
# ---------------------------------------------------------------------------


class TestMalformedPayloadNeverRaises:
    """Subscriber and capture failures are WARNING + continue."""

    @pytest.mark.asyncio
    async def test_malformed_envelope_warns_and_continues(self) -> None:
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        with capture_logs() as logs:
            await subscriber._on_message(
                _request_msg(
                    "agents.approval.forge.build-abc123",
                    data=b"{not-json",
                )
            )

        assert notifier._pending_approvals == {}
        assert any(log["event"] == "approval_request_dropped_malformed" for log in logs)

    @pytest.mark.asyncio
    async def test_bad_payload_warns_and_continues(self) -> None:
        notifier, _ = _make_notifier()
        subscriber = _make_subscriber(notifier)

        with capture_logs() as logs:
            await subscriber._on_message(
                _request_msg(
                    "agents.approval.forge.build-abc123",
                    payload={"agent_id": "forge"},  # missing request_id etc.
                )
            )

        assert notifier._pending_approvals == {}
        assert any(log["event"] == "approval_request_dropped_bad_payload" for log in logs)

    @pytest.mark.asyncio
    async def test_chat_update_failure_on_refresh_never_propagates(self) -> None:
        from slack_sdk.errors import SlackApiError

        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        client.chat_update.side_effect = SlackApiError(
            message="message_not_found",
            response=MagicMock(status_code=404),
        )

        with capture_logs() as logs:
            # Must not raise out of the JetStream callback path
            await _capture(subscriber, "build-abc123", "apr-002")

        assert any(log["event"] == "slack_pause_button_update_failed" for log in logs)

    @pytest.mark.asyncio
    async def test_post_failure_drops_record_and_warns(self) -> None:
        from slack_sdk.errors import SlackApiError

        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response=MagicMock(status_code=404),
        )

        await _capture(subscriber, "build-abc123", "apr-001")
        with capture_logs() as logs:
            await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        assert notifier._pause_messages == {}
        assert any(log["event"] == "slack_pause_message_post_failed" for log in logs)


# ---------------------------------------------------------------------------
# Subscriber lifecycle
# ---------------------------------------------------------------------------


class TestSubscriberLifecycle:
    """start() binds agents.approval.forge.> only; stop() is bounded."""

    @pytest.mark.asyncio
    async def test_start_subscribes_agents_approval_forge_wildcard(self) -> None:
        notifier, _ = _make_notifier()
        js = MagicMock()
        js.subscribe = AsyncMock(return_value=MagicMock())
        nats_client = MagicMock()
        nats_client.js = js

        subscriber = ApprovalRequestsSubscriber(nats_client=nats_client, notifier=notifier)
        await subscriber.start()
        await subscriber.start()  # idempotent

        js.subscribe.assert_awaited_once()
        args = js.subscribe.await_args.args
        assert args[0] == "agents.approval.forge.>"
        # AGENTS stream only — never a pipeline.* subject (err 10100 rule)
        assert not args[0].startswith("pipeline.")
        # The consumer's full shape matters (mutation-hunt fix): the
        # callback must be this subscriber's handler and the policy NEW
        # (DDR-027 no-replay on the limits-retention AGENTS stream).
        from nats.js.api import DeliverPolicy

        kwargs = js.subscribe.await_args.kwargs
        assert kwargs["cb"].__self__ is subscriber
        assert kwargs["cb"].__func__ is ApprovalRequestsSubscriber._on_message
        assert kwargs["deliver_policy"] is DeliverPolicy.NEW
        assert kwargs["ordered_consumer"] is False

    @pytest.mark.asyncio
    async def test_stop_unsubscribes_and_never_raises(self) -> None:
        notifier, _ = _make_notifier()
        subscription = MagicMock()
        subscription.unsubscribe = AsyncMock(side_effect=RuntimeError("broker gone"))
        js = MagicMock()
        js.subscribe = AsyncMock(return_value=subscription)
        nats_client = MagicMock()
        nats_client.js = js

        subscriber = ApprovalRequestsSubscriber(nats_client=nats_client, notifier=notifier)
        await subscriber.start()
        await subscriber.stop()  # must swallow the unsubscribe error
        await subscriber.stop()  # idempotent


# ---------------------------------------------------------------------------
# Lifecycle wiring (build_app_state)
# ---------------------------------------------------------------------------


class TestLifecycleWiring:
    """AppState carries the approval subscriber; wiring gates on sink type."""

    def test_app_state_field_present_and_defaults_none(self) -> None:
        import dataclasses as dc

        from jarvis.infrastructure.lifecycle import AppState

        field_names = {f.name for f in dc.fields(AppState)}
        assert "approval_subscriber" in field_names

        state = AppState(
            config=MagicMock(),
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
            capability_registry=[],
        )
        assert state.approval_subscriber is None

    @pytest.mark.asyncio
    async def test_shutdown_stops_approval_subscriber(self) -> None:
        from jarvis.infrastructure.lifecycle import AppState, shutdown

        approval_subscriber = MagicMock()
        approval_subscriber.stop = AsyncMock()
        store = MagicMock(spec=[])  # no close attr

        state = AppState(
            config=MagicMock(),
            supervisor=MagicMock(),
            store=store,
            session_manager=MagicMock(),
            capability_registry=[],
            approval_subscriber=approval_subscriber,
        )
        await shutdown(state)
        approval_subscriber.stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# Multi-gate builds — a new pause supersedes the previous pause message
# ---------------------------------------------------------------------------


class TestMultiGateSupersede:
    """A second pause of the same build re-anchors: old buttons stripped,
    the fresh pause carries the new gate's buttons (both orderings)."""

    @pytest.mark.asyncio
    async def test_gate2_request_before_pause_buttons_new_message(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)
        client.chat_postMessage.side_effect = [
            {"ok": True, "ts": "1720.0001"},
            {"ok": True, "ts": "1720.0002"},
        ]

        # Gate 1: request + pause → buttoned message M1
        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(
            _pause_notification("build-abc123", stage_label="gate-1", rationale="gate-1 rationale")
        )

        # Gate 2: refreshed request arrives first, then the gate-2 pause
        await _capture(subscriber, "build-abc123", "apr-002")
        await notifier._deliver_pause_message(
            _pause_notification("build-abc123", stage_label="gate-2", rationale="gate-2 rationale")
        )

        # Fresh gate-2 message carries the apr-002 buttons + gate-2 content
        assert client.chat_postMessage.await_count == 2
        m2_kwargs = client.chat_postMessage.await_args_list[1].kwargs
        value = _button_value_from_blocks(m2_kwargs["blocks"])
        assert value["request_id"] == "apr-002"
        m2_text = " ".join(b["text"]["text"] for b in m2_kwargs["blocks"] if b.get("text"))
        assert "gate-2 rationale" in m2_text

        # The LAST update of M1 stripped its buttons (no actions block)
        m1_updates = [
            c.kwargs for c in client.chat_update.await_args_list if c.kwargs["ts"] == "1720.0001"
        ]
        assert m1_updates, "expected M1 to be updated at least once"
        assert _actions_blocks(m1_updates[-1]["blocks"]) == []

    @pytest.mark.asyncio
    async def test_gate2_pause_before_request_buttons_new_message(self) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)
        client.chat_postMessage.side_effect = [
            {"ok": True, "ts": "1720.0001"},
            {"ok": True, "ts": "1720.0002"},
        ]

        # Gate 1: request + pause → buttoned message M1
        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(
            _pause_notification("build-abc123", stage_label="gate-1", rationale="gate-1 rationale")
        )

        # Gate 2: pause first (no request yet), then the gate-2 request
        await notifier._deliver_pause_message(
            _pause_notification("build-abc123", stage_label="gate-2", rationale="gate-2 rationale")
        )
        await _capture(subscriber, "build-abc123", "apr-002")

        assert client.chat_postMessage.await_count == 2

        # M1 stripped when the gate-2 pause superseded it
        m1_updates = [
            c.kwargs for c in client.chat_update.await_args_list if c.kwargs["ts"] == "1720.0001"
        ]
        assert m1_updates
        assert _actions_blocks(m1_updates[-1]["blocks"]) == []

        # M2 upgraded in place with the apr-002 buttons + gate-2 content
        m2_updates = [
            c.kwargs for c in client.chat_update.await_args_list if c.kwargs["ts"] == "1720.0002"
        ]
        assert m2_updates
        value = _button_value_from_blocks(m2_updates[-1]["blocks"])
        assert value["request_id"] == "apr-002"
        m2_text = " ".join(b["text"]["text"] for b in m2_updates[-1]["blocks"] if b.get("text"))
        assert "gate-2 rationale" in m2_text


# ---------------------------------------------------------------------------
# Failed post recovery — a lost post must not consume the approval
# ---------------------------------------------------------------------------


class TestFailedPostRecovery:
    """A failed buttoned post re-parks the request and clears its dedup
    entry, so a later pause (or boot-reconcile re-emit) can still render."""

    @pytest.mark.asyncio
    async def test_failed_buttoned_post_reparks_request(self) -> None:
        from slack_sdk.errors import SlackApiError

        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response=MagicMock(status_code=404),
        )
        await _capture(subscriber, "build-abc123", "apr-001")
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        # The approval is back in the pending map with its dedup cleared
        assert notifier._pending_approvals["build-abc123"].request_id == "apr-001"
        assert "apr-001" not in notifier._seen_request_ids

        # A retried pause now renders the buttons
        client.chat_postMessage.side_effect = None
        client.chat_postMessage.return_value = {"ok": True, "ts": "1720.0009"}
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))

        value = _button_value_from_blocks(client.chat_postMessage.await_args.kwargs["blocks"])
        assert value["request_id"] == "apr-001"


# ---------------------------------------------------------------------------
# Dedup-window eviction — the seen map must not grow or dedup forever
# ---------------------------------------------------------------------------


class TestDedupWindowEviction:
    """Expired dedup entries and pause records are swept, so a re-emit
    after the window is treated as a fresh capture (not silently dropped)."""

    @pytest.mark.asyncio
    async def test_expired_window_allows_recapture(self, clock: FakeClock) -> None:
        notifier, client = _make_notifier()
        subscriber = _make_subscriber(notifier)

        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=300)
        await notifier._deliver_pause_message(_pause_notification("build-abc123"))
        assert client.chat_postMessage.await_count == 1

        # Past both the 300s dedup window and the 3600s registry TTL
        clock.advance(3601.0)
        await _capture(subscriber, "build-abc123", "apr-001", timeout_seconds=300)

        # Re-captured as fresh pending (seen map swept) …
        assert notifier._pending_approvals["build-abc123"].request_id == "apr-001"
        # … and NOT treated as a defer-refresh of the expired record
        # (registry swept — no chat.update was issued)
        client.chat_update.assert_not_awaited()


# ---------------------------------------------------------------------------
# build_app_state wiring — the subscriber is actually constructed in prod
# ---------------------------------------------------------------------------


def _lifecycle_patches(fake_nats: Any) -> list[Any]:
    """The standard build_app_state patch stack (mirrors
    test_lifecycle_notification_sink_wiring.py)."""
    import io

    fake_live_registry = MagicMock()
    fake_live_registry.snapshot = MagicMock(return_value=[])
    fake_live_registry.close = AsyncMock()
    fake_live_registry.subscribe_updates = AsyncMock(return_value=None)

    fake_forge_subscriber = MagicMock()
    fake_forge_subscriber.start = AsyncMock()
    fake_forge_subscriber.stop = AsyncMock()
    fake_forge_subscriber.bind_session_manager = MagicMock()
    fake_forge_subscriber.bind_notification_sink = MagicMock()

    return [
        patch("sys.stderr", new=io.StringIO()),
        patch(
            "jarvis.infrastructure.lifecycle._connect_nats",
            new=AsyncMock(return_value=fake_nats),
        ),
        patch(
            "jarvis.infrastructure.lifecycle._connect_memory",
            new=AsyncMock(return_value=None),
        ),
        patch("jarvis.infrastructure.lifecycle.register_on_fleet", new=AsyncMock()),
        patch(
            "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
            new=AsyncMock(return_value=fake_live_registry),
        ),
        patch("jarvis.infrastructure.lifecycle.heartbeat_loop", new=AsyncMock()),
        patch(
            "jarvis.infrastructure.lifecycle.build_supervisor",
            return_value=MagicMock(),
        ),
        patch(
            "jarvis.infrastructure.lifecycle.build_async_subagents",
            return_value=[],
        ),
        patch(
            "jarvis.infrastructure.lifecycle.ForgeNotificationsSubscriber",
            return_value=fake_forge_subscriber,
        ),
    ]


def _stub_config() -> Any:
    from pathlib import Path

    from jarvis.config.settings import JarvisConfig

    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists()
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
        )
    cfg.validate_provider_keys()
    return cfg


class TestBuildAppStateApprovalWiring:
    """build_app_state constructs + starts the subscriber iff NATS is up
    AND at least one consumer surface (a live SlackNotifier for build pauses,
    OR the TASK-SPL003-J02 planning-checkpoint renderer) is configured. With no
    planning channel in the stub config the renderer is None and the subscriber
    is wired for the build-pause surface only (``planning_renderer=None``)."""

    @pytest.mark.asyncio
    async def test_constructed_and_started_with_nats_and_slack_notifier(
        self,
    ) -> None:
        import contextlib

        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()
        real_sink, _client = _make_notifier()

        fake_cls = MagicMock()
        fake_instance = MagicMock()
        fake_instance.start = AsyncMock()
        fake_instance.stop = AsyncMock()
        fake_cls.return_value = fake_instance

        patches = [
            *_lifecycle_patches(fake_nats),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=real_sink,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ApprovalRequestsSubscriber",
                fake_cls,
            ),
        ]
        from contextlib import ExitStack

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            state = await build_app_state(_stub_config())

        fake_cls.assert_called_once_with(
            nats_client=fake_nats, notifier=real_sink, planning_renderer=None
        )
        fake_instance.start.assert_awaited_once()
        assert state.approval_subscriber is fake_instance

        # Cleanup: stop the (really started) sink and the heartbeat task
        await real_sink.stop()
        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task

    @pytest.mark.asyncio
    async def test_not_constructed_when_sink_is_noop(self) -> None:
        import contextlib

        from jarvis.infrastructure.lifecycle import build_app_state
        from jarvis.infrastructure.slack_notifier import NoOpSink

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_cls = MagicMock()

        patches = [
            *_lifecycle_patches(fake_nats),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=NoOpSink(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ApprovalRequestsSubscriber",
                fake_cls,
            ),
        ]
        from contextlib import ExitStack

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            state = await build_app_state(_stub_config())

        fake_cls.assert_not_called()
        assert state.approval_subscriber is None

        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task

    @pytest.mark.asyncio
    async def test_constructed_for_planning_renderer_even_when_sink_is_noop(self) -> None:
        """TASK-SPL003-J02: a NoOp forge sink but a configured planning renderer
        still wires the subscriber — with notifier=None, planning_renderer set —
        so the assumption dialogue is not gated behind the forge sink (arch F2)."""
        import contextlib

        from jarvis.infrastructure.lifecycle import build_app_state
        from jarvis.infrastructure.slack_notifier import NoOpSink

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_cls = MagicMock()
        fake_instance = MagicMock()
        fake_instance.start = AsyncMock()
        fake_instance.stop = AsyncMock()
        fake_cls.return_value = fake_instance
        fake_renderer = MagicMock()

        patches = [
            *_lifecycle_patches(fake_nats),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_sink",
                return_value=NoOpSink(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.create_planning_checkpoint_renderer",
                return_value=fake_renderer,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.ApprovalRequestsSubscriber",
                fake_cls,
            ),
        ]
        from contextlib import ExitStack

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            state = await build_app_state(_stub_config())

        fake_cls.assert_called_once_with(
            nats_client=fake_nats, notifier=None, planning_renderer=fake_renderer
        )
        fake_instance.start.assert_awaited_once()
        assert state.approval_subscriber is fake_instance

        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task


# ---------------------------------------------------------------------------
# Seam tests — WIDENED_FORGENOTIFICATION consumer contract (TASK-JNB-005)
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("WIDENED_FORGENOTIFICATION")
class TestPauseProjectionContract:
    """Contract: pause projection retains approval_subject; new fields are
    optional with None defaults so CLI rendering is unaffected."""

    def test_pause_projection_round_trips_approval_subject_and_renders_score_none(
        self,
    ) -> None:
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="corr-seam-1",
            feature_id="FEAT-ABC1",
            completed_at=datetime.now(UTC),
            build_id="build-abc123",
            approval_subject="agents.approval.forge.build-abc123",
            coach_score=None,
        )
        # approval_subject survives a serialize/deserialize round trip
        restored = ForgeNotification.model_validate(notification.model_dump())
        assert restored.approval_subject == "agents.approval.forge.build-abc123"
        assert restored.build_id == "build-abc123"
        # coach_score None must render, not raise: 'score unavailable' per
        # ADR-ARCH-033
        blocks = build_pause_blocks(restored)
        rendered_text = " ".join(b["text"]["text"] for b in blocks if b.get("text"))
        # No score is the live default; the card says nothing about it
        # rather than printing the old "score unavailable" non-answer.
        assert "score" not in rendered_text.lower()
        # all text objects are plain_text (mrkdwn disabled)
        assert all(b["text"]["type"] == "plain_text" for b in blocks if b.get("text"))

    def test_widened_fields_default_none_so_pre_widening_construction_still_validates(
        self,
    ) -> None:
        # New optional fields must default to None: a minimal pre-widening
        # construction must validate unchanged.
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="corr-seam-2",
            feature_id="FEAT-ABC2",
            completed_at=datetime.now(UTC),
        )
        assert notification.approval_subject is None
        assert notification.coach_score is None
        assert notification.build_id is None

    @pytest.mark.asyncio
    async def test_pause_projection_populates_build_id_from_payload(self) -> None:
        """The subscriber's pause projection must retain build_id — the
        join key this task's pending map depends on."""
        from jarvis.infrastructure.forge_notifications import (
            ForgeNotificationsSubscriber,
        )

        subscriber = ForgeNotificationsSubscriber(
            nats_client=MagicMock(),
            routing_history_writer=MagicMock(),
        )
        sink = MagicMock()
        sink.notify = AsyncMock()
        subscriber.bind_notification_sink(sink)

        envelope = {
            "source_id": "forge",
            "event_type": "build_paused",
            "correlation_id": "corr-pp-1",
            "payload": {
                "feature_id": "FEAT-ABC1",
                "build_id": "build-abc123",
                # Contract key per nats-core BuildPausedPayload — NOT
                # "stage" (review fix: real forge traffic serializes
                # stage_label; the projection must read that key).
                "stage_label": "autobuild",
                "gate_mode": "MANDATORY_HUMAN_APPROVAL",
                "coach_score": None,
                "rationale": "needs a human",
                "approval_subject": "agents.approval.forge.build-abc123",
                "paused_at": "2026-07-05T10:00:00+00:00",
                "correlation_id": "corr-pp-1",
            },
        }
        msg = SimpleNamespace(subject="pipeline.build-paused.FEAT-ABC1")
        msg.data = json.dumps(envelope).encode()

        await subscriber._on_message(msg)

        sink.notify.assert_awaited_once()
        projected = sink.notify.await_args.args[0]
        assert projected.build_id == "build-abc123"
        assert projected.stage_label == "autobuild"
        assert projected.approval_subject == ("agents.approval.forge.build-abc123")
