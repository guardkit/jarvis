"""The words on the build-gate card (rewritten 2026-09-05).

The defect, verbatim from the owner's screen at 19:18 on 2026-09-05::

    [19:18] Pipeline FEAT-729B: build-paused
    Build: build-FEAT-729B-20260905181841
    Trace: 7cbba8f5-…
    Stage: autobuild
    Checker score: score unavailable
    Rationale: No automatic score exists at this stage, so the factory
    always asks you before starting a build.

Six lines, and not one of them says what is being asked of the reader.
It opens with a status word ("build-paused"), prints two identifiers as
prose, names an internal stage, and answers the score question with a
non-answer — while the one sentence that actually explains the pause is
last and labelled.

What the card says now: a headline that states what happened and what is
owed, the feature as a person would name it, the pipeline's own sentence
as the body, the score only when there is one, and both identifiers on a
single muted line labelled in words. The buttons are untouched — same
action ids, same value — because the wire is untouched; this is what a
person sees, nothing else.

The merge-ready card rides the SAME ``build-paused`` envelope and the
SAME renderer (forge composes it in ``make_merge_card_publisher``); the
only thing that tells the two apart is the stage label forge puts on it,
so it gets the same treatment under its own headline.

No network anywhere: the Slack client is a mock and nothing here touches
NATS.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.infrastructure.forge_notifications import ForgeNotification
from jarvis.infrastructure.slack_notifier import SlackNotifier, build_pause_blocks

# The rationale forge actually sent at 19:18.
_LIVE_RATIONALE = (
    "No automatic score exists at this stage, so the factory always asks "
    "you before starting a build."
)

_PAUSE_HEADLINE = "Build paused — waiting for your go-ahead"
_MERGE_HEADLINE = "Ready to merge and deploy — your press"

# The words the old card put on screen that must never come back.
_BANNED = ("Stage:", "Trace:", "score unavailable", "build-paused")


def _live_payload(**overrides: Any) -> ForgeNotification:
    """The exact 19:18 payload shape, as jarvis projected it."""
    fields: dict[str, Any] = {
        "event_type": "build_paused",
        "correlation_id": "7cbba8f5-0000-4000-8000-000000000001",
        "feature_id": "FEAT-729B",
        "completed_at": datetime(2026, 9, 5, 18, 18, tzinfo=UTC),
        "build_id": "build-FEAT-729B-20260905181841",
        "approval_subject": "agents.approval.forge.build-FEAT-729B-20260905181841",
        "stage_label": "autobuild",
        "coach_score": None,
        "rationale": _LIVE_RATIONALE,
        "gate_mode": "MANDATORY_HUMAN_APPROVAL",
    }
    fields.update(overrides)
    return ForgeNotification(**fields)


def _make_notifier() -> SlackNotifier:
    """A notifier whose web client is a mock — no network."""
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_cls.return_value = AsyncMock()
        return SlackNotifier(bot_token="xoxb-test", channel_id="C123456")


def _visible(node: Any) -> list[str]:
    """Every string a Slack reader sees, machine metadata skipped."""
    collected: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("value", "action_id", "block_id", "callback_id"):
                continue
            if key == "text" and isinstance(value, str):
                collected.append(value)
            else:
                collected.extend(_visible(value))
    elif isinstance(node, list):
        for item in node:
            collected.extend(_visible(item))
    return collected


def _context_texts(blocks: list[dict[str, Any]]) -> list[str]:
    return [
        element["text"]
        for block in blocks
        if block.get("type") == "context"
        for element in block.get("elements", [])
        if isinstance(element, dict) and isinstance(element.get("text"), str)
    ]


def _button_value() -> str:
    return (
        '{"request_id":"apr-001","build_id":"build-FEAT-729B-20260905181841",'
        '"correlation_id":"7cbba8f5-0000-4000-8000-000000000001",'
        '"approval_subject":"agents.approval.forge.build-FEAT-729B-20260905181841"}'
    )


# ---------------------------------------------------------------------------
# The build-gate card
# ---------------------------------------------------------------------------


class TestTheBuildGateCard:
    """The 19:18 payload, rendered the way a person reads it."""

    def test_headline_says_what_is_being_asked(self) -> None:
        blocks = build_pause_blocks(_live_payload(), button_value=_button_value())
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == _PAUSE_HEADLINE

    @pytest.mark.parametrize("banned", _BANNED)
    def test_the_old_words_are_gone_from_every_visible_string(self, banned: str) -> None:
        texts = _visible(build_pause_blocks(_live_payload(), button_value=_button_value()))
        offenders = [t for t in texts if banned in t]
        assert not offenders, f"{banned!r} is still on the card: {offenders}"

    def test_the_rationale_is_the_body(self) -> None:
        texts = _visible(build_pause_blocks(_live_payload(), button_value=_button_value()))
        assert _LIVE_RATIONALE in texts

    def test_both_identifiers_ride_one_muted_line_labelled_in_words(self) -> None:
        blocks = build_pause_blocks(_live_payload(), button_value=_button_value())
        assert _context_texts(blocks) == [
            "FEAT-729B",
            "Build build-FEAT-729B-20260905181841 · reference 7cbba8f5-0000-4000-8000-000000000001",
        ]

    def test_the_feature_id_is_never_the_headline(self) -> None:
        blocks = build_pause_blocks(_live_payload(), button_value=_button_value())
        assert "FEAT-729B" not in blocks[0]["text"]["text"]
        # …but it is still on the card, as muted secondary text.
        assert "FEAT-729B" in _context_texts(blocks)

    def test_no_score_line_when_the_payload_has_no_score(self) -> None:
        texts = _visible(build_pause_blocks(_live_payload(), button_value=_button_value()))
        assert not any("Checker score" in t for t in texts)

    def test_a_score_renders_in_plain_words_on_its_own_line(self) -> None:
        texts = _visible(
            build_pause_blocks(_live_payload(coach_score=0.93), button_value=_button_value())
        )
        assert "Checker score: 0.93" in texts

    def test_a_human_title_replaces_the_id_as_the_cards_subject(self) -> None:
        title = "Show the app version on the home screen"
        blocks = build_pause_blocks(
            _live_payload(feature_title=title), button_value=_button_value()
        )
        section_texts = [
            b["text"]["text"] for b in blocks if b.get("type") == "section" and b.get("text")
        ]
        assert title in section_texts
        # The id drops out of the identity line; only the provenance line
        # (build + reference) stays muted underneath.
        assert _context_texts(blocks) == [
            "Build build-FEAT-729B-20260905181841 · reference 7cbba8f5-0000-4000-8000-000000000001"
        ]

    def test_the_buttons_are_untouched(self) -> None:
        value = _button_value()
        blocks = build_pause_blocks(_live_payload(), button_value=value)
        actions = [b for b in blocks if b.get("type") == "actions"]
        assert len(actions) == 1
        assert actions[0]["block_id"] == "forge_approval"
        approve, reject = actions[0]["elements"]
        assert approve["action_id"] == "forge_approve"
        assert reject["action_id"] == "forge_reject"
        assert approve["text"]["text"] == "Approve"
        assert reject["text"]["text"] == "Reject"
        assert approve["value"] == reject["value"] == value

    def test_a_settled_card_stops_asking_for_a_go_ahead(self) -> None:
        """R3-A: the build ended under the card, so the headline stops
        asking; the stamp underneath says what actually happened."""
        blocks = build_pause_blocks(
            _live_payload(),
            button_value=None,
            status_line="This build was cancelled at 19:41 by rich",
        )
        assert blocks[0]["text"]["text"] == "Build paused"
        texts = _visible(blocks)
        assert "This build was cancelled at 19:41 by rich" in texts
        assert not [b for b in blocks if b.get("type") == "actions"]

    def test_every_visible_text_object_stays_inert_plain_text(self) -> None:
        blocks = build_pause_blocks(
            _live_payload(rationale="*bold* <http://x|link> & injection"),
            button_value=_button_value(),
        )
        for block in blocks:
            if isinstance(block.get("text"), dict):
                assert block["text"]["type"] == "plain_text"
            for element in block.get("elements", []):
                if isinstance(element, dict) and isinstance(element.get("text"), dict):
                    assert element["text"]["type"] == "plain_text"
                elif isinstance(element, dict) and element.get("type") == "plain_text":
                    assert element["type"] == "plain_text"


# ---------------------------------------------------------------------------
# The merge-ready card — same envelope, same renderer, its own headline
# ---------------------------------------------------------------------------


class TestTheMergeReadyCard:
    """forge's merge-ready checkpoint rides the same machinery."""

    def _merge_payload(self, **overrides: Any) -> ForgeNotification:
        return _live_payload(stage_label="the merge-ready checkpoint", **overrides)

    def test_headline_asks_for_the_merge_press(self) -> None:
        blocks = build_pause_blocks(self._merge_payload(), button_value=_button_value())
        assert blocks[0]["text"]["text"] == _MERGE_HEADLINE

    @pytest.mark.parametrize("banned", _BANNED)
    def test_the_old_words_are_gone_here_too(self, banned: str) -> None:
        texts = _visible(build_pause_blocks(self._merge_payload(), button_value=_button_value()))
        assert not [t for t in texts if banned in t]

    def test_the_buttons_are_the_same_buttons(self) -> None:
        blocks = build_pause_blocks(self._merge_payload(), button_value=_button_value())
        actions = next(b for b in blocks if b.get("type") == "actions")
        assert [e["action_id"] for e in actions["elements"]] == [
            "forge_approve",
            "forge_reject",
        ]

    def test_the_text_rendering_carries_the_merge_headline(self) -> None:
        text = _make_notifier()._render(self._merge_payload())
        assert text.startswith(_MERGE_HEADLINE)


