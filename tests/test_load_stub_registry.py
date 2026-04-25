"""Tests for ``jarvis.tools.capabilities.load_stub_registry`` (TASK-J002-006).

Validates the loader contract documented in DM-stub-registry.md:

- AC-001: ``load_stub_registry(path: Path) -> list[CapabilityDescriptor]``
  exists in ``src/jarvis/tools/capabilities.py``.
- AC-002: Loads YAML at ``path``, validates entries against
  :class:`CapabilityDescriptor`, returns the list preserving YAML order.
- AC-003: Raises ``FileNotFoundError`` if ``path`` does not exist.
- AC-004: Raises ``pydantic.ValidationError`` if any descriptor is malformed.
- AC-005: Rejects duplicate ``agent_id`` entries with a ``ValueError`` whose
  message names the duplicated id.
- AC-006: Uses ``yaml.safe_load`` (never ``yaml.load``).
"""

from __future__ import annotations

import inspect
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from jarvis.tools import capabilities as capabilities_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    load_stub_registry,
)

# ---------------------------------------------------------------------------
# Path constants — point at the canonical Phase 2 stub for round-trip tests
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STUB_YAML_PATH = PROJECT_ROOT / "src" / "jarvis" / "config" / "stub_capabilities.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_yaml(path: Path, data: Any) -> Path:
    """Dump ``data`` to ``path`` as YAML and return the path."""
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC-001: function signature + module export
# ---------------------------------------------------------------------------
class TestAC001LoaderSignature:
    """The loader exists with the documented ``(Path) -> list[...]`` shape."""

    def test_load_stub_registry_is_exported_from_module(self) -> None:
        assert hasattr(capabilities_module, "load_stub_registry")

    def test_load_stub_registry_in_dunder_all(self) -> None:
        assert "load_stub_registry" in capabilities_module.__all__

    def test_load_stub_registry_signature_takes_path_returns_list(self) -> None:
        sig = inspect.signature(load_stub_registry)
        params = list(sig.parameters.values())
        assert len(params) == 1
        assert params[0].name == "path"
        # Annotation may be the literal class or a string under
        # ``from __future__ import annotations``; accept both.
        assert params[0].annotation in (Path, "Path")


# ---------------------------------------------------------------------------
# AC-002: load + validate + preserve YAML order
# ---------------------------------------------------------------------------
class TestAC002LoadAndValidate:
    """Loads YAML, validates against :class:`CapabilityDescriptor`, preserves order."""

    def test_load_returns_list_of_capability_descriptors(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "a", "role": "R", "description": "d"},
                    {"agent_id": "b", "role": "R", "description": "d"},
                ],
            },
        )

        result = load_stub_registry(path)

        assert isinstance(result, list)
        assert all(isinstance(item, CapabilityDescriptor) for item in result)
        assert len(result) == 2

    def test_preserves_yaml_order(self, tmp_path: Path) -> None:
        ordered_ids = ["zebra", "apple", "mango", "banana"]
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": agent_id, "role": "R", "description": "d"}
                    for agent_id in ordered_ids
                ],
            },
        )

        result = load_stub_registry(path)

        assert [d.agent_id for d in result] == ordered_ids

    def test_loads_canonical_phase2_stub_file(self) -> None:
        """Round-trip: the canonical Phase 2 file under src/ loads cleanly."""
        result = load_stub_registry(STUB_YAML_PATH)

        assert [d.agent_id for d in result] == [
            "architect-agent",
            "product-owner-agent",
            "ideation-agent",
            "forge",
        ]

    def test_loaded_descriptor_carries_nested_capability_summaries(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {
                        "agent_id": "a",
                        "role": "R",
                        "description": "d",
                        "capability_list": [
                            {
                                "tool_name": "t1",
                                "description": "d1",
                                "risk_level": "mutating",
                            }
                        ],
                    },
                ],
            },
        )

        descriptor = load_stub_registry(path)[0]

        assert len(descriptor.capability_list) == 1
        assert descriptor.capability_list[0].tool_name == "t1"
        assert descriptor.capability_list[0].risk_level == "mutating"

    def test_empty_capability_list_yields_empty_result(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {"version": "1.0", "capabilities": []},
        )

        assert load_stub_registry(path) == []


# ---------------------------------------------------------------------------
# AC-003: missing file -> FileNotFoundError
# ---------------------------------------------------------------------------
class TestAC003MissingFileRaises:
    """A missing path is startup-fatal (FEAT-JARVIS-002 design §7)."""

    def test_nonexistent_path_raises_file_not_found_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.yaml"

        with pytest.raises(FileNotFoundError):
            load_stub_registry(missing)

    def test_file_not_found_error_message_includes_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing-registry.yaml"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_stub_registry(missing)

        assert str(missing) in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-004: malformed entry -> pydantic.ValidationError
