# DDR-018 — `JarvisRoutingHistoryEntry` schema authoritative for v1+ with 16KB filesystem-offload

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** [ADR-FLEET-001](../../../../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md), ADR-ARCH-008 (no SQLite), ADR-ARCH-020 (trace-richness by default), ADR-ARCH-029 (redaction posture), [DM-routing-history.md](../models/DM-routing-history.md)
- **Resolves:** JA1 (architecture-deferred — exact Pydantic shape for `jarvis_routing_history`)

## Context

ADR-ARCH-020 commits Jarvis to ADR-FLEET-001 trace-richness from v1. Phase 3 lights up the first `jarvis_routing_history` writes — until this feature, the schema lived only in prose. The architecture conversation deferred the exact Pydantic shape (JA1) to `/system-design`.

The cost of getting this wrong is high. ADR-FLEET-001 §"Do-not-reopen": *"Once the trace-rich schema is shipping in any surface, any future decision to reduce trace richness requires an explicit ADR and sign-off."* Trace data compounds across thousands of records — a thin schema permanently caps the learning quality of FEAT-JARVIS-008 (`jarvis.learning`, v1.5).

Two design questions to settle:

1. **Field set.** Which ADR-FLEET-001 base fields (sections 1–7) plus which Jarvis-specific extensions are mandatory v1?
2. **Large-trace handling.** ADR-FLEET-001 §"Large traces" allows a filesystem offload; Jarvis needs a concrete threshold and path layout.

## Decision

The full Pydantic shape is documented in [DM-routing-history.md](../models/DM-routing-history.md) — `JarvisRoutingHistoryEntry`, `DispatchOutcome`, `RedirectAttempt`, plus helper types. Highlights:

1. **Authoritative for v1+.** Future field additions are append-only via ADR-FLEET-00X; renames or type changes require a `schema_version` field (introduced at the change point).
2. **Every ADR-FLEET-001 base field (sections 1–7) is mandatory.** No omissions. The session_id (§1) lands as `Session.session_id` per FEAT-J003 review F5 plumbing.
3. **Jarvis-specific extensions** per ADR-FLEET-001's "per-group" clause:
   - `chosen_specialist_id` / `chosen_subagent_name`
   - `alternatives_considered: list[CapabilityDescriptorRef]` — the descriptors the supervisor saw but didn't pick
   - `attempts: list[RedirectAttempt]` — per-attempt detail (DDR-017)
   - `supervisor_reasoning_summary: str` — supervisor's rationale, max 1024 chars
4. **Filesystem offload threshold = 16 KB JSON-encoded.** When `supervisor_tool_call_sequence` and/or `subagent_trace_ref` exceed this combined, the offload path triggers:
   - File written to `~/.jarvis/traces/{date}/{decision_id}.json`
   - Entity stores a `TraceRef(path, content_sha256, size_bytes)` instead of the inline payload
   - Mirrors the Meta-Harness filesystem-as-context pattern; meta-reasoning reads via `cat` / `grep` / `ls`
5. **`frozen=True`** on the entry. Updates from FEAT-JARVIS-005 stage-complete events go on **edges**, not field overwrites — preserves audit-trail integrity.
6. **Redaction at write boundary.** The `RoutingHistoryWriter` applies `structlog`'s redact-processor before either inline or filesystem write. ADR-ARCH-029 redaction posture; API keys, JWTs, NATS credentials, email addresses are filtered at capture, never at read.

## Rationale

- **Authoritative-from-here is the cheap option.** ADR-FLEET-001 explicitly warns retrofits are "nearly impossible" once thousands of records accumulate. Pinning the shape now means later writers (FEAT-JARVIS-005's `queue_build` path, FEAT-JARVIS-006's adapter-aware traces) extend the schema rather than diverge from it.
- **All ADR-FLEET-001 §1–§7 fields, not a subset.** The fleet-wide schema is the contract; Jarvis cherry-picking would break cross-surface meta-reasoning when Forge's `forge_pipeline_history` and Jarvis's `jarvis_routing_history` are queried in concert.
- **16KB threshold.** Graphiti entity size guidance (per ADR-FLEET-001 §"Large traces": "exceeds reasonable Graphiti entity size") is unspecified. 16KB is:
  - Large enough that simple dispatches stay inline (typical decision sequence is 200–500 bytes JSON-encoded).
  - Small enough that ideation / architecture-session traces with detailed sub-sequences offload — those are exactly the records `jarvis.learning` will want to grep through.
  - Aligned with Graphiti's typical entity-size sweet spot per Forge `forge_pipeline_history` operational data.
- **`frozen=True`** prevents accidental mutation in the writer pipeline; updates via edges (FEAT-J005) keep the original entry untouched.
- **Redaction at write boundary** — not Pydantic validator — because validators run on construction; we want redaction *after* the entry is fully populated, just before persistence.

## Alternatives considered

| Option | Why not |
|---|---|
| Subset of ADR-FLEET-001 fields (e.g. drop `recent_session_refs`, `concurrent_workload`) | ADR-FLEET-001's "Do-not-reopen" clause makes subsetting a binding promise to never enrich later. We pay the schema cost up front for compounding payoff. |
| Always-inline (no filesystem offload) | Graphiti entities can balloon to 100KB+ for complex ideation traces; impacts query latency and storage cost; ADR-FLEET-001 explicitly endorses filesystem offload |
| Lower offload threshold (e.g. 4KB) | Would offload routine dispatches with simple tool-call sequences, multiplying filesystem syscalls without proportional benefit |
| Higher threshold (e.g. 64KB) | Allows large entities into Graphiti; degrades query performance for the `jarvis.learning` retrieval path |
| Mutable entries (no `frozen=True`); FEAT-J005 stage-complete events overwrite fields | Breaks audit-trail integrity; violates ADR-FLEET-001's append-only-edges spirit |
| Redaction in a Pydantic validator | Runs at construction time, before downstream code may have added sensitive context (e.g. supervisor_reasoning_summary). Write-boundary redaction is the right seam |
| Schema versioning from v1 (explicit `schema_version` field) | Premature — v1 has one shape; YAGNI. Add the field at the first breaking change |

## Consequences

- `jarvis_routing_history` Graphiti group is the authoritative learning substrate from FEAT-J004 onward.
- ~/.jarvis/traces/ directory created at first write; lifecycle ensures it exists. Permissions: user-only (0700).
- `tests/test_routing_history_schema.py` is the schema-conformance gate — full-shape validation, large-trace offload behaviour, redaction at write boundary.
- FEAT-JARVIS-005 inherits the writer + schema verbatim. New `subagent_type="forge_build_queue"` records use the same Pydantic class.
- FEAT-JARVIS-008 (v1.5 `jarvis.learning`) reads from this schema. The append-only-extension promise gives it a stable contract.
- FEAT-JARVIS-011 (v1.1 `jarvis purge-traces`) deletes both the Graphiti entity *and* any `~/.jarvis/traces/{date}/{decision_id}.json` file referenced — must walk the path-via-`TraceRef` to delete cleanly.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. Append-only — additions via ADR-FLEET-00X; renames or type changes require an explicit ADR plus a `schema_version` field at the change point.
