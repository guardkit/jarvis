# Jarvis — Intent Router & Ship's Computer Vision

## For: `/system-arch` session · guardkit/jarvis repo · April 2026

---

## Purpose of this document

Captures the high-level vision for the Jarvis system — a unified intent router and
orchestration layer that makes the entire Ship's Computer agent fleet accessible through
any interaction modality (voice via Reachy Mini, messaging via Telegram/Slack, dashboard,
CLI). This is the "glue" that turns a collection of specialist agents into a coherent
personal AI assistant.

This document feeds into `/system-arch` to produce architecture intent, C4 diagrams,
component boundaries, ADRs, and open questions.

---

## What is Jarvis?

Jarvis is an **intent router** — a lightweight orchestration layer that:

1. Accepts natural language input from any adapter (voice, text, dashboard, CLI)
2. Classifies the intent of the request
3. Dispatches to the appropriate specialist agent (or handles directly via the General Purpose Agent)
4. Returns results through the originating adapter

The name is aspirational — inspired by Iron Man's JARVIS, Star Trek's Ship Computer, and
Red Dwarf's Holly. The goal is a persistent, always-available AI assistant that feels like
talking to a single intelligence, even though it's orchestrating a fleet of specialists behind
the scenes.

**Key insight:** Jarvis is NOT a single monolithic agent. It's a thin routing layer with a
rich set of specialist agents behind it. The intelligence comes from choosing the right
specialist for each request and from the General Purpose Agent handling everything that
doesn't fit a specialist.

---

## The Agent Fleet

Jarvis dispatches to six specialist agents plus a general purpose fallback, each with
complexity matched to its task. Together they form a complete pipeline from ideation
through to deployed code:

```
Ideation Agent → Product Owner Agent → Architect Agent → GuardKit Factory
(explore)        (document)             (architect)       (implement)
```

### 1. GuardKit Factory (Heavy — Full Adversarial Pipeline)
- **Repo:** `guardkit/guardkitfactory`
- **Template:** `langchain-deepagents-weighted-evaluation` (adversarial template to be extracted post-production as Phase 5)
- **Purpose:** Autonomous software development pipeline driving GuardKit slash commands
- **Complexity:** Multi-stage pipeline (arch → design → spec → plan → build → review), Player-Coach adversarial loop, Graphiti context, human-in-the-loop checkpoints
- **When dispatched:** "Build a new feature for...", "Create a system architecture for...", "Run the pipeline for..."
- **Model:** Gemini 3.1 Pro (orchestration/reasoning) + Claude Code SDK or vLLM Qwen3-Coder-Next (implementation)

### 2. YouTube Planner (Medium — Weighted Evaluation, Research-Intensive)
- **Repo:** `guardkit/youtube-planner`
- **Template:** `langchain-deepagents-weighted-evaluation`
- **Purpose:** AI-powered content planning from idea capture through to filmable bullet-point script
- **Complexity:** Multi-stage pipeline (idea capture → validation → hook/title → 3-act structure → script), competitive intelligence, weighted scoring
- **When dispatched:** "I have a video idea about...", "What should my next video be about?", "Research what channels are covering..."
- **Model:** Gemini 3.1 Pro (reasoning/evaluation) + Claude API (content generation)

### 3. Ideation Agent (Medium — Weighted Evaluation, Divergent Reasoning)
- **Repo:** `guardkit/ideation-agent`
- **Template:** `langchain-deepagents-weighted-evaluation`
- **Purpose:** Structured ideation sessions with weighted evaluation criteria — jumpstarts the exploratory thinking that currently happens manually in Claude Desktop
- **Complexity:** Player generates/expands ideas, Coach evaluates against weighted criteria, configurable criteria per domain
- **When dispatched:** "I want to explore an idea about...", "What if we built...", "Help me think through..."
- **Model:** Gemini 3.1 Pro (divergent reasoning, 1M context for full project landscape)

