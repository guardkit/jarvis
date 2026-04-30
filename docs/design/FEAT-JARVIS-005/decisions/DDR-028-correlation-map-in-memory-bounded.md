# DDR-028 — Correlation map is in-memory, LRU-bounded at 1000 entries

- **Status:** Accepted
- **Date:** 2026-04-29
- **Feature:** FEAT-JARVIS-005 (Phase 3 / Fleet Integration)
- **Related:** [ADR-ARCH-008](../../../architecture/decisions/ADR-ARCH-008-no-sqlite.md) (no SQLite), [ADR-ARCH-009](../../../architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store.md), [ADR-ARCH-026](../../../architecture/decisions/ADR-ARCH-026-no-horizontal-scaling.md), [DDR-027](DDR-027-stage-complete-ephemeral-deliver-new.md)

## Context

`ForgeNotificationsSubscriber._on_message` needs to know which session originated each stage-complete event. The standard mechanism is a correlation-id → session-id map populated at queue-time by `queue_build` and consulted at consume-time by the subscriber.

Two storage shapes considered:

1. **In-memory dict.** Simple; lost on restart; bounded by available memory unless explicitly capped.
2. **Persisted (SQLite, file, or Graphiti entity).** Survives restart; introduces cross-restart state that ADR-ARCH-008 explicitly forbade.

Three sizing concerns:

- A long-running session could queue hundreds of builds across days; the map can't grow without bound.
- A wedged Forge could leave correlations un-flushed indefinitely.
- The map must not OOM the Jarvis process under any operator load.

## Decision

The correlation map is:

1. **In-memory only.** Lives on `ForgeNotificationsSubscriber._correlations` as `OrderedDict[str, BuildCorrelation]` (insertion-ordered for LRU semantics).
2. **LRU-bounded at 1000 entries** by default, configurable via `JarvisConfig.forge_correlation_map_cap` (`Field(ge=10, le=100_000)`).
3. **Eviction on insert when at cap** — drops the oldest entry; logs `WARN forge_correlation_evicted correlation_id=<x> session_id=<y> queued_at=<z>` so saturation is observable.
4. **Lost on Jarvis restart** per DDR-027 — events for evicted-or-restarted correlations are silently dropped at the subscriber per design §8.

## Rationale

- **In-memory matches DDR-027's ephemeral consumer posture.** Persisted correlations + ephemeral consumer is incoherent: the persisted entries would point at session_ids that don't survive restart anyway (sessions are ephemeral per ADR-ARCH-009). Both halves of the bridge are correctly ephemeral.
- **ADR-ARCH-008 (no SQLite) preserved.** Persisting to SQLite would diverge from the architecture; persisting to Graphiti would make the correlation-lookup path latency-bound by FalkorDB; persisting to a flat file would re-introduce a state-management problem (write-on-success, read-on-consume, evict-on-terminal) that doesn't fit the in-memory bridge model.
- **1000-entry cap is generous for solo-operator load.** Empirical estimate: typical builds 5–30 mins; Rich actively building during work hours; ~10–20 builds/day max. 1000 entries = ~50 days of headroom. Sized to never naturally reach saturation; saturation is a signal something is wrong (runaway build loop, Forge wedged, test fixture leaking).
- **LRU eviction over TTL eviction** — TTL would need a periodic sweep task; LRU evicts on the natural insertion event. Simpler.
- **`WARN` (not `ERROR`) on eviction** — same rationale as DDR-019 routing-history WARN: trace-richness is operationally observable, not load-bearing for runtime correctness. Eviction means a stage-complete event for the evicted correlation will be silently dropped, but the build itself is not affected.

## Alternatives considered

| Option | Why not |
|---|---|
| No cap (unbounded `dict`) | Memory leak vector; one wedged Forge could grow the map indefinitely |
| TTL-based eviction (e.g. evict at 24h) | Adds a periodic-sweep task; latency-bound on the sweep cadence; doesn't naturally cap memory |
| Persist to SQLite | Violates ADR-ARCH-008; doesn't actually help (sessions are ephemeral; persisted map points at dead session_ids) |
| Persist to Graphiti as a transient entity group | Latency on every consume path; entity-creation churn; mismatched with the in-memory bridge |
| Persist to a `~/.jarvis/correlations.json` flat file | Adds write-coordination problem (concurrent writes on overlapping queues); v1 has no such persistence story |
| Cap at 100 (smaller) | Would risk eviction during a normal multi-build day; saturation should be a *signal*, not a *common case* |
| Cap at 10000 (larger) | Diminishing returns — 1000 is already 50× expected daily peak; OOM concern doesn't justify higher; configurable for those who want it |

## Consequences

- `ForgeNotificationsSubscriber._correlations: OrderedDict[str, BuildCorrelation]` is the entire storage. No cross-process sharing, no persistence layer.
- `JarvisConfig.forge_correlation_map_cap: int = Field(default=1000, ge=10, le=100_000)`.
- `tests/test_forge_notifications_unit.py` covers: insert at-cap evicts oldest with WARN; insertion of duplicate `correlation_id` updates the existing entry's position (re-inserts at the head) without growing the map.
- `RoutingHistoryWriter` keeps an in-step `dict[str, int]` (per-correlation edge counter for DDR-029's monotonic edge naming) — same `correlation_cap`, same eviction event.
- Operator runbook signal: persistent `WARN forge_correlation_evicted` + missing stage-complete CLI lines = correlation map is overflowing → check for runaway test fixtures or wedged Forge.
- Cross-restart UX: any in-flight build started before a Jarvis restart loses its correlation; operator can `forge status` or query Forge directly to see build progress (out-of-scope for FEAT-J005).

## Status

Accepted at FEAT-JARVIS-005 `/system-design`. The cap is operator-tunable via env; if real-world load saturates 1000 entries, an append-only DDR can revisit with `jarvis.learning` data backing the new bound.
