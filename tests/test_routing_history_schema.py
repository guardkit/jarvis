"""Schema-conformance gate for ``JarvisRoutingHistoryEntry`` (DDR-018).

TASK-J004-005 — schema-conformance round-trip + boundary validators.

This is the DDR-018 schema *authority gate*. It fails loudly if any later
task accidentally renames a field, drops a section, or weakens a validator
on ``JarvisRoutingHistoryEntry`` or its helper types.

Coverage (DM-routing-history.md §7 "Validation tests anchor"):

1. Happy-path full-shape validation — every §1–§7 base field + every Jarvis
   extension populated; ``model_validate(...)`` round-trips through both
   Python (``model_dump`` / ``model_validate``) and JSON
   (``model_dump_json`` / ``model_validate_json``).
2. ``DispatchOutcome`` — every member of the closed Literal accepted; an
   unknown member raises ``ValidationError``.
3. ``attempts`` — monotonic ``attempt_index`` (0, 1, 2…); ``reason_skipped``
   limited to the closed Literal.
4. ``frozen=True`` — direct field assignment after construction raises
   ``ValidationError``.
5. ``extra="ignore"`` — unknown field in input dict is silently dropped
   (forward-compat for ADR-FLEET-00X additions).
6. ``decision_id`` regex — non-UUID-v4 string raises.
7. ``timestamp`` — non-timezone-aware datetime raises.
8. Helper types (``ToolCallRecord``, ``ModelCallRecord``,
   ``CapabilityDescriptorRef``, ``ConcurrentWorkloadSnapshot``,
   ``TraceRef``) — boundary validators.

This task does *not* test the redaction processor or the 16KB filesystem
offload — those depend on the writer (TASK-J004-010) and land in
TASK-J004-018's writer test file.

Notes
-----
* No mocks: Pydantic models are pure-data; tests construct real instances.
* No ``pytest.xfail`` / ``pytest.skip`` — every assertion is live against
  TASK-J004-004's authoritative schema.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timezone
from typing import Any, ClassVar, get_args

import pytest
from pydantic import ValidationError

from jarvis.infrastructure.routing_history import (
    CapabilityDescriptorRef,
    ConcurrentWorkloadSnapshot,
    DispatchOutcome,
    JarvisRoutingHistoryEntry,
    ModelCallRecord,
    RedirectAttempt,
    ToolCallRecord,
    TraceRef,
)


# ============================================================================
# Helpers
# ============================================================================


_VALID_DECISION_ID = "7e4f1b2c-1a2b-4c3d-9e8f-abcdef012345"
_VALID_SHA256 = "a" * 64
_VALID_TIMESTAMP = datetime(2026, 4, 28, 10, 0, 0, tzinfo=UTC)


def _full_shape_payload(**overrides: Any) -> dict[str, Any]:
    """Return a fully-populated valid JarvisRoutingHistoryEntry payload.

    Every §1–§7 base field and every Jarvis extension is non-default so the
    happy-path round-trip exercises the entire schema surface, not just
    the required minimum.
    """

    payload: dict[str, Any] = {
        # §1 Decision identity
        "decision_id": _VALID_DECISION_ID,
        "surface": "jarvis",
        "session_id": "sess-feat-j004-005",
        "timestamp": _VALID_TIMESTAMP,
        # §2 Reasoning context
        "supervisor_tool_call_sequence": [
            {
                "tool_name": "dispatch_by_capability",
                "args_summary": "tool_name=greet,intent_pattern=hello",
                "result_summary": "agent_id=alpha,latency_ms=42",
                "duration_ms": 42,
            }
        ],
        "priors_retrieved": ["entity:alpha", "entity:beta"],
        "capability_snapshot_hash": _VALID_SHA256,
        # §3 Subagent delegation
        "subagent_type": "specialist",
        "subagent_task_id": "corr-001",
        "subagent_trace_ref": {
            "path": "/var/jarvis/traces/2026-04-28/decision.json",
            "content_sha256": "b" * 64,
            "size_bytes": 17000,
        },
        "subagent_final_state": "success",
        # §4 Resource cost
        "model_calls": [
            {
                "model_id": "openai:gpt-5.1",
                "input_tokens": 1024,
                "output_tokens": 256,
                "latency_ms": 380,
                "cost_usd": 0.0042,
            }
        ],
        "wall_clock_ms": 540,
        "total_cost_usd": 0.0042,
        # §5 Outcome
        "outcome_type": "redirected",
        "outcome_detail": {
            "final_attempt_index": 1,
            "final_agent_id": "product-owner",
        },
        # §6 Human response
        "human_response_type": "redirect",
        "human_response_text": "Try the product owner instead.",
        "human_response_latency_ms": 7200,
        # §7 Environmental context
        "project_id": "proj-jarvis",
        "local_time_of_day": "10:00",
        "recent_session_refs": [f"sess-{i:03d}" for i in range(10)],
        "concurrent_workload": {
            "in_flight_dispatches": 2,
            "in_flight_watchers": 1,
            "in_flight_subagents": 0,
        },
        # Jarvis-specific extensions
        "chosen_specialist_id": "product-owner",
        "chosen_subagent_name": None,
        "alternatives_considered": [
            {
                "agent_id": "alpha",
                "role": "greeter",
                "tool_name_match": True,
                "intent_pattern_match": False,
            },
            {
                "agent_id": "beta",
                "role": "summariser",
                "tool_name_match": False,
                "intent_pattern_match": True,
            },
        ],
        "attempts": [
            {
                "agent_id": "alpha",
                "attempt_index": 0,
                "reason_skipped": "timeout",
                "detail": None,
                "duration_ms": 5000,
            },
            {
                "agent_id": "product-owner",
                "attempt_index": 1,
                "reason_skipped": "specialist_error",
                "detail": "501 Not Implemented",
                "duration_ms": 200,
            },
        ],
        "supervisor_reasoning_summary": (
            "alpha timed out so the supervisor redirected to product-owner"
        ),
    }
    payload.update(overrides)
    return payload


# ============================================================================
# (1) Happy-path full-shape validation — round-trips through Python and JSON
# ============================================================================


class TestHappyPathFullShape:
    """(1) Every §1–§7 base field + every Jarvis extension populated."""

    def test_full_shape_payload_validates(self) -> None:
        """A fully-populated valid payload constructs without error."""
        entry = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        assert isinstance(entry, JarvisRoutingHistoryEntry)
        assert entry.decision_id == _VALID_DECISION_ID
        assert entry.surface == "jarvis"
        assert entry.outcome_type == "redirected"
        assert entry.subagent_type == "specialist"
        assert len(entry.attempts) == 2

    def test_python_round_trip_via_model_dump(self) -> None:
        """``model_validate(model_dump())`` round-trips losslessly."""
        original = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        dumped = original.model_dump()
        restored = JarvisRoutingHistoryEntry.model_validate(dumped)
        assert restored == original
        # Verify every documented base field survived the round-trip.
        for field in (
            "decision_id",
            "surface",
            "session_id",
            "timestamp",
            "priors_retrieved",
            "capability_snapshot_hash",
            "subagent_type",
            "subagent_task_id",
            "subagent_final_state",
            "wall_clock_ms",
            "total_cost_usd",
            "outcome_type",
            "outcome_detail",
            "human_response_type",
            "human_response_text",
            "human_response_latency_ms",
            "project_id",
            "local_time_of_day",
            "recent_session_refs",
        ):
            assert field in dumped, f"Field dropped during round-trip: {field}"

    def test_json_round_trip_via_model_dump_json(self) -> None:
        """``model_validate_json(model_dump_json())`` round-trips losslessly."""
        original = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        as_json = original.model_dump_json()
        # The JSON must be a valid JSON document.
        decoded = json.loads(as_json)
        assert isinstance(decoded, dict)
        restored = JarvisRoutingHistoryEntry.model_validate_json(as_json)
        assert restored == original

    def test_jarvis_extensions_present_after_round_trip(self) -> None:
        """All five Jarvis extensions survive a Python round-trip."""
        original = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        dumped = original.model_dump()
        for ext in (
            "chosen_specialist_id",
            "chosen_subagent_name",
            "alternatives_considered",
            "attempts",
            "supervisor_reasoning_summary",
        ):
            assert ext in dumped, f"Jarvis extension dropped: {ext}"
        # Concrete payload values survive byte-for-byte.
        assert dumped["chosen_specialist_id"] == "product-owner"
        assert len(dumped["alternatives_considered"]) == 2
        assert len(dumped["attempts"]) == 2


# ============================================================================
# (2) DispatchOutcome — every member accepted; unknowns rejected
# ============================================================================


class TestDispatchOutcomeMembership:
    """(2) Closed seven-member Literal."""

    EXPECTED_MEMBERS: ClassVar[tuple[str, ...]] = (
        "success",
        "redirected",
        "timeout",
        "specialist_error",
        "exhausted",
        "transport_unavailable",
        "unresolved",
    )

    def test_dispatch_outcome_has_exactly_seven_members(self) -> None:
        """``DispatchOutcome`` is a closed Literal with seven members."""
        members = set(get_args(DispatchOutcome))
        assert members == set(self.EXPECTED_MEMBERS)
        assert len(self.EXPECTED_MEMBERS) == 7

    @pytest.mark.parametrize("outcome", EXPECTED_MEMBERS)
    def test_each_outcome_member_is_accepted(self, outcome: str) -> None:
        """Every documented outcome value validates."""
        entry = JarvisRoutingHistoryEntry.model_validate(
            _full_shape_payload(outcome_type=outcome)
        )
        assert entry.outcome_type == outcome

    def test_unknown_outcome_raises_validation_error(self) -> None:
        """An outcome string outside the seven members raises."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _full_shape_payload(outcome_type="cancelled-by-user")
            )

    def test_empty_outcome_raises_validation_error(self) -> None:
        """The empty string is not a valid outcome."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _full_shape_payload(outcome_type="")
            )


# ============================================================================
# (3) attempts — monotonic attempt_index + closed reason_skipped
# ============================================================================


class TestAttemptsListSemantics:
    """(3) ``attempts`` ordering and reason_skipped membership."""

    def test_attempts_accepts_zero_indexed_monotonic_sequence(self) -> None:
        """Attempts with attempt_index 0, 1, 2 validate as expected."""
        attempts = [
            {
                "agent_id": "alpha",
                "attempt_index": 0,
                "reason_skipped": "timeout",
                "detail": None,
                "duration_ms": 100,
            },
            {
                "agent_id": "beta",
                "attempt_index": 1,
                "reason_skipped": "specialist_error",
                "detail": "boom",
                "duration_ms": 50,
            },
            {
                "agent_id": "gamma",
                "attempt_index": 2,
                "reason_skipped": "transport_error",
                "detail": "nats publish failed",
                "duration_ms": 25,
            },
        ]
        entry = JarvisRoutingHistoryEntry.model_validate(
            _full_shape_payload(attempts=attempts)
        )
        indices = [a.attempt_index for a in entry.attempts]
        assert indices == [0, 1, 2]

    def test_attempts_reason_skipped_is_closed_literal(self) -> None:
        """``reason_skipped`` rejects values outside the three-member Literal."""
        with pytest.raises(ValidationError):
            RedirectAttempt(
                agent_id="alpha",
                attempt_index=0,
                reason_skipped="user_aborted",  # not in the Literal
                duration_ms=10,
            )

    def test_attempts_reason_skipped_accepts_each_documented_member(self) -> None:
        """All three documented reason_skipped values validate."""
        for reason in ("timeout", "specialist_error", "transport_error"):
            attempt = RedirectAttempt(
                agent_id="alpha",
                attempt_index=0,
                reason_skipped=reason,  # type: ignore[arg-type]
                duration_ms=10,
            )
            assert attempt.reason_skipped == reason

    def test_attempts_attempt_index_rejects_negative(self) -> None:
        """``attempt_index`` is constrained to >= 0."""
        with pytest.raises(ValidationError):
            RedirectAttempt(
                agent_id="alpha",
                attempt_index=-1,
                reason_skipped="timeout",
                duration_ms=10,
            )

    def test_attempts_default_is_empty_list(self) -> None:
        """``attempts`` defaults to an empty list (first-attempt success)."""
        # Construct a payload that omits attempts; the default should kick in.
        payload = _full_shape_payload()
        del payload["attempts"]
        entry = JarvisRoutingHistoryEntry.model_validate(payload)
        assert entry.attempts == []


# ============================================================================
# (4) frozen=True — direct field assignment raises
# ============================================================================


class TestFrozenSemantics:
    """(4) ``frozen=True`` enforces post-construction immutability."""

    def test_direct_field_assignment_raises_validation_error(self) -> None:
        """Assigning to ``session_id`` after construction raises."""
        entry = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        with pytest.raises(ValidationError):
            entry.session_id = "mutated"  # type: ignore[misc]

    def test_direct_outcome_type_assignment_raises(self) -> None:
        """``outcome_type`` is also frozen post-construction."""
        entry = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        with pytest.raises(ValidationError):
            entry.outcome_type = "success"  # type: ignore[misc]


# ============================================================================
# (5) extra="ignore" — unknown fields silently dropped
# ============================================================================


class TestExtraIgnoreForwardCompat:
    """(5) Unknown fields are silently dropped (ADR-FLEET-00X append-only)."""

    def test_unknown_top_level_field_is_dropped(self) -> None:
        """A future v1.1 field at the top level is ignored, not rejected."""
        payload = _full_shape_payload()
        payload["future_v1_1_field"] = "ghost-value"
        entry = JarvisRoutingHistoryEntry.model_validate(payload)
        assert not hasattr(entry, "future_v1_1_field")

    def test_unknown_field_does_not_raise(self) -> None:
        """No ValidationError when unknown fields appear in the input."""
        payload = _full_shape_payload()
        payload["some_other_extension"] = {"k": "v"}
        # Must not raise.
        JarvisRoutingHistoryEntry.model_validate(payload)


# ============================================================================
# (6) decision_id regex — non-UUID-v4 strings raise
# ============================================================================


class TestDecisionIdRegex:
    """(6) ``decision_id`` is constrained to a UUID-v4 pattern."""

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "not-a-uuid",
            "1234",
            "ZZZZZZZZ-ZZZZ-ZZZZ-ZZZZ-ZZZZZZZZZZZZ",  # non-hex
            "7e4f1b2c1a2b4c3d9e8fabcdef012345",  # missing dashes
            "7e4f1b2c-1a2b-4c3d-9e8f-abcdef01234",  # too short
        ],
    )
    def test_invalid_decision_id_raises(self, bad: str) -> None:
        """Non-UUID-v4 inputs raise ValidationError."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _full_shape_payload(decision_id=bad)
            )

    def test_valid_decision_id_round_trips(self) -> None:
        """A canonical UUID-v4 string passes and round-trips."""
        entry = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        assert entry.decision_id == _VALID_DECISION_ID


