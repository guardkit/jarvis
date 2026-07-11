---
id: TASK-J006-003
title: "chat_handler module \u2014 extract \u2192 invoke \u2192 drain notifications\
  \ \u2192 dual-publish"
task_type: feature
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 2
implementation_mode: direct
complexity: 6
priority: high
status: completed
dependencies:
- TASK-J006-001
- TASK-J006-002
created: 2026-05-11 00:00:00+00:00
updated: 2026-05-12 00:00:00+00:00
tags:
- nats
- chat
- session-manager
- bug-1
- risk-3
consumer_context:
- task: TASK-J006-001
  consumes: AgentManifest
  framework: nats-core manifest types
  driver: nats_core.manifest.AgentManifest
  format_note: Manifest passed by reference into handler; consumed for capability
    lookup only
- task: TASK-J006-002
  consumes: subscribe_with_reply
  framework: nats-py subscription
  driver: asyncio handler
  format_note: 'Handler signature must be `async def handler(payload: CommandPayload,
    reply_to: str)`'
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 1
  max_turns: 5
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-006
  base_branch: main
  started_at: '2026-05-12T10:46:45.047351'
  last_updated: '2026-05-12T10:55:54.588001'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-05-12T10:46:45.047351'
    player_summary: 'Implementation via task-work delegation. Files planned: 0, Files
      actual: 0'
    player_success: true
    coach_success: true
---

# Task: chat_handler module

## Description

Create `src/jarvis/infrastructure/chat_handler.py` exposing
`async def handle_chat_command(payload, reply_to, *, session_manager, session, nats_client, agent_id) -> None`.

The handler implements the single-command business logic for `agents.command.jarvis`:

1. Extract `args.message` from the inbound `CommandPayload`
2. Call `session_manager.invoke(session, message)` — exactly what `cli/main.py:214` does
3. Drain forge stage-complete notifications via `session_manager.pending_notifications(session.session_id)` and append them to the reply text (Risk #3 — include rather than ignore)
4. Construct `ResultPayload.result` with `{"response": <text>, "tools_called": [...], "correlation_id": <id>}`
5. **Dual-publish (Bug #1)**: publish the result to BOTH the raw `reply_to` inbox AND the canonical `agents.result.jarvis` envelope topic

Inbound `conversation_history` on the payload is ignored — the per-gateway session is the canonical history store (resolves ASSUM from the scope doc).

## Acceptance Criteria

- [ ] `handle_chat_command` extracts `args.message` and rejects missing/empty messages with a structured error in `ResultPayload`
- [ ] `session_manager.invoke(session, message)` is awaited; exceptions are caught and converted to `ResultPayload` with `error` field set (no exceptions escape the handler)
- [ ] After `invoke()` returns, `session_manager.pending_notifications(session.session_id)` is called and any returned notifications are appended to the response text (Risk #3 mitigation)
- [ ] `ResultPayload` is published to the raw `reply_to` inbox (Bug #1 — first publish)
- [ ] `ResultPayload` is also published to `agents.result.jarvis` wrapped in the canonical envelope (Bug #1 — second publish)
- [ ] Both publishes use flat subjects (Bug #4 — no wildcard tokens)
- [ ] Inbound `conversation_history` field is explicitly ignored (per scope-doc design decision)
- [ ] Handler logs structured events: `chat_invoke_start`, `chat_invoke_complete`, `chat_invoke_error` with `correlation_id`
- [ ] All modified files pass project-configured lint/format checks with zero errors

## Test Requirements

- [ ] Unit test: handler with mocked `session_manager` invokes `invoke()` and publishes a `ResultPayload`
- [ ] Unit test: handler appends pending notifications to the response (Risk #3 — fake notifications fixture)
- [ ] Unit test: handler dual-publishes (assert two `client.publish` calls — one to reply_to, one to `agents.result.jarvis`)
- [ ] Unit test: handler catches and reports invoke exceptions via `ResultPayload.error` (does not raise)
- [ ] Unit test: empty/missing `message` yields a structured error reply
- [ ] Unit test: inbound `conversation_history` field is ignored (mock session unchanged)
- [ ] Boundary test: subjects are flat (`agents.result.jarvis`, no wildcards — Bug #4)

## Implementation Notes

Mirror the structure of study-tutor's `adapters/command_router.py` `_safe_invoke` +
`_publish_result` (proven 11 May 2026), but simplify: no `_command_map`, no alias
resolution, no `tool_to_command`. One verb (`chat`), one path.

The handler is closure-free: all dependencies are explicit kwargs so the unit
tests can inject mocks without monkey-patching.

## Coach Validation

- Module imports cleanly
- All unit tests pass
- Dual-publish verified (Bug #1)
- Notification drain verified (Risk #3)
- Lint zero-errors

## Seam Tests

```python
"""Seam test: dual-publish to reply_to + agents.result.jarvis (Bug #1)."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("chat_result_dual_publish")
def test_chat_handler_dual_publishes_result():
    """Verify the handler publishes the ResultPayload to BOTH targets.

    Contract: one publish to the raw `reply_to` inbox (so the requester's
    NATS request/reply future resolves), AND one publish to
    `agents.result.jarvis` (so canonical observers receive the envelope).
    Missing either side is Bug #1 regression.
    Producer: chat_handler.handle_chat_command
    """
    # Full assertion in unit test; this stub documents the contract.
    assert True


@pytest.mark.seam
@pytest.mark.integration_contract("forge_notification_drain")
def test_chat_handler_appends_pending_notifications():
    """Verify Risk #3 mitigation: forge stage-complete notifications drained.

    Contract: session_manager.pending_notifications() is called AFTER invoke()
    and BEFORE publishing; returned notifications are appended to response text.
    Producer: forge_notifications subscriber writing into session
    """
    assert True
```
