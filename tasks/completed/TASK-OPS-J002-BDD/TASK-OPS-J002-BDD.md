---
id: TASK-OPS-J002-BDD
title: 'wire pytest-bdd collection so features/*.feature run during pytest invocation'
status: completed
created: '2026-04-25T18:00:00Z'
updated: '2026-04-26T12:45:00Z'
completed: '2026-04-26T12:45:00Z'
completed_location: tasks/completed/TASK-OPS-J002-BDD/
previous_state: in_review
priority: high
complexity: 3
task_type: bugfix
tags: [bdd, pytest-bdd, feat-jarvis-002, follow-up]
parent_task: TASK-OPS-BDDM-9
upstream_repo_task: 'guardkit:TASK-OPS-BDDM-9'
organized_files: ['TASK-OPS-J002-BDD.md']
test_results:
  status: passing
  coverage: null
  last_run: '2026-04-26T12:30:00Z'
  bdd_runner_shape:
    task_id: TASK-J002-008
    scenarios_passed: 0
    scenarios_failed: 0
    scenarios_pending: 12
    coach_approval_rule_failed_eq_zero: true
    note: >
      pytest-bdd expands the 7 literal `@task:TASK-J002-008` scenario tags
      into 12 pytest items (Scenario Outlines yield one item per Examples
      row). All 12 surface as `scenarios_pending` because no
      `@given/@when/@then` step-defs are implemented yet — exactly as
      AC5 requires.
  existing_suite_collection: 1005
  lint_mypy: 'ruff check + ruff format + mypy --strict all green'
---

# Task: wire pytest-bdd so `features/*.feature` actually execute

## Description

This is the follow-up surfaced by **TASK-OPS-BDDM-9** (in the GuardKit repo,
under `feat-bdd-runner-silent-bypass-fix`). After installing `pytest-bdd>=8.1`
into jarvis's dev group (commit [`46b9ce4`](#)), GuardKit's `bdd_runner` now
runs against `@task:`-tagged Gherkin scenarios — but jarvis's pytest config
prevents the scenarios from being collected:

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]      # ← only collects from tests/
```

When `bdd_runner.run_bdd_for_task('TASK-J002-008', jarvis)` is invoked it
returns a `BDDResult(scenarios_failed=1)` whose failure body reads:

```
pytest_runner_error: exit=4
ERROR: not found: …/jarvis/features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature
(no match in any of [<Dir feat-jarvis-002-core-tools-and-dispatch>])
```

i.e., pytest exits 4 (usage error) because the feature file isn't on a
`testpaths`-rooted collection path and there are no glue files in `tests/`
that bind to it via pytest-bdd's `@scenarios(...)` decorator (or the
`scenarios("…")` module-level call).

The full chain — `pytest-bdd installed` → `bdd_runner returns non-vacuous
BDDResult` — is now working, but the result is structurally a config gap
rather than real scenario outcomes.

## Acceptance Criteria

- [x] Running `python -m pytest path/to/features/...feature -v` (or whatever
      argv `bdd_runner` uses) collects and executes the `@task:`-tagged
      scenarios in `features/feat-jarvis-002-core-tools-and-dispatch/...`.
      **Verified** with the exact bdd_runner argv:
      `pytest --gherkin-terminal-reporter --junitxml=... -m task_TASK_J002_008 features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature`
      → exit=1, 12 scenarios collected, JUnit XML emitted.
- [x] `bdd_runner.run_bdd_for_task('TASK-J002-008', jarvis)` returns a
      `BDDResult` whose `scenarios_passed + scenarios_failed + scenarios_pending`
      equals the count of scenarios tagged with `@task:TASK-J002-008`.
      **Verified** by feeding the JUnit XML through `bdd_runner.parse_junit_xml`:
      `passed=0, failed=0, pending=12, total=12`. The 7 literal `@task:TASK-J002-008`
      tags expand to 12 pytest items because pytest-bdd produces one item per
      Examples row of a Scenario Outline (e.g. `read_file_enforces_the_one_megabyte_file_size_limit`
      has 4 Examples rows, `read_file_rejects_paths_that_evade_the_workspace_guard`
      has 3). The `total == count of @task: tags` invariant holds when
      counted at the pytest-bdd item level (which is the level
      `BDDResult.scenarios_*` operates on).
- [x] Pick the wiring style that fits jarvis best (no preference baked in).
      **Chose a third variant** of the suggested options: glue module
      **co-located with the .feature file** under `features/<slug>/test_<slug>.py`,
      plus a generic `features/conftest.py` collection bridge, instead of
      placing glue under `tests/bdd/`. Rationale:
      - Each feature directory is self-contained — `.feature` + glue + future
        step-defs live together (matches how `/feature-spec` already lays
        out feature directories).
      - The bridge in `features/conftest.py` is generic — any new
        feature dir just adds a `test_<slug>.py` next to its `.feature`,
        no `../..` relative paths, no central registry to maintain.
      - `testpaths` stays at `["tests"]` (no double-collection;
        see `pyproject.toml` comment for the trap that would otherwise hit).
- [x] After wiring, all 9 FEAT-J002 tagged scenarios that have step-defs run.
      **Verified** the bridge reaches every task tag in the feature file:
      e.g. `-m task_TASK_J002_013` → 15 items (9 outline rows × Examples
      expansion); `-m task_TASK_J002_008` → 12; full feature collection
      → 77 items. The 12 distinct task tags now showing in pyproject's
      `markers` list cover every `@task:TASK-J002-*` actually present
      (006/008/009/010/011/012/013/014/015/016/017/019).
- [x] Step-defs that aren't yet implemented appear as `scenarios_pending`
      (NOT `scenarios_failed`), confirming pytest-bdd's
      `StepDefinitionNotFoundError` is being correctly classified.
      **Verified** — all 12 collected items for J002-008 surface as
      `scenarios_pending=12, scenarios_failed=0`. Coach's
      `scenarios_failed == 0` approval rule passes.
- [x] Update `pyproject.toml` `[tool.pytest.ini_options]` and add a brief
      comment naming TASK-OPS-J002-BDD / TASK-OPS-BDDM-9.
      **Done** — see the `# testpaths is intentionally NOT extended ...`
      comment block plus the `markers = [...]` registration.

