---
id: TASK-REV-J6F2
title: "Analyse autobuild FEAT-JARVIS-006 fail-run-2: per-task `approve` vs feature `failed` discrepancy, and whether TASK-J006-006 Intervention A actually applied"
task_type: review
decision_required: true
feature_id: FEAT-JARVIS-006
complexity: 4
priority: high
status: review_complete
review_results:
  mode: root-cause
  depth: standard
  decision: merge
  findings_count: 5
  recommendations_count: 4
  report_path: .claude/reviews/TASK-REV-J6F2-review-report.md
  completed_at: 2026-05-12T00:00:00Z
created: 2026-05-12 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
dependencies: []
tags:
- review
- autobuild
- feat-jarvis-006
- analysis
- fail-run-2
related_tasks:
- TASK-REV-J6F1
- TASK-J006-006
- TASK-J006-003
- TASK-J006-004
- TASK-FIX-CAUD-J6F1
inputs:
- path: docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md
  description: Full autobuild transcript of fail-run-2 (~92 KB, captured 2026-05-12 09:46 → 11:14 local; `guardkit autobuild feature FEAT-JARVIS-006 --verbose --resume`)
- path: .guardkit/features/FEAT-JARVIS-006.yaml
  description: Post-run feature state (feature.status=`failed` but tasks 1–4 all `completed`; J006-005 still `pending` operator_handoff)
- path: tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-003-chat-handler.md
  description: Post-run task file (autobuild_state.turns[0].decision=`approve`, status=`in_review`, implementation_mode=`direct` per TASK-J006-006 reset)
- path: tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-004-serve-nats-cli.md
  description: Post-run task file (autobuild_state.turns[0].decision=`approve`, status=`in_review`, implementation_mode=`direct` per TASK-J006-006 reset)
- path: .claude/reviews/TASK-REV-J6F1-review-report.md
  description: Fail-run-1 review report (root-cause analysis of the prior run; this review's baseline for comparison)
- path: tasks/in_review/feat-jarvis-006-nats-chat-gateway/TASK-J006-006-realign-implementation-mode-and-requeue.md
  description: The tactical-fix task whose Intervention A (implementation_mode=task-work → direct) this run was meant to validate
- path: .guardkit/autobuild/TASK-J006-003/
  description: Per-turn checkpoint and player/coach artefacts from fail-run-2
- path: .guardkit/autobuild/TASK-J006-004/
  description: Per-turn checkpoint and player/coach artefacts from fail-run-2
- path: .guardkit/worktrees/FEAT-JARVIS-006/
  description: Autobuild worktree (branch `autobuild/FEAT-JARVIS-006`) — contains the actual implementation that the run produced
---

# Review Task: Analyse autobuild FEAT-JARVIS-006 fail-run-2

## Summary

A second autobuild run for `FEAT-JARVIS-006` (the NATS Chat Gateway, demo-critical for 16 May DDD Southwest) was queued via `/feature-build FEAT-JARVIS-006` after [`TASK-J006-006`](../in_review/feat-jarvis-006-nats-chat-gateway/TASK-J006-006-realign-implementation-mode-and-requeue.md) applied its tactical reset (Intervention A: switch J006-003 and J006-004 `implementation_mode: task-work → direct`; reset feature/task state; preserve the worktree at `83bb69f1`). The run produced a transcript at `docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md`.

**The signal is contradictory.** A surface read of the post-run state suggests success (per-task Turn 1 `decision: approve` for both J006-003 and J006-004, both task files transitioned to `status: in_review`), but the file name says `failed-run-2`, the feature YAML still reads `status: failed`, and the autobuild log explicitly states `Mode: task-work (explicit frontmatter override)` for J006-003 — implying our `implementation_mode: direct` reset may not have actually changed the run mode.

This review must reconcile those signals: was fail-run-2 actually a success that's being mislabelled, an actual failure at a stage downstream of the per-task gates, or a success that didn't validate the intervention we set out to test?

## Why this needs a review (not direct implementation)

Three independent questions all need evidence-based answers from the same transcript, and the answers determine whether the next action is "merge and ship," "queue fail-run-3 with a different lever," or "wait on `TASK-FIX-CAUD-J6F1` in guardkit." Doing the analysis once, in writing, prevents three rounds of partial reads of a 92 KB log.

## Open questions (the review must answer each with citations)

### Q1 — Why does the feature YAML say `status: failed` when per-task data says success?

Post-run, `.guardkit/features/FEAT-JARVIS-006.yaml` shows:
- `status: failed` (feature-level)
- `execution.tasks_completed: 4`, `execution.tasks_failed: 0`
- `execution.completed_at: '2026-05-12T11:14:22.873358'`
- `execution.completed_waves: [1, 2, 3]`
- All of TASK-J006-001 through TASK-J006-004: `status: completed`, `result.final_decision: approved`
- TASK-J006-005 (live demo verification): `status: pending` — but that task is `implementation_mode: direct` + `operator_handoff` and was never expected to run automatically (matches the spec — see TASK-J006-006 AC-007).

Either:
1. The orchestrator wrote `feature.status: failed` because TASK-J006-005 didn't complete and the run was `--resume` (i.e. the feature-level status is computed against ALL tasks being terminal, not just those marked operator_handoff), **or**
2. A smoke gate / post-wave check failed downstream of the per-task gates, **or**
3. Something else (transcript should make this explicit — search for "FAIL", "abort", "smoke", "exit_code", "preflight_strict").

Identify which one and cite the log line that proves it.

### Q2 — Did TASK-J006-006 Intervention A actually take effect for fail-run-2?

The autobuild log line on or around the J006-003 player invocation reads:

> `INFO:guardkit.orchestrator.agent_invoker:[TASK-J006-003] Mode: task-work (explicit frontmatter override)`

But TASK-J006-006 set `implementation_mode: direct` in **both** the task .md frontmatter **and** the feature YAML before the user re-queued. So one of:

1. The orchestrator reads `implementation_mode` from a source we didn't edit (e.g. an internal state file, a per-task cache, the `.guardkit/autobuild/TASK-J006-003/` dir from fail-run-1, the worktree's own copy of the task file at branch tip `83bb69f`).
2. There's a precedence rule that pins `task-work` once a per-task autobuild dir exists from a prior run (the "explicit frontmatter override" phrasing suggests the orchestrator believed it WAS reading from frontmatter — but from which copy?).
3. There's a third source (CLI default, env var, config layer) silently overriding.

