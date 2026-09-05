"""Per-assumption Block Kit decision dialogue for the Sovereign Planning Loop.

FEAT-SPL-003 (TASK-SPL003-J02 / J03a / J03b) — the **shared render/parse
contract** (arch F5/F6): the single source of truth for the dialogue block
encoding, so the J02 producer (``build_dialogue_blocks``) and the J03 consumer
(``parse_dialogue_blocks``) can never drift. A rendered Slack message *is* the
dialogue state (ADR-ARCH-004 — jarvis holds no pending-dialogue map); every
per-item disposition is re-derivable from the message alone, which is what makes
the dialogue survive a jarvis restart by construction.

The UX is load-bearing for WS4 (harvest: 0 'considered' across 31 sessions): a
planning checkpoint renders **one decidable item per assumption**, forced
per-item decisions, **no approve-all control anywhere** (scenario 15's
anti-rubber-stamp). The only whole-checkpoint control is the zero-assumption
case (nothing to decide per-item) and a whole-run *Cancel* abort in an overflow
menu (an abort, never a decision shortcut — ASSUM-011).

Block contract (§4 IMPLEMENTATION-GUIDE — the seam J03 re-derives from):

* Each assumption is TWO blocks sharing its ``assumption_id``:
  1. a ``section`` block, ``block_id == assumption_id`` — the human display
     (title, assumption text, confidence tag; a decision line once decided).
  2. a companion block that encodes the machine-readable state:
     * **undecided** → an ``actions`` block, ``block_id == f"{aid}::act"``, with
       exactly three buttons (``assumption_approve`` / ``assumption_edit`` /
       ``assumption_defer``). Each button ``value`` is compact JSON
       ``{correlation_id, request_id, assumption_id, cycle, approval_subject}``
       (< ``_SLACK_ACTION_VALUE_LIMIT``; carries ``approval_subject`` so J03a
       publishes to ``{approval_subject}.response`` — JNB-104 parity). The
       assumption TEXT is never in the value.
     * **decided** → a ``context`` block, ``block_id == f"{aid}::state"``,
       carrying a machine-readable state token
       (``spl3state:{"d":<disposition>,"e":<edit_delta>}``) alongside a human
       status element. This is how ``modified``/``edit_delta`` survives a later,
       possibly post-restart, decision on another item (arch F5 / red-team F9).
* ``parse_dialogue_blocks`` keys off the companion block's ``block_id`` suffix,
  never off human display strings.

Chunking: a checkpoint too large for one message (> ``_CHUNK_SIZE`` items) is
continued across messages in the same thread (ASSUM-009); no assumption is
dropped. NB — J03a derives checkpoint completeness from the single clicked
message (ADR-ARCH-004 forbids cross-message state), so the aggregate-publish
contract is exercised against single-message checkpoints; multi-chunk aggregate
publish is deferred to the forge half + J05 live validation.

No reasoning on this path — render proposals for decision only; jarvis never
poses a free-text question of its own (propose-never-elicit, SPL scope §3.3).

THE SPEC DIGEST CARD (machine chain, stage 2 — 2026-08-14)
----------------------------------------------------------
The same detection seam now carries a SECOND kind of planning card, and it is
the one the owner actually reads before a build is specified: the **spec
digest** — one plain sentence per worked example, plus the machine's
assumptions, with the worked examples themselves one click deeper behind a
button. Its ``checkpoint_type`` is ``product_docs_spec_digest``, which starts
with ``product_docs`` and therefore rides :func:`is_planning_checkpoint`
unchanged — that prefix is the only planning path proven answerable from Slack,
and inheriting it is deliberate rather than incidental.

Three things about it, each load-bearing:

* **It is a different card, not more assumption items.** The digest branch has
  its own blocks, its own controls and its own chunking (on worked-example
  count, never assumption count). Every OTHER ``checkpoint_type`` renders
  byte-for-byte what it rendered before.
* **The labels the spec wrote are rendered through an ALLOWLIST.** A label with
  a plain word gets the plain word; a label without one contributes NOTHING.
  Nothing is lost (the labels are in the spec, one click away) and the card can
  never be surprised by a label nobody has read.
* **The one tap can answer two questions.** When the spec tripped the sign-in
  scan, the card carries that question too, written as a statement the reader
  agrees or disagrees with. The answer travels as a per-item value in the
  wire's own ``dispositions`` field — the same encoding the assumption dialogue
  uses — so ordinary code reads it. The note channel says what the SPEC should
  say; it never carries this answer.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from jarvis.infrastructure.planning_notifier import post_threaded
from jarvis.infrastructure.spec_texts import SpecTextRegistry

if TYPE_CHECKING:  # pragma: no cover - typing only
    from jarvis.config.settings import JarvisConfig

logger = structlog.get_logger(__name__)

# Slack per-action value limit (mirrors slack_notifier._SLACK_ACTION_VALUE_LIMIT).
_SLACK_ACTION_VALUE_LIMIT = 2000

# Max per-assumption items per Slack message (ASSUM-009 chunk bound). A real
# manifest larger than this continues across messages in the same thread.
_CHUNK_SIZE = 8

# Dialogue-cycle cap: reaching this escalates to Rich instead of a fourth
# per-assumption cycle (frozen contract — cap-3 → escalate).
_CYCLE_CAP = 3

# The per-item decision action_ids (J03a routes on these; J03b opens the modal
# on ``assumption_edit``).
ACTION_APPROVE = "assumption_approve"
ACTION_EDIT = "assumption_edit"
ACTION_DEFER = "assumption_defer"
# Whole-run abort (overflow menu, ASSUM-011) — never a per-item decision.
ACTION_CANCEL = "planning_cancel"
# The single whole-checkpoint approval offered ONLY in the zero-assumption case.
ACTION_WHOLE_APPROVE = "planning_whole_approve"

# The set of dialogue action_ids J03a/J03b own (routing gate in slack_reply).
DIALOGUE_ACTION_IDS = frozenset(
    {ACTION_APPROVE, ACTION_EDIT, ACTION_DEFER, ACTION_CANCEL, ACTION_WHOLE_APPROVE}
)

# Sentinel assumption_id for the zero-assumption whole-checkpoint approval.
WHOLE_CHECKPOINT_ID = "__whole__"

# Companion-block block_id suffixes — the machine-readable state carriers.
_ACT_SUFFIX = "::act"
_STATE_SUFFIX = "::state"

# Machine-readable state-token prefix inside the decided item's context block.
_STATE_TOKEN_PREFIX = "spl3state:"

# Edit modal (TASK-SPL003-J03b) — callback + input identifiers.
EDIT_MODAL_CALLBACK_ID = "spl3_edit_modal"
_EDIT_INPUT_BLOCK = "spl3_edit_input"
_EDIT_INPUT_ACTION = "spl3_edit_value"

# ---------------------------------------------------------------------------
# Spec digest card (machine chain, stage 2) — identifiers
# ---------------------------------------------------------------------------

# The checkpoint discriminator forge stamps on a spec digest card. It starts
# with ``product_docs`` on purpose: that prefix is the ONE planning path proven
# answerable from Slack, so the digest inherits a working front door.
DIGEST_CHECKPOINT_TYPE = "product_docs_spec_digest"

# The digest card's controls.
ACTION_DIGEST_APPROVE = "digest_approve"
ACTION_DIGEST_NOTE = "digest_note"
ACTION_DIGEST_SHOW_SPEC = "digest_show_spec"
# The sign-in question's two answers (present only when the spec tripped the
# sign-in scan). Neither publishes — they record an answer ON the card, which
# the approve control then carries as a per-item disposition.
ACTION_DIGEST_SIGN_IN_AGREE = "digest_sign_in_agree"
ACTION_DIGEST_SIGN_IN_DISAGREE = "digest_sign_in_disagree"

# The set of digest action_ids the reply handler owns (routing gate).
DIGEST_ACTION_IDS = frozenset(
    {
        ACTION_DIGEST_APPROVE,
        ACTION_DIGEST_NOTE,
        ACTION_DIGEST_SHOW_SPEC,
        ACTION_DIGEST_SIGN_IN_AGREE,
        ACTION_DIGEST_SIGN_IN_DISAGREE,
    }
)

# The note modal (the red pen: a plain-English sentence, never an edit to the
# spec) and the read-only worked-examples view.
NOTE_MODAL_CALLBACK_ID = "spec_digest_note_modal"
SPEC_MODAL_CALLBACK_ID = "spec_digest_spec_modal"
_NOTE_INPUT_BLOCK = "spec_digest_note_input"
_NOTE_INPUT_ACTION = "spec_digest_note_value"

# Sentinel item id for the whole-card controls. Deliberately NOT suffixed
# ``::act``, so the card's own buttons never read back as a decidable item.
DIGEST_CARD_ID = "__digest__"

# The default id of the sign-in answer. The card names its own
# (``sign_in_check.answer_id``) and that is what travels; this is the fallback
# for a card that omits it.
DEFAULT_SIGN_IN_ITEM_ID = "sign-in"

# Max worked examples per Slack message. The digest chunks on EXAMPLES, not
# assumptions — a wide spec is wide in its examples.
_DIGEST_CHUNK_SIZE = 8

# Slack's per-section text ceiling is 3000 characters; the read-only worked
# examples view chunks well inside it, and stops at a bounded number of chunks
# so a runaway spec cannot exceed Slack's 100-block modal limit.
_SPEC_MODAL_CHUNK_CHARS = 2800
_SPEC_MODAL_MAX_CHUNKS = 40

# The label allowlist (2026-08-14 card ruling). A label maps to the words a
# person reads, or it contributes NOTHING to the card. Composed at the render
# site — deterministic, no runtime model.
_TAG_WORDS: dict[str, str] = {
    "key-example": "the main one",
    "smoke": "checked after every deploy",
    "negative": "a refusal case",
    "edge-case": "an awkward case",
}

# The value-JSON keys (ITEM_ACTION_VALUE contract, §4).
_VALUE_KEYS = ("correlation_id", "request_id", "assumption_id", "cycle", "approval_subject")


# ---------------------------------------------------------------------------
# Detection (ASSUM-002 — by checkpoint_type, NEVER by parsing the run-id shape)
# ---------------------------------------------------------------------------


def is_planning_checkpoint(details: dict[str, Any] | None) -> bool:
    """True when ``details`` is a Mode P planning-assumption checkpoint.

    Detection is by ``details.checkpoint_type`` starting with ``product_docs``
    (ASSUM-002) — never by parsing ``plan-<cid>`` out of a subject. A missing or
    empty ``checkpoint_type`` is not a planning checkpoint.
    """
    if not isinstance(details, dict):
        return False
    checkpoint_type = str(details.get("checkpoint_type") or "")
    return checkpoint_type.startswith("product_docs")


def is_spec_digest(details: dict[str, Any] | None) -> bool:
    """True when ``details`` is a spec digest card (machine chain, stage 2).

    Exact equality on ``checkpoint_type`` — a prefix test would swallow any
    future ``product_docs_*`` card into the digest renderer, and a card whose
    shape nobody has read must never be rendered as if it were this one.
    """
    if not isinstance(details, dict):
        return False
    return str(details.get("checkpoint_type") or "") == DIGEST_CHECKPOINT_TYPE


def digest_card(details: dict[str, Any]) -> dict[str, Any]:
    """The digest card body, or an empty dict.

    Forge composes the card and it rides the approval envelope under
    ``details.summary`` (the envelope's one place for a validated body).
    Defensive: a missing or malformed summary yields ``{}``, which renders a
    card that says plainly it has nothing to show rather than crashing.
    """
    summary = details.get("summary")
    return summary if isinstance(summary, dict) else {}


def _digest_examples(card: dict[str, Any]) -> list[dict[str, Any]]:
    """The worked-example sentences on the card, in the order the spec has them."""
    examples = card.get("what_it_will_do")
    if not isinstance(examples, list):
        return []
    return [e for e in examples if isinstance(e, dict)]


def _digest_assumptions(card: dict[str, Any]) -> list[dict[str, Any]]:
    """The spec's own assumptions, each with the reason it was made."""
    assumptions = card.get("what_the_machine_assumed")
    if not isinstance(assumptions, list):
        return []
    return [a for a in assumptions if isinstance(a, dict)]


def _sign_in_check(card: dict[str, Any]) -> dict[str, Any] | None:
    """The sign-in question, when this spec tripped the scan; else ``None``."""
    check = card.get("sign_in_check")
    return check if isinstance(check, dict) and check else None


def sign_in_item_id(card: dict[str, Any]) -> str:
    """The id the sign-in answer travels under on the wire."""
    check = _sign_in_check(card) or {}
    return str(check.get("answer_id") or DEFAULT_SIGN_IN_ITEM_ID)


def is_escalated(details: dict[str, Any]) -> bool:
    """True when this checkpoint should escalate to Rich (ASSUM-012).

    Escalation fires when forge marks the checkpoint escalated
    (``checkpoint_type == "product_docs_escalated"``) OR the cycle cap is
    reached (``attempt_count`` >= :data:`_CYCLE_CAP`). The escalated prompt
    re-renders the full item list addressed to Rich — it is never a fourth
    per-assumption dialogue cycle.
    """
    if str(details.get("checkpoint_type") or "") == "product_docs_escalated":
        return True
    try:
        return int(details.get("attempt_count") or 0) >= _CYCLE_CAP
    except (TypeError, ValueError):
        return False


def _assumptions(details: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the assumption list from ``details.summary.assumptions``.

    Defensive: a missing/malformed summary yields an empty list (a
    zero-assumption checkpoint, not a crash).
    """
    summary = details.get("summary")
    if not isinstance(summary, dict):
        return []
    assumptions = summary.get("assumptions")
    if not isinstance(assumptions, list):
        return []
    return [a for a in assumptions if isinstance(a, dict) and a.get("id")]


def chunk_count_for(details: dict[str, Any]) -> int:
    """Number of Slack messages this checkpoint renders across (>= 1).

    A spec digest chunks on WORKED EXAMPLES (the thing the reader is reading);
    every other checkpoint chunks on assumptions, exactly as before.
    """
    if is_spec_digest(details):
        n = len(_digest_examples(digest_card(details)))
        if n <= 0:
            return 1
        return (n + _DIGEST_CHUNK_SIZE - 1) // _DIGEST_CHUNK_SIZE
    n = len(_assumptions(details))
    if n <= 0:
        return 1
    return (n + _CHUNK_SIZE - 1) // _CHUNK_SIZE


# ---------------------------------------------------------------------------
# Value + state-token encode/decode (the §4 contract, encode side)
# ---------------------------------------------------------------------------


def build_item_value(
    *,
    correlation_id: str | None,
    request_id: str,
    assumption_id: str,
    cycle: Any,
    approval_subject: str,
) -> str:
    """Compact JSON button ``value`` for one item (< 2000 chars, guarded).

    Carries only routing identifiers — never the assumption text (§4). The
    length guard mirrors ``slack_notifier._build_button_value``; an oversized
    value (only reachable with a pathological correlation/subject) logs and
    still returns the JSON so the click remains routable.
    """
    value = json.dumps(
        {
            "correlation_id": correlation_id or "",
            "request_id": request_id,
            "assumption_id": assumption_id,
            "cycle": cycle,
            "approval_subject": approval_subject,
        },
        separators=(",", ":"),
    )
    if len(value) >= _SLACK_ACTION_VALUE_LIMIT:
        logger.warning(
            "assumption_dialogue_value_oversized",
            assumption_id=assumption_id,
            length=len(value),
            limit=_SLACK_ACTION_VALUE_LIMIT,
        )
    return value


def parse_item_value(value: str) -> dict[str, Any]:
    """Decode + validate a dialogue button ``value`` (the §4 decode side).

    The inverse of :func:`build_item_value`. ``request_id`` and
    ``approval_subject`` are load-bearing (publish routing) and must be
    non-empty strings.

    Raises:
        ValueError: on unparseable JSON, a non-object, missing keys, or empty
            load-bearing fields. J03a/J03b catch this and drop the click
            (DDR-007) — it never propagates.
    """
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"dialogue value is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("dialogue value JSON is not an object")

    missing = [k for k in _VALUE_KEYS if k not in parsed]
    if missing:
        raise ValueError(f"dialogue value JSON missing keys: {missing}")

    result = {k: parsed[k] for k in _VALUE_KEYS}
    for load_bearing in ("request_id", "approval_subject"):
        field = result[load_bearing]
        if not isinstance(field, str) or not field:
            raise ValueError(f"dialogue value field {load_bearing!r} must be a non-empty string")
    return result


def _encode_state(disposition: str, edit_delta: str | None) -> str:
    """Encode a decided item's machine-readable state token."""
    return _STATE_TOKEN_PREFIX + json.dumps(
        {"d": disposition, "e": edit_delta}, separators=(",", ":")
    )


def _decode_state(text: str) -> tuple[str, str | None]:
    """Decode a state token → (disposition, edit_delta); defensive on garbage."""
    try:
        raw = text[len(_STATE_TOKEN_PREFIX) :]
        parsed = json.loads(raw)
        disposition = str(parsed.get("d") or "undecided")
        edit_delta = parsed.get("e")
        if edit_delta is not None:
            edit_delta = str(edit_delta)
        return disposition, edit_delta
    except (ValueError, TypeError, AttributeError):
        return "undecided", None


# ---------------------------------------------------------------------------
# Block builders (encode side)
# ---------------------------------------------------------------------------


def _confidence_line(assumption: dict[str, Any]) -> str:
    confidence = str(assumption.get("confidence") or "unspecified")
    basis = assumption.get("basis")
    line = f"_confidence: {confidence}_"
    if basis:
        line += f" · _basis: {basis}_"
    return line


def _section_block(
    assumption: dict[str, Any], *, decision_line: str | None = None
) -> dict[str, Any]:
    aid = str(assumption["id"])
    text = str(assumption.get("text") or "")
    body = f"*{aid}*\n{text}\n{_confidence_line(assumption)}"
    if decision_line:
        body += f"\n{decision_line}"
    return {
        "type": "section",
        "block_id": aid,
        "text": {"type": "mrkdwn", "text": body},
    }


def _actions_block(aid: str, value: str) -> dict[str, Any]:
    """The three per-item decision buttons (undecided state)."""
    return {
        "type": "actions",
        "block_id": f"{aid}{_ACT_SUFFIX}",
        "elements": [
            {
                "type": "button",
                "action_id": ACTION_APPROVE,
                "text": {"type": "plain_text", "text": "Approve", "emoji": False},
                "style": "primary",
                "value": value,
            },
            {
                "type": "button",
                "action_id": ACTION_EDIT,
                "text": {"type": "plain_text", "text": "Edit", "emoji": False},
                "value": value,
            },
            {
                "type": "button",
                "action_id": ACTION_DEFER,
                "text": {"type": "plain_text", "text": "Defer", "emoji": False},
                "value": value,
            },
        ],
    }


def _state_block(aid: str, disposition: str, edit_delta: str | None) -> dict[str, Any]:
    """The decided-item companion block (machine state + human status)."""
    human = f"Decision recorded: *{disposition}*"
    if edit_delta:
        human += f" — {edit_delta}"
    return {
        "type": "context",
        "block_id": f"{aid}{_STATE_SUFFIX}",
        "elements": [
            {"type": "mrkdwn", "text": human},
            {"type": "mrkdwn", "text": _encode_state(disposition, edit_delta)},
        ],
    }


def _item_blocks(
    assumption: dict[str, Any],
    *,
    value: str,
    disposition: str = "undecided",
    edit_delta: str | None = None,
) -> list[dict[str, Any]]:
    """The two blocks for one assumption item (section + companion)."""
    aid = str(assumption["id"])
    if disposition == "undecided":
        return [_section_block(assumption), _actions_block(aid, value)]
    decision_line = f"*Decision:* {disposition}" + (f" — {edit_delta}" if edit_delta else "")
    return [
        _section_block(assumption, decision_line=decision_line),
        _state_block(aid, disposition, edit_delta),
    ]


def _header_blocks(
    details: dict[str, Any], *, chunk_index: int, chunk_count: int
) -> list[dict[str, Any]]:
    cycle = details.get("cycle")
    escalated = is_escalated(details)
    approver = details.get("expected_approver")

    if escalated:
        mention = f"<@{approver}> " if approver else ""
        headline = (
            f"{mention}*Planning checkpoint escalated to Rich* "
            f"(cycle {cycle}, attempt {details.get('attempt_count')})"
        )
    else:
        headline = f"*Planning assumptions — please decide each item* (cycle {cycle})"

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "block_id": "spl3hdr",
            "text": {"type": "mrkdwn", "text": headline},
        }
    ]
    if chunk_count > 1:
        blocks.append(
            {
                "type": "context",
                "block_id": "spl3chunk",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"continued ({chunk_index + 1}/{chunk_count})",
                    }
                ],
            }
        )
    return blocks


