"""From Linear issues to factory requests — the pure part of the Linear door.

Nothing here talks to Linear or the bus. It reads labels and relations, makes
correlation ids and builds the ``PlanningQueuedPayload`` (design section 1,
"A single issue" and "A mission"). The door (:mod:`.door`) decides when.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from jarvis.infrastructure.linear.client import LinearIssue, LinearIssueRef, LinearLabel
from jarvis.infrastructure.planning_intake_grammar import is_allowed_target_name

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.infrastructure.linear.projects import ProjectMap

#: Every comment the door writes starts with this.
COMMENT_PREFIX = "Factory: "
#: The words of the "sent" comment; a resumed send looks for them so the
#: comment is not written twice (attempt numbers come from the door's record).
SENT_WORDS = "Sent to the factory as"

# The wire's correlation-id rule (the same characters Forge checks).
CORRELATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# Forge's mission key rule: 1 to 12 letters or digits.
MISSION_KEY_RE = re.compile(r"^[A-Za-z0-9]{1,12}$")

_MISSION_PREFIX_RE = re.compile(r"^\s*mission\s*:\s*(\S.*?)\s*$", re.IGNORECASE)
_REPO_PREFIX_RE = re.compile(r"^\s*repo\s*:\s*(\S.*?)\s*$", re.IGNORECASE)
_SENT_RE = re.compile(re.escape(SENT_WORDS) + r"\s*`([A-Za-z0-9_-]+)`", re.IGNORECASE)

# Linear workflow-state types that take an issue out of a mission.
_FINISHED_STATE_TYPES = frozenset({"completed", "canceled", "duplicate"})

# Linear's issue relation reads "<issue> <type> <relatedIssue>": a relation of
# type "blocks" says its ``issue`` blocks its ``relatedIssue`` (schema
# ``IssueRelation``: "issue — the source issue ... from which the relation
# originates"; "relatedIssue — the target issue"; type values "blocks,
# duplicate, related"). ``Issue.inverseRelations`` lists the relations whose
# ``relatedIssue`` is this issue, so a "blocks" entry there names an issue
# that blocks this one.
BLOCKS = "blocks"


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def _norm(text: str | None) -> str:
    return " ".join((text or "").split()).casefold()


@dataclass(frozen=True)
class MissionLabel:
    """A mission label: its Linear id is the identity, its name the title."""

    label_id: str
    title: str


def mission_labels(issue: LinearIssue) -> list[MissionLabel]:
    """``mission: <name>``, or ``<name>`` inside a label group called ``mission``."""
    found: list[MissionLabel] = []
    for label in issue.labels:
        if _norm(label.parent_name) == "mission" and label.name.strip():
            found.append(MissionLabel(label_id=label.id, title=label.name.strip()))
            continue
        match = _MISSION_PREFIX_RE.match(label.name)
        if match:
            found.append(MissionLabel(label_id=label.id, title=match.group(1)))
    return found


def repo_labels(issue: LinearIssue) -> list[str]:
    """``repo: <name>``, or ``<name>`` inside a label group called ``repo``."""
    found: list[str] = []
    for label in issue.labels:
        if _norm(label.parent_name) == "repo" and label.name.strip():
            found.append(label.name.strip())
            continue
        match = _REPO_PREFIX_RE.match(label.name)
        if match:
            found.append(match.group(1))
    return found


def _is_no_sign_in(label: LinearLabel) -> bool:
    return _norm(label.name) == "no sign-in"


def no_sign_in(issue: LinearIssue) -> bool:
    return any(_is_no_sign_in(label) for label in issue.labels)


@dataclass(frozen=True)
class RepoChoice:
    """The repository for an issue, or the sentence saying why there is none.

    ``wait`` (no repository, no problem): the team's projects could not be
    read (or not whole) this poll, so the issue is decided on a later poll,
    silently.
    """

    repo: str | None
    problem: str | None = None
    wait: bool = False


def choose_repo(
    issue: LinearIssue, default_repo: str | None, projects: ProjectMap | None = None
) -> RepoChoice:
    """Which repository an issue goes to (design section 11.2, the decision table).

    1. One valid ``repo:`` label: that repository, whatever its project says.
       Two different ``repo:`` labels (or an unusable one): refused.
    2. No ``repo:`` label, in a project that maps to exactly one repository:
       that repository. In a project that maps to nothing, or a conflicting
       project: refused, naming the project and why. No fallback to the
       default.
    3. No ``repo:`` label and no project: ``default_repo``, else refused.

    ``projects`` is this poll's read of the team's projects; ``None`` when it
    could not be read whole, so an issue in a project waits. A project a whole
    read did not include is refused (C3).
    """
    names = list(dict.fromkeys(repo_labels(issue)))
    if len(names) > 1:
        listed = ", ".join(f"`{name}`" for name in names)
        return RepoChoice(
            None,
            f"This issue has more than one repo label ({listed}), so it was not sent. "
            "Keep one and move it to Todo again.",
        )
    if names:
        if not is_allowed_target_name(names[0]):
            return RepoChoice(
                None,
                f"The repo label `{names[0]}` is not a repository name the factory can use "
                "(letters, digits, '.', '_' and '-', with at most one '/'), so this issue "
                "was not sent.",
            )
        return RepoChoice(names[0])
    if issue.project_id:
        from jarvis.infrastructure.linear.projects import problem_words, unseen_project_words

        if projects is None:
            return RepoChoice(None, wait=True)
        mapped = projects.for_project(issue.project_id)
        if mapped is None:
            return RepoChoice(None, unseen_project_words())
        if mapped.repo is None:
            return RepoChoice(None, problem_words(mapped))
        return RepoChoice(mapped.repo)
    if default_repo:
        return RepoChoice(default_repo)
    return RepoChoice(
        None,
        "This issue was not sent because I do not know which repository it is for. "
        "Add a label `repo: <name>`.",
    )


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


def blockers_of(issue: LinearIssue) -> list[LinearIssueRef]:
    """The issues that block ``issue`` — the one place the direction is decided."""
    return [rel.other for rel in issue.inverse_relations if rel.type == BLOCKS]


def is_finished(state_type: str) -> bool:
    """Done, Canceled (or marked a duplicate): no longer part of a mission."""
    return state_type in _FINISHED_STATE_TYPES


def is_done(state_type: str) -> bool:
    return state_type == "completed"


# ---------------------------------------------------------------------------
# Ids
# ---------------------------------------------------------------------------


def feature_key(identifier: str) -> str:
    """``APP-12`` → ``APP12`` (Forge's mission key: 1 to 12 letters or digits)."""
    return identifier.replace("-", "")


def single_prefix(identifier: str) -> str:
    return f"lin-{identifier}-"


def mission_prefix(label_id: str) -> str:
    """``lin-m-<label id as 32 hex characters>-`` (design review R2)."""
    return f"lin-m-{label_id.replace('-', '').lower()}-"


def correlation_id(prefix: str, attempt: int) -> str:
    """``<prefix><attempt>``, refused unless the wire can carry it."""
    value = f"{prefix}{attempt}"
    if attempt < 1 or not CORRELATION_ID_RE.match(value):
        raise ValueError(f"not a usable correlation id: {value!r}")
    return value


def sent_ids_in(body: str) -> list[str]:
    """The correlation ids named by "Sent to the factory as `…`" in a comment."""
    if not body.lstrip().lower().startswith(COMMENT_PREFIX.strip().lower()):
        return []
    return _SENT_RE.findall(body)


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------


def sentence_of(issue: LinearIssue) -> str:
    """Title, a blank line, then the description as written."""
    title = issue.title.strip()
    description = issue.description.strip()
    return f"{title}\n\n{description}" if description else title


def content_hash(issue: LinearIssue) -> str:
    """What "the version sent" means for the edits-after-sending comment."""
    digest = hashlib.sha256()
    digest.update(issue.title.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(issue.description.encode("utf-8"))
    return digest.hexdigest()


def comment(text: str) -> str:
    return f"{COMMENT_PREFIX}{text}"


def sent_comment(cid: str) -> str:
    return comment(f"{SENT_WORDS} `{cid}`")


@dataclass(frozen=True)
class MissionFeature:
    issue: LinearIssue
    key: str
    needs: tuple[str, ...]
    no_sign_in: bool
    sentence: str


def mission_command(title: str, features: list[MissionFeature]) -> dict[str, Any]:
    """The ``queue_command`` Jarvis's Slack route and the harness both send."""
    return {
        "verb": "mission",
        "title": title,
        "features": [
            {
                "key": f.key,
                "needs": list(f.needs),
                "no_sign_in": f.no_sign_in,
                "sentence": f.sentence,
            }
            for f in features
        ],
    }


def mission_text(title: str, features: list[MissionFeature]) -> str:
    """The ``mission:`` text the harness builds from its mission file.

    Each feature is one line, as the Slack grammar reads it, so a sentence's
    own line breaks are folded into spaces here; Forge folds the sentence in
    ``queue_command`` the same way when it reads the mission.
    """
    lines = [f"mission: {title}"]
    for f in features:
        needs = f" (needs {', '.join(f.needs)})" if f.needs else ""
        sign = " [no sign-in]" if f.no_sign_in else ""
        lines.append(f"{f.key}{needs}{sign}: {' '.join(f.sentence.split())}")
    return "\n".join(lines)


#: Forge's limit on features in one mission.
MAX_MISSION_FEATURES = 20


def check_mission(command: dict[str, Any], mission_cid: str) -> str | None:
    """Forge's own mission rules, checked before sending; ``None`` when they pass.

    A copy of ``validate_mission`` in Forge's ``planning/missions_flow.py``
    (design review round 2, R4), so an obviously bad mission is stopped before
    it uses an attempt. Forge still makes the same checks. Returns the sentence
    saying what is wrong.
    """
    features = command.get("features") or []
    if not 1 <= len(features) <= MAX_MISSION_FEATURES:
        return (
            f"A mission has between 1 and {MAX_MISSION_FEATURES} issues, and this one "
            f"has {len(features)}."
        )
    seen: set[str] = set()
    for feature in features:
        key = str(feature.get("key") or "")
        if not MISSION_KEY_RE.fullmatch(key):
            return f"{key or 'An issue'} is not a usable key: a key is 1 to 12 letters or digits."
        if key in seen:
            return f"The key {key} is used twice."
        seen.add(key)
        if not " ".join(str(feature.get("sentence") or "").split()):
            return f"{key} has no title or description."
    needs = {str(f["key"]): [str(n) for n in f.get("needs") or []] for f in features}
    for key, wanted in needs.items():
        for needed in wanted:
            if needed not in seen:
                return f"{key} needs {needed}, which is not in this mission."
    # No circle: repeatedly take the features whose needs are all taken.
    placed: set[str] = set()
    while len(placed) < len(needs):
        ready = [k for k, w in needs.items() if k not in placed and all(n in placed for n in w)]
        if not ready:
            return "The issues' blocking links go round in a circle, so no issue could ever start."
        placed.update(ready)
    longest = max(seen, key=len)
    attempt_id = f"{mission_cid}-{longest}-a2"
    if len(attempt_id) > 128 or not CORRELATION_ID_RE.fullmatch(attempt_id):
        return "The mission's reference is too long to name its issues' builds."
    return None


def identifier_order(identifier: str) -> tuple[str, int]:
    team, _, number = identifier.rpartition("-")
    return (team, int(number) if number.isdigit() else 0)


# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------


def planning_payload(
    *,
    request_text: str,
    target_repo: str | None,
    owner_identity: str,
    cid: str,
    queue_command: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> Any:
    """The ``PlanningQueuedPayload`` for one send (design section 1)."""
    from nats_core.events import PlanningQueuedPayload

    stamp = now or datetime.now(UTC)
    # ``queue_command`` is an extra field the model allows (as the Slack route sends it).
    extra: dict[str, Any] = {"queue_command": queue_command} if queue_command is not None else {}
    return PlanningQueuedPayload(
        request_text=request_text,
        target_repo=target_repo,
        triggered_by="jarvis",
        originating_adapter="linear",
        originating_user=owner_identity,
        correlation_id=cid,
        parent_request_id=None,
        requested_at=stamp,
        queued_at=stamp,
        **extra,
    )


__all__ = [
    "BLOCKS",
    "COMMENT_PREFIX",
    "CORRELATION_ID_RE",
    "MAX_MISSION_FEATURES",
    "MISSION_KEY_RE",
    "MissionFeature",
    "MissionLabel",
    "RepoChoice",
    "blockers_of",
    "check_mission",
    "choose_repo",
    "comment",
    "content_hash",
    "correlation_id",
    "feature_key",
    "identifier_order",
    "is_done",
    "is_finished",
    "mission_command",
    "mission_labels",
    "mission_prefix",
    "mission_text",
    "no_sign_in",
    "planning_payload",
    "repo_labels",
    "sent_comment",
    "sent_ids_in",
    "sentence_of",
    "single_prefix",
]
