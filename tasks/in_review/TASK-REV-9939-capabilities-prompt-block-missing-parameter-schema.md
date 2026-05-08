---
id: TASK-REV-9939
title: "Review: CAPS-PROMPT-SCHEMA — CapabilityDescriptor.as_prompt_block() omits parameter schema, supervisor invents arg names"
task_type: review
review_mode: decision
review_depth: standard
status: review_complete
created: 2026-05-08T18:15:00Z
updated: 2026-05-08T19:30:00Z
review_results:
  mode: decision
  depth: standard
  score: 78
  findings_count: 6
  recommendations_count: 6
  decision: refactor
  report_path: .claude/reviews/TASK-REV-9939-review-report.md
  completed_at: 2026-05-08T19:30:00Z
  chosen_render_shape: R2  # Typed Args block
  go_no_go_date: 2026-05-13  # T-2 from dress rehearsal 2026-05-15
  fallbacks: [R1-feature-branch, explicit-args-operator-script]
priority: high
tags: [jarvis, capabilities-registry, prompt-engineering, dispatch, dddsw-2026-05-16, supervisor-prompt, runbook-docs]
complexity: 0
decision_required: true
demo_blocker_for: 2026-05-16
related_tasks:
  - TASK-REV-CB48  # Sibling — closed the dispatch resolver wiring gap; this task closes the next-hop arg-shape gap
surfaced_by:
  - phase: runbook-RUNBOOK-jarvis-architect-align-dddsw-demo
  - results: docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md
  - run_date: 2026-05-08
  - jarvis_head: 4c53e6c
  - specialist_agent_head: 82ce8a6
  - nats_core_head: 8f2c532  # tag v0.4.0
context_files:
  - src/jarvis/tools/capabilities.py        # Lines 135-164: as_prompt_block() — the gap
  - src/jarvis/agents/supervisor.py         # Lines 69, 80: where as_prompt_block() outputs are joined
  - src/jarvis/prompts/supervisor_prompt.py # Lines 18, 69-74: {available_capabilities} placeholder + tool-usage guidance
  - src/jarvis/tools/dispatch.py            # Lines 351-405: dispatch_by_capability docstring tells the supervisor to consult catalogue for schema
  - src/jarvis/infrastructure/lifecycle.py  # Line 738: where capability_registry feeds the prompt block
evidence_files:
  - docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md
  - docs/runbooks/evidence/dddsw-demo/trace-architect_align-31a2e8de-bug5-missing-args.json
  - docs/runbooks/evidence/dddsw-demo/trace-architect_align-232ec2e0-bug5-missing-args.json
  - docs/runbooks/evidence/dddsw-demo/trace-architect_explore-368f9149-bug5-fallback.json
  - docs/runbooks/evidence/dddsw-demo/trace-architect_align-8df345b4-success.json  # Workaround proof
  - docs/runbooks/evidence/dddsw-demo/wire-command-2026-05-08-postfix.log           # 4 envelopes; first 3 show invented arg shapes, 4th shows correct shape after explicit-prompt workaround
upstream_manifest_files:
  - /home/richardwoollcott/Projects/appmilla_github/specialist-agent/src/specialist_agent/adapters/manifest.py  # Lines 112-141: architect_align ToolCapability — source-of-truth for parameter schema
runbook_followups:
  - file: docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md
    sections:
      - "§0.5"   # Stub yaml introspection one-liner uses key 'agents:' but the file's top-level key is 'capabilities:' — silently returns empty. Trivial fix.
      - "§4.3"   # Lists judgment Literal as "needs_clarification" | "aligned" | "not_aligned". Actual schema (specialist_agent/generation/types.py:147) is Literal["aligned", "misaligned", "needs_clarification"]. Update to match.
      - "§5.2"   # Wire-tap on agents.result.<agent_id> is now misleading — Bug #1 fix routes replies via msg.reply inbox, so this subject is NOT used for request/reply traffic in the demo path. Either drop §5.2 or replace with an _INBOX.> tap.
      - "§0.1"   # Expected commit hash 'ca2ba6b' is several commits stale (top of log: 4c53e6c). Drop the specific hash since it'll continue drifting.
      - "§4.2 / §4.4 / §6"  # If as_prompt_block() is patched, the on-stage prompt no longer needs to over-engineer the args. Add a note that the supervisor will construct the payload from the schema rendered in the catalogue.
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review CAPS-PROMPT-SCHEMA — CapabilityDescriptor.as_prompt_block() omits parameter schema, supervisor invents arg names

