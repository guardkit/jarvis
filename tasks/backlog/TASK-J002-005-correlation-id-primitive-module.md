---
id: TASK-J002-005
title: Correlation-ID primitive module
task_type: feature
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 30
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Concurrent dispatch_by_capability calls produce distinct correlation ids and independent
  log lines
swap_point_note: "n/a \u2014 correlation-id primitive is unchanged across phases."
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:32:25.699486'
  last_updated: '2026-04-24T20:35:14.454004'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-24T20:32:25.699486'
    player_summary: Created src/jarvis/tools/_correlation.py as the single callsite
      for dispatch-path correlation IDs per ASSUM-001. The module imports only the
      stdlib 'uuid' (plus 'from __future__ import annotations' as a compile-time directive)
      and exposes a single function new_correlation_id() -> str returning str(uuid.uuid4()).
      The module docstring explicitly names it as the 'single callsite' for 'dispatch-path
      correlation IDs' and references ASSUM-001, and explains the concurrency-safety
      reasoning (no shared s
    player_success: true
    coach_success: true
---
# Correlation-ID primitive module

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 30 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Land the single callsite for dispatch-path correlation IDs per ASSUM-001. UUID4-based, no shared state — concurrent dispatches are isolated by construction.

## Acceptance Criteria

- [ ] `src/jarvis/tools/_correlation.py` exposes `new_correlation_id() -> str` returning `str(uuid.uuid4())`.
- [ ] Module has a single dependency: `uuid` from stdlib. No other imports.
- [ ] Unit test: 10,000 invocations produce 10,000 distinct strings; every string matches the UUID4 regex `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.
- [ ] Concurrent test: 100 threads each calling `new_correlation_id()` 100 times produce 10,000 distinct strings (no cross-contamination).
- [ ] Module docstring names this as the single callsite for dispatch-path correlation IDs per ASSUM-001.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Concurrent dispatch_by_capability calls produce distinct correlation ids and independent log lines

## Swap-Point Note

n/a — correlation-id primitive is unchanged across phases.

## Test Execution Log

_Populated by `/task-work` during implementation._
