---
complexity: 4
created: 2026-04-24 00:00:00+00:00
dependencies:
- TASK-J003-001
- TASK-J003-003
estimated_minutes: 50
feature_id: FEAT-J003
id: TASK-J003-007
implementation_mode: task-work
parent_review: TASK-REV-J003
priority: high
status: design_approved
tags:
- phase-2
- jarvis
- feat-jarvis-003
- adapters
- ddr-015
task_type: feature
title: Implement LlamaSwapAdapter with stubbed health
updated: 2026-04-24 00:00:00+00:00
wave: 2
---

# Implement LlamaSwapAdapter with stubbed health

**Feature:** FEAT-JARVIS-003
**Wave:** 2 | **Mode:** task-work | **Complexity:** 4/10
**Parent review:** [TASK-REV-J003](../../in_review/TASK-REV-J003-plan-async-subagent-and-frontier-escape.md)

## Description

First Group-D adapter per ADR-ARCH-006 / DDR-015. Reads the *shape* of llama-swap's `/running` and `/log` endpoints but doesn't hit the network in Phase 2 — the read path is test-overrideable. FEAT-JARVIS-004 wires live reads against `http://promaxgb10-41b1:9000`. **Stub contract must match the live-read shape** so FEAT-J004 is a transport swap, not a schema swap (Context A concern #2).

## Acceptance Criteria

- [ ] `src/jarvis/adapters/llamaswap.py` exposes `class LlamaSwapAdapter` with constructor `__init__(self, base_url: str, *, _stub_response: Callable[[str], SwapStatus] | None = None)`. The `_stub_response` keyword-only arg is the test seam; production callers never pass it.
- [ ] `LlamaSwapAdapter.get_status(alias: str) -> SwapStatus` returns `SwapStatus(loaded_model=<alias>, eta_seconds=0, source="stub")` by default (model is assumed loaded).
- [ ] When the test `_stub_response` returns `SwapStatus(loaded_model=<alias>, eta_seconds=180, source="stub")` (or any eta_seconds > 30), the adapter returns that value unchanged — the adapter does not interpret the ETA, only the supervisor does.
- [ ] `get_status` is pure / idempotent: repeated calls with the same alias return equivalent `SwapStatus` instances; no internal counter or cache mutation across reads (scenario: *Repeated swap-status reads for the same alias return consistent results*).
- [ ] `src/jarvis/adapters/__init__.py` re-exports `LlamaSwapAdapter`.
- [ ] No outbound HTTP call in Phase 2; no `httpx`/`requests` import required at runtime (test-overrideable stub IS the read path).
- [ ] Docstring names the real `/running` + `/log` endpoint paths so FEAT-JARVIS-004 can grep for them at swap time.
- [ ] All modified files pass project-configured lint/format checks with zero errors.