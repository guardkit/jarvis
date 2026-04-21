# Data Model — Jarvis Reasoning Context (Phase 1 slice)

**Feature:** FEAT-JARVIS-001
**Bounded context:** Jarvis Reasoning Context
**Scope:** Phase 1 slice only — `Session` aggregate, `Adapter` enum, `AppState` composite, exception hierarchy. Other aggregates in this context (`RoutingDecision`, `SkillInvocation`) ship with later features.
**Version:** 0.1.0
**Status:** Proposed

---

## 1. Entities

### 1.1 `Session` (aggregate root)

```python
from datetime import datetime
from uuid import uuid4
from pydantic import BaseModel, Field
from jarvis.shared.constants import Adapter

class Session(BaseModel):
    session_id: str = Field(
        description="Identity: '{adapter}-{uuid4.hex[:12]}'. Stable for the lifetime of the session.",
    )
    adapter: Adapter = Field(
        description="Which adapter minted this session. Phase 1: Adapter.CLI only.",
    )
    user_id: str = Field(
        description="Stable identifier for the human operator. Phase 1: 'rich' (single-user).",
    )
    thread_id: str = Field(
        description="LangGraph thread identity. Phase 1: equals session_id (1:1 — see DDR-004).",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Session creation instant (UTC).",
    )
    ended_at: datetime | None = Field(
        default=None,
        description="Set on end_session; None while live.",
    )
    correlation_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Carried through logs + (future) NATS dispatches for trace-richness.",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Adapter-specific extensions. Phase 1: unused. Reserved for FEAT-JARVIS-006 Telegram chat_id, etc.",
    )

    model_config = {"frozen": False, "extra": "forbid"}
```

**Identity:** `(adapter, session_id)` tuple is globally unique. `session_id` alone is unique in practice because of the adapter prefix.

**Lifecycle states (implicit — not a state machine field in Phase 1):**
- **LIVE** — created by `start_session`, `ended_at is None`.
- **ENDED** — `end_session` was called, `ended_at` is set.

No PROPOSED or FAILED states — sessions are created eagerly and fail only at session-start validation (raises before the `Session` exists).

### 1.2 `Adapter` (enum)

```python
from enum import Enum

class Adapter(str, Enum):
    CLI = "cli"
    TELEGRAM = "telegram"    # reserved — FEAT-JARVIS-006
    DASHBOARD = "dashboard"  # reserved — FEAT-JARVIS-009
    REACHY = "reachy"        # reserved — FEAT-JARVIS-009
```

Values are stable — used as prefixes in `session_id`, NATS topic names (future), and trace records. Changing a value breaks historical trace continuity.

### 1.3 `AppState` (composite, not a domain entity)

```python
from dataclasses import dataclass
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from jarvis.config import JarvisConfig
from jarvis.sessions import SessionManager

@dataclass
class AppState:
    config: JarvisConfig
    supervisor: CompiledStateGraph
    store: BaseStore
    session_manager: SessionManager
```

Lives in `jarvis.infrastructure.lifecycle`. Carried through the CLI command handlers. Additive across features — FEAT-JARVIS-004 adds `nats_client: NatsClient`, FEAT-JARVIS-008 adds `graphiti_adapter: GraphitiAdapter`, and so on.

### 1.4 Exception hierarchy

```python
class JarvisError(Exception):
    """Base for all Jarvis-specific errors."""

class ConfigurationError(JarvisError):
    """Config invalid or required key missing."""

class SessionNotFoundError(JarvisError):
    """resume_session or end_session called with unknown session_id."""
```

Additive-only across features. FEAT-JARVIS-004 will add `DispatchFailedError`, `WatcherDeadError`, etc.

---

## 2. Relationships

```
AppState
  ├── 1 --> 1 JarvisConfig
  ├── 1 --> 1 CompiledStateGraph
  ├── 1 --> 1 BaseStore
  └── 1 --> 1 SessionManager
                 └── 1 --> * Session  (held in an internal dict[session_id, Session])

Session
  └── 1 --> 1 Adapter (enum value)
```

No relationship between `Session` and `JarvisConfig` — sessions don't re-read config.

---

## 3. Invariants

1. **Session identity is immutable.** `session_id`, `adapter`, `user_id`, `thread_id`, `started_at`, `correlation_id` never change after construction.
2. **`thread_id == session_id`** in Phase 1. [DDR-004](../decisions/DDR-004-session-thread-1to1.md) records the rationale. If FEAT-JARVIS-006 needs to diverge (e.g. persistent Telegram threads), the invariant relaxes — but Phase 1 asserts 1:1.
3. **`ended_at is None` iff the session is LIVE.** `end_session` is idempotent — calling it twice does not raise; the second call is a no-op.
4. **`Session.user_id` is the only Memory Store key input.** `session_id` is never used as a Memory Store namespace element — this is the cross-session-recall invariant required by [ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md).
5. **`correlation_id` is fresh per session.** Not shared across sessions even for the same user — each session's trace is self-contained.
6. **`adapter = Adapter.CLI` is the only permitted value in Phase 1.** Enforced by the CLI being the only caller of `start_session`. Tests that construct `Session` directly may use other values for schema exercise but `SessionManager.start_session` rejects them via an assertion until the corresponding adapter feature ships.

