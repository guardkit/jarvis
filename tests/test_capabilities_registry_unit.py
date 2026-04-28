"""Unit tests for :mod:`jarvis.infrastructure.capabilities_registry`.

Covers TASK-J004-009 acceptance criteria:

- AC-001: ``CapabilitiesRegistry`` Protocol declared with all four methods.
- AC-002: ``LiveCapabilitiesRegistry.create`` returns a usable instance;
  first ``snapshot()`` reflects a fresh KV read; subsequent reads inside
  ``cache_ttl_seconds`` return the cached list.
- AC-003: KV-watch callback invalidates the cache — next ``snapshot()``
  re-reads.
- AC-004: ``snapshot()`` returns a fresh ``list`` copy — mutating the
  result does not affect the cache.
- AC-005: ``subscribe_updates(callback)`` is idempotent — second call
  does not double-subscribe / double-fire.
- AC-006: ``close()`` is idempotent; detaches the watcher.
- AC-007: ``StubCapabilitiesRegistry(fallback_path)`` reads YAML and
  exposes the same Protocol surface; ``subscribe_updates`` is a no-op.
- AC-008: Missing ``client.js`` (JetStream) → ``LiveCapabilitiesRegistry.create``
  raises ``NATSConnectionError``.

Tests substitute the production NATS-backed registry with mock objects
following the project-conventional ``_resolve_registry`` monkeypatch
pattern from ``tests/test_fleet_registration.py``. KV-watch behaviour is
exercised through an injected async-iterator mock so the tests run
without an in-process NATS broker.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats_core import AgentManifest, IntentCapability, ToolCapability

from jarvis.infrastructure import capabilities_registry as cap_reg
from jarvis.infrastructure.capabilities_registry import (
    CapabilitiesRegistry,
    LiveCapabilitiesRegistry,
    StubCapabilitiesRegistry,
)
from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools.capabilities import CapabilityDescriptor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    agent_id: str = "architect-agent",
    *,
    name: str = "Architect",
    template: str = "specialist_agent",
    trust_tier: str = "specialist",
    tools: list[ToolCapability] | None = None,
) -> AgentManifest:
    """Build a minimally-valid AgentManifest for tests."""
    return AgentManifest(
        agent_id=agent_id,
        name=name,
        template=template,
        intents=[IntentCapability(pattern="conversational.gpa", description="x")],
        tools=tools or [],
        trust_tier=trust_tier,  # type: ignore[arg-type]
    )


class _AsyncIterStub:
    """Mimic a NATS KV watcher: async-iterable, with a ``stop`` coro.

    Yields whatever items are pushed via :meth:`push`. ``None`` represents
    the "history-complete" sentinel that the production code must skip.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._stopped = False
        self.stop_calls = 0

    def push(self, item: Any) -> None:
        self._queue.put_nowait(item)

    def __aiter__(self) -> AsyncIterator[Any]:
        return self

    async def __anext__(self) -> Any:
        if self._stopped:
            raise StopAsyncIteration
        return await self._queue.get()

    async def stop(self) -> None:
        self._stopped = True
        self.stop_calls += 1


@pytest.fixture()
def fake_registry() -> MagicMock:
    """A fake NATSKVManifestRegistry whose ``list_all`` returns canned data."""
    registry = MagicMock(name="FakeNATSKVManifestRegistry")
    registry.list_all = AsyncMock(return_value=[])
    registry._kv = MagicMock(name="FakeKV")
    return registry


@pytest.fixture()
def patch_resolve_registry(monkeypatch: pytest.MonkeyPatch, fake_registry: MagicMock) -> MagicMock:
    """Monkeypatch ``_resolve_registry`` to return *fake_registry*."""

    async def _fake_resolve(_client: Any) -> MagicMock:
        return fake_registry

    monkeypatch.setattr(cap_reg, "_resolve_registry", _fake_resolve)
    return fake_registry


@pytest.fixture()
def patch_resolve_watcher(
    monkeypatch: pytest.MonkeyPatch,
) -> _AsyncIterStub:
    """Monkeypatch ``_resolve_watcher`` to return an injectable async iter."""
    watcher = _AsyncIterStub()

    async def _fake_open_watcher(_registry: Any) -> _AsyncIterStub:
        return watcher

    monkeypatch.setattr(cap_reg, "_resolve_watcher", _fake_open_watcher)
    return watcher


