# FEAT-JARVIS-004 — Design

> **Feature:** NATS Fleet Registration & Specialist Dispatch (real transport)
> **Phase:** 3 (Fleet Integration) — FEAT-JARVIS-004 only; FEAT-JARVIS-005 (build-queue + Forge notifications) follows.
> **Generated:** 2026-04-27 via `/system-design FEAT-JARVIS-004`
> **Status:** Proposed — input to `/feature-spec FEAT-JARVIS-004`
> **Architecture source:** [../../architecture/ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) (v1.0, 2026-04-20, 30 ADRs)
> **Scope source:** [../../research/ideas/phase3-fleet-integration-scope.md](../../research/ideas/phase3-fleet-integration-scope.md)
> **Build plan:** [../../research/ideas/phase3-build-plan.md](../../research/ideas/phase3-build-plan.md)
> **Predecessor designs:** [../FEAT-JARVIS-001/design.md](../FEAT-JARVIS-001/design.md), [../FEAT-JARVIS-002/design.md](../FEAT-JARVIS-002/design.md), [../FEAT-JARVIS-003/design.md](../FEAT-JARVIS-003/design.md)
> **Predecessor review:** [.claude/reviews/FEAT-JARVIS-003-review-report.md](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md)

---

## 1. Purpose

FEAT-JARVIS-004 turns Jarvis from a supervisor that *reasons about dispatch* into a fleet citizen that *actually dispatches*. Phase 2 ([FEAT-JARVIS-002](../FEAT-JARVIS-002/design.md)) shipped real `nats_core` payload construction with stubbed transports — the supervisor builds a `CommandPayload`, logs `JARVIS_DISPATCH_STUB …`, and returns a canned `ResultPayload`. FEAT-JARVIS-004 replaces the stubs with real NATS round-trips, registers Jarvis on `fleet.register` (closing the symmetric fleet contract per [ADR-ARCH-004](../../architecture/decisions/ADR-ARCH-004-jarvis-registers-on-fleet-register.md)), reads the live capability catalogue from `NATSKVManifestRegistry`, and lights up the **first ADR-FLEET-001 trace-rich writes** to the `jarvis_routing_history` Graphiti group.

Critically, `dispatch_by_capability`'s tool signature, docstring, and Pydantic return shape are **unchanged** from Phase 2. The reasoning model's view of the world is identical — only the transport behind the seam swaps.

This design closes three open architectural questions:

- **JA1** — exact Pydantic shape of `JarvisRoutingHistoryEntry`. Resolved here as authoritative for v1+; later additions are append-only via ADR-FLEET-00X.
- **Phase 3 close criterion #4** — `dispatch_by_capability` round-trip + timeout + retry-with-redirect. Behaviour pinned at this design.
- **FEAT-JARVIS-003 review findings F5 + F6** — real `session_id` plumbing into `FrontierEscalationContext`; `frontier_default_target` config field becomes load-bearing.

The Phase 3 close criterion (Rich-chosen FEAT-JARVIS-INTERNAL-*** end-to-end build) lives on FEAT-JARVIS-005 — but it depends on every contract this design pins.

One-line success criterion: *Jarvis registers on `fleet.register`, discovers specialists via `NATSKVManifestRegistry`, round-trips `agents.command.{agent_id}` / `agents.result.{agent_id}` with timeout + retry-with-redirect, and writes ADR-FLEET-001-shaped trace records to `jarvis_routing_history` for every dispatch — without changing the reasoning model's tool surface.*

## 2. Scope in-context

Jarvis has seven bounded contexts per [ADR-ARCH-005](../../architecture/decisions/ADR-ARCH-005-seven-bounded-contexts.md). FEAT-JARVIS-004 is **Fleet Dispatch Context core work** plus minor extensions to two cross-cutting modules.

| Bounded context | FEAT-JARVIS-004 touches? | How |
|---|---|---|
| **Fleet Dispatch Context** | **IN — core** | NATS client, fleet registration, `NATSKVManifestRegistry` integration, real `dispatch_by_capability` transport, retry-with-redirect, ADR-FLEET-001 writes |
| **Jarvis Reasoning Context** | unchanged | Tool docstrings, supervisor prompt sections preserved verbatim |
| **Adapter Interface Context** | partial — read-side only | `Session.session_id` plumbed into `FrontierEscalationContext` (review F5) |
| **Config (cross-cutting)** | extended | NATS URL, credentials path, dispatch timeout default, Graphiti endpoint, concurrent dispatch cap, `frontier_default_target` becomes read (F6) |
| **Knowledge Context** | activated | First Graphiti writes — `jarvis_routing_history` group lights up |
| Ambient / Learning / External Tool contexts | untouched | FEAT-J006/008+ territory |

See [phase3-fleet-integration-scope.md §Do-Not-Change](../../research/ideas/phase3-fleet-integration-scope.md) — Phase 1/2 outputs (supervisor, sessions, subagents, tool docstrings, `CapabilityDescriptor` shape) are preserved verbatim. The **only** behavioural-surface changes are the `lifecycle.startup` ordering (NATS + Graphiti now wired before supervisor) and the structured-error strings tools emit when transport is unavailable.

## 3. Surfaces shipped

