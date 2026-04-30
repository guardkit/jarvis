---
id: TASK-DOC-004
title: routing_history.py docstring polish
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

# TASK-DOC-004 — routing_history.py docstring polish

## Description

Polish the module docstring of `src/jarvis/infrastructure/routing_history.py`
to the FEAT-JARVIS-INTERNAL-001 consistent shape: Purpose paragraph (≥ 2
sentences), FEAT-JARVIS origin attribution, design-doc link, ≥ 1 DDR
citation, no `TASK-J\d{3}-\d{3}` references, line count between 20 and 250.

This is the largest candidate (872 LoC), so the upper bound on docstring
length (ASSUM-002, 250 lines) is most likely to pinch here — the existing
ADR-FLEET-001 schema discussion at the top of the file is dense.

Three TASK-Jxxx hits in this file (per `grep -n "TASK-J" src/jarvis/infrastructure/routing_history.py`):
- Line 3: "TASK-J004-004 landed the declarative-only Pydantic schema..."
  — module docstring narrative; reword to point at FEAT-JARVIS-004 instead.
- Line 5: "TASK-J004-010 appends the persistence-side :class:`RoutingHistoryWriter`..."
  — module docstring narrative; reword.
- Line 460: "# §5 — RoutingHistoryWriter (TASK-J004-010 — DDR-018 + DDR-019 + DDR-023)"
  — section header comment; rewrite as
  "# §5 — RoutingHistoryWriter (DDR-018 + DDR-019 + DDR-023)".

## Scope

**In scope:**
- Module-level docstring at the top of `src/jarvis/infrastructure/routing_history.py`.
- Any TASK-Jxxx token anywhere in the file (per ASSUM-003 entire-file ban).

**Out of scope:**
- Class / method bodies; type annotations; signatures; any executable code.

## Acceptance Criteria

- [ ] First paragraph of the module docstring describes the module's purpose
      in ≥ 2 complete sentences (ASSUM-008).
- [ ] Module docstring references `FEAT-JARVIS-004` as origin (Group A.2).
- [ ] Module docstring cites at least one DDR identifier resolving under
      `docs/design/FEAT-JARVIS-004/decisions/` (Group A.3) — at minimum
      preserve **DDR-018** (routing-history schema authoritative) and
      **DDR-019** (Graphiti fire-and-forget writes).
- [ ] Module docstring references the design doc at
      `docs/design/FEAT-JARVIS-004/design.md` (Group A.4).
- [ ] Each cited design-doc / DDR file exists on disk and is readable
      (Group C.3).
- [ ] **Entire file** contains **no** token matching `TASK-J\d{3}-\d{3}`
      (Group C.4 / `@smoke`, ASSUM-003 — covers lines 3, 5, and 460).
- [ ] Module docstring line count is ≥ 20 and ≤ 250 (Group B.2,
      ASSUM-001/002).
- [ ] No executable Python statement is modified (Group C.2).

## Test Requirements

Minimal grep/seam tests only (per Context B Q3 and review R-4):

- [ ] `grep -nE "TASK-J[0-9]{3}-[0-9]{3}" src/jarvis/infrastructure/routing_history.py`
      returns no matches.
- [ ] `grep -n "FEAT-JARVIS-004" src/jarvis/infrastructure/routing_history.py`
      returns ≥ 1 match within the module docstring.
- [ ] `grep -nE "DDR-0(16|17|18|19|20|21|22|23|24)" src/jarvis/infrastructure/routing_history.py`
      returns ≥ 1 match within the module docstring.
- [ ] `python3 -c "import ast; m = ast.parse(open('src/jarvis/infrastructure/routing_history.py').read()); d = ast.get_docstring(m); assert d and 20 <= len(d.splitlines()) <= 250, f'docstring length {len(d.splitlines()) if d else 0}'"`
      exits cleanly.
- [ ] `python3 -c "import jarvis.infrastructure.routing_history"` succeeds.

Full pytest, mypy, ruff, and `langgraph dev` regression deferred to
TASK-DOC-007.

## Implementation Notes

- The ADR-FLEET-001 schema discussion is the heart of this module's
  docstring — keep it. Compress narrative TASK-Jxxx provenance ("TASK-J004-004
  landed X; TASK-J004-010 appends Y") into a single FEAT-JARVIS-004 origin
  attribution.
- The line-460 `§5` section header is in the `__all__`-region of the file
  body, not in the module docstring. Strip the TASK-Jxxx token but keep
  the DDR citations.
- If the polished docstring exceeds 250 lines, prefer pruning historical
  narrative over removing DDR citations.
