"""The Linear door: Linear → factory (design sections 1 and 7, stage 3), and
factory → Linear (section 2, stage 4, in :mod:`.report`).

Every poll (30 seconds by default):

1. Finish any send the record holds unfinished: a ``pending`` send is
   published again with its frozen bytes; a ``published`` one gets its "sent"
   comment; a ``commented`` one is moved to In Progress.
2. Read the team's Todo issues. An issue with no mission label is one feature
   sentence. Issues with a mission label are grouped by the label's **id**;
   for each label the door reads every issue in the team carrying it, in every
   state, and sends the mission once every member (not Done, Canceled or a
   duplicate) is in Todo.
3. Write the edits-after-sending comment, once per attempt.

Between 1 and 2, stage 4 reports the factory's progress, cards and outcomes
back to the issues and reads the answers to cards (:class:`.report.Reporter`);
an attempt that Forge's record shows has ended is brought to its final status
and its issues are released there, so they can be sent again in the same
poll.

A send is written ``pending`` with its exact bytes before it is published,
and in the same transaction its issues are reserved: an issue is in at most
one open attempt, and a reserved issue is left out of every other send. Only
JetStream's acknowledgement moves a send on, and nothing is written to Linear
until then. Whether an attempt has ended (which releases its reservations) is
asked of one object, :class:`.report.AttemptRecord`, answered from Forge's own
record (:class:`.report.ForgeAttempts`).

A new or lost record is rebuilt before anything is sent, only from Forge's
record (:meth:`.report.AttemptRecord.recorded_attempts`) and the requests still
waiting in the PIPELINE stream (:class:`NatsIntakeQueue`, which never
consumes). If either cannot be read, nothing is sent that poll. The issues of
the latest attempts that had already ended are brought to their final state
once (design section 1, "Each issue is in at most one open attempt").

Log hygiene: no log line carries an issue's title or description, or the key.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from jarvis.infrastructure.linear.client import (
    LinearAuthError,
    LinearClient,
    LinearError,
    LinearIssue,
    LinearRateLimited,
    LinearTeam,
)
from jarvis.infrastructure.linear.mapping import (
    SENT_WORDS,
    MissionFeature,
    blockers_of,
    check_mission,
    choose_repo,
    comment,
    content_hash,
    correlation_id,
    feature_key,
    identifier_order,
    is_done,
    is_finished,
    mission_command,
    mission_labels,
    mission_prefix,
    mission_text,
    no_sign_in,
    planning_payload,
    sent_comment,
    sent_ids_in,
    sentence_of,
    single_prefix,
)
from jarvis.infrastructure.linear.progress import BACKLOG, finals
from jarvis.infrastructure.linear.report import (
    AnswerPublisher,
    AssumeAttemptsOpen,
    AttemptRecord,
    AttemptRecordUnavailable,
    BusFeed,
    RecordedAttempt,
    Reporter,
)
from jarvis.infrastructure.linear.store import (
    DoorStore,
    IssueAlreadyReserved,
    Recovery,
    Send,
    SendIssue,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig

logger = structlog.get_logger(__name__)

#: Back-off ceiling after repeated failures, and the bad-key retry (section 7).
MAX_BACKOFF_SECONDS = 300.0
BAD_KEY_RETRY_SECONDS = 300.0
#: The longest the door waits for a rate-limit window (Linear's is an hour).
MAX_RATE_LIMIT_WAIT_SECONDS = 3600.0
#: A whole poll may make several 20-second requests; this bounds the lot.
POLL_TIMEOUT_SECONDS = 120.0
#: How long after sending an issue is watched for edits.
EDIT_WATCH_DAYS = 30
#: Issue ids per edit-check read.
_EDIT_CHUNK = 50
#: After a card arrives, how long the door waits for the rest of a burst.
WAKE_SETTLE_SECONDS = 2.0


class BusUnavailable(Exception):
    """A publish was not acknowledged; the send stays ``pending``."""


class RebuildUnavailable(Exception):
    """A new or lost record could not be rebuilt; nothing is sent this poll."""


@dataclass(frozen=True)
class WaitingRequest:
    """A ``pipeline.planning-queued.lin-…`` message still in the PIPELINE stream."""

    correlation_id: str
    payload: dict[str, Any]


class IntakeQueue(Protocol):
    """Reads the factory's intake queue without consuming from it."""

    async def waiting_requests(self) -> list[WaitingRequest]: ...


