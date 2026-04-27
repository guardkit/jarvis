---
id: TASK-J004-014
title: "Integration: fleet registration + capabilities live KV-watch"
task_type: testing
parent_review: TASK-REV-22CF
feature_id: FEAT-JARVIS-004
wave: 4
implementation_mode: task-work
complexity: 5
dependencies: [TASK-J004-013]
priority: high
tags: [tests, integration, fleet, capabilities, FEAT-JARVIS-004]
status: backlog
created: 2026-04-27T15:30:00Z
test_results:
  status: pending
  coverage: null
  last_run: null
---

# TASK-J004-014 — Integration: fleet registration + capabilities live KV-watch

## Description

Land two integration test files using the in-process NATS test server
fixture (`nats-server -p 0 -js`):

**`tests/test_fleet_registration_integration.py`**:

- Register Jarvis on `fleet.register`; manifest is queryable from the
  registry.
- Heartbeat fires at the configured interval (use a 1s interval +
  `asyncio.wait_for` to verify two heartbeats in 2.5s).
- `deregister_from_fleet` removes the entry; subsequent fleet query
  does not return Jarvis.
- Register-then-register-again is idempotent (no exception, single
  entry).

**`tests/test_capabilities_real.py`**:

- Pre-seed two specialist manifests; `list_available_capabilities()`
  returns both.
- Register a third specialist mid-test → KV-watch invalidates cache →
  next `list_available_capabilities()` returns three.
- Deregister a specialist mid-test → cache invalidates → next call
  returns the remaining set.
- `capabilities_refresh()` forces immediate re-read.

Both test files share an `asyncio` fixture that starts the in-process
NATS server, yields a `NATSClient`, and tears down on test exit.

## Acceptance Criteria

- [ ] In-process NATS test server fixture in `tests/conftest.py` (or a feature-local conftest) — reusable, port=0 so the OS picks a free port.
- [ ] All scenarios above covered with one test function each.
- [ ] No GB10 / external NATS dependency — pure portable tests.
- [ ] Tests survive `--randomly-seed=0` (no inter-test state leakage).
- [ ] `uv run pytest tests/test_fleet_registration_integration.py tests/test_capabilities_real.py -v` green.

## Test Requirements

- [ ] Subjects asserted via `nats_core.Topics.*` formatters (no hard-coded literals in the assertions).
- [ ] `pytest-asyncio` (`@pytest_asyncio.fixture`, `@pytest.mark.asyncio`) used consistently.

## Implementation Notes

The NATS test-server fixture is a Phase 3 floor capability — once
landed it serves Wave 4 + Wave 5 + future FEAT-J005 integration tests.
Place in a top-level `tests/conftest.py` rather than this feature's
folder.

If `nats-server` binary is not on PATH, skip these tests with a clear
`pytest.skip` message ("install nats-server CLI for integration
tests"); they remain CI-skippable and developer-runnable.

## Test Execution Log

(Populated by /task-work.)
