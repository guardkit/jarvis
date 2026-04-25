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
# ---------------------------------------------------------------------------
EXPECTED_TOOL_ORDER = [
    "calculate",
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "dispatch_by_capability",
    "get_calendar_events",
    "list_available_capabilities",
    "queue_build",
    "read_file",
    "search_web",
]

# Public surface per API-internal.md §1.1.
EXPECTED_PUBLIC_SURFACE = {
    # Pydantic types
    "CalendarEvent",
    "CapabilityDescriptor",
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
    # Dispatch tools
    "dispatch_by_capability",
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
def reset_tool_state() -> None:
    """Snapshot and restore tool-module state around each test."""
    saved_general = general_module._config
    saved_caps = list(capabilities_module._capability_registry)
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
        """The return value is ``list[BaseTool]`` of length 9."""
        result = assemble_tool_list(test_config, [descriptor_alpha])
        assert isinstance(result, list)
        assert len(result) == 9
        for tool in result:
            assert isinstance(tool, BaseTool)

    def test_accepts_empty_registry(
        self,
        test_config: JarvisConfig,
        reset_tool_state: None,
    ) -> None:
        """An empty capability registry is permitted."""
        result = assemble_tool_list(test_config, [])
        assert len(result) == 9


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

    def test_capabilities_module_receives_snapshot(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """``capabilities._capability_registry`` is rebound to a snapshot."""
        registry = [descriptor_alpha, descriptor_bravo]
        assemble_tool_list(test_config, registry)
        assert capabilities_module._capability_registry == registry

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

    def test_snapshot_is_decoupled_from_caller_list(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Mutating the caller's list after assembly does not leak."""
        registry = [descriptor_alpha]
        assemble_tool_list(test_config, registry)

        # Mutate the operator's outer list; the modules must remain
        # pinned to the snapshot taken at assemble time.
        registry.append(descriptor_bravo)

        assert capabilities_module._capability_registry == [descriptor_alpha]
        assert dispatch_module._capability_registry == [descriptor_alpha]

    def test_snapshots_are_independent_lists(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Each consumer module gets its own list copy."""
        assemble_tool_list(test_config, [descriptor_alpha])
        assert (
            capabilities_module._capability_registry
            is not dispatch_module._capability_registry
        )

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
        """End-to-end: the catalogue tool reflects the assembled snapshot."""
        assemble_tool_list(test_config, [descriptor_alpha])
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
                    if module_name == forbidden or module_name.startswith(
                        forbidden + "."
                    ):
                        rel = filepath.relative_to(_SRC_DIR)
                        violations.append(f"{rel}: imports {module_name!r}")

        assert violations == [], (
            "Production modules must consume `jarvis.tools` only:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
