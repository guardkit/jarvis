---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T18:35:51.934903'
  max_turns: 30
  started_at: '2026-04-25T18:21:47.096618'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T18:21:47.096618'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 4
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-008
estimated_minutes: 50
feature_id: FEAT-J003
id: TASK-J003-009
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- registry
- ddr-010
task_type: feature
title: Implement subagent_registry.build_async_subagents
updated: 2026-04-24 00:00:00+00:00
wave: 2
---

# Implement subagent_registry.build_async_subagents

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The single-element list of AsyncSubAgent entries the supervisor wires via `async_subagents=`. **Description text is the routing contract** per DDR-010 — cost + latency signals must be readable by the reasoning model. No four-roster names; no cloud-tier promises.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagent_registry.py` exposes `build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]`.
- [ ] Returns a list of **exactly one** element.
- [ ] The element satisfies: `name == "jarvis-reasoner"`; `graph_id == "jarvis_reasoner"`; `description` is non-empty.
- [ ] Description must contain ALL of the following substrings (routing signals): `gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`.
- [ ] Description must NOT contain any of: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`, cloud-tier promises — asserted by TASK-J003-020 regression test (Context A concern #3).
- [ ] `AsyncSubAgent` is imported from `deepagents` (0.5.3 TypedDict); no redefinition.
- [ ] Function is pure — given the same config, returns the same description text (deterministic for Graphiti trace-richness).
- [ ] `src/jarvis/agents/subagents/__init__.py` re-exports the `jarvis_reasoner.graph` symbol so `langgraph.json` can bind `jarvis_reasoner` by module path.
- [ ] No LLM calls; no I/O beyond reading config.
- [ ] All modified files pass project-configured lint/format checks with zero errors.