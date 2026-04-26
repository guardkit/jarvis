"""Adapter-layer Pydantic models for the Jarvis adapters package.

Defines the structured types surfaced by Jarvis adapters that mediate
between the supervisor / subagent graphs and external services.

Per DM-subagent-types §4, DDR-015 and TASK-J003-003:

- :class:`SwapStatus` — snapshot of llama-swap builders-group state for
  a requested model alias.

Phase 2 emits :class:`SwapStatus` instances with ``source="stub"`` from
``LlamaSwapAdapter``'s stubbed health probe. FEAT-JARVIS-004 will switch
to ``source="live"`` once the live HTTP probe lands.

This module performs no I/O at import and makes no LLM calls.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["SwapStatus"]


class SwapStatus(BaseModel):
    """Snapshot of llama-swap builders-group state for a requested alias.

    Constructed by :class:`LlamaSwapAdapter` (stubbed in Phase 2; live in
    FEAT-JARVIS-004) and consumed by the supervisor's swap-aware
    voice-latency policy per ADR-ARCH-012.

    Attributes:
        loaded_model: llama-swap alias currently loaded.
        eta_seconds: Estimated seconds until the requested alias is
            ready (``0`` means already loaded). Pydantic enforces
            non-negativity via ``ge=0`` — construction with ``-1`` raises
            :class:`pydantic.ValidationError`.
        source: ``"stub"`` for Phase 2 / test fixtures (default);
            ``"live"`` once FEAT-JARVIS-004 wires the real HTTP probe.
    """

    model_config = ConfigDict(frozen=True)

    loaded_model: str
    eta_seconds: int = Field(ge=0)
    source: Literal["stub", "live"] = "stub"
