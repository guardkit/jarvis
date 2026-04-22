"""Tests for jarvis.config — JarvisConfig (pydantic-settings) and validate_provider_keys.

Covers acceptance criteria for TASK-J001-003:
  AC-001: Default config loads with correct defaults (INFO, in_memory, openai:jarvis-reasoner)
  AC-002: Non-prefixed supervisor model raises ValidationError
  AC-003: Invalid log level raises ValidationError
  AC-004: SecretStr values masked in str()/repr()
  AC-005: validate_provider_keys() raises ConfigurationError naming missing env var
  AC-006: Lint/format checks pass (verified separately via ruff)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# AC-001: Default config loads with documented defaults
# ---------------------------------------------------------------------------
class TestAC001DefaultConfig:
    """JarvisConfig() with no env vars loads documented defaults."""

    def test_default_log_level_is_info(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.log_level == "INFO"

    def test_default_memory_store_backend_is_in_memory(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.memory_store_backend == "in_memory"

    def test_default_supervisor_model_is_openai_jarvis_reasoner(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.supervisor_model == "openai:jarvis-reasoner"

    def test_default_data_dir_is_home_dot_jarvis(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.data_dir == Path.home() / ".jarvis"

    def test_default_openai_api_key_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.openai_api_key is None

    def test_default_anthropic_api_key_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.anthropic_api_key is None

    def test_default_google_api_key_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.google_api_key is None

    def test_default_openai_base_url_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.openai_base_url is None

    def test_env_prefix_is_jarvis(self) -> None:
        """SettingsConfigDict uses env_prefix='JARVIS_'."""
        from jarvis.config.settings import JarvisConfig

        assert JarvisConfig.model_config.get("env_prefix") == "JARVIS_"

    def test_config_importable_from_package(self) -> None:
        """JarvisConfig can be imported from jarvis.config."""
        from jarvis.config import JarvisConfig as JC

        assert JC is not None


# ---------------------------------------------------------------------------
# AC-002: Non-prefixed supervisor model raises ValidationError
# ---------------------------------------------------------------------------
class TestAC002SupervisorModelValidation:
    """supervisor_model without provider prefix raises ValidationError."""

    def test_bare_model_name_raises_validation_error(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                JarvisConfig(supervisor_model="jarvis-reasoner")
            assert "supervisor_model" in str(exc_info.value)

    def test_bare_model_no_colon_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(supervisor_model="gpt-4")

    @pytest.mark.parametrize(
        "model",
        [
            "openai:gpt-4",
            "anthropic:claude-3-opus",
            "google_genai:gemini-pro",
            "openai:jarvis-reasoner",
        ],
    )
    def test_prefixed_model_accepted(self, model: str) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model=model)
        assert cfg.supervisor_model == model

    def test_empty_model_name_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(supervisor_model="")

    def test_colon_only_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(supervisor_model=":")

    def test_env_var_bare_model_raises(self) -> None:
        """JARVIS_SUPERVISOR_MODEL=jarvis-reasoner raises ValidationError."""
        from jarvis.config.settings import JarvisConfig

        with (
            patch.dict(
                "os.environ",
                {"JARVIS_SUPERVISOR_MODEL": "jarvis-reasoner"},
                clear=True,
            ),
            pytest.raises(ValidationError),
        ):
            JarvisConfig()


# ---------------------------------------------------------------------------
# AC-003: Invalid log level raises ValidationError
# ---------------------------------------------------------------------------
class TestAC003LogLevelValidation:
    """Invalid log_level values raise ValidationError at construction."""

    def test_bogus_log_level_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(log_level="bogus")

    def test_env_var_bogus_log_level_raises(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with (
            patch.dict(
                "os.environ",
                {"JARVIS_LOG_LEVEL": "bogus"},
                clear=True,
            ),
            pytest.raises(ValidationError),
        ):
            JarvisConfig()

    @pytest.mark.parametrize(
        "level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )
    def test_valid_log_levels_accepted(self, level: str) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(log_level=level)
        assert cfg.log_level == level


# ---------------------------------------------------------------------------
# AC-004: SecretStr values masked in str()/repr()
# ---------------------------------------------------------------------------
class TestAC004SecretStrMasking:
    """str() and repr() must not disclose SecretStr values."""

    def test_str_masks_openai_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(openai_api_key="sk-secret-key-12345")
        output = str(cfg)
        assert "sk-secret-key-12345" not in output

    def test_repr_masks_openai_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(openai_api_key="sk-secret-key-12345")
        output = repr(cfg)
        assert "sk-secret-key-12345" not in output

    def test_str_masks_anthropic_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(anthropic_api_key="sk-ant-secret-99999")
        output = str(cfg)
        assert "sk-ant-secret-99999" not in output

    def test_repr_masks_anthropic_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(anthropic_api_key="sk-ant-secret-99999")
        output = repr(cfg)
        assert "sk-ant-secret-99999" not in output

    def test_str_masks_google_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(google_api_key="AIza-google-secret-key")
        output = str(cfg)
        assert "AIza-google-secret-key" not in output

    def test_repr_masks_google_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(google_api_key="AIza-google-secret-key")
        output = repr(cfg)
        assert "AIza-google-secret-key" not in output

    def test_masked_value_shows_stars(self) -> None:
        """SecretStr renders as '**********' in output."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(openai_api_key="sk-secret-key-12345")
        output = str(cfg)
        assert "**********" in output


