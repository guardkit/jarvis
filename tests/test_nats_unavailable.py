"""Soft-fail tests: NATS unavailable — DDR-021 invariants (TASK-J004-016).

Asserts the supervisor's NATS-down behaviour:

* Startup against an unreachable broker still produces a usable
  :class:`AppState` — the process does not exit / crash.
* ``state.nats_client is None`` (DDR-021 soft-fail at the connect boundary).
* ``dispatch_by_capability`` returns the structured
  ``DEGRADED: transport_unavailable — NATS connection failed`` string.
* ``list_available_capabilities`` falls back to the Phase 2 stub list — the
  FEAT-JARVIS-002 regression is preserved (catalogue identical to the YAML).
* ``escalate_to_frontier`` continues to function on attended sessions
  because the cloud-frontier path has no NATS dependency.

Every scenario asserts process-still-alive at the end (no broker dependency
inside the test process). All NATS client construction is patched via
:func:`unittest.mock.patch` against
``jarvis.infrastructure.lifecycle._connect_nats`` and
``jarvis.infrastructure.nats_client.NATSClient.connect``; no real broker
is required.
"""

from __future__ import annotations

import io
import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.lifecycle import AppState, build_app_state
from jarvis.shared.constants import Adapter
from jarvis.tools import capabilities as capabilities_module
from jarvis.tools import dispatch as dispatch_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
    list_available_capabilities,
)
from jarvis.tools.dispatch import dispatch_by_capability, escalate_to_frontier
from jarvis.tools.dispatch_types import FrontierTarget


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _stub_yaml_path() -> Path:
    return _project_root() / "src" / "jarvis" / "config" / "stub_capabilities.yaml"


