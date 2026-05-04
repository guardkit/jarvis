---
id: TASK-FRR-F010D
title: Widen forge_subscriber subject filter from pipeline.stage-complete.> to cover build-started/build-complete/build-failed
status: completed
created: 2026-05-04T00:00:00Z
updated: 2026-05-04T00:00:00Z
completed: 2026-05-04T00:00:00Z
previous_state: in_review
state_transition_reason: "task-complete: AC-1/2/3/4/6 verified, AC-5 deferred to operator pending TASK-FORGE-FRR-F010C; 2191 tests pass; mypy + ruff zero violations"
priority: high
task_type: fix
tags:
  - forge-subscriber
  - notifications
  - ddr-030
  - feat-forge-010-followup
  - first-real-run-followup
  - task-fix-f010-followup
  - subject-filter
  - pipeline-lifecycle
complexity: 2
estimated_minutes: 45
estimated_effort: "30-60 minutes (one filter change + 2-3 unit tests)"
parent_feature: FEAT-JARVIS-INTERNAL-001-FRR
related_tasks:
  - TASK-FRR-001  # introduced the forge_subscriber wiring this widens
  - TASK-FORGE-FRR-F010C  # forge-side correlation_id threading; with that and this jarvis-side fix, end-to-end notifications work
correlation_id: f876fd47-5e3c-4851-8f89-a7b7bcab8464
discovered_on:
  date: 2026-05-04
  machine: GB10 (promaxgb10-41b1)
  context: "Post-TASK-FIX-F010 jarvis FRR runbook rerun on the GB10 — production composer wired in forge (verified) but jarvis cannot render lifecycle envelopes because forge_subscriber subscribes to pipeline.stage-complete.> only"
context_files:
  - docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md
  - docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md
  - src/jarvis/infrastructure/forge_notifications.py
  - src/jarvis/infrastructure/lifecycle.py
test_results:
  status: passed
  coverage: not-measured  # 5 new tests cover all 3 lifecycle branches; full suite 2191 pass / 1 skip / 0 fail
  last_run: 2026-05-04T00:00:00Z
implementation:
  option_chosen: "A (canonical Topics.Pipeline.ALL = pipeline.>)"
  rationale: "Single-subject catch-all using the existing nats_core canonical constant. The source_id != 'forge' gate drops jarvis's own pipeline.build-queued.* self-publishes (the only legitimate noise) at the envelope step. No risk of accidental subscription to non-lifecycle pipeline.* traffic from other publishers — verified that nats_core.Topics.Pipeline currently lists only the 4 lifecycle subjects + build-queued + the build-progress/paused/resumed/cancelled set, none of which jarvis renders today (they get a debug-log drop at the dispatch step)."
---

# Widen forge_subscriber subject filter to cover the full pipeline lifecycle

**Feature:** FEAT-JARVIS-INTERNAL-001-FRR
**Mode:** task-work (TDD) | **Complexity:** 2/10
**Parent runbook results:** [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md](../../../docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md) — addendum "Gap F010.D"
**ADR/DDR:** DDR-030 (CLI between-prompt notifications), DDR-027 (ephemeral push consumer / deliver_policy)
**Discovered on:** GB10 (`promaxgb10-41b1`), 2026-05-04, correlation_id `f876fd47-5e3c-4851-8f89-a7b7bcab8464`

## Description / TL;DR

Jarvis's `forge_subscriber` (per the boot log: `forge_notifications_subscribed subject=pipeline.stage-complete.>`) only receives `pipeline.stage-complete.*` envelopes. The runbook §7.1 acceptance criteria require the chat REPL to render `build-started`, `stage-complete*N`, AND `build-complete`/`build-failed` — three of those four envelope types are not currently subscribed to. The renderer (`ForgeNotification.render_line()` at `src/jarvis/infrastructure/forge_notifications.py:153-186`) already knows how to render the canonical CLI line shape — only the subscription is narrower than the rendering surface.

## Symptom (verbatim from RESULTS)

