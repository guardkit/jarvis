---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-25T19:27:48.199552'
  max_turns: 30
  started_at: '2026-04-25T19:10:07.831500'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-25T19:10:07.831500'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
complexity: 5
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-007
- TASK-J003-009
- TASK-J003-012
- TASK-J003-013
estimated_minutes: 75
feature_id: FEAT-J003
id: TASK-J003-015
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- wiring
- lifecycle
task_type: feature
title: Extend lifecycle.startup — async subagents + ambient tool factory + LlamaSwapAdapter
updated: 2026-04-24 00:00:00+00:00
wave: 3
---

# Extend lifecycle.startup — async subagents + ambient tool factory + LlamaSwapAdapter

**Feature:** FEAT-JARVIS-003
**Wave:** 3 | **Mode:** task-work (TDD — complexity ≥ 5) | **Complexity:** 5/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Per design.md §8 "new lines marked ← NEW in FEAT-JARVIS-003". Four additions to `lifecycle.startup`: construct `LlamaSwapAdapter`; build `async_subagents`; assemble `tool_list_attended` (include frontier) and `tool_list_ambient` (exclude frontier) via `assemble_tool_list`; pass both through to `build_supervisor`. Also: set `OPENAI_BASE_URL=<config.llama_swap_base_url>/v1` at process level so the jarvis_reasoner graph routes correctly. Also: add swap-aware voice-ack logic — if the active adapter is voice-reactive AND `llamaswap_adapter.get_status("jarvis-reasoner").eta_seconds > 30`, emit TTS ack stub and queue the dispatch.

## Acceptance Criteria

- [ ] `src/jarvis/infrastructure/lifecycle.py` — `startup(config)` constructs `llamaswap_adapter = LlamaSwapAdapter(base_url=config.llama_swap_base_url)`.
- [ ] `startup` calls `async_subagents = build_async_subagents(config)` and threads it into `build_supervisor(..., async_subagents=async_subagents, ...)`.
- [ ] `startup` assembles attended AND ambient tool lists via `assemble_tool_list(...)` with `include_frontier=True` / `False` respectively, and passes `ambient_tool_factory=lambda: tool_list_ambient` into `build_supervisor`.
- [ ] `OPENAI_BASE_URL` environment variable is set to `<config.llama_swap_base_url>/v1` before `build_async_subagents` runs (graph compilation reads this).
- [ ] `AppState` is extended to carry `llamaswap_adapter: LlamaSwapAdapter` for later use by the supervisor's swap-aware policy.
- [ ] Swap-aware voice-ack policy: helper function `should_emit_voice_ack(adapter_id: str, swap_status: SwapStatus) -> bool` returns `True` iff `adapter_id in {"reachy"}` (or voice-reactive set from config) AND `swap_status.eta_seconds > 30`. Boundary behaviour: `eta_seconds` of 0 → `False`; 30 → `False`; 31 → `True`; 240 → `True` (scenario: *Swap status above the voice-ack threshold triggers the supervisor TTS acknowledgement*).
- [ ] When `should_emit_voice_ack` returns `True`, the supervisor emits the TTS ack stub and queues the request for dispatch once the swap completes (scenario: *A voice-reactive session above the swap-ETA threshold receives a TTS acknowledgement and the request is queued*).
- [ ] Phase 1 + FEAT-J002 startup behaviour preserved: existing AppState fields unchanged; `session_manager`, `store`, `capability_registry` still wired as before.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

**TDD note:** Write the voice-ack boundary table (ETA 0/30/31/240) as a parametrised failing test FIRST.