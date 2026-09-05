"""The spec digest card — what the owner reads before a build is specified.

Machine chain, stage 2 (2026-08-14). These tests pin the RENDER half: the
numbered sentences, the assumptions with their reasons, the label allowlist,
the three controls, chunking on worked examples, threading, the sign-in
question, and the two modals ("send a note" and the read-only worked-examples
view). Fully hermetic — no Slack, no NATS.

The load-bearing ones, named so a reader knows which failures matter most:

* an unmapped label reaches NO visible text on the card (a spec is free to
  carry internal labels; the owner's surface is not);
* the primary control never says the tap starts a build, because it does not;
* every other ``checkpoint_type`` renders exactly what it rendered before.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from jarvis.infrastructure import assumption_dialogue as ad
from jarvis.infrastructure.assumption_dialogue import PlanningCheckpointRenderer
from jarvis.infrastructure.spec_texts import SpecTextRegistry
from tests.test_assumption_dialogue_render import make_details

_SUBJECT = "agents.approval.forge.plan-cid123"
_CHANNEL = "C_PLANNING"

_SPEC_TEXT = """Feature: Version endpoint

  Scenario: Version endpoint returns the running build
    Given the service is running
    When the version is asked for
    Then the build it started from is returned
"""


def make_digest_details(
    n_examples: int = 3,
    *,
    n_assumptions: int = 2,
    tags: list[list[str]] | None = None,
    sign_in: bool = False,
    parent_request_id: str | None = "1700000000.000100",
    spec_text: str = _SPEC_TEXT,
    feature: str = "version-endpoint",
) -> dict[str, Any]:
    """A digest card in the shape the pipeline actually publishes.

    Mirrors forge's own card builder: the body rides the approval envelope
    under ``details.summary``, and ``checkpoint_type`` is the digest
    discriminator.
    """
    card: dict[str, Any] = {
        "checkpoint": ad.DIGEST_CHECKPOINT_TYPE,
        "title": "The spec is ready — here's what will be built",
        "what_happened": (
            "The spec-writer has written the worked examples this build will "
            "be checked against. Below is one sentence per example, in the "
            "order they appear."
        ),
        "what_it_will_do": [
            {
                "sentence": f"Worked example {i + 1} does the thing it says.",
                "tags": (tags[i] if tags else ["@key-example", "@smoke"]),
            }
            for i in range(n_examples)
        ],
        "what_the_machine_assumed": [
            {
                "assumption": f"Assumption {i + 1} taken by the spec.",
                "why": f"Reason {i + 1} the spec gives.",
            }
            for i in range(n_assumptions)
        ],
        "approve_means": "Yes — this is what I want built: nothing is built yet.",
        "note_means": "Send a note and the machine rewrites the spec.",
        "show_means": "Show the worked examples to read the examples themselves.",
        "no_answer_means": "No answer within one hour: the run stops and says so.",
        "worked_examples": spec_text,
    }
    if feature:
        card["feature"] = feature
    if sign_in:
        card["sign_in_check"] = {
            "title": "One thing to confirm",
            "answer_id": "sign-in",
            "statement": "Nothing in this feature involves signing in.",
            "body": "Say whether that is right, with the spec in front of you.",
            "why_we_ask": "The check that spots this is a keyword scan.",
            "agree_means": "Agree and the build carries on.",
            "disagree_means": "Disagree and a person registers the checklist.",
            "no_answer_means": "Saying nothing here is taken as agreement.",
            "flagged_lines": ["the word 'login' appears in an example"],
        }
    return {
        "build_id": "plan-cid123",
        "feature_id": "plan-cid123",
        "checkpoint_type": ad.DIGEST_CHECKPOINT_TYPE,
        "summary": card,
        "expected_approver": "U_RICH",
        "attempt_count": 0,
        "parent_request_id": parent_request_id,
        "cycle": None,
    }


def _blocks(details: dict[str, Any], *, chunk_index: int = 0, chunk_count: int = 1):
    return ad.build_dialogue_blocks(
        details,
        correlation_id="cid123",
        request_id="req-1",
        approval_subject=_SUBJECT,
        chunk_index=chunk_index,
        chunk_count=chunk_count,
    )


def _texts(node: Any) -> list[str]:
    """Every operator-visible string in a Block Kit structure."""
    out: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("value", "action_id", "block_id", "callback_id", "private_metadata"):
                continue
            if key == "text" and isinstance(value, str):
                out.append(value)
            else:
                out.extend(_texts(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_texts(item))
    return out


def _action_ids(blocks: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for block in blocks:
        for element in block.get("elements") or []:
            if isinstance(element, dict) and element.get("action_id"):
                ids.append(str(element["action_id"]))
    return ids


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
class TestDetection:
    def test_digest_rides_the_planning_front_door(self) -> None:
        """The one planning path proven answerable from Slack."""
        assert ad.is_planning_checkpoint(make_digest_details())

    def test_digest_is_detected_by_exact_checkpoint_type(self) -> None:
        assert ad.is_spec_digest(make_digest_details())

    @pytest.mark.parametrize(
        "checkpoint_type",
        ("product_docs", "product_docs_escalated", "product_docs_something_new", ""),
    )
    def test_other_checkpoints_are_not_digests(self, checkpoint_type: str) -> None:
        """A prefix test would swallow a future card nobody has read."""
        assert not ad.is_spec_digest({"checkpoint_type": checkpoint_type})

    def test_a_missing_summary_is_an_empty_card_not_a_crash(self) -> None:
        details = {"checkpoint_type": ad.DIGEST_CHECKPOINT_TYPE}
        assert ad.digest_card(details) == {}
        blocks = _blocks(details)
        assert any("no worked examples" in t for t in _texts(blocks))


# ---------------------------------------------------------------------------
# The card face
# ---------------------------------------------------------------------------
class TestTheCardFace:
    def test_one_numbered_sentence_per_worked_example_in_order(self) -> None:
        blocks = _blocks(make_digest_details(3))
        sentences = [b for b in blocks if str(b.get("block_id", "")).startswith("digestex")]
        assert [b["block_id"] for b in sentences] == ["digestex0", "digestex1", "digestex2"]
        for index, block in enumerate(sentences):
            text = block["text"]["text"]
            assert text.startswith(f"`{index + 1}.`")
            assert f"Worked example {index + 1}" in text

    def test_the_worked_examples_themselves_are_not_on_the_card(self) -> None:
        """The spec is one click deeper — never the ask."""
        joined = "\n".join(_texts(_blocks(make_digest_details())))
        assert "Given the service is running" not in joined
        assert "Scenario:" not in joined

    def test_each_assumption_shows_its_reason(self) -> None:
        texts = _texts(_blocks(make_digest_details(2, n_assumptions=2)))
        assert any("Assumption 1 taken by the spec." in t for t in texts)
        assert any("Why: Reason 1 the spec gives." in t for t in texts)

    def test_a_spec_with_no_assumptions_still_renders_and_still_asks(self) -> None:
        blocks = _blocks(make_digest_details(2, n_assumptions=0))
        assert any("no assumptions of its own" in t for t in _texts(blocks))
        assert ad.ACTION_DIGEST_APPROVE in _action_ids(blocks)

    def test_the_three_controls_are_present_and_named_plainly(self) -> None:
        blocks = _blocks(make_digest_details())
        assert _action_ids(blocks) == [
            ad.ACTION_DIGEST_APPROVE,
            ad.ACTION_DIGEST_NOTE,
            ad.ACTION_DIGEST_SHOW_SPEC,
        ]
        texts = _texts(blocks)
        assert "Yes — this is what I want built" in texts
        assert "Send a note" in texts
        assert "Show the worked examples" in texts

    def test_the_primary_control_never_says_the_tap_starts_a_build(self) -> None:
        """A control that misnames its consequence is an approval-surface defect."""
        blocks = _blocks(make_digest_details())
        button = next(
            element
            for block in blocks
            for element in (block.get("elements") or [])
            if isinstance(element, dict) and element.get("action_id") == ad.ACTION_DIGEST_APPROVE
        )
        label = button["text"]["text"]
        assert label == "Yes — this is what I want built"
        assert "build this" not in label.lower()
        assert "start" not in label.lower()

    def test_the_fine_print_travels_verbatim(self) -> None:
        texts = _texts(_blocks(make_digest_details()))
        assert "No answer within one hour: the run stops and says so." in texts

    def test_the_controls_carry_only_routing_identifiers(self) -> None:
        """The 2000-character value cap: identifiers ride, text never does."""
        blocks = _blocks(make_digest_details())
        for block in blocks:
            for element in block.get("elements") or []:
                if not isinstance(element, dict) or "value" not in element:
                    continue
                parsed = json.loads(element["value"])
                assert set(parsed) == {
                    "correlation_id",
                    "request_id",
                    "assumption_id",
                    "cycle",
                    "approval_subject",
                }
                assert len(element["value"]) < 2000

    def test_the_card_controls_are_not_a_decidable_item(self) -> None:
        """``parse_dialogue_blocks`` must not read the card's own buttons as state."""
        assert ad.parse_dialogue_blocks(_blocks(make_digest_details())) == {}

    def test_the_card_names_the_repository_it_will_be_built_in(self) -> None:
        """Binding spec 2026-09-05, rule 5 — the owner reads WHERE, not just what."""
        details = make_digest_details()
        details["summary"]["target_repo"] = "guardkit/study-tutor"
        header = next(b for b in _blocks(details) if b.get("block_id") == "digesthdr")
        text = header["text"]["text"]
        assert "_Repo: guardkit/study-tutor_" in text
        # Under the feature line, not above it.
        assert text.index("_Feature: version-endpoint_") < text.index("_Repo:")

    def test_a_card_without_a_repository_renders_exactly_as_before(self) -> None:
        """An older forge sends no such field; the card must be byte-identical."""
        blocks = _blocks(make_digest_details())
        header = next(b for b in blocks if b.get("block_id") == "digesthdr")
        assert header["text"]["text"] == (
            "*The spec is ready — here's what will be built*\n_Feature: version-endpoint_"
        )
        assert "Repo:" not in "\n".join(_texts(blocks))

    def test_a_blank_repository_field_renders_no_repo_line(self) -> None:
        details = make_digest_details()
        details["summary"]["target_repo"] = "   "
        header = next(b for b in _blocks(details) if b.get("block_id") == "digesthdr")
        assert "Repo:" not in header["text"]["text"]


