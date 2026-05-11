# FEAT-JARVIS-006 — NATS Chat Gateway

**Status**: planned · **Driver**: DDD Southwest demo (16 May 2026)
**Deadline**: 12 May 2026 (before DDD dry runs)
**Estimated budget**: 3–4 hours

Adds `jarvis serve-nats` — a NATS subscriber on `agents.command.jarvis` that
feeds inbound chat into the existing `session_manager.invoke()` pipeline and
dual-publishes the supervisor's reply on both the requester's reply inbox
(Bug #1) and the canonical `agents.result.jarvis` envelope topic.

## Tasks

| ID | Title | Type | Wave | Complexity | Est |
|---|---|---|---|---|---|
| [TASK-J006-001](TASK-J006-001-manifest-factory.md) | Manifest factory | declarative | 1 | 3 | 30 min |
| [TASK-J006-002](TASK-J006-002-extend-natsclient-subscribe-with-reply.md) | NATSClient.subscribe_with_reply + drain counter | feature | 1 | 4 | 45 min |
| [TASK-J006-003](TASK-J006-003-chat-handler.md) | chat_handler module | feature | 2 | 6 | 75 min |
| [TASK-J006-004](TASK-J006-004-serve-nats-cli.md) | serve_nats CLI + integration test | feature | 3 | 6 | 90 min |
| [TASK-J006-005](TASK-J006-005-live-openwebui-demo-verification.md) | Live Open WebUI ↔ jarvis demo | operator_handoff | 4 | 2 | manual |

## Documents

- [IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md) — Mermaid diagrams, §4 integration contracts, risk wiring
- [../TASK-REV-JV06-plan-nats-chat-gateway.md](../TASK-REV-JV06-plan-nats-chat-gateway.md) — review task and clarification record
- [`../../../features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md`](../../../features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md) — primary architectural reference
- [`../../../features/feat-jarvis-006-nats-chat-gateway/feat-jarvis-006-nats-chat-gateway.feature`](../../../features/feat-jarvis-006-nats-chat-gateway/feat-jarvis-006-nats-chat-gateway.feature) — 26 BDD scenarios

## Execution

Once Wave 1 starts, the recommended path is:

```bash
# Wave 1 (parallel-safe)
/task-work TASK-J006-001    # manifest
/task-work TASK-J006-002    # subscribe_with_reply

# Wave 2
/task-work TASK-J006-003    # chat_handler

# Wave 3
/task-work TASK-J006-004    # serve_nats CLI

# Wave 4 (manual)
# Operator runs the demo runbook in TASK-J006-005, then /task-complete it.
```

Or run the whole feature autonomously via:

```bash
/feature-build FEAT-JARVIS-006
```

AutoBuild will skip TASK-J006-005 (operator_handoff); the operator completes
it manually after verifying the live demo path.