def build_dialogue_blocks(
    details: dict[str, Any],
    *,
    correlation_id: str | None,
    request_id: str,
    approval_subject: str,
    chunk_index: int = 0,
    chunk_count: int = 1,
) -> list[dict[str, Any]]:
    """Build the Block Kit blocks for one message (chunk) of a checkpoint.

    One decidable item per assumption in this chunk; header addressed to Rich
    when escalated. The zero-assumption case (only ``chunk_index == 0``) renders
    a single whole-checkpoint approval — the only one-control case (ASSUM-006).

    Args:
        details: The forge ``ApprovalRequestPayload.details`` (see §4 fixture).
        correlation_id / request_id / approval_subject: Routing identifiers
            carried into every button ``value`` (never the assumption text).
        chunk_index / chunk_count: Which message of the checkpoint this is.

    Returns:
        The blocks for this chunk (a whole Slack message).
    """
    if is_spec_digest(details):
        return build_digest_blocks(
            details,
            correlation_id=correlation_id,
            request_id=request_id,
            approval_subject=approval_subject,
            chunk_index=chunk_index,
            chunk_count=chunk_count,
        )

    blocks = _header_blocks(details, chunk_index=chunk_index, chunk_count=chunk_count)
    assumptions = _assumptions(details)
    cycle = details.get("cycle")

    if not assumptions:
        # Zero-assumption checkpoint: a single whole-checkpoint approval — the
        # ONLY case with one control (ASSUM-006). Never an approve-all over items.
        value = build_item_value(
            correlation_id=correlation_id,
            request_id=request_id,
            assumption_id=WHOLE_CHECKPOINT_ID,
            cycle=cycle,
            approval_subject=approval_subject,
        )
        blocks.append(
            {
                "type": "section",
                "block_id": "spl3whole",
                "text": {
                    "type": "mrkdwn",
                    "text": "This checkpoint proposes no assumptions to decide.",
                },
            }
        )
        blocks.append(
            {
                "type": "actions",
                "block_id": f"{WHOLE_CHECKPOINT_ID}{_ACT_SUFFIX}",
                "elements": [
                    {
                        "type": "button",
                        "action_id": ACTION_WHOLE_APPROVE,
                        "text": {
                            "type": "plain_text",
                            "text": "Approve checkpoint",
                            "emoji": False,
                        },
                        "style": "primary",
                        "value": value,
                    }
                ],
            }
        )
        return blocks

    start = chunk_index * _CHUNK_SIZE
    for assumption in assumptions[start : start + _CHUNK_SIZE]:
        aid = str(assumption["id"])
        value = build_item_value(
            correlation_id=correlation_id,
            request_id=request_id,
            assumption_id=aid,
            cycle=cycle,
            approval_subject=approval_subject,
        )
        blocks.extend(_item_blocks(assumption, value=value))

    # Whole-run abort (never a per-item decision, never approve-all): an
    # overflow menu with a single Cancel option (ASSUM-011). Only on the last
    # chunk so it appears once.
    if chunk_index == chunk_count - 1 and assumptions:
        first_value = build_item_value(
            correlation_id=correlation_id,
            request_id=request_id,
            assumption_id=WHOLE_CHECKPOINT_ID,
            cycle=cycle,
            approval_subject=approval_subject,
        )
        blocks.append(
            {
                "type": "actions",
                "block_id": "spl3cancel::act",
                "elements": [
                    {
                        "type": "overflow",
                        "action_id": ACTION_CANCEL,
                        "options": [
                            {
                                "text": {
                                    "type": "plain_text",
                                    "text": "Cancel planning run",
                                    "emoji": False,
                                },
                                "value": first_value,
                            }
                        ],
                    }
                ],
            }
        )
    return blocks


