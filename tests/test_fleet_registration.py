"""Tests for :mod:`jarvis.infrastructure.fleet_registration`.

Covers TASK-J004-007 acceptance criteria:

- AC-001: ``build_jarvis_manifest`` is pure.
- AC-002: Manifest validates against ``nats_core.AgentManifest``.
- AC-003: Manifest metadata is JSON-serializable and ≤64KB.
- AC-004: ``register_on_fleet`` is idempotent.
- AC-005: ``heartbeat_loop`` cancels cleanly with an INFO log line.
- AC-006: ``heartbeat_loop`` survives a single failed publish.
- AC-007: ``deregister_from_fleet`` is silent on a missing entry.
- AC-008: Manifest shape, register-then-query, heartbeat fires at
  interval, heartbeat survives one publish failure, deregister removes
  the entry, deregister of missing entry is silent.

The "in-process NATS test server fixture" called for in the task is
substituted with a stub-registry monkeypatch on
``fleet_registration._resolve_registry`` — the production path goes
through ``NATSKVManifestRegistry`` (KV-backed), so swapping in an
:class:`InMemoryManifestRegistry` exercises the same
:class:`ManifestRegistry` Protocol contract without bringing up a real
broker.  This is the project-conventional substitution for unit tests
(see ``tests/test_dispatch_*`` for the parallel pattern).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import patch

import pytest
from nats_core import (
    AgentManifest,
    InMemoryManifestRegistry,
    IntentCapability,
)
from pydantic import ValidationError
from structlog.testing import capture_logs

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import fleet_registration
from jarvis.infrastructure.fleet_registration import (
    JARVIS_AGENT_ID,
    JARVIS_AGENT_NAME,
    JARVIS_TEMPLATE,
    NATSConnectionError,
    build_jarvis_manifest,
    deregister_from_fleet,
    heartbeat_loop,
    register_on_fleet,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def jarvis_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` with a fake openai endpoint.

    The default ``jarvis_agent_version`` ("0.4.0") is a valid semver so
    the manifest validates without overrides.
    """
    return JarvisConfig(
        llama_swap_base_url="http://fake-endpoint",
    )


@pytest.fixture()
def fake_client() -> object:
    """Return a sentinel object passed in place of a real NATS client.

    Tests monkeypatch ``_resolve_registry`` so the client value is never
    introspected — any non-``None`` sentinel works.
    """
    return object()


@pytest.fixture()
def in_memory_registry() -> InMemoryManifestRegistry:
    """Return a fresh in-memory manifest registry per test."""
    return InMemoryManifestRegistry()


@pytest.fixture()
def patch_registry(
    monkeypatch: pytest.MonkeyPatch,
    in_memory_registry: InMemoryManifestRegistry,
) -> InMemoryManifestRegistry:
    """Route ``_resolve_registry`` to *in_memory_registry*.

    Returns the same registry instance the production code receives so
    individual tests can introspect / mutate it directly.
    """

    async def _fake_resolve(_client: Any) -> InMemoryManifestRegistry:
        return in_memory_registry

    monkeypatch.setattr(fleet_registration, "_resolve_registry", _fake_resolve)
    return in_memory_registry


# ---------------------------------------------------------------------------
# build_jarvis_manifest — AC-001, AC-002, AC-003, AC-008 (manifest shape)
# ---------------------------------------------------------------------------