### 4. Product Owner Agent (Medium — Weighted Evaluation, Documentation)
- **Repo:** `guardkit/product-owner-agent`
- **Template:** `langchain-deepagents-weighted-evaluation`
- **Purpose:** Takes raw, unstructured information (brain dumps, meeting notes, regulatory docs, competitor analysis) and produces structured product documentation
- **Complexity:** Player generates document suite, Coach evaluates for grounding/completeness/actionability, domain-configurable templates
- **When dispatched:** "Generate product docs for...", "Structure this information into...", "Create a regulatory analysis for..."
- **Model:** Gemini 3.1 Pro (reasoning/evaluation) + Claude API (document generation)
- **Proof point:** FinProxy LPA — 14 docs (310 KB) in one weekend, James approved with minimal feedback

### 5. Architect Agent (Medium — Weighted Evaluation, Architecture Generation)
- **Repo:** `guardkit/architect-agent`
- **Template:** `langchain-deepagents-weighted-evaluation`
- **Purpose:** Translates product documentation into system architecture — C4 diagrams, ADRs, and GuardKit conversation starter documents for `/system-arch`
- **Complexity:** Player generates C4 diagrams + ADRs, Coach validates by tracing flows, Graphiti integration for architectural memory that compounds over projects
- **When dispatched:** "Architect this project", "Generate a system architecture from these docs", "Create a conversation starter for /system-arch"
- **Model:** Gemini 3.1 Pro (architectural reasoning) + Claude API (document generation)
- **Key pattern:** Output IS the input to `/system-arch` — the conversation starter document format

### 6. General Purpose Agent (Light — ReAct with Rich Toolset)
- **Repo:** `guardkit/jarvis` (co-located with intent router, or future separate repo)
- **Template:** `langchain-deepagents` (base template, no adversarial loop)
- **Purpose:** Everything else — research, drafting, scheduling, chores, quick lookups, home automation
- **Complexity:** Single ReAct agent with broad tool access, fast turnaround, no quality gate needed
- **When dispatched:** Default — anything that doesn't match a specialist pattern
- **Model:** Local vLLM for simple tasks, cloud API for complex reasoning (intent-based model routing)

---

## Intent Classification & Dynamic Agent Discovery (CAN Bus Pattern)

**Resolved decision (D15):** Agents self-register their capabilities on startup,
analogous to devices on a vehicle CAN bus announcing themselves. Jarvis builds its
routing table dynamically from these registrations — no router code changes when
adding new agents.

### How It Works

Each agent publishes an `AgentRegistrationPayload` to `fleet.register` on startup,
declaring:
- **Intents** it can handle, with confidence scores (0.0-1.0)
- **Signal words** that indicate those intents
- **Concurrency limits** (max_concurrent tasks)
- **Status** (ready, starting, degraded)

Jarvis subscribes to `fleet.register`, `fleet.deregister`, and `fleet.heartbeat.>`
and maintains the routing table in the `agent-registry` NATS KV bucket (survives
Jarvis restarts).

### Routing Algorithm

1. Classify the intent (lightweight LLM call or rule-based matching against registered signals)
2. Query the `agent-registry` KV for all registered agents
3. Filter to agents whose intents include the classified intent
4. Select the agent with highest confidence for that intent
5. If tied, pick the one with lowest queue_depth (from heartbeat data)
6. Dispatch to the selected agent
7. If no specialist matches, route to General Purpose Agent (default fallback)

### Example Registration

```yaml
# Product Owner Agent publishes this on startup:
agent_id: "product-owner-agent"
name: "Product Owner Agent"
template: "langchain-deepagents-weighted-evaluation"
intents:
  - pattern: "product.document"
    signals: ["product docs", "structure this", "regulatory analysis", "document the requirements"]
    confidence: 0.9
    description: "Generate structured product documentation from raw information"
  - pattern: "ideate"
    signals: ["explore product", "what should we build"]
    confidence: 0.3  # can handle but ideation-agent is better
max_concurrent: 1
status: "ready"
```

### Lifecycle

```
Agent starts  → publishes registration to fleet.register
              → Jarvis adds to routing table (agent-registry KV)
              → Agent heartbeats every 30s to fleet.heartbeat.{agent_id}

Agent running → Jarvis routes matching requests to it
              → Heartbeat includes queue_depth + active_tasks for load balancing

Agent stops   → publishes deregistration to fleet.deregister
              → Jarvis removes from routing table

Agent crashes → heartbeat stops → after 90s Jarvis marks unavailable
              → docker restart policy recreates container → agent re-registers
```

### Why This Matters

