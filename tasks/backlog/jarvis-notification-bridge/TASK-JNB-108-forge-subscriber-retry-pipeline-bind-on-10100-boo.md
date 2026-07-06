---
id: TASK-JNB-108
title: "jarvis: forge-notifications subscriber must retry the PIPELINE bind on err 10100 (boot restart race leaves the phone silent)"
status: backlog
created: 2026-07-06T15:30:00Z
updated: 2026-07-06T15:30:00Z
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

- [ ] AC-1 **Bounded retry on 10100:** when the PIPELINE subscribe fails with
      err_code 10100 at startup, retry the same bind with backoff (e.g. 4–5
      attempts across ~30s — enough to outlive the predecessor's ephemeral
      cleanup) before declaring soft-fail. Retries must not block the rest of
      supervisor boot (DDR-021): run the retry loop as a background task after
      the first failure, binding the subscriber when it succeeds.
- [ ] AC-2 **Loud terminal degradation:** if retries are exhausted, emit a
      distinct event (`jarvis_forge_subscriber_degraded`, level=error) naming
      the consequence ("build lifecycle notifications OFF until restart") —
      distinguishable from the transient `jarvis_forge_subscriber_start_failed`
      warning so an operator grep catches it.
- [ ] AC-3 **Shutdown drains the consumer:** verify (and fix if absent) that
      the SIGINT stop path unsubscribes/drains the ephemeral PIPELINE consumer
      before the connection closes, so a successor bind does not race at all.
      If the drain already exists, document in the task file why the race
      still occurred (e.g. broker-side cleanup latency) and rely on AC-1.
- [ ] AC-4 **Non-overlap preserved:** the retry path must never leave two
      live jarvis PIPELINE consumers (single-consumer rule; err 10100 is the
      broker enforcing it — retry the same subscribe, never widen filters or
      mint durables).
- [ ] AC-5 **Tests (plain pytest, no BDD glue):** (a) first bind raises 10100,
      retry succeeds → subscriber active, `jarvis_forge_subscriber_started`
      emitted, sink receives a lifecycle event end-to-end; (b) all retries
      raise 10100 → `jarvis_forge_subscriber_degraded` emitted, supervisor
      boot completes anyway; (c) non-10100 startup errors keep today's
      single-shot soft-fail behaviour (no retry storm on auth failures).

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
