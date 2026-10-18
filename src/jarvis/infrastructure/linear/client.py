"""A small async client for Linear's GraphQL API (the Linear door, stage 3).

Only what the door needs: find the team, read its workflow states, read issues
(the Todo list, a mission label's full membership, a handful by id), read the
door's own comments on an issue, write a comment and move an issue. Stage 4
(writing the factory's cards and progress back to Linear) reuses
:meth:`LinearClient.create_comment` (with ``parent_id`` for replies) and
:meth:`LinearClient.move_issue`, and reads the replies under the door's card
comments with one query (:meth:`LinearClient.replies_under`). Section 11
(Linear projects) reads the team's projects with one top-level ``projects``
query (a ``projects`` field nested inside ``teams`` was refused by Linear,
HTTP 400, on 18 October 2026), creates a project and its GitHub link with
caller-chosen UUID v4 ids, reads a project's open issues and posts a project
update.

Facts about Linear this file relies on (checked 18 October 2026 against
Linear's published schema, ``packages/sdk/src/schema.graphql`` in
``github.com/linear/linear``, and its developer pages "GraphQL" and
"Rate limiting"):

* Endpoint ``https://api.linear.app/graphql``; a personal API key goes in the
  ``Authorization`` header as it is, with no ``Bearer`` (OAuth tokens use
  ``Bearer``).
* A personal key may make 2,500 requests an hour. Over the limit, Linear
  answers **HTTP 400** with ``errors[].extensions.code == "RATELIMITED"`` (not
  429), and ``X-RateLimit-Requests-Reset`` says when the window resets, in
  UTC epoch **milliseconds**.
* A query can partly fail with HTTP 200 and an ``errors`` array beside the
  data; this client treats any ``errors`` as a failure.
* One query may cost at most 10,000 complexity points, and a connection
  multiplies its contents by its page size, so issue pages here are 50 with
  20 labels and 20 relations each (about 5,000 points), not 100.

THE KEY. It is held only inside the ``httpx.AsyncClient``'s default headers.
Nothing in this module logs a header, a request, or the key, and no error
raised here carries one: messages are built from Linear's own error text,
status codes and exception class names only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"
REQUEST_TIMEOUT_SECONDS = 20.0

# Page sizes — see the complexity note in the module docstring.
_ISSUE_PAGE = 50
_NESTED_PAGE = 20
_FLAT_PAGE = 100
# A guard against a cursor that never ends; 100 pages of 50 is 5,000 issues.
_MAX_PAGES = 100

# Linear error codes that mean "this key is not accepted". FORBIDDEN is not
# one: it refuses one request (an issue or team the key cannot touch), and is
# an ordinary error for that request.
_AUTH_CODES = frozenset({"AUTHENTICATION_ERROR", "UNAUTHENTICATED"})
_RATE_LIMITED = "RATELIMITED"
#: The only errors the door treats as Linear refusing a request for good
#: (Codex review R9): an entity that does not exist, or input Linear will not
#: take. Linear marks these with ``extensions.code`` INVALID_INPUT (or
#: ``extensions.type`` "invalid input") and, for a missing entity, the message
#: "Entity not found". Every other error, including an internal error inside
#: an HTTP 200, is an outage and is tried again.
_REFUSED_CODES = frozenset({"INVALID_INPUT", "ENTITY_NOT_FOUND", "NOT_FOUND", "BAD_USER_INPUT"})
_REFUSED_TYPES = frozenset({"invalid input"})
# Reset headers, epoch milliseconds. The first is the hourly request window;
# the others are the complexity window and a per-endpoint window, which Linear
# also sends when one of those is what ran out.
_RESET_HEADERS = (
    "X-RateLimit-Requests-Reset",
    "X-RateLimit-Complexity-Reset",
    "X-RateLimit-Endpoint-Requests-Reset",
)


# ---------------------------------------------------------------------------
# Errors — none of them ever carries the key or a header
# ---------------------------------------------------------------------------


class LinearError(Exception):
    """Linear could not be reached, or answered with an error."""


class LinearAuthError(LinearError):
    """Linear refused the API key."""


class LinearRefused(LinearError):
    """Linear answered and refused this request for good: an issue that no
    longer exists, or input it will not take. Only those errors, positively
    identified; anything else (no answer, a time-out, HTTP 5xx, an internal
    or unknown error) is a plain :class:`LinearError` and is tried again."""


class LinearRateLimited(LinearError):
    """Linear's rate limit was reached.

    Attributes:
        reset_at: When the window resets, as a Unix time in seconds, or
            ``None`` when Linear sent no usable reset header.
    """

    def __init__(self, message: str, *, reset_at: float | None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


# ---------------------------------------------------------------------------
# What the door reads
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LinearTeam:
    id: str
    key: str
    name: str


@dataclass(frozen=True)
class LinearState:
    id: str
    name: str
    type: str  # triage | backlog | unstarted | started | completed | canceled | duplicate


@dataclass(frozen=True)
class LinearLabel:
    id: str
    name: str
    parent_name: str | None = None


@dataclass(frozen=True)
class LinearIssueRef:
    """Another issue, as seen from a relation."""

    id: str
    identifier: str
    state_name: str
    state_type: str


@dataclass(frozen=True)
class LinearRelation:
    """One entry of an issue's ``inverseRelations``.

    ``other`` is the relation's ``issue`` field: the issue the relation starts
    from. Which way round "blocks" reads is decided in one place,
    :func:`jarvis.infrastructure.linear.mapping.blockers_of`.
    """

    type: str
    other: LinearIssueRef


@dataclass(frozen=True)
class LinearIssue:
    id: str
    identifier: str
    title: str
    description: str
    url: str
    updated_at: datetime
    state: LinearState
    labels: tuple[LinearLabel, ...] = ()
    inverse_relations: tuple[LinearRelation, ...] = ()
    #: More than one page of labels or relations: what the door would read
    #: from them is not the whole truth, so it is not guessed from.
    truncated: bool = False
    #: The Linear project the issue is in, if any (design section 11.2).
    project_id: str | None = None


@dataclass(frozen=True)
class LinearProject:
    """One of the team's projects, with its external links' URLs (section 11.1)."""

    id: str
    name: str
    url: str
    archived: bool
    #: The project's status is "completed" (Linear's ``ProjectStatusType``).
    completed: bool
    link_urls: tuple[str, ...] = ()
    #: More links than one page holds: its repository is not guessed.
    truncated: bool = False


@dataclass(frozen=True)
class LinearComment:
    id: str
    body: str


@dataclass(frozen=True)
class LinearReply:
    """A reply under one of the door's card comments."""

    id: str
    body: str
    parent_id: str
    user_id: str | None  # None for a reply not written by a person (a bot or integration)


