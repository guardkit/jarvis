---
id: TASK-DOC-006
title: README.md Phase-3-close rewrite
task_type: documentation
parent_review: TASK-REV-C241
feature_id: FEAT-43DE
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
priority: high
tags:
  - documentation
  - readme
  - feat-jarvis-internal-001
  - phase-3-close
status: backlog
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-DOC-006 — README.md Phase-3-close rewrite

## Description

Rewrite the repo-root `README.md` (currently 131 LoC, declares
`Status: Pre-Architecture`, claims `341 passing` tests, suggests
`/system-arch` as the next step) to reflect Phase-3-close state.

Reality (per `docs/research/ideas/phase3-build-plan.md` Status Log):
Phase 1+2+FEAT-J004+FEAT-J005+TASK-J004-FIX-001 baseline confirmed
regression-clean on commit `7e29363`. **2105 passing tests / 1 skipped /
0 failed** at **92% line coverage**. `langgraph dev` boots both `jarvis`
and `jarvis_reasoner` graphs cleanly. Step 14 (end-to-end Forge
round-trip) is the Phase 3 close criterion.

This task runs in parallel with the five module-polish tasks (DOC-001..005)
because the README touches no Python source — there is no merge contention.

## Scope

**In scope:**
- Repo-root `README.md` (single file).

**Out of scope:**
- `CLAUDE.md` / `.claude/CLAUDE.md` (AI-agent-facing, separate convention).
- Any docstring under `src/jarvis/`.
- Any other markdown file in the repo.

## Acceptance Criteria

- [ ] First heading is a level-1 (`#`) heading containing the literal
      string "Jarvis" (Group A.5 / `@smoke`).
- [ ] File contains a `## Status` (or H2-equivalent) section that
      references "Phase 3" by name (ASSUM-006) and describes the
      Phase-3 close criterion as the end-to-end Forge round-trip
      (Group A.6 / `@smoke`).
- [ ] File contains a `## Quick Start` (or H2-equivalent) section that
      includes the canonical install command `uv sync` and the canonical
      runtime command `python -m langgraph dev` (Group A.7, ASSUM-013).
- [ ] File contains an `## Architecture` (or H2-equivalent) section that
      links (markdown link) to `docs/architecture/ARCHITECTURE.md`
      (Group A.8).
- [ ] File contains a `## Design Decisions` (or H2-equivalent) section
      that references the ADR directory `docs/architecture/decisions/`,
      the FEAT-JARVIS-004 DDR directory
      (`docs/design/FEAT-JARVIS-004/decisions/`), and the FEAT-JARVIS-005
      DDR directory (`docs/design/FEAT-JARVIS-005/decisions/`)
      (Group A.9, ASSUM-007).
- [ ] File does **not** contain the literal phrase `Pre-Architecture`
      (Group C.5 — guards against re-introducing stale phase info).
- [ ] File does **not** declare a hard-coded passing-test count below the
      current count (Group C.5 — current count is 2105; `341 passing`
      from the existing README must be removed or updated).
- [ ] All in-repo markdown links use **relative paths** — no absolute
      filesystem paths (Group D.4, ASSUM-009).
- [ ] File line count is ≥ 100 and ≤ 300 (Group B.1, ASSUM-004/005).

## Test Requirements

Minimal grep/seam tests only (per Context B Q3):

- [ ] `head -1 README.md | grep -E "^# .*Jarvis"` returns 1 match.
- [ ] `grep -E "^## Status" README.md` returns ≥ 1 match.
- [ ] `grep "Phase 3" README.md` returns ≥ 1 match.
- [ ] `grep -E "^## Quick Start" README.md` returns ≥ 1 match.
- [ ] `grep "uv sync" README.md` returns ≥ 1 match.
- [ ] `grep "python -m langgraph dev" README.md` returns ≥ 1 match.
- [ ] `grep -E "^## Architecture" README.md` returns ≥ 1 match.
- [ ] `grep "docs/architecture/ARCHITECTURE.md" README.md` returns ≥ 1 match.
- [ ] `grep -E "^## Design Decisions" README.md` returns ≥ 1 match.
- [ ] `grep "docs/architecture/decisions" README.md` returns ≥ 1 match.
- [ ] `grep "docs/design/FEAT-JARVIS-004/decisions" README.md` returns ≥ 1 match.
- [ ] `grep "docs/design/FEAT-JARVIS-005/decisions" README.md` returns ≥ 1 match.
- [ ] `grep -F "Pre-Architecture" README.md` returns no matches.
- [ ] `wc -l README.md` is between 100 and 300.
- [ ] `grep -nE '\]\(/' README.md` returns no matches (no leading-`/`
      absolute paths in markdown links).

Full pytest / mypy / ruff / `langgraph dev` regression deferred to
TASK-DOC-007.

## Implementation Notes

- The current `## Quickstart` section (lines 12–32) is mostly fine —
  the `uv sync` + `uv run …` content is canonical. Either rename to
  `## Quick Start` or keep `## Quickstart` and let the test grep on
  the more permissive `^## Quick ?[Ss]tart` pattern.
- Drop the `## The Full Pipeline` block (lines 88–95) and the
  `## Agent Fleet (8 Agents)` table (lines 97–111) — both are stale
  v0 fleet snapshots.
- Drop the `## Build Command` block (lines 126–131) — references
  `/system-arch` as the next step which is wrong for a Phase-3-close repo.
- The new `## Status` section should mirror the build-plan Status header
  in tone: declare Phase 3 close criterion (end-to-end Forge round-trip),
  acknowledge FEAT-JARVIS-004 + FEAT-JARVIS-005 are merged, and point at
  Step 14 as the gate.
- The new `## Design Decisions` section should be a navigation index, not
  a complete catalogue — three relative-path links to the ADR dir, the
  J004 DDR dir, and the J005 DDR dir is sufficient (per ASSUM-007).
- Target length: 180–250 LoC (the design ceiling is 300 per ASSUM-005,
  but leaving headroom is courteous).
