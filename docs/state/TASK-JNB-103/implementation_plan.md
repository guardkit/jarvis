# Implementation Plan — TASK-JNB-103

**Task**: jarvis: approval-request capture + Block Kit approve/reject buttons
**Feature**: FEAT-BF39 (UBS-003 v1.1) · Wave 7 · Complexity 6
**Mode**: standard `/task-work` (interactive, autonomous session)
**Date**: 2026-07-05

## Context established (Phase 1)

- TASK-JNB-005's widened `ForgeNotification` is merged on main (`build_paused` /
  `build_cancelled` literals + optional `coach_score`, `rationale`, `gate_mode`,
  `approval_subject`, `cancelled_by`, `reason`). Verified in
  `src/jarvis/infrastructure/forge_notifications.py`.
- v1 `SlackNotifier` (bounded queue, 1 msg/s worker, 300s dedup, 429 backoff,
  DDR-007 never-raise) is merged in `src/jarvis/infrastructure/slack_notifier.py`.
- Wire contracts (nats-core 0.4.0, editable install — read-only reference):
  - `ApprovalRequestPayload`: `request_id`, `agent_id`, `action_description`,
    `risk_level`, `details: dict`, `timeout_seconds` (default 300). **No
    `build_id` field** — the build id is the 4th token of the request subject
    (`agents.approval.forge.{build_id}`, per `Topics.Agents.APPROVAL_REQUEST`
    and the task's seam test showing
    `approval_subject="agents.approval.forge.build-abc123"`).
  - Response subjects append `.response` (5 tokens) — a 4-token-only guard in
    the handler skips them structurally.
  - `MessageEnvelope.event_type == EventType.APPROVAL_REQUEST`
    (`"approval_request"`), `envelope.correlation_id` threads the request's
    correlation id.
- Gap found: the pause projection in `_handle_pause_or_cancelled` does **not**
  populate `build_id` (payload carries it; the projection drops it). The
  build_id join and the task's own seam test require it → must be added.
- `.env` already carries `JARVIS_SLACK_APP_TOKEN` and
  `JARVIS_SLACK_OPERATOR_USER_ID`; `JARVIS_SLACK_DECIDED_BY` is not yet set
  (config field still added; value is operator config aligned with forge
  `expected_approver` at TASK-JNB-107 live validation).

## Files to modify (5) — no new source modules

1. **`src/jarvis/config/settings.py`** (~15 LOC)
   Add three pydantic-settings fields under the existing `JARVIS_` prefix:
   - `slack_app_token: SecretStr | None = None`
   - `slack_operator_user_id: str | None = None`
   - `slack_decided_by: str | None = None`

2. **`src/jarvis/infrastructure/forge_notifications.py`** (~10 LOC)
   In `_handle_pause_or_cancelled`, extract `build_id` from the raw payload
   dict and thread it into both the sink notification and the CLI
   notification (frozen-model rule: optional field already exists on the
   model). Applies to both `build_paused` and `build_cancelled`.

