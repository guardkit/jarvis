"""Read Forge's own record, read-only, for the Linear front door.

The Linear door learns what happened to the work it sent by reading Forge's
SQLite record (design ``linear-front-door-2026-10-18.md``, section 2, "Where
the door learns what happened"), the way the factory dashboard reads it: the
file is opened with ``mode=ro`` and nothing here can write to it. Jarvis does
not import Forge; every table, column and constant this module relies on is
copied here and checked against Forge's source. ALL the SQL the door runs
against Forge's record lives in this one module.

What it answers:

* :meth:`ForgeRecord.outcome_for_single` - where one single-issue attempt
  (``lin-<identifier>-<n>``) has got to, and whether the attempt has ended;
* :meth:`ForgeRecord.outcome_for_mission` - the same for a mission
  (``lin-m-<label id>-<n>``), with which keys landed;
* :meth:`ForgeRecord.open_cards_for` - the cards still open for some
  attempts (merge offers without a decision, paused planning runs, proposed
  missions), so a card the message stream no longer holds can be posted;
* :meth:`ForgeRecord.all_linear_attempts` - every attempt Forge has recorded
  for the door, ended or not, for rebuilding the door's own record.

Any failure to read (a missing file, a locked database, a schema that is not
the one checked here) raises :class:`ForgeRecordUnavailable`; the caller
reads nothing that poll.

Publication still under way versus stopped (Codex design review note R14).
Forge's record says "publication pending" in both cases. What tells them
apart is the merge report row: while the approved merge is still running
there is no report after the decision; when the press finished without
sending, its report says ``publication-pending`` (status GATED, or PASSED
when publication is switched off) and Forge leaves the build open for "the
next merge word, or the plain command" (``merge_executor.py`` 3874-3879).
Forge's own queue calls that ``NOT_PUBLISHED`` and treats it as work that
"will not land without someone acting" (``work_queue_loop.py`` 731-734,
793-794). This module reports the first as ``publication_in_flight`` and the
second as ``publication_stopped`` with the report's reason and the action
needed. Neither ends the attempt.

Checked against Forge commit dbd40c7e (main, 18 October 2026). File and line
of each fact, paths under ``src/forge/``:

Tables and columns (final shape after ``lifecycle/schema.sql`` and
``schema_v2.sql`` ... ``schema_v19.sql``, applied in order by
``lifecycle/migrations.py``; mission tables from ``lifecycle/missions.py``):

* ``builds`` (build_id, feature_id, status, correlation_id, queued_at, error)
  - ``lifecycle/schema.sql`` 15-52; ``target_branch`` - ``schema_v12.sql``
  54; ``mission_id``, ``mission_role`` added by ``missions.ensure_tables`` -
  ``lifecycle/missions.py`` 143-147, 150-168 (only when missing, so they may
  be absent on an older record).
* ``stage_log`` (id, build_id, stage_label, target_identifier, status,
  details_json) - ``lifecycle/schema.sql`` 66-91.
* ``planning_runs`` (correlation_id, state, error,
  pending_approval_request_id) - ``schema_v3.sql`` 28-66, states widened
  (FEATURE_SPEC, FEATURE_PLAN, BUILD_QUEUED) in ``schema_v4.sql`` 40-47.
* ``planning_run_events`` (id, correlation_id, stage_label, status,
  details_json) - ``schema_v3.sql`` 79-92; one row per transition with the
  new state as ``status`` - ``planning/run_store.py`` 350-358.
* ``work_queue`` (id, status, correlation_id UNIQUE, closed_reason) and
  ``work_queue_events`` (queue_id, action, details_json) - ``schema_v10.sql``
  37-57.
* ``publication_records`` (build_id, target_branch, j_commit, result) -
  ``schema_v15.sql`` 59-90 (no STRICT).
* ``missions`` (id, status, correlation_id UNIQUE, plan_request_id,
  closed_reason), ``mission_features`` (mission_id, key),
  ``mission_attempts`` (mission_id, key, attempt, correlation_id, status,
  reason) - ``lifecycle/missions.py`` 100-140; statuses 65-75 and 82-84.

Values and rules:

* Merge offer row: ``target_identifier`` ``merge_deploy_offer``, record under
  ``details_json["merge_offer"]`` - ``pipeline/merge_offer.py`` 116-122;
  the record carries ``request_id``, ``correlation_id``,
  ``approval_subject`` and (previewed offers) ``review_evidence`` -
  ``merge_offer.py`` 2790, 2825-2830; the latest offer row is the one every
  reader takes - ``lifecycle/card_revisions.py`` 58-61, 180-207.
* Durable merge decision row: ``target_identifier``
  ``merge_deploy_decision`` (``MERGE_DECISION_TARGET_IDENTIFIER``,
  ``pipeline/merge_executor.py`` 250), status PASSED for approve and SKIPPED
  otherwise, record under ``details_json["merge_decision"]`` with
  ``decision``, ``decided_by``, ``request_id`` - ``merge_executor.py`` 333,
  6241-6280. A reject is read as Forge's mission finish reads it -
  ``pipeline/mission_finish.py`` 1008-1025, and the queue's -
  ``planning/work_queue_loop.py`` 788-790.
* Merge report row: ``stage_label`` ``merge-deploy``, ``target_identifier``
  ``merge_deploy_executor`` - ``merge_executor.py`` 260-261, written by
  ``_record_report`` 1799-1826 with ``result`` and ``detail`` at the top of
  its details. ``publication-pending`` - ``merge_executor.py`` 356, 3874-3879.
* On main: the publication record's ``result`` is ``published, deployment
  pending`` or ``merged into the remote and running`` and its
  ``target_branch`` (or the build's, when the record has none) is the build's
  ``target_branch`` (or ``main``) - ``pipeline/publication_record.py``
  105-127, ``pipeline/mission_finish.py`` 1046-1054. Deploy failed words -
  ``mission_finish.py`` 90-92.
* ``build_rejected`` queue event with ``{"reason": ...}`` -
  ``planning/work_queue_store.py`` 61, 697-702.
* Already done: a PLANNED_HANDOFF transition labelled ``nothing-to-build``
  whose details hold ``{"outcome": "nothing_to_build", "proof": [...]}`` -
  ``planning/driver.py`` 2762-2843, ``planning/nothing_to_build.py`` 58-71,
  278-284; the queue row then closes with a reason starting "already done,
  nothing to build" (``nothing_to_build.py`` 71).
* Terminal build states COMPLETE, FAILED, CANCELLED, SKIPPED -
  ``cli/status.py`` 96-101; the failed ones are those minus COMPLETE -
  ``planning/work_queue_loop.py`` 192-195. Planning failure words -
  ``work_queue_loop.py`` 280-284.
* A mission's merge build: the first ``builds`` row by ``queued_at`` with
  that ``mission_id`` and ``mission_role = 'mission-merge'`` -
  ``lifecycle/mission_builds.py`` 111-126, ``missions.py`` 91. Latest
  attempt per key - ``missions.py`` 667-674.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "ForgeRecord",
    "ForgeRecordUnavailable",
    "KeyAttempt",
    "MissionOutcome",
    "OpenCard",
    "RecordedAttempt",
    "SingleOutcome",
    "connect_read_only",
]


class ForgeRecordUnavailable(Exception):
    """Forge's record could not be read this time. Read nothing this poll."""


