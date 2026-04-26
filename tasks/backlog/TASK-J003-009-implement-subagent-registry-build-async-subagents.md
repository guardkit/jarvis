---
id: TASK-J003-009
title: Implement subagent_registry.build_async_subagents
task_type: feature
status: in_review
created: 2026-04-24 00:00:00+00:00
updated: 2026-04-24 00:00:00+00:00
priority: high
complexity: 4
wave: 2
implementation_mode: task-work
estimated_minutes: 50
dependencies:
- TASK-J003-008
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags:
- phase-2
- jarvis
- feat-jarvis-003
- registry
- ddr-010
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-25T18:21:47.096618'
  last_updated: '2026-04-25T18:35:51.934903'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T18:21:47.096618'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
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
