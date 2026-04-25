"""Supervisor agent factory for Jarvis.

Provides :func:`build_supervisor` — the single public factory that every later
feature composes against.  Phase 1 wired DeepAgents built-ins only; TASK-J002-017
extends the signature with two keyword-only kwargs so Phase 2 callers can wire
the 9 core tools and the active capability catalogue without touching Phase 1
call sites.

Architecture references:
    - ADR-ARCH-010 (DeepAgents 0.5.3 pin)
    - ADR-ARCH-011 (single Jarvis reasoner subagent)
    - ADR-ARCH-002 (clean hexagonal in DeepAgents supervisor)
    - DDR-008 (capability catalogue injection at supervisor build time)

This module belongs to the agents package (Group C) per ADR-ARCH-006.
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver

from jarvis.prompts import SUPERVISOR_SYSTEM_PROMPT

if TYPE_CHECKING:
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


def build_supervisor(
    config: JarvisConfig,
    *,
    tools: list[BaseTool] | None = None,
    available_capabilities: list[CapabilityDescriptor] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compose and return the Jarvis supervisor compiled graph.

    Phase 1 callers (``build_supervisor(config)``) remain valid because
    ``tools`` and ``available_capabilities`` default to ``None``; both
    keyword-only kwargs were added in TASK-J002-017 so lifecycle wiring can
    inject the 9 Phase 2 tools and the active capability catalogue without
    breaking earlier call sites.

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
    4. Passes the model, formatted prompt, the supplied tool list (defaulting
       to ``[]``) and an empty subagents list to ``create_deep_agent`` which
       compiles and returns the state graph.

    Args:
        config: Validated :class:`JarvisConfig` instance. Must have a
            ``supervisor_model`` field in ``"provider:model"`` format.
        tools: Optional list of LangChain ``BaseTool`` objects to wire into
            the supervisor.  ``None`` is normalised to ``[]`` so Phase 1
            call sites that omitted the kwarg observe the original
            zero-tool behaviour.
        available_capabilities: Optional list of
            :class:`~jarvis.tools.CapabilityDescriptor` entries describing
            the dispatchable fleet agents.  ``None`` or ``[]`` injects the
            L305 fallback string.

    Returns:
        A :class:`CompiledStateGraph` ready for invocation — but not yet
        invoked.  Built-in DeepAgents tools (``write_todos``, virtual
        filesystem, ``task``) are available in addition to any caller-supplied
        ``tools``; the ``execute`` tool is provided by the default
        ``StateBackend`` which does not implement
        ``SandboxBackendProtocol``, so ``execute`` will return an error if
        called.

    Raises:
        ValueError: If ``config.supervisor_model`` is not in a valid
            ``provider:model`` format (should be caught by Pydantic
            validation before reaching this point).
    """
    logger.info(
        "Building supervisor graph with model=%s, tools=%d, capabilities=%d",
        config.supervisor_model,
        0 if tools is None else len(tools),
        0 if available_capabilities is None else len(available_capabilities),
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

    # 4. Compile the agent graph — DeepAgents built-ins are wired by middleware.
    #    tools=tools or []      → caller-supplied (Phase 2: 9 tools);
    #                             None preserves Phase 1 zero-tool behaviour.
    #    subagents=[]           → no subagents (FEAT-003 will add them).
    #    checkpointer=InMemorySaver
    #                            → within-process thread-per-session recall so
    #                              ``session_manager.invoke(session, …)``
    #                              accumulates message history across turns when
    #                              called with the same ``thread_id``.  Without
    #                              a checkpointer, ``thread_id`` plumbing is a
    #                              no-op and each turn sees only the current
    #                              message — breaking the day-1 multi-turn
    #                              criterion.  Cross-process / cross-session
    #                              recall requires a persistent saver +
    #                              persistent store, landing in FEAT-JARVIS-007.
    graph: CompiledStateGraph[Any, Any, Any, Any] = create_deep_agent(
        model=model,
        tools=tools if tools is not None else [],
        system_prompt=system_prompt,
        subagents=[],
        checkpointer=InMemorySaver(),
    )

    logger.info("Supervisor graph compiled successfully")
    return graph
