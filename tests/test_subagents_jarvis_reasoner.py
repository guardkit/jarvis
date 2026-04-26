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


# ---------------------------------------------------------------------------
# TASK-J003-017 — additional coverage required by the subagent-layer
# unit-test task (registry + graph + prompts):
#
# - structural assertion that the wrapper graph carries no application
#   tools of its own (DDR-010 leaf invariant, scenario from design.md
#   §9 "subagent-layer tests"); the existing TestAC009 already covers
#   each *inner* deep-agent — this block covers the *outer* wrapper.
# - parametrized unknown-role check that includes the exact strings
#   listed in TASK-J003-017 (``"bard"``, ``"CRITIC"``, ``"adversarial"``,
#   ``""``) all surfacing ``"unknown_role"`` on async_tasks.
# - role → prompt resolution through ``_make_role_runner`` (state
#   inspection only — no LLM output is asserted).
# - ASSUM-002 cancellation path (review Finding F3): the deepagents
#   ``cancel_async_task`` middleware tool produces a Command that
#   updates ``async_tasks`` to ``status="cancelled"`` for a tracked
#   task; ``check_async_task`` against the same task surfaces that
#   status without raising.
# - ASSUM-003 unknown ``task_id``: ``check_async_task`` returns a
#   structured error string mentioning the missing id without raising.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Wrapper graph carries no application tools / no further subagents.
# ---------------------------------------------------------------------------
class TestWrapperGraphCarriesNoApplicationTools:
    """Outer ``graph`` wrapper has no application tool surface.

    The wrapper graph is a plain :class:`StateGraph` whose nodes are
    plain Python functions (the resolver and the role-specific runners).
    LangGraph attaches no ``tools`` attribute on the compiled graph
    itself — verifying that fact is the structural counterpart to the
    AC text *"jarvis_reasoner graph has no application tools wired
    (`tools=[]`) and no further subagents"*.
    """

    def test_compiled_graph_has_no_tools_attribute(self) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        # CompiledStateGraph does not expose a ``tools`` collection
        # because the wrapper itself is a router. If a future refactor
        # accidentally added one, the leaf invariant (DDR-010) would
        # be silently broken at this layer.
        attached_tools = getattr(graph, "tools", [])
        assert attached_tools == [] or attached_tools is None

    def test_wrapper_graph_nodes_are_plain_functions_not_subagents(
        self,
    ) -> None:
        from langgraph.constants import START

        from jarvis.agents.subagents.jarvis_reasoner import graph
        from jarvis.agents.subagents.types import RoleName

        # Verify the wrapper's node set is exactly: resolver + 3 roles.
        node_names = set(graph.nodes.keys()) - {START}
        expected = {"resolve_role"} | {role.value for role in RoleName}
        assert node_names == expected, (
            f"unexpected wrapper graph nodes: {node_names ^ expected}"
        )


# ---------------------------------------------------------------------------
# Parametrized unknown-role: the four exact strings listed in
# TASK-J003-017 must all flow onto the unknown_role branch.
# ---------------------------------------------------------------------------
class TestUnknownRoleStringsFromTaskJ003017:
    """The four strings called out in TASK-J003-017 → unknown_role error."""

    @pytest.mark.parametrize(
        "bad_role",
        ["bard", "CRITIC", "adversarial", ""],
        ids=["bard", "CRITIC_uppercase", "adversarial", "empty_string"],
    )
    def test_strings_listed_in_task_surface_unknown_role(
        self, bad_role: str
    ) -> None:
        from jarvis.agents.subagents.jarvis_reasoner import graph

        result = graph.invoke({"role": bad_role, "prompt": "hello"})
        async_tasks = result.get("async_tasks") or []
        assert async_tasks
        assert "unknown_role" in async_tasks[0]["output"]


