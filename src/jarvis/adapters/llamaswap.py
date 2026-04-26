"""LlamaSwap adapter — first Group-D adapter per ADR-ARCH-006 / DDR-015.

Reads the *shape* of llama-swap's HTTP control surface but does not hit
the network in Phase 2. The read path is exposed via a keyword-only
``_stub_response`` test seam that production callers leave at its
default of :data:`None`.

Live endpoint paths (FEAT-JARVIS-004 will swap the stub for real probes
against ``http://promaxgb10-41b1:9000``):

- ``GET /running`` — list of currently loaded model aliases plus the
  ``eta_seconds`` countdown for any alias still warming up.
- ``GET /log`` — rolling supervisor log, scraped for swap progress when
  ``/running`` is silent.

The Phase 2 stub contract — ``SwapStatus(loaded_model=<alias>,
eta_seconds=0|>0, source="stub")`` — must match the live-read shape so
FEAT-JARVIS-004 is a transport swap, not a schema swap (Context A
concern #2).

This module performs no I/O at import and makes no outbound HTTP calls
at runtime.
"""

from __future__ import annotations

from collections.abc import Callable

from .types import SwapStatus

__all__ = ["LlamaSwapAdapter"]


class LlamaSwapAdapter:
    """Thin transport seam over llama-swap's ``/running`` + ``/log`` endpoints.

    Phase 2 (this task) is read-only and stubbed: ``get_status`` returns
    a :class:`~jarvis.adapters.types.SwapStatus` for the requested alias
    without touching the network. FEAT-JARVIS-004 will replace the stub
    with a live HTTP probe against ``base_url`` while keeping this
    class's public surface stable.

    The adapter is intentionally state-free: ``get_status`` is pure and
    idempotent, so the supervisor can call it as often as it needs to
    without worrying about hidden counters or caches. ETA interpretation
    (e.g. "eta > 30 seconds means escalate") lives in the supervisor's
    voice-latency policy (ADR-ARCH-012) — not here.

    Attributes:
        base_url: Base URL for the live llama-swap server. Stored for
            FEAT-JARVIS-004's HTTP client; ignored by the Phase 2 stub
            path.

    Args:
        base_url: Live llama-swap base URL (``http://<host>:9000``).
        _stub_response: **Test seam** — an optional callable that takes
            the requested ``alias`` and returns a :class:`SwapStatus`.
            Production callers MUST NOT pass this argument; tests use it
            to drive the read path deterministically (e.g. simulate a
            cold-start ``eta_seconds=180`` snapshot). Keyword-only by
            design so positional calls cannot accidentally inject a
            stub. The adapter forwards the callable's return value
            verbatim — it does not interpret or rewrite the ETA, the
            source, or the loaded-model alias.
    """

    def __init__(
        self,
        base_url: str,
        *,
        _stub_response: Callable[[str], SwapStatus] | None = None,
    ) -> None:
        self.base_url = base_url
        self._stub_response = _stub_response

    def get_status(self, alias: str) -> SwapStatus:
        """Return a :class:`SwapStatus` snapshot for ``alias``.

        When a ``_stub_response`` callable was supplied at construction,
        it is invoked with ``alias`` and its return value is forwarded
        unchanged. Otherwise the adapter assumes the alias is already
        loaded and returns
        ``SwapStatus(loaded_model=alias, eta_seconds=0, source="stub")``
        — the FEAT-JARVIS-004 live path will replace this default with
        the result of a ``GET /running`` probe.

        Args:
            alias: llama-swap model alias to probe (e.g.
                ``"qwen3-coder"``).

        Returns:
            Frozen :class:`SwapStatus` describing the alias's load
            state. The caller (typically the supervisor) is responsible
            for interpreting ``eta_seconds`` against its swap-aware
            voice-latency policy.
        """
        if self._stub_response is not None:
            return self._stub_response(alias)
        return SwapStatus(loaded_model=alias, eta_seconds=0, source="stub")
