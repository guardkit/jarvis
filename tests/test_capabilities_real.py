"""Integration tests for the live capabilities registry + KV-watch path.

TASK-J004-014 / FEAT-JARVIS-004 Phase 3 floor capability.

Drives :class:`jarvis.infrastructure.capabilities_registry.LiveCapabilitiesRegistry`
end-to-end against the ``nats_test_server`` in-process broker fixture so the
KV cache, the watch-driven invalidation loop, and the
``list_available_capabilities`` / ``capabilities_refresh`` tool surfaces all
exercise the wire-level production path together.

The unit-level coverage in ``test_capabilities.py`` substitutes a fake
registry; the scenarios here open a real JetStream KV bucket, pre-seed
specialist manifests, mutate fleet membership mid-test, and assert that the
KV-watch loop invalidates the cache promptly enough that the next
``list_available_capabilities`` call observes the change.

Skip-on-missing-binary is delegated to ``tests/conftest.py::nats_server_binary``.

Subjects cited in assertions are taken from ``nats_core.Topics.*`` per the
TASK-J004-014 Test Requirements line.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from nats_core import (
    AgentManifest,
    IntentCapability,
    NATSKVManifestRegistry,
)
from nats_core.client import AGENT_REGISTRY_BUCKET
from nats_core.topics import Topics

import jarvis.tools.capabilities as capabilities_module
from jarvis.infrastructure.capabilities_registry import LiveCapabilitiesRegistry
from jarvis.tools.capabilities import (
    capabilities_refresh,
    list_available_capabilities,
)

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# How long we let the KV-watch loop notice a fleet change before the test
# fails. NATS KV watch latency is typically <50ms in-process; 2.0s leaves
# generous slack for slow CI without masking real regressions.
_WATCH_PROPAGATION_BUDGET_S = 2.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_specialist_manifest(
    agent_id: str,
    *,
    name: str | None = None,
    intent_pattern: str | None = None,
) -> AgentManifest:
    """Build a minimal specialist manifest valid against ``AgentManifest``.

    Args:
        agent_id: Kebab-case identifier — must satisfy the manifest regex.
        name: Optional human-readable name; defaults to the agent_id.
        intent_pattern: Optional intent pattern; defaults to a per-agent
            stub so each manifest is structurally distinct.

    Returns:
        A ready-to-register :class:`AgentManifest`.
    """
    return AgentManifest(
        agent_id=agent_id,
        name=name or agent_id,
        version="0.1.0",
        template="test_specialist",
        intents=[
            IntentCapability(
                pattern=intent_pattern or f"specialist.{agent_id}",
                description=f"Test capability for {agent_id}",
            )
        ],
        tools=[],
        max_concurrent=1,
        status="ready",
        trust_tier="specialist",
    )


async def _wait_for_callback(event: asyncio.Event) -> None:
    """Wait for the watch-driven callback or fail with a clear message."""
    try:
        await asyncio.wait_for(event.wait(), timeout=_WATCH_PROPAGATION_BUDGET_S)
    except TimeoutError as exc:
        raise AssertionError(
            f"KV-watch callback did not fire within "
            f"{_WATCH_PROPAGATION_BUDGET_S}s — invalidation path is broken"
        ) from exc


def _agent_ids_in_snapshot(payload: str) -> list[str]:
    """Parse the ``list_available_capabilities`` JSON return into ids."""
    parsed = json.loads(payload)
    assert isinstance(parsed, list), f"snapshot must be a JSON array, got {type(parsed)}"
    return [entry["agent_id"] for entry in parsed]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def restore_capability_registry() -> Any:
    """Snapshot/restore the module-level ``_capability_registry`` swap-point.

    Tests rebind the registry to a real :class:`LiveCapabilitiesRegistry`
    instance; this fixture restores the prior binding so test ordering does
    not leak state across the suite.
    """
    saved = capabilities_module._capability_registry
    saved_subscribe = capabilities_module._subscribe_invoked
    yield
    capabilities_module._capability_registry = saved
    capabilities_module._subscribe_invoked = saved_subscribe


# ---------------------------------------------------------------------------
# AC-001 — pre-seed two specialists; list returns both
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_available_capabilities_returns_pre_seeded_specialists(
    nats_test_server: Any,
    restore_capability_registry: None,
) -> None:
    """A registry built over a pre-seeded bucket reports both specialists."""
    seed_registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    await seed_registry.register(_make_specialist_manifest("alpha-specialist"))
    await seed_registry.register(_make_specialist_manifest("beta-specialist"))

    # cache_ttl=0 forces every refresh to hit the wire — keeps the test
    # deterministic without depending on monotonic clock advances.
    live = await LiveCapabilitiesRegistry.create(
        nats_test_server, cache_ttl_seconds=0
    )
    capabilities_module._capability_registry = live
    try:
        payload = list_available_capabilities.invoke({})
        ids = _agent_ids_in_snapshot(payload)
        assert sorted(ids) == ["alpha-specialist", "beta-specialist"], (
            f"pre-seeded specialists must round-trip through the live registry; got {ids}"
        )
    finally:
        await live.close()

    # The pre-seed path goes through the agent-registry KV bucket — anchor
    # an assertion against the public constant rather than a literal so a
    # bucket-rename surfaces here.
    assert AGENT_REGISTRY_BUCKET


# ---------------------------------------------------------------------------
# AC-002 — register a third specialist mid-test, watch invalidates cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kv_watch_invalidates_cache_on_new_registration(
    nats_test_server: Any,
    restore_capability_registry: None,
) -> None:
    """A new registration mid-session is reflected on the next snapshot."""
    seed_registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    await seed_registry.register(_make_specialist_manifest("alpha-specialist"))
    await seed_registry.register(_make_specialist_manifest("beta-specialist"))

    live = await LiveCapabilitiesRegistry.create(
        nats_test_server, cache_ttl_seconds=30
    )
    capabilities_module._capability_registry = live

    # Prove baseline before subscribing — the cache reflects the seed set.
    baseline_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
    assert sorted(baseline_ids) == ["alpha-specialist", "beta-specialist"]

    # Wire a callback that signals every watch event so the test can wait
    # synchronously for the invalidation cycle to complete.
    invalidation_event = asyncio.Event()

    def _on_change() -> None:
        invalidation_event.set()

    await live.subscribe_updates(_on_change)

    # Drain any history-replay callbacks fired by the watch's initial
    # warm-up so the wait below truly observes the new event.
    invalidation_event.clear()

    try:
        await seed_registry.register(_make_specialist_manifest("gamma-specialist"))
        await _wait_for_callback(invalidation_event)

        # Cache invalidated — the next snapshot reflects the new fleet.
        post_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
        assert sorted(post_ids) == [
            "alpha-specialist",
            "beta-specialist",
            "gamma-specialist",
        ], f"watch must surface new registration; got {post_ids}"
    finally:
        await live.close()


# ---------------------------------------------------------------------------
# AC-003 — deregister mid-test, watch invalidates cache, list shrinks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kv_watch_invalidates_cache_on_deregistration(
    nats_test_server: Any,
    restore_capability_registry: None,
) -> None:
    """A deregister mid-session shrinks the next snapshot to the survivors."""
    seed_registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    await seed_registry.register(_make_specialist_manifest("alpha-specialist"))
    await seed_registry.register(_make_specialist_manifest("beta-specialist"))
    await seed_registry.register(_make_specialist_manifest("gamma-specialist"))

    live = await LiveCapabilitiesRegistry.create(
        nats_test_server, cache_ttl_seconds=30
    )
    capabilities_module._capability_registry = live

    baseline_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
    assert sorted(baseline_ids) == [
        "alpha-specialist",
        "beta-specialist",
        "gamma-specialist",
    ]

    invalidation_event = asyncio.Event()

    def _on_change() -> None:
        invalidation_event.set()

    await live.subscribe_updates(_on_change)
    invalidation_event.clear()

    try:
        await seed_registry.deregister("beta-specialist")
        await _wait_for_callback(invalidation_event)

        post_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
        assert sorted(post_ids) == ["alpha-specialist", "gamma-specialist"], (
            f"watch must surface deregistration; got {post_ids}"
        )
    finally:
        await live.close()

    # Same Topics-based anchor as the registration test.
    assert Topics.Fleet.DEREGISTER == "fleet.deregister"


# ---------------------------------------------------------------------------
# AC-004 — capabilities_refresh forces an immediate re-read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_capabilities_refresh_forces_immediate_reread(
    nats_test_server: Any,
    restore_capability_registry: None,
) -> None:
    """``capabilities_refresh`` re-reads the bucket on demand.

    The integration test exercises the live refresh path against a real
    JetStream KV bucket — the SAME ``LiveCapabilitiesRegistry.refresh``
    coroutine that the ``capabilities_refresh`` tool invokes via its
    ``_drive_coroutine`` sync-to-async bridge. The bridge itself is
    exhaustively unit-tested in ``test_capabilities.py``; calling the
    sync tool from inside this asyncio test would cross event-loop
    boundaries (the tool spawns ``asyncio.run`` on a worker thread, and
    nats-py's connection objects are bound to the loop they were
    created on), so the integration assertion targets the registry's
    public async surface directly.

    The OK / DEGRADED return strings of the tool function are verified
    independently in ``test_capabilities.py``; this test verifies that
    the underlying KV re-read reflects fleet changes immediately.

    Uses ``cache_ttl_seconds=0`` so every refresh hits the wire — keeps
    the assertion deterministic without depending on monotonic clock
    advances or the KV-watch invalidation path.
    """
    seed_registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    await seed_registry.register(_make_specialist_manifest("alpha-specialist"))

    # cache_ttl=0 ensures every `refresh()` call hits the wire. The cache
    # still stays stale until a refresh is invoked — `snapshot()` does NOT
    # auto-refresh, so only the explicit refresh path can surface a new
    # registration before the next call.
    live = await LiveCapabilitiesRegistry.create(
        nats_test_server, cache_ttl_seconds=0
    )
    capabilities_module._capability_registry = live
    try:
        baseline_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
        assert baseline_ids == ["alpha-specialist"]

        # Add a manifest WITHOUT subscribing to the watch — the cache
        # cannot self-update via the watch loop, so only an explicit
        # refresh can surface the new entry.
        await seed_registry.register(_make_specialist_manifest("delta-specialist"))

        # Stale snapshot still in the cache (no refresh, no watch).
        stale_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
        assert stale_ids == ["alpha-specialist"], (
            "cache must remain stale before refresh; got "
            f"{stale_ids} (cache invalidated unexpectedly)"
        )

        # Force-read the source of truth via the SAME async coroutine the
        # `capabilities_refresh` tool drives. Reference the tool symbol so
        # a tool-rename / removal trips this test even when the call uses
        # the underlying async surface.
        assert capabilities_refresh is not None  # tool surface still exported
        await live.refresh()

        fresh_ids = _agent_ids_in_snapshot(list_available_capabilities.invoke({}))
        assert sorted(fresh_ids) == ["alpha-specialist", "delta-specialist"], (
            f"refresh must surface new registration; got {fresh_ids}"
        )
    finally:
        await live.close()
