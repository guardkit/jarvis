---
id: TASK-JNB-009
title: "LIVE v1 hardening validation: pause on phone, burst, restart"
status: completed
created: 2026-07-03T15:30:00Z
updated: 2026-07-11T21:30:00Z
completed: 2026-07-11T21:30:00Z
priority: high
task_type: operator_handoff
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 6
repo: jarvis
implementation_mode: direct
complexity: 3
dependencies: [TASK-JNB-008]
tags: [ubs-003, jarvis-notification-bridge, slack, v1]
---

# Task: LIVE v1 hardening validation: pause on phone, burst, restart

> **📌 DISPOSITION 2026-07-09 (WS3-S7) — FOLDED into the Session A / TASK-SPL-J04
> operator bundle (disposition (a), the recorded single disposition).** JNB-107
> live-validated the *reply loop* only; this task's burst/restart/pause hardening
> was never live-validated — the un-dispositioned middle state WS3-S7 §3 names as
> itself the defect. Rather than a standalone operator session, the three probes
> below are carried as concrete runbook steps in the WS5 canon bundle that runs
> **tomorrow, 2026-07-10**:
> `ai-transition/docs/handoff-2026-07-07-post-gate-g1-remaining-work.md` §2
> (dated 2026-07-09 note under "Bundle TASK-SPL-J04"). The operator is already at
> the phone with a live forge+jarvis for MP-010/J04, so it is the cheapest live
> venue. This file stays `backlog` (operator_handoff, unrun) until Session A
> executes the probes; on all-green it "marks v1 complete" per the ACs below and
> is closed via `/task-complete`. **No supersession** — the validation is still
> owed; it is now scheduled, not orphaned.

## Description

Operator: run a gated toy build that pauses — the phone shows stage, verbatim rationale, and 'score unavailable' (the live ADR-ARCH-033 default); queue two toy builds finishing close together — both terminals arrive with correct per-build fields and no wedge; restart jarvis mid-build — no replayed notifications, and post-restart events still reach the phone (fan-out is not correlation-gated). This task marks v1 complete.

This is the live confirmation of the full hardened v1 surface. By this wave, the SlackNotifier (`src/jarvis/infrastructure/slack_notifier.py`) is constructed in `infrastructure/lifecycle.py` `build_app_state` when `JARVIS_SLACK_BOT_TOKEN` + `JARVIS_SLACK_CHANNEL_ID` are set; `ForgeNotificationsSubscriber` invokes `sink.notify()` inside `_handle_message` after envelope decode, the `source_id=='forge'` gate and typed payload validation, but before and independent of the correlation-map lookup — so a jarvis restart that loses the LRU correlation map must not silence the phone. The single ephemeral PIPELINE consumer's `filter_subjects` has been extended from 4 to 6 (adding `pipeline.build-paused.>` and `pipeline.build-cancelled.>` — a filter change on the one consumer, never a new consumer), and the queued event arrives via the publish-side hook in `tools/dispatch.py` `queue_build`, never from the stream.

