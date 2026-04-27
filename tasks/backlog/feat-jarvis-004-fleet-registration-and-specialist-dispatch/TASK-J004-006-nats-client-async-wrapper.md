---
id: TASK-J004-006
title: "infrastructure/nats_client.py — async NATS wrapper"
task_type: feature
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 2
implementation_mode: task-work
complexity: 5
dependencies: [TASK-J004-002, TASK-J004-003]
priority: high
tags: [infrastructure, nats, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-006 — infrastructure/nats_client.py async wrapper

## Description

Land `src/jarvis/infrastructure/nats_client.py` per
[API-internal.md §1](../../../docs/design/FEAT-JARVIS-004/contracts/API-internal.md):

```python
class NATSClient:
    @classmethod
    async def connect(cls, config: JarvisConfig) -> "NATSClient | None": ...
    async def request(self, subject: str, payload: bytes, *, timeout: float) -> Msg: ...
    @property
    def client(self) -> nats.aio.client.Client: ...
    @property
    def js(self) -> JetStreamContext: ...
    async def drain(self, *, timeout: float = 5.0) -> None: ...
```

Plus `tests/test_nats_client.py` covering connect / drain / reconnect-logging.

**DDR-021 soft-fail invariant**: `connect()` returns `None` on connection
failure (logged at ERROR but not raised) so lifecycle continues. The
class is the only place where `nats.connect(...)` is called — every
other module receives the wrapper.

**JetStream context** is exposed for FEAT-J005's `queue_build` swap;
FEAT-J004 doesn't use it but the surface is here for forward-compat.

## Acceptance Criteria

- [ ] `NATSClient.connect(config)` returns `NATSClient | None` — never raises on connect failure.
- [ ] Connect failure → ERROR log with `nats_url` and underlying exception, return `None`.
- [ ] Connect success → INFO log; the returned wrapper exposes `client` and `js` properties.
- [ ] `request(subject, payload, *, timeout)` issues NATS request/reply and raises `asyncio.TimeoutError` on timeout, `NATSConnectionError` on transport failure (per design §8 dispatch sequence).
- [ ] `drain(timeout=5.0)` is **idempotent** — second call after drain is a no-op (no second log line, no exception).
- [ ] Reconnect events emit structured logs (`nats_reconnect`, `nats_disconnect`) per ADR-ARCH-020.
- [ ] `tests/test_nats_client.py` covers: successful connect (mock `nats.connect`), failed connect → returns None, idempotent drain, reconnect-event logging, request → TimeoutError on no reply, request → NATSConnectionError on transport-down.
- [ ] `uv run mypy src/jarvis/infrastructure/nats_client.py` strict-clean.
- [ ] All modified files pass project-configured lint/format checks with zero errors.

## Test Requirements

- [ ] Tests use the in-process `nats-server -p 0 -js` test fixture (Phase 3 floor).
- [ ] No real network I/O; either in-process server or `unittest.mock` for unit-level paths.

## Implementation Notes

The wrapper is intentionally thin — its job is to (a) surface the
DDR-021 soft-fail at the connect boundary, (b) hide the nats-py-version
churn from the rest of the codebase, (c) provide a `drain(timeout=)`
that lifecycle.shutdown can rely on.

The reconnect callback hooks (`error_cb`, `reconnected_cb`,
`disconnected_cb`) wire to `structlog`-bound logger fields per
ADR-ARCH-020 — operator-actionable and trace-rich.

## Test Execution Log

(Populated by /task-work.)
