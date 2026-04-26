"""Tests for ``jarvis.agents.subagents.jarvis_reasoner`` — compiled subagent graph.

Covers TASK-J003-008 acceptance criteria:

- AC-001 — module-level ``graph: CompiledStateGraph`` exposed at import.
- AC-002 — first node resolves ``input["role"]`` against ``ROLE_PROMPTS``.
- AC-003 — ``OPENAI_BASE_URL`` is *not* hard-coded in this module.
- AC-004 — unknown role surfaces ``ERROR: unknown_role — …``; never raises.
- AC-005 — empty-string role flows onto the ``unknown_role`` branch
  (``RoleName("")`` ``ValueError`` caught).
- AC-006 — missing role field surfaces ``ERROR: missing_field — role is required``.
- AC-007 — empty prompt surfaces ``ERROR: missing_field — prompt is required``.
- AC-008 — adapter-level failure surfaces a structured error mentioning
  the ``/running`` endpoint.
- AC-009 — leaf graph: every inner ``create_deep_agent`` call uses
  ``tools=[]`` and ``subagents=[]``.
- AC-010 — module performs no LLM network call at import.
- AC-011 — ``correlation_id`` from input propagates to the
  ``async_tasks`` output channel.

Tests deliberately avoid invoking the real model — error-path scenarios
short-circuit at the ``resolve_role`` node before any dispatcher runs,
and adapter-level failure scenarios patch the inner deep-agent's
``ainvoke`` to raise a synthetic exception.
"""

from __future__ import annotations

import asyncio
import importlib
import re
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_fresh_reasoner_module() -> Any:
    """Re-import ``jarvis.agents.subagents.jarvis_reasoner`` from scratch.

    Used by tests that need to assert build-time wiring (e.g. patched
    ``init_chat_model`` / ``create_deep_agent`` calls). Drops any cached
    copy from ``sys.modules`` first so the module body re-executes.
    """
    sys.modules.pop("jarvis.agents.subagents.jarvis_reasoner", None)
    return importlib.import_module("jarvis.agents.subagents.jarvis_reasoner")


