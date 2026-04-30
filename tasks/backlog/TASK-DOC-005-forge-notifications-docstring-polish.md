---
id: TASK-DOC-005
title: forge_notifications.py docstring polish
task_type: documentation
parent_review: TASK-REV-C241
feature_id: FEAT-43DE
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
priority: high
tags:
  - documentation
  - infrastructure
  - feat-jarvis-internal-001
  - phase-3-close
status: backlog
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-DOC-005 — forge_notifications.py docstring polish

## Description

Polish the module docstring of `src/jarvis/infrastructure/forge_notifications.py`
to the FEAT-JARVIS-INTERNAL-001 consistent shape: Purpose paragraph (≥ 2
sentences), FEAT-JARVIS origin attribution, design-doc link, ≥ 1 DDR
citation, no `TASK-J\d{3}-\d{3}` references, line count between 20 and 250.

This is the densest TASK-Jxxx target in the feature: **8 hits** across
the module docstring narrative, §-section header comments, and inline
references in function/method docstrings (per `grep -n "TASK-J" src/jarvis/infrastructure/forge_notifications.py`):

| Line | Context | Treatment |
|---|---|---|
| 3 | `TASK-J005-002 landed the Pydantic v2 declarative schema...` | Module docstring narrative — reword to FEAT-JARVIS-005. |
| 7 | `TASK-J005-003 (this revision) appends the subscriber...` | Module docstring narrative — reword. |
| 19 | `the canonical render shape consumed by ``cli/main.py`` (TASK-J005-007).` | Module docstring; replace `(TASK-J005-007)` with `(see DDR-030)`. |
| 38 | `TASK-J005-003 alongside the subscriber.` | Below the module docstring; treat the same. |
| 80 | `TASK-J005-003 — this task is schema-only.` | Class docstring; reword. |
| 183 | `The subscriber + correlation-map land in TASK-J005-003; this task` | Class docstring; reword. |
| 221 | `# §3 — ForgeNotificationsSubscriber (TASK-J005-003)` | Section header; rewrite as `# §3 — ForgeNotificationsSubscriber (DDR-027 + DDR-028)`. |
| 427 | `# Late binding (TASK-J005-008 lifecycle wiring)` | Inline comment; rewrite as `# Late binding (FEAT-JARVIS-005 lifecycle wiring)`. |
| 462 | `Entry point used by :func:`jarvis.tools.queue_build` (TASK-J005-005)` | Method docstring; replace `(TASK-J005-005)` with `(FEAT-JARVIS-005)`. |

This is the only candidate where the polish meaningfully touches non-module
docstrings — but that's acceptable because the ASSUM-003 entire-file ban
applies regardless of where in the file the TASK-Jxxx token sits.

## Scope

**In scope:**
- Module-level docstring at the top of `src/jarvis/infrastructure/forge_notifications.py`.
- Any TASK-Jxxx token anywhere in the file (per ASSUM-003 entire-file ban).

**Out of scope:**
- Type annotations; method bodies; signatures; any executable code.
- Substantive rewrites of function/method docstrings — only the TASK-Jxxx
  tokens themselves should be substituted.

## Acceptance Criteria

- [ ] First paragraph of the module docstring describes the module's purpose
      in ≥ 2 complete sentences (ASSUM-008).
- [ ] Module docstring references `FEAT-JARVIS-005` as origin (Group A.2 —
      this is the only FEAT-JARVIS-005 module in scope).
- [ ] Module docstring cites at least one DDR identifier resolving under
      `docs/design/FEAT-JARVIS-005/decisions/` (Group A.3) — at minimum
      DDR-026 (forge_notifications module location), DDR-027 (ephemeral
      push consumer), or DDR-028 (correlation-map LRU).
- [ ] Module docstring references the design doc at
      `docs/design/FEAT-JARVIS-005/design.md` (Group A.4).
- [ ] Each cited design-doc / DDR file exists on disk and is readable
      (Group C.3).
- [ ] **Entire file** contains **no** token matching `TASK-J\d{3}-\d{3}`
      (Group C.4 / `@smoke`, ASSUM-003 — covers all 8 hits in the table
      above).
- [ ] Module docstring line count is ≥ 20 and ≤ 250 (Group B.2,
      ASSUM-001/002).
- [ ] No executable Python statement is modified (Group C.2).

## Test Requirements

Minimal grep/seam tests only (per Context B Q3 and review R-4):

- [ ] `grep -nE "TASK-J[0-9]{3}-[0-9]{3}" src/jarvis/infrastructure/forge_notifications.py`
      returns no matches.
- [ ] `grep -n "FEAT-JARVIS-005" src/jarvis/infrastructure/forge_notifications.py`
      returns ≥ 1 match within the module docstring.
- [ ] `grep -nE "DDR-0(25|26|27|28|29|30|31)" src/jarvis/infrastructure/forge_notifications.py`
      returns ≥ 1 match within the module docstring.
- [ ] `python3 -c "import ast; m = ast.parse(open('src/jarvis/infrastructure/forge_notifications.py').read()); d = ast.get_docstring(m); assert d and 20 <= len(d.splitlines()) <= 250"`
      exits cleanly.
- [ ] `python3 -c "import jarvis.infrastructure.forge_notifications"` succeeds.

Full pytest, mypy, ruff, and `langgraph dev` regression deferred to
TASK-DOC-007.

## Implementation Notes

- 9 substitutions across 9 line locations (lines 3, 7, 19, 38, 80, 183,
  221, 427, 462). Most are mechanical — the table above gives the
  recommended replacement for each.
- The `§3 — ForgeNotificationsSubscriber` header (line 221) is the most
  visible change; preserve readability by using the DDR pair instead of
  TASK-Jxxx.
- This is the highest-volume task in wave 1 (3 complexity vs 2 for the
  others) but not the highest-risk — that's TASK-DOC-003 with the
  DDR-021 / ADR-ARCH-017 preservation invariant.
