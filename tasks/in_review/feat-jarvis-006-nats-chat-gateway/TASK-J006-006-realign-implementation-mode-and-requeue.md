---
id: TASK-J006-006
title: "Realign TASK-J006-003 / -004 implementation_mode and re-queue autobuild fail-run-2"
task_type: implementation
parent_review: TASK-REV-J6F1
feature_id: FEAT-JARVIS-006
wave: 0
implementation_mode: direct
complexity: 2
priority: high
status: in_review
created: 2026-05-12 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
dependencies: []
tags:
- autobuild
- feat-jarvis-006
- tactical-fix
- implementation-mode
related_tasks:
- TASK-REV-J6F1
- TASK-J006-003
- TASK-J006-004
source_review: TASK-REV-J6F1
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Realign TASK-J006-003 / -004 implementation_mode and re-queue autobuild fail-run-2

## Summary

Tactical unblock for FEAT-JARVIS-006 autobuild fail-run-1 (see review report
[`TASK-REV-J6F1`](../../../.claude/reviews/TASK-REV-J6F1-review-report.md)).
The chat handler implementation **is already on disk** in the autobuild worktree
(`chat_handler.py` 17.6 KB, `test_chat_handler.py` 26.7 KB, lint-clean, ~20
passing tests) — the failure was in the Coach's claim-audit, not the Player's
work. This task changes the autobuild orchestration knobs so fail-run-2 can
reach a green checkpoint without modifying any jarvis source code.

## Root cause (from TASK-REV-J6F1)

1. **Primary (Coach bug, jarvis cannot fix directly):** Coach claim-audit
   string-compares Player-reported absolute paths against worktree-relative
   `git status --porcelain` output → 100% false-positive "would not be staged"
   flags. Tracked separately in guardkit as `TASK-FIX-CAUD-J6F1`.
