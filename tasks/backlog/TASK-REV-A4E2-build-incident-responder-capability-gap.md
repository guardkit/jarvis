---
id: TASK-REV-A4E2
title: "Review: Build-incident responder capability gap — no fleet agent owns runtime quality-gate failures during AutoBuild"
task_type: review
review_mode: decision
review_depth: standard
status: backlog
created: 2026-05-12T00:00:00Z
updated: 2026-05-12T00:00:00Z
priority: normal
tags: [architecture-review, agent-fleet, gap-analysis, autobuild, forge, capability-design, dddsw-post-demo]
complexity: 0
decision_required: true
surfaced_by:
  - source: test conversation with Jarvis (operator probe, 2026-05-12)
  - probe: "Of those agents, which one would you escalate to if a runtime quality gate failed during an autobuild turn? Walk me through how that handoff would work."
  - jarvis_answer_summary: |
      None of the registered agents (Architect, Product Owner, Forge, Ideation)
      own runtime quality-gate failures. Architect = post-mortem only,
      no runtime authority. Product Owner = scope/priority only, not runtime
      operations. Forge = the build itself, source of the failure signal,
      not the resolver. Ideation = can brainstorm workarounds, no integration
      with the build system to apply them. Jarvis self-identifies as the
      closest current responder (general-purpose, events land in its context)
      but flags this as a new-capability gap: a `forge_monitor` or
      `build_responder` that sits between pipeline events and specialist
      agents and decides the right path when things go wrong.
context_files:
  - src/jarvis/config/stub_capabilities.yaml             # Current four-agent fleet: architect-agent, product-owner-agent, ideation-agent, forge
  - src/jarvis/infrastructure/forge_notifications.py     # Pipeline-event subscriber; subjects, status enum, in-process landing zone
related_tasks:
  - TASK-REV-E73C  # analyse-autobuild-feat-j005-946d-timeout-failure — prior runtime failure post-mortem (no agent owned it then either)
  - TASK-REV-J6F1  # analyse-autobuild-feat-jarvis-006-fail-run-1 — same pattern: Jarvis post-mortems an autobuild failure manually
  - TASK-REV-J6F2  # analyse-autobuild-feat-jarvis-006-fail-run-2 — second instance of the same manual-post-mortem pattern
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Review — Build-incident responder capability gap

## Description

Decision-mode review of a fleet-design gap surfaced by an operator probe
question during a test conversation with Jarvis on 2026-05-12. The probe
asked which of the registered agents Jarvis would escalate to if a runtime
quality gate failed during an AutoBuild turn, and how that handoff would
work. Jarvis's answer — preserved verbatim in the `surfaced_by` block of
this task's frontmatter — concluded that **no agent in the current fleet is
designed for runtime quality-gate failures**, and proposed a new
capability (`forge_monitor` / `build_responder`) to fill the gap.

This review task triages whether that gap is real, whether the proposed
capability is the right shape to close it, and what the immediate
next-step task should be.

## Why this is worth reviewing now (not just deferring)

The pattern has already shipped three concrete instances of the gap:

1. **TASK-REV-E73C** — `analyse-autobuild-feat-j005-946d-timeout-failure`.
   Jarvis manually post-mortemed an AutoBuild timeout. No agent owned the
   live signal.
2. **TASK-REV-J6F1** — `analyse-autobuild-feat-jarvis-006-fail-run-1`. Same
   pattern: a human-driven review task created after the build failed,
   triaging in retrospect.
3. **TASK-REV-J6F2** — `analyse-autobuild-feat-jarvis-006-fail-run-2`. The
   *second* occurrence of the same pattern on the same feature — strong
   signal that the gap is recurring, not one-off.

Each instance was diagnosed by a human operator opening a `TASK-REV-…`
file after the fact. The runtime signal exists (the failure event reached
NATS), the consumer exists (Jarvis subscribes to the four pipeline
lifecycle subjects via `forge_notifications.py`), and the failure
classification logic exists (`status` enum already has `FAILED` and
`GATED`). What is missing is an **agent or capability that consumes the
signal and decides what to do next** — retry, stop-and-notify, route to a
specialist, or escalate to the human.

## Grounding in current plumbing (not speculation)

The test conversation's hypothetical (`pipeline.build-stage-failed.{feature_id}`)
is close but doesn't match the deployed subjects. The real plumbing
already in place:

- **Subscribed subjects** (Jarvis, lifecycle, ephemeral push consumer) per
  [`forge_notifications.py:381-428`](../../src/jarvis/infrastructure/forge_notifications.py):
  - `pipeline.build-started.>`
  - `pipeline.stage-complete.>`
  - `pipeline.build-complete.>`
  - `pipeline.build-failed.>`
- **Status enum** on stage-complete envelopes, per
  [`forge_notifications.py:148`](../../src/jarvis/infrastructure/forge_notifications.py):
  `PASSED | FAILED | GATED | SKIPPED`. Both `FAILED` and `GATED` are
  candidate quality-gate-failure indicators.
