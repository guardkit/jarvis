---
id: TASK-J004-FIX-001
title: Thread CapabilitiesRegistry Protocol through assemble_tool_list (B1)
task_type: bugfix
status: completed
created: 2026-04-30T00:00:00Z
updated: 2026-04-30T00:00:00Z
completed: 2026-04-30T00:00:00Z
completed_location: tasks/completed/TASK-J004-FIX-001/
priority: high
complexity: 3
wave: 1
implementation_mode: task-work
estimated_minutes: 60
parent_review: TASK-REV-FFE4
feature_id: FEAT-JARVIS-004
tags: [jarvis, phase3, feat-j004-followup, mypy, capabilities-registry, ddr-021, bugfix]
context_files:
  - src/jarvis/tools/__init__.py
  - src/jarvis/tools/capabilities.py
  - src/jarvis/infrastructure/lifecycle.py
  - src/jarvis/infrastructure/capabilities_registry.py
  - src/jarvis/agents/supervisor.py
  - tests/test_assemble_tool_list.py
  - tests/test_capabilities.py
  - tests/test_tools_capabilities.py
  - tests/test_lifecycle_feat_j004_wiring.py
  - tests/test_lifecycle_capabilities_wiring.py
  - tests/test_supervisor_lifecycle_wiring.py
  - .claude/reviews/TASK-REV-FFE4-review-report.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md
  - docs/design/FEAT-JARVIS-004/decisions/DDR-021-amendment-capabilities-registry-tool-wiring.md
test_results:
  status: passed
  coverage: null
  last_run: 2026-04-30T00:00:00Z
  pytest_summary: "2105 passed, 1 skipped"
  mypy_summary: "Success: no issues found in 45 source files"
acceptance_criteria_status:
  AC-001: passed  # capabilities_registry kwarg added to assemble_tool_list
  AC-002: passed  # catalogue slot writes the Protocol object directly
  AC-003: passed  # both lifecycle.assemble_tool_list calls pass the kwarg
  AC-004: passed  # ambient factory + build_supervisor + lifecycle plumbed
  AC-005: passed  # mypy clean
  AC-006: passed  # test_assemble_tool_list.py migrated to kwarg
  AC-007: passed  # bound_*/empty_/configured_ fixtures unchanged, all green
  AC-008: passed  # tests/test_lifecycle_capabilities_wiring.py created (2 tests, both branches)
  AC-009: passed  # full pytest green
  AC-010: passed  # DDR-021 amendment created + back-link added
  AC-011: deferred-to-manual  # langgraph dev smoke (requires live OPENAI_API_KEY)
  AC-012: passed  # ruff format clean on all modified files
---

# Task: Thread CapabilitiesRegistry Protocol through assemble_tool_list (B1 fix)

**Feature:** FEAT-JARVIS-004
**Wave:** 1 | **Mode:** task-work | **Complexity:** 3/10
**Parent review:** [TASK-REV-FFE4](../../backlog/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md) ([report](../../../.claude/reviews/TASK-REV-FFE4-review-report.md))

## Description

Implements the **B1** decision recorded in TASK-REV-FFE4: thread the `CapabilitiesRegistry` Protocol object — which `lifecycle.build_app_state` already constructs (`LiveCapabilitiesRegistry.create(...)` or `_build_stub_capabilities_registry(...)`) — through `assemble_tool_list` (and the ambient-tool factory closure inside `build_supervisor`) so the catalogue tools at the `_capabilities._capability_registry` slot actually receive a Protocol-shaped object instead of a `list[CapabilityDescriptor]`.

The review report (§6 sequence diagram) confirmed the runtime symptom: every catalogue-tool invocation in production currently triggers an `AttributeError: 'list' object has no attribute 'snapshot'/'refresh'/'subscribe_updates'` that gets caught by `except Exception` and converted to either `ERROR: registry_unavailable` or, worse, `DEGRADED: transport_unavailable — NATS connection failed` — operationally indistinguishable from a real NATS outage. Tests pass because all three test fixtures explicitly post-wrap the slot with a `_ListBackedRegistry`; production has no such wrap step.

The fix preserves the FEAT-JARVIS-004 design intent (DDR-021 §3 Live/Stub fallback at the tool surface) and keeps the `assemble_tool_list` "ONE place that knows how to wire tool-level state" invariant by extending its kwarg list rather than introducing a separate setter.

## Background — what NOT to change

