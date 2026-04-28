---
complexity: 4
created: 2026-04-27 15:30:00+00:00
dependencies:
- TASK-J004-013
feature_id: FEAT-JARVIS-004
id: TASK-J004-017
implementation_mode: task-work
parent_review: TASK-REV-22CF
priority: high
status: design_approved
tags:
- tests
- regression
- semaphore
- dispatch-outcome
- FEAT-JARVIS-004
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: tests/test_dispatch_slot_release.py — Scenario Outline 5-row regression
wave: 4
---

# TASK-J004-017 — Dispatch slot-release Scenario Outline regression

## Description

Land `tests/test_dispatch_slot_release.py` covering the 5-row
`Scenario Outline: The concurrent dispatch slot is released on every
dispatch outcome` (line 352 of the .feature). This is the canonical
regression that protects DDR-020's semaphore from silent slot-leak
bugs across all five `DispatchOutcome` literals reachable from the
dispatch tool path:

| Row | Outcome | Setup |
|---|---|---|
| 1 | `success` | Mock specialist replies success=True |
| 2 | `timeout` | No specialist subscribed; `timeout_seconds=1` |
| 3 | `specialist_error` | Mock specialist replies success=False (no redirect candidate) |
| 4 | `transport_unavailable` | NATS client.request raises NATSConnectionError |
| 5 | `unresolved` | No capability matches the requested tool_name on first attempt |

For each row, the test:

1. Constructs a `DispatchSemaphore(cap=2)` so we can detect leaks via
   slot count.
2. Pre-acquires 1 slot (`in_flight=1`).
3. Triggers a dispatch matching the row's outcome.
4. Asserts the dispatch returned the expected outcome string / error.
5. Asserts `semaphore.in_flight == 1` at the end (only the
   pre-acquired slot remains; the dispatch released its slot).

## Acceptance Criteria

- [ ] One parametrised test with 5 rows covering all five `DispatchOutcome` literals reachable from `dispatch_by_capability`.
- [ ] Each row asserts the slot is released — `in_flight` invariant after dispatch.
- [ ] No row uses `pytest.xfail` or `pytest.skip` — all five must pass.
- [ ] The test does NOT cover `redirected` or `exhausted` outcomes (those are owned by TASK-J004-015's redirect matrix); this test is specifically the slot-release invariant on the closed five-set.
- [ ] `uv run pytest tests/test_dispatch_slot_release.py -v` green.

## Test Requirements

- [ ] In-process NATS server fixture for rows 1–3 (real reply / no reply / error reply).
- [ ] Mock `NATSClient.request` to raise `NATSConnectionError` for row 4.
- [ ] Stub `_capability_registry.snapshot()` to return an empty list for row 5.

## Implementation Notes

This is the dispatch-semaphore equivalent of FEAT-J002's
"every-tool-returns-structured-error" regression. The bug it
catches (silent slot leak under one specific outcome path) is
exactly the kind of regression that goes undetected for months
without it.

The Scenario Outline at .feature line 352 carries the 5 rows — the
test docstring should reference both the Outline title and the row
labels so future failures point at the spec line.

## Test Execution Log

(Populated by /task-work.)