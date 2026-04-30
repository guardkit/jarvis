# FEAT-JARVIS-005 — Design

> **Feature:** Build Queue Dispatch to Forge (real transport + Forge progress feedback loop)
> **Phase:** 3 (Fleet Integration) — closes Phase 3.
> **Generated:** 2026-04-29 via `/system-design FEAT-JARVIS-005`
> **Status:** Proposed — input to `/feature-spec FEAT-JARVIS-005`
> **Architecture source:** [../../architecture/ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) (v1.0, 2026-04-20, 30 ADRs)
> **Scope source:** [../../research/ideas/phase3-fleet-integration-scope.md](../../research/ideas/phase3-fleet-integration-scope.md)
> **Build plan:** [../../research/ideas/phase3-build-plan.md](../../research/ideas/phase3-build-plan.md)
> **Predecessor design:** [../FEAT-JARVIS-004/design.md](../FEAT-JARVIS-004/design.md) — load-bearing
> **Forge contract:** [../../../../forge/docs/design/contracts/API-nats-pipeline-events.md](../../../../forge/docs/design/contracts/API-nats-pipeline-events.md)

---

## 1. Purpose

FEAT-JARVIS-005 closes the Jarvis → Forge loop. Phase 2's `queue_build` builds a real `BuildQueuedPayload` (via `nats-core`) but emits only a `JARVIS_QUEUE_BUILD_STUB` log line — Forge never sees it. This feature swaps the stub for a real JetStream publish to `pipeline.build-queued.{feature_id}` per Forge ADR-SP-014 Pattern A, **and** subscribes to the eight outbound `pipeline.*` lifecycle subjects so Rich can see Forge's progress surface back into `jarvis chat` between prompts.

It is also where the second half of the FEAT-JARVIS-004 routing-history substrate lights up: every `queue_build` writes a `subagent_type="forge_build_queue"` `JarvisRoutingHistoryEntry`, and every matching `pipeline.stage-complete.*` event lands as an **append-only edge** on that entry (the entry itself stays `frozen=True` per [DDR-018](../FEAT-JARVIS-004/decisions/DDR-018-routing-history-schema-authoritative.md)).

`queue_build`'s tool signature, docstring, and return shape are **unchanged** from Phase 2. The reasoning model's view of the world is identical — only the transport behind the seam swaps and a side-effect path opens (the routing-history write).

This design closes the Phase 3 close criterion #10 (Rich-chosen FEAT-JARVIS-INTERNAL feature queued, consumed, stage-complete notifications flowed, result visible in `jarvis chat`) — the end-to-end test that gates Phase 3 closure lives on this feature.

One-line success criterion: *Jarvis publishes `BuildQueuedPayload` to JetStream, subscribes to `pipeline.stage-complete.>`, surfaces correlation-matched events back to Rich's CLI between prompts, and writes append-only Graphiti edges on the originating routing-history entry — without changing the reasoning model's tool surface.*

---

## 2. Scope in-context

Jarvis has seven bounded contexts per [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-seven-bounded-contexts.md). FEAT-JARVIS-005 is **Fleet Dispatch Context (queue half)** + **Adapter Interface Context (read-side notifications)** with a small extension to the Knowledge Context.

| Bounded context | FEAT-JARVIS-005 touches? | How |
|---|---|---|
| **Fleet Dispatch Context** | **IN — core** | Real `queue_build` JetStream publish; PubAck-as-receipt; correlation-tracking; routing-history write |
| **Adapter Interface Context** | **IN — core** | `pipeline.stage-complete.>` subscriber → in-process `jarvis.notification.forge-stage-complete.*` router → `SessionManager.pending_notifications` → CLI between-prompt rendering |
| **Knowledge Context** | extended | Append-only edges (`stage_complete`) on the `JarvisRoutingHistoryEntry` originating each build |
| **Sessions** | extended | `SessionManager.pending_notifications(session_id) -> list[Notification]`; `end_session` clears the queue |
| **Jarvis Reasoning Context** | unchanged | Tool docstring, supervisor prompt sections preserved verbatim |
| **Config (cross-cutting)** | extended | `forge_notifications_queue_cap` (default 100); `pipeline_publish_timeout_seconds` (default 5) |
| Ambient / Learning / External Tool contexts | untouched | FEAT-J006/008+ territory |

See [phase3-fleet-integration-scope.md §Do-Not-Change](../../research/ideas/phase3-fleet-integration-scope.md) — FEAT-J004 outputs (`NATSClient`, `RoutingHistoryWriter`, `CapabilitiesRegistry`, fleet registration, dispatch semaphore, `JarvisRoutingHistoryEntry`) are preserved verbatim. The **only** behavioural-surface changes are: `queue_build`'s docstring delta (deletes the Phase 2 stub paragraph; adds two `DEGRADED:` lines), `lifecycle.startup` adds a notification-subscriber start step, and `cli/main.py`'s REPL prints zero-or-more notification lines before reading the next prompt.

---

## 3. Surfaces shipped

| Surface | Type | Artefact |
|---|---|---|
| DeepAgents tool surface (`queue_build` body swap; docstring delta only) | in-process — docstring is the contract | [contracts/API-tools.md](contracts/API-tools.md) |
| Internal Python API (Forge notifications subscriber, notification router, SessionManager extensions, CLI rendering helpers, RoutingHistoryWriter completions) | in-process | [contracts/API-internal.md](contracts/API-internal.md) |
| NATS event contracts (consumed + emitted on the wire; one in-process internal subject) | wire + in-process | [contracts/API-events.md](contracts/API-events.md) |