---

## 4. Domain events (Phase 1 emissions — structlog only)

| Event | Emitted by | Fields | Transport |
|---|---|---|---|
| `SessionStarted` | `SessionManager.start_session` | `session_id`, `adapter`, `user_id`, `started_at`, `correlation_id` | structlog `event="session.started"` |
| `SessionEnded` | `SessionManager.end_session` | `session_id`, `adapter`, `user_id`, `ended_at`, `duration_ms`, `turn_count`, `correlation_id` | structlog `event="session.ended"` |
| `InvokeCompleted` | `SessionManager.invoke` | `session_id`, `correlation_id`, `input_tokens`, `output_tokens`, `duration_ms` | structlog `event="invoke.completed"` |
| `InvokeFailed` | `SessionManager.invoke` exception path | `session_id`, `correlation_id`, `error_type`, `error_message` | structlog `event="invoke.failed"` |

**Not yet emitted in Phase 1** (arrives with FEAT-JARVIS-004): `RoutingDecisionMade`, `DispatchRequested`, `DispatchResultReceived`, `NotificationEmitted`, `UserRedirected`. The `Session` fields needed to support these events (`correlation_id`) are already present — Phase 1 commits to the *schema shape* per [ADR-ARCH-020](../../../architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md).

---

## 5. Persistence

| Store | What | Durability |
|---|---|---|
| `SessionManager._sessions: dict[str, Session]` | Live `Session` objects | In-process only. Lost on supervisor restart. (ADR-ARCH-008 — no SQLite in v1.) |
| LangGraph `InMemoryStore` (Phase 1 default) | Memory Store facts, keyed `("user", user_id)` + fact key | In-process only. v1.5 graduates to file-backed; v2 to Graphiti-backed. |
| LangGraph thread state | Per-`thread_id` conversation messages, managed by DeepAgents | In-process only. No checkpointer (ADR-ARCH-008). |

**Deliberate gap:** no durable session registry. A Jarvis restart loses all LIVE sessions — the user notices and reconnects. This is acceptable for Phase 1's single-user, local-only posture and matches [ADR-ARCH-008](../../../architecture/decisions/ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md) ("active sessions are re-initiated if the supervisor restarts").

---

## 6. Validation rules (enforced in `Session` Pydantic model + `SessionManager`)

| Rule | Enforced by | Failure mode |
|---|---|---|
| `session_id` matches `r"^(cli\|telegram\|dashboard\|reachy)-[0-9a-f]{12}$"` | `Session` field validator | `ValidationError` |
| `adapter == Adapter.CLI` in Phase 1 | `SessionManager.start_session` | `AssertionError` → wrapped in `JarvisError` |
| `user_id` non-empty string | `Session` field validator | `ValidationError` |
| `thread_id == session_id` | `SessionManager.start_session` construction step | Internal invariant; not user-triggerable |
| `resume_session(unknown_id)` raises | `SessionManager.resume_session` | `SessionNotFoundError` |

---

## 7. Test coverage surface

Exercised in `tests/test_sessions.py`:

- `Session` constructs from valid inputs; invalid `session_id` formats fail `ValidationError`.
- `SessionManager.start_session(Adapter.CLI, "rich")` returns a `Session`; `session_id` matches the pattern; `thread_id == session_id`.
- Two successive `start_session` calls return different `session_id`s.
- `resume_session(session.session_id)` returns the same object.
- `resume_session("bogus")` raises `SessionNotFoundError`.
- `end_session(session.session_id)` sets `ended_at`; second call is a no-op.
- `invoke(session, "my DDD Southwest talk is 16 May")` then, in a new session (same user), `invoke(session2, "when is my DDD talk?")` — response contains "16 May" via Memory Store recall.
- `start_session(Adapter.TELEGRAM, "rich")` fails until FEAT-JARVIS-006 lifts the gate.

---

## 8. Non-goals for Phase 1

- **No `RoutingDecision` model.** Arrives FEAT-JARVIS-002 (dispatch tools capture routing reasoning).
- **No `SkillInvocation` model.** Arrives FEAT-JARVIS-007.
- **No `Watcher` / `CalibrationAdjustment`.** Different bounded contexts, later features.
- **No persistent session registry.** ADR-ARCH-008 defers this.
- **No trace-richness writes to Graphiti.** FEAT-JARVIS-004 lights up `jarvis_routing_history`. Phase 1 emits structlog-only.

---

## 9. Related

- [API-internal.md](../contracts/API-internal.md) — public surface of these types
- [DDR-002-memory-store-keyed-by-user-id.md](../decisions/DDR-002-memory-store-keyed-by-user-id.md)
- [DDR-004-session-thread-1to1.md](../decisions/DDR-004-session-thread-1to1.md)
- [ADR-ARCH-005](../../../architecture/decisions/ADR-ARCH-005-seven-bounded-contexts.md) — bounded context definition
- [ADR-ARCH-008](../../../architecture/decisions/ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md)
- [ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md)
- [ADR-ARCH-020](../../../architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md)
- [ADR-ARCH-021](../../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md)
- [domain-model.md §1.2](../../../architecture/domain-model.md)
