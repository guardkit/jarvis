---
id: TASK-SPL003-J03a
title: "jarvis: dialogue click engine + structured dispositions (FEAT-SPL-003)"
status: in_review
priority: high
task_type: feature
parent_review: TASK-REV-A387
feature_id: FEAT-SPL-003
wave: 3
repo: jarvis
implementation_mode: task-work
complexity: 6
dependencies: [TASK-SPL003-J02]
tags: [sovereign-planning-loop, feat-spl-003, slack, dispositions, reply]
consumer_context:
  - task: TASK-SPL003-J02
    consumes: ITEM_ACTION_VALUE + dialogue block encoding
    framework: "Slack block_actions payload parsing"
    driver: "slack_sdk Socket Mode"
    format_note: "action value {correlation_id,request_id,assumption_id,cycle,approval_subject}; per-item disposition re-derived via assumption_dialogue.parse_dialogue_blocks(message.blocks)"
---

# Task: Dialogue click engine + structured dispositions (no modal)

## Description

Handle per-assumption dialogue clicks (approve/defer/cancel) and publish ONE aggregate
`ApprovalResponsePayload` carrying the **structured `dispositions` field** (nats-core
0.6.0 — supersedes the ASSUM-003 notes-JSON bridge). Extends `ApprovalReplyHandler` /
`SlackSocketModeReplyClient` in `slack_reply.py`. The **edit** modal is J03b; this task
is the click engine and is independently shippable (a working dialogue minus edit).

## Deliverables

1. **Routing** — in `_handle_block_actions` (`slack_reply.py:277`), branch on the new
   `action_id`s (`assumption_approve` / `assumption_defer` / `planning_cancel`;
   `assumption_edit` is routed to J03b's modal open). Reuse the operator allowlist gate
   (`slack_operator_user_ids`) verbatim — a click from outside the allowlist is refused
   with a private ephemeral notice; nothing recorded, nothing published. **Ignore**
   `forge_approve` / `forge_reject` clicks whose `approval_subject` is a `plan-` subject
   (belt-and-braces with J02's mirror suppression).
2. **Message-as-state re-derivation (ASSUM-004), race-safe (red-team F4).** Inside the
   existing `_decision_lock` (`slack_reply.py:321`):
   - Re-fetch the **authoritative** current message via
     `web_client.conversations_history(channel=..., latest=ts, inclusive=True, limit=1)`
     — NOT the possibly-stale inbound `payload["message"]` (two concurrent final clicks
     each carry a stale snapshot → the checkpoint would never publish). Parse it with
     `assumption_dialogue.parse_dialogue_blocks`.
   - Apply this click's decision to the clicked item; `chat.update` the item to show its
     disposition (machine-readable encoding per J02's contract).
   - jarvis keeps **NO** pending-dialogue map (ADR-ARCH-004 — the Slack message IS the
     state).
3. **Auto-publish on completion (ASSUM-010)** — when the last undecided item receives a
   decision (derived from the authoritative message), publish exactly ONE aggregate
   `ApprovalResponsePayload`:
   - `request_id` from the action value; `decided_by` = the clicking member id (identity
     v2, verbatim, `slack_reply.py:342`); publish to `{approval_subject}.response` via the
     existing `NatsApprovalResponsePublisher` (CORE publish + bounded flush).
   - `dispositions: list[AssumptionDisposition]` — one per assumption:
     approve→`accepted`, defer→`deferred` (edit→`modified`+`edit_delta` lands with J03b).
     **No per-item `rejected`** (ASSUM-006). Never emit the spec words confirmed/overridden.
   - `decision` literal (ASSUM-006): all `accepted` → `approve`; any `deferred` → `defer`;
     `planning_cancel` → `reject` (whole-run abort). (any `modified`, none deferred →
     `approve`, wired with J03b.)
   - First-click-wins on the aggregate (`_decided_request_ids`, `slack_reply.py:325-332`)
     so a redelivered/duplicate final click cannot double-publish.
4. **Completeness gate** — no decision is published while any item is undecided
   (the anti-rubber-stamp enforcement point).
5. **Stale click after terminal state (@regression)** — jarvis has no pending map, so a
   well-formed authorized click still publishes faithfully; forge is the authoritative
   refuser (JNB-105 parity). No local refusal.
6. **Escalated (@edge)** — jarvis publishes the disposition faithfully; forge's per-run
   `expected_approver` is the authoritative identity gate (a non-Rich decision is refused
   by forge). jarvis-side: allowlist gate + faithful publish only.

## Acceptance Criteria

- [ ] Approving every assumption one-by-one publishes exactly one decision recording a
      distinct `accepted` disposition per assumption, each with the clicker's member id;
      the run can proceed. (@smoke)
- [ ] Deferring one assumption + approving the rest publishes a decision whose that-item
      disposition is `deferred`, asks for another cycle (`decision=defer`), and preserves
      the other dispositions. (@key-example)
- [ ] The published decision carries every disposition keyed by `assumption_id`. (@key-example
      "Per-assumption dispositions land in the planning trace record" — jarvis-publish half)
- [ ] A click from outside the allowlist is refused with a private notice; no disposition
      recorded, no decision published. (@negative)
- [ ] No decision is published while any assumption is undecided; the undecided item still
      awaits its own decision. (@negative)
- [ ] A prompt rendered before a restart remains decidable after it (re-derived from the
      message); the published decision carries every assumption's disposition, with no
      re-rendering. (@edge "remains fully decidable after")
- [ ] Two of three decided pre-restart + the third decided after → the published decision
      carries all three, the earlier two preserved exactly. (@edge)
- [ ] Concurrent final clicks do not stall or double-publish (authoritative re-fetch).
- [ ] A stale click after terminal state is still published faithfully; forge refuses it.
      (@regression)
- [ ] An escalated checkpoint: jarvis publishes faithfully; only Rich's decision is
      accepted by the planning run. (@edge — publish half)
- [ ] Published `dispositions[].disposition` ∈ {accepted, deferred} (this task);
      never confirmed/overridden/per-item rejected.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- `tests/test_assumption_dialogue_scenarios_spl003.py` (reply half) — drive
  `SlackSocketModeReplyClient._on_request` / `_handle_block_actions` with synthesized
  `block_actions` envelopes + an `AsyncMock` web client whose `conversations_history`
  returns the current message; assert the published `ApprovalResponsePayload` bytes
  (dispositions structure, decision literal, decided_by, subject). Concurrency test:
  two near-simultaneous final clicks → exactly one publish, complete dispositions.
  Restart = a fresh handler re-deriving from a reconstructed message. Fully hermetic.
- Round-trip the published payload through the **installed** `nats_core`
  `ApprovalResponsePayload` (dispositions validated).

## Coach Validation

```
.venv/bin/python -m pytest tests/test_assumption_dialogue_scenarios_spl003.py tests/test_slack_reply.py tests/test_slack_reply_scenarios_jnb105.py -x -q
.venv/bin/ruff check src/jarvis/infrastructure/slack_reply.py
.venv/bin/mypy src/jarvis/infrastructure/slack_reply.py
```