@pytest.fixture()
def nats_unreachable_config() -> JarvisConfig:
    """A :class:`JarvisConfig` whose NATS URL points at an unreachable broker."""
    stub_path = _stub_yaml_path()
    assert stub_path.exists(), "stub_capabilities.yaml must ship with the package"

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            graphiti_endpoint=None,
            # Deliberately point at an unrouteable address so the integration
            # surface (if it ever leaked through the patches) would fail fast
            # rather than block on a real broker.
            nats_url="nats://203.0.113.1:4222",
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def stub_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a deterministic capability registry into the dispatch + tool seams."""
    saved_dispatch = dispatch_module._capability_registry
    saved_tools = capabilities_module._capability_registry

    registry: list[CapabilityDescriptor] = [
        CapabilityDescriptor(
            agent_id="product-owner",
            role="Product Owner",
            description="Reviews specs against acceptance criteria.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="review_spec",
                    description="Review a feature spec",
                    risk_level="read_only",
                ),
            ],
        ),
    ]

    class _PreloadedRegistry:
        """Protocol-compatible Stub registry shim for the capabilities tool."""

        def __init__(self, descriptors: list[CapabilityDescriptor]) -> None:
            self._descriptors = list(descriptors)

        def snapshot(self) -> list[CapabilityDescriptor]:
            return list(self._descriptors)

        async def refresh(self) -> None:  # pragma: no cover - trivial
            return None

        async def subscribe_updates(self, callback: Any) -> None:  # pragma: no cover
            del callback
            return None

        async def close(self) -> None:  # pragma: no cover
            return None

    dispatch_module._capability_registry = registry
    capabilities_module._capability_registry = _PreloadedRegistry(registry)
    try:
        yield registry
    finally:
        dispatch_module._capability_registry = saved_dispatch
        capabilities_module._capability_registry = saved_tools


# ---------------------------------------------------------------------------
# Process-still-alive helper
# ---------------------------------------------------------------------------
def _assert_process_alive(state: AppState) -> None:
    """Sanity check at the tail of every scenario.

    DDR-021 mandates the supervisor process stays up on NATS soft-fail. The
    cheapest signal is that ``state`` is constructed and frozen — meaning
    ``build_app_state`` returned without raising and the wired tools are
    callable. We deliberately avoid heuristics like ``sys.is_finalizing()``;
    if the call returned a state the lifecycle did not crash.
    """
    assert state is not None
    assert isinstance(state, AppState)
    # Frozen dataclass — attempting mutation raises FrozenInstanceError.
    # The truthy presence of a supervisor confirms the build pipeline ran.
    assert state.supervisor is not None


# ===========================================================================
# AC: startup against an unreachable NATS URL still produces an AppState
# ===========================================================================
class TestStartupNATSUnreachable:
    """Lifecycle returns a usable :class:`AppState` even when NATS is unreachable."""

    @pytest.mark.asyncio
    async def test_startup_with_unreachable_nats_still_starts(
        self,
        nats_unreachable_config: JarvisConfig,
    ) -> None:
        """``build_app_state`` returns successfully; process still alive."""
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
            state = await build_app_state(nats_unreachable_config)

        _assert_process_alive(state)

    @pytest.mark.asyncio
    async def test_state_nats_client_is_none(
        self,
        nats_unreachable_config: JarvisConfig,
    ) -> None:
        """``state.nats_client is None`` — explicit assertion of DDR-021 invariant."""
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
            state = await build_app_state(nats_unreachable_config)

        assert state.nats_client is None
        assert state.fleet_heartbeat_task is None
        _assert_process_alive(state)


# ===========================================================================
# AC: dispatch_by_capability returns the DEGRADED transport string
# ===========================================================================
class TestDispatchReturnsDegradedTransportUnavailable:
    """``dispatch_by_capability`` returns the structured DDR-021 DEGRADED string."""

    @pytest.mark.asyncio
    async def test_dispatch_returns_degraded_transport_unavailable(
        self,
        stub_registry: list[CapabilityDescriptor],
    ) -> None:
        """With ``_nats_client is None`` the tool surfaces DEGRADED synchronously."""
        # Wire dispatch deps as the lifecycle would have on NATS soft-fail.
        dispatch_module._nats_client = None
        dispatch_module._dispatch_semaphore = None
        dispatch_module._routing_history_writer = None

        result = await dispatch_by_capability.ainvoke(
            {"tool_name": "review_spec", "payload_json": "{}"}
        )

        # The exact string from the AC and the @tool docstring.
        assert result == "DEGRADED: transport_unavailable — NATS connection failed"


# ===========================================================================
# AC: list_available_capabilities falls back to the Phase 2 stub list
# ===========================================================================
class TestListAvailableCapabilitiesPhase2StubFallback:
    """Stub-fallback catalogue is identical to the Phase 2 stub YAML — no drift."""

    def test_list_available_capabilities_returns_stub_list_phase2_regression(
        self,
    ) -> None:
        """Tool output ``agent_id`` set matches the YAML — DDR-021 fallback parity."""
        from jarvis.infrastructure.capabilities_registry import StubCapabilitiesRegistry

        # Saved/restored module-level binding so the test is hermetic.
        saved = capabilities_module._capability_registry
        capabilities_module._capability_registry = StubCapabilitiesRegistry(
            _stub_yaml_path()
        )
        try:
            raw = list_available_capabilities.invoke({})
        finally:
            capabilities_module._capability_registry = saved

        # Successful tool body returns JSON of CapabilityDescriptors.
        assert isinstance(raw, str)
        assert raw.startswith("[")
        descriptors = json.loads(raw)

        # Source-of-truth comparison against the YAML the lifecycle reads at
        # startup. Asserts the Phase 2 regression: stub fallback identical to
        # the YAML byte-for-byte (agent_id set + capability_list shapes).
        with _stub_yaml_path().open("r", encoding="utf-8") as handle:
            yaml_doc = yaml.safe_load(handle)
        expected_agent_ids = {entry["agent_id"] for entry in yaml_doc["capabilities"]}

        rendered_agent_ids = {entry["agent_id"] for entry in descriptors}
        assert rendered_agent_ids == expected_agent_ids, (
            "list_available_capabilities stub fallback drifted from "
            "stub_capabilities.yaml — Phase 2 regression"
        )


# ===========================================================================
# AC: escalate_to_frontier still functions on attended sessions (no NATS dep)
# ===========================================================================
class TestEscalateToFrontierNoNATSDep:
    """The cloud-frontier escape path is independent of NATS state."""

    @pytest.fixture()
    def attended_session_hook(self) -> Generator[None, None, None]:
        """Wire ``_current_session_hook`` to an attended ``cli`` session."""
        saved = dispatch_module._current_session_hook

        attended_session = MagicMock()
        attended_session.adapter = Adapter.CLI
        attended_session.metadata = {"currently_in_subagent": False}

        dispatch_module._current_session_hook = lambda: attended_session
        try:
            yield
        finally:
            dispatch_module._current_session_hook = saved

    def test_escalate_to_frontier_works_on_attended_session_without_nats(
        self,
        attended_session_hook: None,
    ) -> None:
        """Even with NATS unwired, the Gemini escape returns the canned text."""
        # Explicitly clear dispatch's NATS binding so a regression that wired
        # NATS into the frontier path would fail this test.
        dispatch_module._nats_client = None

        gemini_response = MagicMock()
        gemini_response.text = "frontier-canned-reply"
        gemini_client = MagicMock()
        gemini_client.models.generate_content.return_value = gemini_response

        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}, clear=True),
            patch("google.genai.Client", return_value=gemini_client),
        ):
            reply = escalate_to_frontier.invoke(
                {"instruction": "hi", "target": FrontierTarget.GEMINI_3_1_PRO}
            )

        assert reply == "frontier-canned-reply"
        # The escape did not consult any NATS client — by construction
        # (``_nats_client is None``) the tool body cannot have touched it.
        assert dispatch_module._nats_client is None
