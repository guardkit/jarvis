# ADR-ARCH-013: Pattern B watcher ceiling — 10 concurrent

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Resolves:** JA2 (ambient watcher resource limits)

## Context

Pattern B ambient watchers (ADR-J-P8, vision §5) are async subagents monitoring a condition and emitting a notification on fire. They consume GB10 resources (memory for context, CPU for periodic evaluation, potentially inference invocations). GB10 also hosts Forge, specialist-agent, llama-swap + backing model servers, and Graphiti. A resource ceiling is needed.

## Decision

**10 concurrent Pattern B watchers in v1.** Matches DeepAgents 0.5.3 `--n-jobs-per-worker` default. Watchers beyond the ceiling are rejected at `start_watcher` time with a structured error; Jarvis reasoning then decides whether to dismiss a lower-priority watcher or tell Rich "I'm already watching 10 things; which should I drop?".

Revisit once real `jarvis_ambient_history` data lands — learning may propose a lower or higher ceiling via `CalibrationAdjustment`.

## Alternatives considered

1. **5 concurrent (conservative)** *(rejected)*: Half the DeepAgents default; may reject useful watchers unnecessarily.
2. **20 concurrent (generous)** *(rejected)*: Memory/bandwidth risk on GB10 when coincident AutoBuild + Jarvis work; notification-fatigue risk.
3. **Defer (no ceiling)** *(rejected)*: Unbounded ambient spawn is a real risk early on before learning establishes norms.

## Consequences

- Captured as `ASSUM-006` — revisit with real data.
- Requires `jarvis.watchers` to maintain an active-count and reject on overflow.
- Overflow rejection is itself a learning signal (recorded in `jarvis_ambient_history`).
