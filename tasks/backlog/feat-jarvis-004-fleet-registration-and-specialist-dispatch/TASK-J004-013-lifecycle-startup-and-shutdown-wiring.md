---
id: TASK-J004-013
title: "infrastructure/lifecycle.py — NATS + Graphiti + register + heartbeat + drain wiring"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 3
implementation_mode: task-work
complexity: 6
dependencies: [TASK-J004-006, TASK-J004-007, TASK-J004-008, TASK-J004-009, TASK-J004-010, TASK-J004-011, TASK-J004-012]
priority: high
tags: [infrastructure, lifecycle, wiring, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-006
    consumes: NATS_CLIENT_API
    framework: "async nats-py wrapper exposed as NATSClient"
    driver: "nats-py"
    format_note: "lifecycle calls NATSClient.connect (returning None on failure per DDR-021) and NATSClient.drain(timeout=5.0) on shutdown"
  - task: TASK-J004-009
    consumes: CAPABILITIES_REGISTRY_PROTOCOL
    framework: "Protocol unifying Live + Stub registries"
    driver: "in-process Python Protocol"
    format_note: "lifecycle wires LiveCapabilitiesRegistry when nats_client is not None; falls back to StubCapabilitiesRegistry(fallback_path) when None per DDR-021"
  - task: TASK-J004-010
    consumes: ROUTING_HISTORY_WRITER_API
    framework: "Fire-and-forget Graphiti writer (DDR-019)"
    driver: "graphiti-core"
    format_note: "lifecycle calls writer.flush(timeout=5.0) before NATS drain; bounded wait, abandons on timeout with WARN per DDR-019"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-013 — Lifecycle: startup + shutdown wiring

## Description

Extend `src/jarvis/infrastructure/lifecycle.py`'s `build_app_state` and
`shutdown` per [design §8 wiring sequence](../../../docs/design/FEAT-JARVIS-004/design.md):

**Startup** (after FEAT-J003 wiring):

```
nats_client = await NATSClient.connect(config)             # DDR-021 soft-fail
graphiti_client = await GraphitiClient.connect(config)     # DDR-019 soft-fail
routing_history_writer = RoutingHistoryWriter(graphiti_client, config)
if nats_client is not None:
    manifest = build_jarvis_manifest(config)
    await register_on_fleet(nats_client, manifest)
    heartbeat_task = asyncio.create_task(heartbeat_loop(nats_client, manifest, config))
    capabilities_registry = await LiveCapabilitiesRegistry.create(nats_client)
else:
    capabilities_registry = StubCapabilitiesRegistry(config.stub_capabilities_path)
    heartbeat_task = None
dispatch_semaphore = DispatchSemaphore(cap=config.dispatch_concurrent_cap)
tool_list_attended = assemble_tool_list(
    config, capabilities_registry, llamaswap_adapter,
    nats_client=nats_client,
    routing_history_writer=routing_history_writer,
    dispatch_semaphore=dispatch_semaphore,
    include_frontier=True)
tool_list_ambient = assemble_tool_list(
    ...same..., include_frontier=False)
```

**`AppState` extensions** (frozen dataclass): `nats_client`,
`graphiti_client`, `routing_history_writer`, `fleet_heartbeat_task`.

**Shutdown ordering** (TASK-J004-018 verifies this):

```
1. cancel fleet_heartbeat_task (if running)
2. await deregister_from_fleet(nats_client, "jarvis")
3. await capabilities_registry.close()
4. await routing_history_writer.flush(timeout=5.0)
5. await nats_client.drain(timeout=5.0)
6. await graphiti_client.aclose()
7. disarm Layer-2 hooks (kept from FEAT-J003 F1 fix)
8. state.store.close()
```

`assemble_tool_list` extended to accept the three new keyword-only
arguments (`nats_client`, `routing_history_writer`, `dispatch_semaphore`)
which it snapshots into `tools/dispatch.py` module attributes
(`_nats_client`, `_routing_history_writer`, `_dispatch_semaphore`) per
the Phase 2 ASSUM-006 module-attribute pattern.

## Seam Tests

```python
"""Seam test: verify ROUTING_HISTORY_WRITER_API contract from TASK-J004-010."""
import pytest
from unittest.mock import AsyncMock


@pytest.mark.seam
@pytest.mark.integration_contract("ROUTING_HISTORY_WRITER_API")
async def test_lifecycle_calls_writer_flush_with_bounded_timeout():
    """Verify lifecycle.shutdown bounds the writer flush per DDR-019.

    Contract: writer.flush(timeout=5.0) is bounded; lifecycle must pass an
    explicit timeout and tolerate WARN+abandon (no exception propagated up).
    Producer: TASK-J004-010
    """
    from jarvis.infrastructure import lifecycle

    writer = AsyncMock()
    writer.flush = AsyncMock()
    state = _build_state_with(writer=writer)  # fixture helper

    await lifecycle.shutdown(state)

    writer.flush.assert_awaited_once()
    args, kwargs = writer.flush.call_args
    assert "timeout" in kwargs and kwargs["timeout"] <= 5.0, (
        "lifecycle must bound writer.flush at <= 5.0s per DDR-019"
    )
```

## Acceptance Criteria

- [ ] Startup wiring matches design §8 sequence **exactly**.
- [ ] **DDR-021 soft-fail**: `NATSClient.connect` returning `None` does NOT block startup; `capabilities_registry` falls back to `StubCapabilitiesRegistry`; `heartbeat_task = None`.
- [ ] **DDR-019 soft-fail**: `GraphitiClient.connect` failure does NOT block startup; `routing_history_writer` constructed with `graphiti_client=None` (degraded mode).
- [ ] `AppState` gains the four new fields (frozen dataclass — order preserved).
- [ ] `assemble_tool_list` accepts and propagates the three new kwargs to `tools/dispatch.py` module attributes.
- [ ] **Shutdown order** matches the 8-step sequence above; ordering enforced by TASK-J004-018's invariant test.
- [ ] Each shutdown step is independently failure-tolerant — a single failed step (WARN-logged) does not skip later steps.
- [ ] Heartbeat task cancellation produces no traceback (handled by `heartbeat_loop`'s CancelledError contract).
- [ ] `uv run mypy src/jarvis/infrastructure/lifecycle.py` strict-clean.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Unit-level lifecycle tests cover: NATS-up + Graphiti-up happy path; NATS-down → Stub fallback; Graphiti-down → writer in degraded mode; both-down → process still starts; shutdown ordering invariant (TASK-J004-018 owns the strict ordering test).
- [ ] Use `unittest.mock.patch` for `NATSClient.connect`, `GraphitiClient.connect` so soft-fail paths can be exercised deterministically.

## Implementation Notes

The Phase 1 / FEAT-J003 hooks (`_dispatch._current_session_hook`,
`_dispatch._async_subagent_frame_hook`) are **kept** — F1 fix from
FEAT-J003 review.

`graphiti_client.aclose()` is the graphiti-core async-close convention;
swap to whatever the version pinned in TASK-J004-002 actually exports.

The `frontier_default_target` resolution from F6 (FEAT-J003 review)
becomes load-bearing here: `_default_target_hook = lambda:
config.frontier_default_target` is wired during startup so
`escalate_to_frontier` can read the lifecycle-bound default. Verify
this is preserved (FEAT-J003-FIX-002 already wired it; this task does
not regress).

## Test Execution Log

(Populated by /task-work.)
