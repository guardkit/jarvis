"""The Linear door's own small record (design section 1, "Never sending anything twice").

One SQLite file in the door's own volume, one writer (the door). Tables:

``sends``
    One row per send (a single issue or a mission attempt): the correlation id,
    the kind, the mission label id and title for a mission, the attempt number,
    the subject and the **frozen bytes** that are published (written before the
    first publish and never rebuilt), and the state ``pending`` → ``published``
    → ``commented`` → ``moved``.
``send_issues``
    The issues a send covers, each with its mission key, a hash of the title
    and description as sent, and whether its "sent" comment, its move to In
    Progress and its edits-after-sending comment are done.
``reservations``
    Each Linear issue (by its UUID) in an open attempt, with that attempt's
    correlation id: at most one open attempt per issue (design review round 2,
    R9). Written in the same transaction as the pending send; deleted only when
    the attempt ends.
``ended_attempts``
    Attempts that have ended (Forge's record said so, or an operator released
    one). An ended send is never published, commented or moved again.
``known_attempts``
    Correlation ids learned when a new or lost record is rebuilt from Forge's
    record and the PIPELINE stream, so attempt numbers continue after the
    highest one found.
``notices``
    Comments the door has already written about an issue that was not sent, so
    each is written once.

Stage 4 (factory → Linear) adds, at ``user_version`` 2:

``progress``
    What the door last wrote about an open attempt, per issue and topic (the
    phase it last commented, each mission key's last reported attempt, the
    final comment and move), so each change is commented once, across
    restarts.
``card_comments``
    Each card posted on an issue: the card's request id, the comment's id,
    whether it can be answered from Linear (and the subject and correlation id
    the answer goes to, and the assumption ids an approve accepts), and
    whether it is open, answered or closed.
``replies``
    Replies under card comments that the door has handled (or written itself),
    so an answer is never published twice.
``marks``
    The time of the last bus message handled on each feed (cards,
    notifications), where the subscription restarts.
``recoveries``
    After a rebuild, the issues of attempts that had already ended, to be
    brought to their final state once (one row per issue: its latest attempt).

Stage 4 repair (Codex review R2-R4), at ``user_version`` 3:

``comment_refs``
    Each comment the door means to write about the factory's work, by a short
    stable reference that also ends the comment's text. Written before the
    comment is sent, so a comment whose sending was not confirmed (a lost
    response, a crash) is looked for by its reference before it is written
    again, and is never written twice.
``held_messages``
    Card and notification messages for sends whose "sent" comment or move is
    not done yet, kept here until the send is finished.
``answer_claims``
    Each answer from Linear, claimed before it is published, with a
    ``published`` flag set only after the publish returns (Codex review R8).
    A claim left unpublished (the publish raised, or the door stopped part
    way) is never published again; it is settled once, by telling the person
    under the card and taking a new reply if Forge still shows the card open.

Linear projects (design section 11), at ``user_version`` 4:

``project_intents``
    One row per registered repository the door set out to create a Linear
    project for: the two UUID v4 ids it chose (the project's and its GitHub
    link's), generated once and written **before** the first write to Linear,
    whether the project has been seen created, and whether the whole intent is
    complete. A completed repository is never created again.

``comment_refs`` also holds each project update's reference (its
``issue_id`` column then holds the project's id).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 4

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sends (
    correlation_id   TEXT PRIMARY KEY,
    kind             TEXT NOT NULL CHECK (kind IN ('single', 'mission')),
    mission_label_id TEXT,
    mission_title    TEXT,
    attempt          INTEGER NOT NULL CHECK (attempt >= 1),
    subject          TEXT NOT NULL,
    payload          BLOB NOT NULL,
    status           TEXT NOT NULL
                     CHECK (status IN ('pending', 'published', 'commented', 'moved')),
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sends_by_mission ON sends (mission_label_id);
CREATE TABLE IF NOT EXISTS send_issues (
    correlation_id TEXT NOT NULL REFERENCES sends (correlation_id),
    issue_id       TEXT NOT NULL,
    identifier     TEXT NOT NULL,
    feature_key    TEXT,
    content_hash   TEXT NOT NULL,
    commented      INTEGER NOT NULL DEFAULT 0,
    moved          INTEGER NOT NULL DEFAULT 0,
    edit_noted     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (correlation_id, issue_id)
);
CREATE INDEX IF NOT EXISTS send_issues_by_issue ON send_issues (issue_id);
CREATE TABLE IF NOT EXISTS reservations (
    issue_id       TEXT PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    identifier     TEXT,
    reserved_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ended_attempts (
    correlation_id TEXT PRIMARY KEY,
    reason         TEXT NOT NULL,
    ended_at       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS known_attempts (
    correlation_id TEXT PRIMARY KEY,
    learned_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notices (
    issue_id    TEXT NOT NULL,
    notice_hash TEXT NOT NULL,
    posted_at   TEXT NOT NULL,
    PRIMARY KEY (issue_id, notice_hash)
);
CREATE TABLE IF NOT EXISTS progress (
    correlation_id TEXT NOT NULL,
    issue_id       TEXT NOT NULL,
    topic          TEXT NOT NULL,
    value          TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    PRIMARY KEY (correlation_id, issue_id, topic)
);
CREATE TABLE IF NOT EXISTS card_comments (
    request_id       TEXT NOT NULL,
    issue_id         TEXT NOT NULL,
    comment_id       TEXT NOT NULL,
    correlation_id   TEXT NOT NULL,
    kind             TEXT NOT NULL,
    answerable       INTEGER NOT NULL,
    approval_subject TEXT,
    reply_correlation_id TEXT,
    assumption_ids   TEXT NOT NULL DEFAULT '[]',
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open', 'answered', 'closed')),
    posted_at        TEXT NOT NULL,
    PRIMARY KEY (request_id, issue_id)
);
CREATE INDEX IF NOT EXISTS card_comments_by_comment ON card_comments (comment_id);
CREATE TABLE IF NOT EXISTS replies (
    comment_id TEXT PRIMARY KEY,
    request_id TEXT,
    outcome    TEXT NOT NULL,
    handled_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS marks (
    name  TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recoveries (
    correlation_id TEXT NOT NULL,
    issue_id       TEXT NOT NULL,
    identifier     TEXT,
    target         TEXT NOT NULL CHECK (target IN ('done', 'backlog')),
    text           TEXT NOT NULL,
    done           INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (correlation_id, issue_id)
);
CREATE TABLE IF NOT EXISTS comment_refs (
    ref        TEXT PRIMARY KEY,
    issue_id   TEXT NOT NULL,
    comment_id TEXT,
    started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS answer_claims (
    reply_id       TEXT PRIMARY KEY,
    request_id     TEXT NOT NULL,
    issue_id       TEXT NOT NULL,
    comment_id     TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    kind           TEXT NOT NULL,
    published      INTEGER NOT NULL DEFAULT 0,
    settled        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS project_intents (
    repo            TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    link_id         TEXT NOT NULL,
    project_created INTEGER NOT NULL DEFAULT 0,
    complete        INTEGER NOT NULL DEFAULT 0,
    note            TEXT,
    started_at      TEXT NOT NULL,
    completed_at    TEXT
);
CREATE TABLE IF NOT EXISTS held_messages (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    feed    TEXT NOT NULL,
    subject TEXT NOT NULL,
    data    BLOB NOT NULL,
    at      TEXT
);
"""

