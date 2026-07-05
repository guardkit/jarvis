---
id: TASK-JNB-008
title: v1 scenario test matrix (plain pytest, no BDD glue)
status: in_review
created: 2026-07-03 15:30:00+00:00
updated: 2026-07-03 15:30:00+00:00
priority: high
task_type: testing
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 5
repo: jarvis
implementation_mode: task-work
complexity: 6
dependencies:
- TASK-JNB-005
- TASK-JNB-006
tags:
- ubs-003
- jarvis-notification-bridge
- slack
- v1
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-28FF
  base_branch: main
  started_at: '2026-07-03T21:53:35.135034'
  last_updated: '2026-07-03T22:06:27.742852'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-07-03T21:53:35.135034'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: v1 scenario test matrix (plain pytest, no BDD glue)

## Description

Build the integration-style plain-pytest matrix in `jarvis/tests` that drives synthetic MessageEnvelopes through the real `ForgeNotificationsSubscriber` + `SlackNotifier` with a mocked Slack client, with one test class per v1 scenario (the full 20-scenario list is embedded below — the jarvis autobuild worktree cannot read the sibling forge repo, so this file is self-contained). Deliberately no pytest-bdd `.feature` glue anywhere (operator decision 2026-07-03): pytest-bdd glue is a known silent-false-green class, where unbound scenarios collect as zero tests and the suite passes vacuously. The verify step therefore includes a pytest collect-only count assertion so a collection regression cannot masquerade as green.

Architecture context: the Slack surface is the new module `src/jarvis/infrastructure/slack_notifier.py` living in-process in the jarvis supervisor. It implements a NotificationSink protocol — `notify(ForgeNotification)` enqueues onto a bounded `asyncio.Queue` drained by one worker task serialising `chat.postMessage` at ~1 msg/s, with mrkdwn disabled / Block Kit `plain_text` objects so rationale and failure_reason are inert, long rationales chunked under Slack's ~3000-char-per-block limit, 429 Retry-After honoured with a bounded per-message retry budget, and every other failure WARNING + drop (DDR-007: the SQLite ledger is authoritative; the notifier can never raise into the JetStream callback or `queue_build`). `ForgeNotificationsSubscriber` calls `sink.notify()` inside `_handle_message` after envelope decode + `source_id == 'forge'` gate + typed payload validation, but before and independent of the correlation-map lookup (fan-out is correlation-INDEPENDENT by design). `stage_complete`/`build_progress`/`build_resumed` are suppressed at the sink policy (ASSUM-002). The queued event never touches the stream: `tools/dispatch.py` `queue_build` calls the sink fire-and-forget after the PubAck/register_correlation block, and failures never alter the returned `QueueBuildAck`. Dedup lives inside `SlackNotifier` at enqueue time — first-wins 300s TTL map keyed `(event_type, build_id, stage_label or '')` for stream events and `('build_queued', correlation_id)` for the intake event, monotonic clock, evict-on-insert; bounded-queue overflow drops oldest with one WARNING. `coach_score` None renders "score unavailable"; out-of-range floats render as inert text, never rejected. The sink is constructed in `infrastructure/lifecycle.py` `build_app_state` only when `JARVIS_SLACK_BOT_TOKEN` + `JARVIS_SLACK_CHANNEL_ID` are set, otherwise a logged no-op sink.

## Acceptance Criteria

- [ ] One plain-pytest test class exists per v1 scenario listed under Test Requirements (20 classes), named to mirror the scenario names
- [ ] Tests drive synthetic MessageEnvelopes through the real `ForgeNotificationsSubscriber._handle_message` and the real `SlackNotifier`, with only the Slack client mocked (no re-implementation of subscriber or notifier logic in test doubles)
- [ ] No pytest-bdd anywhere in the new tests: no `.feature` files, no `scenarios()`/`@scenario` glue, no pytest-bdd import
- [ ] A collect-only count assertion is in place: `.venv/bin/python -m pytest <matrix path> --collect-only -q` is asserted (in a guard test or the documented verify command) to collect the expected number of tests, and the expected number is pinned so a collection regression fails rather than passing vacuously
- [ ] Malformed and unrecognised-source envelopes are dropped without any Slack client call and without raising
- [ ] Delivery-failure tests assert outcome preservation: a Slack client failure logs WARNING, drops the message, and never propagates into the JetStream callback or alters `queue_build`'s returned ack (DDR-007)
- [ ] Dedup tests assert first-wins 300s TTL semantics on the documented keys, including the duplicate-terminal case
- [ ] Throttling burst tests assert the single worker drains at the serialised rate and 429 Retry-After is honoured within the bounded retry budget; overflow drops oldest with one WARNING
- [ ] No-replay-on-restart test asserts the in-memory posture (DDR-027): a rebuilt subscriber/notifier does not re-emit previously delivered notifications from stream history
- [ ] Full suite green via `.venv/bin/python -m pytest` from the jarvis repo root

