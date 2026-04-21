# API Contract — Internal Python API

**Feature:** FEAT-JARVIS-001
**Bounded context:** Jarvis Reasoning Context + Config (cross-cutting)
**Protocol:** in-process Python (no network surface in Phase 1)
**Consumers:** `jarvis.cli.main`, `tests/`, and future FEAT-JARVIS-002..007 code
**Version:** 0.1.0
**Status:** Proposed

---

## 1. Overview

Phase 1 exposes **no network protocols** — not REST, not GraphQL, not MCP, not A2A, not NATS events. All external surfaces arrive in later features ([phase1-build-plan.md Do-Not-Change](../../../research/ideas/phase1-build-plan.md) rule 9). This contract documents the **in-process Python API** between the eight `src/jarvis/` layer modules so FEAT-JARVIS-002..007 consumers know what to import and what's stable.

See [DDR-001-internal-api-in-process-only.md](../decisions/DDR-001-internal-api-in-process-only.md) for the protocol-omission rationale.

---

## 2. Module boundaries (consistent with ADR-ARCH-006)

| Group | Module | May import from | Must not import from |
|---|---|---|---|
| A. Shell | `jarvis.agents` | B, E, `prompts` | C, D |
| A. Shell | `jarvis.prompts` | — (string constants only) | anything |
| A. Shell | `jarvis.subagents` *(reserved, empty)* | — | — |
| A. Shell | `jarvis.skills` *(reserved, empty)* | — | — |
| B. Domain | `jarvis.sessions` | `jarvis.shared`, LangGraph types | C, D, `jarvis.agents` |
| B. Domain | `jarvis.routing` / `watchers` / `learning` / `discovery` *(reserved, empty)* | `jarvis.shared` | C, D |
| C. Tools | `jarvis.tools` *(reserved, empty package)* | B, D | A.agents |
| D. Adapters | `jarvis.adapters` *(reserved, empty)* | `jarvis.shared`, external libs | A, B, C |
| E. Cross-cutting | `jarvis.config` | `jarvis.shared` | A, B, C, D |
| E. Cross-cutting | `jarvis.infrastructure` | E.config, `jarvis.shared` | A, B, C, D |
| E. Cross-cutting | `jarvis.cli` | everything | — |

**Invariant enforced by ruff:** domain modules (group B) may not import from adapters (group D) or tools (group C). Static check via `ruff isort` + custom boundary rule; violations fail `mypy --strict` too because type-level boundary is sealed by empty `__init__.py` markers in Phase 1.

---

## 3. Public API — `jarvis.agents`

### 3.1 `build_supervisor(config: JarvisConfig) -> CompiledStateGraph`

Constructs the DeepAgents supervisor. Pure factory — reads `config`, returns a compiled LangGraph. Does not mutate global state. Does not invoke the model.

```python
from langgraph.graph.state import CompiledStateGraph
from jarvis.config import JarvisConfig

def build_supervisor(config: JarvisConfig) -> CompiledStateGraph: ...
```

**Input:** validated `JarvisConfig`.
**Output:** `CompiledStateGraph` produced by `deepagents.create_deep_agent(...)`.

**Guarantees:**
- Uses `create_deep_agent` (not `create_agent`) — matches Forge ADR-ARCH-020 and [ADR-ARCH-002](../../../architecture/decisions/ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md).
- Model wired via `init_chat_model(config.supervisor_model)`; base URL supplied by env (`OPENAI_BASE_URL` for llama-swap).
- Enabled built-ins: `write_todos`, virtual filesystem, `task`.
- Disabled built-ins: `execute` (no shell in Phase 1), `interrupt` (no approval gates yet — FEAT-JARVIS-008).
- System prompt: `jarvis.prompts.supervisor_prompt.SUPERVISOR_SYSTEM_PROMPT`.
- No subagents (FEAT-JARVIS-003 appends).
- No custom `@tool` functions (FEAT-JARVIS-002 appends).
- Memory Store hook accepted but store itself is passed per-invoke via `SessionManager` — factory does not own the store.

