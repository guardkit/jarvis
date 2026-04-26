"""Tests for TASK-J003-013 — extended ``build_supervisor`` signature.

Acceptance criteria covered (cross-referenced to the task file):

    AC-001: ``build_supervisor`` adds two keyword-only parameters
            (``async_subagents``, ``ambient_tool_factory``) with safe
            defaults.
    AC-002: ``async_subagents=None`` does NOT inject the five
            ``AsyncSubAgentMiddleware`` operational tools into the
            supervisor's tool catalogue (scenario: *Building the supervisor
            without the async-subagents argument preserves existing behaviour*).
    AC-003: ``async_subagents=[<jarvis-reasoner>]`` causes the five
            middleware operational tools (``start_async_task``,
            ``check_async_task``, ``update_async_task``, ``cancel_async_task``,
            ``list_async_tasks``) to be present on the supervisor's tool
            catalogue (scenario: *Wiring the async subagent injects the
            five middleware operational tools*).
    AC-004: ``ambient_tool_factory=None`` resolves to the FEAT-J002
            ``assemble_tool_list(..., include_frontier=False)`` 9-tool
            baseline when invoked (scenario: *Not configuring an ambient
            tool factory falls back to the attended tools without frontier*).
    AC-005: ``ambient_tool_factory=<callable>`` is the canonical ambient
            tool list — its return value is what the supervisor exposes.
    AC-006: Phase 1 + FEAT-J002 backward compatibility — call sites that
            supply only ``tools=`` and ``available_capabilities=`` still
            return a valid ``CompiledStateGraph`` AND do not include the
            five middleware tools.
    AC-007: Signature is documented; new kwargs are keyword-only and
            sit *after* the FEAT-J002 kwargs.

Test layout follows the class-per-AC convention used by the rest of the
Phase 2/3 test suite. Network-free invariants are enforced by patching
``init_chat_model`` to return ``FakeListChatModel``; some tests further
wrap ``create_deep_agent`` via ``Mock(wraps=...)`` so the realised graph
can be inspected for tool-name presence/absence.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from jarvis.config.settings import JarvisConfig
from jarvis.tools import CapabilityDescriptor, load_stub_registry

# ---------------------------------------------------------------------------
# Constants — the five DeepAgents AsyncSubAgentMiddleware operational
# tool names.  Mirrored from the upstream ``deepagents.middleware.async_subagents``
# module so this test acts as a contract check on the wiring we depend on.
# ---------------------------------------------------------------------------
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
    """Return the absolute path to the canonical 4-entry stub YAML."""
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists(), f"Expected stub registry at {stub_path}"
    return stub_path


@pytest.fixture()
def capability_registry() -> list[CapabilityDescriptor]:
    """Return the 4-entry capability registry loaded from the stub YAML."""
    descriptors = load_stub_registry(_stub_registry_path())
    assert len(descriptors) == 4
    return descriptors


@pytest.fixture()
def jarvis_reasoner_subagent() -> dict[str, str]:
    """Return a single AsyncSubAgent spec mirroring ``build_async_subagents``.

    Uses a literal dict (TypedDict-compatible) so this test does not
    introduce a hard dependency on the ``subagent_registry`` module —
    the registry is asserted by its own test suite.
    """
    return {
        "name": "jarvis-reasoner",
        "description": (
            "Local Jarvis reasoning subagent backed by the gpt-oss-120b "
            "model running on the premises (no network egress)."
        ),
        "graph_id": "jarvis_reasoner",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_tool_names(graph: CompiledStateGraph[Any, Any, Any, Any]) -> set[str]:
    """Walk a compiled DeepAgents graph and return the set of tool names.

    Mirrors the helper used in ``tests/test_supervisor_with_tools.py`` so
    introspection stays consistent across the integration suites.
    """
    seen: set[str] = set()
    nodes_attr = getattr(graph, "nodes", None) or {}
    iterable: list[Any] = (
        list(nodes_attr.values()) if isinstance(nodes_attr, dict) else list(nodes_attr)
    )

    for node in iterable:
        for candidate in (node, getattr(node, "runnable", None), getattr(node, "bound", None)):
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
# AC-001 / AC-007 — signature shape
# ---------------------------------------------------------------------------
class TestAC001SignatureShape:
    """``build_supervisor`` accepts the two new keyword-only parameters."""

    def test_async_subagents_is_keyword_only_with_default_none(self) -> None:
        """``async_subagents`` is keyword-only and defaults to ``None``."""
        from jarvis.agents.supervisor import build_supervisor

        sig = inspect.signature(build_supervisor)
        assert "async_subagents" in sig.parameters
        param = sig.parameters["async_subagents"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.default is None

    def test_ambient_tool_factory_is_keyword_only_with_default_none(self) -> None:
        """``ambient_tool_factory`` is keyword-only and defaults to ``None``."""
        from jarvis.agents.supervisor import build_supervisor

        sig = inspect.signature(build_supervisor)
        assert "ambient_tool_factory" in sig.parameters
        param = sig.parameters["ambient_tool_factory"]
        assert param.kind == inspect.Parameter.KEYWORD_ONLY
        assert param.default is None

    def test_phase2_kwargs_still_present(self) -> None:
        """The FEAT-J002 kwargs survive — additions did not displace them."""
        from jarvis.agents.supervisor import build_supervisor

        sig = inspect.signature(build_supervisor)
        for name in ("tools", "available_capabilities"):
            assert name in sig.parameters, f"FEAT-J002 kwarg {name!r} missing"
            assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
            assert sig.parameters[name].default is None

    def test_kwargs_appear_after_feat_j002_kwargs(self) -> None:
        """The new kwargs sit after ``available_capabilities`` in the signature."""
        from jarvis.agents.supervisor import build_supervisor

        params = list(inspect.signature(build_supervisor).parameters)
        idx = {name: params.index(name) for name in params}
        assert idx["available_capabilities"] < idx["async_subagents"]
        assert idx["async_subagents"] < idx["ambient_tool_factory"]

    def test_docstring_documents_new_kwargs(self) -> None:
        """The docstring mentions the two new kwargs by name."""
        from jarvis.agents.supervisor import build_supervisor

        doc = inspect.getdoc(build_supervisor) or ""
        assert "async_subagents" in doc
        assert "ambient_tool_factory" in doc


# ---------------------------------------------------------------------------
# AC-002 / AC-006 — async_subagents=None preserves FEAT-J002 behaviour
# ---------------------------------------------------------------------------
class TestAC002NoAsyncSubagentsByDefault:
    """``async_subagents=None`` does NOT inject the five middleware tools."""

    def test_subagents_kwarg_is_empty_list_when_none(self, test_config: JarvisConfig) -> None:
        """``create_deep_agent`` receives ``subagents=[]`` when caller omits async."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            build_supervisor(test_config, tools=[], available_capabilities=[])

        _, kwargs = mock_create.call_args
        assert "subagents" in kwargs
        assert kwargs["subagents"] == []

    def test_compiled_graph_omits_async_middleware_tools(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """No async-task operational tool appears on the compiled graph."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
            )

        wired = _extract_tool_names(graph)
        leaked = wired & ASYNC_MIDDLEWARE_TOOL_NAMES
        assert not leaked, (
            f"async_subagents=None must NOT inject the middleware tools; "
            f"found {sorted(leaked)!r} on the compiled graph."
        )


# ---------------------------------------------------------------------------
# AC-003 — async_subagents=[reasoner] injects the five middleware tools
# ---------------------------------------------------------------------------
class TestAC003AsyncSubagentInjectsMiddlewareTools:
    """Wiring a single AsyncSubAgent injects the five operational tools."""

    def test_subagents_kwarg_carries_supplied_async_specs(
        self,
        test_config: JarvisConfig,
        jarvis_reasoner_subagent: dict[str, str],
    ) -> None:
        """``create_deep_agent`` receives the async-subagent list verbatim."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
                async_subagents=[jarvis_reasoner_subagent],
            )

        _, kwargs = mock_create.call_args
        assert "subagents" in kwargs
        assert kwargs["subagents"] == [jarvis_reasoner_subagent]

    def test_compiled_graph_exposes_five_middleware_tools(
        self,
        test_config: JarvisConfig,
        jarvis_reasoner_subagent: dict[str, str],
        fake_llm: Any,
    ) -> None:
        """All five async-middleware tool names appear on the compiled graph."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
                async_subagents=[jarvis_reasoner_subagent],
            )

        wired = _extract_tool_names(graph)
        missing = ASYNC_MIDDLEWARE_TOOL_NAMES - wired
        assert not missing, (
            f"async_subagents=[reasoner] must inject all five middleware "
            f"tools; missing {sorted(missing)!r}; got {sorted(wired)!r}"
        )


# ---------------------------------------------------------------------------
# AC-004 — ambient_tool_factory=None falls back to assemble_tool_list(...,
#          include_frontier=False)
# ---------------------------------------------------------------------------
class TestAC004AmbientFactoryDefault:
    """``ambient_tool_factory=None`` resolves to the include_frontier=False fallback."""

    def test_default_factory_is_attached_when_none(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """The compiled graph carries an ambient-factory attribute (callable)."""
        from jarvis.agents.supervisor import (
            AMBIENT_TOOL_FACTORY_ATTR,
            build_supervisor,
        )

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
            )

        factory = getattr(graph, AMBIENT_TOOL_FACTORY_ATTR, None)
        assert factory is not None, (
            "build_supervisor must attach a default ambient-tool factory "
            "when the caller passes ambient_tool_factory=None."
        )
        assert callable(factory)

    def test_default_factory_invokes_assemble_tool_list_without_frontier(
        self,
        test_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        fake_llm: Any,
    ) -> None:
        """The default factory delegates to ``assemble_tool_list(include_frontier=False)``."""
        from jarvis.agents.supervisor import (
            AMBIENT_TOOL_FACTORY_ATTR,
            build_supervisor,
        )

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=capability_registry,
            )

        factory = getattr(graph, AMBIENT_TOOL_FACTORY_ATTR)

        # Patch the lazy import inside the closure to verify the kwargs
        # flow; the closure imports ``assemble_tool_list`` via
        # ``from jarvis.tools import ...`` so we patch it on that module.
        with patch("jarvis.tools.assemble_tool_list") as mock_assemble:
            mock_assemble.return_value = []
            result = factory()

        assert result == []
        mock_assemble.assert_called_once()
        _, kwargs = mock_assemble.call_args
        assert kwargs.get("include_frontier") is False, (
            "The default ambient factory must call assemble_tool_list with "
            "include_frontier=False so the ambient surface excludes "
            "escalate_to_frontier (DDR-014 registration-layer gate)."
        )

    def test_default_factory_returns_real_ambient_list_excluding_frontier(
        self,
        test_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        fake_llm: Any,
    ) -> None:
        """End-to-end: the default factory returns a list that omits ``escalate_to_frontier``."""
        from jarvis.agents.supervisor import (
            AMBIENT_TOOL_FACTORY_ATTR,
            build_supervisor,
        )

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=capability_registry,
            )

        factory = getattr(graph, AMBIENT_TOOL_FACTORY_ATTR)
        ambient_tools = factory()
        names = {t.name for t in ambient_tools}

        assert "escalate_to_frontier" not in names, (
            "Ambient surface must exclude escalate_to_frontier per DDR-014."
        )
        # FEAT-J002 9-tool baseline survives.
        for expected in ("calculate", "search_web", "read_file", "queue_build"):
            assert expected in names, (
                f"Ambient surface must contain FEAT-J002 tool {expected!r}; got {sorted(names)!r}"
            )


# ---------------------------------------------------------------------------
# AC-005 — ambient_tool_factory supplied: factory return value is canonical
# ---------------------------------------------------------------------------
class TestAC005AmbientFactorySupplied:
    """A caller-supplied ``ambient_tool_factory`` is the canonical ambient list."""

    def test_supplied_factory_is_attached_verbatim(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """The caller's factory object is the one attached to the graph."""
        from jarvis.agents.supervisor import (
            AMBIENT_TOOL_FACTORY_ATTR,
            build_supervisor,
        )

        sentinel_tools: list[BaseTool] = []
        marker = object()

        def my_factory() -> list[BaseTool]:
            # The marker proves identity; the empty list is the contract.
            my_factory.__dict__.setdefault("_marker", marker)
            return sentinel_tools

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
                ambient_tool_factory=my_factory,
            )

        attached = getattr(graph, AMBIENT_TOOL_FACTORY_ATTR, None)
        assert attached is my_factory, (
            "build_supervisor must attach the caller-supplied factory "
            "object verbatim (no wrapping) so identity is preserved."
        )

    def test_supplied_factory_return_value_is_canonical(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """Calling the attached factory yields the supplied list, unmodified."""
        from jarvis.agents.supervisor import (
            AMBIENT_TOOL_FACTORY_ATTR,
            build_supervisor,
        )

        canonical: list[BaseTool] = []  # empty list is the simplest sentinel

        def my_factory() -> list[BaseTool]:
            return canonical

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
                ambient_tool_factory=my_factory,
            )

        attached = getattr(graph, AMBIENT_TOOL_FACTORY_ATTR)
        assert attached() is canonical, (
            "build_supervisor must NOT wrap the supplied factory; the "
            "factory's return value must be the canonical ambient tool list."
        )

    def test_supplied_factory_does_not_call_assemble_tool_list(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """Supplying a factory short-circuits the ``assemble_tool_list`` fallback.

        Tests should call the factory once at most; build-time supervisor
        construction itself should NOT trigger the fallback path. This
        guards against a regression where build_supervisor eagerly
        invokes both factories.
        """
        from jarvis.agents.supervisor import build_supervisor

        my_factory = MagicMock(return_value=[])

        with (
            patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm),
            patch("jarvis.tools.assemble_tool_list") as mock_assemble,
        ):
            build_supervisor(
                test_config,
                tools=[],
                available_capabilities=[],
                ambient_tool_factory=my_factory,
            )

        # Neither factory should fire at build time — the factory is
        # invoked lazily by ambient consumers.
        my_factory.assert_not_called()
        mock_assemble.assert_not_called()