Adding the Product Owner Agent or Architect Agent requires zero changes to the
Jarvis router. Build it, containerise it, start it — Jarvis discovers it automatically.
Scale GuardKit Factory to two instances for parallel builds — Jarvis load-balances
across them via queue_depth. This is the architectural pattern that makes the fleet
genuinely extensible.

The classification should be **generous with the general bucket** — if no registered
agent matches with confidence > 0.5, route to General Purpose Agent. Users can always
redirect: "Actually, run that through the ideation agent."

---

## Infrastructure: NATS JetStream as the Backbone

All communication flows through NATS JetStream — the Ship's Computer event bus. This is
already designed and documented in the Ship's Computer Architecture (v1.0, January 2026).

### Topic Structure

```
jarvis.command.{adapter}          ← Input from any adapter
jarvis.intent.classified          ← Router publishes classified intent
jarvis.dispatch.{agent}           ← Dispatched to specialist agent

fleet.register                    ← Agent capability announcements (CAN bus pattern)
fleet.deregister                  ← Agent graceful shutdown
fleet.heartbeat.{agent_id}        ← Periodic health signal (every 30s)

agents.status.{agent}             ← Agent status updates (existing Ship's Computer topics)
agents.approval.{agent}.{task}    ← Human-in-the-loop checkpoints
agents.results.{agent}            ← Agent results

notifications.{adapter}           ← Outbound notifications to adapters
system.health.{component}         ← Health monitoring
```

### Adapter Pattern

Each input/output modality is a thin NATS adapter — a `nats-asyncio-service` (from the
template being built today) that translates between the modality's native protocol and
NATS messages:

| Adapter | Input | Output | Template |
|---------|-------|--------|----------|
| **Reachy Mini** | Voice (OpenAI Realtime API / Whisper) → text → NATS | NATS → TTS → Reachy speaker + expressions | `nats-asyncio-service` |
| **Telegram** | Telegram Bot API → NATS | NATS → Telegram Bot API | `nats-asyncio-service` |
| **Slack** | Slack Events API → NATS | NATS → Slack Web API | `nats-asyncio-service` |
| **Dashboard** | WebSocket → NATS | NATS → WebSocket → React UI | `nats-asyncio-service` |
| **CLI** | stdin → NATS | NATS → stdout | `nats-asyncio-service` |
| **PM Webhooks (Linear)** | Linear webhook → NATS | NATS → Linear API | `nats-asyncio-service` |

**Key principle:** Adapters are stateless translators. They don't contain business logic.
The router and agents contain all the intelligence.

---

## Hardware Topology

