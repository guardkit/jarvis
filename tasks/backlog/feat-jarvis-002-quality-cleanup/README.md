# FEAT-J002F — FEAT-JARVIS-002 Quality & Hygiene Cleanup

> **Parent review:** [.claude/reviews/FEAT-JARVIS-002-review-report.md](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)
> **Parent feature:** [FEAT-JARVIS-002](../../../docs/design/FEAT-JARVIS-002/design.md) — already merged (`1da94ca`, 25 Apr 2026)
> **Generated:** 2026-04-26 via `/task-review FEAT-JARVIS-002` → `[I]mplement`
> **Status:** Backlog — ready to execute

## Problem

The 26 Apr `/task-review` of FEAT-JARVIS-002 confirmed the feature
ships to spec (1585/1585 tests green, all 9 tools wired, all 5 DDRs
honoured) but flagged two non-blocking remediation items the AutoBuild
cycle didn't pick up:

1. **Build-plan success criterion #9 fails** — Ruff reports 7 lints
   and mypy reports 7 errors across `src/jarvis/tools/`. All are
   stylistic / type-hygiene issues with no behavioural risk, but the
   "ruff + mypy clean on new modules" gate is still red.
2. **Kanban state is stale** — `.guardkit/features/FEAT-J002.yaml`
   says `status: completed`, but none of the 23 task files have moved
   to `tasks/completed/`. They sit duplicated across three
   directories: `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/`
   (21 files, missing 013/014), `tasks/backlog/TASK-J002-*` (13 loose
   copies), and `tasks/design_approved/TASK-J002-*` (10 files
   including the missing 013/014).

Neither blocks Phase 3 — both are workflow debt worth clearing
before FEAT-JARVIS-004 builds on top.

## Solution

Two small direct-mode subtasks, parallel-safe (no file conflicts):

- **TASK-J002F-001** — make `src/jarvis/tools/` ruff- and mypy-clean.
- **TASK-J002F-002** — reconcile and move the 23 J002 task files to
  `tasks/completed/`, deduplicating across the three current
  locations.

## Subtasks

| ID | Title | Mode | Wave | Est | Workspace |
|---|---|---|---|---|---|
| TASK-J002F-001 | Quality gates: ruff + mypy clean on `tools/` | direct | 1 | 30-45 min | `feat-jarvis-002-quality-cleanup-wave1-1` |
| TASK-J002F-002 | Kanban hygiene: move J002 task files to `tasks/completed/` | direct | 1 | 10-15 min | `feat-jarvis-002-quality-cleanup-wave1-2` |

## Acceptance

- `.venv/bin/ruff check src/jarvis/tools src/jarvis/config src/jarvis/agents/supervisor.py src/jarvis/prompts/supervisor_prompt.py` exits 0.
- `.venv/bin/mypy src/jarvis/tools` exits 0 (or any remaining warnings explicitly justified).
- Full pytest suite stays at **1585 passed, 2 skipped** with no new failures.
- `find tasks/backlog -name "TASK-J002-*"` returns nothing.
- `find tasks/design_approved -name "TASK-J002-*"` returns nothing.
- `find tasks/completed -name "TASK-J002-*"` returns 23 files (one per autobuild task).

## Out of Scope

- Any behavioural change to the J002 tool surface — this is hygiene
  only.
- Closing the two unverified build-plan success criteria (#5 manual
  `jarvis chat` and #6 `langgraph dev` smoke). Those are attended
  checkpoints that belong to the human, not a subtask.
- The build-plan footnote about `feature_yaml_path` field naming —
  one-line doc edit, do directly without a task.

## See Also

- [FEAT-JARVIS-002 review report](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md) — full findings
- [phase2-build-plan.md §Success Criteria](../../../docs/research/ideas/phase2-build-plan.md)
- [FEAT-J002.yaml](../../../.guardkit/features/FEAT-J002.yaml)
