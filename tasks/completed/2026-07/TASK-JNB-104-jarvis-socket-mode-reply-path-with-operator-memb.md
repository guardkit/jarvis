---
id: TASK-JNB-104
title: "jarvis: Socket Mode reply path with operator-member-id authorization"
status: completed
created: 2026-07-03T15:30:00Z
updated: 2026-07-07T09:05:00Z
completed: 2026-07-07T09:05:00Z
previous_state: in_review
state_transition_reason: "FEAT-BF39 v1.1 rollup (Rich, 2026-07-07): JNB-107 live validation complete — all four scenarios; SPL Gate G1 PASS. Completed by the ops session on Rich's instruction."
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-BF39
version: v1.1
wave: 8
repo: jarvis
implementation_mode: task-work
complexity: 7
dependencies: [TASK-JNB-103]
tags: [ubs-003, jarvis-notification-bridge, slack, v1.1]
consumer_context:
  - task: TASK-JNB-103
    consumes: BUTTON_METADATA
    framework: "Slack Block Kit interactive buttons over Socket Mode"
    driver: "slack-sdk SocketModeClient"
    format_note: "button value is JSON {request_id, build_id, correlation_id, approval_subject} and must stay within Slack's 2000-char action value limit"
  - task: TASK-JNB-101
    consumes: APPROVER_IDENTITY
    framework: "config string equality: forge expected_approver == jarvis slack_decided_by"
    driver: "pydantic-settings"
    format_note: "exact string match; a mismatch silently refuses every phone approval"
---

# Task: jarvis: Socket Mode reply path with operator-member-id authorization

## Description

New Socket Mode client on `JARVIS_SLACK_APP_TOKEN` (outbound WebSocket — no public endpoint), lifecycle-wired with reconnect tolerance and a no-op mode when the app token or operator id are absent. Its `block_actions` handler: ack immediately; the sole Slack-side authorization gate is `payload.user.id == JARVIS_SLACK_OPERATOR_USER_ID` (mismatch: WARN log + ephemeral refusal, nothing published); on an authorized click, publish `ApprovalResponsePayload(request_id from the button value, decision approve|reject, decided_by=settings.slack_decided_by)` to `approval_subject + '.response'` carrying the request's `correlation_id`, apply local first-click-wins, then `chat.update` to disable the buttons and show the recorded decision. A publish failure logs WARNING and re-enables the buttons so the operator can retry.

Architecture context: the client is constructed in `infrastructure/lifecycle.py` `build_app_state`, alongside the existing SlackNotifier (`src/jarvis/infrastructure/slack_notifier.py`), only when `JARVIS_SLACK_APP_TOKEN` and `JARVIS_SLACK_OPERATOR_USER_ID` are set — otherwise a logged no-op, and the supervisor starts normally. All button metadata arrives via the value JSON that TASK-JNB-103's Block Kit message carries: `{request_id, build_id, correlation_id, approval_subject}` (the `approval_subject` arrives free on `BuildPausedPayload` — zero nats-core changes anywhere). The published response is consumed by forge's untouched four-step validation chain (payload validation -> `decided_by` allowlist vs `expected_approver` -> `correlation_id` match -> `request_id` 300s dedup), wired into production by TASK-JNB-101. Window/expiry-race enforcement stays exclusively forge-side, so a reply-vs-expiry race resolves in exactly one place: jarvis must NOT implement any approval-window checks. Local first-click-wins is a client-side courtesy only; forge's `request_id` dedup remains the authoritative guard. Config uses the existing pydantic-settings `JARVIS_` prefix fields: `slack_app_token` (`SecretStr | None`), `slack_operator_user_id`, `slack_decided_by` — matching the keys already validated in jarvis `.env`.

## Acceptance Criteria

