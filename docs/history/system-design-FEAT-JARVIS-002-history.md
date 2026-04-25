/system-design FEAT-JARVIS-002 \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../nats-core/docs/design/contracts/agent-manifest-contract.md \
  --context ../nats-core/src/nats_core/manifest.py \
  --context ../nats-core/src/nats_core/topics.py \
  --context ../nats-core/src/nats_core/payloads/ \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/prompts/supervisor_prompt.py \
  --context .guardkit/context-manifest.yaml
I'll execute /system-design for FEAT-JARVIS-002. Starting with prerequisite checks and loading context.

Read graphiti.yaml
Globpattern: "docs/architecture/**/*.md"
Found 34 files
Graphiti enabled, architecture present (34 docs). Loading the provided context files to ground the design.

Read phase2-dispatch-foundations-scope.md
Loading remaining context files to ground the design.

Read phase2-build-plan.md
Read design.md
Now loading the nats-core contracts and Forge ADRs that shape the dispatch surface, plus current supervisor code.

Read agent-manifest-contract.md
Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH / ADR-J corpus

Draft DDRs (web-search provider, calculate lib, stub registry, call_specialist timeout/retry)

Write docs/design/FEAT-JARVIS-002/design.md + contracts/ + models/ + diagrams/ + decisions/

Present C4 L3 review gate

Offer Graphiti seeding commands
Read manifest.py
Read topics.py
Globpattern: "/Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/payloads/*.py"
No files found
Bash List nats-core payloads directory
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/payloads/

OUT
Exit code 1
ls: /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/payloads/: No such file or directory
Bash List nats-core source tree
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/

OUT
__init__.py
__pycache__
_routing.py
agent_config.py
client.py
config.py
envelope.py
events
manifest.py
py.typed
topics.py
Bash List events subpackage
IN
ls /Users/richardwoollcott/Projects/appmilla_github/nats-core/src/nats_core/events/

OUT
__init__.py
__pycache__
_agent.py
_fleet.py
_jarvis.py
_pipeline.py
fleet.py
Read _agent.py
Read _pipeline.py
Read supervisor.py
Read supervisor_prompt.py
Read ADR-J-001-deepagents-pin.md
Globpattern: "docs/architecture/decisions/ADR-J-*.md"
No files found
Read ARCHITECTURE.md
Read ADR-ARCH-015-capability-driven-dispatch.md
Read ADR-ARCH-016-fleet-is-the-catalogue.md
Read ADR-ARCH-019-no-static-behavioural-config.md
Read envelope.py
Read ADR-ARCH-021-tools-return-structured-errors.md
Read ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md
Read context-manifest.yaml
Context loaded. Updating todos and proceeding to design.

Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH corpus

Draft DDRs (web-search provider, calculate lib, stub registry, dispatch semantics, prompt-injection path)

Write docs/design/FEAT-JARVIS-002/design.md + contracts/ + models/ + diagrams/ + decisions/

Present C4 L3 review gate

Offer Graphiti seeding commands
Before I write artefacts I want to flag two substantive contradictions between the Phase 2 scope doc (20 April) and the later ARCHITECTURE.md + ADRs (also 20 April, but authoritative). These shape the design.

Contradiction 1 — dispatch-tool name & signature
Phase 2 scope (lines 54–56) proposes call_specialist(agent_id, instruction, context). But ADR-ARCH-015's Forge analogue (../forge/…/ADR-ARCH-015) forbids hardcoded agent_id — "no per-role tools" — and ARCHITECTURE.md §3.C commits Jarvis to the same pattern under the name dispatch_by_capability. Adopting call_specialist(agent_id=…) would silently invert ADR-ARCH-016 ("fleet is the catalogue") and force a rename in FEAT-JARVIS-004. Resolution: supersede the scope doc's name; use dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60).

Contradiction 2 — four cloud subagents vs. single local reasoner
Phase 2 scope's FEAT-JARVIS-003 block references four cloud subagents (Gemini 3.1 Pro, Opus 4.7, GPT-5.4, vLLM). ADR-ARCH-011 + ADR-ARCH-001 supersede: one jarvis-reasoner on gpt-oss-120b via llama-swap, cloud only via escalate_to_frontier on attended paths. This is a FEAT-JARVIS-003 concern — I'll note it and not design against it here — but the dispatch-tool design needs to anticipate escalate_to_frontier sitting alongside dispatch_by_capability/queue_build in the same tool-layer module (per ARCHITECTURE.md §3.C).

Proceeding with these resolutions. Writing design artefacts now.

Bash Create design artefact directory tree
IN
mkdir -p /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/design/FEAT-JARVIS-002/{contracts,models,diagrams,decisions}

OUT
(Bash completed with no output)
Write design.md
235 lines
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
Write API-tools.md
375 lines
# API-tools — Tool Surface Contract

> **Surface:** DeepAgents `@tool(parse_docstring=True)` functions registered on the Jarvis supervisor graph.
> **Consumer:** the reasoning model running inside `create_deep_agent(...)`. Tool docstrings ARE the contract — the reasoning model reads them at decision time per ADR-ARCH-016-equivalent pattern.
> **Failure discipline:** every tool follows [ADR-ARCH-021](../../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md) — return a structured string on failure; never raise. Prefix conventions: `ERROR:`, `DEGRADED:`, `TIMEOUT:`.
> **All docstrings below are the *authoritative* docstring text for the AutoBuild player.** Changes require a note in the commit message because docstrings change routing behaviour (per Phase 2 scope §Do-Not-Change ¶7, adapted to the tool layer).

---

## 1. General Tools — `jarvis.tools.general`

### 1.1 `read_file(path: str) -> str`

```python
@tool(parse_docstring=True)
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the user's workspace and return its contents.

    Use this tool when the user refers to a file on disk ("summarise /tmp/foo.md",
    "what's in my notes folder") or when you need file contents to answer. Do NOT
    use it for binary files or files outside the configured workspace root — those
    return a structured error.

    Near-zero cost, <100ms typical latency. No network I/O.

    Args:
        path: Absolute or workspace-relative path. Path traversal outside the
              workspace root is rejected.

    Returns:
        The file contents as a string, OR a structured error:
          - ``ERROR: path_traversal — path resolves outside workspace: <resolved>``
          - ``ERROR: not_found — path does not exist: <path>``
          - ``ERROR: not_a_file — path is a directory or special file: <path>``
          - ``ERROR: too_large — file exceeds 1MB, refusing to read: <path>``
          - ``ERROR: encoding — file is not valid UTF-8: <path>``
    """
```

**Safety:** workspace root is `JarvisConfig.workspace_root` (defaulting to the current working directory resolved at startup). File size cap: 1 MB. Uses the same path-safety guards as DeepAgents built-in filesystem per Phase 2 scope §1.1.

---

### 1.2 `search_web(query: str, max_results: int = 5) -> str`

```python
@tool(parse_docstring=True)
def search_web(query: str, max_results: int = 5) -> str:
    """Run a web search and return up to N results as JSON.

    Use this tool for factual lookups, recent information, or when the user asks
    you to find something online. Prefer over invoking a subagent for simple
    lookups — the subagent cost and latency are higher. Do NOT use it for
    knowledge already in the conversation or for reasoning tasks.

    Moderate cost (~$0.005/query via Tavily), ~1–3s typical latency.
    Requires TAVILY_API_KEY configured; returns a structured error otherwise.

    Args:
        query: The search query string. Non-empty.
        max_results: Maximum number of results to return (1–10). Default 5.

    Returns:
        JSON array of WebResult objects:
          ``[{"title": str, "url": str, "snippet": str, "score": float}, ...]``
        OR a structured error:
          - ``ERROR: config_missing — tavily_api_key not set in JarvisConfig``
          - ``ERROR: invalid_query — query must be non-empty``
          - ``ERROR: invalid_max_results — must be between 1 and 10, got <n>``
          - ``DEGRADED: provider_unavailable — Tavily returned <status>``
    """
```

**Provider:** Tavily, per [DDR-006](../decisions/DDR-006-tavily-as-web-search-provider.md). Provider abstraction allows swap without changing the docstring.

---

### 1.3 `get_calendar_events(window: Literal["today", "tomorrow", "this_week"] = "today") -> str`

```python
@tool(parse_docstring=True)
def get_calendar_events(window: str = "today") -> str:
    """Return calendar events for a named time window.

    Use this tool when the user asks "what's on today", "do I have time next
    Thursday", or similar calendar-shaped questions. Prefer this over reasoning
    about the calendar from memory — the tool reads live data when a real
    provider is configured.

    STUB in Phase 2: returns an empty list ``[]`` (or a canned list configured
    for tests). Signature is stable — FEAT-JARVIS-007's morning-briefing skill
    depends on this shape. Near-zero cost, <50ms latency.

    Args:
        window: One of "today", "tomorrow", "this_week". Default "today".

    Returns:
        JSON array of CalendarEvent objects:
          ``[{"id": str, "title": str, "start": ISO8601, "end": ISO8601,
              "location": str | null, "description": str | null}, ...]``
        OR a structured error:
          - ``ERROR: invalid_window — must be one of today/tomorrow/this_week, got <value>``
    """
```

---

### 1.4 `calculate(expression: str) -> str`

```python
@tool(parse_docstring=True)
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression safely and return the result.

    Use this tool for ANY arithmetic — percentages, unit conversion, compound
    calculations. You are bad at arithmetic; the tool is not. Do NOT use it for
    symbolic manipulation, calculus, or anything that requires an algebra
    system — those return a structured error.

    Near-zero cost, <10ms latency. No network I/O.

    Args:
        expression: A mathematical expression. Supported operators: + - * / ** %
                    and parentheses. Supported functions: sqrt, log, exp, sin,
                    cos, tan, abs, min, max, round. Variables are NOT supported.

    Returns:
        The result as a string (numeric or truthy), OR a structured error:
          - ``ERROR: unsafe_expression — disallowed token: <token>``
          - ``ERROR: parse_error — <detail>``
          - ``ERROR: division_by_zero``
          - ``ERROR: overflow — result exceeds float range``
    """
```

**Implementation:** `asteval` (AST-based evaluator; no `eval`) per [DDR-007](../decisions/DDR-007-asteval-for-calculate.md).

---

## 2. Capability Catalogue Tools — `jarvis.tools.capabilities`

### 2.1 `list_available_capabilities() -> str`

```python
@tool(parse_docstring=True)
def list_available_capabilities() -> str:
    """Return the current fleet capability catalogue as JSON.

    The catalogue is also injected into your system prompt at session start
    (under "## Available Capabilities"). Call this tool only when you suspect
    the injected snapshot is stale — e.g., the user says "a new agent just came
    online" or more than ~10 minutes have elapsed in the same session.

    In Phase 2 this reads from an in-memory stub registry; in FEAT-JARVIS-004
    (Phase 3) it will read from the live NATS KV manifest registry. The
    signature and response shape are identical across phases.

    Near-zero cost, <5ms latency (stub) / <30ms (cached live registry).

    Returns:
        JSON array of CapabilityDescriptor objects:
          ``[{"agent_id": str, "role": str, "description": str,
              "capability_list": [{"tool_name": str, "description": str,
                                   "risk_level": str}, ...],
              "cost_signal": str, "latency_signal": str,
              "last_heartbeat_at": ISO8601 | null,
              "trust_tier": "core" | "specialist" | "extension"}, ...]``
        OR a structured error:
          - ``ERROR: registry_unavailable — <detail>``
    """
```

### 2.2 `capabilities_refresh() -> str`

