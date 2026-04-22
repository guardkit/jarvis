---
id: TASK-J001-FIX-001
title: Fix mypy type errors in src/jarvis/ (Success Criterion #6)
task_type: bug-fix
parent_review: TASK-REV-J001
review_report: .claude/reviews/FEAT-JARVIS-001-review-report.md
feature_id: FEAT-JARVIS-001
wave: 1
implementation_mode: direct
complexity: 3
estimated_minutes: 15
dependencies: []
status: completed
completed: 2026-04-22T00:00:00Z
completed_location: tasks/completed/TASK-J001-FIX-001/
organized_files:
- TASK-J001-FIX-001.md
quality_gates:
  mypy: pass (0 errors on src/jarvis/, was 5)
  ruff: pass (src/jarvis/ clean)
  pytest: no-regressions (339/341; 2 pre-existing failures unrelated to this task)
files_changed:
- src/jarvis/agents/supervisor.py
- src/jarvis/sessions/manager.py
- src/jarvis/infrastructure/logging.py
tags:
- review-fix
- mypy
- type-hints
- quality-gate
conductor_workspace: phase1-review-fixes-wave1-1
---

# Task: Fix mypy type errors in `src/jarvis/`

Close the gap on Phase 1 Success Criterion #6 (`phase1-build-plan.md §Success Criteria`): "Ruff + mypy clean on `src/jarvis/`". Ruff is already clean; mypy reports 5 errors in 3 files that must be resolved without loosening `strict = true`.

## Context

Post-build review [FEAT-JARVIS-001-review-report.md §F1](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md) — finding F1 (HIGH).

Current `uv run mypy src/jarvis/` output:

```
src/jarvis/infrastructure/logging.py:65: error: Unused "type: ignore" comment  [unused-ignore]
src/jarvis/infrastructure/logging.py:88: error: List item 4 has incompatible type
    "Callable[[object, str, dict[str, object]], dict[str, object]]";
    expected "Callable[[Any, str, MutableMapping[str, Any]], Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...]]"
src/jarvis/sessions/manager.py:42: error: Missing type parameters for generic type "CompiledStateGraph"  [type-arg]
src/jarvis/agents/supervisor.py:39: error: Missing type parameters for generic type "CompiledStateGraph"  [type-arg]
src/jarvis/agents/supervisor.py:90: error: Missing type parameters for generic type "CompiledStateGraph"  [type-arg]
```

## Scope

Three files; no behaviour changes:

1. [src/jarvis/agents/supervisor.py](../../../src/jarvis/agents/supervisor.py) lines 39, 90 — parameterise `CompiledStateGraph`. Use the concrete state type DeepAgents compiles against (check `create_deep_agent`'s return annotation); fall back to `CompiledStateGraph[Any, Any, Any]` if the inner state type is not publicly exported.
2. [src/jarvis/sessions/manager.py](../../../src/jarvis/sessions/manager.py) line 42 — same parameterisation on the `_supervisor` field.
3. [src/jarvis/infrastructure/logging.py](../../../src/jarvis/infrastructure/logging.py):
   - Line 65 — remove the unused `# type: ignore[arg-type]` comment.
   - Line 88 — widen `_redact_secrets` signature to match `structlog.types.Processor`: first arg `Any`, second `str`, third `MutableMapping[str, Any]`, return `Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...]`. Keep the redaction behaviour byte-for-byte identical.

## Out of Scope

- Any behaviour change (redaction semantics stay exactly as they are).
- Any mypy config relaxation (`strict = true` remains).
- Any non-mypy finding from the review (those are other FIX tasks).

## Acceptance Criteria

- `uv run mypy src/jarvis/` exits 0 with zero errors and zero warnings.
- `uv run ruff check src/jarvis/` still passes cleanly.
- `uv run pytest tests/` shows the same pass count as before this task (no test regressions). Note: `test_jarvis_version_command` is environmentally fragile and is handled by `TASK-J001-FIX-002`; it may still fail until FIX-002 lands.
- Diff is confined to the three files listed above plus at most a 1-line change in `pyproject.toml` if an explicit type-parameter import becomes necessary (prefer `TYPE_CHECKING`-gated imports instead).

## Coach Validation

- `grep -n "CompiledStateGraph" src/jarvis/**/*.py` — every usage must be parameterised.
- `grep -n "type: ignore" src/jarvis/infrastructure/logging.py` — the line-65 comment must be gone.
- Run `uv run mypy src/jarvis/` twice; second run must still return 0.

## Files Expected to Change

| File | Change |
|---|---|
| `src/jarvis/agents/supervisor.py` | Parameterise two `CompiledStateGraph` references |
| `src/jarvis/sessions/manager.py` | Parameterise one `CompiledStateGraph` reference |
| `src/jarvis/infrastructure/logging.py` | Remove unused `type: ignore`; widen `_redact_secrets` signature |
