# DDR-020 — Concurrent dispatch cap = 8 via `asyncio.Semaphore`

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** ADR-ARCH-013 (Pattern B watcher ceiling = 10 — JA2), ADR-ARCH-021 (tools return structured errors), ADR-ARCH-026 (single instance, no horizontal scaling), [DDR-016](DDR-016-dispatch-timeout-default-60s.md), [DDR-017](DDR-017-retry-with-redirect-policy.md)

## Context

The supervisor can plausibly fire several `dispatch_by_capability` / `queue_build` calls in flight at once — Rich asks Jarvis to "ask the architect, the product owner, and the ideator in parallel" and the reasoning model emits three concurrent tool calls. With FEAT-J005's notification subscription + retry-with-redirect (DDR-017 = 2× timeout worst case = 120s), in-flight dispatches can stack up.

Phase 3 scope §"Open Questions": *"Concurrent dispatch cap. How many in-flight `dispatch_by_capability` / `queue_build` invocations before throttling? Related to JA2 (ambient watcher ceiling) but distinct — this is for synchronous supervisor-initiated dispatch."*

JA2 (ADR-ARCH-013) caps Pattern B watchers at 10 concurrent. The two budgets share the same machine (single Jarvis process per ADR-ARCH-026) but distinct mental models — watchers are background; dispatches are foreground.

## Decision

1. **Cap = 8 in-flight `dispatch_by_capability` + `queue_build` invocations** per supervisor process.
2. **Implementation:** an `asyncio.Semaphore(8)` constructed at lifecycle startup, snapshotted into `tools/dispatch.py` via `assemble_tool_list`.
3. **Overflow behaviour:** `try_acquire()` (non-blocking). On overflow:
   ```
   "DEGRADED: dispatch_overloaded — wait and retry"
   ```
   The reasoning model handles this per the ADR-ARCH-021 structured-error contract. **No queueing, no blocking** — the tool returns synchronously.
4. **Release** in `finally` block — covers success, timeout, exception paths.
5. **Both `dispatch_by_capability` and `queue_build` share the cap.** They compete for the same supervisor process resources (NATS connection, network, supervisor reasoning time).
6. **Configurable** via `JarvisConfig.dispatch_concurrent_cap` (default 8, range 1..64). Operator can tune via `JARVIS_DISPATCH_CONCURRENT_CAP=16` if real-world load motivates.

## Rationale

- **8, not 4.** 4 would throttle the "ask three specialists in parallel" UX too aggressively — once a specialist is in flight, Rich shouldn't wait to queue a build at the same time.
- **8, not 12+.** The single Jarvis process is bandwidth-bounded (one NATS connection, one Tailscale link, one supervisor reasoning loop). 12+ in-flight dispatches saturate that path before producing real value.
- **Stays under JA2's 10 watcher cap.** The two budgets share one machine; if both ran at full 10+ simultaneously, the supervisor's reasoning loop fights itself for time. 8 + 10 still oversubscribes a bit but leaves headroom for the supervisor's own reasoning + frontend tools.
- **`try_acquire()` not blocking `acquire()`.** Blocking would queue the call; the reasoning model has no insight into queue depth and would assume the dispatch is in flight. Surfacing the overload as a structured DEGRADED string lets reasoning back off, retry later, or surface it to Rich.
- **Same cap for dispatch + queue.** Bookkeeping symmetry; the underlying resource (supervisor process bandwidth) is the same. A future DDR can split them if observation shows wildly different latencies.
- **Configurable** so operators can tune without a code change. The default 8 is a starting point; `JARVIS_DISPATCH_CONCURRENT_CAP=16` is a knob if the v1 default proves too tight.

## Alternatives considered

| Option | Why not |
|---|---|
| 4 | Too tight — would frequently overflow on legitimate parallel-dispatch UX |
| 12, 16, 32 | Above the supervisor's bandwidth; produces queueing latency we then have to manage |
| No cap | Theoretical unlimited concurrency saturates NATS / supervisor resources before the reasoning model knows; breaks observability |
| Blocking `acquire()` (queue and wait) | Reasoning model has no view of queue depth; misleading "in flight" semantic; eats timeout_seconds budget while waiting on the semaphore |
| Separate caps for dispatch vs. queue | Premature — same underlying resource. Split via append-only DDR if observed contention warrants it |
| Hard fail → ERROR string | DEGRADED is the correct severity — the operation can succeed if reasoning retries shortly; ERROR implies "give up and tell Rich" |

## Consequences

- `infrastructure/dispatch_semaphore.py` is the new module (per [API-internal.md §5](../contracts/API-internal.md)).
- `JarvisConfig.dispatch_concurrent_cap: int = Field(default=8, ge=1, le=64)`.
- `dispatch_by_capability` runtime sequence (design §8) acquires before payload validation; releases in `finally`.
- `queue_build` (after FEAT-J005's transport swap) acquires the same semaphore.
- `JarvisRoutingHistoryEntry.concurrent_workload.in_flight_dispatches` captures the semaphore depth at decision time — feeds future capacity diagnostics.
- `tests/test_dispatch_semaphore.py` asserts: 8th call succeeds, 9th returns DEGRADED synchronously, release happens on success / timeout / exception, configurable cap takes effect.
- `tests/test_dispatch_by_capability_integration.py::test_concurrent_overflow` exercises the integration: launch 9 concurrent dispatches against a slow consumer, assert the first 8 succeed and the 9th gets DEGRADED.
- The reasoning model's "ask the architect, product owner, ideator in parallel" UX works (3 < 8); the synthetic "ask 20 specialists at once" pathological case fails fast and visibly.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. Operator-tunable via `JARVIS_DISPATCH_CONCURRENT_CAP`; default-change via append-only DDR if `jarvis.learning` (FEAT-J008) flags persistent overload patterns.
