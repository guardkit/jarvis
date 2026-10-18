"""The Linear door, factory → Linear (design section 2, stage 4).

Every poll, after the door has finished delivering its own sends:

1. **Progress.** For each open attempt, read Forge's record
   (:class:`ForgeAttempts`) and write the comment each issue is owed for any
   change since the door last wrote (:mod:`.progress`; what was written is in
   the door's record, so a restart repeats nothing). When the record shows the
   attempt has ended, write each issue's final comment, move it (Done, or
   Backlog — Backlog only when the issue is still In Progress, so a person who
   already moved it back to Todo keeps their retry), and only then end the
   attempt, which releases its issues.
2. **Cards from the bus.** Card messages from ``agents.approval.forge.*`` on
   the AGENTS stream (:class:`NatsBusFeed`) are matched to an open attempt by
   correlation id, mission id and the build ids Forge's record links, and
   posted on the attempt's issues (on every member for a mission) only while
   Forge's record shows that card open (Forge writes a card to its record
   before it sends it). A build gate or other card whose openness the record
   cannot show is posted to be answered in Slack only. Slack notifications
   from the JARVIS stream are copied onto the issues of an attempt Forge has
   not filed (visibility only). A card or notification for a send whose
   "sent" comment or move is not done yet is held in the door's record until
   the send is finished. Each feed's last handled time is recorded, so a
   restart resumes from there.
3. **Cards the stream no longer holds** are posted from the record: a merge
   card in full; any other card asking for its answer in Slack.
4. **Answers.** Replies under the door's open card comments are read with one
   request; ``approve``/``merge`` approve, ``reject``/``decline`` reject,
   anything else is ignored. A listed author's answer is published as the
   Slack button does; an unlisted author is told once that only the people
   listed can answer. Each answer is claimed before it is published and is
   never published again. A claim whose publish did not return (it raised, or
   the door stopped part way) is settled on a later poll: if Forge's record
   still shows the card open, the door says once under the card that it
   could not confirm the answer, and the card takes a new reply.

Every comment the door writes here ends with a short note in small italics
(``_factory note <12 hex>_``) recorded before it is sent, so a comment whose
sending was not confirmed is looked for before it is written again
(:func:`write_once`).

Nothing here decides an outcome from a reply: what happened is reported later
from Forge's record.

5. **Project updates** (design section 11.4). When a single issue's attempt is
   on main with its merge report, or a mission is MERGED, one project update
   is posted to the Linear project its repository maps to (:mod:`.updates`),
   before the attempt ends; nothing for a declined or failed merge, nor to an
   archived or completed project.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Protocol
from urllib.parse import unquote

import structlog

from jarvis.infrastructure.linear import forge_record as fr
from jarvis.infrastructure.linear.cards import (
    MERGE,
    MISSION_PLAN,
    NOT_LISTED,
    OTHER,
    PLAN,
    Card,
    answer_notes,
    card_comment,
    notification_comment,
    parse_card,
    parse_notification,
    parse_reply,
    recovered_card_comment,
)
from jarvis.infrastructure.linear.client import (
    LinearAuthError,
    LinearError,
    LinearRateLimited,
    LinearRefused,
)
from jarvis.infrastructure.linear.mapping import COMMENT_PREFIX, comment, feature_key, is_finished
from jarvis.infrastructure.linear.progress import (
    BACKLOG,
    DONE,
    Final,
    deploy_failed_words,
    finals,
    is_mission,
    key_step,
    phase_step,
)
from jarvis.infrastructure.linear.store import CardComment, DoorStore

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.infrastructure.linear.projects import ProjectMap

logger = structlog.get_logger(__name__)

#: Feeds and their marks in the door's record.
CARDS = "cards"
NOTIFICATIONS = "notifications"

#: How long a published request may wait with no Forge row before the door
#: says so once (design section 2, "Refusals with nothing filed").
UNFILED_NOTICE_AFTER = timedelta(hours=1)
UNFILED_NOTICE = (
    "The factory has not filed this request. If it was refused (see the reason above or "
    "in Slack), the operator can release it."
)
#: A card found open in the record is posted from the record only after this
#: long, so the full card from the stream, which arrives within moments, wins.
RECOVERY_GRACE = timedelta(seconds=60)

#: Polls a card is tried on before a card Linear keeps refusing is let go.
MAX_CARD_TRIES = 5

#: Said under a card when an answer's publish was not confirmed (R2).
UNCONFIRMED_ANSWER = (
    "I could not confirm your answer reached the factory; if the card is still open, "
    "reply again or answer in Slack."
)

#: Whether a card is open, by Forge's record.
_OPEN = "open"
_SETTLED = "settled"
_UNKNOWN = "unknown"  # a card the record cannot show either way: Slack only

#: The last line of every comment written once, in Linear's small italics:
#: ``_factory note <ref>_`` (searchable, and quiet for the person reading).
REF_WORD = "factory note"


def ref_for(*parts: str) -> str:
    """A short stable reference for one comment the door means to write."""
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:12]


async def write_once(
    client: Any,
    store: DoorStore,
    issue_id: str,
    body: str,
    ref: str,
    *,
    parent_id: str | None = None,
) -> str:
    """Write ``body`` on the issue once, and return the comment's id.

    The reference is recorded before the comment is sent and ends its text.
    If an earlier try was not confirmed (Linear's answer was lost, or the door
    stopped), the issue's comments are searched for the reference first, so
    the comment is never written twice (Codex review R3).
    """

    async def find(marker: str) -> str | None:
        for found in await client.comments_containing(issue_id, marker):
            return str(found.id)
        return None

    async def create(text: str) -> str:
        return str(await client.create_comment(issue_id, text, parent_id=parent_id))

    return await write_once_to(store, ref, issue_id, body, find=find, create=create)


async def write_once_to(
    store: DoorStore,
    ref: str,
    owner_id: str,
    body: str,
    *,
    find: Callable[[str], Awaitable[str | None]],
    create: Callable[[str], Awaitable[str]],
) -> str:
    """The write-once guard for anything the door writes with a reference (a
    comment on an issue, a project update on a project ``owner_id``).

    The reference is recorded before the write and ends the text; if an
    earlier try was not confirmed, ``find`` looks for the reference first.
    """
    started, written_id = store.comment_ref(ref)
    if written_id:
        return written_id
    marker = f"{REF_WORD} {ref}"
    if started:
        found = await find(marker)
        if found:
            store.finish_comment(ref, found)
            return found
    else:
        store.begin_comment(ref, owner_id)
    written_id = await create(f"{body}\n\n_{marker}_")
    store.finish_comment(ref, written_id)
    return str(written_id)


class AttemptRecordUnavailable(Exception):
    """Forge's record could not be read this poll."""


