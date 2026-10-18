"""The Linear door against a fake Linear and a captured bus (design stage 3)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from structlog.testing import capture_logs

from jarvis.infrastructure.linear.client import LinearAuthError, LinearError, LinearRateLimited
from jarvis.infrastructure.linear.door import (
    BAD_KEY_RETRY_SECONDS,
    MAX_BACKOFF_SECONDS,
    AssumeAttemptsOpen,
    BusUnavailable,
    DoorSettings,
    LinearDoor,
    NatsIntakeQueue,
    RebuildUnavailable,
    RecordedAttempt,
    WaitingRequest,
)
from jarvis.infrastructure.linear.mapping import mission_prefix
from jarvis.infrastructure.linear.store import DoorStore

from .fake_linear import (
    FAKE_KEY,
    CapturedBus,
    FakeAttempts,
    FakeIntake,
    FakeLinear,
    bad_key,
    rate_limited,
    server_error,
)

OWNER = "U0OWNER0001"


class Harness:
    def __init__(
        self,
        tmp_path: Any,
        *,
        default_repo: str | None = "example-repo",
        linear: FakeLinear | None = None,
        attempts: FakeAttempts | None = None,
        store_name: str = "door.sqlite3",
    ) -> None:
        self.linear = linear or FakeLinear()
        self.bus = CapturedBus()
        self.attempts = attempts or FakeAttempts()
        self.intake = FakeIntake()
        self.store = DoorStore(tmp_path / store_name)
        self.client = self.linear.client()
        self.door = LinearDoor(
            client=self.client,
            publisher=self.bus,
            store=self.store,
            settings=DoorSettings(team="ENG", owner_identity=OWNER, default_repo=default_repo),
            attempts=self.attempts,
            intake=self.intake,
        )

    async def poll(self) -> None:
        await self.door.poll_once()

    def sent_comments(self, issue: Any) -> list[str]:
        return [c for c in self.linear.comments_on(issue) if "Sent to the factory as" in c]


@pytest.fixture
def harness(tmp_path: Any) -> Harness:
    return Harness(tmp_path)


# ---------------------------------------------------------------------------
# A single issue
# ---------------------------------------------------------------------------


async def test_single_issue_is_sent_once_across_two_polls(harness: Harness) -> None:
    issue = harness.linear.issue("Add a dark mode", "Users asked for it.")
    await harness.poll()
    await harness.poll()

    assert len(harness.bus.published) == 1
    subject, data = harness.bus.published[0]
    envelope = json.loads(data)
    payload = envelope["payload"]
    assert subject == "pipeline.planning-queued.lin-ENG-1-1"
    assert envelope["source_id"] == "jarvis"
    assert payload["correlation_id"] == "lin-ENG-1-1"
    assert payload["request_text"] == "Add a dark mode\n\nUsers asked for it."
    assert payload["originating_adapter"] == "linear"
    assert payload["triggered_by"] == "jarvis"
    assert payload["originating_user"] == OWNER
    assert payload["parent_request_id"] is None
    assert payload["target_repo"] == "example-repo"
    assert "queue_command" not in payload
    assert harness.linear.comments_on(issue) == ["Factory: Sent to the factory as `lin-ENG-1-1`"]
    assert harness.linear.state_name(issue) == "In Progress"
    assert harness.store.get_send("lin-ENG-1-1").status == "moved"


async def test_empty_description_sends_the_title_alone(harness: Harness) -> None:
    harness.linear.issue("Just a title")
    await harness.poll()
    assert harness.bus.payloads()[0]["request_text"] == "Just a title"


async def test_crash_between_publish_and_comment_does_not_republish(harness: Harness) -> None:
    issue = harness.linear.issue("Export to CSV")
    harness.linear.fail_next["DoorCommentCreate"] = [server_error()]
    with pytest.raises(LinearError):
        await harness.poll()
    assert len(harness.bus.published) == 1
    assert harness.store.get_send("lin-ENG-1-1").status == "published"
    assert harness.linear.state_name(issue) == "Todo"

    await harness.poll()
    assert len(harness.bus.published) == 1  # never published again
    assert harness.sent_comments(issue) == ["Factory: Sent to the factory as `lin-ENG-1-1`"]
    assert harness.linear.state_name(issue) == "In Progress"


async def test_resumed_send_does_not_repeat_a_comment_already_written(
    harness: Harness, tmp_path: Any
) -> None:
    issue = harness.linear.issue("Export to CSV")
    harness.linear.fail_next["DoorIssueMove"] = [server_error()]
    with pytest.raises(LinearError):
        await harness.poll()
    # The comment was written but (as after a crash) the record did not say so.
    harness.store._db.execute("UPDATE send_issues SET commented = 0")
    harness.store.set_status("lin-ENG-1-1", "published")
    harness.store._db.commit()
    await harness.poll()
    assert len(harness.sent_comments(issue)) == 1
    assert harness.linear.state_name(issue) == "In Progress"
    assert len(harness.bus.published) == 1


async def test_bus_failure_leaves_a_pending_send_and_nothing_in_linear(harness: Harness) -> None:
    issue = harness.linear.issue("Rename the app")
    harness.bus.fail = True
    with pytest.raises(BusUnavailable):
        await harness.poll()
    send = harness.store.get_send("lin-ENG-1-1")
    assert send.status == "pending"
    assert harness.linear.comments_on(issue) == []
    assert harness.linear.state_name(issue) == "Todo"

    # The issue is edited meanwhile: the frozen bytes are what is published.
    issue.title = "Something else entirely"
    harness.bus.fail = False
    await harness.poll()
    assert [data for _, data in harness.bus.published] == [send.payload]
    assert harness.bus.payloads()[0]["request_text"] == "Rename the app"
    assert harness.linear.state_name(issue) == "In Progress"


async def test_repo_label_beats_the_default(harness: Harness) -> None:
    label = harness.linear.label("repo: example-org/other-repo")
    harness.linear.issue("Uses the label", labels=[label])
    group = harness.linear.label("grouped-repo", parent="Repo")
    harness.linear.issue("Uses the group", labels=[group])
    await harness.poll()
    assert [p["target_repo"] for p in harness.bus.payloads()] == [
        "example-org/other-repo",
        "grouped-repo",
    ]


async def test_no_repo_label_and_no_default_is_a_comment_once(tmp_path: Any) -> None:
    harness = Harness(tmp_path, default_repo=None)
    issue = harness.linear.issue("Which repo?")
    await harness.poll()
    await harness.poll()
    assert harness.bus.published == []
    comments = harness.linear.comments_on(issue)
    assert len(comments) == 1
    assert comments[0].startswith("Factory: ")
    assert "which repository" in comments[0]
    assert harness.linear.state_name(issue) == "Todo"


async def test_unusable_repo_name_and_two_repo_labels_are_refused(harness: Harness) -> None:
    bad = harness.linear.issue("Bad", labels=[harness.linear.label("repo: has spaces in it")])
    two = harness.linear.issue(
        "Two",
        labels=[harness.linear.label("repo: one"), harness.linear.label("repo: two")],
    )
    await harness.poll()
    assert harness.bus.published == []
    assert "not a repository name" in harness.linear.comments_on(bad)[0]
    assert "more than one repo label" in harness.linear.comments_on(two)[0]


# ---------------------------------------------------------------------------
# Missions
# ---------------------------------------------------------------------------


def _mission(linear: FakeLinear, name: str = "mission: Sharing") -> str:
    return linear.label(name)


async def test_mission_waits_until_every_member_is_in_todo(harness: Harness) -> None:
    linear = harness.linear
    label = _mission(linear)
    a = linear.issue("Share a note", "By link.", labels=[label])
    b = linear.issue("Revoke a share", labels=[label], state="Backlog", blocked_by=[a.id])
    linear.issue("Old idea", labels=[label], state="Canceled")
    linear.issue("Shipped part", labels=[label], state="Done")
    linear.issue("Duplicate part", labels=[label], state="Duplicate")

    await harness.poll()
    assert harness.bus.published == []
    assert linear.comments_on(a) == []

    linear.move(b, "Todo")
    await harness.poll()
    await harness.poll()
    assert len(harness.bus.published) == 1
    payload = harness.bus.payloads()[0]
    cid = f"{mission_prefix(label)}1"
    assert payload["correlation_id"] == cid
    assert cid == f"lin-m-{label.replace('-', '')}-1" and len(label.replace("-", "")) == 32
    assert payload["queue_command"] == {
        "verb": "mission",
        "title": "Sharing",
        "features": [
            {
                "key": "ENG1",
                "needs": [],
                "no_sign_in": False,
                "sentence": "Share a note\n\nBy link.",
            },
            {"key": "ENG2", "needs": ["ENG1"], "no_sign_in": False, "sentence": "Revoke a share"},
        ],
    }
    assert payload["request_text"] == (
        "mission: Sharing\nENG1: Share a note By link.\nENG2 (needs ENG1): Revoke a share"
    )
    assert payload["originating_adapter"] == "linear"
    assert payload["target_repo"] == "example-repo"
    for issue in (a, b):
        assert harness.sent_comments(issue) == [f"Factory: Sent to the factory as `{cid}`"]
        assert linear.state_name(issue) == "In Progress"


async def test_mission_label_group_and_no_sign_in(harness: Harness) -> None:
    linear = harness.linear
    member = linear.label("Notes app", parent="Mission")
    no_sign_in = linear.label("No Sign-In")
    linear.issue("Public page", labels=[member, no_sign_in])
    await harness.poll()
    command = harness.bus.payloads()[0]["queue_command"]
    assert command["title"] == "Notes app"
    assert command["features"][0]["no_sign_in"] is True


async def test_single_issue_has_no_no_sign_in_field_but_mission_does(harness: Harness) -> None:
    harness.linear.issue("Solo", labels=[harness.linear.label("no sign-in")])
    await harness.poll()
    assert "queue_command" not in harness.bus.payloads()[0]


async def test_out_of_mission_done_blocker_is_ignored(harness: Harness) -> None:
    linear = harness.linear
    outside = linear.issue("Earlier work", state="Done")
    label = _mission(linear)
    linear.issue("Builds on it", labels=[label], blocked_by=[outside.id])
    await harness.poll()
    assert harness.bus.payloads()[0]["queue_command"]["features"][0]["needs"] == []


async def test_out_of_mission_open_blocker_stops_the_mission(harness: Harness) -> None:
    linear = harness.linear
    outside = linear.issue("Not yet done", state="In Progress")
    label = _mission(linear)
    blocked = linear.issue("Builds on it", labels=[label], blocked_by=[outside.id])
    other = linear.issue("Also in mission", labels=[label])
    await harness.poll()
    await harness.poll()
    assert harness.bus.published == []
    comments = linear.comments_on(blocked)
    assert len(comments) == 1
    assert "blocked by ENG-1" in comments[0]
    assert linear.comments_on(other) == []
    assert linear.state_name(blocked) == "Todo"


async def test_mission_repo_disagreement_comments_on_each_member(harness: Harness) -> None:
    linear = harness.linear
    label = _mission(linear)
    a = linear.issue("One", labels=[label, linear.label("repo: first")])
    b = linear.issue("Two", labels=[label])  # the default, example-repo
    await harness.poll()
    assert harness.bus.published == []
    for issue in (a, b):
        (only,) = linear.comments_on(issue)
        assert "different repositories" in only
        assert "ENG-1 → `first`" in only and "ENG-2 → `example-repo`" in only


async def test_mission_with_a_circle_is_not_sent(harness: Harness) -> None:
    linear = harness.linear
    label = _mission(linear)
    a = linear.issue("A", labels=[label])
    b = linear.issue("B", labels=[label], blocked_by=[a.id])
    a.blocked_by.append(b.id)
    await harness.poll()
    assert harness.bus.published == []
    assert "circle" in linear.comments_on(a)[0]
    assert "circle" in linear.comments_on(b)[0]


async def test_mission_with_too_many_members_is_not_sent(harness: Harness) -> None:
    linear = harness.linear
    label = _mission(linear)
    issues = [linear.issue(f"Part {n}", labels=[label]) for n in range(21)]
    await harness.poll()
    assert harness.bus.published == []
    assert "between 1 and 20" in linear.comments_on(issues[0])[0]


async def test_an_issue_with_two_mission_labels_holds_its_mission(harness: Harness) -> None:
    linear = harness.linear
    first, second = _mission(linear, "mission: First"), _mission(linear, "mission: Second")
    both = linear.issue("In two", labels=[first, second])
    plain = linear.issue("Only first", labels=[first])
    await harness.poll()
    await harness.poll()
    assert harness.bus.published == []
    assert len(linear.comments_on(both)) == 1
    assert "more than one mission label" in linear.comments_on(both)[0]
    assert linear.comments_on(plain) == []


async def test_a_running_mission_comments_once_on_a_newly_labelled_issue(harness: Harness) -> None:
    linear = harness.linear
    label = _mission(linear)
    linear.issue("First part", labels=[label])
    await harness.poll()
    assert len(harness.bus.published) == 1

    late = linear.issue("Late part", labels=[label])
    await harness.poll()
    await harness.poll()
    assert len(harness.bus.published) == 1
    (only,) = linear.comments_on(late)
    assert "already running" in only and "next attempt" in only
    assert linear.state_name(late) == "Todo"


async def test_a_reserved_issue_is_left_out_of_a_mission(harness: Harness) -> None:
    linear = harness.linear
    running = linear.issue("Running alone")
    await harness.poll()
    assert harness.store.reservations() == {running.id: "lin-ENG-1-1"}

    # Someone gives the running issue a mission label and moves it back to Todo.
    label = _mission(linear)
    running.label_ids.append(label)
    linear.move(running, "Todo")
    fresh = linear.issue("New part", labels=[label])
    await harness.poll()

    assert len(harness.bus.published) == 2
    command = harness.bus.payloads()[1]["queue_command"]
    assert [f["key"] for f in command["features"]] == ["ENG2"]
    assert "already with the factory as `lin-ENG-1-1`" in linear.comments_on(running)[-1]
    assert linear.state_name(fresh) == "In Progress"


# ---------------------------------------------------------------------------
# Attempts
# ---------------------------------------------------------------------------


async def test_attempt_number_goes_up_after_an_attempt_ends(harness: Harness) -> None:
    linear = harness.linear
    issue = linear.issue("Retry me")
    await harness.poll()
    linear.move(issue, "Todo")  # moved back while the attempt is open
    await harness.poll()
    assert len(harness.bus.published) == 1
    assert "already with the factory" in linear.comments_on(issue)[-1]

    harness.attempts.ended.add("lin-ENG-1-1")
    await harness.poll()
    assert [p["correlation_id"] for p in harness.bus.payloads()] == ["lin-ENG-1-1", "lin-ENG-1-2"]
    assert harness.store.reservations() == {issue.id: "lin-ENG-1-2"}


async def test_a_new_record_continues_numbers_found_in_forges_record(harness: Harness) -> None:
    issue = harness.linear.issue("Old issue")
    harness.attempts.recorded = [RecordedAttempt("lin-ENG-1-3", open=False)]
    await harness.poll()
    assert harness.bus.payloads()[0]["correlation_id"] == "lin-ENG-1-4"
    assert harness.linear.state_name(issue) == "In Progress"


async def test_a_new_record_reserves_open_attempts_from_forge_and_the_intake_queue(
    harness: Harness,
) -> None:
    linear = harness.linear
    single = linear.issue("Filed by Forge, open")
    waiting_a = linear.issue("Mission part A")
    waiting_b = linear.issue("Mission part B")
    label = linear.label("mission: Waiting")
    waiting_a.label_ids.append(label)
    waiting_b.label_ids.append(label)
    mission_cid = f"{mission_prefix(label)}2"
    harness.attempts.recorded = [RecordedAttempt("lin-ENG-1-1", open=True)]
    harness.intake.waiting = [
        WaitingRequest(
            mission_cid,
            {"queue_command": {"verb": "mission", "features": [{"key": "ENG2"}, {"key": "ENG3"}]}},
        )
    ]
    await harness.poll()
    assert harness.bus.published == []
    assert harness.store.reservations() == {
        single.id: "lin-ENG-1-1",
        waiting_a.id: mission_cid,
        waiting_b.id: mission_cid,
    }
    # Linear's comments played no part, and the next mission attempt is 3.
    harness.attempts.ended.add(mission_cid)
    await harness.poll()
    assert harness.bus.payloads()[0]["correlation_id"] == f"{mission_prefix(label)}3"


async def test_a_new_record_sends_nothing_when_the_intake_queue_cannot_be_read(
    harness: Harness,
) -> None:
    harness.linear.issue("Waits for the rebuild")
    harness.intake.fail = True
    with pytest.raises(RebuildUnavailable):
        await harness.poll()
    assert harness.bus.published == []
    # The intake queue is read first: Forge's record was not even asked.
    assert "recorded_attempts" not in harness.attempts.asked
    harness.intake.fail = False
    await harness.poll()
    assert len(harness.bus.published) == 1


async def test_a_new_record_sends_nothing_when_forges_record_cannot_be_read(
    harness: Harness,
) -> None:
    harness.linear.issue("Waits for the rebuild")
    harness.attempts.unreadable = True
    with pytest.raises(RebuildUnavailable):
        await harness.poll()
    assert harness.intake.read  # the intake queue was read first
    assert harness.bus.published == []
    assert harness.store.is_empty()


async def test_stage_three_default_fails_closed_on_a_new_record(tmp_path: Any) -> None:
    linear = FakeLinear()
    linear.issue("Nothing reads Forge yet")
    client = linear.client()
    door = LinearDoor(
        client=client,
        publisher=CapturedBus(),
        store=DoorStore(tmp_path / "new.sqlite3"),
        settings=DoorSettings(team="ENG", owner_identity=OWNER, default_repo="example-repo"),
        attempts=AssumeAttemptsOpen(),
        intake=FakeIntake(),
    )
    with pytest.raises(RebuildUnavailable):
        await door.poll_once()
    await client.aclose()


async def test_an_existing_record_is_not_rebuilt(harness: Harness) -> None:
    harness.linear.issue("First")
    await harness.poll()
    harness.intake.fail = True  # would stop a rebuild; none is needed
    harness.attempts.recorded = [RecordedAttempt("lin-ENG-2-1", open=True)]
    harness.linear.issue("Second")
    await harness.poll()
    assert [p["correlation_id"] for p in harness.bus.payloads()] == ["lin-ENG-1-1", "lin-ENG-2-1"]


async def test_unreadable_attempt_record_keeps_reservations(harness: Harness) -> None:
    issue = harness.linear.issue("Running")
    await harness.poll()
    harness.attempts.unreadable = True
    harness.linear.move(issue, "Todo")
    await harness.poll()
    assert harness.store.reservations() == {issue.id: "lin-ENG-1-1"}
    assert len(harness.bus.published) == 1


async def test_intake_queue_reads_the_stream_without_a_consumer() -> None:
    info = SimpleNamespace(
        state=SimpleNamespace(
            subjects={
                "pipeline.planning-queued.lin-ENG-7-1": 1,
                "pipeline.planning-queued.some-slack-id": 1,
            }
        )
    )

    class Msg:
        data = json.dumps({"payload": {"correlation_id": "lin-ENG-7-1"}}).encode()

    class FakeJetStream:
        def __init__(self) -> None:
            self.calls: list[tuple[str, ...]] = []

        async def stream_info(self, name: str, subjects_filter: str | None = None) -> Any:
            self.calls.append(("stream_info", name, subjects_filter or ""))
            return info

        async def get_last_msg(self, stream: str, subject: str) -> Any:
            self.calls.append(("get_last_msg", stream, subject))
            return Msg()

        def __getattr__(self, name: str) -> Any:  # subscribe, pull_subscribe, ...
            raise AssertionError(f"the intake reader must not call {name}")

    class FakeNats:
        js = FakeJetStream()

    found = await NatsIntakeQueue(FakeNats()).waiting_requests()
    assert found == [WaitingRequest("lin-ENG-7-1", {"correlation_id": "lin-ENG-7-1"})]
    assert FakeNats.js.calls == [
        ("stream_info", "PIPELINE", "pipeline.planning-queued.>"),
        ("get_last_msg", "PIPELINE", "pipeline.planning-queued.lin-ENG-7-1"),
    ]


# ---------------------------------------------------------------------------
# Edits after sending
# ---------------------------------------------------------------------------


async def test_edit_after_sending_is_commented_once(harness: Harness) -> None:
    linear = harness.linear
    issue = linear.issue("Before")
    await harness.poll()
    linear.touch(issue)  # a status change alone is not an edit
    await harness.poll()
    assert len(linear.comments_on(issue)) == 1

    issue.title = "After"
    linear.touch(issue)
    await harness.poll()
    await harness.poll()
    edits = [c for c in linear.comments_on(issue) if "changed after it was sent" in c]
    assert len(edits) == 1 and "`lin-ENG-1-1`" in edits[0]


# ---------------------------------------------------------------------------
# Failures, back-off and the key
# ---------------------------------------------------------------------------


async def test_rate_limited_reply_backs_off_until_the_reset(harness: Harness) -> None:
    reset_ms = int((time.time() + 600) * 1000)
    harness.linear.fail_next["DoorTeams"] = [rate_limited(reset_ms)]
    with pytest.raises(LinearRateLimited) as caught:
        await harness.poll()
    assert caught.value.reset_at == pytest.approx(reset_ms / 1000)
    delay = harness.door.next_delay(caught.value, now=time.time())
    assert 590 <= delay <= 600
    await harness.poll()  # the next poll works


async def test_run_survives_failures_and_stops_cleanly(harness: Harness) -> None:
    harness.linear.fail_next["DoorTeams"] = [rate_limited(int(time.time() * 1000) + 1)]
    harness.door._settings = DoorSettings(
        team="ENG", owner_identity=OWNER, default_repo="example-repo", poll_seconds=0.01
    )
    harness.linear.issue("Sent by the loop")
    stop = asyncio.Event()
    delays: list[float] = []
    original = harness.door.next_delay

    def short(error: BaseException | None, **kw: Any) -> float:
        delays.append(original(error, **kw))
        if harness.bus.published:
            stop.set()
        return 0.0

    harness.door.next_delay = short  # type: ignore[method-assign]
    await asyncio.wait_for(harness.door.run(stop), timeout=10)
    assert len(harness.bus.published) == 1


async def test_bad_key_is_one_clear_log_line_and_a_five_minute_retry(harness: Harness) -> None:
    harness.linear.fail_all = bad_key()
    with capture_logs() as logs:
        for _ in range(3):
            with pytest.raises(LinearAuthError) as caught:
                await harness.poll()
            assert harness.door.next_delay(caught.value) == BAD_KEY_RETRY_SECONDS
    assert [entry["event"] for entry in logs].count("linear_door_bad_key") == 1
    assert harness.bus.published == []
    assert harness.linear.comments == []


def test_failures_back_off_to_five_minutes(harness: Harness) -> None:
    door = harness.door
    delays = [door.next_delay(LinearError("down")) for _ in range(7)]
    assert delays == [30, 60, 120, 240] + [MAX_BACKOFF_SECONDS] * 3
    assert door.next_delay(None) == 30
    assert door.next_delay(LinearError("down")) == 30


async def test_the_key_never_reaches_a_log(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    harness.linear.issue("Something")
    with capture_logs() as logs:
        harness.linear.fail_next["DoorTeams"] = [bad_key(), server_error()]
        for _ in range(2):
            with pytest.raises(LinearError) as caught:
                await harness.poll()
            harness.door.next_delay(caught.value)
            assert FAKE_KEY not in str(caught.value)
        await harness.poll()
        harness.door.next_delay(None)
    everything = json.dumps(logs, default=str) + caplog.text
    assert FAKE_KEY not in everything
    assert FAKE_KEY not in repr(harness.client)
    assert logs  # something was logged


async def test_team_is_found_by_key_or_exact_name(tmp_path: Any) -> None:
    linear = FakeLinear(team_key="ENG", team_name="Example Team")
    client = linear.client()
    assert (await client.find_team("eng")).id == linear.team_id
    assert (await client.find_team("Example Team")).id == linear.team_id
    assert await client.find_team("example team") is None
    await client.aclose()


async def test_partial_success_with_errors_is_a_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"data": {"teams": {"nodes": []}}, "errors": [{"message": "partly broken"}]}
        )

    from jarvis.infrastructure.linear.client import LinearClient

    client = LinearClient(FAKE_KEY, transport=httpx.MockTransport(handler))
    with pytest.raises(LinearError, match="partly broken"):
        await client.find_team("ENG")
    await client.aclose()


async def test_personal_key_is_sent_without_bearer() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        assert str(request.url) == "https://api.linear.app/graphql"
        return httpx.Response(200, json={"data": {"teams": {"nodes": []}}})

    from jarvis.infrastructure.linear.client import LinearClient

    client = LinearClient(FAKE_KEY, transport=httpx.MockTransport(handler))
    await client.find_team("ENG")
    await client.aclose()
    assert seen == [FAKE_KEY]


# ---------------------------------------------------------------------------
# The operator's release
# ---------------------------------------------------------------------------


async def test_release_moves_to_backlog_frees_and_numbers_the_next_attempt(
    harness: Harness,
) -> None:
    linear = harness.linear
    issue = linear.issue("Refused without filing")
    await harness.poll()
    cid, released = await harness.door.release("eng-1")
    assert (cid, released) == ("lin-ENG-1-1", ["ENG-1"])
    assert linear.state_name(issue) == "Backlog"
    assert "An operator released attempt `lin-ENG-1-1`" in linear.comments_on(issue)[-1]
    assert harness.store.reservations() == {}

    linear.move(issue, "Todo")
    await harness.poll()
    assert [p["correlation_id"] for p in harness.bus.payloads()] == ["lin-ENG-1-1", "lin-ENG-1-2"]


async def test_a_released_pending_send_is_never_published(harness: Harness) -> None:
    issue = harness.linear.issue("Bus down")
    harness.bus.fail = True
    with pytest.raises(BusUnavailable):
        await harness.poll()
    await harness.door.release("ENG-1")
    harness.bus.fail = False
    await harness.poll()  # the issue is in Backlog now; nothing is resumed
    assert harness.bus.published == []
    assert harness.linear.state_name(issue) == "Backlog"


async def test_release_of_an_issue_in_no_open_attempt_is_refused(harness: Harness) -> None:
    with pytest.raises(LookupError):
        await harness.door.release("ENG-99")


async def test_release_keeps_the_attempt_when_linear_fails(harness: Harness) -> None:
    harness.linear.issue("Refused")
    await harness.poll()
    harness.linear.fail_next["DoorIssueMove"] = [server_error()]
    with pytest.raises(LinearError):
        await harness.door.release("ENG-1")
    assert harness.store.attempt_holding("ENG-1") == "lin-ENG-1-1"


async def test_a_rebuild_that_fails_part_way_writes_nothing(harness: Harness) -> None:
    issue = harness.linear.issue("Held by Forge")
    harness.attempts.recorded = [RecordedAttempt("lin-ENG-1-1", open=True)]
    harness.linear.fail_next["DoorIssuesByNumber"] = [server_error()]
    with pytest.raises(LinearError):
        await harness.poll()
    assert harness.store.is_empty()
    assert harness.bus.published == []
    await harness.poll()
    assert harness.store.reservations() == {issue.id: "lin-ENG-1-1"}
    assert harness.bus.published == []


# ---------------------------------------------------------------------------
# Stage 3 repair pass (the coach's review of f4d6698)
# ---------------------------------------------------------------------------


async def test_a_send_linear_keeps_refusing_does_not_stop_the_others(harness: Harness) -> None:
    linear = harness.linear
    deleted = linear.issue("Deleted after it was published")
    linear.fail_next["DoorCommentCreate"] = [server_error()]
    with pytest.raises(LinearError):
        await harness.poll()  # published; its comment failed
    linear.gone.add(deleted.id)  # and now the issue is gone
    other = linear.issue("Sent anyway")
    await harness.poll()
    await harness.poll()
    assert [p["correlation_id"] for p in harness.bus.payloads()] == ["lin-ENG-1-1", "lin-ENG-2-1"]
    assert linear.state_name(other) == "In Progress"
    assert harness.store.get_send("lin-ENG-1-1").status == "published"


async def test_a_pending_send_that_cannot_publish_still_stops_the_poll(harness: Harness) -> None:
    harness.linear.issue("Bus down")
    harness.bus.fail = True
    with pytest.raises(BusUnavailable):
        await harness.poll()
    harness.linear.issue("Not reached while the bus is down")
    with pytest.raises(BusUnavailable):
        await harness.poll()
    assert harness.bus.published == []


async def test_no_edit_comment_after_the_attempt_has_ended(harness: Harness) -> None:
    linear = harness.linear
    issue = linear.issue("Before")
    await harness.poll()
    await harness.door.release("ENG-1")
    issue.title = "After"
    linear.touch(issue)
    await harness.poll()
    assert not [c for c in linear.comments_on(issue) if "changed after it was sent" in c]


async def test_an_issue_with_too_many_labels_is_not_guessed_from(harness: Harness) -> None:
    linear = harness.linear
    many = [linear.label(f"tag {n}") for n in range(21)]
    crowded = linear.issue("Crowded", labels=many)
    label = linear.label("mission: Crowd")
    member = linear.issue("Member", labels=[label])
    crowded_member = linear.issue("Crowded member", labels=[label, *many])
    await harness.poll()
    await harness.poll()
    # Neither the crowded issue nor the mission whose membership read would
    # be incomplete is sent.
    assert harness.bus.published == []
    for issue in (crowded, crowded_member):
        (only,) = linear.comments_on(issue)
        assert "more labels or blocking links" in only
    assert linear.comments_on(member) == []


async def test_forbidden_is_an_ordinary_error_not_a_bad_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errors": [{"message": "Forbidden", "extensions": {"code": "FORBIDDEN"}}]},
        )

    from jarvis.infrastructure.linear.client import LinearClient

    client = LinearClient(FAKE_KEY, transport=httpx.MockTransport(handler))
    with pytest.raises(LinearError) as caught:
        await client.find_team("ENG")
    assert not isinstance(caught.value, LinearAuthError)
    await client.aclose()
