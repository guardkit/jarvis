# Jarvis — General Purpose DeepAgent with Dispatch Tools

> **Version:** 2.0
> **Date:** 19 April 2026
> **Status:** Vision — ready for `/system-arch`
> **Supersedes:** v1.0 (March 2026)
> **Aligned with:** fleet-architecture-v3-coherence-via-flywheel.md (19 April 2026), forge-pipeline-architecture.md v2.2, fleet-master-index.md v2 + D40-D46
> **Framing source:** 19 April 2026 conversation — Rich + Claude, "the Tony Stark v1 mini-Jarvis" discussion

---

## 1. What Jarvis Is (v2 Framing)

**Jarvis is a General Purpose DeepAgent with dispatch tools.**

Not a thin intent router in front of a fleet. Not a classification layer. Not a separate process from the GPA. **Jarvis IS the GPA, and dispatch is one tool category among many.** The reasoning model reads registered capability descriptions and decides.

The v1 vision (March 2026) framed Jarvis as a "thin router with the GPA as one of many specialists to dispatch to." That framing made Jarvis a plumbing component. The v2 framing makes Jarvis a DeepAgent whose superpower is *knowing which brain to apply to which problem* — and dispatch is how it applies non-local brains.

**The one-sentence thesis:** *One reasoning model that knows which reasoning model to use.*

This is the Tony Stark / Iron Man aesthetic rendered architecturally. Stark's Jarvis isn't smart because it has one brain; it's smart because it knows which brain to apply to which problem.

---

## 2. Three Delegation Targets

Jarvis has three dispatch mechanisms, each for a different kind of work:

### Target 1: Async Subagents (same process, different model)

`AsyncSubAgent` instances declared at Jarvis startup. Each points to a LangGraph graph with a different `create_deep_agent(model=...)` configuration. Communication via ASGI (in-process). Preview feature in DeepAgents 0.5.3+.

**Use for:** model-routing, parallel reasoning workloads, long-running background research, anything where Jarvis is doing the work itself but wants to parallelise or pick a different brain.

**Ships with four at launch:**

| Name | Model | Description passed to supervisor |
|---|---|---|
| `deep_reasoner` | `google_genai:gemini-3.1-pro` | Deep reasoning, architectural synthesis, 1M-token context work |
| `adversarial_critic` | `anthropic:claude-opus-4-7` | Coach-style quality evaluation, subtle flaw identification. Higher cost — reserve for adversarial work |
| `long_research` | `openai:gpt-5.4` | Multi-hour open-ended research, persistent web search, synthesis |
| `quick_local` | `vllm:qwen3-coder-next` (local on GB10) | Quick lookups, privacy-sensitive content, low-stakes reasoning |

The descriptions include cost + latency signals so the reasoning model has skin in the routing decision. The supervisor's system prompt teaches a preference: **default to cheapest-that-fits; escalate on need.** Local vLLM is the floor; cloud-premium is the escalation.

### Target 2: Specialist Agents (different process, via NATS)

Architect, Product Owner, Ideation, UX Designer — each a deployment of the `specialist-agent` binary with `--role X`, each registered on `fleet.register` with its own `agent_id` and `AgentManifest`.

Communication via `agents.command.{agent_id}` / `agents.result.{agent_id}` (singular topics per ADR-SP-016). Discovered dynamically via `NATSKVManifestRegistry` with live watch per ADR-ARCH-015/ADR-ARCH-017.

**Use for:** fine-tuned domain specialists, work that needs its own Graphiti role group, services that scale independently, tasks that genuinely benefit from a separate model fine-tuned on a domain corpus.

Zero code changes needed when a new specialist role ships — same pattern as Forge.

### Target 3: Forge (different process, via JetStream publish)

Specifically for build intent. Jarvis publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per ADR-SP-014 Pattern A, with `triggered_by="jarvis"`, `originating_adapter`, `correlation_id`, and `parent_request_id`.

Not a command — a queued job. Durable in JetStream. Sequential execution by Forge per `max_ack_pending=1`.

Forge registers on `fleet.register` so Jarvis's capability-driven routing can *discover* it; triggering remains a JetStream publish.

**Use for:** build intent only. "Build a new feature for X", "Run the pipeline for Y", "Queue FEAT-XXX". Everything else routes elsewhere.

