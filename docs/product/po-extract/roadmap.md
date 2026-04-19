# ideas -- Product Roadmap

## Mode

extract

## Epics

### EPIC-001: Intent Routing

**Bounded Context:** Intent Routing

Delivers the thin Jarvis intent router that accepts normalised requests, classifies intent, applies routing policy, and dispatches work to the right fleet participant. This epic preserves the documented principle that Jarvis is glue and orchestration, not a monolithic agent.

**Features:**
  - FEAT-PO-001: Adapter Command Ingress and Correlation Handling
  - FEAT-PO-002: Intent Classification Against Registered Signals
  - FEAT-PO-003: Routing Policy and General Purpose Agent Fallback
  - FEAT-PO-004: Dispatch and Result Return Routing

### EPIC-002: Fleet Coordination

**Bounded Context:** Fleet Coordination

Delivers dynamic discovery, lifecycle management, and operational contracts for the Jarvis fleet over NATS JetStream. This epic makes adding, scaling, and replacing agents possible without router code changes.

**Features:**
  - FEAT-PO-005: Dynamic Agent Registration and Routing Table
  - FEAT-PO-006: Heartbeat, Availability, and Load-Aware Selection
  - FEAT-PO-007: NATS Subject Contracts and Payload Schema Validation
  - FEAT-PO-008: Containerised Fleet Deployment Sequence

### EPIC-003: Adapter Interface

**Bounded Context:** Adapter Interface

Delivers the stateless adapters that translate between user interaction channels and the NATS backbone. This epic covers both generic adapter behaviour and the Reachy Mini embodied interface.

**Features:**
  - FEAT-PO-009: Stateless Multi-Adapter Translation Layer
  - FEAT-PO-010: Reachy Bridge Voice Interaction Pipeline
  - FEAT-PO-011: Reachy Proactive Notifications and Expressive Feedback
  - FEAT-PO-012: Dual Reachy Role Configuration

### EPIC-004: General Purpose Agent

**Bounded Context:** Agent Execution

Delivers the General Purpose Agent as the default 'everything else' bucket in the Jarvis fleet. This epic covers the fallback agent runtime, tool roadmap, model routing, and cross-agent awareness.

**Features:**
  - FEAT-PO-013: General Purpose Agent ReAct Runtime
  - FEAT-PO-014: Intent-Based Model Routing for Local, Cloud, and Privacy-Sensitive Tasks
  - FEAT-PO-015: Phase 1 Core Tool Set
  - FEAT-PO-016: Phased Tool Expansion for Productivity, Home, and Personal Tasks
  - FEAT-PO-017: Cross-Agent Tools for Fleet Awareness and Handoff

### EPIC-005: Knowledge Context

**Bounded Context:** Knowledge Context

Delivers Graphiti-backed knowledge query and architectural memory capabilities used across Jarvis and the General Purpose Agent. This epic covers shared recall without forcing Jarvis to become a heavyweight memory manager.

**Features:**
  - FEAT-PO-018: Graphiti Knowledge Query Integration
  - FEAT-PO-019: Shared Context Strategy for Cross-Agent Conversations

### EPIC-006: Infrastructure and Runtime Strategy

**Bounded Context:** Infrastructure and Runtime

Delivers the infrastructure choices, host topology, and runtime constraints that the Jarvis architecture depends on. This epic also captures the documented rejection of NemoClaw for current production use.

**Features:**
  - FEAT-PO-020: NATS JetStream Backbone Provisioning
  - FEAT-PO-021: Provider-Abstracted Model Client
  - FEAT-PO-022: GB10-Centred Hardware Topology and Connectivity
  - FEAT-PO-023: DeepAgents Runtime Path Instead of NemoClaw

## Priority Rationale

Priority follows the documented build sequence and architectural dependencies. Fleet Coordination and NATS-backed contracts come first because Jarvis cannot route without registration, heartbeat, and subject governance; Intent Routing follows because the router is the system's control plane; the General Purpose Agent comes early as the first high-value fallback participant; adapters, especially Telegram and Reachy, depend on stable routing and return paths; knowledge context and broader runtime refinements follow once the core thin-router and fleet substrate are operational.

## Constraints and Dependencies

