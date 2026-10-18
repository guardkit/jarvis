"""The Linear door, factory → Linear (design section 2, stage 4).

A fake Linear, a captured bus, a fake bus feed and a fake of Forge's record
(the reader's own outcome types), plus one test through the real reader on a
Forge record built from Forge's schema. All names and ids are made up.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from jarvis.infrastructure.linear import forge_record as fr
from jarvis.infrastructure.linear.cards import (
    AUTH_CONFIRMATION,
    SLACK_ONLY_ENDING,
    https_link,
    parse_approvers,
    parse_card,
    parse_reply,
)
from jarvis.infrastructure.linear.client import LinearError
from jarvis.infrastructure.linear.door import DoorSettings, LinearDoor, RecordedAttempt
from jarvis.infrastructure.linear.mapping import mission_prefix
from jarvis.infrastructure.linear.report import (
    CARDS,
    NOTIFICATIONS,
    UNCONFIRMED_ANSWER,
    UNFILED_NOTICE,
    BusMessage,
    ForgeAttempts,
    NatsBusFeed,
)
from jarvis.infrastructure.linear.store import DoorStore

from .fake_linear import (
    CapturedAnswers,
    CapturedBus,
    FakeAttempts,
    FakeFeed,
    FakeIntake,
    FakeLinear,
    internal_error,
    refused,
    server_error,
)

OWNER = "U0OWNER0001"
OWNER_LINEAR = "user-owner"
OWNER_IDENTITY = "U0OWNER0001"
STRANGER = "user-stranger"
SCHEMA = Path(__file__).parents[3] / "infrastructure" / "linear" / "forge_schema_dbd40c7e.sql"
_REF = re.compile(r"\n\n_factory note [0-9a-f]{12}_$")


def plain(body: str) -> str:
    """A door comment without its closing ``_factory note …_`` line."""
    return _REF.sub("", body)


class Harness:
    def __init__(self, tmp_path: Path, *, store_name: str = "door.sqlite3") -> None:
        self.tmp_path = tmp_path
        self.linear = FakeLinear()
        self.bus = CapturedBus()
        self.attempts = FakeAttempts()
        self.intake = FakeIntake()
        self.feed = FakeFeed()
        self.answers = CapturedAnswers()
        self.store_name = store_name
        self.client = self.linear.client()
        self.door = self._door()

    def _door(self) -> LinearDoor:
        self.store = DoorStore(self.tmp_path / self.store_name)
        return LinearDoor(
            client=self.client,
            publisher=self.bus,
            store=self.store,
            settings=DoorSettings(
                team="ENG",
                owner_identity=OWNER,
                default_repo="example-repo",
                approvers={OWNER_LINEAR: OWNER_IDENTITY},
            ),
            attempts=self.attempts,
            intake=self.intake,
            feed=self.feed,
            answers=self.answers,
        )

    def restart(self) -> None:
        """A new door on the same record, as after a restart."""
        self.store.close()
        self.door = self._door()

    async def poll(self, times: int = 1) -> None:
        for _ in range(times):
            await self.door.poll_once()

    def factory(self, comments: list[str]) -> list[str]:
        """The door's own comments, minus its "sent" comment and the refs."""
        return [plain(c) for c in comments if "Sent to the factory as" not in c]

    def card_comments(self, issue: Any) -> list[Any]:
        return [
            c
            for c in self.linear.top_comments_on(issue)
            if "waiting" in c.body and "card" in c.body
        ]


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


def single(cid: str, phase: str, ended: bool = False, reason: str = "", **kw: Any) -> Any:
    return fr.SingleOutcome(cid, phase, ended, reason, **kw)


def mission(cid: str, phase: str, ended: bool = False, **kw: Any) -> Any:
    return fr.MissionOutcome(cid, phase, ended, **kw)


async def sent_single(h: Harness, title: str = "Add a dark mode") -> Any:
    issue = h.linear.issue(title)
    await h.poll()
    assert h.linear.state_name(issue) == "In Progress"
    return issue


async def sent_mission(h: Harness) -> tuple[str, Any, Any]:
    label = h.linear.label("mission: Sharing")
    a = h.linear.issue("Share a note", labels=[label])
    b = h.linear.issue("Revoke a share", labels=[label], blocked_by=[a.id])
    await h.poll()
    cid = f"{mission_prefix(label)}1"
    assert h.bus.payloads()[0]["correlation_id"] == cid
    return cid, a, b


# -- card messages in the shapes of the 17 to 18 October trials ------------------


def card_message(
    subject: str,
    request_id: str,
    *,
    cid: str | None,
    details: dict[str, Any],
    action: str = "Something is waiting for your answer.",
) -> BusMessage:
    from nats_core import EventType, MessageEnvelope
    from nats_core.events import ApprovalRequestPayload

    envelope = MessageEnvelope(
        source_id="forge",
        event_type=EventType.APPROVAL_REQUEST,
        correlation_id=cid,
        payload=ApprovalRequestPayload(
            request_id=request_id,
            agent_id="forge",
            action_description=action,
            risk_level="medium",
            details=details,
        ).model_dump(mode="json"),
    )
    return BusMessage(subject, envelope.model_dump_json().encode(), datetime.now(UTC))


def plan_card(cid: str, request_id: str = "req-plan-1") -> BusMessage:
    return card_message(
        f"agents.approval.forge.plan-{cid}",
        request_id,
        cid=cid,
        details={
            "build_id": f"plan-{cid}",
            "checkpoint_type": "product_docs_spec_digest",
            "correlation_id": cid,
            "summary": {
                "title": "The spec is ready — here's what will be built",
                "feature": "Dark mode",
                "what_happened": "The machine read the code and wrote a spec.",
                "what_it_will_do": [
                    {"sentence": "A toggle switches the theme.", "tags": ["@key-example"]}
                ],
                "what_the_machine_assumed": [
                    {"assumption": "The setting is per browser.", "why": "the input did not say"}
                ],
                "assumptions": [{"id": "A1", "text": "per browser"}, {"id": "A2", "text": "x"}],
            },
        },
        action="The spec for Dark mode is ready.",
    )


def merge_card(
    cid: str, build_id: str, *, app: str = "https://preview.example/app", report: str = ""
) -> BusMessage:
    evidence = {"state": "ready", "app_url": app}
    if report:
        evidence["report_url"] = report
    return card_message(
        "agents.approval.forge.merge-FEAT-1",
        f"merge-{build_id}",
        cid=cid,
        details={
            "kind": "merge_deploy_offer",
            "build_id": build_id,
            "feature_id": "FEAT-1",
            "review_evidence": evidence,
            "resume_options": ["approve", "reject"],
        },
        action="Merge autobuild/FEAT-1 into main?",
    )


def gate_card(cid: str, build_id: str) -> BusMessage:
    return card_message(
        f"agents.approval.forge.{build_id}",
        f"{build_id}:autobuild:0",
        cid=cid,
        details={"build_id": build_id, "stage_label": "autobuild"},
        action="Start the build?",
    )


def mission_plan_card(cid: str, mission_id: str) -> BusMessage:
    return card_message(
        f"agents.approval.forge.mission-{mission_id}",
        "req-mission-plan",
        cid=cid,
        details={
            "build_id": f"mission-{mission_id}",
            "mission_id": mission_id,
            "rationale": 'Mission "Sharing" — 2 features on example-repo\nFirst: ENG1  Share',
            "stage_label": "the mission plan",
        },
        action='The mission "Sharing" is waiting for your go-ahead.',
    )


# ---------------------------------------------------------------------------
# Progress and status moves: a single issue
# ---------------------------------------------------------------------------


