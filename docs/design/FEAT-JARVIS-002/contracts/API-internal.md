# API-internal — Module-Level Python API

> **Surface:** in-process module contracts between `jarvis.tools.*`, `jarvis.agents.supervisor`, `jarvis.config`, and `jarvis.infrastructure.lifecycle`.
> **Consumer:** application code under `src/jarvis/` and the FEAT-JARVIS-002 test suite. Nothing is exposed over the network.

---

## 1. `jarvis.tools` package

```
src/jarvis/tools/
├── __init__.py      # re-exports tool functions + CapabilityDescriptor + WebResult + CalendarEvent + assemble_tool_list
├── types.py         # Pydantic models
├── general.py       # 4 @tool functions
├── capabilities.py  # 3 @tool functions + CapabilityDescriptor + stub registry loader
└── dispatch.py      # 2 @tool functions + stub hook + payload builders
```

### 1.1 Public re-exports from `jarvis.tools`

```python
from jarvis.tools import (
    # Pydantic types
    CapabilityDescriptor,
    WebResult,
    CalendarEvent,
    DispatchError,
    # General tools
    read_file,
    search_web,
    get_calendar_events,
    calculate,
    # Capability catalogue tools
    list_available_capabilities,
    capabilities_refresh,
    capabilities_subscribe_updates,
    # Dispatch tools
    dispatch_by_capability,
    queue_build,
    # Assembly
    assemble_tool_list,
    load_stub_registry,
)
```

No sub-module is ever imported outside `jarvis.tools.*` and the tests; the package `__init__.py` is the stable surface.

---

### 1.2 `assemble_tool_list(...)`

```python
def assemble_tool_list(
    config: JarvisConfig,
    capability_registry: list[CapabilityDescriptor],
) -> list[BaseTool]: ...
```

Returns the 9 FEAT-JARVIS-002 tools in stable alphabetical order. Responsible for:

- Binding `search_web` to the configured provider (Tavily).
- Binding capability tools to the supplied `capability_registry` snapshot.
- Binding dispatch tools to the capability registry (for resolution) and to the Phase 2 stub hook.

This is the ONE place that knows how to wire tool-level state. Tests can substitute a fake registry or fake provider by calling this function with a doctored `config` / registry.

---

### 1.3 `load_stub_registry(path: Path) -> list[CapabilityDescriptor]`

Loads the Phase 2 in-memory stub from the YAML file at `path` (default: `config.stub_capabilities_path`). Validates every entry as a `CapabilityDescriptor`. Returns the descriptors as a list.

- Raises `FileNotFoundError` if the path is missing (startup-fatal per [FEAT-JARVIS-001 JarvisConfig](../../FEAT-JARVIS-001/models/DM-config.md) conventions — this is a config boundary, not a tool boundary).
- Raises `pydantic.ValidationError` if the YAML is malformed (startup-fatal).

This loader is removed in FEAT-JARVIS-004 when real `NATSKVManifestRegistry` reads replace the stub.

---

## 2. `jarvis.agents.supervisor`

Phase 1 signature:

```python
def build_supervisor(config: JarvisConfig) -> CompiledStateGraph[Any, Any, Any, Any]: ...
```

Phase 2 signature (keyword-only additions; backward compatible — callers without kwargs still work):

```python
def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,
    available_capabilities: list[CapabilityDescriptor] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """
    tools:
      None -> [] (Phase 1 behaviour preserved)
      list -> passed verbatim to create_deep_agent(tools=...)

    available_capabilities:
      None -> "No capabilities currently registered." rendered into {available_capabilities}
      list -> render each descriptor via CapabilityDescriptor.as_prompt_block()
              (deterministic ordering by agent_id) and join with "\\n\\n".
              Rendered text replaces {available_capabilities} in the prompt.
    """
```

The rendering step happens inside `build_supervisor` (one place, one format) so tests can assert on the rendered prompt deterministically.

---

## 3. `jarvis.prompts.supervisor_prompt`

New placeholder `{available_capabilities}` inserted **after** the Phase 1 attended-conversation section and **before** the trace-richness section. The domain-specific block still lives at the bottom of the prompt per Phase 1 invariants.

Prompt-injection is the only change to the prompt module in Phase 2 besides the Tool Usage section (design §10). The scope-invariant TASK-J001-004 (no mention of `call_specialist`, `queue_build`, named subagents, skills) is satisfied because:

- `dispatch_by_capability` and `queue_build` are discussed under **"## Tool Usage"** without naming specific specialists.
- The `{available_capabilities}` section is *injected* from the registry — its content varies by deployment, not hard-coded.
- No subagent names appear.
- No skills are referenced.

---

## 4. `jarvis.config.settings`

Phase 2 adds three fields to `JarvisConfig`:

| Field | Type | Default | Env var |
|---|---|---|---|
| `web_search_provider` | `Literal["tavily", "none"]` | `"tavily"` | `JARVIS_WEB_SEARCH_PROVIDER` |
| `tavily_api_key` | `SecretStr \| None` | `None` | `JARVIS_TAVILY_API_KEY` |
| `stub_capabilities_path` | `Path` | `Path("src/jarvis/config/stub_capabilities.yaml")` | `JARVIS_STUB_CAPABILITIES_PATH` |
| `workspace_root` | `Path` | `Path(".")` resolved absolute | `JARVIS_WORKSPACE_ROOT` |

`validate_provider_keys()` is extended to emit a warning (not a fatal error) when `web_search_provider == "tavily"` but `tavily_api_key is None` — the `search_web` tool returns a structured error at call time per ADR-ARCH-021.

Removed keys: none. Phase 1 config is fully preserved.

---

## 5. `jarvis.infrastructure.lifecycle`

`lifecycle.startup(config)` grows two steps before `build_supervisor(...)`:

```python
capability_registry = load_stub_registry(config.stub_capabilities_path)
tool_list = assemble_tool_list(config, capability_registry)
```

`AppState` gains one new field (`capability_registry: list[CapabilityDescriptor]`). All other existing `AppState` fields retain their Phase 1 shape.

---

## 6. `jarvis.shared.exceptions`

No additions in Phase 2 — tools use structured-string returns per ADR-ARCH-021, so the exception hierarchy stays as Phase 1 defined it.

---

## 7. Test fixtures

`tests/conftest.py` gains fixtures:

| Fixture | Scope | Purpose |
|---|---|---|
| `stub_capabilities_yaml_path(tmp_path)` | function | Writes a canonical 4-entry stub YAML into `tmp_path` and returns the path. |
| `capability_registry(stub_capabilities_yaml_path)` | function | Loads the fixture YAML → `list[CapabilityDescriptor]`. |
| `fake_tavily_response(monkeypatch)` | function | Monkeypatches the Tavily client to return 5 canned `WebResult` dicts. |
| `fake_dispatch_stub(monkeypatch)` | function | Sets `jarvis.tools.dispatch._stub_response_hook` to a test-configurable behaviour (success / timeout / specialist_error). |

Existing Phase 1 fixtures (`fake_llm`, `test_config`, `in_memory_store`) are reused unchanged.
