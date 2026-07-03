# DDR-034 — Slack dedup is enqueue-time first-wins 300s TTL inside `SlackNotifier`, in-process only

- **Status:** Accepted
- **Date:** 2026-07-03
- **Feature:** FEAT-28FF (UBS-003 / Slack Notification Bridge v1)
- **Related:** [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md), [DDR-028](../../FEAT-JARVIS-005/decisions/DDR-028-correlation-map-in-memory-bounded.md), [DDR-032](DDR-032-notification-sink-in-process.md), [DDR-033](DDR-033-correlation-independent-fan-out.md), [TASK-JNB-001](../../../../tasks/design_approved/TASK-JNB-001-slacknotifier-component-slack-settings-slack-sdk.md), [TASK-JNB-006](../../../../tasks/design_approved/TASK-JNB-006-hardening-300s-first-wins-dedup-throttling-backo.md)
- **Assumptions:** ASSUM-006 (dedup 300s TTL)

## Context

JetStream provides at-least-once delivery semantics. A redelivered `build-complete` envelope could cause duplicate Slack posts to the operator's phone. Three placement options exist for deduplication:

1. **Inside Forge before publish** — Forge maintains a dedup map and publishes each terminal event exactly once
2. **Inside `ForgeNotificationsSubscriber` before sink call** — Jarvis subscriber deduplicates all stream events, both for CLI FIFO and Slack
3. **Inside `SlackNotifier` at enqueue time** — Slack sink maintains its own dedup map

The CLI FIFO is already idempotent-by-overwrite (FEAT-JARVIS-005): a redelivered terminal event updates `session.pending_notifications[build_id]` with the same value. The Slack surface is append-only (each post is a distinct message in a channel), so it requires explicit deduplication.

## Decision

**Dedup lives inside `SlackNotifier.notify()` at enqueue time — first-wins with a 300s TTL (ASSUM-006), keyed by event identity, using monotonic clock, evict-on-insert.**

### Dedup Map Design (TASK-JNB-006)

- **Data structure:** `dict[tuple, float]` mapping dedup key → monotonic expiry timestamp
- **TTL:** 300 seconds (5 minutes) per ASSUM-006
- **Clock:** `time.monotonic()` (not wall clock) to avoid DST/leap-second edge cases
- **Eviction:** On every `notify()` call, expired entries (where `now > expiry_timestamp`) are removed before checking/inserting the new key
- **Policy:** First-wins — if the key exists and is not expired, the notification is silently dropped (no enqueue, no log)

### Key Shapes

The dedup key distinguishes event identity:

1. **Stream events** (from `ForgeNotificationsSubscriber`):
   ```python
   key = (event_type, build_id, stage_label or '')
   ```
   - `event_type`: `'build_started'`, `'build_complete'`, `'build_failed'`, `'build_paused'`, `'build_cancelled'`
   - `build_id`: Always present on Forge payloads (e.g., `"b-20260703-abc123"`)
   - `stage_label`: Present for events tied to a specific stage (e.g., `'build_paused'` has the stage being approved); empty string for terminal/intake events

   Examples:
   - `('build_complete', 'b-123', '')` — terminal build completion
   - `('build_paused', 'b-456', 'deploy-prod')` — pause at deploy-prod stage

2. **Intake event** (from `queue_build` publish-side hook):
   ```python
   key = ('build_queued', correlation_id)
   ```
   - `event_type`: `'build_queued'`
   - `correlation_id`: Unique per `queue_build` invocation (e.g., `"corr-uuid-xyz"`)

   The `build_queued` event fires before Forge assigns a `build_id`, so the key uses `correlation_id` instead. This event is fire-and-forget from `tools/dispatch.py`; the subscriber never sees it.

### Placement Rationale

Dedup sits inside `SlackNotifier` (not in the subscriber, not in Forge) for three reasons:

1. **Subscriber is multi-surface:** `ForgeNotificationsSubscriber` delivers to both CLI FIFO (idempotent-by-overwrite) and Slack (append-only). Placing dedup in the subscriber would suppress redeliveries for the CLI FIFO, breaking its update-on-redelivery semantics.

2. **Slack surface is the only append-only consumer:** The CLI FIFO doesn't need dedup (it's a dict update). Future notification surfaces (email, webhooks, JARVIS-stream publishers) may have different idempotency needs. Dedup is a Slack-specific concern.

3. **Correlation-independent fan-out (DDR-033):** The sink is called before correlation lookup. If dedup were in the subscriber, it would need to key on `build_id` (correlation_id is not always available). Placing dedup inside the sink means the key shape is decided by the sink's needs, not constrained by the subscriber's call-site context.

