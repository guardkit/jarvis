# API-internal — Module-level Python API (FEAT-JARVIS-004)

> **Owner:** [FEAT-JARVIS-004 design §3](../design.md)
> **Scope:** Internal Python contracts new in FEAT-JARVIS-004. The `@tool` surface is documented separately in [API-tools.md](API-tools.md); the wire contracts in [API-events.md](API-events.md).

These types live in `src/jarvis/infrastructure/` and are consumed by the tool modules and `lifecycle.py`. They are **not** `@tool`-decorated — they're typed Python APIs and the supervisor never calls them directly.

---

## 1. `infrastructure/nats_client.py`

```python
class NATSClient:
    """Async wrapper around nats-py providing connection lifecycle.

    DDR-021 soft-fail: connect failures return None from the classmethod
    so lifecycle continues. The supervisor process stays up; dispatch
    tools surface 'DEGRADED: transport_unavailable — NATS connection
    failed' on each invocation.
    """

    @classmethod
    async def connect(cls, config: JarvisConfig) -> "NATSClient | None":
        """Connect to NATS using config.nats_url + nats_credentials_path.

        Returns None on connect failure (logged as ERROR — operator-actionable
        but not startup-fatal). Returns a connected NATSClient on success.

        Reconnect policy is set on the underlying client: max_reconnect_attempts
        from config; structured logging on disconnect / reconnect events
        per ADR-ARCH-020.
        """

    async def request(
        self,
        subject: str,
        payload: bytes,
        *,
        timeout: float,
    ) -> Msg:
        """Issue a NATS request/reply with timeout.

        Raises asyncio.TimeoutError on timeout (caller catches per
        the dispatch_by_capability sequence in design §8).
        Raises NATSConnectionError on transport failure.
        """

    @property
    def client(self) -> nats.aio.client.Client: ...

    @property
    def js(self) -> JetStreamContext:
        """JetStream context — used by FEAT-JARVIS-005's queue_build swap."""

    async def drain(self, *, timeout: float = 5.0) -> None:
        """Idempotent. Drains any in-flight messages, then closes."""
```

---

## 2. `infrastructure/fleet_registration.py`

```python
def build_jarvis_manifest(config: JarvisConfig) -> AgentManifest:
    """Construct Jarvis's own AgentManifest for fleet.register publication.

    Manifest fields (per ADR-ARCH-004 + nats-core convention):
        agent_id="jarvis"  (kebab-case validated by AgentManifest)
        name="Jarvis"
        version=config.jarvis_agent_version  (semver)
        template="general_purpose_agent"
        intents=[
            IntentCapability(pattern="conversational.gpa", ...),
            IntentCapability(pattern="dispatch.by_capability", ...),
            IntentCapability(pattern="meta.dispatch", ...),
            IntentCapability(pattern="memory.recall", ...),
        ]
        tools=[]  # Jarvis exposes its tools through the supervisor surface,
                  # not as fleet-discoverable tools in v1; FEAT-J006+ may extend.
        max_concurrent=1  # ADR-ARCH-026
        status="ready"
        trust_tier="core"  # Jarvis is a core fleet member
        required_permissions=[]
        container_id=os.environ.get("HOSTNAME") or None
        metadata={"adapter_set": "telegram,cli,dashboard,reachy",
                  "phase": "v1"}

    Pure function — no I/O, no network. Suitable for direct unit testing.
    """


async def register_on_fleet(
    client: NATSClient,
    manifest: AgentManifest,
) -> None:
    """Publish the manifest to fleet.register.

    Uses NATSKVManifestRegistry.register(manifest) per nats-core
    convention. Idempotent — re-registration replaces the prior entry.

    Raises NATSConnectionError if the publish fails. Caller (lifecycle)
    catches and converts to a startup WARN — registration failure does
    not block startup (DDR-021 spirit).
    """


async def heartbeat_loop(
    client: NATSClient,
    manifest: AgentManifest,
    config: JarvisConfig,
) -> None:
    """Periodic heartbeat republish per nats-core convention.

    Republishes manifest every config.heartbeat_interval_seconds (default
    30s). Logged as DEBUG; failures logged as WARN and the loop continues.
    Cancellation (asyncio.CancelledError) is the normal shutdown path.
    """


async def deregister_from_fleet(
    client: NATSClient,
    agent_id: str = "jarvis",
) -> None:
    """Clean shutdown. Idempotent. Logs WARN on failure rather than raising."""
```