**Raises:** `ConfigurationError` if `config.supervisor_model` is malformed or the provider key required by the model prefix is missing. Never raises from within DeepAgents (per [ADR-ARCH-021](../../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md) — but this is a build-time failure, not a runtime one).

---

## 4. Public API — `jarvis.sessions`

### 4.1 `Session` (Pydantic `BaseModel`)

Aggregate root of the Jarvis Reasoning Context. See [DM-jarvis-reasoning.md](../models/DM-jarvis-reasoning.md) for the full schema.

Identity: tuple `(adapter, session_id)`.

### 4.2 `SessionManager`

```python
class SessionManager:
    def __init__(
        self,
        supervisor: CompiledStateGraph,
        store: BaseStore,
    ) -> None: ...

    def start_session(self, adapter: Adapter, user_id: str) -> Session: ...
    def resume_session(self, session_id: str) -> Session: ...
    def end_session(self, session_id: str) -> None: ...

    async def invoke(self, session: Session, user_input: str) -> str: ...
```

**Lifecycle:**

- `start_session(adapter, user_id)` — mints a fresh `Session`. `session_id = f"{adapter.value}-{uuid4().hex[:12]}"` (DDR-004 recommendation (a)). `thread_id = session_id` (1:1 mapping — see [DDR-004-session-thread-1to1.md](../decisions/DDR-004-session-thread-1to1.md)). Emits `SessionStarted` structlog event.
- `resume_session(session_id)` — looks up an existing in-memory `Session`. Raises `SessionNotFoundError` if not found. *Phase 1 sessions are in-memory only — a Jarvis restart invalidates all sessions (acceptable per [ADR-ARCH-008](../../../architecture/decisions/ADR-ARCH-008-no-sqlite-graphiti-and-memory-store-sufficient.md) — no checkpointer in v1).*
- `end_session(session_id)` — marks the session ended, flushes any pending Memory Store writes, emits `SessionEnded`. Idempotent.
- `invoke(session, user_input)` — runs the supervisor on `session.thread_id` with the Memory Store scoped to `session.user_id`:

```python
config = {"configurable": {"thread_id": session.thread_id}}
result = await self._supervisor.ainvoke(
    {"messages": [HumanMessage(user_input)]},
    config=config,
    store=self._store,
)
return result["messages"][-1].content
```

**Memory Store scope:** namespace `("user", user_id)` — keyed per user, not per session. This means facts stated in session A (same user) are recallable in session B across adapters (Phase 1 is CLI-only, but the contract is shaped for FEAT-JARVIS-006 Telegram). See [DDR-002-memory-store-keyed-by-user-id.md](../decisions/DDR-002-memory-store-keyed-by-user-id.md).

**Concurrency:** `invoke` is `async`, but `SessionManager` itself is not thread-safe — Phase 1 CLI runs a single asyncio loop and one session at a time. FEAT-JARVIS-006 Telegram will need to revisit if concurrent sessions arrive.

**Error semantics:**
- Provider errors during `invoke` → logged + re-raised as `JarvisError`. The CLI catches and prints `[error] {message}`; the REPL continues.
- Missing session → `SessionNotFoundError`.
- Per [ADR-ARCH-021](../../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md), tool-layer errors return structured strings; `SessionManager` is not a tool but participates in the same discipline for lower-level errors propagated up.

---

## 5. Public API — `jarvis.config`

### 5.1 `JarvisConfig` (pydantic-settings `BaseSettings`)

See [DM-config.md](../models/DM-config.md) for the full schema.

```python
class JarvisConfig(BaseSettings):
    log_level: str = "INFO"
    supervisor_model: str = "openai:jarvis-reasoner"
    memory_store_backend: Literal["in_memory", "file", "graphiti"] = "in_memory"
    data_dir: Path = Path.home() / ".jarvis"

    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def validate_provider_keys(self) -> None:
        """Raise ConfigurationError if the selected model lacks its provider key."""
```

Note: `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` bypass the `JARVIS_` prefix because `init_chat_model` reads them directly from the unprefixed env vars.

**Construction:** `JarvisConfig()` loads from env. Pass explicitly to `build_supervisor` and `SessionManager.__init__` — no global singleton.

---

## 6. Public API — `jarvis.infrastructure`

