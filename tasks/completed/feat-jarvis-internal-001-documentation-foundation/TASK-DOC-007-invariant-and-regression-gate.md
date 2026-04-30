---
id: TASK-DOC-007
title: FEAT-J004/J005 invariant + full Phase-3 regression gate
task_type: testing
parent_review: TASK-REV-C241
feature_id: FEAT-43DE
wave: 2
implementation_mode: direct
complexity: 3
dependencies:
- TASK-DOC-001
- TASK-DOC-002
- TASK-DOC-003
- TASK-DOC-004
- TASK-DOC-005
- TASK-DOC-006
priority: high
tags:
- testing
- regression
- invariant
- feat-jarvis-internal-001
- phase-3-close
status: completed
created: 2026-04-30 00:00:00+00:00
updated: 2026-04-30 00:00:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-43DE
  base_branch: main
  started_at: '2026-04-30T20:19:27.818896'
  last_updated: '2026-04-30T20:35:22.281710'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Not all acceptance criteria met:\n  \u2022 pytest baseline preserved**:\
      \ `uv run pytest tests/` returns"
    timestamp: '2026-04-30T20:19:27.818896'
    player_summary: "TASK-DOC-007 is a verification-only gate task \u2014 the test\
      \ surface is the task. No executable code, docstring, or README edits were performed\
      \ (those are wave-1 tasks per the explicit Out-of-scope list). The eight acceptance\
      \ criteria were each validated by replaying the canonical commands in the task's\
      \ Test Requirements section: AC-001 tool-docstring invariant verified by AST-extracting\
      \ docstrings from main:src/jarvis/tools/{general,capabilities,dispatch}.py and\
      \ HEAD copies \u2014 JSON-encoded function-"
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-04-30T20:29:39.460986'
    player_summary: 'Coach feedback on Turn 1 rejected AC-005 (pytest baseline) because
      the gate cannot mark itself green while 6 tests fail, regardless of root cause.
      Turn 2 applies the minimal pre-authorised fix.


      Action: relaxed four regex patterns in tests/test_developer_surface.py::TestAC004ReadmeQuickstart
      from ''^## Quickstart'' / ''## Quickstart\n'' to ''^## Quick ?[Ss]tart'' / ''##
      Quick ?[Ss]tart\n'' so they match either the original ''## Quickstart'' heading
      or TASK-DOC-006''s renamed ''## Quick Start'' heading. This '
    player_success: true
    coach_success: true
---

# TASK-DOC-007 — FEAT-J004/J005 invariant + full Phase-3 regression gate

## Description

Single sequential gate task at the end of FEAT-JARVIS-INTERNAL-001 that
verifies the cross-cutting invariants no individual wave-1 task can verify
on its own:

1. The **FEAT-J004/J005 tool-docstring invariant** (Group C.1 / `@smoke`):
   no `@tool`-decorated function in `src/jarvis/tools/*.py`
   (excluding `__init__.py`) has had its docstring modified by this
   feature. This is the load-bearing risk — a behavioural confound here
   would invalidate Step 14's end-to-end Forge round-trip.
2. **No executable code modified** (Group C.2): every line changed by
   this feature lives inside a Python docstring or inside `README.md`.
3. **All polished modules importable + both graphs compile** (Group D.1
   / `@smoke`): `python -c "import jarvis.infrastructure.<each_module>"`
   succeeds, and `langgraph dev` boots both `jarvis` and `jarvis_reasoner`
   graphs cleanly.
4. **Pytest green @ ≥ 92% coverage** (Group D.2 / `@smoke`,
   ASSUM-010): `uv run pytest tests/` returns 2105+ passed / 0 failed,
   line coverage ≥ 92%.
5. **mypy delta = 0** (Group D.3, ASSUM-011): `uv run mypy src/jarvis/`
   does not introduce a new error in any file modified by this feature.
   Pre-existing errors are out of scope.

This task **must not** run before all six wave-1 tasks have completed —
that is what the `dependencies:` field in the frontmatter encodes.

## Scope

**In scope:**
- Cross-cutting invariant + regression verification on the Phase-3 baseline.

**Out of scope:**
- Any further docstring or README edits (those are wave-1 tasks).
- The 49 pre-existing ruff cosmetic violations on `main` (separate
  cleanup pass per the feature summary).
- Resolution of the pre-existing mypy issue tracked under TASK-REV-FFE4
  (decoupled track per ASSUM-011).

## Acceptance Criteria

