---
id: TASK-DOC-002
title: fleet_registration.py docstring polish
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
status: backlog
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-DOC-002 — fleet_registration.py docstring polish

## Description

Polish the module docstring of `src/jarvis/infrastructure/fleet_registration.py`
to the FEAT-JARVIS-INTERNAL-001 consistent shape: Purpose paragraph (≥ 2
sentences), FEAT-JARVIS origin attribution, design-doc link, ≥ 1 DDR
citation, no `TASK-J\d{3}-\d{3}` references, line count between 20 and 250.

Two TASK-Jxxx hits in this file (per `grep -n "TASK-J" src/jarvis/infrastructure/fleet_registration.py`):
- Line 24: "...ahead of TASK-J004-006 landing the local NATSClient wrapper."
  — module docstring narrative; reword to point at FEAT-JARVIS-004 instead.
- Line 143: "The local ``jarvis.NATSClient`` wrapper (planned in TASK-J004-006)..."
  — inside a function docstring (out of scope per the module-docstring-only
  charter, but **must still be removed** because ASSUM-003 says TASK-Jxxx is
  banned *entirely* from polished module files. Treat this hit the same way
  as the module docstring hits.).

## Scope

**In scope:**
- Module-level docstring at the top of `src/jarvis/infrastructure/fleet_registration.py`.
- Any TASK-Jxxx token anywhere in the file (per ASSUM-003 entire-file ban
  on the five candidate modules).

**Out of scope:**
- Any executable code other than docstring text.
- Method bodies, type annotations, signatures.

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
- [ ] **Entire file** contains **no** token matching `TASK-J\d{3}-\d{3}`
      (Group C.4 / `@smoke`, ASSUM-003 — this covers both the module
      docstring on line 24 and the inline reference on line 143).
- [ ] Module docstring line count is ≥ 20 and ≤ 250 (Group B.2,
      ASSUM-001/002).
- [ ] No executable Python statement is modified (Group C.2).

## Test Requirements

Minimal grep/seam tests only (per Context B Q3 and review R-4):

- [ ] `grep -nE "TASK-J[0-9]{3}-[0-9]{3}" src/jarvis/infrastructure/fleet_registration.py`
      returns no matches.
- [ ] `grep -n "FEAT-JARVIS-004" src/jarvis/infrastructure/fleet_registration.py`
      returns ≥ 1 match within the module docstring (top-of-file).
- [ ] `grep -nE "DDR-0(16|17|18|19|20|21|22|23|24)" src/jarvis/infrastructure/fleet_registration.py`
      returns ≥ 1 match within the module docstring.
- [ ] `python3 -c "import ast; m = ast.parse(open('src/jarvis/infrastructure/fleet_registration.py').read()); d = ast.get_docstring(m); assert d and 20 <= len(d.splitlines()) <= 250"`
      exits cleanly.
- [ ] `python3 -c "import jarvis.infrastructure.fleet_registration"` succeeds.

Full pytest, mypy, ruff, and `langgraph dev` regression deferred to
TASK-DOC-007.

## Implementation Notes

- The line-143 inline reference inside a function docstring is the only
  non-module-docstring hit; reword as "the local ``jarvis.NATSClient``
  wrapper (FEAT-JARVIS-004)".
- Preserve the substance of the current module docstring (heartbeat loop,
  clean deregister, manifest contents) — this is a polish-not-rewrite.
- Reference DDR-016/017/018/019/020 as appropriate (the dispatch +
  trace-schema DDRs landed under FEAT-JARVIS-004).