# ---------------------------------------------------------------------------
# AC-001 — module-level ``graph`` is a CompiledStateGraph at import
# ---------------------------------------------------------------------------
class TestAC001GraphCompiledAtImport:
    """``from … import graph`` returns a compiled graph without further init."""

    def test_graph_is_compiled_state_graph(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        assert isinstance(graph, CompiledStateGraph)

    def test_graph_is_module_level_attribute(self) -> None:
        from jarvis.agents.subagents import jarvis_reasoner as mod

        assert hasattr(mod, "graph")
        assert isinstance(mod.graph, CompiledStateGraph)

    def test_module_exports_graph_via___all__(self) -> None:
        from jarvis.agents.subagents import jarvis_reasoner as mod

        assert "graph" in getattr(mod, "__all__", [])

    def test_reasoner_model_constant_is_provider_prefixed(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import REASONER_MODEL

        # Must be ``provider:model`` so init_chat_model can route via
        # OPENAI_BASE_URL → llama-swap.
        assert REASONER_MODEL.startswith("openai:")
        assert REASONER_MODEL == "openai:jarvis-reasoner"


# ---------------------------------------------------------------------------
# AC-002 — first node resolves input[role] against ROLE_PROMPTS
# ---------------------------------------------------------------------------
class TestAC002FirstNodeResolvesRole:
    """``_resolve_role`` looks role values up in :data:`ROLE_PROMPTS`."""

    @pytest.mark.parametrize(
        "role_value",
        ["critic", "researcher", "planner"],
    )
    def test_known_role_value_does_not_emit_error(self, role_value: str) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import _resolve_role

        delta = _resolve_role(
            {"role": role_value, "prompt": "hello", "correlation_id": "cid-1"}
        )

        assert "error" not in delta
        assert delta.get("resolved_role") == role_value

    def test_resolve_role_uses_role_prompts_registry(self) -> None:
        # Smoke check: ROLE_PROMPTS must cover the same RoleName members the
        # resolver consumes; if a future DDR drops a role, this is the
        # earliest point to surface the breakage.
        from jarvis.agents.subagents.prompts import ROLE_PROMPTS
        from jarvis.agents.subagents.types import RoleName

        for member in RoleName:
            assert member in ROLE_PROMPTS
            assert ROLE_PROMPTS[member].strip()


# ---------------------------------------------------------------------------
# AC-003 — OPENAI_BASE_URL is not hard-coded in this module
# ---------------------------------------------------------------------------
class TestAC003NoHardCodedBaseUrl:
    """The module body never references a literal llama-swap URL.

    The supervisor lifecycle exports ``OPENAI_BASE_URL`` from
    ``config.llama_swap_base_url`` before any dispatch lands. This module
    must therefore stay URL-free so a future re-host of llama-swap does
    not require touching the subagent.
    """

    def test_module_source_has_no_llama_swap_url_literal(self) -> None:
        src_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "agents"
            / "subagents"
            / "jarvis_reasoner.py"
        )
        source = src_path.read_text(encoding="utf-8")

        # Strip the module docstring so docstring mentions of
        # ``OPENAI_BASE_URL`` (for documentation) don't trip the literal
        # check — the constraint is about *runtime* code, not prose.
        executable = re.sub(r'"""[\s\S]*?"""', "", source, count=1)

        # Forbid any host:port literal that looks like the llama-swap
        # default in executable code.
        assert "promaxgb10" not in executable
        assert "9000/v1" not in executable
        # Forbid any literal http URL in executable code.
        assert not re.search(r'"http://', executable)
        assert not re.search(r"'http://", executable)

    def test_module_does_not_set_environment_variable(self) -> None:
        src_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "agents"
            / "subagents"
            / "jarvis_reasoner.py"
        )
        source = src_path.read_text(encoding="utf-8")

        # Active assignment to os.environ is forbidden — only the
        # supervisor lifecycle owns that side-effect.
        assert "os.environ[" not in source
        assert "os.environ.setdefault" not in source
        assert "os.putenv" not in source


