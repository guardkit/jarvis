# DDR-023 — Trace-file collision policy: WARN + preserve original (no overwrite)

- **Status:** Accepted
- **Date:** 2026-04-28
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** [ADR-FLEET-001](../../../../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md), ADR-ARCH-020 (trace-richness by default), ADR-ARCH-029 (redaction posture), [DDR-018](DDR-018-routing-history-schema-authoritative.md), [DM-routing-history.md](../models/DM-routing-history.md)
- **Promotes:** [ASSUM-009](../../../../features/feat-jarvis-004-fleet-registration-and-specialist-dispatch/feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml) — trace-file collision treated as a write failure

## Context

[DDR-018](DDR-018-routing-history-schema-authoritative.md) pins the filesystem-offload path for trace records that exceed 16 KB JSON-encoded as `~/.jarvis/traces/{date}/{decision_id}.json`. The mapping is **1:1** — one decision id, one file. The `decision_id` is a UUID generated per dispatch, so collisions should be effectively impossible under correct operation.

But the file write is at a real filesystem boundary. Three failure modes can produce a pre-existing file at the target path:

1. **UUID re-use** — a defective UUID generator, a rolled-back-and-replayed dispatch, or a developer hand-crafting a `decision_id` for a test.
2. **Process-restart replay** — a crashed supervisor re-attempting a dispatch whose first attempt already offloaded its trace before the crash.
3. **Operator copy** — a human placing a previous trace into the directory for inspection or replay (less likely but possible during incident triage).

In **all three** cases the pre-existing file represents *real prior trace data*. The new write would discard that history. The ADR-FLEET-001 §"Do-not-reopen" clause and ADR-ARCH-020's trace-richness mandate make trace data **append-only-by-spirit** — destroying a prior record on collision is the wrong default.

The Phase-3 `/feature-spec` Gherkin enumerates the scenario: *"Writing a trace file that already exists for the same decision is treated as a write failure."* ASSUM-009 (originally low-confidence) named the policy; this DDR promotes it to a binding decision.

## Decision

When `RoutingHistoryWriter` attempts to offload a trace to `~/.jarvis/traces/{date}/{decision_id}.json` and the target file **already exists**:

1. **Do not overwrite.** The pre-existing file is preserved verbatim — content, mtime, permissions, all untouched.
2. **Log `WARN routing_history_write_failed`** with structured fields:
   - `decision_id` (the colliding UUID)
   - `path` (the absolute target path)
   - `reason="trace_file_exists"` (closed-set sentinel for grep / Graphiti queries)
   - `existing_size_bytes` (pre-existing file size, for diagnostics)
3. **The new entry's offload payload is dropped.** The Graphiti entity write proceeds with `TraceRef(path, content_sha256, size_bytes)` populated from the *pre-existing* file, **not** the new entry's payload — so the entity remains queryable but points at the original trace.
4. **The dispatch outcome is unchanged.** The tool boundary still returns the dispatch result (success / TIMEOUT / DEGRADED). Trace persistence is fire-and-forget per [DDR-019](DDR-019-graphiti-fire-and-forget-writes.md); a collision is a writer-internal degradation, not a dispatch failure.
5. **Implementation:** the writer uses `os.open(..., O_CREAT | O_EXCL | O_WRONLY, 0o600)` (or the asyncio equivalent via `aiofiles`) so the existence check and the create are atomic — no TOCTOU window between `os.path.exists` and `open`. On `FileExistsError`, the WARN path runs.

## Rationale

- **Trace data is append-only-by-spirit.** ADR-FLEET-001's "Do-not-reopen" clause makes destroying prior traces the wrong default. Preserve-original is the only policy aligned with trace-richness as a long-running learning substrate.
- **A collision is an error condition** — UUID re-use should not happen. The WARN level, not ERROR, reflects that the *dispatch* succeeded; only the *trace write* degraded. ERROR would over-alert in monitoring.
- **`O_EXCL` is the right primitive.** Atomic create-or-fail eliminates the race between two concurrent dispatches that, by some catastrophe, generated the same UUID. Both writes can't win; the first wins, the second WARNs.
- **`reason="trace_file_exists"` is grep-stable.** Operators investigating recurring collisions can `grep "trace_file_exists" structlog.log | wc -l` to quantify the problem. A free-form message would not.
- **Pointing the Graphiti entity at the pre-existing file** keeps the new dispatch's entry queryable — the meta-reasoner finds *some* trace data, even if it's the older one. Better than a dangling `TraceRef` to a path that has the new content but a sha256 mismatch.
- **The dispatch outcome doesn't change.** Reasoning model and operator UX are unaffected; this is purely a writer-internal policy.

## Alternatives considered

| Option | Why not |
|---|---|
| Overwrite silently | Destroys prior trace data — direct violation of ADR-FLEET-001 "Do-not-reopen" |
| Overwrite with `WARN` | Still destroys the prior trace; the WARN doesn't make the data come back |
| Append a suffix (`{decision_id}.1.json`, `.2.json`, …) | Multiplies filesystem entries on UUID re-use; the Graphiti entity can only point at one path; fan-out would corrupt the 1:1 invariant DDR-018 pins |
| Hard-fail the dispatch (raise / return ERROR) | Overcorrects — the dispatch itself succeeded; the trace is supplementary. Failing the user-facing tool path because of a writer-internal collision violates ADR-ARCH-021's "tools degrade gracefully" posture |
| ERROR log level | Over-alerts on what is a recoverable, non-user-facing degradation. WARN matches DDR-019's fire-and-forget posture |
| Compare content and skip if identical, WARN if different | Unnecessary complexity; identical content implies the same dispatch wrote the same trace twice (process-restart replay), which is itself a signal worth logging. Treating both cases uniformly keeps the policy simple |
| Move the existing file to a `.collision/` subdirectory before writing | Adds a second filesystem op + directory tree; introduces a new failure mode (the move itself can fail). The original-preservation policy with WARN is simpler and equally safe |
| Make collision behaviour operator-tunable (config flag) | Premature; one correct behaviour for v1 is better than two configurable ones. Revisit if `jarvis.learning` (FEAT-J008) surfaces an operational reason to differ |

## Consequences

- `RoutingHistoryWriter._offload_to_filesystem` uses `O_CREAT | O_EXCL` semantics; on `FileExistsError`, runs the WARN path and points `TraceRef` at the pre-existing file (re-reading it for size + sha256).
- The `WARN routing_history_write_failed reason=trace_file_exists` line is testable via `tests/test_routing_history_schema.py::test_trace_file_collision_preserves_original` (or equivalent — name not pinned by this DDR).
- Test coverage: pre-create a target file, attempt offload of a different entry with the same `decision_id`, assert (a) original file content unchanged, (b) WARN line emitted with the expected fields, (c) Graphiti entity references the original `TraceRef`.
- Operators monitoring `WARN routing_history_write_failed reason=trace_file_exists` get a defective-UUID-generator signal. If frequency exceeds 0 per million dispatches in production, that's a follow-up DDR territory.
- FEAT-JARVIS-005's `queue_build` writer inherits the same policy verbatim — same `RoutingHistoryWriter` class, same offload path, same collision behaviour.
- FEAT-JARVIS-011 (v1.1 `jarvis purge-traces`) is unaffected — it walks `TraceRef.path` and deletes; collision history is not retained anywhere except the WARN log.

## Status

Accepted at FEAT-JARVIS-004 (promotion of ASSUM-009 — originally low-confidence operator-decidable policy — to a binding decision). Append-only — change requires a new DDR.
