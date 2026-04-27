# DDR-019 — Per-dispatch fire-and-forget Graphiti writes; WARN on failure

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** [ADR-FLEET-001](../../../../../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md), ADR-ARCH-021 (tools return structured errors), [DDR-018](DDR-018-routing-history-schema-authoritative.md), [DDR-021](DDR-021-nats-unavailable-soft-fail.md)

## Context

Trace-richness per ADR-FLEET-001 means every dispatch writes a `JarvisRoutingHistoryEntry` to Graphiti. The naive implementation — `await graphiti.add_episode(entry)` inline in the dispatch path — couples dispatch latency to Graphiti write latency. Graphiti latency is bounded by FalkorDB on GB10 + Tailscale RTT + Graphiti's own LLM-driven entity-extraction. Worst-case it can take seconds.

Two open questions:

1. **Per-dispatch vs. batched.** Per-dispatch keeps the trace-record-to-decision relationship 1:1 and simple to reason about; batching reduces Graphiti load but introduces ordering / loss complexity.
2. **Failure handling.** If Graphiti is unreachable, do we (a) fail the dispatch, (b) error-log and continue, (c) warn-log and continue?

ADR-FLEET-001 §Consequences ("Negative") names "write latency" as a known cost mitigated by "async writes where possible". The supervisor-side reasoning loop is latency-sensitive — Rich is waiting for the dispatch result.

## Decision

1. **Per-dispatch, fire-and-forget async writes.** At the dispatch boundary:
   ```python
   asyncio.create_task(routing_history_writer.write_specialist_dispatch(entry))
   # Returns immediately; writer task runs concurrently with the supervisor's next turn.
   ```
   No `await`. The dispatch tool returns to the supervisor without waiting for Graphiti.
2. **`WARN` (not `ERROR`) on write failure.** If `graphiti.add_episode` raises, the writer logs:
   ```
   WARN routing_history_write_failed reason=<exception class> decision_id=<uuid>
   ```
   No retry, no buffer-and-replay in v1. The trace is lost for that record. Dispatch is unaffected.
3. **Graphiti unreachable at startup → soft-fail.** `routing_history_writer.graphiti_client` is `None`; subsequent `.write(...)` calls log WARN once (deduplicated per process) and return. Jarvis still runs.
4. **Bounded shutdown drain.** `shutdown(state)` calls `routing_history_writer.flush(timeout=5.0)` — drains in-flight write tasks for up to 5s, then logs `WARN routing_history_flush_timeout` and abandons. Avoids hanging shutdown on a wedged Graphiti.
5. **No write batching in v1.** Each dispatch produces one Graphiti write. Revisit if write rate consistently saturates Graphiti — `jarvis.learning` will surface this signal.

## Rationale

- **Per-dispatch matches the schema's 1:1 decision-to-entry shape.** Batching introduces ordering complexity and a buffer-loss-on-crash failure mode that's hard to reason about during operations.
- **Fire-and-forget keeps dispatch latency on the supervisor's hot path.** A 2s Graphiti write should not become 2s of latency Rich waits for.
- **`WARN` not `ERROR` because the trace is not load-bearing for runtime correctness.** The supervisor still produces a correct answer; only the learning substrate degrades. `ERROR` would alert operators on transient FalkorDB hiccups; `WARN` is the right severity for "operational signal worth watching, not a runtime failure".
- **Bounded shutdown drain prevents hanging tests + CI.** 5s is generous for a healthy Graphiti and doesn't block obvious failures forever.
- **No batching in v1 — YAGNI.** Solo-operator load won't saturate Graphiti. If it does, a `RoutingHistoryWriter` v2 with bounded queue + batch flush is an internal change that doesn't touch the schema.

## Alternatives considered

| Option | Why not |
|---|---|
| `await` inline (synchronous write) | Couples dispatch latency to Graphiti latency; degrades attended UX |
| `ERROR` log on write failure | Wrong severity — alerts on transient hiccups; trace is not load-bearing for runtime |
| Retry with backoff on write failure | Adds complexity; v1 favours observable signal over hidden self-healing. Operator can re-issue the dispatch if needed |
| Buffer-and-replay (write to local queue, drain when Graphiti recovers) | Adds persistent state (where does the buffer live? memory? disk?); complicates ADR-ARCH-008 (no SQLite). Revisit in v1.5 if needed |
| Fail dispatch on Graphiti unavailable | Makes dispatch transitively dependent on Graphiti; defeats the soft-fail spirit (Jarvis dispatches when its peers are healthy regardless of its own learning substrate) |
| Batch per-session | Loses the `recent_session_refs` capture point if batch flush spans sessions; adds drop-on-crash risk |

## Consequences

- Dispatch tool latency is bounded by NATS round-trip + supervisor reasoning, not by Graphiti.
- A Graphiti outage is observable via `WARN routing_history_write_failed` log lines; operator can correlate with Graphiti / FalkorDB health.
- Trace records *can* be lost during outages — explicitly acceptable per ADR-FLEET-001 (compounding value, not transactional integrity). The lost-record rate is the operational signal.
- `tests/test_graphiti_unavailable.py` asserts: dispatches succeed, WARN logged, no ERROR raised, Jarvis stays up.
- `tests/test_routing_history_writer.py` asserts: write task scheduled with `create_task`, dispatch returns before write completes, exceptions in the task surface as WARN logs.
- The Graphiti client lifecycle (connection pool, reconnect) is owned by `RoutingHistoryWriter` — not exposed at the supervisor API.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. Reasonable v2 evolution (batching, retry-with-backoff, buffer-and-replay) is via append-only DDR if `jarvis.learning` shows persistent loss.
