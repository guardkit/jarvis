"""The factory's cards and answers as Linear comments — the pure part of stage 4.

Nothing here talks to Linear, the bus or Forge's record. It reads a card
message from the AGENTS stream (``agents.approval.forge.<id>``), decides what
kind of card it is, writes it as a comment (design section 2, "What is written
to the issue"), reads a reply's first word, and reads a Slack notification.

The card text follows what Jarvis's Slack cards show, reusing their helpers
where they fit (:mod:`jarvis.infrastructure.assumption_dialogue` for the plan
card's examples, assumptions and sign-in question), written as Markdown.
Links are shown only when they are ``https`` (design section 2, the Slack
card's rule).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from jarvis.infrastructure.linear.mapping import comment

# Card kinds.
PLAN = "plan"
MISSION_PLAN = "mission_plan"
MERGE = "merge"
OTHER = "other"

#: The four-token card subject, ``agents.approval.forge.<id>``.
CARD_SUBJECT_PREFIX = "agents.approval.forge."

#: What a reply's first word means (design section 2, "Answering a card").
_ANSWER_WORDS = {"approve": "approve", "merge": "approve", "reject": "reject", "decline": "reject"}

#: The word that tells a plan card's run to stop rather than redraft; the
#: Slack card's decline control sends the same (``assumption_dialogue``).
PLAN_REJECT_WORD = "reject"

APPROVE_ENDING = "Reply to this comment with **approve** or **reject**."
MERGE_ENDING = "Reply to this comment with **merge** or **decline**."
ANSWER_IN_SLACK = (
    "A plan card is waiting. Its details have expired from the message stream; "
    "please answer it in Slack."
)
OTHER_IN_SLACK = (
    "A factory card is waiting. Its details have expired from the message stream; "
    "please answer it in Slack."
)
#: Forge's sign-in confirmation card (``planning/driver.py`` 307, 9965-10010):
#: what approve and reject mean there is not what they mean on a plan card,
#: so it is answered in Slack only (Codex review R7).
AUTH_CONFIRMATION = "auth_surface_confirmation"
#: The ending of a card whose openness the door cannot check in Forge's
#: record: shown, but answered in Slack only (Codex review R6).
SLACK_ONLY_ENDING = "Answer this card in Slack; it cannot be answered here."
NOT_LISTED = "Only the people listed can answer this card."

# A comment is cut here; Forge's cards are far shorter.
_MAX_BODY = 20_000
# Characters that would break a Markdown link or hide part of it.
_LINK_FORBIDDEN = re.compile(r"[\s<>()\[\]\"'`\\\x00-\x1f\x7f]")
_MAX_URL = 2_000
_FIRST_WORD = re.compile(r"^[\W_]*([A-Za-z]+)[\W_]*(.*)$", re.DOTALL)


@dataclass(frozen=True)
class Card:
    """One factory card, read from the AGENTS stream."""

    subject: str
    request_id: str
    kind: str
    correlation_id: str | None  # the envelope's
    action_description: str
    details: dict[str, Any]
    sent_at: datetime | None = None

    @property
    def token(self) -> str:
        return self.subject.rsplit(".", 1)[-1]

    def match_keys(self) -> list[str]:
        """The ids a card may name its work by, most specific first."""
        details = self.details
        keys = [
            self.correlation_id,
            _text(details.get("correlation_id")),
            _text(details.get("build_id")),
            _text(details.get("feature_id")),
            _text(details.get("mission_id")),
            self.token,
        ]
        for prefix in ("plan-", "mission-", "merge-"):
            if self.token.startswith(prefix):
                keys.append(self.token[len(prefix) :])
        return list(dict.fromkeys(k for k in keys if k))

    @property
    def slack_only(self) -> bool:
        """A card shown here but answered in Slack only (the sign-in check)."""
        summary = self.details.get("summary")
        checkpoint = summary.get("checkpoint") if isinstance(summary, dict) else None
        return AUTH_CONFIRMATION in (self.details.get("checkpoint_type"), checkpoint)

    def assumption_ids(self) -> tuple[str, ...]:
        """The ids an approve accepts: every assumption on a plan card (as the
        Slack card's "approve all" and the harness's ``answer_for`` do)."""
        if self.kind != PLAN:
            return ()
        from jarvis.infrastructure.assumption_dialogue import _assumptions

        return tuple(str(item["id"]) for item in _assumptions(self.details))


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def card_kind(token: str, request_id: str, details: dict[str, Any]) -> str:
    from jarvis.infrastructure.assumption_dialogue import is_planning_checkpoint

    if (
        request_id.startswith("merge-")
        or "merge_offer" in details
        or details.get("kind") == "merge_deploy_offer"
    ):
        return MERGE
    if token.startswith("mission-"):
        return MISSION_PLAN
    if is_planning_checkpoint(details) or token.startswith("plan-"):
        return PLAN
    return OTHER


def parse_card(subject: str, data: bytes, sent_at: datetime | None = None) -> Card | None:
    """A card from one AGENTS message, or ``None`` when it is not one.

    Only four-token subjects are cards; ``.response`` (five tokens) never is.
    """
    if not subject.startswith(CARD_SUBJECT_PREFIX) or len(subject.split(".")) != 4:
        return None
    from nats_core import MessageEnvelope
    from nats_core.events import ApprovalRequestPayload
    from pydantic import ValidationError

    try:
        envelope = MessageEnvelope.model_validate_json(data)
    except (ValidationError, ValueError):
        return None
    if str(getattr(envelope.event_type, "value", envelope.event_type)) != "approval_request":
        return None
    try:
        payload = ApprovalRequestPayload.model_validate(envelope.payload)
    except ValidationError:
        return None
    details = payload.details if isinstance(payload.details, dict) else {}
    token = subject.rsplit(".", 1)[-1]
    return Card(
        subject=subject,
        request_id=payload.request_id,
        kind=card_kind(token, payload.request_id, details),
        correlation_id=envelope.correlation_id,
        action_description=payload.action_description,
        details=details,
        sent_at=sent_at,
    )


# ---------------------------------------------------------------------------
# Writing a card
# ---------------------------------------------------------------------------


def https_link(url: Any) -> str | None:
    """``url`` when it is a plain ``https`` link, else ``None``."""
    if not isinstance(url, str) or not url or len(url) > _MAX_URL:
        return None
    if _LINK_FORBIDDEN.search(url):
        return None
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc:
        return None
    return url


def _links(app_url: Any, report_url: Any) -> list[str]:
    lines = []
    app = https_link(app_url)
    if app:
        lines.append(f"[Try the preview]({app})")
    report = https_link(report_url)
    if report:
        lines.append(f"[Read the test report]({report})")
    return lines


def _lines(text: str) -> str:
    """Forge's line breaks kept as Markdown line breaks."""
    return "  \n".join(line.rstrip() for line in str(text).strip().splitlines())