# ---------------------------------------------------------------------------
# The label allowlist
# ---------------------------------------------------------------------------
class TestTheLabelAllowlist:
    def test_mapped_labels_render_their_plain_words(self) -> None:
        blocks = _blocks(
            make_digest_details(
                4,
                tags=[["@key-example"], ["@smoke"], ["@negative"], ["@edge-case"]],
            )
        )
        joined = "\n".join(_texts(blocks))
        for word in (
            "the main one",
            "checked after every deploy",
            "a refusal case",
            "an awkward case",
        ):
            assert word in joined

    def test_an_unmapped_label_reaches_no_visible_text(self) -> None:
        """The hostile fixture: internal labels must not surface on the card."""
        hostile = ["@spl-003", "@TASK-ABW-002", "@forge-internal", "@Mode-B"]
        blocks = _blocks(make_digest_details(1, tags=[hostile]))
        joined = "\n".join(_texts(blocks))
        for tag in hostile:
            assert tag not in joined
            assert tag.lstrip("@") not in joined

    def test_the_raw_label_words_never_reach_the_card(self) -> None:
        """``smoke``/``negative`` are the labels with the @ filed off, not English."""
        blocks = _blocks(make_digest_details(2, tags=[["@smoke"], ["@negative"]]))
        joined = "\n".join(_texts(blocks)).lower()
        assert "smoke" not in joined
        assert "negative" not in joined

    def test_tag_words_dedupes_and_keeps_file_order(self) -> None:
        assert ad.tag_words(["@negative", "@key-example", "@negative"]) == [
            "a refusal case",
            "the main one",
        ]

    def test_a_label_without_its_at_sign_still_maps(self) -> None:
        assert ad.tag_words(["smoke"]) == ["checked after every deploy"]


