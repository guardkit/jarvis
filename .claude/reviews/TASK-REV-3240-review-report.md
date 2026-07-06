# Review Report: TASK-REV-3240 — Plan: Slack Planning Intake (FEAT-SPL-001)

**Mode**: decision · **Depth**: standard · **Date**: 2026-07-06
**Method**: 3-lens multi-agent review (architecture-fit / red-team / plan-critique),
9 critical/high findings adversarially verified by independent agents (12 agents total).
**Scores**: architecture 86/100 · red-team residual-risk 82/100 · plan-confidence 82/100
**Verdict**: **PROCEED** — recommended approach below, with the listed defenses encoded as task ACs.

## Executive Summary

FEAT-SPL-001 is architecturally well-prepared: the wire contract shipped in nats-core
0.5.0, the JNB-104 Socket Mode listener already acks-then-filters by request type, and
every sub-decision has a direct house precedent (JNB-104 publisher shape, JNB-103 TTL
map, DDR-025 bounded publish, DDR-007/C2 best-effort Slack calls). One topology fact
dominates: **Slack load-balances envelopes across all open Socket Mode connections of an
app, and the existing listener acks every envelope before type-filtering** — so a second
connection would silently ack-and-drop ~half of approval clicks, and a second appended
listener would double-ack every envelope. Intake must ride the one existing connection
via request-type routing inside the single `_on_request`.

## Recommended Approach (Option A — selected)

Ride the existing JNB-104 Socket Mode connection via a request-type router seam
(optional `events_api` handler injected into `SlackSocketModeReplyClient`, dispatched
inside the single ack-first `_on_request`) with a **union no-op gate**; all intake logic
in a new `slack_planning_intake.py` module mirroring the `NatsApprovalResponsePublisher`
publish shape (config-sourced DDR-025 timeout) and the `slack_notifier` TTL-map dedup
precedent.

**Options rejected**:
- **B — second Socket Mode connection**: correctness bug, not a trade-off. Slack
  load-balances envelope deliveries across open connections; ack-first listeners would
  ack-and-drop the other feature's traffic (never redelivered). No safe configuration.
- **C — full connection-ownership refactor** (shared `SlackSocketModeConnection`
  registry): architecturally purest, but rewrites the JNB-104 lifecycle class, factory,
  wiring, and test suites days before the OPS-001/JNB-107 live validation, for zero v1
  behavioral difference. Option A's handler-map seam converts to this shape mechanically
  if FEAT-SPL-003 adds a third handler.

## Verified Findings (survivors of adversarial verification)

| # | Sev (verified) | Finding | Required action |
|---|---|---|---|
| F1 | **HIGH (confirmed ×2)** | Factory no-op gate coupling: `create_slack_reply_client` returns None when `slack_operator_user_id` unset → the sole process-wide connection never starts → a fully-configured intake is **silently dead**, logged only as `slack_reply_no_op` blaming the other feature. Spec asymmetry: no scenario covers reply-unconfigured + intake-configured. Same silent-config class as the JARVIS_SLACK_DECIDED_BY scar. | Union gate: connection starts when app_token + bot_token + NATS + (reply-path config **OR** planning config); operator id gates only the interactive handler; planning keys gate only the events_api handler; each unconfigured feature logs its own reason (`slack_planning_intake_no_op`). Test all 4 config permutations. |
| F2 | MEDIUM | Single-listener routing: appending a second `socket_mode_request_listener` double-acks every envelope (SDK fans out to ALL listeners, `async_client.py:151-157`) and forks the reconnect invariant. | Route inside the ONE `_on_request`: ack once, then dispatch `interactive` → ApprovalReplyHandler, `events_api` → intake handler (None-safe). Regression test: exactly one ack per envelope; JNB-105 approval scenarios pass with intake active. |
| F3 | MEDIUM | Self-ack loop / bot filter: modern bot posts arrive **subtype-free** (`bot_id`/`app_id` set, `subtype=bot_message` is legacy-only). ASSUM-006's subtype-only filter would let jarvis's own acks reach the identity gate → one spurious "refusal" per successful intake polluting the DF-009 audit log. | Pin the filter chain order: channel → `bot_id`/`app_id`/subtype present → DEBUG drop (never a "refusal") → `thread_ts` present → drop → identity gate (the ONLY refusal log) → blank-text pre-check → ValidationError backstop. Scenario-10 fixture must be realistic: no subtype, `bot_id` set, user = bot's user id. |
| F4 | MEDIUM | Wire caveat (runtime-verified): Pydantic never runs `_adapter_required_for_jarvis` when `originating_adapter` is omitted (default, no `validate_default`). NB: the house `model_dump(mode="json")` (no `exclude_none`) puts `"originating_adapter": null` on the wire, which consumer-side re-validation catches — silence requires deviating to `exclude_none`. | Hard-code `originating_adapter='slack'` (constant, never config/derived). Contract test asserts the field == 'slack' on the RECONSTRUCTED wire bytes, plus `originating_user` == configured member id. |
| F5 | MEDIUM | Dedup race: slack-sdk schedules WS deliveries as tasks; a redelivery can be in flight concurrently with the original. Check-and-mark spanning an await queues two runs. | Synchronous check-and-mark before the first await (JNB-104 decision-lock lesson). Key: `event_id`, fallback `channel:ts`. dict[str, float] + monotonic clock, TTL 300s, cap ~1000, evict-on-insert (JNB-103 precedent). **Un-mark on publish failure** (nothing was queued; Slack redelivery then retries — mirrors slack_reply discard-on-publish-failure). |
| F6 | MEDIUM | Log hygiene: `request_text` is human free text that may contain secrets (ABL-001 precedent). Spec scenarios 7/8 read naturally as "log the body". | Hard AC: **no intake log event ever contains message text** — records carry {channel, ts, user_id, event_id, correlation_id, text_length, reason} only. Tests assert log fields on discard/refusal/duplicate/failure paths. Scenarios 7/8 interpreted as metadata records. |
| F7 | MEDIUM | Channel/config drift: (a) planning channel == notification channel is plausible and confusing; (b) `message.channels` covers PUBLIC channels only — a private #factory-planning needs `message.groups`; (c) un-invited bot = silently dead. All symptom-free without live validation. | Startup WARN when `planning_channel_id == slack_channel_id`; startup INFO logging effective channel + originator ids; OPS checklist covers manifest events (`message.channels` AND `message.groups`), `/invite`, and one real message → observed ack (JNB-107 style). |
| F8 | MEDIUM | PIPELINE stream reality: `pipeline.>` covers the new subject (verified in nats-infrastructure/streams/stream-definitions.json), but work-queue retention (7d / 10k msgs) bounds "durable" while Mode P doesn't exist; ideas queued before FEAT-SPL-002 deploys can expire. Live broker config unverified (TASK-JSTR-002 is design_approved). | Record the durability bound in docs; `nats stream info PIPELINE` is an OPS pre-flight; hand the consumer-filter-overlap constraint to FEAT-SPL-002's plan. |
| F9 | LOW | nats-core pin `>=0.4` is stale (planning contract is 0.5.0-only) — inert today (`[tool.uv.sources]` pins the editable sibling; uv.lock records 0.5.0) but wrong as a contract. | Bump to `nats-core>=0.5` in the first task. |
| F10 | LOW | "Verbatim" collides with the contract: `PlanningQueuedPayload` strips `request_text` on validation; whitespace-only must be pre-filtered, ValidationError → logged discard (never a crash). | Define verbatim as verbatim-modulo-outer-strip in test docstrings; pre-check `not text.strip()`; wrap construction in `except ValidationError`. |
| F11 | LOW | Unauthorized-post refusal logging is a member-triggerable log-flood vector (unlike button clicks, channel messages are cheap and unbounded). | Log unauthorized posts at INFO (not WARN), metadata-only. Channel posting permissions are the real flood control (OPS note). |
| F12 | LOW | Timestamp edge: Slack `ts` is an epoch string; naive parse can raise. Edits don't propagate (pre-edit text is what gets planned); acks to deleted parents are best-effort; postMessage rate limits are a non-issue at this volume. | `requested_at` parse wrapped with UTC-now fallback; operator doc line: "edits don't update a queued run — repost instead"; no rate-limit machinery (thin surface). |