- `_dispatch._capability_registry` ([dispatch.py:144](../../../src/jarvis/tools/dispatch.py#L144)) **stays a `list[CapabilityDescriptor]`**. The dispatch tool iterates the list to map `tool_name → agent_id` — it does not need (and cannot use) the Protocol surface.
- `state.capability_registry` (the `list` field on `AppState` at [lifecycle.py:323](../../../src/jarvis/infrastructure/lifecycle.py#L323)) **stays a `list[CapabilityDescriptor]`**. It backs the supervisor prompt block (`_render_available_capabilities`) which is rendered once at build time.
- `_render_available_capabilities` and the `available_capabilities=...` kwarg of `build_supervisor` are unaffected.

The fix touches only the **catalogue-tool slot** ([capabilities.py:265](../../../src/jarvis/tools/capabilities.py#L265)) and the wiring path that fills it.

## Acceptance Criteria

### Production code

- [ ] **AC-001 — `assemble_tool_list` accepts a keyword-only `capabilities_registry`.**
  In [src/jarvis/tools/__init__.py](../../../src/jarvis/tools/__init__.py), add `capabilities_registry: CapabilitiesRegistry | None = None` as a keyword-only parameter on `assemble_tool_list` (declare the type in the existing `TYPE_CHECKING` block by importing from `jarvis.infrastructure.capabilities_registry`). The docstring's "Side effects §2" updates accordingly: "Snapshots the supplied `capabilities_registry` (Protocol-shaped) into `jarvis.tools.capabilities._capability_registry` so the catalogue tools speak the Protocol surface (DDR-021 Live/Stub fallback) — when `None`, the slot is set to `None` and tools surface `ERROR: registry_unavailable` per ADR-ARCH-021."

- [ ] **AC-002 — `assemble_tool_list` writes the Protocol into the capabilities slot.**
  At [tools/__init__.py:219](../../../src/jarvis/tools/__init__.py#L219), change
  `_capabilities._capability_registry = list(capability_registry)`
  to
  `_capabilities._capability_registry = capabilities_registry`.
  Line 220 (`_dispatch._capability_registry = list(capability_registry)`) is **unchanged**.

- [ ] **AC-003 — `lifecycle.build_app_state` passes the Protocol through both `assemble_tool_list` calls.**
  At [lifecycle.py:688-696](../../../src/jarvis/infrastructure/lifecycle.py#L688-L696) (attended) and [lifecycle.py:706-714](../../../src/jarvis/infrastructure/lifecycle.py#L706-L714) (ambient), add `capabilities_registry=capabilities_registry` to the kwargs (the local variable is already in scope from the construction at lines 601-632).

- [ ] **AC-004 — Ambient-factory closure threads the Protocol through.**
  In [src/jarvis/agents/supervisor.py](../../../src/jarvis/agents/supervisor.py):
  - Add `capabilities_registry: CapabilitiesRegistry | None` parameter to `_default_ambient_tool_factory` ([line 96](../../../src/jarvis/agents/supervisor.py#L96)). Plumb it through to the inner `_factory()` closure's `assemble_tool_list` call ([line 139](../../../src/jarvis/agents/supervisor.py#L139)) as `capabilities_registry=capabilities_registry`.
  - Add `capabilities_registry: CapabilitiesRegistry | None = None` keyword-only kwarg to `build_supervisor` ([line 148](../../../src/jarvis/agents/supervisor.py#L148)). Thread into `_default_ambient_tool_factory(...)` at [line 275](../../../src/jarvis/agents/supervisor.py#L275).
  - At [lifecycle.py:726-732](../../../src/jarvis/infrastructure/lifecycle.py#L726-L732), pass `capabilities_registry=capabilities_registry` to `build_supervisor(...)`.

  This closes review Finding F4 — without it, an ambient activation would re-overwrite the slot with a raw list and silently re-introduce the bug for the rest of the session.

- [ ] **AC-005 — `uv run mypy src/jarvis/` returns zero errors.**
  Specifically, the existing error at `tools/__init__.py:219` is gone, and no new errors are introduced anywhere.

### Test changes

- [ ] **AC-006 — `tests/test_assemble_tool_list.py` migrates to the kwarg.**
  At [tests/test_assemble_tool_list.py:344-351](../../../tests/test_assemble_tool_list.py#L344-L351), replace the post-hoc module-attribute write with `assemble_tool_list(test_config, [descriptor_alpha], capabilities_registry=_ListBackedRegistry([descriptor_alpha]))`. Delete the comment at lines 319-324 acknowledging the missing TASK-J004-013 upgrade — the upgrade has now landed.

- [ ] **AC-007 — `tests/test_capabilities.py` and `tests/test_tools_capabilities.py` keep their existing fixtures.**
  The `bound_registry` / `empty_registry` / `configured_registry` / `bound_canonical_registry` fixtures may keep direct slot-write semantics (good test isolation). They continue to satisfy the new annotation because `_ListBackedRegistry` already conforms to the Protocol. **No changes required** — but verify all existing tests in these files still pass.

- [ ] **AC-008 — New lifecycle integration test asserts Protocol reaches the slot.**
  Create `tests/test_lifecycle_capabilities_wiring.py` (or add to `tests/test_lifecycle_feat_j004_wiring.py`) with at minimum:

  ```python
  @pytest.mark.asyncio
  async def test_build_app_state_wires_protocol_into_tool_slot_nats_down(
      stub_registry_config, monkeypatch
  ):
      """NATS soft-fail path — _capability_registry slot holds a Protocol, not a list."""
      from jarvis.infrastructure.capabilities_registry import (
          CapabilitiesRegistry,
          StubCapabilitiesRegistry,
      )
      from jarvis.infrastructure.lifecycle import build_app_state
      import jarvis.tools.capabilities as capabilities_module

      with (
          patch("jarvis.infrastructure.lifecycle._connect_nats", new=AsyncMock(return_value=None)),
          patch("jarvis.infrastructure.lifecycle._connect_graphiti", new=AsyncMock(return_value=None)),
          patch("jarvis.agents.supervisor.init_chat_model", return_value=fake_llm),
          patch("sys.stderr", new=io.StringIO()),
      ):
          state = await build_app_state(stub_registry_config)

      assert capabilities_module._capability_registry is not None
      assert isinstance(capabilities_module._capability_registry, CapabilitiesRegistry)
      # Production wiring should match what AppState carries.
      assert capabilities_module._capability_registry is state.capabilities_registry

      # Invoke the tool — must NOT return ERROR / DEGRADED.
      from jarvis.tools import list_available_capabilities
      result = list_available_capabilities.invoke({})
      assert not result.startswith("ERROR:"), result
      assert not result.startswith("DEGRADED:"), result
      # Stub fallback returns the 4-entry YAML catalogue.
      payload = json.loads(result)
      assert isinstance(payload, list)
      assert len(payload) == 4
  ```

  Add a symmetric `test_build_app_state_wires_live_protocol_into_tool_slot_nats_up` using the existing `fake_live_registry` pattern from `tests/test_lifecycle_feat_j004_wiring.py:218-258` so both NATS-up and NATS-down branches are covered.

- [ ] **AC-009 — All existing tests pass.** `uv run pytest tests/` returns green; in particular `test_supervisor_lifecycle_wiring.py:484-523` still passes (unchanged — it inspects tool *names*).

### DDR

- [ ] **AC-010 — DDR-021 amendment recorded.**
  Create `docs/design/FEAT-JARVIS-004/decisions/DDR-021-amendment-capabilities-registry-tool-wiring.md` (linked from DDR-021 via an "Amendments" section) capturing:
  1. The defect (Protocol-typed slot was being written as a list — review report §6).
  2. The chosen fix (B1 — kwarg through `assemble_tool_list`, plumbed through ambient factory).
  3. Why not B2 (separate setter — review report §10 and §12).
  4. Pointer to `.claude/reviews/TASK-REV-FFE4-review-report.md` for full diagrams + analysis.

### Manual verification

- [ ] **AC-011 — Live `langgraph dev` smoke confirms no degraded-mode return.**
  ```bash
  OPENAI_API_KEY=sk-... python -m langgraph dev
  # In another shell:
  curl -X POST http://localhost:2024/threads/$(uuidgen)/runs/wait \
       -H 'content-type: application/json' \
       -d '{"assistant_id":"jarvis","input":{"messages":[{"role":"user","content":"What agents are available?"}]}}'
  ```
  The supervisor's `list_available_capabilities` tool result must be a valid JSON array (4 entries from the stub YAML when NATS is down, or live fleet when NATS is up). It must **not** start with `ERROR:` or `DEGRADED:`.

- [ ] **AC-012 — Lint/format clean.** All modified files pass project-configured lint/format checks with zero errors (`uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`).

## Out of Scope

- The 49 ruff cosmetic violations on `main` (separate cleanup pass).
- Renaming or restructuring the `_capability_registry` module slots (single underscore is fine; the slot name is shared with `dispatch.py` for grep-ability — keep it).
- Changing `assemble_tool_list`'s positional signature (`capability_registry` as a `list` stays positional). The fix is *additive* via a new keyword-only kwarg.
- Any FEAT-JARVIS-005 surface or the GuardKit autobuild bug from TASK-REV-E73C.

## Phase 3 Build Plan Alignment

This unblocks Step 14 (end-to-end Forge round-trip) of `docs/research/ideas/phase3-build-plan.md`. Step 14 is the first real-world trigger of the latent defect; resolving it before Step 14 reduces e2e debugging surface area.

## Implementation Order (recommended)

1. AC-001 + AC-002 (kwarg + slot write) — `tools/__init__.py` change.
2. AC-003 (lifecycle.py wiring) — both `assemble_tool_list` call sites.
3. AC-004 (ambient factory + `build_supervisor` kwarg) — closes F4.
4. AC-005 (`mypy`) — should be green now.
5. AC-006 (test fixture migration in `test_assemble_tool_list.py`).
6. AC-008 (new lifecycle integration test).
7. AC-009 (full pytest run) — fix any unexpected fallout.
8. AC-010 (DDR amendment).
9. AC-011 (live smoke).
10. AC-012 (lint/format).

## Notes / Risks

- The `capabilities_registry` kwarg defaults to `None` so any external caller of `assemble_tool_list` that does not pass it will see the catalogue tools surface `ERROR: registry_unavailable` (matching the pre-wired sentinel semantics at [capabilities.py:373](../../../src/jarvis/tools/capabilities.py#L373)). This is intentional — silently falling back to a list-shaped slot is what got us into this mess.
- `_render_available_capabilities` (supervisor prompt block) still consumes the **list** form (`available_capabilities` kwarg of `build_supervisor`). The Protocol's `snapshot()` is *not* called at prompt-render time, only at tool-call time. So adding the new kwarg does **not** create a circular dependency between prompt rendering and Protocol availability.
- The Protocol's `subscribe_updates` is idempotent; the new lifecycle wiring may want to call `await capabilities_registry.subscribe_updates(_noop_subscribe_callback)` once at startup so the KV-watch invalidation reaches the cache before the model ever asks. **Out of scope for this task** — the existing `capabilities_subscribe_updates` tool path remains the operator's opt-in trigger; deferring proactive subscription is consistent with the FEAT-JARVIS-004 design.

## Implementation Summary

Closed the latent FEAT-JARVIS-004 bug identified in TASK-REV-FFE4 §6: `assemble_tool_list` was writing `jarvis.tools.capabilities._capability_registry` as a `list[CapabilityDescriptor]` while the catalogue tool bodies and the slot's declared type both spoke the `CapabilitiesRegistry` Protocol surface. Every catalogue-tool invocation in production therefore triggered an `AttributeError: 'list' object has no attribute 'snapshot'/'refresh'/'subscribe_updates'` that the tool body's `except Exception` branch caught and converted to `ERROR: registry_unavailable` / `DEGRADED: transport_unavailable — NATS connection failed` — operationally indistinguishable from a real NATS outage. The defect was masked in tests by post-hoc `_ListBackedRegistry` wrappers in every test fixture; production wiring had no such wrap step.

Applied the **B1** decision (kwarg through `assemble_tool_list`) recorded in TASK-REV-FFE4 §10/§12 over the alternative B2 (separate setter) because B1 preserves the "ONE place that knows how to wire tool-level state" invariant and keeps attended/ambient assembly symmetric. Closed Finding F4 by also threading the Protocol through `_default_ambient_tool_factory` and `build_supervisor` so an ambient activation cannot re-overwrite the slot with `None`.

### Approach

Additive kwarg-threading across four production files plus the matching test/DDR updates:

1. `src/jarvis/tools/__init__.py` — added `capabilities_registry: CapabilitiesRegistry | None = None` keyword-only parameter to `assemble_tool_list`; changed the catalogue-slot write from `_capabilities._capability_registry = list(capability_registry)` to `_capabilities._capability_registry = capabilities_registry`. The dispatch slot at line 220 (now 240 post-rewrite) is intentionally unchanged — dispatch tool iterates the list and does not need the Protocol surface.
2. `src/jarvis/infrastructure/lifecycle.py` — both `assemble_tool_list` calls (attended + ambient) and the `build_supervisor(...)` call now pass `capabilities_registry=capabilities_registry`. The local variable was already in scope from the `LiveCapabilitiesRegistry.create(...)` / `_build_stub_capabilities_registry(...)` construction earlier in the function.
3. `src/jarvis/agents/supervisor.py` — added matching `capabilities_registry: CapabilitiesRegistry | None` parameter to `_default_ambient_tool_factory` and plumbed into the inner `_factory()` closure's `assemble_tool_list` call. Added matching keyword-only kwarg to `build_supervisor`. Closes Finding F4 — without this, an ambient activation re-overwrites the slot with `None`.
4. `tests/test_assemble_tool_list.py` — migrated `test_list_available_capabilities_observes_snapshot` from post-hoc module-attribute write to the new kwarg. Rewrote three AC-004 tests that asserted the old list-based slot contract to assert the new Protocol-slot contract (capabilities slot stores the Protocol object directly; dispatch slot stays a list).
5. `tests/test_lifecycle_capabilities_wiring.py` — new file with two integration tests covering NATS-down (Stub fallback) and NATS-up (Live registry) branches. Each asserts the Protocol shape reaches the slot AND that `list_available_capabilities` returns neither `ERROR:` nor `DEGRADED:` on the happy path.
6. `docs/design/FEAT-JARVIS-004/decisions/DDR-021-amendment-capabilities-registry-tool-wiring.md` — new amendment recording defect, B1 fix, why-not-B2, pointer to the TASK-REV-FFE4 review report. Back-link added from DDR-021 §Amendments.

### Result

- 11/12 acceptance criteria PASSED in this run; AC-011 (live `langgraph dev` smoke with `OPENAI_API_KEY`) deferred to manual operator verification — the running infrastructure cannot be exercised from a tool-only session.
- `uv run mypy src/jarvis/`: `Success: no issues found in 45 source files` — the existing error at `tools/__init__.py:219` is gone (AC-005).
- `uv run pytest tests/`: `2105 passed, 1 skipped` — full suite green including the two new integration tests (AC-009).
- `uv run ruff format --check` on all modified files: clean (AC-012).
- The `_dispatch._capability_registry` slot, the `state.capability_registry` `AppState` field, the `_render_available_capabilities` prompt block, and the `available_capabilities=...` kwarg of `build_supervisor` are all unchanged — the fix is surgically scoped to the catalogue-tool slot per the task's "Background — what NOT to change" section.

### Lessons

- A type annotation on a module-level swap-point (`_capability_registry: CapabilitiesRegistry | None`) is only as load-bearing as the wiring path that fills it. Mypy was already reporting the `list[CapabilityDescriptor]` → `CapabilitiesRegistry | None` mismatch at `tools/__init__.py:219` before the fix landed; the upstream lesson is the cosmetic-violations gate that allowed that error to merge into `main`.
- Test fixtures that hide the production wiring path are a smell. All three test files (`test_capabilities.py`, `test_tools_capabilities.py`, `test_assemble_tool_list.py`) wrapped the slot with `_ListBackedRegistry` post-assemble, which made the catalogue tools work in tests but masked the production failure mode entirely. The new `test_lifecycle_capabilities_wiring.py` exercises the *full* `build_app_state` path and asserts on the slot directly — a regression of this exact bug now fails CI.
- Finding F4 (ambient-factory re-overwrite) was an example of "the obvious fix in one place leaves a second place broken". Symmetric production paths — attended and ambient assembly — need symmetric fixes, even when the second path's call frequency is lower.
- The `capabilities_registry` kwarg default of `None` was a deliberate choice. Silently falling back to a list-shaped slot when the kwarg is omitted is exactly what the original bug did; surfacing `ERROR: registry_unavailable` is the documented sentinel (ADR-ARCH-021) and the operationally honest answer.

### Manual Verification (AC-011) — pending

```bash
OPENAI_API_KEY=sk-... python -m langgraph dev
# In another shell:
curl -X POST http://localhost:2024/threads/$(uuidgen)/runs/wait \
     -H 'content-type: application/json' \
     -d '{"assistant_id":"jarvis","input":{"messages":[{"role":"user","content":"What agents are available?"}]}}'
```

Expected: `list_available_capabilities` tool result is a valid JSON array (4 entries from the stub YAML when NATS is down, or live fleet when NATS is up), NOT a structured `ERROR:` or `DEGRADED:` string.

### Related ADRs / DDRs

- [DDR-021 — NATS unavailable soft-fail](../../../docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md) — amended by this task.
- [DDR-021 amendment — capabilities-registry tool wiring](../../../docs/design/FEAT-JARVIS-004/decisions/DDR-021-amendment-capabilities-registry-tool-wiring.md) — the new DDR for this fix.
- ADR-ARCH-021 — tools return structured errors; the `ERROR: registry_unavailable` sentinel.
- ADR-ARCH-023 — the reasoning model cannot rebind its tool list; the reason `assemble_tool_list` is the single wiring point.
- [TASK-REV-FFE4 review report](../../../.claude/reviews/TASK-REV-FFE4-review-report.md) — the review that found the defect; sequence diagram in §6, B1/B2/C trade-off in §10/§12.