# ---------------------------------------------------------------------------
# Chunking — on worked examples, never assumptions
# ---------------------------------------------------------------------------
class TestChunking:
    def test_chunk_count_follows_the_worked_examples(self) -> None:
        assert ad.chunk_count_for(make_digest_details(8)) == 1
        assert ad.chunk_count_for(make_digest_details(9)) == 2
        assert ad.chunk_count_for(make_digest_details(17)) == 3

    def test_many_assumptions_do_not_chunk_a_digest(self) -> None:
        """The assumption chunk size (8) must not drive this card."""
        assert ad.chunk_count_for(make_digest_details(3, n_assumptions=20)) == 1

    def test_no_example_is_dropped_across_chunks(self) -> None:
        details = make_digest_details(9)
        count = ad.chunk_count_for(details)
        seen: list[str] = []
        for index in range(count):
            for block in _blocks(details, chunk_index=index, chunk_count=count):
                if str(block.get("block_id", "")).startswith("digestex"):
                    seen.append(block["text"]["text"])
        assert len(seen) == 9
        for index in range(9):
            assert any(f"`{index + 1}.`" in text for text in seen)

    def test_the_controls_appear_exactly_once_on_the_last_chunk(self) -> None:
        details = make_digest_details(9)
        first = _blocks(details, chunk_index=0, chunk_count=2)
        last = _blocks(details, chunk_index=1, chunk_count=2)
        assert ad.ACTION_DIGEST_APPROVE not in _action_ids(first)
        assert ad.ACTION_DIGEST_APPROVE in _action_ids(last)
        assert any("continued (1/2)" in t for t in _texts(first))


