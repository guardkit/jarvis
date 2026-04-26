---
complexity: 6
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-021
- TASK-J003-022
estimated_minutes: 113
feature_id: FEAT-J003
id: TASK-J003-023
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- tests
- acceptance
- e2e
task_type: testing
title: Acceptance test — test_routing_e2e (7 canned prompts)
updated: 2026-04-24 00:00:00+00:00
wave: 5
---

# Acceptance test — test_routing_e2e (7 canned prompts)

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

**The acceptance test for FEAT-JARVIS-003**, per design.md §9 and the .feature file Group D canonical outline. Seven canned prompts with a mocked LLM returning deterministic tool-call sequences — structural assertions on tool-call identity, not final natural-language output. Same pattern as specialist-agent's Player-Coach test structure.

## Acceptance Criteria

- [ ] `tests/test_routing_e2e.py` builds the full supervisor via `build_supervisor(test_config, tools=<FEAT-J002 set>, async_subagents=build_async_subagents(test_config), ambient_tool_factory=...)`.
- [ ] Attended adapter (`adapter_id="cli"`) is set in the session context.
- [ ] Seven parametrised prompts and their expected tool-call first step (per scenario *The supervisor routes the seven canned acceptance prompts to the expected tools*):
  1. `"What's 15% of 847?"` → `calculate` (FEAT-J002 regression)
  2. `"Summarise /tmp/test.md"` → `read_file` (FEAT-J002 regression)
  3. `"Critique this architecture doc for subtle flaws."` → `start_async_task(name="jarvis-reasoner", input={"role": "critic", ...})`
  4. `"Research Meta-Harness deeply."` → `start_async_task(name="jarvis-reasoner", input={"role": "researcher", ...})`
  5. `"Plan the migration to Python 3.13."` → `start_async_task(name="jarvis-reasoner", input={"role": "planner", ...})`
  6. `"Ask Gemini 3.1 Pro for a frontier opinion on this ADR."` → `escalate_to_frontier(target=GEMINI_3_1_PRO)` (attended CLI path)
  7. `"Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo."` → `queue_build` (FEAT-J002 regression — confirms no routing regression from subagent wiring)
- [ ] Assertions are structural (tool name + first-call arguments), not behavioural (final NL output).
- [ ] LLM is mocked with `FakeListChatModel` or equivalent returning deterministic tool-call sequences; zero real LLM calls.
- [ ] Provider SDKs (google-genai, anthropic) are mocked for prompt 6.
- [ ] `uv run pytest tests/test_routing_e2e.py -v` passes.
- [ ] Test runtime < 5 seconds on M2 Max (no network I/O; all mocks).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the 7-prompt parametrised skeleton with failing assertions FIRST — this is the Phase 2 close criterion for FEAT-J003.