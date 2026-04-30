---
id: TASK-REV-E73C
title: "Analyse AutoBuild FEAT-J005-946D timeout failure (TASK-J005-005)"
task_type: review
review_mode: decision
review_depth: standard
status: completed
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
priority: high
tags:
  - autobuild
  - timeout
  - investigation
  - jarvis
  - feat-jarvis-005
  - guardkit-orchestrator
complexity: 0
feature: FEAT-JARVIS-005
related_feature_id: FEAT-J005-946D
context_files:
  - docs/history/autobuild-FEAT-J005-946D-timeout-history.md
  - .guardkit/features/FEAT-J005-946D.yaml
  - tasks/backlog/feat-jarvis-005-build-queue-dispatch-to-forge/TASK-J005-005-dispatch-queue-build-real-publish.md
  - .guardkit/autobuild/FEAT-J005-946D/review-summary.md
review_results:
  mode: decision
  depth: standard
  revision: v2-deepened
  primary_root_cause: >-
    Single 3000s envelope shared by Player×2 + specialist:test-orchestrator×2 +
    specialist:code-reviewer×2 + Coach×2; specialist pipeline alone consumed 49%
    of budget across 2 turns, Turn 1 Player SDK 41%. Code-validated: matches
    formulas at agent_invoker.py:3820-3901 and autobuild.py:2880-2909.
  race_condition: >-
    asyncio.wait_for(asyncio.to_thread(...)) at feature_orchestrator.py:2079-2087
    cannot hard-cancel the worker thread. Per-task layer has approval-wins-over-
    timeout grace at autobuild.py:2192-2202 (TASK-ABFIX-004) which fired correctly,
    so per-task state says approved (15/15 ACs, decision=approve, coach_turn_2.json,
    git commit 0069a0d at exact wall-clock second 23:53:52). Feature layer has no
    symmetric mechanism; gather() collected TimeoutError 68ms before per-task
    write-back completed.
  worktree_validated: true
  worktree_branch: autobuild/FEAT-J005-946D
  worktree_commits_ahead_main: 9
  worktree_diff_stat: 101 files changed, 11853 insertions(+), 687 deletions(-)
  recommendation: option-a-corrected-resume
  tier_0_fixes:
    - "Create .guardkit/config.yaml with autobuild.coach.test_execution: subprocess (eliminates 7/7 SDK fail noise)"
    - "Set GUARDKIT_AUTOBUILD_TASK_TIMEOUT_FLOOR=4500 in resume shell (zero code change)"
    - "Manually flip TASK-J005-005 to completed in FEAT-J005-946D.yaml + resume"
  tier_1_fixes_followup:
    - "Per-task task_timeout override in task frontmatter for complexity>=7 task-work"
    - "Refresh remaining_budget between Phase 4 and Phase 5 specialists (autobuild.py:2880-2909 latent bug)"
  tier_2_fixes_followup:
    - "Feature-level late-approval reconciliation (read coach_turn_*.json after TimeoutError)"
    - "Graphiti edge_fulltext_search circuit breaker"
    - "File issue against claude-agent-sdk 0.1.66 _bundled/claude pytest exit-code-1"
  report_path: .claude/reviews/TASK-REV-E73C-review-report.md
  completed_at: 2026-04-30T00:00:00Z
test_results:
  status: not_applicable
  coverage: null
  last_run: null
---

# TASK-REV-E73C — Analyse AutoBuild FEAT-J005-946D timeout failure

## Description

`guardkit autobuild feature FEAT-J005-946D --verbose` ran for 90m 16s and stopped
at Wave 3 with **TASK-J005-005** marked `TIMEOUT` (3000s / 50min `task_timeout`
expired). The remaining 4 tasks in Waves 4–5 (009, 010, 011, 012) never ran
because `stop_on_failure=True` was set.

The full transcript is captured at
[docs/history/autobuild-FEAT-J005-946D-timeout-history.md](../../docs/history/autobuild-FEAT-J005-946D-timeout-history.md)
(1904 lines).

This review task is a **post-mortem analysis** to identify the root cause(s),
quantify the contribution of each factor, and recommend a remediation path
(resume vs. re-run, config changes, code/agent changes, or a mix).

## Observed signals (from the transcript)

