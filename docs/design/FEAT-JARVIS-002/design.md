# FEAT-JARVIS-002 — Design

> **Feature:** Core Tools & Capability-Driven Dispatch Tools
> **Phase:** 2 (Dispatch Foundations) — FEAT-JARVIS-002 only; FEAT-JARVIS-003 (async subagents) handled by a separate `/system-design` run.
> **Generated:** 2026-04-23 via `/system-design FEAT-JARVIS-002`
> **Status:** Proposed — input to `/feature-spec FEAT-JARVIS-002`
> **Architecture source:** [../../architecture/ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) (v1.0, 2026-04-20, 30 ADRs)
> **Scope source:** [../../research/ideas/phase2-dispatch-foundations-scope.md](../../research/ideas/phase2-dispatch-foundations-scope.md)
> **Predecessor design:** [../FEAT-JARVIS-001/design.md](../FEAT-JARVIS-001/design.md)

---

## 1. Purpose

FEAT-JARVIS-002 gives the Phase 1 supervisor its *dispatch vocabulary* — the first batch of custom `@tool(parse_docstring=True)` functions, and the first realisation of ADR-ARCH-003 (Jarvis-IS-the-GPA) + ADR-ARCH-015-equivalent capability-driven dispatch.

Three capability clusters ship in this feature, all as tools on the Phase 1 supervisor graph:

| Cluster | Tools | Transport in Phase 2 |
|---|---|---|
| **General** | `read_file`, `search_web`, `get_calendar_events`, `calculate` | real (filesystem / Tavily / stub / asteval) |
| **Capability catalogue** | `list_available_capabilities`, `capabilities_refresh`, `capabilities_subscribe_updates` | real read / no-op / no-op over **in-memory stub registry** |
| **Dispatch** | `dispatch_by_capability`, `queue_build` | **stubbed** — real `nats-core` payloads are built and logged; no network I/O |

The subagent-routing tools (`start_async_task`/`wait_for_async_tasks`/…) arrive with FEAT-JARVIS-003. `escalate_to_frontier` (ADR-ARCH-027) arrives later — its tool-module slot is reserved.

One-line success criterion: *the reasoning model can read the available capabilities and pick correctly across `calculate`, `read_file`, `search_web`, `dispatch_by_capability`, and `queue_build` — before any NATS transport is wired.*

## 2. Scope in-context

Jarvis has seven bounded contexts ([domain-model.md](../../architecture/domain-model.md)). FEAT-JARVIS-002 covers the first two of these; the remaining are untouched (or extended by later features).

| Bounded context | FEAT-JARVIS-002 touches? | How |
|---|---|---|
| **Fleet Dispatch Context** | **IN — core** | `dispatch_by_capability`, `queue_build`, capability catalogue reader |
| **External Tool Context** | **IN** | `read_file`, `search_web`, `get_calendar_events`, `calculate` |
| Jarvis Reasoning Context | extended only | supervisor prompt gains a tool-usage section; factory wires tools |
| Config (cross-cutting) | extended only | new keys for web-search provider + stub-registry path |
| Adapter Interface Context | untouched | CLI remains the only adapter |
| Ambient / Learning / Knowledge contexts | untouched | FEAT-JARVIS-003/004/007/008 territory |

See [phase2-dispatch-foundations-scope.md §Do-Not-Change](../../research/ideas/phase2-dispatch-foundations-scope.md) for the exclusion list Phase 2 preserves.

## 3. Surfaces shipped

| Surface | Type | Artefact |
|---|---|---|
| DeepAgents tool surface (9 `@tool` functions) | in-process — tool docstrings are the contract with the reasoning model | [contracts/API-tools.md](contracts/API-tools.md) |
| Internal Python API (module contracts) | in-process | [contracts/API-internal.md](contracts/API-internal.md) |

**No new network protocols** — consistent with [FEAT-JARVIS-001 DDR-001](../FEAT-JARVIS-001/decisions/DDR-001-internal-api-in-process-only.md). The dispatch tools build real `nats_core.events` payloads but the transport is stubbed — FEAT-JARVIS-004/005 add the network surface. Therefore this design produces no `openapi.yaml`, no `mcp-tools.json`, no `a2a-schemas.yaml`.