| Surface | Type | Artefact |
|---|---|---|
| DeepAgents tool surface (3 capability tools + 1 dispatch tool — bodies updated, docstrings unchanged) | in-process — docstrings are the contract | [contracts/API-tools.md](contracts/API-tools.md) |
| Internal Python API (NATS client, fleet registration, routing history, capabilities live registry) | in-process | [contracts/API-internal.md](contracts/API-internal.md) |
| NATS event contracts (consumed + emitted) | wire | [contracts/API-events.md](contracts/API-events.md) |

**No new network protocols at the Jarvis level.** All NATS traffic uses `nats-core`'s singular topic convention (ADR-SP-016): `fleet.register`, `agents.command.{agent_id}`, `agents.result.{agent_id}`. All Pydantic models on the wire are `nats_core` originals — verbatim, no Jarvis extensions. Per Phase 1 [DDR-001](../FEAT-JARVIS-001/decisions/DDR-001-internal-api-in-process-only.md) and the FEAT-JARVIS-002/003 precedent, no `openapi.yaml`, no `mcp-tools.json`, no `a2a-schemas.yaml`. The `langgraph.json` from FEAT-JARVIS-003 is unchanged.

## 4. Data models

| Model | Purpose | Artefact |
|---|---|---|
| `JarvisRoutingHistoryEntry` (Pydantic v2) | Authoritative ADR-FLEET-001 schema for `jarvis_routing_history` writes — base + Jarvis extensions; large-trace filesystem offload | [models/DM-routing-history.md](models/DM-routing-history.md) |
| `DispatchOutcome` (Literal) | `"success" \| "timeout" \| "redirected" \| "specialist_error" \| "exhausted" \| "transport_unavailable"` — the closed outcome set written into trace records | [models/DM-routing-history.md](models/DM-routing-history.md) |
| `RedirectAttempt` (Pydantic v2) | One element of `alternatives_considered` — captures `agent_id`, `reason_skipped`, `attempt_index`. Append-only | [models/DM-routing-history.md](models/DM-routing-history.md) |
| `AgentManifest` (`nats_core.manifest.AgentManifest`) | Jarvis's own self-registration manifest — emitted to `fleet.register` | imported; no redefinition |
| `CommandPayload`, `ResultPayload` (`nats_core.events`) | The wire types `dispatch_by_capability` round-trips | imported; no redefinition |
| Reused unchanged | `CapabilityDescriptor`, `CapabilityToolSummary`, `FrontierEscalationContext`, `FrontierTarget`, `Session`, `RoleName` | [../FEAT-JARVIS-002/models/DM-tool-types.md](../FEAT-JARVIS-002/models/DM-tool-types.md), [../FEAT-JARVIS-003/models/DM-subagent-types.md](../FEAT-JARVIS-003/models/DM-subagent-types.md) |

## 5. Design decisions captured

| DDR | Decision | Why it's here |
|---|---|---|
| [DDR-016](decisions/DDR-016-dispatch-timeout-default-60s.md) | `dispatch_by_capability` default `timeout_seconds=60`; range 5..600 unchanged | Settles the Phase 2 open question. 60s covers typical specialist round-trips per Forge ADR-ARCH-015; leaves headroom for retry-with-redirect within reasonable wall-clock. |
| [DDR-017](decisions/DDR-017-retry-with-redirect-policy.md) | Max **1** redirect (2 total attempts); prefer descriptors whose `capability_list` contains the same `tool_name`; visited-set on `agent_id` guards loops | Matches the scope-doc spirit ("prefer same-capability match"). One retry caps wall-clock at ~2× timeout; visited-set is the loop guard. |
| [DDR-018](decisions/DDR-018-routing-history-schema-authoritative.md) | `JarvisRoutingHistoryEntry` Pydantic shape is **authoritative for v1+**. Schema additions append-only via ADR-FLEET-00X. Records >16KB JSON-encoded offload `supervisor_tool_call_sequence` + `subagent_trace_ref` to `~/.jarvis/traces/{date}/{decision_id}.json` per ADR-FLEET-001 §"Large traces" | Resolves JA1. Trace data compounds — retrofits are expensive. The 16KB threshold mirrors ADR-FLEET-001's "exceeds reasonable Graphiti entity size" guidance and Meta-Harness's filesystem-as-context pattern. |
| [DDR-019](decisions/DDR-019-graphiti-fire-and-forget-writes.md) | Per-dispatch **fire-and-forget async** Graphiti writes; failures log `WARN` (not `ERROR`); Graphiti unreachable at startup → Jarvis still starts; trace writes drop for the outage window | Dispatch must not stall on Graphiti latency. `WARN` (not `ERROR`) preserves trace continuity in monitoring without alerting on transient outages — the schema is authoritative *if available*, not load-bearing for runtime correctness. |
| [DDR-020](decisions/DDR-020-concurrent-dispatch-cap-8.md) | Concurrent dispatch cap = **8** in-flight `dispatch_by_capability` + `queue_build` invocations per supervisor process, gated by an `asyncio.Semaphore`. Above the cap → `DEGRADED: dispatch_overloaded — wait and retry` per ADR-ARCH-021 | Stays under JA2's 10-Pattern-B-watcher ceiling so the two concurrency budgets don't compete. Surfaces backpressure quickly when a specialist wedges. |
| [DDR-021](decisions/DDR-021-nats-unavailable-soft-fail.md) | NATS unavailable at startup → Jarvis starts; supervisor's NATS client is `None`; dispatch tools return `DEGRADED: transport_unavailable — NATS connection failed`; capability registry **falls back to the stub YAML** so `list_available_capabilities` still serves a non-empty list | Preserves the attended-conversation surface even when fleet is dead. Operator can still chat, ask Jarvis questions, and use frontier-escape — only outbound dispatch is dead. Aligns with FEAT-J003's voice-ack soft-fail posture (Layer 1 of "no silent failures"). |
| [DDR-022](decisions/DDR-022-defer-llamaswap-live-reads-to-v15.md) | `LlamaSwapAdapter` `/running` + `/log` reads remain stubbed in FEAT-JARVIS-004; live HTTP probe deferred to v1.5 (new feature, separate scope) | Keeps Phase 3 scoped — NATS + Graphiti + first ADR-FLEET-001 writes is already medium-high complexity. ASSUM-LLAMASWAP-API (endpoint contract not formally specified by llama-swap project) is independent risk that warrants its own design pass. |