# ---------------------------------------------------------------------------
# The spec digest card (machine chain, stage 2)
# ---------------------------------------------------------------------------


def tag_words(tags: Any) -> list[str]:
    """The plain words for a worked example's labels — allowlist only.

    A label with a plain word renders that word; a label without one renders
    NOTHING. That is the whole rule, and it is an allowlist rather than a
    translation table on purpose: a spec is free to carry internal labels
    (task ids, codenames, whatever a run needs), and a card that rendered them
    verbatim would put words on the owner's surface that nobody had read.
    Nothing is lost — the labels are in the spec, one click deeper.
    """
    words: list[str] = []
    for raw in tags or []:
        word = _TAG_WORDS.get(str(raw).lstrip("@").strip().lower())
        if word and word not in words:
            words.append(word)
    return words


def _digest_header_blocks(
    card: dict[str, Any], *, chunk_index: int, chunk_count: int
) -> list[dict[str, Any]]:
    title = str(card.get("title") or "The spec is ready — here's what will be built")
    feature = str(card.get("feature") or "").strip()
    repo = str(card.get("target_repo") or "").strip()
    headline = f"*{title}*"
    if feature:
        headline += f"\n_Feature: {feature}_"
    # The repository this will be built in, when the forge told us which
    # (binding spec 2026-09-05, rule 5). An older forge sends no such field,
    # and the card then renders byte-for-byte as it did before.
    if repo:
        headline += f"\n_Repo: {repo}_"
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "block_id": "digesthdr",
            "text": {"type": "mrkdwn", "text": headline},
        }
    ]
    if chunk_count > 1:
        blocks.append(
            {
                "type": "context",
                "block_id": "digestchunk",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"continued ({chunk_index + 1}/{chunk_count})",
                    }
                ],
            }
        )
    if chunk_index == 0:
        what_happened = str(card.get("what_happened") or "")
        if what_happened:
            blocks.append(
                {
                    "type": "section",
                    "block_id": "digestwhy",
                    "text": {"type": "mrkdwn", "text": what_happened},
                }
            )
    return blocks