# ---------------------------------------------------------------------------
# Forge's record, as the door asks it
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordedAttempt:
    """One ``lin-`` correlation id Forge has recorded (for a rebuild).

    ``mission_keys`` are a mission's ``mission_features`` keys (the issue
    identifiers without their hyphen); empty for a single issue, whose
    identifier is inside its correlation id. ``filed_at`` is when Forge filed
    it (ISO time): of one issue's attempts, the one filed last is the latest.
    """

    correlation_id: str
    open: bool
    mission_keys: tuple[str, ...] = ()
    filed_at: str = ""


class AttemptRecord(Protocol):
    """Forge's record of the door's attempts, read-only.

    ``outcome`` is where one attempt has got to (a single issue's or a
    mission's outcome from :mod:`.forge_record`); its ``ended`` is the one
    thing that ends an attempt (design section 2, "When an attempt ends").
    ``recorded_attempts`` lists every ``lin-`` attempt Forge has recorded, for
    rebuilding a new or lost door record. ``open_cards`` lists the cards still
    waiting for these attempts. Each raises :class:`AttemptRecordUnavailable`
    when the record cannot be read; the door then changes nothing that depends
    on it that poll.
    """

    def outcome(self, correlation_id: str) -> Any: ...

    def recorded_attempts(self) -> list[RecordedAttempt]: ...

    def open_cards(self, correlation_ids: list[str]) -> list[Any]: ...


class AssumeAttemptsOpen:
    """No Forge record: nothing can be read, so no attempt ever ends, a new or
    lost door record cannot be rebuilt (nothing is sent until it can), and
    nothing is reported. Only for commands that never poll (the release)."""

    def outcome(self, correlation_id: str) -> Any:
        raise AttemptRecordUnavailable("Forge's record is not configured")

    def recorded_attempts(self) -> list[RecordedAttempt]:
        raise AttemptRecordUnavailable("Forge's record is not configured")

    def open_cards(self, correlation_ids: list[str]) -> list[Any]:
        raise AttemptRecordUnavailable("Forge's record is not configured")


class ForgeAttempts:
    """:class:`AttemptRecord` from Forge's own SQLite record (read-only)."""

    def __init__(self, record: fr.ForgeRecord) -> None:
        self._record = record

    def outcome(self, correlation_id: str) -> Any:
        try:
            if is_mission(correlation_id):
                return self._record.outcome_for_mission(correlation_id)
            return self._record.outcome_for_single(correlation_id)
        except fr.ForgeRecordUnavailable as exc:
            raise AttemptRecordUnavailable(str(exc)) from None

    def recorded_attempts(self) -> list[RecordedAttempt]:
        try:
            found = []
            for attempt in self._record.all_linear_attempts():
                keys: tuple[str, ...] = ()
                if is_mission(attempt.correlation_id):
                    keys = tuple(self._record.outcome_for_mission(attempt.correlation_id).keys)
                found.append(
                    RecordedAttempt(
                        attempt.correlation_id, not attempt.ended, keys, attempt.filed_at
                    )
                )
            return found
        except fr.ForgeRecordUnavailable as exc:
            raise AttemptRecordUnavailable(str(exc)) from None

    def open_cards(self, correlation_ids: list[str]) -> list[Any]:
        try:
            return self._record.open_cards_for(correlation_ids)
        except fr.ForgeRecordUnavailable as exc:
            raise AttemptRecordUnavailable(str(exc)) from None


# ---------------------------------------------------------------------------
# The bus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BusMessage:
    subject: str
    data: bytes
    at: datetime | None = None  # the stream's own time for the message


class BusFeed(Protocol):
    """Messages from the bus, kept until the door has handled them."""

    def pending(self, name: str) -> list[BusMessage]: ...

    def done(self, name: str, message: BusMessage) -> None: ...


