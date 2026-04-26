"""Tests for the swap-aware voice-ack policy (TASK-J003-019).

Covers TASK-J003-019's second test surface: the ETA-boundary table that
drives :func:`jarvis.infrastructure.lifecycle.should_emit_voice_ack` and
the coupled "queued for dispatch once swap completes" outcome returned
by :func:`jarvis.infrastructure.lifecycle.emit_voice_ack_and_queue`.

This module *replaces* the retired "quick_local fallback" test from the
FEAT-JARVIS-003 scope doc — the supervisor never had a quick_local
fallback path; the swap-aware voice-ack policy is the surviving
mechanism for masking llama-swap warm-up latency on voice-reactive
adapters (ADR-ARCH-012, FEAT-JARVIS-003 design §8).

Acceptance criteria covered (TASK-J003-019):

- AC-019.6 — *parametrised ETA boundary table*: the policy fires iff
  ``adapter`` is voice-reactive AND ``eta_seconds > 30``.  The truth
  table (driven by :func:`pytest.mark.parametrize`) is:

      | eta_seconds | adapter | emit_ack |
      |-------------|---------|----------|
      | 0           | reachy  | False    |
      | 30          | reachy  | False    |
      | 31          | reachy  | True     |
      | 240         | reachy  | True     |
      | 240         | cli     | False    |  (non-voice adapter never gets ack)

- AC-019.7 — *queued-for-dispatch marker*: when the policy fires on a
  voice-reactive session, the supervisor state captures a "queued for
  dispatch once swap completes" marker.  Asserted here against
  :class:`~jarvis.infrastructure.lifecycle.VoiceAckOutcome`'s
  ``queued`` flag.

The TTS pipeline is stubbed in Phase 2 — no audio is played, no I/O
is performed.  The tests assert the outcome's flags and the static ack
copy without any monkey-patching of audio sinks.
"""

from __future__ import annotations

import pytest

