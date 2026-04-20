# Conversation Starter: Jarvis Build-Out — Phase Pairs Generation Brief

## Date: 19 April 2026 (updated 20 April 2026)
## Status: Decisions landed; `guardkit init` complete. **Next action:** use this document as input to a new Claude Code conversation that produces Phase 1 scope + build plan pair (and further phase pairs as needed), following the specialist-agent pattern.
## Repo: `guardkit/jarvis`
## Instruction to Claude in the next conversation: see §0 below.

---

## 0. Instruction for Claude (read this first)

**You are being given this document as input to produce phase-pair planning artefacts for the Jarvis repo**, following the exact pattern established in `specialist-agent/docs/research/ideas/`. This conversation starter contains the resolved scope, decisions, and feature breakdown — but **it is not itself a build plan**. Your job is to generate the proper pairs.

### Reference pattern (read these first — they are the template)

| File | Role |
|---|---|
| `/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/docs/research/ideas/phase1-output-quality-scope.md` | **Scope doc template.** Motivation, feature descriptions, changes-required, do-not-change list, success criteria, files-that-will-change table. Written as input to `/feature-spec`. |
| `/Users/richardwoollcott/Projects/appmilla_github/specialist-agent/docs/research/ideas/phase1-build-plan.md` | **Build plan template.** Status log, feature summary with dependencies, detailed per-feature change descriptions, exact GuardKit command sequence with full `--context` flags, risk mitigation, timeline, "after this phase" forward pointer. |

**Match the shape of these documents precisely.** Tone, section ordering, table formats, the status-log table, the command blocks with `--context` arrays, the Do-Not-Change section, the Files That Will Change table, the Expected Timeline table, the Risk Mitigation table, and the "After Phase N" forward pointer are all mandatory.

### What to produce

**Phase 1 first, in full:**

1. `/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/research/ideas/phase1-supervisor-scaffolding-scope.md`
2. `/Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/research/ideas/phase1-build-plan.md`

Phase 1 covers **FEAT-JARVIS-001 only** (Project Scaffolding, Supervisor Skeleton & Session Lifecycle). It's the foundation phase and deserves its own pair because every subsequent feature depends on it landing cleanly.

**After Phase 1, propose the phase grouping for the remaining v1 features** and confirm with Rich before generating Phase 2+ pairs. Suggested grouping to validate:

- **Phase 2 — Dispatch Foundations**: FEAT-JARVIS-002 (Core Tools + Dispatch Tools) + FEAT-JARVIS-003 (Async Subagents). Both depend only on 001; both are about giving the supervisor its dispatch vocabulary.
- **Phase 3 — Fleet Integration**: FEAT-JARVIS-004 (NATS Fleet Registration + Specialist Dispatch) + FEAT-JARVIS-005 (Build Queue Dispatch to Forge). Natural pairing — 004 establishes the fleet contract, 005 consumes it.
- **Phase 4 — Surfaces**: FEAT-JARVIS-006 (Telegram Adapter) + FEAT-JARVIS-007 (Skills + Memory Store). Both are user-facing surfaces rather than infrastructure.

Ask Rich whether this grouping is right before producing Phase 2+ docs. He may want finer or coarser slices.

### Inputs you should read before writing anything

1. **This document** — `jarvis-build-plan-conversation-starter.md` — for the resolved decisions, Q2/3/4/5/6/7 answers, feature descriptions, scope-preserving rules, and risk register.
2. **The two reference pattern files above** — the specialist-agent phase1 pair. Match their shape.
3. `jarvis/docs/research/ideas/jarvis-vision.md` v2 — the product vision.
4. `jarvis/docs/research/ideas/jarvis-architecture-conversation-starter.md` v2 — the `/system-arch` inputs (ADR-J-P1..P10, JA1-JA9 open questions).
5. `forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md` — the keystone fleet decision doc (D1-D46).
6. `forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md` — the trace schema Jarvis must honour from day one.
7. `forge/` — pattern reference. Forge's 30 ADRs + ARCHITECTURE.md + its own build-plan document if present.
8. `specialist-agent/docs/reviews/deepagents-sdk-2026-04.md` — justifies the DeepAgents 0.5.3 pin.
9. `jarvis/.guardkit/context-manifest.yaml` — the context manifest landed 19 April.
10. `jarvis/CLAUDE.md` (root) — the post-init project seed.

### Critical constraints to honour

- **`/system-arch` has NOT yet run.** Target: 21 April 2026. It produces `docs/architecture/ARCHITECTURE.md`, C4 diagrams, and ADR-J-001..N (including a DeepAgents pin ADR). Phase 1 scope + build plan will be written *assuming* those lands; the first step in the Phase 1 build plan's command sequence should be `/system-arch`, with the scope doc noting what it produces as input to the subsequent `/system-design` step.
- **`guardkit init` IS complete** (see §1.6 below for observed output). Python scaffolding (`src/`, `tests/`, `pyproject.toml`) did **not** land at init — this is correct; it's part of FEAT-JARVIS-001.
- **FEAT-JARVIS-008 (learning flywheel) is deferred to v1.5** per Q10.2. Do not include it in any v1 phase pair. When it returns, it gets its own phase pair.
- **FEAT-JARVIS-006 is Telegram-only** for v1 per Q10.3. CLI and Dashboard adapters move to v1.5 (FEAT-JARVIS-009) with their own phase pair.
- **DeepAgents `>=0.5.3,<0.6` pin** must be honoured in Phase 1's `pyproject.toml` subtask.
- **Trace richness from day one** per ADR-FLEET-001 — every `*_history` write uses the full schema starting at FEAT-JARVIS-004, even though the `jarvis.learning` reader defers to v1.5.
- **Scope-preserving rules in §2 apply** — no new agent repos until v1 ships, no fleet-decision changes mid-build, Rich-in-the-loop for learning.
- **Holding the line on D40, D45, ADR-ARCH-019 — see §7 watch-points.**