- [x] Socket Mode client (slack-sdk `SocketModeClient` on `JARVIS_SLACK_APP_TOKEN`) is constructed and started in `infrastructure/lifecycle.py` `build_app_state`, and shut down cleanly with the supervisor lifecycle
- [x] When `JARVIS_SLACK_APP_TOKEN` or `JARVIS_SLACK_OPERATOR_USER_ID` is absent, the reply path is a logged no-op and the supervisor starts and runs normally
- [x] Every `block_actions` envelope is acked immediately, before any authorization, parsing, or publish work
- [x] An unauthorized click (`payload.user.id != JARVIS_SLACK_OPERATOR_USER_ID`) never publishes: WARN log + ephemeral refusal to the clicking user, nothing sent to NATS
- [x] An authorized approve click publishes `ApprovalResponsePayload` with `request_id` taken from the button value JSON, `decision="approve"`, and `decided_by=settings.slack_decided_by`, to `approval_subject + ".response"`, carrying the request's `correlation_id` — a payload forge's untouched validation chain accepts
- [x] An authorized reject click publishes `decision="reject"` through the same path
- [x] `decided_by` equals `settings.slack_decided_by` verbatim — no trimming, casing, or normalisation (config alignment with forge `expected_approver`; a mismatch silently refuses every phone approval)
- [x] A double-click publishes at most once client-side (local first-click-wins keyed on `request_id`); forge `request_id` dedup remains the authoritative guard
- [x] After a successful publish, `chat.update` disables the buttons and shows the recorded decision in place
- [x] A publish failure logs WARNING and re-enables the buttons; no exception propagates out of the handler (DDR-007)
- [x] Malformed action payloads (unparseable value JSON, missing keys, unknown action id) are dropped with a log entry; nothing is published and the client keeps running
- [x] A Socket Mode reconnect never duplicates handlers and never re-publishes a prior decision (handler registration is idempotent; first-click-wins state survives reconnect)
- [x] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

Plain pytest ONLY — NO pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror the FEAT-UBS-003 spec scenario names for the reply path. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

- Mock `SocketModeClient` and the NATS publisher with `unittest.mock` / `AsyncMock`; no live Slack or NATS in unit tests
- Suggested class organisation (mirroring scenarios): `TestUnauthorizedClickRefused`, `TestAuthorizedApprovePublishes`, `TestAuthorizedRejectPublishes`, `TestDoubleClickPublishesAtMostOnce`, `TestMalformedActionPayloadDropped`, `TestReconnectNoDuplicateHandlersOrPublishes`, `TestNoOpModeWhenConfigAbsent`, `TestPublishFailureReenablesButtons`
- Assert the ack happens before authorization/publish (call-order assertion on the mocked client)
- Assert the unauthorized path logs WARN, sends an ephemeral refusal, and the publisher mock is never awaited
- Assert the published subject is exactly `approval_subject + ".response"` and the envelope carries the request's `correlation_id`
- Assert publish-failure path: publisher raising -> WARNING logged, `chat.update` re-enables buttons, no exception propagates

## Seam Tests

Include these seam tests (real assertions, no placeholders). Import the handler/parser from the module this task creates for the Socket Mode reply path.

```python
import json
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("BUTTON_METADATA")
def test_button_value_json_round_trips_within_slack_action_value_limit():
    """BUTTON_METADATA from TASK-JNB-103: value JSON {request_id, build_id,
    correlation_id, approval_subject} must round-trip and stay < 2000 chars
    even with max-size build/correlation ids."""
    value_dict = {
        "request_id": "apr-" + "a" * 60,                       # max-size request id
        "build_id": "build-" + "b" * 250,                      # max-size build id
        "correlation_id": "corr-" + "c" * 250,                 # max-size correlation id
        "approval_subject": "agents.approval.forge." + "b" * 250,
    }
    value = json.dumps(value_dict)
    assert len(value) < 2000  # Slack's action value hard limit

    parsed = parse_button_value(value)  # this task's value parser
    assert parsed["request_id"] == value_dict["request_id"]
    assert parsed["build_id"] == value_dict["build_id"]
    assert parsed["correlation_id"] == value_dict["correlation_id"]
    assert parsed["approval_subject"] == value_dict["approval_subject"]


@pytest.mark.seam
@pytest.mark.integration_contract("APPROVER_IDENTITY")
async def test_published_decided_by_equals_slack_decided_by_verbatim(settings, authorized_click_payload, publisher_mock):
    """APPROVER_IDENTITY from TASK-JNB-101: forge accepts the response only if
    decided_by string-equals its expected_approver — exact match, no
    normalisation. A mismatch silently refuses every phone approval."""
    settings.slack_decided_by = "Jarvis-Operator"  # deliberate mixed case
    handler = build_reply_handler(settings=settings, publisher=publisher_mock)

    await handler.handle_block_actions(authorized_click_payload)

    published = publisher_mock.publish.await_args.kwargs["payload"]
    assert published.decided_by == settings.slack_decided_by       # verbatim
    assert published.decided_by == "Jarvis-Operator"               # not lowercased
    assert published.decided_by != "jarvis-operator"               # no normalisation
```

