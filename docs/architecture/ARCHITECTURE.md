# Jarvis — System Architecture

> **Version:** 1.0
> **Generated:** 2026-04-20 via `/system-arch`
> **Status:** Architecture Design — ready for `/system-design`
> **Supersedes:** none (first-pass architecture for the Jarvis repo)
> **Related anchors:**
> - [docs/research/ideas/jarvis-vision.md](../research/ideas/jarvis-vision.md) v2 (19 Apr 2026) — vision
> - [docs/research/ideas/jarvis-architecture-conversation-starter.md](../research/ideas/jarvis-architecture-conversation-starter.md) v2 — session input
> - [../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md](../../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md) — fleet framing
> - [../forge/docs/architecture/ARCHITECTURE.md](../../forge/docs/architecture/ARCHITECTURE.md) — pattern source
> - [../guardkit/docs/research/dgx-spark/dark-factory-economics-and-model-serving.md](../../guardkit/docs/research/dgx-spark/dark-factory-economics-and-model-serving.md) — llama-swap rationale (foundational)

---

## 1. What Jarvis Is

Jarvis is a **General Purpose DeepAgent with dispatch tools** — the attended surface of the three-surface fleet (Jarvis + Forge + specialist-agents). One reasoning model, running locally on GB10, that knows which role to apply, which specialist to dispatch to, and when to queue a build. Rich interacts via four adapter surfaces (Telegram, CLI, Dashboard, Reachy Mini); Jarvis coordinates the rest of the fleet through NATS JetStream.

**Jarvis is not a thin router.** The v1 framing made Jarvis a classification layer in front of a GPA; v2 supersedes that — Jarvis IS the GPA, and dispatch is one tool category among many.

**The one-sentence thesis:** *One local reasoning model that knows which role to apply, which specialist to invoke, and when to escalate.*

---

## 2. Structural Pattern

**Clean/Hexagonal modules inside a DeepAgents 0.5.3+ supervisor** (mirrors Forge ADR-ARCH-001):

- The `create_deep_agent(...)` compiled state graph is the shell — reasoning loop, built-in tools (`write_todos`, filesystem, `execute`, `task`, `interrupt`), async subagent dispatch, Memory Store, Skills.
- Inside: pure domain modules (routing, watchers, learning, discovery, sessions) with no I/O imports.
- Thin adapters at the edges: NATS, Graphiti, llama-swap HTTP. Jarvis-specific `@tool` functions wrap adapters at the DeepAgents tool-layer boundary.
- No transport abstraction — NATS is the control-plane bus, llama-swap is the inference front door.

See [system-context.md](system-context.md) for C4 Level 1 and [container.md](container.md) for C4 Level 2.

---

## 3. Module Map (5 groups — ~20 Python modules + ~6 `@tool`-layer entries)

### A. DeepAgents Shell
- `jarvis.agent` — wires `create_deep_agent()` → `CompiledStateGraph`; exported via `langgraph.json`
- `jarvis.prompts` — system prompt templates with `{date}`, `{domain_prompt}`, `{available_capabilities}`, `{routing_priors}`, `{session_context}` placeholders injected at session start
- `jarvis.subagents` — 1 pre-declared: `jarvis_reasoner` (backed by `gpt-oss-120b` via llama-swap). Specialist roles (critic / researcher / planner) are prompt-driven modes, not separate subagents. Pattern B watchers spawned via `task()` on demand
- `jarvis.skills` — 3 launch skills: `morning-briefing`, `talk-prep`, `project-status`

### B. Domain Core (pure, no I/O imports)
- `jarvis.routing` — capability-description assembly; routing decision domain types
- `jarvis.watchers` — Pattern B watcher specs + lifecycle state + throttling policy
- `jarvis.learning` — pattern detection over routing/ambient history; proposes `CalibrationAdjustment` entities
- `jarvis.discovery` — runtime fleet capability resolution (uses adapter for NATS KV reads)
- `jarvis.sessions` — thread-per-session model; session identifier domain; summary-bridge handoff policy