# ---------------------------------------------------------------------------
# AC-004 — unknown role returns structured error; never raises
# ---------------------------------------------------------------------------
class TestAC004UnknownRoleStructuredError:
    """Unknown role values surface ``ERROR: unknown_role …`` on ``async_tasks``."""

    UNKNOWN_RE: re.Pattern[str] = re.compile(
        r"ERROR: unknown_role — expected one of \{critic, researcher, planner\}, got=.+"
    )

    @pytest.mark.parametrize(
        "bad_role",
        ["bard", "CRITIC", "Critic", "adversarial", "deep_reasoner"],
    )
    def test_unknown_role_returns_structured_error(self, bad_role: str) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke(
            {"role": bad_role, "prompt": "hello", "correlation_id": "cid-1"}
        )

        async_tasks = result.get("async_tasks") or []
        assert async_tasks, "expected structured error on async_tasks channel"
        assert async_tasks[0]["output"].startswith(
            "ERROR: unknown_role"
        ), async_tasks[0]
        assert self.UNKNOWN_RE.match(async_tasks[0]["output"]) is not None
        # Echoed value uses repr() so the operator can spot whitespace
        # / case mismatches at a glance.
        assert repr(bad_role) in async_tasks[0]["output"]

    def test_unknown_role_never_raises(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        # Must not raise — ADR-ARCH-021.
        graph.invoke({"role": "bard", "prompt": "hello"})


# ---------------------------------------------------------------------------
# AC-005 — empty-string role flows onto unknown_role branch
# ---------------------------------------------------------------------------
class TestAC005EmptyStringRoleMapsToUnknownRole:
    """``RoleName("")`` raises ``ValueError`` → caught → ``unknown_role``."""

    def test_empty_role_produces_unknown_role_error(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke({"role": "", "prompt": "hello"})

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert async_tasks[0]["output"].startswith("ERROR: unknown_role")
        assert "got=''" in async_tasks[0]["output"]

    def test_empty_role_never_raises(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        # ASSUM-004 — RoleName("") raises ValueError, the graph catches.
        graph.invoke({"role": "", "prompt": "hello"})


# ---------------------------------------------------------------------------
# AC-006 — missing role field returns structured error
# ---------------------------------------------------------------------------
class TestAC006MissingRoleField:
    """Missing ``role`` key surfaces ``ERROR: missing_field — role is required``."""

    def test_missing_role_returns_structured_error(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke({"prompt": "hello", "correlation_id": "cid-2"})

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert (
            async_tasks[0]["output"]
            == "ERROR: missing_field — role is required"
        )

    def test_none_role_returns_structured_error(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke({"role": None, "prompt": "hello"})

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert (
            async_tasks[0]["output"]
            == "ERROR: missing_field — role is required"
        )


# ---------------------------------------------------------------------------
# AC-007 — empty prompt returns structured error
# ---------------------------------------------------------------------------
class TestAC007EmptyPromptStructuredError:
    """Empty / missing prompt surfaces ``ERROR: missing_field — prompt is required``."""

    def test_empty_prompt_returns_structured_error(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke({"role": "critic", "prompt": ""})

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert (
            async_tasks[0]["output"]
            == "ERROR: missing_field — prompt is required"
        )

    def test_missing_prompt_returns_structured_error(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke({"role": "critic"})

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert (
            async_tasks[0]["output"]
            == "ERROR: missing_field — prompt is required"
        )


# ---------------------------------------------------------------------------
# AC-008 — adapter-level failure surfaces /running mention
# ---------------------------------------------------------------------------
class TestAC008LlamaSwapAliasMissing:
    """A failing inner ``ainvoke`` translates into an adapter error mention."""

    def test_dispatch_failure_mentions_running_endpoint(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import _make_role_runner
        from jarvis.agents.subagents.types import RoleName

        # Synthetic deep agent whose ainvoke raises — emulates a missing
        # llama-swap alias surfaced by the adapter layer.
        failing_agent = MagicMock()

        async def _boom(*_args: Any, **_kwargs: Any) -> Any:
            raise RuntimeError("alias 'jarvis-reasoner' not in /running response")

        failing_agent.ainvoke = _boom

        runner = _make_role_runner(RoleName.CRITIC, failing_agent)
        delta = asyncio.run(
            runner({"prompt": "hello", "correlation_id": "cid-3"})
        )

        async_tasks = delta.get("async_tasks") or []
        assert async_tasks
        output = async_tasks[0]["output"]
        assert "/running" in output
        assert "llama_swap_unavailable" in output
        # Correlation id propagated through to the failure path too.
        assert async_tasks[0]["correlation_id"] == "cid-3"


# ---------------------------------------------------------------------------
# AC-009 — leaf graph: tools=[], subagents=[]
# ---------------------------------------------------------------------------
class TestAC009LeafGraphInvariants:
    """Every inner ``create_deep_agent`` call uses ``tools=[]`` / ``subagents=[]``."""

    def test_create_deep_agent_called_per_role_with_empty_tools(self) -> None:
        # Patch the *source* modules ``deepagents`` and
        # ``langchain.chat_models`` so the ``from … import …`` statements
        # at the top of jarvis_reasoner.py pick up the mocks during the
        # forced reimport below. Patching the importer module's names
        # would race the reload (``from-import`` rebinds those names).
        sys.modules.pop("jarvis.agents.subagents.jarvis_reasoner", None)
        with (
            patch("langchain.chat_models.init_chat_model") as mock_init,
            patch("deepagents.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            importlib.import_module("jarvis.agents.subagents.jarvis_reasoner")

            assert mock_create.call_count == 3, (
                f"expected exactly one create_deep_agent call per RoleName, "
                f"got {mock_create.call_count}"
            )
            for call in mock_create.call_args_list:
                _, kwargs = call
                assert kwargs.get("tools") == []
                assert kwargs.get("subagents") == []
                # System prompt must come from ROLE_PROMPTS — non-empty,
                # non-template (no ``{placeholder}``).
                prompt = kwargs.get("system_prompt")
                assert isinstance(prompt, str)
                assert prompt.strip()
                assert "{" not in prompt or "}" not in prompt

    def test_create_deep_agent_called_with_each_role_prompt(self) -> None:
        from jarvis.agents.subagents.prompts import ROLE_PROMPTS
        from jarvis.agents.subagents.types import RoleName

        sys.modules.pop("jarvis.agents.subagents.jarvis_reasoner", None)
        with (
            patch("langchain.chat_models.init_chat_model") as mock_init,
            patch("deepagents.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            importlib.import_module("jarvis.agents.subagents.jarvis_reasoner")

            seen_prompts = {
                call.kwargs.get("system_prompt") for call in mock_create.call_args_list
            }
            expected_prompts = {ROLE_PROMPTS[r] for r in RoleName}
            assert seen_prompts == expected_prompts


# ---------------------------------------------------------------------------
# AC-010 — no LLM network call at import
# ---------------------------------------------------------------------------
class TestAC010NoNetworkCallAtImport:
    """Importing the module never invokes a chat model."""

    def test_no_invoke_called_on_chat_model_at_import(self) -> None:
        sys.modules.pop("jarvis.agents.subagents.jarvis_reasoner", None)
        with (
            patch("langchain.chat_models.init_chat_model") as mock_init,
            patch("deepagents.create_deep_agent") as mock_create,
        ):
            fake_model = MagicMock()
            mock_init.return_value = fake_model
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            importlib.import_module("jarvis.agents.subagents.jarvis_reasoner")

            # Construction must never have called the model.
            fake_model.invoke.assert_not_called()
            fake_model.ainvoke.assert_not_called()
            fake_model.stream.assert_not_called()
            fake_model.astream.assert_not_called()
            fake_model.predict.assert_not_called()

    def test_init_chat_model_called_with_reasoner_alias(self) -> None:
        sys.modules.pop("jarvis.agents.subagents.jarvis_reasoner", None)
        with (
            patch("langchain.chat_models.init_chat_model") as mock_init,
            patch("deepagents.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = MagicMock()
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            importlib.import_module("jarvis.agents.subagents.jarvis_reasoner")

            mock_init.assert_called_once_with("openai:jarvis-reasoner")


# ---------------------------------------------------------------------------
# AC-011 — correlation_id propagates to async_tasks output
# ---------------------------------------------------------------------------
class TestAC011CorrelationIdPropagates:
    """``correlation_id`` from input flows through to the output channel."""

    def test_correlation_id_propagates_through_unknown_role_branch(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke(
            {
                "role": "bard",
                "prompt": "hello",
                "correlation_id": "00000000-0000-0000-0000-deadbeef0001",
            }
        )

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert (
            async_tasks[0]["correlation_id"]
            == "00000000-0000-0000-0000-deadbeef0001"
        )

    def test_correlation_id_propagates_through_missing_role_branch(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke(
            {
                "prompt": "hello",
                "correlation_id": "cid-missing-role",
            }
        )

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert async_tasks[0]["correlation_id"] == "cid-missing-role"

    def test_correlation_id_propagates_through_empty_prompt_branch(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke(
            {"role": "critic", "prompt": "", "correlation_id": "cid-empty-prompt"}
        )

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert async_tasks[0]["correlation_id"] == "cid-empty-prompt"

    def test_missing_correlation_id_is_none_not_raised(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        # Absent correlation_id is permitted (AsyncTaskInput allows None).
        result = graph.invoke({"role": "bard", "prompt": "hello"})

        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert async_tasks[0]["correlation_id"] is None
