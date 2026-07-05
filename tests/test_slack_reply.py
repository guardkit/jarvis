"""Tests for TASK-JNB-104 — Socket Mode reply path with operator auth.

Plain pytest only — NO pytest-bdd ``.feature`` glue (operator decision
2026-07-03). Test classes mirror the FEAT-UBS-003 spec scenario names for
the reply path.

Coverage (mapped to TASK-JNB-104 acceptance criteria):

* AC — every block_actions envelope acked immediately, before any
  authorization/parsing/publish work
* AC — unauthorized click: WARN + ephemeral refusal, nothing published
* AC — authorized approve/reject publish ApprovalResponsePayload with
  request_id from the button value, decided_by verbatim, to
  ``approval_subject + ".response"`` carrying the request's correlation_id
* AC — double-click publishes at most once client-side (first-click-wins)
* AC — successful publish → chat.update disables buttons + shows decision
* AC — publish failure → WARNING + buttons re-enabled, no exception (DDR-007)
* AC — malformed action payloads dropped with a log entry; client keeps
  running
* AC — reconnect never duplicates handlers / re-publishes (one-time
  registration; first-click state on the handler instance)
* AC — no-op mode when app token / operator id absent; supervisor runs
* C1 (Phase 2.5B review) — success-update failure after a durable publish
  never restores the buttons and keeps first-click-wins marked

No live Slack or NATS anywhere: SocketModeClient, AsyncWebClient, and the
JetStream context are mocked with unittest.mock.AsyncMock.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.slack_reply import (
    NatsApprovalResponsePublisher,
    SlackSocketModeReplyClient,
    build_reply_handler,
    create_slack_reply_client,
    parse_button_value,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPERATOR = "U0OPERATOR"


def _button_value(
    request_id: str = "apr-001",
    build_id: str = "build-abc123",
    correlation_id: str = "corr-1",
    approval_subject: str = "agents.approval.forge.build-abc123",
) -> str:
    return json.dumps(
        {
            "request_id": request_id,
            "build_id": build_id,
            "correlation_id": correlation_id,
            "approval_subject": approval_subject,
        },
        separators=(",", ":"),
    )


def _original_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "section",
            "text": {"type": "plain_text", "text": "build-paused", "emoji": False},
        },
        {"type": "actions", "block_id": "forge_approval", "elements": []},
    ]


def _click_payload(
    *,
    user_id: str = _OPERATOR,
    action_id: str = "forge_approve",
    value: str | None = None,
    channel_id: str | None = "C123456",
    message_ts: str = "1720.0001",
    blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "block_actions",
        "user": {"id": user_id},
        "container": {
            "type": "message",
            "channel_id": channel_id,
            "message_ts": message_ts,
        },
        "message": {"blocks": blocks if blocks is not None else _original_blocks()},
        "actions": [
            {
                "action_id": action_id,
                "block_id": "forge_approval",
                "value": value if value is not None else _button_value(),
            }
        ],
    }
    if channel_id is not None:
        payload["channel"] = {"id": channel_id}
    return payload


def _make_handler(
    *,
    operator: str | None = _OPERATOR,
    decided_by: str | None = "jarvis-op",
    web_client: Any | None = "default",
) -> tuple[Any, MagicMock, Any, Any]:
    settings = SimpleNamespace(
        slack_operator_user_id=operator,
        slack_decided_by=decided_by,
    )
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    client = AsyncMock() if web_client == "default" else web_client
    handler = build_reply_handler(settings=settings, publisher=publisher, web_client=client)
    return handler, publisher, client, settings


def _actions_in(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "actions"]


# ---------------------------------------------------------------------------
# Ack ordering — before any authorization/parse/publish work
# ---------------------------------------------------------------------------


class TestAckBeforeAuthorization:
    """The envelope ack is the listener's first act."""

    @pytest.mark.asyncio
    async def test_ack_sent_before_handler_work(self) -> None:
        order: list[str] = []

        class SpyHandler:
            async def handle_block_actions(self, payload: dict[str, Any]) -> None:
                order.append("handled")

        client = SlackSocketModeReplyClient(
            app_token="xapp-test",
            handler=SpyHandler(),  # type: ignore[arg-type]
            web_client=AsyncMock(),
        )

        socket_client = MagicMock()

        async def _send_ack(response: Any) -> None:
            order.append("ack")

        socket_client.send_socket_mode_response = AsyncMock(side_effect=_send_ack)

        req = SimpleNamespace(type="interactive", envelope_id="env-1", payload=_click_payload())
        await client._on_request(socket_client, req)

        assert order == ["ack", "handled"]

    @pytest.mark.asyncio
    async def test_non_interactive_envelopes_still_acked(self) -> None:
        client = SlackSocketModeReplyClient(
            app_token="xapp-test",
            handler=MagicMock(),
            web_client=AsyncMock(),
        )
        socket_client = MagicMock()
        socket_client.send_socket_mode_response = AsyncMock()

        req = SimpleNamespace(type="events_api", envelope_id="env-2", payload={})
        await client._on_request(socket_client, req)

        socket_client.send_socket_mode_response.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ack_failure_never_raises_and_handler_still_runs(self) -> None:
        handled = AsyncMock()
        handler = MagicMock()
        handler.handle_block_actions = handled

        client = SlackSocketModeReplyClient(
            app_token="xapp-test",
            handler=handler,
            web_client=AsyncMock(),
        )
        socket_client = MagicMock()
        socket_client.send_socket_mode_response = AsyncMock(
            side_effect=RuntimeError("mid-reconnect")
        )

        req = SimpleNamespace(type="interactive", envelope_id="env-3", payload=_click_payload())
        await client._on_request(socket_client, req)  # must not raise
        handled.assert_awaited_once()


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class TestUnauthorizedClickRefused:
    """The sole Slack-side gate is the operator member id."""

    @pytest.mark.asyncio
    async def test_wrong_user_never_publishes_and_gets_ephemeral_refusal(
        self,
    ) -> None:
        handler, publisher, web_client, _ = _make_handler()

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload(user_id="U0EVIL"))

        publisher.publish.assert_not_awaited()
        web_client.chat_update.assert_not_awaited()
        web_client.chat_postEphemeral.assert_awaited_once()
        kwargs = web_client.chat_postEphemeral.await_args.kwargs
        assert kwargs["user"] == "U0EVIL"
        assert kwargs["channel"] == "C123456"
        assert any(log["event"] == "slack_reply_unauthorized_click" for log in logs)

    @pytest.mark.asyncio
    async def test_unset_operator_id_refuses_everyone(self) -> None:
        handler, publisher, _, _ = _make_handler(operator=None)

        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_refusal_channel_falls_back_to_container(self) -> None:
        handler, publisher, web_client, _ = _make_handler()
        payload = _click_payload(user_id="U0EVIL")
        del payload["channel"]  # container.channel_id remains

        await handler.handle_block_actions(payload)

        publisher.publish.assert_not_awaited()
        assert web_client.chat_postEphemeral.await_args.kwargs["channel"] == "C123456"

    @pytest.mark.asyncio
    async def test_refusal_failure_never_raises(self) -> None:
        handler, publisher, web_client, _ = _make_handler()
        web_client.chat_postEphemeral.side_effect = RuntimeError("slack down")

        await handler.handle_block_actions(_click_payload(user_id="U0EVIL"))

        publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# Authorized clicks publish
