---
id: TASK-SPL003-J01
title: "jarvis: jarvis.notification.slack return-channel consumer (FEAT-SPL-003)"
status: in_review
priority: high
task_type: feature
parent_review: TASK-REV-A387
feature_id: FEAT-SPL-003
wave: 1
repo: jarvis
implementation_mode: task-work
complexity: 6
dependencies: []
tags: [sovereign-planning-loop, feat-spl-003, slack, notification, return-channel]
---

# Task: jarvis.notification.slack return-channel consumer

## Description

**FIRST DELIVERABLE (WS1 §5).** forge Mode P core-publishes `NotificationPayload`
to `jarvis.notification.slack` (`forge/src/forge/cli/_serve_planning.py:669`) and
jarvis has **no consumer anywhere** → the JARVIS stream retains `jarvis.>` for
1h/1000 msgs and Mode P's messages to the human evaporate unread. This task adds
the consumer that renders each notification into the originating Slack thread,
degrading to a top-level planning-channel post when no thread anchor is present —
**never dropping**. It is standalone and mergeable without J02–J05, and it works
against the **live** forge today (which currently emits a bare `NotificationPayload`
with no thread anchor → the degrade path is the live path until the forge-half
TASK-SPL003F-001 projects anchors).

New module `src/jarvis/infrastructure/planning_notifier.py` (beside
`slack_planning_intake.py`, mirroring its handler / dedup / factory shape).

## Deliverables

1. **Shared threaded-post helper** — `post_threaded(web_client, *, channel, text,
   thread_ts=None, blocks=None)` (new; place in `planning_notifier.py` or a small
   `slack_posting.py` shared module). Wraps `chat.postMessage` with the JNB-103
   429/`Retry-After` budget (mirror `SlackNotifier._post_with_retry`,
   `slack_notifier.py:567-653`) BUT parameterised on `channel` **and** `thread_ts`
   (which `_post_with_retry` lacks — it hardcodes `self._channel_id` and cannot
   thread). Returns the posted message dict or `None` on exhausted budget. J02/J03
   consume this helper too (arch F3/F11).
2. **`PlanningNotificationConsumer`** (never-raises):
   - Ephemeral **push** JetStream consumer, `DeliverPolicy.NEW`, subject
     `Topics.Jarvis.NOTIFICATION.format(adapter="slack")` == `jarvis.notification.slack`,
     on the JARVIS stream (`jarvis.>`, limits-retention → no workqueue-overlap
     hazard; contrast the PIPELINE `DeliverPolicy.ALL` story at
     `slack_notifier.py:1184-1199`). ASSUM-007 override: ephemeral NEW (DDR-027),
     NOT durable.
   - **Manual ack** (`AckPolicy.EXPLICIT` / `manual_ack=True`): `msg.ack()` after a
     successful post OR after a logged-skip of a malformed notification; `msg.nak()`
     with bounded `max_deliver` (e.g. 5) on a **transient post failure** so a valid
     notification is redelivered within the retention window rather than lost — then
     ack + loud ERROR on redelivery exhaustion (never a silent drop; no storm).
     [Dated refinement of ASSUM-007 — see manifest BUILD-TIME REFINEMENTS.]
   - `_on_message` wraps `_handle` in try/except → `planning_notification_handler_error`
     WARN (DDR-007), and NAK/ack the msg appropriately so an exception never wedges
     the consumer.
   - Parse `MessageEnvelope.model_validate_json(msg.data)`; `event_type` must be
     `notification`; then `NotificationPayload.model_validate(envelope.payload)`.
     A parse/validation failure = **malformed**: log `planning_notification_skipped`
     + `msg.ack()` + keep running (spec: malformed is logged and skipped; subsequent
     notifications still render).
3. **Rendering** (ASSUM-013 copy):
   - Threaded reply into the originating thread when `payload.parent_request_id`
     (preferred) or `payload.thread_ts` is present; else **degrade** to a top-level
     post in `slack_planning_channel_id` (never drop). `NotificationPayload` carries
     no channel field → the planning channel is the sole target (pin this v1
     assumption in a comment).
   - `payload.blocks` passed through when present; else render text: severity prefix
     from `payload.level` (info/warning/error), `payload.message` **verbatim** (no
     jarvis reasoning — intake-only discipline extended to output), the
     `correlation_id` in monospace so it can be traced by hand on the degrade path.
   - `@`-mention `payload.target_user` when present (e.g. the escalation approver).
   - Posts via the shared `post_threaded` helper.