---

## 3. `infrastructure/capabilities_registry.py`

```python
class CapabilitiesRegistry(Protocol):
    """Protocol unifying live NATS-backed and stub-fallback registries.

    `assemble_tool_list` and the capability tools depend on this Protocol
    so the soft-fail path (NATS unreachable) is transparent to consumers.
    """

    def snapshot(self) -> list[CapabilityDescriptor]:
        """Return the current registry as a fresh list copy.

        Snapshot isolation per ASSUM-006 — callers may iterate freely
        without worrying about concurrent invalidation.
        """

    async def refresh(self) -> None:
        """Invalidate cache and re-read source of truth.

        Live impl: fetches all manifests from NATSKVManifestRegistry and
        rebuilds the descriptor list. Stub impl: re-reads the YAML file.
        """

    async def subscribe_updates(self, callback: Callable[[], None]) -> None:
        """Attach a callback fired whenever the source-of-truth changes.

        Live impl: KV-watch on agent-registry. Stub impl: no-op.
        """

    async def close(self) -> None:
        """Idempotent. Detaches watchers, closes underlying clients."""


class LiveCapabilitiesRegistry:
    """NATSKVManifestRegistry-backed registry with 30s cache + watch invalidation.

    Per ADR-ARCH-017 (live KV watch — Forge inheritance).
    """

    @classmethod
    async def create(
        cls,
        client: NATSClient,
        *,
        cache_ttl_seconds: int = 30,
    ) -> "LiveCapabilitiesRegistry": ...


class StubCapabilitiesRegistry:
    """Fallback for the NATS soft-fail path (DDR-021).

    Reads from config.stub_capabilities_path (Phase 2 YAML). Provides the
    same Protocol surface so the rest of the system doesn't branch.
    """

    def __init__(self, fallback_path: Path) -> None: ...
```

---

## 4. `infrastructure/routing_history.py`

```python
class RoutingHistoryWriter:
    """Fire-and-forget Graphiti writer for jarvis_routing_history (DDR-019).

    Failures log WARN (not ERROR) per DDR-019. Large entries offload
    supervisor_tool_call_sequence + subagent_trace_ref to filesystem
    per DDR-018.
    """

    def __init__(
        self,
        graphiti_client: GraphitiClient | None,
        config: JarvisConfig,
    ) -> None:
        """graphiti_client is None when Graphiti was unreachable at startup.
        In that mode, write() is a no-op with a one-time WARN log."""

    async def write_specialist_dispatch(self, entry: JarvisRoutingHistoryEntry) -> None:
        """Write a specialist dispatch trace (subagent_type='specialist').

        Side-effect ordering:
          1. Apply structlog redact-processor (ADR-ARCH-029).
          2. JSON-encode supervisor_tool_call_sequence + subagent_trace_ref.
          3. If JSON >16KB, offload to ~/.jarvis/traces/{date}/{decision_id}.json
             and substitute TraceRef in the entity (DDR-018).
          4. Submit Graphiti add_episode (fire-and-forget — caller used
             asyncio.create_task at the dispatch boundary).
          5. Failure → WARN routing_history_write_failed reason=...
        """

    async def write_build_queue_dispatch(
        self, entry: JarvisRoutingHistoryEntry
    ) -> None:
        """FEAT-JARVIS-005 reuse — same writer, subagent_type='forge_build_queue'."""

    async def append_build_queue_event(
        self,
        correlation_id: str,
        event: dict[str, Any],
    ) -> None:
        """FEAT-JARVIS-005 — append-only edge on the existing entry.

        Stage-complete events arriving on pipeline.stage-complete.* land
        as edges, not field overwrites. Preserves the JarvisRoutingHistoryEntry
        frozen=True invariant.
        """

    async def flush(self, *, timeout: float = 5.0) -> None:
        """Drain in-flight async writes on shutdown. Bounded wait then WARN."""
```

---

## 5. `infrastructure/dispatch_semaphore.py`

