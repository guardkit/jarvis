# Runbook: FEAT-JARVIS-006 — `jarvis serve-nats` (implementation + GB10 verification)

**Status:** Phase 1 (implementation) ✅ complete — landed in commit `51f65e2` (2026-05-12). Phases 0, 2, 3, 4 (pre-flight + GB10 verification + evidence capture) ⏳ pending operator execution on GB10.
**Purpose:** Originally the implementation guide for `jarvis serve-nats` (subscribe `agents.command.jarvis`, feed `session_manager.invoke()`, publish `ResultPayload`). Implementation now landed via the autobuild + squash-merge workflow; this runbook is repurposed as the **GB10 verification runbook** evidencing TASK-J006-005's 8 ACs.
**Machine:** GB10 (`promaxgb10-41b1`) — operator-driven verification session (NOT `/task-work`-driven; `task_type: operator_handoff`)
**Source-of-truth task:** [`tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-005-live-openwebui-demo-verification.md`](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-005-live-openwebui-demo-verification.md) — 8 ACs (AC-005-01..AC-005-08), all evidenced by running this runbook's Phases 0–4
**Predecessor:** FEAT-JARVIS-006 scope doc at `jarvis/features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md`
**Proven templates:** study-tutor `serve-nats` (GREEN run-4, 11 May) and specialist-agent `serve-nats` (GREEN 8 May)
**Expected wall-clock (verification only):** ~60 min — 5 min pre-flight + 10 min smoke + 30 min E2E + 15 min shutdown/broker-down + evidence capture
**Demo deadline:** 2026-05-16 DDD Southwest

---

## Acceptance Criteria coverage

The 8 ACs in TASK-J006-005 map onto the verification phases below. Run the phases in order; the RESULTS file produced in Phase 4 is the evidence artifact for `/task-complete TASK-J006-005`.

