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

Catalogue tools (FEAT-JARVIS-004 — KV-backed bodies, TASK-J004-012)
-------------------------------------------------------------------
This module also hosts the three capability-catalogue ``@tool`` functions
the reasoning model invokes at runtime:

* :func:`list_available_capabilities` — JSON snapshot via
  ``_capability_registry.snapshot()``.
* :func:`capabilities_refresh` — drives ``_capability_registry.refresh()``
  and renders ``OK: refresh queued — registry resynchronised`` on success or
  ``DEGRADED: transport_unavailable — NATS connection failed`` if the KV
  read raises.
* :func:`capabilities_subscribe_updates` — drives
  ``_capability_registry.subscribe_updates(...)`` exactly once per session.

The tools speak only the
:class:`jarvis.infrastructure.capabilities_registry.CapabilitiesRegistry`
Protocol surface (``snapshot/refresh/subscribe_updates/close``); they never
branch on Live vs Stub and never import the production registry class
directly. ``assemble_tool_list`` (TASK-J004-013) populates the module-level
``_capability_registry`` swap-point with whichever implementation the
DDR-021 lifecycle picked.

Snapshot isolation (ASSUM-006) is preserved by the registry implementations
— :meth:`CapabilitiesRegistry.snapshot` returns a fresh ``list`` copy on
every call so a concurrent KV-watch invalidation rebuilding the cache cannot
mutate the JSON an in-flight call is about to render.

This module is a leaf in the import graph (ADR-ARCH-002): it must not import
from ``jarvis.agents.*``, ``jarvis.infrastructure.*``, or ``jarvis.cli.*``
at runtime. The CapabilitiesRegistry Protocol type is referenced only under
``TYPE_CHECKING`` so ``from __future__ import annotations`` keeps the
runtime import graph clean.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

import yaml
from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # pragma: no cover - import-time only, no runtime cost
    # Forward-reference only: the Protocol lives in jarvis.infrastructure
    # (which imports *from* this module). Pulling it in under TYPE_CHECKING
    # keeps capabilities.py a true leaf at runtime (ADR-ARCH-002).
    from jarvis.infrastructure.capabilities_registry import CapabilitiesRegistry

logger = logging.getLogger(__name__)

__all__ = [
    "CapabilityDescriptor",
    "CapabilityToolSummary",
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "list_available_capabilities",
    "load_stub_registry",
]

_T = TypeVar("_T")


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
# Capability registry binding — TASK-J004-012 (KV-backed swap).
#
# Module-level ``CapabilitiesRegistry`` handle. ``assemble_tool_list``
# (TASK-J004-013) assigns either a ``LiveCapabilitiesRegistry`` or a
# ``StubCapabilitiesRegistry`` here at supervisor build time; the lifecycle
# decides which one based on DDR-021 soft-fail. Tool bodies speak only the
# Protocol surface (``snapshot/refresh/subscribe_updates/close``) so they
# never branch on which implementation is in use.
#
# ``None`` is the pre-wired sentinel — a tool invoked before lifecycle
# wiring (e.g. by an early-boot test) surfaces a structured ``ERROR:
# registry_unavailable`` / ``DEGRADED: transport_unavailable`` string per
# ADR-ARCH-021 rather than dereferencing ``None``.
# ---------------------------------------------------------------------------
_capability_registry: CapabilitiesRegistry | None = None


# ---------------------------------------------------------------------------
# Tool-level idempotency for ``capabilities_subscribe_updates``.
#
# The Protocol's :meth:`CapabilitiesRegistry.subscribe_updates` is itself
# idempotent (a second call is a no-op there), but we layer a tool-level
# flag too so the tool returns the same OK string without paying the
# coroutine-drive cost on every reasoning-model invocation. ``False`` is
# the pre-wired default; ``assemble_tool_list`` resets it to ``False`` at
# supervisor build so a re-wired session starts subscribed-once again.
# ---------------------------------------------------------------------------
_subscribe_invoked: bool = False


# ---------------------------------------------------------------------------
# Acknowledgement constants.
#
# The Phase 2 refresh-OK constant is gone — FEAT-JARVIS-004 §4 introduces
# the new OK / DEGRADED return strings as inline module-private constants
# below. ``_SUBSCRIBE_OK_MESSAGE`` is preserved byte-identical because the
# reasoning model has been routing against this exact string since
# FEAT-JARVIS-002 (API-tools.md §5 keeps the OK shape unchanged across the
# swap).
# ---------------------------------------------------------------------------
_SUBSCRIBE_OK_MESSAGE: str = "OK: subscribed (stubbed in Phase 2 — no live updates)"

# Inline constants for the FEAT-J004 refresh return shape (API-tools.md §4).
# Kept module-private (single underscore) so test suites can pin against
# byte-exact drift, but not re-exported as part of the public surface.
_REFRESH_OK: str = "OK: refresh queued — registry resynchronised"
_REFRESH_DEGRADED: str = "DEGRADED: transport_unavailable — NATS connection failed"


