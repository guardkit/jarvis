---
id: TASK-J003-002
title: Define RoleName + FrontierTarget closed enums
task_type: declarative
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, enums, ddr-011]
---

# Define RoleName + FrontierTarget closed enums

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two closed str-Enums per DDR-011 and design.md §4 / models DM-subagent-types §5. Adding a member is a conscious schema change that requires a DDR; these enums are the routing contract.

## Acceptance Criteria

- [ ] `src/jarvis/agents/subagents/types.py` exposes `class RoleName(str, Enum)` with exactly three members: `CRITIC = "critic"`, `RESEARCHER = "researcher"`, `PLANNER = "planner"`.
- [ ] `src/jarvis/tools/dispatch_types.py` (or an existing dispatch types module) exposes `class FrontierTarget(str, Enum)` with exactly two members: `GEMINI_3_1_PRO = "GEMINI_3_1_PRO"`, `OPUS_4_7 = "OPUS_4_7"`.
- [ ] Both enums are `str`-valued so `@tool(parse_docstring=True)` argument coercion works with literal strings.
- [ ] `RoleName("")` raises `ValueError` (default Python enum behaviour) — no custom `__missing__`; the subagent graph maps this to `unknown_role` per ASSUM-004.
- [ ] Module has no side-effects at import; no I/O; no LLM calls.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