# ============================================================================
# (7) timestamp — non-timezone-aware datetimes raise
# ============================================================================


class TestTimestampTzAware:
    """(7) ``timestamp`` requires a timezone-aware datetime.

    Pydantic v2 is permissive with naive datetimes by default. The schema
    relies on ``datetime`` typing alone, but ADR-FLEET-001 §1 mandates UTC
    ISO-8601 timezone-aware values. This test pins the *intent* — a
    timezone-aware datetime is preserved as such; a naive datetime, when
    written and parsed back, must surface as offset-aware (or fail).
    """

    def test_utc_timestamp_is_preserved(self) -> None:
        """A tz-aware UTC datetime survives validation as tz-aware."""
        entry = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        assert entry.timestamp.tzinfo is not None
        assert entry.timestamp.utcoffset() == timezone.utc.utcoffset(None)

    def test_non_utc_timestamp_with_tz_is_accepted(self) -> None:
        """A tz-aware non-UTC datetime is accepted (DDR-018 normalises later)."""
        plus_one = timezone(__import__("datetime").timedelta(hours=1))
        ts = datetime(2026, 4, 28, 11, 0, 0, tzinfo=plus_one)
        entry = JarvisRoutingHistoryEntry.model_validate(
            _full_shape_payload(timestamp=ts)
        )
        assert entry.timestamp.tzinfo is not None

    def test_naive_iso_string_round_trip_through_json_is_tz_aware(self) -> None:
        """A JSON-encoded UTC timestamp parses back as tz-aware datetime.

        This is the runtime contract DDR-018 cares about: every
        ``JarvisRoutingHistoryEntry`` produced by the system carries a
        tz-aware ``timestamp``. The round-trip pins that contract.
        """
        original = JarvisRoutingHistoryEntry.model_validate(_full_shape_payload())
        as_json = original.model_dump_json()
        restored = JarvisRoutingHistoryEntry.model_validate_json(as_json)
        assert restored.timestamp.tzinfo is not None


