"""What Forge's record of an attempt means for its Linear issues (design section 2).

Pure: given an outcome read by :mod:`.forge_record`, these say which progress
comment each issue is owed now (a :class:`Step`, written once per change) and,
when the attempt has ended, where each issue ends up (a :class:`Final`). The
door (:mod:`.report`) compares a step's ``key`` with what it last wrote, so a
restart catches up with one comment per change and never repeats one.

The table, as built:

* single issue: build running → "Building"; publication under way → its
  reason; publication stopped → its reason and what someone has to do, the
  issue stays open; on main → Done with the merged commit (and the failed
  deploy, if it failed); already done → Done with the proof; everything else
  that ends an attempt → Backlog with the reason.
* mission: running → "Building" on every member; each member's feature
  landed, failed or held → one comment on that member; publication as above
  on every member; on main → only the members whose keys landed are Done, the
  others Backlog with their reason; any other end → every member Backlog.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jarvis.infrastructure.linear import forge_record as fr
from jarvis.infrastructure.linear.mapping import feature_key

DONE = "done"
BACKLOG = "backlog"

#: Phases that need nothing written: the card itself, when there is one, is
#: written from the bus (or the record), not as progress.
QUIET_PHASES = frozenset(
    {
        fr.QUEUED,
        fr.PLANNING,
        fr.PLAN_CARD_OPEN,
        fr.BUILD_QUEUED,
        fr.MERGE_CARD_OPEN,
        fr.MISSION_READY,
        fr.UNFILED,
    }
)

#: Plain words for each way an attempt ends without a merge.
_ENDED_WORDS = {
    fr.REFUSED_BUILD: "the build was refused",
    fr.WITHDRAWN: "withdrawn from the factory's queue",
    fr.BLOCKED: "blocked in the factory's queue",
    fr.PLANNING_FAILED: "planning did not finish",
    fr.BUILD_FAILED: "the build failed",
    fr.MERGE_DECLINED: "the merge was declined",
    fr.MERGE_FAILED: "the merge failed",
    fr.PLAN_REJECTED: "the plan was rejected",
    fr.NOT_STARTED: "the mission did not start",
    fr.NOT_MERGED: "the mission was not merged",
}

_AGAIN = "Moved back to Backlog; moving it to Todo sends it again."


@dataclass(frozen=True)
class Step:
    """One progress comment: written when ``key`` differs from the last one
    written under ``topic`` for this issue and attempt."""

    topic: str
    key: str
    text: str  # without the "Factory: " prefix


@dataclass(frozen=True)
class Final:
    """Where an issue ends up when its attempt ends, and the comment saying why."""

    target: str  # DONE or BACKLOG
    text: str  # without the "Factory: " prefix


def is_mission(correlation_id: str) -> bool:
    return correlation_id.startswith("lin-m-")


def _sentence(text: str) -> str:
    text = " ".join(str(text).split()).rstrip(".")
    return (text[:1].upper() + text[1:] + ".") if text else ""


def phase_step(outcome: Any) -> Step | None:
    """The comment every issue of the attempt is owed for its phase, if any."""
    phase = outcome.phase
    if outcome.ended or phase in QUIET_PHASES:
        return None
    if phase in (fr.BUILDING, fr.MISSION_RUNNING):
        return Step("phase", "building", "Building.")
    if phase == fr.PUBLICATION_IN_FLIGHT:
        return Step("phase", phase, _sentence(outcome.reason or "the merge is being published"))
    if phase == fr.PUBLICATION_STOPPED:
        reason = " ".join(str(outcome.reason or "no reason was given").split()).rstrip(".")
        return Step(
            "phase",
            f"{phase}|{outcome.reason}",
            f"The merge was approved but publishing stopped: {reason}. Someone needs to sort "
            "this out before it can finish; the details are in Slack.",
        )
    # A phase this door does not know yet: say it once, plainly.
    return Step("phase", phase, _sentence(outcome.reason or phase))


def key_step(attempt: Any) -> Step | None:
    """A mission member's own comment for its feature's latest attempt."""
    key = f"{attempt.status}:{attempt.attempt}"
    reason = _sentence(attempt.reason or "no reason was given")
    if attempt.status == "LANDED":
        return Step("key", key, "Landed on the mission branch.")
    if attempt.status == "FAILED":
        return Step(
            "key",
            key,
            f"This part of the mission failed: {reason} "
            "It stays In Progress until the mission finishes.",
        )
    if attempt.status == "HELD":
        return Step(
            "key",
            key,
            f"This part of the mission is held: {reason} "
            "It stays In Progress until the mission finishes.",
        )
    return None


def _merged_words(outcome: Any) -> str:
    commit = f" as `{outcome.j_commit}`" if outcome.j_commit else ""
    if outcome.phase == fr.ON_MAIN_DEPLOY_FAILED:
        return f"Merged into the main branch{commit}, but {_deploy_failure(outcome.reason)}"
    return f"Merged into the main branch{commit}."


def _deploy_failure(reason: str) -> str:
    """ "its deploy failed: …" from the reader's "merged into main, but its
    deploy failed: …"."""
    text = " ".join(str(reason or "").split()).rstrip(".")
    _, sep, after = text.partition("but ")
    if sep and after:
        return f"{after}."
    return f"its deploy failed: {text}." if text else "its deploy failed."


