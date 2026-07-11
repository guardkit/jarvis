---
id: TASK-J004-020
title: Retire Phase 2 stubs + update FEAT-J003 routing-e2e for real-NATS path
task_type: refactor
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 5
implementation_mode: direct
complexity: 3
dependencies:
- TASK-J004-015
priority: high
tags:
- refactor
- retire-stubs
- regression
- FEAT-JARVIS-004
status: completed
created: 2026-04-27 15:30:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J004-702C
  base_branch: main
  started_at: '2026-04-28T13:34:25.402845'
  last_updated: '2026-04-28T13:53:18.602779'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-28T13:34:25.402845'
    player_summary: "TASK-J004-020 has two coupled cleanup actions; both landed as\
      \ small, surgical edits.\n\nA. Phase 2 stub-anchor retirement gate.\n  1. Cleaned\
      \ three retirement-explanation docstrings in src/jarvis/tools/dispatch.py that\
      \ still literally named the retired symbols (LOG_PREFIX_DISPATCH, _stub_response_hook,\
      \ JARVIS_DISPATCH_STUB) \u2014 replaced with neutral descriptive text so a strict\
      \ substring search finds zero matches in src/jarvis/. Removed the stale `DEGRADED:\
      \ transport_stub` line from queue_build's doc"
    player_success: true
    coach_success: true
---

# TASK-J004-020 — Retire Phase 2 stubs + update routing-e2e for real-NATS path

## Description

Two coupled cleanup actions that close the Phase 2 → Phase 3 transition:

**A. Retire `LOG_PREFIX_DISPATCH` / `_stub_response_hook` grep invariant**

The Phase 2 task TASK-J002-021 added a grep test that asserts the
presence of `LOG_PREFIX_DISPATCH = "JARVIS_DISPATCH_STUB"` in
`src/jarvis/tools/dispatch.py` (the swap-point anchor). FEAT-J004
deletes that constant (TASK-J004-011). This task **flips the
invariant**: assert the constant is **NOT** present anywhere in
`src/jarvis/`.

The flipped test goes in the existing `tests/test_no_retired_roster_strings.py`
(already used for FEAT-J003 retired-roster strings) — extend that
module with a `test_no_phase_2_stub_anchors` test covering:

- `LOG_PREFIX_DISPATCH` literal must not appear in `src/jarvis/`.
- `_stub_response_hook` literal must not appear in `src/jarvis/`.
- `JARVIS_DISPATCH_STUB` log-prefix string must not appear in
  `src/jarvis/`.
- `transport_stub` (the retired DEGRADED string) must not appear in
  `src/jarvis/tools/`.

**B. Update `tests/test_routing_e2e.py` for the real-NATS path**

The FEAT-J003 acceptance test routes 7 canned prompts through the
supervisor and asserts tool-call sequences. Two of those prompts
(dispatch + queue-build) hit the dispatch tool. Pre-FEAT-J004 they
exercise the stub path; post-FEAT-J004 they must exercise the real-NATS
path with a mocked specialist consumer.

Updates needed:

- Add an in-process NATS server fixture (use the one from TASK-J004-014).
- Mock specialist consumers for the two dispatch prompts.
- Assert tool-call sequences are **identical** to FEAT-J003 (the
  reasoning model behaviour must not change; only the transport
  swapped).
- The `queue_build` prompt continues to exercise the stubbed
  publish (FEAT-J005 territory) — assert the Phase 2 ack shape still
  returns.

## Acceptance Criteria

- [ ] `tests/test_no_retired_roster_strings.py` extended with `test_no_phase_2_stub_anchors`; all 4 retired strings asserted absent from `src/jarvis/`.
- [ ] Test fails (descriptively, naming the file + line) if any retired anchor reappears.
- [ ] `tests/test_routing_e2e.py` updated to use the in-process NATS fixture for the dispatch prompt; mocked specialist replies success.
- [ ] All 7 prompts pass with the same expected tool-call sequence as FEAT-J003.
- [ ] `uv run pytest tests/test_no_retired_roster_strings.py tests/test_routing_e2e.py -v` green.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Tests run on the same in-process NATS server fixture as TASK-J004-014 / TASK-J004-015 (no GB10 dependency).
- [ ] No new test files — extend the existing module per project convention.

## Implementation Notes

This task is the cleanup gate that confirms Phase 2's swap-point
anchors are gone. If TASK-J004-011's body-swap missed deleting any of
the four anchors, this test catches it.

The routing-e2e update is small — one fixture insertion and two
specialist mocks. The 7-prompt sequence assertions stay byte-identical.

## Test Execution Log

(Populated by /task-work.)

> **[WS3-S8 tracker sweep 2026-07-11]** status reconciled to `completed` - FEAT-J004-702C rollup (feature yaml status=completed, all 20 tasks per-task completed; b467939).
