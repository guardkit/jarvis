---
id: TASK-JNB-107
title: "LIVE v1.1 validation: approve/reject from the phone"
status: completed
created: 2026-07-03T15:30:00Z
updated: 2026-07-07T08:30:00Z
completed: 2026-07-07T08:30:00Z
priority: high
task_type: operator_handoff
parent_review: TASK-REV-C951
feature_id: FEAT-BF39
version: v1.1
wave: 10
repo: jarvis
implementation_mode: direct
complexity: 3
dependencies: [TASK-JNB-102, TASK-JNB-104, TASK-JNB-105, TASK-JNB-106, TASK-JNB-OPS-001, TASK-GATE-D659, TASK-JNB-110]
tags: [ubs-003, jarvis-notification-bridge, slack, v1.1]
---

# Task: LIVE v1.1 validation: approve/reject from the phone

> **⚠️ Amended 2026-07-06 by TASK-JNB-110 (identity contract v2 — land JNB-110
> first; now a dependency).** The `decided_by`/`expected_approver` alignment is no
> longer the literal `rich`. jarvis publishes the **actual clicker's Slack member
> id** as `decided_by` (one identity scheme fleet-wide); forge's build-gate
> `approval.expected_approver` must be set to the approver's **Slack member id**
> (`U…`), config-only. Authorization is now the allowlist
> `JARVIS_SLACK_OPERATOR_USER_IDS` (comma-separated member ids; the singular
> `JARVIS_SLACK_OPERATOR_USER_ID` still folds in, deprecated).
> `JARVIS_SLACK_DECIDED_BY` is **removed/deprecated** — do not set it. Everywhere
> below that says `JARVIS_SLACK_DECIDED_BY=rich` or "`expected_approver` == jarvis
> `slack_decided_by`" now reads "forge `expected_approver` == the approver's Slack
> member id == the published `decided_by`". The live probe still confirms the
> alignment; only the value changed (member id, not `rich`).

## Description

Operator, on live NATS/Slack/forge-serve: run a gated toy build to a pause — tap Approve on the phone and observe build-resumed then a terminal notification; run a second and tap Reject — SQLite records CANCELLED and the phone receives the build-cancelled terminal notification (live-closing the ASSUM-010 loop and verifying the expected_approver/decided_by config alignment); have a non-operator Slack account tap a button — refused with the build still paused; let one pause breach the window — cancelled with a phone terminal signal. Marks v1.1 complete.

