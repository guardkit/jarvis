"""Integration test for TASK-J003-021 — supervisor + subagents + ambient/attended surfaces.

Acceptance criteria covered (cross-referenced to the task file):

    AC-001: ``tests/test_supervisor_with_subagents.py`` builds the supervisor
            via ``build_supervisor(test_config, tools=<FEAT-J002 set>,
            async_subagents=build_async_subagents(test_config),
            ambient_tool_factory=lambda: assemble_tool_list(test_config,
            capability_registry, include_frontier=False))`` and asserts the
            return is a :class:`CompiledStateGraph`.
    AC-002: The supervisor's tool catalogue includes all FEAT-J002 tools
            (no regression).
    AC-003: The supervisor's tool catalogue includes the five
            ``AsyncSubAgentMiddleware`` operational tools (``start_async_task``,
            ``check_async_task``, ``update_async_task``, ``cancel_async_task``,
            ``list_async_tasks``).
    AC-004: Attended tool list (``include_frontier=True``) contains
            ``escalate_to_frontier``.
    AC-005: Ambient tool list (``include_frontier=False``) excludes
            ``escalate_to_frontier`` AND contains all FEAT-J002 tools.
    AC-006: Backward-compat — ``build_supervisor(test_config,
            tools=<FEAT-J002 set>)`` (no ``async_subagents``) returns a valid
            ``CompiledStateGraph`` without the five middleware tools.
    AC-007: ``FakeListChatModel``; zero LLM network calls.
    AC-008: ``uv run pytest tests/test_supervisor_with_subagents.py -v`` passes
            with ≥ 80% coverage on the new test module (verified externally).

Test layout follows the class-per-AC convention used by the rest of the
Phase 2/3 test suite.  Network-free invariants are enforced by patching
``init_chat_model`` to return ``FakeListChatModel`` so no provider client is
ever constructed; the ``FakeListChatModel.i`` cursor (which advances on every
invocation) is asserted to remain at ``0`` so we know no model call was made
during build.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from jarvis.config.settings import JarvisConfig
from jarvis.tools import CapabilityDescriptor, assemble_tool_list, load_stub_registry

# ---------------------------------------------------------------------------
# Module constants — the FEAT-J002 9-tool baseline (the surface that
# survived from Phase 2) plus the FEAT-J003 attended 10th tool.
#
# These are duplicated here on purpose: the integration test acts as a
# contract check on :mod:`jarvis.tools` — if either set drifts, this
# file must be updated alongside the production list.
# ---------------------------------------------------------------------------
FEAT_J002_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "calculate",
        "capabilities_refresh",
        "capabilities_subscribe_updates",
        "dispatch_by_capability",
        "get_calendar_events",
        "list_available_capabilities",
        "queue_build",
        "read_file",
        "search_web",
    }
)

ATTENDED_FRONTIER_TOOL: str = "escalate_to_frontier"

# The five DeepAgents ``AsyncSubAgentMiddleware`` operational tool names —
# automatically injected when the supervisor is built with a non-empty
# ``async_subagents=`` list.
ASYNC_MIDDLEWARE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "start_async_task",
        "check_async_task",
        "update_async_task",
        "cancel_async_task",
        "list_async_tasks",
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _stub_registry_path() -> Path:
    """Return the absolute path to the canonical 4-entry stub YAML.

    Mirrors the helper in ``test_supervisor_with_tools.py`` — the autouse
    ``_isolate_dotenv`` fixture chdirs each test into ``tmp_path``, so a
    relative path would not resolve to the real document.
    """
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists(), f"Expected stub registry at {stub_path}"
    return stub_path


@pytest.fixture()
def stub_registry_config() -> JarvisConfig:
    """``JarvisConfig`` whose ``stub_capabilities_path`` is the 4-entry stub.

    Provider key validation is satisfied via the OpenAI base URL (matching
    the conftest ``test_config`` shape) but with the stub registry path
    pinned absolutely so tests that depend on capability descriptors can
    load them.
    """
    stub_path = _stub_registry_path()
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def capability_registry() -> list[CapabilityDescriptor]:
    """Return the 4-entry capability registry loaded from the stub YAML."""
    descriptors = load_stub_registry(_stub_registry_path())
    assert len(descriptors) == 4, (
        f"Expected 4-entry stub registry; got {len(descriptors)} — "
        "the canonical stub must remain at 4 entries for this integration."
    )
    return descriptors


@pytest.fixture()
def feat_j002_tools(
    stub_registry_config: JarvisConfig,
    capability_registry: list[CapabilityDescriptor],
) -> list[BaseTool]:
    """Return the FEAT-J002 attended 10-tool surface.

    This is the ``tools=`` argument the supervisor is wired with in the
    AC-001 build path. ``include_frontier=True`` (the default) so the
    attended tool list contains ``escalate_to_frontier`` (AC-004).
    """
    return assemble_tool_list(
        stub_registry_config,
        capability_registry,
        include_frontier=True,
    )


@pytest.fixture()
def feat_j002_tools_ambient(
    stub_registry_config: JarvisConfig,
    capability_registry: list[CapabilityDescriptor],
) -> list[BaseTool]:
    """Return the FEAT-J002 ambient 9-tool surface (no frontier escalation)."""
    return assemble_tool_list(
        stub_registry_config,
        capability_registry,
        include_frontier=False,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_tool_names(graph: CompiledStateGraph[Any, Any, Any, Any]) -> set[str]:
    """Walk a compiled DeepAgents graph and return the set of tool names.

    Mirrors the helpers used in ``tests/test_supervisor_with_tools.py``
    and ``tests/test_supervisor_extended_signature.py`` so introspection
    stays consistent across the integration suites.
    """
    seen: set[str] = set()
    nodes_attr = getattr(graph, "nodes", None) or {}
    iterable: list[Any] = (
        list(nodes_attr.values()) if isinstance(nodes_attr, dict) else list(nodes_attr)
    )

    for node in iterable:
        for candidate in (
            node,
            getattr(node, "runnable", None),
            getattr(node, "bound", None),
        ):
            if candidate is None:
                continue
            tools_by_name = getattr(candidate, "tools_by_name", None)
            if isinstance(tools_by_name, dict):
                seen.update(tools_by_name.keys())
            tools_attr = getattr(candidate, "tools", None)
            if isinstance(tools_attr, (list, tuple)):
                for t in tools_attr:
                    name = getattr(t, "name", None)
                    if isinstance(name, str):
                        seen.add(name)
    return seen


# ---------------------------------------------------------------------------
# AC-001 — Build invocation returns a CompiledStateGraph
# ---------------------------------------------------------------------------
class TestAC001SupervisorBuild:
    """``build_supervisor(...)`` with subagents and ambient factory returns a graph."""

    def test_build_supervisor_with_subagents_returns_compiled_state_graph(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """Full FEAT-J003 build path returns a :class:`CompiledStateGraph`.

        Combines:

        - ``tools=`` — the FEAT-J002 attended 10-tool surface.
        - ``async_subagents=`` — the local ``jarvis-reasoner`` AsyncSubAgent
          spec (the single entry returned by
          :func:`build_async_subagents`).
        - ``ambient_tool_factory=`` — a closure that returns
          :func:`assemble_tool_list` with ``include_frontier=False`` so
          ambient consumers see the 9-tool baseline.
        """
        from jarvis.agents.subagent_registry import build_async_subagents
        from jarvis.agents.supervisor import build_supervisor

        async_subagents = build_async_subagents(stub_registry_config)
        ambient_tool_factory = lambda: assemble_tool_list(  # noqa: E731
            stub_registry_config,
            capability_registry,
            include_frontier=False,
        )

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
                async_subagents=async_subagents,
                ambient_tool_factory=ambient_tool_factory,
            )

        assert isinstance(graph, CompiledStateGraph), (
            "build_supervisor must return a CompiledStateGraph when wired "
            "with tools, async_subagents and an ambient_tool_factory."
        )


# ---------------------------------------------------------------------------
# AC-002 — supervisor tool catalogue includes all FEAT-J002 tools
# ---------------------------------------------------------------------------
class TestAC002FeatJ002ToolsPresent:
    """The compiled supervisor exposes every FEAT-J002 baseline tool."""

    def test_compiled_graph_exposes_all_feat_j002_tool_names(
        self,
        stub_registry_config: JarvisConfig,
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """All 9 FEAT-J002 tool names appear on the compiled supervisor graph."""
        from jarvis.agents.subagent_registry import build_async_subagents
        from jarvis.agents.supervisor import build_supervisor

        async_subagents = build_async_subagents(stub_registry_config)

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
                async_subagents=async_subagents,
            )

        wired = _extract_tool_names(graph)
        missing = FEAT_J002_TOOL_NAMES - wired
        assert not missing, (
            f"FEAT-J002 regression: the supervisor tool catalogue is missing "
            f"{sorted(missing)!r}; wired tools were {sorted(wired)!r}"
        )


# ---------------------------------------------------------------------------
# AC-003 — wiring async subagents injects the five middleware tools
# ---------------------------------------------------------------------------
class TestAC003AsyncMiddlewareToolsInjected:
    """Wiring ``async_subagents=build_async_subagents(config)`` injects the five tools."""

    def test_compiled_graph_exposes_all_five_async_middleware_tools(
        self,
        stub_registry_config: JarvisConfig,
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """All five ``AsyncSubAgentMiddleware`` operational tools are present."""
        from jarvis.agents.subagent_registry import build_async_subagents
        from jarvis.agents.supervisor import build_supervisor

        async_subagents = build_async_subagents(stub_registry_config)

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
                async_subagents=async_subagents,
            )

        wired = _extract_tool_names(graph)
        missing = ASYNC_MIDDLEWARE_TOOL_NAMES - wired
        assert not missing, (
            f"async_subagents=build_async_subagents(config) must inject all "
            f"five middleware operational tools (start_async_task, "
            f"check_async_task, update_async_task, cancel_async_task, "
            f"list_async_tasks); missing {sorted(missing)!r}; "
            f"got {sorted(wired)!r}"
        )


# ---------------------------------------------------------------------------
# AC-004 — attended tool list contains escalate_to_frontier
# ---------------------------------------------------------------------------
class TestAC004AttendedListContainsFrontier:
    """``assemble_tool_list(..., include_frontier=True)`` contains the escape hatch."""

    def test_attended_list_contains_escalate_to_frontier(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
    ) -> None:
        """The attended tool list (frontier=True) exposes ``escalate_to_frontier``."""
        attended = assemble_tool_list(
            stub_registry_config,
            capability_registry,
            include_frontier=True,
        )
        names = {t.name for t in attended}

        assert ATTENDED_FRONTIER_TOOL in names, (
            f"Attended tool list must contain {ATTENDED_FRONTIER_TOOL!r} "
            f"(DDR-014 attended-only escape hatch); got {sorted(names)!r}"
        )
        # And the FEAT-J002 baseline survives alongside the escalation.
        for expected in FEAT_J002_TOOL_NAMES:
            assert expected in names, (
                f"Attended tool list must also retain FEAT-J002 tool "
                f"{expected!r}; got {sorted(names)!r}"
            )

    def test_attended_supervisor_exposes_escalate_to_frontier(
        self,
        stub_registry_config: JarvisConfig,
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """The compiled attended supervisor exposes ``escalate_to_frontier``."""
        from jarvis.agents.subagent_registry import build_async_subagents
        from jarvis.agents.supervisor import build_supervisor

        async_subagents = build_async_subagents(stub_registry_config)

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
                async_subagents=async_subagents,
            )

        wired = _extract_tool_names(graph)
        assert ATTENDED_FRONTIER_TOOL in wired, (
            f"Attended supervisor must expose {ATTENDED_FRONTIER_TOOL!r}; got {sorted(wired)!r}"
        )


# ---------------------------------------------------------------------------
# AC-005 — ambient tool list excludes escalate_to_frontier and retains
#          the FEAT-J002 9-tool baseline
# ---------------------------------------------------------------------------
class TestAC005AmbientListExcludesFrontier:
    """``assemble_tool_list(..., include_frontier=False)`` is the ambient surface."""

    def test_ambient_list_excludes_escalate_to_frontier(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
    ) -> None:
        """The ambient tool list MUST NOT contain ``escalate_to_frontier``."""
        ambient = assemble_tool_list(
            stub_registry_config,
            capability_registry,
            include_frontier=False,
        )
        names = {t.name for t in ambient}

        assert ATTENDED_FRONTIER_TOOL not in names, (
            f"Ambient tool list MUST NOT contain {ATTENDED_FRONTIER_TOOL!r} "
            f"(DDR-014 registration-layer gate); got {sorted(names)!r}"
        )

    def test_ambient_list_contains_all_feat_j002_tools(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
    ) -> None:
        """The ambient list still exposes every FEAT-J002 baseline tool."""
        ambient = assemble_tool_list(
            stub_registry_config,
            capability_registry,
            include_frontier=False,
        )
        names = {t.name for t in ambient}

        missing = FEAT_J002_TOOL_NAMES - names
        assert not missing, (
            f"Ambient tool list must retain the full FEAT-J002 9-tool "
            f"baseline; missing {sorted(missing)!r}; got {sorted(names)!r}"
        )

    def test_ambient_list_has_exactly_nine_tools(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
    ) -> None:
        """The ambient list is the FEAT-J002 9-tool surface (no more, no less)."""
        ambient = assemble_tool_list(
            stub_registry_config,
            capability_registry,
            include_frontier=False,
        )
        assert len(ambient) == 9, (
            f"Ambient tool list must be exactly the FEAT-J002 9-tool "
            f"surface; got {len(ambient)} tools: "
            f"{sorted(t.name for t in ambient)!r}"
        )

    def test_ambient_factory_attached_to_compiled_graph(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """The supplied ``ambient_tool_factory`` is attached to the graph verbatim.

        Lifecycle/learning consumers retrieve the canonical ambient list by
        calling ``graph._jarvis_ambient_tool_factory()``; the supervisor must
        therefore hand back the caller-supplied closure exactly so calling
        it produces a 9-tool list excluding ``escalate_to_frontier``.
        """
        from jarvis.agents.subagent_registry import build_async_subagents
        from jarvis.agents.supervisor import (
            AMBIENT_TOOL_FACTORY_ATTR,
            build_supervisor,
        )

        async_subagents = build_async_subagents(stub_registry_config)
        ambient_tool_factory = lambda: assemble_tool_list(  # noqa: E731
            stub_registry_config,
            capability_registry,
            include_frontier=False,
        )

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
                async_subagents=async_subagents,
                ambient_tool_factory=ambient_tool_factory,
            )

        attached_factory = getattr(graph, AMBIENT_TOOL_FACTORY_ATTR, None)
        assert attached_factory is ambient_tool_factory, (
            "The caller-supplied ambient_tool_factory must be attached to "
            "the compiled graph by identity (no wrapping)."
        )

        ambient_tools = attached_factory()
        ambient_names = {t.name for t in ambient_tools}
        assert ATTENDED_FRONTIER_TOOL not in ambient_names, (
            f"The ambient factory must yield a list that excludes "
            f"{ATTENDED_FRONTIER_TOOL!r}; got {sorted(ambient_names)!r}"
        )
        assert ambient_names >= FEAT_J002_TOOL_NAMES, (
            f"The ambient factory's list must contain the full FEAT-J002 "
            f"baseline; got {sorted(ambient_names)!r}"
        )


# ---------------------------------------------------------------------------
# AC-006 — backward-compat: build_supervisor without async_subagents
# ---------------------------------------------------------------------------
class TestAC006BackwardCompatNoAsyncSubagents:
    """``build_supervisor(config, tools=…)`` (no async_subagents) preserves FEAT-J002 surface."""

    def test_build_without_async_subagents_returns_compiled_graph(
        self,
        stub_registry_config: JarvisConfig,
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """Omitting ``async_subagents`` still yields a valid :class:`CompiledStateGraph`."""
        from jarvis.agents.supervisor import build_supervisor

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
            )

        assert isinstance(graph, CompiledStateGraph), (
            "build_supervisor without async_subagents must still return "
            "a valid CompiledStateGraph (FEAT-J002 backward compatibility)."
        )

    def test_build_without_async_subagents_omits_middleware_tools(
        self,
        stub_registry_config: JarvisConfig,
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """Omitting ``async_subagents`` must not inject the five middleware tools."""
        from jarvis.agents.supervisor import build_supervisor

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
            )

        wired = _extract_tool_names(graph)
        leaked = wired & ASYNC_MIDDLEWARE_TOOL_NAMES
        assert not leaked, (
            f"FEAT-J002 backward-compat invariant violated: building the "
            f"supervisor without async_subagents leaked the middleware "
            f"tools {sorted(leaked)!r} into the catalogue."
        )

    def test_build_without_async_subagents_retains_feat_j002_tools(
        self,
        stub_registry_config: JarvisConfig,
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """The FEAT-J002 9-tool baseline survives the no-async-subagent path."""
        from jarvis.agents.supervisor import build_supervisor

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ):
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
            )

        wired = _extract_tool_names(graph)
        missing = FEAT_J002_TOOL_NAMES - wired
        assert not missing, (
            f"FEAT-J002 baseline tools must survive the no-async-subagent "
            f"build path; missing {sorted(missing)!r}; "
            f"got {sorted(wired)!r}"
        )


# ---------------------------------------------------------------------------
# AC-007 — FakeListChatModel; zero LLM network calls
# ---------------------------------------------------------------------------
class TestAC007NoLLMNetworkCall:
    """``FakeListChatModel`` is used; build performs no ``.invoke`` / ``.ainvoke``.

    We assert the no-network invariant via two complementary mechanisms:

    1. ``init_chat_model`` is patched to return ``FakeListChatModel`` so no
       real provider client is ever instantiated.
    2. ``FakeListChatModel.i`` (the response-cursor) starts at 0 and only
       advances on each invocation; staying at 0 after build proves no
       ``.invoke`` / ``.ainvoke`` / ``.stream`` / ``.astream`` happened.
    """

    def test_fake_llm_response_cursor_remains_at_zero(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        feat_j002_tools: list[BaseTool],
        fake_llm: Any,
    ) -> None:
        """Build path performs no LLM call — ``FakeListChatModel.i`` stays at 0."""
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        from jarvis.agents.subagent_registry import build_async_subagents
        from jarvis.agents.supervisor import build_supervisor

        # Sanity: the conftest fixture is a real FakeListChatModel.
        assert isinstance(fake_llm, FakeListChatModel)
        assert fake_llm.i == 0, "FakeListChatModel cursor must start at 0"

        async_subagents = build_async_subagents(stub_registry_config)
        ambient_tool_factory = lambda: assemble_tool_list(  # noqa: E731
            stub_registry_config,
            capability_registry,
            include_frontier=False,
        )

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_llm,
        ) as mock_init_chat_model:
            graph = build_supervisor(
                stub_registry_config,
                tools=feat_j002_tools,
                async_subagents=async_subagents,
                ambient_tool_factory=ambient_tool_factory,
            )

        # ``init_chat_model`` is the only provider-construction seam — proving
        # it was patched proves no real provider client was instantiated.
        mock_init_chat_model.assert_called_once_with(stub_registry_config.supervisor_model)

        # ``FakeListChatModel.i`` advances on every model call; staying at 0
        # means no ``.invoke`` / ``.ainvoke`` / ``.stream`` / ``.astream``
        # happened during build_supervisor.
        assert fake_llm.i == 0, (
            f"FakeListChatModel was invoked during build — cursor advanced "
            f"to {fake_llm.i}. build_supervisor must not consume tokens."
        )
        assert isinstance(graph, CompiledStateGraph)