## 4. Data models

| Model | Purpose | Artefact |
|---|---|---|
| `CapabilityDescriptor`, `WebResult`, `CalendarEvent`, `DispatchError` | Tool-layer Pydantic types exposed to the reasoning model and shared across modules | [models/DM-tool-types.md](models/DM-tool-types.md) |
| Stub registry YAML schema | Format of `src/jarvis/config/stub_capabilities.yaml` (Phase-2-only; discarded when `NATSKVManifestRegistry` arrives) | [models/DM-stub-registry.md](models/DM-stub-registry.md) |
| Reused from `nats-core` | `CommandPayload`, `ResultPayload`, `BuildQueuedPayload`, `MessageEnvelope`, `EventType`, `Topics` | unchanged — imported directly. See [../../../nats-core/src/nats_core/events/_agent.py](../../../../nats-core/src/nats_core/events/_agent.py) and [_pipeline.py](../../../../nats-core/src/nats_core/events/_pipeline.py). |

## 5. Design decisions captured

| DDR | Decision | Why it's here |
|---|---|---|
| [DDR-005](decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md) | Dispatch tool name + signature is `dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60)`, superseding the Phase 2 scope doc's `call_specialist(agent_id, ...)` | Aligns with ADR-ARCH-003 / ADR-ARCH-016-equivalent (no `agent_id` hardcoding; fleet-is-the-catalogue). See Contradiction Detection §11 below. |
| [DDR-006](decisions/DDR-006-tavily-as-web-search-provider.md) | `search_web` uses Tavily as the v1 provider, wrapped so the provider can be swapped without changing the tool docstring | Scope doc left the provider open; Tavily is the specialist-agent default. |
| [DDR-007](decisions/DDR-007-asteval-for-calculate.md) | `calculate` uses `asteval` (AST-based, no `eval`) | Scope doc left the implementation open; asteval is maintained, small, and safe. |
| [DDR-008](decisions/DDR-008-capabilities-both-tool-and-prompt-injection.md) | Capabilities reach the supervisor via **both** a `@tool` call (`list_available_capabilities`) *and* prompt injection (`{available_capabilities}` placeholder in `SUPERVISOR_SYSTEM_PROMPT`, Phase-2-safe because prompt injection is also how ADR-ARCH-016 operates in Forge) | Resolves tension between scope doc's tool-based path and ARCHITECTURE.md §3.A's placeholder-based path. |
| [DDR-009](decisions/DDR-009-dispatch-stub-transport-semantics.md) | `dispatch_by_capability` stub: 60s timeout default (60s configurable via tool arg), no retry, structured-error return per ADR-ARCH-021. `queue_build` stub: synchronous ACK, no retry. Both stubs construct **real** `nats-core` payloads and log them distinctly for the FEAT-JARVIS-004/005 grep-for-swap-points check. | Settles Phase 2's "`call_specialist` timeout + retry semantics" open question. |

## 6. Component diagram

[diagrams/fleet-dispatch-l3.md](diagrams/fleet-dispatch-l3.md) — C4 Level 3 view of the Jarvis Supervisor container showing the three FEAT-JARVIS-002 tool modules + their collaborators inside the supervisor graph. **Requires explicit approval per `/system-design` Phase 3.5 gate** (the container exceeds the 3-internal-component threshold — 8 components participate).

## 7. Module layout — extensions to Phase 1

Per [ADR-ARCH-006 five-group layout](../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md). Phase 1 reserved `src/jarvis/tools/` empty; Phase 2 populates it:

```
src/jarvis/
├── agents/
│   └── supervisor.py              # UPDATED — wires 9 new tools
├── prompts/
│   └── supervisor_prompt.py       # UPDATED — adds Tool-Usage section + {available_capabilities}
├── config/
│   ├── settings.py                # UPDATED — web_search_provider, tavily_api_key, stub_capabilities_path
│   └── stub_capabilities.yaml     # NEW    — Phase-2 stub registry (architect, product-owner, ideation, forge)
├── tools/                         # Group C — Shell (populated in Phase 2)
│   ├── __init__.py
│   ├── types.py                   # NEW    — WebResult, CalendarEvent, DispatchError
│   ├── general.py                 # NEW    — read_file, search_web, get_calendar_events, calculate
│   ├── capabilities.py            # NEW    — CapabilityDescriptor, list_available_capabilities, refresh/subscribe stubs
│   └── dispatch.py                # NEW    — dispatch_by_capability, queue_build (stubbed transport)
└── … (all other Phase 1 layout unchanged)
```

