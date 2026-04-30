---
id: TASK-DOC-003
title: capabilities_registry.py docstring polish (preserve DDR-021 / ADR-ARCH-017)
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
  started_at: '2026-04-30T20:13:45.461445'
  last_updated: '2026-04-30T20:16:55.881819'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-30T20:13:45.461445'
    player_summary: Polished the capabilities_registry.py module docstring and surrounding
      doc/comment blocks. (1) Fixed the broken cross-reference to ADR-ARCH-017 by
      pointing at the actual on-disk path docs/architecture/decisions/ADR-ARCH-017-static-skill-declaration-v1.md.
      (2) Removed the two TASK-J\d{3}-\d{3} tokens that lived in a module-level comment
      (TASK-J004-007) and inside the LiveCapabilitiesRegistry.create docstring (TASK-J004-006)
      to satisfy AC-008's whole-file hygiene rule. The phrasing was rewritten s
    player_success: true
    coach_success: true
---

# TASK-DOC-003 — capabilities_registry.py docstring polish

## Description

Polish the module docstring of `src/jarvis/infrastructure/capabilities_registry.py`
to the FEAT-JARVIS-INTERNAL-001 consistent shape: Purpose paragraph (≥ 2
sentences), FEAT-JARVIS origin attribution, design-doc link, ≥ 1 DDR
citation, no `TASK-J\d{3}-\d{3}` references, line count between 20 and 250.

**Critical preservation requirement (per review R-5)**: this module's
existing high-value cross-references to **DDR-021** and **ADR-ARCH-017**
must be retained. These two citations are the architectural anchors for the
NATS KV manifest registry pattern and must survive the polish pass — this
is the only module-level regression risk in the whole feature.

Two TASK-Jxxx hits in this file (per `grep -n "TASK-J" src/jarvis/infrastructure/capabilities_registry.py`):
- Line 174: "...# pattern from TASK-J004-007).  Production code uses these directly; unit"
  — inside a private `# §` section comment.
- Line 309: "...seam contract — see TASK-J004-006."
  — inside a function docstring.

## Scope

**In scope:**
- Module-level docstring at the top of `src/jarvis/infrastructure/capabilities_registry.py`.
- Any TASK-Jxxx token anywhere in the file (per ASSUM-003 entire-file ban).

**Out of scope:**
- Class / method bodies; type annotations; signatures; any executable code.

## Acceptance Criteria

- [ ] First paragraph of the module docstring describes the module's purpose
      in ≥ 2 complete sentences (ASSUM-008).
- [ ] Module docstring references `FEAT-JARVIS-004` as origin (Group A.2).
- [ ] Module docstring cites at least one DDR identifier resolving under
      `docs/design/FEAT-JARVIS-004/decisions/` (Group A.3).
- [ ] Module docstring references the design doc at
      `docs/design/FEAT-JARVIS-004/design.md` (Group A.4).
- [ ] Each cited design-doc / DDR file exists on disk and is readable
      (Group C.3).
- [ ] Polished module docstring still cites **DDR-021**
      (Group D.5 — preservation invariant per review R-5).
- [ ] Polished module docstring still cites **ADR-ARCH-017**
      (Group D.5 — preservation invariant per review R-5).
- [ ] **Entire file** contains **no** token matching `TASK-J\d{3}-\d{3}`
      (Group C.4 / `@smoke`, ASSUM-003 — covers both line 174 and line 309).
- [ ] Module docstring line count is ≥ 20 and ≤ 250 (Group B.2,
      ASSUM-001/002).
- [ ] No executable Python statement is modified (Group C.2).

## Test Requirements

Minimal grep/seam tests only (per Context B Q3 and review R-4):

- [ ] `grep -nE "TASK-J[0-9]{3}-[0-9]{3}" src/jarvis/infrastructure/capabilities_registry.py`
      returns no matches.
- [ ] `grep -n "FEAT-JARVIS-004" src/jarvis/infrastructure/capabilities_registry.py`
      returns ≥ 1 match within the module docstring.
- [ ] `grep -n "DDR-021" src/jarvis/infrastructure/capabilities_registry.py`
      returns ≥ 1 match within the module docstring (preservation gate).
- [ ] `grep -n "ADR-ARCH-017" src/jarvis/infrastructure/capabilities_registry.py`
      returns ≥ 1 match within the module docstring (preservation gate).
- [ ] `python3 -c "import ast; m = ast.parse(open('src/jarvis/infrastructure/capabilities_registry.py').read()); d = ast.get_docstring(m); assert d and 20 <= len(d.splitlines()) <= 250"`
      exits cleanly.
- [ ] `python3 -c "import jarvis.infrastructure.capabilities_registry"` succeeds.

Full pytest, mypy, ruff, and `langgraph dev` regression deferred to
TASK-DOC-007.

## Implementation Notes

- The polished docstring is the canonical citation site for DDR-021 and
  ADR-ARCH-017. If the polish moves text around, those tokens MUST end up
  inside the docstring's text, not just inside the file.
- Replace the line-174 `# pattern from TASK-J004-007)` comment with a
  reference to the FEAT-JARVIS-004 design (no TASK-Jxxx).
- Replace the line-309 `seam contract — see TASK-J004-006` reference with
  a pointer to `docs/design/FEAT-JARVIS-004/contracts/API-internal.md` §1
  (the canonical seam contract for the NATS client wrapper).
- This is the highest-risk task in wave 1 — the preservation invariant
  on DDR-021 and ADR-ARCH-017 is the only place where a sloppy polish
  could remove load-bearing cross-references.
