---
id: TASK-SPL-J01
title: "jarvis: planning intake handler module + settings keys (FEAT-SPL-001)"
status: backlog
created: 2026-07-06T10:20:00Z
updated: 2026-07-06T10:20:00Z
priority: high
task_type: feature
parent_review: TASK-REV-3240
feature_id: FEAT-SPL-001
wave: 1
repo: jarvis
implementation_mode: task-work
complexity: 6
dependencies: []
tags: [sovereign-planning-loop, feat-spl-001, slack, planning-intake]
---

# Task: Planning intake handler module + settings keys

## Description

New module `src/jarvis/infrastructure/slack_planning_intake.py` (beside
`slack_reply.py`, mirroring its handler / publisher-seam / factory shape): an
`events_api` message handler that turns an authorized top-level message in the
planning channel into a `PlanningQueuedPayload` published to JetStream, with a
best-effort in-thread ack. Plus the two settings fields and the nats-core pin
bump. No reasoning anywhere on this path — intake only (SPL scope §5).

Review-report findings F3–F6, F9–F12 (`.claude/reviews/TASK-REV-3240-review-report.md`)
are binding ACs for this task.

## Deliverables

1. **Settings** (`src/jarvis/config/settings.py`, FEAT-SPL block after the
   FEAT-BF39 block):
   - `slack_planning_channel_id: str | None = None` — JARVIS_SLACK_PLANNING_CHANNEL_ID.
   - `slack_planning_originator_user_id: str | None = None` —
     JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID. **Allow-list-ready** (F-hedge for
     ASSUM-001): the intake factory parses comma-separated member ids into a
     frozenset; v1 documented as single-id. Comments cite FEAT-SPL-001 and the
     no-op semantics (both unset ⇒ intake is a logged no-op).
2. **Pin bump** (`pyproject.toml`): `nats-core>=0.4` → `nats-core>=0.5` (F9 —
   the planning contract is 0.5.0-only; the editable-sibling source makes the
   stale pin inert locally, which is exactly why it must be fixed by contract).
3. **Handler** — `PlanningIntakeHandler` (never-raises, DDR-007 backstop like
   `ApprovalReplyHandler.handle_block_actions`). Gate order pinned (F3):
   1. `event.type == "message"` (envelope payload type `event_callback`/events_api)
   2. channel == configured planning channel (else silent drop)
   3. `bot_id`/`app_id`/`subtype` present → DEBUG drop (loop prevention; **never**
      counted as a refusal — modern bot posts are subtype-free with `bot_id` set)
   4. `thread_ts` present → drop (top-level only, ASSUM-006)
   5. originator gate: `event["user"]` (None-safe get; missing ⇒ drop) must be in
      the configured frozenset — the ONLY branch logging an authorization
      refusal, at **INFO** not WARN (F11), metadata-only
   6. blank-text pre-check: `not text.strip()` → logged discard, no ack (F10)
   7. dedup (below), then payload construction wrapped in
      `except ValidationError` → logged discard (backstop)
4. **Dedup** (F5): `dict[str, float]` on the handler instance, key =
   `event_id` falling back to `f"{channel}:{ts}"`, `time.monotonic()` deadlines,
   TTL 300s, cap 1000 (module constants, JNB-103 precedent), evict-on-insert.
   **Synchronous check-and-mark before the first await**; **un-mark on publish
   failure** (nothing queued ⇒ Slack redelivery may retry; mirrors the JNB-104
   discard-on-publish-failure posture). Duplicate hit → INFO
   `planning_intake_duplicate_dropped` with event_id.
5. **Payload construction** (F4, ASSUM-008): `PlanningQueuedPayload(`
   `request_text=text, target_repo=None, triggered_by="jarvis",`
   `originating_adapter="slack"` **(explicit constant — the wire layer verifiably
   skips its validator on omission)**, `originating_user=event["user"],`
   `correlation_id=new_correlation_id(), parent_request_id=<message ts>,`
   `requested_at=<UTC datetime from the Slack ts float, wrapped with a
   UTC-now fallback (F12)>, queued_at=<publish time>)`. `retry_count` left 0.
6. **Publisher** — `PlanningQueuedPublisher` Protocol seam +
   `NatsPlanningQueuedPublisher` mirroring `NatsApprovalResponsePublisher`:
   `MessageEnvelope(source_id="jarvis", event_type=EventType.PLANNING_QUEUED,
   correlation_id=..., payload=payload.model_dump(mode="json"))`, subject
   `Topics.Pipeline.PLANNING_QUEUED.format(correlation_id=...)`,
   `asyncio.wait_for(js.publish(...), timeout=<config.pipeline_publish_timeout_seconds>)`
   (DDR-025 — timeout injected by the factory, not hardcoded; raises to caller).
7. **Ack / failure notice** (ASSUM-003, F-C2): publish first, then best-effort
   threaded `chat.postMessage` ("Queued for planning · `<correlation-id>`",
   `thread_ts` = original ts). On publish failure: best-effort threaded failure
   notice inviting a repost. Each `chat.*` call independently wrapped with its
   own structured WARNING (`planning_intake_ack_failed` /
   `planning_intake_failure_notice_failed`); a None web client degrades to a
   logged no-op. **Never ack success before the publish returns.**
8. **Factory** — `create_slack_planning_intake_handler(config, nats_client)`:
   returns the handler when `slack_planning_channel_id` +
   `slack_planning_originator_user_id` + `slack_bot_token` + NATS are all
   present; else logs `slack_planning_intake_no_op` naming the missing key(s)
   and returns None. Startup INFO logs the effective channel id + originator
   id(s) (F7). WARN when `slack_planning_channel_id == slack_channel_id` (F7).

## Acceptance Criteria

- [ ] Every gate arm, the dedup race posture, field mapping, publish-failure and
      ack-failure branches covered by unit tests (AsyncMock web client, mock
      publisher seam) — hermetic, no live Slack/NATS
- [ ] `originating_adapter == "slack"` asserted explicitly in payload tests
- [ ] **No log record on any path contains message text** (F6) — test asserts
      log fields on discard/refusal/duplicate/failure paths carry only
      {channel, ts, user_id, event_id, correlation_id, text_length, reason}
- [ ] Verbatim semantics documented as verbatim-modulo-outer-strip (F10) in the
      module/test docstrings
- [ ] Self-ack fixture is realistic: no subtype, `bot_id` set, user = bot user id
- [ ] Full existing suite stays green; new tests green
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

- Unit tests in `tests/` following the house per-module pattern
  (`test_slack_planning_intake.py`), AAA, descriptive names.

## Implementation Notes

- Read `slack_reply.py` first — the handler/publisher/factory shapes, the C2
  independent-wrap posture, and the never-raises discipline transfer verbatim.
- Do NOT import `dispatch._resolve_publish_timeout` (private seam); the factory
  has `JarvisConfig` in hand.
- A shared publish helper across the three publishers is explicitly deferred
  (rule-of-three noted; error taxonomies diverge — see review PLAN-1).
