# FEAT-JARVIS-003 — Design

> **Feature:** Async Subagent for Model Routing + Attended Frontier Escape
> **Phase:** 2 (Dispatch Foundations) — FEAT-JARVIS-003 only; FEAT-JARVIS-002 (core tools + capability-driven dispatch) shipped separately.
> **Generated:** 2026-04-23 via `/system-design FEAT-JARVIS-003`
> **Status:** Proposed — input to `/feature-spec FEAT-JARVIS-003`
> **Architecture source:** [../../architecture/ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) (v1.0, 2026-04-20, 30 ADRs)
> **Scope source:** [../../research/ideas/phase2-dispatch-foundations-scope.md](../../research/ideas/phase2-dispatch-foundations-scope.md) — **reframed** by the superseding ADRs below
> **Predecessor designs:** [../FEAT-JARVIS-001/design.md](../FEAT-JARVIS-001/design.md), [../FEAT-JARVIS-002/design.md](../FEAT-JARVIS-002/design.md)

---

## 1. Purpose

FEAT-JARVIS-003 turns *"one reasoning model that knows which reasoning model to use"* from aspiration into observable behaviour by giving the Phase 1 supervisor its **subagent-routing** surface. The original scope (20 April 2026) proposed four heterogeneous cloud+local AsyncSubAgents; the `/system-arch` session that followed (also 20 April 2026) accepted four ADRs that retire that design:

- **ADR-ARCH-001** — no cloud LLMs on unattended paths (AsyncSubAgents run unattended every turn → three of four scope subagents forbidden).
- **ADR-ARCH-011** — single `jarvis-reasoner` AsyncSubAgent on `gpt-oss-120b`; specialist roles are prompt-driven modes of the same model.
- **ADR-ARCH-012** — swap-aware supervisor supersedes JA6 cloud-fallback proposal; `quick_local` is retired.
- **ADR-ARCH-027** — `escalate_to_frontier` is an **attended-only** cloud escape **tool**, not a subagent; constitutionally gated belt+braces.

This design reconciles the scope with those ADRs and ships three capability clusters:

| Cluster | Artefact | Transport |
|---|---|---|
| **AsyncSubAgent `jarvis-reasoner`** (1 subagent, 3 role modes) | `src/jarvis/agents/subagents/jarvis_reasoner.py` compiled graph + `AsyncSubAgent` registry entry | ASGI (co-deployed), per ADR-ARCH-031 default |
| **AsyncSubAgentMiddleware tools** (5 built-ins wired automatically) | `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` | in-process via DeepAgents middleware |
| **`escalate_to_frontier` tool** (attended-only, constitutional) | `jarvis.tools.dispatch.escalate_to_frontier` — slot reserved by FEAT-JARVIS-002 DDR-005/C2 | real cloud provider SDK (`google_genai` default; `anthropic` via `target=`) |

Plus a fourth supporting piece — the **swap-aware llama-swap adapter** (`jarvis.adapters.llamaswap`) — which makes ADR-ARCH-012's voice-latency policy observable from the supervisor. Phase 2 stubs its read path; FEAT-JARVIS-004 wires it live against `http://promaxgb10-41b1:9000`.

One-line success criterion: *the reasoning model can choose between the `jarvis-reasoner` subagent (with a role), the FEAT-JARVIS-002 tools, and `escalate_to_frontier` — and the attended-only gate on the frontier tool holds against both ambient tool sets and a spoofed-ambient invocation from an attended session.*

## 2. Scope in-context

Jarvis has seven bounded contexts per [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-seven-bounded-contexts.md). FEAT-JARVIS-003 extends the same two that FEAT-JARVIS-002 touched, adds the swap-adapter piece to a third, and leaves the remaining four untouched.