### How the reasoning model chooses

One mental pattern: **capability-driven dispatch via reasoning over descriptions.** Three registries:

- Async subagent specs declared at Jarvis startup (from `jarvis/config/subagents.yaml` or similar)
- NATS fleet discovered live from `agent-registry` KV bucket with 30-second cache + watch invalidation
- JetStream build queue just writes `pipeline.build-queued.*` — Forge is discovered via its fleet registration

All three become tools in Jarvis's DeepAgents toolbelt. Tool docstrings carry the descriptions. Reasoning model picks. Same pattern as Forge's ADR-ARCH-015 (no `agent_id` hardcoding) and ADR-ARCH-016 (fleet is the catalogue).

---

## 3. The Adapter Layer

Jarvis's attention comes from humans via adapters. Each adapter is a thin stateless translator between the modality's native protocol and NATS.

| Adapter | Input | Output | Launch priority |
|---|---|---|---|
| **Telegram** | Telegram Bot API → NATS | NATS → Telegram Bot API | 1 — quickest feedback loop |
| **CLI wrapper** | stdin → NATS | NATS → stdout | 2 — for testing + scripting |
| **Dashboard** | WebSocket → NATS | NATS → WebSocket → React UI | 3 — visual monitoring |
| **Reachy Mini** | Voice → Whisper → NATS | NATS → TTS → Reachy speaker + expressions | 4 — when hardware arrives |

All adapters use the `nats-asyncio-service` template (built from `deepagents-orchestrator-exemplar`). Topics follow the existing taxonomy:

- `jarvis.command.{adapter}` — inbound user input
- `jarvis.intent.classified` — (legacy, retained for observability) — Jarvis's classification output event
- `jarvis.dispatch.{target}` — (legacy) — dispatch event for tracing
- `notifications.{adapter}` — outbound proactive messages

**Key principle unchanged:** Adapters are stateless translators. Business logic lives in Jarvis. Jarvis uses `AsyncSubAgent` task IDs + `correlation_id` to route replies back to the originating adapter.

---

## 4. Thread-per-Session Model

**Single Jarvis supervisor, thread-per-session.** A "session" is an adapter + time window.

- Reachy voice session this morning → thread A
- Telegram conversation this evening → thread B
- Dashboard session while coding → thread C

Threads share **Memory Store** (LangGraph long-term memory) so "what we discussed this morning" works across adapters. Threads do **not** share live context windows — Telegram doesn't see Reachy's current context, which prevents context bleed and auto-summarisation churn.

Cross-thread continuity via:

- **Memory Store** for durable recall ("last week we talked about...")
- **Graphiti `jarvis_routing_history`** for routing priors (learned preferences across all sessions)
- **Graphiti `jarvis_ambient_history`** for notification-pattern priors

This is the LangGraph-native pattern: supervisor graph state is thread-scoped; Memory Store is thread-independent.

---

## 5. Selectively Ambient — Three Patterns

Jarvis's ambient behaviour has three patterns with different costs and risks.

### Pattern A — Reactive
Jarvis responds when spoken to. Baseline DeepAgents behaviour.

### Pattern B — Triggered
Watchers — async subagents monitoring a condition, emitting a notification when it fires. Implemented as `start_async_task` with a watcher subagent prompt ("monitor X, return when Y"). Stateful threads, async sleeps internally.

Example watchers:
- "Watch the Forge queue — when FEAT-FORGE-007 completes, nudge me"
- "Watch my calendar — when I have a free 2-hour block today, suggest working on the talk"
- "Watch the NVIDIA driver apt channel — notify when 590 appears"

### Pattern C — Volitional
Jarvis notices something on its own and proactively speaks. "You haven't committed to forge in 4 days and the DDD talk is in 3 weeks." Requires either a scheduler or a long-lived async subagent on a daily cadence.

### v1 Scope

**Commit to A and B. Prototype C as an opt-in skill only.** One skill — "morning briefing" — that runs on demand (Rich asks for it) but could later become scheduled. This lets Pattern C earn its place without auto-enabled-from-day-one risks of annoyance or false alarms.

---

## 6. Skills

DeepAgents 0.5.3+ exposes **Skills** as a first-class capability — reusable workflows, domain knowledge, and custom instructions the agent can invoke.

**v1 ships with three skills:**

