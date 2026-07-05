---
id: TASK-JNB-105
title: "jarvis: v1.1 reply-path scenario tests (plain pytest)"
status: in_review
created: 2026-07-03T15:30:00Z
updated: 2026-07-05T00:00:00Z
previous_state: in_progress
priority: high
task_type: testing
parent_review: TASK-REV-C951
feature_id: FEAT-BF39
version: v1.1
wave: 9
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: [TASK-JNB-104]
tags: [ubs-003, jarvis-notification-bridge, slack, v1.1]
---

# Task: jarvis: v1.1 reply-path scenario tests (plain pytest)

## Description

Plain pytest for the jarvis-observable v1.1 scenarios with mocked Socket Mode and a fake JetStream: unauthorized-responder refusal, duplicate click single-publish, approve-one-not-another (button metadata routing across two paused builds), unrecognised decision never offered nor published, buttons-disabled-after-decision, reply-after-ended (stale buttons -> refusal path), plus contract tests asserting the published envelope validates against the installed `nats_core` `ApprovalResponsePayload`. No pytest-bdd glue anywhere; a collect-only count assertion in the verify step; run via `.venv/bin/python -m pytest` from the jarvis repo root.

The system under test is the v1.1 reply path delivered by TASK-JNB-103 and TASK-JNB-104. On the jarvis side, a small subscriber on `agents.approval.forge.>` (AGENTS stream, limits retention, overlap legal; the 4-token filter never matches `.response`) captures `ApprovalRequestPayload.request_id` per `build_id` into a TTL'd pending map, deduped on `request_id` across forge boot-reconcile re-emits. The pause Slack message upgrades to Block Kit Approve/Reject buttons whose value JSON carries `{request_id, build_id, correlation_id, approval_subject}` (`approval_subject` arrives free on `BuildPausedPayload`), with `chat.update` replacing buttons in place when a defer-republish mints a refreshed `request_id`. A Socket Mode client (`JARVIS_SLACK_APP_TOKEN`, outbound WebSocket, no public endpoint) handles `block_actions`: it acks immediately; the sole Slack-side gate is `user.id == JARVIS_SLACK_OPERATOR_USER_ID` (mismatch: WARN + ephemeral refusal, nothing published); an authorized click publishes `ApprovalResponsePayload(request_id, decision approve|reject, decided_by=slack_decided_by)` to `approval_subject + '.response'` carrying the request's `correlation_id`, then `chat.update` disables the buttons. Local behaviour is first-click-wins, with forge-side `request_id` 300s dedup as the authoritative backstop; window/expiry-race enforcement stays exclusively forge-side, so this task tests only the jarvis-observable half of those races (stale button -> refusal path, no publish attempt on locally-known-dead requests).

Tests must be fully hermetic: mock the slack-sdk `SocketModeClient` surface (deliver synthetic `block_actions` payloads, capture ack/ephemeral/`chat.update` calls) and use a fake JetStream publish capture — no live Slack connection, no live NATS broker. The only real third-party dependency exercised is the installed `nats_core` package, used to validate the published envelope in the contract tests.

## Acceptance Criteria

- [ ] A test module (or modules) exists in the jarvis pytest test tree covering all six behavioural scenarios listed under Test Requirements, each as its own test class whose name mirrors the scenario name.
- [ ] Unauthorized-responder refusal: a `block_actions` event with `user.id != JARVIS_SLACK_OPERATOR_USER_ID` results in a WARNING log and an ephemeral refusal, and the fake JetStream records zero publishes.
- [ ] Duplicate click single-publish: two identical authorized clicks on the same button result in exactly one publish (local first-click-wins asserted on the fake JetStream capture).
- [ ] Approve-one-not-another: with two paused builds holding distinct button metadata, approving build A publishes exactly once to A's `approval_subject + '.response'` carrying A's `request_id` and `correlation_id`; nothing is published for build B and B's buttons remain live.
- [ ] Unrecognised decision: the rendered Block Kit message offers only Approve and Reject actions, and a crafted `block_actions` payload carrying any other decision value publishes nothing.
- [ ] Buttons-disabled-after-decision: after an authorized decision, `chat.update` is invoked replacing the buttons with a disabled/decided rendering.
- [ ] Reply-after-ended: a click whose `request_id` is absent from the pending map (build ended or entry expired) follows the refusal path and publishes nothing. **RECONCILED (Rich, 2026-07-05 — Option A "faithful test"):** the delivered JNB-104 `ApprovalReplyHandler` has NO pending map (`__slots__ = _decided_request_ids, _decision_lock, _publisher, _settings, _web_client`; `create_slack_reply_client` passes none) and publishes self-containedly from the button value JSON — this is the deliberate DDR-027 posture (handoff §6 "old buttons after a jarvis restart still work; the reply path needs no in-memory state to publish"), with forge as the authoritative refuser (correlation mismatch / request_id 300s dedup / expected_approver). There is therefore NO jarvis-local stale-refusal path, and adding one would redesign JNB-104 (forbidden here) and break the post-restart invariant. This AC's original "publishes nothing" premise is **superseded**: the scenario test asserts the DELIVERED behaviour — a well-formed, authorized, first-time "stale" click STILL PUBLISHES, documenting that staleness enforcement lives forge-side (TASK-JNB-106). No production change.
- [ ] Contract tests assert the published envelope deserializes and validates against the installed `nats_core` `ApprovalResponsePayload`, that `decided_by` equals `settings.slack_decided_by` verbatim, that `decision` is one of `approve|reject`, and that the publish subject is exactly `approval_subject + '.response'`.
- [ ] No `.feature` files and no `pytest-bdd` import anywhere in the tests added by this task.
- [ ] The verify step runs `.venv/bin/python -m pytest --collect-only -q` on the new test path(s) and asserts the collected count equals the number of tests written (pinned exact integer, not a minimum).
- [ ] Full suite green: `.venv/bin/python -m pytest` from the jarvis repo root passes with zero failures, with no live Slack or NATS connectivity required.