2. **Secondary (this task's lever):** TASK-J006-003's
   `task_work_results.json.agent_invocations_validation.status = "violation"`
   (Phase 3 / Implementation agent missing) caused
   `validation_results.quality_gates` to be `null`. With quality_gates null
   the Coach promoted the audit warning into a `must_fix` issue → feedback
   loop → `unrecoverable_stall`. TASK-J006-002 had the **same** absolute-path
   audit defect (10 honesty discrepancies) but quality_gates passed →
   warnings stayed warnings → approved.

## Strategy

Two interventions, applied together so the next autobuild run is robust to
both the known Bug-A and any orchestration-condition variance:

### Intervention A — Reduce J006-003 / J006-004 to `implementation_mode: direct`

TASK-J006-001 (the only Wave 2-equivalent task that passed cleanly with
valid `quality_gates.all_gates_passed: true`) used:

- `task_type: declarative`
- `implementation_mode: direct`

TASK-J006-003 currently uses `task_type: feature, implementation_mode:
task-work` and TASK-J006-004 uses the same. Switch both to:

- `implementation_mode: direct` (keep `task_type: feature`)

This makes the autobuild Player handle Phase 3 (Implementation) inline
instead of delegating to a sub-`task-work` invocation, eliminating the
`missing_phases: ["3"]` protocol violation that nulled out the quality-gate
validation block on fail-run-1.

**Caveat acknowledged:** TASK-J006-002 also had `implementation_mode:
task-work` yet quality_gates passed for it. The differentiator may be SDK
turn budget (J006-003 burned 56/160 SDK turns on turn 1 vs much less for
J006-002) or report-structure variance. If Intervention A alone is not
sufficient, Intervention B is the fallback.

### Intervention B — Player path-format directive (fallback / belt-and-braces)

Add a single line to the autobuild Player's system prompt or runtime config:

> "All file paths in `files_created`, `files_modified`, `files_authored`, and
> `tests_written` MUST be relative to the autobuild worktree root. Absolute
> paths starting with `/Users/`, `/home/`, or `/` will be rejected by the
> claim audit and prevent checkpoint approval."

This eliminates Bug-A's trigger condition entirely, regardless of whether
quality_gates pass. Find the right hook by checking
`.guardkit/autobuild/config.yaml`, `.guardkit/autobuild/player_system_prompt.md`,
or equivalent (location is guardkit-template-dependent).

## Acceptance Criteria

- [ ] AC-001: `TASK-J006-003-chat-handler.md` frontmatter
      `implementation_mode` changed from `task-work` → `direct`. Status reset
      from `blocked` → `backlog`. `autobuild_state` block cleared (or `current_turn`
      reset to 0 and `turns: []`).
- [ ] AC-002: `TASK-J006-004-serve-nats-cli.md` frontmatter
      `implementation_mode` changed from `task-work` → `direct`. Status confirmed
      `backlog`.
- [ ] AC-003: The autobuild Player prompt (or config equivalent) has the
      worktree-relative-paths directive added. Location of the change documented in
      the PR / completion note. If the directive can only live in guardkit, this
      AC is satisfied by linking the corresponding guardkit task and proceeding
      without Intervention B for this run.
- [ ] AC-004: A fresh autobuild fail-run-2 is queued (do **not** discard the
      existing worktree branch `autobuild/FEAT-JARVIS-006` — the Wave 1 work
      and J006-003's source files are preserved there and should be reused).
      Command and pre-flight steps documented below.
- [ ] AC-005: Fail-run-2's TASK-J006-003 turn 1 reaches `decision: approve`
      AND `coach_turn_1.json.honesty_verification.verified: true` (or
      `decision: approve` with audit issues remaining as warnings only).
- [ ] AC-006: TASK-J006-004 completes successfully in the same autobuild run
      (or its own subsequent run if dependency ordering forces it).
- [ ] AC-007: TASK-J006-005 remains `operator_handoff` (no automation
      expected) — out of scope of this task.

## Implementation Steps

1. **Snapshot current state.** `git -C .guardkit/worktrees/FEAT-JARVIS-006
   log --oneline -8` and capture; do not delete the worktree.
2. **Edit AC-001.** Update `TASK-J006-003-chat-handler.md` frontmatter:
   - `implementation_mode: direct`
   - `status: backlog`
   - clear or zero out `autobuild_state.current_turn` and `autobuild_state.turns`
   Re-read the file before / after to confirm clean YAML.
3. **Edit AC-002.** Same change pattern on `TASK-J006-004-serve-nats-cli.md`.
4. **Edit AC-003.** Locate the Player-prompt / autobuild-config knob (search
   `.guardkit/` and any sibling template files; the autobuild config likely
   lives at `.guardkit/autobuild/<feature>/config.yaml` or in a runtime
   template under the guardkit install). Add the worktree-relative-paths
   directive. If no jarvis-side knob exists, document that fact in the
   completion note and proceed (relying on Intervention A only).
5. **AC-004.** Re-launch the autobuild for FEAT-JARVIS-006. The exact
   command depends on the guardkit CLI in use (`guardkit autobuild run …` or
   `/feature-build FEAT-JARVIS-006` or equivalent). Pre-flight: confirm
   `git status --porcelain` in the main worktree is clean save for this
   task's own edits; confirm the autobuild worktree's branch tip is at
   `83bb69f1` (Turn 3 checkpoint) so J006-003's existing implementation is
   the starting point for fail-run-2.
6. **AC-005 / AC-006.** Monitor the new run. If turn 1 of J006-003 still
   reports `claim_audit` `must_fix` issues, the upstream guardkit fix
   (`TASK-FIX-CAUD-J6F1`) is the only remaining path forward — escalate.

## Out of Scope

- Modifying `chat_handler.py`, `test_chat_handler.py`, or any
  `src/jarvis/**` file. The implementation is complete; the failure was in
  the audit layer.
- Editing `.gitignore`. It is provably not the cause (TASK-REV-J6F1 F1).
- Fixing the upstream Coach claim-audit. Tracked separately in guardkit as
  `TASK-FIX-CAUD-J6F1`.

## Test Plan

- After AC-001/002 edits: `python -c "import yaml; yaml.safe_load(open('tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-003-chat-handler.md').read().split('---')[1])"` to confirm frontmatter is still valid YAML.
- After AC-004 re-queue: tail `events.jsonl` for the new fail-run-2 and confirm Turn 1 decision is `approve` (or that audit issues are warnings, not must_fix).
- Smoke test of the eventual merged result is deferred to TASK-J006-005.

## Implementation Notes

_Populated by `/task-work TASK-J006-006` on 2026-05-12._

### Changes applied

**AC-001 — TASK-J006-003 frontmatter (`tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-003-chat-handler.md`):**
- `implementation_mode: task-work` → `direct`
- `status: blocked` → `backlog`
- `autobuild_state` block: `current_turn: 3 → 0`, `turns: [3 entries] → []`, `started_at/last_updated` → `null`
- Added `autobuild_state.reset_for_fail_run_2: true` and `reset_note` pointing at `docs/history/autobuild-FEAT-JARVIS-006-fail-run-1.md` and `TASK-REV-J6F1` so the fail-run-1 turn history is recoverable.

**AC-002 — TASK-J006-004 frontmatter (`tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-004-serve-nats-cli.md`):**
- `implementation_mode: task-work` → `direct`
- `status` confirmed `backlog`.

**Beyond the stated ACs but required for the re-queue to actually take effect — `.guardkit/features/FEAT-JARVIS-006.yaml`:**
The autobuild orchestrator schedules from the feature YAML (not the task `.md` frontmatter), so analogous edits were applied there:
- Feature-level `status: failed` → `in_progress`.
- `tasks[id=TASK-J006-003]`: `status: failed → pending`, `implementation_mode: task-work → direct`, `turns_completed: 3 → 0`, `result: {…unrecoverable_stall…} → null`, `started_at`/`completed_at` → `null`.
- `tasks[id=TASK-J006-004]`: `implementation_mode: task-work → direct`.
- `execution.completed_at`: `'2026-05-11T23:15:47.814617' → null`, `tasks_failed: 1 → 0`, `last_updated` bumped to `2026-05-12T00:00:00.000000`.
- Added bookkeeping fields `execution.fail_run_1_archived_to: docs/history/autobuild-FEAT-JARVIS-006-fail-run-1.md` and `execution.reset_by: TASK-J006-006` so the orchestrator's history is auditable.

YAML validity of all three files confirmed via `yaml.safe_load`.

**AC-003 — Player path-format directive (Intervention B):**
No jarvis-side knob exists. The local `.guardkit/config.yaml` only carries Coach config (`autobuild.coach.test_execution: subprocess` — pinned by TASK-REV-E73C). The Player system prompt lives in the guardkit installation itself, not in jarvis. Per this task's AC-003 fallback clause ("If the directive can only live in guardkit, this AC is satisfied by linking the corresponding guardkit task and proceeding without Intervention B for this run"), AC-003 is satisfied by linking `TASK-FIX-CAUD-J6F1` (tracked in guardkit). Fail-run-2 therefore relies on Intervention A only.

### Pre-flight verification (per Implementation Steps §1)

```
git -C .guardkit/worktrees/FEAT-JARVIS-006 log --oneline -8
  83bb69f [guardkit-checkpoint] Turn 3 complete (tests: fail)   ← worktree tip — matches Step 5 expected
  d07ea11 [guardkit-checkpoint] Turn 2 complete (tests: fail)
  7ff3a20 [guardkit-checkpoint] Turn 1 complete (tests: fail)
  25685a3 [guardkit-checkpoint] Turn 1 complete (tests: pass)
  585783f [guardkit-checkpoint] Turn 1 complete (tests: pass)
  0d7f709 feature plan nats chat gateway
  …

git -C .guardkit/worktrees/FEAT-JARVIS-006 branch --show-current
  autobuild/FEAT-JARVIS-006

# Implementation files on disk (TASK-J006-003 work product, preserved per TASK-REV-J6F1):
  chat_handler.py            17 606 B  ≈ 17.6 KB   (review report claim ✓)
  test_chat_handler.py       26 745 B  ≈ 26.7 KB   (review report claim ✓)

# Only stale change in worktree:
  M .guardkit/autobuild/TASK-J006-003/checkpoints.json   (autobuild bookkeeping; harmless)
```

The worktree is primed: fail-run-2 picks up from `83bb69f` with the existing chat_handler implementation in place, and J006-003 starts a fresh Turn 1 because `autobuild_state.current_turn` is `0` in both the task file and the feature YAML.

### AC-004 — re-queue command (DOCUMENTED ONLY; not executed by this task)

The user will queue fail-run-2 via the slash command:

```
/feature-build FEAT-JARVIS-006
```

The launch is intentionally **not** invoked from within `/task-work` because (a) the autobuild run is a multi-turn, multi-minute side effect that warrants explicit user initiation, and (b) the slash command must be entered at the top-level conversation prompt.

### Open follow-up (out of this task's scope)

- **`TASK-FIX-CAUD-J6F1`** (guardkit-side): Coach claim-audit string-compares Player absolute paths against worktree-relative `git status --porcelain` output → 100 % false-positive "would not be staged" flags. Root cause of fail-run-1 per TASK-REV-J6F1. If fail-run-2 still trips claim-audit, this is the only remaining lever.
- **AC-005 / AC-006** can only be verified during/after fail-run-2; they are gating criteria for declaring this task fully done. Until then this task is `in_review` pending the next-run outcome.
- **AC-007** (TASK-J006-005 remains `operator_handoff`) requires no action — confirmed in the feature YAML (`TASK-J006-005.implementation_mode: direct, status: pending`, dependency on J006-004 unchanged).
