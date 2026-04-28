# DDR-024 — Degraded specialists remain dispatch-eligible in v1; status captured in trace

- **Status:** Accepted
- **Date:** 2026-04-28
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** ADR-ARCH-015 (capability-driven dispatch — Forge), ADR-ARCH-020 (trace-richness by default), ADR-ARCH-021 (tools return structured errors), [DDR-017](DDR-017-retry-with-redirect-policy.md), [DDR-018](DDR-018-routing-history-schema-authoritative.md), `nats_core.manifest.AgentManifest` (status enum)
- **Promotes:** [ASSUM-008](../../../../features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml) — degraded specialists eligible for dispatch

## Context

`nats_core.manifest.AgentManifest.status` is an enum with three values: `healthy`, `degraded`, `offline`. Specialists self-report status on registration and on heartbeat. Forge's ARCH-015 capability-driven dispatch convention (which Jarvis inherits) does **not** specify whether `status="degraded"` excludes a specialist from resolution — the enum is contracted, the semantics are open.

Phase-3 `/feature-spec` Gherkin pins the scenario: *"A specialist reporting degraded status is still eligible for dispatch and the trace records the status."* ASSUM-008 named this as a medium-confidence policy choice; this DDR promotes it to a binding decision so the resolver and trace-writer have an authoritative contract.

Three options were on the table:

1. **Exclude degraded specialists at resolution time.** Filter them out of `_resolve_agent_id` candidates entirely.
2. **Dispatch-eligible, but down-rank.** Prefer healthy specialists; fall back to degraded only when no healthy match exists.
3. **Dispatch-eligible, no preference.** Treat all non-`offline` specialists uniformly; let DDR-017 retry-with-redirect handle failures.

The choice has compounding effects:

- The **redirect-with-retry policy** (DDR-017) already handles dispatch failure recovery — including timeouts and `success=False` returns. A degraded specialist that succeeds is indistinguishable, at the dispatch boundary, from a healthy one. A degraded specialist that fails is handled by the same redirect pathway as any other failure.
- The **trace richness mandate** (ADR-FLEET-001 / ADR-ARCH-020) wants the supervisor's full decision context preserved. The specialist's reported status at decision time is part of that context — `jarvis.learning` (FEAT-J008) will want it for retro-analysis.
- The **resolver determinism** invariant (ASSUM-011, lexicographic ordering for trace replay) is stronger if the candidate set is just "all specialists matching the capability" — adding a status filter changes the candidate set in ways that aren't observable from the trace (the trace records *what was chosen*, not *what the registry said about other candidates' status at that moment*).

## Decision

In FEAT-JARVIS-004 (v1):

1. **Specialists with `status="degraded"` remain dispatch-eligible.** `_resolve_agent_id` does not filter on `status`; the only `status`-based exclusion is `offline` (which the registry already filters at the `list_available_capabilities` boundary, since offline specialists are not in the live KV view).
2. **No down-ranking, no preference order.** Healthy and degraded specialists are treated uniformly by the resolver. Lexicographic ordering on `agent_id` (ASSUM-011) is preserved as the only ordering signal — keeping resolution deterministic for trace replay.
3. **Redirect-with-retry handles failures.** A degraded specialist that times out or returns `success=False` triggers the DDR-017 redirect pathway exactly like any other failure. Visited-set on `agent_id` prevents re-trying the same degraded one.
4. **The routing history record captures the chosen specialist's reported status at decision time.** A new field `chosen_specialist_status: Literal["healthy", "degraded"]` is added to `JarvisRoutingHistoryEntry` (mandatory, populated by reading `manifest.status` from the registry snapshot at resolve time). For `RedirectAttempt` entries within `attempts`, the same field — `reported_status` — is also captured per attempt so the full status sequence across redirects is auditable.
5. **Append-only revision pathway.** If real-world traffic shows degraded specialists failing at a materially higher rate than healthy ones (signal: `outcome="redirected" AND attempts[0].reported_status="degraded"` exceeds 5% of dispatches over 7 days), `jarvis.learning` (FEAT-J008) can land an append-only DDR introducing exclusion or down-ranking. Until that data exists, exclusion is premature.

## Rationale

