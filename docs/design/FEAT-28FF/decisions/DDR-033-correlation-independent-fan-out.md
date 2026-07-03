# DDR-033 — Notification fan-out is correlation-independent: sink called before and independent of correlation-map lookup

- **Status:** Accepted
- **Date:** 2026-07-03
- **Feature:** FEAT-28FF (UBS-003 / Slack Notification Bridge v1)
- **Related:** [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md), [DDR-028](../../FEAT-JARVIS-005/decisions/DDR-028-correlation-map-in-memory-bounded.md), [DDR-032](DDR-032-notification-sink-in-process.md), [DDR-034](DDR-034-slack-dedup-placement.md), [TASK-JNB-002](../../../../tasks/design_approved/TASK-JNB-002-notification-sink-seam-in-forgenotificationssubs.md)
- **Assumptions:** ASSUM-002 (suppressed event types), ASSUM-006 (dedup TTL)

## Context

The existing `ForgeNotificationsSubscriber._handle_message` flow (FEAT-JARVIS-005) delivers notifications to the CLI FIFO only when a correlation-map lookup succeeds — i.e., when the `correlation_id` from a `build_started`/`build_complete`/`build_failed` event matches a session that queued the build via `queue_build`. This is correct for the CLI surface: the operator sees progress only for builds they started.

The v1 Slack notification bridge adds a second surface — the operator's phone — with different semantics. Two architectural options exist:

1. **Correlation-DEPENDENT fan-out:** Call `sink.notify()` only when the correlation-map lookup succeeds, mirroring the CLI FIFO gate.
2. **Correlation-INDEPENDENT fan-out:** Call `sink.notify()` after envelope decode and validation but before and independent of the correlation-map lookup.

The Slack surface is per-operator, not per-session. The correlation map is in-memory with LRU eviction (DDR-028: 1000-entry bounded map, evict-on-insert). A Jarvis restart loses all correlation entries. The CLI FIFO is session-ephemeral (ADR-ARCH-009), so correlation-map loss on restart is acceptable there — the operator's terminal sessions are gone anyway. But the phone surface is operator-global and persistent across Jarvis restarts.

## Decision

**Notification fan-out is correlation-INDEPENDENT: `sink.notify()` is invoked after envelope decode + `source_id == 'forge'` gate + typed payload validation, but BEFORE and INDEPENDENT of the correlation-map lookup.**

The call sequence in `ForgeNotificationsSubscriber._handle_message` (TASK-JNB-002):

1. Envelope decode (NATS message → JSON → `ForgeNotificationEnvelope`)
2. `source_id == 'forge'` gate (drop non-Forge envelopes with WARNING)
3. Typed payload validation (decode `event_type`-specific payload, e.g., `BuildStartedPayload`)
4. **→ `sink.notify(notification)` call here** (if a sink is bound)
5. Correlation-map lookup (`self._correlation_map.get(correlation_id)`)
6. CLI FIFO delivery (only if correlation lookup succeeded)

The sink call sits between steps 3 and 5. A correlation-map miss does not prevent the sink from being notified.

## Rationale

### Restart Resilience for the Operator-Global Surface

The phone is per-operator, not per-session. An overnight build queued before a Jarvis restart should still notify the phone when it completes, even though the correlation entry was lost on restart. Correlation-independent fan-out preserves this property:

- **Before restart:** Operator queues build B1 via `queue_build` at 18:00. Correlation entry `(corr_id_B1, session_id_S1)` is registered in the in-memory map.
- **Restart at 19:00:** Jarvis restarts. Correlation map is empty (DDR-028: in-memory only, no persistence).
- **Build completes at 21:00:** Forge publishes `build-complete` with `correlation_id=corr_id_B1`.
  - Correlation-map lookup fails (entry was lost on restart).
  - CLI FIFO delivery is skipped (session S1 is gone anyway per ADR-ARCH-009).
  - **Phone notification is still delivered** because `sink.notify()` is called before the correlation lookup.

The operator's mental model: "My phone shows me what's happening, even if Jarvis crashed." Correlation-dependent fan-out would silently drop all in-flight builds on restart — unacceptable for an overnight/weekend build surface.

### Accepted Consequence: Deliberate Noise

Correlation-independent fan-out means the phone receives notifications for **all** Forge builds with `source_id == 'forge'`, not just builds queued through Jarvis. If the operator (or another tool) queues a build directly via Forge's CLI or API, the phone is notified even though Jarvis has no correlation entry.

This is **deliberate noise**, not a bug. The operator surface is "show me all Forge activity for my operator identity", not "show me only Jarvis-queued builds". The restart-resilience property requires this trade-off.

