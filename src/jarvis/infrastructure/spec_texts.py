"""Bounded in-process store of the worked examples behind a spec digest card.

The seam between the two halves of the spec digest surface (machine chain,
stage 2 — 2026-08-14):

* **Writer** — the planning checkpoint renderer
  (``assumption_dialogue.PlanningCheckpointRenderer``) keeps the card's worked
  examples, keyed by ``request_id``, at the moment it posts the card.
* **Reader** — the Slack reply handler (``slack_reply.ApprovalReplyHandler``)
  reads them when the owner taps "Show the worked examples", and shows them in
  a read-only view.

Both halves are constructed in ``lifecycle.build_app_state``, which wires ONE
store into each — the same shape as the terminal-build registry
(``terminal_builds.TerminalBuildRegistry``), for the same reason: two objects
in one process need one fact between them.

WHY THIS EXISTS, HONESTLY. The design of record says the "show me" view fetches
the examples "from the durable record, keyed by the card's request_id". There is
no such record reachable from here: jarvis holds no planning database, and the
examples are far too long for a Slack button value (2000 characters) or a
``block_id`` (255). The examples arrive once, on the approval request, and the
only place to keep them until a click is memory. So that is what this is, said
plainly rather than dressed up as durability.

Restart degrade (the design, not an accident): the map is in-process and
in-memory. After a jarvis restart it is EMPTY, and a tap on "Show the worked
examples" is answered honestly — the examples are on the run's own branch — and
nothing else changes. The card's list is untouched, and the list is the thing
that was mechanically checked against the spec; the view behind the button is a
convenience, never the ask. No decision depends on this store, which is why
losing it costs a sentence and not a run.

Bounds: entries expire after ``ttl_seconds`` (swept on every record/get) and
the map never exceeds ``max_entries`` (eldest recording evicted first). A spec
is a few kilobytes of text, so the default bounds cost well under a megabyte.

Time-dependent behaviour is driven by the injectable ``_monotonic`` alias
(tests patch ``jarvis.infrastructure.spec_texts._monotonic``, never
``time.monotonic`` — freezing the stdlib attribute hangs the event-loop clock;
the same convention as ``terminal_builds`` and ``slack_notifier``).
"""

from __future__ import annotations

import dataclasses
import time

# Default TTL on a held spec. A card stays tappable in Slack indefinitely, but
# the run behind it closes its answer window in an hour by default; a day is
# generous cover for that and still bounded.
_DEFAULT_TTL_SECONDS = 86400.0

# Hard cap on retained entries (eldest recording evicted first).
_DEFAULT_MAX_ENTRIES = 64

# Injectable monotonic-clock seam (see module docstring).
_monotonic = time.monotonic


@dataclasses.dataclass(frozen=True, slots=True)
class SpecTextRecord:
    """The worked examples of one spec digest card, as they were posted."""

    feature: str
    spec_text: str
    recorded_at_mono: float


class SpecTextRegistry:
    """Bounded, TTL-swept map of ``request_id`` → the card's worked examples."""

    __slots__ = ("_max_entries", "_records", "_ttl_seconds")

    def __init__(
        self,
        *,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        # Insertion-ordered: the eldest recording is the first key.
        self._records: dict[str, SpecTextRecord] = {}

    def record(self, *, request_id: str, feature: str, spec_text: str) -> None:
        """Hold one card's worked examples. A falsy ``request_id`` is ignored."""
        if not request_id:
            return
        self._sweep()
        # Re-recording the same card moves it to the back of the eviction queue
        # (it is the most recent thing the owner has been shown).
        self._records.pop(request_id, None)
        self._records[request_id] = SpecTextRecord(
            feature=feature,
            spec_text=spec_text,
            recorded_at_mono=_monotonic(),
        )
        while len(self._records) > self._max_entries:
            self._records.pop(next(iter(self._records)))

    def get(self, request_id: str) -> SpecTextRecord | None:
        """The held examples for ``request_id``, or ``None`` (expired/never held)."""
        if not request_id:
            return None
        self._sweep()
        return self._records.get(request_id)

    def _sweep(self) -> None:
        cutoff = _monotonic() - self._ttl_seconds
        expired = [key for key, record in self._records.items() if record.recorded_at_mono < cutoff]
        for key in expired:
            self._records.pop(key, None)


__all__ = ["SpecTextRecord", "SpecTextRegistry"]