| # | Signal | Source line(s) |
|---|---|---|
| 1 | TASK-J005-005 timed out at 3000s (50 min) — `task_timeout` expired during turn 2 Coach Validation | 1800–1802 |
| 2 | Last snapshot before timeout: `phase=specialist:code-reviewer invocation, files_changed=0, last_tool=Bash, elapsed=360s` | 1800 |
| 3 | Player turn 2 specialist:code-reviewer invocation observed at 270s, 300s, 330s, 360s, 390s — i.e. ≥390s in flight | 1750–1754 |
| 4 | Coach validation actually completed seconds AFTER the timeout fired: `Coach approved TASK-J005-005 turn 2` at 22:53:52.072 vs timeout at 22:53:52.004 | 1801, 1805–1808 |
| 5 | SDK Coach test execution failed with exit code 1; fell back to subprocess (which then succeeded in 8.3s) | 1794–1799, 1804 |
| 6 | Repeated `RecursionError in edge_fulltext_search` WARNs during Coach context loading (graphiti-core / FalkorDB issue) | 1759–1779 |
| 7 | Final outcome: 7/12 tasks completed (6 SUCCESS + 1 TIMEOUT); Wave 3 marked FAILED; Waves 4–5 (4 tasks) never ran | 1854–1892 |
| 8 | `task_timeout=3000s` is the **feature-level** budget; `sdk_timeout=1200s per invocation` is the per-call budget. Player's specialist invocations and Coach's SDK test execution all share the 50-min envelope. | 4 |
| 9 | Despite the timeout, AutoBuild Summary table for the task shows `Status: APPROVED` after 2 turns — the per-task orchestrator and the feature-level orchestrator disagree | 1821–1842 |

## Acceptance Criteria (review deliverables)

- [ ] **Root cause(s) identified** — name each contributing factor (Player
      turn 2 specialist runtime, Coach SDK test exit-code-1 fallback, Graphiti
      RecursionError noise, task_timeout vs sdk_timeout interaction, stop_on_failure
      cascade) and rank by contribution.
- [ ] **Race condition characterised** — explain the disagreement between
      "TIMEOUT" (feature orchestrator) and "APPROVED" (per-task orchestrator)
      for the same task at the same wall-clock instant. Determine whether the
      Coach's APPROVED outcome should have suppressed the feature-level
      timeout cascade.
- [ ] **Specialist:code-reviewer hot-path reviewed** — answer "is 360s+ for a
      single code-reviewer invocation on TASK-J005-005 expected, or is there a
      pathology in the prompt / context / tool budget?" Reference the task's
      complexity (7/10) and acceptance-criteria count (15) to set a baseline.
- [ ] **Coach-side SDK fallback path reviewed** — the SDK test execution path
      failing with exit-code-1 and then succeeding via subprocess is observed
      twice in the transcript. Is the SDK path systematically broken, or
      environment-specific? Should the Coach default to subprocess on this
      machine?
- [ ] **Resume vs re-run recommendation** — given the worktree is preserved
      and 7 tasks landed clean, recommend either
      (a) `guardkit autobuild feature FEAT-J005-946D --resume` (cheapest path),
      (b) targeted re-run of just TASK-J005-005 + Waves 4–5, or
      (c) full re-run (only if rollback warranted).
- [ ] **Config change recommendation** — propose a concrete change to either
      `task_timeout`, `sdk_timeout`, `stop_on_failure`, or the
      `--max-parallel` / `--bootstrap-failure-mode` flags that would have
      surfaced the failure earlier or prevented the cascade.
- [ ] **Decision checkpoint** — A/R/I/C presented with concrete next-step
      commands for each option.

## Test Requirements

- N/A for review-mode task. Any implementation tasks recommended at the
  decision checkpoint will carry their own test requirements.

## Implementation Notes

- The transcript is large (1904 lines, ~80KB); a `task-review` invocation
  should chunk it: lines 1–200 (setup + Wave 1 launch), 1700–1810 (the timeout
  window), 1820–1900 (final summary). The middle 1500 lines are mostly Wave
  1/2 success traffic that does not bear on the timeout.
- TASK-J005-005's task file shows `autobuild_state.current_turn: 2`,
  `decision: approve` for turn 2 in its frontmatter — this is the per-task
  orchestrator's view. Cross-reference against the feature-level
  `review-summary.md` for the conflicting view.
- Worktree is preserved at
  `.guardkit/worktrees/FEAT-J005-946D` for direct inspection of what
  TASK-J005-005 actually produced.
- Related: this is the **first** AutoBuild run since the FEAT-J004 close
  (commit `b228d7d`, 2026-04-28). FEAT-J004 ran 20 tasks in 7 waves cleanly;
  this run was the first to hit a 3000s task — useful baseline.

## Test Execution Log

[Automatically populated by `/task-review` and downstream commands]