class NatsIntakeQueue:
    """The PIPELINE stream, read with stream info and message get only.

    Never creates a consumer: PIPELINE is a work queue, and a consumer would
    take Forge's messages away (design section 1, R9).
    """

    STREAM = "PIPELINE"
    SUBJECT_PREFIX = "pipeline.planning-queued."

    def __init__(self, nats_client: Any, *, timeout_seconds: float = 10.0) -> None:
        self._nats_client = nats_client
        self._timeout = timeout_seconds

    async def waiting_requests(self) -> list[WaitingRequest]:
        import json

        js = self._nats_client.js
        info = await asyncio.wait_for(
            js.stream_info(self.STREAM, subjects_filter=f"{self.SUBJECT_PREFIX}>"),
            timeout=self._timeout,
        )
        subjects = (info.state.subjects or {}) if info.state else {}
        found: list[WaitingRequest] = []
        for subject in sorted(subjects):
            cid = subject[len(self.SUBJECT_PREFIX) :]
            if not cid.startswith("lin-"):
                continue
            message = await asyncio.wait_for(
                js.get_last_msg(self.STREAM, subject), timeout=self._timeout
            )
            envelope = json.loads(message.data or b"{}")
            payload = envelope.get("payload") if isinstance(envelope, dict) else None
            found.append(WaitingRequest(cid, payload if isinstance(payload, dict) else {}))
        return found


class FrozenPublisher(Protocol):
    """Publishes already-encoded bytes; returns only after JetStream's ack."""

    async def publish_bytes(self, *, subject: str, data: bytes) -> None: ...


@dataclass(frozen=True)
class DoorSettings:
    team: str
    owner_identity: str
    ready_state: str = "Todo"
    started_state: str = "In Progress"
    done_state: str = "Done"
    backlog_state: str = "Backlog"
    default_repo: str | None = None
    poll_seconds: float = 30.0
    #: Linear user id → the identity its answers are sent as (JARVIS_LINEAR_APPROVERS).
    approvers: dict[str, str] = field(default_factory=dict)


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:300]}"