- Jarvis must remain a thin intent router and orchestration layer, not a monolithic agent.
- NATS JetStream is the required event backbone.
- Dynamic agent discovery via `fleet.register`, `fleet.deregister`, and `fleet.heartbeat.*` is a carried-forward decision.
- Agents are containerised in Docker.
- General Purpose Agent is the default fallback when no specialist strongly matches.
- Adapters are stateless translators and should not contain business logic.
- Provider abstraction must support local vLLM and cloud APIs interchangeably.
- Simple and privacy-sensitive tasks should be able to run locally on GB10.
- Voice latency matters for Reachy Mini and sub-2-second response is desirable.
- NemoClaw is rejected for now and should not be used as the primary runtime path.

## Open Questions

- Should the General Purpose Agent be repo-co-located initially, separately deployed from day one, or both in phased rollout?
- Should Jarvis conversation context be isolated per agent, shared via Graphiti, or maintained centrally by Jarvis and passed downstream?
- Should heartbeat timeout remain fixed at 90 seconds or become configurable per agent type?
- What confidence threshold should trigger fallback to the General Purpose Agent in production, and should it vary by adapter or intent family?
- Should Reachy use wake-word activation, button activation, or a hybrid mode for always-on listening?
- How should response correlation be modelled for concurrent multi-adapter conversations: shared notifications subjects only or per-session reply subjects as well?
- Who owns registration schema governance and backward compatibility across independently evolving fleet agents?
- Should Reachy adapter topology remain direct USB to GB10, become network-based via Reachy SDK, or support both modes?

## Coverage Score

**100%** of document sections have at least one mapped feature.

Raw score: 1.0

## Feature Spec Inputs

### FEAT-PO-001: Adapter Command Ingress and Correlation Handling

**Bounded Context:** Intent Routing

**Description:**
Jarvis must consume `jarvis.command.{adapter}` requests from all supported adapters and normalise them into a common command envelope with correlation and session metadata. This ingress path is the front door of the intent router and is responsible for preserving the originating adapter so results can be routed back through the correct modality.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Jarvis must remain a thin orchestration layer rather than a monolithic agent.
  - Adapters are stateless translators and should not own business logic.
  - Requests originate from multiple modalities and must preserve adapter identity for return-path routing.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, reachy-mini-integration.md

### FEAT-PO-002: Intent Classification Against Registered Signals

**Bounded Context:** Intent Routing

**Description:**
Jarvis must classify inbound requests using rule-based matching against registered signal words and intent metadata, with optional model fallback when requests remain ambiguous. The classifier needs to support low-latency conversational paths, especially for Reachy Mini voice interaction, while still handling less obvious phrasing when rule matches are weak.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, reachy-mini-integration.md

**Constraints:**
  - Latency matters for voice flows and sub-2-second interaction is desirable.
  - Classification should use registered signals and confidence metadata where available.
  - Provider abstraction must allow local and cloud classification paths.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, reachy-mini-integration.md

**Depends On:** FEAT-PO-005

### FEAT-PO-003: Routing Policy and General Purpose Agent Fallback

**Bounded Context:** Intent Routing

**Description:**
Jarvis must select the best specialist agent for a classified intent and fall back to the General Purpose Agent when no specialist is a strong match. The routing policy needs to respect documented confidence thresholds, preserve the 'generous with the general bucket' behaviour, and allow user redirection when a different agent is preferred.

**Source Documents:** jarvis-vision.md, general-purpose-agent.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - If no registered agent matches with confidence greater than 0.5, route to the General Purpose Agent.
  - General Purpose Agent is the default fallback path.
  - Jarvis should not hard-code specialist routing logic beyond policy rules.

**Suggested Context Files:** jarvis-vision.md, general-purpose-agent.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-002, FEAT-PO-005, FEAT-PO-010

### FEAT-PO-004: Dispatch and Result Return Routing

**Bounded Context:** Intent Routing

**Description:**
Jarvis must publish classified intents and dispatch messages to `jarvis.dispatch.{agent}`, then consume `agents.results.{agent}` and notifications so responses return through the originating adapter. This response router is what makes the fleet feel like one assistant rather than a disconnected set of containers.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Subject contracts are explicit architectural interfaces and not incidental implementation details.
  - Response routing must preserve adapter and correlation context.
  - Notifications and agent results must both be routable back to the correct adapter.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-001, FEAT-PO-003, FEAT-PO-005

### FEAT-PO-005: Dynamic Agent Registration and Routing Table

**Bounded Context:** Fleet Coordination

