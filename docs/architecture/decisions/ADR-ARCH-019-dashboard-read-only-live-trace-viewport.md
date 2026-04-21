# ADR-ARCH-019: Dashboard read-only live trace viewport

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

The Dashboard adapter is Rich's visual monitoring surface. It could be command-input only (like Telegram/CLI), or it could also provide a live trace view (read model of routing decisions, dispatches, notifications). A live trace view adds observability and makes the fleet legible — valuable for YouTube content and debugging.

## Decision

Dashboard v1 provides **both** command input and a read-only live trace viewport. It subscribes (read-only) to:

- `jarvis.command.*` (see all adapter inputs in real time)
- `notifications.*` (see all outbound messages across adapters)
- `pipeline.*` (see Forge pipeline progress)
- `agents.command.*` / `agents.result.*` (specialist dispatches)
- `fleet.register` + `agent-registry` KV (fleet state)

The React UI renders:
- Session list with current thread + thread summary
- Live trace of the active session (reasoning steps, tool calls, routing decisions)
- Fleet health summary (who's registered, llama-swap state, watcher count)
- Pending `CalibrationAdjustment` queue (read-only — approval still via CLI per ADR-ARCH-018)

**No write actions in v1 beyond sending user input** on `jarvis.command.dashboard`. No approval round-trip, no watcher management UI, no calibration-proposal creation.

## Alternatives considered

1. **Command input only — no trace view v1** *(rejected)*: Loses observability benefit; loses YouTube-content angle.
2. **Full-featured dashboard with write actions** *(rejected for v1)*: Scope creep; defer watcher-management UI / calibration-approval UI until patterns stabilise.
3. **Defer Dashboard adapter to v1.5** *(rejected)*: Dashboard is priority 3 in the launch plan (vision §3); the trace view justifies the priority.

## Consequences

- Dashboard container is more substantial than other adapters (React build, WebSocket bridge, larger codebase).
- NATS subscriptions on read-only streams are lightweight — no performance concern.
- Trace-rich Graphiti data (`jarvis_routing_history`) can be queried by the Dashboard for historical trace inspection in future versions.
