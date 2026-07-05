---
id: TASK-JNB-005
title: 'Pause + cancelled lifecycle: filter extension and rendering'
status: in_review
created: 2026-07-03 15:30:00+00:00
updated: 2026-07-03 15:30:00+00:00
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 4
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-JNB-003
tags:
- ubs-003
- jarvis-notification-bridge
- slack
- v1
autobuild_state:
  current_turn: 2
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-28FF
  base_branch: main
  started_at: '2026-07-03T17:53:17.496635'
  last_updated: '2026-07-03T18:19:11.713233'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Deterministic honesty record (claim_audit_unmodified, severity=should_fix):\
      \ Player claim: Player claimed file docs/design/FEAT-28FF/decisions/DDR-032-notification-sink-in-process.md.\
      \ Actual: Path is tracked in git but 'git status --porcelain' shows no change\
      \ for it \u2014 the Player claimed work on a file it did not actually modify\
      \ this turn. Most likely cause: the report writer swept an orchestrator-managed\
      \ path (e.g. a file under .guardkit/autobuild/ or tasks/<state>/) into files_modified.\
      \ Defence-in-depth for the agent_invoker-side filter; this is a warning, not\
      \ a turn-rejecting fabrication..\n- Deterministic honesty record (claim_audit_unmodified,\
      \ severity=should_fix): Player claim: Player claimed file docs/design/FEAT-28FF/decisions/DDR-033-correlation-independent-fan-out.md.\
      \ Actual: Path is tracked in git but 'git status --porcelain' shows no change\
      \ for it \u2014 the Player claimed work on a file it did not actually modify\
      \ this turn. Most likely cause: the report writer swept an orchestrator-managed\
      \ path (e.g. a file under .guardkit/autobuild/ or tasks/<state>/) into files_modified.\
      \ Defence-in-depth for the agent_invoker-side filter; this is a warning, not\
      \ a turn-rejecting fabrication..\n- Deterministic honesty record (claim_audit_unmodified,\
      \ severity=should_fix): Player claim: Player claimed file docs/design/FEAT-28FF/decisions/DDR-034-slack-dedup-placement.md.\
      \ Actual: Path is tracked in git but 'git status --porcelain' shows no change\
      \ for it \u2014 the Player claimed work on a file it did not actually modify\
      \ this turn. Most likely cause: the report writer swept an orchestrator-managed\
      \ path (e.g. a file under .guardkit/autobuild/ or tasks/<state>/) into files_modified.\
      \ Defence-in-depth for the agent_invoker-side filter; this is a warning, not\
      \ a turn-rejecting fabrication..\n... and 8 more issues"
    timestamp: '2026-07-03T17:53:17.496635'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-07-03T18:12:00.325267'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: Pause + cancelled lifecycle: filter extension and rendering

## Description