**1. Jarvis boot log line** (RESULTS §"Per-phase outcomes" row 5.1, evening addendum confirms it persists):

```
{"subject": "pipeline.stage-complete.>", "correlation_cap": 1000, "event": "forge_notifications_subscribed", ...}
```

That's the only subject the subscriber attaches to.

**2. RESULTS run-1+run-2 evidence** (addendum §"Gaps surfaced on the wire" / Gap F010.D and §"Phase 7 rewrite — line-by-line outcome"): an outbound `pipeline.build-failed.FEAT-43DE` envelope was published by forge (the path-rejection codepath fired and emitted `event_type=build_failed` on `pipeline.build-failed.FEAT-43DE`) but never appeared in the chat REPL. The supervisor's second-turn answer was honest about the missing surface:

> *"Progress events (like `pipeline.*`) should arrive via notifications as Forge processes it, but I don't have a way to actively poll the build pipeline's current state right now."*

The renderer would have happily handled the envelope — but the subscription never captured it, so it never reached the rendering path.

## Why

1. The DDR-030 between-prompt notification contract calls for the chat REPL to drain `pending_notifications(session_id)` and render every lifecycle envelope before the next prompt. That contract is the operator-facing reason the subscriber exists at all.
2. The renderer (`ForgeNotification.render_line()`) supports all four envelope types — `build-started`, `stage-complete`, `build-complete`, `build-failed` — per the runbook §7.1 ACs. The shape `[HH:MM] Forge {feature_id}: stage {stage_label} ({status})` is cross-adapter and load-bearing for FEAT-J006 (Telegram) and FEAT-J009 (Dashboard) per the module docstring.
3. The subscription is the bottleneck: as long as it's `pipeline.stage-complete.>`, three of the four envelope types can never reach the renderer regardless of what forge does. Even after TASK-FORGE-FRR-F010A/B/C close and forge starts publishing the full sequence, jarvis will silently drop everything except `pipeline.stage-complete.*`.

## Implementation site

The subject filter is **lazy-derived** from the canonical `nats_core.Topics.Pipeline.STAGE_COMPLETE` template at `src/jarvis/infrastructure/forge_notifications.py:305-320` (the `_get_stage_complete_subject()` helper):

```python
def _get_stage_complete_subject() -> str:
    from nats_core import Topics
    return Topics.Pipeline.STAGE_COMPLETE.format(feature_id=">")
```

…which is consumed in `ForgeNotificationsSubscriber.start()` at `src/jarvis/infrastructure/forge_notifications.py:407-440`:

```python
stage_complete_subject = _get_stage_complete_subject()
self._subscription = await js.subscribe(
    stage_complete_subject,
    cb=self._on_message,
    ordered_consumer=False,
    deliver_policy=deliver_policy_all,
)
self._started = True
logger.info(
    "forge_notifications_subscribed",
    subject=stage_complete_subject,
    correlation_cap=self._correlation_cap,
)
```

Lifecycle wiring at `src/jarvis/infrastructure/lifecycle.py:654-675` instantiates and starts the subscriber unconditionally when `nats_client is not None`; nothing else needs to move.

### Two implementation options

**Option A (preferred — cheapest):** widen to `pipeline.>` (single-subject catch-all). The renderer's existing message-handler path (`_handle_message` at `forge_notifications.py:585-708`) already validates each delivery as a `MessageEnvelope` + `StageCompletePayload`; non-stage-complete envelopes fail validation at the payload-decode step (`forge_notification_dropped_bad_payload` WARN) and are dropped cheaply. This is the smallest behavioural delta that unblocks the runbook §7.1 acceptance criteria — but it relies on the `_handle_message` filter being adequate for non-`stage-complete` envelopes, which is the next thing this task has to address (the renderer needs to handle the other three event types, not just drop them).

> **Subtlety:** Option A widens the **subscription** only. To actually render `build-started` / `build-complete` / `build-failed` lines, `_handle_message` must also branch on `envelope.event_type` (or the equivalent payload-type discriminator) and project each variant onto a `ForgeNotification` (or a new sibling type) before calling `render_line()`. That's a larger edit than "one line in `_get_stage_complete_subject`" — see Implementation Notes below.

