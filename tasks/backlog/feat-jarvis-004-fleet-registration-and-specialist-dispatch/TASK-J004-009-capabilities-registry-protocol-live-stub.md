---
id: TASK-J004-009
title: "infrastructure/capabilities_registry.py — Protocol + Live + Stub"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 2
implementation_mode: task-work
complexity: 6
dependencies: [TASK-J004-003, TASK-J004-006]
priority: high
tags: [infrastructure, capabilities, kv-watch, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-006
    consumes: NATS_CLIENT_API
    framework: "async nats-py wrapper exposed as NATSClient"
    driver: "nats-py"
    format_note: "LiveCapabilitiesRegistry consumes the wrapper's `client` property + `js` JetStream context for KV operations; never bypasses the wrapper to call nats.connect directly"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-009 — CapabilitiesRegistry: Protocol + LiveCapabilitiesRegistry + StubCapabilitiesRegistry

## Description

Land `src/jarvis/infrastructure/capabilities_registry.py` per
[API-internal.md §3](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md):

- **Protocol `CapabilitiesRegistry`** with `snapshot() -> list[CapabilityDescriptor]`,
  `refresh() -> None`, `subscribe_updates(callback) -> None`, `close() -> None`.
- **`LiveCapabilitiesRegistry`** — backed by `NATSKVManifestRegistry`
  with **30s cache** + KV-watch invalidation per ADR-ARCH-017. Created
  via `await LiveCapabilitiesRegistry.create(client, *, cache_ttl_seconds=30)`.
- **`StubCapabilitiesRegistry`** — DDR-021 soft-fail fallback that
  reads from `config.stub_capabilities_path` (the existing Phase 2 YAML).
  Same Protocol surface; `subscribe_updates` is a no-op.

Plus `tests/test_capabilities_registry_unit.py` covering: 30s cache
window, KV-watch callback invalidates the cache, snapshot isolation
(callers can iterate without seeing concurrent invalidation), stub
fallback returns the YAML-loaded descriptor list.

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify NATS_CLIENT_API contract from TASK-J004-006."""
import pytest
from unittest.mock import AsyncMock


@pytest.mark.seam
@pytest.mark.integration_contract("NATS_CLIENT_API")
async def test_nats_client_api_consumed_by_capabilities_registry():
    """Verify LiveCapabilitiesRegistry consumes NATSClient via the wrapper.

    Contract: LiveCapabilitiesRegistry.create takes a NATSClient instance
    (not a bare nats.aio.client.Client) and accesses NATS via the wrapper's
    `client` and `js` properties only.
    Producer: TASK-J004-006
    """
    from jarvis.infrastructure.nats_client import NATSClient
    from jarvis.infrastructure.capabilities_registry import LiveCapabilitiesRegistry

    # Producer side: NATSClient exposes `client` and `js`.
    fake_client = AsyncMock(spec=NATSClient)

    # Consumer side: registry constructor must accept a NATSClient.
    # Format assertion: signature accepts NATSClient, not Client directly.
    import inspect
    sig = inspect.signature(LiveCapabilitiesRegistry.create)
    client_param = sig.parameters.get("client")
    assert client_param is not None, "create(client=...) parameter must exist"
    annotation = str(client_param.annotation)
    assert "NATSClient" in annotation, (
        f"create() must accept NATSClient (the wrapper), not bare nats.aio.Client; "
        f"got annotation: {annotation}"
    )
```

## Acceptance Criteria

- [ ] `CapabilitiesRegistry` Protocol declared with all four methods + correct return types.
- [ ] `LiveCapabilitiesRegistry.create(client, cache_ttl_seconds=30)` returns a usable instance; first `snapshot()` triggers a fresh KV read; subsequent reads inside `cache_ttl_seconds` return the cached list.
- [ ] KV-watch callback invalidates the cache — next `snapshot()` re-reads.
- [ ] `snapshot()` returns a fresh `list` copy — mutating the result does not affect the cache.
- [ ] `subscribe_updates(callback)` — calling more than once per session is idempotent (no double-subscription, no double-fire).
- [ ] `close()` is idempotent; detaches the watcher; closes the underlying KV handle.
- [ ] `StubCapabilitiesRegistry(fallback_path)` reads YAML, exposes the same Protocol surface; `subscribe_updates` is a no-op.
- [ ] If `client.js` (JetStream context) is unavailable for KV access, `LiveCapabilitiesRegistry.create` raises `NATSConnectionError` (lifecycle catches and falls back to Stub per DDR-021).
- [ ] `uv run mypy src/jarvis/infrastructure/capabilities_registry.py` strict-clean.
- [ ] Tests cover all bullet points above with the in-process NATS test server fixture for the Live path.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Live path tests use an in-process NATS server with a pre-seeded KV bucket.
- [ ] Stub path tests use a tmp_path YAML fixture mirroring `config/stub_capabilities.yaml`.
- [ ] Snapshot-isolation test: take a snapshot, mutate it, re-snapshot — second snapshot unchanged.

## Implementation Notes

The Forge convention for `NATSKVManifestRegistry` cache + watch is the
reference (per phase3-build-plan §Risk Mitigation). If the
nats-core convention differs, isolate the divergence in this module
(ASSUM-NATS-KV-WATCH carry-forward) — do not propagate it upward.

The 30s cache is operator-tunable via `cache_ttl_seconds` parameter so
integration tests can use 0 (no cache) for KV-watch invalidation
assertions.

## Test Execution Log

(Populated by /task-work.)
