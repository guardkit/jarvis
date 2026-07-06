---
id: TASK-REV-3240
title: "Plan: Slack Planning Intake (FEAT-SPL-001)"
status: completed
created: 2026-07-06T09:58:00Z
updated: 2026-07-06T11:30:00Z
review_results:
  mode: decision
  depth: standard
  score: 86
  findings_count: 12
  recommendations_count: 4
  decision: implement
  report_path: .claude/reviews/TASK-REV-3240-review-report.md
  completed_at: 2026-07-06T11:30:00Z
priority: high
task_type: review
repo: jarvis
tags: [sovereign-planning-loop, feat-spl-001, slack, planning-intake]
complexity: 0
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: Slack Planning Intake (FEAT-SPL-001)

## Description

Decision review for FEAT-SPL-001 (Sovereign Planning Loop, jarvis half of the
planning front door): a free-text message posted by the identity-pinned
originator in the dedicated Slack planning channel becomes a
`PlanningQueuedPayload` (nats-core 0.5.0, `stage="planning"`, required
`originating_user`, explicit `originating_adapter="slack"`) published to
JetStream on `pipeline.planning-queued.{correlation_id}`, acknowledged
in-thread. No reasoning in jarvis — intake only.

Spec on disk (18 scenarios, 10 low-confidence assumptions, all deferred):
`features/feat-spl-001-slack-planning-intake/` (committed `1ef48fa`).

Analyze implementation options (Socket Mode listener topology, module layout,
config gates, dedup, publish path), assess risks (shared connection with the
JNB-104 reply path, loop prevention, wire-layer `originating_adapter` caveat),
and produce a task breakdown for implementation.

## Acceptance Criteria

- [ ] Technical options analyzed with a recommended approach
- [ ] Risks identified (shared Socket Mode connection, ack loop, dedup)
- [ ] Task breakdown with dependencies and waves
- [ ] Alignment with SPL scope §3 design constraints verified

## Context

- Feature spec: `features/feat-spl-001-slack-planning-intake/feat-spl-001-slack-planning-intake_summary.md`
- SPL scope: `../ai-transition/docs/sovereign-planning-loop-scope.md` (§5 FEAT-SPL-001)
- SPL build plan Session 2; fable-window plan ACTION 6
- Key code: `src/jarvis/infrastructure/slack_reply.py` (JNB-104 SocketModeClient),
  `src/jarvis/tools/dispatch.py` (`queue_build` publish pattern),
  `src/jarvis/config/settings.py` (Slack settings block)
