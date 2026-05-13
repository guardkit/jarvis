# Runbook: Jarvis → Multi-Specialist via OpenWebUI — DDD South West Demo

**Status:** Draft (dress-rehearsal target). Demo date: **2026-05-16** (DDD South West). Execute end-to-end at least twice before the talk: once for verification (this week), once as a dress rehearsal the day before. Update Status to **Verified** after the first green walkthrough.

**Purpose:** Drive three heterogeneous specialist dispatches from a **single OpenWebUI chat session** through `jarvis serve-nats`, on the same Blackwell box, with no cloud LLM on any of the three paths:

```
OpenWebUI chat (browser, GB10:8080)
  → fleet-pipe (nats_fleet_pipe.deploy.py) publishes MessageEnvelope to agents.command.jarvis
  → jarvis serve-nats unwraps envelope, feeds session_manager.invoke()
  → supervisor reasons + selects one of:
        (A) dispatch_by_capability(tool_name=architect_align)
              → agents.command.architect-agent → specialist-agent container
              → llama-swap (architect-agent Gemma 4 26B-A4B MoE)
              → AlignmentJudgment → _INBOX.> → supervisor
        (B) dispatch_by_capability(tool_name=tutor_start_session) + tutor_turn
              → agents.command.gcse-tutor → study-tutor container
              → llama-swap (gemma4-tutor) → TutoringResult → _INBOX.> → supervisor
        (C) queue_build(feature_id=...)
              → JetStream pipeline.build-queued.<feature_id>
              → forge-prod consumes, emits pipeline.stage-complete.<feature_id>...
              → session_manager.pending_notifications() drained on next chat turn
  → supervisor renders reply → ResultPayload dual-publish (reply_to + agents.result.jarvis)
  → fleet-pipe → OpenWebUI chat render
```

Single per-gateway session across all three turns. Multi-turn context retention across heterogeneous specialists is part of what we evidence.

**Machine layout (single-host GB10, `promaxgb10-41b1`):**
- NATS JetStream (`ships-computer-nats`, host-network, `:4222`)
- llama-swap (host process, `:9000`, serving `qwen36-workhorse`, `architect-agent`, `gemma4-tutor`)
- specialist-agent dual-role compose (`specialist-agent-architect-agent-1`, `specialist-agent-product-owner-agent-1`)
- study-tutor compose (`gcse-tutor` or `study-tutor-gcse-tutor-1`)
- forge-prod container (`forge-prod`)
- OpenWebUI + fleet-pipe (`open-webui`, host-network, `:8080`)
- `jarvis serve-nats` (host venv)

