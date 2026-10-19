"""The Linear door's read-only reader of Forge's record.

Each test builds a Forge record from the copied schema
(``forge_schema_dbd40c7e.sql``), writes the rows Forge writes for one outcome,
and checks the phase and whether the attempt has ended (design
``linear-front-door-2026-10-18.md``, section 2, "When an attempt ends").
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from jarvis.infrastructure.linear import forge_record as fr
from jarvis.infrastructure.linear.forge_record import (
    ForgeRecord,
    ForgeRecordUnavailable,
    connect_read_only,
)

SCHEMA = Path(__file__).with_name("forge_schema_dbd40c7e.sql")
NOW = "2026-10-18T10:00:00+00:00"
CID = "lin-ENG-12-1"
MCID = "lin-m-label1-1"


class Ledger:
    """A writable Forge record for the test to fill, read through ForgeRecord."""

    def __init__(self, path: Path, *, schema: str | None = None) -> None:
        self.path = path
        self.cx = sqlite3.connect(path)
        self.cx.executescript(schema if schema is not None else SCHEMA.read_text())
        self.cx.commit()
        self.record = ForgeRecord(path, timeout=0.2)

    def queue(self, cid: str, status: str = "QUEUED", reason: str | None = None) -> int:
        cur = self.cx.execute(
            "INSERT INTO work_queue (sentence, kind, status, rank, originating_user, "
            "correlation_id, queued_at, closed_reason) "
            "VALUES ('s', 'feature', ?, 1.0, 'u', ?, ?, ?)",
            (status, cid, NOW, reason),
        )
        self.cx.commit()
        return int(cur.lastrowid)

    def queue_event(self, queue_id: int, action: str, details: dict) -> None:
        self.cx.execute(
            "INSERT INTO work_queue_events (queue_id, action, actor_identity, details_json, "
            "recorded_at) VALUES (?, ?, 'forge-pipeline', ?, ?)",
            (queue_id, action, json.dumps(details), NOW),
        )
        self.cx.commit()

    def run(
        self,
        cid: str,
        state: str,
        *,
        error: str | None = None,
        pending: str | None = None,
        event: tuple[str, dict] | None = None,
        request_text: str = "r",
    ) -> None:
        self.cx.execute(
            "INSERT INTO planning_runs (correlation_id, state, originating_user, "
            "expected_approver, request_text, triggered_by, queued_at, error, "
            "pending_approval_request_id) VALUES (?, ?, 'u', 'a', ?, 'jarvis', ?, ?, ?)",
            (cid, state, request_text, NOW, error, pending),
        )
        if event is not None:
            label, details = event
            self.cx.execute(
                "INSERT INTO planning_run_events (correlation_id, stage_label, status, "
                "details_json, recorded_at) VALUES (?, ?, ?, ?, ?)",
                (cid, label, state, json.dumps(details), NOW),
            )
        self.cx.commit()

    def build(
        self,
        cid: str,
        build_id: str,
        status: str = "RUNNING",
        *,
        queued_at: str = NOW,
        error: str | None = None,
        target: str | None = "main",
        mission_id: str | None = None,
        role: str | None = None,
        feature_id: str = "FEAT-1",
        repo: str = "repo",
    ) -> None:
        self.cx.execute(
            "INSERT INTO builds (build_id, feature_id, repo, branch, feature_yaml_path, "
            "status, triggered_by, correlation_id, queued_at, error, target_branch, "
            "mission_id, mission_role) VALUES (?, ?, ?, 'b', 'f.yaml', ?, "
            "'jarvis', ?, ?, ?, ?, ?, ?)",
            (build_id, feature_id, repo, status, cid, queued_at, error, target, mission_id, role),
        )
        self.cx.commit()

    def stage(self, build_id: str, target: str, status: str, details: dict) -> None:
        self.cx.execute(
            "INSERT INTO stage_log (build_id, stage_label, target_kind, target_identifier, "
            "status, started_at, completed_at, duration_secs, details_json) "
            "VALUES (?, 'x', 'local_tool', ?, ?, ?, ?, 0.0, ?)",
            (build_id, target, status, NOW, NOW, json.dumps(details)),
        )
        self.cx.commit()

    def offer(self, build_id: str, cid: str, request_id: str | None = None) -> None:
        self.stage(
            build_id,
            "merge_deploy_offer",
            "GATED",
            {
                "merge_offer": {
                    "request_id": request_id or f"merge-{build_id}",
                    "correlation_id": cid,
                    "approval_subject": "agents.approval.forge.FEAT-1",
                    "review_evidence": {
                        "app_url": "https://preview.example/app",
                        "report_url": "https://preview.example/report",
                    },
                }
            },
        )

    def decide(self, build_id: str, decision: str) -> None:
        self.stage(
            build_id,
            "merge_deploy_decision",
            "PASSED" if decision == "approve" else "SKIPPED",
            {
                "merge_decision": {
                    "decision": decision,
                    "decided_by": "approver",
                    "request_id": f"merge-{build_id}",
                }
            },
        )

    def report(self, build_id: str, status: str, result: str, detail: str) -> None:
        self.stage(
            build_id,
            "merge_deploy_executor",
            status,
            {"status": status, "result": result, "detail": detail},
        )

    def publication(
        self, build_id: str, result: str, *, target: str = "main", j_commit: str = "abc123"
    ) -> None:
        self.cx.execute(
            "INSERT INTO publication_records (build_id, target_branch, j_commit, result) "
            "VALUES (?, ?, ?, ?)",
            (build_id, target, j_commit, result),
        )
        self.cx.commit()

    def mission(
        self,
        cid: str,
        mission_id: str,
        status: str,
        *,
        keys: tuple[str, ...] = (),
        reason: str | None = None,
        plan_request_id: str | None = None,
        title: str = "t",
    ) -> None:
        self.cx.execute(
            "INSERT INTO missions (id, title, target_repo, branch, status, correlation_id, "
            "originating_user, plan_request_id, created_at, closed_reason) "
            "VALUES (?, ?, 'repo', ?, ?, ?, 'u', ?, ?, ?)",
            (mission_id, title, f"mission/{mission_id}", status, cid, plan_request_id, NOW, reason),
        )
        for key in keys:
            self.cx.execute(
                "INSERT INTO mission_features (mission_id, key, sentence) VALUES (?, ?, 's')",
                (mission_id, key),
            )
        self.cx.commit()

    def attempt(
        self, mission_id: str, cid: str, key: str, n: int, status: str, reason: str | None = None
    ) -> None:
        self.cx.execute(
            "INSERT INTO mission_attempts (mission_id, key, attempt, correlation_id, status, "
            "reason) VALUES (?, ?, ?, ?, ?, ?)",
            (mission_id, key, n, f"{cid}-{key}-a{n}", status, reason),
        )
        self.cx.commit()


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    led = Ledger(tmp_path / "forge.db")
    yield led
    led.cx.close()


def single(ledger: Ledger, cid: str = CID) -> fr.SingleOutcome:
    return ledger.record.outcome_for_single(cid)


# ---------------------------------------------------------------------------
# A single issue, before a build
# ---------------------------------------------------------------------------


def test_nothing_recorded_is_unfiled_and_open(ledger: Ledger) -> None:
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.UNFILED, False)


def test_waiting_in_the_queue(ledger: Ledger) -> None:
    ledger.queue(CID)
    assert (single(ledger).phase, single(ledger).ended) == (fr.QUEUED, False)


def test_planning_running(ledger: Ledger) -> None:
    ledger.queue(CID, "ADMITTED")
    ledger.run(CID, "FEATURE_PLAN")
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.PLANNING, False)


def test_paused_planning_run_is_an_open_plan_card(ledger: Ledger) -> None:
    ledger.queue(CID, "ADMITTED")
    ledger.run(CID, "PAUSED", pending="plan-req-1")
    out = single(ledger)
    assert (out.phase, out.ended, out.request_id) == (fr.PLAN_CARD_OPEN, False, "plan-req-1")
    cards = ledger.record.open_cards_for([CID])
    assert [(c.kind, c.request_id) for c in cards] == [("plan", "plan-req-1")]


@pytest.mark.parametrize(
    ("state", "words"),
    [
        ("FAILED", "the planning run failed"),
        ("CANCELLED", "the planning run was cancelled"),
        ("TIMED_OUT", "the planning run ran out of time"),
    ],
)
def test_planning_that_ended_badly_ends_the_attempt(ledger: Ledger, state: str, words: str) -> None:
    ledger.queue(CID, "DONE", "closed")
    ledger.run(CID, state, error="rejected at the plan card")
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.PLANNING_FAILED, True)
    assert out.reason == f"{words}: rejected at the plan card"


def test_nothing_to_build_ends_the_attempt_as_already_done(ledger: Ledger) -> None:
    ledger.queue(CID, "DONE", "already done, nothing to build: see proof")
    ledger.run(
        CID,
        "PLANNED_HANDOFF",
        event=(
            "nothing-to-build",
            {"outcome": "nothing_to_build", "proof": ["src/app.py:10-20 - the endpoint"]},
        ),
    )
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.ALREADY_DONE, True)
    assert out.proof == ("src/app.py:10-20 - the endpoint",)


def test_ordinary_handoff_is_not_an_end(ledger: Ledger) -> None:
    ledger.queue(CID, "DONE", "handed to the build")
    ledger.run(CID, "PLANNED_HANDOFF", event=("feature-plan", {"plan": "x"}))
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.BUILD_QUEUED, False)


def test_build_rejected_before_any_build_row(ledger: Ledger) -> None:
    queue_id = ledger.queue(CID, "DONE", "handed over")
    ledger.run(CID, "PLANNED_HANDOFF")
    ledger.queue_event(queue_id, "build_rejected", {"reason": "path outside the allowed folders"})
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.REFUSED_BUILD, True)
    assert "path outside the allowed folders" in out.reason


@pytest.mark.parametrize(
    ("status", "phase"), [("WITHDRAWN", fr.WITHDRAWN), ("BLOCKED", fr.BLOCKED)]
)
def test_withdrawn_or_blocked_in_the_queue(ledger: Ledger, status: str, phase: str) -> None:
    ledger.queue(CID, status, "operator withdrew it")
    out = single(ledger)
    assert (out.phase, out.ended, out.reason) == (phase, True, "operator withdrew it")


# ---------------------------------------------------------------------------
# A single issue, building and merging
# ---------------------------------------------------------------------------


def _built(ledger: Ledger, status: str = "COMPLETE", build_id: str = "build-FEAT-1-1") -> str:
    ledger.queue(CID, "DONE", "handed over")
    ledger.run(CID, "PLANNED_HANDOFF")
    ledger.build(CID, build_id, status)
    return build_id


def test_building(ledger: Ledger) -> None:
    _built(ledger, "RUNNING")
    out = single(ledger)
    assert (out.phase, out.ended, out.build_id) == (fr.BUILDING, False, "build-FEAT-1-1")


def test_failed_build_ends_the_attempt(ledger: Ledger) -> None:
    ledger.queue(CID, "DONE")
    ledger.build(
        CID, "build-old", "FAILED", queued_at="2026-10-18T09:00:00+00:00", error="tests failed"
    )
    out = single(ledger)
    assert (out.phase, out.ended, out.reason) == (fr.BUILD_FAILED, True, "tests failed")


def test_latest_build_by_queued_at_is_read(ledger: Ledger) -> None:
    ledger.queue(CID, "DONE")
    ledger.build(CID, "build-old", "FAILED", queued_at="2026-10-18T09:00:00+00:00")
    ledger.build(CID, "build-new", "RUNNING", queued_at="2026-10-18T09:30:00+00:00")
    out = single(ledger)
    assert (out.phase, out.ended, out.build_id) == (fr.BUILDING, False, "build-new")


def test_open_merge_card(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.MERGE_CARD_OPEN, False)
    assert out.request_id == f"merge-{build_id}"
    assert (out.app_url, out.report_url) == (
        "https://preview.example/app",
        "https://preview.example/report",
    )
    [card] = ledger.record.open_cards_for([CID])
    assert (card.kind, card.request_id, card.correlation_id, card.approval_subject) == (
        "merge",
        f"merge-{build_id}",
        CID,
        "agents.approval.forge.FEAT-1",
    )
    assert card.build_id == build_id


def test_reject_decision_ends_the_attempt_without_a_report(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "reject")
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.MERGE_DECLINED, True)
    assert ledger.record.open_cards_for([CID]) == []


def test_approved_and_not_yet_reported_is_publication_in_flight(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "publication pending")
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.PUBLICATION_IN_FLIGHT, False)
    assert ledger.record.open_cards_for([CID]) == []


def test_press_finished_without_publishing_is_publication_stopped(ledger: Ledger) -> None:
    """R14: Forge's report says publication-pending (GATED); someone must act."""
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "publication pending")
    ledger.report(
        build_id,
        "GATED",
        "publication-pending",
        "it was checked but not published: the publisher refused",
    )
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.PUBLICATION_STOPPED, False)
    assert out.reason == "it was checked but not published: the publisher refused"


