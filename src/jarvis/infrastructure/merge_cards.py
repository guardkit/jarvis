"""Where each merge card with a preview was posted, and what it last showed.

The previews design of 16 October 2026 (preview expiry, Rebuild, preview slots).

Forge describes every merge card that has a review preview from its own
ledger, at once on each change and again on every five-minute preview sweep.
Jarvis keeps the Slack message true to that description. To do that across a
restart it has to remember, for each card:

* which Slack message it is (channel and message id), keyed by the offer's
  request id — or that it has no message right now (never posted, the post
  failed, or Slack says the message is gone);
* who the card belongs to (the real build id and the correlation id it was
  first posted with, and the candidate commit), so an update for a different
  offer can never land on it;
* the highest revision of Forge's description it has accepted, so a late,
  older description is ignored;
* a fingerprint of what the message last showed SUCCESSFULLY. Jarvis edits
  the message only when a new drawing differs from it, and records a new one
  only after Slack confirms the edit, so a failed edit is simply tried again
  on the next description. Jarvis's own click messages ("Recording approve…",
  "Rebuilding…") are recorded here too, so Forge's next description replaces
  them whenever the truth differs.

All of that is kept in one small JSON file, written atomically (a temporary
file in the same directory, flushed, then renamed over the real one — the
heartbeat file's pattern). In the estate the file sits in the bus gateway's
own ``gateway-state`` volume. With no path configured the store is kept in
memory only, which is what tests and processes without the volume use.

The click latch (the "already clicked" mark that stops a double tap being
sent twice) for these cards lives here as well, in memory only, as it always
has. When a click is recorded the card's revision at that moment is noted
with it, and a NEWER description that says the card is still undecided
clears the latch — that is how Reject works after Forge refuses an Approve.

While a click is latched, a description at a revision no newer than the
click is not drawn either: it would put back live buttons whose taps the
latch then drops. Only a newer revision clears the latch and redraws.

THE RECORD OUTLIVES THE MESSAGE. A card's identity and the highest
revision accepted for it are written down the moment a description is
accepted, before anything is posted, and are never forgotten while the card
is remembered at all: a missing Slack message only clears the message
reference. So a late, older description is always recognised as stale — even
after a failed post or a deleted message, and across a restart — and a
decided card (including one Jarvis first hears of already decided) is kept as
a placeholder that is never posted with buttons.

One lock, :attr:`MergeCardStore.lock`, is shared by the Slack reply handler
(it is the handler's click lock) and the notifier's card updates, so an update
for a card waits while a click on it is being sent.

Entries are dropped 24 hours after a decided description, or 15 days after
the card was first posted, whichever comes first.
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig

logger = structlog.get_logger(__name__)

# The file's name when it is placed beside the gateway's heartbeat file.
MERGE_CARD_FILE_NAME = "merge-cards.json"

# How long a decided card is still remembered (Forge stops describing it
# after 24 hours too), and the longest any card is remembered.
DECIDED_KEEP_SECONDS = 24 * 3600.0
MAX_AGE_SECONDS = 15 * 24 * 3600.0

_FILE_VERSION = 1

# Wall clock seam (entries outlive the process, so not the monotonic clock).
# Tests patch this alias.
_wall_now = time.time


def content_digest(blocks: list[dict[str, Any]] | None, text: str) -> str:
    """A short fingerprint of what a Slack message shows."""
    body = json.dumps(
        {"blocks": blocks or [], "text": text},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclasses.dataclass
class MergeCardEntry:
    """One posted merge card. Keyed in the store by ``request_id``."""

    request_id: str
    build_id: str
    correlation_id: str
    candidate_sha: str
    channel: str
    ts: str | None
    revision: int
    displayed: str
    created_at: float
    decided_at: float | None = None

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_json(cls, data: Any) -> MergeCardEntry | None:
        """An entry from its saved form, or None when it does not read."""
        if not isinstance(data, dict):
            return None
        try:
            entry = cls(
                request_id=str(data["request_id"]),
                build_id=str(data["build_id"]),
                correlation_id=str(data["correlation_id"]),
                candidate_sha=str(data["candidate_sha"]),
                channel=str(data.get("channel") or ""),
                ts=(str(data["ts"]) if data.get("ts") else None),
                revision=int(data["revision"]),
                displayed=str(data["displayed"]),
                created_at=float(data["created_at"]),
                decided_at=(None if data.get("decided_at") is None else float(data["decided_at"])),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if not entry.request_id:
            return None
        return entry


class MergeCardStore:
    """The durable record of posted merge cards, plus their click latch.

    Never raises from any method: a file that cannot be read starts the store
    empty (Forge's sweep then posts replacement cards), and a file that
    cannot be written is logged — the in-memory record still serves this
    process.
    """

    __slots__ = ("_entries", "_latches", "_path", "lock")

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._entries: dict[str, MergeCardEntry] = {}
        # request_id -> the card's revision when the click was recorded.
        self._latches: dict[str, int] = {}
        self.lock = asyncio.Lock()
        self._load()

    @property
    def path(self) -> Path | None:
        """The file this store keeps, or None for memory only."""
        return self._path

    # -- reading ---------------------------------------------------------

    def get(self, request_id: str) -> MergeCardEntry | None:
        """The entry for this offer, or None."""
        return self._entries.get(request_id)

    def knows(self, request_id: str) -> bool:
        """True when this request id is a merge card this store tracks."""
        return request_id in self._entries

    # -- writing ---------------------------------------------------------

    def put(self, entry: MergeCardEntry) -> None:
        """Add or replace an entry and save."""
        self._prune()
        self._entries[entry.request_id] = entry
        self.save()

    def clear_message(self, request_id: str) -> None:
        """The card's Slack message is gone: keep the record, drop the reference."""
        entry = self._entries.get(request_id)
        if entry is not None and entry.ts is not None:
            entry.channel = ""
            entry.ts = None
            entry.displayed = ""
            self.save()

    def set_message(self, request_id: str, channel: str, ts: str, digest: str) -> None:
        """The card was posted: note its message and what it shows."""
        entry = self._entries.get(request_id)
        if entry is None:
            return
        entry.channel = channel
        entry.ts = ts
        entry.displayed = digest
        self.save()

    def record_displayed(self, request_id: str, ts: str | None, digest: str) -> None:
        """Note what the card's message now shows, after Slack confirmed it.

        Only for the tracked message: a click on some other copy of the card
        says nothing about what the tracked message shows.
        """
        entry = self._entries.get(request_id)
        if entry is None or entry.ts is None or (ts is not None and entry.ts != ts):
            return
        if entry.displayed != digest:
            entry.displayed = digest
            self.save()

    # -- the click latch -------------------------------------------------

    def is_latched(self, request_id: str) -> bool:
        """True while a click on this card has been recorded."""
        return request_id in self._latches

    def latched_revision(self, request_id: str) -> int | None:
        """The card's revision when its click was recorded, or None."""
        return self._latches.get(request_id)

    def latch(self, request_id: str) -> None:
        """Record a click, noting the card's revision at this moment."""
        entry = self._entries.get(request_id)
        self._latches[request_id] = entry.revision if entry is not None else -1

    def unlatch(self, request_id: str) -> None:
        """Forget a click that was never sent."""
        self._latches.pop(request_id, None)

    def clear_latch_if_newer(self, request_id: str, revision: int) -> bool:
        """Clear the latch when an undecided description is newer than the click.

        A description made before the click (revision not newer) never
        clears it. Callers hold :attr:`lock`.
        """
        noted = self._latches.get(request_id)
        if noted is None or revision <= noted:
            return False
        del self._latches[request_id]
        return True

    # -- the file --------------------------------------------------------

    def _prune(self) -> None:
        now = _wall_now()
        stale = [
            request_id
            for request_id, entry in self._entries.items()
            if now - entry.created_at >= MAX_AGE_SECONDS
            or (entry.decided_at is not None and now - entry.decided_at >= DECIDED_KEEP_SECONDS)
        ]
        for request_id in stale:
            del self._entries[request_id]
            self._latches.pop(request_id, None)

    def prune(self) -> None:
        """Drop expired entries, saving when anything was dropped."""
        before = len(self._entries)
        self._prune()
        if len(self._entries) != before:
            self.save()

    def _load(self) -> None:
        if self._path is None:
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as exc:
            logger.warning(
                "merge_card_store_read_failed",
                path=str(self._path),
                error_class=type(exc).__name__,
                error=str(exc),
            )
            return
        try:
            document = json.loads(raw)
            cards = document.get("cards") if isinstance(document, dict) else None
            if not isinstance(cards, dict):
                raise ValueError("no 'cards' mapping")
        except (ValueError, AttributeError) as exc:
            logger.warning(
                "merge_card_store_unreadable",
                path=str(self._path),
                error_class=type(exc).__name__,
                detail=(
                    "the merge card file did not read; Jarvis starts with no record "
                    "of posted cards and posts replacements as Forge describes them"
                ),
            )
            return
        for request_id, data in cards.items():
            entry = MergeCardEntry.from_json(data)
            if entry is not None and entry.request_id == request_id:
                self._entries[request_id] = entry
        self._prune()

    def save(self) -> None:
        """Write the file atomically. Never raises."""
        if self._path is None:
            return
        document = {
            "version": _FILE_VERSION,
            "cards": {rid: entry.to_json() for rid, entry in sorted(self._entries.items())},
        }
        body = json.dumps(document, indent=2, sort_keys=True) + "\n"
        tmp_path: str | None = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            handle_fd, tmp_path = tempfile.mkstemp(
                dir=str(self._path.parent),
                prefix=f".{self._path.name}.",
                suffix=".tmp",
            )
            with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self._path)
            tmp_path = None
        except OSError as exc:
            logger.warning(
                "merge_card_store_write_failed",
                path=str(self._path),
                error_class=type(exc).__name__,
                error=str(exc),
                detail=(
                    "the merge card file could not be written; this process still "
                    "remembers its cards, but after a restart Jarvis posts replacements"
                ),
            )
        finally:
            if tmp_path is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp_path)


def resolve_merge_card_path(config: JarvisConfig) -> Path | None:
    """Where the merge card file goes, or None for memory only.

    ``JARVIS_SLACK_MERGE_CARD_PATH`` when set. Otherwise, when the process
    writes a Slack heartbeat file (only the estate's bus gateway does), the
    file goes beside it, in the gateway's own state volume. Otherwise None.
    """
    explicit = getattr(config, "slack_merge_card_path", None)
    if explicit is not None and str(explicit).strip():
        return Path(str(explicit).strip())
    heartbeat = getattr(config, "slack_heartbeat_path", None)
    if heartbeat is not None and str(heartbeat).strip():
        return Path(str(heartbeat).strip()).parent / MERGE_CARD_FILE_NAME
    return None


__all__ = [
    "DECIDED_KEEP_SECONDS",
    "MAX_AGE_SECONDS",
    "MERGE_CARD_FILE_NAME",
    "MergeCardEntry",
    "MergeCardStore",
    "content_digest",
    "resolve_merge_card_path",
]