# ---------------------------------------------------------------------------
# The sign-in question — one tap answers two questions
# ---------------------------------------------------------------------------
class TestTheSignInQuestion:
    def test_it_is_absent_unless_the_spec_raised_it(self) -> None:
        ids = _action_ids(_blocks(make_digest_details(sign_in=False)))
        assert ad.ACTION_DIGEST_SIGN_IN_AGREE not in ids
        assert ad.ACTION_DIGEST_SIGN_IN_DISAGREE not in ids

    def test_it_renders_the_statement_the_reason_and_both_answers(self) -> None:
        blocks = _blocks(make_digest_details(sign_in=True))
        joined = "\n".join(_texts(blocks))
        assert "One thing to confirm" in joined
        assert "Nothing in this feature involves signing in." in joined
        assert "the word 'login' appears in an example" in joined
        assert "The check that spots this is a keyword scan." in joined
        ids = _action_ids(blocks)
        assert ad.ACTION_DIGEST_SIGN_IN_AGREE in ids
        assert ad.ACTION_DIGEST_SIGN_IN_DISAGREE in ids

    def test_its_answer_travels_under_the_id_the_card_names(self) -> None:
        blocks = _blocks(make_digest_details(sign_in=True))
        button = next(
            element
            for block in blocks
            for element in (block.get("elements") or [])
            if isinstance(element, dict)
            and element.get("action_id") == ad.ACTION_DIGEST_SIGN_IN_AGREE
        )
        assert json.loads(button["value"])["assumption_id"] == "sign-in"

    def test_an_unanswered_question_yields_no_item_at_all(self) -> None:
        """No answer means no item on the wire, which the pipeline reads as agreement."""
        state = ad.parse_dialogue_blocks(_blocks(make_digest_details(sign_in=True)))
        assert state == {"sign-in": {"disposition": "undecided", "edit_delta": None}}

    @pytest.mark.parametrize("disposition", ("accepted", "rejected"))
    def test_an_answer_round_trips_through_the_message(self, disposition: str) -> None:
        blocks = _blocks(make_digest_details(sign_in=True))
        updated = ad.apply_sign_in_answer(blocks, item_id="sign-in", disposition=disposition)
        assert ad.parse_dialogue_blocks(updated) == {
            "sign-in": {"disposition": disposition, "edit_delta": None}
        }

    def test_answering_it_leaves_the_cards_own_controls_live(self) -> None:
        blocks = _blocks(make_digest_details(sign_in=True))
        updated = ad.apply_sign_in_answer(blocks, item_id="sign-in", disposition="accepted")
        assert ad.ACTION_DIGEST_APPROVE in _action_ids(updated)
        assert ad.ACTION_DIGEST_SIGN_IN_AGREE not in _action_ids(updated)

    def test_the_recorded_answer_reads_as_english_not_wire_vocabulary(self) -> None:
        updated = ad.apply_sign_in_answer(
            _blocks(make_digest_details(sign_in=True)),
            item_id="sign-in",
            disposition="rejected",
        )
        joined = "\n".join(_texts(updated))
        assert "You said: this really does involve signing in." in joined


