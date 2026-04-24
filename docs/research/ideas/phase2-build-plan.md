# Phase 2 Build Plan — Dispatch Foundations: Core Tools, Dispatch Tools & Async Subagents

> **⚠️ PARTIALLY SUPERSEDED (2026-04-23).** This plan was written on 2026-04-20 *before* the `/system-arch` session produced [ADR-ARCH-001](../../architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md) (local-first; no cloud LLMs on unattended paths), [ADR-ARCH-011](../../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md) (single `jarvis-reasoner` subagent with role-dispatch), [ADR-ARCH-012](../../architecture/decisions/ADR-ARCH-012-swap-aware-voice-latency-policy.md) (swap-aware voice-latency policy supersedes JA6), and [ADR-ARCH-027](../../architecture/decisions/ADR-ARCH-027-attended-only-cloud-escape-hatch.md) (attended-only `escalate_to_frontier`).
>
> The **FEAT-JARVIS-003 four-cloud-subagent roster** (`deep_reasoner`/`adversarial_critic`/`long_research`/`quick_local`) and the **JA6 cloud-cheap-tier fallback hook** are retired. Reconciled in [FEAT-JARVIS-002 design](../../design/FEAT-JARVIS-002/design.md) §11 (C2) and [FEAT-JARVIS-003 design](../../design/FEAT-JARVIS-003/design.md) + its [DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md) + [DDR-015](../../design/FEAT-JARVIS-003/decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md).
>
> See [docs/history/superseded-designs.md](../../history/superseded-designs.md) for the full retirement narrative.
>
> **FEAT-JARVIS-002 sections remain authoritative.** Everything in this plan that is FEAT-JARVIS-003-shaped is the old design — read the FEAT-JARVIS-003 design doc for the canonical shape.

## For: Giving Jarvis's supervisor its dispatch vocabulary — the tools it reaches for and the subagents it delegates to. First phase where "one reasoning model that knows which reasoning model to use" works in practice.
## Date: 20 April 2026
## Status (2026-04-24): Phase 1 closed (22 Apr). Both `/system-design` runs complete (23 Apr). `/feature-spec` complete for both features (24 Apr). `/feature-plan` complete for FEAT-JARVIS-002 → AutoBuild feature [`FEAT-J002.yaml`](../../../.guardkit/features/FEAT-J002.yaml) (23 subtasks, complexity 6, estimated). **Next: `/feature-plan FEAT-JARVIS-003` → AutoBuild YAML, then `/feature-build FEAT-J002` + `/feature-build FEAT-J003`.**
## Repo: `guardkit/jarvis`
## Machine: MacBook Pro M2 Max (planning + build via Claude Code)

## AutoBuild Feature References

The `/feature-plan` command produces structured YAML feature files under
`.guardkit/features/`. These files are the authoritative AutoBuild contract
— each maps to a subtask directory under `tasks/backlog/<feature-slug>/`.

| Feature | AutoBuild YAML | Task directory | Status |
|---|---|---|---|
| FEAT-JARVIS-001 | [`FEAT-JARVIS-001.yaml`](../../../.guardkit/features/FEAT-JARVIS-001.yaml) | `tasks/backlog/project-scaffolding-supervisor-sessions/` | ✅ Phase 1 — AutoBuild complete, closed 22 Apr |
| FEAT-JARVIS-002 | [`FEAT-J002.yaml`](../../../.guardkit/features/FEAT-J002.yaml) | [`tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/`](../../../tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/) | 🟡 Plan landed 24 Apr — 23 subtasks ready for `/feature-build FEAT-J002` |
| FEAT-JARVIS-003 | *pending — produced by `/feature-plan FEAT-JARVIS-003`* | *pending* | 🔲 Feature spec complete 24 Apr; plan is the next step |

`/feature-build FEAT-<id>` executes the AutoBuild cycle — player-coach loop
per subtask, BDD oracle (R2) for tagged scenarios, and between-wave
smoke gates (R3) if declared in the YAML.

---

## Status Log

