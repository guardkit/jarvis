"""Linear projects for registered repositories (design section 11.1 and 11.3).

One meaning of "project" everywhere: a Linear project is a factory project is
one repository. A Linear project's repository is named by one external link
on the project whose URL is exactly ``https://github.com/<owner>/<name>``
(a trailing ``/`` or ``.git`` is ignored).

* :func:`registered_repositories` reads the ``planning.sandboxes`` keys from
  the coordinator's ``forge.yaml`` (what ``forge register-repo`` writes),
  read-only. A file that cannot be read or parsed gives ``None``, and the door
  creates nothing that poll.
* :class:`ProjectMap` is one poll's read of the team's projects (archived and
  completed ones included): which repository each project maps to, and which
  project each repository maps to, with the conflicts of section 11.1.
* :func:`write_projects_file` writes ``linear-projects.json`` into the door's
  state directory, atomically, for the dashboard's "Linear" link (11.3).
* :func:`ensure_projects` creates the project of each registered repository
  that no project links to, with caller-chosen UUID v4 ids recorded in the
  door's record before the first write, and completes an unfinished creation
  on later polls (11.1, design rounds 2 and 3, R8).

Log hygiene: no log line carries a project's name or URL.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import structlog

from jarvis.infrastructure.linear.client import (
    LinearAuthError,
    LinearError,
    LinearProject,
    LinearRateLimited,
)
from jarvis.infrastructure.linear.store import DoorStore
from jarvis.infrastructure.planning_intake_grammar import is_allowed_target_name

logger = structlog.get_logger(__name__)

#: The file the dashboard reads (section 11.3).
PROJECTS_FILE = "linear-projects.json"
#: The label of the GitHub link the door adds to a project it creates.
GITHUB_LABEL = "GitHub"

#: Why a project maps to no repository (the words of the refusal comments).
NO_LINK = "has no GitHub link"
TWO_REPOS = "links to two repositories"
SHARED_REPO = "another project links to the same repository"
TOO_MANY_LINKS = "has more links than the door reads at once"


def repo_key(repo: str) -> str:
    """How repository names are compared (GitHub's names ignore case)."""
    return repo.strip().casefold()


def github_repo(url: str) -> str | None:
    """``owner/name`` from exactly ``https://github.com/<owner>/<name>``
    (a trailing ``/`` or ``.git`` ignored), else ``None``."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme != "https" or parts.netloc.lower() != "github.com":
        return None
    if parts.query or parts.fragment:
        return None
    path = parts.path.rstrip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    segments = path.strip("/").split("/")
    if len(segments) != 2 or not all(segments) or not path.startswith("/"):
        return None
    repo = "/".join(segments)
    return repo if is_allowed_target_name(repo) else None


# ---------------------------------------------------------------------------
# Registered repositories
# ---------------------------------------------------------------------------


def registered_repositories(path: Path | None) -> list[str] | None:
    """The ``planning.sandboxes`` keys of the coordinator's ``forge.yaml``.

    ``None`` when the file is not configured, cannot be read, or is not YAML
    of the expected shape: the door then creates nothing that poll. A file
    with no ``planning.sandboxes`` registers nothing (an empty list).
    """
    if path is None:
        return None
    import yaml

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        logger.warning("linear_door_forge_settings_unreadable", error=type(exc).__name__)
        return None
    if data is None:
        return []
    if not isinstance(data, dict):
        logger.warning("linear_door_forge_settings_unreadable", error="not a mapping")
        return None
    planning = data.get("planning")
    if planning is None:
        return []
    if not isinstance(planning, dict):
        logger.warning("linear_door_forge_settings_unreadable", error="planning is not a mapping")
        return None
    sandboxes = planning.get("sandboxes")
    if sandboxes is None:
        return []
    if not isinstance(sandboxes, dict):
        logger.warning("linear_door_forge_settings_unreadable", error="sandboxes is not a mapping")
        return None
    found: list[str] = []
    for key in sandboxes:
        name = str(key).strip()
        if name.count("/") == 1 and is_allowed_target_name(name):
            found.append(name)
        else:
            logger.info("linear_door_registered_name_skipped", reason="not <owner>/<name>")
    return found


# ---------------------------------------------------------------------------
# The map
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectRepo:
    """What one project means for its issues: a repository, or why none."""

    project: LinearProject
    repo: str | None
    problem: str | None = None  # NO_LINK, TWO_REPOS, SHARED_REPO or TOO_MANY_LINKS
    repos: tuple[str, ...] = ()  # every repository its links name


@dataclass
class ProjectMap:
    """One poll's read of the team's projects (section 11.1)."""

    projects: list[LinearProject]
    registered: list[str] = field(default_factory=list)
    _by_project: dict[str, ProjectRepo] = field(init=False, default_factory=dict)
    _linking: dict[str, list[LinearProject]] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        spelling = {repo_key(r): r for r in self.registered}
        named: dict[str, tuple[str, ...]] = {}
        for project in self.projects:
            repos: dict[str, str] = {}
            for url in project.link_urls:
                repo = github_repo(url)
                if repo is not None:
                    repos.setdefault(repo_key(repo), spelling.get(repo_key(repo), repo))
            named[project.id] = tuple(repos.values())
            for key in repos:
                self._linking.setdefault(key, []).append(project)
        for project in self.projects:
            repos_named = named[project.id]
            if project.truncated:
                self._by_project[project.id] = ProjectRepo(
                    project, None, TOO_MANY_LINKS, repos_named
                )
            elif not repos_named:
                self._by_project[project.id] = ProjectRepo(project, None, NO_LINK)
            elif len(repos_named) > 1:
                self._by_project[project.id] = ProjectRepo(project, None, TWO_REPOS, repos_named)
            elif len(self._linking[repo_key(repos_named[0])]) > 1:
                self._by_project[project.id] = ProjectRepo(project, None, SHARED_REPO, repos_named)
            else:
                self._by_project[project.id] = ProjectRepo(
                    project, repos_named[0], None, repos_named
                )

    def for_project(self, project_id: str) -> ProjectRepo | None:
        """What the project means, or ``None`` when this read did not see it."""
        return self._by_project.get(project_id)

    def get(self, project_id: str) -> LinearProject | None:
        found = self._by_project.get(project_id)
        return found.project if found is not None else None

    def linking(self, repo: str) -> list[LinearProject]:
        """Every project (in any state) with a GitHub link to ``repo``."""
        return list(self._linking.get(repo_key(repo), []))

    def project_for_repo(self, repo: str) -> LinearProject | None:
        """The one project ``repo`` maps to, or ``None`` (none, or a conflict)."""
        linking = self.linking(repo)
        if len(linking) != 1:
            return None
        mapped = self._by_project[linking[0].id]
        return mapped.project if mapped.repo is not None else None

    def mapped(self) -> dict[str, LinearProject]:
        """Each repository exactly one project maps to (its name as registered,
        or as the link spells it) → that project."""
        found: dict[str, LinearProject] = {}
        for mapped in self._by_project.values():
            if mapped.repo is not None:
                found[mapped.repo] = mapped.project
        return found


def problem_words(mapped: ProjectRepo) -> str:
    """The refusal comment for an issue in a project that maps to nothing."""
    name = mapped.project.name or "this project"
    listed = ", ".join(f"`{r}`" for r in mapped.repos)
    why = {
        NO_LINK: "has no GitHub link",
        TWO_REPOS: f"links to two repositories ({listed})",
        SHARED_REPO: f"links to {listed}, but another project links to the same repository",
        TOO_MANY_LINKS: "has more links than the door reads at once",
    }.get(mapped.problem or "", "does not name one repository")
    return (
        f"This issue was not sent: its project “{name}” {why}, so I do not know which "
        "repository it is for. Give the project exactly one GitHub link "
        "(`https://github.com/<owner>/<name>`) that no other project has, or add a label "
        "`repo: <name>` to the issue."
    )


# ---------------------------------------------------------------------------
# linear-projects.json (section 11.3)
# ---------------------------------------------------------------------------


def projects_file_content(projects: ProjectMap, *, now: datetime | None = None) -> dict[str, Any]:
    stamp = (now or datetime.now(UTC)).isoformat()
    return {
        "written_at": stamp,
        "projects": {
            repo: {"name": project.name, "url": project.url}
            for repo, project in sorted(projects.mapped().items())
        },
    }


def write_projects_file(
    state_dir: Path, projects: ProjectMap, *, now: datetime | None = None
) -> Path:
    """Write ``linear-projects.json`` atomically: a temporary file in the same
    directory, then ``os.replace``. Readable by the dashboard's own user."""
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / PROJECTS_FILE
    data = json.dumps(projects_file_content(projects, now=now), indent=2, sort_keys=True)
    fd, temp = tempfile.mkstemp(prefix=".linear-projects-", suffix=".tmp", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o644)
        os.replace(temp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise
    return target


# ---------------------------------------------------------------------------
# Creation (section 11.1)
# ---------------------------------------------------------------------------


def project_description(repo: str) -> str:
    return f"Issues in this project are built by the factory in {repo}."


def short_name(repo: str) -> str:
    return repo.rsplit("/", 1)[-1]


async def ensure_projects(
    client: Any,
    store: DoorStore,
    *,
    team_id: str,
    registered: Iterable[str],
    projects: ProjectMap,
) -> None:
    """Create (or finish creating) the project of each registered repository
    that no project links to.

    An intent is recorded, with two new UUID v4 ids, before the first write;
    a retry reuses the recorded ids. On each poll an unfinished intent is
    completed from what the projects read shows: the project made but no link
    → the link is added; no project and never seen made → it is made. A
    completed repository is never made again. Linear failing part way stops
    creation for this poll (the rest of the poll goes on); a refused key or
    the rate limit stops the poll.
    """
    for repo in registered:
        key = repo_key(repo)
        intent = store.project_intent(key)
        if intent is not None and intent.complete:
            continue
        linking = projects.linking(repo)
        if intent is None:
            if linking:
                continue  # mapped, or a conflict: nothing is created
            intent = store.begin_project_intent(key, str(uuid.uuid4()), str(uuid.uuid4()))
            logger.info("linear_door_project_intent", repo=repo)
        log = logger.bind(repo=repo, project_id=intent.project_id)
        if any(p.id != intent.project_id for p in linking):
            # Someone linked another project to it meanwhile: use theirs.
            store.complete_project_intent(key, "another project already links to it")
            log.info("linear_door_project_intent_done", reason="another project links to it")
            continue
        try:
            own = projects.get(intent.project_id)
            if own is not None and not intent.project_created:
                store.mark_project_created(key)
            if own is None:
                if intent.project_created:
                    store.complete_project_intent(key, "its project was removed before its link")
                    log.warning("linear_door_project_gone_before_link")
                    continue
                await client.create_project(
                    project_id=intent.project_id,
                    name=short_name(repo),
                    team_id=team_id,
                    description=project_description(repo),
                )
                store.mark_project_created(key)
                log.info("linear_door_project_created")
            elif any(p.id == intent.project_id for p in linking):
                store.complete_project_intent(key, "created")
                log.info("linear_door_project_intent_done", reason="its link is there")
                continue
            await client.create_project_link(
                link_id=intent.link_id,
                project_id=intent.project_id,
                url=f"https://github.com/{repo}",
                label=GITHUB_LABEL,
            )
            store.complete_project_intent(key, "created")
            log.info("linear_door_project_linked")
        except (LinearAuthError, LinearRateLimited):
            raise
        except LinearError as exc:
            log.warning("linear_door_project_create_failed", error=str(exc)[:300])
            return


__all__ = [
    "GITHUB_LABEL",
    "NO_LINK",
    "PROJECTS_FILE",
    "SHARED_REPO",
    "TOO_MANY_LINKS",
    "TWO_REPOS",
    "ProjectMap",
    "ProjectRepo",
    "ensure_projects",
    "github_repo",
    "problem_words",
    "project_description",
    "projects_file_content",
    "registered_repositories",
    "repo_key",
    "short_name",
    "write_projects_file",
]
