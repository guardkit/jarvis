"""Integration test for TASK-J002-022 — supervisor-with-tools + nine-tool wiring + prompt injection.

Acceptance criteria covered (cross-referenced to the task file):

    AC-001: ``tests/test_supervisor_with_tools.py`` creates ``test_config`` +
            4-entry ``capability_registry`` fixtures; calls
            ``build_app_state(test_config)``.
    AC-002: Asserts the compiled ``supervisor`` graph exposes exactly the 9
            tool names in alphabetical order:
            ``calculate, capabilities_refresh, capabilities_subscribe_updates,
            dispatch_by_capability, get_calendar_events,
            list_available_capabilities, queue_build, read_file, search_web``.
    AC-003: Asserts the rendered system prompt contains the
            ``{available_capabilities}`` block built from the 4 descriptors —
            each ``as_prompt_block()`` substring appears verbatim.
    AC-004: Asserts empty-registry path:
            ``build_supervisor(test_config, tools=[], available_capabilities=[])``
            renders the ``"No capabilities currently registered."`` sentinel.
    AC-005: No LLM call is made (FakeListChatModel or equivalent); no network.
    AC-006: Phase 1 test modules (``tests/test_supervisor.py``,
            ``tests/test_supervisor_no_llm_call.py``, ``tests/test_sessions.py``,
            ``tests/test_config.py``, ``tests/test_infrastructure.py``,
            ``tests/test_prompts.py``) all still pass unchanged — this file
            adds tests only and does not modify any Phase 1 module.
    AC-007: Coverage of ``src/jarvis/tools/`` >= 80% — verified externally by
            ``pytest --cov=src/jarvis/tools``; this file exercises every
            tool-package public surface (assemble_tool_list, the 9 tool
            names, the prompt-block rendering, the empty-registry fallback)
            so coverage is contributed.

Test layout follows the class-per-AC convention used by the rest of the
Phase 2 test suite.  Network-free invariants are enforced by:

* ``init_chat_model`` is patched to return a ``FakeListChatModel`` (the
  canonical ``fake_llm`` fixture) so no provider client is ever constructed.
* ``create_deep_agent`` is wrapped (not replaced) via ``Mock(wraps=...)`` so
  the *real* compiled graph is still produced — letting the 9-tool wiring
  and the prompt injection both be asserted against the real artefact while
  the kwargs the factory received remain inspectable for the prompt-content
  checks.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from langgraph.graph.state import CompiledStateGraph

from jarvis.config.settings import JarvisConfig
from jarvis.tools import CapabilityDescriptor, load_stub_registry

# ---------------------------------------------------------------------------
# Module constants — the attended Jarvis tool surface in stable
# alphabetical order. Mirrors ``jarvis.tools.assemble_tool_list``'s
# contract; duplicating the list here is intentional so the test acts as
# a contract check on that module.
#
# TASK-J003-012 (Layer 3 of DDR-014) splices ``escalate_to_frontier``
# alongside the FEAT-J002 9-tool baseline whenever
# ``include_frontier=True`` (the default). ``lifecycle.startup`` calls
# ``assemble_tool_list`` without overriding the flag, so the supervisor
# wired here is the attended 10-tool surface.
# ---------------------------------------------------------------------------
EXPECTED_TOOL_NAMES: list[str] = [
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _stub_registry_path() -> Path:
    """Return the absolute path to the canonical 4-entry stub YAML.

    The autouse ``_isolate_dotenv`` fixture chdirs each test into ``tmp_path``,
    which means a relative ``stub_capabilities_path`` would not resolve to the
    real document.  We point the field at the absolute path under the source
    tree so the loader can read it without further patching.
    """
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists(), f"Expected stub registry at {stub_path}"
    return stub_path


@pytest.fixture()
def stub_registry_config() -> JarvisConfig:
    """``JarvisConfig`` whose ``stub_capabilities_path`` is the 4-entry stub.

    Provider key validation is satisfied via the OpenAI base URL — the
    ``test_config`` shape used in conftest, but with the stub registry path
    pinned absolutely so ``build_app_state`` can find it.
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
    """Return the 4-entry capability registry loaded from the stub YAML.

    AC-001 calls for a 4-entry fixture; loading it from the canonical stub
    keeps this fixture in sync with the bundled registry the supervisor
    uses in production.
    """
    descriptors = load_stub_registry(_stub_registry_path())
    assert len(descriptors) == 4, (
        f"Expected 4-entry stub registry; got {len(descriptors)} — "
        "the canonical stub must remain at 4 entries for AC-001."
    )
    return descriptors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_tool_names(graph: CompiledStateGraph[Any, Any, Any, Any]) -> set[str]:
    """Walk a compiled DeepAgents graph and return the set of tool names.

    The compiled graph composes a ``ToolNode`` whose ``tools_by_name`` mapping
    keys are the tool names exposed to the model.  We probe the graph's
    ``nodes`` mapping for any node whose runnable surfaces a
    ``tools_by_name`` attribute and union the keys we find.

    Mirrors ``tests/test_supervisor_lifecycle_wiring.py::_extract_tool_names``
    so the two integration suites stay introspectionally consistent.
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
# AC-001 / AC-002 — build_app_state wires 9 tools in alphabetical order
# ---------------------------------------------------------------------------
class TestAC001NineToolWiring:
    """``build_app_state(test_config)`` produces a supervisor with 9 wired tools."""

    @pytest.mark.asyncio
    async def test_compiled_supervisor_exposes_nine_tool_names(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """Each of the 9 Phase 2 tool names is present on the compiled graph."""
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        wired_tool_names = _extract_tool_names(state.supervisor)
        missing = [name for name in EXPECTED_TOOL_NAMES if name not in wired_tool_names]
        assert not missing, (
            f"Expected the 9 Phase 2 tools wired into the supervisor, "
            f"missing={missing!r}; got {sorted(wired_tool_names)!r}"
        )

    @pytest.mark.asyncio
    async def test_create_deep_agent_receives_nine_tools_alphabetically(
        self,
        stub_registry_config: JarvisConfig,
        fake_llm: Any,
    ) -> None:
        """``create_deep_agent`` is invoked with exactly the 9 tools in alphabetical order."""
        from jarvis.agents import supervisor as supervisor_module
        from jarvis.infrastructure.lifecycle import build_app_state

        real_create_deep_agent = supervisor_module.create_deep_agent

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
            patch(
                "jarvis.agents.supervisor.create_deep_agent",
                wraps=real_create_deep_agent,
            ) as mock_create,
        ):
            await build_app_state(stub_registry_config)

        _, kwargs = mock_create.call_args
        passed_tools = kwargs["tools"]
        passed_names = [getattr(t, "name", None) for t in passed_tools]
        assert passed_names == EXPECTED_TOOL_NAMES, (
            f"Expected create_deep_agent to receive the 9 tools in alphabetical "
            f"order; got {passed_names!r}"
        )

    def test_assemble_tool_list_is_alphabetical(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
    ) -> None:
        """Direct contract check on ``assemble_tool_list`` — attended 10-tool surface."""
        from jarvis.tools import assemble_tool_list

        tools = assemble_tool_list(stub_registry_config, capability_registry)
        names = [t.name for t in tools]
        assert names == EXPECTED_TOOL_NAMES
        # TASK-J003-012: ``include_frontier`` defaults to True so the
        # attended supervisor is wired with the 10-tool surface.
        assert len(tools) == 10


# ---------------------------------------------------------------------------
# AC-003 — rendered system prompt contains every descriptor's as_prompt_block
# ---------------------------------------------------------------------------
class TestAC003CapabilityBlockInjection:
    """The system prompt rendered by ``build_app_state`` contains every block."""

    @pytest.mark.asyncio
    async def test_each_descriptor_block_appears_verbatim_in_system_prompt(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        fake_llm: Any,
    ) -> None:
        """Every descriptor's ``as_prompt_block()`` substring appears verbatim."""
        from jarvis.agents import supervisor as supervisor_module
        from jarvis.infrastructure.lifecycle import build_app_state

        real_create_deep_agent = supervisor_module.create_deep_agent

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
            patch(
                "jarvis.agents.supervisor.create_deep_agent",
                wraps=real_create_deep_agent,
            ) as mock_create,
        ):
            await build_app_state(stub_registry_config)

        _, kwargs = mock_create.call_args
        system_prompt = kwargs["system_prompt"]
        assert isinstance(system_prompt, str) and system_prompt
        # Sanity: no raw template placeholders survived format() rendering.
        assert "{available_capabilities}" not in system_prompt
        assert "{date}" not in system_prompt
        assert "{domain_prompt}" not in system_prompt

        # Each of the 4 descriptors' rendered block appears verbatim.
        assert len(capability_registry) == 4
        for descriptor in capability_registry:
            block = descriptor.as_prompt_block()
            assert block in system_prompt, (
                f"Descriptor block for {descriptor.agent_id!r} not found verbatim "
                f"in the rendered system prompt — prompt was:\n{system_prompt}"
            )

    @pytest.mark.asyncio
    async def test_blocks_appear_in_alphabetical_agent_id_order(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        fake_llm: Any,
    ) -> None:
        """Blocks render in deterministic ascending ``agent_id`` order."""
        from jarvis.agents import supervisor as supervisor_module
        from jarvis.infrastructure.lifecycle import build_app_state

        real_create_deep_agent = supervisor_module.create_deep_agent

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
            patch(
                "jarvis.agents.supervisor.create_deep_agent",
                wraps=real_create_deep_agent,
            ) as mock_create,
        ):
            await build_app_state(stub_registry_config)

        _, kwargs = mock_create.call_args
        system_prompt = kwargs["system_prompt"]

        # Sort descriptors by agent_id and check render order matches.
        ordered = sorted(capability_registry, key=lambda d: d.agent_id)
        positions = [system_prompt.index(d.as_prompt_block()) for d in ordered]
        assert positions == sorted(positions), (
            f"Capability blocks must render in ascending agent_id order; "
            f"got positions {positions!r} for ids {[d.agent_id for d in ordered]!r}"
        )