| Date | Step | Outcome |
|------|------|---------|
| 2026-04-20 | `phase2-dispatch-foundations-scope.md` written | This document's companion scope doc — input to `/system-design FEAT-JARVIS-002` and `/system-design FEAT-JARVIS-003`. |
| 2026-04-20 | `phase2-build-plan.md` written | This document. |
| 2026-04-22 | Phase 1 close | All Phase 1 success criteria met, day-1 multi-turn recall validated, commits landed (`bce53d8` Phase 1 closeout + Step 7/8 + FIX-005). |
| 2026-04-23 | `/system-design FEAT-JARVIS-002` | Design doc at [`docs/design/FEAT-JARVIS-002/design.md`](../../design/FEAT-JARVIS-002/design.md). 5 DDRs landed (DDR-005..009). Resolved contradiction **C1**: `call_specialist(agent_id=…)` → `dispatch_by_capability(tool_name=…)` per [DDR-005](../../design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md). Flagged **C2** (four-cloud-subagents) for FEAT-JARVIS-003. |
| 2026-04-23 | `/system-design FEAT-JARVIS-003` | Design doc at [`docs/design/FEAT-JARVIS-003/design.md`](../../design/FEAT-JARVIS-003/design.md). 6 DDRs landed (DDR-010..015). **Scope-doc four-cloud-subagent roster + JA6 fallback retired** per [ADR-ARCH-001](../../architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md) / [ADR-ARCH-011](../../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md) / [ADR-ARCH-012](../../architecture/decisions/ADR-ARCH-012-swap-aware-voice-latency-policy.md) / [ADR-ARCH-027](../../architecture/decisions/ADR-ARCH-027-attended-only-cloud-escape-hatch.md). **See [docs/history/superseded-designs.md](../../history/superseded-designs.md)** for the full reframe narrative — this plan's FEAT-JARVIS-003 sections from "What Phase 2 IS" onward refer to the retired design; the authoritative shape is in the FEAT-JARVIS-003 design doc. C4 L3 diagram approved; Graphiti seeding running. Commit `b309d79`. |
| 2026-04-24 | `/feature-spec FEAT-JARVIS-002` | Gherkin scenarios landed at [`features/feat-jarvis-002-core-tools-and-dispatch/`](../../../features/feat-jarvis-002-core-tools-and-dispatch/). 42 scenarios across 5 groups (Key Examples, Boundary, Negative, Edge, Security/Concurrency/Integration) — 9 @key-example, 8 @boundary, 17 @negative, 14 @edge-case, 7 @smoke. 6 assumptions recorded (1 high / 4 medium / 1 low). 1 low-confidence assumption (ASSUM-006: snapshot-isolation semantics for Phase 3) flagged for review at FEAT-JARVIS-004 time. `dispatch_by_capability` naming honoured per DDR-005 (the command was phrased around the superseded `call_specialist` name). |
| 2026-04-24 | `/feature-spec FEAT-JARVIS-003` | Gherkin scenarios landed at [`features/feat-jarvis-003-async-subagent-and-frontier-escape/`](../../../features/feat-jarvis-003-async-subagent-and-frontier-escape/). 44 scenarios (11 @smoke, 1 @regression). 6 assumptions (0 high / 5 medium / 1 low) — review required. Spec consumes the reframed design per DDR-010..015: single `jarvis-reasoner` subagent with closed-enum `role`, module-import compilation, `langgraph.json` at repo root, `escalate_to_frontier` with three-layer belt+braces gating, `LlamaSwapAdapter` with stubbed health. |
| 2026-04-24 | `/feature-plan FEAT-JARVIS-002` | AutoBuild feature landed: [`.guardkit/features/FEAT-J002.yaml`](../../../.guardkit/features/FEAT-J002.yaml). 23 subtasks generated under [`tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/`](../../../tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/), aggregate complexity 6. Envelope-first concurrent fan-out (Option B, review score 12/12). DDR-009 swap-point discipline preserved — two primary grep anchors guard the FEAT-JARVIS-004/005 transport swap. Commit `76ca5ff`. Ready for `/feature-build FEAT-J002`. |
| *pending* | `/feature-plan FEAT-JARVIS-003` | AutoBuild feature YAML + task breakdown for FEAT-JARVIS-003. Reframed design commit order: config → llamaswap adapter → role prompts → jarvis_reasoner graph → subagent_registry → escalate_to_frontier → supervisor prompt → supervisor factory → `langgraph.json` → tests. Resolve the low-confidence assumption surfaced at `/feature-spec` time before starting. |
| *pending* | `/feature-build FEAT-J002` | AutoBuild cycle over the 23 subtasks in `FEAT-J002.yaml`. Player-coach loop per subtask; R2 BDD oracle runs `@task:TASK-J002-xxx`-tagged scenarios during `/task-work` Phase 4. |
| *pending* | `/feature-build FEAT-J003` | AutoBuild cycle for FEAT-JARVIS-003 once `/feature-plan FEAT-JARVIS-003` produces the YAML. Preview-feature risk sits here (DeepAgents 0.5.3 `AsyncSubAgentMiddleware` + ASGI multi-graph). |

---

## What Phase 2 IS

The phase that makes Jarvis *Jarvis*. Phase 1's supervisor could hold a conversation; Phase 2's supervisor has:

- **10 tools** it can reach for: 4 general-purpose (`read_file`, `search_web`, `get_calendar_events`, `calculate`), 3 capability-catalogue (`list_available_capabilities`, `capabilities_refresh`, `capabilities_subscribe_updates`), 2 dispatch (`call_specialist`, `queue_build`), plus the 5 `AsyncSubAgentMiddleware` primitives (`start_async_task` etc.).
- **4 async subagents** declared at startup: `deep_reasoner` (Gemini 3.1 Pro), `adversarial_critic` (Claude Opus 4.7), `long_research` (GPT-5.4), `quick_local` (vLLM Qwen3-Coder-Next on GB10). Descriptions carry cost + latency signals so routing has skin in the game.
- **A supervisor system prompt** that teaches *"cheapest-that-fits; escalate on need"* across both tool selection and subagent selection.

Phase 2 deliberately stubs the NATS transports for `call_specialist` and `queue_build`. The dispatch tools exist with real signatures, real docstrings, real `nats-core` Pydantic payload shapes — but no network calls. This lets Phase 2 prove the reasoning-over-tool-descriptions pattern *before* introducing transport risk. FEAT-JARVIS-004 and FEAT-JARVIS-005 swap the stubs for real NATS without changing the tool surface.

Async subagents, by contrast, are real from day one — DeepAgents 0.5.3's `AsyncSubAgent` with ASGI transport is the production path. The only stubbed piece on the subagent side is the `quick_local` fallback's `system.health.vllm` signal (stubbed "healthy" by default; tests override with "degraded" to exercise the fallback branch).

## What Phase 2 IS NOT

- Not NATS integration. `agents.command.{agent_id}` / `agents.result.{agent_id}` round-trips are FEAT-JARVIS-004 (Phase 3).
- Not Forge build-queue integration. `pipeline.build-queued.{feature_id}` JetStream publishes are FEAT-JARVIS-005 (Phase 3).
- Not the Telegram adapter (FEAT-JARVIS-006, Phase 4).
- Not skills or real Memory Store usage (FEAT-JARVIS-007, Phase 4 — Memory Store is wired in Phase 1 but not *used* via skills until Phase 4).
- Not the learning flywheel (FEAT-JARVIS-008, v1.5).
- Not `jarvis_routing_history` writes. Trace-rich schema *shape* is committed; actual writes to Graphiti land at FEAT-JARVIS-004.
- Not the full `quick_local` fallback policy — Phase 2 ships the hook + test; the policy ADR can refine the thresholds and fallback target.
- Not new adapters. CLI remains the only adapter.

