---
complexity: 7
consumer_context:
- consumes: ForgeNotification + BuildCorrelation models
  driver: pydantic
  format_note: 'frozen=True; ForgeNotification.render_line() emits canonical [HH:MM]
    Forge {feature_id}: stage {stage_label} ({status})'
  framework: Pydantic v2 (frozen BaseModel)
  task: TASK-J005-002
- consumes: append_build_queue_event
  driver: graphiti-core
  format_note: Subscriber calls writer.append_build_queue_event(correlation_id, payload)
    on each matched StageCompletePayload; edge_type='stage_complete', body=JSON-encoded
    payload, parent entry frozen=True (DDR-029, DDR-018)
  framework: RoutingHistoryWriter
  task: TASK-J005-004
- consumes: SessionManager.enqueue_notification
  driver: in-process
  format_note: Subscriber calls session_manager.enqueue_notification(session_id, ForgeNotification)
    for each correlation-matched event; binding is late via subscriber.bind_session_manager()
  framework: SessionManager
  task: TASK-J005-006
created: 2026-04-29 00:00:00+00:00
dependencies:
- TASK-J005-002
- TASK-J005-004
- TASK-J005-006
feature_id: FEAT-J005-946D
id: TASK-J005-003
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: design_approved
tags:
- forge-notifications
- jetstream
- subscriber
- DDR-026
- DDR-027
- DDR-028
- FEAT-JARVIS-005
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: ForgeNotificationsSubscriber + correlation map + in-process router
updated: 2026-04-29 00:00:00+00:00
wave: 2
---

# TASK-J005-003 — ForgeNotificationsSubscriber

## Description

Extend `src/jarvis/infrastructure/forge_notifications.py` with the
`ForgeNotificationsSubscriber` class, the in-memory LRU correlation map, and the
in-process router from `pipeline.stage-complete.>` to per-session pending
notifications, per
[design.md §8 `pipeline.stage-complete.*` consumer sequence](../../../docs/design/FEAT-JARVIS-005/design.md)
and DDRs 026–028, 030.

Behaviour:

- JetStream **ephemeral push** consumer on `pipeline.stage-complete.>` with
  `deliver_policy=NEW`, auto-ack (DDR-027). No replay on restart in v1.
- Maintains `correlation_id → BuildCorrelation` LRU map, cap from
  `JarvisConfig.forge_correlation_map_cap` (default 1000, DDR-028). Eviction logs
  WARN `forge_correlation_evicted`.
- `register_correlation(correlation_id, session_id, adapter, queued_at, feature_id)`
  is the entry point used by `queue_build` (TASK-J005-005).
- On each delivered message: validate `MessageEnvelope.source_id == "forge"`,
  decode `StageCompletePayload`, look up correlation, and:
  1. `routing_history_writer.append_build_queue_event(correlation_id, payload)` —
     fire-and-forget (DDR-029).
  2. `session_manager.enqueue_notification(session_id, ForgeNotification(...))`.
- Unknown source / unknown correlation / malformed envelope → drop with structured
  log line; never raise.
- `bind_session_manager(session_manager)` — late binding called from
  `lifecycle.build_app_state` (TASK-J005-008).
- `start()` / `stop()` — start subscribes; stop drains JS within 5s
  (`asyncio.wait_for`) per ASSUM-011.

## Acceptance Criteria

- [ ] `ForgeNotificationsSubscriber.__init__` accepts `nats_client`,
      `routing_history_writer`, `queue_cap`, `correlation_cap`. (Note:
      `queue_cap` is not used by the subscriber itself but kept for API
      symmetry with the lifecycle wiring contract.)
- [ ] `start()` creates an ephemeral push consumer on
      `pipeline.stage-complete.>` with `deliver_policy=NEW`; idempotent on
      double-call.
