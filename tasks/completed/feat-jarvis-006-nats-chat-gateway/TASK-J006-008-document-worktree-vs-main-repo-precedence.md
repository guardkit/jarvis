---
id: TASK-J006-008
title: "Encode autobuild worktree vs main-repo source-of-truth precedence into the runbook"
task_type: docs
parent_review: TASK-REV-J6F2
feature_id: FEAT-JARVIS-006
wave: 2
implementation_mode: direct
complexity: 2
priority: low
status: completed
created: 2026-05-12 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
completed: 2026-05-12 00:00:00+00:00
previous_state: in_review
state_transition_reason: "All ACs met, runbook landed and discoverable"
dependencies:
- TASK-J006-007
tags:
- docs
- autobuild
- runbook
- lesson-learned
related_tasks:
- TASK-REV-J6F1
- TASK-REV-J6F2
- TASK-J006-006
source_review: TASK-REV-J6F2
test_results:
  status: not_applicable
  coverage: null
  last_run: null
  note: "docs-only task; verified via fresh-operator read and grep discoverability"
---

# Task: Encode the autobuild worktree vs main-repo precedence lesson

## Summary

TASK-J006-006 attempted to switch `implementation_mode: task-work → direct`
for TASK-J006-003 and TASK-J006-004 by editing the **main-repo** task `.md`
files and feature YAML. The edits did not take effect because the autobuild
orchestrator reads from the **worktree's** copies on branch
`autobuild/FEAT-JARVIS-006`, which the main-repo edits never reached.

Fail-run-2 succeeded anyway (for an unrelated reason — see TASK-REV-J6F2
§Q2 + §Cross-reference), but the next time a similar tactical reset is
required, the same trap waits.

Encode the precedence rule so future TASK-J006-006-shaped interventions
land where they need to.

## Why this is just docs

The mechanism is now well-understood; nothing in jarvis or guardkit needs
to change to make the *correct* path work — the operator just has to know
which path is correct. A short runbook note (10–20 lines) is sufficient.

## Acceptance Criteria

- [x] **AC-001** — Identify the canonical autobuild runbook in this
      repo. Candidates (search in order):
      1. `docs/autobuild-runbook.md`
      2. `docs/runbooks/autobuild.md`
      3. `.claude/rules/guidance/autobuild.md`
      4. If none exist, create `docs/runbooks/autobuild-orchestration.md`
         as a new file with this lesson as its first entry.

      None of (1)–(3) existed. Created `docs/runbooks/autobuild-orchestration.md`
      per option (4).

- [x] **AC-002** — Add a section titled "Editing task / feature state
      between autobuild runs" with at minimum these points:
      1. **Two sources of truth exist**: main repo (`.guardkit/features/`
         and `tasks/`) and worktree
         (`.guardkit/worktrees/<feature>/.guardkit/features/` and
         `.guardkit/worktrees/<feature>/tasks/`). The worktree is a
         separate git branch (`autobuild/<feature>`); main-repo edits do
         not propagate.
      2. **The orchestrator reads from the worktree**, not from main.
         When the log says `Mode: ... (explicit frontmatter override)`,
         the frontmatter it's reading is the worktree's copy.
      3. **State_bridge moves task files between `tasks/backlog/` and
         `tasks/design_approved/` mid-run** inside the worktree —
         attempting to edit a specific path can fail simply because the
         file isn't there at the moment of the edit.
      4. **Two safe lever options** for between-run tactical resets:
         - **Option A (surgical)**: Edit worktree files directly AND
           commit on `autobuild/<feature>` so the orchestrator's
           working-tree read matches what's on disk. Fragile — needs
           the file to be in the right state directory at edit time.
         - **Option B (clean slate)**: Run
           `guardkit autobuild feature <feature> --fresh` to discard the
           worktree and rebuild from the freshly-edited main-repo source.
           Robust but loses any in-progress autobuild work product.
      5. **Avoid editing only main-repo state** when you actually want
         the next autobuild run to see your change. Doing so is the
         TASK-J006-006 footgun.

- [x] **AC-003** — Cross-reference the two reviews and TASK-J006-006 as
      the historical example: `TASK-REV-J6F2 §Q2`, `TASK-J006-006
      "Changes applied" section`, and `TASK-REV-J6F1`.

- [x] **AC-004** — If `docs/autobuild-runbook.md` (or equivalent) does
      not exist, create it with this content as section 1, and add a
      "Status & ownership" section at the top stating: "Created from
      TASK-J006-008 lesson, 2026-05-12. Owner: jarvis maintainers. The
      authoritative description of the orchestration mechanism lives in
      guardkit; this file captures only the operational lessons jarvis
      has learned from running it."

