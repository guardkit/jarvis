---
id: TASK-SPL-J03
title: "jarvis: FEAT-SPL-001 scenario + contract test suite (JNB-105 pattern, plain pytest)"
status: in_review
previous_state: backlog
created: 2026-07-06T10:20:00Z
updated: 2026-07-06T12:27:06Z
priority: high
task_type: testing
parent_review: TASK-REV-3240
feature_id: FEAT-SPL-001
wave: 3
repo: jarvis
implementation_mode: task-work
complexity: 5
dependencies: [TASK-SPL-J01, TASK-SPL-J02]
tags: [sovereign-planning-loop, feat-spl-001, slack, testing, scenario-tests]
consumer_context:
  - task: TASK-SPL-J01
    consumes: NatsPlanningQueuedPublisher wire bytes
    framework: "installed nats_core 0.5.0 (MessageEnvelope / PlanningQueuedPayload)"
    driver: "nats_core"
    format_note: "Published bytes must parse as MessageEnvelope with event_type=planning_queued and PlanningQueuedPayload.model_validate must succeed; subject = pipeline.planning-queued.{correlation_id}"
---

# Task: FEAT-SPL-001 scenario + contract test suite

## Description

NEW `tests/test_slack_planning_intake_scenarios_spl001.py` — plain pytest, NO
pytest-bdd (operator decision 2026-07-03), one test class per spec scenario
mirroring the JNB-105 layout: synthetic Socket Mode requests driven through the
shared client's `_on_request` (SimpleNamespace envelopes), AsyncMock
`AsyncWebClient` asserting `chat_postMessage` thread placement, mock publisher
seam for behavior classes, and a G2-style contract class using the REAL
`NatsPlanningQueuedPublisher` over a fake JetStream capture.

## Deliverables

- One test class per spec scenario in
  `features/feat-spl-001-slack-planning-intake/feat-spl-001-slack-planning-intake.feature`
  (18 scenarios; the length outline collapses into one parametrized class).
- **G2 contract class** round-tripping captured wire bytes through installed
  `nats_core`: `MessageEnvelope` parse → `EventType.PLANNING_QUEUED`
  recognition → `PlanningQueuedPayload.model_validate` asserting:
  `stage == "planning"`, **`originating_adapter == "slack"` present in the wire
  bytes (never validator-inferred)**, `originating_user` == configured member
  id, subject correlation_id == payload correlation_id, `retry_count == 0`,
  `target_repo is None`.
- Routing-coexistence test: one fake connection, an `interactive` block_actions
  envelope AND an `events_api` message envelope both dispatched correctly
  (spec scenario 18) with exactly one ack each.
- Collect-only count guard (exact declared test count, JNB-105 precedent).
- Module docstring names the four live-only facts explicitly OUT (manifest
  subscription, real co-delivery, real redelivery dedup key, Slack max-length)
  → TASK-SPL-J04.

## Acceptance Criteria

- [ ] Every one of the 18 scenarios has an executable hermetic proof (17 owned
      by J01/J02 logic + the contract scenario owned here)
- [ ] Fully hermetic: no live Slack, no live NATS; only installed nats_core is real
- [ ] Verbatim assertions written against the contract's strip semantics
- [ ] Collect-only count pinned; suite green via `.venv/bin/python -m pytest`
- [ ] Full repo suite green (exit 0); ruff + format + mypy clean on new files
