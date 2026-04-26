---
id: TASK-J003-006
title: "pyproject \u2014 provider SDKs + langgraph dev dep"
task_type: scaffolding
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
- pyproject
- dependencies
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J003
  base_branch: main
  started_at: '2026-04-25T17:58:06.475871'
  last_updated: '2026-04-25T18:04:57.370270'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T17:58:06.475871'
    player_summary: 'Manifest-only change to pyproject.toml: (1) appended `anthropic>=0.40`
      to base [project].dependencies so the Opus-alternate frontier-escalation path
      works without the [providers] extras (AC-002); (2) appended `google-genai>=0.3.0`
      (raw Gemini SDK, distinct from the `langchain-google-genai` wrapper) to [project.optional-dependencies].providers
      (AC-001); (3) added a new [project.optional-dependencies].dev group containing
      `langgraph-cli>=0.1` (AC-003) and mirrored the same pin in [dependency-group'
    player_success: true
    coach_success: true
---

# pyproject — provider SDKs + langgraph dev dep

**Feature:** FEAT-JARVIS-003
**Wave:** 1 | **Mode:** direct | **Complexity:** 2/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

Ensure `pyproject.toml` carries the provider SDKs needed by `escalate_to_frontier` (Gemini default; Opus alternate) and the langgraph CLI needed for the multi-graph ASGI smoke test. Preserve the `deepagents >=0.5.3, <0.6` pin.

## Acceptance Criteria

- [ ] `pyproject.toml` `[project.optional-dependencies].providers` (the existing extras group) includes `google-genai>=0.3.0` (Gemini SDK) — add if absent.
- [ ] `anthropic` is already in base `dependencies` (verify; no change needed if present).
- [ ] `[project.optional-dependencies].dev` includes `langgraph-cli` — add if absent. This is what powers `python -m langgraph dev`.
- [ ] `deepagents` pin remains `>=0.5.3,<0.6` — no upgrade in this task (gated by ADR-ARCH-025).
- [ ] `uv sync` completes without resolution errors; `uv pip list | grep -iE "(google-genai|anthropic|langgraph|deepagents)"` shows all four packages present.
- [ ] No runtime code change; this is a dependency-manifest task only.
- [ ] Lint/format: pyproject.toml is conventionally exempt from formatter; the task is green if `uv sync` succeeds.
