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

Catalogue tools (TASK-J002-012)
-------------------------------
This module also hosts the three capability-catalogue ``@tool`` functions
the reasoning model invokes at runtime:

* :func:`list_available_capabilities` — return the registry as JSON.
* :func:`capabilities_refresh` — Phase 2 no-op acknowledgement.
* :func:`capabilities_subscribe_updates` — Phase 2 no-op acknowledgement.

The tools read ``_capability_registry`` — a module-level
``list[CapabilityDescriptor]`` snapshot that ``assemble_tool_list``
(TASK-J002-015) assigns at supervisor build time. Snapshot isolation
(ASSUM-006) is preserved by capturing a *local* reference at the start of
:func:`list_available_capabilities`: even if ``_capability_registry`` is
re-bound mid-call (e.g. by a concurrent :func:`capabilities_refresh` in a
future phase) the in-flight call still sees the snapshot it captured.

This module is a leaf in the import graph (ADR-ARCH-002): it must not import
from ``jarvis.agents.*``, ``jarvis.infrastructure.*``, or ``jarvis.cli.*``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

__all__ = [
    "CapabilityDescriptor",
    "CapabilityToolSummary",
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "list_available_capabilities",
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
        for cap in self.capability_list:
            # 4-space continuation indent for any embedded newlines so the
            # block remains visually clean when consumed by the model.
            indented_description = cap.description.replace("\n", "\n    ")
            lines.append(f"  - {cap.tool_name} ({cap.risk_level}) — {indented_description}")
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


# ---------------------------------------------------------------------------
# Capability registry binding — TASK-J002-012.
#
# ``assemble_tool_list`` (TASK-J002-015) snapshots a
# ``list[CapabilityDescriptor]`` into this module-level attribute at
# supervisor build time. The default empty list keeps a bare import safe:
# :func:`list_available_capabilities` returns ``"[]"`` rather than raising
# if no operator has wired up a registry yet.
#
# Snapshot isolation (ASSUM-006): ``assemble_tool_list`` MUST assign a
# fresh ``list(...)`` copy here, never share a reference to the operator's
# mutable registry. The tool implementations capture a *local* reference
# at the start of each call so that even if a concurrent rebinding (or a
# future Phase 3 :func:`capabilities_refresh`) replaces this list mid-call,
# the in-flight invocation still sees the original snapshot.
# ---------------------------------------------------------------------------
_capability_registry: list[CapabilityDescriptor] = []


# ---------------------------------------------------------------------------
# Phase 2 stub acknowledgements — Phase 2->3 swap targets.
#
# Grep anchor (per task swap_point_note): the literal ``stubbed in Phase 2``
# substring. A FEAT-JARVIS-004 implementation replaces these constants (and
# the bodies of the two functions that return them) with real NATS KV
# refresh / watcher wiring without touching the docstrings.
# ---------------------------------------------------------------------------
_REFRESH_OK_MESSAGE: str = (
    "OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)"
)
_SUBSCRIBE_OK_MESSAGE: str = "OK: subscribed (stubbed in Phase 2 — no live updates)"


@tool(parse_docstring=True)
def list_available_capabilities() -> str:
    """Return the current fleet capability catalogue as JSON.

    The catalogue is also injected into your system prompt at session start
    (under "## Available Capabilities"). Call this tool only when you suspect
    the injected snapshot is stale — e.g., the user says "a new agent just came
    online" or more than ~10 minutes have elapsed in the same session.

    In Phase 2 this reads from an in-memory stub registry; in FEAT-JARVIS-004
    (Phase 3) it will read from the live NATS KV manifest registry. The
    signature and response shape are identical across phases.

    Near-zero cost, <5ms latency (stub) / <30ms (cached live registry).

    Returns:
        JSON array of CapabilityDescriptor objects:
          ``[{"agent_id": str, "role": str, "description": str,
              "capability_list": [{"tool_name": str, "description": str,
                                   "risk_level": str}, ...],
              "cost_signal": str, "latency_signal": str,
              "last_heartbeat_at": ISO8601 | null,
              "trust_tier": "core" | "specialist" | "extension"}, ...]``
        OR a structured error:
          - ``ERROR: registry_unavailable — <detail>``
    """
    try:
        # Snapshot isolation (ASSUM-006): capture the registry reference
        # ONCE at call start. ``assemble_tool_list`` (and any future Phase 3
        # refresh) rebinds ``_capability_registry`` to a fresh list rather
        # than mutating in place, so a concurrent rebind never affects the
        # JSON we are about to render below.
        snapshot: list[CapabilityDescriptor] = _capability_registry
        serialised = [descriptor.model_dump(mode="json") for descriptor in snapshot]
        return json.dumps(serialised)
    except Exception as exc:
        # ADR-ARCH-021 — never raise across the tool boundary. Log with full
        # stack so operators can diagnose unexpected failures, then return
        # the structured ERROR string the reasoning model can read.
        logger.exception("list_available_capabilities failed unexpectedly")
        return f"ERROR: registry_unavailable — {exc}"


@tool(parse_docstring=True)
def capabilities_refresh() -> str:
    """Invalidate the cached capability catalogue and re-read the source of truth.

    Call this ONLY when the user explicitly indicates the catalogue is stale —
    e.g. "the architect agent should be up now, check again". The injected
    system-prompt snapshot is refreshed at session start; mid-session refresh
    is rarely useful.

    STUB in Phase 2: no-op that returns a structured acknowledgement. Phase 3
    (FEAT-JARVIS-004) triggers a real NATS KV re-read.

    Returns:
        ``OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)``
        OR a structured error in Phase 3+.
    """
    # Phase 2->3 swap point. The body is intentionally trivial; FEAT-JARVIS-004
    # replaces it with a NATS KV re-read followed by a fresh
    # ``_capability_registry`` rebinding. The catch-all preserves the
    # ADR-ARCH-021 never-raises invariant against future edits that make the
    # body non-trivial.
    try:
        return _REFRESH_OK_MESSAGE
    except Exception as exc:
        logger.exception("capabilities_refresh failed unexpectedly")
        return f"ERROR: registry_unavailable — {exc}"


@tool(parse_docstring=True)
def capabilities_subscribe_updates() -> str:
    """Subscribe the current session to live capability-change notifications.

    STUB in Phase 2: no-op that returns a structured acknowledgement. Phase 3
    (FEAT-JARVIS-004) attaches a NATS KV watcher that will re-inject the
    capability block into future turns when fleet membership changes.

    Call at most once per session.

    Returns:
        ``OK: subscribed (stubbed in Phase 2 — no live updates)``
        OR a structured error in Phase 3+.
    """
    # Phase 2->3 swap point. FEAT-JARVIS-004 replaces this body with a real
    # NATS KV watcher attachment that re-injects the capability block on
    # change. Catch-all upholds ADR-ARCH-021 never-raises invariant.
    try:
        return _SUBSCRIBE_OK_MESSAGE
    except Exception as exc:
        logger.exception("capabilities_subscribe_updates failed unexpectedly")
        return f"ERROR: registry_unavailable — {exc}"
