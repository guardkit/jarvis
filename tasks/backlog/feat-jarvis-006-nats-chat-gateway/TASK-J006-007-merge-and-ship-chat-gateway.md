---
id: TASK-J006-007
title: "Merge & ship NATS chat gateway: fix smoke gate, squash-merge autobuild/FEAT-JARVIS-006 → main"
task_type: implementation
parent_review: TASK-REV-J6F2
feature_id: FEAT-JARVIS-006
wave: 1
implementation_mode: direct
complexity: 3
priority: critical
status: backlog
created: 2026-05-12 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
dependencies: []
tags:
- autobuild
- feat-jarvis-006
- merge
- demo-critical
- chat-gateway
related_tasks:
- TASK-REV-J6F2
- TASK-REV-J6F1
- TASK-J006-003
- TASK-J006-004
- TASK-J006-005
- TASK-J006-006
source_review: TASK-REV-J6F2
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Merge & ship NATS chat gateway

## Summary

Land the autobuild output of fail-run-2 onto `main`. The chat gateway
implementation (`chat_handler.py` 411 lines + `cli/main.py` serve-nats
subcommand + 40 unit tests, 20 each side, Coach-approved with 100%
coverage on the CLI side) is correct and ready to merge — see
[`.claude/reviews/TASK-REV-J6F2-review-report.md`](../../../.claude/reviews/TASK-REV-J6F2-review-report.md)
§Q5 for the spot-check evidence and §Next Action for the merge plan this
task implements.

The only blocker is a broken smoke gate (`pytest --timeout=60` with no
`pytest-timeout` installed → exit 4), which is a one-line YAML fix.

This task is **demo-critical** — the 16 May 2026 DDD Southwest demo
depends on the chat gateway being on `main`.

## Why direct mode

Single-operator merge workflow. Each step is git/gh + targeted edits the
operator must visually confirm (diffs, branch state, test output). No
benefit from `/task-work` delegation; `direct` mode keeps the operator in
the loop at every reversible-vs-not boundary.

## Source-of-truth context

Today is 2026-05-12; demo is 2026-05-16 (4 days). Two merge prerequisites,
one merge, one post-merge validation. Estimated wall-clock <45 minutes.

Branch under merge: `autobuild/FEAT-JARVIS-006`, tip on the worktree at
`9bfca9e0 [guardkit-checkpoint] Turn 1 complete (tests: pass)`. Base:
`0d7f709 feature plan nats chat gateway`. Four checkpoint commits exist
between base and tip (three from fail-run-1, one from fail-run-2 J006-004
turn 1). Squash-merge collapses the noise.

## Acceptance Criteria

- [ ] **AC-001** — Smoke gate fixed. Edit `.guardkit/features/FEAT-JARVIS-006.yaml`
      `smoke_gates.command` to remove `--timeout=60` (one-line change;
      the 300s gate-level timeout is sufficient). Verify with
      `python -c "import yaml; yaml.safe_load(open('.guardkit/features/FEAT-JARVIS-006.yaml').read())"`
      → no exception.

- [ ] **AC-002** — Smoke gate validated locally. From the **worktree**:
      ```
      cd .guardkit/worktrees/FEAT-JARVIS-006
      .venv/bin/python -m pytest tests/ -x -q
      ```
      Expected: exit 0. If failures, STOP and investigate — they will
      indicate a real regression that the per-task gates missed (this
      review found none, so failures here would be a surprise).

- [ ] **AC-003** — Branch diff inspected. From the main repo:
      ```
      git fetch
      git diff main..autobuild/FEAT-JARVIS-006 --stat
      git log main..autobuild/FEAT-JARVIS-006 --oneline
      ```
      Expected files in diff: `src/jarvis/infrastructure/chat_handler.py`,
      `src/jarvis/cli/main.py`, `src/jarvis/sessions/manager.py`,
      `src/jarvis/shared/constants.py`, `tests/unit/infrastructure/test_chat_handler.py`,
      `tests/test_serve_nats_cli.py`, `tests/test_shared.py`,
      `.guardkit/features/FEAT-JARVIS-006.yaml`,
      `tasks/design_approved/TASK-J006-00{3,4}-*.md`. Anything else
      (especially `.guardkit-git.lock`, `.coverage`, `.pytest_cache/`,
      `.ruff_cache/`, autobuild bookkeeping JSONs) is bookkeeping — flag
      in the squash commit body or drop with `git restore --staged`.

