---
id: TASK-SPL-J04
title: "jarvis: FEAT-SPL-001 live-validation checklist (operator, JNB-107 style)"
status: backlog
created: 2026-07-06T10:20:00Z
updated: 2026-07-06T10:20:00Z
priority: high
task_type: operator_handoff
parent_review: TASK-REV-3240
feature_id: FEAT-SPL-001
wave: 4
repo: jarvis
implementation_mode: manual
complexity: 2
dependencies: [TASK-SPL-J01, TASK-SPL-J02, TASK-SPL-J03]
tags: [sovereign-planning-loop, feat-spl-001, slack, ops, live-validation]
---

# Task: FEAT-SPL-001 live-validation checklist (operator)

## Description

The hermetic suite proves all 18 scenarios' logic but four facts are live-only
(review F7/F8, RISK-3). This operator task validates them against real Slack +
the live NATS broker. Bundle with OPS-001 (the FEAT-BF39 operator checklist) —
same session works.

## Required operator follow-up

This task is `task_type: operator_handoff` — AutoBuild will not attempt it.
The operator must verify the runtime acceptance criteria below manually, then
mark the task complete via `/task-complete`.

- **AC-1 (manifest)**: The Slack app manifest carries the `message.channels`
  AND `message.groups` bot event subscriptions; the bot is `/invite`d to
  `#factory-planning`. (Private channels deliver via `message.groups` only.)
- **AC-2 (config)**: `JARVIS_SLACK_PLANNING_CHANNEL_ID` = the planning
  channel's id (NOT the notification channel — boot log WARNs on equality);
  `JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID` = the originator's Slack member
  id (James for the exemplar; Rich for pre-exemplar testing). Verify the boot
  log's startup INFO echoes both values. Secrets live in
  `~/.config/guardkit/jarvis.env` per OPS-001 — not in the repo.
- **AC-3 (stream pre-flight)**: `nats stream info PIPELINE` on the live broker
  shows subjects `pipeline.>`, work-queue retention (7d / 10k) — matches
  `nats-infrastructure/streams/stream-definitions.json`.
- **AC-4 (round-trip)**: Post one real message in the planning channel from the
  configured originator → observe the in-thread "Queued for planning ·
  <correlation-id>" ack → inspect the stream message on
  `pipeline.planning-queued.<correlation-id>` and confirm the
  `PlanningQueuedPayload` bytes carry `originating_adapter="slack"` and the
  poster's member id.
- **AC-5 (negative)**: A message from a non-originator member and a threaded
  reply produce NO publish and NO ack (check the intake log records —
  metadata-only, no message text anywhere).
- **AC-6 (redelivery observation, best-effort)**: If observable, confirm a
  redelivered envelope carries a stable `event_id` (validates the dedup key
  choice; ASSUM-005).

## Operator runbook

Full copy-paste step-by-step (Slack app config incl. the scope-reinstall
gotcha, env wiring into `~/.config/guardkit/jarvis.env` + systemd, the
work-queue-safe `nats stream get` inspection commands, and a
symptom→cause table):
`../ai-transition/docs/fable-window-execution-plan-2026-07-04.md`
§"TASK-SPL-J04 + OPS-001 — operator runbook" (added 2026-07-06).
Do OPS-001 (§Step 0) first in the same session — it also unblocks JNB-107.

## Notes

- Durability caveat until FEAT-SPL-002 lands: queued planning requests expire
  at the PIPELINE stream's 7-day / 10k-message bound — do not queue ideas you
  need to survive longer before Mode P deploys.
- Message edits do NOT update a queued run — repost instead (operator doc line).
- Post ideas as plain typed messages: attachments (`file_share`) and
  app-relayed posts (`bot_id`/`app_id` set) are ignored by design (F3 gate).
- At-least-once caveat: a publish-timeout "failure" may still have landed on
  the stream; before reposting after a failure notice, a paranoid check is
  `nats stream info PIPELINE` / inspecting the subject. `parent_request_id`
  (the Slack ts) is the stable dedup key handed to FEAT-SPL-002.