from jarvis.adapters.types import SwapStatus
from jarvis.infrastructure.lifecycle import (
    DEFAULT_VOICE_REACTIVE_ADAPTER_IDS,
    VOICE_ACK_ETA_THRESHOLD_SECONDS,
    VOICE_ACK_TTS_TEXT,
    VoiceAckOutcome,
    emit_voice_ack_and_queue,
    should_emit_voice_ack,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_REASONER_ALIAS = "jarvis-reasoner"


def _swap_status(eta_seconds: int) -> SwapStatus:
    """Build a Phase-2 :class:`SwapStatus` for the reasoner alias."""
    return SwapStatus(
        loaded_model=_REASONER_ALIAS,
        eta_seconds=eta_seconds,
        source="stub",
    )


# ---------------------------------------------------------------------------
# AC-019.6 — parametrised ETA boundary table
# ---------------------------------------------------------------------------


# Truth table from TASK-J003-019 AC.  The fifth row asserts that a
# non-voice-reactive adapter (``cli``) never receives an ack regardless
# of ETA — which is also why we keep ``adapter_id`` in the parametrize
# axis instead of folding it into a separate test.
_BOUNDARY_TABLE = [
    pytest.param(0, "reachy", False, id="eta=0_reachy_no_ack"),
    pytest.param(30, "reachy", False, id="eta=30_reachy_no_ack_at_threshold"),
    pytest.param(31, "reachy", True, id="eta=31_reachy_ack_above_threshold"),
    pytest.param(240, "reachy", True, id="eta=240_reachy_ack_cold_start"),
    pytest.param(240, "cli", False, id="eta=240_cli_never_voice_ack"),
]


class TestEtaBoundaryTable:
    """``should_emit_voice_ack`` boundary behaviour across the AC table."""

    @pytest.mark.parametrize(
        ("eta_seconds", "adapter_id", "expected_emit_ack"),
        _BOUNDARY_TABLE,
    )
    def test_should_emit_voice_ack_matches_acceptance_table(
        self,
        eta_seconds: int,
        adapter_id: str,
        expected_emit_ack: bool,
    ) -> None:
        """Each row of the AC table holds verbatim."""
        status = _swap_status(eta_seconds)

        assert should_emit_voice_ack(adapter_id, status) is expected_emit_ack

    @pytest.mark.parametrize(
        ("eta_seconds", "adapter_id", "expected_emit_ack"),
        _BOUNDARY_TABLE,
    )
    def test_emit_voice_ack_and_queue_emitted_flag_matches_table(
        self,
        eta_seconds: int,
        adapter_id: str,
        expected_emit_ack: bool,
    ) -> None:
        """``emit_voice_ack_and_queue`` mirrors the policy decision."""
        status = _swap_status(eta_seconds)

        outcome = emit_voice_ack_and_queue(adapter_id, status)

        assert outcome.emitted is expected_emit_ack

    def test_threshold_constant_is_thirty_seconds(self) -> None:
        """The exclusive boundary lives at 30 seconds (sanity check)."""
        # Guards against an accidental constant change drifting the AC
        # table out of step with the implementation.
        assert VOICE_ACK_ETA_THRESHOLD_SECONDS == 30

    def test_default_voice_reactive_set_contains_reachy_only(self) -> None:
        """``reachy`` is the lone voice-reactive adapter in Phase 2."""
        assert frozenset({"reachy"}) == DEFAULT_VOICE_REACTIVE_ADAPTER_IDS


# ---------------------------------------------------------------------------
# AC-019.7 — when emit_ack=True on a voice-reactive session, the supervisor
# state captures a "queued for dispatch once swap completes" marker; no
# audio I/O in test (stub TTS hook).
# ---------------------------------------------------------------------------


class TestQueuedForDispatchMarkerOnVoiceReactiveSession:
    """When the policy fires, the outcome carries the queued-for-dispatch flag."""

    def test_emit_ack_true_returns_outcome_with_queued_true(self) -> None:
        """voice-reactive + ETA=240 → ``VoiceAckOutcome.queued is True``."""
        status = _swap_status(eta_seconds=240)

        outcome = emit_voice_ack_and_queue("reachy", status)

        assert outcome.emitted is True
        assert outcome.queued is True

    def test_emit_ack_true_returns_voice_ack_outcome_instance(self) -> None:
        """The marker is carried by the typed :class:`VoiceAckOutcome`."""
        status = _swap_status(eta_seconds=240)

        outcome = emit_voice_ack_and_queue("reachy", status)

        assert isinstance(outcome, VoiceAckOutcome)

    def test_emit_ack_true_outcome_carries_static_ack_text(self) -> None:
        """The TTS ack copy is the canonical ``VOICE_ACK_TTS_TEXT`` constant."""
        status = _swap_status(eta_seconds=240)

        outcome = emit_voice_ack_and_queue("reachy", status)

        assert outcome.ack_text == VOICE_ACK_TTS_TEXT
        assert outcome.ack_text is not None
        # The Phase 2 ack stub must be a non-empty user-facing string —
        # the supervisor passes it directly to the TTS pipeline.
        assert len(outcome.ack_text) > 0

    def test_emit_ack_false_returns_outcome_with_queued_false(self) -> None:
        """ETA at threshold → no ack, no queueing, no ack text."""
        status = _swap_status(eta_seconds=30)

        outcome = emit_voice_ack_and_queue("reachy", status)

        assert outcome.emitted is False
        assert outcome.queued is False
        assert outcome.ack_text is None

    def test_emit_ack_false_for_non_voice_adapter_at_high_eta(self) -> None:
        """Non-voice-reactive adapter (``cli``) never queues, even at ETA=240."""
        status = _swap_status(eta_seconds=240)

        outcome = emit_voice_ack_and_queue("cli", status)

        assert outcome.emitted is False
        assert outcome.queued is False
        assert outcome.ack_text is None

    def test_emit_ack_voice_outcome_does_not_mutate_input_swap_status(
        self,
    ) -> None:
        """The policy is read-only — the input :class:`SwapStatus` is unchanged.

        :class:`SwapStatus` is frozen so mutation would raise; this test
        captures the *value* before and after the call to make the
        guarantee visible to future readers.
        """
        status = _swap_status(eta_seconds=240)
        snapshot = (status.loaded_model, status.eta_seconds, status.source)

        emit_voice_ack_and_queue("reachy", status)

        assert (status.loaded_model, status.eta_seconds, status.source) == snapshot


# ---------------------------------------------------------------------------
# Phase-2 hygiene — no audio I/O in this test module
# ---------------------------------------------------------------------------


class TestNoAudioOrNetworkIoFromVoiceAckPolicy:
    """The voice-ack policy helpers are pure — they touch no audio sink."""

    def test_should_emit_voice_ack_returns_only_a_bool(self) -> None:
        """The decision helper returns a plain ``bool`` — no side effects."""
        status = _swap_status(eta_seconds=240)

        result = should_emit_voice_ack("reachy", status)

        assert isinstance(result, bool)

    def test_emit_voice_ack_and_queue_returns_only_a_dataclass(self) -> None:
        """The orchestration helper returns a frozen dataclass — no audio."""
        status = _swap_status(eta_seconds=240)

        outcome = emit_voice_ack_and_queue("reachy", status)

        # The returned value is the only observable effect — the helper
        # does not, in Phase 2, hand a buffer to the TTS pipeline.
        assert isinstance(outcome, VoiceAckOutcome)

    def test_custom_voice_reactive_set_overrides_default_without_mutation(
        self,
    ) -> None:
        """The override path does not mutate the module-level default set."""
        before = set(DEFAULT_VOICE_REACTIVE_ADAPTER_IDS)
        status = _swap_status(eta_seconds=240)

        # Pass an override that includes ``cli`` — the call must succeed
        # and treat ``cli`` as voice-reactive for this invocation only.
        result = should_emit_voice_ack(
            "cli",
            status,
            voice_reactive_adapters=frozenset({"cli"}),
        )

        assert result is True
        # The module-level default must remain unchanged after the call.
        assert set(DEFAULT_VOICE_REACTIVE_ADAPTER_IDS) == before
