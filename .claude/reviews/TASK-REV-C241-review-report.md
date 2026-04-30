# Review Report: TASK-REV-C241

**Plan: FEAT-JARVIS-INTERNAL-001 Documentation Foundation**

## Executive Summary

Decision-mode review of the FEAT-JARVIS-INTERNAL-001 documentation-foundation
spec. The /feature-spec stage already produced a tight Gherkin specification
(21 scenarios / 40 effective rows / 7 smoke), so the question this review
must settle is **how to slice the work into autobuild-shaped tasks**, not
*what* the work is.

**Verdict**: **Option 1 — wave-based parallel polish (6 parallel tasks +
1 sequential invariant gate)**, recommended on the maintainability lens
chosen in Context A. Score: **86 / 100**. 4 findings; 5 recommendations.
3 low-confidence assumptions (ASSUM-001/002/003) flagged as DDR promotion
candidates but **not** pre-decided here per Context A Q3 — that call is
reserved for the planning task (recommended location: a single new
`DDR-INT-001` under `docs/design/FEAT-JARVIS-INTERNAL-001/decisions/`).

## Review Details

- **Mode**: Decision (Phase 5-style)
- **Depth**: Standard
- **Reviewer**: Claude Opus 4.7 (1M ctx) with /task-review skill
- **Clarification Context A**:
  - Focus: All (broad sweep)
  - Trade-off: Maintainability
  - Assumption promotion: defer to planning task
- **Inputs read**:
  - `feat-jarvis-internal-001-documentation-foundation_summary.md`
  - `feat-jarvis-internal-001-documentation-foundation.feature` (full)
  - `feat-jarvis-internal-001-documentation-foundation_assumptions.yaml` (full)
  - `docs/research/ideas/phase3-build-plan.md` (Steps 1–35)
  - `README.md` (current 131 LoC; "Status: Pre-Architecture")
  - `src/jarvis/infrastructure/nats_client.py` (header docstring)
  - Live grep for `TASK-J\d{3}-\d{3}` across all five candidate modules
    plus `lifecycle.py` (for out-of-scope confirmation)

## Findings

### F1 — TASK-Jxxx leakage is concentrated and shallow but pervasive

Live grep shows TASK-Jxxx tokens in all five candidate modules:

| Module | TASK-Jxxx hits | Notes |
|---|---|---|
| `nats_client.py` | 1 (line 3 — opening sentence) | Easy delete. |
| `fleet_registration.py` | 2 (lines 24, 143) | One opening, one inline reference. |
| `capabilities_registry.py` | 2 (lines 174, 309) | Both inside private `# §` section comments — reword to point at FEAT-JARVIS-004 instead. |
| `routing_history.py` | 3 (lines 3, 5, 460) | Module docstring + one §5 section header. |
| `forge_notifications.py` | **8** (lines 3, 7, 19, 38, 80, 183, 221, 427, 462) | The biggest cleanup target. Most are §-section headers (`§3 — ForgeNotificationsSubscriber (TASK-J005-003)`) — straightforward substitution. |

Pre-existing: `lifecycle.py`, `dispatch_semaphore.py`, etc. carry TASK-Jxxx
references but are **not in scope** — confirmed against the summary's
six-file scope list.

**Implication for task shape**: each module's polish is independent of the
others (different files, no merge conflicts), and the work per module is
small (≤ 8 substitutions plus a Purpose-paragraph audit and a DDR-citation
audit). This pushes toward parallel-per-module rather than a single
mega-task.

### F2 — README is genuinely stale, not just out-of-date

The current `README.md` (131 LoC) declares `Status: Pre-Architecture` and
suggests the next step is `/system-arch`. Reality (per the build plan
Status header at line 5): Phase 2 closed, FEAT-J004 + FEAT-J005 closed,
TASK-J004-FIX-001 closed, Step 11 regression PASSED on commit `7e29363`
with **2105 passing tests at 92% coverage** — versus the README's claim of
`341 passing`. The README also lists "(8 Agents)" with an "Architect Agent"
in a separate `architect-agent` repo, which is a v0 fleet snapshot.

This is not a "tweak" — it is a rewrite from scratch within the agreed
100–300 LoC bounds (ASSUM-004/005). The Quick Start section (lines 12–32)
is the only block likely to survive verbatim, since `uv sync` + `uv run …`
is already canonical (ASSUM-013).

**Implication for task shape**: README rewrite is independent of every
module polish (no shared files), so it can run in parallel with the five
module-polish tasks without merge contention.

### F3 — The tool-docstring invariant is the single load-bearing risk

The FEAT-J004/J005 build-plan invariant — *"Tool docstrings unchanged —
reasoning model behaviour identical between Phase 2 (stubbed) and Phase 3
(real NATS/Forge)"* — is the **only** way this feature can break Step 14.
The .feature file pins it correctly (Group C.1 / `@negative @smoke`,
scoped to `src/jarvis/tools/*.py` excluding `__init__.py` per ASSUM-012),
but **structurally** the test must run after every polish task to give the
Coach a green-light signal. Putting the invariant check inside each
parallel task wastes work; placing it after every task in a sequential
gate is correct.

