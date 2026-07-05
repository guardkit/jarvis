# Handoff: complete the FEAT-BF39 v1.1 live approve/reject round-trip

**Written**: 2026-07-05, end of the jarvis ACTION-4 Fable session (context
nearly full — this doc is the bridge to a fresh conversation).
**Goal for the next session(s)**: get from "jarvis reply path code-complete"
to **TASK-JNB-107 live validation passed** (operator taps Approve/Reject on
the phone and forge resumes/cancels a real build), with
**TASK-JNB-OPS-001** (secrets out of repo `.env`) done before any live
Slack traffic.

Read this top-to-bottom before doing anything. The single most important
correction to the summary you may have seen: **the live test is NOT the
next step — the forge half of the loop is not built yet** (verified
2026-07-05: forge TASK-JNB-101/102/106 are still in
`forge/tasks/backlog/jarvis-notification-bridge/`, and jarvis TASK-JNB-105
is still in `jarvis/tasks/backlog/jarvis-notification-bridge/`).

---

## 1. Where things stand (verified 2026-07-05)

### Built and committed (jarvis main — all quality gates green)

| What | Commit(s) | State |
|---|---|---|
| TASK-JNB-103 — approval-request capture + Block Kit Approve/Reject buttons | `0b2d1bf` | `tasks/in_review/` |
| TASK-JNB-104 — Socket Mode reply path + operator authorization | `51305d7` + `8f52775` | `tasks/in_review/` |

Suite at handoff: **2527 passed / 2 skipped / 0 failed** (run:
`.venv/bin/python -m pytest` from jarvis repo root). Plans, arch reviews,
multi-lens review outcomes, and plan audits are in
`docs/state/TASK-JNB-103/implementation_plan.md` and
`docs/state/TASK-JNB-104/implementation_plan.md` — read both if you touch
this code; they record binding invariants (C1/C2) the tests enforce.

Earlier v1 work (JNB-001..008, merged in FEAT-28FF) provides the outbound
notify path (SlackNotifier: bounded queue, 1 msg/s pacing, 300s dedup,
429 backoff). nats-core **0.5.0** is on its `origin/main` (needed by other
lanes; not by this one — the approval loop needed **zero nats-core
changes**).

### NOT built (blocking TASK-JNB-107, in dependency order)

1. **jarvis TASK-JNB-105** (wave 9) — "v1.1 reply-path scenario tests".
   File: `jarvis/tasks/backlog/jarvis-notification-bridge/TASK-JNB-105-*.md`.
   NOTE: `tests/test_slack_reply.py` (43 tests, written with JNB-104)
   already covers most of what 105's spec asks for. The right move is a
   short `/task-work TASK-JNB-105` that AUDITS 105's ACs against existing
   coverage and adds only the gaps — do not duplicate.
2. **forge TASK-JNB-101** (wave 7) — ApprovalSubscriber **production
   wiring** into forge-serve. The subscriber class EXISTS and is tested
   (`forge/src/forge/adapters/nats/approval_subscriber.py`) but nothing
   constructs it in the forge-serve runtime yet. This is where
   `expected_approver` gets wired from config (see §3).
3. **forge TASK-JNB-102** (wave 8) — emit `build-cancelled` on CANCELLED
   transitions (closes ASSUM-010; without it the phone never sees the
   reject/window-breach terminal signal).
4. **forge TASK-JNB-106** (wave 9) — scenario tests over the production
   wiring.
5. **TASK-JNB-107** (wave 10, `operator_handoff`) — the live validation
   itself. Task file:
   `jarvis/tasks/backlog/jarvis-notification-bridge/TASK-JNB-107-*.md` —
   it contains the full live script and troubleshooting notes; treat it as
   authoritative for the run.

**TASK-JNB-OPS-001** (`jarvis/tasks/backlog/TASK-JNB-OPS-001-*.md`,
`operator_handoff`) is independent of the build order but MUST land before
any live Slack traffic — see §4.

