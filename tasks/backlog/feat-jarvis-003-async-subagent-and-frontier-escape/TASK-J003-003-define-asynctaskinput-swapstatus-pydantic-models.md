---
id: TASK-J003-003
title: Define AsyncTaskInput + SwapStatus Pydantic models
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
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-26T08:26:07.381391'
  last_updated: '2026-04-26T08:32:05.109905'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-26T08:26:07.381391'
    player_summary: "Created the Phase 2 subagent input and adapter status models\
      \ per TASK-J003-003 acceptance criteria.\n\n1. `src/jarvis/agents/subagents/types.py`\
      \ exposes `AsyncTaskInput(BaseModel)` with `prompt: str = Field(min_length=1)`,\
      \ `role: str` (deliberately a plain str \u2014 not RoleName \u2014 so unknown\
      \ role values reach the subagent graph's `unknown_role` error branch per AC-001\
      \ + ASSUM-004 rather than raising at construction), and `correlation_id: str\
      \ | None = None`. The module's __all__ + docstring also accomm"
    player_success: true
    coach_success: true
---

# Define AsyncTaskInput + SwapStatus Pydantic models

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two Pydantic models from models DM-subagent-types §2 (AsyncTaskInput) and §4 (SwapStatus). AsyncTaskInput is the contract for `start_async_task(name="jarvis-reasoner", input=...)`; SwapStatus is what the LlamaSwapAdapter returns.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/types.py` (same module as RoleName) exposes `class AsyncTaskInput(BaseModel)` with fields: `prompt: str` (non-empty per Pydantic `min_length=1`); `role: str` (validated against `RoleName` at the subagent graph's first node, NOT at model construction — so unknown roles reach the `unknown_role` error branch rather than raising at input); `correlation_id: str | None = None`.
- [ ] `src/jarvis/adapters/types.py` exposes `class SwapStatus(BaseModel)` with fields: `loaded_model: str`; `eta_seconds: int = Field(ge=0)` (Pydantic enforces non-negativity — construction with `-1` raises `ValidationError`); `source: Literal["stub", "live"] = "stub"` (Phase 2 default; FEAT-JARVIS-004 will use `"live"`).
- [ ] Both models are frozen (`model_config = ConfigDict(frozen=True)`) — immutable once constructed.
- [ ] No I/O at import; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