### Rollback Lever: Config Toggle

If the noise consequence proves operationally unacceptable (e.g., a CI system flooding Forge with builds not routed through Jarvis), a config toggle `JARVIS_SLACK_NOTIFY_CORRELATED_ONLY=true` can be added to switch back to correlation-dependent fan-out. This toggle is **not implemented in v1** but is named here as the documented rollback path.

Enabling the toggle would:
- Move the `sink.notify()` call from before the correlation lookup to after it (inside the `if session_id is not None:` branch)
- Restore correlation-dependent semantics (phone notifies only for Jarvis-queued builds)
- Accept the silent-drop-on-restart consequence for overnight builds

The toggle is a one-line if-gate in `_handle_message`. Its absence in v1 is an operator sign-off on the noise consequence.

## Alternatives Considered

| Option | Why Not |
|--------|---------|
| **Correlation-dependent fan-out (mirror CLI FIFO gate)** | Breaks restart resilience: overnight builds queued before a Jarvis restart would not notify the phone on completion because the correlation entry is lost. Unacceptable for the operator-global surface. |
| **Persist correlation map to disk/KV** | Out of v1 scope: adds durability machinery (SQLite? NATS KV?) and cross-restart state management. DDR-028 explicitly chose in-memory-only for simplicity. Deferrable to v1.x if restart-resilience for the CLI FIFO becomes a requirement. |
| **Fan out only on terminal events, suppress started** | Reduces noise but doesn't eliminate it: a non-Jarvis build would still notify on completion. Also breaks the "show me when my build starts" UX. Noise reduction is better addressed via the rollback toggle or future Forge-side filtering. |
| **Forge publishes to separate `jarvis.notification.{adapter}` subjects** | Requires Forge changes (violates v1 "jarvis-only, zero Forge changes" constraint). Deferred to FEAT-JARVIS-006 wire promotion. |

## Operator Sign-Off on Noise Consequence

**This DDR records explicit operator acceptance of the noise consequence.**

The phone will notify for:
- All Jarvis-queued builds (intended)
- All Forge builds queued outside Jarvis with `source_id == 'forge'` (deliberate noise, accepted for restart resilience)

The rollback lever is the `JARVIS_SLACK_NOTIFY_CORRELATED_ONLY` config toggle (not implemented in v1, documented as the escape hatch).

## Consequences

- `ForgeNotificationsSubscriber._handle_message` calls `sink.notify()` after typed payload validation, before correlation-map lookup (TASK-JNB-002).
- A correlation-map miss does not prevent Slack delivery. CLI FIFO delivery is still gated on correlation success (existing behaviour unchanged).
- Builds queued outside Jarvis (via Forge CLI, Forge API, or other tools) trigger phone notifications if `source_id == 'forge'`.
- Jarvis restarts do not silence phone notifications for in-flight builds queued before the restart.
- The correlation map remains in-memory only (DDR-028), LRU-bounded, no persistence.
- Suppressed event types (`stage_complete`, `build_progress`, `build_resumed` per ASSUM-002) are gated inside `SlackNotifier.notify()` so they never reach the phone, regardless of correlation status.
- Dedup inside `SlackNotifier` (DDR-034) uses `(event_type, build_id, stage_label or '')` as the key for stream events — build_id is always present on Forge payloads, so dedup works whether or not a correlation entry exists.
- The `build_queued` notification (publish-side hook in `queue_build`, ASSUM-011) always has a correlation entry by construction (it's fired immediately after `register_correlation`), so it's unaffected by this decision.
- Future config toggle `JARVIS_SLACK_NOTIFY_CORRELATED_ONLY=true` is the documented rollback path if noise proves unacceptable; moving the `sink.notify()` call inside the correlation-success branch is a one-line change.

## Cross-References

- **Related DDRs:** [DDR-027](../../FEAT-JARVIS-005/decisions/DDR-027-stage-complete-ephemeral-deliver-new.md) (ephemeral consumer, in-memory state), [DDR-028](../../FEAT-JARVIS-005/decisions/DDR-028-correlation-map-in-memory-bounded.md) (LRU map, no persistence), [DDR-032](DDR-032-notification-sink-in-process.md) (sink seam), [DDR-034](DDR-034-slack-dedup-placement.md) (dedup keyed on build_id, not correlation_id)
- **Implementing tasks:** TASK-JNB-002 (bind_notification_sink, call placement in _handle_message)
- **Assumptions:** ASSUM-002 (suppressed event types), ASSUM-006 (dedup 300s TTL)
