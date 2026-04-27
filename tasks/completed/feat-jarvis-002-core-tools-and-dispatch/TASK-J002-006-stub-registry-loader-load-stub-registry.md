---
id: TASK-J002-006
title: Stub registry loader (load_stub_registry)
task_type: feature
status: completed
created: 2026-04-24 06:55:00+00:00
updated: '2026-04-25T16:59:59.713467'
priority: high
complexity: 3
wave: 2
implementation_mode: direct
estimated_minutes: 45
dependencies:
- TASK-J002-003
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Starting Jarvis with a missing stub capabilities file fails fast at startup
- Starting Jarvis with a malformed stub capabilities file fails fast at startup
consumer_context:
- task: TASK-J002-003
  consumes: CapabilityDescriptor
  framework: LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent
  driver: pydantic v2
  format_note: "CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore');\
    \ agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension'];\
    \ as_prompt_block() renders deterministic text (see DM-tool-types.md \xA7'Prompt-block\
    \ shape')."
swap_point_note: 'DELETED in FEAT-JARVIS-004. Grep anchor: `load_stub_registry`.'
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:27:08.343246'
  last_updated: '2026-04-25T16:30:49.419398'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:27:08.343246'
    player_summary: "Added load_stub_registry(path: Path) -> list[CapabilityDescriptor]\
      \ to src/jarvis/tools/capabilities.py and exported it from __all__. The loader:\
      \ (1) raises FileNotFoundError with the path in the message when path.exists()\
      \ is False (startup-fatal per design \xA77); (2) opens the file with utf-8 encoding\
      \ and parses with yaml.safe_load (the only YAML call in the file \u2014 verified\
      \ by a static grep test); (3) validates the document root is a mapping with\
      \ a list-valued 'capabilities' key, raising ValueErro"
    player_success: true
    coach_success: true
completed_at: '2026-04-25T16:59:59.713467'
---
# Stub registry loader (load_stub_registry)

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** direct | **Complexity:** 3/10 | **Est.:** 45 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Load stub_capabilities.yaml into a validated list[CapabilityDescriptor]. Startup-fatal on missing or malformed YAML per design §7.

## Acceptance Criteria

- [ ] `src/jarvis/tools/capabilities.py` adds `load_stub_registry(path: Path) -> list[CapabilityDescriptor]`.
- [ ] Loads YAML at `path`; validates every entry against `CapabilityDescriptor`; returns list preserving YAML order.
- [ ] Raises `FileNotFoundError` if `path` does not exist (startup-fatal per design §7).
- [ ] Raises `pydantic.ValidationError` if any descriptor is malformed (e.g. uppercase `agent_id`).
- [ ] Rejects duplicate `agent_id` entries with a ValueError mentioning the duplicated id.
- [ ] Uses `yaml.safe_load` (never `yaml.load`).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Starting Jarvis with a missing stub capabilities file fails fast at startup
- Starting Jarvis with a malformed stub capabilities file fails fast at startup

## Swap-Point Note

DELETED in FEAT-JARVIS-004. Grep anchor: `load_stub_registry`.

## Test Execution Log

_Populated by `/task-work` during implementation._
