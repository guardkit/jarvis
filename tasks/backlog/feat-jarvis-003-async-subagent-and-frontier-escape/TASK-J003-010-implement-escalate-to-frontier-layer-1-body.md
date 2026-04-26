---
id: TASK-J003-010
title: Implement escalate_to_frontier Layer 1 (body + docstring + config/provider
  branches)
task_type: feature
status: in_progress
created: 2026-04-24 00:00:00+00:00
updated: 2026-04-24 00:00:00+00:00
priority: high
complexity: 6
wave: 2
implementation_mode: task-work
estimated_minutes: 113
dependencies:
- TASK-J003-001
- TASK-J003-002
- TASK-J003-004
- TASK-J003-006
parent_review: TASK-REV-J003
feature_id: FEAT-J003
tags:
- phase-2
- jarvis
- feat-jarvis-003
- dispatch
- frontier
- ddr-014
autobuild_state:
  current_turn: 0
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-26T08:32:58.282126'
  last_updated: '2026-04-26T08:32:58.282128'
  turns: []
---

# Implement escalate_to_frontier Layer 1 (body + docstring + config/provider branches)

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 6/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Layer 1 of the three-layer belt+braces gate per DDR-014. The tool body: docstring prohibition + provider SDK invocation (Gemini default, Opus alternate) + structured error returns for missing keys / provider unavailability / empty body. Executor assertions (Layer 2) land in TASK-J003-011; tool-registry absence (Layer 3) lands in TASK-J003-012. This task is **one of two short Coach loops** on the escalate tool per Context A concern #5.

## Acceptance Criteria

- [ ] `src/jarvis/tools/dispatch.py` — the FEAT-JARVIS-002 DDR-005/C2 reserved slot — gains `escalate_to_frontier(instruction: str, target: FrontierTarget = FrontierTarget.GEMINI_3_1_PRO) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring (the contract per DDR-005 precedent) states verbatim: "ATTENDED-ONLY — cloud escape hatch. Never invoke from ambient, learning, or async-subagent contexts."
- [ ] `target=GEMINI_3_1_PRO` invokes `google_genai:gemini-3.1-pro` via the `google-genai` SDK; `target=OPUS_4_7` invokes `anthropic:claude-opus-4-7` via the `anthropic` SDK.
- [ ] Out-of-enum `target` is rejected at `@tool(parse_docstring=True)` argument coercion before the function body runs (ASSUM-005, confirmed) — no provider contacted.
- [ ] Missing `GOOGLE_API_KEY` when called with Gemini target returns `"ERROR: config_missing — GOOGLE_API_KEY not set"`; missing `ANTHROPIC_API_KEY` when called with Opus target returns `"ERROR: config_missing — ANTHROPIC_API_KEY not set"`. No outbound request made in either case.
- [ ] Unreachable provider returns `"DEGRADED: provider_unavailable — <short reason>"`; no exception propagates.
- [ ] Empty body from provider maps to `"DEGRADED: provider_unavailable — empty response"` (ASSUM-001, confirmed).
- [ ] Happy path returns the provider's response text as a `str` — not the raw SDK response object.
- [ ] Every successful OR degraded call emits exactly one structured INFO log via `log_frontier_escalation(ctx, logger)` with `model_alias="cloud-frontier"` (budget trace per ADR-ARCH-030). `outcome` field set to `"success"`, `"config_missing"`, `"provider_unavailable"`, or `"degraded_empty"`.
- [ ] **Instruction body is never logged nor echoed in any error/degraded return string** (ASSUM-006, confirmed; concern #6 in the review report).
- [ ] Never raises — all error paths produce a structured string per ADR-ARCH-021.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the config_missing branches + degraded empty-body branch as failing tests BEFORE implementing (so the redaction posture is pinned before the happy path exists).
