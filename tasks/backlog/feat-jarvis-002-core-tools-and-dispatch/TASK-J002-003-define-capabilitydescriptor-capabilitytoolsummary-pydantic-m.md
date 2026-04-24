---
id: TASK-J002-003
title: "Define CapabilityDescriptor + CapabilityToolSummary Pydantic models"
task_type: declarative
status: backlog
created: 2026-04-24T06:55:00Z
updated: 2026-04-24T06:55:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 40
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags: [phase-2, jarvis, feat-jarvis-002]
scenarios_covered:
  - "Listing available capabilities returns the current stub registry"
  - "The capability catalogue is injected into the supervisor system prompt at session start"
swap_point_note: "CapabilityDescriptor is the stable schema kept across Phase 2→3. No swap at this boundary."
test_results:
  status: pending
  coverage: null
  last_run: null
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