# ---------------------------------------------------------------------------
# Forge's names, copied (see the module docstring for where each comes from)
# ---------------------------------------------------------------------------

#: forge/pipeline/merge_offer.py 116, 122.
MERGE_OFFER_TARGET_IDENTIFIER = "merge_deploy_offer"
MERGE_OFFER_DETAILS_KEY = "merge_offer"
#: forge/pipeline/merge_executor.py 250 (MERGE_DECISION_TARGET_IDENTIFIER), 333.
MERGE_DECISION_TARGET_IDENTIFIER = "merge_deploy_decision"
MERGE_DECISION_DETAILS_KEY = "merge_decision"
#: forge/pipeline/merge_executor.py 261 (the merge report, stage "merge-deploy").
MERGE_REPORT_TARGET_IDENTIFIER = "merge_deploy_executor"
#: forge/pipeline/merge_executor.py 356.
RESULT_WORD_PUBLICATION_PENDING = "publication-pending"
#: forge/pipeline/publication_record.py 109, 127.
ON_MAIN_RESULTS = frozenset({"published, deployment pending", "merged into the remote and running"})
#: forge/pipeline/mission_finish.py 90-92.
DEPLOY_FAILED_WORDS = frozenset({"merged-deploy-failed", "merged-deploy-reverted"})
#: forge/planning/work_queue_store.py 61.
BUILD_REJECTED_ACTION = "build_rejected"
#: forge/planning/nothing_to_build.py 58, 61, 64, 71.
NOTHING_TO_BUILD = "nothing_to_build"
NOTHING_TO_BUILD_QUEUE_REASON = "already done, nothing to build"
#: forge/lifecycle/missions.py 91.
MISSION_ROLE_MERGE = "mission-merge"

