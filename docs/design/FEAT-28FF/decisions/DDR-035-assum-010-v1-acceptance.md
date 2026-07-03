# DDR-035 — ASSUM-010 v1 acceptance: pause-is-last-signal accepted, build-cancelled handler implemented day-one, closure delegated to v1.1

- **Status:** Accepted
- **Date:** 2026-07-03
- **Feature:** FEAT-28FF (UBS-003 / Slack Notification Bridge v1)
- **Related:** [DDR-032](DDR-032-notification-sink-in-process.md), [DDR-033](DDR-033-correlation-independent-fan-out.md), [TASK-JNB-005](../../../../tasks/design_approved/TASK-JNB-005-pause-cancelled-lifecycle-filter-extension-and-r.md), TASK-JNB-102 (v1.1 / Forge-side `publish_build_cancelled` wiring)
- **Assumptions:** ASSUM-010 (pause-is-last-signal for v1)

## Context

Forge's build lifecycle includes two quality-gate pause points (per Forge ADR-ARCH-033 / gate modes):

1. **`build-paused`** — The build has reached a gate (e.g., deploy-prod stage); the coach has evaluated the rationale and either recommended approval, rejection, or flagged the score as unavailable. The operator must approve or reject to continue.

2. **`build-cancelled`** — The build was explicitly cancelled (by operator CLI command, max-wait timeout, or rejection). This is the terminal "did not proceed past gate" state.

The Forge contract is: after `build-paused`, the next signal is **either** a `build-complete` (if approved and the build succeeded) **or** a `build-cancelled` (if rejected, timed out, or manually cancelled). The operator's phone should surface both outcomes.

ASSUM-010 records the v1 split decision: the `build-cancelled` handler is **implemented and unit-validated from day one** (TASK-JNB-005), but **Forge does not publish `build-cancelled` in v1**. The only live `CANCELLED` producer in v1 is the operator's own `forge cancel` CLI invocation (off the checkpoint path — the operator already knows they cancelled it). The pause → complete path is live; the pause → cancelled path is code-complete but has no upstream producer.

## Decision

**For v1, pause-is-last-signal is accepted as the observable phone UX. The `build-cancelled` handler is implemented and unit-validated day-one (TASK-JNB-005) so the phone path goes live the moment Forge starts emitting. Gap closure is explicitly delegated to v1.1 (TASK-JNB-102).**

### v1 Split Decision

1. **Jarvis-side handler is complete:** `ForgeNotificationsSubscriber._handle_message` gains a `BuildCancelledPayload` projection branch (TASK-JNB-005). `ForgeNotification.event_type` Literal includes `'build_cancelled'`. `SlackNotifier` renders the cancelled message (shows `cancelled_by`, `reason`). All unit tests validate against synthetic `build-cancelled` envelopes.

2. **Forge does not publish `build-cancelled` in v1:** The `publish_build_cancelled` helper exists in Forge's `pipeline_notifications.py` but is not wired to the reject/max-wait/CLI-cancel transitions in v1. Wiring it would require Forge code changes, breaking the v1 "jarvis-only, zero Forge changes" constraint.

3. **Observable v1 phone UX:** After a `build-paused` notification, the operator sees either:
   - `build-complete` (if they approved via CLI and the build succeeded)
   - **Nothing** (if they rejected, or max-wait timed out, or they ran `forge cancel`)

   The "nothing" case is the pause-is-last-signal gap. The operator must infer cancellation from the absence of a completion signal.

4. **v1 mitigation:** The `build-paused` Slack message includes a CLI hint line: `"To approve: jarvis approve <build-id>; to reject: forge cancel <build-id>"`. This reminds the operator that rejection is a CLI action and sets the expectation that cancelled builds do not auto-notify the phone in v1.

5. **v1.1 closure (TASK-JNB-102):** Wire Forge's existing `publish_build_cancelled` helper onto the three cancellation paths:
   - Explicit rejection (operator runs `forge cancel` or uses the v1.1 Jarvis approve/reject command)
   - Max-wait timeout (gate expires without operator action)
   - CLI cancel (already exists, becomes a proper publish point instead of a side-effect)

   Once wired, the Jarvis-side handler (implemented in TASK-JNB-005) becomes live with zero additional Jarvis changes. The phone receives `build-cancelled` notifications the moment Forge starts publishing them.

### Rationale for the Split

**Why accept pause-is-last-signal for v1?**

- **v1 constraint:** "jarvis-only, zero Forge changes" (operator decision, scoping for rapid checkpoint). Wiring `publish_build_cancelled` touches Forge's `pipeline_coordinator.py` state machine — a Forge change, not a Jarvis change.

- **Low operational impact:** The only live `CANCELLED` producer in v1 is the operator's own `forge cancel` CLI invocation. If the operator manually cancels a build, they already know it's cancelled — the missing phone notification is low-impact noise, not a lost critical signal.