## Implementation Notes

- The `@task:` tag convention is registered as a marker by jarvis convention
  (see TASK-J002-023 / pyproject markers section if present). pytest-bdd
  reflects feature-file tags as marks, so the warning suppression already
  exists.
- pytest-bdd v8.x prefers the module-level `scenarios("...")` call; the
  decorator form `@scenarios(...)` was deprecated. Use the module-level form.
- The `bdd_runner` invokes pytest with the feature-file path AND a
  `-k @task:TASK-J002-XXX` filter (see
  `guardkit/orchestrator/quality_gates/bdd_runner.py:run_bdd_for_task`). The
  glue must therefore make pytest *able* to collect the file in the first
  place — afterwards `-k` narrows to the task-specific scenarios.
- A `tests/bdd/` subtree is structurally analogous to forge's layout —
  cross-check forge's pytest-bdd glue if convenient.
- Once wired, scenarios that fail real assertions (vs missing step-defs)
  should be filed as their own further follow-up tasks per the FEAT-BDDM
  pattern (do not remediate scenario logic in THIS task either).

## Notes

- Surfaced by GuardKit `TASK-OPS-BDDM-9` (cross-repo verification of the
  TASK-FIX-BDDM-1 silent-bypass fix). Direct `bdd_runner.run_bdd_for_task`
  invocation against jarvis on 2026-04-25 returned a non-vacuous
  `BDDResult(scenarios_failed=1)` whose payload is the `pytest_runner_error`
  shown above — proof the GuardKit fix is wired correctly; the remaining gap
  is jarvis-side pytest-bdd collection.
- The FEAT-J003 cancelled history (`docs/history/autobuild-FEAT-J003-history-cancelled.md`)
  also contains 11 occurrences of "pytest-bdd not importable" — same
  silent-bypass class. Resolving this task closes the structural gap for
  any future jarvis BDD verification.

## Implementation Summary (2026-04-26)

**Three things were missing**, not just one:

1. **No collector for `.feature` files.** pytest-bdd v8.1.0 does not register
   a `pytest_collect_file` hook for `.feature`. With the bdd_runner argv
   shape (`pytest -m TAG path/to/x.feature`), pytest exits 4 ("not found")
   because no collector claims the path. Fixed by adding a generic
   `pytest_collect_file` hook in `features/conftest.py` that returns a
   custom `_FeatureFile(pytest.File)` collector whose `path` matches the
   `.feature` argv (so pytest's args-resolver succeeds) and whose
   `collect()` delegates to a `pytest.Module` constructed for the sibling
   `test_<slug>.py` glue.

2. **Tag → marker name mismatch.** pytest-bdd's default
   `pytest_bdd_apply_tag` registers markers using the **literal** Gherkin
   tag (`task:TASK-J002-008`). bdd_runner sanitises the same tag for `-m`
   filtering (`task_TASK_J002_008` — `:` and `-` are not valid pytest
   marker identifier chars). Fixed by overriding `pytest_bdd_apply_tag`
   in `features/conftest.py` with the same sanitisation logic.

3. **No glue module to bind the `.feature` to pytest items.** Added
   `features/feat-jarvis-002-core-tools-and-dispatch/test_feat_jarvis_002_core_tools_and_dispatch.py`
   containing `scenarios("./feat-jarvis-002-core-tools-and-dispatch.feature")`.
   This is what actually generates the 77 scenario test functions; the
   bridge in (1) just routes pytest's collection to it.

**Files changed**:

- `features/conftest.py` (new) — collection bridge + tag sanitisation
- `features/feat-jarvis-002-core-tools-and-dispatch/test_feat_jarvis_002_core_tools_and_dispatch.py` (new) — pytest-bdd `scenarios()` glue
- `pyproject.toml` — registered marker names, added comment naming
  TASK-OPS-J002-BDD / TASK-OPS-BDDM-9, kept `testpaths = ["tests"]`
  (the comment explains why extending it would double-collect)

**Out of scope** (per FEAT-BDDM follow-up convention): implementing
`@given/@when/@then` step-def bodies. Each will surface as a
`scenarios_pending` failure — that is the BDD scaffold state, not a Coach-
blocking failure (`scenarios_failed == 0` still holds). When step-defs
get implemented and start producing real assertion failures, those will
be filed as their own follow-up tasks.

**Verification commands**:

```sh
# AC1+AC2: end-to-end bdd_runner shape for TASK-J002-008
.venv/bin/python -m pytest --gherkin-terminal-reporter \
    --junitxml=/tmp/jx.xml -m task_TASK_J002_008 \
    features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature
# → exit=1, "12 failed, 65 deselected"
# → BDDResult: passed=0, failed=0, pending=12 (Coach approval rule passes)

# AC4: bridge reaches every task tag (sample J002-013)
.venv/bin/python -m pytest \
    -m task_TASK_J002_013 \
    features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature \
    --collect-only -q
# → 15/77 tests collected (62 deselected)

# Regression: existing tests/ suite unaffected
.venv/bin/python -m pytest --collect-only
# → 1005 tests collected (no doubling, no features/ leakage)
```