| Skill | Purpose |
|---|---|
| `morning-briefing` | Synthesis of calendar + pipeline status + news scan. Opt-in; Rich triggers it. Candidate for Pattern C graduation. |
| `talk-prep` | DDD Southwest progress tracker — what's done, what's next, where energy should go today |
| `project-status` | Query Forge queue + specialist-agent fleet state + Graphiti knowledge for a project |

Skills are tool compositions, not new code. They compose existing dispatch targets + Memory Store + Graphiti queries into a named capability.

Fleet-master-index D28 ("Skills layer dropped — superseded by fine-tuning strategy") applied to specialist-agent roles. It does not apply to Jarvis — Jarvis is not fine-tuned and benefits from Skills as composable shortcuts.

---

## 7. The Learning Flywheel (per fleet v3 §7)

Jarvis has its own learning track, structurally identical to Forge's.

### Two Graphiti groups

- `jarvis_routing_history` — dispatch decisions + outcomes + human redirects
- `jarvis_ambient_history` — watcher firings + notification outcomes + human dismisses

### `jarvis.learning` module

Same pattern as `forge.learning`. Inside the Jarvis process (module, not separate agent — per fleet v3 D45 deferring meta-agent split). Detects patterns in routing priors and ambient behaviour. Proposes `CalibrationAdjustment` entities. Rich confirms via CLI or notification round-trip.

### Implicit metrics

- **Routing**: redirection rate ("actually, try that with Opus") as the first-order correction signal. Retry rate and cost-adjusted satisfaction once baselines are established.
- **Ambient**: dismiss rate on proactive notifications; response latency; whether the notification was acted on.

### Trace-richness from day one

Per ADR-FLEET-001, every `jarvis_routing_history` and `jarvis_ambient_history` entry captures the full reasoning trace: tool-call sequence, subagent task IDs, cost/latency per model call, Rich's response text (not just button presses), environmental context.

This compounds. Every session makes future sessions better. Every redirect sharpens future routing. Every dismissed notification refines Pattern B thresholds.

---

## 8. Infrastructure Dependencies

All inherited from fleet substrate. No new infrastructure required.

| Dependency | Role in Jarvis |
|---|---|
| **NATS JetStream** | Fleet event bus, adapter↔Jarvis, Jarvis↔Forge (via `pipeline.build-queued.*`), Jarvis↔specialist-agents |
| **`nats-core`** | Typed payloads, `AgentManifest`, `NATSKVManifestRegistry`, topic registry |
| **DeepAgents 0.5.3+** | Core harness, `write_todos`, filesystem, `execute`, `task`, `AsyncSubAgent`, `interrupt()`, Memory Store, permissions, Skills, auto-summarisation |
| **Graphiti / FalkorDB** | `jarvis_routing_history`, `jarvis_ambient_history`, general knowledge queries |
| **vLLM on GB10** | `quick_local` subagent backing (Qwen3-Coder-Next) |
| **Cloud providers** | Gemini 3.1 Pro, Claude Opus 4.7, GPT-5.4 — for respective subagents |
| **Fleet registration via `fleet.register`** | Jarvis itself registers with `agent_id=jarvis`, intents for GPA tasks + meta-dispatch |

---

## 9. Hardware Topology

| Machine | Role |
|---|---|
| **MacBook Pro M2 Max** | Primary Claude Desktop / planning environment; Dashboard client; CLI adapter host |
| **Dell DGX Spark GB10 (128GB)** | Jarvis runs here. NATS, vLLM (quick_local backing), FalkorDB, ChromaDB, Reachy USB connection. Docker host. |
| **Synology DS918+ NAS (32TB)** | Backup + archived traces per ADR-FLEET-001 retention policy |
| **Reachy Mini ×2** | Scholar (tutoring interface, Study Tutor target) + Bridge (Jarvis interface). On order. |

Connected via Tailscale mesh. NATS at `nats://100.x.y.z:4222`.

---

## 10. Resolved Decisions (Carry Forward)

### Fleet-wide (from fleet-master-index D1-D39 and fleet v3 D40-D46)