_BUILD_FAILED_STATES = frozenset({"FAILED", "CANCELLED", "SKIPPED"})
_PLANNING_FAILURE_WORDS = {
    "FAILED": "the planning run failed",
    "CANCELLED": "the planning run was cancelled",
    "TIMED_OUT": "the planning run ran out of time",
}
_PLANNING_HANDED_OVER = frozenset({"PLANNED_HANDOFF", "BUILD_QUEUED"})
_MISSION_ENDED = frozenset({"REJECTED", "NOT_STARTED", "MERGED", "NOT_MERGED"})

#: Columns this module reads, per table. A record missing any is refused.
_REQUIRED_COLUMNS: dict[str, frozenset[str]] = {
    "work_queue": frozenset({"id", "status", "correlation_id", "closed_reason"}),
    "work_queue_events": frozenset({"id", "queue_id", "action", "details_json"}),
    "planning_runs": frozenset({"correlation_id", "state", "error", "pending_approval_request_id"}),
    "planning_run_events": frozenset(
        {"id", "correlation_id", "stage_label", "status", "details_json"}
    ),
    "builds": frozenset(
        {"build_id", "correlation_id", "status", "error", "queued_at", "target_branch"}
    ),
    "stage_log": frozenset({"id", "build_id", "target_identifier", "status", "details_json"}),
    "publication_records": frozenset({"build_id", "result", "target_branch", "j_commit"}),
}
#: The mission tables are created outside Forge's migration ladder; a record
#: without any of them simply has no missions. Some but not all is refused.
_MISSION_COLUMNS: dict[str, frozenset[str]] = {
    "missions": frozenset({"id", "status", "correlation_id", "plan_request_id", "closed_reason"}),
    "mission_features": frozenset({"mission_id", "key"}),
    "mission_attempts": frozenset(
        {"mission_id", "key", "attempt", "correlation_id", "status", "reason"}
    ),
}

#: The door's own correlation ids start with this (design section 1).
LINEAR_PREFIX = "lin-"

# Phases. The ones marked "ends" end the attempt (design, "When an attempt ends").
UNFILED = "unfiled"
QUEUED = "queued"
PLANNING = "planning"
PLAN_CARD_OPEN = "plan_card_open"
BUILD_QUEUED = "build_queued"
BUILDING = "building"
MERGE_CARD_OPEN = "merge_card_open"
PUBLICATION_IN_FLIGHT = "publication_in_flight"
PUBLICATION_STOPPED = "publication_stopped"
ALREADY_DONE = "already_done"  # ends
REFUSED_BUILD = "refused_build"  # ends
WITHDRAWN = "withdrawn"  # ends
BLOCKED = "blocked"  # ends
PLANNING_FAILED = "planning_failed"  # ends (failed, cancelled or rejected, timed out)
BUILD_FAILED = "build_failed"  # ends
MERGE_DECLINED = "merge_declined"  # ends
MERGE_FAILED = "merge_failed"  # ends
ON_MAIN = "on_main"  # ends
ON_MAIN_DEPLOY_FAILED = "on_main_deploy_failed"  # ends
# Mission-only phases.
MISSION_RUNNING = "running"
MISSION_READY = "ready"
PLAN_REJECTED = "plan_rejected"  # ends
NOT_STARTED = "not_started"  # ends
NOT_MERGED = "not_merged"  # ends

