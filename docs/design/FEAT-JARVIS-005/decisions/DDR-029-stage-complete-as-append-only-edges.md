# DDR-029 — Stage-complete events land as append-only Graphiti edges, not field overwrites

- **Status:** Accepted
- **Date:** 2026-04-29
- **Feature:** FEAT-JARVIS-005 (Phase 3 / Fleet Integration)
- **Related:** [ADR-FLEET-001 §"Do-not-reopen"](../../../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md), [DDR-018](../../FEAT-JARVIS-004/decisions/DDR-018-routing-history-schema-authoritative.md), [DDR-019](../../FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md), [ADR-ARCH-029](../../../architecture/decisions/ADR-ARCH-029-redaction-posture.md), [DM-routing-history.md](../../FEAT-JARVIS-004/models/DM-routing-history.md)

## Context

Every `queue_build` writes a `JarvisRoutingHistoryEntry` with `subagent_type="forge_build_queue"` per FEAT-JARVIS-004. Forge then publishes 1..N `pipeline.stage-complete.{feature_id}` events as the build progresses. Two shapes are possible for capturing those stage events on the originating Graphiti record:

1. **Field overwrites.** Each stage-complete event mutates fields on the original entry — e.g. `outcome_type` flips from `"queued"` to `"running"` to `"complete"`; `outcome_detail` accumulates stage history as a list.
2. **Append-only edges.** Each stage-complete event lands as a new Graphiti edge against the original entry's node; the entry itself stays immutable.

DDR-018 already pinned `JarvisRoutingHistoryEntry.model_config = ConfigDict(frozen=True)` and the rationale `"updates from FEAT-J005 stage-complete events go on edges, not field overwrites — preserves audit-trail integrity"`. This DDR ratifies that shape and pins the edge-naming convention so FEAT-J008 (`jarvis.learning`) has a stable read contract.

ADR-FLEET-001 §"Do-not-reopen" reinforces it: *"Once the trace-rich schema is shipping in any surface, any future decision to reduce trace richness requires an explicit ADR and sign-off."* Field overwrites would silently destroy intermediate state — exactly the failure mode the clause forbids.

## Decision

1. **Stage-complete events land as append-only Graphiti edges.** Each event = one edge on the original `JarvisRoutingHistoryEntry` node. The entry remains `frozen=True` per DDR-018; no field overwrites.
2. **Edge type:** `stage_complete`. (Singular per ADR-SP-016 conventions.)
3. **Edge body:** redaction-processed JSON-encoded `StageCompletePayload`. Same `structlog` redact-processor as `RoutingHistoryWriter.write_specialist_dispatch` (ADR-ARCH-029).
4. **Edge name:** `stage_complete:{correlation_id}:{seq}` where `seq` is a per-correlation monotonic counter (0, 1, 2, …) so multiple stage events for the same build have distinct entity names. The counter is in-memory on the writer (bounded in step with DDR-028's correlation map).
5. **Implementation:** `RoutingHistoryWriter.append_build_queue_event(correlation_id, event)` schedules `add_episode(name=..., episode_body=..., source_description='jarvis-routing-history-edge', reference_time=event.completed_at)` per the FEAT-J004 reservation in API-internal.md §4.
6. **Failure:** WARN-only per DDR-019. `WARN routing_history_append_failed reason=<exception_class>`. Append-only-best-effort.

## Rationale

- **DDR-018 pinned the shape.** This DDR ratifies and supplies the implementation detail (edge type, edge naming, monotonic counter) that the FEAT-J004 reservation deferred.
- **Audit-trail integrity is the whole point.** Field overwrites would let later events silently destroy prior outcome state. ADR-FLEET-001 §"Do-not-reopen" makes the audit trail load-bearing for the whole learning loop — `jarvis.learning` (FEAT-J008) reads stage-by-stage progressions, not just terminal state.
- **Per-correlation monotonic seq prevents Graphiti name collisions.** A naïve `stage_complete:{correlation_id}` would produce duplicate names if Forge emits >1 stage-complete event for the same correlation (which it does — one per gated dispatch per Forge's contract). The `:seq` suffix makes each edge unique.
- **WARN-only failure surface inherited from DDR-019.** Same rationale: trace-richness is operationally observable, not load-bearing for runtime correctness.
- **Append-only-by-design plays well with FEAT-J008's read pattern.** The learning module wants to grep through stage progressions to detect gating-mode patterns, coach-score drops, redirect rates per stage label. An edge timeline is the right data shape for that.

## Alternatives considered

| Option | Why not |
|---|---|
| Field overwrite of `outcome_type` / `outcome_detail` | Destroys intermediate state; violates DDR-018's `frozen=True` invariant; violates ADR-FLEET-001 "do-not-reopen" |
| Append to a list field on the entry | Requires mutating a frozen entry — same violation as field overwrite |
| Single edge accumulating events as `event_count` + `events` array | Loses Graphiti's per-edge reference_time signal; edge would grow over time and become a hot-spot for FEAT-J008 reads |
| Stage events as separate routing-history *entries* (`subagent_type="stage_event"`) | Decouples stage events from the originating build; FEAT-J008 would need a join on correlation_id; defeats the audit-trail-on-original purpose |
| Edge type `stage-complete` (kebab-case) | Singular per ADR-SP-016 but the convention for entity / edge names is snake_case; align with `routing_history_write_failed`-style log keys |
| Edge name = `correlation_id` only | Name collisions when Forge fires multiple stage-complete events on one build |

## Consequences

- `RoutingHistoryWriter.append_build_queue_event` body lands per [API-internal.md §2](../contracts/API-internal.md). The FEAT-J004 no-op signature is preserved; only the body changes.
- `RoutingHistoryWriter` gains a `_correlation_edge_seq: dict[str, int]` for per-correlation seq tracking; capped in step with the subscriber's correlation map (entries pruned on subscriber-side eviction).
- FEAT-JARVIS-008 (v1.5 `jarvis.learning`) reads stage-complete edges via Graphiti's edge-query primitives. The append-only-extension promise of DDR-018 extends to edges — no rename, no type change post-v1 without a `schema_version` bump.
- `tests/test_routing_history_build_queue.py` covers: 3 stage-complete events for one correlation produce 3 distinct edges with seqs 0, 1, 2; edge body matches the redaction-processed payload; failure (Graphiti unreachable) logs WARN.
- Storage cost: one edge per stage event. Typical Forge build emits ~5–10 stage-complete events; multiplicative cost is small relative to entity count.
- FEAT-JARVIS-011 (v1.1 `jarvis purge-traces`) deletes both the entry node *and* all attached `stage_complete` edges via Graphiti's cascade — must walk the edge-collection at purge time.

## Status

Accepted at FEAT-JARVIS-005 `/system-design`. Schema additions to the edge body are append-only via ADR-FLEET-00X (same convention as DDR-018 establishes for the entry).
