# DDR-025 — `queue_build` swaps to real JetStream publish; PubAck-as-receipt; 5s timeout → DEGRADED

- **Status:** Accepted
- **Date:** 2026-04-29
- **Feature:** FEAT-JARVIS-005 (Phase 3 / Fleet Integration — Build Queue Dispatch to Forge)
- **Related:** [Forge ADR-SP-014 Pattern A](../../../../forge/docs/research/forge-pipeline-architecture.md), [Forge API-nats-pipeline-events.md](../../../../forge/docs/design/contracts/API-nats-pipeline-events.md), ADR-ARCH-021 (tools return structured errors), [DDR-009](../../FEAT-JARVIS-002/decisions/DDR-009-stub-transport-semantics.md), [DDR-019](../../FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md), [DDR-020](../../FEAT-JARVIS-004/decisions/DDR-020-concurrent-dispatch-cap-8.md), [DDR-021](../../FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md)

## Context

Phase 2's `queue_build` builds a real `BuildQueuedPayload` (per `nats-core`) and emits a `JARVIS_QUEUE_BUILD_STUB` log line — Forge never sees it. Per [DDR-009](../../FEAT-JARVIS-002/decisions/DDR-009-stub-transport-semantics.md), `tools/dispatch.py` is the single seam for the swap. FEAT-JARVIS-005 retires the queue-build half of that seam (the dispatch-side half retired in TASK-J004-011).

Two design questions to settle:

1. **Publish semantics.** How does Jarvis know the publish landed? Forge's contract names PubAck as a transport-level receipt — *not* delivery confirmation (LES1: PubAck ≠ success). Yet Jarvis must surface "queued" to the supervisor only when there's a real signal that the message is in JetStream.
2. **Failure handling.** What happens when the publish times out, the broker is in transient drain, or JetStream returns an error?

Forge's [forge-pipeline-architecture.md](../../../../forge/docs/research/forge-pipeline-architecture.md) is the canonical model: Jarvis publishes; Forge consumes from the durable `PIPELINE` stream; Jarvis does not hold queue position. The Phase 2 stub already constructed a real `MessageEnvelope` + `BuildQueuedPayload`; only the actual `js.publish` call needs to land.

## Decision

1. **`queue_build` body swaps to a real JetStream publish.** The Phase 2 `logger.info("JARVIS_QUEUE_BUILD_STUB ...")` line is replaced by:
   ```python
   pub_ack = await asyncio.wait_for(
       nats.js.publish(subject, envelope.model_dump_json().encode()),
       timeout=config.pipeline_publish_timeout_seconds,
   )
   ```
   The `LOG_PREFIX_QUEUE_BUILD` constant is **deleted**; the FEAT-J004 grep-invariant test is extended to assert its absence.
2. **PubAck-as-receipt.** A successful `PubAck` confirms JetStream stored the message. It is **NOT** delivery confirmation (Forge has not necessarily consumed it). Jarvis returns `status="queued"` on the basis of PubAck — this matches Forge's own publish semantics and the LES1 parity rule.
3. **5-second publish timeout (default), configurable via `JarvisConfig.pipeline_publish_timeout_seconds`.** On timeout → `DEGRADED: transport_unavailable — JetStream publish failed`. ADR-ARCH-021-compliant structured string; reasoning model handles it via the existing DEGRADED branch.
4. **No retry in v1.** Operator can re-issue the dispatch via the supervisor if needed. Same posture as `dispatch_by_capability`'s timeout (DDR-017's redirect is for *specialist* dispatch — JetStream publishes don't have a redirect-equivalent).
5. **Routing-history fire-and-forget on every outcome.** Success / NATS-down / publish-timeout all write a `JarvisRoutingHistoryEntry` with `subagent_type="forge_build_queue"`. Per DDR-019.
6. **Semaphore-acquired** — `queue_build` shares the dispatch semaphore (DDR-020 cap=8) with `dispatch_by_capability`. Overflow → `DEGRADED: dispatch_overloaded`.

## Rationale

- **PubAck-as-receipt is the right surface for the supervisor.** "Queued" is a verifiable claim once JetStream stores the message; "delivered" or "started" would require subscribing to `pipeline.build-started.*` to round-trip — out of scope for v1 per FEAT-J005 design §1. The reasoning model has skin in the game ("the build is queued, not started; expect delay") via the existing tool docstring.
- **5s is the right default timeout for a healthy local broker.** Forge's contract is "fire-and-forget" — typical PubAck on a healthy NATS-on-GB10 + Tailscale is <100ms. 5s is generous; longer would mask wedged JetStream from the operator.
- **No retry in v1 because retries on JetStream publish are footguns.** A retry on PubAck-timeout could land *two* messages if the original publish actually succeeded but the ack was lost — Forge's idempotency check would dedupe at consume, but Jarvis would have written two routing-history entries with different `correlation_id`s. v1.5 may add reconciliation if this becomes a real operational signal.
- **Semaphore reuse** — DDR-020's docstring already named both `dispatch_by_capability` and `queue_build` as cap-bound. FEAT-005 honours it without changing the cap.
- **Structured DEGRADED string** — same shape as DDR-021's `transport_unavailable`. The reasoning model already routes against this string format.

## Alternatives considered

| Option | Why not |
|---|---|
| Subscribe to `pipeline.build-started.{feature_id}` and only return "started" | Adds a synchronous wait against Forge's pull-consumer latency; defeats Pattern A "fire and forget"; adds correlation tracking complexity for a marginal supervisor-UX gain. v1.5 territory. |
| No timeout (rely on nats-py default) | Default depends on `nats-py` version; could be unbounded; reasoning model would block the supervisor turn. |
| Retry-on-timeout with exponential backoff | Risks duplicate publishes (PubAck loss masquerading as failure); Forge's idempotency would catch it but Jarvis's routing-history would diverge. |
| ERROR (not DEGRADED) on publish failure | Wrong severity. The supervisor *can* recover (re-issue at user request); ERROR would alert on transient hiccups. DEGRADED is the right fit per ADR-ARCH-021's degraded-modes-as-reasoning-inputs posture. |
| Skip the semaphore for `queue_build` | DDR-020 already specifies both tools share the cap. Skipping would defeat the cross-tool capacity guard and let runaway loops bypass the throttle. |

## Consequences

- `tools/dispatch.py::queue_build` body becomes a real publish; the `LOG_PREFIX_QUEUE_BUILD` constant is removed in the same commit.
- `tests/test_dispatch_queue_build.py` Phase 2 stub-path tests are deleted; replaced with integration tests using an in-process JetStream test server.
- `tests/test_no_phase_2_stub_anchors.py` (FEAT-J004 carry-forward) extended to assert `LOG_PREFIX_QUEUE_BUILD` absence — same anchor pattern that retired `LOG_PREFIX_DISPATCH` in TASK-J004-020.
- Supervisor prompt section's structured-error documentation grows two lines (`DEGRADED: transport_unavailable — JetStream publish failed` + `DEGRADED: dispatch_overloaded — wait and retry`); the reasoning model handles them via the existing DEGRADED branch.
- `tests/test_end_to_end_forge_roundtrip.py` (Phase 3 close criterion #10) is the soft-prereq end-to-end gate — closes when Rich-chosen FEAT-JARVIS-INTERNAL feature flows.

## Status

Accepted at FEAT-JARVIS-005 `/system-design`. Reconnect / retry strategy is a v1.5 candidate via append-only DDR if real-world publish-timeout rate becomes a problem.
