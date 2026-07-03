# DDR-032 — Notification sink is an in-process `NotificationSink` protocol implementation, not a second PIPELINE consumer

- **Status:** Accepted
- **Date:** 2026-07-03
- **Feature:** FEAT-28FF (UBS-003 / Slack Notification Bridge v1)
- **Related:** [DDR-007](../../FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md), [DDR-021](../../FEAT-JARVIS-004/decisions/DDR-021-amendment-capabilities-registry-tool-wiring.md), [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md), [DDR-033](DDR-033-correlation-independent-fan-out.md), [TASK-JNB-001](../../../../tasks/design_approved/TASK-JNB-001-slacknotifier-component-slack-settings-slack-sdk.md), [TASK-JNB-002](../../../../tasks/design_approved/TASK-JNB-002-notification-sink-seam-in-forgenotificationssubs.md), [TASK-JNB-003](../../../../tasks/backlog/TASK-JNB-003-lifecycle-wiring-construct-and-bind-slacknotifie.md)
- **Assumptions:** ASSUM-002 (suppressed event types), ASSUM-011 (build_queued is publish-side hook)

## Context

The v1 Slack notification bridge requires delivering Forge pipeline events to the operator's phone. Two architectural options exist:

1. **Second PIPELINE consumer** — create a dedicated JetStream consumer for Slack delivery, parallel to the existing CLI FIFO consumer
2. **In-process sink** — invoke a `NotificationSink` protocol implementation from inside the existing consumer's message handler

The PIPELINE stream uses workqueue retention (per [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md) and `nats-infrastructure/streams/stream-definitions.json`). Workqueue streams enforce a single-consumer-per-matching-subject rule: attempting to bind a second consumer with an overlapping filter raises NATS error code 10100 (`consumer must be deliver all on workqueue stream`).

The existing `ForgeNotificationsSubscriber` already binds an ephemeral push consumer on `pipeline.stage-complete.>` (extended to six lifecycle subjects in TASK-JNB-005: `build-started`, `build-complete`, `build-failed`, `build-paused`, `build-cancelled`, `stage-complete`). A second consumer with any overlapping subject would violate the workqueue invariant.

## Decision

**The Slack notification surface is an in-process sink invoked from inside the existing PIPELINE consumer's `_handle_message` callback, not a second JetStream consumer.**

1. **Protocol-based seam:** Define `NotificationSink` as a protocol with `async notify(ForgeNotification) -> None` (plus lifecycle `start()`/`stop()`) in `src/jarvis/infrastructure/slack_notifier.py` (TASK-JNB-001).

2. **Binding point:** `ForgeNotificationsSubscriber` gains `bind_notification_sink(sink: NotificationSink)` (TASK-JNB-002). The subscriber calls `sink.notify()` inside `_handle_message` after envelope decode, `source_id == 'forge'` gate, and typed payload validation, but before and independent of the correlation-map lookup (see [DDR-033](DDR-033-correlation-independent-fan-out.md) for fan-out rationale).

3. **Lifecycle wiring:** `infrastructure/lifecycle.py` `build_app_state` constructs a `SlackNotifier` (the concrete `NotificationSink` implementation) only when `JARVIS_SLACK_BOT_TOKEN` and `JARVIS_SLACK_CHANNEL_ID` are set; otherwise a logged no-op sink (TASK-JNB-003).

4. **Publish-side hook for `build_queued`:** The queued event never touches the NATS stream (ASSUM-011). Instead, `tools/dispatch.py` `queue_build` fires a `build_queued` notification via a module-level `_notification_sink` snapshot immediately after the PubAck/`register_correlation` block (TASK-JNB-002), mirroring the existing `_forge_subscriber`/`_nats_client` module-level pattern.

5. **No second consumer created:** The PIPELINE consumer count remains exactly 1. Subject filter changes (e.g., TASK-JNB-005 extending from 4 to 6 subjects) modify the existing consumer's `filter_subjects`, never create a new consumer.

## Rationale

- **Workqueue err_code 10100 constraint.** The canonical PIPELINE stream provisioned by `nats-infrastructure` is `retention=workqueue`. A second consumer with overlapping subjects is structurally impossible — NATS rejects the bind with error code 10100. The in-process sink avoids this constraint entirely.

- **Simplicity over distributed complexity.** A second consumer would require: duplicate envelope decode/validation logic, duplicate error handling, duplicate lifecycle shutdown sequencing, and coordination to ensure both consumers stay aligned on filter changes. The in-process sink reuses the existing subscriber's decode/validation/lifecycle paths with a single additional protocol call.

- **DDR-007 never-raise invariant extends cleanly.** The sink call is wrapped in try/except with WARNING-only failure semantics (TASK-JNB-002 AC, TASK-JNB-001 contract). A raised exception from `sink.notify()` is caught and logged; the JetStream callback completes normally, the SQLite ledger remains authoritative, and existing CLI FIFO delivery proceeds unaffected.

