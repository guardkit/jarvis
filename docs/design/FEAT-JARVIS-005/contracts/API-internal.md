# API-internal — Module-level Python API (FEAT-JARVIS-005)

> **Owner:** [FEAT-JARVIS-005 design §3](../design.md)
> **Scope:** Internal Python contracts new in FEAT-JARVIS-005. The `@tool` surface is documented separately in [API-tools.md](API-tools.md); the wire contracts in [API-events.md](API-events.md).

These types live in `src/jarvis/infrastructure/`, `src/jarvis/sessions/`, and `src/jarvis/cli/` and are consumed by the lifecycle, the dispatch tool, and the CLI REPL. They are **not** `@tool`-decorated — they're typed Python APIs and the supervisor never calls them directly.

---

## 1. `infrastructure/forge_notifications.py` — NEW

```python
class ForgeNotificationsSubscriber:
    """JetStream subscriber for `pipeline.stage-complete.>` plus the
    in-process notification router that bridges matched events to the
    active `SessionManager`.

    DDR-027: ephemeral push consumer with `deliver_policy=NEW`. No
    replay across Jarvis restart.
    DDR-028: in-memory correlation map; LRU bounded.
    """

    def __init__(
        self,
        nats_client: NATSClient,
        routing_history_writer: RoutingHistoryWriter,
        *,
        queue_cap: int = 100,
        correlation_cap: int = 1000,
    ) -> None:
        """Construct the subscriber.

        ``nats_client`` must be a connected NATSClient (DDR-021 soft-fail
        is handled at the lifecycle layer — when ``nats_client is None``
        the subscriber is simply not created).

        ``queue_cap`` is forwarded to ``SessionManager.enqueue_notification``
        per DDR-030. ``correlation_cap`` bounds the LRU correlation map
        per DDR-028.
        """

    def bind_session_manager(self, session_manager: SessionManager) -> None:
        """Late-bind the session manager.

        Construction order in lifecycle is supervisor → session_manager
        → subscriber-bind. Call this exactly once after construction;
        a second call is idempotent (replaces the binding).
        """

    async def start(self) -> None:
        """Subscribe to `pipeline.stage-complete.>` on the JetStream
        context.

        Uses an ephemeral push consumer (DDR-027). Logs structured
        ``forge_notifications_subscribed`` on success. On subscription
        failure logs ``ERROR forge_notifications_subscribe_failed``
        and re-raises — the lifecycle layer treats this as a
        soft-fail and converts to a startup WARN.
        """

    async def stop(self, *, timeout: float = 5.0) -> None:
        """Drain the JetStream consumer; idempotent.

        Bounded by ``timeout``; on timeout logs WARN and abandons.
        Safe to call from ``shutdown(state)`` even when ``start()``
        never succeeded.
        """

    def register_correlation(
        self,
        *,
        correlation_id: str,
        session_id: str | None,
        feature_id: str,
        adapter: str,
        queued_at: datetime,
    ) -> None:
        """Insert a build correlation into the in-memory map.

        Called by ``queue_build`` after a successful PubAck. LRU
        eviction at ``correlation_cap`` (DDR-028); evicted entries
        log ``WARN forge_correlation_evicted``.

        ``session_id is None`` is allowed (for tests / sessionless
        paths) — events for those correlations are still bridged to
        the routing-history writer for the trace edge but are not
        enqueued anywhere (no session to surface them on).
        """

    def correlation_count(self) -> int:
        """Diagnostic: current size of the correlation map."""

    async def _on_message(self, msg: Msg) -> None:
        """Internal: invoked by nats-py for each delivered message.

        Behaviour per design §8:
          1. Validate envelope; verify ``source_id == 'forge'``.
          2. Validate ``StageCompletePayload``.
          3. Look up correlation; drop silently on miss.
          4. Build ``ForgeNotification.from_stage_complete(...)``.
          5. Enqueue on ``SessionManager.enqueue_notification(...)``.
          6. Fire-and-forget ``routing_history_writer.append_build_queue_event(...)``.

        Auto-acks on return — the subscriber does not call ``msg.ack()``
        explicitly because the consumer was created without
        ``manual_ack=True``. Failures upstream of step 4 are
        silently dropped (no redelivery — bridge is in-process,
        not durable). Failures downstream are caught by the
        writer's WARN-only path.
        """


class ForgeNotification(BaseModel):
    """In-process notification routed from `pipeline.stage-complete.*`
    to the originating session's CLI rendering surface.

    See [DM-forge-notification.md](../models/DM-forge-notification.md)
    for the authoritative shape.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    correlation_id: str
    feature_id: str
    stage_label: str
    status: Literal["PASSED", "FAILED", "GATED", "SKIPPED"]
    target_kind: Literal["local_tool", "fleet_capability", "subagent"]
    target_identifier: str
    completed_at: datetime
    duration_secs: float

    @classmethod
    def from_stage_complete(
        cls,
        payload: StageCompletePayload,
        correlation: BuildCorrelation,
    ) -> ForgeNotification:
        """Project a Forge stage-complete payload onto the in-process
        notification shape.

        Pure function — no I/O. Suitable for direct unit testing.
        """

    def format_one_line(self) -> str:
        """Render the canonical CLI line.

        Shape: ``[HH:MM] Forge {feature_id}: stage {stage_label} ({status})``
        Example: ``[15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete (PASSED)``

        Time is the local-time portion of ``completed_at``. Reused by
        FEAT-J006 (Telegram), FEAT-J009 (Dashboard) for canonical
        cross-adapter rendering.
        """


class BuildCorrelation(BaseModel):
    """One element of the in-memory correlation map.

    See [DM-forge-notification.md §2](../models/DM-forge-notification.md).
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    correlation_id: str
    feature_id: str
    session_id: str | None
    adapter: str
    queued_at: datetime
```

