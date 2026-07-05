---
id: TASK-JNB-002
title: Notification-sink seam in ForgeNotificationsSubscriber + queued hook in queue_build
status: in_review
created: 2026-07-03 15:30:00+00:00
updated: 2026-07-03 15:30:00+00:00
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 1
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: []
tags:
- ubs-003
- jarvis-notification-bridge
- slack
- v1
consumer_context:
- task: TASK-JNB-001
  consumes: NOTIFICATION_SINK
  framework: Python async protocol (in-process jarvis)
  driver: asyncio
  format_note: async notify(ForgeNotification) must NEVER raise into the caller; failures
    are WARNING + continue (DDR-007)
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-28FF
  base_branch: main
  started_at: '2026-07-03T17:02:52.042303'
  last_updated: '2026-07-03T17:19:39.405110'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-07-03T17:02:52.042303'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: Notification-sink seam in ForgeNotificationsSubscriber + queued hook in queue_build

## Description

In `src/jarvis/infrastructure/forge_notifications.py`, add `bind_notification_sink()` and invoke `sink.notify()` after the source-id gate and payload validation but before — and independent of — the correlation lookup for `build_started` / `build_complete` / `build_failed`. Widen `ForgeNotification` with optional `build_id`, `pr_url`, and `summary` fields. `stage_complete` is never forwarded to the sink (ASSUM-002). Sink errors are WARN-only: they must never disturb the existing subscriber behaviour. In `src/jarvis/tools/dispatch.py`, add a `_notification_sink` module-level snapshot and fire a `build_queued` notification immediately after the PubAck / `register_correlation` block in `queue_build` (~line 957ff), never affecting the returned ack.

Architecture context: the Slack surface for FEAT-UBS-003 is an in-process sink (a `NotificationSink` protocol implemented by `SlackNotifier` in `src/jarvis/infrastructure/slack_notifier.py`, built in TASK-JNB-001) invoked from inside the one existing ephemeral PIPELINE consumer's `_handle_message` — there is deliberately no second PIPELINE consumer, which makes the workqueue err-10100 violation structurally impossible. The sink call sits AFTER envelope decode + `source_id == 'forge'` gate + typed payload validation but BEFORE and independent of the correlation-map lookup: the phone is per-operator, not per-session, so LRU correlation loss on a jarvis restart must not silence it (correlation-independent fan-out is a deliberate, DDR-recorded semantic change). The `build_queued` event never touches the NATS stream at all — it is a publish-side hook in `queue_build` (ASSUM-011), routed through a module-level `_notification_sink` snapshot mirroring the existing `_forge_subscriber` / `_nats_client` pattern in `dispatch.py`. `ForgeNotification` widening follows its frozen-model rule: new fields are optional with `None` defaults, so the FEAT-JARVIS-005 cross-adapter contract and existing CLI rendering stay intact. The sink protocol is the seam a future FEAT-JARVIS-006 JARVIS-stream publisher plugs into without touching the subscriber again.

## Acceptance Criteria

- [ ] `bind_notification_sink()` exists on `ForgeNotificationsSubscriber` and, once bound, `sink.notify()` is invoked for `build_started`, `build_complete`, and `build_failed` after the source-id gate and typed payload validation but before, and independent of, the correlation lookup
- [ ] Malformed envelopes never reach the sink (decode/validation failures short-circuit before the sink call)
- [ ] Envelopes with `source_id != 'forge'` never reach the sink
- [ ] A correlation-map miss still notifies the sink (fan-out is correlation-independent)
- [ ] `stage_complete` events are never forwarded to the sink (ASSUM-002)
- [ ] A sink whose `notify()` raises produces only a WARNING log; the exception never propagates into `_handle_message` and existing subscriber processing continues unchanged (DDR-007)
- [ ] With no sink bound, subscriber behaviour is byte-identical to today; existing CLI FIFO behaviour is byte-identical with or without a bound sink
- [ ] `ForgeNotification` is widened with optional `build_id`, `pr_url`, and `summary` (all defaulting to `None`); existing CLI rendering and schema-import-isolation tests are updated to cover the widened model and pass
- [ ] `src/jarvis/tools/dispatch.py` has a module-level `_notification_sink` snapshot mirroring the existing `_forge_subscriber` / `_nats_client` pattern, with a setter for lifecycle wiring (TASK-JNB-003)
- [ ] `queue_build` fires a `build_queued` notification immediately after the PubAck / `register_correlation` block (~line 957ff); a sink failure never alters the returned `QueueBuildAck`
- [ ] `queue_build` error and degraded paths emit nothing to the sink
- [ ] jarvis supervisor startup binds exactly one PIPELINE consumer; boot logs show no err_code 10100
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

Plain pytest ONLY — no pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

Required coverage:

- Class per behaviour: sink invoked for each of `build_started` / `build_complete` / `build_failed` with a valid envelope and a bound sink; assert the constructed `ForgeNotification` carries the widened optional fields where present in the payload.
- Malformed envelope (undecodable / failing typed payload validation): sink mock is never awaited; existing error handling unchanged.
- `source_id != 'forge'`: sink mock never awaited.
- Correlation-map miss: sink IS awaited; existing miss handling (logging/skip of CLI FIFO delivery) unchanged.
- `stage_complete` envelope: sink never awaited.
- Raising sink: `notify()` side-effect raises; assert `_handle_message` completes without exception, a WARNING is logged (`caplog`), and downstream CLI FIFO delivery for a correlated build still occurs.
- No sink bound: all existing subscriber tests pass unmodified in behaviour; CLI FIFO output identical.
- `queue_build` happy path: sink receives exactly one `build_queued` notification after PubAck/`register_correlation`; the returned `QueueBuildAck` is identical whether the sink succeeds, raises, or is unbound.
- `queue_build` error/degraded paths (publish failure, NATS unavailable): sink mock never awaited.
- `ForgeNotification` model: new fields optional with `None` defaults; existing serialisation/rendering tests updated, schema-import-isolation tests updated and green.

## Seam Tests

Consumes NOTIFICATION_SINK from TASK-JNB-001 (framework: Python async protocol, in-process jarvis; driver: asyncio). The contract: `async notify(ForgeNotification)` must NEVER raise into the caller; failures are WARNING + continue (DDR-007).

```python
import logging
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("NOTIFICATION_SINK")
@pytest.mark.asyncio
async def test_sink_notify_never_raises_into_caller(caplog):
    """A sink whose Slack client raises must return normally and log WARNING (DDR-007)."""
    from slack_sdk.errors import SlackApiError
    from unittest.mock import AsyncMock

    from jarvis.infrastructure.slack_notifier import SlackNotifier

    client = AsyncMock()
    client.chat_postMessage.side_effect = SlackApiError(
        message="boom", response={"ok": False, "error": "channel_not_found"}
    )
    sink = SlackNotifier(client=client, channel_id="C000TEST")
    notification = make_forge_notification(event_type="build_failed", build_id="b-1")

    with caplog.at_level(logging.WARNING):
        # Must NOT raise — behavioural assertion of the never-raises contract.
        await sink.notify(notification)

    assert any(r.levelno == logging.WARNING for r in caplog.records), (
        "sink failure must be surfaced as WARNING, not silence and not an exception"
    )
```

The subscriber-side mirror of the same contract must also be asserted behaviourally: bind a sink stub whose `notify()` raises `RuntimeError`, await `_handle_message` with a valid `build_failed` envelope, and assert no exception propagates, a WARNING is logged, and correlated CLI FIFO delivery still happens.

## Implementation Notes

- No upstream task outputs are required to start (wave 1, no dependencies); the sink is consumed via the `NotificationSink` protocol shape only — code against the protocol (`async notify(ForgeNotification) -> None`) and test with stubs/mocks, not against `SlackNotifier` internals, so this task and TASK-JNB-001 can land in either order.
- Workqueue err-10100 single-consumer rule: the PIPELINE stream is workqueue-retention; a second overlapping consumer is a hard NATS error. This task adds NO consumer and NO filter change — the sink is called inside the existing ephemeral consumer's `_handle_message`, and `build_queued` is a publish-side hook in `queue_build` that never touches the stream. Keep it that way.
- DDR-007 never-regress: the SQLite ledger is authoritative; the notifier can never raise into the JetStream callback or into `queue_build`. Wrap every sink call in try/except, log WARNING, continue.
- DDR-027 no-replay: notification state is in-process only; do not add persistence or replay for missed notifications.
- Correlation-INDEPENDENT fan-out is deliberate: the phone receives started/terminal events even for builds not queued through jarvis, so a jarvis restart (LRU correlation loss) cannot blind the overnight surface. Do not gate the sink call on a correlation hit.
- `ForgeNotification` widening touches the FEAT-JARVIS-005 cross-adapter contract: apply the frozen-model rule (new optional fields with `None` defaults only) and update the existing CLI rendering and schema-import-isolation tests in the same change, or autobuild will red-loop.
- The `_notification_sink` snapshot in `dispatch.py` must mirror the existing `_forge_subscriber` / `_nats_client` module-level pattern; TASK-JNB-003 wires the real `SlackNotifier` in `build_app_state` (`infrastructure/lifecycle.py`).
- The autobuild worktree is jarvis-scoped: it cannot read the sibling forge repo. Everything needed to implement and test this task is contained in this file; forge payload shapes must be exercised via synthetic envelopes constructed in tests.