| Bounded context | FEAT-JARVIS-003 touches? | How |
|---|---|---|
| **Fleet Dispatch Context** | **IN — core** | `jarvis-reasoner` AsyncSubAgent (routing target), `escalate_to_frontier` tool, llama-swap adapter |
| **Jarvis Reasoning Context** | extended | supervisor factory gains `async_subagents=`; prompt gains role-dispatch + escalation sections |
| **Config (cross-cutting)** | extended | llama-swap base URL, frontier provider keys, `RoleName` enum export |
| **Adapter Interface Context** | partial — read-side only | session-aware tool registration reads adapter identity (no new adapter containers) |
| Ambient / Learning / Knowledge / External Tool contexts | untouched | FEAT-JARVIS-004/007/008 territory |

See [phase2-dispatch-foundations-scope.md §Do-Not-Change](../../research/ideas/phase2-dispatch-foundations-scope.md) with the understanding that its four-subagent roster is superseded; everything else (Phase 1 outputs, FEAT-JARVIS-002 outputs, ASGI default, subagent-descriptions-are-the-contract) is preserved.

## 3. Surfaces shipped

| Surface | Type | Artefact |
|---|---|---|
| DeepAgents AsyncSubAgent surface (1 `AsyncSubAgent` entry) | in-process — description + `graph_id` is the contract | [contracts/API-subagent.md](contracts/API-subagent.md) |
| DeepAgents tool surface (1 new `@tool` function + 5 middleware-provided tools) | in-process — docstrings are the contract | [contracts/API-tools.md](contracts/API-tools.md) |
| Internal Python API (module contracts) | in-process | [contracts/API-internal.md](contracts/API-internal.md) |

**No new network protocols.** The `jarvis-reasoner` graph runs under ASGI on the same LangGraph server as the supervisor per ADR-ARCH-031. `escalate_to_frontier` issues outbound HTTPS to a cloud provider but exposes no endpoint. llama-swap reads are outbound HTTP only. Consistent with [FEAT-JARVIS-001 DDR-001](../FEAT-JARVIS-001/decisions/DDR-001-internal-api-in-process-only.md) and [FEAT-JARVIS-002 §3](../FEAT-JARVIS-002/design.md) — no `openapi.yaml`, no `mcp-tools.json`, no `a2a-schemas.yaml`.

The `langgraph.json` *is* a new surface for deployment tooling and lands in this feature — see [DDR-013](decisions/DDR-013-langgraph-json-at-repo-root.md).

## 4. Data models

| Model | Purpose | Artefact |
|---|---|---|
| `RoleName` (enum), `AsyncTaskInput`, `RolePromptRegistry`, `SwapStatus`, `FrontierEscalationContext`, `FrontierTarget` (enum) | Subagent-layer + escalation-layer Pydantic types | [models/DM-subagent-types.md](models/DM-subagent-types.md) |
| `AsyncSubAgent` (DeepAgents 0.5.3 TypedDict) | Reused from `deepagents` — single entry for `jarvis-reasoner` | imported; no redefinition |
| Reused from FEAT-JARVIS-002 | `CapabilityDescriptor` still the catalogue type; unchanged | [../FEAT-JARVIS-002/models/DM-tool-types.md](../FEAT-JARVIS-002/models/DM-tool-types.md) |

## 5. Design decisions captured