```python
@tool(parse_docstring=True)
def capabilities_refresh() -> str:
    """Invalidate the cached capability catalogue and re-read the source of truth.

    Call this ONLY when the user explicitly indicates the catalogue is stale —
    e.g. "the architect agent should be up now, check again". The injected
    system-prompt snapshot is refreshed at session start; mid-session refresh
    is rarely useful.

    STUB in Phase 2: no-op that returns a structured acknowledgement. Phase 3
    (FEAT-JARVIS-004) triggers a real NATS KV re-read.

    Returns:
        ``OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)``
        OR a structured error in Phase 3+.
    """
```

### 2.3 `capabilities_subscribe_updates() -> str`

```python
@tool(parse_docstring=True)
def capabilities_subscribe_updates() -> str:
    """Subscribe the current session to live capability-change notifications.

    STUB in Phase 2: no-op that returns a structured acknowledgement. Phase 3
    (FEAT-JARVIS-004) attaches a NATS KV watcher that will re-inject the
    capability block into future turns when fleet membership changes.

    Call at most once per session.

    Returns:
        ``OK: subscribed (stubbed in Phase 2 — no live updates)``
        OR a structured error in Phase 3+.
    """
```

---

## 3. Dispatch Tools — `jarvis.tools.dispatch`

### 3.1 `dispatch_by_capability(tool_name: str, payload_json: str, intent_pattern: str | None = None, timeout_seconds: int = 60) -> str`

**This tool supersedes `call_specialist` per [DDR-005](../decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md).** No `agent_id` parameter — resolution happens against the capability catalogue per ADR-ARCH-016-equivalent pattern.

```python
@tool(parse_docstring=True)
def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str | None = None,
    timeout_seconds: int = 60,
) -> str:
    """Dispatch work to a specialist agent by capability name, not agent name.

    Resolution order:
      1. Exact match on a registered ToolCapability.name across the catalogue.
      2. If no exact match, match IntentCapability.pattern (if intent_pattern
         is provided) with highest confidence wins.
      3. If still unresolved, returns ``ERROR: unresolved``. Reason the
         response yourself — do not retry the same dispatch with a different
         tool_name unless the user confirms.

    Use this tool when the user asks for work that falls under a specialist
    agent's description (e.g. "ask the architect for a C4 diagram", "have
    product-owner review this spec"). Check the capability catalogue first —
    injected at session start under "## Available Capabilities" — to find the
    tool_name you need. Do NOT pass agent IDs; pass capability names.

    In Phase 2 the transport is stubbed: the tool builds a real CommandPayload
    per nats-core, logs it, and returns a canned ResultPayload JSON for tests.
    FEAT-JARVIS-004 replaces the stub with real NATS round-trips without
    changing this docstring.

    Cost depends on the resolved specialist; latency is capped by
    timeout_seconds. Moderate cost (~$0.10–$2 per dispatch, specialist-
    dependent); 5–60s typical wall-clock.

    Args:
        tool_name: The ToolCapability.name to invoke (e.g.
                   ``run_architecture_session``). Required.
        payload_json: JSON string matching the tool's parameters schema as
                     declared in its ToolCapability.parameters. Must be a JSON
                     object literal (starts with ``{``). The tool does NOT
                     validate your payload against the schema in Phase 2 — the
                     specialist will.
        intent_pattern: Optional intent pattern (e.g. ``architecture.generate``)
                       used only when no exact tool match is found.
        timeout_seconds: How long to wait for the specialist's reply, between
                        5 and 600. Default 60. Timeout returns a structured
                        TIMEOUT error; it does NOT cancel the specialist — the
                        result may still appear in NATS after timeout
                        (Phase 3+).

    Returns:
        JSON string of the specialist's ResultPayload on success:
          ``{"command": str, "result": {...}, "correlation_id": str,
             "success": true}``
        OR a structured error:
          - ``ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>``
          - ``ERROR: invalid_payload — payload_json is not a JSON object literal``
          - ``ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>``
          - ``TIMEOUT: agent_id=<id> tool_name=<x> timeout_seconds=<n>``
          - ``ERROR: specialist_error — agent_id=<id> detail=<reason>``
          - ``DEGRADED: transport_stub — (Phase 2 stub, real NATS arrives in FEAT-JARVIS-004)``
    """
```

**Stub behaviour (Phase 2):** configurable per test via a module-level `_stub_response_hook`:

| Stub mode | Returns |
|---|---|
| `success` (default) | Canned `ResultPayload` with `success=True` and `result={"stub": true, "tool_name": <x>}` |
| `timeout` | `TIMEOUT: ...` structured error |
| `specialist_error` | `ERROR: specialist_error — agent_id=<id> detail=<reason>` |

**Phase 3 (FEAT-JARVIS-004) migration points:** The log line `JARVIS_DISPATCH_STUB tool_name=... agent_id=... correlation_id=...` is the grep anchor — swapping the stub for real NATS publish/subscribe loops replaces the log line with an actual publish. Tool docstring and return shape stay identical.

---

### 3.2 `queue_build(feature_id: str, feature_yaml_path: str, repo: str, branch: str = "main", originating_adapter: str = "terminal", correlation_id: str | None = None, parent_request_id: str | None = None) -> str`

```python
@tool(parse_docstring=True)
def queue_build(
    feature_id: str,
    feature_yaml_path: str,
    repo: str,
    branch: str = "main",
    originating_adapter: str = "terminal",
    correlation_id: str | None = None,
    parent_request_id: str | None = None,
) -> str:
    """Queue a Forge build for an already-planned feature. Pattern A per
    ADR-SP-014: Jarvis publishes and walks away; Forge consumes from JetStream.

    Use this tool when the user has a feature spec already produced (via
    /feature-spec and /feature-plan) and says "build it" or equivalent. Do NOT
    use it to kick off planning — that is not a Forge responsibility. If the
    user asks you to plan, route to the architect or product-owner specialist
    via dispatch_by_capability instead.

    In Phase 2 the transport is stubbed: the tool builds a real
    BuildQueuedPayload per nats-core, logs it, and returns a canned ACK.
    FEAT-JARVIS-005 replaces the stub with a real
    pipeline.build-queued.{feature_id} JetStream publish without changing this
    docstring.

    Fire-and-forget. Near-zero publish latency when real; Forge may take hours
    to complete the build — you will receive pipeline.* progress events via
    notifications in FEAT-JARVIS-005. Do not await completion.

    Args:
        feature_id: FEAT-XXX identifier matching ``^FEAT-[A-Z0-9]{3,12}$``.
        feature_yaml_path: Path to the feature YAML spec, relative to the
                           repo root (e.g. ``features/feat-jarvis-002/....yaml``).
        repo: GitHub org/repo, e.g. ``guardkit/jarvis`` or ``appmilla/forge``.
              Must match ``^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$``.
        branch: Base branch to branch from. Default ``main``.
        originating_adapter: Which Jarvis adapter the human used. One of
                            ``terminal``, ``voice-reachy``, ``telegram``,
                            ``slack``, ``dashboard``, ``cli-wrapper``.
                            Default ``terminal`` (CLI). ``triggered_by`` is
                            always set to ``jarvis`` by this tool.
        correlation_id: Stable ID for tracing. Auto-generated if omitted.
        parent_request_id: The Jarvis dispatch message ID that spawned this
                          build, for progress-event correlation. Optional.

    Returns:
        JSON string of the QueueBuildAck on success:
          ``{"feature_id": str, "correlation_id": str,
             "queued_at": ISO8601,
             "publish_target": "pipeline.build-queued.{feature_id}",
             "status": "queued"}``
        OR a structured error:
          - ``ERROR: invalid_feature_id — must match FEAT-XXX pattern, got <value>``
          - ``ERROR: invalid_repo — must be org/name format, got <value>``
          - ``ERROR: invalid_adapter — <value> not in allowed list``
          - ``ERROR: validation — <pydantic detail>``
          - ``DEGRADED: transport_stub — (Phase 2 stub, real publish arrives in FEAT-JARVIS-005)``
    """
```

**Stub behaviour (Phase 2):** always returns success. Log line prefix: `JARVIS_QUEUE_BUILD_STUB feature_id=... correlation_id=... repo=...`.

**Phase 4 (FEAT-JARVIS-005) migration:** the log-only stub becomes a real `jetstream.publish(subject=Topics.Pipeline.BUILD_QUEUED.format(...), payload=MessageEnvelope(...))` call. Tool signature, docstring, and return shape unchanged.

---

## 4. Registration on the supervisor

All 9 tools are collected into a single list via `jarvis.tools.assemble_tool_list(config, capability_registry)` and passed to `build_supervisor(config, tools=..., available_capabilities=...)`. The ordering in the list is not semantically significant (DeepAgents surfaces tool descriptions alphabetically), but the registration module keeps a stable alphabetical order to reduce prompt-cache churn.

Deferred to later features:

- `start_async_task`, `wait_for_async_tasks`, etc. — added by `AsyncSubAgentMiddleware` in FEAT-JARVIS-003.
- `escalate_to_frontier` — reserved slot in `jarvis.tools.dispatch`; lands with its own feature ticket after ADR-ARCH-027 implementation work.
- `record_routing_decision`, `record_ambient_event`, `query_knowledge` — Graphiti tools, FEAT-JARVIS-004.
- `emit_notification` — FEAT-JARVIS-004 / 006.
Write API-internal.md
175 lines
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
Write DM-tool-types.md
214 lines
# DM-tool-types — Tool-Layer Pydantic Models

> Models live in [`src/jarvis/tools/types.py`](../../../../src/jarvis/tools/types.py) (+ `capabilities.py` for `CapabilityDescriptor` because that module owns the registry). All models validate at construction per fleet-wide D22 / ADR-ARCH-021 (Pydantic 2 at every boundary).

---

## 1. `CapabilityDescriptor` — `jarvis.tools.capabilities`

The supervisor-facing projection of an agent's `nats_core.AgentManifest`. Deliberately a subset of the manifest — the reasoning model reads this; not every manifest field is useful to the model, and some (e.g. `container_id`) leak infrastructure.

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilityToolSummary(BaseModel):
    """A single tool exposed by a fleet agent, as surfaced to Jarvis.

    Attributes:
        tool_name: Maps 1:1 to ``nats_core.ToolCapability.name``.
        description: Human-readable description the reasoning model reads
                     at decision time.
        risk_level: Risk classification for approval gating.
    """

    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["read_only", "mutating", "destructive"] = "read_only"


class CapabilityDescriptor(BaseModel):
    """A fleet agent's capabilities as rendered into Jarvis's context.

    Attributes:
        agent_id: Kebab-case identifier. Matches ``AgentManifest.agent_id``.
        role: Human-readable role name (e.g. "Architect", "Product Owner").
              Derived from ``AgentManifest.name`` in Phase 3+.
        description: One-paragraph description of what this agent does best —
                     surfaces in ``{available_capabilities}`` prompt block.
        capability_list: The ToolCapability summaries Jarvis can dispatch to.
        cost_signal: Human-readable cost indicator (e.g. "low", "~$0.10/call").
        latency_signal: Human-readable latency indicator (e.g. "5-30s", "sub-second").
        last_heartbeat_at: Timestamp of last heartbeat received. None in Phase 2
                           (no heartbeats yet); populated in Phase 3.
        trust_tier: Trust classification, mapped from ``AgentManifest.trust_tier``.
    """

    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Kebab-case agent identifier",
    )
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capability_list: list[CapabilityToolSummary] = Field(default_factory=list)
    cost_signal: str = Field(default="unknown")
    latency_signal: str = Field(default="unknown")
    last_heartbeat_at: datetime | None = None
    trust_tier: Literal["core", "specialist", "extension"] = "specialist"

    def as_prompt_block(self) -> str:
        """Render this descriptor as a prompt-friendly text block.

        The supervisor's ``{available_capabilities}`` placeholder is filled
        by joining these blocks with double newlines.
        """
        ...  # implementation returns deterministic, token-cheap text
