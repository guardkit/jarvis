---
id: TASK-JNB-007
title: 'DDR set: sink seam, correlation-independent fan-out, dedup placement, ASSUM-010
  v1 acceptance'
status: completed
created: 2026-07-03 15:30:00+00:00
updated: 2026-07-03 15:30:00+00:00
priority: high
task_type: documentation
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 4
repo: jarvis
implementation_mode: direct
complexity: 2
dependencies:
- TASK-JNB-003
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
  started_at: '2026-07-03T17:53:17.497748'
  last_updated: '2026-07-03T18:03:00.834425'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-07-03T17:53:17.497748'
    player_summary: 'Created four comprehensive Design Decision Records (DDRs) documenting
      the v1 Slack notification bridge architecture decisions:


      1. DDR-032: Documents the in-process NotificationSink protocol implementation
      as the architectural seam, explaining why no second PIPELINE consumer is created
      (workqueue err_code 10100 constraint), deferral of FEAT-JARVIS-006 wire promotion,
      and how the protocol serves as the plug point for future JARVIS-stream publishers.


      2. DDR-033: Documents correlation-independent '
    player_success: true
    coach_success: true
---

# Task: DDR set: sink seam, correlation-independent fan-out, dedup placement, ASSUM-010 v1 acceptance

## Description

Write decision records under jarvis `docs/design` capturing four decisions made for the v1 Slack notification bridge, now that the implementation they describe is wired (TASK-JNB-003 landed the lifecycle binding):

