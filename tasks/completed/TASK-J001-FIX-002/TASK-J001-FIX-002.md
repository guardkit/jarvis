---
id: TASK-J001-FIX-002
title: Pin Python 3.12 end-to-end and stabilise the subprocess entry-point test
task_type: bug-fix
parent_review: TASK-REV-J001
review_report: .claude/reviews/FEAT-JARVIS-001-review-report.md
feature_id: FEAT-JARVIS-001
wave: 1
implementation_mode: direct
complexity: 2
estimated_minutes: 10
dependencies: []
status: completed
completed: 2026-04-22T00:00:00Z
completed_location: tasks/completed/TASK-J001-FIX-002/
organized_files:
- TASK-J001-FIX-002.md
quality_gates:
  target_test: pass (test_jarvis_version_command passes on clean .venv)
  full_suite: 340/341 passed (+1 vs. pre-task baseline of 339); 1 pre-existing failure (test_returns_compiled_state_graph requires OPENAI_API_KEY in ambient env, unrelated)
  full_suite_with_api_key: 341/341 passed — matches coach target exactly
  python_pin: .venv uses Python 3.12.4 via .python-version
files_changed:
- .python-version
- README.md
- tests/test_build_system.py
notes: |
  `uv sync --dev` on this project installs runtime deps only; dev deps are
  declared under [project.optional-dependencies].dev, so `uv sync --extra dev`
  (or --all-extras) is required to install pytest. This is out of scope for
  FIX-002 but worth a follow-up: either update the task-doc validation command,
  migrate dev deps to [dependency-groups].dev (PEP 735), or add [tool.uv]
  default-groups so `--dev` auto-includes them.
tags:
- review-fix
- environment
- ci-hygiene
- quality-gate
conductor_workspace: phase1-review-fixes-wave1-2
---

# Task: Pin Python 3.12 end-to-end; stabilise the subprocess entry-point test

Close Phase 1 Success Criterion #5 ("All Phase 1 smoke tests pass"). One test currently fails due to environment drift: `test_jarvis_version_command` invokes `sys.executable -m jarvis.cli.main version`, but when the active venv is Python 3.14 (a different venv than the project's `.venv` at 3.12), `jarvis` is not importable from `sys.executable`.

## Context

Post-build review [FEAT-JARVIS-001-review-report.md §F2](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md) — finding F2 (HIGH).

Observed during review:

```
warning: `VIRTUAL_ENV=/Library/Frameworks/Python.framework/Versions/3.14`
         does not match the project environment path `.venv` and will be ignored
...
FAILED tests/test_build_system.py::TestAC004EntryPoint::test_jarvis_version_command
  ModuleNotFoundError: No module named 'jarvis'
```

The test body ([tests/test_build_system.py:211-221](../../../tests/test_build_system.py#L211)) is correct in using `sys.executable`; the failure is environmental, not algorithmic.

## Scope

1. **Pin Python version** — create `/.python-version` at repo root with exactly the one line `3.12` (matches [pyproject.toml:9](../../../pyproject.toml) `requires-python = ">=3.12,<3.13"` and `ADR-ARCH-010`). `uv` respects this file and will select 3.12 even when an ambient venv is a different version.
2. **README Quickstart hardening** — update the Quickstart in [README.md](../../../README.md) to make `uv run` the canonical invocation (instead of bare `python -m` or `pytest`). One short sentence is enough: "Run everything via `uv run …`; `uv` selects the project's pinned 3.12 interpreter."
3. **Test-level safety net** — in [tests/test_build_system.py](../../../tests/test_build_system.py) `test_jarvis_version_command`, add a pre-assertion that prints a diagnostic if `jarvis` is not importable under `sys.executable`, so future environment drift fails loudly rather than opaquely. Do NOT `pytest.skip` — a silent skip would hide the same class of bug.

   Suggested shape:

   ```python
   check = subprocess.run(
       [sys.executable, "-c", "import jarvis; print(jarvis.__version__)"],
       capture_output=True, text=True, timeout=10,
   )
   assert check.returncode == 0, (
       f"sys.executable {sys.executable!r} cannot import jarvis. "
       f"Run via `uv run pytest` so the project's pinned venv is used. "
       f"stderr: {check.stderr}"
   )
   ```

## Out of Scope

- Any change to the package version string, `requires-python`, or build backend.
- Any CI pipeline changes (no CI exists yet in Phase 1).
- Any fix to other finding-F-* items.

## Acceptance Criteria

- `.python-version` exists at repo root with content `3.12\n`.
- `uv run pytest tests/test_build_system.py::TestAC004EntryPoint::test_jarvis_version_command -v` passes on a clean `.venv` (delete `.venv`, `uv sync --dev`, `uv run pytest <target>`).
- `uv run pytest tests/` overall pass count increases by exactly 1 vs. pre-task baseline (the one failing test now passes).
- README contains a one-line Quickstart note steering users to `uv run`.

## Coach Validation

- `cat .python-version` — exactly `3.12`.
- `uv run python -c "import sys; print(sys.executable)"` — path contains `.venv/`.
- Full `uv run pytest tests/` shows 341 passed, 0 failed.

## Files Expected to Change

| File | Change |
|---|---|
| `.python-version` | NEW — one line `3.12` |
| `README.md` | UPDATED — Quickstart points to `uv run` |
| `tests/test_build_system.py` | UPDATED — diagnostic pre-assertion in `test_jarvis_version_command` |
