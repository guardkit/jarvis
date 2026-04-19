# Conversation Starter: Jarvis Build-Out — Scope, Build Plan, `guardkit init`

## Date: 19 April 2026
## Status: Ready — scopes today's build-planning session, assumes tomorrow's `/system-arch` lands as planned
## Repo: `guardkit/jarvis`
## Target outcomes of this session:
1. Confirmed scope doc for Jarvis v1
2. Build plan (feature breakdown, prerequisites, sequencing) — patterned on Forge's
3. Decided `guardkit init` invocation, ready to run
4. Known open questions parked for tomorrow's `/system-arch` or later sessions

---

## Framing

Per fleet v3 (19 April 2026), Jarvis is a **General Purpose DeepAgent with dispatch tools** — the attended surface of a three-surface fleet on one NATS/Graphiti/adapter/DeepAgents-0.5.3 substrate. This is the "Tony Stark v1 mini-Jarvis" aesthetic made architectural.

**One-sentence thesis:** *One reasoning model that knows which reasoning model to use.*

This document covers the build — not the architecture. Architecture is settled across:
- `forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md` (keystone)
- `jarvis/docs/research/ideas/jarvis-vision.md` v2 (Jarvis-specific vision)
- `jarvis/docs/research/ideas/jarvis-architecture-conversation-starter.md` v2 (inputs for `/system-arch`)
- `forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md` (trace schema commitment)

Tomorrow's `/system-arch` on Jarvis (20 April) will produce `ARCHITECTURE.md`, C4 diagrams, and ADR-J-P1..P10. This build plan assumes those land and feature work follows.

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

### Post-`init` pin bump (required)

The template is pinned `deepagents >= 0.4.11`. Per the specialist-agent SDK review (`specialist-agent/docs/reviews/deepagents-sdk-2026-04.md`), the latest stable is 0.5.3 (15 April 2026), which includes **`AsyncSubAgentMiddleware`** — the preview feature that makes Jarvis's four-subagent dispatch work naturally.

**First commit after `guardkit init`**: bump `requirements.txt` and `pyproject.toml` to `deepagents >= 0.5.3, < 0.6`, matching Forge and Study Tutor. Record this decision in-repo (ADR-J-001 or as a note under `docs/architecture/`).

### Post-`init` pre-existing content to preserve

The Jarvis repo already contains:

- `docs/research/ideas/` — vision v2, conversation-starter v2, general-purpose-agent, nemoclaw-assessment, reachy-mini-integration (keep all)
- `docs/product/architect-greenfield/architecture.md` — from an earlier architect-greenfield run (pre-fleet-v3). **Flag as superseded** once tomorrow's `/system-arch` lands; don't delete yet (it's useful evidence of how the framing shifted).
- `docs/product/po-extract/` and `docs/product/gpa-idea/` — 30 PO extract outputs and 7 gpa-idea outputs. **Valuable raw material** — treat as feature-spec input candidates when we reach `/feature-spec`.
- `.guardkit/context-manifest.yaml` — already landed (fleet v3 session), references nats-core, forge, specialist-agent, nats-infrastructure, guardkit.
- `tasks/` — currently empty; populated by this build plan.

The `guardkit init` command will add `.claude/`, `agents/`, `manifest.json`, `settings.json`, and template scaffolds under `src/`, `tests/`, `docs/`. Existing `docs/research/` and `docs/product/` will be merged, not overwritten (per the template resolver's skip logic).

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

- [ ] **Tomorrow's `/system-arch` complete.** Produces `docs/architecture/ARCHITECTURE.md`, C4 diagrams, ADR-J-P1..P10. Without this, feature IDs and acceptance criteria are ungrounded. **Target: 20 April 2026.**
- [ ] **`guardkit init langchain-deepagents-orchestrator` executed.** Scaffolds `src/`, `tests/`, `.claude/`, `manifest.json`. Baseline commit before feature work.
- [ ] **DeepAgents pin bumped to `>=0.5.3, <0.6`.** Required for `AsyncSubAgentMiddleware`. First post-init commit.
- [x] **nats-core library.** 98% coverage, shipping. Contains `AgentManifest`, `CommandPayload`, `ResultPayload`, `BuildQueuedPayload`, `NotificationPayload`, `NATSKVManifestRegistry`. Used by Forge and specialist-agent in production.
- [x] **Fleet-wide ADR-FLEET-001 landed.** Trace-richness schema committed. Defines what Jarvis must capture per decision.
- [x] **`.guardkit/context-manifest.yaml` in Jarvis repo.** References nats-core, forge, specialist-agent, nats-infrastructure, guardkit. Landed 19 April.

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

## 4. Feature Breakdown — FEAT-JARVIS-001..008

Patterned on Forge's FEAT-FORGE-001..007. Each feature ≈ 2-4 days, suitable for AutoBuild per feature with `/task-review` gates.

| # | Feature | Depends On | Est. | Purpose |
|---|---|---|---|---|
| **FEAT-JARVIS-001** | Supervisor Skeleton & Session Lifecycle | — | 2-3 days | DeepAgent supervisor via `create_deep_agent()` (or `create_agent()` per `/system-arch` outcome). Session type, thread-per-session model, Memory Store integration, startup/shutdown lifecycle. `jarvis` CLI entrypoint. Smoke test: supervisor answers a trivial question via CLI. |
| **FEAT-JARVIS-002** | Core Tools & Capability-Driven Dispatch Tools | 001 | 2-3 days | Non-dispatch tools (file read, web search, calendar stub, calculator), dispatch tools (`call_specialist`, `queue_build`), capability catalogue reader reading from `nats-core` KV manifest registry. Same pattern as Forge ADR-ARCH-015/016. Smoke test: supervisor lists available capabilities and picks correctly for three canned prompts. |
| **FEAT-JARVIS-003** | Async Subagents for Model Routing | 001 | 2-3 days | Four `AsyncSubAgent` instances at startup: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`. ASGI transport (per Forge ADR-ARCH-031 precedent). Cost + latency signals in descriptions. Supervisor dispatches to subagents via `start_async_task`/`check_async_task`. Smoke test: each subagent callable; supervisor picks `quick_local` for a trivial lookup and `deep_reasoner` for a reasoning task. |
| **FEAT-JARVIS-004** | NATS Fleet Registration & Specialist Dispatch | 002 | 2-3 days | Jarvis registers on `fleet.register` with `AgentManifest`. `NATSKVManifestRegistry` discovers specialist-agent fleet. `call_specialist` tool issues `agents.command.{agent_id}` and awaits `agents.result.{agent_id}`. Timeout handling, retry with redirect. Smoke test: Jarvis dispatches to a running `specialist-agent --role architect` and receives `ResultPayload` with Coach score. |
| **FEAT-JARVIS-005** | Build Queue Dispatch (Jarvis → Forge) | 004 | 1-2 days | `queue_build` tool publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per ADR-SP-014 Pattern A. No await; fire-and-forget pattern. Notification channel for Forge progress updates (`pipeline.stage-complete.*`). Smoke test: Jarvis queues a build, Forge consumer picks it up, Jarvis receives stage-complete notifications. |
| **FEAT-JARVIS-006** | Adapters — Telegram + CLI + Dashboard | 001 | 3-4 days | Three adapters each as `nats-asyncio-service`-patterned module publishing `jarvis.command.*` / subscribing `jarvis.notification.*`. Adapter ↔ session correlation via session_id in payload. Smoke test: each adapter round-trips a "hello" to Jarvis. |
| **FEAT-JARVIS-007** | Skills & Memory Store | 001 | 2-3 days | Three launch skills: `morning-briefing`, `talk-prep`, `project-status`. Each a composable tool unit callable via command pattern (`/skill morning-briefing`) or via natural language dispatch. Memory Store holds cross-session state (e.g. "last session we discussed X"). Smoke test: each skill produces plausible output; Memory Store recalls a fact from a prior session. |
| **FEAT-JARVIS-008** | Learning Flywheel — `jarvis.learning` + Graphiti Groups | 004 | 2-3 days | `jarvis_routing_history` and `jarvis_ambient_history` Graphiti groups populated per ADR-FLEET-001 schema. `jarvis.learning` pattern detector (module, not separate agent per D45) reads groups, proposes `CalibrationAdjustment` entities. Rich-in-the-loop CLI for confirm/reject. System prompt retrieval injects priors. Smoke test: after 10 dispatches, learning module proposes one plausible adjustment. |

### Optional post-v1 features (NOT in v1 scope — noted for reference)

- **FEAT-JARVIS-009**: Ambient Pattern B watcher — one proven candidate ("Forge queue completion nudge").
- **FEAT-JARVIS-010**: Reachy Mini voice adapter — when hardware lands.
- **FEAT-JARVIS-011**: Second cohort of async subagents if the original four prove insufficient.
- **FEAT-JARVIS-012**: Context7 integration as a first-class Jarvis tool.

---

## 5. Full Build Pipeline (Forge-style)

Once tomorrow's `/system-arch` lands and `guardkit init` is done, the pipeline is:

```
[done]     /system-arch   → docs/architecture/ARCHITECTURE.md + C4 + ADR-J-P1..P10
[next]     /system-design → per-feature design docs (8 × FEAT-JARVIS-00N design.md)
           /feature-spec  → per-feature gherkin scenarios (8 × FEAT-JARVIS-00N_summary.md)
           /feature-plan  → per-feature task decomposition (8 × FEAT-JARVIS-00N build plan)
           autobuild      → per-feature implementation (8 × AutoBuild runs)
           /task-review   → gates as needed per feature complexity
```

### Batch or sequential?

**Sequential, not batched.** Reasoning:

- FEAT-JARVIS-001 establishes the supervisor skeleton; every subsequent feature depends on it.
- FEAT-JARVIS-002 and -003 are parallel candidates (both depend only on 001) but Forge's experience shows **sequential with AutoBuild** is faster in practice than juggling parallel AutoBuild runs.
- The learning feature (008) depends on 004 (NATS integration). Don't schedule it early.
- Adapters (006) and skills (007) depend only on 001; they can slot in wherever makes sense.

### Suggested ordering (v1)

```
Day 1:    guardkit init + pin bump + FEAT-JARVIS-001 (/system-design + /feature-spec)
Day 2-3:  FEAT-JARVIS-001 (/feature-plan + autobuild + /task-review)
Day 3-4:  FEAT-JARVIS-002 (/system-design through autobuild)
Day 5-6:  FEAT-JARVIS-003 (async subagents — the hardest)
Day 7-8:  FEAT-JARVIS-004 (NATS fleet integration)
Day 9:    FEAT-JARVIS-005 (build queue — small)
Day 10-11: FEAT-JARVIS-006 (adapters — three thin modules)
Day 12-13: FEAT-JARVIS-007 (skills + Memory Store)
Day 14-15: FEAT-JARVIS-008 (learning flywheel)
```

Total: ~15 working days for v1. Realistic given testing plus interruptions.

---

## 6. AutoBuild Considerations

Forge's experience (30 ADRs, 6 features via AutoBuild) informs:

- **Per-feature AutoBuild, not per-task.** AutoBuild runs a whole feature's task list overnight, not a single task. Expect ~90 minutes per feature.
- **`/task-review` after each feature, not after each task.** Review once at the gate, not per sub-task. Keeps signal-to-noise high.
- **Context manifests are populated and ready.** `.guardkit/context-manifest.yaml` already landed.
- **Trace richness on by default.** ADR-FLEET-001 implementations follow from FEAT-JARVIS-008; earlier features use the schema even if the learning module isn't yet reading it.
- **Three-Layer Build Defence applies.** Layer 1 (prevention via better plans + Graphiti context), Layer 2 (recovery via Player-Coach loop), Layer 3 (assisted resolution via specialist resolver agents). Same as Forge.

---

## 7. Relationship to Tomorrow's `/system-arch`

Tomorrow's session produces Jarvis's architecture documents. This build plan is *written for those outputs to land_cleanly*. Specifically:

- FEAT-JARVIS-001..008 are **tentative feature IDs** — `/system-arch` may adjust numbering or rename. Acceptable.
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
| Adapters (006) turning into a rabbit-hole | Scope discipline: three thin modules, `nats-asyncio-service`-patterned, no fancy UX. Dashboard is *status*, not *control centre*. |

---

## 9. Decisions Required From This Conversation

1. **Confirm template choice** — `langchain-deepagents-orchestrator`. ✅ if accepted; alternative needs evidence.
2. **Confirm `guardkit init` invocation timing** — today (before `/system-arch`) or tomorrow (after `/system-arch`)?
   - **My recommendation: today.** Reasoning: scaffolding the repo doesn't depend on architecture decisions; `/system-arch` consumes existing repo state + conversation-starter. Having `.claude/`, `agents/`, and the orchestrator specialists already in place means `/system-arch` runs with more context.
3. **Confirm feature-ordering preference** — as per §5 Day-by-day, or different?
4. **Agree Day-1 scope** — `guardkit init` + pin bump + start FEAT-JARVIS-001 `/system-design`? Or `guardkit init` + pin bump + stop-for-the-day?
5. **Any additional v1 features needed?** (E.g. if there's a Telegram-adapter-first urgency that bumps it ahead of FEAT-JARVIS-002/003.)

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

## 11. Exact Command to Run Today

Assuming §9 decisions land positively:

```bash
# 1. Confirm repo state
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
git status                                   # should be clean on main
ls .guardkit/                                 # should show context-manifest.yaml

# 2. Run guardkit init
guardkit init langchain-deepagents-orchestrator \
  --project-name jarvis \
  --interactive

# 3. Inspect what landed
git status
ls -la                                        # should show new .claude/, agents/, manifest.json, settings.json, src/, tests/, templates/

# 4. Pin bump (first commit after init)
# Edit requirements.txt: deepagents >= 0.5.3, < 0.6
# Edit pyproject.toml equivalent
git add -A
git commit -m "chore: guardkit init with langchain-deepagents-orchestrator template; bump DeepAgents pin to 0.5.3"

# 5. (Optional, if there is bandwidth today) — prep for tomorrow's /system-arch
# Nothing to do here — jarvis-architecture-conversation-starter.md v2 is the primary input.
```

### After `/system-arch` tomorrow

```bash
# 1. Validate /system-arch outputs exist
ls docs/architecture/
# Expected: ARCHITECTURE.md, decisions/ADR-J-001..N.md, c4-*.svg or similar

# 2. Update this build plan if needed
# Reconcile FEAT-JARVIS-001..008 names with actual ADR-J-001..N

# 3. Start FEAT-JARVIS-001 /system-design
guardkit system-design "Supervisor Skeleton & Session Lifecycle" \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md
```

---

## 12. Done-Definition for This Conversation

The conversation is done when:

- [ ] `guardkit init langchain-deepagents-orchestrator` executed in `jarvis/` repo
- [ ] DeepAgents pin bumped to `>= 0.5.3, < 0.6`
- [ ] First commit on Jarvis repo landed (the init + pin bump)
- [ ] Build plan (§4 feature breakdown) confirmed or revised
- [ ] Day-by-day ordering (§5) confirmed or revised
- [ ] Starter questions 1-7 have explicit answers (or explicit "defer to `/system-arch`")
- [ ] This conversation starter updated with answers as comments/edits

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