| DDR | Decision | Why it's here |
|---|---|---|
| [DDR-010](decisions/DDR-010-single-async-subagent-supersedes-four-roster.md) | One AsyncSubAgent (`jarvis-reasoner`) with a `role` kwarg supersedes the four-subagent roster from the scope doc | Reconciles scope with ADR-ARCH-001 + ADR-ARCH-011 (the C2 contradiction FEAT-JARVIS-002 deferred). |
| [DDR-011](decisions/DDR-011-role-enum-closed-v1.md) | `RoleName` is a closed enum for v1: `CRITIC`, `RESEARCHER`, `PLANNER` | Open questions left the role set unspecified; a closed enum matches ADR-ARCH-017's static-declaration posture and gives the learning flywheel (v1.5) a fixed label space to measure against. |
| [DDR-012](decisions/DDR-012-subagent-module-import-compilation.md) | Subagent graphs compile at **module import** time, not lazily | Settles the scope doc's open question "module import vs lazy-at-first-use". Module-import gives `langgraph dev` deterministic startup validation and fails fast on missing provider keys per ADR-ARCH-015. |
| [DDR-013](decisions/DDR-013-langgraph-json-at-repo-root.md) | `langgraph.json` lives at **repo root**; declares two graphs (`jarvis`, `jarvis_reasoner`) with ASGI transport | Settles the scope doc's open question "repo root vs `src/jarvis/`". Matches Forge ADR-ARCH-031 and LangGraph convention; no packaging gymnastics. |
| [DDR-014](decisions/DDR-014-escalate-to-frontier-in-dispatch-tool-module.md) | `escalate_to_frontier` lands in `jarvis.tools.dispatch` (the FEAT-JARVIS-002 DDR-005/C2 reserved slot). Constitutional gating is **belt+braces**: docstring prohibition, executor assertion on `adapter_id`, caller-frame non-ambient check, **and session-aware tool registration** so the tool is *absent* from ambient/learning/Pattern-C tool sets entirely | Realises ADR-ARCH-027 in code — not just prompt-level prohibition. The absence-from-tool-set layer is the third brace; reasoning cannot invoke a tool it cannot see. |
| [DDR-015](decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md) | Swap-aware read path lives in `jarvis.adapters.llamaswap`, the first Group-D adapter. Phase 2 stubs the `/running` + `/log` reads (test-overrideable); FEAT-JARVIS-004 wires live reads against `http://promaxgb10-41b1:9000` | Realises ADR-ARCH-012 in code. Retires the scope doc's "quick_local fallback hook" (JA6) cleanly — the hook becomes a swap-awareness hook, not a cloud-fallback hook. |

DDR numbering continues from FEAT-JARVIS-002 (DDR-005..009). FEAT-JARVIS-003 uses DDR-010..015; next available after this design is DDR-016.

## 6. Component diagram

[diagrams/jarvis-reasoning-l3.md](diagrams/jarvis-reasoning-l3.md) — C4 Level 3 view of the Jarvis Supervisor container extended with the `jarvis-reasoner` AsyncSubAgent graph, `AsyncSubAgentMiddleware`-injected tools, the `escalate_to_frontier` dispatch tool, and the llama-swap adapter. **Requires explicit approval per `/system-design` Phase 3.5 gate** — the container exceeds the 3-internal-component threshold (10 components participate).

## 7. Module layout — extensions to Phase 1 + FEAT-JARVIS-002

Per [ADR-ARCH-006 five-group layout](../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md). Phase 1 reserved `agents/subagents/`, `adapters/` empty; FEAT-JARVIS-002 populated `tools/`; FEAT-JARVIS-003 fills `agents/subagents/`, starts `adapters/`, and extends three existing modules:

```
src/jarvis/
├── agents/
│   ├── supervisor.py                       # UPDATED — wires async_subagents + session-aware tool list
│   ├── subagent_registry.py                # NEW    — build_async_subagents(config) → [AsyncSubAgent]
│   └── subagents/                          # Group A — populated in FEAT-JARVIS-003
│       ├── __init__.py                     # NEW
│       ├── jarvis_reasoner.py              # NEW    — create_deep_agent graph; role→prompt resolver
│       └── prompts.py                      # NEW    — ROLE_PROMPTS registry (3 role system prompts)
├── prompts/
│   └── supervisor_prompt.py                # UPDATED — role-dispatch + escalation sections
├── config/
│   └── settings.py                         # UPDATED — llama_swap_base_url, frontier_default_target,
│                                           #           gemini_api_key (opt), anthropic_api_key already present
├── tools/
│   └── dispatch.py                         # UPDATED — adds escalate_to_frontier (reserved slot fill)
├── adapters/                               # Group D — first Jarvis adapter populated
│   ├── __init__.py                         # was RESERVED — now re-exports LlamaSwapAdapter
│   └── llamaswap.py                        # NEW    — SwapStatus type + stubbed /running /log reads
└── infrastructure/
    └── lifecycle.py                        # UPDATED — builds async subagents, session-aware tool registry
langgraph.json                              # NEW    — repo-root, 2 graphs, ASGI transport
```