**Description:**
Fleet agents must self-register on startup through `fleet.register`, advertise intents, signals, confidence, concurrency, and status, and have their routing metadata persisted in the `agent-registry` KV bucket. Jarvis must treat this registration substrate as authoritative so agents can be added or scaled without changing router code.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Dynamic registration via NATS is a resolved architectural decision.
  - Routing table must survive router restarts through the `agent-registry` KV bucket.
  - Bad registrations can poison routing unless payloads are validated.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

### FEAT-PO-006: Heartbeat, Availability, and Load-Aware Selection

**Bounded Context:** Fleet Coordination

**Description:**
Registered agents must heartbeat every 30 seconds on `fleet.heartbeat.{agent_id}` with queue depth and active task data so Jarvis can track availability and balance load. Jarvis must mark agents unavailable when heartbeat policy is exceeded and use queue depth to break ties between equally suitable agents.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Default documented heartbeat interval is 30 seconds.
  - Current documented timeout example is 90 seconds, though policy remains open.
  - Queue depth and active tasks are required for load-aware selection.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-005

### FEAT-PO-007: NATS Subject Contracts and Payload Schema Validation

**Bounded Context:** Fleet Coordination

**Description:**
Jarvis must treat NATS subjects and payload schemas as explicit domain contracts covering commands, dispatches, registrations, heartbeats, approvals, results, notifications, and health events. Registration payloads and related fleet messages need schema validation so dynamic discovery remains stable across independently evolving agents.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Topic taxonomy requires governance and is part of the architecture.
  - Registration schema compatibility is a documented open governance issue.
  - The message surface spans command, dispatch, result, approval, notification, and health subjects.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-005

### FEAT-PO-008: Containerised Fleet Deployment Sequence

**Bounded Context:** Fleet Coordination

**Description:**
Jarvis and its fleet must be deployable as Docker containers with NATS infrastructure, streams, KV buckets, and fleet compose support in the documented build order. The deployment sequence needs to enable overlapping delivery after NATS is available while preserving the expectation that agents auto-register on startup.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Containerisation in Docker is a carried-forward decision.
  - The router depends on at least one agent being dispatchable.
  - Build order starts with GuardKit Factory and NATS infrastructure before Jarvis router and broader fleet expansion.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-005, FEAT-PO-007

### FEAT-PO-009: Stateless Multi-Adapter Translation Layer

**Bounded Context:** Adapter Interface

**Description:**
Jarvis must support Reachy Mini, Telegram, Slack, Dashboard, CLI, and PM webhooks as thin `nats-asyncio-service` translators between native protocols and NATS messages. These adapters must remain stateless and avoid embedding routing or business logic so the router and agents remain the only intelligence-bearing components.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Adapters are stateless translators by design.
  - Supported adapters include voice, messaging, dashboard, CLI, and PM webhooks.
  - The template pattern is `nats-asyncio-service`.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-007

### FEAT-PO-010: Reachy Bridge Voice Interaction Pipeline

**Bounded Context:** Adapter Interface

**Description:**
The Reachy Bridge adapter must translate between voice interaction and Jarvis routing by capturing audio, transcribing locally on the GB10, publishing `jarvis.command.reachy-bridge`, and speaking returned results through TTS. The pipeline needs to preserve the embodied interaction pattern where Reachy feels like a persistent Ship's Computer interface rather than just another microphone.

**Source Documents:** reachy-mini-integration.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Voice input uses local Whisper on GB10 in the documented flow.
  - Reachy is a thin NATS adapter rather than an embedded intelligence layer.
  - Voice latency should feel conversational and sub-2 seconds is desirable.

**Suggested Context Files:** reachy-mini-integration.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-001, FEAT-PO-004, FEAT-PO-009

### FEAT-PO-011: Reachy Proactive Notifications and Expressive Feedback

**Bounded Context:** Adapter Interface

**Description:**
The Reachy adapter must subscribe to `notifications.reachy-bridge`, play attention animations, wait for user engagement, and then speak notification content back through the robot. This gives Jarvis persistent presence and expressive feedback through head movement, antenna motion, and spoken updates rather than relying only on user-initiated requests.

**Source Documents:** reachy-mini-integration.md, jarvis-vision.md

**Constraints:**
  - Notifications are delivered through `notifications.{adapter}` subjects.
  - The adapter should leverage existing Reachy movement and expression capabilities.
  - Proactive notifications are a key part of the Ship's Computer feel.

