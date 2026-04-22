---
id: TASK-J001-009
title: tests/test_smoke_end_to_end.py + import-graph regression test
task_type: testing
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 6
implementation_mode: direct
complexity: 4
dependencies: [TASK-J001-008]
status: pending
tags: [testing, smoke, end-to-end, regression, import-graph]
---

# Task: end-to-end smoke test + import-graph invariant test

The smallest possible "Rich-can-have-a-conversation" acceptance test + the regression guard that proves the five-group layout boundaries (ADR-ARCH-006).

## Context

- [phase1-build-plan.md §Change 10](../../../docs/research/ideas/phase1-build-plan.md)
- Feature file @edge-case @smoke "End-to-end smoke test"
- Feature file @edge-case @regression "Domain modules do not import from adapter or tool layers"
- Feature file @edge-case @integration @regression "build_supervisor does not invoke the language model"

## Scope

**Files (NEW):**

- `tests/test_smoke_end_to_end.py`:
  - Uses `CliRunner` to drive `jarvis chat` with a canned `FakeListChatModel` response "Hello, Rich."
  - Submits a single turn then EOF
  - Asserts the canned response appears in stdout
  - Asserts exit code 0 and "session ended." banner present
- `tests/test_import_graph.py` (regression):
  - Inspects `jarvis.sessions` and `jarvis.agents` module imports
  - Asserts no import from `jarvis.adapters` or `jarvis.tools` (Group B domain cannot depend on Group C tools or Group D adapters per ADR-ARCH-006)
- `tests/test_supervisor_no_llm_call.py`:
  - Patches the chat model transport layer with a mock that raises on any `.invoke`/`.ainvoke`
  - Calls `build_supervisor(test_config)`
  - Asserts the mock was NEVER invoked (build_supervisor must be token-free)

## Acceptance Criteria

- `pytest tests/test_smoke_end_to_end.py -v` passes with 1 test covering the full CLI→supervisor→stdout path.
- `pytest tests/test_import_graph.py -v` passes; any accidental `from jarvis.adapters ...` or `from jarvis.tools ...` in domain modules is caught.
- `pytest tests/test_supervisor_no_llm_call.py -v` passes; the mock assertion fires on any regression that would issue a token-consuming request from `build_supervisor`.
- Full test suite (`pytest tests/ -v --tb=short --cov=src/jarvis`) reports 30–40 tests total across all task files, >=80% coverage on scaffolded modules.

## Coach Validation

- Coach verifies the smoke test uses `FakeListChatModel` (not a real model) via the `fake_llm` fixture.
- Coach verifies the import-graph test uses `ast`-level or `importlib`-level inspection (not string greps, which are brittle).