### C. Tool Layer (`@tool(parse_docstring=True)` functions)
- `jarvis.tools.dispatch` — `dispatch_by_capability` (NATS specialists), `queue_build` (Forge JetStream), `start_async_task` (jarvis-reasoner + watchers), `escalate_to_frontier` (attended-only cloud escape; constitutionally blocked from ambient tool sets)
- `jarvis.tools.graphiti` — `record_routing_decision`, `record_ambient_event`, `query_knowledge`
- `jarvis.tools.external` — calendar, weather, email (read-only v1), Home Assistant, web search (ACL wrappers)
- `jarvis.tools.notifications` — emits `NotificationPayload` routed to originating adapter via `correlation_id`

### D. Adapters (I/O edges)
- `jarvis.adapters.nats` — consumes `jarvis.command.*`, publishes dispatches + notifications, fleet.register lifecycle, KV read + watch
- `jarvis.adapters.graphiti` — read/write against `jarvis_routing_history` + `jarvis_ambient_history`
- `jarvis.adapters.llamaswap` — `init_chat_model` configured for `http://promaxgb10-41b1:9000/v1` (OpenAI format) and `/v1/messages` (Anthropic format) via llama-swap
- **Adapter services (separate containers on GB10):** `telegram`, `cli`, `dashboard`, `reachy` — built from `nats-asyncio-service` template

### E. Cross-cutting
- `jarvis.config` — `AgentConfig` + `jarvis.yaml` loader (infrastructure + model aliases + constitutional rules + learning meta-config only; no behavioural config)
- `jarvis.fleet` — Jarvis's own `fleet.register` publication + heartbeat lifecycle
- `jarvis.cli` — Click CLI for operator control (status / confirm-adjustment / health)

---

## 4. Technology Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| Agent framework | LangChain DeepAgents `>=0.5.3, <0.6` |
| Graph runtime | LangGraph — `langgraph.json` / `langgraph dev` / `CompiledStateGraph` |
| Model client | `init_chat_model("<llama-swap-alias>")` via OpenAI-compatible base URL `http://promaxgb10-41b1:9000/v1` |
| Primary reasoner | `gpt-oss-120b` MXFP4 (llama-swap `jarvis-reasoner` alias; builders group, swap) |
| Voice/coder-adjacent | `qwen3-coder-next` FP8 (llama-swap `qwen-coder-next` alias; builders group, swap) |
| Attended-only escape | Gemini 3.1 Pro / Opus 4.7 via `escalate_to_frontier` tool (constitutionally attended-gated) |
| Schemas | Pydantic 2 + pydantic-settings (via `nats-core.AgentConfig`) |
| CLI | Click |
| Async I/O | `asyncio` |
| Testing | pytest + pytest-asyncio + `unittest.mock` (per `pytest-agent-testing-specialist` rule) |
| Lint / type | ruff, mypy `--strict` |
| CI | GitHub Actions — ruff + mypy + pytest gates on PR |
| Internal library | `nats-core` (pip-installed from sibling repo) |

---

## 5. Data Stores

| Store | Purpose | ADR |
|---|---|---|
| FalkorDB via Graphiti (`whitestocks:6379`) | `jarvis_routing_history`, `jarvis_ambient_history`, general knowledge | ADR-ARCH-020 |
| JetStream `FLEET` | Self-registration + heartbeats | fleet-master-index |
| JetStream `AGENTS` (7-day) | Specialist commands/results | ADR-ARCH-016 |
| JetStream `PIPELINE` (7-day, write-only from Jarvis) | Outbound build queue | ADR-SP-014 Pattern A |
| JetStream `JARVIS` | Inbound adapter commands | ADR-ARCH-016 |
| JetStream `NOTIFICATIONS` | Outbound proactive messages | ADR-ARCH-016 |
| NATS KV `agent-registry` | Live fleet discovery (30s cache + watch invalidation) | nats-core ADR-004 |
| LangGraph Memory Store | Cross-session recall | ADR-ARCH-009 |
| Per-session thread state | Ephemeral within supervisor graph | ADR-ARCH-009 |

**NOT used:** SQLite (ADR-ARCH-008 — diverges from Forge; no build-lifecycle equivalent). LangGraph checkpointer (not needed — sessions are ephemeral + Memory Store covers durable recall).

---

## 6. Inference Strategy (Foundational)

