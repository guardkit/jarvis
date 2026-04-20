# Phase 2: Dispatch Foundations — Core Tools, Dispatch Tools & Async Subagents — Scope Document

## For: Claude Code `/system-design` → `/feature-spec` → `/feature-plan` → AutoBuild (per feature)
## Date: 20 April 2026
## Status: Blocked on Phase 1 completion (FEAT-JARVIS-001 merged + day-1 conversation validated). Ready for `/system-design FEAT-JARVIS-002` once Phase 1 closes.
## Context: Phase 1 landed the supervisor skeleton, session lifecycle, and `jarvis` CLI. The supervisor has DeepAgents built-ins only — no custom tools, no subagents. Phase 2 gives the supervisor its *dispatch vocabulary*: the tools it can reach for and the subagents it can delegate to. Model-routing as a reasoning decision (D43) begins working in practice at the end of this phase.

---

## Motivation

Phase 1's supervisor can hold a conversation. Phase 2 is what makes it *Jarvis*. The one-sentence thesis — *one reasoning model that knows which reasoning model to use* — requires two things Phase 1 deliberately deferred:

1. **A tool surface for dispatch.** `call_specialist`, `queue_build`, and the non-dispatch tools (file read, web search, calendar stub, calculator) that make the supervisor a useful general-purpose agent rather than a chatbot. The capability catalogue reader that turns `nats-core`'s KV manifest registry into a tool docstring the reasoning model reads and decides over — same pattern as Forge ADR-ARCH-015/016 adopted fleet-wide.
2. **Async subagents for model routing.** The four launch subagents — `deep_reasoner` (Gemini 3.1 Pro), `adversarial_critic` (Claude Opus 4.7), `long_research` (GPT-5.4), `quick_local` (vLLM Qwen3-Coder-Next on GB10) — declared at supervisor startup via DeepAgents 0.5.3's `AsyncSubAgent` primitive with ASGI transport per ADR-J-P7. Descriptions carry cost + latency signals so the supervisor has skin in the routing decision.

Phase 2 pairs these because they are *one architectural idea in two forms*. Tools and subagents are both capability-driven dispatch targets that the supervisor's reasoning model picks between. The supervisor's system prompt teaches one preference — "cheapest-that-fits, escalate on need" — that applies across both. Building them in one phase keeps the prompt coherent and lets Phase 2's end-to-end test exercise the whole routing surface in one pass.

Phase 2 does **not** wire any of these tools to NATS yet. `call_specialist` in Phase 2 is *mockable at the tool boundary* — the dispatch tool exists, its signature and docstring are real, but its transport is stubbed. FEAT-JARVIS-004 replaces the stub with real NATS `agents.command.{agent_id}` / `agents.result.{agent_id}` round-trips. This lets Phase 2 prove the reasoning-over-tool-descriptions pattern works before introducing transport risk.

---

## Scope: Two Features

### FEAT-JARVIS-002: Core Tools & Capability-Driven Dispatch Tools

**Problem:** Phase 1's supervisor has no way to do anything except reason. Real Jarvis value begins when the supervisor can read a file, look something up on the web, check the calendar stub, and — crucially — dispatch to specialists and the build queue. The dispatch tools in particular are the concrete realisation of ADR-J-P1 (Jarvis-as-GPA-with-dispatch-tools). Without them, "dispatch is tool selection" is aspirational. Additionally, the supervisor must be able to read the fleet's capability catalogue dynamically — not from a hardcoded list, but from the `nats-core` KV manifest registry, rendered into tool docstrings the reasoning model reads at decision time. This is the fleet-wide inheritance of Forge's ADR-ARCH-015 (capability-driven dispatch) and ADR-ARCH-016 (fleet is the catalogue).

**Changes required:**

#### 1. Non-dispatch tools (`src/jarvis/tools/general.py` or per-tool files)

A small, well-chosen set of general tools — enough to make the supervisor meaningfully useful in reactive Pattern A mode without ballooning Phase 2's scope:

- `read_file(path: str) -> str` — reads a file from Rich's filesystem with the same path-safety guards DeepAgents' built-in filesystem uses; thin wrapper so tool invocations are traceable.
- `search_web(query: str, max_results: int = 5) -> list[WebResult]` — thin wrapper around a configured web-search provider (Tavily or similar; exact provider lands as an ADR at `/system-design` time, or stays provider-agnostic via an interface). Provider key read from config; if no key, tool raises a clear `ConfigurationError` the supervisor surfaces to Rich.
- `get_calendar_events(window: Literal["today", "tomorrow", "this_week"] = "today") -> list[CalendarEvent]` — **stub for Phase 2.** Returns an empty list or a canned list for tests. Real calendar integration is a v1.5 concern. Ships as a stub now so the `morning-briefing` skill in FEAT-JARVIS-007 has the tool signature ready.
- `calculate(expression: str) -> str` — wraps `mathjs`-style safe evaluation (no `eval`). Small but demonstrably useful; prevents the supervisor from wasting a model call on arithmetic.

Every tool is a `@tool`-decorated function (LangChain tool pattern) with a rich docstring. Docstrings are *the contract with the reasoning model* — they state what the tool does, when to use it, when not to use it, and the cost/latency signal where relevant.

#### 2. Capability catalogue reader (`src/jarvis/tools/capabilities.py`)

The reader that turns `nats-core`'s KV manifest registry into a tool-level capability catalogue the supervisor reads:

- Exposes `list_available_capabilities() -> list[CapabilityDescriptor]` as a tool. Descriptors include `agent_id`, `role`, `description`, `capability_list`, `cost_signal`, `latency_signal`, `last_heartbeat_at`, `trust_tier`.
- Phase 2 implementation reads from an **in-memory stub registry** populated at startup from `config/stub_capabilities.yaml`. The stub models two architect-agent-shaped capabilities, one product-owner-agent-shaped, and one ideation-agent-shaped — enough for the supervisor to exercise routing decisions during Phase 2 tests. FEAT-JARVIS-004 replaces the stub with the real `NATSKVManifestRegistry` read path; the `CapabilityDescriptor` shape stays identical.
- Exposes `capabilities_refresh()` and `capabilities_subscribe_updates()` as **no-ops in Phase 2**. Signatures land now so FEAT-JARVIS-004 wires them to the real KV watch without changing the tool surface.

Same pattern as Forge's: no pre-coded agent catalogue (ADR-ARCH-016), no hardcoded `agent_id` (ADR-ARCH-015). The reasoning model picks by reading descriptions at decision time.

#### 3. Dispatch tools (`src/jarvis/tools/dispatch.py`)

The two dispatch tools at the heart of ADR-J-P1:

- `call_specialist(agent_id: str, instruction: str, context: dict = {}) -> SpecialistResult` — dispatches a command to a specialist agent and awaits a result. **Phase 2 implementation: stubbed transport.** The tool builds the `CommandPayload` per `nats-core`'s contract, logs it as if publishing, and returns a stubbed `SpecialistResult` matching `ResultPayload`'s shape. Behaviour is configurable per test: success with canned output, timeout, error. This lets FEAT-JARVIS-002 tests exercise the supervisor's dispatch reasoning without requiring NATS. FEAT-JARVIS-004 replaces the stub.
- `queue_build(feature_id: str, feature_spec_ref: str, repo: str, triggered_by: str = "jarvis", correlation_id: str | None = None, parent_request_id: str | None = None) -> QueueBuildAck` — builds `BuildQueuedPayload` per Forge ADR-SP-014 Pattern A; **stubbed transport in Phase 2** (log-only). FEAT-JARVIS-005 replaces the stub with the real `pipeline.build-queued.{feature_id}` JetStream publish.

Both tools' docstrings carry the *real* dispatch semantics — cost signal, latency signal, when to use, when not to use. The reasoning model should behave identically in Phase 2 (stubbed) and Phase 3 (real NATS) because the *contract* is the tool docstring, not the transport.