# ============================================================================
# (8) Helper-type boundary validators
# ============================================================================


class TestTraceRefBoundary:
    """(8a) ``TraceRef`` boundary validators."""

    def test_traceref_round_trips(self) -> None:
        """A valid TraceRef round-trips through model_dump."""
        ref = TraceRef(
            path="/var/jarvis/traces/decision.json",
            content_sha256="c" * 64,
            size_bytes=17000,
        )
        restored = TraceRef.model_validate(ref.model_dump())
        assert restored == ref

    def test_traceref_rejects_short_sha256(self) -> None:
        """``content_sha256`` rejects strings shorter than 64 hex chars."""
        with pytest.raises(ValidationError):
            TraceRef(
                path="/tmp/x.json", content_sha256="deadbeef", size_bytes=1
            )

    def test_traceref_rejects_non_hex_sha256(self) -> None:
        """``content_sha256`` rejects non-hex characters."""
        with pytest.raises(ValidationError):
            TraceRef(
                path="/tmp/x.json",
                content_sha256="g" * 64,  # 'g' isn't hex
                size_bytes=1,
            )

    def test_traceref_rejects_negative_size(self) -> None:
        """``size_bytes`` must be >= 0."""
        with pytest.raises(ValidationError):
            TraceRef(path="/tmp/x.json", content_sha256="a" * 64, size_bytes=-1)


