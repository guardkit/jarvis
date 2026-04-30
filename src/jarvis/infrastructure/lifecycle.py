"""Application lifecycle management — startup and shutdown.

Provides :func:`build_app_state` and :func:`shutdown` for bootstrapping and
tearing down the Jarvis runtime, plus the frozen :class:`AppState`
dataclass that holds all runtime dependencies.

``build_app_state()`` configures structured logging **before** any validation
so that configuration errors are emitted as structured events.  It returns a
fully populated ``AppState`` — supervisor, session manager, capability
registry and (since FEAT-JARVIS-003) the ``LlamaSwapAdapter`` are always
wired.

TASK-J002-017 extended ``build_app_state`` with two additional steps that
sit between store creation and supervisor build:

1. ``capability_registry = load_stub_registry(config.stub_capabilities_path)``
   — startup-fatal if the YAML is missing (FEAT-JARVIS-002 design §7).
2. ``tool_list = assemble_tool_list(config, capability_registry)`` — wires
   the 9 Phase 2 tools and snapshots the registry into the capability +
   dispatch tool modules (ASSUM-006 snapshot isolation).

TASK-J003-015 (FEAT-JARVIS-003 design §8 "← NEW") layers four further
additions on top:

3. ``LlamaSwapAdapter`` is constructed from
   ``config.llama_swap_base_url`` and stored on :class:`AppState` so the
   supervisor's swap-aware voice-latency policy (ADR-ARCH-012) can probe
   the GB10 builders-group state at request time.
4. ``OPENAI_BASE_URL`` is exported into ``os.environ`` as
   ``<config.llama_swap_base_url>/v1`` *before* the
   ``jarvis-reasoner`` AsyncSubAgent's leaf graph compiles — that
   compilation runs through ``init_chat_model`` which reads the env
   var to route OpenAI-shaped requests at the local llama-swap proxy.
5. ``async_subagents = build_async_subagents(config)`` is built and
   threaded into ``build_supervisor`` so DeepAgents'
   ``AsyncSubAgentMiddleware`` injects its five operational tools
   (``start_async_task`` / ``check_async_task`` / ``update_async_task``
   / ``cancel_async_task`` / ``list_async_tasks``).
6. ``assemble_tool_list`` is called twice — once with
   ``include_frontier=True`` (the *attended* 10-tool surface) and once
   with ``include_frontier=False`` (the *ambient* 9-tool surface that
   excludes ``escalate_to_frontier`` per DDR-014's registration-layer
   gate).  The ambient list is exposed via
   ``ambient_tool_factory=lambda: tool_list_ambient`` so ambient /
   learning consumers can pull the canonical list without re-running
   the lifecycle wiring.

All seams are imported at module top so tests can patch them via the
canonical ``jarvis.infrastructure.lifecycle`` namespace.

This module also hosts the swap-aware voice-ack policy helpers
(:func:`should_emit_voice_ack` and :func:`emit_voice_ack_and_queue`).
They live next to :class:`AppState` and the LlamaSwap wiring rather
than in the supervisor module so the supervisor stays free of cross
imports back into ``jarvis.adapters`` (the supervisor only consumes
the types via the lifecycle's typed surface).
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
from typing import TYPE_CHECKING, Any

import structlog

from jarvis.adapters.llamaswap import LlamaSwapAdapter
from jarvis.adapters.types import SwapStatus
from jarvis.agents import build_supervisor
from jarvis.agents.subagent_registry import build_async_subagents
from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.capabilities_registry import (
    CapabilitiesRegistry,
    LiveCapabilitiesRegistry,
    StubCapabilitiesRegistry,
)
from jarvis.infrastructure.dispatch_semaphore import DispatchSemaphore
from jarvis.infrastructure.fleet_registration import (
    JARVIS_AGENT_ID,
    build_jarvis_manifest,
    deregister_from_fleet,
    heartbeat_loop,
    register_on_fleet,
)
from jarvis.infrastructure.forge_notifications import ForgeNotificationsSubscriber
from jarvis.infrastructure.logging import configure
from jarvis.infrastructure.nats_client import NATSClient
from jarvis.infrastructure.routing_history import (
    GraphitiClientProtocol,
    RoutingHistoryWriter,
)
from jarvis.sessions.manager import SessionManager
from jarvis.shared.exceptions import ConfigurationError
from jarvis.tools import (
    CapabilityDescriptor,
    assemble_tool_list,
    load_stub_registry,
)
from jarvis.tools import dispatch as _dispatch

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph
    from langgraph.store.base import BaseStore

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Voice-ack policy constants (ADR-ARCH-012 + FEAT-JARVIS-003 design §8).
#
# The ETA threshold is the boundary above which a voice-reactive adapter
# (e.g. ``reachy``) should hear a TTS acknowledgement instead of dead air
# while the local model warms up.  Boundary table from the AC:
#
#     eta_seconds  | should_emit_voice_ack
#     -------------+-----------------------
#                0 | False  (already loaded)
#               30 | False  (at threshold — no ack)
#               31 | True   (above threshold)
#              240 | True   (cold start)
#
# ``DEFAULT_VOICE_REACTIVE_ADAPTER_IDS`` is the closed set of adapters
# that benefit from the audible ack.  ``reachy`` is the only voice-
# reactive surface in Phase 2; future adapters opt in by either being
# added here (with a DDR) or by the caller passing a
# ``voice_reactive_adapters`` override at the call site.
# ---------------------------------------------------------------------------
VOICE_ACK_ETA_THRESHOLD_SECONDS: int = 30
DEFAULT_VOICE_REACTIVE_ADAPTER_IDS: frozenset[str] = frozenset({"reachy"})

# The TTS ack copy is a stub in Phase 2; the real text and the dispatch
# queueing channel land alongside the live llama-swap probe in
# FEAT-JARVIS-004.  The string is short and self-contained so the TTS
# pipeline can synthesize it deterministically.
VOICE_ACK_TTS_TEXT: str = (
    "One moment — I'm warming up the local reasoner. I'll come back to you as soon as it's ready."
)


@dataclasses.dataclass(frozen=True)
class VoiceAckOutcome:
    """Outcome of evaluating the swap-aware voice-ack policy.

    Returned by :func:`emit_voice_ack_and_queue`.  The supervisor uses
    the flags to decide whether to (a) speak the TTS ack and (b) queue
    the original request for dispatch once the swap completes — the two
    actions are coupled in the AC ("emits the TTS ack stub and queues
    the request for dispatch") so the outcome carries them together.

    Attributes:
        emitted: ``True`` iff the supervisor should speak ``ack_text``.
        queued: ``True`` iff the supervisor should park the originating
            request and re-issue it once the swap completes.  In Phase 2
            this is always equal to ``emitted``; FEAT-JARVIS-004 may
            split the two when the live probe distinguishes "warming"
            from "loaded".
        ack_text: The TTS ack copy to speak.  ``None`` when the policy
            does not fire — callers must guard on ``emitted`` before
            using this field.
    """

    emitted: bool
    queued: bool
    ack_text: str | None


def should_emit_voice_ack(
    adapter_id: str,
    swap_status: SwapStatus,
    *,
    voice_reactive_adapters: frozenset[str] | None = None,
) -> bool:
    """Decide whether the supervisor should emit a TTS voice acknowledgement.

    The policy fires iff BOTH of the following hold:

    1. ``adapter_id`` is in the configured voice-reactive set
       (``DEFAULT_VOICE_REACTIVE_ADAPTER_IDS`` by default — currently
       ``frozenset({"reachy"})``).
    2. ``swap_status.eta_seconds`` is **strictly greater than**
       :data:`VOICE_ACK_ETA_THRESHOLD_SECONDS` (30).  The boundary is
       deliberately exclusive so the AC's table holds verbatim:
       ``eta_seconds=30`` → ``False``; ``eta_seconds=31`` → ``True``.

    The function is pure and side-effect free; it never logs and never
    contacts the network.  The caller (typically
    :func:`emit_voice_ack_and_queue` or the supervisor's request-time
    dispatch) is responsible for any subsequent action.

    Args:
        adapter_id: The active session's adapter identifier — e.g.
            ``"reachy"``, ``"cli"``, ``"telegram"``, ``"dashboard"``.
            Compared against the voice-reactive set with case-sensitive
            equality.
        swap_status: The :class:`~jarvis.adapters.types.SwapStatus`
            snapshot from ``llamaswap_adapter.get_status(<alias>)``.
            Only ``eta_seconds`` is read.
        voice_reactive_adapters: Optional override for the voice-
            reactive set.  When ``None`` (the default) the function
            uses :data:`DEFAULT_VOICE_REACTIVE_ADAPTER_IDS`.  Tests and
            future adapters that opt in dynamically can pass a custom
            ``frozenset[str]`` here without touching the module global.

    Returns:
        ``True`` iff both gates above are open.  ``False`` otherwise.
    """
    voice_set = (
        voice_reactive_adapters
        if voice_reactive_adapters is not None
        else DEFAULT_VOICE_REACTIVE_ADAPTER_IDS
    )
    return adapter_id in voice_set and swap_status.eta_seconds > VOICE_ACK_ETA_THRESHOLD_SECONDS


def emit_voice_ack_and_queue(
    adapter_id: str,
    swap_status: SwapStatus,
    *,
    voice_reactive_adapters: frozenset[str] | None = None,
) -> VoiceAckOutcome:
    """Apply the swap-aware voice-ack policy and return the outcome.

    When :func:`should_emit_voice_ack` returns ``True`` the supervisor
    must speak the TTS ack copy AND queue the originating request for
    dispatch once the swap completes — the two actions are coupled by
    the AC.  This helper returns a single :class:`VoiceAckOutcome` so
    the supervisor cannot accidentally do one without the other.

    The Phase 2 implementation is a stub: it logs the decision and
    returns the outcome; the live wiring to the TTS pipeline + the
    actual dispatch queue lands in FEAT-JARVIS-004.  Tests assert the
    outcome's ``emitted`` / ``queued`` flags and the boundary
    behaviour; the integration with the TTS / queue subsystems is
    covered by their own tests once those subsystems land.

    Args:
        adapter_id: The active session's adapter identifier.
        swap_status: The :class:`~jarvis.adapters.types.SwapStatus`
            snapshot for the alias the supervisor wants to dispatch to.
        voice_reactive_adapters: Optional override forwarded verbatim
            to :func:`should_emit_voice_ack`.

    Returns:
        A :class:`VoiceAckOutcome` with the resolved flags and ack
        text.
    """
    if should_emit_voice_ack(
        adapter_id,
        swap_status,
        voice_reactive_adapters=voice_reactive_adapters,
    ):
        logger.info(
            "voice_ack_emitted",
            adapter_id=adapter_id,
            loaded_model=swap_status.loaded_model,
            eta_seconds=swap_status.eta_seconds,
            source=swap_status.source,
        )
        return VoiceAckOutcome(
            emitted=True,
            queued=True,
            ack_text=VOICE_ACK_TTS_TEXT,
        )
    return VoiceAckOutcome(emitted=False, queued=False, ack_text=None)


@dataclasses.dataclass(frozen=True)
class AppState:
    """Immutable container for fully-wired runtime dependencies.

    Attributes:
        config: Validated application configuration.
        supervisor: The compiled LangGraph supervisor graph.
        store: The LangGraph memory store instance.
        session_manager: The session manager wired over supervisor + store.
        capability_registry: Capability descriptors loaded from the
            stub registry at startup.  ``build_app_state`` populates this
            from ``load_stub_registry(config.stub_capabilities_path)``;
            tests that construct ``AppState`` directly may rely on the
            empty default.
        llamaswap_adapter: The :class:`LlamaSwapAdapter` instance the
            supervisor uses to probe llama-swap's builders-group state
            for swap-aware voice-latency decisions (ADR-ARCH-012).  The
            field is optional with a ``None`` default so tests that
            construct an ``AppState`` directly do not have to wire one;
            ``build_app_state`` always populates it from
            ``config.llama_swap_base_url``.
        nats_client: Connected :class:`NATSClient` wrapper, or ``None``
            when NATS soft-failed at startup (DDR-021).  ``shutdown`` calls
            :meth:`NATSClient.drain` when present.
        graphiti_client: Connected Graphiti client (any object satisfying
            :class:`GraphitiClientProtocol`), or ``None`` when Graphiti
            soft-failed at startup (DDR-019).  ``shutdown`` calls
            ``aclose()`` when present.
        routing_history_writer: Configured :class:`RoutingHistoryWriter`
            owning the in-flight Graphiti submission tasks.  Always
            populated by ``build_app_state`` even when
            ``graphiti_client is None`` — the writer enters degraded mode
            (every ``write_*`` becomes a no-op + WARN once).
        fleet_heartbeat_task: The :class:`asyncio.Task` running
            :func:`heartbeat_loop` against the live NATS broker, or
            ``None`` when NATS soft-failed at startup.  ``shutdown``
            cancels it before draining the broker so the deregister hop
            is the last write the broker observes.
        capabilities_registry: The Protocol-shaped
            :class:`CapabilitiesRegistry` (live KV-watch or stub YAML)
            backing the supervisor's capability prompt block at runtime.
            ``shutdown`` calls ``close()`` to detach the watcher.
        forge_subscriber: The
            :class:`ForgeNotificationsSubscriber` started over
            ``pipeline.stage-complete.>`` for in-process routing of Forge
            stage-complete events back to the originating session FIFO
            (FEAT-JARVIS-005 / TASK-J005-008). ``None`` when NATS soft-
            failed at startup — ``shutdown`` skips the ``stop()`` step in
            that case.
    """

    config: JarvisConfig
    supervisor: CompiledStateGraph[Any, Any, Any, Any]
    store: BaseStore
    session_manager: SessionManager
    capability_registry: list[CapabilityDescriptor] = dataclasses.field(default_factory=list)
    llamaswap_adapter: LlamaSwapAdapter | None = None
    nats_client: NATSClient | None = None
    graphiti_client: GraphitiClientProtocol | None = None
    routing_history_writer: RoutingHistoryWriter | None = None
    fleet_heartbeat_task: asyncio.Task[None] | None = None
    capabilities_registry: CapabilitiesRegistry | None = None
    forge_subscriber: ForgeNotificationsSubscriber | None = None


# ---------------------------------------------------------------------------
# Graphiti connect seam — DDR-019 soft-fail.
#
# A thin, patchable helper that hides the graphiti-core import from the
# lifecycle hot path. Returns ``None`` on any failure (missing endpoint,
# import error, connect error). Tests patch this symbol directly via
# ``patch("jarvis.infrastructure.lifecycle._connect_graphiti", ...)`` so the
# soft-fail branch is exercisable without importing graphiti-core in CI.
# ---------------------------------------------------------------------------


class _PreloadedCapabilitiesRegistry:
    """Protocol-compatible wrapper around a pre-loaded descriptor list.

    Used by ``build_app_state`` when ``StubCapabilitiesRegistry`` cannot
    re-read its YAML source (e.g. tests patched ``load_stub_registry``
    higher in the call stack and the on-disk path no longer resolves).
    The existing ``capability_registry`` list is the authoritative
    snapshot for the lifetime of the process; ``refresh`` and
    ``subscribe_updates`` are intentionally inert because there is no
    source of truth to re-read.
    """

    __slots__ = ("_descriptors",)

    def __init__(self, descriptors: list[CapabilityDescriptor]) -> None:
        self._descriptors = list(descriptors)

    def snapshot(self) -> list[CapabilityDescriptor]:
        return list(self._descriptors)

    async def refresh(self) -> None:
        return None

    async def subscribe_updates(self, callback: Any) -> None:
        del callback
        return None

    async def close(self) -> None:
        return None


def _build_stub_capabilities_registry(
    config: JarvisConfig,
    preloaded: list[CapabilityDescriptor],
) -> CapabilitiesRegistry:
    """Construct a Stub-style capabilities registry without re-reading the YAML.

    ``StubCapabilitiesRegistry.__init__`` re-loads the YAML at the
    configured path. When the path is unresolvable (test environments
    that patch ``load_stub_registry`` higher up but leave the on-disk
    file shadowed by an autouse ``chdir``), we fall back to the
    Protocol-compatible :class:`_PreloadedCapabilitiesRegistry` shim
    that wraps the already-loaded descriptor list.
    """
    try:
        return StubCapabilitiesRegistry(config.stub_capabilities_path)
    except FileNotFoundError:
        logger.info(
            "jarvis_capabilities_registry_preloaded_fallback",
            stub_capabilities_path=str(config.stub_capabilities_path),
            count=len(preloaded),
        )
        return _PreloadedCapabilitiesRegistry(preloaded)


async def _connect_nats(config: JarvisConfig) -> NATSClient | None:
    """Lifecycle-side seam for :meth:`NATSClient.connect`.

    Tests patch this thin wrapper rather than the class method so the
    NATSClient unit tests (which exercise the real ``connect`` surface)
    are unaffected by the lifecycle's autouse stub.
    """
    return await NATSClient.connect(config)


async def _connect_graphiti(config: JarvisConfig) -> GraphitiClientProtocol | None:
    """Connect to Graphiti per DDR-019 — return ``None`` on any failure.

    The function is intentionally permissive: a missing
    ``graphiti_endpoint``, an unimportable ``graphiti_core`` SDK, or a live
    connect failure all converge on the same ``None`` return so the
    supervisor lifecycle continues into degraded-mode wiring without a
    second branch.

    Args:
        config: Validated :class:`JarvisConfig`. Reads
            ``config.graphiti_endpoint`` and ``config.graphiti_api_key``.

    Returns:
        A connected Graphiti client on success; ``None`` on any failure.
        Never raises.
    """
    if config.graphiti_endpoint is None:
        logger.info(
            "graphiti_skipped_no_endpoint",
            graphiti_endpoint=None,
        )
        return None
    try:
        # Lazy import — graphiti-core is an optional extra (TASK-J004-002).
        from graphiti_core import Graphiti

        api_key = (
            config.graphiti_api_key.get_secret_value()
            if config.graphiti_api_key is not None
            else None
        )
        # Graphiti's constructor signature varies across 0.9.x; we forward
        # the kwargs the SDK currently accepts via duck typing, falling back
        # to the positional ``uri`` form when ``api_key`` is unsupported.
        kwargs: dict[str, Any] = {"uri": config.graphiti_endpoint}
        if api_key is not None:
            kwargs["api_key"] = api_key
        try:
            client: Any = Graphiti(**kwargs)
        except TypeError:
            # Older SDKs reject ``api_key``; fall back to URI-only.
            client = Graphiti(uri=config.graphiti_endpoint)
        logger.info(
            "graphiti_connect_success",
            graphiti_endpoint=config.graphiti_endpoint,
        )
        # The graphiti-core ``Graphiti`` client implements ``add_episode``
        # so it satisfies the GraphitiClientProtocol structural surface;
        # the cast keeps mypy strict-clean without forcing a Protocol
        # subclass declaration into the third-party SDK.
        return client  # type: ignore[no-any-return]
    except Exception as exc:
        logger.error(
            "graphiti_connect_failed",
            graphiti_endpoint=config.graphiti_endpoint,
            error_class=type(exc).__name__,
            error=str(exc),
        )
        return None


async def build_app_state(config: JarvisConfig) -> AppState:
    """Bootstrap the Jarvis application into a fully-wired :class:`AppState`.

    Sequence:
        1. (Re-)configure structured logging at ``config.log_level``.
        2. Validate provider keys — raises :class:`ConfigurationError`
           if the selected provider's credentials are missing.
        3. Build the memory store (``InMemoryStore`` for Phase 1).
        4. Load the stub capability registry from
           ``config.stub_capabilities_path`` — startup-fatal if missing.
        5. Construct the :class:`LlamaSwapAdapter` from
           ``config.llama_swap_base_url`` (FEAT-JARVIS-003 ← NEW).
        6. Export ``OPENAI_BASE_URL=<llama_swap_base_url>/v1`` into
           ``os.environ`` so the ``jarvis-reasoner`` leaf graph routes
           OpenAI-shaped requests at the local proxy when DeepAgents
           compiles it (FEAT-JARVIS-003 ← NEW).
        7. Build ``async_subagents = build_async_subagents(config)``
           (FEAT-JARVIS-003 ← NEW).
        8. Assemble the *attended* tool list via
           ``assemble_tool_list(config, registry, include_frontier=True)``
           (10 tools — FEAT-J002 baseline plus
           ``escalate_to_frontier``).  This call also snapshots the
           registry into the capability + dispatch tool modules per
           ASSUM-006.
        9. Assemble the *ambient* tool list via
           ``assemble_tool_list(config, registry, include_frontier=False)``
           (9 tools — same baseline minus ``escalate_to_frontier``,
           DDR-014 registration-layer gate).
        10. Build the supervisor compiled graph with the attended tools,
            the capability catalogue, the async-subagent list, and an
            ``ambient_tool_factory`` closure that returns the ambient
            list.
        11. Wire a :class:`SessionManager` over supervisor + store.
        12. Return an :class:`AppState` with every field populated,
            including the new ``llamaswap_adapter``.

    ``configure()`` is idempotent, so callers are free to configure logging
    themselves at process entry (so that ``pydantic.ValidationError`` at
    ``JarvisConfig()`` load is emitted as a structured event) — this call
    will simply re-apply the user-configured level over that default.

    Args:
        config: A validated :class:`JarvisConfig` instance.

    Returns:
        A fully wired :class:`AppState`.

    Raises:
        ConfigurationError: If provider key validation fails.
        FileNotFoundError: If the configured stub capabilities path does
            not exist (startup-fatal per FEAT-JARVIS-002 design §7).
    """
    # 1. Re-apply logging config at the user-selected level (idempotent).
    configure(config.log_level)

    log = structlog.get_logger(__name__)
    log.info("jarvis_startup_begin", supervisor_model=config.supervisor_model)

    # 2. Validate provider keys — may raise ConfigurationError.
    try:
        config.validate_provider_keys()
    except ConfigurationError:
        log.error(
            "jarvis_startup_failed",
            reason="provider_key_validation_failed",
            supervisor_model=config.supervisor_model,
        )
        raise

    # 3. Build memory store (Phase 1: in_memory only).
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    log.info("jarvis_store_ready", backend=config.memory_store_backend)

    # 4. Load the stub capability registry — startup-fatal if missing.
    capability_registry = load_stub_registry(config.stub_capabilities_path)
    log.info(
        "jarvis_capability_registry_loaded",
        path=str(config.stub_capabilities_path),
        count=len(capability_registry),
    )

    # 5. Construct the LlamaSwapAdapter.  Phase 2 is read-only / stubbed;
    # FEAT-JARVIS-004 swaps in a live HTTP probe without changing the
    # public surface (TASK-J003-007 / DDR-015).
    llamaswap_adapter = LlamaSwapAdapter(base_url=config.llama_swap_base_url)
    log.info(
        "jarvis_llamaswap_adapter_ready",
        base_url=config.llama_swap_base_url,
    )

    # 6. Export ``OPENAI_BASE_URL`` so the ``jarvis-reasoner`` leaf graph
    # picks up the local proxy URL when DeepAgents compiles it.  This
    # MUST happen BEFORE ``build_async_subagents`` runs because the
    # AsyncSubAgentMiddleware will resolve the ``graph_id`` at
    # ``create_deep_agent`` time and the leaf graph's
    # ``init_chat_model`` instantiation reads the env var.
    openai_base_url = f"{config.llama_swap_base_url}/v1"
    os.environ["OPENAI_BASE_URL"] = openai_base_url
    log.info(
        "jarvis_openai_base_url_set",
        openai_base_url=openai_base_url,
    )

    # 7. Compose the AsyncSubAgent list (currently a single
    # ``jarvis-reasoner`` entry per ADR-ARCH-011 / DDR-010).  Pure
    # function — no network I/O — so it is safe to call before the
    # supervisor is built.
    async_subagents = build_async_subagents(config)
    log.info(
        "jarvis_async_subagents_built",
        count=len(async_subagents),
    )

    # 7b. FEAT-JARVIS-004 wiring — connect the live transports per
    # DDR-021 (NATS soft-fail) and DDR-019 (Graphiti soft-fail), then
    # build the writer + dispatch semaphore the swapped-in dispatch tools
    # consume. ``register_on_fleet`` failures convert to a startup WARN so
    # a degraded broker (e.g. JetStream offline) does not block the
    # supervisor process.
    nats_client = await _connect_nats(config)
    graphiti_client = await _connect_graphiti(config)
    routing_history_writer = RoutingHistoryWriter(graphiti_client, config)
    log.info(
        "jarvis_routing_history_writer_ready",
        graphiti_available=graphiti_client is not None,
    )

    fleet_heartbeat_task: asyncio.Task[None] | None = None
    capabilities_registry: CapabilitiesRegistry
    if nats_client is not None:
        manifest = build_jarvis_manifest(config)
        try:
            await register_on_fleet(nats_client, manifest)
        except Exception as exc:
            # DDR-021 soft-fail at the registration boundary — a flaky
            # broker must not block startup. The supervisor stays up;
            # downstream fleet observers simply will not see Jarvis.
            log.warning(
                "jarvis_fleet_register_failed",
                agent_id=manifest.agent_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )
        fleet_heartbeat_task = asyncio.create_task(
            heartbeat_loop(nats_client, manifest, config),
            name="jarvis_fleet_heartbeat",
        )
        try:
            capabilities_registry = await LiveCapabilitiesRegistry.create(nats_client)
        except Exception as exc:
            # DDR-021 soft-fail — bind failure falls back to the stub
            # YAML so the prompt block is still populated.
            log.warning(
                "jarvis_live_capabilities_registry_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)
    else:
        capabilities_registry = _build_stub_capabilities_registry(config, capability_registry)

    dispatch_semaphore = DispatchSemaphore(cap=config.dispatch_concurrent_cap)
    log.info(
        "jarvis_dispatch_semaphore_ready",
        cap=config.dispatch_concurrent_cap,
    )

    # 7c. FEAT-JARVIS-005 (TASK-J005-008) — start the Forge stage-complete
    # subscriber over ``pipeline.stage-complete.>``. The subscriber is
    # constructed only when NATS is up (DDR-021 soft-fail keeps the
    # supervisor alive on NATS-down) and started AFTER fleet registration
    # has either succeeded or fallen through, BEFORE the session manager is
    # constructed. ``bind_session_manager(...)`` happens later — once the
    # session manager exists — per design.md §8.
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
            # DDR-021-style soft-fail at the subscriber boundary — a flaky
            # JetStream consumer must not block the supervisor process.
            log.warning(
                "jarvis_forge_subscriber_start_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            forge_subscriber = None
        else:
            log.info(
                "jarvis_forge_subscriber_started",
                queue_cap=config.forge_notifications_queue_cap,
                correlation_cap=config.forge_correlation_map_cap,
            )

    # 8. Assemble the attended tool list (10 tools: FEAT-J002 baseline
    # plus ``escalate_to_frontier``).  The ``include_frontier=True``
    # flag is the default but we pass it explicitly here so the
    # symmetry with the ambient call below stays loud at the call site.
    # This call also snapshots ``capability_registry`` into the
    # capability + dispatch tool modules per ASSUM-006.
    #
    # FEAT-JARVIS-004 — the three new kwargs (``nats_client``,
    # ``routing_history_writer``, ``dispatch_semaphore``) snapshot into
    # the ``jarvis.tools.dispatch`` module attributes so the swapped-in
    # dispatch tool body (TASK-J004-011) finds connected dependencies on
    # every call. Passing the Protocol-shaped registry separately
    # (``capabilities_registry``) keeps the prompt-block wiring
    # backwards compatible — the supervisor prompt still consumes the
    # ``list[CapabilityDescriptor]`` form.
    tool_list_attended = assemble_tool_list(
        config,
        capability_registry,
        include_frontier=True,
        nats_client=nats_client,
        routing_history_writer=routing_history_writer,
        dispatch_semaphore=dispatch_semaphore,
        forge_subscriber=forge_subscriber,
        capabilities_registry=capabilities_registry,
    )
    log.info(
        "jarvis_tool_list_attended_assembled",
        count=len(tool_list_attended),
    )

    # 9. Assemble the ambient tool list (9 tools: attended minus
    # ``escalate_to_frontier``).  This is the canonical surface
    # exposed via the ``ambient_tool_factory`` closure on the
    # supervisor — DDR-014's registration-layer gate.
    tool_list_ambient = assemble_tool_list(
        config,
        capability_registry,
        include_frontier=False,
        nats_client=nats_client,
        routing_history_writer=routing_history_writer,
        dispatch_semaphore=dispatch_semaphore,
        forge_subscriber=forge_subscriber,
        capabilities_registry=capabilities_registry,
    )
    log.info(
        "jarvis_tool_list_ambient_assembled",
        count=len(tool_list_ambient),
    )

    # 10. Build supervisor with the attended tools, the capability
    # catalogue, the async-subagent list, and an ambient_tool_factory
    # closure that returns the ambient list.  The closure is bound to
    # ``tool_list_ambient`` at startup so ambient consumers always
    # observe the same list the lifecycle assembled (no per-invocation
    # re-derivation).
    supervisor = build_supervisor(
        config,
        tools=tool_list_attended,
        available_capabilities=capability_registry,
        async_subagents=async_subagents,
        ambient_tool_factory=lambda: tool_list_ambient,
        capabilities_registry=capabilities_registry,
    )

    # 11. Wire the session manager so AppState is fully populated on return.
    session_manager = SessionManager(supervisor=supervisor, store=store)

    # 11a. FEAT-JARVIS-005 (TASK-J005-008) — late-bind the session manager
    # into the forge subscriber. The two are constructed in strict order
    # (subscriber first, session manager second) so the subscriber can hold
    # a back-reference and route stage-complete events into the per-session
    # FIFO without a circular dependency at construction time. A second
    # bind raises ``RuntimeError`` per the subscriber contract — that is
    # safe here because ``build_app_state`` only binds once.
    if forge_subscriber is not None:
        forge_subscriber.bind_session_manager(session_manager)
        log.info("jarvis_forge_subscriber_bound_session_manager")

    # 11b. Arm DDR-014 Layer 2 — the executor assertion of the
    # constitutional ``escalate_to_frontier`` gate. Until these hooks are
    # assigned, ``_check_attended_only`` short-circuits to ``None`` and the
    # gate operates with two layers (prompt + registration absence) instead
    # of three (FEAT-JARVIS-003 review Finding F1, TASK-J003-FIX-001).
    #
    # ``_current_session_hook`` is bound to ``session_manager.current_session``
    # — a method backed by a per-instance ``contextvars.ContextVar`` set by
    # :meth:`SessionManager.invoke` for the duration of each supervisor
    # turn. The dispatch module reads ``Session.adapter`` and
    # ``Session.metadata['currently_in_subagent']`` from the returned
    # value.
    #
    # ``_async_subagent_frame_hook`` is wired to a callable returning
    # ``None`` per ASSUM-FRONTIER-CALLER-FRAME — DeepAgents 0.5.3 does
    # not expose ``AsyncSubAgentMiddleware`` caller-frame metadata, so
    # the hook deliberately falls through to the session-state fallback
    # (Finding F6's resilience path). When a future DeepAgents release
    # surfaces the metadata, swap this for a probe over the middleware
    # state and the gate gains its second detection path automatically.
    #
    # Plain assignment makes this naturally idempotent: a second
    # ``build_app_state`` call simply replaces the closures with fresh
    # ones bound to the new ``SessionManager``. No stacking, no guards
    # required.
    _dispatch._current_session_hook = session_manager.current_session
    _dispatch._async_subagent_frame_hook = lambda: None
    log.info("jarvis_layer2_hooks_wired")

    state = AppState(
        config=config,
        supervisor=supervisor,
        store=store,
        session_manager=session_manager,
        capability_registry=capability_registry,
        llamaswap_adapter=llamaswap_adapter,
        nats_client=nats_client,
        graphiti_client=graphiti_client,
        routing_history_writer=routing_history_writer,
        fleet_heartbeat_task=fleet_heartbeat_task,
        capabilities_registry=capabilities_registry,
        forge_subscriber=forge_subscriber,
    )

    log.info(
        "jarvis_startup_complete",
        nats_available=nats_client is not None,
        graphiti_available=graphiti_client is not None,
        capabilities_mode="live"
        if isinstance(capabilities_registry, LiveCapabilitiesRegistry)
        else "stub",
    )
    return state


# Backwards-compatible alias — earlier phases imported ``startup`` by name.
startup = build_app_state


async def shutdown(state: AppState) -> None:
    """Gracefully shut down the Jarvis application.

    Idempotent — calling this multiple times on the same state does
    not raise. Each step is independently failure-tolerant: a single
    failed step is logged at WARN and shutdown continues — no step is
    skipped because of an earlier failure (TASK-J004-018 invariant).

    Sequence (per FEAT-JARVIS-004 / FEAT-JARVIS-005 design §8 wiring):

        1. Cancel ``fleet_heartbeat_task`` (if running).
        2. ``await state.forge_subscriber.stop()`` (FEAT-JARVIS-005 — bounded
           at 5s; idempotent on double-shutdown; skipped when ``None``).
        3. ``await deregister_from_fleet(nats_client, "jarvis")``.
        4. ``await capabilities_registry.close()``.
        5. ``await routing_history_writer.flush(timeout=5.0)``.
        6. ``await nats_client.drain(timeout=5.0)``.
        7. ``await graphiti_client.aclose()``.
        8. Disarm Layer-2 hooks + dispatch deps + forge subscriber ref.
        9. ``state.store.close()``.

    Args:
        state: The :class:`AppState` to tear down.
    """
    log = structlog.get_logger(__name__)

    # 1. Cancel the fleet heartbeat task — must run first so the
    # subsequent deregister write is the last fleet observation the
    # broker records (no race against an in-flight heartbeat re-register).
    heartbeat_task = state.fleet_heartbeat_task
    if heartbeat_task is not None and not heartbeat_task.done():
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            # Expected — ``heartbeat_loop`` re-raises CancelledError after
            # a clean INFO log so the asyncio task machinery records the
            # cancellation correctly. No traceback is emitted.
            pass
        except Exception as exc:
            log.warning(
                "jarvis_heartbeat_cancel_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 1b. FEAT-JARVIS-005 (TASK-J005-008) — stop the Forge stage-complete
    # subscriber BEFORE the fleet deregister so any in-flight stage event
    # has a chance to drain through the message handler before the broker
    # connection is torn down. ``ForgeNotificationsSubscriber.stop()`` is
    # itself bounded at 5s via ``asyncio.wait_for`` and never raises out
    # (ASSUM-011 / Group D #14); the wrapper here is a defensive belt-and-
    # braces against future evolutions of the contract.
    if state.forge_subscriber is not None:
        try:
            await state.forge_subscriber.stop()
        except Exception as exc:
            log.warning(
                "jarvis_forge_subscriber_stop_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 2. Deregister from the fleet so downstream observers immediately
    # stop routing to us. ``deregister_from_fleet`` already swallows
    # broker-level failures (logs WARN); we still wrap to keep the
    # invariant explicit at the call site.
    if state.nats_client is not None:
        try:
            await deregister_from_fleet(state.nats_client, JARVIS_AGENT_ID)
        except Exception as exc:
            log.warning(
                "jarvis_deregister_warning",
                agent_id=JARVIS_AGENT_ID,
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 3. Detach the capability KV watcher (idempotent close).
    if state.capabilities_registry is not None:
        try:
            await state.capabilities_registry.close()
        except Exception as exc:
            log.warning(
                "jarvis_capabilities_registry_close_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 4. Flush the routing-history writer — bounded at 5.0s per DDR-019.
    # ``flush`` already swallows broker / Graphiti failures (logs WARN);
    # the wrapper here protects the rest of the sequence from any
    # untyped exception slipping out.
    if state.routing_history_writer is not None:
        try:
            await state.routing_history_writer.flush(timeout=5.0)
        except Exception as exc:
            log.warning(
                "jarvis_routing_history_flush_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 5. Drain NATS — bounded at 5.0s per the DDR-021 contract surface.
    if state.nats_client is not None:
        try:
            await state.nats_client.drain(timeout=5.0)
        except Exception as exc:
            log.warning(
                "jarvis_nats_drain_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 6. Close Graphiti. The graphiti-core convention as of the version
    # pinned in TASK-J004-002 is ``aclose()`` (async). When a future SDK
    # release renames the method, swap the call here — the soft-fail
    # wrapper protects the rest of the sequence.
    if state.graphiti_client is not None:
        try:
            close = getattr(state.graphiti_client, "aclose", None)
            if close is None:
                # Some graphiti-core versions only expose ``close``; fall
                # back rather than raise so the test surface is stable.
                close = getattr(state.graphiti_client, "close", None)
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        except Exception as exc:
            log.warning(
                "jarvis_graphiti_close_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    # 7. Disarm Layer 2 — the dispatch module's hooks must not survive
    # ``shutdown`` so a fresh ``build_app_state`` can rewire them
    # without aliasing this lifecycle's SessionManager.
    try:
        _dispatch._current_session_hook = None
        _dispatch._async_subagent_frame_hook = None
        # FEAT-JARVIS-004 — also disarm the dispatch dependencies so a
        # subsequent ``build_app_state`` call starts from a clean module
        # state and stale references cannot leak into a fresh wiring.
        _dispatch._nats_client = None
        _dispatch._routing_history_writer = None
        _dispatch._dispatch_semaphore = None
        # FEAT-JARVIS-005 (TASK-J005-008) — also disarm the forge subscriber
        # so a re-entrant ``build_app_state`` does not see a stale reference.
        _dispatch._forge_subscriber = None
    except Exception as exc:
        log.warning(
            "jarvis_layer2_disarm_warning",
            error_class=type(exc).__name__,
            error=str(exc),
        )

    # 8. Close the memory store. ``store.close`` is the last step so the
    # Phase-1 invariant (store outlives every async transport) holds.
    if hasattr(state.store, "close"):
        try:
            state.store.close()
        except Exception as exc:
            log.warning(
                "jarvis_store_close_warning",
                error_class=type(exc).__name__,
                error=str(exc),
            )

    log.info("jarvis_shutdown_complete")