## Test Requirements

Plain pytest only — no pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror the spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

Explicit scenario list (each is one test class; the class name should be a direct CamelCase rendering of the scenario):

1. **Unauthorized responder refusal** — Socket Mode delivers a `block_actions` payload whose `user.id` does not equal `JARVIS_SLACK_OPERATOR_USER_ID`: assert WARNING logged, ephemeral refusal sent, zero JetStream publishes.
2. **Duplicate click single-publish** — the same authorized button is clicked twice: assert exactly one `ApprovalResponsePayload` publish on the fake JetStream (local first-click-wins), and both clicks are acked.
3. **Approve one, not another** — two paused builds each hold buttons with distinct value JSON `{request_id, build_id, correlation_id, approval_subject}`: approving build A routes the publish to A's `approval_subject + '.response'` with A's `request_id`/`correlation_id`; assert no publish references build B.
4. **Unrecognised decision never offered nor published** — assert the button blocks offer only `approve` and `reject`, and a synthetic action carrying an unknown decision value produces no publish.
5. **Buttons disabled after decision** — after an authorized approve or reject, assert `chat.update` replaced the interactive blocks with a non-interactive decided rendering.
6. **Reply after ended (stale buttons -> refusal path)** — a click carrying a `request_id` no longer present in the TTL'd pending map: assert refusal-path behaviour and zero publishes (forge remains the authoritative refuser for anything that slips past). **RECONCILED (see AC "Reply-after-ended" above):** the reply path holds no pending map (DDR-027), so this scenario tests the DELIVERED behaviour — a well-formed authorized stale click still publishes and forge is the sole refuser. The class name still mirrors the scenario ("ReplyAfterEnded"); the assertion is inverted from the original draft to match the implementation, not a redesign of it.

Plus **contract tests** (may be one class): construct the reply path end-to-end with the fake JetStream, trigger an authorized approve, then take the captured bytes and validate them against the installed `nats_core` `ApprovalResponsePayload` model — field-level asserts on `request_id`, `decision`, `decided_by == settings.slack_decided_by`, carried `correlation_id`, and the exact `.response` subject suffix.

Collect-only count assertion requirement: the verify step must run `.venv/bin/python -m pytest --collect-only -q <new test path(s)>` and compare the collected item count against a pinned expected integer recorded in the verify step itself; a mismatch is a hard failure (this is the guard against silently-uncollected tests that motivated dropping pytest-bdd).

Mocking strategy: patch/mock the slack-sdk `SocketModeClient` so tests inject `block_actions` request objects directly into the registered listener and capture `ack`, ephemeral responses, and `chat.update` calls; the JetStream publisher is a fake capturing `(subject, payload_bytes, headers)` tuples for assertion. Environment/config comes from `pydantic-settings` fields under the `JARVIS_` prefix (`slack_operator_user_id`, `slack_decided_by`, `slack_app_token`) set via test fixtures, never from the developer's real environment.

## Implementation Notes

- **Dependency**: TASK-JNB-104 — jarvis: Socket Mode reply path with operator-member-id authorization. This task tests that implementation as delivered; do not redesign it. If a behaviour under test is missing, that is a red test against TASK-JNB-104's output, not licence to change the contract here.
- **Single-consumer rule (workqueue err 10100)**: the PIPELINE stream tolerates exactly one consumer. The reply path's only NATS consumers are on the AGENTS stream (limits retention, overlap legal). Tests must not construct anything that implies a second PIPELINE consumer; the fake JetStream keeps this structurally impossible, but assertions should never encode a second-consumer expectation.
- **DDR-007 (never raise / best-effort)**: notification and reply-path failures are WARNING + continue; the SQLite ledger on the forge side is authoritative. Failure-path tests assert refusal/no-publish plus logging — never a raised exception propagating out of the handler.
- **DDR-027 (no replay, in-memory state)**: the pending-approval map and dedup state are in-process with TTLs; tests should exercise TTL/absence via direct state manipulation or injected clocks, not real sleeps.
- **Correlation-INDEPENDENT fan-out is deliberate**: the notification surface fires regardless of the correlation-map lookup (the phone is per-operator, not per-session). Do not write tests that require a correlation-map hit for a notification or reply to function; only the button value JSON carries `correlation_id`, and only the publish envelope must round-trip it.
- **Authorization seam**: the sole jarvis-side gate is `user.id == JARVIS_SLACK_OPERATOR_USER_ID`; `decided_by` must be `settings.slack_decided_by` verbatim (forge compares it against `expected_approver` by exact string equality — a mismatch silently refuses every phone approval, which is why the contract test pins the verbatim value).
- **Window/expiry enforcement is forge-side only**: jarvis tests cover the local refusal path for stale buttons; they must not attempt to assert approval-window semantics — those live in TASK-JNB-106 (forge repo).
- **Worktree scope**: the autobuild worktree for this task is jarvis-scoped and cannot read the sibling forge repo. Everything needed — scenario list, contract fields, subject shapes — is embedded in this file; validate the envelope against the *installed* `nats_core` package, never against forge sources.
- **Test runner**: always `.venv/bin/python -m pytest` from the jarvis repo root; the default interpreter lacks `nats_core`.
