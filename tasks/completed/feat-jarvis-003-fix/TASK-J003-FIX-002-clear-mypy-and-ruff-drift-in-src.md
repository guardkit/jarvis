---
complexity: 3
created: 2026-04-26 00:00:00+00:00
dependencies: []
estimated_minutes: 35
feature_id: FEAT-J003-FIX
id: TASK-J003-FIX-002
implementation_mode: direct
parent_review: FEAT-JARVIS-003
priority: high
status: completed
completed: '2026-04-27T00:00:00+00:00'
tags:
- phase-2
- jarvis
- feat-jarvis-003-fix
- build-hygiene
- mypy
- ruff
- ddr-014
task_type: bugfix
title: Clear all mypy + ruff drift in src/jarvis/ to satisfy Phase 2 close criterion #9
updated: '2026-04-27T00:00:00+00:00'
wave: 1
test_results:
  status: pass
  last_run: 2026-04-27
  ruff: "All checks passed!"
  mypy: "Success: no issues found in 39 source files"
  pytest: "1585 passed, 2 skipped"
---

# Clear all mypy + ruff drift in src/jarvis/ to satisfy Phase 2 close criterion #9

**Feature:** FEAT-J003-FIX
**Wave:** 1 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [FEAT-JARVIS-003 review report](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md) — Finding F3
**Phase-2 close criterion:** #9 — *"Ruff + mypy clean on new src/jarvis/ modules"* (currently 9 mypy + 8 ruff errors)

## Description

Phase 2 closes only when `ruff check src/jarvis/` and `mypy src/jarvis/` both report zero errors. Today there are 9 mypy errors and 8 ruff errors. The most substantive error — the one that actually flags Finding F1's production gap structurally — is in `_emit_frontier_log`'s `outcome` Literal: the type annotation omits `"attended_only"` even though Layer-2 callers pass exactly that string (matching design contract 4 verbatim).

