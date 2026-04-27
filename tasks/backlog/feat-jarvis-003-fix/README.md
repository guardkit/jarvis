# FEAT-JARVIS-003-FIX — Layer 2 Wiring + Quality-Gate Closeout

**Parent review:** [FEAT-JARVIS-003 review report](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md)
**Score driving this wave:** 80/100 — strong delivery with two substantive defects (F1 + F3) and one DX defect (F2).
**Approach:** AutoBuild parallel worktrees per FEAT-J002/J003 precedent.
**Execution:** `/feature-build FEAT-J003-FIX`

---

## Why this wave exists

The FEAT-JARVIS-003 architectural review (and a follow-up manual close-out attempt on 27 Apr) surfaced four follow-up items the AutoBuild cycle didn't catch because each fails *silently* in the dimension AutoBuild measures:

1. **F1** — `escalate_to_frontier` Layer 2 (executor assertion) is **dormant in production** because `lifecycle.startup` doesn't wire the resolver hooks DDR-014 designates. Tests inject hooks per-test, so the test suite passes despite the production gap.
2. **F2** — Module-import graph compilation requires `OPENAI_API_KEY`; `conftest.py` doesn't pre-seed a stub. Fresh-environment `pytest tests/` collection fails.
3. **F3** — Phase-2 close criterion #9 ("ruff + mypy clean on `src/jarvis/`") is unmet — 8 ruff + 9 mypy errors remain, including the `_emit_frontier_log` Literal that flags F1's gap structurally.
4. **F8** *(added 2026-04-27 during Phase-2 manual close-out)* — `langgraph.json` declares `./src/jarvis/agents/supervisor.py:graph` but `supervisor.py` exposes no module-level `graph` symbol. `langgraph dev` will fail with `ImportError`/`AttributeError` at startup. The TASK-J003-024 smoke test only checked file existence, not symbol resolution.

This wave closes all four. F4–F7 from the review remain forward-compat polish (deferred to FEAT-J004's design pass).

---

## Wave 1 — Build hygiene (parallel, direct mode)

| # | Task | Complexity | Mode |
|---|---|---|---|
| FIX-002 | [Clear all mypy + ruff drift in src/jarvis/](TASK-J003-FIX-002-clear-mypy-and-ruff-drift-in-src.md) | 3 | direct |
| FIX-003 | [Pre-seed OPENAI_API_KEY stub in tests/conftest.py](TASK-J003-FIX-003-pre-seed-openai-api-key-in-conftest.md) | 1 | direct |

Independent file scopes — fully parallel-safe. Conductor recommendation: 2 worktrees.

## Wave 2 — Constitutional gate restoration (TDD, gated on FIX-002)

| # | Task | Complexity | Mode | Status |
|---|---|---|---|---|
| FIX-001 | [Wire escalate_to_frontier Layer 2 hooks in lifecycle.build_app_state](../../in_review/feat-jarvis-003-fix/TASK-J003-FIX-001-wire-layer2-hooks-in-lifecycle-startup.md) | 4 | task-work (TDD) | ✅ landed (commits `431024f` red + `26fb128` green); awaiting Coach acceptance |

Gated on FIX-002 because FIX-001's TDD test exercises the Layer-2 path through to `_emit_frontier_log`, which mypy must accept as type-clean before merge.

## Wave 3 — Deployment surface fix (TDD, post-merge addendum)

| # | Task | Complexity | Mode | Status |
|---|---|---|---|---|
| FIX-004 | [Wire supervisor module-level graph symbol for langgraph CLI](TASK-J003-FIX-004-wire-supervisor-module-level-graph-for-langgraph-cli.md) | 3 | task-work (TDD) | backlog |

Surfaced 2026-04-27 during Phase-2 manual close-out; independent of Wave 1/2 (all wired hooks + clean gates remain).

---

## Acceptance gate (whole wave)

- [x] `mypy src/jarvis/` → 0 errors *(Wave 1 — FIX-002)*
- [x] `ruff check src/jarvis/` → 0 errors *(Wave 1 — FIX-002)*
- [x] `unset OPENAI_API_KEY && uv run pytest tests/` → ≥1585 passed *(Wave 1 — FIX-003; current count 1593)*
- [x] New integration test `test_lifecycle_layer2_wiring.py` passes; same test FAILS on `main` pre-fix *(Wave 2 — FIX-001; 5/5 green 27 Apr)*
- [x] All four FEAT-JARVIS-003 acceptance suites still green: routing E2E, role propagation, retired-roster regression, langgraph.json smoke
- [x] No new `# type: ignore` or `# noqa` without inline rule + justification
- [x] FEAT-JARVIS-003 review report's F1, F2, F3 are crossed off; F4–F7 documented as deferred to FEAT-J004 design
- [ ] **Wave 3:** `langgraph dev` starts both graphs without `ImportError`; symbol-resolution smoke test asserts both `:make_graph` and `:graph` resolve *(FIX-004 — pending)*

## Phase-2 close criteria recovered

After Waves 1+2 (landed 27 Apr), the build-plan's Phase-2 close-criteria table reads ✅ on every automated row plus the ambient-watcher rejection manual check. Two manual gates remain:

- **#5 `jarvis chat` UX** — blocked on llama-swap provisioning at `promaxgb10-41b1:9000` (separate infra workstream).
- **#6 `langgraph dev` real-server spin** — blocked on Wave 3 / FIX-004; will become satisfiable on M2 Max **without** the GB10 once FIX-004 lands.

---

## Next steps

1. `cd /Users/richardwoollcott/Projects/appmilla_github/jarvis`
2. Review [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) (dependency graph + integration contracts)
3. `/task-work TASK-J003-FIX-004` (single-task wave) OR fold into a `/feature-build FEAT-J003-FIX` re-run targeting just FIX-004
