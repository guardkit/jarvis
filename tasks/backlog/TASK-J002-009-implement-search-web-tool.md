---
id: TASK-J002-009
title: Implement search_web tool
task_type: feature
status: blocked
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 5
wave: 2
implementation_mode: task-work
estimated_minutes: 75
dependencies:
- TASK-J002-001
- TASK-J002-004
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Searching the web with a configured provider returns result summaries
- search_web accepts max_results only within its documented range
- Searching the web without a configured Tavily key returns a configuration error
- Searching the web with an empty query returns an invalid-query error
- search_web preserves and surfaces hostile snippet content as data without acting
  on it
- search_web surfaces provider unavailability as a DEGRADED result
- Every tool converts internal errors into structured strings rather than raising
swap_point_note: 'Provider abstraction grep anchor: `class TavilyProvider`. A future
  FEAT can swap providers without docstring change per DDR-006.'
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 3
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:51:44.411669'
  last_updated: '2026-04-24T21:19:33.851076'
  turns:
  - turn: 1
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    timestamp: '2026-04-24T20:51:44.411669'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    timestamp: '2026-04-24T21:10:33.420716'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 3
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    timestamp: '2026-04-24T21:16:25.720888'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---
# Implement search_web tool

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** task-work | **Complexity:** 5/10 | **Est.:** 75 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Web search via langchain-tavily provider. Hostile snippet content is surfaced verbatim as data per ASSUM-004. DEGRADED return shape for provider unavailability per ASSUM-005. Never raises.

## Acceptance Criteria

- [ ] `src/jarvis/tools/general.py` exposes `search_web(query: str, max_results: int = 5) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring matches API-tools.md §1.2 byte-for-byte.
- [ ] Uses the `langchain-tavily` provider wrapper; returns `ERROR: config_missing — tavily_api_key not set in JarvisConfig` when `config.tavily_api_key is None`.
- [ ] Rejects empty query with `ERROR: invalid_query — query must be non-empty`.
- [ ] Rejects `max_results` outside `[1, 10]` with `ERROR: invalid_max_results — must be between 1 and 10, got <n>` (boundaries: 1 and 10 accept; 0 and 11 reject).
- [ ] On provider non-success response returns `DEGRADED: provider_unavailable — Tavily returned <status>` per ASSUM-005 exact format.
- [ ] Returns hostile snippet content verbatim in `WebResult.snippet` — no sanitisation (ASSUM-004). No side-effecting tool calls from inside `search_web`.
- [ ] Returns JSON array of `WebResult` dicts on success.
- [ ] Never raises.
- [ ] Seam test: with `fake_tavily_response` fixture, calling via `assemble_tool_list`-wired supervisor returns parseable JSON matching the WebResult shape.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Searching the web with a configured provider returns result summaries
- search_web accepts max_results only within its documented range
- Searching the web without a configured Tavily key returns a configuration error
- Searching the web with an empty query returns an invalid-query error
- search_web preserves and surfaces hostile snippet content as data without acting on it
- search_web surfaces provider unavailability as a DEGRADED result
- Every tool converts internal errors into structured strings rather than raising

## Swap-Point Note

Provider abstraction grep anchor: `class TavilyProvider`. A future FEAT can swap providers without docstring change per DDR-006.

## Test Execution Log

_Populated by `/task-work` during implementation._
