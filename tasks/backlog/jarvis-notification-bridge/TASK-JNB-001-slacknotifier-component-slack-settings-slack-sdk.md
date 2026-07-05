---
id: TASK-JNB-001
title: SlackNotifier component + Slack settings + slack-sdk dependency
status: in_review
created: 2026-07-03 15:30:00+00:00
updated: 2026-07-03 15:30:00+00:00
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 1
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: []
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
  started_at: '2026-07-03T17:02:52.042781'
  last_updated: '2026-07-03T17:19:36.013135'
  turns:
  - turn: 1
    decision: feedback
    feedback: '- 4 tests failed in independent verification. Specific failure: assert
      notification.pr_url == ''https://github.com/org/repo/pull/42'' failed with AssertionError
      (pr_url was None). This indicates the ForgeNotification model or render logic
      is not correctly handling the pr_url field.: Investigate whether pr_url is defined
      on ForgeNotification model, whether _render() correctly extracts it for build-complete
      events, and whether test fixtures correctly populate it. Run full test suite
      locally to identify all 4 failures and fix underlying issues.

      - Evidence bundle shows tests_passed: false, tests_failed: 4, contradicting
      Player''s report of 16 passing tests. The orchestrator''s independent test-orchestrator
      specialist found failures.: Run pytest with verbose output to see all failures.
      Fix each failing test before resubmitting. Ensure test fixtures correctly populate
      all required fields on ForgeNotification objects.

      - Coverage requirement not met. coverage_met: false while coverage_required:
      true. Coverage data is null due to gathering abort after test failures.: After
      fixing test failures, run coverage analysis (likely pytest-cov or coverage.py).
      Ensure line coverage meets project threshold. Add tests for uncovered branches,
      especially error handling paths required by AC-007 never-raise contract.

      ... and 1 more issues'
    timestamp: '2026-07-03T17:02:52.042781'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-07-03T17:11:28.407057'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
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