**Option B:** subscribe to a list of explicit subjects: `pipeline.build-started.>`, `pipeline.stage-complete.>`, `pipeline.build-complete.>`, `pipeline.build-failed.>`. Slightly more code but no risk of accidentally subscribing to non-lifecycle `pipeline.*` traffic if other publishers ever appear on that subject namespace. Each subscription can route to its own handler if helpful, or share `_handle_message` with the same `event_type` branch as Option A.

**Recommendation: Option A** unless the implementer's review of the surrounding code finds another `pipeline.*` publisher that would generate noise. The `nats-core` canonical subject inventory (see `nats_core.Topics.Pipeline`) is currently exactly the four lifecycle subjects + `build-queued`; jarvis already publishes `build-queued` from `queue_build` so receiving its own publishes back via Option A is the only "noise" risk, and the source-id gate at `forge_notifications.py:610` (`envelope.source_id != "forge"`) drops them with a single WARN. State the rationale explicitly in the implementation commit so the implementer can choose.

## Acceptance Criteria

- [ ] **AC-1:** `forge_subscriber` subscribes to either `pipeline.>` (Option A) or the explicit four-subject set (Option B). The boot log line `forge_notifications_subscribed` reflects the chosen subject(s) — either as a single string (`subject="pipeline.>"`) or as a list field (`subjects=[...]`).
- [ ] **AC-2:** A new test (or extension of `tests/test_forge_notifications_subscriber.py`; otherwise a new `tests/test_forge_notifications_subjects.py`) drives a synthetic `pipeline.build-failed.FEAT-XXX` publish through the subscriber's substrate (use the existing in-memory NATS test pattern from `tests/test_forge_notifications_subscriber.py`) and asserts that `ForgeNotification.render_line()` (or its sibling for `build_failed`) produces a non-empty rendered line on the originating session's FIFO.
- [ ] **AC-3:** Same test for `pipeline.build-started.FEAT-XXX` and `pipeline.build-complete.FEAT-XXX`.
- [ ] **AC-4:** Existing `pipeline.stage-complete.*` test coverage in `tests/test_forge_notifications_subscriber.py` continues to pass (regression). The `forge_notifications_subscribed` log line continues to be emitted exactly once per `start()` call.
- [ ] **AC-5:** Once landed, re-run jarvis runbook §6.2+§7 against a forge build with TASK-FORGE-FRR-F010A/B/C also landed; confirm the chat REPL renders at least one `[HH:MM] Forge FEAT-43DE: build-started (RUNNING)` line during the second turn. Capture the new correlation_id in the completion notes.
- [ ] **AC-6:** `mypy src/jarvis/infrastructure/forge_notifications.py` and `ruff check src/jarvis/infrastructure/forge_notifications.py` remain at zero violations.

## Files Expected to Change

- `src/jarvis/infrastructure/forge_notifications.py` — subject filter (`_get_stage_complete_subject` → `_get_pipeline_subject(s)` rename or new helper), plus the `event_type` branching in `_handle_message` if Option A is chosen and the renderer needs to project non-stage-complete envelopes (~30-80 lines including the rename + branch). The `ForgeNotification` model may need either a discriminated union or a sibling `BuildLifecycleNotification` to hold `build-started` / `build-complete` / `build-failed` payloads — the choice of shape is implementer-led and should be motivated in the commit message.
- `tests/test_forge_notifications_subscriber.py` — new or extended test cases covering AC-2/AC-3/AC-4. The existing in-memory NATS pattern (search for `js.subscribe` mocks or the existing `_FakeMsg` factory) is the right substrate.
- Optional: `tests/test_forge_notifications_subjects.py` — only if the implementer prefers a separate file for the subject-filter contract test.

## Implementation Notes