class NatsBusFeed:
    """Two non-consuming JetStream subscriptions, buffered for the poll.

    * cards: ``agents.approval.forge.*`` on AGENTS (limits retention). The
      ``*`` matches one token, so only four-token card subjects arrive, never
      ``.response``.
    * notifications: ``jarvis.notification.slack`` on JARVIS (limits, 1 hour).

    Each is an ordered consumer (ephemeral, no acknowledgements), starting
    from the time the door last recorded for it, or from the start of what the
    stream still holds. Neither is on the PIPELINE work queue, so neither can
    take a message from Forge.
    """

    STREAMS: ClassVar[dict[str, str]] = {CARDS: "AGENTS", NOTIFICATIONS: "JARVIS"}

    def __init__(
        self,
        nats_client: Any,
        *,
        wake: asyncio.Event | None = None,
        wake_if: Callable[[BusMessage], bool] | None = None,
    ) -> None:
        self._nats_client = nats_client
        self._wake = wake
        # Wake the door early only for messages about its own work.
        self._wake_if = wake_if
        self._buffers: dict[str, deque[BusMessage]] = {CARDS: deque(), NOTIFICATIONS: deque()}
        self._subscriptions: list[Any] = []

    @staticmethod
    def subjects() -> dict[str, str]:
        from nats_core import Topics

        cards = Topics.Agents.APPROVAL_REQUEST.replace("{agent_id}", "forge").replace(
            "{task_id}", "*"
        )
        return {CARDS: cards, NOTIFICATIONS: Topics.Jarvis.NOTIFICATION.format(adapter="slack")}

    async def start(self, marks: dict[str, str | None]) -> None:
        from nats.js.api import ConsumerConfig, DeliverPolicy

        js = self._nats_client.js
        for name, subject in self.subjects().items():
            mark = marks.get(name)
            if mark:
                config = ConsumerConfig(
                    deliver_policy=DeliverPolicy.BY_START_TIME,
                    opt_start_time=datetime.fromisoformat(mark),
                )
            else:
                config = ConsumerConfig(deliver_policy=DeliverPolicy.ALL)

            async def on_message(msg: Any, name: str = name) -> None:
                self._receive(name, msg)

            self._subscriptions.append(
                await js.subscribe(
                    subject,
                    stream=self.STREAMS[name],
                    cb=on_message,
                    ordered_consumer=True,
                    config=config,
                )
            )
            logger.info("linear_door_bus_subscribed", feed=name, subject=subject, since=mark)

    def _receive(self, name: str, msg: Any) -> None:
        at = None
        with contextlib.suppress(Exception):
            at = msg.metadata.timestamp
        message = BusMessage(msg.subject, bytes(msg.data or b""), at)
        self._buffers[name].append(message)
        if self._wake is not None and (self._wake_if is None or self._wake_if(message)):
            self._wake.set()

    def pending(self, name: str) -> list[BusMessage]:
        return list(self._buffers[name])

    def done(self, name: str, message: BusMessage) -> None:
        buffer = self._buffers[name]
        if buffer and buffer[0] is message:
            buffer.popleft()
        else:
            with contextlib.suppress(ValueError):
                buffer.remove(message)

    async def stop(self) -> None:
        for sub in self._subscriptions:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(sub.unsubscribe(), timeout=5.0)
        self._subscriptions.clear()


class AnswerPublisher(Protocol):
    """Publishes an ``ApprovalResponsePayload`` (Jarvis's
    :class:`~jarvis.infrastructure.slack_reply.NatsApprovalResponsePublisher`:
    core publish and flush on the AGENTS subject)."""

    async def publish(self, *, subject: str, payload: Any, correlation_id: str | None) -> None: ...


# ---------------------------------------------------------------------------
# The reporter
# ---------------------------------------------------------------------------


@dataclass
class _Attempt:
    """One open attempt, as read this poll."""

    correlation_id: str
    issues: list[tuple[str, str | None]]  # (issue id, identifier)
    outcome: Any = None
    by_key: dict[str, tuple[str, str | None]] = field(default_factory=dict)


@dataclass(frozen=True)
class _Target:
    attempt: _Attempt
    issues: list[tuple[str, str | None]]


def _now() -> datetime:
    return datetime.now(UTC)