_SINGLE_ENDS = frozenset(
    {
        ALREADY_DONE,
        REFUSED_BUILD,
        WITHDRAWN,
        BLOCKED,
        PLANNING_FAILED,
        BUILD_FAILED,
        MERGE_DECLINED,
        MERGE_FAILED,
        ON_MAIN,
        ON_MAIN_DEPLOY_FAILED,
    }
)

_STOPPED_ACTION = (
    "Nothing was published. Someone needs to deal with the reason given, then run "
    "the merge again (the next merge word, or forge merge-deploy for build {build_id})."
)


# ---------------------------------------------------------------------------
# What it hands back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleOutcome:
    """Where one single-issue attempt has got to, read from Forge's record."""

    correlation_id: str
    phase: str
    ended: bool
    reason: str = ""
    build_id: str | None = None
    #: The open card's request id (plan or merge card), when one is open.
    request_id: str | None = None
    app_url: str | None = None
    report_url: str | None = None
    j_commit: str | None = None
    #: The already-done proof lines (``path:line - why``).
    proof: tuple[str, ...] = ()
    #: For ``publication_stopped``: what someone has to do.
    required_action: str | None = None


@dataclass(frozen=True)
class KeyAttempt:
    """The latest attempt of one mission key."""

    key: str
    attempt: int
    status: str
    reason: str | None
    correlation_id: str


@dataclass(frozen=True)
class MissionOutcome:
    """Where one mission attempt has got to, read from Forge's record."""

    correlation_id: str
    phase: str
    ended: bool
    mission_id: str | None = None
    status: str | None = None
    reason: str = ""
    keys: tuple[str, ...] = ()
    attempts: tuple[KeyAttempt, ...] = ()
    landed_keys: tuple[str, ...] = ()
    merge_build_id: str | None = None
    request_id: str | None = None
    app_url: str | None = None
    report_url: str | None = None
    j_commit: str | None = None
    required_action: str | None = None


@dataclass(frozen=True)
class OpenCard:
    """A card Forge's record shows as still waiting for an answer.

    ``kind`` is ``merge`` (answerable from Linear: it carries the request id,
    correlation id and approval subject), ``plan`` (a paused planning run) or
    ``mission_plan`` (a proposed mission); the last two lack their assumption
    lists here, so the door asks for them to be answered in Slack.
    """

    kind: str
    correlation_id: str
    request_id: str
    approval_subject: str | None = None
    build_id: str | None = None
    app_url: str | None = None
    report_url: str | None = None


@dataclass(frozen=True)
class RecordedAttempt:
    """One attempt Forge has recorded for the door (``kind`` single or mission)."""

    correlation_id: str
    kind: str
    phase: str
    ended: bool


# ---------------------------------------------------------------------------
# Opening the record
# ---------------------------------------------------------------------------


def connect_read_only(path: str | Path, *, timeout: float = 5.0) -> sqlite3.Connection:
    """Open Forge's record read-only (``mode=ro``); a missing file is refused."""
    db = Path(path)
    if not db.is_file():
        raise ForgeRecordUnavailable(f"Forge's record is not at {db}")
    try:
        cx = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=timeout, isolation_level=None)
    except sqlite3.Error as exc:
        raise ForgeRecordUnavailable(f"Forge's record could not be opened: {exc}") from exc
    return cx


def _columns(cx: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in cx.execute(f"PRAGMA table_info({table})")}


def _details(raw: Any) -> dict[str, Any]:
    try:
        decoded = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


