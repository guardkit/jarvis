---
id: TASK-J003-011
title: Implement escalate_to_frontier Layer 2 (executor assertion)
task_type: feature
status: pending
created: 2026-04-24T00:00:00Z
updated: 2026-04-24T00:00:00Z
priority: high
complexity: 5
wave: 2
implementation_mode: task-work
estimated_minutes: 75
dependencies: [TASK-J003-010]
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags: [phase-2, jarvis, feat-jarvis-003, dispatch, frontier, ddr-014, security]
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
