---
id: TASK-J003-004
title: Define FrontierEscalationContext Pydantic model
task_type: declarative
status: in_review
created: 2026-04-24 00:00:00+00:00
updated: 2026-04-24 00:00:00+00:00
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags:
- phase-2
- jarvis
- feat-jarvis-003
- models
- redaction
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-25T17:58:06.469024'
  last_updated: '2026-04-25T18:03:57.831444'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:58:06.469024'
    player_summary: "Extended src/jarvis/tools/dispatch_types.py (which already housed\
      \ the FrontierTarget closed enum from TASK-J003-002) by adding FrontierEscalationContext\
      \ as a frozen Pydantic model with the exact six-field shape design.md \xA78\
      \ / DM-subagent-types \xA76 prescribes: target (FrontierTarget), session_id\
      \ (str), correlation_id (str), adapter (str), instruction_length (int >= 0 via\
      \ Field(ge=0)), outcome (Literal of the five terminal outcomes). model_config\
      \ = ConfigDict(frozen=True). No instruction-body field"
    player_success: true
    coach_success: true
---

# Define FrontierEscalationContext Pydantic model

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The log-event shape FEAT-JARVIS-004's `jarvis_routing_history` ingest path will consume, per models DM-subagent-types §6 and design.md §8 "Frontier escalation contract". Redacts instruction body per ADR-ARCH-029; only records `instruction_length`.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch_types.py` (same module as FrontierTarget) exposes `class FrontierEscalationContext(BaseModel)` with fields: `target: FrontierTarget`; `session_id: str`; `correlation_id: str`; `adapter: str`; `instruction_length: int = Field(ge=0)`; `outcome: Literal["success", "config_missing", "attended_only", "provider_unavailable", "degraded_empty"]`.
- [ ] Model is frozen (`model_config = ConfigDict(frozen=True)`).
- [ ] No field for the instruction body — its presence would defeat the redaction posture; tests will assert absence.
- [ ] Module-level helper `log_frontier_escalation(ctx: FrontierEscalationContext, logger: Logger) -> None` emits one structured INFO record with `model_alias="cloud-frontier"` tag (ADR-ARCH-030 budget tracing) and all six fields — and never the body.
- [ ] No I/O at import beyond the logger reference; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
