# Feature Spec Summary: FEAT-JARVIS-INTERNAL-001 Documentation Foundation

**Stack**: python
**Generated**: 2026-04-30T11:45:00Z
**Scenarios**: 21 definitions / 40 effective rows (5 outlines expand into 25 module-iteration rows + 4 README-bound rows + 11 single scenarios)
**Smoke**: 7 · **Regression**: 0
**Assumptions**: 13 total (5 high / 5 medium / 3 low)
**Review required**: Yes (3 low-confidence assumptions — ASSUM-001, ASSUM-002, ASSUM-003)

## Scope

Polish the five FEAT-J004/J005 infrastructure module docstrings under
`src/jarvis/infrastructure/` (`nats_client.py`, `fleet_registration.py`,
`capabilities_registry.py`, `routing_history.py`, `forge_notifications.py`) to a
consistent shape — Purpose paragraph (≥ 2 sentences), FEAT-JARVIS-XXX origin,
design-doc link, ≥ 1 DDR citation, no internal TASK-Jxxx leakage — and rewrite
the existing repo-root `README.md` (currently 131 lines and stale, declaring
"Status: Pre-Architecture") to reflect Phase-3-close state with H1 Jarvis project
name, Status section referencing "Phase 3" + the end-to-end Forge close criterion,
Quick Start with `uv sync` + `python -m langgraph dev`, Architecture link to
`docs/architecture/ARCHITECTURE.md`, and Design Decisions section cataloguing the
ADR directory plus the FEAT-JARVIS-004 and FEAT-JARVIS-005 DDR directories.

Reasoning-model-facing tool docstrings under `src/jarvis/tools/` are EXPLICITLY
OUT OF SCOPE per the FEAT-JARVIS-004/-005 build-plan invariant: *"Tool docstrings
unchanged — reasoning model behaviour identical between Phase 2 (stubbed) and
Phase 3 (real NATS/Forge)"*.

This feature is the payload for **Step 14 of `docs/research/ideas/phase3-build-plan.md`**
— the end-to-end Forge round-trip that closes Phase 3.

## Scenario Counts by Category

| Category | Scenario definitions | Effective rows |
|----------|---------------------|----------------|
| Key examples (`@key-example`) | 9 | 25 (4 outlines × 5 modules + 5 single) |
| Boundary conditions (`@boundary`) | 2 | 5 (1 outline × 4 + 1 single) |
| Negative cases (`@negative`) | 5 | 5 |
| Edge cases (`@edge-case`) | 5 | 5 |
| **Smoke** (`@smoke`) | **7** | — |
| **Total** | **21** | **40** |

## Deferred Items

None — Phase 4 (security/concurrency/integration edge-case expansion) was
**deliberately skipped**. This is a documentation-only feature with no auth
surfaces, no concurrent code paths, and no downstream service boundaries; the
standard Phase-4 expansion targets do not apply.

## Open Assumptions (low confidence — require coach + human review)

- **ASSUM-001** — Module docstring lower bound = 20 lines.
  *Basis:* Inferred — `nats_client.py` is the thinnest candidate and could
  legitimately compress to 20 after polish; below 20 reads as a stub.
- **ASSUM-002** — Module docstring upper bound = 250 lines.
  *Basis:* Inferred — caps `routing_history.py`-style ADR-FLEET-001 schema
  discussion while leaving headroom.
- **ASSUM-003** — TASK-Jxxx references banned **entirely** from polished docstrings
  (overridden from initial "trailing-section allowance" proposal).
  *Basis:* Convention call — TASK-Jxxx is GuardKit autobuild bookkeeping, not
  reader-facing prose; FEAT-JARVIS-XXX origin attribution provides equivalent
  traceability without the bookkeeping leak.

## Out of Scope

- Reasoning-model-facing tool docstrings under `src/jarvis/tools/*.py` (FEAT-J004/J005
  invariant: tool docstrings byte-unchanged from Phase 2). Concretely:
  `general.py`, `capabilities.py`, `dispatch.py` `@tool`-decorated functions.
- Any Python source code changes beyond docstrings (no refactors, no type
  annotation changes, no behavioural modifications).
- Updates to `CLAUDE.md` / `.claude/CLAUDE.md` (those are AI-agent-facing and
  on a separate convention).
- Files outside the five infrastructure module candidates and `README.md`.
- Pre-existing FEAT-J004 mypy issue tracked under [`TASK-REV-FFE4`](../../tasks/backlog/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md)
  (resolved on its own track; this feature must not add to the mypy error count
  but is decoupled from FFE4's resolution timing).
- The 49 ruff cosmetic violations on `main` (separate cleanup pass).

## Phase 3 Build Plan Alignment

This is the FEAT-JARVIS-INTERNAL-001 candidate selected at **Step 13 of
`phase3-build-plan.md`** for the Step 14 end-to-end Forge round-trip. The
"broader foundation, lower behavioural risk" scope (referred to in conversation
as **option a-1.5**) was chosen over:

- **a-1** (smaller, infrastructure modules only — no README) — the README is
  genuinely missing/stale and is a do-once foundation.
- **a-2** (broader, includes the 10 reasoning-model tool docstrings) —
  rejected on demo-stability grounds: tool docstrings ARE the supervisor's
  reasoning input and have been routing-stable since Phase 2; touching them
  during the Step-14 transport validator introduces a behavioural confound.

## Smoke Set (7 scenarios — Coach-blocking)

The `@smoke` set defines the minimum the coach must verify on every autobuild
turn:

1. Each infrastructure module has a Purpose paragraph (Group A.1)
2. Each infrastructure module references its FEAT-JARVIS origin (Group A.2)
3. The repo README has an H1 with the project name (Group A.5)
4. The repo README declares the current Phase-3-close status (Group A.6)
5. Reasoning-model-facing tool docstrings remain byte-unchanged (Group C.1)
6. Polished docstrings contain no TASK-Jxxx references (Group C.4)
7. All polished modules remain importable and graphs still compile (Group D.1)
8. The full pytest suite remains green and coverage does not regress (Group D.2)

## Integration with /feature-plan

This summary can be passed to `/feature-plan` as a context file:

```bash
/feature-plan "FEAT-JARVIS-INTERNAL-001 Documentation Foundation" \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_summary.md \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation.feature \
  --context features/feat-jarvis-internal-001-documentation-foundation/feat-jarvis-internal-001-documentation-foundation_assumptions.yaml \
  --context docs/research/ideas/phase3-build-plan.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context src/jarvis/infrastructure/nats_client.py \
  --context src/jarvis/infrastructure/fleet_registration.py \
  --context src/jarvis/infrastructure/capabilities_registry.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context src/jarvis/infrastructure/forge_notifications.py \
  --context README.md
```

## Pre-flight Notes for /feature-plan

- **ASSUM-001/002/003 promotion candidate**: the three low-confidence assumptions
  are the right size to promote to a single DDR — *DDR-INT-001: Documentation
  Polish Bounds and TASK-Jxxx Convention*. Consider this in the planning task
  breakdown.
- **Coach-friendly verification**: every assertion in the .feature is
  structurally testable (regex against file contents, `wc -l` against files,
  AST inspection of module docstrings). No subjective "is this README good"
  judgements required.
- **Single-coach-pass shape**: the feature is small enough for a 1–2 wave
  breakdown — likely one wave of 5 module-polish tasks running in parallel,
  plus one wave for the README rewrite + a final invariant-check task.
