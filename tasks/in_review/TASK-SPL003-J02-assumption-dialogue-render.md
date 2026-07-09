---
id: TASK-SPL003-J02
title: "jarvis: assumption-dialogue render + binary-mirror suppression (FEAT-SPL-003)"
status: in_review
priority: high
task_type: feature
parent_review: TASK-REV-A387
feature_id: FEAT-SPL-003
wave: 2
repo: jarvis
implementation_mode: task-work
complexity: 7
dependencies: [TASK-SPL003-J01]
tags: [sovereign-planning-loop, feat-spl-003, slack, block-kit, dialogue]
consumer_context:
  - task: TASK-SPL003-J01
    consumes: post_threaded
    framework: "Slack Web API (chat.postMessage) via AsyncWebClient"
    driver: "slack_sdk"
    format_note: "post_threaded(web_client, *, channel, text, thread_ts, blocks) — J02 posts the dialogue into the planning thread through this helper"
---

# Task: Assumption-dialogue render + binary-mirror suppression

## Description

Render a Mode P planning checkpoint (`plan-{cid}` `ApprovalRequestPayload`) as a
per-assumption Block Kit decision prompt — **one item per assumption, forced
per-item decisions, no mega-Approve**. The anti-rubber-stamp UX is load-bearing for
WS4 (harvest: 0 'considered' across 31 sessions).

**Two CRITICAL corrections from TASK-REV-A387 (verified against forge/jarvis code):**

1. **Render directly from `payload.details`, NOT via the pause-join.** The existing
   `ApprovalRequestsSubscriber._handle_message` (`slack_notifier.py:1323-1391`) calls
   `capture_approval_request(...)` which **discards `payload.details`** (the only place
   the assumptions live). Rendering today happens later, off a `build_paused` mirror,
   which has no assumptions. So planning MUST render at capture time from
   `ApprovalRequestPayload.details`. Branch in `_handle_message` **after** the
   `ApprovalRequestPayload.model_validate(...)` parse and **before**
   `capture_approval_request`: if this is a planning checkpoint, render + `return`
   (never park in `_pending_approvals`). The build-pause capture branch stays
   **byte-for-byte unchanged** (~112 shared tests must stay green).
2. **Suppress the binary `plan-` rubber-stamp mirror.** forge
   (`_serve_planning.py:342-410`) also publishes a `pipeline.build-paused.FEAT-PLANNING`
   mirror that jarvis would render as a binary `forge_approve`/`forge_reject` — the
   exact approve-all control scenario 15 forbids. In `SlackNotifier._deliver_pause_message`
   (`slack_notifier.py:797-884`) / the `notify` routing, **skip planning builds**
   (`build_id.startswith("plan-")` OR `feature_id == "FEAT-PLANNING"`) so no binary
   pause message is posted for a checkpoint. (J03a additionally ignores
   `forge_approve`/`forge_reject` clicks on `plan-` subjects.)

**Detection** is by `details.checkpoint_type` (`product_docs` / `product_docs_*`) —
NEVER by parsing the run-id shape out of the subject (ASSUM-002).

**Testability:** forge does NOT yet project `assumptions`/`parent_request_id`/`cycle`
(`forge/src/forge/planning/checkpoint.py:294-309`; ASSUM-014 — forge-half unbuilt).
This task is therefore **jarvis-fixture-tested** against synthetic `details`; the exact
`details` schema is pinned as the contract fixture in J04 that TASK-SPL003F-001 must
satisfy. Live E2E of scenarios 1/2/6/11/21/24 is deferred to the operator task (J05)
once forge-half lands. Do NOT overclaim live workability.

## Deliverables

