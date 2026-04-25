"""Supervisor agent factory for Jarvis.

Provides :func:`build_supervisor` — the single public factory that every later
feature composes against.  Phase 1 wires DeepAgents built-ins only: no custom
tools (FEAT-002), no subagents (FEAT-003), and **no LLM call at build time**.

Architecture references:
    - ADR-ARCH-010 (DeepAgents 0.5.3 pin)
    - ADR-ARCH-011 (single Jarvis reasoner subagent)
    - ADR-ARCH-002 (clean hexagonal in DeepAgents supervisor)

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
    from langgraph.graph.state import CompiledStateGraph

    from jarvis.config.settings import JarvisConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Phase 1 domain prompt — no domain file wired yet (FEAT-004+).
# ---------------------------------------------------------------------------
_PHASE1_DOMAIN_PROMPT = "No domain-specific instructions configured (Phase 1)."

# ---------------------------------------------------------------------------
# Default capability-catalogue text injected when no registry is wired.
# TASK-J002-017 will replace this with rendered ``CapabilityDescriptor``
# blocks; until then ``build_supervisor`` ships the safe fallback so the
# ``{available_capabilities}`` placeholder added in TASK-J002-016 resolves.
# ---------------------------------------------------------------------------
_DEFAULT_AVAILABLE_CAPABILITIES = "No capabilities currently registered."


def build_supervisor(config: JarvisConfig) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compose and return the Jarvis supervisor compiled graph.

    Phase 1: DeepAgents built-ins only.  No LLM traffic at build time.

    The factory:

    1. Resolves the model via ``init_chat_model`` using the provider-prefixed
       string from ``config.supervisor_model`` (e.g. ``"openai:jarvis-reasoner"``).
       ``init_chat_model`` instantiates the chat model object **without** issuing
       any network request.

    2. Formats the supervisor system prompt with today's date and the Phase 1
       domain stub.

    3. Passes the model, formatted prompt, empty tools list, and empty subagents
       list to ``create_deep_agent`` which compiles and returns the state graph.

    Args:
        config: Validated :class:`JarvisConfig` instance.  Must have a
            ``supervisor_model`` field in ``"provider:model"`` format.

    Returns:
        A :class:`CompiledStateGraph` ready for invocation — but not yet invoked.
        Built-in DeepAgents tools (write_todos, filesystem, task) are available;
        the ``execute`` tool is provided by the default ``StateBackend`` which
        does not implement ``SandboxBackendProtocol``, so ``execute`` will
        return an error if called.

    Raises:
        ValueError: If ``config.supervisor_model`` is not in a valid
            ``provider:model`` format (should be caught by Pydantic validation
            before reaching this point).
    """
    logger.info(
        "Building supervisor graph with model=%s",
        config.supervisor_model,
    )

    # 1. Resolve model — no network call; just object instantiation.
    model = init_chat_model(config.supervisor_model)

    # 2. Format system prompt with runtime context.
    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        date=datetime.date.today().isoformat(),
        available_capabilities=_DEFAULT_AVAILABLE_CAPABILITIES,
        domain_prompt=_PHASE1_DOMAIN_PROMPT,
    )

    # 3. Compile the agent graph — DeepAgents built-ins are wired by middleware.
    #    tools=[]                → no custom tools (FEAT-002 will add them)
    #    subagents=[]            → no subagents   (FEAT-003 will add them)
    #    checkpointer=InMemorySaver → within-process thread-per-session recall
    #       so ``session_manager.invoke(session, …)`` accumulates message history
    #       across turns when called with the same ``thread_id``. Without a
    #       checkpointer, ``thread_id`` plumbing is a no-op and each turn sees
    #       only the current message — breaking the day-1 multi-turn criterion.
    #       Cross-process / cross-session recall requires a persistent saver +
    #       persistent store, landing in FEAT-JARVIS-007.
    graph: CompiledStateGraph[Any, Any, Any, Any] = create_deep_agent(
        model=model,
        tools=[],
        system_prompt=system_prompt,
        subagents=[],
        checkpointer=InMemorySaver(),
    )

    logger.info("Supervisor graph compiled successfully")
    return graph
