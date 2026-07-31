"""The plain-name fence for Slack-rendered text (factory phrase-book, 2026-07-31).

**The law.** ``docs/ways-of-working/factory-phrase-book.md`` (ratified by Rich
on 2026-07-31) makes the plain names the factory's *outward* vocabulary:
user-visible surfaces — Slack messages, approval cards, notifications — speak
plain names; the internal codenames stay in code, field names and log keys.
A new audience (a client, a viewer, James) must meet "the pipeline"
and "the checker" and understand the system in one pass, with no glossary.

**The live receipt this fence exists for.** A planning-run notification read
``feature FEAT-2D61 queued for build on forge's Mode B pipeline`` — "Mode B" is
an internal codename that was *retired* on 2026-07-31, printed on the surface
Rich actually reads. (That particular sentence is authored in the **forge**
repo and relayed verbatim by ``planning_notifier``; it is out of this repo's
venue. This fence guards the strings jarvis itself authors, so the same class
of defect cannot be reintroduced here.)

**What is and is not in scope.** Only what a Slack reader sees. Log event keys
(``forge_notification_dropped_malformed``), field names (``coach_score``),
NATS subjects (``agents.approval.forge.>``) and module names are code
identifiers and are deliberately untouched — the phrase-book says codenames
live there.

**One known gap this fence does NOT cover.** ``ForgeNotification.render_line()``
still emits ``[HH:MM] Forge {feature_id}: …``. That is *not* a code identifier
and *not* terminal-only: ``chat_handler`` appends the rendered line to the chat
gateway's reply on ``agents.command.jarvis``, which a human reads. By the
phrase-book's outward-vocabulary rule it wants sweeping — it is carried, not
cleared, because the shape is a contract of record (DDR-030,
``DM-forge-notification`` §1, ``API-internal.md``, and a ``confidence=high``
assumption in the FEAT-JARVIS-005 spec) that only a spec ruling may change.
This fence is deliberately silent about it rather than blessing it.

**How the fence works.** It renders the real Slack surfaces with *neutral*
fixture data and asserts the rendered operator-visible text carries no
codename. Feeding neutral data is the point: it isolates the **template** (the
thing jarvis authors and this repo owns) from **payload data** (stage labels,
rationales and failure reasons authored by forge, which jarvis relays verbatim
and must not rewrite). A template regression fails here; a forge-authored
string does not, because that is a defect to fix in forge.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.infrastructure.slack_notifier import (
    SlackNotifier,
    _terminal_status_line,
    build_pause_blocks,
)
from jarvis.infrastructure.slack_reply import (
    ApprovalReplyHandler,
    _already_terminal_text,
)
from jarvis.infrastructure.terminal_builds import TerminalBuildRecord

# ---------------------------------------------------------------------------
# The forbidden vocabulary — internal codenames that must never reach Slack.
#
# Sourced from the phrase-book's "Codename" column plus the retired mode
# labels. Plain-name replacements (phrase-book): forge → the pipeline; the
# Coach → the checker; guardkit/autobuild → the build system; Mode P → the
# full journey / the planning chain; Mode B → RETIRED 2026-07-31.
# ---------------------------------------------------------------------------
_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "forge",
    "coach",
    "autobuild",
    "guardkit",
    "nats-core",
    "llama-swap",
    "workhorse",
    "passbar",
    "gherkin",
)

_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"\bMode [ABCP]\b",  # the mode codenames (Mode B retired 2026-07-31)
    r"\bADR-[A-Z]+-\d+",  # architecture decision ids
    r"\bDDR-\d+",  # design decision ids
    r"\bTASK-[A-Z0-9]",  # task ids
    r"\bSPL-\d+",  # spec/planning-loop feature ids
    r"§",  # section-clause references
)


def _codename_offenders(text: str) -> list[str]:
    """Every forbidden codename found in one operator-visible string."""
    lowered = text.lower()
    found = [token for token in _FORBIDDEN_SUBSTRINGS if token in lowered]
    for pattern in _FORBIDDEN_PATTERNS:
        found.extend(re.findall(pattern, text))
    return found


def _assert_plain(texts: list[str], surface: str) -> None:
    """Assert every rendered string on ``surface`` is codename-free."""
    offenders = {t: _codename_offenders(t) for t in texts}
    offenders = {t: found for t, found in offenders.items() if found}
    assert not offenders, (
        f"{surface} renders internal codenames on a Slack surface — the "
        f"factory phrase-book (ratified 2026-07-31) requires plain names on "
        f"every user-visible string. Offending text → codenames: {offenders}"
    )


def _visible_texts(node: Any) -> list[str]:
    """Collect operator-visible strings from a Block Kit structure.

    Walks the blocks and returns every ``"text"`` string. Anything under a
    ``"value"``, ``"action_id"``, ``"block_id"`` or ``"callback_id"`` key is
    skipped: those are machine metadata (the BUTTON_METADATA routing JSON
    legitimately carries ``agents.approval.forge.…``) and a Slack reader never
    sees them.
    """
    collected: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("value", "action_id", "block_id", "callback_id"):
                continue
            if key == "text" and isinstance(value, str):
                collected.append(value)
            else:
                collected.extend(_visible_texts(value))
    elif isinstance(node, list):
        for item in node:
            collected.extend(_visible_texts(item))
    return collected


# ---------------------------------------------------------------------------
# Neutral fixtures — codename-free DATA so the assertions test the TEMPLATE.
# ---------------------------------------------------------------------------

_COMPLETED_AT = datetime(2026, 7, 31, 14, 7, tzinfo=UTC)
# The rendered stamp is local time (host-zone dependent) — derive it the same
# way the renderers do rather than hard-coding a UTC-only expectation.
_HHMM = _COMPLETED_AT.astimezone().strftime("%H:%M")


def _notification(event_type: str, **overrides: Any) -> ForgeNotification:
    """A notification whose every data field is deliberately codename-free."""
    fields: dict[str, Any] = {
        "event_type": event_type,
        "correlation_id": "corr-plain-1",
        "feature_id": "FEAT-2D61",
        "completed_at": _COMPLETED_AT,
        "build_id": "build-plain-1",
    }
    if event_type == "stage_complete":
        fields["stage_label"] = "plan-complete"
        fields["status"] = "PASSED"
    if event_type == "build_failed":
        fields["failure_reason"] = "a required check did not pass"
    if event_type == "build_complete":
        fields["summary"] = "one file changed"
        fields["pr_url"] = "https://example.invalid/pr/1"
    if event_type == "build_paused":
        fields["stage_label"] = "gate-2"
        fields["coach_score"] = 0.42
        fields["rationale"] = "a wiring risk was flagged"
        fields["approval_subject"] = "agents.approval.forge.build-plain-1"
    if event_type == "build_cancelled":
        fields["cancelled_by"] = "rich"
        fields["reason"] = "superseded by a newer plan"
    fields.update(overrides)
    return ForgeNotification(**fields)


def _make_notifier() -> SlackNotifier:
    """A SlackNotifier with a fully mocked web client — no network."""
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_cls.return_value = AsyncMock()
        return SlackNotifier(bot_token="xoxb-test", channel_id="C123456")


_ALL_EVENT_TYPES: tuple[str, ...] = (
    "stage_complete",
    "build_started",
    "build_complete",
    "build_failed",
    "build_queued",
    "build_paused",
    "build_cancelled",
)


# ---------------------------------------------------------------------------
# The notification sink's plain-text Slack messages.
# ---------------------------------------------------------------------------
class TestSlackNotifierRendersPlainNames:
    """``SlackNotifier._render`` speaks plain names for every event type."""

    @pytest.mark.parametrize("event_type", _ALL_EVENT_TYPES)
    def test_render_is_codename_free(self, event_type: str) -> None:
        text = _make_notifier()._render(_notification(event_type))
        _assert_plain(text.splitlines(), f"SlackNotifier._render({event_type})")

    @pytest.mark.parametrize("event_type", _ALL_EVENT_TYPES)
    def test_render_keeps_the_real_identifiers(self, event_type: str) -> None:
        """Feature ids and build ids are identifiers, not codenames — kept."""
        text = _make_notifier()._render(_notification(event_type))
        assert "FEAT-2D61" in text

    def test_render_uses_the_phrase_book_plain_names(self) -> None:
        """The positive assertion behind the fence, so it cannot pass vacuously."""
        text = _make_notifier()._render(_notification("build_paused"))
        assert text.startswith(f"[{_HHMM}] Pipeline FEAT-2D61: build-paused")
        assert "Checker score: 0.42" in text


# ---------------------------------------------------------------------------
# The Block Kit approval card.
# ---------------------------------------------------------------------------
class TestPauseCardRendersPlainNames:
    """``build_pause_blocks`` speaks plain names in all three card states."""

    def test_buttoned_card_is_codename_free(self) -> None:
        blocks = build_pause_blocks(
            _notification("build_paused"),
            button_value='{"request_id":"r1","build_id":"build-plain-1"}',
        )
        _assert_plain(_visible_texts(blocks), "build_pause_blocks (buttoned)")

    def test_text_only_card_is_codename_free(self) -> None:
        blocks = build_pause_blocks(_notification("build_paused"), button_value=None)
        _assert_plain(_visible_texts(blocks), "build_pause_blocks (text-only)")

    def test_terminal_stamped_card_is_codename_free(self) -> None:
        blocks = build_pause_blocks(
            _notification("build_paused"),
            button_value=None,
            status_line=_terminal_status_line(_notification("build_cancelled")),
        )
        _assert_plain(_visible_texts(blocks), "build_pause_blocks (terminal)")

    def test_card_uses_the_phrase_book_plain_names(self) -> None:
        texts = _visible_texts(build_pause_blocks(_notification("build_paused")))
        assert f"[{_HHMM}] Pipeline FEAT-2D61: build-paused" in texts
        assert "Checker score: 0.42" in texts

    @pytest.mark.parametrize("event_type", ("build_cancelled", "build_complete", "build_failed"))
    def test_terminal_status_line_is_codename_free(self, event_type: str) -> None:
        line = _terminal_status_line(_notification(event_type))
        _assert_plain([line], f"_terminal_status_line({event_type})")


# ---------------------------------------------------------------------------
# The reply handler's operator-visible answers.
# ---------------------------------------------------------------------------
class TestReplySurfacesRenderPlainNames:
    """Every string the approval reply path shows an operator is plain."""

    @pytest.mark.parametrize(
        "terminal_state", ("build_cancelled", "build_complete", "build_failed")
    )
    def test_tap_after_terminal_answer_is_codename_free(self, terminal_state: str) -> None:
        record = TerminalBuildRecord(
            terminal_state=terminal_state,
            at=_COMPLETED_AT,
            by="rich",
            recorded_at_mono=0.0,
        )
        _assert_plain([_already_terminal_text(record)], "_already_terminal_text")

    @pytest.mark.asyncio
    async def test_unauthorized_refusal_is_codename_free(self) -> None:
        web_client = AsyncMock()
        handler = ApprovalReplyHandler(
            operator_ids=frozenset({"U-OPERATOR"}),
            publisher=MagicMock(),
            web_client=web_client,
        )

        await handler._send_ephemeral_refusal({"channel": {"id": "C123456"}}, "U-STRANGER")

        text = web_client.chat_postEphemeral.await_args.kwargs["text"]
        _assert_plain([text], "ApprovalReplyHandler._send_ephemeral_refusal")
        assert text == "You are not authorized to decide build approvals from Slack."


# ---------------------------------------------------------------------------
# The fence must bite — a guard that always passes guards nothing.
# ---------------------------------------------------------------------------
class TestTheFenceBites:
    """The detector catches the exact defect the live receipt showed."""

    def test_the_live_receipt_string_is_caught(self) -> None:
        receipt = (
            "Planning run corr-1: feature FEAT-2D61 queued for build on "
            "forge's Mode B pipeline (branch main); paused at the build "
            "approval gate for the human tap."
        )
        found = _codename_offenders(receipt)
        assert "forge" in found
        assert "Mode B" in found

    @pytest.mark.parametrize(
        ("text", "expected"),
        (
            ("Stage: autobuild-complete", "autobuild"),
            ("Coach score: 0.42", "coach"),
            ("Approved per ADR-ARCH-019", "ADR-ARCH-019"),
            ("See design.md §8 for detail", "§"),
            ("Handing off to Mode P", "Mode P"),
        ),
    )
    def test_each_codename_class_is_detected(self, text: str, expected: str) -> None:
        assert expected in _codename_offenders(text)

    def test_plain_names_and_identifiers_pass_clean(self) -> None:
        """No false positives on the vocabulary the phrase-book prescribes."""
        for clean in (
            "[14:07] Pipeline FEAT-2D61: build-complete (PASSED)",
            "Checker score: 0.42",
            "Build: build-plain-1",
            "Trace: corr-plain-1",
            "You are not authorized to decide build approvals from Slack.",
            "This build was cancelled at 14:07 by rich",
        ):
            assert _codename_offenders(clean) == [], clean