| # | Decision | Resolution |
|---|---|---|
| D1 | Agent framework | LangChain DeepAgents SDK 0.5.3+ |
| D2 | Reasoning model | Configurable per subagent (see §2) |
| D4 | Event bus | NATS JetStream |
| D6 | NemoClaw | Rejected. Revisit Q3-Q4 2026. Hooks named but not built (D46). |
| D14 | Containerisation | Jarvis runs in Docker container |
| D15 | Agent discovery | Dynamic CAN-bus via `fleet.register` + `agent-registry` KV |
| D35 | Confidence-gated checkpoints | Applied via Coach scores from specialist agents (when dispatched) |
| D40 | Three surfaces, one substrate | Jarvis IS a DeepAgent; routing is tool selection |
| D41 | Flywheel-via-calibration-loop fleet-wide | `jarvis.learning` + Graphiti groups |
| D42 | Trace-richness by default | Per ADR-FLEET-001 from Jarvis v1 |
| D43 | Model routing is a reasoning decision | Async subagents expose models; supervisor picks |
| D44 | Selectively ambient, A+B for v1 | Pattern C as opt-in skill only |
| D45 | Meta-agent split and harness auto-rewriting deferred | `jarvis.learning` is a module, not separate agent |
| D46 | NemoClaw integration hooks named but not built | — |

### Jarvis-specific (new)

| # | Decision | Resolution |
|---|---|---|
| **J1** | Jarvis architecture | DeepAgent with dispatch tools; not a thin router |
| **J2** | Four launch subagents | `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local` |
| **J3** | Session model | Single supervisor, thread-per-session (adapter + time window) |
| **J4** | Cross-session continuity | Memory Store + `jarvis_routing_history` + `jarvis_ambient_history` |
| **J5** | Launch adapters | Telegram first, CLI wrapper second, Dashboard third, Reachy when hardware arrives |
| **J6** | Launch skills | `morning-briefing`, `talk-prep`, `project-status` |
| **J7** | Classification approach | Reasoning over capability descriptions, not rule-based signal matching. Opens D11 from v1 vision; resolves it in favour of reasoning-model-driven routing |
| **J8** | GPA location | There is no separate GPA — Jarvis IS the GPA. Closes D12 from v1 vision |

---

## 11. Open Questions for `/system-arch` to Resolve

Questions that genuinely need architectural reasoning tomorrow:

| # | Question | Notes |
|---|---|---|
| **JA1** | `jarvis_routing_history` schema fields — exact Pydantic shape | Follow ADR-FLEET-001 base schema + Jarvis-specific fields. Specialist architect agent can propose the structure. |
| **JA2** | Ambient watcher resource limits — how many concurrent Pattern B watchers before we throttle? | DeepAgents 0.5.3 suggests `--n-jobs-per-worker 10` as a starting point for local dev. Need a defensible ceiling. |
| **JA3** | Cross-adapter handoff — what happens when Rich starts a task on Telegram and continues on Reachy? | Options: (a) force same-thread by conversation ID if Rich chooses; (b) summary-bridge via Memory Store; (c) both. |
| **JA4** | Skill discoverability — should skills be statically declared or dynamically registerable like NATS fleet? | v1 leans static. Future: skills-as-registered-capabilities is interesting but not v1. |
| **JA5** | Rich's confirmation UX for `CalibrationAdjustment` proposals | CLI-based approval round-trip is the baseline. Should Telegram also support it? |
| **JA6** | `quick_local` fallback when GB10 vLLM is under heavy load (AutoBuild running) | Candidate strategy: supervisor checks `system.health.vllm` and falls back to cloud cheap-tier for "quick" tasks. |

Note: v1 vision's D11 (intent classification model) and D12 (GPA location) are **resolved** by the Jarvis-IS-GPA framing. Neither is an open question anymore. D13 (cross-agent context) is answered by the Memory Store + thread-per-session model (J3, J4). D16 (Reachy adapter topology) and D17 (heartbeat timeout) remain open but are adapter-level and heartbeat-config decisions, not foundational.

---

## 12. Constraints

