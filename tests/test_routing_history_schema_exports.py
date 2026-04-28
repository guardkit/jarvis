"""Tests for jarvis.infrastructure.routing_history — declarative schema exports.

TASK-J004-004: JarvisRoutingHistoryEntry Pydantic schema (declarative-only).

Acceptance Criteria:
    AC-001: ``src/jarvis/infrastructure/routing_history.py`` exports the 8
            types listed in DM-routing-history.md.
    AC-002: ``JarvisRoutingHistoryEntry.model_config`` is
            ``ConfigDict(extra="ignore", frozen=True)``.
    AC-003: All Field validators match DM-routing-history.md verbatim
            (regex patterns, max_length, ge/le bounds).
    AC-004: ``DispatchOutcome`` is a closed ``Literal[...]`` with exactly
            the seven members listed.
    AC-005: ``__all__`` exports are explicit.
    AC-006: No writer logic, no filesystem I/O, no Graphiti import in this file.
    AC-007: ``uv run mypy ...`` passes (verified externally).
    AC-008: Lint/format checks pass with zero errors (verified externally).

Note:
    Heavyweight schema-conformance / round-trip / redaction / offload tests
    live in TASK-J004-005 — parallel-safe. This module verifies the
    *declarative* surface only: exports, model_config, validator metadata,
    Literal closure, and the no-writer-no-fs-no-graphiti invariant.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any, ClassVar, get_args

import pytest
from pydantic import BaseModel, ValidationError

import jarvis.infrastructure.routing_history as rh
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
# AC-001 + AC-005: 8 exports + explicit __all__
# ============================================================================


class TestModuleExports:
    """AC-001 and AC-005 — public surface.

    Note: TASK-J004-010 appended ``RoutingHistoryWriter``,
    ``GraphitiClientProtocol`` and ``REDACTION_PLACEHOLDER`` to ``__all__``
    per the writer-lands-here contract spelled out in the module docstring
    and API-internal.md §4. The schema's eight DM-routing-history.md types
    must remain a *subset* of ``__all__``.
    """

    EXPECTED_SCHEMA_EXPORTS: ClassVar[set[str]] = {
        "JarvisRoutingHistoryEntry",
        "DispatchOutcome",
        "RedirectAttempt",
        "TraceRef",
        "ToolCallRecord",
        "ModelCallRecord",
        "CapabilityDescriptorRef",
        "ConcurrentWorkloadSnapshot",
    }

    def test_module_exports_eight_named_types(self) -> None:
        """All 8 types from DM-routing-history.md are importable."""
        for name in self.EXPECTED_SCHEMA_EXPORTS:
            assert hasattr(rh, name), f"Missing export: {name}"

    def test_module_dunder_all_is_explicit(self) -> None:
        """__all__ is declared and is a superset of the schema exports."""
        assert hasattr(rh, "__all__"), "Module must declare __all__"
        missing = self.EXPECTED_SCHEMA_EXPORTS - set(rh.__all__)
        assert not missing, f"__all__ missing schema exports: {missing}"

    def test_basemodel_subclasses_are_pydantic(self) -> None:
        """Every schema-typed export is a Pydantic BaseModel subclass."""
        model_exports = self.EXPECTED_SCHEMA_EXPORTS - {"DispatchOutcome"}
        for name in model_exports:
            obj = getattr(rh, name)
            assert inspect.isclass(obj), f"{name} must be a class"
            assert issubclass(obj, BaseModel), f"{name} must subclass BaseModel"


# ============================================================================
# AC-002: JarvisRoutingHistoryEntry model_config — extra=ignore + frozen=True
# ============================================================================


class TestJarvisRoutingHistoryEntryConfig:
    """AC-002 — model_config = ConfigDict(extra='ignore', frozen=True)."""

    def test_extra_is_ignore(self) -> None:
        """Unknown fields are silently dropped (forward-compat)."""
        cfg = JarvisRoutingHistoryEntry.model_config
        assert cfg.get("extra") == "ignore", (
            f"extra must be 'ignore', got {cfg.get('extra')!r}"
        )

    def test_frozen_is_true(self) -> None:
        """Entries are immutable post-construction (DDR-018)."""
        cfg = JarvisRoutingHistoryEntry.model_config
        assert cfg.get("frozen") is True, (
            f"frozen must be True, got {cfg.get('frozen')!r}"
        )


# ============================================================================
# AC-004: DispatchOutcome closed Literal with exactly 7 members
# ============================================================================


class TestDispatchOutcomeLiteral:
    """AC-004 — closed Literal with the seven canonical members."""

    EXPECTED_MEMBERS: ClassVar[set[str]] = {
        "success",
        "redirected",
        "timeout",
        "specialist_error",
        "exhausted",
        "transport_unavailable",
        "unresolved",
    }

    def test_dispatch_outcome_is_a_literal_alias(self) -> None:
        """DispatchOutcome resolves to typing.Literal."""
        # Literal aliases unwrap via typing.get_args; a proper Literal has args.
        args = get_args(DispatchOutcome)
        assert args, "DispatchOutcome must be a typing.Literal alias"

    def test_dispatch_outcome_has_seven_members(self) -> None:
        """Exactly seven distinct members — no more, no fewer."""
        members = set(get_args(DispatchOutcome))
        assert members == self.EXPECTED_MEMBERS, (
            f"DispatchOutcome members mismatch: extra="
            f"{members - self.EXPECTED_MEMBERS}, missing="
            f"{self.EXPECTED_MEMBERS - members}"
        )


# ============================================================================
# AC-003: Field validators match DM-routing-history.md verbatim
# ============================================================================


class TestFieldValidators:
    """AC-003 — regex patterns, max_length, and ge/le bounds match the spec."""

    # ---- JarvisRoutingHistoryEntry ----

    def test_decision_id_uses_uuid_regex(self) -> None:
        """decision_id is constrained to a UUIDv4 pattern."""
        bad_uuid_inputs = ["", "abc", "not-a-uuid", "X" * 36]
        for bad in bad_uuid_inputs:
            with pytest.raises(ValidationError):
                JarvisRoutingHistoryEntry.model_validate(
                    _entry_payload(decision_id=bad)
                )

    def test_decision_id_accepts_valid_uuid(self) -> None:
        """A canonical lowercase UUIDv4 string passes validation."""
        valid = "7e4f1b2c-1a2b-4c3d-9e8f-abcdef012345"
        entry = JarvisRoutingHistoryEntry.model_validate(
            _entry_payload(decision_id=valid)
        )
        assert entry.decision_id == valid

    def test_surface_is_jarvis_literal(self) -> None:
        """surface is a Literal['jarvis'] with default 'jarvis'."""
        entry = JarvisRoutingHistoryEntry.model_validate(_entry_payload())
        assert entry.surface == "jarvis"
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(surface="other")
            )

    def test_session_id_has_min_length_one(self) -> None:
        """session_id rejects the empty string."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(_entry_payload(session_id=""))

    def test_capability_snapshot_hash_uses_sha256_regex(self) -> None:
        """capability_snapshot_hash matches a 64-char hex SHA-256."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(capability_snapshot_hash="not-hex")
            )
        good = "a" * 64
        entry = JarvisRoutingHistoryEntry.model_validate(
            _entry_payload(capability_snapshot_hash=good)
        )
        assert entry.capability_snapshot_hash == good

    def test_subagent_type_closed_literal(self) -> None:
        """subagent_type rejects values outside the three approved members."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(subagent_type="frontier")
            )

    def test_subagent_final_state_closed_literal(self) -> None:
        """subagent_final_state rejects values outside its four members."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(subagent_final_state="unknown")
            )

    def test_wall_clock_ms_ge_zero(self) -> None:
        """wall_clock_ms rejects negative values."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(wall_clock_ms=-1)
            )

    def test_total_cost_usd_ge_zero(self) -> None:
        """total_cost_usd rejects negative values."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(total_cost_usd=-0.01)
            )

    def test_human_response_text_max_length_4096(self) -> None:
        """human_response_text rejects strings longer than 4096 chars."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(human_response_text="x" * 4097)
            )

    def test_human_response_latency_ms_ge_zero(self) -> None:
        """human_response_latency_ms rejects negative values."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(human_response_latency_ms=-1)
            )

    def test_local_time_of_day_pattern(self) -> None:
        """local_time_of_day matches HH:MM only."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(local_time_of_day="9:00")
            )
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(local_time_of_day="25:00")
            )
        entry = JarvisRoutingHistoryEntry.model_validate(
            _entry_payload(local_time_of_day="09:30")
        )
        assert entry.local_time_of_day == "09:30"

    def test_recent_session_refs_max_length_ten(self) -> None:
        """recent_session_refs rejects more than 10 entries."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(recent_session_refs=[f"sess-{i}" for i in range(11)])
            )

    def test_chosen_specialist_id_pattern(self) -> None:
        """chosen_specialist_id matches the agent_id pattern when provided."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(chosen_specialist_id="UPPERCASE")
            )

    def test_supervisor_reasoning_summary_max_length_1024(self) -> None:
        """supervisor_reasoning_summary rejects strings >1024 chars."""
        with pytest.raises(ValidationError):
            JarvisRoutingHistoryEntry.model_validate(
                _entry_payload(supervisor_reasoning_summary="z" * 1025)
            )

    # ---- RedirectAttempt ----

    def test_redirect_attempt_agent_id_pattern(self) -> None:
        """RedirectAttempt.agent_id rejects uppercase / leading digit."""
        for bad in ["UPPER", "1leading-digit", "with_underscore"]:
            with pytest.raises(ValidationError):
                RedirectAttempt(
                    agent_id=bad,
                    attempt_index=0,
                    reason_skipped="timeout",
                    duration_ms=10,
                )

    def test_redirect_attempt_attempt_index_ge_zero(self) -> None:
        """RedirectAttempt.attempt_index must be >= 0."""
        with pytest.raises(ValidationError):
            RedirectAttempt(
                agent_id="alpha",
                attempt_index=-1,
                reason_skipped="timeout",
                duration_ms=10,
            )

    def test_redirect_attempt_reason_skipped_closed(self) -> None:
        """RedirectAttempt.reason_skipped is a closed Literal."""
        with pytest.raises(ValidationError):
            RedirectAttempt(
                agent_id="alpha",
                attempt_index=0,
                reason_skipped="something_else",
                duration_ms=10,
            )

    def test_redirect_attempt_detail_max_length_512(self) -> None:
        """RedirectAttempt.detail rejects strings >512 chars."""
        with pytest.raises(ValidationError):
            RedirectAttempt(
                agent_id="alpha",
                attempt_index=0,
                reason_skipped="specialist_error",
                detail="x" * 513,
                duration_ms=10,
            )

    def test_redirect_attempt_duration_ms_ge_zero(self) -> None:
        """RedirectAttempt.duration_ms must be >= 0."""
        with pytest.raises(ValidationError):
            RedirectAttempt(
                agent_id="alpha",
                attempt_index=0,
                reason_skipped="timeout",
                duration_ms=-5,
            )

    # ---- TraceRef ----

    def test_traceref_content_sha256_pattern(self) -> None:
        """TraceRef.content_sha256 must be 64 hex chars."""
        with pytest.raises(ValidationError):
            TraceRef(path="/tmp/x.json", content_sha256="short", size_bytes=1)

    def test_traceref_size_bytes_ge_zero(self) -> None:
        """TraceRef.size_bytes must be >= 0."""
        with pytest.raises(ValidationError):
            TraceRef(path="/tmp/x.json", content_sha256="a" * 64, size_bytes=-1)

    # ---- ToolCallRecord ----

    def test_toolcallrecord_tool_name_min_length_one(self) -> None:
        """ToolCallRecord.tool_name rejects empty strings."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="", args_summary="x", result_summary="y", duration_ms=1
            )

    def test_toolcallrecord_summary_max_length_512(self) -> None:
        """args_summary and result_summary reject strings >512 chars."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="t",
                args_summary="x" * 513,
                result_summary="y",
                duration_ms=1,
            )
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="t",
                args_summary="x",
                result_summary="y" * 513,
                duration_ms=1,
            )

    def test_toolcallrecord_duration_ms_ge_zero(self) -> None:
        """ToolCallRecord.duration_ms must be >= 0."""
        with pytest.raises(ValidationError):
            ToolCallRecord(
                tool_name="t",
                args_summary="x",
                result_summary="y",
                duration_ms=-1,
            )

    # ---- ModelCallRecord ----

    def test_modelcallrecord_model_id_min_length_one(self) -> None:
        """ModelCallRecord.model_id rejects empty strings."""
        with pytest.raises(ValidationError):
            ModelCallRecord(
                model_id="",
                input_tokens=0,
                output_tokens=0,
                latency_ms=0,
                cost_usd=0.0,
            )

    def test_modelcallrecord_numeric_bounds(self) -> None:
        """All numeric fields on ModelCallRecord are >= 0."""
        for kwargs in [
            {"input_tokens": -1},
            {"output_tokens": -1},
            {"latency_ms": -1},
            {"cost_usd": -0.01},
        ]:
            base = {
                "model_id": "gpt",
                "input_tokens": 0,
                "output_tokens": 0,
                "latency_ms": 0,
                "cost_usd": 0.0,
            }
            base.update(kwargs)  # type: ignore[arg-type]
            with pytest.raises(ValidationError):
                ModelCallRecord(**base)  # type: ignore[arg-type]

    # ---- CapabilityDescriptorRef ----

    def test_capability_ref_agent_id_pattern(self) -> None:
        """CapabilityDescriptorRef.agent_id matches the agent_id regex."""
        with pytest.raises(ValidationError):
            CapabilityDescriptorRef(
                agent_id="UPPER",
                role="some-role",
                tool_name_match=True,
                intent_pattern_match=False,
            )

    def test_capability_ref_role_min_length_one(self) -> None:
        """CapabilityDescriptorRef.role rejects empty strings."""
        with pytest.raises(ValidationError):
            CapabilityDescriptorRef(
                agent_id="alpha",
                role="",
                tool_name_match=True,
                intent_pattern_match=False,
            )

    # ---- ConcurrentWorkloadSnapshot ----

    def test_workload_snapshot_ge_zero(self) -> None:
        """All ConcurrentWorkloadSnapshot counters are >= 0."""
        for kwargs in [
            {"in_flight_dispatches": -1},
            {"in_flight_watchers": -1},
            {"in_flight_subagents": -1},
        ]:
            base = {
                "in_flight_dispatches": 0,
                "in_flight_watchers": 0,
                "in_flight_subagents": 0,
            }
            base.update(kwargs)
            with pytest.raises(ValidationError):
                ConcurrentWorkloadSnapshot(**base)  # type: ignore[arg-type]


