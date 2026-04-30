# API-tools — Tool surface deltas (FEAT-JARVIS-005)

> **Owner:** [FEAT-JARVIS-005 design §3](../design.md)
> **Predecessor:** [../FEAT-JARVIS-004/contracts/API-tools.md](../../FEAT-JARVIS-004/contracts/API-tools.md)

This document captures the **single tool delta** introduced by FEAT-JARVIS-005. `queue_build` exists today (Phase 2 / FEAT-J004); FEAT-J005 swaps the body, not the contract. Per scope-doc §"Do-Not-Change", the reasoning model's view of the world is identical.

---

## 1. `queue_build` — body swap, contract unchanged

**Signature** — unchanged:

```python
@tool(parse_docstring=True)
def queue_build(
    feature_id: str,
    feature_yaml_path: str,
    repo: str,
    branch: str = "main",
    originating_adapter: str = "terminal",
    correlation_id: str | None = None,
    parent_request_id: str | None = None,
) -> str: ...
```

**Docstring deltas** (only):

- The Phase 2 paragraph `"In Phase 2 the transport is stubbed: the tool builds a real BuildQueuedPayload per nats-core, logs it, and returns a canned ACK. FEAT-JARVIS-005 replaces the stub with a real pipeline.build-queued.{feature_id} JetStream publish without changing this docstring."` is **deleted**. The transport swap has happened.
- Three new **return-shape lines** in the structured-error documentation:
  - `DEGRADED: dispatch_overloaded — wait and retry` (DDR-020 reuse — semaphore overflow)
  - `DEGRADED: transport_unavailable — NATS connection failed` (DDR-021 — NATS soft-fail)
  - `DEGRADED: transport_unavailable — JetStream publish failed` (DDR-025 — PubAck timeout / publish error)

**Behavioural contract** — see [design §8 — runtime sequence](../design.md). Key invariants preserved:

1. Never raises — every error path returns a structured string per ADR-ARCH-021.
2. `correlation_id` auto-generated when omitted (ASSUM-001 — one CSPRNG read per call).
3. Validation paths preserved: `feature_id` matches `^FEAT-[A-Z0-9]{3,12}$`; `repo` matches `^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$`; `originating_adapter` ∈ allowed set.
4. `triggered_by="jarvis"` hardcoded.
5. Phase 2 return shape on success (`QueueBuildAck` JSON) preserved verbatim:
   ```json
   {
     "feature_id": "FEAT-XXX",
     "correlation_id": "uuid4",
     "queued_at": "ISO8601",
     "publish_target": "pipeline.build-queued.FEAT-XXX",
     "status": "queued"
   }
   ```

**New behavioural contract additions:**

- **Concurrency cap** — `queue_build` now acquires the same `dispatch_semaphore` (cap=8) used by `dispatch_by_capability`. Overflow → `DEGRADED: dispatch_overloaded — wait and retry` synchronously (no block). DDR-020 docstring already named both tools as cap-bound; FEAT-005 honours it.
- **Real JetStream publish** — `await asyncio.wait_for(nats.js.publish(subject, envelope.model_dump_json().encode()), timeout=config.pipeline_publish_timeout_seconds)`. PubAck-as-receipt; not delivery confirmation. Default 5s timeout. DDR-025.
- **Adapter from session** — when an active `Session` is available via `_resolve_current_session()` (FEAT-J004 hook), `originating_adapter` is overridden to match `Session.adapter`. The arg becomes a fallback only for sessionless paths (unit tests, the rare scripted call). DDR-031.
- **Correlation registration** — on a successful publish, the resolved `correlation_id` is registered with the `ForgeNotificationsSubscriber` (in-process call) so subsequent `pipeline.stage-complete.{feature_id}` events route back to the originating session.
- **Routing-history fire-and-forget** — every dispatch (success / NATS-down / publish-timeout) writes a `JarvisRoutingHistoryEntry` with `subagent_type="forge_build_queue"`, `subagent_task_id == correlation_id`. Fire-and-forget per DDR-019.

**Phase 2 swap-point retirement:**

The `LOG_PREFIX_QUEUE_BUILD` constant in `tools/dispatch.py` is **deleted**. The `logger.info("JARVIS_QUEUE_BUILD_STUB ...")` line is replaced by the `await js.publish(...)` body. The grep-invariant test (`tests/test_no_phase_2_stub_anchors.py`, FEAT-J004 carry-forward) is extended to assert the constant's absence — same anchor pattern that retired `LOG_PREFIX_DISPATCH` in TASK-J004-020.

---

## 2. Other tools — unchanged

`dispatch_by_capability`, `list_available_capabilities`, `capabilities_refresh`, `capabilities_subscribe_updates`, `escalate_to_frontier`, `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` — all preserved verbatim from FEAT-JARVIS-004.

The supervisor prompt section that teaches DEGRADED-handling needs no edit; the new error strings follow the same shape the reasoning model already routes against.

---

*"The reasoning model's view of the world is identical between Phase 2 (stubbed) and Phase 3 (real JetStream). Only the transport behind the seam swaps."* — [phase3-fleet-integration-scope.md §Do-Not-Change](../../../research/ideas/phase3-fleet-integration-scope.md)
