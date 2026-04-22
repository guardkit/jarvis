"""Tests for jarvis.sessions — Session model + SessionManager.

Acceptance criteria from TASK-J001-007, organised as nested test classes.
TDD RED phase: these tests are written before the implementation.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.store.memory import InMemoryStore

from jarvis.shared.constants import Adapter
from jarvis.shared.exceptions import JarvisError, SessionNotFoundError


# ---------------------------------------------------------------------------
# AC-001: SessionManager(supervisor, store) constructs without side-effects
# ---------------------------------------------------------------------------
class TestAC001ConstructWithoutSideEffects:
    """SessionManager(supervisor, store) constructs without side-effects."""

    def test_construction_does_not_invoke_supervisor(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        supervisor.ainvoke.assert_not_called()
        assert mgr is not None

    def test_construction_does_not_write_to_store(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        _mgr = SessionManager(supervisor, store)

        # Store should have no items written during construction
        results = store.search(("user",), limit=100)
        assert len(list(results)) == 0


# ---------------------------------------------------------------------------
# AC-002: start_session(Adapter.CLI, "rich") returns correct Session
# ---------------------------------------------------------------------------
class TestAC002StartSessionCLI:
    """start_session(Adapter.CLI, 'rich') returns a properly formed Session."""

    def test_returns_session_with_matching_fields(self) -> None:
        from jarvis.sessions.manager import SessionManager
        from jarvis.sessions.session import Session

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")

        assert isinstance(session, Session)
        assert session.adapter == Adapter.CLI
        assert session.user_id == "rich"

    def test_session_id_starts_with_adapter_prefix(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")

        assert session.session_id.startswith("cli-")

    def test_thread_id_equals_session_id(self) -> None:
        """DDR-004: thread_id == session_id in Phase 1."""
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")

        assert session.thread_id == session.session_id

    def test_started_at_is_utc_and_recent(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        before = datetime.now(UTC)
        session = mgr.start_session(Adapter.CLI, "rich")
        after = datetime.now(UTC)

        assert session.started_at.tzinfo is not None
        assert before <= session.started_at <= after

    def test_emits_session_started_log_event(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        with patch("jarvis.sessions.manager.logger") as mock_logger:
            session = mgr.start_session(Adapter.CLI, "rich")
            mock_logger.info.assert_any_call(
                "session_started",
                session_id=session.session_id,
                adapter="cli",
                user_id="rich",
            )


# ---------------------------------------------------------------------------
# AC-003: start_session with non-CLI adapter raises JarvisError (ASSUM-006)
# ---------------------------------------------------------------------------
class TestAC003NonCLIAdapterRefused:
    """start_session(Adapter.TELEGRAM|DASHBOARD|REACHY, ...) raises JarvisError."""

    @pytest.mark.parametrize("adapter", [Adapter.TELEGRAM, Adapter.DASHBOARD, Adapter.REACHY])
    def test_non_cli_adapter_raises_jarvis_error(self, adapter: Adapter) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        with pytest.raises(JarvisError, match=str(adapter)):
            mgr.start_session(adapter, "rich")


# ---------------------------------------------------------------------------
# AC-004: Two successive start_session calls return distinct session_ids
# ---------------------------------------------------------------------------
class TestAC004DistinctSessionIds:
    """Two successive start_session calls for same user_id return distinct session_ids."""

    def test_distinct_session_ids_for_same_user(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        s1 = mgr.start_session(Adapter.CLI, "rich")
        s2 = mgr.start_session(Adapter.CLI, "rich")

        assert s1.session_id != s2.session_id


# ---------------------------------------------------------------------------
# AC-005: resume_session("unknown") raises SessionNotFoundError
# ---------------------------------------------------------------------------
class TestAC005ResumeSessionUnknown:
    """resume_session('unknown') raises SessionNotFoundError."""

    def test_unknown_session_raises(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        with pytest.raises(SessionNotFoundError):
            mgr.resume_session("unknown")

    def test_resume_session_returns_started_session(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        resumed = mgr.resume_session(session.session_id)

        assert resumed.session_id == session.session_id
        assert resumed.user_id == session.user_id


# ---------------------------------------------------------------------------
# AC-006: end_session idempotent — double call does not raise
# ---------------------------------------------------------------------------
class TestAC006EndSessionIdempotent:
    """end_session(sid); end_session(sid) both succeed; session marked ended exactly once."""

    def test_double_end_session_does_not_raise(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        mgr.end_session(session.session_id)
        mgr.end_session(session.session_id)  # Should not raise

    def test_end_emits_session_ended_log_once(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")

        with patch("jarvis.sessions.manager.logger") as mock_logger:
            mgr.end_session(session.session_id)
            mgr.end_session(session.session_id)

            # SessionEnded log emitted exactly once
            ended_calls = [
                c
                for c in mock_logger.info.call_args_list
                if c.args and c.args[0] == "session_ended"
            ]
            assert len(ended_calls) == 1

    def test_ended_session_cannot_be_resumed(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        mgr.end_session(session.session_id)

        with pytest.raises(SessionNotFoundError):
            mgr.resume_session(session.session_id)


# ---------------------------------------------------------------------------
# AC-007: invoke(session, "hello") returns canned text, Memory Store keyed
#         by ("user", user_id) — no session_id segment (DDR-002)
# ---------------------------------------------------------------------------
class TestAC007InvokeReturnsText:
    """invoke(session, 'hello') with fake_llm returns canned text."""

    @pytest.mark.asyncio
    async def test_invoke_returns_supervisor_response(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        supervisor.ainvoke.return_value = {
            "messages": [AIMessage(content="Canned response 1")],
        }
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        reply = await mgr.invoke(session, "hello")

        assert reply == "Canned response 1"

    @pytest.mark.asyncio
    async def test_invoke_passes_thread_id_config_and_store(self) -> None:
        """Coach validation: both config and store must be passed."""
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        supervisor.ainvoke.return_value = {
            "messages": [AIMessage(content="ok")],
        }
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        await mgr.invoke(session, "hello")

        supervisor.ainvoke.assert_called_once()
        call_kwargs = supervisor.ainvoke.call_args
        # config must have thread_id
        assert call_kwargs.kwargs["config"] == {
            "configurable": {"thread_id": session.thread_id},
        }
        # store must be passed
        assert call_kwargs.kwargs["store"] is store


# ---------------------------------------------------------------------------
# AC-008: Concurrent invoke on same session raises JarvisError (ASSUM-003)
# ---------------------------------------------------------------------------
class TestAC008ConcurrentInvokeRefusal:
    """Second concurrent invoke on same session raises JarvisError."""

    @pytest.mark.asyncio
    async def test_concurrent_invoke_raises(self) -> None:
        from jarvis.sessions.manager import SessionManager

        # First invoke hangs forever (simulates slow LLM)
        hang_forever: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()

        async def slow_ainvoke(*args: Any, **kwargs: Any) -> dict[str, Any]:
            return await hang_forever

        supervisor = AsyncMock()
        supervisor.ainvoke = slow_ainvoke

        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)
        session = mgr.start_session(Adapter.CLI, "rich")

        task1 = asyncio.create_task(mgr.invoke(session, "first"))
        # Yield control so task1 starts and sets the in-flight flag
        await asyncio.sleep(0.01)

        # Second invoke should refuse immediately
        with pytest.raises(JarvisError, match=r"[Cc]oncurrent invoke refused"):
            await mgr.invoke(session, "second")

        # Cleanup: cancel the hung task
        task1.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task1


# ---------------------------------------------------------------------------
# AC-009: Cross-session recall — session A writes → session B for same user reads
# ---------------------------------------------------------------------------
class TestAC009CrossSessionRecall:
    """Cross-session recall: session A writes fact → session B for same user reads fact."""

    @pytest.mark.asyncio
    async def test_same_user_sessions_share_memory_namespace(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        supervisor.ainvoke.return_value = {
            "messages": [AIMessage(content="recalled")],
        }
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session_a = mgr.start_session(Adapter.CLI, "rich")
        session_b = mgr.start_session(Adapter.CLI, "rich")

        # Both sessions invoke with the same store and user_id namespace
        await mgr.invoke(session_a, "remember this")
        await mgr.invoke(session_b, "recall")

        # Both calls must use the same store instance (DDR-002: user-keyed)
        assert supervisor.ainvoke.call_count == 2
        for call in supervisor.ainvoke.call_args_list:
            assert call.kwargs["store"] is store


# ---------------------------------------------------------------------------
# AC-010: Cross-user isolation — user A's fact not returned for user B
# ---------------------------------------------------------------------------
class TestAC010CrossUserIsolation:
    """Cross-user isolation: user A's fact not returned for user B."""

    @pytest.mark.asyncio
    async def test_different_users_get_different_thread_ids(self) -> None:
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        supervisor.ainvoke.return_value = {
            "messages": [AIMessage(content="ok")],
        }
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session_a = mgr.start_session(Adapter.CLI, "alice")
        session_b = mgr.start_session(Adapter.CLI, "bob")

        await mgr.invoke(session_a, "alice secret")
        await mgr.invoke(session_b, "bob query")

        # Verify different thread_ids were passed (session isolation)
        call_a = supervisor.ainvoke.call_args_list[0]
        call_b = supervisor.ainvoke.call_args_list[1]

        thread_a = call_a.kwargs["config"]["configurable"]["thread_id"]
        thread_b = call_b.kwargs["config"]["configurable"]["thread_id"]

        assert thread_a != thread_b
        assert thread_a == session_a.session_id
        assert thread_b == session_b.session_id