**No new network protocols at the Jarvis level.** All NATS traffic uses `nats-core`'s singular topic convention (ADR-SP-016): `pipeline.build-queued.{feature_id}`, `pipeline.stage-complete.>`. All Pydantic models on the wire are `nats_core` originals — verbatim, no Jarvis extensions. Per the FEAT-JARVIS-001..004 precedent, no `openapi.yaml`, no `mcp-tools.json`, no `a2a-schemas.yaml`. The `langgraph.json` from FEAT-JARVIS-003 is unchanged. The internal subject `jarvis.notification.forge-stage-complete.{correlation_id}` is in-process only — not published to NATS in v1 (FEAT-J006 will promote it to a real subject when the Telegram adapter lands).

---

## 4. Data models

| Model | Purpose | Artefact |
|---|---|---|
| `ForgeNotification` (Pydantic v2, frozen) | The in-process notification envelope routed from `pipeline.stage-complete.*` to the CLI. Carries `correlation_id`, `feature_id`, `stage_label`, `status`, `timestamp` plus a render-helper. | [models/DM-forge-notification.md](models/DM-forge-notification.md) |
| `BuildCorrelation` (Pydantic v2, frozen) | One element of the in-memory correlation map: `correlation_id → session_id + adapter + queued_at + feature_id`. | [models/DM-forge-notification.md](models/DM-forge-notification.md) |
| `BuildQueueAck` (already shipped Phase 2 — `dict` literal) | Returned by `queue_build` on success. Shape unchanged from Phase 2; FEAT-005 only confirms the JetStream PubAck before the dict is returned. | (no new file — Phase 2 contract) |
| `BuildQueuedPayload` (`nats_core.events.BuildQueuedPayload`) | The wire type Jarvis publishes to `pipeline.build-queued.{feature_id}`. | imported; no redefinition |
| `StageCompletePayload` (`nats_core.events.StageCompletePayload`) | The wire type Jarvis consumes on `pipeline.stage-complete.>`. | imported; no redefinition |
| `MessageEnvelope` (`nats_core.MessageEnvelope`) | Outer envelope for both publish + subscribe directions. `source_id="jarvis"` on publish; verified `source_id="forge"` on consume (audit-trail invariant). | imported; no redefinition |
| Reused unchanged | `JarvisRoutingHistoryEntry`, `RoutingHistoryWriter`, `NATSClient`, `Session`, `SessionManager` | [../FEAT-JARVIS-004/models/DM-routing-history.md](../FEAT-JARVIS-004/models/DM-routing-history.md), [../FEAT-JARVIS-004/contracts/API-internal.md](../FEAT-JARVIS-004/contracts/API-internal.md) |

---

## 5. Design decisions captured

| DDR | Decision | Why it's here |
|---|---|---|
| [DDR-025](decisions/DDR-025-queue-build-real-transport.md) | `queue_build` swaps to `js.publish(...)` on `pipeline.build-queued.{feature_id}`. PubAck is treated as a transport-level receipt (per Forge LES1: PubAck ≠ delivery). 5-second publish timeout → `DEGRADED: transport_unavailable`. No retry in v1. | Settles the Phase 2 open question. Aligns with Forge's own publish semantics (forge-pipeline-architecture.md). 5s is generous for a healthy local broker; longer would mask wedged JetStream from the operator. |
| [DDR-026](decisions/DDR-026-forge-notifications-module-location.md) | The `pipeline.stage-complete.>` subscriber and the in-process notification router live in a dedicated `infrastructure/forge_notifications.py` module — **not** as a `SessionManager` method. | Symmetric with the `nats_client` / `fleet_registration` / `routing_history` placement. Keeps `SessionManager` focused on session lifecycle; the subscriber is a transport adapter, not a session concern. FEAT-J006 (Telegram) will pick the same router up unchanged. |
| [DDR-027](decisions/DDR-027-stage-complete-ephemeral-deliver-new.md) | The `pipeline.stage-complete.>` JetStream consumer is **ephemeral** with `deliver_policy=NEW`. No replay on Jarvis restart in v1; if Jarvis was restarted mid-build, Forge's terminal events still land in JetStream's 7-day retention but Jarvis silently drops them (the build itself is not affected — Forge owns its own crash-recovery). | Matches ADR-ARCH-009 (sessions are ephemeral) + ADR-ARCH-026 (single instance). Durable consumers add complexity (consumer name lifecycle, replay-on-restart UX) without proportional value when the cross-process feedback loop only matters during the originating session. v1.5 (Telegram durable session per FEAT-J006) revisits. |
| [DDR-028](decisions/DDR-028-correlation-map-in-memory-bounded.md) | The `correlation_id → BuildCorrelation` map is in-memory, LRU-bounded at 1000 entries. Lost on Jarvis restart per DDR-027. Eviction logs `WARN forge_correlation_evicted` so saturation is observable. | ADR-ARCH-008 (no SQLite) preserved. 1000 is ~3 days of solo-operator builds; FEAT-J008 will tighten if real saturation appears. LRU prevents unbounded memory growth on long-running sessions. |
| [DDR-029](decisions/DDR-029-stage-complete-as-append-only-edges.md) | Stage-complete events land as **append-only Graphiti edges** on the originating `JarvisRoutingHistoryEntry`. Edge type = `stage_complete`; edge body = JSON-encoded `StageCompletePayload`. The entry's `frozen=True` invariant from DDR-018 is preserved. | DDR-018 §"Updates from FEAT-J005 stage-complete events go on edges, not field overwrites" pinned this in advance — FEAT-J005 honours it. Edges over field-overwrites means audit-trail integrity holds and FEAT-J008 (`jarvis.learning`) can join across decisions cleanly. |
| [DDR-030](decisions/DDR-030-cli-notifications-between-prompts.md) | CLI notifications render **between prompts only** — never mid-turn. Per-session queue cap = 100 entries; overflow evicts oldest with `WARN forge_notification_queue_overflow`. SIGINT-safe (queue is checked once at REPL top-of-loop). | ASSUM-003 (single-concurrent-invoke per session) holds — the renderer cannot race with `SessionManager.invoke`. 100 caps a runaway-Forge stage stream while preserving useful history for typical builds. The cap is a defensive ceiling, not an expected operating point. |
| [DDR-031](decisions/DDR-031-originating-adapter-from-session.md) | `originating_adapter` is resolved from the active `Session.adapter` at the `queue_build` call site, **not** from the reasoning model's tool argument. The arg becomes a fallback used only when no session is active (tests, sessionless paths). The reasoning model cannot override the session's adapter identity. | Honours `BuildQueuedPayload._adapter_required_for_jarvis` validator (`triggered_by="jarvis"` requires a non-None adapter from the closed enum). Prevents the reasoning model from spoofing a different adapter. The arg-as-fallback preserves Phase 2 unit-test paths where the tool was exercised without a session. |

