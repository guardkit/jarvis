---
autobuild_state:
  base_branch: main
  current_turn: 1
  last_updated: '2026-04-28T08:01:46.615431'
  max_turns: 30
  started_at: '2026-04-28T07:50:31.927706'
  turns:
  - coach_success: true
    decision: approve
    feedback: null
    player_success: true
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    timestamp: '2026-04-28T07:50:31.927706'
    turn: 1
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-J004-702C
complexity: 4
created: 2026-04-27 15:30:00+00:00
dependencies: []
feature_id: FEAT-JARVIS-004
id: TASK-J004-004
implementation_mode: task-work
parent_review: TASK-REV-22CF
priority: high
status: design_approved
tags:
- routing-history
- pydantic
- schema
- FEAT-JARVIS-004
task_type: declarative
test_results:
  coverage: null
  last_run: null
  status: pending
title: JarvisRoutingHistoryEntry Pydantic schema (declarative-only, no writer)
wave: 1
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