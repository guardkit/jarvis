---
id: TASK-J001-FIX-004
title: Cosmetic polish — correlation_id docstring, HumanMessage hoist, ruff-fix tests/
task_type: chore
parent_review: TASK-REV-J001
review_report: .claude/reviews/FEAT-JARVIS-001-review-report.md
feature_id: FEAT-JARVIS-001
wave: 2
implementation_mode: direct
complexity: 2
estimated_minutes: 15
dependencies:
- TASK-J001-FIX-001
status: completed
completed: 2026-04-22
completed_location: tasks/completed/TASK-J001-FIX-004/
organized_files:
- TASK-J001-FIX-004.md
tags:
- review-fix
- cosmetic
- lint
conductor_workspace: phase1-review-fixes-wave2-2
---

# Task: Cosmetic polish from review findings F5 / F6 / F8

Three unrelated low-severity findings, batched because each is a one-touch edit. No behaviour changes, no architectural impact.

## Context

Post-build review [FEAT-JARVIS-001-review-report.md §F5 / §F6 / §F8](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md).

## Scope

### Part A — `correlation_id` docstring drift (F5)

[src/jarvis/sessions/session.py:29](../../../src/jarvis/sessions/session.py#L29) docstring says "ULID reserved for FEAT-004 trace-richness (ADR-ARCH-020)" but [src/jarvis/sessions/manager.py:79](../../../src/jarvis/sessions/manager.py#L79) sets it via `uuid.uuid4().hex`. Pick the lower-cost option:

- Update the docstring to: "Hex-encoded UUID4 placeholder; will migrate to ULID when FEAT-004 wires the trace-richness pipeline (ADR-ARCH-020)."

Do **not** introduce a ULID library in this task — FEAT-004 owns that decision.

### Part B — Hoist `HumanMessage` import (F8)

[src/jarvis/sessions/manager.py:166](../../../src/jarvis/sessions/manager.py#L166): `from langchain_core.messages import HumanMessage` is inside `async def invoke`. Hoist to the top of the module alongside the other runtime imports. `langchain_core` is already a declared runtime dependency; there is no cycle to break.

### Part C — Ruff clean on `tests/` (F6)

`uv run ruff check tests/` currently reports 7 errors:

- 4 auto-fixable (`F401` unused imports + `I001` unsorted imports): run `uv run ruff check tests/ --fix`.
- 3 `RUF012` mutable class attrs in `tests/test_build_system.py`, `tests/test_import_graph.py`, `tests/test_supervisor_no_llm_call.py` — annotate the three lists with `typing.ClassVar[list[str]]`. Do not convert them to frozensets or change their contents.

Goal: `uv run ruff check src/jarvis/ tests/` passes cleanly.

## Out of Scope

- Adopting a ULID library or modifying `correlation_id` generation.
- Any mypy fix in tests/ (tests are outside Success Criterion #6 scope; do not add tests/ to the strict mypy target).
- Any behaviour change anywhere.

## Acceptance Criteria

- `uv run ruff check src/jarvis/ tests/` → "All checks passed!".
- `grep -n "ULID reserved" src/jarvis/sessions/session.py` → no matches; docstring now names UUID4 as the placeholder.
- `grep -n "^from langchain_core" src/jarvis/sessions/manager.py` — import appears at module top; no `from langchain_core…` remains inside a function body.
- `uv run pytest tests/` pass count unchanged from post-FIX-002 baseline (341).
- `uv run mypy src/jarvis/` remains clean.

## Coach Validation

- Diff must be confined to:
  - `src/jarvis/sessions/session.py` (1 docstring line)
  - `src/jarvis/sessions/manager.py` (1 import hoist)
  - `tests/test_smoke_end_to_end.py`, `tests/test_supervisor_no_llm_call.py` (ruff `--fix` output)
  - `tests/test_build_system.py`, `tests/test_import_graph.py`, `tests/test_supervisor_no_llm_call.py` (`ClassVar` annotations)
- No edits to `src/jarvis/agents/`, `src/jarvis/config/`, `src/jarvis/cli/`, or `src/jarvis/infrastructure/`.

## Files Expected to Change

| File | Change |
|---|---|
| `src/jarvis/sessions/session.py` | Docstring: UUID4 placeholder wording |
| `src/jarvis/sessions/manager.py` | Hoist `HumanMessage` import to module top |
| `tests/test_smoke_end_to_end.py` | `ruff --fix` removes unused imports |
| `tests/test_supervisor_no_llm_call.py` | `ruff --fix` sorts imports + removes unused `pytest`; `ClassVar` on `TOKEN_CONSUMING_METHODS` |
| `tests/test_build_system.py` | `ClassVar` on `REQUIRED_PATTERNS` |
| `tests/test_import_graph.py` | `ClassVar` on `HIGHER_PACKAGES` |