DDR numbering continues from FEAT-JARVIS-004 (DDR-016..024). FEAT-JARVIS-005 uses DDR-025..031; next available after this design is DDR-032.

---

## 6. Component diagram

[diagrams/forge-feedback-l3.md](diagrams/forge-feedback-l3.md) — C4 Level 3 view of the **Forge Feedback Loop** as it stands after FEAT-JARVIS-005 lands. **Requires explicit approval per `/system-design` Phase 3.5 gate** — the participating components exceed the 3-internal threshold (10 components: `queue_build` tool, `NATSClient.js` JetStream context, `RoutingHistoryWriter` (build-queue path), `ForgeNotificationsSubscriber`, in-process notification router, correlation map, `SessionManager.pending_notifications`, CLI renderer, `pipeline.stage-complete.*` consumer, append-only edge writer).

---

## 7. Module layout — extensions to FEAT-JARVIS-004

Per [ADR-ARCH-006 five-group layout](../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md). FEAT-J004 fully populated `infrastructure/`; FEAT-005 adds **one new module** there (`forge_notifications.py`) and updates four existing modules.

```
src/jarvis/
├── infrastructure/
│   ├── lifecycle.py                            # UPDATED — start ForgeNotificationsSubscriber
│   │                                           #           after fleet registration; stop it
│   │                                           #           before NATS drain on shutdown.
│   ├── forge_notifications.py                  # NEW    — pipeline.stage-complete.> subscriber;
│   │                                           #           correlation map; in-process router;
│   │                                           #           per-session queue handoff to
│   │                                           #           SessionManager.
│   ├── routing_history.py                      # UPDATED — write_build_queue_dispatch (replaces
│   │                                           #           the FEAT-J004 no-op); append_build_queue_event
│   │                                           #           (replaces the no-op) emits append-only
│   │                                           #           Graphiti edges per DDR-029.
│   ├── nats_client.py                          # unchanged — js property already wired
│   ├── fleet_registration.py                   # unchanged
│   ├── capabilities_registry.py                # unchanged
│   └── dispatch_semaphore.py                   # unchanged (queue_build also acquires the cap
│                                               #           per FEAT-J004 §DDR-020 — no
│                                               #           module-level change; only the call
│                                               #           site in tools/dispatch.py grows the
│                                               #           semaphore.try_acquire() guard.)
├── tools/
│   └── dispatch.py                             # UPDATED — queue_build:
│                                               #           - LOG_PREFIX_QUEUE_BUILD constant deleted
│                                               #           - logger.info stub line replaced with
│                                               #             `await js.publish(subject, envelope.model_dump_json().encode())`
│                                               #           - dispatch_semaphore.try_acquire guard
│                                               #             (DDR-020 reuse for queue_build)
│                                               #           - originating_adapter resolved from
│                                               #             current_session() per DDR-031
│                                               #           - routing-history fire-and-forget
│                                               #             via _routing_history_writer.write_build_queue_dispatch
│                                               #           - 5s asyncio.wait_for around js.publish
│                                               #             (DDR-025); failure → DEGRADED string
├── sessions/
│   └── manager.py                              # UPDATED — pending_notifications(session_id) ->
│                                               #           list[ForgeNotification]; end_session
│                                               #           clears the per-session queue.
├── cli/
│   └── main.py                                 # UPDATED — REPL top-of-loop drains
│                                               #           session_manager.pending_notifications;
│                                               #           renders one click.echo line per
│                                               #           notification before reading the next
│                                               #           prompt.
└── config/
    └── settings.py                             # UPDATED — pipeline_publish_timeout_seconds (default 5);
                                                #           forge_notifications_queue_cap (default 100);
                                                #           forge_correlation_map_cap (default 1000).

(no pyproject.toml change — nats-py + graphiti-core landed in FEAT-J004)
```

The Phase 2 `LOG_PREFIX_QUEUE_BUILD` swap-point anchor disappears in the same commit that swaps the publish; its absence is asserted by the FEAT-005 grep invariant test (mirrors how FEAT-J004 retired the dispatch-side anchor in TASK-J004-020). Tool docstring's Phase 2 stub paragraph is deleted; the rest is preserved verbatim.

### What is *not* in this layout

