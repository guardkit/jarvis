---
id: TASK-J004-011
title: "tools/dispatch.py — real dispatch_by_capability transport swap"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 3
implementation_mode: task-work
complexity: 7
dependencies: [TASK-J004-006, TASK-J004-008, TASK-J004-009, TASK-J004-010]
priority: high
tags: [tools, dispatch, transport, retry, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-006
    consumes: NATS_CLIENT_API
    framework: "async nats-py wrapper exposed as NATSClient"
    driver: "nats-py"
    format_note: "dispatch consumes NATSClient.request(subject, payload, *, timeout); subject is built via nats_core.Topics formatters; payload is bytes (envelope.model_dump_json().encode())"
  - task: TASK-J004-008
    consumes: DISPATCH_SEMAPHORE_API
    framework: "asyncio.Semaphore wrapper"
    driver: "asyncio"
    format_note: "dispatch must use try_acquire() (synchronous, non-blocking); on False, return DEGRADED string immediately without awaiting; release() always called in finally block"
  - task: TASK-J004-009
    consumes: CAPABILITIES_REGISTRY_PROTOCOL
    framework: "Protocol unifying Live + Stub registries"
    driver: "in-process Python Protocol"
    format_note: "dispatch reads via .snapshot() returning fresh list; never mutates the snapshot; resolution iterates lexicographically by agent_id (DDR-017 determinism invariant)"
  - task: TASK-J004-010
    consumes: ROUTING_HISTORY_WRITER_API
    framework: "Fire-and-forget Graphiti writer (DDR-019)"
    driver: "graphiti-core"
    format_note: "dispatch calls asyncio.create_task(writer.write_specialist_dispatch(entry)) at every outcome; never awaits the write; never raises on writer failure"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-011 — tools/dispatch.py: real dispatch_by_capability transport swap

## Description

Swap the body of `dispatch_by_capability` in `src/jarvis/tools/dispatch.py`
from the Phase 2 stub to the real NATS round-trip per
[design §8 dispatch_by_capability runtime sequence](../../../docs/design/FEAT-JARVIS-004/design.md):

1. Generate `correlation_id`, validate `timeout_seconds` (5..600) and
   `payload_json` (must be JSON object literal).
2. `_dispatch_semaphore.try_acquire()` — overflow → `DEGRADED: dispatch_overloaded — wait and retry`.
3. Loop: `attempt_index ∈ {0, 1}` (`MAX_REDIRECTS=1` per DDR-017):
   - `_resolve_agent_id(tool_name, intent_pattern, registry, exclude=visited)`
     — `None` → outcome=exhausted-or-unresolved; write trace; release; return error.
   - `visited.add(agent_id)`.
   - Build `CommandPayload` + `MessageEnvelope(source_id="jarvis", ...)`.
   - `await asyncio.wait_for(_nats_client.request("agents.command.{agent_id}", envelope.encode(), timeout=...), timeout=timeout_seconds)`.
   - On reply success → write trace (outcome="success" or "redirected"); release; return result JSON.
   - On reply failure → append RedirectAttempt; continue loop.
   - On `asyncio.TimeoutError` → append RedirectAttempt(reason="timeout"); continue.
   - On `NATSConnectionError` → outcome="transport_unavailable"; write trace; release; return DEGRADED.
4. Loop exit → outcome="exhausted"; write trace; release; return TIMEOUT.

**Trace writes are always fire-and-forget**: `asyncio.create_task(_routing_history_writer.write_specialist_dispatch(entry))`.
The dispatch never awaits the Graphiti write.

**Module-level swap-point attributes** added:

```python
_nats_client: NATSClient | None = None
_routing_history_writer: RoutingHistoryWriter | None = None
_dispatch_semaphore: DispatchSemaphore | None = None
```

`assemble_tool_list` (TASK-J004-013) populates these.

**Phase 2 anchors retired** in this same task:

- `_stub_response_hook` — deleted.
- `LOG_PREFIX_DISPATCH` constant — deleted.
- TASK-J002-021 grep invariant test — flipped from "must contain LOG_PREFIX_DISPATCH" to "must NOT contain LOG_PREFIX_DISPATCH" (the retirement gate). The flip lives in TASK-J004-020.

**Docstring deltas**:

- Delete the Phase 2 paragraph ("In Phase 2 the transport is stubbed: ...").
- Delete the existing `DEGRADED: transport_stub —` line.
- Add `DEGRADED: dispatch_overloaded — wait and retry` (DDR-020).
- Add `DEGRADED: transport_unavailable — NATS connection failed` (DDR-021).

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify NATS_CLIENT_API contract from TASK-J004-006."""
import pytest
from unittest.mock import AsyncMock


@pytest.mark.seam
@pytest.mark.integration_contract("NATS_CLIENT_API")
async def test_dispatch_consumes_nats_client_request_signature():
    """Verify dispatch_by_capability calls NATSClient.request with the contract shape.

    Contract: request(subject, payload, *, timeout) — subject is str, payload is
    bytes, timeout is keyword-only float. Subject is built via nats_core.Topics,
    never hard-coded.
    Producer: TASK-J004-006
    """
    from jarvis.tools import dispatch as dispatch_module
    from jarvis.infrastructure.nats_client import NATSClient

    nats_client = AsyncMock(spec=NATSClient)
    nats_client.request = AsyncMock()
    dispatch_module._nats_client = nats_client
    # ... set _routing_history_writer, _dispatch_semaphore, _capability_registry ...

    # Invoke dispatch (with a mocked _resolve_agent_id returning a known agent_id).
    # Assert the call signature.
    # ...
    args, kwargs = nats_client.request.call_args
    subject = args[0] if args else kwargs.get("subject")
    payload = args[1] if len(args) > 1 else kwargs.get("payload")
    assert isinstance(subject, str), "subject must be str"
    assert isinstance(payload, bytes), "payload must be bytes (envelope.model_dump_json().encode())"
    assert "timeout" in kwargs, "timeout must be keyword-only"
    assert subject.startswith("agents.command."), (
        "subject must follow nats_core.Topics.command(...) singular convention"
    )
```

## Acceptance Criteria

- [ ] `dispatch_by_capability` body matches design §8 sequence verbatim.
- [ ] Tool signature, parse_docstring, return-shape **byte-identical** to Phase 2 (the reasoning model's view is unchanged).
- [ ] `MessageEnvelope.source_id == "jarvis"` on every emitted envelope.
- [ ] All NATS subjects produced via `nats_core.Topics.*` formatters; no hard-coded literals (`agents.command.foo` strings) in this module.
- [ ] Visited-set prevents loops on retry-with-redirect; `_resolve_agent_id(exclude=visited)` is called.
- [ ] `MAX_REDIRECTS=1` (2 total attempts max per DDR-017); exceeded → outcome="exhausted".
- [ ] Lexicographic resolution order (DDR-017 determinism) preserved — testable via integration test in TASK-J004-015.
- [ ] Semaphore is released in **every** outcome path (use `try` / `finally` or context-manager pattern).
- [ ] Trace writes via `asyncio.create_task(...)` — never `await` the writer call from inside dispatch.
- [ ] `_stub_response_hook` and `LOG_PREFIX_DISPATCH` are deleted from this file.
- [ ] Phase 2 docstring paragraph deleted; new DEGRADED return-shape lines added per design §10.
- [ ] `uv run mypy src/jarvis/tools/dispatch.py` strict-clean.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Unit-level tests (in this task or alongside TASK-J004-015) cover: timeout-range validation, payload-object validation, semaphore-overflow synchronous DEGRADED, `MessageEnvelope.source_id="jarvis"`, fire-and-forget trace writes (assert `create_task` was called).
- [ ] Integration tests (TASK-J004-015) own the round-trip / redirect / exhausted matrix.

## Implementation Notes

The `_resolve_agent_id` helper from Phase 2 already exists in this
module. This task adds the `exclude: set[str]` parameter and confirms
the lexicographic ordering invariant. Do not relocate the function.

The `asyncio.create_task(writer.write_specialist_dispatch(entry))`
pattern intentionally swallows the returned task — the writer's WARN
log is the only failure surface. Storing the task in a module-level
set is unnecessary in v1 (the writer's `flush()` on shutdown bounds
the wait).

## Test Execution Log

(Populated by /task-work.)