def _digest_example_blocks(
    examples: list[dict[str, Any]], *, start: int
) -> list[dict[str, Any]]:
    """One block per worked example: its number, its sentence, its plain labels."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "block_id": f"digestdo{start}",
            "text": {"type": "mrkdwn", "text": "*What it will do*"},
        }
    ]
    for offset, example in enumerate(examples):
        index = start + offset
        sentence = str(example.get("sentence") or "")
        words = tag_words(example.get("tags"))
        body = f"`{index + 1}.`  {sentence}"
        if words:
            body += f"\n_({' · '.join(words)})_"
        blocks.append(
            {
                "type": "section",
                "block_id": f"digestex{index}",
                "text": {"type": "mrkdwn", "text": body},
            }
        )
    return blocks


def _digest_assumption_blocks(card: dict[str, Any]) -> list[dict[str, Any]]:
    """The spec's assumptions, each with the reason it was made.

    The reason is half the decision: "the input did not say" and "confirmed
    with the operations team" call for very different answers, and showing only
    the assumption hides that.
    """
    assumptions = _digest_assumptions(card)
    if not assumptions:
        return [
            {
                "type": "context",
                "block_id": "digestnoassum",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The spec makes no assumptions of its own.",
                    }
                ],
            }
        ]
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "block_id": "digestassum",
            "text": {"type": "mrkdwn", "text": "*What the machine assumed*"},
        }
    ]
    for index, entry in enumerate(assumptions):
        text = str(entry.get("assumption") or "")
        why = str(entry.get("why") or "")
        body = f"`{index + 1}.`  {text}"
        if why:
            body += f"\n_Why: {why}_"
        blocks.append(
            {
                "type": "section",
                "block_id": f"digestassum{index}",
                "text": {"type": "mrkdwn", "text": body},
            }
        )
    return blocks


def _sign_in_state_block(item_id: str, disposition: str) -> dict[str, Any]:
    """The answered sign-in question — plain words for a reader, a token for code.

    Reuses the dialogue's ``::state`` companion-block encoding, so
    :func:`parse_dialogue_blocks` decodes this answer through the one decode
    path that already exists. The human half is written in the owner's own
    terms rather than the wire's vocabulary; nothing reads it.
    """
    if disposition == "accepted":
        human = "You said: nothing here involves signing in."
    elif disposition == "rejected":
        human = "You said: this really does involve signing in."
    else:
        human = f"Answer recorded: {disposition}"
    return {
        "type": "context",
        "block_id": f"{item_id}{_STATE_SUFFIX}",
        "elements": [
            {"type": "mrkdwn", "text": human},
            {"type": "mrkdwn", "text": _encode_state(disposition, None)},
        ],
    }


def _sign_in_blocks(card: dict[str, Any], *, value: str) -> list[dict[str, Any]]:
    """The sign-in question, asked on the card the spec is already in front of."""
    check = _sign_in_check(card)
    if check is None:
        return []
    item_id = sign_in_item_id(card)
    lines = [f"*{check.get('title') or 'One thing to confirm'}*"]
    statement = str(check.get("statement") or "")
    if statement:
        lines.append(f"> {statement}")
    body = str(check.get("body") or "")
    if body:
        lines.append(body)
    flagged = [str(line) for line in (check.get("flagged_lines") or [])]
    if flagged:
        lines.append("What made us ask:")
        lines.extend(f"• {line}" for line in flagged)
    why = str(check.get("why_we_ask") or "")
    if why:
        lines.append(f"_{why}_")

    blocks: list[dict[str, Any]] = [
        {"type": "divider", "block_id": "signindiv"},
        {
            "type": "section",
            "block_id": item_id,
            "text": {"type": "mrkdwn", "text": "\n".join(lines)},
        },
    ]
    meanings = [
        str(check.get(key) or "")
        for key in ("agree_means", "disagree_means", "no_answer_means")
    ]
    meanings = [m for m in meanings if m]
    if meanings:
        blocks.append(
            {
                "type": "context",
                "block_id": "signinmeans",
                "elements": [{"type": "mrkdwn", "text": m} for m in meanings],
            }
        )
    blocks.append(
        {
            "type": "actions",
            "block_id": f"{item_id}{_ACT_SUFFIX}",
            "elements": [
                {
                    "type": "button",
                    "action_id": ACTION_DIGEST_SIGN_IN_AGREE,
                    "text": {
                        "type": "plain_text",
                        "text": "Agree — no signing in here",
                        "emoji": False,
                    },
                    "value": value,
                },
                {
                    "type": "button",
                    "action_id": ACTION_DIGEST_SIGN_IN_DISAGREE,
                    "text": {
                        "type": "plain_text",
                        "text": "Disagree — it does involve signing in",
                        "emoji": False,
                    },
                    "value": value,
                },
            ],
        }
    )
    return blocks


def _digest_control_blocks(card: dict[str, Any], *, value: str) -> list[dict[str, Any]]:
    """The three controls, and the fine print that tells the truth about them.

    The primary control says what saying yes actually does. It does NOT start a
    build — the machine writes the task plan and the quality checklist and comes
    back for the go-ahead — and a button that misnamed its own consequence would
    be an approval-surface defect, not a wording nit.
    """
    blocks: list[dict[str, Any]] = [
        {"type": "divider", "block_id": "digestdiv"},
        {
            "type": "actions",
            # Deliberately NOT ``::act``-suffixed: these are the card's own
            # controls, never a decidable item.
            "block_id": "digestctl",
            "elements": [
                {
                    "type": "button",
                    "action_id": ACTION_DIGEST_APPROVE,
                    "text": {
                        "type": "plain_text",
                        "text": "Yes — this is what I want built",
                        "emoji": False,
                    },
                    "style": "primary",
                    "value": value,
                },
                {
                    "type": "button",
                    "action_id": ACTION_DIGEST_NOTE,
                    "text": {"type": "plain_text", "text": "Send a note", "emoji": False},
                    "value": value,
                },
                {
                    "type": "button",
                    "action_id": ACTION_DIGEST_SHOW_SPEC,
                    "text": {
                        "type": "plain_text",
                        "text": "Show the worked examples",
                        "emoji": False,
                    },
                    "value": value,
                },
            ],
        },
    ]
    fine_print = [
        str(card.get(key) or "")
        for key in ("approve_means", "note_means", "show_means", "no_answer_means")
    ]
    fine_print = [line for line in fine_print if line]
    if fine_print:
        blocks.append(
            {
                "type": "context",
                "block_id": "digestfine",
                "elements": [{"type": "mrkdwn", "text": line} for line in fine_print],
            }
        )
    return blocks


def build_digest_blocks(
    details: dict[str, Any],
    *,
    correlation_id: str | None,
    request_id: str,
    approval_subject: str,
    chunk_index: int = 0,
    chunk_count: int = 1,
) -> list[dict[str, Any]]:
    """Build one message of the spec digest card.

    One sentence per worked example, numbered, in the spec's own order; then the
    spec's assumptions with their reasons; then the sign-in question if this
    spec raised one; then the three controls. The worked examples themselves are
    never on this surface — they sit behind "Show the worked examples", which is
    the whole point of the digest.

    The assumptions, the sign-in question and the controls ride the LAST chunk,
    so they appear exactly once however wide the spec is.
    """
    card = digest_card(details)
    examples = _digest_examples(card)
    cycle = details.get("cycle")

    blocks = _digest_header_blocks(card, chunk_index=chunk_index, chunk_count=chunk_count)

    start = chunk_index * _DIGEST_CHUNK_SIZE
    window = examples[start : start + _DIGEST_CHUNK_SIZE]
    if window:
        blocks.extend(_digest_example_blocks(window, start=start))
    elif chunk_index == 0:
        blocks.append(
            {
                "type": "section",
                "block_id": "digestnoex",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "This card arrived with no worked examples on it. "
                        "Nothing has been built; send a note and the machine "
                        "will write the spec again."
                    ),
                },
            }
        )

    if chunk_index != chunk_count - 1:
        return blocks

    value = build_item_value(
        correlation_id=correlation_id,
        request_id=request_id,
        assumption_id=DIGEST_CARD_ID,
        cycle=cycle,
        approval_subject=approval_subject,
    )
    blocks.extend(_digest_assumption_blocks(card))
    sign_in = _sign_in_check(card)
    if sign_in is not None:
        item_id = sign_in_item_id(card)
        blocks.extend(
            _sign_in_blocks(
                card,
                value=build_item_value(
                    correlation_id=correlation_id,
                    request_id=request_id,
                    assumption_id=item_id,
                    cycle=cycle,
                    approval_subject=approval_subject,
                ),
            )
        )
    blocks.extend(_digest_control_blocks(card, value=value))
    return blocks


def apply_sign_in_answer(
    message_blocks: list[dict[str, Any]], *, item_id: str, disposition: str
) -> list[dict[str, Any]]:
    """Return a copy of the card with the sign-in question answered.

    The question's ``actions`` (or prior ``state``) companion block becomes a
    ``state`` block carrying the answer; every other block is preserved exactly,
    so the card's own controls stay live — answering the sign-in question is not
    answering the card.
    """
    act_id = f"{item_id}{_ACT_SUFFIX}"
    state_id = f"{item_id}{_STATE_SUFFIX}"
    updated: list[dict[str, Any]] = []
    for block in message_blocks:
        bid = str(block.get("block_id") or "")
        if bid in (act_id, state_id):
            updated.append(_sign_in_state_block(item_id, disposition))
        else:
            updated.append(block)
    return updated


def build_note_modal(*, private_metadata: str) -> dict[str, Any]:
    """The modal that collects the owner's note — plain English, required.

    The red pen is a sentence, never an edit to the spec: the machine rewrites
    the spec from what is typed here and comes back with a fresh list. The input
    is required, so an empty note cannot be sent from this surface.
    """
    return {
        "type": "modal",
        "callback_id": NOTE_MODAL_CALLBACK_ID,
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "Send a note", "emoji": False},
        "submit": {"type": "plain_text", "text": "Send", "emoji": False},
        "close": {"type": "plain_text", "text": "Cancel", "emoji": False},
        "blocks": [
            {
                "type": "input",
                "block_id": _NOTE_INPUT_BLOCK,
                "label": {
                    "type": "plain_text",
                    "text": "What should be different?",
                    "emoji": False,
                },
                "hint": {
                    "type": "plain_text",
                    "text": (
                        "Say it however you would say it out loud. The machine "
                        "rewrites the spec from this and comes back with a "
                        "fresh list."
                    ),
                    "emoji": False,
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": _NOTE_INPUT_ACTION,
                    "multiline": True,
                },
            }
        ],
    }


def read_note_submission(view: dict[str, Any]) -> str:
    """Extract the owner's note from a ``view_submission`` view."""
    values = (view.get("state") or {}).get("values") or {}
    block = values.get(_NOTE_INPUT_BLOCK) or {}
    element = block.get(_NOTE_INPUT_ACTION) or {}
    return str(element.get("value") or "")


