# Superseded Designs — Provenance Index

> **Purpose:** Durable pointer to design decisions that were proposed in pre-ADR scope/plan documents, then retired by subsequent architectural decisions. If a future reader (or future Claude) encounters a reference to a retired design element, this file records what replaced it, when, and why.
>
> **Convention:** One section per retirement event. Each section names (a) the retired element, (b) the upstream docs that still reference it, (c) the superseding ADR / DDR, (d) the replacement design, (e) the rationale.

---

## 1. Four-cloud-subagent roster → single `jarvis-reasoner` with role-dispatch

**Retired on:** 2026-04-20 (`/system-arch` session) + 2026-04-23 (`/system-design FEAT-JARVIS-003`)
**Superseded by:** [ADR-ARCH-001](../architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md), [ADR-ARCH-011](../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md), [FEAT-JARVIS-003 DDR-010](../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md), [FEAT-JARVIS-003 DDR-011](../design/FEAT-JARVIS-003/decisions/DDR-011-role-enum-closed-v1.md)

### Retired element

Four `AsyncSubAgent` instances proposed as the FEAT-JARVIS-003 launch roster:

| Scope-doc name | Scope-doc model | Retired because |
|---|---|---|
| `deep_reasoner` | `google_genai:gemini-3.1-pro` | Cloud LLM on unattended path — forbidden by ADR-ARCH-001 |
| `adversarial_critic` | `anthropic:claude-opus-4-7` | Same |
| `long_research` | `openai:gpt-5.4` | Same |
| `quick_local` | `vllm:qwen3-coder-next` | Retired by ADR-ARCH-011's single-subagent collapse; the latency/privacy slot it occupied is served by `jarvis-reasoner` itself via prompt-only role differentiation on the loaded model |

### Replacement

One `AsyncSubAgent`: **`jarvis-reasoner`**, backed by `gpt-oss-120b` MXFP4 via llama-swap alias `jarvis-reasoner`. Accepts a `role` kwarg in `input={}` selecting one of three role modes:

| `RoleName` member | Replaces (roughly) |
|---|---|
| `CRITIC` | `adversarial_critic` |
| `RESEARCHER` | `long_research` + parts of `deep_reasoner` |
| `PLANNER` | `deep_reasoner` planning work + parts of `quick_local` summarisation |

Genuine frontier-tier reasoning (Gemini 3.1 Pro, Opus 4.7) remains available — but only through the **`escalate_to_frontier`** tool on **attended sessions**, constitutionally gated per [ADR-ARCH-027](../architecture/decisions/ADR-ARCH-027-attended-only-cloud-escape-hatch.md) + [FEAT-JARVIS-003 DDR-014](../design/FEAT-JARVIS-003/decisions/DDR-014-escalate-to-frontier-in-dispatch-tool-module.md) (three-layer belt+braces: prompt prohibition, executor assertion, registration absence).

### Why

The four-subagent roster was drafted on 2026-04-20 against a cloud-primary cost model. Three days of normal Graphiti tinkering in April 2026 consumed £29.91 of an £80/month Gemini cap — extrapolating to £900–£1,500/month at full fleet load. The `/system-arch` session accepted ADR-ARCH-001 (local-first; no cloud on unattended paths) in response, which invalidated three of four subagents directly. ADR-ARCH-011 then collapsed the fourth to a prompt-driven-role-mode pattern on the single local backing model to avoid Roster-vs-Model mismatch confusion (four subagent names, one backing model) and to keep llama-swap's `swap: true, exclusive: true` builders group from thrashing.

### Docs that still reference the retired design

- [docs/research/ideas/jarvis-vision.md](../research/ideas/jarvis-vision.md) — upstream source of the roster; historical anchor, left intact (ADR-ARCH-011 records the supersession in its `Supersedes:` field).
- [docs/research/ideas/jarvis-architecture-conversation-starter.md](../research/ideas/jarvis-architecture-conversation-starter.md) — ADR-J-P2 names the four subagents; historical input to `/system-arch`, left intact.
- [docs/research/ideas/jarvis-build-plan-conversation-starter.md](../research/ideas/jarvis-build-plan-conversation-starter.md) — launch-subagents table row; historical, left intact.
- [docs/research/ideas/phase2-dispatch-foundations-scope.md](../research/ideas/phase2-dispatch-foundations-scope.md) — scope-doc FEAT-JARVIS-003 section; **banner added** pointing here.
- [docs/research/ideas/phase2-build-plan.md](../research/ideas/phase2-build-plan.md) — FEAT-JARVIS-003 build steps; **banner added** pointing here.
- [docs/research/ideas/phase3-build-plan.md](../research/ideas/phase3-build-plan.md) — "Phase 2 Results" section; **hot-edited** to the replacement shape.
- [docs/research/ideas/phase4-build-plan.md](../research/ideas/phase4-build-plan.md), [docs/research/ideas/phase4-surfaces-scope.md](../research/ideas/phase4-surfaces-scope.md) — skill-composition references to `quick_local` / `long_research` / `adversarial_critic`; **hot-edited** to use `jarvis-reasoner` with roles.

### Transitive retirements

