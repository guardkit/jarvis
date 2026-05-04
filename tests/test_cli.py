"""Tests for jarvis.cli.main — click group with chat/version/health + REPL.

Covers acceptance criteria for TASK-J001-008:
  AC-001: ``jarvis`` (no args) prints the command list and exits 0.
  AC-002: ``jarvis version`` prints version, exits 0, does NOT load config.
  AC-003: ``jarvis health`` with valid config succeeds.
  AC-004: ``jarvis health`` with missing provider key (anthropic/google_genai) fails
          with ConfigurationError. (TASK-FRR-002 retired the OPENAI_BASE_URL gate —
          ADR-ARCH-001 mandates llama-swap, which has a hard-coded default endpoint.)
  AC-005: ``jarvis health`` with malformed supervisor model fails with ValidationError.
  AC-006: ``jarvis chat`` REPL — /exit, EOF, SIGINT, empty lines, provider errors.
  AC-007: REPL serialises turns (ASSUM-004).
  AC-008: Modified files pass lint/format checks.

Also covers TASK-J005-007 — REPL between-prompts ForgeNotification render:
  J005-007 AC-001: REPL drains ``pending_notifications`` once per iteration
    before reading user input.
  J005-007 AC-002: Each pending notification rendered via one
    ``click.echo(notification.render_line())`` call, in FIFO order.
  J005-007 AC-003: Notifications enqueued during a supervisor turn surface on
    the next iteration, never mid-turn (Group D #2).
  J005-007 AC-005: Empty queue → no output line emitted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from jarvis.cli.main import main
from jarvis.infrastructure.forge_notifications import ForgeNotification


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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
# AC-004: ``jarvis health`` missing provider key → ConfigurationError, exit 1
#
# TASK-FRR-002 / ADR-ARCH-001 retired the OPENAI_BASE_URL operator-failure
# mode (the supervisor always routes through llama-swap and that endpoint
# has a hard-coded default). The remaining operator-failure modes are the
# anthropic / google_genai supervisor models without their respective keys.
# ---------------------------------------------------------------------------
class TestHealthMissingKey:
    """AC-004: health with missing provider key (anthropic/google_genai)."""

    def test_health_missing_anthropic_key_exits_one(self) -> None:
        runner = CliRunner()
        with patch.dict(
            "os.environ",
            {"JARVIS_SUPERVISOR_MODEL": "anthropic:claude-sonnet-4-20250514"},
            clear=True,
        ):
            result = runner.invoke(main, ["health"])
        assert result.exit_code == 1

    def test_health_missing_anthropic_key_names_env_var(self) -> None:
        runner = CliRunner()
        with patch.dict(
            "os.environ",
            {"JARVIS_SUPERVISOR_MODEL": "anthropic:claude-sonnet-4-20250514"},
            clear=True,
        ):
            result = runner.invoke(main, ["health"])
        assert "ANTHROPIC_API_KEY" in result.output


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
                "JARVIS_LLAMA_SWAP_BASE_URL": "http://fake",
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
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


# ---------------------------------------------------------------------------
# TASK-J005-007: REPL between-prompts ForgeNotification render
# ---------------------------------------------------------------------------
def _make_notification(idx: int = 0, *, status: str = "PASSED") -> ForgeNotification:
    """Build a valid :class:`ForgeNotification` for CLI render tests.

    Mirrors ``tests/test_session_notifications.py::_make_notification`` so the
    same shape is exercised end-to-end. The fixed ``completed_at`` makes the
    rendered ``[HH:MM]`` deterministic per local timezone — assertions that
    check the literal shape rather than the time digits remain stable across
    CI hosts.
    """
    return ForgeNotification(
        correlation_id=f"corr-{idx:04d}",
        feature_id="FEAT-JARVIS005",
        stage_label=f"stage-{idx}",
        status=status,  # type: ignore[arg-type]
        target_kind="local_tool",
        target_identifier="queue_build",
        completed_at=datetime(2026, 4, 29, 15, 42, tzinfo=UTC),
        duration_secs=1.5,
    )


class TestReplBetweenPromptsNotificationRender:
    """TASK-J005-007 — drain + render queued notifications before each prompt.

    The acceptance criteria reference design.md §8 and DDR-030: the REPL must
    drain ``session_manager.pending_notifications(session_id)`` once per loop
    iteration *before* reading the next user line, and emit one
    ``click.echo(notification.render_line())`` per drained entry in FIFO order.
    """

    def _make_mock_state(self) -> MagicMock:
        """Mock AppState whose session_manager exposes both invoke + drain.

        The drain method is wired as a ``MagicMock`` (synchronous — it is *not*
        awaited in the production REPL) so ``side_effect`` can return per-call
        lists for multi-iteration scenarios.
        """
        state = MagicMock()
        session = MagicMock()
        session.session_id = "cli-notif-session"
        state.session_manager = MagicMock()
        state.session_manager.start_session.return_value = session
        state.session_manager.invoke = AsyncMock(return_value="mock reply")
        state.session_manager.pending_notifications = MagicMock(return_value=[])
        return state

    def test_three_queued_notifications_render_three_lines_before_prompt(self) -> None:
        """J005-007 AC-001/AC-002 (Group A #5): three queued → three echo lines."""
        state = self._make_mock_state()
        notifs = [_make_notification(i) for i in range(3)]
        # First iteration drains all three; subsequent iterations are empty.
        state.session_manager.pending_notifications.side_effect = [notifs, [], []]
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="/exit\n")
        # All three render_line() outputs appear in CLI output, in FIFO order.
        out = result.output
        assert out.find("stage-0") < out.find("stage-1") < out.find("stage-2")
        # One click.echo per notification — count occurrences of the unique
        # feature_id substring (each render_line emits exactly one).
        assert out.count("Forge FEAT-JARVIS005:") == 3

    def test_pending_notifications_called_before_reading_input(self) -> None:
        """J005-007 AC-001: drain happens before ``invoke`` and before EOF read."""
        state = self._make_mock_state()
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            runner.invoke(main, ["chat"], input="/exit\n")
        # Drained at least once (top of iteration before /exit was read).
        assert state.session_manager.pending_notifications.called
        # Called with the session_id from start_session.
        state.session_manager.pending_notifications.assert_called_with("cli-notif-session")

    def test_notification_enqueued_mid_turn_renders_next_iteration(self) -> None:
        """J005-007 AC-003 (Group D #2): mid-turn enqueue → next iteration only."""
        state = self._make_mock_state()
        mid_turn_notif = _make_notification(42)

        # Iteration sequence (drain calls):
        # 1. before "hello" turn — empty
        # 2. before "/exit" — drain the notification enqueued during the turn
        state.session_manager.pending_notifications.side_effect = [
            [],
            [mid_turn_notif],
        ]
        # ``invoke`` returns plain reply — the notification is "enqueued during
        # the supervisor turn" by virtue of the side_effect ordering above.
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="hello\n/exit\n")
        out = result.output
        # The notification must appear AFTER the "mock reply" (proof it did not
        # surface mid-turn), not before.
        reply_idx = out.find("mock reply")
        notif_idx = out.find("stage-42")
        assert reply_idx >= 0
        assert notif_idx > reply_idx

    def test_empty_queue_emits_no_extra_output(self) -> None:
        """J005-007 AC-005 (Group A #5 negative): empty drain → no blank line."""
        state = self._make_mock_state()
        # All drains return [].
        state.session_manager.pending_notifications.return_value = []
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="/exit\n")
        # No "Forge " line and no spurious blank lines beyond the closing
        # "session ended." banner.
        assert "Forge " not in result.output
        # The output should contain exactly the session-ended banner.
        non_empty = [ln for ln in result.output.splitlines() if ln.strip()]
        assert non_empty == ["session ended."]

    def test_render_line_shape_matches_dm_forge_notification(self) -> None:
        """J005-007 AC-002: render_line() shape matches DM-forge-notification §1.

        Canonical example pinned per task Test Requirements bullet #4. The
        local-time component is non-deterministic across CI host timezones,
        so the assertion fixes the structural shape and the deterministic
        non-time fields.
        """
        notif = _make_notification(7, status="FAILED")
        state = self._make_mock_state()
        state.session_manager.pending_notifications.side_effect = [[notif], []]
        runner = CliRunner()
        with (
            patch.dict(
                "os.environ",
                {"JARVIS_LLAMA_SWAP_BASE_URL": "http://fake"},
                clear=True,
            ),
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ),
        ):
            result = runner.invoke(main, ["chat"], input="/exit\n")
        # The exact rendered_line emitted by ForgeNotification.render_line()
        # must appear verbatim in CLI output (one click.echo per notif).
        expected_line = notif.render_line()
        assert expected_line in result.output
        # Sanity: shape matches "[HH:MM] Forge FEAT-...: stage ... (STATUS)".
        assert expected_line.startswith("[")
        assert "] Forge FEAT-JARVIS005: stage stage-7 (FAILED)" in expected_line
