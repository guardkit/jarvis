# ADR-ARCH-008: No SQLite — Graphiti + Memory Store sufficient for Jarvis

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Forge uses SQLite (`~/.forge/forge.db`) for the authoritative build-lifecycle history (`builds` + `stage_log` tables). Jarvis has no equivalent long-running build entity — sessions are ephemeral, watchers are in-process, routing decisions are recorded to Graphiti as events.

## Decision

Jarvis v1 uses **only** Graphiti (for trace-rich history and general knowledge) and LangGraph Memory Store (for cross-session recall). No SQLite.

Stores:
- **Graphiti groups**: `jarvis_routing_history`, `jarvis_ambient_history`, plus shared general knowledge. Durable.
- **LangGraph Memory Store**: cross-session recall, local disk persistence.
- **Per-session thread state**: ephemeral within supervisor graph. LangGraph-managed.

No LangGraph checkpointer in v1 — sessions don't need persistence across supervisor restarts; active sessions are re-initiated if the supervisor restarts.

## Alternatives considered

1. **Add SQLite for session index + watcher registry** *(rejected for v1)*: Provides fast listing of active sessions and Pattern B watchers. Adds a persistence layer Jarvis doesn't otherwise need. Watcher durability across restart is explicitly non-goal (ADR-ARCH-028). If operational visibility becomes a pain, revisit — could add SQLite later without breaking anything.

## Consequences

- Diverges from Forge ADR-ARCH-009 (which uses SQLite) by necessity — different problem shape.
- Simpler persistence story — one durable store (Graphiti) + one recall store (Memory Store).
- Operational introspection (which sessions active? which watchers running?) comes from in-memory supervisor state + trace-rich Graphiti records, not a queryable SQL table. If this proves inadequate, reopen.
