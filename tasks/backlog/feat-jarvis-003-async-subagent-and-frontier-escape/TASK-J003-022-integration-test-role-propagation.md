---
id: TASK-J003-022
title: "Integration test \u2014 role propagation through AsyncSubAgent preview API"
task_type: testing
status: in_review
created: 2026-04-24 00:00:00+00:00
updated: 2026-04-24 00:00:00+00:00
priority: high
complexity: 5
wave: 5
implementation_mode: task-work
estimated_minutes: 75
dependencies:
- TASK-J003-008
- TASK-J003-009
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags:
- phase-2
- jarvis
- feat-jarvis-003
- tests
- integration
- role-propagation
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-25T18:37:54.249785'
  last_updated: '2026-04-25T18:53:56.588592'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T18:37:54.249785'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
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
