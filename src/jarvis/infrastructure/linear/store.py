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

Stage 4 adds its own tables (card comments, progress steps, the last card time)
beside these and raises ``user_version``.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1

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

    def latest_send(self, prefix: str) -> Send | None:
        """The send ``<prefix><n>`` with the highest ``n``, if any."""
        attempt = self.max_attempt(prefix)
        return self.get_send(f"{prefix}{attempt}") if attempt else None

    def sends_to_watch_for_edits(self, since: str) -> list[tuple[Send, SendIssue]]:
        """The latest fully sent attempt of each issue, sent after ``since`` (ISO
        time), whose edits-after-sending comment is not written yet."""
        rows = self._db.execute(
            "SELECT s.correlation_id, si.issue_id FROM send_issues si "
            "JOIN sends s USING (correlation_id) "
            "WHERE s.status = 'moved' AND si.edit_noted = 0 AND s.created_at >= ? "
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

    def apply_rebuild(self, *, known: list[str], reservations: list[tuple[str, str, str]]) -> None:
        """Write a rebuild in one transaction: every attempt found (for the
        numbering) and ``(issue id, correlation id, identifier)`` for each
        issue an open attempt holds."""
        now = _now()
        with self._db:
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

    def reserve(self, issue_id: str, correlation_id: str, identifier: str | None = None) -> None:
        """Reserve one issue for an open attempt found in a rebuild."""
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO reservations "
                "(issue_id, correlation_id, identifier, reserved_at) VALUES (?, ?, ?, ?)",
                (issue_id, correlation_id, identifier, _now()),
            )

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
        """The attempt has ended: free its issues, and never deliver it again."""
        with self._db:
            self._db.execute(
                "INSERT OR IGNORE INTO ended_attempts (correlation_id, reason, ended_at) "
                "VALUES (?, ?, ?)",
                (correlation_id, reason, _now()),
            )
            self._db.execute("DELETE FROM reservations WHERE correlation_id = ?", (correlation_id,))

    def is_ended(self, correlation_id: str) -> bool:
        return (
            self._db.execute(
                "SELECT 1 FROM ended_attempts WHERE correlation_id = ?", (correlation_id,)
            ).fetchone()
            is not None
        )

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


__all__ = ["STATUSES", "DoorStore", "IssueAlreadyReserved", "Send", "SendIssue"]