- No new adapter modules. The CLI rendering is a small REPL loop edit; FEAT-J006 (Telegram) introduces a real `adapters/` channel and at that point the in-process `jarvis.notification.forge-stage-complete.*` subject becomes a real NATS subject.
- No new `tests/test_forge_notifications.py` *only* — FEAT-005 adds five new test files (see §9).
- No reachability for `pipeline.stage-complete.>` outside `forge_notifications.py`. The dispatch tool itself never reads from the subscriber; the trace-edge path goes through `RoutingHistoryWriter.append_build_queue_event` only.
- No durable JetStream consumer name. DDR-027 keeps the consumer ephemeral.

---

## 8. Wiring — how lifecycle composes the new substrate

Extends the FEAT-JARVIS-004 wiring sequence. New lines marked `← NEW in FEAT-J005`.

```
JarvisConfig()                                    ← jarvis.config.settings (extended in 005)
    │
    ▼
lifecycle.build_app_state(config):
    │
    ├── … (FEAT-J001..J004 sequence unchanged) …
    │
    ├── nats_client = await NATSClient.connect(config)            (FEAT-J004)
    ├── graphiti_client = await GraphitiClient.connect(config)    (FEAT-J004)
    ├── routing_history_writer = RoutingHistoryWriter(...)        (FEAT-J004)
    ├── fleet_heartbeat_task / register_on_fleet                  (FEAT-J004)
    ├── capabilities_registry = LiveCapabilitiesRegistry / Stub    (FEAT-J004)
    ├── dispatch_semaphore = DispatchSemaphore(cap=8)             (FEAT-J004)
    │
    ├── if nats_client is not None:                                ← NEW in 005
    │     forge_subscriber = ForgeNotificationsSubscriber(         ← NEW in 005
    │         nats_client=nats_client,
    │         routing_history_writer=routing_history_writer,
    │         queue_cap=config.forge_notifications_queue_cap,
    │         correlation_cap=config.forge_correlation_map_cap)
    │     await forge_subscriber.start()                          ← NEW in 005
    │     # JetStream ephemeral push consumer on
    │     # `pipeline.stage-complete.>` per DDR-027.
    │   else:
    │     forge_subscriber = None
    │
    ├── tool_list_attended = assemble_tool_list(                   (UPDATED in 005)
    │       …,
    │       forge_subscriber=forge_subscriber)                    ← NEW in 005
    │
    ├── tool_list_ambient = assemble_tool_list(                    (UPDATED in 005)
    │       …, forge_subscriber=forge_subscriber)
    │
    ├── supervisor = build_supervisor(...)
    ├── session_manager = SessionManager(supervisor, store)
    ├── if forge_subscriber is not None:
    │     forge_subscriber.bind_session_manager(session_manager)  ← NEW in 005
    │     # Subscriber needs the manager to enqueue per-session
    │     # notifications. Late binding keeps construction order
    │     # supervisor → session_manager → subscriber-bind.
    │
    └── return AppState(…, forge_subscriber=forge_subscriber)     ← NEW in 005
```

`shutdown(state)` extends FEAT-J004's surface with one new step (between the heartbeat cancel and the deregister hop):

1. Cancel `fleet_heartbeat_task`. (unchanged)
2. **`await state.forge_subscriber.stop()` ← NEW in 005** — drains the JetStream consumer (bounded at 5s); idempotent.
3. `await deregister_from_fleet(...)`. (unchanged)
4. `await state.capabilities_registry.close()`. (unchanged)
5. `await state.routing_history_writer.flush(...)`. (unchanged — now also drains build-queue edge writes)
6. `await state.nats_client.drain(...)`. (unchanged)
7. `await state.graphiti_client.aclose()`. (unchanged)
8. Disarm Layer-2 hooks. (unchanged)
9. `state.store.close()`. (unchanged)

### `queue_build` runtime sequence (replaces the Phase 2 stub)

```
queue_build(feature_id, feature_yaml_path, repo, branch="main",
            originating_adapter="terminal", correlation_id=None,
            parent_request_id=None):
  1. Validate feature_id, repo, originating_adapter (Phase 2 invariants — preserved).
  2. resolved_correlation_id = correlation_id or new_correlation_id()
  3. session = _resolve_current_session()  # DDR-031
     IF session is not None:
       resolved_adapter = session.adapter  # overrides the arg
     ELSE:
       resolved_adapter = originating_adapter  # arg fallback (test paths)
     started_at = _now_utc()
  4. semaphore.try_acquire()
       on overflow → "DEGRADED: dispatch_overloaded — wait and retry"
  5. TRY:
     a. Build BuildQueuedPayload + MessageEnvelope (Phase 2 path — unchanged).
     b. nats = _nats_client
        IF nats is None:
          fire-and-forget routing-history trace (outcome="transport_unavailable");
          release semaphore;
          return "DEGRADED: transport_unavailable — NATS connection failed"
     c. subject = Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id)
     d. payload_bytes = envelope.model_dump_json().encode()
     e. TRY:
          pub_ack = await asyncio.wait_for(
              nats.js.publish(subject, payload_bytes),
              timeout=config.pipeline_publish_timeout_seconds)
          # PubAck ≠ delivery (Forge LES1) — but it IS confirmation that
          # JetStream stored the message. Without a PubAck we cannot
          # claim "queued".
        EXCEPT TimeoutError | NATSConnectionError:
          fire-and-forget routing-history trace (outcome="transport_unavailable");
          return "DEGRADED: transport_unavailable — JetStream publish failed"
     f. forge_subscriber.register_correlation(
          correlation_id=resolved_correlation_id,
          session_id=session.session_id if session else None,
          feature_id=feature_id,
          adapter=resolved_adapter,
          queued_at=started_at)
     g. fire-and-forget routing-history trace
        (subagent_type="forge_build_queue",
         subagent_task_id=resolved_correlation_id,
         outcome="success",
         outcome_detail={"publish_target": subject,
                         "stream_seq": pub_ack.seq if pub_ack else None})
     h. Return QueueBuildAck JSON (Phase 2 shape — unchanged):
        {"feature_id": ..., "correlation_id": ...,
         "queued_at": ISO8601, "publish_target": subject,
         "status": "queued"}
  6. FINALLY:
     release semaphore.
```