**All unattended inference routes through llama-swap on GB10** at `http://promaxgb10-41b1:9000`. No cloud LLMs on unattended paths. Cloud frontier models (Gemini 3.1 Pro, Opus 4.7) are permitted only via the `escalate_to_frontier` tool on attended adapter sessions, constitutionally blocked from ambient/learning/Pattern-C subagent tool sets.

llama-swap model groups:
- **forever** (always-on; lifecycle delegated to existing vLLM scripts): `qwen-graphiti` (Qwen2.5-14B FP8 for Graphiti entity extraction), `nomic-embed` (embeddings)
- **builders** (swap: true, exclusive: true — ONE at a time): `qwen-coder-next` (Qwen3-Coder-Next FP8, for AutoBuild + Jarvis coder-assist), `gpt-oss-120b` (GPT-OSS 120B MXFP4, `jarvis-reasoner` / `architect` / `coach` alias)

Swap cost ≈ 2–4 min cold load for 120B. Jarvis supervisor is swap-aware: voice-reactive paths queue if ETA ≤ 30s, otherwise TTS speaks a "one moment" acknowledgement before the substantive response.

See [decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md](decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md).

---

## 7. Multi-Consumer API Strategy

| Consumer | Direction | Protocol | Notes |
|---|---|---|---|
| Rich via Telegram | inbound | NATS `jarvis.command.telegram` | Priority 1 launch |
| Rich via CLI | inbound | NATS `jarvis.command.cli` | Priority 2; also `CalibrationAdjustment` approval surface |
| Rich via Dashboard | inbound + read-only subscribe | NATS `jarvis.command.dashboard` + read-only trace streams | Priority 3; React live trace view |
| Rich via Reachy | inbound | NATS `jarvis.command.reachy` | Priority 4 — hardware-gated |
| All adapters | outbound | NATS `notifications.{adapter}` + `correlation_id` | Trace-rich routing |
| Operator CLI | read + write | Click — reads Graphiti; writes via NATS | `status` / `approve-adjustment` / `health` |
| Forge | outbound | JetStream `pipeline.build-queued.{feature_id}` (Pattern A) | Write-only — queued, never commanded |
| Specialist Agents | outbound | NATS req/reply `agents.command.{agent_id}` / `agents.result.{agent_id}.{correlation_id}` | Discovered via fleet registry |
| Fleet Registry | in+out | NATS KV `agent-registry` (read) + `fleet.register` (publish) | Heartbeat + manifest |
| Other fleet agents (future) | inbound | NATS `agents.command.jarvis` | GPA-level delegation |
| llama-swap | outbound | OpenAI `/v1/...` + Anthropic `/v1/messages` | ALL inference |
| Graphiti | in+out | FalkorDB protocol | Trace-rich history + general knowledge |
| External APIs | outbound | HTTPS (CalDAV / REST / etc.) | Wrapped in `jarvis.tools.external` ACL |
| Cloud Frontier Models | outbound (attended only) | Provider SDKs | `escalate_to_frontier` tool — constitutionally gated |

**Explicitly NOT used:** MCP at Jarvis level (would overflow context — matches Forge ADR-ARCH-012); HTTP/REST; gRPC.

---

## 8. Selectively Ambient — Three Patterns

| Pattern | Scope | v1 Status |
|---|---|---|
| A — Reactive | Jarvis responds when spoken to | Baseline DeepAgents behaviour |
| B — Triggered | Watchers (async subagents monitoring a condition, emitting when fired) | Shipped; ≤10 concurrent; retry-3×-then-notify; non-durable across restart |
| C — Volitional | Jarvis notices something unprompted and speaks | Opt-in skill only (`morning-briefing`) — graduates on evidence |

---

## 9. Learning Loop

Two Graphiti groups, one write path:

| Group | Written by | Read by |
|---|---|---|
| `jarvis_routing_history` | `jarvis.adapters.graphiti` per routing decision (chosen role, alternatives, reasoning, cost, correlation, session, Rich response text) | Supervisor retrieval at next decision; `jarvis.learning` pattern detection |
| `jarvis_ambient_history` | `jarvis.adapters.graphiti` per watcher firing + outcome + dismiss | `jarvis.learning`; supervisor priors |

