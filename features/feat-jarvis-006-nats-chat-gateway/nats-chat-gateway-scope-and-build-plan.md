# NATS Chat Gateway — Feature Scope & Build Plan

**Project:** jarvis
**Feature ID:** FEAT-JARVIS-006
**Date:** 7 May 2026
**Driver:** DDD Southwest demo (16 May) + Gemma 4 Good Hackathon (18 May)
**Dependencies:** `nats-core`, `specialist-agent` serve-nats (reference), Jarvis FEAT-004/005 (dispatch infrastructure, proven 4 May)
**Architecture decision:** `study-tutor/docs/talks/openwebui-nats-pipe-architecture.md`

---

## Context

Jarvis is the fleet's intent router and supervisor. On 4 May 2026, a live runbook on the GB10 proved the full chain: Jarvis's supervisor (powered by `qwen36-workhorse` via llama-swap) received a natural language request, called `queue_build` with structured arguments, published a `BuildQueuedPayload` to NATS JetStream, and Forge consumed and acked it. Seven same-day reruns closed thirteen wiring gaps and achieved structural Phase 7 close (see `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md`).

Today Jarvis receives user messages via the CLI REPL (`jarvis chat`). The fleet is moving to Open WebUI + NATS Pipe Functions as the user-facing surface. Jarvis needs a `serve-nats` mode so the Open WebUI Pipe Function can send user messages to Jarvis over NATS, Jarvis routes them to the right specialist agent, and returns the response.

This is the natural architecture: the Pipe Function sends every message to Jarvis. Jarvis is the bridge between natural language and structured commands — the same role Claude played in Claude Desktop. The supervisor's reasoning model (Qwen3.6-35B-A3B, 3B active params) looks at the user's message, looks at the available agent capabilities from the KV registry, and constructs the right `dispatch_by_capability` or `queue_build` tool call. The specialist-agent's `CommandRouter` receives clean, structured `CommandPayload` messages — exactly as designed.

---

## What already works (proven 4 May)

| Component | Status | Evidence |
|---|---|---|
| Supervisor agent graph with tool calling | ✅ | `qwen36-workhorse` successfully called `queue_build` with structured args |
| `dispatch_by_capability` — real NATS request/reply to agents | ✅ | FEAT-JARVIS-004, all 20 tasks completed |
| `queue_build` — JetStream publish to forge | ✅ | Full round-trip proven, correlation_id threaded |
| Fleet registration, heartbeat, capabilities registry | ✅ | Clean boot, manifest published, KV bind successful |
| Soft-fail when NATS/Graphiti unavailable | ✅ | FRR-003, trace offload works |
| Session manager — start, invoke, end, notifications | ✅ | CLI REPL uses all four; forge notifications drain between prompts |
| `AppState` bootstrap — config → supervisor → session_manager | ✅ | `_create_app_state()` wires everything |

## What's missing

One thing: **a NATS subscriber that feeds user messages into `session_manager.invoke()`.**

The CLI REPL does this today via `stdin.readline()` → `session_manager.invoke(session, message)` → `click.echo(reply)`. The `serve-nats` command replaces stdin/stdout with NATS subscribe/publish. The supervisor, dispatch infrastructure, session manager, and notification drain are all unchanged.

---

## Command surface

One command — simpler than both the specialist-agent and study-tutor:

| NATS command | What it does |
|---|---|
| `chat` | Receives a user message + conversation context, feeds it to `session_manager.invoke()`, returns the supervisor's response |

NATS subjects:
- Inbound: `agents.command.jarvis`
- Outbound: reply via NATS request/reply inbox (automatic)
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

## GuardKit commands

**Feature spec:**

```bash
specialist-agent run \
    --role architect \
    --mode greenfield \
    --docs /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/ \
    --scope "FEAT-JARVIS-006 NATS Chat Gateway: add serve-nats CLI command that subscribes to agents.command.jarvis, receives CommandPayload with user message, feeds it to the existing session_manager.invoke() pipeline, and publishes ResultPayload with the supervisor's response. Reuse existing AppState bootstrap, fleet registration, heartbeat, and NATS client from FEAT-004. Single command (chat), no mode inference. Reference: specialist-agent serve-nats pattern. Consumer: fleet-gateway/openwebui/nats_fleet_pipe.py. Proven on 4 May: supervisor + qwen36-workhorse + dispatch_by_capability + queue_build all working via CLI REPL. Scope doc at features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope-and-build-plan.md" \
    --output /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-006-nats-chat-gateway/ \
    --player-model local \
    --no-web-search \
    --skip-confirmation \
    --verbose
```

**Feature plan:**

```bash
specialist-agent run \
    --role product-owner \
    --mode evolve \
    --docs /Users/richardwoollcott/Projects/appmilla_github/jarvis/docs/ \
    --build-plan /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-006-nats-chat-gateway/ \
    --output /Users/richardwoollcott/Projects/appmilla_github/jarvis/features/feat-jarvis-006-nats-chat-gateway/ \
    --player-model local \
    --verbose
```