Every `@tool` still follows ADR-ARCH-021 (return structured error strings; never raise). The subagent graph itself returns structured output per DeepAgents 0.5.3 conventions; the supervisor reads the `async_tasks` state channel via `check_async_task`.

## 8. Wiring — how subagents and the frontier tool compose

Extends the FEAT-JARVIS-002 wiring sequence. New lines marked `← NEW in FEAT-JARVIS-003`.

```
env + .env
    │
    ▼
JarvisConfig()                                    ← jarvis.config.settings (extended in 003)
    │
    ▼
lifecycle.startup(config):
    │
    ├── logging.configure(...)
    ├── config.validate_provider_keys()
    ├── capability_registry = load_stub_registry(config.stub_capabilities_path)        # 002
    ├── llamaswap_adapter = LlamaSwapAdapter(base_url=config.llama_swap_base_url)      # ← NEW in 003
    ├── async_subagents = build_async_subagents(config)                                # ← NEW in 003
    │                                              # → [AsyncSubAgent(name="jarvis-reasoner",
    │                                              #                  graph_id="jarvis_reasoner",
    │                                              #                  description="…gpt-oss-120b…")]
    ├── tool_list_attended = assemble_tool_list(                                       # EXTENDED in 003
    │       config, capability_registry, llamaswap_adapter,
    │       include_frontier=True,             # adapter ∈ {telegram, cli, dashboard, reachy}
    │   )
    ├── tool_list_ambient = assemble_tool_list(                                        # ← NEW in 003
    │       config, capability_registry, llamaswap_adapter,
    │       include_frontier=False,            # constitutional: frontier removed from ambient
    │   )
    ├── supervisor = build_supervisor(
    │       config,
    │       tools=tool_list_attended,
    │       available_capabilities=capability_registry,
    │       async_subagents=async_subagents,                                           # ← NEW in 003
    │       ambient_tool_factory=lambda: tool_list_ambient,                            # ← NEW in 003
    │   )
    ├── store = InMemoryStore()
    └── session_manager = SessionManager(supervisor, store)
    │
    ▼
AppState(config, supervisor, store, session_manager,
         capability_registry, llamaswap_adapter)           # extended
    │
    ▼
cli.main runs its subcommand (Phase 1 behaviour preserved)
```

`build_supervisor(...)`'s public signature gains two keyword-only arguments; both have safe defaults so FEAT-JARVIS-001/002 call sites still work:

```python
def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,                      # added in 002
    available_capabilities: list[CapabilityDescriptor] | None = None,  # added in 002
    async_subagents: list[AsyncSubAgent] | None = None,       # ← NEW in 003
    ambient_tool_factory: Callable[[], list[BaseTool]] | None = None,  # ← NEW in 003
) -> CompiledStateGraph[Any, Any, Any, Any]: ...
```

Defaults: `async_subagents=None` → no subagents wired (Phase 1 + FEAT-JARVIS-002 behaviour preserved). `ambient_tool_factory=None` → Pattern B / learning paths fall back to the attended tool list *without* `escalate_to_frontier` (a later feature can register watcher-specific tool sets).

### Role-dispatch contract

The supervisor invokes the subagent as:

```python
# From within the reasoning loop, as a tool call produced by the reasoning model:
start_async_task(
    name="jarvis-reasoner",
    input={
        "prompt": "<Rich's rendered instruction>",
        "role": "critic",                    # RoleName.CRITIC.value
        "correlation_id": "<session.correlation_id>",
    },
)
```

The `jarvis_reasoner` graph reads `input["role"]` at its first node, looks up the system prompt in `ROLE_PROMPTS[RoleName(role)]`, and runs `create_deep_agent(model="openai:jarvis-reasoner", system_prompt=<resolved>, tools=[])` with `OPENAI_BASE_URL=http://promaxgb10-41b1:9000/v1` — so a single llama-swap-backed `gpt-oss-120b` handles all three roles via prompt-only differentiation. No swap cost between role modes (ADR-ARCH-011 consequence).

