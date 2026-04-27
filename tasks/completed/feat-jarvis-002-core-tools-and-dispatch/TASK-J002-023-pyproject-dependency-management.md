---
id: TASK-J002-023
title: pyproject + dependency management
task_type: scaffolding
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T16:27:06.247640'
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
  started_at: '2026-04-25T16:18:47.023390'
  last_updated: '2026-04-25T16:27:06.195974'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:18:47.023390'
    player_summary: "Added Phase 2 runtime dependencies to [project].dependencies\
      \ in pyproject.toml: langchain-tavily>=0.2 (DDR-006 web-search provider), asteval>=0.9.33\
      \ (DDR-007 safe expression evaluator with the floor recorded in DDR-007 \xA7\
      Consequences), and nats-core>=0.2 (Pydantic payload imports for CommandPayload\
      \ / ResultPayload / BuildQueuedPayload \u2014 payloads only, no transport, per\
      \ phase2-dispatch-foundations-scope \xA7Scope Invariants \xB65). pyyaml was\
      \ already pinned at >=6.0 from Phase 1, so AC-001's 'if not alr"
    player_success: true
    coach_success: true
completed_at: '2026-04-25T16:27:06.247640'
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