class LinearDoor:
    """One door: a Linear client, a bus publisher and the record."""

    def __init__(
        self,
        *,
        client: LinearClient,
        publisher: FrozenPublisher,
        store: DoorStore,
        settings: DoorSettings,
        attempts: AttemptRecord | None = None,
        intake: IntakeQueue | None = None,
        feed: BusFeed | None = None,
        answers: AnswerPublisher | None = None,
        wake: asyncio.Event | None = None,
    ) -> None:
        self._client = client
        self._publisher = publisher
        self._store = store
        self._settings = settings
        self._attempts: AttemptRecord = attempts or AssumeAttemptsOpen()
        self._intake = intake
        self._reporter = Reporter(
            client=client,
            store=store,
            attempts=self._attempts,
            feed=feed,
            answers=answers,
            approvers=dict(settings.approvers),
        )
        # Set by the bus feed when a card or notification arrives, so it
        # reaches Linear without waiting for the next poll.
        self._wake = wake or asyncio.Event()
        self._team: LinearTeam | None = None
        self._state_ids: dict[str, str] = {}
        self._rebuilt = False
        # Loop state, for the back-off rules of section 7.
        self._failures = 0
        self._bad_key_reported = False

    # ------------------------------------------------------------------
    # Set-up
    # ------------------------------------------------------------------

    async def _ensure_team(self) -> LinearTeam:
        """Resolve the team (by key, else exact name) and its states, once."""
        if self._team is not None:
            return self._team
        team = await self._client.find_team(self._settings.team)
        if team is None:
            raise LinearError(
                f"Linear has no team with the key or name {self._settings.team!r} "
                "that this key can see"
            )
        states = await self._client.workflow_states(team.id)
        by_name = {state.name.casefold(): state.id for state in states}
        wanted = {
            "ready": self._settings.ready_state,
            "started": self._settings.started_state,
            "done": self._settings.done_state,
            "backlog": self._settings.backlog_state,
        }
        ids: dict[str, str] = {}
        for role, name in wanted.items():
            state_id = by_name.get(name.casefold())
            if state_id is None:
                if role in ("ready", "started"):
                    raise LinearError(f"team {team.key} has no status called {name!r}")
                logger.warning("linear_door_status_missing", team=team.key, role=role, name=name)
                continue
            ids[role] = state_id
        self._state_ids = ids
        self._team = team
        logger.info("linear_door_team_resolved", team=team.key)
        return team

    async def _rebuild(self, team: LinearTeam) -> None:
        """A new or lost record: rebuild open attempts and reservations.

        Only from Forge's record and the PIPELINE stream, never from Linear's
        statuses, labels or comments (design section 1, R9). If either read
        fails, raise :class:`RebuildUnavailable`, so nothing is sent this poll.
        Attempt numbers then continue after the highest found in either place.
        """
        if self._rebuilt or not self._store.is_empty():
            self._rebuilt = True
            return
        # The intake queue first, Forge's record second (design review round
        # 5): a request Forge takes between the two reads is then found in one
        # or the other, never in neither. Nothing is published until both
        # reads have succeeded.
        if self._intake is None:
            raise RebuildUnavailable("the intake queue cannot be read")
        try:
            waiting = await self._intake.waiting_requests()
        except Exception as exc:
            raise RebuildUnavailable(
                f"the intake queue could not be read: {_safe_error(exc)}"
            ) from None
        try:
            recorded = self._attempts.recorded_attempts()
        except AttemptRecordUnavailable as exc:
            raise RebuildUnavailable(f"Forge's record could not be read: {exc}") from None

        open_attempts: dict[str, list[str]] = {}  # correlation id -> identifiers
        for attempt in recorded:
            if attempt.open:
                open_attempts[attempt.correlation_id] = self._identifiers(
                    team, attempt.correlation_id, list(attempt.mission_keys)
                )
        for request in waiting:
            command = request.payload.get("queue_command") or {}
            keys = [str(f.get("key") or "") for f in command.get("features") or []]
            open_attempts[request.correlation_id] = self._identifiers(
                team, request.correlation_id, keys
            )
        ended = self._latest_ended(team, recorded, set(open_attempts))

        numbers = {
            int(identifier.rpartition("-")[2])
            for identifiers in [*open_attempts.values(), *(i for _, _, i in ended)]
            for identifier in identifiers
        }
        by_identifier = {
            issue.identifier: issue.id
            for issue in await self._client.issues_by_number(team.id, sorted(numbers))
        }
        holds = [
            (by_identifier[identifier], cid, identifier)
            for cid, identifiers in open_attempts.items()
            for identifier in identifiers
            if identifier in by_identifier
        ]
        held = {issue_id for issue_id, _, _ in holds}
        recoveries = []
        for cid, outcome, identifiers in ended:
            members: list[tuple[str, str | None]] = [
                (by_identifier[i], i)
                for i in identifiers
                if i in by_identifier and by_identifier[i] not in held
            ]
            for issue_id, final in finals(outcome, members).items():
                recoveries.append(
                    Recovery(
                        cid,
                        issue_id,
                        dict(members).get(issue_id),
                        final.target,
                        f"Recovered after a restart: {final.text}",
                    )
                )
        # Everything is written at once, after every read has succeeded, so a
        # failure part-way leaves the record empty and the next poll rebuilds.
        self._store.apply_rebuild(
            known=[a.correlation_id for a in recorded] + [r.correlation_id for r in waiting],
            reservations=holds,
            recoveries=recoveries,
        )
        reserved = len(holds)
        self._rebuilt = True
        logger.info(
            "linear_door_record_rebuilt",
            attempts_found=len(recorded) + len(waiting),
            open_attempts=len(open_attempts),
            issues_reserved=reserved,
        )

    @staticmethod
    def _identifiers(team: LinearTeam, cid: str, mission_keys: list[str]) -> list[str]:
        """The team's issue identifiers an attempt covers."""
        if cid.startswith("lin-m-"):
            found = []
            for key in mission_keys:
                number = key[len(team.key) :] if key.upper().startswith(team.key.upper()) else ""
                if number.isdigit():
                    found.append(f"{team.key}-{int(number)}")
            return found
        identifier = cid[len("lin-") :].rpartition("-")[0]
        team_key, _, number = identifier.rpartition("-")
        return [identifier] if team_key == team.key and number.isdigit() else []

    def _latest_ended(
        self, team: LinearTeam, recorded: list[RecordedAttempt], open_cids: set[str]
    ) -> list[tuple[str, Any, list[str]]]:
        """``(correlation id, outcome, identifiers)`` of the latest ended attempt
        of each issue or mission that has no open attempt.

        Older ended attempts are history: only the latest says where the issue
        should be now. Raises :class:`RebuildUnavailable` if an outcome cannot
        be read (nothing is written).
        """

        def split(cid: str) -> tuple[str, int]:
            prefix, _, number = cid.rpartition("-")
            return f"{prefix}-", int(number) if number.isdigit() else 0

        open_prefixes = {split(cid)[0] for cid in open_cids}
        latest: dict[str, tuple[int, RecordedAttempt]] = {}
        for attempt in recorded:
            prefix, number = split(attempt.correlation_id)
            if prefix in open_prefixes:
                continue
            if prefix not in latest or number > latest[prefix][0]:
                latest[prefix] = (number, attempt)
        found = []
        for _, attempt in sorted(latest.values(), key=lambda pair: pair[1].correlation_id):
            if attempt.open:
                continue
            try:
                outcome = self._attempts.outcome(attempt.correlation_id)
            except AttemptRecordUnavailable as exc:
                raise RebuildUnavailable(f"Forge's record could not be read: {exc}") from None
            if not outcome.ended:
                continue
            identifiers = self._identifiers(
                team, attempt.correlation_id, list(attempt.mission_keys)
            )
            found.append((attempt.correlation_id, outcome, identifiers))
        return found

    async def _finish_recoveries(self) -> None:
        """Bring the issues of attempts that had ended before a rebuild to their
        final state, once: a comment and the move, only when the issue is not
        already where that attempt left it (Done unless finished; Backlog only
        while still In Progress), and never for an issue an open attempt holds."""
        pending = self._store.pending_recoveries()
        if not pending:
            return
        from jarvis.infrastructure.linear.report import _move_to

        reserved = self._store.reservations()
        current = {
            issue.id: issue
            for issue in await self._client.issues_by_id(sorted({r.issue_id for r in pending}))
        }
        for recovery in pending:
            issue = current.get(recovery.issue_id)
            state_id = (
                None
                if issue is None or recovery.issue_id in reserved
                else _move_to(recovery.target, issue, self._state_ids)
            )
            if state_id is not None:
                await self._client.create_comment(recovery.issue_id, comment(recovery.text))
                await self._client.move_issue(recovery.issue_id, state_id)
                logger.info(
                    "linear_door_recovered_issue",
                    correlation_id=recovery.correlation_id,
                    issue=recovery.identifier,
                    target=recovery.target,
                )
            self._store.finish_recovery(recovery.correlation_id, recovery.issue_id)

    # ------------------------------------------------------------------
    # One poll
    # ------------------------------------------------------------------

    async def poll_once(self) -> None:
        """One pass of the door. Raises on a Linear or bus failure."""
        self._wake.clear()
        team = await self._ensure_team()
        await self._rebuild(team)
        await self._finish_recoveries()
        for send in self._store.unfinished_sends():
            await self._advance(send, resumed=True)
        # Factory → Linear: progress, cards, answers; an ended attempt frees
        # its issues here, before the ready list is read.
        await self._reporter.report(
            self._state_ids, {send.correlation_id for send in self._store.unfinished_sends()}
        )

        ready = await self._client.issues_in_state(team.id, self._state_ids["ready"])
        reserved = self._store.reservations()
        unfinished = self._store.issue_ids_in_unfinished_sends()
        missions: dict[str, tuple[str, list[LinearIssue]]] = {}
        for issue in sorted(ready, key=lambda i: identifier_order(i.identifier)):
            labels = mission_labels(issue)
            if issue.id in unfinished:
                continue  # its send is still being delivered
            if issue.id in reserved:
                # In an open attempt: left out of every other send, whatever
                # its labels say now (design review round 2, R9).
                await self._notice(issue, _already_running(reserved[issue.id]))
            elif len(labels) > 1:
                await self._notice(issue, _two_mission_labels(labels))
            elif not labels:
                await self._consider_single(issue)
            else:
                label = labels[0]
                missions.setdefault(label.label_id, (label.title, []))[1].append(issue)

        for label_id, (title, todo) in missions.items():
            await self._consider_mission(team, label_id, title, todo)

        await self._check_edits()

    # ------------------------------------------------------------------
    # A single issue
    # ------------------------------------------------------------------

    async def _consider_single(self, issue: LinearIssue) -> None:
        choice = choose_repo(issue, self._settings.default_repo)
        if choice.problem:
            await self._notice(issue, choice.problem)
            return
        prefix = single_prefix(issue.identifier)
        attempt = self._store.max_attempt(prefix) + 1
        cid = correlation_id(prefix, attempt)
        payload = planning_payload(
            request_text=sentence_of(issue),
            target_repo=choice.repo,
            owner_identity=self._settings.owner_identity,
            cid=cid,
        )
        await self._record_and_send(
            correlation_id=cid,
            kind="single",
            attempt=attempt,
            payload=payload,
            issues=[SendIssue(issue.id, issue.identifier, None, content_hash(issue))],
        )

    # ------------------------------------------------------------------
    # A mission
    # ------------------------------------------------------------------

    async def _consider_mission(
        self, team: LinearTeam, label_id: str, title: str, todo: list[LinearIssue]
    ) -> None:
        prefix = mission_prefix(label_id)
        log = logger.bind(mission=prefix.rstrip("-"))
        reserved = self._store.reservations()

        # An open attempt of this mission: issues newly given the label and
        # moved to Todo wait for the next attempt (design review R7).
        running = sorted({cid for cid in reserved.values() if cid.startswith(prefix)})
        if running:
            for issue in todo:
                await self._notice(issue, _mission_running(title, running[-1]))
            return

        # The mission's full membership, in every state (design review R3).
        try:
            everyone = await self._client.issues_with_label(team.id, label_id)
        except (LinearAuthError, LinearRateLimited):
            raise
        except LinearError as exc:
            log.warning("linear_door_mission_read_failed", error=_safe_error(exc))
            return
        # Members: not Done, Canceled or a duplicate, and not in another open
        # attempt (R9 — a reserved issue is left out of every other send).
        members = sorted(
            (i for i in everyone if not is_finished(i.state.type) and i.id not in reserved),
            key=lambda i: identifier_order(i.identifier),
        )
        if not members:
            return
        doubled = [m for m in members if len(mission_labels(m)) > 1]
        if doubled:
            # An issue with two mission labels is not sent, nor is its mission.
            for member in doubled:
                await self._notice(member, _two_mission_labels(mission_labels(member)))
            log.info("linear_door_mission_held", reason="an issue has two mission labels")
            return
        waiting = [m.identifier for m in members if m.state.id != self._state_ids["ready"]]
        if waiting:
            log.debug("linear_door_mission_waiting", not_in_todo=waiting)
            return

        by_id = {m.id: m for m in members}
        problems: dict[str, list[str]] = {}
        repos: dict[str, str] = {}
        for member in members:
            choice = choose_repo(member, self._settings.default_repo)
            if choice.problem:
                problems.setdefault(member.id, []).append(choice.problem)
            elif choice.repo:
                repos[member.id] = choice.repo
            for blocker in blockers_of(member):
                if blocker.id in by_id or is_done(blocker.state_type):
                    continue
                problems.setdefault(member.id, []).append(
                    f"The mission “{title}” was not sent: this issue is blocked by "
                    f"{blocker.identifier}, which is not in the mission and is not done. "
                    f"Finish {blocker.identifier}, remove the link, or add it to the mission."
                )
        if problems:
            for member in members:
                if member.id in problems:
                    await self._notice(member, "\n\n".join(problems[member.id]))
            return
        if len(set(repos.values())) > 1:
            listed = ", ".join(f"{m.identifier} → `{repos[m.id]}`" for m in members)
            for member in members:
                await self._notice(
                    member,
                    f"The mission “{title}” was not sent because its issues name different "
                    f"repositories ({listed}). Give them all the same repo label.",
                )
            return

        order = {m.id: index for index, m in enumerate(members)}
        features = []
        for member in members:
            need_ids = {b.id for b in blockers_of(member) if b.id in by_id}
            features.append(
                MissionFeature(
                    issue=member,
                    key=feature_key(member.identifier),
                    needs=tuple(
                        feature_key(by_id[i].identifier)
                        for i in sorted(need_ids, key=lambda i: order[i])
                    ),
                    no_sign_in=no_sign_in(member),
                    sentence=sentence_of(member),
                )
            )
        attempt = self._store.max_attempt(prefix) + 1
        cid = correlation_id(prefix, attempt)
        command = mission_command(title, features)
        refusal = check_mission(command, cid)
        if refusal is not None:
            for member in members:
                await self._notice(member, f"The mission “{title}” was not sent. {refusal}")
            return
        payload = planning_payload(
            request_text=mission_text(title, features),
            target_repo=next(iter(repos.values())),
            owner_identity=self._settings.owner_identity,
            cid=cid,
            queue_command=command,
        )
        await self._record_and_send(
            correlation_id=cid,
            kind="mission",
            attempt=attempt,
            payload=payload,
            issues=[
                SendIssue(f.issue.id, f.issue.identifier, f.key, content_hash(f.issue))
                for f in features
            ],
            mission_label_id=label_id,
            mission_title=title,
        )

    # ------------------------------------------------------------------
    # Record → publish → comment → move
    # ------------------------------------------------------------------

    async def _record_and_send(
        self,
        *,
        correlation_id: str,
        kind: str,
        attempt: int,
        payload: Any,
        issues: list[SendIssue],
        mission_label_id: str | None = None,
        mission_title: str | None = None,
    ) -> None:
        try:
            send = self._store.record_send(
                correlation_id=correlation_id,
                kind=kind,
                attempt=attempt,
                subject=_subject(correlation_id),
                payload=_encode(payload, correlation_id),
                issues=issues,
                mission_label_id=mission_label_id,
                mission_title=mission_title,
            )
        except IssueAlreadyReserved as exc:
            logger.info(
                "linear_door_issue_reserved", correlation_id=correlation_id, detail=str(exc)
            )
            return
        await self._advance(send, resumed=False)

    async def _advance(self, send: Send, *, resumed: bool) -> None:
        cid = send.correlation_id
        log = logger.bind(correlation_id=cid, kind=send.kind, attempt=send.attempt)
        if send.status == "pending":
            try:
                await self._publisher.publish_bytes(subject=send.subject, data=send.payload)
            except Exception as exc:
                log.warning("linear_door_publish_failed", error=_safe_error(exc))
                raise BusUnavailable(f"the bus did not acknowledge {cid}") from None
            self._store.set_status(cid, "published")
            log.info(
                "linear_door_published",
                subject=send.subject,
                issues=[i.identifier for i in send.issues],
                resumed=resumed,
            )
            send = self._reload(cid)

        if send.status == "published":
            for issue in send.issues:
                if issue.commented:
                    continue
                if not (resumed and await self._has_sent_comment(issue.issue_id, cid)):
                    await self._client.create_comment(issue.issue_id, sent_comment(cid))
                self._store.mark_issue(cid, issue.issue_id, "commented")
            self._store.set_status(cid, "commented")
            send = self._reload(cid)

        if send.status == "commented":
            for issue in send.issues:
                if issue.moved:
                    continue
                await self._client.move_issue(issue.issue_id, self._state_ids["started"])
                self._store.mark_issue(cid, issue.issue_id, "moved")
            self._store.set_status(cid, "moved")
            self._store.clear_notices([i.issue_id for i in send.issues])
            log.info("linear_door_sent", issues=[i.identifier for i in send.issues])

    def _reload(self, cid: str) -> Send:
        send = self._store.get_send(cid)
        assert send is not None
        return send

    async def _has_sent_comment(self, issue_id: str, cid: str) -> bool:
        found = await self._client.comments_containing(issue_id, SENT_WORDS)
        return any(cid in sent_ids_in(c.body) for c in found)

    # ------------------------------------------------------------------
    # Comments that are not about a send
    # ------------------------------------------------------------------

    async def _notice(self, issue: LinearIssue, text: str) -> None:
        """Comment ``text`` on ``issue`` once; never again for the same text."""
        body = comment(text)
        if self._store.notice_posted(issue.id, body):
            return
        await self._client.create_comment(issue.id, body)
        self._store.record_notice(issue.id, body)
        logger.info("linear_door_not_sent_comment", issue=issue.identifier)

    async def _check_edits(self) -> None:
        since = (datetime.now(UTC) - timedelta(days=EDIT_WATCH_DAYS)).isoformat()
        watched = self._store.sends_to_watch_for_edits(since)
        if not watched:
            return
        ids = sorted({si.issue_id for _, si in watched})
        current: dict[str, LinearIssue] = {}
        for start in range(0, len(ids), _EDIT_CHUNK):
            for found in await self._client.issues_by_id(ids[start : start + _EDIT_CHUNK]):
                current[found.id] = found
        for send, sent in watched:
            issue = current.get(sent.issue_id)
            if issue is None or content_hash(issue) == sent.content_hash:
                continue
            sent_at = datetime.fromisoformat(send.created_at)
            if issue.updated_at <= sent_at:
                continue
            stamp = sent_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
            await self._client.create_comment(
                issue.id,
                comment(
                    "This issue changed after it was sent; the factory is working from the "
                    f"version sent at {stamp} (`{send.correlation_id}`)."
                ),
            )
            self._store.mark_issue(send.correlation_id, sent.issue_id, "edit_noted")

    # ------------------------------------------------------------------
    # The operator's release (design section 2, "Refusals with nothing filed")
    # ------------------------------------------------------------------

    async def release(self, identifier: str) -> tuple[str, list[str]]:
        """End the open attempt holding ``identifier``, by an operator's word.

        For a request the factory refused without filing anything: comments on
        each of the attempt's issues, moves them to Backlog, then ends the
        attempt in the record, which frees its reservations and stops any
        further delivery. Linear is written first, so a failure can be retried
        by running the command again.

        Returns:
            The correlation id and the identifiers of the issues released.

        Raises:
            LookupError: no open attempt holds that issue.
            LinearError: Linear could not be written (nothing was ended).
        """
        cid = self._store.attempt_holding(identifier.strip())
        if cid is None:
            raise LookupError(f"no open attempt holds {identifier}")
        await self._ensure_team()
        backlog = self._state_ids.get(BACKLOG)
        if backlog is None:
            raise LinearError(f"the team has no status called {self._settings.backlog_state!r}")
        released: list[str] = []
        for issue_id, issue_identifier in self._store.reserved_issues(cid):
            await self._client.create_comment(
                issue_id,
                comment(
                    f"An operator released attempt `{cid}`: the factory did not file it. "
                    "This issue is back in Backlog; move it to Todo to send it again."
                ),
            )
            await self._client.move_issue(issue_id, backlog)
            released.append(issue_identifier or issue_id)
        self._store.end_attempt(cid, "released by an operator")
        logger.info("linear_door_attempt_released", correlation_id=cid, issues=released)
        return cid, released

    # ------------------------------------------------------------------
    # The loop
    # ------------------------------------------------------------------

    def next_delay(self, error: BaseException | None, *, now: float | None = None) -> float:
        """Seconds until the next poll after a poll ended with ``error`` (or none)."""
        poll = self._settings.poll_seconds
        if error is None:
            if self._failures or self._bad_key_reported:
                logger.info("linear_door_recovered", after_failures=self._failures)
            self._failures = 0
            self._bad_key_reported = False
            return poll
        if isinstance(error, LinearAuthError):
            if not self._bad_key_reported:
                logger.error(
                    "linear_door_bad_key",
                    detail="Linear refused the API key (JARVIS_LINEAR_API_KEY); the door does "
                    "nothing else and tries again every five minutes",
                )
            self._bad_key_reported = True
            return BAD_KEY_RETRY_SECONDS
        if isinstance(error, LinearRateLimited):
            moment = time.time() if now is None else now
            wait = (error.reset_at - moment) if error.reset_at else MAX_BACKOFF_SECONDS
            wait = min(max(wait, poll), MAX_RATE_LIMIT_WAIT_SECONDS)
            logger.warning("linear_door_rate_limited", wait_seconds=round(wait))
            return wait
        self._failures += 1
        wait = float(min(poll * (2 ** (self._failures - 1)), MAX_BACKOFF_SECONDS))
        logger.warning(
            "linear_door_poll_failed",
            error=_safe_error(error),
            failures=self._failures,
            next_try_seconds=round(wait),
        )
        return wait

    async def run(self, stop: asyncio.Event) -> None:
        """Poll until ``stop`` is set. Never raises for a Linear or bus failure."""
        logger.info(
            "linear_door_started",
            team=self._settings.team,
            poll_seconds=self._settings.poll_seconds,
            default_repo=self._settings.default_repo,
        )
        while not stop.is_set():
            error: BaseException | None = None
            try:
                await asyncio.wait_for(self.poll_once(), timeout=POLL_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # every failure waits and tries again
                error = exc
            delay = self.next_delay(error)
            await self._sleep(stop, delay, wake=error is None)
        logger.info("linear_door_stopped")

    async def _sleep(self, stop: asyncio.Event, delay: float, *, wake: bool) -> None:
        """Wait ``delay`` seconds, until stopped, or (after a good poll) until a
        card or notification arrives — then a moment more, so a burst is one
        poll."""
        waits = [asyncio.ensure_future(stop.wait())]
        if wake:
            waits.append(asyncio.ensure_future(self._wake.wait()))
        try:
            await asyncio.wait(waits, timeout=delay, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for waiting in waits:
                waiting.cancel()
        if wake and self._wake.is_set() and not stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=WAKE_SETTLE_SECONDS)


def _already_running(cid: str) -> str:
    return (
        f"This issue is already with the factory as `{cid}`, so it was not sent again. "
        "It can be sent again once that attempt has finished."
    )


def _mission_running(title: str, cid: str) -> str:
    return (
        f"The mission “{title}” is already running as `{cid}`; this issue will be included "
        "in the next attempt if it is still in Todo then."
    )


def _two_mission_labels(labels: list[Any]) -> str:
    names = ", ".join(f"“{label.title}”" for label in labels)
    return (
        f"This issue has more than one mission label ({names}), so neither it nor its "
        "mission was sent. Keep one."
    )


def _subject(cid: str) -> str:
    from nats_core import Topics

    return Topics.Pipeline.PLANNING_QUEUED.format(correlation_id=cid)


def _encode(payload: Any, cid: str) -> bytes:
    from jarvis.infrastructure.slack_planning_intake import planning_queued_envelope_bytes

    return planning_queued_envelope_bytes(payload, cid)


# ---------------------------------------------------------------------------
# From configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DoorConfig:
    settings: DoorSettings
    linear_auth: str
    state_path: Any
    forge_db: Any = None
    publish_timeout_seconds: float = 5.0

    def __repr__(self) -> str:  # never show the key
        return f"DoorConfig(settings={self.settings!r}, state_path={self.state_path!r})"


def door_config(config: JarvisConfig) -> DoorConfig | str:
    """The door's configuration, or the one sentence saying what is missing."""
    # Unwrapped once, into a name that is not credential-shaped (this
    # repository is public, and scanners cannot tell an expression from a
    # literal).
    linear_auth = config.resolve_linear_api_key()
    team = (config.linear_team or "").strip()
    owner = config.resolve_linear_owner_identity()
    missing = []
    if not linear_auth:
        missing.append("JARVIS_LINEAR_API_KEY (or JARVIS_LINEAR_API_KEY_FILE)")
    if not team:
        missing.append("JARVIS_LINEAR_TEAM")
    if not owner:
        missing.append("JARVIS_LINEAR_OWNER_IDENTITY (or JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID)")
    if missing:
        return (
            f"the Linear door is not configured ({', '.join(missing)} not set), "
            "so it is not running"
        )
    assert linear_auth is not None and owner is not None
    default_repo = (config.linear_default_repo or "").strip() or None
    from jarvis.infrastructure.linear.cards import parse_approvers

    try:
        approvers = parse_approvers(config.linear_approvers)
    except ValueError:
        return (
            "the Linear door is not running: JARVIS_LINEAR_APPROVERS has an entry that is "
            "not <linear user id>=<identity>"
        )
    return DoorConfig(
        settings=DoorSettings(
            team=team,
            owner_identity=owner,
            ready_state=config.linear_ready_state,
            started_state=config.linear_started_state,
            done_state=config.linear_done_state,
            backlog_state=config.linear_backlog_state,
            default_repo=default_repo,
            poll_seconds=float(config.linear_poll_seconds),
            approvers=approvers,
        ),
        linear_auth=linear_auth,
        state_path=config.linear_state_dir / "linear-door.sqlite3",
        forge_db=config.linear_forge_db,
        publish_timeout_seconds=float(config.pipeline_publish_timeout_seconds),
    )


__all__ = [
    "AssumeAttemptsOpen",
    "AttemptRecord",
    "AttemptRecordUnavailable",
    "BusUnavailable",
    "DoorConfig",
    "DoorSettings",
    "FrozenPublisher",
    "IntakeQueue",
    "LinearDoor",
    "NatsIntakeQueue",
    "RebuildUnavailable",
    "RecordedAttempt",
    "WaitingRequest",
    "door_config",
]