def test_merge_report_that_failed_before_publication_ends_the_attempt(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "publication pending")
    ledger.report(build_id, "FAILED", "conflict", "the branch did not join cleanly")
    out = single(ledger)
    assert (out.phase, out.ended, out.reason) == (
        fr.MERGE_FAILED,
        True,
        "the branch did not join cleanly",
    )


def test_on_main(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "merged into the remote and running", j_commit="j0123")
    ledger.report(build_id, "PASSED", "merged-into-the-remote-and-running", "deployed")
    out = single(ledger)
    assert (out.phase, out.ended, out.j_commit) == (fr.ON_MAIN, True, "j0123")


def test_on_main_with_deploy_failed(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "published, deployment pending", j_commit="j0456")
    ledger.report(build_id, "FAILED", "merged-deploy-failed", "the deploy step failed")
    out = single(ledger)
    assert (out.phase, out.ended, out.j_commit) == (fr.ON_MAIN_DEPLOY_FAILED, True, "j0456")
    assert "the deploy step failed" in out.reason


def test_published_to_another_branch_is_not_on_main(ledger: Ledger) -> None:
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "published, deployment pending", target="release")
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.PUBLICATION_IN_FLIGHT, False)


# ---------------------------------------------------------------------------
# A mission
# ---------------------------------------------------------------------------