**Implication for task shape**: a single sequential **Wave 2** invariant +
regression task at the end of the wave-1 fan-out.

### F4 — Three low-confidence assumptions are real DDR candidates, but not for this review

ASSUM-001 (lower bound 20 LoC), ASSUM-002 (upper bound 250 LoC), and
ASSUM-003 (TASK-Jxxx ban entirely) are all *convention calls* that survive
this feature's lifetime — exactly the shape that DDRs preserve. The summary
proposes promoting all three to a single `DDR-INT-001: Documentation Polish
Bounds and TASK-Jxxx Convention`. Per Context A Q3, this review **does
not** make that call; it surfaces the evidence for the planning task to
decide. Recommendation: the planning task's first wave-1 task should be
the DDR-INT-001 write-up (analogous to how FEAT-J004 used TASK-J004-001
to land DDR-023 + DDR-024 ahead of the implementation tasks).

## Implementation Approaches Considered

### Option 1 — Wave-based parallel polish (6 + 1) — **RECOMMENDED**

```
Wave 1 (parallel, 6 tasks):
  TASK-DOC-001  nats_client.py            docstring polish
  TASK-DOC-002  fleet_registration.py     docstring polish
  TASK-DOC-003  capabilities_registry.py  docstring polish (preserve DDR-021 / ADR-ARCH-017)
  TASK-DOC-004  routing_history.py        docstring polish
  TASK-DOC-005  forge_notifications.py    docstring polish (8 TASK-Jxxx hits)
  TASK-DOC-006  README.md                 rewrite (Phase-3-close)
Wave 2 (sequential, 1 task):
  TASK-DOC-007  Invariant + regression gate
                - tool docstrings byte-unchanged
                - mypy 0-delta on touched files
                - pytest green @ ≥ 92% line coverage
                - langgraph dev boots both graphs
                - ruff baseline unchanged
```

Plus an optional **Wave 0** task for the DDR-INT-001 write-up, deferred to
the planning step.

| Dimension | Score |
|---|---|
| Maintainability | 9/10 — one task per file = clean diff per Coach turn, scenario tags map cleanly. |
| Parallelism | 9/10 — 6-wide fan-out, no merge contention. |
| Coach burden | 8/10 — small per-task scope keeps each Coach review fast. |
| Risk | 9/10 — invariant gate guarantees behavioural protection before merge. |
| Effort | 8/10 — ~7 tasks, ≈ 3–4 worktree turns each. |
| **Total** | **86/100** |

Pros:
- Mirrors the proven FEAT-J004 / FEAT-J005 wave shape (one task per file
  in wave 1, sequential gate at the end).
- Scenario tags map 1-to-1 to tasks: each module's outline rows
  (Group A.1 / A.2 / A.3 / A.4 / B.2) tag onto exactly one wave-1 task;
  README scenarios (A.5 / A.6 / A.7 / A.8 / A.9 / B.1 / C.5 / D.4) all
  land on TASK-DOC-006; invariants (C.1 / C.2 / C.3 / C.4 / D.1 / D.2 /
  D.3 / D.5) land on TASK-DOC-007.
- Per-module context narrows the Coach's read window — capabilities_registry
  (593 LoC) and routing_history (872 LoC) are the longest files and benefit
  most from focused diff review.
- Conductor-friendly: 6 parallel worktrees in wave 1, then converge.

Cons:
- 7 tasks may feel heavy for a documentation-only feature.
  Mitigation: each task is small (≤ 30-min Coach turn budget per the
  per-task profile), so total wall-clock ≈ wave-1 (parallel) + wave-2
  (sequential) ≈ 1 wave + 1 wave ≈ 60–90 min on the bench.

### Option 2 — Sequential single-task per file (6 + 1)

Same task list as Option 1 but no parallelism. Simpler orchestration; no
Conductor needed. ~6× wall-clock cost. Score: **62/100**. No structural
benefit over Option 1 — rejected.

### Option 3 — Combined "polish all docstrings" mega-task + README + invariant (3 tasks)

```
Wave 1 (parallel):
  TASK-DOC-001  All five infrastructure module docstrings (single mega-diff)
  TASK-DOC-002  README.md rewrite
Wave 2 (sequential):
  TASK-DOC-003  Invariant + regression gate
```

Pros: minimal task count.

Cons:
- Wave-1 task #1 touches **5 files at once** — Coach review window blows
  out, error attribution becomes ambiguous, and a single failed acceptance
  criterion potentially rolls back four files of correct work.
- Defeats the per-scenario tag mapping in the .feature file — can't
  cleanly link each module's `@key-example` outline rows to a single task
  ID for the BDD-linker step.
- Maintainability score drops to **5/10** — too large per task. Rejected
  for the chosen lens.

Score: **64/100** — rejected.

## Recommendations