- **In-process landing zone** — the file's module docstring describes
  itself as "the in-process landing zone; the canonical NATS pipeline is
  upstream." Today nothing **acts** on `FAILED` / `GATED` beyond routing
  to the originating session's pending notifications.

So the runtime substrate to host a build-incident responder is **already
there**. The question this review answers is: **is the responder an
agent, a capability on an existing agent, a tool, or a non-agent runtime
subscriber?**

## Current fleet (from `stub_capabilities.yaml`)

Confirms the test conversation's enumeration:

| agent_id              | role           | trust_tier | latency_signal     | runtime-failure fit |
| --------------------- | -------------- | ---------- | ------------------ | ------------------- |
| `architect-agent`     | Architect      | specialist | 5-30 minutes       | Post-mortem only — too slow for runtime triage |
| `product-owner-agent` | Product Owner  | specialist | 30s-2min           | Scope/priority — not operational |
| `ideation-agent`      | Ideation       | specialist | 10-30s             | Brainstorming — no apply-mechanism |
| `forge`               | Build Pipeline | core       | 15-180min          | Source of the signal, not the resolver |

There is **no `core`-tier specialist whose latency budget and authority
match runtime triage**. Jarvis itself (orchestrator, not a registered
fleet member) is the de-facto responder today because the in-process
landing zone is in its address space.

## Review Scope (Context A)

- **Focus**: Capability design — is `forge_monitor` / `build_responder` an
  agent, a tool, or a Jarvis-internal subscriber callback? What
  signal-classification + routing logic should it own? Where does the
  human-in-the-loop boundary sit?
- **Trade-off priority**: Correct shape over speed. This is a design
  decision, not a demo-blocker. The DDD South West 2026-05-16 demo does
  not depend on this — `TASK-REV-CB48` is the demo-critical thread.
- **Specific concerns to surface**:
  1. **Agent vs. capability-on-Jarvis.** If the responder is a registered
     fleet member, it inherits the dispatch + heartbeat + KV-watch
     machinery and shows up in `list_available_capabilities`. If it's a
     Jarvis-internal subscriber, it bypasses dispatch but lives inside
     Jarvis's process and can't be replaced/upgraded independently. Both
     are defensible — pick one with stated rationale.
  2. **Trust tier.** If it's an agent, `core` is the right tier (same as
     `forge`). It would be the *only* core-tier responder besides Forge
     itself. Document the implication for the trust model.
  3. **Signal classification.** Distinguish transient failure (flaky
     test, infra blip, NATS hiccup) from real defect (assertion
     failure, AC mismatch, type error). The classification rule should
     be deterministic enough to test, not LLM-judgment alone.
  4. **Retry authority.** If the responder retries, what's the budget
     (count, wall-clock, cost)? Where does the budget come from —
     feature YAML, Jarvis config, hardcoded? What happens when the budget
     is exhausted?
  5. **Route-to-specialist logic.** The test conversation proposes:
     Architect for architectural contradiction, Product Owner for scope
     change, Ideation for unblocking ideas. Can the responder classify
     reliably enough to route, or does it always escalate to a human
     first? The three precedent post-mortems (E73C, J6F1, J6F2) are the
     test corpus.
  6. **Notification semantics.** When the responder stops a build and
     escalates, what does the human see? A `TASK-REV-…` file
     auto-generated by the responder, mirroring the manual pattern in
     E73C / J6F1 / J6F2? Or just a chat message? Or both?
  7. **Existing `TASK-REV-E73C`/`-J6F1`/`-J6F2` audit.** Re-read those
     three reviews and extract: (a) what *would* a build_responder have
     done at the moment of failure that the human didn't, (b) what
     *couldn't* it have done without human judgment, (c) what
     classification signal would have separated transient from real in
     each case.
  8. **Scope boundary against AutoBuild-internal retry.** AutoBuild
     (GuardKit) already has its own retry/escalation surface inside the
     build. The build_responder is meant to act on signals AutoBuild
     *emits as terminal* — not to duplicate AutoBuild's internal loop.
     Confirm the boundary so the responder doesn't get drawn into
     in-build retries.

## Required Decisions

1. **Is the gap real and worth a feature?** Three precedent reviews
   (E73C, J6F1, J6F2) say yes. Confirm or refute, with the boundary
   defined: a feature only if at least *one* of {retry budget owner,
   stop-and-notify owner, route-to-specialist owner} cannot live cleanly
   inside Jarvis's current orchestrator role.
2. **Shape of the capability.** Pick one:
   - **(A) Jarvis-internal subscriber callback.** Add a build-incident
     classifier inside the `forge_notifications` landing zone. No new
     agent. Lowest blast radius; tightest coupling to Jarvis.
   - **(B) Tool on Jarvis.** A `respond_to_build_failure(feature_id)`
     tool the supervisor invokes when a `FAILED` / `GATED`
     stage-complete envelope arrives. Mid blast radius; LLM-driven
     routing.
   - **(C) New fleet agent (`build-responder-agent`, core tier).** Full
     specialist with its own capability list (e.g. `triage_build_failure`,
     `retry_build`, `escalate_to_human`, `route_to_architect`). Highest
     blast radius; cleanest separation of concerns; replaceable.
   - **(D) Hybrid: A now, C later.** Start with the in-process callback
     (A) to capture signals, promote to (C) once the classification
     logic stabilises.
