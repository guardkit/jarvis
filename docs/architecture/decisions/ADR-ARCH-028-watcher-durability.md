# ADR-ARCH-028: Ambient watchers non-durable in v1; specs optionally persisted for respawn

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Pattern B watchers are async subagents running inside the Jarvis supervisor. When the supervisor restarts (deploy, reboot, crash), in-process state is lost. Watchers could be made durable via state-store persistence and auto-respawn, but this adds lifecycle logic disproportionate to v1 needs.

## Decision

**Watchers are non-durable across supervisor restarts in v1.** When the supervisor restarts:

- All active watchers are terminated (no graceful drain needed — they are monitoring, not holding critical state).
- Watcher specs are **optionally** persisted to Graphiti (`jarvis_ambient_history` meta-entries) at spawn time, so:
  - The operator CLI can list previously-active watchers (`jarvis watchers list --previous-session`)
  - The `morning-briefing` skill can suggest respawning important watchers
  - Rich can explicitly re-trigger ("spawn all my watchers from yesterday")

**No auto-respawn on startup in v1.** If a watcher was monitoring something important, Rich respawns it explicitly.

## Alternatives considered

1. **Durable watchers with auto-respawn via Graphiti** *(rejected for v1)*: Adds lifecycle logic (spawn / respawn / reconcile) disproportionate to single-operator v1 needs. Useful once ambient becomes core — revisit.
2. **No spec persistence at all** *(rejected)*: Loses useful information for the operator; prevents `morning-briefing` from learning yesterday's watcher patterns.

## Consequences

- Supervisor restart is a "clean slate" for ambient monitoring.
- Rich bears the small cost of re-spawning important watchers after a restart (infrequent event).
- Captured as `ASSUM-007`.
- Path to durable watchers is additive — persisting specs already produces the inputs; add auto-respawn when it becomes worth the complexity.
