---
id: TASK-J004-008
title: "infrastructure/dispatch_semaphore.py — DispatchSemaphore wrapper"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 2
implementation_mode: direct
complexity: 3
dependencies: [TASK-J004-003]
priority: high
tags: [infrastructure, dispatch, semaphore, concurrency, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-008 — DispatchSemaphore wrapper

## Description

Land `src/jarvis/infrastructure/dispatch_semaphore.py` per
[API-internal.md §5](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md):

```python
class DispatchSemaphore:
    def __init__(self, *, cap: int = 8) -> None: ...
    def try_acquire(self) -> bool: ...
    def release(self) -> None: ...
    @property
    def in_flight(self) -> int: ...
```

Thin wrapper around `asyncio.Semaphore(cap)`. The point of the wrapper:

1. **Non-blocking `try_acquire()`** — DDR-020 requires synchronous
   overflow detection (`asyncio.Semaphore.acquire` is async; we want
   immediate False on overflow so the dispatch tool returns
   `DEGRADED: dispatch_overloaded` synchronously).
2. **`in_flight` property** — feeds `ConcurrentWorkloadSnapshot` into
   the routing-history record.
3. **Idempotent `release()`** — safe in `finally` blocks even after a
   double-release path bug.

Plus `tests/test_dispatch_semaphore.py` covering exact-cap ceiling and
release semantics.

## Acceptance Criteria

- [ ] `DispatchSemaphore(cap=8)` allows exactly 8 concurrent acquisitions; the 9th `try_acquire()` returns `False` synchronously (no `await`).
- [ ] `release()` after a successful `try_acquire()` returns the slot.
- [ ] `release()` without a matching acquire is a no-op (no exception, no underflow).
- [ ] `in_flight` reflects acquired slots accurately at any inspection point.
- [ ] `tests/test_dispatch_semaphore.py` covers: exact ceiling (8 OK, 9th False); release on success; release on timeout; release on exception path; double-release idempotency; `in_flight` accuracy.
- [ ] `uv run mypy src/jarvis/infrastructure/dispatch_semaphore.py` strict-clean.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Tests use real `asyncio.Semaphore` — no mocks. The wrapper is small enough to test end-to-end.

## Implementation Notes

`asyncio.Semaphore.locked()` returns True only when the counter is
0 — useful for the `try_acquire` non-blocking path. Implementation
sketch:

```python
def try_acquire(self) -> bool:
    if self._sem.locked():
        return False
    # _value is private but stable; alternative: check via a counter we maintain
    self._sem._value -= 1   # or use a counter wrapper
    self._in_flight += 1
    return True
```

Prefer maintaining an explicit counter rather than touching
`_value` — implementations vary by Python version.

## Test Execution Log

(Populated by /task-work.)
