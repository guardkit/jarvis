# Agent Framework Assessment: ADK, A2A, and the Ship's Computer Evolution

**Date:** 19 May 2026  
**Author:** Rich Woollcott (with Claude AI research assistance)  
**Status:** Research — Decision Pending  
**Related:** ADR-ARCH-016 (NATS-only transport), distributed_agent_orchestration_architecture.md, fleet-master-index.md

---

## 1. Purpose

This document captures research into whether the Ship's Computer agent ecosystem should adopt Google's Agent Development Kit (ADK) and the Agent-to-Agent (A2A) protocol, either alongside or as a replacement for the current NATS JetStream-only orchestration. The trigger is threefold: (a) an IBM/Google Developers video clarifying that MCP and ADK solve different layers (connectivity vs orchestration), (b) an AWS Developer Advocate presenting A2A at DDD SouthWest on 16 May 2026, and (c) Rich's interest in a hybrid architecture where some agents run locally on GB10 and others run in the cloud for client deployments.

**Source video:** [MCP vs ADK — Connectivity vs Orchestration for AI Agent Development](https://www.youtube.com/watch?v=BedAaB1RKgE) (Google Developers channel). Insights extracted via YouTube Insights MCP — see `/Users/richardwoollcott/Projects/YouTube Channel/insights/MCP vs ADK - Connectivity vs Orchestration for AI Agent Development.md`.

---

## 2. Context: What We Have Today

The Ship's Computer fleet is a working POC proven through DDD SouthWest demos. The current stack:

| Layer | Technology | Status |
|-------|-----------|--------|
| Inference | llama-swap on GB10:9000 (OpenAI-compatible API) | Production (DECISION-DF-001) |
| Orchestration | LangChain DeepAgents SDK (built on LangGraph) | Production |
| Intent routing | Jarvis via NATS request-reply | Proven 4 May 2026 |
| Agent comms | NATS JetStream (ADR-SP-001) | Production |
| Knowledge graph | Graphiti / FalkorDB on Synology NAS | Production |
| Specialist agents | Unified harness (`specialist-agent`) with `--role` flag | Phase 1B complete |
| Chat surface | Open WebUI → NATS Pipe Function → Jarvis | Working |
| Embodied interface | Reachy Mini (Scholar + Bridge) via Pollen scaffolded app | Working |

Key architectural decisions already made:

- **ADR-SP-001:** NATS over Kafka/Redis for message bus (sub-millisecond latency, single binary, JetStream persistence)
- **ADR-SP-002:** Event bus as orchestration source of truth (PM tools are interchangeable adapters)
- **ADR-ARCH-016:** Six consumer surfaces, NATS-only transport
- **DECISION-DF-001:** No cloud API on critical path; llama-swap as unified inference front door

The A2A protocol was considered at the start of 2026 but deferred for simplicity. The question now is whether the ecosystem has matured enough to warrant adoption.

---

## 3. The Agent Framework Landscape in May 2026

### 3.1 Major Frameworks

The field has consolidated into five credible production options, each backed by a hyperscaler or frontier lab:

| Framework | Backer | Philosophy | Language Support | Key Strength |
|-----------|--------|-----------|-----------------|-------------|
| **Google ADK** | Google | Code-first, structured agents | Python, TypeScript, Go, Java | A2A native, hierarchical multi-agent, deploy-anywhere |
| **LangGraph** | LangChain | Explicit graph-based orchestration | Python, TypeScript | Widest model support, largest ecosystem (600+ integrations) |
| **AWS Strands** | AWS | Model-driven, minimal code | Python | Bedrock integration, 14M+ downloads, powers Amazon Q |
| **OpenAI Agents SDK** | OpenAI | Handoff model, sandbox execution | Python, TypeScript | Simple mental model, integrated tracing |
| **Claude Agent SDK** | Anthropic | Extended thinking, general-purpose | Python, TypeScript | Extracted from Claude Code, strong agentic patterns |

**Thoughtworks Tech Radar (April 2026):** ADK moved from "Assess" to "Trial". Quote: "ADK's strength lies in its deep integration with Google's AI infrastructure... designed for interoperability, supporting tool wrappers and the A2A protocol for agent-to-agent communication."

**Critical observation from The New Stack:** The hyperscalers are giving away frameworks as on-ramps to their paid inference and deployment runtimes. This is the GKE/EKS/AKS playbook applied to agents — free orchestrator, monetised infrastructure. For the Ship's Computer (which runs on owned hardware with zero cloud inference cost), this means we can take the framework without the cloud lock-in.

### 3.2 ADK Specifically

ADK Python 2.0 shipped with:

- **Workflow Runtime:** Graph-based execution engine with routing, fan-out/fan-in, loops, retry, state management, dynamic nodes, human-in-the-loop, and nested workflows
- **Task API:** Structured agent-to-agent delegation with multi-turn task mode
- **Runner/Yield pattern:** Agent yields tool call requests or state changes; runner has full control to handle consequences before agent sees what happens next — analogous to our Player-Coach pattern
- **Session state vs Memory:** Short-term working memory (per conversation) and long-term cross-session knowledge — maps to our Graphiti split
- **Model connectors:** Gemini (native), OpenAI, Anthropic, Ollama, vLLM, LiteLLM, Apigee — genuinely model-agnostic despite the Google branding

ADK's Python GitHub repo has breaking changes in 2.0 (agent API, event model, session schema) but sessions generated by 2.0 are readable by 1.28+.

### 3.3 The Consensus View

Multiple independent framework comparison articles converge on the same conclusion: the question is not "which one?" but "which combination covers your stack?" Production teams typically use 3-4 of these tools together: ADK or LangGraph for orchestration, LangChain for tool integrations, LangSmith for observability, and A2A for inter-agent communication.

---

## 4. A2A Protocol: What Changed Since January

When we deferred A2A in January 2026, it was a new Google-only initiative with ~50 partners. The landscape has shifted dramatically:

- **150+ organisations** now support the standard (April 2026 milestone)
- **Linux Foundation governance** — no longer a single-vendor project
- **22,000+ GitHub stars** on the A2A repository
- **Five production-ready SDKs:** Python, JavaScript, Java, Go, .NET
- **Deep platform integration:** Google (ADK native), Microsoft (Agent Framework), AWS (Bedrock AgentCore)
- **Enterprise production deployments** across supply chain, financial services, insurance, and IT operations
- **Industry adoption:** SAP (Joule), Zoom, ServiceNow, Workday, Auth0, Salesforce

### 4.1 How A2A Works

A2A uses standard web protocols: HTTP, JSON-RPC, and Server-Sent Events (SSE). The core abstraction is:

- **Agent Card:** JSON metadata describing an agent's identity, capabilities, and endpoint (like a business card)
- **Task object:** Represents a unit of work progressing through lifecycle states: `submitted → working → input-required → completed`
- **Asynchronous by design:** Supports long-running operations and handles connectivity interruptions
- **Modality independent:** Text, audio, video, structured data

### 4.2 A2A vs NATS: Different Problems

A2A and NATS serve fundamentally different purposes:

| Concern | A2A | NATS JetStream |
|---------|-----|----------------|
| Purpose | Cross-framework, cross-location agent delegation | Internal fleet real-time messaging |
| Latency | HTTP/SSE (~10-100ms) | Sub-millisecond (~0.1-0.4ms) |
| Protocol | HTTP + JSON-RPC + SSE | NATS protocol (binary, lightweight) |
| Discovery | Agent Cards (JSON endpoint) | Topic subscriptions |
| Best for | Task delegation across boundaries | Real-time voice, build pipeline events, internal state |
| Persistence | Stateful tasks with lifecycle | JetStream + KV store |

**Key insight:** A2A does NOT replace NATS. It adds a layer on top for cross-boundary agent communication. NATS remains the right choice for Reachy voice loops (sub-millisecond latency), internal fleet coordination, and build pipeline events.

### 4.3 The Three-Layer Stack

The industry is converging on a three-layer interoperability stack:

1. **MCP** (Model Context Protocol) — tool connectivity: how agents access tools and data, model-agnostic
2. **A2A** (Agent-to-Agent) — agent-to-agent communication: how agents delegate to each other across frameworks and locations
3. **ADK / LangGraph / Strands** — orchestration: how individual agents reason and act

A Q3 2026 joint MCP/A2A specification is the first formal step toward protocol-level bridges between these layers.

---

## 5. ADK + Local Models: Compatibility with DECISION-DF-001

This is the critical question for the Ship's Computer. ADK integrates with local models via **LiteLLM**, which provides a unified interface to 100+ LLM providers through OpenAI-compatible endpoints.

### 5.1 llama-swap Compatibility

Since llama-swap on GB10:9000 exposes an OpenAI-compatible API, ADK can connect directly:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

specialist = LlmAgent(
    model=LiteLlm(
        model="openai/qwen36-workhorse",
        api_base="http://gb10:9000/v1"
    ),
    name="architect_agent",
    instruction="You are a software architecture specialist...",
    tools=[review_architecture, check_drift, suggest_improvement]
)
```

The ADK docs explicitly support Ollama and vLLM via LiteLLM, with an important note: the provider must be `ollama_chat` not `ollama` to avoid infinite tool call loops and context loss. For llama-swap (which provides an OpenAI-compatible endpoint), the `openai/` provider prefix is the correct choice.

### 5.2 Proven Local-Only Examples

Multiple community projects have validated fully local ADK deployments:

- ADK + Ollama + LiteLLM POC (zero API cost, offline operation)
- ADK + Gemma 4 + Docker Model Runner (no cloud inference)
- ADK + vLLM + Qwen2.5 for offline business intelligence agents
- ADK + Ollama on AMD Instinct GPUs with A2A cross-framework coordination

The ADK docs include a dedicated Gemma page showing ADK + vLLM + Gemma 4 configurations, including thinking mode support — directly relevant to our Gemma 4 26B-A4B fine-tuned study tutor model.

### 5.3 Model-Specific Considerations

Our Qwen3.6-35B-A3B has proven tool calling through llama-swap (4 May demo). ADK's LiteLLM integration requires the model to support OpenAI-compatible tool/function calling. This is already validated for our workhorse model.

The Gemma 4 fine-tuned study tutor model uses `GemmaFunctionCallingMixin` in ADK (converts tool declarations to text prompts for models that don't support native function calling). This could be relevant if we ever want the tutor to use ADK tools.

---

## 6. ADK + LangChain / LangGraph Compatibility

Good news: ADK and LangGraph are explicitly designed to coexist.

### 6.1 Interoperability Mechanisms

- **ADK can consume LangChain tools** via `LangchainTool` wrapper — no rewrite needed
- **ADK can consume CrewAI tools** via `CrewaiTool` wrapper
- **LangSmith can trace ADK agents** via `configure_google_adk()` — observability across both frameworks
- **ADK agents can wrap LangGraph agents** as A2A endpoints (and vice versa)
- **A2A bridges frameworks:** Proven cross-framework coordination (ADK + CrewAI + LangGraph in AMD tutorial)

### 6.2 DeepAgents SDK Compatibility

Our specialist-agent harness uses LangChain DeepAgents SDK (built on LangGraph). The migration path is NOT a rewrite — it's an A2A bridge:

1. Wrap existing LangGraph-based specialist agents as A2A endpoints
2. Build new agents using ADK where appropriate
3. ADK orchestrator can delegate to LangGraph agents via A2A
4. Both frameworks can share LangChain tool integrations

### 6.3 Production Architecture Pattern

The pattern emerging from production teams (per multiple independent sources):

- **ADK** for top-level orchestration (sequential steps, parallel fan-out, agent topology)
- **LangChain** for individual tool calls (RAG retrieval, API integrations, LLM abstractions)
- **LangGraph** for complex stateful workflows (our Player-Coach loop, approval gates)
- **LangSmith** for observability (tracing every LLM call, tool invocation, routing decision)

This means our existing LangGraph-based specialist agents remain valuable — they handle the complex stateful reasoning that LangGraph excels at. ADK would handle the higher-level orchestration and A2A communication.

---

## 7. Hybrid Cloud/Local Architecture

This is the vision that ADK + A2A unlocks.

### 7.1 Cross-Platform Coordination (Proven)

AWS has demonstrated cross-platform agent coordination on Bedrock AgentCore Runtime where a Google ADK orchestrator directed Strands and OpenAI SDK agents running on the same infrastructure. AgentCore Runtime supports agents built with any framework (ADK, Strands, LangGraph, CrewAI, OpenAI Agents SDK) communicating via A2A.

This means an ADK agent running on GB10 can delegate to a Strands agent running on AWS Lambda, or vice versa, without custom translation layers.

### 7.2 Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        A2A Protocol Layer                           │
│          (HTTP/JSON-RPC/SSE — cross-boundary delegation)            │
├────────────────────────────┬────────────────────────────────────────┤
│      LOCAL (GB10 + NAS)    │         CLOUD (Future)                 │
│                            │                                        │
│  ┌──────────────────────┐  │  ┌──────────────────────────────────┐  │
│  │  Jarvis (GPA)        │  │  │  Client-facing agents            │  │
│  │  ADK orchestrator    │◄─┼──┤  (Cloud Run / Lambda / AgentCore)│  │
│  │  + NATS gateway      │  │  │  ADK or Strands                  │  │
│  └──────┬───────────────┘  │  └──────────────────────────────────┘  │
│         │ NATS (internal)  │                                        │
│  ┌──────▼───────────────┐  │                                        │
│  │  Specialist agents    │  │                                        │
│  │  LangGraph harness    │  │                                        │
│  │  (architect, PO, etc) │  │                                        │
│  │  Exposed as A2A       │  │                                        │
│  └──────────────────────┘  │                                        │
│                            │                                        │
│  ┌──────────────────────┐  │                                        │
│  │  Study Tutor          │  │                                        │
│  │  Gemma 4 fine-tuned   │  │                                        │
│  │  Direct Graphiti read │  │                                        │
│  └──────────────────────┘  │                                        │
│                            │                                        │
│  ┌──────────────────────┐  │                                        │
│  │  Reachy Mini robots   │  │                                        │
│  │  NATS real-time voice │  │                                        │
│  │  (latency-critical)   │  │                                        │
│  └──────────────────────┘  │                                        │
│                            │                                        │
│  ┌──────────────────────┐  │                                        │
│  │  llama-swap :9000     │  │                                        │
│  │  (inference endpoint) │  │                                        │
│  └──────────────────────┘  │                                        │
│                            │                                        │
│  ┌──────────────────────┐  │                                        │
│  │  Graphiti / FalkorDB  │  │                                        │
│  │  (Synology NAS)       │  │                                        │
│  └──────────────────────┘  │                                        │
└────────────────────────────┴────────────────────────────────────────┘
```

### 7.3 What Changes, What Stays

| Component | Change | Rationale |
|-----------|--------|-----------|
| NATS JetStream | **Stays** — internal fleet bus | Sub-millisecond latency for Reachy, build pipeline events, internal coordination |
| Specialist agents (LangGraph) | **Stay** — gain A2A endpoints | Complex stateful reasoning is LangGraph's strength; A2A exposes them to cloud agents |
| Jarvis intent router | **Evolves** — adds A2A capability | Becomes both NATS gateway (internal) and A2A host (external) |
| New agents | **ADK preferred** | Better primitives for structured agents, native A2A, model-agnostic |
| llama-swap | **Stays** — ADK connects via LiteLLM | Already OpenAI-compatible; no changes needed |
| Graphiti / FalkorDB | **Stays** | Knowledge graph is infrastructure, not framework-dependent |
| Open WebUI | **Stays** — chat surface | Pipe function still routes to Jarvis via NATS |
| Reachy robots | **Stay on NATS** | Real-time voice latency precludes HTTP/SSE |

---

## 8. Risk Assessment

### 8.1 Risks of Adopting ADK + A2A

| Risk | Severity | Mitigation |
|------|----------|------------|
| ADK is pre-GA in parts (Thoughtworks notes "occasional rough edges and upgrade friction") | Medium | Use stable 1.x for production; evaluate 2.0 workflow runtime incrementally |
| A2A adds HTTP latency to agent delegation (~10-100ms) | Low | Only use A2A for cross-boundary delegation; NATS remains for real-time internal comms |
| Two orchestration frameworks to maintain (ADK + LangGraph) | Medium | Clear boundary: ADK for new agents and top-level orchestration, LangGraph for existing complex workflows |
| LiteLLM is an additional dependency in the inference path | Low | LiteLLM is a thin wrapper; we can always fall back to direct OpenAI client calls |
| Google ecosystem gravity (ADK optimised for GCP) | Medium | Validated: ADK works fully local with Ollama/vLLM/LiteLLM; no GCP dependency for self-hosted |

### 8.2 Risks of NOT Adopting

| Risk | Severity | Notes |
|------|----------|-------|
| Isolation from agent interoperability ecosystem | High | 150+ orgs on A2A; industry standard hardening rapidly |
| No path for hybrid cloud/local deployments | High | Client-facing deployments need cloud agents that coordinate with local fleet |
| NATS-only transport limits agent discovery and cross-framework collaboration | Medium | NATS is excellent internally but doesn't support the Agent Card discovery pattern |
| Missed DDD SouthWest follow-up opportunity | Low | Blog post and talks could reference A2A adoption as progressive enhancement |

---

## 9. Recommended Approach

### 9.1 Decision: Incremental Adoption

**Do not rip out NATS.** NATS is the real-time internal bus. A2A and NATS serve different purposes at different layers.

**Adopt ADK incrementally for new agent development:**
- ADK for agents where structured orchestration, A2A exposure, or cloud deployment are needed
- LangGraph remains for existing complex stateful workflows (Player-Coach loop, specialist agents)
- Both coexist via A2A protocol bridges

**Add A2A endpoints to existing agents:**
- Expose specialist agents (architect, PO, etc.) as A2A services
- Jarvis evolves to be both NATS gateway and A2A host
- Cloud agents (future) delegate to local agents via A2A over Tailscale

### 9.2 Layered Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Real-time bus | NATS JetStream | Internal fleet comms, Reachy voice, build pipeline events |
| Agent orchestration | ADK (new agents) + LangGraph (existing complex agents) | Agent reasoning, tool use, workflow |
| Agent-to-agent | A2A protocol | Cross-framework, cross-location agent delegation |
| Tool connectivity | MCP | Standardised tool access (already in use) |
| Inference | llama-swap / GB10 (local) + cloud APIs (future) | Model serving |
| Observability | LangSmith (traces ADK and LangGraph) | Unified tracing across frameworks |

### 9.3 Proof of Concept: Suggested First Step

Build one new agent using ADK + LiteLLM → llama-swap as a proof of concept:

1. Create a simple ADK agent on GB10 using `LiteLlm(model="openai/qwen36-workhorse", api_base="http://localhost:9000/v1")`
2. Expose it as an A2A endpoint (Agent Card + JSON-RPC handler)
3. Have Jarvis delegate a task to it via A2A (alongside existing NATS delegation)
4. Validate round-trip: Open WebUI → NATS → Jarvis → A2A → ADK agent → llama-swap → response

The `fleet-gateway` repo is a natural candidate for this PoC — it's already positioned at the boundary between the internal NATS world and external interfaces.

---

## 10. Open Questions

| # | Question | Notes |
|---|----------|-------|
| 1 | Should the A2A endpoint live in Jarvis or in a separate gateway service? | Jarvis is already the GPA and intent router; A2A hosting could be a separate bounded context |
| 2 | How does A2A authentication work over Tailscale for hybrid deployments? | A2A supports HTTPS + auth tokens; Tailscale provides the network layer — but need to validate |
| 3 | What's the minimum ADK version for stable A2A + LiteLLM? | ADK Python 1.x is stable; 2.0 beta has workflow runtime but may have rough edges |
| 4 | Should we use ADK's session/memory services or continue with Graphiti? | Graphiti provides temporal knowledge graph semantics that ADK's memory services don't match — likely keep Graphiti as the knowledge layer, use ADK session for conversation state |
| 5 | Does the LangChain DeepAgents SDK ≥0.5.3 need any changes to expose agents as A2A endpoints? | DeepAgents is built on LangGraph; A2A wrapping happens at the transport layer, not the agent layer |
| 6 | What's the A2A overhead for local-to-local calls on the same machine? | HTTP loopback should be <1ms but needs measurement vs NATS's ~0.1ms |

---

## 11. References

### Primary Sources

- [MCP vs ADK — Connectivity vs Orchestration for AI Agent Development](https://www.youtube.com/watch?v=BedAaB1RKgE) — Google Developers (video)
- [ADK Documentation](https://google.github.io/adk-docs/) — Official docs
- [ADK Python GitHub](https://github.com/google/adk-python) — Source, 2.0 release notes
- [A2A Protocol — Linux Foundation](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) — April 2026 milestone
- [ADK on Thoughtworks Tech Radar](https://www.thoughtworks.com/radar/languages-and-frameworks/agent-development-kit-adk) — April 2026, "Trial"

### Framework Comparisons

- [Google ADK vs LangGraph — ZenML Blog](https://www.zenml.io/blog/google-adk-vs-langgraph) — Deep technical comparison
- [Google ADK vs LangChain vs LangGraph vs LangFlow vs LangSmith — Diego O'Hurtado](https://diegohurtadoo.medium.com/google-adk-vs-langchain-vs-langgraph-vs-langflow-vs-langsmith-60ed7b8e2d14) — Production architecture patterns
- [Agent Framework Selection Guide — DataOps Labs](https://blog.dataopslabs.com/ai-agent-framework-selection-guide) — 12-factor methodology
- [Agent Framework Container Wars — The New Stack](https://thenewstack.io/agent-framework-container-wars/) — Hyperscaler strategy analysis
- [Agent Interoperability Protocols — Zylos Research](https://zylos.ai/research/2026-03-26-agent-interoperability-protocols-mcp-a2a-acp-convergence) — MCP/A2A/ACP convergence

### Local Model Integration

- [ADK Ollama Documentation](https://google.github.io/adk-docs/agents/models/ollama/) — Official Ollama integration
- [ADK vLLM Documentation](https://google.github.io/adk-docs/agents/models/vllm/) — Official vLLM integration
- [ADK LiteLLM Documentation](https://docs.litellm.ai/docs/tutorials/google_adk) — Multi-provider setup
- [AI Multi-Agents with Google ADK and AMD GPUs](https://rocm.docs.amd.com/projects/ai-developer-hub/en/latest/notebooks/inference/power-Google-ADK-on-AMD-platform-and-local-LLMs.html) — Cross-framework A2A with local models

### A2A Deep Dives

- [Google A2A Protocol: How Agent-to-Agent Coordination Works — Atlan](https://atlan.com/know/google-a2a-protocol/) — Enterprise use cases
- [A2A Protocol Complete Guide 2026 — Rapid Claw](https://rapidclaw.dev/blog/a2a-protocol-complete-guide-2026) — Implementation guide
- [LangSmith ADK Tracing](https://docs.langchain.com/langsmith/trace-with-google-adk) — Cross-framework observability

---

## 12. Decision Record

**Decision:** Deferred pending PoC validation.

**Proposed ADR:** If PoC succeeds, create `ADR-ARCH-031-a2a-bridges-for-cross-boundary-delegation.md` recording the decision to add A2A as a cross-boundary agent communication layer alongside NATS.

**What this does NOT change:**
- DECISION-DF-001 (no cloud API on critical path) — local inference via llama-swap remains
- ADR-SP-001 (NATS for message bus) — NATS remains the internal real-time bus
- ADR-SP-002 (event bus as orchestration source of truth) — NATS events still own workflow state
- Specialist agent harness on LangGraph — existing agents are preserved and exposed via A2A

**What this adds:**
- A2A protocol as a new transport layer for cross-boundary agent delegation
- ADK as the preferred framework for new agents (especially those needing A2A exposure or cloud deployment)
- A path from local-only to hybrid cloud/local agent deployments
