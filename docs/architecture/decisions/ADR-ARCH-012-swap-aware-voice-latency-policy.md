# ADR-ARCH-012: Swap-aware voice latency policy

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Depends on:** ADR-ARCH-001 (llama-swap swap semantics)
**Supersedes:** JA6 cloud cheap-tier fallback proposal

## Context

llama-swap's builders group is `swap: true, exclusive: true` — only one model loaded at a time (Qwen3-Coder-Next ↔ GPT-OSS 120B). Cold swap takes ~2–4 minutes for 120B. The Reachy voice path targets <2s p95 for conversational feel. A swap during a voice session would silently block for minutes.

ADR-ARCH-001 disallows cloud fallback on unattended paths, so the original JA6 proposal ("fall back to cloud cheap-tier on vLLM degraded") is invalid.

## Decision

The Jarvis supervisor is **swap-aware** via llama-swap's `/running` and `/log` endpoints. For voice-reactive paths:

1. Supervisor queries llama-swap state before dispatching reasoning.
2. If the required model is loaded OR swap ETA ≤ 30s: queue the request; swap completes quickly.
3. If swap ETA > 30s (cold load required): TTS immediately speaks a short acknowledgement ("Just a moment, switching brains") and dispatches the request; full response plays when the model is ready.
4. For non-voice paths (Telegram, Dashboard): no acknowledgement needed; standard latency.

Pre-emptive warm-hold: if Jarvis is about to need a different model (reasoning model detects from the incoming request), it may proactively request a swap before responding, so the second turn is fast.

## Alternatives considered

1. **Always wait silently for swap** *(rejected)*: Violates <2s voice target; feels broken.
2. **Route voice to a small always-warm local model (third forever-group member)** *(considered, deferred)*: Add a Qwen3-4B or Gemma-2-2B to the forever group for voice reactive responses. Adds ~3 GB memory and operational complexity. Defer to v1.5 if swap-ack proves too disruptive.
3. **Cloud cheap-tier fallback** *(rejected)*: Violates ADR-ARCH-001 local-first principle.

## Consequences

- Honest latency UX — Rich hears *why* there's a pause, rather than silence.
- Requires Jarvis to integrate llama-swap status queries into the routing tool layer (`jarvis.adapters.llamaswap`).
- Swap churn becomes visible in trace data (`jarvis_routing_history` records ETA + ack-triggered events), enabling learning ("batch coder requests after voice-heavy sessions").
- Captured as `ASSUM-004` pending real-world swap-time measurement.