def chunk_spec_text(text: str) -> tuple[list[str], bool]:
    """Split the worked examples for display; report whether any was dropped.

    Returns ``(chunks, truncated)``. Truncation is ANNOUNCED by the caller
    rather than silent: a reader who cannot tell that a view stopped early
    cannot trust what it showed them.
    """
    body = text or ""
    chunks: list[str] = []
    for start in range(0, len(body), _SPEC_MODAL_CHUNK_CHARS):
        if len(chunks) == _SPEC_MODAL_MAX_CHUNKS:
            return chunks, True
        chunks.append(body[start : start + _SPEC_MODAL_CHUNK_CHARS])
    return chunks, False


def build_spec_modal(*, feature: str, spec_text: str) -> dict[str, Any]:
    """The read-only view of the worked examples — one click deeper, never the ask.

    No ``submit`` key: there is nothing to decide in here. The examples are the
    spec's OWN words, rendered verbatim and deliberately unscrubbed — this is
    the one surface where that is right, because its entire value is showing
    exactly what was written. Every other string on the digest card is composed
    by jarvis and is checked by the plain-name fence.
    """
    title = "The worked examples"
    blocks: list[dict[str, Any]] = []
    if feature:
        blocks.append(
            {
                "type": "context",
                "block_id": "specmodalfeat",
                "elements": [{"type": "mrkdwn", "text": f"_Feature: {feature}_"}],
            }
        )
    if not (spec_text or "").strip():
        blocks.append(
            {
                "type": "section",
                "block_id": "specmodalempty",
                "text": {
                    "type": "plain_text",
                    "text": (
                        "The worked examples are not on this card. They are on "
                        "the run's own branch."
                    ),
                    "emoji": False,
                },
            }
        )
        return _spec_modal(title, blocks)

    chunks, truncated = chunk_spec_text(spec_text)
    for index, chunk in enumerate(chunks):
        blocks.append(
            {
                "type": "section",
                "block_id": f"specmodal{index}",
                "text": {"type": "plain_text", "text": chunk, "emoji": False},
            }
        )
    if truncated:
        shown = sum(len(chunk) for chunk in chunks)
        blocks.append(
            {
                "type": "context",
                "block_id": "specmodalmore",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Showing the first {shown} characters of "
                            f"{len(spec_text)}. The rest is on the run's own "
                            "branch — nothing has been left out of the list on "
                            "the card."
                        ),
                    }
                ],
            }
        )
    return _spec_modal(title, blocks)


