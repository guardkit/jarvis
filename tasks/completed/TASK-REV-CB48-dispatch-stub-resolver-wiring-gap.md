---
id: TASK-REV-CB48
title: "Review: DISPATCH-STUB-RESOLVER — live registry not wired into dispatch_by_capability resolver"
task_type: review
review_mode: decision
review_depth: standard
status: review_complete
created: 2026-05-08T00:00:00Z
updated: 2026-05-08T00:00:00Z
review_results:
  mode: decision
  depth: standard
  score: 78
  findings_count: 6
  recommendations_count: 5
  decision: hybrid-w1-then-w2
  recommended_option: hybrid
  report_path: .claude/reviews/TASK-REV-CB48-review-report.md
  completed_at: 2026-05-08T00:00:00Z
priority: critical
tags: [jarvis, dispatch, capabilities-registry, wiring-gap, demo-blocker, dddsw-2026-05-16, latent-bug]
complexity: 0
decision_required: true
demo_blocker_for: 2026-05-16
related_tasks:
  - TASK-REV-FFE4  # Structurally identical FEAT-JARVIS-004 wiring review (same shape: code shipped, one wiring step missing)
surfaced_by:
  - phase: runbook-RUNBOOK-jarvis-architect-align-dddsw-demo
  - results: docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md
  - run_date: 2026-05-08
  - jarvis_head: ca2ba6b
  - specialist_agent_head: 7345e33
context_files:
  - src/jarvis/tools/__init__.py            # Line 252-263: assemble_tool_list wiring (live → catalogue, stub → dispatch)
  - src/jarvis/tools/dispatch.py            # Line 438: resolver reads _dispatch._capability_registry
  - src/jarvis/infrastructure/lifecycle.py  # Lines 547, 628, 695-704, 714-723: stub vs live registry construction + plumbing
  - src/jarvis/infrastructure/capabilities_registry.py  # LiveCapabilitiesRegistry, KVCapabilityRegistry
  - src/jarvis/config/stub_capabilities.yaml             # Stub list (architect-agent: run_architecture_session, draft_adr only)
evidence_files:
  - docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md
  - docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/chat-attempt3-intent-pattern-arg-dropped.log
  - docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/trace-attempt2-becfa233.json
  - docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/trace-attempt2-c428dc05.json
  - docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/trace-attempt3-d8525237.json
runbook_followups:
  - file: docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md
    sections:
      - "§2.5 Catalogue-vs-stub note"  # claim that live KV watch replaces stub is half-correct
      - "§6 failure modes"             # `unresolved` row's fix advice (restart jarvis chat) is incorrect
      - "§0 pre-flight"                # add stub↔live alignment gate until resolver gap closes
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review DISPATCH-STUB-RESOLVER — live registry not wired into dispatch_by_capability resolver

## Description

Decision-mode review of a real, demo-blocking architectural gap discovered while
executing
[`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
on 2026-05-08. Phases 0–3 ran clean; Phase 4 was blocked across three independent
dispatch attempts with `ERROR: unresolved — no capability matches tool_name=architect_align`.
Wire taps captured **zero envelopes** on `agents.command.architect-agent.>` for the
duration of all three attempts; three FRR-003 routing-history offload traces all
show `outcome_type: "unresolved"` with empty `attempts` and `visited` arrays — the
dispatch never reached JetStream because the resolver returned `None`.

Full per-phase outcomes, code-level root cause, three workarounds, and runbook
follow-ups are captured in
[`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md).
This review task triages the fix path before the 2026-05-16 DDD South West demo.

## Root-Cause Hypothesis

The boot path establishes **two separate capability registries** that
[`assemble_tool_list`](../../src/jarvis/tools/__init__.py) plumbs to **different
consumers**:

1. **Stub list** — loaded at
   [`lifecycle.py:547`](../../src/jarvis/infrastructure/lifecycle.py) from
   `src/jarvis/config/stub_capabilities.yaml` into
   `capability_registry: list[CapabilityDescriptor]`.
