---
id: TASK-J002-018
title: Unit tests for tool types (types.py + capabilities.py models)
task_type: testing
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T16:59:59.784066'
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
  started_at: '2026-04-25T16:27:08.342381'
  last_updated: '2026-04-25T16:30:39.331301'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:27:08.342381'
    player_summary: "Created tests/test_tools_types.py (plural \u2014 distinct from\
      \ the pre-existing tests/test_tool_types.py) as a single suite covering both\
      \ jarvis.tools.types and jarvis.tools.capabilities per TASK-J002-018. Organised\
      \ into seven classes mirroring acceptance criteria: TestCapabilityToolSummaryValidation,\
      \ TestCapabilityDescriptorValidation (parametrised invalid agent_id pattern,\
      \ invalid trust_tier, unknown risk_level), TestAsPromptBlockByteEqual (DM-tool-types\
      \ \xA7'Prompt-block shape' byte-equal assertion),"
    player_success: true
    coach_success: true
completed_at: '2026-04-25T16:59:59.784066'
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
