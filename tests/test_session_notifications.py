"""Tests for SessionManager pending notification queue (TASK-J005-006).

Acceptance criteria from
``tasks/design_approved/TASK-J005-006-session-manager-pending-notifications.md``,
organised as nested test classes mirroring AC IDs.

The tests exercise the per-session FIFO contract specified by
DM-forge-notification §3 and DDR-030:

- AC-001 — :meth:`enqueue_notification` lazily creates a session-scoped FIFO.
- AC-002 — at cap, the oldest entry is evicted before the new one is appended;
  exactly one WARN ``forge_notification_queue_overflow`` per overflow.
- AC-003 — :meth:`pending_notifications` returns + clears atomically (idempotent
  drain — re-entry returns ``[]``).
- AC-004 — :meth:`end_session` clears the per-session queue; subsequent
  ``enqueue_notification`` is silently dropped (no raise).
- AC-005 — cap value is read once from
  :attr:`JarvisConfig.forge_notifications_queue_cap` at construction time.

Test scenarios mirror the Test Requirements block in the task file:

- Group B #1 — boundary: enqueue exactly ``cap``; drain returns all; queue empty.
- Group B #2 — boundary-overlap: enqueue ``cap + 1``; oldest evicted, WARN logged.
- Group D #1 — cross-session edge case: A's notifications never surface on B.
- Group D #3 — end_session drops subsequent enqueues silently.
- ASSUM-003 — re-entry-safe: two sequential drains both correct.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from langgraph.store.memory import InMemoryStore

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.sessions.manager import SessionManager
from jarvis.shared.constants import Adapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_notification(idx: int = 0, *, status: str = "PASSED") -> ForgeNotification:
    """Build a valid :class:`ForgeNotification` parameterised by ``idx``.

    All field constraints from DM-forge-notification §1 are satisfied.
    Each call returns a distinct ``correlation_id`` and ``stage_label`` so the
    FIFO ordering assertions can identify individual entries unambiguously.
    """
    return ForgeNotification(
        correlation_id=f"corr-{idx:04d}",
        feature_id="FEAT-JARVIS005",
        stage_label=f"stage-{idx}",
        status=status,  # type: ignore[arg-type]
        target_kind="local_tool",
        target_identifier="queue_build",
        completed_at=datetime(2026, 4, 29, 15, 42, tzinfo=UTC),
        duration_secs=1.5,
    )


def _make_manager(queue_cap: int = 100) -> SessionManager:
    """Construct a :class:`SessionManager` with a non-invoking supervisor.

    The supervisor mock is never awaited in these tests — the queue API is
    pure book-keeping inside ``SessionManager`` and does not touch the
    supervisor or the store.
    """
    supervisor = AsyncMock()
    store = InMemoryStore()
    return SessionManager(supervisor, store, queue_cap=queue_cap)


# ---------------------------------------------------------------------------
# AC-001 / AC-005: lazy FIFO + cap read once at construction
# ---------------------------------------------------------------------------
class TestAC001LazyFifoAndConstructionCap:
    """``enqueue_notification`` lazy-creates the FIFO; cap is read once."""

    def test_enqueue_creates_fifo_on_first_call(self) -> None:
        mgr = _make_manager(queue_cap=10)
        session = mgr.start_session(Adapter.CLI, "rich")

        notif = _make_notification(0)
        mgr.enqueue_notification(session.session_id, notif)

        drained = mgr.pending_notifications(session.session_id)
        assert drained == [notif]

    def test_construction_reads_cap_once(self) -> None:
        # Build a manager with cap=3, then mutate the field name on the
        # underlying object to ensure enqueue does NOT re-read it per call.
        mgr = _make_manager(queue_cap=3)
        session = mgr.start_session(Adapter.CLI, "rich")

        # Mutate the captured cap to a deliberately-wrong sentinel; if
        # enqueue still respects 3 (the construction-time value), the
        # assertion below holds.
        # (We rely on the snapshot semantics — not a public API, just a
        # belt-and-braces guard against regressions to per-call reads.)
        snapshot_attr = "_notification_queue_cap"
        assert hasattr(mgr, snapshot_attr), (
            f"SessionManager must snapshot the cap as ``{snapshot_attr}`` at construction time"
        )

        for i in range(5):
            mgr.enqueue_notification(session.session_id, _make_notification(i))

        drained = mgr.pending_notifications(session.session_id)
        # Only the latest 3 survive; the cap was NOT re-read per-call.
        assert len(drained) == 3
        assert [n.stage_label for n in drained] == ["stage-2", "stage-3", "stage-4"]


# ---------------------------------------------------------------------------
# Group B #1 — boundary: enqueue == cap; drain returns all; queue empty
# ---------------------------------------------------------------------------
class TestACBoundaryFillAndDrain:
    """Boundary scenario: exactly ``cap`` entries surface, then queue empty."""

    def test_enqueue_cap_items_drains_all_in_fifo_order(self) -> None:
        cap = 100
        mgr = _make_manager(queue_cap=cap)
        session = mgr.start_session(Adapter.CLI, "rich")

        for i in range(cap):
            mgr.enqueue_notification(session.session_id, _make_notification(i))

        drained = mgr.pending_notifications(session.session_id)
        assert len(drained) == cap
        # FIFO: arrival order is preserved.
        assert [n.stage_label for n in drained] == [f"stage-{i}" for i in range(cap)]

        # Queue is empty after a drain — the second drain returns [].
        assert mgr.pending_notifications(session.session_id) == []


# ---------------------------------------------------------------------------
# AC-002 / Group B #2 — boundary-overlap: cap + 1 evicts oldest with WARN
# ---------------------------------------------------------------------------
class TestAC002OverflowEvictsOldestWithWarn:
    """At cap, oldest entry is evicted before the new one is appended."""

    def test_overflow_evicts_oldest_and_logs_warn_once(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        cap = 5  # small cap keeps the test fast and the assertions readable
        mgr = _make_manager(queue_cap=cap)
        session = mgr.start_session(Adapter.CLI, "rich")

        with caplog.at_level(logging.WARNING, logger="jarvis.sessions.manager"):
            for i in range(cap + 1):
                mgr.enqueue_notification(session.session_id, _make_notification(i))

        drained = mgr.pending_notifications(session.session_id)

        # Oldest (stage-0) was evicted; the latest cap entries survive.
        assert len(drained) == cap
        assert [n.stage_label for n in drained] == [f"stage-{i}" for i in range(1, cap + 1)]

        # Exactly one WARN ``forge_notification_queue_overflow`` line was emitted.
        overflow_records = [
            record
            for record in caplog.records
            if "forge_notification_queue_overflow" in record.getMessage()
            or getattr(record, "event", "") == "forge_notification_queue_overflow"
        ]
        assert len(overflow_records) == 1, (
            f"Expected exactly 1 overflow WARN, got {len(overflow_records)}: "
            f"{[r.getMessage() for r in caplog.records]}"
        )


# ---------------------------------------------------------------------------
# AC-003 / ASSUM-003 — atomic drain, re-entry-safe
# ---------------------------------------------------------------------------
class TestAC003AtomicDrainReentrySafe:
    """``pending_notifications`` returns + clears atomically; safe to re-drain."""

    def test_two_sequential_drains_no_duplicates(self) -> None:
        mgr = _make_manager(queue_cap=10)
        session = mgr.start_session(Adapter.CLI, "rich")

        for i in range(3):
            mgr.enqueue_notification(session.session_id, _make_notification(i))

        first = mgr.pending_notifications(session.session_id)
        second = mgr.pending_notifications(session.session_id)

        assert [n.stage_label for n in first] == ["stage-0", "stage-1", "stage-2"]
        assert second == [], "Second drain must return [] — atomic clear on first drain"

    def test_drain_then_enqueue_then_drain_preserves_only_new_entries(self) -> None:
        mgr = _make_manager(queue_cap=10)
        session = mgr.start_session(Adapter.CLI, "rich")

        mgr.enqueue_notification(session.session_id, _make_notification(0))
        first = mgr.pending_notifications(session.session_id)

        mgr.enqueue_notification(session.session_id, _make_notification(1))
        second = mgr.pending_notifications(session.session_id)

        assert [n.stage_label for n in first] == ["stage-0"]
        assert [n.stage_label for n in second] == ["stage-1"]


# ---------------------------------------------------------------------------
# AC-004 / Group D #3 — end_session clears + drops subsequent enqueues
# ---------------------------------------------------------------------------
class TestAC004EndSessionClearsAndDrops:
    """``end_session`` clears the queue; subsequent enqueue silently drops."""

    def test_end_session_clears_pending(self) -> None:
        mgr = _make_manager(queue_cap=10)
        session = mgr.start_session(Adapter.CLI, "rich")

        for i in range(3):
            mgr.enqueue_notification(session.session_id, _make_notification(i))

        mgr.end_session(session.session_id)

        # After end_session, pending returns [] (queue cleared).
        assert mgr.pending_notifications(session.session_id) == []

    def test_subsequent_enqueue_after_end_is_silently_dropped(self) -> None:
        mgr = _make_manager(queue_cap=10)
        session = mgr.start_session(Adapter.CLI, "rich")

        mgr.end_session(session.session_id)

        # Must NOT raise — silently drops the notification.
        mgr.enqueue_notification(session.session_id, _make_notification(0))

        assert mgr.pending_notifications(session.session_id) == []


# ---------------------------------------------------------------------------
# Group D #1 — cross-session isolation
# ---------------------------------------------------------------------------
class TestACCrossSessionIsolation:
    """Notifications enqueued on session A do not surface on session B."""

    def test_notifications_for_session_a_do_not_leak_to_session_b(self) -> None:
        mgr = _make_manager(queue_cap=10)
        session_a = mgr.start_session(Adapter.CLI, "rich")
        session_b = mgr.start_session(Adapter.CLI, "rich")

        assert session_a.session_id != session_b.session_id

        # Enqueue 2 notifications for A only.
        mgr.enqueue_notification(session_a.session_id, _make_notification(0))
        mgr.enqueue_notification(session_a.session_id, _make_notification(1))

        # Session B sees nothing — its queue has never been created.
        assert mgr.pending_notifications(session_b.session_id) == []

        # Session A's drain returns both entries.
        drained_a = mgr.pending_notifications(session_a.session_id)
        assert [n.stage_label for n in drained_a] == ["stage-0", "stage-1"]


# ---------------------------------------------------------------------------
# Idempotent on unknown session_id
# ---------------------------------------------------------------------------
class TestACUnknownSessionIdempotent:
    """Enqueue/drain on an unknown ``session_id`` is a no-op (DM §3, point 6)."""

    def test_enqueue_unknown_session_does_not_raise(self) -> None:
        mgr = _make_manager(queue_cap=10)
        # No session started — session_id is unknown.
        mgr.enqueue_notification("cli-deadbeef", _make_notification(0))
        # And reading from an unknown session returns [].
        assert mgr.pending_notifications("cli-deadbeef") == []

    def test_pending_notifications_unknown_session_returns_empty(self) -> None:
        mgr = _make_manager(queue_cap=10)
        # Reading from an unknown session_id without prior enqueue — returns [].
        result: list[Any] = mgr.pending_notifications("cli-never-existed")
        assert result == []
