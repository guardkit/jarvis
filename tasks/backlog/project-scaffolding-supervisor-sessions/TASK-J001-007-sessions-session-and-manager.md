---
id: TASK-J001-007
title: "sessions/ \u2014 Session model + SessionManager (thread-per-session, user-keyed\
  \ Memory Store, concurrent-invoke refusal)"
task_type: feature
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 4
implementation_mode: task-work
complexity: 8
dependencies:
- TASK-J001-005
- TASK-J001-006
status: in_review
tags:
- feature
- sessions
- memory-store
- thread-per-session
- concurrency
- adr-arch-009
- ddr-002
- ddr-004
consumer_context:
- task: TASK-J001-006
  consumes: COMPILED_SUPERVISOR_GRAPH
  framework: LangGraph CompiledStateGraph (DeepAgents-produced)
  driver: langgraph.store.BaseStore
  format_note: 'SessionManager.invoke MUST pass config={''configurable'': {''thread_id'':
    session.thread_id}} AND store=self._store to supervisor.ainvoke; Memory Store
    namespace MUST be (''user'', user_id) with NO session_id segment (DDR-002)'
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T22:59:22.086481'
  last_updated: '2026-04-21T23:09:02.135737'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-21T22:59:22.086481'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: `src/jarvis/sessions/` — `Session` + `SessionManager`

The stable primitive every adapter extends. Thread-per-session 1:1 (DDR-004), user-keyed Memory Store (DDR-002), single-threaded invoke contract in Phase 1 (ASSUM-003).

## Context

- [ADR-ARCH-009 thread-per-session + Memory Store](../../../docs/architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md)
- [DDR-002 Memory Store keyed by user_id](../../../docs/design/FEAT-JARVIS-001/decisions/DDR-002-memory-store-keyed-by-user-id.md) (referenced)
- [DDR-004 session/thread 1:1](../../../docs/design/FEAT-JARVIS-001/decisions/DDR-004-session-thread-1to1.md) (referenced)
- [DM-jarvis-reasoning.md](../../../docs/design/FEAT-JARVIS-001/models/DM-jarvis-reasoning.md) — `Session` field shape
- ASSUM-003, ASSUM-006 — pinned behaviours

## Scope

**Files (NEW):**

- `src/jarvis/sessions/__init__.py`
- `src/jarvis/sessions/session.py` — `Session(BaseModel)`:
  - `session_id: str` (adapter-prefixed pattern — e.g. `cli-01HA...`)
  - `adapter: Adapter`
  - `user_id: str`
  - `thread_id: str` (= `session_id` per DDR-004 in Phase 1)
  - `started_at: datetime`
  - `correlation_id: str` (ULID; reserved for FEAT-004 trace-richness per ADR-ARCH-020)
  - `metadata: dict[str, Any] = {}`

