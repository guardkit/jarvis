# API Contract — FEAT-JARVIS-003 Internal Python API

> **Feature:** FEAT-JARVIS-003
> **Surface type:** In-process Python module API (module-level functions, classes, enums)
> **Protocol:** Direct Python import — consumed by sibling modules and tests
> **Stability:** Semver-like — breaking changes require a DDR
> **Generated:** 2026-04-23

---

## `jarvis.agents.subagent_registry`

### `build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]`

Returns the list of `AsyncSubAgent` instances to wire into the supervisor. v1 returns a single-element list (per [DDR-010](../decisions/DDR-010-single-async-subagent-supersedes-four-roster.md)). The `AsyncSubAgent` description reads from a module-level constant so it is testable without invoking the full factory.

Reads from `config`:
- No config fields required in v1 — the single subagent's model alias is static (`openai:jarvis-reasoner`).

Returns:
- A list with one `AsyncSubAgent(name="jarvis-reasoner", graph_id="jarvis_reasoner", description=...)`.

Raises:
- Nothing. Function is pure.

---

## `jarvis.agents.subagents.prompts`

### `class RoleName(str, Enum)`

Closed enum per [DDR-011](../decisions/DDR-011-role-enum-closed-v1.md):

```python
class RoleName(str, Enum):
    CRITIC = "critic"
    RESEARCHER = "researcher"
    PLANNER = "planner"
```

Members are stable; additions are permitted (non-breaking) with commit-message justification; removals/renames require a DDR.

### `ROLE_PROMPTS: Mapping[RoleName, str]`

Complete mapping from `RoleName` members to system prompt strings. Exhaustiveness asserted in `tests/test_subagent_prompts.py`:

```python
assert set(ROLE_PROMPTS.keys()) == set(RoleName)
```

Each prompt is non-empty and describes the role's posture. The subagent graph selects the system prompt at invocation time: `system_prompt = ROLE_PROMPTS[RoleName(input["role"])]`.

---

## `jarvis.agents.subagents.jarvis_reasoner`

### `graph: CompiledStateGraph[Any, Any, Any, Any]`

Module-level compiled graph per [DDR-012](../decisions/DDR-012-subagent-module-import-compilation.md). Referenced from the repo-root `langgraph.json` (per [DDR-013](../decisions/DDR-013-langgraph-json-at-repo-root.md)):

```json
"jarvis_reasoner": "./src/jarvis/agents/subagents/jarvis_reasoner.py:graph"
```

Compiled via:

```python
graph = create_deep_agent(
    model=init_chat_model("openai:jarvis-reasoner"),
    tools=[],                                      # leaf subagent, no further dispatch
    system_prompt=ROLE_PROMPTS[RoleName.PLANNER],  # default — overridden per invocation at node 0
    subagents=[],
)
```

The first node of the graph reads `input["role"]` and swaps the system prompt via a LangGraph state update; see DeepAgents 0.5.3 subagent-prompt-rebinding patterns.

### Import-time side effects

Importing this module:
- Calls `init_chat_model("openai:jarvis-reasoner")` — instantiates a chat-model object, **no network I/O**.
- Calls `create_deep_agent(...)` — builds a `CompiledStateGraph`, microseconds of CPU.
- Raises if `JARVIS_SUPERVISOR_MODEL` or `OPENAI_BASE_URL` is malformed.

Test harnesses set valid env vars via `conftest.py` fixtures before importing.

---

## `jarvis.adapters.llamaswap`

### `class SwapStatus(BaseModel)`

```python
class SwapStatus(BaseModel):
    loaded_model: str | None
    eta_seconds: int                   # ge=0
    source: Literal["live", "stub"] = "stub"
```

### `class LlamaSwapAdapterProtocol(Protocol)`

```python
class LlamaSwapAdapterProtocol(Protocol):
    def current_status(self, *, wanted_alias: str) -> SwapStatus: ...
```

### `class LlamaSwapAdapter(LlamaSwapAdapterProtocol)`

Phase 2 stub implementation per [DDR-015](../decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md):

```python
class LlamaSwapAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        stub_responses: dict[str, SwapStatus] | None = None,
    ) -> None:
        self._base_url = base_url
        self._stub_responses = stub_responses or {}

    def current_status(self, *, wanted_alias: str) -> SwapStatus:
        if wanted_alias in self._stub_responses:
            return self._stub_responses[wanted_alias]
        return SwapStatus(
            loaded_model=wanted_alias, eta_seconds=0, source="stub"
        )
```

FEAT-JARVIS-004 replaces the body with live HTTP reads against `{base_url}/running` + `{base_url}/log`.

---

## `jarvis.tools.dispatch` (extensions)

FEAT-JARVIS-002 shipped `dispatch_by_capability` and `queue_build`. FEAT-JARVIS-003 adds:

