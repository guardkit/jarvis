---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T18:53:56.588592'
  max_turns: 30
  started_at: '2026-04-25T18:37:54.249785'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T18:37:54.249785'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 5
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-008
- TASK-J003-009
estimated_minutes: 75
feature_id: FEAT-J003
id: TASK-J003-022
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- tests
- integration
- role-propagation
task_type: testing
title: Integration test — role propagation through AsyncSubAgent preview API
updated: 2026-04-24 00:00:00+00:00
wave: 5
---

# Integration test — role propagation through AsyncSubAgent preview API

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Standalone integration test per Context A concern #4 — the ASSUM-ASYNC-ROLE-PROPAGATION assumption in design.md §12. DeepAgents 0.5.3 preview API accepts extra keys in `input={}`; this test verifies the role key actually arrives at the subagent graph's first node in the initial state channel, for all three `RoleName` values, end-to-end through `start_async_task`.

## Acceptance Criteria

- [ ] `tests/test_role_propagation_e2e.py` exercises all three roles via the middleware-provided `start_async_task` tool (not direct graph invocation).
- [ ] Three parametrised cases: `role="critic"`, `role="researcher"`, `role="planner"`. For each: the test asserts the jarvis_reasoner graph's initial-state node received `role=<value>` AND that `ROLE_PROMPTS[RoleName(<value>)]` was resolved and injected as the system prompt.
- [ ] Correlation-id propagation: `input={"prompt": ..., "role": ..., "correlation_id": "abc123"}` — the test asserts `check_async_task(task_id)` returns a result carrying `correlation_id="abc123"` (scenario: *The session correlation identifier propagates from input through to check-task results*).
- [ ] Parallel safety: start two concurrent tasks with different roles (`critic` + `planner`); assert distinct task identifiers; assert each task resolved its own role prompt; assert neither overwrote the other's state (scenario: *Two different role-mode tasks can run in parallel without collision*).
- [ ] Uses `FakeListChatModel` with canned responses; zero real LLM calls.
- [ ] If DeepAgents 0.5.3 preview API breaks role-key propagation at any point, this test fails loudly — it is the ASSUM-ASYNC-ROLE-PROPAGATION regression surface (if a 0.6 breakage occurs, the fallback is inlining `role` as a leading `[role=...]` token in the prompt per design §12; this test drives that decision).
- [ ] `uv run pytest tests/test_role_propagation_e2e.py -v` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.