# ---------------------------------------------------------------------------
# The text rendering (the no-buttons message, and the notification preview)
# ---------------------------------------------------------------------------


class TestTheTextRendering:
    """The same words, for the path that has no buttons."""

    def test_the_whole_message_in_order(self) -> None:
        text = _make_notifier()._render(_live_payload(coach_score=0.93))
        assert text.split("\n") == [
            _PAUSE_HEADLINE,
            "FEAT-729B",
            _LIVE_RATIONALE,
            "Checker score: 0.93",
            "Build build-FEAT-729B-20260905181841 · reference 7cbba8f5-0000-4000-8000-000000000001",
            "Use CLI to approve or reject this build.",
        ]

    @pytest.mark.parametrize("banned", _BANNED)
    def test_the_old_words_are_gone_from_the_text(self, banned: str) -> None:
        text = _make_notifier()._render(_live_payload())
        assert banned not in text

    def test_a_human_title_is_used_instead_of_the_id(self) -> None:
        title = "Show the app version on the home screen"
        text = _make_notifier()._render(_live_payload(feature_title=title))
        lines = text.split("\n")
        assert lines[0] == _PAUSE_HEADLINE
        assert lines[1] == title
        # The id is not a line of its own any more; it survives only
        # inside the build id on the muted provenance line.
        assert "FEAT-729B" not in lines
