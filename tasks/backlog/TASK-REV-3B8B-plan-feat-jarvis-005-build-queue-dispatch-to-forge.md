---
id: TASK-REV-3B8B
title: "Plan: FEAT-JARVIS-005 — Build Queue Dispatch to Forge"
task_type: review
status: backlog
created: 2026-04-29T00:00:00Z
updated: 2026-04-29T00:00:00Z
priority: high
tags: [jarvis, phase3, forge, nats, planning]
complexity: 0
feature: FEAT-JARVIS-005
clarification:
  context_a:
    timestamp: 2026-04-29T00:00:00Z
    decisions:
      focus: all
      tradeoff: quality
      concerns:
        - end_to_end_forge_round_trip_gating
        - append_only_edges_frozen_entry_ddr_029_018
context_files:
  - features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md
  - features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge.feature
  - features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_assumptions.yaml
  - docs/design/FEAT-JARVIS-005/design.md
  - docs/design/FEAT-JARVIS-005/decisions/
  - docs/design/FEAT-JARVIS-005/contracts/
  - docs/research/ideas/phase3-build-plan.md
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan FEAT-JARVIS-005 — Build Queue Dispatch to Forge

## Description

Decision-mode review for FEAT-JARVIS-005 ("Build Queue Dispatch to Forge"). Closes the
Jarvis → Forge loop: `queue_build` swaps from a Phase 2 stub log line to a real
`js.publish(...)` on `pipeline.build-queued.{feature_id}` (PubAck-as-receipt, 5s timeout
per ADR-SP-014 Pattern A + DDR-025); Jarvis subscribes to `pipeline.stage-complete.>`
via an ephemeral push consumer with `deliver_policy=NEW` (DDR-027), routes
correlation-matched events through an in-process `ForgeNotificationsSubscriber` to the
originating session's per-session pending-notification queue (DDR-026, DDR-030), and
renders one CLI line per notification between prompts in the canonical
`[HH:MM] Forge {feature_id}: stage {stage_label} ({status})` shape.

Every build-queue dispatch writes a `subagent_type="forge_build_queue"` routing-history
entry; every matched stage-complete event lands as an append-only Graphiti edge on that
entry (DDR-029). Adapter identity is constitutional — resolved from `Session.adapter`
(DDR-031). The reasoning model's tool surface is unchanged from Phase 2.

## Review Scope (Context A)

- **Focus**: All aspects (technical, architecture, integration, sequencing, risk)
- **Trade-off priority**: Quality / reliability — Phase 3 closer; tight quality gates,
  full coverage of soft-fail paths, contract tests gating later waves.
- **Specific concerns to surface**:
  - End-to-end Forge round-trip gating (Wave 7 soft-prereq on GB10 + Forge + Graphiti)
  - Append-only Graphiti edges + frozen routing-history entry invariant (DDR-029 / DDR-018)

## Acceptance Criteria (review deliverables)

- [ ] Technical-options analysis covering each of the seven changes (publish swap,
      subscriber module, append-only edge writer, CLI rendering, session-manager queue,
      lifecycle wiring, contract tests).
- [ ] Architecture verification that DDR-025..031 are honoured by the proposed wave
      sequence; no DDR is silently relaxed.
- [ ] Risk analysis covering: bounded-map saturation, soft-fail paths (NATS down,
      Graphiti down, JetStream wedged), CLI overflow, correlation-id collisions,
      session-clears-queue invariant.
- [ ] Effort estimate per wave (Wave 1..7) and aggregate complexity score.
- [ ] Cross-repo contract verification — Jarvis publishes / consumes verbatim
      `nats_core.events.BuildQueuedPayload` / `StageCompletePayload`, no
      Jarvis-specific wire extensions; subjects produced by `nats_core.Topics.Pipeline.*`.
- [ ] §4 Integration Contracts identified for cross-task data flow
      (BuildQueuedPayload, StageCompletePayload, BuildCorrelation map handle,
      ForgeNotification queue handle, JarvisRoutingHistoryEntry).
- [ ] Decision checkpoint — A/R/I/C — surfaces the suggested 7-wave breakdown for
      operator confirmation.

## Test Requirements

- N/A for review-mode task. Test work is created as subtasks under the chosen
  implementation plan after the [I]mplement decision.

## Implementation Notes

This is a `task_type: review` decision task. Continue under `/feature-plan` orchestration —
do not stop. Next phase: `/task-review TASK-REV-3B8B --mode=decision --depth=standard`,
followed by the decision checkpoint and (if [I]mplement) Context B + structure generation.

## Test Execution Log

[Automatically populated by `/task-review` and downstream commands]
