---
id: TASK-J002-007
title: Stub-response-hook contract for dispatch
task_type: scaffolding
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T16:27:06.239407'
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
- Stubbed dispatches construct real nats-core payloads before logging
- Stubbed queue_build constructs a real BuildQueuedPayload before logging
swap_point_note: Establishes the grep anchors required by DDR-009. Test TASK-J002-021
  asserts the grep-count invariant.
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:18:47.016472'
  last_updated: '2026-04-25T16:26:04.923583'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:18:47.016472'
    player_summary: 'Implemented the DDR-009 swap-point seam in src/jarvis/tools/dispatch.py.
      The file was already present from a previous checkpoint with byte-identical
      content to what this task requires; my Write produced no diff (verified via
      `git diff src/jarvis/tools/dispatch.py` which returned empty). I added a fresh
      tests/test_tools_dispatch_contract.py covering all five acceptance criteria.


      Key design decisions:

      - StubResponse is encoded as a TypeAlias union of three tagged tuples: tuple[Literal[''success''],'
    player_success: true
    coach_success: true
completed_at: '2026-04-25T16:27:06.239407'
---
# Stub-response-hook contract for dispatch

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 30 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Establish the named swap seam for dispatch. Creates the `_stub_response_hook` attribute, the StubResponse typed-dict/Literal union, and the two LOG_PREFIX constants. These are the DDR-009 grep anchors FEAT-JARVIS-004/005 will target.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py` defines a module-level attribute `_stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None`.
- [ ] Defines `StubResponse` as a typed dict / Literal union covering `("success", ResultPayload) | ("timeout",) | ("specialist_error", str)`.
- [ ] Defines module-level string constants `LOG_PREFIX_DISPATCH = "JARVIS_DISPATCH_STUB"` and `LOG_PREFIX_QUEUE_BUILD = "JARVIS_QUEUE_BUILD_STUB"`.
- [ ] Module docstring carries a "SWAP POINT" section naming the two grep anchors and stating that FEAT-JARVIS-004 replaces `_stub_response_hook` with a real NATS round-trip.
- [ ] `grep -rn "JARVIS_DISPATCH_STUB\|JARVIS_QUEUE_BUILD_STUB" src/jarvis/` returns exactly two lines (the two constant definitions) pre-feature wiring; after TASK-J002-013 and TASK-J002-014 land, it returns exactly four (two definitions + two `logger.info` usages).

## Scenarios Covered

- Stubbed dispatches construct real nats-core payloads before logging
- Stubbed queue_build constructs a real BuildQueuedPayload before logging

## Swap-Point Note

Establishes the grep anchors required by DDR-009. Test TASK-J002-021 asserts the grep-count invariant.

## Test Execution Log

_Populated by `/task-work` during implementation._
