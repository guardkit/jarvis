# FEAT-JARVIS-003-FIX — Layer 2 Wiring + Quality-Gate Closeout

**Parent review:** [FEAT-JARVIS-003 review report](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md)
**Score driving this wave:** 80/100 — strong delivery with two substantive defects (F1 + F3) and one DX defect (F2).
**Approach:** AutoBuild parallel worktrees per FEAT-J002/J003 precedent.
**Execution:** `/feature-build FEAT-J003-FIX`

---

## Why this wave exists

The FEAT-JARVIS-003 architectural review surfaced three follow-up items the AutoBuild cycle didn't catch because each fails *silently* in the dimension AutoBuild measures:

1. **F1** — `escalate_to_frontier` Layer 2 (executor assertion) is **dormant in production** because `lifecycle.startup` doesn't wire the resolver hooks DDR-014 designates. Tests inject hooks per-test, so the test suite passes despite the production gap.
2. **F2** — Module-import graph compilation requires `OPENAI_API_KEY`; `conftest.py` doesn't pre-seed a stub. Fresh-environment `pytest tests/` collection fails.
3. **F3** — Phase-2 close criterion #9 ("ruff + mypy clean on `src/jarvis/`") is unmet — 8 ruff + 9 mypy errors remain, including the `_emit_frontier_log` Literal that flags F1's gap structurally.

This wave closes all three with three task files. F4–F7 from the review are forward-compat polish (deferred to FEAT-J004's design pass).

---

## Wave 1 — Build hygiene (parallel, direct mode)

| # | Task | Complexity | Mode |
|---|---|---|---|
| FIX-002 | [Clear all mypy + ruff drift in src/jarvis/](TASK-J003-FIX-002-clear-mypy-and-ruff-drift-in-src.md) | 3 | direct |
| FIX-003 | [Pre-seed OPENAI_API_KEY stub in tests/conftest.py](TASK-J003-FIX-003-pre-seed-openai-api-key-in-conftest.md) | 1 | direct |

Independent file scopes — fully parallel-safe. Conductor recommendation: 2 worktrees.

## Wave 2 — Constitutional gate restoration (TDD, gated on FIX-002)

| # | Task | Complexity | Mode |
|---|---|---|---|
| FIX-001 | [Wire escalate_to_frontier Layer 2 hooks in lifecycle.build_app_state](TASK-J003-FIX-001-wire-layer2-hooks-in-lifecycle-startup.md) | 4 | task-work (TDD) |

Gated on FIX-002 because FIX-001's TDD test exercises the Layer-2 path through to `_emit_frontier_log`, which mypy must accept as type-clean before merge.

---

## Acceptance gate (whole wave)

- [ ] `mypy src/jarvis/` → 0 errors
- [ ] `ruff check src/jarvis/` → 0 errors
- [ ] `unset OPENAI_API_KEY && uv run pytest tests/` → ≥1585 passed (no regression)
- [ ] New integration test `test_lifecycle_layer2_wiring.py` passes; same test FAILS on `main` pre-fix (auditable two-commit history)
- [ ] All four FEAT-JARVIS-003 acceptance suites still green: routing E2E, role propagation, retired-roster regression, langgraph.json smoke
- [ ] No new `# type: ignore` or `# noqa` without inline rule + justification
- [ ] FEAT-JARVIS-003 review report's F1, F2, F3 are crossed off; F4–F7 documented as deferred to FEAT-J004 design

## Phase-2 close criteria recovered

After this wave, the build-plan's Phase-2 close-criteria table reads ✅ on every row except the three manual checks (`jarvis chat` round, `langgraph dev` spin, ambient-watcher rejection — none of which are testable until FEAT-J004 lands real adapters).

---

## Next steps

1. `cd /Users/richardwoollcott/Projects/appmilla_github/jarvis`
2. Review [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) (dependency graph + integration contracts)
3. `/feature-build FEAT-J003-FIX` — AutoBuild over the 3 subtasks