### Output format reminders (from specialist-agent pair)

- Each scope doc header: `## For: <what command consumes it>`, `## Date:`, `## Status:`, `## Context:`.
- Each build plan header: `## For: <purpose>`, `## Date:`, `## Status:`, `## Repo:`, `## Machine:`.
- Build plan must have a **Status Log** table, populated with the known events to date (`guardkit init` on 20 April, `/system-arch` target 21 April).
- Build plan must have a **GuardKit Command Sequence** with fully-spelled-out `--context` arrays for each `/feature-spec` and `/feature-plan` invocation — see specialist-agent's Step 1–Step 4 blocks for the exact shape.
- Build plan must have a **Do-Not-Change** section calling out fleet v3 decisions, scope-preserving rules, and the template-inherited patterns.
- Build plan must have a **Files That Will Change** table.
- Build plan must have an **Expected Timeline** table and an **After Phase N: What Comes Next** section.
- Scope doc must have a **Do-Not-Change** section, **Success Criteria** list, and a **Files That Will Change** table.

### Quality bar

Treat each phase pair as a production-quality planning artefact that Rich can hand to `/feature-spec` the next morning without further editing. The specialist-agent Phase 1 pair is the quality bar — match or exceed it.

---

## Target outcomes of this session:
1. ✅ Confirmed scope doc for Jarvis v1 (below, as revised 20 April)
2. ✅ Build plan (feature breakdown, prerequisites, sequencing) — patterned on Forge's
3. ✅ `guardkit init langchain-deepagents-orchestrator` executed (20 April morning)
4. **Next:** generate Phase 1 scope + build plan pair per the instruction in §0 above

## 20 April update — summary of decisions

- **Q10.2** — FEAT-JARVIS-008 (learning flywheel) deferred to v1.5. Trace-richness schema (ADR-FLEET-001) stays on from day one; the pattern detector + Rich-in-the-loop CLI defer.
- **Q10.3** — Adapters narrowed: **Telegram only** for v1. CLI and Dashboard adapters move to v1.5 (FEAT-JARVIS-009).
- **Q10.5** — `talk-prep` Pattern C ambient slot reserved. `jarvis.skills.talk_prep` scaffolded as a module in FEAT-JARVIS-007; ambient nudge logic lands in v1.5 (FEAT-JARVIS-010).
- **Q10.4** — `jarvis.learning` stays a module, not a separate DeepAgent. D45 holds.
- **Q10.6** — First real FEAT-JARVIS-005 test case: a genuinely useful Jarvis internal improvement, not a canned `hello-world`.
- **Q10.7** — `jarvis purge-traces` CLI defers to v1.1.
- **Scaffolding reframed as a feature.** The original §11 "Step 4 — pin bump" presupposed that `guardkit init` rendered `requirements.txt` / `pyproject.toml`. It didn't — the template's pattern layer (20 scaffold files) is consumed by AutoBuild, not at init time. So `pyproject.toml` creation, Python `src/` layout, CLI entrypoint, and the DeepAgents `>=0.5.3,<0.6` pin all move **inside FEAT-JARVIS-001** and land via the proper `/system-design → /feature-spec → /feature-plan → AutoBuild` pipeline. The pin bump is no longer a standalone prerequisite — it is an architectural decision recorded by tomorrow's `/system-arch` and implemented as a subtask of FEAT-JARVIS-001.
- **Revised v1 timeline:** ~11–12 working days (down from 15), reflecting -008 deferral and the adapter narrowing.

---

## Framing

Per fleet v3 (19 April 2026), Jarvis is a **General Purpose DeepAgent with dispatch tools** — the attended surface of a three-surface fleet on one NATS/Graphiti/adapter/DeepAgents-0.5.3 substrate. This is the "Tony Stark v1 mini-Jarvis" aesthetic made architectural.

**One-sentence thesis:** *One reasoning model that knows which reasoning model to use.*

This document covers the build — not the architecture. Architecture is settled across:
- `forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md` (keystone)
- `jarvis/docs/research/ideas/jarvis-vision.md` v2 (Jarvis-specific vision)
- `jarvis/docs/research/ideas/jarvis-architecture-conversation-starter.md` v2 (inputs for `/system-arch`)
- `forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md` (trace schema commitment)

Tomorrow's `/system-arch` on Jarvis (21 April) will produce `ARCHITECTURE.md`, C4 diagrams, and ADR-J-P1..P10. This build plan assumes those land and feature work follows.

---

## 1. Template Decision

**Use `langchain-deepagents-orchestrator`.**

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
guardkit init langchain-deepagents-orchestrator \
  --project-name jarvis \
  --interactive
