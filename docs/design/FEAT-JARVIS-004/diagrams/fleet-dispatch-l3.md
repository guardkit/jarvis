# C4 L3 — Fleet Dispatch Container (post-FEAT-JARVIS-004)

> **Owner:** [FEAT-JARVIS-004 design §6](../design.md)
> **Mandatory review gate:** This diagram triggers `/system-design` Phase 3.5. The Fleet Dispatch Context container exceeds the 3-internal-component threshold (12 components participate after this feature lands). **Explicit approval required** before the design is finalised.

---

## Component diagram

```mermaid
C4Component
    title Fleet Dispatch Context — Components after FEAT-JARVIS-004

    Container_Boundary(jarvis, "Jarvis Supervisor (single process, GB10)") {

        Component(supervisor, "Jarvis Supervisor", "DeepAgents create_deep_agent CompiledStateGraph", "Reasoning loop; routes through tool calls")

        Boundary(tools, "Tool layer (`@tool(parse_docstring=True)`)") {
            Component(t_dispatch, "dispatch_by_capability", "@tool", "Real NATS round-trip with timeout + retry-with-redirect (FEAT-J004 swap)")
            Component(t_queue, "queue_build", "@tool", "Stubbed in FEAT-J004; FEAT-J005 swaps to JetStream publish")
            Component(t_caps, "list_available_capabilities / refresh / subscribe_updates", "@tool", "Reads CapabilitiesRegistry (live KV with stub fallback)")
            Component(t_frontier, "escalate_to_frontier", "@tool", "Layer 2 hooks armed by lifecycle (FEAT-J003 F1 fix); F5 plumbs real session_id")
        }

        Boundary(infra, "Infrastructure (Group D)") {
            Component(nats_client, "NATSClient", "nats-py wrapper", "Connection lifecycle + JetStream context; soft-fail on connect (DDR-021)")
            Component(fleet_reg, "FleetRegistration", "Python module", "Builds Jarvis's AgentManifest; publishes on fleet.register; heartbeat loop")
            Component(caps_reg, "CapabilitiesRegistry", "Python module", "NATSKVManifestRegistry adapter; 30s cache + KV watch invalidation; stub fallback when NATS unavailable")
            Component(rh_writer, "RoutingHistoryWriter", "Python module", "Fire-and-forget Graphiti writes (DDR-019); >16KB filesystem offload (DDR-018)")
            Component(disp_sem, "DispatchSemaphore", "asyncio.Semaphore(8)", "Concurrent dispatch cap (DDR-020); overflow → DEGRADED")
            Component(lifecycle, "Lifecycle / AppState", "Python module", "Orchestrates startup: NATS → Graphiti → fleet register → capabilities → tools → supervisor")
        }

        Boundary(domain, "Domain (Group B)") {
            Component(session_mgr, "SessionManager", "Python module", "current_session() drives Layer-2 hooks + F5 session_id plumb")
            Component(capability_descriptor, "CapabilityDescriptor (Pydantic)", "shared model", "Phase 2 shape; unchanged in 004")
            Component(routing_history_entry, "JarvisRoutingHistoryEntry (Pydantic)", "DM-routing-history", "Authoritative ADR-FLEET-001 schema (DDR-018); JA1 resolution")
        }
    }

    System_Ext(nats, "NATS / JetStream (GB10)", "Subjects: fleet.register, agents.command.*, agents.result.*, agent-registry KV")
    System_Ext(graphiti, "Graphiti / FalkorDB (GB10)", "Group: jarvis_routing_history")
    System_Ext(specialists, "Specialist Agents", "architect, product-owner, ideation, … — registered manifests")
    System_Ext(filesystem, "Filesystem", "~/.jarvis/traces/{date}/{decision_id}.json — large-trace offload")

    Rel(supervisor, t_dispatch, "Calls")
    Rel(supervisor, t_caps, "Reads catalogue")
    Rel(supervisor, t_frontier, "Calls (attended only)")

    Rel(t_dispatch, disp_sem, "acquire / release")
    Rel(t_dispatch, caps_reg, "_resolve_agent_id with exclude=visited")
    Rel(t_dispatch, nats_client, "await nats.request(agents.command.{agent_id}, ...)")
    Rel(t_dispatch, rh_writer, "asyncio.create_task(write(entry))")

    Rel(t_caps, caps_reg, "snapshot() / refresh() / subscribe()")
    Rel(t_frontier, session_mgr, "_current_session_hook → Session.session_id (F5)")

    Rel(lifecycle, nats_client, "connect / drain")
    Rel(lifecycle, fleet_reg, "register + heartbeat task")
    Rel(lifecycle, caps_reg, "create + close (KV watcher)")
    Rel(lifecycle, rh_writer, "construct + flush on shutdown")
    Rel(lifecycle, disp_sem, "construct(config.dispatch_concurrent_cap)")
    Rel(lifecycle, session_mgr, "wire hooks (FEAT-J003 F1)")

    Rel(fleet_reg, nats_client, "publish AgentManifest to fleet.register; heartbeat republish")
    Rel(caps_reg, nats_client, "KV read + watch on agent-registry")
    Rel(rh_writer, graphiti, "add_episode (fire-and-forget)")
    Rel(rh_writer, filesystem, "write JSON when payload >16KB")

    Rel(nats_client, nats, "TCP", "nats:// (Tailscale)")
    Rel(nats_client, specialists, "agents.command.{agent_id} → agents.result.{agent_id}", "via NATS req/reply")
```