**Companion runbooks (this runbook reuses their phases):**
- [`RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md`](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md) — `jarvis serve-nats` boot, smoke, OpenWebUI plumbing, AC matrix
- [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](RUNBOOK-jarvis-architect-align-dddsw-demo.md) — architect-agent dispatch + AlignmentJudgment shape
- [`../../../study-tutor/docs/runbooks/RUNBOOK-study-tutor-nats-fleet-demo.md`](../../../study-tutor/docs/runbooks/RUNBOOK-study-tutor-nats-fleet-demo.md) — tutor capability surface + dispatch
- [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — forge `queue_build` JetStream wire path + notification drain
- [`RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md`](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md) — the last known-green state of the gateway path (7/8 ACs PASS; AC-005-06 forge drain pending; same constraints this runbook addresses)

**Expected wall-clock (clean dress rehearsal):** ~45–60 min — 15 min pre-flight + bring-up, ~25 min for the three demo turns (architect inference 30–90s, tutor 10–30s, forge stage drain depends on the chosen no-op feature), 5–10 min evidence capture.

**On-stage wall-clock target:** 6–8 minutes from "type prompt" to "third reply rendered" — pre-warmed models, single OpenWebUI session.

**Outputs:**
- [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-<YYYY-MM-DD>.md`](.) capturing per-turn outcomes and evidence pointers
- [`evidence/multi-specialist-demo/`](evidence/) — wire-tap logs, screenshots, RESULTS JSON for each turn
- `~/.jarvis/transcripts/<session_correlation_root>.txt` — the OpenWebUI chat transcript (operator screenshot or paste)
- Three captured envelope payloads — one per dispatch path — saved as `evidence/multi-specialist-demo/turn-{1,2,3}-payload.json`

---

## What this runbook does NOT cover

- **CLI `jarvis chat` REPL path.** This is OpenWebUI-only. The CLI path is covered by [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](RUNBOOK-jarvis-architect-align-dddsw-demo.md) and [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md).
- **Cloud-LLM escalation.** Zero cloud calls on any of the three paths. If `architect-agent` or `gcse-tutor` falls back to Anthropic mid-run, that is a failure mode (see Phase 6).
- **Greenfield / Exploration / Feasibility architect modes.** Long-running async modes (5–30 min); not appropriate for stage demo. Architect turn uses **Mode 2 (`architect_align`)** synchronous-single-pass exclusively.
- **Forge build completion.** The forge turn evidences `queue_build` publish + `pipeline.*` event consume + chat-handler notification drain. The autobuild does not need to finish on stage; one or two `stage-complete` events arriving back through the chat is the demo win.

---

## Demo narrative (Talk Track) — read this first

The runbook below is the operator script. The talk track is what the operator says aloud while the runbook executes. Roughly:

1. **Frame** (~30s): "I'm going to drive three completely different specialist agents from a single chat window in OpenWebUI. Each agent runs in its own container, each calls a different fine-tuned model on this Blackwell box behind me, and they all share one conversation."
2. **Show topology slide** (~30s): OpenWebUI box on the left, NATS in the middle, three specialist boxes on the right (architect, tutor, forge), llama-swap underneath them. "Jarvis is the supervisor — it picks which specialist to talk to based on what I type."
3. **Turn 1 — architect** (~90s): paste prompt; while inference runs, narrate the wire envelope on the second screen. Read the judgment aloud.
4. **Turn 2 — study-tutor** (~90s): paste prompt; narrate as the second specialist takes over inside the same chat session. Highlight: jarvis preserved turn-1 context but is now routing to a different agent on a different model.
5. **Turn 3 — forge** (~60s): paste a `queue_build` prompt; jarvis returns "queued" within seconds; while the build runs, take one more conversational turn that drains the forge stage-complete notifications back into the reply text. Highlight: async dispatch + notification drain — the chat is not blocked by the build.
6. **Land the point** (~60s): "Three specialists, three models, one chat, zero cloud LLM, one Blackwell box. The marginal cost of each specialist call is effectively zero. This is what local-first agent operations look like in 2026."

Total: ~6–8 minutes on stage. Buffer for architect inference latency.

---

## Phase 0: Go/no-go pre-flight (on GB10)

### 0.1 Confirm jarvis main + clean tree

```bash
cd ~/Projects/appmilla_github/jarvis
git fetch origin && git status -s -uno && git log --oneline -5
```

**Pass:** Top of log includes `076b9353` (TASK-J006-010 head, the bounded-startup-reconnect + envelope-unwrap fixes that flipped the gateway from 4/8 BLOCKED to 7/8 PASS — see [RESULTS-2026-05-12-rerun](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md) §Executive summary), or a descendant on `main`. Working tree clean.

### 0.2 Confirm NATS broker is up + auth env sourced

```bash
docker ps --filter name=ships-computer-nats --format '{{.Names}}\t{{.Status}}'
set -a && source ~/Projects/appmilla_github/nats-infrastructure/.env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
nats --server "$NATS_URL" stream ls 2>&1 | head -5
```

**Pass:** `ships-computer-nats` Up (healthy). `nats stream ls` returns ≥7 streams (PIPELINE, AGENTS, JARVIS, FLEET, NOTIFICATIONS, SYSTEM, FINPROXY) with no auth errors. If `nats stream ls` returns `nats: 'Authorization Violation'`, `RICH_NATS_PASSWORD` is not sourced — redo the `set -a && source ...` line in this shell.

### 0.3 Confirm llama-swap is serving all three model aliases

```bash
ss -tlnp 2>/dev/null | grep :9000
curl -sf http://localhost:9000/v1/models | jq -r '.data[].id' | sort
```

**Pass:** Model list contains all three aliases this demo uses:
- `qwen36-workhorse` (supervisor reasoning + supervisor's main chat model)
- `architect-agent` (fine-tuned Gemma 4 26B-A4B MoE for architect turn)
- `gemma4-tutor` (tutor turn)

If any of the three is missing, the corresponding turn will fail with `model not found` mid-inference. Check `pgrep -a llama-swap` for the pid + tail the configured log path (llama-swap is a native process on GB10, not a container — `docker logs llama-swap` does not work).

### 0.4 Confirm canonical NATS provisioning is in place

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
bash scripts/verify-nats.sh
```

**Pass:** All 7 streams + all 4 KV buckets present. The forge turn needs PIPELINE; the architect/tutor turns need AGENTS + the `agent-registry` KV.

### 0.5 Pre-warm all three models in llama-swap

The architect, supervisor, and tutor models cold-load on first request; on stage you do not want any of them to add 30–60s of cold latency. Fire one throwaway prompt at each.

```bash
for MODEL in qwen36-workhorse architect-agent gemma4-tutor; do
  echo "== warming $MODEL =="
  curl -sS http://localhost:9000/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"warmup ping\"}],\"max_tokens\":8,\"stream\":false}" \
    | jq -r '.choices[0].message.content // .error.message'
done
```

**Pass:** Each model returns non-empty content within ~10s (warm) or 30–60s (cold first call). If any model returns `.error.message`, fix llama-swap before stepping on stage. Record warmup latencies in the Phase 5 RESULTS file.

---

## Phase 1: Bring up the specialist fleet

> **Order matters here.** Start specialist-agent first (architect + PO), then study-tutor, then forge-prod, then OpenWebUI/fleet-pipe sanity check, then `jarvis serve-nats` in Phase 2. Each specialist registers into `agent-registry` KV on boot; the live KV watch inside jarvis surfaces them in the supervisor's capability catalogue.

### 1.1 Bring up specialist-agent dual-role stack (architect + product-owner)

Per the user's known-good workaround for the multi-account NATS auth — `RICH_NATS_PASSWORD` is in `nats-infrastructure/.env` but the whole file is NOT sourced (stale `OPENAI_API_KEY` baggage):

```bash
cd ~/Projects/appmilla_github/specialist-agent
export RICH_NATS_PASSWORD="$(grep '^RICH_NATS_PASSWORD=' ../nats-infrastructure/.env | cut -d= -f2-)"
export NATS_USER=rich
export NATS_PASSWORD="$RICH_NATS_PASSWORD"

docker compose -f docker-compose.dual-role.yml down
docker compose -f docker-compose.dual-role.yml up -d
sleep 5
docker ps --filter name=specialist-agent --format 'table {{.Names}}\t{{.Status}}'
```

**Pass:** Both `specialist-agent-architect-agent-1` and `specialist-agent-product-owner-agent-1` Status `Up`. (Healthcheck status varies; `Up` is sufficient.)

**Pass (registration):**

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" kv ls agent-registry
```

Output includes `architect-agent` and `product-owner-agent` rows. Empty rows = registration failed; check container logs for `Authorization Violation` (redo the `export` block + `down + up -d` in the same shell — compose only re-substitutes env at `up -d` time).

> **Specialist reconnect gap (carried over from RESULTS-2026-05-12-rerun §Other findings):** `specialist-agent-*` containers lack the bounded NATS reconnect that TASK-J006-010 added to jarvis. If NATS was bounced any time before this session, the architect/PO containers may be in an indefinite reconnect loop. The `kv ls` check above is authoritative — if the rows are missing or empty, `docker restart specialist-agent-architect-agent-1 specialist-agent-product-owner-agent-1` and re-check.

### 1.2 Confirm the architect manifest advertises `architect_align`

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    kv get agent-registry architect-agent --raw 2>/dev/null \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('agent_id:', d['agent_id']); print('tool count:', len(d['tools'])); [print('  -', t['name']) for t in d['tools']]"
```

**Pass:**

```
agent_id: architect-agent
tool count: 4
  - architect_greenfield
  - architect_align
  - architect_explore
  - architect_feasibility
```

If `architect_align` is missing the image is pre-MDF-PORT. Rebuild per [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](RUNBOOK-jarvis-architect-align-dddsw-demo.md) §0.2.

### 1.3 Bring up study-tutor (`gcse-tutor`)

```bash
cd ~/Projects/appmilla_github/study-tutor
docker compose -f docker-compose.study-tutor.yml down
docker compose -f docker-compose.study-tutor.yml up -d
sleep 5
docker ps --filter name=gcse-tutor --format 'table {{.Names}}\t{{.Status}}'
```

> The study-tutor compose is **additive** to the specialist-agent dual-role stack — they coexist cleanly.

**Pass (registration + manifest):**

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    kv get agent-registry gcse-tutor --raw 2>/dev/null \
  | python3 -c "import sys, json; d=json.load(sys.stdin); print('agent_id:', d['agent_id']); print('tool count:', len(d['tools'])); [print('  -', t['name']) for t in d['tools']]"
```

Expected:

```
agent_id: gcse-tutor
tool count: 4
  - tutor_start_session
  - tutor_turn
  - tutor_session_status
  - tutor_session_end
```

> **`/v1` suffix trap (study-tutor Bug #3):** if the container's `OPENAI_BASE_URL` lacks `/v1`, `tutor_turn` returns 404 from llama-swap mid-inference. The compose default includes `/v1`. If a manual `.env` was edited, verify with `docker exec gcse-tutor printenv OPENAI_BASE_URL` — must end in `/v1`.

### 1.4 Bring up forge-prod

Per [RESULTS-2026-05-12-rerun §Other findings](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md): `forge-prod` was `Exited (255) 2 days ago` at the time of that session. This is the bring-up step that unblocks the AC-005-06 forge notification drain evidence.

```bash
docker ps -a --filter name=forge-prod --format 'table {{.Names}}\t{{.Status}}'
```

If `Exited (...)`:

```bash
docker start forge-prod
sleep 5
docker ps --filter name=forge-prod --format 'table {{.Names}}\t{{.Status}}'
docker logs --tail=30 forge-prod
```

If forge-prod doesn't exist on this host or you need a fresh deployment, fall back to [`forge/docs/runbooks/RUNBOOK-FEAT-FORGE-008-finproxy-first-run.md`](../../../forge/docs/runbooks/RUNBOOK-FEAT-FORGE-008-finproxy-first-run.md) and [`forge/docs/runbooks/RUNBOOK-FEAT-FORGE-009-nats-core-symlink-fix.md`](../../../forge/docs/runbooks/RUNBOOK-FEAT-FORGE-009-nats-core-symlink-fix.md). The forge container ships in the `forge` repo, not `jarvis`.

**Pass:**
- `forge-prod` Status `Up`
- Last 30 log lines show: connection to NATS healthy, durable consumer attached, no `Authorization Violation`, no `register_ack_handle raised (no such table: lifecycle_bridge_registry)` (the wave-2 FOLLOWUP-A symptom from the FEAT-JARVIS-INTERNAL-001 runbook; if you see it, see Phase 6)
- `nats consumer info -j PIPELINE forge_subscriber 2>/dev/null | jq '.config.durable_name, .num_pending, .delivered.consumer_seq'` shows the durable consumer attached and `num_pending: 0` (steady state)

> **Forge bridge-translator gap (FOLLOWUP-B carried over):** even with FOLLOWUP-A landed, the bridge attaches cleanly but **zero outbound `pipeline.stage-complete.*` envelopes** ever land on the wire on a real autobuild — that's the documented FOLLOWUP-B blocker per the FEAT-JARVIS-INTERNAL-001 runbook §Known issues. If FOLLOWUP-B is unresolved at demo time, Turn 3 in §4.3 will queue successfully but the notification drain will show `notifications_drained=0` and no rendered stage-complete lines. The chat-gateway behaviour is still demonstrated — what's missing is upstream evidence of the build progressing. See §4.3 fallback narrative.

### 1.5 Confirm OpenWebUI + fleet-pipe + nats-py

```bash
docker ps --filter name=open-webui --format '{{.Names}}\t{{.Status}}'
docker exec open-webui python -c "import nats; print('nats-py', nats.__version__, 'ok')"
docker exec open-webui python -c "
import sqlite3
con = sqlite3.connect('/app/backend/data/webui.db')
cur = con.cursor()
cur.execute(\"SELECT id, name, type, is_active FROM function WHERE type='pipe'\")
print(cur.fetchall())
"
```

**Pass:**
- `open-webui` Up
- `nats-py` import succeeds (if `ModuleNotFoundError`: `docker exec open-webui pip install nats-py` — note this is lost on container restart; fleet-gateway team has a long-term fix in flight)
- The function row shows the Jarvis pipe `is_active=1`

If the pipe row is missing, paste `fleet-gateway/openwebui/nats_fleet_pipe.deploy.py` into Admin → Functions → New Function and toggle on. **Then set the `NATS_URL` Valve to include broker credentials** (`nats://rich:${RICH_NATS_PASSWORD}@localhost:4222`) — the default `nats://localhost:4222` will silently fail with `Authorization Violation` and the chat reply spins for 120s. See [`RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md`](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md) §3.2.

### 1.6 KV registry final check — all four agents live

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" kv ls agent-registry
```

**Pass:** Output lists at minimum:

```
architect-agent
gcse-tutor
jarvis              # added in Phase 2 below
product-owner-agent
```

(`forge` does not register into `agent-registry` — forge consumes from JetStream `PIPELINE` stream, not the request-reply fleet bus, so its presence is verified by the consumer state in §1.4, not by KV.)

---

## Phase 2: Boot `jarvis serve-nats`

This subsumes Phases 0.5 + 2 + 2.3 of [`RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md`](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md) for context-portability.

### 2.1 Boot jarvis in serve-nats mode

```bash
cd ~/Projects/appmilla_github/jarvis
set -a && source ~/Projects/appmilla_github/nats-infrastructure/.env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
JARVIS_LOG_LEVEL=INFO .venv/bin/jarvis serve-nats \
    --nats "$JARVIS_NATS_URL" \
    2>&1 | tee /tmp/jarvis-multi-specialist-smoke.log
```

**Pass:**
- `nats_connect_success` ✅
- `fleet_register_published` ✅
- `jarvis_startup_complete nats_available=true graphiti_available=<...> capabilities_mode=live` ✅
- `jarvis_serve_nats_subscribed` naming `agents.command.jarvis` ✅
- `jarvis_serve_nats_ready` ✅
- Process stays running (run-forever loop). Leave this terminal pane visible — it's the on-stage log feed.

Heartbeat verification (optional, for the dress rehearsal — not for the live talk): KV-revision tick on `agent-registry` jarvis row 30–60s apart, per [`RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md`](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md) §2.1.

### 2.2 Pre-stage CLI smoke (one-shot, not on stage)

Before opening the browser, verify the wire is alive with a CLI request against jarvis. This catches envelope-unwrap regressions in seconds — the same probe that surfaced TASK-J006-009 when it was open.

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    request agents.command.jarvis \
    '{"command":"chat","args":{"message":"list available agents","adapter":"runbook-smoke"},"correlation_id":"multi-spec-smoke-001"}' \
    --timeout 60s
```

**Pass:** Response is a JSON `ResultPayload` with `success: true` and `result.response` naming at least `architect-agent`, `product-owner-agent`, `gcse-tutor` (forge will be absent from this list — it's not in `agent-registry` KV, see §1.6 note).

If this returns nothing or `nats: 'no responders available'`, jarvis serve-nats is not listening on `agents.command.jarvis`. Re-check §2.1.

---

## Phase 3: Open wire-taps for the demo (parallel session — talk's "live wire" mirror)

These are the panes mirrored on the stage screen behind you. Start them **before** §4 so envelopes are captured live as they happen.

### 3.1 Tail `agents.command.>` (catches inbound jarvis commands + downstream architect + tutor dispatch envelopes)

In a second pane:

```bash
set -a && source ~/Projects/appmilla_github/nats-infrastructure/.env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.command.>" --raw \
  | tee /tmp/jarvis-multi-specialist-e2e-command.log
```

> **Flat subjects only.** The canonical subject is `agents.command.<agent_id>` with no further token. `agents.command.architect-agent.>` matches nothing — that's the Bug #4 trap captured in the study-tutor and FEAT-JARVIS-006 runbooks.

### 3.2 Tail `agents.result.>` (catches jarvis reply envelopes — fan-out side; the point-to-point reply rides `_INBOX.>`)

In a third pane:

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.result.>" --raw \
  | tee /tmp/jarvis-multi-specialist-e2e-result.log
```

> Specialist replies to jarvis ride the `_INBOX.>` request/reply inbox, not `agents.result.<specialist>` (see [architect-align runbook footnote](RUNBOOK-jarvis-architect-align-dddsw-demo.md) §5.2). The `agents.result.>` tap above is for jarvis's fan-out result envelope to the OpenWebUI gateway, not the specialist→jarvis reply leg. For the architect/tutor specialist reply leg, see §3.4 below.

### 3.3 Tail `pipeline.>` (catches forge queue + stage-complete envelopes for Turn 3)

In a fourth pane:

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "pipeline.>" --raw \
  | tee /tmp/jarvis-multi-specialist-e2e-pipeline.log
```

**Expected during §4.3:**
- One `pipeline.build-queued.<feature_id>` envelope (jarvis publishes)
- Subsequent `pipeline.build-started.<feature_id>` + `pipeline.stage-complete.<feature_id>` envelopes (forge publishes; **gated on FOLLOWUP-B being resolved** per §1.4 note)

### 3.4 (Optional) Tail `_INBOX.>` for the specialist reply leg

If the dress-rehearsal verification needs explicit evidence of the architect/tutor specialist→jarvis reply leg, add a fifth pane (skip for the live talk — too many panes):

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "_INBOX.>" --raw \
  | tee /tmp/jarvis-multi-specialist-e2e-inbox.log
```

`_INBOX.>` is high-traffic across the cluster; post-filter the tee'd log by correlation_id after each turn to extract just your envelope, per the architect-align runbook §5.2 recipe.

---

## Phase 4: The single-session OpenWebUI demo — three heterogeneous dispatches

### 4.0 Open OpenWebUI and select Jarvis

In the browser at `http://promaxgb10-41b1:8080/`, select **Jarvis** from the model dropdown. **Use a single chat session for all three turns + the recap turn** — per-gateway session retention across heterogeneous specialist dispatches is part of what this runbook evidences (it's the strongest demo of the gateway's per-adapter session model).

> **GB10 port note:** OpenWebUI runs `network: host` on GB10 and listens on `:8080`, not the upstream default `:3000`. Confirm with `ss -ltn | grep :8080` if anything looks off.

### 4.1 Turn 1 — Architect: `architect_align` (Option A, the talk headliner)

Paste:

```text
I'd like the architect to evaluate whether adding a Claude Opus 4.7 escalation tool to the jarvis supervisor is architecturally sound. The escalation would only fire when the local reasoner has low confidence on safety-critical or high-stakes user requests, and would be bounded by a per-session budget cap. The relevant ADR is ADR-ARCH-001, which commits jarvis to local-first inference via llama-swap and explicitly keeps cloud LLMs out of the supervisor's hot path. Does this proposal align with ADR-ARCH-001's local-first invariant, or what would need to change in the ADR or the supervisor's contract for it to be aligned?
```

**What should happen:**

1. Supervisor recognises this as architect-routable work.
2. Resolves `architect_align` from the live capability catalogue.
3. Constructs `payload_json` with three fields (`context`, `proposal`, `question`) from the prose — the typed `Args (required):` schema is rendered in the supervisor's capability prompt block post-TASK-CAPS-PROMPT-001 (see architect-align runbook §4.2).
4. Calls `dispatch_by_capability(tool_name="architect_align", payload_json="{...}", timeout_seconds=180)`.
5. Waits for the architect's inference (30–90s warm; longer cold).
6. Renders the returned `AlignmentJudgment` to the chat.

**Pass:**
- Chat renders a reply within ~120s (faster on warm `architect-agent` post-§0.5).
- Reply shows judgment / confidence / reasoning / suggestions, all populated.
- `/tmp/jarvis-multi-specialist-e2e-command.log` has one envelope on `agents.command.jarvis` (the inbound OpenWebUI command) + one envelope on `agents.command.architect-agent` (the dispatch).
- The dispatch envelope has an empty `args.message` field — this is the characteristic `dispatch_by_capability` wire shape, not a flat chat command. The actual payload is in `args.payload_json` (or equivalent — see [RESULTS-2026-05-12-rerun §Wire-tap correlation table](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md) for the May 2026 dispatch shape).

**Capture:** the `correlation_id` of the architect dispatch envelope (visible in the pane from §3.1). You'll need it for §5 evidence.

> **Stage tip:** while the architect runs, narrate the topology + point at the second pane as the dispatch envelope lands. The 30–90s inference window is the talk's "look how it's really working" beat.

### 4.2 Turn 2 — Study-tutor: GCSE Macbeth session + dagger soliloquy

In the **same chat session**, paste:

```text
Now please start a GCSE English Literature tutoring session on Macbeth, focused on AO1 and AO2 (knowledge of the text and language analysis), then ask the tutor to walk me through how Shakespeare uses imagery to characterise Macbeth in his "Is this a dagger which I see before me" soliloquy.
```

**What should happen:**

1. Supervisor recognises this as tutor-routable work (note: the supervisor MUST switch routing context away from the architect — turn-1's architect context is in the session but should not bias turn-2's routing).
2. Resolves `tutor_start_session` from the live KV catalogue.
3. Calls `dispatch_by_capability(tool_name="tutor_start_session", ...)` — sub-second (no LLM call).
4. On success, calls `dispatch_by_capability(tool_name="tutor_turn", ...)` for the dagger-soliloquy question — 10–30s of `gemma4-tutor` inference warm.
5. Renders the tutor's coaching prompt to the chat.

**Pass:**
- Chat renders a tutor-shaped reply (coaching prompt + Socratic question) within ~30–45s warm.
- Wire-tap (§3.1) shows two envelopes in succession on `agents.command.gcse-tutor` — one for `tutor_start_session`, one for `tutor_turn`. Each has its own `correlation_id`; the supervisor preserves the parent `correlation_id` chain through.
- The reply tone is markedly different from Turn 1 (Socratic / coaching vs analytical / judgment-shaped) — visual confirmation that a different specialist + model handled this turn.

**Capture:** both `correlation_id`s (start_session + turn).

> **Stage tip:** highlight that the chat session is the same as Turn 1 — you didn't open a new chat, didn't switch models in the dropdown, didn't change anything about your prompt format. The supervisor chose the tutor because of what you asked for. This is the routing-by-meaning beat.

### 4.3 Turn 3 — Forge: `queue_build` (async dispatch + notification drain)

In the **same chat session**, paste a forge build request. Pick a feature spec + repo you know is safe to autobuild — for the dress rehearsal, pick a known-small no-op feature in your most-stable repo. **Choose this pair before stepping on stage** and substitute it into the prompt below.

```text
Please queue a forge build for FEAT-<EXAMPLE> from features/feat-<example>/<example>.yaml in <org>/<repo> on main — I want to confirm forge notifications come back through this chat session.
```

**What should happen:**

1. Supervisor recognises this as a `queue_build` request — pattern-A fire-and-forget per ADR-SP-014.
2. Calls `queue_build(feature_id="FEAT-<EXAMPLE>", feature_yaml_path="...", repo="<org>/<repo>", branch="main", originating_adapter="<auto-resolved-from-Session.adapter>")`.
3. Publishes `BuildQueuedPayload` to `pipeline.build-queued.FEAT-<EXAMPLE>` (JetStream, not the request-reply bus).
4. Returns `QueueBuildAck` JSON within a second or two — the supervisor renders "queued" + the publish_target + the correlation_id to the chat.
5. Forge-prod's durable consumer (`forge_subscriber`) on the `PIPELINE` stream dequeues the build, dispatches it, and (gated on FOLLOWUP-B per §1.4) publishes `pipeline.build-started.FEAT-<EXAMPLE>` + zero-or-more `pipeline.stage-complete.FEAT-<EXAMPLE>` envelopes back on JetStream.
6. Jarvis's chat handler subscribes to `pipeline.build-{started,stage-complete,build-complete,build-failed}.*` for this session; envelopes that arrive between turns accumulate as pending notifications on the jarvis session.

**Pass for the queue half:**
- Reply within ~5s confirms queue success with the publish_target and correlation_id.
- `/tmp/jarvis-multi-specialist-e2e-pipeline.log` shows one `pipeline.build-queued.FEAT-<EXAMPLE>` envelope with the correlation_id from the supervisor reply.
- `nats consumer info -j PIPELINE forge_subscriber 2>/dev/null | jq '.delivered.consumer_seq, .ack_floor.consumer_seq'` shows the seq incrementing (forge dequeued it). On steady-state passing post-FOLLOWUP-A, `ack_floor.consumer_seq` advances within a second or two of `delivered.consumer_seq` — see the FEAT-JARVIS-INTERNAL-001 runbook §7.2 for the canonical recipe.

To evidence the **notification drain half** (the AC-005-06 path that's been pending since [RESULTS-2026-05-12-rerun](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md)), take **one more conversational turn** ~30s after the queue confirmation — any innocuous follow-up. The chat handler will drain `session_manager.pending_notifications(session_id)` and append rendered notification lines to the reply text:

```text
While that's running — can you give me a one-line summary of what you queued, and tell me if you've heard anything back from forge yet?
```

**Pass for the drain half:**
- The follow-up reply contains forge notification lines appended at the end — typically `pipeline.build-started.FEAT-<EXAMPLE>` and any `pipeline.stage-complete` events that landed in the interval, rendered via `ForgeNotification.render_line()`.
- Smoke log (Phase 2.1) shows `chat_invoke_complete ... notifications_drained=<N>` with N>0 (the drain path was wired post-J006-009; the only reason N=0 in [RESULTS-2026-05-12-rerun](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md) was that forge wasn't producing).

**Fallback narrative if FOLLOWUP-B is unresolved at demo time:**

`queue_build` will return success and the wire-tap will show the `build-queued` envelope, but no `stage-complete` envelopes will land. Notifications_drained stays 0. The demo win is still real — the chat-gateway publishes correctly, the supervisor's tool-routing recognises a build request, the autobuild is queued. The talk-track for this fallback: "The chat is fire-and-forget — I queue the build and I'm not blocked. Forge consumes it asynchronously. In a moment we'll see stage-complete events flow back into this same chat session (gated on FOLLOWUP-B), but the gateway's job is done the second the queue ack returns."

### 4.4 Turn 4 — Recap (cross-specialist session retention)

In the **same chat session**, paste:

```text
Recap our conversation so far in three sentences — one per specialist you talked to.
```

**Pass:** The recap correctly references **all three prior dispatches** — the architect's judgment on ADR-ARCH-001, the tutor's Macbeth session, and the forge build queue. This is the strongest single piece of evidence that per-gateway session retention works across heterogeneous specialist dispatches (the [RESULTS-2026-05-12-rerun](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md) Turn 4 only had to recap two homogeneous architect-side turns; this is harder).

**Fail:** if the recap says "I don't have context from earlier" or misattributes a specialist, capture the screenshot + the wire-tap log and mark session retention regressed.

---

## Phase 5: Evidence capture

### 5.1 Save logs

```bash
mkdir -p ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/multi-specialist-demo
cp /tmp/jarvis-multi-specialist-smoke.log \
   /tmp/jarvis-multi-specialist-e2e-command.log \
   /tmp/jarvis-multi-specialist-e2e-result.log \
   /tmp/jarvis-multi-specialist-e2e-pipeline.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/multi-specialist-demo/
# (and inbox.log if you tailed §3.4)
```

**Redact credentials before committing:** `sed -i 's/:[^@]*@/:***@/g' ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/multi-specialist-demo/*.log` strips `RICH_NATS_PASSWORD` from any URL in the logs.

### 5.2 Save the three turn payloads for slides + post-talk write-up

```bash
cd ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/multi-specialist-demo
# Per-turn correlation_id from each pane in Phase 4
jq -c --arg cid "<TURN-1-CID>" 'select(.correlation_id == $cid) | .payload.result' /tmp/jarvis-multi-specialist-e2e-result.log > turn-1-architect-payload.json
jq -c --arg cid "<TURN-2-START-CID>" 'select(.correlation_id == $cid) | .payload.result' /tmp/jarvis-multi-specialist-e2e-result.log > turn-2-tutor-start-payload.json
jq -c --arg cid "<TURN-2-TURN-CID>"  'select(.correlation_id == $cid) | .payload.result' /tmp/jarvis-multi-specialist-e2e-result.log > turn-2-tutor-turn-payload.json
jq -c --arg cid "<TURN-3-CID>"       'select(.correlation_id == $cid) | .payload.result' /tmp/jarvis-multi-specialist-e2e-result.log > turn-3-forge-queue-payload.json
```

Save OpenWebUI screenshots of each turn (browser → right-click → save as PNG, or use the OS screenshot tool). One PNG per turn is the minimum; a single screenshot of the full chat at the end of Turn 4 is the strongest single artefact.

### 5.3 Write the RESULTS file

Create `docs/runbooks/RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-$(date +%F).md` using this template:

```markdown
# RESULTS — Jarvis Multi-Specialist OpenWebUI Demo (YYYY-MM-DD)

**Operator:** <name>
**Date:** YYYY-MM-DD
**Commit verified:** `<git rev-parse HEAD>`
**Demo deadline:** 2026-05-16 DDD South West
**Runbook executed:** docs/runbooks/RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md

## Per-turn outcomes

| Turn | Specialist | Tool dispatched | Outcome | Evidence |
|---|---|---|---|---|
| 1 | architect-agent | architect_align | ✅ / ❌ | `turn-1-architect-payload.json`; screenshot `turn-1.png`; correlation_id `<id>` |
| 2 | gcse-tutor | tutor_start_session + tutor_turn | ✅ / ❌ | `turn-2-tutor-{start,turn}-payload.json`; screenshot `turn-2.png`; correlation_ids `<start>`, `<turn>` |
| 3 | forge | queue_build → pipeline.build-queued | ✅ / ❌ | `turn-3-forge-queue-payload.json`; pipeline.log `pipeline.build-queued.<feat>` envelope; notifications_drained=<N> in follow-up turn |
| 4 | (no dispatch) | recap | ✅ / ❌ | screenshot `turn-4-recap.png`; recap text quoted below |

## Recap (Turn 4 evidence body — cross-specialist session retention)

> <copy verbatim from the chat>

## Wall-clock budget

| Phase | Target | Actual | Notes |
|---|---|---|---|
| §0 pre-flight + warmup | ~10 min | | |
| §1 bring-up | ~10 min | | |
| §2 jarvis serve-nats boot | ~1 min | | |
| §4.1 architect turn | ~30–90s | | warm vs cold |
| §4.2 tutor turn | ~30–45s | | warm |
| §4.3 forge queue + drain | ~30–60s | | gated on FOLLOWUP-B for the drain half |
| §4.4 recap | ~5s | | |

## Forward-references that landed (or didn't)

| Forward-reference | Resolved this session? | Note |
|---|---|---|
| FEAT-JARVIS-006 AC-005-06 (forge notification drain) | ✅ / ⏳ / ❌ | depends on forge-prod + FOLLOWUP-B |
| specialist-agent bounded reconnect (cross-repo follow-up) | n/a | unchanged this session |
| FOLLOWUP-A (forge `lifecycle_bridge_registry` migration) | ✅ / ⏳ / ❌ | per `docker logs forge-prod` Phase 1.4 |
| FOLLOWUP-B (forge bridge↔autobuild_runner state-update contract) | ✅ / ⏳ / ❌ | per pipeline.log `stage-complete` envelopes |

## Failures and follow-ups

For any turn marked ❌, capture:
- Failure mode (one sentence)
- Evidence pointer (log + line range, or screenshot)
- Follow-up task ID via `/task-create` referencing this runbook + the affected turn

## Demo-day notes (optional)

Any operator notes for 2026-05-16 — pacing, fallback narrative if Turn 3 drain doesn't fire (FOLLOWUP-B), what to highlight in each turn for the audience.
```

Commit:

```bash
git add docs/runbooks/RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-$(date +%F).md \
        docs/runbooks/evidence/multi-specialist-demo/
git commit -m "docs(runbook): RESULTS for multi-specialist OpenWebUI demo $(date +%F)"
```

---

## Phase 6: Failure modes — fast triage during rehearsal

| Symptom | Likely cause | Fix |
|---|---|---|
| OpenWebUI chat spins for 120s then times out, no envelopes on `agents.command.jarvis` | Fleet-pipe `NATS_URL` Valve set to the unauthenticated default `nats://localhost:4222` | Admin → Functions → ⚙ Valves → set `NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222` |
| `dispatch_by_capability` returns `ERROR: unresolved` for `architect_align` or `tutor_start_session` | Specialist not in `agent-registry` KV (Phase 1 registration failed) | §1.1 / §1.3 — most common: `NATS_USER`/`NATS_PASSWORD` not exported in the shell that did `up -d`; redo the export + `down + up -d` in the same shell |
| Architect/tutor specialist container is up but no envelope ever reaches it | Specialist in indefinite reconnect loop after a NATS broker bounce (specialist-agent + study-tutor lack the bounded reconnect TASK-J006-010 added to jarvis) | `docker restart specialist-agent-architect-agent-1 specialist-agent-product-owner-agent-1 gcse-tutor`; re-check `kv ls agent-registry` |
| Architect reply contains `payload.success: false` with Anthropic / `X-Api-Key` error | Container has `AGENT_MODELS__REASONING_MODEL=claude` (compose default if `.env` didn't override) | Stop, set `AGENT_MODELS__REASONING_MODEL=local` in `specialist-agent/.env`, `down + up -d` |
| Tutor turn returns 404 from llama-swap | `OPENAI_BASE_URL` in `gcse-tutor` container lacks `/v1` suffix (Bug #3) | `docker exec gcse-tutor printenv OPENAI_BASE_URL` — must end in `/v1`; edit compose env if not |
| Turn 3 queues but no `pipeline.build-started.*` ever lands | FOLLOWUP-A or FOLLOWUP-B unresolved on forge-prod | Check `docker logs forge-prod` for the `lifecycle_bridge_registry` / no such table line — if present, FOLLOWUP-A is open. If absent but no envelopes still arrive, FOLLOWUP-B is open. Use the §4.3 fallback narrative on stage |
| Recap turn (Turn 4) loses prior context | Per-gateway session retention regressed — possible regression in jarvis session keying off `args.adapter` | Capture screenshot + wire-tap (correlation_ids on each prior turn should share the same `args.adapter` value); file a P0 follow-up |
| Heavy "Suggest follow-up questions" sidecar load | OpenWebUI feature; not a regression | Each operator turn produces ~2× the visible chat traffic on `agents.command.jarvis`. Per [RESULTS-2026-05-12-rerun](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md), gateway handles this load fine. If it confuses the audience, point at it on the wire-tap pane as "background sidecar prompts the chat UI is doing" and move on |
| Wire-tap pane silent during a turn even though chat renders an answer | Subscriber on `agents.result.<specialist>.>` (trailing wildcard) instead of `agents.result.>` (flat) — Bug #4 trap | Re-subscribe per §3.2 (flat wildcard) |

---

## Phase 7: Demo close

Once §4 has rendered all four turns and §5 has saved the evidence bundle:

- [ ] §3.1 `agents.command.>` tap captured: inbound jarvis command for each of Turns 1/2/3/4, plus dispatch envelopes for Turn 1 (architect-agent) and Turn 2 (gcse-tutor ×2)
- [ ] §3.2 `agents.result.>` tap captured: a jarvis result envelope for each turn (4 turns × 1 envelope each, plus any OpenWebUI sidecar follow-up-question envelopes)
- [ ] §3.3 `pipeline.>` tap captured: `pipeline.build-queued.<feat>` envelope from Turn 3, and (if FOLLOWUP-B resolved) ≥1 `pipeline.stage-complete.*` envelope before the follow-up drain turn
- [ ] OpenWebUI screenshots of all four turns + recap saved to `evidence/multi-specialist-demo/`
- [ ] RESULTS file written, all evidence pointers populated
- [ ] If all green: tag the commit (`git tag jarvis-multi-specialist-demo-rehearsal-$(date +%F)`) and run `/task-create` for any follow-up gaps surfaced

If all four turns land, the multi-specialist demo is **green** for 2026-05-16. Take down only what's safe to take down:

```bash
# Leave running for any subsequent work on the same box:
#   ships-computer-nats, llama-swap, open-webui

# Safe to take down once the dress-rehearsal is done:
cd ~/Projects/appmilla_github/specialist-agent
docker compose -f docker-compose.dual-role.yml down

cd ~/Projects/appmilla_github/study-tutor
docker compose -f docker-compose.study-tutor.yml down

# forge-prod: leave running unless the operator owns it and needs to reclaim resources

# jarvis serve-nats: Ctrl-C in its pane — clean SIGINT teardown is itself evidenced
# in the smoke log (see RUNBOOK-FEAT-JARVIS-006 §3.7).
```

---

## See also

- **Gateway implementation + verification:** [`RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md`](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md)
- **Last known-green state of the gateway:** [`RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md`](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12-rerun-post-J006-009-010.md)
- **Architect-only demo (CLI REPL path):** [`RUNBOOK-jarvis-architect-align-dddsw-demo.md`](RUNBOOK-jarvis-architect-align-dddsw-demo.md)
- **Tutor-only demo (CLI REPL path):** [`../../../study-tutor/docs/runbooks/RUNBOOK-study-tutor-nats-fleet-demo.md`](../../../study-tutor/docs/runbooks/RUNBOOK-study-tutor-nats-fleet-demo.md)
- **Forge-only wire path (CLI REPL):** [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Fleet-pipe deployment:** `fleet-gateway/openwebui/nats_fleet_pipe.deploy.py` (paste into Admin → Functions → New Function)
- **Wire contracts:** `nats-core/src/nats_core/events/_agent.py` (CommandPayload, ResultPayload), `nats-core/src/nats_core/events/_pipeline.py` (BuildQueuedPayload)
- **`dispatch_by_capability` tool surface:** [`src/jarvis/tools/dispatch.py`](../../src/jarvis/tools/dispatch.py) `:351-410`
- **`queue_build` tool surface:** [`src/jarvis/tools/dispatch.py`](../../src/jarvis/tools/dispatch.py) `:957`
- **Chat-handler envelope unwrap + dual-publish + notification drain:** [`src/jarvis/infrastructure/chat_handler.py`](../../src/jarvis/infrastructure/chat_handler.py) (post-TASK-J006-009)
