"""Tests for :mod:`jarvis.adapters.llamaswap` (TASK-J003-019).

This module covers TASK-J003-019's first test surface: the stubbed
``LlamaSwapAdapter`` plus the ``SwapStatus`` validation seam that the
adapter forwards.  It is deliberately scoped to the five acceptance
criteria listed in the task — it does NOT replicate the broader
TASK-J003-007 sweep (constructor signature introspection, package
re-export, AST scan for forbidden HTTP imports) which lives in
``test_llamaswap_adapter.py``.

Acceptance criteria covered (TASK-J003-019):

- AC-019.1 — *default stub*: ``LlamaSwapAdapter(base_url="http://stub")
  .get_status("jarvis-reasoner")`` returns
  ``SwapStatus(loaded_model="jarvis-reasoner", eta_seconds=0,
  source="stub")``.
- AC-019.2 — *degraded stub*: a ``_stub_response`` callable returning
  ``SwapStatus(loaded_model="jarvis-reasoner", eta_seconds=180,
  source="stub")`` flows through unchanged (boundary for the
  >30s-ETA branch consumed by the voice-ack policy).
- AC-019.3 — *negative ETA rejected at model level*:
  ``SwapStatus(loaded_model="x", eta_seconds=-1)`` raises
  :class:`pydantic.ValidationError` (scenario: *Swap status enforces a
  non-negative ETA*).
- AC-019.4 — *idempotency*: three successive calls to
  ``get_status("jarvis-reasoner")`` return equivalent
  :class:`SwapStatus` instances; no internal counter mutated (scenario:
  *Repeated swap-status reads for the same alias return consistent
  results*).
- AC-019.5 — *source marker*: the default stub path returns
  ``source="stub"`` (scenario: *The llama-swap adapter reports a stub
  source in Phase 2*).

The tests do not perform network I/O and do not call live providers —
the adapter's Phase 2 contract is deterministic and fully synchronous.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from jarvis.adapters.llamaswap import LlamaSwapAdapter
from jarvis.adapters.types import SwapStatus

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_REASONER_ALIAS = "jarvis-reasoner"
_STUB_BASE_URL = "http://stub"


# ---------------------------------------------------------------------------
# AC-019.1 — default stub returns the loaded snapshot for the alias
# ---------------------------------------------------------------------------


class TestDefaultStubReturnsLoadedSnapshot:
    """``LlamaSwapAdapter(base_url=...).get_status(alias)`` defaults."""

    def test_default_get_status_returns_eta_zero_stub_source_for_reasoner_alias(
        self,
    ) -> None:
        """Default stub: ``jarvis-reasoner`` resolves to the loaded snapshot."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        result = adapter.get_status(_REASONER_ALIAS)

        assert result == SwapStatus(
            loaded_model=_REASONER_ALIAS,
            eta_seconds=0,
            source="stub",
        )

    def test_default_get_status_returns_swapstatus_instance(self) -> None:
        """Default stub returns a :class:`SwapStatus` value object."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        result = adapter.get_status(_REASONER_ALIAS)

        assert isinstance(result, SwapStatus)


# ---------------------------------------------------------------------------
# AC-019.2 — degraded stub forwards ETA=180 unchanged (>30s branch boundary)
# ---------------------------------------------------------------------------


class TestDegradedStubForwardedUnchanged:
    """``_stub_response`` returning ETA=180 flows through unchanged."""

    def test_degraded_stub_callable_eta_180_flows_through_unchanged(self) -> None:
        """Adapter does not interpret ETA — ETA=180 is returned verbatim."""
        degraded = SwapStatus(
            loaded_model=_REASONER_ALIAS,
            eta_seconds=180,
            source="stub",
        )

        adapter = LlamaSwapAdapter(
            base_url=_STUB_BASE_URL,
            _stub_response=lambda _alias: degraded,
        )

        result = adapter.get_status(_REASONER_ALIAS)

        # Equivalence by value (frozen Pydantic models hash by field tuple).
        assert result == degraded
        assert result.loaded_model == _REASONER_ALIAS
        assert result.eta_seconds == 180
        assert result.source == "stub"

    def test_degraded_stub_alias_is_forwarded_to_callable(self) -> None:
        """The adapter passes the requested alias to the stub callable."""
        captured: list[str] = []

        def stub(alias: str) -> SwapStatus:
            captured.append(alias)
            return SwapStatus(loaded_model=alias, eta_seconds=180, source="stub")

        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL, _stub_response=stub)

        adapter.get_status(_REASONER_ALIAS)

        assert captured == [_REASONER_ALIAS]


# ---------------------------------------------------------------------------
# AC-019.3 — negative ETA rejected at the model level
# ---------------------------------------------------------------------------


class TestNegativeEtaRejectedAtModelLevel:
    """``SwapStatus(eta_seconds=-1)`` raises ``ValidationError``."""

    def test_construct_swapstatus_with_negative_eta_raises_validation_error(
        self,
    ) -> None:
        """Pydantic enforces ``ge=0`` — ``-1`` is rejected at construction."""
        with pytest.raises(ValidationError):
            SwapStatus(loaded_model="x", eta_seconds=-1)

    def test_negative_eta_validation_error_mentions_eta_seconds_field(self) -> None:
        """The validation error names the ``eta_seconds`` field for diagnostics."""
        with pytest.raises(ValidationError) as exc_info:
            SwapStatus(loaded_model="x", eta_seconds=-1)

        # Pydantic's ValidationError exposes ``.errors()`` as a list of dicts
        # — at least one entry must point at ``eta_seconds``.
        offending_locations = {tuple(err["loc"]) for err in exc_info.value.errors()}
        assert ("eta_seconds",) in offending_locations


# ---------------------------------------------------------------------------
# AC-019.4 — idempotency: three successive default reads
# ---------------------------------------------------------------------------


class TestIdempotentReadsForSameAlias:
    """Three successive ``get_status`` calls return equivalent snapshots."""

    def test_three_successive_default_reads_for_reasoner_alias_are_equivalent(
        self,
    ) -> None:
        """Repeated reads of the same alias compare equal (no drift)."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        first = adapter.get_status(_REASONER_ALIAS)
        second = adapter.get_status(_REASONER_ALIAS)
        third = adapter.get_status(_REASONER_ALIAS)

        assert first == second == third

    def test_three_successive_reads_do_not_mutate_internal_state(self) -> None:
        """Reading is pure — no attribute on the adapter instance is bumped."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        before = dict(adapter.__dict__)
        for _ in range(3):
            adapter.get_status(_REASONER_ALIAS)
        after = dict(adapter.__dict__)

        assert before == after

    def test_three_successive_reads_each_have_eta_zero(self) -> None:
        """Each of the three reads still resolves to the loaded snapshot."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        snapshots = [adapter.get_status(_REASONER_ALIAS) for _ in range(3)]

        assert all(snap.eta_seconds == 0 for snap in snapshots)


# ---------------------------------------------------------------------------
# AC-019.5 — source marker on the default stub path
# ---------------------------------------------------------------------------


class TestDefaultStubSourceMarker:
    """The default path reports ``source="stub"`` (Phase 2 marker)."""

    def test_default_stub_source_marker_is_stub(self) -> None:
        """The Phase 2 stub adapter labels its output ``source="stub"``."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        result = adapter.get_status(_REASONER_ALIAS)

        assert result.source == "stub"

    def test_default_stub_source_is_stub_for_arbitrary_alias(self) -> None:
        """The marker is alias-independent — every default read is stubbed."""
        adapter = LlamaSwapAdapter(base_url=_STUB_BASE_URL)

        for alias in ("jarvis-reasoner", "qwen3-coder", "some-future-alias"):
            assert adapter.get_status(alias).source == "stub"