- [ ] **AC-004** — Squash-merge executed.
      ```
      git switch main
      git merge --squash autobuild/FEAT-JARVIS-006
      # review staged diff one more time
      git diff --staged --stat
      git commit -m "$(cat <<'EOF'
      FEAT-JARVIS-006: NATS chat gateway (chat_handler + serve-nats CLI)

      Implements dual-publish chat handler (Bug #1) and forge notification
      drain (Risk #3) on agents.command.jarvis, plus the serve-nats CLI
      subcommand with SIGINT/SIGTERM teardown sequence
      (unsubscribe → drain in-flight → cancel heartbeat → deregister).

      40 unit tests passing (20 chat_handler, 20 serve-nats CLI),
      100% coverage on the CLI side.

      Closes TASK-J006-003, TASK-J006-004.
      Implements TASK-J006-007 (merge step from review TASK-REV-J6F2).

      DEMO-CRITICAL for 16 May 2026 DDD Southwest.

      Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
      EOF
      )"
      ```

- [ ] **AC-005** — Full project test suite passes from main repo (not
      worktree).
      ```
      cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
      .venv/bin/python -m pytest tests/ -x -q
      ```
      Expected: exit 0. This catches path/import drift that the
      worktree-isolated environment might have hidden.

- [ ] **AC-006** — Task & feature state updated.
      - `.guardkit/features/FEAT-JARVIS-006.yaml` `status: failed → in_progress`
        (J006-005 still pending operator handoff; do NOT mark `completed`).
      - `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-003-chat-handler.md`
        `status: in_review → completed`.
      - `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-004-serve-nats-cli.md`
        `status: in_review → completed`.
      - `tasks/in_review/feat-jarvis-006-nats-chat-gateway/TASK-J006-006-realign-implementation-mode-and-requeue.md`
        → move to `tasks/completed/feat-jarvis-006-nats-chat-gateway/`,
        `status: in_review → completed`. AC-005/006 of that task were met
        per TASK-REV-J6F2 §Q4.
      - This task (TASK-J006-007) `status: backlog → completed`.

- [ ] **AC-007** — Worktree cleanup. Do NOT delete the worktree until
      TASK-J006-005 (operator-handoff demo verification) has completed —
      the worktree is a fallback if something is wrong on `main`. After
      J006-005 is green, run `guardkit autobuild archive FEAT-JARVIS-006`
      (or equivalent) to clean up.

## Out of Scope

- **TASK-J006-005** (operator-handoff live Open WebUI demo verification).
  Runs after this merge; the review report calls out the 4-day demo
  margin. Schedule separately.
- **TASK-J006-008** (the lesson-encoding follow-up; encode the
  worktree-vs-main-repo source-of-truth split into the autobuild runbook).
  Independent and non-blocking; routed by TASK-REV-J6F2 AC-008.
- **Fixing the upstream Coach `agent_invocations_validation` rigor** — the
  current "outcome gates passed → advisory" heuristic is reasonable but
  undocumented; lives in guardkit.
- **Touching any `src/jarvis/**` file**. The implementation is done.

## Test Plan

Verification is by AC, not by writing new tests:
- AC-001 YAML validity (one-shot `yaml.safe_load`).
- AC-002 pytest from worktree: exit 0.
- AC-003 git diff inspection (visual).
- AC-005 pytest from main: exit 0.
- AC-006 status file edits visible on disk + via git log.

If AC-002 or AC-005 fail, STOP — do not push partial state. Investigate
which test is failing and whether it's pre-existing on `main` (run
`pytest` on `main` before merging to establish baseline).

## Risk Notes

- **Squash vs merge-commit**: Use squash. The four guardkit-checkpoint
  commits on the branch are noise (Turn 1 attempt 1 / Turn 1 attempt 2 /
  Turn 2 / Turn 3 from fail-run-1, plus J006-004 turn 1 from
  fail-run-2). Squash collapses them into a single semantic commit on
  `main`.
- **Do NOT force-push**. The squash-merge produces a normal fast-forward
  commit on `main`; no force needed.
- **Pre-commit hooks**: If any hooks fail at AC-004, create a NEW commit
  to fix — do NOT `--amend` (per CLAUDE.md git-safety protocol).
- **TASK-J006-005**: After AC-006, the feature YAML's
  `tasks[id=TASK-J006-005].status` should remain `pending` and
  `implementation_mode: direct + operator_handoff`. Do not touch it.

## Implementation Notes

_(Populated by the operator running this task. Suggested structure:
record the actual commit SHA produced by AC-004, the full-suite test
output summary from AC-005, and the git log of the post-merge `main`
tip.)_