# ---------------------------------------------------------------------------
# AC-004 — empty-registry path renders the safe sentinel
# ---------------------------------------------------------------------------
class TestAC004EmptyRegistryFallback:
    """``build_supervisor`` with an empty registry renders the L305 sentinel."""

    _SENTINEL: str = "No capabilities currently registered."

    def test_empty_registry_renders_sentinel(
        self, test_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """Empty registry call to ``build_supervisor`` injects the L305 sentinel.

        Calls ``build_supervisor(test_config, tools=[], available_capabilities=[])``
        and asserts the rendered system prompt contains the sentinel string.
        """
        from jarvis.agents import supervisor as supervisor_module
        from jarvis.agents.supervisor import build_supervisor

        real_create_deep_agent = supervisor_module.create_deep_agent

        with (
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
            patch(
                "jarvis.agents.supervisor.create_deep_agent",
                wraps=real_create_deep_agent,
            ) as mock_create,
        ):
            graph = build_supervisor(test_config, tools=[], available_capabilities=[])

        assert isinstance(graph, CompiledStateGraph)
        _, kwargs = mock_create.call_args
        system_prompt = kwargs["system_prompt"]
        assert self._SENTINEL in system_prompt, (
            f"Empty registry must render the L305 sentinel verbatim — "
            f"prompt did not contain {self._SENTINEL!r}"
        )
        # And no descriptor block leaks through when the registry is empty.
        assert (
            "### " not in system_prompt or "Tools:" not in system_prompt.split(self._SENTINEL, 1)[0]
        ), (
            "Sentinel should replace the capability block entirely, but a "
            "descriptor-style header appeared before the sentinel."
        )


# ---------------------------------------------------------------------------
# AC-005 — no LLM call is made; no network
# ---------------------------------------------------------------------------
class TestAC005NoLLMCallNoNetwork:
    """``FakeListChatModel`` (or equivalent) is used; build performs no .invoke.

    We can't naively wrap the chat model in ``MagicMock(wraps=fake_llm)`` —
    DeepAgents' ``resolve_model`` short-circuits with
    ``isinstance(model, BaseChatModel)`` and the Mock proxy is not a
    ``BaseChatModel`` subclass, so it falls through to ``_get_harness_profile``
    which calls ``.partition(":")`` and explodes. Instead we lean on the
    fact that ``FakeListChatModel`` exposes an ``i`` cursor that increments
    on every invocation: the cursor stays at 0 iff no model call happened
    during build. Combined with ``init_chat_model`` being patched (no real
    provider client constructed) this proves the no-network invariant.
    """

    @pytest.mark.asyncio
    async def test_fake_llm_response_cursor_remains_at_zero(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """``FakeListChatModel.i`` is unchanged after ``build_app_state``."""
        from langchain_core.language_models.fake_chat_models import FakeListChatModel

        from jarvis.infrastructure.lifecycle import build_app_state

        # Sanity: the conftest fixture is a real FakeListChatModel.
        assert isinstance(fake_llm, FakeListChatModel)
        assert fake_llm.i == 0, "FakeListChatModel cursor must start at 0"

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ) as mock_init_chat_model,
        ):
            state = await build_app_state(stub_registry_config)

        # ``init_chat_model`` is the only provider-construction seam — proving
        # it was patched proves no real provider client was instantiated.
        mock_init_chat_model.assert_called_once_with(stub_registry_config.supervisor_model)

        # ``FakeListChatModel.i`` advances on every call; staying at 0 means
        # no .invoke / .ainvoke / .stream / .astream happened during build.
        assert fake_llm.i == 0, (
            f"FakeListChatModel was invoked during build — cursor advanced to "
            f"{fake_llm.i}. build_app_state must not consume tokens."
        )
        assert isinstance(state.supervisor, CompiledStateGraph)