```

### Why this template, not the others

| Template | Fit for Jarvis? | Reason |
|---|---|---|
| **`langchain-deepagents-orchestrator`** | ✅ **Chosen** | Two-model orchestration (reasoning supervises + implementation executes), subagent composition, domain prompt injection, factory function agents, config-driven model selection, defensive fallback chain. Maps exactly onto supervisor + four async subagents (`deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`). |
| `langchain-deepagents` | ❌ | Binary Player-Coach adversarial cooperation. Jarvis is *not* adversarial — it's a reasoning dispatcher. Wrong shape; we'd fight it. |
| `langchain-deepagents-weighted-evaluation` | ❌ | Specialist-agent's template (extends adversarial with weighted scoring). Wrong shape for Jarvis — same reason as above. |
| `nats-asyncio-service` | ❌ | FastStream pub/sub. Great for adapters (we'll use it as a *pattern* for NATS adapter modules), but wrong centre of gravity for the whole repo. |
| `fastmcp-python` | ❌ | MCP server template. Jarvis's MCP needs are consumer-side (DeepAgents' `langchain-mcp-adapters`), not server-side. |
| `python-library` | ❌ | Too generic; we'd re-derive everything the orchestrator template gives us. |
| `default` | ❌ | Minimal starter; wastes the work already proven by the orchestrator template. |

### Bundled specialist agents (what `guardkit init` gives us)

The orchestrator template ships with seven specialist agents under `.claude/agents/`:

- `deepagents-orchestrator-specialist` — orchestrator patterns
- `subagent-composition-specialist` — how to compose subagents (async + sync mix)
- `domain-context-injection-specialist` — prompt injection / context framing
- `langchain-tool-decorator-specialist` — `@tool` boundary patterns
- `langgraph-deployment-config-specialist` — LangGraph deployment config
- `pytest-agent-testing-specialist` — agent testing patterns
- `system-prompt-template-specialist` — system prompt authoring

These map 1:1 onto the patterns Jarvis vision v2 §8 and the `/system-arch` conversation-starter v2 §11 call out. No adaptation needed — we'll lean on them during feature builds.

### Known caveat

The template's `manifest.json` lists `production_ready: false, learning_resource: true, reference_implementation: true, confidence_score: 85.0`. Interpretation: it's the *closest fit* but Jarvis may be the first production user. Same relationship Forge and specialist-agent had with their templates — expect to contribute improvements back. Acceptable trade-off.

### DeepAgents pin requirement (handled inside FEAT-JARVIS-001)

The template's `manifest.json` pins `deepagents >= 0.4.11`. Per the specialist-agent SDK review (`specialist-agent/docs/reviews/deepagents-sdk-2026-04.md`), the latest stable is 0.5.3 (15 April 2026), which includes **`AsyncSubAgentMiddleware`** — the preview feature that makes Jarvis's four-subagent dispatch work naturally.

**20 April correction:** `guardkit init` does not render `requirements.txt` / `pyproject.toml` at init time (the 20 pattern-layer scaffold files are consumed by AutoBuild). So there is no file to "bump" today. Instead:

1. Tomorrow's `/system-arch` records the `deepagents >= 0.5.3, < 0.6` pin as an ADR (likely ADR-J-001 or similar) — an architectural constraint, not a side-note.
2. FEAT-JARVIS-001 creates `pyproject.toml` with the correct pin as part of its scaffolding subtasks.
3. Same pattern as Forge and Study Tutor — pin lives in the feature that creates the dependency file, not in a separate pre-commit step.

This reframing is documented in the 20 April update block at the top of this document.

### Post-`init` pre-existing content preserved (20 April — confirmed)

The Jarvis repo contains (all preserved through init):

- `docs/research/ideas/` — vision v2, conversation-starter v2, general-purpose-agent, nemoclaw-assessment, reachy-mini-integration (kept)
- `docs/product/architect-greenfield/architecture.md` — from an earlier architect-greenfield run (pre-fleet-v3). **Flag as superseded** once tomorrow's `/system-arch` lands; don't delete yet (useful evidence of how the framing shifted).
- `docs/product/po-extract/` and `docs/product/gpa-idea/` — 30 PO extract outputs and 7 gpa-idea outputs. **Valuable raw material** — treat as feature-spec input candidates when we reach `/feature-spec`.
- `.guardkit/context-manifest.yaml` — landed 19 April (fleet v3 session), references nats-core, forge, specialist-agent, nats-infrastructure, guardkit.
- `tasks/` — currently empty; populated by this build plan.

### What `guardkit init` actually landed (20 April)

Observed output:

- `.claude/` — 14 agent files (7 orchestrator specialists × base + ext), 15 rule files, `CLAUDE.md`, `commands/`, `manifest.json`, `rules/`, `task-plans/`
- `.guardkit/.mcp.json` — MCP config
- `.guardkit/graphiti.yaml` — copied from `agentic-dataset-factory`, `project_id=jarvis`
- `CLAUDE.md` (repo root) — seeded with project purpose, Python stack, LangChain DeepAgents SDK
- **No** `src/`, `tests/`, `pyproject.toml`, `requirements.txt` — the pattern layer's 20 scaffold files are deferred to AutoBuild / `guardkit render` (per the init tip).
- Graphiti seeding skipped (`GOOGLE_API_KEY` not set); Graphiti seeding is opt-in and can be revisited later.

Existing `docs/research/` and `docs/product/` trees were not disturbed.

---

## 2. v1 Scope — What Ships

Mirrors fleet v3 §8 ("Jarvis v1") exactly. Re-stating here so this document stands alone.

### Hard scope (ships in v1)

| Element | Scope |
|---|---|
| **Supervisor** | One DeepAgent instance. Single-process, single-container, thread-per-session (where a session = adapter + user + time window). |
| **Async subagents** | Four at launch: `deep_reasoner` (Gemini 3.1 Pro), `adversarial_critic` (Claude Opus 4.7), `long_research` (GPT-5.4), `quick_local` (vLLM Qwen3-Coder-Next on GB10). Descriptions include cost + latency signals; supervisor defaults cheapest-that-fits, escalates on need. |
| **NATS dispatch targets** | Three at launch: `architect-agent`, `product-owner-agent`, `forge`. Other specialist-agent roles auto-appear via CAN-bus when registered. |
| **Build-queue dispatch** | One pattern: publish `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per Forge ADR-SP-014 Pattern A. |
| **Adapters** | Three at launch: Telegram (quickest feedback loop), CLI-wrapper, Dashboard. Reachy voice arrives with the hardware. Each an `nats-asyncio-service`-patterned module. |
| **Skills** | Three at launch: `morning-briefing`, `talk-prep` (DDD progress tracker), `project-status` (query fleet state). |
| **Ambient behaviour** | Pattern A (reactive) always on. Pattern B (triggered watchers) available via opt-in. Pattern C (volitional) as *one* opt-in skill (`morning-briefing`) — per D44. |
| **Learning flywheel** | `jarvis_routing_history` and `jarvis_ambient_history` Graphiti groups. Trace-rich schema per ADR-FLEET-001 from day one. `jarvis.learning` module (pattern detector; not a separate agent per D45). |
| **MCP support** | Via DeepAgents' `langchain-mcp-adapters`. No `jarvis-mcp` adapter repo needed. |
| **Memory Store** | DeepAgents 0.5.3 Memory Store for cross-session recall. |

