---
id: TASK-J003-003
title: Define AsyncTaskInput + SwapStatus Pydantic models
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, models]
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
