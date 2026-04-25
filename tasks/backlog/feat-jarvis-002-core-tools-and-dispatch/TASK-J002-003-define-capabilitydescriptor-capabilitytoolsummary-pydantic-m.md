---
id: TASK-J002-003
title: Define CapabilityDescriptor + CapabilityToolSummary Pydantic models
task_type: declarative
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 40
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Listing available capabilities returns the current stub registry
- The capability catalogue is injected into the supervisor system prompt at session
  start
swap_point_note: "CapabilityDescriptor is the stable schema kept across Phase 2\u2192\
  3. No swap at this boundary."
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:18:47.024920'
  last_updated: '2026-04-25T16:25:28.684107'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:18:47.024920'
    player_summary: "Created src/jarvis/tools/capabilities.py with two Pydantic v2\
      \ models exactly per DM-tool-types \xA71: CapabilityToolSummary (tool_name min_length=1,\
      \ description min_length=1, risk_level Literal[read_only|mutating|destructive]\
      \ default 'read_only', ConfigDict(extra='ignore')) and CapabilityDescriptor\
      \ (agent_id pattern=r'^[a-z][a-z0-9-]*$', role, description, capability_list\
      \ defaulting to [], cost_signal/latency_signal default 'unknown', last_heartbeat_at:\
      \ datetime|None=None, trust_tier Literal[core|s"
    player_success: true
    coach_success: true
---
# Define CapabilityDescriptor + CapabilityToolSummary Pydantic models

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 40 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Define the Pydantic v2 models that carry capability metadata from the stub registry into the supervisor prompt and the dispatch resolver. Schema is frozen across Phase 2→3; extra='ignore' guards forward-compat with NATSKVManifestRegistry output.

## Acceptance Criteria

- [ ] `src/jarvis/tools/capabilities.py` defines `CapabilityToolSummary(BaseModel)` with fields `tool_name: str (min_length=1)`, `description: str (min_length=1)`, `risk_level: Literal["read_only","mutating","destructive"] = "read_only"` and `ConfigDict(extra="ignore")`.
- [ ] Same file defines `CapabilityDescriptor(BaseModel)` with fields `agent_id: str (pattern=r"^[a-z][a-z0-9-]*$")`, `role: str`, `description: str`, `capability_list: list[CapabilityToolSummary]`, `cost_signal: str = "unknown"`, `latency_signal: str = "unknown"`, `last_heartbeat_at: datetime | None = None`, `trust_tier: Literal["core","specialist","extension"] = "specialist"`, and `ConfigDict(extra="ignore")`.
- [ ] `CapabilityDescriptor.as_prompt_block() -> str` renders a deterministic text block whose format matches DM-tool-types.md §"Prompt-block shape" byte-for-byte.
- [ ] Module has no import of `jarvis.agents.*`, `jarvis.infrastructure.*`, or `jarvis.cli.*`.

## Scenarios Covered

- Listing available capabilities returns the current stub registry
- The capability catalogue is injected into the supervisor system prompt at session start

## Swap-Point Note

CapabilityDescriptor is the stable schema kept across Phase 2→3. No swap at this boundary.

## Test Execution Log

_Populated by `/task-work` during implementation._