def test_mission_not_recorded_is_unfiled(ledger: Ledger) -> None:
    out = ledger.record.outcome_for_mission(MCID)
    assert (out.phase, out.ended) == (fr.UNFILED, False)


def test_proposed_mission_is_an_open_plan_card(ledger: Ledger) -> None:
    ledger.mission(
        MCID, "m-aaaaaa", "PROPOSED", keys=("ENG1", "ENG2"), plan_request_id="mission-req"
    )
    out = ledger.record.outcome_for_mission(MCID)
    assert (out.phase, out.ended, out.request_id) == (fr.PLAN_CARD_OPEN, False, "mission-req")
    assert out.keys == ("ENG1", "ENG2")
    cards = ledger.record.open_cards_for([MCID])
    assert [(c.kind, c.request_id) for c in cards] == [("mission_plan", "mission-req")]


@pytest.mark.parametrize(
    ("status", "phase", "ended"),
    [
        ("REJECTED", fr.PLAN_REJECTED, True),
        ("NOT_STARTED", fr.NOT_STARTED, True),
        ("NOT_MERGED", fr.NOT_MERGED, True),
        ("MERGED", fr.ON_MAIN, True),
        ("STARTING", fr.MISSION_RUNNING, False),
        ("RUNNING", fr.MISSION_RUNNING, False),
        ("READY", fr.MISSION_READY, False),
    ],
)
def test_mission_statuses(ledger: Ledger, status: str, phase: str, ended: bool) -> None:
    ledger.mission(MCID, "m-bbbbbb", status, reason="why")
    out = ledger.record.outcome_for_mission(MCID)
    assert (out.phase, out.ended, out.status) == (phase, ended, status)