# ============================================================================
# AC-002 reinforcement: frozen=True semantics
# ============================================================================


class TestFrozenSemantics:
    """JarvisRoutingHistoryEntry instances reject mutation post-construction."""

    def test_assignment_after_construction_raises(self) -> None:
        entry = JarvisRoutingHistoryEntry.model_validate(_entry_payload())
        with pytest.raises(ValidationError):
            entry.session_id = "mutated"  # type: ignore[misc]


# ============================================================================
# AC-002 reinforcement: extra="ignore" forward-compat
# ============================================================================


class TestExtraIgnoreForwardCompat:
    """Unknown fields are silently dropped per ADR-FLEET-00X append-only rule."""

    def test_unknown_field_is_dropped_not_raised(self) -> None:
        payload = _entry_payload()
        payload["future_field_v1_1"] = "value-from-newer-schema"
        entry = JarvisRoutingHistoryEntry.model_validate(payload)
        assert not hasattr(entry, "future_field_v1_1")


# ============================================================================
# AC-006 (TASK-J004-004) was retired by TASK-J004-010, which appended
# ``RoutingHistoryWriter`` to this module per API-internal.md §4. The writer
# legitimately needs ``pathlib``, ``hashlib`` and the Graphiti protocol
# alias — the "declarative-only" invariant only held until the writer
# landed. The writer's own behavioural tests live in
# ``tests/test_routing_history_writer.py``.
# ============================================================================


