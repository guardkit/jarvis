---
id: TASK-DSR-005
title: "W1' — Patch stub_capabilities.yaml to mirror live KV gcse-tutor tools"
task_type: bugfix
status: backlog
created: 2026-05-13T11:00:00Z
updated: 2026-05-13T11:00:00Z
priority: critical
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 20
parent_review: TASK-REV-CB48
feature_id: FEAT-DSR
demo_blocker_for: 2026-05-16
depends_on: []
relates_to:
  - TASK-DSR-001  # W1 — established the pattern for architect-agent
  - TASK-DSR-003  # W2 — wired live KV into the dispatch RESOLVER (but not the supervisor prompt)
  - study-tutor@TASK-LCA-007  # parallel diagnosis that turned out to be incorrect — descriptions improved but don't reach the supervisor prompt
tags: [jarvis, dispatch, capabilities-registry, demo-unblock, w1-insurance, stub-yaml, gcse-tutor]
context_files:
  - src/jarvis/config/stub_capabilities.yaml
  - src/jarvis/infrastructure/lifecycle.py  # line 738 — available_capabilities=capability_registry (stub list, not live)
  - src/jarvis/agents/supervisor.py  # line 289 — _render_available_capabilities consumes the stub list
  - .claude/reviews/TASK-REV-CB48-review-report.md  # original FEAT-DSR root-cause review
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: W1' — Patch stub_capabilities.yaml to mirror live KV gcse-tutor tools

## Provenance

