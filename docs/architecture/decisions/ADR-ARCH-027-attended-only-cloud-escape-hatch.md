# ADR-ARCH-027: Attended-only cloud escape hatch via `escalate_to_frontier` tool

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Depends on:** ADR-ARCH-001 (local-first inference), ADR-ARCH-022 (constitutional enforcement)

## Context

ADR-ARCH-001 disallows cloud LLMs on unattended paths. However, frontier reasoning (Gemini 3.1 Pro, Opus 4.7) genuinely helps some attended tasks — hard architecture questions, adversarial critique of proposals, long-form research synthesis beyond GPT-OSS 120B's ceiling. Forbidding cloud entirely loses this capability.

## Decision

Jarvis exposes an explicit `escalate_to_frontier` tool. When invoked, it calls the configured cloud frontier model (Gemini 3.1 Pro as default; Opus 4.7 on request) and returns the response to the reasoning flow.

**Constitutional gating (belt+braces per ADR-ARCH-022):**
- **Prompt rule**: the tool docstring + system prompt both state "only call this when Rich has explicitly asked for a frontier opinion on the current attended task; never from ambient watchers, learning-loop reasoning, or Pattern-C volitional contexts."
- **Executor assertion**: the tool implementation reads the current session adapter (from supervisor state) and asserts `adapter_id in {telegram, cli, dashboard, reachy}`. It also asserts the call frame is not an ambient watcher (checked via AsyncSubAgent metadata). Any violation returns `"ERROR: escalate_to_frontier is attended-only; caller frame rejected"`.

**Tool is removed** from the tool set passed to:
- Pattern B watcher AsyncSubAgents
- `jarvis.learning` reasoning paths
- Pattern C opt-in skill seed (`morning-briefing`)

Budget envelope (fleet-wide, not Jarvis-specific): ~£20–£50/month. Monitored via trace data (`model_alias=cloud-frontier` tagged entries in `jarvis_routing_history`). Soft limit — no hard gate.

## Alternatives considered

1. **No cloud tool at all — local-only** *(rejected)*: Loses frontier reasoning when genuinely needed; user switches to Claude Desktop manually — fine, but surrenders the "one reasoning model knows when to escalate" framing for frontier-tier.
2. **Rich-confirmed interrupt() each invocation** *(rejected for v1)*: Most conservative; highest UX friction. Revisit if escalations turn out to be more frequent than expected or if cost drifts up.
3. **Rate-limit per day/week** *(considered, deferred)*: Add a numeric quota. Trace-based monitoring is sufficient for v1; explicit quota can be added as a `CalibrationAdjustment` later.

## Consequences

- The "one reasoning model that knows when to escalate" framing survives — Jarvis reasons over when to use `escalate_to_frontier` just like any other tool, but the tool is only *available* on attended sessions.
- Cloud spend stays bounded by Rich's actual in-session asks, not by ambient loop volume.
- Adds complexity to the tool layer (session-aware tool registration; executor assertions). Acceptable cost for the safety property.