async def test_building_is_one_comment_across_polls_and_restarts(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING, reason="planning (running)")
    await h.poll()
    assert h.factory(h.linear.comments_on(issue)) == []

    h.attempts.outcomes[cid] = single(cid, fr.BUILDING, reason="the build is running")
    await h.poll(2)
    h.restart()
    h.attempts.outcomes[cid] = single(cid, fr.BUILDING, reason="built; the merge card is next")
    await h.poll()
    assert h.factory(h.linear.comments_on(issue)) == ["Factory: Building."]


async def test_on_main_is_done_with_the_commit_and_ends_the_attempt(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(
        cid, fr.ON_MAIN, True, "merged into main (published)", j_commit="abc1234"
    )
    await h.poll(2)
    assert h.factory(h.linear.comments_on(issue)) == [
        "Factory: Merged into the main branch as `abc1234`."
    ]
    assert h.linear.state_name(issue) == "Done"
    assert h.store.reservations() == {}


async def test_on_main_with_a_failed_deploy_says_so(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(
        cid,
        fr.ON_MAIN_DEPLOY_FAILED,
        True,
        "merged into main, but its deploy failed: the health check timed out",
        j_commit="abc1234",
    )
    await h.poll()
    (only,) = h.factory(h.linear.comments_on(issue))
    assert only == (
        "Factory: Merged into the main branch as `abc1234`, but its deploy failed: "
        "the health check timed out."
    )
    assert h.linear.state_name(issue) == "Done"


@pytest.mark.parametrize(
    ("phase", "reason", "words"),
    [
        (fr.PLANNING_FAILED, "the plan was rejected by the approver", "planning did not finish"),
        (fr.WITHDRAWN, "withdrawn by an operator", "withdrawn from the factory's queue"),
        (fr.BLOCKED, "the repository is not registered", "blocked in the factory's queue"),
        (fr.REFUSED_BUILD, "the build was refused: path policy", "the build was refused"),
        (fr.BUILD_FAILED, "tests failed", "the build failed"),
        (fr.MERGE_DECLINED, "approver declined the merge card", "the merge was declined"),
        (fr.MERGE_FAILED, "the candidate no longer applies", "the merge failed"),
    ],
)
async def test_endings_without_a_merge_go_to_backlog_with_the_reason(
    h: Harness, phase: str, reason: str, words: str
) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, phase, True, reason)
    await h.poll(2)
    (only,) = h.factory(h.linear.comments_on(issue))
    assert only.startswith(f"Factory: Ended without a merge — {words}")
    assert reason.split(": ")[-1] in only
    assert "moving it to Todo sends it again" in only
    assert h.linear.state_name(issue) == "Backlog"
    assert h.store.reservations() == {}


async def test_already_done_is_done_with_the_proof(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(
        cid,
        fr.ALREADY_DONE,
        True,
        "already done",
        proof=("web/theme.ts:12 - the toggle exists",),
    )
    await h.poll()
    (only,) = h.factory(h.linear.comments_on(issue))
    assert only.startswith(
        "Factory: Already done: the factory found this in the code and built nothing."
    )
    assert "- web/theme.ts:12 - the toggle exists" in only
    assert h.linear.state_name(issue) == "Done"


async def test_publication_in_flight_then_stopped_keeps_the_issue_open(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(
        cid,
        fr.PUBLICATION_IN_FLIGHT,
        reason="approver approved the merge; it is being joined, checked and published",
    )
    await h.poll(2)
    h.attempts.outcomes[cid] = single(
        cid,
        fr.PUBLICATION_STOPPED,
        reason="the remote refused the push",
    )
    await h.poll(2)
    comments = h.factory(h.linear.comments_on(issue))
    assert comments[0] == (
        "Factory: Approver approved the merge; it is being joined, checked and published."
    )
    assert comments[1] == (
        "Factory: The merge was approved but publishing stopped: the remote refused the push. "
        "Someone needs to sort this out before it can finish; the details are in Slack."
    )
    assert len(comments) == 2
    assert h.linear.state_name(issue) == "In Progress"
    assert h.store.reservations() == {issue.id: cid}


async def test_an_issue_moved_back_to_todo_keeps_its_retry(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.linear.move(issue, "Todo")  # a person retries while the attempt is open
    h.attempts.outcomes[cid] = single(cid, fr.BUILD_FAILED, True, "tests failed")
    await h.poll()
    # Not moved to Backlog: it is sent again as the next attempt at once.
    assert [p["correlation_id"] for p in h.bus.payloads()] == [cid, "lin-ENG-1-2"]
    assert h.linear.state_name(issue) == "In Progress"
    assert ("ENG-1", "Backlog") not in h.linear.moves


async def test_a_failed_linear_write_while_ending_repeats_nothing(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.BUILD_FAILED, True, "tests failed")
    h.linear.fail_next["DoorIssueMove"] = [server_error()]
    await h.poll()  # logged for this attempt alone; the poll carries on
    assert h.store.reservations() == {issue.id: cid}  # not ended until Linear is written
    await h.poll()
    assert len(h.factory(h.linear.comments_on(issue))) == 1
    assert h.linear.state_name(issue) == "Backlog"
    assert h.store.reservations() == {}


async def test_one_attempt_linear_refuses_does_not_hold_up_the_others(h: Harness) -> None:
    gone = await sent_single(h, "Deleted later")
    kept = await sent_single(h, "Still here")
    h.linear.gone.add(gone.id)
    h.attempts.outcomes["lin-ENG-1-1"] = single("lin-ENG-1-1", fr.BUILDING)
    h.attempts.outcomes["lin-ENG-2-1"] = single("lin-ENG-2-1", fr.BUILDING)
    await h.poll(2)
    assert h.factory(h.linear.comments_on(kept)) == ["Factory: Building."]


async def test_unfiled_request_is_noted_once_after_an_hour(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.UNFILED, reason="not recorded")
    await h.poll(2)
    assert h.factory(h.linear.comments_on(issue)) == []
    old = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    h.store.set_progress(cid, "", "unfiled_since", old)
    await h.poll(2)
    assert h.factory(h.linear.comments_on(issue)) == [f"Factory: {UNFILED_NOTICE}"]
    assert h.linear.state_name(issue) == "In Progress"
    assert h.store.reservations() == {issue.id: cid}


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------


def key(k: str, status: str, reason: str | None = None, attempt: int = 1) -> Any:
    return fr.KeyAttempt(k, attempt, status, reason, f"m-1-{k}-a{attempt}")


async def test_partial_mission_merge_moves_only_landed_members_to_done(h: Harness) -> None:
    cid, a, b = await sent_mission(h)
    h.attempts.outcomes[cid] = mission(cid, fr.MISSION_RUNNING, mission_id="m-1")
    await h.poll()
    h.attempts.outcomes[cid] = mission(
        cid,
        fr.MISSION_RUNNING,
        mission_id="m-1",
        attempts=(key("ENG1", "LANDED"), key("ENG2", "FAILED", "tests failed")),
        landed_keys=("ENG1",),
    )
    await h.poll(2)
    h.restart()
    await h.poll()
    assert h.factory(h.linear.comments_on(a)) == [
        "Factory: Building.",
        "Factory: Landed on the mission branch.",
    ]
    assert h.factory(h.linear.comments_on(b)) == [
        "Factory: Building.",
        "Factory: This part of the mission failed: Tests failed. "
        "It stays In Progress until the mission finishes.",
    ]
    assert h.linear.state_name(b) == "In Progress"

    h.attempts.outcomes[cid] = mission(
        cid,
        fr.ON_MAIN,
        True,
        mission_id="m-1",
        status="MERGED",
        attempts=(key("ENG1", "LANDED"), key("ENG2", "FAILED", "tests failed")),
        landed_keys=("ENG1",),
        j_commit="def5678",
    )
    await h.poll(2)
    assert h.factory(h.linear.comments_on(a))[-1] == (
        "Factory: Merged with the mission into the main branch as `def5678`."
    )
    assert h.factory(h.linear.comments_on(b))[-1] == (
        "Factory: The mission merged without this issue: tests failed. "
        "Moved back to Backlog; moving it to Todo sends it again."
    )
    assert h.linear.state_name(a) == "Done"
    assert h.linear.state_name(b) == "Backlog"
    assert h.store.reservations() == {}


@pytest.mark.parametrize(
    "phase", [fr.NOT_MERGED, fr.NOT_STARTED, fr.PLAN_REJECTED, fr.MERGE_DECLINED]
)
async def test_mission_ending_without_a_merge_moves_every_member_to_backlog(
    h: Harness, phase: str
) -> None:
    cid, a, b = await sent_mission(h)
    h.attempts.outcomes[cid] = mission(cid, phase, True, reason="the approver said no")
    await h.poll()
    for issue in (a, b):
        (only,) = h.factory(h.linear.comments_on(issue))
        assert only.startswith("Factory: Ended without a merge")
        assert h.linear.state_name(issue) == "Backlog"
    assert h.store.reservations() == {}


# ---------------------------------------------------------------------------
# Cards from the bus
# ---------------------------------------------------------------------------


async def test_plan_card_is_posted_once_with_its_summary(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    message = plan_card(cid)
    h.feed.push(CARDS, message)
    await h.poll()
    h.feed.push(CARDS, message)  # delivered again after a restart
    h.restart()
    await h.poll()
    (card,) = h.card_comments(issue)
    assert card.body.startswith("Factory: **The plan card is waiting for your answer.**")
    assert "A toggle switches the theme. _(the main one)_" in card.body
    assert "The setting is per browser." in card.body and "the input did not say" in card.body
    assert plain(card.body).endswith("Reply to this comment with **approve** or **reject**.")
    assert h.feed.pending(CARDS) == []
    assert h.store.mark(CARDS) == message.at.isoformat()


async def test_mission_plan_card_is_posted_on_every_member(h: Harness) -> None:
    cid, a, b = await sent_mission(h)
    h.attempts.outcomes[cid] = mission(cid, fr.PLAN_CARD_OPEN, mission_id="m-1")
    h.feed.push(CARDS, mission_plan_card(cid, "m-1"))
    await h.poll()
    for issue in (a, b):
        (card,) = h.card_comments(issue)
        assert "The mission's plan card is waiting for your answer." in card.body
        assert 'Mission "Sharing" — 2 features' in card.body
        assert plain(card.body).endswith("**approve** or **reject**.")


async def test_merge_card_shows_https_links_only(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.MERGE_CARD_OPEN, build_id="build-1")
    h.attempts.cards = [
        fr.OpenCard("merge", cid, "merge-build-1", "agents.approval.forge.merge-FEAT-1", "build-1")
    ]
    h.feed.push(
        CARDS,
        merge_card(
            cid,
            "build-1",
            app="https://preview.example/app?preview=t",
            report="http://plain.example/r",
        ),
    )
    await h.poll()
    (card,) = h.card_comments(issue)
    assert "Merge autobuild/FEAT-1 into main?" in card.body
    assert "[Try the preview](https://preview.example/app?preview=t)" in card.body
    assert "plain.example" not in card.body
    assert plain(card.body).endswith("Reply to this comment with **merge** or **decline**.")


async def test_mission_merge_card_says_which_keys_landed(h: Harness) -> None:
    cid, a, b = await sent_mission(h)
    h.attempts.outcomes[cid] = mission(
        cid,
        fr.MERGE_CARD_OPEN,
        mission_id="m-1",
        merge_build_id="build-m",
        landed_keys=("ENG1",),
        attempts=(key("ENG1", "LANDED"), key("ENG2", "FAILED", "tests failed")),
    )
    h.attempts.cards = [fr.OpenCard("merge", cid, "merge-build-m", "s", "build-m")]
    h.feed.push(CARDS, merge_card(cid, "build-m"))
    await h.poll()
    for issue in (a, b):
        (card,) = h.card_comments(issue)
        assert "Landed on the mission branch: ENG-1." in card.body
        assert "Did not land (merging leaves these out): ENG-2." in card.body


async def test_a_build_gate_card_is_posted_like_any_other(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.BUILDING, build_id="build-1")
    h.attempts.cards = [fr.OpenCard("build", cid, "build-1:autobuild:0", build_id="build-1")]
    h.feed.push(CARDS, gate_card(cid, "build-1"))
    await h.poll()
    (card,) = h.card_comments(issue)
    assert "A factory card is waiting for your answer (autobuild)." in card.body
    assert "Start the build?" in card.body
    assert plain(card.body).endswith("**approve** or **reject**.")
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    (subject, payload, _) = h.answers.published[0]
    assert (subject, payload.request_id) == (
        "agents.approval.forge.build-1.response",
        "build-1:autobuild:0",
    )


async def test_a_card_already_answered_is_not_posted(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    # The merge card was answered in Slack: the record shows no open card.
    h.attempts.outcomes[cid] = single(cid, fr.PUBLICATION_IN_FLIGHT, reason="approved")
    h.feed.push(CARDS, merge_card(cid, "build-1"))
    # And a plan card whose run has already moved on to building.
    h.feed.push(CARDS, plan_card(cid))
    await h.poll()
    assert h.card_comments(issue) == []
    assert h.feed.pending(CARDS) == []


async def test_cards_for_other_work_and_responses_are_ignored(h: Harness) -> None:
    await sent_single(h)
    h.feed.push(CARDS, plan_card("some-slack-request"))
    response = plan_card("lin-ENG-1-1")
    h.feed.push(CARDS, BusMessage(response.subject + ".response", response.data, response.at))
    await h.poll()
    assert all("waiting" not in c.body for c in h.linear.comments)
    assert h.feed.pending(CARDS) == []


async def test_cards_wait_while_the_record_cannot_be_read(h: Harness) -> None:
    issue = await sent_single(h)
    h.attempts.cards = [fr.OpenCard("plan", "lin-ENG-1-1", "req-plan-1")]
    h.attempts.unreadable = True
    h.feed.push(CARDS, plan_card("lin-ENG-1-1"))
    await h.poll()
    assert len(h.feed.pending(CARDS)) == 1
    h.attempts.unreadable = False
    await h.poll()
    assert len(h.card_comments(issue)) == 1


async def test_recovered_plan_card_says_answer_in_slack(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLAN_CARD_OPEN, request_id="req-old")
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-old")]
    await h.poll()
    assert h.card_comments(issue) == []  # the stream gets a moment to deliver it
    old = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    h.store.set_progress(cid, "", "card-seen:req-old", old)
    await h.poll(2)
    (card,) = h.card_comments(issue)
    assert "please answer it in Slack" in card.body
    assert "approve" not in card.body
    assert h.store.open_cards(answerable_only=True) == []


async def test_recovered_merge_card_can_be_answered(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.MERGE_CARD_OPEN, build_id="build-1")
    h.attempts.cards = [
        fr.OpenCard(
            "merge",
            cid,
            "merge-build-1",
            "agents.approval.forge.merge-FEAT-1",
            "build-1",
            app_url="https://preview.example/app",
            report_url="javascript:alert(1)",
        )
    ]
    await h.poll()
    h.store.set_progress(
        cid, "", "card-seen:merge-build-1", (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    )
    await h.poll()
    (card,) = h.card_comments(issue)
    assert "[Try the preview](https://preview.example/app)" in card.body
    assert "javascript" not in card.body
    assert plain(card.body).endswith("**merge** or **decline**.")
    h.linear.reply(card, "merge", user_id=OWNER_LINEAR)
    await h.poll()
    (subject, payload, correlation) = h.answers.published[0]
    assert subject == "agents.approval.forge.merge-FEAT-1.response"
    assert (payload.request_id, payload.decision, correlation) == ("merge-build-1", "approve", cid)


# ---------------------------------------------------------------------------
# Answers from Linear
# ---------------------------------------------------------------------------


async def _plan_card_posted(h: Harness) -> tuple[Any, Any]:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    h.feed.push(CARDS, plan_card(cid))
    await h.poll()
    (card,) = h.card_comments(issue)
    return issue, card


async def test_approve_on_a_plan_card_accepts_every_assumption(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "**Approve** looks right", user_id=OWNER_LINEAR)
    await h.poll()
    (subject, payload, correlation) = h.answers.published[0]
    assert subject == "agents.approval.forge.plan-lin-ENG-1-1.response"
    assert correlation == "lin-ENG-1-1"
    assert payload.request_id == "req-plan-1"
    assert payload.decision == "approve"
    assert payload.decided_by == OWNER_IDENTITY
    assert payload.notes == "looks right"
    assert [(d.assumption_id, d.disposition) for d in payload.dispositions] == [
        ("A1", "accepted"),
        ("A2", "accepted"),
    ]
    (ack,) = h.linear.replies_to(card.id)[1:]
    assert ack.body.startswith("Factory: Sent **approve** to the factory.")


async def test_reject_on_a_plan_card_stops_the_run(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "reject: wrong feature", user_id=OWNER_LINEAR)
    await h.poll()
    (_, payload, _) = h.answers.published[0]
    assert (payload.decision, payload.notes, payload.dispositions) == (
        "reject",
        "reject wrong feature",
        None,
    )


@pytest.mark.parametrize(("word", "decision"), [("merge", "approve"), ("Decline.", "reject")])
async def test_merge_and_decline_answer_a_merge_card(h: Harness, word: str, decision: str) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.MERGE_CARD_OPEN, build_id="build-1")
    h.attempts.cards = [fr.OpenCard("merge", cid, "merge-build-1", "s", "build-1")]
    h.feed.push(CARDS, merge_card(cid, "build-1"))
    await h.poll()
    (card,) = h.card_comments(issue)
    h.linear.reply(card, word, user_id=OWNER_LINEAR)
    await h.poll()
    (subject, payload, _) = h.answers.published[0]
    assert subject == "agents.approval.forge.merge-FEAT-1.response"
    assert (payload.request_id, payload.decision, payload.notes) == (
        "merge-build-1",
        decision,
        None,
    )
    ack = h.linear.replies_to(card.id)[-1].body
    assert ("**merge**" if decision == "approve" else "**decline**") in ack


async def test_a_reply_is_handled_once_across_polls_and_restarts(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    h.linear.reply(card, "approve again", user_id=OWNER_LINEAR)
    await h.poll(2)
    h.restart()
    await h.poll()
    assert len(h.answers.published) == 1


async def test_an_unlisted_author_is_told_once_and_nothing_is_published(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "approve", user_id=STRANGER)
    await h.poll()
    h.linear.reply(card, "approve please", user_id=STRANGER)
    await h.poll(2)
    assert h.answers.published == []
    refusals = [
        plain(c.body) for c in h.linear.replies_to(card.id) if c.body.startswith("Factory:")
    ]
    assert refusals == ["Factory: Only the people listed can answer this card."]
    # A listed person can still answer.
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert len(h.answers.published) == 1


async def test_discussion_in_the_thread_is_ignored(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "What does per browser mean?", user_id=OWNER_LINEAR)
    h.linear.reply(card, "approvement", user_id=OWNER_LINEAR)
    await h.poll(2)
    assert h.answers.published == []


def _unconfirmed_notices(h: Harness, card: Any) -> list[str]:
    return [plain(c.body) for c in h.linear.replies_to(card.id) if UNCONFIRMED_ANSWER in c.body]


async def test_a_failed_publish_is_not_repeated_and_a_new_reply_is_taken(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    h.answers.fail = True
    await h.poll()
    h.answers.fail = False
    await h.poll(2)
    assert h.answers.published == []
    assert _unconfirmed_notices(h, card) == [f"Factory: {UNCONFIRMED_ANSWER}"]
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)  # the person replies again
    await h.poll()
    assert len(h.answers.published) == 1


async def test_an_answer_whose_flush_timed_out_is_never_sent_again(h: Harness) -> None:
    # Codex review R2: the answer reached the bus, then the flush timed out.
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    h.answers.flush_times_out = True
    await h.poll()
    h.answers.flush_times_out = False
    await h.poll(2)
    h.restart()
    await h.poll()
    assert len(h.answers.published) == 1
    assert _unconfirmed_notices(h, card) == [f"Factory: {UNCONFIRMED_ANSWER}"]


async def test_a_newer_plan_card_closes_the_older_one(h: Harness) -> None:
    issue, first = await _plan_card_posted(h)
    h.attempts.cards = [fr.OpenCard("plan", "lin-ENG-1-1", "req-plan-2")]
    h.feed.push(CARDS, plan_card("lin-ENG-1-1", request_id="req-plan-2"))
    await h.poll()
    h.linear.reply(first, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert h.answers.published == []
    second = h.card_comments(issue)[-1]
    h.linear.reply(second, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert [p.request_id for _, p, _ in h.answers.published] == ["req-plan-2"]


async def test_cards_of_an_ended_attempt_take_no_answers(h: Harness) -> None:
    _, card = await _plan_card_posted(h)
    h.attempts.outcomes["lin-ENG-1-1"] = single("lin-ENG-1-1", fr.WITHDRAWN, True, "withdrawn")
    await h.poll()
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert h.answers.published == []


# ---------------------------------------------------------------------------
# Slack notifications
# ---------------------------------------------------------------------------


def notification(cid: str, text: str) -> BusMessage:
    from nats_core import EventType, MessageEnvelope
    from nats_core.events import NotificationPayload

    envelope = MessageEnvelope(
        source_id="forge",
        event_type=EventType.NOTIFICATION,
        correlation_id=cid,
        payload=NotificationPayload(message=text, adapter="slack", correlation_id=cid).model_dump(
            mode="json"
        ),
    )
    return BusMessage("jarvis.notification.slack", envelope.model_dump_json().encode(), None)


async def test_notification_is_copied_only_for_an_unfiled_attempt(h: Harness) -> None:
    first = await sent_single(h, "First")
    second = await sent_single(h, "Second")
    h.attempts.outcomes["lin-ENG-1-1"] = single("lin-ENG-1-1", fr.UNFILED)
    h.attempts.outcomes["lin-ENG-2-1"] = single("lin-ENG-2-1", fr.PLANNING)
    message = notification("lin-ENG-1-1", "Missions are switched off.\nAsk the operator.")
    h.feed.push(NOTIFICATIONS, message)
    h.feed.push(NOTIFICATIONS, notification("lin-ENG-2-1", "Planning run started."))
    await h.poll()
    h.feed.push(NOTIFICATIONS, message)  # delivered again
    await h.poll()
    assert h.factory(h.linear.comments_on(first)) == [
        "Factory: The factory said, in Slack:\n\n> Missions are switched off.\n> Ask the operator."
    ]
    assert h.factory(h.linear.comments_on(second)) == []
    assert h.store.reservations()  # visibility only: nothing ended


# ---------------------------------------------------------------------------
# A rebuilt record brings ended attempts to their final state once
# ---------------------------------------------------------------------------


async def test_rebuild_brings_ended_attempts_to_their_final_state_once(h: Harness) -> None:
    linear = h.linear
    landed = linear.issue("Landed long ago", state="In Progress")
    failed = linear.issue("Failed while the door was away", state="In Progress")
    retried = linear.issue("Already moved back to Todo", state="Todo")
    h.attempts.recorded = [
        RecordedAttempt("lin-ENG-1-1", open=False),
        RecordedAttempt("lin-ENG-1-2", open=False),
        RecordedAttempt("lin-ENG-2-1", open=False),
        RecordedAttempt("lin-ENG-3-1", open=False),
    ]
    h.attempts.outcomes["lin-ENG-1-2"] = single(
        "lin-ENG-1-2", fr.ON_MAIN, True, "merged", j_commit="abc1234"
    )
    h.attempts.outcomes["lin-ENG-2-1"] = single("lin-ENG-2-1", fr.BUILD_FAILED, True, "tests")
    await h.poll(2)
    assert [plain(c) for c in linear.comments_on(landed)] == [
        "Factory: Recovered after a restart: Merged into the main branch as `abc1234`."
    ]
    assert linear.state_name(landed) == "Done"
    assert linear.state_name(failed) == "Backlog"
    assert "Recovered after a restart: Ended without a merge" in linear.comments_on(failed)[0]
    # Already in Todo (a person's retry): left there and sent as attempt 2.
    assert [p["correlation_id"] for p in h.bus.payloads()] == ["lin-ENG-3-2"]
    assert all("Recovered" not in c for c in linear.comments_on(retried))
    # Only the latest attempt of each issue was read.
    assert "lin-ENG-1-1" not in h.attempts.asked


# ---------------------------------------------------------------------------
# Through the real reader, on a Forge record built from Forge's schema
# ---------------------------------------------------------------------------


async def test_through_the_real_forge_record(tmp_path: Path) -> None:
    db = tmp_path / "forge.db"
    cx = sqlite3.connect(db)
    cx.executescript(SCHEMA.read_text())
    h = Harness(tmp_path)
    h.attempts = ForgeAttempts(fr.ForgeRecord(db, timeout=0.2))  # type: ignore[assignment]
    h.door = h._door()
    issue = h.linear.issue("Add a dark mode")
    await h.poll()  # a new door record is rebuilt from the (empty) record first
    cid = "lin-ENG-1-1"
    assert h.bus.payloads()[0]["correlation_id"] == cid
    now = "2026-10-18T10:00:00+00:00"
    cx.execute(
        "INSERT INTO builds (build_id, feature_id, repo, branch, feature_yaml_path, status, "
        "triggered_by, correlation_id, queued_at, target_branch) "
        "VALUES ('build-1', 'FEAT-1', 'repo', 'b', 'f.yaml', 'RUNNING', 'jarvis', ?, ?, 'main')",
        (cid, now),
    )
    cx.commit()
    await h.poll()
    assert h.factory(h.linear.comments_on(issue)) == ["Factory: Building."]
    cx.execute(
        "INSERT INTO publication_records (build_id, target_branch, j_commit, result) "
        "VALUES ('build-1', 'main', 'abc1234', 'merged into the remote and running')"
    )
    cx.commit()
    await h.poll()
    assert h.factory(h.linear.comments_on(issue))[-1] == (
        "Factory: Merged into the main branch as `abc1234`."
    )
    assert h.linear.state_name(issue) == "Done"
    # Watched until Forge's merge report says whether the deploy worked (R11).
    assert h.store.reservations() == {issue.id: cid}
    cx.execute(
        "INSERT INTO stage_log (build_id, stage_label, target_kind, target_identifier, "
        "status, started_at, completed_at, duration_secs, details_json) VALUES ('build-1', "
        "'merge-deploy', 'local_tool', 'merge_deploy_executor', 'PASSED', ?, ?, 0.0, ?)",
        (now, now, json.dumps({"result": "merged-into-the-remote-and-running"})),
    )
    cx.commit()
    await h.poll()
    assert len(h.factory(h.linear.comments_on(issue))) == 2
    assert h.store.reservations() == {}


# ---------------------------------------------------------------------------
# The bus feed and the small pure parts
# ---------------------------------------------------------------------------


async def test_bus_feed_subscribes_without_taking_anything(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    class FakeJetStream:
        async def subscribe(self, subject: str, **kwargs: Any) -> Any:
            calls.append({"subject": subject, **kwargs})
            return SimpleNamespace(unsubscribe=lambda: None)

        def __getattr__(self, name: str) -> Any:  # pull_subscribe, consumer creation, ...
            raise AssertionError(f"the bus feed must not call {name}")

    feed = NatsBusFeed(SimpleNamespace(js=FakeJetStream()))
    mark = "2026-10-18T10:00:00+00:00"
    await feed.start({CARDS: mark, NOTIFICATIONS: None})
    from nats.js.api import DeliverPolicy

    cards, notes = calls
    assert (cards["subject"], cards["stream"]) == ("agents.approval.forge.*", "AGENTS")
    assert cards["ordered_consumer"] is True
    assert cards["config"].deliver_policy == DeliverPolicy.BY_START_TIME
    assert cards["config"].opt_start_time == datetime.fromisoformat(mark)
    assert (notes["subject"], notes["stream"]) == ("jarvis.notification.slack", "JARVIS")
    assert notes["config"].deliver_policy == DeliverPolicy.ALL
    assert all("durable" not in c and "queue" not in c for c in calls)

    message = SimpleNamespace(
        subject="agents.approval.forge.x",
        data=b"{}",
        metadata=SimpleNamespace(timestamp=datetime(2026, 10, 18, tzinfo=UTC)),
    )
    await cards["cb"](message)
    (pending,) = feed.pending(CARDS)
    assert pending.at == datetime(2026, 10, 18, tzinfo=UTC)
    feed.done(CARDS, pending)
    assert feed.pending(CARDS) == []


def test_parse_reply() -> None:
    assert parse_reply("approve") == ("approve", None)
    assert parse_reply("  **Merge** now please") == ("approve", "now please")
    assert parse_reply("reject: too vague") == ("reject", "too vague")
    assert parse_reply("Decline") == ("reject", None)
    assert parse_reply("approvement") == (None, None)
    assert parse_reply("I approve") == (None, None)
    assert parse_reply("") == (None, None)


def test_https_link() -> None:
    assert (
        https_link("https://preview.example/a?preview=t") == "https://preview.example/a?preview=t"
    )
    for bad in (
        "http://preview.example/a",
        "javascript:alert(1)",
        "https://user@preview.example/",
        "https://preview.example/a)(b",
        "https://preview.example/a b",
        None,
    ):
        assert https_link(bad) is None


def test_parse_approvers() -> None:
    assert parse_approvers(None) == {}
    assert parse_approvers(" user-a = U0A , user-b=linear:user-b,") == {
        "user-a": "U0A",
        "user-b": "linear:user-b",
    }
    with pytest.raises(ValueError):
        parse_approvers("user-a")


def test_four_token_subjects_only() -> None:
    message = plan_card("lin-ENG-1-1")
    assert parse_card(message.subject, message.data) is not None
    assert parse_card(message.subject + ".response", message.data) is None
    assert parse_card("agents.approval.other.x", message.data) is None
    payload = json.loads(message.data)
    payload["event_type"] = "approval_response"
    assert parse_card(message.subject, json.dumps(payload).encode()) is None


def test_door_config_reads_approvers_and_the_forge_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis.config.settings import JarvisConfig
    from jarvis.infrastructure.linear.door import door_config

    monkeypatch.setenv("JARVIS_LINEAR_API_KEY", "fake-linear-key-for-tests-only-7f3a")
    monkeypatch.setenv("JARVIS_LINEAR_TEAM", "ENG")
    monkeypatch.setenv("JARVIS_LINEAR_OWNER_IDENTITY", OWNER)
    monkeypatch.setenv("JARVIS_LINEAR_APPROVERS", f"{OWNER_LINEAR}={OWNER_IDENTITY}")
    monkeypatch.setenv("JARVIS_LINEAR_FORGE_DB", str(tmp_path / "forge.db"))
    resolved = door_config(JarvisConfig())
    assert not isinstance(resolved, str)
    assert resolved.settings.approvers == {OWNER_LINEAR: OWNER_IDENTITY}
    assert resolved.forge_db == tmp_path / "forge.db"

    monkeypatch.setenv("JARVIS_LINEAR_APPROVERS", "not-a-pair")
    reason = door_config(JarvisConfig())
    assert isinstance(reason, str) and "JARVIS_LINEAR_APPROVERS" in reason


# ---------------------------------------------------------------------------
# Codex review of 5c34f70: the repairs (R1-R6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mission_first", [True, False])
async def test_rebuild_moves_each_issue_by_its_own_latest_attempt(
    h: Harness, mission_first: bool
) -> None:
    # R1: a failed mission containing ENG-1, then a successful single retry
    # (and the other way round). Only the later attempt decides.
    label = h.linear.label("mission: Sharing")
    issue = h.linear.issue("Share a note", state="In Progress", labels=[label])
    mcid = f"{mission_prefix(label)}1"
    early, late = "2026-10-18T09:00:00+00:00", "2026-10-18T10:00:00+00:00"
    h.attempts.recorded = [
        RecordedAttempt(
            mcid, open=False, mission_keys=("ENG1",), filed_at=early if mission_first else late
        ),
        RecordedAttempt("lin-ENG-1-1", open=False, filed_at=late if mission_first else early),
    ]
    h.attempts.outcomes[mcid] = mission(mcid, fr.NOT_STARTED, True, reason="no seed")
    h.attempts.outcomes["lin-ENG-1-1"] = single(
        "lin-ENG-1-1", fr.ON_MAIN, True, "merged", j_commit="abc1234"
    )
    await h.poll(2)
    comments = [plain(c) for c in h.linear.comments_on(issue)]
    if mission_first:
        assert h.linear.state_name(issue) == "Done"
        assert comments == [
            "Factory: Recovered after a restart: Merged into the main branch as `abc1234`."
        ]
        assert mcid not in h.attempts.asked
    else:
        assert h.linear.state_name(issue) == "Backlog"
        (only,) = comments
        assert only.startswith("Factory: Recovered after a restart: Ended without a merge")
        assert "lin-ENG-1-1" not in h.attempts.asked


async def test_a_card_and_a_refusal_wait_for_their_send_to_finish(h: Harness) -> None:
    # R4: the "sent" comment fails for a while; the plan card and a refusal
    # arrive meanwhile, and the stream will not deliver them again.
    issue = h.linear.issue("Add a dark mode")
    cid = "lin-ENG-1-1"
    h.linear.fail_next["DoorCommentCreate"] = [server_error(), server_error()]
    with pytest.raises(LinearError):
        await h.poll()  # published; its "sent" comment failed
    assert h.bus.payloads()[0]["correlation_id"] == cid
    h.feed.push(CARDS, plan_card(cid))
    h.feed.push(NOTIFICATIONS, notification(cid, "Missions are switched off."))
    await h.poll()  # the "sent" comment fails again: both are held
    assert h.card_comments(issue) == []
    assert h.feed.pending(CARDS) == [] and h.feed.pending(NOTIFICATIONS) == []
    assert len(h.store.held_messages(CARDS)) == len(h.store.held_messages(NOTIFICATIONS)) == 1
    h.restart()
    h.attempts.outcomes[cid] = single(cid, fr.UNFILED)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    await h.poll()
    assert h.linear.state_name(issue) == "In Progress"
    assert len(h.card_comments(issue)) == 1
    assert any("Missions are switched off." in c for c in h.linear.comments_on(issue))
    assert h.store.held_messages(CARDS) == h.store.held_messages(NOTIFICATIONS) == []


async def test_comments_whose_answer_was_lost_are_not_written_twice(h: Harness) -> None:
    # R3: Linear writes the comment, the door does not hear back, then restarts.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.BUILDING)
    h.linear.lose_response["DoorCommentCreate"] = 1
    await h.poll()
    h.restart()
    await h.poll(2)
    assert h.factory(h.linear.comments_on(issue)) == ["Factory: Building."]

    h.attempts.outcomes[cid] = single(cid, fr.BUILD_FAILED, True, "tests failed")
    h.linear.lose_response["DoorCommentCreate"] = 1
    await h.poll()
    h.restart()
    await h.poll(2)
    comments = h.factory(h.linear.comments_on(issue))
    assert len(comments) == 2 and comments[1].startswith("Factory: Ended without a merge")
    assert h.linear.state_name(issue) == "Backlog"
    assert all(
        re.fullmatch(r"_factory note [0-9a-f]{12}_", c.splitlines()[-1])
        for c in h.linear.comments_on(issue)[1:]
    )


async def test_a_card_whose_answer_was_lost_is_posted_once_and_answered(h: Harness) -> None:
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    h.feed.push(CARDS, plan_card(cid))
    h.linear.lose_response["DoorCommentCreate"] = 1
    with pytest.raises(LinearError):  # an outage stops the poll (coach C3)
        await h.poll()  # the card is on the issue; the door did not hear back
    assert len(h.store.held_messages(CARDS)) == 1
    h.restart()
    await h.poll()
    (card,) = h.card_comments(issue)
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)  # under the card found again
    await h.poll()
    assert [p.request_id for _, p, _ in h.answers.published] == ["req-plan-1"]


async def test_a_build_gate_answered_in_slack_is_not_posted_or_answered(h: Harness) -> None:
    # R6: posted while open; answered in Slack; then a replay of the card.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.BUILDING, build_id="build-1")
    h.attempts.cards = [fr.OpenCard("build", cid, "build-1:autobuild:0", build_id="build-1")]
    h.feed.push(CARDS, gate_card(cid, "build-1"))
    await h.poll()
    (card,) = h.card_comments(issue)
    h.attempts.cards = []  # answered in Slack: the build is no longer paused
    await h.poll()
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert h.answers.published == []

    second = await sent_single(h, "Second")
    cid2 = "lin-ENG-2-1"
    h.attempts.outcomes[cid2] = single(cid2, fr.BUILDING, build_id="build-2")
    h.feed.push(CARDS, gate_card(cid2, "build-2"))  # a replay after the Slack answer
    await h.poll()
    assert h.card_comments(second) == []


async def test_a_card_the_record_cannot_check_is_answered_in_slack_only(h: Harness) -> None:
    # R6: a card for a build the record does not link to this attempt.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.BUILDING)
    h.feed.push(CARDS, gate_card(cid, "build-9"))
    await h.poll()
    (card,) = h.card_comments(issue)
    assert plain(card.body).endswith(SLACK_ONLY_ENDING)
    assert h.store.open_cards(answerable_only=True) == []
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert h.answers.published == []


async def test_an_expired_spec_digest_card_is_recovered_from_the_real_record(
    tmp_path: Path,
) -> None:
    # R5: Forge's spec digest card waits inline (no PAUSED state); its opening
    # is in planning_run_events. Through the real reader.
    db = tmp_path / "forge.db"
    cx = sqlite3.connect(db)
    cx.executescript(SCHEMA.read_text())
    h = Harness(tmp_path)
    h.attempts = ForgeAttempts(fr.ForgeRecord(db, timeout=0.2))  # type: ignore[assignment]
    h.door = h._door()
    issue = h.linear.issue("Add a dark mode")
    await h.poll()
    cid = "lin-ENG-1-1"
    request = f"plan-{cid}:feature-spec-digest-review:0"
    now = "2026-10-18T10:00:00+00:00"
    cx.execute(
        "INSERT INTO planning_runs (correlation_id, state, originating_user, expected_approver, "
        "request_text, triggered_by, queued_at) VALUES (?, 'FEATURE_SPEC', 'u', 'a', 'r', "
        "'jarvis', ?)",
        (cid, now),
    )
    cx.execute(
        "INSERT INTO planning_run_events (correlation_id, stage_label, status, actor_identity, "
        "details_json, recorded_at) VALUES (?, 'feature-spec-digest-review', 'GATED', "
        "'planning-driver', ?, ?)",
        (
            cid,
            json.dumps(
                {
                    "digest_review": {
                        "outcome": "opened",
                        "request_id": request,
                        "attempt_count": 0,
                        "expected_approver": "a",
                        "card": {"title": "The spec is ready"},
                        "wait_seconds": 900,
                    }
                }
            ),
            now,
        ),
    )
    cx.commit()
    await h.poll()  # seen; the stream gets a moment to deliver the full card
    assert h.card_comments(issue) == []
    old = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    h.store.set_progress(cid, "", f"card-seen:{request}", old)
    await h.poll()
    (card,) = h.card_comments(issue)
    assert "please answer it in Slack" in card.body and request in card.body
    assert h.store.open_cards(answerable_only=True) == []
    cx.close()


# ---------------------------------------------------------------------------
# Codex review round 2 on 3dde0e4 (R4, R7, R8)
# ---------------------------------------------------------------------------


async def test_a_mission_features_card_waits_for_the_missions_send_to_finish(
    h: Harness,
) -> None:
    # R4: a feature's build gate carries <mission cid>-<KEY>-a<n>; it arrives
    # while the mission's "sent" comment is failing.
    label = h.linear.label("mission: Sharing")
    a = h.linear.issue("Share a note", labels=[label])
    b = h.linear.issue("Revoke a share", labels=[label], blocked_by=[a.id])
    cid = f"{mission_prefix(label)}1"
    child = f"{cid}-ENG1-a1"
    h.linear.fail_next["DoorCommentCreate"] = [server_error(), server_error()]
    with pytest.raises(LinearError):
        await h.poll()
    assert h.bus.payloads()[0]["correlation_id"] == cid
    h.feed.push(CARDS, gate_card(child, "build-4"))
    await h.poll()  # the "sent" comment fails again: the card is held
    assert h.feed.pending(CARDS) == []
    assert len(h.store.held_messages(CARDS)) == 1
    h.restart()
    h.attempts.outcomes[cid] = mission(
        cid,
        fr.MISSION_RUNNING,
        mission_id="m-1",
        attempts=(fr.KeyAttempt("ENG1", 1, "ADMITTED", None, child),),
    )
    h.attempts.cards = [fr.OpenCard("build", child, "build-4:autobuild:0", build_id="build-4")]
    await h.poll()
    assert h.linear.state_name(a) == h.linear.state_name(b) == "In Progress"
    (card,) = h.card_comments(a)
    assert h.card_comments(b) == []
    assert plain(card.body).endswith("**approve** or **reject**.")
    assert h.store.held_messages(CARDS) == []


def auth_confirmation_card(cid: str, request_id: str) -> BusMessage:
    """Forge's sign-in confirmation card (driver.py 9965-10010, checkpoint.py 324-420)."""
    return card_message(
        f"agents.approval.forge.plan-{cid}",
        request_id,
        cid=cid,
        details={
            "build_id": f"plan-{cid}",
            "correlation_id": cid,
            "checkpoint_type": AUTH_CONFIRMATION,
            "summary": {
                "checkpoint": AUTH_CONFIRMATION,
                "title": "Does this feature sit behind a sign-in?",
                "what_happened": "The spec checker flagged this feature as behind a sign-in.",
                "flagged_lines": ["Only signed-in users can see their notes."],
                "confirm_means": "Confirm — there is no sign-in here.",
                "reject_means": "Reject — this really is behind a sign-in.",
                "later_means": "Setting this aside for later stops the run too.",
                "no_answer_means": "No answer within 15 minutes: the run stops.",
            },
        },
        action="The owner confirms whether the sign-in is real.",
    )


async def test_the_sign_in_confirmation_card_is_answered_in_slack_only(h: Harness) -> None:
    # R7
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    request = f"plan-{cid}:qa-pass-bars-auth-confirm:0"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, request)]
    h.feed.push(CARDS, auth_confirmation_card(cid, request))
    await h.poll()
    (card,) = h.card_comments(issue)
    assert plain(card.body) == (
        "Factory: **A factory card is waiting: Does this feature sit behind a sign-in?**"
        f"\n\n{SLACK_ONLY_ENDING}"
    )
    assert h.store.open_cards(answerable_only=True) == []
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert h.answers.published == []


async def test_an_answer_interrupted_after_its_claim_is_not_lost(h: Harness) -> None:
    # R8: the door stops straight after claiming the answer.
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    h.answers.interrupted = True
    with pytest.raises(asyncio.CancelledError):
        await h.poll()
    h.answers.interrupted = False
    h.restart()
    await h.poll(2)
    assert h.answers.published == []  # the original is never published
    assert _unconfirmed_notices(h, card) == [f"Factory: {UNCONFIRMED_ANSWER}"]
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)  # a new reply is taken
    await h.poll()
    assert len(h.answers.published) == 1


async def test_an_unpublished_claim_for_a_settled_card_says_nothing(h: Harness) -> None:
    # R8: answered in Slack meanwhile; nothing to tell, nothing to reopen.
    _, card = await _plan_card_posted(h)
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    h.answers.interrupted = True
    with pytest.raises(asyncio.CancelledError):
        await h.poll()
    h.answers.interrupted = False
    h.restart()
    h.attempts.cards = []
    await h.poll(2)
    assert _unconfirmed_notices(h, card) == []
    assert h.store.unpublished_claims() == []


# ---------------------------------------------------------------------------
# Coach review of 3dde0e4 (C1-C6) and Codex round 3 on 16c3c63 (R9)
# ---------------------------------------------------------------------------


async def test_a_digest_sign_in_question_says_what_approving_means(h: Harness) -> None:
    # C1: Forge counts an approval that leaves the item unanswered as "no
    # sign-in" (planning/driver.py 5940-5948).
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    message = plan_card(cid)
    data = json.loads(message.data)
    data["payload"]["details"]["summary"]["sign_in_check"] = {
        "title": "One thing to confirm",
        "statement": "Only signed-in users can see their notes.",
        "no_answer_means": "the run stops",
    }
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    h.feed.push(CARDS, BusMessage(message.subject, json.dumps(data).encode(), message.at))
    await h.poll()
    (card,) = h.card_comments(issue)
    assert (
        "> Only signed-in users can see their notes.\n\n"
        "Approving here counts as agreeing that nothing here involves signing in. "
        "To disagree, answer the card in Slack."
    ) in card.body
    assert "the run stops" not in card.body and "unanswered" not in card.body


async def test_a_deleted_mission_member_does_not_keep_the_mission_open(h: Harness) -> None:
    # C2: Linear refuses the first member's final comment (it was deleted);
    # the other member still ends and every reservation is released.
    cid, a, b = await sent_mission(h)
    h.linear.gone.add(a.id)
    h.attempts.outcomes[cid] = mission(cid, fr.NOT_STARTED, True, reason="no seed")
    await h.poll()
    assert h.factory(h.linear.comments_on(b))[-1].startswith("Factory: Ended without a merge")
    assert h.linear.state_name(b) == "Backlog"
    assert h.store.reservations() == {}


async def test_a_long_outage_never_downgrades_a_card(h: Harness) -> None:
    # C3, R9 (a): Linear is down for longer than five polls while a plan card
    # waits; then it comes back after a restart. The full card is posted once,
    # answerable, and no "answer in Slack" fallback is written.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    h.store.set_progress(
        cid, "", "card-seen:req-plan-1", (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    )
    h.feed.push(CARDS, plan_card(cid))
    h.linear.fail_next["DoorCommentCreate"] = [server_error() for _ in range(7)]
    for _ in range(7):
        with pytest.raises(LinearError):
            await h.poll()
    assert h.feed.pending(CARDS) == [] and len(h.store.held_messages(CARDS)) == 1
    h.restart()
    await h.poll(2)
    (card,) = h.card_comments(issue)
    assert card.body.startswith("Factory: **The plan card is waiting for your answer.**")
    assert all("answer it in Slack" not in c for c in h.linear.comments_on(issue))
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert [p.request_id for _, p, _ in h.answers.published] == ["req-plan-1"]


async def test_no_slack_fallback_while_the_full_card_waits(h: Harness) -> None:
    # R9 (b): Linear refuses the full card twice; the record's fallback is
    # not written meanwhile, and the full card is posted when Linear takes it.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    h.store.set_progress(
        cid, "", "card-seen:req-plan-1", (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    )
    h.feed.push(CARDS, plan_card(cid))
    h.linear.fail_next["DoorCommentCreate"] = [refused(), refused()]
    await h.poll(2)
    assert h.card_comments(issue) == []
    await h.poll()
    (card,) = h.card_comments(issue)
    assert plain(card.body).endswith("**approve** or **reject**.")
    assert h.store.open_cards(answerable_only=True)


async def test_only_the_doors_own_cards_wake_it(h: Harness) -> None:
    # C6
    from jarvis.infrastructure.linear.report import wakes_for

    await sent_single(h)
    cid = "lin-ENG-1-1"
    wake = asyncio.Event()
    feed = NatsBusFeed(SimpleNamespace(js=None), wake=wake, wake_if=wakes_for(h.store))

    def arrive(message: BusMessage) -> bool:
        wake.clear()
        feed._receive(CARDS, SimpleNamespace(subject=message.subject, data=message.data))
        return wake.is_set()

    assert arrive(plan_card(cid))
    assert arrive(gate_card(f"{cid}-x-a1", "build-1"))
    assert not arrive(plan_card("slack-abc"))
    assert not arrive(plan_card("lin-ENG-1-10"))
    assert not arrive(notification("slack-abc", "Not ours."))
    assert arrive(notification(cid, "Ours."))
    assert len(feed.pending(CARDS)) == 6  # every message is still kept


# ---------------------------------------------------------------------------
# Codex round 4 on 1da0e82 (R9, R10, R11)
# ---------------------------------------------------------------------------


async def test_internal_errors_in_a_200_never_downgrade_a_card(h: Harness) -> None:
    # R9: Linear answers HTTP 200 with an internal error, more than five times.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.PLANNING)
    h.attempts.cards = [fr.OpenCard("plan", cid, "req-plan-1")]
    h.store.set_progress(
        cid, "", "card-seen:req-plan-1", (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    )
    h.feed.push(CARDS, plan_card(cid))
    h.linear.fail_next["DoorCommentCreate"] = [internal_error() for _ in range(7)]
    for _ in range(7):
        with pytest.raises(LinearError):
            await h.poll()
    h.restart()
    await h.poll(2)
    (card,) = h.card_comments(issue)
    assert card.body.startswith("Factory: **The plan card is waiting for your answer.**")
    assert all("answer it in Slack" not in c for c in h.linear.comments_on(issue))
    h.linear.reply(card, "approve", user_id=OWNER_LINEAR)
    await h.poll()
    assert [p.request_id for _, p, _ in h.answers.published] == ["req-plan-1"]


async def test_a_transient_error_while_ending_does_not_abandon_the_issue(h: Harness) -> None:
    # R9: an internal error on the final comment is tried again, not given up.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(cid, fr.BUILD_FAILED, True, "tests failed")
    h.linear.fail_next["DoorCommentCreate"] = [internal_error()]
    await h.poll()
    assert h.store.reservations() == {issue.id: cid}
    assert h.store.progress(cid, issue.id, "final") is None
    await h.poll()
    (only,) = h.factory(h.linear.comments_on(issue))
    assert only.startswith("Factory: Ended without a merge")
    assert h.linear.state_name(issue) == "Backlog"
    assert h.store.reservations() == {}


async def test_a_deleted_member_with_unreported_steps_does_not_hold_the_mission(
    h: Harness,
) -> None:
    # R10: the deleted member's FAILED step and the survivor's LANDED step were
    # never written; the mission merged.
    cid, a, b = await sent_mission(h)
    h.linear.gone.add(a.id)
    h.attempts.outcomes[cid] = mission(
        cid,
        fr.ON_MAIN,
        True,
        mission_id="m-1",
        status="MERGED",
        attempts=(key("ENG1", "FAILED", "tests failed"), key("ENG2", "LANDED")),
        landed_keys=("ENG2",),
        j_commit="def5678",
    )
    await h.poll()
    h.restart()
    await h.poll()
    assert h.factory(h.linear.comments_on(b)) == [
        "Factory: Merged with the mission into the main branch as `def5678`."
    ]
    assert h.linear.state_name(b) == "Done"
    assert h.store.reservations() == {}


async def test_a_deploy_failure_reported_after_the_merge_is_still_said(h: Harness) -> None:
    # R11: on main by its publication record first; Forge's merge report, saying
    # the deploy failed, arrives on a later poll, after a restart.
    issue = await sent_single(h)
    cid = "lin-ENG-1-1"
    h.attempts.outcomes[cid] = single(
        cid, fr.ON_MAIN_REPORT_PENDING, False, "merged into main", j_commit="abc1234"
    )
    await h.poll(2)
    assert h.factory(h.linear.comments_on(issue)) == [
        "Factory: Merged into the main branch as `abc1234`."
    ]
    assert h.linear.state_name(issue) == "Done"
    assert h.store.reservations() == {issue.id: cid}
    h.restart()
    h.attempts.outcomes[cid] = single(
        cid,
        fr.ON_MAIN_DEPLOY_FAILED,
        True,
        "merged into main, but its deploy failed: the health check timed out",
        j_commit="abc1234",
    )
    await h.poll(2)
    assert h.factory(h.linear.comments_on(issue)) == [
        "Factory: Merged into the main branch as `abc1234`.",
        "Factory: The deploy failed: the health check timed out.",
    ]
    assert h.linear.state_name(issue) == "Done"
    assert h.store.reservations() == {}
