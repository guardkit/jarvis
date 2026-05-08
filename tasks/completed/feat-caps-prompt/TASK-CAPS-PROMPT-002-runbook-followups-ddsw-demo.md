---
id: TASK-CAPS-PROMPT-002
title: "Runbook follow-ups: §0.1, §0.5, §4.2/§4.4/§6, §4.3, §5.2 (DDD South West demo)"
task_type: docs
status: completed
created: 2026-05-08T19:35:00Z
updated: 2026-05-08T20:45:00Z
completed: 2026-05-08T20:45:00Z
completed_location: tasks/completed/feat-caps-prompt/
priority: high
complexity: 2
implementation_mode: direct
estimated_minutes: 60
parent_review: TASK-REV-9939
feature_id: FEAT-CAPS-PROMPT
demo_blocker_for: 2026-05-16
go_no_go_date: 2026-05-15  # Must land before dress rehearsal
related_tasks:
  - TASK-CAPS-PROMPT-001  # Sibling — code R2 fix; §4.2/§4.4/§6 conditional on it landing
  - TASK-REV-9939         # Parent review
tags: [jarvis, runbook, docs, dddsw-2026-05-16, supervisor-prompt, dispatch-evidence]
context_files:
  - docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md
  - docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md
  - .claude/reviews/TASK-REV-9939-review-report.md
  - /home/richardwoollcott/Projects/appmilla_github/specialist-agent/src/specialist_agent/generation/types.py  # Line 147 — judgment Literal source-of-truth
upstream_evidence_files:
  - docs/runbooks/evidence/dddsw-demo/wire-command-2026-05-08-postfix.log  # Bug #1 fix routes via msg.reply, not agents.result.<id>
test_results:
  status: pending  # docs-only, no test gates
  coverage: null
  last_run: null
acceptance_criteria_status:
  AC-001: complete  # §0.1 stale commit hash dropped
  AC-002: complete  # §0.5 yaml introspection key fixed
  AC-003: complete  # §4.3 judgment Literal aligned to schema
  AC-004: complete  # §5.2 wire-tap inbox-routing note (load-bearing for stage)
  AC-005: complete  # §4.2/§4.4/§6 explicit-args workaround footnote (R1 path; TASK-CAPS-PROMPT-001 still in_progress)
---

# Task: Runbook follow-ups for DDD South West demo

## Description

Five runbook docs updates surfaced by [`TASK-REV-9939`](../in_review/TASK-REV-9939-capabilities-prompt-block-missing-parameter-schema.md)
Decision D5. Independent of the R2 code fix (sibling
[`TASK-CAPS-PROMPT-001`](TASK-CAPS-PROMPT-001-render-tool-parameter-schema.md)) —
**must land before 2026-05-15 dress rehearsal** so the on-stage operator works
against an accurate guide.

§5.2 is the load-bearing edit for stage: the existing wire-tap on
`agents.result.<agent_id>` will leave the audience watching an empty pane after
Bug #1's `msg.reply` inbox-routing fix. Prioritise §5.2 if any pressure forces
edits to be split across multiple PRs.

§4.2/§4.4/§6 (drop the explicit-args workaround language) is **conditional on
TASK-CAPS-PROMPT-001 landing first**. If R2 slips to the demo's break-glass
window, leave the explicit-args language in place and add a footnote noting the
natural-routing claim is degraded for the R1/explicit-args path.

## Implementation