### `class FrontierTarget(str, Enum)`

```python
class FrontierTarget(str, Enum):
    GEMINI_3_1_PRO = "google_genai:gemini-3.1-pro"
    OPUS_4_7 = "anthropic:claude-opus-4-7"
```

### `ATTENDED_ADAPTERS: frozenset[Adapter]`

```python
ATTENDED_ADAPTERS: frozenset[Adapter] = frozenset({
    Adapter.TELEGRAM, Adapter.CLI, Adapter.DASHBOARD, Adapter.REACHY,
})
```

Used by `escalate_to_frontier`'s executor assertion (Layer 2 of DDR-014's three-layer gating).

### `escalate_to_frontier` (the `@tool`)

Full docstring in [API-tools.md §1](API-tools.md).

### Private helpers

- `_current_session() -> Session` — reads from `jarvis.sessions.manager` thread-local or equivalent; returns the active session for the current reasoning turn. Implementation detail; not part of the public tool surface.
- `_caller_is_async_subagent() -> bool` — inspects `AsyncSubAgentMiddleware` metadata if available, else returns `True` (fail-closed per DDR-014).

---

## `jarvis.agents.supervisor` (extended signature)

Phase 1 exposed:

```python
def build_supervisor(config: JarvisConfig) -> CompiledStateGraph: ...
```

FEAT-JARVIS-002 extended it:

```python
def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,
    available_capabilities: list[CapabilityDescriptor] | None = None,
) -> CompiledStateGraph: ...
```

FEAT-JARVIS-003 extends further:

```python
def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,
    available_capabilities: list[CapabilityDescriptor] | None = None,
    async_subagents: list[AsyncSubAgent] | None = None,         # ← NEW
    ambient_tool_factory: Callable[[], list[BaseTool]] | None = None,  # ← NEW
) -> CompiledStateGraph: ...
```

**Defaults preserve backwards compatibility:**
- `async_subagents=None` → no subagents wired (Phase 1 + FEAT-JARVIS-002 behaviour unchanged).
- `ambient_tool_factory=None` → ambient contexts fall back to the attended `tools` list **without** `escalate_to_frontier` (the factory strips it if present).

### Module-level `graph` export (DDR-013)

```python
# At module scope, for langgraph.json resolution:
graph = build_supervisor(JarvisConfig())
```

Test fixtures ensure `JarvisConfig()` is constructible in the test environment before this module is imported.

---

## `jarvis.infrastructure.lifecycle` (extended)

Phase 2 `assemble_tool_list(...)` gains a keyword argument:

```python
def assemble_tool_list(
    config: JarvisConfig,
    capability_registry: list[CapabilityDescriptor],
    llamaswap_adapter: LlamaSwapAdapterProtocol,
    *,
    include_frontier: bool,      # ← NEW in FEAT-JARVIS-003
) -> list[BaseTool]: ...
```

Called twice in `startup`:
- `assemble_tool_list(..., include_frontier=True)` → attended tool list
- `assemble_tool_list(..., include_frontier=False)` → ambient tool list (passed as `ambient_tool_factory=lambda: ...` to `build_supervisor`)

---

## `jarvis.config.settings` (extended)

New fields on `JarvisConfig`:

```python
# Group D adapter endpoint
llama_swap_base_url: str = "http://promaxgb10-41b1:9000"

# Frontier escalation
frontier_default_target: FrontierTarget = FrontierTarget.GEMINI_3_1_PRO
google_api_key: SecretStr | None = None         # already present from FEAT-JARVIS-001 scaffold
anthropic_api_key: SecretStr | None = None      # already present
```

`validate_provider_keys()` (Phase 1) gains an additional check: if `frontier_default_target` is set and the corresponding provider key is absent, `validate_provider_keys` does **not** raise — it defers to the tool's runtime structured-error path per ADR-ARCH-021. Jarvis starts up without a frontier key (the tool just fails gracefully when invoked).

---

## Stability policy

- **Public factories** (`build_async_subagents`, `build_supervisor` additions) — semver-like; new keyword arguments are non-breaking, removals require a DDR.
- **`RoleName` enum** — additive-only (DDR-011); removals/renames require a DDR and commit-message justification.
- **`SwapStatus` model** — additive-only per Pydantic 2 conventions.
- **`FrontierTarget` enum** — additive-only.
- **`ATTENDED_ADAPTERS` set** — matches `Adapter` enum members; changes track the `Adapter` enum directly.

---

## Traceability

- **ADR-ARCH-002** — clean/hexagonal; adapters + tools + agents cleanly separated
- **ADR-ARCH-005** — seven bounded contexts
- **ADR-ARCH-006** — five-group module layout (adapters/ populated here)
- **DDR-010/011/012/013/014/015** — this feature's six DDRs
