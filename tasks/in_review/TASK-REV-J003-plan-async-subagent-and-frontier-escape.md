---
id: TASK-REV-J003
title: "Plan: Async Subagent for Model Routing + Attended Frontier Escape (FEAT-JARVIS-003)"
task_type: review
status: review_complete
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
review_results:
  mode: decision
  depth: standard
  score: 12
  findings_count: 7
  recommendations_count: 3
  decision: pending
  report_path: .claude/reviews/TASK-REV-J003-review-report.md
  recommended_option: "Option B — Envelope-first, concurrent fan-out"
  task_count: 24
  wave_count: 5
priority: high
tags: [feature-planning, decision, phase-2, async-subagent, frontier-escape, jarvis]
complexity: 7
feature_id: FEAT-JARVIS-003
decision_required: true
test_results:
  status: pending
  coverage: null
  last_run: null
clarification:
  context_a:
    timestamp: 2026-04-24T00:00:00Z
    decisions:
      review_aspects: all
      analysis_depth: standard
      tradeoff_priority: quality
      specific_concerns:
        - layer-3-tool-registry-absence-standalone-task
        - llamaswap-stub-shape-stable-for-feat-j004
        - zero-retired-roster-strings-no-shims
        - role-propagation-integration-test
        - tight-subtask-granularity-vs-coach-player-stall
context_files:
  - features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_summary.md
  - features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature
  - features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape_assumptions.yaml
  - docs/design/FEAT-JARVIS-003/design.md
  - docs/research/ideas/phase2-dispatch-foundations-scope.md
  - docs/research/ideas/phase2-build-plan.md
  - .guardkit/context-manifest.yaml
---

# Task: Plan Async Subagent for Model Routing + Attended Frontier Escape (FEAT-JARVIS-003)

## Description

Produce a feature-plan-grade decision review for FEAT-JARVIS-003. The feature ships the `jarvis-reasoner` AsyncSubAgent with a closed-enum `role` kwarg, the attended-only `escalate_to_frontier` tool with three-layer belt+braces gating, and the swap-aware `LlamaSwapAdapter` with stubbed health — reconciling the retired four-cloud-subagent roster with ADR-ARCH-001 / ADR-ARCH-011 / ADR-ARCH-012 / ADR-ARCH-027.

The review must recommend how to sequence and break down the work so that subsequent implementation tasks preserve the Phase 2 invariants and the six DDRs (DDR-010..015) already pinned at `/system-design` on 2026-04-23.

## Acceptance Criteria

- [x] All 44 Gherkin scenarios mapped to specific subtasks via `@task:TASK-J003-xxx` tags after feature-file linking.
- [x] Three task-breakdown options analysed against Context A priority (quality) and five specific concerns.
- [x] One option recommended with explicit justification.
- [x] 24 subtasks across 5 waves; aggregate complexity 7; zero intra-wave conflicts.
- [x] Layer 3 tool-registry-absence is a standalone subtask (Context A concern #1).
- [x] Retired-roster-string regression test is a standalone subtask (Context A concern #3).
- [x] Role propagation integration test is a standalone subtask (Context A concern #4).
- [x] Subtask complexity ≤ 6 for every task (Context A concern #5 — Coach-Player stall mitigation).
- [x] Review report saved to `.claude/reviews/TASK-REV-J003-review-report.md`.

## Review Output

**See** [`.claude/reviews/TASK-REV-J003-review-report.md`](../../.claude/reviews/TASK-REV-J003-review-report.md) for the full decision analysis.

**Recommendation:** Option B — Envelope-first, concurrent fan-out. Review score 12/12.

**Decision:** Pending user input at decision checkpoint.