### Explicitly out of scope for v1 (deferred)

| Deferred item | Revisit condition |
|---|---|
| Meta-agent / task-agent split (D45) | After 6 months of real runs, if `jarvis.learning` quality insufficient |
| Harness auto-rewriting (D45) | Not v1, not v2 unless full conditions in fleet v3 §7 met |
| Pattern C always-on ambient (D44) | When one opt-in skill proves it earns its place |
| HTTP transport for async subagents | When a subagent needs independent compute/scaling |
| NemoClaw integration (D46) | When GitHub issues #341/#415/#878 resolved + NIM stable + driver 590 shipped |
| Context7 integration as first-class Jarvis tool | When other v1 work is proven |
| Supervisor-per-adapter architecture | Rejected by v2 design; not revisiting |
| `jarvis-mcp` adapter repo | Rejected — DeepAgents native MCP handles this |

### Scope-preserving rules

- **No new agent repos until v1 ships.** All specialist-agent roles stay in `specialist-agent`. Forge stays in `forge`.
- **No changes to fleet v3 decisions D1-D46 mid-build.** If a build-time finding challenges one, stop and run a fleet-level decision round first.
- **Trace-richness from day one.** No "we'll add traces later" — ADR-FLEET-001 is a hard constraint on every `*_history` write.
- **Rich-in-the-loop for learning.** `jarvis.learning` proposes `CalibrationAdjustment` entities; Rich confirms via CLI; same pattern as Forge ADR-ARCH-005/006.

---

## 3. Prerequisites

### Hard prerequisites (blocking — can't start FEAT-JARVIS-001)

- [ ] **`/system-arch` complete.** Produces `docs/architecture/ARCHITECTURE.md`, C4 diagrams, ADR-J-001..N (including the DeepAgents 0.5.3 pin ADR). Without this, feature IDs and acceptance criteria are ungrounded. **Target: 21 April 2026.**
- [x] **`guardkit init langchain-deepagents-orchestrator` executed.** Landed 20 April. `.claude/` agents/rules, `CLAUDE.md`, `.guardkit/graphiti.yaml` present. Python scaffold deferred to FEAT-JARVIS-001 per the reframing above.
- [x] **nats-core library.** 98% coverage, shipping. Contains `AgentManifest`, `CommandPayload`, `ResultPayload`, `BuildQueuedPayload`, `NotificationPayload`, `NATSKVManifestRegistry`. Used by Forge and specialist-agent in production.
- [x] **Fleet-wide ADR-FLEET-001 landed.** Trace-richness schema committed. Defines what Jarvis must capture per decision.
- [x] **`.guardkit/context-manifest.yaml` in Jarvis repo.** References nats-core, forge, specialist-agent, nats-infrastructure, guardkit. Landed 19 April.

*Removed from prerequisites:* "DeepAgents pin bumped to `>=0.5.3, <0.6`" — this is no longer a pre-feature step; it is implemented inside FEAT-JARVIS-001 as a scaffolding subtask, informed by the pin ADR from `/system-arch`.

### Soft prerequisites (valuable but not blocking)

- [ ] **nats-infrastructure running on GB10** — needed end-to-end but Jarvis can develop against an in-process `nats-py` test server initially.
- [ ] **specialist-agent Phase 3 (NATS fleet integration) complete** — needed for real dispatch; Jarvis can mock in early features.
- [x] **Forge shipping** — 30 ADRs + ARCHITECTURE.md, 18 April. Forge ADR-ARCH-031 (async subagents amendment) landed 19 April. Forge is the template pattern Jarvis mirrors.
- [ ] **Study Tutor runnable** — not required for Jarvis v1, but useful as a third reference DeepAgent surface for trace-richness schema validation.