3. **Classification policy.** Define the transient-vs-real rule set
   (signal sources: stage label, stderr regex, exit code, retry count,
   stage-complete `status` enum value). Keep it deterministic and
   testable. LLM judgment, if used, is a *secondary* signal layered on
   the deterministic classification.
4. **Routing decision tree.** From a classified `real` failure, produce
   one of: `retry`, `stop-and-notify-human`, `route-to-architect`,
   `route-to-product-owner`, `route-to-ideation`. Spell out the
   conditions for each branch and the default (must be
   `stop-and-notify-human`, never silent retry on `real`).
5. **Test corpus.** Use E73C, J6F1, J6F2 as the regression scenarios.
   For each, document the *expected* responder behaviour at the moment
   of failure. If the responder design can't reproduce a sensible
   action for any of those three, the design isn't ready.
6. **Next-step task.** Output exactly one of:
   - A defer with rationale (the gap is real but doesn't merit a feature
     yet).
   - A feature YAML draft brief for `FEAT-JARVIS-BIR-001` (or similar)
     with the chosen shape from decision 2 and the scope boundary from
     concern 8.

## Acceptance Criteria

- [ ] Decision recorded on each of (1)–(6) above, with rationale.
- [ ] Test corpus audit completed: for each of TASK-REV-E73C, J6F1, J6F2,
      a short "what would the responder have done here?" paragraph.
- [ ] Capability shape selected from {A, B, C, D} with explicit
      trade-offs against the four alternatives.
- [ ] If a feature is recommended, a draft feature brief (one page
      max) attached as a follow-up artefact in `docs/` or
      `.guardkit/`, ready to feed `/feature-spec` /
      `/feature-plan`. If deferral is recommended, the rationale and
      the trigger condition that would re-open the question are
      recorded.
- [ ] No-regression on the existing pipeline subscriber: any responder
      design that touches `forge_notifications.py` preserves the four
      lifecycle subject filters (per FRR-F010Db, `pipeline.>` overlaps
      with forge-serve's queued subject and is rejected by JetStream).

## Out of Scope

- TASK-REV-CB48's DISPATCH-STUB-RESOLVER fix — separate demo-critical
  thread, unrelated to this gap.
- Heartbeat / liveness handling for the proposed responder agent —
  inherits from the existing `agent-registry` KV mechanics if shape
  (C) is chosen; no new design needed.
- AutoBuild-internal retry policy — owned by GuardKit, out of bounds.
- Re-architecting the four registered specialists' capabilities to
  cover runtime triage — already rejected as a design path by the
  latency signals in the fleet table above.
- The "no heartbeat" hallucination story (qwen36-workhorse model-side
  concern) — separate model/prompt thread.

## Phase Alignment

- Surfaced **after** TASK-REV-J6F2 (the second AutoBuild post-mortem on
  FEAT-JARVIS-006), which is the third instance of the recurring
  manual-post-mortem pattern.
- Independent of TASK-REV-CB48 (the demo-critical dispatch-stub
  resolver review) and TASK-REV-FFE4 (the closed FEAT-JARVIS-004
  prompt-block wiring review). Those are wiring-correctness reviews on
  shipped code; this is a fleet-design review on a missing capability.
- Should not pre-empt the 2026-05-16 DDD South West demo. Decision can
  land post-demo (week of 2026-05-18) without harm.

## Next Steps

1. Run `/task-review TASK-REV-A4E2` to execute the decision-mode review
   against the scope and decisions above.
2. Depending on the review outcome:
   - If `defer`: archive with rationale + trigger condition.
   - If `implement`: spawn the follow-up feature task (e.g.
     `FEAT-JARVIS-BIR-001` for build-incident responder) per the chosen
     shape (A / B / C / D).
3. Cross-link this review's decision back into TASK-REV-E73C / J6F1 /
   J6F2 as a "what would have happened with a build_responder in place"
   appendix on each, so the precedent corpus stays current.

## See Also

- [`src/jarvis/config/stub_capabilities.yaml`](../../src/jarvis/config/stub_capabilities.yaml)
  — current four-agent fleet definition.
- [`src/jarvis/infrastructure/forge_notifications.py`](../../src/jarvis/infrastructure/forge_notifications.py)
  — pipeline-event subscriber, the in-process landing zone where any
  shape-(A) responder would live.
- `TASK-REV-E73C`, `TASK-REV-J6F1`, `TASK-REV-J6F2` — three precedent
  manual post-mortems documenting the gap in action.
- `TASK-REV-CB48` — orthogonal demo-critical wiring review; this task
  does NOT depend on, block, or duplicate it.
