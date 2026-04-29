---
id: TASK-REV-22CF
title: "Plan: NATS Fleet Registration and Specialist Dispatch"
task_type: review
status: review_complete
created: 2026-04-27T15:10:00Z
updated: 2026-04-27T15:25:00Z
review_results:
  mode: decision
  depth: standard
  score: 88
  findings_count: 4
  recommendations_count: 20
  decision: implement
  feature_yaml: .guardkit/features/FEAT-J004-702C.yaml
  feature_folder: tasks/backlog/feat-jarvis-004-fleet-registration-and-specialist-dispatch/
  bdd_scenarios_tagged: 36
  bdd_scenarios_below_threshold: 0
  report_path: .claude/reviews/TASK-REV-22CF-review-report.md
  approaches_considered: 3
  recommended_approach: "Wave-based parallel fan-out (Approach 2)"
priority: high
tags: [feature-plan, fleet, nats, dispatch, FEAT-JARVIS-004]
complexity: 0
feature_id: FEAT-JARVIS-004
clarification:
  context_a:
    timestamp: 2026-04-27T15:10:00Z
    decisions:
      focus: all
      tradeoff: balanced
      concerns:
        - assum_009_trace_file_collision_policy
        - assum_008_degraded_specialist_eligibility
        - contract_enforcement_payloads_and_manifest
        - test_strategy_gaps
context_files:
  - features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_summary.md
  - features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature
  - features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml
  - docs/design/FEAT-JARVIS-004/design.md
  - docs/design/FEAT-JARVIS-004/contracts/API-tools.md
  - docs/design/FEAT-JARVIS-004/contracts/API-internal.md
  - docs/design/FEAT-JARVIS-004/contracts/API-events.md
  - docs/design/FEAT-JARVIS-004/models/DM-routing-history.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-016-dispatch-timeout-default-60s.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-017-retry-with-redirect-policy.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-018-routing-history-schema-authoritative.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-020-concurrent-dispatch-cap-8.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-022-defer-llamaswap-live-reads-to-v15.md
  - docs/research/ideas/phase3-fleet-integration-scope.md
  - docs/research/ideas/phase3-build-plan.md
  - .guardkit/context-manifest.yaml
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Plan: NATS Fleet Registration and Specialist Dispatch

## Description

Decision-mode review for FEAT-JARVIS-004: NATS Fleet Registration and Specialist
Dispatch. The design corpus is large and stable (one feature spec with 36 Gherkin
scenarios, one design.md, three contract docs, one data model, seven DDRs, and a
phase-3 build plan). The job of this review is **not** to redesign the feature
but to:

1. Validate the design holds together end-to-end (lifecycle, dispatch, retry,
   shutdown, soft-fail).
2. Convert the design + contracts + assumptions into a concrete, dependency-aware
   task breakdown that AutoBuild can execute.
3. Surface and resolve the four user-flagged concerns (ASSUM-009, ASSUM-008,
   contract enforcement, test strategy gaps).
4. Emit a /feature-plan with mandatory data-flow and contract diagrams plus a §4
   Integration Contracts section so cross-task hand-offs (NATS subjects, registry
   keys, routing-history schema) are pinned before Wave 1.

## Review Scope (from Context A clarification)

- **Focus**: All areas — full-spectrum review (architecture, correctness,
  testing, security, performance).
- **Trade-off priority**: Balanced — surface trade-offs explicitly; do not bias
  toward speed-to-merge or maximalist refactor.
- **Specific concerns** to address directly:
  - **ASSUM-009** (low confidence): trace-file collision policy when two
    concurrent dispatches collide on the same `trace_id`-derived path.
  - **ASSUM-008** (medium confidence): whether degraded specialists remain
    eligible for dispatch and how the registry communicates that.
  - **Contract enforcement**: nats-core payload round-trips, CommandPayload /
    ResultPayload schema fidelity, AgentManifest kebab-case validation,
    redaction-boundary invariants (ADR-ARCH-029).
  - **Test strategy gaps**: coverage of the five-row semaphore-slot-release
    outline (DDR-020), filesystem-offload edge cases, partial-failure lifecycle
    tests, drain-on-shutdown ordering.

## Acceptance Criteria

- [ ] Decision-mode review produces ≥3 evaluated approaches with explicit
      trade-offs and a recommended approach with rationale.
- [ ] Recommendation reconciles all seven DDRs (DDR-016 through DDR-022) and
      flags any tension with the design or contracts.
- [ ] Each of the four concerns (ASSUM-008, ASSUM-009, contract enforcement,
      test strategy) is addressed with a concrete recommendation —
      either a follow-up DDR, a frontmatter constraint, an explicit task, or a
      documented deferral.
- [ ] Task breakdown is dependency-aware (waves), maps to design components, and
      includes `task_type` for every task.
- [ ] Cross-task data hand-offs are captured as §4 Integration Contracts (NATS
      subjects, registry KV keys, routing-history schema, manifest kebab-case
      identifiers).
- [ ] IMPLEMENTATION-GUIDE.md includes the mandatory data-flow diagram (always),
      sequence diagram (complexity ≥ 5 — yes), and dependency graph (≥ 3 tasks
      — yes).
- [ ] Disconnection rule honoured: every write path has a corresponding read
      path or an explicit deferral note.
- [ ] FEAT-JARVIS-004 YAML emitted under `.guardkit/features/` with parallel
      execution waves and `--discover`-resolved file_path values.
- [ ] Pre-flight `guardkit feature validate` runs against the emitted YAML.

## Test Requirements

- [ ] At decision-checkpoint, the review surfaces (not hides) any open
      questions — scope creep into v1.5 (DDR-022) or out-of-scope items must be
      explicit deferrals.
- [ ] Review is reproducible: clarification decisions and context manifest
      pointers are persisted in this task's frontmatter so re-running planning
      does not silently change scope.

## Implementation Notes

This review task is the input to `/task-review --mode=decision --depth=standard`.
It is **not** an implementation task — `/task-work` should not be invoked
against it directly. The output of the decision checkpoint becomes the
implementation breakdown that lives under
`tasks/backlog/feat-jarvis-004-fleet-registration-and-specialist-dispatch/`.

### Source-of-truth references

- **Design**: `docs/design/FEAT-JARVIS-004/design.md`
- **Contracts**: `docs/design/FEAT-JARVIS-004/contracts/API-{tools,internal,events}.md`
- **Data model**: `docs/design/FEAT-JARVIS-004/models/DM-routing-history.md`
- **DDRs**: `docs/design/FEAT-JARVIS-004/decisions/DDR-016..DDR-022`
- **BDD**: `features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature`
- **Assumptions**: `features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml`
- **Phase plan**: `docs/research/ideas/phase3-build-plan.md`

## Test Execution Log

(Populated by /task-review and /feature-plan downstream steps.)
