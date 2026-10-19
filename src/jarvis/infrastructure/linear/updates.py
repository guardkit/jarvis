"""Project updates after each merge (design sections 11.4 and 11.5).

Once per merge to main of Linear-originated work in a mapped project, the door
posts a short project update to Linear: what was delivered, what is open and
what it cost, with Linear's own on track / at risk / off track health. The
dashboard computes the figures and writes ``project-summaries.json``; the door
only reads that file, at the moment it posts, and formats.

* :func:`read_summary` reads the dashboard's file and judges its freshness at
  read time (11.5): the whole file unavailable when unset, missing,
  unreadable, malformed or not ``version`` 1; open issues and health
  unavailable when now is past ``forge.valid_until`` (or it is missing); cost
  "not available" when never read or read over an hour ago, and every cost
  figure "may be incomplete" when read over ``cost.stale_after_seconds`` ago.
* :func:`update_health` and :func:`update_body` decide the health and write
  the text (pure).
* :func:`post_update_once` posts it through the door's write-once guard, with
  its own reference.

Costs are shown exactly as the dashboard states them (its ``value`` or
``label``, ``reason``, "estimated", "may be incomplete"): nominal US dollars.
A missing figure is "not available", never zero, and unknown health is never
shown as on track.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from jarvis.infrastructure.linear.projects import repo_key
from jarvis.infrastructure.linear.report import write_once_to
from jarvis.infrastructure.linear.store import DoorStore

logger = structlog.get_logger(__name__)

SUMMARY_VERSION = 1
#: The pages' cost rule, when the file does not say (11.5).
DEFAULT_COST_STALE_SECONDS = 600
#: Cost read longer ago than this is "not available" (11.5).
COST_UNAVAILABLE_AFTER = timedelta(hours=1)
#: Titles of open Linear issues listed in an update.
MAX_OPEN_TITLES = 5

NOT_AVAILABLE = "not available"
HEALTH_NOT_AVAILABLE = "Project health: not available from the dashboard."

#: The dashboard's health → Linear's ``ProjectUpdateHealthType``.
HEALTH_TO_LINEAR = {"on_track": "onTrack", "at_risk": "atRisk", "off_track": "offTrack"}
_HEALTH_WORDS = {"onTrack": "on track", "atRisk": "at risk", "offTrack": "off track"}


def _parse_time(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        stamp = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else stamp.replace(tzinfo=UTC)


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# The dashboard's summary file (11.5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    """The dashboard's summary as judged at the moment of reading."""

    available: bool = False
    #: Open issues and health can be used (the Forge evidence is in date).
    forge_fresh: bool = False
    #: ``fresh``, ``stale`` (shown with "may be incomplete") or ``unavailable``.
    cost: str = "unavailable"
    cost_read_at: datetime | None = None
    projects: dict[str, Any] = field(default_factory=dict)
    attempts: dict[str, Any] = field(default_factory=dict)

    def project(self, repo: str) -> dict[str, Any] | None:
        for name, entry in self.projects.items():
            if repo_key(str(name)) == repo_key(repo) and isinstance(entry, dict):
                return entry
        return None


UNAVAILABLE = Summary()


def read_summary(path: Path | None, *, now: datetime | None = None) -> Summary:
    """Read ``project-summaries.json`` and judge it now (11.5)."""
    if path is None:
        return UNAVAILABLE
    moment = now or datetime.now(UTC)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        logger.info("linear_door_summary_unavailable", error=type(exc).__name__)
        return UNAVAILABLE
    if not isinstance(data, dict) or data.get("version") != SUMMARY_VERSION:
        logger.info("linear_door_summary_unavailable", error="not version 1")
        return UNAVAILABLE
    forge = data.get("forge")
    forge = forge if isinstance(forge, dict) else {}
    valid_until = _parse_time(forge.get("valid_until"))
    forge_fresh = valid_until is not None and moment <= valid_until

    cost = data.get("cost")
    cost = cost if isinstance(cost, dict) else {}
    read_at = _parse_time(cost.get("read_at"))
    limit = cost.get("stale_after_seconds")
    if not isinstance(limit, int | float) or limit <= 0:
        limit = DEFAULT_COST_STALE_SECONDS
    stale_after = timedelta(seconds=limit)
    if read_at is None or moment - read_at > COST_UNAVAILABLE_AFTER:
        cost_state = "unavailable"
    elif moment - read_at > stale_after:
        cost_state = "stale"
    else:
        cost_state = "fresh"
    projects = data.get("projects")
    attempts = data.get("attempts")
    return Summary(
        available=True,
        forge_fresh=forge_fresh,
        cost=cost_state,
        cost_read_at=read_at,
        projects=projects if isinstance(projects, dict) else {},
        attempts=attempts if isinstance(attempts, dict) else {},
    )


def cost_words(slot: Any, summary: Summary) -> str:
    """One cost figure, exactly as the dashboard states it (11.4, 11.5)."""
    if not summary.available or summary.cost == "unavailable" or not isinstance(slot, dict):
        return NOT_AVAILABLE
    value = str(slot.get("value") or "").strip()
    label = str(slot.get("label") or "").strip()
    reason = str(slot.get("reason") or "").strip()
    if value:
        text = f"{value} nominal" + (" (part estimated)" if slot.get("estimated") else "")
    else:
        text = label or NOT_AVAILABLE
    if reason:
        text += f" ({reason.rstrip('.')})"
    if summary.cost == "stale" and summary.cost_read_at is not None:
        text += f"; may be incomplete: cost data last read at {_stamp(summary.cost_read_at)}"
    elif slot.get("stale") and str(slot.get("stale_text") or "").strip():
        text += f"; {str(slot['stale_text']).strip()}"
    return text