def _finish(parts: list[str], ending: str | None) -> str:
    body = "\n\n".join(p for p in parts if p)
    if len(body) > _MAX_BODY:
        body = body[:_MAX_BODY].rstrip() + " …"
    if ending:
        body = f"{body}\n\n{ending}"
    return comment(body)


def _plan_parts(details: dict[str, Any]) -> list[str]:
    from jarvis.infrastructure import assumption_dialogue as ad

    parts: list[str] = []
    if ad.is_spec_digest(details):
        card = ad.digest_card(details)
        title = str(card.get("title") or "The spec is ready — here's what will be built")
        heading = [f"**{title}**"]
        if card.get("feature"):
            heading.append(f"Feature: {card['feature']}")
        if card.get("target_repo"):
            heading.append(f"Repo: {card['target_repo']}")
        parts.append("  \n".join(heading))
        for key in ("what_happened", "possible_contradiction"):
            if card.get(key):
                parts.append(_lines(str(card[key])))
        examples = ad._digest_examples(card)
        if examples:
            lines = ["**What it will do**"]
            for index, example in enumerate(examples, 1):
                words = ad.tag_words(example.get("tags"))
                extra = f" _({' · '.join(words)})_" if words else ""
                lines.append(f"{index}. {example.get('sentence') or ''}{extra}")
            parts.append("\n".join(lines))
        assumed = ad._digest_assumptions(card)
        if assumed:
            lines = ["**What the machine assumed**"]
            for index, entry in enumerate(assumed, 1):
                why = f" — _why: {entry['why']}_" if entry.get("why") else ""
                lines.append(f"{index}. {entry.get('assumption') or ''}{why}")
            parts.append("\n".join(lines))
        else:
            parts.append("The spec makes no assumptions of its own.")
        check = card.get("sign_in_check")
        if isinstance(check, dict) and check:
            lines = [f"**{check.get('title') or 'One thing to confirm'}**"]
            if check.get("statement"):
                lines.append(f"> {check['statement']}")
            lines.append(
                "Approving here leaves this question unanswered"
                + (f": {check['no_answer_means']}" if check.get("no_answer_means") else ".")
                + " To answer it, use the card in Slack."
            )
            parts.append("\n\n".join(lines))
        return parts
    assumptions = ad._assumptions(details)
    if details.get("rationale"):
        parts.append(_lines(str(details["rationale"])))
    if assumptions:
        lines = ["**Assumptions** (approve accepts them all)"]
        for item in assumptions:
            lines.append(f"- **{item['id']}** {item.get('text') or ''}")
        parts.append("\n".join(lines))
    return parts


