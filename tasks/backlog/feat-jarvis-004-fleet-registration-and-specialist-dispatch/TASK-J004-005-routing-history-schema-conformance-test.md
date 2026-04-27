---
id: TASK-J004-005
title: "tests/test_routing_history_schema.py — schema-conformance gate"
task_type: testing
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 1
implementation_mode: direct
complexity: 3
dependencies: [TASK-J004-004]
priority: high
tags: [tests, routing-history, schema, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-004
    consumes: JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA
    framework: "Pydantic v2 BaseModel with frozen=True, extra=ignore"
    driver: "pydantic"
    format_note: "Schema is authoritative per DDR-018; tests must validate exact field set including all ADR-FLEET-001 §1–§7 base fields + Jarvis extensions"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-005 — Routing-history schema-conformance gate

## Description

Land `tests/test_routing_history_schema.py` — the DDR-018 schema
authority gate. This test fails loudly if any later task accidentally
renames a field, drops a section, or weakens a validator on
`JarvisRoutingHistoryEntry`.

Coverage (matching DM-routing-history.md §7 "Validation tests anchor"):

1. Happy-path full-shape validation — every §1–§7 base field + every
   Jarvis extension populated; `model_validate(...)` round-trips.
2. `DispatchOutcome` — every member of the Literal accepted; an unknown
   member raises ValidationError.
3. `attempts` — monotonic `attempt_index` (0, 1, 2…); `reason_skipped`
   limited to the closed Literal.
4. `frozen=True` — direct field assignment after construction raises
   ValidationError.
5. `extra="ignore"` — unknown field in input dict is silently dropped
   (forward-compat for ADR-FLEET-00X additions).
6. `decision_id` regex — non-UUID-v4 string raises.
7. `timestamp` — non-timezone-aware datetime raises.
8. Helper types (`ToolCallRecord`, `ModelCallRecord`,
   `CapabilityDescriptorRef`, `ConcurrentWorkloadSnapshot`,
   `TraceRef`) — boundary validators.

This task does **not** test the redaction processor or the 16KB
filesystem offload — those depend on the writer (TASK-J004-010) and
land in TASK-J004-018's writer test file.

## Acceptance Criteria

- [ ] `tests/test_routing_history_schema.py` exists with ≥ 12 test functions covering points 1–8 above.
- [ ] Tests pass against TASK-J004-004's schema with no `pytest.xfail` or `pytest.skip`.
- [ ] `uv run pytest tests/test_routing_history_schema.py -v` green.
- [ ] No mocks — Pydantic models are pure-data; tests construct real instances.

## Seam Tests

The following seam test validates the integration contract with the producer task. Implement this test to verify the boundary before integration.

```python
"""Seam test: verify JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA contract from TASK-J004-004."""
import pytest
from datetime import datetime, timezone


@pytest.mark.seam
@pytest.mark.integration_contract("JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA")
def test_jarvis_routing_history_entry_schema_format():
    """Verify JarvisRoutingHistoryEntry matches DDR-018 authoritative shape.

    Contract: Pydantic v2 BaseModel with frozen=True, extra=ignore.
    Schema is authoritative per DDR-018; all ADR-FLEET-001 §1–§7 base
    fields + Jarvis extensions must be present; field types and validators
    must match DM-routing-history.md verbatim.
    Producer: TASK-J004-004
    """
    from jarvis.infrastructure.routing_history import JarvisRoutingHistoryEntry

    # Producer side: model_config asserts the structural invariants.
    config = JarvisRoutingHistoryEntry.model_config

    # Consumer side: verify format matches contract.
    assert config.get("frozen") is True, "Schema must be frozen=True per DDR-018"
    assert config.get("extra") == "ignore", "Schema must accept extra='ignore' for forward-compat"

    # Field set assertion — every required ADR-FLEET-001 + Jarvis extension field.
    fields = JarvisRoutingHistoryEntry.model_fields
    required_base = {
        "decision_id", "surface", "session_id", "timestamp",
        "supervisor_tool_call_sequence", "priors_retrieved", "capability_snapshot_hash",
        "subagent_type", "subagent_task_id", "subagent_trace_ref", "subagent_final_state",
        "model_calls", "wall_clock_ms", "total_cost_usd",
        "outcome_type", "outcome_detail",
        "human_response_type", "human_response_text", "human_response_latency_ms",
        "project_id", "local_time_of_day", "recent_session_refs", "concurrent_workload",
    }
    jarvis_extensions = {
        "chosen_specialist_id", "chosen_subagent_name", "alternatives_considered",
        "attempts", "supervisor_reasoning_summary",
    }
    expected = required_base | jarvis_extensions
    missing = expected - set(fields.keys())
    assert not missing, f"Schema missing required fields per DDR-018: {missing}"
```

## Test Requirements

- [ ] Tests fail if `JarvisRoutingHistoryEntry` ever loses `frozen=True` or `extra="ignore"`.
- [ ] Tests fail if any field in DM-routing-history.md is dropped.
- [ ] Tests do not reach into Graphiti or filesystem — schema-only.

## Implementation Notes

Use `pytest.raises(ValidationError)` for negative cases. Construct happy-path
instances via dict-literal in fixture so failed validations point to the
exact field that broke.

## Test Execution Log

(Populated by /task-work.)
