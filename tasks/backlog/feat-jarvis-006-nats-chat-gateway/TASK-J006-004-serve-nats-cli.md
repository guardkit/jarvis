---
id: TASK-J006-004
title: serve_nats CLI command with signal handling + integration test
task_type: feature
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 3
implementation_mode: direct
complexity: 6
priority: high
status: in_review
dependencies:
- TASK-J006-003
created: 2026-05-11 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
tags:
- nats
- cli
- serve-nats
- risk-5
- signal-handling
consumer_context:
- task: TASK-J006-003
  consumes: handle_chat_command
  framework: asyncio handler invoked from NATSClient.subscribe_with_reply
  driver: functools.partial bound to AppState
  format_note: Handler bound with session_manager, session, nats_client, agent_id;
    subscribe registers it against agents.command.jarvis
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-006
  base_branch: main
  started_at: '2026-05-12T10:55:54.654041'
  last_updated: '2026-05-12T11:14:22.214034'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-05-12T10:55:54.654041'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: serve_nats CLI command + integration test

## Description

Add `jarvis serve-nats` to `src/jarvis/cli/main.py`:

1. New click command `serve_nats` with options `--nats <url>`, `--agent-id`, `--log-level` (match study-tutor)
2. Reuse `_create_app_state()` — same bootstrap as `chat`, no duplication (Risk #5 — AppState already owns connect/register/heartbeat/deregister)
3. Refuse to start if NATS broker is unreachable (broker-as-hard-dependency posture — rejects soft-fail mode that the chat-REPL uses). Exit non-zero with a clear error.
4. Build `Session` via `session_manager.start_session(Adapter.NATS, "nats-shared")`. Phase 1 trade-off: single shared session for the gateway (concurrent requests serialise — see scope doc).
5. Register `handle_chat_command` (TASK-003) on `agents.command.jarvis` via `NATSClient.subscribe_with_reply` (TASK-002)
6. Install SIGINT/SIGTERM handlers that set an `asyncio.Event`; `_serve_adapter` awaits the event then performs graceful shutdown in this order:
   unsubscribe → drain in-flight (30s) → cancel heartbeat task → deregister → disconnect

Do NOT add a second `register_on_fleet` call — `build_app_state()` already does this.

## Acceptance Criteria

- [ ] `jarvis serve-nats --nats nats://localhost:4222` starts and subscribes to `agents.command.jarvis`
- [ ] Bootstrap reuses `_create_app_state()` exactly — no duplicate `register_on_fleet`, no duplicate `heartbeat_loop` (Risk #5 verified)
- [ ] Broker-unreachable case: command exits with non-zero status and a clear error message (no soft-fail)
- [ ] SIGINT and SIGTERM both trigger graceful shutdown via shared `asyncio.Event`
- [ ] Shutdown order: unsubscribe → drain (30s timeout) → cancel heartbeat → deregister → disconnect
- [ ] All existing CLI-path tests (`chat`, `health`, `version`) still pass
- [ ] `--log-level` option works (matches existing CLI patterns)
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

- [ ] Unit test: `serve_nats` click command parses options and calls `_serve_adapter`
- [ ] Unit test: broker-unreachable case raises and exits non-zero (mock `_create_app_state` to return `nats_client=None`)
- [ ] Unit test: signal handler sets the shutdown event
- [ ] Unit test: `_serve_adapter` shutdown ordering — assert call order on a mock NATSClient
- [ ] Integration test: end-to-end with a fake/in-memory NATS (or `nats-py` test server) — publish a `CommandPayload`, assert a `ResultPayload` arrives on the reply inbox AND on `agents.result.jarvis`
- [ ] Integration test: confirm no double registration on fleet (assert `register_on_fleet` is called exactly once during the full flow — Risk #5)

## Implementation Notes

Reference: `study-tutor/src/study_tutor/cli/main.py` `serve_nats` command (~line 338+),
`_serve_adapter` function, `_load_agent_config` (proven 11 May 2026).

Use `asyncio.run(_serve_adapter(...))` pattern. Install signal handlers via
`loop.add_signal_handler(signal.SIGINT, shutdown_event.set)` and matching SIGTERM.

The handler closure must capture the bound session and AppState so that the
subscriber receives a fully-wired callback. Use `functools.partial` rather than
a closure over local names for testability.

Do NOT introduce a NATSAdapter class. The lifecycle hooks are owned by AppState
(see scope doc §Risks #5).

## Coach Validation

- Command imports cleanly via `jarvis serve-nats --help`
- All unit tests pass
- Integration test passes against a fake NATS
- Risk #5 verified: `register_on_fleet` called exactly once
- Lint zero-errors

## Seam Tests

```python
"""Seam test: serve_nats reuses AppState lifecycle exactly once (Risk #5)."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("appstate_single_registration")
def test_serve_nats_does_not_double_register():
    """Verify Risk #5 mitigation: register_on_fleet called exactly once.

    Contract: `_create_app_state()` already performs fleet registration
    inside `build_app_state()`. The serve_nats command MUST NOT call
    `register_on_fleet` again. Double-registration silently degrades the
    fleet's view of jarvis and is the Risk #5 footgun.
    Producer: build_app_state in infrastructure/lifecycle.py
    """
    # Full assertion in integration test; this stub documents the contract.
    assert True
```
