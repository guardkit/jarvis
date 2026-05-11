# NATS Chat Gateway — Feature Scope & Build Plan (Updated)

**Project:** jarvis
**Feature ID:** FEAT-JARVIS-006
**Date:** 7 May 2026 (updated 11 May 2026 — added proven code references)
**Driver:** DDD Southwest demo (16 May) + Gemma 4 Good Hackathon (18 May)
**Dependencies:** `nats-core`, `specialist-agent` serve-nats (reference), Jarvis FEAT-004/005 (dispatch infrastructure, proven 4 May)
**Architecture decision:** `study-tutor/docs/talks/openwebui-nats-pipe-architecture.md`

---

## Context

Jarvis is the fleet's intent router and supervisor. On 4 May 2026, a live runbook on the GB10 proved the full chain: Jarvis's supervisor (powered by `qwen36-workhorse` via llama-swap) received a natural language request, called `queue_build` with structured arguments, published a `BuildQueuedPayload` to NATS JetStream, and Forge consumed and acked it. Seven same-day reruns closed thirteen wiring gaps and achieved structural Phase 7 close (see `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md`).

Today Jarvis receives user messages via the CLI REPL (`jarvis chat`). The fleet is moving to Open WebUI + NATS Pipe Functions as the user-facing surface. Jarvis needs a `serve-nats` mode so the Open WebUI Pipe Function can send user messages to Jarvis over NATS, Jarvis routes them to the right specialist agent, and returns the response.

This is the natural architecture: the Pipe Function sends every message to Jarvis. Jarvis is the bridge between natural language and structured commands — the same role Claude played in Claude Desktop. The supervisor's reasoning model (Qwen3.6-35B-A3B, 3B active params) looks at the user's message, looks at the available agent capabilities from the KV registry, and constructs the right `dispatch_by_capability` or `queue_build` tool call. The specialist-agent's `CommandRouter` receives clean, structured `CommandPayload` messages — exactly as designed.

---

## What already works (proven 4 May + 11 May)

| Component | Status | Evidence |
|---|---|---|
| Supervisor agent graph with tool calling | ✅ | `qwen36-workhorse` successfully called `queue_build` with structured args |
| `dispatch_by_capability` — real NATS request/reply to agents | ✅ | FEAT-JARVIS-004, all 20 tasks completed |
| `queue_build` — JetStream publish to forge | ✅ | Full round-trip proven, correlation_id threaded |
| Fleet registration, heartbeat, capabilities registry | ✅ | Clean boot, manifest published, KV bind successful |
| Soft-fail when NATS/Graphiti unavailable | ✅ | FRR-003, trace offload works |
| Session manager — start, invoke, end, notifications | ✅ | CLI REPL uses all four; forge notifications drain between prompts |
| `AppState` bootstrap — config → supervisor → session_manager | ✅ | `_create_app_state()` wires everything |
| study-tutor NATS fleet dispatch (full Player-Coach loop) | ✅ | Run-4 GREEN 11 May — `decision: accept`, 12.6s latency |
| specialist-agent architect-align NATS dispatch | ✅ | DDD demo rehearsal GREEN 8 May |
| fleet-gateway OpenWebUI pipe + common module | ✅ | FEAT-FG-001 complete, all 9 tasks merged |

## What's missing

One thing: **a NATS subscriber that feeds user messages into `session_manager.invoke()`.**

The CLI REPL does this today via `stdin.readline()` → `session_manager.invoke(session, message)` → `click.echo(reply)`. The `serve-nats` command replaces stdin/stdout with NATS subscribe/publish. The supervisor, dispatch infrastructure, session manager, and notification drain are all unchanged.

---

## Proven Code Templates — Use These As Implementation References

Two fleet members already ship working `serve-nats` implementations. Jarvis's implementation should follow these exact patterns.

### Template 1: study-tutor (recommended primary template — most recent, proven 11 May)

The study-tutor's NATS integration was built 8–11 May 2026 and proven GREEN across four runbook executions. It demonstrates the complete pattern including all four Bug fixes (Bug #1–#4) that any new fleet member must honour.

