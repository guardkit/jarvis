---
id: TASK-J006-010
title: Bound startup reconnect — fail fast when broker is unreachable at boot
task_type: bug
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 5
implementation_mode: task-work
complexity: 2
priority: critical
status: backlog
dependencies:
  - TASK-J006-005
created: 2026-05-12 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
tags:
  - nats
  - infrastructure
  - bug
  - demo-blocker
  - hard-dependency-posture
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Bound startup reconnect — fail fast when broker is unreachable at boot

## Severity / impact

**P0 — demo-blocker if broker hiccups during the 2026-05-16 DDD Southwest demo.**

`jarvis serve-nats` retries `ConnectionRefusedError` to the NATS broker
**indefinitely** on boot rather than exiting non-zero with a clear error.
This violates the hard-dependency posture documented in
`docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md` §3.8 and
fails AC-005-08 of TASK-J006-005.

If the broker is briefly unavailable during demo prep (container restart,
network blip, healthcheck flap), serve-nats will start, hang in a silent
reconnect loop, and never log "ready" — the operator will see nothing wrong
in the foreground process. With NATS healthy again the gateway should be
explicitly restarted; the current behaviour blurs that observation.

## Bug specification

### Expected behaviour (per runbook §3.8 / AC-005-08)

> Pass: Process exits within ~10s (no indefinite hang). Exit code is non-zero
> (typically 1 or 2). Log contains a clear error naming the unreachable broker
> (e.g., `nats_connect_failed`, `ConnectionRefusedError`, or equivalent) — not
> a vague stack trace. No `jarvis_startup_complete` line in the log (we never
> reached ready).

### Actual behaviour (2026-05-12 GB10 evidence)

1. Stop broker: `docker stop ships-computer-nats`
2. `JARVIS_LOG_LEVEL=INFO jarvis serve-nats --nats nats://rich:****@localhost:4222`
3. Observed log (`/tmp/jarvis-serve-nats-broker-down.log`, abridged):
   ```json
   {"event":"jarvis_startup_begin","timestamp":"...13:44:07.703Z"}
   {"event":"jarvis_store_ready","timestamp":"...13:44:07.704Z"}
   {"event":"jarvis_capability_registry_loaded","timestamp":"...13:44:07.710Z"}
   {"event":"jarvis_async_subagents_built","timestamp":"...13:44:07.710Z"}
   {"error_class":"ConnectionRefusedError",
    "error":"[Errno 111] Connect call failed ('127.0.0.1', 4222)",
    "event":"nats_error","level":"warning",
    "timestamp":"...13:44:07.711Z"}
   {"event":"nats_error","timestamp":"...13:44:09.715Z"}    # +2s
   {"event":"nats_error","timestamp":"...13:44:11.719Z"}    # +2s
   ... (15 retries over 28s, same level=warning, same shape)
   ```
4. `timeout 30 jarvis serve-nats ...` had to kill the process from outside
   (exit code 124 from `coreutils timeout`, not from jarvis)
5. No `jarvis_startup_complete`, no `jarvis_startup_aborted`,
   no `nats_connect_failed` terminal event. Just unbounded
   `nats_error` warnings at the underlying `nats-py` reconnect cadence.

### Root cause (provisional)

`nats-py` client's `connect()` uses `max_reconnect_attempts` defaults that
let it loop indefinitely. Jarvis's `NATSClient` wrapper (boot path in
`src/jarvis/infrastructure/lifecycle.py` calling
`src/jarvis/infrastructure/nats_client.py`) doesn't pass a finite
`max_reconnect_attempts` nor wrap the initial connect call in an `asyncio.wait_for(...)` budget. The result is that the boot path can never declare
broker-unreachable — it can only declare broker-eventually-reachable.

## Recommended fix scope

Two small, additive changes in `src/jarvis/infrastructure/nats_client.py`
(connect path) **only** — do NOT change steady-state reconnect behaviour
(which is correct: once running, jarvis should reconnect on transient
broker hiccups).

