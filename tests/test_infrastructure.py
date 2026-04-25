"""Tests for jarvis.infrastructure — structlog setup + lifecycle.

Acceptance Criteria:
    AC-001: configure("INFO") produces JSON on pipe, console on TTY.
    AC-002: Log events redact all *_key and *_token values.
    AC-003: startup() raises ConfigurationError with structured logging active.
    AC-004: shutdown(state) is idempotent — calling twice does not raise.
    AC-005: All modified files pass lint/format checks (verified externally).

Coach Validation:
    - configure() called before validate_provider_keys() in startup().
    - No raw secret values in structured log emit sites.
    - AppState is @dataclass(frozen=True) or equivalent.
"""

from __future__ import annotations

import dataclasses
import io
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import structlog

from jarvis.config.settings import JarvisConfig
from jarvis.shared.exceptions import ConfigurationError

# ============================================================================
# AC-001: configure() produces JSON on pipe, console on TTY
# ============================================================================


class TestConfigureLogging:
    """AC-001: infrastructure.logging.configure() output format selection."""

    def test_configure_json_on_pipe(self) -> None:
        """When stderr is not a TTY, configure() sets up JSON rendering."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        captured = io.StringIO()
        with patch("sys.stderr", new=captured):
            configure("INFO")
            bound = structlog.get_logger()
            bound.info("test_event", key="value")

        raw = captured.getvalue()
        # Should be parseable as JSON (one JSON object per line)
        lines = [line for line in raw.strip().split("\n") if line.strip()]
        assert len(lines) >= 1, f"Expected at least one log line, got: {raw!r}"
        parsed = json.loads(lines[-1])
        assert parsed["event"] == "test_event"
        assert parsed["key"] == "value"

    def test_configure_console_on_tty(self) -> None:
        """When stderr is a TTY, configure() sets up console rendering."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        captured = io.StringIO()
        captured.isatty = lambda: True  # type: ignore[attr-defined]

        with patch("sys.stderr", new=captured):
            configure("INFO")
            bound = structlog.get_logger()
            bound.info("tty_event", detail="hello")

        raw = captured.getvalue()
        # Console output should NOT be valid JSON
        lines = [line for line in raw.strip().split("\n") if line.strip()]
        assert len(lines) >= 1, "Expected log output, got nothing"
        with pytest.raises(json.JSONDecodeError):
            json.loads(lines[-1])
        # But should contain the event name
        assert "tty_event" in raw

    def test_configure_sets_log_level(self) -> None:
        """configure() respects the log_level argument."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        captured = io.StringIO()
        with patch("sys.stderr", new=captured):
            configure("WARNING")
            bound = structlog.get_logger()
            bound.info("should_be_filtered")
            bound.warning("should_appear")

        raw = captured.getvalue()
        assert "should_be_filtered" not in raw
        assert "should_appear" in raw


# ============================================================================
# AC-002: Secret redaction in log events
# ============================================================================


class TestSecretRedaction:
    """AC-002: Log events redact *_key and *_token values."""

    def test_redact_api_key_fields(self) -> None:
        """Fields ending with _key are redacted in log output."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        captured = io.StringIO()
        with patch("sys.stderr", new=captured):
            configure("INFO")
            bound = structlog.get_logger()
            bound.info("config_dump", openai_api_key="sk-secret-12345", normal="visible")

        raw = captured.getvalue()
        assert "sk-secret-12345" not in raw, "Secret key value must be redacted"
        assert "visible" in raw, "Non-secret values should be present"
        assert "***" in raw or "REDACTED" in raw.upper(), "Redacted placeholder expected"

    def test_redact_token_fields(self) -> None:
        """Fields ending with _token are redacted in log output."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        captured = io.StringIO()
        with patch("sys.stderr", new=captured):
            configure("INFO")
            bound = structlog.get_logger()
            bound.info("auth_event", refresh_token="tok-abc-999", user="alice")

        raw = captured.getvalue()
        assert "tok-abc-999" not in raw, "Token value must be redacted"
        assert "alice" in raw, "Non-secret values should be present"

    def test_redact_nested_dict_keys(self) -> None:
        """Redaction works on nested dict values containing *_key or *_token."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        captured = io.StringIO()
        with patch("sys.stderr", new=captured):
            configure("INFO")
            bound = structlog.get_logger()
            bound.info(
                "nested_config",
                config={
                    "anthropic_api_key": "ant-secret-key",
                    "google_api_key": "goog-secret",
                    "log_level": "INFO",
                },
            )

        raw = captured.getvalue()
        assert "ant-secret-key" not in raw, "Nested secret must be redacted"
        assert "goog-secret" not in raw, "Nested secret must be redacted"

    def test_redact_config_model_dump(self) -> None:
        """config.model_dump() payload redacts SecretStr and *_key/*_token fields."""
        from jarvis.infrastructure.logging import configure

        structlog.reset_defaults()

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(
                openai_base_url="http://fake/v1",
                openai_api_key="sk-real-secret-key-value",  # type: ignore[arg-type]
                anthropic_api_key="ant-real-secret",  # type: ignore[arg-type]
            )

        captured = io.StringIO()
        with patch("sys.stderr", new=captured):
            configure("INFO")
            bound = structlog.get_logger()
            dump = config.model_dump()
            bound.info("full_config", **dump)

        raw = captured.getvalue()
        # The literal secret values must NOT appear
        assert "sk-real-secret-key-value" not in raw
        assert "ant-real-secret" not in raw


