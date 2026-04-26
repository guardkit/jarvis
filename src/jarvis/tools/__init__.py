"""Public surface of the ``jarvis.tools`` package.

This module is the **only** stable surface for Jarvis tools — code outside
``jarvis.tools.*`` (and the test suite where strictly necessary) MUST
import from here, never from the submodules ``general``, ``capabilities``,
or ``dispatch`` directly. See API-internal.md §1.1 for the contract.

The :func:`assemble_tool_list` factory is the **single** wiring point that:

1. Calls :func:`jarvis.tools.general.configure` so :func:`search_web` can
   resolve the active :class:`~jarvis.config.settings.JarvisConfig`.
2. Snapshots ``capability_registry`` into the module-level
   ``_capability_registry`` attributes of ``jarvis.tools.capabilities``
   and ``jarvis.tools.dispatch`` (a fresh ``list(...)`` copy in each, so
   subsequent operator mutations of the caller's list cannot leak into
   the supervisor's view — ASSUM-006 snapshot isolation).
3. Returns the FEAT-J002 9 Phase 2 tools in stable alphabetical order
   so test expectations and the supervisor wiring are deterministic, and
   — when ``include_frontier=True`` (the default) — splices in the
   FEAT-J003 ``escalate_to_frontier`` cloud escape hatch as the **Layer 3**
   constitutional gate. Layer 3 (DDR-014, ADR-ARCH-022, ADR-ARCH-023)
   makes the attended vs. ambient surfaces diverge by tool-registry
   *membership*, not by a runtime check the reasoning model could
   subvert: the model literally cannot invoke a tool it cannot see.

Per ADR-ARCH-002 / API-internal.md §1.1: this module is the leaf
boundary of ``jarvis.tools``. No domain package (``jarvis.agents``,
``jarvis.cli``, ``jarvis.infrastructure``) may bypass this surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool

from jarvis.tools import capabilities as _capabilities
from jarvis.tools import dispatch as _dispatch
from jarvis.tools import general as _general
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    capabilities_refresh,
    capabilities_subscribe_updates,
    list_available_capabilities,
    load_stub_registry,
)
from jarvis.tools.dispatch import (
    dispatch_by_capability,
    escalate_to_frontier,
    queue_build,
)
from jarvis.tools.general import (
    calculate,
    get_calendar_events,
    read_file,
    search_web,
)
from jarvis.tools.types import CalendarEvent, DispatchError, WebResult

if TYPE_CHECKING:
    from jarvis.config.settings import JarvisConfig


__all__ = [
    # Pydantic types (3 + 1 internal sentinel = 4)
    "CalendarEvent",
    "CapabilityDescriptor",
    "DispatchError",
    "WebResult",
    # General tools (4)
    "calculate",
    "get_calendar_events",
    "read_file",
    "search_web",
    # Capability catalogue tools (3)
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "list_available_capabilities",
    # Dispatch tools (2 + 1 attended-only escalation)
    "dispatch_by_capability",
    "escalate_to_frontier",
    "queue_build",
    # Assembly + loader
    "assemble_tool_list",
    "load_stub_registry",
]


def assemble_tool_list(
    config: "JarvisConfig",
    capability_registry: list[CapabilityDescriptor],
    *,
    include_frontier: bool = True,
) -> list[BaseTool]:
    """Wire and return the Jarvis tool list in stable alphabetical order.

    This factory is the ONE place that knows how to wire tool-level state
    (per API-internal.md §1.2). It performs three side effects on the
    submodules and then returns the tool objects the supervisor passes to
    ``create_deep_agent(tools=...)``.

    Side effects:

    1. ``general.configure(config)`` — installs the active config so
       :func:`search_web` can resolve ``tavily_api_key`` lazily on each
       call.
    2. ``capabilities._capability_registry = list(capability_registry)``
       — snapshot copy so the catalogue tools see a stable view.
    3. ``dispatch._capability_registry = list(capability_registry)`` —
       independent snapshot copy so :func:`dispatch_by_capability` can
       resolve ``tool_name`` to ``agent_id`` deterministically.

    Both snapshots are fresh ``list(...)`` copies; mutating the
    operator's ``capability_registry`` argument after this call cannot
    leak into either submodule (ASSUM-006 snapshot isolation).

    **Layer 3 constitutional gate (DDR-014, ADR-ARCH-022, ADR-ARCH-023).**
    The ``include_frontier`` keyword-only flag is the third (and outermost)
    layer of the belt+braces gate that protects the cloud escape hatch:

    - ``include_frontier=True`` (the default) is used by
      ``lifecycle.startup`` for **attended** sessions. The returned list
      contains :func:`escalate_to_frontier` slotted alphabetically between
      ``dispatch_by_capability`` and ``get_calendar_events`` — 10 tools
      total. The reasoning model can see and invoke the escalation.
    - ``include_frontier=False`` is used for **ambient / learning /
      async-subagent** contexts. The returned list omits
      :func:`escalate_to_frontier` entirely — 9 tools total, identical to
      the FEAT-J002 surface — so the reasoning model literally cannot
      invoke a tool it cannot see.

    The flag is **lifecycle-time only** and has no relationship to
    session state; the caller (``lifecycle.startup``) decides per
    constructor. ADR-ARCH-023 forbids the reasoning model from rebinding
    its own tool list, and the fresh ``list[...]`` returned each call
    means a hostile mutation cannot leak between calls.

    Args:
        config: Active :class:`~jarvis.config.settings.JarvisConfig`. The
            ``tavily_api_key`` field is read by :func:`search_web` on
            each call; an absent key surfaces as a structured
            ``ERROR: config_missing`` string at tool time, never at
            assemble time.
        capability_registry: Descriptors for the fleet agents Jarvis can
            dispatch to. Empty list is allowed — every dispatch then
            returns ``ERROR: unresolved`` and
            :func:`list_available_capabilities` returns ``"[]"``.
        include_frontier: Layer 3 gate flag. ``True`` (default) wires
            the attended 10-tool surface that includes
            :func:`escalate_to_frontier`; ``False`` wires the ambient
            9-tool surface that omits it. Keyword-only by design — the
            flag must be supplied explicitly at the call site so a
            misplaced positional argument cannot accidentally enable the
            cloud escape hatch.

    Returns:
        A fresh ``list[BaseTool]`` in stable alphabetical order:

        - With ``include_frontier=True`` (10 tools): ``[calculate,
          capabilities_refresh, capabilities_subscribe_updates,
          dispatch_by_capability, escalate_to_frontier,
          get_calendar_events, list_available_capabilities, queue_build,
          read_file, search_web]``.
        - With ``include_frontier=False`` (9 tools): the same list with
          ``escalate_to_frontier`` removed.

        A new ``list`` object is returned on every call so callers cannot
        mutate a shared instance (ADR-ARCH-023).
    """
    # 1. Inject the active config into general.search_web's resolver.
    _general.configure(config)

    # 2. + 3. Snapshot-copy the registry into both consuming modules.
    #
    # Use ``list(...)`` rather than ``capability_registry`` directly so
    # the operator's outer list is decoupled from the in-process view
    # the tools observe. ASSUM-006 mandates that a concurrent rebinding
    # of either attribute (e.g. by a future Phase 3
    # ``capabilities_refresh``) replaces the list rather than mutating
    # it in place; the in-flight tool calls capture a local reference
    # at the start of each invocation so they remain consistent.
    _capabilities._capability_registry = list(capability_registry)
    _dispatch._capability_registry = list(capability_registry)

    # Stable alphabetical ordering — the test suite and the supervisor
    # wiring rely on this being deterministic. A literal list (rather
    # than ``sorted(...)`` over a mapping) makes the contract obvious to
    # readers and is one fewer thing to break under refactor.
    #
    # ``escalate_to_frontier`` slots alphabetically between
    # ``dispatch_by_capability`` and ``get_calendar_events`` when the
    # Layer 3 attended gate (``include_frontier=True``) is open.
    if include_frontier:
        return [
            calculate,
            capabilities_refresh,
            capabilities_subscribe_updates,
            dispatch_by_capability,
            escalate_to_frontier,
            get_calendar_events,
            list_available_capabilities,
            queue_build,
            read_file,
            search_web,
        ]
    return [
        calculate,
        capabilities_refresh,
        capabilities_subscribe_updates,
        dispatch_by_capability,
        get_calendar_events,
        list_available_capabilities,
        queue_build,
        read_file,
        search_web,
    ]
