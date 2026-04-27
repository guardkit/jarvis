---
id: TASK-J004-010
title: "RoutingHistoryWriter — write_specialist_dispatch + 16KB offload + redaction + flush"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 2
implementation_mode: task-work
complexity: 7
dependencies: [TASK-J004-003, TASK-J004-004]
priority: high
tags: [infrastructure, routing-history, graphiti, redaction, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-004
    consumes: JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA
    framework: "Pydantic v2 BaseModel with frozen=True, extra=ignore"
    driver: "pydantic"
    format_note: "Writer accepts JarvisRoutingHistoryEntry instances; never mutates fields (frozen=True invariant); applies redaction processor at write boundary, not at construction"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-010 — RoutingHistoryWriter: writer methods + filesystem offload + redaction

## Description

Add the writer class to `src/jarvis/infrastructure/routing_history.py`
(schema landed in TASK-J004-004) per [API-internal.md §4](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md):

```python
class RoutingHistoryWriter:
    def __init__(self, graphiti_client: GraphitiClient | None, config: JarvisConfig) -> None: ...
    async def write_specialist_dispatch(self, entry: JarvisRoutingHistoryEntry) -> None: ...
    async def write_build_queue_dispatch(self, entry: JarvisRoutingHistoryEntry) -> None: ...
    async def append_build_queue_event(self, correlation_id: str, event: dict) -> None: ...
    async def flush(self, *, timeout: float = 5.0) -> None: ...
```

Side-effect ordering inside `write_specialist_dispatch` (DDR-018 + DDR-019):

1. Apply `structlog` redact-processor (ADR-ARCH-029) to:
   - `human_response_text`
   - `supervisor_reasoning_summary`
   - `args_summary` and `result_summary` inside every `ToolCallRecord`
   - File-side payload too — both inline and offloaded paths.
2. JSON-encode `supervisor_tool_call_sequence` + `subagent_trace_ref`.
3. If JSON >16KB, write to `~/.jarvis/traces/{date}/{decision_id}.json`
   (mode 0700 dir, mode 0600 file) and substitute `TraceRef(path,
   content_sha256, size_bytes)` in the entity.
4. Submit Graphiti `add_episode` (called via `asyncio.create_task` —
   the dispatch boundary owns the fire-and-forget; this method awaits
   the *submission*, not the round-trip).
5. Failure → `WARN routing_history_write_failed reason=<err>`; never
   raises.

**ASSUM-009 / DDR-023 collision policy**: if the trace file path
already exists, log `WARN routing_history_write_failed reason=trace_file_exists`,
preserve the original, do not overwrite. The Graphiti write does not
fire (the entity needs the TraceRef).

`flush()` drains in-flight async tasks with a 5s bound; on overflow
log `WARN routing_history_flush_timeout` and abandon (DDR-019).

`write_build_queue_dispatch` and `append_build_queue_event` are
**reserved-but-no-op** in FEAT-J004 — return immediately. FEAT-J005
fills in the bodies. Land the signatures here so the writer is
forward-compatible.

Plus `tests/test_routing_history_writer.py` covering all of the above.

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA contract from TASK-J004-004."""
import pytest
from datetime import datetime, timezone


@pytest.mark.seam
@pytest.mark.integration_contract("JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA")
async def test_writer_consumes_entry_without_mutation():
    """Verify RoutingHistoryWriter does not mutate the frozen entry.

    Contract: JarvisRoutingHistoryEntry is frozen=True per DDR-018.
    The writer applies redaction to a *copy* derived from the entry's
    model_dump output, not by mutating the original.
    Producer: TASK-J004-004
    """
    from jarvis.infrastructure.routing_history import (
        JarvisRoutingHistoryEntry,
        RoutingHistoryWriter,
    )

    # Producer side: a populated entry.
    entry = _build_minimal_entry()  # fixture helper

    # Consumer side: writer must not mutate.
    original_dump = entry.model_dump()
    writer = RoutingHistoryWriter(graphiti_client=None, config=_test_config())
    await writer.write_specialist_dispatch(entry)
    assert entry.model_dump() == original_dump, (
        "RoutingHistoryWriter must not mutate the frozen entry; "
        "redaction applies to a copy, not the source"
    )
```

## Acceptance Criteria

- [ ] All 5 methods land with the exact API-internal.md §4 signatures.
- [ ] Inline write path (<=16KB JSON-encoded) — no filesystem touch.
- [ ] Filesystem offload (>16KB) — directory created with mode 0700 lazily on first write; file written with mode 0600.
- [ ] `TraceRef.content_sha256` matches the SHA-256 of the on-disk file contents.
- [ ] **DDR-023 collision policy**: pre-existing trace file at the same path → WARN + preserve original; the writer does not call Graphiti `add_episode` for that record.
- [ ] **ADR-ARCH-029 redaction** runs at the **write boundary**, not in a Pydantic validator. Test asserts a synthetic `OPENAI_API_KEY=sk-...` string in `human_response_text` lands as `***REDACTED***` in the persisted entity (and also in the offloaded file content if the field went into the offload).
- [ ] Graphiti unreachable (`graphiti_client is None`) → write is a no-op with **one-time** WARN log; subsequent writes silent (no log spam).
- [ ] `flush(timeout=5.0)` drains pending tasks; bounded; WARN on overflow; never raises.
- [ ] `write_build_queue_dispatch` and `append_build_queue_event` exist with type-checked signatures but bodies are `pass` + a single DEBUG line ("FEAT-J005 not yet implemented") — preserves forward-compat without faking work.
- [ ] `tests/test_routing_history_writer.py` covers: inline, offload, collision (DDR-023), redaction inline + offload, Graphiti-down WARN-once, flush bounded by timeout.
- [ ] `uv run mypy src/jarvis/infrastructure/routing_history.py` strict-clean.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Use `tmp_path` fixture for filesystem-offload tests — never write to the real `~/.jarvis/traces/`.
- [ ] Mock `GraphitiClient.add_episode` — no real Graphiti round-trip in unit tests.
- [ ] Use `caplog` to assert WARN messages on collision / Graphiti-down / flush-timeout paths.

## Implementation Notes

`structlog` redact-processor configuration covers the four token classes
per ADR-ARCH-029 + DDR-018: API keys (regex), JWT tokens
(`eyJ...`-prefix), NATS credentials (creds files mention
`NKEY`-prefixed lines), email addresses (RFC-loose regex). Land the
processor in `infrastructure/logging.py` if not already there; this
task wires it at the writer boundary.

The Phase 2 stub for `_stub_response_hook` does not exist on this
module — that anchor is in `tools/dispatch.py` and is retired by
TASK-J004-011.

## Test Execution Log

(Populated by /task-work.)