## Description

Decision-mode review of a real, demo-relevant prompt-engineering gap discovered while
executing
[`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
on 2026-05-08 (post-fix walkthrough — the third run of the day, after specialist-agent
Bugs #1/#2/#3 fixes had landed). Phases 0-3 ran clean; Phase 4 round-1 fired three
dispatch envelopes that the architect rejected in 6ms each with *"Missing required
arguments for 'align': proposal, question"*. Three FRR-003 traces (`31a2e8de`,
`232ec2e0`, `368f9149`) all show the supervisor (`qwen36-workhorse`) inventing arg
names like `{adr_id, adr_summary, proposal_summary, context}` — none of which are in
the architect_align manifest's `required: ["context", "proposal", "question"]`. Phase
4 round-2 worked first try with a prompt that explicitly listed the three required arg
names (trace `8df345b4`, success in 5.3s).

The wire-level fixes (Bugs #1/#2/#3) closed the previous demo blockers; this gap is
the **next-hop bottleneck** — once the wire round-trip works, the supervisor's
payload-construction quality becomes the load-bearing surface. **Bug #5 is wholly
orthogonal to Bugs #1-#3.**

Full per-phase outcomes, code-level root cause, workaround proof, and runbook
follow-ups are captured in
[`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md).
This review task triages the fix path before the 2026-05-16 DDD South West demo.

## Root-Cause Hypothesis