STATUSES = ("pending", "published", "commented", "moved")


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class SendIssue:
    issue_id: str
    identifier: str
    feature_key: str | None
    content_hash: str
    commented: bool = False
    moved: bool = False
    edit_noted: bool = False


@dataclass(frozen=True)
class Send:
    correlation_id: str
    kind: str
    mission_label_id: str | None
    mission_title: str | None
    attempt: int
    subject: str
    payload: bytes
    status: str
    created_at: str
    issues: tuple[SendIssue, ...]


class IssueAlreadyReserved(Exception):
    """An issue is already in another open attempt; nothing was written."""


class DoorStore:
    """The door's record. Synchronous and small; every write commits at once."""

    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # A short wait for the lock: the release command may write while the
        # door runs.
        self._db = sqlite3.connect(str(path), timeout=10.0)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        with self._db:
            self._db.executescript(_SCHEMA)
            version = self._db.execute("PRAGMA user_version").fetchone()[0]
            if version < SCHEMA_VERSION:
                self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def close(self) -> None:
        self._db.close()

    # -- sends ---------------------------------------------------------------

    def record_send(
        self,
        *,
        correlation_id: str,
        kind: str,
        attempt: int,
        subject: str,
        payload: bytes,
        issues: list[SendIssue],
        mission_label_id: str | None = None,
        mission_title: str | None = None,
    ) -> Send:
        """Write a send as ``pending``, with its frozen bytes, and reserve its
        issues, in one transaction.

        Raises:
            IssueAlreadyReserved: an issue is in another open attempt; nothing
                is written.
        """
        now = _now()
        with self._db:
            for issue in issues:
                row = self._db.execute(
                    "SELECT correlation_id FROM reservations WHERE issue_id = ?",
                    (issue.issue_id,),
                ).fetchone()
                if row is not None and row[0] != correlation_id:
                    raise IssueAlreadyReserved(f"{issue.identifier} is in {row[0]}")
            self._db.executemany(
                "INSERT OR REPLACE INTO reservations "
                "(issue_id, correlation_id, identifier, reserved_at) VALUES (?, ?, ?, ?)",
                [(i.issue_id, correlation_id, i.identifier, now) for i in issues],
            )
            self._db.execute(
                "INSERT INTO sends (correlation_id, kind, mission_label_id, mission_title, "
                "attempt, subject, payload, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (
                    correlation_id,
                    kind,
                    mission_label_id,
                    mission_title,
                    attempt,
                    subject,
                    payload,
                    now,
                    now,
                ),
            )
            self._db.executemany(
                "INSERT INTO send_issues (correlation_id, issue_id, identifier, feature_key, "
                "content_hash) VALUES (?, ?, ?, ?, ?)",
                [
                    (correlation_id, i.issue_id, i.identifier, i.feature_key, i.content_hash)
                    for i in issues
                ],
            )
        send = self.get_send(correlation_id)
        assert send is not None
        return send

    def get_send(self, correlation_id: str) -> Send | None:
        row = self._db.execute(
            "SELECT * FROM sends WHERE correlation_id = ?", (correlation_id,)
        ).fetchone()
        return self._send_from_row(row) if row is not None else None

    def _send_from_row(self, row: sqlite3.Row) -> Send:
        issues = tuple(
            SendIssue(
                issue_id=r["issue_id"],
                identifier=r["identifier"],
                feature_key=r["feature_key"],
                content_hash=r["content_hash"],
                commented=bool(r["commented"]),
                moved=bool(r["moved"]),
                edit_noted=bool(r["edit_noted"]),
            )
            for r in self._db.execute(
                "SELECT * FROM send_issues WHERE correlation_id = ? ORDER BY rowid",
                (row["correlation_id"],),
            )
        )
        return Send(
            correlation_id=row["correlation_id"],
            kind=row["kind"],
            mission_label_id=row["mission_label_id"],
            mission_title=row["mission_title"],
            attempt=row["attempt"],
            subject=row["subject"],
            payload=bytes(row["payload"]),
            status=row["status"],
            created_at=row["created_at"],
            issues=issues,
        )

    def set_status(self, correlation_id: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(status)
        with self._db:
            self._db.execute(
                "UPDATE sends SET status = ?, updated_at = ? WHERE correlation_id = ?",
                (status, _now(), correlation_id),
            )

    def mark_issue(self, correlation_id: str, issue_id: str, step: str) -> None:
        """Mark ``commented``, ``moved`` or ``edit_noted`` done for one issue of a send."""
        if step not in ("commented", "moved", "edit_noted"):
            raise ValueError(step)
        with self._db:
            self._db.execute(
                f"UPDATE send_issues SET {step} = 1 WHERE correlation_id = ? AND issue_id = ?",
                (correlation_id, issue_id),
            )

    def unfinished_sends(self) -> list[Send]:
        rows = self._db.execute(
            "SELECT * FROM sends WHERE status != 'moved' AND correlation_id NOT IN "
            "(SELECT correlation_id FROM ended_attempts) ORDER BY created_at, rowid"
        ).fetchall()
        return [self._send_from_row(row) for row in rows]

    def issue_ids_in_unfinished_sends(self) -> set[str]:
        return {
            row[0]
            for row in self._db.execute(
                "SELECT si.issue_id FROM send_issues si JOIN sends s USING (correlation_id) "
                "WHERE s.status != 'moved' AND s.correlation_id NOT IN "
                "(SELECT correlation_id FROM ended_attempts)"
            )
        }

    def max_attempt(self, prefix: str) -> int:
        """The highest attempt number among ids ``<prefix><n>`` the record knows:
        its sends, its reservations and the attempts learned in a rebuild."""
        best = 0
        for (cid,) in self._db.execute(
            "SELECT correlation_id FROM sends WHERE substr(correlation_id, 1, ?) = ? "
            "UNION SELECT correlation_id FROM reservations WHERE substr(correlation_id, 1, ?) = ? "
            "UNION SELECT correlation_id FROM known_attempts "
            "WHERE substr(correlation_id, 1, ?) = ?",
            (len(prefix), prefix) * 3,
        ):
            rest = cid[len(prefix) :]
            if rest.isdigit():
                best = max(best, int(rest))
        return best

    def sends_to_watch_for_edits(self, since: str) -> list[tuple[Send, SendIssue]]:
        """The latest fully sent attempt of each issue, sent after ``since`` (ISO
        time), still open and still holding the issue, whose edits-after-sending
        comment is not written yet. Once an attempt has ended (or been
        released) an edit is the next attempt's business, not this one's."""
        rows = self._db.execute(
            "SELECT s.correlation_id, si.issue_id FROM send_issues si "
            "JOIN sends s USING (correlation_id) "
            "WHERE s.status = 'moved' AND si.edit_noted = 0 AND s.created_at >= ? "
            "AND s.correlation_id NOT IN (SELECT correlation_id FROM ended_attempts) "
            "AND EXISTS (SELECT 1 FROM reservations r "
            "  WHERE r.issue_id = si.issue_id AND r.correlation_id = s.correlation_id) "
            "AND s.created_at = (SELECT max(s2.created_at) FROM sends s2 "
            "  JOIN send_issues si2 USING (correlation_id) WHERE si2.issue_id = si.issue_id)",
            (since,),
        ).fetchall()
        watched: list[tuple[Send, SendIssue]] = []
        for cid, issue_id in rows:
            send = self.get_send(cid)
            if send is None:
                continue
            for issue in send.issues:
                if issue.issue_id == issue_id:
                    watched.append((send, issue))
        return watched

    def is_empty(self) -> bool:
        """Nothing sent, reserved or learned: a new or lost record."""
        return all(
            self._db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is None
            for table in ("sends", "reservations", "known_attempts")
        )

    def apply_rebuild(
        self,
        *,
        known: list[str],
        reservations: list[tuple[str, str, str]],
        recoveries: list[Recovery] | None = None,
    ) -> None:
        """Write a rebuild in one transaction: every attempt found (for the
        numbering), ``(issue id, correlation id, identifier)`` for each
        issue an open attempt holds, and the issues of ended attempts to bring
        to their final state once."""
        now = _now()
        with self._db:
            self._db.executemany(
                "INSERT OR IGNORE INTO recoveries "
                "(correlation_id, issue_id, identifier, target, text) VALUES (?, ?, ?, ?, ?)",
                [
                    (r.correlation_id, r.issue_id, r.identifier, r.target, r.text)
                    for r in recoveries or []
                ],
            )
            self._db.executemany(
                "INSERT OR IGNORE INTO known_attempts (correlation_id, learned_at) VALUES (?, ?)",
                [(cid, now) for cid in known],
            )
            self._db.executemany(
                "INSERT OR IGNORE INTO reservations "
                "(issue_id, correlation_id, identifier, reserved_at) VALUES (?, ?, ?, ?)",
                [(issue_id, cid, identifier, now) for issue_id, cid, identifier in reservations],
            )

    # -- reservations --------------------------------------------------------

    def reservations(self) -> dict[str, str]:
        """Issue id → the correlation id of the open attempt it is in."""
        return {
            row[0]: row[1]
            for row in self._db.execute("SELECT issue_id, correlation_id FROM reservations")
        }

    def reserved_issues(self, correlation_id: str) -> list[tuple[str, str | None]]:
        """``(issue id, identifier)`` of each issue an open attempt holds."""
        return [
            (row[0], row[1])
            for row in self._db.execute(
                "SELECT issue_id, identifier FROM reservations WHERE correlation_id = ? "
                "ORDER BY rowid",
                (correlation_id,),
            )
        ]

    def attempt_holding(self, identifier: str) -> str | None:
        """The open attempt holding the issue with this identifier (any case)."""
        row = self._db.execute(
            "SELECT correlation_id FROM reservations WHERE upper(identifier) = upper(?)",
            (identifier,),
        ).fetchone()
        return row[0] if row else None

    def end_attempt(self, correlation_id: str, reason: str) -> None:
        """The attempt has ended: free its issues, never deliver it again, and
        stop reading answers under its cards."""
        with self._db:
            self._db.execute(
                "UPDATE card_comments SET status = 'closed' "
                "WHERE correlation_id = ? AND status = 'open'",
                (correlation_id,),
            )
            self._db.execute(
                "INSERT OR IGNORE INTO ended_attempts (correlation_id, reason, ended_at) "
                "VALUES (?, ?, ?)",
                (correlation_id, reason, _now()),
            )
            self._db.execute("DELETE FROM reservations WHERE correlation_id = ?", (correlation_id,))

    # -- notices -------------------------------------------------------------

    @staticmethod
    def _notice_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def notice_posted(self, issue_id: str, text: str) -> bool:
        return (
            self._db.execute(
                "SELECT 1 FROM notices WHERE issue_id = ? AND notice_hash = ?",
                (issue_id, self._notice_hash(text)),
            ).fetchone()
            is not None
        )

    def record_notice(self, issue_id: str, text: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO notices (issue_id, notice_hash, posted_at) VALUES (?, ?, ?)",
                (issue_id, self._notice_hash(text), _now()),
            )

    def clear_notices(self, issue_ids: list[str]) -> None:
        """Forget the not-sent comments of issues that have now been sent."""
        with self._db:
            self._db.executemany(
                "DELETE FROM notices WHERE issue_id = ?", [(i,) for i in issue_ids]
            )

    def open_attempts(self) -> list[str]:
        """The correlation ids of every open attempt (those holding issues)."""
        return [
            row[0]
            for row in self._db.execute(
                "SELECT DISTINCT correlation_id FROM reservations ORDER BY correlation_id"
            )
        ]

    def reserved_at(self, correlation_id: str) -> str | None:
        row = self._db.execute(
            "SELECT min(reserved_at) FROM reservations WHERE correlation_id = ?",
            (correlation_id,),
        ).fetchone()
        return row[0] if row else None

    # -- progress (stage 4) --------------------------------------------------

    def progress(self, correlation_id: str, issue_id: str, topic: str) -> str | None:
        row = self._db.execute(
            "SELECT value FROM progress WHERE correlation_id = ? AND issue_id = ? AND topic = ?",
            (correlation_id, issue_id, topic),
        ).fetchone()
        return row[0] if row else None

    def set_progress(self, correlation_id: str, issue_id: str, topic: str, value: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO progress "
                "(correlation_id, issue_id, topic, value, updated_at) VALUES (?, ?, ?, ?, ?)",
                (correlation_id, issue_id, topic, value, _now()),
            )

    # -- card comments (stage 4) ---------------------------------------------

    def card_posted(self, request_id: str, issue_id: str) -> bool:
        return (
            self._db.execute(
                "SELECT 1 FROM card_comments WHERE request_id = ? AND issue_id = ?",
                (request_id, issue_id),
            ).fetchone()
            is not None
        )

    def record_card(self, card: CardComment) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO card_comments (request_id, issue_id, comment_id, "
                "correlation_id, kind, answerable, approval_subject, reply_correlation_id, "
                "assumption_ids, status, posted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    card.request_id,
                    card.issue_id,
                    card.comment_id,
                    card.correlation_id,
                    card.kind,
                    int(card.answerable),
                    card.approval_subject,
                    card.reply_correlation_id,
                    json.dumps(list(card.assumption_ids)),
                    card.status,
                    _now(),
                ),
            )

    @staticmethod
    def _card_from_row(row: sqlite3.Row) -> CardComment:
        return CardComment(
            request_id=row["request_id"],
            issue_id=row["issue_id"],
            comment_id=row["comment_id"],
            correlation_id=row["correlation_id"],
            kind=row["kind"],
            answerable=bool(row["answerable"]),
            approval_subject=row["approval_subject"],
            reply_correlation_id=row["reply_correlation_id"],
            assumption_ids=tuple(json.loads(row["assumption_ids"] or "[]")),
            status=row["status"],
        )

    def open_cards(self, *, answerable_only: bool = False) -> list[CardComment]:
        sql = "SELECT * FROM card_comments WHERE status = 'open'"
        if answerable_only:
            sql += " AND answerable = 1"
        return [self._card_from_row(r) for r in self._db.execute(sql + " ORDER BY rowid")]

    def cards_of(self, correlation_id: str) -> list[CardComment]:
        return [
            self._card_from_row(r)
            for r in self._db.execute(
                "SELECT * FROM card_comments WHERE correlation_id = ? ORDER BY rowid",
                (correlation_id,),
            )
        ]

    def set_card_status(self, request_id: str, status: str) -> None:
        """Answer or close a card on every issue it was posted on."""
        with self._db:
            self._db.execute(
                "UPDATE card_comments SET status = ? WHERE request_id = ? AND status = 'open'",
                (status, request_id),
            )

    # -- replies (stage 4) ---------------------------------------------------

    def reply_handled(self, comment_id: str) -> bool:
        return (
            self._db.execute("SELECT 1 FROM replies WHERE comment_id = ?", (comment_id,)).fetchone()
            is not None
        )

    def record_reply(self, comment_id: str, request_id: str | None, outcome: str) -> None:
        """Record a handled reply that answers nothing."""
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO replies (comment_id, request_id, outcome, handled_at) "
                "VALUES (?, ?, ?, ?)",
                (comment_id, request_id, outcome, _now()),
            )

    def claim_answer(self, reply_id: str, card: CardComment, decision: str) -> None:
        """Before an answer is published: the reply is handled, the claim is
        recorded unpublished and the card is answered, in one transaction."""
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO replies (comment_id, request_id, outcome, handled_at) "
                "VALUES (?, ?, ?, ?)",
                (reply_id, card.request_id, decision, _now()),
            )
            self._db.execute(
                "INSERT OR IGNORE INTO answer_claims (reply_id, request_id, issue_id, "
                "comment_id, correlation_id, kind) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    reply_id,
                    card.request_id,
                    card.issue_id,
                    card.comment_id,
                    card.correlation_id,
                    card.kind,
                ),
            )
            self._db.execute(
                "UPDATE card_comments SET status = 'answered' "
                "WHERE request_id = ? AND status = 'open'",
                (card.request_id,),
            )

    def mark_published(self, reply_id: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE answer_claims SET published = 1 WHERE reply_id = ?", (reply_id,)
            )

    def unpublished_claims(self) -> list[AnswerClaim]:
        """Claims whose publish never returned, not yet settled."""
        return [
            AnswerClaim(
                r["reply_id"],
                r["request_id"],
                r["issue_id"],
                r["comment_id"],
                r["correlation_id"],
                r["kind"],
            )
            for r in self._db.execute(
                "SELECT * FROM answer_claims WHERE published = 0 AND settled = 0 ORDER BY rowid"
            )
        ]

    def settle_claim(self, reply_id: str) -> None:
        with self._db:
            self._db.execute("UPDATE answer_claims SET settled = 1 WHERE reply_id = ?", (reply_id,))

    def reopen_card(self, request_id: str) -> None:
        """After a publish that was not confirmed: the reply stays handled (it
        is never published again), but a new reply may answer the card."""
        with self._db:
            self._db.execute(
                "UPDATE card_comments SET status = 'open' "
                "WHERE request_id = ? AND status = 'answered'",
                (request_id,),
            )

    # -- marks (stage 4) -----------------------------------------------------

    def mark(self, name: str) -> str | None:
        row = self._db.execute("SELECT value FROM marks WHERE name = ?", (name,)).fetchone()
        return row[0] if row else None

    def set_mark(self, name: str, value: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO marks (name, value) VALUES (?, ?)", (name, value)
            )

    # -- recoveries (stage 4) ------------------------------------------------

    def pending_recoveries(self) -> list[Recovery]:
        return [
            Recovery(r["correlation_id"], r["issue_id"], r["identifier"], r["target"], r["text"])
            for r in self._db.execute("SELECT * FROM recoveries WHERE done = 0 ORDER BY rowid")
        ]

    def finish_recovery(self, correlation_id: str, issue_id: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE recoveries SET done = 1 WHERE correlation_id = ? AND issue_id = ?",
                (correlation_id, issue_id),
            )

    # -- comments written once (stage 4 repair, R3) --------------------------

    def comment_ref(self, ref: str) -> tuple[bool, str | None]:
        """``(started, comment id)`` for a comment reference."""
        row = self._db.execute(
            "SELECT comment_id FROM comment_refs WHERE ref = ?", (ref,)
        ).fetchone()
        return (row is not None, row[0] if row is not None else None)

    def begin_comment(self, ref: str, issue_id: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO comment_refs (ref, issue_id, started_at) VALUES (?, ?, ?)",
                (ref, issue_id, _now()),
            )

    def finish_comment(self, ref: str, comment_id: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE comment_refs SET comment_id = ? WHERE ref = ?", (comment_id, ref)
            )

    # -- held bus messages (stage 4 repair, R4) ------------------------------

    def hold_message(self, feed: str, subject: str, data: bytes, at: str | None) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO held_messages (feed, subject, data, at) VALUES (?, ?, ?, ?)",
                (feed, subject, data, at),
            )

    def held_messages(self, feed: str) -> list[tuple[int, str, bytes, str | None]]:
        """``(id, subject, data, time)`` of each message held for ``feed``, oldest first."""
        return [
            (int(r[0]), str(r[1]), bytes(r[2]), r[3])
            for r in self._db.execute(
                "SELECT id, subject, data, at FROM held_messages WHERE feed = ? ORDER BY id",
                (feed,),
            )
        ]

    def release_message(self, held_id: int) -> None:
        with self._db:
            self._db.execute("DELETE FROM held_messages WHERE id = ?", (held_id,))

    # -- project creation intents (section 11.1) -----------------------------

    def project_intent(self, repo: str) -> ProjectIntent | None:
        row = self._db.execute("SELECT * FROM project_intents WHERE repo = ?", (repo,)).fetchone()
        if row is None:
            return None
        return ProjectIntent(
            repo=row["repo"],
            project_id=row["project_id"],
            link_id=row["link_id"],
            project_created=bool(row["project_created"]),
            complete=bool(row["complete"]),
            note=row["note"],
        )

    def begin_project_intent(self, repo: str, project_id: str, link_id: str) -> ProjectIntent:
        """Record the intent and its ids before anything is written to Linear.
        An intent already recorded is kept as it is (its ids never change)."""
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO project_intents (repo, project_id, link_id, started_at) "
                "VALUES (?, ?, ?, ?)",
                (repo, project_id, link_id, _now()),
            )
        intent = self.project_intent(repo)
        assert intent is not None
        return intent

    def mark_project_created(self, repo: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE project_intents SET project_created = 1 WHERE repo = ?", (repo,)
            )

    def complete_project_intent(self, repo: str, note: str) -> None:
        with self._db:
            self._db.execute(
                "UPDATE project_intents SET complete = 1, note = ?, completed_at = ? "
                "WHERE repo = ? AND complete = 0",
                (note, _now(), repo),
            )