def card_comment(
    card: Card,
    *,
    landed: list[str] | None = None,
    missing: list[str] | None = None,
    answerable: bool = True,
) -> str:
    """The comment for a card from the bus.

    ``landed`` and ``missing`` are the mission members whose keys did and did
    not land on the mission branch (merge card of a mission). A card that is
    not ``answerable`` here ends by saying to answer it in Slack.
    """
    details = card.details
    if card.kind == MERGE:
        evidence = details.get("review_evidence")
        evidence = evidence if isinstance(evidence, dict) else {}
        parts = ["**The merge card is waiting for your answer.**"]
        if card.action_description:
            parts.append(_lines(card.action_description))
        parts.extend(_links(evidence.get("app_url"), evidence.get("report_url")))
        parts.extend(_mission_lines(landed, missing))
        return _finish(parts, MERGE_ENDING)
    if card.kind == MISSION_PLAN:
        parts = ["**The mission's plan card is waiting for your answer.**"]
        parts.append(_lines(str(details.get("rationale") or card.action_description)))
        return _finish(parts, APPROVE_ENDING)
    if card.slack_only:
        summary = details.get("summary")
        summary = summary if isinstance(summary, dict) else {}
        title = str(summary.get("title") or card.action_description or "A factory card")
        return _finish([f"**A factory card is waiting: {title}**"], SLACK_ONLY_ENDING)
    if card.kind == PLAN:
        parts = ["**The plan card is waiting for your answer.**"]
        parts.extend(_plan_parts(details))
        return _finish(parts, APPROVE_ENDING)
    stage = _text(details.get("stage_label"))
    parts = [f"**A factory card is waiting for your answer{f' ({stage})' if stage else ''}.**"]
    if card.action_description:
        parts.append(_lines(card.action_description))
    if details.get("rationale") and str(details["rationale"]) != card.action_description:
        parts.append(_lines(str(details["rationale"])))
    return _finish(parts, APPROVE_ENDING if answerable else SLACK_ONLY_ENDING)


def _mission_lines(landed: list[str] | None, missing: list[str] | None) -> list[str]:
    lines = []
    if landed:
        lines.append(f"Landed on the mission branch: {', '.join(landed)}.")
    if missing:
        lines.append(f"Did not land (merging leaves these out): {', '.join(missing)}.")
    return lines


