---
id: TASK-J001-010
title: Reserve-empty packages (tools, subagents, skills, routing, watchers, discovery,
  learning, adapters)
task_type: scaffolding
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
status: in_review
tags:
- scaffolding
- reserved-packages
- adr-arch-006
- namespace-allocation
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T22:31:06.697784'
  last_updated: '2026-04-21T22:34:46.721516'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-21T22:31:06.697784'
    player_summary: "Created the src/jarvis/ parent package with an empty __init__.py\
      \ and eight reserved-empty sub-packages per ADR-ARCH-006. Each reserved __init__.py\
      \ contains a single-line comment identifying the reserving feature (e.g. '#\
      \ Reserved for FEAT-JARVIS-002 (dispatch tools)'). No code, no imports, no public\
      \ symbols \u2014 just namespace reservation to prevent import-ordering and directory-creation\
      \ race conditions in later features."
    player_success: true
    coach_success: true
---

# Task: Reserve-empty package namespaces per ADR-ARCH-006

Create the eight reserved-empty packages that later v1 features populate. Landing these in Phase 1 avoids the "later feature creates parent directory + import ordering lottery" class of bugs.

## Context

- [ADR-ARCH-006 five-group module layout](../../../docs/architecture/decisions/ADR-ARCH-006-five-group-module-layout.md)
- [design.md §7 module layout](../../../docs/design/FEAT-JARVIS-001/design.md)

## Scope

**Files (NEW — all empty `__init__.py`):**

- `src/jarvis/tools/__init__.py`       — Group C, reserved for FEAT-JARVIS-002
- `src/jarvis/subagents/__init__.py`   — Group A, reserved for FEAT-JARVIS-003
- `src/jarvis/skills/__init__.py`      — Group A, reserved for FEAT-JARVIS-007
- `src/jarvis/routing/__init__.py`     — Group B, reserved for FEAT-JARVIS-002
- `src/jarvis/watchers/__init__.py`    — Group B, reserved for FEAT-JARVIS-003
- `src/jarvis/discovery/__init__.py`   — Group B, reserved for FEAT-JARVIS-004
- `src/jarvis/learning/__init__.py`    — Group B, reserved for FEAT-JARVIS-008 (v1.5)
- `src/jarvis/adapters/__init__.py`    — Group D, reserved for FEAT-JARVIS-004+

Each `__init__.py` should be **empty** or contain only a single-line comment identifying the reserving feature:

```python
# Reserved for FEAT-JARVIS-002 (dispatch tools)
```

## Acceptance Criteria

- All eight packages are importable: `import jarvis.tools`, `import jarvis.subagents`, etc. — none raise `ModuleNotFoundError`.
- `from jarvis.tools import *` yields nothing (empty namespace).
- Each `__init__.py` is <=1 line of content (reserved comment only, no code).