- **The redirect policy already covers failure.** Excluding degraded specialists at resolution would prevent a category of *successful* dispatches that today work fine — degraded ≠ broken. A degraded model might be reporting elevated latency or partial GPU offload but still completing requests correctly. Filtering them costs successful round-trips.
- **The learning signal needs the data.** FEAT-J008 cannot decide "should we exclude degraded specialists?" without observing what happens when we don't. Excluding from day-1 means the data never gets gathered; the policy is permanently uninformable.
- **Deterministic resolution is load-bearing for trace replay.** Adding status as a candidate filter introduces hidden state — a specialist's degraded→healthy transition between two replays would change the chosen `agent_id`. Lexicographic-only ordering keeps replays bit-for-bit reproducible.
- **`offline` is already filtered.** The KV registry only surfaces specialists currently registered (heartbeat alive). Offline specialists are gone from the candidate set without any resolver-level filtering. So "no status filtering" really means "no `degraded` filtering".
- **Capturing `chosen_specialist_status` in the trace** is cheap (one enum field) and high-value — it gives FEAT-J008 the per-decision data needed to evaluate whether the v1 policy is correct.
- **Per-attempt `reported_status`** in `RedirectAttempt` lets the meta-reasoner reconstruct sequences like "degraded specialist failed → redirected to healthy specialist → success" without joining against historical manifest snapshots. The status data lives with the decision.

## Alternatives considered

| Option | Why not |
|---|---|
| Exclude degraded specialists at `_resolve_agent_id` | Prevents successful dispatches today; permanently blocks the data signal `jarvis.learning` needs to evaluate the policy. Status is self-reported and conservative — many "degraded" specialists complete requests fine |
| Down-rank degraded (prefer healthy first, fall back to degraded) | Breaks lexicographic-only determinism (ASSUM-011); a status flap between replays changes the chosen `agent_id`. Also adds resolver complexity for a v1 with no observed failure data |
| Exclude degraded *only when a healthy alternative exists* | Same determinism break as down-ranking; introduces hidden conditional behaviour that is hard to reason about in trace replay |
| Surface `status="degraded"` as a structured DEGRADED string at the tool boundary instead of dispatching | Pre-empts the dispatch on a *self-reported* signal; the specialist may handle the request fine. Better to attempt and let the result speak — and let the trace capture both |
| Capture only the chosen specialist's status (skip per-attempt status in `RedirectAttempt`) | Loses the redirect-sequence story — meta-reasoning can't tell whether a redirect was healthy→degraded or degraded→healthy. Per-attempt status is cheap (one enum) and fully reconstructable from the registry at resolve time |
| Defer the policy to FEAT-J008 (no v1 decision) | Leaves an underspecified resolver; the implementation must pick *some* behaviour, and an undocumented choice is worse than a documented one |
| Make exclusion operator-tunable (config flag) | Premature; YAGNI. One correct behaviour for v1 with a clear data-driven revision pathway is better than two configurable ones |

## Consequences

- `_resolve_agent_id` (in `tools/dispatch.py`) does **not** filter on `manifest.status`; only the registry's natural `offline` exclusion applies.
- `JarvisRoutingHistoryEntry` gains `chosen_specialist_status: Literal["healthy", "degraded"]` (mandatory, populated by the writer from registry snapshot at resolve time) — append to the schema per [DDR-018](DDR-018-routing-history-schema-authoritative.md)'s append-only-from-v1 contract.
- `RedirectAttempt` gains `reported_status: Literal["healthy", "degraded"]` (mandatory) — same population path.
- [DM-routing-history.md](../models/DM-routing-history.md) updated to document both fields. `tests/test_routing_history_schema.py` exercises both happy / degraded / mixed-redirect-sequence scenarios.
- `tests/test_dispatch_by_capability_integration.py` adds a scenario: pre-seed two specialist manifests, one healthy + one degraded, both matching the requested capability; assert lexicographic ordering picks one regardless of status; assert trace record carries the chosen status; assert the same scenario with the chosen specialist failing → redirect to the other works regardless of which status was tried first.
- FEAT-JARVIS-008 (`jarvis.learning`, v1.5) gets the data it needs to evaluate whether to exclude or down-rank in v2 via an append-only DDR.
- FEAT-JARVIS-005's `queue_build` dispatch path inherits the same policy — degraded build-queue specialists are still eligible; trace captures status uniformly.
- The Phase-3 close criterion's end-to-end test must include at least one degraded specialist in the fixture to exercise this code path; otherwise the new schema fields aren't observably populated.

## Status

Accepted at FEAT-JARVIS-004 (promotion of ASSUM-008 — originally medium-confidence — to a binding decision). Append-only — revision (toward exclusion or down-ranking) requires a new DDR grounded in observed `jarvis.learning` data.