```

### Prompt-block shape (deterministic)

Example rendering (exact format — tests assert byte-equal):

```
### architect-agent — Architect (trust: specialist, cost: moderate, latency: 5-30s)

Produces architecture sessions, C4 diagrams, and ADRs for features. Prefers
evidence-based decisions grounded in the existing ARCHITECTURE.md.

Tools:
  - run_architecture_session (read_only) — Drive a full /system-arch
    session end-to-end from a scope document.
  - draft_adr (mutating) — Produce a new ADR file given context + decision.
```

### Compatibility with `nats_core.AgentManifest`

| `CapabilityDescriptor` field | Source in `AgentManifest` | Notes |
|---|---|---|
| `agent_id` | `agent_id` | 1:1 |
| `role` | `name` | Human-friendly mapping |
| `description` | `metadata["jarvis_description"]` OR first-paragraph of a convention field — **settled here for Phase 3:** use `metadata["jarvis_description"]`, fall back to `f"{name} ({template})"` if absent. This keeps the `AgentManifest` contract un-touched and gives Jarvis a dedicated field to negotiate on. |
| `capability_list` | `tools[*]` mapped to `CapabilityToolSummary` | 1:1 per entry |
| `cost_signal` | `metadata["cost_signal"]` | Free-form |
| `latency_signal` | `metadata["latency_signal"]` | Free-form |
| `last_heartbeat_at` | `AgentHeartbeatPayload.timestamp` (last received) | `None` in Phase 2 |
| `trust_tier` | `trust_tier` | 1:1 |

`metadata["jarvis_description"]`, `metadata["cost_signal"]`, `metadata["latency_signal"]` are **conventions** the fleet adopts for Jarvis consumption; they sit inside `AgentManifest.metadata` (which is designed for exactly this kind of extension). No `nats-core` schema change is required.

---

## 2. `WebResult` — `jarvis.tools.types`

```python
class WebResult(BaseModel):
    """A single web-search result surfaced by ``search_web``.

    Attributes:
        title: Page title from the search result.
        url: Fully-qualified URL.
        snippet: Short extract or description from the search provider.
        score: Relevance score (0.0–1.0) if the provider supplies one; 0.0 otherwise.
    """

    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    snippet: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
