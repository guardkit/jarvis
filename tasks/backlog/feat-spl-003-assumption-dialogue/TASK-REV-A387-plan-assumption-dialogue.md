---
id: TASK-REV-A387
title: "Plan: Assumption Dialogue (FEAT-SPL-003, jarvis half)"
task_type: review
status: review_complete
priority: high
feature_id: FEAT-SPL-003
created: 2026-07-08
mode: decision
clarification:
  context_a:
    decisions:
      focus: all
      tradeoff: quality
  context_b:
    decisions:
      approach: reshaped-per-panel
      execution: sequential
      testing: standard
---

# Plan: Assumption Dialogue (FEAT-SPL-003, jarvis half)

Decision review for the FEAT-SPL-003 build plan, run as the **house 3-agent
decision panel** (TASK-REV pattern) against the accepted spec triple
(`features/feat-spl-003-assumption-dialogue/`, 25 scenarios / 14 assumptions all
resolved 2026-07-07) and the live jarvis + forge + nats-core 0.6.0 code.

## Panel scores

| Lens | Score | Verdict |
|---|---|---|
| Architecture-fit | 77/100 | Load-bearing bets correct; rendering mechanism mischaracterised |
| Red-team | 56/100 | Two CRITICALs: binary-mirror rubber-stamp + render-path discards assumptions |
| Plan-critique | 78/100 | J03 over-sized; split modal; add operator task; SPL-003-specific smoke gate |

## Findings ACCEPTED and folded into the plan pre-build

1. **[CRITICAL — red-team F1/F2, arch F1] Render directly from `payload.details`;
   suppress the binary `plan-` mirror.** Verified in forge: `_PlanningPausePublisher.publish_request`
   (`forge/src/forge/cli/_serve_planning.py:342-410`) publishes the AGENTS approval request
   FIRST **and** a `pipeline.build-paused.FEAT-PLANNING` mirror SECOND, which jarvis renders as a
   binary Approve/Reject (the rubber-stamp scenario 15 forbids). And `ApprovalRequestsSubscriber`
   (`slack_notifier.py`) does not render — `capture_approval_request` discards `payload.details`
   (where the assumptions live). **Fix:** J02 branches in `_handle_message` *before*
   `capture_approval_request` and renders per-assumption directly from `ApprovalRequestPayload.details`;
   J02 also suppresses the `plan-` build-paused binary render; J03a ignores `forge_approve`/`forge_reject`
   on `plan-` subjects.
2. **[HIGH — red-team F3] Forge projects no `assumptions`/`parent_request_id`/`cycle` today**
   (`forge/src/forge/planning/checkpoint.py:294-309`; ASSUM-014). J02/J03 are **jarvis-fixture-testable
   now, E2E-gated on the forge-half TASK-SPL003F-001**. The plan pins the exact `details` contract
   fixture (J04) the forge task must satisfy; scenarios 1/2/6/11/21/24 are covered jarvis-side by
   fixture, live E2E deferred. J01 (the consumer) works against **live** forge today (degrade path).
3. **[HIGH — red-team F4, arch F5] Auto-publish concurrent-final-click stall.** Two last clicks
   carry stale `payload["message"]` snapshots → checkpoint never publishes. **Fix (J03a):** inside
   `_decision_lock`, re-fetch the AUTHORITATIVE message via `conversations.history` before deriving
   completeness — still ADR-ARCH-004 (the message IS the state, ASSUM-004).
4. **[HIGH — red-team F5, arch F7] Dedup key.** `correlation_id + timestamp` (ASSUM-008 literal)
   can drop a distinct burst notification. **Fix (J01):** key on `envelope.message_id` (uuid4,
   redelivery-stable). Dated deviation filed in the manifest.
5. **[MEDIUM — red-team F8] Ephemeral-NEW + post-failure = silent loss.** **Fix (J01):** ephemeral
   NEW push consumer with **manual ack** — ack after successful post/logged-skip; bounded NAK-redeliver
   on transient post failure (never-drop within the 1h retention). Honours ASSUM-007 (ephemeral, NEW,
   no durable restart-replay). Dated note in the manifest.
6. **[MEDIUM — red-team F6] Dialogue action value carries `approval_subject`** so J03 publishes to
   `{approval_subject}.response` (JNB-104 parity); do NOT reuse `parse_button_value` (raises on the
   dialogue value shape).
7. **[MEDIUM — red-team F7] Disposition vocabulary.** Spec says confirmed/overridden; canonical enum
   is accepted|modified|rejected|deferred. Map approve→accepted, edit→modified(+edit_delta),
   defer→deferred; **no per-item rejected**. J04 asserts published dispositions ∈ {accepted,modified,deferred}.
8. **[HIGH — plan-critique #1, arch F8] Split J03 → J03a (click engine, no modal) + J03b (edit modal +
   `view_submission` routing).** Modal is first-of-kind in the codebase.
9. **[HIGH — arch F2] Planning-independent config gate.** J01/J02 gate on planning config
   (`slack_planning_channel_id` + `slack_bot_token`), NOT on `isinstance(notification_sink, SlackNotifier)`
   — else the dialogue is dark when only the planning channel is configured. J02 uses its own web client
   + planning channel, independent of the forge-notification sink.
10. **[MEDIUM — arch F3/F11] Shared threaded-post helper.** `_post_with_retry` posts to the forge
    channel with no `thread_ts`. J01 extracts a shared `post_threaded(...)` (channel + thread_ts + 429
    budget), consumed by J01/J02/J03.
11. **[MEDIUM — plan-critique #3] Add operator live-validation task J05** (modal live facts,
    Interactivity toggle, return-channel E2E). Mirrors SPL-001 TASK-SPL-J04.
12. **[MINOR — plan-critique #6] Structured dispositions write ONLY; no notes-JSON read/write path**
    (YAGNI — jarvis is the writer, never reads its own responses). Dated note in the manifest.
13. **[MEDIUM — plan-critique #5] SPL-003-specific smoke gate** (`after_wave: "all"`) covering the
    build-pause regression surface + the new scenario files + `test_contract_nats_core.py`.
14. **[MEDIUM — arch F6] The J02↔J03 block contract is SHARED CODE** (`assumption_dialogue.build_dialogue_blocks`
    / `parse_dialogue_blocks`), not prose across a wave boundary — kills the metadata-drift seam.

## Decision: [I]mplement — 6 tasks / 6 waves (J01→J02→J03a→J03b→J04, + J05 operator)

Gate = `guardkit feature validate FEAT-SPL-003` PASS. Build via the autobuild lane, J01 first
(the first-deliverable mandate — shippable alone).
