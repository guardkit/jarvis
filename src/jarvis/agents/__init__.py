"""Agent definitions package for Jarvis.

Exports the public factory for the supervisor agent graph:

- :func:`build_supervisor` — builds the Phase 1 supervisor CompiledStateGraph.
"""

from .supervisor import build_supervisor

__all__ = ["build_supervisor"]