### Context documents for `/system-arch` and beyond

Already-enumerated in `jarvis-architecture-conversation-starter.md` v2 §13. Summarised:

| Document | Used in |
|---|---|
| `fleet-architecture-v3-coherence-via-flywheel.md` | All |
| `jarvis-vision.md` v2 | All |
| `jarvis-architecture-conversation-starter.md` v2 | `/system-arch` specifically |
| `ADR-FLEET-001-trace-richness.md` | `/system-arch`, FEAT-JARVIS-007 (flywheel) |
| Forge `ARCHITECTURE.md` + 30 ADRs | All (pattern reference) |
| Forge `ADR-ARCH-031` | FEAT-JARVIS-003 (async subagents) |
| DeepAgents 0.5.3 async-subagents docs | FEAT-JARVIS-003 |
| `general-purpose-agent.md` | FEAT-JARVIS-002 (tools) |
| `reachy-mini-integration.md` | Future adapter; inform voice-adapter design early |
| `nemoclaw-assessment.md` | FEAT-JARVIS-008 hook design |

---

## 4. Feature Breakdown — FEAT-JARVIS-001..007 (v1)

Patterned on Forge's FEAT-FORGE-001..007. Each feature ≈ 2-4 days, suitable for AutoBuild per feature with `/task-review` gates. FEAT-JARVIS-008 (learning flywheel) is deferred to v1.5 per the 20 April update.