`jarvis.learning` detects patterns (e.g. "Rich redirected 4/5 recent reasoning attempts on `architecture-review` topics to `escalate_to_frontier`") and proposes `CalibrationAdjustment` entities. Rich confirms via CLI approval round-trip; entity lands in Graphiti; future sessions retrieve it. **No YAML edits** — behavioural config lives in Graphiti, not files.

Trace-richness from day one per [ADR-FLEET-001](../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md) / [ADR-ARCH-020](decisions/ADR-ARCH-020-trace-richness-by-default.md).

---

## 10. Cross-Cutting

| Concern | Approach | ADR |
|---|---|---|
| Auth | NATS account-based (APPMILLA); env-only LLM keys; DeepAgents permissions (fs/shell/network allowlists); constitutional, not reasoning-adjustable | ADR-ARCH-023 |
| Observability | structured `structlog` JSON logs + NATS `jarvis.*` / `notifications.*` event streams + Graphiti audit; optional LangSmith opt-in; no Prometheus V1 | ADR-ARCH-020 |
| Error handling | Tools return structured error strings, never raise; degraded modes are reasoning inputs | ADR-ARCH-021 |
| Validation | Pydantic 2 at every boundary (NATS, tools, CLI, Graphiti, YAML) | fleet-wide D22 |
| Secrets | env only; `structlog` redact-processor; never in `AgentManifest`/logs/Graphiti | agent-manifest-contract |
| Prompt-injection defence | Constitutional rules belt+braces (prompt AND executor assertion) | ADR-ARCH-022 |
| Thread isolation | Per-session thread identity is the isolation boundary; Memory Store is the only cross-thread channel | ADR-ARCH-009 |
| Caching | 30s + watch invalidation for fleet registry reads | Forge ADR-ARCH-017 (adopted) |

---

## 11. Constraints

- **No cloud LLMs on unattended paths** — foundational principle (ADR-ARCH-001).
- **Single instance, no horizontal scaling** (ADR-ARCH-026). Fleet growth = multiple Jarvis *users* (one per operator), not one scaled out.
- **Best-effort availability**, no SLA (ADR-ARCH-029 equivalent). Bounded by GB10 + Tailscale + llama-swap + NATS + Graphiti.
- **Voice latency target**: <2s p95 on reactive path (common case); swap-aware degradation with explicit acknowledgement during llama-swap swaps.
- **Ambient watchers ceiling**: ≤10 concurrent Pattern B watchers; non-durable across supervisor restart in v1.
- **Budget**: £0 unattended spend; fleet-wide attended escape ≈ £20–£50/month shared across all frontier-tier invocations.
- **Preview-feature dependency**: `AsyncSubAgent` is preview in DeepAgents 0.5.3; pinned `>=0.5.3, <0.6` with explicit compatibility review gating the 0.6 upgrade.

---

## 12. Relationship to Fleet Anchors

This architecture is a **crystallisation** of [fleet-architecture-v3-coherence-via-flywheel.md](../../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md) (v3, 19 Apr 2026) applied to the Jarvis surface:

- Preserves: three surfaces-one-substrate (D40), model routing as reasoning (D43), flywheel-per-surface (D41), trace-richness by default (D42, ADR-FLEET-001), selectively ambient A+B v1 (D44), `jarvis.learning` as module not separate agent (D45).
- Extends: the "four-cloud-subagents" suggestion from vision §2 is superseded by ADR-ARCH-001's local-first principle → single `jarvis-reasoner` on `gpt-oss-120b` with role-driven prompts.
- Clarifies: llama-swap on GB10 is the fleet's unified inference front door, not only Jarvis's — Forge and specialist-agent containers share the same `http://promaxgb10-41b1:9000` endpoint.

---

## 13. Decision Index

30 ADRs captured across the 6 categories plus foundational ADR-ARCH-001. See [decisions/](decisions/) for the full set:

