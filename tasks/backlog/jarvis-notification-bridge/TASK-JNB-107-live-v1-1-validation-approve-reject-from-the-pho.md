---
id: TASK-JNB-107
title: "LIVE v1.1 validation: approve/reject from the phone"
status: backlog
created: 2026-07-03T15:30:00Z
updated: 2026-07-03T15:30:00Z
priority: high
task_type: operator_handoff
parent_review: TASK-REV-C951
feature_id: FEAT-BF39
version: v1.1
wave: 10
repo: jarvis
implementation_mode: direct
complexity: 3
dependencies: [TASK-JNB-102, TASK-JNB-104, TASK-JNB-105, TASK-JNB-106]
tags: [ubs-003, jarvis-notification-bridge, slack, v1.1]
---

# Task: LIVE v1.1 validation: approve/reject from the phone

## Description

Operator, on live NATS/Slack/forge-serve: run a gated toy build to a pause — tap Approve on the phone and observe build-resumed then a terminal notification; run a second and tap Reject — SQLite records CANCELLED and the phone receives the build-cancelled terminal notification (live-closing the ASSUM-010 loop and verifying the expected_approver/decided_by config alignment); have a non-operator Slack account tap a button — refused with the build still paused; let one pause breach the window — cancelled with a phone terminal signal. Marks v1.1 complete.

This validation exercises the complete v1.1 reply path end to end. On the forge side, the ApprovalSubscriber is constructed in the forge-serve runtime and injected as the already-typed `ApprovalGateDeps.subscriber` (gating/wrappers.py:396), so the existing `await_response` call sites (wrappers.py:556/801) consume `agents.approval.forge.{build_id}.response` through the untouched four-step validation chain: payload validation -> decided_by allowlist vs expected_approver -> correlation_id match -> request_id 300s dedup. An approve dispatch drives the first-ever `autobuild_runner.mark_resume_pending` call sites; a reject, the REASON_MAX_WAIT breach (wrappers.py:563-574), and `CliSteeringHandler.handle_cancel` now each trigger the existing `publish_build_cancelled` (pipeline_publisher.py:272), best-effort per DDR-007 with the SQLite ledger authoritative. On the jarvis side, a small subscriber on `agents.approval.forge.>` (AGENTS stream, limits retention, overlap legal) captures `ApprovalRequestPayload.request_id` per build_id, the pause Slack message carries Block Kit Approve/Reject buttons whose value JSON is `{request_id, build_id, correlation_id, approval_subject}`, and a Socket Mode client (JARVIS_SLACK_APP_TOKEN, outbound WebSocket, no public endpoint) handles `block_actions`: the sole Slack-side gate is `user.id == JARVIS_SLACK_OPERATOR_USER_ID`; an authorized click publishes `ApprovalResponsePayload(request_id, decision, decided_by=slack_decided_by)` to `approval_subject + '.response'`, then `chat.update` disables the buttons. Window/expiry-race enforcement stays exclusively forge-side, so a reply-vs-expiry race resolves in exactly one place.

