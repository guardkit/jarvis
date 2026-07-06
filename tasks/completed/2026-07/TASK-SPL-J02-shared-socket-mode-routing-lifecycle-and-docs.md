---
id: TASK-SPL-J02
title: "jarvis: shared Socket Mode routing (union gate) + lifecycle wiring + config docs (FEAT-SPL-001)"
status: completed
previous_state: in_review
completed: 2026-07-06T12:40:13Z
created: 2026-07-06T10:20:00Z
updated: 2026-07-06T12:40:13Z
priority: high
task_type: feature
parent_review: TASK-REV-3240
feature_id: FEAT-SPL-001
wave: 2
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: [TASK-SPL-J01]
tags: [sovereign-planning-loop, feat-spl-001, slack, socket-mode, lifecycle]
consumer_context:
  - task: TASK-SPL-J01
    consumes: PlanningIntakeHandler + create_slack_planning_intake_handler
    framework: "slack-sdk aiohttp SocketModeClient (JNB-104 lifecycle wrapper)"
    driver: "slack_sdk.socket_mode.aiohttp"
    format_note: "Handler exposes an async handle_message_event(payload: dict) -> None that never raises; factory returns handler-or-None per its own no-op gate"
---

# Task: Shared Socket Mode routing (union gate) + lifecycle wiring + config docs

## Description

Route planning intake through the ONE existing Socket Mode connection and
restructure the no-op gate to a **union gate** so neither feature's
misconfiguration silently kills the other (review F1 — confirmed HIGH twice;
F2). Wire into `build_app_state`, document the new keys in `.env.example`.

**Do not** open a second Socket Mode connection (ack-and-drop of the other
feature's traffic) and **do not** append a second `socket_mode_request_listener`
(the SDK fans every envelope to all listeners → double-ack, forked invariants).

## Deliverables

1. **`src/jarvis/infrastructure/slack_reply.py`** (minimal diff — the module
   awaits its JNB-107 live validation):
   - `SlackSocketModeReplyClient.__init__` gains an optional
     `events_handler` (the J01 intake handler, or None).
   - `_on_request` becomes a request-type router: **ack exactly once, first**
     (unchanged), then `req.type == "interactive"` → existing
     ApprovalReplyHandler branch; `req.type == "events_api"` → None-safe
     dispatch to the intake handler. The approval handler itself may be None
     when only intake is configured — both branches None-safe.
   - Registration-before-connect and register-once-across-reconnects
     invariants preserved verbatim (docstring pins stay).
   - Class docstring updated: the client hosts both Slack Socket Mode
     features (name kept — rename deferred with the Option-C refactor).
2. **Union gate** — factory restructure (same module):
   connection is constructed when `slack_app_token` + `slack_bot_token` +
   NATS are present **AND at least one feature is fully configured**
   (reply path: `slack_operator_user_id`; intake: both planning keys).
   Each feature's handler is built only when its own settings are present;
   each unconfigured feature logs its own distinct no-op reason
   (`slack_reply_no_op` / `slack_planning_intake_no_op` naming the missing
   keys). An operator-id-unset deployment MUST still run intake, and vice
   versa.
3. **`src/jarvis/infrastructure/lifecycle.py`**: `build_app_state` builds the
   intake handler via the J01 factory and passes it into the (renamed
   responsibility, same slot) client construction site; DDR-021 soft-fail on
   `start()` unchanged; `AppState` docstring notes the client now also carries
   planning intake; shutdown ordering unchanged.
4. **`.env.example`**: `JARVIS_SLACK_PLANNING_CHANNEL_ID` +
   `JARVIS_SLACK_PLANNING_ORIGINATOR_USER_ID` with placeholder values and the
   operator note: Slack app manifest needs the `message.channels` **and**
   `message.groups` bot event subscriptions (private channels use groups), the
   bot must be `/invite`d to the planning channel, and live validation is
   TASK-SPL-J04 (bundle with OPS-001).

## Acceptance Criteria

- [ ] Factory-gate permutation tests: all four config permutations
      (both / reply-only / intake-only / neither) — connection existence,
      handler registration, and the specific no-op log event asserted for each
- [ ] Exactly ONE ack per envelope with both handlers active (regression test)
- [ ] Single-registration-across-reconnect test on a fake client (JNB-104 precedent)
- [ ] Existing JNB-104/JNB-105 suites pass unchanged (approval path unaffected)
- [ ] `build_app_state` wiring tests (patched collaborators) cover
      intake-handler-present and None branches
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Implementation Notes

- The gate change alters `create_slack_reply_client`'s documented contract —
  update its docstring's no-op-conditions list to the union semantics.
- Keep the diff to `slack_reply.py` as small as honestly possible (~20-40
  lines); all intake logic lives in J01's module.