## Test Requirements

Plain pytest ONLY — no pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror the spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root. Tests live in `jarvis/tests`.

The 20 v1 scenarios (embedded here because the jarvis-scoped autobuild worktree cannot read the sibling forge repo):

1. Queued rendering — `queue_build` hook posts the build-queued message with correct fields
2. Started rendering — build-started envelope renders correctly
3. Complete rendering — build-complete envelope renders correctly
4. Failed rendering — build-failed envelope renders failure_reason as inert text
5. Paused rendering, no-score smoke — `coach_score` None renders "score unavailable"
6. Paused rendering, 0.0 score boundary — renders 0.0 (falsy float must not fall through to "score unavailable")
7. Paused rendering, 1.0 score boundary — renders 1.0
8. Cancelled rendering — build-cancelled envelope renders `cancelled_by` and reason
9. Suppression — `stage_complete`/`build_progress`/`build_resumed` produce no Slack call (ASSUM-002 sink policy)
10. Duplicate-terminal dedup — a redelivered terminal event within 300s posts exactly once (first-wins)
11. Malformed drop — undecodable envelope is dropped without raising and without a Slack call
12. Unrecognised-source drop — `source_id != 'forge'` is dropped without a Slack call
13. Delivery-failure outcome-preservation — Slack client raises; WARNING logged, message dropped, no exception into the JetStream callback, `queue_build` ack unaltered (DDR-007)
14. Inert-text — hostile mrkdwn/injection content in rationale/failure_reason arrives as `plain_text`, not interpreted
15. Long-rationale — rationale beyond the ~3000-char block limit is chunked and arrives intact
16. Throttling burst — a burst of notifications is serialised at ~1 msg/s by the single worker; 429 Retry-After honoured within the bounded retry budget
17. Concurrent terminals — terminal events for distinct builds arriving concurrently each post exactly once with no cross-contamination
18. No-replay-on-restart — rebuilding the subscriber/notifier does not re-post history (DDR-027 in-memory posture)
19. Degraded start — missing `JARVIS_SLACK_BOT_TOKEN`/`JARVIS_SLACK_CHANNEL_ID` yields the logged no-op sink; envelopes flow without error and without Slack calls
20. Two-build field isolation — interleaved envelopes for two builds render each message with its own build's fields only

Collect-only count assertion requirement: pin the expected collected-test count for the matrix (at minimum, assert the 20 scenario classes each collect at least one test) via `.venv/bin/python -m pytest <matrix path> --collect-only -q`, so any future collection breakage fails loudly instead of passing green with zero tests.

## Implementation Notes

- Dependencies: TASK-JNB-005 (pause + cancelled lifecycle: filter extension and rendering) and TASK-JNB-006 (hardening: 300s first-wins dedup, throttling backoff, overflow bounds) must both be merged — scenarios 5-10, 16-18 exercise behaviour those tasks introduce.
- Key constraints to respect in fixtures and assertions:
  - Workqueue err-10100 single-consumer rule: there is exactly one ephemeral PIPELINE consumer; the Slack surface is an in-process sink invoked inside its `_handle_message`, never a second consumer. Do not construct tests that stand up an additional PIPELINE consumer.
  - DDR-007 never-regress: the notifier can never raise into the JetStream callback or `queue_build`; failures are WARNING + drop, and the SQLite ledger stays authoritative.
  - DDR-027 no-replay: dedup and delivery state are in-process only; restart tests assert absence of replay, not persistence.
  - Correlation-INDEPENDENT fan-out is deliberate: `sink.notify()` fires after decode/source-gate/payload validation but independent of the correlation-map lookup, so the phone surface survives LRU loss on restart and receives events for builds not queued through jarvis. Tests must not gate notification assertions on correlation-map hits.
- Dedup keys: `(event_type, build_id, stage_label or '')` for stream events; `('build_queued', correlation_id)` for the intake event. Monotonic clock; evict-on-insert; first-wins 300s TTL (ASSUM-006).
- The queued event originates from the `tools/dispatch.py` `queue_build` publish-side hook (module-level `_notification_sink` snapshot mirroring the existing `_forge_subscriber`/`_nats_client` pattern), not from the stream — scenario 1 must exercise that hook, not a synthetic envelope.
- The jarvis autobuild worktree is jarvis-scoped and cannot read the sibling forge repo: everything needed (scenario list, keys, constraints) is embedded in this file; do not reference forge sources.
- Run tests with `.venv/bin/python -m pytest` (the default python lacks required packages).
