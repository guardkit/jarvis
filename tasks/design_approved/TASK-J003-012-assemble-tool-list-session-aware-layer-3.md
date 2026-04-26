---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T18:54:32.635360'
  max_turns: 30
  started_at: '2026-04-25T18:37:54.252642'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T18:37:54.252642'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 4
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-011
estimated_minutes: 50
feature_id: FEAT-J003
id: TASK-J003-012
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- wiring
- ddr-014
- layer-3
- security
task_type: feature
title: assemble_tool_list session-aware gating (Layer 3 standalone)
updated: 2026-04-24 00:00:00+00:00
wave: 3
---

# assemble_tool_list session-aware gating (Layer 3 standalone)

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

**Layer 3 of the belt+braces gate — standalone per Context A concern #1.** The reasoning model cannot invoke a tool it cannot see. This task extends the FEAT-J002 `assemble_tool_list` with an `include_frontier: bool` kwarg so attended vs ambient tool lists diverge by tool-registry membership, not by runtime check. Constitutionally, not reasoning-adjustable (ADR-ARCH-023).

## Acceptance Criteria

- [ ] `src/jarvis/tools/__init__.py` (or wherever `assemble_tool_list` lives from FEAT-J002) gains an `include_frontier: bool = True` keyword-only parameter.
- [ ] When `include_frontier=True`: the returned list includes `escalate_to_frontier` alongside all FEAT-J002 tools.
- [ ] When `include_frontier=False`: the returned list **omits** `escalate_to_frontier` entirely and includes ALL other FEAT-J002 tools unchanged (scenario: *escalate_to_frontier is not present in the ambient tool list at all*; *the assembled list still contains all FEAT-JARVIS-002 tools*).
- [ ] The returned list is a new list object each call (no mutable aliasing); the reasoning model cannot mutate a shared list to add `escalate_to_frontier` at runtime (scenario: *The reasoning model cannot add escalate_to_frontier to the ambient tool list at runtime* — ADR-ARCH-023).
- [ ] No default coupling: `include_frontier` has no relationship to session state; it is a pure lifecycle-time flag set by the caller (`lifecycle.startup` in TASK-J003-015).
- [ ] Identity check: `escalate_to_frontier in assemble_tool_list(..., include_frontier=False)` is `False`; `... is True` when `include_frontier=True`.
- [ ] All modified files pass project-configured lint/format checks with zero errors.