"""Tests for TASK-J002-017 — extend build_supervisor signature + lifecycle wiring.

Acceptance criteria covered (cross-referenced to the task file):

    AC-001: build_supervisor gains keyword-only kwargs ``tools`` and
            ``available_capabilities``; Phase 1 callers (no kwargs) still work.
    AC-002: ``available_capabilities`` None or empty renders the exact fallback
            string ``"No capabilities currently registered."``
            (per ``feat-jarvis-002...feature`` L305).
    AC-003: A non-empty registry is rendered via ``CapabilityDescriptor.as_prompt_block()``
            in deterministic ``agent_id`` order, joined with ``\\n\\n``.
    AC-004: ``tools`` None passes ``tools=[]`` to ``create_deep_agent``.
    AC-005: ``build_app_state`` loads the stub registry, assembles the tool list,
            and forwards both into ``build_supervisor`` via the new kwargs.
    AC-006: ``AppState`` gains a ``capability_registry: list[CapabilityDescriptor]``
            field.
    AC-007: Startup with the 4-entry stub registry completes in under 2 seconds
            (no network).
    AC-008: Seam test — ``build_app_state(test_config)`` returns an ``AppState``
            whose ``supervisor`` has 9 tools wired and ``capability_registry``
            has 4 entries.

The lint/format AC (AC-009) is verified externally via ``ruff`` /
``ruff format`` and is not asserted here.
"""

from __future__ import annotations

import dataclasses
import io
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from jarvis.config.settings import JarvisConfig
from jarvis.tools import CapabilityDescriptor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def descriptor_alpha() -> CapabilityDescriptor:
    """Return the 'alpha' descriptor used to assert deterministic ordering."""
    return CapabilityDescriptor(
        agent_id="alpha-agent",
        role="Alpha",
        description="First agent for ordering tests.",
    )


@pytest.fixture()
def descriptor_bravo() -> CapabilityDescriptor:
    """Return the 'bravo' descriptor used to assert deterministic ordering."""
    return CapabilityDescriptor(
        agent_id="bravo-agent",
        role="Bravo",
        description="Second agent for ordering tests.",
    )


@pytest.fixture()
def descriptor_charlie() -> CapabilityDescriptor:
    """Return the 'charlie' descriptor used to assert deterministic ordering."""
    return CapabilityDescriptor(
        agent_id="charlie-agent",
        role="Charlie",
        description="Third agent for ordering tests.",
    )


@pytest.fixture()
def stub_registry_config(tmp_path: Path) -> JarvisConfig:
    """Return a ``JarvisConfig`` whose ``stub_capabilities_path`` resolves to
    the canonical 4-entry stub document.

    The autouse ``_isolate_dotenv`` fixture chdirs each test into ``tmp_path``,
    which means a relative ``stub_capabilities_path`` would not resolve to the
    real document.  We point the field at the absolute path under the source
    tree so the loader can read it without further patching.
    """
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists(), f"Expected stub registry at {stub_path}"

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
        )
    cfg.validate_provider_keys()
    return cfg


