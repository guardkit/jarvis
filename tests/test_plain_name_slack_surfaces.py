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

**One gap CLOSED, and one exemption taken deliberately (2026-08-14).** The
planning surfaces — the per-assumption dialogue and the new spec digest card —
are now rendered here. The dialogue was never covered before, which meant the
one surface Rich actually taps was the one surface this fence never rendered.
The single exemption is the read-only view behind "Show the worked examples":
it carries the spec's own words verbatim, because its whole value is fidelity,
and it is asserted as an exemption below rather than left to be discovered.

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

from jarvis.infrastructure import assumption_dialogue as ad
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
        assert text.startswith("Build paused — waiting for your go-ahead")
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
        assert "Build paused — waiting for your go-ahead" in texts
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
# The planning surfaces Rich actually taps.
#
# Both were outside this fence until 2026-08-14 — the one surface a person
# decides on was the one surface it never rendered. Neutral fixtures again:
# these assertions test the TEMPLATE, and the card body a planning run supplies
# is authored elsewhere.
# ---------------------------------------------------------------------------
_PLANNING_SUBJECT = "agents.approval.forge.plan-cid123"


def _dialogue_details(n: int = 2, *, checkpoint_type: str = "product_docs") -> dict[str, Any]:
    """An assumption checkpoint whose every data field is codename-free."""
    return {
        "checkpoint_type": checkpoint_type,
        "cycle": 1,
        "attempt_count": 1,
        "expected_approver": "U_RICH",
        "parent_request_id": "1700000000.000100",
        "summary": {
            "checkpoint": "product-docs",
            "assumptions": [
                {
                    "id": f"A{i + 1}",
                    "text": f"Assumption {i + 1} proposed text",
                    "confidence": "medium",
                    "basis": "the input did not say",
                }
                for i in range(n)
            ],
        },
    }


def _digest_details(*, sign_in: bool = False, tags: list[str] | None = None) -> dict[str, Any]:
    """A spec digest card whose every data field is codename-free."""
    card: dict[str, Any] = {
        "checkpoint": ad.DIGEST_CHECKPOINT_TYPE,
        "title": "The spec is ready — here's what will be built",
        "feature": "version-endpoint",
        "what_happened": "Below is one sentence per example, in the order they appear.",
        "what_it_will_do": [
            {
                "sentence": "Asking the service which version it runs returns the build.",
                "tags": tags if tags is not None else ["@key-example", "@smoke"],
            }
        ],
        "what_the_machine_assumed": [
            {"assumption": "The version comes from the image.", "why": "the input did not say"}
        ],
        "approve_means": "Nothing is built yet.",
        "note_means": "The machine rewrites the spec from what you say.",
        "show_means": "Read the examples themselves. You never have to.",
        "no_answer_means": "No answer within one hour: the run stops and says so.",
        "worked_examples": "Feature: version\n  Scenario: it answers\n",
    }
    if sign_in:
        card["sign_in_check"] = {
            "title": "One thing to confirm",
            "answer_id": "sign-in",
            "statement": "Nothing in this feature involves signing in.",
            "body": "Say whether that is right, with the spec in front of you.",
            "why_we_ask": "The check that spots this is a keyword scan.",
            "agree_means": "The build carries on.",
            "disagree_means": "A person registers the quality checklist by hand.",
            "no_answer_means": "Saying nothing here is taken as agreement.",
            "flagged_lines": ["an example mentions a password"],
        }
    return {
        "checkpoint_type": ad.DIGEST_CHECKPOINT_TYPE,
        "cycle": None,
        "expected_approver": "U_RICH",
        "parent_request_id": "1700000000.000100",
        "summary": card,
    }


