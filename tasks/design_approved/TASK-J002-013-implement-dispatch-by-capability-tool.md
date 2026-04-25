---
autobuild_state:
  base_branch: main
  current_turn: 3
  last_updated: '2026-04-24T21:22:46.137165'
  max_turns: 30
  started_at: '2026-04-24T20:51:44.454329'
  turns:
  - coach_success: true
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 3 (Implementation), 5 (Code Review). Invoke these agents via
      the Task tool before re-emitting the report:

      - Phase 3: `the stack-specific Phase-3 specialist` (Implementation)

      - Phase 5: `code-reviewer` (Code Review)'
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-24T20:51:44.454329'
    turn: 1
  - coach_success: true
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-24T21:12:57.421680'
    turn: 2
  - coach_success: true
    decision: feedback
    feedback: '- Task-work produced a report with 1 of 3 required agent invocations.
      Missing phases: 4 (Testing), 5 (Code Review). Invoke these agents via the Task
      tool before re-emitting the report:

      - Phase 4: `test-orchestrator` (Testing)

      - Phase 5: `code-reviewer` (Code Review)'
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-24T21:19:12.812755'
    turn: 3
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
complexity: 7
consumer_context:
- consumes: CapabilityDescriptor
  driver: pydantic v2
  format_note: CapabilityDescriptor is a Pydantic v2 BaseModel with ConfigDict(extra='ignore');
    agent_id matches ^[a-z][a-z0-9-]*$; trust_tier is Literal['core','specialist','extension'];
    as_prompt_block() renders deterministic text (see DM-tool-types.md §'Prompt-block
    shape').
  framework: LangChain @tool(parse_docstring=True) + DeepAgents create_deep_agent
  task: TASK-J002-003
- consumes: new_correlation_id
  driver: stdlib
  format_note: new_correlation_id() -> str returning str(uuid.uuid4()); result matches
    ^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$; no shared
    state; safe under concurrent invocation (ASSUM-001).
  framework: stdlib uuid.uuid4
  task: TASK-J002-005
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
- TASK-J002-003
- TASK-J002-004
- TASK-J002-005
- TASK-J002-007
estimated_minutes: 110
feature_id: FEAT-J002
id: TASK-J002-013
implementation_mode: task-work
parent_review: TASK-REV-J002
priority: high
scenarios_covered:
- Dispatching by capability resolves a specialist and returns a successful result
- dispatch_by_capability accepts timeout_seconds only within 5 to 600
- Dispatching by an unknown capability name returns an unresolved error
- dispatch_by_capability rejects payloads that are not JSON object literals
- Dispatching by capability with a simulated timeout returns a timeout error
- Dispatching by capability falls back to intent pattern matching when no exact tool
  match exists
- Stubbed dispatches construct real nats-core payloads before logging
- Concurrent dispatch_by_capability calls produce distinct correlation ids and independent
  log lines
- dispatch_by_capability surfaces specialist-side failures as structured errors
- Every tool converts internal errors into structured strings rather than raising
status: design_approved
swap_point_note: '**PRIMARY DDR-009 SWAP POINT.** Grep anchors: `JARVIS_DISPATCH_STUB`
  (the log-line prefix), `_stub_response_hook` (the hook attribute). FEAT-JARVIS-004
  replaces the `logger.info` call with `await nats.request(...)` and removes `_stub_response_hook`;
  tool docstring and return shape are untouched.'
tags:
- phase-2
- jarvis
- feat-jarvis-002
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Implement dispatch_by_capability tool
updated: 2026-04-24 06:55:00+00:00
wave: 2
---

# Implement dispatch_by_capability tool

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** task-work | **Complexity:** 7/10 | **Est.:** 110 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

The primary dispatch tool. Resolves tool_name → agent_id against the capability registry (exact match, then intent_pattern fallback). Constructs real nats-core CommandPayload + MessageEnvelope. Emits exactly one JARVIS_DISPATCH_STUB log line. Honours _stub_response_hook for testability. This is the PRIMARY DDR-009 swap point.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py` exposes `dispatch_by_capability(tool_name: str, payload_json: str, intent_pattern: str | None = None, timeout_seconds: int = 60) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring matches API-tools.md §3.1 byte-for-byte.
- [ ] Resolution: exact `CapabilityToolSummary.tool_name` match wins; else `intent_pattern` substring match on descriptor `role`/`description` with highest-confidence (first match on lexicographic agent_id order for stability); else `ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>`.
- [ ] Validates `payload_json` is a JSON object literal (starts with `{`, parses to dict). Non-object / non-JSON → `ERROR: invalid_payload — payload_json is not a JSON object literal`.
- [ ] Validates `timeout_seconds` in `[5, 600]`. Out of range → `ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>`.
- [ ] Constructs a real `nats_core.events.CommandPayload` with `command=tool_name`, `args=json.loads(payload_json)`, `correlation_id=new_correlation_id()` (uses TASK-J002-005 helper).
- [ ] Constructs a real `MessageEnvelope(source_id="jarvis", event_type=EventType.COMMAND, correlation_id=..., payload=command.model_dump(mode="json"))`.
- [ ] Emits exactly one `logger.info` call per invocation with message starting with `LOG_PREFIX_DISPATCH` (= `"JARVIS_DISPATCH_STUB"`) and containing `tool_name=<x> agent_id=<y> correlation_id=<z> topic=agents.command.<y> payload_bytes=<n>` in the rendered line.
- [ ] Honours `_stub_response_hook`: unset → returns canned `ResultPayload` JSON with `success=True, result={"stub":True,"tool_name":<x>}, correlation_id=<same>`; `timeout` → `TIMEOUT: agent_id=<y> tool_name=<x> timeout_seconds=<n>`; `specialist_error` → `ERROR: specialist_error — agent_id=<y> detail=<reason>`.
- [ ] No retry inside the tool (DDR-009 §6); error string returned verbatim.
- [ ] Concurrent dispatches produce distinct correlation IDs; two parallel invocations yield two distinct `JARVIS_DISPATCH_STUB` log lines, each carrying its own correlation_id.
- [ ] Seam test: dispatches succeed end-to-end through `assemble_tool_list`-wired supervisor fixture; log capture verifies exactly-one log line per call.
- [ ] Never raises; Pydantic ValidationError on MessageEnvelope construction is caught and returned as `ERROR: validation — <detail>`.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Dispatching by capability resolves a specialist and returns a successful result
- dispatch_by_capability accepts timeout_seconds only within 5 to 600
- Dispatching by an unknown capability name returns an unresolved error
- dispatch_by_capability rejects payloads that are not JSON object literals
- Dispatching by capability with a simulated timeout returns a timeout error
- Dispatching by capability falls back to intent pattern matching when no exact tool match exists
- Stubbed dispatches construct real nats-core payloads before logging
- Concurrent dispatch_by_capability calls produce distinct correlation ids and independent log lines
- dispatch_by_capability surfaces specialist-side failures as structured errors
- Every tool converts internal errors into structured strings rather than raising

## Swap-Point Note

**PRIMARY DDR-009 SWAP POINT.** Grep anchors: `JARVIS_DISPATCH_STUB` (the log-line prefix), `_stub_response_hook` (the hook attribute). FEAT-JARVIS-004 replaces the `logger.info` call with `await nats.request(...)` and removes `_stub_response_hook`; tool docstring and return shape are untouched.

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