# ---------------------------------------------------------------------------
# AC-001 — build_supervisor signature gains keyword-only kwargs
# ---------------------------------------------------------------------------
class TestAC001SupervisorSignature:
    """``build_supervisor`` accepts ``tools`` and ``available_capabilities``."""

    def test_signature_exposes_keyword_only_tools(self) -> None:
        """``tools`` is a keyword-only parameter."""
        import inspect

        from jarvis.agents.supervisor import build_supervisor

        sig = inspect.signature(build_supervisor)
        assert "tools" in sig.parameters
        assert sig.parameters["tools"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["tools"].default is None

    def test_signature_exposes_keyword_only_available_capabilities(self) -> None:
        """``available_capabilities`` is a keyword-only parameter."""
        import inspect

        from jarvis.agents.supervisor import build_supervisor

        sig = inspect.signature(build_supervisor)
        assert "available_capabilities" in sig.parameters
        assert sig.parameters["available_capabilities"].kind is inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["available_capabilities"].default is None

    def test_phase_1_callers_unaffected(self, test_config: JarvisConfig, fake_llm: Any) -> None:
        """Calling ``build_supervisor(config)`` with no kwargs still returns a graph."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(test_config)
        assert isinstance(graph, CompiledStateGraph)


# ---------------------------------------------------------------------------
# AC-002 — empty / None registry renders the safe fallback string
# ---------------------------------------------------------------------------
class TestAC002EmptyCapabilitiesFallback:
    """Empty / None registry renders the L305 fallback verbatim."""

    _EXPECTED_FALLBACK = "No capabilities currently registered."

    def test_none_capabilities_renders_fallback(self, test_config: JarvisConfig) -> None:
        """``available_capabilities=None`` injects the L305 fallback string."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config, available_capabilities=None)

        _, kwargs = mock_create.call_args
        prompt = kwargs["system_prompt"]
        assert self._EXPECTED_FALLBACK in prompt

    def test_empty_capabilities_renders_fallback(self, test_config: JarvisConfig) -> None:
        """``available_capabilities=[]`` also injects the fallback string."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config, available_capabilities=[])

        _, kwargs = mock_create.call_args
        prompt = kwargs["system_prompt"]
        assert self._EXPECTED_FALLBACK in prompt


# ---------------------------------------------------------------------------
# AC-003 — non-empty registry renders deterministic prompt blocks
# ---------------------------------------------------------------------------
class TestAC003CapabilityBlockRendering:
    """Non-empty registry is rendered via ``as_prompt_block``, sorted by agent_id."""

    def test_blocks_rendered_via_as_prompt_block(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
    ) -> None:
        """Each descriptor's ``as_prompt_block()`` output appears in the prompt."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config, available_capabilities=[descriptor_alpha])

        _, kwargs = mock_create.call_args
        prompt = kwargs["system_prompt"]
        assert descriptor_alpha.as_prompt_block() in prompt

    def test_blocks_sorted_by_agent_id(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
        descriptor_charlie: CapabilityDescriptor,
    ) -> None:
        """Descriptors render in deterministic ascending ``agent_id`` order."""
        from jarvis.agents.supervisor import build_supervisor

        # Pass them in non-sorted order.
        registry = [descriptor_charlie, descriptor_alpha, descriptor_bravo]

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config, available_capabilities=registry)

        _, kwargs = mock_create.call_args
        prompt = kwargs["system_prompt"]

        idx_alpha = prompt.index(descriptor_alpha.as_prompt_block())
        idx_bravo = prompt.index(descriptor_bravo.as_prompt_block())
        idx_charlie = prompt.index(descriptor_charlie.as_prompt_block())
        assert idx_alpha < idx_bravo < idx_charlie

    def test_blocks_joined_with_double_newline(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        descriptor_bravo: CapabilityDescriptor,
    ) -> None:
        """Blocks are joined with the literal ``"\\n\\n"`` separator."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(
                test_config,
                available_capabilities=[descriptor_alpha, descriptor_bravo],
            )

        _, kwargs = mock_create.call_args
        prompt = kwargs["system_prompt"]
        expected = descriptor_alpha.as_prompt_block() + "\n\n" + descriptor_bravo.as_prompt_block()
        assert expected in prompt


# ---------------------------------------------------------------------------
# AC-004 — None tools => tools=[] passed to create_deep_agent
# ---------------------------------------------------------------------------
class TestAC004NoneToolsPassesEmptyList:
    """``tools=None`` preserves the Phase 1 ``tools=[]`` contract."""

    def test_none_tools_forwards_empty_list(self, test_config: JarvisConfig) -> None:
        """``tools=None`` is normalised to ``tools=[]`` at create_deep_agent."""
        from jarvis.agents.supervisor import build_supervisor

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config, tools=None)

        _, kwargs = mock_create.call_args
        assert kwargs["tools"] == []

    def test_explicit_tool_list_forwards_unchanged(self, test_config: JarvisConfig) -> None:
        """A non-None ``tools`` list reaches ``create_deep_agent`` intact."""
        from jarvis.agents.supervisor import build_supervisor

        fake_tool = MagicMock(spec=BaseTool)
        fake_tool.name = "fake_tool"

        with (
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config, tools=[fake_tool])

        _, kwargs = mock_create.call_args
        assert kwargs["tools"] == [fake_tool]


# ---------------------------------------------------------------------------
# AC-005 — build_app_state wires registry + tool list through to supervisor
# ---------------------------------------------------------------------------
class TestAC005LifecycleWiring:
    """``build_app_state`` calls ``load_stub_registry``, ``assemble_tool_list``,
    and forwards both into ``build_supervisor``."""

    @pytest.mark.asyncio
    async def test_load_stub_registry_called_with_configured_path(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """``build_app_state`` calls ``load_stub_registry(config.stub_capabilities_path)``."""
        from jarvis.infrastructure.lifecycle import build_app_state

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch("jarvis.infrastructure.lifecycle.load_stub_registry") as mock_load,
            patch(
                "jarvis.infrastructure.lifecycle.assemble_tool_list",
                return_value=[],
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            mock_load.return_value = []
            await build_app_state(stub_registry_config)

        mock_load.assert_called_once_with(stub_registry_config.stub_capabilities_path)

    @pytest.mark.asyncio
    async def test_assemble_tool_list_called_with_config_and_registry(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """``assemble_tool_list(config, registry, include_frontier=...)`` is the second seam.

        TASK-J003-015 (FEAT-JARVIS-003 design §8) extended this seam: the
        lifecycle now calls ``assemble_tool_list`` twice — once with
        ``include_frontier=True`` for the attended 10-tool surface and
        once with ``include_frontier=False`` for the ambient 9-tool
        surface (DDR-014 registration-layer gate).  Both calls receive
        ``(config, registry)`` positionally; only the ``include_frontier``
        kwarg differs.
        """
        from jarvis.infrastructure.lifecycle import build_app_state

        sentinel_registry = [MagicMock(spec=CapabilityDescriptor)]

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=sentinel_registry,
            ),
            patch("jarvis.infrastructure.lifecycle.assemble_tool_list") as mock_assemble,
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            mock_assemble.return_value = []
            await build_app_state(stub_registry_config)

        # Two calls — attended (include_frontier=True) and ambient (=False).
        assert mock_assemble.call_count == 2
        for call in mock_assemble.call_args_list:
            assert call.args == (stub_registry_config, sentinel_registry)
        flags = {call.kwargs.get("include_frontier") for call in mock_assemble.call_args_list}
        assert flags == {True, False}

    @pytest.mark.asyncio
    async def test_build_supervisor_called_with_tools_and_capabilities(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """The new kwargs flow through to ``build_supervisor``."""
        from jarvis.infrastructure.lifecycle import build_app_state

        sentinel_registry = [MagicMock(spec=CapabilityDescriptor)]
        sentinel_tools = [MagicMock(spec=BaseTool)]

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=sentinel_registry,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.assemble_tool_list",
                return_value=sentinel_tools,
            ),
            patch("jarvis.infrastructure.lifecycle.build_supervisor") as mock_build,
        ):
            mock_build.return_value = MagicMock()
            await build_app_state(stub_registry_config)

        # build_supervisor receives config positionally and our two new kwargs.
        args, kwargs = mock_build.call_args
        assert args == (stub_registry_config,)
        assert kwargs.get("tools") is sentinel_tools
        assert kwargs.get("available_capabilities") is sentinel_registry


# ---------------------------------------------------------------------------
# AC-006 — AppState carries a capability_registry field
# ---------------------------------------------------------------------------
class TestAC006AppStateCapabilityRegistry:
    """``AppState`` exposes a ``capability_registry`` field."""

    def test_field_present_on_dataclass(self) -> None:
        """``capability_registry`` is a declared dataclass field."""
        from jarvis.infrastructure.lifecycle import AppState

        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "capability_registry" in field_names

    @pytest.mark.asyncio
    async def test_app_state_capability_registry_populated_from_loader(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """The registry returned by the loader is stored on AppState."""
        from jarvis.infrastructure.lifecycle import build_app_state

        sentinel_registry = [MagicMock(spec=CapabilityDescriptor)]

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=sentinel_registry,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.assemble_tool_list",
                return_value=[],
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.capability_registry == sentinel_registry


# ---------------------------------------------------------------------------
# AC-007 — startup completes in under 2 seconds with the 4-entry stub
# ---------------------------------------------------------------------------
class TestAC007StartupPerformance:
    """Startup with the real 4-entry stub registry is fast (<2s, no network)."""

    @pytest.mark.asyncio
    async def test_startup_under_two_seconds(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """``build_app_state`` returns within 2 seconds for the stub config."""
        from jarvis.infrastructure.lifecycle import build_app_state

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
        ):
            start = time.perf_counter()
            state = await build_app_state(stub_registry_config)
            elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"startup took {elapsed:.3f}s, must be under 2s"
        assert state.supervisor is not None


# ---------------------------------------------------------------------------
# AC-008 — Seam test — supervisor has 9 tools and registry has 4 entries
# ---------------------------------------------------------------------------
class TestAC008Seam:
    """``build_app_state(test_config)`` returns a fully-wired AppState."""

    @pytest.mark.asyncio
    async def test_supervisor_has_nine_tools_and_registry_has_four_entries(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """End-to-end seam: 9 wired tools, 4 capability entries."""
        from jarvis.infrastructure.lifecycle import build_app_state

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        # The 4-entry stub registry shipped at
        # src/jarvis/config/stub_capabilities.yaml.
        assert len(state.capability_registry) == 4

        # 9 Phase 2 tools wired into the supervisor.  The compiled DeepAgents
        # graph exposes tool names via the ``tools_by_name`` middleware
        # configuration; we tolerate either the fast attribute path or a
        # walk of the graph nodes.
        wired_tool_names = _extract_tool_names(state.supervisor)
        expected = {
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
        assert expected.issubset(wired_tool_names), (
            f"Expected the 9 Phase 2 tools wired into the supervisor, got "
            f"{sorted(wired_tool_names)!r}"
        )


def _extract_tool_names(graph: CompiledStateGraph[Any, Any, Any, Any]) -> set[str]:
    """Walk a compiled DeepAgents graph and return the set of tool names.

    The compiled graph composes a ``ToolNode`` whose ``tools_by_name`` mapping
    keys are the tool names exposed to the model.  We probe the graph's
    ``nodes`` mapping for any node whose runnable surfaces a
    ``tools_by_name`` attribute and union the keys we find.
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
