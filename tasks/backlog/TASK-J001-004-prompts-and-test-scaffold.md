---
id: TASK-J001-004
title: prompts/supervisor_prompt.py + tests/ scaffold (conftest with fake_llm fixture)
task_type: scaffolding
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 2
implementation_mode: direct
complexity: 3
dependencies: [TASK-J001-001, TASK-J001-002]
status: pending
tags: [scaffolding, prompts, testing-infrastructure, fake-llm]
---

# Task: prompts module + tests scaffold

Land the minimal-but-correct supervisor system prompt and the shared test fixtures that every later test will key off.

## Context

- [phase1-build-plan.md §Change 4 and §Change 10](../../../docs/research/ideas/phase1-build-plan.md)
- [ADR-ARCH-011 single Jarvis reasoner subagent](../../../docs/architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md): prompt-surface invariants
- [ADR-ARCH-020 trace-richness by default](../../../docs/architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md): attended-conversation posture

## Scope

**Files (NEW):**

- `src/jarvis/prompts/__init__.py`
- `src/jarvis/prompts/supervisor_prompt.py`:
  - `SUPERVISOR_SYSTEM_PROMPT: str` constant
  - States Jarvis's purpose: general-purpose DeepAgent for Rich, attended conversation surface
  - States "cheapest-that-fits, escalate on need" preference (dormant until FEAT-003)
  - States attended-conversation posture ("you are always in a conversation with a human")
  - Does **NOT** teach dispatch, build queue, or skill invocation (those lands at FEAT-002/004/007)

- `tests/__init__.py`
- `tests/conftest.py` with fixtures:
  - `fake_llm` — `FakeListChatModel` with canned responses (deterministic, no network)
  - `test_config` — `JarvisConfig` with `openai_base_url="http://fake-endpoint/v1"` and sensible defaults
  - `in_memory_store` — fresh `InMemoryStore` per test (yield, then clear)
  - `app_state` — composed AppState (added later; placeholder is fine)

## Acceptance Criteria

- `from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT` works; the constant is non-empty.
- `pytest tests/` collects successfully (no tests defined yet in this task, but collection works).
- `fake_llm` fixture is callable in a test and returns canned responses without hitting a real provider.
- `test_config` fixture validates cleanly (no `ConfigurationError`).
- No mention of `call_specialist`, `queue_build`, `morning-briefing`, `task`, or subagent names in the supervisor prompt (scope invariant).

## Coach Validation

- Coach greps the prompt for any mention of tools that do not exist yet (`call_specialist`, `queue_build`, `morning_briefing`, `talk_prep`) — none must appear.
- Coach verifies the prompt explicitly states the attended-conversation posture.