Hardening from TASK-JNB-006 is now live and is what the burst and restart probes exercise: first-wins 300s TTL dedup keyed `(event_type, build_id, stage_label or '')` for stream events and `('build_queued', correlation_id)` for the intake event; a bounded asyncio.Queue drained by one worker task serialising `chat.postMessage` at ~1 msg/s with 429 Retry-After honoured under a bounded per-message retry budget; overflow drops oldest with one WARNING. Pause rendering from TASK-JNB-005 delivers stage, verbatim rationale as inert plain_text Block Kit objects (rationales chunked under Slack's ~3000-char-per-block limit), and `coach_score` None rendered as 'score unavailable'. Dedup and pending state are in-process only (DDR-027 posture): a restart clears the dedup map, but no replay occurs because the ephemeral consumer holds no durable state and DDR-027 forbids replay.

## Acceptance Criteria

- [x] A gated toy build reaches its pause: the phone shows the pause message with the correct stage, the coach rationale rendered verbatim (inert text, intact even if long), and 'score unavailable' where `coach_score` is None (today's live ADR-ARCH-033 default).
- [x] Two toy builds queued to finish close together: both terminal notifications arrive on the phone, each carrying the correct per-build fields (no cross-build field bleed), and the notifier does not wedge — subsequent notifications continue to flow.
- [x] jarvis restarted mid-build: no previously delivered notifications are replayed after restart (DDR-027), and events emitted after the restart still reach the phone even though the correlation map was lost — confirming fan-out is not correlation-gated.
- [x] Each expected notification arrives exactly once (dedup active); any at-least-once redelivery during the run is absorbed by the 300s first-wins dedup rather than double-posting.
- [x] v1 is declared complete on the strength of the above.

## Live validation record — ALL GREEN (2026-07-11 evening, GB10)

Run per the fold-in spec (ai-transition `ways-of-working/mode-p-forge-specialist-execution-
integration-handoff.md` §8, with its two dated 2026-07-11 corrections): no phone in the loop —
every assertion evidenced from jarvis journal + forge-prod docker logs + the live forge db
(read-only) + Slack `conversations.history` on `C0BF2FPQXAM`. Orchestrated as workflow
`wf_4c27d46d-089` (Opus driver + independent Opus evidence-coach per probe; driver AND coach
pass on every probe; evidence dirs in the session scratchpad `jnb009/`).

- **Probe 1 — pause rendering (FEAT-3CC2, build-FEAT-3CC2-20260711201118):** pause message
  ts `1783802623.630599`: `Stage: autobuild` (matches request_id + stage_log), the 202-char
  ADR-ARCH-019 degraded rationale rendered verbatim as inert `plain_text` (byte-identical to
  the db `stage_log.details_json.gate.rationale`), `Coach score: score unavailable` with db
  `coach_score=NULL` (ADR-ARCH-033), exactly once. Terminal `build-cancelled` ts
  `1783802784.960349` (`Cancelled by: U03QR8WKT29`), exactly once, post-dating the pause.
  Bonus negative datum: a wrong-identity synthetic reject (`responder 'rich'`) was held by the
  gate (`unrecognised responder — anomaly, NOT resuming`) and produced NO Slack post — the
  identity pin holds silently.
- **Probe 2 — burst / no-wedge (FEAT-947C + FEAT-9E59):** strictly-serial worker (Max Ack
  Pending 1) paused 947C while 9E59 waited; rapid identity-pinned cancels drove all four
  messages — pause-947C, terminal-947C, pause-9E59, terminal-9E59 — exactly once, in order,
  correct per-build fields, no cross-build bleed, no wedge; spacing consistent with the
  ~1 msg/s serialised worker. Both builds db-confirmed CANCELLED, nothing launched.
- **Probe 3 — restart no-replay + correlation-independent fan-out (FEAT-B2D7):** pause
  delivered → the ONE deliberate restart (`systemctl --user stop/start`, PID 612110→2860676,
  clean boot, no `err_code 10100`, 6 `filter_subjects` re-established) → post-restart history
  ts-set identical (NO replay, DDR-027) → post-restart cancel's terminal DELIVERED despite the
  lost correlation map (fan-out not correlation-gated) → whole-session exactly-once table
  holds across P1+P2+P3. DDR-007 observed-not-forced: zero WARNING/drop events all session.

**v1 is declared complete.** Operational notes that fell out of the run (filed forge-side as
`TASK-FWD-005`): `forge cancel` is unusable against the identity-pinned gate (stale
`/var/forge/forge.db` shadow · `os.getlogin()` OSError under docker exec · hardcoded
`SYNTHETIC_RESPONDER='rich'` rejected by the pin while the CLI reports success); the working
cancel is an identity-pinned synthetic reject via forge's own injector. Also: a gate-paused
build ACKS its PIPELINE message, so `nats consumer info` reads idle while the single serial
worker is occupied — check forge logs/db, not the consumer, for worker freeness.

## Test Requirements

No new automated tests are written by this task — it is a live operator validation. Precondition: the TASK-JNB-008 v1 scenario test matrix (plain pytest, no BDD glue) must be fully green before starting, run from the jarvis repo root:

```
.venv/bin/python -m pytest
```

Do not proceed with the live probes if any TASK-JNB-008 test fails or hangs; a hung test must be investigated directly, not read as an absent signal.

## Implementation Notes

- Dependency: TASK-JNB-008 — v1 scenario test matrix (plain pytest, no BDD glue). This live validation is the runtime counterpart of that matrix; the three probes (pause rendering, burst, restart) map onto its scenario classes.
- Single-consumer rule: the whole v1 surface rides the one existing ephemeral PIPELINE consumer (workqueue err_code 10100 makes a second consumer structurally impossible); pause/cancelled arrived via a filter extension in TASK-JNB-005, and the queued event via the `queue_build` publish hook. If notifications stop entirely, check the supervisor boot logs for err_code 10100 before anything else.
- DDR-007 never-regress: the sink can never raise into the JetStream callback or `queue_build`; every Slack failure is WARNING + drop, the SQLite ledger stays authoritative. A missing phone message with a healthy build is a WARNING in the jarvis logs, not a build failure.
- DDR-027 no-replay: dedup and pending state are in-memory only; the restart probe validates that this posture holds — nothing is replayed, and nothing durable is expected to survive the restart.
- Correlation-INDEPENDENT fan-out is deliberate: `sink.notify()` runs before and independent of the correlation-map lookup, so the phone is per-operator, not per-session. The restart probe is the direct validation of this DDR (recorded in TASK-JNB-007) — post-restart events must arrive even for builds whose correlation entries were lost.
- Burst behaviour: the ~1 msg/s serialised worker means two near-simultaneous terminals arrive sequentially, roughly a second apart — that is correct behaviour, not a wedge. A wedge is when the second (and all later) messages never arrive.
- Environment: the four `JARVIS_SLACK_*` env vars, the bot's membership of the Slack channel, and a healthy ships-computer-nats broker were verified for TASK-JNB-004 but are perishable — re-confirm before running the probes.
- The autobuild worktree for jarvis tasks is jarvis-scoped and cannot read the sibling forge repo; everything needed for this validation is contained in this file. (Moot for execution here — this task is operator-run — but relevant to anyone cross-referencing forge behaviour.)

## Required operator follow-up

This task is task_type: operator_handoff — AutoBuild will not attempt it. The operator must verify the runtime acceptance criteria below manually, then mark the task complete via /task-complete.

- Run a gated toy build that pauses — phone shows stage, verbatim rationale, and 'score unavailable' (live ADR-ARCH-033 default).
- Queue two toy builds finishing close together — both terminals arrive with correct per-build fields and no wedge.
- Restart jarvis mid-build — no replayed notifications, and post-restart events still reach the phone (fan-out is not correlation-gated).
- Marks v1 complete.