| Machine | Role in Jarvis |
|---------|---------------|
| **MacBook Pro M2 Max** | Dashboard client. CLI adapter. Planning/research. Cloud API calls originate here. |
| **Dell DGX Spark GB10 (128GB)** | NATS server. vLLM inference (3 models). Graphiti (FalkorDB). Agent execution. Docker host. Reachy Mini connection (USB). |
| **Synology DS918+ NAS (32TB)** | FalkorDB persistence. Shared storage. Backup. |
| **Reachy Mini (×2)** | "Scholar" (tutoring interface). "Bridge" (Ship's Computer / Jarvis interface). |

Connected via Tailscale mesh VPN. NATS accessible at `nats://100.x.y.z:4222` from any device.

---

## Relationship to Existing Architecture

| Document | Relationship |
|----------|-------------|
| **Ship's Computer Architecture** (v1.0, Jan 2026) | Jarvis IS the Ship's Computer with a concrete intent router. Same NATS infrastructure, message envelope format, topic conventions, approval workflow. |
| **Dev Pipeline Architecture** (v1.0, Feb 2026) | GuardKit Factory replaces the Build Agent concept. Jarvis dispatches to it. |
| **Pipeline Orchestrator Conversation Starter** | The GuardKit Factory conversation starter — feeds `/system-arch` for the factory specifically. |
| **Pipeline Orchestrator Consolidated Build Plan** | The overall build plan — Jarvis adds the intent router layer and the three additional agents on top. |

---

## Resolved Decisions (Carry Forward)

These decisions are inherited from the Pipeline Orchestrator and Ship's Computer work.
Do NOT reopen.

| # | Decision | Resolution |
|---|----------|-----------|
| D1 | Agent framework | LangChain DeepAgents SDK |
| D2 | Reasoning model | Gemini 3.1 Pro API or Claude API (configurable) |
| D3 | Implementation model | Claude Code SDK (cloud) or vLLM on GB10 (local) |
| D4 | Event bus | NATS JetStream |
| D5 | Two-model separation | Orchestration model MUST differ from implementation model |
| D6 | NemoClaw | Rejected for now — not production-ready on DGX Spark (see `nemoclaw-assessment.md`) |
| D7 | Tool interface stability | Tool signatures identical across cloud and local modes |
| D8 | Multi-project | Concurrent pipelines with NATS topic prefix isolation |
| D9 | Template strategy | Option C — enhance base + create adversarial template (harvest from production) |
| D10 | ChromaDB over NVIDIA RAG | ChromaDB PersistentClient for vector storage |
| D14 | Containerisation | Phase 2 — agents run in Docker containers for lifecycle management, concurrency, and fleet scaling. See big-picture-vision-and-durability.md. |
| D15 | Agent discovery | Dynamic registration via NATS (CAN bus pattern). Agents self-announce capabilities to `fleet.register`. Routing table in `agent-registry` KV bucket. See ADR-004 in nats-core. |

---

## New Decisions for `/system-arch` to Resolve

| # | Question | Options | Considerations |
|---|----------|---------|---------------|
| D11 | Intent classification model | a) Local Nemotron Nano, b) Cloud API (fast/cheap tier), c) Rule-based matching against registered signals + LLM fallback | Latency matters for voice — Reachy needs fast response. Rule-based for registered signals, LLM for ambiguous. |
| D12 | General Purpose Agent location | a) Co-located in jarvis repo, b) Separate repo/container | Co-location argument: it's the default/fallback. Separate container argument: follows the fleet pattern, independently scalable. |
| D13 | Conversation context across agents | a) Each agent independent, b) Shared context via Graphiti, c) Jarvis maintains session state and passes to agents | Multi-turn conversations that span agents need thought. "Build that idea we just discussed" requires context handoff. |
| D16 | Reachy Mini adapter architecture | a) Direct USB connection from GB10, b) Network-connected via Reachy SDK, c) Hybrid | Two Reachy units with different roles (Scholar vs Bridge) may need different adapter configs. |
| D17 | Heartbeat timeout policy | a) Fixed 90s, b) Configurable per agent, c) Adaptive based on agent type | Heavy agents (GuardKit Factory) might legitimately go quiet for minutes during builds. |

---

## Build Sequence

The Jarvis intent router depends on having at least one agent to dispatch to. Recommended
build order:

1. **GuardKit Factory** (already in progress — `guardkitfactory` repo)
2. **NATS infrastructure + Fleet Compose** (NATS server, streams, KV buckets, agent-registry, docker-compose.fleet.yml)
3. **Jarvis intent router** (this repo — thin, subscribes to `fleet.register`, routes via KV-backed registry)
4. **General Purpose Agent** (broad tools, fast turnaround — first containerised agent to auto-register)
5. **Ideation Agent** (weighted evaluation, divergent reasoning)
6. **Product Owner Agent** (raw info → structured docs — FinProxy as first domain)
7. **Architect Agent** (product docs → C4 + ADRs → conversation starter for `/system-arch`)
8. **YouTube Planner** (weighted evaluation, research-intensive)
9. **Adapters** (Telegram first — quickest to test, then Dashboard, then Reachy Mini when hardware arrives)

Each agent is containerised (Dockerfile from `nats-asyncio-service` template) and
auto-registers with Jarvis on startup via the CAN bus pattern. Steps 3-8 can overlap
once NATS infrastructure exists. Scale any agent with `--scale` for parallel execution.

---

## YouTube Content Angle

Building Jarvis is a multi-video content arc for the channel:

- **"I'm Building My Own Jarvis"** — the vision video (browse, emotional hook)
- **"From Specialist to Assistant"** — the journey from single-purpose agents to general intelligence (building in public)
- **"Why I'm Not Using NemoClaw (Yet)"** — honest assessment of NVIDIA's marketing vs reality (search + browse)
- **"Giving My Robot a Brain"** — Reachy Mini integration (browse, hardware porn)
- **"The Missing Piece Was an Intent Router"** — technical insight video (search)

This feeds directly into the YouTube Planner once it's operational — dogfooding the system.