2. **Live registry** —
   `LiveCapabilitiesRegistry.create(nats_client)` at
   [`lifecycle.py:628`](../../src/jarvis/infrastructure/lifecycle.py), which warms a
   30s-TTL cache via an immediate `refresh()` and opens an async `watchall()` on the
   `agent-registry` KV bucket. Bound to a **separate** local
   `capabilities_registry: CapabilitiesRegistry`.

Inside [`assemble_tool_list`](../../src/jarvis/tools/__init__.py) at lines 252-263:

```python
# Live registry → catalogue tools (list_available_capabilities,
# capabilities_refresh, capabilities_subscribe_updates)
_capabilities._capability_registry = capabilities_registry          # ← LIVE

# Stub list snapshot → dispatch tool's resolver
_dispatch._capability_registry = list(capability_registry)          # ← STUB
```

The dispatch resolver at
[`tools/dispatch.py:438`](../../src/jarvis/tools/dispatch.py) reads from
`_dispatch._capability_registry` only:

```python
registry_snapshot = list(_capability_registry)                      # ← STUB
…
agent_id = _resolve_agent_id(tool_name, intent_pattern, registry_snapshot, …)
```

`stub_capabilities.yaml` lists architect-agent's tools as `run_architecture_session`
and `draft_adr` only. The live container publishes `architect_greenfield`,
`architect_align`, `architect_explore`, `architect_feasibility`. The supervisor's
prompt block correctly shows `architect_align` (live registry feeds the prompt-block
injection via the catalogue tools) and the supervisor dispatches with
`tool_name="architect_align"` — but the resolver iterates the stub list, finds no
match, has no `intent_pattern` to fall back on (qwen36-workhorse drops the explicit
arg), and returns `None` → callers see `ERROR: unresolved`.

This is the **same shape as Gap PEBR-WIREUP** from
`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md` and
[`TASK-REV-FFE4`](../completed/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md):
underlying machinery (Live registry) fully implemented, wireup function accepts both
registries as parameters, exactly one wiring step missing at the integration boundary.
Caught only when the runbook walked the full path.

The runbook §2.5 "Catalogue-vs-stub note" claim that live KV watch "replaces the stub
entries" is **half-correct** — it hydrates the prompt-block, but NOT the dispatch
resolver. The runbook author did not test the resolver path against the live KV.

## Review Scope (Context A)

- **Focus**: Wiring correctness, runtime fix selection, demo unblock path.
- **Trade-off priority**: Time-critical correctness — DDD South West demo on
  2026-05-16; dress rehearsal 2026-05-15. Real fix preferred over workaround if it
  fits the window; workaround acceptable if not.