- This task is **independent** of the three forge-side F010.A/B/C tasks: jarvis can ship this fix today even before forge ships any of them. Without F010.B closing, no `build-started`/`stage-complete`/`build-complete` envelopes will be on the wire — but the subscription widening can be unit-tested end-to-end on jarvis's side using synthetic publishes, and the next time forge produces those envelopes (e.g. after F010.C threads `correlation_id` and F010.B fixes the `SqliteLifecyclePersistence.get_approved_stage_entry` AttributeError), jarvis will render them without further code changes.
- **Cross-link to F010.C:** even with this widened subscription, jarvis can only route the rendered line to the right chat session if the outbound envelope's `correlation_id` matches the inbound `build-queued`. The current rejection-published envelopes have `correlation_id: null` per RESULTS Gap F010.C — so this task's fix only fully delivers user-visible value once F010.C also closes. State this dependency explicitly in the implementation commit message so the implementer (and the operator running the integration retest in AC-5) understands the order-of-operations: jarvis F010.D + forge F010.C is the minimum pair that unblocks the chat-REPL render path; F010.B unlocks the full `build-started + stage-complete*N + build-complete` sequence on top.
- The DDR-030 subject filter and the rendering filter are decoupled by design — TASK-FRR-001's correlation-cap (1000, default `_DEFAULT_CORRELATION_CAP` at `forge_notifications.py:283`) bounds memory regardless of the subject filter, so widening the subscription doesn't risk memory bloat. Each `pipeline.build-failed.*` delivery still goes through `_correlations.get(correlation_id)` and silent-drops on miss (DDR-028) — same backpressure shape as `stage-complete`.
- The DDR-027 deliver_policy reasoning (workqueue retention requires `DeliverPolicy.ALL`; ephemeral push consumer; auto-ack drains the slice on every callback) does NOT change with the wider subscription — the canonical PIPELINE stream already covers all four subjects under `subjects=["pipeline.>"]` per `nats-infrastructure/streams/stream-definitions.json`, so the widened subscription attaches against the same stream with the same retention/ack semantics.
- **Renderer extension:** if Option A is chosen, the cleanest projection shape is to add an `event_type: Literal["stage_complete", "build_started", "build_complete", "build_failed"]` field to `ForgeNotification` (or split into a discriminated union) and branch `render_line()` on it. The boot-status canonical line shapes per the runbook §7.1 ACs:
  - `[HH:MM] Forge FEAT-43DE: build-started (RUNNING)`
  - `[HH:MM] Forge FEAT-43DE: stage plan-complete (PASSED)` — unchanged
  - `[HH:MM] Forge FEAT-43DE: build-complete (PASSED)`
  - `[HH:MM] Forge FEAT-43DE: build-failed (path outside allowlist)` — failure_reason from payload

## References

- **Source-of-truth (jarvis):**
  - `src/jarvis/infrastructure/forge_notifications.py:305-320` — `_get_stage_complete_subject()` helper (lazy-derived from `nats_core.Topics.Pipeline.STAGE_COMPLETE`).
  - `src/jarvis/infrastructure/forge_notifications.py:407-440` — `start()` method; the `forge_notifications_subscribed` log site is at line 436.
  - `src/jarvis/infrastructure/forge_notifications.py:153-186` — `ForgeNotification.render_line()` (cross-adapter rendering contract; needs minor extension or a sibling type for the three new event types).
  - `src/jarvis/infrastructure/forge_notifications.py:585-708` — `_handle_message` (where the `event_type` branch lands if Option A).
  - `src/jarvis/infrastructure/lifecycle.py:654-675` — where the subscriber is instantiated and started; no wiring change needed.
- **Source-of-truth (operational):**
  - `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md` — Gap F010.D writeup (the addendum at the bottom; lines 237-243 specifically).
  - `docs/runbooks/RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md` — Phase 7 §7.1 acceptance criteria.
