# C4 Level 3 — Forge Feedback Loop (post-FEAT-JARVIS-005)

> **Owner:** [FEAT-JARVIS-005 design §6](../design.md)
> **Container in focus:** Jarvis Supervisor (Fleet Dispatch + Adapter Interface contexts)
> **Required by:** Phase 3.5 mandatory review gate (component count > 3)

This is the C4 Level 3 view of the **Forge Feedback Loop** as it stands after FEAT-JARVIS-005 lands. It zooms inside the Jarvis Supervisor container and shows the components that participate in (a) the outbound `queue_build` publish path and (b) the inbound `pipeline.stage-complete.>` subscription path that bridges back to Rich's CLI between prompts.

The Fleet Dispatch container exceeds the 3-internal-component threshold (10 components participate after this feature lands), so per `/system-design` Phase 3.5 the diagram **requires explicit operator approval** before the design output is finalised.

---

## Diagram

```mermaid
C4Component
    title Component diagram — Forge Feedback Loop (post-FEAT-JARVIS-005)

    Person(rich, "Rich", "Solo operator on the CLI")

    Container_Boundary(jarvis, "Jarvis Supervisor (single GB10 process)") {

        Component(cli, "CLI REPL", "click + asyncio", "Reads stdin, drives session_manager.invoke(), drains pending notifications between prompts")

        Component(session_mgr, "SessionManager", "Python", "Per-instance ContextVar for current_session(); per-session notification deque; pending_notifications drain")

        Component(supervisor, "DeepAgents Supervisor", "LangGraph CompiledStateGraph", "Reasoning loop; calls queue_build via @tool surface")

        Component(queue_build, "queue_build tool", "@tool(parse_docstring=True)", "Validates args; resolves adapter from Session.adapter; acquires dispatch_semaphore; publishes BuildQueuedPayload; registers correlation; fire-and-forget routing-history write")

        Component(disp_sem, "DispatchSemaphore", "asyncio.Semaphore(8)", "Shared cap across queue_build + dispatch_by_capability (DDR-020 reuse)")

        Component(nats_client, "NATSClient", "nats-py wrapper", "Connection lifecycle; exposes JetStreamContext via .js property; soft-fail on connect failure (DDR-021)")

        Component(forge_sub, "ForgeNotificationsSubscriber", "Python", "JetStream ephemeral push consumer on pipeline.stage-complete.>; in-memory LRU correlation map; bridges to SessionManager.enqueue_notification (DDR-026, DDR-027, DDR-028)")

        Component(corr_map, "Correlation Map", "OrderedDict", "correlation_id -> BuildCorrelation (session_id, adapter, feature_id, queued_at); LRU bounded at 1000 (DDR-028)")

        Component(rh_writer, "RoutingHistoryWriter", "Python", "Fire-and-forget Graphiti add_episode for entries + append-only edges (DDR-019, DDR-029)")

        Component(forge_notif, "ForgeNotification", "Pydantic v2 frozen", "In-process notification: feature_id, stage_label, status, target_kind, completed_at, duration_secs; format_one_line() for canonical CLI render")
    }

    System_Ext(nats, "NATS JetStream", "PIPELINE stream (7-day retention)")
    System_Ext(forge, "Forge", "Pull consumer on pipeline.build-queued.>; publisher of pipeline.stage-complete.{feature_id}")
    System_Ext(graphiti, "Graphiti / FalkorDB", "jarvis_routing_history group: entry nodes + stage_complete edges")

    Rel(rich, cli, "Types prompt + reads notifications", "stdin/stdout")
    Rel(cli, session_mgr, "invoke(session, input); pending_notifications(sid)")
    Rel(session_mgr, supervisor, "ainvoke({messages: [...]})")
    Rel(supervisor, queue_build, "@tool call (when reasoning chooses build dispatch)")
    Rel(queue_build, session_mgr, "current_session() -> Session.adapter (DDR-031)")
    Rel(queue_build, disp_sem, "try_acquire() / release() (DDR-020)")
    Rel(queue_build, nats_client, "js.publish(pipeline.build-queued.{feature_id}, BuildQueuedPayload) — PubAck timeout 5s (DDR-025)")
    Rel(queue_build, forge_sub, "register_correlation(correlation_id, session_id, adapter, feature_id)")
    Rel(queue_build, rh_writer, "create_task(write_build_queue_dispatch(entry)) — fire-and-forget")
    Rel(nats_client, nats, "JetStream req/publish via nats-py")

    Rel(forge, nats, "Consume pipeline.build-queued.>; publish pipeline.stage-complete.{feature_id}")

    Rel(forge_sub, nats_client, ".js.subscribe(pipeline.stage-complete.>, deliver_policy=NEW)")
    Rel(forge_sub, corr_map, "lookup(correlation_id) -> BuildCorrelation (drop on miss)")
    Rel(forge_sub, forge_notif, "from_stage_complete(payload, correlation)")
    Rel(forge_sub, session_mgr, "enqueue_notification(session_id, ForgeNotification) — bounded queue (DDR-030)")
    Rel(forge_sub, rh_writer, "create_task(append_build_queue_event(correlation_id, event)) — fire-and-forget edge (DDR-029)")

    Rel(rh_writer, graphiti, "add_episode(entry) + add_episode(edge)")
```