# ---------------------------------------------------------------------------


class TestAuthorizedApprovePublishes:
    @pytest.mark.asyncio
    async def test_approve_publishes_correct_payload_subject_and_correlation(
        self,
    ) -> None:
        handler, publisher, _web_client, _ = _make_handler(decided_by="jarvis-op")

        await handler.handle_block_actions(_click_payload(action_id="forge_approve"))

        publisher.publish.assert_awaited_once()
        kwargs = publisher.publish.await_args.kwargs
        assert kwargs["subject"] == ("agents.approval.forge.build-abc123.response")
        assert kwargs["correlation_id"] == "corr-1"
        published = kwargs["payload"]
        assert published.request_id == "apr-001"
        assert published.decision == "approve"
        assert published.decided_by == "jarvis-op"

    @pytest.mark.asyncio
    async def test_success_update_disables_buttons_and_shows_decision(self) -> None:
        handler, _, web_client, _ = _make_handler()

        await handler.handle_block_actions(_click_payload(action_id="forge_approve"))

        # Last chat.update is the success update: no actions block, shows
        # the recorded decision.
        final_kwargs = web_client.chat_update.await_args.kwargs
        assert final_kwargs["ts"] == "1720.0001"
        assert _actions_in(final_kwargs["blocks"]) == []
        joined = " ".join(b["text"]["text"] for b in final_kwargs["blocks"] if b.get("text"))
        assert "Decision recorded: approve" in joined


