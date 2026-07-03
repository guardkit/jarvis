---
autobuild_state:
  base_branch: main
  current_turn: 2
  last_updated: '2026-07-03T16:02:49.049723'
  max_turns: 5
  started_at: '2026-07-03T15:48:38.629072'
  turns:
  - coach_success: true
    decision: feedback
    feedback: '- 131 tests failed. Specific error from test-orchestrator: ''AssertionError:
      Expected notify to have been awaited once. Awaited 0 times.'' This indicates
      the async notify() method is not being called or awaited correctly in the implementation.:
      Debug the notify() method implementation in src/jarvis/infrastructure/slack_notifier.py.
      Verify: (1) notify() is properly declared as async, (2) it''s being awaited
      in tests, (3) the method signature matches the NotificationSink protocol, (4)
      the queue enqueue logic is actually executing. Run tests locally with pytest
      -v to see all failure details.

      - Evidence gathering aborted with status ''partial_gate_abort''. Multiple verification
      fields are null (bdd, arch_review, independent_tests, wiring, mocked_seam, spec_gap,
      requirements, runtime_parity), indicating evidence collection stopped before
      completion due to test failures.: Fix the test failures first. Once tests pass,
      the Coach can gather complete evidence for all criteria. The aborted gathering
      means most acceptance criteria cannot be independently verified.

      - All quality gates failed: tests_passed=false, coverage_met=false, all_gates_passed=false.
      The test-orchestrator phase (Phase 4) produced a substrate failure, meaning
      the orchestrator''s own test run detected deterministic failures.: Review tests/test_slack_notifier.py
      for async/await correctness. Ensure all async methods are awaited in tests.
      Verify mock setup for AsyncWebClient is correct. The error suggests notify()
      may not be async or is not being called at all.'
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-07-03T15:48:38.629072'
    turn: 1
  - coach_success: true
    decision: feedback
    feedback: '- Deterministic honesty record (claim_audit_unmodified, severity=should_fix):
      Player claim: Player claimed file pyproject.toml. Actual: Path is tracked in
      git but ''git status --porcelain'' shows no change for it — the Player claimed
      work on a file it did not actually modify this turn. Most likely cause: the
      report writer swept an orchestrator-managed path (e.g. a file under .guardkit/autobuild/
      or tasks/<state>/) into files_modified. Defence-in-depth for the agent_invoker-side
      filter; this is a warning, not a turn-rejecting fabrication..

      - Deterministic honesty record (claim_audit_unmodified, severity=should_fix):
      Player claim: Player claimed file src/jarvis/config/settings.py. Actual: Path
      is tracked in git but ''git status --porcelain'' shows no change for it — the
      Player claimed work on a file it did not actually modify this turn. Most likely
      cause: the report writer swept an orchestrator-managed path (e.g. a file under
      .guardkit/autobuild/ or tasks/<state>/) into files_modified. Defence-in-depth
      for the agent_invoker-side filter; this is a warning, not a turn-rejecting fabrication..

      - Deterministic honesty record (claim_audit_unmodified, severity=should_fix):
      Player claim: Player claimed file src/jarvis/infrastructure/forge_notifications.py.
      Actual: Path is tracked in git but ''git status --porcelain'' shows no change
      for it — the Player claimed work on a file it did not actually modify this turn.
      Most likely cause: the report writer swept an orchestrator-managed path (e.g.
      a file under .guardkit/autobuild/ or tasks/<state>/) into files_modified. Defence-in-depth
      for the agent_invoker-side filter; this is a warning, not a turn-rejecting fabrication..

      ... and 10 more issues'
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-07-03T15:57:04.035571'
    turn: 2
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-28FF
complexity: 5
created: 2026-07-03 15:30:00+00:00
dependencies: []
feature_id: FEAT-28FF
id: TASK-JNB-001
implementation_mode: task-work
parent_review: TASK-REV-C951
priority: high
repo: jarvis
status: design_approved
tags:
- ubs-003
- jarvis-notification-bridge
- slack
- v1
task_type: feature
title: SlackNotifier component + Slack settings + slack-sdk dependency
updated: 2026-07-03 15:30:00+00:00
version: v1
wave: 1
---

# Task: SlackNotifier component + Slack settings + slack-sdk dependency

## Description

Add `slack_bot_token` (`SecretStr | None`) and `slack_channel_id` pydantic-settings fields under the existing `JARVIS_` prefix (matching the keys already validated in `jarvis/.env`), plus the `slack-sdk` dependency in the jarvis `pyproject.toml`. Then implement `src/jarvis/infrastructure/slack_notifier.py`: a `NotificationSink` protocol; a factory that returns a logged no-op sink when the Slack config is absent; a bounded `asyncio.Queue` drained by a single worker task posting plain-text `chat.postMessage` (mrkdwn disabled); `start()`/`stop()` with bounded shutdown; and `notify()` that never raises and logs WARNING on any delivery failure (DDR-007). This task renders the checkpoint slice only: queued, build-started, build-complete (`pr_url` + `summary` when present), and build-failed (`reason`).