### Session/lane discipline (fleet rules that bit us before)

- One repo per session (Decided #5 in the fable-window plan). Forge tasks
  need a session opened in `~/Projects/appmilla_github/forge`; jarvis tasks
  in jarvis. Check
  `ai-transition/docs/fable-window-execution-plan-2026-07-04.md` (status
  snapshot + dated notes) before starting — another session may have
  claimed a lane. Add a dated claim note there if you take one.
- Read `ai-transition/docs/decisions/REGISTER.md` before architectural
  changes (CLAUDE.md rule in every repo).
- Commit immediately after writing — uncommitted files do not survive repo
  syncs.

---

## 2. The loop, end to end (what the code actually does)

```
forge build hits a gate
  ├─ publishes ApprovalRequestPayload on  agents.approval.forge.{build_id}   (AGENTS stream)
  └─ publishes BuildPausedPayload on      pipeline.build-paused.{feature_id} (PIPELINE stream)
jarvis ApprovalRequestsSubscriber (agents.approval.forge.>, DeliverPolicy.NEW)
  └─ captures request_id/correlation_id/subject into a TTL pending map keyed by build_id
jarvis ForgeNotificationsSubscriber → SlackNotifier worker
  └─ pause message posted with Block Kit Approve/Reject buttons
     (join purely on build_id; text-only fallback when no request captured)
operator taps a button (phone)
jarvis SlackSocketModeReplyClient (Socket Mode, outbound WS)
  ├─ acks the envelope FIRST
  ├─ sole Slack-side gate: payload.user.id == JARVIS_SLACK_OPERATOR_USER_ID
  ├─ first-click-wins under a handler lock
  └─ publishes ApprovalResponsePayload(request_id, decision, decided_by)
     to  {approval_subject}.response  with the request's correlation_id
forge ApprovalSubscriber (await_response) — four-step validation chain:
  payload validation → decided_by vs expected_approver → correlation_id match → request_id 300s dedup
  └─ approve → mark_resume_pending → build-resumed…terminal notifications
     reject  → CANCELLED in SQLite ledger → build-cancelled (needs JNB-102)
```

Load-bearing contract details (all pinned by tests — don't change casually):

- **BUTTON_METADATA**: both buttons carry the same compact value JSON
  `{"request_id","build_id","correlation_id","approval_subject"}`
  (< 2000 chars); `action_id`s are `forge_approve` / `forge_reject`,
  `block_id` `forge_approval`. Producer:
  `slack_notifier._build_button_value`; consumer:
  `slack_reply.parse_button_value`. A cross-module seam test pins
  producer→consumer compatibility.
- **build_id is the 4th token** of the approval subject
  (`agents.approval.forge.{build_id}`) — `ApprovalRequestPayload` has no
  build_id field. 5-token `.response` subjects are skipped structurally by
  the jarvis subscriber (so jarvis never eats its own responses).
- **Streams**: everything approval-related is on the AGENTS stream (limits
  retention — consumer overlap legal, publish-only responses). The
  PIPELINE stream keeps exactly ONE ephemeral jarvis consumer — any
  `err_code 10100` in boot logs is a hard failure.
- **Envelope**: `MessageEnvelope(source_id="jarvis",
  event_type="approval_response", correlation_id=<from button value>)`.
  The emit site is registered in `tests/test_contract_nats_core.py`'s
  count-pinned `_EMIT_SITES` — a new emit site anywhere in jarvis must be
  added there or the suite fails.
- **In-memory only (DDR-027)**: pending map, dedup windows, first-click
  state all die on jarvis restart by design; forge boot-reconcile re-emits
  repopulate requests; forge's request_id dedup is the authoritative
  double-publish guard.
- **DDR-007**: nothing in the notify or reply path may raise into a
  JetStream callback, the Socket Mode client, or the supervisor loop.

Hard-won fixes already in (do not regress; each has a regression test):

- slack-sdk's `SocketModeClient.connect()` is an **infinite retry loop
  that never raises** — `start()` bounds it (`_CONNECT_TIMEOUT_SECONDS
  = 15.0`) and lifecycle soft-fails, else a revoked app token bricks
  supervisor boot.
- Multi-gate builds: a new `build_paused` **supersedes** the previous pause
  message (old buttons stripped via one `chat.update`).
- A failed buttoned post **re-parks** the approval and clears its dedup
  entry (`_repark_lost_approval`).
- Pause projection reads payload key **`stage_label`** (the
  BuildPausedPayload contract key) — the old `stage` read was a real bug;
  `stage` is kept only as a legacy-synthetic fallback.
- Reply handler: decision sequence (check/mark → publish → update/restore)
  runs under an `asyncio.Lock`; after a **durable publish the original
  blocks are never restored**; optimistic disable is skipped when the
  interaction payload has no `message.blocks`.

---

## 3. Config alignment — the thing that silently breaks everything

jarvis side (`JarvisConfig`, prefix `JARVIS_`, fields in
`src/jarvis/config/settings.py`):

| Env var | Used by | State in repo `.env` (2026-07-05) |
|---|---|---|
| `JARVIS_SLACK_BOT_TOKEN` | notifier + reply web client | present (secret — see OPS-001) |
| `JARVIS_SLACK_CHANNEL_ID` | notifier | present |
| `JARVIS_SLACK_APP_TOKEN` | Socket Mode reply client | present (secret) |
| `JARVIS_SLACK_OPERATOR_USER_ID` | reply authorization gate | present |
| `JARVIS_SLACK_DECIDED_BY` | published `decided_by` | **ABSENT — must be set before the live test** |

forge side: `expected_approver` is a field on the ApprovalSubscriber deps
(`forge/src/forge/adapters/nats/approval_subscriber.py`, dataclass field
`expected_approver: str | None = None`). **`None` = permissive mode** (any
decided_by accepted — fine for dev, but JNB-107's AC explicitly wants the
alignment *proven*, so wire it to a real value in TASK-JNB-101 and set
both sides). How it surfaces as forge config is TASK-JNB-101's decision —
whatever key that becomes, its value must **string-equal
`JARVIS_SLACK_DECIDED_BY` verbatim** (no trimming/casing — jarvis
publishes it untouched, forge compares `!=`). Suggested value: something
identity-pinned like `rich-slack-operator`.

Failure signature of a mismatch: **Approve does nothing** — jarvis logs
`slack_reply_decision_published`, forge logs
`approval_subscriber: unrecognised responder ... NOT resuming`, build
stays paused. JNB-107's notes say: if Approve does nothing, check these
two values first.

Also note: `slack_reply` behavior when `JARVIS_SLACK_DECIDED_BY` is unset
is a **loud WARN + no publish + buttons restored** (`slack_reply_decided_by_unset`)
— deliberate (task AC only gates the no-op factory on app token +
operator id).

---

## 4. TASK-JNB-OPS-001 — do this before any live Slack traffic

Why it exists: during FEAT-28FF (2026-07-03), autobuild worktree agents
read the real bot token from the repo-adjacent gitignored `.env` and
posted ~a dozen synthetic messages to the live `#forge-builds` channel.
Worktrees do NOT isolate secrets.

Operator steps (task file is authoritative:
`jarvis/tasks/backlog/TASK-JNB-OPS-001-move-slack-secrets-out-of-repo-env.md`):

1. Move `JARVIS_SLACK_BOT_TOKEN` / `CHANNEL_ID` / `APP_TOKEN` /
   `OPERATOR_USER_ID` — **and add the new `JARVIS_SLACK_DECIDED_BY`** —
   out of `jarvis/.env` into `~/.config/guardkit/jarvis.env` on BOTH hosts
   (the GB10 systemd unit `jarvis-serve-nats` already loads that file via
   `EnvironmentFile`; on the Mac export per-session or mirror the file).
2. pydantic-settings resolution: real env vars beat `.env` values, so the
   unit's EnvironmentFile wins by construction. Verify with a boot log
   check (below).
3. **Rotate the bot token** afterwards (it was readable by worktree
   agents).
4. Restart `jarvis-serve-nats`; confirm in logs:
   `slack_notifier_started` (not `slack_sink_no_op`),
   `jarvis_approval_subscriber_started`, and
   `jarvis_slack_reply_started` (not `slack_reply_no_op`) — the last one
   proves all four reply-path vars + NATS resolved.

The jarvis serve entrypoint is `serve-nats`
(`src/jarvis/cli/main.py`, `@main.command("serve-nats")`).

---

## 5. Recommended execution order for the new conversation(s)

**Step 0 — orient (any repo).** Read the fable-window plan
(`ai-transition/docs/fable-window-execution-plan-2026-07-04.md`) status
snapshot + latest dated notes; confirm nobody else has claimed these
lanes. Note: ACTION 6 (jarvis FEAT-SPL-001) also wants a jarvis session —
distinct from this work; don't conflate.

**Step 1 — jarvis session: `/task-work TASK-JNB-105`.** Audit its ACs
against `tests/test_slack_reply.py` + `tests/test_slack_approval_buttons.py`
first; implement only the delta. Expect this to be small. Move to
in_review, commit.

**Step 2 — forge session: `/task-work TASK-JNB-101`, then `TASK-JNB-102`,
then `TASK-JNB-106`.** These are forge-repo tasks; their task files are in
`forge/tasks/backlog/jarvis-notification-bridge/` and are written to be
self-contained (the JNB-107 description also summarizes the intended
wiring: subscriber constructed in the forge-serve runtime, injected as the
typed `ApprovalGateDeps.subscriber` at `gating/wrappers.py:396`, consumed
by the existing `await_response` call sites at `wrappers.py:556/801`;
102 triggers the existing `publish_build_cancelled`
(`pipeline_publisher.py:272`) from CANCELLED transitions incl.
REASON_MAX_WAIT and `CliSteeringHandler.handle_cancel`). Wire
`expected_approver` from forge config here (§3). I have NOT read those
task files in depth — trust them over this summary where they differ.

**Step 3 — operator: TASK-JNB-OPS-001** (§4), including setting
`JARVIS_SLACK_DECIDED_BY` == forge's expected_approver value, then restart
both services on the deployed commits and re-verify the perishable
prerequisites (bot invited to `#forge-builds`, healthy
ships-computer-nats broker, both suites green on deployed commits).

**Step 4 — operator + assistant: TASK-JNB-107 live run.** Follow the task
file's script exactly (it is `operator_handoff` — the assistant preps,
watches logs, and reduces any failure to a failing plain-pytest scenario;
the operator taps). The four live scenarios:
1. Approve loop: gated toy build → pause message with live buttons on the
   phone → tap Approve → build-resumed then terminal notification;
   buttons disabled in place.
2. Reject loop: second build → tap Reject → SQLite shows CANCELLED
   (check SQLite FIRST, then expect the phone signal — that order; ledger
   is authoritative per DDR-007) → build-cancelled on the phone.
3. Unauthorized click: non-operator Slack account taps → ephemeral
   refusal, WARN log, nothing published, build still paused and still
   approvable.
4. Window breach: let one pause exceed the approval window
   (REASON_MAX_WAIT) → forge cancels → phone terminal signal.
Plus: every notification exactly once; **zero `err_code 10100`** across
the session's jarvis logs. Then `/task-complete TASK-JNB-107` and mark
v1.1 complete (update the fable plan's UBS-003 row: Gate G1 → PASS).

---

## 6. Live-run gotchas (from the task files + this session's findings)

- **Briefly-stale button is UX-only**: a forge defer-republish can outrun
  the `chat.update` refresh; forge safely refuses the stale request_id —
  wait for the refreshed message and tap again. Not a defect.
- **Correlation-INDEPENDENT fan-out**: the phone shows events for ALL
  builds, not just yours — don't misread others' events as duplicates.
- **jarvis restart mid-window**: pending map dies (DDR-027);
  `DeliverPolicy.NEW` means requests published while jarvis was down are
  not replayed — forge boot-reconcile re-emits repopulate. A pause whose
  request was lost renders the text-only fallback (CLI approval still
  works). Cosmetic double-posts after restart are tolerable; missing or
  wrong-order lifecycle signals are not.
- **Old buttons after a jarvis restart still work**: the value JSON is
  self-contained — the reply path needs no in-memory state to publish.
- **Approve does nothing** → check `decided_by`/`expected_approver`
  alignment first (§3), then forge logs for the four-step chain refusals
  (unrecognised responder / correlation mismatch / dedup).
- **Supervisor won't boot with Slack configured** → should be impossible
  now (bounded connect, 15s + soft-fail), but if boot is slow by ~15s,
  that's the reply client timing out against an unreachable Slack — check
  `jarvis_slack_reply_start_failed` in logs; the supervisor must still
  come up with `slack_reply_client=None`.

## 7. Process lessons for the new session (cheap to honor, expensive to relearn)

- `/task-work` flow that worked twice here: plan →
  architectural-reviewer subagent (fold its critical items into the plan
  BEFORE coding) → implement → full suite + ruff + ruff format + mypy →
  multi-lens review Workflow (3-4 lenses, adversarial verifiers) → fix
  confirmed findings → plan audit → in_review → commit.
- Give review/verify agents that might mutate code **`isolation:
  'worktree'`** — a JNB-103 verifier mutation-tested the live tree and a
  sibling reviewer reported the transient mutation as a real defect. AND:
  worktree isolation leaves changed worktrees under `.claude/worktrees/`
  — now gitignored in jarvis, but run `git worktree list` + prune before
  staging, and never `git add -A` blindly after a workflow.
- `uv.lock` keeps re-locking itself (sibling nats-core at 0.5.0);
  `git checkout uv.lock` before committing unless your task owns the bump.
- Pre-existing-failure honesty: verify a suspect failure exists on HEAD
  (`git stash` trick) before attributing it to your diff; jarvis had a
  hard-coded macOS worktree path in `test_v1_scenario_matrix.py` (fixed in
  `0b2d1bf`).

## 8. Key file index

| Thing | Path |
|---|---|
| Reply path (JNB-104) | `jarvis/src/jarvis/infrastructure/slack_reply.py` |
| Buttons + capture (JNB-103) | `jarvis/src/jarvis/infrastructure/slack_notifier.py` (§1b, §2b) |
| Pause/cancelled projection | `jarvis/src/jarvis/infrastructure/forge_notifications.py` (`_handle_pause_or_cancelled`) |
| Lifecycle wiring (7c2/7c3, 1b2/1b3) | `jarvis/src/jarvis/infrastructure/lifecycle.py` |
| Settings | `jarvis/src/jarvis/config/settings.py`; keys documented in `jarvis/.env.example` |
| Tests | `jarvis/tests/test_slack_approval_buttons.py`, `test_slack_reply.py`, emit-site pin in `test_contract_nats_core.py` |
| Plans + review records | `jarvis/docs/state/TASK-JNB-10{3,4}/implementation_plan.md` |
| Forge subscriber (exists, unwired) | `forge/src/forge/adapters/nats/approval_subscriber.py` |
| Forge tasks to build | `forge/tasks/backlog/jarvis-notification-bridge/TASK-JNB-10{1,2,6}-*.md` |
| Live validation script | `jarvis/tasks/backlog/jarvis-notification-bridge/TASK-JNB-107-*.md` |
| Env hygiene | `jarvis/tasks/backlog/TASK-JNB-OPS-001-*.md` |
| Fleet plan / lane claims | `ai-transition/docs/fable-window-execution-plan-2026-07-04.md` |
| Wire contracts (read-only) | `nats-core/src/nats_core/events/_agent.py`, `_pipeline.py`, `envelope.py`, `topics.py` |
