"""Tests for :mod:`jarvis.infrastructure.chat_handler`.

TASK-J006-003 acceptance criteria coverage:

- AC-001: ``handle_chat_command`` extracts ``args.message`` and rejects
  missing/empty messages with a structured error ``ResultPayload``.
- AC-002: ``session_manager.invoke`` is awaited; exceptions are caught
  and converted to ``ResultPayload`` with ``error`` field set (no
  exceptions escape).
- AC-003: After ``invoke()`` returns, ``pending_notifications`` is
  called and appended to the response text (Risk #3 mitigation).
- AC-004: ``ResultPayload`` is published to the raw ``reply_to`` inbox
  (Bug #1 — first publish).
- AC-005: ``ResultPayload`` is also published to ``agents.result.jarvis``
  wrapped in the canonical envelope (Bug #1 — second publish).
- AC-006: Both publishes use flat subjects (Bug #4 — no wildcards).
- AC-007: Inbound ``conversation_history`` field is explicitly ignored.
- AC-008: Handler logs ``chat_invoke_start`` / ``chat_invoke_complete``
  / ``chat_invoke_error`` with ``correlation_id``.

All tests mock the session manager and NATS client — no live broker
required.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events._agent import CommandPayload, ResultPayload

from jarvis.infrastructure.chat_handler import handle_chat_command
from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.sessions.session import Session
from jarvis.shared.constants import Adapter

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session() -> Session:
    """Return a minimal in-memory :class:`Session` for handler tests.

    The handler reads ``session.session_id`` and passes the whole
    :class:`Session` to :meth:`SessionManager.invoke`; the mocks below
    don't introspect any other attributes.
    """
    return Session(
        session_id="cli-test-session",
        adapter=Adapter.CLI,
        user_id="test-user",
        thread_id="cli-test-session",
        started_at=datetime.now(UTC),
        correlation_id="test-corr-id",
        metadata={},
    )


@pytest.fixture()
def session_manager() -> MagicMock:
    """Return a session manager double with awaitable ``invoke`` + sync drain.

    ``invoke`` is an :class:`AsyncMock` returning ``"reply text"`` by
    default; tests that need a different reply override
    ``session_manager.invoke.return_value``. ``pending_notifications`` is
    a plain :class:`MagicMock` returning an empty list — tests that
    exercise Risk #3 (notifications appended) override the return value.
    """
    mgr = MagicMock()
    mgr.invoke = AsyncMock(return_value="reply text")
    mgr.pending_notifications = MagicMock(return_value=[])
    return mgr


@pytest.fixture()
def nats_client() -> MagicMock:
    """Return a NATS client double exposing ``.client.publish`` as AsyncMock.

    The handler publishes via ``nats_client.client.publish(subject,
    bytes)``; the mock records every call so tests can assert the
    dual-publish contract.
    """
    client = MagicMock()
    client.client = MagicMock()
    client.client.publish = AsyncMock(return_value=None)
    return client


def _make_payload(
    *,
    message: Any = "hello jarvis",
    correlation_id: str | None = "corr-123",
    extra_args: dict[str, Any] | None = None,
) -> CommandPayload:
    """Build a :class:`CommandPayload` with optional extra args.

    Helper centralises the construction so test bodies stay focused on
    the contract under test rather than payload boilerplate.
    """
    args: dict[str, Any] = {}
    if message is not None:
        args["message"] = message
    if extra_args:
        args.update(extra_args)
    return CommandPayload(
        command="chat",
        args=args,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# AC-002 / AC-003 / AC-004 / AC-005 — happy path: invoke + dual-publish
# ---------------------------------------------------------------------------


class TestHappyPathInvokeAndDualPublish:
    """Handler invokes the supervisor and dual-publishes the result."""

    @pytest.mark.asyncio
    async def test_invokes_supervisor_with_extracted_message(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC-002: ``invoke(session, message)`` is awaited with extracted text."""
        payload = _make_payload(message="hello jarvis")

        await handle_chat_command(
            payload,
            reply_to="_INBOX.test-reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        session_manager.invoke.assert_awaited_once_with(session, "hello jarvis")

    @pytest.mark.asyncio
    async def test_dual_publishes_to_reply_to_and_canonical(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC-004 + AC-005: two publishes — reply_to and agents.result.jarvis."""
        payload = _make_payload()

        await handle_chat_command(
            payload,
            reply_to="_INBOX.test-reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        # Exactly two publishes — reply_to first, canonical second.
        assert nats_client.client.publish.await_count == 2
        first_call = nats_client.client.publish.await_args_list[0]
        second_call = nats_client.client.publish.await_args_list[1]

        # First publish: raw payload to reply_to inbox
        assert first_call.args[0] == "_INBOX.test-reply"
        first_bytes = first_call.args[1]
        assert isinstance(first_bytes, bytes)
        # Decodes as bare ResultPayload (NOT a MessageEnvelope wrapper).
        first_json = json.loads(first_bytes.decode())
        bare_result = ResultPayload.model_validate(first_json)
        assert bare_result.command == "chat"
        assert bare_result.success is True
        assert bare_result.result["response"] == "reply text"
        assert bare_result.correlation_id == "corr-123"

        # Second publish: envelope-wrapped to canonical subject.
        assert second_call.args[0] == "agents.result.jarvis"
        second_bytes = second_call.args[1]
        envelope = MessageEnvelope.model_validate_json(second_bytes)
        assert envelope.event_type == EventType.RESULT
        assert envelope.source_id == "jarvis"
        assert envelope.correlation_id == "corr-123"
        inner = ResultPayload.model_validate(envelope.payload)
        assert inner.success is True
        assert inner.result["response"] == "reply text"

    @pytest.mark.asyncio
    async def test_result_payload_carries_response_tools_called_and_corr_id(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC: result dict contains response/tools_called/correlation_id."""
        payload = _make_payload(correlation_id="custom-corr")

        await handle_chat_command(
            payload,
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        first_call_bytes = nats_client.client.publish.await_args_list[0].args[1]
        bare = ResultPayload.model_validate_json(first_call_bytes)
        assert bare.result == {
            "response": "reply text",
            "tools_called": [],
            "correlation_id": "custom-corr",
        }


# ---------------------------------------------------------------------------
# AC-003 — notification drain (Risk #3 mitigation)
# ---------------------------------------------------------------------------


class TestPendingNotificationDrain:
    """Forge stage-complete notifications appended to response text."""

    def _make_notification(self, *, label: str) -> ForgeNotification:
        return ForgeNotification(
            event_type="stage_complete",
            correlation_id="forge-corr",
            feature_id="FEAT-ABC123",
            stage_label=label,
            status="PASSED",
            target_kind="local_tool",
            target_identifier="some_tool",
            completed_at=datetime(2026, 5, 11, 15, 42, tzinfo=UTC),
            duration_secs=1.5,
        )

    @pytest.mark.asyncio
    async def test_pending_notifications_called_after_invoke(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """``pending_notifications`` is called AFTER ``invoke`` returns."""
        call_order: list[str] = []
        session_manager.invoke = AsyncMock(
            side_effect=lambda *a, **kw: (call_order.append("invoke") or "supervisor reply")
        )
        session_manager.pending_notifications = MagicMock(
            side_effect=lambda *a, **kw: (call_order.append("drain") or [])
        )

        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        assert call_order == ["invoke", "drain"]
        session_manager.pending_notifications.assert_called_once_with(session.session_id)

    @pytest.mark.asyncio
    async def test_notifications_appended_to_response_text(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC-003: rendered notification lines appended to the response."""
        notif_a = self._make_notification(label="plan-complete")
        notif_b = self._make_notification(label="autobuild-complete")
        session_manager.pending_notifications.return_value = [notif_a, notif_b]
        session_manager.invoke.return_value = "supervisor said hi"

        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        first_bytes = nats_client.client.publish.await_args_list[0].args[1]
        bare = ResultPayload.model_validate_json(first_bytes)
        response = bare.result["response"]
        # Original supervisor text is preserved verbatim at the head.
        assert response.startswith("supervisor said hi")
        # Both rendered lines are present in arrival order.
        assert notif_a.render_line() in response
        assert notif_b.render_line() in response
        idx_a = response.index(notif_a.render_line())
        idx_b = response.index(notif_b.render_line())
        assert idx_a < idx_b

    @pytest.mark.asyncio
    async def test_empty_notifications_produces_no_trailing_newline(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """Empty drain → response_text equals reply_text exactly (no extra \\n)."""
        session_manager.pending_notifications.return_value = []
        session_manager.invoke.return_value = "supervisor said hi"

        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        first_bytes = nats_client.client.publish.await_args_list[0].args[1]
        bare = ResultPayload.model_validate_json(first_bytes)
        # No trailing newline appended when there are no notifications.
        assert bare.result["response"] == "supervisor said hi"

    @pytest.mark.asyncio
    async def test_malformed_notification_dropped_without_losing_reply(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """A notification whose render_line() raises is dropped silently.

        Defensive guard against future ForgeNotification field migrations
        that might surface a renderer regression — a single bad notification
        must NOT lose the entire supervisor reply.
        """
        good = self._make_notification(label="stage-good")
        bad = MagicMock()
        bad.render_line = MagicMock(side_effect=RuntimeError("renderer broken"))
        bad.correlation_id = "bad-corr"
        session_manager.pending_notifications.return_value = [good, bad]
        session_manager.invoke.return_value = "supervisor said hi"

        # Critically: does NOT raise.
        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        first_bytes = nats_client.client.publish.await_args_list[0].args[1]
        bare = ResultPayload.model_validate_json(first_bytes)
        response = bare.result["response"]
        # Good notification still rendered; supervisor text still intact.
        assert response.startswith("supervisor said hi")
        assert good.render_line() in response


# ---------------------------------------------------------------------------
# AC-002 — invoke exception path
# ---------------------------------------------------------------------------


class TestInvokeExceptionHandling:
    """Handler catches ``invoke`` exceptions and emits a failure reply."""

    @pytest.mark.asyncio
    async def test_invoke_exception_caught_and_reported(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """Exception in invoke → ResultPayload(success=False, error=...)."""
        session_manager.invoke = AsyncMock(side_effect=RuntimeError("provider exploded"))

        # Critically: does NOT raise.
        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        # Still dual-publishes so the requester's future resolves.
        assert nats_client.client.publish.await_count == 2

        bare = ResultPayload.model_validate_json(
            nats_client.client.publish.await_args_list[0].args[1]
        )
        assert bare.success is False
        assert bare.result["error"] == "provider exploded"
        assert bare.result["error_type"] == "RuntimeError"
        assert bare.correlation_id == "corr-123"

    @pytest.mark.asyncio
    async def test_no_exception_escapes_handler(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC-002 explicit: handler swallows all invoke exceptions."""
        session_manager.invoke = AsyncMock(side_effect=Exception("boom"))

        # If the handler re-raised, this would fail the test directly.
        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

    @pytest.mark.asyncio
    async def test_invoke_exception_skips_notification_drain(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """On invoke failure, the drain is not attempted (no half-reply)."""
        session_manager.invoke = AsyncMock(side_effect=RuntimeError("x"))

        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        session_manager.pending_notifications.assert_not_called()


# ---------------------------------------------------------------------------
# AC-001 — empty / missing message
# ---------------------------------------------------------------------------


class TestEmptyOrMissingMessage:
    """Empty / missing ``message`` field yields a structured error reply."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_message",
        ["", "   ", None],
        ids=["empty_string", "whitespace_only", "missing_field"],
    )
    async def test_missing_or_empty_message_short_circuits_with_error(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
        bad_message: Any,
    ) -> None:
        """AC-001: missing / empty / whitespace ``message`` → error reply."""
        payload = _make_payload(message=bad_message)

        await handle_chat_command(
            payload,
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        # invoke must NOT run when the message is invalid.
        session_manager.invoke.assert_not_awaited()

        # Still dual-publishes the structured error.
        assert nats_client.client.publish.await_count == 2
        bare = ResultPayload.model_validate_json(
            nats_client.client.publish.await_args_list[0].args[1]
        )
        assert bare.success is False
        assert bare.result["error_type"] == "MissingMessage"
        assert "message" in bare.result["error"].lower()

    @pytest.mark.asyncio
    async def test_non_string_message_rejected(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """Non-string ``message`` (e.g. int / list) is rejected as invalid."""
        payload = _make_payload(message=42)  # type: ignore[arg-type]

        await handle_chat_command(
            payload,
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        session_manager.invoke.assert_not_awaited()
        bare = ResultPayload.model_validate_json(
            nats_client.client.publish.await_args_list[0].args[1]
        )
        assert bare.success is False
        assert bare.result["error_type"] == "MissingMessage"


# ---------------------------------------------------------------------------
# AC-007 — inbound conversation_history is ignored
# ---------------------------------------------------------------------------


class TestConversationHistoryIgnored:
    """The per-gateway Session is the canonical history store."""

    @pytest.mark.asyncio
    async def test_inbound_conversation_history_not_passed_to_invoke(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC-007: ``conversation_history`` field is not used at all."""
        payload = _make_payload(
            message="hello",
            extra_args={
                "conversation_history": [
                    {"role": "user", "content": "previous turn"},
                    {"role": "assistant", "content": "previous answer"},
                ],
            },
        )

        await handle_chat_command(
            payload,
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        # invoke gets the message only — never the history list.
        session_manager.invoke.assert_awaited_once_with(session, "hello")
        # Inspect the positional + keyword args to ensure the history
        # list never reached invoke through any channel.
        call_args = session_manager.invoke.await_args
        assert "previous turn" not in str(call_args)
        assert "conversation_history" not in str(call_args)


# ---------------------------------------------------------------------------
# AC-006 — flat subjects (Bug #4)
# ---------------------------------------------------------------------------


class TestFlatSubjectsBoundary:
    """Bug #4 guard: published subjects contain no wildcard tokens."""

    @pytest.mark.asyncio
    async def test_canonical_subject_is_flat_and_correct(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """AC-006: canonical subject is the flat ``agents.result.jarvis``."""
        await handle_chat_command(
            _make_payload(),
            reply_to="_INBOX.reply",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        canonical_subject = nats_client.client.publish.await_args_list[1].args[0]
        assert canonical_subject == "agents.result.jarvis"
        assert "*" not in canonical_subject
        assert ">" not in canonical_subject

    @pytest.mark.asyncio
    async def test_invalid_agent_id_rejected_at_resolve(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """Wildcards in ``agent_id`` are rejected before any publish."""
        # Topics.resolve validates agent_id against the identifier
        # allowlist — wildcard tokens raise ValueError before either
        # publish leg fires.
        with pytest.raises(ValueError):
            await handle_chat_command(
                _make_payload(),
                reply_to="_INBOX.reply",
                session_manager=session_manager,
                session=session,
                nats_client=nats_client,
                agent_id="jarvis.*",
            )


# ---------------------------------------------------------------------------
# AC-005 / Bug #1 — fire-and-forget (empty reply_to)
# ---------------------------------------------------------------------------


class TestFireAndForgetReplyToEmpty:
    """Empty ``reply_to`` skips raw publish but keeps canonical envelope."""

    @pytest.mark.asyncio
    async def test_empty_reply_to_skips_raw_publish(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
    ) -> None:
        """Fire-and-forget: exactly one publish, to the canonical subject."""
        await handle_chat_command(
            _make_payload(),
            reply_to="",
            session_manager=session_manager,
            session=session,
            nats_client=nats_client,
            agent_id="jarvis",
        )

        assert nats_client.client.publish.await_count == 1
        only_call = nats_client.client.publish.await_args_list[0]
        assert only_call.args[0] == "agents.result.jarvis"


# ---------------------------------------------------------------------------
# AC-008 — structured logging
# ---------------------------------------------------------------------------


class TestStructuredLogging:
    """Handler emits the documented structured log events."""

    @pytest.mark.asyncio
    async def test_logs_start_and_complete_with_correlation_id(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AC-008: ``chat_invoke_start`` + ``chat_invoke_complete`` logged."""
        import logging as _logging

        import structlog

        # Reset structlog to its default configuration with caplog
        # integration — caplog records the formatted message, which
        # contains the event name as the message body when the
        # default ConsoleRenderer / KeyValueRenderer is in play.
        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.KeyValueRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(_logging.DEBUG),
            logger_factory=structlog.stdlib.LoggerFactory(),
        )

        with caplog.at_level(_logging.DEBUG):
            await handle_chat_command(
                _make_payload(correlation_id="log-corr-1"),
                reply_to="_INBOX.r",
                session_manager=session_manager,
                session=session,
                nats_client=nats_client,
                agent_id="jarvis",
            )

        all_messages = " ".join(rec.getMessage() for rec in caplog.records)
        assert "chat_invoke_start" in all_messages
        assert "chat_invoke_complete" in all_messages
        assert "log-corr-1" in all_messages

    @pytest.mark.asyncio
    async def test_logs_error_event_on_invoke_failure(
        self,
        session: Session,
        session_manager: MagicMock,
        nats_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """AC-008: ``chat_invoke_error`` logged on invoke exception."""
        import logging as _logging

        import structlog

        structlog.reset_defaults()
        structlog.configure(
            processors=[
                structlog.stdlib.add_log_level,
                structlog.processors.KeyValueRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(_logging.DEBUG),
            logger_factory=structlog.stdlib.LoggerFactory(),
        )

        session_manager.invoke = AsyncMock(side_effect=RuntimeError("blam"))

        with caplog.at_level(_logging.DEBUG):
            await handle_chat_command(
                _make_payload(correlation_id="err-corr-1"),
                reply_to="_INBOX.r",
                session_manager=session_manager,
                session=session,
                nats_client=nats_client,
                agent_id="jarvis",
            )

        all_messages = " ".join(rec.getMessage() for rec in caplog.records)
        assert "chat_invoke_error" in all_messages
        assert "err-corr-1" in all_messages
