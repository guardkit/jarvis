---
id: TASK-J003-017
title: Unit tests — subagent layer (registry + graph + prompts)
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 4
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-005, TASK-J003-008, TASK-J003-009]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests]
---

# Unit tests — subagent layer (registry + graph + prompts)

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Three unit-test files covering design.md §9 subagent-layer tests. FakeListChatModel everywhere; no LLM network call.

## Acceptance Criteria

- [ ] `tests/test_subagent_registry.py` — `build_async_subagents(test_config)` returns a list of length 1; the element has `name="jarvis-reasoner"`, `graph_id="jarvis_reasoner"`, non-empty description; description contains all required signal substrings (`gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`).
- [ ] `tests/test_subagents_jarvis_reasoner.py` — `from jarvis.agents.subagents.jarvis_reasoner import graph` returns a compiled graph at import time (DDR-012); no LLM network call on import.
- [ ] Same test file — unknown-role inputs (`"bard"`, `"CRITIC"`, `"adversarial"`, `""`) all return structured error through the `async_tasks` channel containing "unknown_role".
- [ ] Same test file — missing-role and missing-prompt inputs both return structured errors mentioning "missing_field".
- [ ] Same test file — a role of `"critic"` resolves to the critic prompt; `"researcher"` → researcher prompt; `"planner"` → planner prompt (structural assertion via state-inspection, not LLM output).
- [ ] Same test file — cancellation path: starting an async task then calling `cancel_async_task` surfaces `status="cancelled"` via `check_async_task` (ASSUM-002 verification per review Finding F3).
- [ ] Same test file — unknown `task_id` passed to `check_async_task` returns structured `"ERROR: unknown_task_id"` without raising (ASSUM-003).
- [ ] Same test file — jarvis_reasoner graph has no application tools wired (`tools=[]`) and no further subagents (scenario: *The jarvis-reasoner subagent graph carries no tools of its own*).
- [ ] `tests/test_subagent_prompts.py` — `ROLE_PROMPTS` is a complete mapping over `RoleName` (len == 3, keys == set(RoleName)); each prompt non-empty ≥ 40 chars; each prompt contains the expected posture keyword (CRITIC → "adversarial"; RESEARCHER → "open-ended research"; PLANNER → "multi-step planning").
- [ ] All tests use `FakeListChatModel` from langchain_core.language_models.fake (or DeepAgents equivalent); zero real LLM calls.
- [ ] `uv run pytest tests/test_subagent_*.py -v` passes with ≥ 80% coverage on the three subagent-layer modules.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
