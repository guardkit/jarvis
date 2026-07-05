---
id: TASK-JNB-103
title: "jarvis: approval-request capture + Block Kit approve/reject buttons"
status: backlog
created: 2026-07-03T15:30:00Z
updated: 2026-07-03T15:30:00Z
priority: high
task_type: feature
parent_review: TASK-REV-C951
feature_id: FEAT-BF39
version: v1.1
wave: 7
repo: jarvis
implementation_mode: task-work
complexity: 6
dependencies: [TASK-JNB-004, TASK-JNB-005]
tags: [ubs-003, jarvis-notification-bridge, slack, v1.1]
consumer_context:
  - task: TASK-JNB-005
    consumes: WIDENED_FORGENOTIFICATION
    framework: "pydantic model (jarvis ForgeNotification)"
    driver: "pydantic"
    format_note: "pause projection retains approval_subject; new fields are optional with None defaults so CLI rendering is unaffected"
---

# Task: jarvis: approval-request capture + Block Kit approve/reject buttons

## Description

Add `slack_app_token`, `slack_operator_user_id`, and `slack_decided_by` settings, then a small subscriber on `agents.approval.forge.>` (AGENTS stream, limits retention — overlap is legal; the existing 4-token filter never matches `.response` subjects) capturing `ApprovalRequestPayload.request_id` plus its timeout into a TTL-bounded pending map keyed by `build_id`, deduped on `request_id` including across forge boot-reconcile re-emits. Upgrade the pause Slack message to Block Kit Approve/Reject buttons whose `value` JSON carries `{request_id, build_id, correlation_id, approval_subject}` (`approval_subject` arrives on `BuildPausedPayload` — zero nats-core changes), with rationale in `plain_text` blocks only. On a defer-refreshed `request_id`, `chat.update` replaces the buttons in place so the operator never holds a stale button. Fall back to the v1 text-only pause message when no request was captured, tolerant of request-before-pause ordering.

Architecture context (from the FEAT-UBS-003 plan): the Slack surface lives in-process in the jarvis supervisor as `src/jarvis/infrastructure/slack_notifier.py`, implementing a `NotificationSink` protocol whose `notify(ForgeNotification)` enqueues onto a bounded asyncio.Queue drained by one worker task serializing `chat.postMessage` at ~1 msg/s, mrkdwn disabled and all text as Block Kit `plain_text` objects so rationale and failure_reason are inert. The new settings are pydantic-settings fields under the existing `JARVIS_` prefix — `slack_bot_token`/`slack_app_token` (SecretStr|None), `slack_channel_id`, `slack_operator_user_id`, `slack_decided_by` — matching the keys already validated in `jarvis/.env`. Sink construction happens in `infrastructure/lifecycle.py` `build_app_state`; the approval-request subscriber added by this task is the only new jarvis-side NATS consumer, and it binds the AGENTS stream where limits retention permits overlap — it must never touch the PIPELINE stream's single ephemeral consumer.

TASK-JNB-005 widened `ForgeNotification` per its frozen-model rule (event_type Literal gains `build_queued`/`build_paused`/`build_cancelled`; new optional fields `build_id`, `pr_url`, `summary`, `coach_score`, `rationale`, `gate_mode`, `approval_subject`, `cancelled_by`, `reason`). The pause projection deliberately retains `approval_subject` so this task's button routing needs no re-plumbing: joining a captured pending approval to a pause message happens purely on `build_id`, and the button value JSON is assembled from the pause notification plus the pending-map entry. `BuildPausedPayload` carries no `attempt_count`, so jarvis can never derive `request_id` itself — buttons depend entirely on the AGENTS approval-request subscription being healthy, hence the mandatory text-only fallback.

## Acceptance Criteria

- [ ] pydantic-settings fields `slack_app_token` (SecretStr|None), `slack_operator_user_id`, and `slack_decided_by` exist under the `JARVIS_` prefix and load from the keys already present in `jarvis/.env`
- [ ] A subscriber on `agents.approval.forge.>` (AGENTS stream) captures `ApprovalRequestPayload.request_id` and its timeout into a TTL-bounded pending map keyed by `build_id`; `.response` subjects are never consumed by the PIPELINE consumer's 4-token filter and never mishandled here
- [ ] Pending-map entries are deduped on `request_id`, including across forge boot-reconcile re-emits: a re-emitted identical `request_id` produces no second actionable message
- [ ] Join by `build_id` proven for two concurrently paused builds with distinct `request_id`s — each pause message carries only its own build's button metadata (approve-one-not-another precondition)
- [ ] Exactly one actionable (buttoned) message exists per `request_id` at any time
- [ ] TTL expiry drops stale pending-map entries; a pause arriving after expiry renders the text-only fallback, not a dead button
- [ ] Button `value` JSON carries exactly `{request_id, build_id, correlation_id, approval_subject}` and round-trips within Block Kit limits (action value under 2000 characters)
- [ ] On a defer-refreshed `request_id` for the same `build_id`, `chat.update` replaces the existing buttons in place — the operator never holds a stale button and no second buttoned message is posted
- [ ] When no approval request has been captured for a paused `build_id`, the v1 text-only pause message is posted unchanged
- [ ] Request-before-pause and pause-before-request orderings both converge on one correct buttoned message (or fallback when the request never arrives)
- [ ] Rationale and all operator-visible text render as Block Kit `plain_text` objects only — no mrkdwn interpretation
- [ ] Subscriber and rendering failures follow DDR-007: WARNING + continue, never raising into the JetStream callback
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

