---
id: TASK-DSR-002
title: "Runbook immediate updates — §0 stub↔live gate + §6 unresolved row"
task_type: docs
status: completed
created: 2026-05-08T00:00:00Z
updated: 2026-05-08T00:00:00Z
completed: 2026-05-08T00:00:00Z
priority: high
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 30
parent_review: TASK-REV-CB48
feature_id: FEAT-DSR
demo_blocker_for: 2026-05-16
tags: [jarvis, runbook, dispatch, dddsw-2026-05-16, docs]
context_files:
  - docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md
  - .claude/reviews/TASK-REV-CB48-review-report.md
test_results:
  status: pending
  coverage: null
  last_run: null
acceptance_criteria_status:
  AC-001: passing  # §0 stub↔live alignment gate added
  AC-002: passing  # §6 unresolved-row advice corrected
  AC-003: passing  # §2.5 untouched (deferred to TASK-DSR-004)
  AC-004: passing  # markdown links verified to resolve from runbook location
---

# Task: Runbook immediate updates — §0 stub↔live gate + §6 unresolved row

## Description

Two of the three runbook updates from review report R4 land in Wave 1 because
they describe the W1-current state (the structural gap is open until W2/DSR-003
ships). The §2.5 rewrite is held for Wave 3 (TASK-DSR-004) because its content
depends on W2 having shipped.

The §0 update is the load-bearing operational guard for the demo: it tells the
operator to verify the stub yaml lists every tool the supervisor will dispatch
before booting. The §6 update corrects misleading "restart jarvis chat" advice
that does not address the actual cause (yaml↔live divergence).

## Implementation

Edit `docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md`.

### §0 — Add new pre-flight gate

Add a new gate item to the §0 pre-flight section (place near the bottom of
existing checks so the order reads "infrastructure → fleet → alignment").
Suggested text:

> **Stub ↔ Live alignment.** For every `tool_name` the supervisor will
> dispatch in this run, confirm the corresponding `agent_id` entry in
> `src/jarvis/config/stub_capabilities.yaml` includes that `tool_name` in its
> `capability_list`. The dispatch resolver iterates the stub yaml only —
> divergence between the live KV and the yaml causes `ERROR: unresolved` even
> when the prompt block (sourced from the live KV) shows the tool name.
> Until [TASK-DSR-003](../../tasks/backlog/dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)
> (W2) ships, this is the single guard that saves a demo. Reference:
> [TASK-REV-CB48 review report](../../.claude/reviews/TASK-REV-CB48-review-report.md).

### §6 — Update the `unresolved` failure-mode row

Locate the row (or paragraph) in the §6 failure-modes section that handles
`ERROR: unresolved`. Replace the existing "restart jarvis chat" advice with:

> **Cause:** The `tool_name` is not present in `stub_capabilities.yaml` for the
> matching `agent_id`. The dispatch resolver iterates the stub yaml only and
> returns `ERROR: unresolved` when no match exists, regardless of what the live
> KV publishes.
> **Fix:** Add the `tool_name` to the agent's `capability_list` in
> `src/jarvis/config/stub_capabilities.yaml` (W1 / TASK-DSR-001), or land
> [TASK-DSR-003](../../tasks/backlog/dispatch-stub-resolver-fix/TASK-DSR-003-W2-wiring-fix-and-tests.md)
> (W2 — wires the live KV into the dispatch slot directly). Restarting Jarvis
> without editing the yaml or shipping W2 will reproduce the same error.

If §6 has multiple rows for `unresolved` vs `exhausted`, this update applies
only to the `unresolved` row — keep the `exhausted` advice intact.

### §2.5 — DEFER to TASK-DSR-004

Do **not** edit §2.5 in this task. The §2.5 rewrite depends on W2's status
(once W2 ships, the section can be deleted entirely as obsolete). TASK-DSR-004
handles it.

## Acceptance Criteria

- [ ] **AC-001:** §0 pre-flight contains the new "Stub ↔ Live alignment"
      gate, referencing this feature's tasks and the review report.
- [ ] **AC-002:** §6 `unresolved` row replaces the "restart jarvis chat"
      advice with the actionable fix path (W1 yaml edit OR W2 wiring fix).
- [ ] **AC-003:** §2.5 is unchanged in this task (TASK-DSR-004 handles it
      after W2 ships).
- [ ] **AC-004:** Markdown links resolve (relative paths work from the
      runbook's location).

## Out of Scope

- §2.5 rewrite — TASK-DSR-004.
- Adding the runbook's results-doc back-link — separate concern.

## See Also

- [Review report](../../../.claude/reviews/TASK-REV-CB48-review-report.md) — R4.
- [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md) — file to edit.
- [TASK-DSR-001](./TASK-DSR-001-W1-stub-yaml-patch.md) — the W1 path the §6 fix references.
- [TASK-DSR-003](./TASK-DSR-003-W2-wiring-fix-and-tests.md) — the W2 path the §0 gate references.
- [TASK-DSR-004](./TASK-DSR-004-runbook-final-rewrite-and-verification.md) — handles §2.5 post-W2.