@pytest.fixture()
def stub_yaml(tmp_path: Path) -> Path:
    """Write a minimal stub_capabilities.yaml under tmp_path."""
    path = tmp_path / "stub_capabilities.yaml"
    path.write_text(
        """version: "1.0"
capabilities:
  - agent_id: architect-agent
    role: Architect
    description: Designs systems and produces ADRs.
    capability_list:
      - tool_name: run_architecture_session
        description: Drive a full architecture session.
        risk_level: read_only
    cost_signal: "moderate"
    latency_signal: "minutes"
    last_heartbeat_at: null
    trust_tier: specialist
  - agent_id: product-owner-agent
    role: Product Owner
    description: Refines specs and prioritises work.
    capability_list:
      - tool_name: review_specification
        description: Review a feature spec.
        risk_level: read_only
    cost_signal: "low"
    latency_signal: "seconds"
    last_heartbeat_at: null
    trust_tier: specialist
""",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# AC-001 — Protocol shape
# ---------------------------------------------------------------------------


class TestAC001ProtocolShape:
    """``CapabilitiesRegistry`` Protocol exposes all four methods."""

    def test_protocol_has_required_methods(self) -> None:
        """Protocol declares snapshot/refresh/subscribe_updates/close."""
        for name in ("snapshot", "refresh", "subscribe_updates", "close"):
            assert hasattr(CapabilitiesRegistry, name), f"Protocol missing required method {name!r}"

    def test_live_implements_protocol(self, fake_registry: MagicMock) -> None:
        """LiveCapabilitiesRegistry satisfies the runtime-checkable Protocol."""
        live = LiveCapabilitiesRegistry(fake_registry)
        assert isinstance(live, CapabilitiesRegistry)

    def test_stub_implements_protocol(self, stub_yaml: Path) -> None:
        """StubCapabilitiesRegistry satisfies the runtime-checkable Protocol."""
        stub = StubCapabilitiesRegistry(stub_yaml)
        assert isinstance(stub, CapabilitiesRegistry)


# ---------------------------------------------------------------------------
# AC-002 — create() warms cache; refresh respects TTL
# ---------------------------------------------------------------------------


class TestAC002CacheTTL:
    """First snapshot reflects a fresh read; refresh inside TTL is a no-op."""

    async def test_create_warms_cache_with_first_kv_read(
        self, patch_resolve_registry: MagicMock
    ) -> None:
        """``create()`` performs the initial KV fetch so the first snapshot is fresh."""
        manifest = _make_manifest("architect-agent")
        patch_resolve_registry.list_all.return_value = [manifest]

        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)

        snapshot = live.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0].agent_id == "architect-agent"
        # Exactly one KV read so far — the warm-up done by create().
        assert patch_resolve_registry.list_all.await_count == 1

    async def test_refresh_within_ttl_does_not_reread_kv(
        self, patch_resolve_registry: MagicMock
    ) -> None:
        """A refresh() call inside cache_ttl_seconds returns cached data."""
        manifest = _make_manifest("architect-agent")
        patch_resolve_registry.list_all.return_value = [manifest]

        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)
        first_count = patch_resolve_registry.list_all.await_count

        # Call refresh repeatedly inside the 30s window — no new KV reads.
        for _ in range(3):
            await live.refresh()

        assert patch_resolve_registry.list_all.await_count == first_count

    async def test_refresh_with_zero_ttl_always_rereads(
        self, patch_resolve_registry: MagicMock
    ) -> None:
        """cache_ttl_seconds=0 disables caching — every refresh re-reads."""
        patch_resolve_registry.list_all.return_value = [_make_manifest("a-agent")]

        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=0)
        baseline = patch_resolve_registry.list_all.await_count

        await live.refresh()
        await live.refresh()

        assert patch_resolve_registry.list_all.await_count == baseline + 2


# ---------------------------------------------------------------------------
# AC-003 — KV-watch invalidation
# ---------------------------------------------------------------------------


class TestAC003KVWatchInvalidation:
    """KV-watch callback invalidates cache — next snapshot re-reads."""

    async def test_kv_watch_event_triggers_refresh(
        self,
        patch_resolve_registry: MagicMock,
        patch_resolve_watcher: _AsyncIterStub,
    ) -> None:
        """A KV change event causes cache to refresh and snapshot to update."""
        # Cache TTL=30 so the only thing that can invalidate is a watch event.
        patch_resolve_registry.list_all.return_value = [_make_manifest("a-agent")]

        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)

        callback_fires: list[None] = []

        def _on_change() -> None:
            callback_fires.append(None)

        await live.subscribe_updates(_on_change)

        # Now flip the KV side: list_all returns a new manifest set.
        patch_resolve_registry.list_all.return_value = [
            _make_manifest("a-agent"),
            _make_manifest("b-agent"),
        ]

        # Push a KV change event into the watcher.
        patch_resolve_watcher.push(MagicMock(name="KvUpdate"))

        # Allow the watch loop to process the event and re-fetch.
        await _wait_until(lambda: len(live.snapshot()) == 2, timeout=2.0)
        await _wait_until(lambda: len(callback_fires) == 1, timeout=2.0)

        snapshot = live.snapshot()
        assert {d.agent_id for d in snapshot} == {"a-agent", "b-agent"}
        assert len(callback_fires) == 1
        await live.close()

    async def test_history_complete_sentinel_is_skipped(
        self,
        patch_resolve_registry: MagicMock,
        patch_resolve_watcher: _AsyncIterStub,
    ) -> None:
        """``None`` from the watcher (history-complete sentinel) is ignored."""
        patch_resolve_registry.list_all.return_value = [_make_manifest("a-agent")]
        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)
        baseline = patch_resolve_registry.list_all.await_count

        callback_fires: list[None] = []
        await live.subscribe_updates(lambda: callback_fires.append(None))

        patch_resolve_watcher.push(None)  # sentinel
        # Give the watcher loop a chance to consume the sentinel.
        await asyncio.sleep(0.05)

        # No additional KV read; no callback fired.
        assert patch_resolve_registry.list_all.await_count == baseline
        assert callback_fires == []
        await live.close()