# ---------------------------------------------------------------------------
# AC-005: validate_provider_keys() raises ConfigurationError
# ---------------------------------------------------------------------------
class TestAC005ValidateProviderKeys:
    """validate_provider_keys() raises ConfigurationError naming missing env var."""

    def test_openai_model_requires_openai_base_url(self) -> None:
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="openai:jarvis-reasoner")
        with pytest.raises(ConfigurationError, match="OPENAI_BASE_URL"):
            cfg.validate_provider_keys()

    def test_openai_model_with_base_url_passes(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="openai:jarvis-reasoner",
                openai_base_url="http://promaxgb10-41b1:9000/v1",
            )
        # Should not raise
        cfg.validate_provider_keys()

    def test_anthropic_model_requires_anthropic_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="anthropic:claude-3-opus")
        with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
            cfg.validate_provider_keys()

    def test_anthropic_model_with_key_passes(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="anthropic:claude-3-opus",
                anthropic_api_key="sk-ant-valid-key",
            )
        cfg.validate_provider_keys()

    def test_google_genai_model_requires_google_api_key(self) -> None:
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="google_genai:gemini-pro")
        with pytest.raises(ConfigurationError, match="GOOGLE_API_KEY"):
            cfg.validate_provider_keys()

    def test_google_genai_model_with_key_passes(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="google_genai:gemini-pro",
                google_api_key="AIza-valid-key",
            )
        cfg.validate_provider_keys()

    def test_error_message_names_specific_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="anthropic:claude-3-opus")
        with pytest.raises(ConfigurationError) as exc_info:
            cfg.validate_provider_keys()
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)

    def test_non_in_memory_backend_raises_configuration_error(self) -> None:
        """memory_store_backend != 'in_memory' raises ConfigurationError at validate time."""
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                memory_store_backend="file",
                openai_base_url="http://localhost:9000/v1",
            )
        with pytest.raises(ConfigurationError, match="not implemented"):
            cfg.validate_provider_keys()

    def test_graphiti_backend_raises_configuration_error(self) -> None:
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                memory_store_backend="graphiti",
                openai_base_url="http://localhost:9000/v1",
            )
        with pytest.raises(ConfigurationError, match="not implemented"):
            cfg.validate_provider_keys()

    def test_unknown_provider_passes_validation(self) -> None:
        """Unknown provider prefix has no key requirement — passes silently."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="custom_local:my-model")
        # Should not raise
        cfg.validate_provider_keys()

    def test_anthropic_empty_secret_raises(self) -> None:
        """SecretStr set to empty string still raises ConfigurationError."""
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="anthropic:claude-3-opus",
                anthropic_api_key="",
            )
        with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
            cfg.validate_provider_keys()

    def test_configuration_error_is_jarvis_error(self) -> None:
        """ConfigurationError raised by validate_provider_keys is a JarvisError."""
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import JarvisError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="anthropic:claude-3-opus")
        with pytest.raises(JarvisError):
            cfg.validate_provider_keys()