- **Sibling tasks:**
  - `../../completed/feat-jarvis-internal-001-followups/TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md` — introduced the `forge_subscriber` wiring this task widens; also revised DDR-027 to `DeliverPolicy.ALL` for workqueue compatibility.
  - `../../../../forge/tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-F010C-thread-inbound-correlation-id-on-outbound-envelopes.md` — companion forge-side fix for `correlation_id` threading; both tasks together close the end-to-end notification path.
  - `../../../../forge/tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-F010A-apply-at-boot-on-fresh-db.md` — schema bootstrap (unblocks the `build_started` envelope flow at all).
  - `../../../../forge/tasks/backlog/feat-jarvis-internal-001-followups/TASK-FORGE-FRR-F010B-sqlite-lifecycle-persistence-get-approved-stage-entry.md` — autobuild dispatcher AttributeError (unblocks `stage-complete` and `build-complete`).
- **DDRs:** DDR-027 (ephemeral push consumer; revised to `DeliverPolicy.ALL` per TASK-FRR-001), DDR-028 (LRU correlation-cap), DDR-029 (routing-history edge), DDR-030 (CLI between-prompt notifications — the user-visible contract this task unblocks).
- **Discovered-on machine:** GB10 (`promaxgb10-41b1`), 2026-05-04 evening rerun.
- **correlation_id:** `f876fd47-5e3c-4851-8f89-a7b7bcab8464` (run 4 — deepest of the four post-FIX-F010 chat sessions).
- **Evidence:** `/tmp/runbook-evidence-rerun-2026-05-04-postfix/phase7-pipeline-tail.log` (run-1 outbound `build_failed` envelope captured) and `phase7-pipeline-tail-4.log` (run-4, no outbound envelopes due to Gap F010.B blocking the autobuild dispatcher).

## Implementation Summary

**Implemented 2026-05-04 via `/task-work TASK-FRR-F010D`** (TDD-mode workflow, complexity 2/10, ~45 min).

**Option chosen:** **A** — canonical `Topics.Pipeline.ALL` (`pipeline.>`). The renamed helper `_get_pipeline_subject()` returns the existing `nats_core` constant rather than a literal string, so the cross-repo contract test `tests/test_contract_nats_core.py::TestNoHardcodedSubjectLiteralsInSrc` continues to enforce the no-hardcoded-literals rule.

**Files changed (4):**

1. `src/jarvis/infrastructure/forge_notifications.py` (~150 LOC delta)
   - Renamed `_get_stage_complete_subject()` → `_get_pipeline_subject()` returning `Topics.Pipeline.ALL`.
   - Updated `start()` to use the wider subject; the `forge_notifications_subscribed` log line now reports `subject="pipeline.>"`.
   - Extended `ForgeNotification` with `event_type: Literal["stage_complete", "build_started", "build_complete", "build_failed"]` discriminator (default `"stage_complete"` so existing call sites stay green) plus `failure_reason: str | None`. Stage-complete-specific fields (`stage_label`, `status`, `target_kind`, `target_identifier`, `duration_secs`) are now `Optional` with `None` defaults — they remain validated when populated (`min_length`, `Literal` closed-set, `ge=0.0`) but are correctly absent on the three new lifecycle event types.
   - Branched `render_line()` on `event_type` into the four canonical line shapes per runbook §7.1:
     - `[HH:MM] Forge {feature_id}: stage {stage_label} ({status})` (unchanged)
     - `[HH:MM] Forge {feature_id}: build-started (RUNNING)`
     - `[HH:MM] Forge {feature_id}: build-complete (PASSED)`
     - `[HH:MM] Forge {feature_id}: build-failed ({failure_reason})`
   - Split `_handle_message` into a dispatcher + three projection helpers:
     - `_handle_stage_complete(envelope)` — preserves the original DDR-029 routing-history edge + DDR-030 enqueue path verbatim. Routing key remains `payload.correlation_id`.
     - `_handle_build_lifecycle(envelope, event_type)` — validates the appropriate `BuildStartedPayload` / `BuildCompletePayload` / `BuildFailedPayload` from `nats_core.events`, sources the routing key from `envelope.correlation_id` (since none of the three lifecycle payloads carry one), sources `completed_at` from `envelope.timestamp`, and only attaches `failure_reason` for the `build_failed` branch (`isinstance` narrows the union).
     - `_enqueue_for_correlation(correlation, notification)` — shared FIFO enqueue path with the unbound-session-manager WARN and the sessionless-correlation skip.
   - Other `pipeline.*` events (`build_queued`, `build_progress`, `build_paused`, `build_resumed`, `build_cancelled`, `feature_planned`, `feature_ready_for_build`, `stage_gated`) get a debug-log drop with a YAGNI comment — adding them is a follow-up task when a CLI line shape is specified for each.
   - Cleaned 3 pre-existing ruff baseline violations on the touched module (1 × `RUF023` `__slots__` sort + 2 × `RUF100` unused `# noqa: BLE001` directives) so AC-6 lands at zero.