class Reporter:
    """Factory → Linear for one door. Called by the door once per poll."""

    def __init__(
        self,
        *,
        client: Any,
        store: DoorStore,
        attempts: AttemptRecord,
        feed: BusFeed | None,
        answers: AnswerPublisher | None,
        approvers: dict[str, str],
        dashboard_summary: Path | None = None,
    ) -> None:
        self._client = client
        self._store = store
        self._attempts = attempts
        self._feed = feed
        self._answers = answers
        self._approvers = approvers
        # Cards Linear refused to take, by request id (in memory only).
        self._card_failures: dict[str, int] = {}
        # Section 11: this poll's read of the team's projects (set by the door
        # before :meth:`report`; ``None`` when it could not be read), and the
        # dashboard's summary file.
        self.projects: ProjectMap | None = None
        self._summary_path = dashboard_summary

    async def _write(
        self, issue_id: str, body: str, ref: str, *, parent_id: str | None = None
    ) -> str:
        return await write_once(self._client, self._store, issue_id, body, ref, parent_id=parent_id)

    # -- one poll ---------------------------------------------------------------

    async def report(self, state_ids: dict[str, str], unfinished: set[str]) -> None:
        """Progress, cards, notifications and answers for every open attempt.

        ``unfinished`` are sends still being delivered: no progress is written
        for them, and their cards and notifications are held until they are
        delivered. Raises on a Linear failure (the poll then backs off); a
        Forge record that cannot be read only skips what depends on it.
        """
        # Taken before Forge's record is read: Forge records a card before it
        # sends it, so every card here is already in the read below.
        cards = self._pending(CARDS)
        notes = self._pending(NOTIFICATIONS)
        attempts, unreadable = self._read_attempts(unfinished)
        for attempt in attempts.values():
            try:
                await self._progress(attempt, state_ids)
            except (LinearAuthError, LinearRateLimited):
                raise
            except LinearError as exc:
                # This attempt alone (an issue deleted, say): tried again next
                # poll, never holding up the others.
                logger.warning(
                    "linear_door_progress_failed",
                    correlation_id=attempt.correlation_id,
                    error=str(exc)[:300],
                )
        live = {cid: a for cid, a in attempts.items() if not a.outcome.ended}
        if unreadable:
            # A card or notification is matched only against every open
            # attempt; wait for a poll that can read them all.
            logger.info("linear_door_cards_wait_for_the_record", unreadable=len(unreadable))
        else:
            open_cards = self._open_cards(list(live))
            if open_cards is not None:
                await self._cards_from_bus(cards, live, unfinished, open_cards)
                await self._notifications(notes, live, unfinished)
                await self._cards_from_record(live, open_cards)
                await self._settle_claims(live, open_cards)
                self._close_settled_cards(live, open_cards)
        await self._read_answers()

    def _read_attempts(self, unfinished: set[str]) -> tuple[dict[str, _Attempt], list[str]]:
        found: dict[str, _Attempt] = {}
        unreadable: list[str] = []
        for cid in self._store.open_attempts():
            if cid in unfinished:
                continue
            try:
                outcome = self._attempts.outcome(cid)
            except AttemptRecordUnavailable as exc:
                logger.info(
                    "linear_door_attempt_record_unreadable", correlation_id=cid, error=str(exc)
                )
                unreadable.append(cid)
                continue
            issues = self._store.reserved_issues(cid)
            found[cid] = _Attempt(
                cid,
                issues,
                outcome,
                {feature_key(ident or ""): (iid, ident) for iid, ident in issues},
            )
        return found, unreadable

    def _open_cards(self, cids: list[str]) -> list[Any] | None:
        if not cids:
            return []
        try:
            return self._attempts.open_cards(cids)
        except AttemptRecordUnavailable as exc:
            logger.info("linear_door_open_cards_unreadable", error=str(exc))
            return None

    # -- progress -----------------------------------------------------------------

    async def _progress(self, attempt: _Attempt, state_ids: dict[str, str]) -> None:
        outcome = attempt.outcome
        cid = attempt.correlation_id
        if outcome.phase == fr.UNFILED and not outcome.ended:
            await self._unfiled(attempt)
            return
        if outcome.ended or outcome.phase == fr.ON_MAIN_REPORT_PENDING:
            # Straight to each issue's final comment and move, which already
            # carries each member's result: nothing in between can hold the
            # end up (Codex review R10).
            await self._end(attempt, finals(outcome, attempt.issues), state_ids)
            return
        if is_mission(cid):
            for key_attempt in getattr(outcome, "attempts", ()) or ():
                member = attempt.by_key.get(key_attempt.key)
                step = key_step(key_attempt)
                if member is not None and step is not None:
                    await self._write_step(cid, member[0], step.topic, step.key, step.text)
        step = phase_step(outcome)
        if step is not None:
            for issue_id, _ in attempt.issues:
                await self._write_step(cid, issue_id, step.topic, step.key, step.text)

    async def _write_step(self, cid: str, issue_id: str, topic: str, key: str, text: str) -> None:
        if self._store.progress(cid, issue_id, topic) == key:
            return
        await self._write(issue_id, comment(text), ref_for("step", cid, issue_id, topic, key))
        self._store.set_progress(cid, issue_id, topic, key)
        logger.info("linear_door_progress_comment", correlation_id=cid, topic=topic, key=key)

    async def _unfiled(self, attempt: _Attempt) -> None:
        cid = attempt.correlation_id
        since = self._store.progress(cid, "", "unfiled_since")
        if since is None:
            self._store.set_progress(cid, "", "unfiled_since", _now().isoformat())
            return
        if _now() - datetime.fromisoformat(since) < UNFILED_NOTICE_AFTER:
            return
        for issue_id, _ in attempt.issues:
            await self._write_step(cid, issue_id, "unfiled", "noted", UNFILED_NOTICE)

    async def _end(
        self, attempt: _Attempt, ends: dict[str, Final], state_ids: dict[str, str]
    ) -> None:
        """Final comment and move for each issue, then end the attempt.

        Linear is written first and each step is recorded, so a failure part
        way is resumed next poll without repeating a comment; the attempt (and
        its reservations) ends only after every issue is done. A single issue
        on main before Forge's merge report is Done but not ended: it is
        watched until the report says whether the deploy worked, and a failed
        deploy is then said once (Codex review R11).
        """
        cid = attempt.correlation_id
        outcome = attempt.outcome
        pending = [
            iid for iid, _ in attempt.issues if self._store.progress(cid, iid, "moved") is None
        ]
        current = {i.id: i for i in await self._client.issues_by_id(pending)} if pending else {}
        for issue_id, _ in attempt.issues:
            final = ends.get(issue_id)
            if final is None:
                continue
            try:
                if self._store.progress(cid, issue_id, "final") is None:
                    await self._write(
                        issue_id, comment(final.text), ref_for("final", cid, issue_id)
                    )
                    self._store.set_progress(cid, issue_id, "final", outcome.phase)
                if outcome.phase == fr.ON_MAIN_DEPLOY_FAILED and not is_mission(cid):
                    # Its own ref, whatever the final comment said or when:
                    # written once, and the attempt ends only after it.
                    await self._write(
                        issue_id,
                        comment(deploy_failed_words(outcome)),
                        ref_for("deploy-failed", cid, issue_id),
                    )
                if self._store.progress(cid, issue_id, "moved") is None:
                    issue = current.get(issue_id)
                    state_id = _move_to(final.target, issue, state_ids)
                    if state_id is not None:
                        await self._client.move_issue(issue_id, state_id)
                    self._store.set_progress(cid, issue_id, "moved", final.target)
            except LinearRefused as exc:
                # The issue was deleted (or Linear refuses it for good): it is
                # finished here, so the others still end and are released.
                logger.warning(
                    "linear_door_final_refused", correlation_id=cid, error=str(exc)[:300]
                )
                self._store.set_progress(cid, issue_id, "final", "refused")
                self._store.set_progress(cid, issue_id, "moved", "refused")
        if not outcome.ended:
            return  # on main, waiting for Forge's merge report
        if outcome.phase in (fr.ON_MAIN, fr.ON_MAIN_DEPLOY_FAILED) and not (
            await self._project_update(attempt)
        ):
            return  # the projects could not be read: tried again next poll
        reason = f"{outcome.phase}: {outcome.reason}"[:500]
        self._store.end_attempt(cid, reason)
        logger.info("linear_door_attempt_ended", correlation_id=cid, phase=attempt.outcome.phase)

    # -- project updates (section 11.4) ----------------------------------------------

    def _attempt_repo(self, cid: str) -> str | None:
        """The repository the attempt was sent to, from its frozen payload."""
        send = self._store.get_send(cid)
        if send is None:
            return None
        try:
            payload = json.loads(send.payload).get("payload") or {}
        except (ValueError, AttributeError):
            return None
        repo = payload.get("target_repo") if isinstance(payload, dict) else None
        return str(repo) if repo else None

    async def _project_update(self, attempt: _Attempt) -> bool:
        """Post the merge's project update once. ``False`` when it cannot be
        decided this poll (the projects read failed), so the attempt waits."""
        from jarvis.infrastructure.linear import updates as up

        cid = attempt.correlation_id
        if self._store.progress(cid, "", "project-update") is not None:
            return True
        projects = self.projects
        if projects is None:
            logger.info("linear_door_project_update_waits", correlation_id=cid)
            return False
        log = logger.bind(correlation_id=cid)
        repo = self._attempt_repo(cid)
        issues = {i.id: i for i in await self._client.issues_by_id([i for i, _ in attempt.issues])}
        if repo is None:
            # A rebuilt record keeps no payload: the issues' own project.
            found = {
                m.repo
                for i in issues.values()
                if i.project_id and (m := projects.for_project(i.project_id)) and m.repo
            }
            repo = found.pop() if len(found) == 1 else None
        project = projects.project_for_repo(repo) if repo else None
        if repo is None or project is None or project.archived or project.completed:
            why = (
                "no repository"
                if repo is None
                else "no project"
                if project is None
                else "archived or completed project"
            )
            self._store.set_progress(cid, "", "project-update", f"skipped: {why}")
            log.info("linear_door_project_update_skipped", reason=why)
            return True

        outcome = attempt.outcome
        landed_keys = set(getattr(outcome, "landed_keys", ()) or ())

        def line(issue_id: str, identifier: str | None) -> tuple[str, str]:
            found = issues.get(issue_id)
            return (identifier or issue_id, found.title if found is not None else "")

        mission = is_mission(cid)
        landed, not_landed = [], []
        for issue_id, identifier in attempt.issues:
            if not mission or feature_key(identifier or "") in landed_keys:
                landed.append(line(issue_id, identifier))
            else:
                not_landed.append(line(issue_id, identifier))
        send = self._store.get_send(cid)
        delivered = up.Delivered(
            correlation_id=cid,
            repo=repo,
            landed=landed,
            not_landed=not_landed,
            commit=getattr(outcome, "j_commit", None),
            mission_title=send.mission_title if send is not None else None,
            deploy_failed=_deploy_reason(outcome)
            if outcome.phase == fr.ON_MAIN_DEPLOY_FAILED
            else "",
            is_mission=mission,
        )
        open_in_linear = await self._client.project_open_issues(project.id)
        summary = up.read_summary(self._summary_path)
        health, health_line = up.update_health(delivered, summary)
        body = up.update_body(delivered, summary, open_in_linear, health_line)
        try:
            await up.post_update_once(
                self._client,
                self._store,
                project.id,
                body,
                ref_for("project-update", cid),
                health=health,
            )
        except LinearRefused as exc:
            # The project was deleted, say: given up, so the attempt still ends.
            log.warning("linear_door_project_update_refused", error=str(exc)[:300])
            self._store.set_progress(cid, "", "project-update", "refused")
            return True
        self._store.set_progress(cid, "", "project-update", "posted")
        log.info("linear_door_project_update_posted", health=health or "omitted")
        return True

    # -- the bus -------------------------------------------------------------------

    def _pending(self, name: str) -> list[tuple[int | None, BusMessage]]:
        """Messages held in the door's record (with their id), then the feed's."""
        held: list[tuple[int | None, BusMessage]] = [
            (held_id, BusMessage(subject, data, datetime.fromisoformat(at) if at else None))
            for held_id, subject, data, at in self._store.held_messages(name)
        ]
        fresh = self._feed.pending(name) if self._feed is not None else []
        return held + [(None, message) for message in fresh]

    def _handled(self, name: str, held_id: int | None, message: BusMessage) -> None:
        if held_id is not None:
            self._store.release_message(held_id)
            return
        assert self._feed is not None
        if message.at is not None:
            self._store.set_mark(name, message.at.isoformat())
        self._feed.done(name, message)

    def _hold(self, name: str, held_id: int | None, message: BusMessage) -> None:
        """Keep a message for a send not yet delivered (Codex review R4). It is
        kept in the door's record, so the feed's mark may move past it."""
        if held_id is not None:
            return
        at = message.at.isoformat() if message.at is not None else None
        self._store.hold_message(name, message.subject, message.data, at)
        self._handled(name, None, message)

    # -- cards ---------------------------------------------------------------------

    @staticmethod
    def _index(live: dict[str, _Attempt]) -> dict[str, _Target]:
        """Every id a card may name an open attempt's work by."""
        index: dict[str, _Target] = {}
        for cid, attempt in live.items():
            outcome = attempt.outcome
            everyone = _Target(attempt, attempt.issues)
            for key in (
                cid,
                getattr(outcome, "build_id", None),
                getattr(outcome, "merge_build_id", None),
                getattr(outcome, "mission_id", None),
            ):
                if key:
                    index.setdefault(str(key), everyone)
            mission_id = getattr(outcome, "mission_id", None)
            if mission_id:
                index.setdefault(f"mission-{mission_id}", everyone)
            for key_attempt in getattr(outcome, "attempts", ()) or ():
                member = attempt.by_key.get(key_attempt.key)
                if member is not None and key_attempt.correlation_id:
                    index.setdefault(key_attempt.correlation_id, _Target(attempt, [member]))
        return index

    @staticmethod
    def _card_state(
        kind: str,
        request_id: str,
        attempt: _Attempt,
        open_cards: list[Any],
        build_id: str | None = None,
    ) -> str:
        """Whether Forge's record shows the card open (a card answered in Slack,
        or anywhere, is settled). One rule: the card's request id is among the
        record's open cards. A mission's plan card is recorded just after it is
        sent, so it is open while the mission is PROPOSED with no other card
        recorded. A build gate or other card whose build the record does not
        link to this attempt cannot be checked: ``_UNKNOWN`` (Slack only)."""
        outcome = attempt.outcome
        if outcome.ended:
            return _SETTLED
        if kind == MISSION_PLAN:
            waiting = getattr(outcome, "request_id", None)
            open_now = outcome.phase == fr.PLAN_CARD_OPEN and waiting in (None, request_id)
            return _OPEN if open_now else _SETTLED
        if any(c.request_id == request_id for c in open_cards):
            return _OPEN
        if kind != OTHER:
            return _SETTLED
        known = {getattr(outcome, "build_id", None), getattr(outcome, "merge_build_id", None)}
        return _SETTLED if build_id and build_id in known else _UNKNOWN

    def _members(self, attempt: _Attempt) -> tuple[list[str], list[str]]:
        """For a mission merge card: the members that landed and those that did not."""
        if not is_mission(attempt.correlation_id):
            return [], []
        landed = set(getattr(attempt.outcome, "landed_keys", ()) or ())
        yes = [ident or iid for key, (iid, ident) in attempt.by_key.items() if key in landed]
        no = [ident or iid for key, (iid, ident) in attempt.by_key.items() if key not in landed]
        return sorted(yes), sorted(no)

    async def _cards_from_bus(
        self,
        messages: list[tuple[int | None, BusMessage]],
        live: dict[str, _Attempt],
        unfinished: set[str],
        open_cards: list[Any],
    ) -> None:
        index = self._index(live)
        for held_id, message in messages:
            card = parse_card(message.subject, message.data, message.at)
            if card is not None:
                keys = card.match_keys()
                target = next((index[k] for k in keys if k in index), None)
                if target is None and _belongs_to(keys, unfinished):
                    self._hold(CARDS, held_id, message)
                    continue
                if target is not None:
                    state = self._card_state(
                        card.kind, card.request_id, target.attempt, open_cards, _gate_build(card)
                    )
                    if state == _SETTLED:
                        logger.info(
                            "linear_door_card_not_open",
                            request_id=card.request_id,
                            correlation_id=target.attempt.correlation_id,
                        )
                    else:
                        answerable = state == _OPEN and not card.slack_only
                        try:
                            await self._post_card(card, target, answerable=answerable)
                        except LinearRefused as exc:
                            # Linear refused this comment (its issue deleted,
                            # say): the card is kept in the door's record for
                            # the next poll, and let go after a few refusals
                            # so the cards behind it still arrive.
                            tries = self._card_failures.get(card.request_id, 0) + 1
                            self._card_failures[card.request_id] = tries
                            logger.warning(
                                "linear_door_card_refused",
                                request_id=card.request_id,
                                tries=tries,
                                error=str(exc)[:300],
                            )
                            if tries < MAX_CARD_TRIES:
                                self._hold(CARDS, held_id, message)
                                return
                        except BaseException:
                            # An outage (no answer, a time-out, HTTP 5xx), the
                            # rate limit or a refused key: nothing is counted;
                            # the full card is kept in the door's record and
                            # the poll stops (Codex review R9, coach C3).
                            self._hold(CARDS, held_id, message)
                            raise
            self._handled(CARDS, held_id, message)

    async def _post_card(self, card: Card, target: _Target, *, answerable: bool) -> None:
        attempt = target.attempt
        landed, missing = self._members(attempt) if card.kind == MERGE else ([], [])
        body = card_comment(card, landed=landed, missing=missing, answerable=answerable)
        for issue_id, _ in target.issues:
            if self._store.card_posted(card.request_id, issue_id):
                continue
            comment_id = await self._write(
                issue_id, body, ref_for("card", card.request_id, issue_id)
            )
            self._store.record_card(
                CardComment(
                    request_id=card.request_id,
                    issue_id=issue_id,
                    comment_id=comment_id,
                    correlation_id=attempt.correlation_id,
                    kind=card.kind,
                    answerable=answerable,
                    approval_subject=card.subject,
                    reply_correlation_id=card.correlation_id,
                    assumption_ids=card.assumption_ids(),
                )
            )
            logger.info(
                "linear_door_card_posted",
                kind=card.kind,
                request_id=card.request_id,
                correlation_id=attempt.correlation_id,
                answerable=answerable,
            )

    async def _notifications(
        self,
        messages: list[tuple[int | None, BusMessage]],
        live: dict[str, _Attempt],
        unfinished: set[str],
    ) -> None:
        for held_id, message in messages:
            note = parse_notification(message.data)
            attempt = live.get(note.correlation_id) if note is not None else None
            if (
                note is not None
                and attempt is None
                and _belongs_to([note.correlation_id], unfinished)
            ):
                self._hold(NOTIFICATIONS, held_id, message)
                continue
            if note is not None and attempt is not None and attempt.outcome.phase == fr.UNFILED:
                body = notification_comment(note)
                key = f"{attempt.correlation_id}\n{note.message_id}"
                for issue_id, _ in attempt.issues:
                    if self._store.notice_posted(issue_id, key):
                        continue
                    await self._write(issue_id, body, ref_for("note", key, issue_id))
                    self._store.record_notice(issue_id, key)
                logger.info(
                    "linear_door_notification_copied", correlation_id=attempt.correlation_id
                )
            self._handled(NOTIFICATIONS, held_id, message)

    async def _cards_from_record(self, live: dict[str, _Attempt], open_cards: list[Any]) -> None:
        index = self._index(live)
        now = _now()
        # Cards the door has in full, held or still buffered: these wait for
        # the full card, never for the Slack-only fallback (Codex review R9).
        waiting = {
            card.request_id
            for _, message in self._pending(CARDS)
            if (card := parse_card(message.subject, message.data)) is not None
        }
        for found in open_cards:
            if found.request_id in waiting:
                continue
            target = next(
                (
                    index[k]
                    for k in (found.correlation_id, getattr(found, "build_id", None))
                    if k and k in index
                ),
                None,
            )
            if target is None:
                continue
            cid = target.attempt.correlation_id
            issues = [
                (iid, ident)
                for iid, ident in target.issues
                if not self._store.card_posted(found.request_id, iid)
            ]
            if not issues:
                continue
            topic = f"card-seen:{found.request_id}"
            seen = self._store.progress(cid, "", topic)
            if seen is None:
                self._store.set_progress(cid, "", topic, now.isoformat())
                continue
            if now - datetime.fromisoformat(seen) < RECOVERY_GRACE:
                continue
            kind = _RECORD_KINDS.get(found.kind, OTHER)
            landed, missing = self._members(target.attempt) if kind == MERGE else ([], [])
            body, answerable = recovered_card_comment(
                kind,
                found.request_id,
                app_url=getattr(found, "app_url", None),
                report_url=getattr(found, "report_url", None),
                landed=landed,
                missing=missing,
            )
            for issue_id, _ in issues:
                comment_id = await self._write(
                    issue_id, body, ref_for("card", found.request_id, issue_id)
                )
                self._store.record_card(
                    CardComment(
                        request_id=found.request_id,
                        issue_id=issue_id,
                        comment_id=comment_id,
                        correlation_id=cid,
                        kind=kind,
                        answerable=answerable and bool(found.approval_subject),
                        approval_subject=found.approval_subject,
                        reply_correlation_id=found.correlation_id,
                    )
                )
            logger.info(
                "linear_door_card_posted_from_record",
                kind=kind,
                request_id=found.request_id,
                correlation_id=cid,
            )

    async def _settle_claims(self, live: dict[str, _Attempt], open_cards: list[Any]) -> None:
        """Answers claimed whose publish never returned (Codex review R2, R8).

        The original is never published again. If Forge's record still shows
        the card open, the person is told once under it and the card takes a
        new reply (Forge keeps the first answer it gets, so a second is
        harmless); otherwise the claim is simply settled.
        """
        for claim in self._store.unpublished_claims():
            attempt = live.get(claim.correlation_id)
            if (
                attempt is not None
                and self._card_state(claim.kind, claim.request_id, attempt, open_cards) == _OPEN
            ):
                own = await self._write(
                    claim.issue_id,
                    comment(UNCONFIRMED_ANSWER),
                    ref_for("unconfirmed", claim.reply_id),
                    parent_id=claim.comment_id,
                )
                self._store.record_reply(own, claim.request_id, "the door's own")
                self._store.reopen_card(claim.request_id)
                logger.info("linear_door_answer_reopened", request_id=claim.request_id)
            self._store.settle_claim(claim.reply_id)

    def _close_settled_cards(self, live: dict[str, _Attempt], open_cards: list[Any]) -> None:
        """Stop reading answers under cards Forge's record no longer shows open."""
        for card in self._store.open_cards():
            attempt = live.get(card.correlation_id)
            if attempt is None:
                continue
            if self._card_state(card.kind, card.request_id, attempt, open_cards) != _OPEN:
                self._store.set_card_status(card.request_id, "closed")

    # -- answers -------------------------------------------------------------------

    async def _read_answers(self) -> None:
        cards = self._store.open_cards(answerable_only=True)
        if not cards or self._answers is None:
            return
        by_comment = {c.comment_id: c for c in cards}
        for reply in await self._client.replies_under(list(by_comment)):
            if self._store.reply_handled(reply.id):
                continue
            card = by_comment.get(reply.parent_id)
            if card is None:
                continue
            if reply.body.lstrip().startswith(COMMENT_PREFIX.strip()):
                self._store.record_reply(reply.id, card.request_id, "the door's own")
                continue
            decision, notes = parse_reply(reply.body)
            if decision is None:
                self._store.record_reply(reply.id, card.request_id, "not an answer")
                continue
            current = next(
                (
                    c
                    for c in self._store.cards_of(card.correlation_id)
                    if c.comment_id == card.comment_id
                ),
                card,
            )
            if current.status != "open":
                self._store.record_reply(reply.id, card.request_id, "card already answered")
                continue
            identity = self._approvers.get(reply.user_id or "")
            if identity is None:
                await self._refuse(card, reply.id, reply.user_id)
                continue
            await self._answer(card, reply.id, decision, notes, identity)

    async def _refuse(self, card: CardComment, reply_id: str, user_id: str | None) -> None:
        key = f"not-listed\n{card.comment_id}\n{user_id or ''}"
        if not self._store.notice_posted(card.issue_id, key):
            own = await self._write(
                card.issue_id,
                comment(NOT_LISTED),
                ref_for("not-listed", card.comment_id, user_id or ""),
                parent_id=card.comment_id,
            )
            self._store.record_reply(own, card.request_id, "the door's own")
            self._store.record_notice(card.issue_id, key)
        self._store.record_reply(reply_id, card.request_id, "author not listed")
        logger.info("linear_door_answer_refused", request_id=card.request_id)

    async def _answer(
        self, card: CardComment, reply_id: str, decision: str, notes: str | None, identity: str
    ) -> None:
        from nats_core.events import ApprovalResponsePayload, AssumptionDisposition

        assert self._answers is not None and card.approval_subject
        dispositions = (
            [
                AssumptionDisposition(assumption_id=a, disposition="accepted")
                for a in card.assumption_ids
            ]
            if decision == "approve"
            else []
        )
        payload = ApprovalResponsePayload(
            request_id=card.request_id,
            decision=decision,  # type: ignore[arg-type]
            decided_by=identity,
            notes=answer_notes(card.kind, decision, notes),
            dispositions=dispositions or None,
        )
        # Claimed first, and never published again (Codex review R2, R8): a
        # publish that raised may still have reached the factory (a flush that
        # timed out after the send), and one interrupted may not have. Either
        # way the claim stays unpublished and :meth:`_settle_claims` deals
        # with it on a later poll.
        self._store.claim_answer(reply_id, card, decision)
        try:
            await self._answers.publish(
                subject=f"{card.approval_subject}.response",
                payload=payload,
                correlation_id=card.reply_correlation_id,
            )
        except Exception as exc:
            logger.warning(
                "linear_door_answer_not_confirmed",
                request_id=card.request_id,
                error_class=type(exc).__name__,
            )
            return
        self._store.mark_published(reply_id)
        logger.info(
            "linear_door_answer_published",
            request_id=card.request_id,
            decision=decision,
            decided_by=identity,
        )
        words = {"approve": "merge", "reject": "decline"} if card.kind == MERGE else {}
        word = words.get(decision, decision)
        own = await self._write(
            card.issue_id,
            comment(
                f"Sent **{word}** to the factory. What happens next is reported here from the "
                "factory's own record."
            ),
            ref_for("ack", reply_id),
            parent_id=card.comment_id,
        )
        self._store.record_reply(own, card.request_id, "the door's own")


