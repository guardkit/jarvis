---
id: TASK-J002-011
title: Implement calculate tool
task_type: feature
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T16:59:59.748718'
priority: high
complexity: 4
wave: 2
implementation_mode: task-work
estimated_minutes: 60
dependencies:
- TASK-J002-004
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Evaluating a supported arithmetic expression returns a numeric result
- Calculating an expression that divides by zero returns a structured error
- Calculating an expression that exceeds the float range returns an overflow error
- Calculator rejects expressions containing unsafe tokens
- Every tool converts internal errors into structured strings rather than raising
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:27:08.331810'
  last_updated: '2026-04-25T16:47:29.661089'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:27:08.331810'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
completed_at: '2026-04-25T16:59:59.748718'
---
# Implement calculate tool

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** task-work | **Complexity:** 4/10 | **Est.:** 60 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Safe arithmetic via asteval.Interpreter per DDR-007. Rejects unsafe tokens (__import__, open, lambda, def). Handles percentage shorthand. Never raises.

## Acceptance Criteria

- [ ] `src/jarvis/tools/general.py` exposes `calculate(expression: str) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring matches API-tools.md §1.4 byte-for-byte.
- [ ] Uses `asteval.Interpreter` (DDR-007); disables `__import__`, `open`, `lambda`, function definitions.
- [ ] Supports operators `+ - * / ** %` + parentheses; functions `sqrt log exp sin cos tan abs min max round`.
- [ ] Rejects `__import__('os').getcwd`, `open('/etc/passwd')`, `lambda x: x` with `ERROR: unsafe_expression — disallowed token: <token>`.
- [ ] Returns `ERROR: division_by_zero` for `1/0`-shaped inputs.
- [ ] Returns `ERROR: overflow — result exceeds float range` for overflow (e.g. `10.0 ** 500`).
- [ ] Returns `ERROR: parse_error — <detail>` for syntactically malformed input.
- [ ] Handles `"15% of 847"` by preprocessing `X% of Y` → `X/100 * Y`; returns the numeric result as a string.
- [ ] Never raises; all asteval internal errors are trapped and converted.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Evaluating a supported arithmetic expression returns a numeric result
- Calculating an expression that divides by zero returns a structured error
- Calculating an expression that exceeds the float range returns an overflow error
- Calculator rejects expressions containing unsafe tokens
- Every tool converts internal errors into structured strings rather than raising

## Test Execution Log

_Populated by `/task-work` during implementation._