The Phase 2 `ResultPayload` / `QueueBuildAck` stubs must match the `nats-core` Pydantic models exactly (importing from `nats-core` is acceptable even though the actual NATS client isn't used yet). This keeps the seam honest.

#### 4. Tool registration in the supervisor factory

`build_supervisor(config)` in `src/jarvis/agents/supervisor.py` (landed Phase 1) grows a Phase 2 tool list:

- General tools: `read_file`, `search_web`, `get_calendar_events`, `calculate`
- Capability catalogue: `list_available_capabilities`, `capabilities_refresh`, `capabilities_subscribe_updates`
- Dispatch: `call_specialist`, `queue_build`

The factory's signature does not change. The supervisor system prompt gains a section on tool usage — "prefer `calculate` over mental arithmetic", "use `list_available_capabilities` before `call_specialist` if the supervisor hasn't already retrieved capabilities this session", etc.

Smoke test from the conversation starter §4: "supervisor lists available capabilities and picks correctly for three canned prompts." That translates to three end-to-end tests with a mocked LLM returning deterministic tool-call sequences — one for file read, one for `calculate`, one for `call_specialist` with a prompt the reasoning model should route to `architect`. These are *structural* tests of the tool wiring, not *behavioural* tests of the reasoning model (LLM quality is out of scope for unit tests).

---

### FEAT-JARVIS-003: Async Subagents for Model Routing

**Problem:** Phase 2's dispatch tools let the supervisor route to *other agents*. Async subagents let it route to *other models* — same-process, different brain, parallelisable. Per ADR-J-P2 (four launch subagents) and ADR-J-P7 (ASGI transport), the supervisor needs four `AsyncSubAgent` instances declared at startup: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`. Each is a thin `create_deep_agent(model=...)` graph with a carefully worded description that carries the cost + latency signal. The supervisor's reasoning model then has skin in the routing decision — picking Opus 4.7 for a shallow Q&A is expensively wrong and the description says so.

This is a preview feature. DeepAgents 0.5.3 ships `AsyncSubAgentMiddleware` as preview (the reason for the `<0.6` upper bound on the pin per ADR-J-001). Phase 2 is the first feature to exercise it. The Forge ADR-ARCH-031 precedent (19 April 2026) establishes the pattern — we follow the same shape.

**Changes required:**

#### 1. Subagent graph definitions (`src/jarvis/agents/subagents/`)

Four sub-packages, each defining one subagent graph:

- `src/jarvis/agents/subagents/deep_reasoner.py` — `create_deep_agent(model="google_genai:gemini-3.1-pro", system_prompt=DEEP_REASONER_PROMPT, tools=[])`. System prompt: "You are a deep-reasoning subagent. You receive structured problems from a supervisor and return architectural synthesis, multi-step reasoning chains, and 1M-token-context work. You do not dispatch further. You return structured output." No tools — subagents are leaves, not supervisors.
- `src/jarvis/agents/subagents/adversarial_critic.py` — same shape, `model="anthropic:claude-opus-4-7"`, system prompt emphasises Coach-style evaluation, subtle flaw identification, calibrated scoring.
- `src/jarvis/agents/subagents/long_research.py` — same shape, `model="openai:gpt-5.4"`, system prompt emphasises multi-hour open-ended research, persistent web search (tool: `search_web` from FEAT-JARVIS-002 — reused so subagents aren't reinventing), synthesis.
- `src/jarvis/agents/subagents/quick_local.py` — same shape, `model="vllm:qwen3-coder-next"` via the local vLLM endpoint on GB10, system prompt emphasises low-latency low-stakes work, privacy-sensitive content, quick lookups. Configurable endpoint URL from `JarvisConfig` (added in Phase 2).

Each graph has a `graph_id` matching the subagent name. The graphs are compiled at module import time (or lazily at first use — the ADR from `/system-design` pins which).

#### 2. `AsyncSubAgent` declarations (`src/jarvis/agents/subagent_registry.py`)

A `build_async_subagents(config) -> list[AsyncSubAgent]` function returning the four instances:

```python
def build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]:
    return [
        AsyncSubAgent(
            name="deep_reasoner",
            description=(
                "Gemini 3.1 Pro. For deep reasoning, architectural synthesis, "
                "multi-step chains-of-thought, and 1M-token-context work. "
                "Moderate cost (~$1.25/Mtok input, ~$5/Mtok output), ~15-30s typical "
                "latency per turn. Use when the problem genuinely requires long-form "
                "reasoning; do not use for factual lookups, quick Q&A, or code-completion."
            ),
            graph_id="deep_reasoner",
        ),
        AsyncSubAgent(
            name="adversarial_critic",
            description=(
                "Claude Opus 4.7. For quality evaluation, identifying subtle flaws, "
                "Coach-style adversarial review. Higher cost (~$15/Mtok output) — "
                "reserve for tasks where flaw detection matters more than throughput. "
                "Do not use for routine Q&A or factual lookups."
            ),
            graph_id="adversarial_critic",
        ),
        AsyncSubAgent(
            name="long_research",
            description=(
                "GPT-5.4. For multi-hour open-ended research with persistent web "
                "search and synthesis. High wall-clock time (can run 30min+). "
                "Use when the work is research-shaped and bounded only by quality, "
                "not latency."
            ),
            graph_id="long_research",
        ),
        AsyncSubAgent(
            name="quick_local",
            description=(
                "Qwen3-Coder-Next via local vLLM on GB10. For quick lookups, "
                "low-stakes reasoning, privacy-sensitive content that should not "
                "leave the premises. Near-zero cost, sub-second latency when GB10 "
                "is idle; may degrade under AutoBuild load (see JA6 fallback policy)."
            ),
            graph_id="quick_local",
        ),
    ]
```

Descriptions are the single most important authoring concern in this feature. They are the contract with the reasoning model. Changes to these strings change routing behaviour.

#### 3. Supervisor wiring (`src/jarvis/agents/supervisor.py`)

`build_supervisor(config)` gains a second change: the compiled graph is produced with `async_subagents=build_async_subagents(config)` passed through to DeepAgents 0.5.3's supervisor factory. The `AsyncSubAgentMiddleware` wires in `start_async_task`, `check_async_task`, `wait_for_async_tasks`, `cancel_async_task`, `list_async_tasks` as tools available to the supervisor.

Supervisor system prompt grows a subagent-routing section: "You have four async subagents available. Prefer `quick_local` by default for low-stakes work; escalate to `deep_reasoner` when the problem requires long-form reasoning; invoke `adversarial_critic` when quality evaluation is the goal; use `long_research` for open-ended research with no latency budget. Always check cost and latency signals in the subagent description before dispatching." The prompt is additive to Phase 1's — it does not rewrite the attended-conversation posture.

#### 4. ASGI transport configuration (`src/jarvis/infrastructure/asgi.py` or `langgraph.json`)

Per ADR-J-P7 (ASGI transport for co-deployed subagents — same as Forge ADR-ARCH-031's default):

- A `langgraph.json` at repo root declares the five graphs (supervisor + four subagents) and their ASGI transport configuration. `/system-design` pins whether this lives at the repo root (LangGraph convention) or inside `src/jarvis/`.
- `JarvisConfig` gains a `vllm_endpoint_url: str = "http://localhost:8000/v1"` field for `quick_local`.
- No HTTP transport. No separate deployment. Single-process, single-container, multiple graphs. Matches Forge's default.

#### 5. `quick_local` fallback hook (`src/jarvis/agents/subagents/quick_local.py`)

JA6 from the architecture conversation-starter asks: what happens to `quick_local` when AutoBuild is hammering the GB10 GPU? Phase 2 does not *solve* JA6 (the full policy lands as an ADR the `/system-design` step produces), but it lands the hook:

- `quick_local.py` reads a `system.health.vllm`-like signal (stubbed in Phase 2 — returns "healthy"). When the signal is "degraded", the graph optionally falls back to a cloud cheap-tier model (`gemini-flash-latest` or equivalent, pinned by ADR). Fallback is logged so trace-rich records (once ADR-FLEET-001 writes go live in FEAT-JARVIS-004) capture the event.
- Phase 2 ships the fallback branch *tested with the degraded signal stubbed*. The real health-signal producer is a v1.5 concern.

#### 6. End-to-end routing test

The key acceptance test for Phase 2 is routing-correctness at the tool-call-sequence level:

- Mocked LLM returning a deterministic routing decision for each of these prompts: "What's 15% of 847?" (expect `calculate`), "Summarise this file: /tmp/test.md" (expect `read_file`), "Find me recent papers on Meta-Harness" (expect `long_research` via `start_async_task`), "Review this architecture doc for subtle flaws" (expect `adversarial_critic` via `start_async_task`), "Quickly, what's my next meeting?" (expect `quick_local` via `start_async_task` calling the stubbed `get_calendar_events`), "Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo" (expect `queue_build`), "Ask the architect agent for a C4 diagram of Jarvis" (expect `call_specialist` with `agent_id="architect"`).
- Tests assert the tool-call sequence, not the final natural-language output. Same pattern as specialist-agent's Player-Coach test structure.

This is the first time Jarvis genuinely is *"one reasoning model that knows which reasoning model to use."*

---

## Do-Not-Change

1. **Phase 1 outputs.** `pyproject.toml`, `src/jarvis/{__init__,shared,config,prompts,infrastructure,sessions,cli}/`, `tests/conftest.py` and the Phase 1 test modules. Phase 2 *adds* to these (new config fields, new prompt sections, new test fixtures) but does not rewrite them.
2. **The Phase 1 supervisor system prompt's attended-conversation posture + "cheapest-that-fits" preference.** Phase 2 extends the prompt (adds tool usage section, subagent routing section) but preserves the Phase 1 content verbatim.
3. **Fleet v3 D40–D46** and **ADR-J-P1..P10.** Phase 2 is the first real consumer of P1, P2, P7 — honouring, not re-litigating.
4. **ADR-FLEET-001 trace-richness schema shape.** Phase 2 does not *write* to `jarvis_routing_history` (no NATS yet — FEAT-JARVIS-004's job) but subagent dispatch sequences and tool call sequences are *shaped* to be schema-compatible when FEAT-JARVIS-004 lights up the writes.
5. **No NATS client import in Phase 2.** `nats-py` does not appear in `pyproject.toml` dependencies until FEAT-JARVIS-004. `nats-core` Pydantic models can be imported (for `CommandPayload`, `ResultPayload`, `BuildQueuedPayload` shape compliance) because they're pure data classes.
6. **No new adapters.** CLI remains the only adapter in Phase 2. Telegram is FEAT-JARVIS-006 (Phase 4).
7. **Subagent descriptions are the contract.** Once landed, changes to the four descriptions require an explicit decision recorded in the commit message — they shape routing behaviour and the learning flywheel (FEAT-JARVIS-008, v1.5) will *measure against* them.
8. **Singular topic convention (ADR-SP-016)** on any stub payload topic strings.

---

## Success Criteria

1. All Phase 1 tests still pass (no regressions).
2. The 10 Phase 2 tools (`read_file`, `search_web`, `get_calendar_events`, `calculate`, `list_available_capabilities`, `capabilities_refresh`, `capabilities_subscribe_updates`, `call_specialist`, `queue_build`, plus any `/system-design` names) are registered on the supervisor and each has a unit test for its happy path + one failure case.
3. The four `AsyncSubAgent` instances are built at supervisor startup and the `AsyncSubAgentMiddleware` dispatch tools (`start_async_task` etc.) are available to the reasoning model.
4. End-to-end routing test passes: the seven canned prompts produce the expected tool-call sequences.
5. `jarvis chat` held with a real supervisor model exhibits noticeably better behaviour than Phase 1 — uses `calculate` for arithmetic, `read_file` when asked to read a file, dispatches to `quick_local` for quick lookups.
6. `langgraph.json` is valid and `langgraph dev` can spin all five graphs locally.
7. Capability catalogue stub renders to the supervisor correctly — the reasoning model can see the four stub descriptors and their descriptions.
8. `quick_local` fallback branch is covered by a test using the stubbed "degraded" health signal.
9. Ruff + mypy clean on all new `src/jarvis/` modules.
10. Day-1 conversation criterion from Phase 1 still holds — Memory Store round-trip across sessions still works.

---

## Files That Will Change

| File | Feature | Change Type |
|------|---------|------------|
| `pyproject.toml` | FEAT-JARVIS-002, -003 | **UPDATED** — add `langchain-tavily` (or chosen web-search provider), `mathjs`-equivalent if used; add `nats-core` as a dependency for Pydantic payload imports (no network use yet); add provider SDKs for the four subagent models |
| `src/jarvis/config/settings.py` | FEAT-JARVIS-002, -003 | **UPDATED** — add `web_search_provider_key`, `vllm_endpoint_url`, subagent-model env vars |
| `src/jarvis/tools/general.py` | FEAT-JARVIS-002 | **NEW** — `read_file`, `search_web`, `get_calendar_events`, `calculate` |
| `src/jarvis/tools/capabilities.py` | FEAT-JARVIS-002 | **NEW** — `list_available_capabilities`, refresh + subscribe stubs, `CapabilityDescriptor` type |
| `src/jarvis/tools/dispatch.py` | FEAT-JARVIS-002 | **NEW** — `call_specialist`, `queue_build` (both stubbed transport) |
| `src/jarvis/config/stub_capabilities.yaml` | FEAT-JARVIS-002 | **NEW** — Phase 2 stub registry (architect, product-owner, ideation shapes) |
| `src/jarvis/prompts/supervisor_prompt.py` | FEAT-JARVIS-002, -003 | **UPDATED** — add tool usage section, subagent routing section |
| `src/jarvis/agents/supervisor.py` | FEAT-JARVIS-002, -003 | **UPDATED** — wire tool list + `async_subagents` |
| `src/jarvis/agents/subagent_registry.py` | FEAT-JARVIS-003 | **NEW** — `build_async_subagents(config)` |
| `src/jarvis/agents/subagents/{__init__,deep_reasoner,adversarial_critic,long_research,quick_local}.py` | FEAT-JARVIS-003 | **NEW** — four subagent graph definitions |
| `src/jarvis/infrastructure/asgi.py` | FEAT-JARVIS-003 | **NEW** — ASGI transport wiring if not expressible in `langgraph.json` alone |
| `langgraph.json` | FEAT-JARVIS-003 | **NEW** — declares supervisor + four subagent graphs, ASGI transport |
| `tests/test_tools_general.py` | FEAT-JARVIS-002 | **NEW** — per-tool happy path + one failure case each |
| `tests/test_tools_capabilities.py` | FEAT-JARVIS-002 | **NEW** — catalogue reader over stub |
| `tests/test_tools_dispatch.py` | FEAT-JARVIS-002 | **NEW** — `call_specialist` + `queue_build` over stubbed transports |
| `tests/test_subagent_registry.py` | FEAT-JARVIS-003 | **NEW** — four subagents built, descriptions present, graph IDs unique |
| `tests/test_subagents_*.py` | FEAT-JARVIS-003 | **NEW** — one structural test per subagent (no LLM calls, `FakeListChatModel`) |
| `tests/test_routing_e2e.py` | FEAT-JARVIS-003 | **NEW** — the seven-canned-prompt routing test with mocked LLM |
| `tests/test_quick_local_fallback.py` | FEAT-JARVIS-003 | **NEW** — fallback branch with stubbed degraded signal |
| `docs/design/FEAT-JARVIS-002/design.md` | FEAT-JARVIS-002 | **NEW** — produced by `/system-design` |
| `docs/design/FEAT-JARVIS-003/design.md` | FEAT-JARVIS-003 | **NEW** — produced by `/system-design` |
| `features/feat-jarvis-002-*/...` | FEAT-JARVIS-002 | **NEW** — produced by `/feature-spec` |
| `features/feat-jarvis-003-*/...` | FEAT-JARVIS-003 | **NEW** — produced by `/feature-spec` |
| `tasks/FEAT-JARVIS-002-*.md` | FEAT-JARVIS-002 | **NEW** — produced by `/feature-plan` |
| `tasks/FEAT-JARVIS-003-*.md` | FEAT-JARVIS-003 | **NEW** — produced by `/feature-plan` |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/`.

---

## Open Questions `/system-design` Resolves (for Phase 2's benefit)

- **Web search provider.** Tavily (matches specialist-agent) is the default preference; ADR may pin.
- **`calculate` implementation.** Safe-evaluator library choice.
- **`langgraph.json` location.** Repo root (LangGraph convention) vs `src/jarvis/`.
- **Subagent graph compilation timing.** Module import vs lazy-at-first-use.
- **`quick_local` fallback policy.** The full JA6 answer — exact thresholds, fallback target model, logging shape. Phase 2 ships the hook; the policy lands as ADR-J-XXX.
- **`call_specialist` timeout + retry semantics.** Even stubbed, the tool needs a defensible timeout default and a retry-with-redirect behaviour spec so FEAT-JARVIS-004 swaps transports cleanly.

---

*Scope document: 20 April 2026*
*Input to: `/system-design FEAT-JARVIS-002`, `/system-design FEAT-JARVIS-003`, then `/feature-spec` for each.*
*"Dispatch is tool selection."*