#: Forge's record's card kinds, as the door's.
_RECORD_KINDS = {"merge": MERGE, "plan": PLAN, "mission_plan": MISSION_PLAN}


def wakes_for(store: DoorStore) -> Callable[[BusMessage], bool]:
    """Whether a card or notification is about one of the door's own open
    attempts (its correlation id is the attempt's, or a child of it), so the
    door polls at once rather than at the next poll (coach C6)."""

    def ours(message: BusMessage) -> bool:
        card = parse_card(message.subject, message.data)
        if card is not None:
            named = [card.correlation_id, card.details.get("correlation_id")]
        else:
            note = parse_notification(message.data)
            named = [note.correlation_id] if note is not None else []
        return _belongs_to([str(c) for c in named if c], set(store.open_attempts()))

    return ours


def _belongs_to(correlation_ids: list[str], unfinished: set[str]) -> bool:
    """Whether a message is for a send not yet delivered: its correlation id
    is the send's, or a child of it (a mission feature's
    ``<mission cid>-<KEY>-a<n>``)."""
    return any(
        cid == send or cid.startswith(f"{send}-") for cid in correlation_ids for send in unfinished
    )


def _gate_build(card: Card) -> str | None:
    """The build a build gate (or other card) is about: its details' build id,
    else the first part of Forge's ``<build>:<stage>:<n>`` request id."""
    named = card.details.get("build_id")
    if named:
        return str(named)
    parts = card.request_id.split(":")
    return unquote(parts[0]) if len(parts) == 3 and parts[2].isdigit() else None