def _spec_modal(title: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "modal",
        "callback_id": SPEC_MODAL_CALLBACK_ID,
        "title": {"type": "plain_text", "text": title, "emoji": False},
        "close": {"type": "plain_text", "text": "Close", "emoji": False},
        "blocks": blocks,
    }


def build_spec_unavailable_modal() -> dict[str, Any]:
    """The honest answer when the worked examples are no longer to hand.

    The examples are held in memory between rendering the card and a click on
    it; a restart empties that (the same in-process posture every other jarvis
    map has). Saying so is the whole behaviour — the card's list is unaffected,
    and it is the list that was checked against the spec.
    """
    return _spec_modal(
        "The worked examples",
        [
            {
                "type": "section",
                "block_id": "specmodalgone",
                "text": {
                    "type": "plain_text",
                    "text": (
                        "The worked examples are no longer to hand — they are "
                        "on the run's own branch. The list on the card is "
                        "unchanged, and it is checked against the examples."
                    ),
                    "emoji": False,
                },
            }
        ],
    )


# ---------------------------------------------------------------------------
# parse_dialogue_blocks (decode side — the J03 consumer of the §4 contract)
# ---------------------------------------------------------------------------


def parse_dialogue_blocks(
    message_blocks: list[Any] | None,
) -> dict[str, dict[str, Any]]:
    """Re-derive per-item disposition state from a rendered dialogue message.

    Returns ``{assumption_id: {"disposition": str, "edit_delta": str | None}}``
    for every per-assumption item present in the message. Keys off the companion
    block's ``block_id`` suffix (``::act`` = undecided, ``::state`` = decided) —
    NEVER off human display text (arch F5). The ``__whole__`` sentinel item and
    the cancel-overflow block are excluded from the item map.

    This is the single decode point J03a/J03b use to re-derive state from the
    authoritative message (ADR-ARCH-004) — the dialogue survives a restart
    because the state lives here, not in jarvis memory.
    """
    result: dict[str, dict[str, Any]] = {}
    if not message_blocks:
        return result

    for block in message_blocks:
        if not isinstance(block, dict):
            continue
        bid = str(block.get("block_id") or "")

        if bid.endswith(_ACT_SUFFIX):
            aid = bid[: -len(_ACT_SUFFIX)]
            if aid in (WHOLE_CHECKPOINT_ID, "spl3cancel"):
                continue
            # Decided state (::state) wins if it also appears; don't overwrite it.
            result.setdefault(aid, {"disposition": "undecided", "edit_delta": None})
        elif bid.endswith(_STATE_SUFFIX):
            aid = bid[: -len(_STATE_SUFFIX)]
            if aid == WHOLE_CHECKPOINT_ID:
                continue
            disposition, edit_delta = _read_state_token(block)
            result[aid] = {"disposition": disposition, "edit_delta": edit_delta}

    return result


