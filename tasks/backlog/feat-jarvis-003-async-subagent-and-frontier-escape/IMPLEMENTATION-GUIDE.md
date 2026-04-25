# Implementation Guide — FEAT-JARVIS-003

**Feature:** Async Subagent for Model Routing + Attended Frontier Escape
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)
**Design:** [docs/design/FEAT-JARVIS-003/design.md](../../../docs/design/FEAT-JARVIS-003/design.md)
**Gherkin spec:** [features/feat-jarvis-003-.../feat-jarvis-003-....feature](../../../features/feat-jarvis-003-async-subagent-and-frontier-escape/feat-jarvis-003-async-subagent-and-frontier-escape.feature) (44 scenarios)

**Approach:** Option B — Envelope-first, concurrent fan-out (review score 12/12).
**Wave count:** 5 | **Tasks:** 24 | **Aggregate complexity:** 7/10
**Execution model:** AutoBuild parallel worktrees (FEAT-J002 precedent)
**Testing posture:** TDD for complexity ≥ 5; standard Coach gates for < 5

---

## Wave summary

| Wave | Tasks | Focus | Parallel-safe |
|---|---|---|---|
| 1 | 6 | Envelope — config, enums, models, role prompts, pyproject | ✅ all independent |
| 2 | 5 | Components — LlamaSwapAdapter, subagent graph, registry, escalate L1, escalate L2 | ✅ within wave (deps chained on Wave 1) |
| 3 | 4 | Wiring — assemble_tool_list (Layer 3), build_supervisor, supervisor prompt, lifecycle | partial (015 gates on 007+009+012+013) |
| 4 | 4 | Deployment + unit tests — langgraph.json, subagent tests, escalate tests, llamaswap+voice-ack tests | ✅ all independent within wave |
| 5 | 5 | Integration + regression + acceptance + smoke | 020/021/022/024 parallel; 023 gates on 021+022 |

---

## Data flow: read/write paths

The mandatory Data Flow diagram (per /feature-plan spec) — every write path and every read path for this feature. Healthy = green, disconnected = red with dotted edges.

```mermaid
flowchart LR
    subgraph Writes["Write Paths"]
        W1["JarvisConfig (TASK-001)"]
        W2["RoleName / FrontierTarget enums (TASK-002)"]
        W3["AsyncTaskInput / SwapStatus (TASK-003)"]
        W4["FrontierEscalationContext (TASK-004)"]
        W5["ROLE_PROMPTS registry (TASK-005)"]
        W6["jarvis_reasoner graph module (TASK-008)"]
        W7["subagent_registry → AsyncSubAgent list (TASK-009)"]
        W8["escalate_to_frontier tool (TASK-010+011)"]
        W9["LlamaSwapAdapter (TASK-007)"]
    end

    subgraph Storage["Storage / Module state"]
        S1[("settings.py fields")]
        S2[("subagents/types.py enums")]
        S3[("dispatch_types.py FrontierTarget + FrontierEscalationContext")]
        S4[("adapters/types.py SwapStatus")]
        S5[("subagents/prompts.py ROLE_PROMPTS")]
        S6[("compiled graph module-scope var")]
        S7[("AsyncSubAgent list[]")]
        S8[("@tool function registry entry")]
        S9[("Adapter instance in AppState")]
    end

    subgraph Reads["Read Paths"]
        R1["lifecycle.startup (TASK-015)"]
        R2["jarvis_reasoner first-node (TASK-008)"]
        R3["build_async_subagents (TASK-009)"]
        R4["assemble_tool_list attended (TASK-012)"]
        R5["assemble_tool_list ambient (TASK-012)"]
        R6["build_supervisor (TASK-013)"]
        R7["supervisor_prompt render (TASK-014)"]
        R8["supervisor swap-aware voice-ack (TASK-015)"]
        R9["langgraph.json graph binding (TASK-016)"]
        R10["test_routing_e2e (TASK-023)"]
    end

    W1 --> S1
    W2 --> S2
    W2 --> S3
    W3 --> S4
    W4 --> S3
    W5 --> S5
    W6 --> S6
    W7 --> S7
    W8 --> S8
    W9 --> S9

    S1 --> R1
    S1 --> R3
    S1 --> R6
    S2 --> R2
    S3 --> R4
    S3 --> R5
    S4 --> R1
    S4 --> R8
    S5 --> R2
    S6 --> R9
    S7 --> R3
    S7 --> R6
    S8 --> R4
    S9 --> R1
    S9 --> R8
    S7 --> R7

    R6 --> R10
```