def test_mission_partial_landing(ledger: Ledger) -> None:
    mid = "m-cccccc"
    ledger.mission(MCID, mid, "MERGED", keys=("ENG1", "ENG2"), reason="merged")
    ledger.attempt(mid, MCID, "ENG1", 1, "LANDED")
    ledger.attempt(mid, MCID, "ENG2", 1, "FAILED", "conflict")
    ledger.attempt(mid, MCID, "ENG2", 2, "FAILED", "tests failed")
    ledger.build(
        MCID,
        "build-merge-1",
        "COMPLETE",
        queued_at="2026-10-18T09:00:00+00:00",
        mission_id=mid,
        role="mission-merge",
    )
    ledger.build(
        MCID,
        "build-merge-2",
        "COMPLETE",
        queued_at="2026-10-18T09:30:00+00:00",
        mission_id=mid,
        role="mission-merge",
    )
    ledger.offer("build-merge-1", MCID)
    ledger.decide("build-merge-1", "approve")
    ledger.publication("build-merge-1", "published, deployment pending", j_commit="jm1")
    ledger.report("build-merge-1", "PASSED", "published-deployment-pending", "not deployed yet")
    out = ledger.record.outcome_for_mission(MCID)
    assert (out.phase, out.ended) == (fr.ON_MAIN, True)
    assert out.merge_build_id == "build-merge-1"  # the first by queued_at, as Forge reads it
    assert out.landed_keys == ("ENG1",)
    assert [(a.key, a.attempt, a.status, a.reason) for a in out.attempts] == [
        ("ENG1", 1, "LANDED", None),
        ("ENG2", 2, "FAILED", "tests failed"),
    ]
    assert out.j_commit == "jm1"


