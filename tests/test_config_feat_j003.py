"""Tests for FEAT-JARVIS-003 JarvisConfig extensions (TASK-J003-001).

Covers acceptance criteria:
  AC-001: ``llama_swap_base_url`` field with documented default and
          ``JARVIS_LLAMA_SWAP_BASE_URL`` env binding.
  AC-002: ``frontier_default_target`` Literal with default ``GEMINI_3_1_PRO``
          and ``JARVIS_FRONTIER_DEFAULT_TARGET`` env binding.
  AC-003: ``gemini_api_key`` SecretStr | None bound to the un-prefixed
          ``GOOGLE_API_KEY`` env name; ``anthropic_api_key`` already present.
  AC-004: ``attended_adapter_ids`` frozenset default ==
          ``{"telegram","cli","dashboard","reachy"}`` (ADR-ARCH-016).
  AC-005: No existing field renamed/removed; FEAT-J001/J002 fields still
          load with documented defaults.
"""

from __future__ import annotations

from typing import get_args, get_type_hints
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError


# ---------------------------------------------------------------------------
# AC-001: llama_swap_base_url
# ---------------------------------------------------------------------------
class TestAC001LlamaSwapBaseUrl:
    """JarvisConfig defines llama_swap_base_url with the documented default."""

    def test_default_llama_swap_base_url_is_gb10(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.llama_swap_base_url == "http://promaxgb10-41b1:9000"

    def test_llama_swap_base_url_is_str(self) -> None:
        from jarvis.config.settings import JarvisConfig

        hints = get_type_hints(JarvisConfig)
        assert hints["llama_swap_base_url"] is str

    def test_jarvis_llama_swap_base_url_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_LLAMA_SWAP_BASE_URL": "http://other-host:8080"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.llama_swap_base_url == "http://other-host:8080"


# ---------------------------------------------------------------------------
# AC-002: frontier_default_target
# ---------------------------------------------------------------------------
class TestAC002FrontierDefaultTarget:
    """frontier_default_target is a closed Literal with documented default."""

    def test_default_frontier_default_target_is_gemini(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.frontier_default_target == "GEMINI_3_1_PRO"

    def test_frontier_default_target_literal_membership(self) -> None:
        from jarvis.config.settings import JarvisConfig

        hints = get_type_hints(JarvisConfig)
        allowed = set(get_args(hints["frontier_default_target"]))
        assert allowed == {"GEMINI_3_1_PRO", "OPUS_4_7"}

    def test_frontier_default_target_rejects_unknown(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True), pytest.raises(ValidationError):
            JarvisConfig(frontier_default_target="GPT-5")

    def test_jarvis_frontier_default_target_env_var(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_FRONTIER_DEFAULT_TARGET": "OPUS_4_7"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert cfg.frontier_default_target == "OPUS_4_7"


# ---------------------------------------------------------------------------
# AC-003: gemini_api_key (env GOOGLE_API_KEY) + anthropic_api_key already present
# ---------------------------------------------------------------------------
class TestAC003FrontierProviderKeys:
    """gemini_api_key reads GOOGLE_API_KEY; anthropic_api_key already present."""

    def test_default_gemini_api_key_is_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.gemini_api_key is None

    def test_gemini_api_key_is_secret_str_when_set(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(gemini_api_key="AIza-secret-9876")
        assert isinstance(cfg.gemini_api_key, SecretStr)
        assert cfg.gemini_api_key.get_secret_value() == "AIza-secret-9876"

    def test_gemini_api_key_masked_in_repr(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(gemini_api_key="AIza-secret-9876")
        assert "AIza-secret-9876" not in repr(cfg)
        assert "AIza-secret-9876" not in str(cfg)

    def test_gemini_api_key_reads_unprefixed_google_api_key(self) -> None:
        """AC-003: env binding is the un-prefixed `GOOGLE_API_KEY`."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {"GOOGLE_API_KEY": "AIza-from-google-env"}, clear=True):
            cfg = JarvisConfig()
        assert isinstance(cfg.gemini_api_key, SecretStr)
        assert cfg.gemini_api_key.get_secret_value() == "AIza-from-google-env"

    def test_gemini_api_key_falls_back_to_jarvis_prefix(self) -> None:
        """JARVIS_GEMINI_API_KEY is honoured as a fallback alias."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ", {"JARVIS_GEMINI_API_KEY": "AIza-from-jarvis-env"}, clear=True
        ):
            cfg = JarvisConfig()
        assert isinstance(cfg.gemini_api_key, SecretStr)
        assert cfg.gemini_api_key.get_secret_value() == "AIza-from-jarvis-env"

    def test_anthropic_api_key_field_still_present(self) -> None:
        """anthropic_api_key from FEAT-J001 must remain unchanged."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.anthropic_api_key is None

    def test_anthropic_api_key_reads_jarvis_prefix(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict(
            "os.environ",
            {"JARVIS_ANTHROPIC_API_KEY": "sk-ant-from-env"},
            clear=True,
        ):
            cfg = JarvisConfig()
        assert isinstance(cfg.anthropic_api_key, SecretStr)
        assert cfg.anthropic_api_key.get_secret_value() == "sk-ant-from-env"


# ---------------------------------------------------------------------------
# AC-004: attended_adapter_ids
# ---------------------------------------------------------------------------
class TestAC004AttendedAdapterIds:
    """attended_adapter_ids defaults to the ADR-ARCH-016 consumer-surface set."""

    def test_default_attended_adapter_ids_is_arch016_set(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.attended_adapter_ids == frozenset({"telegram", "cli", "dashboard", "reachy"})

    def test_attended_adapter_ids_is_frozenset(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert isinstance(cfg.attended_adapter_ids, frozenset)

    def test_attended_adapter_ids_membership(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        for expected in ("telegram", "cli", "dashboard", "reachy"):
            assert expected in cfg.attended_adapter_ids

    def test_attended_adapter_ids_is_immutable(self) -> None:
        """frozenset rejects mutation — guards constitutional gate integrity."""
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        with pytest.raises(AttributeError):
            cfg.attended_adapter_ids.add("rogue-adapter")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AC-005: No regression — existing FEAT-J001/J002 fields still load
# ---------------------------------------------------------------------------
class TestAC005NoRegression:
    """Existing fields must not be renamed/removed; defaults still load."""

    def test_phase1_supervisor_model_default(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.supervisor_model == "openai:jarvis-reasoner"

    def test_phase1_log_level_default(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.log_level == "INFO"

    def test_phase1_memory_store_backend_default(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.memory_store_backend == "in_memory"

    def test_phase1_provider_keys_default_none(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.openai_api_key is None
        assert cfg.anthropic_api_key is None
        assert cfg.google_api_key is None
        assert cfg.openai_base_url is None

    def test_phase2_web_search_provider_default(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.web_search_provider == "tavily"

    def test_phase2_workspace_root_is_absolute(self) -> None:
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig()
        assert cfg.workspace_root.is_absolute()

    def test_validate_provider_keys_still_works(self) -> None:
        """validate_provider_keys() still raises for missing OPENAI_BASE_URL."""
        from jarvis.config.settings import JarvisConfig
        from jarvis.shared.exceptions import ConfigurationError

        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(supervisor_model="openai:jarvis-reasoner")
        with pytest.raises(ConfigurationError, match="OPENAI_BASE_URL"):
            cfg.validate_provider_keys()


# ---------------------------------------------------------------------------
# AC-006: .env.example documents the four new variables
# ---------------------------------------------------------------------------
class TestAC006EnvExampleDocumented:
    """The four FEAT-J003 env variables appear in .env.example."""

    def _read_env_example(self) -> str:
        from pathlib import Path

        # tests/ → repo root
        repo_root = Path(__file__).resolve().parents[1]
        return (repo_root / ".env.example").read_text(encoding="utf-8")

    def test_env_example_documents_llama_swap_base_url(self) -> None:
        assert "JARVIS_LLAMA_SWAP_BASE_URL" in self._read_env_example()

    def test_env_example_documents_frontier_default_target(self) -> None:
        assert "JARVIS_FRONTIER_DEFAULT_TARGET" in self._read_env_example()

    def test_env_example_documents_google_api_key(self) -> None:
        assert "GOOGLE_API_KEY" in self._read_env_example()

    def test_env_example_documents_attended_adapter_ids(self) -> None:
        assert "JARVIS_ATTENDED_ADAPTER_IDS" in self._read_env_example()
