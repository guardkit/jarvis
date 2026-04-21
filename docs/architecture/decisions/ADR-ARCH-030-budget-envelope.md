# ADR-ARCH-030: Budget — £0 unattended; £20–£50/month attended cloud escape fleet-wide

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Depends on:** ADR-ARCH-001 (local-first inference), ADR-ARCH-027 (attended cloud escape)

## Context

ADR-ARCH-001 moves all unattended inference to GB10 via llama-swap, reducing unattended LLM spend to £0. ADR-ARCH-027 permits an attended escape hatch via `escalate_to_frontier`. The overall Jarvis LLM budget needs an explicit envelope.

## Decision

**Unattended spend: £0** (GB10 is the whole of the unattended inference substrate; no cloud API charges).

**Attended cloud escape: ~£20–£50/month fleet-wide** (not Jarvis-specific). This envelope is shared across:

- Jarvis `escalate_to_frontier` invocations
- Occasional interactive `/system-arch`-style sessions on the MacBook where frontier reasoning is justified
- Any `architect-agent` frontier consults on attended tasks

**Not a hard gate.** Monitored via Graphiti trace data (`model_alias=cloud-frontier` tagged entries across repos). Soft alarm if monthly running total approaches £60; review if persistent.

**Hardware budget: zero.** All compute already paid for (GB10, MacBook, NAS, Reachy on order).

## Alternatives considered

1. **£250/month for Jarvis** *(rejected)*: Original proposal — implicit cloud-subagent roster. Invalidated by ADR-ARCH-001.
2. **No explicit envelope** *(rejected)*: Trace-based monitoring works best against a target number; zero vs £50 vs £500 are very different regimes for learning-loop behaviour.
3. **£100+/month permissive attended** *(rejected)*: Invites creep; Rich wants frontier as a rare-tool, not a habit.

## Consequences

- Captured as `ASSUM-010`.
- Trace-rich Graphiti data makes cost attribution (which session, which tool, which model) directly queryable.
- If `escalate_to_frontier` usage drifts up, `jarvis.learning` can propose a `CalibrationAdjustment` tightening the constitutional rule (e.g. "block escalation when session has already had 2 escalations").
- Fleet-wide envelope means the Jarvis repo doesn't unilaterally own the budget — decisions that affect the envelope coordinate across repos.
