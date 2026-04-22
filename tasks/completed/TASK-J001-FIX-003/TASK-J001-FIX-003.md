---
id: TASK-J001-FIX-003
title: Tighten AppState typing and move logging configuration to CLI entry
task_type: refactor
parent_review: TASK-REV-J001
review_report: .claude/reviews/FEAT-JARVIS-001-review-report.md
feature_id: FEAT-JARVIS-001
wave: 2
implementation_mode: task-work
complexity: 5
estimated_minutes: 35
dependencies:
- TASK-J001-FIX-001
status: completed
completed: 2026-04-22T14:54:39Z
completed_location: tasks/completed/TASK-J001-FIX-003/
organized_files:
- TASK-J001-FIX-003.md
tags:
- review-fix
- refactor
- lifecycle
- bootstrap
conductor_workspace: phase1-review-fixes-wave2-1
---

# Task: Tighten `AppState` bootstrap and move logging configuration to CLI entry

Resolve two related review findings that both live in the bootstrap path:

- **F3** (MEDIUM): `AppState.supervisor` and `AppState.session_manager` are typed `Any` with stale "*(None until TASK-J001-006 wires it up)*" comments. The CLI has to stitch them in via `dataclasses.replace(state, supervisor=..., session_manager=...)` — a bootstrap smell.
- **F4** (MEDIUM): `JarvisConfig()` runs pydantic validation *before* `startup()` is called, so a pydantic `ValidationError` is surfaced via `click.echo` without structlog being configured. The scenario "Startup configures logging before validating configuration" ([feature:277-283](../../../features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature#L277-L283)) expects structured log events for config failures too.

## Context

Post-build review [FEAT-JARVIS-001-review-report.md §F3 + §F4](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md).

Current shape ([cli/main.py:30-51](../../../src/jarvis/cli/main.py#L30-L51)):

```python
async def _create_app_state() -> AppState:
    config = JarvisConfig()          # pydantic ValidationError here → no structlog yet
    state = await startup(config)     # startup configures structlog first, but too late
    supervisor = build_supervisor(state.config)
    session_manager = SessionManager(supervisor=supervisor, store=state.store)
    return dataclasses.replace(state, supervisor=supervisor, session_manager=session_manager)
```

`AppState` ([lifecycle.py:25-40](../../../src/jarvis/infrastructure/lifecycle.py#L25-L40)) carries three `Any`-typed fields that now all have real types.

## Scope

1. **Configure logging at CLI entry**
   - In [cli/main.py](../../../src/jarvis/cli/main.py), before `JarvisConfig()` is instantiated (both in `health()` and in `_create_app_state`), call `configure(default_log_level)` where `default_log_level = os.environ.get("JARVIS_LOG_LEVEL", "INFO")`.
   - Inside `startup()`, if `config.log_level` differs from the already-applied default, re-apply `configure(config.log_level)` so the user-specified level wins. Idempotent `configure()` is already the contract ([logging.py:71](../../../src/jarvis/infrastructure/logging.py#L71) — the function is safe to call multiple times).
   - Rewrap `JarvisConfig()` call site(s) so `pydantic.ValidationError` is logged via `structlog` before `SystemExit(1)`.

2. **Tighten `AppState` typing**
   - In [lifecycle.py](../../../src/jarvis/infrastructure/lifecycle.py):
     - `supervisor: CompiledStateGraph[...]` (use the same parameterisation as TASK-J001-FIX-001).
     - `store: BaseStore` (import from `langgraph.store.base` under `TYPE_CHECKING`).
     - `session_manager: SessionManager` (import from `jarvis.sessions.manager`).
     - Drop every "*(None until TASK-J001-…)*" comment in the docstring and field annotations.

3. **Collapse the bootstrap into one step**
   - Introduce `build_app_state(config: JarvisConfig) -> AppState` in [lifecycle.py](../../../src/jarvis/infrastructure/lifecycle.py) (or extend `startup()`) that:
     - Ensures logging is configured.
     - Calls `validate_provider_keys()` (as `startup()` already does).
     - Builds the store, supervisor, and `SessionManager`.
     - Returns a fully-populated `AppState` — no more `None` fields.
   - Delete `dataclasses.replace` from `_create_app_state` in [cli/main.py:51](../../../src/jarvis/cli/main.py#L51). `_create_app_state` collapses to: load config → call `build_app_state(config)` → return.

## Out of Scope

- Changing the semantics of `validate_provider_keys()`, the memory-store backend, or the supervisor prompt.
- Any change to `SessionManager.invoke` concurrency model (that's a FEAT-006 concern per review F7).
- Any test file changes beyond what's needed to keep tests passing; do **not** add new BDD scenarios in this task.
- Correlation-id / HumanMessage / tests-ruff polish (those live in `TASK-J001-FIX-004`).

## Acceptance Criteria

- `pydantic.ValidationError` at `JarvisConfig()` load is emitted as a structlog event (JSON or console depending on TTY) **before** the CLI exits 1.
- `AppState` has no `Any`-typed fields remaining; mypy on `src/jarvis/` is still clean (criterion from TASK-J001-FIX-001 is preserved).
- `dataclasses.replace` no longer appears in `src/jarvis/cli/main.py`.
- All three `AppState` fields carry their concrete types; the stale "*(None until TASK-J001-…)*" comments are removed.
- All existing 341 tests still pass (340 baseline + 1 from FIX-002 = 341). If a test asserted on the old `startup()` returning `supervisor=None`, update it to the new contract — but only if it asserts the legacy incomplete state.
- `jarvis health` and `jarvis chat` still work end-to-end (manual smoke: `uv run jarvis health`).

## Coach Validation

- `grep -n "Any" src/jarvis/infrastructure/lifecycle.py` — no `Any` type annotations on `AppState` fields.
- `grep -n "dataclasses.replace" src/jarvis/` — no matches.
- `grep -n "None until TASK" src/jarvis/` — no matches.
- Run the failing-config path by hand: `JARVIS_LOG_LEVEL=bogus uv run jarvis health` — confirm the error is emitted as a structlog event (look for the JSON or bracketed console render), not a bare `click.echo`.

## Files Expected to Change

| File | Change |
|---|---|
| `src/jarvis/infrastructure/lifecycle.py` | Tighten `AppState` types; add `build_app_state` factory; remove stale comments |
| `src/jarvis/cli/main.py` | Configure logging at entry; remove `dataclasses.replace`; route `ValidationError` through structlog before exit 1 |
| `tests/test_infrastructure.py` + `tests/test_cli.py` (if needed) | Update any test asserting on the old `AppState` incomplete shape |