- `src/jarvis/sessions/manager.py` — `SessionManager`:
  - `__init__(supervisor: CompiledStateGraph, store: BaseStore)` — dependency-injected
  - `start_session(adapter: Adapter, user_id: str) -> Session`:
    - Refuses non-CLI adapters in Phase 1 with `JarvisError` (ASSUM-006)
    - Mints `session_id` (adapter-prefixed pattern)
    - Emits structured `SessionStarted` event
  - `resume_session(session_id: str) -> Session`:
    - Raises `SessionNotFoundError` if unknown (feature file @negative + @edge-case restart invariant)
  - `end_session(session_id: str) -> None`:
    - **Idempotent** — calling twice does not raise (feature file @boundary)
    - Emits `SessionEnded` exactly once
  - `async invoke(session: Session, user_input: str) -> str`:
    - Tracks in-flight invokes per `session_id` in an `asyncio.Lock` dict
    - Second concurrent invoke on the same session raises `JarvisError("Concurrent invoke refused ...")` (ASSUM-003) — **not** `await`ing the existing lock
    - Blank-line input (`user_input.strip() == ""`) returns early with empty string; no supervisor call (ASSUM-001) — **or** caller handles in REPL (TASK-J001-008). Pin the decision in the task once: REPL handles blank-line skip; `invoke` trusts caller. See Implementation Notes.
    - Calls `await self._supervisor.ainvoke({"messages": [HumanMessage(user_input)]}, config={"configurable": {"thread_id": session.thread_id}}, store=self._store)`
    - Returns `result["messages"][-1].content`
    - Provider errors propagate (REPL prefixes `[error]` — TASK-J001-008's concern)

## Implementation Notes

- **Blank-line handling:** per feature file @boundary "empty chat turn", pin the skip at the **REPL** layer (TASK-J001-008), not here. `SessionManager.invoke` assumes input is non-empty; behaviour on empty input is undefined/untested. REPL tests cover the scenario.
- **Memory Store write key:** when the supervisor writes a fact, it writes to namespace `("user", session.user_id)`. This is DDR-002 — no session_id segment. The @security cross-user-isolation scenario keys off this.
- **`thread_id == session_id`** in Phase 1 per DDR-004. Do not introduce a second identifier.

## Acceptance Criteria

- `SessionManager(supervisor, store)` constructs without side-effects.
- `start_session(Adapter.CLI, "rich")` returns a `Session` with distinct `session_id` / `thread_id` (== each other), `started_at` current UTC, and emits a `SessionStarted` structured log event.
- `start_session(Adapter.TELEGRAM|DASHBOARD|REACHY, ...)` raises `JarvisError` naming the adapter (ASSUM-006).
- Two successive `start_session` calls for the same `user_id` return distinct `session_id` values (feature file @boundary).
- `resume_session("unknown")` raises `SessionNotFoundError`.
- `end_session(sid); end_session(sid)` both succeed; session marked ended exactly once.
- `invoke(session, "hello")` with `fake_llm` returns canned text and writes to Memory Store under `("user", user_id)` namespace (no session_id segment).
- Concurrent `invoke` on the same session (second call issued before first awaits) raises `JarvisError` with a clear message (ASSUM-003).
- Cross-session recall test: session A writes fact → session B for same `user_id` reads fact (day-1 criterion, @key-example @smoke).
- Cross-user isolation test: user A's fact not returned for user B (@edge-case @security).
- All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

- Coach verifies `SessionManager.invoke` passes **both** `config={"configurable": {"thread_id": ...}}` AND `store=self._store` to `supervisor.ainvoke` (both required for Memory Store recall to work).
- Coach greps for any construction of a Memory Store key containing a `session_id` — none must appear (DDR-002 invariant).
- Coach verifies the concurrent-invoke check is implemented as "refuse" (raise immediately), not "serialise" (await) — ASSUM-003.

## Seam Tests

```python
"""Seam test: verify COMPILED_SUPERVISOR_GRAPH contract from TASK-J001-006."""
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.store.memory import InMemoryStore

from jarvis.agents.supervisor import build_supervisor
from jarvis.sessions.manager import SessionManager
from jarvis.shared.constants import Adapter


@pytest.mark.seam
@pytest.mark.integration_contract("COMPILED_SUPERVISOR_GRAPH")
async def test_compiled_supervisor_graph_contract(test_config, fake_llm, monkeypatch):
    """Verify SessionManager invokes supervisor with thread_id config AND store kwarg.

    Contract: SessionManager.invoke MUST pass config={'configurable': {'thread_id': session.thread_id}}
    AND store=self._store to supervisor.ainvoke. Memory Store namespace MUST be ('user', user_id)
    with NO session_id segment.
    Producer: TASK-J001-006
    """
    # Producer side: real build_supervisor (patched to use fake_llm internally)
    monkeypatch.setattr("jarvis.agents.supervisor.init_chat_model", lambda _: fake_llm)
    supervisor = build_supervisor(test_config)
    store = InMemoryStore()
    mgr = SessionManager(supervisor, store)

    # Consumer side: start and invoke
    session = mgr.start_session(Adapter.CLI, "rich")
    reply = await mgr.invoke(session, "hello")

    # Assertion 1: thread_id equals session_id (DDR-004)
    assert session.thread_id == session.session_id

    # Assertion 2: any keys written to the store under this user use ('user', 'rich') namespace
    # (no session_id segment; DDR-002)
    for namespace, _, _ in store.search(("user", "rich"), limit=10):
        assert session.session_id not in namespace, (
            f"Memory Store namespace must not contain session_id; got {namespace}"
        )
```