### In-Process Only (Crash-Loop Can Double-Post)

The dedup map is **in-process only** — no persistence to disk, no shared state across Jarvis restarts. This matches the DDR-027 no-replay / DDR-028 in-memory posture for all notification state.

**Consequence:** A crash-loop inside the 300s window can double-post. Example:

1. Forge publishes `build-complete` for build B1 at T+0
2. Jarvis delivers to Slack at T+1, inserts dedup entry `('build_complete', 'b1', '')` → expires at T+301
3. Jarvis crashes at T+10
4. Jarvis restarts at T+15 (dedup map is empty)
5. JetStream redelivers `build-complete` for B1 at T+20 (workqueue re-presents unacked messages)
6. Jarvis delivers to Slack again at T+21 — **double-post**

**This is accepted as low-impact noise.** The alternative (persist dedup map to SQLite or NATS KV) is out of v1 scope:
- Adds durability machinery (schema, reads, writes, TTL cleanup)
- Increases latency on the notify hot path
- Requires cross-restart state lifecycle (when to purge expired entries on startup?)

The crash-loop double-post is cosmetic (operator sees two identical Slack messages) and rare (requires crash during the 300s window). The v1 posture is in-memory only; durability can be added in v1.x if operational pain warrants.

## Alternatives Considered

| Option | Why Not |
|--------|---------|
| **Dedup in Forge before publish** | Requires Forge changes (violates v1 "jarvis-only, zero Forge changes" constraint). Also doesn't cover the `build_queued` intake event (which is a Jarvis-side hook, not a Forge publish). |
| **Dedup in `ForgeNotificationsSubscriber`** | Subscriber is multi-surface: CLI FIFO is idempotent-by-overwrite and benefits from redelivery (latest terminal state wins). Placing dedup in the subscriber would suppress redeliveries globally, not just for Slack. |
| **Dedup after enqueue, in worker loop** | Wastes queue slots on duplicates; bounded-queue overflow (TASK-JNB-006) would drop real events to make room for duplicates. Enqueue-time dedup is cleaner. |
| **Persist dedup map to SQLite** | Out of v1 scope: adds durability machinery, schema, TTL cleanup logic, and read latency on the hot path. The crash-loop double-post consequence is low-impact noise; in-memory-only is the v1-sufficient choice. |
| **Persist dedup map to NATS KV** | Same scope/complexity concerns as SQLite. Also: NATS KV has its own TTL/replication semantics to reason about. Deferred to v1.x. |
| **No dedup, rely on Slack's message dedup** | Slack does not deduplicate identical text posts — each `chat.postMessage` call creates a distinct message, even if the text is byte-identical. Append-only surfaces require explicit deduplication. |

## Consequences

- `SlackNotifier.notify()` checks the in-process dedup map before enqueuing (TASK-JNB-006). If the key exists and is not expired, the notification is silently dropped (no enqueue, no log, no exception).
- Expired entries are evicted on every `notify()` call (sweep-on-insert) using `time.monotonic()` comparison.
- Stream events key on `(event_type, build_id, stage_label or '')`. The `build_queued` intake event keys on `('build_queued', correlation_id)`.
- Dedup map state is in-memory only. A Jarvis crash-loop inside the 300s window can double-post to Slack (accepted low-impact noise).
- Suppressed event types (`stage_complete`, `build_progress`, `build_resumed` per ASSUM-002) are gated before the dedup check, so they never occupy map slots.
- Tests (TASK-JNB-006): duplicate terminal envelope posts once; TTL expiry allows repost after 300s; concurrent distinct terminals both post; queued intake deduplicates on correlation_id; monotonic clock patching makes tests fast and deterministic.
- The dedup map is a new `dict` field on `SlackNotifier`, initialized in `__init__`, cleared on `stop()`.
- No cross-restart state: the map is lost on restart, and the first redelivery of any event after restart will post to Slack (same observable behaviour as if the event arrived for the first time).

## Cross-References

- **Related DDRs:** [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md) (in-memory state, no replay), [DDR-028](../../FEAT-JARVIS-005/decisions/DDR-028-correlation-map-in-memory-bounded.md) (in-memory map precedent), [DDR-032](DDR-032-notification-sink-in-process.md) (sink seam), [DDR-033](DDR-033-correlation-independent-fan-out.md) (keys on build_id, not correlation_id)
- **Implementing tasks:** TASK-JNB-001 (SlackNotifier component), TASK-JNB-006 (dedup map, TTL, key shapes, tests)
- **Assumptions:** ASSUM-006 (300s TTL)
