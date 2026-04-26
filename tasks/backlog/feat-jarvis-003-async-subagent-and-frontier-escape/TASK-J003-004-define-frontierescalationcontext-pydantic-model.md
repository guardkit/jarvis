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
  started_at: '2026-04-26T08:26:07.375088'
  last_updated: '2026-04-26T08:30:49.778674'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-26T08:26:07.375088'
    player_summary: "Created src/jarvis/tools/dispatch_types.py with three public\
      \ symbols: (1) FrontierTarget(str, Enum) with members GEMINI_3_1_PRO and OPUS_4_7\
      \ \u2014 needed as the 'target' field type and aligned with TASK-J003-002's\
      \ location requirement so a future run of that task does not collide. (2) FrontierEscalationContext(BaseModel)\
      \ \u2014 frozen via model_config = ConfigDict(frozen=True), with the six required\
      \ fields target/session_id/correlation_id/adapter/instruction_length(ge=0)/outcome\
      \ (Literal of the five cano"
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