def _read_state_token(block: dict[str, Any]) -> tuple[str, str | None]:
    for element in block.get("elements") or []:
        if not isinstance(element, dict):
            continue
        text = str(element.get("text") or "")
        if text.startswith(_STATE_TOKEN_PREFIX):
            return _decode_state(text)
    return "undecided", None


def apply_disposition(
    message_blocks: list[dict[str, Any]],
    *,
    assumption_id: str,
    disposition: str,
    edit_delta: str | None = None,
) -> list[dict[str, Any]]:
    """Return a copy of ``message_blocks`` with one item flipped to decided.

    The clicked item's ``actions`` (or prior ``state``) companion block is
    replaced with a fresh ``state`` block carrying ``disposition``/``edit_delta``
    (machine-readable), and its ``section`` gains a human decision line. Every
    other block — and thus every other item's disposition — is preserved exactly
    (arch F5). This is the whole-message rebuild J03a hands to ``chat.update``.
    """
    act_id = f"{assumption_id}{_ACT_SUFFIX}"
    state_id = f"{assumption_id}{_STATE_SUFFIX}"
    decision_line = f"*Decision:* {disposition}" + (f" — {edit_delta}" if edit_delta else "")

    updated: list[dict[str, Any]] = []
    for block in message_blocks:
        bid = str(block.get("block_id") or "")
        if bid == assumption_id and block.get("type") == "section":
            new_section = json.loads(json.dumps(block))  # deep copy
            base_text = str((new_section.get("text") or {}).get("text") or "")
            # Strip any prior decision line before re-appending (idempotent).
            base_text = base_text.split("\n*Decision:*")[0]
            new_section.setdefault("text", {})["text"] = f"{base_text}\n{decision_line}"
            updated.append(new_section)
        elif bid in (act_id, state_id):
            updated.append(_state_block(assumption_id, disposition, edit_delta))
        else:
            updated.append(block)
    return updated


def extract_assumption_text(message_blocks: list[Any] | None, assumption_id: str) -> str:
    """Recover an assumption's proposed text from its rendered section block.

    Used by J03b to prefill the edit modal. The section (``block_id ==
    assumption_id``) renders ``*{aid}*\\n{text}\\n_confidence: …_`` plus an
    optional ``*Decision:* …`` line; this strips the title, confidence, and any
    decision line, returning the middle proposal text. Empty string if absent.
    """
    for block in message_blocks or []:
        if not isinstance(block, dict):
            continue
        if block.get("block_id") == assumption_id and block.get("type") == "section":
            text = str((block.get("text") or {}).get("text") or "")
            lines = text.split("\n")
            body = [
                ln
                for ln in lines[1:]
                if not ln.startswith("_confidence:") and not ln.startswith("*Decision:*")
            ]
            return "\n".join(body).strip()
    return ""


def build_edit_modal(
    *, assumption_id: str, prefill: str, private_metadata: str
) -> dict[str, Any]:
    """The Slack modal view for editing one assumption (TASK-SPL003-J03b).

    ``private_metadata`` (a JSON string) carries the routing identifiers +
    ``channel``/``message_ts`` so the submission can locate and update the
    originating message. Prefilled with the assumption's proposed text.
    """
    return {
        "type": "modal",
        "callback_id": EDIT_MODAL_CALLBACK_ID,
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "Edit assumption", "emoji": False},
        "submit": {"type": "plain_text", "text": "Save", "emoji": False},
        "close": {"type": "plain_text", "text": "Cancel", "emoji": False},
        "blocks": [
            {
                "type": "input",
                "block_id": _EDIT_INPUT_BLOCK,
                "label": {
                    "type": "plain_text",
                    "text": f"Replacement value for {assumption_id}",
                    "emoji": False,
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": _EDIT_INPUT_ACTION,
                    "multiline": True,
                    "initial_value": prefill,
                },
            }
        ],
    }


def read_edit_submission(view: dict[str, Any]) -> str:
    """Extract the submitted replacement text from a ``view_submission`` view."""
    values = (view.get("state") or {}).get("values") or {}
    block = values.get(_EDIT_INPUT_BLOCK) or {}
    element = block.get(_EDIT_INPUT_ACTION) or {}
    return str(element.get("value") or "")


def aggregate_decision(state: dict[str, dict[str, Any]]) -> str:
    """The aggregate ``decision`` literal from a fully-decided item map (ASSUM-006).

    all ``accepted`` → ``approve``; any ``modified`` and none ``deferred`` →
    ``approve``; any ``deferred`` → ``defer``. (Whole-run ``planning_cancel`` →
    ``reject`` is handled at the click site, not here — cancel is an abort, not
    an aggregation over items.) An empty map defaults to ``approve`` (the
    zero-assumption whole-checkpoint approval).
    """
    dispositions = [item["disposition"] for item in state.values()]
    if any(d == "deferred" for d in dispositions):
        return "defer"
    return "approve"


def is_complete(message_blocks: list[Any] | None) -> bool:
    """True when every per-assumption item in the message is decided.

    The anti-rubber-stamp enforcement point (J03a): no aggregate decision is
    published while any item is undecided. A message with no items (e.g. the
    whole-checkpoint case, handled separately) is not 'complete' here.
    """
    state = parse_dialogue_blocks(message_blocks)
    if not state:
        return False
    return all(item["disposition"] != "undecided" for item in state.values())


# ---------------------------------------------------------------------------
# Renderer — posts a checkpoint into the originating thread (own web client)
# ---------------------------------------------------------------------------


