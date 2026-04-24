---
id: TASK-J002-007
title: "Stub-response-hook contract for dispatch"
task_type: scaffolding
status: backlog
created: 2026-04-24T06:55:00Z
updated: 2026-04-24T06:55:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 30
dependencies: []
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags: [phase-2, jarvis, feat-jarvis-002]
scenarios_covered:
  - "Stubbed dispatches construct real nats-core payloads before logging"
  - "Stubbed queue_build constructs a real BuildQueuedPayload before logging"
swap_point_note: "Establishes the grep anchors required by DDR-009. Test TASK-J002-021 asserts the grep-count invariant."
test_results:
  status: pending
  coverage: null
  last_run: null
---
# Stub-response-hook contract for dispatch

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10 | **Est.:** 30 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Establish the named swap seam for dispatch. Creates the `_stub_response_hook` attribute, the StubResponse typed-dict/Literal union, and the two LOG_PREFIX constants. These are the DDR-009 grep anchors FEAT-JARVIS-004/005 will target.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py` defines a module-level attribute `_stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None`.
- [ ] Defines `StubResponse` as a typed dict / Literal union covering `("success", ResultPayload) | ("timeout",) | ("specialist_error", str)`.
- [ ] Defines module-level string constants `LOG_PREFIX_DISPATCH = "JARVIS_DISPATCH_STUB"` and `LOG_PREFIX_QUEUE_BUILD = "JARVIS_QUEUE_BUILD_STUB"`.
- [ ] Module docstring carries a "SWAP POINT" section naming the two grep anchors and stating that FEAT-JARVIS-004 replaces `_stub_response_hook` with a real NATS round-trip.
- [ ] `grep -rn "JARVIS_DISPATCH_STUB\|JARVIS_QUEUE_BUILD_STUB" src/jarvis/` returns exactly two lines (the two constant definitions) pre-feature wiring; after TASK-J002-013 and TASK-J002-014 land, it returns exactly four (two definitions + two `logger.info` usages).

## Scenarios Covered

- Stubbed dispatches construct real nats-core payloads before logging
- Stubbed queue_build constructs a real BuildQueuedPayload before logging

## Swap-Point Note

Establishes the grep anchors required by DDR-009. Test TASK-J002-021 asserts the grep-count invariant.

## Test Execution Log

_Populated by `/task-work` during implementation._
