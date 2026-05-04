"""Tests for TASK-J004-FIX-001 — CapabilitiesRegistry Protocol reaches the tool slot.

Closes the latent defect identified in TASK-REV-FFE4 §6: catalogue tools at
``jarvis.tools.capabilities._capability_registry`` were receiving a raw
``list[CapabilityDescriptor]`` from ``assemble_tool_list`` instead of the
Protocol-shaped ``CapabilitiesRegistry`` object that ``lifecycle.build_app_state``
was already constructing. The defect was masked in tests by a post-hoc
module-attribute rewrite that production wiring did not have, so every catalogue
tool invocation in production triggered an ``AttributeError`` that was caught
by ``except Exception`` and converted to ``ERROR: registry_unavailable`` /
``DEGRADED: transport_unavailable`` — operationally indistinguishable from a
real NATS outage.

Acceptance criteria covered:

    AC-008: Lifecycle integration test asserts Protocol reaches the slot —
            both NATS-down (Stub fallback) and NATS-up (Live registry)
            branches.

The tests assert two things on each branch:

1. ``capabilities_module._capability_registry`` is a ``CapabilitiesRegistry``
   Protocol instance, NOT a list.
2. Invoking ``list_available_capabilities`` does NOT return a structured
   ``ERROR:`` or ``DEGRADED:`` string — i.e. the catch-all that masked the
   defect can no longer fire on the happy path.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig


@pytest.fixture()
def stub_registry_config() -> JarvisConfig:
    """A ``JarvisConfig`` whose ``stub_capabilities_path`` resolves to the
    real on-disk YAML so the StubCapabilitiesRegistry path can construct."""
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists()

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
        )
    cfg.validate_provider_keys()
    return cfg


class TestProtocolReachesToolSlot:
    """``assemble_tool_list`` (called by lifecycle) writes the Protocol into
    ``jarvis.tools.capabilities._capability_registry`` on both NATS branches."""

    @pytest.mark.asyncio
    async def test_build_app_state_wires_protocol_into_tool_slot_nats_down(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """NATS soft-fail path — slot holds a Protocol, not a list."""
        import jarvis.tools.capabilities as capabilities_module
        from jarvis.infrastructure.capabilities_registry import (
            CapabilitiesRegistry,
            StubCapabilitiesRegistry,
        )
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(stub_registry_config)

        # Protocol shape — NOT a list — reached the catalogue tool slot.
        assert capabilities_module._capability_registry is not None
        assert isinstance(capabilities_module._capability_registry, CapabilitiesRegistry)
        assert isinstance(capabilities_module._capability_registry, StubCapabilitiesRegistry)
        # Production wiring should match what AppState carries.
        assert capabilities_module._capability_registry is state.capabilities_registry

        # Invoke the tool — must NOT return ERROR / DEGRADED.
        from jarvis.tools import list_available_capabilities

        result = list_available_capabilities.invoke({})
        assert not result.startswith("ERROR:"), result
        assert not result.startswith("DEGRADED:"), result

        # Stub fallback returns the on-disk YAML catalogue — 4 entries.
        payload = json.loads(result)
        assert isinstance(payload, list)
        assert len(payload) == 4

    @pytest.mark.asyncio
    async def test_build_app_state_wires_live_protocol_into_tool_slot_nats_up(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """NATS-up happy path — slot holds the Live Protocol object."""
        import asyncio

        import jarvis.tools.capabilities as capabilities_module
        from jarvis.infrastructure.capabilities_registry import CapabilitiesRegistry
        from jarvis.infrastructure.lifecycle import build_app_state
        from jarvis.tools.capabilities import CapabilityDescriptor

        # Build a Protocol-conformant fake that returns a deterministic
        # 1-entry catalogue so the test does not depend on the on-disk
        # stub YAML.
        live_descriptor = CapabilityDescriptor(
            agent_id="live-agent-1",
            role="Live registry sample agent",
            description="Live registry sample entry.",
        )

        class _LiveRegistryFake:
            """Protocol-conformant Live registry stand-in."""

            def snapshot(self) -> list[CapabilityDescriptor]:
                return [live_descriptor]

            async def refresh(self) -> None:
                return None

            async def subscribe_updates(self, callback: object) -> None:
                return None

            async def close(self) -> None:
                return None

        fake_live_registry = _LiveRegistryFake()

        fake_nats = MagicMock()
        fake_nats.drain = AsyncMock()
        fake_graphiti = MagicMock()
        fake_graphiti.aclose = AsyncMock()

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=fake_nats),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_graphiti",
                new=AsyncMock(return_value=fake_graphiti),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.register_on_fleet",
                new=AsyncMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.LiveCapabilitiesRegistry.create",
                new=AsyncMock(return_value=fake_live_registry),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.heartbeat_loop",
                new=AsyncMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[],
            ),
        ):
            state = await build_app_state(stub_registry_config)

        try:
            # Protocol shape reached the catalogue tool slot — same object
            # that AppState carries, NOT a list.
            assert capabilities_module._capability_registry is fake_live_registry
            assert isinstance(capabilities_module._capability_registry, CapabilitiesRegistry)
            assert capabilities_module._capability_registry is state.capabilities_registry

            # Invoke the catalogue tool — must NOT return ERROR / DEGRADED.
            from jarvis.tools import list_available_capabilities

            result = list_available_capabilities.invoke({})
            assert not result.startswith("ERROR:"), result
            assert not result.startswith("DEGRADED:"), result

            payload = json.loads(result)
            assert isinstance(payload, list)
            assert len(payload) == 1
            assert payload[0]["agent_id"] == "live-agent-1"
        finally:
            # Cleanup the heartbeat task scheduled by build_app_state.
            if state.fleet_heartbeat_task is not None:
                state.fleet_heartbeat_task.cancel()
                try:
                    await state.fleet_heartbeat_task
                except (asyncio.CancelledError, Exception):
                    pass