# ---------------------------------------------------------------------------
# The note modal
# ---------------------------------------------------------------------------
class TestTheNoteModal:
    def test_it_asks_for_one_required_plain_english_note(self) -> None:
        view = ad.build_note_modal(private_metadata="{}")
        assert view["callback_id"] == ad.NOTE_MODAL_CALLBACK_ID
        assert view["submit"]["text"] == "Send"
        inputs = [b for b in view["blocks"] if b["type"] == "input"]
        assert len(inputs) == 1
        # Slack input blocks are required unless explicitly optional.
        assert inputs[0].get("optional") is not True
        assert inputs[0]["element"]["multiline"] is True

    def test_it_is_never_prefilled_with_the_spec(self) -> None:
        """The red pen is the owner's own sentence, not an edit to the spec."""
        view = ad.build_note_modal(private_metadata="{}")
        assert "initial_value" not in view["blocks"][0]["element"]

    def test_the_submitted_note_is_read_verbatim(self) -> None:
        note = "The version should come from the running image, not a file."
        view = {
            "state": {
                "values": {"spec_digest_note_input": {"spec_digest_note_value": {"value": note}}}
            }
        }
        assert ad.read_note_submission(view) == note

    def test_a_malformed_submission_reads_as_empty(self) -> None:
        assert ad.read_note_submission({}) == ""


# ---------------------------------------------------------------------------
# The read-only worked-examples view
# ---------------------------------------------------------------------------
class TestTheWorkedExamplesView:
    def test_it_has_nothing_to_submit(self) -> None:
        view = ad.build_spec_modal(feature="version-endpoint", spec_text=_SPEC_TEXT)
        assert "submit" not in view
        assert view["close"]["text"] == "Close"

    def test_the_worked_examples_ride_verbatim_and_unscrubbed(self) -> None:
        """The ONE surface where the spec's own words are right, decided here.

        Every other string on the digest card is composed by jarvis and is held
        to the plain-name fence. This view's whole value is showing exactly what
        was written, so it is exempt deliberately rather than by accident — and
        this test is what makes the choice visible to whoever changes it next.
        """
        spec = "Feature: sign in\n  Scenario: TASK-ABW-002 the pipeline logs in\n"
        view = ad.build_spec_modal(feature="f", spec_text=spec)
        assert spec in "\n".join(_texts(view))

    def test_a_long_spec_chunks_and_announces_what_it_could_not_show(self) -> None:
        spec = "x" * (2800 * 41)
        view = ad.build_spec_modal(feature="f", spec_text=spec)
        joined = "\n".join(_texts(view))
        assert "Showing the first" in joined
        assert len(view["blocks"]) <= 100

    def test_a_short_spec_announces_nothing(self) -> None:
        joined = "\n".join(_texts(ad.build_spec_modal(feature="f", spec_text=_SPEC_TEXT)))
        assert "Showing the first" not in joined

    def test_chunk_spec_text_keeps_every_character_it_reports(self) -> None:
        chunks, truncated = ad.chunk_spec_text(_SPEC_TEXT)
        assert truncated is False
        assert "".join(chunks) == _SPEC_TEXT

    def test_an_empty_spec_says_where_the_examples_are(self) -> None:
        joined = "\n".join(_texts(ad.build_spec_modal(feature="f", spec_text="")))
        assert "on the run's own branch" in joined

    def test_the_unavailable_view_is_honest_about_what_it_lost(self) -> None:
        joined = "\n".join(_texts(ad.build_spec_unavailable_modal()))
        assert "no longer to hand" in joined
        assert "checked against the examples" in joined


