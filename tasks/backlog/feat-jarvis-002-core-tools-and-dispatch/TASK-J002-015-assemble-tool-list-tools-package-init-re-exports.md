---
id: TASK-J002-015
title: assemble_tool_list + tools package __init__ re-exports
task_type: scaffolding
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 3
wave: 3
implementation_mode: direct
estimated_minutes: 40
dependencies:
- TASK-J002-008
- TASK-J002-009
- TASK-J002-010
- TASK-J002-011
- TASK-J002-012
- TASK-J002-013
- TASK-J002-014
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- The supervisor is built with all nine Phase 2 tools wired
consumer_context:
- task: TASK-J002-003
  consumes: CapabilityDescriptor
  framework: LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent
  driver: pydantic v2
  format_note: "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore');\
    \ agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension'];\
    \ as_prompt_block() renders deterministic text (see DM-tool-types.md \xA7'Prompt-block\
    \ shape')."
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T17:14:17.526772'
  last_updated: '2026-04-25T17:20:52.217315'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:14:17.526772'
    player_summary: "Populated src/jarvis/tools/__init__.py to expose the 15-symbol\
      \ public surface listed in API-internal.md \xA71.1 (4 Pydantic types + 4 general\
      \ tools + 3 capability catalogue tools + 2 dispatch tools + assemble_tool_list\
      \ + load_stub_registry). The new assemble_tool_list(config, capability_registry)\
      \ factory is the single wiring point: it (a) calls jarvis.tools.general.configure(config)\
      \ so search_web can resolve the active JarvisConfig, (b) snapshot-copies the\
      \ registry into capabilities._capability_reg"
    player_success: true
    coach_success: true
---
# assemble_tool_list + tools package __init__ re-exports

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 3 | **Mode:** direct | **Complexity:** 3/10 | **Est.:** 40 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Wire the 9 tools into one assemble_tool_list(config, capability_registry) function. Returns tools in stable alphabetical order. Closure-binds the capability registry into capability + dispatch tools — this is where snapshot isolation is enforced. tools/__init__.py re-exports the public surface.

## Acceptance Criteria

- [ ] `src/jarvis/tools/__init__.py` re-exports exactly the public surface listed in API-internal.md §1.1 (11 symbols plus `assemble_tool_list` and `load_stub_registry`).
- [ ] `src/jarvis/tools/__init__.py` exposes `assemble_tool_list(config: JarvisConfig, capability_registry: list[CapabilityDescriptor]) -> list[BaseTool]`.
- [ ] `assemble_tool_list` returns the 9 tools in stable alphabetical order: `calculate, capabilities_refresh, capabilities_subscribe_updates, dispatch_by_capability, get_calendar_events, list_available_capabilities, queue_build, read_file, search_web`.
- [ ] `assemble_tool_list` is the **only** place that binds capability_registry into the capability + dispatch tools via closure (snapshot isolation).
- [ ] No other module imports `jarvis.tools.general`, `jarvis.tools.capabilities`, `jarvis.tools.dispatch` directly — only `jarvis.tools`.

## Scenarios Covered

- The supervisor is built with all nine Phase 2 tools wired

## Test Execution Log

_Populated by `/task-work` during implementation._