1. **`src/jarvis/infrastructure/assumption_dialogue.py`** — the shared render/parse
   module (J03 imports the parse half; single source of truth for the block contract,
   arch F6):
   - `build_dialogue_blocks(details, *, chunk_index, chunk_count) -> list[blocks]` —
     one item per assumption from `details["summary"]["assumptions"]`
     (`[{id, text, confidence, basis}]`): section with assumption text + a confidence
     context tag, and three buttons (action_ids `assumption_approve` / `assumption_edit`
     / `assumption_defer`), `block_id = assumption_id`. Each button's `value` is compact
     JSON `{"correlation_id","request_id","assumption_id","cycle","approval_subject"}`
     (carries `approval_subject` so J03a publishes to `{approval_subject}.response`,
     JNB-104 parity; guard `len < _SLACK_ACTION_VALUE_LIMIT` = 2000 —
     `slack_notifier.py:86`). The assumption text is NEVER in the value.
   - **No approve-all control** anywhere. A single whole-run **"Cancel planning run"**
     control in an overflow menu (`action_id planning_cancel`) — abort, not a decision
     shortcut (ASSUM-011).
   - **Chunking** at 8 items/message (ASSUM-009), continued in the same thread with a
     "continued (n/m)" context marker; item metadata stays under the 2000-char limit.
   - **Zero assumptions** → a single whole-checkpoint approve (the only one-control
     case, ASSUM-006).
   - **Escalation** (`checkpoint_type == "product_docs_escalated"`, or cap-3 reached via
     `attempt_count`) → re-render the FULL item list, `@`-mention Rich (from
     `details["expected_approver"]`), show cycle + attempt (ASSUM-012).
   - **Open questions** in the PO output render as confidence-tagged decidable items —
     jarvis never poses a free-text question of its own (propose-never-elicit, scope §3.3).
   - The dialogue prompt shows which **cycle** it belongs to.
   - `parse_dialogue_blocks(message_blocks) -> dict[assumption_id, {disposition, edit_delta}]`
     — re-derive per-item disposition state from a rendered message (used by J03a;
     defined here so encode/decode share one contract). Disposition state is stashed in
     a **machine-readable** field per item (block `block_id` + a stable metadata encoding),
     NOT human display strings (arch F5).
2. **Edits to `slack_notifier.py`**:
   - The `_handle_message` branch (above), routing planning checkpoints to a new render
     path that posts threaded via J01's `post_threaded` into `slack_planning_channel_id`
     (thread anchor from `details.get("parent_request_id")`; degrade top-level if absent).
   - The `plan-` binary-mirror suppression (above).
   - The render path uses its **own** `AsyncWebClient` (bot token) + planning channel,
     independent of the sink (arch F2). Wire it where the `ApprovalRequestsSubscriber`
     is constructed (`lifecycle.py` 7c2) — widen that gate to also wire when planning
     config is present even if the forge-notification `SlackNotifier` sink is a NoOp.

## Acceptance Criteria

- [ ] A planning checkpoint renders a decision prompt in the originating thread; every
      proposed assumption is its own item showing text + confidence; each offers exactly
      approve/edit/defer; no control decides more than one assumption. (@smoke)
- [ ] 1 assumption and 16 assumptions both render as N individually-decidable items.
      (@boundary Scenario Outline)
- [ ] A checkpoint too large for one message continues across messages in the same
      thread; no assumption dropped. (@boundary)
- [ ] The third dialogue cycle renders as a normal per-assumption prompt. (@boundary)
- [ ] Reaching the cycle cap escalates to Rich (no fourth prompt), rendered in the same
      thread addressed to Rich. (@boundary @negative + @edge escalated render)
- [ ] A zero-assumption checkpoint offers a single whole-checkpoint approval — the only
      case with one control. (@boundary)
- [ ] No approve-all control is present anywhere in the prompt. (@negative)
- [ ] Open questions render as confidence-tagged decidable items; jarvis poses no
      free-text question. (@negative)
- [ ] A revised checkpoint re-renders in the same thread showing its cycle number.
      (@key-example "A revision cycle re-renders ...")
- [ ] No binary `forge_approve`/`forge_reject` pause message is posted for a `plan-`
      build; the existing build-pause path is unchanged for non-planning builds.
- [ ] The build-pause regression surface stays green (test_slack_notifier.py,
      test_slack_approval_buttons.py, test_forge_notifications_subscriber.py,
      test_slack_notifier_hardening.py).
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- `tests/test_assumption_dialogue_render.py` — `build_dialogue_blocks` unit tests:
  per-item shape, confidence tag, action value < 2000 & carries approval_subject,
  no approve-all, cancel-in-overflow, chunking (16→2 msgs), zero-item whole-approve,
  escalation full-list + Rich mention + cycle/attempt, open-questions-as-items.
- `tests/test_assumption_dialogue_scenarios_spl003.py` (render half) — the render
  scenarios above, driven by synthetic `ApprovalRequestPayload.details` fixtures.
- Regression: the four build-pause test files above must pass unchanged (run in Coach).
- Hermetic: no live Slack/NATS. Synthetic details fixtures only.

## Coach Validation

```
.venv/bin/python -m pytest tests/test_assumption_dialogue_render.py tests/test_assumption_dialogue_scenarios_spl003.py tests/test_slack_notifier.py tests/test_slack_approval_buttons.py tests/test_forge_notifications_subscriber.py tests/infrastructure/test_slack_notifier_hardening.py -x -q
.venv/bin/ruff check src/jarvis/infrastructure/assumption_dialogue.py src/jarvis/infrastructure/slack_notifier.py
.venv/bin/mypy src/jarvis/infrastructure/assumption_dialogue.py
```
