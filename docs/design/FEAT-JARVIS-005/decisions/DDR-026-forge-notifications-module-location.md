# DDR-026 — Forge notifications subscriber lives in dedicated `infrastructure/forge_notifications.py` (not on `SessionManager`)

- **Status:** Accepted
- **Date:** 2026-04-29
- **Feature:** FEAT-JARVIS-005 (Phase 3 / Fleet Integration)
- **Related:** [ADR-ARCH-006](../../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md), [phase3-fleet-integration-scope.md §FEAT-005 Open Questions](../../../research/ideas/phase3-fleet-integration-scope.md), [DDR-027](DDR-027-stage-complete-ephemeral-deliver-new.md), [DDR-028](DDR-028-correlation-map-in-memory-bounded.md)

## Context

phase3-fleet-integration-scope.md §"Open Questions `/system-design` Resolves" raised the question:

> `jarvis.notification.forge-stage-complete.*` routing. Is the router a dedicated module or a method on `SessionManager`? Impacts how FEAT-JARVIS-006 (Telegram) slots in.

Two viable shapes:

1. **Dedicated module** — `infrastructure/forge_notifications.py` owns the JetStream subscription, the in-memory correlation map, and the bridge that calls into `SessionManager.enqueue_notification`.
2. **`SessionManager` method** — `SessionManager.start_forge_subscription()` and `SessionManager._on_stage_complete(...)` live on the manager itself; correlation map is a manager attribute.

The choice matters because FEAT-JARVIS-006 (Telegram) reuses the same router seam — the in-process `jarvis.notification.forge-stage-complete.{correlation_id}` becomes a real NATS subject under `jarvis.notification.{adapter}` per ARCHITECTURE.md §7. The seam location is where that one-shot promotion lands.

## Decision

The Forge notifications subscriber, the in-memory correlation map, and the in-process bridge live in **`src/jarvis/infrastructure/forge_notifications.py`** — a dedicated module.

`SessionManager` exposes a thin per-session enqueue/drain surface (`enqueue_notification`, `pending_notifications`) that the subscriber calls into. The manager **does not** own the JetStream subscription, the correlation map, or the bridge logic.

## Rationale

- **Matches the ADR-ARCH-006 five-group layout.** Group D (`adapters/`) and Group A (`infrastructure/`) house the I/O edges. NATS subscription is transport plumbing, not session lifecycle. Putting it on `SessionManager` would mix the two concerns.
- **Symmetric with FEAT-J004 placement.** `nats_client.py`, `fleet_registration.py`, `capabilities_registry.py`, `routing_history.py`, `dispatch_semaphore.py` all live in `infrastructure/`. Adding `forge_notifications.py` there keeps the symmetry — every NATS-touching module is in one place.
- **Easier to swap when FEAT-J006 lands.** When the in-process bridge becomes a real NATS publish on `jarvis.notification.{adapter}`, the change is local to `forge_notifications.py`. A `SessionManager`-based router would entangle the manager's session lifecycle with adapter-specific routing logic.
- **Keeps `SessionManager` focused.** The manager already orchestrates session start/end, thread-per-session isolation (DDR-004), `current_session()` ContextVar (FEAT-J003 Layer 2 hook), and concurrent-invoke refusal (ASSUM-003). Adding JetStream subscription + correlation map + payload validation makes it a god-class.
- **Testability.** A standalone `ForgeNotificationsSubscriber` class is unit-testable without spinning up a `SessionManager`; the bridge target is a small `enqueue_notification(session_id, ForgeNotification)` API that's trivial to mock.

## Alternatives considered

| Option | Why not |
|---|---|
| `SessionManager` method | Mixes transport with session lifecycle; complicates the FEAT-J006 promotion path; turns a focused class into a god-class |
| `tools/dispatch.py` module-level subscriber | Tools are `@tool`-decorated reasoning surfaces; running JetStream subscriptions from a tool module breaks the ADR-ARCH-006 layering |
| `agents/supervisor.py` (build_supervisor) ownership | Subscription must outlive the supervisor build; lifecycle would have to gate on supervisor construction |
| Make it a free-function in `lifecycle.py` | Lifecycle composes; it doesn't own. The subscriber has its own state (correlation map, consumer handle) — it deserves a class |

## Consequences

- One new file: `src/jarvis/infrastructure/forge_notifications.py` (~250 LOC).
- `SessionManager` adds two narrow methods (`enqueue_notification`, `pending_notifications`) and clears the per-session queue on `end_session`. No transport awareness.
- `lifecycle.build_app_state` constructs the subscriber after `nats_client + routing_history_writer` are wired and **late-binds** the session manager onto it (after the manager is built, before `AppState` is returned).
- `lifecycle.shutdown` calls `subscriber.stop()` between heartbeat-cancel and fleet-deregister.
- FEAT-J006 (Telegram adapter) imports the same module; the `jarvis.notification.forge-stage-complete.{correlation_id}` promotion lives in `forge_notifications.py` exclusively.
- Module docstring: "JetStream subscriber for `pipeline.stage-complete.>` plus the in-process notification router that bridges matched events to the active `SessionManager`."

## Status

Accepted at FEAT-JARVIS-005 `/system-design`.
