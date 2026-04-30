---
complexity: 4
created: 2026-04-29 00:00:00+00:00
dependencies:
- TASK-J005-005
feature_id: FEAT-J005-946D
id: TASK-J005-010
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: design_approved
tags:
- tests
- contract
- nats-core
- cross-repo
- FEAT-JARVIS-005
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: Contract tests vs nats-core — payloads, subjects, envelope round-trip
updated: 2026-04-29 00:00:00+00:00
wave: 4
---

# TASK-J005-010 — Contract tests against nats-core

## Description

Add (or extend) `tests/test_contract_nats_core.py` to verify Jarvis's wire-level
contract with `nats-core` for FEAT-JARVIS-005's two new directions per
[design.md §11 Contradiction detection](../../../docs/design/FEAT-JARVIS-005/design.md)
and the cross-repo invariants in
[summary.md Forge Cross-Repo Contract](../../../features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md):

- **Publish direction** — `BuildQueuedPayload` validation; subject construction
  via `nats_core.Topics.Pipeline.BUILD_QUEUED.format(feature_id=...)`; envelope
  `source_id="jarvis"` round-trip; `_adapter_required_for_jarvis` validator
  fires when adapter is None.
- **Subscribe direction** — `StageCompletePayload` validation; subject pattern
  `pipeline.stage-complete.>` derived from `Topics.Pipeline.STAGE_COMPLETE.format`;
  envelope `source_id="forge"` enforced (drop when not).

This is the **cross-repo contract gate** — these tests run against the actual
`nats-core` package import (no mocks of nats-core types). If `nats-core`
changes its payload shape, this is the first place to fail.

## Acceptance Criteria

- [ ] Test: `BuildQueuedPayload` constructs from a known-good dict; `model_dump()`
      round-trip preserves all fields; `_adapter_required_for_jarvis` validator
      raises when `triggered_by="jarvis"` and `adapter is None`.
- [ ] Test: `StageCompletePayload` constructs from a known-good dict; round-
      trip via `model_dump_json()` and `model_validate_json()` is bit-stable.
- [ ] Test: `nats_core.Topics.Pipeline.BUILD_QUEUED.format(feature_id="X")`
      produces exactly `pipeline.build-queued.X` (singular convention,
      ADR-SP-016).
- [ ] Test: `nats_core.Topics.Pipeline.STAGE_COMPLETE` template, with the
      subscribe `>` wildcard, produces a pattern that matches a known
      stage-complete subject (e.g. `pipeline.stage-complete.X.plan-complete`).
- [ ] Test: `MessageEnvelope(source_id="jarvis", payload=...)` round-trips
      through `model_dump_json()` + `model_validate_json()` with
      `source_id` preserved.
- [ ] Test: Subscriber drops a message with `envelope.source_id="malicious"` —
      no notification enqueued, WARN logged (Group C #1, security
      attestation).
- [ ] Grep test: hard-coded `"pipeline.build-queued."` or `"pipeline.stage-
      complete."` strings absent from `src/jarvis/` (Subjects must come from
      `nats_core.Topics`).
- [ ] `uv run pytest tests/test_contract_nats_core.py -v` passes.

## Test Requirements

- See Acceptance Criteria — this IS the test task.

## Implementation Notes

- These tests exercise `nats-core` types directly (real imports); no mocks of
  `BuildQueuedPayload` / `StageCompletePayload` / `MessageEnvelope` /
  `Topics.Pipeline`.
- The grep test is intentionally surgical — `src/jarvis/` only, not tests/ (test
  fixtures may legitimately string-construct subjects for negative cases).
- If `nats-core` is updated and these tests fail, the failure indicates a
  contract drift that needs cross-repo coordination — do not soften the
  assertion; raise the issue.