# ---------------------------------------------------------------------------
# What the update says (11.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Delivered:
    """What one merge delivered, from Forge's record and Linear."""

    correlation_id: str
    repo: str
    landed: list[tuple[str, str]]  # (identifier, title)
    not_landed: list[tuple[str, str]] = field(default_factory=list)
    commit: str | None = None
    mission_title: str | None = None
    #: The deploy after this merge failed: the reader's words, else "".
    deploy_failed: str = ""
    is_mission: bool = False


def update_health(delivered: Delivered, summary: Summary) -> tuple[str | None, str]:
    """Linear's health value (or ``None`` to leave it out) and the line saying it."""
    if delivered.deploy_failed:
        return "offTrack", "Project health: off track (the deploy after this merge failed)."
    if delivered.not_landed:
        return "offTrack", "Project health: off track (part of the mission did not land)."
    entry = summary.project(delivered.repo) if summary.available else None
    if not summary.forge_fresh or entry is None:
        return None, HEALTH_NOT_AVAILABLE
    health = HEALTH_TO_LINEAR.get(str(entry.get("health") or ""))
    if health is None:
        return None, HEALTH_NOT_AVAILABLE
    return health, f"Project health: {_HEALTH_WORDS[health]} (from the dashboard)."


def _issue_line(identifier: str, title: str) -> str:
    title = " ".join(title.split())
    return f"- {identifier} {title}".rstrip()


def update_body(
    delivered: Delivered,
    summary: Summary,
    open_in_linear: list[tuple[str, str]],
    health_line: str,
) -> str:
    """The update's text: delivered, open, cost and health, in plain English."""
    lines: list[str] = ["**Delivered**"]
    commit = f" as `{delivered.commit}`" if delivered.commit else ""
    if delivered.is_mission:
        title = f" “{delivered.mission_title}”" if delivered.mission_title else ""
        lines.append(f"The mission{title} merged into the main branch{commit}.")
        if delivered.landed:
            lines.append("Landed:")
            lines.extend(_issue_line(i, t) for i, t in delivered.landed)
        if delivered.not_landed:
            lines.append("Did not land:")
            lines.extend(_issue_line(i, t) for i, t in delivered.not_landed)
    else:
        lines.extend(_issue_line(i, t) for i, t in delivered.landed)
        lines.append(f"Merged into the main branch{commit}.")
    if delivered.deploy_failed:
        lines.append(f"The deploy after this merge failed: {delivered.deploy_failed.rstrip('.')}.")

    lines += ["", "**Open**"]
    if open_in_linear:
        count = len(open_in_linear)
        noun = "issue" if count == 1 else "issues"
        lines.append(f"In Linear: {count} {noun} not done.")
        lines.extend(_issue_line(i, t) for i, t in open_in_linear[:MAX_OPEN_TITLES])
        if count > MAX_OPEN_TITLES:
            lines.append(f"- and {count - MAX_OPEN_TITLES} more")
    else:
        lines.append("In Linear: no issues left open in this project.")
    entry = summary.project(delivered.repo) if summary.available else None
    if summary.forge_fresh and entry is not None:
        words = " ".join(str(entry.get("open_issues_words") or "").split())
        total = entry.get("open_issues_total")
        if words:
            lines.append(f"In the factory: {words.rstrip('.')}.")
        elif isinstance(total, int):
            lines.append(f"In the factory: {total} open.")
        else:
            lines.append("In the factory: not available from the dashboard.")
    else:
        lines.append("In the factory: not available from the dashboard.")

    lines += ["", "**Cost** (nominal US dollars, as the dashboard shows them)"]
    attempt = summary.attempts.get(delivered.correlation_id) if summary.available else None
    lines.append(f"- This merge: {cost_words(attempt, summary)}")
    lines.append(
        f"- This week: {cost_words((entry or {}).get('spend_week') if entry else None, summary)}"
    )
    lines.append(
        f"- Project total: "
        f"{cost_words((entry or {}).get('spend_total') if entry else None, summary)}"
    )
    lines += ["", health_line]
    return "\n".join(lines)


class UpdateHeld(Exception):
    """An update not found on its project is not created now (Codex review R5).

    ``wait``: the projects could not be read whole this poll, so it is tried
    again; otherwise the project is no longer active and the update is given
    up without being created.
    """

    def __init__(self, why: str, *, wait: bool) -> None:
        super().__init__(why)
        self.wait = wait


async def post_update_once(
    client: Any,
    store: DoorStore,
    project_id: str,
    body: str,
    ref: str,
    *,
    health: str | None,
    before_create: Callable[[], None] | None = None,
) -> str:
    """Post the update once: its reference is recorded before it is posted
    and ends its text, so an update whose posting was not confirmed is looked
    for among the project's updates before it is posted again.

    ``before_create`` runs only when no update was found and one is about to
    be created; it raises :class:`UpdateHeld` to stop the creation. An update
    already found counts as posted whatever the project's state now.
    """

    async def find(marker: str) -> str | None:
        for update in await client.project_updates(project_id):
            if marker in update.body:
                return str(update.id)
        return None

    async def create(text: str) -> str:
        if before_create is not None:
            before_create()
        return str(await client.create_project_update(project_id, text, health=health))

    return await write_once_to(store, ref, project_id, body, find=find, create=create)


__all__ = [
    "HEALTH_NOT_AVAILABLE",
    "HEALTH_TO_LINEAR",
    "NOT_AVAILABLE",
    "Delivered",
    "Summary",
    "UpdateHeld",
    "cost_words",
    "post_update_once",
    "read_summary",
    "update_body",
    "update_health",
]