---

## Component count + threshold

10 internal components participate in this diagram:

1. CLI REPL
2. SessionManager
3. DeepAgents Supervisor
4. `queue_build` tool
5. DispatchSemaphore
6. NATSClient
7. ForgeNotificationsSubscriber
8. Correlation Map
9. RoutingHistoryWriter
10. ForgeNotification

10 > 3 → C4 L3 review gate is mandatory.

---

## What to look for in review

Per the `/system-design` Phase 3.5 review prompt, examine:

- **Components with too many dependencies.** `queue_build` connects to 5 internal collaborators (SessionManager, DispatchSemaphore, NATSClient, ForgeNotificationsSubscriber, RoutingHistoryWriter). Is that reasonable, or does it suggest extracting an intermediate `BuildQueuePublisher` class? **Assessment:** the five connections each have a distinct concern (adapter resolution, capacity guard, transport, correlation tracking, trace persistence); a `BuildQueuePublisher` wrapper would just thread the same five through one extra layer without removing coupling. Keep `queue_build` as the seam.
- **Missing persistence layers.** The Correlation Map is in-memory (DDR-028) — is that durability sufficient for the use case? **Assessment:** yes, per DDR-027 (ephemeral consumer) + DDR-028 (in-memory bounded). The bridge is in-process, not durable.
- **Unclear separation of concerns.** Subscriber + Correlation Map are tightly coupled (the map lives inside the subscriber). They're modelled separately on the diagram for clarity, but the colocation is intentional — separating them across modules would force an awkward ownership question.
- **Forge boundary clarity.** Forge is shown as `System_Ext` (external system) — Jarvis only interacts with it via NATS subjects, never directly. The arrows make the publish/subscribe directionality explicit.
- **Cross-cutting: routing-history writer.** Both `queue_build` and the subscriber call into the writer (via `create_task`). The writer is a single shared component, not duplicated — matches the FEAT-J004 design.

---

## Approval

**Per `/system-design` Phase 3.5 — this diagram requires explicit approval before design output is finalised.**

Options:

- `[A]pprove` — diagram lands as drawn; design output proceeds.
- `[R]evise` — request changes; diagram is re-rendered before approval.
- `[R]eject` — diagram is excluded from output; design lands without a C4 L3.

(See the `/system-design` Phase 3.5 prompt at the end of this run.)

---

*"Zoom in on the seam where the reasoning model touches the wire — and the bridge that brings progress back."* — [FEAT-JARVIS-005 design §6](../design.md)
