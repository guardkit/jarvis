---
id: TASK-REV-FFE4
title: "Review: FEAT-JARVIS-004 _capability_registry list-vs-Protocol wiring inconsistency"
task_type: review
review_mode: decision
review_depth: standard
status: review_complete
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
review_results:
  mode: decision
  depth: standard
  findings_count: 6
  recommendations_count: 5
  decision: refactor
  recommended_option: B1
  report_path: .claude/reviews/TASK-REV-FFE4-review-report.md
  implementation_task: TASK-J004-FIX-001
  completed_at: 2026-04-30T00:00:00Z
priority: high
tags: [jarvis, phase3, feat-j004-followup, mypy, capabilities-registry, latent-bug]
complexity: 0
feature: FEAT-JARVIS-004
surfaced_by:
  - phase: step-11-regression-check
  - commit: 8848795
  - run_date: 2026-04-30
context_files:
  - src/jarvis/tools/__init__.py
  - src/jarvis/tools/capabilities.py
  - src/jarvis/infrastructure/lifecycle.py
  - src/jarvis/infrastructure/capabilities_registry.py
  - tests/test_assemble_tool_list.py
  - tests/test_capabilities.py
  - tests/test_tools_capabilities.py
  - docs/design/FEAT-JARVIS-004/contracts/API-internal.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md
  - docs/research/ideas/phase3-build-plan.md
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review FEAT-JARVIS-004 _capability_registry list-vs-Protocol wiring inconsistency

## Description

Decision-mode review of a latent FEAT-JARVIS-004 wiring bug surfaced during the Step 11
regression check on `main` (commit `8848795`). A single mypy error remains:

```
src/jarvis/tools/__init__.py:219: error: Incompatible types in assignment
(expression has type "list[CapabilityDescriptor]", variable has type
"CapabilitiesRegistry | None")  [assignment]
```

The error reflects a real cross-module wiring inconsistency, not a cosmetic annotation
mismatch — the catalogue tools call Protocol methods on what production wires up as a
plain list.

## Root-Cause Hypothesis

FEAT-JARVIS-004 (TASK-J004-012) changed the type annotation in
[`src/jarvis/tools/capabilities.py:265`](../../src/jarvis/tools/capabilities.py) from
`list[CapabilityDescriptor]` to `CapabilitiesRegistry | None` (Protocol). The catalogue
tool bodies were updated in lockstep to call the Protocol API:

- `list_available_capabilities` — line 372: `registry.snapshot()`
- `capabilities_refresh` — lines 414/425: `registry.refresh()`
- `capabilities_subscribe_updates` — line 455: `registry.subscribe_updates(...)`

However, [`assemble_tool_list`](../../src/jarvis/tools/__init__.py) at line 219 still
performs `_capabilities._capability_registry = list(capability_registry)` — assigning a
raw `list[CapabilityDescriptor]`. The lifecycle production path
([`lifecycle.py:688/706`](../../src/jarvis/infrastructure/lifecycle.py)) calls
`assemble_tool_list(config, capability_registry, ...)` with a list and never wraps it in
a Protocol-shaped registry afterwards.

The Protocol-shaped `state.capabilities_registry` (built at `lifecycle.py:601-632` via
`LiveCapabilitiesRegistry.create(...)` or `_build_stub_capabilities_registry(...)`) is
stored in `AppState` for shutdown but never wired into the
`_capabilities._capability_registry` slot.

**Inferred consequence:** in production, after `lifecycle.startup` completes, the
catalogue tools should crash with `AttributeError: 'list' object has no attribute
'snapshot'` (and `'refresh'`, `'subscribe_updates'`) the first time the supervisor
invokes them. Tests pass because they explicitly wrap with `_ListBackedRegistry`
([`tests/test_assemble_tool_list.py:344-350`](../../tests/test_assemble_tool_list.py),
[`tests/test_capabilities.py:486-490`](../../tests/test_capabilities.py),
[`tests/test_tools_capabilities.py:126`](../../tests/test_tools_capabilities.py)) —
production lacks that wrapping step.

The end-to-end Forge test (Step 14 of `phase3-build-plan.md`) and any `jarvis chat`
session would be the first triggers if this is genuinely runtime-broken.

