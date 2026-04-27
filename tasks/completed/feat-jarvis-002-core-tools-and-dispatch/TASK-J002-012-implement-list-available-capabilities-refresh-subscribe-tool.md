---
id: TASK-J002-012
title: Implement list_available_capabilities + refresh + subscribe tools
task_type: feature
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T17:14:15.601528'
priority: high
complexity: 3
wave: 2
implementation_mode: task-work
estimated_minutes: 50
dependencies:
- TASK-J002-003
- TASK-J002-006
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Listing available capabilities returns the current stub registry
- capabilities_refresh and capabilities_subscribe_updates return OK acknowledgements
  in Phase 2
- list_available_capabilities returns a stable snapshot even when refresh is called
  concurrently
- Every tool converts internal errors into structured strings rather than raising
consumer_context:
- task: TASK-J002-003
  consumes: CapabilityDescriptor
  framework: LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent
  driver: pydantic v2
  format_note: "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore');\
    \ agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension'];\
    \ as_prompt_block() renders deterministic text (see DM-tool-types.md \xA7'Prompt-block\
    \ shape')."
swap_point_note: "`capabilities_refresh` and `capabilities_subscribe_updates` bodies\
  \ are the Phase 2\u21923 swap targets. Grep anchor: `stubbed in Phase 2` inside\
  \ capabilities.py."
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T17:00:01.852489'
  last_updated: '2026-04-25T17:14:07.338105'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:00:01.852489'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
completed_at: '2026-04-25T17:14:15.601528'
---
# Implement list_available_capabilities + refresh + subscribe tools

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** task-work | **Complexity:** 3/10 | **Est.:** 50 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Three @tool functions over the closed-over capability registry snapshot. list_available_capabilities returns a JSON-serialised COPY (snapshot isolation per ASSUM-006). refresh and subscribe are Phase-2 no-ops returning exact OK strings — their bodies are the Phase-2→3 swap targets.

## Acceptance Criteria

- [ ] `src/jarvis/tools/capabilities.py` exposes three `@tool(parse_docstring=True)` functions: `list_available_capabilities() -> str`, `capabilities_refresh() -> str`, `capabilities_subscribe_updates() -> str`.
- [ ] Docstrings match API-tools.md §2.1–2.3 byte-for-byte.
- [ ] `list_available_capabilities` returns JSON-serialised copy of the registry list captured at `assemble_tool_list` time. Snapshot isolation invariant (ASSUM-006): the closed-over list is NOT mutated; a subsequent `capabilities_refresh` does not affect an in-flight call.
- [ ] `capabilities_refresh` returns the exact string `"OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)"`.
- [ ] `capabilities_subscribe_updates` returns the exact string `"OK: subscribed (stubbed in Phase 2 — no live updates)"`.
- [ ] All three never raise; internal errors wrapped as `ERROR: registry_unavailable — <detail>`.
- [ ] Concurrent test: issuing `list_available_capabilities()` and `capabilities_refresh()` in parallel returns the startup snapshot from the former and the OK string from the latter with no mutation of the snapshot between call start and return.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Listing available capabilities returns the current stub registry
- capabilities_refresh and capabilities_subscribe_updates return OK acknowledgements in Phase 2
- list_available_capabilities returns a stable snapshot even when refresh is called concurrently
- Every tool converts internal errors into structured strings rather than raising

## Swap-Point Note

`capabilities_refresh` and `capabilities_subscribe_updates` bodies are the Phase 2→3 swap targets. Grep anchor: `stubbed in Phase 2` inside capabilities.py.

## Test Execution Log

_Populated by `/task-work` during implementation._
