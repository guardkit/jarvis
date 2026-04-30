---
complexity: 8
created: 2026-04-29 00:00:00+00:00
dependencies:
- TASK-J005-008
- TASK-J005-010
feature_id: FEAT-J005-946D
id: TASK-J005-012
implementation_mode: task-work
parent_review: TASK-REV-3B8B
priority: high
status: completed
tags:
- tests
- end-to-end
- phase3-close
- soft-prereq
- gb10
- FEAT-JARVIS-005
task_type: testing
test_results:
  coverage: null
  last_run: null
  status: pending
title: End-to-end Forge round-trip (soft-prereq, GB10 gated)
updated: 2026-04-30T11:10:33Z
wave: 5
---

# TASK-J005-012 — End-to-end Forge round-trip

## Description

Implement `tests/test_end_to_end_forge_roundtrip.py` — the **Phase 3 close
criterion** evidence test, per
[phase3-build-plan.md Step 14](../../../docs/research/ideas/phase3-build-plan.md).

This is a **soft-prereq** test — it requires real Forge + real NATS + real
Graphiti running on GB10, plus all subagent provider keys for any subagent
dispatch the chosen FEAT-JARVIS-INTERNAL-001 build entails. When the prereqs
are not present (CI default, MacBook-only), the test should **skip with a clear
reason**, not fail.

Test shape:

1. Pre-flight: assert `JARVIS_NATS_URL`, `JARVIS_GRAPHITI_ENDPOINT` set;
   `pytest.skip` otherwise.
2. Build `JarvisConfig` from env; run `lifecycle.build_app_state(config)`;
   assert subscriber started + bound.
3. Resolve a chosen FEAT-JARVIS-INTERNAL-001 candidate (Phase 3 plan §13;
   docstring polish / trace-schema refinement / skill scaffolding — operator
   selects via env var or fixture).
4. Invoke `queue_build(feature_id="FEAT-JARVIS-INTERNAL-001", ...)` via the
   supervisor flow (or via `tool_list_attended`).
5. Assert `correlation_id` in the returned ack; subscriber's correlation_map
   has the entry.
6. Wait (bounded ≤ 5 minutes) for stage-complete events to flow back from
   Forge.
7. Assert the per-session pending-notifications queue receives the expected
   stage-complete events (`plan-complete`, `autobuild-complete`,
   `task-review-complete`).
8. Assert Graphiti dump contains:
   - One `JarvisRoutingHistoryEntry` with `subagent_type="forge_build_queue"`,
     `subagent_task_id=correlation_id`.
   - One stage-complete edge per Forge stage event observed.
   - Schema matches ADR-FLEET-001 + Jarvis extensions.
9. Run `shutdown(state)`; assert clean drain.

## Acceptance Criteria

- [ ] Test skips cleanly when GB10 env-vars absent (no spurious failures in
      laptop / CI runs).
- [ ] When prereqs present, test runs to completion within 10 minutes.
- [ ] Asserts the full round-trip:
      `queue_build → BuildQueuedPayload published → Forge consumes → Forge
      stage-complete events → subscriber routes → CLI queue → Graphiti edges`.
- [ ] Asserts at least 3 distinct stage-complete edges land in Graphiti.
- [ ] Failure modes produce structured pytest output naming the failing
      assertion (correlation lookup miss, edge missing, etc.).
- [ ] Records the session transcript and Graphiti trace dump as test
      attachments — this is the Phase 3 evidence artefact.

## Test Requirements

- See Acceptance Criteria — this IS the test task.

## Implementation Notes

- The Phase 3 plan calls for Rich to select the FEAT-JARVIS-INTERNAL-001
  candidate before this test runs (`/feature-spec` against the Jarvis repo
  itself); the candidate's `feature_id` is passed in via env var
  `JARVIS_E2E_FEATURE_ID` for reproducibility.
- Prereqs (per phase3-build-plan §14):
  - NATS on GB10 reachable via `JARVIS_NATS_URL`
  - Forge running and subscribed to `pipeline.build-queued.>`
  - Graphiti / FalkorDB running on GB10 via `JARVIS_GRAPHITI_ENDPOINT`
  - Subagent provider keys for Forge's pipeline stages
- Mark the test `@pytest.mark.e2e` so it can be opted-out via `pytest -m "not e2e"`.
- This test does NOT block the merge of FEAT-J005 — it is the *evidence* test
  for Phase 3 close, run after the rest of the wave lands.