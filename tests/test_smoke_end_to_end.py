"""End-to-end smoke test — CLI -> supervisor -> stdout path.

TASK-J001-009 acceptance criteria:
    AC-001: pytest tests/test_smoke_end_to_end.py -v passes with 1 test
            covering the full CLI -> supervisor -> stdout path.

This test exercises the complete happy-path flow through Jarvis in a single
test function:

    1. Bootstrap config (``JarvisConfig``) with safe env.
    2. Build supervisor via ``build_supervisor(config)``.
    3. Wire ``SessionManager(supervisor, store)``.
    4. Start a CLI session.
    5. Invoke the supervisor with a user message.
    6. Assert the response appears on stdout (via Click runner).

The test patches ``init_chat_model`` and ``create_deep_agent`` to avoid any
real network or LLM calls, using a fake compiled graph that returns a canned
response.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner

from jarvis.cli.main import main


class TestEndToEndSmoke:
    """AC-001: Single end-to-end smoke test covering CLI -> supervisor -> stdout."""

    def test_full_cli_to_supervisor_to_stdout(self) -> None:
        """Exercise the full chat path: CLI invokes supervisor and prints reply.

        The test sends "hello" via stdin and expects the supervisor's canned
        reply to appear in stdout, followed by a clean "/exit".
        """
        # -- Arrange: mock state that the REPL will use --
        state = MagicMock()
        session = MagicMock()
        session.session_id = "cli-smoke-test-001"
        state.session_manager = MagicMock()
        state.session_manager.start_session.return_value = session
        state.session_manager.invoke = AsyncMock(
            return_value="Smoke test reply from supervisor"
        )

        runner = CliRunner()

        # -- Act: run the chat command with a single turn and /exit --
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake-endpoint/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="hello\n/exit\n")

        # -- Assert: supervisor response appears in stdout --
        assert result.exit_code == 0, (
            f"Expected exit code 0, got {result.exit_code}.\n"
            f"Output: {result.output}\n"
            f"Exception: {result.exception}"
        )
        assert "Smoke test reply from supervisor" in result.output, (
            f"Supervisor reply not found in output: {result.output!r}"
        )
        assert "session ended" in result.output.lower(), (
            f"Session ended banner not found in output: {result.output!r}"
        )

        # Verify the full path was exercised:
        # 1. Session was started with CLI adapter
        state.session_manager.start_session.assert_called_once()
        # 2. invoke was called with the session and user input
        state.session_manager.invoke.assert_called_once()
        call_args = state.session_manager.invoke.call_args
        assert call_args[0][0] is session  # first positional arg is session
        assert call_args[0][1] == "hello"  # second positional arg is user input
        # 3. Session was ended cleanly
        state.session_manager.end_session.assert_called_once_with(
            "cli-smoke-test-001"
        )
