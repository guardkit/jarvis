"""Tests for ``jarvis.agents.supervisor`` — build_supervisor factory.

TASK-J001-006 acceptance criteria:
    AC-001: build_supervisor(test_config) returns CompiledStateGraph without network.
    AC-002: Built-in tools present; execute and custom tools absent; no subagents.
    AC-003: jarvis health can call it without consuming tokens.
    AC-004: Idempotent-safe: calling twice yields independent graphs.
    AC-005: All files pass lint/format checks.

Seam test:
    SUPERVISOR_MODEL_ENDPOINT contract from TASK-J001-003.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph


# ---------------------------------------------------------------------------
# AC-001 — build_supervisor returns CompiledStateGraph without network calls
# ---------------------------------------------------------------------------
class TestBuildSupervisorReturnsGraph:
    """AC-001: build_supervisor(test_config) returns a CompiledStateGraph
    without issuing any network request."""

    def test_returns_compiled_state_graph(
        self, test_config: object, fake_llm: Any
    ) -> None:
        """Factory returns a CompiledStateGraph instance without a real provider client.

        Patches ``init_chat_model`` with the deterministic ``fake_llm`` fixture so the
        OpenAI client is never instantiated — AC-001 requires no network and no real
        provider credentials at build time.
        """
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm):
            graph = build_supervisor(test_config)
        assert isinstance(graph, CompiledStateGraph)

    def test_no_network_calls_at_build_time(self, test_config: object) -> None:
        """No .invoke(), .ainvoke(), .stream(), .astream() on the model."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_model = MagicMock()
            mock_init.return_value = mock_model

            # Patch create_deep_agent to accept mock model and return a mock graph
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

            # Verify no LLM invocations happened
            mock_model.invoke.assert_not_called()
            mock_model.ainvoke.assert_not_called()
            mock_model.stream.assert_not_called()
            mock_model.astream.assert_not_called()


# ---------------------------------------------------------------------------
# AC-002 — Built-in tools present; execute absent; no subagents
# ---------------------------------------------------------------------------
class TestToolInventory:
    """AC-002: write_todos, virtual filesystem, task tools present;
    execute does not appear; no custom tools; no subagents."""

    def test_tools_kwarg_is_empty_list(self, test_config: object) -> None:
        """tools=[] is explicitly passed to create_deep_agent."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

                _, kwargs = mock_create.call_args
                assert kwargs.get("tools") == [] or mock_create.call_args[0] == []
                assert "tools" in kwargs
                assert kwargs["tools"] == []

    def test_subagents_kwarg_is_empty_list(self, test_config: object) -> None:
        """subagents=[] is explicitly passed to create_deep_agent."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

                _, kwargs = mock_create.call_args
                assert "subagents" in kwargs
                assert kwargs["subagents"] == []

    def test_system_prompt_is_imported_not_hardcoded(self) -> None:
        """System prompt is imported from jarvis.prompts.supervisor_prompt."""
        import ast
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "src" / "jarvis" / "agents" / "supervisor.py"
        tree = ast.parse(src.read_text())

        # Look for import of SUPERVISOR_SYSTEM_PROMPT
        found_import = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "prompts" in node.module:
                for alias in node.names:
                    if alias.name == "SUPERVISOR_SYSTEM_PROMPT":
                        found_import = True
        assert found_import, (
            "SUPERVISOR_SYSTEM_PROMPT must be imported from jarvis.prompts, not hard-coded"
        )

    def test_system_prompt_passed_to_create_deep_agent(self, test_config: object) -> None:
        """The system prompt (with date/domain injected) is passed to create_deep_agent."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

                _, kwargs = mock_create.call_args
                assert "system_prompt" in kwargs
                prompt = kwargs["system_prompt"]
                assert isinstance(prompt, str)
                assert len(prompt) > 0
                # Should have date injected (no raw placeholder)
                assert "{date}" not in prompt
                # Should have domain_prompt placeholder resolved
                assert "{domain_prompt}" not in prompt


# ---------------------------------------------------------------------------
# AC-003 — jarvis health can call it without consuming tokens
# ---------------------------------------------------------------------------
class TestTokenFree:
    """AC-003: jarvis health can call build_supervisor without consuming tokens."""

    def test_init_chat_model_called_with_config_supervisor_model(self, test_config: object) -> None:
        """init_chat_model receives the provider:model string from config."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

                mock_init.assert_called_once_with(test_config.supervisor_model)

    def test_no_model_method_calls(self, test_config: object) -> None:
        """The model object is only passed to create_deep_agent, never invoked."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_model = MagicMock()
            mock_init.return_value = mock_model
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

            # model is passed through but never called
            mock_model.invoke.assert_not_called()
            mock_model.ainvoke.assert_not_called()
            mock_model.stream.assert_not_called()
            mock_model.astream.assert_not_called()
            mock_model.predict.assert_not_called()


# ---------------------------------------------------------------------------
# AC-004 — Idempotent-safe: two calls → two independent graphs
# ---------------------------------------------------------------------------
class TestIdempotentSafe:
    """AC-004: Calling build_supervisor twice yields independent graphs."""

    def test_two_calls_yield_distinct_objects(self, test_config: object) -> None:
        """Two calls to build_supervisor return separate graph objects."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()
            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                # Return distinct mock objects
                graph_a = MagicMock(spec=CompiledStateGraph)
                graph_b = MagicMock(spec=CompiledStateGraph)
                mock_create.side_effect = [graph_a, graph_b]

                result_a = build_supervisor(test_config)
                result_b = build_supervisor(test_config)

                assert result_a is not result_b
                assert mock_create.call_count == 2

    def test_no_global_state_leakage(self, test_config: object) -> None:
        """No module-level caching or global state between calls."""
        from jarvis.agents import supervisor

        # Check there are no module-level mutable caches
        module_attrs = {
            k: v
            for k, v in vars(supervisor).items()
            if not k.startswith("_")
            and not callable(v)
            and not isinstance(v, type)
            and k != "SUPERVISOR_SYSTEM_PROMPT"
        }
        # All public non-callable attrs should be immutable or absent
        for attr_name, attr_value in module_attrs.items():
            assert not isinstance(attr_value, (list, dict, set)), (
                f"Module-level mutable {type(attr_value).__name__} '{attr_name}' "
                f"could leak state between build_supervisor calls"
            )