# ---------------------------------------------------------------------------
# AC-006 — Phase 1 + FEAT-J002 backward compatibility
# ---------------------------------------------------------------------------
class TestAC006BackwardCompatibility:
    """Existing callers continue to receive a valid ``CompiledStateGraph``."""

    def test_phase1_call_site_still_returns_compiled_graph(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """``build_supervisor(config)`` (Phase 1) returns a CompiledStateGraph."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(test_config)

        assert isinstance(graph, CompiledStateGraph)

    def test_feat_j002_call_site_still_returns_compiled_graph(
        self,
        test_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        fake_llm: Any,
    ) -> None:
        """``build_supervisor(config, tools=…, available_capabilities=…)`` works."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=capability_registry,
            )

        assert isinstance(graph, CompiledStateGraph)

    def test_feat_j002_call_site_omits_async_middleware_tools(
        self,
        test_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        fake_llm: Any,
    ) -> None:
        """FEAT-J002 callers (no async_subagents) get the FEAT-J002 surface only."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(
                test_config,
                tools=[],
                available_capabilities=capability_registry,
            )

        wired = _extract_tool_names(graph)
        leaked = wired & ASYNC_MIDDLEWARE_TOOL_NAMES
        assert not leaked, (
            "FEAT-J002 backward-compat invariant violated: the FEAT-J002 "
            f"call site exposed middleware tools {sorted(leaked)!r}."
        )