# ============================================================================
# AC-003: startup() raises ConfigurationError with logging active
# ============================================================================


class TestStartup:
    """AC-003: startup() configures logging before raising ConfigurationError."""

    @pytest.mark.asyncio
    async def test_startup_raises_configuration_error_with_logging(self) -> None:
        """startup() logs the error as a structured event before re-raising."""
        from jarvis.infrastructure.lifecycle import startup

        structlog.reset_defaults()

        # Create a config that will fail validate_provider_keys()
        with patch.dict("os.environ", {}, clear=True):
            bad_config = JarvisConfig(
                supervisor_model="anthropic:claude-3",
                # No anthropic_api_key set — should trigger ConfigurationError
            )

        captured = io.StringIO()
        with patch("sys.stderr", new=captured), pytest.raises(ConfigurationError):
            await startup(bad_config)

        raw = captured.getvalue()
        # Logging should have been configured and should have captured the error
        assert len(raw) > 0, "Logging should have emitted structured events"

    @pytest.mark.asyncio
    async def test_startup_configures_logging_before_validation(self) -> None:
        """configure() is called before validate_provider_keys() in startup()."""
        from jarvis.infrastructure.lifecycle import startup
        from jarvis.infrastructure.logging import configure as real_configure

        structlog.reset_defaults()

        call_order: list[str] = []

        def mock_configure(log_level: str) -> None:
            call_order.append("configure")
            real_configure(log_level)

        def mock_validate(self: Any) -> None:
            call_order.append("validate_provider_keys")
            raise ConfigurationError("test error")

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(
                supervisor_model="anthropic:claude-3",
            )

        captured = io.StringIO()
        with (
            patch("jarvis.infrastructure.lifecycle.configure", side_effect=mock_configure),
            patch.object(JarvisConfig, "validate_provider_keys", mock_validate),
            patch("sys.stderr", new=captured),
            pytest.raises(ConfigurationError),
        ):
            await startup(config)

        assert call_order.index("configure") < call_order.index("validate_provider_keys"), (
            f"configure() must be called before validate_provider_keys(), got: {call_order}"
        )

    @pytest.mark.asyncio
    async def test_startup_returns_app_state_on_success(self) -> None:
        """startup() returns a fully-wired AppState on successful configuration."""
        from jarvis.infrastructure.lifecycle import AppState, startup

        structlog.reset_defaults()

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(
                openai_base_url="http://fake-endpoint/v1",
            )

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=[],
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
            state = await startup(config)

        assert isinstance(state, AppState)
        assert state.config is config
        assert state.store is not None
        # New contract: AppState is fully populated — supervisor and
        # session_manager are never None.
        assert state.supervisor is not None
        assert state.session_manager is not None


# ============================================================================
# AC-004: shutdown() is idempotent
# ============================================================================


class TestShutdown:
    """AC-004: shutdown(state) is idempotent — calling twice does not raise."""

    @pytest.mark.asyncio
    async def test_shutdown_does_not_raise(self) -> None:
        """A single shutdown call completes without error."""
        from jarvis.infrastructure.lifecycle import shutdown, startup

        structlog.reset_defaults()

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(openai_base_url="http://fake/v1")

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=[],
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
            state = await startup(config)
            await shutdown(state)

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self) -> None:
        """Calling shutdown twice on the same state does not raise."""
        from jarvis.infrastructure.lifecycle import shutdown, startup

        structlog.reset_defaults()

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(openai_base_url="http://fake/v1")

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=[],
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
            state = await startup(config)
            await shutdown(state)
            # Second call must NOT raise
            await shutdown(state)

    @pytest.mark.asyncio
    async def test_shutdown_logs_clean_shutdown(self) -> None:
        """shutdown() emits a structured log event for clean shutdown."""
        from jarvis.infrastructure.lifecycle import shutdown, startup

        structlog.reset_defaults()

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig(openai_base_url="http://fake/v1")

        captured = io.StringIO()
        with (
            patch("sys.stderr", new=captured),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=[],
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
            state = await startup(config)
            await shutdown(state)

        raw = captured.getvalue()
        assert "shutdown" in raw.lower(), "Expected a shutdown log event"


# ============================================================================
# AppState immutability (Coach Validation)
# ============================================================================


class TestAppStateImmutability:
    """Coach: AppState must be @dataclass(frozen=True) or equivalent."""

    def test_app_state_is_frozen_dataclass(self) -> None:
        """AppState is a frozen dataclass (immutable after creation)."""
        from jarvis.infrastructure.lifecycle import AppState

        assert dataclasses.is_dataclass(AppState), "AppState must be a dataclass"
        # frozen=True means we can't set attributes after init.  All four
        # fields are required with concrete types (no more ``None``
        # sentinels — supervisor and session_manager are always wired).
        state = AppState(
            config=MagicMock(),
            supervisor=MagicMock(),
            store=MagicMock(),
            session_manager=MagicMock(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            state.config = MagicMock()  # type: ignore[misc]