# ---------------------------------------------------------------------------
# The renderer — threading, chunking, and the held examples
# ---------------------------------------------------------------------------
class TestTheRenderer:
    def _renderer(self, spec_texts: SpecTextRegistry | None = None):
        web = AsyncMock()
        web.chat_postMessage = AsyncMock(return_value={"ok": True, "ts": "1700000000.500000"})
        return (
            PlanningCheckpointRenderer(channel_id=_CHANNEL, web_client=web, spec_texts=spec_texts),
            web,
        )

    @pytest.mark.asyncio
    async def test_the_card_is_threaded_under_the_runs_own_anchor(self) -> None:
        renderer, web = self._renderer()
        await renderer.render(
            details=make_digest_details(),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert web.chat_postMessage.await_args.kwargs["thread_ts"] == "1700000000.000100"

    @pytest.mark.asyncio
    async def test_a_wide_spec_posts_one_message_per_chunk(self) -> None:
        renderer, web = self._renderer()
        await renderer.render(
            details=make_digest_details(9),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert web.chat_postMessage.await_count == 2

    @pytest.mark.asyncio
    async def test_the_notification_line_speaks_plainly(self) -> None:
        renderer, web = self._renderer()
        await renderer.render(
            details=make_digest_details(),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        text = web.chat_postMessage.await_args.kwargs["text"]
        assert text == "The spec is ready — here's what will be built"

    @pytest.mark.asyncio
    async def test_the_worked_examples_are_held_before_the_card_is_posted(self) -> None:
        store = SpecTextRegistry()
        renderer, _web = self._renderer(store)
        await renderer.render(
            details=make_digest_details(),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        held = store.get("req-1")
        assert held is not None
        assert held.spec_text == _SPEC_TEXT
        assert held.feature == "version-endpoint"

    @pytest.mark.asyncio
    async def test_an_assumption_checkpoint_holds_nothing(self) -> None:
        store = SpecTextRegistry()
        renderer, _web = self._renderer(store)
        await renderer.render(
            details=make_details(2),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert store.get("req-1") is None

    @pytest.mark.asyncio
    async def test_an_unwired_store_still_posts_the_card(self) -> None:
        renderer, web = self._renderer(None)
        await renderer.render(
            details=make_digest_details(),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert web.chat_postMessage.await_count == 1


# ---------------------------------------------------------------------------
# Every other checkpoint type is untouched
# ---------------------------------------------------------------------------
class TestUnknownCardTypesKeepTodaysBehaviour:
    @pytest.mark.parametrize("checkpoint_type", ("product_docs", "product_docs_escalated"))
    def test_the_assumption_dialogue_renders_as_before(self, checkpoint_type: str) -> None:
        details = make_details(3, checkpoint_type=checkpoint_type)
        blocks = ad.build_dialogue_blocks(
            details,
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        ids = _action_ids(blocks)
        assert ad.DIGEST_ACTION_IDS.isdisjoint(ids)
        assert ad.ACTION_APPROVE in ids
        assert [b["block_id"] for b in blocks if b["block_id"] in ("A1", "A2", "A3")] == [
            "A1",
            "A2",
            "A3",
        ]

    def test_the_assumption_dialogue_still_chunks_on_assumptions(self) -> None:
        assert ad.chunk_count_for(make_details(9)) == 2

    def test_the_zero_assumption_whole_approval_is_unchanged(self) -> None:
        blocks = ad.build_dialogue_blocks(
            make_details(0),
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        assert _action_ids(blocks) == [ad.ACTION_WHOLE_APPROVE]


# ---------------------------------------------------------------------------
# The shared seam
# ---------------------------------------------------------------------------
class TestSharedSeamWiring:
    def test_one_store_is_wired_into_both_halves(self) -> None:
        """The renderer writes it and the reply handler reads it — one instance."""
        import inspect

        from jarvis.infrastructure import lifecycle as lc

        assert "spec_texts" in inspect.signature(lc.create_planning_checkpoint_renderer).parameters
        assert "spec_texts" in inspect.signature(lc.create_slack_reply_client).parameters
        source = inspect.getsource(lc.build_app_state)
        assert "spec_texts = SpecTextRegistry()" in source
        renderer_call = (
            "create_planning_checkpoint_renderer(\n        config, spec_texts=spec_texts"
        )
        assert renderer_call in source
        assert "spec_texts=spec_texts" in source