Per ADR-ARCH-021, every `@tool` wraps its logic in `try/except` and returns a structured string on error (`ERROR: <category> — <detail>`, `DEGRADED: <reason>`, `TIMEOUT: <details>`). Tools **never raise** — the reasoning model reads the string.

## 8. Wiring — how tools compose into the supervisor

```
env + .env
    │
    ▼
JarvisConfig()                                   ← jarvis.config.settings (UPDATED)
    │
    ▼
lifecycle.startup(config):                        ← jarvis.infrastructure.lifecycle (unchanged)
    │
    ├── logging.configure(...)
    ├── config.validate_provider_keys()           # NEW: also validates tavily_api_key if provider != "none"
    ├── capability_registry = load_stub_registry(config.stub_capabilities_path)  # FEAT-JARVIS-002
    ├── tool_list = assemble_tool_list(           # FEAT-JARVIS-002
    │       config, capability_registry,
    │   )   # → [read_file, search_web, get_calendar_events, calculate,
    │       #    list_available_capabilities, capabilities_refresh,
    │       #    capabilities_subscribe_updates, dispatch_by_capability, queue_build]
    ├── supervisor = build_supervisor(config, tools=tool_list,
    │                                 available_capabilities=capability_registry)
    │                                              # passes both the tool list AND the {available_capabilities}
    │                                              # rendered text into the prompt (DDR-008)
    ├── store = InMemoryStore()
    └── session_manager = SessionManager(supervisor, store)
    │
    ▼
AppState(config, supervisor, store, session_manager,
         capability_registry)                     # extended
    │
    ▼
cli.main runs its subcommand (unchanged Phase 1 behaviour)
```

`build_supervisor(...)`'s public signature gains two keyword arguments — both keyword-only, both with safe defaults — so existing callers still work:

```python
def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,
    available_capabilities: list[CapabilityDescriptor] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]: ...
```

`tools=None` → Phase 1 behaviour (empty list). `available_capabilities=None` → renders "No capabilities currently registered." into `{available_capabilities}`.

## 9. Test shape

Target: +35–50 tests on top of Phase 1's baseline; maintain 80% coverage on all new modules.

- `tests/test_tools_types.py` — Pydantic validation for `WebResult`, `CalendarEvent`, `CapabilityDescriptor`, `DispatchError`.
- `tests/test_tools_general.py` — per-tool happy path + one failure case each:
  - `read_file` — reads a file; rejects path traversal outside the configured workspace (`ERROR: path_traversal`).
  - `search_web` — returns 5 `WebResult`s via a mocked Tavily response; returns `ERROR: config_missing — tavily_api_key not set` when provider key absent.
  - `get_calendar_events` — returns `[]` (Phase 2 stub); rejects invalid `window` with `ERROR: invalid_window — <value>`.
  - `calculate` — evaluates `"15% of 847"`-shaped inputs; rejects unsafe tokens (`ERROR: unsafe_expression — <detail>`).
- `tests/test_tools_capabilities.py` — stub registry loads from YAML; `list_available_capabilities()` returns the 4 descriptors; `capabilities_refresh()` and `capabilities_subscribe_updates()` are no-ops that return a structured "stubbed in Phase 2" string.
- `tests/test_tools_dispatch.py`:
  - `dispatch_by_capability` resolves a tool name to an agent via the stub registry, builds a real `CommandPayload` with the expected `correlation_id` seeding, logs at INFO with the canonical `JARVIS_DISPATCH_STUB` prefix, and returns the configured stub `ResultPayload` JSON.
  - `dispatch_by_capability` returns `ERROR: unresolved — no capability matches tool_name=<x>` when no registry entry matches, with `intent_pattern` fallback exercised.
  - `dispatch_by_capability` returns `TIMEOUT: agent_id=<y> timeout_seconds=<n>` when the stub is configured to simulate a timeout.
  - `queue_build` builds a real `BuildQueuedPayload` (Pattern A) with the required `triggered_by="jarvis"` + `originating_adapter="terminal"` + correlation-id derivation from the session; validates `feature_id` matches `FEATURE_ID_PATTERN`; logs at INFO with `JARVIS_QUEUE_BUILD_STUB` prefix; returns a `QueueBuildAck`-shaped JSON string.
  - `queue_build` rejects malformed `feature_id` / `repo` with a structured error string (Pydantic `ValidationError` caught at the tool boundary per ADR-ARCH-021).