---

## 2. `infrastructure/routing_history.py` — UPDATED

The FEAT-JARVIS-004 file already declares the methods as no-ops (see [../../../FEAT-JARVIS-004/contracts/API-internal.md §4](../../FEAT-JARVIS-004/contracts/API-internal.md)). FEAT-J005 replaces the no-op bodies with the real Graphiti calls.

```python
class RoutingHistoryWriter:
    # ... __init__ unchanged ...
    # ... write_specialist_dispatch unchanged ...

    async def write_build_queue_dispatch(
        self, entry: JarvisRoutingHistoryEntry
    ) -> None:
        """Persist a `subagent_type='forge_build_queue'` routing-history entry.

        Side-effect ordering (DDR-018 + DDR-019), identical to
        ``write_specialist_dispatch``:

        1. Apply structlog redact-processor (ADR-ARCH-029).
        2. JSON-encode `supervisor_tool_call_sequence` and
           `subagent_trace_ref`.
        3. Filesystem-offload at 16KB threshold (rare on this path —
           queue-build entries are typically tiny).
        4. Submit Graphiti ``add_episode`` (fire-and-forget — caller
           used ``asyncio.create_task`` at the queue_build boundary).
        5. Failure → ``WARN routing_history_write_failed reason=…``.
        """

    async def append_build_queue_event(
        self,
        correlation_id: str,
        event: dict[str, Any],
    ) -> None:
        """Append a ``stage_complete`` Graphiti edge on the entry whose
        ``subagent_task_id == correlation_id``.

        DDR-029: edge-not-overwrite. The originating
        ``JarvisRoutingHistoryEntry`` stays ``frozen=True`` per DDR-018;
        each stage-complete event lands as one edge. Multiple events
        for the same ``correlation_id`` produce multiple edges (not
        one-overwritten edge).

        Side-effect ordering:

        1. Redact ``event`` via the same processor used by
           ``write_specialist_dispatch`` (ADR-ARCH-029).
        2. Submit Graphiti edge add via ``add_episode`` with
           ``source_description='jarvis-routing-history-edge'`` and
           ``name='stage_complete:{correlation_id}:{seq}'`` where
           ``seq`` is a per-correlation monotonic counter so multiple
           edges for the same correlation have distinct entity names.
        3. Failure → ``WARN routing_history_append_failed reason=…``
           and is swallowed.

        Fire-and-forget: this method awaits the *submission*, not the
        Graphiti round-trip. Caller (``ForgeNotificationsSubscriber.
        _on_message``) wraps it in ``asyncio.create_task``.
        """

    # ... flush unchanged — drains both write-paths' in-flight tasks ...
```

