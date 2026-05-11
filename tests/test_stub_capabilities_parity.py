"""Parity assertion: every tool in ``stub_capabilities.yaml`` carries ``parameters``.

Closes F2 from TASK-REV-9939 review (DDR-021 NATS-down soft-fail regression):
under degraded operation the stub fallback must render the same
``Args (required):`` block as the live registry, so the supervisor's
``{available_capabilities}`` prompt is shape-stable across the live↔stub
swap. A stub entry that omits ``parameters:`` regresses the supervisor to
schema-guessing — the failure mode that originally surfaced as 3×
``Missing required arguments for 'align'`` rejections in 6ms on 2026-05-08.

Authoritative DDR amendment: see
``docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md``
§Amendments — 2026-05-13.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
    load_stub_registry,
)

# Stub registry path is conventionally ``src/jarvis/config/stub_capabilities.yaml``;
# resolve relative to the repo root so the test runs from any cwd.
_STUB_PATH = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "jarvis"
    / "config"
    / "stub_capabilities.yaml"
)


@pytest.fixture(scope="module")
def stub_descriptors() -> list[CapabilityDescriptor]:
    """Load the stub registry once per test module."""
    return load_stub_registry(_STUB_PATH)


def _iter_tools(
    descriptors: list[CapabilityDescriptor],
) -> list[tuple[str, CapabilityToolSummary]]:
    """Flatten the descriptor list into ``(agent_id.tool_name, summary)`` pairs."""
    return [
        (f"{descriptor.agent_id}.{tool.tool_name}", tool)
        for descriptor in descriptors
        for tool in descriptor.capability_list
    ]


class TestStubCapabilitiesParity:
    """DDR-021 amendment: every stub tool must carry a non-None parameters block."""

    def test_every_tool_has_non_none_parameters(
        self, stub_descriptors: list[CapabilityDescriptor]
    ) -> None:
        """Every tool entry parses with ``parameters is not None``.

        Failure message names the offending ``agent_id.tool_name`` so the
        operator knows where to add the missing block in the YAML.
        """
        offenders = [
            qualified_name
            for qualified_name, tool in _iter_tools(stub_descriptors)
            if tool.parameters is None
        ]

        assert not offenders, (
            "stub_capabilities.yaml regression — the following tools have no "
            "parameters: block, which would render no Args (required): in the "
            "supervisor prompt under DDR-021 NATS-down soft-fail. Add a "
            "parameters: block per the upstream specialist-agent manifest "
            "shape (see DDR-021 amendment 2026-05-13). Offending tools: "
            f"{offenders}"
        )

    def test_every_tool_parameters_is_object_with_properties(
        self, stub_descriptors: list[CapabilityDescriptor]
    ) -> None:
        """Each parameters block is a JSON-Schema object with a properties map.

        This is the minimum shape ``_render_required_args`` needs to render
        the ``Args (required):`` block without falling through to the
        ``(unknown):`` defensive path. Catches malformed entries earlier
        than the snapshot test would.
        """
        malformed = []
        for qualified_name, tool in _iter_tools(stub_descriptors):
            params = tool.parameters
            if params is None:
                # Covered by the previous test; skip to keep the message focused.
                continue
            if params.get("type") != "object":
                malformed.append((qualified_name, "type != 'object'"))
                continue
            properties = params.get("properties")
            if not isinstance(properties, dict):
                malformed.append((qualified_name, "properties missing or not a dict"))

        assert not malformed, (
            "stub_capabilities.yaml has parameters: blocks that are not "
            f"JSON-Schema objects with a properties map: {malformed}"
        )

    def test_required_keys_resolve_in_properties(
        self, stub_descriptors: list[CapabilityDescriptor]
    ) -> None:
        """Every key in ``required`` has a matching entry under ``properties``.

        Manifest hygiene check: a required key absent from properties would
        render as ``(unknown):`` per the defensive render path — that's a
        last-resort surface, not the steady state.
        """
        gaps = []
        for qualified_name, tool in _iter_tools(stub_descriptors):
            params = tool.parameters
            if params is None:
                continue
            required = params.get("required") or []
            properties = params.get("properties") or {}
            for key in required:
                if key not in properties:
                    gaps.append(f"{qualified_name}: required key {key!r} missing from properties")

        assert not gaps, (
            "stub_capabilities.yaml manifest hygiene gap — required keys "
            f"absent from properties: {gaps}"
        )