### 6.1 `lifecycle.startup(config) -> AppState`

```python
@dataclass
class AppState:
    config: JarvisConfig
    supervisor: CompiledStateGraph
    store: BaseStore
    session_manager: SessionManager

async def startup(config: JarvisConfig) -> AppState: ...
async def shutdown(state: AppState) -> None: ...
```

`startup` orders the wiring: configure logging → validate config → build supervisor → instantiate store (per `config.memory_store_backend`; Phase 1 only supports `in_memory`) → wire `SessionManager`. Returns the application state.

`shutdown` cancels outstanding sessions, flushes store writes, logs a clean shutdown message. Hooked to `SIGINT`/`SIGTERM` by `jarvis.cli.main`.

### 6.2 `logging.configure(level)`

Initialises `structlog` with:
- JSON renderer when stderr is not a TTY (CI, log aggregation)
- Console renderer when stderr is a TTY (interactive `jarvis chat`)
- Processors: `TimeStamper(fmt="iso")`, `add_log_level`, `StackInfoRenderer`, `format_exc_info`

Redaction processor strips secret-suffixed keys (`*_key`, `*_token`) per [agent-manifest-contract](../../../../../nats-core/docs/design/contracts/agent-manifest-contract.md) secret-handling rule.

---

## 7. Shared types — `jarvis.shared`

```python
# constants.py
__version__ = "0.1.0"
VERSION: Final[str] = __version__

class Adapter(str, Enum):
    CLI = "cli"
    TELEGRAM = "telegram"   # reserved, not used Phase 1
    DASHBOARD = "dashboard" # reserved
    REACHY = "reachy"       # reserved

# exceptions.py
class JarvisError(Exception): ...
class ConfigurationError(JarvisError): ...
class SessionNotFoundError(JarvisError): ...
```

Safe-to-import-from-anywhere tier. No dependencies on supervisor, sessions, config, or I/O.

---

## 8. Stability guarantees

| API | Stability | Rationale |
|---|---|---|
| `build_supervisor(config)` signature | **Stable** across v1 | Downstream features only add to config; signature stays |
| `SessionManager.{start,resume,end,invoke}` signatures | **Stable** across v1 | Adapter surfaces + NATS wiring layer above, not inside |
| `Session` field names | **Stable** | FEAT-JARVIS-004 will add `routing_priors_applied` etc.; additive only |
| `JarvisConfig` field names | **Stable**; additive | Each new feature adds fields; nothing renamed |
| `Adapter` enum values | **Stable** | Used in NATS topic names (FEAT-JARVIS-006); changing a value breaks trace continuity |
| `AppState` fields | **Additive** | New sub-systems (NATS client, Graphiti client) slot in as new fields |
| Exception hierarchy | **Additive** | New error subtypes only; never rename or reparent |

---

## 9. Non-goals for Phase 1

- **No network protocols.** REST/GraphQL/MCP/A2A/ACP are not applicable — see DDR-001.
- **No NATS emission** — `SessionStarted`/`SessionEnded`/`RoutingDecisionMade` events exist only as structlog trace records until FEAT-JARVIS-004 lights up the Graphiti writer.
- **No interrupt-based approvals** — the DeepAgents `interrupt` primitive is disabled in Phase 1; approval round-trips (`ApprovalRequestPayload`) arrive with FEAT-JARVIS-008 at the earliest.
- **No `ainvoke`-streaming** — Phase 1 returns whole responses. Streaming can be added per-adapter without changing this contract.

---

## 10. Related

- [API-cli.md](API-cli.md) — the consumer of this API
- [DM-jarvis-reasoning.md](../models/DM-jarvis-reasoning.md) — Session, Adapter, AppState schemas
- [DM-config.md](../models/DM-config.md) — JarvisConfig schema
- [ADR-ARCH-002](../../../architecture/decisions/ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md) — Clean/Hexagonal boundary
- [ADR-ARCH-006](../../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md) — Module groupings
- [ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md) — Thread-per-session + Memory Store
- [ADR-ARCH-010](../../../architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md) — Python + DeepAgents pin
- [ADR-ARCH-011](../../../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md) — Single reasoner; llama-swap aliases