@dataclass(frozen=True)
class ProjectIntent:
    """The door's intent to create one repository's Linear project (section 11.1)."""

    repo: str  # the repository's name, case folded
    project_id: str
    link_id: str
    project_created: bool = False
    complete: bool = False
    note: str | None = None


@dataclass(frozen=True)
class CardComment:
    """A card posted as a comment on one issue."""

    request_id: str
    issue_id: str
    comment_id: str
    correlation_id: str  # the door's attempt
    kind: str  # plan | mission_plan | merge | other
    answerable: bool
    approval_subject: str | None = None
    reply_correlation_id: str | None = None
    assumption_ids: tuple[str, ...] = ()
    status: str = "open"


@dataclass(frozen=True)
class AnswerClaim:
    """An answer from Linear claimed before it was published."""

    reply_id: str
    request_id: str
    issue_id: str
    comment_id: str  # the card comment it replied under
    correlation_id: str
    kind: str


@dataclass(frozen=True)
class Recovery:
    """An issue of an attempt that had ended before a rebuild."""

    correlation_id: str
    issue_id: str
    identifier: str | None
    target: str  # done | backlog
    text: str


__all__ = [
    "STATUSES",
    "AnswerClaim",
    "CardComment",
    "DoorStore",
    "IssueAlreadyReserved",
    "ProjectIntent",
    "Recovery",
    "Send",
    "SendIssue",
]