| File | What to copy/adapt | Key patterns |
|---|---|---|
| `study-tutor/src/study_tutor/adapters/nats_adapter.py` | **NATSAdapter class** — lifecycle manager (connect → register → subscribe_with_reply → heartbeat → drain → deregister → disconnect). Copy this structure wholesale. | `subscribe_with_reply` (Bug #1 fix — reply inbox propagation); `_on_command` with active_tasks counting; 30s drain timeout on stop; `_heartbeat_loop` with AgentHeartbeatPayload |
| `study-tutor/src/study_tutor/adapters/command_router.py` | **CommandRouter class** — alias resolution (Bug #2), dispatch table, dual-publish (Bug #1). For Jarvis this simplifies significantly: single `chat` command, no alias table needed. | `_publish_result` dual-publish pattern (reply_to raw + canonical `agents.result.<agent_id>`); `_safe_invoke` exception boundary; `UnsupportedCommandError` |
| `study-tutor/src/study_tutor/adapters/manifest.py` | **Manifest factory** — `AgentManifest` with `ToolCapability` + `IntentCapability` entries. Jarvis needs one tool (`chat`) and one intent (`general.*`). | `ToolCapability` parameter schema; `IntentCapability` with signals; Bug #5 guard (non-empty intents) |
| `study-tutor/src/study_tutor/cli/main.py` — `serve_nats` command (line ~338+) | **CLI wiring** — `_load_agent_config()` → `_build_nats_runtime()` → `_serve_adapter()` run-forever loop with signal handling. | Click command with `--nats`, `--agent-id`, `--log-level` options; `asyncio.run(_serve_adapter(...))` pattern; SIGINT/SIGTERM shutdown |
| `study-tutor/src/study_tutor/cli/main.py` — `_serve_adapter` function | **Run-forever loop** — start → install signal handlers → `shutdown_event.wait()` → stop → runtime_shutdown. | The try/finally for clean shutdown; signal handler setting the event; SystemExit(1) on start failure with best-effort stop |
| `study-tutor/src/study_tutor/cli/main.py` — `_build_nats_runtime` function | **Wiring function** — constructs MCPAdapter → CommandRouter → NATSAdapter. For Jarvis, replace MCPAdapter with the existing `session_manager.invoke()` pipeline. | Lazy imports pattern; `get_role("tutor").tool_to_command` for alias map; router.client sharing (Bug #8 fix) |

### Template 2: specialist-agent (original pattern — reference for comparison)

The specialist-agent's `serve-nats` was the original fleet member pattern. The study-tutor mirrors it structurally. Use it to cross-check patterns but build from the study-tutor template (it's more recent and has all the bug fixes baked in).

| File | What to reference |
|---|---|
| `specialist-agent/src/specialist_agent/adapters/nats_adapter.py` | Original NATSAdapter — structurally identical to study-tutor's |
| `specialist-agent/src/specialist_agent/cli/main.py` (serve-nats section, ~line 1515+) | Original CLI wiring with `--nats` flag override pattern |

### What Jarvis's implementation simplifies vs the templates

Jarvis is **simpler** than either template because:

1. **Single command: `chat`.** No `_command_map` dispatch table needed. Every inbound envelope goes to `session_manager.invoke()`. No `tool_to_command` alias resolution (Bug #2 is structurally absent).
2. **No MCPAdapter.** Jarvis's business logic is already wired in `_create_app_state()` → `session_manager`. The CommandRouter equivalent just extracts `args.message` and calls `invoke()`.
3. **No orchestrator factory.** No Player-Coach loop, no role config. The supervisor IS the orchestrator.
4. **AppState already handles fleet registration + heartbeat.** `build_app_state()` in `infrastructure/lifecycle.py` already starts NATS, registers, and runs heartbeats. The `serve-nats` command just needs to ADD the command subscription and run-forever loop.

### What Jarvis MUST replicate from the templates

1. **Bug #1 — `subscribe_with_reply`, not plain `subscribe`.** The reply inbox must propagate to the handler so the `ResultPayload` reaches the requester's future. This is the single most important pattern.
2. **Bug #1 — dual-publish.** Publish result to BOTH the `reply_to` inbox (raw bytes) AND `agents.result.jarvis` (envelope-wrapped). The fleet-gateway's `JarvisClient` uses request-reply; other fleet observers may subscribe to the canonical result topic.
3. **Bug #4 — flat NATS subjects.** Subscribe to `agents.command.jarvis` exactly. No trailing wildcard tokens.
4. **Signal handling.** SIGINT/SIGTERM → set shutdown event → drain in-flight → deregister → disconnect. Match the study-tutor's `_serve_adapter` pattern.
5. **Graceful shutdown ordering.** Unsubscribe → drain active tasks (30s timeout) → cancel heartbeat → deregister → disconnect. Match the NATSAdapter.stop() ordering.

---

## Command surface

One command — simpler than both the specialist-agent and study-tutor:

| NATS command | What it does |
|---|---|
| `chat` | Receives a user message + conversation context, feeds it to `session_manager.invoke()`, returns the supervisor's response |

NATS subjects:
- Inbound: `agents.command.jarvis`
- Outbound: reply via NATS request/reply inbox (automatic) + `agents.result.jarvis` (canonical envelope)
- Fleet registration: `fleet.register` (already implemented in lifecycle)
- Heartbeat: `fleet.heartbeat.jarvis` (already implemented in lifecycle)

Wire format: the inbound `CommandPayload.args` contains:

```json
{
    "message": "Is the selective retrieval decision still defensible?",
    "conversation_history": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "adapter": "openwebui"
}
```

The `ResultPayload.result` contains:

```json
{
    "response": "The supervisor's reply text...",
    "tools_called": ["dispatch_by_capability"],
    "correlation_id": "..."
}
```

---

## Single phase (DEMO-CRITICAL)

**Deadline:** 12 May 2026 (before DDD dry runs)
**Estimate:** 3–4 hours
**Feature ID:** `FEAT-JARVIS-006`

Jarvis already has fleet registration, heartbeat, and NATS client infrastructure from FEAT-004. This feature adds:

1. A NATS subscription on `agents.command.jarvis` that receives `CommandPayload` messages
2. A handler that extracts `args.message`, creates or reuses a session, calls `session_manager.invoke()`, and publishes the reply as a `ResultPayload`
3. A `jarvis serve-nats` CLI command that bootstraps `AppState` (same as `chat`), subscribes, and runs the event loop

**Implementation approach — build from study-tutor template:**

The implementation should follow the study-tutor's three-module pattern but simplified for Jarvis's single-command surface:

| study-tutor module | Jarvis equivalent | Simplification |
|---|---|---|
| `adapters/nats_adapter.py` (NATSAdapter) | `infrastructure/nats_serve.py` (or add to existing `nats_client.py`) | Reuse. Copy the NATSAdapter class from study-tutor. The lifecycle (connect, register, subscribe_with_reply, heartbeat, drain, deregister, disconnect) is identical. |
| `adapters/command_router.py` (CommandRouter) | `infrastructure/chat_handler.py` (or inline in nats_serve) | Simplify heavily. Single `chat` command. Extract `args.message` + `args.conversation_history`. Call `session_manager.invoke(session, message)`. Wrap result in `ResultPayload`. Dual-publish (Bug #1). |
| `adapters/manifest.py` (manifest factory) | `infrastructure/manifest.py` | Simplify. One `ToolCapability` entry for `chat`. One `IntentCapability`. |
| `cli/main.py` — `serve_nats` command | `cli/main.py` — add `serve_nats` command | Copy the click command, `_serve_adapter`, and `_load_agent_config` from study-tutor. Replace `_build_nats_runtime` with jarvis's `_create_app_state` + subscription wiring. |

**Acceptance criteria:**
- `jarvis serve-nats --nats nats://localhost:4222` starts, bootstraps AppState, subscribes to `agents.command.jarvis`
- Fleet registration and heartbeat fire on startup (reusing existing lifecycle infrastructure)
- A `CommandPayload` with `command: "chat"` and `args: {message: "queue a build for FEAT-TEST"}` returns a `ResultPayload` containing the supervisor's response
- The supervisor successfully calls `dispatch_by_capability` or `queue_build` when appropriate (same behaviour as the CLI REPL proven on 4 May)
- Forge notifications drain and are included in the response (or streamed via a follow-up mechanism)
- The Open WebUI Pipe Function in `fleet-gateway/openwebui/nats_fleet_pipe.py` can hold a multi-turn conversation with Jarvis
- All existing CLI-path tests still pass

**What this does NOT include:**
- Streaming responses (stretch — `pipe()` can return `AsyncGenerator` but requires a NATS streaming protocol; non-blocking for the demo since Jarvis responses are typically 1–3 paragraphs)
- Multiple concurrent sessions from different Open WebUI users (Phase 2 — session-per-user routing)
- Docker deployment (follows study-tutor Phase 3 pattern)

---

## Key context files for Claude Code

### Jarvis (this repo — being modified)

| File | Why |
|---|---|
| This document | Scope, command surface, wire format, **proven code templates** |
| `src/jarvis/cli/main.py` | The `chat` command — shows `_create_app_state()`, `session_manager.start_session()`, `session_manager.invoke()`, notification drain. The `serve-nats` command follows the same bootstrap but replaces stdin/stdout with NATS. |
| `src/jarvis/infrastructure/lifecycle.py` | `build_app_state()` — wires supervisor, session_manager, NATS client, fleet registration, forge subscriber. Already starts NATS and registers on the bus. |
| `src/jarvis/infrastructure/nats_client.py` | `NATSClient` — async wrapper, already used by dispatch tools. The `serve-nats` subscriber uses the same client instance. |
| `src/jarvis/sessions/session.py` | `Session` and `SessionManager` — start, invoke, end, pending_notifications |
| `src/jarvis/tools/dispatch.py` | `dispatch_by_capability` and `queue_build` — the tools the supervisor calls. No changes needed. |

### Proven templates (copy from these)

| File | What to copy |
|---|---|
| `study-tutor/src/study_tutor/adapters/nats_adapter.py` | **NATSAdapter** — lifecycle manager. Copy the class structure, adapt config injection to use jarvis's existing AppState/NATSClient. |
| `study-tutor/src/study_tutor/adapters/command_router.py` | **CommandRouter** — dual-publish pattern (Bug #1). Simplify: single command, no alias table. |
| `study-tutor/src/study_tutor/adapters/manifest.py` | **Manifest factory** — ToolCapability + IntentCapability schema. Simplify: one tool, one intent. |
| `study-tutor/src/study_tutor/cli/main.py` (serve-nats command, ~line 338+) | **CLI command + _serve_adapter + _load_agent_config** — Click wiring, run-forever loop, signal handling. Copy and adapt. |

### Fleet-gateway (the consumer — already built)

| File | Why |
|---|---|
| `fleet-gateway/openwebui/nats_fleet_pipe.py` | The Pipe Function that publishes to `agents.command.jarvis` — defines the wire format Jarvis must respond to |
| `fleet-gateway/common/envelope.py` | Envelope construction — shows the exact `CommandPayload` shape the pipe sends |
| `fleet-gateway/common/jarvis_client.py` | JarvisClient — shows NATS request-reply pattern and expected response parsing |

### Shared contracts

| File | Why |
|---|---|
| `nats-core/src/nats_core/events/_agent.py` | `CommandPayload`, `ResultPayload` — the wire format |
| `nats-core/src/nats_core/topics.py` | `Topics.resolve()` — subject registry |
| `nats-core/src/nats_core/client.py` | `NATSClient` — the `subscribe_with_reply` method (Bug #1 fix) |
| `nats-core/src/nats_core/agent_config.py` | `AgentConfig` — pydantic-settings model for NATS config |
| `nats-core/src/nats_core/manifest.py` | `AgentManifest`, `ToolCapability`, `IntentCapability` |

---

## Design decisions

| Decision | Choice | Reasoning |
|---|---|---|
| **Reuse AppState bootstrap** | `serve-nats` calls `_create_app_state()` exactly as `chat` does | All infrastructure (supervisor, session_manager, NATS client, fleet registration, forge subscriber) is already wired by `build_app_state()`. No duplication. |
| **Single command: `chat`** | No command dispatch table | Jarvis has one job from the Pipe Function's perspective: "here's a message, give me a response." The supervisor decides what to do internally (call tools, answer directly, escalate). No external command routing needed. |
| **Session per connection** | One session created when `serve-nats` starts; future: session-per-user | For the demo, a single session is sufficient. Post-demo, the `adapter` field in the inbound payload can carry a user ID for session-per-user routing. |
| **Agent ID: `jarvis`** | Matches `fleet.register` already published by lifecycle | The fleet already knows Jarvis as `jarvis`. The Pipe Function publishes to `agents.command.jarvis`. No new ID needed. |
| **No streaming for Phase 1** | Return complete response as `ResultPayload` | NATS request/reply is inherently request-response. Streaming would require a different pattern (publish to a reply subject in chunks). Non-blocking for demo — Jarvis's responses are typically 1–3 paragraphs. |
| **Build from study-tutor template** | Copy patterns, simplify for single-command surface | The study-tutor's NATSAdapter/CommandRouter/manifest pattern is proven GREEN across four runbook executions. Jarvis simplifies it (no MCPAdapter, no orchestrator factory, no alias table) but the lifecycle and wire protocol are identical. |

---

## Risks

| Risk | Mitigation |
|---|---|
| Supervisor response time is slow (model swap + inference + dispatch + specialist inference) | Pre-warm `qwen36-workhorse` in llama-swap before demo. The routing call is 3B active params — fast. The specialist call is the long pole; audience sees this as "the factory working." |
| Session state accumulates in memory | Single session for the demo. Post-demo: session TTL with cleanup. |
| Forge notifications don't drain during NATS serve (no REPL loop) | The `serve-nats` handler should call `session_manager.pending_notifications()` after `invoke()` and include them in the response. Or: ignore for demo (notifications are visible in the terminal log pane). |
| NATS connection drops during demo | Existing soft-fail and reconnection logic from FEAT-004 handles this. Jarvis degrades to "useful chat surface" without dispatch. |
| AppState already registers on NATS — double registration risk | Check if `build_app_state()` already subscribes to `agents.command.jarvis`. If so, skip the NATSAdapter's connect/register and just add the command subscription to the existing client. |

---

*Drafted: 7 May 2026*
*Updated: 11 May 2026 — added proven code references from study-tutor (run-4 GREEN) and specialist-agent*
*For: Claude Code implementation session on GB10 (target: 12 May)*