## Review Scope (Context A)

- **Focus**: Wiring correctness, runtime behaviour, fix selection.
- **Trade-off priority**: Quality / correctness — this is on the Phase 3 close path and
  blocks confident Step 14 execution.
- **Specific concerns to surface**:
  - Whether the inferred runtime crash actually fires, or whether some wiring step
    elsewhere mitigates it.
  - Whether the Protocol-based design intent (Live KV-watch-aware re-reads, DDR-021
    Live/Stub fallback) should be preserved or reverted.
  - Test honesty — do the existing tests skip over the wiring gap, and how should the
    fix close it?

## Required Decisions

1. **Confirm runtime symptom.** Reproduce in dev (e.g. `langgraph dev` + a synthetic
   supervisor invocation calling `list_available_capabilities`). Either confirm the
   `AttributeError` fires, or identify the missing wiring step in the analysis.
2. **Choose fix approach** if confirmed broken:
   - **(A) Revert** — restore `capabilities.py:265` annotation to
     `list[CapabilityDescriptor]`; revert tool bodies to operate on the list directly.
     Side effect: `LiveCapabilitiesRegistry` becomes unused at the tool layer (still
     useful for shutdown / supervisor's prompt-block rendering). Loses live KV-watch
     re-read behaviour at the tool surface.
   - **(B) Wire the Protocol through.** Two sub-options:
     - **(B1)** Add a `capabilities_registry: CapabilitiesRegistry` kwarg to
       `assemble_tool_list` and have lifecycle pass the Protocol-shaped registry through.
     - **(B2)** Introduce a separate setter `wire_capabilities_registry(registry)` in
       `tools/capabilities.py` that lifecycle calls after `assemble_tool_list`.
     (B) preserves FEAT-JARVIS-004 design intent (DDR-021 Live/Stub fallback flowing all
     the way through to the tool surface).
3. **Test plumbing.** If (B), update `tests/test_assemble_tool_list.py:344-350`,
   `tests/test_capabilities.py:486-490`, and `tests/test_tools_capabilities.py:126` so
   the `_ListBackedRegistry` wrap happens via the new wiring path rather than direct
   module attribute assignment — keeps the tests honest about the production wiring.

## Acceptance Criteria

- [ ] Decision recorded as a DDR (or DDR amendment to FEAT-JARVIS-004): A vs. B with
      rationale; if B, B1 vs. B2.
- [ ] Implementation lands the chosen fix.
- [ ] `uv run mypy src/jarvis/` returns zero errors.
- [ ] All existing tests pass (the `_ListBackedRegistry` wrap may move from inline to
      fixture/setter, but coverage shape unchanged).
- [ ] A new test asserts the production lifecycle wiring actually puts a Protocol-shaped
      registry into the tool layer (closes the gap the existing tests skip over).
- [ ] Running `langgraph dev` + a real `list_available_capabilities` invocation completes
      without `AttributeError`.

## Out of Scope

- The 49 ruff cosmetic violations on `main` (mostly auto-fixable; separate cleanup pass).
- The GuardKit autobuild cap-refresh bug from
  [`TASK-REV-E73C`](../completed/TASK-REV-E73C-analyse-autobuild-feat-j005-946d-timeout-failure.md)
  — belongs in the `guardkit` repo, not `jarvis`.
- Any FEAT-JARVIS-005 tool surface changes — `forge_notifications` / `queue_build` are
  on a separate registry-free path and unaffected.

## Phase 3 Build Plan Alignment

This is a deferred FEAT-JARVIS-004 follow-up surfaced during Step 11 of
`docs/research/ideas/phase3-build-plan.md`. The build plan's Step 14 (end-to-end Forge
round-trip) is the real-world trigger if this defect is runtime-live; resolving it before
Step 14 reduces e2e debugging surface area.

## Next Steps

1. Run `/task-review TASK-REV-FFE4` to execute the decision-mode review.
2. Apply the chosen fix in a follow-up implementation task.
3. Re-run Step 11 to confirm zero mypy errors and continue Phase 3 close (Step 13 → 14).
