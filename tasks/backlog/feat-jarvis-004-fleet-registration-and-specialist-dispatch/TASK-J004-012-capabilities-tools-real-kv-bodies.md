---
id: TASK-J004-012
title: "tools/capabilities.py — real KV-backed bodies for list / refresh / subscribe_updates"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 3
implementation_mode: task-work
complexity: 4
dependencies: [TASK-J004-009]
priority: high
tags: [tools, capabilities, kv-watch, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-009
    consumes: CAPABILITIES_REGISTRY_PROTOCOL
    framework: "Protocol unifying Live + Stub registries"
    driver: "in-process Python Protocol"
    format_note: "tools/capabilities.py reads from a CapabilitiesRegistry instance via the Protocol surface only (.snapshot/.refresh/.subscribe_updates/.close); never branches on Live vs Stub"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-012 — tools/capabilities.py: real KV-backed bodies

## Description

Swap the three capability tools in `src/jarvis/tools/capabilities.py`
from Phase 2 stubs to real KV-backed bodies per
[API-tools.md §3–§5](../../../docs/design/FEAT-JARVIS-004/contracts/API-tools.md):

- `list_available_capabilities()` — body now reads from
  `_capability_registry: CapabilitiesRegistry` via `.snapshot()`.
  Return shape unchanged.
- `capabilities_refresh()` — calls `_capability_registry.refresh()`;
  returns `OK: refresh queued — registry resynchronised` on success
  or `DEGRADED: transport_unavailable — NATS connection failed`
  if the refresh raises (Live → propagates from KV read failure).
- `capabilities_subscribe_updates()` — calls
  `_capability_registry.subscribe_updates(callback)`; returns the
  existing OK / no-op string (per API-tools.md §5).

**Module attribute** `_capability_registry: CapabilitiesRegistry | None`
swap-point — populated by `assemble_tool_list` in TASK-J004-013.

**Docstring deltas**:

- Delete each tool's Phase 2 paragraph (`STUB in Phase 2: no-op …`).
- `list_available_capabilities` latency line → `<30ms (cached live registry; <5ms when serving the stub fallback)`.
- `capabilities_refresh` adds `DEGRADED: transport_unavailable — NATS connection failed` return string.
- `_REFRESH_OK_MESSAGE` constant deleted.

## Seam Tests

```python
"""Seam test: verify CAPABILITIES_REGISTRY_PROTOCOL contract from TASK-J004-009."""
import pytest
from unittest.mock import MagicMock


@pytest.mark.seam
@pytest.mark.integration_contract("CAPABILITIES_REGISTRY_PROTOCOL")
def test_list_available_capabilities_reads_via_protocol_only():
    """Verify list_available_capabilities consumes only the Protocol surface.

    Contract: CapabilitiesRegistry Protocol — snapshot/refresh/subscribe_updates/close.
    The tool must not branch on Live vs Stub or call NATS directly.
    Producer: TASK-J004-009
    """
    from jarvis.tools import capabilities as caps_module

    registry = MagicMock()
    registry.snapshot.return_value = []
    caps_module._capability_registry = registry

    result = caps_module.list_available_capabilities.invoke({})

    # Format assertion: snapshot() was called; no other interaction with registry internals.
    registry.snapshot.assert_called_once()
    assert isinstance(result, str), "tool must return str per ADR-ARCH-021"
```

## Acceptance Criteria

- [ ] `list_available_capabilities` body reads via `_capability_registry.snapshot()` only — does not directly touch NATS or the stub YAML.
- [ ] `capabilities_refresh` returns the success string on no-exception path; the DEGRADED string when `.refresh()` raises a transport-related exception.
- [ ] `capabilities_subscribe_updates` is idempotent — calling more than once during a session returns the same OK string and does not double-subscribe.
- [ ] Phase 2 stub paragraphs deleted from all three docstrings; `_REFRESH_OK_MESSAGE` constant deleted.
- [ ] Tool signatures + docstring shape (parse_docstring) **byte-identical** modulo the documented deltas (Phase 2 paragraphs + new return-shape lines).
- [ ] `uv run mypy src/jarvis/tools/capabilities.py` strict-clean.
- [ ] Tests in this task cover: `_capability_registry` swap-in via direct attribute set; happy-path snapshot return; refresh DEGRADED on simulated KV exception; subscribe_updates idempotent.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Mock `CapabilitiesRegistry` Protocol — no real NATS in unit tests for this module.
- [ ] Round-trip / KV-watch behaviour is owned by TASK-J004-014 (integration tests against in-process NATS).

## Implementation Notes

`list_available_capabilities` returns JSON-encoded `CapabilityToolSummary`
per the existing Phase 2 contract — the schema doesn't change in
FEAT-J004; only the source of truth does.

## Test Execution Log

(Populated by /task-work.)