## Success Criteria

1. All Phase 1 tests still pass (zero regressions).
2. 10 Phase 2 tools registered on the supervisor, each with a unit test (happy + one failure case).
3. 4 `AsyncSubAgent` instances built at supervisor startup; `AsyncSubAgentMiddleware` dispatch tools available.
4. End-to-end routing test passes: 7 canned prompts produce the expected tool-call sequences.
5. `jarvis chat` exhibits noticeably better behaviour than Phase 1 — arithmetic via `calculate`, file reads via `read_file`, quick lookups via `quick_local` subagent.
6. `langgraph.json` validates; `langgraph dev` spins all 5 graphs locally.
7. Capability catalogue stub renders 4 descriptors to the supervisor; reasoning model sees the full description text.
8. `quick_local` fallback branch covered by a test with the stubbed "degraded" health signal.
9. Ruff + mypy clean on new `src/jarvis/` modules.
10. Memory Store round-trip from Phase 1 still works.

---

## Phase 1 Results (Context)

Expected at Phase 2 start:

- Python scaffold in place (`pyproject.toml` with `deepagents>=0.5.3,<0.6`, `src/jarvis/` layer structure, `tests/` with 30–40 smoke tests)
- Supervisor skeleton runnable via `jarvis chat` (DeepAgents built-ins only, no custom tools, no subagents)
- `SessionManager` + Memory Store wired (in-memory backend; cross-session recall validated)
- Ruff + mypy clean; coverage baseline recorded
- `docs/architecture/ARCHITECTURE.md` + ADR-J-001..N landed
- Day-1 conversation criterion met

**Gaps Phase 2 closes:**

| Gap | Impact | Source |
|-----|--------|--------|
| Supervisor has no custom tools | Supervisor cannot read files, do arithmetic, search the web, or dispatch anywhere | ADR-J-P1 (Jarvis-as-GPA-with-dispatch-tools) is aspirational without tools |
| No capability catalogue reader | Supervisor cannot *discover* specialist capabilities — violates ADR-ARCH-015/016 fleet-wide inheritance | Fleet v3 §3 |
| No async subagents | Model routing is not a reasoning decision because there's nothing to route to | ADR-J-P2, fleet v3 D43 |
| Supervisor prompt teaches no routing preference | The "cheapest-that-fits, escalate on need" preference is dormant in Phase 1 | Conversation starter §2 + ADR-J-P2 |
| No end-to-end routing test | No proof that the reasoning-over-descriptions pattern actually works for Jarvis | Phase 1 only tests structural correctness |

---

## Feature Summary

| # | Feature | Depends On | Est. Complexity | Priority |
|---|---------|-----------|-----------------|----------|
| FEAT-JARVIS-002 | Core Tools & Capability-Driven Dispatch Tools | FEAT-JARVIS-001 | Medium | **High** (foundation for 004, 005, 007) |
| FEAT-JARVIS-003 | Async Subagents for Model Routing | FEAT-JARVIS-001 | High (preview feature, 4 model providers) | **High** (thesis-defining feature) |

**Dependency graph:**

```
FEAT-JARVIS-001 (Phase 1 — merged)
         │
         ├──→ FEAT-JARVIS-002 (tools)
         │         │
         │         └──→ FEAT-JARVIS-004, -005 (NATS integration — Phase 3)
         │
         └──→ FEAT-JARVIS-003 (async subagents)
                   │
                   └──→ FEAT-JARVIS-007 (skills compose tools + subagents — Phase 4)
```

FEAT-JARVIS-002 and FEAT-JARVIS-003 are independent (both depend only on 001). **Sequential build within the phase: 002 first, then 003.** Tools before subagents matches the "dispatch is tool selection" framing — the reasoning model reads tool descriptions; subagents register as additional tools via `AsyncSubAgentMiddleware`. Also, FEAT-JARVIS-003's `long_research` subagent reuses FEAT-JARVIS-002's `search_web` tool, so building 002 first avoids a forward reference.

---

## FEAT-JARVIS-002: Core Tools & Capability-Driven Dispatch Tools

**Purpose:** Give the supervisor its non-subagent tool surface — general-purpose tools, capability catalogue reader, and (stubbed-transport) dispatch tools. First realisation of ADR-J-P1 (Jarvis-as-GPA-with-dispatch-tools).

### Change 1: General tools module (`src/jarvis/tools/general.py`)

**Files (NEW):**

- `src/jarvis/tools/general.py` — four `@tool`-decorated functions:
  - `read_file(path: str) -> str` — path-safe file read, same guards as DeepAgents built-in filesystem.
  - `search_web(query: str, max_results: int = 5) -> list[WebResult]` — thin wrapper around configured provider (Tavily default; ADR-pinned). Provider key via `JarvisConfig`.
  - `get_calendar_events(window: Literal["today", "tomorrow", "this_week"] = "today") -> list[CalendarEvent]` — **stub**: returns `[]` or canned list for tests. Signature stable for FEAT-JARVIS-007's `morning-briefing` skill.
  - `calculate(expression: str) -> str` — safe-evaluator wrapper (no `eval`).
- `src/jarvis/tools/types.py` — `WebResult`, `CalendarEvent` Pydantic models.

Every tool has a rich docstring — the docstring is the contract with the reasoning model.

### Change 2: Capability catalogue reader (`src/jarvis/tools/capabilities.py`)

**Files (NEW):**

