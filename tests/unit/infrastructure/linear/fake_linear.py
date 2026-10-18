"""A fake Linear GraphQL server for the Linear door's tests.

It answers the door's own named operations from an in-memory workspace, over
``httpx.MockTransport``, so nothing leaves the process. All names and ids are
made up.
"""

from __future__ import annotations

import itertools
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from jarvis.infrastructure.linear.client import LinearClient

FAKE_KEY = "fake-linear-key-for-tests-only-7f3a"

_OPERATION_RE = re.compile(r"(?:query|mutation)\s+(\w+)")


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class FakeLabel:
    id: str
    name: str
    parent: str | None = None


@dataclass
class FakeIssue:
    id: str
    number: int
    title: str
    description: str
    state_id: str
    label_ids: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)  # issue ids that block this one
    updated_at: datetime = field(default_factory=lambda: datetime(2026, 1, 1, tzinfo=UTC))


@dataclass
class FakeComment:
    id: str
    issue_id: str
    body: str
    parent_id: str | None = None


class FakeLinear:
    """One team, its statuses, labels, issues and comments."""

    def __init__(self, *, team_key: str = "ENG", team_name: str = "Example Team") -> None:
        self.team_id = _uuid()
        self.team_key = team_key
        self.team_name = team_name
        self.states = {
            name: (_uuid(), kind)
            for name, kind in [
                ("Triage", "triage"),
                ("Backlog", "backlog"),
                ("Todo", "unstarted"),
                ("In Progress", "started"),
                ("Done", "completed"),
                ("Canceled", "canceled"),
                ("Duplicate", "duplicate"),
            ]
        }
        self.labels: dict[str, FakeLabel] = {}
        self.issues: dict[str, FakeIssue] = {}
        self.comments: list[FakeComment] = []
        self.calls: list[str] = []
        self.moves: list[tuple[str, str]] = []
        self._numbers = itertools.count(1)
        self._clock = itertools.count(1)
        # Failure injection: operation name -> list of responses to give first.
        self.fail_next: dict[str, list[httpx.Response]] = {}
        self.fail_all: httpx.Response | None = None

    # -- building the workspace ---------------------------------------------

    def label(self, name: str, parent: str | None = None) -> str:
        for existing in self.labels.values():
            if existing.name == name and existing.parent == parent:
                return existing.id
        label_id = _uuid()
        self.labels[label_id] = FakeLabel(label_id, name, parent)
        return label_id

    def issue(
        self,
        title: str,
        description: str = "",
        *,
        state: str = "Todo",
        labels: list[str] | None = None,
        blocked_by: list[str] | None = None,
    ) -> FakeIssue:
        issue = FakeIssue(
            id=_uuid(),
            number=next(self._numbers),
            title=title,
            description=description,
            state_id=self.states[state][0],
            label_ids=list(labels or []),
            blocked_by=list(blocked_by or []),
        )
        self.issues[issue.id] = issue
        return issue

    def identifier(self, issue: FakeIssue) -> str:
        return f"{self.team_key}-{issue.number}"

    def state_name(self, issue: FakeIssue) -> str:
        for name, (state_id, _) in self.states.items():
            if state_id == issue.state_id:
                return name
        raise KeyError(issue.state_id)

    def move(self, issue: FakeIssue, state: str) -> None:
        issue.state_id = self.states[state][0]
        self.touch(issue)

    def touch(self, issue: FakeIssue) -> None:
        issue.updated_at = datetime.now(UTC) + timedelta(seconds=next(self._clock))

    def comments_on(self, issue: FakeIssue) -> list[str]:
        return [c.body for c in self.comments if c.issue_id == issue.id]

    def client(self) -> LinearClient:
        return LinearClient(FAKE_KEY, transport=httpx.MockTransport(self.handle))

    # -- serving -------------------------------------------------------------

    def _state(self, state_id: str) -> dict[str, Any]:
        for name, (sid, kind) in self.states.items():
            if sid == state_id:
                return {"id": sid, "name": name, "type": kind}
        raise KeyError(state_id)

    def _issue_node(self, issue: FakeIssue) -> dict[str, Any]:
        labels = []
        for label_id in issue.label_ids:
            label = self.labels[label_id]
            labels.append(
                {
                    "id": label.id,
                    "name": label.name,
                    "parent": {"name": label.parent} if label.parent else None,
                }
            )
        relations = []
        for blocker_id in issue.blocked_by:
            blocker = self.issues[blocker_id]
            state = self._state(blocker.state_id)
            relations.append(
                {
                    "type": "blocks",
                    "issue": {
                        "id": blocker.id,
                        "identifier": self.identifier(blocker),
                        "state": {"name": state["name"], "type": state["type"]},
                    },
                }
            )
        # An unrelated relation type the door must ignore.
        relations.append(
            {
                "type": "related",
                "issue": {
                    "id": "unrelated",
                    "identifier": "OTHER-1",
                    "state": {"name": "Todo", "type": "unstarted"},
                },
            }
        )
        return {
            "id": issue.id,
            "identifier": self.identifier(issue),
            "title": issue.title,
            "description": issue.description or None,
            "url": f"https://linear.example/issue/{self.identifier(issue)}",
            "updatedAt": issue.updated_at.isoformat().replace("+00:00", "Z"),
            "state": self._state(issue.state_id),
            "labels": {"nodes": labels},
            "inverseRelations": {"nodes": relations},
        }

    @staticmethod
    def _page(nodes: list[dict[str, Any]], after: str | None, size: int = 2) -> dict[str, Any]:
        # Small pages, so the door's pagination is exercised.
        start = int(after) if after else 0
        chunk = nodes[start : start + size]
        more = start + size < len(nodes)
        return {
            "nodes": chunk,
            "pageInfo": {"hasNextPage": more, "endCursor": str(start + size) if more else None},
        }

    def _issues(self, **want: Any) -> list[FakeIssue]:
        found = sorted(self.issues.values(), key=lambda i: i.number)
        if "state_id" in want:
            found = [i for i in found if i.state_id == want["state_id"]]
        if "label_id" in want:
            found = [i for i in found if want["label_id"] in i.label_ids]
        if "ids" in want:
            found = [i for i in found if i.id in want["ids"]]
        return found

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == FAKE_KEY
        body = json.loads(request.content)
        match = _OPERATION_RE.search(body["query"])
        assert match, body["query"]
        operation = match.group(1)
        self.calls.append(operation)
        if self.fail_all is not None:
            return self.fail_all
        queued = self.fail_next.get(operation)
        if queued:
            return queued.pop(0)
        variables = body.get("variables") or {}
        data = getattr(self, f"_op_{operation}")(variables)
        return httpx.Response(200, json={"data": data})

    def _op_DoorTeams(self, v: dict[str, Any]) -> dict[str, Any]:
        text = v["text"]
        nodes = []
        if text.lower() == self.team_key.lower() or text == self.team_name:
            nodes.append({"id": self.team_id, "key": self.team_key, "name": self.team_name})
        return {"teams": {"nodes": nodes}}

    def _op_DoorStates(self, v: dict[str, Any]) -> dict[str, Any]:
        assert v["teamId"] == self.team_id
        nodes = [
            {"id": sid, "name": name, "type": kind} for name, (sid, kind) in self.states.items()
        ]
        return {"workflowStates": self._page(nodes, v.get("after"), size=100)}

    def _op_DoorIssuesInState(self, v: dict[str, Any]) -> dict[str, Any]:
        nodes = [self._issue_node(i) for i in self._issues(state_id=v["stateId"])]
        return {"issues": self._page(nodes, v.get("after"))}

    def _op_DoorIssuesWithLabel(self, v: dict[str, Any]) -> dict[str, Any]:
        nodes = [self._issue_node(i) for i in self._issues(label_id=v["labelId"])]
        return {"issues": self._page(nodes, v.get("after"))}

    def _op_DoorIssuesById(self, v: dict[str, Any]) -> dict[str, Any]:
        nodes = [self._issue_node(i) for i in self._issues(ids=set(v["ids"]))]
        return {"issues": self._page(nodes, v.get("after"))}

    def _op_DoorIssuesByNumber(self, v: dict[str, Any]) -> dict[str, Any]:
        assert v["teamId"] == self.team_id
        wanted = {int(n) for n in v["numbers"]}
        nodes = [self._issue_node(i) for i in self._issues() if i.number in wanted]
        return {"issues": self._page(nodes, v.get("after"))}

    def _op_DoorComments(self, v: dict[str, Any]) -> dict[str, Any]:
        text = v["text"].lower()
        nodes = [
            {"id": c.id, "body": c.body}
            for c in self.comments
            if c.issue_id == v["issueId"] and text in c.body.lower()
        ]
        return {"issue": {"comments": self._page(nodes, v.get("after"))}}

    def _op_DoorCommentCreate(self, v: dict[str, Any]) -> dict[str, Any]:
        data = v["input"]
        comment = FakeComment(_uuid(), data["issueId"], data["body"], data.get("parentId"))
        self.comments.append(comment)
        return {"commentCreate": {"success": True, "comment": {"id": comment.id}}}

    def _op_DoorIssueMove(self, v: dict[str, Any]) -> dict[str, Any]:
        issue = self.issues[v["id"]]
        issue.state_id = v["stateId"]
        self.moves.append((self.identifier(issue), self.state_name(issue)))
        return {"issueUpdate": {"success": True}}