- **Future-proof plug point.** The `NotificationSink` protocol is the seam a future JARVIS-stream publisher (deferred FEAT-JARVIS-006 `jarvis.notification.{adapter}` promotion) slots into without touching `ForgeNotificationsSubscriber` again. The subscriber calls `.notify()`; whether the implementation posts to Slack, publishes to a NATS stream, or both is transparent.

## Deferred: FEAT-JARVIS-006 `jarvis.notification.{adapter}` Wire Promotion

The v1 Slack surface is in-process only. The long-term vision (`jarvis.notification.{adapter}` subject family, external adapter processes, multi-tenant routing) is explicitly deferred to FEAT-JARVIS-006. Rationale for deferral:

- v1 is single-operator, single-Slack-channel only (ADR-ARCH-026 no horizontal scaling, personal-use compliance posture per ADR-ARCH-029)
- Wire promotion requires Forge changes (publish to `jarvis.notification.{adapter}` in addition to `pipeline.*`) — out of scope for the "jarvis-only, zero Forge changes" v1 constraint
- The `NotificationSink` protocol is the abstraction boundary: v1.x can add a second implementation that publishes to JARVIS-stream without changing the subscriber or lifecycle wiring

The in-process sink is the v1-sufficient, structurally simple choice. The protocol seam preserves the future path.

## Alternatives Considered

| Option | Why Not |
|--------|---------|
| **Second ephemeral PIPELINE consumer** | Structurally invalid: workqueue retention rejects overlapping consumers with err_code 10100. Verified against canonical `nats-infrastructure` provisioning 2026-07-03. |
| **Durable Slack-specific consumer with non-overlapping filter** | No non-overlapping subjects exist: the Slack surface needs the same lifecycle events the CLI FIFO consumes (`build-started`, `build-complete`, `build-failed`, etc.). Inventing synthetic routing subjects would break the Forge contract. |
| **Switch PIPELINE to `LimitsPolicy` retention** | Out of scope: Forge's `forge-prod` durable consumer depends on workqueue ack-deletes semantics for build-trigger draining (per DDR-027 workqueue interaction block). Changing retention would alter Forge's correctness model, not just Jarvis's Slack bridge. |
| **Publish to a separate `NOTIFICATIONS` stream** | Requires Forge to double-publish every lifecycle event (once to PIPELINE, once to NOTIFICATIONS) — violates the v1 "jarvis-only, zero Forge changes" constraint. Deferred to FEAT-JARVIS-006 wire promotion. |
| **In-process sink invoking a background task that publishes to `jarvis.notification.{adapter}`** | Premature: no consumer exists for that subject family yet, and the JARVIS-stream provisioning/routing/adapter-manager are out of v1 scope. The protocol seam preserves this path for v1.x. |

## Consequences

- `ForgeNotificationsSubscriber` binds exactly one ephemeral PIPELINE consumer on startup; boot logs show no err_code 10100.
- `bind_notification_sink(sink)` is called from `lifecycle.build_app_state` (TASK-JNB-003); the subscriber stores `self._notification_sink` and invokes `await self._notification_sink.notify(notification)` inside `_handle_message` after validation, before correlation lookup.
- Sink failures (Slack API errors, full queue, stopped sink) are WARNING-only; they never propagate into the JetStream callback or affect the returned `QueueBuildAck` from `queue_build`.
- `SlackNotifier` is constructed with a bounded `asyncio.Queue` drained by a single worker task serialising `chat.postMessage` at ~1 msg/s (TASK-JNB-001). All delivery state is in-process only (consistent with DDR-027 no-replay posture).
- The `_notification_sink` module-level snapshot in `tools/dispatch.py` is wired in `lifecycle.build_app_state` alongside `_forge_subscriber` and `_nats_client`; `queue_build` fires `build_queued` notifications via this snapshot (TASK-JNB-002).
- Suppressed event types (`stage_complete`, `build_progress`, `build_resumed` per ASSUM-002) are gated inside `SlackNotifier.notify()` so they never occupy dedup map slots or queue capacity.
- The `NotificationSink` protocol surface is stable and minimal: `async notify(ForgeNotification)` plus `start()`/`stop()`. FEAT-JARVIS-006 can add a second implementation (NATS publisher) without changing the subscriber or lifecycle wiring.
- v1.x scope boundary: single-operator, single-Slack-channel, in-process delivery only. Multi-tenant routing, external adapters, and wire promotion are FEAT-JARVIS-006 territory.

## Cross-References

- **Related DDRs:** [DDR-007](../../FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md) (never-raise contract), [DDR-021](../../FEAT-JARVIS-004/decisions/DDR-021-amendment-capabilities-registry-tool-wiring.md) (NATS soft-fail), [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md) (workqueue retention, ephemeral consumer, in-memory state), [DDR-033](DDR-033-correlation-independent-fan-out.md) (fan-out before correlation), [DDR-034](DDR-034-slack-dedup-placement.md) (dedup inside sink)
- **Implementing tasks:** TASK-JNB-001 (SlackNotifier + NotificationSink protocol), TASK-JNB-002 (bind_notification_sink + queue_build hook), TASK-JNB-003 (lifecycle wiring)
- **Assumptions:** ASSUM-002 (suppressed event types), ASSUM-011 (build_queued is publish-side)
