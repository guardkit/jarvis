"""Bounded TTL registry of terminal build states (approval-card truth R3-B).

The shared-state seam between the two halves of the Slack approval
surface (options card ``approval-surface-truth-options-card-2026-07-30``,
R3-B):

* **Writer** — the notification sink (``slack_notifier.SlackNotifier``)
  records every terminal build event it observes (``build_cancelled``,
  ``build_complete``, ``build_failed``) keyed by ``build_id``.
* **Reader** — the Slack reply handler (``slack_reply.ApprovalReplyHandler``)
  consults the registry between first-click-wins and the NATS publish: a
  tap on a build already known terminal is answered honestly on the card
  ("your tap was not recorded") and NEVER published — forge would only
  drop the response silently (no active waiter) while the card lied
  "Decision recorded".

Both halves are constructed in ``lifecycle.build_app_state``, which wires
ONE registry instance into each.

Restart degrade (state this plainly — it is the design, DDR-027): all
state is in-process and in-memory. After a jarvis restart the map is
EMPTY, every consult misses, and behaviour degrades exactly to today's —
the tap publishes, forge drops it if the build is terminal, and the card
shows "Decision recorded". The registry narrows the lying window; it
does not close it across restarts.

Bounds: entries expire after ``ttl_seconds`` (swept on every record/get)
and the map never exceeds ``max_entries`` (eldest recording evicted
first). Values are three small strings and a datetime — memory is
trivial at these bounds.

Time-dependent behaviour is driven by the injectable ``_monotonic``
alias (tests patch ``jarvis.infrastructure.terminal_builds._monotonic``,
never ``time.monotonic`` — freezing the stdlib attribute hangs the
event-loop clock; same convention as ``slack_notifier``).
"""

from __future__ import annotations

import dataclasses
import time
from datetime import datetime

# Default TTL on a terminal record. Generous by design: the 07-28
# occurrence was a tap 51 minutes post-cancel, and cards stay tappable in
# Slack indefinitely — 24h covers an unattended overnight window while
# keeping the map bounded (a restart clears it regardless).
_DEFAULT_TTL_SECONDS = 86400.0

# Hard cap on retained entries (eldest recording evicted first).
_DEFAULT_MAX_ENTRIES = 1024

# Injectable monotonic-clock seam (see module docstring).
_monotonic = time.monotonic


def render_local_hhmm(at: datetime) -> str:
    """Render ``at`` as local-time ``HH:MM`` (the card timestamp shape).

    Timezone-aware datetimes shift into the host's local zone via
    ``astimezone()``; naive datetimes format unchanged — byte-identical
    to the rendering convention in ``slack_notifier``.
    """
    local_at = at.astimezone() if at.tzinfo is not None else at
    return local_at.strftime("%H:%M")


@dataclasses.dataclass(frozen=True)
class TerminalBuildRecord:
    """One observed terminal state for a build.

    ``at`` is the retained ``ForgeNotification.completed_at`` (the
    envelope timestamp of the terminal event — what the card stamps as
    HH:MM); ``by`` is ``cancelled_by`` for a cancel and ``None`` for
    complete/failed.
    """

    terminal_state: str  # "build_cancelled" | "build_complete" | "build_failed"
    at: datetime
    by: str | None
    recorded_at_mono: float


class TerminalBuildRegistry:
    """Bounded TTL map ``build_id -> TerminalBuildRecord``.

    In-process, in-memory only (DDR-027) — see the module docstring for
    the write/read seam and the empty-after-restart degrade. Not
    thread-safe and needs no lock: both the writer (sink ``notify()``)
    and the reader (reply handler) run on the one supervisor event loop,
    and neither ``record`` nor ``get`` awaits.
    """

    __slots__ = ("_entries", "_max_entries", "_ttl_seconds")

    def __init__(
        self,
        *,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        # Insertion-ordered by recording time (record() re-inserts on
        # overwrite), so eviction pops the eldest recording first.
        self._entries: dict[str, TerminalBuildRecord] = {}

    def record(
        self,
        build_id: str,
        *,
        terminal_state: str,
        at: datetime,
        by: str | None = None,
    ) -> None:
        """Record (or overwrite) the terminal state for ``build_id``.

        A falsy ``build_id`` is ignored — the registry only ever answers
        exact build_id lookups, and terminal payloads without a build_id
        have nothing a card tap could join on.
        """
        if not build_id:
            return
        self._sweep()
        # Re-insert so overwrites move to the back of eviction order.
        self._entries.pop(build_id, None)
        self._entries[build_id] = TerminalBuildRecord(
            terminal_state=terminal_state,
            at=at,
            by=by,
            recorded_at_mono=_monotonic(),
        )
        while len(self._entries) > self._max_entries:
            del self._entries[next(iter(self._entries))]

    def get(self, build_id: str) -> TerminalBuildRecord | None:
        """The live terminal record for ``build_id``, or ``None``.

        Expired entries are swept first, so a hit is always within TTL.
        A miss means "not known terminal" — which, post-restart or
        post-expiry, is exactly the honest degrade to today's behaviour.
        """
        self._sweep()
        return self._entries.get(build_id)

    def _sweep(self) -> None:
        """Evict expired entries (monotonic clock, evict-on-touch)."""
        now_mono = _monotonic()
        expired = [
            build_id
            for build_id, rec in self._entries.items()
            if (now_mono - rec.recorded_at_mono) >= self._ttl_seconds
        ]
        for build_id in expired:
            del self._entries[build_id]


__all__ = [
    "TerminalBuildRecord",
    "TerminalBuildRegistry",
    "render_local_hhmm",
]
