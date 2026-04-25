"""Jarvis configuration model — pydantic-settings ``BaseSettings`` subclass.

Provides :class:`JarvisConfig` which reads environment variables with the
``JARVIS_`` prefix and validates provider-specific API keys at runtime.

Default supervisor model routes through llama-swap on the local GB10
(ADR-ARCH-001 — local-first inference).

This module belongs to Group E (cross-cutting) per ADR-ARCH-006.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jarvis.shared.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider-key requirements keyed by the provider prefix in supervisor_model.
# Each entry maps to (field_name, env_var_name) so error messages name the
# exact environment variable the operator needs to set.
# ---------------------------------------------------------------------------
_PROVIDER_KEY_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "openai": ("openai_base_url", "OPENAI_BASE_URL"),
    "anthropic": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
    "google_genai": ("google_api_key", "GOOGLE_API_KEY"),
}


class JarvisConfig(BaseSettings):
    """Application configuration loaded from environment / ``.env`` file.

    Fields use the ``JARVIS_`` prefix so ``JARVIS_LOG_LEVEL=DEBUG`` maps to
    ``log_level``.  Provider API keys are stored as :class:`SecretStr` to
    prevent accidental leakage in logs or ``repr()`` output.
    """

    # -- Application settings ------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    supervisor_model: str = "openai:jarvis-reasoner"
    memory_store_backend: Literal["in_memory", "file", "graphiti"] = "in_memory"
    data_dir: Path = Path.home() / ".jarvis"

    # -- Provider API keys (SecretStr for masking) ---------------------------
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    google_api_key: SecretStr | None = None

    # -- Phase 2: web search + workspace settings ----------------------------
    web_search_provider: Literal["tavily", "none"] = "tavily"
    tavily_api_key: SecretStr | None = None
    stub_capabilities_path: Path = Path("src/jarvis/config/stub_capabilities.yaml")
    workspace_root: Path = Path(".").resolve()

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Validators ----------------------------------------------------------

    @field_validator("supervisor_model")
    @classmethod
    def _supervisor_model_must_have_provider_prefix(cls, value: str) -> str:
        """Reject bare model names — require ``provider:model`` format.

        Raises :class:`~pydantic.ValidationError` when the value does not
        contain a colon with non-empty segments on both sides.
        """
        if ":" not in value:
            msg = (
                "supervisor_model must use 'provider:model' format "
                f"(e.g. 'openai:gpt-4'), got {value!r}"
            )
            raise ValueError(msg)

        provider, model_name = value.split(":", 1)
        if not provider or not model_name:
            msg = f"supervisor_model must have non-empty provider and model name, got {value!r}"
            raise ValueError(msg)

        return value

    # -- Runtime validation --------------------------------------------------

    def validate_provider_keys(self) -> None:
        """Validate that required provider credentials are present.

        Checks two things:

        1. The ``memory_store_backend`` is ``"in_memory"`` (only backend
           implemented in Phase 1).
        2. The provider extracted from ``supervisor_model`` has the required
           API key or base URL configured.

        Raises:
            ConfigurationError: With a clear message naming the missing
                environment variable.
        """
        # Phase 1: only in_memory backend is supported
        if self.memory_store_backend != "in_memory":
            raise ConfigurationError(
                f"{self.memory_store_backend} backend is not implemented in Phase 1"
            )

        # Phase 2: warn (do not raise) if Tavily is selected without an API key.
        # Web search is optional/best-effort, so a missing key downgrades the
        # capability rather than breaking startup.
        if self.web_search_provider == "tavily":
            tavily_key = self.tavily_api_key
            tavily_value = (
                tavily_key.get_secret_value()
                if isinstance(tavily_key, SecretStr)
                else tavily_key
            )
            if not tavily_value:
                message = (
                    "web_search_provider='tavily' but TAVILY_API_KEY "
                    "(JARVIS_TAVILY_API_KEY) is not set — web search will be "
                    "disabled."
                )
                warnings.warn(message, stacklevel=2)
                logger.warning(message)

        provider = self.supervisor_model.split(":", 1)[0]

        requirement = _PROVIDER_KEY_REQUIREMENTS.get(provider)
        if requirement is None:
            # Unknown provider — nothing to validate
            return

        field_name, env_var_name = requirement
        field_value = getattr(self, field_name, None)

        # SecretStr wraps the value — check if it's set
        if isinstance(field_value, SecretStr):
            if not field_value.get_secret_value():
                raise ConfigurationError(f"Provider '{provider}' requires {env_var_name} to be set")
        elif not field_value:
            raise ConfigurationError(f"Provider '{provider}' requires {env_var_name} to be set")