# ---------------------------------------------------------------------------
# GraphQL text
# ---------------------------------------------------------------------------

_ISSUE_FIELDS = f"""
fragment DoorIssue on Issue {{
  id
  identifier
  title
  description
  url
  updatedAt
  state {{ id name type }}
  project {{ id }}
  labels(first: {_NESTED_PAGE}) {{
    nodes {{ id name parent {{ name }} }}
    pageInfo {{ hasNextPage }}
  }}
  inverseRelations(first: {_NESTED_PAGE}) {{
    nodes {{ type issue {{ id identifier state {{ name type }} }} }}
    pageInfo {{ hasNextPage }}
  }}
}}
"""

TEAMS_QUERY = """
query DoorTeams($text: String!) {
  teams(filter: { or: [{ key: { eqIgnoreCase: $text } }, { name: { eq: $text } }] }) {
    nodes { id key name }
  }
}
"""

STATES_QUERY = f"""
query DoorStates($teamId: ID!, $after: String) {{
  workflowStates(
    first: {_FLAT_PAGE}
    after: $after
    filter: {{ team: {{ id: {{ eq: $teamId }} }} }}
  ) {{
    nodes {{ id name type }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""

ISSUES_IN_STATE_QUERY = (
    f"""
query DoorIssuesInState($teamId: ID!, $stateId: ID!, $after: String) {{
  issues(
    first: {_ISSUE_PAGE}
    after: $after
    filter: {{ team: {{ id: {{ eq: $teamId }} }}, state: {{ id: {{ eq: $stateId }} }} }}
  ) {{
    nodes {{ ...DoorIssue }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
    + _ISSUE_FIELDS
)

ISSUES_WITH_LABEL_QUERY = (
    f"""
query DoorIssuesWithLabel($teamId: ID!, $labelId: ID!, $after: String) {{
  issues(
    first: {_ISSUE_PAGE}
    after: $after
    filter: {{
      team: {{ id: {{ eq: $teamId }} }}
      labels: {{ some: {{ id: {{ eq: $labelId }} }} }}
    }}
  ) {{
    nodes {{ ...DoorIssue }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
    + _ISSUE_FIELDS
)

ISSUES_BY_ID_QUERY = (
    f"""
query DoorIssuesById($ids: [ID!]!, $after: String) {{
  issues(first: {_ISSUE_PAGE}, after: $after, filter: {{ id: {{ in: $ids }} }}) {{
    nodes {{ ...DoorIssue }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
    + _ISSUE_FIELDS
)

ISSUES_BY_NUMBER_QUERY = (
    f"""
query DoorIssuesByNumber($teamId: ID!, $numbers: [Float!]!, $after: String) {{
  issues(
    first: {_ISSUE_PAGE}
    after: $after
    filter: {{ team: {{ id: {{ eq: $teamId }} }}, number: {{ in: $numbers }} }}
  ) {{
    nodes {{ ...DoorIssue }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""
    + _ISSUE_FIELDS
)

DOOR_COMMENTS_QUERY = f"""
query DoorComments($issueId: String!, $text: String!, $after: String) {{
  issue(id: $issueId) {{
    comments(
      first: {_FLAT_PAGE}
      after: $after
      filter: {{ body: {{ containsIgnoreCase: $text }} }}
    ) {{
      nodes {{ id body }}
      pageInfo {{ hasNextPage endCursor }}
    }}
  }}
}}
"""

# Root ``comments`` with ``filter.parent.id.in`` (``CommentFilter.parent:
# NullableCommentFilter``; ``Comment.parentId`` and ``Comment.user``): every
# reply under the door's open card comments in one request a poll.
REPLIES_QUERY = f"""
query DoorReplies($parentIds: [ID!]!, $after: String) {{
  comments(
    first: {_FLAT_PAGE}
    after: $after
    filter: {{ parent: {{ id: {{ in: $parentIds }} }} }}
  ) {{
    nodes {{ id body parentId user {{ id }} }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""

# Top-level ``projects`` filtered to the team (``ProjectFilter.accessibleTeams``),
# archived ones included (section 11.1); a project's status type says whether
# it is completed.
PROJECTS_QUERY = f"""
query DoorProjects($teamId: ID!, $after: String) {{
  projects(
    first: {_ISSUE_PAGE}
    after: $after
    includeArchived: true
    filter: {{ accessibleTeams: {{ some: {{ id: {{ eq: $teamId }} }} }} }}
  ) {{
    nodes {{
      id
      name
      url
      archivedAt
      status {{ type }}
      externalLinks(first: {_NESTED_PAGE}) {{
        nodes {{ url label }}
        pageInfo {{ hasNextPage }}
      }}
    }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""

# A project's issues that are not Done, Canceled or a duplicate (section 11.4).
PROJECT_OPEN_ISSUES_QUERY = f"""
query DoorProjectOpenIssues($projectId: ID!, $after: String) {{
  issues(
    first: {_FLAT_PAGE}
    after: $after
    filter: {{
      project: {{ id: {{ eq: $projectId }} }}
      state: {{ type: {{ nin: ["completed", "canceled", "duplicate"] }} }}
    }}
  ) {{
    nodes {{ identifier title }}
    pageInfo {{ hasNextPage endCursor }}
  }}
}}
"""

# A project's updates, to find one whose posting was not confirmed
# (``ProjectUpdateFilter`` has no body filter, so the bodies are read).
PROJECT_UPDATES_QUERY = f"""
query DoorProjectUpdates($projectId: String!, $after: String) {{
  project(id: $projectId) {{
    projectUpdates(first: {_ISSUE_PAGE}, after: $after) {{
      nodes {{ id body }}
      pageInfo {{ hasNextPage endCursor }}
    }}
  }}
}}
"""

PROJECT_CREATE_MUTATION = """
mutation DoorProjectCreate($input: ProjectCreateInput!) {
  projectCreate(input: $input) {
    success
    project { id }
  }
}
"""

LINK_CREATE_MUTATION = """
mutation DoorLinkCreate($input: EntityExternalLinkCreateInput!) {
  entityExternalLinkCreate(input: $input) {
    success
    entityExternalLink { id }
  }
}
"""

PROJECT_UPDATE_CREATE_MUTATION = """
mutation DoorProjectUpdateCreate($input: ProjectUpdateCreateInput!) {
  projectUpdateCreate(input: $input) {
    success
    projectUpdate { id }
  }
}
"""

COMMENT_CREATE_MUTATION = """
mutation DoorCommentCreate($input: CommentCreateInput!) {
  commentCreate(input: $input) {
    success
    comment { id }
  }
}
"""

ISSUE_MOVE_MUTATION = """
mutation DoorIssueMove($id: String!, $stateId: String!) {
  issueUpdate(id: $id, input: { stateId: $stateId }) {
    success
  }
}
"""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _safe_text(value: Any, limit: int = 300) -> str:
    return str(value)[:limit]


def _reset_at(headers: httpx.Headers) -> float | None:
    """The latest future reset time Linear sent, in Unix seconds."""
    now = time.time()
    found: list[float] = []
    for name in _RESET_HEADERS:
        raw = headers.get(name)
        if not raw:
            continue
        try:
            at = float(raw) / 1000.0
        except ValueError:
            continue
        if at > now:
            found.append(at)
    return max(found) if found else None


def _parse_datetime(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def _parse_issue(node: dict[str, Any]) -> LinearIssue:
    state = node.get("state") or {}
    labels = []
    for label in (node.get("labels") or {}).get("nodes") or []:
        parent = label.get("parent") or {}
        labels.append(
            LinearLabel(
                id=str(label.get("id") or ""),
                name=str(label.get("name") or ""),
                parent_name=parent.get("name"),
            )
        )
    relations = []
    for relation in (node.get("inverseRelations") or {}).get("nodes") or []:
        other = relation.get("issue") or {}
        other_state = other.get("state") or {}
        relations.append(
            LinearRelation(
                type=str(relation.get("type") or ""),
                other=LinearIssueRef(
                    id=str(other.get("id") or ""),
                    identifier=str(other.get("identifier") or ""),
                    state_name=str(other_state.get("name") or ""),
                    state_type=str(other_state.get("type") or ""),
                ),
            )
        )
    return LinearIssue(
        id=str(node["id"]),
        identifier=str(node["identifier"]),
        title=str(node.get("title") or ""),
        description=str(node.get("description") or ""),
        url=str(node.get("url") or ""),
        updated_at=_parse_datetime(str(node["updatedAt"])),
        state=LinearState(
            id=str(state.get("id") or ""),
            name=str(state.get("name") or ""),
            type=str(state.get("type") or ""),
        ),
        labels=tuple(labels),
        inverse_relations=tuple(relations),
        truncated=any(
            ((node.get(name) or {}).get("pageInfo") or {}).get("hasNextPage")
            for name in ("labels", "inverseRelations")
        ),
        project_id=str((node.get("project") or {}).get("id") or "") or None,
    )


def _parse_project(node: dict[str, Any]) -> LinearProject:
    links = node.get("externalLinks") or {}
    return LinearProject(
        id=str(node["id"]),
        name=str(node.get("name") or ""),
        url=str(node.get("url") or ""),
        archived=bool(node.get("archivedAt")),
        completed=str((node.get("status") or {}).get("type") or "") == "completed",
        link_urls=tuple(
            str(link.get("url") or "")
            for link in links.get("nodes") or []
            if isinstance(link, dict) and link.get("url")
        ),
        truncated=bool((links.get("pageInfo") or {}).get("hasNextPage")),
    )


class LinearClient:
    """Async Linear GraphQL client. One instance per process.

    Args:
        api_key: A Linear personal API key. Kept only in the HTTP client's
            headers; never logged.
        endpoint: The GraphQL endpoint (tests point it anywhere; with a mock
            transport nothing leaves the process).
        timeout_seconds: Per-request timeout (design section 7: 20 seconds).
        transport: An ``httpx`` transport, for tests (``httpx.MockTransport``).
    """

    def __init__(
        self,
        api_key: str,
        *,
        endpoint: str = LINEAR_GRAPHQL_URL,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._http = httpx.AsyncClient(
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def __repr__(self) -> str:  # never show the headers
        return f"LinearClient(endpoint={self._endpoint!r})"

    async def aclose(self) -> None:
        await self._http.aclose()

    # -- the one place a request is made -------------------------------------

    async def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run one GraphQL request and return its ``data``.

        Raises:
            LinearAuthError: the key was refused.
            LinearRateLimited: the rate limit was reached.
            LinearError: anything else — no answer, an HTTP error, or an
                ``errors`` array (even beside data, with HTTP 200).
        """
        try:
            response = await self._http.post(
                self._endpoint, json={"query": query, "variables": variables or {}}
            )
        except httpx.TimeoutException as exc:
            raise LinearError(f"Linear did not answer in time ({type(exc).__name__})") from None
        except httpx.HTTPError as exc:
            raise LinearError(f"Linear could not be reached ({type(exc).__name__})") from None

        try:
            body = response.json()
        except ValueError:
            body = None
        errors = body.get("errors") if isinstance(body, dict) else None
        codes: set[str] = set()
        types: set[str] = set()
        messages: list[str] = []
        not_found = False
        for error in errors or []:
            if not isinstance(error, dict):
                continue
            extensions = error.get("extensions") or {}
            extensions = extensions if isinstance(extensions, dict) else {}
            if extensions.get("code"):
                codes.add(str(extensions["code"]).upper())
            if extensions.get("type"):
                types.add(str(extensions["type"]).lower())
            if error.get("message"):
                messages.append(_safe_text(error["message"], 200))
                not_found |= str(error["message"]).lower().startswith("entity not found")
        detail = "; ".join(messages) or "no detail"

        if _RATE_LIMITED in codes or response.status_code == 429:
            raise LinearRateLimited(
                f"Linear's rate limit was reached (HTTP {response.status_code})",
                reset_at=_reset_at(response.headers),
            )
        if response.status_code in (401, 403) or codes & _AUTH_CODES:
            raise LinearAuthError(
                f"Linear refused the API key (HTTP {response.status_code}): {detail}"
            )
        if errors:
            permanent = bool(codes & _REFUSED_CODES or types & _REFUSED_TYPES or not_found)
            refused = LinearRefused if permanent and response.status_code < 500 else LinearError
            raise refused(
                f"Linear answered with errors (HTTP {response.status_code}, "
                f"codes {sorted(codes) or 'none'}): {detail}"
            )
        if response.status_code != 200 or not isinstance(body, dict):
            raise LinearError(f"Linear answered HTTP {response.status_code}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise LinearError("Linear's answer had no data")
        return data

    async def _paginate(
        self, query: str, variables: dict[str, Any], path: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        """Every node of a connection, following ``pageInfo`` to the end."""
        nodes: list[dict[str, Any]] = []
        after: str | None = None
        for _ in range(_MAX_PAGES):
            data: Any = await self.execute(query, {**variables, "after": after})
            for key in path:
                data = (data or {}).get(key)
            if not isinstance(data, dict):
                raise LinearError(f"Linear's answer had no {'.'.join(path)}")
            nodes.extend(node for node in data.get("nodes") or [] if isinstance(node, dict))
            page = data.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                return nodes
            after = page.get("endCursor")
            if not after:
                raise LinearError("Linear said there was another page but gave no cursor")
        raise LinearError(f"more than {_MAX_PAGES} pages of {'.'.join(path)}; stopped")

    # -- reads ---------------------------------------------------------------

    async def find_team(self, text: str) -> LinearTeam | None:
        """The team whose key is ``text`` (any case) or, failing that, whose
        name is exactly ``text``."""
        data = await self.execute(TEAMS_QUERY, {"text": text})
        teams = [
            LinearTeam(id=str(n["id"]), key=str(n.get("key") or ""), name=str(n.get("name") or ""))
            for n in (data.get("teams") or {}).get("nodes") or []
            if isinstance(n, dict) and n.get("id")
        ]
        for team in teams:
            if team.key.casefold() == text.casefold():
                return team
        for team in teams:
            if team.name == text:
                return team
        return None

    async def workflow_states(self, team_id: str) -> list[LinearState]:
        nodes = await self._paginate(STATES_QUERY, {"teamId": team_id}, ("workflowStates",))
        return [
            LinearState(id=str(n["id"]), name=str(n["name"]), type=str(n.get("type") or ""))
            for n in nodes
        ]

    async def issues_in_state(self, team_id: str, state_id: str) -> list[LinearIssue]:
        nodes = await self._paginate(
            ISSUES_IN_STATE_QUERY, {"teamId": team_id, "stateId": state_id}, ("issues",)
        )
        return [_parse_issue(node) for node in nodes]

    async def issues_with_label(self, team_id: str, label_id: str) -> list[LinearIssue]:
        """Every issue of the team carrying the label, in every state.

        Raises:
            LinearError: also when an issue has more labels or links than one
                page holds, so the mission is skipped rather than guessed.
        """
        nodes = await self._paginate(
            ISSUES_WITH_LABEL_QUERY, {"teamId": team_id, "labelId": label_id}, ("issues",)
        )
        issues = [_parse_issue(node) for node in nodes]
        if any(issue.truncated for issue in issues):
            raise LinearError(
                f"an issue has more than {_NESTED_PAGE} labels or links, so the mission "
                "cannot be read whole"
            )
        return issues

    async def issues_by_id(self, issue_ids: list[str]) -> list[LinearIssue]:
        if not issue_ids:
            return []
        nodes = await self._paginate(ISSUES_BY_ID_QUERY, {"ids": issue_ids}, ("issues",))
        return [_parse_issue(node) for node in nodes]

    async def issues_by_number(self, team_id: str, numbers: list[int]) -> list[LinearIssue]:
        """The team's issues with these numbers (``ENG-12`` is number 12)."""
        if not numbers:
            return []
        nodes = await self._paginate(
            ISSUES_BY_NUMBER_QUERY,
            {"teamId": team_id, "numbers": sorted(set(numbers))},
            ("issues",),
        )
        return [_parse_issue(node) for node in nodes]

    async def comments_containing(self, issue_id: str, text: str) -> list[LinearComment]:
        """The issue's comments whose body contains ``text`` (any case)."""
        nodes = await self._paginate(
            DOOR_COMMENTS_QUERY, {"issueId": issue_id, "text": text}, ("issue", "comments")
        )
        return [LinearComment(id=str(n["id"]), body=str(n.get("body") or "")) for n in nodes]

    async def replies_under(self, parent_ids: list[str]) -> list[LinearReply]:
        """Every reply under these comments, oldest first."""
        if not parent_ids:
            return []
        nodes = await self._paginate(
            REPLIES_QUERY, {"parentIds": sorted(set(parent_ids))}, ("comments",)
        )
        replies = []
        for n in nodes:
            user = n.get("user") or {}
            replies.append(
                LinearReply(
                    id=str(n["id"]),
                    body=str(n.get("body") or ""),
                    parent_id=str(n.get("parentId") or ""),
                    user_id=str(user["id"]) if user.get("id") else None,
                )
            )
        return replies

    async def projects(self, team_id: str) -> list[LinearProject]:
        """Every project of the team, archived and completed ones included."""
        nodes = await self._paginate(PROJECTS_QUERY, {"teamId": team_id}, ("projects",))
        return [_parse_project(node) for node in nodes]

    async def project_open_issues(self, project_id: str) -> list[tuple[str, str]]:
        """``(identifier, title)`` of the project's issues not Done, Canceled or a duplicate."""
        nodes = await self._paginate(
            PROJECT_OPEN_ISSUES_QUERY, {"projectId": project_id}, ("issues",)
        )
        return [(str(n.get("identifier") or ""), str(n.get("title") or "")) for n in nodes]

    async def project_updates(self, project_id: str) -> list[LinearComment]:
        """The project's updates (id and body)."""
        nodes = await self._paginate(
            PROJECT_UPDATES_QUERY, {"projectId": project_id}, ("project", "projectUpdates")
        )
        return [LinearComment(id=str(n["id"]), body=str(n.get("body") or "")) for n in nodes]

    # -- writes --------------------------------------------------------------

    async def create_project(
        self, *, project_id: str, name: str, team_id: str, description: str
    ) -> None:
        """Create a project with a caller-chosen id (UUID v4)."""
        data = await self.execute(
            PROJECT_CREATE_MUTATION,
            {
                "input": {
                    "id": project_id,
                    "name": name,
                    "teamIds": [team_id],
                    "description": description,
                }
            },
        )
        if not (data.get("projectCreate") or {}).get("success"):
            raise LinearError("Linear did not confirm the project")

    async def create_project_link(
        self, *, link_id: str, project_id: str, url: str, label: str
    ) -> None:
        """Add an external link to a project, with a caller-chosen id (UUID v4)."""
        data = await self.execute(
            LINK_CREATE_MUTATION,
            {"input": {"id": link_id, "projectId": project_id, "url": url, "label": label}},
        )
        if not (data.get("entityExternalLinkCreate") or {}).get("success"):
            raise LinearError("Linear did not confirm the project's link")

    async def create_project_update(
        self, project_id: str, body: str, *, health: str | None = None
    ) -> str:
        """Post a project update (Markdown) and return its id. ``health`` is
        ``onTrack``, ``atRisk`` or ``offTrack``; ``None`` leaves it out."""
        update_input: dict[str, Any] = {"projectId": project_id, "body": body}
        if health is not None:
            update_input["health"] = health
        data = await self.execute(PROJECT_UPDATE_CREATE_MUTATION, {"input": update_input})
        result = data.get("projectUpdateCreate") or {}
        update = result.get("projectUpdate") or {}
        if not result.get("success") or not update.get("id"):
            raise LinearError("Linear did not confirm the project update")
        return str(update["id"])

    async def create_comment(
        self, issue_id: str, body: str, *, parent_id: str | None = None
    ) -> str:
        """Post a comment (Markdown) and return its id.

        ``parent_id`` makes it a reply under another comment (stage 4).
        """
        comment_input: dict[str, Any] = {"issueId": issue_id, "body": body}
        if parent_id:
            comment_input["parentId"] = parent_id
        data = await self.execute(COMMENT_CREATE_MUTATION, {"input": comment_input})
        result = data.get("commentCreate") or {}
        comment = result.get("comment") or {}
        if not result.get("success") or not comment.get("id"):
            raise LinearError("Linear did not confirm the comment")
        return str(comment["id"])

    async def move_issue(self, issue_id: str, state_id: str) -> None:
        data = await self.execute(ISSUE_MOVE_MUTATION, {"id": issue_id, "stateId": state_id})
        if not (data.get("issueUpdate") or {}).get("success"):
            raise LinearError("Linear did not confirm the status change")


__all__ = [
    "LINEAR_GRAPHQL_URL",
    "LinearAuthError",
    "LinearClient",
    "LinearComment",
    "LinearError",
    "LinearIssue",
    "LinearIssueRef",
    "LinearLabel",
    "LinearProject",
    "LinearRateLimited",
    "LinearRefused",
    "LinearRelation",
    "LinearReply",
    "LinearState",
    "LinearTeam",
]