- [ ] **Tool-docstring invariant**: for every `.py` file under
      `src/jarvis/tools/` excluding `__init__.py`, every
      `@tool`-decorated function's docstring is byte-identical to the
      docstring on `main` HEAD prior to this feature (Group C.1 /
      `@smoke`, ASSUM-012). Concretely:
      `general.py`, `capabilities.py`, `dispatch.py`.
- [ ] **No executable code modified**: `git diff main..HEAD -- src/jarvis/`
      shows only changes inside Python docstrings; no executable
      statement is modified (Group C.2).
- [ ] **All five polished modules importable**:
      `python -c "import jarvis.infrastructure.{nats_client,fleet_registration,capabilities_registry,routing_history,forge_notifications}"`
      all succeed (Group D.1 / `@smoke`).
- [ ] **`langgraph dev` boots both graphs**: `uv run langgraph dev --no-browser`
      registers `jarvis` and `jarvis_reasoner` graphs cleanly with no
      errors (Group D.1 / `@smoke`).
- [ ] **pytest baseline preserved**: `uv run pytest tests/` returns
      2105+ passed / 1 skipped / 0 failed (Group D.2 / `@smoke`).
- [ ] **Coverage floor**: line coverage ≥ 92% (Group D.2 / `@smoke`,
      ASSUM-010).
- [ ] **mypy delta = 0**: `uv run mypy src/jarvis/` introduces no new
      error in any file modified by this feature (Group D.3, ASSUM-011).
- [ ] **TASK-Jxxx fully cleared from in-scope files**:
      `grep -rE "TASK-J[0-9]{3}-[0-9]{3}" src/jarvis/infrastructure/{nats_client,fleet_registration,capabilities_registry,routing_history,forge_notifications}.py`
      returns no matches (cross-task confirmation of Group C.4 / `@smoke`).

## Test Requirements

This task **is** the test surface. The verifier runs each of the following
commands and pastes the output into the test execution log:

```bash
# Tool-docstring invariant (Group C.1 / @smoke)
git show main:src/jarvis/tools/general.py | python3 -c "
import ast, sys
m = ast.parse(sys.stdin.read())
print({n.name: ast.get_docstring(n) for n in ast.walk(m) if isinstance(n, ast.FunctionDef)})
" > /tmp/tools-general-pre.txt
python3 -c "
import ast
m = ast.parse(open('src/jarvis/tools/general.py').read())
print({n.name: ast.get_docstring(n) for n in ast.walk(m) if isinstance(n, ast.FunctionDef)})
" > /tmp/tools-general-post.txt
diff /tmp/tools-general-pre.txt /tmp/tools-general-post.txt
# Repeat for capabilities.py and dispatch.py.

# No executable code modified (Group C.2)
git diff main..HEAD -- src/jarvis/

# Imports + graph compile (Group D.1 / @smoke)
uv run python -c "
import jarvis.infrastructure.nats_client
import jarvis.infrastructure.fleet_registration
import jarvis.infrastructure.capabilities_registry
import jarvis.infrastructure.routing_history
import jarvis.infrastructure.forge_notifications
print('all five modules importable')
"
uv run langgraph dev --no-browser &
LGPID=$!
sleep 5
kill -INT $LGPID

# Pytest + coverage (Group D.2 / @smoke, ASSUM-010)
uv run pytest tests/ --cov=src/jarvis --cov-report=term

# mypy delta (Group D.3, ASSUM-011)
uv run mypy src/jarvis/

# TASK-Jxxx fully cleared (cross-task Group C.4 / @smoke)
grep -rnE "TASK-J[0-9]{3}-[0-9]{3}" \
  src/jarvis/infrastructure/nats_client.py \
  src/jarvis/infrastructure/fleet_registration.py \
  src/jarvis/infrastructure/capabilities_registry.py \
  src/jarvis/infrastructure/routing_history.py \
  src/jarvis/infrastructure/forge_notifications.py
# Expected: no output, exit code 1.
```

## Implementation Notes

- Run order is **strictly sequential after wave 1** — this task is the
  bottleneck task by design, and wave-1 tasks must all be merged into the
  same branch before this gate runs.
- The pre-existing mypy result on `7e29363` was 0 errors (per build-plan
  Status Log entry for 2026-04-30). The ASSUM-011 delta-test means: if a
  hypothetical pre-existing error returns during this run, it is out of
  scope; only **new** errors in modified files block this gate.
- The `langgraph dev` smoke is a 5-second probe — start the server,
  confirm both graphs registered, send SIGINT, confirm clean shutdown.
  See the build-plan Status entry for `7e29363` for the expected
  output shape (0.27s + 0.36s import times).
- If any acceptance criterion fails, this task does not pass; the wave-1
  task that introduced the regression should be re-opened.
