"""Tests for Phase 2 JarvisConfig extensions (TASK-J002-001).

Covers acceptance criteria:
  AC-001: JarvisConfig gains four Phase 2 fields with documented defaults.
  AC-002: Env var names respect the JARVIS_ prefix
          (JARVIS_WEB_SEARCH_PROVIDER, JARVIS_TAVILY_API_KEY,
          JARVIS_STUB_CAPABILITIES_PATH, JARVIS_WORKSPACE_ROOT).
  AC-003: validate_provider_keys() emits a *warning* (not a
          ConfigurationError) when web_search_provider == 'tavily' and
          tavily_api_key is None.
  AC-004: Verified by tests/test_config.py continuing to pass unchanged.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import get_args, get_type_hints
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError


# ---------------------------------------------------------------------------
# AC-001: Four Phase 2 fields exist with correct types and defaults
# ---------------------------------------------------------------------------
class TestAC001Phase2FieldsExist:
    """JarvisConfig defines the four Phase 2 fields with documented defaults."""

    def test_default_web_search_provider_is_tavily(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.web_search_provider == "tavily"

    def test_web_search_provider_is_literal_tavily_or_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        hints = get_type_hints(JarvisConfig)
        allowed = set(get_args(hints["web_search_provider"]))
        assert allowed == {"tavily", "none"}

    def test_web_search_provider_rejects_unknown_value(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(web_search_provider="bing")

    def test_default_tavily_api_key_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.tavily_api_key is None

    def test_tavily_api_key_is_secret_str_when_set(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(tavily_api_key="tvly-secret-key-9876")
        assert isinstance(cfg.tavily_api_key, SecretStr)
        assert cfg.tavily_api_key.get_secret_value() == "tvly-secret-key-9876"

    def test_tavily_api_key_masked_in_repr(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(tavily_api_key="tvly-secret-key-9876")
        assert "tvly-secret-key-9876" not in repr(cfg)
        assert "tvly-secret-key-9876" not in str(cfg)

    def test_default_stub_capabilities_path(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert isinstance(cfg.stub_capabilities_path, Path)
        assert cfg.stub_capabilities_path == Path(
            "src/jarvis/config/stub_capabilities.yaml"
        )

    def test_default_workspace_root_is_resolved_cwd(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert isinstance(cfg.workspace_root, Path)
        # The default is captured at class-definition time as Path(".").resolve();
        # it must be an absolute path.
        assert cfg.workspace_root.is_absolute()


# ---------------------------------------------------------------------------
# AC-002: Env vars respect JARVIS_ prefix
# ---------------------------------------------------------------------------
class TestAC002JarvisEnvPrefix:
    """Phase 2 fields are populated from JARVIS_-prefixed environment vars."""

    def test_jarvis_web_search_provider_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ", {"JARVIS_WEB_SEARCH_PROVIDER": "none"}, clear=True
        ):
            cfg = JarvisConfig()
        assert cfg.web_search_provider == "none"

    def test_jarvis_tavily_api_key_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ", {"JARVIS_TAVILY_API_KEY": "tvly-from-env-1234"}, clear=True
        ):
            cfg = JarvisConfig()
        assert isinstance(cfg.tavily_api_key, SecretStr)
        assert cfg.tavily_api_key.get_secret_value() == "tvly-from-env-1234"

    def test_jarvis_stub_capabilities_path_env_var(self, tmp_path: Path) -> None:
        from jarvis.config.settings import JarvisConfig

        custom = tmp_path / "stub.yaml"
        with patch.dict(
            "os.environ",
            {"JARVIS_STUB_CAPABILITIES_PATH": str(custom)},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.stub_capabilities_path == custom

    def test_jarvis_workspace_root_env_var(self, tmp_path: Path) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_WORKSPACE_ROOT": str(tmp_path)},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.workspace_root == tmp_path

    def test_env_prefix_remains_jarvis(self) -> None:
        from jarvis.config.settings import JarvisConfig

        assert JarvisConfig.model_config.get("env_prefix") == "JARVIS_"


# ---------------------------------------------------------------------------
# AC-003: validate_provider_keys() warns (not raises) for missing tavily key
# ---------------------------------------------------------------------------
class TestAC003TavilyKeyWarning:
    """Tavily provider with no key emits a warning, not a ConfigurationError."""

    def test_missing_tavily_key_emits_warning(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="openai:jarvis-reasoner",
                openai_base_url="http://localhost:9000/v1",
                web_search_provider="tavily",
            )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg.validate_provider_keys()

        assert any(
            "tavily" in str(w.message).lower() for w in caught
        ), f"Expected a warning mentioning tavily, got: {[str(w.message) for w in caught]}"

    def test_missing_tavily_key_does_not_raise(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="openai:jarvis-reasoner",
                openai_base_url="http://localhost:9000/v1",
                web_search_provider="tavily",
                tavily_api_key=None,
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Must not raise — returning normally is the contract.
            cfg.validate_provider_keys()

    def test_tavily_with_key_does_not_warn(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="openai:jarvis-reasoner",
                openai_base_url="http://localhost:9000/v1",
                web_search_provider="tavily",
                tavily_api_key="tvly-real-key",
            )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg.validate_provider_keys()

        tavily_warnings = [w for w in caught if "tavily" in str(w.message).lower()]
        assert tavily_warnings == []

    def test_provider_none_does_not_warn(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="openai:jarvis-reasoner",
                openai_base_url="http://localhost:9000/v1",
                web_search_provider="none",
                tavily_api_key=None,
            )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg.validate_provider_keys()

        tavily_warnings = [w for w in caught if "tavily" in str(w.message).lower()]
        assert tavily_warnings == []

    def test_empty_tavily_secret_emits_warning(self) -> None:
        """Empty SecretStr counts as 'no key' and triggers the warning."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                supervisor_model="openai:jarvis-reasoner",
                openai_base_url="http://localhost:9000/v1",
                web_search_provider="tavily",
                tavily_api_key="",
            )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg.validate_provider_keys()

        assert any("tavily" in str(w.message).lower() for w in caught)