**Suggested Context Files:** reachy-mini-integration.md, jarvis-vision.md

**Depends On:** FEAT-PO-004, FEAT-PO-010

### FEAT-PO-012: Dual Reachy Role Configuration

**Bounded Context:** Adapter Interface

**Description:**
The adapter stack must support two Reachy Mini units with identical adapter software but different default routing roles: Scholar for GCSE English tutoring and Bridge for Jarvis access. This configuration model needs to keep the adapter reusable while allowing per-unit defaults and resource planning on the shared GB10 host.

**Source Documents:** reachy-mini-integration.md

**Constraints:**
  - Both Reachy units are physically connected to the GB10 via USB in the documented topology.
  - Adapter software is identical and only default routing differs.
  - Shared GB10 resources may become a contention point for both units.

**Suggested Context Files:** reachy-mini-integration.md

**Depends On:** FEAT-PO-009, FEAT-PO-010

### FEAT-PO-013: General Purpose Agent ReAct Runtime

**Bounded Context:** Agent Execution

**Description:**
The General Purpose Agent must run as a single ReAct agent using the `langchain-deepagents` base template, selecting tools to answer natural language requests in one-shot or short multi-turn interactions. It exists to handle the mundane and unclassified requests that do not justify a weighted-evaluation pipeline or specialist dispatch.

**Source Documents:** general-purpose-agent.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - No adversarial loop, no Coach, and no weighted evaluation in this agent.
  - The agent should be fast turnaround rather than long-running pipeline execution.
  - It is the default fallback participant in the fleet.

**Suggested Context Files:** general-purpose-agent.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-003, FEAT-PO-005

### FEAT-PO-014: Intent-Based Model Routing for Local, Cloud, and Privacy-Sensitive Tasks

**Bounded Context:** Agent Execution

**Description:**
The General Purpose Agent must route simple queries to local vLLM on the GB10, route complex reasoning and synthesis to a cloud API, and keep privacy-sensitive calendar or email tasks on the local model path. This model routing mirrors the local-first privacy router concept while using the existing provider abstraction pattern instead of vendor lock-in.

**Source Documents:** general-purpose-agent.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md, nemoclaw-assessment.md

**Constraints:**
  - Provider abstraction must support local and cloud APIs interchangeably.
  - Simple and privacy-sensitive tasks should be able to run locally on GB10.
  - The design should avoid NVIDIA-specific runtime lock-in.

**Suggested Context Files:** general-purpose-agent.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md, nemoclaw-assessment.md

**Depends On:** FEAT-PO-013

### FEAT-PO-015: Phase 1 Core Tool Set

**Bounded Context:** Agent Execution

**Description:**
The General Purpose Agent must implement the MVP tool set of Web Search, Web Fetch, Calendar, Email Draft, Slack Draft, File Operations, Weather, and Timer/Reminder so Jarvis can handle research, scheduling, drafting, lookups, and local task support. These tools expand capability without changing the architecture because the ReAct pattern handles selection at runtime.

**Source Documents:** general-purpose-agent.md

**Constraints:**
  - Phase 1 tool set is the documented MVP scope.
  - Integrations include web APIs, local filesystem access, and local scheduling plus NATS notification.
  - Email and Slack are draft-oriented rather than autonomous send actions in the current docs.

**Suggested Context Files:** general-purpose-agent.md

**Depends On:** FEAT-PO-013, FEAT-PO-014

### FEAT-PO-016: Phased Tool Expansion for Productivity, Home, and Personal Tasks

**Bounded Context:** Agent Execution

**Description:**
The General Purpose Agent must support phased expansion beyond MVP with Productivity tools such as Linear, Git, Note Taking, and Calculator, followed by Home Automation, Shopping List, and Travel tools. This roadmap is explicitly tool-led, where each added integration compounds Jarvis capability without requiring a new specialist architecture.

**Source Documents:** general-purpose-agent.md

**Constraints:**
  - Phase 2, Phase 3, and later tool additions should extend capability without architecture changes.
  - Note Taking may use local markdown with optional Graphiti.
  - Home and personal integrations rely on external APIs like Home Assistant, Todoist, and Maps.

**Suggested Context Files:** general-purpose-agent.md

**Depends On:** FEAT-PO-015

