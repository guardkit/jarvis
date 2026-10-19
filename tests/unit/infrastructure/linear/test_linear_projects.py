"""Linear projects, the dashboard's link and project updates (design section 11).

A fake Linear, a captured bus and a fake of Forge's record, as in the other
door tests. All names, ids and repositories are made up.
"""

from __future__ import annotations

import json
import os
import re
import stat
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from jarvis.infrastructure.linear import forge_record as fr
from jarvis.infrastructure.linear.client import LinearIssue, LinearLabel, LinearProject, LinearState
from jarvis.infrastructure.linear.door import DoorSettings, LinearDoor, RecordedAttempt
from jarvis.infrastructure.linear.mapping import choose_repo, mission_prefix
from jarvis.infrastructure.linear.projects import (
    PROJECTS_FILE,
    ProjectMap,
    github_repo,
    registered_repositories,
    write_projects_file,
)
from jarvis.infrastructure.linear.store import DoorStore
from jarvis.infrastructure.linear.updates import (
    Delivered,
    Summary,
    cost_words,
    read_summary,
    update_health,
)

from .fake_linear import (
    CapturedAnswers,
    CapturedBus,
    FakeAttempts,
    FakeFeed,
    FakeIntake,
    FakeLinear,
    refused,
    server_error,
)

OWNER = "U0OWNER0001"
REPO = "example-org/notes-app"
OTHER = "example-org/other-app"
_REF = re.compile(r"\n\n_factory note [0-9a-f]{12}_$")


def plain(body: str) -> str:
    return _REF.sub("", body)


def forge_yaml(path: Path, *repos: str) -> Path:
    lines = ["planning:", "  sandboxes:"]
    for repo in repos:
        lines += [f"    {repo}:", "      name: shared-sandbox", '      runner_url: "${RUNNER}"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class Harness:
    def __init__(self, tmp_path: Path, *, registered: tuple[str, ...] = ()) -> None:
        self.tmp_path = tmp_path
        self.linear = FakeLinear()
        self.bus = CapturedBus()
        self.attempts = FakeAttempts()
        self.intake = FakeIntake()
        self.feed = FakeFeed()
        self.state_dir = tmp_path / "state"
        self.forge_settings = forge_yaml(tmp_path / "forge.yaml", *registered)
        self.summary_path = tmp_path / "dashboard" / "project-summaries.json"
        self.default_repo: str | None = "example-org/default-app"
        self.client = self.linear.client()
        self.door = self._door()

    def _door(self) -> LinearDoor:
        self.store = DoorStore(self.state_dir / "linear-door.sqlite3")
        return LinearDoor(
            client=self.client,
            publisher=self.bus,
            store=self.store,
            settings=DoorSettings(
                team="ENG",
                owner_identity=OWNER,
                default_repo=self.default_repo,
                forge_settings=self.forge_settings,
                dashboard_summary=self.summary_path,
                state_dir=self.state_dir,
            ),
            attempts=self.attempts,
            intake=self.intake,
            feed=self.feed,
            answers=CapturedAnswers(),
        )

    def restart(self) -> None:
        self.store.close()
        self.door = self._door()

    async def poll(self, times: int = 1) -> None:
        for _ in range(times):
            await self.door.poll_once()

    def factory(self, issue: Any) -> list[str]:
        return [
            plain(c) for c in self.linear.comments_on(issue) if "Sent to the factory as" not in c
        ]

    def summary(self, **overrides: Any) -> None:
        now = datetime.now(UTC)
        data: dict[str, Any] = {
            "version": 1,
            "written_at": now.isoformat(),
            "forge": {
                "last_success_at": now.isoformat(),
                "valid_until": (now + timedelta(minutes=5)).isoformat(),
                "stale": False,
            },
            "cost": {"read_at": now.isoformat(), "state": "fresh", "stale_after_seconds": 600},
            "projects": {
                REPO: {
                    "delivered_total": 4,
                    "delivered_7d": 2,
                    "in_progress": 1,
                    "open_issues_total": 3,
                    "open_issues_words": "3 open issues, 1 being built",
                    "health": "at_risk",
                    "spend_total": slot("$41.20"),
                    "spend_week": slot("$7.05", estimated=True),
                }
            },
            "attempts": {"lin-ENG-1-1": slot("$2.20")},
        }
        for dotted, value in overrides.items():
            target = data
            *path, last = dotted.split("__")
            for part in path:
                target = target[part]
            if value is _DELETE:
                target.pop(last, None)
            else:
                target[last] = value
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(json.dumps(data), encoding="utf-8")


_DELETE = object()


def slot(value: str, **kw: Any) -> dict[str, Any]:
    data = {
        "state": "measured",
        "value": value,
        "label": "",
        "reason": "",
        "amount_usd": float(value.strip("$")),
        "estimated": False,
        "unpriced_calls": 0,
        "stale": False,
        "stale_text": "",
        "price_label": "LiteLLM prices, 1 October 2026",
    }
    data.update(kw)
    return data


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


# ---------------------------------------------------------------------------
# Links and registered repositories
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "repo"),
    [
        ("https://github.com/example-org/notes-app", "example-org/notes-app"),
        ("https://github.com/example-org/notes-app/", "example-org/notes-app"),
        ("https://github.com/example-org/notes-app.git", "example-org/notes-app"),
        ("https://GitHub.com/example-org/notes-app", "example-org/notes-app"),
        ("http://github.com/example-org/notes-app", None),
        ("https://github.com/example-org", None),
        ("https://github.com/example-org/notes-app/issues", None),
        ("https://github.com/example-org/notes-app?tab=readme", None),
        ("https://gitlab.com/example-org/notes-app", None),
        ("https://www.example.com/", None),
    ],
)
def test_github_link(url: str, repo: str | None) -> None:
    assert github_repo(url) == repo


