"""Session manager for Jarvis.

Provides :class:`SessionManager` — the central component that manages session
lifecycle (start, resume, end) and routes user input through the supervisor
graph with proper thread-per-session isolation (DDR-004) and user-keyed
Memory Store (DDR-002).

This module belongs to the sessions package (Group D) per ADR-ARCH-006.
"""

from __future__ import annotations

import contextvars
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog
from langchain_core.messages import HumanMessage

from jarvis.sessions.session import Session
from jarvis.shared.constants import Adapter
from jarvis.shared.exceptions import JarvisError, SessionNotFoundError

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.store.base import BaseStore

logger = structlog.get_logger(__name__)


class SessionManager:
    """Manages session lifecycle and supervisor invocation.

    Thread-per-session 1:1 mapping (DDR-004), user-keyed Memory Store (DDR-002),
    and single-threaded invoke contract per session (ASSUM-003).

    Args:
        supervisor: A compiled LangGraph supervisor graph from
            :func:`jarvis.agents.supervisor.build_supervisor`.
        store: A LangGraph BaseStore instance for cross-session memory.
    """

    def __init__(
        self,
        supervisor: CompiledStateGraph[Any, Any, Any, Any],
        store: BaseStore,
    ) -> None:
        self._supervisor = supervisor
        self._store = store
        self._sessions: dict[str, Session] = {}
        self._ended: set[str] = set()
        self._in_flight: dict[str, bool] = {}
        # ContextVar (per-instance) backing :meth:`current_session`. A
        # ContextVar is required rather than a plain attribute because the
        # supervisor invocation is awaited and multiple sessions can be
        # in flight across asyncio tasks at the same time — each task's
        # context copy holds its own session reference, so the dispatch
        # module's ``_current_session_hook`` resolves to the session whose
        # supervisor turn is actually running. The unique name embeds
        # ``id(self)`` so multiple SessionManagers (e.g. across
        # ``build_app_state`` calls in a single test process) do not
        # alias one another's storage.
        self._current_session_var: contextvars.ContextVar[Session | None] = (
            contextvars.ContextVar(
                f"jarvis_session_manager_{id(self)}_current_session",
                default=None,
            )
        )

    def start_session(self, adapter: Adapter, user_id: str) -> Session:
        """Create a new session for the given adapter and user.

        Phase 1 only supports :attr:`Adapter.CLI`. All other adapters are
        refused with a :class:`JarvisError` (ASSUM-006).

        Args:
            adapter: The adapter surface creating the session.
            user_id: The user identifier.

        Returns:
            A new :class:`Session` with a unique adapter-prefixed session_id.

        Raises:
            JarvisError: If the adapter is not :attr:`Adapter.CLI`.
        """
        if adapter != Adapter.CLI:
            msg = (
                f"Adapter '{adapter}' is not supported in Phase 1. "
                f"Only '{Adapter.CLI}' is allowed."
            )
            raise JarvisError(msg)

        session_id = f"{adapter}-{uuid.uuid4().hex}"
        session = Session(
            session_id=session_id,
            adapter=adapter,
            user_id=user_id,
            thread_id=session_id,  # DDR-004: thread_id == session_id
            started_at=datetime.now(UTC),
            correlation_id=uuid.uuid4().hex,
            metadata={},
        )

        self._sessions[session_id] = session

        logger.info(
            "session_started",
            session_id=session_id,
            adapter=str(adapter),
            user_id=user_id,
        )

        return session

    def resume_session(self, session_id: str) -> Session:
        """Retrieve an existing active session by its ID.

        Args:
            session_id: The session identifier to look up.

        Returns:
            The :class:`Session` matching the given ID.

        Raises:
            SessionNotFoundError: If the session_id is unknown or has been ended.
        """
        if session_id in self._ended or session_id not in self._sessions:
            msg = f"Session '{session_id}' not found"
            raise SessionNotFoundError(msg)

        return self._sessions[session_id]

    def current_session(self) -> Session | None:
        """Return the session whose supervisor turn is currently running.

        Backs the ``jarvis.tools.dispatch._current_session_hook`` resolver
        wired by :func:`jarvis.infrastructure.lifecycle.build_app_state`.
        Layer 2 of the constitutional ``escalate_to_frontier`` gate
        (DDR-014) reads ``Session.adapter`` and
        ``Session.metadata['currently_in_subagent']`` from the returned
        value to decide whether to reject the call before any provider
        SDK invocation.

        The result is sourced from a per-instance :class:`contextvars.ContextVar`
        that :meth:`invoke` sets for the duration of each supervisor turn —
        ``None`` is the dormant default observed when no session is
        currently driving a supervisor call (which the dispatch module
        treats as ``adapter_id == "unknown"``, an attended-only
        rejection).

        Returns:
            The :class:`Session` currently driving a supervisor turn, or
            ``None`` when the manager is idle on the active asyncio task.
        """
        return self._current_session_var.get()

    def end_session(self, session_id: str) -> None:
        """End a session. Idempotent — calling twice does not raise.

        Emits a ``session_ended`` structured log event exactly once per session.

        Args:
            session_id: The session identifier to end.
        """
        if session_id in self._ended:
            return

        self._ended.add(session_id)
        # Remove from in-flight tracking
        self._in_flight.pop(session_id, None)

        logger.info(
            "session_ended",
            session_id=session_id,
        )

    async def invoke(self, session: Session, user_input: str) -> str:
        """Send user input through the supervisor for this session.

        Enforces single-concurrent-invoke per session (ASSUM-003): if another
        invoke is already in-flight for the same session, raises
        :class:`JarvisError` immediately — does NOT queue or await.

        The supervisor is invoked with:
            - ``config={"configurable": {"thread_id": session.thread_id}}``
            - ``store=self._store``

        Memory Store namespace is ``("user", user_id)`` with NO session_id
        segment (DDR-002). This is handled by the supervisor/store layer.

        Args:
            session: The active session to invoke against.
            user_input: The user's message text.

        Returns:
            The text content of the supervisor's response.

        Raises:
            JarvisError: If a concurrent invoke is already in-flight for
                this session (ASSUM-003).
        """
        sid = session.session_id

        # ASSUM-003: refuse concurrent invokes — do NOT await/serialize
        if self._in_flight.get(sid, False):
            msg = f"Concurrent invoke refused for session '{sid}'"
            raise JarvisError(msg)

        self._in_flight[sid] = True
        # Publish the active session to the per-instance ContextVar so the
        # dispatch module's ``_current_session_hook`` (wired in
        # ``lifecycle.build_app_state``) can resolve the active adapter
        # for DDR-014 Layer 2.
        token = self._current_session_var.set(session)
        try:
            result: dict[str, Any] = await self._supervisor.ainvoke(
                {"messages": [HumanMessage(content=user_input)]},
                config={"configurable": {"thread_id": session.thread_id}},
                store=self._store,
            )

            return str(result["messages"][-1].content)
        finally:
            self._current_session_var.reset(token)
            self._in_flight[sid] = False
