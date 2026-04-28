---
complexity: 5
created: 2026-04-27 15:30:00+00:00
dependencies:
- TASK-J004-013
feature_id: FEAT-JARVIS-004
id: TASK-J004-016
implementation_mode: task-work
parent_review: TASK-REV-22CF
priority: high
status: design_approved
tags:
- tests
- soft-fail
- lifecycle
- FEAT-JARVIS-004
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: 'Soft-fail tests: NATS down, Graphiti down, partial failures'
wave: 4
---

# TASK-J004-016 — Soft-fail tests: NATS-down, Graphiti-down, partial failures

## Description

Land three test files asserting the DDR-019 (Graphiti soft-fail) and
DDR-021 (NATS soft-fail) invariants:

**`tests/test_nats_unavailable.py`**:

- Startup with unreachable NATS URL → Jarvis still starts;
  `state.nats_client is None`.
- `dispatch_by_capability(...)` returns `DEGRADED: transport_unavailable
  — NATS connection failed`.
- `list_available_capabilities()` returns the stub list (FEAT-J002
  regression preserved — Stub fallback).
- `escalate_to_frontier` still works on attended sessions (no NATS
  dependency).

**`tests/test_graphiti_unavailable.py`**:

- Startup with unreachable Graphiti endpoint → Jarvis still starts.
- `routing_history_writer` is in degraded mode (`graphiti_client is None`).
- Dispatches succeed (real round-trips).
- Trace writes log `WARN routing_history_write_failed reason=...`
  exactly once (subsequent writes are silent — DDR-019 ratchet).
- Recovery on next startup (test by reconfiguring + restarting fixture).

**`tests/test_lifecycle_partial_failure.py`** — DDR-021 + DDR-019 cross-product:

- NATS up + Graphiti down → dispatches succeed; traces lost; WARN.
- NATS down + Graphiti up → dispatches return DEGRADED; no traces.
- Both down → Jarvis still starts; only attended-only escape +
  local subagent + Phase 2 deterministic tools functional.

## Acceptance Criteria

- [ ] All three files exist with the scenarios above; ≥10 test functions total.
- [ ] **No process exits / crashes** on soft-fail paths — tests assert process-still-alive at the end of each scenario.
- [ ] `WARN routing_history_write_failed` log line asserted via `caplog.records` filter on `logger == "jarvis.infrastructure.routing_history"` and `level == WARNING`.
- [ ] Stub-fallback capability list **identical** to the Phase 2 stub YAML — no drift.
- [ ] The DDR-019 "WARN once, then silent" ratchet is asserted — not "WARN every dispatch".
- [ ] Tests survive `--randomly-seed=0`.
- [ ] `uv run pytest tests/test_nats_unavailable.py tests/test_graphiti_unavailable.py tests/test_lifecycle_partial_failure.py -v` green.

## Test Requirements

- [ ] Use `unittest.mock.patch` for `NATSClient.connect` and `GraphitiClient.connect` to deterministically simulate unreachable endpoints.
- [ ] Use `caplog` (`pytest`'s built-in) for log assertions — never grep stderr.
- [ ] No real GB10 / external endpoints — pure local + in-process where needed.

## Implementation Notes

Demo-day relevance: these tests are the demo-robustness gate. If GB10
hiccups during the DDD Southwest talk, Jarvis must keep talking — this
is what those tests prove.

The "WARN once" ratchet for Graphiti soft-fail is implemented in
TASK-J004-010's writer (one-time WARN log; subsequent writes silent).
This task asserts the contract from the test side.

## Test Execution Log

(Populated by /task-work.)