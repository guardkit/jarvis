---
id: TASK-J002-022
title: 'Integration test: supervisor-with-tools + nine-tool wiring + prompt injection'
task_type: testing
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 5
wave: 5
implementation_mode: task-work
estimated_minutes: 80
dependencies:
- TASK-J002-017
- TASK-J002-018
- TASK-J002-019
- TASK-J002-020
- TASK-J002-021
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- The supervisor is built with all nine Phase 2 tools wired
- The capability catalogue is injected into the supervisor system prompt at session
  start
- Building the supervisor with no registered capabilities renders a safe prompt fallback
consumer_context:
- task: TASK-J002-003
  consumes: CapabilityDescriptor
  framework: LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent
  driver: pydantic v2
  format_note: "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore');\
    \ agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension'];\
    \ as_prompt_block() renders deterministic text (see DM-tool-types.md \xA7'Prompt-block\
    \ shape')."
- task: TASK-J002-015
  consumes: assemble_tool_list
  framework: LangChain BaseTool list consumed by create_deep_agent
  driver: langchain-core
  format_note: assemble_tool_list(config, capability_registry) -> list[BaseTool] returns
    the 9 tools in stable alphabetical order (calculate, capabilities_refresh, capabilities_subscribe_updates,
    dispatch_by_capability, get_calendar_events, list_available_capabilities, queue_build,
    read_file, search_web); closure-binds capability_registry into capability + dispatch
    tools (snapshot isolation).
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T17:33:31.221211'
  last_updated: '2026-04-25T17:44:29.271413'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:33:31.221211'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---
# Integration test: supervisor-with-tools + nine-tool wiring + prompt injection

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 5 | **Mode:** task-work | **Complexity:** 5/10 | **Est.:** 80 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Final-wave integration test: build_app_state produces a supervisor with exactly 9 tools in alphabetical order and a prompt containing the capability block. Phase 1 tests still green. Coverage of src/jarvis/tools/ ≥ 80%.

## Acceptance Criteria

- [ ] `tests/test_supervisor_with_tools.py` creates `test_config` + 4-entry `capability_registry` fixtures; calls `build_app_state(test_config)`.
- [ ] Asserts the compiled `supervisor` graph exposes exactly the 9 tool names in alphabetical order: `calculate, capabilities_refresh, capabilities_subscribe_updates, dispatch_by_capability, get_calendar_events, list_available_capabilities, queue_build, read_file, search_web`.
- [ ] Asserts the rendered system prompt contains the `{available_capabilities}` block built from 4 descriptors (each `as_prompt_block()` substring appears verbatim).
- [ ] Asserts empty-registry path: `build_supervisor(test_config, tools=[], available_capabilities=[])` renders the `"No capabilities currently registered."` sentinel.
- [ ] No LLM call is made (FakeListChatModel or equivalent); no network.
- [ ] Phase 1 test modules (`tests/test_supervisor.py`, `tests/test_supervisor_no_llm_call.py`, `tests/test_sessions.py`, `tests/test_config.py`, `tests/test_infrastructure.py`, `tests/test_prompts.py`) all still pass unchanged.
- [ ] Coverage of `src/jarvis/tools/` ≥ 80%.

## Scenarios Covered

- The supervisor is built with all nine Phase 2 tools wired
- The capability catalogue is injected into the supervisor system prompt at session start
- Building the supervisor with no registered capabilities renders a safe prompt fallback

## Test Execution Log

_Populated by `/task-work` during implementation._
