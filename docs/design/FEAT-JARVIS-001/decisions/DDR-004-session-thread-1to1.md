# DDR-004: `thread_id == session_id` — 1:1 mapping in Phase 1

**Status:** Accepted
**Date:** 2026-04-21
**Feature:** FEAT-JARVIS-001
**Deciders:** Rich + /system-design session
**Implements:** [ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md) at design level

---

## Context

[ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md) pins "single Jarvis supervisor, thread-per-session" — a session is tuple `(adapter_id, session_id)`, threads do not share live context windows, Memory Store is the cross-thread channel. The ADR does not specify how `thread_id` (a LangGraph-level primitive, passed in `config["configurable"]["thread_id"]` to `supervisor.ainvoke`) is derived from `session_id` (a Jarvis-level identity).

Two plausible mappings:
1. **1:1** — `thread_id = session_id`. One session = one thread for its entire lifetime.
2. **1:N** — session owns multiple threads (e.g. "main" thread + task-specific threads per `task()` call).

## Decision

Phase 1 fixes **1:1**: `session.thread_id = session.session_id` at session creation, immutable for the session lifetime.

`Session.session_id` format: `f"{adapter.value}-{uuid4().hex[:12]}"` (12 hex chars ≈ 48 bits of uniqueness — plenty for a single-user, single-host deployment).

`Session.thread_id` holds the same string. DeepAgents / LangGraph consume `thread_id` directly without further transformation.

## Rationale

- **LangGraph's thread model aligns with "conversation".** A thread is a conversation in LangGraph's vocabulary — the sequence of messages and intermediate state. A Jarvis session *is* a conversation. The 1:1 mapping matches the primitive to its intended use.
- **`task()` spawn does not create a new thread.** DeepAgents' `task` built-in (enabled in Phase 1) spawns subagent work; the resulting messages land back in the originating thread by default. No divergence from 1:1.
- **Human-readable session IDs help debugging.** The adapter prefix (`cli-a3f2b9...`) makes log-grep trivial. A bare UUID works but reads worse.
- **Collision-free.** 48 bits of entropy per adapter + adapter prefix = effectively unique globally for Phase 1's scale.

## Alternatives considered

1. **`session_id = uuid4().hex` (no adapter prefix).** *(Rejected)* — loses the log-readability advantage; trivially reintroduced if we ever need opaque IDs.
2. **`thread_id = f"{session_id}:main"` (leave room for `:tool`, `:subagent` threads).** *(Rejected for Phase 1)* — speculative; DeepAgents' `task()` handles sub-thread concerns internally. Revisit if FEAT-JARVIS-003 async subagents need per-subagent thread isolation.
3. **Monotonic session counter `cli-000042`.** *(Rejected)* — requires persistence to avoid collisions across restart; Phase 1 has no persistence (ADR-ARCH-008).
4. **Allow `session_id ≠ thread_id` with an explicit mapping table.** *(Rejected)* — adds a concept for no current benefit. If FEAT-JARVIS-006 Telegram needs Telegram-conversation-level thread persistence that outlives a session, the mapping relaxes then, not now.

## Consequences

- Tests assert `session.thread_id == session.session_id` after `start_session`.
- Memory Store key scheme is session-agnostic (keyed by `user_id` — see DDR-002), so the 1:1 constraint does not leak into the recall path.
- Future relaxation (FEAT-JARVIS-003 / 006 may want 1:N) is a design-doc + test change — nothing persistent depends on 1:1 behaviour.
- The `Session` Pydantic model still exposes `thread_id` as a separate field rather than a computed property — future features that need to diverge can set it independently without breaking the schema.

## Related

- [DM-jarvis-reasoning.md §1.1](../models/DM-jarvis-reasoning.md) — `Session` schema
- [DDR-002-memory-store-keyed-by-user-id.md](DDR-002-memory-store-keyed-by-user-id.md)
- [ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md)