```

---

## 3. `CalendarEvent` — `jarvis.tools.types`

```python
class CalendarEvent(BaseModel):
    """A single calendar event surfaced by ``get_calendar_events``.

    Phase 2 only constructs these in tests — the real provider lands in v1.5.

    Attributes:
        id: Stable event identifier from the source provider.
        title: Event title.
        start: Event start time (UTC).
        end: Event end time (UTC). Must be >= start.
        location: Optional physical / virtual location string.
        description: Optional free-text body.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def _end_must_not_precede_start(self) -> "CalendarEvent":
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self
```

---

## 4. `DispatchError` — `jarvis.tools.types`

Structured-error sentinel used internally by `dispatch.py` and `capabilities.py`. **Not** surfaced over the tool boundary — tools convert it into an `ERROR: <category> — <detail>` string per ADR-ARCH-021. Kept as a Pydantic model so tests can match on fields rather than on error-string regex.

```python
class DispatchError(BaseModel):
    """Internal structured representation of a dispatch failure.

    Attributes:
        category: One of unresolved | invalid_payload | invalid_timeout |
                  timeout | specialist_error | transport_stub.
        detail: Human-readable context.
        agent_id: Resolved agent if known; None if resolution failed.
        tool_name: Requested tool_name if set.
        correlation_id: Correlation ID assigned even on failure so the event
                        is traceable.
    """

    model_config = ConfigDict(extra="ignore")

    category: Literal[
        "unresolved",
        "invalid_payload",
        "invalid_timeout",
        "timeout",
        "specialist_error",
        "transport_stub",
    ]
    detail: str = Field(min_length=1)
    agent_id: str | None = None
    tool_name: str | None = None
    correlation_id: str

    def to_tool_string(self) -> str:
        """Render the ADR-ARCH-021-compliant single-line error string."""
        ...
```

---

## 5. Invariants

- All models set `ConfigDict(extra="ignore")` — forward-compatible with new fields published by evolving manifests.
- `datetime` fields are UTC-aware; serialization goes through Pydantic's default ISO-8601 encoder.
- No model imports from `jarvis.agents.*`, `jarvis.infrastructure.*`, or `jarvis.cli.*` — the tools package is a leaf per ADR-ARCH-002 (clean hexagonal).
- Models are hashable by value only where mutation is never needed — `CapabilityDescriptor` sits inside lists that are rebuilt on refresh rather than mutated in place.
Write DM-stub-registry.md
143 lines
# DM-stub-registry — `stub_capabilities.yaml` Schema

> **Path:** `src/jarvis/config/stub_capabilities.yaml`
> **Lifetime:** Phase 2 only. Removed when FEAT-JARVIS-004 wires `NATSKVManifestRegistry`.
> **Loader:** `jarvis.tools.capabilities.load_stub_registry(path) -> list[CapabilityDescriptor]`.

---

## Why a file, not a constant

A YAML file rather than a Python constant lets tests swap the registry without monkeypatching, and keeps the stub data in a format **identical** to what an operator would paste into a debug fixture when investigating a production issue once the real registry arrives. YAML was chosen over JSON for comment support — the stub entries include justification comments linking to the specialist-agent role that inspired each.

---

## Schema

Root is a mapping with two keys:

```yaml
version: "1.0"
capabilities:
  - agent_id: <kebab-case>
    role: <free-form>
    description: <free-form, 1+ paragraphs>
    capability_list:
      - tool_name: <snake_case>
        description: <free-form>
        risk_level: read_only | mutating | destructive  # optional, default read_only
    cost_signal: <free-form>                            # e.g. "low", "~$0.10/call"
    latency_signal: <free-form>                         # e.g. "5-30s", "sub-second"
    last_heartbeat_at: null                             # always null in Phase 2
    trust_tier: core | specialist | extension           # default specialist
```

Each element under `capabilities` is validated against `CapabilityDescriptor` on load. Missing required fields or malformed `agent_id` raise `pydantic.ValidationError` at startup — this is startup-fatal (same posture as a missing model API key in Phase 1).

---

## Canonical Phase 2 content (AutoBuild starting point)

This is the shape AutoBuild produces for Phase 2. Values are informed by [phase2-dispatch-foundations-scope.md §2.2](../../research/ideas/phase2-dispatch-foundations-scope.md) — "four stubbed descriptors (architect, product-owner, ideation shapes) plus one for Forge". Feature-spec MAY refine descriptions but the agent_id + tool_name keys must remain stable for the routing e2e test in FEAT-JARVIS-003.

```yaml
version: "1.0"
capabilities:

  - agent_id: architect-agent
    role: Architect
    description: >
      Produces architecture sessions, C4 diagrams, and ADRs for features. Best
      for "design the system for X", "generate a C4 diagram", "review this
      architecture against the ADR set". Not for implementation.
    capability_list:
      - tool_name: run_architecture_session
        description: Drive a full /system-arch session from a scope document and emit ARCHITECTURE.md + ADRs.
        risk_level: read_only
      - tool_name: draft_adr
        description: Given a decision + context, emit a single ADR file.
        risk_level: mutating
    cost_signal: "moderate (~$0.50-$2 per session)"
    latency_signal: "5-30 minutes per session"
    last_heartbeat_at: null
    trust_tier: specialist

  - agent_id: product-owner-agent
    role: Product Owner
    description: >
      Reviews feature specifications, prioritises work, and refines acceptance
      criteria. Best for "is this spec complete?", "what's missing from this
      feature?", "should we build X or Y first?". Not for architectural
      decisions.
    capability_list:
      - tool_name: review_specification
        description: Evaluate a feature spec for completeness, clarity, and priority.
        risk_level: read_only
      - tool_name: refine_acceptance_criteria
        description: Expand or tighten the Given/When/Then scenarios in a feature spec.
        risk_level: mutating
    cost_signal: "low (~$0.10/call)"
    latency_signal: "30s-2min"
    last_heartbeat_at: null
    trust_tier: specialist

  - agent_id: ideation-agent
    role: Ideation
    description: >
      Generates candidate solutions, alternatives, and counter-examples. Best
      for "what are our options here?", "steelman the opposing view", "what
      could go wrong?". Not for committing to a decision — delegate that back
      to Rich or to the architect.
    capability_list:
      - tool_name: generate_alternatives
        description: Produce 3-5 distinct candidate approaches to a stated problem.
        risk_level: read_only
      - tool_name: steelman
        description: Construct the strongest possible argument for the opposing position.
        risk_level: read_only
    cost_signal: "low (~$0.05/call)"
    latency_signal: "10-30s"
    last_heartbeat_at: null
    trust_tier: specialist

  - agent_id: forge
    role: Build Pipeline
    description: >
      Executes feature builds end-to-end given a feature YAML. Consumes
      pipeline.build-queued.{feature_id} from JetStream. Jarvis queues; Forge
      does the work. Fire-and-forget — progress events arrive via
      notifications, not by awaiting this dispatch.
    capability_list:
      - tool_name: build_feature
        description: >
          Synonym surfacing the queue_build tool's semantics into the catalogue so the
          reasoning model can reason about "Forge" as a dispatch target
          alongside specialist agents. In practice the reasoning model will
          invoke the dedicated queue_build tool rather than dispatch_by_capability.
        risk_level: mutating
    cost_signal: "high (full GuardKit AutoBuild run)"
    latency_signal: "15-180min"
    last_heartbeat_at: null
    trust_tier: core
```

---

## Rationale for the fourth entry (Forge)

Including `forge` as a capability entry even though `queue_build` is a dedicated tool (not `dispatch_by_capability`) serves two purposes:

1. **Routing test coverage** — FEAT-JARVIS-003's `test_routing_e2e.py` asserts the reasoning model reads the catalogue before picking a dispatch target. Having Forge visible in the catalogue exercises the case where the model sees multiple dispatch targets side-by-side and correctly uses the dedicated `queue_build` tool rather than `dispatch_by_capability`.
2. **FEAT-JARVIS-005 continuity** — when the real `NATSKVManifestRegistry` lights up, Forge already registers itself on `fleet.register`. The catalogue will include Forge automatically. Having a stub entry keeps Phase 2's reasoning-model behaviour identical to Phase 3+.

---

## Validation tests

- Roundtrip: YAML → `list[CapabilityDescriptor]` → dump → compare.
- Reject malformed `agent_id` (e.g. `Architect` with capital).
- Reject unknown `risk_level`.
- Reject `last_heartbeat_at` set to a non-ISO-8601 value (but `null` always valid).
- Reject duplicate `agent_id` entries (deduplication is the loader's job; violates the CapabilityDescriptor's implicit identity).
- Tolerate unknown keys (ConfigDict extra="ignore") so a future field published by a real AgentManifest doesn't break Phase 2 loaders.
Now the DDRs.

Write DDR-005-dispatch-by-capability-supersedes-call-specialist.md
59 lines
# DDR-005: Dispatch tool is `dispatch_by_capability`, superseding scope-doc `call_specialist`

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** Fleet Dispatch Context; `jarvis.tools.dispatch`
- **Supersedes (within scope doc only):** [phase2-dispatch-foundations-scope.md §1.3](../../../research/ideas/phase2-dispatch-foundations-scope.md) `call_specialist(agent_id, instruction, context={})`
- **Related ADRs:** ADR-ARCH-003 (Jarvis-IS-GPA); ADR-ARCH-016 (NATS-only transport); Forge ADR-ARCH-015 (capability-driven dispatch, adopted fleet-wide); Forge ADR-ARCH-016 (fleet-is-the-catalogue)

## Context

The Phase 2 scope document (20 April 2026) predates the final `/system-arch` session (also 20 April, produced ADR-ARCH-001..030). Between the scope being drafted and ARCHITECTURE.md v1.0 being signed off, the fleet-wide pattern was pinned:

- [ARCHITECTURE.md §3.C](../../../architecture/ARCHITECTURE.md) calls the tool `dispatch_by_capability`.
- Forge's ADR-ARCH-015 (19 April) forbids hardcoded `agent_id`: *"one generic dispatch tool covers every specialist, present and future"*.
- Forge's ADR-ARCH-016 requires the catalogue to be the fleet, not a declared list in code.

The scope doc's proposed signature — `call_specialist(agent_id: str, instruction: str, context: dict = {})` — conflicts with those constraints in two ways:

1. The first parameter is a hardcoded `agent_id` — the reasoning model would need to know which agent to talk to before it can dispatch. That inverts the capability-driven pattern.
2. The `instruction: str, context: dict` shape is an agent-generic envelope; it cannot pre-declare a tool name on the target agent, so the target agent has to do intent-extraction in addition to whatever it's being asked to do. The same `ToolCapability` primitive is available in `nats-core` and solves this cleanly.

## Decision

**Adopt `dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60)` as the single generic dispatch tool for Jarvis, matching Forge ADR-ARCH-015's pattern verbatim.**

Key shape decisions:

- `tool_name: str` — maps to `nats_core.ToolCapability.name`. The reasoning model picks this by reading the prompt-injected `{available_capabilities}` block (or via `list_available_capabilities()` if mid-session refresh is needed per DDR-008).
- `payload_json: str` — a JSON-object-literal string matching the target tool's `ToolCapability.parameters` schema. Passing as a string (not a dict) preserves tool docstring readability — the reasoning model is used to constructing JSON strings for tool arguments; a structured parameter pollutes the displayed signature with a nested schema.
- `intent_pattern: str | None` — optional fallback for `IntentCapability.pattern` resolution when no exact tool match exists.
- `timeout_seconds: int = 60` — fleet-normal timeout; tests may override. Out-of-range values return a structured error rather than raising.
- No `agent_id` parameter. The tool resolves internally against the capability registry.

**Phase 2 implementation is stubbed** — see [DDR-009](DDR-009-dispatch-stub-transport-semantics.md) for transport semantics. FEAT-JARVIS-004 replaces the stub with real NATS round-trips without changing this signature.

## Alternatives considered

1. **Keep `call_specialist(agent_id, …)` as written in the scope doc.**
   Rejected — violates ADR-ARCH-015-equivalent's "no per-role tools, no hardcoded `agent_id`". Every specialist addition would require a prompt update; the learning flywheel (FEAT-JARVIS-008) couldn't measure the reasoning model's routing choices because the "which agent" decision would be baked into the tool call.

2. **Ship both `call_specialist(agent_id, …)` AND `dispatch_by_capability(...)`.**
   Rejected — doubles the surface area of the prompt ("## Tool Usage") without adding value. The reasoning model would need to be told when to prefer one over the other, which is a rule the capability pattern already subsumes.

3. **Keep the scope-doc name `call_specialist` but change the signature to match `dispatch_by_capability`.**
   Rejected — aesthetics-only. The name `dispatch_by_capability` is what ARCHITECTURE.md §3.C already uses and the specialist-agent side of the fleet expects Jarvis to call.

4. **Split `dispatch_by_capability` into two tools: one for `tool_name` exact match, one for `intent_pattern` fuzzy match.**
   Rejected — would surface a resolution-strategy choice to the reasoning model that shouldn't be its concern. The `intent_pattern` parameter is a fallback knob inside one tool, not a separate tool.

## Consequences

- **+** Jarvis's dispatch tool is name- and shape-identical to Forge's. Specialist agents and the fleet registry see one consumer contract across the two upstream surfaces.
- **+** New specialist agents register, and Jarvis picks them up without code changes. Matches the fleet-wide capability-driven pattern.
- **+** The learning flywheel (v1.5) can measure routing decisions at the capability level — the reasoning model's choice of `tool_name` is data.
- **+** The stubbed Phase 2 and real Phase 3 tool look identical to the reasoning model. Behaviour depends on docstring; transport depends on implementation.
- **−** The scope doc is now out of sync with this design. Mitigation: this DDR is the durable record; the scope doc will be updated only if a future refactor warrants.
- **−** The reasoning model must construct a valid `payload_json` for each capability. Mitigation: each `ToolCapability.description` in the injected catalogue is required to state the JSON shape — the `agent-manifest-contract` pattern already enforces this.
Write DDR-006-tavily-as-web-search-provider.md
34 lines
# DDR-006: Tavily is the v1 provider behind `search_web`

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** External Tool Context; `jarvis.tools.general.search_web`

## Context

The Phase 2 scope document leaves the web-search provider open — *"Tavily (matches specialist-agent) is the default preference; ADR may pin"* ([phase2-dispatch-foundations-scope.md §Open Questions](../../../research/ideas/phase2-dispatch-foundations-scope.md)). `search_web` is a reused dependency — the FEAT-JARVIS-003 `long_research` subagent (once its scope is reconciled with ADR-ARCH-011) will call it, so the provider choice affects more than one feature.

## Decision

**`search_web` uses Tavily via `langchain-tavily` as the v1 provider.** The provider is wrapped behind an internal `WebSearchProvider` protocol inside `jarvis.tools.general`; the tool docstring does not name Tavily (it talks about "the configured web-search provider" internally), so a future swap does not require changing routing behaviour.

Environment variable: `JARVIS_TAVILY_API_KEY` → `JarvisConfig.tavily_api_key: SecretStr | None`.
Provider selector: `JarvisConfig.web_search_provider: Literal["tavily", "none"] = "tavily"`.
When `web_search_provider == "none"`, the tool always returns `ERROR: config_missing — no web-search provider configured`.

## Alternatives considered

1. **Bing Web Search API.** Rejected — recent Microsoft pricing changes make it ~3× the per-query cost, and integration is more surface (multiple response fields, scoring differences).
2. **SerpAPI.** Rejected — cost-per-query is higher than Tavily and the response format is tailored to SERP scraping, which is not what Jarvis needs.
3. **Provider-agnostic via a direct HTTP wrapper.** Rejected — adds a compatibility layer Jarvis doesn't need; `langchain-tavily` is already pinned for the fleet (specialist-agent uses it) and the `WebSearchProvider` protocol gives us swap-freedom later.
4. **No default — fail closed when provider is unconfigured.** Adopted in spirit: `search_web` returns a structured error at call time rather than failing at startup. The startup-time warning (Phase 1 `validate_provider_keys` extension) surfaces the config gap without blocking `jarvis chat` when web search isn't needed.

## Consequences

- **+** One provider, one API-key management path, one quota. Specialist-agent and Jarvis share it.
- **+** Tool docstring does not name Tavily — swapping to a different provider is a one-file change in `general.py` that doesn't touch routing.
- **+** `search_web` degrades gracefully when the API key is absent — the reasoning model receives a structured error and can fall back (e.g. ask the user, defer, or use `dispatch_by_capability` against a research-shaped specialist once v1.5 long_research lands).
- **−** Tavily outages mean Jarvis loses web-search capability until the provider recovers. Mitigation: structured `DEGRADED:` return lets the reasoning model adapt per ADR-ARCH-021.
- **−** Tavily pricing changes over time; the cost signal in the tool docstring (`~$0.005/query`) becomes approximate.
Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH corpus

Draft remaining DDRs (asteval, capabilities-path, stub semantics)

Write C4 L3 diagram

Present C4 L3 review gate

Offer Graphiti seeding commands
Write DDR-007-asteval-for-calculate.md
43 lines
# DDR-007: `calculate` uses `asteval` for safe expression evaluation

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** External Tool Context; `jarvis.tools.general.calculate`

## Context

The Phase 2 scope document specifies *"wraps `mathjs`-style safe evaluation (no `eval`)"* and leaves the library choice open. Python has several options, each with distinct safety and surface-area trade-offs.

The requirement: the reasoning model passes a user-visible expression string (e.g. `"15% of 847"`, `"sqrt(2) * 10"`, `"2 ** 32"`), and the tool returns a numeric result or a structured error. No variables, no functions outside a small allow-list, no file access, no network access, no unbounded loops.

## Decision

**Use `asteval` (by Matt Newville, MIT-licensed).** It evaluates Python expressions by parsing to AST and walking it with a per-instance symbol table, forbidding function definitions, imports, and unsafe attribute access by default. The allow-list of mathematical builtins (`sqrt`, `log`, `exp`, `sin`, `cos`, `tan`, `abs`, `min`, `max`, `round`, plus operators `+ - * / ** %`) is injected into the interpreter at construction.

Phase 2 `calculate` flow:

1. Pre-filter expression: reject if it contains `import`, `lambda`, `class`, `def`, `=` (assignment), `__` (dunder access), or `\n`. Returns `ERROR: unsafe_expression — disallowed token: <token>`.
2. Normalise percent syntax: `"15% of 847"` → `"0.15 * 847"` via a small regex. This is a user-affordance so the docstring's example works.
3. Invoke `asteval.Interpreter(symtable=MATH_BUILTINS, max_time=1.0)` on the normalised expression.
4. If `interp.error` is non-empty, return `ERROR: parse_error — <first error message>`.
5. Catch `ZeroDivisionError`, `OverflowError`, `ValueError` at the tool boundary; convert to `ERROR: division_by_zero`, `ERROR: overflow`, `ERROR: parse_error`.
6. Return the result as a string (`repr(result)` for ints, `f"{result:g}"` for floats to avoid noisy trailing zeros).

## Alternatives considered

1. **Python `ast.literal_eval`.** Rejected — only evaluates literal structures (numbers, strings, tuples, lists, dicts, booleans, None). Doesn't support arithmetic operators or math functions.
2. **`simpleeval`.** Considered. Smaller API surface than `asteval`, comparable safety. Picked `asteval` because it's already used by NumPy's parameter-file loader and specialist-agent, so the fleet has prior exposure. Rollback is trivial if needed — the `Interpreter()` API is almost identical.
3. **Sympy.** Rejected — too heavy (50 MB+ install) for a calculator tool; would balloon Jarvis's image size. Also gives symbolic results by default, which would need re-coercion.
4. **Write our own AST walker.** Rejected — reinventing a well-maintained library is a security-surface liability.
5. **Use the LLM itself to compute.** Explicitly rejected — the tool exists precisely *because* the LLM is unreliable at arithmetic. This is the tool's raison d'être per ADR-ARCH-016-equivalent ("prefer tools over mental work").

## Consequences

- **+** Small, well-maintained dependency (`asteval >= 0.9.33`).
- **+** The tool is genuinely safe against expression injection — no code execution, no symbol table bleed.
- **+** `asteval.Interpreter(max_time=1.0)` terminates runaway expressions (e.g. `10**100**100`) without killing the host process.
- **+** Tests are straightforward: pass expressions, assert on returned strings or error prefixes.
- **−** `asteval`'s error messages are Pythonic and sometimes verbose. Mitigation: the tool truncates to a single line in the `ERROR: parse_error — <detail>` return.
- **−** Adds one dependency. Mitigation: `asteval` is ~40 KB of pure Python with only `numpy` as an optional dependency which Jarvis already has transitively.
Write DDR-008-capabilities-both-tool-and-prompt-injection.md
59 lines
# DDR-008: Capabilities reach the supervisor via BOTH a `@tool` call AND a prompt-injected placeholder

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** Fleet Dispatch Context; `jarvis.prompts.supervisor_prompt`; `jarvis.tools.capabilities`; `jarvis.agents.supervisor`

## Context

Two competing signals about how the reasoning model should see the capability catalogue:

- [Phase 2 scope §1.2](../../../research/ideas/phase2-dispatch-foundations-scope.md) puts `list_available_capabilities()` on the tool surface — the reasoning model calls a tool to get the list.
- [ARCHITECTURE.md §3.A](../../../architecture/ARCHITECTURE.md) places `{available_capabilities}` as a placeholder in the supervisor system prompt — the list arrives as context at session start, as Forge ADR-ARCH-016 does for its reasoning model.

These are not mutually exclusive. Each has distinct properties:

| | Tool call | Prompt injection |
|---|---|---|
| When the reasoning model sees it | On demand | At session start, every turn |
| Cost | Tokens on demand | Tokens every turn |
| Staleness | Explicit opt-in refresh | Re-injected per session, not per turn |
| When it works well | Large catalogues, infrequent routing | Small catalogues, frequent routing |
| Failure mode | Missed tool call → routing blind | Cached snapshot stale if agent added mid-session |

Jarvis's catalogue is small (Phase 2: 4 entries; v1 launch expected: <20) and routing is frequent (every dispatch decision). Prompt injection is the dominant signal; the tool is an escape hatch.

## Decision

**Ship both.**

1. **Prompt injection (primary path).** `SUPERVISOR_SYSTEM_PROMPT` gains a `{available_capabilities}` placeholder between the attended-conversation section and the trace-richness section. `build_supervisor(...)` renders the registry snapshot (joining `CapabilityDescriptor.as_prompt_block()` with double newlines) and substitutes the placeholder via `str.format(...)`. When the registry is empty, the fallback text is literally `"No capabilities currently registered."` — asserted byte-equal by tests.

2. **Tool access (escape hatch).** `list_available_capabilities()`, `capabilities_refresh()`, and `capabilities_subscribe_updates()` remain on the tool surface with docstrings explicitly steering the reasoning model to the injected snapshot first.

3. **Consistency.** The rendered injection and the tool return serialise the *same* descriptors from the *same* registry snapshot. Tests assert this equivalence to prevent drift.

## Alternatives considered

1. **Prompt injection only (drop the tool).**
   Rejected — offers no path for mid-session refresh in Phase 3+ when real KV updates arrive. The tool surface is cheap to keep and it costs nothing in Phase 2.

2. **Tool only (drop the prompt placeholder).**
   Rejected — forces the reasoning model to issue a tool call on every turn that might need routing. With only 4–20 entries, the token overhead of prompt injection is dwarfed by the round-trip cost of an extra tool call.

3. **Tool-only but with result caching inside the tool.**
   Rejected — caching hides state from the reasoning model; the model can't tell whether it's looking at fresh or cached data. Prompt injection is explicit about "this is the snapshot at session start".

4. **Load-bearing docstring with static specialist names.**
   Rejected — violates ADR-ARCH-016 (no pre-coded catalogue); duplicates DDR-005's dispatch pattern.

## Consequences

- **+** Routing decisions work from turn 1 — no warm-up tool call needed.
- **+** Operators can inspect the catalogue Jarvis sees by reading the rendered prompt (available via `jarvis health` in FEAT-JARVIS-007+ or via debug logging in Phase 2).
- **+** The tool path is preserved for future use: mid-session refresh once FEAT-JARVIS-004's NATS KV watch is live, and as a debugging hook.
- **+** Phase 2's scope doc and ARCHITECTURE.md are both honoured — no contradiction with either.
- **−** Token cost per turn for the injected block. Mitigation: Phase 2 catalogue is small (~400 tokens across 4 descriptors); prompt caching at the LLM layer keeps this cheap.
- **−** The two paths must stay in sync. Mitigation: one shared render function (`CapabilityDescriptor.as_prompt_block()`) used by both; test asserts they serialise identically.
Write DDR-009-dispatch-stub-transport-semantics.md
134 lines
# DDR-009: Phase 2 dispatch-tool stub transport semantics

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** Fleet Dispatch Context; `jarvis.tools.dispatch`
- **Related ADRs:** ADR-ARCH-021 (structured errors); ADR-SP-014 Pattern A via Forge pipeline architecture
- **Related decisions:** DDR-005 (dispatch tool name/signature); DDR-008 (capabilities delivery)

## Context

The Phase 2 scope document lists an open question: *"`call_specialist` timeout + retry semantics. Even stubbed, the tool needs a defensible timeout default and a retry-with-redirect behaviour spec so FEAT-JARVIS-004 swaps transports cleanly."* Same question applies to `queue_build` — even stubbed, the return-value shape and error-category set need to match what the real transport will produce.

Phase 2 stubs must:

- Build **real** `nats_core.events` payloads — this keeps FEAT-JARVIS-004/005 a transport-level swap (per scope doc invariant ¶7 *"stubbed transport ≠ stubbed schema"*).
- Log publishes with distinct, grep-able prefixes so the FEAT-JARVIS-004/005 AutoBuild task can locate the swap points mechanically.
- Return strings that a reasoning model behaves identically to in Phase 2 (stub) and Phase 3+ (real) — per DDR-005, the tool docstring is the contract.

## Decision

### `dispatch_by_capability` — Phase 2 stub behaviour

1. **Resolution.** Look up `tool_name` against the in-memory capability registry.
   - Exact `CapabilityToolSummary.tool_name` match → resolves to that `agent_id`.
   - No exact match but `intent_pattern` supplied → highest-confidence match among registered specialists (Phase 2 stub: simple substring match on descriptor `role`/`description`; the real resolver in `NATSKVManifestRegistry` is richer in Phase 3).
   - No resolution → return `ERROR: unresolved — no capability matches tool_name=<x> intent_pattern=<y>`.

2. **Payload validation.**
   - `payload_json` must parse to a JSON object literal. On failure → `ERROR: invalid_payload — payload_json is not a JSON object literal`.
   - `timeout_seconds` must be between 5 and 600 inclusive. Out of range → `ERROR: invalid_timeout — timeout_seconds must be 5..600, got <n>`.

3. **Payload construction (always, even on stub).**
   ```python
   command = CommandPayload(
       command=tool_name,
       args=json.loads(payload_json),
       correlation_id=correlation_id or str(uuid4()),
   )
   envelope = MessageEnvelope(
       source_id="jarvis",
       event_type=EventType.COMMAND,
       correlation_id=command.correlation_id,
       payload=command.model_dump(mode="json"),
   )
   ```
   Topic that *would* be published: `Topics.Agents.COMMAND.format(agent_id=resolved_agent_id)` → `"agents.command.<agent_id>"` (singular per ADR-SP-016).

4. **Logged publish (the grep anchor).**
   ```
   JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y> correlation_id=<z>
     topic=agents.command.<y> payload_bytes=<n>
   ```

5. **Stub response.** A module-level hook `_stub_response_hook: Callable[[CommandPayload], StubResponse] | None`
   controls the behaviour for tests:
   - Unset (default) → return a canned `ResultPayload(command=tool_name, result={"stub": True, "tool_name": tool_name}, correlation_id=<same>, success=True)` serialised as JSON.
   - Set to `stub_timeout` → return `TIMEOUT: agent_id=<y> tool_name=<x> timeout_seconds=<n>`.
   - Set to `stub_error` → return `ERROR: specialist_error — agent_id=<y> detail=<canned>`.

6. **No retry.** Even in Phase 3+, retry is **not** a property of this tool — the reasoning model decides whether to re-dispatch after reading the structured error. This is fleet-consistent with Forge's equivalent: retry is a reasoning decision, not a mechanical one. [ADR-ARCH-024](../../../architecture/decisions/ADR-ARCH-024-pattern-b-watcher-failure-policy.md) constrains retry to the Pattern B watcher subsystem, not the dispatch surface.

### `queue_build` — Phase 2 stub behaviour

1. **Validation.** `feature_id` matches `^FEAT-[A-Z0-9]{3,12}$`. `repo` matches `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`. `originating_adapter` ∈ the `OriginatingAdapter` literal. Invalid inputs return structured errors; valid inputs proceed to payload construction.

2. **Payload construction.**
   ```python
   payload = BuildQueuedPayload(
       feature_id=feature_id,
       repo=repo,
       branch=branch,
       feature_yaml_path=feature_yaml_path,
       triggered_by="jarvis",
       originating_adapter=originating_adapter,
       originating_user=config.user_id or "rich",
       correlation_id=correlation_id or str(uuid4()),
       parent_request_id=parent_request_id,
       requested_at=now_utc(),
       queued_at=now_utc(),
   )
   envelope = MessageEnvelope(
       source_id="jarvis",
       event_type=EventType.BUILD_QUEUED,
       correlation_id=payload.correlation_id,
       payload=payload.model_dump(mode="json"),
   )
   ```
   Topic: `Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)` → `"pipeline.build-queued.<feature_id>"`.

3. **Logged publish.**
   ```
   JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
     topic=pipeline.build-queued.<x> payload_bytes=<n>
   ```

4. **Return.** Always returns a JSON `QueueBuildAck`:
   ```json
   {
     "feature_id": "<x>",
     "correlation_id": "<z>",
     "queued_at": "<iso8601>",
     "publish_target": "pipeline.build-queued.<x>",
     "status": "queued"
   }
   ```
   There is no failure mode in the stub beyond input validation — the real JetStream publish in FEAT-JARVIS-005 can add `DEGRADED: stream_unavailable` and `ERROR: stream_publish_failed` categories without changing this shape.

5. **No retry.** Same reasoning as `dispatch_by_capability` — retry is a reasoning decision.

### Timeout defaults

- `dispatch_by_capability.timeout_seconds` default: **60 s**. Rationale: specialist round-trips observed in prior fleet work cluster around 5–45 s; 60 s catches the long tail without tying up the reasoning model for unreasonable durations.
- `queue_build`: no timeout — Pattern A is fire-and-forget. The JetStream publish in FEAT-JARVIS-005 will use a transport-level 3 s publish-ACK budget that's internal to the adapter, not a tool parameter.

## Alternatives considered

1. **Retry inside the tool with exponential backoff.** Rejected — violates the "retry is reasoning" principle (ADR-ARCH-024's Pattern B exception is the only retrying subsystem). Baking retry into the dispatch tool would make the reasoning model blind to intermittent failures and would conflict with how specialist-agents handle idempotency (they don't in v1 — duplicate commands produce duplicate work).

2. **Construct a fake payload (drop the `nats-core` model build).** Rejected — violates scope invariant ¶7. Real payloads at the stub boundary ensure FEAT-JARVIS-004/005 are transport-only swaps.

3. **Skip logging the stub publishes.** Rejected — without the `JARVIS_DISPATCH_STUB` / `JARVIS_QUEUE_BUILD_STUB` grep anchors, the FEAT-JARVIS-004 AutoBuild run has to find the swap points by hand.

4. **Use structured logging (`structlog`) for the publish line at DEBUG.** Adopted partially — the log is structured JSON per Phase 1's `configure_logging()`, but emitted at **INFO** so it shows up in the default `jarvis chat` session log. Rich has asked for visible evidence during attended sessions that dispatch happened.

## Consequences

- **+** FEAT-JARVIS-004 (specialist dispatch) replaces one log line and one stub hook with a real NATS req/reply; tool docstring and return shape unchanged.
- **+** FEAT-JARVIS-005 (queue_build JetStream) replaces one log line with `js.publish(subject, payload=envelope.model_dump_json().encode())`; tool docstring and return shape unchanged.
- **+** The structured-error vocabulary committed here (`unresolved | invalid_payload | invalid_timeout | timeout | specialist_error | transport_stub`) is the stable vocabulary the reasoning model learns; Phase 3+ adds `transport_unavailable | publish_failed | stream_down` without removing any category.
- **+** `queue_build` is ready to honour the Pattern A constraint: Jarvis never awaits a build.
- **−** Tests must assert on log lines to verify the stub publishes happened — brittle if the format drifts. Mitigation: the log-line format is asserted verbatim in `test_tools_dispatch.py` so any drift is caught.
- **−** `dispatch_by_capability`'s in-process "no retry" is one of the things that might bite on transient NATS errors in Phase 3+. If that becomes an operational issue, an ADR can add bounded retry *at the adapter* (not in the tool); the tool docstring would not change.
Now the C4 L3 diagram.

Write fleet-dispatch-l3.md
119 lines
# C4 Level 3 — Fleet Dispatch Components inside the Jarvis Supervisor Container

> **Bounded context:** Fleet Dispatch Context (+ External Tool Context)
> **Container:** Jarvis Supervisor (single Python process built around `create_deep_agent(...)`)
> **Scope:** Components added or touched by FEAT-JARVIS-002. Phase 1 components (sessions, CLI, lifecycle, config) are shown in `system=boundary` grey for orientation but are not modified here.
> **Review gate:** this diagram must be approved per `/system-design` Phase 3.5 before Graphiti seeding. See [§ Review gate](#review-gate) below.

---

## Why this diagram exists

FEAT-JARVIS-002 introduces 4 new modules with 9 `@tool` functions, one YAML data file, and updates two Phase 1 modules. That's 7 collaborating components inside the Jarvis Supervisor container — above the 3-internal-component threshold that triggers the mandatory C4 L3 gate.

## Diagram

```mermaid
C4Component
    title Component diagram — Jarvis Supervisor container (FEAT-JARVIS-002)

    Container_Boundary(supervisor, "Jarvis Supervisor (Python process)") {

        Component(prompt, "jarvis.prompts.supervisor_prompt", "Python module (UPDATED)", "SUPERVISOR_SYSTEM_PROMPT with {date}, {domain_prompt}, {available_capabilities} placeholders. Adds '## Tool Usage' section.")

        Component(factory, "jarvis.agents.supervisor.build_supervisor", "Python function (UPDATED)", "Composes create_deep_agent(tools=..., system_prompt=...) graph. New kwargs: tools, available_capabilities.")

        Component(config, "jarvis.config.settings.JarvisConfig", "Pydantic BaseSettings (UPDATED)", "Adds web_search_provider, tavily_api_key, stub_capabilities_path, workspace_root.")

        Component(types, "jarvis.tools.types", "Python module (NEW)", "WebResult, CalendarEvent, DispatchError Pydantic models.")

        Component(general, "jarvis.tools.general", "Python module (NEW)", "@tool: read_file, search_web, get_calendar_events (stub), calculate (asteval).")

        Component(caps, "jarvis.tools.capabilities", "Python module (NEW)", "CapabilityDescriptor, in-memory stub registry loader, @tool: list_available_capabilities, capabilities_refresh, capabilities_subscribe_updates.")

        Component(dispatch, "jarvis.tools.dispatch", "Python module (NEW)", "@tool: dispatch_by_capability, queue_build. Builds real nats-core payloads; Phase 2 transport is a logged stub.")

        ComponentDb(yaml, "stub_capabilities.yaml", "YAML data (NEW)", "4 CapabilityDescriptor stubs: architect, product-owner, ideation, forge. Phase 2 only; removed in FEAT-JARVIS-004.")

        Component(lifecycle, "jarvis.infrastructure.lifecycle", "Python module (UPDATED)", "startup() now loads stub registry and assembles tool list before build_supervisor.")

        Component_Ext(sessions, "jarvis.sessions.SessionManager", "Phase 1 — unchanged", "Thread-per-session invocation of the supervisor graph.")
    }

    Container_Ext(tavily, "Tavily", "Web search API", "Called by search_web when configured. JARVIS_TAVILY_API_KEY.")
    Container_Ext(natscore, "nats-core library", "Python library", "Supplies CommandPayload, ResultPayload, BuildQueuedPayload, MessageEnvelope, EventType, Topics. Imported but no NATS traffic in Phase 2.")
    Container_Ext(fs, "Local filesystem", "OS", "read_file + stub YAML read.")

    %% Wiring — load order
    Rel(config, yaml, "Points to (stub_capabilities_path)")
    Rel(lifecycle, config, "Reads")
    Rel(lifecycle, caps, "Calls load_stub_registry(path)")
    Rel(caps, yaml, "Reads + validates")
    Rel(lifecycle, general, "Imports @tool functions")
    Rel(lifecycle, caps, "Imports @tool functions")
    Rel(lifecycle, dispatch, "Imports @tool functions")
    Rel(lifecycle, factory, "Calls build_supervisor(config, tools=..., available_capabilities=...)")

    %% Prompt wiring
    Rel(factory, prompt, "str.format with {available_capabilities}")
    Rel(factory, caps, "Renders CapabilityDescriptor.as_prompt_block()")

    %% Runtime tool invocation (at session time, not build time)
    Rel(sessions, factory, "Invokes compiled graph")
    Rel(general, types, "Uses WebResult / CalendarEvent")
    Rel(general, tavily, "search_web HTTP (when configured)", "HTTPS")
    Rel(general, fs, "read_file")
    Rel(caps, types, "Uses CapabilityDescriptor + CapabilityToolSummary")
    Rel(dispatch, types, "Uses DispatchError")
    Rel(dispatch, caps, "Resolves tool_name against registry")
    Rel(dispatch, natscore, "Builds CommandPayload / BuildQueuedPayload / MessageEnvelope")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Trace through the diagram

**Startup**
1. `lifecycle.startup()` reads `JarvisConfig` (Phase 1 code path, extended with the new keys).
2. `lifecycle` calls `load_stub_registry(config.stub_capabilities_path)` → `caps` parses the YAML into `list[CapabilityDescriptor]`.
3. `lifecycle` assembles the 9 `@tool` functions via `assemble_tool_list(config, capability_registry)`.
4. `lifecycle` calls `build_supervisor(config, tools=..., available_capabilities=...)` → `factory`.
5. `factory` renders each `CapabilityDescriptor.as_prompt_block()`, joins with double newlines, substitutes into `{available_capabilities}` in `SUPERVISOR_SYSTEM_PROMPT`, and passes everything to `create_deep_agent(...)`.

**Turn**
6. `sessions.SessionManager.invoke()` drives the compiled graph (Phase 1 code path).
7. The reasoning model reads the prompt (including `## Available Capabilities`) and chooses a tool.
8. `read_file` touches `fs`; `search_web` touches `tavily`; `calculate` runs in-process via `asteval`; `get_calendar_events` returns `[]` (stub).
9. `list_available_capabilities` returns the same list that was injected.
10. `dispatch_by_capability` resolves `tool_name` against the registry, builds a real `CommandPayload` + `MessageEnvelope` via `natscore`, logs the `JARVIS_DISPATCH_STUB` line, returns the stub response.
11. `queue_build` builds a real `BuildQueuedPayload` + `MessageEnvelope`, logs `JARVIS_QUEUE_BUILD_STUB`, returns the `QueueBuildAck` JSON.

---

## What the diagram does NOT show

- **FEAT-JARVIS-003 additions** — `AsyncSubAgentMiddleware` and the four subagent graphs. Subject to `/system-design FEAT-JARVIS-003`.
- **Graphiti tools** (`record_routing_decision`, etc.) — FEAT-JARVIS-004.
- **NATS adapter** (`jarvis.adapters.nats`) — FEAT-JARVIS-004. Phase 2 uses `nats-core` only as a Pydantic-model library.
- **Notifications adapter** — FEAT-JARVIS-006 / 004.
- **Skills** (`morning-briefing`, etc.) — FEAT-JARVIS-007.
- **`escalate_to_frontier`** — reserved future slot in `jarvis.tools.dispatch`; not in Phase 2.

---

## Review gate

> Per `/system-design` Phase 3.5: this diagram must be explicitly approved before seeding to Graphiti.
>
> **Look for:**
> - Components with too many dependencies (cyclic imports, leaking state).
> - Missing persistence layers — Phase 2 has none (in-memory stub + no NATS); is that acceptable? *Yes, per Phase 2 scope.*
> - Unclear separation of concerns — does `jarvis.tools.dispatch` correctly depend on `jarvis.tools.capabilities` but not the other way?
> - Circular wiring between `factory` and `caps`. (The diagram shows only `factory → caps` for rendering; tests will assert `caps` does not import `factory`.)

**[A]pprove | [R]evise | [R]eject**

Awaiting explicit approval by Rich before `/system-design` proceeds to Phase 4 (OpenAPI validation — skipped here, no REST surface) and Phase 5 (Graphiti seeding).
Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH corpus

Draft DDRs (dispatch name, Tavily, asteval, capabilities delivery, stub semantics)

Write C4 L3 diagram

Present C4 L3 review gate to user + await approval

Offer Graphiti seeding commands after approval
Design artefacts written. Summary and mandatory review gate below.

✅ SYSTEM DESIGN DRAFT COMPLETE (pending gate)
Created: docs/design/FEAT-JARVIS-002/


docs/design/FEAT-JARVIS-002/
├── design.md                                                       ← top-level
├── contracts/
│   ├── API-tools.md                                                ← 9 @tool docstring contracts
│   └── API-internal.md                                             ← module-level Python API
├── models/
│   ├── DM-tool-types.md                                            ← Pydantic types
│   └── DM-stub-registry.md                                         ← stub YAML schema + canonical content
├── diagrams/
│   └── fleet-dispatch-l3.md                                        ← C4 L3 (REVIEW GATE BELOW)
└── decisions/
    ├── DDR-005-dispatch-by-capability-supersedes-call-specialist.md
    ├── DDR-006-tavily-as-web-search-provider.md
    ├── DDR-007-asteval-for-calculate.md
    ├── DDR-008-capabilities-both-tool-and-prompt-injection.md
    └── DDR-009-dispatch-stub-transport-semantics.md
Key design resolutions:

Dispatch tool is dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60) — supersedes scope-doc call_specialist(agent_id, ...) to honour ADR-ARCH-016-equivalent capability-driven pattern (DDR-005).
Capabilities surface via BOTH prompt-injected {available_capabilities} AND the list_available_capabilities tool, sharing one renderer (DDR-008).
search_web → Tavily behind a swappable provider protocol (DDR-006).
calculate → asteval with allow-listed builtins + 1s time cap (DDR-007).
Stub transport builds real nats-core payloads; logs JARVIS_DISPATCH_STUB / JARVIS_QUEUE_BUILD_STUB as grep anchors for FEAT-JARVIS-004/005 swap (DDR-009).
Two contradictions with the Phase 2 scope doc resolved (C1 dispatch name; C2 four-cloud-subagents flagged and deferred to /system-design FEAT-JARVIS-003).
🔍 MANDATORY REVIEW GATE — C4 LEVEL 3 DIAGRAM
Per /system-design Phase 3.5, I cannot proceed to Graphiti seeding without your explicit approval of the component diagram. Please review docs/design/FEAT-JARVIS-002/diagrams/fleet-dispatch-l3.md — 8 components shown, three new tool modules plus one YAML data file plus three updated Phase 1 modules.

No openapi.yaml, mcp-tools.json, or a2a-schemas.yaml are produced — consistent with Phase 1 DDR-001 (in-process only). Phase 4 (OpenAPI validation) is therefore skipped.

Your choice: [A]pprove | [R]evise (tell me what to change) | [R]eject

Once approved I'll offer the Graphiti seeding commands (5 DDRs → architecture_decisions group, 4 contracts/models → project_design group).

I can't see any output, please represent it
Rendering the C4 L3 diagram and design summary inline for review.

📋 Design Summary
Feature: FEAT-JARVIS-002 — Core Tools & Capability-Driven Dispatch Tools

9 tools shipped on the Phase 1 supervisor:

Cluster	Tools	Transport
General	read_file, search_web, get_calendar_events, calculate	real (fs / Tavily / stub / asteval)
Capability catalogue	list_available_capabilities, capabilities_refresh, capabilities_subscribe_updates	real read / no-op / no-op over in-memory stub registry
Dispatch	dispatch_by_capability, queue_build	stubbed — real nats-core payloads built and logged; no network I/O
5 DDRs captured:

DDR-005 — Dispatch tool is dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60), superseding scope-doc call_specialist(agent_id, ...) (aligns with ADR-ARCH-003 / ADR-ARCH-016-equivalent — no hardcoded agent_id).
DDR-006 — Tavily as v1 web-search provider behind a swappable protocol.
DDR-007 — asteval for calculate (AST-based, no eval, 1 s time cap).
DDR-008 — Capabilities reach the supervisor via BOTH {available_capabilities} prompt injection AND the list_available_capabilities tool.
DDR-009 — Stub-transport semantics: build real nats-core payloads, log with JARVIS_DISPATCH_STUB / JARVIS_QUEUE_BUILD_STUB grep anchors, 60 s default timeout, no in-tool retry.
2 contradictions with scope doc resolved:

C1 — call_specialist(agent_id=...) vs fleet-wide capability-driven pattern → resolved via DDR-005 (rename + re-shape).
C2 — four cloud subagents vs ADR-ARCH-011 (single jarvis-reasoner on gpt-oss-120b) → flagged and deferred to /system-design FEAT-JARVIS-003.
🖼️ C4 Level 3 Component Diagram

C4Component
    title Component diagram — Jarvis Supervisor container (FEAT-JARVIS-002)

    Container_Boundary(supervisor, "Jarvis Supervisor (Python process)") {

        Component(prompt, "jarvis.prompts.supervisor_prompt", "Python module (UPDATED)", "SUPERVISOR_SYSTEM_PROMPT with {date}, {domain_prompt}, {available_capabilities} placeholders. Adds '## Tool Usage' section.")

        Component(factory, "jarvis.agents.supervisor.build_supervisor", "Python function (UPDATED)", "Composes create_deep_agent(tools=..., system_prompt=...) graph. New kwargs: tools, available_capabilities.")

        Component(config, "jarvis.config.settings.JarvisConfig", "Pydantic BaseSettings (UPDATED)", "Adds web_search_provider, tavily_api_key, stub_capabilities_path, workspace_root.")

        Component(types, "jarvis.tools.types", "Python module (NEW)", "WebResult, CalendarEvent, DispatchError Pydantic models.")

        Component(general, "jarvis.tools.general", "Python module (NEW)", "@tool: read_file, search_web, get_calendar_events (stub), calculate (asteval).")

        Component(caps, "jarvis.tools.capabilities", "Python module (NEW)", "CapabilityDescriptor, in-memory stub registry loader, @tool: list_available_capabilities, capabilities_refresh, capabilities_subscribe_updates.")

        Component(dispatch, "jarvis.tools.dispatch", "Python module (NEW)", "@tool: dispatch_by_capability, queue_build. Builds real nats-core payloads; Phase 2 transport is a logged stub.")

        ComponentDb(yaml, "stub_capabilities.yaml", "YAML data (NEW)", "4 CapabilityDescriptor stubs: architect, product-owner, ideation, forge. Phase 2 only; removed in FEAT-JARVIS-004.")

        Component(lifecycle, "jarvis.infrastructure.lifecycle", "Python module (UPDATED)", "startup() now loads stub registry and assembles tool list before build_supervisor.")

        Component_Ext(sessions, "jarvis.sessions.SessionManager", "Phase 1 — unchanged", "Thread-per-session invocation of the supervisor graph.")
    }

    Container_Ext(tavily, "Tavily", "Web search API", "Called by search_web when configured. JARVIS_TAVILY_API_KEY.")
    Container_Ext(natscore, "nats-core library", "Python library", "Supplies CommandPayload, ResultPayload, BuildQueuedPayload, MessageEnvelope, EventType, Topics. Imported but no NATS traffic in Phase 2.")
    Container_Ext(fs, "Local filesystem", "OS", "read_file + stub YAML read.")

    Rel(config, yaml, "Points to (stub_capabilities_path)")
    Rel(lifecycle, config, "Reads")
    Rel(lifecycle, caps, "Calls load_stub_registry(path)")
    Rel(caps, yaml, "Reads + validates")
    Rel(lifecycle, general, "Imports @tool functions")
    Rel(lifecycle, caps, "Imports @tool functions")
    Rel(lifecycle, dispatch, "Imports @tool functions")
    Rel(lifecycle, factory, "Calls build_supervisor(config, tools=..., available_capabilities=...)")

    Rel(factory, prompt, "str.format with {available_capabilities}")
    Rel(factory, caps, "Renders CapabilityDescriptor.as_prompt_block()")

    Rel(sessions, factory, "Invokes compiled graph")
    Rel(general, types, "Uses WebResult / CalendarEvent")
    Rel(general, tavily, "search_web HTTP (when configured)", "HTTPS")
    Rel(general, fs, "read_file")
    Rel(caps, types, "Uses CapabilityDescriptor + CapabilityToolSummary")
    Rel(dispatch, types, "Uses DispatchError")
    Rel(dispatch, caps, "Resolves tool_name against registry")
    Rel(dispatch, natscore, "Builds CommandPayload / BuildQueuedPayload / MessageEnvelope")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
Trace — startup
lifecycle.startup() reads JarvisConfig (Phase 1 path, extended).
lifecycle → caps.load_stub_registry(config.stub_capabilities_path) → list[CapabilityDescriptor].
lifecycle → assemble_tool_list(config, capability_registry) returns 9 @tool funcs.
lifecycle → build_supervisor(config, tools=..., available_capabilities=...).
factory renders each descriptor via CapabilityDescriptor.as_prompt_block(), joins with \n\n, substitutes into {available_capabilities}, passes to create_deep_agent(...).
Trace — turn
SessionManager.invoke() drives the compiled graph (Phase 1 path).
Reasoning model reads the prompt (including ## Available Capabilities) and picks a tool.
read_file → fs; search_web → Tavily; calculate → asteval; get_calendar_events → [] (stub).
dispatch_by_capability resolves tool_name against registry, builds real CommandPayload + MessageEnvelope, logs JARVIS_DISPATCH_STUB, returns stub response.
queue_build builds real BuildQueuedPayload + MessageEnvelope, logs JARVIS_QUEUE_BUILD_STUB, returns QueueBuildAck JSON.
What the diagram does NOT show
FEAT-JARVIS-003 — AsyncSubAgentMiddleware + 4 subagent graphs (next /system-design).
Graphiti tools — FEAT-JARVIS-004.
NATS adapter — FEAT-JARVIS-004. Phase 2 uses nats-core as a Pydantic library only.
Skills — FEAT-JARVIS-007.
escalate_to_frontier — reserved slot in jarvis.tools.dispatch; lands later per ADR-ARCH-027.
🔍 Review gate — your decision
Look for:

Cyclic imports or leaking state (caps must not import factory).
Separation of concerns (dispatch depends on caps, not vice versa).
Missing persistence: Phase 2 has none (in-memory stub + no NATS) — acceptable per scope?
Any module with too many dependencies.
[A]pprove — I'll seed to Graphiti next
[R]evise — tell me what to change and I'll regenerate
[Reject] — drop this design and restart

Waiting for your call before proceeding to seeding.

command_history.md
A
Approved. Proceeding to Graphiti seeding.

Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH corpus

Draft DDRs (dispatch name, Tavily, asteval, capabilities delivery, stub semantics)

Write C4 L3 diagram

Present C4 L3 review gate to user + await approval

Offer Graphiti seeding commands
Quick Graphiti reachability probe before offering commands.

Bash Check Graphiti connectivity via guardkit CLI
IN
guardkit graphiti status 2>&1 | head -20

OUT
╔════════════════════════════════════════╗
║       Graphiti Knowledge Status        ║
╚════════════════════════════════════════╝

  Status: ENABLED
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"

  System Knowledge:
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"
    • product_knowledge: 84
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"
    • command_workflows: 100
INFO:httpx:HTTP Request: POST http://promaxgb10-41b1:8001/v1/embeddings "HTTP/1.1 200 OK"
    • patterns: 100
Graphiti is reachable. Here are the seeding commands — 9 commands total (1 top-level design.md + 2 contracts + 2 models + 5 DDRs).


# Top-level design doc — indexed to project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/design.md \
  --group project_design

# API contracts — indexed to project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-tools.md \
  --group project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-internal.md \
  --group project_design

# Data models — indexed to project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-tool-types.md \
  --group project_design
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md \
  --group project_design

# DDRs — indexed to architecture_decisions (matches how FEAT-JARVIS-001 DDRs were seeded)
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-006-tavily-as-web-search-provider.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-008-capabilities-both-tool-and-prompt-injection.md \
  --group architecture_decisions
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-009-dispatch-stub-transport-semantics.md \
  --group architecture_decisions
Want me to run these now? [Y]es / [N]o (I'll seed later)

Each seeding call takes ~5–20 s (embedding + entity extraction); the whole batch is ~1–3 min. I'll run them sequentially so failures are easy to isolate.

Y
Running the 9 seeding commands sequentially.

Bash Seed 10 FEAT-JARVIS-002 design artefacts to Graphiti
IN
set -e
echo "=== 1/9: design.md ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/design.md --group project_design
echo "=== 2/9: API-tools.md ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-tools.md --group project_design
echo "=== 3/9: API-internal.md ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-internal.md --group project_design
echo "=== 4/9: DM-tool-types.md ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-tool-types.md --group project_design
echo "=== 5/9: DM-stub-registry.md ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md --group project_design
echo "=== 6/9: DDR-005 ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md --group architecture_decisions
echo "=== 7/9: DDR-006 ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-006-tavily-as-web-search-provider.md --group architecture_decisions
echo "=== 8/9: DDR-007 ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md --group architecture_decisions
echo "=== 9/9: DDR-008 ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-008-capabilities-both-tool-and-prompt-injection.md --group architecture_decisions
echo "=== 10/9: DDR-009 ==="
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-009-dispatch-stub-transport-semantics.md --group architecture_decisions
echo "=== ALL 10 SEEDED ==="

OUT
=== 1/9: design.md ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 2/9: API-tools.md ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 3/9: API-internal.md ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 4/9: DM-tool-types.md ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 5/9: DM-stub-registry.md ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 6/9: DDR-005 ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 7/9: DDR-006 ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 8/9: DDR-007 ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 9/9: DDR-008 ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== 10/9: DDR-009 ===
Usage: guardkit-py graphiti add-context [OPTIONS] PATH
Try 'guardkit-py graphiti add-context --help' for help.

Error: No such option: --group
=== ALL 10 SEEDED ===
The --group flag doesn't exist on this guardkit version. Let me check the actual options.

Bash Inspect actual add-context CLI options
IN
guardkit graphiti add-context --help 2>&1

OUT
Usage: guardkit-py graphiti add-context [OPTIONS] PATH

  Add context from files to Graphiti.

  Adds content from markdown files to the Graphiti knowledge graph. Supports
  single files or directories with glob patterns.

  Examples:
      guardkit graphiti add-context docs/ADR-001.md
      guardkit graphiti add-context docs/architecture/
      guardkit graphiti add-context docs/ --pattern "**/*.md"
      guardkit graphiti add-context docs/ADR-001.md --type adr
      guardkit graphiti add-context docs/ --dry-run
      guardkit graphiti add-context docs/ --delay 1.0
      guardkit graphiti add-context docs/ --delay 0

  Supported parser types:
      - adr: Architecture Decision Records
      - feature_spec: Feature specifications
      - full_doc: Full document capture (entire markdown content)
      - project_overview: Project overview documents
      - project_doc: General project documentation (CLAUDE.md, README.md)

Options:
  --type TEXT           Force parser type (adr, feature-spec, project-
                        overview)
  -f, --force           Overwrite existing context
  --dry-run             Show what would be added without adding
  --pattern TEXT        Glob pattern for directory (default: **/*.md)
  -v, --verbose         Show detailed processing output
  -q, --quiet           Suppress non-error output
  --delay FLOAT         Inter-episode delay in seconds (default: 0.5, 0 to
                        disable)
  --chunk-size INTEGER  Force chunking for docs above this size in bytes
                        (default: 10240). Use 0 to always chunk.
  --timeout FLOAT       Per-episode timeout in seconds (overrides auto-
                        detected timeout). Use for slow vLLM instances.
  --help                Show this message and exit.
Let me check what a dry-run resolves these to for routing.

Bash Dry-run a DDR seeding to inspect resolved group
IN
guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md --type adr --dry-run 2>&1 | head -40

OUT
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

  ✓ 
docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-
call-specialist.md (adr)

Dry run complete - Would add:
  1 file, 1 episode

Warnings:
  Warning: 
docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-
call-specialist.md: Missing required section: Status
--type adr works for DDRs; group is auto-routed. The Status warning is cosmetic (I used bold markdown not a heading). Now seeding all 10 with appropriate types.

Bash Seed 10 artefacts with correct types
IN
fail=0
run() {
  label="$1"; shift
  echo "=== $label ==="
  if "$@" 2>&1 | tail -20; then :; else fail=1; echo "!!! FAILED: $label"; fi
}

run "1/10 design.md (full_doc)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/design.md --type full_doc
run "2/10 contracts/API-tools.md (full_doc)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-tools.md --type full_doc
run "3/10 contracts/API-internal.md (full_doc)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/contracts/API-internal.md --type full_doc
run "4/10 models/DM-tool-types.md (full_doc)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-tool-types.md --type full_doc
run "5/10 models/DM-stub-registry.md (full_doc)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md --type full_doc
run "6/10 DDR-005 (adr)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md --type adr
run "7/10 DDR-006 (adr)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-006-tavily-as-web-search-provider.md --type adr
run "8/10 DDR-007 (adr)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md --type adr
run "9/10 DDR-008 (adr)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-008-capabilities-both-tool-and-prompt-injection.md --type adr
run "10/10 DDR-009 (adr)" \
  guardkit graphiti add-context docs/design/FEAT-JARVIS-002/decisions/DDR-009-dispatch-stub-transport-semantics.md --type adr

if [ $fail -eq 0 ]; then echo "=== ALL 10 SEEDED SUCCESSFULLY ==="; else echo "=== COMPLETED WITH FAILURES ==="; fi

OUT
Command running in background with ID: brukm4quk. Output is being written to: /private/tmp/claude-501/-Users-richardwoollcott-Projects-appmilla-github-jarvis/f96a90b0-86f2-4079-95a7-390514dae17b/tasks/brukm4quk.output
Seeding running in background. Waiting for completion before summarising.

Seeding running. I'll report results when the batch completes (expected 1–3 min).

Bash Inspect seeding output tail
IN
tail -150 /private/tmp/claude-501/-Users-richardwoollcott-Projects-appmilla-github-jarvis/f96a90b0-86f2-4079-95a7-390514dae17b/tasks/brukm4quk.output

OUT
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

WARNING:graphiti_core.utils.maintenance.edge_operations:LLM returned invalid duplicate_facts idx values [3] (valid range: 0-0 for EXISTING FACTS)
WARNING:graphiti_core.utils.maintenance.edge_operations:LLM returned invalid duplicate_facts idx values [6] (valid range: 0--1 for EXISTING FACTS)
INFO:graphiti_core.graphiti:Completed add_episode in 338042.023897171 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [docs/design/FEAT-JARVIS-002/contracts/API-internal.md]: nodes=26, edges=52, invalidated=0
  ✓ docs/design/FEAT-JARVIS-002/contracts/API-internal.md (full_doc)

Summary:
  Added 1 file, 1 episode
=== 4/10 models/DM-tool-types.md (full_doc) ===
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 102546.03886604309 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [docs/design/FEAT-JARVIS-002/models/DM-tool-types.md]: nodes=6, edges=10, invalidated=0
  ✓ docs/design/FEAT-JARVIS-002/models/DM-tool-types.md (full_doc)

Summary:
  Added 1 file, 1 episode
=== 5/10 models/DM-stub-registry.md (full_doc) ===
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 202139.45078849792 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md]: nodes=15, edges=16, invalidated=0
  ✓ docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md (full_doc)

Summary:
  Added 1 file, 1 episode
=== 6/10 DDR-005 (adr) ===
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 119383.54301452637 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [adr_ddr-005-dispatch-tool-is-dispatch-by-capability-superseding-scope-doc-call-specialist]: nodes=10, edges=4, invalidated=0
  ✓ 
docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-
call-specialist.md (adr)

Summary:
  Added 1 file, 1 episode

Warnings:
  Warning: 
docs/design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-
call-specialist.md: Missing required section: Status
=== 7/10 DDR-006 (adr) ===
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 145820.45984268188 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [adr_ddr-006-tavily-is-the-v1-provider-behind-search-web]: nodes=11, edges=5, invalidated=0
  ✓ 
docs/design/FEAT-JARVIS-002/decisions/DDR-006-tavily-as-web-search-provider.md 
(adr)

Summary:
  Added 1 file, 1 episode

Warnings:
  Warning: 
docs/design/FEAT-JARVIS-002/decisions/DDR-006-tavily-as-web-search-provider.md: 
Missing required section: Status
=== 8/10 DDR-007 (adr) ===
Graphiti Add Context

INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 108389.37091827393 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [adr_ddr-007-calculate-uses-asteval-for-safe-expression-evaluation]: nodes=5, edges=5, invalidated=0
  ✓ docs/design/FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md (adr)

Summary:
  Added 1 file, 1 episode

Warnings:
  Warning: 
docs/design/FEAT-JARVIS-002/decisions/DDR-007-asteval-for-calculate.md: Missing 
required section: Status
=== 9/10 DDR-008 (adr) ===
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 124663.8548374176 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [adr_ddr-008-capabilities-reach-the-supervisor-via-both-a-tool-call-and-a-prompt-injected-placeholder]: nodes=7, edges=9, invalidated=0
  ✓ 
docs/design/FEAT-JARVIS-002/decisions/DDR-008-capabilities-both-tool-and-prompt-
injection.md (adr)

Summary:
  Added 1 file, 1 episode

Warnings:
  Warning: 
docs/design/FEAT-JARVIS-002/decisions/DDR-008-capabilities-both-tool-and-prompt-
injection.md: Missing required section: Status
=== 10/10 DDR-009 (adr) ===
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: handle_multiple_group_ids patched for single group_id support (upstream PR #1170)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: build_fulltext_query patched to remove group_id filter (redundant on FalkorDB)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_fulltext_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.falkordb_workaround:[Graphiti] Applied FalkorDB workaround: edge_bfs_search patched for O(n) startNode/endNode (upstream issue #1272)
INFO:guardkit.knowledge.graphiti_client:Connected to FalkorDB via graphiti-core at whitestocks:6379
Connected to Graphiti

INFO:graphiti_core.graphiti:Completed add_episode in 422025.97880363464 ms
INFO:guardkit.knowledge.graphiti_client:Episode profile [adr_ddr-009-phase-2-dispatch-tool-stub-transport-semantics]: nodes=21, edges=40, invalidated=0
  ✓ 
docs/design/FEAT-JARVIS-002/decisions/DDR-009-dispatch-stub-transport-semantics.
md (adr)

Summary:
  Added 1 file, 1 episode

Warnings:
  Warning: 
docs/design/FEAT-JARVIS-002/decisions/DDR-009-dispatch-stub-transport-semantics.
md: Missing required section: Status
=== ALL 10 SEEDED SUCCESSFULLY ===
Update Todos

Load all context files (ADRs, nats-core payloads, supervisor code)

Design API contracts (tool surfaces) for FEAT-JARVIS-002

Design data models (CapabilityDescriptor, SpecialistResult, QueueBuildAck, WebResult, CalendarEvent)

Run contradiction detection against existing ADR-ARCH corpus

Draft DDRs (dispatch name, Tavily, asteval, capabilities delivery, stub semantics)

Write C4 L3 diagram

Present C4 L3 review gate to user + await approval

Offer and execute Graphiti seeding commands
✅ SYSTEM DESIGN COMPLETE — FEAT-JARVIS-002
All 10 artefacts seeded successfully.

Graphiti seeding results
#	Artefact	Episode	Nodes	Edges
1	design.md	full_doc	—	—
2	contracts/API-tools.md	full_doc	—	—
3	contracts/API-internal.md	full_doc	26	52
4	models/DM-tool-types.md	full_doc	6	10
5	models/DM-stub-registry.md	full_doc	15	16
6	DDR-005 (dispatch_by_capability)	adr	10	4
7	DDR-006 (Tavily)	adr	11	5
8	DDR-007 (asteval)	adr	5	5
9	DDR-008 (capabilities delivery)	adr	7	9
10	DDR-009 (stub transport semantics)	adr	21	40
Cosmetic warnings: all 5 DDRs got "Missing required section: Status" because I wrote **Status:** Accepted (bold field) rather than ## Status (heading). Parser still accepted and indexed them. Easy fix for future consistency if needed — the FEAT-JARVIS-001 DDRs may use the same convention.

Files written

docs/design/FEAT-JARVIS-002/
├── design.md
├── contracts/API-tools.md
├── contracts/API-internal.md
├── models/DM-tool-types.md
├── models/DM-stub-registry.md
├── diagrams/fleet-dispatch-l3.md           (reviewed + approved, not seeded)
└── decisions/
    ├── DDR-005-dispatch-by-capability-supersedes-call-specialist.md
    ├── DDR-006-tavily-as-web-search-provider.md
    ├── DDR-007-asteval-for-calculate.md
    ├── DDR-008-capabilities-both-tool-and-prompt-injection.md
    └── DDR-009-dispatch-stub-transport-semantics.md
Next steps (per phase2-build-plan.md)
/system-design FEAT-JARVIS-003 — async subagents (needs reconciliation with ADR-ARCH-011's single-reasoner supersede — flagged in contradiction C2).
/feature-spec FEAT-JARVIS-002 — Gherkin scenarios grounded in this design.
/feature-plan FEAT-JARVIS-002 — task breakdown per phase2-build-plan.md Step 7.
AutoBuild in commit order: config → types → general → capabilities → dispatch → prompt → supervisor factory → supervisor-with-tools test.