This is the final wave-10 gate: it requires the merged output of BOTH repos (jarvis waves 7-9 tasks and forge TASK-JNB-101/102/106) deployed together. Live prerequisites (bot /invite to #forge-builds, the four JARVIS_SLACK_* env vars including the app token, healthy ships-computer-nats broker) were verified 2026-07-03 but are perishable — re-check them before starting.

## Acceptance Criteria

- [ ] Preconditions confirmed: forge-serve running with ApprovalSubscriber wiring (TASK-JNB-101/102 merged), jarvis supervisor restarted with all four JARVIS_SLACK_* env vars set and the Socket Mode client connected, bot present in the Slack channel, ships-computer-nats broker healthy, and the TASK-JNB-105/106 test suites green on the deployed commits.
- [ ] Approve loop: a gated toy build reaches a pause; the phone shows the pause message with live Approve/Reject buttons; tapping Approve produces a build-resumed notification followed by a terminal notification on the phone, and the buttons are disabled in place via chat.update.
- [ ] Reject loop (ASSUM-010 closed live): a second gated toy build is paused; tapping Reject transitions the build to CANCELLED in the forge SQLite ledger AND the phone receives the build-cancelled terminal notification.
- [ ] Config alignment proven live: the accepted approve/reject decisions confirm forge `expected_approver` == jarvis `slack_decided_by` exactly (any mismatch would surface as forge silently refusing the phone decision — the build would stay paused).
- [ ] Unauthorized click refused: a non-operator Slack account taps a button and receives an ephemeral refusal; jarvis logs a WARN, publishes nothing, and the build remains paused and still approvable by the operator.
- [ ] Window breach: one pause is left to breach the approval window (REASON_MAX_WAIT); forge cancels the build and the phone receives the build-cancelled terminal signal.
- [ ] Each notification in the above runs arrives exactly once on the phone (dedup from TASK-JNB-006 holding under live at-least-once delivery).
- [ ] jarvis supervisor logs across the session show no err_code 10100 (still exactly one PIPELINE consumer; the approval-request capture binds only the AGENTS stream).
- [ ] v1.1 marked complete once all of the above are observed.

## Test Requirements

No automated tests are added by this task — it is a live, manual validation. Plain pytest only applies to the prerequisite suites (no pytest-bdd .feature glue anywhere per the 2026-07-03 operator decision):

- Before the live run, confirm the jarvis v1.1 reply-path suite (TASK-JNB-105) passes: `.venv/bin/python -m pytest` from the jarvis repo root.
- Confirm the forge v1.1 production-wiring suite (TASK-JNB-106) passes: `.venv/bin/python -m pytest` from the forge repo root.
- The live scenarios in this task are the runtime counterparts of those suites; any live failure here should be reduced to a failing plain-pytest scenario in the relevant suite before re-attempting.

## Implementation Notes

Dependency summaries:
- TASK-JNB-102 — forge: emit build-cancelled on CANCELLED transitions (ASSUM-010 closure).
- TASK-JNB-104 — jarvis: Socket Mode reply path with operator-member-id authorization.
- TASK-JNB-105 — jarvis: v1.1 reply-path scenario tests (plain pytest).
- TASK-JNB-106 — forge: v1.1 scenario tests over the production wiring.

Key constraints and context for the operator:
- Single-consumer rule (workqueue err 10100): the Slack surface is an in-process sink inside the one existing ephemeral PIPELINE consumer; the only new NATS consumers (jarvis approval-request capture, forge ApprovalSubscriber) bind the AGENTS stream where limits retention permits overlap. Any err_code 10100 in boot logs is a hard failure of this validation.
- DDR-007 (never-regress): Slack/notify failures are WARNING + continue; the SQLite ledger is authoritative. The reject check here reads CANCELLED from SQLite first, then expects the phone signal — in that order.
- DDR-027 (no-replay): dedup and pending-approval state are in-process only; a jarvis restart mid-window can double-post low-impact noise. Cosmetic double-posts during the toy runs are tolerable; missing or wrong-order lifecycle signals are not.
- Correlation-INDEPENDENT fan-out is deliberate: the phone is per-operator, not per-session, so it will also show events for builds not queued through jarvis — do not misread these as duplicates of your toy builds.
- expected_approver (forge) vs slack_decided_by (jarvis) alignment is config, not code: a mismatch silently refuses every phone approval. This task is the live probe of that alignment — if Approve does nothing, check these two values first.
- Reply-auth layering: jarvis-side the sole gate is Socket Mode `user.id == JARVIS_SLACK_OPERATOR_USER_ID`; forge-side the four-step validation chain is the authoritative backstop. The unauthorized-click scenario exercises the jarvis gate; the forge chain runs on every accepted decision.
- A defer-republish that outruns the chat.update refresh can leave a briefly-stale button; forge safely refuses it (request_id dedup). If a tap is refused, wait for the refreshed message and tap again — this is UX-only, not a defect.
- Cross-repo: this task needs BOTH repos merged and deployed (waves 7-9 interleave jarvis and forge; autobuild cannot edit sibling repos, so wave discipline is the coordination mechanism). The autobuild worktree for jarvis tasks is jarvis-scoped and cannot read the sibling forge repo — everything needed for this validation is contained in this file.

## Required operator follow-up

This task is task_type: operator_handoff — AutoBuild will not attempt it. The operator must verify the runtime acceptance criteria below manually, then mark the task complete via /task-complete.

- Run a gated toy build to a pause on live NATS/Slack/forge-serve — tap Approve on the phone and observe build-resumed then a terminal notification.
- Run a second gated toy build and tap Reject — SQLite records CANCELLED and the phone receives the build-cancelled terminal notification (live-closing the ASSUM-010 loop and verifying the expected_approver/decided_by config alignment).
- Have a non-operator Slack account tap a button — refused with the build still paused.
- Let one pause breach the window — cancelled with a phone terminal signal.
- Marks v1.1 complete.
