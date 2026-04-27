---
id: TASK-J004-015
title: "Integration: dispatch_by_capability round-trip + redirect matrix"
task_type: testing
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 4
implementation_mode: task-work
complexity: 6
dependencies: [TASK-J004-013]
priority: high
tags: [tests, integration, dispatch, retry, redirect, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-015 — Integration: dispatch_by_capability round-trip + redirect matrix

## Description

Land `tests/test_dispatch_by_capability_integration.py` with the six
matrix scenarios from [design §9](../../../docs/design/FEAT-JARVIS-004/design.md):

1. **Round-trip happy path**: mock specialist consumer subscribes to
   `agents.command.test-architect`, replies with canned `ResultPayload(success=True)`;
   tool returns the result; trace `outcome="success"`, `attempts=[]`.
2. **Timeout → exhausted**: no consumer subscribed; `timeout_seconds=1`
   reduced for test; tool returns `TIMEOUT: agent_id=… exhausted attempts=1`;
   trace `outcome="exhausted"`, `attempts` length 1.
3. **Timeout → redirect → success**: first specialist times out;
   second specialist (matching capability) replies; tool returns the
   second result; trace `outcome="redirected"`, `attempts` length 1,
   `chosen_specialist_id` matches second.
4. **Timeout → redirect → timeout**: both specialists time out; tool
   returns `TIMEOUT: ... exhausted attempts=2`; trace `outcome="exhausted"`,
   `attempts` length 2; visited-set prevented loops.
5. **Specialist error → redirect → success**: first specialist replies
   `success=False, error="capacity_exceeded"`; second replies success;
   trace `outcome="redirected"`, `attempts[0].reason_skipped="specialist_error"`.
6. **Concurrent dispatch overflow**: launch 9 concurrent dispatches
   against a slow (delayed-reply) consumer; 9th returns `DEGRADED:
   dispatch_overloaded` synchronously; first 8 return success when
   the consumer fires.

## Acceptance Criteria

- [ ] All 6 matrix scenarios covered with parametrised tests where natural.
- [ ] Mocked specialist consumers built via the in-process NATS server fixture from TASK-J004-014.
- [ ] **Lexicographic resolution** (DDR-017 determinism) asserted: when two specialists match the same capability, the tool always picks the one with the lexicographically-first `agent_id` first.
- [ ] **Visited-set guard**: in scenario 4, assert that the second attempt does NOT target the first specialist.
- [ ] **Trace shape** validated for each scenario via `JarvisRoutingHistoryEntry.model_validate(...)` against the captured Graphiti-write payload (mock the Graphiti client to capture).
- [ ] **DEGRADED string format** matches design §10 exactly — no typos in the structured-error contract.
- [ ] Integration tests survive `--randomly-seed=0`.
- [ ] `uv run pytest tests/test_dispatch_by_capability_integration.py -v` green.

## Test Requirements

- [ ] Each test uses an isolated in-process NATS server (per-test fixture or scoped session fixture with cleanup).
- [ ] Mocked specialists implement the **NATS req/reply** pattern — subscribe with `cb=` and reply via `msg.respond(...)`.
- [ ] Capture the Graphiti-write episode payloads via a `MagicMock` on `GraphitiClient.add_episode`; assert the entries match the expected outcomes.

## Implementation Notes

The `_resolve_agent_id` lexicographic ordering is the easiest
deterministic-resolution test: seed the registry with `agent_ids
["test-zarchitect", "test-architect"]` (lexicographically earliest is
`test-architect`), assert `chosen_specialist_id == "test-architect"`
on first attempt.

DDR-020 semaphore-overflow scenario (#6) is also covered by the
five-row Scenario Outline regression in TASK-J004-017; both tests
should pass independently — keep them as separate tests rather than
deduplicating.

## Test Execution Log

(Populated by /task-work.)