# ---------------------------------------------------------------------------
# AC-004 — Snapshot isolation
# ---------------------------------------------------------------------------


class TestAC004SnapshotIsolation:
    """Mutating the snapshot does not affect the cached registry."""

    async def test_snapshot_returns_fresh_list_copy(
        self, patch_resolve_registry: MagicMock
    ) -> None:
        """Mutating the returned list (clear/append) doesn't poison the cache."""
        patch_resolve_registry.list_all.return_value = [
            _make_manifest("a-agent"),
            _make_manifest("b-agent"),
        ]
        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)

        snapshot_a = live.snapshot()
        snapshot_a.clear()
        snapshot_a.append(_FAKE_DESCRIPTOR)

        snapshot_b = live.snapshot()

        assert len(snapshot_b) == 2
        assert {d.agent_id for d in snapshot_b} == {"a-agent", "b-agent"}
        # And the two snapshots are not the same list object.
        assert snapshot_a is not snapshot_b


_FAKE_DESCRIPTOR = CapabilityDescriptor(
    agent_id="poisoned",
    role="Poisoned",
    description="should never be in the registry",
)


# ---------------------------------------------------------------------------
# AC-005 — subscribe_updates idempotency
# ---------------------------------------------------------------------------


class TestAC005SubscribeIdempotent:
    """Calling subscribe_updates more than once does not double-subscribe."""

    async def test_second_subscribe_call_is_noop(
        self,
        patch_resolve_registry: MagicMock,
        patch_resolve_watcher: _AsyncIterStub,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Second subscribe call does not open a second watcher or fire twice."""
        patch_resolve_registry.list_all.return_value = [_make_manifest("a-agent")]

        # Wrap the patched watcher resolver so we can count invocations.
        open_calls: list[None] = []
        original_resolve = cap_reg._resolve_watcher

        async def _counting_resolve(reg: Any) -> Any:
            open_calls.append(None)
            return await original_resolve(reg)

        monkeypatch.setattr(cap_reg, "_resolve_watcher", _counting_resolve)

        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)

        callback_fires: list[None] = []

        def _on_change() -> None:
            callback_fires.append(None)

        await live.subscribe_updates(_on_change)
        await live.subscribe_updates(_on_change)  # second call: no-op

        assert len(open_calls) == 1, "watcher opened more than once"

        # Push one KV event — callback must fire EXACTLY once, not twice.
        patch_resolve_registry.list_all.return_value = [
            _make_manifest("a-agent"),
            _make_manifest("b-agent"),
        ]
        patch_resolve_watcher.push(MagicMock())

        await _wait_until(lambda: len(callback_fires) == 1, timeout=2.0)
        # Wait a little longer to confirm no double-fire.
        await asyncio.sleep(0.05)
        assert len(callback_fires) == 1, "callback fired more than once per change"
        await live.close()


# ---------------------------------------------------------------------------
# AC-006 — close idempotency
# ---------------------------------------------------------------------------


class TestAC006CloseIdempotent:
    """close() is idempotent and detaches the watcher."""

    async def test_close_cancels_watcher_task(
        self,
        patch_resolve_registry: MagicMock,
        patch_resolve_watcher: _AsyncIterStub,
    ) -> None:
        """close() stops the watcher async iterator."""
        patch_resolve_registry.list_all.return_value = [_make_manifest("a-agent")]
        live = await LiveCapabilitiesRegistry.create(client=MagicMock(), cache_ttl_seconds=30)
        await live.subscribe_updates(lambda: None)

        await live.close()

        # The watcher's stop() must have been invoked at least once.
        assert patch_resolve_watcher.stop_calls >= 1

    async def test_close_is_idempotent(
        self,
        patch_resolve_registry: MagicMock,
        patch_resolve_watcher: _AsyncIterStub,
    ) -> None:
        """Calling close() multiple times does not raise."""
        patch_resolve_registry.list_all.return_value = []
        live = await LiveCapabilitiesRegistry.create(client=MagicMock())
        await live.subscribe_updates(lambda: None)

        await live.close()
        await live.close()  # second call: no-op
        await live.close()  # third call: still no-op

    async def test_close_without_subscribe_is_safe(self, patch_resolve_registry: MagicMock) -> None:
        """close() before any subscribe is a clean no-op (no watcher to detach)."""
        patch_resolve_registry.list_all.return_value = []
        live = await LiveCapabilitiesRegistry.create(client=MagicMock())
        await live.close()


# ---------------------------------------------------------------------------
# AC-007 — Stub fallback reads YAML
# ---------------------------------------------------------------------------


class TestAC007StubFallback:
    """StubCapabilitiesRegistry returns the YAML-loaded descriptor list."""

    def test_snapshot_returns_yaml_descriptors(self, stub_yaml: Path) -> None:
        """Snapshot mirrors the YAML's ``capabilities`` list, in order."""
        stub = StubCapabilitiesRegistry(stub_yaml)

        snapshot = stub.snapshot()

        agent_ids = [d.agent_id for d in snapshot]
        assert agent_ids == ["architect-agent", "product-owner-agent"]

    def test_snapshot_returns_fresh_copy(self, stub_yaml: Path) -> None:
        """Mutating the stub snapshot doesn't poison the cache."""
        stub = StubCapabilitiesRegistry(stub_yaml)

        snapshot_a = stub.snapshot()
        snapshot_a.clear()

        snapshot_b = stub.snapshot()
        assert len(snapshot_b) == 2

    async def test_subscribe_updates_is_noop(self, stub_yaml: Path) -> None:
        """Stub subscribe_updates accepts a callback but never fires."""
        stub = StubCapabilitiesRegistry(stub_yaml)
        fires: list[None] = []

        await stub.subscribe_updates(lambda: fires.append(None))
        await asyncio.sleep(0.05)

        assert fires == []

    async def test_refresh_rereads_yaml(self, stub_yaml: Path) -> None:
        """Stub refresh() re-reads the YAML file from disk."""
        stub = StubCapabilitiesRegistry(stub_yaml)
        original = stub.snapshot()
        assert len(original) == 2

        # Rewrite the file with a single capability.
        stub_yaml.write_text(
            """version: "1.0"
capabilities:
  - agent_id: forge
    role: Forge
    description: Build new features end-to-end.
    capability_list:
      - tool_name: build_feature
        description: Build a feature.
        risk_level: mutating
    cost_signal: "high"
    latency_signal: "hours"
    last_heartbeat_at: null
    trust_tier: core
""",
            encoding="utf-8",
        )

        await stub.refresh()
        refreshed = stub.snapshot()
        assert [d.agent_id for d in refreshed] == ["forge"]

    async def test_close_is_idempotent(self, stub_yaml: Path) -> None:
        """Stub close() is a clean no-op, idempotent."""
        stub = StubCapabilitiesRegistry(stub_yaml)
        await stub.close()
        await stub.close()


# ---------------------------------------------------------------------------
# AC-008 — JetStream-unavailable raises NATSConnectionError
# ---------------------------------------------------------------------------


class TestAC008JetStreamUnavailableRaises:
    """If JetStream cannot be acquired, ``create()`` raises NATSConnectionError."""

    async def test_create_wraps_resolve_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Any exception from ``_resolve_registry`` becomes NATSConnectionError."""

        async def _exploding_resolve(_client: Any) -> Any:
            raise RuntimeError("jetstream unavailable")

        monkeypatch.setattr(cap_reg, "_resolve_registry", _exploding_resolve)

        with pytest.raises(NATSConnectionError):
            await LiveCapabilitiesRegistry.create(client=MagicMock())

    async def test_create_chains_original_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The original failure is preserved as ``__cause__`` for diagnostics."""

        async def _exploding_resolve(_client: Any) -> Any:
            raise AttributeError("no jetstream() on this client")

        monkeypatch.setattr(cap_reg, "_resolve_registry", _exploding_resolve)

        with pytest.raises(NATSConnectionError) as exc_info:
            await LiveCapabilitiesRegistry.create(client=MagicMock())

        assert isinstance(exc_info.value.__cause__, AttributeError)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _wait_until(predicate: Any, *, timeout: float = 1.0) -> None:
    """Poll *predicate* until True or timeout — minimal async wait helper."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Timeout: predicate did not become true within {timeout}s")
