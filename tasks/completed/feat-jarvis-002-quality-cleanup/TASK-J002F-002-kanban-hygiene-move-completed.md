---
id: TASK-J002F-002
title: Kanban hygiene - move J002 task files to tasks/completed
task_type: chore
status: completed
created: 2026-04-26 00:00:00+00:00
updated: '2026-04-27T00:00:00+00:00'
completed: '2026-04-27T00:00:00+00:00'
priority: low
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 15
dependencies: []
parent_review: FEAT-JARVIS-002-review-2026-04-26
feature_id: FEAT-J002F
tags:
- phase-2
- jarvis
- feat-jarvis-002
- kanban
- post-review-fix
scenarios_covered:
- All 23 J002 task files live under tasks/completed/feat-jarvis-002-core-tools-and-dispatch
- No J002 task files remain in tasks/backlog/ or tasks/design_approved/
- Each canonical task file has status=completed and a completed_at timestamp
test_results:
  status: pass
  coverage: null
  last_run: 2026-04-27
  acceptance_checks: "backlog clean (0 J002 files); design_approved clean (0 J002 files); completed has 23 J002 files"
---
# Kanban hygiene: move J002 task files to tasks/completed

**Feature:** FEAT-J002F "FEAT-JARVIS-002 Quality & Hygiene Cleanup"
**Wave:** 1 | **Mode:** direct | **Complexity:** 1/10 | **Est.:** 10-15 min
**Parent review:** [.claude/reviews/FEAT-JARVIS-002-review-report.md §4.3](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)

## Description

`.guardkit/features/FEAT-J002.yaml` says `status: completed` and
AutoBuild closed cleanly on 25 Apr (commit `1da94ca`), but the 23
task files never moved to `tasks/completed/`. They are scattered
across three directories with overlap and gaps:

| Location | Count | Notes |
|---|---|---|
| `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/` | 21 | Canonical subfolder; **missing** TASK-J002-013, TASK-J002-014 |
| `tasks/backlog/TASK-J002-*` | 13 | Loose duplicates at top of backlog |
| `tasks/design_approved/TASK-J002-*` | 10 | Includes the missing 013, 014 |

Result: future `/task-status FEAT-J002` queries return wrong state,
and there are at most three copies of the same task ID floating
around.

## Approach

1. **Inventory** — list all J002 task files across the three
   locations, group by ID:

   ```bash
   for id in $(seq -w 1 23); do
     echo "TASK-J002-$id:"
     find tasks -name "TASK-J002-$id-*.md" -type f
   done
   ```

2. **Pick the canonical copy per ID** — prefer the one with
   populated `autobuild_state.turns` and `status: in_review` (this
   is the version `/task-work` wrote during the AutoBuild cycle).
   If only one copy exists, that is canonical by default.

3. **Update frontmatter** of each canonical copy:
   - `status: completed`
   - `completed_at: <timestamp>` — pull the value from the matching
     entry in `.guardkit/features/FEAT-J002.yaml`'s `tasks` array
     (each task there has `completed_at` populated).

4. **Move** with `git mv` to
   `tasks/completed/feat-jarvis-002-core-tools-and-dispatch/`,
   creating that directory if needed.

5. **Delete** the duplicate copies with `git rm`.

6. **Sanity check** that the moved files' relative paths to README,
   IMPLEMENTATION-GUIDE, and any sibling markdown still resolve.
   The completed feature subfolder will need its own `README.md` /
   `IMPLEMENTATION-GUIDE.md` copied too if they were in
   `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/` (move
   them over).

## Constraints

- **Use git, not raw `mv`/`rm`.** History matters — `git mv`
  preserves the rename trail.
- **Do not alter task body content** — only the two frontmatter
  fields above. Keep the AutoBuild player/coach turn history intact.
- **Do not move TASK-J002F-001 or TASK-J002F-002 themselves.** Those
  files (and this whole `feat-jarvis-002-quality-cleanup/` subfolder)
  stay in backlog until they themselves complete.

## Acceptance Criteria

```bash
test $(find tasks/backlog -name "TASK-J002-[0-9]*" 2>/dev/null | wc -l) -eq 0 && echo "backlog clean"
test $(find tasks/design_approved -name "TASK-J002-*" 2>/dev/null | wc -l) -eq 0 && echo "design_approved clean"
test $(find tasks/completed -name "TASK-J002-*" 2>/dev/null | wc -l) -eq 23 && echo "completed has 23 files"
```

All three lines must print their success message. The pattern
`TASK-J002-[0-9]*` deliberately excludes `TASK-J002F-*` (this
feature's own files).

Spot-check three canonical files for `status: completed` +
`completed_at: 2026-04-25T...` in frontmatter.

## Out of Scope

- Any code change.
- Any change to `.guardkit/features/FEAT-J002.yaml` — it is already
  correct.
- Cleanup of FEAT-J003 task files (different feature, different
  review).

## See Also

- [Review report §4.3](../../../.claude/reviews/FEAT-JARVIS-002-review-report.md)
- [.guardkit/features/FEAT-J002.yaml](../../../.guardkit/features/FEAT-J002.yaml) — source of `completed_at` timestamps
