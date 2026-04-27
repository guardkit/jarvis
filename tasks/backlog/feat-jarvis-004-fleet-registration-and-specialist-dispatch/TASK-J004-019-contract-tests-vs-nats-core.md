---
id: TASK-J004-019
title: "tests/test_contract_nats_core.py — contract tests + Topics-formatter grep invariant"
task_type: testing
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 5
implementation_mode: task-work
complexity: 4
dependencies: [TASK-J004-015]
priority: high
tags: [tests, contract, nats-core, regression-gate, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
consumer_context:
  - task: TASK-J004-011
    consumes: SOURCE_ID_JARVIS_AUDIT
    framework: "nats_core.MessageEnvelope"
    driver: "pydantic"
    format_note: "Every emitted MessageEnvelope must carry source_id='jarvis' (audit invariant per API-events §5)"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-019 — Contract tests vs nats-core + Topics-formatter grep invariant

## Description

Land `tests/test_contract_nats_core.py` per [API-events §5](../../../docs/design/FEAT-JARVIS-004/contracts/API-events.md):

1. **`test_jarvis_manifest_round_trips`** — `build_jarvis_manifest(config)`
   → JSON → `nats_core.AgentManifest.model_validate_json` produces an
   equal manifest.
2. **`test_command_payload_emitted_matches_nats_core`** — Jarvis's
   emitted `CommandPayload` deserialises cleanly via
   `nats_core.events.CommandPayload`. All required fields populated.
3. **`test_result_payload_consumed_matches_nats_core`** — Synthetic
   specialist reply (built from `nats_core.events.ResultPayload(...)`)
   round-trips through `dispatch_by_capability` without ValidationError.
4. **`test_envelope_source_id_is_jarvis`** — parametrised across every
   `MessageEnvelope` emitted from `tools/dispatch.py` (and any other
   emit site found via grep); asserts `envelope.source_id == "jarvis"`.
5. **`test_topic_subjects_match_topics_class`** — every
   `agents.command.*` / `agents.result.*` / `fleet.register` subject
   string Jarvis emits is produced by a `nats_core.Topics.*` formatter.
6. **`test_no_hardcoded_subject_literals_in_src`** — **grep invariant**
   over `src/jarvis/`: no string matches `"agents.command."` /
   `"agents.result."` / `"fleet.register"` outside the allow-list (the
   `nats_core.Topics` import + comments in module docstrings).
7. **(Carry-forward stub for FEAT-J005)**
   `test_build_queued_payload_emitted_matches_nats_core` — module
   exists but only exercises the Phase 2 stub builder; FEAT-J005 will
   light it up with the real publish.

## Seam Tests

```python
"""Seam test: verify SOURCE_ID_JARVIS_AUDIT contract from TASK-J004-011."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("SOURCE_ID_JARVIS_AUDIT")
def test_envelope_source_id_jarvis_audit_invariant():
    """Verify every emitted MessageEnvelope carries source_id='jarvis'.

    Contract: API-events §5 audit invariant — every MessageEnvelope
    constructed inside src/jarvis/tools/dispatch.py (and any other emit
    site) sets source_id='jarvis'. This is the audit trail invariant
    that survives schema drift.
    Producer: TASK-J004-011
    """
    from jarvis.tools.dispatch import _build_message_envelope  # or wherever construction lives

    envelope = _build_message_envelope(
        tool_name="x", parsed_args={}, correlation_id="00000000-0000-4000-8000-000000000000"
    )
    assert envelope.source_id == "jarvis", (
        "API-events §5 invariant: every emitted MessageEnvelope must set source_id='jarvis'"
    )
```

## Acceptance Criteria

- [ ] All 6 contract tests + the FEAT-J005 carry-forward stub exist.
- [ ] **Grep invariant test (#6)** uses `pathlib.Path.rglob` + `str.contains` to scan `src/jarvis/` for hard-coded subject literals; allow-list documented in the test docstring.
- [ ] Tests fail loudly if any subject string is hard-coded (failure message names the offending file + line).
- [ ] **Source_id audit (#4)** parametrises across every `MessageEnvelope(source_id=...)` construction site found via grep.
- [ ] No real NATS / Graphiti — these are pure schema + grep contract tests.
- [ ] `uv run pytest tests/test_contract_nats_core.py -v` green.

## Test Requirements

- [ ] Use synthetic `CommandPayload` / `ResultPayload` / `AgentManifest` instances (constructed in-test) — no live NATS round-trips needed.
- [ ] Grep invariant runs against `src/jarvis/` only (not `tests/`, not `features/`, not `docs/`).

## Implementation Notes

The grep invariant pattern is the FEAT-J002 TASK-J002-021 template
(retired in TASK-J004-020 — this is its replacement). The test is the
cross-repo handshake protector; it'll catch the kind of drift that
breaks Forge↔Jarvis interop without a clear blast radius.

## Test Execution Log

(Populated by /task-work.)
