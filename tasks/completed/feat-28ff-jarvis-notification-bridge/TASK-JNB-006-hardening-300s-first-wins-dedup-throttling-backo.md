---
id: TASK-JNB-006
title: 'Hardening: 300s first-wins dedup, throttling backoff, overflow bounds'
status: completed
created: 2026-07-03 15:30:00+00:00
updated: 2026-07-03 15:30:00+00:00
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 4
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-JNB-003
tags:
- ubs-003
- jarvis-notification-bridge
- slack
- v1
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-28FF
  base_branch: main
  started_at: '2026-07-03T20:14:21.639835'
  last_updated: '2026-07-03T20:26:09.637906'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-07-03T20:14:21.639835'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: Hardening: 300s first-wins dedup, throttling backoff, overflow bounds

## Description

In `src/jarvis/infrastructure/slack_notifier.py` add the ASSUM-006 dedup map: first-wins 300s TTL keyed `(event_type, build_id, stage_label or '')` for stream events and `('build_queued', correlation_id)` for the intake event, using a monotonic clock, evict-on-insert; ~1 msg/s pacing on the worker; 429 handling honouring `Retry-After` with a bounded per-message retry budget then WARNING + drop; bounded-queue overflow dropping the oldest message with exactly one WARNING.

Architecture context: `SlackNotifier` lives in the jarvis supervisor process and implements the `NotificationSink` protocol — `notify(ForgeNotification)` enqueues onto a bounded `asyncio.Queue` drained by a single worker task that serialises `chat.postMessage` at ~1 msg/s. Every failure other than a 429 within its retry budget is WARNING + drop (DDR-007 — the SQLite ledger is authoritative; the notifier can never raise into the JetStream callback or `queue_build`). The dedup map sits inside `SlackNotifier` at enqueue time, not in the subscriber or dispatch hook, so both the stream fan-out path (`ForgeNotificationsSubscriber._handle_message` calling `sink.notify()`) and the queued-hook path (`tools/dispatch.py` `queue_build` fire-and-forget via the module-level `_notification_sink` snapshot) are covered by one mechanism. The sink was constructed and bound in `infrastructure/lifecycle.py` `build_app_state` by TASK-JNB-003; this task hardens the already-live component.

Note: the live v1 checkpoint (TASK-JNB-004) runs before this task lands, so an at-least-once JetStream redelivery during the toy run could double-post — cosmetic and expected. This task closes that gap.

## Acceptance Criteria

- [ ] Dedup map is first-wins with a 300s TTL, keyed `(event_type, build_id, stage_label or '')` for stream events and `('build_queued', correlation_id)` for the intake event (ASSUM-006).
- [ ] TTL is measured with a monotonic clock (`time.monotonic()`), never wall clock; expired entries are evicted on insert.
- [ ] A duplicated terminal envelope (same event_type/build_id redelivered within 300s) posts to Slack exactly once.
- [ ] Two distinct concurrent terminal events (different build_ids) both post, and each message contains only its own build's fields — no cross-contamination.
- [ ] Worker paces `chat.postMessage` at ~1 msg/s.
- [ ] A 429 response honours `Retry-After`, retries within a bounded per-message retry budget, and on budget exhaustion logs WARNING and drops that message (DDR-007 — never raises).
- [ ] A mocked 429 burst backs off, keeps delivering subsequent messages after the backoff, and never blocks the subscriber callback or the event loop (enqueue returns immediately; backoff sleeps happen only in the worker task).
- [ ] Bounded-queue overflow drops the oldest queued message and emits exactly one WARNING per drop; enqueue never blocks and never raises.
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

Plain pytest only — NO pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror the spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

- `TestDuplicateTerminalEnvelopePostsOnce` — deliver the same terminal `ForgeNotification` twice within the TTL through `notify()`; assert the mocked Slack client received exactly one `chat.postMessage`.
- `TestDedupTtlExpiry` — same key delivered again after the 300s window (advance a patched monotonic clock, do not sleep) posts a second time; assert evict-on-insert removes expired entries from the map.
- `TestDistinctConcurrentTerminalsBothPost` — two terminals for different build_ids delivered concurrently; assert two posts, each carrying only its own build's fields.
- `TestQueuedIntakeDedupKeyedOnCorrelationId` — two `build_queued` notifications with the same correlation_id post once; different correlation_ids post twice.
- `Test429BackoffHonoursRetryAfter` — mock the Slack client to return a 429 with `Retry-After: N` then succeed; assert the worker waits ~N (patched sleep/clock), the message is delivered, and later messages still flow.
- `Test429BudgetExhaustionWarnsAndDrops` — sustained 429s beyond the retry budget: assert WARNING logged, message dropped, no exception propagates, subsequent messages deliver.
- `TestOverflowDropsOldestWithOneWarning` — fill the bounded queue past capacity; assert the oldest entry is dropped, exactly one WARNING per drop, and `notify()` returned without blocking.
- `TestNotifyNeverBlocksEventLoop` — with the worker stalled in a 429 backoff, `notify()` for a new event completes immediately (bounded await, e.g. `asyncio.wait_for` with a small timeout).

Use `unittest.mock.AsyncMock` for the Slack client; patch the monotonic clock and `asyncio.sleep` rather than real waiting so the suite stays fast and deterministic.

## Implementation Notes

- Dependency: TASK-JNB-003 (lifecycle wiring — `SlackNotifier` is constructed and bound in `infrastructure/lifecycle.py` `build_app_state`). This task modifies the existing `src/jarvis/infrastructure/slack_notifier.py`; it introduces no new modules and no new wiring.
- Single-consumer rule: do NOT create or touch any NATS consumer. The Slack surface is an in-process sink invoked inside the one existing ephemeral PIPELINE consumer; a second PIPELINE consumer triggers workqueue err_code 10100. All hardening in this task is internal to `SlackNotifier`.
- DDR-007 never-regress: `notify()` and the worker must never raise into the JetStream callback or `queue_build`. Every failure path (429 budget exhausted, arbitrary `SlackApiError`, overflow) is WARNING + continue. The SQLite ledger is authoritative; Slack is best-effort.
- DDR-027 no-replay: dedup state is in-process only. A jarvis crash-loop inside a 300s window may double-post low-impact noise — accepted, do not persist the map.
- Correlation-INDEPENDENT fan-out is deliberate: `sink.notify()` fires before and independent of the correlation-map lookup, so dedup keys must not assume a correlation entry exists for stream events — hence the `(event_type, build_id, stage_label or '')` key; only the intake event keys on correlation_id.
- Suppression policy (stage_complete/build_progress/build_resumed per ASSUM-002) already exists in the sink; apply dedup after the suppression gate so suppressed events never occupy map slots.
- Pacing and 429 backoff belong exclusively in the worker task draining the queue; enqueue-side code must stay non-blocking and non-raising.
- The autobuild worktree is jarvis-scoped: it cannot read the sibling forge repo. Everything needed to implement this task is contained in this file.

> **[WS3-S8 tracker sweep 2026-07-11]** status reconciled to `completed` - FEAT-28FF rollup (feature yaml status=completed, task per-task completed; 133f2e4).
