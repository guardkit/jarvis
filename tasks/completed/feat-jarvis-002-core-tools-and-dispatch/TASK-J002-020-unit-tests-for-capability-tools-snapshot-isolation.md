---
id: TASK-J002-020
title: Unit tests for capability tools + snapshot isolation
task_type: testing
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T17:20:52.231163'
priority: high
complexity: 4
wave: 4
implementation_mode: direct
estimated_minutes: 70
dependencies:
- TASK-J002-006
- TASK-J002-012
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Listing available capabilities returns the current stub registry
- Starting Jarvis with a missing stub capabilities file fails fast at startup
- Starting Jarvis with a malformed stub capabilities file fails fast at startup
- capabilities_refresh and capabilities_subscribe_updates return OK acknowledgements
  in Phase 2
- list_available_capabilities returns a stable snapshot even when refresh is called
  concurrently
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
  started_at: '2026-04-25T17:14:17.526358'
  last_updated: '2026-04-25T17:17:10.028465'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:14:17.526358'
    player_summary: "Created tests/test_tools_capabilities.py \u2014 a focused, self-contained\
      \ pytest suite covering the AC-001/002/003 scenarios from TASK-J002-020. The\
      \ file exercises load_stub_registry against the canonical Phase 2 stub YAML\
      \ (4 descriptors, agent_ids architect-agent/product-owner-agent/ideation-agent/forge),\
      \ the three @tool functions (list_available_capabilities, capabilities_refresh,\
      \ capabilities_subscribe_updates), startup-fatal failures on missing/malformed\
      \ YAML, duplicate-agent_id rejection, and sn"
    player_success: true
    coach_success: true
completed_at: '2026-04-25T17:20:52.231163'
---
# Unit tests for capability tools + snapshot isolation

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 4 | **Mode:** direct | **Complexity:** 4/10 | **Est.:** 70 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

pytest suite covering the stub registry loader and the three capability @tools, including the ASSUM-006 snapshot-isolation concurrency test.

## Acceptance Criteria

- [ ] `tests/test_tools_capabilities.py` covers: stub YAML loads into 4 descriptors; `list_available_capabilities` returns JSON of 4 descriptors; refresh/subscribe OK acks; startup-fatal on missing YAML; startup-fatal on malformed YAML (invalid agent_id uppercase); snapshot isolation (concurrent `list_available_capabilities` + `capabilities_refresh` via `concurrent.futures` — both succeed, snapshot unchanged).
- [ ] Byte-equal check on the `OK:` strings from refresh and subscribe.
- [ ] Duplicate-agent_id YAML is rejected by loader.

## Scenarios Covered

- Listing available capabilities returns the current stub registry
- Starting Jarvis with a missing stub capabilities file fails fast at startup
- Starting Jarvis with a malformed stub capabilities file fails fast at startup
- capabilities_refresh and capabilities_subscribe_updates return OK acknowledgements in Phase 2
- list_available_capabilities returns a stable snapshot even when refresh is called concurrently

## Test Execution Log

_Populated by `/task-work` during implementation._
