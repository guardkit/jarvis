---
id: TASK-J003-021
title: Integration test — supervisor_with_subagents (attended/ambient tool lists + 5 middleware tools)
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 5
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-013, TASK-J003-015]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, integration]
---

# Integration test — supervisor_with_subagents

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Extends FEAT-JARVIS-002's `test_supervisor_with_tools.py`: builds the supervisor with all FEAT-J002 tools, the jarvis-reasoner subagent, and attended tool list (including `escalate_to_frontier`). Asserts the five middleware operational tools are present AND asserts that `escalate_to_frontier` is present on attended / absent on ambient tool lists. No LLM call.

## Acceptance Criteria

- [ ] `tests/test_supervisor_with_subagents.py` — builds the supervisor via `build_supervisor(test_config, tools=<FEAT-J002 set>, async_subagents=build_async_subagents(test_config), ambient_tool_factory=lambda: assemble_tool_list(test_config, include_frontier=False))` and asserts the return is a `CompiledStateGraph`.
- [ ] The supervisor's tool catalogue includes all FEAT-J002 tools (no regression).
- [ ] The supervisor's tool catalogue includes the five `AsyncSubAgentMiddleware` operational tools: `start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` (scenario: *Wiring the async subagent injects the five middleware operational tools*).
- [ ] Attended tool list (`include_frontier=True`) contains `escalate_to_frontier`.
- [ ] Ambient tool list (`include_frontier=False`) excludes `escalate_to_frontier` AND contains all FEAT-J002 tools (scenario: *escalate_to_frontier is not present in the ambient tool list at all* + *the assembled list still contains all FEAT-JARVIS-002 tools*).
- [ ] Backward-compat: `build_supervisor(test_config, tools=<FEAT-J002 set>)` (no async_subagents) returns a valid `CompiledStateGraph` WITHOUT the five middleware tools (scenario: *Building the supervisor without async subagents preserves existing behaviour*).
- [ ] FakeListChatModel; zero LLM network calls.
- [ ] `uv run pytest tests/test_supervisor_with_subagents.py -v` passes with ≥ 80% coverage on the new test module.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
