"""pytest-bdd glue module for the feat-jarvis-004 fleet/dispatch feature file.

Binds the sibling ``.feature`` file's scenarios into pytest's collection
tree via :func:`pytest_bdd.scenarios`. Same shape as the FEAT-JARVIS-002
and FEAT-JARVIS-003 glue
(``features/feat-jarvis-002-core-tools-and-dispatch/test_feat_jarvis_002_core_tools_and_dispatch.py``
and
``features/feat-jarvis-003-async-subagent-and-frontier-escape/test_feat_jarvis_003_async_subagent_and_frontier_escape.py``)
and is required by ``features/conftest.py``'s ``_FeatureFile.collect``
hook — without a glue file at this path, ``pytest <slug>.feature``
exits 4 ("not found") and the GuardKit BDD runner reports zero scenarios
collected for every TASK-J004-* task that tags a scenario in this file.

TASK-J004-007 step-defs — implemented (this file)
-------------------------------------------------
The two ``@task:TASK-J004-007`` scenarios
("Jarvis publishes its own manifest on fleet.register at startup" and
"Jarvis republishes its manifest periodically as a heartbeat") have full
``@given/@when/@then`` step-defs below. They drive
:mod:`jarvis.infrastructure.fleet_registration` against an
:class:`nats_core.InMemoryManifestRegistry` substituted in via
``monkeypatch.setattr(fleet_registration, "_resolve_registry", ...)`` —
the same Protocol-substitution pattern the unit-test suite uses. No
in-process NATS broker is required.

Scenarios tagged for OTHER TASK-J004-* tasks remain ``scenarios_pending``
(pytest-bdd raises ``StepDefinitionNotFoundError`` per the FEAT-BDDM
convention) until those tasks land their own step-defs. Coach treats
``scenarios_pending`` as informational (should_fix), not blocking.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from nats_core import AgentManifest, InMemoryManifestRegistry
from pytest_bdd import given, scenarios, then, when

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import fleet_registration
from jarvis.infrastructure.fleet_registration import (
    JARVIS_AGENT_ID,
    JARVIS_TEMPLATE,
    build_jarvis_manifest,
    deregister_from_fleet,
    heartbeat_loop,
    register_on_fleet,
)

scenarios("./feat-jarvis-004-fleet-registration-and-specialist-dispatch.feature")


# ---------------------------------------------------------------------------
# Test-state container
# ---------------------------------------------------------------------------


class _FleetWorld:
    """Mutable per-scenario state shared between step-defs.

    pytest-bdd does not provide a built-in scenario-scoped container, so a
    single fixture-managed instance threads state from Background → Given
    → When → Then. Kept deliberately small — only what the two
    TASK-J004-007 scenarios need.
    """

    config: JarvisConfig
    registry: InMemoryManifestRegistry
    client: object
    initial_manifest: AgentManifest | None
    republished_manifests: list[AgentManifest]
    transport_available: bool

    def __init__(self) -> None:
        # Default ``jarvis_agent_version`` ("0.4.0") and
        # ``heartbeat_interval_seconds`` (30) are valid for the manifest
        # validators; tests override the interval indirectly by patching
        # ``asyncio.sleep`` rather than mutating config here.
        self.config = JarvisConfig(openai_base_url="http://fake-endpoint/v1")
        self.registry = InMemoryManifestRegistry()
        self.client = object()
        self.initial_manifest = None
        self.republished_manifests = []
        self.transport_available = False


@pytest.fixture()
def fleet_world(monkeypatch: pytest.MonkeyPatch) -> _FleetWorld:
    """Provision a fresh :class:`_FleetWorld` and re-route the registry.

    Patches ``fleet_registration._resolve_registry`` to return the
    in-memory registry held on the world. This is the same pattern the
    unit-test suite (``tests/test_fleet_registration.py``) uses, so the
    BDD scenarios exercise identical behaviour without needing an
    in-process NATS broker.
    """
    world = _FleetWorld()

    async def _fake_resolve(_client: Any) -> InMemoryManifestRegistry:
        return world.registry

    monkeypatch.setattr(fleet_registration, "_resolve_registry", _fake_resolve)
    return world


# ---------------------------------------------------------------------------
# Background steps (shared by every scenario in the .feature file)
# ---------------------------------------------------------------------------


@given("Jarvis is starting up with a configured NATS endpoint")
def _given_jarvis_starting(fleet_world: _FleetWorld) -> None:
    """Background pre-condition: a JarvisConfig is available.

    The NATS endpoint itself is stubbed — production code reaches the
    broker via ``NATSKVManifestRegistry`` which we substitute with
    :class:`InMemoryManifestRegistry` for these scenarios.
    """
    assert fleet_world.config is not None


@given("the configured Graphiti endpoint")
def _given_graphiti_endpoint(fleet_world: _FleetWorld) -> None:
    """Background pre-condition: Graphiti config is loaded.

    Graphiti is not exercised by the TASK-J004-007 scenarios (it lights
    up in TASK-J004-010 / -015), so this step asserts only that the
    JarvisConfig has been built.
    """
    assert fleet_world.config is not None


@given("the configured stub capability catalogue as a fallback")
def _given_stub_catalogue(fleet_world: _FleetWorld) -> None:
    """Background pre-condition: stub catalogue path is configured.

    ``JarvisConfig.stub_capabilities_path`` defaults to
    ``src/jarvis/config/stub_capabilities.yaml`` and is a no-op for the
    TASK-J004-007 fleet-register / heartbeat scenarios.
    """
    assert fleet_world.config.stub_capabilities_path is not None


# ---------------------------------------------------------------------------
# Scenario A — "Jarvis publishes its own manifest on fleet.register at startup"
# ---------------------------------------------------------------------------


@given("the NATS transport is available")
def _given_nats_available(fleet_world: _FleetWorld) -> None:
    """Mark the in-memory registry as reachable.

    The fixture's ``_fake_resolve`` always succeeds, so this step simply
    flips a flag the When step can read. A future "transport unavailable"
    scenario would override the resolver to raise.
    """
    fleet_world.transport_available = True


@when("Jarvis completes startup")
def _when_jarvis_completes_startup(fleet_world: _FleetWorld) -> None:
    """Drive the production startup path: build manifest + register.

    Mirrors the lifecycle bootstrap's ``register_on_fleet`` call. Uses
    :func:`asyncio.run` because the production path is ``async`` and
    pytest-bdd step-defs are sync.
    """
    assert fleet_world.transport_available, "Background did not mark transport ready"
    manifest = build_jarvis_manifest(fleet_world.config)
    asyncio.run(register_on_fleet(fleet_world.client, manifest))
    fleet_world.initial_manifest = manifest


@then("Jarvis's manifest should be discoverable on the fleet registry")
def _then_manifest_discoverable(fleet_world: _FleetWorld) -> None:
    """Assert the registry now holds Jarvis's entry under its agent_id."""
    stored = asyncio.run(fleet_world.registry.get(JARVIS_AGENT_ID))
    assert stored is not None, "Jarvis manifest missing from fleet registry"
    assert stored.agent_id == JARVIS_AGENT_ID


