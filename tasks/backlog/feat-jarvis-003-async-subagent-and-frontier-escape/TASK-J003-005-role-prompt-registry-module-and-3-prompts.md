---
id: TASK-J003-005
title: Role prompt registry module + 3 role prompts
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 3
wave: 1
implementation_mode: direct
estimated_minutes: 33
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, prompts, ddr-011]
---

# Role prompt registry module + 3 role prompts

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 3/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

The `ROLE_PROMPTS` registry is consumed by the `jarvis_reasoner` graph at its first node (design.md §8 "Role-dispatch contract"). Exhaustiveness over `RoleName` is a test-asserted invariant (scenario: *The role prompt registry covers every member of the role enum*). DDR-011 pins the closed-enum shape.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/prompts.py` defines three module-level string constants:
  - `CRITIC_PROMPT: str` — adversarial-evaluation posture; the word "adversarial" appears verbatim.
  - `RESEARCHER_PROMPT: str` — open-ended research posture; the phrase "open-ended research" appears verbatim.
  - `PLANNER_PROMPT: str` — multi-step planning posture; the phrase "multi-step planning" appears verbatim.
- [ ] The same module exposes `ROLE_PROMPTS: Mapping[RoleName, str]` with exactly three entries, one per `RoleName` member. No extra keys.
- [ ] Each prompt is non-empty and ≥ 40 characters (enough to carry the role posture) but avoids prescribing specific tools (the subagent is leaf per design §8).
- [ ] Prompts are plain strings, no `{placeholders}` — they are final system prompts, not templates.
- [ ] `from jarvis.agents.subagents.prompts import ROLE_PROMPTS` is side-effect free; no I/O; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