## Out of Scope

- **Documenting the full autobuild lifecycle.** The authoritative
  description lives in guardkit. This task is one operational lesson, not
  a full runbook rewrite.
- **Proposing a guardkit-side fix** to make main-repo edits propagate.
  That's a separate guardkit task if it's worth doing at all (the
  current `--fresh` flag is the principled solution).
- **Reopening TASK-J006-006** to mechanically apply Intervention A.
  Per TASK-REV-J6F2 §Q4, J006-006 is mergeable as-is (AC-005 / AC-006
  met). The intervention not mechanically applying is documented in
  TASK-REV-J6F2 §Q2 — that's where the historical record lives.

## Test Plan

- Read the new section as a fresh operator: does it tell you, in <60
  seconds, what to do when you need to edit `implementation_mode`
  between autobuild runs?
- Search the docs tree for "worktree" and "implementation_mode" to
  confirm the new entry is discoverable.

## Implementation Notes

**Outcome**: Created `docs/runbooks/autobuild-orchestration.md` as the
canonical autobuild operational-lessons runbook. The TASK-J006-008
lesson is section 1: "Editing task / feature state between autobuild
runs".

**AC verification**:
- AC-001: candidates (1)–(3) absent → created
  `docs/runbooks/autobuild-orchestration.md` per fallback (4).
- AC-002: all 5 required points are present in section 1, under the
  required title. Section structure: rule → why this exists → mechanism
  (5 numbered points) → decision shortcut → cross-references.
- AC-003: cross-refs to `TASK-REV-J6F2 §Q2`, `TASK-J006-006 "Changes
  applied"`, and `TASK-REV-J6F1` are present. Also linked
  `TASK-REV-J6F2 §Q4` for the "mergeable as-is" reasoning per Out of
  Scope.
- AC-004: top-level "Status & ownership" section is present with the
  required attribution string.

**Test plan results**:
- 60-second fresh-operator read test: section 1 leads with the rule
  (edit worktree + commit, or `--fresh`), then explains why, then gives
  a decision shortcut. Operator can act in well under 60 seconds.
- Discoverability: `grep -c "worktree\|implementation_mode"` returned
  15 matches in the new file, so the entry is findable via the search
  terms a confused operator would actually use.

**Final runbook section** (verbatim copy of section 1 in
`docs/runbooks/autobuild-orchestration.md`):

> ## 1. Editing task / feature state between autobuild runs
>
> **Rule**: if you want the next autobuild run to see a change to
> `implementation_mode`, acceptance criteria, the feature YAML, or any
> other task/feature state, edit the **worktree** copy and commit it on
> `autobuild/<feature>` — or wipe the worktree with `--fresh` and let it
> re-seed from main. **Do not edit only the main-repo copy** and expect
> the next run to pick it up.
>
> ### Why this exists
>
> TASK-J006-006 attempted to switch
> `implementation_mode: task-work → direct` for TASK-J006-003 and
> TASK-J006-004 by editing the main-repo task `.md` files and the
> feature YAML. The edits never took effect because the orchestrator
> reads from the worktree (branch `autobuild/FEAT-JARVIS-006`), which
> the main-repo edits never reached. Fail-run-2 succeeded anyway for an
> unrelated reason (see TASK-REV-J6F2 §Q2 and §Cross-reference), but
> the trap is still loaded for the next operator.
>
> ### The mechanism
>
> 1. **Two sources of truth exist.** Main repo:
>    `.guardkit/features/<feature>.yaml` and
>    `tasks/{backlog,in_progress,…}/`. Worktree:
>    `.guardkit/worktrees/<feature>/.guardkit/features/<feature>.yaml`
>    and `.guardkit/worktrees/<feature>/tasks/…`. The worktree is a
>    separate git branch (`autobuild/<feature>`). Main-repo edits do
>    **not** propagate to it.
> 2. **The orchestrator reads from the worktree, not from main.** When
>    the autobuild log says `Mode: ... (explicit frontmatter override)`,
>    the frontmatter it is reading is the worktree's copy.
> 3. **`state_bridge` moves task files between `tasks/backlog/` and
>    `tasks/design_approved/` mid-run**, inside the worktree. An edit
>    that targets a specific path can fail simply because the file is
>    no longer at that path at the moment of the edit.
> 4. **Two safe lever options**: surgical (edit + commit on the
>    worktree branch) or clean slate (`guardkit autobuild feature
>    <feature> --fresh`).
> 5. **Avoid editing only main-repo state** — the TASK-J006-006
>    footgun.
