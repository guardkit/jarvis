"""Capability descriptor models — supervisor-facing projection of fleet manifests.

Defines :class:`CapabilityToolSummary` and :class:`CapabilityDescriptor`,
the Pydantic models the reasoning model reads to decide which fleet agent /
tool to dispatch. They are deliberately a *subset* of
``nats_core.AgentManifest`` — not every manifest field is useful to the model
and some (e.g. ``container_id``) leak infrastructure (ADR-ARCH-002).

The :meth:`CapabilityDescriptor.as_prompt_block` method renders a
deterministic, token-cheap text block. The supervisor's
``{available_capabilities}`` placeholder is filled by joining these blocks
with double newlines.

Model contract — DM-tool-types §1.

This module is a leaf in the import graph (ADR-ARCH-002): it must not import
from ``jarvis.agents.*``, ``jarvis.infrastructure.*``, or ``jarvis.cli.*``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "CapabilityDescriptor",
    "CapabilityToolSummary",
    "load_stub_registry",
]


class CapabilityToolSummary(BaseModel):
    """A single tool exposed by a fleet agent, as surfaced to Jarvis.

    Attributes:
        tool_name: Maps 1:1 to ``nats_core.ToolCapability.name``.
        description: Human-readable description the reasoning model reads
                     at decision time.
        risk_level: Risk classification for approval gating.
    """

    model_config = ConfigDict(extra="ignore")

    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["read_only", "mutating", "destructive"] = "read_only"


class CapabilityDescriptor(BaseModel):
    """A fleet agent's capabilities as rendered into Jarvis's context.

    Attributes:
        agent_id: Kebab-case identifier. Matches ``AgentManifest.agent_id``.
        role: Human-readable role name (e.g. "Architect", "Product Owner").
              Derived from ``AgentManifest.name`` in Phase 3+.
        description: One-paragraph description of what this agent does best —
                     surfaces in ``{available_capabilities}`` prompt block.
        capability_list: The ToolCapability summaries Jarvis can dispatch to.
        cost_signal: Human-readable cost indicator (e.g. "low", "~$0.10/call").
        latency_signal: Human-readable latency indicator (e.g. "5-30s",
                        "sub-second").
        last_heartbeat_at: Timestamp of last heartbeat received. ``None`` in
                           Phase 2 (no heartbeats yet); populated in Phase 3.
        trust_tier: Trust classification, mapped from
                    ``AgentManifest.trust_tier``.
    """

    model_config = ConfigDict(extra="ignore")

    agent_id: str = Field(
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Kebab-case agent identifier",
    )
    role: str = Field(min_length=1)
    description: str = Field(min_length=1)
    capability_list: list[CapabilityToolSummary] = Field(default_factory=list)
    cost_signal: str = Field(default="unknown")
    latency_signal: str = Field(default="unknown")
    last_heartbeat_at: datetime | None = None
    trust_tier: Literal["core", "specialist", "extension"] = "specialist"

    def as_prompt_block(self) -> str:
        """Render this descriptor as a prompt-friendly text block.

        The output is deterministic and matches DM-tool-types §"Prompt-block
        shape" byte-for-byte:

        * Line 1 — ``### {agent_id} — {role} (trust: {trust_tier}, cost:
          {cost_signal}, latency: {latency_signal})``
        * Blank line
        * ``description`` rendered verbatim (any embedded newlines preserved)
        * Blank line
        * ``Tools:``
        * One line per capability ``  - {tool_name} ({risk_level}) —
          {description}`` with continuation lines indented 4 spaces

        Joining multiple descriptor blocks with ``"\\n\\n"`` produces the
        ``{available_capabilities}`` prompt fragment.
        """
        header = (
            f"### {self.agent_id} — {self.role} "
            f"(trust: {self.trust_tier}, cost: {self.cost_signal}, "
            f"latency: {self.latency_signal})"
        )
        lines: list[str] = [header, "", self.description, "", "Tools:"]
        for tool in self.capability_list:
            # 4-space continuation indent for any embedded newlines so the
            # block remains visually clean when consumed by the model.
            indented_description = tool.description.replace("\n", "\n    ")
            lines.append(f"  - {tool.tool_name} ({tool.risk_level}) — {indented_description}")
        return "\n".join(lines)


def load_stub_registry(path: Path) -> list[CapabilityDescriptor]:
    """Load the Phase 2 stub capability registry from a YAML file.

    Reads ``path`` with ``yaml.safe_load`` (never ``yaml.load`` — see
    DM-stub-registry §"Validation tests"), validates each entry under
    ``capabilities`` against :class:`CapabilityDescriptor`, and returns the
    resulting list in the order it appeared in the source document.

    A missing file is **startup-fatal** per the FEAT-JARVIS-002 design §7:
    Jarvis cannot route dispatches without a capability catalogue, so the
    loader raises ``FileNotFoundError`` rather than degrading to an empty
    registry.

    Duplicate ``agent_id`` entries are rejected with a ``ValueError`` naming
    the offending id; downstream routing assumes ``agent_id`` is the
    identity key for a descriptor.

    Args:
        path: Filesystem path to the stub capabilities YAML document. Expected
            shape is documented in ``DM-stub-registry.md``::

                version: "1.0"
                capabilities:
                  - agent_id: ...
                    role: ...
                    description: ...
                    ...

    Returns:
        ``list[CapabilityDescriptor]`` — descriptors in the order they appear
        under the ``capabilities`` list in the YAML document.

    Raises:
        FileNotFoundError: ``path`` does not exist on disk.
        pydantic.ValidationError: One or more entries fails
            :class:`CapabilityDescriptor` validation (e.g. uppercase
            ``agent_id``, missing required field, unknown ``risk_level``).
        ValueError: Two or more entries share the same ``agent_id``, or the
            document root is not a mapping with a list-valued ``capabilities``
            key.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Stub capability registry not found at {path!s} — startup-fatal "
            "per FEAT-JARVIS-002 design §7."
        )

    with path.open("r", encoding="utf-8") as handle:
        # ``yaml.safe_load`` (never ``yaml.load``) — DM-stub-registry §Schema.
        raw: Any = yaml.safe_load(handle)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Stub capability registry at {path!s} must be a YAML mapping "
            f"with a 'capabilities' key; got {type(raw).__name__}."
        )

    entries = raw.get("capabilities")
    if not isinstance(entries, list):
        raise ValueError(
            f"Stub capability registry at {path!s} must contain a list under "
            f"'capabilities'; got {type(entries).__name__}."
        )

    descriptors: list[CapabilityDescriptor] = [
        CapabilityDescriptor.model_validate(entry) for entry in entries
    ]

    # Reject duplicate agent_id values. Use a manual loop (not a set
    # comparison) so the error message names the first duplicate encountered,
    # which is what an operator needs to grep for in the offending YAML.
    seen: set[str] = set()
    for descriptor in descriptors:
        if descriptor.agent_id in seen:
            raise ValueError(
                f"Duplicate agent_id {descriptor.agent_id!r} in stub "
                f"capability registry at {path!s}."
            )
        seen.add(descriptor.agent_id)

    return descriptors