# ---------------------------------------------------------------------------
# AC-005 — Lint/format (verified externally, but we check imports are clean)
# ---------------------------------------------------------------------------
class TestLintCompliance:
    """AC-005: All files pass lint/format checks."""

    def test_supervisor_module_compiles(self) -> None:
        """Module compiles without syntax errors."""
        import jarvis.agents.supervisor  # noqa: F401

    def test_agents_init_compiles(self) -> None:
        """__init__.py compiles and re-exports build_supervisor."""
        from jarvis.agents import build_supervisor  # noqa: F401

    def test_build_supervisor_has_type_annotations(self) -> None:
        """build_supervisor has proper type annotations."""
        import inspect

        from jarvis.agents.supervisor import build_supervisor

        sig = inspect.signature(build_supervisor)
        # Should have a 'config' parameter
        assert "config" in sig.parameters
        # Should have a return annotation
        assert sig.return_annotation is not inspect.Parameter.empty


# ---------------------------------------------------------------------------
# Seam test — SUPERVISOR_MODEL_ENDPOINT contract from TASK-J001-003
# ---------------------------------------------------------------------------
class TestSeamSupervisorModelEndpoint:
    """Seam test: verify SUPERVISOR_MODEL_ENDPOINT contract from TASK-J001-003."""

    @pytest.mark.seam
    def test_supervisor_model_endpoint_format(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify supervisor_model is provider-prefixed and openai: → OPENAI_BASE_URL is required.

        Contract: supervisor_model must be provider-prefixed (e.g. 'openai:jarvis-reasoner');
        openai: prefix routes to llama-swap via OPENAI_BASE_URL.
        Producer: TASK-J001-003
        """
        from jarvis.config.settings import JarvisConfig

        monkeypatch.setenv("JARVIS_OPENAI_BASE_URL", "http://promaxgb10-41b1:9000/v1")
        config = JarvisConfig()

        assert ":" in config.supervisor_model, (
            f"supervisor_model must be provider-prefixed, got: {config.supervisor_model!r}"
        )
        provider, _, _model_name = config.supervisor_model.partition(":")
        assert provider in {"openai", "anthropic", "google_genai"}, (
            f"Unknown provider prefix {provider!r} in {config.supervisor_model!r}"
        )
        if provider == "openai":
            assert config.openai_base_url, (
                "openai: prefix requires OPENAI_BASE_URL to route via llama-swap"
            )
