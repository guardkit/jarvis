# ADR-ARCH-003: Jarvis IS the GPA — not a thin router

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Supersedes:** Original jarvis-vision v1 (March 2026) framing of "thin router with GPA as one of many specialists"

## Context

The v1 vision framed Jarvis as a classification layer in front of a separate General Purpose Agent. That framing (a) makes Jarvis a plumbing component with no substantive reasoning, (b) duplicates processes without architectural benefit, and (c) complicates cross-session memory because per-session context would need to cross process boundaries.

Fleet v3 resolved D40 ("three surfaces, one substrate") — Jarvis IS a DeepAgent, and routing is tool selection. D43 reinforces this: model routing is a reasoning decision, not a classification pipeline stage.

## Decision

There is no separate GPA. Jarvis is a DeepAgents supervisor whose primary superpower is *knowing which reasoning role to apply, which specialist to dispatch to, and when to queue a build*. Dispatch is one tool category among many in Jarvis's toolbelt.

Three dispatch mechanisms (all tools the supervisor reasons over):

1. **Async subagents** — `start_async_task` → `jarvis-reasoner` AsyncSubAgent for long-running reasoning with role-mode prompts
2. **NATS specialists** — `dispatch_by_capability` → `agents.command.{agent_id}` for architect/product-owner/ideation/ux-designer
3. **Forge** — `queue_build` → `pipeline.build-queued.{feature_id}` for build intent

Plus the attended-only `escalate_to_frontier` cloud escape (ADR-ARCH-027).

## Alternatives considered

1. **Thin router + separate GPA process (v1 vision)** *(rejected)*: Adds deployment complexity; splits reasoning across processes; weakens per-session memory.
2. **Rule-based intent classifier with LLM fallback (D11 direction)** *(rejected)*: Fleet v3 resolves this by making routing a reasoning-over-descriptions decision; a classifier is a worse implementation of the same idea.

## Consequences

- One Jarvis container, one reasoning loop, unified per-session memory across all delegation targets.
- "One reasoning model that knows which role to apply" becomes the one-sentence thesis.
- Capability-driven dispatch (Forge ADR-ARCH-015 pattern) applies — Jarvis reads tool docstrings + registered capability descriptions; reasoning model picks.
- Closes D11 (intent classifier) and D12 (GPA location) from vision v1.