class TestAuthorizedRejectPublishes:
    @pytest.mark.asyncio
    async def test_reject_publishes_decision_reject(self) -> None:
        handler, publisher, _, _ = _make_handler()

        await handler.handle_block_actions(_click_payload(action_id="forge_reject"))

        published = publisher.publish.await_args.kwargs["payload"]
        assert published.decision == "reject"


# ---------------------------------------------------------------------------
# First-click-wins
# ---------------------------------------------------------------------------


class TestDoubleClickPublishesAtMostOnce:
    @pytest.mark.asyncio
    async def test_sequential_double_click_publishes_once(self) -> None:
        handler, publisher, _, _ = _make_handler()

        await handler.handle_block_actions(_click_payload())
        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_concurrent_double_click_publishes_once(self) -> None:
        """The check-and-mark is synchronous — two concurrently scheduled
        listener tasks (the SDK's asyncio.ensure_future dispatch) must
        still publish at most once."""
        handler, publisher, _, _ = _make_handler()

        release = asyncio.Event()

        async def slow_publish(**kwargs: Any) -> None:
            await release.wait()

        publisher.publish = AsyncMock(side_effect=slow_publish)

        first = asyncio.create_task(handler.handle_block_actions(_click_payload()))
        second = asyncio.create_task(handler.handle_block_actions(_click_payload()))
        await asyncio.sleep(0.01)
        release.set()
        await asyncio.gather(first, second)

        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_distinct_request_ids_both_publish(self) -> None:
        handler, publisher, _, _ = _make_handler()

        await handler.handle_block_actions(
            _click_payload(value=_button_value(request_id="apr-001"))
        )
        await handler.handle_block_actions(
            _click_payload(value=_button_value(request_id="apr-002"))
        )

        assert publisher.publish.await_count == 2


# ---------------------------------------------------------------------------
# Malformed payloads
# ---------------------------------------------------------------------------


class TestMalformedActionPayloadDropped:
    @pytest.mark.asyncio
    async def test_unparseable_value_json_dropped(self) -> None:
        handler, publisher, _, _ = _make_handler()

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload(value="{not-json"))

        publisher.publish.assert_not_awaited()
        assert any(log["event"] == "slack_reply_malformed_value_dropped" for log in logs)

    @pytest.mark.asyncio
    async def test_missing_keys_dropped(self) -> None:
        handler, publisher, _, _ = _make_handler()

        await handler.handle_block_actions(
            _click_payload(value=json.dumps({"request_id": "apr-001"}))
        )

        publisher.publish.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_action_id_dropped(self) -> None:
        handler, publisher, _, _ = _make_handler()

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload(action_id="something_else"))

        publisher.publish.assert_not_awaited()
        assert any(log["event"] == "slack_reply_unknown_action_dropped" for log in logs)

    @pytest.mark.asyncio
    async def test_empty_actions_list_dropped_without_exception(self) -> None:
        handler, publisher, _, _ = _make_handler()
        payload = _click_payload()
        payload["actions"] = []

        await handler.handle_block_actions(payload)  # must not raise

        publisher.publish.assert_not_awaited()


# ---------------------------------------------------------------------------
# Publish failure — re-enable buttons
# ---------------------------------------------------------------------------