- **Specific concerns to surface**:
  - Whether the Live registry's `snapshot()` returns the right shape to drop directly
    into `_dispatch._capability_registry` (list of `CapabilityDescriptor`).
  - Whether the StubCapabilitiesRegistry wrapper at
    [`lifecycle.py:637`](../../src/jarvis/infrastructure/lifecycle.py) (DDR-021
    NATS-down soft-fail path) `.snapshot()` is equivalent to the current
    `list(capability_registry)` behaviour — required for graceful degradation.
  - Whether the watch-driven refresh callback (`subscribe_updates`) needs threading /
    locking, given `_dispatch._capability_registry` is read concurrently by the
    resolver.
  - Test honesty — the existing FEAT-JARVIS-004 test corpus did not catch this; needs
    audit (per recommended-followup #1 in the RESULTS doc).
  - Whether the stub yaml format should be deprecated entirely once this closes (the
    stub serves two purposes today: DDR-021 soft-fail + dispatch resolver source-of-
    truth; closing this gap eliminates the second purpose).

## Required Decisions

1. **Confirm runtime symptom in dev.** Reproduce in a controlled lab — boot jarvis
   chat against the dual-role stack with `architect_align` published in live KV but
   absent from `stub_capabilities.yaml`. Confirm `dispatch_by_capability(tool_name=
   "architect_align", …)` returns `ERROR: unresolved`. (Already confirmed three times
   in production-equivalent run on 2026-05-08; this step exists to set the regression
   test fixture.)

2. **Choose fix approach for 2026-05-16 demo unblock.** Three workarounds and one
   real fix, ranked by RESULTS doc:

   - **(W1) Patch `stub_capabilities.yaml`** — add `architect_align`,
     `architect_greenfield`, `architect_explore`, `architect_feasibility` to
     architect-agent's `capability_list` to mirror the live KV. One-edit, reversible,
     demo-safe. Side-effect: masks the gap in any future runbook that doesn't hit
     this exact stub.
   - **(W2) Real fix in `tools/__init__.py:263`** — change the snapshot from
     `list(capability_registry)` (stub list) to `list(capabilities_registry.snapshot())`
     (live registry view), plus a `subscribe_updates(...)` callback that refreshes on
     every KV update. Bigger blast radius (unit + integration tests required) but
     actually closes the gap. Indicative shape:

     ```python
     _dispatch._capability_registry = list(capabilities_registry.snapshot())
     def _refresh_dispatch_registry() -> None:
         _dispatch._capability_registry = list(capabilities_registry.snapshot())
     capabilities_registry.subscribe_updates(_refresh_dispatch_registry)
     ```

     Plus a graceful-degradation check: if `capabilities_registry` is the
     StubCapabilitiesRegistry wrapper (DDR-021 NATS-down path,
     [`lifecycle.py:637/639`](../../src/jarvis/infrastructure/lifecycle.py)),
     `snapshot()` should still return stub-derived descriptors so dispatch keeps
     working in NATS-down mode.

   - **(W3) `intent_pattern` resolver fallback** — instruct the supervisor to call
     `dispatch_by_capability(tool_name="architect_align", intent_pattern="Architect", …)`
     so the resolver hits the role-based fallback at
     [`dispatch.py:249-254`](../../src/jarvis/tools/dispatch.py). **Empirically
     unreliable** with `qwen36-workhorse` as supervisor — verified 2026-05-08
     (attempt 3): the supervisor LLM drops the `intent_pattern` arg from the tool
     call. A larger or differently-tuned supervisor model might preserve it. Not
     recommended as primary path.

   - **(W2) is the canonical close.** Decision needed: ship W2 before 2026-05-15
     dress-rehearsal, or fall back to W1 for the demo and file W2 as immediate
     post-talk follow-up.

3. **Test plumbing.** If W2 is taken, ship an integration test that drives
   `assemble_tool_list` with a Live registry pre-loaded with a tool name not in the
   stub yaml, then asserts the dispatch resolver finds it (or at minimum doesn't
   return `ERROR: unresolved` for that tool). Audit FEAT-JARVIS-004 test corpus to
   confirm whether any existing test exercises this exact path — if it does,
   understand why the gap shipped through; if not, that is the test gap to close.

4. **Runbook follow-ups.** Three updates to
   [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md):
   - **§2.5 "Catalogue-vs-stub note"** — rewrite. Current text claims live KV watch
     "replaces the stub entries"; that's true for the prompt-block injection but
     FALSE for the dispatch resolver. The note misleads operators into expecting
     Phase 4 to work when DISPATCH-STUB-RESOLVER is open.
   - **§6 "failure modes"** — update the `ERROR: unresolved` row. Restarting jarvis
     chat doesn't help; the actual cause is the stub yaml not listing the tool name.
     Reference Gap DISPATCH-STUB-RESOLVER (this task).
   - **§0 pre-flight** — add a new gate: "Confirm stub yaml ↔ live KV alignment for
     the demo's tool name." Until W2 ships, this is the single guard that saves a
     demo.

5. **Stub-yaml deprecation question.** Once W2 ships, the stub yaml's only remaining
   purpose is the DDR-021 NATS-down soft-fail. Decide whether to keep it, deprecate
   it, or rebuild it as a NATS-down-only safety-net file. Out-of-scope for this
   review's primary fix but the decision is cleaner to make in this context than
   later.

## Acceptance Criteria

- [ ] Decision recorded: which fix path (W1 vs W2 vs hybrid) for 2026-05-16, with
      rationale and explicit go/no-go date for W2-before-demo vs W1-for-demo+W2-after.
- [ ] If W2 chosen: implementation lands the wiring fix in `tools/__init__.py`,
      including the watch-driven refresh callback and the graceful-degradation path
      for StubCapabilitiesRegistry (DDR-021 fallback preserved).
- [ ] Integration test added that drives `assemble_tool_list` with a Live registry
      pre-loaded with a tool name not in the stub yaml; asserts the dispatch resolver
      resolves it (or at minimum returns something other than `ERROR: unresolved`).
- [ ] FEAT-JARVIS-004 test corpus audit: documented finding on whether the gap was
      exercised by any existing test, and if so, why it didn't fire.
- [ ] Runbook §2.5, §6, and §0 updated per decision 4 above. §2.5 rewrite is the
      load-bearing one.
- [ ] Re-run the runbook end-to-end against the dual-role stack on the GB10 host;
      Phase 4 lands a real `agents.command.architect-agent.<corr>` envelope, the
      architect container's command router maps `architect_align → align`, and a
      real `AlignmentJudgment` lands in the chat REPL.
- [ ] DDR (or DDR amendment) recorded if the stub-yaml deprecation question (decision
      5) lands a yes; otherwise note as deferred follow-up.

## Out of Scope

- Forge dispatch path (FEAT-JARVIS-INTERNAL-001) — `queue_build` does not use
  `dispatch_by_capability` (dedicated tool, separate registry-free path), so
  unaffected by this fix.
- The supervisor's hallucinated "no heartbeat" narrative interpretation of the
  unresolved error — that's a model-side prose concern, not a wiring concern.
  `qwen36-workhorse` model selection / prompt engineering is a separate
  conversation.
- The supervisor's failure to honour explicit `intent_pattern` instruction (W3
  reliability) — also a model-side concern, separate from the resolver wiring.
