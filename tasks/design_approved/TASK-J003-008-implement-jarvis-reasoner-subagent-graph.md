---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T18:21:45.166972'
  max_turns: 30
  started_at: '2026-04-25T18:04:59.371685'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T18:04:59.371685'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 6
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-001
- TASK-J003-002
- TASK-J003-005
estimated_minutes: 113
feature_id: FEAT-J003
id: TASK-J003-008
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- subagent
- ddr-010
- ddr-012
task_type: feature
title: Implement jarvis_reasoner subagent graph
updated: 2026-04-24 00:00:00+00:00
wave: 2
---

# Implement jarvis_reasoner subagent graph

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The single local AsyncSubAgent — a leaf `create_deep_agent` graph that resolves `input["role"]` against `ROLE_PROMPTS[RoleName(role)]` at its first node, then runs against `openai:jarvis-reasoner` with `OPENAI_BASE_URL=<config.llama_swap_base_url>/v1` so llama-swap routes to `gpt-oss-120b`. Compiles at module import (DDR-012). Leaf — no tools, no further subagents (DDR-010).

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/jarvis_reasoner.py` exposes a module-level `graph: CompiledStateGraph` via `create_deep_agent(model="openai:jarvis-reasoner", system_prompt=<resolved>, tools=[])`. Compilation happens at import time per DDR-012 — `from jarvis.agents.subagents.jarvis_reasoner import graph` returns a compiled object without further initialisation.
- [ ] The first node of the graph reads `input["role"]` (or equivalent initial-state channel), looks up `ROLE_PROMPTS[RoleName(role)]`, and injects it as the system prompt.
- [ ] `OPENAI_BASE_URL` environment variable is set to `<config.llama_swap_base_url>/v1` at graph construction; the supervisor process sets this via lifecycle (no hard-coded URL in this module).
- [ ] Unknown role (e.g. `"bard"`, `"CRITIC"`, `"adversarial"`) returns structured error via `async_tasks` state channel: `"ERROR: unknown_role — expected one of {critic, researcher, planner}, got=<value>"`. **Never raises.**
- [ ] Empty-string role (`""`) — `RoleName("")` raises `ValueError` at enum lookup; the graph catches and maps to the `unknown_role` branch (ASSUM-004, confirmed).
- [ ] Missing role field entirely returns structured error: `"ERROR: missing_field — role is required"`.
- [ ] Empty prompt returns structured error: `"ERROR: missing_field — prompt is required"`.
- [ ] Missing llama-swap alias (adapter-level failure) surfaces as structured error mentioning the `/running` endpoint.
- [ ] Graph exposes no tools (`tools=[]`) and no further subagents — leaf per design §8 / DDR-010.
- [ ] Module has no LLM network call at import (FakeListChatModel in tests; production model only hit on actual dispatch).
- [ ] `correlation_id` from input propagates through to the async task's output channel (scenario: *session correlation identifier propagates from input through to check-task results*).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note (Q3=D, complexity 6):** Write the structural graph-compilation test + unknown-role test + missing-field test BEFORE implementing, so they fail first.