### FEAT-PO-017: Cross-Agent Tools for Fleet Awareness and Handoff

**Bounded Context:** Agent Execution

**Description:**
The General Purpose Agent must expose cross-agent tools for Agent Status, Agent Trigger, and Knowledge Query so users can inspect fleet activity, trigger pipelines, and retrieve prior decisions. These tools are what make the fallback agent fleet-aware instead of behaving like a standalone desktop chat assistant.

**Source Documents:** general-purpose-agent.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Agent Status uses NATS `agents.status.*` subscription patterns.
  - Agent Trigger uses NATS dispatch subjects for handoff into the fleet.
  - Knowledge Query should use Graphiti search.

**Suggested Context Files:** general-purpose-agent.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-013, FEAT-PO-005, FEAT-PO-018

### FEAT-PO-018: Graphiti Knowledge Query Integration

**Bounded Context:** Knowledge Context

**Description:**
Jarvis ecosystem components must be able to query Graphiti for prior decisions, architectural memory, and other stored context when a request needs recall rather than fresh generation. In the documented design this capability is primarily surfaced through the General Purpose Agent's Knowledge Query tool and through architecture-oriented workflows that benefit from persistent memory.

**Source Documents:** general-purpose-agent.md, jarvis-architecture-conversation-starter.md, jarvis-vision.md

**Constraints:**
  - Graphiti is an external knowledge backend in the documented C4 views.
  - Knowledge query is a cross-agent tool rather than a replacement for routing.
  - Jarvis conversation context strategy remains an open decision.

**Suggested Context Files:** general-purpose-agent.md, jarvis-architecture-conversation-starter.md, jarvis-vision.md

### FEAT-PO-019: Shared Context Strategy for Cross-Agent Conversations

**Bounded Context:** Knowledge Context

**Description:**
Jarvis must support a documented strategy for carrying context across agent boundaries so requests like 'build that idea we just discussed' can be resolved coherently. The current documents leave open whether this is handled by isolated agents, shared Graphiti memory, or Jarvis-maintained session state, so the feature should establish an explicit implementation path while preserving thin-router boundaries.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, general-purpose-agent.md

**Constraints:**
  - Cross-agent conversation context is explicitly unresolved in the docs.
  - Jarvis must remain thin even if it participates in context handoff.
  - Graphiti is the documented candidate for shared memory.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, general-purpose-agent.md

**Depends On:** FEAT-PO-018

### FEAT-PO-020: NATS JetStream Backbone Provisioning

**Bounded Context:** Infrastructure and Runtime

**Description:**
Jarvis must run on NATS JetStream as the backbone for commands, dispatches, fleet lifecycle events, notifications, approvals, and health monitoring. The runtime needs streams, consumers, and KV buckets that support the documented CAN bus registration pattern and persistent routing metadata across restarts.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - NATS JetStream is a resolved architectural decision that should not be reopened.
  - The `agent-registry` KV bucket is part of the authoritative routing substrate.
  - Subject structure must support commands, dispatch, registration, heartbeat, results, notifications, and health.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-007

### FEAT-PO-021: Provider-Abstracted Model Client

**Bounded Context:** Infrastructure and Runtime

**Description:**
Jarvis and the General Purpose Agent must use a provider-abstracted model client so local vLLM and cloud APIs can be swapped through configuration rather than vendor-specific code paths. This abstraction is necessary to preserve privacy routing, provider independence, and the documented rejection of NVIDIA-only runtime lock-in.

**Source Documents:** jarvis-architecture-conversation-starter.md, jarvis-vision.md, general-purpose-agent.md, nemoclaw-assessment.md

**Constraints:**
  - Tool signatures should remain stable across cloud and local modes.
  - Provider independence is a recurring documented architectural principle.
  - The abstraction must support both router classification and agent execution paths.

**Suggested Context Files:** jarvis-architecture-conversation-starter.md, jarvis-vision.md, general-purpose-agent.md, nemoclaw-assessment.md

### FEAT-PO-022: GB10-Centred Hardware Topology and Connectivity

**Bounded Context:** Infrastructure and Runtime

**Description:**
The deployed system must use the DGX Spark GB10 as the execution host for NATS, vLLM, Graphiti, and fleet agents, while MacBook Pro acts as dashboard and CLI client and Reachy Mini connects as an embodied adapter endpoint. The topology must also account for Tailscale mesh connectivity and shared storage or persistence roles described for the NAS and FalkorDB.

