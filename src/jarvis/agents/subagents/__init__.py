"""Subagent package for the Jarvis reasoner.

This package hosts the ``jarvis-reasoner`` AsyncSubAgent contract for
FEAT-JARVIS-003: the closed :class:`RoleName` enum (DDR-011), the
:class:`AsyncTaskInput` payload model, the role-prompt registry, and
the compiled sub-graph itself.

The :data:`graph` symbol is re-exported here so that ``langgraph.json``
can bind the ``jarvis_reasoner`` graph by the package-level dotted path
``jarvis.agents.subagents:graph`` (TASK-J003-009 AC-008). Importing the
package therefore *does* trigger compilation of the
:mod:`jarvis.agents.subagents.jarvis_reasoner` sub-module — DDR-012
mandates compile-at-import for the leaf graph. ``init_chat_model`` is
invoked during that compilation but performs no network I/O (it merely
instantiates a chat-model wrapper); see the docstring on
:mod:`jarvis.agents.subagents.jarvis_reasoner` for the full contract.

The lighter type-surface (``RoleName``, ``AsyncTaskInput``) remains
importable without forcing the heavier graph compile when callers want
only the typed contracts — ``from jarvis.agents.subagents.types import
RoleName`` keeps the original side-effect-free path intact.
"""

from __future__ import annotations

from jarvis.agents.subagents.jarvis_reasoner import graph
from jarvis.agents.subagents.types import AsyncTaskInput, RoleName

__all__ = ["AsyncTaskInput", "RoleName", "graph"]