- Any FEAT-JARVIS-005 tool surface changes — separate registry-free path.

## Phase Alignment

This is an immediate post-merge follow-up to:

- `dcaa8eb` (lifecycle subscriber widening) and `6071fe0` (TASK-FRR-F010Db disjoint
  filter) — the surrounding plumbing is green; this is the missing wiring step
  upstream of the dispatch resolver.
- [`TASK-REV-FFE4`](../completed/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md)
  closed the prompt-block-side wiring gap (Live registry → catalogue tools); this
  task closes the dispatch-side wiring gap (Live registry → dispatch resolver).
  Together they complete the FEAT-JARVIS-004 Live registry integration.

## Demo-Blocking Status

**YES** for DDD South West 2026-05-16. Mitigation paths:

- **Best:** W2 lands and is verified by 2026-05-15 dress-rehearsal.
- **Acceptable:** W1 patch applied for the demo; W2 filed as immediate post-talk
  follow-up.
- **Not viable:** W3 alone (supervisor drops the arg).

## Next Steps

1. Run `/task-review TASK-REV-CB48` to execute the decision-mode review.
2. Apply the chosen fix path in a follow-up implementation task
   (W2 → e.g. `TASK-DSR-FIX-001`; or W1 → e.g. `TASK-DSR-W1-001`).
3. Re-run `RUNBOOK-jarvis-architect-align-dddsw-demo.md` end-to-end against the
   dual-role stack to confirm Phase 4 closes green and a real `AlignmentJudgment`
   lands.
4. Update the runbook's §2.5 / §6 / §0 sections per decision 4.

## See Also

- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08.md)
  — full per-phase outcomes, code-level root cause, evidence index.
- [`TASK-REV-FFE4`](../completed/TASK-REV-FFE4-feat-j004-capabilities-registry-wiring-inconsistency.md)
  — structurally identical FEAT-JARVIS-004 wiring review (same shape, prompt-block
  side).
- `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md` — Gap PEBR-WIREUP
  (structurally identical forge-side wiring gap discovered same day).
- [`docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
  — the runbook whose §2.5 / §6 / §0 are misleading and need updates.
- Evidence: [`docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/`](../../docs/runbooks/evidence/dddsw-demo-2026-05-08-blocked/)
  — chat log + three FRR-003 traces.