The catalogue rendered into the supervisor's system prompt under
[`## Available Capabilities`](../../src/jarvis/prompts/supervisor_prompt.py#L69) is
constructed by joining each
[`CapabilityDescriptor.as_prompt_block()`](../../src/jarvis/tools/capabilities.py#L135-L164)
output. The current implementation renders only a header line, the agent description,
and a tool list of the form:

```
- {tool_name} ({risk_level}) — {description}
```

with **no parameter schema**. So for `architect_align` the supervisor sees:

```
- architect_align (read_only) — Align an existing design against the ADR set; emit an AlignmentJudgment.
```

The full
[`ToolCapability.parameters`](../../../specialist-agent/src/specialist_agent/adapters/manifest.py#L118-L137)
schema (`{type: object, properties: {context, proposal, question}, required: [...]}`)
is published in the live `agent-registry` KV bucket, watched by jarvis's
`KVCapabilityRegistry`, but the prompt-block render drops it. The supervisor has to
**guess the JSON shape** from the description string alone.

The `dispatch_by_capability` docstring at
[`tools/dispatch.py:381-385`](../../src/jarvis/tools/dispatch.py#L381) explicitly
tells the supervisor:

> `payload_json: JSON string matching the tool's parameters schema as declared in its
> ToolCapability.parameters. … The tool does NOT validate your payload against the
> schema — the specialist will.`

— but the schema isn't in the prompt for the supervisor to consult. The supervisor's
only options are (a) call `list_available_capabilities` (penalised by the prompt:
"Call `list_available_capabilities` at most once per session — the catalogue injected
above is authoritative for the rest of the conversation") or (b) guess.
`qwen36-workhorse` chose (b) consistently across three independent attempts.

This is a **catalogue-render fidelity gap**, not a wiring bug. The live KV has the
right data; the prompt block strips it on its way to the model.

## Review Scope (Context A)

- **Focus:** Prompt-block fidelity, supervisor payload-construction reliability, demo
  unblock path, and runbook docs hygiene.
- **Trade-off priority:** Time-critical correctness — DDD South West demo on
  2026-05-16; dress rehearsal 2026-05-15. The non-blocking workaround is "operator's
  prompt explicitly enumerates the args" — which dents the talk's "look how naturally
  it routes" demo claim. Real fix preferred if it fits the window.
- **Specific concerns to surface:**
  - Whether rendering `parameters.properties` keys + `parameters.required` per tool is
    sufficient, or whether full type/description strings are needed (latency/token
    trade-off).
  - Whether the render shape should match an existing convention (OpenAI tool schema?
    Anthropic XML-style? markdown table?). Pick a shape that reads cleanly to
    `qwen36-workhorse` in particular.
  - Whether to extend `as_prompt_block()` itself or add a sibling renderer + flag (so
    the existing snapshot tests don't churn unnecessarily).
  - Whether the prompt-block change should be paired with tightened prose in
    [`supervisor_prompt.py`](../../src/jarvis/prompts/supervisor_prompt.py) — e.g. an
    explicit "construct `payload_json` using the `Args:` block under each tool"
    instruction.
  - Whether `dispatch_by_capability`'s tool docstring should ALSO grow a stricter
    arg-construction reminder, given supervisor models vary in how diligently they
    consult the catalogue.
  - Test honesty — there's no existing snapshot/golden test on `as_prompt_block()`
    that asserts schema fidelity; the gap shipped uncaught. New regression test needs
    to fail today and pass after the fix.
  - Whether richer rendering risks blowing the supervisor's context budget on a fleet
    with N specialists × M tools each. Token cost projection is small for the current
    fleet (4 tools × 1 specialist) but worth a sanity check.

## Required Decisions

1. **Confirm runtime symptom in dev.** Reproduce in a controlled lab — boot jarvis
   chat against the dual-role stack with a naturally phrased prompt that names the
   architect by capability; assert that `qwen36-workhorse` constructs `args` whose
   keys do NOT match `{context, proposal, question}`. (Already confirmed three times
   in production-equivalent run on 2026-05-08; this step exists to set the regression
   test fixture.)

2. **Choose the prompt-block render shape.** Three candidates, ranked by cost/clarity:

   - **(R1) Minimal — required-keys-only line.** Append a single line per tool:
     ```
     - architect_align (read_only) — Align an existing design against the ADR set; emit an AlignmentJudgment.
         Args (required): context, proposal, question
     ```
     ~5 LOC change in `as_prompt_block()`. Lowest token cost. Loses parameter types
     and per-arg descriptions. May still leave the model guessing on string vs
     structured types.
   - **(R2) Typed — required-keys with type annotations.** Append:
     ```
         Args (required):
           - context (string): Background: existing architecture, constraints
           - proposal (string): The proposal or design to evaluate
           - question (string): Specific question to answer
     ```
     ~10 LOC change. Higher token cost (per-arg descriptions are author-controlled in
     the manifest, so they can be kept tight). Eliminates guessing on type and
     intent. **Recommended candidate for primary fix** — matches the `Args:` block
     convention the rest of the jarvis codebase already uses in `@tool` docstrings.
   - **(R3) JSON-Schema verbatim.** Render the raw `parameters` JSON Schema as a
     fenced code block. Highest fidelity, highest token cost, hardest to read. Useful
     for tools with optional args or nested objects; over-engineered for the
     architect's flat string schemas.

   - **(R2) is the canonical close.** Decision needed: ship R2 before 2026-05-15
     dress-rehearsal, or fall back to R1 for the demo and file R2 as immediate
     post-talk follow-up.

3. **Decide whether to deprecate `list_available_capabilities`'s "at most once per
   session" guidance** if the catalogue now carries the parameter schema. The current
   prose nudges the supervisor away from re-discovery, which made sense when the
   catalogue was thin; with R2 in place the catalogue *is* the source of truth and
   re-querying it is wasteful — keep the guidance, but make it land on the right
   reasoning ("the catalogue is authoritative" rather than "don't re-query").

4. **Test plumbing.** Ship two tests:
   - **Unit/snapshot test on `as_prompt_block()`** — golden output for the
     architect-agent descriptor including the new `Args (required):` block. Fails
     before the fix; passes after. Catches future regressions.
   - **Integration test (optional but recommended)** — drive the supervisor with a
     stubbed `qwen36-workhorse` (or a deterministic model harness) and a naturally
     phrased prompt; assert the constructed `payload_json` has keys matching the
     manifest's `required` list. This is the actual user-visible behaviour change;
     unit-only coverage is insufficient.

5. **Runbook follow-ups.** Five updates to
   [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
   (also recorded in the `runbook_followups` frontmatter above):

   - **§0.5 yaml introspection one-liner** — uses `d.get('agents', [])` but the file's
     top-level key is `capabilities:` — silently returns empty. Suggested fix:
     `d.get('capabilities', [])`. Trivial.
   - **§4.3 `judgment` Literal values** — lists `"needs_clarification" | "aligned" |
     "not_aligned"`; actual schema
     ([`specialist_agent/generation/types.py:147`](file:///home/richardwoollcott/Projects/appmilla_github/specialist-agent/src/specialist_agent/generation/types.py#L147))
     is `Literal["aligned", "misaligned", "needs_clarification"]`. The model returned
     `"misaligned"`, which is in-schema. Runbook should be aligned to the actual
     Literal — replace `"not_aligned"` with `"misaligned"`.
   - **§5.2 wire-tap on `agents.result.<agent_id>`** — now a misleading expectation.
     Bug #1 fix (specialist-agent commit `1979aa8`, nats-core v0.4.0
     `subscribe_with_reply`/`publish_raw`) routes replies via the `msg.reply` inbox
     subject, **not** `agents.result.<agent_id>`. The runbook's "live wire mirror"
     stage trick will leave the audience watching an empty pane. Either drop §5.2 or
     replace with an `_INBOX.>` tap (or with a directed log of jarvis's
     `nats_request_received` event). Add a footnote explaining the Bug #1 fix's
     reply-channel change so future runbook readers don't expect old behaviour.
   - **§0.1 expected commit `ca2ba6b`** — several commits stale (top-of-log moved to
     `4c53e6c` and continues drifting). Drop the specific hash; the runbook is
     otherwise version-agnostic.
   - **§4.2 / §4.4 / §6** — once R2 lands, the on-stage prompt no longer needs to
     enumerate the args (the demo gets back its "naturally phrased" claim). Add a
     note that the supervisor will construct the payload from the schema rendered in
     the catalogue, and remove any "explicit args" workaround language that was added
     for the post-fix run.

6. **Stub-yaml schema-fidelity question.** `src/jarvis/config/stub_capabilities.yaml`
   currently lists `tool_name`, `description`, and `risk_level` per tool — no
   parameter schema. If R2 ships, the NATS-down soft-fail path (DDR-021) will render
   tools with no `Args:` block, recreating the same supervisor-guessing failure mode
   under degraded operation. Decide whether to extend the stub yaml schema to carry
   `parameters` per tool (mirroring the live KV's shape), or accept the degradation
   as an explicit NATS-down trade-off. Out-of-scope for the primary fix but cleaner
   to decide in this context than later.

## Acceptance Criteria

- [ ] Decision recorded: which render shape (R1 vs R2 vs R3) for 2026-05-16, with
      rationale and explicit go/no-go date for fix-before-demo vs explicit-prompt-
      workaround-for-demo + fix-after.
- [ ] If R2 (or richer) chosen: implementation extends `CapabilityDescriptor.as_prompt_block()`
      to render parameter schema (at minimum `properties` keys + `required` list,
      with type/description per R2). Snapshot test asserts the new shape.
- [ ] Integration or end-to-end test added that drives the supervisor with a naturally
      phrased prompt against the catalogue-rendered tool list and asserts
      `dispatch_by_capability`'s constructed `payload_json` has keys matching the
      manifest `required` list (or at minimum doesn't get rejected with "Missing
      required arguments" when run against the real architect).
- [ ] FRR-003 trace audit: confirm the post-fix run produces a single trace with
      `outcome_type=success` and no `attempts` carrying `specialist_error: Missing
      required arguments`.
- [ ] Runbook §0.1, §0.5, §4.2/§4.4/§6, §4.3, and §5.2 updated per decision 5 above.
      §5.2 (wire-tap inbox-routing note) is the load-bearing one for the on-stage
      operator.
- [ ] Re-run the runbook end-to-end against the dual-role stack on the GB10 host with
      a naturally phrased prompt (no explicit args enumeration); Phase 4 lands an
      `agents.command.architect-agent.<corr>` envelope, the architect dispatches
      `architect_align → align`, and a real `AlignmentJudgment` lands in the chat
      REPL on the first attempt.
- [ ] DDR (or DDR amendment) recorded if the stub-yaml schema-fidelity question
      (decision 6) lands a yes; otherwise note as deferred follow-up.

## Out of Scope

- Re-litigating Bugs #1/#2/#3 (specialist-agent — closed by `1979aa8`/`08a95fe`/`4d80bd3`,
  verified in this run by the wire-level round-trip happening at all).
- The `nats-core/pyproject.toml` v0.4.0 bump (one-line edit applied during the run to
  unblock the docker rebuild — should be committed in the `nats-core` repo
  separately; not in this task's scope).
- Forge dispatch path (FEAT-JARVIS-INTERNAL-001) — `queue_build` does not use
  `dispatch_by_capability`, so unaffected.
- The supervisor's hallucination tendencies on cross-tool routing — separate
  model-engineering concern, not a catalogue-render concern. (The hallucination
  scare in run 1 of this walkthrough turned out to be real architect output —
  see RESULTS doc.)
- Replacing `qwen36-workhorse` with a different supervisor model — separate decision.
  R2 should make the gap survivable for any reasonably capable supervisor.

## Phase Alignment

This is an immediate post-merge follow-up to:

- `1979aa8` / `08a95fe` / `4d80bd3` (specialist-agent Bugs #1/#2/#3) +
  `82ce8a6` (nats-core>=0.4 floor bump) +
  `nats-core` `8f2c532` / tag `v0.4.0` (`subscribe_with_reply` + `publish_raw`) —
  the wire-level surface is now green; this is the next-hop arg-shape gap upstream
  of the architect's command router.
- [`TASK-REV-CB48`](TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md) closed the
  dispatch-resolver wiring gap (Live registry → dispatch resolver). This task closes
  the catalogue-render fidelity gap (Live registry parameters → supervisor prompt
  block). Together they make capability-name dispatch end-to-end usable from a
  naturally phrased operator prompt.

## Demo-Blocking Status

**No** for the strict "AlignmentJudgment renders" demo close criterion (the post-fix
walkthrough greens Phase 8 with the explicit-args workaround; trace `8df345b4`,
slide artefact `8df345b4-7b47-4214-8ae3-959aac5252e4.json`).

**Yes** for the talk's narrative claim of "watch the supervisor naturally route to
the architect." With R2 unfixed, the operator prompt has to enumerate the three
required args, which is over-engineered and audience-visible. Mitigations:

- **Best:** R2 lands and is verified by 2026-05-15 dress-rehearsal — natural prompt
  works first try.
- **Acceptable:** R1 patch for the demo (single `Args (required):` line); R2 filed
  as immediate post-talk follow-up.
- **Fallback:** explicit-args prompt template kept as the on-stage script; R2 filed
  as post-talk follow-up. The demo still lands; the narrative is slightly weaker.

## Next Steps

1. Run `/task-review TASK-REV-9939` to execute the decision-mode review.
2. Apply the chosen render shape in a follow-up implementation task
   (R2 → e.g. `TASK-CAPS-PROMPT-001`).
3. Re-run `RUNBOOK-jarvis-architect-align-dddsw-demo.md` end-to-end against the
   dual-role stack with a naturally phrased prompt to confirm Phase 4 closes green
   on the first attempt.
4. Apply the five runbook docs patches per decision 5.

## See Also

- [`RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md`](../../docs/runbooks/RESULTS-jarvis-architect-align-dddsw-demo-2026-05-08-postfix.md)
  — full per-phase outcomes, Bug #5 surfacing context, evidence index.
- [`TASK-REV-CB48`](TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md) — sibling
  review (dispatch-resolver wiring gap) closed by TASK-DSR-001/W2/W3; this task
  closes the next layer of the same prompt/catalogue fidelity story.
- [`docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md`](../../docs/runbooks/RUNBOOK-jarvis-architect-align-dddsw-demo.md)
  — the runbook whose §0.1/§0.5/§4.2/§4.3/§4.4/§5.2/§6 are misleading or stale and
  need updates per decision 5.
- Evidence: [`docs/runbooks/evidence/dddsw-demo/`](../../docs/runbooks/evidence/dddsw-demo/)
  — chat logs (run 1 reproduction + run 2 workaround success), four wire-command
  envelopes (3 misshape + 1 success), three Bug #5 traces + 1 success trace, and the
  slide artefact.
- `src/jarvis/tools/capabilities.py:135-164` — the function to extend.
- `src/jarvis/agents/supervisor.py:69-80` — where the rendered blocks are joined into
  `{available_capabilities}`.
- `specialist-agent/src/specialist_agent/adapters/manifest.py:112-141` —
  `architect_align` ToolCapability source-of-truth (the schema the supervisor needs
  to see).
