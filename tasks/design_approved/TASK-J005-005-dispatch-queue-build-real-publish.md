---
complexity: 7
consumer_context:
- consumes: pipeline_publish_timeout_seconds
  driver: pydantic-settings
  format_note: int seconds; passed to asyncio.wait_for around js.publish; default
    5
  framework: JarvisConfig
  task: TASK-J005-001
- consumes: ForgeNotificationsSubscriber.register_correlation
  driver: in-process
  format_note: register_correlation(correlation_id, session_id, adapter, queued_at,
    feature_id) — populates LRU map (DDR-028)
  framework: ForgeNotificationsSubscriber
  task: TASK-J005-003
- consumes: RoutingHistoryWriter.write_build_queue_dispatch
  driver: graphiti-core
  format_note: Fire-and-forget write of JarvisRoutingHistoryEntry with subagent_type='forge_build_queue',
    subagent_task_id=correlation_id
  framework: RoutingHistoryWriter
  task: TASK-J005-004
created: 2026-04-29 00:00:00+00:00
dependencies:
- TASK-J005-001
- TASK-J005-003
- TASK-J005-004
feature_id: FEAT-J005-946D
id: TASK-J005-005
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: design_approved
tags:
- dispatch
- queue-build
- jetstream
- DDR-025
- DDR-031
- FEAT-JARVIS-005
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: tools/dispatch.py queue_build real JetStream publish
updated: 2026-04-29 00:00:00+00:00
wave: 3
---

# TASK-J005-005 — `queue_build` real JetStream publish

## Description

Update `src/jarvis/tools/dispatch.py` `queue_build`: swap the Phase 2 stub log
line for a real `js.publish(...)` on `pipeline.build-queued.{feature_id}` per
ADR-SP-014 Pattern A, [design.md §8 queue_build runtime sequence](../../../docs/design/FEAT-JARVIS-005/design.md),
and [DDR-025](../../../docs/design/FEAT-JARVIS-005/decisions/DDR-025-queue-build-real-transport.md).

Concrete edits:

- **Delete** `LOG_PREFIX_QUEUE_BUILD` constant; delete the `logger.info(...)`
  stub line; delete the Phase 2 stub paragraph in the tool docstring.
- **Acquire** `dispatch_semaphore.try_acquire()` (DDR-020 reuse for queue_build);
  on saturation return DEGRADED `dispatch_capacity_saturated` (Group C #4).
- **Resolve** `originating_adapter` from the active `Session.adapter` (DDR-031);
  the reasoning model's tool argument becomes a fallback used only when no
  session is active (Group A #1, Group C #6, Group D #4 scenarios).
- **Subject** = `nats_core.Topics.Pipeline.BUILD_QUEUED.format(feature_id=...)`;
  hard-coded subject strings remain forbidden.
- **Payload** = `MessageEnvelope(source_id="jarvis", payload=BuildQueuedPayload(...))`;
  `triggered_by="jarvis"`, fresh `correlation_id`, `parent_request_id` from
  session metadata if present.
- **Publish** = `await asyncio.wait_for(js.publish(subject, envelope.model_dump_json().encode()), timeout=config.pipeline_publish_timeout_seconds)`;
  PubAck = transport-level receipt (per LES1: PubAck ≠ delivery).
- **Timeout** → return DEGRADED `transport_unavailable` (Group B #6 scenario);
  log WARN; do not retry in v1.
- **Register correlation** with `forge_subscriber.register_correlation(...)`
  immediately after PubAck succeeds.
- **Fire-and-forget routing-history write** via
  `routing_history_writer.write_build_queue_dispatch(entry)` —
  `subagent_type="forge_build_queue"`, `subagent_task_id=correlation_id`.
- **Return** `QueueBuildAck` (Phase 2 dict shape, unchanged).

## Acceptance Criteria

- [ ] `LOG_PREFIX_QUEUE_BUILD` is removed from `tools/dispatch.py`; the Phase 2
      stub paragraph is removed from the tool docstring; the rest of the
      docstring is preserved verbatim.
- [ ] `js.publish` is wrapped in `asyncio.wait_for(...,
      timeout=config.pipeline_publish_timeout_seconds)`.
- [ ] Subject is constructed via `nats_core.Topics.Pipeline.BUILD_QUEUED.format(...)`;
      hard-coded subject strings absent (grep test in TASK-J005-011 verifies).
- [ ] Payload uses `nats_core.events.BuildQueuedPayload` verbatim — no Jarvis-
      specific wire extensions.
- [ ] Envelope `source_id="jarvis"` always; never read from the reasoning model's
      arg.
- [ ] `originating_adapter` resolved from `Session.adapter` when a session is
      active; arg-as-fallback only when no session is active (Group A #1, Group
      C #6, Group D #4).
- [ ] On PubAck timeout: returns `{"status": "degraded", "reason":
      "transport_unavailable", ...}` per ADR-ARCH-021 structured-error shape;
      never raises (Group B #6).
- [ ] On dispatch-semaphore saturation: returns `{"status": "degraded", "reason":
      "dispatch_capacity_saturated", ...}` (Group C #4).
- [ ] On NATS unavailable (no `js`): returns `{"status": "degraded", "reason":
      "transport_unavailable", ...}` (Group C #3).
- [ ] On invalid args (Group C #5 outline): returns
      `{"status": "validation_error", ...}` per ADR-ARCH-021; never raises.
- [ ] `forge_subscriber.register_correlation(...)` called once on PubAck
      success.
- [ ] `routing_history_writer.write_build_queue_dispatch(entry)` invoked
      fire-and-forget after PubAck success (Group A #1, #3, #6).
- [ ] Reasoning-model attempt to override `originating_adapter` is silently
      overridden (Group D #4 security scenario).
- [ ] `uv run mypy src/jarvis/tools/dispatch.py` passes (strict).
- [ ] All modified files pass project-configured lint/format checks with zero
      errors.

## Test Requirements

- [ ] Integration test (in-process JetStream): publish a payload, assert subject
      shape, envelope source_id="jarvis", payload round-trip via nats-core
      (Group A #1 smoke).
- [ ] Integration test: PubAck within timeout returns "queued" (Group B #5).
- [ ] Integration test: simulated PubAck stall returns DEGRADED
      `transport_unavailable` after `pipeline_publish_timeout_seconds` ± 200ms
      (Group B #6).
- [ ] Integration test: dispatch-semaphore saturated returns DEGRADED
      `dispatch_capacity_saturated` (Group C #4).
- [ ] Integration test: queue + specialist dispatch in parallel each consume
      one slot (Group D #15 concurrency scenario).
- [ ] Integration test: `register_correlation` called with the same
      `correlation_id` returned to the caller (Group A #1).
- [ ] Integration test: reasoning-model arg override of `originating_adapter`
      is ignored (Group D #4 security scenario).
- [ ] Integration test: `routing_history_writer.write_build_queue_dispatch`
      called once per successful publish (Group A #3).

## Implementation Notes

- `nats_core.MessageEnvelope` is the outer wrapper; `BuildQueuedPayload` is the
  inner payload. Validators on `BuildQueuedPayload` enforce
  `_adapter_required_for_jarvis` (DDR-031).
- Use `asyncio.wait_for` (not `js.publish(timeout=...)`) so the path is
  framework-agnostic should `nats-py` change semantics.
- DispatchSemaphore is shared with specialist-dispatch (FEAT-J004); the cap=8
  applies across both (DDR-020).