`fire-and-forget` is `asyncio.create_task(routing_history_writer.write_build_queue_dispatch(entry))` — the dispatch never awaits the Graphiti write per [DDR-019](../FEAT-JARVIS-004/decisions/DDR-019-graphiti-fire-and-forget-writes.md).

### `pipeline.stage-complete.*` consumer sequence

```
ForgeNotificationsSubscriber.start():
  1. consumer = await nats.js.subscribe(
         "pipeline.stage-complete.>",
         deliver_policy=NEW,
         # ephemeral — no `durable=` per DDR-027
         manual_ack=False,
         cb=self._on_message)
  2. self._consumer = consumer
  3. logger.info("forge_notifications_subscribed", subject="pipeline.stage-complete.>")

ForgeNotificationsSubscriber._on_message(msg):
  1. envelope = MessageEnvelope.model_validate_json(msg.data)
  2. IF envelope.source_id != "forge":
       logger.warning("forge_notifications_unexpected_source", source_id=envelope.source_id)
       return  # auto-ack still happens
  3. payload = StageCompletePayload.model_validate(envelope.payload)
  4. correlation = self._correlations.get(payload.correlation_id)
     IF correlation is None:
       logger.debug("forge_notifications_no_correlation",
                    correlation_id=payload.correlation_id)
       return  # auto-ack still happens — drop silently
  5. notification = ForgeNotification.from_stage_complete(payload, correlation)
  6. self._session_manager.enqueue_notification(correlation.session_id, notification)
       # SessionManager applies the queue cap per DDR-030; overflow logs WARN.
  7. asyncio.create_task(
         self._routing_history_writer.append_build_queue_event(
             correlation_id=payload.correlation_id,
             event=payload.model_dump(mode="json")))
       # Append-only Graphiti edge per DDR-029 — fire-and-forget.
```

Auto-ack semantics (no `manual_ack`) are intentional: Jarvis cannot meaningfully redeliver a notification (the bridge is in-process, not durable), so the JetStream replay budget is wasted on retries. Failures upstream of step 4 (the correlation lookup) are silently dropped; failures downstream are caught by the `RoutingHistoryWriter`'s WARN-only path.

### CLI render sequence (`cli/main.py`)

```
_chat_loop():
  …
  while True:
    # NEW — drain pending forge notifications BEFORE reading the next line.
    notifications = session_manager.pending_notifications(session.session_id)
    for n in notifications:
        click.echo(n.format_one_line())  # e.g. "[15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete"
    line = await loop.run_in_executor(None, sys.stdin.readline)
    …
```

Notifications are rendered as one line each, prefixed with the local-time HH:MM and the feature_id; the body is the `stage_label` and `status` from the `StageCompletePayload`. The exact format helper lives on `ForgeNotification.format_one_line()` so future adapters (Telegram, Dashboard) can reuse the same canonical rendering.

---

## 9. Test shape

Target: **+25–35 tests** on top of FEAT-JARVIS-004's baseline; maintain 80% coverage on new modules. Integration tests use the same in-process `nats-py` test server as FEAT-J004 (`nats-server -p 0 -js`) so the suite is GB10-independent (Phase 3 floor).

### Unit tests

- `tests/test_forge_notifications_unit.py`:
  - `ForgeNotification.from_stage_complete` populates every render field correctly across `PASSED|FAILED|GATED|SKIPPED` statuses.
  - `format_one_line()` honours the `[HH:MM] Forge {feature_id}: stage {stage_label} ({status})` shape.
  - Correlation map LRU eviction at the configured cap (1000 by default; reduced to 4 in the test) emits `WARN forge_correlation_evicted` and the oldest entry is removed.
  - Per-session queue cap enforcement: 101st enqueue evicts the oldest with `WARN forge_notification_queue_overflow`; queue length stays ≤ cap.
- `tests/test_routing_history_build_queue.py`:
  - `RoutingHistoryWriter.write_build_queue_dispatch` schedules an `add_episode` with `subagent_type="forge_build_queue"` and `subagent_task_id == correlation_id`.
  - `RoutingHistoryWriter.append_build_queue_event` writes an append-only edge of type `stage_complete` against the existing entry's `decision_id` (asserted via the Graphiti stub).
  - Multiple `append_build_queue_event` calls for the same `correlation_id` produce N edges (not field overwrites) — DDR-029 invariant.
- `tests/test_dispatch_queue_build_unit.py`:
  - Validation paths preserved from Phase 2 (invalid_feature_id, invalid_repo, invalid_adapter, validation).
  - `DEGRADED: dispatch_overloaded` when the semaphore is exhausted.
  - `DEGRADED: transport_unavailable` when `_nats_client is None`.
  - PubAck timeout (5s) → `DEGRADED: transport_unavailable — JetStream publish failed`; trace written with `outcome="transport_unavailable"`.

### Integration tests (in-process JetStream test server)

