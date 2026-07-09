---
id: TASK-SPL003-J04
title: "jarvis: scenario + contract test suite + forge details fixture (FEAT-SPL-003)"
status: completed
completed: 2026-07-09
priority: high
task_type: testing
parent_review: TASK-REV-A387
feature_id: FEAT-SPL-003
wave: 5
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: [TASK-SPL003-J01, TASK-SPL003-J02, TASK-SPL003-J03a, TASK-SPL003-J03b]
tags: [sovereign-planning-loop, feat-spl-003, contract, tests]
---

> **✅ COMPLETED 2026-07-09 (WS3-S7 tracker rollup).** Shipped + reviewed +
> accepted on jarvis `origin/main` at `ebe320e`
> (`test(FEAT-SPL-003 J04): contract suite + forge details fixture + scenario
> guard`). Acceptance criteria verified against the merged tests:
> `test_contract_spl003.py` round-trips the published `ApprovalResponsePayload`
> through installed `nats_core` 0.6.0 with the {accepted, modified, deferred}
> vocabulary guard and decision-literal rule; `tests/fixtures/spl003_forge_details.json`
> is the forge-half `details` contract fixture that J02 renders end-to-end; and
> `test_spl003_scenario_coverage.py` pins the 25-scenario `@task:`-tagged coverage
> (25 scenarios confirmed in the `.feature` file this session). Coach suite re-run
> green this session: `test_contract_spl003.py`, `test_spl003_scenario_coverage.py`,
> `test_contract_nats_core.py`. L11 exec-plan verification (25-scenario contract
> suite, 2775/0) recorded upstream. Moved in_review → `tasks/completed/2026-07/`.

# Task: Scenario + contract test suite + forge details fixture

## Description

The cross-cutting contract layer (SPL-001 TASK-SPL-J03 pattern): pin the wire bytes
against the **installed** `nats_core` 0.6.0, cross-check the 25-scenario coverage, and
pin the forge `details` contract fixture that TASK-SPL003F-001 (forge half) must satisfy.

## Deliverables

1. **`tests/test_contract_spl003.py`** — round-trip the published `ApprovalResponsePayload`
   through the installed `nats_core.events.ApprovalResponsePayload`:
   - `dispositions` is a `list[AssumptionDisposition]`, one per assumption, keyed by
     `assumption_id`; each `disposition` ∈ {`accepted`, `modified`, `deferred`} (NEVER
     `confirmed` / `overridden` / per-item `rejected` — vocabulary drift guard, red-team F7);
     an `edit` carries `edit_delta`; the synonym map (approve→accepted etc.) is honoured.
   - `decision` literal matches the aggregate rule (all accepted→approve; any
     modified/none deferred→approve; any deferred→defer; cancel→reject).
   - `NotificationPayload` optional round-trip fields (`parent_request_id`, `thread_ts`,
     `target_user`, `blocks`) survive a round-trip; a bare payload (no anchor) still parses.
2. **`tests/fixtures/spl003_forge_details.json`** (+ a test asserting J02 renders it) —
   the **contract fixture** for the forge-half `ApprovalRequestPayload.details`:
   `{build_id: "plan-<cid>", feature_id: "FEAT-PLANNING", checkpoint_type: "product_docs",
   expected_approver, attempt_count, parent_request_id, cycle,
   summary: {assumptions: [{id, text, confidence, basis}], ...}}`. This is the schema
   TASK-SPL003F-001 is obligated to emit; J02 renders it end-to-end.
3. **`tests/test_spl003_scenario_coverage.py`** — a collect/coverage guard cross-checking
   all 25 `.feature` scenarios against `@task:` tags (every scenario owned) and asserting
   the scenario-file counts (collect-only pins).

## Acceptance Criteria

- [ ] Published dispositions validate against installed `nats_core` 0.6.0; vocabulary
      guard passes (no confirmed/overridden/per-item rejected on the wire).
- [ ] The forge `details` contract fixture renders a per-assumption prompt in J02.
- [ ] All 25 scenarios are `@task:`-tagged; scenario counts pinned by collect-only.
- [ ] `dispositions` are keyed by `assumption_id` and preserved distinctly.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

```
.venv/bin/python -m pytest tests/test_contract_spl003.py tests/test_spl003_scenario_coverage.py tests/test_contract_nats_core.py -x -q
```
