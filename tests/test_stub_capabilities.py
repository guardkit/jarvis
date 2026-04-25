"""Tests for `src/jarvis/config/stub_capabilities.yaml` (TASK-J002-002).

Covers acceptance criteria:

- AC-001: File exists at ``src/jarvis/config/stub_capabilities.yaml`` containing
  exactly four capabilities: ``architect-agent``, ``product-owner-agent``,
  ``ideation-agent``, ``forge``.
- AC-002: Content matches byte-for-byte the canonical YAML in
  ``DM-stub-registry.md`` §"Canonical Phase 2 content".
- AC-003: All ``agent_id`` values are kebab-case; all ``tool_name`` values are
  snake_case; all ``trust_tier`` values are one of
  ``core | specialist | extension``.
- AC-004: ``forge`` entry carries a ``build_feature`` capability so the
  reasoning model sees Forge alongside specialists in the catalogue.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STUB_YAML_PATH = PROJECT_ROOT / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
DM_REGISTRY_MD = (
    PROJECT_ROOT
    / "docs"
    / "design"
    / "FEAT-JARVIS-002"
    / "models"
    / "DM-stub-registry.md"
)

EXPECTED_AGENT_IDS: list[str] = [
    "architect-agent",
    "product-owner-agent",
    "ideation-agent",
    "forge",
]

VALID_TRUST_TIERS: set[str] = {"core", "specialist", "extension"}

KEBAB_CASE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def stub_yaml_text() -> str:
    """Raw text contents of the stub YAML file."""
    return STUB_YAML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def stub_yaml_data(stub_yaml_text: str) -> dict[str, Any]:
    """Parsed YAML mapping of the stub registry."""
    parsed = yaml.safe_load(stub_yaml_text)
    assert isinstance(parsed, dict), "stub_capabilities.yaml root must be a mapping"
    return parsed


@pytest.fixture(scope="module")
def canonical_yaml_text() -> str:
    """Canonical YAML extracted verbatim from DM-stub-registry.md §Canonical Phase 2 content."""
    md = DM_REGISTRY_MD.read_text(encoding="utf-8")
    section_marker = "Canonical Phase 2 content"
    idx = md.index(section_marker)
    section = md[idx:]
    fence_open = "```yaml\n"
    start = section.index(fence_open) + len(fence_open)
    end = section.index("```", start)
    return section[start:end]


# ---------------------------------------------------------------------------
# AC-001: file exists and contains exactly four expected capabilities
# ---------------------------------------------------------------------------
class TestAC001FileExistsWithFourCapabilities:
    """File exists at the canonical path and contains exactly four capabilities."""

    def test_stub_yaml_file_exists(self) -> None:
        assert STUB_YAML_PATH.is_file(), (
            f"Expected file at {STUB_YAML_PATH} but it does not exist"
        )

    def test_stub_yaml_has_four_capabilities(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        capabilities = stub_yaml_data.get("capabilities")
        assert isinstance(capabilities, list)
        assert len(capabilities) == 4

    def test_stub_yaml_agent_ids_match_expected_set(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        agent_ids = [entry["agent_id"] for entry in stub_yaml_data["capabilities"]]
        assert agent_ids == EXPECTED_AGENT_IDS

    def test_stub_yaml_has_version_key(self, stub_yaml_data: dict[str, Any]) -> None:
        assert stub_yaml_data.get("version") == "1.0"


# ---------------------------------------------------------------------------
# AC-002: byte-for-byte match with canonical content in DM-stub-registry.md
# ---------------------------------------------------------------------------
class TestAC002CanonicalByteForByteMatch:
    """File content matches byte-for-byte the YAML block in DM-stub-registry.md."""

    def test_byte_equal_to_canonical(
        self, stub_yaml_text: str, canonical_yaml_text: str
    ) -> None:
        assert stub_yaml_text == canonical_yaml_text

    def test_byte_lengths_match(
        self, stub_yaml_text: str, canonical_yaml_text: str
    ) -> None:
        assert len(stub_yaml_text.encode("utf-8")) == len(
            canonical_yaml_text.encode("utf-8")
        )


# ---------------------------------------------------------------------------
# AC-003: agent_id kebab-case, tool_name snake_case, trust_tier in allowed set
# ---------------------------------------------------------------------------
class TestAC003NamingAndTrustTier:
    """agent_id is kebab-case, tool_name is snake_case, trust_tier is allowed."""

    def test_all_agent_ids_are_kebab_case(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        for entry in stub_yaml_data["capabilities"]:
            agent_id = entry["agent_id"]
            assert KEBAB_CASE.match(agent_id), (
                f"agent_id {agent_id!r} is not kebab-case"
            )

    def test_all_tool_names_are_snake_case(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        for entry in stub_yaml_data["capabilities"]:
            for cap in entry["capability_list"]:
                tool_name = cap["tool_name"]
                assert SNAKE_CASE.match(tool_name), (
                    f"tool_name {tool_name!r} is not snake_case"
                )

    def test_all_trust_tiers_are_valid(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        for entry in stub_yaml_data["capabilities"]:
            tier = entry["trust_tier"]
            assert tier in VALID_TRUST_TIERS, (
                f"trust_tier {tier!r} not in {sorted(VALID_TRUST_TIERS)}"
            )


# ---------------------------------------------------------------------------
# AC-004: forge entry carries a build_feature capability
# ---------------------------------------------------------------------------
class TestAC004ForgeBuildFeatureCapability:
    """The forge entry exposes ``build_feature`` so it appears in the catalogue."""

    def test_forge_entry_present(self, stub_yaml_data: dict[str, Any]) -> None:
        forge = next(
            (
                entry
                for entry in stub_yaml_data["capabilities"]
                if entry["agent_id"] == "forge"
            ),
            None,
        )
        assert forge is not None, "forge entry missing from stub_capabilities.yaml"

    def test_forge_has_build_feature_capability(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        forge = next(
            entry
            for entry in stub_yaml_data["capabilities"]
            if entry["agent_id"] == "forge"
        )
        tool_names = [cap["tool_name"] for cap in forge["capability_list"]]
        assert "build_feature" in tool_names

    def test_forge_trust_tier_is_core(
        self, stub_yaml_data: dict[str, Any]
    ) -> None:
        """Forge is trust_tier=core per DM-stub-registry §Canonical Phase 2 content."""
        forge = next(
            entry
            for entry in stub_yaml_data["capabilities"]
            if entry["agent_id"] == "forge"
        )
        assert forge["trust_tier"] == "core"