## Implementation Notes

- **Dependency — TASK-JNB-103** ("jarvis: approval-request capture + Block Kit approve/reject buttons"): produces the Block Kit Approve/Reject buttons whose value JSON carries `{request_id, build_id, correlation_id, approval_subject}`, backed by a TTL'd pending map keyed by `build_id` and captured from `agents.approval.forge.>`; a defer-republish mints a refreshed `request_id` and `chat.update`s the buttons in place. This task consumes that value JSON verbatim — do not re-derive `request_id` locally (`BuildPausedPayload` carries no `attempt_count`, so jarvis can never derive it).
- **Contract with TASK-JNB-101** (forge ApprovalSubscriber production wiring, wave 7): the published `ApprovalResponsePayload` traverses forge's untouched chain — payload validation -> `decided_by` allowlist vs `expected_approver` -> `correlation_id` match -> `request_id` 300s dedup. The `decided_by`/`expected_approver` shared value is config, not code; it is a named AC here and in TASK-JNB-101, and is probed live in TASK-JNB-107.
- **Single-consumer rule (workqueue err-10100)**: this task must not create any PIPELINE-stream consumer. Its only NATS interaction is a publish to `approval_subject + ".response"` on the AGENTS stream (limits retention — overlap legal). The one ephemeral PIPELINE consumer stays untouched.
- **DDR-007 (never regress the core loop)**: no code path in the reply handler may raise into the supervisor event loop or the Socket Mode client; every failure is WARNING + continue. Publish failure specifically re-enables the buttons rather than crashing or silently swallowing.
- **DDR-027 (no replay)**: first-click-wins and pending-approval state are in-process only; a jarvis restart loses them by design. Forge's `request_id` dedup is the authoritative backstop, so a post-restart re-click is safe.
- **Window/expiry enforcement is forge-side only**: do not implement approval-window or expiry checks in jarvis. A briefly-stale button (defer-republish outrunning the `chat.update` refresh) is safe — forge refuses it; UX-only risk.
- **Correlation-INDEPENDENT fan-out is deliberate**: the phone surface is per-operator, not per-session; nothing in this task should couple the reply path to the correlation LRU.
- **Operational surface**: the Socket Mode client's lifetime inside the supervisor event loop (reconnects, missed acks) is new; reconnect-without-duplicate-handlers/publishes is an explicit AC because real behaviour only shows in TASK-JNB-107.
- **Worktree scope**: the autobuild worktree is jarvis-scoped and cannot read the sibling forge repo — everything needed (contract shapes, subjects, validation-chain behaviour) is stated in this file; do not attempt to open forge sources.


---

## Completion note (2026-07-05, task-work session)

Implemented per `docs/state/TASK-JNB-104/implementation_plan.md` (arch review
78/100 with C1/C2 invariants; multi-lens review with worktree-isolated
verifiers — 7 confirmed findings fixed, most notably the CRITICAL unbounded
`SocketModeClient.connect()` hang that could brick supervisor boot on a bad
app token, now bounded at 15 s with DDR-021 soft-fail; handler-wide decision
lock; missing-blocks guard).

- Suite: 2527 passed / 2 skipped / 0 failed. New tests: `tests/test_slack_reply.py` (43).
- Coverage (branch): slack_reply 91%.
- New emit site registered in the API-events §5 source_id pin
  (`tests/test_contract_nats_core.py`).
- Live approve/reject round-trip deferred to TASK-JNB-107 (operator phone +
  live forge; `JARVIS_SLACK_DECIDED_BY` must equal forge `expected_approver`).