If `role` is missing or unknown, the graph returns a structured error via the `async_tasks` channel (not a raise) per ADR-ARCH-021: `"ERROR: unknown_role — expected one of {critic, researcher, planner}"`.

### Frontier escalation contract

`escalate_to_frontier(instruction: str, target: FrontierTarget = GEMINI_3_1_PRO) -> str` — direct synchronous call to the cloud provider; no subagent. The tool is:

- **Registered only on attended sessions** (`adapter_id ∈ {telegram, cli, dashboard, reachy}`). The `ambient_tool_factory` returns a list that omits it entirely — ambient watchers cannot invoke a tool that is not in their registered set.
- **Asserts at the boundary** that the active session's `adapter_id` is attended *and* that the call frame is not inside an `AsyncSubAgent` (checked via the `AsyncSubAgentMiddleware` metadata or, if unavailable, via session-state lookup). Any violation returns `"ERROR: attended_only — escalate_to_frontier cannot be invoked from {frame}"`.
- **Default target** is `google_genai:gemini-3.1-pro`; `target=FrontierTarget.OPUS_4_7` switches to `anthropic:claude-opus-4-7`. Both cost toward the £20–£50/month ADR-ARCH-030 budget.

Budget monitoring is trace-based per ADR-ARCH-027: invocations log with `model_alias=cloud-frontier` at INFO, ready to flow into `jarvis_routing_history` when FEAT-JARVIS-004 lights up Graphiti writes.

## 9. Test shape

Target: **+25–35 tests** on top of FEAT-JARVIS-002's baseline; maintain 80% coverage on new modules.

- `tests/test_subagent_registry.py` — `build_async_subagents(test_config)` returns a 1-element list whose single `AsyncSubAgent` has `name="jarvis-reasoner"`, `graph_id="jarvis_reasoner"`, and a non-empty description containing the gpt-oss-120b cost/latency signal substring.
- `tests/test_subagents_jarvis_reasoner.py` — `from jarvis.agents.subagents.jarvis_reasoner import graph`; graph compiles at import (DDR-012); resolves `ROLE_PROMPTS[RoleName.CRITIC]` to a non-empty prompt; unknown-role input path returns the structured error. No LLM call — uses `FakeListChatModel`.
- `tests/test_subagent_prompts.py` — `ROLE_PROMPTS` is a complete mapping over `RoleName` members (exhaustiveness check); each prompt is non-empty and mentions the role's posture (critic → "adversarial evaluation"; researcher → "open-ended research"; planner → "multi-step planning").
- `tests/test_escalate_to_frontier.py`:
  - Happy path: attended session (`adapter_id="cli"`) → mocked provider returns canned text → tool returns it.
  - Rejection: ambient call frame → returns `ERROR: attended_only — …`.
  - Rejection: tool absent from `ambient_tool_factory()` result (registration-layer assertion, not runtime).
  - Default target is `FrontierTarget.GEMINI_3_1_PRO`; `target=FrontierTarget.OPUS_4_7` routes to `anthropic:claude-opus-4-7`.
  - Missing provider key → structured error per ADR-ARCH-021 (`ERROR: config_missing — GOOGLE_API_KEY not set`).
