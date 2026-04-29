---
id: TASK-J005-011
title: Grep-invariant retire — assert LOG_PREFIX_QUEUE_BUILD absent
task_type: testing
parent_review: TASK-REV-3B8B
feature_id: FEAT-J005-946D
wave: 4
implementation_mode: direct
complexity: 2
dependencies:
  - TASK-J005-005
priority: high
tags:
  - tests
  - grep-invariant
  - phase2-retire
  - FEAT-JARVIS-005
status: backlog
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J005-011 — Grep-invariant retire

## Description

Add the symmetric grep-invariant test for the `queue_build` Phase 2 stub
anchor, mirroring TASK-J004-020's dispatch-side retire (FEAT-J004 commit log).

The Phase 2 `queue_build` stub used a constant `LOG_PREFIX_QUEUE_BUILD` and a
`logger.info(f"{LOG_PREFIX_QUEUE_BUILD} ...")` line; both are removed by
TASK-J005-005. This task adds a one-shot test that **asserts** they are
absent, so a future regression cannot silently restore the stub.

## Acceptance Criteria

- [ ] New test in `tests/test_phase2_stubs_retired.py` (or extend the FEAT-J004
      test file): asserts the literal string `LOG_PREFIX_QUEUE_BUILD` is
      absent from `src/jarvis/` source tree (excluding `tests/`).
- [ ] Test asserts the literal `"queue_build stub"` is absent from
      `src/jarvis/tools/dispatch.py`.
- [ ] Test runs in <100ms (it's a `Path.rglob` + substring check).
- [ ] Test fails with a clear message naming the offending file when the
      string is present.
- [ ] `uv run pytest tests/test_phase2_stubs_retired.py -v` passes.

## Test Requirements

- See Acceptance Criteria — this IS the test task.

## Implementation Notes

- Pattern: same as TASK-J004-020 dispatch-side retire — `Path("src/jarvis").rglob("*.py")`
  filter, `read_text()`, substring check.
- This is a *deliberate redundancy* against the standard test suite —
  TASK-J005-005's tests would catch a regression at run time, but the grep
  test catches it at static-scan time. The redundancy is the point.