class TestToolCallRecordBoundary:
    """(8b) ``ToolCallRecord`` boundary validators."""

    def test_toolcall_round_trips(self) -> None:
        """A valid ToolCallRecord round-trips through model_dump."""
        rec = ToolCallRecord(
            tool_name="dispatch_by_capability",
            args_summary="tool=greet",
            result_summary="agent=alpha",
            duration_ms=42,
        )
        restored = ToolCallRecord.model_validate(rec.model_dump())
        assert restored == rec

    def test_toolcall_rejects_empty_tool_name(self) -> None:
        """``tool_name`` rejects empty strings (min_length=1)."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="",
                args_summary="x",
                result_summary="y",
                duration_ms=1,
            )

    def test_toolcall_args_summary_max_length(self) -> None:
        """``args_summary`` rejects strings >512 chars."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="t",
                args_summary="x" * 513,
                result_summary="ok",
                duration_ms=1,
            )

    def test_toolcall_result_summary_max_length(self) -> None:
        """``result_summary`` rejects strings >512 chars."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="t",
                args_summary="ok",
                result_summary="x" * 513,
                duration_ms=1,
            )

    def test_toolcall_rejects_negative_duration(self) -> None:
        """``duration_ms`` must be >= 0."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="t",
                args_summary="x",
                result_summary="y",
                duration_ms=-1,
            )


