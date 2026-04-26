"""Subagent package for the Jarvis reasoner.

This package hosts the ``jarvis-reasoner`` AsyncSubAgent contract for
FEAT-JARVIS-003: the closed :class:`RoleName` enum (DDR-011), the
:class:`AsyncTaskInput` payload model, and — in subsequent tasks — the
role-prompt registry and compiled sub-graph itself.

Importing the package itself has no side-effects; see
:mod:`jarvis.agents.subagents.types` for the v1 type surface.
"""

from __future__ import annotations

from jarvis.agents.subagents.types import AsyncTaskInput, RoleName

__all__ = ["AsyncTaskInput", "RoleName"]
