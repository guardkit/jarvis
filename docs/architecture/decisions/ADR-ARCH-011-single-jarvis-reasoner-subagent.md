# ADR-ARCH-011: Single jarvis-reasoner subagent via gpt-oss-120b

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Depends on:** ADR-ARCH-001 (local-first inference)
**Supersedes:** original four-cloud-subagent roster from jarvis-vision v2 §2

## Context

The original vision proposed four async subagents (`deep_reasoner` → Gemini 3.1 Pro, `adversarial_critic` → Opus 4.7, `long_research` → GPT-5.4, `quick_local` → vLLM). Under ADR-ARCH-001 (no cloud LLMs on unattended paths), three of these become invalid, and llama-swap's builders group (`swap: true, exclusive: true`) makes parallel heterogeneous-model subagents impossible on GB10 without swap cost.

## Decision

Jarvis v1 ships with **one** async subagent: `jarvis-reasoner`. Backed by `gpt-oss-120b` MXFP4 via llama-swap alias `jarvis-reasoner`.

Specialist roles (critic, researcher, planner) are **prompt-driven modes** of the same model, not separate subagents. The supervisor invokes `start_async_task(role="critic", prompt=...)` which constructs a role-specific system prompt for the single subagent. The "one reasoning model that knows which reasoning model to use" thesis becomes "one reasoning model that knows which role/prompt to apply, when to swap-in coder-assist (`qwen-coder-next`), and when to escalate to cloud (`escalate_to_frontier`, attended only)."

llama-swap alias registry (model-field values Jarvis accepts):

| Alias | Backs | Used for |
|---|---|---|
| `jarvis-reasoner` | `gpt-oss-120b` (builders group, swap) | Primary reasoning; all role modes |
| `qwen-coder-next` | Qwen3-Coder-Next FP8 (builders group, swap) | Jarvis coder-assist work (rare); shared with Forge AutoBuild |
| `qwen-graphiti` | Qwen2.5-14B FP8 (forever group) | Graphiti entity extraction — not directly invoked by Jarvis reasoning |

## Alternatives considered

1. **Two subagents (jarvis-reasoner + coder-assist)** *(considered, deferred)*: Adds a formal coder-assist subagent. Useful if Jarvis needs to generate code itself (rare in v1 — code work goes to Forge). If a pattern emerges, promote `qwen-coder-next` invocation to a named subagent.
2. **Swap-aware four subagents (all aliased to local models)** *(rejected)*: Preserves the four-role taxonomy but creates Roster-vs-Model mismatch confusion — four subagent names, two backing models, each swap costs 2–4 min.
3. **Zero subagents (supervisor-only)** *(rejected)*: Loses the model-routing-as-reasoning framing that motivates per-invocation role selection. Keeps the architecture too flat for the complexity Jarvis needs to handle.

## Consequences

- Dramatically simpler architecture; the "reasoning model chooses a role" decision is a prompt construction step, not a subagent dispatch.
- No swap cost between role modes — critic / researcher / planner all run on the same loaded `gpt-oss-120b`.
- Loses model-heterogeneity. If GPT-OSS 120B turns out to be bad at adversarial critique specifically, we can't swap in a different model for that role without adding a new llama-swap member (and accepting swap cost).
- Clean path to grow later: adding `coder-assist` or fine-tuned specialist models is additive, not a rewrite.
