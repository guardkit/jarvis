---
id: TASK-J002-006
title: Stub registry loader (load_stub_registry)
task_type: feature
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
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
  started_at: '2026-04-24T20:51:44.457211'
  last_updated: '2026-04-24T20:56:11.176862'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-24T20:51:44.457211'
    player_summary: "Added load_stub_registry(path: Path) -> list[CapabilityDescriptor]\
      \ to src/jarvis/tools/capabilities.py. The loader: (1) checks path.exists()\
      \ and raises FileNotFoundError with a message mentioning the missing path if\
      \ not present (AC-003, startup-fatal per design \xA77); (2) reads the file text\
      \ and calls yaml.safe_load \u2014 never yaml.load (AC-006); (3) accepts both\
      \ the canonical root-mapping shape ({version, capabilities: [...]}) and a bare\
      \ top-level list for operator-pasted fixtures; (4) validates eac"
    player_success: true
    coach_success: true
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
