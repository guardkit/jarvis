---
id: TASK-J001-FIX-005
title: Wire InMemorySaver into build_supervisor (within-session recall)
task_type: bug-fix
parent_review: TASK-REV-J001
review_report: .claude/reviews/FEAT-JARVIS-001-review-report.md
feature_id: FEAT-JARVIS-001
wave: 3
implementation_mode: direct
complexity: 2
estimated_minutes: 20
dependencies: []
status: completed
completed: 2026-04-22T00:00:00Z
completed_location: tasks/completed/TASK-J001-FIX-005/
organized_files:
- TASK-J001-FIX-005.md
quality_gates:
  mypy: pass (0 errors on src/jarvis/)
  ruff: pass (src/jarvis/ and tests/ clean)
  pytest: pass (348/348; +4 tests in TestWithinSessionRecall)
files_changed:
- src/jarvis/agents/supervisor.py
- tests/test_supervisor.py
tags:
- review-fix
- post-phase1
- checkpointer
- memory
- day-1-validation
---

# Task: Wire `InMemorySaver` into `build_supervisor`

Close the day-1 multi-turn conversation gap surfaced during Step 8 (Day-1 conversation validation) of `phase1-build-plan.md`. Within a single `jarvis chat` session, the supervisor was treating each turn as a fresh conversation — ignoring prior context — which broke both the @smoke multi-turn scenarios in the feature spec and the "useful conversation on day 1" success criterion.

## Context

Step 8 live validation revealed that a two-turn conversation in the *same* `uv run jarvis chat` process failed to recall:

```
> Remember that my DDD Southwest talk is on 16 May.
[ack]
> When is my DDD Southwest talk?
I couldn't find any information about your DDD Southwest talk.
```

Root cause: [src/jarvis/agents/supervisor.py](../../../src/jarvis/agents/supervisor.py) called `create_deep_agent(...)` without a `checkpointer=` kwarg. `create_deep_agent`'s signature defaults `checkpointer: None | bool | BaseCheckpointSaver = None`, so the compiled graph had no saver to hook into. `SessionManager.invoke()` correctly passes `config={"configurable": {"thread_id": session.thread_id}}` on every turn — but with no saver, `thread_id` has nothing to key state against. Every turn is stateless.

All pre-existing tests passed because they mock `create_deep_agent` and `ainvoke`; they never exercise the real DeepAgents middleware with a real LangGraph saver. The gap only appears when live OpenAI traffic flows through the unmocked graph.

Note: cross-session / cross-process recall (Phase 1 Success Criterion #4 as written) still requires a persistent checkpointer + persistent store — both land in FEAT-JARVIS-007. This fix closes only the within-session (same-process) path, which is what the day-1 criterion actually exercises.

## Scope

1. [src/jarvis/agents/supervisor.py](../../../src/jarvis/agents/supervisor.py):
   - Import `InMemorySaver` from `langgraph.checkpoint.memory`.
   - Pass `checkpointer=InMemorySaver()` to `create_deep_agent(...)`.
   - Update the surrounding comment to document why: `thread_id` plumbing is a no-op without a saver; persistent savers are deferred to FEAT-JARVIS-007.

2. [tests/test_supervisor.py](../../../tests/test_supervisor.py) — new `TestWithinSessionRecall` class with three regression-guards:
   - `test_compiled_graph_has_checkpointer` — asserts `graph.checkpointer is not None`.
   - `test_checkpointer_is_in_memory_saver` — pins the Phase 1 choice (catches silent swaps to persistent savers).
   - `test_create_deep_agent_receives_checkpointer_kwarg` — argument-level assertion (catches DeepAgents parameter renames).
   - `test_distinct_graphs_get_distinct_checkpointers` — guards the idempotency contract against shared-saver state leaks.

## Out of Scope

- Persistent savers (`FileSaver`, `SqliteSaver`, `PostgresSaver`) — deferred to FEAT-JARVIS-007.
- Cross-session / cross-process recall (Success Criterion #4) — deferred to FEAT-JARVIS-007.
- End-to-end recall test driving the full DeepAgents graph — blocked because every stock `FakeListChatModel` / `GenericFakeChatModel` variant raises `NotImplementedError` for `bind_tools`, which the DeepAgents tool-calling middleware requires. The four argument-level / wiring-level tests together cover the regression surface we care about; live `jarvis chat` remains the end-to-end check.

## Acceptance Criteria

- `uv run pytest tests/test_supervisor.py::TestWithinSessionRecall -v` — 4 tests pass.
- `uv run pytest tests/` — 348/348 passing (no regressions; +4 over the FIX-004 baseline of 344).
- `uv run ruff check src/jarvis/ tests/` — clean.
- `uv run mypy src/jarvis/` — clean (0 errors in 26 files).
- Live: `uv run jarvis chat` retains facts stated in an earlier turn when queried later in the same session.

## Coach Validation

- `grep -n "InMemorySaver\|checkpointer" src/jarvis/agents/supervisor.py` — both the import and the kwarg must be present.
- `grep -n "checkpointer" tests/test_supervisor.py` — the regression-guard class must be wired.
- Within-session recall must be demonstrable in a live `jarvis chat` transcript (day-1 evidence).

## Files Changed

| File | Change |
|---|---|
| `src/jarvis/agents/supervisor.py` | +2 lines: `InMemorySaver` import + `checkpointer=InMemorySaver()` kwarg; +7 lines of explanatory comment |
| `tests/test_supervisor.py` | +1 class `TestWithinSessionRecall` with 4 regression-guard tests |