- **Day-one code completeness preserves v1.1 path:** Implementing the handler in v1 (even though it has no producer) means v1.1 Forge changes are Forge-only. The Jarvis subscriber already speaks the `build-cancelled` contract; TASK-JNB-102 is purely Forge-side wiring.

**Why not defer the handler to v1.1?**

- Deferring the handler would require re-touching the subscriber, `ForgeNotification` widening, and Slack rendering in v1.1 — spreading a single feature (cancelled notifications) across two waves. Implementing day-one keeps the Jarvis contract complete and isolates v1.1 work to Forge.

## Accepted Consequence

**The operator may see pause-is-last-signal for rejected/timed-out/cancelled builds in v1.**

Example scenario:
1. Operator queues build B1 via `queue_build`
2. Build pauses at `deploy-prod` gate; phone receives `build-paused` notification
3. Operator rejects via `forge cancel b1`
4. **Phone receives no `build-cancelled` notification** (Forge does not publish it in v1)
5. Operator infers cancellation from the absence of `build-complete`

This is explicitly accepted for v1 as the trade-off for "jarvis-only, zero Forge changes". The CLI hint in the pause message sets operator expectations.

## v1.1 Closure: TASK-JNB-102

TASK-JNB-102 (Forge-side, v1.1) wires `publish_build_cancelled` onto:
- `PipelineCoordinator._handle_rejection()` (explicit operator rejection)
- `PipelineCoordinator._handle_gate_timeout()` (max-wait expiry)
- `forge cancel` CLI command handler (make it a proper publish point)

Once landed, the Jarvis-side handler implemented in TASK-JNB-005 becomes live with zero additional Jarvis changes. The phone UX becomes: pause → cancelled for all rejection paths, pause → complete for approval + success paths.

## Alternatives Considered

| Option | Why Not |
|--------|---------|
| **Wire `publish_build_cancelled` in v1** | Requires Forge changes (violates "jarvis-only, zero Forge changes" v1 constraint). Deferred to v1.1. |
| **Defer Jarvis handler to v1.1** | Spreads a single feature (cancelled notifications) across two waves; v1.1 would require re-touching subscriber, ForgeNotification, and SlackNotifier. Implementing day-one isolates v1.1 work to Forge. |
| **Poll Forge state to detect cancellation** | Adds polling machinery (when? how often?) and a new dependency on Forge's build-state API. The publish-subscribe model is cleaner: Forge publishes cancellation, Jarvis reacts. Deferred to never. |
| **Send a synthetic `build-cancelled` from Jarvis when CLI rejection is invoked** | Jarvis does not own the rejection command in v1 (operator runs `forge cancel`). Jarvis cannot send a notification for an action it didn't mediate. v1.1 adds a Jarvis `reject` command that can do this. |

## Consequences

- `ForgeNotificationsSubscriber._get_lifecycle_subjects()` includes `pipeline.build-cancelled.>` in v1 (TASK-JNB-005), extending the filter from 4 to 6 subjects on the single ephemeral consumer (no second consumer per DDR-032).
- `_handle_message` gains a `BuildCancelledPayload` projection branch; `ForgeNotification.event_type` Literal includes `'build_cancelled'`; new optional fields `cancelled_by` and `reason` are added with `None` defaults.
- `SlackNotifier` renders the cancelled message: shows `cancelled_by`, `reason`, plain-text Block Kit.
- Unit tests (TASK-JNB-005) validate the cancelled projection and rendering against synthetic envelopes constructed in-test (no live producer exists in v1).
- The `build-paused` Slack message includes a CLI hint: `"To approve: jarvis approve <build-id>; to reject: forge cancel <build-id>"` (v1 mitigation for pause-is-last-signal).
- v1 phone UX: pause → complete for approved builds; pause → **nothing** for rejected/timed-out/cancelled builds (accepted gap).
- v1.1 TASK-JNB-102 wires Forge's `publish_build_cancelled` onto rejection/timeout/CLI-cancel; the Jarvis-side handler becomes live with zero additional Jarvis changes.
- The v1 checkpoint (TASK-JNB-004) exercises the pause → approve → complete path only (the cancel path is unit-validated but not live-validated in v1).

## Cross-References

- **Related DDRs:** [DDR-032](DDR-032-notification-sink-in-process.md) (single consumer, filter extension), [DDR-033](DDR-033-correlation-independent-fan-out.md) (fan-out semantics)
- **Implementing tasks:** TASK-JNB-005 (pause + cancelled handler, rendering, unit tests), TASK-JNB-102 (v1.1 / Forge-side `publish_build_cancelled` wiring)
- **Assumptions:** ASSUM-010 (pause-is-last-signal accepted for v1)
