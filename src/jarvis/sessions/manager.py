"""Session manager for Jarvis.

Provides :class:`SessionManager` — the central component that manages session
lifecycle (start, resume, end) and routes user input through the supervisor
graph with proper thread-per-session isolation (DDR-004) and user-keyed
Memory Store (DDR-002).

This module belongs to the sessions package (Group D) per ADR-ARCH-006.
"""

from __future__ import annotations

import contextvars
import logging
import uuid
from collections import deque
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

    # ``ForgeNotification`` is imported under TYPE_CHECKING to avoid a
    # circular import at module load time. The chain that fails when
    # imported eagerly is:
    #
    #     manager → infrastructure.forge_notifications → infrastructure.__init__
    #     → infrastructure.lifecycle → sessions.manager (partial).
    #
    # Annotations are evaluated lazily under ``from __future__ import
    # annotations`` (already imported above), so the string-only reference
    # below is sufficient for static type-checking; the runtime body of
    # ``enqueue_notification`` only accesses
    # :attr:`ForgeNotification.correlation_id`, which is duck-typed.
    from jarvis.infrastructure.forge_notifications import ForgeNotification

logger = structlog.get_logger(__name__)

# Standard-library logger used for the FEAT-JARVIS-005 queue overflow WARN
# (DDR-030). The structlog ``logger`` above is unconfigured by default in the
# unit-test process — relying on it would make ``forge_notification_queue_overflow``
# undetectable via pytest's ``caplog`` fixture. Routing this single WARN through
# the stdlib logger keeps it asserted in tests AND visible in production
# (configured logging propagates to the same root handler).
_stdlib_logger = logging.getLogger(__name__)


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
        *,
        queue_cap: int = 100,
    ) -> None:
        self._supervisor = supervisor
        self._store = store
        self._sessions: dict[str, Session] = {}
        self._ended: set[str] = set()
        self._in_flight: dict[str, bool] = {}
        # FEAT-JARVIS-005 / DDR-030 — per-session forge-notification FIFO.
        # Cap is read once at construction time per AC-005 of TASK-J005-006;
        # the lifecycle wiring (TASK-J005-008) plumbs the corresponding
        # JarvisConfig field through as ``queue_cap``. The dict is keyed on
        # ``session_id`` and values are bounded ``collections.deque``
        # instances created lazily on first enqueue.
        self._notification_queue_cap: int = queue_cap
        self._notification_queues: dict[str, deque[ForgeNotification]] = {}
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
        self._current_session_var: contextvars.ContextVar[Session | None] = contextvars.ContextVar(
            f"jarvis_session_manager_{id(self)}_current_session",
            default=None,
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
                f"Adapter '{adapter}' is not supported in Phase 1. Only '{Adapter.CLI}' is allowed."
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

        Per TASK-J005-006 AC-004 / DM-forge-notification §3, this also clears
        the per-session forge-notification FIFO and discards any future
        :meth:`enqueue_notification` calls for ``session_id`` (silently —
        they become no-ops with a DEBUG ``forge_notification_dropped`` line).

        Args:
            session_id: The session identifier to end.
        """
        if session_id in self._ended:
            return

        self._ended.add(session_id)
        # Remove from in-flight tracking
        self._in_flight.pop(session_id, None)
        # Drop the per-session FIFO so future ``pending_notifications`` calls
        # return ``[]`` and any in-flight notification objects can be
        # garbage-collected promptly.
        self._notification_queues.pop(session_id, None)

        logger.info(
            "session_ended",
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # FEAT-JARVIS-005 / TASK-J005-006 — pending notification queue
    # ------------------------------------------------------------------

    def enqueue_notification(
        self,
        session_id: str,
        notification: ForgeNotification,
    ) -> None:
        """Append a :class:`ForgeNotification` to ``session_id``'s FIFO.

        Per TASK-J005-006 acceptance criteria:

        * The FIFO is created lazily on the first enqueue for a given
          ``session_id`` (AC-001).
        * When the queue is at cap, the oldest entry is evicted before
          the new one is appended; exactly one WARN
          ``forge_notification_queue_overflow`` log line is emitted per
          overflow (AC-002).
        * Enqueueing to an unknown or already-ended ``session_id`` is a
          silent no-op with a DEBUG ``forge_notification_dropped`` line —
          it does NOT raise (AC-004 / DM-forge-notification §3 point 6).
        * The cap was read once from the corresponding JarvisConfig
          field at construction time (AC-005); this method does NOT
          re-read it.

        Args:
            session_id: The session identifier owning the FIFO.
            notification: The :class:`ForgeNotification` to enqueue.
        """
        # Idempotent on missing/ended sessions — DM-forge-notification §3 #6.
        if session_id in self._ended or session_id not in self._sessions:
            logger.debug(
                "forge_notification_dropped",
                session_id=session_id,
                reason="unknown_or_ended_session",
                correlation_id=notification.correlation_id,
            )
            return

        cap = self._notification_queue_cap
        queue = self._notification_queues.get(session_id)
        if queue is None:
            # Lazy-create. ``maxlen=cap`` makes ``deque.append`` evict the
            # oldest entry automatically when the queue is full — the manual
            # length check below is purely to surface the overflow as a WARN
            # log line; the eviction itself is a property of ``maxlen``.
            queue = deque(maxlen=cap)
            self._notification_queues[session_id] = queue

        if len(queue) >= cap:
            # ``deque(maxlen=cap).append(x)`` will silently drop the oldest
            # entry; emit one WARN per overflow so operators can spot a
            # session that is producing notifications faster than the CLI
            # render loop drains them (DDR-030).
            _stdlib_logger.warning(
                "forge_notification_queue_overflow",
                extra={
                    "session_id": session_id,
                    "cap": cap,
                    "evicted_correlation_id": queue[0].correlation_id,
                },
            )

        queue.append(notification)

    def pending_notifications(self, session_id: str) -> list[ForgeNotification]:
        """Drain ``session_id``'s FIFO — return entries in arrival order, then clear.

        Atomic per AC-003 / ASSUM-003: the return + clear pair runs without
        an intermediate ``await`` so the single asyncio loop guarantees no
        notification is double-rendered or lost between drain and clear.
        Re-entry-safe — a second sequential drain returns ``[]``.

        For unknown ``session_id`` (no enqueue ever made; or session was
        already ended), returns ``[]`` per DM-forge-notification §3 point 6.

        Args:
            session_id: The session whose pending notifications to drain.

        Returns:
            The notifications enqueued since the last drain, in FIFO order.
            Empty list if the session has no pending notifications, the
            session_id is unknown, or the session has been ended.
        """
        queue = self._notification_queues.get(session_id)
        if queue is None:
            return []

        # Atomic drain — list() snapshots the current contents before
        # ``clear()`` empties the deque. Both operations execute without an
        # ``await`` boundary, so a concurrent ``enqueue_notification`` from
        # the subscriber lands either fully before this snapshot or fully
        # after the clear; never in-between (ASSUM-003 single-loop).
        drained = list(queue)
        queue.clear()
        return drained

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