1. **Adopt Option 1 (wave-based parallel polish)**. 6 parallel tasks in
   wave 1 + 1 sequential invariant gate in wave 2. (R-1 — primary)
2. **Add a Wave 0 DDR-INT-001 task** if the planning step decides to
   promote ASSUM-001/002/003. The DDR write-up is independent of all
   polish work and small (≈ 200 LoC of decision prose). Deferring the
   decision to the planning task is the intent of Context A Q3. (R-2)
3. **Pin the invariant test as @smoke in the wave-2 task**, not in
   wave-1 tasks. Wave-1 tasks should still verify their *own* file's
   structural assertions (Purpose paragraph, FEAT-JARVIS origin, DDR
   citations, line bounds, no TASK-Jxxx) but not the cross-cutting
   invariants. (R-3)
4. **Use grep-based seam tests for wave-1 tasks** rather than full pytest
   re-runs per task. The acceptance criteria are all structurally testable
   (`grep`, `wc -l`, AST inspection of `__doc__`). The Coach can verify
   each in seconds. Reserve the full pytest + mypy + ruff + langgraph dev
   gate for wave-2. (R-4)
5. **Preserve DDR-021 / ADR-ARCH-017 in capabilities_registry.py** as an
   explicit acceptance criterion on TASK-DOC-003 (mapped from scenario
   "Existing DDR-021 / ADR-ARCH-017 references in capabilities_registry.py
   are preserved" in the .feature Group D). This is the only module-level
   regression risk in the whole feature. (R-5)

## Decision Matrix

| Option | Score | Effort | Risk | Recommendation |
|---|---|---|---|---|
| **1: Wave-based parallel polish (6+1)** | **86** | Low | Low | **Adopt** |
| 2: Sequential single-task per file (6+1) | 62 | Medium | Low | Reject — no benefit over 1 |
| 3: Combined mega-task (3) | 64 | Low | Medium | Reject — Coach burden, scenario tag loss |

## Wave Shape Reference (for the planning step)

```
Wave 1 (parallel, 6 tasks):
  ├─ TASK-DOC-001 nats_client.py polish
  ├─ TASK-DOC-002 fleet_registration.py polish
  ├─ TASK-DOC-003 capabilities_registry.py polish (preserve DDR-021/ADR-ARCH-017)
  ├─ TASK-DOC-004 routing_history.py polish
  ├─ TASK-DOC-005 forge_notifications.py polish
  └─ TASK-DOC-006 README.md rewrite
Wave 2 (sequential, 1 task):
  └─ TASK-DOC-007 Invariant + full regression gate
```

7 tasks total. Aggregate complexity: ≈ 18/70 (≈ 2.5/10 per task).
Estimated wall-clock: 60–90 min on the bench (parallel wave 1 ≈ 30 min,
sequential wave 2 ≈ 30 min).

## Appendix — Scenario → Task Mapping (for the BDD-linker step)

| Scenario tag | Mapped task |
|---|---|
| Group A.1/A.2/A.3/A.4 outlines × `nats_client.py` row | TASK-DOC-001 |
| Group A.1/A.2/A.3/A.4 outlines × `fleet_registration.py` row | TASK-DOC-002 |
| Group A.1/A.2/A.3/A.4 outlines × `capabilities_registry.py` row | TASK-DOC-003 |
| Group A.1/A.2/A.3/A.4 outlines × `routing_history.py` row | TASK-DOC-004 |
| Group A.1/A.2/A.3/A.4 outlines × `forge_notifications.py` row | TASK-DOC-005 |
| Group A.5–A.9 (README scenarios) | TASK-DOC-006 |
| Group B.1 (README line bounds) | TASK-DOC-006 |
| Group B.2 (module docstring line bounds) | each TASK-DOC-001..005 (own row) |
| Group C.1 (`@smoke` tool-docstring invariant) | TASK-DOC-007 |
| Group C.2 (no executable code modified) | TASK-DOC-007 |
| Group C.3 (cited design-doc paths resolve) | each TASK-DOC-001..005 (own row) |
| Group C.4 (`@smoke` no TASK-Jxxx in polished) | each TASK-DOC-001..005 (own row) |
| Group C.5 (README no Pre-Architecture) | TASK-DOC-006 |
| Group D.1 (`@smoke` modules importable + graphs compile) | TASK-DOC-007 |
| Group D.2 (`@smoke` pytest + coverage) | TASK-DOC-007 |
| Group D.3 (mypy delta) | TASK-DOC-007 |
| Group D.4 (README relative paths) | TASK-DOC-006 |
| Group D.5 (DDR-021 / ADR-ARCH-017 preserved in capabilities_registry) | TASK-DOC-003 |

This mapping is exactly the shape the BDD-linker subagent expects (Step 11
of the /feature-plan flow). Confidence per row: ≥ 0.8 — every scenario
either has an `Examples` row that names the file unambiguously, or scopes
itself to "the file `README.md`" / "the polished modules", so the matching
is mechanical.