| # | Title | Category |
|---|---|---|
| ADR-ARCH-001 | Local-first inference via llama-swap on GB10 — no cloud LLMs on unattended paths | **Foundational** |
| ADR-ARCH-002 | Clean/Hexagonal modules within DeepAgents supervisor | Structural pattern |
| ADR-ARCH-003 | Jarvis IS the GPA — not a thin router | Structural pattern |
| ADR-ARCH-004 | Jarvis registers on fleet.register for cross-agent delegation | Fleet integration |
| ADR-ARCH-005 | Seven bounded contexts with DDD context map | Domain model |
| ADR-ARCH-006 | Five-group module layout mirroring Forge | Module structure |
| ADR-ARCH-007 | Adapter services as separate containers | Deployment |
| ADR-ARCH-008 | No SQLite — Graphiti + Memory Store sufficient for Jarvis | Data stores |
| ADR-ARCH-009 | Thread-per-session with Memory Store summary-bridge | Session model |
| ADR-ARCH-010 | Python 3.12 + DeepAgents >=0.5.3,<0.6 pin | Technology |
| ADR-ARCH-011 | Single jarvis-reasoner subagent via gpt-oss-120b (replaces four-cloud roster) | Implementation substrate |
| ADR-ARCH-012 | Swap-aware voice latency policy (queue ≤30s, else "one moment" ack) | Implementation substrate |
| ADR-ARCH-013 | 10-concurrent Pattern B watcher ceiling | Scalability |
| ADR-ARCH-014 | Docker-on-GB10 single-instance deployment | Deployment |
| ADR-ARCH-015 | CI = ruff + mypy --strict + pytest; manual deploy | Technology |
| ADR-ARCH-016 | Six consumer surfaces; NATS-only transport at Jarvis level | API strategy |
| ADR-ARCH-017 | Static skill declaration for v1 | API strategy |
| ADR-ARCH-018 | CalibrationAdjustment approvals via CLI only in v1 | API strategy |
| ADR-ARCH-019 | Dashboard read-only live trace viewport | API strategy |
| ADR-ARCH-020 | Trace-richness by default (ADR-FLEET-001 adoption) | Observability |
| ADR-ARCH-021 | Tools return structured errors, never raise | Error handling |
| ADR-ARCH-022 | Constitutional rules enforced belt+braces | Security |
| ADR-ARCH-023 | Permissions constitutional, not reasoning-adjustable | Security |
| ADR-ARCH-024 | Pattern B watcher failure policy — retry-3×-then-notify | Error handling |
| ADR-ARCH-025 | DeepAgents 0.6 upgrade gated by compatibility review | Technology |
| ADR-ARCH-026 | No horizontal scaling — single instance per user per GB10 | Scalability |
| ADR-ARCH-027 | Attended-only cloud escape hatch via `escalate_to_frontier` tool | API strategy |
| ADR-ARCH-028 | Ambient watchers non-durable in v1; specs optionally persisted for respawn | Availability |
| ADR-ARCH-029 | Personal-use compliance posture — no formal regime | Compliance |
| ADR-ARCH-030 | Budget — £0 unattended; £20–£50/month attended cloud escape fleet-wide | Cost |

---

## 14. Open Questions Resolved in This Session

| # | Question | Resolution |
|---|---|---|
| JA2 | Ambient watcher resource ceiling | ≤10 concurrent Pattern B watchers (ADR-ARCH-013) |
| JA3 | Cross-adapter handoff semantics | Memory Store summary-bridge only; no explicit continue command in v1 (ADR-ARCH-009) |
| JA4 | Skill discoverability | Static declaration for v1 (ADR-ARCH-017) |
| JA5 | CalibrationAdjustment approval UX | CLI only in v1 (ADR-ARCH-018) |
| JA6 | quick_local fallback policy | Replaced by swap-aware supervisor + "one moment" ack; no cloud fallback on unattended path (ADR-ARCH-012) |
| JA7 | Pattern B watcher failure mode | Silent log + retry 3× with backoff, then notify + DEAD state (ADR-ARCH-024) |
| JA8 | DeepAgents 0.6 migration strategy | Compatibility review + regression suite before unpin (ADR-ARCH-025) |

## 15. Open Questions Deferred to /system-design

| # | Question | Reason |
|---|---|---|
| JA1 | `jarvis_routing_history` exact Pydantic shape | Architecture commits to trace-richness + field list; exact Pydantic definition (validators, indexes) is a `/system-design` artefact. Captured as `ASSUM-routing-history-schema`. |

---

*"One local reasoning model that knows which role to apply, which specialist to invoke, and when to escalate."*