class PlanningCheckpointRenderer:
    """Renders a Mode P planning checkpoint into its originating Slack thread.

    Holds its OWN ``AsyncWebClient`` (bot token) and the planning channel id,
    independent of the forge-notification ``SlackNotifier`` sink (arch F2) — the
    planning dialogue must not go dark when only the planning channel is
    configured. Constructed via :func:`create_planning_checkpoint_renderer` and
    wired into :class:`~jarvis.infrastructure.slack_notifier.ApprovalRequestsSubscriber`.

    Never raises (DDR-007): a render failure logs and returns; the subscriber's
    build-pause path is untouched.
    """

    __slots__ = ("_channel_id", "_spec_texts", "_web_client")

    def __init__(
        self,
        *,
        channel_id: str,
        web_client: Any,
        spec_texts: SpecTextRegistry | None = None,
    ) -> None:
        self._channel_id = channel_id
        self._web_client = web_client
        # Spec digest cards only: the worked examples are held here between
        # posting the card and a tap on "Show the worked examples". ``None``
        # (unwired) means that tap answers honestly that they are not to hand.
        self._spec_texts = spec_texts

    async def render(
        self,
        *,
        details: dict[str, Any],
        correlation_id: str | None,
        request_id: str,
        approval_subject: str,
    ) -> None:
        """Render the checkpoint as per-assumption prompts, threaded. Never raises."""
        try:
            thread_ts = details.get("parent_request_id") or details.get("thread_ts")
            count = chunk_count_for(details)
            worked_examples = 0
            if is_spec_digest(details):
                card = digest_card(details)
                # A digest card carries no per-assumption items; what it has a
                # count of is worked examples, and the log says which is which.
                n_items = 0
                worked_examples = len(_digest_examples(card))
                if self._spec_texts is not None:
                    # Held BEFORE the post, so the button can never be tapped
                    # on a card whose examples were not yet kept.
                    self._spec_texts.record(
                        request_id=request_id,
                        feature=str(card.get("feature") or ""),
                        spec_text=str(card.get("worked_examples") or ""),
                    )
            else:
                n_items = len(_assumptions(details))
            for chunk_index in range(count):
                blocks = build_dialogue_blocks(
                    details,
                    correlation_id=correlation_id,
                    request_id=request_id,
                    approval_subject=approval_subject,
                    chunk_index=chunk_index,
                    chunk_count=count,
                )
                response = await post_threaded(
                    self._web_client,
                    channel=self._channel_id,
                    text=_fallback_text(details, chunk_index=chunk_index, chunk_count=count),
                    thread_ts=thread_ts,
                    blocks=blocks,
                    correlation_id=correlation_id,
                )
                if response is None:
                    logger.warning(
                        "planning_checkpoint_render_post_failed",
                        correlation_id=correlation_id,
                        chunk_index=chunk_index,
                    )
                    return
            logger.info(
                "planning_checkpoint_rendered",
                correlation_id=correlation_id,
                request_id=request_id,
                assumptions=n_items,
                worked_examples=worked_examples,
                chunks=count,
                threaded=bool(thread_ts),
                escalated=is_escalated(details),
                spec_digest=is_spec_digest(details),
            )
        except Exception as exc:  # pragma: no cover - defensive DDR-007
            logger.warning(
                "planning_checkpoint_render_error",
                correlation_id=correlation_id,
                error_class=type(exc).__name__,
                error=str(exc),
            )


def _fallback_text(details: dict[str, Any], *, chunk_index: int, chunk_count: int) -> str:
    cycle = details.get("cycle")
    if is_spec_digest(details):
        base = "The spec is ready — here's what will be built"
        if chunk_count > 1:
            base += f" — continued ({chunk_index + 1}/{chunk_count})"
        return base
    if is_escalated(details):
        base = f"Planning checkpoint escalated to Rich (cycle {cycle})"
    else:
        base = f"Planning assumptions to decide (cycle {cycle})"
    if chunk_count > 1:
        base += f" — continued ({chunk_index + 1}/{chunk_count})"
    return base


def create_planning_checkpoint_renderer(
    config: JarvisConfig,
    *,
    spec_texts: SpecTextRegistry | None = None,
) -> PlanningCheckpointRenderer | None:
    """Create the checkpoint renderer, or a logged no-op (``None``).

    Gated on its OWN config only (arch F2), independent of the forge sink:

    * ``slack_planning_channel_id`` unset/blank — no render target.
    * ``slack_bot_token`` unset — no web client for ``chat.*``.

    Args:
        config: The jarvis configuration.
        spec_texts: The shared store the reply handler reads when the owner
            taps "Show the worked examples" on a spec digest card. ``None``
            (unwired) makes that tap answer honestly that they are not to hand;
            nothing else changes.

    Returns:
        A ready :class:`PlanningCheckpointRenderer`, or ``None``.
    """
    channel_id = (config.slack_planning_channel_id or "").strip() or None
    if not channel_id:
        logger.info(
            "planning_checkpoint_renderer_no_op",
            reason="slack_planning_channel_id not configured; disabled",
        )
        return None

    bot_token = config.slack_bot_token
    if bot_token is None or not bot_token.get_secret_value():
        logger.info(
            "planning_checkpoint_renderer_no_op",
            reason="slack_bot_token not configured; disabled",
        )
        return None

    from slack_sdk.web.async_client import AsyncWebClient

    renderer = PlanningCheckpointRenderer(
        channel_id=channel_id,
        web_client=AsyncWebClient(token=bot_token.get_secret_value()),
        spec_texts=spec_texts,
    )
    logger.info("planning_checkpoint_renderer_configured", channel_id=channel_id)
    return renderer


__all__ = [
    "ACTION_APPROVE",
    "ACTION_CANCEL",
    "ACTION_DEFER",
    "ACTION_DIGEST_APPROVE",
    "ACTION_DIGEST_NOTE",
    "ACTION_DIGEST_SHOW_SPEC",
    "ACTION_DIGEST_SIGN_IN_AGREE",
    "ACTION_DIGEST_SIGN_IN_DISAGREE",
    "ACTION_EDIT",
    "ACTION_WHOLE_APPROVE",
    "DEFAULT_SIGN_IN_ITEM_ID",
    "DIALOGUE_ACTION_IDS",
    "DIGEST_ACTION_IDS",
    "DIGEST_CARD_ID",
    "DIGEST_CHECKPOINT_TYPE",
    "EDIT_MODAL_CALLBACK_ID",
    "NOTE_MODAL_CALLBACK_ID",
    "SPEC_MODAL_CALLBACK_ID",
    "WHOLE_CHECKPOINT_ID",
    "PlanningCheckpointRenderer",
    "aggregate_decision",
    "apply_disposition",
    "apply_sign_in_answer",
    "build_dialogue_blocks",
    "build_digest_blocks",
    "build_edit_modal",
    "build_item_value",
    "build_note_modal",
    "build_spec_modal",
    "build_spec_unavailable_modal",
    "chunk_count_for",
    "chunk_spec_text",
    "create_planning_checkpoint_renderer",
    "digest_card",
    "extract_assumption_text",
    "is_complete",
    "is_escalated",
    "is_planning_checkpoint",
    "is_spec_digest",
    "parse_dialogue_blocks",
    "parse_item_value",
    "read_edit_submission",
    "read_note_submission",
    "sign_in_item_id",
    "tag_words",
]