def _drive_coroutine(coro: Coroutine[Any, Any, _T]) -> _T:
    """Run an async coroutine to completion from sync code.

    Most tool invocations come in on a thread that does not own a running
    event loop (LangGraph's sync-tool runner posts the call onto a worker
    thread). In that case ``asyncio.run`` is the cheapest path: it spins
    up a fresh loop, runs the coroutine, and tears the loop down.

    When the runtime invokes a sync tool from inside its own loop's
    thread, ``asyncio.get_running_loop`` succeeds and ``asyncio.run``
    cannot be used directly (it would refuse to nest loops). We delegate
    to a single-shot worker thread so ``asyncio.run`` runs on a clean
    thread with no running loop — paying one thread context switch in
    the rare nested-loop path is cheaper than depending on ``nest_asyncio``
    or maintaining a long-lived bridge thread.

    Args:
        coro: Coroutine produced by an ``async def`` method on the
            registry Protocol (``refresh`` or ``subscribe_updates``).

    Returns:
        Whatever the coroutine returns. Exceptions raised by the coroutine
        propagate verbatim (the caller is responsible for translating
        transport failures into structured error strings).
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop in this thread — drive the coroutine directly.
        return asyncio.run(coro)

    # Running loop in the calling thread — hand off to a worker thread so
    # ``asyncio.run`` does not collide with the existing loop.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _noop_subscribe_callback() -> None:
    """Default no-op callback for ``capabilities_subscribe_updates``.

    The watcher's job is to invalidate the registry's cached snapshot so
    the next ``list_available_capabilities`` call returns fresh data; the
    callback exists only to satisfy the Protocol surface and to be a
    later wiring seam for session-level reactions to fleet changes.
    """
    return None


@tool(parse_docstring=True)
def list_available_capabilities() -> str:
    """Return the current fleet capability catalogue as JSON.

    The catalogue is also injected into your system prompt at session start
    (under "## Available Capabilities"). Call this tool only when you suspect
    the injected snapshot is stale — e.g., the user says "a new agent just came
    online" or more than ~10 minutes have elapsed in the same session.

    Near-zero cost, <30ms (cached live registry; <5ms when serving the stub fallback).

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
        registry = _capability_registry
        if registry is None:
            # Pre-wired path: lifecycle has not run ``assemble_tool_list``
            # yet. Surface a structured error rather than crash so the
            # reasoning model sees a recoverable state per ADR-ARCH-021.
            return (
                "ERROR: registry_unavailable — capability registry has not been "
                "wired into jarvis.tools.capabilities yet"
            )
        # Snapshot isolation (ASSUM-006): the Protocol contract requires
        # ``snapshot()`` to return a fresh ``list`` copy, so a concurrent
        # KV-watch invalidation rebuilding the underlying cache cannot
        # mutate the descriptors we are about to render.
        descriptors = registry.snapshot()
        serialised = [descriptor.model_dump(mode="json") for descriptor in descriptors]
        return json.dumps(serialised)
    except Exception as exc:
        # ADR-ARCH-021 — never raise across the tool boundary. Log with
        # full stack so operators can diagnose unexpected failures, then
        # return the structured ERROR string the reasoning model can read.
        logger.exception("list_available_capabilities failed unexpectedly")
        return f"ERROR: registry_unavailable — {exc}"


@tool(parse_docstring=True)
def capabilities_refresh() -> str:
    """Invalidate the cached capability catalogue and re-read the source of truth.

    Call this ONLY when the user explicitly indicates the catalogue is stale —
    e.g. "the architect agent should be up now, check again". The injected
    system-prompt snapshot is refreshed at session start; mid-session refresh
    is rarely useful.

    Forces an immediate re-read of NATSKVManifestRegistry; returns
    ``OK: refresh queued`` on success, or ``DEGRADED: transport_unavailable``
    if NATS is down (registry continues serving the stub fallback).

    Returns:
        ``OK: refresh queued — registry resynchronised`` on success, or
        ``DEGRADED: transport_unavailable — NATS connection failed`` if the
        underlying KV read raises.
    """
    registry = _capability_registry
    if registry is None:
        # No registry wired — treat as the strongest form of transport
        # degradation per DDR-021. The lifecycle's stub fallback should
        # always have populated this, so reaching here is an operator
        # signal that wiring is incomplete.
        logger.warning(
            "capabilities_refresh called before _capability_registry was wired"
        )
        return _REFRESH_DEGRADED
    try:
        _drive_coroutine(registry.refresh())
    except Exception:
        # Any failure inside the registry's KV re-read is a transport
        # degradation from the model's perspective — the registry itself
        # logged a structured warning before it raised.
        logger.exception(
            "capabilities_refresh: registry.refresh() failed; surfacing DEGRADED"
        )
        return _REFRESH_DEGRADED
    return _REFRESH_OK


@tool(parse_docstring=True)
def capabilities_subscribe_updates() -> str:
    """Subscribe the current session to live capability-change notifications.

    Attaches a NATS KV watcher; when fleet membership changes, the cached
    registry invalidates and the next ``list_available_capabilities`` call
    returns fresh data. Idempotent — calling more than once per session is a
    no-op (the registry's underlying watcher is opened at most once).

    Call at most once per session.

    Returns:
        ``OK: subscribed (stubbed in Phase 2 — no live updates)``
        OR a structured error:
          - ``ERROR: registry_unavailable — <detail>``
    """
    global _subscribe_invoked
    try:
        registry = _capability_registry
        if registry is None:
            return (
                "ERROR: registry_unavailable — capability registry has not been "
                "wired into jarvis.tools.capabilities yet"
            )
        if _subscribe_invoked:
            # Tool-level idempotency: skip the coroutine drive entirely on
            # the second-and-later calls. The registry implements its own
            # idempotency guard too, so a missed flag here is still safe;
            # the flag is purely a perf shortcut.
            return _SUBSCRIBE_OK_MESSAGE
        _drive_coroutine(registry.subscribe_updates(_noop_subscribe_callback))
        _subscribe_invoked = True
        return _SUBSCRIBE_OK_MESSAGE
    except Exception as exc:
        logger.exception("capabilities_subscribe_updates failed unexpectedly")
        return f"ERROR: registry_unavailable — {exc}"
