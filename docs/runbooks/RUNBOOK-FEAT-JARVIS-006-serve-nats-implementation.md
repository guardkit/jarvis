# Runbook: FEAT-JARVIS-006 — Implement `jarvis serve-nats`

**Status:** Ready for execution
**Purpose:** Implement the `jarvis serve-nats` CLI command that subscribes to `agents.command.jarvis`, feeds inbound messages to the existing `session_manager.invoke()` pipeline, and publishes `ResultPayload` responses. Then verify end-to-end with the fleet-gateway OpenWebUI pipe.
**Machine:** GB10 (`promaxgb10-41b1`) — Claude Code session
**Predecessor:** FEAT-JARVIS-006 scope doc at `jarvis/features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md` (updated 11 May with proven code references)
**Proven templates:** study-tutor `serve-nats` (GREEN run-4, 11 May) and specialist-agent `serve-nats` (GREEN 8 May)
**Expected wall-clock:** 3–4 hours implementation + 30 min first-run verification

---

## Pre-read (mandatory before writing any code)

Read these files in order. They define the wire contract, the proven patterns, and the existing jarvis infrastructure you're wiring into.

### 1. Scope doc (the feature spec)

```
jarvis/features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md
```

Read the entire doc. Pay particular attention to:
- **"Proven Code Templates"** section — lists every file to copy from, what to copy, and what to simplify
- **"Command surface"** — the wire format (inbound `CommandPayload.args`, outbound `ResultPayload.result`)
- **"What Jarvis MUST replicate"** — the five non-negotiable patterns (Bug #1 dual-publish, Bug #1 subscribe_with_reply, Bug #4 flat subjects, signal handling, graceful shutdown ordering)

### 2. study-tutor proven implementation (primary template)

Read these four files. They are the structural template.

```
study-tutor/src/study_tutor/adapters/nats_adapter.py     — NATSAdapter lifecycle
study-tutor/src/study_tutor/adapters/command_router.py    — CommandRouter + dual-publish
study-tutor/src/study_tutor/adapters/manifest.py          — Manifest factory
study-tutor/src/study_tutor/cli/main.py                   — serve-nats CLI command (from line ~338)
```

Focus on:
- `NATSAdapter.start()` — the five steps (connect, share client, register, subscribe_with_reply, heartbeat, set ready)
- `NATSAdapter.stop()` — the six steps (unsubscribe, drain, cancel heartbeat, deregister, disconnect, clear ready)
- `CommandRouter._publish_result()` — the dual-publish pattern (reply_to raw + canonical envelope)
- `CommandRouter._safe_invoke()` — exception boundary that wraps failures as `ResultPayload(success=False)`
- `_serve_adapter()` — run-forever loop with signal handling and shutdown event
- `serve_nats` click command — CLI options and `asyncio.run` entry

### 3. Jarvis existing infrastructure (being wired into)

```
jarvis/src/jarvis/cli/main.py                             — existing chat command + _create_app_state
jarvis/src/jarvis/infrastructure/lifecycle.py              — build_app_state (supervisor, session_manager, NATS)
jarvis/src/jarvis/infrastructure/nats_client.py            — NATSClient wrapper
jarvis/src/jarvis/sessions/session.py                      — Session + SessionManager
jarvis/src/jarvis/shared/constants.py                      — VERSION, Adapter enum
```

Key question to answer from reading `lifecycle.py` and `nats_client.py`: **does `build_app_state()` already connect to NATS?** If so, the NATSAdapter should reuse that connection rather than opening a second one.

### 4. Fleet-gateway consumer (what will call jarvis)

```
fleet-gateway/common/envelope.py                           — build_command_envelope shape
fleet-gateway/common/jarvis_client.py                      — JarvisClient request-reply pattern
fleet-gateway/openwebui/nats_fleet_pipe.py                 — Pipe Function (source-of-truth)
```

### 5. nats-core wire contracts

```
nats-core/src/nats_core/events/_agent.py                   — CommandPayload, ResultPayload
nats-core/src/nats_core/topics.py                          — Topics.Agents.COMMAND, Topics.Agents.RESULT
nats-core/src/nats_core/client.py                          — NATSClient.subscribe_with_reply
nats-core/src/nats_core/agent_config.py                    — AgentConfig (pydantic-settings)
nats-core/src/nats_core/manifest.py                        — AgentManifest, ToolCapability, IntentCapability
```

---

## Implementation plan

### Wave 1: Manifest + handler (no CLI yet, testable in isolation)

#### TASK-J006-001: Jarvis agent manifest

**Create:** `src/jarvis/infrastructure/manifest.py`

Copy the pattern from `study-tutor/src/study_tutor/adapters/manifest.py` and simplify:

- One `ToolCapability`: `chat` — accepts `message` (str, required), `conversation_history` (list, optional), `adapter` (str, optional)
- One `IntentCapability`: `general.*` with broad signals — "help me", "what", "how", "build", "queue", "review", "status"
- Factory function: `_jarvis_manifest_factory(agent_id: str) -> AgentManifest`

**Test:** `tests/test_manifest.py` — manifest validates, has one tool, has one intent, agent_id is kebab-case.

#### TASK-J006-002: Chat handler (simplified CommandRouter)

**Create:** `src/jarvis/infrastructure/chat_handler.py`

This is a drastically simplified CommandRouter. No dispatch table, no alias resolution. The handler:

1. Parses inbound `MessageEnvelope.payload` as `CommandPayload`
2. Extracts `args["message"]` and optionally `args["conversation_history"]`
3. Calls `session_manager.invoke(session, message)` — reuses the existing session or creates one per `args.get("adapter", "nats")`
4. Drains `session_manager.pending_notifications(session.session_id)` and appends rendered notification lines to the response
5. Wraps result in `ResultPayload(command="chat", result={"response": reply, ...}, success=True, correlation_id=...)`
6. Dual-publishes (Bug #1): raw bytes to `reply_to` inbox + envelope to `agents.result.jarvis`

Copy `_publish_result` from `study-tutor/src/study_tutor/adapters/command_router.py` — this is load-bearing.
Copy `_safe_invoke` exception boundary — handler failures must never crash the subscription.

```python
class ChatHandler:
    def __init__(self, session_manager, nats_client, agent_id="jarvis"):
        ...

    async def on_command(self, envelope: MessageEnvelope, reply_to: str | None = None):
        """Handle one inbound chat command. Never raises."""
        ...

    async def _publish_result(self, reply_to, result_payload, correlation_id):
        """Bug #1 dual-publish: reply_to raw + canonical agents.result.jarvis."""
        ...
```

**Test:** `tests/test_chat_handler.py` — mock session_manager, verify invoke called with message, verify dual-publish, verify exception wrapping.

### Wave 2: NATSAdapter + CLI command

#### TASK-J006-003: NATSAdapter (lifecycle manager)

**Create:** `src/jarvis/infrastructure/nats_serve.py` (or extend existing `nats_client.py`)

Copy `NATSAdapter` from `study-tutor/src/study_tutor/adapters/nats_adapter.py`. The lifecycle is identical:

- `start()` — connect, share client with handler, register manifest, `subscribe_with_reply` on `agents.command.jarvis`, start heartbeat, set ready
- `stop()` — unsubscribe, drain active tasks (30s), cancel heartbeat, deregister, disconnect, clear ready
- `_on_command()` — increment active_tasks, dispatch to ChatHandler.on_command, decrement in finally
- `_heartbeat_loop()` — publish AgentHeartbeatPayload at interval

**Critical design question:** `build_app_state()` in `lifecycle.py` may already connect to NATS and register jarvis. If so:
- Option A: Reuse the existing connection. Pass `state.nats_client` to the NATSAdapter instead of creating a new NATSClient. Skip the register step if lifecycle already registered.
- Option B: Don't use NATSAdapter at all. Add `subscribe_with_reply` directly to the existing lifecycle flow. This is simpler but diverges from the fleet pattern.

**Recommendation: Option A.** Reuse the connection, keep the NATSAdapter shape for fleet consistency, but inject the already-connected client.

**Test:** `tests/test_nats_serve.py` — mock NATSClient, verify lifecycle ordering, verify subscribe_with_reply called (not plain subscribe), verify heartbeat fires.

#### TASK-J006-004: `serve-nats` CLI command

**Modify:** `src/jarvis/cli/main.py`

Add a `serve-nats` command following the study-tutor pattern. Copy:
- `_load_agent_config()` from study-tutor (or adapt for jarvis's existing `JarvisConfig`)
- `_serve_adapter()` run-forever loop — this is the study-tutor's `_serve_adapter` function at `cli/main.py:~line 430`
- `serve_nats` click command — `--nats`, `--agent-id`, `--log-level` options

The command's flow:
1. Configure logging
2. Load config (`JarvisConfig` + `AgentConfig` from nats-core)
3. `await _create_app_state()` — same bootstrap as `chat`
4. Build manifest via `_jarvis_manifest_factory("jarvis")`
5. Build `ChatHandler(state.session_manager, state.nats_client, "jarvis")`
6. Build `NATSAdapter(config, manifest, chat_handler)`
7. `await _serve_adapter(adapter, ...)` — run-forever

**Note on DDR-003:** The jarvis docstring says "exactly three commands, no more" (`chat`, `version`, `health`). `serve-nats` is the fourth. Update the docstring (DDR-003 was a design constraint from FEAT-001 that predated fleet integration; the constraint was appropriate then but `serve-nats` is a natural addition).

**Test:** Existing CLI tests should still pass. Add a smoke test that `serve_nats` command exists in the click group.

### Wave 3: First-run verification

#### TASK-J006-005: First-run verification on GB10

Run the verification sequence below (Phase 3 of this runbook). This is not a separate task file — it's the operator executing this runbook's Phase 3.

---

## Phase 0: Pre-flight (before implementation)

### 0.1 Confirm jarvis main + clean tree on GB10

```bash
cd ~/Projects/appmilla_github/jarvis
git fetch origin && git status -s -uno && git log --oneline -3
```

### 0.2 Confirm study-tutor template files are readable

```bash
ls -la ~/Projects/appmilla_github/study-tutor/src/study_tutor/adapters/{nats_adapter,command_router,manifest}.py
```

### 0.3 Confirm nats-core is accessible as sibling

```bash
ls ~/Projects/appmilla_github/nats-core/src/nats_core/{events/_agent.py,topics.py,client.py,agent_config.py,manifest.py}
```

### 0.4 Confirm NATS + llama-swap + study-tutor fleet are up

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'nats|open-webui'
curl -sf http://localhost:9000/v1/models | jq -r '.data[].id' | head -5
```

---

## Phase 1: Implementation (Claude Code executes)

Execute TASK-J006-001 through TASK-J006-004 in wave order.

After each task, run the task's tests:

```bash
cd ~/Projects/appmilla_github/jarvis
.venv/bin/pytest tests/test_manifest.py -v          # after TASK-J006-001
.venv/bin/pytest tests/test_chat_handler.py -v      # after TASK-J006-002
.venv/bin/pytest tests/test_nats_serve.py -v        # after TASK-J006-003
.venv/bin/pytest tests/ -v                          # after TASK-J006-004 (all tests)
```

---

## Phase 2: Smoke test — `jarvis serve-nats` boots and subscribes

### 2.1 Boot jarvis in serve-nats mode

```bash
cd ~/Projects/appmilla_github/jarvis
source ../nats-infrastructure/.env
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
JARVIS_LOG_LEVEL=INFO .venv/bin/jarvis serve-nats \
    --nats "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    2>&1 | tee /tmp/jarvis-serve-nats-smoke.log
```

**Pass:**
- Boot log shows `nats_connect_success`
- Boot log shows `jarvis_startup_complete` with `nats_available=true`
- Boot log shows subscription to `agents.command.jarvis`
- Heartbeat fires within 30s on `fleet.heartbeat.jarvis`
- Process stays running (run-forever loop)

### 2.2 Verify jarvis registered in agent-registry KV

In a second terminal:

```bash
source ~/Projects/appmilla_github/nats-infrastructure/.env
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    kv get agent-registry jarvis --raw 2>/dev/null \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('agent_id:', d['agent_id']); print('tool count:', len(d['tools'])); [print('  -', t['name']) for t in d['tools']]"
```

**Pass:**
```
agent_id: jarvis
tool count: 1
  - chat
```

### 2.3 Send a test command via `nats request`

```bash
source ~/Projects/appmilla_github/nats-infrastructure/.env
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    request agents.command.jarvis \
    '{"command":"chat","args":{"message":"What tools do you have available?","adapter":"runbook-test"},"correlation_id":"test-001"}' \
    --timeout 120s
```

**Pass:** Response is a JSON `ResultPayload` with `success: true` and `result.response` containing the supervisor's answer listing available tools.

---

## Phase 3: End-to-end — OpenWebUI → jarvis serve-nats → specialist dispatch

### 3.1 Confirm nats-py is installed in Open WebUI container

```bash
docker exec open-webui python -c "import nats; print(nats.__version__)"
```

If `ModuleNotFoundError`: `docker exec open-webui pip install nats-py`

### 3.2 Confirm the deploy pipe is pasted and enabled

Open `http://promaxgb10-41b1:3000/admin/functions` in a browser. Verify the Jarvis pipe is listed and toggled on.

### 3.3 Open a wire-tap on command + result subjects

In a second terminal:

```bash
source ~/Projects/appmilla_github/nats-infrastructure/.env
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.command.jarvis" --raw \
  | tee /tmp/jarvis-serve-nats-e2e-command.log
```

In a third terminal:

```bash
source ~/Projects/appmilla_github/nats-infrastructure/.env
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.result.jarvis" --raw \
  | tee /tmp/jarvis-serve-nats-e2e-result.log
```

### 3.4 Post a chat in Open WebUI

In the browser, select **Jarvis** from the model dropdown. Type:

> What agents do you have available, and can you ask the architect to evaluate whether ADR-ARCH-001's local-first invariant should allow a budget-capped cloud escalation path?

**Pass:**
- Chat renders a response within 120s
- The response shows the supervisor's reasoning about routing to the architect
- The wire-tap shows the command envelope on `agents.command.jarvis`
- The wire-tap shows the result envelope on `agents.result.jarvis`
- The `correlation_id` matches across command, result, and (if visible) the container log

### 3.5 Verify the dispatch chain fired

If the supervisor dispatched to the architect, the second terminal should also show traffic on `agents.command.architect-agent` (if you widened the sub to `agents.command.>`). The full chain is:

```
OpenWebUI → nats_fleet_pipe → agents.command.jarvis
    → jarvis serve-nats → session_manager.invoke → supervisor
    → dispatch_by_capability(tool_name="architect_align", ...)
    → agents.command.architect-agent → specialist-agent container
    → llama-swap (architect-agent model) → AlignmentJudgment
    → agents.result.architect-agent → jarvis supervisor
    → ResultPayload → agents.result.jarvis + reply_to inbox
    → nats_fleet_pipe → Open WebUI chat render
```

---

## Phase 4: Evidence capture

### 4.1 Save logs

```bash
mkdir -p ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/feat-jarvis-006-first-run
cp /tmp/jarvis-serve-nats-smoke.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/feat-jarvis-006-first-run/
cp /tmp/jarvis-serve-nats-e2e-command.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/feat-jarvis-006-first-run/
cp /tmp/jarvis-serve-nats-e2e-result.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/feat-jarvis-006-first-run/
```

### 4.2 Write RESULTS file

Create `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-$(date +%F).md` with the Phase × Gate × Outcome × Evidence table.

---

## Phase 5: Commit and tag

```bash
cd ~/Projects/appmilla_github/jarvis
git add -A
git commit -m "feat(FEAT-JARVIS-006): add serve-nats CLI command

Adds jarvis serve-nats --nats <url> that subscribes to
agents.command.jarvis, feeds inbound CommandPayload messages to
session_manager.invoke(), and publishes ResultPayload responses
via dual-publish (reply_to inbox + agents.result.jarvis).

Built from study-tutor NATSAdapter/CommandRouter template (proven
GREEN run-4 11 May). Simplified for Jarvis's single-command surface.

Closes FEAT-JARVIS-006."
```

---

## See also

- **Scope doc:** `jarvis/features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md`
- **study-tutor template (primary):** `study-tutor/src/study_tutor/adapters/` (nats_adapter, command_router, manifest)
- **study-tutor CLI template:** `study-tutor/src/study_tutor/cli/main.py` (serve-nats command, _serve_adapter, _build_nats_runtime)
- **study-tutor run-4 RESULTS (proof template works):** `study-tutor/docs/runbooks/RESULTS-study-tutor-nats-fleet-demo-2026-05-11-run-4.md`
- **fleet-gateway OpenWebUI E2E runbook (post-implementation verification):** `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-openwebui-e2e.md`
- **specialist-agent template (cross-reference):** `specialist-agent/src/specialist_agent/adapters/nats_adapter.py`
