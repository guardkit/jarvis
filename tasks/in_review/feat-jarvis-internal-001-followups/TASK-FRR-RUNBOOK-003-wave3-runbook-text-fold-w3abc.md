---
complexity: 1
created: 2026-05-08 00:00:00+00:00
dependencies: []
discovered_on_machine: GB10 (promaxgb10-41b1)
discovered_on_date: 2026-05-08
discovered_via_correlation_id: 1506e6c4-cc6a-4591-8dc0-d9258b231b11
estimated_minutes: 25
feature_id: FEAT-JARVIS-INTERNAL-001-FRR
forward_references:
- TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B
id: TASK-FRR-RUNBOOK-003
implementation_mode: direct
parent_runbook_results: docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md
priority: low
status: in_review
tags:
- jarvis
- feat-jarvis-internal-001-followups
- runbook
- gap-fold
- wave-3
- documentation
- cosmetic
- post-followup-b-instrumentation
task_type: documentation
title: Wave-3 runbook text fold (W3-A/B/C) — Signature B framing, deadline qualifier, §6.2 prose tolerance
updated: 2026-05-08T00:00:00Z
wave: 3
edits_applied:
  w3a_signature_b_two_cycle_fingerprint:
    file: docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
    line: 677
    summary: "Added refined two-cycle fingerprint to §7 Signature B (cycle 1 parts_received=N>0; cycles 2+ parts_received=0 from drained-not-empty), citing forge HEAD e1eef81+ FOLLOWUP-B SSE instrumentation"
  w3b_deadline_not_firing_qualifier:
    file: docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
    line: 678
    summary: "Added deferred-ack deadline qualifier to §7 Signature B — explicit that the 5-min deadline path is gated on stream unreachability (TCP reset / 5xx / connection refused), NOT stream silence; reachable-but-translator-silent streams do not trigger build-failed"
  w3c_prose_tolerance:
    file: docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
    lines: [586, 588]
    summary: "Extended §6.2 prose-tolerance comment to document Target/Publish target/Publishing to label variance; only the subject string pipeline.build-queued.FEAT-43DE is load-bearing"
verification:
  forward_reference_preserved: true
  scope_discipline: "Three edits, one file, no other sections touched"
  out_of_scope_observed: "Pre-existing uncommitted modifications to runbook §2.0 area (pre-flight 1 + queue stats + §6.x symptom check) untouched; tracked separately by whoever filed those"
test_results:
  status: n/a
  notes: "Documentation-only direct-mode task — no automated tests; verification via re-read of edited sections in surrounding context"
---

# Wave-3 runbook text fold (W3-A / W3-B / W3-C)

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Wave:** 3 | **Type:** documentation | **Mode:** direct | **Complexity:** 1/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md) — "Wave-3 candidates (none blocking AC-12; observational)" table; recommended follow-up #2 ("wave-3 runbook fold")
**Forward references:** TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B (translator-vs-emission-discipline; not blocking this fold — see Notes)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-08, correlation_id `1506e6c4-cc6a-4591-8dc0-d9258b231b11` (jarvis HEAD `30e4ae4`, forge HEAD `e1eef81`)
**Sibling task:** [TASK-FRR-RUNBOOK-002](../../in_progress/feat-jarvis-internal-001-followups/TASK-FRR-RUNBOOK-002-gap-fold-runbook-for-post-pebr-wireup-topology.md) — wave-2 post-PEBR-WIREUP fold (currently in_progress); this task is the wave-3 cosmetic follow-up that lands once -002 ships.

## Description

