"""Unit tests for the FEAT-SPL-003 assumption-dialogue render/parse contract.

TASK-SPL003-J02 — the shared block encoding (``build_dialogue_blocks``) and its
inverse (``parse_dialogue_blocks`` / ``apply_disposition`` / ``is_complete``)
live in one module so encode and decode can never drift (§4). These tests pin
the per-item shape, the anti-rubber-stamp invariants (no approve-all; one
control decides at most one assumption), chunking, the zero-item whole-approval,
escalation, and the machine-readable state round-trip. Fully hermetic — no
Slack, no NATS.
"""

from __future__ import annotations

import json
from typing import Any

from jarvis.infrastructure import assumption_dialogue as ad

_SUBJECT = "agents.approval.forge.plan-cid123"


def make_details(
    n: int = 3,
    *,
    checkpoint_type: str = "product_docs",
    cycle: int = 1,
    attempt_count: int = 1,
    parent_request_id: str | None = "1700000000.000100",
    expected_approver: str = "U_RICH",
    confidences: list[str] | None = None,
    texts: list[str] | None = None,
) -> dict[str, Any]:
    assumptions = [
        {
            "id": f"A{i + 1}",
            "text": (texts[i] if texts else f"Assumption {i + 1} proposed text"),
            "confidence": (confidences[i] if confidences else "medium"),
            "basis": f"basis {i + 1}",
        }
        for i in range(n)
    ]
    details: dict[str, Any] = {
        "build_id": "plan-cid123",
        "feature_id": "FEAT-PLANNING",
        "checkpoint_type": checkpoint_type,
        "expected_approver": expected_approver,
        "attempt_count": attempt_count,
        "cycle": cycle,
        "summary": {"assumptions": assumptions},
    }
    if parent_request_id is not None:
        details["parent_request_id"] = parent_request_id
    return details


def build(details: dict[str, Any], **kw: Any) -> list[dict[str, Any]]:
    return ad.build_dialogue_blocks(
        details,
        correlation_id="cid123",
        request_id="req-1",
        approval_subject=_SUBJECT,
        **kw,
    )


def _sections(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "section"]


def _actions(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in blocks if b.get("type") == "actions"]