## Assumption Disposition (10 total)

- **Resolved by this review (design half)**: ASSUM-007 → shared connection + union gate
  + per-feature handler registration (evidence above). Manifest note stands as an OPS step.
- **Hedged cheaply**: ASSUM-001 → settings field parses comma-separated ids to a
  frozenset (allow-list-ready), v1 documented as single id; upgrade is pure config.
  Startup logs the effective id(s). Rich can still override at review.
- **Corrected**: ASSUM-006's "bot messages are a subtype" is factually wrong (F3) — the
  filter keys on `bot_id`/`app_id` presence.
- **Deferrable behind config defaults (safe)**: ASSUM-002, 003, 004, 005, 008, 009, 010.

## Live-only facts (fall to the OPS follow-up task, JNB-107 style)

1. Slack app manifest has the message event subscriptions and the bot is in the channel.
2. Real Socket Mode co-delivers `events_api` + `interactive` on the one shared connection.
3. The real redelivery dedup key (stable `event_id` vs `channel:ts` fallback).
4. Live PIPELINE stream config matches stream-definitions.json (`nats stream info PIPELINE`).

## Task Breakdown (adopted from plan-critique, +OPS handoff task)

| Task | Type | Cx | Deps | Scope |
|---|---|---|---|---|
| TASK-SPL-J01 intake handler module + settings | feature | 6 | — | NEW `slack_planning_intake.py` (predicate chain, dedup, publisher, factory) + 2 settings fields (allow-list-ready) + nats-core pin bump + unit tests |
| TASK-SPL-J02 shared-connection routing + lifecycle + docs | feature | 5 | J01 | `slack_reply.py` router seam (~20 lines), union gate, `lifecycle.py` wiring, `.env.example`, 4-permutation tests |
| TASK-SPL-J03 scenario + contract suite | testing | 5 | J01, J02 | JNB-105-pattern hermetic suite: 18 scenarios + G2 contract round-trip through installed nats_core, collect-only guard |
| TASK-SPL-J04 live-validation checklist | operator_handoff | 2 | J01–J03 | OPS checklist doc (manifest, invite, live message → ack, stream info) — NOT autobuild-attempted |

Scenario ownership: J01 owns 14 scenarios, J02 owns 3, J03 owns 1 (+ executable proof
for all 17 others). Every one of the 18 spec scenarios is owned by exactly one task.

## Context Used

- jarvis: `slack_reply.py`, `slack_notifier.py`, `dispatch.py`, `settings.py`,
  `lifecycle.py`, `tests/test_slack_reply_scenarios_jnb105.py`, `pyproject.toml`, `.env.example`
- nats-core 0.5.0: `events/_pipeline.py` (runtime-probed validator behavior), `envelope.py`, `topics.py`
- nats-infrastructure: `streams/stream-definitions.json`
- ai-transition: SPL scope §3/§5/§8, fable-window plan; project memory (JNB-107 decided_by scar,
  worktree-isolation lesson, JNB-105 scenario-6 reconciliation)
