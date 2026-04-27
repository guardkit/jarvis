---
id: TASK-J004-001
title: Promote ASSUM-008 + ASSUM-009 to DDR-024 + DDR-023
task_type: documentation
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 1
implementation_mode: direct
complexity: 2
dependencies: []
priority: high
tags:
- docs
- ddr
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
  started_at: '2026-04-27T16:42:59.611604'
  last_updated: '2026-04-27T16:51:13.628814'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-27T16:42:59.611604'
    player_summary: 'Pure documentation task. Worktree autobuild/FEAT-J004-702C did
      not contain the FEAT-JARVIS-004 design directory because the main repo had it
      untracked; copied design.md, decisions/DDR-016..022.md, contracts/, diagrams/,
      models/, and the assumptions YAML into the worktree as a prerequisite. Then:
      (1) Created DDR-023 (trace-file collision: O_CREAT|O_EXCL; on FileExistsError
      log WARN routing_history_write_failed and preserve original), promoting ASSUM-009
      from low confidence; rationale leans on DDR'
    player_success: true
    coach_success: true
---

# TASK-J004-001 — Promote ASSUM-008 + ASSUM-009 to DDR-024 + DDR-023

## Description

Convert two flagged assumptions from `feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml` into append-only DDRs so they stop carrying low/medium-confidence tags through the rest of Wave 1+:

- **DDR-023** (resolves ASSUM-009 — *low confidence*): trace-file collision policy. When a per-decision trace file already exists at `~/.jarvis/traces/{date}/{decision_id}.json`, the routing history writer logs `WARN routing_history_write_failed`, preserves the original, does not overwrite. Rationale: `decision_id` is UUIDv4, so collision implies UUID re-use which is itself an error condition; preserving the original retains audit-trail evidence; aligns with `frozen=True` invariant.
- **DDR-024** (resolves ASSUM-008 — *medium confidence*): degraded specialists remain dispatch-eligible at resolution time in v1; redirect-with-retry (DDR-017) handles their failures. FEAT-J008 (`jarvis.learning`, v1.5) may suppress later via append-only DDR. Routing-history captures specialist status at decision time.

Both are **append-only** DDRs — they pin behaviour the design implicitly assumed but never explicitly decided.

## Acceptance Criteria

- [ ] `docs/design/FEAT-JARVIS-004/decisions/DDR-023-trace-file-collision-warn-and-preserve.md` created with Status / Date / Context / Decision / Rationale / Alternatives / Consequences sections matching the existing DDR-016..022 template.
- [ ] `docs/design/FEAT-JARVIS-004/decisions/DDR-024-degraded-specialists-eligible-v1.md` created using the same template.
- [ ] `feat-jarvis-004-fleet-registration-and-specialist-dispatch_assumptions.yaml` updated: ASSUM-008 confidence → "high" with `resolved_by: DDR-024`; ASSUM-009 confidence → "high" with `resolved_by: DDR-023`. The `human_response` line on both is updated to reflect promotion.
- [ ] `docs/design/FEAT-JARVIS-004/design.md` §5 (Design decisions captured) and §11 (Contradiction detection) reference the new DDRs.
- [ ] No code changes — pure documentation task.

## Test Requirements

- [ ] None — documentation-only task. Files render in markdown preview without errors. Cross-references resolve to existing files.

## Implementation Notes

DDR template (mirror DDR-016 through DDR-022 structure):

```markdown
# DDR-XXX — <one-line decision>

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** <ADR / DDR refs>
- **Resolves:** ASSUM-XXX (was confidence: low|medium)

## Context
## Decision
## Rationale
## Alternatives considered
## Consequences
## Status
```

Both DDRs land in a single commit with a single review-link back to TASK-REV-22CF. No file moves; both new files only.

## Test Execution Log

(Populated by /task-work.)
