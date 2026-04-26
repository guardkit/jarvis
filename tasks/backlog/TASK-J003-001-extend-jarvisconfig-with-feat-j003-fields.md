---
id: TASK-J003-001
title: Extend JarvisConfig with FEAT-JARVIS-003 fields
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
- config
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-25T17:58:06.463907'
  last_updated: '2026-04-25T18:02:52.672156'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:58:06.463907'
    player_summary: 'Extended JarvisConfig (src/jarvis/config/settings.py) with the
      four FEAT-JARVIS-003 fields in a new ''-- FEAT-JARVIS-003'' section placed after
      the existing Phase 2 block: (1) llama_swap_base_url (str, default http://promaxgb10-41b1:9000,
      picked up via the existing JARVIS_ env_prefix as JARVIS_LLAMA_SWAP_BASE_URL);
      (2) frontier_default_target (Literal[GEMINI_3_1_PRO, OPUS_4_7], default GEMINI_3_1_PRO,
      env JARVIS_FRONTIER_DEFAULT_TARGET); (3) gemini_api_key (SecretStr | None) defined
      with Field(val'
    player_success: true
    coach_success: true
---

# Extend JarvisConfig with FEAT-JARVIS-003 fields

**Feature:** FEAT-JARVIS-003 "Async Subagent for Model Routing + Attended Frontier Escape"
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Add the four config fields FEAT-JARVIS-003 needs, preserving the FEAT-JARVIS-001/002 field set unchanged. Per design.md §7 and §8.

## Acceptance Criteria

- [ ] `src/jarvis/config/settings.py` gains `llama_swap_base_url: str = "http://promaxgb10-41b1:9000"` (env `JARVIS_LLAMA_SWAP_BASE_URL`).
- [ ] `frontier_default_target: Literal["GEMINI_3_1_PRO", "OPUS_4_7"] = "GEMINI_3_1_PRO"` (env `JARVIS_FRONTIER_DEFAULT_TARGET`).
- [ ] `gemini_api_key: SecretStr | None = None` (env `GOOGLE_API_KEY`); `anthropic_api_key: SecretStr | None = None` (env `ANTHROPIC_API_KEY`) — if not already present from FEAT-001/002.
- [ ] `attended_adapter_ids: frozenset[str] = frozenset({"telegram", "cli", "dashboard", "reachy"})` (ADR-ARCH-016 consumer-surface list).
- [ ] No existing field renamed or removed; Phase 1 + FEAT-J002 call sites still work.
- [ ] `.env.example` updated with the four new variables with explanatory comments.
- [ ] All modified files pass project-configured lint/format checks with zero errors.
