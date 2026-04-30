# API-events — NATS event surface (FEAT-JARVIS-005)

> **Owner:** [FEAT-JARVIS-005 design §3](../design.md)
> **Wire-format authority:** All payloads are `nats_core` Pydantic models — emitted and consumed verbatim. No Jarvis-specific extensions on the wire.
> **Predecessor:** [../FEAT-JARVIS-004/contracts/API-events.md](../../FEAT-JARVIS-004/contracts/API-events.md) — extends without contradiction.

---

## 1. Subjects — what Jarvis publishes / subscribes / bridges in FEAT-JARVIS-005

| Subject | Direction | Payload | Frequency | Notes |
|---|---|---|---|---|
| `pipeline.build-queued.{feature_id}` | **Publish** | `nats_core.MessageEnvelope` wrapping `nats_core.events.BuildQueuedPayload` | Per `queue_build` invocation | JetStream — durable in `PIPELINE` stream per Forge ADR-SP-017 (7-day retention). Singular per ADR-SP-016. |
| `pipeline.stage-complete.>` | **Subscribe** | `nats_core.MessageEnvelope` wrapping `nats_core.events.StageCompletePayload` | Per Forge stage-complete event | JetStream **ephemeral push** consumer with `deliver_policy=NEW` per DDR-027. Auto-ack (no `manual_ack`). |
| `jarvis.notification.forge-stage-complete.{correlation_id}` | **In-process bridge** (NOT published to NATS in v1) | `ForgeNotification` (in-process Pydantic model, see [DM-forge-notification.md](../models/DM-forge-notification.md)) | Per matched stage-complete | Method-call boundary on `SessionManager.enqueue_notification`; FEAT-J006 promotes to a real NATS subject. |

### FEAT-JARVIS-004 subjects — preserved unchanged

`fleet.register`, `fleet.deregister`, `fleet.heartbeat.jarvis`, `agents.command.{agent_id}`, `agents.result.{agent_id}`, `$KV.agent-registry.>` — all preserved verbatim from FEAT-J004; no behavioural change in this feature.

### Not in FEAT-JARVIS-005

