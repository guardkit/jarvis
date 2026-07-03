---
id: TASK-JNB-003
title: "Lifecycle wiring: construct and bind SlackNotifier in build_app_state"
status: backlog
created: 2026-07-03T15:30:00Z
updated: 2026-07-03T15:30:00Z
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-28FF
version: v1
wave: 2
repo: jarvis
implementation_mode: direct
complexity: 3
dependencies: [TASK-JNB-001, TASK-JNB-002]
tags: [ubs-003, jarvis-notification-bridge, slack, v1]
consumer_context:
  - task: TASK-JNB-001
    consumes: NOTIFICATION_SINK
    framework: "Python async protocol (in-process jarvis)"
    driver: "asyncio"
    format_note: "async notify(ForgeNotification) must NEVER raise into the caller; failures are WARNING + continue (DDR-007)"
---

# Task: Lifecycle wiring: construct and bind SlackNotifier in build_app_state

## Description

In `src/jarvis/infrastructure/lifecycle.py` construct the SlackNotifier from settings, bind it to the subscriber and the dispatch-module snapshot, and order start/stop (notifier stops after subscriber with best-effort drain). Degraded-start matrix: NATS down keeps the existing DDR-021 soft-fail with the notifier idle; Slack config missing yields the logged no-op sink; neither crashes the supervisor.

Architecture context: the Slack sender lives in `src/jarvis/infrastructure/slack_notifier.py` inside the jarvis supervisor process (not a separate adapter process), implementing a NotificationSink protocol whose `notify(ForgeNotification)` enqueues onto a bounded asyncio.Queue drained by one worker task serialising `chat.postMessage` at roughly 1 msg/s. The notifier can never raise into the JetStream callback or `queue_build` — every failure beyond the bounded 429 retry budget is WARNING + drop, because the SQLite ledger is authoritative (DDR-007). This task is the point where the two Wave 1 artefacts meet: the SlackNotifier component and Slack pydantic-settings fields from TASK-JNB-001, and the `bind_notification_sink()` seam on ForgeNotificationsSubscriber plus the module-level `_notification_sink` snapshot in `tools/dispatch.py` from TASK-JNB-002. `build_app_state` constructs the notifier only when `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID` are both set; otherwise it installs a logged no-op sink so every downstream call site is unconditionally safe. The dispatch snapshot mirrors the existing `_forge_subscriber`/`_nats_client` pattern so the queued hook in `queue_build` fires through the same sink instance the subscriber holds.

Shutdown ordering matters: the subscriber stops first so no new events arrive, then the notifier stops with a best-effort drain of its queue — in-flight Slack messages get a bounded chance to post, but shutdown never blocks indefinitely on Slack. Start ordering is the mirror: notifier ready before the subscriber binds it, so no early event finds an unbound sink.

## Acceptance Criteria

- [ ] `build_app_state` constructs a real SlackNotifier when both `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID` are set, and a logged no-op sink otherwise; construction never raises for any settings permutation.
- [ ] The constructed sink is bound to ForgeNotificationsSubscriber via `bind_notification_sink()` and installed as the `tools/dispatch.py` module-level `_notification_sink` snapshot, so subscriber events and the `queue_build` queued hook flow through the same instance.
- [ ] Start ordering: the notifier is started before the subscriber binds/starts; stop ordering: the notifier stops after the subscriber, with a best-effort bounded drain of queued messages.
- [ ] NATS down at startup preserves the existing DDR-021 soft-fail behaviour with the notifier idle; the supervisor does not crash.
- [ ] Slack config missing (either or both env vars unset) yields the logged no-op sink; the supervisor boots cleanly and all notify paths remain no-ops.
- [ ] Supervisor boots cleanly in all degraded permutations: NATS up/down crossed with Slack config present/absent (four permutations, none crash).
- [ ] Wiring tests mirror the existing `forge_subscriber` lifecycle tests in structure and placement.
- [ ] A synthetic queued + started + complete sequence through the fully wired path produces exactly three `chat.postMessage` calls on a mocked Slack client.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

Plain pytest ONLY — no pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