def deploy_failed_words(outcome: Any) -> str:
    """The follow-up for an issue already Done when its deploy then failed."""
    text = " ".join(str(outcome.reason or "").split()).rstrip(".")
    _, sep, after = text.partition("deploy failed: ")
    return f"The deploy failed: {after}." if sep and after else "The deploy failed."


def _ended_words(outcome: Any) -> str:
    words = _ENDED_WORDS.get(outcome.phase, "the attempt ended")
    reason = " ".join(str(outcome.reason or "").split()).rstrip(".")
    if reason and reason.lower() != words.lower():
        return f"Ended without a merge — {words}: {reason}. {_AGAIN}"
    return f"Ended without a merge — {words}. {_AGAIN}"


def finals(outcome: Any, issues: list[tuple[str, str | None]]) -> dict[str, Final]:
    """Each issue's end, for an attempt Forge's record shows has ended.

    ``issues`` are ``(issue id, identifier)``; a mission member's key is its
    identifier without the hyphen.
    """
    on_main = outcome.phase in (fr.ON_MAIN, fr.ON_MAIN_DEPLOY_FAILED, fr.ON_MAIN_REPORT_PENDING)
    if not outcome.ended and outcome.phase != fr.ON_MAIN_REPORT_PENDING:
        return {}
    if not is_mission(outcome.correlation_id):
        if on_main:
            # A failed deploy is said in its own notice (report.py), so the
            # merge and the deploy are each said once, whenever each is known.
            commit = f" as `{outcome.j_commit}`" if outcome.j_commit else ""
            final = Final(DONE, f"Merged into the main branch{commit}.")
        elif outcome.phase == fr.ALREADY_DONE:
            proof = "".join(f"\n- {line}" for line in getattr(outcome, "proof", ()) or ())
            final = Final(
                DONE, f"Already done: the factory found this in the code and built nothing.{proof}"
            )
        else:
            final = Final(BACKLOG, _ended_words(outcome))
        return {issue_id: final for issue_id, _ in issues}

    if not on_main:
        final = Final(BACKLOG, _ended_words(outcome))
        return {issue_id: final for issue_id, _ in issues}
    landed = set(outcome.landed_keys)
    reasons = {a.key: a.reason for a in outcome.attempts}
    found: dict[str, Final] = {}
    for issue_id, identifier in issues:
        key = feature_key(identifier or "")
        if key in landed:
            found[issue_id] = Final(
                DONE, _merged_words(outcome).replace("Merged", "Merged with the mission", 1)
            )
        else:
            why = reasons.get(key) or "it did not land on the mission branch"
            found[issue_id] = Final(
                BACKLOG,
                f"The mission merged without this issue: {' '.join(str(why).split()).rstrip('.')}. "
                f"{_AGAIN}",
            )
    return found


__all__ = [
    "BACKLOG",
    "DONE",
    "QUIET_PHASES",
    "Final",
    "Step",
    "deploy_failed_words",
    "finals",
    "is_mission",
    "key_step",
    "phase_step",
]
