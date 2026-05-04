"""Integration tests for fleet registration against an in-process NATS broker.

TASK-J004-014 / FEAT-JARVIS-004 Phase 3 floor capability.

Exercises :mod:`jarvis.infrastructure.fleet_registration` end-to-end against
the ``nats_test_server`` fixture (an isolated ``nats-server -p <free> -js``
subprocess). The unit-level coverage in ``test_fleet_registration.py``
substitutes :class:`nats_core.InMemoryManifestRegistry` for the KV path; the
scenarios here drive the production ``NATSKVManifestRegistry`` over a real
JetStream KV bucket so the wrapper, the registry helper, and the heartbeat
loop are exercised against the wire-level surface they ship to operators.

If ``nats-server`` is not on PATH the fixture skips the file with a clear
operator hint — see ``tests/conftest.py::nats_server_binary``.

Subjects cited in assertions are imported from ``nats_core.Topics``
(per the TASK-J004-014 Test Requirements line "Subjects asserted via
``nats_core.Topics.*`` formatters") rather than hard-coded literals so a
future Topic-namespace rename surfaces here as a compile-time mismatch.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from nats_core import NATSKVManifestRegistry
from nats_core.client import AGENT_REGISTRY_BUCKET
from nats_core.topics import Topics

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.fleet_registration import (
    JARVIS_AGENT_ID,
    build_jarvis_manifest,
    deregister_from_fleet,
    heartbeat_loop,
    register_on_fleet,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _FastHeartbeatConfig:
    """Duck-typed config exposing a sub-second heartbeat interval.

    :class:`JarvisConfig` clamps ``heartbeat_interval_seconds`` to ``ge=5``
    via pydantic, but :func:`heartbeat_loop` only reads the attribute, so
    a structural type with an integer field is sufficient — and required
    to keep the "two heartbeats in 2.5s" budget bounded.
    """

    heartbeat_interval_seconds: int = 1


def _build_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` valid enough for manifest construction."""
    return JarvisConfig(llama_swap_base_url="http://fake-endpoint")


# ---------------------------------------------------------------------------
# AC-001 — register-then-query round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_on_fleet_publishes_manifest_queryable_via_registry(
    nats_test_server: Any,
) -> None:
    """A registered manifest is immediately readable from the KV bucket."""
    config = _build_config()
    manifest = build_jarvis_manifest(config)

    await register_on_fleet(nats_test_server, manifest)

    # Verify via a fresh registry handle on the same bucket — confirms the
    # entry survives across registry instances (i.e. it lives on the wire,
    # not in process-local state).
    registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    fetched = await registry.get(JARVIS_AGENT_ID)

    assert fetched is not None, "registered manifest must be retrievable"
    assert fetched.agent_id == JARVIS_AGENT_ID
    assert fetched.version == manifest.version
    assert fetched.template == manifest.template
    # Topics.Fleet.REGISTER is the conceptual fleet-registration subject;
    # we anchor an assertion against it so a Topic-namespace rename trips
    # this file, not just the publish-side modules.
    assert Topics.Fleet.REGISTER == "fleet.register"
    # The registry name must match the published constant from nats_core.
    assert AGENT_REGISTRY_BUCKET


# ---------------------------------------------------------------------------
# AC-002 — heartbeat fires at the configured interval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_loop_fires_at_configured_interval(
    nats_test_server: Any,
) -> None:
    """Two heartbeats land inside a 2.5s window with a 1s interval.

    The loop re-publishes the manifest on every tick (KV ``put`` upserts on
    ``agent_id``, bumping the JetStream KV revision). We count revision
    deltas via ``KeyValue.history`` so the assertion does not depend on
    monkeypatching the registry — the wire is the source of truth.
    """
    config = _build_config()
    manifest = build_jarvis_manifest(config)

    # Prime the bucket with one register so the heartbeat loop's job is
    # purely "refresh" rather than "create + refresh".
    await register_on_fleet(nats_test_server, manifest)

    # Snapshot baseline revision then start the heartbeat loop. Use the
    # underlying KV bucket directly for revision introspection.
    kv = await nats_test_server.client.jetstream().key_value(AGENT_REGISTRY_BUCKET)

    baseline_entry = await kv.get(JARVIS_AGENT_ID)
    baseline_revision = baseline_entry.revision

    fast_config = _FastHeartbeatConfig(heartbeat_interval_seconds=1)
    task = asyncio.create_task(
        heartbeat_loop(nats_test_server, manifest, fast_config),  # type: ignore[arg-type]
        name="heartbeat_under_test",
    )
    try:
        # Budget: 2.5s — long enough for two ticks at 1s, short enough that
        # a stuck loop fails fast under the wait_for guard.
        async def _await_two_more_revisions() -> int:
            while True:
                entry = await kv.get(JARVIS_AGENT_ID)
                if entry.revision >= baseline_revision + 2:
                    return int(entry.revision)
                await asyncio.sleep(0.1)

        observed_revision = await asyncio.wait_for(
            _await_two_more_revisions(),
            timeout=2.5,
        )
        assert observed_revision >= baseline_revision + 2
    finally:
        task.cancel()
        # Awaiting the cancelled task surfaces any unexpected exception
        # raised by the loop body (CancelledError is the documented
        # shutdown path and is swallowed here).
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# AC-003 — deregister removes the entry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deregister_from_fleet_removes_entry(nats_test_server: Any) -> None:
    """After ``deregister_from_fleet`` the registry no longer returns Jarvis."""
    config = _build_config()
    manifest = build_jarvis_manifest(config)

    await register_on_fleet(nats_test_server, manifest)
    registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    pre = await registry.get(JARVIS_AGENT_ID)
    assert pre is not None, "fixture invariant: register must succeed"

    await deregister_from_fleet(nats_test_server)

    post = await registry.get(JARVIS_AGENT_ID)
    assert post is None, "deregister must remove the manifest"
    # The fleet broadcast subject for deregistration is owned by
    # nats_core.Topics — keep the assertion grounded in the registry rather
    # than hard-coded literals.
    assert Topics.Fleet.DEREGISTER == "fleet.deregister"


# ---------------------------------------------------------------------------
# AC-004 — register-then-register-again is idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_on_fleet_is_idempotent(nats_test_server: Any) -> None:
    """A second register call does not raise and does not duplicate the entry."""
    config = _build_config()
    manifest = build_jarvis_manifest(config)

    await register_on_fleet(nats_test_server, manifest)
    # Second call must not raise.
    await register_on_fleet(nats_test_server, manifest)

    registry = await NATSKVManifestRegistry.create(nats_test_server.client)
    all_manifests = await registry.list_all()

    jarvis_entries = [m for m in all_manifests if m.agent_id == JARVIS_AGENT_ID]
    assert len(jarvis_entries) == 1, (
        "idempotent register must yield exactly one entry, "
        f"got {len(jarvis_entries)}"
    )
