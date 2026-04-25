---
id: TASK-J002-014
title: Implement queue_build tool
task_type: feature
status: blocked
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 6
wave: 2
implementation_mode: task-work
estimated_minutes: 90
dependencies:
- TASK-J002-004
- TASK-J002-005
- TASK-J002-007
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Queueing a build for a planned feature returns an acknowledgement
- queue_build validates feature_id against the documented pattern
- queue_build validates repo against the org/name pattern
- queue_build restricts originating_adapter to the documented values
- Stubbed queue_build constructs a real BuildQueuedPayload before logging
- Every tool converts internal errors into structured strings rather than raising
consumer_context:
- task: TASK-J002-005
  consumes: new_correlation_id
  framework: stdlib uuid.uuid4
  driver: stdlib
  format_note: new_correlation_id() -> str returning str(uuid.uuid4()); result matches
    ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$; no shared
    state; safe under concurrent invocation (ASSUM-001).
- task: TASK-J002-007
  consumes: _stub_response_hook + LOG_PREFIX constants
  framework: DDR-009 swap-point discipline
  driver: stdlib logging + nats_core.events models
  format_note: '_stub_response_hook: Callable[[CommandPayload], StubResponse] | None
    = None; module-level LOG_PREFIX_DISPATCH=''JARVIS_DISPATCH_STUB'' and LOG_PREFIX_QUEUE_BUILD=''JARVIS_QUEUE_BUILD_STUB''
    are the grep anchors. grep -rn must return exactly 4 lines (2 constants + 2 logger.info
    usages) post-Wave-3.'
swap_point_note: '**PRIMARY DDR-009 SWAP POINT.** Grep anchor: `JARVIS_QUEUE_BUILD_STUB`.
  FEAT-JARVIS-005 replaces the `logger.info` call with `await js.publish(subject=Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id),
  payload=envelope.model_dump_json().encode())`. Tool docstring and return shape untouched.'
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 3
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-24T20:51:44.452060'
  last_updated: '2026-04-24T21:24:45.621326'
  turns:
  - turn: 1
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    timestamp: '2026-04-24T20:51:44.452060'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    timestamp: '2026-04-24T21:16:53.773517'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 3
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    timestamp: '2026-04-24T21:20:56.195739'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---
# Implement queue_build tool

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** task-work | **Complexity:** 6/10 | **Est.:** 90 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

The build-queue publisher tool. Validates feature_id / repo / originating_adapter, constructs a real BuildQueuedPayload + MessageEnvelope, emits one JARVIS_QUEUE_BUILD_STUB log line, and returns a QueueBuildAck JSON. PRIMARY DDR-009 swap point (FEAT-JARVIS-005).

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py` exposes `queue_build(feature_id: str, feature_yaml_path: str, repo: str, branch: str = "main", originating_adapter: str = "terminal", correlation_id: str | None = None, parent_request_id: str | None = None) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring matches API-tools.md §3.2 byte-for-byte.
- [ ] Validates `feature_id` against `^FEAT-[A-Z0-9]{3,12}$`; rejects invalid with `ERROR: invalid_feature_id — must match FEAT-XXX pattern, got <value>`.
- [ ] Validates `repo` against `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`; rejects invalid with `ERROR: invalid_repo — must be org/name format, got <value>`.
- [ ] Validates `originating_adapter` in `{terminal, telegram, dashboard, voice-reachy, slack, cli-wrapper}`; rejects other with `ERROR: invalid_adapter — <value> not in allowed list`.
- [ ] Constructs real `BuildQueuedPayload` with `triggered_by="jarvis"`, `originating_adapter=<value>`, `correlation_id=correlation_id or new_correlation_id()`, `requested_at=now_utc()`, `queued_at=now_utc()`.
- [ ] Constructs real `MessageEnvelope(source_id="jarvis", event_type=EventType.BUILD_QUEUED, correlation_id=..., payload=...)`.
- [ ] Emits exactly one `logger.info` call with message starting with `LOG_PREFIX_QUEUE_BUILD` (= `"JARVIS_QUEUE_BUILD_STUB"`) and containing `feature_id=<x> repo=<y> correlation_id=<z> topic=pipeline.build-queued.<x> payload_bytes=<n>`.
- [ ] Returns `QueueBuildAck` JSON: `{"feature_id":<x>,"correlation_id":<z>,"queued_at":<iso>,"publish_target":"pipeline.build-queued.<x>","status":"queued"}`.
- [ ] Uses `Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)` — singular-topic ADR-SP-016 compliant.
- [ ] Pydantic ValidationError caught at tool boundary → `ERROR: validation — <pydantic detail>` (ADR-ARCH-021).
- [ ] Never raises.
- [ ] Seam test: dispatches succeed end-to-end through `assemble_tool_list`-wired supervisor fixture; payload JSON round-trips through `BuildQueuedPayload.model_validate_json`.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Queueing a build for a planned feature returns an acknowledgement
- queue_build validates feature_id against the documented pattern
- queue_build validates repo against the org/name pattern
- queue_build restricts originating_adapter to the documented values
- Stubbed queue_build constructs a real BuildQueuedPayload before logging
- Every tool converts internal errors into structured strings rather than raising

## Swap-Point Note

**PRIMARY DDR-009 SWAP POINT.** Grep anchor: `JARVIS_QUEUE_BUILD_STUB`. FEAT-JARVIS-005 replaces the `logger.info` call with `await js.publish(subject=Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id), payload=envelope.model_dump_json().encode())`. Tool docstring and return shape untouched.

## Seam Tests

The following seam test(s) validate the integration contract(s) with the producer task(s). Implement before integration.

```python
"""Seam test: verify _stub_response_hook + LOG_PREFIX constants contract from TASK-J002-007."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("_stub_response_hook + LOG_PREFIX constants")
def test__stub_response_hook_contract():
    """Verify _stub_response_hook + LOG_PREFIX constants matches the expected format.

    Contract: _stub_response_hook: Callable[[CommandPayload], StubResponse] | None = None; module-level LOG_PREFIX_DISPATCH='JARVIS_DISPATCH_STUB' and LOG_PREFIX_QUEUE_BUILD='JARVIS_QUEUE_BUILD_STUB' are the grep anchors. grep -rn must return exactly 4 lines (2 constants + 2 logger.info usages) post-Wave-3.
    Producer: TASK-J002-007
    """
    # Producer side: acquire the artifact.
    # e.g.: from jarvis.tools.dispatch import _stub_response_hook, LOG_PREFIX_DISPATCH
    # Consumer side: verify format matches contract.
    # e.g.: assert LOG_PREFIX_DISPATCH == "JARVIS_DISPATCH_STUB"
    raise NotImplementedError("Implement the seam assertion derived from the contract above.")
```

## Test Execution Log

_Populated by `/task-work` during implementation._