def _all_action_ids(blocks: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for b in blocks:
        for el in b.get("elements") or []:
            if "action_id" in el:
                ids.append(el["action_id"])
    return ids


# --- detection --------------------------------------------------------------


class TestDetection:
    def test_product_docs_is_planning(self) -> None:
        assert ad.is_planning_checkpoint(make_details()) is True

    def test_escalated_type_is_planning(self) -> None:
        assert ad.is_planning_checkpoint(make_details(checkpoint_type="product_docs_escalated"))

    def test_non_planning_checkpoint(self) -> None:
        assert ad.is_planning_checkpoint({"checkpoint_type": "build_gate"}) is False

    def test_missing_checkpoint_type(self) -> None:
        assert ad.is_planning_checkpoint({}) is False
        assert ad.is_planning_checkpoint(None) is False

    def test_escalated_by_type(self) -> None:
        assert ad.is_escalated(make_details(checkpoint_type="product_docs_escalated"))

    def test_escalated_by_attempt_cap(self) -> None:
        assert ad.is_escalated(make_details(attempt_count=3))

    def test_not_escalated_below_cap(self) -> None:
        assert ad.is_escalated(make_details(attempt_count=2)) is False


# --- per-item shape ---------------------------------------------------------


class TestPerItemShape:
    def test_one_item_per_assumption_with_three_choices(self) -> None:
        blocks = build(make_details(3))
        # one section (block_id == assumption_id) + one actions block per item
        item_sections = [b for b in _sections(blocks) if b["block_id"] in ("A1", "A2", "A3")]
        assert len(item_sections) == 3
        for aid in ("A1", "A2", "A3"):
            act = [b for b in _actions(blocks) if b["block_id"] == f"{aid}::act"]
            assert len(act) == 1
            action_ids = [el["action_id"] for el in act[0]["elements"]]
            assert action_ids == [
                ad.ACTION_APPROVE,
                ad.ACTION_EDIT,
                ad.ACTION_DEFER,
            ]

    def test_confidence_tag_shown(self) -> None:
        blocks = build(make_details(1, confidences=["low"]))
        section = next(b for b in _sections(blocks) if b["block_id"] == "A1")
        assert "confidence: low" in section["text"]["text"]

    def test_block_id_equals_assumption_id(self) -> None:
        blocks = build(make_details(2))
        assert {b["block_id"] for b in _sections(blocks) if b["block_id"].startswith("A")} == {
            "A1",
            "A2",
        }


class TestValueEncoding:
    def test_value_under_limit_and_carries_subject(self) -> None:
        blocks = build(make_details(1))
        act = next(b for b in _actions(blocks) if b["block_id"] == "A1::act")
        value = act["elements"][0]["value"]
        assert len(value) < ad._SLACK_ACTION_VALUE_LIMIT
        parsed = json.loads(value)
        assert parsed["approval_subject"] == _SUBJECT
        assert parsed["request_id"] == "req-1"
        assert parsed["assumption_id"] == "A1"
        assert parsed["cycle"] == 1

    def test_value_never_carries_assumption_text(self) -> None:
        blocks = build(make_details(1, texts=["SECRET-ASSUMPTION-TEXT"]))
        act = next(b for b in _actions(blocks) if b["block_id"] == "A1::act")
        for el in act["elements"]:
            assert "SECRET-ASSUMPTION-TEXT" not in el["value"]


class TestAntiRubberStamp:
    def test_no_approve_all_control(self) -> None:
        blocks = build(make_details(4))
        assert ad.ACTION_WHOLE_APPROVE not in _all_action_ids(blocks)

    def test_every_decision_button_decides_one_assumption(self) -> None:
        blocks = build(make_details(3))
        # each actions block for an item carries buttons whose value names
        # exactly one assumption_id (the block's own).
        for aid in ("A1", "A2", "A3"):
            act = next(b for b in _actions(blocks) if b["block_id"] == f"{aid}::act")
            for el in act["elements"]:
                assert json.loads(el["value"])["assumption_id"] == aid

    def test_cancel_is_overflow_abort_not_decision(self) -> None:
        blocks = build(make_details(3))
        cancel_ids = [
            el["action_id"]
            for b in blocks
            for el in b.get("elements") or []
            if el.get("action_id") == ad.ACTION_CANCEL
        ]
        assert cancel_ids == [ad.ACTION_CANCEL]
        # the cancel element is an overflow menu, not a plain button
        cancel_el = next(
            el
            for b in blocks
            for el in b.get("elements") or []
            if el.get("action_id") == ad.ACTION_CANCEL
        )
        assert cancel_el["type"] == "overflow"


class TestChunking:
    def test_sixteen_items_two_chunks_none_dropped(self) -> None:
        details = make_details(16)
        assert ad.chunk_count_for(details) == 2
        chunk0 = build(details, chunk_index=0, chunk_count=2)
        chunk1 = build(details, chunk_index=1, chunk_count=2)
        ids0 = {b["block_id"] for b in _sections(chunk0) if b["block_id"].startswith("A")}
        ids1 = {b["block_id"] for b in _sections(chunk1) if b["block_id"].startswith("A")}
        assert len(ids0) == 8 and len(ids1) == 8
        assert ids0 | ids1 == {f"A{i + 1}" for i in range(16)}
        assert ids0.isdisjoint(ids1)

    def test_continued_marker_present_when_chunked(self) -> None:
        chunk1 = build(make_details(16), chunk_index=1, chunk_count=2)
        markers = [
            el["text"] for b in chunk1 if b.get("block_id") == "spl3chunk" for el in b["elements"]
        ]
        assert markers == ["continued (2/2)"]

    def test_single_message_no_continued_marker(self) -> None:
        blocks = build(make_details(3))
        assert all(b.get("block_id") != "spl3chunk" for b in blocks)


class TestZeroAssumptions:
    def test_single_whole_checkpoint_approval(self) -> None:
        blocks = build(make_details(0))
        assert ad.chunk_count_for(make_details(0)) == 1
        action_ids = _all_action_ids(blocks)
        assert action_ids == [ad.ACTION_WHOLE_APPROVE]
        # no per-item sections
        assert not [b for b in _sections(blocks) if b["block_id"].startswith("A")]

    def test_whole_approve_only_when_no_items(self) -> None:
        with_items = build(make_details(2))
        assert ad.ACTION_WHOLE_APPROVE not in _all_action_ids(with_items)


class TestEscalation:
    def test_escalated_mentions_rich_and_shows_cycle_attempt(self) -> None:
        details = make_details(
            2, checkpoint_type="product_docs_escalated", cycle=3, attempt_count=3
        )
        blocks = build(details)
        header = next(b for b in blocks if b.get("block_id") == "spl3hdr")
        text = header["text"]["text"]
        assert "<@U_RICH>" in text
        assert "cycle 3" in text
        assert "attempt 3" in text
        # full item list still rendered
        assert len([b for b in _sections(blocks) if b["block_id"] in ("A1", "A2")]) == 2

    def test_escalation_via_attempt_cap_renders_full_list(self) -> None:
        details = make_details(3, attempt_count=3)
        blocks = build(details)
        header = next(b for b in blocks if b.get("block_id") == "spl3hdr")
        assert "<@U_RICH>" in header["text"]["text"]

    def test_third_cycle_is_normal_prompt(self) -> None:
        # cycle 3 but attempt_count 3 would escalate; a *normal* third cycle has
        # attempt_count below the cap.
        details = make_details(2, cycle=3, attempt_count=2)
        blocks = build(details)
        header = next(b for b in blocks if b.get("block_id") == "spl3hdr")
        assert "<@U_RICH>" not in header["text"]["text"]
        assert "cycle 3" in header["text"]["text"]


class TestOpenQuestionsAsItems:
    def test_open_questions_render_as_decidable_items(self) -> None:
        details = make_details(
            2,
            texts=["Should the API be REST or gRPC?", "Is Postgres acceptable?"],
            confidences=["low", "low"],
        )
        blocks = build(details)
        # rendered as normal per-assumption items with the three choices —
        # jarvis never emits a free-text question element.
        for aid in ("A1", "A2"):
            act = next(b for b in _actions(blocks) if b["block_id"] == f"{aid}::act")
            assert [el["action_id"] for el in act["elements"]] == [
                ad.ACTION_APPROVE,
                ad.ACTION_EDIT,
                ad.ACTION_DEFER,
            ]
        assert not any(b.get("type") == "input" for b in blocks)


# --- parse / apply / completeness round-trip --------------------------------


class TestParseRoundTrip:
    def test_fresh_render_all_undecided(self) -> None:
        blocks = build(make_details(3))
        state = ad.parse_dialogue_blocks(blocks)
        assert set(state) == {"A1", "A2", "A3"}
        assert all(v["disposition"] == "undecided" for v in state.values())

    def test_apply_accepted_preserves_others(self) -> None:
        blocks = build(make_details(3))
        updated = ad.apply_disposition(blocks, assumption_id="A2", disposition="accepted")
        state = ad.parse_dialogue_blocks(updated)
        assert state["A2"]["disposition"] == "accepted"
        assert state["A1"]["disposition"] == "undecided"
        assert state["A3"]["disposition"] == "undecided"

    def test_edit_delta_byte_exact_round_trip(self) -> None:
        long_edit = "X" * 500
        blocks = build(make_details(2))
        updated = ad.apply_disposition(
            blocks, assumption_id="A1", disposition="modified", edit_delta=long_edit
        )
        state = ad.parse_dialogue_blocks(updated)
        assert state["A1"]["disposition"] == "modified"
        assert state["A1"]["edit_delta"] == long_edit

    def test_deferred_disposition(self) -> None:
        blocks = build(make_details(2))
        updated = ad.apply_disposition(blocks, assumption_id="A1", disposition="deferred")
        assert ad.parse_dialogue_blocks(updated)["A1"]["disposition"] == "deferred"

    def test_whole_and_cancel_excluded_from_item_map(self) -> None:
        blocks = build(make_details(2))
        state = ad.parse_dialogue_blocks(blocks)
        assert ad.WHOLE_CHECKPOINT_ID not in state
        assert "spl3cancel" not in state

    def test_zero_assumption_message_has_no_items(self) -> None:
        blocks = build(make_details(0))
        assert ad.parse_dialogue_blocks(blocks) == {}


class TestCompleteness:
    def test_incomplete_while_any_undecided(self) -> None:
        blocks = build(make_details(3))
        one = ad.apply_disposition(blocks, assumption_id="A1", disposition="accepted")
        assert ad.is_complete(one) is False

    def test_complete_when_all_decided(self) -> None:
        blocks = build(make_details(2))
        blocks = ad.apply_disposition(blocks, assumption_id="A1", disposition="accepted")
        blocks = ad.apply_disposition(blocks, assumption_id="A2", disposition="deferred")
        assert ad.is_complete(blocks) is True

    def test_empty_message_not_complete(self) -> None:
        assert ad.is_complete([]) is False