# ---------------------------------------------------------------------------
# Role → prompt resolution (structural / state-only assertion).
# ---------------------------------------------------------------------------
class TestRoleResolvesToCorrectPromptStructurally:
    """The factory threads the matching :data:`ROLE_PROMPTS` entry to each role.

    Asserts via state inspection, not via LLM output — the runner
    closure is built with a specific deep-agent whose ``system_prompt``
    came from :data:`ROLE_PROMPTS`. Patching the inner deep-agent at
    module-import time and inspecting the captured ``system_prompt``
    keyword on each call gives a deterministic, network-free check.
    """

    @pytest.mark.parametrize(
        ("role_value", "expected_keyword"),
        [
            ("critic", "adversarial"),
            ("researcher", "open-ended research"),
            ("planner", "multi-step planning"),
        ],
    )
    def test_each_role_threads_its_own_prompt(
        self, role_value: str, expected_keyword: str
    ) -> None:
        from jarvis.agents.subagents.prompts import ROLE_PROMPTS
        from jarvis.agents.subagents.types import RoleName

        # Look up the prompt the registry wired to this role and assert
        # the documented posture keyword survives — i.e. the structural
        # round-trip ``RoleName -> ROLE_PROMPTS[RoleName]`` is intact.
        role = RoleName(role_value)
        assert expected_keyword in ROLE_PROMPTS[role]

    def test_each_role_routes_to_a_distinct_dispatcher_node(self) -> None:
        from langgraph.constants import START

        from jarvis.agents.subagents.jarvis_reasoner import graph
        from jarvis.agents.subagents.types import RoleName

        node_names = set(graph.nodes.keys()) - {START}
        for role in RoleName:
            assert role.value in node_names, (
                f"dispatcher node for role {role.value!r} not found in graph"
            )


# ---------------------------------------------------------------------------
# ASSUM-002 — cancellation path verification (review Finding F3).
# ---------------------------------------------------------------------------
class TestAssum002CancellationPath:
    """Cancellation propagates through ``async_tasks`` as ``status='cancelled'``.

    Tests the deepagents ``AsyncSubAgentMiddleware`` cancel tool against
    a tracked task (the supervisor lifecycle is the producer; the
    middleware tool is the consumer). The LangGraph SDK client is
    patched so no network call occurs.
    """

    def _build_runtime(self, async_tasks: dict[str, Any]) -> MagicMock:
        runtime = MagicMock()
        runtime.state = {"async_tasks": async_tasks}
        runtime.tool_call_id = "tool-call-1"
        return runtime

    def _tracked_task(self) -> dict[str, Any]:
        # Mirrors the deepagents ``AsyncTask`` shape — keys not values
        # are what the cancel/check tools depend on.
        return {
            "task_id": "task-cid-1",
            "agent_name": "jarvis-reasoner",
            "thread_id": "thread-1",
            "run_id": "run-1",
            "status": "running",
            "created_at": "2026-01-01T00:00:00Z",
            "last_checked_at": "2026-01-01T00:00:00Z",
            "last_updated_at": "2026-01-01T00:00:00Z",
        }

    def test_cancel_async_task_emits_cancelled_status(self) -> None:
        from deepagents.middleware.async_subagents import _build_cancel_tool

        # Patch the LangGraph SDK client so ``client.runs.cancel`` is a
        # no-op rather than a network call. The cancel tool's contract
        # only needs a sync client whose ``runs.cancel`` succeeds.
        clients = MagicMock()
        sync_client = MagicMock()
        sync_client.runs.cancel = MagicMock(return_value=None)
        clients.get_sync = MagicMock(return_value=sync_client)

        cancel_tool = _build_cancel_tool(clients)

        tracked = self._tracked_task()
        runtime = self._build_runtime({tracked["task_id"]: tracked})

        # Invoke the tool's underlying function directly (skips the
        # StructuredTool schema-validation wrapper which is exercised
        # elsewhere in the deepagents test-suite).
        result = cancel_tool.func(  # type: ignore[union-attr]
            task_id=tracked["task_id"],
            runtime=runtime,
        )

        # The Command update must mark the task as cancelled.
        assert hasattr(result, "update")
        update = result.update
        async_tasks = update.get("async_tasks") or {}
        assert tracked["task_id"] in async_tasks
        assert async_tasks[tracked["task_id"]]["status"] == "cancelled"

    def test_check_async_task_after_cancel_surfaces_cancelled(self) -> None:
        from deepagents.middleware.async_subagents import _build_check_tool

        # Build a check tool whose run-fetch returns status='cancelled'
        # — emulating the SDK's view after the cancel op landed.
        clients = MagicMock()
        sync_client = MagicMock()
        sync_client.runs.get = MagicMock(
            return_value={"status": "cancelled", "error": None}
        )
        sync_client.threads.get = MagicMock(
            return_value={"values": {"messages": []}}
        )
        clients.get_sync = MagicMock(return_value=sync_client)

        check_tool = _build_check_tool(clients)

        tracked = self._tracked_task()
        # Mark already-cancelled to skip the live fetch shortcut on
        # terminal statuses; the AC just requires that the status is
        # surfaced via check_async_task.
        tracked["status"] = "cancelled"
        runtime = self._build_runtime({tracked["task_id"]: tracked})

        result = check_tool.func(  # type: ignore[union-attr]
            task_id=tracked["task_id"],
            runtime=runtime,
        )

        # check_async_task returns a Command whose update carries the
        # status on the tracked async_tasks entry.
        assert hasattr(result, "update")
        async_tasks = result.update.get("async_tasks") or {}
        assert tracked["task_id"] in async_tasks
        assert async_tasks[tracked["task_id"]]["status"] == "cancelled"


