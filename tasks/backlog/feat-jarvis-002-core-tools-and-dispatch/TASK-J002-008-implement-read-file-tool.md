---
id: TASK-J002-008
title: Implement read_file tool
task_type: feature
status: in_review
created: 2026-04-24 06:55:00+00:00
updated: 2026-04-24 06:55:00+00:00
priority: high
complexity: 4
wave: 2
implementation_mode: task-work
estimated_minutes: 60
dependencies:
- TASK-J002-001
- TASK-J002-004
parent_review: TASK-REV-J002
feature_id: FEAT-J002
tags:
- phase-2
- jarvis
- feat-jarvis-002
scenarios_covered:
- Reading a UTF-8 text file inside the workspace returns its contents
- read_file enforces the one megabyte file size limit
- Reading a path outside the workspace returns a path traversal error
- Reading a path that does not exist returns a not-found error
- Reading a directory instead of a file returns a not-a-file error
- Reading a file with invalid UTF-8 bytes returns an encoding error
- read_file rejects paths that evade the workspace guard
- Every tool converts internal errors into structured strings rather than raising
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J002
  base_branch: main
  started_at: '2026-04-25T16:27:08.367100'
  last_updated: '2026-04-25T16:45:38.708844'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-25T16:27:08.367100'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---
# Implement read_file tool

**Feature:** FEAT-JARVIS-002 "Core Tools & Capability-Driven Dispatch Tools"
**Wave:** 2 | **Mode:** task-work | **Complexity:** 4/10 | **Est.:** 60 min
**Parent review:** [TASK-REV-J002](../../in_review/TASK-REV-J002-plan-core-tools-and-dispatch.md)

## Description

Read-only filesystem access scoped to config.workspace_root. Rejects path traversal, symlinks out, null-byte paths, non-UTF-8 bytes, and files over 1 MiB. Never raises — all errors are structured strings per ADR-ARCH-021.

## Acceptance Criteria

- [ ] `src/jarvis/tools/general.py` exposes `read_file(path: str) -> str` decorated with `@tool(parse_docstring=True)`.
- [ ] Docstring matches API-tools.md §1.1 byte-for-byte (it IS the contract per DDR-005 precedent).
- [ ] Resolves `path` relative to `config.workspace_root`; rejects paths whose `os.path.realpath` resolves outside workspace with `ERROR: path_traversal — path resolves outside workspace: <resolved>`.
- [ ] Rejects paths containing embedded null bytes (`\x00`) with `ERROR: path_traversal — ...` (ASSUM-003: same category, no new one).
- [ ] Rejects symlinks whose resolved target lies outside workspace with `ERROR: path_traversal — ...` (ASSUM-002).
- [ ] Returns `ERROR: not_found — ...` for non-existent paths; `ERROR: not_a_file — ...` for directories; `ERROR: too_large — ...` for files > 1 MiB (boundary: exactly 1 MiB = accept; 1 MiB + 1 byte = reject); `ERROR: encoding — ...` for non-UTF-8 bytes.
- [ ] Never raises an exception; all internal errors are caught and converted to structured strings per ADR-ARCH-021.
- [ ] Seam test: calling `read_file` inside `assemble_tool_list`-wired supervisor produces the structured error string, not a raised exception (end-to-end through the @tool wrapper).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Scenarios Covered

- Reading a UTF-8 text file inside the workspace returns its contents
- read_file enforces the one megabyte file size limit
- Reading a path outside the workspace returns a path traversal error
- Reading a path that does not exist returns a not-found error
- Reading a directory instead of a file returns a not-a-file error
- Reading a file with invalid UTF-8 bytes returns an encoding error
- read_file rejects paths that evade the workspace guard
- Every tool converts internal errors into structured strings rather than raising

## Test Execution Log

_Populated by `/task-work` during implementation._
