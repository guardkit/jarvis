---
id: TASK-DOC-001
title: nats_client.py docstring polish
task_type: documentation
parent_review: TASK-REV-C241
feature_id: FEAT-43DE
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
priority: high
tags:
- documentation
- infrastructure
- feat-jarvis-internal-001
- phase-3-close
status: completed
created: 2026-04-30 00:00:00+00:00
updated: 2026-04-30 00:00:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-43DE
  base_branch: main
  started_at: '2026-04-30T20:13:45.457153'
  last_updated: '2026-04-30T20:16:36.743736'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-30T20:13:45.457153'
    player_summary: 'Polished the module docstring of src/jarvis/infrastructure/nats_client.py
      without touching any executable statement. Two surgical changes: (1) removed
      the `TASK-J004-006` token from line 3 (AC-006) by reframing the second paragraph
      to lead with `Origin: FEAT-JARVIS-004 (Group A.2 row).`; (2) corrected the cited
      path for ADR-ARCH-020 from the non-existent `docs/design/decisions/ADR-ARCH-020.md`
      to the real `docs/architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md`
      so AC-005 (every ci'
    player_success: true
    coach_success: true
---

# TASK-DOC-001 — nats_client.py docstring polish

## Description

Polish the module docstring of `src/jarvis/infrastructure/nats_client.py` to
the FEAT-JARVIS-INTERNAL-001 consistent shape: Purpose paragraph (≥ 2
sentences), FEAT-JARVIS origin attribution, design-doc link, ≥ 1 DDR
citation, no `TASK-J\d{3}-\d{3}` references, line count between 20 and 250.

The current module docstring (lines 1–37) opens with
`"""Async wrapper around ``nats-py`` providing connection lifecycle.\n\nTASK-J004-006 / FEAT-JARVIS-004. The wrapper is intentionally thin — its job is to:..."`.
The `TASK-J004-006 / ` prefix on line 3 is the only TASK-Jxxx hit in this
file (per `grep -n "TASK-J" src/jarvis/infrastructure/nats_client.py`).

## Scope

**In scope:**
- Module-level docstring at the top of `src/jarvis/infrastructure/nats_client.py`.

**Out of scope:**
- Class docstrings (`NATSClient.__doc__`, etc.).
- Method docstrings.
- Any executable code (no refactors, no type-annotation changes).
- Any other module under `src/jarvis/infrastructure/`.

## Acceptance Criteria

- [ ] First paragraph of the module docstring describes the module's purpose
      in ≥ 2 complete sentences (ASSUM-008).
- [ ] Docstring references `FEAT-JARVIS-004` as origin (Group A.2 row).
- [ ] Docstring cites at least one DDR identifier resolving under
      `docs/design/FEAT-JARVIS-004/decisions/` (Group A.3 row).
- [ ] Docstring references the design doc at
      `docs/design/FEAT-JARVIS-004/design.md` (Group A.4 row).
- [ ] Each cited design-doc / DDR file exists on disk and is readable
      (Group C.3).
- [ ] Polished docstring contains **no** token matching `TASK-J\d{3}-\d{3}`
      (Group C.4 / `@smoke`, ASSUM-003).
- [ ] Docstring line count is ≥ 20 and ≤ 250 (Group B.2, ASSUM-001/002).
- [ ] No executable Python statement is modified (Group C.2).

## Test Requirements

Minimal grep/seam tests only (per Context B Q3 and review R-4):

- [ ] `grep -nE "TASK-J[0-9]{3}-[0-9]{3}" src/jarvis/infrastructure/nats_client.py`
      returns no matches.
- [ ] `grep -n "FEAT-JARVIS-004" src/jarvis/infrastructure/nats_client.py`
      returns ≥ 1 match within the module docstring.
- [ ] `grep -nE "DDR-0(16|17|18|19|20|21|22|23|24)" src/jarvis/infrastructure/nats_client.py`
      returns ≥ 1 match within the module docstring.
- [ ] `python3 -c "import ast; m = ast.parse(open('src/jarvis/infrastructure/nats_client.py').read()); d = ast.get_docstring(m); assert d and 20 <= len(d.splitlines()) <= 250, f'docstring length {len(d.splitlines()) if d else 0}'"`
      exits cleanly.
- [ ] `python3 -c "import jarvis.infrastructure.nats_client"` succeeds
      (smoke import — the cross-module @smoke gate runs in TASK-DOC-007).

Full pytest, mypy, ruff, and `langgraph dev` regression are deferred to
TASK-DOC-007.

## Implementation Notes

- Preserve the substance of the current docstring (DDR-021 soft-fail
  invariant, `nats-py` version-churn isolation, drain idempotency,
  reconnect-callback wiring) — this is a polish-not-rewrite.
- Replace the `TASK-J004-006 / FEAT-JARVIS-004.` opener with a clean
  Purpose paragraph that names FEAT-JARVIS-004 as origin without the
  TASK-Jxxx prefix.
- The existing `References` section (lines 29–36) already cites
  DDR-021 and the design doc — keep the structure, add the FEAT-JARVIS-004
  origin attribution somewhere in the first paragraph.