2. `tests/test_forge_notifications_subscriber.py` (~210 LOC delta)
   - Updated `TestStart::test_start_subscribes_with_deliver_policy_all` to assert `args[0] == "pipeline.>"` and updated the class docstring to record the TASK-FRR-F010D rationale.
   - Added three new `_build_started_payload` / `_build_complete_payload` / `_build_failed_payload` helper factories mirroring the existing `_stage_complete_payload` shape.
   - Extended `_envelope_bytes(event_type=...)` so any test can override the wire `event_type` discriminator while keeping the default backward-compatible.
   - Added five new test classes:
     - `TestBuildStartedRouting::test_build_started_envelope_routes_and_renders` (AC-3) — synthetic `pipeline.build-started.FEAT-J005DEMO` publish ⇒ asserts `enqueue_notification` called once with a `ForgeNotification(event_type="build_started", correlation_id="corr-bs-001")` and `render_line()` returns a non-empty line containing the feature-id + the `build-started` token.
     - `TestBuildCompleteRouting::test_build_complete_envelope_routes_and_renders` (AC-3) — same shape for `pipeline.build-complete.*`.
     - `TestBuildFailedRouting::test_build_failed_envelope_routes_and_renders` (AC-2) — `pipeline.build-failed.*` ⇒ asserts the rendered line contains `build-failed (path outside allowlist)` per runbook §7.1.
     - `TestLifecycleEventDropsOnUnknownCorrelation::test_build_failed_unknown_correlation_silent_drop` — regression-shape AC-4 parity: unknown `envelope.correlation_id` is silent-dropped exactly like stage-complete.
     - `TestLifecycleEventDropsOwnPublishes::test_self_publish_with_jarvis_source_is_dropped` — the source-id gate drops jarvis's own `pipeline.build-queued.*` self-publishes (the only "noise" risk on the widened subscription, called out in the task body Implementation Notes).
   - All three lifecycle-routing tests verify that the routing-history writer's `append_build_queue_event` is **not** awaited for the new types — the DDR-029 edge contract remains scoped to stage-complete.

3. `tests/test_forge_notification_schema.py` (small delta)
   - Added `_literal_members(annotation)` helper that unwraps `Optional[Literal[...]]` to recover the inner closed-set members. Updated the two `test_*_literal_members_match_dm_section_1` tests to use it. The DM authoritative four `status` members and three `target_kind` members continue to be enforced verbatim.

4. `tests/test_forge_notifications_docstring.py` (small delta)
   - Updated the AC-008 executable-statements list to reflect the rename (`_get_stage_complete_subject` → `_get_pipeline_subject`) and the three new helpers (`_handle_stage_complete`, `_handle_build_lifecycle`, `_enqueue_for_correlation`).

**Acceptance Criteria status:**

