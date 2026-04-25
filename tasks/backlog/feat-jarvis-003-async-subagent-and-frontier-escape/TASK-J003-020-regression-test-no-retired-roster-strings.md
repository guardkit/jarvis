---
id: TASK-J003-020
title: Regression test — no retired-roster strings; jarvis-reasoner description invariants
task_type: testing
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 5
implementation_mode: direct
estimated_minutes: 33
dependencies: [TASK-J003-005, TASK-J003-008, TASK-J003-009, TASK-J003-014]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, tests, regression]
---

# Regression test — no retired-roster strings; jarvis-reasoner description invariants

**Feature:** FEAT-JARVIS-003
**Wave:** 5 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Standalone regression test per Context A concern #3 — "Keep quick_local / four-roster strings out of the codebase entirely — no backward-compat shims". Grep-based invariant on `src/` and the generated supervisor prompt + subagent description. Also asserts the jarvis-reasoner description contains all required signal substrings per TASK-J003-009.

## Acceptance Criteria

- [ ] `tests/test_no_retired_roster_strings.py` walks `src/jarvis/` recursively and asserts the following strings DO NOT appear in any `.py`, `.yaml`, or `.txt` file: `deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local` (scenario: *The jarvis-reasoner description does not mention the retired four-subagent roster*).
- [ ] Same test — asserts the rendered `SUPERVISOR_SYSTEM_PROMPT` contains none of the four retired names.
- [ ] Same test — asserts `SUPERVISOR_SYSTEM_PROMPT` contains none of the retired JA6 cloud-fallback phrases (e.g. no mention of "vllm fallback", "gemini-flash-latest", "cloud cheap-tier").
- [ ] `tests/test_jarvis_reasoner_description.py` asserts the `AsyncSubAgent` description from `build_async_subagents(test_config)[0].description` contains ALL required signal substrings: `gpt-oss-120b`, `on the premises`, `sub-second`, `two to four minutes`, `critic`, `researcher`, `planner`.
- [ ] Same file — asserts the description does NOT promise cloud-tier reasoning (no `cloud`, `GPT`, `Claude`, `Gemini`, `OpenAI`, `Anthropic` tokens — the model name `gpt-oss-120b` is local-fleet, not cloud).
- [ ] Note: the `gpt-oss-120b` substring contains `gpt` — the assertion uses word-boundary regex so it does not trigger on this model-name token alone.
- [ ] `uv run pytest tests/test_no_retired_roster_strings.py tests/test_jarvis_reasoner_description.py -v` passes.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
