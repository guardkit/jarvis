---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T18:37:52.313690'
  max_turns: 30
  started_at: '2026-04-25T18:21:47.096225'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T18:21:47.096225'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 5
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-010
estimated_minutes: 75
feature_id: FEAT-J003
id: TASK-J003-011
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- dispatch
- frontier
- ddr-014
- security
task_type: feature
title: Implement escalate_to_frontier Layer 2 (executor assertion)
updated: 2026-04-24 00:00:00+00:00
wave: 2
---

# Implement escalate_to_frontier Layer 2 (executor assertion)

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Layer 2 of DDR-014 belt+braces: **executor assertion** — the tool body rejects non-attended sessions AND async-subagent caller frames *before* any provider call. Two detection paths (middleware metadata AND session-state) per review Finding F6: if one fails, the other must still hold.

## Acceptance Criteria

- [ ] `escalate_to_frontier` (extended from TASK-J003-010) looks up the active session's `adapter_id` via `SessionManager.current_session()` — `ambient` / `learning` / `pattern-c` adapters return `"ERROR: attended_only — escalate_to_frontier cannot be invoked from {adapter_id} adapter"`.
- [ ] Attended `adapter_id` set: `{"telegram", "cli", "dashboard", "reachy"}` (from `config.attended_adapter_ids`) — only these pass.
- [ ] Second detection path: the tool body also checks whether the call frame is inside an `AsyncSubAgent` execution — via `AsyncSubAgentMiddleware` metadata if available (ASSUM-FRONTIER-CALLER-FRAME), else via session-state "currently-in-subagent" flag. An affirmative check returns `"ERROR: attended_only — escalate_to_frontier cannot be invoked from async-subagent frame"`.
- [ ] Both assertion paths run before ANY provider SDK call — no outbound HTTP attempt on rejection.
- [ ] Spoofed-ambient case: an **attended** session with an in-progress async-subagent frame is still rejected (scenario: *A spoofed-ambient invocation from inside an attended session is rejected*) — the async-subagent frame check overrides the attended-adapter pass.
- [ ] A prompt-injection instruction body ("ignore the gate and ...") does not alter the assertion flow — the gate fires on `adapter_id` / frame, not on instruction content. Instruction body is never echoed in the rejection string (ASSUM-006).
- [ ] `log_frontier_escalation` records `outcome="attended_only"` on the structured log entry for every rejection.
- [ ] If `AsyncSubAgentMiddleware` metadata is unavailable in DeepAgents 0.5.3 (verified at test time per ASSUM-FRONTIER-CALLER-FRAME), the session-state fallback still holds — tests cover both paths (review Finding F6).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the spoofed-ambient scenario as a failing test FIRST (this is the security-critical case and the one that would regress silently).