---
id: TASK-DSR-004
title: "Runbook §2.5 final rewrite + end-to-end re-run verification"
task_type: docs
status: backlog
created: 2026-05-08T00:00:00Z
updated: 2026-05-08T00:00:00Z
priority: high
complexity: 2
wave: 3
implementation_mode: task-work
estimated_minutes: 90
parent_review: TASK-REV-CB48
feature_id: FEAT-DSR
demo_blocker_for: 2026-05-16
depends_on:
  - TASK-DSR-003  # W2 must be merged + manually smoked before the §2.5 rewrite makes sense
tags: [jarvis, runbook, dispatch, dddsw-2026-05-16, verification, end-to-end]
context_files:
  - docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md
  - docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md
  - .claude/reviews/TASK-REV-CB48-review-report.md
test_results:
  status: pending
  coverage: null
  last_run: null
acceptance_criteria_status:
  AC-001: complete   # §2.5 divergence note replaced with post-W2 parity note (2026-05-08)
  AC-002: complete   # §0.5 softened to advisory; §6 unresolved row reordered (2026-05-08)
  AC-003: pending    # End-to-end runbook re-run on GB10 host (operator-driven, separate session)
  AC-004: pending    # Real AlignmentJudgment in chat REPL (gated on AC-003)
  AC-005: pending    # New RESULTS-*-{date}.md doc capturing green run (gated on AC-003)
  AC-006: pending    # Wire-tap + FRR-003 trace evidence in dddsw-demo-{date}-green/ (gated on AC-003)
session_log:
  - date: 2026-05-08
    scope: "Steps 1+2 only (doc edits) per operator clarification; Steps 3+4 (runbook re-run + RESULTS doc) deferred to separate session that requires GB10 host access"
    files_touched:
      - docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md  # §0.5, §2.5 callout, §6 unresolved row
---

# Task: Runbook §2.5 final rewrite + end-to-end re-run verification

## Description

Two coupled outcomes after W2 (TASK-DSR-003) ships and is smoke-tested:

1. **§2.5 rewrite.** The current §2.5 "Catalogue-vs-stub note" claims the live
   KV watch "replaces the stub entries". Pre-W2 that was half-correct
   (catalogue path only). Post-W2 the live registry feeds *both* the
   catalogue path AND the dispatch resolver, so the section's premise is
   obsolete. Either delete it entirely or rewrite as a historical note that
   references TASK-REV-CB48 and TASK-DSR-003 as the closure.

2. **End-to-end re-run.** The original AC from TASK-REV-CB48 — re-run
   `RUNBOOK-jarvis-architect-align-dddsw-demo.md` end-to-end against the
   dual-role stack on the GB10 host. Phase 4 must land a real
   `agents.command.architect-agent.<corr>` envelope, the architect container's
   command router maps `architect_align → align`, and a real `AlignmentJudgment`
   lands in the chat REPL. Capture outcomes in a new `RESULTS-*-2026-05-XX.md`
   alongside the existing 2026-05-08 results doc.

## Implementation

### Step 1 — §2.5 decision

Read the current §2.5 in `docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md`.
Decide between:

**Option A (recommended): delete entirely.** Replace with a one-line historical
note immediately above the next section:

> *Note: §2.5 previously documented a divergence between the live KV
> (catalogue path) and the stub yaml (dispatch resolver path). That gap was
> closed by [TASK-REV-CB48](../../.claude/reviews/TASK-REV-CB48-review-report.md)
> / [TASK-DSR-003](../../tasks/completed/TASK-DSR-003-W2-wiring-fix-and-tests.md);
> both paths now read the live KV. Section retired.*

**Option B: rewrite as a positive statement.** If §2.5 carries operationally
useful content beyond the divergence note, rewrite the section to describe
the post-W2 state — the live KV is the single source of truth for both
catalogue tools and the dispatch resolver, the stub yaml's only remaining
role is the DDR-021 NATS-down soft-fail. Keep the section if it serves
operators reading the runbook for the first time; delete it if its content
was purely about the former divergence.

Pick A unless §2.5 has additional content the runbook needs.

### Step 2 — §0 + §6 review pass

