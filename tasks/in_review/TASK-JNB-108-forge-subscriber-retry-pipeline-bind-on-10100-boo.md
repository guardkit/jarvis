---
id: TASK-JNB-108
title: "jarvis: forge-notifications subscriber must retry the PIPELINE bind on err 10100 (boot restart race leaves the phone silent)"
status: in_review
created: 2026-07-06T15:30:00Z
updated: 2026-07-06T16:45:00Z
previous_state: backlog
state_transition_reason: "task-work complete: bounded background retry on err 10100 + loud degraded event landed; AC-5 tests green (tests/test_lifecycle_forge_subscriber_retry.py); AC-3 shutdown-drain investigation documented below"
priority: high
task_type: implementation
repo: jarvis
implementation_mode: task-work
complexity: 4
dependencies: []
tags: [defect, jarvis-notification-bridge, nats, ddr-021, found-2026-07-06]
---

# Task: forge-notifications subscriber must retry the PIPELINE bind on err 10100

## Defect (observed live, GB10, 2026-07-06)

During the TASK-JNB-OPS-001 secrets restart, `systemctl --user restart
jarvis-serve-nats` produced this boot sequence (journal, 15:00:17):

```
{"event": "slack_reply_socket_mode_started", ...}
{"error_class": "BadRequestError",
 "error": "nats: BadRequestError: code=400 err_code=10100
           description='filtered consumer not unique on workqueue stream'",
 "event": "jarvis_forge_subscriber_start_failed", "level": "warning", ...}
```

**Root cause — restart race:** `restart` = SIGINT the old process, start the
new one ~1s later. The old process's **ephemeral PIPELINE consumer** was still
registered on the broker when the new process tried to bind; PIPELINE is a
workqueue stream, which rejects overlapping filtered consumers with err 10100.
The lifecycle soft-fail (DDR-021, `lifecycle.py` "7d" block) then sets
`forge_subscriber = None` with **no retry**, so the supervisor comes up
healthy-looking while **every build lifecycle phone notification is dead**
(build-started/paused/resumed/cancelled/complete) until a manual restart.

Proof of mechanism: a second restart with a 10s stop-gap
(`stop; sleep 10; start`) bound cleanly at 15:13:47 —
`jarvis_forge_subscriber_started` (queue_cap=100, correlation_cap=1000), new
ephemeral consumer visible in `nats consumer ls PIPELINE`, no 10100.

**Why this is high priority:** TASK-JNB-107's acceptance criteria treat any
err_code 10100 in boot logs as a hard failure of the live validation, and the
degraded state is silent — nothing downstream alarms. Every fast restart
(deploy, crash-loop `RestartSec=5`, operator restart) can reproduce it.

## Acceptance Criteria

- [x] AC-1 **Bounded retry on 10100:** when the PIPELINE subscribe fails with
      err_code 10100 at startup, retry the same bind with backoff (e.g. 4–5
      attempts across ~30s — enough to outlive the predecessor's ephemeral
      cleanup) before declaring soft-fail. Retries must not block the rest of
      supervisor boot (DDR-021): run the retry loop as a background task after
      the first failure, binding the subscriber when it succeeds.
      → `lifecycle.py` 7d block: on a 10100 rejection the subscriber is
      **kept non-None** (so the session-manager bind + dispatch snapshot still
      wire it) and `_retry_forge_subscriber_bind` is scheduled via
      `asyncio.create_task`. Schedule: 1 synchronous boot attempt + 4
      background retries at `FORGE_SUBSCRIBER_BIND_RETRY_DELAYS_SECONDS =
      (5, 7, 8, 10)` → 5 attempts across ~30s.
- [x] AC-2 **Loud terminal degradation:** if retries are exhausted, emit a
      distinct event (`jarvis_forge_subscriber_degraded`, level=error) naming
      the consequence ("build lifecycle notifications OFF until restart") —
      distinguishable from the transient `jarvis_forge_subscriber_start_failed`
      warning so an operator grep catches it.
      → Terminal `log.error("jarvis_forge_subscriber_degraded",
      consequence="build lifecycle notifications OFF until restart", …)` on
      exhaustion (and on a non-10100 error appearing mid-retry). The
      per-attempt transient stays `jarvis_forge_subscriber_start_failed`
      (warning) so the two grep apart.
- [x] AC-3 **Shutdown drains the consumer:** verify (and fix if absent) that
      the SIGINT stop path unsubscribes/drains the ephemeral PIPELINE consumer
      before the connection closes, so a successor bind does not race at all.
      If the drain already exists, document in the task file why the race
      still occurred (e.g. broker-side cleanup latency) and rely on AC-1.
      → **The drain already exists** — see "AC-3 investigation" below. The
      race persists because of broker-side ephemeral-consumer reap latency;
      AC-1 is the fix. Also hardened shutdown to cancel the new background
      retry task *before* `forge_subscriber.stop()` so a pending bind cannot
      outlive teardown.