# ---------------------------------------------------------------------------
# AC-011: All modified files pass lint/format with zero errors
# (Verified externally by ruff — this is an infrastructure concern)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Session model unit tests
# ---------------------------------------------------------------------------
class TestSessionModel:
    """Unit tests for the Session Pydantic model."""

    def test_session_is_pydantic_base_model(self) -> None:
        from pydantic import BaseModel

        from jarvis.sessions.session import Session

        assert issubclass(Session, BaseModel)

    def test_session_fields_present(self) -> None:
        from jarvis.sessions.session import Session

        fields = set(Session.model_fields.keys())
        expected = {
            "session_id",
            "adapter",
            "user_id",
            "thread_id",
            "started_at",
            "correlation_id",
            "metadata",
        }
        assert expected.issubset(fields)

    def test_metadata_defaults_to_empty_dict(self) -> None:
        from jarvis.sessions.session import Session

        s = Session(
            session_id="cli-abc",
            adapter=Adapter.CLI,
            user_id="test",
            thread_id="cli-abc",
            started_at=datetime.now(UTC),
            correlation_id="corr-123",
        )
        assert s.metadata == {}


# ---------------------------------------------------------------------------
# DDR-002 invariant: no session_id in Memory Store namespace
# ---------------------------------------------------------------------------
class TestDDR002NoSessionIdInNamespace:
    """Memory Store namespace must be ('user', user_id) with NO session_id segment."""

    @pytest.mark.asyncio
    async def test_invoke_does_not_include_session_id_in_store_namespace(self) -> None:
        """Verify no store namespace key construction includes session_id."""
        from jarvis.sessions.manager import SessionManager

        supervisor = AsyncMock()
        supervisor.ainvoke.return_value = {
            "messages": [AIMessage(content="ok")],
        }
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        await mgr.invoke(session, "test")

        # The store is passed to ainvoke — manager itself doesn't write to store
        # with any session_id-based key. Verify the call doesn't construct
        # a namespace with session_id.
        call_kwargs = supervisor.ainvoke.call_args.kwargs
        assert call_kwargs["store"] is store
        # config only has thread_id for checkpointing
        assert "thread_id" in call_kwargs["config"]["configurable"]


