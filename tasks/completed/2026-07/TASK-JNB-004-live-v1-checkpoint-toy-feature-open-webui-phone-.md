---
id: TASK-JNB-004
title: "LIVE V1 CHECKPOINT: toy feature Open WebUI -> phone queued->running->terminal"
status: completed
created: 2026-07-03T15:30:00Z
updated: 2026-07-04T10:30:00Z
priority: high
task_type: operator_handoff
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 3
repo: jarvis
implementation_mode: direct
complexity: 3
dependencies: [TASK-JNB-003]
tags: [ubs-003, jarvis-notification-bridge, slack, v1]
---

# Task: LIVE V1 CHECKPOINT: toy feature Open WebUI -> phone queued->running->terminal

## Description

Operator: /invite the Jarvis Forge Bridge bot to #forge-builds, restart the jarvis supervisor with the JARVIS_SLACK_* env vars, queue a toy feature from Open WebUI, and observe the phone receive queued -> running -> terminal over live NATS/Slack, each exactly once. Also verify boot logs show the single consumer bound with no err_code 10100, and on a second run break the bot token deliberately to confirm WARNING logs while the build completes normally in the forge ledger (DDR-007). Hard gate: no v1.1 task starts until this passes.

This checkpoint exercises the complete v1 wiring landed by waves 1-2. The Slack sender is `src/jarvis/infrastructure/slack_notifier.py`, an in-process component of the jarvis supervisor (not a separate adapter process) implementing the NotificationSink protocol: `notify(ForgeNotification)` enqueues onto a bounded asyncio.Queue drained by one worker task serializing `chat.postMessage` at ~1 msg/s, with mrkdwn disabled / Block Kit `plain_text` objects so rationale and failure_reason are inert. It is constructed in `infrastructure/lifecycle.py` `build_app_state` only when `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID` are set; otherwise a logged no-op sink is bound, and NATS-down keeps the existing DDR-021 soft-fail.

Event flow under test: the `queued` message comes from the publish-side hook in `tools/dispatch.py` `queue_build` (fired immediately after the PubAck/register_correlation block via the module-level `_notification_sink` snapshot — it never touches the stream); `running` and the terminal message arrive through the single existing ephemeral PIPELINE consumer, whose existing 4-subject filter already carries build-started/complete/failed. Zero forge changes, zero new NATS consumers, and no filter changes exist before this checkpoint. The sink is invoked inside `_handle_message` after envelope decode, the `source_id=='forge'` gate, and typed payload validation, but independent of the correlation-map lookup — the phone is per-operator, not per-session.

## Acceptance Criteria

- [ ] Perishable prerequisites re-checked first: the Jarvis Forge Bridge bot is /invited to #forge-builds, the JARVIS_SLACK_* env vars are present in the supervisor environment (at minimum `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID`, which gate SlackNotifier construction), and the ships-computer-nats broker is healthy (all verified 2026-07-03 but perishable).
- [ ] jarvis supervisor restarted with the JARVIS_SLACK_* env vars; boot logs show the SlackNotifier constructed (not the no-op sink).
- [ ] Boot logs show the single ephemeral PIPELINE consumer bound with no err_code 10100.
- [ ] A toy feature queued from Open WebUI produces a `queued` message on the phone (from the `queue_build` publish-side hook).
- [ ] The phone then receives `running` and the terminal message (complete or failed) over live NATS/Slack, each exactly once.
- [ ] Second run with the bot token deliberately broken: jarvis logs WARNING on Slack delivery failure, no exception reaches the JetStream callback or `queue_build`, and the build completes normally in the forge SQLite ledger (DDR-007).
- [ ] Hard gate confirmed: no v1.1 task (TASK-JNB-101 onward) starts until this checkpoint passes.

## Test Requirements

This is a live operator checkpoint, not an automated test task — no new pytest scenarios are added here. All automated verification lives in the dependency tasks and in TASK-JNB-008 (plain pytest classes mirroring spec scenario names; no pytest-bdd .feature glue anywhere, per operator decision 2026-07-03).

