---
review_target: FEAT-JARVIS-001
task_id: TASK-REV-J001
mode: architectural
depth: standard
output: detailed
completed_at: 2026-04-22T08:00:00Z
score: 82
findings_count: 8
recommendations_count: 5
decision: revise
---

# Review Report: FEAT-JARVIS-001 — Project Scaffolding, Supervisor Skeleton & Session Lifecycle

## Executive Summary

**Verdict: REVISE (fix-then-accept).** The feature delivers the day-1 runnable
skeleton the plan promised. All six load-bearing `ASSUM-*` behaviours and three
DDR-* contracts are implemented correctly in code, not merely described. Scope
invariants hold: no NATS / Telegram / Graphiti / subagent / custom-tool imports
escape into `src/jarvis/`, and the eight reserved packages for FEAT-002..007 are
properly stubbed with `# Reserved for FEAT-JARVIS-0NN` comments.

Three classes of polish are required before declaring Phase 1 closed per the
success criteria in [phase1-build-plan.md:52-63](../../docs/research/ideas/phase1-build-plan.md):

1. **Mypy is not clean on `src/jarvis/`** — 5 errors, all trivial fixes, but
   violates Success Criterion #6.
2. **One pytest failure** — `test_jarvis_version_command` is environmentally
   fragile (subprocess picks up a Python without `jarvis` installed), violating
   Success Criterion #5.
3. **`AppState` typing is too loose and stale** — `supervisor: Any` /
   `session_manager: Any` with comments referencing tasks that are already
   complete; the CLI stitches them in via `dataclasses.replace`, which is
   a bootstrap smell.

None require re-scoping. All three fit in a single 15–30 minute touch-up task.

## Review Details

- **Mode**: Architectural (with code-quality crosscheck)
- **Depth**: Standard (clarification recorded in TASK-REV-J001: focus=all,
  depth=standard, tradeoff=balanced, extensibility=yes)
- **Review scope**: Post-build gate (Step 6 of
  [phase1-build-plan.md:473-482](../../docs/research/ideas/phase1-build-plan.md))
- **Evidence base**: 29 source files under `src/jarvis/`, 14 test files under
  `tests/`, pyproject.toml, 35 BDD scenarios, plan/scope/design docs
- **Quality gates run**: `uv run pytest`, `uv run ruff check`, `uv run mypy`
- **Knowledge graph context**: skipped (Graphiti MCP unavailable in session;
  non-blocking per Phase 1.5 graceful-degradation pattern)

## Scores

| Axis | Score | Notes |
|---|---|---|
| ASSUM-*/DDR-* compliance | 10/10 | All 6 assumptions + 3 DDRs implemented |
| Scope invariants (no NATS/Telegram/Graphiti/subagents/tools) | 10/10 | Grep-clean; 8 reserved packages stubbed |
| Test coverage vs 35 BDD scenarios | 9/10 | 341 tests, 340 pass; 1 env-fragile failure |
| Ruff clean on `src/jarvis/` | 10/10 | "All checks passed!" |
| Mypy clean on `src/jarvis/` | 6/10 | 5 errors in 3 files |
| Hexagonal layering (ADR-ARCH-002/006) | 10/10 | AST + runtime import-graph tests enforce it |
| Bootstrap design | 7/10 | `AppState.Any` + `dataclasses.replace` smell |
| Prompt scope discipline (FEAT-002/004/007 boundary) | 10/10 | Module docstring pins the invariant |
| **Overall** | **82/100** | Strong foundation; polish required |

## Findings

### F1 — Mypy: 5 errors in `src/jarvis/` (HIGH, blocks Success Criterion #6)

**Evidence** (`uv run mypy src/jarvis/`):

```
src/jarvis/infrastructure/logging.py:65: error: Unused "type: ignore" comment  [unused-ignore]
src/jarvis/infrastructure/logging.py:88: error: List item 4 has incompatible type
    "Callable[[object, str, dict[str, object]], dict[str, object]]";
    expected "Callable[[Any, str, MutableMapping[str, Any]], Mapping[str, Any] | str | bytes | bytearray | tuple[Any, ...]]"
src/jarvis/sessions/manager.py:42: error: Missing type parameters for generic type "CompiledStateGraph"  [type-arg]
src/jarvis/agents/supervisor.py:39: error: Missing type parameters for generic type "CompiledStateGraph"  [type-arg]
src/jarvis/agents/supervisor.py:90: error: Missing type parameters for generic type "CompiledStateGraph"  [type-arg]
```

