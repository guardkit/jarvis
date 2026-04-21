# ADR-ARCH-001: Local-first inference via llama-swap on GB10

**Status:** Accepted (Foundational)
**Date:** 2026-04-20
**Deciders:** Rich (operator) + /system-arch session

## Context

Three days of normal Graphiti tinkering in April 2026 consumed £29.91 of an £80/month Gemini cap — extrapolating to ~£300–£400/month for *indexing alone* before any agent runs. Full-fleet projection with Jarvis + Forge + specialists at continuous load: £900–£1,500/month. The dark-factory economic thesis (marginal cost per build approaches zero → enables experimentation without per-run price tag) breaks at that cost level.

The GB10 (128 GB unified memory, Blackwell SM121) is already paid for. As of January 2026, llama.cpp PR #17570 added native `/v1/messages` support, unblocking Claude Agent SDK-based clients. Community (eugr, g.marconi) have converged on llama-swap + llama.cpp for multi-model GB10 setups because vLLM's `--gpu-memory-utilization` percentage allocation is wrong for unified memory.

## Decision

No cloud LLMs on any unattended path. All inference for Jarvis supervisor, async subagents, specialist-agent roles, Forge orchestration, AutoBuild, Graphiti entity extraction, and ambient watchers routes through **llama-swap on GB10** at `http://promaxgb10-41b1:9000`.

Cloud LLMs (Gemini 3.1 Pro, Opus 4.7) are permitted only on the **interactive** path where a human is driving, via the explicit `escalate_to_frontier` tool constitutionally blocked from ambient/learning/Pattern-C subagent tool sets. Budget envelope: ~£20–£50/month fleet-wide.

llama-swap model groups:

- **forever** (always-on, lifecycle delegated to existing vLLM scripts): `qwen-graphiti` (Qwen2.5-14B FP8), `nomic-embed` (nomic-embed-text-v1.5)
- **builders** (swap: true, exclusive: true — ONE at a time): `qwen-coder-next` (Qwen3-Coder-Next FP8), `gpt-oss-120b` (GPT-OSS 120B MXFP4 — Blackwell-optimised `sowilow/gpt-oss-120b-DGX-Spark-GGUF` build)

All fleet agents (Jarvis, Forge, specialists) share the same llama-swap instance. Model selection = llama-swap alias in the `model` field of each request, consumed by `init_chat_model("<alias>")` pointed at `http://promaxgb10-41b1:9000/v1`.

## Alternatives considered

1. **Cloud-primary with cost discipline via priors** *(rejected)*: The originally-proposed four-subagent roster (Gemini 3.1 Pro, Opus 4.7, GPT-5.4, local quick_local). Projects to £900–£1,500/month at full fleet load. Incompatible with dark-factory thesis and with the local-first principle Rich has established for the unattended path.
2. **Hybrid per-task sensitivity routing** *(rejected)*: Cloud for non-sensitive content, local for sensitive. Still carries cloud cost on unattended paths where most of the loop runs. Does not address the economic thesis.
3. **vLLM-per-model concurrent serving** *(rejected)*: vLLM's percentage-based memory allocation via `--gpu-memory-utilization` doesn't play well with GB10's unified 128 GB pool. Community migrated from vLLM to llama.cpp + llama-swap for multi-model GB10 setups specifically for this reason.
4. **Ollama for everything** *(rejected)*: llama.cpp with custom SM121 build gives better throughput on Blackwell; Ollama layers add complexity without benefit at fleet scale.

## Consequences

**Positive:**
- Marginal cost per Jarvis invocation ≈ £0. GB10 investment amortises against avoided cloud spend in the first month.
- Privacy default — all personal content (calendar, email, voice) stays on GB10.
- No rate-limit surprises on ambient/continuous loops.
- Single `/v1` front door simplifies integration — every agent uses `init_chat_model` pointed at llama-swap.
- Fleet coherence — Forge, Jarvis, and specialists share one inference hub.

**Negative:**
- **Builders group is `swap: true, exclusive: true`** — only one builder model loaded at a time. Parallel model routing across `jarvis-reasoner` and `autobuild-player` forces a swap (~2–4 min cold load for 120B). Supervisor must batch related work to minimise swap churn.
- Frontier reasoning (Gemini 3.1 Pro class) is **not** available to Jarvis reasoning on the unattended path. GPT-OSS 120B MXFP4 is the ceiling.
- Preview-feature dependency on llama.cpp `/v1/messages` (stable since build b4847+) and the `sowilow/gpt-oss-120b-DGX-Spark-GGUF` community build (not upstream).
- Memory bandwidth (273 GB/s shared) is a silent constraint — concurrent model activity drops each model's throughput to 60–70% of solo.
- Health of llama-swap + underlying model servers becomes a critical Jarvis dependency. Graceful degradation (swap-aware latency policy) required.

## Source documents

- `../guardkit/docs/research/dgx-spark/dark-factory-economics-and-model-serving.md`
- `../guardkit/docs/research/dgx-spark/llama-swap-setup.md`
- llama.cpp PR #17570 (Anthropic Messages API, Jan 2026)
- NVIDIA Developer Forums — "Best LLM engine for several parallel models?", "Code assist and RAG in single node"