@then("the manifest should identify Jarvis as a core fleet member")
def _then_manifest_core_tier(fleet_world: _FleetWorld) -> None:
    """Trust tier must be ``"core"`` (per ADR-ARCH-026 / API-internal §2)."""
    stored = asyncio.run(fleet_world.registry.get(JARVIS_AGENT_ID))
    assert stored is not None
    assert stored.trust_tier == "core"


@then("the manifest should advertise Jarvis's general-purpose-agent role")
def _then_manifest_gpa_role(fleet_world: _FleetWorld) -> None:
    """Template must be the canonical ``general_purpose_agent``."""
    stored = asyncio.run(fleet_world.registry.get(JARVIS_AGENT_ID))
    assert stored is not None
    assert stored.template == JARVIS_TEMPLATE
    assert stored.template == "general_purpose_agent"


@then(
    "the manifest should advertise Jarvis's intent capabilities for "
    "conversational dispatch, capability dispatch, meta-dispatch, "
    "and memory recall"
)
def _then_manifest_four_intents(fleet_world: _FleetWorld) -> None:
    """All four canonical intent patterns from API-internal §2 must appear."""
    stored = asyncio.run(fleet_world.registry.get(JARVIS_AGENT_ID))
    assert stored is not None
    patterns = {intent.pattern for intent in stored.intents}
    assert patterns == {
        "conversational.gpa",
        "dispatch.by_capability",
        "meta.dispatch",
        "memory.recall",
    }


