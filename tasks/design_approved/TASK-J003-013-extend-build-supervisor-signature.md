---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T19:10:05.889730'
  max_turns: 30
  started_at: '2026-04-25T18:54:34.701008'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T18:54:34.701008'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 4
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-009
- TASK-J003-012
estimated_minutes: 50
feature_id: FEAT-J003
id: TASK-J003-013
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- wiring
- supervisor
task_type: feature
title: Extend build_supervisor signature (async_subagents + ambient_tool_factory)
updated: 2026-04-24 00:00:00+00:00
wave: 3
---

# Extend build_supervisor signature (async_subagents + ambient_tool_factory)

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two new keyword-only args with safe defaults (design.md §8). Phase 1 + FEAT-J002 call sites that omit them must still work unchanged — scenario: *Building the supervisor without async subagents preserves existing behaviour*.

## Acceptance Criteria

- [ ] `src/jarvis/agents/supervisor.py` — `build_supervisor` adds two keyword-only parameters:
  ```python
  async_subagents: list[AsyncSubAgent] | None = None,
  ambient_tool_factory: Callable[[], list[BaseTool]] | None = None,
  ```
- [ ] When `async_subagents=None`: no async subagents wired; the supervisor's tool catalogue does **not** include the five `AsyncSubAgentMiddleware` operational tools (scenario: *Building the supervisor without the async-subagents argument preserves existing behaviour*).
- [ ] When `async_subagents=[<jarvis-reasoner>]`: `AsyncSubAgentMiddleware` auto-injects `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` into the supervisor's tool catalogue (scenario: *Wiring the async subagent injects the five middleware operational tools*).
- [ ] When `ambient_tool_factory=None`: ambient/learning paths fall back to `assemble_tool_list(..., include_frontier=False)` — the attended tool list minus `escalate_to_frontier` (scenario: *Not configuring an ambient tool factory falls back to the attended tools without frontier*).
- [ ] When `ambient_tool_factory` is supplied: the factory's return value is the canonical ambient tool list.
- [ ] Phase 1 + FEAT-J002 call sites that supply only `tools=` and `available_capabilities=` still return a valid `CompiledStateGraph` (backward compat).
- [ ] Signature is documented in docstring; parameter order preserves existing ordering (kwargs-only additions).
- [ ] All modified files pass project-configured lint/format checks with zero errors.