- `pipeline.build-started.>`, `pipeline.build-progress.>`, `pipeline.build-paused.>`, `pipeline.build-resumed.>`, `pipeline.build-complete.>`, `pipeline.build-failed.>`, `pipeline.build-cancelled.>` — Forge publishes all eight outbound subjects per [API-nats-pipeline-events.md §3.1](../../../../forge/docs/design/contracts/API-nats-pipeline-events.md). v1 only subscribes to `stage-complete.>` per scope-doc §FEAT-005 Change 2. The `StageCompletePayload.status ∈ {PASSED, FAILED, GATED, SKIPPED}` already covers the failure-equivalent semantics for the per-stage view; v1.5 may extend coverage to terminal subjects (`build-complete`, `build-failed`, `build-cancelled`) when a richer end-of-build summary line is needed. ASSUM-NOTIFICATION-COVERAGE.
- `pipeline.stage-gated.>` — Forge publishes it; not subscribed in v1 (no human-in-the-loop approval flow on the Jarvis side until FEAT-J008's `CalibrationAdjustment` approvals).
- `agents.approval.>` — out of scope for FEAT-J005.

---

## 2. Payload shapes — exact references

All payloads are **imported verbatim** from `nats_core`. Jarvis does not redefine them. Pinned versions per Phase 2 / FEAT-J004 (`nats-core>=X.Y,<X+1.0` in `pyproject.toml`).

### 2.1 `nats_core.events.BuildQueuedPayload` (publish)

Used for the outbound build-queue publish on `pipeline.build-queued.{feature_id}`. Shape (key fields — full schema in [nats-core/src/nats_core/events/_pipeline.py](../../../../nats-core/src/nats_core/events/_pipeline.py)):

```python
class BuildQueuedPayload(BaseModel):
    feature_id: str         # validated against ^FEAT-[A-Z0-9]{3,12}$
    repo: str               # validated against ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$
    branch: str             # default "main"
    feature_yaml_path: str
    triggered_by: Literal["cli", "jarvis", "forge-internal", "notification-adapter"]   # always "jarvis" from queue_build
    originating_adapter: OriginatingAdapter | None
        # When triggered_by == "jarvis", the validator ENFORCES non-None.
        # Resolved at the call site from Session.adapter per DDR-031.
    correlation_id: str
    parent_request_id: str | None
    requested_at: datetime
    queued_at: datetime
    max_turns: int = 5
    sdk_timeout_seconds: int = 1800
    wave_gating: bool = False
    config_overrides: dict[str, Any] | None = None
    retry_count: int = 0    # publishers leave at 0; Forge increments on redelivery
    originating_user: str | None
```

Constructed inside `tools/dispatch.queue_build` from the tool's arguments + the resolved `Session`. Wrapped in `MessageEnvelope(source_id="jarvis", event_type=EventType.BUILD_QUEUED, ...)` per the Phase 2 invariant.

### 2.2 `nats_core.events.StageCompletePayload` (subscribe)

Used for the inbound stage-complete consumption on `pipeline.stage-complete.>`:

```python
class StageCompletePayload(BaseModel):
    feature_id: str
    build_id: str
    stage_label: str                                      # reasoning-model-chosen; e.g. "plan-complete"
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    gate_mode: Literal["AUTO_APPROVE", "FLAG_FOR_REVIEW", "HARD_STOP", "MANDATORY_HUMAN_APPROVAL"] | None
    coach_score: float | None
    duration_secs: float
    completed_at: str                                     # ISO 8601 timestamp
    correlation_id: str                                   # matches the originating BuildQueuedPayload.correlation_id
```

Validated via `StageCompletePayload.model_validate(envelope.payload)` after `MessageEnvelope.model_validate_json(msg.data)` succeeds.

---

## 3. Reply / ack semantics

### Publish — `pipeline.build-queued.{feature_id}`

- **JetStream** — `await nats.js.publish(subject, payload_bytes, timeout=config.pipeline_publish_timeout_seconds)`.
- **PubAck-as-receipt** — a successful `PubAck` confirms JetStream stored the message in the `PIPELINE` stream. It does **NOT** confirm that Forge consumed it (LES1 parity rule per Forge contract). Jarvis's success surface to the supervisor is "queued", not "started" or "delivered".
- **Timeout** — `asyncio.wait_for` wraps the publish at the supervisor side (5s default). Failure → `DEGRADED: transport_unavailable — JetStream publish failed` per DDR-025.
- **No retry at the publisher level** — DDR-025 says no retry in v1; the operator can re-issue the dispatch if needed.
- **`source_id="jarvis"`** on every emitted envelope (audit-trail invariant; verified by contract test).

### Subscribe — `pipeline.stage-complete.>`

- **Ephemeral JetStream push consumer** per DDR-027:
  ```python
  await nats.js.subscribe(
      subject="pipeline.stage-complete.>",
      deliver_policy=DeliverPolicy.NEW,    # no replay on Jarvis restart
      # No `durable=` — ephemeral consumer; cleaned up automatically
      # when the subscription drains.
      manual_ack=False,                    # auto-ack on return from _on_message
      cb=self._on_message,
  )
  ```
- **Deliver policy `NEW`** — Jarvis only sees stage-complete events emitted *after* its own consumer was created. Forge's 7-day retention on the `PIPELINE` stream is unaffected by Jarvis's ephemeral consumer.
- **Auto-ack** — the in-process bridge to the CLI is not durable; redelivery wastes JetStream's ack budget on retries that cannot improve the outcome. If `_on_message` raises mid-handler, the writer's WARN-only path catches it and the message is still acked.
- **`source_id` verification** — every consumed envelope must have `source_id == "forge"`; mismatches log `WARN forge_notifications_unexpected_source` and the message is dropped (still acked).

### Bridge — `jarvis.notification.forge-stage-complete.{correlation_id}` (in-process)

- **Method-call boundary** in v1, not a NATS subject. The router resolves the correlation map and calls `SessionManager.enqueue_notification(session_id, ForgeNotification)`.
- **No ack semantics** — direct method call.
- **FEAT-J006 (Telegram)** promotes this to a real NATS subject under `jarvis.notification.{adapter}` (per ARCHITECTURE.md §7); the router seam in `forge_notifications.py` is the single place that change lands. The internal `ForgeNotification` Pydantic model becomes the wire payload at that point.

---

## 4. Subject naming — pinned conventions

Per [ADR-SP-016](../../../../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md) singular topic convention (Forge inheritance):

- ✅ `pipeline.build-queued.FEAT-JARVIS-INTERNAL-001` (singular `pipeline`, singular `build-queued`)
- ✅ `pipeline.stage-complete.FEAT-JARVIS-INTERNAL-001`
- ✅ `pipeline.stage-complete.>` (wildcard subscription on the family)
- ❌ Never `pipelines.*` or `pipeline.builds-queued.*` — plural forms reject at the `nats_core.Topics` constructor.

`nats_core.Topics.Pipeline.BUILD_QUEUED.format(feature_id=...)` and `nats_core.Topics.Pipeline.STAGE_COMPLETE.format(feature_id=...)` are the canonical formatters; Jarvis uses them verbatim. Hard-coded subject strings are forbidden — the contract test `tests/test_contract_nats_core.py` (FEAT-J004 carry-forward, extended in FEAT-J005) asserts every subject Jarvis emits is produced by a `nats_core.Topics.*` formatter.

---

## 5. Contract tests — `tests/test_contract_nats_core.py` extensions

These tests are the cross-repo handshake, extended from the FEAT-J004 set:

1. **(FEAT-J005 swap)** `test_build_queued_payload_emitted_matches_nats_core` — the FEAT-J004 test that exercised the Phase 2 stub builder is upgraded: the real `js.publish` path is exercised against a mock JetStream consumer; emitted bytes deserialise cleanly via `nats_core.events.BuildQueuedPayload`; every field populated; `triggered_by="jarvis"`; `originating_adapter` matches the active session's adapter.
2. **(NEW)** `test_stage_complete_payload_consumed_matches_nats_core` — synthetic stage-complete payload built from `nats_core.events.StageCompletePayload(...)` round-trips through `ForgeNotificationsSubscriber._on_message` without `ValidationError`; the resulting `ForgeNotification` populates every field.
3. **(NEW)** `test_envelope_source_id_jarvis_on_publish` — every emitted `MessageEnvelope.source_id == "jarvis"` (audit-trail invariant; FEAT-J004 test covered the request/reply path; this test extends to the JetStream publish path).
4. **(NEW)** `test_envelope_source_id_forge_on_subscribe` — incoming envelopes with `source_id != "forge"` are dropped with WARN; only `source_id == "forge"` envelopes propagate to the bridge.
5. **(NEW)** `test_topic_subjects_match_topics_class_pipeline` — every `pipeline.build-queued.*` and `pipeline.stage-complete.>` subject string Jarvis emits or subscribes to is produced by a `nats_core.Topics.Pipeline.*` formatter; never hard-coded.
6. **(extended)** `test_no_phase_2_stub_anchors` — extended to assert the `LOG_PREFIX_QUEUE_BUILD` constant is removed from `tools/dispatch.py`. Mirrors how FEAT-J004 retired `LOG_PREFIX_DISPATCH` (TASK-J004-020).

---

## 6. Notes on Forge's contract observance

Forge's [API-nats-pipeline-events.md](../../../../forge/docs/design/contracts/API-nats-pipeline-events.md) defines the consumer side; Jarvis's contract is the publisher side. Cross-repo invariants this design honours:

- **`feature_id` regex** — `^FEAT-[A-Z0-9]{3,12}$` validated by Jarvis at the tool boundary AND by Forge's consumer; mismatches surface as Forge's `pipeline.build-failed` with `failure_reason="malformed BuildQueuedPayload"`.
- **`feature_yaml_path` allowlist** — Jarvis does NOT validate the path; Forge's permission check at consume time (per its API-nats-pipeline-events.md §2.3 step 3) is the authoritative gate. If Forge rejects the path, Jarvis sees a `pipeline.build-failed.{feature_id}` event — not subscribed in v1, so the rejection is silent on the Jarvis side. ASSUM-PATH-VALIDATION-FORGE.
- **Idempotency** — Forge's consumer deduplicates on `(feature_id, correlation_id)`. Jarvis's correlation generator uses `uuid.uuid4().hex` per call; collisions are astronomically unlikely.
- **Crash recovery (Forge side)** — Forge owns its own redelivery. Jarvis's job is to publish; if Forge restarts after consume but before terminal-ack, Forge will see redelivery; Jarvis is unaffected (the original publish stays in JetStream's 7-day retention).

---

*"Pattern A: Jarvis publishes and walks away; Forge consumes from JetStream."* — [ADR-SP-014 Pattern A](../../../../forge/docs/research/forge-pipeline-architecture.md), [phase3-fleet-integration-scope.md §FEAT-005](../../../research/ideas/phase3-fleet-integration-scope.md)