Architecturally, the Slack sender lives as a new module inside the jarvis supervisor process — not a separate adapter process. `NotificationSink.notify(ForgeNotification)` enqueues onto the bounded queue; one worker serialises delivery via `chat.postMessage` at roughly 1 msg/s. Messages are plain text (mrkdwn disabled / Block Kit `plain_text` objects) so payload strings arrive inert. Every delivery failure is WARNING + drop: the SQLite ledger is authoritative, and the notifier can never raise into the JetStream callback or `queue_build` (DDR-007). The sink protocol defined here is the seam consumed downstream — TASK-JNB-002 binds it into `ForgeNotificationsSubscriber` and hooks `queue_build` in `tools/dispatch.py`, and TASK-JNB-003 constructs it in `infrastructure/lifecycle.py` `build_app_state` only when `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID` are set (otherwise the no-op sink). It is also the seam a future JARVIS-stream publisher (deferred FEAT-JARVIS-006 promotion) plugs into without touching the subscriber again. Keep the protocol surface stable and minimal.

## Acceptance Criteria

- [ ] `slack_bot_token` (`SecretStr | None`, default `None`) and `slack_channel_id` fields exist on the jarvis pydantic-settings model under the existing `JARVIS_` prefix, matching the `.env` keys `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID`
- [ ] `slack-sdk` is declared as a dependency in the jarvis `pyproject.toml` and imports resolve in the test venv
- [ ] `src/jarvis/infrastructure/slack_notifier.py` defines a `NotificationSink` protocol with `async notify(ForgeNotification)` (plus `start()`/`stop()` lifecycle)
- [ ] Factory returns a logged no-op sink when `slack_bot_token` or `slack_channel_id` is unset; no Slack client is constructed and no network calls occur in no-op mode
- [ ] Delivery uses a bounded `asyncio.Queue` drained by a single worker task posting plain-text `chat.postMessage` with mrkdwn disabled
- [ ] `start()` launches the worker; `stop()` performs a bounded shutdown (does not hang on a full or stuck queue)
- [ ] `notify()` never raises to the caller under any failure (client error, full queue, stopped sink); every delivery failure logs at WARNING and processing continues (DDR-007)
- [ ] Render shapes implemented for exactly the checkpoint slice: queued; build-started; build-complete including `pr_url` and `summary` when present; build-failed including `reason`
- [ ] Mocked `AsyncWebClient` tests prove: never-raise behaviour, no-op mode, WARNING-on-failure, all four render shapes, and that a raised `SlackApiError` does not stop the worker (subsequent messages still deliver)
- [ ] The `SecretStr` token value never appears in `repr()`, `str()`, or any log output (asserted in tests)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

Plain pytest only — NO pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror the spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

- Patch/mock `slack_sdk.web.async_client.AsyncWebClient`; no real network in any test.
- Class-based organisation, one class per behaviour cluster, e.g. `TestNoOpSinkWhenConfigAbsent`, `TestNotifyNeverRaises`, `TestDeliveryFailureLogsWarning`, `TestCheckpointRenderShapes`, `TestWorkerSurvivesSlackApiError`, `TestSecretTokenNeverLogged`.
- Never-raise must be asserted behaviourally: await `notify()` with the mocked client raising `SlackApiError` and assert no exception propagates and a WARNING record is emitted (use `caplog`).
- Render-shape tests assert the outgoing `chat.postMessage` text for each of the four checkpoint events, including presence of `pr_url`/`summary` on build-complete and `reason` on build-failed, and their graceful absence when fields are `None`.
- SecretStr test asserts the raw token string is absent from settings `repr()` and from all captured log output.
- Worker-survival test: first message raises `SlackApiError`, second message delivers; assert both a WARNING for the first and a successful post for the second.

## Implementation Notes

- No dependencies: this is a wave-1 task with an empty `dependencies` list; do not touch `ForgeNotificationsSubscriber`, `tools/dispatch.py`, or `infrastructure/lifecycle.py` — those seams are TASK-JNB-002/003. This task is purely the component, settings fields, and dependency declaration.
- Contract you are producing (NOTIFICATION_SINK, consumed by TASK-JNB-002 and TASK-JNB-003): `async notify(ForgeNotification)` must NEVER raise into the caller; failures are WARNING + continue (DDR-007). Downstream tasks carry seam tests against exactly this behaviour — keep it strict.
- Single-consumer rule (workqueue err-10100): this task adds NO NATS consumer of any kind. The Slack surface is an in-process sink; all stream traffic continues to flow through the one existing ephemeral PIPELINE consumer. Do not create, bind, or subscribe to anything.
- DDR-027 (no replay): all sink state is in-process and in-memory; no persistence, no replay of missed notifications on restart. The SQLite ledger remains authoritative.
- Correlation-INDEPENDENT fan-out is deliberate: the phone is a per-operator surface, not per-session, so the sink must not depend on correlation-map lookups. Design `notify()` to take only the `ForgeNotification` — the binding site (TASK-JNB-002) calls it before and independent of correlation lookup.
- Scope boundaries: 300s first-wins dedup, 429 Retry-After backoff, and overflow-drop bounds land later in TASK-JNB-006; pause/cancelled rendering and rationale chunking land in TASK-JNB-005. Do not implement them here, but keep the enqueue path and worker loop shaped so they can be added without restructuring (e.g. a single enqueue chokepoint, a single send call site in the worker).
- Rendering: plain text only, mrkdwn disabled so payload strings (e.g. failure reasons) are inert. Optional fields render gracefully when `None`.
- Autobuild worktree is jarvis-scoped: it cannot read the sibling forge repo. Everything needed to implement this task is contained in this file; do not plan on inspecting forge sources.