def _render(details: dict[str, Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    count = ad.chunk_count_for(details)
    for index in range(count):
        blocks.extend(
            ad.build_dialogue_blocks(
                details,
                correlation_id="cid123",
                request_id="req-1",
                approval_subject=_PLANNING_SUBJECT,
                chunk_index=index,
                chunk_count=count,
            )
        )
    return blocks


class TestPlanningDialogueRendersPlainNames:
    """The per-assumption dialogue — the surface the fence used to skip."""

    @pytest.mark.parametrize("checkpoint_type", ("product_docs", "product_docs_escalated"))
    def test_dialogue_blocks_are_codename_free(self, checkpoint_type: str) -> None:
        blocks = _render(_dialogue_details(checkpoint_type=checkpoint_type))
        _assert_plain(_visible_texts(blocks), f"build_dialogue_blocks({checkpoint_type})")

    def test_zero_assumption_dialogue_is_codename_free(self) -> None:
        _assert_plain(_visible_texts(_render(_dialogue_details(0))), "dialogue (no items)")

    def test_edit_modal_is_codename_free(self) -> None:
        view = ad.build_edit_modal(
            assumption_id="A1", prefill="a proposed value", private_metadata="{}"
        )
        _assert_plain(_visible_texts(view), "build_edit_modal")

    @pytest.mark.parametrize("chunk_index", (0, 1))
    def test_dialogue_fallback_text_is_codename_free(self, chunk_index: int) -> None:
        text = ad._fallback_text(_dialogue_details(), chunk_index=chunk_index, chunk_count=2)
        _assert_plain([text], "dialogue fallback text")


class TestSpecDigestCardRendersPlainNames:
    """The spec digest card — the one card that decides what gets built."""

    def test_digest_blocks_are_codename_free(self) -> None:
        _assert_plain(_visible_texts(_render(_digest_details())), "spec digest card")

    def test_the_sign_in_variant_is_codename_free(self) -> None:
        blocks = _render(_digest_details(sign_in=True))
        _assert_plain(_visible_texts(blocks), "spec digest card (sign-in)")

    def test_an_answered_sign_in_question_is_codename_free(self) -> None:
        blocks = ad.apply_sign_in_answer(
            _render(_digest_details(sign_in=True)), item_id="sign-in", disposition="rejected"
        )
        _assert_plain(_visible_texts(blocks), "spec digest card (answered)")

    def test_the_note_modal_is_codename_free(self) -> None:
        _assert_plain(_visible_texts(ad.build_note_modal(private_metadata="{}")), "note modal")

    def test_the_unavailable_examples_view_is_codename_free(self) -> None:
        _assert_plain(
            _visible_texts(ad.build_spec_unavailable_modal()), "worked examples (unavailable)"
        )

    def test_digest_fallback_text_is_codename_free(self) -> None:
        text = ad._fallback_text(_digest_details(), chunk_index=0, chunk_count=1)
        _assert_plain([text], "spec digest fallback text")

    def test_an_internal_label_never_reaches_the_card(self) -> None:
        """The hostile fixture: a spec's own labels are not the card's vocabulary.

        The allowlist is what makes this hold — an unmapped label contributes
        nothing — so a spec carrying task ids or codenames on its examples can
        never turn a leak into a fence failure at render time.
        """
        blocks = _render(
            _digest_details(tags=["@spl-003", "@TASK-ABW-002", "@forge-only", "@coach"])
        )
        _assert_plain(_visible_texts(blocks), "spec digest card (hostile labels)")

    def test_the_worked_examples_view_is_deliberately_exempt(self) -> None:
        """Named here so the exemption is a decision, not an oversight.

        The read-only view behind "Show the worked examples" carries the spec's
        OWN words, verbatim. Real specs in this estate carry task ids and tool
        names, and scrubbing them would make the one surface whose whole value
        is fidelity the one surface that lies. It is one click deeper, it is
        never the ask, and every other string on the card is fenced above.
        """
        spec = "Feature: sign in\n  Scenario: TASK-ABW-002 the pipeline logs in\n"
        view = ad.build_spec_modal(feature="version-endpoint", spec_text=spec)
        rendered = "\n".join(_visible_texts(view))
        assert spec in rendered
        # The frame around it is still the fence's business.
        frame = [t for t in _visible_texts(view) if spec not in t]
        _assert_plain(frame, "worked examples view (frame)")


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
            "[14:07] Pipeline FEAT-2D61: build complete — 4 of 4 tasks passed the checker.",
            "Checker score: 0.42",
            "Build: build-plain-1",
            "Trace: corr-plain-1",
            "You are not authorized to decide build approvals from Slack.",
            "This build was cancelled at 14:07 by rich",
        ):
            assert _codename_offenders(clean) == [], clean