_Caption: every write path has at least one read path. The supervisor integration surface (R6) is the single confluence point — it reads subagent list, tool lists, and config before compiling._

**Disconnection check:** ✅ No disconnected write paths. No read paths without callers. R10 (test_routing_e2e) is the acceptance surface — it reads the compiled supervisor state.

---

## Integration contract sequence (complexity ≥ 5 → mandatory)

The three-layer belt+braces gate on `escalate_to_frontier` is the most delicate integration surface. This sequence diagram shows who calls what, in what order, and where rejections happen.

```mermaid
sequenceDiagram
    participant Reasoning as Reasoning model
    participant ToolReg as assemble_tool_list (Layer 3)
    participant FrontierTool as escalate_to_frontier
    participant Session as SessionManager
    participant Middleware as AsyncSubAgentMiddleware
    participant Provider as Gemini / Anthropic SDK
    participant Log as structured logger

    Note over Reasoning,ToolReg: Layer 3 — Registration absence (ambient)
    Reasoning->>ToolReg: assemble_tool_list(include_frontier=False)
    ToolReg-->>Reasoning: [<FEAT-J002 tools>]  (no escalate_to_frontier)
    Note over Reasoning: Cannot call a tool it cannot see

    Note over Reasoning,FrontierTool: Layer 3 — Attended session
    Reasoning->>ToolReg: assemble_tool_list(include_frontier=True)
    ToolReg-->>Reasoning: [<FEAT-J002 tools>, escalate_to_frontier]
    Reasoning->>FrontierTool: escalate_to_frontier(instruction, target)

    Note over FrontierTool,Session: Layer 2 — Executor assertion (adapter)
    FrontierTool->>Session: current_session().adapter_id
    Session-->>FrontierTool: "cli" (attended) / "ambient" / etc.
    alt adapter_id not in attended set
        FrontierTool->>Log: log_frontier_escalation(outcome="attended_only")
        FrontierTool-->>Reasoning: "ERROR: attended_only — {adapter}"
        Note over Reasoning: No provider call. Instruction body NOT echoed.
    end

    Note over FrontierTool,Middleware: Layer 2 — Executor assertion (frame)
    FrontierTool->>Middleware: is_inside_async_subagent_frame()
    Middleware-->>FrontierTool: True / False
    alt inside async-subagent frame
        FrontierTool->>Log: log_frontier_escalation(outcome="attended_only")
        FrontierTool-->>Reasoning: "ERROR: attended_only — async-subagent frame"
        Note over Reasoning: Spoofed-ambient case — still rejected.
    end

    Note over FrontierTool,Provider: Layer 1 — Tool body (passed all checks)
    FrontierTool->>Provider: generate(instruction, model=<target>)
    alt missing API key
        FrontierTool->>Log: log_frontier_escalation(outcome="config_missing")
        FrontierTool-->>Reasoning: "ERROR: config_missing — {KEY} not set"
    else provider unreachable
        FrontierTool->>Log: log_frontier_escalation(outcome="provider_unavailable")
        FrontierTool-->>Reasoning: "DEGRADED: provider_unavailable — ..."
    else empty body
        FrontierTool->>Log: log_frontier_escalation(outcome="degraded_empty")
        FrontierTool-->>Reasoning: "DEGRADED: provider_unavailable — empty response"
    else happy path
        Provider-->>FrontierTool: response text
        FrontierTool->>Log: log_frontier_escalation(outcome="success")
        FrontierTool-->>Reasoning: response text
    end
```

_Caption: Layer 3 (registration absence) is the strongest guarantee — the reasoning model cannot invoke a tool not in its registered set. Layer 2 (adapter_id + frame check) is the belt; Layer 1 (tool body branches) is the braces. Instruction body is never echoed; only adapter/frame labels appear in error strings._

---

## Task dependency graph (≥ 3 tasks → mandatory)

Parallel-safe tasks within a wave are coloured green. Wall-clock shortens roughly linearly with AutoBuild parallel worktree count.