3. **`src/jarvis/infrastructure/slack_notifier.py`** (~420 LOC)
   The task's file list places the whole approval surface here (no new module):
   - **`PendingApproval`** frozen dataclass: `request_id`, `build_id`,
     `correlation_id`, `approval_subject`, `timeout_seconds`,
     `captured_at_mono`.
   - **`build_pause_blocks(notification, pending=None) -> list[dict]`** —
     module-level rendering entry point (named by the task's seam test).
     Section blocks with `plain_text` text objects only (header line, stage,
     coach score with `"score unavailable"` for None, rationale chunked at
     ≤2900 chars/block); when `pending` is provided, append one `actions`
     block with Approve (primary) / Reject (danger) buttons, `action_id`s
     `forge_approve` / `forge_reject`, both carrying the same compact value
     JSON `{"request_id","build_id","correlation_id","approval_subject"}`
     (`json.dumps(..., separators=(",",":"))`). Helper
     `_build_button_value(...)` returns `None` (→ caller falls back to
     text-only) if the JSON would reach Slack's 2000-char action value limit.
   - **`SlackNotifier` state** (all in-process, monotonic clock via the
     existing `_monotonic` alias, evict-on-insert — DDR-027):
     - `_pending_approvals: dict[str, PendingApproval]` keyed by `build_id`,
       TTL = each entry's `timeout_seconds`.
     - `_seen_request_ids: dict[str, float]` — dedup across forge
       boot-reconcile re-emits, TTL = the request's `timeout_seconds`.
     - `_pause_messages: dict[str, _PauseMessageRecord]` keyed by `build_id`
       (`ts`, `notification`, `request_id | None`, `buttoned`, `posted_at_mono`)
       with a constant registry TTL (3600 s) — needed so a later
       defer-refresh / late request can `chat.update` the exact message.
   - **`SlackNotifier.capture_approval_request(request_id, build_id,
     correlation_id, approval_subject, timeout_seconds)`** — sync state
     mutation + async Slack side-effects; never raises (DDR-007):
     1. Evict expired entries in all three maps.
     2. Dedup: `request_id` already seen → drop (debug log), no second
        actionable message.
     3. Record in `_seen_request_ids`.
     4. If a pause message is already posted for `build_id`:
        - buttoned (defer-refresh): `chat.update` replaces the blocks in
          place with the new value JSON (operator never holds a stale
          button); registry record's `request_id` updated. No new message.
        - text-only (pause-before-request): `chat.update` upgrades the
          fallback message to the buttoned form (orderings converge on one
          buttoned message).
        In both cases the request is consumed — not left in the pending map.
     5. Otherwise store in `_pending_approvals` (request-before-pause).
   - **Worker `build_paused` branch** — `_post_pause_message(notification)`:
     look up `_pending_approvals` by `notification.build_id` (evict expired
     first); hit → post Block Kit message (`blocks=` + plain-text fallback
     `text=`), consume the pending entry, record the message `ts` with
     `buttoned=True`; miss (never captured, expired, or already consumed) →
     v1 text-only fallback posted unchanged, recorded with `buttoned=False`
     so a late request can upgrade it. Uses the existing 429/pacing loop.
   - **`ApprovalRequestsSubscriber`** — the only new jarvis-side NATS
     consumer. Binds `agents.approval.forge.>` on the AGENTS stream (limits
     retention — overlap legal; never touches the PIPELINE stream). Ephemeral
     push consumer, `deliver_policy=NEW` (DDR-027 no-replay: a restart loses
     the pending map by design; forge boot-reconcile re-emits repopulate it,
     absorbed by the request_id dedup). Handler `_on_message` never raises:
     - subject token gate: exactly 4 tokens (`agents.approval.forge.{build_id}`)
       → 5-token `.response` subjects are skipped structurally;
     - envelope parse + `event_type == "approval_request"` gate + `source_id`
       logging (WARN + continue on anything malformed — DDR-007);
     - `ApprovalRequestPayload` validation; `build_id` := subject token 4;
     - delegates to `SlackNotifier.capture_approval_request(...)` with
       `correlation_id=envelope.correlation_id`, `approval_subject=msg.subject`.
     `start()` idempotent / `stop()` bounded at 5 s, mirroring
     `ForgeNotificationsSubscriber`. Lazy `nats` imports (schema-import
     isolation, same pattern as forge_notifications).

4. **`src/jarvis/infrastructure/lifecycle.py`** (~45 LOC)
   - `AppState` gains `approval_subscriber: Any = None`.
   - `build_app_state`: after the sink starts and only when
     `nats_client is not None` **and** the sink is a live `SlackNotifier`,
     construct + start `ApprovalRequestsSubscriber(nats_client, notifier=sink)`
     with DDR-021-style soft-fail (WARN + continue, subscriber set to None).
   - `shutdown`: stop the approval subscriber right after the forge
     subscriber (before the sink stops so in-flight captures drain).

5. **`pyproject.toml`** (2 lines)
   Register `seam` and `integration_contract` pytest markers (used by the
   task-mandated seam tests).

## Files to create (1)

6. **`tests/test_slack_approval_buttons.py`** (~700 LOC)
   Plain pytest, class per behaviour (task Test Requirements):
   - `TestApprovalRequestCapture` — subscriber driven directly with synthetic
     envelopes; capture lands in the pending map; `.response` (5-token)
     subjects skipped; non-approval event types skipped.
   - `TestRequestIdDedup` — identical `request_id` re-emit (boot-reconcile)
     produces no second actionable message (chat.postMessage/chat.update call
     args asserted, not counts alone).
   - `TestTtlExpiry` — injectable `_monotonic` patch; pause after expiry
     renders the text-only fallback, not a dead button.
   - `TestBuildIdJoin` — two concurrently paused builds with distinct
     request_ids: each message carries only its own build's value JSON.
   - `TestDeferRefreshChatUpdate` — refreshed `request_id` for same build →
     `chat.update` in place, no second buttoned message, value JSON carries
     the new request_id.
   - `TestTextOnlyFallback` — no captured request → v1 text posted unchanged.
   - `TestOrderingTolerance` — request→pause and pause→request converge on
     one correct buttoned message.
   - `TestButtonValueJson` — exact 4-key shape, compact encoding, <2000 chars;
     over-limit value falls back to text-only.
   - `TestMalformedPayloadNeverRaises` — DDR-007 negative path (WARNING +
     continue, no exception out of the JetStream callback).
   - `TestPauseProjectionContract` (seam, `integration_contract
     ("WIDENED_FORGENOTIFICATION")`) — verbatim contract assertions from the
     task file adapted to the real constructor (correlation_id/feature_id/
     completed_at required): approval_subject round-trip, None-default
     optionals, `score unavailable` rendering, plain_text-only blocks.
   Slack client mocked with `AsyncMock`; time driven by patching
   `jarvis.infrastructure.slack_notifier._monotonic` (never
   `time.monotonic` — event-loop hang hazard documented in the module).
   Also extend `tests/test_forge_notifications_pause_cancelled.py` only if
   its assertions break (build_id now populated — additive, not expected to
   break).

## Explicitly out of scope

- Socket Mode reply path, click handling, ApprovalResponse publish →
  TASK-JNB-104 (consumes this task's BUTTON_METADATA contract).
- Any PIPELINE-stream consumer change (single-consumer rule, err 10100).
- Jarvis-side approval-window/expiry enforcement beyond the TTL map
  (forge-side only).
- Live Slack validation (TASK-JNB-107; needs operator phone + live forge).
- nats-core changes (zero required — `approval_subject` arrives free).

## Risks

- 🟡 Envelope `correlation_id` on approval requests could in principle be
  empty → button value falls back to the pause notification's
  correlation_id at assembly time.
- 🟡 `chat.update` needs the original blocks → registry record stores the
  source notification so blocks are rebuilt deterministically.
- 🟢 AGENTS stream availability: subscriber start is soft-fail (WARN +
  text-only fallback everywhere) — DDR-007/DDR-021 preserved.

## Estimates

- LOC: ~490 source + ~700 tests · Duration: one session · No new deps
  (slack-sdk already present from TASK-JNB-001).

## Phase 2.5B outcome (2026-07-05)

Architectural review: **68/100 — approve with recommendations** (SOLID 68,
DRY 74, YAGNI 87). Two must-fix items, both folded into this plan before
implementation:

- **C1 (TOCTOU race capture ↔ worker)** — all map mutations happen
  synchronously (never across an `await`); Slack calls are issued only after
  state is settled. Concretely: `_post_pause_message` pops the pending entry
  and writes the `_pause_messages` record (with `ts=None` in-flight marker)
  *before* awaiting `chat.postMessage`, then sets `ts` and **reconciles**: if
  a concurrent capture changed the record's `request_id`/`buttoned` during
  the await, one `chat.update` brings the posted message to the settled
  state. `capture_approval_request` mutates the record synchronously first;
  when `ts is None` (post in flight) it issues no Slack call — the worker's
  reconcile step converges. A text-only post never overwrites an existing
  buttoned record (the buttoned message stays the single actionable anchor).
  A dedicated concurrency test (`TestConcurrentCaptureAndPost`) forces this
  interleaving with a delayed mocked Slack client.
- **C2 (DDR-007 on capture-path `chat.update`)** — every Slack call on the
  capture path is wrapped try/except (SlackApiError + Exception → WARNING +
  continue), single attempt, no retry loop (a missed update is a UX-only
  stale button; forge safely refuses it). `_on_message` gets the same outer
  catch-all backstop as `ForgeNotificationsSubscriber._on_message`.

Adopted recommendations: shared `_evict_expired` helper across the three
maps; `_pause_messages` swept from both entry points; AGENTS-stream
retention + `DeliverPolicy.NEW` rationale documented inline (mirroring the
PIPELINE 10101 comment style); `ForgeNotification.build_id` docstring
updated for paused/cancelled; text-only fallback keeps using the existing
`_render()` verbatim (byte-identical v1 message — deliberate divergence from
`build_pause_blocks`, documented); §N section-header convention inside
slack_notifier.py. Deferred as optional polish: `ApprovalCapturable`
Protocol (wiring layer already tolerates concrete coupling).

Complexity 6 → QUICK_OPTIONAL checkpoint → auto-approved (autonomous
session, `approved_by: timeout-equivalent`).

## Phase 5 outcome (2026-07-05) — multi-lens review workflow

4 review lenses (concurrency, contract, regression, test-quality) + one
adversarial verifier per finding (23 agents). 15 raw findings → 12
confirmed, 3 refuted. All confirmed findings fixed in-session:

- **Multi-gate supersede** (major): a second pause of the same build now
  supersedes the previous pause message (old buttons stripped via one
  `chat.update`); the capture path also parks every request in the
  pending map since a defer-refresh is indistinguishable from the next
  gate's early request. Regression tests added for both orderings.
- **Failed-post recovery** (major): a lost `chat.postMessage` re-parks
  the consumed approval (remaining TTL) and clears its dedup entry
  (`_repark_lost_approval`).
- **Retry-After parse guard** (major, reproduced): malformed
  `Retry-After` (e.g. HTTP-date) no longer raises out of the 429 handler.
- **`stage_label` contract key** (major, pre-existing TASK-JNB-005 bug):
  the pause projection read payload key `stage` but BuildPausedPayload
  serializes `stage_label` — real forge traffic never populated the
  stage line. Fixed with contract-key-first fallback; seam test updated
  to the real key.
- Test-quality fixes: subscriber `start()` now pins `cb` identity +
  `DeliverPolicy.NEW`; re-emit dedup asserts first-wins TTL; fallback
  test uses an explicit expected string (not a `_render` self-oracle);
  dedup-window eviction covered; two real `build_app_state` wiring tests
  (subscriber constructed with NATS + live SlackNotifier; not with
  NoOpSink); `tests/test_v1_scenario_matrix.py` lint debt cleared
  (29 → 0) to satisfy the modified-files lint AC.

Refuted (not real): un-serialized concurrent `chat.update` (single
push-subscription callback serializes captures); failed-post
"permanently disables re-emit" variant (superseded by the re-park fix);
"wiring gate is `if False`" (a transient artifact of a verifier's
mutation testing on the shared worktree, observed mid-mutation by a
sibling reviewer — tree verified intact afterwards).

## Plan audit (Phase 5.5)

Planned files all touched as specified. Deviations (documented):

- `tests/test_v1_scenario_matrix.py` — not in plan; pre-existing
  hard-coded macOS worktree cwd made the suite red on this machine
  (portability fix) + lint cleanup required by the modified-files AC.
- `.env.example` — +4 doc lines for `JARVIS_SLACK_DECIDED_BY` (no secret).
- LOC over estimate (~900 gross in slack_notifier.py vs ~420 planned)
  — review fixes + docstrings + formatter rewrap; no scope creep in
  behaviour (all additions trace to task ACs or confirmed findings).

Severity: LOW-MEDIUM → Approve (autonomous session; deviations justified
above). Final: suite 2483 passed / 2 skipped / 0 failed; modified files
ruff + format clean; mypy delta vs HEAD zero.

## Live-validation caveat

The task's live approve/reject round-trip against a forge approval
request (fable plan ACTION 4 tail) requires the operator's Slack
workspace/phone and a live forge build — deferred to TASK-JNB-107 /
operator session. `JARVIS_SLACK_DECIDED_BY` must be set in `.env` to
match forge `expected_approver` before that test (documented in
`.env.example`).
