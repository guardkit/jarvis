"""A project update after every merge, whatever its origin (design section 11.8).

The same fake Linear, captured bus and fake of Forge's record as the other
door tests; the builds on main are given as the reader's own
:class:`~jarvis.infrastructure.linear.forge_record.MergeOnMain`. All names,
ids and repositories are made up.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.linear import forge_record as fr

from .test_linear_projects import OTHER, REPO, Harness, lose_record, on_main, plain, slot

MERGE_ID = "build-FEAT-9163-20261019101500"


def merge(
    build_id: str = MERGE_ID,
    *,
    cid: str = "slack-1234",
    repo: str | None = REPO,
    title: str = "Explain the security checks in the README",
    report: bool = True,
    deploy_failed: str = "",
    **kw: Any,
) -> fr.MergeOnMain:
    return fr.MergeOnMain(
        build_id=build_id,
        correlation_id=cid,
        feature_id=kw.pop("feature_id", "FEAT-9163"),
        repo=repo,
        title=title,
        j_commit=kw.pop("j_commit", "d00dfeed"),
        report=report,
        report_result=kw.pop("report_result", "merged-and-running" if report else None),
        deploy_failed=deploy_failed,
        **kw,
    )


def mission_merge(status: str = "MERGED") -> fr.MergeOnMain:
    return merge(
        "build-FEAT-M1-20261019110000",
        cid="slack-mission-77",
        title="Dark mode everywhere",
        feature_id="FEAT-M1",
        report=False,  # a mission waits for MERGED, not for the report
        mission_id="m-77",
        mission_status=status,
        landed_keys=("A1", "A2"),
        not_landed_keys=("A3",),
        part_sentences=(("A1", "Add a dark mode toggle."), ("A3", "Theme the charts.")),
    )


@pytest.fixture
async def h(tmp_path: Path) -> Harness:
    """A door whose merge baseline is taken (nothing on main yet) and whose
    repository has one active project, ``Notes``."""
    harness = Harness(tmp_path)
    harness.notes = harness.linear.project("Notes", f"https://github.com/{REPO}")
    await harness.poll()
    assert harness.store.merge_baseline() is not None
    return harness


def merge_cost(h: Harness, build_id: str, value: str) -> None:
    h.summary(merges={build_id: slot(value)})


# ---------------------------------------------------------------------------
# The baseline
# ---------------------------------------------------------------------------


async def test_the_first_run_records_every_merge_already_on_main_and_posts_none(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path)
    notes = h.linear.project("Notes", f"https://github.com/{REPO}")
    h.summary()
    h.attempts.merges = [merge("build-old-1"), merge("build-old-2", cid="cli-9")]
    with capture_logs() as logs:
        await h.poll(3)
    assert h.linear.updates_on(notes) == []
    assert h.store.merge_state("build-old-1") == ("seen", None)
    assert h.store.merge_state("build-old-2") == ("seen", None)
    (taken,) = [e for e in logs if e["event"] == "linear_door_merge_baseline_taken"]
    assert taken["merges_on_main"] == 2
    assert "no project update" in taken["gap"]


async def test_a_failed_read_of_forges_record_takes_no_baseline(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    h.linear.project("Notes", f"https://github.com/{REPO}")
    await h.poll()  # the door's own record is rebuilt first (once per start)
    # As if this check had never run on this record.
    h.store._db.execute("DELETE FROM marks WHERE name = 'merge-baseline'")
    h.store._db.commit()
    h.attempts.merges = [merge("build-old-1")]
    h.attempts.unreadable = True
    await h.poll()
    assert h.store.merge_baseline() is None
    assert h.store.merge_state("build-old-1") is None
    h.attempts.unreadable = False
    await h.poll()
    assert h.store.merge_state("build-old-1") == ("seen", None)


# ---------------------------------------------------------------------------
# A single merge
# ---------------------------------------------------------------------------


async def test_a_new_merge_posts_once_after_its_report_and_not_before(h: Harness) -> None:
    merge_cost(h, MERGE_ID, "$1.10")
    h.attempts.merges = [merge(report=False, report_result=None)]
    await h.poll(2)
    assert h.linear.updates_on(h.notes) == []  # waits for the merge report
    assert h.store.merge_state(MERGE_ID) == ("pending", None)
    h.attempts.merges = [merge()]
    await h.poll()
    h.restart()
    await h.poll(2)
    (update,) = h.linear.updates_on(h.notes)
    assert update.health == "atRisk"
    assert plain(update.body) == "\n".join(
        [
            "**Delivered**",
            "- FEAT-9163 Explain the security checks in the README",
            "Merged into the main branch as `d00dfeed`.",
            "",
            "**Open**",
            "In Linear: no issues left open in this project.",
            "In the factory: 3 open issues, 1 being built.",
            "",
            "**Cost** (nominal US dollars, as the dashboard shows them)",
            "- This merge: $1.10 nominal",
            "- This week: $7.05 nominal (part estimated)",
            "- Project total: $41.20 nominal",
            "",
            "Project health: at risk (from the dashboard).",
        ]
    )
    assert h.store.merge_state(MERGE_ID) == ("posted", None)


async def test_a_merge_with_no_planning_request_is_named_by_its_feature_id(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [merge(title="FEAT-9163")]
    await h.poll()
    (update,) = h.linear.updates_on(h.notes)
    assert plain(update.body).startswith("**Delivered**\n- FEAT-9163\nMerged into the main branch")


async def test_a_merge_whose_dashboard_cost_is_missing_says_not_available(h: Harness) -> None:
    h.summary()  # no merges entry for this build
    h.attempts.merges = [merge()]
    await h.poll()
    (update,) = h.linear.updates_on(h.notes)
    assert "- This merge: not available" in update.body
    assert "- This week: $7.05 nominal (part estimated)" in update.body


async def test_a_failed_deploy_is_off_track_whatever_the_dashboard_says(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [merge(deploy_failed="the health check timed out")]
    await h.poll()
    (update,) = h.linear.updates_on(h.notes)
    assert update.health == "offTrack"
    assert "The deploy after this merge failed: the health check timed out." in update.body
    assert "Project health: off track (the deploy after this merge failed)." in update.body


async def test_each_merge_gets_its_own_update(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [merge("build-a"), merge("build-b", cid="cli-2", j_commit="cafe0001")]
    await h.poll(2)
    assert len(h.linear.updates_on(h.notes)) == 2
    assert h.linear.calls.count("DoorProjectUpdateCreate") == 2


# ---------------------------------------------------------------------------
# A mission
# ---------------------------------------------------------------------------


async def test_a_mission_merge_posts_once_on_merged(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [mission_merge("MERGING")]
    await h.poll(2)
    assert h.linear.updates_on(h.notes) == []
    h.attempts.merges = [mission_merge("MERGED")]
    await h.poll(2)
    (update,) = h.linear.updates_on(h.notes)
    assert update.health == "offTrack"  # A3 did not land
    body = plain(update.body)
    assert body.startswith(
        "\n".join(
            [
                "**Delivered**",
                "The mission “Dark mode everywhere” merged into the main branch as `d00dfeed`.",
                "Landed:",
                "- A1 — Add a dark mode toggle.",
                "- A2",
                "Did not land:",
                "- A3 — Theme the charts.",
            ]
        )
    )
    assert "Project health: off track (part of the mission did not land)." in body


# ---------------------------------------------------------------------------
# No double posting, restarts and lost answers
# ---------------------------------------------------------------------------


async def test_the_doors_own_merge_is_posted_once_by_its_own_path(h: Harness) -> None:
    h.summary()
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = h.notes.id
    await h.poll()
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    h.attempts.merges = [merge("build-lin-1", cid="lin-ENG-1-1")]
    await h.poll(3)
    (update,) = h.linear.updates_on(h.notes)
    assert "- ENG-1 Add a dark mode" in update.body  # the 11.4 update
    assert h.store.merge_state("build-lin-1") == ("seen", None)


async def test_a_lost_answer_is_found_and_never_posted_twice(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [merge()]
    h.linear.lose_response["DoorProjectUpdateCreate"] = 1
    await h.poll()  # made on Notes, its answer lost: still pending
    assert h.store.merge_state(MERGE_ID) == ("pending", None)
    h.restart()
    await h.poll(2)
    assert len(h.linear.updates_on(h.notes)) == 1
    assert h.linear.calls.count("DoorProjectUpdateCreate") == 1
    assert h.store.merge_state(MERGE_ID) == ("posted", None)


async def test_an_unconfirmed_update_is_retried_on_its_first_project(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [merge()]
    h.linear.fail_next["DoorProjectUpdateCreate"] = [_outage()]
    await h.poll()  # begun on Notes; Linear never took it
    h.notes.links.clear()  # the repository's link moves to another project
    newer = h.linear.project("Notes v2", f"https://github.com/{REPO}")
    await h.poll()
    assert len(h.linear.updates_on(h.notes)) == 1
    assert h.linear.updates_on(newer) == []


def _outage() -> Any:
    from .fake_linear import server_error

    return server_error()


async def test_a_lost_record_takes_a_new_baseline_and_backfills_nothing(h: Harness) -> None:
    h.summary()
    h.attempts.merges = [merge("build-a")]
    await h.poll()
    assert len(h.linear.updates_on(h.notes)) == 1
    lose_record(h)
    h.attempts.merges.append(merge("build-b", cid="cli-2"))  # merged while it was lost
    with capture_logs() as logs:
        await h.poll(2)
    assert len(h.linear.updates_on(h.notes)) == 1  # nothing for build-b
    assert h.store.merge_state("build-b") == ("seen", None)
    (taken,) = [e for e in logs if e["event"] == "linear_door_merge_baseline_taken"]
    assert taken["merges_on_main"] == 2
    h.attempts.merges.append(merge("build-c", cid="cli-3"))
    await h.poll()
    assert len(h.linear.updates_on(h.notes)) == 2
    assert h.store.merge_state("build-c") == ("posted", None)


# ---------------------------------------------------------------------------
# Where it goes, and when it goes nowhere
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("change", ["archived", "completed", "trashed"])
async def test_an_inactive_project_is_skipped(h: Harness, change: str) -> None:
    if change == "completed":
        h.notes.status = "completed"
    else:
        setattr(h.notes, change, True)
    h.attempts.merges = [merge()]
    with capture_logs() as logs:
        await h.poll(2)
    assert h.linear.project_updates == []
    state, why = h.store.merge_state(MERGE_ID) or ("", "")
    assert state == "skipped" and "no active project" in str(why)
    (skipped,) = [e for e in logs if e["event"] == "linear_door_merge_update_skipped"]
    assert skipped["build_id"] == MERGE_ID


async def test_a_project_closed_after_the_update_was_begun_gets_nothing_new(h: Harness) -> None:
    h.attempts.merges = [merge()]
    h.linear.fail_next["DoorProjectUpdateCreate"] = [_outage()]
    await h.poll()
    h.notes.archived = True
    await h.poll(2)
    assert h.linear.project_updates == []
    assert h.linear.calls.count("DoorProjectUpdateCreate") == 1
    state, why = h.store.merge_state(MERGE_ID) or ("", "")
    assert state == "skipped" and "no longer active" in str(why)


@pytest.mark.parametrize(
    ("repo", "why"),
    [
        (OTHER, "no active project"),
        (None, "not known"),
        ("notes-app", "fits more than one"),
    ],
)
async def test_no_or_ambiguous_project_is_skipped(h: Harness, repo: str | None, why: str) -> None:
    h.linear.project("Notes elsewhere", "https://github.com/someone-else/notes-app")
    h.attempts.merges = [merge(repo=repo)]
    await h.poll()
    assert h.linear.project_updates == []
    state, reason = h.store.merge_state(MERGE_ID) or ("", "")
    assert state == "skipped" and why in str(reason)


async def test_a_merge_waits_while_the_projects_cannot_be_read(h: Harness) -> None:
    from .fake_linear import server_error

    h.attempts.merges = [merge()]
    h.linear.fail_next["DoorProjects"] = [server_error()]
    await h.poll()
    assert h.store.merge_state(MERGE_ID) == ("pending", None)
    await h.poll()
    assert len(h.linear.updates_on(h.notes)) == 1


async def test_an_unreadable_record_changes_nothing_that_poll(h: Harness) -> None:
    h.attempts.merges = [merge()]
    h.attempts.unreadable = True
    await h.poll()
    assert h.store.merge_state(MERGE_ID) is None
    h.attempts.unreadable = False
    await h.poll()
    assert len(h.linear.updates_on(h.notes)) == 1


# ---------------------------------------------------------------------------
# Through Forge's real reader (the copied schema)
# ---------------------------------------------------------------------------

_SCHEMA = Path(__file__).parents[3] / "infrastructure" / "linear" / "forge_schema_dbd40c7e.sql"


async def test_a_merge_read_from_forges_record_is_posted_once(h: Harness) -> None:
    import sqlite3

    from jarvis.infrastructure.linear.report import ForgeAttempts

    path = h.tmp_path / "forge.db"
    cx = sqlite3.connect(path)
    cx.executescript(_SCHEMA.read_text())
    now = "2026-10-19T10:00:00+00:00"

    def merged(build_id: str, cid: str, request: str) -> None:
        cx.execute(
            "INSERT INTO planning_runs (correlation_id, state, originating_user, "
            "expected_approver, request_text, triggered_by, queued_at, target_repo) "
            "VALUES (?, 'BUILD_QUEUED', 'u', 'a', ?, 'jarvis', ?, ?)",
            (cid, request, now, REPO),
        )
        cx.execute(
            "INSERT INTO builds (build_id, feature_id, repo, branch, feature_yaml_path, status, "
            "triggered_by, correlation_id, queued_at, target_branch) "
            "VALUES (?, 'FEAT-9163', ?, 'b', 'f.yaml', 'COMPLETE', 'jarvis', ?, ?, 'main')",
            (build_id, REPO, cid, now),
        )
        cx.execute(
            "INSERT INTO publication_records (build_id, target_branch, j_commit, result) "
            "VALUES (?, 'main', 'd00dfeed', 'merged into the remote and running')",
            (build_id,),
        )
        cx.execute(
            "INSERT INTO stage_log (build_id, stage_label, target_kind, target_identifier, "
            "status, started_at, completed_at, duration_secs, details_json) VALUES "
            "(?, 'merge-deploy', 'local_tool', 'merge_deploy_executor', 'PASSED', ?, ?, 0.0, ?)",
            (build_id, now, now, '{"result": "merged-and-running", "detail": "deployed"}'),
        )
        cx.commit()

    real = ForgeAttempts(fr.ForgeRecord(path, timeout=0.2))
    h.attempts.merges_on_main = real.merges_on_main  # type: ignore[method-assign]
    merged("build-old", "slack-old", "Something merged before the door looked")
    await h.poll()  # the baseline was taken empty in the fixture: this one is new
    assert h.store.merge_state("build-old") == ("posted", None)
    merged("build-new", "slack-new", "Explain the security checks in the README\nDetails.")
    await h.poll(2)
    updates = h.linear.updates_on(h.notes)
    assert len(updates) == 2
    assert "- FEAT-9163 Explain the security checks in the README" in updates[1].body
    cx.close()


async def test_a_merge_pending_over_a_day_is_logged_once(h: Harness) -> None:
    h.attempts.merges = [merge(report=False, report_result=None)]
    await h.poll()
    assert h.store.merge_state(MERGE_ID) == ("pending", None)
    with capture_logs() as logs:
        await h.poll()
    assert not [e for e in logs if e["event"] == "linear_door_merge_pending_long"]
    h.store._db.execute(
        "UPDATE merges SET recorded_at = '2026-01-01T00:00:00+00:00' WHERE build_id = ?",
        (MERGE_ID,),
    )
    h.store._db.commit()
    with capture_logs() as logs:
        await h.poll(3)
    (noted,) = [e for e in logs if e["event"] == "linear_door_merge_pending_long"]
    assert noted["build_id"] == MERGE_ID
    assert noted["waiting_for"] == "its merge report"
    assert h.store.merge_state(MERGE_ID) == ("pending", None)