```mermaid
graph TD
    %% Wave 1 - all independent
    T001[TASK-001 Config fields]
    T002[TASK-002 RoleName + FrontierTarget]
    T003[TASK-003 AsyncTaskInput + SwapStatus]
    T004[TASK-004 FrontierEscalationContext]
    T005[TASK-005 ROLE_PROMPTS]
    T006[TASK-006 pyproject deps]

    %% Wave 2
    T007[TASK-007 LlamaSwapAdapter]
    T008[TASK-008 jarvis_reasoner graph]
    T009[TASK-009 subagent_registry]
    T010[TASK-010 escalate Layer 1]
    T011[TASK-011 escalate Layer 2]

    %% Wave 3
    T012[TASK-012 assemble_tool_list L3]
    T013[TASK-013 build_supervisor signature]
    T014[TASK-014 supervisor_prompt sections]
    T015[TASK-015 lifecycle startup]

    %% Wave 4
    T016[TASK-016 langgraph.json]
    T017[TASK-017 unit: subagent layer]
    T018[TASK-018 unit: escalate]
    T019[TASK-019 unit: llamaswap + voice-ack]

    %% Wave 5
    T020[TASK-020 regression: roster strings]
    T021[TASK-021 integration: supervisor+subagents]
    T022[TASK-022 integration: role propagation]
    T023[TASK-023 acceptance: routing e2e]
    T024[TASK-024 langgraph.json smoke]

    %% Wave 1 → Wave 2
    T001 --> T007
    T003 --> T007
    T001 --> T008
    T002 --> T008
    T005 --> T008
    T008 --> T009
    T001 --> T010
    T002 --> T010
    T004 --> T010
    T006 --> T010
    T010 --> T011

    %% Wave 2 → Wave 3
    T011 --> T012
    T009 --> T013
    T012 --> T013
    T009 --> T014
    T011 --> T014
    T007 --> T015
    T009 --> T015
    T012 --> T015
    T013 --> T015

    %% Wave 3 → Wave 4
    T008 --> T016
    T015 --> T016
    T005 --> T017
    T008 --> T017
    T009 --> T017
    T010 --> T018
    T011 --> T018
    T012 --> T018
    T007 --> T019
    T015 --> T019

    %% Wave 4 → Wave 5
    T005 --> T020
    T008 --> T020
    T009 --> T020
    T014 --> T020
    T013 --> T021
    T015 --> T021
    T008 --> T022
    T009 --> T022
    T021 --> T023
    T022 --> T023
    T016 --> T024

    style T001 fill:#cfc,stroke:#090
    style T002 fill:#cfc,stroke:#090
    style T003 fill:#cfc,stroke:#090
    style T004 fill:#cfc,stroke:#090
    style T005 fill:#cfc,stroke:#090
    style T006 fill:#cfc,stroke:#090

    style T007 fill:#cfe,stroke:#079
    style T008 fill:#cfe,stroke:#079
    style T009 fill:#cfe,stroke:#079
    style T010 fill:#cfe,stroke:#079
    style T011 fill:#cfe,stroke:#079

    style T016 fill:#ffc,stroke:#cc0
    style T017 fill:#ffc,stroke:#cc0
    style T018 fill:#ffc,stroke:#cc0
    style T019 fill:#ffc,stroke:#cc0

    style T020 fill:#fce,stroke:#c09
    style T021 fill:#fce,stroke:#c09
    style T022 fill:#fce,stroke:#c09
    style T023 fill:#fce,stroke:#c09
    style T024 fill:#fce,stroke:#c09
```

_Caption: Wave 1 (green) is 6-way parallel; Wave 2 (blue-green) is 3-way parallel after Wave 1 clears; Wave 3 (white) is serialised on lifecycle (015); Wave 4 (yellow) is 4-way parallel; Wave 5 (pink) is 4-way parallel except 023 gating on 021+022._

---

## §4: Integration Contracts

Cross-task data dependencies where one task's output is consumed by another task's input. Every consumer task listed here carries a `consumer_context` note in its frontmatter (where it would be load-bearing for Coach validation) OR names the producer in its acceptance criteria.

