"""FEAT-SPL-003 cross-cutting contract suite (TASK-SPL003-J04).

Pins the wire bytes against the **installed** ``nats_core`` (0.6.0+ — the
structured ``dispositions`` field), pins the forge ``details`` contract fixture
that TASK-SPL003F-001 (forge half) must satisfy, and cross-checks the aggregate
decision rule + the disposition vocabulary drift guard (red-team F7). Hermetic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nats_core.events import (
    ApprovalResponsePayload,
    AssumptionDisposition,
    NotificationPayload,
)

from jarvis.infrastructure import assumption_dialogue as ad

_FIXTURE = Path(__file__).parent / "fixtures" / "spl003_forge_details.json"
_SUBJECT = "agents.approval.forge.plan-4d5e205f"


def _load_details() -> dict[str, Any]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. ApprovalResponsePayload.dispositions round-trip + vocabulary guard
# ---------------------------------------------------------------------------


class TestDispositionsRoundTrip:
    def test_dispositions_round_trip_through_installed_nats_core(self) -> None:
        response = ApprovalResponsePayload(
            request_id="req-1",
            decision="defer",
            decided_by="U03QR8WKT29",
            dispositions=[
                AssumptionDisposition(assumption_id="ASSUM-P1", disposition="accepted"),
                AssumptionDisposition(
                    assumption_id="ASSUM-P2", disposition="modified", edit_delta="Use SQLite."
                ),
                AssumptionDisposition(assumption_id="ASSUM-P3", disposition="deferred"),
            ],
        )
        decoded = ApprovalResponsePayload.model_validate_json(response.model_dump_json())
        assert decoded.dispositions is not None
        by_id = {d.assumption_id: d for d in decoded.dispositions}
        assert set(by_id) == {"ASSUM-P1", "ASSUM-P2", "ASSUM-P3"}
        assert by_id["ASSUM-P1"].disposition == "accepted"
        assert by_id["ASSUM-P2"].disposition == "modified"
        assert by_id["ASSUM-P2"].edit_delta == "Use SQLite."
        assert by_id["ASSUM-P3"].disposition == "deferred"

    def test_synonym_map_normalises_ux_verbs(self) -> None:
        # approve→accepted, edit→modified, defer→deferred on input.
        assert (
            AssumptionDisposition(assumption_id="a", disposition="approve").disposition
            == "accepted"
        )
        assert (
            AssumptionDisposition(assumption_id="a", disposition="edit").disposition == "modified"
        )
        assert (
            AssumptionDisposition(assumption_id="a", disposition="defer").disposition == "deferred"
        )

    def test_vocabulary_guard_no_forbidden_words_on_wire(self) -> None:
        """The wire never carries confirmed/overridden/per-item rejected (F7)."""
        response = ApprovalResponsePayload(
            request_id="req-1",
            decision="approve",
            decided_by="U03QR8WKT29",
            dispositions=[
                AssumptionDisposition(assumption_id="ASSUM-P1", disposition="accepted"),
                AssumptionDisposition(
                    assumption_id="ASSUM-P2", disposition="modified", edit_delta="x"
                ),
            ],
        )
        wire = response.model_dump_json()
        for forbidden in ("confirmed", "overridden"):
            assert forbidden not in wire
        # no per-item disposition is "rejected" (whole-run reject is the
        # aggregate decision, never a per-assumption disposition here)
        dumped = json.loads(wire)
        assert all(d["disposition"] != "rejected" for d in dumped["dispositions"])

    def test_dispositions_optional_defaults_none(self) -> None:
        """A build/other gate omits dispositions and still validates (migration)."""
        response = ApprovalResponsePayload(
            request_id="req-1", decision="approve", decided_by="U03QR8WKT29"
        )
        assert response.dispositions is None
        decoded = ApprovalResponsePayload.model_validate_json(response.model_dump_json())
        assert decoded.dispositions is None


# ---------------------------------------------------------------------------
# 2. Aggregate decision rule (ASSUM-006) matches the ApprovalResponsePayload enum
# ---------------------------------------------------------------------------


class TestAggregateDecisionRule:
    def test_all_accepted_is_approve(self) -> None:
        state = {"a": {"disposition": "accepted"}, "b": {"disposition": "accepted"}}
        assert ad.aggregate_decision(state) == "approve"

    def test_any_modified_none_deferred_is_approve(self) -> None:
        state = {"a": {"disposition": "accepted"}, "b": {"disposition": "modified"}}
        assert ad.aggregate_decision(state) == "approve"

    def test_any_deferred_is_defer(self) -> None:
        state = {"a": {"disposition": "accepted"}, "b": {"disposition": "deferred"}}
        assert ad.aggregate_decision(state) == "defer"

    def test_decision_literals_valid_against_payload(self) -> None:
        for decision in ("approve", "defer", "reject"):
            payload = ApprovalResponsePayload(
                request_id="r", decision=decision, decided_by="U03QR8WKT29"
            )
            assert payload.decision == decision


# ---------------------------------------------------------------------------
# 3. NotificationPayload optional round-trip fields (J01/J02 anchor)
# ---------------------------------------------------------------------------


class TestNotificationPayloadRoundTrip:
    def test_anchor_fields_survive_round_trip(self) -> None:
        payload = NotificationPayload(
            message="Planning handoff reached",
            adapter="slack",
            correlation_id="cid123",
            thread_ts="1700000000.000100",
            parent_request_id="1700000000.000100",
            target_user="U03QR8WKT29",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "hi"}}],
        )
        decoded = NotificationPayload.model_validate_json(payload.model_dump_json())
        assert decoded.parent_request_id == "1700000000.000100"
        assert decoded.thread_ts == "1700000000.000100"
        assert decoded.target_user == "U03QR8WKT29"
        assert decoded.blocks and decoded.blocks[0]["type"] == "section"

    def test_bare_payload_without_anchor_parses(self) -> None:
        payload = NotificationPayload(message="thin update", adapter="slack")
        decoded = NotificationPayload.model_validate_json(payload.model_dump_json())
        assert decoded.parent_request_id is None
        assert decoded.thread_ts is None
        assert decoded.blocks is None


# ---------------------------------------------------------------------------
# 4. The forge details contract fixture renders end-to-end in J02
# ---------------------------------------------------------------------------


class TestForgeDetailsFixture:
    def test_fixture_is_a_planning_checkpoint(self) -> None:
        details = _load_details()
        assert ad.is_planning_checkpoint(details)
        assert details["build_id"].startswith("plan-")
        assert details["feature_id"] == "FEAT-PLANNING"

    def test_fixture_renders_per_assumption_prompt(self) -> None:
        details = _load_details()
        blocks = ad.build_dialogue_blocks(
            details,
            correlation_id="cid123",
            request_id="req-1",
            approval_subject=_SUBJECT,
        )
        state = ad.parse_dialogue_blocks(blocks)
        assert set(state) == {"ASSUM-P1", "ASSUM-P2", "ASSUM-P3"}
        # each item offers exactly approve/edit/defer
        for aid in state:
            act = next(b for b in blocks if b.get("block_id") == f"{aid}::act")
            assert [el["action_id"] for el in act["elements"]] == [
                ad.ACTION_APPROVE,
                ad.ACTION_EDIT,
                ad.ACTION_DEFER,
            ]
        # value carries approval_subject, never the assumption text
        act = next(b for b in blocks if b.get("block_id") == "ASSUM-P1::act")
        value = json.loads(act["elements"][0]["value"])
        assert value["approval_subject"] == _SUBJECT
        assert "REST" not in act["elements"][0]["value"]

    def test_fixture_dispositions_publishable(self) -> None:
        """A full decision over the fixture validates as a nats_core payload."""
        details = _load_details()
        state = {
            a["id"]: {"disposition": "accepted", "edit_delta": None}
            for a in details["summary"]["assumptions"]
        }
        dispositions = [
            AssumptionDisposition(
                assumption_id=aid, disposition=item["disposition"], edit_delta=item["edit_delta"]
            )
            for aid, item in state.items()
        ]
        response = ApprovalResponsePayload(
            request_id="req-1",
            decision=ad.aggregate_decision(state),
            decided_by=details["expected_approver"],
            dispositions=dispositions,
        )
        decoded = ApprovalResponsePayload.model_validate_json(response.model_dump_json())
        assert decoded.decision == "approve"
        assert decoded.dispositions is not None
        assert len(decoded.dispositions) == 3