4. **Best-effort in-process dedup** — TTL-bounded map (`_seen`, TTL 300s, cap 1000,
   `time.monotonic` seam), keyed on **`envelope.message_id`** (uuid4, redelivery-stable)
   — NOT `correlation_id + timestamp` (a burst shares `correlation_id`; a timestamp
   collision would drop a distinct notification and violate never-drop + burst-order).
   Mirror `PlanningIntakeHandler._mark_if_new` (`slack_planning_intake.py:434-446`).
   [Dated deviation from ASSUM-008 — see manifest BUILD-TIME REFINEMENTS.]
5. **Burst ordering** — process each delivery to completion (awaited post) before the
   next; do NOT fan posts into `asyncio.create_task`, so notifications for one run
   render in publication order (scenario "a burst of notifications ... all render in order").
6. **Lifecycle wiring** (`lifecycle.py`):
   - New `AppState` field `planning_notification_consumer`.
   - New `build_app_state` block (after 7c3) gated on **planning config**
     (`nats_client is not None` AND `slack_planning_channel_id` set AND
     `slack_bot_token` set), constructing its own `AsyncWebClient` from the bot token
     — independent of the forge-notification `SlackNotifier` sink (arch F2: the
     dialogue must not be dark when only the planning channel is configured). Soft-fail
     on start (DDR-021). JNB-108 bounded-background bind-retry
     (`FORGE_SUBSCRIBER_BIND_RETRY_DELAYS_SECONDS` pattern) for startup races.
   - Shutdown: stop the consumer alongside blocks 1b2/1b3; cancel any bind-retry task.
7. **Docs** — if a new bind-retry env var is added, document it in `.env.example`;
   otherwise state in the task notes that no new env var is required (the consumer
   reuses `JARVIS_SLACK_PLANNING_CHANNEL_ID` + `JARVIS_SLACK_BOT_TOKEN`).

## Acceptance Criteria

- [ ] A planned-handoff `NotificationPayload` with `parent_request_id` renders as a
      reply in that thread, includes the message verbatim + the correlation id, and
      posts nothing outside the thread. (@smoke — scenario "A planned handoff
      notification is rendered into the originating thread")
- [ ] A notification with **no** thread anchor is posted top-level in the planning
      channel, includes the correlation id, and is **not dropped**. (@negative —
      "degrades to the channel and is never dropped")
- [ ] A malformed notification is logged and skipped (acked); a following valid
      notification still renders. (@negative — "A malformed notification is skipped
      and the consumer keeps running")
- [ ] A duplicate delivery of the same envelope (same `message_id`) renders once.
      (@edge — "A duplicate delivery ... renders only once")
- [ ] After a simulated restart (fresh consumer instance, no retained jarvis state),
      a notification for a run originated pre-restart still threads correctly, with
      the anchor taken from the payload — not from anything jarvis remembered.
      (@smoke @edge — "The thread mapping survives a Jarvis restart")
- [ ] A burst of notifications for one run all render, in publication order.
      (@edge — "A burst of notifications for the same run all render in order")
- [ ] The consumer is wired only when nats + `slack_planning_channel_id` +
      `slack_bot_token` are all present; otherwise a logged no-op (no crash).
- [ ] On a transient post failure the message is NAK'd (redelivered), not lost.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- `tests/test_planning_notifier.py` — unit: dedup by `message_id`, malformed-skip
  + ack, threaded vs degrade rendering, target_user mention, blocks passthrough,
  429/Retry-After budget in `post_threaded`, NAK-on-post-failure.
- `tests/test_planning_notifier_scenarios_spl003.py` — the 6 notification scenarios
  above, driven by a fake JetStream (`SimpleNamespace` msgs with `.data`/`.ack`/`.nak`)
  and an `AsyncMock` web client. Restart-survival = fresh consumer instance re-processing
  a payload; ordering = a fake that delivers N messages sequentially and asserts
  `chat_postMessage` call order. Fully hermetic — no live Slack/NATS.
- `tests/test_lifecycle_planning_notifier_wiring.py` — the AppState field is set when
  planning config present, absent (no-op) otherwise; shutdown stops it.
- Collect-only guard pinning the scenario count.

## Coach Validation

```
.venv/bin/python -m pytest tests/test_planning_notifier.py tests/test_planning_notifier_scenarios_spl003.py tests/test_lifecycle_planning_notifier_wiring.py -x -q
.venv/bin/ruff check src/jarvis/infrastructure/planning_notifier.py
.venv/bin/ruff format --check src/jarvis/infrastructure/planning_notifier.py
.venv/bin/mypy src/jarvis/infrastructure/planning_notifier.py
```

## Notes

The forge producer today emits a bare `NotificationPayload` (no anchor) → the
degrade path is exercised live. Threaded rendering activates once forge-half
TASK-SPL003F-001 projects `parent_request_id`. Both paths ship here; neither drops.