DDR numbering continues from FEAT-JARVIS-003 (DDR-010..015). FEAT-JARVIS-004 uses DDR-016..022; next available after this design is DDR-023.

## 6. Component diagram

[diagrams/fleet-dispatch-l3.md](diagrams/fleet-dispatch-l3.md) — C4 Level 3 view of the **Jarvis Supervisor → Fleet Dispatch Context** as it stands after FEAT-JARVIS-004 lands. **Requires explicit approval per `/system-design` Phase 3.5 gate** — the Fleet Dispatch container exceeds the 3-internal-component threshold (12 components participate after this feature: NATS client, fleet registration, capability registry — live, capability registry — stub fallback, dispatch tool, queue-build tool, frontier tool, routing-history writer, lifecycle orchestrator, async dispatch semaphore, redirect-policy resolver, visited-set guard).

## 7. Module layout — extensions to Phase 1/2 + FEAT-JARVIS-003

Per [ADR-ARCH-006 five-group layout](../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md). Phase 1 reserved `infrastructure/` with only `lifecycle.py` + `logging.py`; FEAT-JARVIS-002/003 populated `tools/` and `agents/subagents/`. FEAT-JARVIS-004 fills out `infrastructure/` with the NATS-side modules and updates four existing modules.

```
src/jarvis/
├── infrastructure/
│   ├── lifecycle.py                            # UPDATED — NATS + Graphiti startup; register on fleet;
│   │                                           #           heartbeat task; drain + deregister; arm
│   │                                           #           dispatch semaphore; soft-fail bookkeeping
│   ├── nats_client.py                          # NEW    — async nats-py wrapper; connect/drain;
│   │                                           #           JetStream context; structured logging
│   ├── fleet_registration.py                   # NEW    — Jarvis's AgentManifest builder + heartbeat
│   │                                           #           loop; deregister on shutdown
│   ├── capabilities_registry.py                # NEW    — NATSKVManifestRegistry adapter; 30s cache +
│   │                                           #           KV watch invalidation; stub fallback
│   ├── routing_history.py                      # NEW    — JarvisRoutingHistoryEntry write functions;
│   │                                           #           large-trace filesystem offload; WARN-only
│   │                                           #           failure path; Graphiti client lifecycle
│   ├── dispatch_semaphore.py                   # NEW    — asyncio.Semaphore(8) + structured-error
│   │                                           #           rendering when above cap
│   └── logging.py                              # unchanged
├── tools/
│   ├── dispatch.py                             # UPDATED — dispatch_by_capability real transport
│   │                                           #           (round-trip + timeout + redirect);
│   │                                           #           routing_history write boundaries;
│   │                                           #           session_id plumbing (review F5);
│   │                                           #           frontier_default_target read (review F6)
│   ├── capabilities.py                         # UPDATED — list_available_capabilities reads from
│   │                                           #           capabilities_registry (cache + watch);
│   │                                           #           capabilities_refresh / _subscribe_updates
│   │                                           #           swap stub bodies for real KV ops
│   └── (other tool modules unchanged)
├── config/
│   └── settings.py                             # UPDATED — nats_url, nats_credentials_path,
│                                               #           graphiti_endpoint (typed), graphiti_api_key,
│                                               #           specialist_dispatch_timeout_seconds,
│                                               #           dispatch_concurrent_cap,
│                                               #           jarvis_traces_dir, jarvis_agent_version,
│                                               #           heartbeat_interval_seconds
├── sessions/
│   └── session.py                              # UPDATED — Session.session_id surfaced via
│                                               #           current_session() to dispatch hooks (F5).
│                                               #           No new fields — F5 is plumbing-only.
└── (rest unchanged)
pyproject.toml                                  # UPDATED — nats-py, graphiti-core (optional[nats], optional[graphiti])
```

Every `@tool` still follows [ADR-ARCH-021](../../architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md) (return structured error strings; never raise). The new infrastructure modules expose **typed Python APIs** consumed by the tool modules — they do not get `@tool`-decorated. This keeps the swap-point seam from Phase 2's [DDR-009](../FEAT-JARVIS-002/decisions/DDR-009-stub-transport-semantics.md) intact: the `LOG_PREFIX_DISPATCH` grep anchor disappears (replaced by `await nats.request(...)`), but the tool docstring + return shape stay byte-identical.