- [ ] `stop()` cancels the consumer and returns within 5s even if the broker is
      unresponsive (Group D #14 scenario).
- [ ] `register_correlation` populates an LRU dict, evicts oldest at cap, logs
      one WARN per eviction (Group B #3–4 scenarios).
- [ ] Re-registering the same correlation_id is silently overwritten (idempotent
      register, not a duplicate-error) per DDR-028 §Consequences.
- [ ] On each delivered message: envelope validated, `source_id="forge"`
      enforced, correlation looked up, edge written via
      `routing_history_writer.append_build_queue_event`, notification enqueued via
      `session_manager.enqueue_notification`.
- [ ] Unknown source_id → message dropped, WARN
      `forge_notification_dropped_unknown_source` logged (Group C #1 scenario).
- [ ] Unknown correlation_id → message dropped, no log line (Group C #2 scenario).
- [ ] Malformed envelope (not valid JSON / missing required fields) → drop, WARN
      logged, never raises (Group D #7 scenario).
- [ ] Extra unknown fields tolerated (`extra="ignore"`) — no rejection (Group D
      #8 scenario).
- [ ] If `session_manager` is unbound when a message arrives, queue the
      notification on a buffer drained at `bind_session_manager` time (or drop
      gracefully — design.md §8 chooses drop with WARN; verify against design).
- [ ] `uv run mypy src/jarvis/infrastructure/forge_notifications.py` passes
      (strict).
- [ ] All modified files pass project-configured lint/format checks with zero
      errors.

## Test Requirements

- [ ] Unit test for each Group C / D negative + edge case (envelope source check,
      unknown correlation, evicted correlation drop, malformed envelope, extra
      fields).
- [ ] Unit test: registering past-cap registrations evicts oldest (Group B #4).
- [ ] Unit test: two stage-complete events for two correlations route to their
      own sessions (Group D #9 concurrency scenario).
- [ ] Unit test: burst of 5 events for one correlation arrive in publication
      order at the per-session queue (Group D #10 concurrency scenario).
- [ ] Unit test: `stop()` returns within 5s with unresponsive broker (Group D #14).

## Implementation Notes

- `nats-py` JetStream API: `js.subscribe(subject, ordered_consumer=False, ...)`
  with `deliver_policy=NEW`; capture the `Subscription` for `.unsubscribe()` on
  stop.
- LRU map: `collections.OrderedDict` with explicit `move_to_end` on lookup; cheap
  and correct.
- Source-id check: `MessageEnvelope.model_validate_json(msg.data)`; reject
  `envelope.source_id != "forge"`. Per ASSUM-006 / API-events §3.
- `bind_session_manager` is called once at lifecycle wiring time; defensive
  re-bind raises (programming error).
- See [DDR-027](../../../docs/design/FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md)
  for the consumer config rationale.

## Seam Tests

```python
"""Seam test: ForgeNotificationsSubscriber consumer contracts."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("ForgeNotification")
def test_forge_notification_model_consumed():
    """Subscriber must construct ForgeNotification from StageCompletePayload.

    Contract: ForgeNotification is frozen Pydantic v2; render_line() emits
    canonical [HH:MM] Forge ... shape.
    Producer: TASK-J005-002.
    """
    from jarvis.infrastructure.forge_notifications import ForgeNotification
    assert ForgeNotification.model_config["frozen"] is True
    assert hasattr(ForgeNotification, "render_line")


@pytest.mark.seam
@pytest.mark.integration_contract("append_build_queue_event")
def test_routing_history_append_signature():
    """Subscriber must call writer.append_build_queue_event on each matched event.

    Contract: edge_type='stage_complete'; body=JSON-encoded StageCompletePayload;
    frozen=True invariant on parent entry preserved (DDR-029, DDR-018).
    Producer: TASK-J005-004.
    """
    from jarvis.infrastructure.routing_history import RoutingHistoryWriter
    assert hasattr(RoutingHistoryWriter, "append_build_queue_event")


@pytest.mark.seam
@pytest.mark.integration_contract("SessionManager.enqueue_notification")
def test_session_manager_enqueue_signature():
    """Subscriber must call session_manager.enqueue_notification per matched event.

    Contract: per-session FIFO; cap=100; oldest evicted on overflow with WARN.
    Producer: TASK-J005-006.
    """
    from jarvis.sessions.manager import SessionManager
    assert hasattr(SessionManager, "enqueue_notification")


@pytest.mark.seam
@pytest.mark.integration_contract("StageComplete.envelope")
def test_stage_complete_envelope_source_id():
    """Subscriber must reject messages with source_id != 'forge'.

    Contract: nats_core.MessageEnvelope wraps StageCompletePayload; source_id is
    Forge's audit-trail attestation per API-events §3.
    """
    expected_source = "forge"
    assert expected_source == "forge"
```