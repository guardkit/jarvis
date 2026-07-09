---
id: TASK-SPL003-J03b
title: "jarvis: assumption edit modal (views.open + view_submission) (FEAT-SPL-003)"
status: in_review
priority: high
task_type: feature
parent_review: TASK-REV-A387
feature_id: FEAT-SPL-003
wave: 4
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: [TASK-SPL003-J03a]
tags: [sovereign-planning-loop, feat-spl-003, slack, modal]
---

# Task: Assumption edit modal (views.open + view_submission)

## Description

Add the **edit** disposition path — a Slack modal for a prefilled free-text override.
This is the **first modal in the codebase** (no `views.open` / `view_submission`
handling exists anywhere in `src/`), so it is isolated in its own task to keep the
J03a click engine independently green. The edited value is the highest-value curation
signal (the input to forge's revision cycle).

## Deliverables

1. **`view_submission` routing** — `SlackSocketModeReplyClient._on_request`
   (`slack_reply.py:659-700`) today handles only `block_actions` (it `return`s on any
   other `interactive` payload type, `:679-686`). Add a `view_submission` branch that
   acks first and routes to the new submission handler.
2. **Open the modal** — on an `assumption_edit` click, call `views.open` with the click's
   `trigger_id`, prefilled with the assumption's proposed text. **Open the modal BEFORE
   taking the handler-wide `_decision_lock`** (arch F4 — the `trigger_id` has a ~3s TTL;
   lock contention must not blow the window). `private_metadata` carries
   `{correlation_id, request_id, assumption_id, cycle, approval_subject, channel, message_ts}`
   so the submission can locate and update the originating message.
3. **Handle the submission** — on `view_submission`, record `modified:<submitted text>`
   for that item (disposition `modified`, `edit_delta` = the submitted text). `chat.update`
   the item in the originating message (via `private_metadata`) to show the override, then
   reuse J03a's re-derive + auto-publish path (if this was the final undecided item, the
   aggregate publishes with `decision=approve` when any item is `modified` and none
   `deferred`). Modal **cancel/close** leaves the item undecided.
4. **`edit_delta` survives (arch F5 / red-team F9)** — the override text is stashed
   machine-readably in the item encoding (via `assumption_dialogue`), so a later,
   possibly post-restart, decision on another item re-derives the earlier `modified`
   disposition **and its full replacement text** verbatim into the aggregate.

## Acceptance Criteria

- [ ] Choosing edit opens a modal prefilled with the assumption text; submitting a
      corrected value records that assumption's disposition as `modified` carrying the
      corrected value (`edit_delta`); the other assumptions' dispositions are unaffected.
      (@key-example "Editing an assumption records an overridden disposition")
- [ ] After an edit completes the checkpoint, the aggregate `decision` is `approve` and
      the `modified` item carries `edit_delta` == the submitted text (byte-exact, even a
      500-char edit re-derived across a later click).
- [ ] Modal cancel leaves the item undecided (no publish while undecided).
- [ ] `view_submission` is routed (was previously dropped); `block_actions` still works.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- `tests/test_assumption_dialogue_scenarios_spl003.py` (modal half) — drive `_on_request`
  with a synthesized `assumption_edit` `block_actions` envelope (assert `views_open`
  called with the trigger_id + prefilled text) and a synthesized `view_submission`
  envelope (assert the item becomes `modified` with `edit_delta`, and the aggregate
  publish when it completes the checkpoint). `edit_delta` byte-exact round-trip test with
  a long override re-derived after a simulated restart. Fully hermetic (AsyncMock web
  client; no live Slack).

## Coach Validation

```
.venv/bin/python -m pytest tests/test_assumption_dialogue_scenarios_spl003.py tests/test_slack_reply.py -x -q
.venv/bin/ruff check src/jarvis/infrastructure/slack_reply.py
.venv/bin/mypy src/jarvis/infrastructure/slack_reply.py
```

## Required operator follow-up

The modal's live-only facts (trigger_id opens a view within Slack's ~3s window;
`view_submission` co-delivers on the shared Socket Mode connection; **Interactivity
must be enabled in the Slack app manifest**) are verified by TASK-SPL003-J05, not here.
