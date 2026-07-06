---
id: TASK-JNB-111
title: "Approval-response publish must match the no-ack AGENTS stream: core publish + flush (forge precedent); stop mis-reporting stored publishes as failures"
status: in_review
created: 2026-07-06T22:30:00Z
updated: 2026-07-06T23:55:00Z
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

- [x] `slack_reply` publishes approval responses with CORE publish
      (`nc.publish` + `flush`), matching the forge ApprovalPublisher
      pattern; wire bytes and subject unchanged (G2 contract untouched).
- [x] Publish success/failure semantics updated: connection-level errors
      still restore buttons + warn; the no-PubAck case no longer exists.
      Keep first-click-wins and optimistic-disable semantics.
- [x] The G2 wire-bytes contract tests updated to drive the core-publish
      path (assert same bytes/subject through the real publisher).
- [x] Regression note: any OTHER jarvis `js.publish` to `agents.>` subjects
      swept (planning intake publishes to `pipeline.>` — PIPELINE is a
      normal acked stream, unaffected).
- [x] Cross-repo note for forge (no code change): MP-012's planning
      checkpoint/escalation publishes approval requests on `agents.>` —
      verify at the next forge session that it uses the acked-publisher
      seam or core publish, not a raw `js.publish` (same trap).

## Evidence

Deploy record: forge `docs/state/TASK-MP-012/deploy-verification-2026-07-06-evening.md`
(addendum 3). Stream config: `no_ack=true, retention=limits, subjects=[agents.>]`.

## Implementation (2026-07-06, moved to in_review)

### Change

`NatsApprovalResponsePublisher.publish` (src/jarvis/infrastructure/slack_reply.py)
now uses CORE publish + bounded flush instead of `js.publish`:

```python
nc = self._nats_client.client          # raw nats-py client seam
await nc.publish(subject, envelope.model_dump_json().encode("utf-8"))
await asyncio.wait_for(nc.flush(), timeout=_PUBLISH_TIMEOUT_SECONDS)
```

- Envelope construction (MessageEnvelope, source_id="jarvis",
  event_type=approval_response, correlation_id) is byte-for-byte
  unchanged; subject construction unchanged → G2 contract untouched.
- `nc.publish` raises only on a closed/broken connection; the bounded
  `flush` round-trips the server, so a success return means the broker
  received the bytes. Connection-level failures (publish raise, flush
  raise/timeout) still propagate to the handler, which keeps its
  existing restore-buttons + warn + un-mark first-click-wins branch.
  The false-failure mode (stored-but-no-PubAck) no longer exists.
- Handler semantics (first-click-wins, optimistic-disable, C1
  never-restore-after-durable-publish, decision lock) untouched.

### Tests (all green: 89 in the 3 touched files; full suite passes)

- `tests/test_slack_reply.py::TestNatsApprovalResponsePublisher` rewired
  to the core seam (`nats_client.client.publish/flush`), plus two new
  pins: `test_never_uses_jetstream_publish` (regression pin — js.publish
  must not be touched) and `test_flush_timeout_propagates_to_caller`
  (hung flush → TimeoutError → handler restore path still reachable).
- `tests/test_slack_reply.py::TestJnb110IdentityContractEndToEnd` drives
  the real factory + publisher through the core seam; decided_by
  verbatim assertions unchanged.
- `tests/test_slack_reply_scenarios_jnb105.py::TestReplyPathEnvelopeContract`
  (G2): captures wire bytes off `nc.publish`, validates against installed
  nats_core models, and asserts the flush round-trip fired. Bytes and
  subject assertions identical to the old JetStream-path assertions.
- `tests/test_contract_nats_core.py` emit-site registry unchanged (the
  envelope builder is transport-agnostic; bytes unchanged).

### AC4 — regression sweep of other `js.publish` sites (2026-07-06)

`grep -rn "js\.publish" src/` → exactly two remaining runtime sites,
both on `pipeline.>` subjects carried by the normal ACKED PIPELINE
stream — correct as-is, no change:

- `src/jarvis/tools/dispatch.py:1154` — `queue_build`, subject
  `Topics.Pipeline.BUILD_QUEUED` (`pipeline.build-queued.{feature_id}`).
- `src/jarvis/infrastructure/slack_planning_intake.py:211` — planning
  intake, subject `pipeline.planning-queued.{correlation_id}`.

No other jarvis `js.publish` targets `agents.>`; slack_reply was the
only offender.

### AC5 — cross-repo note for forge (carry to next forge session)

MP-012's planning checkpoint/escalation publishes approval REQUESTS on
`agents.>` subjects. Verify it uses the acked-publisher seam or CORE
publish (`self._nc.publish` + flush, the ApprovalPublisher pattern at
approval_publisher.py:487) — a raw `js.publish` on any `agents.>`
subject hits the identical no-PubAck trap: message stored, publisher
times out, caller mis-reports failure. No jarvis-side action; this is a
forge-session verification item.

### Unblocks

TASK-JNB-107 (live phone-approval validation) can now re-run: the tap
path publishes without the 2s stall/restore churn and reports success
truthfully.
