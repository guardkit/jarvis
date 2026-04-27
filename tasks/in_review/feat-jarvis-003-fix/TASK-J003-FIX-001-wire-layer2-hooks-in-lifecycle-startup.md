---
complexity: 4
created: 2026-04-26 00:00:00+00:00
dependencies:
- TASK-J003-FIX-002
estimated_minutes: 60
feature_id: FEAT-J003-FIX
id: TASK-J003-FIX-001
implementation_mode: task-work
parent_review: FEAT-JARVIS-003
priority: high
status: in_review
tags:
- phase-2
- jarvis
- feat-jarvis-003-fix
- security
- ddr-014
- adr-arch-027
- tdd
task_type: bugfix
title: Wire escalate_to_frontier Layer 2 hooks in lifecycle.build_app_state
updated: 2026-04-27 00:00:00+00:00
wave: 2
---

# Wire escalate_to_frontier Layer 2 hooks in lifecycle.build_app_state

**Feature:** FEAT-J003-FIX
**Wave:** 2 | **Mode:** task-work (TDD) | **Complexity:** 4/10
**Parent review:** [FEAT-JARVIS-003 review report](../../../.claude/reviews/FEAT-JARVIS-003-review-report.md) — Finding F1
**ADR/DDR:** ADR-ARCH-027 (attended-only escape hatch), ADR-ARCH-022 (belt+braces),
DDR-014 (three-layer gate; *"Production wiring lands in `jarvis.infrastructure.lifecycle.startup`"*)

## Description

The FEAT-JARVIS-003 review found that Layer 2 of the `escalate_to_frontier` belt+braces gate is **dormant in production**. `_current_session_hook` and `_async_subagent_frame_hook` are defined in `jarvis.tools.dispatch` but never assigned in `src/`. `_check_attended_only` short-circuits to `None` (no rejection) when both hooks are unwired, leaving the constitutional cloud-spend gate operating with two layers (prompt + registration absence) instead of the documented three.

This task wires both hooks during `lifecycle.build_app_state` so the executor assertion is active in every production-built supervisor — the spoofed-ambient case (attended adapter session running an in-progress async-subagent frame) is then caught by Layer 2 even when Layer 3 (registration absence) hasn't been retrofitted onto a future ambient consumer.

TDD posture: write the spoofed-ambient integration test first (MUST FAIL on `main` today), then land the wiring, then watch it turn green.

## Acceptance Criteria

- [ ] **TDD red phase.** `tests/test_lifecycle_layer2_wiring.py::TestSpoofedAmbientRejected::test_attended_session_with_subagent_frame_rejects_escalation` is written and FAILS against the current `main` branch (proving F1 was real). Commit the failing test on its own commit so the regression-fix history is auditable.
- [ ] `lifecycle.build_app_state` assigns `dispatch._current_session_hook` to a callable that resolves the active `Session` via `session_manager.current_session()` (or whatever resolver the SessionManager exposes — add one if missing, name it `current_session`, return `None` when no session is active).
- [ ] `lifecycle.build_app_state` assigns `dispatch._async_subagent_frame_hook` to either:
  - (preferred) a probe over `AsyncSubAgentMiddleware` metadata if DeepAgents 0.5.3 exposes it, OR
  - (fallback per ASSUM-FRONTIER-CALLER-FRAME) a callable returning `None` so `_is_async_subagent_frame()` falls through to `session.metadata["currently_in_subagent"]`. Document the choice in a code comment that cites ASSUM-FRONTIER-CALLER-FRAME.
- [ ] Hook assignment is **idempotent** — calling `build_app_state` twice does not stack hooks or raise. Either reset to a fresh closure each time or guard with `if dispatch._current_session_hook is None`.
- [ ] `lifecycle.shutdown` clears both hooks back to `None` so a subsequent `build_app_state` in the same process (e.g. tests, `jarvis chat` restart) starts from a clean state.
- [ ] **Integration test green phase.** The spoofed-ambient test now passes — the supervisor built via `build_app_state` rejects an `escalate_to_frontier` invocation when the active session has `metadata["currently_in_subagent"] = True`, with the structured `"ERROR: attended_only — escalate_to_frontier cannot be invoked from async-subagent frame"` return string.
- [ ] Existing `tests/test_escalate_to_frontier.py` and `tests/test_tools_escalate_to_frontier_layer2.py` remain green — the new wiring must not break any per-test hook injection. Per-test hooks save and restore the module-level attributes; verify the save/restore pattern is compatible with the new lifecycle assignment (it is, but assert it explicitly in a teardown sanity check).
- [ ] `tests/test_lifecycle_startup_phase3.py` is extended to assert that `dispatch._current_session_hook is not None` after `build_app_state` returns. Same for the frame hook (or the documented `None` choice).
- [ ] All Phase 2 close criteria still hold post-fix: 1585 pytest pass, regression test green, langgraph.json smoke green, role-propagation green, routing E2E green.
- [ ] `mypy src/jarvis/` count of errors does not increase from the post-FIX-002 baseline (zero, ideally).
- [ ] `ruff check src/jarvis/` reports zero new violations.
- [ ] No instruction body or PII leaks into the new log records (ADR-ARCH-029 invariant — verified by extending `test_dispatch_types_frontier_escalation.py` field-set assertion to include the new code path).

## Files Expected to Change

- `src/jarvis/infrastructure/lifecycle.py` — wire hooks in `build_app_state`; clear in `shutdown`.
- `src/jarvis/sessions/manager.py` — add `current_session()` method if not present.
- `tests/test_lifecycle_layer2_wiring.py` — **NEW** integration test (red-then-green).
- `tests/test_lifecycle_startup_phase3.py` — extend AC assertions for hook population.

## Notes

The two-stage TDD requirement (failing-commit-then-passing-commit) is deliberate — F1 is a constitutional-gate gap and the audit trail should show the regression test catching it. AutoBuild's Coach should accept the failing-test commit as PASS (test correctly characterises a real defect) and the implementation commit as PASS (test now passes). If Coach rejects the failing-test commit, override and proceed.
