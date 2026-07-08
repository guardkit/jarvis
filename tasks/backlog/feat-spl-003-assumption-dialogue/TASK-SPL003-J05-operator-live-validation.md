---
id: TASK-SPL003-J05
title: "jarvis: assumption-dialogue operator live-validation checklist (FEAT-SPL-003)"
status: backlog
priority: medium
task_type: operator_handoff
parent_review: TASK-REV-A387
feature_id: FEAT-SPL-003
wave: 6
repo: jarvis
implementation_mode: direct
complexity: 2
dependencies: [TASK-SPL003-J01, TASK-SPL003-J02, TASK-SPL003-J03a, TASK-SPL003-J03b, TASK-SPL003-J04]
tags: [sovereign-planning-loop, feat-spl-003, operator, live-validation]
---

# Task: Assumption-dialogue operator live-validation checklist

## Description

The live-only facts hermetic tests cannot prove (SPL-001 TASK-SPL-J04 pattern). AutoBuild
will not attempt this task. Runs once forge-half TASK-SPL003F-001 has projected the
per-assumption `details` (assumptions list + `parent_request_id` + `cycle`); until then
the notification return-channel (J01 degrade path) can be validated standalone.

## Required operator follow-up

This task is `task_type: operator_handoff`. Verify the runtime criteria below manually,
then mark complete via `/task-complete`.

- **AC-1 (return channel, standalone):** with `JARVIS_SLACK_PLANNING_CHANNEL_ID` +
  `JARVIS_SLACK_BOT_TOKEN` set, a `jarvis.notification.slack` publish renders in the
  planning channel (degrade path) — jarvis boot shows the planning-notification consumer
  started; the message is not dropped.
- **AC-2 (Slack Interactivity):** the Slack app manifest has **Interactivity enabled**
  (required for `views.open` / `view_submission`); the request URL / Socket Mode is
  configured so modal submissions co-deliver on the shared connection.
- **AC-3 (modal round-trip):** clicking **edit** on an assumption opens a prefilled modal
  within Slack's window; submitting records the override; the item updates in-thread.
- **AC-4 (end-to-end dialogue):** a real Mode P checkpoint renders per-assumption in the
  originating thread; per-item approve/edit/defer each land as distinct dispositions in
  the published `ApprovalResponsePayload` and the forge planning trace; the cap-3 →
  escalate-to-Rich boundary escalates rather than offering a fourth cycle.