- **Local-first where feasible.** `quick_local` defaults handle privacy-sensitive and low-stakes work on GB10.
- **Cost discipline.** Per fleet v3 §4, supervisor defaults to cheapest-that-fits; escalation on reasoning need. Cost budget observable via trace-rich `jarvis_routing_history`.
- **Voice latency budget.** Reachy Mini voice interaction should feel conversational — sub-2-second target for reactive responses. Async subagents are for *non-voice* long-running work; voice reactive stays on fast tier (Gemini Flash or similar).
- **No horizontal scaling.** Single Jarvis supervisor process per user, per GB10 (mirrors Forge ADR-ARCH-027).
- **Best-effort availability.** No SLA. Bounded by GB10 uptime + Tailscale + LLM provider uptime (mirrors Forge ADR-ARCH-029).
- **Preview-feature dependency.** `AsyncSubAgent` is preview in 0.5.3. Pin `>=0.5.3, <0.6` with monitoring on 0.6.x release notes.

---

## 13. Build Sequence

Prerequisites (in order):

1. ✅ `nats-core` shipping at 98% coverage
2. ✅ `nats-infrastructure` configured
3. ◻ NATS running on GB10, integration tests passing
4. ◻ Specialist-agent Phase 3 (NATS-callable) — enables Jarvis→architect dispatch
5. ◻ Forge Phase 4 (at minimum partially) — enables Jarvis→build-queue
6. ◻ DeepAgents 0.5.3 validated on our codebase

Jarvis build:

1. **`/system-arch` on Jarvis** (tomorrow, 20 April 2026) — produces ARCHITECTURE.md + ADRs
2. `/system-design` — component boundaries, `jarvis_routing_history` schema, skill plugin interface
3. `/feature-spec × N` — one per major capability (dispatch, async subagents, skills, ambient watchers, learning)
4. `/feature-plan × N`
5. `autobuild × N` — waves, sequential within Jarvis's own DeepAgent harness
6. Validation — Telegram adapter first; dispatch to architect-agent; dispatch to forge; routing learning enabled

v1 ship target: **June 2026** (after Forge Phase 4 completes, same hardware, coincident trace-rich learning).

---

## 14. YouTube Content Angle

The Jarvis build is a multi-video arc:

- **"Building Jarvis — the Tony Stark Aesthetic"** — vision + why-this-not-chatbot (browse)
- **"One reasoning model that knows which reasoning model to use"** — the model-routing insight (search + browse)
- **"I Built a Learning Loop for Every Agent"** — Karpathy parallel + flywheel narrative (browse, technical)
- **"Giving My Robot a Brain"** — Reachy Mini integration (browse, hardware)
- **"Why I'm Not Using NemoClaw (Yet)"** — D6 rationale with driver-590 update (search + browse)
- **"Three Agents, One Substrate"** — fleet coherence story (browse, architectural)

The "one reasoning model that knows which reasoning model" line is the hook for the browse-algorithm version; the flywheel story is the deeper technical content.

---

## 15. Source Documents

Materials this vision was built from:

| Source | Contribution |
|---|---|
| fleet-architecture-v3-coherence-via-flywheel.md | Keystone framing: three surfaces, Jarvis-IS-GPA, flywheel-per-surface, D40-D46 |
| ADR-FLEET-001 | Trace-richness commitment — basis for `jarvis_routing_history` schema |
| forge-pipeline-architecture.md v2.2 | Jarvis→Forge trigger pattern (ADR-SP-014 Pattern A); capability-driven dispatch |
| forge/docs/architecture/ARCHITECTURE.md + ADRs | Pattern source for ADR-ARCH-015, ADR-ARCH-016, ADR-ARCH-019, ADR-ARCH-020 adoption |
| DeepAgents 0.5.3 docs (fetched 19 April 2026) | `AsyncSubAgent`, Memory Store, Skills, preview-feature warnings |
| The Karpathy Loop video transcript (Nate, 2026-04-19) | Flywheel pattern source, trace-richness insight, Karpathy Triplet, safety concerns |
| Meta-Harness paper (Stanford, 2026 preprint) | External validation of trace-rich learning; Full-filesystem proposer context |
| Original jarvis-vision.md v1 (March 2026) | What to carry forward: adapter pattern, NATS topic taxonomy, hardware topology. What to supersede: thin-router framing, GPA-as-separate-agent, six-agent fleet list. |
| Original jarvis-architecture-conversation-starter.md | Preferred decisions ADR-P1-01..06 — most carry forward with fleet v3 refinements |
| 19 April 2026 conversation (Rich + Claude) | Tony Stark mini-Jarvis framing, model-routing-as-reasoning insight, async subagents integration decision, selectively-ambient three-pattern model |
