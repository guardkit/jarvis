# ADR-ARCH-009: Thread-per-session with Memory Store summary-bridge

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Resolves:** JA3 (cross-adapter handoff semantics)

## Context

Rich interacts with Jarvis via four adapter surfaces (Telegram, CLI, Dashboard, Reachy). A single live thread shared across adapters would pollute each adapter's context with the others' live messages, trigger auto-summarisation churn, and complicate trace-per-session. But users do switch adapters mid-task ("we discussed this on Telegram this morning, let's continue on Reachy now"), so some continuity is needed.

## Decision

**Single Jarvis supervisor, thread-per-session.** A session is the tuple (adapter_id, session_id), where session_id is adapter-minted.

- Telegram session this morning → thread A
- Reachy session this evening → thread B
- Dashboard session while coding → thread C

Threads share **LangGraph Memory Store** for durable recall ("last week we discussed..."). Threads do **not** share live context windows.

Cross-adapter continuity via:
- **Memory Store** for recall — Jarvis retrieves relevant entries when starting a new session
- **Graphiti `jarvis_routing_history`** for routing priors (learned preferences across all sessions)
- **Graphiti `jarvis_ambient_history`** for notification-pattern priors

**No explicit "continue session" command in v1.** Rich relies on natural-language recall ("what did we decide about the talk?") which Jarvis resolves via Memory Store retrieval. If this proves insufficient, reopen JA3 and add an explicit-continue primitive.

## Alternatives considered

1. **Single shared thread across adapters** *(rejected)*: Context pollution; auto-summarisation churn; broken trace-per-session.
2. **Supervisor-per-adapter** *(rejected)*: Coordination complexity with no gain — one supervisor covers all adapters natively.
3. **Explicit continue command forces same thread** *(rejected for v1)*: More precise, more UX friction, cross-adapter context bleed risk. Can be added later without breaking the summary-bridge default.
4. **Both — summary-bridge default + explicit-continue escape hatch** *(rejected for v1)*: Most flexible; most implementation complexity; defer until we see real handoff failure patterns.

## Consequences

- LangGraph-native pattern (supervisor graph state is thread-scoped; Memory Store is thread-independent).
- Clean trace per session — each thread produces a standalone routing/dispatch log.
- Cross-session continuity depends on Memory Store retrieval quality. If Rich finds himself re-explaining context often, revisit.
- Captured as `ASSUM-013` for /system-design validation.