- [x] AC-4 **Non-overlap preserved:** the retry path must never leave two
      live jarvis PIPELINE consumers (single-consumer rule; err 10100 is the
      broker enforcing it — retry the same subscribe, never widen filters or
      mint durables).
      → The retry re-invokes the **same** `forge_subscriber.start()` verbatim
      (identical `filter_subjects`, ephemeral, `deliver_policy=ALL`). `start()`
      is idempotent (a failed attempt leaves `_started=False`, no partial
      consumer), so a success leaves exactly one live consumer. No durable,
      no widened filter, no second `subscribe`.
- [x] AC-5 **Tests (plain pytest, no BDD glue):** (a) first bind raises 10100,
      retry succeeds → subscriber active, `jarvis_forge_subscriber_started`
      emitted, sink receives a lifecycle event end-to-end; (b) all retries
      raise 10100 → `jarvis_forge_subscriber_degraded` emitted, supervisor
      boot completes anyway; (c) non-10100 startup errors keep today's
      single-shot soft-fail behaviour (no retry storm on auth failures).
      → `tests/test_lifecycle_forge_subscriber_retry.py`: `TestBootRaceSchedulesRetry`
      + `TestEndToEndSinkAfterRetry` (a), `TestRetryExhaustedDegrades` (b),
      `TestNon10100SingleShot` parametrised over an auth failure and a 10101
      deliver-policy error (c), plus `TestShutdownCancelsRetryTask`.

## AC-3 investigation — the drain exists; broker reap latency is why it wasn't enough

The SIGINT stop path **does** already unsubscribe before the connection
closes:

* `shutdown()` runs `forge_subscriber.stop()` (step 1b) *before*
  `nats_client.drain()` (step 5) — ordering asserted by
  `tests/test_lifecycle_shutdown_order.py`.
* `ForgeNotificationsSubscriber.stop()` calls `sub.unsubscribe()` (bounded
  by `asyncio.wait_for`, never raises).

But `nats-py`'s `Subscription.unsubscribe()` only sends a **client-side
`UNSUB`** (`_send_unsubscribe`) — it removes local interest. It does **not**
issue a JetStream `delete_consumer` for the auto-created ephemeral consumer.
The broker reaps that ephemeral consumer only after its **inactivity
threshold** elapses (the server-side `inactive_threshold` / heartbeat reaper),
which outlasts the ~1s `systemctl restart` gap. So at successor-boot time the
predecessor's consumer is still registered on the workqueue PIPELINE stream,
its identical `filter_subjects` are "not unique", and JetStream rejects the
bind with `err_code=10100`.

Forcing an immediate `js.delete_consumer(...)` on stop was considered and
rejected for this task: the consumer name is server-assigned, the delete adds
a broker round-trip on the shutdown-critical path (which must stay bounded and
best-effort), and it still would not cover the crash-loop / `RestartSec` case
where the predecessor never runs its stop path at all. AC-1's bounded
background retry covers **every** restart flavour (clean, crash, deploy)
uniformly by outliving the reap latency, so it is the load-bearing fix and
AC-3 relies on it per the task's own guidance.

## Constraints

- DDR-021: nothing here may block or crash supervisor boot.
- DDR-007: no exceptions may escape into JS callbacks; retry task must
  swallow-and-log.
- The Slack surface and approval subscriber (AGENTS stream) are unaffected —
  scope is only the ForgeNotificationsSubscriber PIPELINE bind
  (`src/jarvis/infrastructure/forge_notifications.py` +
  `src/jarvis/infrastructure/lifecycle.py` 7d block).
- Evidence for the reproduction is in the 2026-07-06 journal on the GB10 and
  the OPS-001 session notes; the fix should land before the next
  deploy-restart cycle so JNB-107's boot check stays clean.

## Post-implementation adversarial review

A 4-dimension adversarial review (concurrency/races, AC-faithfulness, DDR
compliance, test quality) with independent refutation of every finding raised
7 candidates and **confirmed 2 — both test-coverage gaps, zero production
defects**. The shipped retry/degrade/shutdown logic verified correct.

1. **(medium) Non-blocking property not pinned.** The AC-5a/AC-5b tests
   asserted `start.await_count == 2` only *after* awaiting the retry task, so a
   regression that inlined the `await` inside `build_app_state` (blocking boot
   for the full backoff — the exact DDR-021/AC-1 violation) would still pass.
   Fixed: both tests now assert `start.await_count == 1` and
   `retry_task.done() is False` at boot-return time. A mutation test (inline
   `await` injected) confirms both tests now fail on that regression and pass
   once reverted — there is no `await` between the `create_task` and
   `return state`, so the assertion is deterministic.
2. **(low) Mid-retry non-overlap branch untested.** The
   `reason="non_overlap_error_during_retry"` degrade path (a *different* error
   surfacing on a later retry after the boot race) had no coverage. Fixed:
   `TestNonOverlapErrorDuringRetry` drives `side_effect=[10100, RuntimeError]`
   and asserts exactly one `jarvis_forge_subscriber_degraded` at error level
   with that reason, `start.await_count == 2` (no storm), and no exhaustion
   event.

Suite after hardening: `tests/test_lifecycle_forge_subscriber_retry.py`
7 passed; the forge/lifecycle/nats-subscriptions related set 125 passed; full
suite green.