# ============================================================================
# Helpers
# ============================================================================


def _entry_payload(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid JarvisRoutingHistoryEntry payload.

    Used as a base for negative tests — override one field at a time to
    surface single-field validation failures.
    """
    payload: dict[str, Any] = {
        "decision_id": "7e4f1b2c-1a2b-4c3d-9e8f-abcdef012345",
        "surface": "jarvis",
        "session_id": "sess-001",
        "timestamp": datetime(2026, 4, 28, 10, 0, 0, tzinfo=UTC),
        "supervisor_tool_call_sequence": [],
        "priors_retrieved": [],
        "capability_snapshot_hash": "0" * 64,
        "subagent_type": "specialist",
        "subagent_task_id": "corr-001",
        "subagent_trace_ref": None,
        "subagent_final_state": "success",
        "model_calls": [],
        "wall_clock_ms": 100,
        "total_cost_usd": 0.0,
        "outcome_type": "success",
        "outcome_detail": {},
        "human_response_type": None,
        "human_response_text": None,
        "human_response_latency_ms": None,
        "project_id": None,
        "local_time_of_day": "10:00",
        "recent_session_refs": [],
        "concurrent_workload": {
            "in_flight_dispatches": 0,
            "in_flight_watchers": 0,
            "in_flight_subagents": 0,
        },
        "chosen_specialist_id": None,
        "chosen_subagent_name": None,
        "alternatives_considered": [],
        "attempts": [],
        "supervisor_reasoning_summary": "ok",
    }
    payload.update(overrides)
    return payload