def test_ready_mission_with_its_merge_card_open(ledger: Ledger) -> None:
    mid = "m-dddddd"
    ledger.mission(MCID, mid, "READY", keys=("ENG1",))
    ledger.attempt(mid, MCID, "ENG1", 1, "LANDED")
    ledger.build(MCID, "build-merge", "COMPLETE", mission_id=mid, role="mission-merge")
    ledger.offer("build-merge", MCID)
    out = ledger.record.outcome_for_mission(MCID)
    assert (out.phase, out.ended, out.request_id) == (
        fr.MERGE_CARD_OPEN,
        False,
        "merge-build-merge",
    )
    [card] = ledger.record.open_cards_for([MCID])
    assert (card.kind, card.build_id, card.correlation_id) == ("merge", "build-merge", MCID)


def test_mission_merge_declined(ledger: Ledger) -> None:
    mid = "m-eeeeee"
    ledger.mission(MCID, mid, "NOT_MERGED", reason="approver declined the merge card")
    ledger.build(MCID, "build-merge", "COMPLETE", mission_id=mid, role="mission-merge")
    ledger.offer("build-merge", MCID)
    ledger.decide("build-merge", "reject")
    out = ledger.record.outcome_for_mission(MCID)
    assert (out.phase, out.ended) == (fr.MERGE_DECLINED, True)


# ---------------------------------------------------------------------------
# The rebuild listing
# ---------------------------------------------------------------------------


def test_all_linear_attempts(ledger: Ledger) -> None:
    ledger.queue("lin-ENG-1-1", "WITHDRAWN", "withdrawn")
    ledger.queue("lin-ENG-2-1", "ADMITTED")
    ledger.run("lin-ENG-2-1", "RUNNING")
    ledger.run("lin-ENG-3-2", "PAUSED", pending="plan-x")
    ledger.queue("slack-abc", "QUEUED")  # not the door's
    ledger.queue("LIN-ENG-9-1", "QUEUED")  # not the door's prefix (case matters)
    ledger.mission(MCID, "m-ffffff", "RUNNING", keys=("ENG4",))
    ledger.attempt("m-ffffff", MCID, "ENG4", 1, "ADMITTED")
    ledger.run(f"{MCID}-ENG4-a1", "RUNNING")  # a mission feature's own run
    ledger.mission("lin-m-label2-1", "m-999999", "REJECTED")
    found = {(a.correlation_id, a.kind, a.ended) for a in ledger.record.all_linear_attempts()}
    assert found == {
        ("lin-ENG-1-1", "single", True),
        ("lin-ENG-2-1", "single", False),
        ("lin-ENG-3-2", "single", False),
        (MCID, "mission", False),
        ("lin-m-label2-1", "mission", True),
    }


# ---------------------------------------------------------------------------
# Reading, and refusing to read
# ---------------------------------------------------------------------------


def test_the_connection_is_read_only(ledger: Ledger) -> None:
    ledger.queue(CID)
    before = ledger.path.read_bytes()
    cx = connect_read_only(ledger.path)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            cx.execute("UPDATE work_queue SET status = 'DONE'")
    finally:
        cx.close()
    single(ledger)
    ledger.record.all_linear_attempts()
    assert ledger.path.read_bytes() == before


def test_missing_file_raises(tmp_path: Path) -> None:
    record = ForgeRecord(tmp_path / "absent.db")
    with pytest.raises(ForgeRecordUnavailable):
        record.outcome_for_single(CID)
    assert not (tmp_path / "absent.db").exists()


def test_schema_mismatch_raises(tmp_path: Path) -> None:
    without = SCHEMA.read_text().replace("j_commit            TEXT,", "")
    led = Ledger(tmp_path / "forge.db", schema=without)
    with pytest.raises(ForgeRecordUnavailable, match="publication_records"):
        led.record.outcome_for_single(CID)
    led.cx.close()


def test_not_a_database_raises(tmp_path: Path) -> None:
    path = tmp_path / "forge.db"
    path.write_text("not a database at all, just text " * 40)
    with pytest.raises(ForgeRecordUnavailable):
        ForgeRecord(path).all_linear_attempts()


