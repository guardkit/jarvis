---
id: TASK-REV-J002
title: "Plan: Core Tools & Capability-Driven Dispatch Tools (FEAT-JARVIS-002)"
task_type: review
status: review_complete
created: 2026-04-24T06:53:48Z
updated: 2026-04-24T06:54:30Z
review_results:
  mode: decision
  depth: standard
  score: 12
  findings_count: 7
  recommendations_count: 3
  decision: pending
  report_path: .claude/reviews/TASK-REV-J002-review-report.md
  recommended_option: "Option B — Envelope-first, concurrent fan-out"
  task_count: 23
  wave_count: 5
priority: high
tags: [feature-planning, decision, phase-2, core-tools, dispatch, jarvis]
complexity: 8
feature_id: FEAT-JARVIS-002
decision_required: true
test_results:
  status: pending
  coverage: null
  last_run: null
clarification:
  context_a:
    timestamp: 2026-04-24T06:53:48Z
    decisions:
      review_aspects: all
      analysis_depth: standard
      tradeoff_priority: maintainability
      specific_concerns:
        - stub-transport-swap-point-safety
        - capability-envelope-schema-evolution
        - correlation-id-propagation
        - task-ordering-constraints
      future_extensibility: default
context_files:
  - features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_summary.md
  - features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature
  - features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_assumptions.yaml
  - docs/design/FEAT-JARVIS-002/design.md
  - docs/research/ideas/phase2-dispatch-foundations-scope.md
  - docs/research/ideas/phase2-build-plan.md
  - .guardkit/context-manifest.yaml
---

# Task: Plan Core Tools & Capability-Driven Dispatch Tools (FEAT-JARVIS-002)

## Description

Produce a feature-plan-grade decision review for FEAT-JARVIS-002. The feature
introduces Jarvis's five core tools (`search_web`, `calculator`, `read_file`,
`write_workspace_file`, `list_workspace`) and the three dispatch-intent tools
(`ingest_capability_registry`, `dispatch_to_agent`, `dispatch_subscribe`) that
unlock Phase 2 supervisor behaviour.

The review must recommend how to sequence and break down the work so that
subsequent implementation tasks preserve the Phase 2 invariants documented in:
- `docs/design/FEAT-JARVIS-002/design.md`
- `docs/research/ideas/phase2-dispatch-foundations-scope.md`
- `docs/research/ideas/phase2-build-plan.md`

And the feature specification in:
- `features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature`
- `features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_summary.md`
- `features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_assumptions.yaml`

## Acceptance Criteria

- [ ] All five core tools (`search_web`, `calculator`, `read_file`,
      `write_workspace_file`, `list_workspace`) are represented as discrete
      implementation tasks with acceptance criteria traceable to the
      `.feature` scenarios.
- [ ] All three dispatch-intent tools (`ingest_capability_registry`,
      `dispatch_to_agent`, `dispatch_subscribe`) are represented as discrete
      tasks with stub transport contracts preserved behind a documented
      swap-point (DDR-009).
- [ ] Capability registry polling, TTL/ETag behaviour, and freshness metadata
      are accounted for as either their own task or an explicit sub-slice of
      `ingest_capability_registry`.
- [ ] Correlation ID scheme (UUID4 per ASSUM-001) is assigned to a specific
      task and its propagation through `dispatch_to_agent` /
      `dispatch_subscribe` is validated.
- [ ] Capability envelope schema (per ASSUM-006) is defined in a task that
      lands before any dispatch-intent tool that consumes it.
- [ ] Task ordering honours the integration-test precondition: registry +
      envelope + at least one core tool must land before the first end-to-end
      dispatch test.
- [ ] `--context` files above are treated as authoritative; any recommendation
      that deviates from them is flagged with an explicit rationale.
- [ ] Security concerns from ASSUM-002/003/004 (`read_file` symlink + null
      byte rejection, `search_web` hostile snippet passthrough) receive
      standard (not deep-dive) coverage in acceptance criteria.
- [ ] Fallback routing behaviours (`search_web` DEGRADED, `asteval` error
      containment) receive standard coverage.
- [ ] A task dependency graph (waves) is produced suitable for AutoBuild
      parallel execution.
- [ ] Integration contracts are surfaced for every cross-task data
      dependency (§4 of IMPLEMENTATION-GUIDE.md).
- [ ] A data-flow diagram of writes/reads for the capability envelope and
      dispatch pipelines is included.

## Test Requirements

Review tasks do not produce code. The test requirement for this task is:

- [ ] The generated subtask plan, when executed end-to-end by AutoBuild,
      must satisfy every `Scenario:` in
      `features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature`
      without further rework.

## Implementation Notes

### Review scope (locked by Context A)

- **Focus**: All aspects (technical + architectural + performance + security)
- **Depth**: Standard
- **Trade-off priority**: Maintainability — clean module boundaries,
  swap-point documentation (DDR-009), grep-for-swap-points discipline.
- **Dedicated concerns**:
  1. Stub transport swap-point safety (DDR-009).
  2. Capability envelope schema evolution (ASSUM-006, snapshot-isolation
     invariant for Phase 3 / FEAT-JARVIS-004).
  3. Correlation ID propagation (ASSUM-001, UUID4, concurrent dispatch
     isolation).
  4. Task ordering constraints — which tools must land before integration
     tests can run.

### Out of dedicated scope (standard coverage only)

- Fallback routing (`search_web` DEGRADED, `asteval` error containment).
- Security boundary deep-dive (`read_file` symlink + null-byte rejection,
  hostile snippet passthrough).

### Review must produce

1. A numbered list of 2–3 technical approaches with pros/cons.
2. A recommended approach with rationale, scored against the four
   dedicated concerns above.
3. A concrete task breakdown (task IDs, titles, complexity 1–10,
   dependencies, `implementation_mode`) suitable for AutoBuild.
4. A wave plan (parallel execution groups) and a §4 Integration Contracts
   section for every cross-task data dependency.
5. A data-flow diagram (writes/reads) and — given complexity ≥ 5 — an
   integration contract sequence diagram.

## Test Execution Log

_Populated during `/task-review` execution._
