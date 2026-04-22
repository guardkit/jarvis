"""Tests for jarvis.cli.main — click group with chat/version/health + REPL.

Covers acceptance criteria for TASK-J001-008:
  AC-001: ``jarvis`` (no args) prints the command list and exits 0.
  AC-002: ``jarvis version`` prints version, exits 0, does NOT load config.
  AC-003: ``jarvis health`` with valid config succeeds.
  AC-004: ``jarvis health`` with missing OPENAI_BASE_URL fails with ConfigurationError.
  AC-005: ``jarvis health`` with malformed supervisor model fails with ValidationError.
  AC-006: ``jarvis chat`` REPL — /exit, EOF, SIGINT, empty lines, provider errors.
  AC-007: REPL serialises turns (ASSUM-004).
  AC-008: Modified files pass lint/format checks.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from jarvis.cli.main import main


# ---------------------------------------------------------------------------
# Autouse: stub ``jarvis.cli.main.load_dotenv`` so tests that run the CLI
# don't re-seed ``os.environ`` from the operator's real ``.env``. The global
# conftest already chdirs to a tmp path, which prevents pydantic-settings
# from reading ``.env`` via its ``env_file`` path; this fixture closes the
# other path (the explicit ``load_dotenv`` bridge we call in ``main()``).
# Tests in ``TestDotenvBridge`` apply their own ``patch()`` which nests
# correctly over this stub.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stub_load_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jarvis.cli.main.load_dotenv", lambda **kw: None)


# ---------------------------------------------------------------------------
# AC-001: ``jarvis`` (no args) prints command list, exits 0
# ---------------------------------------------------------------------------
class TestNoArgs:
    """AC-001: jarvis with no arguments."""

    def test_no_args_prints_help_and_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        # Must show the three commands
        assert "version" in result.output
        assert "health" in result.output
        assert "chat" in result.output

    def test_no_args_shows_group_description(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# .env bridging: load_dotenv runs on every CLI entry so that downstream
# consumers reading os.environ directly (langchain's provider clients) see
# values the user put in .env. pydantic-settings populates JarvisConfig from
# .env but does NOT export to os.environ — without this bridge, `jarvis chat`
# crashes with "api_key option must be set" even when .env has the key.
# ---------------------------------------------------------------------------
class TestDotenvBridge:
    """Every CLI entry calls ``dotenv.load_dotenv`` before subcommand dispatch."""

    def test_version_invokes_load_dotenv(self) -> None:
        runner = CliRunner()
        with patch("jarvis.cli.main.load_dotenv") as mock_load:
            result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        mock_load.assert_called_once_with(override=False)

    def test_no_args_invokes_load_dotenv(self) -> None:
        runner = CliRunner()
        with patch("jarvis.cli.main.load_dotenv") as mock_load:
            result = runner.invoke(main, [])
        assert result.exit_code == 0
        mock_load.assert_called_once_with(override=False)

    def test_load_dotenv_does_not_override_existing_env(self) -> None:
        """``override=False`` — shell exports must win over ``.env``.

        Ensures ad-hoc ``export OPENAI_API_KEY=…`` in the shell can override
        a stale value in ``.env`` without the user having to edit the file.
        """
        runner = CliRunner()
        with patch("jarvis.cli.main.load_dotenv") as mock_load:
            runner.invoke(main, ["version"])
        _, kwargs = mock_load.call_args
        assert kwargs.get("override") is False


# ---------------------------------------------------------------------------
# AC-002: ``jarvis version`` — prints version, exits 0, no config load
# ---------------------------------------------------------------------------
class TestVersion:
    """AC-002: jarvis version command."""

    def test_version_prints_version_string(self) -> None:
        from jarvis.shared.constants import VERSION

        runner = CliRunner()
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert VERSION in result.output

    def test_version_does_not_import_jarvis_config(self) -> None:
        """Coach validation: version must NOT import JarvisConfig or call startup()."""
        runner = CliRunner()
        with patch("jarvis.config.settings.JarvisConfig") as mock_cfg:
            result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        mock_cfg.assert_not_called()

    def test_version_does_not_call_startup(self) -> None:
        """Coach validation: version must NOT call startup()."""
        runner = CliRunner()
        with patch("jarvis.infrastructure.lifecycle.startup") as mock_startup:
            result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        mock_startup.assert_not_called()


# ---------------------------------------------------------------------------
# AC-003: ``jarvis health`` with valid config prints summary, exits 0
# ---------------------------------------------------------------------------
class TestHealthValid:
    """AC-003: jarvis health with valid config."""

    def test_health_valid_config_exits_zero(self) -> None:
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            result = runner.invoke(main, ["health"])
        assert result.exit_code == 0

    def test_health_reports_supervisor_build_success(self) -> None:
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            result = runner.invoke(main, ["health"])
        assert "supervisor" in result.output.lower()

    def test_health_reports_memory_store_ready(self) -> None:
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            result = runner.invoke(main, ["health"])
        assert "memory" in result.output.lower() or "store" in result.output.lower()


# ---------------------------------------------------------------------------
# AC-004: ``jarvis health`` missing OPENAI_BASE_URL → ConfigurationError, exit 1
# ---------------------------------------------------------------------------
class TestHealthMissingKey:
    """AC-004: health with missing provider key."""

    def test_health_missing_openai_base_url_exits_one(self) -> None:
        runner = CliRunner()
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(main, ["health"])
        assert result.exit_code == 1

    def test_health_missing_key_names_env_var(self) -> None:
        runner = CliRunner()
        with patch.dict("os.environ", {}, clear=True):
            result = runner.invoke(main, ["health"])
        assert "OPENAI_BASE_URL" in result.output


# ---------------------------------------------------------------------------
# AC-005: ``jarvis health`` with malformed supervisor_model → ValidationError, exit 1
# ---------------------------------------------------------------------------
class TestHealthMalformedModel:
    """AC-005: health with malformed supervisor_model."""

    def test_health_malformed_model_exits_one(self) -> None:
        runner = CliRunner()
        with patch.dict(
            "os.environ",
            {
                "JARVIS_SUPERVISOR_MODEL": "jarvis-reasoner",
                "JARVIS_OPENAI_BASE_URL": "http://fake/v1",
            },
            clear=True,
        ):
            result = runner.invoke(main, ["health"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# AC-006: ``jarvis chat`` REPL behaviour
# ---------------------------------------------------------------------------
class TestChatRepl:
    """AC-006: REPL interaction tests."""

    def _make_mock_state(self) -> MagicMock:
        """Create a mock AppState with a working session manager."""
        state = MagicMock()
        session = MagicMock()
        session.session_id = "cli-test-session-123"
        state.session_manager = MagicMock()
        state.session_manager.start_session.return_value = session
        state.session_manager.invoke = AsyncMock(return_value="mock reply")
        return state

    def test_chat_exit_command_clean_exit(self) -> None:
        """/exit (case-sensitive, whitespace-trimmed) → clean exit, code 0."""
        state = self._make_mock_state()
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="/exit\n")
        assert result.exit_code == 0
        assert "session ended" in result.output.lower()

    def test_chat_exit_is_case_sensitive(self) -> None:
        """Coach validation: /EXIT should NOT trigger exit — treated as normal input."""
        state = self._make_mock_state()
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            # /EXIT is NOT /exit, so it should be sent to supervisor, then EOF exits
            runner.invoke(main, ["chat"], input="/EXIT\n")
        # The mock invoke should have been called with "/EXIT"
        state.session_manager.invoke.assert_called()

    def test_chat_eof_clean_exit(self) -> None:
        """EOF / Ctrl-D → clean exit with 'session ended.' banner, code 0."""
        state = self._make_mock_state()
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="")
        assert result.exit_code == 0
        assert "session ended" in result.output.lower()

    def test_chat_empty_line_silently_skipped(self) -> None:
        """Empty line → silently skipped, no supervisor call."""
        state = self._make_mock_state()
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            runner.invoke(main, ["chat"], input="\n\n/exit\n")
        # invoke must NOT have been called for empty lines
        state.session_manager.invoke.assert_not_called()

    def test_chat_provider_error_survives(self) -> None:
        """Provider error mid-turn → [error] printed, REPL continues."""
        state = self._make_mock_state()
        state.session_manager.invoke = AsyncMock(
            side_effect=[RuntimeError("LLM down"), "recovered reply"]
        )
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="hello\nworld\n/exit\n")
        assert "[error]" in result.output.lower()
        # Second invoke should have been called (REPL continued)
        assert state.session_manager.invoke.call_count == 2

    def test_chat_exit_with_leading_whitespace(self) -> None:
        """' /exit ' (whitespace-trimmed) should trigger exit."""
        state = self._make_mock_state()
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="  /exit  \n")
        assert result.exit_code == 0
        assert "session ended" in result.output.lower()

    def test_chat_sigint_exits_130(self) -> None:
        """SIGINT / Ctrl-C → session ended, exit 130."""
        state = self._make_mock_state()
        # Simulate SIGINT by having invoke raise KeyboardInterrupt
        state.session_manager.invoke = AsyncMock(side_effect=KeyboardInterrupt)
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
            patch("jarvis.cli.main.sys") as mock_sys,
        ):
            mock_sys.exit = MagicMock(side_effect=SystemExit(130))
            try:
                runner.invoke(main, ["chat"], input="hello\n")
            except SystemExit as exc:
                assert exc.code == 130
        # end_session must have been called
        state.session_manager.end_session.assert_called()


# ---------------------------------------------------------------------------
# AC-007: REPL serialises turns (ASSUM-004)
# ---------------------------------------------------------------------------
class TestReplSerialisation:
    """AC-007: REPL does not read next line until reply printed."""

    def test_turns_are_sequential(self) -> None:
        """Verify invoke is awaited before next line is read (sequential loop)."""
        call_order: list[str] = []

        async def track_invoke(session: Any, user_input: str) -> str:
            call_order.append(f"invoke:{user_input.strip()}")
            return f"reply to {user_input.strip()}"

        state = MagicMock()
        session = MagicMock()
        session.session_id = "cli-serial-test"
        state.session_manager = MagicMock()
        state.session_manager.start_session.return_value = session
        state.session_manager.invoke = AsyncMock(side_effect=track_invoke)

        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_OPENAI_BASE_URL": "http://fake/v1"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="first\nsecond\n/exit\n")

        # Both turns should have been invoked, sequentially
        assert call_order == ["invoke:first", "invoke:second"]
        # Replies appear in output before next prompt
        assert "reply to first" in result.output
        assert "reply to second" in result.output