- `tests/test_supervisor_with_tools.py` — extends Phase 1's `test_supervisor.py`: `build_supervisor(test_config, tools=[…], available_capabilities=[…])` returns a `CompiledStateGraph`; the 9 tools are wired; the rendered system prompt contains the `{available_capabilities}` text verbatim; no LLM call.

## 10. Supervisor prompt extensions

[`SUPERVISOR_SYSTEM_PROMPT`](../../../src/jarvis/prompts/supervisor_prompt.py) gains two sections, each appended *after* the Phase 1 content (preserving Phase 1 scope-invariant TASK-J001-004 — attended-conversation posture stays verbatim):

1. **`## Available Capabilities`** — injected via new placeholder `{available_capabilities}`. Rendered from `CapabilityDescriptor.as_prompt_block()` for every entry in the stub registry (plus a fallback "No capabilities currently registered." when empty). This is how ADR-ARCH-016 injects capabilities in Forge — Jarvis mirrors the pattern.
2. **`## Tool Usage`** — a short preference list: prefer `calculate` over mental arithmetic; call `list_available_capabilities` at most once per session (prompt-injected list is authoritative); prefer `dispatch_by_capability` over repeating specialist work in-process; use `queue_build` only when the request explicitly names a feature to build; always return errors from tools as-is to the user rather than re-invoking the same tool on a structured failure.

**No mention of `start_async_task`, named subagents, `escalate_to_frontier`, or skills** — Phase 1's TASK-J001-004 scope-invariant still holds for those (they arrive with FEAT-JARVIS-003 / 007 / via their own ADRs).

## 11. Contradiction detection (against existing ADRs)

Proposed contracts were checked against all 30 accepted ADRs in [docs/architecture/decisions/](../../architecture/decisions/). **Two contradictions found — both resolved via superseding decisions in the upstream scope doc rather than new ADRs** (the scope doc predated the final `/system-arch` output).

| # | Contradiction | ADR | Resolution |
|---|---|---|---|
| C1 | Scope doc proposes `call_specialist(agent_id=..., ...)` with hardcoded `agent_id` | ADR-ARCH-003 (Jarvis-IS-the-GPA); ADR-ARCH-016 (NATS-only transport, fleet catalogue); Forge ADR-ARCH-015/016 adopted fleet-wide per ARCHITECTURE.md §3.C | **DDR-005** — supersede scope name. Use `dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60)` per the capability-driven pattern. Single generic tool, no hardcoded `agent_id`. |
| C2 | Scope doc references four cloud subagents (Gemini/Opus/GPT/vLLM) for FEAT-JARVIS-003 | ADR-ARCH-001 (no cloud LLMs on unattended paths); ADR-ARCH-011 (single `jarvis-reasoner` via gpt-oss-120b supersedes four-cloud roster); ADR-ARCH-027 (attended-only `escalate_to_frontier`) | **Out of scope for this design** — flagged for `/system-design FEAT-JARVIS-003`. This design leaves a reserved slot in `jarvis.tools.dispatch` for `escalate_to_frontier` (attended-path-only, constitutionally gated per ADR-ARCH-022/023) but does not implement it here. |

No other contradictions detected. Compatibility notes:

