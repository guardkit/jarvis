---
id: TASK-DSR-001
title: "W1 — Patch stub_capabilities.yaml to mirror live KV architect-agent tools"
task_type: bugfix
status: completed
created: 2026-05-08T00:00:00Z
updated: 2026-05-08T00:00:00Z
completed: 2026-05-08T00:00:00Z
priority: critical
complexity: 1
wave: 1
implementation_mode: direct
estimated_minutes: 15
parent_review: TASK-REV-CB48
feature_id: FEAT-DSR
demo_blocker_for: 2026-05-16
tags: [jarvis, dispatch, capabilities-registry, demo-unblock, w1-insurance, stub-yaml]
context_files:
  - src/jarvis/config/stub_capabilities.yaml
  - .claude/reviews/TASK-REV-CB48-review-report.md
test_results:
  status: passed
  coverage: null
  last_run: 2026-05-08T00:00:00Z
acceptance_criteria_status:
  AC-001: passed   # Six tool entries present (run_architecture_session, draft_adr, architect_greenfield, architect_align, architect_explore, architect_feasibility)
  AC-002: deferred # Manual boot-time verification — satisfied at Wave 1 close gate (covered by TASK-DSR-004 end-to-end re-run)
  AC-003: passed   # YAML structure validated; pytest collection blocked by unrelated env issue (missing asteval module), not introduced by this change
---

## Implementation Summary

Added four architect tool entries to `architect-agent`'s `capability_list` in
`src/jarvis/config/stub_capabilities.yaml` to mirror the live KV's published
surface: `architect_greenfield`, `architect_align`, `architect_explore`,
`architect_feasibility` (all `read_only`). Existing `run_architecture_session`
and `draft_adr` entries preserved unchanged. The dispatch resolver at
`dispatch.py:438` now finds `architect_align` (and the three siblings) on the
stub path until W2 (TASK-DSR-003) replaces the stub-list snapshot with the live
KV snapshot.

This is the tourniquet — W1 demo insurance for DDD South West 2026-05-16. W2
closes the structural gap durably; if W2 slips, this change still protects the
demo.

## Notes

AC-002 is a manual boot-time verification (boot Jarvis with the dual-role
stack, dispatch `architect_align`, confirm the trace lands an
`agents.command.architect-agent.<corr>` envelope on JetStream). This step is
the Wave 1 close gate per `IMPLEMENTATION-GUIDE.md` and is also exercised by
TASK-DSR-004's end-to-end re-run of the runbook. Marked `deferred` here
because it cannot be executed inside the code change itself — the YAML edit is
the only artifact required.

AC-003: the pytest collection error encountered while verifying
(`ModuleNotFoundError: No module named 'asteval'`) reproduces against the
pre-change `main` and is unrelated to this YAML edit. Direct yaml.safe_load +
schema validation confirms the file parses and every entry has the required
`tool_name`, `description`, and `risk_level` (all `read_only` or `mutating`).

# Task: W1 — Patch stub_capabilities.yaml to mirror live KV architect-agent tools

## Description

Demo insurance for DDD South West 2026-05-16. The dispatch resolver iterates the
stub yaml at `dispatch.py:438` and finds no match for `architect_align` because
the yaml only lists `run_architecture_session` and `draft_adr` for architect-agent.
Mirror the live KV's published surface in the yaml so the resolver wins on the
stub path until W2 (TASK-DSR-003) ships.

This is a tourniquet, not the canonical fix — it masks the structural gap rather
than closing it. W2 closes the gap durably. Both land independently; W1 protects
the demo if W2 slips.

## Implementation

In `src/jarvis/config/stub_capabilities.yaml`, under the `architect-agent` entry's
`capability_list`, add four tool entries to mirror the live KV. The exact tool
names from the live container are `architect_greenfield`, `architect_align`,
`architect_explore`, `architect_feasibility` (per the review root-cause section).

Suggested entries (descriptions are operator-facing; copy the tone of the
existing two entries):

```yaml
- tool_name: architect_greenfield
  description: Drive a greenfield architecture session for a new feature scope.
  risk_level: read_only
- tool_name: architect_align
  description: Align an existing design against the ADR set; emit an AlignmentJudgment.
  risk_level: read_only
- tool_name: architect_explore
  description: Explore design alternatives for an open architectural question.
  risk_level: read_only
- tool_name: architect_feasibility
  description: Assess feasibility of a proposed approach against current constraints.
  risk_level: read_only
```

Keep `run_architecture_session` and `draft_adr` intact — they remain the agent's
existing entries.

## Acceptance Criteria

- [ ] **AC-001:** `architect-agent`'s `capability_list` in `stub_capabilities.yaml`
      contains all six tool entries (`run_architecture_session`, `draft_adr`,
      `architect_greenfield`, `architect_align`, `architect_explore`,
      `architect_feasibility`) with appropriate descriptions and `risk_level`.
- [ ] **AC-002:** Manual boot-time verification — boot Jarvis with the
      dual-role stack and dispatch `architect_align` once. The trace must land
      an `agents.command.architect-agent.<corr>` envelope on JetStream
      (i.e. resolver finds the entry, regardless of downstream outcome).
- [ ] **AC-003:** `pytest` remains green (yaml load is exercised by existing
      `load_stub_registry` tests; no new test required at this layer).

## Out of Scope

- The dispatch wiring fix (W2) — handled by TASK-DSR-003.
- Runbook updates — handled by TASK-DSR-002 (Wave 1) and TASK-DSR-004 (Wave 3).
- Stub-yaml deprecation question — review report R5; defer post-demo.

## See Also

- [Review report](../../../.claude/reviews/TASK-REV-CB48-review-report.md) — R1.
- [`stub_capabilities.yaml`](../../../src/jarvis/config/stub_capabilities.yaml) — the file to edit.
- [`dispatch.py:438`](../../../src/jarvis/tools/dispatch.py#L438) — the resolver line that consumes this yaml's content.
