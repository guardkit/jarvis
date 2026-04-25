---
id: TASK-J002-018
title: Unit tests for tool types (types.py + capabilities.py models)
task_type: testing
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 3
wave: 4
implementation_mode: direct
estimated_minutes: 45
dependencies:
- TASK-J002-003
- TASK-J002-004
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Listing available capabilities returns the current stub registry
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
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:51:44.413223'
  last_updated: '2026-04-24T20:55:02.923945'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-24T20:51:44.413223'
    player_summary: Extended tests/test_tools_types.py so a single file covers Pydantic
      validation for both jarvis.tools.types (WebResult, CalendarEvent, DispatchError)
      and jarvis.tools.capabilities (CapabilityToolSummary, CapabilityDescriptor).
      Added three new test classes (TestJ002_018_CapabilityToolSummary, TestJ002_018_CapabilityDescriptor,
      TestJ002_018_AsPromptBlock) plus TestJ002_018_UnittestMockUsage to satisfy AC-003's
      unittest.mock requirement. The byte-equal EXPECTED_ARCHITECT_BLOCK constant
      reproduces do
    player_success: true
    coach_success: true
---
# Unit tests for tool types (types.py + capabilities.py models)

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 4 | **Mode:** direct | **Complexity:** 3/10 | **Est.:** 45 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

pytest suite exercising Pydantic validation on every model in types.py and capabilities.py, including the as_prompt_block byte-equal assertion.

## Acceptance Criteria

- [ ] `tests/test_tools_types.py` added with at least 12 tests covering Pydantic validation for CapabilityDescriptor (valid + invalid agent_id pattern + unknown risk_level), CapabilityToolSummary, WebResult (score bounds), CalendarEvent (end>=start validator), DispatchError (category literal).
- [ ] `as_prompt_block` byte-equal assertion against DM-tool-types.md §"Prompt-block shape" example.
- [ ] All tests use `pytest` + `unittest.mock` per .claude/CLAUDE.md rules.
- [ ] No tests require network or filesystem beyond `tmp_path`.

## Scenarios Covered

- Listing available capabilities returns the current stub registry
- Building the supervisor with no registered capabilities renders a safe prompt fallback

## Test Execution Log

_Populated by `/task-work` during implementation._