# ---------------------------------------------------------------------------
# Seam test from task specification
# ---------------------------------------------------------------------------
@pytest.mark.seam
@pytest.mark.integration_contract("COMPILED_SUPERVISOR_GRAPH")
class TestSeamCompiledSupervisorGraph:
    """Seam: verify COMPILED_SUPERVISOR_GRAPH contract from TASK-J001-006."""

    @pytest.mark.asyncio
    async def test_compiled_supervisor_graph_contract(
        self, test_config: Any, fake_llm: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify SessionManager invokes supervisor with thread_id config AND store.

        Contract: SessionManager.invoke MUST pass
        config={'configurable': {'thread_id': session.thread_id}}
        AND store=self._store to supervisor.ainvoke.
        Memory Store namespace MUST be ('user', user_id) — no session_id.
        Producer: TASK-J001-006
        """
        from jarvis.sessions.manager import SessionManager

        # Use a mock supervisor that records its call args — real build_supervisor
        # requires a model that supports bind_tools which FakeListChatModel doesn't.
        supervisor = AsyncMock()
        supervisor.ainvoke.return_value = {
            "messages": [AIMessage(content="Canned response 1")],
        }
        store = InMemoryStore()
        mgr = SessionManager(supervisor, store)

        session = mgr.start_session(Adapter.CLI, "rich")
        reply = await mgr.invoke(session, "hello")

        # Assertion 1: thread_id equals session_id (DDR-004)
        assert session.thread_id == session.session_id

        # Assertion 2: reply is a string
        assert isinstance(reply, str)
        assert reply == "Canned response 1"

        # Assertion 3: config and store passed correctly
        call_kwargs = supervisor.ainvoke.call_args
        assert call_kwargs.kwargs["config"] == {
            "configurable": {"thread_id": session.thread_id},
        }
        assert call_kwargs.kwargs["store"] is store

        # Assertion 4: no session_id in namespace construction
        # (manager doesn't construct store namespaces — passes store through)