---

## Key context files for Claude Code

### Jarvis (this repo — being modified)

| File | Why |
|---|---|
| This document | Scope, command surface, wire format |
| `src/jarvis/cli/main.py` | The `chat` command — shows `_create_app_state()`, `session_manager.start_session()`, `session_manager.invoke()`, notification drain. The `serve-nats` command follows the same bootstrap but replaces stdin/stdout with NATS. |
| `src/jarvis/infrastructure/lifecycle.py` | `build_app_state()` — wires supervisor, session_manager, NATS client, fleet registration, forge subscriber. Already starts NATS and registers on the bus. |
| `src/jarvis/infrastructure/nats_client.py` | `NATSClient` — async wrapper, already used by dispatch tools. The `serve-nats` subscriber uses the same client instance. |
| `src/jarvis/sessions/session.py` | `Session` and `SessionManager` — start, invoke, end, pending_notifications |
| `src/jarvis/tools/dispatch.py` | `dispatch_by_capability` and `queue_build` — the tools the supervisor calls. No changes needed. |
| `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md` | Proof that the full chain works with `qwen36-workhorse` via llama-swap |

### Reference implementation

| File | Why |
|---|---|
| `specialist-agent/src/specialist_agent/adapters/nats_adapter.py` | Reference: NATS subscribe + command dispatch pattern |
| `specialist-agent/src/specialist_agent/cli/main.py` (serve-nats section) | Reference: CLI wiring — config → adapter → event loop |

### Fleet-gateway (the consumer)

| File | Why |
|---|---|
| `fleet-gateway/openwebui/nats_fleet_pipe.py` | The Pipe Function that publishes to `agents.command.jarvis` — defines the wire format Jarvis must respond to |

### Shared contracts

| File | Why |
|---|---|
| `nats-core/src/nats_core/events/_agent.py` | `CommandPayload`, `ResultPayload` — the wire format |
| `nats-core/src/nats_core/topics.py` | `Topics.resolve()` — subject registry |

---

## Design decisions

| Decision | Choice | Reasoning |
|---|---|---|
| **Reuse AppState bootstrap** | `serve-nats` calls `_create_app_state()` exactly as `chat` does | All infrastructure (supervisor, session_manager, NATS client, fleet registration, forge subscriber) is already wired by `build_app_state()`. No duplication. |
| **Single command: `chat`** | No command dispatch table | Jarvis has one job from the Pipe Function's perspective: "here's a message, give me a response." The supervisor decides what to do internally (call tools, answer directly, escalate). No external command routing needed. |
| **Session per connection** | One session created when `serve-nats` starts; future: session-per-user | For the demo, a single session is sufficient. Post-demo, the `adapter` field in the inbound payload can carry a user ID for session-per-user routing. |
| **Agent ID: `jarvis`** | Matches `fleet.register` already published by lifecycle | The fleet already knows Jarvis as `jarvis`. The Pipe Function publishes to `agents.command.jarvis`. No new ID needed. |
| **No streaming for Phase 1** | Return complete response as `ResultPayload` | NATS request/reply is inherently request-response. Streaming would require a different pattern (publish to a reply subject in chunks). Non-blocking for demo — Jarvis's responses are typically 1–3 paragraphs. |

---

## Risks

| Risk | Mitigation |
|---|---|
| Supervisor response time is slow (model swap + inference + dispatch + specialist inference) | Pre-warm `qwen36-workhorse` in llama-swap before demo. The routing call is 3B active params — fast. The specialist call is the long pole; audience sees this as "the factory working." |
| Session state accumulates in memory | Single session for the demo. Post-demo: session TTL with cleanup. |
| Forge notifications don't drain during NATS serve (no REPL loop) | The `serve-nats` handler should call `session_manager.pending_notifications()` after `invoke()` and include them in the response. Or: ignore for demo (notifications are visible in the terminal log pane). |
| NATS connection drops during demo | Existing soft-fail and reconnection logic from FEAT-004 handles this. Jarvis degrades to "useful chat surface" without dispatch. |

---

## How this changes the demo

The Pipe Function in `fleet-gateway/openwebui/nats_fleet_pipe.py` simplifies from a manifold of four agents to a single entry:

```python
def pipes(self):
    return [{"id": "jarvis", "name": "Jarvis"}]
```

One model in the Open WebUI dropdown: **Jarvis**. The audience types a question, Jarvis routes it. The terminal log shows the full chain: NATS message → Jarvis supervisor → tool call decision → dispatch to specialist → specialist inference → response back.

The narrative writes itself: "I type a question. Jarvis — running a 3-billion-active-parameter model on that box — figures out which specialist can answer it. It constructs the right request, dispatches it over NATS, and the architect agent picks it up. The architect runs a 26-billion-parameter fine-tuned model, also on that box, and sends back a structured review. Two models, one box, zero cloud."

---

*Drafted: 7 May 2026*
*For: Claude Code implementation session (target: 12 May)*