**Source Documents:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, reachy-mini-integration.md

**Constraints:**
  - GB10 hosts NATS, vLLM, Graphiti, and agent execution.
  - Reachy units are physically connected to GB10 via USB in the documented integration plan.
  - Tailscale mesh networking is part of the operating context.

**Suggested Context Files:** jarvis-vision.md, jarvis-architecture-conversation-starter.md, reachy-mini-integration.md

**Depends On:** FEAT-PO-020

### FEAT-PO-023: DeepAgents Runtime Path Instead of NemoClaw

**Bounded Context:** Infrastructure and Runtime

**Description:**
Jarvis must use the NATS plus DeepAgents SDK runtime path as the current execution strategy instead of NemoClaw, because NemoClaw is documented as rejected for now due to alpha instability and DGX Spark onboarding failures. This decision keeps implementation on proven templates and battle-tested vLLM patterns while leaving room to revisit NemoClaw later if it matures.

**Source Documents:** nemoclaw-assessment.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Constraints:**
  - Decision D6 rejects NemoClaw for now and should not be reopened in the current roadmap.
  - Current preferred path is DeepAgents SDK plus NATS plus existing Docker setup.
  - NemoClaw may be revisited later as a complementary runtime, not a replacement architecture.

**Suggested Context Files:** nemoclaw-assessment.md, jarvis-vision.md, jarvis-architecture-conversation-starter.md

**Depends On:** FEAT-PO-021

## Source Documents

| Document | Contribution |
| --- | --- |
| general-purpose-agent.md | Defined the General Purpose Agent as the default fallback, including its ReAct runtime, phased tool roadmap, model routing, and cross-agent capabilities. It also provided open decisions around repo placement, session context, tool discovery, and escalation. |
| jarvis-architecture-conversation-starter.md | Provided the most explicit bounded contexts, C4 component breakdown, preferred architectural decisions, constraints, and open questions across routing, fleet coordination, adapters, execution, and knowledge. It also grounded domain contracts around NATS subjects, registration, fallback policy, and provider abstraction. |
| jarvis-vision.md | Supplied the core product vision for Jarvis as a thin intent router, the specialist fleet, dynamic discovery, NATS topic structure, adapter pattern, hardware topology, resolved decisions, and build sequence. It was the primary source for routing behaviour and fleet lifecycle. |
| nemoclaw-assessment.md | Documented why NemoClaw is rejected for now and why the current runtime path should remain NATS plus DeepAgents SDK with vLLM. It also reinforced provider independence, DGX Spark realism, and revisit conditions for future runtime evolution. |
| reachy-mini-integration.md | Defined the embodied adapter model for Reachy Mini, including voice input/output flows, proactive notifications, expressive feedback, dual-unit roles, dependencies, and latency concerns. It grounded the adapter-specific features for Bridge and Scholar configurations. |

## Assumptions

| # | Category | Assumption | Confidence | Impact if Wrong |
| --- | --- | --- | --- | --- |
| ASM-001 | domain | Jarvis is a real product concept rather than a pure architecture thought exercise, because the documents consistently describe user-facing behaviour, bounded contexts, runtime components, adapters, and delivery order. | high | If Jarvis is only exploratory architecture and not an intended product, the roadmap would overstate delivery-ready epics and features. |
| ASM-002 | technical | The `agent-registry` KV bucket is intended to be the durable source for live routing metadata across router restarts. | high | Routing, recovery, and registration features would need redesign around another persistence or discovery mechanism. |
| ASM-003 | operational | The General Purpose Agent should participate in the same fleet registration and heartbeat contracts as specialists, even if code is initially co-located with Jarvis. | high | Fallback routing and fleet uniformity would need a special-case integration path inside the router. |
| ASM-004 | technical | Local Whisper on GB10 is the primary transcription path for Reachy Bridge input in the first implementation. | medium | Voice adapter latency, privacy characteristics, and infrastructure sizing would differ materially. |
| ASM-005 | technical | Provider abstraction is required across both router classification and agent execution, not only within the General Purpose Agent. | high | Model client design could be narrower, but current features would over-abstract the router path. |
| ASM-006 | operational | The documented build sequence is advisory for delivery priority but not an absolute gating sequence after NATS infrastructure exists. | medium | Epic ordering and dependency planning would need to become more strictly sequential. |