This task widens the Literal, autofixes the safe ruff drift, and migrates `RoleName` + `FrontierTarget` from `class X(str, Enum)` to `class X(StrEnum)` (UP042). The migration must preserve every behaviour relied on by FEAT-J003: `RoleName("")` raises `ValueError`, `RoleName.CRITIC.value == "critic"`, members are `str` instances, `set(RoleName)` iterates, and `@tool(parse_docstring=True)` argument coercion still accepts literal role strings.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py::_emit_frontier_log` `outcome` parameter Literal extended to `Literal["success", "config_missing", "attended_only", "provider_unavailable", "degraded_empty"]` — exactly the union from FEAT-J003 design contract 4 / IMPLEMENTATION-GUIDE.md §4 Contract 4.
- [ ] `mypy src/jarvis/` reports **zero errors** (currently 9). Includes the 5 unreachable-branch warnings — restructure or `# type: ignore[unreachable]` with a comment explaining why. The two arg-type errors at lines 661 and 678 disappear naturally with the Literal widening.
- [ ] `_make_role_runner` in `src/jarvis/agents/subagents/jarvis_reasoner.py` gains a return type annotation. Suggest `Callable[[_ReasonerState], Awaitable[dict[str, Any]]]` (or whatever mypy ratifies cleanly).
- [ ] `add_conditional_edges` mapping arg type at jarvis_reasoner.py line 374 — narrow the dict type to `dict[Hashable, str]` per langgraph's stub.
- [ ] `class RoleName(str, Enum)` → `class RoleName(StrEnum)` in `src/jarvis/agents/subagents/types.py`. **Verify:** `RoleName("")` still raises `ValueError`; `RoleName("CRITIC")` still raises `ValueError` (uppercase); `RoleName("critic") is RoleName.CRITIC`; `RoleName.CRITIC.value == "critic"`; existing test_subagent_types_role_name.py passes unchanged.
- [ ] `class FrontierTarget(str, Enum)` → `class FrontierTarget(StrEnum)` in `src/jarvis/tools/dispatch_types.py`. Same semantic invariants. Existing test_dispatch_types_frontier_escalation.py passes unchanged.
- [ ] `ruff check src/jarvis/` reports **zero errors** (currently 8). Run `ruff check src/jarvis/ --fix` for the autofixable subset, then manually clear remaining UP042/RUF002/UP037/I001/RUF022 issues.
- [ ] `OPENAI_API_KEY=stub uv run pytest tests/` still reports **1585 passed, 2 skipped** (no regressions from the StrEnum migration or Literal widening).
- [ ] No new `# type: ignore` or `# noqa` comments without an inline justification line referencing the rule and why suppression is correct.
- [ ] **Out of scope:** ruff drift in `tests/` (28 errors there — cleaner up follow-up if desired, but not gated by Phase-2 close criterion #9).

## Files Expected to Change

- `src/jarvis/tools/dispatch.py` — Literal widening + unreachable-branch cleanup.
- `src/jarvis/tools/dispatch_types.py` — `FrontierTarget` → `StrEnum`.
- `src/jarvis/tools/general.py` — unreachable-branch cleanup at line 187.
- `src/jarvis/tools/__init__.py` — `__all__` sort.
- `src/jarvis/agents/subagents/types.py` — `RoleName` → `StrEnum`.
- `src/jarvis/agents/subagents/jarvis_reasoner.py` — `_make_role_runner` annotation, conditional-edges mapping type.
- Possibly `src/jarvis/tools/dispatch_types.py` (RUF002 EN-DASH if present in docstrings).

## Notes

This task **unblocks FIX-001's** TDD acceptance gate — once the Literal is widened, mypy is satisfied with the existing Layer-2 code path and FIX-001's new integration test runs against a clean baseline. Land FIX-002 first (Wave 1); FIX-001 follows in Wave 2.

## Implementation Summary

**Outcome:** Phase 2 close criterion #9 satisfied — `ruff check src/jarvis/` and `mypy src/jarvis/` both report zero errors; full test suite remains at 1585 passed, 2 skipped.

**Baseline correction.** Task description was based on a stale baseline (9 mypy + 8 ruff errors). At the time of execution the surface had already been narrowed to **2 mypy + 1 ruff** by adjacent work — `FrontierTarget` had already been migrated to `StrEnum`, the `_emit_frontier_log` `outcome` Literal already included `"attended_only"`, and the dispatch.py / general.py / tools/__init__.py drift the description listed had already been cleared by TASK-J002F-001. Only `RoleName`, `_make_role_runner`, and the `add_conditional_edges` mapping type remained.

**Approach.**
- `src/jarvis/agents/subagents/types.py`: switched `class RoleName(str, Enum)` → `class RoleName(StrEnum)`. Test invariants verified: `RoleName("")` raises `ValueError`, `RoleName("CRITIC")` raises (lowercase-only), `RoleName.CRITIC.value == "critic"`, `issubclass(RoleName, str)` and `issubclass(RoleName, Enum)` both still hold (StrEnum extends both). `test_subagent_types_role_name.py` (33 cases) passed unchanged.
- `src/jarvis/agents/subagents/jarvis_reasoner.py`: added `Callable[[_ReasonerState], Any]` return annotation to `_make_role_runner`; narrowed `role_edge_map` to `dict[Hashable, str]` so `add_conditional_edges` accepts it; added `from collections.abc import Callable, Hashable`.

**Lessons.**
- langgraph's `StateGraph.add_node` does not propagate the StateGraph's `StateT` into the `_Node[NodeInputT_contra]` Protocol — mypy infers `NodeInputT_contra=Never`, so a typed `Callable[[_ReasonerState], Any]` looks incompatible with `_Node[Never]` even though it is contravariantly valid at runtime. The typed `_make_role_runner` therefore required a single justified `# type: ignore[arg-type]` at the `builder.add_node(role.value, runner)` call site, with an inline comment naming the rule and the cause. Returning `Any` from `_make_role_runner` (instead of typing it) would have hidden the same incompatibility but lost the contract — the explicit annotation + scoped suppression is the better trade.
- Always re-baseline mypy + ruff before starting a "clean drift" task. The drift surface compresses fast as adjacent tasks land, and the fix list in the description can rot in days.

**Related ADRs / contracts.**
- DDR-014 (Phase-2 close criterion #9 — ruff + mypy clean on `src/jarvis/`)
- DDR-011 (RoleName closed enum invariants — preserved by StrEnum migration)
- FEAT-J003 IMPLEMENTATION-GUIDE.md §4 Contract 4 (already satisfied by prior `outcome` Literal widening)