def test_registered_repositories(tmp_path: Path) -> None:
    assert registered_repositories(None) is None
    assert registered_repositories(tmp_path / "missing.yaml") is None
    bad = tmp_path / "bad.yaml"
    bad.write_text("planning: [unclosed\n", encoding="utf-8")
    assert registered_repositories(bad) is None
    listy = tmp_path / "list.yaml"
    listy.write_text("- a\n- b\n", encoding="utf-8")
    assert registered_repositories(listy) is None
    empty = tmp_path / "empty.yaml"
    empty.write_text("planning:\n  target_repo_paths: {}\n", encoding="utf-8")
    assert registered_repositories(empty) == []
    good = forge_yaml(tmp_path / "forge.yaml", REPO, OTHER)
    assert registered_repositories(good) == [REPO, OTHER]


def test_door_config_reads_the_project_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.linear.door import door_config

    monkeypatch.setenv("JARVIS_LINEAR_API_KEY", "fake-linear-key-for-tests-only-7f3a")
    monkeypatch.setenv("JARVIS_LINEAR_TEAM", "ENG")
    monkeypatch.setenv("JARVIS_LINEAR_OWNER_IDENTITY", OWNER)
    monkeypatch.setenv("JARVIS_LINEAR_STATE_DIR", str(tmp_path))
    resolved = door_config(JarvisConfig())
    assert not isinstance(resolved, str)
    assert resolved.settings.forge_settings == Path("/etc/forge/forge.yaml")
    assert resolved.settings.dashboard_summary is None
    assert resolved.settings.state_dir == tmp_path

    monkeypatch.setenv("JARVIS_LINEAR_FORGE_SETTINGS", "")
    monkeypatch.setenv("JARVIS_LINEAR_DASHBOARD_SUMMARY", " ")
    resolved = door_config(JarvisConfig())
    assert not isinstance(resolved, str)
    assert resolved.settings.forge_settings is None
    assert resolved.settings.dashboard_summary is None

    monkeypatch.setenv("JARVIS_LINEAR_FORGE_SETTINGS", "/forge-settings/forge.yaml")
    monkeypatch.setenv("JARVIS_LINEAR_DASHBOARD_SUMMARY", "/dashboard/project-summaries.json")
    resolved = door_config(JarvisConfig())
    assert not isinstance(resolved, str)
    assert resolved.settings.forge_settings == Path("/forge-settings/forge.yaml")
    assert resolved.settings.dashboard_summary == Path("/dashboard/project-summaries.json")


# ---------------------------------------------------------------------------
# The decision table (11.2)
# ---------------------------------------------------------------------------


def _project(pid: str, name: str, *urls: str) -> LinearProject:
    return LinearProject(pid, name, f"https://linear.app/x/{pid}", False, False, urls)


def _issue(*labels: str, project_id: str | None = None) -> LinearIssue:
    return LinearIssue(
        id="i-1",
        identifier="ENG-1",
        title="t",
        description="",
        url="",
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        state=LinearState("s", "Todo", "unstarted"),
        labels=tuple(LinearLabel(f"l{n}", name) for n, name in enumerate(labels)),
        project_id=project_id,
    )


MAP = ProjectMap(
    [
        _project("p-one", "Notes", f"https://github.com/{REPO}", "https://example.com/docs"),
        _project("p-none", "Ideas", "https://example.com/board"),
        _project("p-two", "Both", f"https://github.com/{OTHER}", "https://github.com/x/y"),
        _project("p-a", "First", "https://github.com/example-org/shared"),
        _project("p-b", "Second", "https://github.com/example-org/shared.git"),
    ],
    [REPO],
)


def test_decision_table() -> None:
    dflt = "example-org/default-app"
    # A repo label wins, whatever the project says.
    assert choose_repo(_issue("repo: a/b", project_id="p-none"), dflt, MAP).repo == "a/b"
    # Two different repo labels: refused.
    two = choose_repo(_issue("repo: a/b", "repo: c/d", project_id="p-one"), dflt, MAP)
    assert two.repo is None and "more than one repo label" in (two.problem or "")
    # A project that maps to exactly one repository.
    assert choose_repo(_issue(project_id="p-one"), dflt, MAP).repo == REPO
    # A project that maps to nothing, or a conflict: refused, never the default.
    for pid, words in [
        ("p-none", "“Ideas” has no GitHub link"),
        ("p-two", "“Both” links to two repositories"),
        ("p-a", "another project links to the same repository"),
        ("p-b", "another project links to the same repository"),
    ]:
        choice = choose_repo(_issue(project_id=pid), dflt, MAP)
        assert choice.repo is None and not choice.wait
        assert words in (choice.problem or ""), choice.problem
    # No label and no project: the default, else the existing comment.
    assert choose_repo(_issue(), dflt, MAP).repo == dflt
    missing = choose_repo(_issue(), None, MAP)
    assert missing.repo is None and "do not know which repository" in (missing.problem or "")
    # A project a whole read did not include: refused (C3). No read: wait, silently.
    unseen = choose_repo(_issue(project_id="p-unseen"), dflt, MAP)
    assert not unseen.wait and "cannot see its project" in (unseen.problem or "")
    assert choose_repo(_issue(project_id="p-one"), dflt, None).wait
    assert choose_repo(_issue(), dflt, None).repo == dflt


