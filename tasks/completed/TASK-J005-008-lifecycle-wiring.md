---
complexity: 6
consumer_context:
- consumes: forge_notifications_queue_cap, forge_correlation_map_cap
  driver: pydantic-settings
  format_note: Both ints with defaults 100 and 1000; passed to ForgeNotificationsSubscriber.__init__
  framework: JarvisConfig
  task: TASK-J005-001
- consumes: ForgeNotificationsSubscriber
  driver: in-process
  format_note: start() / bind_session_manager() / stop(); start AFTER fleet registration;
    stop BEFORE NATS drain (5s bound)
  framework: ForgeNotificationsSubscriber
  task: TASK-J005-003
- consumes: SessionManager (target of bind_session_manager)
  driver: in-process
  format_note: Late-bind session_manager into subscriber after both are constructed
  framework: SessionManager
  task: TASK-J005-006
created: 2026-04-29 00:00:00+00:00
dependencies:
- TASK-J005-001
- TASK-J005-003
- TASK-J005-004
- TASK-J005-006
feature_id: FEAT-J005-946D
id: TASK-J005-008
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: completed
tags:
- lifecycle
- wiring
- shutdown
- FEAT-JARVIS-005
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: lifecycle.py wiring — start/bind/stop subscriber
updated: 2026-04-30T11:10:33Z
wave: 3
---

# TASK-J005-008 — Lifecycle wiring for subscriber

## Description

Update `src/jarvis/infrastructure/lifecycle.py` to start, bind, and stop the
`ForgeNotificationsSubscriber` per
[design.md §8 wiring](../../../docs/design/FEAT-JARVIS-005/design.md).

**Startup** (`build_app_state(config)` — extends FEAT-J004 sequence):

1. After fleet registration + heartbeat task creation, if `nats_client is not
   None`:
   ```python
   forge_subscriber = ForgeNotificationsSubscriber(
       nats_client=nats_client,
       routing_history_writer=routing_history_writer,
       queue_cap=config.forge_notifications_queue_cap,
       correlation_cap=config.forge_correlation_map_cap,
   )
   await forge_subscriber.start()
   ```
   else `forge_subscriber = None`.
2. Pass `forge_subscriber` to `assemble_tool_list(...)` for both attended and
   ambient tool lists (so `queue_build` can call `register_correlation`).
3. After `session_manager` is constructed:
   `forge_subscriber.bind_session_manager(session_manager)`.
4. Return `AppState(..., forge_subscriber=forge_subscriber)`.

**Shutdown** (`shutdown(state)` — adds one new step between heartbeat-cancel and
deregister):

1. Cancel `fleet_heartbeat_task` (unchanged).
2. **`await state.forge_subscriber.stop()`** — bounded at 5s; idempotent
   (NEW).
3. `await deregister_from_fleet(...)` (unchanged).
4. `await state.capabilities_registry.close()` (unchanged).
5. `await state.routing_history_writer.flush(...)` (unchanged — now also drains
   build-queue edge writes).

## Acceptance Criteria

- [ ] `build_app_state` constructs `ForgeNotificationsSubscriber` only when
      `nats_client is not None`; sets `forge_subscriber = None` otherwise.
- [ ] `subscriber.start()` is called once, AFTER fleet registration succeeds,
      BEFORE the `session_manager` is constructed.
- [ ] `subscriber.bind_session_manager(session_manager)` is called once, AFTER
      `session_manager` is constructed, BEFORE `build_app_state` returns.
- [ ] `assemble_tool_list` accepts `forge_subscriber=None | Subscriber` and
      threads it into the closure available to `queue_build`.
- [ ] `AppState` dataclass / Pydantic model has a `forge_subscriber:
      ForgeNotificationsSubscriber | None` field.
- [ ] `shutdown` calls `state.forge_subscriber.stop()` if non-None, BEFORE
      `deregister_from_fleet`.
- [ ] `subscriber.stop()` is idempotent on double-shutdown (test) and returns
      within 5s if the broker is unresponsive (Group D #14).
- [ ] On `nats_client is None` (NATS-down path), the subscriber is never
      constructed, lifecycle still completes successfully, and `queue_build`
      returns DEGRADED `transport_unavailable` (Group C #3).
- [ ] `uv run mypy src/jarvis/infrastructure/lifecycle.py` passes (strict).
- [ ] All modified files pass project-configured lint/format checks with zero
      errors.

## Test Requirements

- [ ] Integration test: full `build_app_state` with mocked NATS; assert subscriber
      `.start()` called once, `bind_session_manager` called once.
- [ ] Integration test: `shutdown` called twice — second call is a no-op
      (idempotency).
- [ ] Integration test: NATS-down path (`nats_client=None`) — `build_app_state`
      completes; `forge_subscriber` is None; `queue_build` returns DEGRADED.

## Implementation Notes

- The construction order in build_app_state is **strict** —
  supervisor → session_manager → subscriber-bind. Out-of-order bind raises
  programming-error per design.md §8 (subscriber raises on rebind).
- `assemble_tool_list` is the FEAT-J004 closure factory; threading
  `forge_subscriber` into it keeps the `queue_build` tool's signature
  unchanged from Phase 2 (DDR-J005-tool-surface-frozen invariant).