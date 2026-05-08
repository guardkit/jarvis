"""Tests for TASK-J002-015: assemble_tool_list + tools package re-exports.

Validates the public surface of ``jarvis.tools`` per API-internal.md §1.1:

- AC-001: ``__init__.py`` re-exports the documented public surface.
- AC-002: ``assemble_tool_list(config, capability_registry)`` is exposed.
- AC-003: returns the 9 tools in stable alphabetical order.
- AC-004: ``assemble_tool_list`` is the only place that binds the
  capability registry into the capability + dispatch tools (snapshot
  isolation).
- AC-005: no production module under ``src/jarvis/`` imports
  ``jarvis.tools.general``, ``jarvis.tools.capabilities``, or
  ``jarvis.tools.dispatch`` directly — only ``jarvis.tools``.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest
from langchain_core.tools import BaseTool

import jarvis.tools as tools_pkg
from jarvis.tools import (
    CalendarEvent,
    CapabilityDescriptor,
    DispatchError,
    WebResult,
    assemble_tool_list,
    calculate,
    capabilities_refresh,
    capabilities_subscribe_updates,
    dispatch_by_capability,
    get_calendar_events,
    list_available_capabilities,
    load_stub_registry,
    queue_build,
    read_file,
    search_web,
)
from jarvis.tools import capabilities as capabilities_module
from jarvis.tools import dispatch as dispatch_module
from jarvis.tools import general as general_module
from jarvis.config.settings import JarvisConfig


# ---------------------------------------------------------------------------
# Constants — the canonical alphabetical order required by AC-003.
#
# TASK-J003-012 (Layer 3 of DDR-014) added the ``include_frontier`` kwarg to
# ``assemble_tool_list``; the **default-True** attended surface splices
# ``escalate_to_frontier`` between ``dispatch_by_capability`` and
# ``get_calendar_events``. The 9-tool ambient surface is kept available
# behind ``include_frontier=False`` so that the FEAT-J002 contract stays
# accessible for ambient / learning / async-subagent contexts.
# ---------------------------------------------------------------------------
EXPECTED_TOOL_ORDER = [
    "calculate",
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "dispatch_by_capability",
    "escalate_to_frontier",
    "get_calendar_events",
    "list_available_capabilities",
    "queue_build",
    "read_file",
    "search_web",
]

# Public surface per API-internal.md §1.1 (FEAT-J003 adds
# ``escalate_to_frontier`` to the dispatch group).
EXPECTED_PUBLIC_SURFACE = {
    # Pydantic types
    "CalendarEvent",
    "CapabilityDescriptor",
    "CapabilityToolSummary",
    "DispatchError",
    "WebResult",
    # General tools
    "calculate",
    "get_calendar_events",
    "read_file",
    "search_web",
    # Capability catalogue tools
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "list_available_capabilities",
    # Dispatch tools (includes the FEAT-J003 attended-only escalation)
    "dispatch_by_capability",
    "escalate_to_frontier",
    "queue_build",
    # Assembly + loader
    "assemble_tool_list",
    "load_stub_registry",
}


_SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def descriptor_alpha() -> CapabilityDescriptor:
    """Return a minimal valid descriptor."""
    return CapabilityDescriptor(
        agent_id="alpha",
        role="Alpha Agent",
        description="Handles alpha capabilities for tests.",
    )


@pytest.fixture()
def descriptor_bravo() -> CapabilityDescriptor:
    """Return a second valid descriptor."""
    return CapabilityDescriptor(
        agent_id="bravo",
        role="Bravo Agent",
        description="Handles bravo capabilities for tests.",
    )


@pytest.fixture()
def descriptor_beta() -> CapabilityDescriptor:
    """Return a descriptor that intentionally collides with neither alpha nor bravo.

    Used by the TASK-DSR-003 / W2 divergent-registry regression to assert that
    the dispatch resolver observes the live registry's content (``beta``)
    rather than the stub-list positional argument (``alpha``).
    """
    from jarvis.tools.capabilities import CapabilityToolSummary

    return CapabilityDescriptor(
        agent_id="beta",
        role="Beta Agent",
        description="Handles beta capabilities for tests.",
        capability_list=[
            CapabilityToolSummary(
                tool_name="beta_tool",
                description="A tool exposed only by the live registry.",
                risk_level="read_only",
            ),
        ],
    )


@pytest.fixture()
def reset_tool_state() -> None:
    """Snapshot and restore tool-module state around each test.

    FEAT-JARVIS-004 (TASK-J004-012) changed the capabilities-module's
    ``_capability_registry`` swap-point type from ``list`` to
    ``CapabilitiesRegistry | None``; the snapshot is preserved as an
    opaque object reference rather than a list copy.
    """
    saved_general = general_module._config
    saved_caps = capabilities_module._capability_registry
    saved_dispatch = list(dispatch_module._capability_registry)
    yield
    general_module._config = saved_general
    capabilities_module._capability_registry = saved_caps
    dispatch_module._capability_registry = saved_dispatch


# ---------------------------------------------------------------------------
# AC-001 — public surface re-exports
# ---------------------------------------------------------------------------
class TestAC001PublicSurface:
    """``jarvis.tools`` re-exports exactly the documented public surface."""

    def test_all_attribute_matches_expected_surface(self) -> None:
        """``__all__`` mirrors API-internal.md §1.1 set."""
        assert set(tools_pkg.__all__) == EXPECTED_PUBLIC_SURFACE

    @pytest.mark.parametrize("symbol", sorted(EXPECTED_PUBLIC_SURFACE))
    def test_each_symbol_is_importable(self, symbol: str) -> None:
        """Every documented symbol is reachable as ``jarvis.tools.<symbol>``."""
        assert hasattr(tools_pkg, symbol), f"jarvis.tools missing {symbol!r}"

    def test_types_are_pydantic_classes(self) -> None:
        """The four type re-exports are the canonical Pydantic models."""
        from jarvis.tools.capabilities import CapabilityDescriptor as CD
        from jarvis.tools.types import (
            CalendarEvent as CE,
            DispatchError as DE,
            WebResult as WR,
        )

        assert CapabilityDescriptor is CD
        assert CalendarEvent is CE
        assert DispatchError is DE
        assert WebResult is WR


# ---------------------------------------------------------------------------
# AC-002 — assemble_tool_list signature
# ---------------------------------------------------------------------------
class TestAC002Signature:
    """``assemble_tool_list(config, capability_registry)`` is the wiring entry."""

    def test_function_is_callable(self) -> None:
        """``assemble_tool_list`` is a top-level callable on the package."""
        assert callable(assemble_tool_list)

    def test_returns_list_of_base_tools(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """The return value is ``list[BaseTool]`` of length 10 (attended)."""
        result = assemble_tool_list(test_config, [descriptor_alpha])
        assert isinstance(result, list)
        # TASK-J003-012: default ``include_frontier=True`` splices in the
        # ``escalate_to_frontier`` cloud escape hatch alongside the FEAT-J002
        # 9 tools.
        assert len(result) == 10
        for tool in result:
            assert isinstance(tool, BaseTool)

    def test_accepts_empty_registry(
        self,
        test_config: JarvisConfig,
        reset_tool_state: None,
    ) -> None:
        """An empty capability registry is permitted."""
        result = assemble_tool_list(test_config, [])
        assert len(result) == 10


# ---------------------------------------------------------------------------
# AC-003 — alphabetical order
# ---------------------------------------------------------------------------
class TestAC003AlphabeticalOrder:
    """Tools come back in stable alphabetical order."""

    def test_tool_names_match_expected_order(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Tool names are exactly the documented sequence."""
        result = assemble_tool_list(test_config, [descriptor_alpha])
        actual = [tool.name for tool in result]
        assert actual == EXPECTED_TOOL_ORDER

    def test_order_is_idempotent_across_calls(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Repeated calls yield the same alphabetical order."""
        first = [t.name for t in assemble_tool_list(test_config, [descriptor_alpha])]
        second = [t.name for t in assemble_tool_list(test_config, [descriptor_alpha])]
        assert first == second == EXPECTED_TOOL_ORDER


# ---------------------------------------------------------------------------
# AC-004 — snapshot isolation: only assemble_tool_list binds the registry
# ---------------------------------------------------------------------------
class TestAC004SnapshotIsolation:
    """``assemble_tool_list`` is the single point that binds the registry."""

    def test_capabilities_module_receives_protocol(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """``capabilities._capability_registry`` is bound to the Protocol object.

        TASK-J004-FIX-001 — the catalogue-tool slot now stores the
        Protocol-shaped registry directly (no list copy) so the tool
        bodies can call ``snapshot()`` / ``refresh()`` /
        ``subscribe_updates(...)``. The slot is bound to whichever
        Protocol object the caller passes via ``capabilities_registry=``;
        ``None`` (the default) parks it at the pre-wired sentinel.
        """

        class _ProtocolFake:
            def snapshot(self) -> list[CapabilityDescriptor]:
                return [descriptor_alpha, descriptor_bravo]

            async def refresh(self) -> None:
                return None

            async def subscribe_updates(self, callback: object) -> None:
                return None

            async def close(self) -> None:
                return None

        registry_obj = _ProtocolFake()
        assemble_tool_list(
            test_config,
            [descriptor_alpha, descriptor_bravo],
            capabilities_registry=registry_obj,
        )
        assert capabilities_module._capability_registry is registry_obj

    def test_capabilities_module_default_is_none(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Omitting ``capabilities_registry`` parks the slot at ``None``.

        ADR-ARCH-021 sentinel semantics — catalogue tools then surface
        ``ERROR: registry_unavailable``.
        """
        assemble_tool_list(test_config, [descriptor_alpha])
        assert capabilities_module._capability_registry is None

    def test_dispatch_module_receives_snapshot(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """``dispatch._capability_registry`` is rebound to a snapshot."""
        registry = [descriptor_alpha, descriptor_bravo]
        assemble_tool_list(test_config, registry)
        assert dispatch_module._capability_registry == registry

    def test_dispatch_snapshot_is_decoupled_from_caller_list(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Mutating the caller's list after assembly does not leak into dispatch.

        The dispatch slot stores a fresh ``list(...)`` copy (ASSUM-006);
        the capabilities slot stores the Protocol object directly so its
        own ``snapshot()`` semantics own freshness, not
        ``assemble_tool_list``.
        """
        registry = [descriptor_alpha]
        assemble_tool_list(test_config, registry)

        # Mutate the operator's outer list; dispatch must remain
        # pinned to the snapshot taken at assemble time.
        registry.append(descriptor_bravo)

        assert dispatch_module._capability_registry == [descriptor_alpha]

    def test_search_web_config_is_injected(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """``general.configure(config)`` runs once during assembly."""
        assemble_tool_list(test_config, [descriptor_alpha])
        assert general_module._config is test_config

    def test_list_available_capabilities_observes_snapshot(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """End-to-end: the catalogue tool reflects the assembled snapshot.

        TASK-J004-FIX-001 — ``assemble_tool_list`` now accepts a
        ``capabilities_registry`` Protocol kwarg and snapshots it into
        the catalogue-tool slot directly. The test passes a
        Protocol-conformant adapter as that kwarg so the catalogue tool
        can call ``.snapshot()`` without a post-hoc module-attribute
        rewrite.
        """

        class _ListBackedRegistry:
            """Test-local Protocol adapter for the catalogue-tool slot."""

            def __init__(self, descriptors: list[CapabilityDescriptor]) -> None:
                self._descriptors = descriptors

            def snapshot(self) -> list[CapabilityDescriptor]:
                return list(self._descriptors)

            async def refresh(self) -> None:
                return None

            async def subscribe_updates(self, callback: object) -> None:
                return None

            async def close(self) -> None:
                return None

        assemble_tool_list(
            test_config,
            [descriptor_alpha],
            capabilities_registry=_ListBackedRegistry([descriptor_alpha]),
        )

        rendered = list_available_capabilities.invoke({})
        loaded = json.loads(rendered)
        assert isinstance(loaded, list)
        assert len(loaded) == 1
        assert loaded[0]["agent_id"] == "alpha"


# ---------------------------------------------------------------------------
# AC-005 — no production module imports submodules directly
# ---------------------------------------------------------------------------
_INTERNAL_PREFIXES = (
    "jarvis.tools.general",
    "jarvis.tools.capabilities",
    "jarvis.tools.dispatch",
)


def _python_files_under(root: pathlib.Path) -> list[pathlib.Path]:
    """Return all .py files recursively under ``root``."""
    return sorted(root.rglob("*.py"))


def _imports(filepath: pathlib.Path) -> list[str]:
    """Return imported module names for ``filepath``."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


class TestAC005NoSubmoduleImports:
    """Production code under ``src/jarvis/`` consumes the package surface only.

    The check is scoped to modules **outside** ``src/jarvis/tools/`` —
    intra-package siblings (e.g. ``dispatch.py`` importing
    ``capabilities.py``) are necessary and explicitly permitted.
    """

    def test_no_production_module_imports_submodules(self) -> None:
        """Walk ``src/jarvis/`` excluding ``src/jarvis/tools/``."""
        jarvis_dir = _SRC_DIR / "jarvis"
        tools_dir = jarvis_dir / "tools"

        violations: list[str] = []
        for filepath in _python_files_under(jarvis_dir):
            try:
                filepath.relative_to(tools_dir)
            except ValueError:
                # Outside the tools package — apply the AC-005 check.
                pass
            else:
                # Inside ``jarvis.tools.*`` — sibling imports are fine.
                continue

            for module_name in _imports(filepath):
                for forbidden in _INTERNAL_PREFIXES:
                    if module_name == forbidden or module_name.startswith(forbidden + "."):
                        rel = filepath.relative_to(_SRC_DIR)
                        violations.append(f"{rel}: imports {module_name!r}")

        assert violations == [], (
            "Production modules must consume `jarvis.tools` only:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# TASK-DSR-003 / W2 — dispatch resolver sources from the live registry
# (closes the DISPATCH-STUB-RESOLVER gap surfaced by review TASK-REV-CB48 F2)
# ---------------------------------------------------------------------------
class _ListBackedRegistry:
    """Test-local Protocol adapter — same shape as the helper inside
    ``TestAC004SnapshotIsolation.test_list_available_capabilities_observes_snapshot``
    (kept module-level here so multiple tests can reuse it).
    """

    def __init__(self, descriptors: list[CapabilityDescriptor]) -> None:
        self._descriptors = descriptors

    def snapshot(self) -> list[CapabilityDescriptor]:
        return list(self._descriptors)

    async def refresh(self) -> None:
        return None

    async def subscribe_updates(self, callback: object) -> None:
        return None

    async def close(self) -> None:
        return None


class TestDispatchResolverSourcesFromLiveRegistry:
    """W2 regression: ``dispatch._capability_registry`` reflects the live
    registry's content, not the stub-list positional argument.

    Closes the DISPATCH-STUB-RESOLVER gap surfaced by TASK-REV-CB48 F2.
    Structural twin of TASK-J004-FIX-001 (which closed the catalogue-tool
    side of the same wiring inconsistency).
    """

    def test_dispatch_resolver_observes_live_registry_for_divergent_content(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_beta: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Dispatch resolver MUST find tools published by the live registry
        even when they are absent from the stub list.

        F3 fixture from review TASK-REV-CB48: stub list contains alpha only;
        live registry contains beta only. The dispatch slot must reflect the
        LIVE registry (beta), not the stub list (alpha).
        """
        assemble_tool_list(
            test_config,
            [descriptor_alpha],
            capabilities_registry=_ListBackedRegistry([descriptor_beta]),
        )

        snapshot = list(dispatch_module._capability_registry)
        agent_ids = {d.agent_id for d in snapshot}
        assert "beta" in agent_ids, (
            "dispatch slot must reflect the live registry's content"
        )
        assert "alpha" not in agent_ids, (
            "dispatch slot MUST NOT fall back to the stub list when a "
            "live registry is supplied"
        )

    def test_dispatch_slot_falls_back_to_stub_list_when_registry_is_none(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """FEAT-J002 / Phase 1 default path remains intact.

        When ``capabilities_registry`` is omitted (None), the dispatch slot
        falls back to ``list(capability_registry)`` so the FEAT-J002 unit
        tests that pre-date the Protocol surface keep working.
        """
        assemble_tool_list(test_config, [descriptor_alpha])

        snapshot = list(dispatch_module._capability_registry)
        assert [d.agent_id for d in snapshot] == ["alpha"]

    def test_dispatch_snapshot_is_decoupled_from_live_registry_internal_list(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_beta: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """ASSUM-006 snapshot isolation extends to the live-source path.

        The dispatch slot stores a fresh ``list(...)`` copy of
        ``snapshot()`` — mutating that list does not poison the live
        registry's internal cache, and a subsequent rebind from a watch
        event produces a fresh list.
        """
        live = _ListBackedRegistry([descriptor_alpha])
        assemble_tool_list(test_config, [], capabilities_registry=live)

        # Mutate the dispatch slot's list — must not poison the registry.
        dispatch_module._capability_registry.clear()

        # The live registry's snapshot remains intact.
        assert [d.agent_id for d in live.snapshot()] == ["alpha"]
