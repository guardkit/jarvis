"""CapabilitiesRegistry — Protocol + Live + Stub implementations.

Public surface (per FEAT-JARVIS-004 API-internal §3):

- :class:`CapabilitiesRegistry` — Protocol unifying live and stub paths so
  ``assemble_tool_list`` and the capability tools never branch on which
  implementation backs the registry.
- :class:`LiveCapabilitiesRegistry` — KV-watch-aware registry backed by
  :class:`nats_core.NATSKVManifestRegistry` with an operator-tunable
  in-memory cache (default 30s).  Created via the async classmethod
  :meth:`LiveCapabilitiesRegistry.create` so the JetStream KV bind happens
  on a connected loop.
- :class:`StubCapabilitiesRegistry` — DDR-021 soft-fail fallback that reads
  the Phase 2 ``stub_capabilities.yaml`` document.  ``subscribe_updates``
  is a no-op because the stub catalogue cannot change at runtime.

The 30s default cache + KV-watch invalidation pattern follows ADR-ARCH-017
(Forge inheritance).  KV-watch fires :meth:`LiveCapabilitiesRegistry.refresh`
unconditionally (bypassing TTL) so the next :meth:`snapshot` reflects the
new fleet membership.

Snapshot isolation (ASSUM-006): :meth:`snapshot` returns a fresh ``list``
copy on every call so callers may iterate / mutate the result without
worrying about a concurrent KV-watch invalidation rebuilding the cache
mid-iteration.

The class lives under :mod:`jarvis.infrastructure` because it owns
external I/O (NATS, filesystem); the dependency-free
:class:`jarvis.tools.capabilities.CapabilityDescriptor` model is
re-imported here so consumers only need this module.

References
----------
* :doc:`docs/design/FEAT-JARVIS-004/contracts/API-internal.md` §3 —
  authoritative class signatures.
* :doc:`docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md`
  — the soft-fail invariant the stub fallback satisfies.
* :doc:`docs/architecture/decisions/ADR-ARCH-017-static-skill-declaration-v1.md`
  — live KV-watch + cache pattern inherited from Forge.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import structlog
from nats_core import AgentManifest, NATSKVManifestRegistry

from jarvis.infrastructure.nats_client import NATSClient
from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools import (
    CapabilityDescriptor,
    CapabilityToolSummary,
    load_stub_registry,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "CapabilitiesRegistry",
    "LiveCapabilitiesRegistry",
    "StubCapabilitiesRegistry",
]


# ---------------------------------------------------------------------------
# Protocol — the contract `assemble_tool_list` and the capability tools
# consume.  Marked ``runtime_checkable`` so tests (and lifecycle code that
# wants to defensively assert "we got SOMETHING that satisfies the surface")
# can use ``isinstance(obj, CapabilitiesRegistry)``.
# ---------------------------------------------------------------------------


@runtime_checkable
class CapabilitiesRegistry(Protocol):
    """Unified surface over the live + stub capability sources.

    Both :class:`LiveCapabilitiesRegistry` and :class:`StubCapabilitiesRegistry`
    satisfy this Protocol so the supervisor wiring never branches on which
    one is in use — DDR-021 soft-fail at the lifecycle boundary picks the
    implementation, downstream code is identical.
    """

    def snapshot(self) -> list[CapabilityDescriptor]:
        """Return the current registry as a fresh ``list`` copy.

        Snapshot isolation per ASSUM-006: callers may iterate or mutate
        the returned list freely without affecting any subsequent call,
        and a concurrent KV-watch invalidation will not change the data
        already returned.
        """
        ...

    async def refresh(self) -> None:
        """Re-read the source of truth and rebuild the cached descriptor list.

        Live impl: fetch all manifests from
        :class:`nats_core.NATSKVManifestRegistry` and rebuild.  Inside
        ``cache_ttl_seconds`` of the previous read this is a no-op.

        Stub impl: re-read the YAML file unconditionally.
        """
        ...

    async def subscribe_updates(self, callback: Callable[[], None]) -> None:
        """Attach a callback fired whenever the source of truth changes.

        Idempotent — calling more than once per session does not open a
        second watcher and does not double-fire the supplied callback.

        Live impl: opens a NATS KV watch on ``agent-registry``.  Stub
        impl: no-op (the YAML cannot change at runtime).
        """
        ...

    async def close(self) -> None:
        """Detach watchers and release underlying handles.  Idempotent."""
        ...


# ---------------------------------------------------------------------------
# Translation: AgentManifest (NATS-side) → CapabilityDescriptor (Jarvis-side).
#
# CapabilityDescriptor is the supervisor-facing projection per
# DM-tool-types §1: a deliberately-narrower view that omits container_id
# and other infrastructure leakage (ADR-ARCH-002).  We carry name/template
# into role/description so the prompt block remains useful even when an
# agent's manifest doesn't carry richer metadata.
# ---------------------------------------------------------------------------


def _manifest_to_descriptor(manifest: AgentManifest) -> CapabilityDescriptor:
    """Project a :class:`nats_core.AgentManifest` into a CapabilityDescriptor.

    The manifest's ``name`` becomes the descriptor's ``role`` (human-
    readable); ``template`` is rendered inline on the description so the
    reasoning model has at least one signal about what the agent is for
    until the fleet schema grows a richer description field.

    Args:
        manifest: A validated :class:`AgentManifest` from the KV bucket.

    Returns:
        A :class:`CapabilityDescriptor` projection — fields the
        supervisor prompt block consumes.
    """
    capability_list = [
        CapabilityToolSummary(
            tool_name=tool.name,
            description=tool.description or tool.name,
            risk_level=tool.risk_level,
        )
        for tool in manifest.tools
    ]
    return CapabilityDescriptor(
        agent_id=manifest.agent_id,
        role=manifest.name,
        description=f"{manifest.name} ({manifest.template})",
        capability_list=capability_list,
        cost_signal="unknown",
        latency_signal="unknown",
        last_heartbeat_at=None,
        trust_tier=manifest.trust_tier,
    )


# ---------------------------------------------------------------------------
# Resolver helpers — module-level so tests can monkeypatch them in place
# (mirrors the project-conventional ``fleet_registration._resolve_registry``
# pattern).  Production code uses these directly; unit tests substitute
# fakes that return mock NATSKVManifestRegistry / watcher objects so the
# Live path is exercisable without an in-process broker.
# ---------------------------------------------------------------------------


async def _resolve_registry(client: Any) -> NATSKVManifestRegistry:
    """Open (or bind to) the ``agent-registry`` JetStream KV bucket.

    Accepts either the local :class:`jarvis.infrastructure.NATSClient`
    wrapper (which exposes the underlying client on ``.client``) or a raw
    ``nats.aio.client.Client`` instance.  Anything with a ``jetstream()``
    method satisfies the duck-typed contract that
    :meth:`NATSKVManifestRegistry.create` requires.

    Args:
        client: The NATS client (or wrapper) to bind the registry to.

    Returns:
        A registry bound to the ``agent-registry`` KV bucket.
    """
    nc = getattr(client, "client", client)
    return await NATSKVManifestRegistry.create(nc)


async def _resolve_watcher(registry: NATSKVManifestRegistry) -> Any:
    """Open a KV watcher on the registry's underlying bucket.

    Returns an async-iterable object whose ``__anext__`` yields KV update
    events.  ``None`` items are treated as the "history-complete"
    sentinel by :class:`LiveCapabilitiesRegistry` and skipped.

    The watcher must also expose an awaitable ``stop()`` so
    :meth:`LiveCapabilitiesRegistry.close` can detach cleanly.

    Args:
        registry: The :class:`NATSKVManifestRegistry` whose underlying
            ``_kv`` bucket we want to watch.

    Returns:
        A NATS JetStream KV watcher (``KeyWatcher``) that yields updates
        as they land in the bucket.
    """
    # NATSKVManifestRegistry stores the KV bucket on ``_kv``; the
    # ``KeyValue`` API exposes ``watchall()`` for cross-key watches.
    return await registry._kv.watchall()


# ---------------------------------------------------------------------------
# LiveCapabilitiesRegistry
# ---------------------------------------------------------------------------


class LiveCapabilitiesRegistry:
    """KV-backed capability registry with TTL cache + watch invalidation.

    Per ADR-ARCH-017 the supervisor reads the fleet through an in-memory
    cache (default 30s) refreshed by a NATS KV watch on the
    ``agent-registry`` bucket.  ``snapshot()`` is sync and returns from
    the cache; ``refresh()`` is the cache-aware fetcher; the KV watch
    bypasses TTL on every event so the cache reflects fleet changes
    promptly.

    Construction is async — use :meth:`create` rather than the constructor
    so the initial KV warm-up completes before the first ``snapshot()``.
    """

    __slots__ = (
        "_cache",
        "_cache_loaded_at",
        "_cache_ttl",
        "_cache_warmed",
        "_callback",
        "_closed",
        "_lock",
        "_registry",
        "_subscribed",
        "_watcher",
        "_watcher_task",
    )

    def __init__(
        self,
        registry: NATSKVManifestRegistry,
        *,
        cache_ttl_seconds: int = 30,
    ) -> None:
        """Construct an unwarmed registry.  Prefer :meth:`create`.

        Args:
            registry: A :class:`NATSKVManifestRegistry` already bound to
                the ``agent-registry`` KV bucket.
            cache_ttl_seconds: How long a successful KV read remains
                authoritative before :meth:`refresh` re-reads.  ``0``
                disables caching (every refresh re-reads); the KV watch
                bypasses TTL regardless.
        """
        self._registry = registry
        self._cache_ttl = cache_ttl_seconds
        self._cache: list[CapabilityDescriptor] = []
        self._cache_loaded_at: float = 0.0
        self._cache_warmed: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        self._callback: Callable[[], None] | None = None
        self._subscribed: bool = False
        self._watcher: Any | None = None
        self._watcher_task: asyncio.Task[None] | None = None
        self._closed: bool = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    async def create(
        cls,
        client: NATSClient,
        *,
        cache_ttl_seconds: int = 30,
    ) -> LiveCapabilitiesRegistry:
        """Build a usable registry bound to *client*'s JetStream KV.

        DDR-021 boundary: any failure to acquire the KV bucket (JetStream
        unavailable, bucket-create denied, broker disconnected) raises
        :class:`NATSConnectionError`.  The lifecycle catches this and
        falls back to :class:`StubCapabilitiesRegistry`.

        After binding, the cache is warmed via an immediate
        :meth:`refresh`, so the very first :meth:`snapshot` call returns
        fresh data rather than an empty list.

        Args:
            client: A connected :class:`jarvis.infrastructure.NATSClient`
                (or a raw ``nats.aio.Client``).  The signature names the
                wrapper to satisfy the FEAT-JARVIS-004 NATS_CLIENT_API
                seam contract.
            cache_ttl_seconds: Cache window for :meth:`refresh`; default
                30s per ADR-ARCH-017.

        Returns:
            A :class:`LiveCapabilitiesRegistry` whose cache is already
            warmed (first snapshot is fresh).

        Raises:
            NATSConnectionError: If the JetStream KV bind fails for any
                reason (the originating exception is chained as
                ``__cause__`` for diagnosis).
        """
        try:
            registry = await _resolve_registry(client)
        except Exception as exc:
            raise NATSConnectionError(
                f"Failed to bind agent-registry KV bucket: {type(exc).__name__}: {exc}"
            ) from exc

        instance = cls(registry, cache_ttl_seconds=cache_ttl_seconds)
        try:
            await instance._force_refresh()
        except Exception as exc:
            raise NATSConnectionError(
                f"Failed to perform initial capability KV read: {type(exc).__name__}: {exc}"
            ) from exc
        return instance

    # ------------------------------------------------------------------
    # Snapshot / refresh
    # ------------------------------------------------------------------

    def snapshot(self) -> list[CapabilityDescriptor]:
        """Return a fresh ``list`` copy of the cached descriptors.

        Snapshot isolation per ASSUM-006: every call constructs a new
        list so a caller's iteration cannot be affected by a concurrent
        KV-watch invalidation rebuilding the underlying cache.
        """
        return list(self._cache)

    async def refresh(self) -> None:
        """Re-read the KV bucket if the TTL window has elapsed.

        Within ``cache_ttl_seconds`` of the last successful read this is
        a silent no-op — the cached descriptor list is treated as
        authoritative.  With ``cache_ttl_seconds=0`` every call performs
        an unconditional KV read (operator-tunable for integration tests
        that need deterministic invalidation assertions).
        """
        if self._cache_warmed and self._cache_ttl > 0:
            elapsed = time.monotonic() - self._cache_loaded_at
            if elapsed < self._cache_ttl:
                return
        await self._force_refresh()

    async def _force_refresh(self) -> None:
        """Unconditionally re-read the KV bucket and rebuild the cache.

        Used by :meth:`create` for warm-up and by the KV-watch loop for
        invalidation.  Held under ``self._lock`` so a watch event firing
        concurrently with an explicit :meth:`refresh` doesn't race two
        ``list_all`` calls into a half-written cache.
        """
        async with self._lock:
            try:
                manifests = await self._registry.list_all()
            except Exception as exc:
                # Surface to caller — :meth:`create` wraps this as
                # NATSConnectionError; the watch loop logs and continues.
                logger.warning(
                    "capabilities_kv_read_failed",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
                raise
            self._cache = [_manifest_to_descriptor(m) for m in manifests]
            self._cache_loaded_at = time.monotonic()
            self._cache_warmed = True

    # ------------------------------------------------------------------
    # Subscribe / watch loop
    # ------------------------------------------------------------------

    async def subscribe_updates(self, callback: Callable[[], None]) -> None:
        """Attach *callback* to fire whenever a KV change lands.

        Idempotent: a second call (regardless of the supplied callback)
        does not open a second watcher and does not double-fire on the
        next change.  The first callback wins for the lifetime of the
        registry; replacing it requires :meth:`close` and a fresh
        :meth:`create`.

        Args:
            callback: Synchronous callable invoked once per KV change
                AFTER the cache has been refreshed.  Exceptions raised
                from the callback are caught and logged, never raised
                back into the watch loop.
        """
        if self._subscribed:
            # Idempotent: ignore subsequent subscribe calls.  Per the
            # spec a single registry supports a single watcher / single
            # callback for the duration of its lifetime.
            return
        self._subscribed = True
        self._callback = callback
        try:
            self._watcher = await _resolve_watcher(self._registry)
        except Exception as exc:
            # Failing to open the watcher is operator-relevant but must
            # not crash the supervisor — log loudly and revert the flag
            # so a subsequent retry can attempt to open again.
            logger.warning(
                "capabilities_watch_open_failed",
                error_class=type(exc).__name__,
                error=str(exc),
            )
            self._subscribed = False
            self._callback = None
            return
        self._watcher_task = asyncio.create_task(self._watch_loop(), name="capabilities_kv_watch")

    async def _watch_loop(self) -> None:
        """Consume KV updates, force-refresh the cache, fire the callback.

        The NATS KV watcher emits ``None`` as a "history-complete"
        sentinel after replaying any existing keys; we treat that as a
        no-op and continue.  Real updates trigger an unconditional cache
        refresh (bypassing TTL) followed by exactly one callback
        invocation per change.

        Cancellation is the normal shutdown path — :meth:`close` cancels
        this task and awaits it, so we re-raise CancelledError after
        cleanup propagates back to the awaiter.
        """
        assert self._watcher is not None
        try:
            async for update in self._watcher:
                if update is None:
                    # NATS KV emits None at history-complete.  Skip.
                    continue
                try:
                    await self._force_refresh()
                except Exception as exc:
                    # KV read failed during a watch event — log WARN and
                    # continue.  The callback still fires because the
                    # change landed in the bucket; the cache will catch
                    # up on the next successful refresh.
                    logger.warning(
                        "capabilities_refresh_after_watch_failed",
                        error_class=type(exc).__name__,
                        error=str(exc),
                    )
                cb = self._callback
                if cb is not None:
                    try:
                        cb()
                    except Exception:
                        # Never let a user callback crash the watch loop.
                        logger.exception("capabilities_subscribe_callback_failed")
        except asyncio.CancelledError:
            raise

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Detach the KV watcher and release internal handles.  Idempotent.

        Cancels the watch task (if running), awaits its cancellation,
        and asks the underlying watcher to stop.  Subsequent calls are
        silent no-ops so re-entrant lifecycle teardown can't double-stop
        a watcher.
        """
        if self._closed:
            return
        self._closed = True

        task = self._watcher_task
        self._watcher_task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                # Expected — we cancelled it above.
                pass
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "capabilities_watch_task_close_error",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )

        watcher = self._watcher
        self._watcher = None
        if watcher is not None:
            try:
                await watcher.stop()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "capabilities_watch_stop_error",
                    error_class=type(exc).__name__,
                    error=str(exc),
                )


