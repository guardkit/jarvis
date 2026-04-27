---
id: TASK-J002F-001
title: Quality gates - ruff and mypy clean on tools surface
task_type: feature
status: completed
created: 2026-04-26 00:00:00+00:00
updated: '2026-04-27T00:00:00+00:00'
completed: '2026-04-27T00:00:00+00:00'
priority: medium
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 45
dependencies: []
parent_review: FEAT-JARVIS-002-review-2026-04-26
feature_id: FEAT-J002F
tags:
- phase-2
- jarvis
- feat-jarvis-002
- quality-gates
- post-review-fix
scenarios_covered:
- ruff check exits 0 on src/jarvis/tools and related FEAT-J002 modules
- mypy exits 0 on src/jarvis/tools
- Full pytest suite remains at 1585 passed, 2 skipped
test_results:
  status: pass
  coverage: null
  last_run: 2026-04-27
  ruff: "All checks passed!"
  mypy: "Success: no issues found in 7 source files"
  pytest: "1585 passed, 2 skipped"
---
# Quality gates: ruff + mypy clean on FEAT-JARVIS-002 tools surface

**Feature:** FEAT-J002F "FEAT-JARVIS-002 Quality & Hygiene Cleanup"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 30-45 min
**Parent review:** [.claude/reviews/FEAT-JARVIS-002-review-report.md §4.2](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)

## Description

Phase 2 build-plan success criterion #9 ("Ruff + mypy clean on all
new `src/jarvis/` modules") is the only outstanding red gate from the
26 Apr `/task-review` of FEAT-JARVIS-002. AutoBuild closed without
catching it because its quality oracle didn't include the
project-level lint/type sweep. Close the gap before Phase 3 inherits
the technical debt.

All findings are stylistic / type-hygiene; **no behavioural change**
to the tool surface is allowed by this task.

## Findings to Close

**Ruff (7 errors across the J002 surface):**

| Rule | File | Action |
|---|---|---|
| RUF022 | `src/jarvis/tools/__init__.py:64` | Either accept isort sort, or `# noqa: RUF022` with comment explaining the deliberate category grouping |
| UP037 | `src/jarvis/tools/__init__.py:90` | Remove quotes from `"JarvisConfig"` annotation (forward reference no longer needed) |
| UP042 | `src/jarvis/tools/dispatch_types.py:39` | Convert `class FrontierTarget(str, Enum)` to `class FrontierTarget(StrEnum)` |
| I001 | one file | `ruff check --fix` autofix |
| RUF002 | several docstrings | Pin `[tool.ruff.lint.per-file-ignores] "src/jarvis/**" = ["RUF002"]` in `pyproject.toml` — em-dash prose style is intentional |

**Mypy (7 errors in `src/jarvis/tools/`):**

| Line | Error | Fix |
|---|---|---|
| `general.py:187` | `unreachable` after type narrowing | Either remove the dead arm or `# type: ignore[unreachable]` with explanatory comment |
| `dispatch.py:349,356` | `Subclass of "str" and "ResultPayload" cannot exist` | Add explicit `isinstance(value, str)` narrowing before the comparison |
| `dispatch.py:359` | `unreachable` | Same treatment as `general.py:187` |
| `dispatch.py:661,678` | `arg-type — Literal["attended_only"] not in outcome union` | Widen the `outcome` literal in `_emit_frontier_log` to include `"attended_only"`, OR split the call site into a specialised emitter |
| `dispatch.py:944` | `unreachable` | Same treatment as `general.py:187` |

## Constraints

- **No behavioural changes.** Every existing test must pass without
  modification. If a test starts failing, the fix is wrong — revert
  and pick a different approach.
- **No new tests required.** Lint/type cleanup is its own
  verification.
- **No mass mechanical fixes.** Do not run `ruff check --fix
  --unsafe-fixes` blindly — RUF022 and UP042 deserve human review
  because they affect the public ordering and `__mro__` of exported
  symbols.

## Acceptance Criteria

```bash
.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py
# expected: "All checks passed!" (exit 0)

.venv/bin/mypy src/jarvis/tools
# expected: "Success: no issues found in N source files" (exit 0)

.venv/bin/pytest -q
# expected: "1585 passed, 2 skipped" (exit 0)
```

All three commands must exit 0. If any test starts failing, revert
and re-approach.

## Files Likely Touched

- `src/jarvis/tools/__init__.py`
- `src/jarvis/tools/dispatch.py`
- `src/jarvis/tools/dispatch_types.py`
- `src/jarvis/tools/general.py`
- `pyproject.toml` (only if pinning the RUF002 per-file ignore)

## Out of Scope

- Coverage improvements on `tools/dispatch.py` (the 53% number in
  the J002-only run is an artefact of FEAT-J003 tests being excluded
  — see review §4.4).
- Any change to tool docstrings beyond the RUF002 dash issue.
- Re-running `langgraph dev` or `jarvis chat` (criteria #5/#6 are
  attended-checkpoint items, not subtasks).

## See Also

- [Review report §4.2](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)
- [phase2-build-plan.md §Success Criteria #9](../../../docs/research/ideas/phase2-build-plan.md)