def test_locked_record_raises(ledger: Ledger) -> None:
    holder = sqlite3.connect(ledger.path, isolation_level=None)
    holder.execute("PRAGMA locking_mode = EXCLUSIVE")
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(ForgeRecordUnavailable):
            single(ledger)
    finally:
        holder.execute("ROLLBACK")
        holder.close()


def test_record_without_mission_tables_has_no_missions(tmp_path: Path) -> None:
    text = SCHEMA.read_text()
    core = text[: text.index("CREATE TABLE missions")]
    led = Ledger(tmp_path / "forge.db", schema=core)
    led.queue(CID)
    assert led.record.outcome_for_mission(MCID).phase == fr.UNFILED
    assert [a.correlation_id for a in led.record.all_linear_attempts()] == [CID]
    led.cx.close()


# ---------------------------------------------------------------------------
# Codex review of 5c34f70: inline planning cards (R5), paused builds (R6),
# and when an attempt was filed (R1)
# ---------------------------------------------------------------------------


def door_event(ledger: Ledger, cid: str, stage: str, status: str, details: dict) -> None:
    """A row as Forge's inline door writes it (``driver.py`` 9512-9531)."""
    ledger.cx.execute(
        "INSERT INTO planning_run_events (correlation_id, stage_label, status, actor_identity, "
        "details_json, recorded_at) VALUES (?, ?, ?, 'planning-driver', ?, ?)",
        (cid, stage, status, json.dumps(details), NOW),
    )
    ledger.cx.commit()


def opened(key: str, request_id: str, outcome: str = "opened") -> dict:
    return {
        key: {
            "outcome": outcome,
            "request_id": request_id,
            "attempt_count": 0,
            "expected_approver": "a",
            "card": {"title": "The spec is ready"},
            "wait_seconds": 900,
        }
    }


DIGEST = ("feature-spec-digest-review", "digest_review")
AUTH = ("qa-pass-bars-auth-confirm", "auth_confirmation")


@pytest.mark.parametrize(
    ("stage", "key", "state"), [(*DIGEST, "FEATURE_SPEC"), (*AUTH, "FEATURE_PLAN")]
)
def test_a_planning_card_waiting_inline_is_an_open_plan_card(
    ledger: Ledger, stage: str, key: str, state: str
) -> None:
    ledger.run(CID, state)
    request = f"plan-{CID}:{stage}:0"
    door_event(ledger, CID, stage, "GATED", opened(key, request))
    assert [(c.kind, c.request_id) for c in ledger.record.open_cards_for([CID])] == [
        ("plan", request)
    ]
    assert ledger.record.outcome_for_single(CID).phase == fr.PLANNING
    # Re-opened after a restart: the same card, still open.
    door_event(ledger, CID, stage, "reopened", opened(key, request, "reopened"))
    assert [c.request_id for c in ledger.record.open_cards_for([CID])] == [request]
    # Any verdict closes it.
    door_event(
        ledger, CID, stage, "approved", {key: {"outcome": "approved", "request_id": request}}
    )
    assert ledger.record.open_cards_for([CID]) == []


def test_an_inline_card_left_open_by_a_run_that_ended_is_not_open(ledger: Ledger) -> None:
    ledger.run(CID, "FAILED", error="the daemon stopped")
    door_event(ledger, CID, DIGEST[0], "GATED", opened(DIGEST[1], "plan-x:d:0"))
    assert ledger.record.open_cards_for([CID]) == []


def test_a_paused_build_is_an_open_card(ledger: Ledger) -> None:
    ledger.queue(CID, "ADMITTED")
    ledger.build(CID, "build-1", "PAUSED")
    ledger.cx.execute(
        "UPDATE builds SET pending_approval_request_id = 'build-1:autobuild:0' "
        "WHERE build_id = 'build-1'"
    )
    ledger.cx.commit()
    [card] = ledger.record.open_cards_for([CID])
    assert (card.kind, card.correlation_id, card.request_id, card.build_id) == (
        "build",
        CID,
        "build-1:autobuild:0",
        "build-1",
    )
    # Answered (in Slack or anywhere): Forge clears the pause.
    ledger.cx.execute(
        "UPDATE builds SET status = 'RUNNING', pending_approval_request_id = NULL "
        "WHERE build_id = 'build-1'"
    )
    ledger.cx.commit()
    assert ledger.record.open_cards_for([CID]) == []