This is the diagnostic-quality question. The review must identify the actual code path that resolved `implementation_mode` to `task-work` for fail-run-2, and from there determine what TASK-J006-006 needs to additionally edit on a future re-run (or whether the intervention is unfixable jarvis-side and must move to guardkit).

### Q3 — Did the per-task `decision: approve` outcomes actually validate, or are they false positives like fail-run-1's claim-audit warnings?

Fail-run-1 had per-task `coach_success: true` for all three turns of J006-003 (and `player_success: true`), yet the run stalled because `quality_gates` was null and the claim-audit warnings were promoted to `must_fix`. Fail-run-2 reports `decision: approve` on Turn 1 for both J006-003 and J006-004. Verify:

1. Was `coach_validator.verify_quality_gates` actually run and did it return `all_gates_passed: true`? (Cross-check the `task_work_results.json` for each task.)
2. Did the claim-audit emit any warnings, and were they kept as warnings (not promoted to `must_fix`)? — this is what `TASK-FIX-CAUD-J6F1` was supposed to fix in guardkit; verify whether that fix landed before this run.
3. Did the `agent_invocations_validation` block (TASK-FIX-RWOP1.3.1, see `/task-work` Step 6.5) record `status: passed` or `violation`? — `direct` mode was meant to ensure all expected phases ran inline; verify.
4. Did the `plan_audit` verdict (TASK-FIX-RWOP1.3.2) come back clean?

If any of (1)–(4) failed quietly while the surface `decision: approve` still landed, that's a regression worth flagging.

### Q4 — TASK-J006-006 acceptance criteria status

Update the closure status of TASK-J006-006:

- **AC-005**: "Fail-run-2's TASK-J006-003 turn 1 reaches `decision: approve` AND `coach_turn_1.json.honesty_verification.verified: true` (or `decision: approve` with audit issues remaining as warnings only)." — The `decision: approve` half is met per the task file. The `honesty_verification.verified` half needs the `coach_turn_1.json` artefact inspected (in `.guardkit/autobuild/TASK-J006-003/`).
- **AC-006**: "TASK-J006-004 completes successfully in the same autobuild run." — Per the feature YAML, J006-004 has `status: completed, final_decision: approved, turns_completed: 1`. Verify against the transcript.

If both are met → TASK-J006-006 can move from `in_review` to `completed` regardless of the Q2 answer about whether Intervention A was the actual mechanism.

### Q5 — Was the produced implementation actually correct?

Independent of orchestration outcome: does the code at branch tip of `autobuild/FEAT-JARVIS-006` satisfy the substantive acceptance criteria of J006-003 and J006-004? (Dual-publish, notification drain, signal handling, no double-register, lint zero-errors.) Spot-check rather than line-by-line review — the goal is to confirm that whatever did succeed produced a real artefact, not a stub.

## Acceptance Criteria