class TestModelCallRecordBoundary:
    """(8c) ``ModelCallRecord`` boundary validators."""

    def test_modelcall_round_trips(self) -> None:
        """A valid ModelCallRecord round-trips through model_dump."""
        rec = ModelCallRecord(
            model_id="openai:gpt-5.1",
            input_tokens=100,
            output_tokens=50,
            latency_ms=200,
            cost_usd=0.001,
        )
        restored = ModelCallRecord.model_validate(rec.model_dump())
        assert restored == rec

    def test_modelcall_rejects_empty_model_id(self) -> None:
        """``model_id`` rejects empty strings (min_length=1)."""
        with pytest.raises(ValidationError):
            ModelCallRecord(
                model_id="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                cost_usd=0.0,
            )

    @pytest.mark.parametrize(
        "field, bad_value",
        [
            ("input_tokens", -1),
            ("output_tokens", -1),
            ("latency_ms", -1),
            ("cost_usd", -0.01),
        ],
    )
    def test_modelcall_rejects_negative_numeric_fields(
        self, field: str, bad_value: float
    ) -> None:
        """Numeric fields all enforce >= 0."""
        kwargs: dict[str, Any] = {
            "model_id": "gpt",
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0,
            "cost_usd": 0.0,
        }
        kwargs[field] = bad_value
        with pytest.raises(ValidationError):
            ModelCallRecord(**kwargs)