The per-correlation monotonic counter is held in a small `dict[str, int]` on the writer, bounded by the same `correlation_cap` as the subscriber's correlation map (entries evicted in lock-step when a build's correlation falls out of the LRU).

---

## 3. `sessions/manager.py` — UPDATED

```python
class SessionManager:
    # ... __init__ unchanged from FEAT-J004 ...

    def enqueue_notification(
        self,
        session_id: str,
        notification: ForgeNotification,
        *,
        cap: int = 100,
    ) -> None:
        """Append a notification to the per-session queue.

        DDR-030: per-session cap. Overflow evicts the oldest entry
        with ``WARN forge_notification_queue_overflow`` and proceeds.

        Idempotent on ``session_id == ended`` — drops the notification
        with ``DEBUG forge_notification_dropped reason=session_ended``
        rather than raising.
        """

    def pending_notifications(
        self, session_id: str
    ) -> list[ForgeNotification]:
        """Drain the per-session notification queue.

        Returns the queue contents in FIFO order. The returned list
        is a fresh copy; the underlying queue is cleared atomically
        on read so a concurrent ``enqueue_notification`` from the
        ``ForgeNotificationsSubscriber`` does not lose entries.

        Returns an empty list when the session has no pending
        notifications, or when ``session_id`` is unknown / ended.
        """

    def end_session(self, session_id: str) -> None:
        """End a session. Idempotent.

        FEAT-J005 addition: also clears the per-session notification
        queue. Logs ``forge_notification_queue_cleared count=N`` when
        the cleared queue was non-empty.
        """
```

The notification queue is a plain `dict[str, deque[ForgeNotification]]` on the manager (`maxlen=cap`). `deque.maxlen` automatically discards the oldest entry on overflow; the WARN log fires from a thin wrapper that observes the discard.

---

## 4. `cli/main.py` — UPDATED

The `_chat_loop` REPL grows one new step at the top of each iteration:

```python
async def _chat_loop() -> None:
    # ... bootstrap unchanged ...
    while True:
        # FEAT-JARVIS-005: drain any pending Forge notifications BEFORE
        # reading the next prompt. Renders one click.echo line per
        # notification. Non-blocking; does not delay user input.
        for n in session_manager.pending_notifications(session.session_id):
            click.echo(n.format_one_line())

        line = await asyncio.get_event_loop().run_in_executor(
            None, sys.stdin.readline)
        # ... rest of loop unchanged ...
```

The drain runs **once per loop iteration** at the top, before reading stdin. Notifications that arrive while the user is typing surface on the next iteration. `KeyboardInterrupt` (SIGINT) clears the queue via `end_session`; no orphaned notifications survive a session.

---

## 5. `infrastructure/lifecycle.py` — UPDATED

`AppState` gains one field (FEAT-JARVIS-005):

```python
@dataclasses.dataclass(frozen=True)
class AppState:
    # ... FEAT-J001..J004 fields unchanged ...

    # FEAT-JARVIS-005 addition
    forge_subscriber: ForgeNotificationsSubscriber | None = None
```

`build_app_state(config)` extends FEAT-J004's sequence per design §8:

