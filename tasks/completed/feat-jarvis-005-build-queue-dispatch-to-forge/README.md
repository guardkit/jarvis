# FEAT-JARVIS-005 — Build Queue Dispatch to Forge

| | |
|---|---|
| **Feature ID** | `FEAT-J005-946D` |
| **Parent review** | `TASK-REV-3B8B` |
| **Created** | 2026-04-29 |
| **Tasks** | 12 across 5 waves |
| **Aggregate complexity** | 7/10 |
| **Status** | planned |

## Purpose

Closes the Jarvis → Forge loop. `queue_build` swaps from a Phase 2 stub log
line to a real `js.publish(...)` on `pipeline.build-queued.{feature_id}`
(ADR-SP-014 Pattern A + DDR-025); Jarvis subscribes to
`pipeline.stage-complete.>` and surfaces matching notifications back to the
originating session's CLI between prompts (DDR-026..030). Adapter identity is
constitutional — resolved from `Session.adapter` (DDR-031). Stage-complete
events become append-only Graphiti edges on the originating routing-history
entry (DDR-029).

This is a **Phase 3 closer** for the DDD Southwest demo deadline.

## Context

- **Spec**:
  [feat-jarvis-005-…_summary.md](../../../features/feat-jarvis-005-build-queue-dispatch-to-forge/feat-jarvis-005-build-queue-dispatch-to-forge_summary.md) (32 scenarios, 4 smoke)
- **Design**:
  [docs/design/FEAT-JARVIS-005/design.md](../../../docs/design/FEAT-JARVIS-005/design.md)
- **DDRs**:
  [DDR-025..031](../../../docs/design/FEAT-JARVIS-005/decisions/) — all 11
  assumptions resolved high-confidence
- **Build plan**:
  [phase3-build-plan.md](../../../docs/research/ideas/phase3-build-plan.md)

## Quick start

```bash
# Sequential (one-at-a-time)
/task-work TASK-J005-001
/task-work TASK-J005-002
/task-work TASK-J005-004
/task-work TASK-J005-006
# … etc through TASK-J005-012

# Parallel via AutoBuild (preferred)
/feature-build FEAT-J005-946D
```

See [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) for:
- Wave structure and parallel groups
- Data flow diagram (read/write paths)
- `queue_build` runtime sequence diagram
- §4 Integration Contracts (cross-task data flow)
- Task dependency graph
- Verification of cross-cutting concerns (DDRs, ADRs)

## Files modified

| File | Task | Change |
|---|---|---|
| `src/jarvis/config/settings.py` | 001 | Add 3 fields (timeout + caps) |
| `src/jarvis/infrastructure/forge_notifications.py` | 002, 003 | NEW (declarative + subscriber) |
| `src/jarvis/infrastructure/routing_history.py` | 004 | Replace J004 no-ops with real writers |
| `src/jarvis/sessions/manager.py` | 006 | Add per-session pending notification queue |
| `src/jarvis/cli/main.py` | 007 | Render notifications between prompts |
| `src/jarvis/tools/dispatch.py` | 005 | Real `queue_build` JetStream publish |
| `src/jarvis/infrastructure/lifecycle.py` | 008 | Start/bind/stop subscriber |
| `tests/test_jarvis_005_soft_fail.py` (new) | 009 | NATS / Graphiti / stop-bound |
| `tests/test_contract_nats_core.py` | 010 | Cross-repo contract verification |
| `tests/test_phase2_stubs_retired.py` (extend) | 011 | Grep-invariant retire |
| `tests/test_end_to_end_forge_roundtrip.py` (new) | 012 | Phase 3 close evidence |

## Success criteria

- All 32 BDD scenarios in `feat-jarvis-005-….feature` pass against the
  in-process JetStream test server (Wave 4 contract gate).
- Phase 3 evidence test (Wave 5) records a successful round-trip on GB10:
  one Graphiti `JarvisRoutingHistoryEntry` for the queue_build dispatch + one
  stage-complete edge per Forge stage.
- No `LOG_PREFIX_QUEUE_BUILD` reference remains in `src/jarvis/` (Wave 4 grep).
