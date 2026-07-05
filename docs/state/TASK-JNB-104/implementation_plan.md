# Implementation Plan — TASK-JNB-104

**Task**: jarvis: Socket Mode reply path with operator-member-id authorization
**Feature**: FEAT-BF39 (UBS-003 v1.1) · Wave 8 · Complexity 7
**Mode**: standard `/task-work` (interactive, autonomous session)
**Date**: 2026-07-05
**Depends on**: TASK-JNB-103 (in_review, merged to main `0b2d1bf`) — consumes
its BUTTON_METADATA value JSON verbatim.

## Context established (Phase 1)

- TASK-JNB-103 landed: buttons with `action_id` `forge_approve` /
  `forge_reject`, `block_id` `forge_approval`, value JSON
  `{"request_id","build_id","correlation_id","approval_subject"}` (compact,
  <2000 chars). Settings fields `slack_app_token` (SecretStr|None),
  `slack_operator_user_id`, `slack_decided_by` already exist.
- slack-sdk's asyncio Socket Mode client
  `slack_sdk.socket_mode.aiohttp.SocketModeClient` is usable (aiohttp 3.13.5
  installed). It owns reconnects internally (`auto_reconnect_enabled`);
  listener registration happens once at start → no duplicate handlers on
  reconnect, and first-click-wins state lives on the handler instance →
  survives reconnect.
- Publish convention (mirrors `jarvis.tools.dispatch.queue_build`):
  `MessageEnvelope(source_id="jarvis", event_type=..., correlation_id=...,
  payload=<model dump>)` → `model_dump_json().encode()` →
  `await asyncio.wait_for(nats_client.js.publish(subject, bytes), timeout)`.
- `ApprovalResponsePayload` (nats-core): `request_id`, `decision`
  (approve|reject|defer|override), `decided_by` (min_length 1), `notes`.
  `EventType.APPROVAL_RESPONSE = "approval_response"`.
- The response subject is `approval_subject + ".response"` (AGENTS stream,
  limits retention — publish only; no PIPELINE consumer anywhere).
  TASK-JNB-103's own AGENTS subscriber skips 5-token subjects structurally,
  so jarvis never consumes its own responses.

## Files to create (2)