# ---------------------------------------------------------------------------
# Scenario B — "Jarvis republishes its manifest periodically as a heartbeat"
# ---------------------------------------------------------------------------


@given("Jarvis has registered on the fleet")
def _given_jarvis_registered(fleet_world: _FleetWorld) -> None:
    """Pre-register Jarvis so the heartbeat scenario starts from steady state."""
    manifest = build_jarvis_manifest(fleet_world.config)
    asyncio.run(register_on_fleet(fleet_world.client, manifest))
    fleet_world.initial_manifest = manifest


@when("the configured heartbeat interval elapses")
def _when_heartbeat_interval_elapses(
    fleet_world: _FleetWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run :func:`heartbeat_loop` long enough to observe ≥1 republish.

    ``asyncio.sleep`` is patched to a no-op so the loop runs at full
    speed; we record each ``registry.register`` invocation to
    ``world.republished_manifests`` and cancel after the first tick. The
    initial register from the Given step is captured separately on
    ``world.initial_manifest``; this step records only heartbeat ticks.
    """
    real_register = fleet_world.registry.register
    fleet_world.republished_manifests = []

    async def _capture_register(manifest: AgentManifest) -> None:
        fleet_world.republished_manifests.append(manifest)
        await real_register(manifest)
        # Cancel the loop once a heartbeat tick has been observed so the
        # test does not run forever under the patched (no-op) sleep.
        raise asyncio.CancelledError

    monkeypatch.setattr(fleet_world.registry, "register", _capture_register)

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    async def _drive() -> None:
        with pytest.raises(asyncio.CancelledError):
            await heartbeat_loop(
                fleet_world.client,
                fleet_world.initial_manifest,  # type: ignore[arg-type]
                fleet_world.config,
            )

    asyncio.run(_drive())


@then("Jarvis's manifest should be republished to the fleet")
def _then_manifest_republished(fleet_world: _FleetWorld) -> None:
    """At least one heartbeat tick must have re-published the manifest."""
    assert len(fleet_world.republished_manifests) >= 1, (
        "heartbeat_loop did not republish the manifest"
    )


@then("the manifest's trust tier and version should remain stable across republications")
def _then_trust_tier_and_version_stable(fleet_world: _FleetWorld) -> None:
    """Republished manifests must carry the same trust_tier + version."""
    initial = fleet_world.initial_manifest
    assert initial is not None
    for republished in fleet_world.republished_manifests:
        assert republished.trust_tier == initial.trust_tier
        assert republished.version == initial.version


# ---------------------------------------------------------------------------
# Module-level cleanup: ensure no leftover entries leak between scenarios.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_clean_deregister(fleet_world: _FleetWorld) -> Any:
    """After each scenario, deregister Jarvis to clear the in-memory registry.

    Unrelated to ACs but tightens scenario isolation: the fixture-scoped
    registry is already fresh per test, so this is belt-and-braces against
    a future refactor that promotes the registry to module scope.
    """
    yield
    asyncio.run(deregister_from_fleet(fleet_world.client))
