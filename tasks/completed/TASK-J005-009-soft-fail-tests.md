---
complexity: 5
created: 2026-04-29 00:00:00+00:00
dependencies:
- TASK-J005-005
- TASK-J005-008
feature_id: FEAT-J005-946D
id: TASK-J005-009
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: completed
tags:
- tests
- soft-fail
- DDR-021
- DDR-019
- FEAT-JARVIS-005
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: Soft-fail tests — NATS down, Graphiti down, subscriber stop bounded
updated: 2026-04-30T11:10:33Z
wave: 4
---

# TASK-J005-009 — Soft-fail tests

## Description

Add the soft-fail test suite for FEAT-JARVIS-005, exercising the three
production-grade fail-soft paths inherited from FEAT-J004 and ratified by
DDR-019 / DDR-021 / DDR-027 / ASSUM-011:

- **NATS down** — `queue_build` returns DEGRADED `transport_unavailable` and
  `lifecycle.build_app_state` completes with `forge_subscriber=None` (Group C
  #3 scenario).
- **Graphiti down** — `routing_history_writer.write_build_queue_dispatch` and
  `append_build_queue_event` log WARN and return None; the operator-facing
  `queue_build` ack is still "queued" (DDR-019 fire-and-forget).
- **Subscriber stop with unresponsive broker** — `subscriber.stop()` returns
  within 5s ± 200ms (Group D #14 scenario).

This is a **dedicated test task** because the tests cross multiple modules and
the failure modes are non-trivial to set up. Lives in
`tests/test_jarvis_005_soft_fail.py` (or extend
`tests/test_nats_unavailable.py` from FEAT-J004 — implementer's call, but
keep the module count manageable).

## Acceptance Criteria

- [ ] Test: NATS-down at `build_app_state` time → `forge_subscriber=None`,
      lifecycle completes, `queue_build` returns DEGRADED `transport_unavailable`.
- [ ] Test: NATS-up but `js.publish` stalls past timeout → DEGRADED
      `transport_unavailable` (Group B #6).
- [ ] Test: Graphiti raises during `write_build_queue_dispatch` → WARN logged,
      `queue_build` still returns `{"status": "queued", ...}` (Group A #6).
- [ ] Test: Graphiti raises during `append_build_queue_event` → WARN logged,
      notification still enqueued + rendered (Group D #5 scenario).
- [ ] Test: `subscriber.stop()` against an unresponsive broker stub returns
      within 5s ± 200ms (Group D #14).
- [ ] Test: `subscriber.stop()` called twice is idempotent.
- [ ] All tests use the in-process JetStream test server pattern from FEAT-J004
      where applicable; mocked broker stubs for the unresponsive-broker case.
- [ ] `uv run pytest tests/test_jarvis_005_soft_fail.py -v` passes locally.

## Test Requirements

- See Acceptance Criteria — this IS the test task.

## Implementation Notes

- Re-use `tests/test_nats_unavailable.py` and `tests/test_graphiti_unavailable.py`
  fixtures from FEAT-J004; add new test functions, do not duplicate fixtures.
- Use `pytest.MonkeyPatch` to short-circuit `nats_client.connect` for the NATS-
  down case; use a stub `GraphitiClient.add_edge` that raises for the
  Graphiti-down case.
- `subscriber.stop()` timeout test: mock `JetStreamContext.unsubscribe` to hang
  forever; assert `stop()` returns within 5s.