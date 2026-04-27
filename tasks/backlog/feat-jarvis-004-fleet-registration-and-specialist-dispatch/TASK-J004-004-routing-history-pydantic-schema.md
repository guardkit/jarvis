---
id: TASK-J004-004
title: JarvisRoutingHistoryEntry Pydantic schema (declarative-only, no writer)
task_type: declarative
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 1
implementation_mode: task-work
complexity: 4
dependencies: []
priority: high
tags:
- routing-history
- pydantic
- schema
- FEAT-JARVIS-004
status: in_review
created: 2026-04-27 15:30:00+00:00
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J004-702C
  base_branch: main
  started_at: '2026-04-27T19:56:15.737211'
  last_updated: '2026-04-27T20:01:48.198889'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-27T19:56:15.737211'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# TASK-J004-004 — JarvisRoutingHistoryEntry Pydantic schema

## Description

Land the **schema only** for `src/jarvis/infrastructure/routing_history.py`
per [DM-routing-history.md](../../../docs/design/FEAT-JARVIS-004/models/DM-routing-history.md):

- `JarvisRoutingHistoryEntry` (BaseModel, `frozen=True`, `extra="ignore"`)
  — full ADR-FLEET-001 §1–§7 fields plus Jarvis-specific extensions.
- `DispatchOutcome` (closed Literal: success / redirected / timeout /
  specialist_error / exhausted / transport_unavailable / unresolved).
- `RedirectAttempt` (BaseModel; `agent_id`, `attempt_index`,
  `reason_skipped`, `detail`, `duration_ms`).
- `TraceRef` (BaseModel; `path`, `content_sha256`, `size_bytes`).
- `ToolCallRecord`, `ModelCallRecord`, `CapabilityDescriptorRef`,
  `ConcurrentWorkloadSnapshot` helper types.

This task **does not** ship the writer (`RoutingHistoryWriter`,
`write_specialist_dispatch`, filesystem offload, redaction) — that lands
in TASK-J004-010. Splitting schema-from-writer here means TASK-J004-005
(schema-conformance test) and TASK-J004-010 (writer logic) can run
in parallel.

## Acceptance Criteria

- [ ] `src/jarvis/infrastructure/routing_history.py` exports the 8 types listed above.
- [ ] `JarvisRoutingHistoryEntry.model_config = ConfigDict(extra="ignore", frozen=True)`.
- [ ] All Field validators match DM-routing-history.md verbatim (regex patterns, max_length, ge/le bounds).
- [ ] `DispatchOutcome` is a closed `Literal[...]` with exactly the seven members listed.
- [ ] `__all__` exports are explicit.
- [ ] No writer logic, no filesystem I/O, no Graphiti import in this file.
- [ ] `uv run mypy src/jarvis/infrastructure/routing_history.py` passes (strict mode).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Schema-conformance tests live in TASK-J004-005 (parallel-safe).

## Implementation Notes

This is a **declarative** task — Pydantic models only. The writer class
`RoutingHistoryWriter` is added to this same module by TASK-J004-010,
so the file's `__all__` should be ready to extend (declare in this
task: `__all__ = ["JarvisRoutingHistoryEntry", "DispatchOutcome", ...]`;
TASK-J004-010 appends `"RoutingHistoryWriter"`).

DDR-018 makes this schema **authoritative for v1+**. Future field
additions are append-only via ADR-FLEET-00X. Renames or type changes
require a `schema_version` field at the change point. Get it right here.

## Test Execution Log

(Populated by /task-work.)