```python
async def build_app_state(config: JarvisConfig) -> AppState:
    # ... FEAT-J004 sequence unchanged through dispatch_semaphore ...

    # NEW in FEAT-J005:
    forge_subscriber: ForgeNotificationsSubscriber | None = None
    if nats_client is not None:
        forge_subscriber = ForgeNotificationsSubscriber(
            nats_client=nats_client,
            routing_history_writer=routing_history_writer,
            queue_cap=config.forge_notifications_queue_cap,
            correlation_cap=config.forge_correlation_map_cap,
        )
        try:
            await forge_subscriber.start()
        except Exception as exc:
            log.warning(
                "jarvis_forge_subscriber_start_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            forge_subscriber = None  # soft-fail per DDR-027 spirit

    # ... assemble_tool_list calls grow `forge_subscriber=` kwarg ...
    # ... build_supervisor unchanged ...
    # ... session_manager construction unchanged ...

    # NEW in FEAT-J005 — late-bind the manager onto the subscriber
    if forge_subscriber is not None:
        forge_subscriber.bind_session_manager(session_manager)

    return AppState(..., forge_subscriber=forge_subscriber)
```

`shutdown(state)` extends with one new step between the heartbeat cancel and the deregister hop (design §8 lists all 9 steps):

```python
async def shutdown(state: AppState) -> None:
    # 1. Cancel heartbeat (unchanged)
    # ...

    # 2. NEW in FEAT-J005 — drain the Forge subscriber.
    if state.forge_subscriber is not None:
        try:
            await state.forge_subscriber.stop(timeout=5.0)
        except Exception as exc:
            log.warning(
                "jarvis_forge_subscriber_stop_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 3. Deregister from fleet (unchanged)
    # ... rest unchanged ...
```

---

## 6. Tool-level wiring — `assemble_tool_list` extensions

```python
def assemble_tool_list(
    config: JarvisConfig,
    capability_registry: list[CapabilityDescriptor],
    *,
    nats_client: NATSClient | None = None,                # FEAT-J004
    routing_history_writer: RoutingHistoryWriter | None = None,  # FEAT-J004
    dispatch_semaphore: DispatchSemaphore | None = None,  # FEAT-J004
    forge_subscriber: ForgeNotificationsSubscriber | None = None,  # ← NEW in 005
    include_frontier: bool = True,
) -> list[BaseTool]:
    """FEAT-J005 — also snapshots `forge_subscriber` into the
    `tools.dispatch._forge_subscriber` module attribute so
    `queue_build` can call `.register_correlation(...)` on a
    successful publish.
    """
```

The new module-level attribute on `tools/dispatch.py`:

```python
_forge_subscriber: ForgeNotificationsSubscriber | None = None  # ← NEW in 005
```

Default `None` preserves the Phase 1 import-only invariant (a bare import yields a tool that returns `DEGRADED:` strings rather than raising). When `None`, `queue_build` skips the `register_correlation` step — dispatch still succeeds; only the back-channel correlation tracking is missing.

---

## 7. Cross-cutting — config additions (`config/settings.py`)

```python
class JarvisConfig(BaseSettings):
    # ... FEAT-J001..J004 fields unchanged ...

    # ── FEAT-JARVIS-005 — JetStream publish ────────────────────────
    pipeline_publish_timeout_seconds: int = Field(
        default=5, ge=1, le=60,
        description="PubAck timeout for queue_build (DDR-025).",
    )

    # ── FEAT-JARVIS-005 — Forge notifications ──────────────────────
    forge_notifications_queue_cap: int = Field(
        default=100, ge=1, le=10_000,
        description="Per-session pending-notifications cap (DDR-030).",
    )
    forge_correlation_map_cap: int = Field(
        default=1000, ge=10, le=100_000,
        description="In-memory correlation-map LRU cap (DDR-028).",
    )
```

`JARVIS_PIPELINE_PUBLISH_TIMEOUT_SECONDS`, `JARVIS_FORGE_NOTIFICATIONS_QUEUE_CAP`, `JARVIS_FORGE_CORRELATION_MAP_CAP` resolve via the existing `env_prefix="JARVIS_"`.

---

*"Typed Python APIs at the boundary; the supervisor never sees them."* — [ADR-ARCH-006](../../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md)
