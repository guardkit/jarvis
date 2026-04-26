---
id: TASK-J003-002
title: Define RoleName + FrontierTarget closed enums
task_type: declarative
status: in_review
created: 2026-04-24 00:00:00+00:00
updated: 2026-04-24 00:00:00+00:00
priority: high
complexity: 2
wave: 1
implementation_mode: direct
estimated_minutes: 22
dependencies: []
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags:
- phase-2
- jarvis
- feat-jarvis-003
- enums
- ddr-011
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-25T17:58:06.475098'
  last_updated: '2026-04-25T18:02:55.845908'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:58:06.475098'
    player_summary: "Created two closed-enum modules per AC-001/002. Both enums inherit\
      \ from (str, Enum) so @tool(parse_docstring=True) literal-string coercion works\
      \ (AC-003) and instances compare equal to their wire string. RoleName has exactly\
      \ three lower-case members (critic, researcher, planner) used in NATS subjects/log\
      \ fields/prompt templates. FrontierTarget has exactly two upper-case members\
      \ (GEMINI_3_1_PRO, OPUS_4_7) used on the dispatch subject. No custom __missing__\
      \ on either class \u2014 RoleName('') and Front"
    player_success: true
    coach_success: true
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