Three observational, non-blocking text edits surfaced by the 2026-05-08 fresh-followup-b-instrumented walkthrough. All three are confined to [`docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](../../../docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md):

- **W3-A — §7 Signature B framing.** Update Signature B's description to reflect FOLLOWUP-B SSE instrumentation now in place at forge HEAD `e1eef81`+. The current text conflates two distinct expected states; the refined fingerprint is: **cycle 1** produces `parts_received=N>0` (the SSE stream is producing `event='values'` parts; the bridge translator just doesn't emit outbound envelopes), and **cycles 2+** produce `parts_received=0` because the original run is already drained — *not* because the original run was empty.
- **W3-B — §7 deadline qualifier.** The runbook's deadline-timer note says *"deadline timer will publish `build-failed` if the sidecar stays unreachable"*. Today's evidence (sidecar fully reachable, translator silent, no `build-failed` published after the 5-min deadline) shows the path is gated on stream **unreachability**, not stream **silence**. Add an "...if the SSE stream itself fails (not merely silent)" qualifier so the operator's expectation matches the actual contract.
- **W3-C — §6.2 prose-tolerance comment.** The supervisor in this run rendered `- **Target:**` rather than `- **Publish target:**`. The runbook already explicitly tolerates narration variance (*"the exact narration prose ... may vary turn-to-turn; the two bulleted lines above are the load-bearing evidence"*); this is a polish edit only — extend the prose-tolerance note with `Target` as a third example string so the next operator does not waste cycles confirming whether the variance is acceptable.

All three are flagged "Low / Cosmetic" in the source RESULTS table and **none gate AC-11 or AC-12**. The fold lands the runbook on the post-FOLLOWUP-B-instrumentation ground truth so the next walkthrough — whether it executes against the current state or against a future FOLLOWUP-B-resolved state — does not have to mentally re-translate stale framing.

## Headlines (the three edits and exact targets)

Pulled verbatim from the source RESULTS "Wave-3 candidates" table; line numbers are best-effort against jarvis HEAD `30e4ae4` and may shift slightly if TASK-FRR-RUNBOOK-002 lands first.

1. **W3-A: §7.1 Signature B description (around runbook line 668-676).** Current text reads: *"Signature B — FOLLOWUP-A landed, FOLLOWUP-B pending"* with a log signature ending at `httpx: HTTP Request: GET ... /stream?... HTTP/1.1 200 OK`. Refine to call out the two-cycle fingerprint: cycle 1 = stream open + `parts_received=N>0` + zero outbound envelopes; cycles 2+ = stream open + `parts_received=0` (original run drained, not empty). Cite forge HEAD `e1eef81`+ as the instrumentation source.
2. **W3-B: §7.1 deadline qualifier (around runbook line 651-654 in the "expected outcome" framing, and any other §7 location that references the deadline timer).** Find the *"deadline timer will publish `build-failed`"* phrasing (or equivalent) and add the qualifier *"...if the SSE stream itself fails (not merely silent)"*. The qualifier should be unambiguous to an operator reading cold: stream **fails** (TCP reset / 5xx / unreachable) → deadline publishes `build-failed`; stream **silent** (200 OK, parts produced but no translator-recognized transitions) → deadline does **not** publish `build-failed`.
3. **W3-C: §6.2 prose-tolerance comment (around runbook line 588).** The current sentence is *"The exact narration prose ... is generated by the supervisor's reasoner and may vary turn-to-turn; the **two bulleted lines above are the load-bearing evidence**."* Add `Target` as a documented example of acceptable variance for the `Publish target` line — either inline (e.g. *"...the supervisor may render the second line as either `- **Publish target:**` or `- **Target:**` — both acceptable"*) or as a parenthetical example. The §5.1 "Symptom check" / §6.2 evidence pattern should match either string.

## Acceptance Criteria

- [ ] **W3-A:** §7's Signature B description in `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` distinguishes cycle 1 (`parts_received=N>0`, stream producing parts, translator silent) from cycles 2+ (`parts_received=0`, original run drained), citing forge HEAD `e1eef81`+ as the source of the FOLLOWUP-B SSE instrumentation. The two states are no longer conflated.
- [ ] **W3-B:** Every §7 reference to the deferred-ack deadline timer publishing `build-failed` carries an explicit "...if the SSE stream itself fails (not merely silent)" qualifier (or equivalent unambiguous phrasing). An operator reading §7 cold can correctly predict that a reachable-but-translator-silent stream will **not** trigger the deadline failure path.
- [ ] **W3-C:** §6.2's prose-tolerance comment (the *"the two bulleted lines above are the load-bearing evidence"* paragraph at ~line 588) lists `Target` alongside `Publish target` as a documented narration variance, and the §6.2 match pattern accepts either string.
- [ ] No other section of the runbook is edited beyond these three folds (scope discipline — wave-2 topology folds are TASK-FRR-RUNBOOK-002's responsibility).
- [ ] The forward-reference to TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B in §7's "expected FAIL today" preamble is preserved (and updated to point at the refined Signature B language) — this fold polishes the wave-2 framing; it does **not** retire the FAIL-is-expected language until FOLLOWUP-B actually lands.
- [ ] If the runbook's command_history / changelog footer convention exists, the fold is recorded there with date `2026-05-08` and reference to this task ID and the source RESULTS file.

## Files Expected to Change

- `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — three edits (W3-A in §7, W3-B in §7, W3-C in §6.2).

No code changes. No test changes. No frontmatter / YAML / configuration touched.

## References

- **Source RESULTS file:** [docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md) — "Wave-3 candidates (none blocking AC-12; observational)" table (the W3-A/B/C row source); §"The deferred-ack-deadline path doesn't fire when the SSE stream is reachable" (W3-B forensic evidence); §6.2 row of the per-phase outcomes table (W3-C variance evidence).
- **Target file:** [docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Sibling in-progress fold:** [tasks/in_progress/feat-jarvis-internal-001-followups/TASK-FRR-RUNBOOK-002-gap-fold-runbook-for-post-pebr-wireup-topology.md](../../in_progress/feat-jarvis-internal-001-followups/TASK-FRR-RUNBOOK-002-gap-fold-runbook-for-post-pebr-wireup-topology.md) — wave-2 topology folds; land this task **after** -002 ships to avoid merge conflicts.
- **Wave-1 predecessor:** [tasks/completed/feat-jarvis-internal-001-followups/TASK-FRR-004-runbook-gap-fold-rewrite.md](../../completed/feat-jarvis-internal-001-followups/TASK-FRR-004-runbook-gap-fold-rewrite.md) — the original 13-gap fold (2026-05-01 baseline).
- **Folder index:** [tasks/backlog/feat-jarvis-internal-001-followups/README.md](README.md)

## Notes

- **Why this is `direct` mode, not `task-work` (TDD):** all three edits are prose-only changes to a single markdown file with no code, no tests, no frontmatter, and no behavioural impact. The TASK-FRR-RUNBOOK-002 precedent (also `direct`) and the original TASK-FRR-004 (also `direct` for the 13-gap fold) establish that runbook gap-folds are documentation-mode tasks.
- **Independence from FOLLOWUP-B resolution.** The source RESULTS file frames W3-A/B/C as a "wave-3 fold once FOLLOWUP-B's translator-vs-emission-discipline question is resolved." That framing is correct for the *broader* §7 re-anchor (which retires the FAIL-is-expected language and writes the success path). **This task is the narrower polish:** correcting the present-state Signature B fingerprint (W3-A) to match what HEAD `e1eef81`+ produces *today*, sharpening the deadline expectation (W3-B) to match the *current* contract, and extending the §6.2 tolerance (W3-C) to match observed variance. None of the three depend on FOLLOWUP-B *resolving* — they depend only on FOLLOWUP-B *being instrumented*, which has already happened. The broader §7 re-anchor remains a future-wave task and is **out of scope here**.
- **Ordering with TASK-FRR-RUNBOOK-002.** -002 is currently in_progress and edits the same runbook file (six wave-2 topology gap-folds). Land this task **after** -002 merges to avoid line-number drift and merge conflicts. If -002 stalls indefinitely, this task can be re-planned for parallel execution but the executor must rebase against -002's pending changes; do not duplicate any of -002's edits here.
- **Scope discipline.** The user's brief lists exactly three text edits. Do not opportunistically fold other observed gaps from the source RESULTS file (e.g. evidence-index polish, recommended-follow-ups numbering) — those go in their own task if they need to land. Three edits, one file, one commit.
- **Verification.** After editing, re-read the three edited sections cold (as a fresh operator would) and confirm the qualifications/examples land unambiguously — the W3-B qualifier especially has a subtle reachable-vs-silent distinction that is easy to garble.
