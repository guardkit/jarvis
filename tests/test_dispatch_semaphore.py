"""Tests for jarvis.infrastructure.dispatch_semaphore.

TASK-J004-008 — DispatchSemaphore wrapper.

Acceptance Criteria:
    AC-001: DispatchSemaphore(cap=8) allows exactly 8 concurrent acquisitions;
            the 9th try_acquire() returns False synchronously (no await).
    AC-002: release() after a successful try_acquire() returns the slot.
    AC-003: release() without a matching acquire is a no-op (no exception,
            no underflow).
    AC-004: in_flight reflects acquired slots accurately at any inspection
            point.
    AC-005: This file covers: exact ceiling (8 OK, 9th False); release on
            success; release on timeout; release on exception path; double-
            release idempotency; in_flight accuracy.

Per the task brief (Test Requirements §1) these tests use the real
DispatchSemaphore — no mocks, no patches.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from jarvis.infrastructure.dispatch_semaphore import DispatchSemaphore

# ============================================================================
# AC-001: exact ceiling — 8 acquisitions OK, 9th returns False synchronously
# ============================================================================


class TestExactCeiling:
    """AC-001: DispatchSemaphore(cap=8) honours the cap synchronously."""

    def test_try_acquire_with_cap_eight_allows_exactly_eight_acquisitions(self) -> None:
        sem = DispatchSemaphore(cap=8)

        results = [sem.try_acquire() for _ in range(8)]

        assert results == [True] * 8
        assert sem.in_flight == 8

    def test_try_acquire_ninth_returns_false_synchronously(self) -> None:
        sem = DispatchSemaphore(cap=8)
        for _ in range(8):
            assert sem.try_acquire() is True

        ninth = sem.try_acquire()

        assert ninth is False
        assert sem.in_flight == 8  # overflow did not increment

    def test_try_acquire_is_not_a_coroutine(self) -> None:
        """No await — DDR-020 requires synchronous overflow detection."""
        sem = DispatchSemaphore(cap=2)

        result = sem.try_acquire()

        assert isinstance(result, bool)
        assert not inspect.iscoroutine(result)
        assert not inspect.isawaitable(result)

    def test_try_acquire_with_cap_one_allows_only_one(self) -> None:
        """Smallest valid cap still enforces the ceiling."""
        sem = DispatchSemaphore(cap=1)

        assert sem.try_acquire() is True
        assert sem.try_acquire() is False
        assert sem.in_flight == 1

    def test_default_cap_is_eight(self) -> None:
        """DDR-020: cap defaults to 8 in-flight calls."""
        sem = DispatchSemaphore()

        for _ in range(8):
            assert sem.try_acquire() is True
        assert sem.try_acquire() is False

    def test_invalid_cap_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="cap must be"):
            DispatchSemaphore(cap=0)
        with pytest.raises(ValueError, match="cap must be"):
            DispatchSemaphore(cap=-1)


# ============================================================================
# AC-002: release on success returns the slot
# ============================================================================


class TestReleaseOnSuccess:
    """AC-002: release() after successful try_acquire returns the slot."""

    def test_release_after_acquire_decrements_in_flight(self) -> None:
        sem = DispatchSemaphore(cap=8)
        assert sem.try_acquire() is True
        assert sem.in_flight == 1

        sem.release()

        assert sem.in_flight == 0

    def test_release_frees_slot_for_next_try_acquire(self) -> None:
        """After cap reached + one release, the next try_acquire must succeed."""
        sem = DispatchSemaphore(cap=2)
        assert sem.try_acquire() is True
        assert sem.try_acquire() is True
        assert sem.try_acquire() is False  # at ceiling

        sem.release()

        assert sem.try_acquire() is True
        assert sem.in_flight == 2

    def test_release_on_timeout_path(self) -> None:
        """A success path that "times out" still frees the slot via finally."""
        sem = DispatchSemaphore(cap=8)
        acquired = sem.try_acquire()
        assert acquired is True

        try:
            # Simulate a dispatch that timed out — caller still gets to release.
            raise TimeoutError("simulated specialist timeout")
        except TimeoutError:
            sem.release()

        assert sem.in_flight == 0

    def test_release_on_exception_path(self) -> None:
        """An exception in the work body still frees the slot via finally."""
        sem = DispatchSemaphore(cap=8)
        assert sem.try_acquire() is True

        try:
            raise RuntimeError("simulated specialist crash")
        except RuntimeError:
            sem.release()

        assert sem.in_flight == 0


# ============================================================================
# AC-003: release without matching acquire is a no-op
# ============================================================================


class TestReleaseIdempotency:
    """AC-003: release() without a matching acquire never raises or underflows."""

    def test_release_on_fresh_semaphore_is_noop(self) -> None:
        sem = DispatchSemaphore(cap=8)

        sem.release()  # no acquire happened — must not raise

        assert sem.in_flight == 0

    def test_double_release_does_not_underflow(self) -> None:
        sem = DispatchSemaphore(cap=8)
        assert sem.try_acquire() is True

        sem.release()
        sem.release()  # second release is the bug-class — must be a no-op

        assert sem.in_flight == 0

    def test_many_extra_releases_stay_at_zero(self) -> None:
        """Bounds underflow damage from a runaway release loop."""
        sem = DispatchSemaphore(cap=8)
        assert sem.try_acquire() is True
        sem.release()

        for _ in range(20):
            sem.release()

        assert sem.in_flight == 0

    def test_release_overflow_does_not_grant_extra_capacity(self) -> None:
        """Idempotent release must not "owe" the caller a free slot later."""
        sem = DispatchSemaphore(cap=2)
        assert sem.try_acquire() is True
        assert sem.try_acquire() is True

        # Three releases — only two should apply.
        sem.release()
        sem.release()
        sem.release()

        assert sem.in_flight == 0
        # And the cap is still 2:
        assert sem.try_acquire() is True
        assert sem.try_acquire() is True
        assert sem.try_acquire() is False


# ============================================================================
# AC-004: in_flight accuracy at any inspection point
# ============================================================================


class TestInFlightAccuracy:
    """AC-004: in_flight reflects the live counter at any point."""

    def test_in_flight_starts_at_zero(self) -> None:
        sem = DispatchSemaphore(cap=8)

        assert sem.in_flight == 0

    def test_in_flight_increments_per_acquire(self) -> None:
        sem = DispatchSemaphore(cap=8)

        for expected in range(1, 9):
            assert sem.try_acquire() is True
            assert sem.in_flight == expected

    def test_in_flight_decrements_per_release(self) -> None:
        sem = DispatchSemaphore(cap=8)
        for _ in range(5):
            sem.try_acquire()
        assert sem.in_flight == 5

        sem.release()
        assert sem.in_flight == 4
        sem.release()
        assert sem.in_flight == 3

    def test_in_flight_unchanged_on_overflow(self) -> None:
        sem = DispatchSemaphore(cap=2)
        sem.try_acquire()
        sem.try_acquire()
        snapshot_before = sem.in_flight

        assert sem.try_acquire() is False

        assert sem.in_flight == snapshot_before == 2

    def test_in_flight_property_is_read_only(self) -> None:
        sem = DispatchSemaphore(cap=8)

        with pytest.raises(AttributeError):
            sem.in_flight = 99  # type: ignore[misc]

    def test_cap_property_exposes_configured_ceiling(self) -> None:
        sem = DispatchSemaphore(cap=4)

        assert sem.cap == 4


# ============================================================================
# Integration — the dispatch-tool usage shape (try_acquire / try / finally)
# ============================================================================


class TestDispatchUsageShape:
    """The exact pattern dispatch_by_capability + queue_build will follow."""

    @pytest.mark.asyncio
    async def test_synchronous_overflow_inside_async_caller(self) -> None:
        """The dispatch tool is async but try_acquire must be sync.

        The whole point of DDR-020's synchronous overflow path is that an
        async tool can render DEGRADED without ever yielding control.
        """
        sem = DispatchSemaphore(cap=1)

        async def call() -> str:
            if not sem.try_acquire():
                return "DEGRADED: dispatch_overloaded"
            try:
                await asyncio.sleep(0)
                return "ok"
            finally:
                sem.release()

        first, second = await asyncio.gather(
            call(),
            _immediate_second_call(sem),
        )
        # Either ordering is acceptable; what matters is that exactly one
        # call sees DEGRADED and the other sees ok.
        assert {first, second} == {"ok", "DEGRADED: dispatch_overloaded"}
        assert sem.in_flight == 0


async def _immediate_second_call(sem: DispatchSemaphore) -> str:
    """Helper that races for the only slot without awaiting first."""
    if not sem.try_acquire():
        return "DEGRADED: dispatch_overloaded"
    try:
        await asyncio.sleep(0)
        return "ok"
    finally:
        sem.release()
