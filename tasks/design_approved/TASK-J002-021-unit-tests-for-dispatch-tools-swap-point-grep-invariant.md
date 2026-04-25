---
complexity: 6
consumer_context:
- consumes: _stub_response_hook + LOG_PREFIX constants
  driver: stdlib logging + nats_core.events models
  format_note: '_stub_response_hook: Callable[[CommandPayload], StubResponse] | None
    = None; module-level LOG_PREFIX_DISPATCH=''JARVIS_DISPATCH_STUB'' and LOG_PREFIX_QUEUE_BUILD=''JARVIS_QUEUE_BUILD_STUB''
    are the grep anchors. grep -rn must return exactly 4 lines (2 constants + 2 logger.info
    usages) post-Wave-3.'
  framework: DDR-009 swap-point discipline
  task: TASK-J002-007
created: 2026-04-24 06:55:00+00:00
dependencies:
- TASK-J002-007
- TASK-J002-013
- TASK-J002-014
estimated_minutes: 110
feature_id: FEAT-J002
id: TASK-J002-021
implementation_mode: task-work
parent_review: TASK-REV-J002
priority: high
scenarios_covered:
- Dispatching by capability resolves a specialist and returns a successful result
- Queueing a build for a planned feature returns an acknowledgement
- dispatch_by_capability accepts timeout_seconds only within 5 to 600
- queue_build validates feature_id against the documented pattern
- queue_build validates repo against the org/name pattern
- queue_build restricts originating_adapter to the documented values
- Dispatching by an unknown capability name returns an unresolved error
- dispatch_by_capability rejects payloads that are not JSON object literals
- Dispatching by capability with a simulated timeout returns a timeout error
- Dispatching by capability falls back to intent pattern matching when no exact tool
  match exists
- Stubbed dispatches construct real nats-core payloads before logging
- Stubbed queue_build constructs a real BuildQueuedPayload before logging
- Concurrent dispatch_by_capability calls produce distinct correlation ids and independent
  log lines
- dispatch_by_capability surfaces specialist-side failures as structured errors
status: design_approved
swap_point_note: Contains the **grep-invariant test** that guards DDR-009. If this
  test fails, a swap-point anchor has drifted and FEAT-JARVIS-004/005 will lose its
  landmark.
tags:
- phase-2
- jarvis
- feat-jarvis-002
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: Unit tests for dispatch tools + swap-point grep invariant
updated: 2026-04-24 06:55:00+00:00
wave: 4
---

# Unit tests for dispatch tools + swap-point grep invariant

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 4 | **Mode:** task-work | **Complexity:** 6/10 | **Est.:** 110 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

pytest suite for dispatch_by_capability and queue_build, including the grep-invariant test that guards the DDR-009 swap-point anchors. Uses fake_dispatch_stub to flip _stub_response_hook between success / timeout / specialist_error modes.

## Acceptance Criteria

- [ ] `tests/test_tools_dispatch.py` covers every dispatch-targeted scenario in `.feature`.
- [ ] `dispatch_by_capability`: happy path resolves `run_architecture_session` → `architect-agent`; intent-pattern fallback; timeout_seconds table (5, 60, 600, 4, 601); invalid JSON payload table; unresolved; simulated timeout via `_stub_response_hook`; specialist_error via `_stub_response_hook`; concurrent dispatch produces distinct UUIDs (ThreadPoolExecutor with 2 parallel calls, assert `{id_a} != {id_b}`, assert 2 log lines with matching correlation_ids).
- [ ] `queue_build`: happy path; feature_id table (FEAT-AB1, FEAT-JARVIS-EXAMPLE01 accept; FEAT-AB, feat-jarvis-002, BUG-JARVIS-001 reject); repo table (accept/reject per Gherkin); originating_adapter table (accept/reject per Gherkin).
- [ ] Asserts log lines match exact format: `JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y> correlation_id=<z> topic=agents.command.<y> payload_bytes=<n>`; same format pattern for `JARVIS_QUEUE_BUILD_STUB`.
- [ ] Asserts real `CommandPayload` and `BuildQueuedPayload` instances (not dicts) are constructed — `isinstance` check on captured object.
- [ ] **Swap-point grep invariant test:** a helper runs `grep -rn "JARVIS_DISPATCH_STUB\|JARVIS_QUEUE_BUILD_STUB" src/jarvis/` and asserts the result contains exactly the expected lines (2 constants + 2 usages = 4 lines minimum, all in `src/jarvis/tools/dispatch.py`). Test fails if anchor leaks to another module or anchor name drifts.
- [ ] Uses `fake_dispatch_stub` fixture to flip `_stub_response_hook` between modes.

## Scenarios Covered

- Dispatching by capability resolves a specialist and returns a successful result
- Queueing a build for a planned feature returns an acknowledgement
- dispatch_by_capability accepts timeout_seconds only within 5 to 600
- queue_build validates feature_id against the documented pattern
- queue_build validates repo against the org/name pattern
- queue_build restricts originating_adapter to the documented values
- Dispatching by an unknown capability name returns an unresolved error
- dispatch_by_capability rejects payloads that are not JSON object literals
- Dispatching by capability with a simulated timeout returns a timeout error
- Dispatching by capability falls back to intent pattern matching when no exact tool match exists
- Stubbed dispatches construct real nats-core payloads before logging
- Stubbed queue_build constructs a real BuildQueuedPayload before logging
- Concurrent dispatch_by_capability calls produce distinct correlation ids and independent log lines
- dispatch_by_capability surfaces specialist-side failures as structured errors

## Swap-Point Note

Contains the **grep-invariant test** that guards DDR-009. If this test fails, a swap-point anchor has drifted and FEAT-JARVIS-004/005 will lose its landmark.

## Test Execution Log

_Populated by `/task-work` during implementation._