class ForgeRecord:
    """Read-only reader of Forge's SQLite record (``forge.db``)."""

    def __init__(self, path: str | Path, *, timeout: float = 5.0) -> None:
        self._path = Path(path)
        self._timeout = timeout

    def outcome_for_single(self, correlation_id: str) -> SingleOutcome:
        with self._reading() as reader:
            return reader.single(correlation_id)

    def outcome_for_mission(self, correlation_id: str) -> MissionOutcome:
        with self._reading() as reader:
            return reader.mission(correlation_id)

    def open_cards_for(self, correlation_ids: Iterable[str]) -> list[OpenCard]:
        with self._reading() as reader:
            return [card for cid in correlation_ids for card in reader.cards(cid)]

    def all_linear_attempts(self) -> list[RecordedAttempt]:
        with self._reading() as reader:
            return reader.all_attempts()

    @contextmanager
    def _reading(self) -> Iterator[_Reader]:
        """One read transaction, so every answer comes from one moment."""
        cx = connect_read_only(self._path, timeout=self._timeout)
        try:
            cx.execute("BEGIN")
            reader = _Reader(cx, *self._check_schema(cx))
            yield reader
        except sqlite3.Error as exc:
            raise ForgeRecordUnavailable(f"Forge's record could not be read: {exc}") from exc
        finally:
            with suppress(sqlite3.Error):
                cx.execute("ROLLBACK")
            cx.close()

    @staticmethod
    def _check_schema(cx: sqlite3.Connection) -> tuple[bool, bool]:
        """Refuse a record whose shape is not the one checked here.

        Returns (has mission tables, builds has mission columns).
        """
        for table, needed in _REQUIRED_COLUMNS.items():
            missing = needed - _columns(cx, table)
            if missing:
                raise ForgeRecordUnavailable(
                    f"Forge's record has no {table} columns {sorted(missing)}"
                )
        present = [t for t in _MISSION_COLUMNS if _columns(cx, t)]
        if present and len(present) != len(_MISSION_COLUMNS):
            raise ForgeRecordUnavailable(f"Forge's record has only some mission tables: {present}")
        for table in present:
            missing = _MISSION_COLUMNS[table] - _columns(cx, table)
            if missing:
                raise ForgeRecordUnavailable(
                    f"Forge's record has no {table} columns {sorted(missing)}"
                )
        build_columns = _columns(cx, "builds")
        return bool(present), {"mission_id", "mission_role"} <= build_columns


# ---------------------------------------------------------------------------
# The reads (one connection, one transaction)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _MergeView:
    """What a build's merge rows say, as (phase, reason, action) plus details."""

    phase: str | None
    reason: str = ""
    required_action: str | None = None
    request_id: str | None = None
    app_url: str | None = None
    report_url: str | None = None
    j_commit: str | None = None