Plain pytest ONLY — no pytest-bdd `.feature` glue (operator decision 2026-07-03; eliminates a known silent-false-green class). Test classes mirror spec scenario names. Run via `.venv/bin/python -m pytest` from the jarvis repo root.

- Class per behaviour: approval-request capture, request_id dedup (including boot-reconcile re-emit), TTL expiry, build_id join with two concurrent pauses, defer-refresh `chat.update`, text-only fallback, request/pause ordering tolerance, button value JSON shape and size.
- Slack client interactions (`chat.postMessage`, `chat.update`) mocked with `unittest.mock.AsyncMock`; assert call arguments (blocks, `value` JSON) rather than call counts alone.
- Synthetic `ApprovalRequestPayload` envelopes drive the subscriber directly; no live NATS in unit tests.
- Time-dependent behaviour (TTL expiry, dedup window) driven by an injectable/monotonic clock, not `sleep`.
- Negative path: subscriber handler receiving a malformed payload logs WARNING and continues (DDR-007) — assert no exception propagates.

## Seam Tests

Consumer of WIDENED_FORGENOTIFICATION (produced by TASK-JNB-005). Include the following seam test with real assertions:

```python
import pytest

@pytest.mark.seam
@pytest.mark.integration_contract("WIDENED_FORGENOTIFICATION")
class TestPauseProjectionContract:
    def test_pause_projection_round_trips_approval_subject_and_renders_score_none(self):
        # Contract: pause projection retains approval_subject; new fields are
        # optional with None defaults so CLI rendering is unaffected.
        notification = ForgeNotification(
            event_type="build_paused",
            build_id="build-abc123",
            approval_subject="agents.approval.forge.build-abc123",
            coach_score=None,
        )
        # approval_subject survives a serialize/deserialize round trip
        restored = ForgeNotification.model_validate(notification.model_dump())
        assert restored.approval_subject == "agents.approval.forge.build-abc123"
        assert restored.build_id == "build-abc123"
        # coach_score None must render, not raise: 'score unavailable' per ADR-ARCH-033
        blocks = build_pause_blocks(restored)  # rendering entry point in src/jarvis/infrastructure/slack_notifier.py
        rendered_text = " ".join(
            b["text"]["text"] for b in blocks if b.get("text")
        )
        assert "score unavailable" in rendered_text
        # all text objects are plain_text (mrkdwn disabled)
        assert all(b["text"]["type"] == "plain_text" for b in blocks if b.get("text"))

    def test_widened_fields_default_none_so_pre_widening_construction_still_validates(self):
        # New optional fields must default to None: a minimal pre-widening
        # construction must validate unchanged.
        notification = ForgeNotification(event_type="build_paused")
        assert notification.approval_subject is None
        assert notification.coach_score is None
        assert notification.build_id is None
```

Adapt the constructor's required base fields and the rendering entry-point name to the actual `ForgeNotification` model and `slack_notifier.py` API as they exist after TASK-JNB-005 — but the assertions (approval_subject round trip, None-default optionals, `score unavailable` rendering, plain_text-only blocks) are the contract and must be kept.

## Implementation Notes

Dependencies:

- TASK-JNB-004 — LIVE V1 CHECKPOINT: toy feature Open WebUI -> phone queued->running->terminal. This task is hard-gated behind that live checkpoint; do not start until it is complete.
- TASK-JNB-005 — Pause + cancelled lifecycle: filter extension and rendering. Supplies the widened `ForgeNotification` (with `approval_subject` retained on the pause projection) and the v1 text-only pause message this task upgrades and falls back to.

Key constraints:

- Single-PIPELINE-consumer rule (workqueue err_code 10100): the PIPELINE stream has exactly one ephemeral consumer, whose filter TASK-JNB-005 already extended to 6 subjects. This task's new subscriber binds the AGENTS stream only (limits retention, overlap legal). Never add or rebind a PIPELINE consumer.
- DDR-007 never-regress: notification/subscriber failures are WARNING + continue; nothing here may raise into a JetStream callback or block build progress. The SQLite ledger on the forge side stays authoritative.
- DDR-027 no-replay: pending-approval state and dedup are in-process, in-memory, TTL-bounded (monotonic clock, evict-on-insert). A jarvis restart loses the pending map by design — the text-only fallback covers pauses whose requests were lost, and forge boot-reconcile re-emits (which the request_id dedup absorbs) repopulate it.
- Correlation-INDEPENDENT fan-out is deliberate: the phone surface fires regardless of the correlation-map lookup, so a jarvis restart cannot blind it. Do not gate button rendering on correlation-map presence; `correlation_id` in the button value comes from the notification/pending entry, not the LRU.
- Producer contract for TASK-JNB-104 (downstream consumer of BUTTON_METADATA): the button `value` is JSON `{request_id, build_id, correlation_id, approval_subject}` and must stay within Slack's 2000-character action value limit — keep the JSON compact (no pretty-printing, no extra keys).
- Window/expiry-race enforcement stays exclusively forge-side: a briefly-stale button is a UX-only risk (forge safely refuses it); do not attempt jarvis-side expiry enforcement beyond the TTL map.
- The AutoBuild worktree for this task is jarvis-scoped: it cannot read the sibling forge repo. Everything needed (payload field names, subjects, contract notes above) must come from this file — do not plan steps that inspect forge sources.

Files (verified in shared plan): `src/jarvis/infrastructure/slack_notifier.py` (rendering + button upgrade), `infrastructure/lifecycle.py` `build_app_state` (construction/wiring of the new subscriber and settings), jarvis pyproject already carries slack-sdk from TASK-JNB-001.
