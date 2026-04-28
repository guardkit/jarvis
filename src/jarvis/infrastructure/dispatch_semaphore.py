"""DispatchSemaphore — synchronous, non-blocking concurrency cap.

TASK-J004-008 — bounds the number of in-flight ``dispatch_by_capability`` and
``queue_build`` calls per
[API-internal.md §5](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md).

Why this isn't a thin wrapper around ``asyncio.Semaphore``
---------------------------------------------------------

The task brief describes a "thin wrapper around ``asyncio.Semaphore(cap)``", but
``asyncio.Semaphore`` exposes no public *non-blocking* acquire path — only the
async ``acquire()`` coroutine and the binary ``locked()`` predicate. DDR-020
requires the dispatch tool to detect overflow synchronously so it can return
``DEGRADED: dispatch_overloaded`` without ``await`` (the Phase 2 dispatch code
path is a tool function, not a coroutine).

Touching ``asyncio.Semaphore._value`` directly was the original sketch but is
explicitly discouraged in the task's Implementation Notes — the private slot
varies across CPython versions. Instead, this module maintains an explicit
counter under a ``threading.Lock`` so:

1. ``try_acquire()`` returns ``False`` synchronously on overflow.
2. ``release()`` is idempotent — safe to call from ``finally`` blocks even
   after a double-release path bug, and a no-op when ``in_flight == 0``.
3. ``in_flight`` reflects the live counter for ``ConcurrentWorkloadSnapshot``.

The lock makes the wrapper safe to share across threads (the routing-history
writer runs on a worker thread) without inheriting asyncio's loop affinity.
"""

from __future__ import annotations

import threading

__all__ = ["DispatchSemaphore"]


class DispatchSemaphore:
    """Non-blocking concurrency cap with idempotent release.

    DDR-020 caps in-flight ``dispatch_by_capability`` + ``queue_build`` calls
    at ``cap=8`` by default. Use :meth:`try_acquire` before launching work and
    :meth:`release` in a ``finally`` block when the work completes (success,
    timeout, or exception path — all three call ``release`` exactly once).

    Attributes
    ----------
    in_flight
        Number of slots currently held. Read via the property; never mutate
        directly.

    Example
    -------
    >>> sem = DispatchSemaphore(cap=8)
    >>> if not sem.try_acquire():
    ...     return "DEGRADED: dispatch_overloaded — wait and retry"
    >>> try:
    ...     ...  # do work
    ... finally:
    ...     sem.release()
    """

    def __init__(self, *, cap: int = 8) -> None:
        if cap < 1:
            raise ValueError(f"cap must be >= 1, got {cap}")
        self._cap: int = cap
        self._in_flight: int = 0
        self._lock: threading.Lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Synchronously attempt to acquire a slot.

        Returns
        -------
        bool
            ``True`` on success (slot acquired, ``in_flight`` incremented).
            ``False`` on overflow — ``in_flight`` already equals ``cap``. The
            caller should surface ``DEGRADED: dispatch_overloaded`` and *not*
            call :meth:`release` (no acquire happened).
        """
        with self._lock:
            if self._in_flight >= self._cap:
                return False
            self._in_flight += 1
            return True

    def release(self) -> None:
        """Return a slot. Idempotent — a release without a matching acquire
        is a no-op rather than an error.

        This makes ``release`` safe to call from ``finally`` blocks even when
        the surrounding code path is unsure whether ``try_acquire`` succeeded
        (e.g. early-return guards). It also bounds underflow damage from a
        double-release path bug to a single dropped decrement.
        """
        with self._lock:
            if self._in_flight <= 0:
                return
            self._in_flight -= 1

    @property
    def in_flight(self) -> int:
        """Slots currently held — feeds ``ConcurrentWorkloadSnapshot``."""
        with self._lock:
            return self._in_flight

    @property
    def cap(self) -> int:
        """Configured ceiling — exposed for diagnostics, never mutated."""
        return self._cap