### What is *not* in this layout

- No new adapters in `adapters/`. NATS lives under `infrastructure/` (it's transport plumbing, not a behaviour adapter); the Group D `adapters/` slot is reserved for adapter-channel containers (Telegram, Reachy, etc.) per ADR-ARCH-006/ARCH-007.
- No `nats.py` adapter module — NATS is the transport; the cross-cutting "adapter" mental model (per ARCHITECTURE.md §3) is satisfied by `infrastructure/nats_client.py` + `infrastructure/capabilities_registry.py` + `infrastructure/routing_history.py`. We split the responsibilities along their lifecycle (connection vs. KV-watch vs. Graphiti-write) rather than bundling them into a god-module.

## 8. Wiring — how lifecycle composes the new substrate

Extends the FEAT-JARVIS-003 wiring sequence (which itself extended FEAT-JARVIS-002's). New lines marked `← NEW in FEAT-JARVIS-004`.

```
env + .env
    │
    ▼
JarvisConfig()                                    ← jarvis.config.settings (extended in 004)
    │
    ▼
lifecycle.build_app_state(config):
    │
    ├── logging.configure(...)
    ├── config.validate_provider_keys()
    ├── store = InMemoryStore()
    ├── nats_client = await NATSClient.connect(config)            ← NEW in 004 (soft-fail per DDR-021)
    ├── graphiti_client = await GraphitiClient.connect(config)    ← NEW in 004 (soft-fail; WARN per DDR-019)
    ├── routing_history_writer = RoutingHistoryWriter(graphiti_client, config)  ← NEW in 004
    ├── if nats_client is not None:
    │     manifest = build_jarvis_manifest(config)                ← NEW in 004 (fleet_registration.py)
    │     await register_on_fleet(nats_client, manifest)          ← NEW in 004
    │     heartbeat_task = asyncio.create_task(
    │         heartbeat_loop(nats_client, manifest, config))      ← NEW in 004
    │     capabilities_registry = await CapabilitiesRegistry.create(  ← NEW in 004
    │         nats_client, fallback_path=config.stub_capabilities_path)
    │     # Watches NATS KV; 30s cache + invalidation; on miss falls
    │     # back to stub; emits structured logs on transitions.
    │   else:
    │     # NATS soft-fail — capability_registry serves the stub.
    │     capabilities_registry = StubCapabilitiesRegistry(config.stub_capabilities_path)
    │     heartbeat_task = None
    ├── llamaswap_adapter = LlamaSwapAdapter(base_url=config.llama_swap_base_url)  # 003 (still stubbed — DDR-022)
    ├── os.environ["OPENAI_BASE_URL"] = f"{config.llama_swap_base_url}/v1"          # 003
    ├── async_subagents = build_async_subagents(config)                              # 003
    ├── dispatch_semaphore = asyncio.Semaphore(config.dispatch_concurrent_cap)      ← NEW in 004
    ├── tool_list_attended = assemble_tool_list(                                    # extended in 004
    │       config, capabilities_registry, llamaswap_adapter,
    │       nats_client=nats_client,
    │       routing_history_writer=routing_history_writer,
    │       dispatch_semaphore=dispatch_semaphore,
    │       include_frontier=True,
    │   )
    ├── tool_list_ambient = assemble_tool_list(                                     # extended in 004
    │       …same, include_frontier=False)                                          #   (registration-layer
    │                                                                                #    gate per DDR-014)
    ├── supervisor = build_supervisor(
    │       config, tools=tool_list_attended,
    │       available_capabilities=capabilities_registry.snapshot(),
    │       async_subagents=async_subagents,
    │       ambient_tool_factory=lambda: tool_list_ambient)
    ├── session_manager = SessionManager(supervisor, store)
    ├── _dispatch._current_session_hook = session_manager.current_session            # 003 review F1 fix (kept)
    ├── _dispatch._async_subagent_frame_hook = lambda: None                          # 003 review F1 fix (kept)
    └── return AppState(config, supervisor, store, session_manager,
                       capabilities_registry, llamaswap_adapter,
                       nats_client=nats_client,                                     ← NEW in 004
                       graphiti_client=graphiti_client,                             ← NEW in 004
                       routing_history_writer=routing_history_writer,               ← NEW in 004
                       fleet_heartbeat_task=heartbeat_task)                         ← NEW in 004
```

`shutdown(state)` extends FEAT-J003's surface:

1. Cancel `fleet_heartbeat_task` (if running).
2. `await deregister_from_fleet(state.nats_client, "jarvis")` (idempotent).
3. `await state.capabilities_registry.close()` (closes KV watcher).
4. `await state.routing_history_writer.flush()` — drains any in-flight async writes; bounded wait (5s default), then logs WARN and abandons.
5. `await state.nats_client.drain()` (graceful, with 5s drain timeout).
6. `await state.graphiti_client.aclose()`.
7. Disarm Layer-2 hooks (kept from FEAT-J003 review F1 fix).
8. `state.store.close()` (Phase 1 invariant).

### `dispatch_by_capability` runtime sequence (replaces the Phase 2 stub)

```
dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60):
  1. correlation_id = new_correlation_id()
  2. validate timeout (5..600); validate payload JSON-object literal (Phase 2 invariant)
  3. semaphore.acquire_nowait()
       on overflow → "DEGRADED: dispatch_overloaded — wait and retry"
  4. visited: set[str] = set()
  5. attempt_index = 0; attempts: list[RedirectAttempt] = []
  6. WHILE attempt_index <= MAX_REDIRECTS (= 1):
       a. agent_id = _resolve_agent_id(tool_name, intent_pattern, registry,
                                       exclude=visited)
       b. IF agent_id is None:
            outcome = "exhausted" if attempts else "unresolved"
            write trace; release semaphore; return structured error
       c. visited.add(agent_id)
       d. command, envelope = build_payloads(tool_name, parsed_args, correlation_id)
       e. TRY:
            response_envelope = await asyncio.wait_for(
                nats.request(f"agents.command.{agent_id}",
                             envelope.model_dump_json().encode()),
                timeout=timeout_seconds,
            )
            result = ResultPayload.model_validate_json(response_envelope.data)
            IF result.success:
              outcome = "success" if attempt_index == 0 else "redirected"
              write trace (one entry covering the whole dispatch — alternatives_considered
                          carries the prior attempts); release semaphore;
                          return result.model_dump_json()
            ELSE:
              attempts.append(RedirectAttempt(agent_id=agent_id,
                                              reason_skipped=result.error,
                                              attempt_index=attempt_index))
              attempt_index += 1; continue
          EXCEPT asyncio.TimeoutError:
            attempts.append(RedirectAttempt(agent_id=agent_id,
                                            reason_skipped="timeout",
                                            attempt_index=attempt_index))
            attempt_index += 1; continue
          EXCEPT NATSConnectionError:
            outcome = "transport_unavailable"; write trace; release semaphore;
            return "DEGRADED: transport_unavailable — NATS connection failed"
  7. outcome = "exhausted"; write trace; release semaphore;
       return "TIMEOUT: agent_id=… tool_name=… exhausted attempts=…"
```

`write trace` is **always** fire-and-forget: `asyncio.create_task(routing_history_writer.write(entry))`. The dispatch never awaits the Graphiti write; failures land in the writer's `WARN` log and never propagate to the tool boundary.

### Capability resolution with redirect

`_resolve_agent_id` (Phase 2's existing function) gains an `exclude: set[str]` parameter. Resolution order is unchanged — exact `tool_name` match first, then intent-pattern fallback — but excluded `agent_id`s are skipped. **Crucially, the lexicographic ordering is preserved** so retry-with-redirect is deterministic across runs (testable, reproducible, and matches Forge's resolver convention per ADR-ARCH-015).

## 9. Test shape

Target: **+45–55 tests** on top of FEAT-JARVIS-003's baseline; maintain 80% coverage on new modules. Integration tests use an **in-process `nats-py` test server** (`nats-server -p 0 -js`) so the suite is GB10-independent (Phase 3 floor).

### Unit tests

- `tests/test_nats_client.py` — `NATSClient.connect(config)` returns a connected client; `drain()` is idempotent; reconnect logging; structured logging on connect failure (returns `None`, doesn't raise).
- `tests/test_fleet_registration.py` — `build_jarvis_manifest(config)` produces a valid `nats_core.AgentManifest` with `agent_id="jarvis"`, kebab-case validated, `template="general_purpose_agent"`, intent capabilities populated, `trust_tier="core"`, version pulled from `config.jarvis_agent_version`.
- `tests/test_routing_history_schema.py` — full `JarvisRoutingHistoryEntry` exercise: every field populated under happy / timeout / redirect / exhausted scenarios; trace records >16KB JSON-encoded offload `supervisor_tool_call_sequence` and `subagent_trace_ref` to filesystem path; content hash matches; trace file written; small records stay inline.
- `tests/test_dispatch_semaphore.py` — `asyncio.Semaphore(8)` ceiling is exact; 9th call returns `DEGRADED: dispatch_overloaded` immediately (no block); release on timeout / exception / success.
- `tests/test_capabilities_registry_unit.py` — 30s cache; KV watch callback invalidates; stub-fallback path is invoked when NATS is `None`; snapshot isolation (ASSUM-006) preserved.

### Integration tests (in-process NATS test server)

- `tests/test_fleet_registration_integration.py` — register on `fleet.register`; manifest is queryable from the registry; heartbeat loop fires at the configured interval; `deregister_from_fleet` removes the entry.
- `tests/test_capabilities_real.py` — `NATSKVManifestRegistry` integration: pre-seed two specialist manifests; `list_available_capabilities()` returns both; new specialist registers mid-session → KV watch fires → cache invalidates → `list_available_capabilities()` returns three; specialist deregisters → cache invalidates → returns two.
- `tests/test_dispatch_by_capability_integration.py`:
  - Round-trip happy path: mock specialist consumer subscribes to `agents.command.test-architect`, replies with canned `ResultPayload`; supervisor sees the result; trace record `outcome="success"`, `attempts=[]`.
  - Timeout → exhausted: no consumer; default 60s reduced to 1s for test; tool returns `TIMEOUT: agent_id=… tool_name=… exhausted attempts=1`; trace record `outcome="exhausted"`, `attempts` length 1.
  - Timeout → redirect → success: first specialist times out; second one (matching capability) replies; tool returns the second result; trace record `outcome="redirected"`, `attempts` length 1, `chosen_specialist_id` matches the second.
  - Timeout → redirect → timeout: both specialists time out; tool returns `TIMEOUT: … exhausted attempts=2`; trace `outcome="exhausted"`, `attempts` length 2; visited-set prevented loops.
  - Specialist error → redirect → success: first specialist replies with `success=False`, `error="capacity_exceeded"`; second specialist replies success; trace `outcome="redirected"`, `attempts[0].reason_skipped="capacity_exceeded"`.
  - Concurrent dispatch overflow: launch 9 concurrent dispatches against a slow (delayed-reply) consumer; 9th returns `DEGRADED: dispatch_overloaded` synchronously; first 8 return success when the consumer fires.
- `tests/test_contract_nats_core.py` — Jarvis's emitted `CommandPayload` deserialises cleanly with `nats_core.events.CommandPayload.model_validate_json(...)`; the same for `BuildQueuedPayload` (regression for FEAT-J005 which inherits this transport); `AgentManifest` round-trips through `nats_core.manifest.AgentManifest`.

### Fallback / soft-fail tests

- `tests/test_nats_unavailable.py` — startup with unreachable NATS URL: Jarvis still starts; `nats_client` is `None`; `dispatch_by_capability` returns `DEGRADED: transport_unavailable — NATS connection failed`; capabilities registry serves the stub; `list_available_capabilities` returns the stub list (FEAT-J002 regression preserved); `escalate_to_frontier` still works on attended sessions (no NATS dependency).
- `tests/test_graphiti_unavailable.py` — startup with unreachable Graphiti endpoint: Jarvis still starts; `routing_history_writer` is in degraded mode; dispatches succeed; trace writes log `WARN routing_history_write_failed reason=…` once; subsequent writes are no-ops with the same WARN; recovery on next startup.
- `tests/test_lifecycle_partial_failure.py` — NATS up, Graphiti down: dispatches work (real round-trips), traces lost; NATS down, Graphiti up: dispatches return DEGRADED, no traces; both down: Jarvis still starts, only attended-only escape + local subagent + Phase 2 deterministic tools are functional.

### Regression tests

- `tests/test_routing_e2e.py` (FEAT-J003 acceptance) — all 7 prompts still pass with the real transport; the `dispatch_by_capability` and `queue_build` prompts now invoke the real-NATS path (mocked specialist consumer in the test fixture) instead of the stubbed path; tool-call sequences identical.
- `tests/test_dispatch_by_capability.py` (renamed from FEAT-J002) — Phase 2 stub-path tests deleted (the swap point is gone); replaced with the integration tests above. Preserve the validation tests (timeout range, payload-object validation) — those are tool-boundary invariants that survive the swap.
- `tests/test_no_retired_roster_strings.py` — unchanged; trips if any forbidden FEAT-J003 superseded role string reappears.
- `tests/test_escalate_to_frontier_*` (FEAT-J003) — unchanged; F5 plumbing is additive (new `session_id` assertion on the structured INFO record), F6 plumbing reads from config but defaults are unchanged.

Tests assert tool-call sequences, payload shapes, and trace-record schema (structural) — never natural-language specialist responses (behavioural). Mocked specialist consumers return deterministic canned payloads.

## 10. Supervisor prompt extensions

**None.** Per scope-doc §"Do-Not-Change" and the FEAT-J002/003 contract: the reasoning model's view of the world is identical between Phase 2 (stubbed) and Phase 3 (real NATS). The `dispatch_by_capability` tool docstring's Phase 2 paragraph (`"In Phase 2 the transport is stubbed: the tool builds a real CommandPayload …; FEAT-JARVIS-004 replaces the stub with real NATS round-trips without changing this docstring."`) is **deleted** in this feature — the swap has happened — but the rest of the docstring (including the cost / latency signal and the structured-error contract) is preserved verbatim. The reasoning model has been routing against this surface since Phase 2; it does not need to learn anything new.

**One-line additions** in the structured-error contract documentation (return-shape paragraph of the docstring):

- New error: `DEGRADED: dispatch_overloaded — wait and retry` (DDR-020 boundary).
- New error: `DEGRADED: transport_unavailable — NATS connection failed` (DDR-021 soft-fail).
- The existing `DEGRADED: transport_stub …` line is removed (no longer reachable).

These edits are documentation, not behavioural — the reasoning model handles them via the existing "if response starts with ERROR/DEGRADED/TIMEOUT" branch logic taught in the FEAT-J002 supervisor prompt.

## 11. Contradiction detection (against existing ADRs + DDRs)

Proposed contracts checked against:

- All **30 accepted ADRs** in [docs/architecture/decisions/](../../architecture/decisions/).
- All **15 accepted DDRs** from FEAT-JARVIS-001..003 (DDR-001..009 + DDR-010..015).
- Forge ADR-ARCH-015/016/017/031 and ADR-FLEET-001 — pattern source / inheritance, not dependency.

**No contradictions detected.** Compatibility notes:

- **ADR-ARCH-001** (local-first, no cloud LLMs unattended) — unaffected; FEAT-J004 adds NATS + Graphiti, no new LLM call sites. The `routing_history.py` Graphiti writes route to FalkorDB (local), not a cloud service.
- **ADR-ARCH-004** (Jarvis registers on fleet.register) — *now realised in code* by `fleet_registration.py`. The architectural "should" becomes runtime "does".
- **ADR-ARCH-008** (no SQLite — Graphiti + Memory Store sufficient) — preserved. Trace files on disk are **flat-file overflow** for >16KB Graphiti entities, not a separate persistent store. ADR-FLEET-001 §"Large traces" explicitly endorses this.
- **ADR-ARCH-015** (CI = ruff + mypy --strict + pytest) — new modules must pass; the FEAT-J003 review's F3 (drift in `src/jarvis/`) is closed before this feature merges via the FEAT-J003-FIX-002 wave. FEAT-J004 does not regress that gate.
- **ADR-ARCH-016** (NATS-only transport) — preserved; all new wire traffic is NATS subjects.
- **ADR-ARCH-017** (constitutional permissions, not reasoning-adjustable) — unaffected; the new `dispatch_concurrent_cap` is a config field, not a reasoning input.
- **ADR-ARCH-020** (trace-richness by default) — *now realised in code* by `routing_history.py`'s schema. JA1 resolves here.
- **ADR-ARCH-021** (tools return structured errors, never raise) — every new error path emits a structured string. The dispatch semaphore `acquire_nowait()` on overflow returns DEGRADED rather than blocking or raising.
- **ADR-ARCH-022** (constitutional rules belt+braces) — F5 plumbing strengthens the Layer-2 telemetry (real `session_id` instead of placeholder); F6 plumbing makes the `frontier_default_target` config lever load-bearing per ADR-ARCH-027 budget-bucketing intent.
- **ADR-ARCH-026** (single instance, no horizontal scaling) — unchanged. One Jarvis process, one NATS connection, one Graphiti client.
- **ADR-ARCH-027** (attended-only frontier escape) — F5/F6 fixes strengthen rather than weaken the constitutional gate. Layer 2 (lifecycle-wired hooks per FEAT-J003 F1 fix) remains the executor assertion; F5 adds session traceability without weakening the boundary.
- **ADR-ARCH-029** (redaction posture) — `JarvisRoutingHistoryEntry` capture path applies `structlog`'s redact-processor at write time per ADR-FLEET-001 §"Privacy and redaction"; instruction bodies, NATS credentials, API keys are filtered at the trace-capture boundary.
- **ADR-ARCH-030** (budget envelope) — unaffected; FEAT-J004 adds zero cloud spend (NATS + Graphiti are local).
- **ADR-ARCH-031** (async subagents for long-running work) — unaffected; subagent dispatch path remains FEAT-J003 surface.
- **DDR-001** (no network protocols Phase 1/2) — `langgraph.json` from FEAT-J003 unchanged. NATS subjects are *consumed* outbound; no inbound network endpoint is added.
- **DDR-005** (`dispatch_by_capability` supersedes `call_specialist`) — preserved; the renamed tool is the one this feature swaps the transport for.
- **DDR-009** (stub transport semantics) — *retired by this feature*. The `_stub_response_hook`, `LOG_PREFIX_DISPATCH`, and `LOG_PREFIX_QUEUE_BUILD` swap-point anchors disappear from `tools/dispatch.py`; the TASK-J002-021 grep invariant is updated/retired in the same commit. (FEAT-J005 retires the queue-build half.)
- **DDR-014** (Layer 1+2+3 frontier gate) — F5/F6 plumbing strengthens; no layer is removed.
- **DDR-015** (LlamaSwapAdapter stubbed) — preserved by DDR-022; live reads remain v1.5.

One **forward-compatibility note** the FEAT-J005 design must consume: the `routing_history_writer` is a **shared component** between FEAT-J004 and FEAT-J005. FEAT-J005's `queue_build` real-transport path writes to the same writer (`subagent_type="forge_build_queue"`, `subagent_task_id=correlation_id`); stage-complete events arriving on `pipeline.stage-complete.*` add edges to the original entry rather than overwriting. The `RoutingHistoryWriter` class must support both `write_specialist_dispatch(entry)` and `write_build_queue_dispatch(entry)` + `append_build_queue_event(correlation_id, event)` to honour this. Captured in the API-internal contract.

## 12. Assumptions carried forward

| Assumption | Reason it's not settled here |
|---|---|
| `ASSUM-NATS-KV-WATCH` | `NATSKVManifestRegistry`'s exact KV watch callback shape is implementation-dependent (nats-core may expose it differently than Forge's `forge.adapters.nats`). Verified at integration-test time with the in-process server; if the Forge convention differs, a thin adapter lands in `infrastructure/capabilities_registry.py`. |
| `ASSUM-LLAMASWAP-API` | (carried from FEAT-J003) The `/running` + `/log` endpoints are not formally contracted. DDR-022 defers live reads to v1.5; stub-only here. |
| `ASSUM-FRONTIER-CALLER-FRAME` | (carried from FEAT-J003) DeepAgents 0.5.3 does not expose `AsyncSubAgentMiddleware` caller-frame metadata; F5 plumbing does not change this. The session-state fallback path remains the only Layer-2 caller-frame signal. |
| `ASSUM-ATTENDED-ADAPTER-ID` | (carried from FEAT-J003) The attended-adapter set is the ADR-ARCH-016 list. F5 plumbs `session_id` but the comparison is still on `Session.adapter`. |
| `ASSUM-GRAPHITI-EPISODE-LATENCY` | Graphiti `add_episode` calls are submitted fire-and-forget; we don't measure round-trip latency in v1. If `WARN routing_history_write_failed` exceeds 1% of dispatches over 24h, it becomes an operational signal worth a follow-up DDR. |
| `ASSUM-TRACE-OFFLOAD-PATH` | `~/.jarvis/traces/{date}/{decision_id}.json` is a personal-use posture per ADR-ARCH-029. A multi-user deployment would want a per-user directory; v1 is single-instance per ADR-ARCH-026 so the simple path holds. |
| `ASSUM-FORGE-NOTIFICATION-MODULE` | (forward-compat for FEAT-J005) `infrastructure/forge_notifications.py` is the planned location. FEAT-J005's `/system-design` re-validates the boundary. |
| `ASSUM-DISPATCH-SEMAPHORE-CAP` | DDR-020's `8` is a starting point; if real-world dispatch traffic during the FEAT-J005 end-to-end test consistently bumps the cap, an append-only DDR raises it. Logging on overflow makes the signal observable. |

## 13. Next steps

1. **Approve the C4 L3 diagram** at [diagrams/fleet-dispatch-l3.md](diagrams/fleet-dispatch-l3.md) — Phase 3.5 review gate.
2. **Seed design to Graphiti** (commands offered at the end of this `/system-design` run — `project_design` group for contracts/models, `architecture_decisions` group for DDRs).
3. **Proceed to `/feature-spec FEAT-JARVIS-004`** — Gherkin scenarios grounded in this design. Primary scenarios:
   - Jarvis registers on `fleet.register` at startup; manifest is queryable from the registry.
   - `list_available_capabilities` reflects live KV state including a mid-session new-specialist registration.
   - `dispatch_by_capability` round-trips with a mocked specialist consumer.
   - Timeout → retry-with-redirect → success (different specialist, same capability).
   - Timeout → retry-with-redirect → exhausted (structured error).
   - Trace record written with all ADR-FLEET-001 fields populated; large records offload to filesystem.
   - NATS unavailable at startup → Jarvis starts; dispatch returns `DEGRADED: transport_unavailable`; chat still works.
   - Graphiti unavailable at startup → Jarvis starts; dispatch returns success; `WARN routing_history_write_failed` logged.
4. **Then `/feature-plan FEAT-JARVIS-004`** — task breakdown per [phase3-build-plan.md Step 7 commit order](../../research/ideas/phase3-build-plan.md), preserving the dependency chain (config → NATS client → fleet registration → routing_history → capabilities live registry → dispatch_by_capability swap → lifecycle integration → fallback tests → contract tests).
5. **Then AutoBuild** — follow the commit order from build-plan §Step 7. The TASK-J002-021 grep invariant test for `LOG_PREFIX_DISPATCH` is retired in the same commit that swaps the transport.
6. **Phase 3 close criterion #4** — `dispatch_by_capability` round-trip + timeout + retry-with-redirect — closes here. Criteria #2 (fleet.register), #3 (live capabilities), #8 (trace writes), #9 (Graphiti fallback), #11 (contract tests), #12 (ruff + mypy clean) all close in this feature too.

## 14. File manifest

```
docs/design/FEAT-JARVIS-004/
├── design.md                                                       ← this file
├── contracts/
│   ├── API-internal.md                                             ← module-level Python API:
│   │                                                                #   NATSClient, RoutingHistoryWriter,
│   │                                                                #   CapabilitiesRegistry,
│   │                                                                #   build_jarvis_manifest,
│   │                                                                #   register_on_fleet, heartbeat_loop
│   ├── API-tools.md                                                ← updated tool contracts:
│   │                                                                #   dispatch_by_capability (transport
│   │                                                                #   swap, new DEGRADED strings);
│   │                                                                #   list_available_capabilities (live);
│   │                                                                #   capabilities_refresh / _subscribe
│   │                                                                #   _updates (real KV ops)
│   └── API-events.md                                               ← NATS event surface — what Jarvis
│                                                                    #   emits + consumes (subjects, payloads,
│                                                                    #   ack semantics)
├── models/
│   └── DM-routing-history.md                                       ← JarvisRoutingHistoryEntry, DispatchOutcome,
│                                                                    #   RedirectAttempt — JA1 resolution
├── diagrams/
│   └── fleet-dispatch-l3.md                                        ← C4 L3 (mandatory review gate)
└── decisions/
    ├── DDR-016-dispatch-timeout-default-60s.md
    ├── DDR-017-retry-with-redirect-policy.md
    ├── DDR-018-routing-history-schema-authoritative.md
    ├── DDR-019-graphiti-fire-and-forget-writes.md
    ├── DDR-020-concurrent-dispatch-cap-8.md
    ├── DDR-021-nats-unavailable-soft-fail.md
    └── DDR-022-defer-llamaswap-live-reads-to-v15.md
```

---

*"The fleet contract is symmetric — Jarvis registers, dispatches, and writes its own learning substrate from the first turn."* — [phase3-fleet-integration-scope.md](../../research/ideas/phase3-fleet-integration-scope.md)
