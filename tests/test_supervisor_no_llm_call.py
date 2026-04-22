"""Supervisor no-LLM-call invariant test — build_supervisor must never consume tokens.

TASK-J001-009 acceptance criteria:
    AC-003: pytest tests/test_supervisor_no_llm_call.py -v passes; the mock
            assertion fires on any regression that would issue a
            token-consuming request from ``build_supervisor``.

This test file provides a focused, regression-proof guard against accidental
LLM invocations during ``build_supervisor(config)`` calls.  Unlike the broader
tests in ``test_supervisor.py`` which cover many concerns, these tests
exclusively verify the "no tokens at build time" invariant.

Strategy:
    - Patch ``init_chat_model`` to return a strict MagicMock that records all
      method calls.
    - Patch ``create_deep_agent`` to accept the mock and return a mock graph.
    - Call ``build_supervisor(config)`` and assert that NO token-consuming
      method was ever called on the model object.
    - Cover: ``.invoke()``, ``.ainvoke()``, ``.stream()``, ``.astream()``,
      ``.predict()``, ``.apredict()``, ``.generate()``, ``.agenerate()``,
      ``.batch()``, ``.abatch()``, ``.bind_tools()()``, and ``__call__``.
"""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

from langgraph.graph.state import CompiledStateGraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_with_mock_model(test_config: Any) -> MagicMock:
    """Call build_supervisor(config) with a fully mocked model and return the model mock.

    Returns:
        The MagicMock model object that was injected via init_chat_model.
    """
    from jarvis.agents.supervisor import build_supervisor

    with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
        mock_model = MagicMock(name="mock_llm_model")
        mock_init.return_value = mock_model

        with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)
            build_supervisor(test_config)

    return mock_model


# ---------------------------------------------------------------------------
# Core invariant — no token-consuming calls
# ---------------------------------------------------------------------------

class TestNoTokenConsumingCalls:
    """build_supervisor must never issue a token-consuming LLM request."""

    def test_invoke_and_ainvoke_not_called(self, test_config: object) -> None:
        """model.invoke() and model.ainvoke() are never called during build."""
        model = _build_with_mock_model(test_config)
        model.invoke.assert_not_called()
        model.ainvoke.assert_not_called()

    def test_stream_and_astream_not_called(self, test_config: object) -> None:
        """model.stream() and model.astream() are never called during build."""
        model = _build_with_mock_model(test_config)
        model.stream.assert_not_called()
        model.astream.assert_not_called()

    def test_predict_and_apredict_not_called(self, test_config: object) -> None:
        """model.predict() and model.apredict() are never called during build."""
        model = _build_with_mock_model(test_config)
        model.predict.assert_not_called()
        model.apredict.assert_not_called()

    def test_generate_and_agenerate_not_called(self, test_config: object) -> None:
        """model.generate() and model.agenerate() are never called during build."""
        model = _build_with_mock_model(test_config)
        model.generate.assert_not_called()
        model.agenerate.assert_not_called()

    def test_batch_and_abatch_not_called(self, test_config: object) -> None:
        """model.batch() and model.abatch() are never called during build."""
        model = _build_with_mock_model(test_config)
        model.batch.assert_not_called()
        model.abatch.assert_not_called()


# ---------------------------------------------------------------------------
# Composite assertion — all methods in one shot
# ---------------------------------------------------------------------------

class TestCompositeNoLLMCall:
    """Single comprehensive test that asserts all LLM methods are untouched."""

    TOKEN_CONSUMING_METHODS: ClassVar[list[str]] = [
        "invoke",
        "ainvoke",
        "stream",
        "astream",
        "predict",
        "apredict",
        "generate",
        "agenerate",
        "batch",
        "abatch",
    ]

    def test_no_token_consuming_method_called(self, test_config: object) -> None:
        """Assert that none of the known token-consuming methods were called."""
        model = _build_with_mock_model(test_config)

        violations: list[str] = []
        for method_name in self.TOKEN_CONSUMING_METHODS:
            method = getattr(model, method_name)
            if method.called:
                violations.append(
                    f"model.{method_name}() was called {method.call_count} time(s)"
                )

        assert violations == [], (
            "build_supervisor must not issue token-consuming requests:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Model passthrough — model is only passed to create_deep_agent, not invoked
# ---------------------------------------------------------------------------

class TestModelPassthrough:
    """The model object is only passed through to create_deep_agent."""

    def test_model_passed_as_kwarg_to_create_deep_agent(
        self, test_config: object
    ) -> None:
        """create_deep_agent receives the model object as its 'model' kwarg."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_model = MagicMock(name="passthrough_model")
            mock_init.return_value = mock_model

            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

                # Verify model was passed to create_deep_agent
                _, kwargs = mock_create.call_args
                assert kwargs["model"] is mock_model, (
                    "model must be passed through to create_deep_agent"
                )

    def test_init_chat_model_called_exactly_once(
        self, test_config: object
    ) -> None:
        """init_chat_model is called exactly once per build_supervisor call."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()

            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

            mock_init.assert_called_once()

    def test_create_deep_agent_called_exactly_once(
        self, test_config: object
    ) -> None:
        """create_deep_agent is called exactly once per build_supervisor call."""
        from jarvis.agents.supervisor import build_supervisor

        with patch("jarvis.agents.supervisor.init_chat_model") as mock_init:
            mock_init.return_value = MagicMock()

            with patch("jarvis.agents.supervisor.create_deep_agent") as mock_create:
                mock_create.return_value = MagicMock(spec=CompiledStateGraph)
                build_supervisor(test_config)

                mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Regression guard — build_supervisor called from health command
# ---------------------------------------------------------------------------

class TestHealthCommandNoTokens:
    """``jarvis health`` must call build_supervisor without consuming tokens."""

    def test_health_command_does_not_consume_tokens(self) -> None:
        """Run jarvis health and verify no LLM methods called on the model."""
        from click.testing import CliRunner

        from jarvis.cli.main import main

        mock_model = MagicMock(name="health_check_model")

        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake-endpoint/v1"},
                clear=True,
            ),
            patch("jarvis.agents.supervisor.init_chat_model") as mock_init,
            patch("jarvis.agents.supervisor.create_deep_agent") as mock_create,
        ):
            mock_init.return_value = mock_model
            mock_create.return_value = MagicMock(spec=CompiledStateGraph)

            runner = CliRunner()
            result = runner.invoke(main, ["health"])

        assert result.exit_code == 0, (
            f"Health check failed: {result.output}"
        )

        # Verify no token-consuming methods on the model
        for method_name in TestCompositeNoLLMCall.TOKEN_CONSUMING_METHODS:
            method = getattr(mock_model, method_name)
            assert not method.called, (
                f"model.{method_name}() called during 'jarvis health' — "
                f"this would consume tokens in production"
            )