The Wave 1 task (TASK-DSR-002) added a §0 stub↔live alignment gate and
corrected the §6 `unresolved` row. Now that W2 ships, soften both:

- **§0 gate** — downgrade from "single guard that saves a demo" to advisory:
  > *Optional sanity check (post-W2): confirm `stub_capabilities.yaml`
  > matches the live KV's published surface for any agent the supervisor
  > will dispatch to. The dispatch resolver now reads the live KV directly,
  > so divergence is operationally tolerated; a CI drift lint is a follow-up
  > (see review report R5).*
- **§6 `unresolved` row** — keep the cause / fix structure but reorder:
  the W2 path is now the canonical close; W1 yaml edit is the fallback for
  NATS-down boots (where the dispatch resolver reads the StubCapabilitiesRegistry's
  yaml content via the W2 wireup).

### Step 3 — End-to-end runbook re-run

Boot the dual-role stack on the GB10 host. Walk all phases of
`RUNBOOK-jarvis-architect-align-dddsw-demo.md` end-to-end:

- Phases 0-3 should pass as they did on 2026-05-08 (those were green).
- Phase 4 must now land a real `agents.command.architect-agent.<corr>`
  envelope on JetStream. Capture the trace correlation ID.
- The architect container's command router maps `architect_align → align`.
- A real `AlignmentJudgment` lands in the chat REPL.
- Capture wire taps and FRR-003 routing-history traces alongside the existing
  2026-05-08 evidence in `docs/runbooks/evidence/`.

### Step 4 — New RESULTS doc

Create `docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-{YYYY-MM-DD}.md`
mirroring the structure of the 2026-05-08 doc. Include:

- Per-phase outcomes (especially Phase 4 — the originally blocked step).
- Comparison with the 2026-05-08 RESULTS doc's "blocked" outcome — what
  changed (TASK-DSR-001 W1 + TASK-DSR-003 W2 + this task's runbook updates).
- Trace correlation IDs and JetStream subject paths captured.
- Any unexpected behaviour (e.g. supervisor prose interpretation issues that
  are model-side concerns, not wiring concerns — document but mark out-of-scope
  per the original review's §"Out of Scope").

Link the new RESULTS doc from this task's frontmatter `evidence_files` once it
exists.

## Acceptance Criteria

- [ ] **AC-001:** §2.5 is rewritten or deleted post-W2 per Step 1's decision
      (Option A or Option B); the section no longer claims a divergence
      between live KV and stub yaml.
- [ ] **AC-002:** §0 and §6 are softened per Step 2 — §0 advisory rather
      than load-bearing; §6 `unresolved` row reflects W2 as canonical close.
- [ ] **AC-003:** End-to-end runbook re-run completes; Phase 4 lands a real
      `agents.command.architect-agent.<corr>` envelope with a captured
      correlation ID.
- [ ] **AC-004:** A real `AlignmentJudgment` lands in the chat REPL.
- [ ] **AC-005:** A new `RESULTS-*-{date}.md` doc is created in
      `docs/runbooks/` capturing the green run and contrasting with the
      2026-05-08 blocked outcome.
- [ ] **AC-006:** Wire-tap and FRR-003 trace evidence is captured alongside
      the existing `dddsw-demo-2026-05-08-blocked/` directory (e.g. in a
      sibling `dddsw-demo-{date}-green/` directory).

## Out of Scope

- Stub-yaml deprecation (review report R5) — separate post-demo task.
- Supervisor prose / model-side concerns surfaced during the re-run — document
  in the RESULTS doc as observations but do not act on them here.
- Any FEAT-JARVIS-005 changes — separate registry-free path.

## See Also

- [Review report](../../../.claude/reviews/TASK-REV-CB48-review-report.md) — R4 (runbook updates).
- [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md) — file to edit + run.
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](../../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md) — original blocked run, template for the new green-run doc.
- [TASK-DSR-002](./TASK-DSR-002-runbook-immediate-updates.md) — Wave 1 runbook updates this task softens.
- [TASK-DSR-003](./TASK-DSR-003-W2-wiring-fix-and-tests.md) — W2 fix this task verifies end-to-end.
