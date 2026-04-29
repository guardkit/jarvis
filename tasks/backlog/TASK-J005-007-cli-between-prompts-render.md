---
id: TASK-J005-007
title: cli/main.py REPL between-prompts notification render
task_type: feature
parent_review: TASK-REV-3B8B
feature_id: FEAT-J005-946D
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
  - TASK-J005-006
  - TASK-J005-002
priority: high
tags:
  - cli
  - repl
  - notifications
  - DDR-030
  - FEAT-JARVIS-005
status: backlog
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
consumer_context:
  - task: TASK-J005-002
    consumes: ForgeNotification.render_line
    framework: "Pydantic v2 (frozen BaseModel)"
    driver: pydantic
    format_note: "render_line() returns canonical [HH:MM] Forge {feature_id}: stage {stage_label} ({status}) per DM-forge-notification §1"
  - task: TASK-J005-006
    consumes: SessionManager.pending_notifications
    framework: SessionManager
    driver: in-process
    format_note: "pending_notifications(session_id) drains + clears the per-session FIFO atomically; called once at REPL top-of-loop, before reading the next prompt"
---

# TASK-J005-007 — CLI between-prompts notification render

## Description

Update `src/jarvis/cli/main.py` `jarvis chat` REPL: at the top of each prompt
loop, drain `session_manager.pending_notifications(session_id)` and emit one
`click.echo` per notification before reading user input, per
[design.md §8 CLI render sequence](../../../docs/design/FEAT-JARVIS-005/design.md)
and [DDR-030](../../../docs/design/FEAT-JARVIS-005/decisions/DDR-030-cli-notifications-between-prompts.md).

Behaviour:

- Render is between prompts only — never mid-turn (DDR-030 §Why).
- One `click.echo` per notification, formatted via
  `notification.render_line()`.
- Notifications arriving during a supervisor turn are buffered (by the
  SessionManager queue) and rendered at the next REPL iteration (Group D #2).
- SIGINT-safe: queue is drained once per loop iteration before
  `click.prompt(...)`; KeyboardInterrupt during prompt does not lose buffered
  notifications.

## Acceptance Criteria

- [ ] REPL loop calls `session_manager.pending_notifications(session_id)` once
      per iteration, before `click.prompt(...)`.
- [ ] Each pending notification rendered via one `click.echo(notification.render_line())`
      call, in FIFO order.
- [ ] Notifications enqueued during a supervisor turn surface on the next
      iteration, never mid-turn (Group D #2 scenario).
- [ ] SIGINT during `click.prompt` leaves any not-yet-rendered notifications in
      the queue for the next iteration (no loss).
- [ ] Empty queue → no output, no spurious blank lines.
- [ ] `uv run mypy src/jarvis/cli/main.py` passes (strict).
- [ ] All modified files pass project-configured lint/format checks with zero
      errors.

## Test Requirements

- [ ] CLI test (Click `CliRunner` + mocked SessionManager): three queued
      notifications produce three lines before the next prompt (Group A #5
      scenario).
- [ ] CLI test: a notification enqueued during a mocked turn is rendered at the
      start of the next iteration, not mid-turn (Group D #2).
- [ ] CLI test: empty queue → no output line emitted (Group A #5 negative).
- [ ] CLI test: render-line shape matches DM-forge-notification §1 verbatim
      (asserted in one canonical example case).

## Implementation Notes

- The REPL uses `click.prompt`; render the notifications *immediately before*
  the prompt call to keep the output above the input cursor.
- Mock `SessionManager.pending_notifications` in CLI tests; do not require the
  full subscriber stack.
- See DDR-030 §Consequences for the SIGINT-safe drain semantics.