# ---------------------------------------------------------------------------
class TestAC004MalformedEntryRaisesValidationError:
    """Any entry that fails :class:`CapabilityDescriptor` validation surfaces."""

    def test_uppercase_agent_id_raises_validation_error(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "Architect", "role": "R", "description": "d"},
                ],
            },
        )

        with pytest.raises(ValidationError):
            load_stub_registry(path)

    def test_missing_required_field_raises_validation_error(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    # Missing ``description``.
                    {"agent_id": "a", "role": "R"},
                ],
            },
        )

        with pytest.raises(ValidationError):
            load_stub_registry(path)

    def test_unknown_risk_level_raises_validation_error(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {
                        "agent_id": "a",
                        "role": "R",
                        "description": "d",
                        "capability_list": [
                            {
                                "tool_name": "t",
                                "description": "d",
                                "risk_level": "catastrophic",
                            }
                        ],
                    }
                ],
            },
        )

        with pytest.raises(ValidationError):
            load_stub_registry(path)

    def test_invalid_trust_tier_raises_validation_error(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {
                        "agent_id": "a",
                        "role": "R",
                        "description": "d",
                        "trust_tier": "rogue",
                    }
                ],
            },
        )

        with pytest.raises(ValidationError):
            load_stub_registry(path)


# ---------------------------------------------------------------------------
# AC-005: duplicate agent_id -> ValueError mentioning the duplicate
# ---------------------------------------------------------------------------
class TestAC005DuplicateAgentIdRejected:
    """Duplicate ``agent_id`` raises ``ValueError`` and names the offender."""

    def test_duplicate_agent_id_raises_value_error(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "twin", "role": "R", "description": "d"},
                    {"agent_id": "twin", "role": "R", "description": "d"},
                ],
            },
        )

        with pytest.raises(ValueError) as exc_info:
            load_stub_registry(path)

        assert "twin" in str(exc_info.value)

    def test_duplicate_in_middle_of_list_detected(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "first", "role": "R", "description": "d"},
                    {"agent_id": "second", "role": "R", "description": "d"},
                    {"agent_id": "first", "role": "R", "description": "d"},
                ],
            },
        )

        with pytest.raises(ValueError, match="first"):
            load_stub_registry(path)

    def test_pydantic_validation_error_is_not_value_error(self, tmp_path: Path) -> None:
        """A malformed entry must raise ValidationError, not the duplicate ValueError."""
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "Bad", "role": "R", "description": "d"},
                ],
            },
        )

        with pytest.raises(ValidationError):
            load_stub_registry(path)


# ---------------------------------------------------------------------------
# AC-006: uses yaml.safe_load (never yaml.load)
# ---------------------------------------------------------------------------
class TestAC006UsesSafeLoad:
    """The loader uses ``yaml.safe_load``; ``yaml.load`` must never be called."""

    def test_safe_load_invoked(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path / "stub.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "a", "role": "R", "description": "d"},
                ],
            },
        )

        with patch.object(
            capabilities_module.yaml,
            "safe_load",
            wraps=capabilities_module.yaml.safe_load,
        ) as spy:
            load_stub_registry(path)

        assert spy.call_count == 1

    def test_capabilities_module_source_does_not_call_yaml_load(self) -> None:
        """Static check — `yaml.load(` must not appear anywhere in the file."""
        source = Path(inspect.getfile(capabilities_module)).read_text(encoding="utf-8")
        # ``yaml.safe_load`` is allowed; ``yaml.load(`` (with an open paren)
        # is the call we forbid. Use a strict substring check.
        assert "yaml.load(" not in source


# ---------------------------------------------------------------------------
# Defensive shape checks (root must be a mapping with a list of capabilities)
# ---------------------------------------------------------------------------
class TestRootShapeValidation:
    """The root document must be a mapping with a list-valued ``capabilities`` key."""

    def test_non_mapping_root_raises_value_error(self, tmp_path: Path) -> None:
        path = tmp_path / "stub.yaml"
        path.write_text("- just\n- a\n- list\n", encoding="utf-8")

        with pytest.raises(ValueError):
            load_stub_registry(path)

    def test_missing_capabilities_key_raises_value_error(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path / "stub.yaml", {"version": "1.0"})

        with pytest.raises(ValueError):
            load_stub_registry(path)

    def test_capabilities_not_a_list_raises_value_error(self, tmp_path: Path) -> None:
        path = tmp_path / "stub.yaml"
        path.write_text(
            textwrap.dedent(
                """\
                version: "1.0"
                capabilities:
                  agent_id: a
                  role: R
                  description: d
                """
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError):
            load_stub_registry(path)