1. **In-process Slack sink inside the single PIPELINE consumer.** The Slack surface is `src/jarvis/infrastructure/slack_notifier.py`, a `NotificationSink` protocol implementation living in the jarvis supervisor process — not a separate adapter process and not a second JetStream consumer. Record why no second PIPELINE consumer is created (the workqueue single-consumer rule: a second bind raises err_code 10100; the sink is invoked inside the one existing ephemeral consumer's `_handle_message`), why the FEAT-JARVIS-006 `jarvis.notification.{adapter}` wire promotion is explicitly deferred, and how the sink protocol is the plug point a future JARVIS-stream publisher slots into without touching the subscriber again.
2. **Fan-out before correlation.** `ForgeNotificationsSubscriber` calls `sink.notify()` inside `_handle_message` after envelope decode + `source_id=='forge'` gate + typed payload validation, but before and independent of the correlation-map lookup. Record the rationale: the phone is a per-operator, not per-session, surface, so LRU correlation loss on a jarvis restart must not silence the overnight surface. Record the accepted consequence: builds not queued through jarvis now also notify the phone (deliberate noise), with a config toggle noted as the rollback lever — this needs explicit operator sign-off in the DDR.
3. **Slack-surface dedup placement.** Dedup lives inside `SlackNotifier` at enqueue time — first-wins 300s TTL map (ASSUM-006), keyed `(event_type, build_id, stage_label or '')` for stream events and `('build_queued', correlation_id)` for the intake event, monotonic clock, evict-on-insert — not in the subscriber and not in forge. State is in-process only, consistent with the DDR-027 no-replay/in-memory posture.
4. **ASSUM-010 v1 acceptance.** Record the explicit split decision: for v1, pause-is-last-signal is accepted because the only live CANCELLED producer is the operator's own forge CLI cancel (off the checkpoint path), and wiring forge would break the v1 "jarvis-only, zero forge changes" property. The build-cancelled handler is nonetheless implemented and unit-validated from day one (TASK-JNB-005) so the phone path goes live the moment forge starts emitting; the gap is closed in v1.1 by TASK-JNB-102 wiring the existing `publish_build_cancelled` onto the reject/max-wait/CLI-cancel transitions.

Architecture context the DDR author needs: the Slack sender serializes `chat.postMessage` at ~1 msg/s from a bounded asyncio queue, uses Block Kit plain_text so rationale/failure_reason are inert, honours 429 Retry-After with a bounded retry budget, and treats every other failure as WARNING + drop (DDR-007 — the SQLite ledger is authoritative; the notifier can never raise into the JetStream callback or `queue_build`). It is constructed in `infrastructure/lifecycle.py` `build_app_state` only when `JARVIS_SLACK_BOT_TOKEN` + `JARVIS_SLACK_CHANNEL_ID` are set, otherwise a logged no-op sink; NATS-down keeps the existing DDR-021 soft-fail. `stage_complete`/`build_progress`/`build_resumed` are suppressed at the sink policy (ASSUM-002). The queued event never touches the stream — it is a publish-side hook in `tools/dispatch.py` `queue_build` (ASSUM-011).

## Acceptance Criteria

- [ ] A DDR exists under jarvis `docs/design` (following the repo's existing DDR naming/numbering convention) covering the in-process sink seam: no second PIPELINE consumer (err_code 10100 rationale named), deferral of the FEAT-JARVIS-006 `jarvis.notification.{adapter}` promotion, and the `NotificationSink` protocol described as the plug point for a future JARVIS-stream publisher.
- [ ] A DDR exists covering correlation-independent fan-out: restart resilience for the operator-global surface as the rationale, the accepted noise consequence (non-jarvis-queued builds now notify the phone) stated explicitly, and a config toggle named as the rollback lever.
- [ ] A DDR exists covering Slack-surface dedup placement: enqueue-time first-wins 300s TTL inside `SlackNotifier`, both key shapes documented, and the in-process-only (crash-loop can double-post) posture tied to DDR-027.
- [ ] A DDR exists covering the ASSUM-010 v1 acceptance: pause-is-last-signal accepted for v1, the day-one unit-validated build-cancelled handler (TASK-JNB-005) noted, and closure explicitly delegated to v1.1 TASK-JNB-102.
- [ ] Every DDR cross-references DDR-007, DDR-021, and DDR-027 where relevant, and cites the spec assumption ids it rests on (at minimum ASSUM-002, ASSUM-006, ASSUM-010, ASSUM-011).
- [ ] DDRs cross-reference each other and the implementing tasks (TASK-JNB-001/002/003/005/006) so a reader can trace decision → code.

## Test Requirements

This is a documentation task: no pytest suite is required and no pytest-bdd .feature glue may be added (operator decision 2026-07-03 — plain pytest only, and none is needed here). Verification is by review of the DDR files against the acceptance criteria above. If the jarvis repo has an existing docs lint/link-check step, the new files must pass it; run any project checks via `.venv/bin/python -m pytest` from the jarvis repo root only if a docs-validation test target already exists — do not create one.

## Implementation Notes

- **Dependency summary — TASK-JNB-003** (complete before this task): lifecycle wiring that constructs and binds `SlackNotifier` in `build_app_state`. The DDRs document behaviour that is now real code, so cite the actual module paths (`src/jarvis/infrastructure/slack_notifier.py`, `infrastructure/lifecycle.py`, `tools/dispatch.py`) rather than planned ones.
- **Key constraints to record accurately:**
  - Workqueue err-10100 single-consumer rule: the PIPELINE stream tolerates exactly one bound consumer; the Slack surface must remain an in-process sink invoked inside that consumer, and the later pause/cancelled subjects (TASK-JNB-005) arrive as a filter change on the same consumer, never a new one.
  - DDR-007 never-regress: notifier failures are WARNING + drop; the sink can never raise into the JetStream callback or `queue_build`, and the SQLite ledger stays authoritative.
  - DDR-027 no-replay: dedup and any pending state are in-memory only; a crash-loop inside a 300s window can double-post low-impact noise, and that is the accepted posture.
  - Correlation-INDEPENDENT fan-out is deliberate, not an oversight — the DDR must present it as a chosen semantic change with the noise consequence and rollback toggle, requiring operator sign-off.
- **Worktree scope:** the autobuild worktree for this task is jarvis-scoped and cannot read the sibling forge repo. Everything needed to write these DDRs is contained in this file — do not attempt to consult forge sources; refer to forge artefacts (`publish_build_cancelled`, TASK-JNB-102) by name only, as done above.
- Follow whatever DDR template/numbering already exists under jarvis `docs/design`; one file per decision is preferred, but a single multi-decision record is acceptable if that matches repo convention.

> **[WS3-S8 tracker sweep 2026-07-11]** status reconciled to `completed` - FEAT-28FF rollup (feature yaml status=completed, task per-task completed; 133f2e4).
