---
autobuild_state:
  base_branch: main
  current_turn: 0
  last_updated: '2026-04-25T21:10:31.980318'
  max_turns: 30
  started_at: '2026-04-25T21:10:31.980315'
  turns: []
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 5
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-007
- TASK-J003-015
estimated_minutes: 75
feature_id: FEAT-J003
id: TASK-J003-019
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- tests
- ddr-015
task_type: testing
title: Unit tests — LlamaSwapAdapter + swap-aware voice-ack
updated: 2026-04-24 00:00:00+00:00
wave: 4
---

# Unit tests — LlamaSwapAdapter + swap-aware voice-ack

**Feature:** FEAT-JARVIS-003
**Wave:** 4 | **Mode:** task-work | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Two test files: `tests/test_adapters_llamaswap.py` for the stubbed adapter, and `tests/test_swap_aware_voice_ack.py` for the supervisor's voice-ack policy (replaces the scope doc's retired "quick_local fallback test").

## Acceptance Criteria

- [ ] `tests/test_adapters_llamaswap.py` — default stub: `LlamaSwapAdapter(base_url="http://stub").get_status("jarvis-reasoner")` returns `SwapStatus(loaded_model="jarvis-reasoner", eta_seconds=0, source="stub")`.
- [ ] Same file — degraded stub: `_stub_response` callable returning `SwapStatus(loaded_model="jarvis-reasoner", eta_seconds=180, source="stub")` flows through unchanged (boundary for >30s-ETA branch).
- [ ] Same file — negative ETA rejected at model level: `SwapStatus(loaded_model="x", eta_seconds=-1)` raises `ValidationError` (scenario: *Swap status enforces a non-negative ETA*).
- [ ] Same file — idempotency: three successive calls to `get_status("jarvis-reasoner")` return equivalent `SwapStatus` instances; no internal counter mutated (scenario: *Repeated swap-status reads for the same alias return consistent results*).
- [ ] Same file — source marker: default stub returns `source="stub"` (scenario: *The llama-swap adapter reports a stub source in Phase 2*).
- [ ] `tests/test_swap_aware_voice_ack.py` — parametrised ETA boundary table:
  | eta_seconds | voice-reactive adapter | emit_ack |
  |---|---|---|
  | 0   | reachy | False |
  | 30  | reachy | False |
  | 31  | reachy | True  |
  | 240 | reachy | True  |
  | 240 | cli    | False (non-voice adapter never gets ack) |
- [ ] Same file — when `emit_ack=True` on a voice-reactive session, the supervisor state captures a "queued for dispatch once swap completes" marker; no audio I/O in test (stub TTS hook).
- [ ] No network I/O; no live provider calls.
- [ ] `uv run pytest tests/test_adapters_llamaswap.py tests/test_swap_aware_voice_ack.py -v` passes with ≥ 80% coverage on both modules.
- [ ] All modified files pass project-configured lint/format checks with zero errors.