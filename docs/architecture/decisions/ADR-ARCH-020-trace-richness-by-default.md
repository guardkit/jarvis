# ADR-ARCH-020: Trace-richness by default (ADR-FLEET-001 adoption)

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Adopts:** [ADR-FLEET-001](../../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md)

## Context

Meta-Harness (Stanford 2026 preprint) showed that learning quality scales with trace richness — full-filesystem / full-reasoning-text traces enable 10× iteration efficiency over outcome-only logging. ADR-FLEET-001 commits the fleet to trace-rich logging from v1. Jarvis's learning loop (`jarvis.learning` module) benefits from exactly this pattern.

## Decision

Every `RoutingDecisionMade` event and every watcher firing is recorded to Graphiti with the full reasoning trace. Minimum captured fields:

**`jarvis_routing_history`:**
- `chosen_role` (prompt mode / subagent name / specialist id / build target / cloud_escape)
- `alternatives_considered` (list — each with description, cost signal, latency signal, reason rejected)
- `supervisor_reasoning` (free text — the model's rationale)
- `tool_call_sequence` (all tools invoked in this decision)
- `correlation_id`, `session_id`, `adapter_id`
- `retrieved_priors` (what Graphiti entries were loaded into the prompt)
- `outcome_reference` (fk to dispatch result or notification)
- `user_response_text` (full text, not just button press) — highest-signal field
- `redirect_flag` + `redirect_reason` if Rich corrected the decision
- `model_latency_ms`, `model_token_counts`, `model_alias` (llama-swap alias used)
- `environmental_context` (adapter, time, active watchers, llama-swap state)
- `timestamp`

**`jarvis_ambient_history`:**
- `watcher_id`, `watcher_spec`
- `trigger_condition_fired`
- `notification_text`
- `user_response_text` (dismiss reason if dismissed)
- `response_latency_ms`
- `acted_on` (did the notification lead to downstream action?)

No Prometheus V1 (matches Forge ADR-ARCH-024) — observability is events + Graphiti, not metrics.

## Alternatives considered

1. **Outcome-only logging** *(rejected)*: Caps learning quality permanently. Can't backfill richness retroactively.
2. **Retrofit trace-richness later** *(rejected)*: Early data would be low-resolution forever.

## Consequences

- Slightly higher per-decision write cost (Graphiti indexing).
- Dramatic learning-quality ceiling — `jarvis.learning` can detect subtle patterns that outcome-only logging would miss.
- Privacy: trace contents may include email subjects, calendar entries, voice transcripts. Retained under Rich's control on Tailscale/NAS per ADR-ARCH-029 personal-use posture.
- Exact Pydantic schema deferred to /system-design (`ASSUM-005`).