### Contract 1: RoleName closed enum
- **Producer task:** TASK-J003-002 (Define RoleName + FrontierTarget closed enums)
- **Consumer task(s):** TASK-J003-005 (ROLE_PROMPTS keys), TASK-J003-008 (graph first-node role resolution), TASK-J003-009 (registry description mentions role names), TASK-J003-017 (exhaustiveness test), TASK-J003-020 (regression), TASK-J003-022 (role propagation)
- **Artifact type:** Python enum class in `src/jarvis/agents/subagents/types.py`
- **Format constraint:** closed str-Enum with exactly three members — `CRITIC="critic"`, `RESEARCHER="researcher"`, `PLANNER="planner"`. `RoleName("")` raises `ValueError` (consumed by TASK-008 to route to `unknown_role` branch).
- **Validation method:** TASK-J003-017's `tests/test_subagent_prompts.py` asserts `set(RoleName) == set(ROLE_PROMPTS.keys())` — exhaustiveness; TASK-J003-008 graph-init test exercises each member.

### Contract 2: FrontierTarget closed enum
- **Producer task:** TASK-J003-002
- **Consumer task(s):** TASK-J003-010 (default arg + dispatch), TASK-J003-018 (tests)
- **Artifact type:** Python enum class in `src/jarvis/tools/dispatch_types.py`
- **Format constraint:** closed str-Enum with exactly two members — `GEMINI_3_1_PRO`, `OPUS_4_7`. Must be str-valued so `@tool(parse_docstring=True)` argument coercion accepts literal strings.
- **Validation method:** TASK-J003-018 asserts out-of-enum target rejected at tool-boundary before provider contacted (ASSUM-005).

### Contract 3: SwapStatus model
- **Producer task:** TASK-J003-003
- **Consumer task(s):** TASK-J003-007 (adapter returns it), TASK-J003-015 (lifecycle voice-ack logic), TASK-J003-019 (tests assert shape + boundary)
- **Artifact type:** Pydantic frozen model in `src/jarvis/adapters/types.py`
- **Format constraint:** `{loaded_model: str, eta_seconds: int >= 0, source: Literal["stub","live"] = "stub"}`. Negative `eta_seconds` raises `ValidationError` at construction. Phase 2 always emits `source="stub"`; FEAT-JARVIS-004 switches to `"live"` without schema change — **this is the load-bearing invariant for Context A concern #2**.
- **Validation method:** TASK-J003-019's boundary table (ETA 0 / 30 / 31 / 240 / -1) tests both the model's `ge=0` constraint and the supervisor's voice-ack threshold.

### Contract 4: FrontierEscalationContext log-event shape
- **Producer task:** TASK-J003-004
- **Consumer task(s):** TASK-J003-010 (log emission), TASK-J003-018 (log shape assertion)
- **Artifact type:** Pydantic frozen model + `log_frontier_escalation` helper in `src/jarvis/tools/dispatch_types.py`
- **Format constraint:** exact field set `{target, session_id, correlation_id, adapter, instruction_length, outcome}`. **No `instruction` or `instruction_body` field** — ADR-ARCH-029 redaction posture (ASSUM-006). `outcome` is literal union of `success / config_missing / attended_only / provider_unavailable / degraded_empty`.
- **Validation method:** TASK-J003-018 asserts field set verbatim AND asserts instruction body absent from logged fields (regex scan).

### Contract 5: ROLE_PROMPTS mapping
- **Producer task:** TASK-J003-005
- **Consumer task(s):** TASK-J003-008 (first-node resolution), TASK-J003-017 (exhaustiveness + posture keyword assertions)
- **Artifact type:** `Mapping[RoleName, str]` in `src/jarvis/agents/subagents/prompts.py`
- **Format constraint:** exactly three entries; keys == `set(RoleName)`; each value non-empty ≥ 40 chars; each carries its posture keyword (`adversarial` / `open-ended research` / `multi-step planning`); no `{placeholders}` (final prompts, not templates).
- **Validation method:** TASK-J003-017's `test_subagent_prompts.py` exhaustiveness check.