Before the live run, confirm the merged v1 wiring is green by running the existing jarvis suite from the jarvis repo root:

```
.venv/bin/python -m pytest
```

Zero failures is a precondition for starting the live checkpoint.

## Implementation Notes

- Dependency: TASK-JNB-003 — Lifecycle wiring: construct and bind SlackNotifier in build_app_state. This checkpoint transitively validates TASK-JNB-001 (settings + slack-sdk + SlackNotifier checkpoint-slice rendering) and TASK-JNB-002 (sink seam in ForgeNotificationsSubscriber + queued hook in queue_build).
- Single-consumer rule (workqueue err-10100): the Slack surface is an in-process sink invoked inside the one existing ephemeral consumer's `_handle_message`, so a second PIPELINE consumer is structurally impossible — but this task verifies it live: boot logs must show exactly one PIPELINE consumer bound and no err_code 10100.
- DDR-007 never-regress: the SQLite ledger is authoritative; the notifier can never raise into the JetStream callback or `queue_build`. Every non-429 failure is WARNING + drop. The broken-token run proves this live.
- DDR-027 no-replay: dedup and notification state are in-process only; nothing is replayed from the stream on restart.
- Correlation-INDEPENDENT fan-out is deliberate: the phone will show started/terminal events for builds not queued through jarvis; a jarvis restart (LRU correlation loss) must not blind the overnight surface. DDR recorded in TASK-JNB-007.
- Dedup/throttling (TASK-JNB-006) land post-checkpoint: an at-least-once redelivery during the toy run could double-post a message — cosmetic and acceptable for a single toy build, but expect it as a possibility. `coach_score` None rendering as "score unavailable" is today's live default per ADR-ARCH-033.
- The autobuild worktree for jarvis tasks is jarvis-scoped and cannot read the sibling forge repo; this task is operator-run, so ledger verification happens directly in the forge deployment, outside any worktree.

## Required operator follow-up

This task is task_type: operator_handoff — AutoBuild will not attempt it. The operator must verify the runtime acceptance criteria below manually, then mark the task complete via /task-complete.

- /invite the Jarvis Forge Bridge bot to #forge-builds.
- Restart the jarvis supervisor with the JARVIS_SLACK_* env vars.
- Queue a toy feature from Open WebUI.
- Observe the phone receive queued -> running -> terminal over live NATS/Slack, each exactly once.
- Verify boot logs show the single consumer bound with no err_code 10100.
- On a second run, break the bot token deliberately to confirm WARNING logs while the build completes normally in the forge ledger (DDR-007).
- Hard gate: no v1.1 task starts until this passes.


## Completion record (2026-07-04)

PASSED on live GB10 evidence, observed in #forge-builds:
- queued: 07:14 (jarvis publish, correlation A) and 11:07 (clean Open WebUI
  run) — exactly once per build (ASSUM-011 path).
- build-started (RUNNING): 09:58 (real FEAT-9E59 build, SDK harness).
- build-complete (PASSED) + summary: 09:58 and 11:07 — exactly once each,
  dedup held under replay-preface batch delivery.
- Boot AC: forge_notifications_subscribed with 6 subjects, no err_code 10100;
  slack_notifier_started (real channel, not no-op).
- DDR-007 held throughout: multiple forge-side dispatch failures during the
  session never regressed a build; SQLite stayed authoritative.

Collateral findings filed separately: 5 forge wire-dispatch bugs (identity
LIMIT-1, unarmed deadline timer, duplicate-guard wedge, duplicate sidecar
unit, ABW-002), jarvis NATS-user pipeline grant (fixed, nats-infrastructure
d252c35), guardkit langgraph-harness default vs GB10 sidecar (GUARDKIT_HARNESS
=sdk + coach-model argv removal, both to revert for P2).