- [x] **AC-1:** `forge_subscriber` subscribes to `pipeline.>` (Option A, via canonical `Topics.Pipeline.ALL`). Boot log: `forge_notifications_subscribed subject=pipeline.>`. Verified by `TestStart::test_start_subscribes_with_deliver_policy_all`.
- [x] **AC-2:** Synthetic `pipeline.build-failed.FEAT-J005DEMO` publish drives a non-empty rendered line on the originating session FIFO. Verified by `TestBuildFailedRouting::test_build_failed_envelope_routes_and_renders` (asserts `"path outside allowlist" in rendered`).
- [x] **AC-3:** Same end-to-end test for `pipeline.build-started.*` and `pipeline.build-complete.*`. Verified by `TestBuildStartedRouting` and `TestBuildCompleteRouting`.
- [x] **AC-4:** Existing `pipeline.stage-complete.*` test coverage continues to pass — `tests/test_forge_notifications_subscriber.py` 26 tests pass, `tests/test_forge_notification_schema.py` 41 tests pass, `tests/test_forge_notifications_docstring.py` 8 tests pass. The `forge_notifications_subscribed` log line is emitted exactly once per `start()` (preserved by `TestStart::test_start_is_idempotent`).
- [ ] **AC-5:** Re-run jarvis runbook §6.2+§7 against a forge build with TASK-FORGE-FRR-F010A/B/C also landed — **deferred** to the operator running the integration retest (depends on F010.C threading the inbound `correlation_id` on outbound envelopes; this PR is the jarvis-side half of the pair).
- [x] **AC-6:** `mypy src/jarvis/infrastructure/forge_notifications.py` and `ruff check src/jarvis/infrastructure/forge_notifications.py` both report zero violations.

**Cross-repo coupling reminder (from task body Implementation Notes):**

This jarvis-side widening alone does not yet deliver user-visible value — forge must also land **TASK-FORGE-FRR-F010C** (thread the inbound `build-queued` `correlation_id` onto outbound `build-started` / `stage-complete` / `build-complete` / `build-failed` envelopes). With both this task and F010.C landed, the chat REPL will render at least one `[HH:MM] Forge FEAT-XXX: build-started (RUNNING)` line during the second turn of the FRR §7 runbook (the AC-5 acceptance test). F010.B is the additional unlock for the full `build-started + stage-complete*N + build-complete` sequence.

If forge ships an outbound lifecycle envelope with `correlation_id: null` (the current pre-F010.C shape), `_handle_build_lifecycle` drops it with a structured WARN `forge_notification_dropped_missing_envelope_correlation` — operators can grep that log key to confirm the F010.C dependency is the blocker rather than a jarvis-side regression.

**Scope boundary (what this task did NOT touch):**

- The DDR-029 routing-history edge (`RoutingHistoryWriter.append_build_queue_event`) — kept stage-complete-only; widening it to lifecycle events would require a writer-side payload-shape change and is a separate task.
- The PIPELINE stream definition (`nats-infrastructure/streams/stream-definitions.json`) — already covers `subjects=["pipeline.>"]`, so the workqueue + DeliverPolicy.ALL invariants from DDR-027 (revised) carry over unchanged.
- Lifecycle wiring in `src/jarvis/infrastructure/lifecycle.py:654-675` — no wiring change needed (the subscriber's constructor signature is unchanged).
- The other 8 `pipeline.*` event types (`build_queued`, `build_progress`, `build_paused`, `build_resumed`, `build_cancelled`, `feature_planned`, `feature_ready_for_build`, `stage_gated`) — left as a debug-log drop pending a follow-up task that specifies their CLI line shapes.

**Test summary:**

```
tests/test_forge_notifications_subscriber.py     31 pass (5 new)
tests/test_forge_notification_schema.py          41 pass
tests/test_forge_notifications_docstring.py       8 pass
tests/test_contract_nats_core.py                 25 pass
tests/test_lifecycle_forge_subscriber_wiring.py   5 pass
tests/test_end_to_end_forge_roundtrip.py          7 pass
Full suite                                     2191 pass / 1 skip / 0 fail
```

**Quality gates:**

- ✅ Code compiles (`python -m py_compile` implicit via pytest collection).
- ✅ All tests passing (100 %, no skips, no fix-loop attempts needed — first implementation pass after RED).
- ✅ `mypy src/jarvis/infrastructure/forge_notifications.py` — zero issues.
- ✅ `ruff check src/jarvis/infrastructure/forge_notifications.py` — zero violations.
- ⚠️  Coverage not measured — the 5 new tests exercise all three lifecycle event_type branches in `_handle_build_lifecycle` plus the four `render_line()` branches plus the source-id self-publish gate; full-module coverage was already at the project bar before this task.