# -- canned failures ---------------------------------------------------------


def rate_limited(reset_epoch_ms: int) -> httpx.Response:
    return httpx.Response(
        400,
        headers={"X-RateLimit-Requests-Reset": str(reset_epoch_ms)},
        json={
            "errors": [{"message": "Rate limit exceeded", "extensions": {"code": "RATELIMITED"}}]
        },
    )


def bad_key() -> httpx.Response:
    return httpx.Response(
        400,
        json={
            "errors": [
                {
                    "message": "Authentication required, not authenticated",
                    "extensions": {"code": "AUTHENTICATION_ERROR"},
                }
            ]
        },
    )


def server_error() -> httpx.Response:
    return httpx.Response(503, text="unavailable")


class CapturedBus:
    """A bus publisher that keeps what it was given; can be told to fail."""

    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []
        self.fail = False

    async def publish_bytes(self, *, subject: str, data: bytes) -> None:
        if self.fail:
            raise TimeoutError("no acknowledgement")
        self.published.append((subject, data))

    def payloads(self) -> list[dict[str, Any]]:
        return [json.loads(data)["payload"] for _, data in self.published]


class FakeAttempts:
    """Forge's record, as the test describes it."""

    def __init__(self) -> None:
        self.ended: set[str] = set()
        self.recorded: list[Any] = []
        self.unreadable = False
        self.asked: list[str] = []

    def is_open(self, correlation_id: str) -> bool:
        from jarvis.infrastructure.linear.door import AttemptRecordUnavailable

        self.asked.append(correlation_id)
        if self.unreadable:
            raise AttemptRecordUnavailable("record locked")
        return correlation_id not in self.ended

    def recorded_attempts(self) -> list[Any]:
        from jarvis.infrastructure.linear.door import AttemptRecordUnavailable

        self.asked.append("recorded_attempts")
        if self.unreadable:
            raise AttemptRecordUnavailable("record locked")
        return list(self.recorded)


class FakeIntake:
    """The PIPELINE stream's waiting ``lin-`` requests, as the test describes them."""

    def __init__(self) -> None:
        self.waiting: list[Any] = []
        self.fail = False
        self.read = False

    async def waiting_requests(self) -> list[Any]:
        self.read = True
        if self.fail:
            raise TimeoutError("stream info timed out")
        return list(self.waiting)