class TestPublishFailureReenablesButtons:
    @pytest.mark.asyncio
    async def test_publish_failure_warns_restores_blocks_and_allows_retry(
        self,
    ) -> None:
        handler, publisher, web_client, _ = _make_handler()
        publisher.publish = AsyncMock(side_effect=RuntimeError("broker gone"))

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload())  # no exception

        assert any(log["event"] == "slack_reply_publish_failed" for log in logs)
        # The LAST chat.update restored the original blocks (buttons back)
        restore_kwargs = web_client.chat_update.await_args.kwargs
        assert _actions_in(restore_kwargs["blocks"]) != []

        # Retry after the failure publishes (first-click-wins un-marked)
        publisher.publish = AsyncMock()
        await handler.handle_block_actions(_click_payload())
        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_update_failure_never_restores_buttons(self) -> None:
        """C1: after a durable publish, a failing success-update must not
        re-enable the buttons nor un-mark first-click-wins."""
        handler, publisher, web_client, _ = _make_handler()

        update_calls: list[dict[str, Any]] = []

        async def failing_update(**kwargs: Any) -> None:
            update_calls.append(kwargs)
            if len(update_calls) >= 2:  # the success update
                raise RuntimeError("slack down")

        web_client.chat_update = AsyncMock(side_effect=failing_update)

        await handler.handle_block_actions(_click_payload())  # no exception

        publisher.publish.assert_awaited_once()
        # No third update (no restore) — and every update issued removed
        # the actions block (optimistic + success, never original blocks)
        assert len(update_calls) == 2
        for kwargs in update_calls:
            assert _actions_in(kwargs["blocks"]) == []

        # First-click-wins stays marked: a re-click never re-publishes
        await handler.handle_block_actions(_click_payload())
        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_optimistic_update_failure_does_not_skip_publish(self) -> None:
        """C2: an optimistic-disable failure must not short-circuit the
        publish."""
        handler, publisher, web_client, _ = _make_handler()
        web_client.chat_update = AsyncMock(side_effect=RuntimeError("slack down"))

        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_none_web_client_still_publishes(self) -> None:
        """Intentional degrade: without a web client, UI updates are
        logged no-ops but authorization + publish still run."""
        handler, publisher, _, _ = _make_handler(web_client=None)

        await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# decided_by guard
# ---------------------------------------------------------------------------


class TestDecidedByUnsetRefusesToPublish:
    @pytest.mark.asyncio
    async def test_unset_decided_by_warns_and_publishes_nothing(self) -> None:
        handler, publisher, _, _ = _make_handler(decided_by=None)

        with capture_logs() as logs:
            await handler.handle_block_actions(_click_payload())

        publisher.publish.assert_not_awaited()
        assert any(log["event"] == "slack_reply_decided_by_unset" for log in logs)

        # Not permanently consumed: once configured, a re-click publishes
        handler._settings.slack_decided_by = "jarvis-op"
        await handler.handle_block_actions(_click_payload())
        publisher.publish.assert_awaited_once()


# ---------------------------------------------------------------------------
# Reconnect / lifecycle of the Socket Mode client
# ---------------------------------------------------------------------------


class TestReconnectNoDuplicateHandlersOrPublishes:
    @pytest.mark.asyncio
    async def test_start_registers_exactly_one_listener_and_is_idempotent(
        self,
    ) -> None:
        handler, _, _, _ = _make_handler()
        reply_client = SlackSocketModeReplyClient(
            app_token="xapp-test", handler=handler, web_client=AsyncMock()
        )

        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient") as mock_cls:
            sdk_client = MagicMock()
            sdk_client.socket_mode_request_listeners = []
            listeners_at_connect: list[int] = []

            async def _connect() -> None:
                listeners_at_connect.append(len(sdk_client.socket_mode_request_listeners))

            sdk_client.connect = AsyncMock(side_effect=_connect)
            mock_cls.return_value = sdk_client

            await reply_client.start()
            await reply_client.start()  # idempotent — no re-registration

        mock_cls.assert_called_once()
        assert len(sdk_client.socket_mode_request_listeners) == 1
        sdk_client.connect.assert_awaited_once()
        # Registration precedes connect (SDK's process_messages starts in
        # __init__) — the listener was present when connect() was awaited.
        assert listeners_at_connect == [1]

    @pytest.mark.asyncio
    async def test_first_click_state_survives_reconnect(self) -> None:
        """A reconnect replaces only the SDK session; the handler (and its
        first-click-wins state) is untouched, so a redelivered click after
        reconnect never re-publishes."""
        handler, publisher, _, _ = _make_handler()
        reply_client = SlackSocketModeReplyClient(
            app_token="xapp-test", handler=handler, web_client=AsyncMock()
        )

        socket_client = MagicMock()
        socket_client.send_socket_mode_response = AsyncMock()
        req = SimpleNamespace(type="interactive", envelope_id="env-1", payload=_click_payload())

        await reply_client._on_request(socket_client, req)
        # Simulate the SDK reconnecting: a new session delivers the same
        # interaction again (missed-ack redelivery).
        await reply_client._on_request(socket_client, req)

        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_is_bounded_and_never_raises(self) -> None:
        handler, _, _, _ = _make_handler()
        reply_client = SlackSocketModeReplyClient(
            app_token="xapp-test", handler=handler, web_client=AsyncMock()
        )

        with patch("slack_sdk.socket_mode.aiohttp.SocketModeClient") as mock_cls:
            sdk_client = MagicMock()
            sdk_client.socket_mode_request_listeners = []
            sdk_client.connect = AsyncMock()
            sdk_client.close = AsyncMock(side_effect=RuntimeError("ws gone"))
            mock_cls.return_value = sdk_client

            await reply_client.start()
            await reply_client.stop()  # swallows the close error
            await reply_client.stop()  # idempotent


