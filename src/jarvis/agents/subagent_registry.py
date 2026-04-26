"""AsyncSubAgent registry for the Jarvis supervisor (FEAT-JARVIS-003).

This module exposes the single public factory
:func:`build_async_subagents` which returns the list of
:class:`AsyncSubAgent` specs the supervisor wires via
``async_subagents=`` at build time. Per ADR-ARCH-011 + DDR-010 the
list contains *exactly one* entry — the local ``jarvis-reasoner``
subagent that fronts the three role-mode prompts (critic / researcher
/ planner) over the shared local model alias.

The DDR-010 routing contract is encoded by the spec's ``description``
text: the reasoning model uses it to choose when to delegate, so the
description must surface the cost + latency signals the model needs
without leaking any four-roster legacy names (see Context A concern
#3 / TASK-J003-020 regression test).

Architecture references
-----------------------
- ADR-ARCH-001 — local-first inference (llama-swap on the GB10).
- ADR-ARCH-011 — single ``jarvis-reasoner`` subagent.
- DDR-010 — description text *is* the routing contract.
- DDR-012 — leaf graph compiles at module import time
  (:mod:`jarvis.agents.subagents.jarvis_reasoner`).

Purity contract
---------------
:func:`build_async_subagents` performs no network I/O, no model
instantiation, and reads only the supplied :class:`JarvisConfig`. The
``description`` string is a module-level constant so the function is
deterministic — successive calls with the same config produce
byte-identical output, which Graphiti relies on for trace richness.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deepagents import AsyncSubAgent

if TYPE_CHECKING:
    from jarvis.config.settings import JarvisConfig

__all__ = ["AsyncSubAgent", "build_async_subagents"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public name + graph_id constants.
#
# ``_REASONER_NAME`` is the ``async_subagents=`` key the supervisor uses
# when calling ``start_async_task(name=…)``; the literal value MUST stay
# stable so prompt fragments and routing rules remain valid across
# refactors.
#
# ``_REASONER_GRAPH_ID`` is the LangGraph graph identifier that
# ``langgraph.json`` binds to the compiled graph re-exported via
# :mod:`jarvis.agents.subagents` (see AC-008 of TASK-J003-009).
# ---------------------------------------------------------------------------
_REASONER_NAME: str = "jarvis-reasoner"
_REASONER_GRAPH_ID: str = "jarvis_reasoner"


# ---------------------------------------------------------------------------
# Routing description — DDR-010 contract.
#
# Every substring asserted by the AC must appear verbatim:
#
# - ``gpt-oss-120b``           — the underlying local model.
# - ``on the premises``        — locality signal (no network egress).
# - ``sub-second``             — fast-path latency budget.
# - ``two to four minutes``    — slow-path latency budget for
#                                researcher / planner runs.
# - ``critic`` / ``researcher`` / ``planner`` — the three role modes.
#
# Forbidden substrings are enumerated in the TASK-J003-020 regression
# test (the legacy four-roster names plus any cloud-tier promise). The
# tokens are deliberately not duplicated here so the source tree stays
# free of them; new routing copy is authored here, never auto-generated
# from a legacy roster.
# ---------------------------------------------------------------------------
_REASONER_DESCRIPTION: str = (
    "Local Jarvis reasoning subagent backed by the gpt-oss-120b model "
    "running on the premises (no network egress). Selects one of three "
    "role modes per call: critic for sub-second adversarial review of an "
    "in-flight plan, researcher for two to four minutes of grounded "
    "investigation across the supplied prompt context, and planner for "
    "two to four minutes of multi-step decomposition. Delegate here "
    "whenever the supervisor needs a focused reasoning pass that does "
    "not require external tools or fleet capabilities."
)


def build_async_subagents(config: JarvisConfig) -> list[AsyncSubAgent]:
    """Return the supervisor's ``async_subagents=`` list.

    Per ADR-ARCH-011 + DDR-010 the list contains *exactly one* entry —
    the local ``jarvis-reasoner`` AsyncSubAgent. The element's
    ``description`` is the routing contract; cost + latency signals
    must remain readable by the reasoning model.

    The function is pure: given the same config it returns the same
    specification text. ``config`` is accepted (rather than read from a
    module global) so future fields — e.g. a pluggable description
    overlay or a remote-deployment URL — can be threaded through
    without breaking call sites. For TASK-J003-009 only the
    deterministic constant text is used; the parameter is logged for
    traceability and otherwise unread.

    Args:
        config: Validated :class:`~jarvis.config.settings.JarvisConfig`
            instance. Currently unused beyond logging; retained in the
            signature for forward compatibility per the AC.

    Returns:
        A fresh ``list[AsyncSubAgent]`` of length 1. Each call
        constructs a new list and dict so the supervisor cannot
        inadvertently mutate shared module state.
    """
    logger.debug(
        "build_async_subagents: composing supervisor async-subagent spec",
        extra={
            "supervisor_model": config.supervisor_model,
            "reasoner_name": _REASONER_NAME,
            "reasoner_graph_id": _REASONER_GRAPH_ID,
        },
    )

    spec: AsyncSubAgent = {
        "name": _REASONER_NAME,
        "description": _REASONER_DESCRIPTION,
        "graph_id": _REASONER_GRAPH_ID,
    }

    return [spec]