# ---------------------------------------------------------------------------
# StubCapabilitiesRegistry
# ---------------------------------------------------------------------------


class StubCapabilitiesRegistry:
    """DDR-021 fallback that reads the Phase 2 stub YAML.

    Same Protocol surface as :class:`LiveCapabilitiesRegistry` so the
    supervisor wiring never branches on which one is in use; the only
    behavioural difference is :meth:`subscribe_updates` is a no-op
    (the YAML cannot change at runtime — operators edit the file and
    restart Jarvis).

    Loaded eagerly at construction so the first :meth:`snapshot` call
    returns the YAML content without any I/O.  :meth:`refresh` re-reads
    the file from disk for parity with the live path's signature.
    """

    __slots__ = ("_cache", "_closed", "_fallback_path")

    def __init__(self, fallback_path: Path) -> None:
        """Load *fallback_path* into the descriptor cache.

        Args:
            fallback_path: Filesystem path to the stub capabilities YAML
                document.  Typically ``config.stub_capabilities_path``.

        Raises:
            FileNotFoundError: If *fallback_path* does not exist on disk
                (delegated from :func:`load_stub_registry`).
            ValueError: If the YAML root is malformed.
            pydantic.ValidationError: If any entry fails
                :class:`CapabilityDescriptor` validation.
        """
        self._fallback_path = fallback_path
        self._cache: list[CapabilityDescriptor] = load_stub_registry(fallback_path)
        self._closed = False

    def snapshot(self) -> list[CapabilityDescriptor]:
        """Return a fresh ``list`` copy of the YAML-loaded descriptors."""
        return list(self._cache)

    async def refresh(self) -> None:
        """Re-read the YAML file, replacing the cached descriptor list.

        Sync-loaded for parity with the live path's async signature.
        Useful in tests that mutate the YAML between assertions.
        """
        self._cache = load_stub_registry(self._fallback_path)

    async def subscribe_updates(self, callback: Callable[[], None]) -> None:
        """No-op — the stub catalogue cannot change at runtime.

        Accepts the callback to satisfy the Protocol but never invokes
        it; operators who need fresh capabilities edit the YAML and
        restart Jarvis (DDR-021 fallback semantics).

        Args:
            callback: Ignored.  Accepted only for Protocol conformance.
        """
        # Intentionally a no-op — the stub source of truth is a static
        # YAML document.  Returning silently keeps the call site identical
        # across live + stub branches.
        del callback
        return None

    async def close(self) -> None:
        """Idempotent close — clears the in-memory cache reference.

        The stub holds no external handles, so close just marks the
        registry as closed for lifecycle parity with the live path.
        """
        if self._closed:
            return
        self._closed = True