def test_a_mission_features_paused_build_is_an_open_card(ledger: Ledger) -> None:
    ledger.mission(MCID, "m-1", "RUNNING", keys=("ENG4",))
    ledger.attempt("m-1", MCID, "ENG4", 1, "ADMITTED")
    ledger.build(f"{MCID}-ENG4-a1", "build-4", "PAUSED")
    ledger.cx.execute("UPDATE builds SET pending_approval_request_id = 'build-4:autobuild:0'")
    ledger.cx.commit()
    [card] = ledger.record.open_cards_for([MCID])
    assert (card.kind, card.correlation_id, card.build_id) == (
        "build",
        f"{MCID}-ENG4-a1",
        "build-4",
    )


def test_recorded_attempts_say_when_they_were_filed(ledger: Ledger) -> None:
    ledger.queue("lin-ENG-1-1", "WITHDRAWN", "withdrawn")
    ledger.mission(MCID, "m-1", "REJECTED")
    filed = {a.correlation_id: a.filed_at for a in ledger.record.all_linear_attempts()}
    assert filed == {"lin-ENG-1-1": NOW, MCID: NOW}


def test_on_main_before_the_merge_report_is_watched_not_ended(ledger: Ledger) -> None:
    """R11: Forge writes "published, deployment pending" before its report."""
    build_id = _built(ledger)
    ledger.offer(build_id, CID)
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "published, deployment pending", j_commit="j0456")
    out = single(ledger)
    assert (out.phase, out.ended, out.j_commit) == (fr.ON_MAIN_REPORT_PENDING, False, "j0456")
    ledger.report(build_id, "FAILED", "merged-deploy-failed", "the deploy step failed")
    out = single(ledger)
    assert (out.phase, out.ended) == (fr.ON_MAIN_DEPLOY_FAILED, True)


def test_linear_errors_are_refusals_only_when_linear_says_so() -> None:
    """R9: only "not found" or "invalid input" is a refusal; the rest is an outage."""
    import asyncio

    import httpx

    from jarvis.infrastructure.linear.client import LinearClient, LinearError, LinearRefused

    def answer(status: int, errors: list[dict]) -> type[Exception]:
        client = LinearClient(
            "fake-linear-key-for-tests-only-7f3a",
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, json={"data": None, "errors": errors})
            ),
        )
        try:
            asyncio.run(client.execute("query DoorX { x }"))
        except LinearError as exc:
            return type(exc)
        raise AssertionError("no error")

    assert answer(200, [{"message": "Entity not found: Issue"}]) is LinearRefused
    assert answer(200, [{"message": "x", "extensions": {"code": "INVALID_INPUT"}}]) is LinearRefused
    assert answer(400, [{"message": "x", "extensions": {"type": "invalid input"}}]) is LinearRefused
    internal = [{"message": "boom", "extensions": {"code": "INTERNAL_SERVER_ERROR"}}]
    assert answer(200, internal) is LinearError
    assert answer(200, [{"message": "something else"}]) is LinearError
    assert answer(500, [{"message": "Entity not found"}]) is LinearError


def test_the_target_repository_is_read_from_the_record(ledger: Ledger) -> None:
    # Design section 11.4 (Codex review R2): the update's repository comes
    # from Forge's record when the door's own record is lost.
    ledger.run(CID, "FEATURE_PLAN")
    ledger.cx.execute(
        "UPDATE planning_runs SET target_repo = 'example-org/from-run' WHERE correlation_id = ?",
        (CID,),
    )
    ledger.cx.commit()
    assert single(ledger).target_repo == "example-org/from-run"
    ledger.queue(CID, "ADMITTED")
    ledger.cx.execute(
        "UPDATE work_queue SET target_repo = 'example-org/from-queue' WHERE correlation_id = ?",
        (CID,),
    )
    ledger.cx.commit()
    assert single(ledger).target_repo == "example-org/from-queue"
    ledger.mission(MCID, "m-1", "RUNNING")
    assert ledger.record.outcome_for_mission(MCID).target_repo == "repo"


# ---------------------------------------------------------------------------
# Every build on main (design section 11.8)
# ---------------------------------------------------------------------------

ORG_REPO = "example-org/notes-app"