| Task AC | Description | Runbook phase | Evidence |
|---|---|---|---|
| AC-005-01 | Pre-warm `qwen36-workhorse` in llama-swap | §0.5 | `curl /v1/chat/completions` returning a token-stream |
| AC-005-02 | `serve-nats` boot logs `fleet.register` + heartbeat tick | §2.1 | `/tmp/jarvis-serve-nats-smoke.log` (boot lines, heartbeat within 30s) |
| AC-005-03 | Open WebUI chat reply renders E2E | §3.4 (first turn) | Browser screenshot + `/tmp/jarvis-serve-nats-e2e-{command,result}.log` |
| AC-005-04 | Multi-turn ≥3, per-gateway session retains context | §3.4 (turns 2-3) | Reply text references turn-1 context |
| AC-005-05 | `dispatch_by_capability` / `queue_build` fires specialist | §3.5 | Wire-tap on `agents.command.<specialist>` + `tools_called` in reply |
| AC-005-06 | Forge build → notifications appended to closing turn (Risk #3) | §3.6 | Reply text contains rendered notification lines |
| AC-005-07 | SIGINT → graceful shutdown (unsubscribe → drain → cancel HB → deregister → disconnect) | §3.7 | `/tmp/jarvis-serve-nats-smoke.log` grep for ordered phrases |
| AC-005-08 | Broker-down → non-zero exit, clear error (hard-dependency posture) | §3.8 | Exit code + stderr message capture |

Phase 5 (commit + tag) was already executed by the autobuild + squash-merge workflow on `main` — no further commit required for verification, only the Phase 4 RESULTS file and `/task-complete TASK-J006-005`.

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

> ✅ **All implementation tasks below landed in commit `51f65e2` (2026-05-12)** via the autobuild + squash-merge workflow (see TASK-J006-007). Retained here for historical context and as a pointer to the proven templates. **Skip ahead to [Phase 0](#phase-0-pre-flight-on-gb10) if running verification.**

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

## Phase 0: Pre-flight (on GB10)

### 0.1 Confirm jarvis main + clean tree on GB10

```bash
cd ~/Projects/appmilla_github/jarvis
git fetch origin && git status -s -uno && git log --oneline -3
```

**Pass:** Top commit is `51f65e2 FEAT-JARVIS-006: NATS chat gateway (chat_handler + serve-nats CLI)` (or descendant). Working tree clean.

### 0.2 Confirm study-tutor template files are readable

```bash
ls -la ~/Projects/appmilla_github/study-tutor/src/study_tutor/adapters/{nats_adapter,command_router,manifest}.py
```

> Note: required only for diagnostic comparison if Phase 2-3 hits unexpected behaviour. Implementation is already on `main`; not load-bearing for verification.

### 0.3 Confirm nats-core is accessible as sibling

```bash
ls ~/Projects/appmilla_github/nats-core/src/nats_core/{events/_agent.py,topics.py,client.py,agent_config.py,manifest.py}
```

### 0.4 Confirm NATS + llama-swap + Open WebUI are up

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'nats|open-webui|llama-swap'
curl -sf http://localhost:9000/v1/models | jq -r '.data[].id' | head -10
```

**Pass:** All three containers `Up`. llama-swap lists `qwen36-workhorse` (and any specialist models the demo expects).

### 0.5 Pre-warm `qwen36-workhorse` in llama-swap (AC-005-01)

llama-swap loads models on first request; cold-loading the 36B during the demo adds ~30-60s to the first turn's latency and risks the operator perceiving jarvis as hung. Fire one throwaway prompt to swap it in before opening the browser.

```bash
curl -sS http://localhost:9000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen36-workhorse",
    "messages": [{"role": "user", "content": "warmup ping"}],
    "max_tokens": 8,
    "stream": false
  }' | jq -r '.choices[0].message.content'
```

**Pass (AC-005-01 ✅):** Response returns within ~10s on a warm load (first invocation may take 30-60s). Any non-empty text in `.choices[0].message.content` means the model is loaded and ready. Record the wall-clock latency in the Phase 4 RESULTS file.

**Fail:** llama-swap returns 5xx or empty response — check `docker logs llama-swap` for the containerised deployment, or `journalctl --user -u llama-swap -n 200 --no-pager` / process log (e.g. `ps -ef | grep llama-swap` then read its log path) when llama-swap runs as a native process. On GB10 (May 2026), llama-swap is a native process on port 9000 (`pgrep -a llama-swap` to find pid), not a container — adapt the diagnostic command accordingly.

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

**Pass (AC-005-02 ✅):**
- Boot log shows `nats_connect_success`
- Boot log shows `jarvis_startup_complete` with `nats_available=true`
- Boot log shows `fleet_register_published` (from logger `jarvis.infrastructure.fleet_registration`) + a `jarvis_serve_nats_subscribed` line naming subject `agents.command.jarvis`
- Heartbeat fires within `JARVIS_HEARTBEAT_INTERVAL_SECONDS` (default 30s) — **verified by KV revision tick, not a subject publish**
- Process stays running (run-forever loop)

> **Heartbeat verification recipe (KV-only, not subject):** Jarvis's heartbeat re-publishes the manifest to the `agent-registry` KV bucket; it is *not* sent on `fleet.heartbeat.jarvis` (see `src/jarvis/infrastructure/fleet_registration.py` module docstring: *"never published as `fleet.heartbeat...`"*). The log line is DEBUG-level `fleet_heartbeat_published`, so it does **not** appear at INFO. To evidence the tick, snapshot the KV revision number twice with the configured interval in between:
>
> ```bash
> source ~/Projects/appmilla_github/nats-infrastructure/.env
> nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
>     kv get agent-registry jarvis 2>&1 | head -1    # snapshot A: revision: <N>
> # wait for at least one heartbeat_interval_seconds tick (default 30s)
> nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
>     kv get agent-registry jarvis 2>&1 | head -1    # snapshot B: revision: <N+1 or higher>
> ```
>
> A monotonic increase in `revision:` between snapshot A and B (with no nats-cli writes between) evidences the heartbeat re-register firing. Alternatively, restart serve-nats with `JARVIS_LOG_LEVEL=DEBUG` and grep the smoke log for `fleet_heartbeat_published`.

Leave the process running for the rest of Phases 2-3.

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

Open `http://promaxgb10-41b1:8080/admin/functions` in a browser. Verify the Jarvis pipe is listed and toggled on, **and that the `NATS_URL` Valve includes the broker credentials**.

> **GB10 port note:** OpenWebUI on GB10 runs with `network: host` and listens on port **8080**, not the upstream OpenWebUI default of 3000. Confirm with `docker inspect open-webui --format '{{.HostConfig.NetworkMode}}'` (expect `host`) and `ss -ltn | grep :8080`. If you find a bridge-network deployment on `:3000` somewhere else, substitute that port instead.

> **Pipe deployment + Valve credentials (load-bearing):** The deployable pipe file is `fleet-gateway/openwebui/nats_fleet_pipe.deploy.py` — paste its full contents into Admin → Functions → New Function and toggle on. Then **click the function row's ⚙ Valves icon** and set `NATS_URL` to the authenticated broker URL (e.g. `nats://rich:${RICH_NATS_PASSWORD}@localhost:4222`). The pipe's default Valve value is `nats://localhost:4222` (no credentials), which the broker rejects with `nats: 'Authorization Violation'` — the chat reply will silently spin and time out at 120s.
>
> Verify the install by running, inside the open-webui container:
>
> ```bash
> docker exec open-webui python -c "
> import sqlite3
> con = sqlite3.connect('/app/backend/data/webui.db')
> cur = con.cursor()
> cur.execute(\"SELECT id, name, type, is_active FROM function WHERE type='pipe'\")
> print(cur.fetchall())
> "
> # Expect: [('nats_gateway', 'nats-gateway', 'pipe', 1, 0)] (or equivalent with is_active=1)
> ```
>
> If `nats-py` isn't installed in the container, the pipe import will fail silently in Admin UI. Install with:
>
> ```bash
> docker exec open-webui pip install nats-py
> ```
>
> (Effect is lost on container restart — for a permanent fix, fold into the open-webui image. See FEAT-JARVIS-006 RESULTS for the May 2026 first-run gap.)

### 3.3 Open a wire-tap on command + result subjects

In a second terminal (widen to `agents.command.>` so the wire-tap also catches downstream specialist dispatch in §3.5):

```bash
source ~/Projects/appmilla_github/nats-infrastructure/.env
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.command.>" --raw \
  | tee /tmp/jarvis-serve-nats-e2e-command.log
```

In a third terminal (widen to `agents.result.>` for the same reason):

```bash
source ~/Projects/appmilla_github/nats-infrastructure/.env
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.result.>" --raw \
  | tee /tmp/jarvis-serve-nats-e2e-result.log
```

### 3.4 Post a multi-turn chat in Open WebUI (AC-005-03 + AC-005-04)

In the browser at `http://promaxgb10-41b1:8080/` (port :8080 on GB10, see §3.2 GB10 port note), select **Jarvis** from the model dropdown and stay within a single chat session for all three turns below — per-gateway session retention (Phase 1 single-shared-session trade-off) is part of the verification.

#### Turn 1 (AC-005-03)

Type:

> What agents do you have available, and can you ask the architect to evaluate whether ADR-ARCH-001's local-first invariant should allow a budget-capped cloud escalation path?

**Pass (AC-005-03 ✅):**
- Chat renders a response within 120s (faster on warm `qwen36-workhorse`)
- Response shows the supervisor's reasoning about routing to the architect
- Wire-tap (`/tmp/jarvis-serve-nats-e2e-command.log`) shows command envelope on `agents.command.jarvis`
- Wire-tap (`/tmp/jarvis-serve-nats-e2e-result.log`) shows result envelope on `agents.result.jarvis`
- `correlation_id` matches across command, result, and (if visible) the container log

#### Turn 2 (AC-005-04 — session retention)

In the same chat, type a follow-up that references turn-1 context implicitly:

> Of those agents, which one would you escalate to if a runtime quality gate failed during an autobuild turn? Walk me through how that handoff would work.

**Pass:** Response references the agent list from turn 1 (e.g., "as I mentioned, …" or builds on the architect's role from turn 1) without you having to re-list them. The wire-tap shows another command envelope with a NEW `correlation_id` but the same `args.adapter` value (the Open WebUI gateway identifier).

#### Turn 3 (AC-005-04 — session retention continues)

Type:

> Recap our conversation so far in two sentences.

**Pass (AC-005-04 ✅):** Response correctly summarises turns 1 and 2. If the reply says "I don't have context from earlier" or similar, session retention is broken — capture the wire-tap log and the response, mark AC-005-04 failed, and file a follow-up task before continuing.

### 3.5 Verify the dispatch chain fired (AC-005-05)

The widened wire-tap from §3.3 should show traffic on `agents.command.<specialist>` subjects (e.g., `agents.command.architect-agent`) triggered by turn 1's request. The full chain is:

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

**Pass (AC-005-05 ✅):**
- Wire-tap shows traffic on at least one downstream `agents.command.<specialist>` subject (typically `architect-agent` for turn 1)
- Wire-tap shows the corresponding `agents.result.<specialist>` envelope
- The Open WebUI reply text includes a `tools_called` indicator (either rendered explicitly as a field or visible in the supervisor's narrative reasoning)
- `correlation_id` on the specialist command envelope chains back to the jarvis command envelope (jarvis's supervisor preserves it)

### 3.6 Forge build → notification drain (Risk #3, AC-005-06)

This verifies the chat handler drains pending forge notifications via `session_manager.pending_notifications(session_id)` and appends them to the closing turn's reply — the Risk #3 mitigation that the chat-gateway delivers.

In the same Open WebUI chat session as §3.4, type:

> Please queue a forge build for `study-tutor` on the main branch — I want to confirm forge notifications come back through the chat session.

**Pass (AC-005-06 ✅):**
- The first reply confirms the build was queued (`queue_build` tool fired; wire-tap shows traffic on the forge subjects, typically `forge.build.*`)
- As forge stage-complete events fire, they accumulate as pending notifications on the jarvis session
- A subsequent turn (or the closing turn of this exchange, depending on forge timing) renders forge `stage_complete` / `build_done` notification lines **appended to the supervisor reply text** — not as separate chat bubbles
- Wire-tap shows the forge notification envelopes arriving on the configured forge result subject in real time

If the forge build is too slow to complete within the demo window, sending **one more conversational turn** after waiting ~30s should pick up whatever notifications accumulated since the build started — that's enough to evidence the drain pattern even if `build_done` hasn't fired.

**Fail:** Notifications appear as separate chat messages, are missing entirely, or are dropped silently. Capture the wire-tap log and reply text; this would indicate a regression in the dual-publish + drain logic landed in `51f65e2`.

### 3.7 Graceful shutdown (AC-005-07)

Verify the `serve-nats` teardown sequence: **unsubscribe → drain in-flight → cancel heartbeat → deregister → disconnect**. This is the lifecycle ordering documented in the chat-gateway scope doc as a non-negotiable.

In the terminal running `serve-nats` (the §2.1 process), send `SIGINT`:

```
Ctrl-C
```

Then immediately inspect the smoke log for the ordered shutdown phrases:

```bash
grep -E '(unsubscribe|drain|heartbeat|deregister|disconnect)' /tmp/jarvis-serve-nats-smoke.log | tail -20
```

**Pass (AC-005-07 ✅):** All five phrases appear in the log, in this order:

1. `unsubscribe` (subscription torn down first, no new commands accepted)
2. `drain` (active in-flight commands allowed to complete; typically a 30s budget)
3. `heartbeat` (cancelled — `state.fleet_heartbeat_task` cancelled, KV-revision tick on `agent-registry` stops)
4. `deregister` (KV `agent-registry` entry for jarvis removed)
5. `disconnect` (NATS client connection closed cleanly)

Process exit code is 0 (`echo $?` immediately after Ctrl-C exits).

**Fail modes to watch for:**
- Phrases out of order — indicates the lifecycle.stop() sequence is wrong
- A phrase missing — indicates a step was skipped (e.g., never deregistered, so KV still shows jarvis → next boot will conflict)
- Exit code non-zero — indicates an exception during teardown; capture stderr

### 3.8 Broker-down hard-fail (AC-005-08)

Verify the broker-as-hard-dependency posture: jarvis MUST exit non-zero with a clear error if it cannot reach NATS at startup (no silent degraded mode).

Stop the NATS broker, then attempt to start `serve-nats`:

```bash
# Container name may vary by deployment. On GB10 (May 2026) the broker is `ships-computer-nats`;
# in older single-tenant deployments it was `nats`. Confirm with:
#   docker ps --format '{{.Names}}' | grep -i nats
NATS_CONTAINER=${NATS_CONTAINER:-ships-computer-nats}
docker stop "$NATS_CONTAINER"
JARVIS_LOG_LEVEL=INFO .venv/bin/jarvis serve-nats \
    --nats "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    2>&1 | tee /tmp/jarvis-serve-nats-broker-down.log
echo "exit=$?"
```

> **⚠ Blast-radius note (GB10):** Stopping `ships-computer-nats` takes the entire NATS-dependent fleet down for the duration of the test — specialist-agents (architect-agent, product-owner-agent), fleet-gateway pipe traffic, and any other consumers will all be disconnected until `docker start` completes. Coordinate this with anyone else using the box. The hard-fail probe itself only needs ~10s; total broker downtime is dominated by the `docker start` + healthcheck wait (~20s).

**Pass (AC-005-08 ✅):**
- Process exits within ~10s (no indefinite hang)
- Exit code is non-zero (typically 1 or 2)
- Log contains a clear error naming the unreachable broker (e.g., `nats_connect_failed`, `ConnectionRefusedError`, or equivalent) — not a vague stack trace
- No `jarvis_startup_complete` line in the log (we never reached ready)

Restart the broker before continuing:

```bash
docker start "$NATS_CONTAINER"
# wait for healthy
until docker exec "$NATS_CONTAINER" nats-server --version >/dev/null 2>&1; do sleep 1; done
```

**Fail modes:**
- Process hangs indefinitely → reconnect logic isn't bounded; capture log and file follow-up
- Exit code 0 → silent degraded mode; this would violate the hard-dependency posture and break the demo if the broker hiccups

---

## Phase 4: Evidence capture

### 4.1 Save logs

```bash
mkdir -p ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/feat-jarvis-006-first-run
cp /tmp/jarvis-serve-nats-smoke.log \
   /tmp/jarvis-serve-nats-e2e-command.log \
   /tmp/jarvis-serve-nats-e2e-result.log \
   /tmp/jarvis-serve-nats-broker-down.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/feat-jarvis-006-first-run/
```

Also save any Open WebUI screenshots of the multi-turn conversation (turns 1-3 from §3.4 and the forge-notification turn from §3.6) to the same evidence directory — PNG is fine.

### 4.2 Write RESULTS file (TASK-J006-005 evidence artifact)

Create `docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-$(date +%F).md` using the template below. This file is the evidence artifact `/task-complete TASK-J006-005` references.

```markdown
# RESULTS — FEAT-JARVIS-006 first-run verification (YYYY-MM-DD)

**Operator:** <name>
**Date:** YYYY-MM-DD
**Commit verified:** 51f65e2 (or descendant — record `git rev-parse HEAD`)
**Demo deadline:** 2026-05-16 DDD Southwest
**Runbook executed:** docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md
**Task:** TASK-J006-005 (Live Open WebUI ↔ jarvis serve-nats multi-turn demo verification)

## TASK-J006-005 acceptance criteria — outcomes

| AC | Phase | Outcome | Evidence | Notes |
|---|---|---|---|---|
| AC-005-01 (pre-warm qwen36-workhorse) | §0.5 | ✅ / ❌ | warmup latency: <X>s; first-token-time post-warm: <Y>s | |
| AC-005-02 (boot + heartbeat) | §2.1 | ✅ / ❌ | `evidence/.../jarvis-serve-nats-smoke.log` lines NN-NN | First heartbeat at T+<Z>s |
| AC-005-03 (Open WebUI E2E reply) | §3.4 turn 1 | ✅ / ❌ | screenshot `turn-1.png`; `e2e-{command,result}.log` correlation_id=`<id>` | Reply latency: <X>s |
| AC-005-04 (multi-turn session retention ≥3) | §3.4 turns 2-3 | ✅ / ❌ | screenshots `turn-2.png`, `turn-3.png`; turn-3 recap text quoted below | |
| AC-005-05 (specialist dispatch) | §3.5 | ✅ / ❌ | wire-tap log: `agents.command.<specialist>` correlation_id=`<id>` chains from jarvis command | Specialist: <name> |
| AC-005-06 (forge notification drain, Risk #3) | §3.6 | ✅ / ❌ | screenshot showing forge notification text appended to reply; wire-tap of `forge.*` envelopes | Build queued: `<build_id>` |
| AC-005-07 (SIGINT graceful shutdown) | §3.7 | ✅ / ❌ | smoke.log grep output (5 phrases in order); exit code 0 | Total teardown wall-clock: <X>s |
| AC-005-08 (broker-down hard-fail) | §3.8 | ✅ / ❌ | `broker-down.log`; exit code <N>; error message: "<...>" | Time-to-exit: <Y>s |

## Multi-turn transcript (AC-005-04 evidence body)

> Turn 1 (operator): <copy from chat>
> Turn 1 (jarvis): <copy from chat — abridged OK if long>
> Turn 2 (operator): ...
> ...

## Failures and follow-ups

For any AC marked ❌, capture:
- Failure mode (one sentence)
- Evidence pointer (log + line range, or screenshot filename)
- Follow-up task ID (file via `/task-create` referencing TASK-J006-005)

If all 8 ACs ✅, the chat gateway is demo-ready. Run `/task-complete TASK-J006-005`.

## Demo-day notes (optional)

Any operator notes for the 2026-05-16 demo session itself — pacing, fallback plan if X breaks, what to highlight in the chat conversation.
```

Save with: `cp /tmp/jarvis-serve-nats-smoke.log ~/.../evidence/...` then write the RESULTS file with the above template and `git add docs/runbooks/RESULTS-FEAT-JARVIS-006-serve-nats-first-run-$(date +%F).md docs/runbooks/evidence/feat-jarvis-006-first-run/ && git commit -m "docs(runbook): RESULTS for FEAT-JARVIS-006 verification (TASK-J006-005)"`.

---

## Phase 5: Commit and tag

> ✅ **Completed by the autobuild + squash-merge workflow on 2026-05-12**, commit `51f65e2 FEAT-JARVIS-006: NATS chat gateway (chat_handler + serve-nats CLI)` on `main` (see TASK-J006-007 implementation notes). The original Phase 5 commit recipe is retained below for historical reference.
>
> **GB10 operator action required:** None for the implementation commit. After Phase 4 RESULTS file is written, commit only the RESULTS + evidence (see end of Phase 4.2) and run `/task-complete TASK-J006-005`.

<details>
<summary>Original Phase 5 commit recipe (superseded by 51f65e2)</summary>

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

</details>

---

## See also

- **Scope doc:** `jarvis/features/feat-jarvis-006-nats-chat-gateway/nats-chat-gateway-scope.md`
- **study-tutor template (primary):** `study-tutor/src/study_tutor/adapters/` (nats_adapter, command_router, manifest)
- **study-tutor CLI template:** `study-tutor/src/study_tutor/cli/main.py` (serve-nats command, _serve_adapter, _build_nats_runtime)
- **study-tutor run-4 RESULTS (proof template works):** `study-tutor/docs/runbooks/RESULTS-study-tutor-nats-fleet-demo-2026-05-11-run-4.md`
- **fleet-gateway OpenWebUI E2E runbook (post-implementation verification):** `fleet-gateway/docs/runbooks/RUNBOOK-fleet-gateway-openwebui-e2e.md`
- **specialist-agent template (cross-reference):** `specialist-agent/src/specialist_agent/adapters/nats_adapter.py`