- `tests/test_adapters_llamaswap.py` — `LlamaSwapAdapter(base_url="http://stub")` with stubbed `/running` and `/log` returns `SwapStatus(loaded_model=..., eta_seconds=0)`; "degraded" stub returns `SwapStatus(eta_seconds=180)` for the >30s-ETA branch.
- `tests/test_swap_aware_voice_ack.py` — replaces the scope doc's "`quick_local` fallback test". Supervisor dispatched with a voice-adapter session + swap ETA > 30s emits the TTS ack stub and queues the request. Pure state assertion; no audio I/O.
- `tests/test_supervisor_with_subagents.py` — extends FEAT-JARVIS-002's `test_supervisor_with_tools.py`: `build_supervisor(test_config, tools=[...], async_subagents=[...], ambient_tool_factory=...)` returns a `CompiledStateGraph`; the 5 `AsyncSubAgentMiddleware` tools are exposed; `escalate_to_frontier` is present on attended tool list and absent on ambient tool list. No LLM call.
- `tests/test_routing_e2e.py` — **the acceptance test for FEAT-JARVIS-003.** Seven canned prompts with a mocked LLM returning deterministic tool-call sequences:
  1. "What's 15% of 847?" → `calculate` (FEAT-JARVIS-002 regression).
  2. "Summarise /tmp/test.md" → `read_file` (FEAT-JARVIS-002 regression).
  3. "Critique this architecture doc for subtle flaws." → `start_async_task(name="jarvis-reasoner", input={"role": "critic", ...})`.
  4. "Research Meta-Harness deeply." → `start_async_task(name="jarvis-reasoner", input={"role": "researcher", ...})`.
  5. "Plan the migration to Python 3.13." → `start_async_task(name="jarvis-reasoner", input={"role": "planner", ...})`.
  6. "Ask Gemini 3.1 Pro for a frontier opinion on this ADR." (attended CLI) → `escalate_to_frontier(target=GEMINI_3_1_PRO)`.
  7. "Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo." → `queue_build` (FEAT-JARVIS-002 regression) — confirms no routing regression from the subagent wiring.
- `tests/test_langgraph_json.py` — `langgraph.json` at repo root is valid JSON; declares both `jarvis` and `jarvis_reasoner` graphs with ASGI transport; `python -m langgraph dev --help` returns 0 under the test harness (CLI smoke, no server spin).

Tests assert tool-call sequences (structural), not final natural-language output (behavioural). Same pattern as `specialist-agent`'s Player-Coach test structure.

## 10. Supervisor prompt extensions

[`SUPERVISOR_SYSTEM_PROMPT`](../../../src/jarvis/prompts/supervisor_prompt.py) gains two sections appended *after* FEAT-JARVIS-002's Tool-Usage section, preserving the Phase 1 + FEAT-JARVIS-002 content verbatim:

1. **`## Subagent Routing`** — "You have one async subagent: `jarvis-reasoner` (gpt-oss-120b via llama-swap). It runs locally, has no cloud cost, and carries no privacy risk. It accepts a `role` input with three values: `critic` (adversarial evaluation), `researcher` (open-ended research with web tools), `planner` (multi-step planning). Prefer `start_async_task(name='jarvis-reasoner', input={'role': ..., 'prompt': ...})` for any task that needs sustained reasoning beyond a single turn. Do not invoke it for one-shot factual lookups or arithmetic — those have direct tools (`calculate`, `search_web`, `read_file`). Check cost + latency in the subagent description before dispatching; llama-swap may need to warm the model (the system will ack automatically if so)."

2. **`## Frontier Escalation`** — "The `escalate_to_frontier` tool is **available only when I ask for it explicitly** — 'ask Gemini / Opus', 'frontier opinion', 'cloud model', etc. It is not a default escalation path; local reasoning is preferred. The tool will refuse invocation from ambient or learning contexts. Default target is Gemini 3.1 Pro; use `target=OPUS_4_7` for adversarial critique specifically. Budget is shared £20–£50/month fleet-wide — use sparingly."

No mention of the retired four-subagent roster, `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`, or a cloud fallback for `quick_local`. The Phase 1 attended-conversation posture and the FEAT-JARVIS-002 tool-usage preferences remain unchanged.

## 11. Contradiction detection (against existing ADRs + DDRs)

Proposed contracts checked against:

- All **30 accepted ADRs** in [docs/architecture/decisions/](../../architecture/decisions/).
- All **9 accepted DDRs** from FEAT-JARVIS-001 (001–004) and FEAT-JARVIS-002 (005–009).
- Forge ADR-ARCH-031 (async subagents) — imported pattern; consistency, not dependency.