- `tests/test_dispatch_queue_build_integration.py`:
  - Real `js.publish` → mock Forge consumer subscribes to `pipeline.build-queued.FEAT-XXX`; assert payload shape (matches `BuildQueuedPayload` exactly), `triggered_by="jarvis"`, `originating_adapter` matches `Session.adapter`.
  - `parent_request_id` round-trip — set on the call, observed on the consumer.
  - Trace record landed: `subagent_type="forge_build_queue"`, `subagent_task_id == correlation_id`, `outcome="success"`.
- `tests/test_forge_notifications_integration.py`:
  - Pre-stage two queued builds with `register_correlation`; mock Forge publishes `pipeline.stage-complete.FEAT-A` and `pipeline.stage-complete.FEAT-B`; both notifications surface on `SessionManager.pending_notifications` for their respective sessions; the third correlation (no register) is dropped.
  - Cross-session isolation: builds queued from session-A do not surface in session-B's `pending_notifications`.
  - Append-only edges: 3 `stage-complete` events for the same `correlation_id` produce 3 edges (not 1 overwritten).
- `tests/test_end_to_end_forge_roundtrip.py` — **soft-prereq** end-to-end test (real Forge + NATS + Graphiti on GB10 — see [phase3-build-plan.md Step 14](../../research/ideas/phase3-build-plan.md)):
  - Queue Rich-chosen FEAT-JARVIS-INTERNAL feature; assert Forge picks up the payload (or skip with reason if Forge isn't running); assert at least one `stage-complete` notification flows back; assert it surfaces on the next CLI prompt cycle; assert the routing-history entry has both the original write and ≥1 stage-complete edge.
  - Marked `pytest.mark.integration` — opt-in via `pytest -m integration` so CI doesn't require GB10.

### Fallback / soft-fail tests

- `tests/test_queue_build_nats_unavailable.py` — `_nats_client is None` (DDR-021 soft-fail inherited): `queue_build` returns `DEGRADED: transport_unavailable — NATS connection failed`; trace still written with the appropriate outcome; CLI continues; no subscription was started so no further degradation.
- `tests/test_forge_notifications_graphiti_unavailable.py` — Graphiti soft-fail inherited from DDR-019: stage-complete events still surface on the CLI; the append-only edge writes log `WARN routing_history_write_failed`; one WARN deduplicated per process.
- `tests/test_pubsub_lifecycle.py` — `forge_subscriber.stop()` on shutdown is bounded at 5s; idempotent; survives a wedged JetStream by escalating to `nats_client.drain()` afterwards (the drain timeout is the secondary safety net).

### Regression tests

- `tests/test_routing_e2e.py` (FEAT-J003 acceptance) — the `queue_build` prompt now invokes the real-JetStream path (mocked Forge consumer in the test fixture) instead of the stubbed path; tool-call sequence identical.
- `tests/test_dispatch_queue_build.py` (renamed from FEAT-J002) — Phase 2 stub-path tests deleted; replaced by the integration tests above. Validation tests preserved (tool-boundary invariants survive the swap).
- `tests/test_no_phase_2_stub_anchors.py` (the FEAT-J004 grep invariant) — extended to assert `LOG_PREFIX_QUEUE_BUILD` constant is removed from `tools/dispatch.py`. The Phase 2 stub-anchor seam is fully retired in this commit.
- All FEAT-J004 tests preserved unchanged.

Tests assert tool-call sequences, payload shapes, trace-record schema, and CLI rendering shape — never natural-language Forge responses (behavioural).

---

## 10. Supervisor prompt extensions

**None.** Per scope-doc §"Do-Not-Change" and the FEAT-J002/003/004 contract: the reasoning model's view of the world is identical between Phase 2 (stubbed) and Phase 3 (real JetStream). The `queue_build` tool docstring's Phase 2 paragraph (`"In Phase 2 the transport is stubbed: ... FEAT-JARVIS-005 replaces the stub with a real pipeline.build-queued.{feature_id} JetStream publish without changing this docstring."`) is **deleted** in this feature — the swap has happened — but the rest of the docstring is preserved verbatim.

**One-line additions** in the structured-error contract documentation (return-shape paragraph):

- New error: `DEGRADED: transport_unavailable — NATS connection failed` (DDR-021 inheritance).
- New error: `DEGRADED: transport_unavailable — JetStream publish failed` (DDR-025 — publish-timeout / PubAck failure).
- New error: `DEGRADED: dispatch_overloaded — wait and retry` (DDR-020 reuse — `queue_build` now also acquires the dispatch semaphore).

These edits are documentation, not behavioural — the reasoning model handles them via the existing "if response starts with ERROR/DEGRADED/TIMEOUT" branch logic taught in the FEAT-J002 supervisor prompt.

The CLI between-prompt notifications are **not** part of the reasoning model's surface — they render outside the supervisor invoke loop. The reasoning model never sees a `ForgeNotification`; it only sees the user's next prompt (which may reference the notification verbatim if Rich asks about it).

---

## 11. Contradiction detection (against existing ADRs + DDRs)

Proposed contracts checked against:

- All **30 accepted ADRs** in [docs/architecture/decisions/](../../architecture/decisions/).
- All **24 accepted DDRs** from FEAT-JARVIS-001..004 (DDR-001..009 + DDR-010..015 + DDR-016..024).
- The **7 DDRs** introduced by this design (DDR-025..031).
- Forge ADR-ARCH-014 (single-consumer max-ack-pending=1), ADR-ARCH-016/017, ADR-SP-014 Pattern A, ADR-SP-017 retention; ADR-FLEET-001 — pattern source, not dependency.

**No contradictions detected.** Compatibility notes:

- **ADR-ARCH-001** (local-first, no cloud LLMs unattended) — unaffected; FEAT-J005 adds JetStream traffic, no new LLM call sites.
- **ADR-ARCH-008** (no SQLite — Graphiti + Memory Store sufficient) — preserved. The correlation map is in-memory only (DDR-028); the trace edges land in Graphiti.
- **ADR-ARCH-009** (thread-per-session ephemeral state) — preserved. The correlation map is process-local; per-session notification queues are also process-local; both are cleared on `end_session`.
- **ADR-ARCH-016** (NATS-only transport at Jarvis level) — preserved; all new wire traffic is NATS subjects.
- **ADR-ARCH-020** (trace-richness by default) — extended in spirit by DDR-029 (append-only edges keep the trace audit-trail intact across multi-stage builds).
- **ADR-ARCH-021** (tools return structured errors, never raise) — every new error path emits a structured string. PubAck timeout is caught and converted to `DEGRADED:` rather than raising.
- **ADR-ARCH-026** (single instance, no horizontal scaling) — unchanged. One Jarvis process, one JetStream subscription, one correlation map.
- **ADR-ARCH-029** (redaction posture) — preserved. The append-only edge body is a JSON-encoded `StageCompletePayload`; ADR-ARCH-029 redaction runs at the same write boundary as DDR-018's main-entry redaction. `StageCompletePayload` carries no free-text user content — only structured stage labels — so the redaction surface is small.
- **DDR-018** (routing-history schema authoritative) — actively honoured by [DDR-029](decisions/DDR-029-stage-complete-as-append-only-edges.md): stage-complete events land on edges, not as field overwrites; the entry's `frozen=True` invariant holds.
- **DDR-019** (Graphiti fire-and-forget writes; WARN on failure) — extended unchanged to the new `write_build_queue_dispatch` and `append_build_queue_event` paths. Same WARN-only failure surface; same shutdown-flush timeout.
- **DDR-020** (concurrent dispatch cap = 8) — `queue_build` now also acquires the semaphore. The cap covers `dispatch_by_capability` *and* `queue_build` collectively; this matches DDR-020's docstring intent ("`dispatch_by_capability` + `queue_build` invocations per supervisor process").
- **DDR-021** (NATS unavailable → soft-fail) — extended unchanged: `queue_build` returns `DEGRADED: transport_unavailable` when `_nats_client is None`; the notifications subscriber is simply not started, so there's nothing to fail-stop.
- **Forge ADR-SP-014 Pattern A** — preserved verbatim. Jarvis publishes; Forge consumes; no synchronous round-trip; Jarvis does not hold queue position.
- **Forge ADR-SP-017** (PIPELINE stream 7-day retention) — preserved. Jarvis is a publisher only on the build-queued direction; it consumes on stage-complete with `deliver_policy=NEW`, so the retention budget is unaffected by Jarvis (no replay reads the back-history).
- **`BuildQueuedPayload._adapter_required_for_jarvis` validator** — actively honoured by [DDR-031](decisions/DDR-031-originating-adapter-from-session.md): when `triggered_by="jarvis"` the validator requires a non-None adapter from the closed enum, and Jarvis always populates it from the active `Session.adapter` (or the arg fallback for sessionless paths).
- **`StageCompletePayload` `target_kind` Literal** — `"local_tool" | "fleet_capability" | "subagent"`. Jarvis consumes verbatim; the `target_kind` is informational on the rendered CLI line ("stage <label> via <target_kind>").

One **forward-compatibility note** the FEAT-J006 (Telegram) design must consume: the in-process subject `jarvis.notification.forge-stage-complete.{correlation_id}` is currently a method-call boundary (`SessionManager.enqueue_notification`), **not** a published NATS subject. FEAT-J006 promotes it to a real subject under `jarvis.notification.{adapter}` per ARCHITECTURE.md §7. The router seam in `forge_notifications.py` is the single place that change lands.

---

## 12. Assumptions carried forward

| Assumption | Reason it's not settled here |
|---|---|
| `ASSUM-NATS-KV-WATCH` | (carried from FEAT-J004) Unrelated to FEAT-J005's JetStream pub/sub surface. |
| `ASSUM-LLAMASWAP-API` | (carried from FEAT-J003) DDR-022 defers live reads to v1.5; stub-only here. |
| `ASSUM-FRONTIER-CALLER-FRAME` | (carried from FEAT-J003) Unaffected by FEAT-J005. |
| `ASSUM-GRAPHITI-EPISODE-LATENCY` | (carried from FEAT-J004) The append-only edge writes share the same fire-and-forget posture; same ASSUM, same operational signal. |
| `ASSUM-TRACE-OFFLOAD-PATH` | (carried from FEAT-J004) `~/.jarvis/traces/{date}/{decision_id}.json` for oversize traces; FEAT-J005's stage-complete edges are typically <1KB so offload is rare on this path. |
| `ASSUM-FORGE-CONSUMER-SCHEMA` (new) | Forge's `pipeline.stage-complete.>` consumer publishes `nats_core.events.StageCompletePayload` with `correlation_id` always populated. The Forge contract pins this; the contract test in `tests/test_contract_nats_core.py` (FEAT-J004 carry-forward) verifies it on every CI run. |
| `ASSUM-PUBACK-RECEIPT-NOT-DELIVERY` (new) | (Forge LES1) PubAck means JetStream stored the message; it does NOT mean Forge consumed it. Jarvis surfaces "queued" semantics, not "started" — Forge's own `pipeline.build-started.{feature_id}` event (not subscribed in v1) would carry that signal. v1.5 may extend the subscription. |
| `ASSUM-ADAPTER-OVERRIDE-NEVER-NEEDED` (new) | DDR-031 forbids reasoning-model adapter override. If a future use case genuinely needs to spoof an adapter (e.g. dashboard previewing a Telegram-originated build), an append-only DDR + an explicit constitutional allowlist lands then. |
| `ASSUM-NOTIFICATION-RUNAWAY-CAP` (new) | The 100-per-session queue cap (DDR-030) is a defensive ceiling. A long Forge build with hundreds of stages would saturate it; in that regime the older entries would be lost (WARN logged). Operationally: if `WARN forge_notification_queue_overflow` fires, append-only DDR raises the cap or introduces a stage-rollup. |

---

## 13. Next steps

1. **Approve the C4 L3 diagram** at [diagrams/forge-feedback-l3.md](diagrams/forge-feedback-l3.md) — Phase 3.5 review gate.
2. **Seed design to Graphiti** (commands offered at the end of this `/system-design` run — `project_design` group for contracts/models, `architecture_decisions` group for DDRs).
3. **Proceed to `/feature-spec FEAT-JARVIS-005`** — Gherkin scenarios grounded in this design. Primary scenarios:
   - `queue_build` publishes a real `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` with `triggered_by="jarvis"` and `originating_adapter` matching `Session.adapter`.
   - PubAck timeout (5s) → `DEGRADED: transport_unavailable — JetStream publish failed`.
   - `pipeline.stage-complete.>` events for a registered correlation surface on `SessionManager.pending_notifications` for the originating session.
   - Stage-complete events for an unregistered correlation are silently dropped.
   - Append-only Graphiti edges land on the original `JarvisRoutingHistoryEntry` per DDR-029.
   - CLI renders queued notifications between prompts; the queue is drained after rendering.
   - End-of-session clears the per-session queue.
   - Per-session queue cap: 101st enqueue evicts the oldest with `WARN forge_notification_queue_overflow`.
   - Cross-session isolation: build queued from session-A does not surface on session-B.
   - NATS unavailable at startup → Jarvis starts; `queue_build` returns `DEGRADED`; subscriber not started; chat works.
   - End-to-end with real Forge — Rich-chosen FEAT-JARVIS-INTERNAL feature.
4. **Then `/feature-plan FEAT-JARVIS-005`** — task breakdown per [phase3-build-plan.md Step 9 commit order](../../research/ideas/phase3-build-plan.md). Suggested wave structure:
   - Wave 1 (parallel): config extensions; ForgeNotification + BuildCorrelation Pydantic models; DDRs.
   - Wave 2: `forge_notifications.py` module + unit tests; `routing_history_writer` build-queue extensions + tests.
   - Wave 3: `tools/dispatch.py` `queue_build` swap + integration tests.
   - Wave 4: `sessions/manager.py` notification queue + CLI rendering.
   - Wave 5: `lifecycle.py` start/stop wiring + soft-fail tests.
   - Wave 6: Contract tests + grep-invariant retire (`LOG_PREFIX_QUEUE_BUILD`).
   - Wave 7: End-to-end Forge round-trip (soft-prereq, gated on GB10 availability).
5. **Then AutoBuild** — follow the wave order above. The `LOG_PREFIX_QUEUE_BUILD` grep invariant is retired in the same commit that swaps the publish (mirrors how FEAT-J004 retired `LOG_PREFIX_DISPATCH`).
6. **Phase 3 close criteria** — #5 (queue_build publishes), #6 (stage-complete subscription routes), #7 (trace-rich writes for build queue), #10 (end-to-end with real Forge), #11 (contract tests), #12 (ruff + mypy clean) all close in this feature. Phase 3 is **complete** when this feature merges.

---

## 14. File manifest

```
docs/design/FEAT-JARVIS-005/
├── design.md                                                       ← this file
├── contracts/
│   ├── API-internal.md                                             ← module-level Python API:
│   │                                                                #   ForgeNotificationsSubscriber,
│   │                                                                #   ForgeNotification,
│   │                                                                #   RoutingHistoryWriter additions,
│   │                                                                #   SessionManager additions,
│   │                                                                #   CLI rendering helpers
│   ├── API-tools.md                                                ← updated tool contracts:
│   │                                                                #   queue_build (transport swap, new
│   │                                                                #   DEGRADED strings, semaphore guard,
│   │                                                                #   adapter from session)
│   └── API-events.md                                               ← NATS event surface — what Jarvis
│                                                                    #   publishes (pipeline.build-queued.*)
│                                                                    #   + consumes (pipeline.stage-complete.>)
│                                                                    #   + the in-process notification subject
├── models/
│   └── DM-forge-notification.md                                    ← ForgeNotification, BuildCorrelation,
│                                                                    #   per-session queue invariants
├── diagrams/
│   └── forge-feedback-l3.md                                        ← C4 L3 (mandatory review gate)
└── decisions/
    ├── DDR-025-queue-build-real-transport.md
    ├── DDR-026-forge-notifications-module-location.md
    ├── DDR-027-stage-complete-ephemeral-deliver-new.md
    ├── DDR-028-correlation-map-in-memory-bounded.md
    ├── DDR-029-stage-complete-as-append-only-edges.md
    ├── DDR-030-cli-notifications-between-prompts.md
    └── DDR-031-originating-adapter-from-session.md
```

---

*"Jarvis publishes, walks away, listens for stage-complete, and surfaces progress between prompts — without holding queue position and without blocking the supervisor's next turn."* — [phase3-fleet-integration-scope.md §FEAT-JARVIS-005](../../research/ideas/phase3-fleet-integration-scope.md)
