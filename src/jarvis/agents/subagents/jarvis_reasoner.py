"""Compiled ``jarvis_reasoner`` AsyncSubAgent graph (FEAT-JARVIS-003).

This module is the single local AsyncSubAgent target referenced by the
supervisor's ``AsyncSubAgent(name="jarvis-reasoner", graph_id="jarvis_reasoner")``
spec. Per ADR-ARCH-011 the three role modes (`critic`, `researcher`, `planner`)
share a single llama-swap-routed model — only the resolved role-specific
system prompt distinguishes the modes.

Architecture references:
    - ADR-ARCH-001 — local-first inference (llama-swap on the GB10).
    - ADR-ARCH-011 — single ``jarvis-reasoner`` subagent with prompt-only
      role differentiation.
    - ADR-ARCH-021 — structured-error contract (never raise; always
      surface a structured error string on the output channel).
    - DDR-010 — leaf graph: no tools, no further subagents.
    - DDR-011 — closed :class:`RoleName` enum.
    - DDR-012 — graph compiles at module import time.
    - ASSUM-004 — empty-string and unknown-role values map onto the
      ``unknown_role`` error branch via ``RoleName(value)`` ``ValueError``.

Compilation contract (DDR-012)
------------------------------
``from jarvis.agents.subagents.jarvis_reasoner import graph`` returns a
fully compiled :class:`~langgraph.graph.state.CompiledStateGraph` without
any further initialisation. ``init_chat_model`` and ``create_deep_agent``
are invoked at import time but neither performs network I/O —
``init_chat_model`` only instantiates a chat-model wrapper (per
TASK-J001-006 supervisor pattern) and ``create_deep_agent`` only assembles
a graph. The actual model is hit only when the supervisor dispatches a
real run via the LangGraph SDK against this graph's ``graph_id``.

``OPENAI_BASE_URL`` is *not* set in this module — the supervisor process
exports it from ``config.llama_swap_base_url`` during lifecycle startup so
llama-swap routing is in effect by the time any real dispatch arrives.
This module therefore has no hard-coded URL.

Graph shape
-----------
``StateGraph[_ReasonerState]`` with a router-style first node:

1. ``resolve_role`` — validates ``input["role"]`` and ``input["prompt"]``,
   maps unknown / empty / missing values onto structured errors via the
   ``async_tasks`` output channel (and a final ``AIMessage`` for the
   conventional ``messages`` channel), and otherwise sets
   ``state["resolved_role"]`` to the matched :class:`RoleName` value.
2. Three role-specific dispatcher nodes (``critic``, ``researcher``,
   ``planner``) each delegate to a pre-compiled inner ``create_deep_agent``
   graph whose ``system_prompt`` was resolved at import to the matching
   :data:`~jarvis.agents.subagents.prompts.ROLE_PROMPTS` entry. Each
   dispatcher catches adapter-level failures (e.g. llama-swap missing the
   ``jarvis-reasoner`` alias on ``/running``) and translates them into the
   structured error contract instead of raising.

The leaf-subagent invariant (DDR-010) is enforced by the ``tools=[]`` and
``subagents=[]`` arguments to ``create_deep_agent`` for every role.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Hashable
from typing import Any, TypedDict

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from jarvis.agents.subagents.prompts import ROLE_PROMPTS
from jarvis.agents.subagents.types import RoleName

__all__ = ["REASONER_MODEL", "graph"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Provider-prefixed model alias resolved by llama-swap to ``gpt-oss-120b``
# (ADR-ARCH-001 + ADR-ARCH-011). The supervisor's lifecycle exports
# ``OPENAI_BASE_URL=<config.llama_swap_base_url>/v1`` before any dispatch so
# this alias routes through llama-swap rather than the real OpenAI cluster.
REASONER_MODEL: str = "openai:jarvis-reasoner"

# Stable enumeration of valid role values, formatted for inclusion in the
# ``unknown_role`` error message. Sourced from :class:`RoleName` so a
# future DDR adding / removing a member updates the error text in lockstep.
_VALID_ROLES_DESCRIPTION: str = "{" + ", ".join(r.value for r in RoleName) + "}"


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class _ReasonerState(TypedDict, total=False):
    """Internal state schema for the ``jarvis_reasoner`` wrapper graph.

    Fields mirror the ``input`` dict shape published by
    :class:`~jarvis.agents.subagents.types.AsyncTaskInput` (``role``,
    ``prompt``, ``correlation_id``) plus three internal channels used by
    the router:

    - ``messages`` — final assistant content surfaced to the
      ``check_async_task`` SDK reader.
    - ``async_tasks`` — structured payload mirroring the supervisor-side
      AsyncSubAgentMiddleware ``async_tasks`` channel; carries the
      correlation_id + output verbatim.
    - ``error`` — non-empty error string when the resolver short-circuits
      to ``END`` instead of dispatching to a role node.
    - ``resolved_role`` — the :class:`RoleName` value chosen by the
      resolver and consumed by the conditional edge router.
    """

    role: str
    prompt: str
    correlation_id: str | None
    messages: list[Any]
    async_tasks: list[dict[str, Any]]
    error: str | None
    resolved_role: str


# ---------------------------------------------------------------------------
# Helpers — structured-error emission (ADR-ARCH-021)
# ---------------------------------------------------------------------------


def _structured_error(message: str, correlation_id: str | None) -> dict[str, Any]:
    """Build a state delta that surfaces a structured error.

    The same error string is mirrored on three channels so consumers can
    read whichever surface they happen to be wired to:

    - ``messages`` — final assistant message (LangGraph SDK
      ``check_async_task`` returns this verbatim).
    - ``async_tasks`` — the supervisor-side AsyncSubAgentMiddleware
      payload shape; ``correlation_id`` is preserved so the originating
      session can re-key its own state.
    - ``error`` — sentinel field consumed by the conditional-edge router
      to short-circuit dispatch to ``END``.

    Per ADR-ARCH-021 the function never raises. Logging is deliberately
    left to caller-site context (``_resolve_role`` logs at ``warning``
    when the input fails validation, dispatcher nodes log at ``warning``
    when llama-swap surfaces an adapter error).
    """
    return {
        "messages": [AIMessage(content=message)],
        "async_tasks": [
            {
                "output": message,
                "correlation_id": correlation_id,
            }
        ],
        "error": message,
    }


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def _resolve_role(state: _ReasonerState) -> dict[str, Any]:
    """First node — validate input and resolve ``role`` to a :class:`RoleName`.

    Mapping (per acceptance criteria):

    +-------------------------------------+---------------------------------+
    | Input shape                         | Behaviour                       |
    +=====================================+=================================+
    | ``role`` key absent / ``None``      | structured ``missing_field``    |
    +-------------------------------------+---------------------------------+
    | ``prompt`` key absent / empty       | structured ``missing_field``    |
    +-------------------------------------+---------------------------------+
    | ``role`` is unknown string (incl.   | structured ``unknown_role``     |
    | ``""``, ``"CRITIC"``, ``"bard"``)   | (catches ``RoleName`` lookup    |
    |                                     | ``ValueError`` per ASSUM-004)   |
    +-------------------------------------+---------------------------------+
    | ``role`` resolves to a member       | sets ``resolved_role`` to the   |
    |                                     | enum value for the conditional  |
    |                                     | router                          |
    +-------------------------------------+---------------------------------+

    Per ADR-ARCH-021 this function never raises — every failure path
    emits a structured error string instead.
    """
    correlation_id = state.get("correlation_id")
    role_value = state.get("role")
    prompt_value = state.get("prompt")

    # Order of checks matters: ``role`` is validated before ``prompt`` so
    # the more obviously-broken contract surfaces first in the operator's
    # logs. Both are "missing_field" so the precedence is cosmetic.
    if role_value is None:
        message = "ERROR: missing_field — role is required"
        logger.warning(
            "jarvis_reasoner_input_invalid",
            extra={"reason": "missing_role", "correlation_id": correlation_id},
        )
        return _structured_error(message, correlation_id)

    if not prompt_value:
        message = "ERROR: missing_field — prompt is required"
        logger.warning(
            "jarvis_reasoner_input_invalid",
            extra={"reason": "missing_prompt", "correlation_id": correlation_id},
        )
        return _structured_error(message, correlation_id)

    try:
        role = RoleName(role_value)
    except ValueError:
        message = (
            f"ERROR: unknown_role — expected one of {_VALID_ROLES_DESCRIPTION}, "
            f"got={role_value!r}"
        )
        logger.warning(
            "jarvis_reasoner_input_invalid",
            extra={
                "reason": "unknown_role",
                "received_role": role_value,
                "correlation_id": correlation_id,
            },
        )
        return _structured_error(message, correlation_id)

    return {"resolved_role": role.value}


def _route_after_resolution(state: _ReasonerState) -> str:
    """Conditional-edge router consumed after :func:`_resolve_role`.

    Returns one of:

    - ``END`` — when the resolver emitted a structured error
      (``state["error"]`` is non-empty) or no role was resolved.
    - ``RoleName.value`` — the matching dispatcher node name; the
      conditional-edges mapping defined in :func:`_build_graph` then
      routes to the role-specific ``create_deep_agent`` node.
    """
    if state.get("error"):
        return END
    role_value = state.get("resolved_role")
    if role_value is None:
        return END
    return role_value


def _make_role_runner(
    role: RoleName,
    deep_agent: CompiledStateGraph[Any, Any, Any, Any],
) -> Callable[[_ReasonerState], Any]:
    """Factory: build the dispatcher node for one role.

    Each role gets a closure that delegates to its pre-compiled inner
    ``create_deep_agent`` graph. The closure also implements the
    adapter-error contract from the AC: any exception bubbling out of
    ``deep_agent.ainvoke`` is caught and translated into a structured
    error string mentioning the ``/running`` endpoint, so that an absent
    ``jarvis-reasoner`` alias on llama-swap surfaces as data on
    ``async_tasks`` instead of an unhandled raise (ADR-ARCH-021).
    """

    async def _run(state: _ReasonerState) -> dict[str, Any]:
        prompt = state.get("prompt") or ""
        correlation_id = state.get("correlation_id")

        try:
            result = await deep_agent.ainvoke(
                {"messages": [HumanMessage(content=prompt)]}
            )
        except Exception as exc:
            message = (
                "ERROR: llama_swap_unavailable — model alias 'jarvis-reasoner' "
                "could not be resolved against the llama-swap /running endpoint "
                f"(role={role.value}, detail={exc!s})"
            )
            logger.warning(
                "jarvis_reasoner_dispatch_failed",
                extra={
                    "role": role.value,
                    "error": str(exc),
                    "correlation_id": correlation_id,
                },
            )
            return _structured_error(message, correlation_id)

        # Extract the assistant's last message content — the SDK reader on
        # ``check_async_task`` reads from this channel.
        messages = result.get("messages", []) if isinstance(result, dict) else []
        output = ""
        if messages:
            last = messages[-1]
            content = getattr(last, "content", None)
            if content is None and isinstance(last, dict):
                content = last.get("content", "")
            output = content or ""

        return {
            "async_tasks": [
                {
                    "output": output,
                    "role": role.value,
                    "correlation_id": correlation_id,
                }
            ],
            "messages": [AIMessage(content=output)] if output else [],
        }

    _run.__name__ = f"_run_{role.value}"
    return _run


# ---------------------------------------------------------------------------
# Graph factory — compiles at import (DDR-012)
# ---------------------------------------------------------------------------


def _build_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compose and compile the ``jarvis_reasoner`` wrapper graph.

    Steps:

    1. Instantiate the shared chat-model wrapper via ``init_chat_model``.
       No network call is issued — the wrapper only validates the
       provider prefix and stores routing info.
    2. Compile one inner ``create_deep_agent`` graph per
       :class:`RoleName` member, each with its resolved system prompt
       from :data:`ROLE_PROMPTS` and ``tools=[]``, ``subagents=[]`` per
       DDR-010 (leaf invariant).
    3. Build the outer :class:`~langgraph.graph.state.StateGraph`:

       - entry node ``resolve_role`` (sync validator + role lookup)
       - one role-specific dispatcher per :class:`RoleName`
       - conditional edges from ``resolve_role`` keyed by
         :class:`RoleName.value` (or ``END`` for the error branch)
       - terminal edges from each dispatcher to ``END``.

    Returns a fully-compiled :class:`CompiledStateGraph`.
    """
    # 1. Shared chat-model wrapper — no network call at construction.
    model = init_chat_model(REASONER_MODEL)

    # 2. Per-role inner deep-agent graphs (leaf — tools=[], subagents=[]).
    role_deep_agents: dict[RoleName, CompiledStateGraph[Any, Any, Any, Any]] = {
        role: create_deep_agent(
            model=model,
            tools=[],
            system_prompt=ROLE_PROMPTS[role],
            subagents=[],
        )
        for role in RoleName
    }

    # 3. Outer wrapper graph.
    builder = StateGraph(_ReasonerState)
    builder.add_node("resolve_role", _resolve_role)
    for role, deep_agent in role_deep_agents.items():
        # langgraph's ``add_node`` infers its node-input TypeVar as
        # ``Never`` (it doesn't propagate StateGraph's ``StateT`` into
        # the ``_Node[NodeInputT_contra]`` protocol), so a typed
        # ``Callable[[_ReasonerState], Any]`` looks incompatible even
        # though it is contravariantly valid at runtime. Suppression is
        # safe — _ReasonerState is the StateGraph schema (line 361
        # above).
        runner = _make_role_runner(role, deep_agent)
        builder.add_node(role.value, runner)  # type: ignore[arg-type]

    builder.set_entry_point("resolve_role")

    # Conditional edges: resolver emits a role value or END.
    role_edge_map: dict[Hashable, str] = {role.value: role.value for role in RoleName}
    role_edge_map[END] = END
    builder.add_conditional_edges(
        "resolve_role",
        _route_after_resolution,
        role_edge_map,
    )

    # Each dispatcher terminates the run.
    for role in RoleName:
        builder.add_edge(role.value, END)

    compiled: CompiledStateGraph[Any, Any, Any, Any] = builder.compile()
    logger.debug(
        "jarvis_reasoner_graph_compiled",
        extra={"roles": [r.value for r in RoleName], "model": REASONER_MODEL},
    )
    return compiled


# ---------------------------------------------------------------------------
# Module-level compiled graph (DDR-012)
# ---------------------------------------------------------------------------

graph: CompiledStateGraph[Any, Any, Any, Any] = _build_graph()
