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
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

from jarvis.infrastructure.planning_notifier import post_threaded

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
    """Number of Slack messages this checkpoint renders across (>= 1)."""
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

    __slots__ = ("_channel_id", "_web_client")

    def __init__(self, *, channel_id: str, web_client: Any) -> None:
        self._channel_id = channel_id
        self._web_client = web_client

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
                chunks=count,
                threaded=bool(thread_ts),
                escalated=is_escalated(details),
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
    if is_escalated(details):
        base = f"Planning checkpoint escalated to Rich (cycle {cycle})"
    else:
        base = f"Planning assumptions to decide (cycle {cycle})"
    if chunk_count > 1:
        base += f" — continued ({chunk_index + 1}/{chunk_count})"
    return base


def create_planning_checkpoint_renderer(
    config: JarvisConfig,
) -> PlanningCheckpointRenderer | None:
    """Create the checkpoint renderer, or a logged no-op (``None``).

    Gated on its OWN config only (arch F2), independent of the forge sink:

    * ``slack_planning_channel_id`` unset/blank — no render target.
    * ``slack_bot_token`` unset — no web client for ``chat.*``.

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
    )
    logger.info("planning_checkpoint_renderer_configured", channel_id=channel_id)
    return renderer


__all__ = [
    "ACTION_APPROVE",
    "ACTION_CANCEL",
    "ACTION_DEFER",
    "ACTION_EDIT",
    "ACTION_WHOLE_APPROVE",
    "DIALOGUE_ACTION_IDS",
    "WHOLE_CHECKPOINT_ID",
    "PlanningCheckpointRenderer",
    "aggregate_decision",
    "apply_disposition",
    "build_dialogue_blocks",
    "build_item_value",
    "chunk_count_for",
    "create_planning_checkpoint_renderer",
    "is_complete",
    "is_escalated",
    "is_planning_checkpoint",
    "parse_dialogue_blocks",
    "parse_item_value",
]
