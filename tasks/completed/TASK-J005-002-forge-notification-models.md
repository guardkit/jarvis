---
id: TASK-J005-002
title: ForgeNotification + BuildCorrelation Pydantic models (declarative-only)
task_type: declarative
parent_review: TASK-REV-3B8B
feature_id: FEAT-J005-946D
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
priority: high
tags:
  - pydantic
  - schema
  - forge-notifications
  - FEAT-JARVIS-005
status: completed
created: 2026-04-29T00:00:00Z
updated: 2026-04-30T11:10:33Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J005-002 — ForgeNotification + BuildCorrelation Pydantic models

## Description

Land **schema-only** for two Pydantic v2 frozen models in
`src/jarvis/infrastructure/forge_notifications.py`, per
[DM-forge-notification.md](../../../docs/design/FEAT-JARVIS-005/models/DM-forge-notification.md):

- `ForgeNotification` (`frozen=True`, `extra="ignore"`) — in-process envelope routed
  from `pipeline.stage-complete.>` to the CLI. Fields: `correlation_id`,
  `feature_id`, `stage_label`, `status`, `timestamp`, plus a `render_line()`
  helper that emits the canonical
  `[HH:MM] Forge {feature_id}: stage {stage_label} ({status})` shape (DDR-030).
- `BuildCorrelation` (`frozen=True`, `extra="ignore"`) — one entry of the in-memory
  correlation map: `correlation_id`, `session_id`, `adapter`, `queued_at`,
  `feature_id`.

This task does **not** ship the subscriber, the correlation-map, or any I/O — that
lands in TASK-J005-003. Splitting schema-from-behaviour mirrors FEAT-J004's
TASK-J004-004 / TASK-J004-010 pattern; lets TASK-J005-003 focus on transport.

## Acceptance Criteria

- [ ] `src/jarvis/infrastructure/forge_notifications.py` exports `ForgeNotification`
      and `BuildCorrelation` via explicit `__all__`.
- [ ] Both models declare `model_config = ConfigDict(extra="ignore", frozen=True)`.
- [ ] `ForgeNotification.render_line()` produces the canonical CLI shape per
      DM-forge-notification §1, with `timestamp` rendered as `HH:MM` local time.
- [ ] All Field validators / regex / max_length match DM-forge-notification verbatim.
- [ ] No subscriber, no NATS imports, no `js.subscribe` call in this file yet.
- [ ] `uv run mypy src/jarvis/infrastructure/forge_notifications.py` passes (strict).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Unit test: instantiate `ForgeNotification` with valid data; assert
      `render_line()` shape matches DM-forge-notification §1.
- [ ] Unit test: `frozen=True` enforced — assigning to a field raises
      `ValidationError`.
- [ ] Unit test: `BuildCorrelation` round-trips via `model_dump_json()`.

## Implementation Notes

- See DM-forge-notification.md for exact field types, defaults, and the render-helper
  spec.
- Use `datetime.datetime` (timezone-aware) for `timestamp`; render `HH:MM` via
  `strftime("%H:%M")`.