1. **Bound the initial connect:** wrap the `await self._client.connect(...)`
   call (or the `lifecycle.py` equivalent) in `asyncio.wait_for(...,
   timeout=config.startup_connect_timeout_seconds)`, default 10s. On
   `asyncio.TimeoutError`, log `nats_connect_failed` (INFO/ERROR) naming
   `nats_url` and the elapsed budget, then re-raise so the CLI exits with
   a non-zero code via the standard click/asyncio.run error path.

2. **Make the warning emit observable as the failure cause:** when
   `connect()` is invoked from the startup path and exhausts the budget,
   emit a single terminal `nats_connect_failed` event (level=error) that
   names both the broker URL and the underlying exception class
   (`ConnectionRefusedError`, `nats.errors.NoServersError`,
   `nats.errors.AuthorizationError`, etc.). The existing per-retry
   `nats_error` warnings are noise once a failure is conclusive.

A new pydantic-settings field `startup_connect_timeout_seconds: int = Field(
default=10, ge=1, le=60)` belongs in `config/settings.py` alongside
`heartbeat_interval_seconds`.

## Acceptance Criteria

- **AC-010-01:** With the broker stopped, `jarvis serve-nats --nats <url>`
  exits within `startup_connect_timeout_seconds + ~1s` (default 10s) with
  exit code non-zero.
- **AC-010-02:** Log contains exactly one terminal `nats_connect_failed`
  event (level=error) naming the URL, the underlying exception class, and
  the elapsed wall-clock. Per-retry `nats_error` warnings are suppressed
  in the startup path (or, at minimum, capped).
- **AC-010-03:** No `jarvis_startup_complete` event is emitted.
- **AC-010-04:** Steady-state behaviour unchanged: once jarvis is up and
  the broker hiccups (drops connection mid-run), the existing reconnect
  loop continues as before — this task does NOT bound runtime reconnect.
- **AC-010-05:** Unit test (`tests/test_nats_client_startup_timeout.py`)
  monkeypatches `nats.connect` to raise `ConnectionRefusedError` and
  asserts the wrapper raises a typed `BrokerUnreachableError` (or
  re-raises with the bounded wait) within `startup_connect_timeout_seconds`.
- **AC-010-06:** Live verification on GB10: rerun runbook Phase 3.8 from
  TASK-J006-005; AC-005-08 flips ✅ (exit ≤10s, non-zero, terminal log line
  present). Evidence in next-run `RESULTS-FEAT-JARVIS-006-serve-nats-*.md`.

## Implementation Notes

- Decision point: pass `max_reconnect_attempts=1` to `nats.connect` vs.
  wrap with `asyncio.wait_for`. The latter is preferred — `nats-py`'s
  reconnect loop semantics differ subtly across versions and the
  `wait_for` approach is provider-agnostic.
- The shutdown path (`nats_client.drain`) already bounds at 5s — re-use
  that pattern (bounded `wait_for`, terminal log line) for symmetry.
- Naming: prefer `BrokerUnreachableError(RuntimeError)` over
  `ConnectionError` so callers can distinguish "broker bounded out at
  startup" from "ad-hoc TCP refusal mid-run".

## Out of scope

- Changing steady-state reconnect to bounded — that would weaken the
  recovery posture (jarvis SHOULD survive transient broker hiccups
  mid-run; only the boot path needs the explicit fail-fast).
- Adding a circuit-breaker, exponential-backoff curve, or jitter to
  the existing reconnect loop. Those are nice-to-haves; the
  hard-dependency-posture-at-boot is the demo-critical fix.

## See also

- Evidence: `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12.md`
- Evidence log: `docs/runbooks/evidence/feat-jarvis-006-first-run/jarvis-serve-nats-broker-down.log`
- Runbook: `docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md` §3.8 / AC-005-08
- Parent task: `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-005-live-openwebui-demo-verification.md`
- Companion bug: `TASK-J006-009-fix-subscribe-with-reply-envelope-unwrap.md` (also discovered in the same verification session)
