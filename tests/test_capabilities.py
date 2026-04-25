"""Tests for ``jarvis.tools.capabilities`` Pydantic models.

Validates DM-tool-types §1 contract:

* :class:`CapabilityToolSummary` — required fields, defaults, ``extra="ignore"``.
* :class:`CapabilityDescriptor` — kebab-case ``agent_id``, defaults, literal
  enums, ``extra="ignore"``.
* :meth:`CapabilityDescriptor.as_prompt_block` — byte-for-byte deterministic
  rendering matching DM-tool-types §"Prompt-block shape".
* Module-level invariant — no imports from forbidden domain packages
  (ADR-ARCH-002 leaf).
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary

# ---------------------------------------------------------------------------
# CapabilityToolSummary — AC-001
# ---------------------------------------------------------------------------


class TestCapabilityToolSummary:
    """AC-001 — model contract for CapabilityToolSummary."""

    def test_construct_with_required_fields_succeeds(self) -> None:
        summary = CapabilityToolSummary(
            tool_name="run_architecture_session",
            description="Drive a full /system-arch session.",
        )
        assert summary.tool_name == "run_architecture_session"
        assert summary.description == "Drive a full /system-arch session."
        assert summary.risk_level == "read_only"

    def test_risk_level_defaults_to_read_only(self) -> None:
        summary = CapabilityToolSummary(tool_name="t", description="d")
        assert summary.risk_level == "read_only"

    @pytest.mark.parametrize(
        "risk_level", ["read_only", "mutating", "destructive"]
    )
    def test_valid_risk_levels_accepted(self, risk_level: str) -> None:
        summary = CapabilityToolSummary(
            tool_name="t", description="d", risk_level=risk_level
        )
        assert summary.risk_level == risk_level

    def test_invalid_risk_level_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(
                tool_name="t", description="d", risk_level="catastrophic"
            )

    def test_empty_tool_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(tool_name="", description="d")

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(tool_name="t", description="")

    def test_extra_fields_ignored(self) -> None:
        """ConfigDict(extra='ignore') — forward-compatible with new fields."""
        summary = CapabilityToolSummary.model_validate(
            {
                "tool_name": "t",
                "description": "d",
                "risk_level": "mutating",
                "future_field": "should-not-raise",
            }
        )
        assert summary.tool_name == "t"
        assert not hasattr(summary, "future_field")


# ---------------------------------------------------------------------------
# CapabilityDescriptor — AC-002
# ---------------------------------------------------------------------------


class TestCapabilityDescriptor:
    """AC-002 — model contract for CapabilityDescriptor."""

    def test_construct_with_required_fields_succeeds(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description="Designs systems.",
        )
        assert descriptor.agent_id == "architect-agent"
        assert descriptor.role == "Architect"
        assert descriptor.description == "Designs systems."
        assert descriptor.capability_list == []
        assert descriptor.cost_signal == "unknown"
        assert descriptor.latency_signal == "unknown"
        assert descriptor.last_heartbeat_at is None
        assert descriptor.trust_tier == "specialist"

    @pytest.mark.parametrize(
        "agent_id",
        ["a", "ab", "abc-def", "agent1", "a1-b2-c3", "architect-agent"],
    )
    def test_valid_kebab_case_agent_ids_accepted(self, agent_id: str) -> None:
        descriptor = CapabilityDescriptor(
            agent_id=agent_id, role="r", description="d"
        )
        assert descriptor.agent_id == agent_id

    @pytest.mark.parametrize(
        "agent_id",
        [
            "",  # empty
            "1agent",  # leading digit
            "-agent",  # leading hyphen
            "Agent",  # uppercase
            "agent_id",  # underscore
            "agent.id",  # dot
            "agent id",  # space
            "AGENT",  # all caps
        ],
    )
    def test_invalid_agent_ids_rejected(self, agent_id: str) -> None:
        with pytest.raises(ValidationError):
            CapabilityDescriptor(agent_id=agent_id, role="r", description="d")

    @pytest.mark.parametrize(
        "trust_tier", ["core", "specialist", "extension"]
    )
    def test_valid_trust_tiers_accepted(self, trust_tier: str) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="r", description="d", trust_tier=trust_tier
        )
        assert descriptor.trust_tier == trust_tier

    def test_invalid_trust_tier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityDescriptor(
                agent_id="a", role="r", description="d", trust_tier="rogue"
            )

    def test_capability_list_holds_summaries(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a",
            role="r",
            description="d",
            capability_list=[
                CapabilityToolSummary(tool_name="t1", description="d1"),
                CapabilityToolSummary(tool_name="t2", description="d2"),
            ],
        )
        assert len(descriptor.capability_list) == 2
        assert descriptor.capability_list[0].tool_name == "t1"

    def test_capability_list_coerces_dicts(self) -> None:
        descriptor = CapabilityDescriptor.model_validate(
            {
                "agent_id": "a",
                "role": "r",
                "description": "d",
                "capability_list": [
                    {"tool_name": "t1", "description": "d1"},
                ],
            }
        )
        assert isinstance(descriptor.capability_list[0], CapabilityToolSummary)

    def test_last_heartbeat_at_accepts_datetime(self) -> None:
        ts = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
        descriptor = CapabilityDescriptor(
            agent_id="a", role="r", description="d", last_heartbeat_at=ts
        )
        assert descriptor.last_heartbeat_at == ts

    def test_extra_fields_ignored(self) -> None:
        """ConfigDict(extra='ignore') — forward-compatible with new manifest fields."""
        descriptor = CapabilityDescriptor.model_validate(
            {
                "agent_id": "a",
                "role": "r",
                "description": "d",
                "container_id": "must-be-stripped",  # infrastructure leak
                "future_field": 42,
            }
        )
        assert not hasattr(descriptor, "container_id")
        assert not hasattr(descriptor, "future_field")


# ---------------------------------------------------------------------------
# as_prompt_block — AC-003
# ---------------------------------------------------------------------------


class TestAsPromptBlock:
    """AC-003 — deterministic prompt-block rendering matching DM-tool-types."""

    def test_byte_for_byte_matches_dm_tool_types_example(self) -> None:
        """Render the exact example from DM-tool-types.md §Prompt-block shape."""
        descriptor = CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description=(
                "Produces architecture sessions, C4 diagrams, and ADRs for "
                "features. Prefers\nevidence-based decisions grounded in the "
                "existing ARCHITECTURE.md."
            ),
            cost_signal="moderate",
            latency_signal="5-30s",
            trust_tier="specialist",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="run_architecture_session",
                    description=(
                        "Drive a full /system-arch\nsession end-to-end "
                        "from a scope document."
                    ),
                    risk_level="read_only",
                ),
                CapabilityToolSummary(
                    tool_name="draft_adr",
                    description=(
                        "Produce a new ADR file given context + decision."
                    ),
                    risk_level="mutating",
                ),
            ],
        )

        expected = (
            "### architect-agent — Architect "
            "(trust: specialist, cost: moderate, latency: 5-30s)\n"
            "\n"
            "Produces architecture sessions, C4 diagrams, and ADRs for "
            "features. Prefers\n"
            "evidence-based decisions grounded in the existing "
            "ARCHITECTURE.md.\n"
            "\n"
            "Tools:\n"
            "  - run_architecture_session (read_only) — "
            "Drive a full /system-arch\n"
            "    session end-to-end from a scope document.\n"
            "  - draft_adr (mutating) — Produce a new ADR file given "
            "context + decision."
        )

        assert descriptor.as_prompt_block() == expected

    def test_render_is_deterministic(self) -> None:
        """Same descriptor renders to the same bytes every call."""
        descriptor = CapabilityDescriptor(
            agent_id="a",
            role="r",
            description="d",
            capability_list=[
                CapabilityToolSummary(tool_name="t", description="td"),
            ],
        )
        assert descriptor.as_prompt_block() == descriptor.as_prompt_block()

    def test_no_capabilities_renders_tools_header_only(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="R", description="d"
        )
        block = descriptor.as_prompt_block()
        assert block.endswith("\nTools:")
        assert (
            block
            == "### a — R (trust: specialist, cost: unknown, latency: unknown)"
            "\n\nd\n\nTools:"
        )

    def test_default_signals_render_unknown(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="x-y", role="X-Role", description="desc"
        )
        first_line = descriptor.as_prompt_block().splitlines()[0]
        assert (
            first_line
            == "### x-y — X-Role (trust: specialist, cost: unknown, "
            "latency: unknown)"
        )

    def test_trust_tier_appears_in_header(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="x",
            role="R",
            description="d",
            trust_tier="core",
        )
        first_line = descriptor.as_prompt_block().splitlines()[0]
        assert "trust: core" in first_line

    def test_returns_str(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="r", description="d"
        )
        assert isinstance(descriptor.as_prompt_block(), str)


# ---------------------------------------------------------------------------
# Import-graph leaf invariant — AC-004
# ---------------------------------------------------------------------------


class TestModuleIsLeaf:
    """AC-004 — capabilities.py must not import from agents/infrastructure/cli."""

    FORBIDDEN_PREFIXES = (
        "jarvis.agents",
        "jarvis.infrastructure",
        "jarvis.cli",
    )

    def _capabilities_path(self) -> pathlib.Path:
        return (
            pathlib.Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "tools"
            / "capabilities.py"
        )

    def test_no_forbidden_static_imports(self) -> None:
        tree = ast.parse(self._capabilities_path().read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        violations = [
            imp
            for imp in imports
            for prefix in self.FORBIDDEN_PREFIXES
            if imp == prefix or imp.startswith(prefix + ".")
        ]
        assert violations == [], (
            f"capabilities.py must be a leaf — forbidden imports: {violations}"
        )