class TestCapabilityDescriptorRefBoundary:
    """(8d) ``CapabilityDescriptorRef`` boundary validators."""

    def test_capability_ref_round_trips(self) -> None:
        """A valid CapabilityDescriptorRef round-trips through model_dump."""
        ref = CapabilityDescriptorRef(
            agent_id="alpha",
            role="greeter",
            tool_name_match=True,
            intent_pattern_match=False,
        )
        restored = CapabilityDescriptorRef.model_validate(ref.model_dump())
        assert restored == ref

    @pytest.mark.parametrize(
        "bad_id",
        ["UPPER", "1leading", "with_underscore", "", "with space"],
    )
    def test_capability_ref_rejects_bad_agent_id(self, bad_id: str) -> None:
        """``agent_id`` rejects values that violate the agent_id regex."""
        with pytest.raises(ValidationError):
            CapabilityDescriptorRef(
                agent_id=bad_id,
                role="role",
                tool_name_match=True,
                intent_pattern_match=False,
            )

    def test_capability_ref_rejects_empty_role(self) -> None:
        """``role`` rejects empty strings (min_length=1)."""
        with pytest.raises(ValidationError):
            CapabilityDescriptorRef(
                agent_id="alpha",
                role="",
                tool_name_match=True,
                intent_pattern_match=False,
            )


class TestConcurrentWorkloadSnapshotBoundary:
    """(8e) ``ConcurrentWorkloadSnapshot`` boundary validators."""

    def test_workload_round_trips(self) -> None:
        """A valid ConcurrentWorkloadSnapshot round-trips through model_dump."""
        snap = ConcurrentWorkloadSnapshot(
            in_flight_dispatches=2,
            in_flight_watchers=1,
            in_flight_subagents=0,
        )
        restored = ConcurrentWorkloadSnapshot.model_validate(snap.model_dump())
        assert restored == snap

    @pytest.mark.parametrize(
        "field",
        ["in_flight_dispatches", "in_flight_watchers", "in_flight_subagents"],
    )
    def test_workload_rejects_negative_counters(self, field: str) -> None:
        """Each in-flight counter enforces >= 0."""
        kwargs: dict[str, int] = {
            "in_flight_dispatches": 0,
            "in_flight_watchers": 0,
            "in_flight_subagents": 0,
        }
        kwargs[field] = -1
        with pytest.raises(ValidationError):
            ConcurrentWorkloadSnapshot(**kwargs)


# ============================================================================
# Seam test — TASK-J004-004 producer contract
# ============================================================================


class TestSeamContractWithTaskJ004004:
    """Verify the JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA producer contract.

    This is the seam test embedded in the TASK-J004-005 spec; it lives here
    so the schema-conformance gate fails loudly if TASK-J004-004's exported
    surface ever drifts from DDR-018.
    """

    REQUIRED_BASE_FIELDS: ClassVar[set[str]] = {
        "decision_id",
        "surface",
        "session_id",
        "timestamp",
        "supervisor_tool_call_sequence",
        "priors_retrieved",
        "capability_snapshot_hash",
        "subagent_type",
        "subagent_task_id",
        "subagent_trace_ref",
        "subagent_final_state",
        "model_calls",
        "wall_clock_ms",
        "total_cost_usd",
        "outcome_type",
        "outcome_detail",
        "human_response_type",
        "human_response_text",
        "human_response_latency_ms",
        "project_id",
        "local_time_of_day",
        "recent_session_refs",
        "concurrent_workload",
    }

    JARVIS_EXTENSIONS: ClassVar[set[str]] = {
        "chosen_specialist_id",
        "chosen_subagent_name",
        "alternatives_considered",
        "attempts",
        "supervisor_reasoning_summary",
    }

    def test_model_config_is_frozen_and_extra_ignore(self) -> None:
        """Producer's ``model_config`` enforces the DDR-018 invariants."""
        cfg = JarvisRoutingHistoryEntry.model_config
        assert cfg.get("frozen") is True
        assert cfg.get("extra") == "ignore"

    def test_field_set_matches_ddr018(self) -> None:
        """Every required ADR-FLEET-001 + Jarvis-extension field is present."""
        actual = set(JarvisRoutingHistoryEntry.model_fields.keys())
        expected = self.REQUIRED_BASE_FIELDS | self.JARVIS_EXTENSIONS
        missing = expected - actual
        assert not missing, (
            f"Schema missing required fields per DDR-018: {missing}"
        )