- The scope-doc's **4 separate provider SDK dependencies** (`google-genai`, `anthropic`, `openai`, `vllm`) are retired — only `anthropic` + `google-genai` remain, and only for `escalate_to_frontier` on attended sessions.
- The scope-doc's **5-graph `langgraph.json`** (supervisor + 4 subagents) is retired — replaced by 2 graphs (supervisor + `jarvis_reasoner`) per [FEAT-JARVIS-003 DDR-013](../design/FEAT-JARVIS-003/decisions/DDR-013-langgraph-json-at-repo-root.md).

---

## 2. `quick_local` cloud-cheap-tier fallback (JA6) → swap-aware voice policy

**Retired on:** 2026-04-20 (`/system-arch` session) + 2026-04-23 (`/system-design FEAT-JARVIS-003`)
**Superseded by:** [ADR-ARCH-012](../architecture/decisions/ADR-ARCH-012-swap-aware-voice-latency-policy.md), [FEAT-JARVIS-003 DDR-015](../design/FEAT-JARVIS-003/decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md)

### Retired element

The scope-doc's JA6 answer: when AutoBuild is pressuring GB10 (Forge consuming GPU), `quick_local.py` would read a `system.health.vllm` signal; when `"degraded"`, the graph would fall back to an ADR-pinned cloud cheap-tier (`gemini-flash-latest` or equivalent). Fallback events would be logged for trace-richness.

### Replacement

**Swap-aware supervisor policy.** The supervisor reads llama-swap's `/running` and `/log` endpoints via `jarvis.adapters.llamaswap.LlamaSwapAdapter` (Phase 2 stub; FEAT-JARVIS-004 wires live). For voice-reactive paths, if the model is already loaded OR swap ETA ≤ 30s, the request queues. If swap ETA > 30s, TTS emits "just a moment, switching brains" before dispatching, and the full response plays when ready. **No cloud fallback on unattended paths.**

### Why

ADR-ARCH-012 §Context: "ADR-ARCH-001 disallows cloud fallback on unattended paths, so the original JA6 proposal is invalid." The trade is honest latency UX (Rich hears *why* there's a pause) instead of silent cloud spend on every unattended load-spike.

### Docs that still reference the retired design

All retired JA6 / `system.health.vllm` / `quick_local` fallback mentions have been hot-edited or banner-annotated per §1 above. Anchor docs ([jarvis-vision.md](../research/ideas/jarvis-vision.md), [jarvis-architecture-conversation-starter.md](../research/ideas/jarvis-architecture-conversation-starter.md)) left intact as historical inputs.

---

## 3. `call_specialist(agent_id, ...)` → `dispatch_by_capability(tool_name, ...)`

**Retired on:** 2026-04-23 (`/system-design FEAT-JARVIS-002`)
**Superseded by:** [ADR-ARCH-003](../architecture/decisions/ADR-ARCH-003-jarvis-is-the-gpa.md), [ADR-ARCH-016](../architecture/decisions/ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md), [FEAT-JARVIS-002 DDR-005](../design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md)

### Retired element

Scope-doc dispatch tool `call_specialist(agent_id: str, instruction: str, context: dict = {}) -> SpecialistResult` — hardcoded `agent_id` parameter.

### Replacement

`dispatch_by_capability(tool_name: str, payload_json: str, intent_pattern: str | None = None, timeout_seconds: int = 60) -> str` — capability-driven, no hardcoded `agent_id`. The reasoning model picks by reading capability descriptions at decision time; `NATSKVManifestRegistry` resolves `tool_name` → `agent_id` per Forge ADR-ARCH-015/016's fleet-wide inheritance.

### Why

Hardcoded `agent_id` would violate ADR-ARCH-003 (Jarvis-IS-the-GPA — capabilities, not agent names) and ADR-ARCH-016 (fleet-is-the-catalogue — no pre-coded agent list). The capability-driven shape matches Forge exactly.

### Docs hot-edited (2026-04-23, same sweep as retirement 1)

- [docs/research/ideas/phase3-fleet-integration-scope.md](../research/ideas/phase3-fleet-integration-scope.md) — 13 refs renamed; also noted `langgraph dev` graph count (5 → 2) per FEAT-JARVIS-003 DDR-013.
- [docs/research/ideas/phase3-build-plan.md](../research/ideas/phase3-build-plan.md) — 10 refs renamed (incl. `test_dispatch_call_specialist.py` → `test_dispatch_by_capability.py`).
- [docs/research/ideas/phase4-build-plan.md](../research/ideas/phase4-build-plan.md) — 2 refs: renamed + retirement annotation.
- [docs/research/ideas/phase4-surfaces-scope.md](../research/ideas/phase4-surfaces-scope.md) — 2 refs: renamed + retirement annotation.

Anchor docs ([jarvis-vision.md](../research/ideas/jarvis-vision.md), conversation-starters) left intact as historical inputs. [FEAT-JARVIS-002 design §11 C1](../design/FEAT-JARVIS-002/design.md) remains the authoritative record of the rename.

---

## Adding to this index

When a future `/system-design` or `/system-arch` session retires an upstream-doc element:

1. Record the retirement as a new numbered section above.
2. Hot-edit forward-looking docs (Phase N+1 build plans, scope docs) that will drive the next `/system-design` sessions.
3. Banner-annotate partially-superseded docs where hot-editing would lose provenance.
4. Leave anchor/vision docs intact — ADRs record the supersession, this file indexes them.

This file is the single place a reader can look up "what happened to X?" without having to grep the ADR corpus.
