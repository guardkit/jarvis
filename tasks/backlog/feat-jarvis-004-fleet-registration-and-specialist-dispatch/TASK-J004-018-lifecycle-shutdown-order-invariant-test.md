---
id: TASK-J004-018
title: "tests/test_lifecycle_shutdown_order.py — drain ordering invariant"
task_type: testing
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 4
implementation_mode: task-work
complexity: 4
dependencies: [TASK-J004-013]
priority: high
tags: [tests, lifecycle, shutdown, ordering, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-018 — Lifecycle shutdown-order invariant test

## Description

Land `tests/test_lifecycle_shutdown_order.py` asserting the exact
8-step shutdown ordering from [design §8](../../../docs/design/FEAT-JARVIS-004/design.md):

```
1. cancel fleet_heartbeat_task
2. await deregister_from_fleet(nats_client, "jarvis")
3. await capabilities_registry.close()
4. await routing_history_writer.flush(timeout=5.0)
5. await nats_client.drain(timeout=5.0)
6. await graphiti_client.aclose()
7. disarm Layer-2 hooks
8. state.store.close()
```

Why ordering matters:

- **3 before 5**: closing the registry before draining NATS prevents
  KV-watch callbacks firing during drain.
- **4 before 5**: writer flush submits Graphiti episodes that may
  themselves use the NATS client indirectly; flush before drain.
- **2 before 5**: deregister must publish to NATS, so it has to
  precede `drain()`.
- **6 last (among I/O closes)**: Graphiti close after the writer has
  flushed avoids dropping in-flight episodes.

Implementation strategy:

- Wrap each shutdown side-effect target with a `MagicMock` that
  records call order via a shared list.
- Run `await lifecycle.shutdown(state)`.
- Assert the recorded list matches the expected sequence.

## Acceptance Criteria

- [ ] Test verifies the **exact** ordering of all 8 steps via call-order recording.
- [ ] Test fails (descriptively) if any step is skipped, reordered, or duplicated.
- [ ] **Failure tolerance**: a separate test asserts that a single failed step (e.g. `deregister_from_fleet` raises) does NOT skip subsequent steps — they all execute, errors are WARN-logged.
- [ ] Heartbeat cancellation produces no traceback / unhandled-exception warning.
- [ ] `uv run pytest tests/test_lifecycle_shutdown_order.py -v` green.

## Test Requirements

- [ ] Build the test `AppState` via a fixture that injects mocked clients/writers/registry/store; no real NATS or Graphiti.
- [ ] Use `MagicMock(side_effect=...)` to record call order via a shared `list.append` callback.

## Implementation Notes

This test is an **invariant gate** — once it passes, future refactors
that accidentally reorder shutdown steps will break here, not in
production where the symptom would be a hung CI pipeline or a lost
final trace write.

## Test Execution Log

(Populated by /task-work.)