class _Reader:
    def __init__(self, cx: sqlite3.Connection, has_missions: bool, mission_builds: bool):
        self._cx = cx
        self._has_missions = has_missions
        self._mission_builds = mission_builds

    def _one(self, sql: str, *args: Any) -> tuple[Any, ...] | None:
        row: tuple[Any, ...] | None = self._cx.execute(sql, args).fetchone()
        return row

    # -- the merge rows of one build -----------------------------------------

    def _latest_stage(self, build_id: str, target: str) -> tuple[int, str, dict[str, Any]] | None:
        row = self._one(
            "SELECT id, status, details_json FROM stage_log "
            "WHERE build_id = ? AND target_identifier = ? ORDER BY id DESC LIMIT 1",
            build_id,
            target,
        )
        return (int(row[0]), str(row[1]), _details(row[2])) if row else None

    def merge_view(self, build_id: str, build_target: str | None) -> _MergeView:
        offer_row = self._latest_stage(build_id, MERGE_OFFER_TARGET_IDENTIFIER)
        decision_row = self._latest_stage(build_id, MERGE_DECISION_TARGET_IDENTIFIER)
        report_row = self._latest_stage(build_id, MERGE_REPORT_TARGET_IDENTIFIER)
        record = self._one(
            "SELECT result, target_branch, j_commit FROM publication_records WHERE build_id = ?",
            build_id,
        )
        offer = offer_row[2].get(MERGE_OFFER_DETAILS_KEY) if offer_row else None
        offer = offer if isinstance(offer, dict) else {}
        evidence = offer.get("review_evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        target = build_target or "main"
        result, recorded_target, j_commit = (
            (_text(record[0]), _text(record[1]), _text(record[2])) if record else (None, None, None)
        )
        report = report_row[2] if report_row else {}
        word = str(report.get("result") or "")
        detail = str(report.get("detail") or "")

        def view(phase: str | None, reason: str = "", **extra: Any) -> _MergeView:
            return _MergeView(
                phase,
                reason,
                app_url=_text(evidence.get("app_url")),
                report_url=_text(evidence.get("report_url")),
                j_commit=j_commit,
                **extra,
            )

        on_main = result in ON_MAIN_RESULTS and (recorded_target or target) == target
        if on_main:
            if word in DEPLOY_FAILED_WORDS:
                return view(
                    ON_MAIN_DEPLOY_FAILED,
                    f"merged into {target}, but its deploy failed: {detail or word}",
                )
            return view(ON_MAIN, f"merged into {target} ({result})")
        if decision_row is not None:
            decision_id, decision_status, decision_details = decision_row
            said = decision_details.get(MERGE_DECISION_DETAILS_KEY)
            said = said if isinstance(said, dict) else {}
            who = str(said.get("decided_by") or "the approver")
            if decision_status != "PASSED" or said.get("decision") == "reject":
                return view(MERGE_DECLINED, f"{who} declined the merge card")
            if report_row is None or report_row[0] < decision_id:
                return view(
                    PUBLICATION_IN_FLIGHT,
                    f"{who} approved the merge; it is being joined, checked and published",
                )
            if report_row[1] == "FAILED":
                return view(MERGE_FAILED, detail or f"the merge ended {word or 'without a word'}")
            # The press finished and did not publish: publication-pending, or
            # any other report that left the work off main.
            return view(
                PUBLICATION_STOPPED,
                detail or f"the merge ended {word or 'without a word'} and nothing was published",
                required_action=_STOPPED_ACTION.format(build_id=build_id),
            )
        if offer_row is not None:
            return view(
                MERGE_CARD_OPEN,
                "the merge card is waiting for an answer",
                request_id=_text(offer.get("request_id")),
            )
        return view(None)

    # -- a single issue ------------------------------------------------------

    def single(self, cid: str) -> SingleOutcome:
        queue = self._one(
            "SELECT id, status, closed_reason FROM work_queue WHERE correlation_id = ?", cid
        )
        run = self._one(
            "SELECT state, error, pending_approval_request_id FROM planning_runs "
            "WHERE correlation_id = ?",
            cid,
        )
        build = self._one(
            "SELECT build_id, status, error, target_branch FROM builds "
            "WHERE correlation_id = ? ORDER BY queued_at DESC LIMIT 1",
            cid,
        )

        def out(phase: str, reason: str = "", **extra: Any) -> SingleOutcome:
            return SingleOutcome(cid, phase, phase in _SINGLE_ENDS, reason, **extra)

        if queue is None and run is None and build is None:
            return out(UNFILED, "Forge has not recorded this request")

        if build is not None:
            build_id, status = str(build[0]), str(build[1])
            view = self.merge_view(build_id, _text(build[3]))
            if view.phase is not None:
                return out(
                    view.phase,
                    view.reason,
                    build_id=build_id,
                    request_id=view.request_id,
                    app_url=view.app_url,
                    report_url=view.report_url,
                    j_commit=view.j_commit,
                    required_action=view.required_action,
                )
            if status in _BUILD_FAILED_STATES:
                reason = _text(build[2]) or f"the build ended {status.lower()}"
                return out(BUILD_FAILED, reason, build_id=build_id)
            if status == "COMPLETE":
                return out(BUILDING, "built; the merge card is being prepared", build_id=build_id)
            return out(BUILDING, f"the build is {status.lower()}", build_id=build_id)

        if queue is not None:
            refused = self._one(
                "SELECT details_json FROM work_queue_events WHERE queue_id = ? AND action = ? "
                "ORDER BY id DESC LIMIT 1",
                int(queue[0]),
                BUILD_REJECTED_ACTION,
            )
            if refused is not None:
                reason = _details(refused[0]).get("reason") or "no reason was given"
                return out(REFUSED_BUILD, f"the build was refused: {reason}")
            if queue[1] == "WITHDRAWN":
                return out(WITHDRAWN, _text(queue[2]) or "withdrawn from the queue")
            if queue[1] == "BLOCKED":
                return out(BLOCKED, _text(queue[2]) or "blocked in the queue")

        if run is not None:
            state = str(run[0])
            if state == "PAUSED":
                return out(
                    PLAN_CARD_OPEN,
                    "the plan card is waiting for an answer",
                    request_id=_text(run[2]),
                )
            if state in _PLANNING_FAILURE_WORDS:
                words = _PLANNING_FAILURE_WORDS[state]
                return out(PLANNING_FAILED, f"{words}: {run[1]}" if run[1] else words)
            if state in _PLANNING_HANDED_OVER:
                proof = self._already_done_proof(cid)
                if proof is not None:
                    return out(
                        ALREADY_DONE,
                        "already done: the factory found this in the code and built nothing",
                        proof=proof,
                    )
                return out(BUILD_QUEUED, "planned; the build is queued")
            return out(PLANNING, f"planning ({state.lower()})")

        assert queue is not None
        reason = _text(queue[2]) or ""
        if queue[1] == "DONE":
            if reason.startswith(NOTHING_TO_BUILD_QUEUE_REASON):
                return out(ALREADY_DONE, reason)
            return out(BUILD_QUEUED, reason or "handed over from the queue")
        return out(QUEUED, f"waiting in the factory's queue ({str(queue[1]).lower()})")

    def _already_done_proof(self, cid: str) -> tuple[str, ...] | None:
        """The proof lines when the run ended with the nothing-to-build marker."""
        row = self._one(
            "SELECT details_json FROM planning_run_events "
            "WHERE correlation_id = ? AND status = 'PLANNED_HANDOFF' ORDER BY id DESC LIMIT 1",
            cid,
        )
        details = _details(row[0]) if row else {}
        if details.get("outcome") != NOTHING_TO_BUILD:
            return None
        proof = details.get("proof")
        return tuple(str(p) for p in proof) if isinstance(proof, list) else ()

    # -- a mission -----------------------------------------------------------

    def _mission_row(self, cid: str) -> tuple[Any, ...] | None:
        if not self._has_missions:
            return None
        return self._one(
            "SELECT id, status, closed_reason, plan_request_id FROM missions "
            "WHERE correlation_id = ?",
            cid,
        )

    def _mission_merge_build(self, mission_id: str) -> tuple[str, str | None] | None:
        if not self._mission_builds:
            return None
        row = self._one(
            "SELECT build_id, target_branch FROM builds WHERE mission_id = ? "
            "AND mission_role = ? ORDER BY queued_at ASC LIMIT 1",
            mission_id,
            MISSION_ROLE_MERGE,
        )
        return (str(row[0]), _text(row[1])) if row else None

    def mission(self, cid: str) -> MissionOutcome:
        row = self._mission_row(cid)
        if row is None:
            return MissionOutcome(cid, UNFILED, False, reason="Forge has not recorded this mission")
        mission_id, status = str(row[0]), str(row[1])
        closed_reason = _text(row[2]) or ""
        keys = tuple(
            str(r[0])
            for r in self._cx.execute(
                "SELECT key FROM mission_features WHERE mission_id = ? ORDER BY key",
                (mission_id,),
            )
        )
        latest: dict[str, KeyAttempt] = {}
        for r in self._cx.execute(
            "SELECT key, attempt, status, reason, correlation_id FROM mission_attempts "
            "WHERE mission_id = ? ORDER BY key, attempt",
            (mission_id,),
        ):
            latest[str(r[0])] = KeyAttempt(str(r[0]), int(r[1]), str(r[2]), _text(r[3]), str(r[4]))
        attempts = tuple(latest[k] for k in sorted(latest))
        landed = tuple(a.key for a in attempts if a.status == "LANDED")

        merge = self._mission_merge_build(mission_id)
        view = self.merge_view(*merge) if merge else _MergeView(None)

        request_id = view.request_id
        required_action = view.required_action
        reason = closed_reason
        if status == "PROPOSED":
            phase, request_id = PLAN_CARD_OPEN, _text(row[3])
            reason = "the mission's plan card is waiting for an answer"
        elif status == "REJECTED":
            phase = PLAN_REJECTED
        elif status == "NOT_STARTED":
            phase = NOT_STARTED
        elif status in ("STARTING", "RUNNING"):
            phase = MISSION_RUNNING
        elif status == "MERGED":
            phase = view.phase if view.phase in (ON_MAIN, ON_MAIN_DEPLOY_FAILED) else ON_MAIN
            reason = view.reason or closed_reason
        elif status == "NOT_MERGED":
            phase = MERGE_DECLINED if view.phase == MERGE_DECLINED else NOT_MERGED
        else:  # READY, MERGING
            phase = view.phase or MISSION_READY
            reason = view.reason or "the mission is finished; its merge card is being prepared"
        return MissionOutcome(
            cid,
            phase,
            status in _MISSION_ENDED,
            mission_id=mission_id,
            status=status,
            reason=reason,
            keys=keys,
            attempts=attempts,
            landed_keys=landed,
            merge_build_id=merge[0] if merge else None,
            request_id=request_id,
            app_url=view.app_url,
            report_url=view.report_url,
            j_commit=view.j_commit,
            required_action=required_action,
        )

    # -- open cards ----------------------------------------------------------

    def cards(self, cid: str) -> list[OpenCard]:
        found: list[OpenCard] = []
        run = self._one(
            "SELECT pending_approval_request_id FROM planning_runs "
            "WHERE correlation_id = ? AND state = 'PAUSED'",
            cid,
        )
        if run is not None and run[0]:
            found.append(OpenCard("plan", cid, str(run[0])))
        mission = self._mission_row(cid)
        if mission is not None:
            if mission[1] == "PROPOSED" and mission[3]:
                found.append(OpenCard("mission_plan", cid, str(mission[3])))
            merge = self._mission_merge_build(str(mission[0]))
            build_id = merge[0] if merge else None
        else:
            build = self._one(
                "SELECT build_id FROM builds WHERE correlation_id = ? "
                "ORDER BY queued_at DESC LIMIT 1",
                cid,
            )
            build_id = str(build[0]) if build else None
        if build_id is not None:
            card = self._open_merge_card(cid, build_id)
            if card is not None:
                found.append(card)
        return found

    def _open_merge_card(self, cid: str, build_id: str) -> OpenCard | None:
        """The latest offer, when no decision row is on record for the build."""
        if self._latest_stage(build_id, MERGE_DECISION_TARGET_IDENTIFIER) is not None:
            return None
        offer_row = self._latest_stage(build_id, MERGE_OFFER_TARGET_IDENTIFIER)
        if offer_row is None:
            return None
        offer = offer_row[2].get(MERGE_OFFER_DETAILS_KEY)
        offer = offer if isinstance(offer, dict) else {}
        request_id = _text(offer.get("request_id"))
        if request_id is None:
            return None
        evidence = offer.get("review_evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        return OpenCard(
            "merge",
            _text(offer.get("correlation_id")) or cid,
            request_id,
            approval_subject=_text(offer.get("approval_subject")),
            build_id=build_id,
            app_url=_text(evidence.get("app_url")),
            report_url=_text(evidence.get("report_url")),
        )

    # -- the rebuild ---------------------------------------------------------

    def all_attempts(self) -> list[RecordedAttempt]:
        prefix = (len(LINEAR_PREFIX), LINEAR_PREFIX)
        missions: list[str] = []
        not_single: set[str] = set()
        if self._has_missions:
            missions = [
                str(r[0])
                for r in self._cx.execute(
                    "SELECT correlation_id FROM missions WHERE substr(correlation_id, 1, ?) = ?",
                    prefix,
                )
            ]
            # A mission feature's own planning run is part of its mission.
            not_single = set(missions) | {
                str(r[0])
                for r in self._cx.execute(
                    "SELECT correlation_id FROM mission_attempts "
                    "WHERE substr(correlation_id, 1, ?) = ?",
                    prefix,
                )
            }
        singles = sorted(
            {
                str(r[0])
                for r in self._cx.execute(
                    "SELECT correlation_id FROM work_queue WHERE substr(correlation_id, 1, ?) = ? "
                    "UNION SELECT correlation_id FROM planning_runs "
                    "WHERE substr(correlation_id, 1, ?) = ?",
                    prefix + prefix,
                )
            }
            - not_single
        )
        found: list[RecordedAttempt] = []
        for cid in singles:
            single = self.single(cid)
            found.append(RecordedAttempt(cid, "single", single.phase, single.ended))
        for cid in sorted(missions):
            mission = self.mission(cid)
            found.append(RecordedAttempt(cid, "mission", mission.phase, mission.ended))
        return found