- Lifecycle wiring tests live alongside and mirror the existing `forge_subscriber` lifecycle tests: same fixture style, same patch points, extended for the notifier.
- A degraded-start matrix test class covering all four permutations (NATS up/down x Slack config present/absent), asserting no exception escapes `build_app_state`/startup and that the correct sink flavour (real vs logged no-op) is installed in each case.
- A stop-ordering test asserting the subscriber is stopped before the notifier and that the notifier's drain is bounded (does not hang when the queue holds undelivered messages).
- An end-to-end wired-path test: with a mocked Slack client, drive a synthetic queued event (via the `queue_build` hook path) plus started and complete envelopes (via the subscriber path) and assert exactly three `chat.postMessage` invocations with the expected channel.
- A no-op-sink test: with Slack config absent, the same synthetic sequence produces zero Slack client calls and one log line noting no-op mode.

## Seam Tests

Consumes NOTIFICATION_SINK from TASK-JNB-001. Contract: `async notify(ForgeNotification)` must never raise into the caller; failures are WARNING + continue (DDR-007).

```python
import logging

import pytest
from slack_sdk.errors import SlackApiError


@pytest.mark.seam
@pytest.mark.integration_contract("NOTIFICATION_SINK")
class TestNotificationSinkSeam:
    async def test_notify_never_raises_when_slack_client_fails(
        self, caplog, make_notifier, make_forge_notification
    ):
        """A sink whose Slack client raises must swallow the failure:
        WARNING logged, no exception propagates to the caller (DDR-007)."""
        client = ...  # mock whose chat_postMessage raises SlackApiError
        client.chat_postMessage.side_effect = SlackApiError(
            message="boom", response={"ok": False, "error": "fatal_error"}
        )
        notifier = make_notifier(client=client)
        notification = make_forge_notification(event_type="build_started")

        with caplog.at_level(logging.WARNING):
            # Behavioural 'never raises': awaiting notify() (and letting the
            # worker drain) must complete without any exception escaping.
            await notifier.notify(notification)
            await notifier.drain_for_test()

        assert any(r.levelno == logging.WARNING for r in caplog.records)
        # And the caller-facing contract held: no exception propagated —
        # reaching this assertion proves it.
```

## Implementation Notes

- Dependencies: TASK-JNB-001 delivers the SlackNotifier component, the Slack pydantic-settings fields (`JARVIS_` prefix: `slack_bot_token`, `slack_app_token`, `slack_channel_id`, `slack_operator_user_id`, `slack_decided_by`), and the `slack-sdk` dependency. TASK-JNB-002 delivers the notification-sink seam (`bind_notification_sink()`) in ForgeNotificationsSubscriber and the queued hook in `queue_build` with its module-level `_notification_sink` snapshot. This task only wires; it adds no new rendering, events, or consumers.
- Single-consumer rule: do NOT create any new NATS/JetStream consumer here — the workqueue PIPELINE stream permits exactly one consumer (err_code 10100 on a second bind). The Slack surface is an in-process sink invoked inside the one existing ephemeral consumer; the queued event never touches the stream (publish-side hook in `queue_build`).
- DDR-007 never-regress: the notifier must never raise into the JetStream callback or `queue_build`; the wiring must preserve this — the no-op sink and the real sink are both unconditionally safe to call.
- DDR-027 no-replay: dedup/pending state is in-process only; nothing in lifecycle wiring should attempt persistence or replay of notifications across restarts.
- Correlation-INDEPENDENT fan-out is deliberate: the sink is invoked before and independent of the correlation-map lookup, so a jarvis restart (LRU loss) cannot silence the phone. Do not "fix" this by gating notify on correlation hits.
- Degraded starts: NATS down keeps the existing DDR-021 soft-fail (supervisor up, subscriber retrying/idle, notifier idle); Slack config missing installs the logged no-op sink. No permutation may crash the supervisor.
- Worktree scope: the autobuild worktree is jarvis-scoped and CANNOT read the sibling forge repo — everything needed for this task is in this file plus the jarvis codebase (`src/jarvis/infrastructure/lifecycle.py`, `src/jarvis/infrastructure/slack_notifier.py`, `tools/dispatch.py`).