---

## Components — narrative

**Tool layer (Group C — all 4 @tool functions live in `src/jarvis/tools/`):**

1. **dispatch_by_capability** — Phase 2 stub body retired; real NATS round-trip with `asyncio.wait_for(...)`, retry-with-redirect (max 1, DDR-017), trace write at every boundary. **Tool docstring + return shape unchanged** so the reasoning model sees no transition.
2. **queue_build** — Phase 2 stub remains until FEAT-JARVIS-005 swaps it. Documented here so the diagram reflects the post-FEAT-J004 state including the not-yet-swapped tool.
3. **list_available_capabilities / capabilities_refresh / capabilities_subscribe_updates** — bodies updated to read from `CapabilitiesRegistry` (live KV) instead of the in-memory `_capability_registry` snapshot. Stub-fallback when NATS is `None`.
4. **escalate_to_frontier** — Layer 2 hooks were armed in the FEAT-J003-FIX-001 wave; FEAT-J004 plumbs real `session_id` (review F5) and reads `frontier_default_target` from config (review F6).

**Infrastructure layer (Group D — Phase 1 reserved, populated here):**

5. **NATSClient** — async wrapper around `nats-py`; connect on startup, drain on shutdown; exposes `client` + `js` (JetStream) properties; soft-fail returns `None` per DDR-021.
6. **FleetRegistration** — `build_jarvis_manifest(config) → AgentManifest`; `register_on_fleet(client, manifest)` publishes to `fleet.register`; `heartbeat_loop(client, manifest, config)` is the asyncio task launched by lifecycle.
7. **CapabilitiesRegistry** — wraps `NATSKVManifestRegistry` from `nats-core` (or vendor-stamps the KV-watch shape per ASSUM-NATS-KV-WATCH); 30s cache; `subscribe_updates()` attaches a watcher; `StubCapabilitiesRegistry` is the soft-fail fallback so `list_available_capabilities` still serves the stub list.
8. **RoutingHistoryWriter** — Graphiti client lifecycle; `write_specialist_dispatch(entry)` and (FEAT-J005) `write_build_queue_dispatch(entry)` + `append_build_queue_event(correlation_id, event)`; redaction processor at the write boundary; large-trace filesystem offload per DDR-018.
9. **DispatchSemaphore** — `asyncio.Semaphore(8)`; `acquire_nowait()` returns immediately on overflow so the tool emits `DEGRADED: dispatch_overloaded — wait and retry`.
10. **Lifecycle / AppState** — orchestrates startup ordering and stores all the new substrate references on `AppState` (`nats_client`, `graphiti_client`, `routing_history_writer`, `fleet_heartbeat_task`).

**Domain (Group B — pure types, no I/O):**

11. **SessionManager** — already present from Phase 1; `current_session()` returns the active `Session` so the dispatch tool can read `session.session_id` for trace records (F5).
12. **JarvisRoutingHistoryEntry** — full Pydantic shape per [DM-routing-history.md](../models/DM-routing-history.md).

---

## Review gate

_Look for:_

- **Components with too many dependencies.** `Lifecycle` legitimately has many — that's its job (orchestration). `dispatch_by_capability` reaches semaphore + capabilities + nats_client + rh_writer; that's the dispatch sequence and is documented in `design.md §8`.
- **Missing persistence layers.** Graphiti + filesystem are both shown. No SQLite per ADR-ARCH-008 — JarvisRoutingHistoryEntry is the substitute for Forge's SQLite-backed pipeline state.
- **Unclear separation of concerns.** Group B (domain, pure) / Group C (tools) / Group D (infrastructure) is the ADR-ARCH-006 five-group layout. The diagram's boundaries reflect that grouping.
- **God modules.** No single module owns more than one cross-cutting concern. NATS is split across `nats_client.py` (transport), `fleet_registration.py` (lifecycle), `capabilities_registry.py` (KV reads). Graphiti is split between `routing_history.py` (writes) and the future `infrastructure/graphiti_client.py` (connection — minimal in v1).
- **Cyclic dependencies.** None. `tools/` imports from `infrastructure/` (one direction); `infrastructure/` imports from `config/`, `sessions/`, `shared/` (one direction).

[A]pprove | [R]evise | [R]eject

> Reviewer: please indicate approval before this design is seeded to Graphiti and `/feature-spec FEAT-JARVIS-004` is invoked.

---

*"Twelve components — registered, dispatched, traced. The fleet contract is symmetric."* — [phase3-fleet-integration-scope.md](../../../research/ideas/phase3-fleet-integration-scope.md)
