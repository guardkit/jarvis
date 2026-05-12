"""Tests for :mod:`jarvis.infrastructure.manifest`.

TASK-J006-001 acceptance criteria coverage:

- AC-001: module exports ``build_manifest(config: JarvisConfig) -> AgentManifest``
- AC-002: returned manifest carries ``agent_id == "jarvis"``
- AC-003: exactly one ``ToolCapability`` named ``"chat"`` whose
  parameter schema documents ``message`` (required, str),
  ``conversation_history`` (optional, list), and ``adapter``
  (optional, str)
- AC-004: exactly one ``IntentCapability`` describing natural-language
  chat routing with non-empty ``signals`` (Bug #5 regression guard)
- AC-005: ``version`` field matches the existing fleet-register
  convention (sourced from ``config.jarvis_agent_version``)
"""

from __future__ import annotations

import inspect

import pytest
from nats_core import AgentManifest, IntentCapability, ToolCapability

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import manifest as manifest_module
from jarvis.infrastructure.fleet_registration import build_jarvis_manifest
from jarvis.infrastructure.manifest import build_manifest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def jarvis_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` with default semver agent version.

    Default ``jarvis_agent_version`` ("0.4.0") is valid semver so the
    manifest validates without overrides.
    """
    return JarvisConfig(llama_swap_base_url="http://fake-endpoint")


# ---------------------------------------------------------------------------
# AC-001 — module exports the factory with the right signature
# ---------------------------------------------------------------------------


class TestModuleSurface:
    """AC-001: ``build_manifest(config: JarvisConfig) -> AgentManifest``."""

    def test_module_exports_build_manifest_callable(self) -> None:
        assert hasattr(manifest_module, "build_manifest")
        assert callable(manifest_module.build_manifest)

    def test_build_manifest_is_listed_in_all(self) -> None:
        assert "build_manifest" in manifest_module.__all__

    def test_build_manifest_signature_takes_config_returns_manifest(self) -> None:
        sig = inspect.signature(build_manifest)
        params = list(sig.parameters.values())
        assert len(params) == 1
        (param,) = params
        assert param.name == "config"
        assert param.annotation in (JarvisConfig, "JarvisConfig")
        assert sig.return_annotation in (AgentManifest, "AgentManifest")

    def test_build_manifest_returns_agent_manifest_instance(
        self, jarvis_config: JarvisConfig
    ) -> None:
        manifest = build_manifest(jarvis_config)
        assert isinstance(manifest, AgentManifest)


# ---------------------------------------------------------------------------
# AC-002 — agent_id == "jarvis" (matches existing fleet.register)
# ---------------------------------------------------------------------------


class TestAgentIdMatchesFleetRegister:
    """AC-002: ``agent_id`` is the literal ``"jarvis"``."""

    def test_agent_id_is_jarvis(self, jarvis_config: JarvisConfig) -> None:
        manifest = build_manifest(jarvis_config)
        assert manifest.agent_id == "jarvis"

    def test_agent_id_matches_existing_fleet_register_factory(
        self, jarvis_config: JarvisConfig
    ) -> None:
        """Both factories must publish under the same fleet entry."""
        new = build_manifest(jarvis_config)
        existing = build_jarvis_manifest(jarvis_config)
        assert new.agent_id == existing.agent_id == "jarvis"


# ---------------------------------------------------------------------------
# AC-003 — single ToolCapability(name="chat") with documented schema
# ---------------------------------------------------------------------------


class TestChatToolCapability:
    """AC-003: exactly one ``ToolCapability`` named ``chat``."""

    def test_exactly_one_tool_capability(self, jarvis_config: JarvisConfig) -> None:
        manifest = build_manifest(jarvis_config)
        assert len(manifest.tools) == 1

    def test_only_tool_is_chat(self, jarvis_config: JarvisConfig) -> None:
        (tool,) = build_manifest(jarvis_config).tools
        assert isinstance(tool, ToolCapability)
        assert tool.name == "chat"

    def test_chat_tool_parameter_schema_is_object(self, jarvis_config: JarvisConfig) -> None:
        (tool,) = build_manifest(jarvis_config).tools
        assert tool.parameters.get("type") == "object"
        assert "properties" in tool.parameters

    def test_chat_tool_message_is_required_string(self, jarvis_config: JarvisConfig) -> None:
        (tool,) = build_manifest(jarvis_config).tools
        props = tool.parameters["properties"]
        assert "message" in props
        assert props["message"].get("type") == "string"
        assert "message" in tool.parameters.get("required", [])

    def test_chat_tool_conversation_history_is_optional_list(
        self, jarvis_config: JarvisConfig
    ) -> None:
        (tool,) = build_manifest(jarvis_config).tools
        props = tool.parameters["properties"]
        assert "conversation_history" in props
        assert props["conversation_history"].get("type") == "array"
        # optional ⇒ MUST NOT appear in the required list
        assert "conversation_history" not in tool.parameters.get("required", [])

    def test_chat_tool_adapter_is_optional_string(self, jarvis_config: JarvisConfig) -> None:
        (tool,) = build_manifest(jarvis_config).tools
        props = tool.parameters["properties"]
        assert "adapter" in props
        assert props["adapter"].get("type") == "string"
        assert "adapter" not in tool.parameters.get("required", [])


# ---------------------------------------------------------------------------
# AC-004 — single IntentCapability with non-empty signals (Bug #5 guard)
# ---------------------------------------------------------------------------


class TestGeneralIntentCapability:
    """AC-004: one ``IntentCapability`` describing natural-language chat."""

    def test_exactly_one_intent_capability(self, jarvis_config: JarvisConfig) -> None:
        manifest = build_manifest(jarvis_config)
        assert len(manifest.intents) == 1

    def test_intent_is_intent_capability(self, jarvis_config: JarvisConfig) -> None:
        (intent,) = build_manifest(jarvis_config).intents
        assert isinstance(intent, IntentCapability)

    def test_intent_pattern_routes_general_chat(self, jarvis_config: JarvisConfig) -> None:
        (intent,) = build_manifest(jarvis_config).intents
        # ``general`` must appear in the pattern so downstream routers
        # can resolve natural-language chat traffic to jarvis.
        assert "general" in intent.pattern

    def test_intent_signals_are_non_empty_bug5_guard(self, jarvis_config: JarvisConfig) -> None:
        """Bug #5 regression guard — empty signals are routinely ignored."""
        (intent,) = build_manifest(jarvis_config).intents
        assert intent.signals  # non-empty list
        assert all(isinstance(s, str) and s for s in intent.signals)

    def test_intent_description_is_non_empty(self, jarvis_config: JarvisConfig) -> None:
        (intent,) = build_manifest(jarvis_config).intents
        assert intent.description
        assert intent.description.strip()


# ---------------------------------------------------------------------------
# AC-005 — version matches existing fleet-register convention
# ---------------------------------------------------------------------------


class TestManifestVersionConvention:
    """AC-005: ``version`` mirrors ``config.jarvis_agent_version``."""

    def test_version_uses_config_jarvis_agent_version(self, jarvis_config: JarvisConfig) -> None:
        manifest = build_manifest(jarvis_config)
        assert manifest.version == jarvis_config.jarvis_agent_version

    def test_version_matches_fleet_register_factory(self, jarvis_config: JarvisConfig) -> None:
        new = build_manifest(jarvis_config)
        existing = build_jarvis_manifest(jarvis_config)
        assert new.version == existing.version

    def test_version_propagates_custom_value(self) -> None:
        custom = JarvisConfig(
            llama_swap_base_url="http://fake-endpoint",
            jarvis_agent_version="1.2.3",
        )
        manifest = build_manifest(custom)
        assert manifest.version == "1.2.3"


# ---------------------------------------------------------------------------
# Purity — factory must be deterministic given the same config
# ---------------------------------------------------------------------------


class TestFactoryPurity:
    """The factory is documented as pure — two calls produce equal output."""

    def test_two_invocations_produce_equal_manifests(self, jarvis_config: JarvisConfig) -> None:
        first = build_manifest(jarvis_config)
        second = build_manifest(jarvis_config)
        # AgentManifest is a pydantic BaseModel — equality is field-wise.
        assert first == second