Surfaced during the multi-specialist OpenWebUI demo verification **run-2**
on 2026-05-13 (~10:25 UTC, against
[`jarvis@cc8c981`](https://github.com/guardkit/jarvis) under
systemd-managed `jarvis-serve-nats.service`).

**Symptom:** the supervisor's response to *"Now please start a GCSE
English Literature tutoring session on Macbeth, focused on AO1 and AO2…"*
was a self-handled "📚 Tutoring Framework" reply rendered from its own
reasoner, with **zero envelopes on `agents.command.gcse-tutor`**.

**Confirmation via direct probe** of the supervisor's mental model with
the "list available agents" smoke (same smoke used in
[RESULTS-2026-05-13](../../docs/runbooks/RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md)
§2.2 but at run-2 time):

> *"Here are the capabilities available to me right now:
> | architect-agent | …
> | forge | …
> | ideation-agent | …
> | product-owner-agent | …
> **There is no GCSE English Literature tutor agent registered.**"*

The supervisor literally lists the four entries in
`stub_capabilities.yaml` and concludes **gcse-tutor doesn't exist** —
even though it's in the live KV `agent-registry` bucket with four
healthy tool entries (`tutor_start_session`, `tutor_turn`,
`tutor_session_status`, `tutor_session_end`).

## Root cause

[`src/jarvis/infrastructure/lifecycle.py:738`](../../src/jarvis/infrastructure/lifecycle.py#L738)
passes `available_capabilities=capability_registry` (the **singular**,
stub-loaded `list[CapabilityDescriptor]`) into
[`build_supervisor()`](../../src/jarvis/agents/supervisor.py).

The supervisor then renders `{available_capabilities}` via
[`_render_available_capabilities`](../../src/jarvis/agents/supervisor.py#L62)
from that stub list — **never** from the live KV-backed
`capabilities_registry` (the **plural** `LiveCapabilitiesRegistry` that
TASK-DSR-003 W2 wired in for dispatch resolution).

TASK-DSR-003 W2 solved the **dispatch resolver** path (the supervisor's
`dispatch_by_capability(tool_name=...)` lookups now consult live KV),
but the supervisor's **prompt block** was left out of scope. So the
supervisor only proposes dispatches to tools it can see in its prompt
block — which means the stub list — which means **the supervisor never
proposes gcse-tutor tools**.

This is the same structural gap TASK-DSR-001 W1 closed for
`architect-agent` on 2026-05-08. When `gcse-tutor` joined the fleet
afterwards, its corresponding stub entry was never added.

### Why this looked stochastic on the morning run

The run-1 demo (this morning, 06:08 UTC) **did** dispatch five tutor
envelopes successfully — but only because the supervisor's reasoning
model **guessed** the tool name `tutor_start_session` from the user
prompt's intent. With W2's live-KV-backed resolver, the guess succeeded.
At run-2 (10:25 UTC) the reasoner took a different path through its
reasoning and concluded *"I don't have a tutor capability"* — refusing
to guess. Six subsequent CLI smoke trials (`lca-007-verify-*` +
`lca-007-fresh-*`) reproduced the run-2 behaviour deterministically:
0/6 dispatches.

## Acceptance criteria

- **AC-DSR-005-01** ▸ `src/jarvis/config/stub_capabilities.yaml` contains
  a `gcse-tutor` entry under `capabilities:` with:
  - `agent_id: gcse-tutor`
  - `role: GCSE Tutor`
  - `description:` mentioning GCSE-level tutoring across English
    Literature, English Language, Maths, Sciences, History, with
    Socratic dialogue and AO1/AO2/AO3/AO4 assessment objectives
  - `capability_list` containing exactly the four tools that match the
    live KV: `tutor_start_session`, `tutor_turn`,
    `tutor_session_status`, `tutor_session_end`
  - Each tool entry has `description`, `risk_level`, and `parameters`
    block — same shape as the architect tools mirrored under
    `architect-agent`
  - `cost_signal`, `latency_signal`, `last_heartbeat_at`, `trust_tier`
    fields populated
- **AC-DSR-005-02** ▸ Tool parameter schemas (`properties` + `required`)
  in the stub `gcse-tutor` block match the live KV manifest's
  `parameters` field byte-equivalent (same contract as TASK-DSR-001
  AC-001 enforced for architect tools).
- **AC-DSR-005-03** ▸ After the change, restarting `jarvis-serve-nats`
  and firing the "list available agents" CLI smoke returns a list that
  includes `gcse-tutor` in the capability catalogue (manual probe).
- **AC-DSR-005-04** ▸ Three consecutive CLI smoke trials with the demo
  runbook's Turn 2 prompt (GCSE English Literature Macbeth + AO1/AO2)
  each result in **at least one** envelope on `agents.command.gcse-tutor`
  (`tutor_start_session` or `tutor_turn`). Dispatch rate ≥ 3/3.
- **AC-DSR-005-05** ▸ Existing stub entries (`architect-agent`,
  `forge`, `ideation-agent`, `product-owner-agent`) are unchanged. The
  patch is additive only.

## Suggested implementation

Insert a `gcse-tutor` block in `stub_capabilities.yaml`, modelled on the
existing `architect-agent` entry. Source of truth for parameter schemas:
[`study-tutor/src/study_tutor/adapters/manifest.py:28-128`](../../../study-tutor/src/study_tutor/adapters/manifest.py).

Tool descriptions in this stub block should be domain-rich (mirror the
language from the live KV manifest's freshly-rewritten descriptions per
study-tutor@TASK-LCA-007 — the descriptions ARE helpful, just not where
TASK-LCA-007 thought they were being consumed).

## Out of scope

- **The durable fix** — making `available_capabilities` flow from the
  live KV registry into the supervisor's prompt block (closing the
  remaining half of TASK-DSR-003 W2). That's a structural change that
  should be filed as a separate task (TASK-DSR-006 W2' or similar) after
  2026-05-16 demo.
- **Adding new agent-level `description` fields to `AgentManifest`** in
  nats-core. Out of scope for the stub patch.
- **Reverting study-tutor@TASK-LCA-007's manifest description changes** —
  they're additive value (richer live-KV descriptions help any future
  consumer that reads them), even though they weren't the actual fix.

## Verification

After implementation:

1. **Restart** `systemctl --user restart jarvis-serve-nats.service`.
2. **Probe** with the "list available agents" smoke. Assert response
   names `gcse-tutor`.
3. **3× Turn 2 smoke trials** with the demo runbook's exact Turn 2
   prompt. Assert ≥1 envelope per trial on `agents.command.>` matching
   `tutor_start_session` or `tutor_turn`.
4. **End-to-end re-run** of the demo runbook's Phase 4 from OpenWebUI
   (run-3) — Turn 2 should now dispatch to gcse-tutor reliably, the
   coach loop (TASK-LCA-006) should exercise, and the Turn 4 recap
   should attribute the tutor as `gcse-tutor` (not "general-purpose
   subagent").

## Demo-day safety net

This task is the **tourniquet** for 2026-05-16. The structural fix
(`available_capabilities` from live KV) is a larger change and can wait
until post-demo. If the stub patch lands, the demo path is unblocked
regardless of how long the structural fix takes.
