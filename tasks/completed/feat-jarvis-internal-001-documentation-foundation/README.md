# FEAT-JARVIS-INTERNAL-001 Documentation Foundation

**Feature ID**: `FEAT-43DE`
**Status**: planned (backlog)
**Parent review**: [`TASK-REV-C241`](../../completed/TASK-REV-C241-plan-feat-jarvis-internal-001-documentation-foundation.md)
**Phase 3 alignment**: Step 13 → Step 14 close criterion in
[`docs/research/ideas/phase3-build-plan.md`](../../../docs/research/ideas/phase3-build-plan.md)

## Problem

Two distinct documentation gaps need to close before Phase 3's end-to-end
Forge round-trip (Step 14):

1. The five FEAT-J004/J005 infrastructure module docstrings under
   `src/jarvis/infrastructure/` carry inconsistent shape and TASK-Jxxx
   GuardKit-bookkeeping leakage from the autobuild process.
2. The repo-root `README.md` is stale — declares `Status: Pre-Architecture`,
   suggests `/system-arch` as the next step, and claims `341 passing` tests
   when reality is 2105 at 92% coverage on commit `7e29363`.

Both surfaces are reader-facing — the README for humans landing on the
repo, and the module docstrings for any reader (human or agent) navigating
the FEAT-J004/J005 implementation.

## Solution

**Approach 1 (recommended)**: Wave-based parallel polish. Six wave-1 tasks
each touch a single file (5 modules + README). One sequential wave-2 task
verifies cross-cutting invariants (tool-docstring byte-equality,
pytest/mypy/coverage, both langgraph graphs compile).

This shape mirrors the FEAT-JARVIS-004 / FEAT-JARVIS-005 wave conventions
that Rich has been using throughout Phase 3. Aggregate complexity is low
(≈ 2.5/10 per task), wall-clock is 60–90 min, and each task has a clean,
mechanically verifiable acceptance set (grep / `wc -l` / AST `get_docstring`).

## Subtasks (7 total)

| # | Task | Wave | File | Complexity |
|---|---|---|---|---|
| 1 | [TASK-DOC-001](TASK-DOC-001-nats-client-docstring-polish.md) | 1 | `nats_client.py` | 2 |
| 2 | [TASK-DOC-002](TASK-DOC-002-fleet-registration-docstring-polish.md) | 1 | `fleet_registration.py` | 2 |
| 3 | [TASK-DOC-003](TASK-DOC-003-capabilities-registry-docstring-polish.md) | 1 | `capabilities_registry.py` (preserve DDR-021 / ADR-ARCH-017) | 3 |
| 4 | [TASK-DOC-004](TASK-DOC-004-routing-history-docstring-polish.md) | 1 | `routing_history.py` | 2 |
| 5 | [TASK-DOC-005](TASK-DOC-005-forge-notifications-docstring-polish.md) | 1 | `forge_notifications.py` (8 TASK-Jxxx hits) | 3 |
| 6 | [TASK-DOC-006](TASK-DOC-006-readme-rewrite.md) | 1 | `README.md` rewrite | 3 |
| 7 | [TASK-DOC-007](TASK-DOC-007-invariant-and-regression-gate.md) | 2 | invariant + regression gate | 3 |

**Wave 1** (parallel, 6 tasks, ≈ 30 min): all module-docstring polishes
plus the README rewrite.
**Wave 2** (sequential, 1 task, ≈ 30 min): cross-cutting invariant +
regression gate.

## Hard out-of-scope (FEAT-J004/J005 invariant)

- `src/jarvis/tools/*.py` `@tool`-decorated docstrings must remain
  **byte-identical** to `main` HEAD prior to this feature. The reasoning
  model has been routing against these since Phase 2; touching them is
  a behavioural confound during the Step-14 transport validator. Verified
  by TASK-DOC-007 against `general.py`, `capabilities.py`, `dispatch.py`.
- Any executable Python (no refactors, no type-annotation changes).
- `CLAUDE.md` / `.claude/CLAUDE.md` (AI-agent-facing, separate convention).

## Where to start

1. Read the [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) for the
   full wave structure, mermaid data-flow diagram, and scenario→task
   mapping.
2. Read [TASK-REV-C241's review report](../../../.claude/reviews/TASK-REV-C241-review-report.md)
   for the decision rationale (why Option 1 over Options 2 and 3).
3. Run wave 1 in parallel (Conductor or sequential depending on autobuild
   backend), then run TASK-DOC-007 to close.

## Source-of-truth

- **Feature YAML** (autobuild driver): `.guardkit/features/FEAT-43DE.yaml`
- **Gherkin scenarios**: [`features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation.feature`](../../../features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation.feature)
- **Assumptions**: [`features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml`](../../../features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml)
- **Decision review**: [`.claude/reviews/TASK-REV-C241-review-report.md`](../../../.claude/reviews/TASK-REV-C241-review-report.md)
- **Build plan context**: [`docs/research/ideas/phase3-build-plan.md`](../../../docs/research/ideas/phase3-build-plan.md) (Steps 13–14)