```python
class DispatchSemaphore:
    """asyncio.Semaphore wrapper with structured-error rendering.

    DDR-020: cap=8 in-flight dispatch_by_capability + queue_build calls.
    """

    def __init__(self, *, cap: int = 8) -> None: ...

    def try_acquire(self) -> bool:
        """Non-blocking. True on success, False on overflow.

        The dispatch tool calls try_acquire and returns
        'DEGRADED: dispatch_overloaded — wait and retry' on False.
        """

    def release(self) -> None:
        """Idempotent on release. Safe to call from finally blocks."""

    @property
    def in_flight(self) -> int:
        """For ConcurrentWorkloadSnapshot capture in trace records."""
```

---

## 6. `infrastructure/lifecycle.py` — extensions

`AppState` gains four fields (FEAT-JARVIS-004):

```python
@dataclasses.dataclass(frozen=True)
class AppState:
    # ... Phase 1/2/3 fields unchanged ...

    # FEAT-JARVIS-004 additions
    nats_client: NATSClient | None = None
    graphiti_client: GraphitiClient | None = None
    routing_history_writer: RoutingHistoryWriter | None = None
    fleet_heartbeat_task: asyncio.Task[None] | None = None
```

`build_app_state(config)` extends FEAT-J003's sequence per design §8. `shutdown(state)` extends with the reverse-order teardown per design §8.

---

## 7. Tool-level wiring — `assemble_tool_list` extensions

```python
def assemble_tool_list(
    config: JarvisConfig,
    capabilities_registry: CapabilitiesRegistry,
    llamaswap_adapter: LlamaSwapAdapter | None = None,
    *,
    nats_client: NATSClient | None = None,                # ← NEW in 004
    routing_history_writer: RoutingHistoryWriter | None = None,  # ← NEW in 004
    dispatch_semaphore: DispatchSemaphore | None = None,  # ← NEW in 004
    include_frontier: bool = True,
) -> list[BaseTool]:
    """Snapshots capabilities_registry into both _capability_registry
    module attributes (capabilities.py + dispatch.py) per ASSUM-006.

    Snapshots nats_client, routing_history_writer, dispatch_semaphore into
    dispatch.py module attributes for use by dispatch_by_capability.

    All four module attributes default to None / empty list — Phase 1
    invariant preserved (a bare import yields functional tools that
    surface DEGRADED strings rather than raising).
    """
```

The four module-level swap-point attributes in `tools/dispatch.py`:

```python
_nats_client: NATSClient | None = None                            # ← NEW
_routing_history_writer: RoutingHistoryWriter | None = None       # ← NEW
_dispatch_semaphore: DispatchSemaphore | None = None              # ← NEW
_capability_registry: list[CapabilityDescriptor] = []             # Phase 2 (now populated from
                                                                  #          capabilities_registry.snapshot())
```

The Phase 2 `_stub_response_hook`, `LOG_PREFIX_DISPATCH` constants are **deleted** (DDR-009 retired); the TASK-J002-021 grep invariant test is updated to assert their absence.

---

## 8. Cross-cutting — config additions (`config/settings.py`)

```python
class JarvisConfig(BaseSettings):
    # ... Phase 1/2/3 fields unchanged ...

    # ── FEAT-JARVIS-004 — NATS ────────────────────────────────────────────
    nats_url: str = "nats://localhost:4222"
    nats_credentials_path: Path | None = None
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=300)

    # ── FEAT-JARVIS-004 — Graphiti ────────────────────────────────────────
    graphiti_endpoint: str | None = None  # None = soft-fail at startup
    graphiti_api_key: SecretStr | None = None
    jarvis_traces_dir: Path = Path.home() / ".jarvis" / "traces"

    # ── FEAT-JARVIS-004 — dispatch ────────────────────────────────────────
    specialist_dispatch_timeout_seconds: int = Field(default=60, ge=5, le=600)
    dispatch_concurrent_cap: int = Field(default=8, ge=1, le=64)

    # ── FEAT-JARVIS-004 — fleet ───────────────────────────────────────────
    jarvis_agent_version: str = Field(
        default="0.4.0",  # tracks the FEAT-JARVIS-004 release
        pattern=r"^\d+\.\d+\.\d+(?:-[a-z0-9.]+)?$",
    )
```

`JARVIS_NATS_URL`, `JARVIS_GRAPHITI_ENDPOINT`, etc. resolve via the existing `env_prefix="JARVIS_"`.

---

*"Typed Python APIs at the boundary; the supervisor never sees them."* — [ADR-ARCH-006](../../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md)