async def test_an_issue_in_a_mapped_project_goes_to_its_repository(h: Harness) -> None:
    project = h.linear.project("Notes", f"https://github.com/{REPO}")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = project.id
    await h.poll()
    assert h.bus.payloads()[0]["target_repo"] == REPO


async def test_an_issue_in_an_unlinked_project_is_refused_once_and_stays(h: Harness) -> None:
    project = h.linear.project("Ideas")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = project.id
    await h.poll(2)
    assert h.bus.published == []
    (only,) = h.factory(issue)
    assert "its project “Ideas” has no GitHub link" in only
    assert h.linear.state_name(issue) == "Todo"
    # Fixed by hand: sent on the next poll.
    project.links.append(_link(REPO))
    await h.poll()
    assert h.bus.payloads()[0]["target_repo"] == REPO


def _link(repo: str) -> Any:
    from .fake_linear import FakeLink

    return FakeLink(str(uuid.uuid4()), f"https://github.com/{repo}", "GitHub")


async def test_a_mission_member_in_a_conflicting_project_holds_the_mission(h: Harness) -> None:
    h.linear.project("First", f"https://github.com/{REPO}")
    second = h.linear.project("Second", f"https://github.com/{REPO}")
    label = h.linear.label("mission: Sharing")
    a = h.linear.issue("Share a note", labels=[label])
    b = h.linear.issue("Revoke a share", labels=[label])
    a.project_id = second.id
    await h.poll()
    assert h.bus.published == []
    assert "another project links to the same repository" in h.factory(a)[0]
    assert h.factory(b) == []


async def test_mission_members_decided_by_their_projects_must_agree(h: Harness) -> None:
    notes = h.linear.project("Notes", f"https://github.com/{REPO}")
    label = h.linear.label("mission: Sharing")
    a = h.linear.issue("Share a note", labels=[label])
    b = h.linear.issue("Revoke a share", labels=[label])
    a.project_id = b.project_id = notes.id
    await h.poll()
    assert h.bus.payloads()[0]["target_repo"] == REPO
    assert h.bus.payloads()[0]["correlation_id"] == f"{mission_prefix(label)}1"


async def test_a_failed_projects_read_holds_only_issues_in_a_project(h: Harness) -> None:
    notes = h.linear.project("Notes", f"https://github.com/{REPO}")
    in_project = h.linear.issue("In a project")
    in_project.project_id = notes.id
    loose = h.linear.issue("No project")
    h.linear.fail_next["DoorProjects"] = [server_error()]
    await h.poll()
    assert [p["correlation_id"] for p in h.bus.payloads()] == ["lin-ENG-2-1"]
    assert h.factory(in_project) == []
    await h.poll()
    assert [p["target_repo"] for p in h.bus.payloads()] == ["example-org/default-app", REPO]
    assert h.linear.state_name(loose) == "In Progress"


# ---------------------------------------------------------------------------
# Creation (11.1)
# ---------------------------------------------------------------------------


def _uuid4(value: str) -> bool:
    return uuid.UUID(value).version == 4