def _merged(ledger: Ledger, cid: str, build_id: str, *, report: bool = True, **kw: object) -> None:
    ledger.build(cid, build_id, "COMPLETE", repo=ORG_REPO, **kw)  # type: ignore[arg-type]
    ledger.decide(build_id, "approve")
    ledger.publication(build_id, "published, deployment pending", j_commit=f"j-{build_id}")
    if report:
        ledger.report(build_id, "PASSED", "merged-and-running", "deployed")


def test_merges_on_main_lists_a_single_build_with_its_title(ledger: Ledger) -> None:
    request = "\n  Explain the checks  in the README\nMore."
    ledger.run("slack-1", "BUILD_QUEUED", request_text=request)
    _merged(ledger, "slack-1", "build-a", feature_id="FEAT-9163")
    (found,) = ledger.record.merges_on_main()
    assert found == fr.MergeOnMain(
        build_id="build-a",
        correlation_id="slack-1",
        feature_id="FEAT-9163",
        repo=ORG_REPO,
        title="Explain the checks in the README",
        j_commit="j-build-a",
        report=True,
        report_result="merged-and-running",
    )
    assert found.ready and not found.is_mission


def test_a_merge_without_a_planning_request_is_named_by_its_feature_id(ledger: Ledger) -> None:
    _merged(ledger, "cli-7", "build-b", feature_id="FEAT-77")
    (found,) = ledger.record.merges_on_main()
    assert found.title == "FEAT-77"


def test_a_merge_before_its_report_is_listed_but_not_ready(ledger: Ledger) -> None:
    _merged(ledger, "slack-1", "build-a", report=False)
    (found,) = ledger.record.merges_on_main()
    assert not found.report and not found.ready


def test_a_failed_deploy_is_carried(ledger: Ledger) -> None:
    ledger.build("slack-1", "build-a", "COMPLETE", repo=ORG_REPO)
    ledger.decide("build-a", "approve")
    ledger.publication("build-a", "published, deployment pending")
    ledger.report("build-a", "FAILED", "merged-deploy-failed", "the health check timed out")
    (found,) = ledger.record.merges_on_main()
    assert found.ready
    assert found.deploy_failed == "the health check timed out"


def test_builds_not_on_main_are_not_listed(ledger: Ledger) -> None:
    ledger.build("slack-1", "build-pending", "COMPLETE")
    ledger.publication("build-pending", "publication pending")
    ledger.build("slack-2", "build-other", "COMPLETE", target="release")
    ledger.publication("build-other", "published, deployment pending", target="main")
    ledger.build("slack-3", "build-none", "COMPLETE")
    assert ledger.record.merges_on_main() == []


def test_a_mission_lists_its_merge_build_once_and_never_its_parts(ledger: Ledger) -> None:
    mcid = "slack-mission-1"
    ledger.mission(mcid, "m-1", "MERGING", keys=("A1", "A2", "A3"), title="Dark mode")
    for key, status in (("A1", "LANDED"), ("A2", "LANDED"), ("A3", "FAILED")):
        ledger.attempt("m-1", mcid, key, 1, status)
        part = f"build-part-{key}"
        ledger.build(
            f"{mcid}-{key}-a1",
            part,
            "COMPLETE",
            mission_id="m-1",
            role="feature",
            target="mission/m-1",
        )
        ledger.publication(part, "published to the mission branch", target="mission/m-1")
    # Even a part whose record used an on-main word is never listed.
    ledger.cx.execute(
        "UPDATE publication_records SET result = 'published, deployment pending' "
        "WHERE build_id = 'build-part-A1'"
    )
    ledger.cx.commit()
    ledger.build(
        mcid, "build-merge", "COMPLETE", mission_id="m-1", role="mission-merge", repo=ORG_REPO
    )
    ledger.decide("build-merge", "approve")
    ledger.publication("build-merge", "merged into the remote and running")
    (found,) = ledger.record.merges_on_main()
    assert found.build_id == "build-merge"
    assert found.is_mission and found.mission_id == "m-1"
    assert found.title == "Dark mode"
    assert found.landed_keys == ("A1", "A2")
    assert found.not_landed_keys == ("A3",)
    assert found.mission_status == "MERGING" and not found.ready
    ledger.cx.execute("UPDATE missions SET status = 'MERGED' WHERE id = 'm-1'")
    ledger.cx.commit()
    (found,) = ledger.record.merges_on_main()
    assert found.ready


def test_merges_on_main_on_an_unreadable_record_raises(tmp_path: Path) -> None:
    with pytest.raises(ForgeRecordUnavailable):
        ForgeRecord(tmp_path / "missing.db").merges_on_main()
