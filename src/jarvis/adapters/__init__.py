"""Public adapter surface for the Jarvis runtime.

The ``jarvis.adapters`` package was reserved-empty during Phase 1
(ADR-ARCH-006) and is being populated through FEAT-JARVIS-003 / -004
as the Group-D adapters land. The first one — :class:`LlamaSwapAdapter`
(TASK-J003-007) — exposes a stubbed read path over llama-swap's
``/running`` + ``/log`` endpoints; FEAT-JARVIS-004 swaps the stub for
a live HTTP probe without changing the public surface.

NATS / Graphiti adapters land in subsequent waves and will join this
re-export list.
"""

from .llamaswap import LlamaSwapAdapter
from .types import SwapStatus

__all__ = ["LlamaSwapAdapter", "SwapStatus"]
