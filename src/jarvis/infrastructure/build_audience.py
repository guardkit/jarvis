"""Bounded in-memory registry of *who to tell* when a build ends.

The sibling of :mod:`jarvis.infrastructure.terminal_builds`: that module
records *what happened* to a build, this one records *who was waiting to
hear about it*.

The defect it exists for (observed live 2026-08-15, planning run
``71c5e49a`` / build ``build-FEAT-D9A6-20260815104250``): planning-side
notifications @-mention the owner via ``NotificationPayload.target_user``
(``planning_notifier._render``), but the build-side line
(``slack_notifier._render``) mentioned nobody. The build finished, jarvis
posted a bare ``Pipeline FEAT-D9A6: build-complete (PASSED)``, and nobody
noticed for an hour.

Three writers, one reader — all in ONE process (``jarvis-serve-nats``
runs the planning notifier, the approval reply handler and the
notification sink on the same supervisor event loop):

* **Writer — planning notifier.** Every planning notification carries the
  owner's member id for its ``correlation_id``; forge threads that same
  correlation onto the outbound build envelopes, so it is the strongest
  join available.
* **Writer — approval reply handler.** The member id of whoever actually
  tapped the gate for a ``build_id``: they asked for this build, so they
  are the right person to tell it finished.
* **Reader — the notification sink.** On a terminal build event it asks
  correlation first, then build, then falls back to a sole configured
  operator (see ``slack_notifier._resolve_mention_target``).

Bounds and degrade (state it plainly — this is the design, DDR-027): both
maps are in-process, in-memory and capped; the eldest recording is
evicted at the cap, and a jarvis restart empties them. A miss is never an
error — it means "nobody known", and the build line then posts unmentioned
exactly as it did before this module existed. There is no TTL: unlike a
terminal record (which must expire so a stale card is not answered from
memory), a stale audience entry is only ever consulted by an event
carrying the very same correlation or build id, so age carries no risk —
the cap alone bounds the memory.

Not thread-safe and needs no lock: every reader and writer runs on the one
supervisor event loop and no method awaits.
"""

from __future__ import annotations

# Hard cap per map (eldest recording evicted first). A member id and a key
# are two short strings; 512 builds' worth of them is trivial memory, and
# the estate never has anything close to that many builds in flight.
_DEFAULT_MAX_ENTRIES = 512


class BuildAudienceRegistry:
    """Two bounded maps: ``correlation_id -> member id`` and ``build_id -> member id``.

    Every method is total: falsy keys and falsy values are ignored on the
    write side and answered with ``None`` on the read side, so no caller
    needs a guard of its own.
    """

    __slots__ = ("_clickers", "_max_entries", "_targets")

    def __init__(self, *, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._max_entries = max_entries
        # Insertion-ordered by recording time (a re-record re-inserts), so
        # eviction pops the eldest recording first.
        self._targets: dict[str, str] = {}
        self._clickers: dict[str, str] = {}

    # -- planning side: correlation_id -> the notified owner --------------

    def record_planning_target(self, correlation_id: str | None, member_id: str | None) -> None:
        """Record the member id a planning notification @-mentioned."""
        self._record(self._targets, correlation_id, member_id)

    def planning_target(self, correlation_id: str | None) -> str | None:
        """The member id planning notifications mention for this run, or ``None``."""
        if not correlation_id:
            return None
        return self._targets.get(correlation_id)

    # -- gate side: build_id -> the operator who tapped ------------------

    def record_gate_clicker(self, build_id: str | None, member_id: str | None) -> None:
        """Record the member id that decided this build's approval gate."""
        self._record(self._clickers, build_id, member_id)

    def gate_clicker(self, build_id: str | None) -> str | None:
        """The member id that tapped this build's gate, or ``None``."""
        if not build_id:
            return None
        return self._clickers.get(build_id)

    # -- shared bounded-write primitive ----------------------------------

    def _record(self, entries: dict[str, str], key: str | None, member_id: str | None) -> None:
        if not key or not member_id:
            return
        # Re-insert so a re-record moves to the back of eviction order.
        entries.pop(key, None)
        entries[key] = member_id
        while len(entries) > self._max_entries:
            del entries[next(iter(entries))]


__all__ = ["BuildAudienceRegistry"]
