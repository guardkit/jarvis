---
id: TASK-JNB-111
title: "Approval-response publish must match the no-ack AGENTS stream: core publish + flush (forge precedent); stop mis-reporting stored publishes as failures"
status: backlog
created: 2026-07-06T22:30:00Z
updated: 2026-07-06T22:30:00Z
priority: high
task_type: implementation
repo: jarvis
complexity: 3
dependencies: []
blocks: [TASK-JNB-107]
tags: [jnb, approval-loop, nats, found-live-2026-07-06]
---

# Task: core-publish approval responses (the no-ack AGENTS stream)

## Defect (found live, first real phone tap, 2026-07-06 21:30 UTC)

The AGENTS stream is deliberately `no_ack: true` (it captures `agents.>`,
which carries core request-reply chat traffic where PubAcks would collide
with replies). JetStream publishes to it therefore STORE the message but
never receive a PubAck — `js.publish` always raises `TimeoutError`.

`slack_reply` publishes ApprovalResponsePayload via `js.publish`, so the
first-ever live approve tap produced:
- jarvis: `slack_reply_publish_failed` (TimeoutError, empty error) →
  buttons restored, operator believes the tap failed;
- broker: the response WAS stored (AGENTS #894, 21:30:46 UTC — verbatim
  `decided_by=U03QR8WKT29`, `decision=approve`, correct subject/envelope);
- reproduced 3/3 with a standalone probe; forge's own ApprovalPublisher
  uses CORE publish (`self._nc.publish`, approval_publisher.py:487) —
  jarvis's `js.publish` is the fleet outlier on `agents.>`.

Consequence: every phone approval "fails" jarvis-side (restore + warning)
while actually being delivered — inverted truthfulness at the UX layer,
and pointless 2s stalls + restore churn on every tap.

## Acceptance criteria

- [ ] `slack_reply` publishes approval responses with CORE publish
      (`nc.publish` + `flush`), matching the forge ApprovalPublisher
      pattern; wire bytes and subject unchanged (G2 contract untouched).
- [ ] Publish success/failure semantics updated: connection-level errors
      still restore buttons + warn; the no-PubAck case no longer exists.
      Keep first-click-wins and optimistic-disable semantics.
- [ ] The G2 wire-bytes contract tests updated to drive the core-publish
      path (assert same bytes/subject through the real publisher).
- [ ] Regression note: any OTHER jarvis `js.publish` to `agents.>` subjects
      swept (planning intake publishes to `pipeline.>` — PIPELINE is a
      normal acked stream, unaffected).
- [ ] Cross-repo note for forge (no code change): MP-012's planning
      checkpoint/escalation publishes approval requests on `agents.>` —
      verify at the next forge session that it uses the acked-publisher
      seam or core publish, not a raw `js.publish` (same trap).

## Evidence

Deploy record: forge `docs/state/TASK-MP-012/deploy-verification-2026-07-06-evening.md`
(addendum 3). Stream config: `no_ack=true, retention=limits, subjects=[agents.>]`.
