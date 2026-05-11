---
id: TASK-J006-005
title: Live Open WebUI ↔ jarvis serve-nats multi-turn demo verification
task_type: operator_handoff
parent_review: TASK-REV-JV06
feature_id: FEAT-JARVIS-006
wave: 4
implementation_mode: direct
complexity: 2
priority: high
status: backlog
dependencies:
  - TASK-J006-004
created: 2026-05-11T00:00:00Z
updated: 2026-05-11T00:00:00Z
tags: [demo, operator-handoff, live-infrastructure]
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Live Open WebUI ↔ jarvis serve-nats demo verification

## Description

Verify the end-to-end demo path against the live NATS broker on the GB10 demo
machine: Open WebUI Pipe Function (`fleet-gateway/openwebui/nats_fleet_pipe.py`)
publishes a chat message to `agents.command.jarvis`, jarvis processes via the
supervisor and (where appropriate) dispatches to a specialist agent, and the
reply renders in Open WebUI.

This task is `task_type: operator_handoff` — AutoBuild will NOT attempt it.
AutoBuild's Player↔Coach loop cannot satisfy live-infrastructure +
human-in-the-loop acceptance criteria; the operator runs the steps below
manually post-merge and marks the task complete via `/task-complete`.

## Required operator follow-up

This task is `task_type: operator_handoff` — AutoBuild will not attempt it.
The operator must verify the runtime acceptance criteria below manually,
then mark the task complete via `/task-complete`.

- **AC-005-01**: Pre-warm `qwen36-workhorse` in llama-swap on the GB10 before the demo (model swap latency removed from the critical path).
- **AC-005-02**: Start `jarvis serve-nats --nats nats://<gb10-broker>:4222` on the GB10 and confirm it logs `fleet.register` published and heartbeat ticking.
- **AC-005-03**: From Open WebUI, send a chat message via the fleet-gateway Pipe Function and confirm the reply renders end-to-end.
- **AC-005-04**: Drive a multi-turn conversation (≥3 turns); confirm the per-gateway session retains context across turns (Phase 1 single-shared-session trade-off accepted).
- **AC-005-05**: Send a message that should trigger `dispatch_by_capability` or `queue_build`; confirm the specialist/forge agent receives the dispatch and the response includes `tools_called` reflecting the dispatch.
- **AC-005-06**: Send a message that triggers a forge build; confirm forge stage-complete notifications appear appended to the reply that closes the turn (Risk #3 verification).
- **AC-005-07**: Send SIGINT to the `serve-nats` process; confirm graceful shutdown ordering in the logs (unsubscribe → drain → cancel heartbeat → deregister → disconnect).
- **AC-005-08**: Confirm broker-down behaviour: stop the broker, start `serve-nats`, confirm it exits non-zero with a clear error (broker-as-hard-dependency posture).

## Acceptance Criteria

See **Required operator follow-up** above. All ACs are verified by the operator
during the live demo runbook.

## Implementation Notes

This task does not modify the codebase. Outputs are:
- A short runbook entry under `docs/runbooks/` recording the demo session
- The `/task-complete` invocation flipping this task to completed status

If any AC fails, file a follow-up task referencing this one and re-run the
demo against the fix.