Single-PR docs change against
[`docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md).
Sub-edits:

### Edit 1 — §0.1 expected commit hash *(trivial)*

The hash `ca2ba6b` is several commits stale (top-of-log moved to `4c53e6c` on
2026-05-08 and continues drifting). Drop the specific hash; the runbook is
otherwise version-agnostic. Replace with a comment that the runbook tracks
`main` and the specific HEAD is not load-bearing.

### Edit 2 — §0.5 yaml introspection one-liner *(trivial fix)*

Current one-liner uses `d.get('agents', [])` but the file's top-level key is
`capabilities:` — silently returns empty. Fix:

```python
d.get('capabilities', [])
```

### Edit 3 — §4.3 `judgment` Literal values *(schema alignment)*

Current text lists `"needs_clarification" | "aligned" | "not_aligned"`.
Source-of-truth at
[`specialist_agent/generation/types.py:147`](file:///home/richardwoollcott/Projects/appmilla_github/specialist-agent/src/specialist_agent/generation/types.py#L147)
is `Literal["aligned", "misaligned", "needs_clarification"]`. The 2026-05-08
post-fix run returned `"misaligned"`, which is in-schema.

Replace `"not_aligned"` with `"misaligned"` and reorder to match the schema
declaration order if the runbook lists them in a fixed order. Ordering is not
load-bearing — alphabetic or schema-order, pick one.

### Edit 4 — §5.2 wire-tap inbox-routing *(load-bearing for stage)*

Bug #1 fix (specialist-agent commit `1979aa8`, nats-core v0.4.0
`subscribe_with_reply`/`publish_raw`) routes replies via the `msg.reply` inbox
subject, **not** `agents.result.<agent_id>`. Two options for the rewrite:

**Option A (recommended)** — replace the `agents.result.<agent_id>` tap with
an `_INBOX.>` tap. Pros: still a wire-mirror moment for the talk; shows the
correct subject. Cons: `_INBOX.>` is high-traffic; requires a filter on the
correlation_id to be useful for stage.

**Option B** — drop §5.2 entirely; replace with a directed log of jarvis's
`nats_request_received` event. Pros: zero risk of audience confusion. Cons:
loses the "watch the wire" theatre.

**Decision:** ship Option A with a correlation-id filter. Add a footnote
explaining the Bug #1 fix's reply-channel change so future runbook readers
don't expect old behaviour:

> *Footnote (2026-05-08, post-Bug #1):* Specialist replies route via the
> NATS `msg.reply` inbox subject (typically `_INBOX.>`), **not** the
> previous `agents.result.<agent_id>` subject. The `subscribe_with_reply` /
> `publish_raw` change in `nats-core` v0.4.0 (`8f2c532` / specialist-agent
> `1979aa8`) closed the request/reply round-trip; the old `agents.result.*`
> subject is reserved for fan-out events, not point-to-point replies.

### Edit 5 — §4.2 / §4.4 / §6 explicit-args workaround *(conditional on TASK-CAPS-PROMPT-001)*

These three sections currently script the operator to enumerate the three
required architect_align args (`context`, `proposal`, `question`) explicitly
in their prompt — the workaround that yielded the 2026-05-08 success trace
(`8df345b4`).

Once TASK-CAPS-PROMPT-001 (R2) lands, the on-stage prompt no longer needs
this workaround. Update to:

- Remove the explicit-args enumeration from the on-stage operator prompt.
- Add a note that the supervisor will construct the payload from the `Args
  (required):` block rendered in the catalogue under §"Available Capabilities".
- Cite the R2 fix (this PR's sibling TASK-CAPS-PROMPT-001) and the snapshot
  test as the reliability guarantee.

**Conditional gate:** if TASK-CAPS-PROMPT-001 has not merged to `main` by
the time this docs PR is ready to ship, leave the explicit-args language in
place and add a footnote:

> *Footnote (2026-05-08):* The explicit-args prompt is the R1/break-glass
> path. The R2 catalogue-render fix (TASK-CAPS-PROMPT-001) is targeted for
> 2026-05-13; once landed the natural-routing claim is restored and this
> section will be updated.

## Acceptance Criteria

- [ ] **AC-001** — §0.1 stale `ca2ba6b` commit hash dropped; runbook
      tracks `main` HEAD comment in its place.
- [ ] **AC-002** — §0.5 yaml introspection one-liner uses
      `d.get('capabilities', [])`.
- [ ] **AC-003** — §4.3 `judgment` Literal lists exactly the three
      schema values: `"aligned"`, `"misaligned"`, `"needs_clarification"`.
- [ ] **AC-004** — §5.2 wire-tap rewritten per Edit 4 Option A
      (`_INBOX.>` with correlation-id filter) plus footnote explaining the
      Bug #1 reply-channel change. **(Load-bearing for stage.)**
- [ ] **AC-005** — §4.2/§4.4/§6 updated per Edit 5: either explicit-args
      workaround removed (if TASK-CAPS-PROMPT-001 landed) or footnote added
      flagging the R1/break-glass path (if R2 slips).
- [ ] PR opens against `main` with the runbook diff visible; reviewer can
      see all five edits in one read.
- [ ] Dress-rehearsal walkthrough on **2026-05-15** confirms the on-stage
      operator follows §5.2 and §4.2/§4.4/§6 cleanly with no script
      ambiguity.

## Implementation Summary

Single-PR docs change against `docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md` applied 2026-05-08. All five edits landed in one read:

- **§0.1** — Dropped stale `ca2ba6b` HEAD reference; runbook now declares it tracks `main` non-load-bearingly and gates only on the two specific commits (`dcaa8eb` lifecycle subscriber widening, `6071fe0` TASK-FRR-F010Db disjoint filter) the demo's hygiene assumes.
- **§0.5** — Fixed yaml introspection one-liner: `d.get('agents', [])` → `d.get('capabilities', [])`. Verified against `src/jarvis/config/stub_capabilities.yaml` whose top-level key is `capabilities` (item shape unchanged: still has `agent_id` / `capability_list`).
- **§4.3** — Aligned `judgment` Literal to source-of-truth at `specialist_agent/generation/types.py:147` (`"aligned" | "misaligned" | "needs_clarification"`). Cascaded the rename to three prose references (`not_aligned` → `misaligned`) in §0.6 Option A and §4.3 prose for Option A / Option B expected-judgment paragraphs.
- **§5.2** *(load-bearing for stage)* — Replaced `agents.result.architect-agent.>` tap with `_INBOX.>` tap filtered via `jq --arg cid "$CID" 'select(.correlation_id == $cid)'`. Added footnote explaining the Bug #1 reply-channel change (`nats-core` v0.4.0 `subscribe_with_reply` / `publish_raw`, specialist-agent `1979aa8`). Cascaded change to topology overview (line 13), Phase 6 troubleshooting (replaced one row, added two new rows for the `_INBOX.>` failure modes), and Phase 8 close criterion.
- **§4.2 / §4.4 / §6** *(conditional gate)* — TASK-CAPS-PROMPT-001 still `in_progress` at completion time, so per the conditional gate I left the explicit-args framing in place. Added an R1/break-glass footnote at §4.2 documenting why §4.1's `Context: / Proposal: / Question:` prompt template is the workaround (catalogue render omits `Args (required):`), citing the 2026-05-08 success trace `correlation_id=8df345b4-7b47-4214-8ae3-959aac5252e4`. Added a back-reference at §4.4. Both notes are written to retire cleanly once R2 merges.

**Approach:** Direct edits on `main` working tree (no branch) — task is docs-only with no test gates, complexity 2/10, well-scoped.

**Outcome:** All five ACs (AC-001..AC-005) marked complete in frontmatter. The two unchecked checkboxes at the bottom of the AC list (PR open, dress-rehearsal walkthrough on 2026-05-15) are operational gates outside this implementation's scope.

**Out-of-scope confirmed untouched:** `src/jarvis/config/stub_capabilities.yaml`, `src/jarvis/infrastructure/capabilities_registry.py`, `src/jarvis/tools/capabilities.py` had pre-existing modifications in the working tree from sibling TASK-CAPS-PROMPT-001 R2 work — left alone.

## Notes

**Lessons / non-obvious bits worth carrying forward:**

1. **The §4.3 schema-alignment fix had a hidden cascade.** The AC only called for fixing the Literal block, but `not_aligned` appeared three more times in surrounding prose (Option A pre-stage table, §4.3 expected-judgment paragraphs). A literal-only fix would have left the runbook internally inconsistent — worth a `grep -n` sweep on any string-literal schema fix in future docs work.
2. **§5.2 `_INBOX.>` cascade was bigger than the AC suggested.** AC-004 named §5.2 and the footnote, but the request/reply switch also invalidated:
   - Topology narrative (line 13) describing the response subject
   - One Phase 6 troubleshooting row about `agents.result.architect-agent.>` 32-byte PubAck
   - Phase 8 close criterion about response-tail capture
   Future load-bearing wire-subject changes should look for these three echo points by default.
3. **Conditional-gate detection for AC-005 worked off `git log` for the sibling task ID.** TASK-CAPS-PROMPT-001 had no merge commit on `main`, plus its task file lived in `tasks/in_progress/` — both signals agreed on R1-path-not-yet-shipped, so the footnote variant of Edit 5 was the right call. Document this dual-signal check in the conditional-gate language for future sibling-gated tasks.
4. **Bug #1 reply-channel change is now load-bearing context for any future runbook touching specialist-agent dispatch.** The `_INBOX.>` vs `agents.result.<id>` distinction (point-to-point reply vs fan-out event) should be cited in any new wire-evidence section or troubleshooting row.

**Related ADRs / decisions referenced in the runbook:** ADR-ARCH-001 (local-first inference), ADR-ARCH-008 (no-SQLite), DDR-021 (NATS-down soft-fail), TASK-DSR-001/003 (live KV watch + dispatch resolver wiring).

## Risks & Mitigations

- **§5.2 `_INBOX.>` filter wrong** — verify the correlation-id filter
  pattern against the wire log
  ([`wire-command-2026-05-08-postfix.log`](../../docs/runbooks/evidence/dddsw-demo/wire-command-2026-05-08-postfix.log))
  before committing.
- **R2 conditional drifts** — if TASK-CAPS-PROMPT-001 status changes
  between this PR's draft and merge, re-evaluate §4.2/§4.4/§6 wording the
  hour before merge; this is the only edit gated on sibling state.
- **Splitting edits across PRs** — undesirable; if forced, ship §5.2
  alone first (load-bearing), then bundle the remaining four.

## Out of Scope

- The R2 code fix — owned by sibling TASK-CAPS-PROMPT-001.
- DDR-021 amendment — owned by TASK-CAPS-PROMPT-001 (Step 5).
- Re-running the runbook end-to-end as a fix-verification gate — owned by
  TASK-CAPS-PROMPT-001 AC-009.

## See Also

- [`TASK-REV-9939`](../in_review/TASK-REV-9939-capabilities-prompt-block-missing-parameter-schema.md)
  — parent review, decision D5.
- [`TASK-CAPS-PROMPT-001`](TASK-CAPS-PROMPT-001-render-tool-parameter-schema.md)
  — sibling code fix; gates Edit 5.
- [`docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
  — the runbook under edit.
- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md)
  — surfacing context, evidence index.