Extend `_get_lifecycle_subjects()` to six subjects (adding `pipeline.build-paused.>` and `pipeline.build-cancelled.>`, both verified unbound 2026-07-03), add `_handle_message` projection branches for `BuildPausedPayload` and `BuildCancelledPayload` (each carries its own `correlation_id`) onto widened `ForgeNotification` fields — including `approval_subject` retained on the pause projection for v1.1 button routing — and implement rendering: pause shows stage + verbatim plain-text rationale + coach score or `'score unavailable'` (today's live default per ADR-ARCH-033) + an approve/reject-via-CLI hint; cancelled shows `cancelled_by`/`reason`. Rationales chunk under Slack's ~3000-char Block Kit `plain_text` per-block limit so they arrive intact. The cancelled path has no live producer yet (ASSUM-010: for v1 the only live CANCELLED producer is the operator's own forge CLI cancel), so it is unit-validated against a synthetic envelope — the phone path becomes live the moment forge starts emitting (v1.1, TASK-JNB-102).

Architecture context: the Slack surface is an in-process sink (`src/jarvis/infrastructure/slack_notifier.py`, constructed in `infrastructure/lifecycle.py` `build_app_state` by TASK-JNB-003) invoked inside the one existing ephemeral PIPELINE consumer's `_handle_message` on `ForgeNotificationsSubscriber`, after envelope decode + `source_id == 'forge'` gate + typed payload validation, but before and independent of the correlation-map lookup — the phone is per-operator, not per-session, so LRU loss on restart must not silence it. This task changes the `filter_subjects` of that single consumer from 4 to 6 — a filter change on the one consumer, never a new consumer (workqueue retention makes a second overlapping PIPELINE consumer fail with err_code 10100). `ForgeNotification` is widened per its frozen-model rule: `event_type` Literal gains `build_paused`/`build_cancelled`, and the new fields (`coach_score`, `rationale`, `gate_mode`, `approval_subject`, `cancelled_by`, `reason`, and the wave-1 additions such as `build_id`) are all optional with `None` defaults so existing CLI rendering is unaffected. `approval_subject` arrives free on `BuildPausedPayload` and is retained on the pause projection so v1.1 button routing (TASK-JNB-103) needs no re-plumbing. Rendering uses Block Kit `plain_text` objects with mrkdwn disabled so rationale content is inert; `coach_score` `None` renders `'score unavailable'`; out-of-range floats render as inert text, never rejected — the notifier can never raise into the JetStream callback (DDR-007).

## Acceptance Criteria

- [ ] `_get_lifecycle_subjects()` returns exactly six subjects: the existing four plus `pipeline.build-paused.>` and `pipeline.build-cancelled.>`
- [ ] `_handle_message` gains projection branches for `BuildPausedPayload` and `BuildCancelledPayload`, each projecting the payload's own `correlation_id` onto the `ForgeNotification`
- [ ] `ForgeNotification` `event_type` Literal accepts `build_paused` and `build_cancelled`; all newly added fields (`coach_score`, `rationale`, `gate_mode`, `approval_subject`, `cancelled_by`, `reason`) are optional with `None` defaults
- [ ] The pause projection retains `approval_subject` verbatim from `BuildPausedPayload` (required for v1.1 button routing without re-plumbing)
- [ ] Pause rendering shows: stage, verbatim plain-text rationale, coach score (or `'score unavailable'` when `coach_score` is `None` — the live ADR-ARCH-033 default), and an approve/reject-via-CLI hint line
- [ ] Cancelled rendering shows `cancelled_by` and `reason`
- [ ] A multi-paragraph rationale survives intact: chunked into multiple Block Kit `plain_text` blocks each under the ~3000-char limit, no truncation, order preserved
- [ ] Formatting characters in rationale (mrkdwn/Block Kit special characters, e.g. `*`, `_`, `<`, `>`, `&`) render inert as plain text
- [ ] Coach score boundary values 0.0 and 1.0 render correctly; out-of-range values (e.g. -0.5, 1.7) render defensively as inert text and are never rejected — the notify path never raises
- [ ] The cancelled projection and rendering path is unit-validated against a synthetic `build-cancelled` envelope (ASSUM-010: no live producer yet)
- [ ] Existing CLI rendering and schema-import-isolation tests (FEAT-JARVIS-005 cross-adapter contract) are updated for the widened model — new optional fields and render branches — with no regressions
- [ ] jarvis supervisor startup binds exactly one PIPELINE consumer; boot logs show no err_code 10100
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

Plain pytest ONLY — no pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror the spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

Required coverage:

- Subject-filter test: `_get_lifecycle_subjects()` returns the six expected subjects, including `pipeline.build-paused.>` and `pipeline.build-cancelled.>`, and the consumer is (re)created with the extended `filter_subjects` on the same single ephemeral consumer — no second consumer is created.
- Pause projection test: a valid `BuildPausedPayload` envelope produces a `ForgeNotification` with `event_type == 'build_paused'`, the payload's own `correlation_id`, and `approval_subject` retained verbatim.
- Cancelled projection test: a synthetic `BuildCancelledPayload` envelope (construct it in-test; no live producer exists per ASSUM-010) produces a `ForgeNotification` with `event_type == 'build_cancelled'`, the payload's own `correlation_id`, `cancelled_by`, and `reason`.
- Pause rendering tests: stage present; rationale verbatim; `coach_score=None` renders `'score unavailable'`; CLI-hint line present; scores 0.0 and 1.0 render; out-of-range scores render as inert text without raising.
- Chunking test: a multi-paragraph rationale longer than 3000 chars is split into multiple `plain_text` blocks, each under the limit, concatenating back to the original text.
- Inertness test: rationale containing mrkdwn/Block Kit formatting characters is emitted as `plain_text` blocks (mrkdwn disabled), asserting the characters appear unmodified in the block text.
- Never-raise test: rendering/notify with a malformed or out-of-range payload field logs WARNING and returns without raising (DDR-007).
- Regression: existing CLI rendering and schema-import-isolation tests updated for the widened `ForgeNotification` still pass.

## Implementation Notes

- Dependency — TASK-JNB-003 (complete before this task): lifecycle wiring; `SlackNotifier` is constructed and bound in `infrastructure/lifecycle.py` `build_app_state`. This task extends the already-bound subscriber and the already-constructed notifier; it does not touch construction or binding.
- Single-consumer rule (err_code 10100): the PIPELINE stream uses workqueue retention — a second overlapping consumer fails to bind with err_code 10100. This task must only extend `filter_subjects` on the one existing ephemeral consumer from 4 to 6 subjects. Never create a new consumer. Both new subjects were verified unbound as of 2026-07-03.
- DDR-007 (never regress the pipeline): the notifier and every projection/render branch added here must never raise into the JetStream callback. Any failure is WARNING + drop; the SQLite ledger remains authoritative.
- DDR-027 (no replay): dedup and notification state are in-process only; this task does not add persistence or replay. Hardening (300s first-wins dedup, throttling) lands separately in TASK-JNB-006.
- Correlation-INDEPENDENT fan-out is deliberate: `sink.notify()` is called after envelope decode + `source_id == 'forge'` gate + typed payload validation but before and independent of the correlation-map lookup. Do not gate the pause/cancelled projections on a correlation-map hit — a jarvis restart (LRU loss) must not blind the phone surface.
- Frozen-model rule for `ForgeNotification`: widen via new optional fields with `None` defaults and Literal extension only. The FEAT-JARVIS-005 cross-adapter contract tests (CLI rendering, schema-import isolation) will red-loop autobuild if not updated in step with the widening.
- `coach_score` rendering: `None` is the live default today (ADR-ARCH-033), so `'score unavailable'` is the common path — do not treat it as an error. Out-of-range floats are rendered as text, never validated away.
- The pause message's CLI-hint line is the v1 mitigation for ASSUM-010's pause-is-last-signal consequence (documented in the TASK-JNB-007 DDR); v1.1 replaces it with Block Kit buttons (TASK-JNB-103), which is why `approval_subject` must be retained on the pause projection now.
- Worktree scope: the autobuild worktree for this task is jarvis-scoped and cannot read the sibling forge repo. Everything needed (payload field names, subject names, limits, constraints) is in this file; construct synthetic envelopes in-test rather than importing forge fixtures.