- 3 are the same class of issue: `CompiledStateGraph` is generic and needs type
  parameters.
- [logging.py:88](../../src/jarvis/infrastructure/logging.py#L88) — the
  `_redact_secrets` signature uses `dict[str, object]` but `structlog.types.Processor`
  expects `MutableMapping[str, Any] → Mapping[...]`. Widen the types or add
  `cast`.
- [logging.py:65](../../src/jarvis/infrastructure/logging.py#L65) — `# type: ignore[arg-type]` is no longer needed.

**Fix**: ~10 minutes. Trivial annotations.

### F2 — Pytest: `test_jarvis_version_command` fails (HIGH, blocks Success Criterion #5)

**Evidence** ([test_build_system.py:211-221](../../tests/test_build_system.py#L211-L221)):

```python
result = subprocess.run(
    [sys.executable, "-m", "jarvis.cli.main", "version"],
    capture_output=True, text=True, timeout=10,
)
assert result.returncode == 0  # fails: ModuleNotFoundError: No module named 'jarvis'
```

`sys.executable` resolves to the Python interpreter running pytest. In the
current dev machine state, that interpreter is Python 3.14 (user-active venv),
while `uv sync` installed `jarvis` into a separate 3.12 `.venv`. Result:
`jarvis` not importable from `sys.executable`.

**Root cause**: environment drift — `uv` warned at session start that
`VIRTUAL_ENV=.../Python 3.14` doesn't match the project's `.venv`. The test
is correct in principle (`sys.executable` is the right pattern) but the
project venv ↔ active venv mismatch defeats it.

**Fix options** (any one works):
- (a) Pin the project to a single Python version end-to-end (add `python-version`
  file or README step saying "always `uv run`, never system python").
- (b) Harden the test: skip if `importlib.util.find_spec("jarvis")` returns
  `None` under `sys.executable`, or use `uv run` explicitly.
- (c) Add a pre-test assertion that `sys.executable` has `jarvis` installed
  so the failure message is diagnostic rather than opaque.

Option (a) is the Phase 1 answer.

### F3 — `AppState` typing is loose and carries stale bootstrap comments (MEDIUM)

**Evidence** ([lifecycle.py:25-40](../../src/jarvis/infrastructure/lifecycle.py#L25-L40)):

```python
class AppState:
    config: JarvisConfig
    supervisor: Any  # CompiledStateGraph — not yet available
    store: Any  # InMemoryStore (or future backend)
    session_manager: Any  # SessionManager — not yet available
```

The docstring (lines 31-34) says "*(None until TASK-J001-006 wires it up)*" —
but TASK-J001-006 and TASK-J001-007 are both **completed**. The comments are
a build-time artefact that leaked into shipped code.

Downstream consequence ([cli/main.py:43-51](../../src/jarvis/cli/main.py#L43-L51)):

```python
config = JarvisConfig()
state = await startup(config)

supervisor = build_supervisor(state.config)
session_manager = SessionManager(supervisor=supervisor, store=state.store)

return dataclasses.replace(state, supervisor=supervisor, session_manager=session_manager)
```

`startup()` returns an *incomplete* `AppState` with two `None` fields that the
CLI must then fix up. A complete `AppState` in one step would eliminate this
and tighten the types.

**Fix** (suggested): move supervisor + session_manager construction into
`startup()` itself, or introduce `compose_app_state(config)` that does it all.
Type `supervisor: CompiledStateGraph`, `store: BaseStore`, `session_manager:
SessionManager`. Drop the stale comments.

### F4 — Scenario "Startup configures logging before validating configuration" has a partial gap (MEDIUM)

**Evidence**: The scenario
([feature:277-283](../../features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature))
requires logging to be configured *before* configuration validation so that
the validation failure itself is emitted as a structured log event.

- [lifecycle.py:63](../../src/jarvis/infrastructure/lifecycle.py#L63) configures
  logging first and validates provider keys second — ✓ for the
  `validate_provider_keys()` path.
- But `JarvisConfig()` **instantiation** (pydantic field validation) happens
  at [cli/main.py:78](../../src/jarvis/cli/main.py#L78) and
  [cli/main.py:43](../../src/jarvis/cli/main.py#L43), *before* `startup()` is
  called. Pydantic `ValidationError` is surfaced via `click.echo(..., err=True)`,
  not as a structlog event.

This is a narrow interpretation gap, not a load-bearing failure: all 341 tests
include 340 passing, so whatever the existing test for this scenario checks,
it's passing. Worth tightening so the guarantee holds for *both* pydantic and
post-pydantic failures.

**Fix**: configure structlog at CLI entry (before loading config), or split
`JarvisConfig` loading into two phases: load (pure) then `startup()` validates
and emits structured events.

### F5 — `correlation_id` docstring says ULID, code uses UUID (LOW)

**Evidence**:
- [session.py:29](../../src/jarvis/sessions/session.py#L29) docstring:
  "ULID reserved for FEAT-004 trace-richness (ADR-ARCH-020)".
- [manager.py:79](../../src/jarvis/sessions/manager.py#L79) code:
  `correlation_id=uuid.uuid4().hex`.

ULIDs are sortable / timestamp-prefixed; UUID4 is not. Since FEAT-004 is the
first consumer of trace-richness, fixing now (before FEAT-004 starts depending
on it) is cheap. Either swap to `ulid-py` or update the docstring to match the
code ("UUID4 placeholder; will migrate to ULID at FEAT-004").

### F6 — Ruff errors in `tests/` (LOW, scoped outside success criterion)

**Evidence** (`uv run ruff check src/jarvis/ tests/`): 7 errors, all in `tests/`:

- `F401` unused imports in `test_smoke_end_to_end.py`, `test_supervisor_no_llm_call.py`
- `RUF012` mutable class attrs (mark with `typing.ClassVar`) in 3 test files
- `I001` unsorted imports in `test_supervisor_no_llm_call.py`

Success Criterion #6 scopes to `src/jarvis/` only, so this doesn't block Phase 1.
But `ruff check tests/` being red signals drift — worth including tests in the
success bar for Phase 2. 4 of 7 are `--fix`-able.

### F7 — `SessionManager` concurrency model is adequate but implicit (LOW)

**Evidence** ([manager.py:47](../../src/jarvis/sessions/manager.py#L47),
[manager.py:160-164](../../src/jarvis/sessions/manager.py#L160-L164)):

```python
self._in_flight: dict[str, bool] = {}
...
if self._in_flight.get(sid, False):
    raise JarvisError(msg)
self._in_flight[sid] = True
try:
    ...
```

Between the `get` check and the `= True` assignment there is no `await`, so
under asyncio's single-event-loop this is race-free. For a CLI-only Phase 1
this is correct. For FEAT-006 (Telegram) the adapter may drive the
SessionManager from a different task; at that point the plain-dict flag
becomes a liability.

**Fix** (defer to FEAT-006 consumer): when a second adapter lands, either
document "single-tasked-per-session" as an explicit invariant or upgrade
`_in_flight` to `dict[str, asyncio.Lock]` with `lock.locked()` check.

### F8 — Local import of `HumanMessage` inside `invoke()` (LOW)

**Evidence** ([manager.py:166](../../src/jarvis/sessions/manager.py#L166)):

```python
async def invoke(self, ...) -> str:
    ...
    try:
        from langchain_core.messages import HumanMessage
```

Import at function scope is usually used to defer heavy imports or break
cycles. `langchain_core.messages` is already a runtime dep and `manager.py`
imports LangGraph types in `TYPE_CHECKING` only. Safe to hoist to module top.
Micro-nit.

## Context Used

- `docs/research/ideas/phase1-supervisor-scaffolding-scope.md` (scope)
- `docs/research/ideas/phase1-build-plan.md` (build plan, success criteria)
- `features/project-scaffolding-supervisor-sessions/*.feature` (35 scenarios)
- `tasks/in_review/TASK-REV-J001-*.md` (planning review decisions)
- `.guardkit/features/FEAT-JARVIS-001.yaml` (11-task completion record)

Knowledge graph context: skipped (Graphiti MCP not available in session).

## Recommendations

Priority-ordered, all fit in a single revision pass.

### R1 — Fix mypy errors in `src/jarvis/` (REQUIRED for Success Criterion #6)

Add generic parameters to `CompiledStateGraph` usages in
[supervisor.py:39,90](../../src/jarvis/agents/supervisor.py#L39) and
[manager.py:42](../../src/jarvis/sessions/manager.py#L42). Widen
`_redact_secrets` signature in
[logging.py:21-48](../../src/jarvis/infrastructure/logging.py#L21-L48) to match
`structlog.types.Processor`; drop the unused `type: ignore` at line 65.

**Effort**: ~10 min. **Risk**: none.

### R2 — Stabilise `test_jarvis_version_command` (REQUIRED for Success Criterion #5)

Pin the project to Python 3.12 as the single interpreter end-to-end
(add `.python-version`, document `uv run` as the entry discipline, or both).

**Effort**: ~10 min. **Risk**: none — environmental hygiene only.

### R3 — Tighten `AppState` and bootstrap path (RECOMMENDED)

Move `build_supervisor` + `SessionManager` construction into `startup()` (or a
new `compose_app_state`). Replace `Any` fields with
`CompiledStateGraph[...]`, `BaseStore`, `SessionManager`. Remove the stale
"*(None until TASK-J001-006…)*" comments. Drop `dataclasses.replace` at
[cli/main.py:51](../../src/jarvis/cli/main.py#L51).

**Effort**: ~20 min. **Risk**: low — CLI path remains identical; tests for
`startup()` continue to hold since they already assert `AppState`.

### R4 — Close the logging-before-validation gap (RECOMMENDED)

Move `configure(log_level)` to CLI entry (before `JarvisConfig()` is called),
or accept a logging-fallback path when pydantic validation fires.

**Effort**: ~10 min. **Risk**: low.

### R5 — Cosmetic polish (NICE-TO-HAVE)

- Resolve the `correlation_id` ULID-vs-UUID docstring drift (F5).
- Hoist `HumanMessage` import to module top (F8).
- Run `ruff check tests/ --fix` to clear 4 auto-fixable issues (F6).
- Annotate `RUF012` mutable class attrs with `typing.ClassVar` in 3 test files.

**Effort**: ~15 min combined. **Risk**: none.

## Decision Matrix

| Option | Effort | Risk | Recommended When |
|---|---|---|---|
| [A]ccept as-is | 0 min | Ships with failing mypy + 1 failing test → Phase 1 success criteria #5, #6 not met | N/A for this review |
| [R]evise (R1+R2 required, R3–R5 recommended) | ~30–60 min | Low — all trivial edits | **← Recommended**; closes the phase cleanly |
| [I]mplement (create subtasks for fixes) | ~10 min overhead + fixes | Low | Use if you want the fixes tracked as their own AutoBuild pass |
| [C]ancel | — | Throws away review findings | Not recommended |

## Appendix

### A. Quality-Gate Output (abridged)

```
pytest:  340 passed, 1 failed, 4 warnings
ruff (src/jarvis/):  All checks passed!
ruff (tests/):       7 errors (4 auto-fixable)
mypy (src/jarvis/):  5 errors in 3 files
```

### B. Invariant checks (all ✓)

- `grep -rn '^(import|from)' src/jarvis/ | grep -iE '(nats|telegram|graphiti|discord)'` → 0 matches
- `subagents=[]` and `tools=[]` in `build_supervisor` ([supervisor.py:92,94](../../src/jarvis/agents/supervisor.py#L92))
- 8 reserved packages each carry a `# Reserved for FEAT-JARVIS-00N` comment
- Hexagonal boundary enforced by `tests/test_import_graph.py` (AST + runtime)

### C. BDD-scenario → test coverage

- 35 scenarios in the feature file
- 341 pytest items across 14 test modules
- 1 failing test is the `version`-command AC-004 check (F2), which represents
  a valid scenario; the code behaves correctly under `uv run` / correct venv

### D. 6 ASSUM pins implementation evidence

| Pin | Spec | Code | ✓ |
|---|---|---|---|
| ASSUM-001 | blank-line chat turn skipped | [main.py:154](../../src/jarvis/cli/main.py#L154) `if stripped == "": continue` | ✓ |
| ASSUM-002 | `/exit` case-sensitive, trimmed | [main.py:158](../../src/jarvis/cli/main.py#L158) `if stripped == "/exit": break` | ✓ |
| ASSUM-003 | concurrent invoke refused | [manager.py:160-162](../../src/jarvis/sessions/manager.py#L160-L162) | ✓ |
| ASSUM-004 | read-next-line after reply | [main.py:141-164](../../src/jarvis/cli/main.py#L141-L164) serial await loop | ✓ |
| ASSUM-005 | ValidationError → exit 1 | [main.py:76-81](../../src/jarvis/cli/main.py#L76-L81) | ✓ |
| ASSUM-006 | non-CLI adapter → JarvisError | [manager.py:65-70](../../src/jarvis/sessions/manager.py#L65-L70) | ✓ |