1. **`src/jarvis/infrastructure/slack_reply.py`** (~430 LOC)
   - **`parse_button_value(value: str) -> dict[str, str]`** — module-level
     (named by the task's seam test). `json.loads`; requires the four
     BUTTON_METADATA keys with non-empty `request_id` and
     `approval_subject`; raises `ValueError` on any malformed shape
     (callers catch → drop + log; never propagates further).
   - **`ApprovalResponsePublisher` Protocol** —
     `async publish(*, subject, payload, correlation_id)`.
   - **`NatsApprovalResponsePublisher`** — wraps `NATSClient`; builds the
     `MessageEnvelope` (source_id `"jarvis"`, event_type
     `approval_response`, correlation_id from the button value) and
     publishes with a bounded timeout. Raises on failure (the handler's
     publish-failure path needs to see it).
   - **`ApprovalReplyHandler`** + factory **`build_reply_handler(*,
     settings, publisher, web_client=None)`** (named by the seam test).
     `handle_block_actions(payload)` — the post-ack interaction handler,
     never raises (DDR-007):
     1. **Authorization first**: `payload["user"]["id"] !=
        settings.slack_operator_user_id` → WARN +
        `chat.postEphemeral` refusal to the clicking user; nothing
        published. The member id is the SOLE Slack-side gate.
     2. Extract the clicked action; `action_id` must be `forge_approve` /
        `forge_reject` (unknown → drop + log); `parse_button_value` on its
        `value` (ValueError → drop + log).
     3. **First-click-wins** keyed on `request_id` (in-memory set;
        client-side courtesy only — forge's dedup is authoritative,
        DDR-027: state lost on restart by design). Duplicate → drop + log,
        no publish.
     4. **Optimistic disable**: `chat.update` replaces the actions block
        with a plain_text "Recording <decision>…" section (original blocks
        taken from `payload["message"]["blocks"]`; wrapped, WARNING-only).
     5. **Publish** `ApprovalResponsePayload(request_id=<from value>,
        decision="approve"|"reject", decided_by=settings.slack_decided_by
        — VERBATIM, no trimming/casing)` to
        `approval_subject + ".response"`, envelope carrying the request's
        `correlation_id`.
     6. Success → `chat.update` shows the recorded decision in place
        (buttons stay removed). Failure → WARNING, un-mark
        first-click-wins, `chat.update` restores the ORIGINAL blocks
        verbatim (buttons re-enabled) so the operator can retry.
     No approval-window/expiry checks anywhere (forge-side only).
   - **`SlackSocketModeReplyClient`** — lifecycle component. `start()`
     (idempotent): constructs the aiohttp `SocketModeClient`
     (`app_token`, `web_client=AsyncWebClient(bot_token)`), registers ONE
     listener, `connect()`. Listener: **ack every envelope immediately**
     (`SocketModeResponse(envelope_id)`) before any authorization/parse/
     publish work; then route `type == "interactive"` +
     `payload.type == "block_actions"` to the handler (wrapped
     never-raise). `stop()`: bounded `close()`, never raises. Lazy
     slack-sdk socket-mode imports (keep module import light).
   - **`create_slack_reply_client(config, nats_client) -> ... | None`** —
     logged no-op (`None`) when `slack_app_token` OR
     `slack_operator_user_id` is absent (task AC), when `slack_bot_token`
     is absent (no web client for updates/ephemeral), or when
     `nats_client` is `None` (DDR-021-style; nothing to publish to).

2. **`tests/test_slack_reply.py`** (~700 LOC) — plain pytest, classes per
   task Test Requirements: `TestUnauthorizedClickRefused`,
   `TestAuthorizedApprovePublishes`, `TestAuthorizedRejectPublishes`,
   `TestDoubleClickPublishesAtMostOnce`,
   `TestMalformedActionPayloadDropped`,
   `TestReconnectNoDuplicateHandlersOrPublishes`,
   `TestNoOpModeWhenConfigAbsent`, `TestPublishFailureReenablesButtons`,
   plus `TestAckBeforeAuthorization` (call-order assertion on the mocked
   socket client), the two task-mandated seam tests
   (`BUTTON_METADATA` round-trip incl. max-size ids;
   `APPROVER_IDENTITY` verbatim decided_by), publisher envelope-shape
   tests (subject == `approval_subject + ".response"`, envelope
   correlation_id, event_type), and lifecycle wiring tests
   (`build_app_state` constructs iff app token + operator id + bot token +
   NATS; `shutdown` stops it) reusing the `_lifecycle_patches` pattern.
   SocketModeClient + AsyncWebClient + NATS js mocked with
   `unittest.mock.AsyncMock`; no live Slack or NATS anywhere.

## Files to modify (2)

3. **`src/jarvis/infrastructure/lifecycle.py`** (~45 LOC)
   `AppState.slack_reply_client` (default None); construct + start after
   the approval subscriber (7c3) with DDR-021 soft-fail; `shutdown` stops
   it before the sink (1b3).

4. **`docs/state/TASK-JNB-104/implementation_plan.md`** (this file).

## Explicitly out of scope

- Any nats-core change (zero — subjects/payloads all exist).
- Any PIPELINE-stream consumer (publish-only NATS interaction).
- Approval-window/expiry enforcement (forge-side only).
- Live round-trip validation → TASK-JNB-107 (operator phone + live forge;
  `JARVIS_SLACK_DECIDED_BY` must equal forge `expected_approver` first).

## Risks

- 🟡 slack-sdk aiohttp SocketModeClient API drift — mitigated: all client
  interactions behind our wrapper + lazy imports; tests mock the client.
- 🟡 Ephemeral refusal needs `channel` from the payload — fall back to
  `container.channel_id`; if absent, WARN-only (refusal is best-effort UX).
- 🟢 decided_by None (unset config): publish would fail payload validation
  (min_length 1) — guard: treat unset `slack_decided_by` as a no-op reply
  path at factory time? NO — task AC only gates on app token + operator
  id. Instead the handler refuses to publish with a WARN naming the
  missing config (fail loud in logs, buttons restored), since a silent
  wrong decided_by would be refused by forge anyway. Documented in tests.

## Estimates

- LOC: ~430 source + ~700 tests · one session · no new deps (slack-sdk +
  aiohttp already installed).

## Phase 2.5B outcome (2026-07-05)

Architectural review: **78/100 — approve with recommendations** (SOLID 82,
DRY 85, YAGNI 92). Both critical items folded in as binding invariants:

- **C1 — success-update failure after a durable publish**: if the publish
  succeeded but the "recorded decision" `chat.update` fails → WARNING
  only; first-click-wins STAYS marked; NEVER restore the original blocks
  (re-enabling a button for an already-recorded decision would reintroduce
  double-publish risk). The restore-on-failure branch fires ONLY on
  publish failure.
- **C2 — blanket wrap invariant**: EVERY `chat.*` call in the handler
  (ephemeral refusal, optimistic-disable, success-update, failure-restore)
  and the Socket Mode ack itself is wrapped in its own independent
  try/except → WARNING; a failure in one never short-circuits a later
  required step (publish still runs if optimistic-disable failed;
  failure-restore's own failure never raises). Consequence (intentional):
  `web_client=None` degrades gracefully — Slack UI updates become logged
  no-ops while authorization + publish still execute (this is what the
  task's own seam test exercises).

Adopted recommendations: first-click-wins check-and-mark is synchronous
(no `await` between membership check and insert — the SDK dispatches each
WS message via `asyncio.ensure_future`, so double-click = two concurrent
tasks; C1-TOCTOU precedent from slack_notifier.py applies); `decided_by`
presence guard promoted to explicit handler step 3b (before payload
construction, WARN + restore, no publish); ephemeral-refusal channel =
`payload["channel"]["id"]` falling back to
`payload["container"]["channel_id"]`, WARN-only if both absent; listener
registration BEFORE `connect()` with a comment citing the SDK internals
(listener list lives on the client object and is untouched by reconnects;
`process_messages()` starts in `__init__`).

Complexity 7 → FULL_REQUIRED checkpoint → auto-approved (autonomous
session; plan + arch review persisted here as the review artifact).


## Phase 5 outcome (2026-07-05) — multi-lens review workflow

3 review lenses + worktree-isolated adversarial verifiers (12 agents; no
shared-tree mutation this time — isolation applied per the JNB-103
lesson). 9 raw findings → 7 confirmed (1 duplicate cluster), 2 refuted.
All confirmed findings fixed:

- **CRITICAL — unbounded `connect()` hang**: slack-sdk's aiohttp
  `SocketModeClient.connect()` is a `while True` retry loop that never
  raises (swallows invalid_auth and network errors), so `await start()`
  could wedge `build_app_state` forever on a bad app token or Slack
  outage — the DDR-021 soft-fail except was unreachable, and the
  mock-based soft-fail test was false-green evidence. Fixed:
  `_CONNECT_TIMEOUT_SECONDS = 15.0` bound via `asyncio.wait_for`, with
  best-effort SDK-client close + `_client = None` on failure before
  re-raising, so the lifecycle soft-fails as designed. Two new tests
  drive the REAL `start()` (hanging connect → bounded raise + cleanup;
  full `build_app_state` completes with `slack_reply_client=None`).
- **MINOR — C1 cross-task race**: a failed attempt's restore
  `chat.update` could land after a concurrent retry's durable publish
  (SDK dispatches one task per WS message). Fixed with a handler-wide
  `asyncio.Lock` serializing check/mark → publish → update/restore; the
  ack stays outside the lock. Regression test pins the exact event order.
- **MINOR — missing `message.blocks`**: the optimistic disable would
  destroy buttons it could not restore (restore sent `blocks=None`).
  Fixed: optimistic disable and restore are skipped when the payload
  carries no original blocks; publish is unaffected. Tests added.
- **MINOR — listener-ordering assertion gap**: registration-before-
  connect is now pinned (listener count captured at connect-await time).

Refuted: partial-start `stop()` leak (superseded by the connect-failure
cleanup path), and one duplicate of the missing-blocks finding whose
harm-path analysis differed (the fix covers both readings).

## Plan audit (Phase 5.5)

Planned files all created/modified as specified; one extra file beyond
plan: `tests/test_contract_nats_core.py` — required by the pre-existing
emit-site count pin (the new `MessageEnvelope` publish site had to be
registered; 2 pre-existing SIM110s cleared for the modified-files lint
AC). LOC ~640 source (vs ~475 planned; review fixes + docstrings) and
~1030 tests (vs ~700). Severity: LOW → Approve (deviations traced to the
contract pin and confirmed review findings).

Final: suite 2527 passed / 2 skipped / 0 failed; `slack_reply.py` 91%
line/branch-inclusive coverage; ruff + format + mypy clean on all
modified files.

## Live-validation caveat

The live approve/reject round-trip (TASK-JNB-107) needs the operator's
Slack workspace/phone, a live forge build, and `JARVIS_SLACK_DECIDED_BY`
set to string-equal forge's `expected_approver` — not runnable in this
autonomous session.