def recovered_card_comment(
    kind: str,
    request_id: str,
    *,
    app_url: Any = None,
    report_url: Any = None,
    landed: list[str] | None = None,
    missing: list[str] | None = None,
) -> tuple[str, bool]:
    """The comment for a card found open in Forge's record but no longer in
    the stream, and whether it can be answered from Linear.

    A merge card carries everything an answer needs; a plan card's assumption
    list is gone, so it is answered in Slack (design review round 3, R11).
    """
    if kind == MERGE:
        parts = [
            "**The merge card is waiting for your answer.** Its full text has expired "
            "from the message stream; the card in Slack has it."
        ]
        parts.extend(_links(app_url, report_url))
        parts.extend(_mission_lines(landed, missing))
        return _finish(parts, MERGE_ENDING), True
    words = ANSWER_IN_SLACK if kind in (PLAN, MISSION_PLAN) else OTHER_IN_SLACK
    return _finish([f"{words} (`{request_id}`)"], None), False


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------


def parse_reply(body: str) -> tuple[str | None, str | None]:
    """``(decision, notes)`` from a reply: the first word decides, the rest is
    the note. Anything else is ``(None, None)`` and ignored."""
    match = _FIRST_WORD.match(body.strip())
    if not match:
        return None, None
    decision = _ANSWER_WORDS.get(match.group(1).lower())
    if decision is None:
        return None, None
    notes = match.group(2).strip().strip("*_").strip() or None
    return decision, notes


def answer_notes(kind: str, decision: str, notes: str | None) -> str | None:
    """The answer's ``notes``. A no to a plan card starts with "reject", the
    word that stops the run (the Slack decline sends the same); without it a
    note would be read as a request to redraft."""
    if kind == PLAN and decision == "reject":
        return f"{PLAN_REJECT_WORD} {notes}" if notes else PLAN_REJECT_WORD
    return notes


def parse_approvers(text: str | None) -> dict[str, str]:
    """``<linear user id>=<identity>,…`` → a mapping.

    Raises:
        ValueError: an entry is not ``<id>=<identity>``.
    """
    found: dict[str, str] = {}
    for entry in (text or "").split(","):
        if not entry.strip():
            continue
        user, sep, identity = entry.partition("=")
        if not sep or not user.strip() or not identity.strip():
            raise ValueError("an entry is not <linear user id>=<identity>")
        found[user.strip()] = identity.strip()
    return found


# ---------------------------------------------------------------------------
# Slack notifications (visibility only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Notification:
    message_id: str
    correlation_id: str
    text: str


def parse_notification(data: bytes) -> Notification | None:
    """A ``jarvis.notification.slack`` message with a correlation id, or ``None``."""
    from nats_core import MessageEnvelope
    from nats_core.events import NotificationPayload
    from pydantic import ValidationError

    try:
        envelope = MessageEnvelope.model_validate_json(data)
        payload = NotificationPayload.model_validate(envelope.payload)
    except (ValidationError, ValueError):
        return None
    cid = payload.correlation_id or envelope.correlation_id
    if not cid or not payload.message.strip():
        return None
    return Notification(str(envelope.message_id), cid, payload.message.strip())


def notification_comment(note: Notification) -> str:
    quoted = "\n".join(f"> {line}".rstrip() for line in note.text.splitlines())
    return _finish([f"The factory said, in Slack:\n\n{quoted}"], None)


__all__ = [
    "ANSWER_IN_SLACK",
    "APPROVE_ENDING",
    "AUTH_CONFIRMATION",
    "MERGE",
    "MERGE_ENDING",
    "MISSION_PLAN",
    "NOT_LISTED",
    "OTHER",
    "OTHER_IN_SLACK",
    "PLAN",
    "SLACK_ONLY_ENDING",
    "Card",
    "Notification",
    "answer_notes",
    "card_comment",
    "card_kind",
    "https_link",
    "notification_comment",
    "parse_approvers",
    "parse_card",
    "parse_notification",
    "parse_reply",
    "recovered_card_comment",
]