**No contradictions detected after the scope reframe** (C1/C2 from FEAT-JARVIS-002 resolved in §1). Compatibility notes:

- The single-subagent shape aligns with **ADR-ARCH-011** verbatim — the role-via-input pattern is the exact "prompt-driven modes of the same model" that the ADR specifies.
- **ADR-ARCH-001**'s local-first constraint holds — the AsyncSubAgent runs on `gpt-oss-120b` via llama-swap (no cloud on unattended path). `escalate_to_frontier` is the *only* cloud call-site Jarvis makes and is constitutionally attended-gated per **ADR-ARCH-027**.
- **ADR-ARCH-012**'s swap-aware voice-latency policy is load-bearing for the LlamaSwapAdapter's `/running` + `/log` read surface. DDR-015 stubs the reads in Phase 2; live reads land with FEAT-JARVIS-004.
- **ADR-ARCH-022** (belt+braces constitutional rules) — `escalate_to_frontier` enforces at three layers: prompt, executor assertion, and tool-registry absence (DDR-014). Exceeds the ADR's two-layer minimum.
- **ADR-ARCH-023** (permissions constitutional, not reasoning-adjustable) — the `ambient_tool_factory` is a lifecycle-built list; the reasoning model cannot toggle its contents. Honoured.
- **ADR-ARCH-025** (DeepAgents 0.6 upgrade gated) — this feature is the first real consumer of the 0.5.3 `AsyncSubAgent` preview; the routing e2e test + subagent structural tests become the regression suite the 0.6 upgrade gate runs.
- **ADR-ARCH-026** (single instance, no horizontal scaling) — two graphs, one process, one container. Unchanged.
- **ADR-ARCH-030** (budget envelope) — `escalate_to_frontier` is the only source of cloud spend; trace-tagged for post-hoc review. Honoured.
- **DDR-001** (no network protocols Phase 1/2) — `langgraph.json` is a deployment manifest, not a network-protocol surface; `escalate_to_frontier`'s outbound HTTPS is a consumer, not a server. Honoured.
- **DDR-005** (dispatch-by-capability) — `escalate_to_frontier` is *not* a capability-driven dispatch; it's a named, constitutionally-gated tool. The two patterns coexist — capability-driven for fleet agents, named-tool for the cloud escape. Consistent with ADR-ARCH-027's framing.
- **DDR-008** (capabilities via tool *and* prompt injection) — unchanged; FEAT-JARVIS-003 adds subagent metadata to the prompt but not to the capability registry.
- **DDR-009** (stub transport semantics) — `escalate_to_frontier` uses **real** transport (cloud provider SDK), not a stub. The capability it exercises is orthogonal to the `dispatch_by_capability` stub that DDR-009 governs; no conflict.

One **forward compatibility note** worth flagging: if FEAT-JARVIS-006 (Telegram adapter) reshapes `adapter_id` semantics, the attended-gate executor assertion in `escalate_to_frontier` will need a verification pass — captured as `ASSUM-ATTENDED-ADAPTER-ID` below.

## 12. Assumptions carried forward