# ---------------------------------------------------------------------------
# Bounded connect — the SDK's infinite retry loop must not wedge boot
# ---------------------------------------------------------------------------


class TestBoundedConnect:
    """slack-sdk's connect() never raises (infinite retry) — start() must
    bound it so a bad app token / Slack outage cannot hang build_app_state
    (review fix, CRITICAL)."""

    @pytest.mark.asyncio
    async def test_hanging_connect_times_out_and_closes_sdk_client(self) -> None:
        handler, _, _, _ = _make_handler()
        reply_client = SlackSocketModeReplyClient(
            app_token="xapp-test", handler=handler, web_client=AsyncMock()
        )

        async def hang() -> None:
            await asyncio.Event().wait()  # the SDK's retry loop, in spirit

        with (
            patch("slack_sdk.socket_mode.aiohttp.SocketModeClient") as mock_cls,
            patch("jarvis.infrastructure.slack_reply._CONNECT_TIMEOUT_SECONDS", 0.05),
        ):
            sdk_client = MagicMock()
            sdk_client.socket_mode_request_listeners = []
            sdk_client.connect = AsyncMock(side_effect=hang)
            sdk_client.close = AsyncMock()
            mock_cls.return_value = sdk_client

            with pytest.raises(TimeoutError):
                await reply_client.start()

        # The half-started SDK client was cleaned up (its __init__ spawns
        # process_messages + an aiohttp session).
        sdk_client.close.assert_awaited_once()
        assert reply_client._client is None
        assert reply_client._started is False

    @pytest.mark.asyncio
    async def test_build_app_state_soft_fails_when_connect_hangs(self) -> None:
        """Drives the REAL factory + start() through lifecycle: the boot
        must complete with slack_reply_client=None (DDR-021), replacing
        the mock-only soft-fail evidence flagged by the review."""
        import contextlib
        from contextlib import ExitStack
        from pathlib import Path

        from jarvis.config.settings import JarvisConfig
        from jarvis.infrastructure.lifecycle import build_app_state

        project_root = Path(__file__).resolve().parent.parent
        stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
        with patch.dict(
            "os.environ",
            {
                "JARVIS_SLACK_BOT_TOKEN": "xoxb-t",
                "JARVIS_SLACK_APP_TOKEN": "xapp-t",
                "JARVIS_SLACK_OPERATOR_USER_ID": _OPERATOR,
            },
            clear=True,
        ):
            cfg = JarvisConfig(
                stub_capabilities_path=stub_path,
                llama_swap_base_url="http://fake-llama-swap:9000",
                graphiti_endpoint=None,
            )
        cfg.validate_provider_keys()

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        async def hang() -> None:
            await asyncio.Event().wait()

        sdk_client = MagicMock()
        sdk_client.socket_mode_request_listeners = []
        sdk_client.connect = AsyncMock(side_effect=hang)
        sdk_client.close = AsyncMock()

        patches = [
            *_lifecycle_patches(fake_nats),
            patch(
                "slack_sdk.socket_mode.aiohttp.SocketModeClient",
                return_value=sdk_client,
            ),
            patch("jarvis.infrastructure.slack_reply._CONNECT_TIMEOUT_SECONDS", 0.05),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            state = await asyncio.wait_for(build_app_state(cfg), timeout=10.0)

        # Boot completed; the reply path degraded to None per DDR-021.
        assert state.slack_reply_client is None
        sdk_client.close.assert_awaited_once()

        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task


# ---------------------------------------------------------------------------
# Cross-task decision serialization (review fix)
# ---------------------------------------------------------------------------


class TestDecisionSequenceSerialized:
    """A failed attempt's restore can never land after a concurrent
    retry's durable publish — the decision sequence holds a lock."""

    @pytest.mark.asyncio
    async def test_failed_restore_completes_before_concurrent_retry_publishes(
        self,
    ) -> None:
        handler, publisher, web_client, _ = _make_handler()

        events: list[str] = []
        publisher.publish = AsyncMock(side_effect=[RuntimeError("broker blip"), None])

        async def record_update(**kwargs: Any) -> None:
            blocks = kwargs.get("blocks") or []
            if _actions_in(blocks):
                events.append("restore")
            else:
                joined = " ".join(b["text"]["text"] for b in blocks if b.get("text"))
                events.append("success" if "Decision recorded" in joined else "optimistic")
            await asyncio.sleep(0.01)  # let the other task try to interleave

        web_client.chat_update = AsyncMock(side_effect=record_update)

        first = asyncio.create_task(handler.handle_block_actions(_click_payload()))
        retry = asyncio.create_task(handler.handle_block_actions(_click_payload()))
        await asyncio.gather(first, retry)

        assert publisher.publish.await_count == 2
        # The failed attempt's restore strictly precedes the retry's
        # updates; the LAST update visible to the operator is the
        # success update, never a restore.
        assert events == ["optimistic", "restore", "optimistic", "success"]


# ---------------------------------------------------------------------------
# Missing message.blocks — never destroy what cannot be restored
# ---------------------------------------------------------------------------


class TestMissingMessageBlocks:
    """Without message.blocks in the interaction payload, the optimistic
    disable is skipped (nothing restorable) but publish still runs."""

    @pytest.mark.asyncio
    async def test_publish_failure_without_blocks_issues_no_updates(self) -> None:
        handler, publisher, web_client, _ = _make_handler()
        publisher.publish = AsyncMock(side_effect=RuntimeError("broker gone"))

        payload = _click_payload()
        del payload["message"]

        await handler.handle_block_actions(payload)

        publisher.publish.assert_awaited_once()
        web_client.chat_update.assert_not_awaited()  # nothing destroyed

        # Retry still possible (first-click-wins un-marked)
        publisher.publish = AsyncMock()
        await handler.handle_block_actions(payload)
        publisher.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_without_blocks_still_shows_decision(self) -> None:
        handler, publisher, web_client, _ = _make_handler()

        payload = _click_payload()
        del payload["message"]

        await handler.handle_block_actions(payload)

        publisher.publish.assert_awaited_once()
        # Exactly one update: the success update (no optimistic pass)
        web_client.chat_update.assert_awaited_once()
        blocks = web_client.chat_update.await_args.kwargs["blocks"]
        joined = " ".join(b["text"]["text"] for b in blocks if b.get("text"))
        assert "Decision recorded: approve" in joined


# ---------------------------------------------------------------------------
# No-op mode
# ---------------------------------------------------------------------------


class TestNoOpModeWhenConfigAbsent:
    def _config(self, **env: str) -> Any:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", env, clear=True):
            return JarvisConfig()

    def test_none_when_app_token_missing(self) -> None:
        config = self._config(
            JARVIS_SLACK_BOT_TOKEN="xoxb-t",
            JARVIS_SLACK_OPERATOR_USER_ID=_OPERATOR,
        )
        assert create_slack_reply_client(config, MagicMock()) is None

    def test_none_when_operator_id_missing(self) -> None:
        config = self._config(
            JARVIS_SLACK_BOT_TOKEN="xoxb-t",
            JARVIS_SLACK_APP_TOKEN="xapp-t",
        )
        assert create_slack_reply_client(config, MagicMock()) is None

    def test_none_when_bot_token_missing(self) -> None:
        config = self._config(
            JARVIS_SLACK_APP_TOKEN="xapp-t",
            JARVIS_SLACK_OPERATOR_USER_ID=_OPERATOR,
        )
        assert create_slack_reply_client(config, MagicMock()) is None

    def test_none_when_nats_unavailable(self) -> None:
        config = self._config(
            JARVIS_SLACK_BOT_TOKEN="xoxb-t",
            JARVIS_SLACK_APP_TOKEN="xapp-t",
            JARVIS_SLACK_OPERATOR_USER_ID=_OPERATOR,
        )
        assert create_slack_reply_client(config, None) is None

    def test_constructed_when_fully_configured(self) -> None:
        config = self._config(
            JARVIS_SLACK_BOT_TOKEN="xoxb-t",
            JARVIS_SLACK_APP_TOKEN="xapp-t",
            JARVIS_SLACK_OPERATOR_USER_ID=_OPERATOR,
        )
        client = create_slack_reply_client(config, MagicMock())
        assert isinstance(client, SlackSocketModeReplyClient)


# ---------------------------------------------------------------------------
# Publisher — envelope + subject shape
# ---------------------------------------------------------------------------


class TestNatsApprovalResponsePublisher:
    @pytest.mark.asyncio
    async def test_publishes_enveloped_payload_to_subject(self) -> None:
        from nats_core.events import ApprovalResponsePayload

        js = MagicMock()
        js.publish = AsyncMock()
        nats_client = MagicMock()
        nats_client.js = js

        publisher = NatsApprovalResponsePublisher(nats_client)
        payload = ApprovalResponsePayload(
            request_id="apr-001",
            decision="approve",
            decided_by="jarvis-op",
        )
        await publisher.publish(
            subject="agents.approval.forge.build-abc123.response",
            payload=payload,
            correlation_id="corr-1",
        )

        js.publish.assert_awaited_once()
        subject, data = js.publish.await_args.args
        assert subject == "agents.approval.forge.build-abc123.response"
        envelope = json.loads(data.decode("utf-8"))
        assert envelope["source_id"] == "jarvis"
        assert envelope["event_type"] == "approval_response"
        assert envelope["correlation_id"] == "corr-1"
        assert envelope["payload"]["request_id"] == "apr-001"
        assert envelope["payload"]["decision"] == "approve"
        assert envelope["payload"]["decided_by"] == "jarvis-op"

    @pytest.mark.asyncio
    async def test_publish_failure_propagates_to_caller(self) -> None:
        js = MagicMock()
        js.publish = AsyncMock(side_effect=RuntimeError("broker gone"))
        nats_client = MagicMock()
        nats_client.js = js

        from nats_core.events import ApprovalResponsePayload

        publisher = NatsApprovalResponsePublisher(nats_client)
        with pytest.raises(RuntimeError):
            await publisher.publish(
                subject="agents.approval.forge.b.response",
                payload=ApprovalResponsePayload(
                    request_id="apr-001",
                    decision="reject",
                    decided_by="jarvis-op",
                ),
                correlation_id=None,
            )


# ---------------------------------------------------------------------------
# Lifecycle wiring (build_app_state)
# ---------------------------------------------------------------------------


def _lifecycle_patches(fake_nats: Any) -> list[Any]:
    """Standard build_app_state patch stack (mirrors
    tests/test_slack_approval_buttons.py)."""
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

    fake_sink = MagicMock()
    fake_sink.start = AsyncMock()
    fake_sink.stop = AsyncMock()

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
        patch(
            "jarvis.infrastructure.lifecycle.create_slack_sink",
            return_value=fake_sink,
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


class TestBuildAppStateReplyWiring:
    """The reply client is constructed + started + shut down by lifecycle."""

    @pytest.mark.asyncio
    async def test_constructed_and_started_when_factory_returns_client(
        self,
    ) -> None:
        import contextlib
        from contextlib import ExitStack

        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_reply = MagicMock()
        fake_reply.start = AsyncMock()
        fake_reply.stop = AsyncMock()
        factory = MagicMock(return_value=fake_reply)

        cfg = _stub_config()
        patches = [
            *_lifecycle_patches(fake_nats),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_reply_client",
                factory,
            ),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            state = await build_app_state(cfg)

        factory.assert_called_once_with(cfg, fake_nats)
        fake_reply.start.assert_awaited_once()
        assert state.slack_reply_client is fake_reply

        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task

    @pytest.mark.asyncio
    async def test_start_failure_soft_fails_to_none(self) -> None:
        import contextlib
        from contextlib import ExitStack

        from jarvis.infrastructure.lifecycle import build_app_state

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()

        fake_reply = MagicMock()
        fake_reply.start = AsyncMock(side_effect=RuntimeError("ws refused"))
        factory = MagicMock(return_value=fake_reply)

        patches = [
            *_lifecycle_patches(fake_nats),
            patch(
                "jarvis.infrastructure.lifecycle.create_slack_reply_client",
                factory,
            ),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            state = await build_app_state(_stub_config())

        # Supervisor started and runs normally; reply path degraded
        assert state.slack_reply_client is None

        if state.fleet_heartbeat_task is not None:
            state.fleet_heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await state.fleet_heartbeat_task

    @pytest.mark.asyncio
    async def test_shutdown_stops_reply_client(self) -> None:
        from jarvis.infrastructure.lifecycle import AppState, shutdown

        reply_client = MagicMock()
        reply_client.stop = AsyncMock()

        state = AppState(
            config=MagicMock(),
            supervisor=MagicMock(),
            store=MagicMock(spec=[]),
            session_manager=MagicMock(),
            capability_registry=[],
            slack_reply_client=reply_client,
        )
        await shutdown(state)
        reply_client.stop.assert_awaited_once()


# ---------------------------------------------------------------------------
# Seam tests (task-mandated)
# ---------------------------------------------------------------------------


@pytest.fixture()
def settings() -> Any:
    return SimpleNamespace(
        slack_operator_user_id=_OPERATOR,
        slack_decided_by="initial-identity",
    )


@pytest.fixture()
def publisher_mock() -> MagicMock:
    publisher = MagicMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture()
def authorized_click_payload() -> dict[str, Any]:
    return _click_payload(user_id=_OPERATOR, action_id="forge_approve")


@pytest.mark.seam
@pytest.mark.integration_contract("BUTTON_METADATA")
def test_button_value_json_round_trips_within_slack_action_value_limit() -> None:
    """BUTTON_METADATA from TASK-JNB-103: value JSON {request_id, build_id,
    correlation_id, approval_subject} must round-trip and stay < 2000 chars
    even with max-size build/correlation ids."""
    value_dict = {
        "request_id": "apr-" + "a" * 60,  # max-size request id
        "build_id": "build-" + "b" * 250,  # max-size build id
        "correlation_id": "corr-" + "c" * 250,  # max-size correlation id
        "approval_subject": "agents.approval.forge." + "b" * 250,
    }
    value = json.dumps(value_dict)
    assert len(value) < 2000  # Slack's action value hard limit

    parsed = parse_button_value(value)  # this task's value parser
    assert parsed["request_id"] == value_dict["request_id"]
    assert parsed["build_id"] == value_dict["build_id"]
    assert parsed["correlation_id"] == value_dict["correlation_id"]
    assert parsed["approval_subject"] == value_dict["approval_subject"]


@pytest.mark.seam
@pytest.mark.integration_contract("BUTTON_METADATA")
def test_producer_value_parses_with_this_tasks_parser() -> None:
    """Cross-module seam: the value TASK-JNB-103's producer emits must be
    accepted verbatim by this task's parser."""
    from jarvis.infrastructure.slack_notifier import _build_button_value

    produced = _build_button_value(
        request_id="apr-001",
        build_id="build-abc123",
        correlation_id="corr-1",
        approval_subject="agents.approval.forge.build-abc123",
    )
    assert produced is not None
    parsed = parse_button_value(produced)
    assert parsed["request_id"] == "apr-001"
    assert parsed["approval_subject"] == "agents.approval.forge.build-abc123"


@pytest.mark.seam
@pytest.mark.integration_contract("APPROVER_IDENTITY")
@pytest.mark.asyncio
async def test_published_decided_by_equals_slack_decided_by_verbatim(
    settings: Any,
    authorized_click_payload: dict[str, Any],
    publisher_mock: MagicMock,
) -> None:
    """APPROVER_IDENTITY from TASK-JNB-101: forge accepts the response only
    if decided_by string-equals its expected_approver — exact match, no
    normalisation. A mismatch silently refuses every phone approval."""
    settings.slack_decided_by = "Jarvis-Operator"  # deliberate mixed case
    handler = build_reply_handler(settings=settings, publisher=publisher_mock)

    await handler.handle_block_actions(authorized_click_payload)

    published = publisher_mock.publish.await_args.kwargs["payload"]
    assert published.decided_by == settings.slack_decided_by  # verbatim
    assert published.decided_by == "Jarvis-Operator"  # not lowercased
    assert published.decided_by != "jarvis-operator"  # no normalisation
