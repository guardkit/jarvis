# Phase 1 Review Fixes

Remediation subtasks generated from the post-build review of **FEAT-JARVIS-001** (Project Scaffolding, Supervisor Skeleton & Session Lifecycle).

## Problem

FEAT-JARVIS-001 delivered the full 11-task Phase 1 scaffold (supervisor factory, thread-per-session `SessionManager`, `jarvis` CLI, structlog infra, shared primitives, 340 passing tests). The post-build review ([.claude/reviews/FEAT-JARVIS-001-review-report.md](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md)) confirmed every load-bearing contract is correctly implemented — but surfaced two issues that block the Phase 1 Success Criteria as written, plus two medium-severity bootstrap cleanups and one cosmetic batch.

## Outcome

After these four fix tasks land, FEAT-JARVIS-001 meets every Phase 1 Success Criterion in [docs/research/ideas/phase1-build-plan.md](../../../docs/research/ideas/phase1-build-plan.md), and the bootstrap path is tight enough that FEAT-002 (dispatch tools) and FEAT-003 (async subagents) can extend `AppState` without stumbling over stale `Any`-typed fields or logging-ordering gotchas.

## Subtasks

| # | Task | Wave | Fixes review finding | Mode | Est. |
|---|---|---|---|---|---|
| 1 | [FIX-001](TASK-J001-FIX-001-mypy-clean-src.md) — Fix mypy type errors in src/jarvis/ | 1 | F1 (HIGH) | direct | 15 min |
| 2 | [FIX-002](TASK-J001-FIX-002-python-version-pin.md) — Pin Python 3.12 end-to-end; stabilise subprocess test | 1 | F2 (HIGH) | direct | 10 min |
| 3 | [FIX-003](TASK-J001-FIX-003-bootstrap-refactor.md) — Tighten AppState typing; move logging to CLI entry | 2 | F3 + F4 (MEDIUM) | task-work | 35 min |
| 4 | [FIX-004](TASK-J001-FIX-004-cosmetic-polish.md) — correlation_id docstring, HumanMessage hoist, ruff-fix tests/ | 2 | F5 + F6 + F8 (LOW) | direct | 15 min |

**Total effort: ~75 min. Wall-clock with parallel waves: ~50 min.**

## Execution order

See [IMPLEMENTATION-GUIDE.md §5](IMPLEMENTATION-GUIDE.md#5-ordered-execution-recipe) for the full recipe. TL;DR:

1. **Wave 1** — FIX-001 ∥ FIX-002 (parallel; no file conflicts)
2. **Regression gate** — `pytest` / `ruff` / `mypy` all green on `src/jarvis/`
3. **Wave 2** — FIX-003 ∥ FIX-004 (parallel after Wave 1 lands)
4. **Final gate** — `pytest` (341/341), `ruff` clean on src/ *and* tests/, `mypy` clean on src/

## Not in scope

- Review finding **F7** (SessionManager concurrency model) — deferred to FEAT-JARVIS-006 (Telegram adapter), which is the first consumer that stresses multi-task-per-session.
- Any change to ASSUM-* / DDR-* pinned behaviours — all already implemented correctly.
- Any new BDD scenarios; the 35 existing scenarios cover the contract and no new behaviour is being added.
- Adopting a ULID library for `correlation_id` — FEAT-JARVIS-004 owns that decision.

## Provenance

- **Parent feature:** [FEAT-JARVIS-001](../../../.guardkit/features/FEAT-JARVIS-001.yaml)
- **Parent review:** [TASK-REV-J001](../../in_review/TASK-REV-J001-plan-project-scaffolding-supervisor-sessions.md)
- **Review report:** [.claude/reviews/FEAT-JARVIS-001-review-report.md](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md)
- **Build plan reference:** [phase1-build-plan.md §Step 6](../../../docs/research/ideas/phase1-build-plan.md) — "`/task-review FEAT-JARVIS-001` / Review gate. Fix anything flagged."