async def test_a_registered_repository_gets_one_project_with_its_link(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    await h.poll(3)
    (project,) = h.linear.projects.values()
    assert project.name == "notes-app"
    assert project.description == (
        "Issues in this project are built by the factory in example-org/notes-app."
    )
    assert [(link.url, link.label) for link in project.links] == [
        (f"https://github.com/{REPO}", "GitHub")
    ]
    intent = h.store.project_intent(REPO)
    assert intent is not None and intent.complete
    assert intent.project_id == project.id and intent.link_id == project.links[0].id
    assert _uuid4(intent.project_id) and _uuid4(intent.link_id)
    assert h.linear.calls.count("DoorProjectCreate") == 1
    assert h.linear.calls.count("DoorLinkCreate") == 1


async def test_the_intent_and_its_ids_are_recorded_before_the_first_write(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.linear.fail_next["DoorProjectCreate"] = [server_error()]
    await h.poll()
    intent = h.store.project_intent(REPO)
    assert intent is not None and not intent.complete and not intent.project_created
    assert h.linear.projects == {}
    h.restart()
    await h.poll()
    (project,) = h.linear.projects.values()
    assert project.id == intent.project_id  # the recorded id, reused
    assert project.links[0].id == intent.link_id


async def test_project_made_then_link_failed_is_finished_on_the_same_project(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.linear.fail_next["DoorLinkCreate"] = [server_error()]
    await h.poll()
    (project,) = h.linear.projects.values()
    assert project.links == []
    h.restart()
    await h.poll(2)
    assert list(h.linear.projects) == [project.id]
    assert [link.url for link in project.links] == [f"https://github.com/{REPO}"]
    assert h.store.project_intent(REPO).complete  # type: ignore[union-attr]


@pytest.mark.parametrize("operation", ["DoorProjectCreate", "DoorLinkCreate"])
async def test_a_lost_answer_never_makes_a_second_project_or_link(
    tmp_path: Path, operation: str
) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.linear.lose_response[operation] = 1
    await h.poll()
    h.restart()
    await h.poll(2)
    (project,) = h.linear.projects.values()
    assert len(project.links) == 1
    assert h.linear.calls.count("DoorProjectCreate") == 1
    assert h.store.project_intent(REPO).complete  # type: ignore[union-attr]


async def test_a_completed_repository_is_never_created_again(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO, OTHER))
    await h.poll()
    by_name = {p.name: p for p in h.linear.projects.values()}
    del h.linear.projects[by_name["notes-app"].id]  # deleted by a person
    by_name["other-app"].archived = True  # archived by a person
    h.restart()
    await h.poll(2)
    assert sorted(p.name for p in h.linear.projects.values()) == ["other-app"]
    assert h.linear.calls.count("DoorProjectCreate") == 2


async def test_an_archived_or_completed_project_counts_as_existing(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO, OTHER))
    h.linear.project("Old notes", f"https://github.com/{REPO}", archived=True)
    h.linear.project("Old other", f"https://github.com/{OTHER}.git", status="completed")
    await h.poll(2)
    assert "DoorProjectCreate" not in h.linear.calls
    assert h.store.project_intent(REPO) is None


async def test_a_conflicting_repository_gets_nothing_created(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.linear.project("One", f"https://github.com/{REPO}")
    h.linear.project("Two", f"https://github.com/{REPO}/")
    await h.poll()
    assert "DoorProjectCreate" not in h.linear.calls
    assert len(h.linear.projects) == 2


@pytest.mark.parametrize("contents", [None, "planning: [unclosed\n"])
async def test_an_unreadable_forge_yaml_creates_nothing(
    tmp_path: Path, contents: str | None
) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    if contents is None:
        h.forge_settings.unlink()
    else:
        h.forge_settings.write_text(contents, encoding="utf-8")
    await h.poll()
    assert h.linear.projects == {}
    assert h.store.project_intent(REPO) is None


async def test_an_unfinished_intent_waits_while_forge_yaml_is_unreadable(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.linear.fail_next["DoorLinkCreate"] = [server_error()]
    await h.poll()
    h.forge_settings.write_text("planning: [unclosed\n", encoding="utf-8")
    await h.poll()
    (project,) = h.linear.projects.values()
    assert project.links == []
    forge_yaml(h.forge_settings, REPO)
    await h.poll()
    assert len(project.links) == 1


# ---------------------------------------------------------------------------
# linear-projects.json (11.3)
# ---------------------------------------------------------------------------


async def test_linear_projects_file_lists_each_mapped_repository(h: Harness) -> None:
    notes = h.linear.project("Notes", f"https://github.com/{REPO}.git")
    h.linear.project("Ideas")
    h.linear.project("One", "https://github.com/example-org/shared")
    h.linear.project("Two", "https://github.com/example-org/shared")
    await h.poll()
    path = h.state_dir / PROJECTS_FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {"written_at", "projects"}
    assert data["projects"] == {
        REPO: {"name": "Notes", "url": f"https://linear.app/example/project/{notes.id[:8]}"}
    }
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert [p.name for p in h.state_dir.iterdir() if p.name.startswith(".linear-projects-")] == []


async def test_linear_projects_file_is_not_touched_when_the_read_fails(h: Harness) -> None:
    h.linear.project("Notes", f"https://github.com/{REPO}")
    await h.poll()
    path = h.state_dir / PROJECTS_FILE
    before = path.read_text(encoding="utf-8")
    h.linear.fail_next["DoorProjects"] = [server_error()]
    await h.poll()
    assert path.read_text(encoding="utf-8") == before


def test_linear_projects_file_is_replaced_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    projects = ProjectMap([_project("p-one", "Notes", f"https://github.com/{REPO}")])
    path = write_projects_file(tmp_path, projects)
    before = path.read_text(encoding="utf-8")

    def broken(src: Any, dst: Any) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(OSError):
        write_projects_file(tmp_path, ProjectMap([]))
    assert path.read_text(encoding="utf-8") == before
    assert sorted(p.name for p in tmp_path.iterdir()) == [PROJECTS_FILE]


# ---------------------------------------------------------------------------
# Project updates (11.4, 11.5)
# ---------------------------------------------------------------------------


async def sent_in_project(h: Harness, title: str = "Add a dark mode") -> tuple[Any, Any]:
    project = h.linear.project("Notes", f"https://github.com/{REPO}")
    issue = h.linear.issue(title)
    issue.project_id = project.id
    await h.poll()
    assert h.linear.state_name(issue) == "In Progress"
    return project, issue


def on_main(cid: str = "lin-ENG-1-1", *, phase: str = fr.ON_MAIN, reason: str = "") -> Any:
    return fr.SingleOutcome(
        cid, phase, phase != fr.ON_MAIN_REPORT_PENDING, reason or "merged", j_commit="abc1234"
    )


async def test_one_update_per_merge_across_polls_and_restarts(h: Harness) -> None:
    h.summary()
    project, issue = await sent_in_project(h)
    other = h.linear.issue("Export to CSV", state="Backlog")
    other.project_id = project.id
    h.attempts.outcomes["lin-ENG-1-1"] = on_main(phase=fr.ON_MAIN_REPORT_PENDING)
    await h.poll(2)
    assert h.linear.updates_on(project) == []  # waits for the merge report
    assert h.store.reservations() != {}
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    h.restart()
    await h.poll(2)
    (update,) = h.linear.updates_on(project)
    assert update.health == "atRisk"
    assert plain(update.body) == "\n".join(
        [
            "**Delivered**",
            "- ENG-1 Add a dark mode",
            "Merged into the main branch as `abc1234`.",
            "",
            "**Open**",
            "In Linear: 1 issue not done.",
            "- ENG-2 Export to CSV",
            "In the factory: 3 open issues, 1 being built.",
            "",
            "**Cost** (nominal US dollars, as the dashboard shows them)",
            "- This merge: $2.20 nominal",
            "- This week: $7.05 nominal (part estimated)",
            "- Project total: $41.20 nominal",
            "",
            "Project health: at risk (from the dashboard).",
        ]
    )
    assert h.store.reservations() == {}
    assert h.linear.state_name(issue) == "Done"


async def test_a_failed_deploy_is_off_track_whatever_the_dashboard_says(h: Harness) -> None:
    h.summary()
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main(
        phase=fr.ON_MAIN_DEPLOY_FAILED,
        reason="merged into main, but its deploy failed: the health check timed out",
    )
    await h.poll()
    (update,) = h.linear.updates_on(project)
    assert update.health == "offTrack"
    assert "The deploy after this merge failed: the health check timed out." in update.body
    assert "Project health: off track (the deploy after this merge failed)." in update.body


@pytest.mark.parametrize("health", ["unknown", "sideways"])
async def test_unknown_health_is_left_out_and_said(h: Harness, health: str) -> None:
    h.summary()
    data = json.loads(h.summary_path.read_text())
    data["projects"][REPO]["health"] = health
    h.summary_path.write_text(json.dumps(data))
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    (update,) = h.linear.updates_on(project)
    assert update.health is None
    assert "Project health: not available from the dashboard." in update.body


async def test_with_no_summary_health_and_figures_are_not_available(h: Harness) -> None:
    project, _ = await sent_in_project(h)  # no summary file written
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    (update,) = h.linear.updates_on(project)
    assert update.health is None
    body = plain(update.body)
    assert "In the factory: not available from the dashboard." in body
    assert "- This merge: not available" in body
    assert "- This week: not available" in body
    assert "- Project total: not available" in body
    assert body.endswith("Project health: not available from the dashboard.")


@pytest.mark.parametrize(
    "overrides",
    [
        {"forge__valid_until": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
        {"forge__valid_until": _DELETE},
    ],
)
async def test_stale_forge_evidence_hides_open_issues_and_health(
    h: Harness, overrides: dict[str, Any]
) -> None:
    h.summary(**overrides)
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    (update,) = h.linear.updates_on(project)
    assert update.health is None
    assert "In the factory: not available from the dashboard." in update.body
    assert "- This merge: $2.20 nominal" in update.body  # cost has its own rule


def test_cost_wording_and_freshness(tmp_path: Path) -> None:
    now = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
    path = tmp_path / "s.json"

    def summary(read_at: datetime | None) -> Summary:
        cost = {"read_at": read_at.isoformat() if read_at else None, "stale_after_seconds": 600}
        path.write_text(json.dumps({"version": 1, "forge": {}, "cost": cost}))
        return read_summary(path, now=now)

    fresh = summary(now - timedelta(minutes=2))
    assert cost_words(slot("$2.20"), fresh) == "$2.20 nominal"
    assert cost_words(slot("$2.20", estimated=True), fresh) == "$2.20 nominal (part estimated)"
    unpriced = slot("$2.20", reason="3 calls on a model with no price.")
    assert cost_words(unpriced, fresh) == "$2.20 nominal (3 calls on a model with no price)"
    not_measured = {
        "state": "not_measured",
        "value": "",
        "label": "Not measured",
        "reason": "calls before 17 October 2026 were not tagged",
    }
    assert cost_words(not_measured, fresh) == (
        "Not measured (calls before 17 October 2026 were not tagged)"
    )
    saved_stale = slot(
        "$2.20", stale=True, stale_text="cost data last read at 11:40 — may be incomplete"
    )
    assert cost_words(saved_stale, fresh) == (
        "$2.20 nominal; cost data last read at 11:40 — may be incomplete"
    )
    assert cost_words(None, fresh) == "not available"  # a missing entry is never zero

    stale = summary(now - timedelta(minutes=20))
    assert cost_words(slot("$2.20"), stale) == (
        "$2.20 nominal; may be incomplete: cost data last read at 2026-10-18 11:40 UTC"
    )
    assert cost_words(slot("$2.20"), summary(now - timedelta(minutes=61))) == "not available"
    assert cost_words(slot("$2.20"), summary(None)) == "not available"
    assert cost_words(slot("$2.20"), read_summary(None, now=now)) == "not available"

    for broken in ["{not json", json.dumps({"version": 2}), json.dumps([1])]:
        path.write_text(broken)
        assert not read_summary(path, now=now).available


def test_health_mapping() -> None:
    def summary(health: str, fresh: bool = True) -> Summary:
        return Summary(True, fresh, "fresh", None, {REPO: {"health": health}}, {})

    def delivered(**kw: Any) -> Delivered:
        return Delivered("lin-ENG-1-1", REPO, [("ENG-1", "t")], **kw)

    assert update_health(delivered(), summary("on_track"))[0] == "onTrack"
    assert update_health(delivered(), summary("at_risk"))[0] == "atRisk"
    assert update_health(delivered(), summary("off_track"))[0] == "offTrack"
    assert update_health(delivered(), summary("unknown"))[0] is None
    assert update_health(delivered(), summary("on_track", fresh=False))[0] is None
    assert update_health(delivered(deploy_failed="x"), summary("on_track"))[0] == "offTrack"
    assert update_health(delivered(not_landed=[("ENG-2", "u")]), summary("on_track"))[0] == (
        "offTrack"
    )
    assert update_health(delivered(not_landed=[("ENG-2", "u")]), Summary())[0] == "offTrack"


async def test_a_mission_with_a_member_not_landed_is_off_track(h: Harness) -> None:
    h.summary()
    data = json.loads(h.summary_path.read_text())
    data["projects"][REPO]["health"] = "on_track"
    h.summary_path.write_text(json.dumps(data))
    project = h.linear.project("Notes", f"https://github.com/{REPO}")
    label = h.linear.label("mission: Sharing")
    a = h.linear.issue("Share a note", labels=[label])
    b = h.linear.issue("Revoke a share", labels=[label], blocked_by=[a.id])
    a.project_id = b.project_id = project.id
    await h.poll()
    cid = f"{mission_prefix(label)}1"
    h.attempts.outcomes[cid] = fr.MissionOutcome(
        cid,
        fr.ON_MAIN,
        True,
        mission_id="m-1",
        status="MERGED",
        attempts=(
            fr.KeyAttempt("ENG1", 1, "LANDED", None, "x"),
            fr.KeyAttempt("ENG2", 1, "FAILED", "tests failed", "y"),
        ),
        landed_keys=("ENG1",),
        j_commit="def5678",
    )
    await h.poll(2)
    (update,) = h.linear.updates_on(project)
    assert update.health == "offTrack"
    body = plain(update.body)
    assert body.startswith(
        "**Delivered**\nThe mission “Sharing” merged into the main branch as `def5678`.\n"
        "Landed:\n- ENG-1 Share a note\nDid not land:\n- ENG-2 Revoke a share\n"
    )
    assert "In Linear: 1 issue not done.\n- ENG-2 Revoke a share" in body
    assert "- This merge: not available" in body  # no attempt entry for this mission
    assert "Project health: off track (part of the mission did not land)." in body
    assert h.store.reservations() == {}


@pytest.mark.parametrize(
    ("phase", "reason"),
    [
        (fr.MERGE_DECLINED, "the approver declined the merge card"),
        (fr.MERGE_FAILED, "the candidate no longer applies"),
        (fr.BUILD_FAILED, "tests failed"),
    ],
)
async def test_nothing_is_posted_for_a_declined_or_failed_merge(
    h: Harness, phase: str, reason: str
) -> None:
    h.summary()
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = fr.SingleOutcome("lin-ENG-1-1", phase, True, reason)
    await h.poll(2)
    assert h.linear.updates_on(project) == []
    assert "DoorProjectUpdateCreate" not in h.linear.calls
    assert h.store.reservations() == {}


async def test_nothing_is_posted_for_a_mission_that_was_not_merged(h: Harness) -> None:
    project = h.linear.project("Notes", f"https://github.com/{REPO}")
    label = h.linear.label("mission: Sharing")
    a = h.linear.issue("Share a note", labels=[label])
    a.project_id = project.id
    await h.poll()
    cid = f"{mission_prefix(label)}1"
    h.attempts.outcomes[cid] = fr.MissionOutcome(cid, fr.NOT_MERGED, True, status="NOT_MERGED")
    await h.poll()
    assert h.linear.updates_on(project) == []


@pytest.mark.parametrize("change", ["archived", "completed"])
async def test_nothing_is_posted_to_an_archived_or_completed_project(
    h: Harness, change: str
) -> None:
    project, _ = await sent_in_project(h)
    if change == "archived":
        project.archived = True
    else:
        project.status = "completed"
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    assert h.linear.updates_on(project) == []
    assert h.store.reservations() == {}


async def test_nothing_is_posted_for_a_repository_without_a_project(h: Harness) -> None:
    issue = h.linear.issue("Add a dark mode")  # the default repository, no project
    await h.poll()
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    assert h.linear.project_updates == []
    assert h.linear.state_name(issue) == "Done"


async def test_an_update_whose_answer_was_lost_is_not_posted_twice(h: Harness) -> None:
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    h.linear.lose_response["DoorProjectUpdateCreate"] = 1
    await h.poll()  # the update is made but its answer lost: the attempt stays open
    assert h.store.reservations() != {}
    h.restart()
    await h.poll(2)
    assert len(h.linear.updates_on(project)) == 1
    assert h.linear.calls.count("DoorProjectUpdateCreate") == 1
    assert h.store.reservations() == {}


async def test_an_update_linear_refuses_does_not_hold_the_attempt(h: Harness) -> None:
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    h.linear.fail_next["DoorProjectUpdateCreate"] = [refused()]
    await h.poll()
    assert h.linear.updates_on(project) == []
    assert h.store.reservations() == {}


async def test_an_update_waits_while_the_projects_cannot_be_read(h: Harness) -> None:
    project, issue = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    h.linear.fail_next["DoorProjects"] = [server_error()]
    await h.poll()
    assert h.linear.state_name(issue) == "Done"
    assert h.store.reservations() != {}
    assert h.linear.updates_on(project) == []
    await h.poll()
    assert len(h.linear.updates_on(project)) == 1
    assert h.store.reservations() == {}


# ---------------------------------------------------------------------------
# Repair pass: Codex round 1 (R1-R4) and the coach (C1-C4)
# ---------------------------------------------------------------------------


def lose_record(h: Harness) -> None:
    """The door's record is lost: a new, empty one on the next start."""
    h.store.close()
    (h.state_dir / "linear-door.sqlite3").unlink()
    h.door = h._door()


async def test_r1_a_short_default_resolves_to_its_project(tmp_path: Path) -> None:
    h = Harness(tmp_path)
    h.default_repo = "notes-app"
    h.restart()
    project = h.linear.project("Notes", f"https://github.com/{REPO}")
    h.linear.issue("Add a dark mode")  # no project: the short default
    await h.poll()
    assert h.bus.payloads()[0]["target_repo"] == "notes-app"
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    assert len(h.linear.updates_on(project)) == 1


async def test_r1_a_short_label_resolves_to_its_project(h: Harness) -> None:
    project = h.linear.project("Notes", f"https://github.com/{REPO}")
    ideas = h.linear.project("Ideas")
    issue = h.linear.issue("Add a dark mode", labels=[h.linear.label("repo: notes-app")])
    issue.project_id = ideas.id
    await h.poll()
    assert h.bus.payloads()[0]["target_repo"] == "notes-app"
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    assert len(h.linear.updates_on(project)) == 1
    assert h.linear.updates_on(ideas) == []


async def test_r1_an_ambiguous_short_name_gets_no_update(tmp_path: Path) -> None:
    from structlog.testing import capture_logs

    h = Harness(tmp_path, registered=("org-a/notes-app", "org-b/notes-app"))
    h.default_repo = "notes-app"
    h.restart()
    one = h.linear.project("A", "https://github.com/org-a/notes-app")
    two = h.linear.project("B", "https://github.com/org-b/notes-app")
    h.linear.issue("Add a dark mode")
    await h.poll()
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    with capture_logs() as logs:
        await h.poll()
    assert h.linear.project_updates == []
    assert h.linear.updates_on(one) == h.linear.updates_on(two) == []
    (skipped,) = [e for e in logs if e["event"] == "linear_door_project_update_skipped"]
    assert "more than one" in skipped["reason"]
    assert h.store.reservations() == {}


async def _sent_then_record_lost(h: Harness, issue: Any) -> None:
    await h.poll()
    assert h.linear.state_name(issue) == "In Progress"
    lose_record(h)
    h.attempts.recorded = [RecordedAttempt("lin-ENG-1-1", open=True)]
    h.attempts.outcomes["lin-ENG-1-1"] = fr.SingleOutcome("lin-ENG-1-1", fr.BUILDING, False)
    await h.poll()  # rebuilt from Forge's record: the attempt is open again
    assert h.store.reservations() != {}


async def test_r2_after_a_lost_record_the_override_repository_gets_the_update(
    h: Harness,
) -> None:
    notes = h.linear.project("Notes", f"https://github.com/{REPO}")
    other = h.linear.project("Other", f"https://github.com/{OTHER}")
    issue = h.linear.issue("Add a dark mode", labels=[h.linear.label(f"repo: {OTHER}")])
    issue.project_id = notes.id
    await _sent_then_record_lost(h, issue)
    h.attempts.outcomes["lin-ENG-1-1"] = fr.SingleOutcome(
        "lin-ENG-1-1", fr.ON_MAIN, True, "merged", j_commit="abc1234", target_repo=OTHER
    )
    await h.poll()
    assert h.linear.updates_on(notes) == []
    assert len(h.linear.updates_on(other)) == 1


async def test_r2_after_a_lost_record_a_moved_issue_keeps_its_repository(h: Harness) -> None:
    notes = h.linear.project("Notes", f"https://github.com/{REPO}")
    other = h.linear.project("Other", f"https://github.com/{OTHER}")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = notes.id
    await _sent_then_record_lost(h, issue)
    issue.project_id = other.id  # moved while it was being built
    h.attempts.outcomes["lin-ENG-1-1"] = fr.SingleOutcome(
        "lin-ENG-1-1", fr.ON_MAIN, True, "merged", j_commit="abc1234", target_repo=REPO
    )
    await h.poll()
    assert len(h.linear.updates_on(notes)) == 1
    assert h.linear.updates_on(other) == []


async def test_r2_with_no_known_repository_no_update_is_posted(h: Harness) -> None:
    notes = h.linear.project("Notes", f"https://github.com/{REPO}")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = notes.id
    await _sent_then_record_lost(h, issue)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()  # Forge's record names no repository
    await h.poll()
    assert h.linear.project_updates == []
    assert h.linear.state_name(issue) == "Done"
    assert h.store.reservations() == {}


async def test_r3_a_lost_update_is_found_where_it_was_written(h: Harness) -> None:
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    h.linear.lose_response["DoorProjectUpdateCreate"] = 1
    await h.poll()  # written on Notes, answer lost
    project.links.clear()  # the repository's link moves to another project
    newer = h.linear.project("Notes v2", f"https://github.com/{REPO}")
    h.restart()
    await h.poll(2)
    assert len(h.linear.updates_on(project)) == 1
    assert h.linear.updates_on(newer) == []
    assert h.linear.calls.count("DoorProjectUpdateCreate") == 1
    assert h.store.reservations() == {}


async def test_r3_an_unconfirmed_update_is_retried_on_its_first_project(h: Harness) -> None:
    project, _ = await sent_in_project(h)
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    h.linear.fail_next["DoorProjectUpdateCreate"] = [server_error()]
    await h.poll()  # begun on Notes; Linear never took it
    project.links.clear()
    newer = h.linear.project("Notes v2", f"https://github.com/{REPO}")
    await h.poll()
    assert len(h.linear.updates_on(project)) == 1
    assert h.linear.updates_on(newer) == []


def _many_links(repo: str | None) -> list[str]:
    """21 links: 20 on the first page, then the GitHub link (or one more)."""
    links = [f"https://example.com/page-{n}" for n in range(20)]
    return [*links, f"https://github.com/{repo}" if repo else "https://example.com/page-20"]


async def test_r4_a_github_link_on_the_second_page_makes_the_read_unusable(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.linear.project("Notes", *_many_links(REPO))
    ideas = h.linear.project("Ideas")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = ideas.id
    await h.poll(2)
    assert "DoorProjectCreate" not in h.linear.calls  # nothing created
    assert h.store.project_intent(REPO) is None
    assert h.factory(issue) == []  # nothing refused
    assert h.linear.state_name(issue) == "Todo"
    assert not (h.state_dir / PROJECTS_FILE).exists()


async def test_r4_an_update_waits_while_the_read_is_not_whole(h: Harness) -> None:
    project, issue = await sent_in_project(h)
    crowded = h.linear.project("Crowded", *_many_links(None))
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    assert h.linear.state_name(issue) == "Done"
    assert h.linear.updates_on(project) == []
    assert h.store.reservations() != {}
    crowded.links = crowded.links[:5]
    await h.poll()
    assert len(h.linear.updates_on(project)) == 1
    assert h.store.reservations() == {}


@pytest.mark.parametrize("old", ["archived", "completed", "trashed"])
async def test_c1_an_inactive_old_project_does_not_block_a_new_one(
    tmp_path: Path, old: str
) -> None:
    h = Harness(tmp_path, registered=(REPO,))
    h.summary()
    retired = h.linear.project("Notes", f"https://github.com/{REPO}")
    if old == "completed":
        retired.status = "completed"
    else:
        setattr(retired, old, True)
    new = h.linear.project("Notes v2", f"https://github.com/{REPO}")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = new.id
    await h.poll()
    assert h.bus.payloads()[0]["target_repo"] == REPO
    data = json.loads((h.state_dir / PROJECTS_FILE).read_text(encoding="utf-8"))
    assert data["projects"][REPO]["name"] == "Notes v2"
    h.attempts.outcomes["lin-ENG-1-1"] = on_main()
    await h.poll()
    assert len(h.linear.updates_on(new)) == 1
    assert h.linear.updates_on(retired) == []
    assert "DoorProjectCreate" not in h.linear.calls  # creation still counts the old one


async def test_c1_an_issue_in_an_inactive_project_with_an_active_rival_is_refused(
    h: Harness,
) -> None:
    retired = h.linear.project("Notes", f"https://github.com/{REPO}", archived=True)
    h.linear.project("Notes v2", f"https://github.com/{REPO}")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = retired.id
    await h.poll()
    (only,) = h.factory(issue)
    assert "another project links to the same repository" in only


async def test_c1_two_active_projects_still_conflict(h: Harness) -> None:
    h.linear.project("One", f"https://github.com/{REPO}")
    h.linear.project("Two", f"https://github.com/{REPO}")
    await h.poll()
    data = json.loads((h.state_dir / PROJECTS_FILE).read_text(encoding="utf-8"))
    assert data["projects"] == {}


async def test_c2_a_refused_creation_holds_back_only_its_repository(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO, OTHER))
    h.linear.fail_next["DoorProjectCreate"] = [refused()]
    await h.poll(3)
    assert sorted(p.name for p in h.linear.projects.values()) == ["other-app"]
    intent = h.store.project_intent(REPO)
    assert intent is not None and not intent.complete and intent.retry_after is not None
    assert h.linear.calls.count("DoorProjectCreate") == 2  # not retried within the hour
    h.store.set_intent_retry(REPO, datetime.now(UTC) - timedelta(seconds=1))
    await h.poll(2)
    assert sorted(p.name for p in h.linear.projects.values()) == ["notes-app", "other-app"]
    assert h.store.project_intent(REPO).complete  # type: ignore[union-attr]


async def test_c2_an_outage_still_stops_creation_for_the_poll(tmp_path: Path) -> None:
    h = Harness(tmp_path, registered=(REPO, OTHER))
    h.linear.fail_next["DoorProjectCreate"] = [server_error()]
    await h.poll()
    assert h.linear.projects == {}
    await h.poll(2)
    assert len(h.linear.projects) == 2


async def test_c3_an_issue_in_a_project_the_read_cannot_see_is_refused_once(
    h: Harness,
) -> None:
    elsewhere = h.linear.project("Elsewhere", f"https://github.com/{REPO}", team_id="team-x")
    issue = h.linear.issue("Add a dark mode")
    issue.project_id = elsewhere.id
    await h.poll(3)
    assert h.bus.published == []
    (only,) = h.factory(issue)
    assert "cannot see its project" in only
    assert h.linear.state_name(issue) == "Todo"


async def test_c4_an_unusable_forge_yaml_is_logged_once(tmp_path: Path) -> None:
    from structlog.testing import capture_logs

    h = Harness(tmp_path, registered=(REPO,))
    h.forge_settings.unlink()
    with capture_logs() as logs:
        await h.poll(3)
        forge_yaml(h.forge_settings, REPO)
        await h.poll(2)
    events = [e["event"] for e in logs if e["event"].startswith("linear_door_forge_settings")]
    assert events == ["linear_door_forge_settings_unusable", "linear_door_forge_settings_usable"]