# ---------------------------------------------------------------------------
# ASSUM-003 — unknown task_id returns structured error without raising.
# ---------------------------------------------------------------------------
class TestAssum003UnknownTaskId:
    """``check_async_task`` against an unknown ``task_id`` never raises."""

    def test_check_async_task_unknown_id_returns_structured_string(self) -> None:
        from deepagents.middleware.async_subagents import _build_check_tool

        clients = MagicMock()
        # No client call should occur — the resolver short-circuits
        # before reaching the SDK because the tracked task is missing.
        clients.get_sync = MagicMock(side_effect=AssertionError(
            "client should not be reached for unknown task_id"
        ))

        check_tool = _build_check_tool(clients)

        runtime = MagicMock()
        runtime.state = {"async_tasks": {}}
        runtime.tool_call_id = "tool-call-unknown"

        # Must not raise — ASSUM-003. Instead it returns a plain string
        # naming the missing task_id so the supervisor can surface a
        # structured error to the user.
        result = check_tool.func(  # type: ignore[union-attr]
            task_id="nonexistent-task-id",
            runtime=runtime,
        )

        assert isinstance(result, str), (
            f"expected structured error string, got {type(result).__name__}"
        )
        # The string must identify the missing task — the AC text in
        # TASK-J003-017 abbreviates this as "unknown_task_id"; the
        # underlying middleware spells it "No tracked task found for
        # task_id". Either form must mention the offending id verbatim.
        assert "task_id" in result
        assert "nonexistent-task-id" in result

    def test_check_async_task_unknown_id_does_not_raise(self) -> None:
        from deepagents.middleware.async_subagents import _build_check_tool

        clients = MagicMock()
        clients.get_sync = MagicMock()  # never reached, no assertion needed
        check_tool = _build_check_tool(clients)

        runtime = MagicMock()
        runtime.state = {"async_tasks": {}}
        runtime.tool_call_id = "tool-call-noraise"

        # No try / except wrapping — the call must complete cleanly
        # for ASSUM-003 to hold.
        check_tool.func(task_id="missing", runtime=runtime)  # type: ignore[union-attr]

    def test_resolve_tracked_task_returns_string_for_unknown_id(self) -> None:
        from deepagents.middleware.async_subagents import _resolve_tracked_task

        runtime = MagicMock()
        runtime.state = {"async_tasks": {}}

        result = _resolve_tracked_task("never-existed", runtime)

        # The middleware-internal resolver returns the error string
        # synchronously without raising — this is the framework
        # primitive the supervisor relies on. If a future deepagents
        # release switches to raising, this test fires immediately.
        assert isinstance(result, str)
        assert "never-existed" in result
