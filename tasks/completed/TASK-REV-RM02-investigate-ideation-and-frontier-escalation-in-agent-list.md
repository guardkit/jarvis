---
id: TASK-REV-RM02
title: "Audit specialist-agent list: 'Ideation' is an unbuilt stub and 'Frontier Escalation' is a tool mis-labelled as an agent"
task_type: review
review_mode: decision
review_depth: standard
status: completed
created: 2026-05-13T00:00:00Z
updated: 2026-05-13T00:00:00Z
completed: 2026-05-13T00:00:00Z
completed_location: tasks/completed/TASK-REV-RM02-investigate-ideation-and-frontier-escalation-in-agent-list.md
decisions:
  ideation: A1
  frontier_escalation: B2
priority: normal
tags: [jarvis, capabilities, stub-registry, supervisor-prompt, reachy, frontier-escalation, ideation, surfaced-by-conversation]
complexity: 0
decision_required: true
surfaced_by:
  - source: reachy-mini-conversation
    history: docs/history/reachy-run-1-history.md
    turn_lines: "57-66"
    run_date: 2026-05-13
related_tasks:
  - TASK-REV-CB48  # Dispatch stub-resolver wiring gap — same dual-registry (stub vs live) seam
  - TASK-REV-A4E2  # Build incident-responder capability gap — adjacent stub-registry triage
context_files:
  - src/jarvis/config/stub_capabilities.yaml         # Lines 301-345 (ideation-agent stub)
  - src/jarvis/prompts/supervisor_prompt.py          # Lines 69-74 ({available_capabilities} injection), 122-141 (Frontier Escalation section)
  - docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md  # Original stub-registry design (four canonical stubs)
  - tasks/completed/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-002-write-canonical-stub-capabilities-yaml.md  # Provenance of the four stubs
evidence_files:
  - docs/history/reachy-run-1-history.md             # Line 64 (Jarvis listing), line 66 (Reachy LLM mis-labelling)
test_results:
  status: passed
  coverage: null
  last_run: 2026-05-13T00:00:00Z
  notes: "tests/test_prompts.py 85/85 passed; tests/test_capability_descriptor_prompt_block.py 7/7 passed"
---

# Task: Audit specialist-agent list — 'Ideation' is an unbuilt stub, 'Frontier Escalation' is a tool

## Description

During the 2026-05-13 Reachy Mini conversation (recorded in
[`docs/history/reachy-run-1-history.md`](../../docs/history/reachy-run-1-history.md)),
Rich asked the scholar adapter to relay Jarvis's available agents. Two
entries in the spoken summary were unexpected:

- **"Ideation"** — listed by Jarvis at history line 64.
- **"Frontier Escalation"** — listed by the Reachy realtime LLM at history
  line 66 ("the specialist agents are Architect, Product Owner, GCSE Tutor,
  Ideation, Forge, and Frontier Escalation for cloud models").

This task triages whether each is real, intentional, or a hardcoded leftover.

## Pre-Triaged Findings

### 'Ideation' — real stub, no live agent

[`src/jarvis/config/stub_capabilities.yaml:301-345`](../../src/jarvis/config/stub_capabilities.yaml#L301-L345)
declares an `ideation-agent` capability with two stub tools
(`generate_alternatives`, `steelman`). It was added deliberately in
FEAT-JARVIS-002 as one of four canonical stubs (architect, product-owner,
ideation, forge) — see
[`docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md`](../../docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md)
and
[`tasks/completed/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-002-write-canonical-stub-capabilities-yaml.md`](../../tasks/completed/feat-jarvis-002-core-tools-and-dispatch/TASK-J002-002-write-canonical-stub-capabilities-yaml.md).
However, no live fleet ideation specialist has been built — calling it via
`dispatch_by_capability` would resurface the same
`unresolved` failure mode that
[TASK-REV-CB48](./TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md)
documents for `architect-agent`.

The descriptor is presented to the user as an available capability via the
`{available_capabilities}` placeholder injected at
[`src/jarvis/prompts/supervisor_prompt.py:69-74`](../../src/jarvis/prompts/supervisor_prompt.py#L69-L74),
so the supervisor truthfully relayed it. The mismatch is that "advertised in
the catalogue" ≠ "actually dispatchable end-to-end".

### 'Frontier Escalation' — not an agent at all

There is no `frontier-escalation` agent. The string "Frontier Escalation"
appears in [`src/jarvis/prompts/supervisor_prompt.py:122-141`](../../src/jarvis/prompts/supervisor_prompt.py#L122-L141)
as the **section heading** above the `escalate_to_frontier` *tool*
description. Jarvis's actual response at history line 64 lists Ideation but
*does not* mention Frontier Escalation as an agent — the addition of
"Frontier Escalation for cloud models" in the spoken summary at line 66 is
the Reachy realtime LLM rephrasing the response and conflating the tool
with the specialist roster.

So:
- Ideation = real catalogue entry, no live dispatchable agent behind it.
- Frontier Escalation = a tool (`escalate_to_frontier`), mis-narrated as an
  agent by the consumer LLM, not by Jarvis.

## Decision Options

For 'Ideation':
- **A1 — Leave as-is.** The stub serves its FEAT-JARVIS-002 design role
  (four canonical capability shapes). Document elsewhere that stub-only
  capabilities exist and dispatching to them may fail unresolved.
- **A2 — Annotate the stub.** Add a `trust_tier: stub-only` or
  `live_agent: false` flag to the YAML and have the prompt block render
  "(stub — not yet built)" so the supervisor can prefer real agents when
  options overlap.
- **A3 — Remove the ideation stub from the prompt block** (still load it
  in tests) so the supervisor stops advertising it to attended consumers
  until a real specialist exists.
- **A4 — Promote ideation to a real specialist** (out of scope for this
  task; would land as its own feature).

For 'Frontier Escalation':
- **B1 — Accept the mis-narration as a downstream LLM artefact** and take
  no action in Jarvis.
- **B2 — Tighten the supervisor prompt** so the section heading at
  [`supervisor_prompt.py:122`](../../src/jarvis/prompts/supervisor_prompt.py#L122)
  more obviously frames `escalate_to_frontier` as a tool, not a
  specialist (e.g. "Frontier Escalation Tool"), reducing the surface for
  consumer-LLM mis-labelling.
- **B3 — Add explicit guidance in the prompt's roster section** that
  `escalate_to_frontier` is a tool, not an agent, and should not be
  enumerated alongside specialists in any catalogue answer.

## Decisions (2026-05-13)

### Ideation → **A1 — Leave as-is**

**Justification.** The `ideation-agent` stub serves its FEAT-JARVIS-002
design role (one of the four canonical capability shapes — see
[`docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md`](../../docs/design/FEAT-JARVIS-002/models/DM-stub-registry.md)).
The "advertised but unresolved" failure mode is **the same gap already
tracked under [TASK-REV-CB48](../backlog/TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md)**
for `architect-agent`; fixing the dispatch-stub-resolver wiring there
will lift Ideation too. Adding a `live_agent: false` flag (option A2)
here would create a second, narrower seam to revisit when CB48 lands,
and the DDDSW demo on 2026-05-16 is three days out — minimising surface
churn this week is the load-bearing constraint. Re-evaluate after CB48.

### Frontier Escalation → **B2 — Rename section heading to "Frontier Escalation Tool"**

**Justification.** The mis-narration at history line 66 originated
*downstream* in the Reachy realtime LLM (Jarvis's own response at line
64 correctly omits "Frontier Escalation" from the specialist roster),
so option B1 (no action) is defensible. However, B2 is a one-word prompt
change that directly addresses the surface that enabled the conflation:
a `## Frontier Escalation` heading sitting next to `## Subagent Routing`
reads ambiguously when summarised. Renaming to `## Frontier Escalation
Tool` (now at
[`src/jarvis/prompts/supervisor_prompt.py:122`](../../src/jarvis/prompts/supervisor_prompt.py#L122))
makes the tool-vs-agent disambiguation explicit without adding prose
weight (B3 was the more verbose alternative). Existing
`TestJ003014FrontierEscalationSection` assertions are substring checks
on `"## Frontier Escalation"` and remain green; a new
`TestRevRm02FrontierEscalationToolHeading` class locks in the renamed
heading and forbids the bare-heading regression.

## Acceptance Criteria

- [x] Confirm the two pre-triaged findings by re-reading the history file
      and the cited source lines.
      → Confirmed against
      [`stub_capabilities.yaml:301-345`](../../src/jarvis/config/stub_capabilities.yaml#L301-L345),
      [`supervisor_prompt.py:69-74, 122`](../../src/jarvis/prompts/supervisor_prompt.py#L122),
      and
      [`docs/history/reachy-run-1-history.md:64,66`](../../docs/history/reachy-run-1-history.md).
- [x] Pick one Ideation option (A1 / A2 / A3 / A4) with a written
      justification.
      → **A1** (see Decisions §Ideation above).
- [x] Pick one Frontier Escalation option (B1 / B2 / B3) with a written
      justification.
      → **B2** (see Decisions §Frontier Escalation above).
- [x] If the choice mutates `stub_capabilities.yaml` or the supervisor
      prompt, add or update tests under `tests/test_stub_capabilities.py`
      and `tests/test_supervisor_prompt.py` (or the closest equivalents)
      so the new contract is locked in.
      → Added `TestRevRm02FrontierEscalationToolHeading` in
      [`tests/test_prompts.py`](../../tests/test_prompts.py) with two
      assertions: the renamed heading is present, and the bare
      `## Frontier Escalation\n` heading is absent (regression guard).
- [x] If the choice mutates the prompt rendering, run the
      TASK-J003-020-style regression test (no retired roster strings) and
      confirm no new false positives.
      → `TestJ003014RetiredRosterAbsent.test_no_retired_roster_names`
      and `test_no_cloud_fallback_for_quick_local_language` both green
      under the renamed heading (full 85/85 in `tests/test_prompts.py`).

## Test Requirements

- [x] Snapshot test on the rendered `{available_capabilities}` block if
      A2 or A3 is adopted.
      → **Not applicable** (A1 chosen — no rendering change for the
      Ideation block).
- [x] Prompt-content assertion test if B2 or B3 is adopted.
      → Added `TestRevRm02FrontierEscalationToolHeading` (two tests).

## Implementation Notes

- Any change to `stub_capabilities.yaml` should be cross-checked against
  [TASK-REV-CB48](./TASK-REV-CB48-dispatch-stub-resolver-wiring-gap.md) —
  the dispatch stub-resolver gap is the load-bearing piece of context for
  why "advertised but unresolved" is currently possible.
- The DDDSW demo on 2026-05-16 should not be destabilised by churn in
  this area. If any option touches the prompt, gate it behind the existing
  pre-flight stub↔live alignment check rather than a hot-swap during
  demo week.

## Test Execution Log

**2026-05-13 — /task-work TASK-REV-RM02 (standard mode, decision task)**

- `.venv/bin/python -m pytest tests/test_prompts.py -x -q` → **85 passed**
  (includes new `TestRevRm02FrontierEscalationToolHeading` class with two
  assertions on the renamed heading and the regression guard against the
  bare heading).
- `.venv/bin/python -m pytest tests/test_capability_descriptor_prompt_block.py -x -q`
  → **7 passed** (sanity-check that the `{available_capabilities}`
  rendering — which still advertises the ideation stub under decision
  A1 — is unaffected by the supervisor-prompt heading rename).

Code changes:

- `src/jarvis/prompts/supervisor_prompt.py:122` — `## Frontier
  Escalation` → `## Frontier Escalation Tool` (one-line rename,
  consistent with decision B2).
- `tests/test_prompts.py` (tail) — new
  `TestRevRm02FrontierEscalationToolHeading` class with two assertions.

No changes to `stub_capabilities.yaml` (decision A1 — leave as-is and
re-evaluate after TASK-REV-CB48 lands).