| # | Feature | Depends On | Est. | Purpose |
|---|---|---|---|---|
| **FEAT-JARVIS-001** | Project Scaffolding, Supervisor Skeleton & Session Lifecycle | — | 3-4 days | **Includes all Python scaffolding** — `pyproject.toml` with `deepagents>=0.5.3,<0.6` pin, `src/{agents,tools,prompts,config,infrastructure,shared}/` layer structure per template, `tests/` layout, ruff config. DeepAgent supervisor via `create_deep_agent()` (or `create_agent()` per `/system-arch` outcome). Session type, thread-per-session model, Memory Store integration, startup/shutdown lifecycle. `jarvis` CLI entrypoint. Smoke test: supervisor answers a trivial question via CLI. |
| **FEAT-JARVIS-002** | Core Tools & Capability-Driven Dispatch Tools | 001 | 2-3 days | Non-dispatch tools (file read, web search, calendar stub, calculator), dispatch tools (`call_specialist`, `queue_build`), capability catalogue reader reading from `nats-core` KV manifest registry. Same pattern as Forge ADR-ARCH-015/016. Smoke test: supervisor lists available capabilities and picks correctly for three canned prompts. |
| **FEAT-JARVIS-003** | Async Subagents for Model Routing | 001 | 2-3 days | Four `AsyncSubAgent` instances at startup: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`. ASGI transport (per Forge ADR-ARCH-031 precedent). Cost + latency signals in descriptions. Supervisor dispatches to subagents via `start_async_task`/`check_async_task`. Smoke test: each subagent callable; supervisor picks `quick_local` for a trivial lookup and `deep_reasoner` for a reasoning task. |
| **FEAT-JARVIS-004** | NATS Fleet Registration & Specialist Dispatch | 002 | 2-3 days | Jarvis registers on `fleet.register` with `AgentManifest`. `NATSKVManifestRegistry` discovers specialist-agent fleet. `call_specialist` tool issues `agents.command.{agent_id}` and awaits `agents.result.{agent_id}`. Timeout handling, retry with redirect. Smoke test: Jarvis dispatches to a running `specialist-agent --role architect` and receives `ResultPayload` with Coach score. |
| **FEAT-JARVIS-005** | Build Queue Dispatch (Jarvis → Forge) | 004 | 1-2 days | `queue_build` tool publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per ADR-SP-014 Pattern A. No await; fire-and-forget pattern. Notification channel for Forge progress updates (`pipeline.stage-complete.*`). Smoke test: Jarvis queues a genuinely useful Jarvis internal improvement (per Q10.6), Forge consumer picks it up, Jarvis receives stage-complete notifications. |
| **FEAT-JARVIS-006** | Telegram Adapter | 001 | 1-2 days | **Telegram only for v1** (per Q10.3). `nats-asyncio-service`-patterned module publishing `jarvis.command.*` / subscribing `jarvis.notification.*`. Adapter ↔ session correlation via session_id in payload. Smoke test: Telegram adapter round-trips a "hello" to Jarvis. CLI and Dashboard adapters move to FEAT-JARVIS-009 (v1.5). |
| **FEAT-JARVIS-007** | Skills & Memory Store | 001 | 2-3 days | Three launch skills: `morning-briefing`, `talk-prep`, `project-status`. Each a composable tool unit callable via command pattern (`/skill morning-briefing`) or via natural language dispatch. **`talk-prep` module scaffolded with a reserved slot for Pattern C ambient nudges** (per Q10.5); v1 ships the command-pattern form only, ambient logic lands in FEAT-JARVIS-010. Memory Store holds cross-session state. Smoke test: each skill produces plausible output; Memory Store recalls a fact from a prior session. |
| ~~**FEAT-JARVIS-008**~~ | ~~Learning Flywheel~~ | — | — | **Deferred to v1.5** (per Q10.2). Trace-richness writes (ADR-FLEET-001 schema) still populate from day one — every `*_history` write uses the full schema — so no data is lost. What defers: the `jarvis.learning` pattern detector module, the `CalibrationAdjustment` Graphiti entity, and the Rich-in-the-loop CLI for confirm/reject. |

### v1.5 features (post-attended-dispatch-ships)

- **FEAT-JARVIS-008 (moved)**: Learning Flywheel — `jarvis.learning` + Graphiti calibration loop. Re-enters when v1 has shipped and real routing history exists to learn from.
- **FEAT-JARVIS-009**: CLI + Dashboard adapters — the two adapters deferred from FEAT-JARVIS-006 per Q10.3.
- **FEAT-JARVIS-010**: `talk-prep` Pattern C ambient nudges — volitional behaviour targeting DDD Southwest (16 May) prep.
- **FEAT-JARVIS-011**: `jarvis purge-traces` CLI — GDPR-clean per ADR-FLEET-001, deferred from v1 per Q10.7.

### Further-post-v1 features (noted for reference)

- Ambient Pattern B watcher — one proven candidate ("Forge queue completion nudge").
- Reachy Mini voice adapter — when hardware lands.
- Second cohort of async subagents if the original four prove insufficient.
- Context7 integration as a first-class Jarvis tool.

---

## 5. Full Build Pipeline (Forge-style)

Once `/system-arch` lands (21 April) and `guardkit init` is done (✅ 20 April), the pipeline is:

```
[done]     guardkit init    → .claude/, CLAUDE.md, .guardkit/graphiti.yaml (Python scaffold deferred to FEAT-JARVIS-001)
[pending]  /system-arch     → docs/architecture/ARCHITECTURE.md + C4 + ADR-J-001..N (21 April)
[then]     /system-design   → per-feature design docs (7 × FEAT-JARVIS-00N design.md)
           /feature-spec    → per-feature gherkin scenarios (7 × FEAT-JARVIS-00N_summary.md)
           /feature-plan    → per-feature task decomposition (7 × FEAT-JARVIS-00N build plan,
                              mirroring Study Tutor's FEAT-PO-002 output shape)
           autobuild        → per-feature implementation (7 × AutoBuild runs)
           /task-review     → gates as needed per feature complexity
```

### Batch or sequential?

**Sequential, not batched.** Reasoning:

- FEAT-JARVIS-001 establishes the supervisor skeleton (and all Python scaffolding per §4); every subsequent feature depends on it.
- FEAT-JARVIS-002 and -003 are parallel candidates (both depend only on 001) but Forge's experience shows **sequential with AutoBuild** is faster in practice than juggling parallel AutoBuild runs.
- Adapters (006 Telegram-only) and skills (007) depend only on 001; they can slot in wherever makes sense.
- FEAT-JARVIS-008 (learning) is deferred to v1.5; it would have depended on 004 (NATS integration) if retained.
### Suggested ordering (v1 — revised 20 April)

```
Day 0 (20 Apr):  guardkit init ✅ (done) + init commit
Day 1 (21 Apr):  /system-arch → ARCHITECTURE.md, C4, ADR-J-001..N (incl. DeepAgents pin ADR)
Day 2-4:         FEAT-JARVIS-001 (/system-design → /feature-spec → /feature-plan → autobuild → /task-review)
                 — includes pyproject.toml, src/ scaffolding, pin, CLI entrypoint, supervisor
Day 5-6:         FEAT-JARVIS-002 (core tools + dispatch tools)
Day 7-8:         FEAT-JARVIS-003 (async subagents — the hardest)
Day 9-10:        FEAT-JARVIS-004 (NATS fleet integration)
Day 10-11:       FEAT-JARVIS-005 (build queue — small)
Day 11-12:       FEAT-JARVIS-006 (Telegram adapter only)
Day 12-13:       FEAT-JARVIS-007 (skills + Memory Store)
```

Total: ~11–12 working days for v1 (down from 15). Saved by deferring -008 (learning) and narrowing -006 to Telegram-only. Realistic given testing plus interruptions.

---

## 6. AutoBuild Considerations

Forge's experience (30 ADRs, 6 features via AutoBuild) informs:

- **Per-feature AutoBuild, not per-task.** AutoBuild runs a whole feature's task list overnight, not a single task. Expect ~90 minutes per feature.
- **`/task-review` after each feature, not after each task.** Review once at the gate, not per sub-task. Keeps signal-to-noise high.
- **Context manifests are populated and ready.** `.guardkit/context-manifest.yaml` already landed.
- **Trace richness on by default from day one.** ADR-FLEET-001 schema is used by every `*_history` write starting with FEAT-JARVIS-004 (which introduces routing dispatch) — even though the `jarvis.learning` *reader* is deferred to v1.5 (FEAT-JARVIS-008). This is non-negotiable per the scope-preserving rules in §2; no "we'll add traces later".
- **Three-Layer Build Defence applies.** Layer 1 (prevention via better plans + Graphiti context), Layer 2 (recovery via Player-Coach loop), Layer 3 (assisted resolution via specialist resolver agents). Same as Forge.

---

## 7. Relationship to Tomorrow's `/system-arch`

Tomorrow's session produces Jarvis's architecture documents. This build plan is *written for those outputs to land_cleanly*. Specifically:

- FEAT-JARVIS-001..007 are **tentative feature IDs** — `/system-arch` may adjust numbering or rename. Acceptable. (008 is deferred to v1.5 per the 20 April update.)
- ADR-J-P1..P10 named in `jarvis-architecture-conversation-starter.md` v2 become real ADR-J-001..N. Acceptable drift.
- JA1-JA9 open questions in the conversation-starter will resolve in `/system-arch` — particularly JA1 (schema fields for `jarvis_routing_history`), JA6 (`quick_local` fallback under GB10 pressure), and JA3 (cross-adapter handoff semantics).
- Anything `/system-arch` uncovers that this build plan doesn't anticipate → update this document after the session.

### Watch-points for `/system-arch`

Reminder from the fleet v3 conversation capture (notes for tomorrow):

- Model might re-open D11 (intent classification) or D12 (GPA location) — both resolved by D40. Hold the line.
- Model might propose meta-agent split — D45 deferred. Hold the line.
- Model might propose static gate/threshold config — ADR-ARCH-019 inherited. Hold the line.
- Model might propose polling for Jarvis status — redirect to `list_async_tasks`.

---

## 8. Risk Register

| Risk | Mitigation |
|---|---|
| `/system-arch` reveals gaps this build plan didn't anticipate | Update this doc between `/system-arch` and first `/system-design`. Not starting AutoBuild until the plan matches arch outputs. |
| DeepAgents 0.5.3 `AsyncSubAgentMiddleware` preview-feature instability | Accept. Fallback: sync `task()` dispatch, single-model degraded mode. Record in ADR-J-XXX at `/system-arch`. |
| nats-infrastructure on GB10 not running when FEAT-JARVIS-004 starts | In-process nats-py test server acceptable for dev; deferred for end-to-end test. |
| Four subagents triggering rate limits or cost spikes during dev | `quick_local` (GB10 vLLM) is the default; remote subagents gated by supervisor reasoning. Per-day spend cap in dev. |
| Learning module (008) proposing bad adjustments early | Rich-in-the-loop gate; `CalibrationAdjustment` entities only persist on confirm. Same pattern as Forge's proven ADR-ARCH-005/006. |
| Adapters (006) turning into a rabbit-hole | Scope discipline: v1 is **Telegram only** (per Q10.3), `nats-asyncio-service`-patterned, no fancy UX. CLI and Dashboard defer to v1.5 (FEAT-JARVIS-009). |

---

## 9. Decisions From The 19–20 April Conversation (resolved)

1. ✅ **Template choice** — `langchain-deepagents-orchestrator` confirmed. Sanity-checked against template source tree; layer mapping and seven specialists match Jarvis's needs.
2. ✅ **`guardkit init` timing** — executed 20 April morning, before `/system-arch`. Gives tomorrow's session more context to work with.
3. ✅ **Feature ordering** — as per §5 revised. Sequential, not batched. FEAT-JARVIS-001 first (now includes scaffolding).
4. ✅ **Day-1 scope** — `guardkit init` + commit + stop. The original "pin bump" step is absorbed into FEAT-JARVIS-001 (see reframing at top of document).
5. ✅ **v1 scope tightened** — Telegram-only adapter (Q10.3); -008 learning deferred to v1.5 (Q10.2); `talk-prep` Pattern C slot reserved (Q10.5); purge-traces deferred to v1.1 (Q10.7); `jarvis.learning` stays a module not an agent (Q10.4); FEAT-JARVIS-005 test case is a genuinely useful Jarvis internal improvement (Q10.6).

---

## 10. Starter Questions For This Conversation

1. Is the `langchain-deepagents-orchestrator` choice confidently right, or do you want to check the template's source tree against Jarvis's needs before committing?

2. Does 15 working days feel right for v1, or should we scope down (drop -008 learning to v1.5) to ship attended-dispatch sooner?

3. For adapters (FEAT-JARVIS-006), do all three ship in v1, or just Telegram first (fastest feedback loop, per vision v2 §7)?

4. `jarvis.learning` is currently scoped as a module, not a separate DeepAgent (per D45). Confirm we're holding that line — even though the self-improving-harness work in specialist-agent is closer to the meta-agent split pattern?

5. Pattern C ambient — only `morning-briefing` as opt-in skill in v1? Or do you want to pre-register a slot for `talk-prep` ambient nudges as DDD Southwest approaches (16 May)?

6. What's the right first real test case for FEAT-JARVIS-005 (Jarvis→Forge build queue)? A canned `hello-world` feature, or something genuinely useful like "queue a Jarvis internal improvement"?

7. Do we want `jarvis purge-traces` CLI from day one (GDPR-clean per ADR-FLEET-001), or defer to v1.1?

---

## 11. Commands Run / To Run

### ✅ Executed 20 April 2026

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
git status                                   # clean on main
ls .guardkit/                                 # context-manifest.yaml present

guardkit init langchain-deepagents-orchestrator \
  --project-name jarvis \
  --interactive
# Landed: .claude/ (14 agents, 15 rules, CLAUDE.md, commands, manifest, rules, task-plans),
#         .guardkit/.mcp.json, .guardkit/graphiti.yaml, CLAUDE.md (root)
# Deferred to FEAT-JARVIS-001: src/, tests/, pyproject.toml
# Graphiti seeding skipped (GOOGLE_API_KEY not set — can seed later)
```

### Still to run — 20 April (end of day)

```bash
# Commit the init output (and the 20 April edits to this conversation starter)
git add -A
git commit -m "chore: guardkit init with langchain-deepagents-orchestrator template

- Seven orchestrator specialist agents under .claude/agents/ (14 files incl. ext)
- 15 rules and CLAUDE.md seeded with project purpose and DeepAgents SDK stack
- Graphiti config copied from agentic-dataset-factory; seeding deferred
  (GOOGLE_API_KEY not set; can revisit later)
- Python scaffolding (src/, tests/, pyproject.toml) and DeepAgents pin bump
  to >=0.5.3,<0.6 deferred to FEAT-JARVIS-001 (Phase 1)
- Conversation starter updated to instruct generation of phase pair docs
  (per specialist-agent pattern) as the next-conversation brief"
```

### Next conversation — generate Phase 1 pair (see §0)

Open a fresh Claude Code conversation in the `jarvis/` repo and reference **this document** plus the two specialist-agent template files. Claude will produce:

- `docs/research/ideas/phase1-supervisor-scaffolding-scope.md`
- `docs/research/ideas/phase1-build-plan.md`

Both structured to match the specialist-agent Phase 1 pair exactly. The Phase 1 build plan's command sequence will begin with `/system-arch` (target 21 April), followed by `/system-design FEAT-JARVIS-001 → /feature-spec FEAT-JARVIS-001 → /feature-plan FEAT-JARVIS-001 → AutoBuild → /task-review`.

Once Rich confirms the Phase 1 pair is good, Claude will propose the grouping for Phase 2–4 (covering FEAT-JARVIS-002..007) and generate those pairs on confirmation.

### Tomorrow — 21 April 2026: `/system-arch` (invoked from Phase 1 build plan)

The actual `/system-arch` invocation will be spelled out in the Phase 1 build plan's GuardKit Command Sequence (Step 1), with full `--context` flags matching the specialist-agent pattern. Something along these lines:

```bash
/system-arch "Jarvis: General Purpose DeepAgent with dispatch tools" \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-build-plan-conversation-starter.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md
```

The exact form (context ordering, any additional references to Forge ADRs) is for the Phase 1 build plan to finalise.

---

## 12. Done-Definition for This Conversation (20 April close)

The conversation is done when:

- [x] `guardkit init langchain-deepagents-orchestrator` executed in `jarvis/` repo
- [x] Build plan (§4 feature breakdown) revised — -008 deferred, -006 Telegram-only, scaffolding absorbed into -001
- [x] Day-by-day ordering (§5) revised — ~11–12 days, scaffolding inside FEAT-JARVIS-001
- [x] Starter questions 1–7 answered (Q2/3/5 by user, Q4/6/7 by recommendation; all recorded in the 20 April update block)
- [x] This conversation starter updated with answers
- [x] Conversation starter rewritten at §0 to instruct Claude (in the next conversation) to generate the Phase 1 scope + build plan pair following the specialist-agent template
- [ ] First commit on Jarvis repo landed (the init output + this conversation-starter update)

*Open for next session:* Phase 1 pair generation per §0, then `/system-arch` on 21 April invoked from the Phase 1 build plan's Step 1.

---

## 13. Source Documents

| Document | Contribution |
|---|---|
| `jarvis-vision.md` v2 (19 April 2026) | Jarvis's v2 framing, three delegation targets, four launch subagents, selectively ambient |
| `jarvis-architecture-conversation-starter.md` v2 (19 April 2026) | `/system-arch` inputs, ADR-J-P1..P10, JA1-JA9 open questions |
| `fleet-architecture-v3-coherence-via-flywheel.md` (forge, 19 April 2026) | Three surfaces, one substrate, flywheel-via-calibration-loop, v1 scope discipline |
| `ADR-FLEET-001-trace-richness.md` (forge, 19 April 2026) | Trace schema Jarvis must implement from day one |
| Forge `ARCHITECTURE.md` + 30 ADRs (18 April 2026) | Pattern reference — Jarvis mirrors Forge's modular structure |
| Forge `ADR-ARCH-031` (19 April 2026) | Async subagents precedent for FEAT-JARVIS-003 |
| `specialist-agent/docs/reviews/deepagents-sdk-2026-04.md` (19 April 2026) | DeepAgents 0.5.3 stability and features — justifies pin bump |
| `forge/docs/research/ideas/forge-build-plan.md` | Pattern for this document |
| `guardkit/installer/core/templates/langchain-deepagents-orchestrator/manifest.json` | Template choice rationale |

---

## 14. Parting Thought

Jarvis is the only one of the three surfaces that's **attended by default**. Forge runs while Rich is elsewhere; Study Tutor runs for a student; Jarvis runs *with* Rich in the loop, as his ambient intelligence. That changes how we think about feature sequencing: FEAT-JARVIS-001 isn't about batch correctness like Forge's pipeline state machine — it's about "Rich can have a useful conversation with it on day 1, even if it can't dispatch to anything yet."

That's the shape of the v1 success criterion: a useful conversation before anything fancy works.

Everything else is compounding on that baseline.

---

*"One reasoning model that knows which reasoning model to use."*

*Jarvis build-out conversation starter · 19 April 2026*
