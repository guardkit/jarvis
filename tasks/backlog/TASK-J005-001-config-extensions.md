---
id: TASK-J005-001
title: JarvisConfig extensions for FEAT-J005 (timeout + caps)
task_type: declarative
parent_review: TASK-REV-3B8B
feature_id: FEAT-J005-946D
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
priority: high
tags:
  - config
  - settings
  - FEAT-JARVIS-005
status: backlog
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J005-001 — JarvisConfig extensions for FEAT-J005

## Description

Extend `src/jarvis/config/settings.py` (`JarvisConfig`) with three new fields per
[design.md §7](../../../docs/design/FEAT-JARVIS-005/design.md):

- `pipeline_publish_timeout_seconds: int = 5` — DDR-025 publish timeout.
- `forge_notifications_queue_cap: int = 100` — DDR-030 per-session CLI queue cap.
- `forge_correlation_map_cap: int = 1000` — DDR-028 LRU correlation-map cap.

Declarative-only — no consumers wired in this task. TASK-J005-005 (`queue_build`),
TASK-J005-003 (subscriber), TASK-J005-008 (lifecycle) consume these fields.

## Acceptance Criteria

- [ ] Three fields added to `JarvisConfig` with defaults exactly as above.
- [ ] Field metadata includes the DDR anchor in the `description=`.
- [ ] Env-var overrides follow the FEAT-J004 convention (`JARVIS_<UPPER_SNAKE>`).
- [ ] No other module imports the new fields in this commit.
- [ ] `uv run mypy src/jarvis/config/settings.py` passes (strict mode).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Unit test: instantiate `JarvisConfig()` with defaults; assert the three new
      values match the design defaults (5, 100, 1000).
- [ ] Unit test: env-var override for one field round-trips.

## Implementation Notes

- Mirrors the FEAT-J004 settings pattern (TASK-J004-003).
- No `pyproject.toml` changes needed (`nats-py` + `graphiti-core` landed in J004).
