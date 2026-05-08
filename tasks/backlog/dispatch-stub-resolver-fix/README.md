# Feature: Dispatch Stub-Resolver Wiring Fix (FEAT-DSR)

**Parent review:** [TASK-REV-CB48](../TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md)
**Review report:** [`.claude/reviews/TASK-REV-CB48-review-report.md`](../../../.claude/reviews/TASK-REV-CB48-review-report.md)
**Demo blocker for:** DDD South West 2026-05-16 (dress rehearsal 2026-05-15)
**Decision:** Hybrid (W1 immediate + W2 by 2026-05-15)

## Problem

`assemble_tool_list` wires the **stub** capability list (from `stub_capabilities.yaml`) into `_dispatch._capability_registry`, while the live KV-backed `CapabilitiesRegistry` only reaches the catalogue tools. The dispatch resolver iterates the stub list at `dispatch.py:438` — any tool name in the live KV but absent from the stub yaml returns `ERROR: unresolved`. This blocked Phase 4 of the architect-align runbook on 2026-05-08 across three independent dispatch attempts.

This is the structural twin of [TASK-REV-FFE4](../../completed/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md) (catalogue-side gap, closed via TASK-J004-FIX-001). The two halves complete the FEAT-JARVIS-004 Live registry integration.

## Solution Approach

Hybrid plan — W1 today as demo insurance, W2 for durable close, runbook updates around both.

- **W1 (TASK-DSR-001):** Patch `stub_capabilities.yaml` to mirror the live KV's architect-agent tool list. Reversible, single file, 15 minutes.
- **Runbook immediate (TASK-DSR-002):** §0 pre-flight stub↔live alignment gate + §6 failure-mode row correction. Wave 1, parallel to W1.
- **W2 (TASK-DSR-003):** Real wiring fix in `tools/__init__.py` — snapshot from `capabilities_registry.snapshot()` instead of the stub list, plus a `subscribe_updates` callback that rebinds on KV changes. Includes the F3 divergent-registry integration test and the StubCapabilitiesRegistry parity test.
- **Runbook final + verification (TASK-DSR-004):** §2.5 rewrite (announce W2's status) and end-to-end re-run of `RUNBOOK-jarvis-architect-align-dddsw-demo.md` to confirm Phase 4 lands a real `AlignmentJudgment`.

## Subtasks

| ID | Title | Wave | Mode | Est. | Depends on |
|---|---|---|---|---|---|
| TASK-DSR-001 | W1 — patch `stub_capabilities.yaml` to mirror live KV | 1 | direct | 15m | — |
| TASK-DSR-002 | Runbook immediate updates (§0 gate + §6 row) | 1 | direct | 30m | — |
| TASK-DSR-003 | W2 — wiring fix + integration test + parity test | 2 | task-work | 3-4h | DSR-001 |
| TASK-DSR-004 | Runbook §2.5 rewrite + end-to-end verification | 3 | task-work | 1-2h | DSR-003 |

Wave 1 and Wave 3 tasks are markdown / config edits — `direct` mode is appropriate. Wave 2 is the production code change with full test additions — `task-work` runs the quality gates.

## Out of Scope

- Stub-yaml deprecation (decision 5 in the review). Recommendation R5 says **keep** the stub yaml post-W2 as the DDR-021 NATS-down fallback; rename its documented role and add a CI drift lint. This is a separate post-demo task.
- Forge dispatch path, supervisor model selection, FEAT-JARVIS-005 — all confirmed unaffected per review §"Out of Scope".

## See Also

- [Review report](../../../.claude/reviews/TASK-REV-CB48-review-report.md) — full findings and decision matrix.
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](../../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md) — original blocker evidence.
- [TASK-REV-FFE4](../../completed/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md) / [TASK-J004-FIX-001](../../completed/TASK-J004-FIX-001/TASK-J004-FIX-001.md) — structural twin and its real-fix precedent.