This validation exercises the complete v1.1 reply path end to end. On the forge side, the ApprovalSubscriber is constructed in the forge-serve runtime and injected as the already-typed `ApprovalGateDeps.subscriber` (gating/wrappers.py:396), so the existing `await_response` call sites (wrappers.py:556/801) consume `agents.approval.forge.{build_id}.response` through the untouched four-step validation chain: payload validation -> decided_by allowlist vs expected_approver -> correlation_id match -> request_id 300s dedup. An approve dispatch resumes the build via the subscriber resume-emit seam activated by TASK-GATE-D659 (`maybe_gate_build` in the daemon dispatch flow — the previously-cited `autobuild_runner.mark_resume_pending` mechanism was killed by JNB-101's arch review as dead-and-broken and removed by TASK-GATE-D659 §D5; corrected 2026-07-06); a reject, the REASON_MAX_WAIT breach (wrappers.py:563-574), and `CliSteeringHandler.handle_cancel` now each trigger the existing `publish_build_cancelled` (pipeline_publisher.py:272), best-effort per DDR-007 with the SQLite ledger authoritative. On the jarvis side, a small subscriber on `agents.approval.forge.>` (AGENTS stream, limits retention, overlap legal) captures `ApprovalRequestPayload.request_id` per build_id, the pause Slack message carries Block Kit Approve/Reject buttons whose value JSON is `{request_id, build_id, correlation_id, approval_subject}`, and a Socket Mode client (JARVIS_SLACK_APP_TOKEN, outbound WebSocket, no public endpoint) handles `block_actions`: the sole Slack-side gate is `user.id in JARVIS_SLACK_OPERATOR_USER_IDS` (allowlist; post-JNB-110); an authorized click publishes `ApprovalResponsePayload(request_id, decision, decided_by=<clicking member id>)` to `approval_subject + '.response'`, then `chat.update` disables the buttons. Window/expiry-race enforcement stays exclusively forge-side, so a reply-vs-expiry race resolves in exactly one place.

This is the final wave-10 gate: it requires the merged output of BOTH repos (jarvis waves 7-9 tasks and forge TASK-JNB-101/102/106 **plus the TASK-GATE-D659 gate activation**) deployed together, and **TASK-JNB-OPS-001 complete first** (no live Slack traffic before the secrets move). Live prerequisites (bot /invite to #forge-builds, the **five** JARVIS_SLACK_* env vars — including the app token and `JARVIS_SLACK_DECIDED_BY=rich`, verbatim-equal to forge `expected_approver` — healthy ships-computer-nats broker) were verified 2026-07-03 but are perishable — re-check them before starting. Pre-flight additions (2026-07-06 audit): `nats consumer info` on the GB10 PIPELINE durable to confirm `ack_wait=1h` (no runtime artifact exists for the re-pin), and assess forge TASK-FWD-002/003/004 (`forge/tasks/backlog/forge-wire-dispatch-fixes/`) — open defects on the gated-build dispatch path (FWD-003's redelivery wedge interacts with the window-breach scenario; FWD-004's duplicate GB10 runner unit can double-dispatch).

## Acceptance Criteria

- [x] Preconditions confirmed: forge-serve running with ApprovalSubscriber wiring (TASK-JNB-101/102 merged) AND gate activation deployed (TASK-GATE-D659), TASK-JNB-OPS-001 done, TASK-JNB-110 landed on both repos, jarvis supervisor restarted with the JARVIS_SLACK_* env vars set — `JARVIS_SLACK_OPERATOR_USER_IDS` (allowlist of member ids; NO `JARVIS_SLACK_DECIDED_BY`) — and the Socket Mode client connected, forge `approval.expected_approver` set to the approver's Slack member id, bot present in the Slack channel, ships-computer-nats broker healthy, GB10 PIPELINE durable `ack_wait` verified, and the TASK-JNB-105/106 test suites green on the deployed commits.
- [x] Approve loop: a gated toy build reaches a pause; the phone shows the pause message with live Approve/Reject buttons; tapping Approve produces a build-resumed notification followed by a terminal notification on the phone, and the buttons are disabled in place via chat.update.
- [x] Reject loop (ASSUM-010 closed live): a second gated toy build is paused; tapping Reject transitions the build to CANCELLED in the forge SQLite ledger AND the phone receives the build-cancelled terminal notification.
- [x] Config alignment proven live (identity contract v2, TASK-JNB-110): the accepted approve/reject decisions confirm forge `expected_approver` == the approver's Slack member id == the published `decided_by` (the clicker's own id) exactly (any mismatch would surface as forge silently refusing the phone decision — the build would stay paused).
- [x] Unauthorized click refused: a non-operator Slack account taps a button and receives an ephemeral refusal; jarvis logs a WARN, publishes nothing, and the build remains paused and still approvable by the operator.
- [x] Window breach: one pause is left to breach the approval window (REASON_MAX_WAIT); forge cancels the build and the phone receives the build-cancelled terminal signal.
- [x] Each notification in the above runs arrives exactly once on the phone (dedup from TASK-JNB-006 holding under live at-least-once delivery).
- [x] jarvis supervisor logs across the session show no err_code 10100 (still exactly one PIPELINE consumer; the approval-request capture binds only the AGENTS stream).
- [x] v1.1 marked complete once all of the above are observed.

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
- Alignment is config, not code (post-JNB-110): forge `expected_approver` must equal the approver's Slack member id, which is exactly what jarvis publishes as `decided_by` (the clicker's own id). A mismatch silently refuses every phone approval. This task is the live probe of that alignment — if Approve does nothing, check forge `expected_approver` against the clicking member's `U…` id first.
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

## Live validation record (2026-07-07, operator: Rich)

All four live scenarios validated on production (forge-prod image `43402d07`,
jarvis redeployed on JNB-110/JNB-111 code). Canonical evidence: forge
`docs/state/TASK-MP-012/deploy-verification-2026-07-06-evening.md` addenda
5-7 (forge commits `99c36e8`, `482b5de`, `3041621` — "ALL FOUR SCENARIOS
COMPLETE; Gate G1 condition met").

- **Scenario 1 (approve loop)** ✅ 06:48 UTC — first completed phone approval
  round-trip: tap → `slack_reply_decision_published` → forge
  `gate decided outcome=RESUMED` → autobuild launched → terminal signal on
  the phone (toy build's expected failure IS the terminal signal).
- **Scenario 2 (reject, ASSUM-010 closed live)** ✅ 07:00 UTC — one second
  tap-to-CANCELLED: ledger CANCELLED authoritative-first (DDR-007 ordering
  held), no launch, build-cancelled terminal on the phone.
- **Scenario 3 (unauthorized click)** ✅ 07:16 UTC — non-allowlisted account
  (U0BFNQ969U1) refused: WARN `slack_reply_unauthorized_click`, ephemeral
  refusal operator-confirmed, ZERO publishes, build stayed PAUSED; the
  operator's real account then approved the SAME prompt → RESUMED →
  RUNNING ("paused and still approvable" proven on one prompt).
- **Scenario 4 (window breach)** ✅ ×11 (2026-07-06 evening + overnight) —
  REASON_MAX_WAIT cancel with phone terminal signal each time.
- **Identity contract v2 alignment proven live**: accepted decisions confirm
  forge `expected_approver` == the approver's Slack member id == published
  `decided_by` (clicker's own id, verbatim).
- **Zero `err_code 10100` across the session** (single-PIPELINE-consumer
  rule held; approval capture bound only the AGENTS stream).
- **Dedup clean** under live at-least-once delivery (addendum `123f1f7`).

Dependencies at completion: JNB-102/104/105/106, OPS-001, GATE-D659,
JNB-110 all landed/deployed; JNB-111 (core-publish on the no-ack AGENTS
stream) completed 2026-07-07 before the formal scenarios, so taps reported
success truthfully.

**v1.1 is marked complete. SPL Gate G1: PASS — UBS-003 v1.1 formally
shipped.**
