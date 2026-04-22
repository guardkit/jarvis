---
id: TASK-J001-011
title: .env.example + README Quickstart + .gitignore audit
task_type: documentation
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 6
implementation_mode: direct
complexity: 2
dependencies:
- TASK-J001-003
- TASK-J001-008
status: in_review
tags:
- documentation
- env-example
- readme
- gitignore
- security
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T23:17:29.117373'
  last_updated: '2026-04-21T23:21:32.896196'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-21T23:17:29.117373'
    player_summary: "Created .env.example with all four required variables (JARVIS_SUPERVISOR_MODEL,\
      \ JARVIS_OPENAI_BASE_URL, JARVIS_LOG_LEVEL, JARVIS_MEMORY_STORE_BACKEND) with\
      \ descriptive comments and sensible defaults matching JarvisConfig in settings.py.\
      \ Verified .gitignore already correctly ignores .env but not .env.example \u2014\
      \ no .gitignore changes needed. Added a Quickstart section to README.md with\
      \ clone, venv, install, env setup, test, and CLI commands. No FEAT-002/003/004\
      \ content present in README."
    player_success: true
    coach_success: true
---

# Task: developer surface — `.env.example`, README Quickstart, `.gitignore` audit

The "on-ramp" for a new developer (and for Rich to re-bootstrap a laptop). Also the @security tripwire: `.env` must be ignored, `.env.example` must be committed.

## Context

- [phase1-build-plan.md §Change 11](../../../docs/research/ideas/phase1-build-plan.md)
- Feature file @edge-case @security "The .env file is git-ignored"

## Scope

**Files (NEW / UPDATED):**

- `.env.example` (NEW) — documented env vars with comments:
  ```
  # Supervisor model — default routes to local llama-swap on GB10
  JARVIS_SUPERVISOR_MODEL=openai:jarvis-reasoner
  JARVIS_OPENAI_BASE_URL=http://promaxgb10-41b1:9000/v1

  # Cloud provider keys (only set if switching JARVIS_SUPERVISOR_MODEL to a cloud model)
  # JARVIS_ANTHROPIC_API_KEY=
  # JARVIS_GOOGLE_API_KEY=

  # Logging
  JARVIS_LOG_LEVEL=INFO

  # Memory store backend: in_memory | file | graphiti (only in_memory implemented in Phase 1)
  JARVIS_MEMORY_STORE_BACKEND=in_memory
  ```

- `README.md` (UPDATED) — add Quickstart section above existing content:
  ```markdown
  ## Quickstart

      git clone ...
      cd jarvis
      python -m venv .venv && source .venv/bin/activate
      pip install -e ".[dev]"
      cp .env.example .env          # edit as needed
      jarvis version                # 0.1.0
      jarvis health                 # config + supervisor build + memory store
      jarvis chat                   # start talking
  ```
  Do NOT write a comprehensive manual here — Phase 1 Quickstart only.

- `.gitignore` audit — verify these patterns are present (add if missing):
  - `.venv/`, `.env`, `__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `.pytest_cache/`, `dist/`, `build/`, `*.egg-info/`
  - **`.env` MUST be ignored** — the @edge-case @security scenario asserts this.
  - **`.env.example` MUST NOT be ignored** — it's the committed template.

## Acceptance Criteria

- `.env.example` exists and includes `JARVIS_SUPERVISOR_MODEL`, `JARVIS_OPENAI_BASE_URL`, `JARVIS_LOG_LEVEL`, `JARVIS_MEMORY_STORE_BACKEND` with comments.
- `git check-ignore .env` prints `.env` (it IS ignored).
- `git check-ignore .env.example` exits non-zero (it is NOT ignored).
- `README.md` contains a Quickstart section with the commands above; no mention of FEAT-002/003/004 content (scope invariant).

## Coach Validation

- Coach verifies `.env.example` does NOT contain real secret values (only placeholders / comments).
- Coach verifies README Quickstart uses `pip install -e ".[dev]"` OR `uv sync --dev` — either is acceptable.