### Contract 6: jarvis-reasoner AsyncSubAgent description — the routing contract
- **Producer task:** TASK-J003-009
- **Consumer task(s):** TASK-J003-013 (build_supervisor wires it), TASK-J003-015 (lifecycle), TASK-J003-020 (regression — substring invariants), TASK-J003-021 (integration test catalogue assertion)
- **Artifact type:** `AsyncSubAgent["description"]` string
- **Format constraint:** MUST contain all of `gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`. MUST NOT contain any of `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`, or cloud-tier promise language. This is the routing-behaviour contract per DDR-010 — **the reasoning model reads this text and makes dispatch decisions based on it**.
- **Validation method:** TASK-J003-020 grep regression + TASK-J003-021 catalogue assertion.

### Contract 7: ambient_tool_factory output — Layer 3 invariant
- **Producer task:** TASK-J003-012
- **Consumer task(s):** TASK-J003-013 (factory threaded through build_supervisor), TASK-J003-015 (lifecycle calls it with `include_frontier=False`), TASK-J003-018 (registration-absence test), TASK-J003-021 (attended vs ambient catalogue assertion)
- **Artifact type:** `Callable[[], list[BaseTool]]` returning a fresh list each call
- **Format constraint:** when called with the lifecycle's fixed `include_frontier=False`, the returned list **excludes** `escalate_to_frontier` AND **includes** every FEAT-J002 tool. The list is a new object each call (no mutable aliasing); the reasoning model cannot mutate a shared list to add `escalate_to_frontier` back at runtime (ADR-ARCH-023).
- **Validation method:** TASK-J003-018 asserts identity check + mutation-isolation; TASK-J003-021 asserts tool-name set diff.

### Contract 8: JarvisConfig fields consumed by adapter + tool
- **Producer task:** TASK-J003-001
- **Consumer task(s):** TASK-J003-007 (`llama_swap_base_url` → adapter `base_url`), TASK-J003-010 (`gemini_api_key` / `anthropic_api_key` → provider SDK; `frontier_default_target` → default target; `attended_adapter_ids` → Layer 2 assertion set)
- **Artifact type:** Pydantic `JarvisConfig` fields
- **Format constraint:** `llama_swap_base_url: str` (e.g. `http://promaxgb10-41b1:9000` — no trailing slash required; consumer appends `/v1` for OpenAI-compatible base URL); `gemini_api_key: SecretStr | None`; `anthropic_api_key: SecretStr | None`; `frontier_default_target: Literal["GEMINI_3_1_PRO", "OPUS_4_7"]`; `attended_adapter_ids: frozenset[str]` (default `{"telegram","cli","dashboard","reachy"}`).
- **Validation method:** TASK-J003-015's lifecycle smoke (constructing adapter + setting OPENAI_BASE_URL) + TASK-J003-018's attended-only test matrix.

---

## Suggested commit boundaries

One commit per wave (or per contract cluster within a wave) is a reasonable rhythm. Commit messages should reference the task IDs and the relevant DDR:

- Wave 1 commits: `envelope: primitives for FEAT-JARVIS-003 (TASK-J003-001..006)` — touches config, types, models, prompts, pyproject.
- Wave 2 commits: `components: jarvis-reasoner graph + LlamaSwapAdapter (TASK-J003-007..009, DDR-010/012/015)`; then `components: escalate_to_frontier L1+L2 (TASK-J003-010..011, DDR-014)`.
- Wave 3 commits: `wiring: session-aware tool lists + build_supervisor (TASK-J003-012..015, DDR-014 Layer 3)`.
- Wave 4 commits: `deploy: langgraph.json + unit tests (TASK-J003-016..019, DDR-013)`.
- Wave 5 commits: `acceptance: regression + integration + routing e2e (TASK-J003-020..024)`.

---

## Phase 2 close criteria (FEAT-JARVIS-003 side)

Per design.md §13 item 6:
- [ ] `jarvis chat` invokes `start_async_task(name="jarvis-reasoner", role=…)` correctly on three canned role prompts (critic / researcher / planner).
- [ ] `escalate_to_frontier` returns a real Gemini 3.1 Pro response when asked explicitly on the CLI adapter.
- [ ] Ambient watcher attempt to invoke `escalate_to_frontier` → structured error.
- [ ] `langgraph dev` spins both graphs locally without packaging errors (real server, not harness smoke).

These are manual validations AFTER AutoBuild lands the 24 subtasks — not part of the feature's AC.