def _deploy_reason(outcome: Any) -> str:
    """Why the deploy after a merge failed, from the reader's "merged into
    main, but its deploy failed: …"."""
    text = " ".join(str(outcome.reason or "").split()).rstrip(".")
    _, sep, after = text.partition("deploy failed: ")
    return after if sep and after else "no reason was given"


def _move_to(target: str, issue: Any, state_ids: dict[str, str]) -> str | None:
    """The status to move an ending issue to, or ``None`` to leave it.

    Done: unless it is already finished (Done, Canceled, a duplicate).
    Backlog: only while it is still In Progress, the door's own status, so a
    person who has already moved it (back to Todo to retry, or anywhere else)
    is not overruled.
    """
    if issue is None:
        return None
    if target == DONE:
        return None if is_finished(issue.state.type) else state_ids.get("done")
    if target == BACKLOG:
        return state_ids.get("backlog") if issue.state.id == state_ids.get("started") else None
    return None


__all__ = [
    "CARDS",
    "NOTIFICATIONS",
    "RECOVERY_GRACE",
    "REF_WORD",
    "UNCONFIRMED_ANSWER",
    "UNFILED_NOTICE",
    "UNFILED_NOTICE_AFTER",
    "AnswerPublisher",
    "AssumeAttemptsOpen",
    "AttemptRecord",
    "AttemptRecordUnavailable",
    "BusFeed",
    "BusMessage",
    "ForgeAttempts",
    "NatsBusFeed",
    "RecordedAttempt",
    "Reporter",
    "ref_for",
    "wakes_for",
    "write_once",
    "write_once_to",
]