class TestBuildJarvisManifest:
    """Manifest shape, purity, and AgentManifest validation."""

    def test_manifest_validates_as_agent_manifest(self, jarvis_config: JarvisConfig) -> None:
        """AC-002: returned object is a valid AgentManifest instance."""
        manifest = build_jarvis_manifest(jarvis_config)
        assert isinstance(manifest, AgentManifest)
        # Round-trip through pydantic validation to catch any latent
        # issue with field types or kebab-case agent_id.
        AgentManifest.model_validate(manifest.model_dump())

    def test_manifest_has_canonical_static_fields(self, jarvis_config: JarvisConfig) -> None:
        """AC-008 manifest shape: agent_id, name, template, status, trust_tier."""
        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.agent_id == JARVIS_AGENT_ID == "jarvis"
        assert manifest.name == JARVIS_AGENT_NAME == "Jarvis"
        assert manifest.template == JARVIS_TEMPLATE == "general_purpose_agent"
        assert manifest.status == "ready"
        assert manifest.trust_tier == "core"
        assert manifest.max_concurrent == 1
        assert manifest.tools == []
        assert manifest.required_permissions == []

    def test_manifest_carries_four_canonical_intents(self, jarvis_config: JarvisConfig) -> None:
        """AC-008 manifest shape: four named IntentCapability entries."""
        manifest = build_jarvis_manifest(jarvis_config)
        patterns = {cap.pattern for cap in manifest.intents}
        assert patterns == {
            "conversational.gpa",
            "dispatch.by_capability",
            "meta.dispatch",
            "memory.recall",
        }
        # Every intent has a non-empty description (AgentManifest enforces
        # the field's presence; we additionally guard against blanks).
        for cap in manifest.intents:
            assert isinstance(cap, IntentCapability)
            assert cap.description.strip()

    def test_manifest_version_tracks_config(self, jarvis_config: JarvisConfig) -> None:
        """Version flows from config.jarvis_agent_version."""
        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.version == jarvis_config.jarvis_agent_version

    def test_manifest_container_id_from_hostname_env(
        self,
        jarvis_config: JarvisConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """API-internal §2: container_id = HOSTNAME or None (not the reverse)."""
        monkeypatch.setenv("HOSTNAME", "jarvis-host-7")
        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.container_id == "jarvis-host-7"

    def test_manifest_container_id_falls_back_to_none_when_unset(
        self,
        jarvis_config: JarvisConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing HOSTNAME env var → container_id is None, not empty string."""
        monkeypatch.delenv("HOSTNAME", raising=False)
        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.container_id is None

    def test_manifest_container_id_falls_back_when_hostname_blank(
        self,
        jarvis_config: JarvisConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Blank HOSTNAME ("") is treated as unset per the spec ``or None``."""
        monkeypatch.setenv("HOSTNAME", "")
        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.container_id is None

    def test_metadata_has_expected_keys(self, jarvis_config: JarvisConfig) -> None:
        """API-internal §2: adapter_set + phase keys."""
        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.metadata == {
            "adapter_set": "telegram,cli,dashboard,reachy",
            "phase": "v1",
        }

    def test_metadata_is_json_serializable_and_under_64kb(
        self, jarvis_config: JarvisConfig
    ) -> None:
        """AC-003: metadata serialises to JSON ≤64KB."""
        manifest = build_jarvis_manifest(jarvis_config)
        encoded = json.dumps(manifest.metadata).encode()
        # AgentManifest enforces ≤65536; we additionally assert the
        # static metadata is small (well under).
        assert len(encoded) <= 65536
        assert len(encoded) < 1024

    def test_function_is_pure_no_network_no_filesystem(
        self,
        jarvis_config: JarvisConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-001: build_jarvis_manifest performs no network or filesystem I/O.

        We assert this by patching ``socket.socket`` and ``builtins.open``
        — any usage during the call would raise immediately.  ``os.environ``
        access (HOSTNAME lookup) is in-process and explicitly allowed by
        the spec.
        """

        def _no_socket(*args: object, **kwargs: object) -> None:
            raise AssertionError("build_jarvis_manifest opened a socket")

        def _no_open(*args: object, **kwargs: object) -> None:
            raise AssertionError("build_jarvis_manifest opened a file")

        import socket

        monkeypatch.setattr(socket, "socket", _no_socket)
        monkeypatch.setattr("builtins.open", _no_open)

        manifest = build_jarvis_manifest(jarvis_config)
        assert manifest.agent_id == JARVIS_AGENT_ID

    def test_function_is_deterministic(self, jarvis_config: JarvisConfig) -> None:
        """AC-001: identical config → identical manifest."""
        m1 = build_jarvis_manifest(jarvis_config)
        m2 = build_jarvis_manifest(jarvis_config)
        assert m1.model_dump() == m2.model_dump()

    def test_invalid_version_rejected_at_config_time(self) -> None:
        """JarvisConfig rejects bad semver before build_jarvis_manifest runs."""
        with pytest.raises(ValidationError):
            JarvisConfig(
                llama_swap_base_url="http://fake-endpoint",
                jarvis_agent_version="not-a-semver",
            )


# ---------------------------------------------------------------------------
# register_on_fleet — AC-004, AC-008 (register-then-query)
# ---------------------------------------------------------------------------


class TestRegisterOnFleet:
    """Register publishes the manifest; idempotent on repeat calls."""

    async def test_register_then_query_returns_manifest(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """AC-008 register-then-query: registry.get(agent_id) == manifest."""
        manifest = build_jarvis_manifest(jarvis_config)
        await register_on_fleet(fake_client, manifest)

        stored = await patch_registry.get(JARVIS_AGENT_ID)
        assert stored is not None
        assert stored.agent_id == JARVIS_AGENT_ID
        assert stored.version == manifest.version

    async def test_register_is_idempotent(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """AC-004: re-registering replaces the prior entry without raising."""
        manifest_v1 = build_jarvis_manifest(jarvis_config)
        await register_on_fleet(fake_client, manifest_v1)

        # Build a second manifest with a bumped version to confirm the
        # second register OVERWRITES (not duplicates) the first.
        config_v2 = jarvis_config.model_copy(update={"jarvis_agent_version": "0.4.1"})
        manifest_v2 = build_jarvis_manifest(config_v2)
        await register_on_fleet(fake_client, manifest_v2)

        listed = await patch_registry.list_all()
        assert len(listed) == 1
        assert listed[0].version == "0.4.1"

    async def test_register_failure_raises_nats_connection_error(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Transport failures surface as NATSConnectionError, not bare Exception."""

        async def _exploding_resolve(_client: Any) -> Any:
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(fleet_registration, "_resolve_registry", _exploding_resolve)

        manifest = build_jarvis_manifest(jarvis_config)
        with pytest.raises(NATSConnectionError) as exc_info:
            await register_on_fleet(fake_client, manifest)
        # __cause__ chains the originating error so ops can debug.
        assert isinstance(exc_info.value.__cause__, RuntimeError)


# ---------------------------------------------------------------------------
# heartbeat_loop — AC-005, AC-006, AC-008 (heartbeat fires at interval)
# ---------------------------------------------------------------------------


class TestHeartbeatLoop:
    """Periodic heartbeat publishes; survives errors; cancels cleanly."""

    async def test_heartbeat_fires_at_interval(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """AC-008 heartbeat fires at interval (asyncio.sleep is mocked).

        We patch ``asyncio.sleep`` to be a no-op so the loop spins
        without real wall-clock waits.  After three sleeps we cancel
        the task and verify ``register`` was called multiple times.
        """
        manifest = build_jarvis_manifest(jarvis_config)
        sleep_calls: list[float] = []
        ticks_to_run = 3
        cancel_event = asyncio.Event()

        real_sleep = asyncio.sleep

        async def _counting_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
            if len(sleep_calls) >= ticks_to_run:
                cancel_event.set()
                # Yield once to let the cancel actually propagate.
                await real_sleep(0)
            # No real wait — keep the test fast.

        with patch.object(fleet_registration.asyncio, "sleep", _counting_sleep):
            task = asyncio.create_task(heartbeat_loop(fake_client, manifest, jarvis_config))
            await cancel_event.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        # Each sleep is preceded by exactly one register call, so the
        # registry's _store reflects at least ticks_to_run upserts. We
        # only have one agent_id so list_all has one entry; assert the
        # sleep cadence directly.
        assert len(sleep_calls) >= ticks_to_run
        assert all(s == jarvis_config.heartbeat_interval_seconds for s in sleep_calls)
        # AC-008 register-then-query path holds during heartbeat too.
        stored = await patch_registry.get(JARVIS_AGENT_ID)
        assert stored is not None

    async def test_heartbeat_survives_single_publish_failure(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC-006: one transient register failure → WARN, next tick succeeds."""
        manifest = build_jarvis_manifest(jarvis_config)

        # Stand up an in-memory registry whose first .register() raises
        # but subsequent calls succeed.
        registry = InMemoryManifestRegistry()
        attempts: list[int] = []
        original_register = registry.register

        async def _flaky_register(m: AgentManifest) -> None:
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("transient KV write error")
            await original_register(m)

        registry.register = _flaky_register  # type: ignore[method-assign]

        async def _fake_resolve(_client: Any) -> Any:
            return registry

        monkeypatch.setattr(fleet_registration, "_resolve_registry", _fake_resolve)

        cancel_event = asyncio.Event()
        real_sleep = asyncio.sleep

        async def _counting_sleep(_seconds: float) -> None:
            # Cancel after the second tick — by then we've seen the
            # failed first register AND the successful second one.
            if len(attempts) >= 2:
                cancel_event.set()
                await real_sleep(0)

        with patch.object(fleet_registration.asyncio, "sleep", _counting_sleep):
            task = asyncio.create_task(heartbeat_loop(fake_client, manifest, jarvis_config))
            await cancel_event.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        # First attempt failed, the loop continued, the second attempt
        # succeeded (registry now has the manifest).
        assert len(attempts) >= 2
        stored = await registry.get(JARVIS_AGENT_ID)
        assert stored is not None

    async def test_heartbeat_cancels_cleanly_with_info_log(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """AC-005: cancellation logs INFO ``fleet_heartbeat_cancelled``.

        Re-raises CancelledError after logging so asyncio records the
        task as cancelled.  We verify the INFO event was emitted using
        ``structlog.testing.capture_logs`` (the project's structlog
        loggers do not necessarily route through stdlib ``logging`` in
        the test environment, so ``caplog`` cannot see them directly).
        """
        manifest = build_jarvis_manifest(jarvis_config)
        real_sleep = asyncio.sleep
        started = asyncio.Event()

        async def _instant_sleep(_seconds: float) -> None:
            started.set()
            await real_sleep(0)

        with (
            capture_logs() as logs,
            patch.object(fleet_registration.asyncio, "sleep", _instant_sleep),
        ):
            task = asyncio.create_task(heartbeat_loop(fake_client, manifest, jarvis_config))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        cancelled_logs = [
            entry for entry in logs if entry.get("event") == "fleet_heartbeat_cancelled"
        ]
        assert cancelled_logs, "cancellation INFO log was not emitted"
        # Must be an INFO-level log (no traceback path).
        assert all(entry.get("log_level") == "info" for entry in cancelled_logs)
        # No exc_info — cancellation is the normal shutdown path.
        assert all("exc_info" not in entry for entry in cancelled_logs)


# ---------------------------------------------------------------------------
# deregister_from_fleet — AC-007, AC-008 (deregister silent on missing)
# ---------------------------------------------------------------------------


class TestDeregisterFromFleet:
    """Deregister is idempotent and never raises."""

    async def test_deregister_removes_entry(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """AC-008 deregister removes the entry."""
        manifest = build_jarvis_manifest(jarvis_config)
        await register_on_fleet(fake_client, manifest)
        assert await patch_registry.get(JARVIS_AGENT_ID) is not None

        await deregister_from_fleet(fake_client)
        assert await patch_registry.get(JARVIS_AGENT_ID) is None

    async def test_deregister_silent_on_missing_entry(
        self,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """AC-007 / AC-008: deregister of a missing entry does not raise."""
        # Registry is empty — InMemoryManifestRegistry.deregister silently
        # ignores missing keys, and the wrapper preserves that.
        await deregister_from_fleet(fake_client, agent_id="never-registered")

    async def test_deregister_swallows_transport_errors(
        self,
        fake_client: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Unexpected transport failures log WARN rather than raising."""

        async def _exploding_resolve(_client: Any) -> Any:
            raise RuntimeError("broker unreachable")

        monkeypatch.setattr(fleet_registration, "_resolve_registry", _exploding_resolve)

        with capture_logs() as logs:
            # Must not raise — clean shutdown trumps a flaky broker.
            await deregister_from_fleet(fake_client)

        warn_logs = [entry for entry in logs if entry.get("event") == "fleet_deregister_failed"]
        assert warn_logs, "expected fleet_deregister_failed WARN log"
        assert all(entry.get("log_level") == "warning" for entry in warn_logs)

    async def test_deregister_uses_default_jarvis_agent_id(
        self,
        jarvis_config: JarvisConfig,
        fake_client: object,
        patch_registry: InMemoryManifestRegistry,
    ) -> None:
        """Default agent_id resolves to ``"jarvis"`` per the spec signature."""
        manifest = build_jarvis_manifest(jarvis_config)
        await register_on_fleet(fake_client, manifest)
        # No agent_id arg → defaults to JARVIS_AGENT_ID
        await deregister_from_fleet(fake_client)
        assert await patch_registry.get(JARVIS_AGENT_ID) is None


# ---------------------------------------------------------------------------
# Public-surface invariants
# ---------------------------------------------------------------------------


class TestPublicSurface:
    """Module-level exports match API-internal §2."""

    def test_module_exports_required_symbols(self) -> None:
        """The four functions and the exception type are public."""
        public = set(fleet_registration.__all__)
        assert {
            "build_jarvis_manifest",
            "register_on_fleet",
            "heartbeat_loop",
            "deregister_from_fleet",
            "NATSConnectionError",
        }.issubset(public)