- [ ] AC-001: Full read of `docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md` completed; key events (wave starts, turn outcomes, validation blocks, smoke gate, feature finalisation) timestamped and quoted in the review report.
- [ ] AC-002: Q1 answered with a citation of the specific log line(s) or YAML field(s) that prove why `feature.status: failed`. State whether this is a legitimate failure or an artefact of `TASK-J006-005` being operator_handoff.
- [ ] AC-003: Q2 answered with the actual code path (file:line if visible from log, otherwise the resolution mechanism inferred from artefact contents). State whether TASK-J006-006 Intervention A is effective, partially effective, or ineffective, and if ineffective, what additional lever is needed.
- [ ] AC-004: Q3 answered by inspecting `task_work_results.json` for J006-003 and J006-004 in `.guardkit/autobuild/`. Cite the `validation_results.quality_gates`, `agent_invocations_validation`, and `plan_audit` blocks for both tasks.
- [ ] AC-005: Q4 closure recommendation for TASK-J006-006: state whether AC-005 and AC-006 of that task are met, with citations; recommend whether to move it `in_review → completed` or to keep it open pending re-test.
- [ ] AC-006: Q5 spot-check completed: confirm `chat_handler.py` and `serve_nats` CLI in the autobuild worktree implement the substantive ACs of J006-003 and J006-004 (dual-publish, notification drain, signal handling, lint-clean, ~20 unit tests passing). Test runs from the worktree are out of scope; static inspection only.
- [ ] AC-007: Review report saved to `.claude/reviews/TASK-REV-J6F2-review-report.md` with sections matching Q1–Q5. Report includes a **Next Action** section that picks ONE of: `[M]erge and ship` (run produced correct artefacts and a merge is the path forward), `[R]equeue fail-run-3` (with the additional lever Q2 identified), `[E]scalate to guardkit` (with the specific guardkit task ID — likely `TASK-FIX-CAUD-J6F1` or a sibling), or `[C]omplex` (mixed; describe the multi-step path).
- [ ] AC-008: If Next Action is `[R]equeue`, an implementation task is created via `/task-create` capturing the additional lever (analogous to how TASK-J006-006 was the implementation arm of TASK-REV-J6F1). If Next Action is `[M]erge`, the path to a clean merge of `autobuild/FEAT-JARVIS-006` → `main` is documented (any pre-merge cleanup, conflict checks, smoke test). If Next Action is `[E]scalate`, the guardkit-side task is referenced and the demo-deadline impact (16 May 2026) is called out explicitly.

## Out of Scope

- **Implementing any fix** identified in this review. The review's output is a report and a routing decision; implementation lives in a follow-up task created by AC-008 (mirroring the TASK-REV-J6F1 → TASK-J006-006 pattern).
- **Running tests or `serve-nats` end-to-end.** Smoke testing of the merged result is owned by TASK-J006-005 (operator_handoff, demo verification). This review is static analysis of the run transcript + artefacts.
- **Touching any `src/jarvis/**` source file.** If the worktree's implementation is wrong, that's a finding for the report — fixing it is the follow-up task's job.
- **Fixing the upstream Coach claim-audit bug.** Still tracked separately in guardkit as `TASK-FIX-CAUD-J6F1`. This review may *reference* whether that fix has landed (it would affect Q3's answer), but does not own its resolution.
- **TASK-J006-005 (live Open WebUI demo verification).** Operator-handoff; will be scheduled separately once the chat gateway is verified-good and merged.

## Test Plan

Not applicable — this is an analysis task, not an implementation. Verification is by review report quality:
- Each open question Q1–Q5 has a section in the report with at least one specific citation (log line, YAML key, file path:line, or artefact path).
- Next Action recommendation is specific enough that an executor (human or `/task-create`) could act on it without further interpretation.
- Report length is constrained to what's needed; no padding.

## Implementation Notes

_(populated by `/task-review TASK-REV-J6F2`)_

### Suggested review mode

Use `/task-review TASK-REV-J6F2 --mode=architectural` or `--mode=root-cause` (whichever is the closer fit to "diagnose orchestration failure from a transcript" in your install — the goal is a root-cause analysis with a routing decision, not a code-quality assessment).

### Starting points in the transcript

The fail-run-1 review (`TASK-REV-J6F1-review-report.md`) used a fixed scan pattern that worked well: scan for `WARNING`, `ERROR`, `FAIL`, `must_fix`, `unrecoverable`, `Mode:`, `Phase`, `decision:`, and `[TASK-J006-` qualifier. Recommend the same pattern here, plus an explicit pass for `feature.status`, `smoke`, `preflight`, and any references to `operator_handoff` (Q1's most likely answer hides in those).

### Cross-reference checklist

When reading the transcript, keep three windows open:
1. `docs/history/autobuild-FEAT-JARVIS-006-failed-run-2.md` (the transcript)
2. `.guardkit/features/FEAT-JARVIS-006.yaml` (the resulting feature state)
3. `tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-00{3,4}-*.md` (the resulting task state)

The discrepancy across those three is the story.
