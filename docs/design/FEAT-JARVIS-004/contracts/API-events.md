# API-events — NATS event surface (FEAT-JARVIS-004)

> **Owner:** [FEAT-JARVIS-004 design §3](../design.md)
> **Wire-format authority:** All payloads are `nats_core` Pydantic models — emitted and consumed verbatim. No Jarvis-specific extensions on the wire.

---

## 1. Subjects — what Jarvis publishes / subscribes

| Subject | Direction | Payload | Frequency | Notes |
|---|---|---|---|---|
| `fleet.register` | **Publish** | `nats_core.AgentManifest` (Jarvis's own manifest) | Once at startup; republished every `heartbeat_interval_seconds` (default 30s) | ADR-ARCH-004; published via `NATSKVManifestRegistry.register()` |
| `fleet.deregister` | **Publish** | `nats_core.AgentManifest` (Jarvis's manifest, status="terminating") OR equivalent per nats-core deregister convention | Once at shutdown | Idempotent; missing nats-core convention falls back to KV-tombstone |
| `agents.command.{agent_id}` | **Publish** (request) | `nats_core.MessageEnvelope` wrapping `nats_core.events.CommandPayload` | Per `dispatch_by_capability` invocation | Singular per ADR-SP-016; correlation_id round-trips on the reply |
| `agents.result.{agent_id}` | **Subscribe** (reply) | `nats_core.MessageEnvelope` wrapping `nats_core.events.ResultPayload` | Per dispatch reply (timeout-bounded) | Implicit subscription via NATS request/reply pattern |
| `$KV.agent-registry.>` | **Subscribe** (KV watch) | `nats_core.AgentManifest` snapshots | On fleet membership change | Drives `CapabilitiesRegistry` cache invalidation per ADR-ARCH-017 |

### Not in FEAT-JARVIS-004

- `pipeline.build-queued.*` — FEAT-JARVIS-005 (queue_build swap).
- `pipeline.stage-complete.*` — FEAT-JARVIS-005 (notification subscription).
- `jarvis.notification.forge-stage-complete.*` — FEAT-JARVIS-005 (internal router).
- `agents.status.*` — Jarvis does not publish status events in v1 (heartbeat republish on `fleet.register` carries liveness).

---

## 2. Payload shapes — exact references

All payloads are **imported verbatim** from `nats_core`. Jarvis does not redefine them. Pinned versions:

```
nats-core>=X.Y,<X+1.0  (pinned in pyproject.toml at FEAT-J002 land)
```

### 2.1 `nats_core.manifest.AgentManifest`

Used for Jarvis's own self-registration on `fleet.register`. Shape:

```python
class AgentManifest(BaseModel):
    agent_id: str          # kebab-case; "jarvis"
    name: str              # "Jarvis"
    version: str           # semver, default "0.1.0"; we set config.jarvis_agent_version
    intents: list[IntentCapability]
    tools: list[ToolCapability]    # empty list in v1 — Jarvis's tools are not fleet-discoverable yet
    template: str          # "general_purpose_agent"
    max_concurrent: int    # 1 per ADR-ARCH-026
    status: Literal["ready", "starting", "degraded"]
    trust_tier: Literal["core", "specialist", "extension"]   # "core" for Jarvis
    required_permissions: list[str]
    container_id: str | None
    metadata: dict[str, str]   # ≤64KB JSON-encoded — validator-enforced
```

Constructed by `infrastructure.fleet_registration.build_jarvis_manifest(config)` per [API-internal.md §2](API-internal.md).

### 2.2 `nats_core.events.CommandPayload`

Outbound. Constructed inside `dispatch_by_capability` from `tool_name`, `args` (parsed payload_json), `correlation_id`. Wrapped in `MessageEnvelope(source_id="jarvis", event_type=EventType.COMMAND, ...)` per Phase 2 invariant.

### 2.3 `nats_core.events.ResultPayload`

Inbound (the reply on `agents.result.{agent_id}`). Validated via `ResultPayload.model_validate_json(msg.data)` after the request returns. `success=True` → success path; `success=False` → specialist_error or redirect candidate; no reply within timeout → `asyncio.TimeoutError` → redirect or exhaustion.

---

## 3. Reply / ack semantics

- **Request/reply** — `agents.command.{agent_id}` uses NATS native request/reply with a per-call inbox. Timeout is enforced via `asyncio.wait_for(...)` at the supervisor side (does **not** rely on NATS server-side timeouts). The specialist sees a normal subject-subscribed message and replies on the inbox.
- **No JetStream** for specialist dispatch — req/reply is core NATS (per ADR-ARCH-016 / ADR-SP-016). JetStream is reserved for `pipeline.*` and `jarvis.notification.*` streams (FEAT-JARVIS-005+).
- **No retries at the NATS layer** — retry-with-redirect lives at the supervisor level (DDR-017) and selects a *different* `agent_id`, not the same one again. NATS-level retry would fight the visited-set guard.
- **Late replies** — if a specialist replies after Jarvis has timed out and moved on, the inbox is gone and the reply is dropped at the NATS level. The Phase 2 docstring's `"the result may still appear in NATS after timeout (Phase 3+)"` statement was speculative; the chosen design **discards** late replies. Documented in the dispatch_by_capability docstring delta.

---

## 4. Subject naming — pinned conventions

Per [ADR-SP-016](../../../../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md) singular topic convention (Forge inheritance):

- ✅ `agents.command.architect` (singular `agents`, singular `command`)
- ✅ `agents.result.architect`
- ✅ `fleet.register`
- ✅ `pipeline.build-queued.FEAT-JARVIS-INTERNAL-001` (FEAT-J005)
- ❌ Never `agent.commands.*` or `agents.commands.*` — plural forms reject at the `nats_core.Topics` constructor.

`nats_core.Topics` provides the canonical subject formatters; Jarvis uses them verbatim. Hard-coded subject strings are forbidden — they break refactoring and contract tests.

---

## 5. Contract tests — `tests/test_contract_nats_core.py`

These tests are the cross-repo handshake. They protect Jarvis from `nats-core` schema drift between releases.

1. `test_jarvis_manifest_round_trips` — `build_jarvis_manifest(config)` → JSON → `AgentManifest.model_validate_json` produces an equal manifest.
2. `test_command_payload_emitted_matches_nats_core` — Jarvis's emitted `CommandPayload` deserialises cleanly via `nats_core.events.CommandPayload`. All fields populated.
3. `test_result_payload_consumed_matches_nats_core` — Synthetic specialist reply (built from `nats_core.events.ResultPayload(...)`) round-trips through `dispatch_by_capability` without ValidationError.
4. `test_envelope_source_id_is_jarvis` — every emitted `MessageEnvelope.source_id == "jarvis"` (audit-trail invariant).
5. `test_topic_subjects_match_topics_class` — Every `agents.command.*` / `agents.result.*` / `fleet.register` subject string Jarvis emits is produced by a `nats_core.Topics.*` formatter, never hard-coded.
6. **(FEAT-J005 carry-forward)** `test_build_queued_payload_emitted_matches_nats_core` — included here so the test module is shared, but only exercises the Phase 2 stub builder until FEAT-J005 swaps the publish.

---

*"The `nats-core` Pydantic models are the contract — verbatim, no shortcuts."* — [phase3-fleet-integration-scope.md §Do-Not-Change](../../../research/ideas/phase3-fleet-integration-scope.md)