- Stub-registry data shape is chosen to be superset-compatible with what `NATSKVManifestRegistry.list_all()` will return in FEAT-JARVIS-004 — the transport swap requires no schema change (per the Phase 2 scope invariant "stubbed transport ≠ stubbed schema").
- `queue_build`'s `BuildQueuedPayload` usage honours Pattern A from ADR-SP-014 and the singular-topic convention (ADR-SP-016) baked into `Topics.Pipeline.BUILD_QUEUED`.
- All tools return structured-error strings per ADR-ARCH-021. No tool raises.
- `search_web` API-key absence returns a structured error — consistent with ADR-ARCH-021, not a startup failure, so Jarvis can still run without Tavily configured.
- Capability prompt-injection (DDR-008) and tool-based retrieval coexist — this matches ADR-ARCH-016's placeholder-injection pattern.

## 12. Assumptions carried forward

| Assumption | Reason it's not settled here |
|---|---|
| `ASSUM-ROUTING-HISTORY-SCHEMA` (carried from FEAT-JARVIS-001) | Exact `jarvis_routing_history` Pydantic shape lands with FEAT-JARVIS-004 when real routing decisions start being recorded. This design ensures the stubbed `dispatch_by_capability` log line includes enough structure (selected `tool_name`, resolved `agent_id`, `correlation_id`, `latency_ms`, `error_category` if any) to be schema-compatible when writes go live. |
| `ASSUM-DISPATCH-AMBIGUITY` | ADR-ARCH-015-equivalent resolution priority (highest `trust_tier` + highest intent confidence + lowest `queue_depth`) lives in `NATSKVManifestRegistry` — Phase 2's stub registry implements a reduced form: unique `tool_name` keys. FEAT-JARVIS-004 inherits the real resolver. |
| `ASSUM-CALENDAR-PROVIDER` | `get_calendar_events` is a Phase 2 stub; real provider (CalDAV via `jarvis.tools.external`) is a v1.5 concern, pinned at that time. The signature agreed here (`window: Literal["today","tomorrow","this_week"] = "today"`) is load-bearing for the FEAT-JARVIS-007 `morning-briefing` skill. |
| `ASSUM-TAVILY-AVAILABILITY` | If Tavily adds captcha / upstream outage, `search_web` returns `DEGRADED: provider_unavailable` and the reasoning model handles it per ADR-ARCH-021 — no in-tool failover in Phase 2. |

## 13. Next steps

1. **Approve the C4 L3 diagram** at [diagrams/fleet-dispatch-l3.md §Review gate](diagrams/fleet-dispatch-l3.md).
2. **Seed design to Graphiti** (commands offered at the end of this `/system-design` run — `project_design` group for contracts/models, `architecture_decisions` group for DDRs).
3. **Proceed to `/system-design FEAT-JARVIS-003`** — async subagents (separate design run; this design is input context).
4. **Then `/feature-spec FEAT-JARVIS-002`** — Gherkin scenarios grounded in this design.
5. **Then `/feature-plan FEAT-JARVIS-002`** — task breakdown per [phase2-build-plan.md Step 7 commit order](../../research/ideas/phase2-build-plan.md).
6. **Then AutoBuild** — follow the Step 7 commit order: config → types → general → capabilities → dispatch → prompt → supervisor factory → supervisor-with-tools test.

## 14. File manifest

```
docs/design/FEAT-JARVIS-002/
├── design.md                                                       ← this file
├── contracts/
│   ├── API-tools.md                                                ← 9 @tool surfaces (docstring contracts)
│   └── API-internal.md                                             ← module-level Python API
├── models/
│   ├── DM-tool-types.md                                            ← CapabilityDescriptor, WebResult, CalendarEvent, DispatchError
│   └── DM-stub-registry.md                                         ← stub_capabilities.yaml schema
├── diagrams/
│   └── fleet-dispatch-l3.md                                        ← C4 L3 (mandatory review gate)
└── decisions/
    ├── DDR-005-dispatch-by-capability-supersedes-call-specialist.md
    ├── DDR-006-tavily-as-web-search-provider.md
    ├── DDR-007-asteval-for-calculate.md
    ├── DDR-008-capabilities-both-tool-and-prompt-injection.md
    └── DDR-009-dispatch-stub-transport-semantics.md
```

DDR numbering continues from FEAT-JARVIS-001 (which used DDR-001..004); next available is DDR-005.

---

*"Dispatch is tool selection."* — [phase2-dispatch-foundations-scope.md](../../research/ideas/phase2-dispatch-foundations-scope.md)
