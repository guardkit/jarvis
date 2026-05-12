# Autobuild orchestration — jarvis operational lessons

## Status & ownership

Created from TASK-J006-008 lesson, 2026-05-12. Owner: jarvis maintainers.
The authoritative description of the orchestration mechanism lives in
guardkit; this file captures only the operational lessons jarvis has
learned from running it.

Add new sections as new lessons land. Each section should be a single
self-contained operational rule plus enough context to explain *why* it
exists, with cross-references to the originating review/task.

---

## 1. Editing task / feature state between autobuild runs

**Rule**: if you want the next autobuild run to see a change to
`implementation_mode`, acceptance criteria, the feature YAML, or any
other task/feature state, edit the **worktree** copy and commit it on
`autobuild/<feature>` — or wipe the worktree with `--fresh` and let it
re-seed from main. **Do not edit only the main-repo copy** and expect
the next run to pick it up.

### Why this exists

TASK-J006-006 attempted to switch
`implementation_mode: task-work → direct` for TASK-J006-003 and
TASK-J006-004 by editing the main-repo task `.md` files and the feature
YAML. The edits never took effect because the orchestrator reads from
the worktree (branch `autobuild/FEAT-JARVIS-006`), which the main-repo
edits never reached. Fail-run-2 succeeded anyway for an unrelated
reason (see `.claude/reviews/TASK-REV-J6F2-review-report.md` §Q2 and
§Cross-reference), but the trap is still loaded for the next operator.

### The mechanism

1. **Two sources of truth exist.** Both directories carry task and
   feature state:
   - **Main repo**: `.guardkit/features/<feature>.yaml` and
     `tasks/{backlog,in_progress,in_review,…}/`.
   - **Worktree**:
     `.guardkit/worktrees/<feature>/.guardkit/features/<feature>.yaml`
     and `.guardkit/worktrees/<feature>/tasks/…`.

   The worktree is a separate git branch (`autobuild/<feature>`).
   Main-repo edits do **not** propagate to it.

2. **The orchestrator reads from the worktree, not from main.** When
   the autobuild log says `Mode: ... (explicit frontmatter override)`,
   the frontmatter it is reading is the worktree's copy. Treat the
   worktree as the live state.

3. **`state_bridge` moves task files between `tasks/backlog/` and
   `tasks/design_approved/` mid-run**, inside the worktree. An edit
   that targets a specific path can fail simply because the file is no
   longer at that path at the moment of the edit — it moved.

4. **Two safe lever options** for between-run tactical resets:

   - **Option A — surgical**: edit the worktree files directly, then
     `git add` + `git commit` on `autobuild/<feature>` so the
     orchestrator's working-tree read matches what is on disk. Fragile:
     requires the file to be in the right state directory at the
     moment you edit it (see point 3).
   - **Option B — clean slate**: run
     `guardkit autobuild feature <feature> --fresh`. This discards the
     worktree and rebuilds from the freshly-edited main-repo source.
     Robust, but loses any in-progress autobuild work product (Player
     turns, partial diffs, etc.).

5. **Avoid editing only main-repo state** when you actually want the
   next autobuild run to see your change. Doing so is the
   TASK-J006-006 footgun.

### Decision shortcut

- "I want a small, targeted change and I don't mind reasoning about
  which state directory the file is in right now" → Option A.
- "I want to be certain the next run starts from my edits, and I can
  afford to lose the current worktree work product" → Option B.
- "I edited main-repo only and the next run still sees the old
  state" → you hit the footgun. Apply Option A or Option B.

### Cross-references

- `.claude/reviews/TASK-REV-J6F2-review-report.md` §Q2 — mechanism
  diagnosis and historical record of the intervention not taking
  effect.
- `tasks/in_review/feat-jarvis-006-nats-chat-gateway/TASK-J006-006-realign-implementation-mode-and-requeue.md`
  "Changes applied" section — the edits that were made to main-repo
  copies and did not propagate.
- `.claude/reviews/TASK-REV-J6F1-review-report.md` — fail-run-1
  analysis, prior context for why the mode realignment was attempted.
- `TASK-REV-J6F2 §Q4` — confirms TASK-J006-006 is mergeable as-is
  despite Intervention A not mechanically landing; the historical
  record lives in the review, not in a reopened task.
