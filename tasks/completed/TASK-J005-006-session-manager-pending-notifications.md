---
complexity: 4
created: 2026-04-29 00:00:00+00:00
dependencies: []
feature_id: FEAT-J005-946D
id: TASK-J005-006
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: completed
tags:
- sessions
- notifications
- DDR-030
- FEAT-JARVIS-005
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: SessionManager pending_notifications + per-session FIFO queue
updated: 2026-04-30T11:10:33Z
wave: 1
---

# TASK-J005-006 — SessionManager pending notification queue

## Description

Extend `src/jarvis/sessions/manager.py` (`SessionManager`) with a per-session
pending notification queue, per
[design.md §7](../../../docs/design/FEAT-JARVIS-005/design.md) and
[DDR-030](../../../docs/design/FEAT-JARVIS-005/decisions/DDR-030-cli-notifications-between-prompts.md):

- `enqueue_notification(session_id: str, notification: ForgeNotification) -> None`
  — appends to a per-session FIFO; cap = `JarvisConfig.forge_notifications_queue_cap`
  (default 100); on overflow evicts oldest with WARN
  `forge_notification_queue_overflow`.
- `pending_notifications(session_id: str) -> list[ForgeNotification]`
  — drains the per-session queue (returns + clears in one atomic operation;
  re-entry-safe per ASSUM-003 single-concurrent-invoke).
- `end_session(session_id)` clears the per-session queue (and discards future
  enqueues for that session).

The subscriber (TASK-J005-003) and the CLI render loop (TASK-J005-007) consume
these methods.

## Acceptance Criteria

- [ ] `enqueue_notification` appends to a session-scoped FIFO; FIFO is created on
      first call.
- [ ] When the queue is at cap, oldest entry is evicted before the new one is
      appended; one WARN log line per overflow.
- [ ] `pending_notifications` returns + clears atomically (no notification can be
      double-rendered or lost between drain and clear).
- [ ] `end_session` clears the per-session queue; subsequent
      `enqueue_notification` for that session_id is silently dropped (no raise).
- [ ] Cap value is read once from `JarvisConfig.forge_notifications_queue_cap` at
      construction time, not per-call.
- [ ] `uv run mypy src/jarvis/sessions/manager.py` passes (strict).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Unit test: enqueue exactly `cap` items; `pending_notifications` returns all
      `cap`; queue is empty after (Group B #1 boundary scenario).
- [ ] Unit test: enqueue `cap + 1` items; oldest is evicted, WARN logged, latest
      `cap` returned (Group B #2 boundary-overlap scenario).
- [ ] Unit test: `end_session` clears the queue; subsequent enqueue is dropped
      (Group D #3 scenario).
- [ ] Unit test: stage-complete enqueued for session A does not surface on
      session B (Group D #1 cross-session edge case).
- [ ] Unit test: `pending_notifications` is re-entry-safe — two sequential drains
      (per ASSUM-003) both return correct lists, no duplicates.

## Implementation Notes

- Use `collections.deque(maxlen=cap)` per session to get free FIFO + automatic
  eviction; wrap eviction with a manual check for the WARN log emission.
- Per-session map: `dict[str, deque[ForgeNotification]]`. Lazy-create on first
  enqueue.
- See DM-forge-notification §2 for the queue contract; see DDR-030 §Consequences
  for the SIGINT-safe drain semantics.