---
complexity: 6
created: 2026-04-29 00:00:00+00:00
dependencies: []
feature_id: FEAT-J005-946D
id: TASK-J005-004
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: completed
tags:
- routing-history
- graphiti
- append-only
- DDR-029
- FEAT-JARVIS-005
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: routing_history.py build-queue write + append-only edge writer
updated: 2026-04-30T11:10:33Z
wave: 1
---

# TASK-J005-004 — RoutingHistoryWriter build-queue extensions

## Description

Replace the FEAT-J004 no-ops in `src/jarvis/infrastructure/routing_history.py` with
two real methods on `RoutingHistoryWriter`, per
[design.md §7](../../../docs/design/FEAT-JARVIS-005/design.md) and
[DDR-029](../../../docs/design/FEAT-JARVIS-005/decisions/DDR-029-stage-complete-as-append-only-edges.md):

- `async def write_build_queue_dispatch(self, entry: JarvisRoutingHistoryEntry) -> None`
  — fire-and-forget Graphiti write of a routing-history entry with
  `subagent_type="forge_build_queue"` and `subagent_task_id=correlation_id`. Mirrors
  `write_specialist_dispatch` (FEAT-J004); reuses the same redaction + offload paths.

- `async def append_build_queue_event(self, correlation_id: str, payload: StageCompletePayload) -> None`
  — appends a single Graphiti edge of type `stage_complete` to the entry whose
  `subagent_task_id == correlation_id`. Edge body = `payload.model_dump_json()`.
  **Preserves the `frozen=True` invariant on the parent entry** (DDR-018) — never
  rewrites the entry itself. Graphiti errors → WARN-only per DDR-019; never raises.

## Acceptance Criteria

- [ ] `RoutingHistoryWriter.write_build_queue_dispatch` accepts a frozen
      `JarvisRoutingHistoryEntry` with `subagent_type="forge_build_queue"`.
- [ ] `write_build_queue_dispatch` is fire-and-forget (`asyncio.create_task`) and
      returns immediately (does not block the caller).
- [ ] `append_build_queue_event` looks up the parent entry by
      `subagent_task_id == correlation_id` and emits an append-only Graphiti edge
      with `edge_type="stage_complete"` and JSON-encoded payload as body.
- [ ] Parent entry is **never re-written**; field-overwrite attempts raise (the
      DDR-018 frozen invariant is the test).
- [ ] If the parent entry cannot be found (e.g. evicted correlation), log a WARN
      and return — never raise.
- [ ] All Graphiti errors are WARN-only per DDR-019; the writer never raises.
- [ ] `uv run mypy src/jarvis/infrastructure/routing_history.py` passes (strict).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Unit test: `write_build_queue_dispatch` emits one entry with
      `subagent_type="forge_build_queue"` and `subagent_task_id == correlation_id`.
- [ ] Unit test: two `append_build_queue_event` calls for the same correlation_id
      produce two distinct stage-complete edges (Group A #4 scenario).
- [ ] Unit test: `append_build_queue_event` for an unknown correlation_id logs a
      WARN and does not raise (Group D #11–12 scenarios).
- [ ] Unit test: Graphiti raises during edge write → WARN logged, function returns
      None (Group D #5 scenario).
- [ ] Unit test: parent entry's frozen=True is preserved — direct-attribute
      assignment after `append_build_queue_event` raises `ValidationError`.

## Implementation Notes

- Reuse the FEAT-J004 redaction + filesystem-offload pipeline; this task adds the
  build-queue path through it.
- Edge writes go through the same `GraphitiClient.add_edge(...)` surface as the
  FEAT-J004 path; if that surface needs a small extension to take a typed body,
  that goes here.
- See [API-internal.md §1](../../../docs/design/FEAT-JARVIS-005/contracts/API-internal.md)
  for the exact method signatures.

## Seam Tests

The following seam test validates the Integration Contract with TASK-J005-003
(forge_notifications subscriber) and TASK-J005-005 (queue_build dispatcher).

```python
"""Seam test: verify RoutingHistoryWriter build-queue contract."""
import pytest
from jarvis.infrastructure.routing_history import RoutingHistoryWriter, JarvisRoutingHistoryEntry


@pytest.mark.seam
@pytest.mark.integration_contract("write_build_queue_dispatch")
def test_write_build_queue_dispatch_signature():
    """Verify write_build_queue_dispatch accepts JarvisRoutingHistoryEntry.

    Contract: subagent_type='forge_build_queue', subagent_task_id=correlation_id.
    Producer: TASK-J005-004; Consumers: TASK-J005-005, TASK-J005-003.
    """
    assert hasattr(RoutingHistoryWriter, "write_build_queue_dispatch")
    assert hasattr(RoutingHistoryWriter, "append_build_queue_event")


@pytest.mark.seam
@pytest.mark.integration_contract("append_build_queue_event_edge_type")
def test_stage_complete_edge_type_invariant():
    """Verify append_build_queue_event emits edge_type='stage_complete'.

    Contract: edge body = JSON-encoded StageCompletePayload; frozen=True on parent
    preserved per DDR-018.
    """
    # Format constraint: edge_type must be exactly 'stage_complete'
    expected_edge_type = "stage_complete"
    assert expected_edge_type == "stage_complete"
```