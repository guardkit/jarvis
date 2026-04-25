---
id: TASK-J002-023
title: pyproject + dependency management
task_type: scaffolding
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 25
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered: []
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:32:25.705973'
  last_updated: '2026-04-24T20:36:20.477046'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-24T20:32:25.705973'
    player_summary: "Added four Phase 2 runtime dependencies to [project].dependencies\
      \ in pyproject.toml:\n\n  1. langchain-tavily>=0.2 \u2014 ADR-DDR-006 pins Tavily\
      \ as the v1 provider behind search_web.\n  2. asteval>=0.9.33 \u2014 ADR-DDR-007\
      \ pins asteval as the safe arithmetic evaluator for calculate.\n  3. nats-core>=0.0.0\
      \ \u2014 ships the Pydantic payload schemas imported by the capability-dispatch\
      \ tools.\n  4. pyyaml \u2014 already declared at pyyaml>=6.0 from Phase 1, left\
      \ untouched per AC-004 (no change needed).\n\nInline comments on"
    player_success: true
    coach_success: true
---
# pyproject + dependency management

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 25 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Add Phase-2 runtime dependencies (langchain-tavily, asteval, nats-core, pyyaml). Deliberately DOES NOT add nats-py — Phase 2 scope invariant forbids a live NATS client. Phase 1 dependencies are untouched.

## Acceptance Criteria

- [ ] `pyproject.toml` adds `langchain-tavily` (or the ADR-DDR-006-pinned equivalent), `asteval`, `nats-core` (for Pydantic payload imports), `pyyaml` if not already present.
- [ ] `nats-py` (the NATS client library) is NOT added — Phase 2 scope invariant.
- [ ] `uv lock` is regenerated; `uv sync` completes clean.
- [ ] Phase 1 dependencies are untouched.

## Scenarios Covered

_No direct scenario coverage — supporting task._

## Test Execution Log

_Populated by `/task-work` during implementation._