| Assumption | Reason it's not settled here |
|---|---|
| `ASSUM-LLAMASWAP-API` | The `/running` + `/log` endpoints at `http://promaxgb10-41b1:9000` are not formally contracted by the llama-swap project; ADR-ARCH-012 references them by behaviour. Phase 2 **stubs** the adapter; FEAT-JARVIS-004 wires live reads and, if the endpoint shape diverges, a thin protocol adapter lands there. |
| `ASSUM-ASYNC-ROLE-PROPAGATION` | DeepAgents 0.5.3's `AsyncSubAgent` preview accepts extra keys in `input={}` and surfaces them in the subgraph's initial state per the 19 April 2026 SDK review. `test_subagents_jarvis_reasoner.py` verifies this at compile-time under the test harness; if a 0.6 breakage occurs, the fallback is to inline `role` inside `prompt` itself as a leading `[role=...]` token. |
| `ASSUM-FRONTIER-CALLER-FRAME` | `AsyncSubAgentMiddleware` is believed to expose enough metadata on the tool-call frame for the non-ambient assertion. If not (verified at test time), the executor assertion falls back to session-state lookup via `SessionManager.current_session()`. Either path preserves the belt+braces property. |
| `ASSUM-ATTENDED-ADAPTER-ID` | The attended-adapter set `{telegram, cli, dashboard, reachy}` is the ADR-ARCH-016 consumer-surface list. If FEAT-JARVIS-006 reshapes adapter identity (e.g. per-user sub-adapters), the assertion's adapter-id comparison needs a verification pass. Flagged at that feature's `/system-design`. |
| `ASSUM-ROLE-SET-STABILITY` | `RoleName` is closed at v1 (DDR-011). If the learning flywheel in FEAT-JARVIS-008 (v1.5) surfaces a missing role category, adding a member is additive and non-breaking for the enum; prompts and `ROLE_PROMPTS` need the new entry and the supervisor prompt's role-dispatch block needs a line. The routing e2e test is the regression surface. |

## 13. Next steps

1. **Approve the C4 L3 diagram** at [diagrams/jarvis-reasoning-l3.md §Review gate](diagrams/jarvis-reasoning-l3.md).
2. **Seed design to Graphiti** (commands offered at the end of this `/system-design` run — `project_design` group for contracts/models, `architecture_decisions` group for DDRs).
3. **Proceed to `/feature-spec FEAT-JARVIS-003`** — Gherkin scenarios grounded in this design. Primary scenarios:
   - Rich asks for a critique → role-dispatch to `jarvis-reasoner` with `role=critic`.
   - Rich asks Jarvis to ask Gemini → `escalate_to_frontier` succeeds on CLI adapter.
   - An ambient watcher attempts `escalate_to_frontier` → structured error.
4. **Then `/feature-plan FEAT-JARVIS-003`** — task breakdown per [phase2-build-plan.md Step 8 commit order](../../research/ideas/phase2-build-plan.md), adjusted for single-subagent + frontier-tool shape.
5. **Then AutoBuild** — follow the adjusted commit order: config → llamaswap adapter → subagent prompts → jarvis_reasoner graph → subagent_registry → escalate_to_frontier tool → supervisor prompt update → supervisor factory update → `langgraph.json` → extended `test_supervisor_with_subagents.py` → `test_routing_e2e.py`.
6. **Phase 2 close criteria** extend Phase 1's day-1 conversation with: `jarvis chat` invokes `start_async_task(name='jarvis-reasoner', role=…)` correctly on three canned role prompts; `escalate_to_frontier` returns a real Gemini 3.1 Pro response when asked explicitly.

## 14. File manifest

```
docs/design/FEAT-JARVIS-003/
├── design.md                                                       ← this file
├── contracts/
│   ├── API-subagent.md                                             ← AsyncSubAgent entry + role-input contract
│   ├── API-tools.md                                                ← escalate_to_frontier + 5 middleware tools
│   └── API-internal.md                                             ← module-level Python API
├── models/
│   └── DM-subagent-types.md                                        ← RoleName, AsyncTaskInput, SwapStatus,
│                                                                   #   FrontierEscalationContext, FrontierTarget
├── diagrams/
│   └── jarvis-reasoning-l3.md                                      ← C4 L3 (mandatory review gate)
└── decisions/
    ├── DDR-010-single-async-subagent-supersedes-four-roster.md
    ├── DDR-011-role-enum-closed-v1.md
    ├── DDR-012-subagent-module-import-compilation.md
    ├── DDR-013-langgraph-json-at-repo-root.md
    ├── DDR-014-escalate-to-frontier-in-dispatch-tool-module.md
    └── DDR-015-llamaswap-adapter-with-stubbed-health.md
```

---

*"One local reasoning model that knows which role to apply, which specialist to invoke, and when to escalate."* — [ARCHITECTURE.md §1](../../architecture/ARCHITECTURE.md)
