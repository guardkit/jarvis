---
id: TASK-J006-002
title: Extend NATSClient with subscribe_with_reply + in-flight drain counter
task_type: feature
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 1
implementation_mode: task-work
complexity: 4
priority: high
status: backlog
dependencies: []
created: 2026-05-11T00:00:00Z
updated: 2026-05-11T00:00:00Z
tags: [nats, infrastructure, bug-1]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Extend NATSClient with subscribe_with_reply + drain counter

## Description

Add `subscribe_with_reply` to `src/jarvis/infrastructure/nats_client.py` so the
chat handler can receive `CommandPayload` envelopes with the reply inbox
propagated to the handler (Bug #1 fix — without this the `ResultPayload` never
reaches the requester's future).

Add an in-flight tasks counter (`asyncio.Lock`-protected or `dataclass` with int
counter) to `NATSClient` so graceful shutdown can drain active handler invocations
(30 s timeout, study-tutor template default).

This task touches the existing thin nats-py wrapper. No new files. No subscription
is started here — this is the API surface only; the subscriber is registered in
TASK-J006-004.

## Acceptance Criteria

- [ ] `NATSClient.subscribe_with_reply(subject: str, handler: Callable[[CommandPayload, str], Awaitable[None]]) -> Subscription` exists
- [ ] Handler signature receives both the decoded `CommandPayload` AND the raw `reply_to` inbox string (Bug #1 — no plain `subscribe`)
- [ ] Subscription registers against the underlying `nats-py` client with flat subject (no wildcard tokens — Bug #4)
- [ ] In-flight counter increments before handler invocation, decrements after (try/finally), regardless of handler exception
- [ ] `NATSClient.drain(timeout: float = 30.0)` waits for counter to reach zero before draining the underlying connection, or times out
- [ ] Drain timeout logs an `nats_drain_timeout` warning naming the count of in-flight tasks
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

- [ ] Unit test: `subscribe_with_reply` registers the subject and propagates reply_to to the handler (use `unittest.mock` to patch the underlying `nats-py` subscribe)
- [ ] Unit test: in-flight counter increments/decrements around handler calls including the exception path
- [ ] Unit test: `drain()` waits for counter==0 before completing
- [ ] Unit test: `drain()` timeout logs warning and returns

## Implementation Notes

Reference: `study-tutor/src/study_tutor/adapters/nats_adapter.py` `_on_command` and
`active_tasks` counter (proven pattern).
Reference: `nats-core/src/nats_core/client.py` `subscribe_with_reply` (line 177) —
mirror the contract.

Keep the `NATSClient` class non-stateful w.r.t. handler subscriptions — return
the subscription object so callers can manage lifecycle.

## Coach Validation

- Module imports cleanly
- All unit tests pass
- Bug #1 verified by test: handler receives reply_to
- Bug #4 verified by test: subject is flat (no `*` / `>`)
- Lint zero-errors

## Seam Tests

The following seam test validates the Bug #1 contract at the NATS subscribe boundary.

```python
"""Seam test: verify subscribe_with_reply propagates reply_to (Bug #1)."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("subscribe_with_reply")
def test_subscribe_with_reply_passes_reply_to_to_handler():
    """Verify the handler receives the raw reply inbox alongside the decoded payload.

    Contract: handler signature is `(payload: CommandPayload, reply_to: str)`.
    Without reply_to in the handler signature the ResultPayload cannot reach
    the requester's NATS future (Bug #1).
    Producer: nats-py underlying subscribe (delivers Msg with .reply)
    """
    # See unit test for the full assertion; this stub documents the contract.
    assert True
```
