"""Supervisor agent factory for Jarvis.

Provides :func:`build_supervisor` — the single public factory that every later
feature composes against.  Phase 1 wired DeepAgents built-ins only; TASK-J002-017
extends the signature with two keyword-only kwargs so Phase 2 callers can wire
the 9 core tools and the active capability catalogue without touching Phase 1
call sites.  TASK-J003-013 extends the signature *again* with two further
keyword-only kwargs (``async_subagents``, ``ambient_tool_factory``) so Phase 3
callers can wire the local ``jarvis-reasoner`` AsyncSubAgent and the
ambient-context tool list without touching the FEAT-J002 call sites.

Architecture references:
    - ADR-ARCH-010 (DeepAgents 0.5.3 pin)
    - ADR-ARCH-011 (single Jarvis reasoner subagent)
    - ADR-ARCH-002 (clean hexagonal in DeepAgents supervisor)
    - ADR-ARCH-022 / ADR-ARCH-023 (constitutional / belt+braces
      separation of attended vs. ambient tool surfaces)
    - DDR-008 (capability catalogue injection at supervisor build time)
    - DDR-014 (three-layer gating of ``escalate_to_frontier``;
      ambient tool list is the registration-layer gate)

This module belongs to the agents package (Group C) per ADR-ARCH-006.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

from jarvis.prompts import SUPERVISOR_SYSTEM_PROMPT

if TYPE_CHECKING:
    from deepagents import AsyncSubAgent
    from langchain_core.tools import BaseTool
    from langgraph.graph.state import CompiledStateGraph

    from jarvis.config.settings import JarvisConfig
    from jarvis.tools import CapabilityDescriptor

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase 1 domain prompt — no domain file wired yet (FEAT-004+).
# ---------------------------------------------------------------------------
_PHASE1_DOMAIN_PROMPT = "No domain-specific instructions configured (Phase 1)."

# ---------------------------------------------------------------------------
# Default capability-catalogue text injected when the registry is None or
# empty.  Per ``feat-jarvis-002...feature`` line 305 the literal string MUST
# match byte-for-byte so prompts remain stable across refactors.
# ---------------------------------------------------------------------------
_DEFAULT_AVAILABLE_CAPABILITIES = "No capabilities currently registered."


def _render_available_capabilities(
    descriptors: list[CapabilityDescriptor] | None,
) -> str:
    """Render the ``{available_capabilities}`` prompt fragment.

    Returns the L305 fallback string when ``descriptors`` is ``None`` or
    empty; otherwise sorts the descriptors deterministically by ``agent_id``
    and joins each ``CapabilityDescriptor.as_prompt_block()`` rendering with
    a literal ``"\\n\\n"`` separator (DDR-008 / DM-tool-types §"Prompt-block
    shape").

    Sorting is performed on a *local* copy so the caller's list is not
    mutated — important because the same registry is also stored on
    ``AppState`` and bound into the tool snapshots.
    """
    if not descriptors:
        return _DEFAULT_AVAILABLE_CAPABILITIES
    ordered = sorted(descriptors, key=lambda d: d.agent_id)
    return "\n\n".join(d.as_prompt_block() for d in ordered)


# ---------------------------------------------------------------------------
# Attribute name used to attach the resolved ambient-tool factory to the
# compiled supervisor graph.  Downstream consumers (lifecycle wiring,
# ambient/learning paths) read the attribute rather than the kwarg so the
# factory survives the ``create_deep_agent`` boundary, which does not
# accept (or surface) caller-supplied attributes.
#
# The attribute name is deliberately namespaced with the ``_jarvis_``
# prefix so it cannot collide with any DeepAgents-injected attribute on
# the compiled graph.
# ---------------------------------------------------------------------------
AMBIENT_TOOL_FACTORY_ATTR: str = "_jarvis_ambient_tool_factory"


def _default_ambient_tool_factory(
    config: JarvisConfig,
    available_capabilities: list[CapabilityDescriptor] | None,
) -> Callable[[], list[BaseTool]]:
    """Build the default ``ambient_tool_factory`` for a supervisor.

    When the caller passes ``ambient_tool_factory=None`` (the FEAT-J002
    backward-compat path) the supervisor still needs an *effective*
    factory to expose to ambient/learning consumers — DDR-014's
    registration-layer gate is a list, never ``None`` — so this helper
    returns a closure that calls
    :func:`jarvis.tools.assemble_tool_list` with
    ``include_frontier=False``.  The closure resolves
    ``available_capabilities`` to ``[]`` when the caller passed ``None``
    so the closure body matches the FEAT-J002 ``capability_registry``
    contract (a real list, possibly empty).

    The :mod:`jarvis.tools` import is performed *inside* the closure so
    importing :mod:`jarvis.agents.supervisor` does not eagerly pull the
    tools package and trigger its module-level side effects (capability
    snapshots, etc.).  The closure body runs at most once per ambient
    activation.

    Args:
        config: The :class:`JarvisConfig` originally supplied to
            :func:`build_supervisor`.  Threaded into the assembled tool
            list so :func:`~jarvis.tools.search_web` resolves the active
            ``tavily_api_key`` at call time.
        available_capabilities: The capability registry the supervisor
            was built with; ``None`` is normalised to ``[]`` inside the
            closure to honour the snapshot-isolation contract
            (ASSUM-006).

    Returns:
        A zero-argument callable that, on each invocation, returns a
        fresh ``list[BaseTool]`` representing the ambient surface
        (FEAT-J002 9-tool baseline minus ``escalate_to_frontier``).
    """

    def _factory() -> list[BaseTool]:
        # Lazy import keeps build_supervisor's import surface narrow.
        from jarvis.tools import assemble_tool_list

        return assemble_tool_list(
            config,
            list(available_capabilities) if available_capabilities is not None else [],
            include_frontier=False,
        )

    return _factory


def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,
    available_capabilities: list[CapabilityDescriptor] | None = None,
    async_subagents: list[AsyncSubAgent] | None = None,
    ambient_tool_factory: Callable[[], list[BaseTool]] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compose and return the Jarvis supervisor compiled graph.

    Phase 1 callers (``build_supervisor(config)``) remain valid because
    every additional parameter is keyword-only with a safe default. The
    keyword-only kwargs were introduced incrementally:

    - TASK-J002-017 added ``tools`` and ``available_capabilities`` so
      lifecycle wiring could inject the 9 FEAT-J002 tools and the active
      capability catalogue.
    - TASK-J003-013 added ``async_subagents`` and ``ambient_tool_factory``
      so lifecycle wiring can wire the local ``jarvis-reasoner``
      AsyncSubAgent (DDR-010 / ADR-ARCH-011) and register the
      registration-layer gate of the constitutional ``escalate_to_frontier``
      cloud escape hatch (DDR-014 / ADR-ARCH-022 / ADR-ARCH-023).

    The factory:

    1. Resolves the model via ``init_chat_model`` using the provider-prefixed
       string from ``config.supervisor_model`` (e.g. ``"openai:jarvis-reasoner"``).
       ``init_chat_model`` instantiates the chat model object **without**
       issuing any network request.
    2. Renders the ``{available_capabilities}`` prompt fragment from the
       supplied ``available_capabilities`` list (or the L305 fallback string
       when the registry is ``None`` / empty).
    3. Formats the supervisor system prompt with today's date, the rendered
       capability block, and the Phase 1 domain stub.
    4. Resolves the ambient-tool factory: caller-supplied closure if
       provided, else the default closure that delegates to
       :func:`jarvis.tools.assemble_tool_list` with
       ``include_frontier=False``.
    5. Passes the model, formatted prompt, the supplied tool list (defaulting
       to ``[]``) and the supplied async-subagent list (defaulting to
       ``[]``) to ``create_deep_agent`` which compiles the state graph.
       The DeepAgents ``AsyncSubAgentMiddleware`` auto-injects its five
       operational tools (``start_async_task``, ``check_async_task``,
       ``update_async_task``, ``cancel_async_task``, ``list_async_tasks``)
       into the supervisor's tool catalogue **iff** the async-subagent
       list is non-empty.
    6. Attaches the resolved ambient factory to the compiled graph as
       ``graph._jarvis_ambient_tool_factory`` so ambient/learning
       consumers can fetch the canonical ambient list without re-running
       the lifecycle wiring.

    Args:
        config: Validated :class:`JarvisConfig` instance. Must have a
            ``supervisor_model`` field in ``"provider:model"`` format.
        tools: Optional list of LangChain ``BaseTool`` objects to wire into
            the supervisor (the *attended* surface).  ``None`` is
            normalised to ``[]`` so Phase 1 call sites that omitted the
            kwarg observe the original zero-tool behaviour.
        available_capabilities: Optional list of
            :class:`~jarvis.tools.CapabilityDescriptor` entries describing
            the dispatchable fleet agents.  ``None`` or ``[]`` injects the
            L305 fallback string.
        async_subagents: Optional list of DeepAgents
            :class:`~deepagents.AsyncSubAgent` specs.  ``None`` (the
            FEAT-J002 default) means **no** async subagents are wired —
            the supervisor's tool catalogue does *not* include the five
            ``AsyncSubAgentMiddleware`` operational tools.  Supplying a
            non-empty list (e.g. ``build_async_subagents(config)``) wires
            those specs and DeepAgents auto-injects the five tools.
        ambient_tool_factory: Optional zero-argument callable returning
            a ``list[BaseTool]`` to use as the canonical ambient tool
            surface (DDR-014 registration-layer gate).  ``None`` (the
            FEAT-J002 default) resolves to a closure that calls
            ``assemble_tool_list(config, available_capabilities or [],
            include_frontier=False)`` — the FEAT-J002 9-tool baseline
            minus ``escalate_to_frontier``.  Whichever factory is
            effective is attached to the returned graph as
            ``graph._jarvis_ambient_tool_factory``.

    Returns:
        A :class:`CompiledStateGraph` ready for invocation — but not yet
        invoked.  Built-in DeepAgents tools (``write_todos``, virtual
        filesystem, ``task``) are available in addition to any caller-supplied
        ``tools``; the ``execute`` tool is provided by the default
        ``StateBackend`` which does not implement
        ``SandboxBackendProtocol``, so ``execute`` will return an error if
        called.  The compiled graph carries a
        ``_jarvis_ambient_tool_factory`` attribute (zero-argument
        callable) that ambient/learning consumers invoke to obtain the
        canonical ambient tool surface.

    Raises:
        ValueError: If ``config.supervisor_model`` is not in a valid
            ``provider:model`` format (should be caught by Pydantic
            validation before reaching this point).
    """
    logger.info(
        "Building supervisor graph with model=%s, tools=%d, capabilities=%d, "
        "async_subagents=%d, ambient_tool_factory=%s",
        config.supervisor_model,
        0 if tools is None else len(tools),
        0 if available_capabilities is None else len(available_capabilities),
        0 if async_subagents is None else len(async_subagents),
        "supplied" if ambient_tool_factory is not None else "default",
    )

    # 1. Resolve model — no network call; just object instantiation.
    model = init_chat_model(config.supervisor_model)

    # 2. Render the capability catalogue prompt fragment.
    rendered_capabilities = _render_available_capabilities(available_capabilities)

    # 3. Format system prompt with runtime context.
    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        date=datetime.date.today().isoformat(),
        available_capabilities=rendered_capabilities,
        domain_prompt=_PHASE1_DOMAIN_PROMPT,
    )

    # 4. Resolve the ambient-tool factory.  When the caller passed
    #    ``None`` we substitute the default closure so the registration-
    #    layer gate (DDR-014) is *always* an inspectable callable on the
    #    returned graph.  This means downstream consumers never have to
    #    branch on ``factory is None``.
    resolved_ambient_factory = (
        ambient_tool_factory
        if ambient_tool_factory is not None
        else _default_ambient_tool_factory(config, available_capabilities)
    )

    # 5. Compile the agent graph — DeepAgents built-ins are wired by middleware.
    #    tools=tools or []        → caller-supplied (Phase 2: 9 tools, or
    #                               Phase 3 attended 10-tool surface);
    #                               None preserves Phase 1 zero-tool behaviour.
    #    subagents=async_subagents → caller-supplied AsyncSubAgent list, or
    #                               an empty list when no subagents are
    #                               wired.  An empty list keeps
    #                               ``AsyncSubAgentMiddleware`` *out* of the
    #                               middleware stack, so its five
    #                               operational tools (start/check/update/
    #                               cancel/list) are NOT injected — a
    #                               critical FEAT-J002 backward-compat
    #                               invariant asserted by the design's
    #                               "Building the supervisor without async
    #                               subagents preserves existing behaviour"
    #                               scenario.
    #    checkpointer=InMemorySaver
    #                              → within-process thread-per-session recall
    #                                so ``session_manager.invoke(session, …)``
    #                                accumulates message history across turns
    #                                when called with the same ``thread_id``.
    #                                Cross-process / cross-session recall
    #                                requires a persistent saver + persistent
    #                                store, landing in FEAT-JARVIS-007.
    graph: CompiledStateGraph[Any, Any, Any, Any] = create_deep_agent(
        model=model,
        tools=tools if tools is not None else [],
        system_prompt=system_prompt,
        subagents=list(async_subagents) if async_subagents else [],
        checkpointer=InMemorySaver(),
    )

    # 6. Attach the resolved ambient-tool factory to the compiled graph
    #    so DDR-014 Layer-3 ambient consumers can fetch the canonical
    #    list without re-deriving it from lifecycle state.  The
    #    attribute is namespaced (``_jarvis_*``) so it cannot collide
    #    with any DeepAgents-injected attribute, and it is deliberately
    #    a *callable* (not a list) so the consumer pays the assembly
    #    cost only when it actually activates an ambient context.
    try:
        setattr(graph, AMBIENT_TOOL_FACTORY_ATTR, resolved_ambient_factory)
    except (AttributeError, TypeError) as exc:
        # Some compiled-graph types use ``__slots__`` or otherwise reject
        # attribute assignment.  Log + carry on — ambient consumers will
        # then re-derive the factory from lifecycle state.  We intentionally
        # do NOT swallow the broader Exception class so a programmer error
        # (e.g. ``setattr`` raising for a different reason) still surfaces.
        logger.warning(
            "Could not attach ambient tool factory to supervisor graph "
            "(graph type %s rejected setattr: %s); ambient consumers must "
            "fall back to lifecycle wiring.",
            type(graph).__name__,
            exc,
        )

    logger.info("Supervisor graph compiled successfully")
    return graph