- `src/jarvis/tools/capabilities.py`:
  - `CapabilityDescriptor` Pydantic model: `agent_id`, `role`, `description`, `capability_list`, `cost_signal`, `latency_signal`, `last_heartbeat_at`, `trust_tier`.
  - `list_available_capabilities() -> list[CapabilityDescriptor]` — reads from in-memory stub registry.
  - `capabilities_refresh() -> None` — no-op stub.
  - `capabilities_subscribe_updates() -> None` — no-op stub.
  - Stub registry loader reads `src/jarvis/config/stub_capabilities.yaml` at startup.
- `src/jarvis/config/stub_capabilities.yaml` — four stubbed descriptors (architect, product-owner, ideation shapes) plus one for Forge (so `queue_build`'s reasoning model can find Forge in the catalogue).

The `CapabilityDescriptor` shape is deliberately identical to what FEAT-JARVIS-004 will produce from `NATSKVManifestRegistry` reads. The stub-to-real swap is then a transport change, not a schema change.

### Change 3: Dispatch tools (`src/jarvis/tools/dispatch.py`)

**Files (NEW):**

- `src/jarvis/tools/dispatch.py`:
  - `call_specialist(agent_id: str, instruction: str, context: dict = {}) -> SpecialistResult` — builds `CommandPayload` from `nats-core`; **Phase 2: stubbed transport** (logs as if published, returns test-configurable `SpecialistResult`).
  - `queue_build(feature_id: str, feature_spec_ref: str, repo: str, triggered_by: str = "jarvis", correlation_id: str | None = None, parent_request_id: str | None = None) -> QueueBuildAck` — builds `BuildQueuedPayload` per Forge ADR-SP-014 Pattern A; **Phase 2: stubbed transport** (log-only).

Docstrings carry full dispatch semantics. The reasoning model's behaviour in Phase 2 (stubbed) should match Phase 3 (real NATS) because *the contract is the docstring, not the transport*.

**Important:** Import `nats-core`'s `CommandPayload`, `ResultPayload`, `BuildQueuedPayload` as real Pydantic models. Stubbed transport ≠ stubbed schema. This keeps the FEAT-JARVIS-004/005 seam honest.

### Change 4: Supervisor factory update (`src/jarvis/agents/supervisor.py`)

**File:** `src/jarvis/agents/supervisor.py` (UPDATED — Phase 1 created it)

Phase 2 changes:

- Imports the 9 new tool functions (4 general + 3 capability + 2 dispatch).
- Passes them as `tools=[...]` to `create_deep_agent(...)` (or `create_agent(...)` per ADR-J-002).
- No signature change to `build_supervisor(config)`.

### Change 5: Supervisor system prompt update (`src/jarvis/prompts/supervisor_prompt.py`)

**File:** `src/jarvis/prompts/supervisor_prompt.py` (UPDATED — Phase 1 created it)

Add a "tool usage" section. The dormant "cheapest-that-fits, escalate on need" preference from Phase 1 now has tools to apply to:

- Prefer `calculate` over mental arithmetic.
- Use `list_available_capabilities` before `call_specialist` if capabilities have not already been retrieved this session.
- `call_specialist` for specialist agents; `queue_build` for Forge build intent; keep them separate.

Phase 1's attended-conversation posture preserved verbatim. Subagent routing section deferred to FEAT-JARVIS-003.

### Change 6: Config extensions (`src/jarvis/config/settings.py`)

**File:** `src/jarvis/config/settings.py` (UPDATED)

New fields:

- `web_search_provider: Literal["tavily", "none"] = "tavily"`
- `tavily_api_key: SecretStr | None = None` (or the ADR-pinned provider's equivalent)
- `stub_capabilities_path: Path = Path("src/jarvis/config/stub_capabilities.yaml")`

### Change 7: Tests

**Files (NEW):**

- `tests/test_tools_general.py` — per-tool happy path + one failure case each (path traversal rejected for `read_file`; missing API key error for `search_web`; empty/invalid window for `get_calendar_events`; invalid expression for `calculate`).
- `tests/test_tools_capabilities.py` — stub registry loads, `list_available_capabilities` returns expected descriptors, refresh + subscribe are no-ops.
- `tests/test_tools_dispatch.py` — `call_specialist` builds correct `CommandPayload` shape, timeout returns structured error, `queue_build` builds correct `BuildQueuedPayload` shape with all Pattern A required fields.
- `tests/test_supervisor_with_tools.py` (UPDATED or NEW) — extends Phase 1's `test_supervisor.py` to assert the 9 new tools are on the compiled graph; no LLM calls.

### Invariants

- Phase 1 test modules unchanged.
- Phase 1 supervisor prompt text unchanged (extended, not rewritten).
- `nats-py` is NOT added as a dependency. Only `nats-core` Pydantic models are imported.
- No subagents wired yet — that's FEAT-JARVIS-003.
- `call_specialist` and `queue_build` log their stubbed publishes distinctly so FEAT-JARVIS-004/005 can grep for the swap points.

---

## FEAT-JARVIS-003: Async Subagents for Model Routing

**Purpose:** Four `AsyncSubAgent` instances — model routing as a reasoning decision per fleet v3 D43. First use of DeepAgents 0.5.3 preview feature `AsyncSubAgentMiddleware`.

### Change 1: Subagent graph definitions (`src/jarvis/agents/subagents/`)

**Files (NEW):**

- `src/jarvis/agents/subagents/__init__.py`
- `src/jarvis/agents/subagents/deep_reasoner.py` — `create_deep_agent(model="google_genai:gemini-3.1-pro", system_prompt=DEEP_REASONER_PROMPT, tools=[])`. Leaf subagent; no tools; no further dispatch.
- `src/jarvis/agents/subagents/adversarial_critic.py` — same shape, `anthropic:claude-opus-4-7`, Coach-style adversarial prompt.
- `src/jarvis/agents/subagents/long_research.py` — same shape, `openai:gpt-5.4`, reuses `search_web` from FEAT-JARVIS-002 as its one tool.
- `src/jarvis/agents/subagents/quick_local.py` — `vllm:qwen3-coder-next` via `config.vllm_endpoint_url`, fallback-aware (see Change 5).
- `src/jarvis/agents/subagents/prompts.py` — the four subagent system prompts.

Each graph has a unique `graph_id`. Compilation timing (module-import vs lazy-at-first-use) pinned by `/system-design` ADR.

### Change 2: Subagent registry (`src/jarvis/agents/subagent_registry.py`)

**Files (NEW):**

- `src/jarvis/agents/subagent_registry.py` — `build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]`.

The four `AsyncSubAgent` instances with full descriptions (cost + latency signals). Descriptions are the contract — changes require commit-message justification.

### Change 3: Supervisor wiring (`src/jarvis/agents/supervisor.py`)

**File:** `src/jarvis/agents/supervisor.py` (UPDATED)

Pass `async_subagents=build_async_subagents(config)` through to the DeepAgents 0.5.3 supervisor factory. `AsyncSubAgentMiddleware` wires `start_async_task`, `check_async_task`, `wait_for_async_tasks`, `cancel_async_task`, `list_async_tasks` as tools.

### Change 4: Supervisor prompt — subagent routing section (`src/jarvis/prompts/supervisor_prompt.py`)

**File:** `src/jarvis/prompts/supervisor_prompt.py` (UPDATED)

Append subagent routing section:

- Default to `quick_local` for low-stakes work.
- Escalate to `deep_reasoner` for long-form reasoning.
- Invoke `adversarial_critic` for quality evaluation / flaw detection.
- Use `long_research` for open-ended research with no latency budget.
- Always check cost + latency signals in subagent descriptions before dispatching.
- Use `start_async_task` for fire-and-forget / parallel work; `task` (sync) for blocking-necessary delegation.

Additive — Phase 1 + FEAT-JARVIS-002 prompt content preserved.

### Change 5: `quick_local` fallback hook (`src/jarvis/agents/subagents/quick_local.py`)

Per JA6 from the architecture conversation-starter: handle GB10 vLLM pressure when AutoBuild is running.

- `quick_local.py` reads a `system.health.vllm` signal (**stubbed in Phase 2** — returns `"healthy"` by default; test-overridable).
- When signal is `"degraded"`, fall back to ADR-pinned cloud cheap-tier (`gemini-flash-latest` or equivalent).
- Fallback invocations are logged distinctly so FEAT-JARVIS-004's `jarvis_routing_history` writes can capture the event once trace-rich writes go live.
- Phase 2 ships the hook + test with stubbed signal. Real health-signal producer is v1.5.

### Change 6: ASGI transport configuration

**Files (NEW):**

- `langgraph.json` at repo root (or `/system-design`-pinned location) — declares 5 graphs (supervisor + 4 subagents), ASGI transport for all.
- `src/jarvis/infrastructure/asgi.py` if transport config needs code (may be unnecessary if `langgraph.json` suffices).
- `JarvisConfig` gains `vllm_endpoint_url: str = "http://localhost:8000/v1"`.

Matches Forge ADR-ARCH-031 default: single-process, single-container, multiple graphs.

### Change 7: Tests

**Files (NEW):**

- `tests/test_subagent_registry.py` — `build_async_subagents(test_config)` returns 4 instances, names unique, descriptions present and non-empty, graph IDs unique.
- `tests/test_subagents_deep_reasoner.py`, `test_subagents_adversarial_critic.py`, `test_subagents_long_research.py`, `test_subagents_quick_local.py` — one structural test per subagent: graph compiles, expected model string in config, expected tools (empty for most; `search_web` for `long_research`). No LLM calls — `FakeListChatModel` everywhere.
- `tests/test_routing_e2e.py` — **the acceptance test for Phase 2**: seven canned prompts with a mocked LLM returning deterministic tool-call sequences:
  1. "What's 15% of 847?" → `calculate`
  2. "Summarise /tmp/test.md" → `read_file`
  3. "Find recent papers on Meta-Harness" → `start_async_task(name="long_research", ...)`
  4. "Review this architecture doc for flaws" → `start_async_task(name="adversarial_critic", ...)`
  5. "What's my next meeting?" → `start_async_task(name="quick_local", ...)` → `get_calendar_events`
  6. "Build FEAT-JARVIS-EXAMPLE-001" → `queue_build`
  7. "Ask the architect agent for a C4 diagram of Jarvis" → `list_available_capabilities` then `call_specialist(agent_id="architect", ...)`
- `tests/test_quick_local_fallback.py` — override health signal to `"degraded"`; assert fallback-model is invoked; log assertion on fallback event.

### Invariants

- FEAT-JARVIS-002's tool modules unchanged.
- `create_deep_agent()` / `create_agent()` factory choice from ADR-J-002 unchanged.
- Subagent descriptions are the contract — any modification requires an explicit commit-message note.
- ASGI is the transport. No HTTP transport. No separate deployment.

---

## GuardKit Command Sequence

### Step 1: /system-design FEAT-JARVIS-002

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis

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
```

Expected output: `docs/design/FEAT-JARVIS-002/design.md` — tool module boundaries, `CapabilityDescriptor` Pydantic shape, `SpecialistResult` / `QueueBuildAck` shapes, stub registry YAML schema, web-search provider ADR (if pinned here rather than at Phase 1's `/system-arch`), `call_specialist` timeout + retry semantics.

### Step 2: /system-design FEAT-JARVIS-003

```bash
/system-design FEAT-JARVIS-003 \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/design/FEAT-JARVIS-002/design.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/prompts/supervisor_prompt.py \
  --context src/jarvis/config/settings.py \
  --context .guardkit/context-manifest.yaml
```

Expected output: `docs/design/FEAT-JARVIS-003/design.md` — four subagent module boundaries, `AsyncSubAgent` instantiation pattern, ASGI transport declaration shape, `quick_local` fallback policy (JA6 answer), `langgraph.json` location ADR.

### Step 3: /feature-spec FEAT-JARVIS-002

```bash
/feature-spec "Core Tools & Capability-Driven Dispatch Tools: general tools (read_file, search_web, get_calendar_events stub, calculate), capability catalogue reader over stub registry, dispatch tools (call_specialist, queue_build) with stubbed transports matching nats-core payloads" \
  --context docs/design/FEAT-JARVIS-002/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../nats-core/src/nats_core/manifest.py \
  --context ../nats-core/src/nats_core/payloads/ \
  --context src/jarvis/agents/supervisor.py \
  --context .guardkit/context-manifest.yaml
```

### Step 4: /feature-spec FEAT-JARVIS-003

```bash
/feature-spec "Async Subagents for Model Routing: four AsyncSubAgent instances (deep_reasoner, adversarial_critic, long_research, quick_local) via AsyncSubAgentMiddleware with ASGI transport; cost+latency descriptions; quick_local fallback hook under stubbed GB10 health signal" \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/tools/general.py \
  --context .guardkit/context-manifest.yaml
```

### Step 5: /feature-plan FEAT-JARVIS-002

After the 2026-04-24 `/feature-spec` run the concrete feature directory is
`features/feat-jarvis-002-core-tools-and-dispatch/` — use the explicit paths
below rather than the original wildcard form so the context resolver pulls
only this feature's artefacts:

```bash
/feature-plan "Core Tools & Capability-Driven Dispatch Tools" \
  --context features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_summary.md \
  --context features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch.feature \
  --context features/feat-jarvis-002-core-tools-and-dispatch/feat-jarvis-002-core-tools-and-dispatch_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-002/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context .guardkit/context-manifest.yaml
```

Resolve the 1 low-confidence assumption (ASSUM-006 — snapshot-isolation semantics
for Phase 3) and any medium-confidence assumptions flagged at Coach review
before Step 7.

### Step 6: /feature-plan FEAT-JARVIS-003

```bash
/feature-plan "Async Subagents for Model Routing" \
  --context features/feat-jarvis-003-*/feat-jarvis-003-*_summary.md \
  --context features/feat-jarvis-003-*/feat-jarvis-003-*.feature \
  --context features/feat-jarvis-003-*/feat-jarvis-003-*_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md \
  --context .guardkit/context-manifest.yaml
```

Resolve any low-confidence assumptions before Step 8.

### Step 7: AutoBuild FEAT-JARVIS-002

AutoBuild feature YAML: [`.guardkit/features/FEAT-J002.yaml`](../../../.guardkit/features/FEAT-J002.yaml) — 23 subtasks, complexity 6, produced 2026-04-24.

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
/feature-build FEAT-J002
```

The `/feature-plan` run has already enumerated the wave structure and commit order inside the YAML + `tasks/backlog/feat-jarvis-002-core-tools-and-dispatch/IMPLEMENTATION-GUIDE.md`. Envelope-first concurrent fan-out (Option B, review score 12/12); DDR-009 swap-point discipline preserved — two primary grep anchors guard the FEAT-JARVIS-004/005 transport swap. Per-feature AutoBuild, not per-task. `/task-review` at feature gate.

### Step 8: AutoBuild FEAT-JARVIS-003

Precondition: `/feature-plan FEAT-JARVIS-003` must land its AutoBuild YAML first (anticipated path `.guardkit/features/FEAT-J003.yaml`).

```bash
/feature-build FEAT-J003
```

Suggested commit order (the `/feature-plan` run should refine, and the YAML's wave structure governs once written):

1. `subagents/prompts.py` (role prompts — critic / researcher / planner per DDR-011 closed-enum).
2. `subagents/jarvis_reasoner.py` — single `AsyncSubAgent` with module-import compilation per DDR-012.
3. `subagent_registry.py` + `test_subagent_registry.py`.
4. `LlamaSwapAdapter` with stubbed health per DDR-015.
5. `escalate_to_frontier` in `jarvis.tools.dispatch` per DDR-014 — three-layer belt+braces gating.
6. Supervisor factory + prompt updates.
7. ASGI transport (`langgraph.json` at repo root per DDR-013 + `infrastructure/asgi.py` if needed).
8. `test_routing_e2e.py` — the acceptance test.

### Step 9: /task-review FEAT-JARVIS-002 + /task-review FEAT-JARVIS-003

```bash
/task-review FEAT-JARVIS-002 \
  --context tasks/FEAT-JARVIS-002-*.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md

/task-review FEAT-JARVIS-003 \
  --context tasks/FEAT-JARVIS-003-*.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/phase2-build-plan.md
```

### Step 10: Regression check

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
uv sync
uv run pytest tests/ -v --tb=short --cov=src/jarvis
uv run ruff check src/jarvis/ tests/
uv run mypy src/jarvis/
uv run langgraph dev --no-browser  # validate langgraph.json
```

### Step 11: End-to-end routing validation

Manual validation of the thesis — *one reasoning model that knows which reasoning model to use*:

```bash
export JARVIS_SUPERVISOR_MODEL="<ADR-pinned default>"
export GOOGLE_API_KEY="..."       # for deep_reasoner + supervisor if Gemini
export ANTHROPIC_API_KEY="..."    # for adversarial_critic
export OPENAI_API_KEY="..."       # for long_research
# vLLM on GB10 must be serving Qwen3-Coder-Next at $JARVIS_VLLM_ENDPOINT_URL

jarvis chat
  > What's 15% of 847?                              # expect: calculate
  > Read /Users/.../some-file.md                    # expect: read_file
  > Quickly what's my next meeting?                 # expect: quick_local subagent
  > Review this for subtle flaws: <paste text>      # expect: adversarial_critic subagent
  > Research Meta-Harness deeply for 30min          # expect: long_research subagent
```

Record the session — evidence for the Phase 2 close.

---

## Files That Will Change

| File | Feature | Change Type |
|------|---------|------------|
| `pyproject.toml` | FEAT-JARVIS-002, -003 | **UPDATED** — `langchain-tavily` (or equivalent), `nats-core` (Pydantic imports only), provider SDKs for 4 subagent models |
| `src/jarvis/config/settings.py` | FEAT-JARVIS-002, -003 | **UPDATED** — `web_search_provider`, provider API keys, `vllm_endpoint_url`, `stub_capabilities_path` |
| `src/jarvis/config/stub_capabilities.yaml` | FEAT-JARVIS-002 | **NEW** — 4 stubbed capability descriptors |
| `src/jarvis/tools/general.py` | FEAT-JARVIS-002 | **NEW** — 4 general tools |
| `src/jarvis/tools/types.py` | FEAT-JARVIS-002 | **NEW** — `WebResult`, `CalendarEvent` |
| `src/jarvis/tools/capabilities.py` | FEAT-JARVIS-002 | **NEW** — `CapabilityDescriptor`, catalogue reader, refresh/subscribe stubs |
| `src/jarvis/tools/dispatch.py` | FEAT-JARVIS-002 | **NEW** — `call_specialist`, `queue_build` (stubbed transports, real `nats-core` payloads) |
| `src/jarvis/prompts/supervisor_prompt.py` | FEAT-JARVIS-002, -003 | **UPDATED** — tool-usage section (002), subagent-routing section (003) |
| `src/jarvis/agents/supervisor.py` | FEAT-JARVIS-002, -003 | **UPDATED** — tool list + `async_subagents` wiring |
| `src/jarvis/agents/subagent_registry.py` | FEAT-JARVIS-003 | **NEW** — `build_async_subagents(config)` |
| `src/jarvis/agents/subagents/{__init__,prompts}.py` | FEAT-JARVIS-003 | **NEW** |
| `src/jarvis/agents/subagents/{deep_reasoner,adversarial_critic,long_research,quick_local}.py` | FEAT-JARVIS-003 | **NEW** — 4 subagent graphs |
| `src/jarvis/infrastructure/asgi.py` | FEAT-JARVIS-003 | **NEW** (if needed beyond `langgraph.json`) |
| `langgraph.json` | FEAT-JARVIS-003 | **NEW** — 5 graphs, ASGI transport |
| `tests/test_tools_general.py` | FEAT-JARVIS-002 | **NEW** |
| `tests/test_tools_capabilities.py` | FEAT-JARVIS-002 | **NEW** |
| `tests/test_tools_dispatch.py` | FEAT-JARVIS-002 | **NEW** |
| `tests/test_supervisor_with_tools.py` | FEAT-JARVIS-002 | **NEW** or **UPDATED** |
| `tests/test_subagent_registry.py` | FEAT-JARVIS-003 | **NEW** |
| `tests/test_subagents_{deep_reasoner,adversarial_critic,long_research,quick_local}.py` | FEAT-JARVIS-003 | **NEW** |
| `tests/test_routing_e2e.py` | FEAT-JARVIS-003 | **NEW** — 7-prompt acceptance test |
| `tests/test_quick_local_fallback.py` | FEAT-JARVIS-003 | **NEW** |
| `docs/design/FEAT-JARVIS-002/design.md` | FEAT-JARVIS-002 | **NEW** — produced by `/system-design` |
| `docs/design/FEAT-JARVIS-003/design.md` | FEAT-JARVIS-003 | **NEW** — produced by `/system-design` |
| `features/feat-jarvis-002-*/...` | FEAT-JARVIS-002 | **NEW** |
| `features/feat-jarvis-003-*/...` | FEAT-JARVIS-003 | **NEW** |
| `tasks/FEAT-JARVIS-002-*.md` | FEAT-JARVIS-002 | **NEW** |
| `tasks/FEAT-JARVIS-003-*.md` | FEAT-JARVIS-003 | **NEW** |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/`.

---

## Do-Not-Change

1. **Fleet v3 D40–D46, ADR-J-P1..P10, ADR-FLEET-001.** Phase 2 is first major consumer of P1, P2, P7; honour, don't re-litigate.
2. **Phase 1 outputs.** `pyproject.toml` dependency set, `src/jarvis/{shared,config,prompts,infrastructure,sessions,cli}/` modules, Phase 1 test modules. Phase 2 extends; does not rewrite.
3. **Phase 1 supervisor prompt's attended-conversation posture.** Preserve verbatim; append new sections.
4. **`create_deep_agent()` / `create_agent()` factory choice** pinned in ADR-J-002.
5. **Subagent descriptions are the contract.** Post-landing changes require explicit commit-message justification. Learning flywheel (v1.5) will measure against them.
6. **No NATS transport in Phase 2.** `call_specialist` + `queue_build` log-stub only. `nats-py` is NOT a Phase 2 dependency. `nats-core` Pydantic models ARE imported (pure data, no network).
7. **Scope-preserving rules from conversation starter §2.** No new agent repos, no fleet-decision changes mid-build, trace-richness schema shape honoured from day one.
8. **Singular topic convention (ADR-SP-016).** Any reference to NATS topics (in stub logs, docstrings) uses singular form.
9. **ASGI transport.** Phase 2 commits to ASGI per ADR-J-P7. HTTP transport is a v1.5+ consideration.
10. **`get_calendar_events` is a stub.** Real calendar integration is v1.5. Stub signature must not change — FEAT-JARVIS-007's `morning-briefing` skill depends on it.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| `AsyncSubAgentMiddleware` preview-feature instability | Fallback documented in ADR-J-001: sync `task()` dispatch as degraded mode. If instability blocks FEAT-JARVIS-003, land 002 alone and defer 003 to a Phase 2.5. |
| Web-search provider choice affects architecture | `/system-design FEAT-JARVIS-002` pins provider via ADR. Tool abstracted behind `search_web` — swap providers without tool-surface change. |
| Subagent descriptions subtly wrong (wrong cost, wrong latency, ambiguous "when to use") | Review descriptions against `specialist-agent/docs/reviews/deepagents-sdk-2026-04.md` and Forge's ADR-ARCH-031 examples. Routing test (`test_routing_e2e.py`) catches description-driven regressions. |
| 4 subagent models = 4 provider API keys + 4 quota budgets | `config.py` validates keys only for *configured* subagents. `quick_local` keeps load off cloud providers; cost budget enforced via supervisor prompt preference. |
| Stub-registry drift from real `NATSKVManifestRegistry` shape | `CapabilityDescriptor` Pydantic model is the source of truth. FEAT-JARVIS-004 verifies stub-to-real swap is transport-only. Integration test in FEAT-JARVIS-004 asserts schema compatibility. |
| `langgraph.json` validation fails with multi-graph config | `langgraph dev --no-browser` smoke test in Step 10. DeepAgents 0.5.3 docs confirm multi-graph ASGI — if broken, raise to Anthropic/LangChain support. |
| `quick_local` fallback test brittle | Use a clear health-signal injection interface (`fake_health_signal` fixture); test the *branch*, not the fallback model's behaviour. |
| AutoBuild mega-commits | `/feature-plan` enumerates commit boundaries; split at `/task-review` if violated. |
| `call_specialist` / `queue_build` stub behaviour drifts from real NATS in FEAT-JARVIS-004/005 | Stubbed transports build **real** `CommandPayload`/`BuildQueuedPayload` via `nats-core`; only the "publish" step is logged. Swap is transport-level only. |

---

## Expected Timeline

Building on Phase 1's timeline (Phase 1: 21–24 April 2026):

| Day | Activity | Output | Status |
|-----|----------|--------|--------|
| 1 (23 Apr) | Step 1 + Step 2 — `/system-design FEAT-JARVIS-002` + `/system-design FEAT-JARVIS-003` | `docs/design/FEAT-JARVIS-002/design.md`, `docs/design/FEAT-JARVIS-003/design.md` | ✅ |
| 2 (24 Apr) | Step 3 + Step 4 — `/feature-spec` for both features | Gherkin scenarios (42 + 44), assumptions, summaries | ✅ |
| 2 (24 Apr) | Step 5 — `/feature-plan FEAT-JARVIS-002` | AutoBuild YAML `FEAT-J002.yaml` + 23 subtasks | ✅ |
| 3 (25 Apr) | Step 6 — `/feature-plan FEAT-JARVIS-003` | AutoBuild YAML `FEAT-J003.yaml` + task breakdown | 🔲 |
| 3 (25 Apr) | Step 7 — `/feature-build FEAT-J002` (tools first — low-risk) | Tools + capability reader + dispatch stubs shipping; FEAT-JARVIS-002 tests green | 🔲 |
| 4 (26 Apr) | Step 8 — `/feature-build FEAT-J003` (single subagent + escalate_to_frontier — preview feature) | `jarvis-reasoner` subagent + ASGI + routing e2e test shipping | 🔲 |
| 5 (27 Apr) | Step 9 — `/task-review` for both; fix any gaps. Step 10 — regression check. Step 11 — end-to-end routing validation with real models. | Phase 2 closed; evidence recorded | 🔲 |

**Target: Phase 2 complete within the 23–27 Apr window.** Design + spec + FEAT-002 plan landed ahead of the original 25–29 Apr plan. FEAT-JARVIS-003 remains the hardest feature in v1 (preview-feature risk on `AsyncSubAgentMiddleware`, first ASGI multi-graph, three-layer `escalate_to_frontier` gating); budget still accommodates a 1-day overrun if needed.

---

## After Phase 2: What Comes Next

| Priority | Phase | Content |
|----------|-------|---------|
| **Next** | Phase 3 | FEAT-JARVIS-004 (NATS Fleet Registration & Specialist Dispatch) + FEAT-JARVIS-005 (Build Queue Dispatch to Forge). 004 replaces `call_specialist`'s stub transport with real `agents.command.{agent_id}` / `agents.result.{agent_id}` round-trips; registers Jarvis on `fleet.register`; populates the capability catalogue from real `NATSKVManifestRegistry` reads. 005 replaces `queue_build`'s stub with real `pipeline.build-queued.{feature_id}` JetStream publishes. First live `jarvis_routing_history` writes to Graphiti per ADR-FLEET-001. |
| **Then** | Phase 4 | FEAT-JARVIS-006 (Telegram adapter, Telegram-only per Q10.3) + FEAT-JARVIS-007 (skills + Memory Store activation with `morning-briefing`, `talk-prep`, `project-status`). |
| **v1.5** | Phase 5 | FEAT-JARVIS-008 (Learning Flywheel). Deferred per 20 April Q10.2; returns when real routing history exists. |
| **v1.5** | — | FEAT-JARVIS-009 (CLI + Dashboard adapters), FEAT-JARVIS-010 (Pattern C ambient for `talk-prep`), FEAT-JARVIS-011 (`jarvis purge-traces`). |

---

*Phase 2 build plan: 20 April 2026*
*Predecessor: Phase 1 (FEAT-JARVIS-001 — scaffolding, supervisor skeleton, session lifecycle).*
*Input to: `/system-design FEAT-JARVIS-002`, `/system-design FEAT-JARVIS-003`.*
*"Dispatch is tool selection."*
