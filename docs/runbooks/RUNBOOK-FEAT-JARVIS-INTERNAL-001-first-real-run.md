# Runbook: FEAT-JARVIS-INTERNAL-001 First Real Run — Jarvis Phase 3 Close

**Status:** Ready for execution (gap-fold rewrite per TASK-FRR-004; close criterion narrowed — see "Known issues / forward-references" below). FEAT-JARVIS-INTERNAL-001 merged to `main` (`81bb792` → `47ec4e5` → `2864173`). All cross-repo prerequisites verified shipped (cross-repo state audit 2026-05-01). What remains is operator runtime: bring up NATS + Forge + specialist-agent on GB10, then publish one `BuildQueuedPayload` from `jarvis chat` and prove that forge dequeued and acked it on the wire.

**Purpose:** Drive the wire-level `jarvis chat → queue_build → JetStream → forge serve → consume + ack` path end-to-end on GB10. This is what the **Phase 3 close criterion** per `docs/research/ideas/phase3-build-plan.md` Step 14 reduces to today; the structural roundtrip back into the chat REPL as between-prompt notifications (the original framing) is deferred to forge-followup-1 (real `dispatch_payload`) + [TASK-FRR-001](../../tasks/backlog/feat-jarvis-internal-001-followups/TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md) (forge_subscriber attach reconciliation) landing.

**Machines:**
- **GB10** (`promaxgb10-41b1`) — primary host. Runs NATS (JetStream + KV), FalkorDB/Graphiti, `forge serve` daemon, specialist-agent fleet (architect minimum), and (recommended for first walkthrough) `jarvis chat` itself.
- **Local MacBook** — secondary walkthrough host. Repeat the e2e against GB10 NATS over Tailscale once the GB10-resident pass is green.

> **GB10 first, MacBook second:** Co-resident services on the first walkthrough remove network variables when the wire goes red. The MacBook-over-Tailscale walkthrough is the *second* pass and matches the shape of forge's Phase 6.4 "clean MacBook + GB10" gate. Don't try to do both in one session.

**Predecessors (all verified shipped before walkthrough — see `Cross-repo state preconditions` below):**
- ✅ FEAT-JARVIS-INTERNAL-001 merged to `jarvis` `main`
- ✅ FCH-001 canonical NATS provisioning artefacts shipped in `nats-infrastructure` (compose, provision-streams.sh, provision-kv.sh)
- ✅ FEAT-FORGE-009 production image + `forge serve` daemon merged to `forge` `main` (`732408f`, 2026-05-01)
- ⚠️ **FEAT-FORGE-010 (orchestrator wiring) — REQUIRED for Phase 7 close** — feature is **filed** as of 2026-05-02 (`forge/tasks/backlog/forge-serve-orchestrator-wiring/`, anchor decision DDR-007); 4-wave / 11-task plan; **not yet merged**. F009 alone ships only the daemon process container; the orchestrator chain (Supervisor + dispatchers + autobuild_runner subagent + PipelineLifecycleEmitter) that actually runs autobuilds and publishes lifecycle events is wired by this new feature. **Do not run this runbook expecting Phase 7 to pass until FEAT-FORGE-010 has merged.** See "Phase 7 expectations" below for the per-stage envelope sequence the new feature delivers.
- ✅ specialist-agent architect role NATS-callable (live verification per TASK-REV-B8E4)
- ✅ nats-core 0.2.0 with `BuildQueuedPayload` schema (`pipeline.build-queued.{feature_id}`)

**Expected wall-clock:** ~60–90 minutes for a clean GB10 walkthrough. ~30 minutes for the follow-up MacBook-over-Tailscale walkthrough once GB10 is green.

**Outputs:**
- `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md` capturing per-phase outcomes, evidence pointers, and any runbook gap-folds
- A chat transcript saved at `~/.jarvis/transcripts/<correlation_id>.txt` (or equivalent — capture verbatim from terminal scrollback if no auto-save)
- A Graphiti trace dump for the routing-history entry + stage-complete edges (proves DDR-029 append-only edges are landing as designed)
- A `command_history.md` entry per LES1 §8 — every shell block in this runbook executed verbatim with timestamps
- A row appended to `docs/research/ideas/phase3-build-plan.md` Status Log declaring **Phase 3 closed**

---

## Known issues / forward-references

This runbook has been gap-folded across two waves of GB10 first-real-run results:

- **Wave 1** (2026-05-01, correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`) — original 13-gap fold. Resolved as of wave 2.
- **Wave 2** (2026-05-08, correlation_ids `af772739-9ebf-473b-b8b7-32c234ccdb73` / `7657ed5a-8d24-4c78-b615-aef7bf835b74`, post-PEBR-WIREUP at forge HEAD `1b82236`) — the **current** state. PEBR-WIREUP composes `LifecycleBridgeWireup` into `bind_production_serve`, but two integration gaps land Phase 7 in a known-FAIL signature; the runbook forward-references them so the operator does not interpret the FAIL as their own setup mistake.

The active forward-references for wave 2 are:

| ID | Repo | Summary | Affects phase | Workaround in runbook? |
|---|---|---|---|---|
| TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A | forge | `bind_production_serve` calls `apply_at_boot` and `_bridge_coexistence.apply_migration` but does **not** call `forge.persistence.migrations.lifecycle_bridge_registry.apply()`. The bridge's `register_ack_handle` raises `no such table: lifecycle_bridge_registry` on first dispatch and silently degrades to a legacy ack_callback that doesn't translate SSE → envelope publishes. **Symptom on the wire:** every inbound `pipeline.build-queued.*` is dequeued but no `pipeline.build-started.*` / `stage-complete.*` envelope is ever published; JetStream `ack_floor` does not advance. **Symptom in `docker logs forge-prod`:** `pipeline_consumer: register_ack_handle raised (no such table: lifecycle_bridge_registry) for feature_id=… correlation_id=…; continuing with legacy ack_callback fallback` on every dispatch. ~5-line fix in `forge/src/forge/cli/_serve_production.py` Step 3.5b. | §7 (the whole phase will FAIL until landed) | No — runbook forward-references and the Phase 7 FAIL is **expected** today; do not hot-fix in-flight |
| TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B | forge | Even with FOLLOWUP-A applied, the bridge attaches cleanly per its own logs (`lifecycle_bridge.attach … observer task scheduled` + successful HTTP 200 on the SSE GET against the langgraph-runner sidecar) but **zero outbound envelopes** ever land on the wire. Hypothesis: the autobuild_runner subagent runs a long deepagents tool loop without producing the `_update_state` transitions the bridge translator looks for. Recommend structured logging in `forge.lifecycle_bridge.translator` + rerun of `tests/integration/test_lifecycle_bridge_sidecar_e2e.py`. | §7 (still FAILs after FOLLOWUP-A lands, until B lands) | No — runbook forward-references; expected FAIL until B lands |
| forge-followup-2 | forge | `forge serve` parses `FORGE_LOG_LEVEL` into `ServeConfig.log_level` but historically did not call `logging.basicConfig()`, leaving `docker logs forge-prod` empty even on successful consume. **Status:** the 2026-05-08 wave-2 evidence (`/tmp/jarvis-runbook-evidence/phase7-forge-prod-logs.log`) shows `docker logs forge-prod` now has substantial content, suggesting this may already be partially or fully resolved at HEAD `1b82236`. Verification deferred to wave 3. Until verified, the runbook keeps the `nats consumer info -j` belt-and-braces pattern from wave 1. | §2.2 (forge logs), §7.2 (forge log tail) | Yes — §7.2 uses `nats consumer info -j` to prove consume+ack |
| forge-followup-3 | forge | `scripts/build-image.sh` cd's to forge's parent and runs `--build-context nats-core=../nats-core`, which from the parent resolves to `~/Projects/nats-core` (does not exist on the canonical layout). | §2.1 (image build) | Yes — §2.1 invokes `docker buildx build` directly from inside `forge/` |
| forge-followup-orchestrator-graph | forge | `forge/langgraph.json` declares an `orchestrator` graph at `./src/forge/agent.py:agent` whose import statement (`from agents import create_orchestrator`) fails to resolve — there is no `agents` Python package on the forge import path. Boots of `langgraph dev` against the canonical `langgraph.json` therefore fail to load any graph. | §2.0 (langgraph-runner sidecar) | Yes — §2.0 boots the sidecar with a stripped `langgraph.json` containing only `autobuild_runner` |

**Resolved follow-ups (no longer forward-referenced; demoted to "✅ resolved" footnotes here for archeology):**

- ✅ **TASK-FRR-001** *(resolved 2026-05-08)* — `JARVIS` stream / `agent-registry` KV / `forge_subscriber` consumer reconciliation with canonical `nats-infrastructure` provisioning. Wave-2 evidence (`/tmp/jarvis-runbook-evidence/phase5-boot.log`) shows a clean `jarvis_startup_complete` with `nats_available=true, capabilities_mode=live` and **zero** of the documented wave-1 NATS subscription warnings. Removed from §5.1 expected-warnings (see wave-2 §5.1 below).
- ✅ **TASK-FRR-002** *(resolved earlier; archived in `tasks/completed/`)* — `lifecycle.py` `OPENAI_BASE_URL` clobber + misleading `.env.example` field. Documented historically; §0.4's local-only mandate prose stands.
- ✅ **TASK-FRR-003** *(resolved earlier; archived in `tasks/completed/`)* — DDR-019 trace-offload autocreate. §8.3's `mkdir -p` precondition still recommended for runbook discipline.
- ✅ **forge-followup-1** *(superseded by PEBR-WIREUP at forge HEAD `1b82236`, 2026-05-08)* — wire `dispatch_payload` to the real `pipeline_consumer` orchestrator + stage-complete publish path. PEBR-WIREUP composed `LifecycleBridgeWireup` into `bind_production_serve` and rebound the dispatch chain; the wave-1 receipt-only-stub failure mode no longer reproduces. The new gating constraints are FOLLOWUP-A and FOLLOWUP-B (above).

**For the operator:** read this section before executing. The wave-2 reality is that **Phases 0–6 should run cleanly with no manual gap-folds**, and **Phase 7 will FAIL with the FOLLOWUP-A symptom signature** (or, once FOLLOWUP-A lands, the FOLLOWUP-B signature) until those forge-side fixes ship. The Phase 7 FAIL is **expected** and is itself the evidence trail; do not interpret it as a setup mistake on your host. The close criterion that this runbook proves end-to-end **today** is *"forge consumed, ack tracked, and the FAIL signature matches FOLLOWUP-A or FOLLOWUP-B as documented"* — the structural roundtrip back into the chat REPL as between-prompt notifications becomes provable once both forge follow-ups land.

---

## Why this runbook exists

Every previous Jarvis exercise has been one of:
- A unit test (mocked NATS, mocked Forge)
- An integration test (in-memory NATS substrate)
- An adapter test (NATS reachable but no real consumer)

This is the first time:
1. `queue_build` will publish a real `BuildQueuedPayload` to JetStream
2. A real `forge serve` daemon will dequeue it via the durable consumer and dispatch a real autobuild
3. Real `pipeline.stage-complete` / `pipeline.build-paused` events will flow back from forge to jarvis with the same `correlation_id`
4. The chat REPL's `pending_notifications(session_id)` drain will render those events as between-prompt notifications via `ForgeNotification.render_line()`

The dominant failure mode for first real runs is **integration drift between code that passed unit tests and the substrate it actually talks to**. Forge's F008 validation rerun caught five copy-paste defects this way (folded back as F008-RERUN-001); LES1 §8 makes this a first-class lesson. **Every command in this runbook is a unit of evidence. Capture verbatim and gap-fold any drift.**

---

## Cross-repo state preconditions (last refreshed 2026-05-08)

Confirm the assumptions baked into this runbook still hold before executing:

| Repo | Required state | Last verified |
|---|---|---|
| `jarvis` | `main` includes `2864173` (FEAT-JARVIS-INTERNAL-001 close). 2026-05-08 walkthrough exercised at HEAD `60cee6b`. | 2026-05-08 |
| `nats-infrastructure` | Has `docker-compose.yml` + `streams/provision-streams.sh` + `kv/provision-kv.sh`. Streams: PIPELINE, AGENTS, JARVIS, FLEET, NOTIFICATIONS, SYSTEM, FINPROXY. KV: agent-status, agent-registry, pipeline-state, jarvis-session. | 2026-05-08 |
| `forge` | `main` includes the PEBR-WIREUP commit `1b82236` (`fix(FEAT-PEBR): compose LifecycleBridgeWireup in bind_production_serve`). PEBR-WIREUP supersedes the wave-1 FEAT-FORGE-010 framing — the dispatch chain is now composed in `bind_production_serve` and the daemon's startup log line *"forge-serve: dispatch chain composed; `_serve_daemon.dispatch_payload` rebound to handle_message dispatcher (receipt-only stub no longer reachable)"* proves it. **However, two integration gaps land Phase 7 in a known-FAIL signature** — the missing `lifecycle_bridge_registry` migration (FOLLOWUP-A) and the bridge↔autobuild_runner state-update contract (FOLLOWUP-B). See the Known issues table above. `pyproject.toml` declares `nats-core>=0.3.0,<0.4` but the active install resolves via `[tool.uv.sources] nats-core = "../nats-core"` (editable). | 2026-05-08 (PEBR-WIREUP portion); pending (FOLLOWUP-A + FOLLOWUP-B for Phase 7 to close end-to-end) |
| `nats-core` | Sibling of forge. Version `0.2.0`. `BuildQueuedPayload` defined at `src/nats_core/events/_pipeline.py:265`. **Note:** the formal schema does not declare `task_id`/`mode` — `ConfigDict(extra="allow")` permits them as untyped extras. **Not relevant for FEAT-JARVIS-INTERNAL-001 (Mode B).** | 2026-05-08 |
| `specialist-agent` | Architect role NATS-callable (verified TASK-REV-B8E4). PO role recently fixed (TASK-MDF-PORT/POLR Apr 17) but **not required for this run** — FEAT-JARVIS-INTERNAL-001 is documentation-only and dispatches no PO work. | 2026-05-08 |

If any row above has drifted, stop and resolve drift before proceeding.

---

## Phase 0: Go/no-go pre-flight

### 0.1 Confirm `jarvis main` is on the FEAT-JARVIS-INTERNAL-001 close commit

```bash
cd ~/Projects/appmilla_github/jarvis
git fetch origin
git status
git log --oneline -5
```

**Pass:** Working tree clean, branch is `main` up to date with `origin/main`, top of log includes `2864173` (or a later commit that does not revert the FEAT-JARVIS-INTERNAL-001 close).

**If not on main:** check out `main` and reconcile any local work before continuing — the e2e test must run against the merged surface, not a feature branch.

### 0.2 Confirm GB10 is reachable

```bash
ssh promaxgb10-41b1 'uname -a && uptime'
ping -c 2 promaxgb10-41b1
```

**Pass:** SSH succeeds, ping returns at least one ICMP reply.

> If running this entire runbook **from GB10**, treat the `ssh promaxgb10-41b1 …` prefixes as no-ops — `/etc/hosts` on the GB10 maps `promaxgb10-41b1` to `127.0.0.1`, so commands run locally either way (mirrors forge's RUNBOOK-FEAT-FORGE-008-validation §0 note).

### 0.3 Apply the forge nats-core symlink fix on GB10 (one-time)

The forge production image build path needs this; the `forge serve` runtime image doesn't, but if you're going to autobuild anything else on GB10 later you'll want it. Skip if already done.

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/forge && \
    ls -la .guardkit/worktrees/nats-core 2>/dev/null || \
    ln -s ../../../nats-core .guardkit/worktrees/nats-core && \
    ls -la .guardkit/worktrees/nats-core/pyproject.toml'
```

**Pass:** `pyproject.toml` resolves under the symlink. See [`forge/docs/runbooks/RUNBOOK-FEAT-FORGE-009-nats-core-symlink-fix.md`](../../../forge/docs/runbooks/RUNBOOK-FEAT-FORGE-009-nats-core-symlink-fix.md) for the full diagnosis if it errors.

### 0.4 Confirm provider keys + NATS auth + local-only model selection are present

> **Local-only ethos (per ADR-ARCH-001):** the supervisor always routes through llama-swap on `:9000` regardless of any cloud-OpenAI URL the operator sets. `lifecycle.py:569-570` unconditionally sets `OPENAI_BASE_URL=<llama_swap_base_url>/v1` at startup; the `.env.example` `JARVIS_OPENAI_BASE_URL` field does **not** override this and will be retired (forward-ref [TASK-FRR-002](../../tasks/completed/feat-jarvis-internal-001-followups/TASK-FRR-002-drop-misleading-jarvis-openai-base-url-field.md)). Cloud provider keys (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, etc.) are **not required** for this run — pick a `JARVIS_SUPERVISOR_MODEL` that llama-swap actually serves.

```bash
ssh promaxgb10-41b1 'env | grep -E "JARVIS_NATS|JARVIS_GRAPHITI|JARVIS_OPENAI_API_KEY|JARVIS_SUPERVISOR_MODEL|RICH_NATS_PASSWORD" | sed "s/=.*/=<set>/"'
```

**Pass:** At least the following are set (values masked is fine):

- `JARVIS_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@localhost:4222` (on GB10) or `nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222` (from MacBook over Tailscale).
  **The running NATS server uses multi-account auth (APPMILLA / FINPROXY / SYS).** A bare `nats://localhost:4222` will fail to publish and `verify-nats.sh` will misreport streams as `[MISSING]` (it silently swallows `nats stream ls` auth errors).
  Alternative: set `JARVIS_NATS_CREDENTIALS_PATH` to a `.creds` file path if you have one.
- `JARVIS_OPENAI_API_KEY` — used as a bearer token against llama-swap; any non-empty string is accepted (llama-swap doesn't validate it).
- `JARVIS_SUPERVISOR_MODEL` — must name a model llama-swap actually serves. **The `.env.example` default `openai:jarvis-reasoner` is stale**; `jarvis-reasoner` is not a model llama-swap exposes. Working values for this walkthrough:
  - `openai:qwen36-workhorse` (used in the 2026-05-01 GB10 run — successful queue)
  - `openai:gemma4-tutor`
  - `openai:qwen-graphiti`
  - (Embeddings model `nomic-embed` is also served but is not a chat model.)

**Optional (graceful soft-fail if absent):**
- `JARVIS_GRAPHITI_ENDPOINT` — Graphiti HTTP endpoint (e.g. `http://localhost:8080` on GB10). Without it, jarvis takes the DDR-019 trace-offload soft-fail path (writes to `~/.jarvis/traces/`; see TASK-FRR-003 for the autocreate fix).

**If `JARVIS_NATS_URL` lacks credentials:** stop. The supervisor will appear to boot, but `queue_build` publishes will fail at the wire and `verify-nats.sh` (Phase 1.2) will lie about stream presence. Either source the NATS env file (`source ~/Projects/appmilla_github/nats-infrastructure/.env`) or export `RICH_NATS_PASSWORD` and rebuild the URL inline.

---

## Phase 1: Canonical NATS up on GB10

### 1.1 Bring up NATS via `nats-infrastructure` compose

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    docker compose ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
```

**Pass:** A `nats` (or similarly named) container is running, status `Up`, ports include `4222` (client) and `8222` (monitoring).

**If not running:**
```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    docker compose up -d && \
    sleep 5 && \
    docker compose ps'
```

### 1.2 Verify the canonical streams + KV buckets are provisioned

> **Auth sourcing required.** `verify-nats.sh` and the provisioning scripts shell out to the `nats` CLI, which needs `NATS_URL` (with credentials) exported in the same shell. Without auth, `nats stream ls` returns an auth error that the verify script silently swallows and treats as "stream missing" — so a green-volume cluster looks fresh and red. **Always source `nats-infrastructure/.env` first.**

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" && \
    bash scripts/verify-nats.sh'
```

**Pass:** `verify-nats.sh` reports all 7 streams present (PIPELINE, AGENTS, JARVIS, FLEET, NOTIFICATIONS, SYSTEM, FINPROXY) and all 4 KV buckets present (agent-status, agent-registry, pipeline-state, jarvis-session).

> **If you see all streams `[MISSING]`:** stop and check that `NATS_URL` is exported with credentials in the current shell. The 2026-05-01 GB10 run hit this: the verify script can't tell auth-failure apart from stream-absence, so a misreport is the standard symptom of forgotten auth. Three leftover test streams from earlier runs (`PERSISTENCE_TEST`, `RETRIEVAL_TEST`, `SURVIVAL_TEST`) may also appear in `nats stream ls` output — they are unrelated drift and not blocking.

**If a stream or bucket is genuinely missing** (typically because the JetStream volume is fresh — see LES1 §7 / TASK-NI-PSBUG):
```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" && \
    bash streams/provision-streams.sh && \
    bash kv/provision-kv.sh && \
    bash scripts/verify-nats.sh'
```

The provisioning scripts are idempotent. Re-run `verify-nats.sh` afterward to confirm green.

> **Critical (LES1 §7 / TASK-MDF-PRVS):** A fresh-volume NATS without provisioning will accept publishes (PubAck) but **not retain or deliver them** — exactly the failure mode that masked the MacBook reds. If `verify-nats.sh` is green (with auth sourced!) you're past this trap.

### 1.3 Confirm `pipeline.build-queued.*` is bound to the PIPELINE stream

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    docker exec -i $(docker ps -qf name=nats) \
        nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
        stream info PIPELINE -j' | \
    jq -r '.config.subjects[]'
```

**Pass:** Output includes `pipeline.build-queued.>` (or `pipeline.>` — the canonical PIPELINE stream covers `pipeline.>`, which subsumes `pipeline.build-queued.*`).

---

## Phase 2: Forge `serve` daemon running and subscribed

### 2.0 Start the `langgraph-runner` sidecar (NEW in wave 2)

> **Why this is a separate phase now.** Post-PEBR-WIREUP (forge HEAD `1b82236`+), `bind_production_serve` requires `FORGE_AUTOBUILD_RUNNER_URL` pointing at a reachable `langgraph-runner` sidecar. With the env var unset, the daemon crashes on boot with `ValueError: bind_production_serve: 'autobuild_runner_url' is required but missing/empty` — there is no in-process ASGI fallback in production. The deployment topology is now: `forge-serve` container + `langgraph-runner` sidecar (typically `langgraph dev` against the forge repo). §2.0 brings the sidecar up before §2.2 boots `forge serve`.
>
> **Caveat — `forge/langgraph.json` `orchestrator` graph fails to import (forge-followup-orchestrator-graph).** The canonical `langgraph.json` declares both an `orchestrator` graph (at `./src/forge/agent.py:agent`) and an `autobuild_runner` graph. The `orchestrator` graph's import path (`from agents import create_orchestrator` at `forge/src/forge/agent.py:23`) does not resolve — there is no `agents` package on the forge import path — so `langgraph dev` against the canonical config fails to load any graph. Until the forge follow-up lands, boot the sidecar with a **stripped** `langgraph.json` that contains only the `autobuild_runner` graph. The runbook does not need the `orchestrator` graph for FEAT-JARVIS-INTERNAL-001.

**Pre-flight 1: kill any pre-existing `langgraph dev` and clear stale in-memory queue state.**

The runbook's interactive REPL phases (§5.1, §6.1) rely on the supervisor model (`qwen36-workhorse`) responding within seconds. On a stock `llama-server -np 1` fleet, the model has a single parallel slot — and if the `langgraph dev` sidecar has a backlog of `autobuild_runner` runs from a prior session (e.g. left-over un-acked redeliveries from FOLLOWUP-A/-B development, or a prior runbook execution), it will saturate that slot with continuous `POST /v1/responses` calls and **the §6.x interactive REPL will hang indefinitely** waiting for a model response.

`langgraph dev` persists its in-memory queue across restarts via pickle files in `<cwd>/.langgraph_api/` — so simply restarting the sidecar process is **not** enough; the operator must also clear the persisted queue. **Skip this pre-flight only if you are actively using `langgraph dev` for forge dev work right now and need to preserve the in-flight runs** — in that case, set up a separate forge clone for the runbook walkthrough.

```bash
ssh promaxgb10-41b1 'pkill -f "langgraph dev" 2>/dev/null; \
    sleep 1; \
    rm -rf ~/Projects/appmilla_github/forge/.langgraph_api/ 2>/dev/null; \
    ss -lntp 2>/dev/null | grep -q ":8124 " && echo "WARN: port 8124 still in use after pkill — investigate before continuing" || echo "OK: port 8124 free, .langgraph_api/ cleared"'
```

**Pass:** `OK: port 8124 free, .langgraph_api/ cleared`. If you see the WARN line, identify the process holding `:8124` (`lsof -i :8124` or `fuser 8124/tcp`) and stop it manually before continuing — a stale dev server from another shell session is the most common cause.

**Pre-flight 2: write a stripped `langgraph.json`** alongside the forge repo (or anywhere — pass the path via `--config`):

```bash
ssh promaxgb10-41b1 'cat > ~/forge-runner-only-langgraph.json <<EOF
{
    "dependencies": ["."],
    "graphs": {
        "autobuild_runner": "./src/forge/subagents/autobuild_runner.py:graph"
    },
    "env": ".env"
}
EOF'
```

**Boot the sidecar:**

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/forge && \
    nohup .venv/bin/langgraph dev \
        --config ~/forge-runner-only-langgraph.json \
        --host 127.0.0.1 \
        --port 8124 \
        --no-browser \
        > /tmp/langgraph-sidecar.log 2>&1 &'
```

**Verify the sidecar is up before booting `forge serve`** (the daemon's fail-fast path will catch an unreachable sidecar later, but checking up-front saves a restart):

```bash
ssh promaxgb10-41b1 'sleep 3 && curl -sf http://localhost:8124/openapi.json | jq ".info.title // empty"'
```

**Pass:** `curl` returns a non-empty title (current `langgraph dev` returns `"LangSmith Deployment"`; older versions returned `"LangGraph API"`). The sidecar is now serving the `autobuild_runner` graph at `http://localhost:8124`. If the curl fails or returns nothing, tail `/tmp/langgraph-sidecar.log` — most likely cause is the import failure described in the caveat above (the stripped `langgraph.json` write above didn't land, or got pointed at the canonical config by mistake).

**Verify the in-memory queue boots clean** (no carry-over backlog from a stale persistence file that pre-flight 1 missed):

```bash
ssh promaxgb10-41b1 'sleep 3 && \
    PENDING=$(grep "Queue stats" /tmp/langgraph-sidecar.log | head -1 | grep -oE "n_pending=[0-9]+" | cut -d= -f2); \
    if [ -z "$PENDING" ]; then \
        echo "OK: no Queue stats line yet (queue is empty — no work has been enqueued)"; \
    elif [ "$PENDING" -eq 0 ]; then \
        echo "OK: queue starts clean (n_pending=0)"; \
    else \
        echo "FAIL: queue has $PENDING pending runs from a prior session — pre-flight 1 missed something"; \
        echo "      stop the sidecar (pkill -f \"langgraph dev\"), remove .langgraph_api/, retry §2.0"; \
    fi'
```

**Pass:** Either `OK` line. If `FAIL`, the operator's `.langgraph_api/` directory was not at the expected path under `~/Projects/appmilla_github/forge/.langgraph_api/` — find it (`find ~/Projects -maxdepth 4 -name ".langgraph_api" -type d 2>/dev/null`), remove it, restart the sidecar, and retry.

> When `forge-followup-orchestrator-graph` lands (the `agents`-import path is fixed or the `orchestrator` graph is removed from `langgraph.json`), this whole stripped-config dance can be replaced with a plain `langgraph dev --host 127.0.0.1 --port 8124 --no-browser` from the forge repo root. Pre-flights 1 and 2 (process kill + state clear) remain relevant regardless.

### 2.1 Build (or pull) the forge production image on GB10

> **Workaround for forge-followup-3:** `scripts/build-image.sh` cd's to forge's parent and runs `--build-context nats-core=../nats-core`, which from the parent resolves to `~/Projects/nats-core` (does not exist on the canonical layout). Until the forge follow-up lands, invoke `docker buildx build` directly from inside `forge/` so the relative `../nats-core` resolves to the correct sibling.

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/forge && \
    git pull --ff-only && \
    docker buildx build \
        --build-context nats-core=../nats-core \
        -t forge:production-validation \
        -t forge:latest \
        -f Dockerfile .'
```

**Pass:** Build completes. `docker images forge` shows fresh `forge:production-validation` and `forge:latest` tags. (The 2026-05-01 GB10 build produced a 430 MB image.)

**When forge-followup-3 lands** (fix to `scripts/build-image.sh` cwd), this block can revert to the simpler `bash scripts/build-image.sh` invocation.

### 2.2 Start `forge serve` against canonical NATS

> **Daemon-config gotchas folded here (wave 2):**
>
> 1. **`forge serve` now requires `--config <path>`** between the `forge` parent group and the `serve` subcommand. The container ships without a default `forge.yaml`. With it missing, the daemon crashes immediately with `Error: forge serve requires a forge.yaml — pass --config <path> or run from a directory containing ./forge.yaml.` (`bind_production_serve` reads `approved_originators` and the filesystem allowlist from it.) Mount the operator's `forge.yaml` and pass `--config /var/forge/forge.yaml`.
>
> 2. **`FORGE_AUTOBUILD_RUNNER_URL` is mandatory.** Wave 2's `bind_production_serve` fails fast at boot with `ValueError: bind_production_serve: 'autobuild_runner_url' is required but missing/empty` when this env var is unset. Point it at the §2.0 sidecar (`http://localhost:8124` for the canonical co-resident layout).
>
> 3. **`/home/forge/.forge/forge.db` is not in the existing `~/forge-state` volume.** The forge daemon now persists its SQLite DB at `/home/forge/.forge/forge.db` inside the container's writable layer, **not** in the existing `-v ~/forge-state:/var/forge` mount. Without an additional `-v ~/forge-prod-state/.forge:/home/forge/.forge` bind-mount, every container restart is a fresh DB and any operator-applied migrations (or hot-fixes — see FOLLOWUP-A in the Known issues table) are lost. The host directory must be pre-created and chowned to **uid 1000** (the container's `forge` user, not necessarily the host operator's uid).
>
> 4. **`FORGE_NATS_URL`, not `NATS_URL`** (carried over from wave 1). The daemon reads `FORGE_NATS_URL` exclusively; a bare `NATS_URL` is silently ignored. Must include credentials per Phase 0.4.
>
> 5. **`FORGE_HEALTHZ_PORT=8088`** (carried over from wave 1). The daemon defaults to port 8080, but `open-webui` holds 8080 host-network on the GB10. Override to 8088 (or any free port) to avoid a bind conflict.
>
> Note that `FORGE_LOG_LEVEL=info` was historically a no-op (forge-followup-2). The 2026-05-08 walkthrough captured non-trivial `docker logs forge-prod` output across a 13-minute run, which suggests the issue may already be resolved at HEAD `1b82236` — but until verified, use Phase 7.2's `nats consumer info -j` belt-and-braces pattern.

**Pre-flight 1 — write a minimal `forge.yaml`** for the daemon to read. The schema's only required block is `permissions.filesystem.allowlist` (absolute paths only; `forge/src/forge/config/models.py:209-243` rejects relatives at config-load time). All other blocks (`fleet`, `pipeline`, `approval`, `queue`) ship sensible defaults. A minimal `forge.yaml` is therefore literally:

```bash
ssh promaxgb10-41b1 'mkdir -p ~/forge-state && cat > ~/forge-state/forge.yaml <<EOF
permissions:
  filesystem:
    allowlist:
      - /home/forge/build-workspace
      # Add any other absolute paths the daemon should be allowed to read or write
EOF'
```

(The `/home/forge/build-workspace` path is a placeholder — set it to whatever the operator wants the daemon's filesystem footprint to be. The runbook does not exercise the autobuild filesystem path itself, so a single placeholder allowlist entry is enough to satisfy the schema.)

**Pre-flight 2 — pre-create + chown the host DB directory.** The chown target is **uid 1000** (the container's `forge` user, fixed by the forge Dockerfile). On hosts where the operator's uid is also 1000 (the GB10 baseline), this is invisible; on Tailscale-walkthrough hosts where the operator's uid differs, this matters:

```bash
ssh promaxgb10-41b1 'mkdir -p ~/forge-prod-state/.forge && \
    sudo chown -R 1000:1000 ~/forge-prod-state/.forge'
```

Without this mount, **every container restart is a fresh DB** and any operator-applied migrations (e.g. a FOLLOWUP-A hot-fix) are lost on the next `docker restart` / image rebuild.

**Boot the daemon** (note `--config` between `forge:latest` and `serve`, and the new `FORGE_AUTOBUILD_RUNNER_URL` env var):

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    docker rm -f forge-prod 2>/dev/null
    docker run -d --name forge-prod \
        --network host \
        -e FORGE_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
        -e FORGE_HEALTHZ_PORT=8088 \
        -e FORGE_LOG_LEVEL=info \
        -e FORGE_AUTOBUILD_RUNNER_URL="http://localhost:8124" \
        -v ~/forge-state:/var/forge \
        -v ~/forge-prod-state/.forge:/home/forge/.forge \
        forge:latest --config /var/forge/forge.yaml serve
    sleep 3
    docker logs --tail 30 forge-prod
'
```

**Pass:**
- Container status `Up (healthy)` per `docker ps`
- `/healthz` is green (verified in 2.3)
- A `forge-serve` durable consumer is attached on stream `PIPELINE` (verified in 2.3 via `nats consumer info`)
- `docker logs forge-prod` includes the wave-2 dispatch-chain composition signature: `forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)`. Absence of this exact line means PEBR-WIREUP did not land in the image — rebuild §2.1 against the current forge `main`.

**Common boot failures (read the docker logs first):**

| Error | Cause | Fix |
|---|---|---|
| `Error: forge serve requires a forge.yaml — pass --config <path>...` | Pre-flight 1 skipped, or `--config` not in the docker run command | Write the minimal `forge.yaml` per pre-flight 1; add `--config /var/forge/forge.yaml` between `forge:latest` and `serve` |
| `ValueError: bind_production_serve: 'autobuild_runner_url' is required but missing/empty` | `FORGE_AUTOBUILD_RUNNER_URL` not exported, or §2.0 sidecar not running | Confirm §2.0 sidecar is up (`curl http://localhost:8124/openapi.json`); add `-e FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124` to the docker run command |
| `pydantic.ValidationError: filesystem.allowlist entries must be absolute paths` | Pre-flight 1's `forge.yaml` has a relative path | Edit `forge.yaml` so every `allowlist` entry begins with `/` |
| Container exits immediately, `docker logs forge-prod` empty | Most likely the image was built before PEBR-WIREUP landed | Re-run §2.1 to rebuild against the current forge `main`; verify `git log` includes commit `1b82236` |

### 2.3 Confirm `/healthz` reports JetStream subscription healthy

```bash
ssh promaxgb10-41b1 'curl -s http://localhost:8088/healthz | jq .'
```

> Port `8088` here matches `FORGE_HEALTHZ_PORT=8088` from Phase 2.2. Don't drop the override — port 8080 is held by `open-webui` host-network on this box.

**Pass:** JSON response is `{"status":"healthy"}` (per `_serve_healthz.py:80` contract — 200 healthy iff JetStream subscription is live). Cross-check with the consumer attached on PIPELINE:

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    docker exec -i $(docker ps -qf name=nats) \
        nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
        consumer ls PIPELINE'
```

**Pass:** Output includes `forge-serve` (the durable consumer name).

**If `/healthz` returns anything other than `{"status":"healthy"}`:** this is the LES1 CMDW failure mode (production image silently fails to subscribe). Stop. Do not proceed to Phase 6 — investigate the container's NATS reachability and credentials before publishing anything real.

---

## Phase 3: Specialist-agent fleet — architect available

> FEAT-JARVIS-INTERNAL-001 is documentation-only and triggers no specialist dispatch. **This phase is technically optional for the close criterion**, but verifying the fleet is healthy now means we don't have to redo it on the next e2e.

### 3.1 Architect role responding on `agents.command.architect-agent`

```bash
ssh promaxgb10-41b1 'docker ps --format "{{.Names}}\t{{.Status}}" | grep specialist'
```

**Pass:** At least one container running with `--role architect` (typically `specialist-agent-architect` per the dual-role compose). PO container ✅ if also up; ⚠️ if not — note in RESULTS but don't block.

### 3.2 Smoke ping (optional)

```bash
ssh promaxgb10-41b1 'docker exec -i $(docker ps -qf name=nats) \
    nats --server nats://localhost:4222 \
    request agents.command.architect-agent.ping "{}" --timeout 10s'
```

**Pass:** Architect responds within 10s with a result envelope (any payload — we're checking the wire is up, not the response shape).

**If no response:** the architect container is up but its NATS subscription isn't bound. Restart the container and re-check before proceeding.

---

## Phase 4: Graphiti reachable from jarvis

> **Two distinct services, don't confuse them:**
> - **Graphiti MCP** — the routing-history backend. Serves on `graphiti-mcp`'s HTTP port (typically `:8080` or whatever `JARVIS_GRAPHITI_ENDPOINT` points at). Backed by FalkorDB on `whitestocks` (or local `falkordb` container).
> - **llama-swap** — the local LLM router. Serves on `:9000`. Among many other things, it exposes an `/v1/embeddings` route. It is **not** Graphiti.
>
> The 2026-05-01 GB10 run hit this confusion: a successful llama-swap embeddings probe was treated as proof Graphiti was reachable. It isn't. Below probes both services, distinctly.

### 4.1 Graphiti / FalkorDB up

```bash
ssh promaxgb10-41b1 'docker ps --format "{{.Names}}\t{{.Status}}" | grep -E "graphiti|falkor"'
```

**Pass:** A `graphiti-mcp` container is running. (FalkorDB may be local or on `whitestocks` per `FALKORDB_HOST` — local container not required.)

> **Health-state history.** The 2026-05-01 walkthrough reported `graphiti-mcp` unhealthy on GB10; the 2026-05-08 walkthrough reported it Up healthy. The runbook tolerates either state — when `JARVIS_GRAPHITI_ENDPOINT` is unset (or the endpoint is unreachable for any reason), jarvis takes the DDR-019 trace-offload soft-fail path. Capture the offload trace in §8.3 instead of querying Graphiti, and note the observed health state in RESULTS for the operator after you.

### 4.2 Probe the actual Graphiti HTTP endpoint

> **Open-webui port-conflict caveat (wave 2).** On the GB10, host-network `open-webui` holds port 8080 and serves an HTML splash page that returns HTTP 200 — a naive `curl -sf` against `http://localhost:8080/healthz` looks like success but is **not** Graphiti. The probe below adds a Content-Type guard to reject HTML responses. Note also that `graphiti-mcp` on the GB10 lives on a docker-internal network only — it is not reachable from the host. Leave `JARVIS_GRAPHITI_ENDPOINT` unset on this box and rely on the §8.3 soft-fail offload; on Tailscale-walkthrough hosts where graphiti is exposed at a host-mapped endpoint, set `JARVIS_GRAPHITI_ENDPOINT` to that endpoint and the same probe just works.

```bash
ssh promaxgb10-41b1 'PROBE_URL="${JARVIS_GRAPHITI_ENDPOINT:-http://localhost:8080}/healthz"; \
    RESP=$(curl -sf -i --max-time 5 "$PROBE_URL" 2>/dev/null || true); \
    if [ -z "$RESP" ]; then \
        echo "graphiti unreachable (curl failed)"; \
    elif echo "$RESP" | grep -i "^Content-Type:" | grep -qi "text/html"; then \
        echo "graphiti unreachable (got HTML — likely port hijack by another service such as open-webui)"; \
    elif echo "$RESP" | head -1 | grep -q "^HTTP.*200"; then \
        echo "graphiti probe OK"; \
    else \
        echo "graphiti unreachable (non-200 response)"; \
    fi'
```

**Pass:** Output is `graphiti probe OK`. Any of the three `unreachable` branches means leave `JARVIS_GRAPHITI_ENDPOINT` unset and rely on the §8.3 soft-fail offload — the runbook still completes. The HTML-splash branch in particular is a known operator hazard on the GB10; it's not a misconfiguration on the operator's part.

### 4.3 (Optional) llama-swap embeddings probe

This is **not** a Graphiti gate — it just confirms llama-swap is up so the supervisor's reasoner has somewhere to call.

```bash
ssh promaxgb10-41b1 'curl -sf -X POST http://localhost:9000/v1/embeddings \
    -H "Content-Type: application/json" \
    -d "{\"input\": \"runbook smoke\", \"model\": \"nomic-embed\"}" \
    | jq .data[0].index'
```

**Pass:** Returns `0` (the index of the first/only embedding). Use the model name `nomic-embed` — that's the embeddings model llama-swap actually serves on the GB10. (Cloud-style names like `text-embedding-3-small` will 404 against llama-swap.)

---

## Phase 5: Jarvis chat REPL smoke (no NATS publish yet)

### 5.1 Boot `jarvis chat`

> **Logging is env-var-only.** `jarvis chat` does **not** accept a `--log-level` CLI flag (no such argument exists). Only the `JARVIS_LOG_LEVEL` environment variable controls verbosity. Set it inline before invoking the binary.

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/jarvis && \
    git pull --ff-only && \
    JARVIS_LOG_LEVEL=INFO .venv/bin/jarvis chat 2>&1 | tee /tmp/jarvis-chat-phase5.log'
```

**Pass:** Banner prints, supervisor builds without error, prompt renders, tool list includes `queue_build` and `dispatch_by_capability`. The boot log terminates with a clean `jarvis_startup_complete` line carrying `nats_available=true, capabilities_mode=live` and **zero** NATS subscription warnings — specifically, none of the historical wave-1 errors (fleet-register `stream name already in use with a different configuration`, agent-registry KV bind same, `forge_subscriber` attach `BadRequestError code=10101 description='consumer must be deliver all on workqueue stream'`) reproduce. TASK-FRR-001's reconciliation fully resolved this on 2026-05-08; see the Known Issues table for the resolution footnote.

> **Two non-NATS boot lines you may see — these are operator-config-dependent, not failures:**
>
> - `web_search_provider='tavily' but TAVILY_API_KEY (JARVIS_TAVILY_API_KEY) is not set — web search will be disabled.` Reproduces on any host without `JARVIS_TAVILY_API_KEY` set; web search is optional and unrelated to the runbook's close criterion.
> - `graphiti_skipped_no_endpoint` / `graphiti_available: false`. Expected DDR-019 path when `JARVIS_GRAPHITI_ENDPOINT` is unset (see §4.2). Soft-fail offload covered by §8.3.

**If you see any `nats_*` warning that's not in the two-line list above** (fleet-register, agent-registry KV, `forge_subscriber` attach, or anything new), capture verbatim and treat as a regression — TASK-FRR-001's resolution should keep the boot clean across the full subscription set. Do not silently accept new NATS warnings as "expected"; the wave-2 baseline is a strictly clean boot.

**If supervisor fails to build entirely** (no prompt renders): the most common cause is a missing or invalid `JARVIS_SUPERVISOR_MODEL` (must name a model llama-swap serves — see §0.4) or missing `JARVIS_NATS_URL` credentials. Hit Ctrl+C (exit code 130 expected) and resolve.

### 5.2 Tool inventory smoke (in the chat REPL)

```text
> What tools do you have available?
```

**Pass:** Reasoner names `queue_build` (and others) without prompting. Don't try to actually queue anything yet — that's Phase 6.

Hit Ctrl+C to exit (clean SIGINT, exit code 130).

---

## Phase 6: End-to-end publish — `Queue FEAT-JARVIS-INTERNAL-001 for build`

> **Operator decision:** Re-queueing FEAT-JARVIS-INTERNAL-001 (already merged to `jarvis` `main`) is a *wire test* — forge will receive the build-queued message and attempt to autobuild a feature whose work is already on main. Forge's exact behaviour in that case is part of what this runbook discovers. The alternative is to pick a small fresh feature; the trade-off is more work-in-flight to interpret. **Recommended: stick with FEAT-JARVIS-INTERNAL-001** — the e2e wire is what the Phase 3 close criterion measures, not the build outcome.

> **Symptom check before booting:** if `jarvis chat` hangs at `session_started` and never gets to a model response, the most likely cause is that the §2.0 sidecar accumulated a backlog of `autobuild_runner` runs (e.g. from earlier dispatches in this same runbook session that the bridge couldn't terminal-ack — see Phase 7), and those runs are saturating the supervisor model's single `np=1` slot via continuous `POST /v1/responses` calls every ~5s. **Recovery:** stop the sidecar (`pkill -f "langgraph dev"`), clear the persisted queue (`rm -rf ~/Projects/appmilla_github/forge/.langgraph_api/`), restart §2.0 from pre-flight 1, then retry §6.1. (The wave-2 §2.0 pre-flights catch this on the *first* runbook execution; the symptom mostly recurs when re-running §6 in the same session.)

### 6.1 Boot a fresh chat REPL with full tracing

Two equivalent patterns — pick whichever matches your harness:

**Interactive (operator typing in a TTY):**

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/jarvis && \
    JARVIS_LOG_LEVEL=DEBUG \
    .venv/bin/jarvis chat 2>&1 | tee /tmp/jarvis-chat-phase6.log'
```

**Non-interactive (driving the REPL from a script or piped stdin):**

The `jarvis chat` REPL has no `--prompt` flag, but the REPL reads from `sys.stdin.readline`, so piping stdin works for runbook automation. Each line you pipe is a turn; terminate the session with EOF (and the REPL will exit cleanly with code 0 once stdin closes).

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/jarvis && \
    JARVIS_LOG_LEVEL=DEBUG \
    printf "Queue FEAT-43DE for build. The feature YAML is at .guardkit/archive/FEAT-43DE/feature_state.yaml on the main branch of guardkit/jarvis.\nWhat is happening with that build?\n" \
        | .venv/bin/jarvis chat 2>&1 | tee /tmp/jarvis-chat-phase6.log'
```

The 2026-05-01 GB10 run used the non-interactive pattern (the operator was running this from inside an autobuild harness with no TTY). Both patterns produce the same evidence; the non-interactive form is the only thing that reliably round-trips to a `tee` log when there's no terminal attached.

### 6.2 Issue the queue request

> **Critical: use the internal feature id, not the brand name.** `queue_build`'s validation regex is `^FEAT-[A-Z0-9]{3,12}$` (alphanumerics only, length 3–12). The brand-name string `FEAT-JARVIS-INTERNAL-001` contains hyphens beyond the leading `FEAT-` and exceeds 12 chars in the alphanumeric tail — it fails validation with `status: validation_error`. **Use the on-disk internal id** for the feature you're queueing.
>
> For FEAT-JARVIS-INTERNAL-001 the internal id is `FEAT-43DE` (per `.guardkit/archive/FEAT-43DE/feature_state.yaml`, archived as of `47ec4e5`). For any other feature, look up the internal id under `.guardkit/features/` (in-flight) or `.guardkit/archive/` (merged + archived).

In the REPL (or piped via the non-interactive pattern in 6.1), type:

```text
> Queue FEAT-43DE for build. The feature YAML is at .guardkit/archive/FEAT-43DE/feature_state.yaml on the main branch of guardkit/jarvis.
```

> Adjust the YAML path / repo / branch arguments to match what `queue_build`'s docstring requires; the supervisor should fill these from your prompt. If it asks clarifying questions, answer them — and **note the questions in RESULTS** as a gap-fold candidate (the runbook's prompt above should have been complete enough).

**Pass — the supervisor returns a markdown-bullet acknowledgement** rendered roughly like:

```text
FEAT-43DE has been queued for build.

- **Correlation ID:** `<uuid>`           ← save this verbatim — threads through every subsequent stage event and the Graphiti / offload trace
- **Publish target:** `pipeline.build-queued.FEAT-43DE`

Forge will pick it up from the JetStream topic. ...
```

**Match these two lines** to confirm success:
- A line beginning with `- **Correlation ID:**` carrying a UUID.
- A line beginning with `- **Publish target:**` (or `- **Target:**` — see prose-tolerance note below) carrying `pipeline.build-queued.FEAT-43DE`.

The exact narration prose ("FEAT-43DE has been queued..." / "Forge will pick it up...") is generated by the supervisor's reasoner and may vary turn-to-turn; the **two bulleted lines above are the load-bearing evidence**. The label on the second line in particular has been observed as both `- **Publish target:**` and `- **Target:**` (and may render with other near-equivalents like `- **Publishing to:**`); only the subject string `pipeline.build-queued.FEAT-43DE` is load-bearing — accept any reasonable label so long as that subject value is present.

> **Why the bullets, not the JSON?** The underlying tool returns the canonical raw JSON via `json.dumps(ack)` at [`src/jarvis/tools/dispatch.py:1238`](../../src/jarvis/tools/dispatch.py#L1238) — the dict carries `status: "queued"`, `feature_id`, `correlation_id`, `publish_target`, `queued_at`. The markdown re-rendering happens in the supervisor's tool-result presentation layer (system prompt + reasoner narration), not in `dispatch.py` itself. A future, separate task may tighten the supervisor prompt to pass through the raw JSON unchanged for non-narrative tool results — if that lands, this section can be re-tightened back to a JSON-shape match. **Do not modify `dispatch.py` to "fix" this from inside this runbook**; the tool's contract is correct. (Tracked as an optional supervisor-prompt follow-up; not blocking.)

**If you see no bullet lines at all** (the reasoner asked clarifying questions, or returned a free-form refusal): the prompt in 6.1 above was incomplete or the supervisor model is mis-configured. Re-prompt with the YAML path / repo / branch arguments inline.

**If `status: validation_error` appears** (rare — usually surfaces inline rather than as a bullet): the most likely cause is the feature_id failing the `^FEAT-[A-Z0-9]{3,12}$` regex (hyphens or > 12 chars in the tail). Substitute the internal id and retry.

**If `status: degraded` appears:** NATS publish failed. Most likely Phase 1 isn't actually green — re-run 1.2 (with auth sourced!) and verify the PIPELINE stream is bound to `pipeline.build-queued.>`.

### 6.3 Capture proof of publication on the wire

> **Don't use `nats stream view`.** It requires a TTY (interactive pager), can't be tee'd non-interactively, and on a workqueue-retention stream like PIPELINE the message is removed by the consumer's ack before any `view` command can see it anyway. Use `stream info -j` + `consumer info -j` instead — both produce the same evidence (publish landed, consumer dequeued + acked) and survive `tee`.

In a second SSH session to GB10 (or a second non-interactive shell):

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    docker exec -i $(docker ps -qf name=nats) \
        nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
        stream info PIPELINE -j' \
    | tee /tmp/jarvis-pipeline-state.json \
    | jq '{last_seq: .state.last_seq, messages: .state.messages, first_ts: .state.first_ts, last_ts: .state.last_ts}'
```

**Pass:** `state.last_seq >= 1` (one or more publishes landed). `state.messages` may read `0` because workqueue retention removes the message after ack — that's expected and is what §7.2 then proves via `consumer info`.

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    docker exec -i $(docker ps -qf name=nats) \
        nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
        consumer info PIPELINE forge-serve -j' \
    | tee /tmp/jarvis-forge-serve-consumer.json \
    | jq '{delivered: .delivered.consumer_seq, acked: (.delivered.consumer_seq - .num_pending), pending: .num_pending, redelivered: .num_redelivered}'
```

**Pass:** `delivered >= 1` (forge dequeued). `pending == 0` and `redelivered == 0` (forge acked cleanly). Capture both JSON files as evidence.

---

## Phase 7: Real per-stage lifecycle events arrive in chat as between-prompt notifications

> **What this phase tests in wave 2 (post-PEBR-WIREUP, forge HEAD `1b82236`).** PEBR-WIREUP composes `LifecycleBridgeWireup` into `bind_production_serve` and rebinds the dispatch chain — the wave-1 receipt-only stub (`_serve_daemon._default_dispatch`) is no longer reachable. **However, two integration gaps remain pending in the forge repo** and land Phase 7 in a known-FAIL signature today:
>
> 1. **FOLLOWUP-A** — `bind_production_serve` does not call `forge.persistence.migrations.lifecycle_bridge_registry.apply()` at boot, so `register_ack_handle` raises `no such table: lifecycle_bridge_registry` on every dispatch and the consumer falls back to a legacy ack_callback that does not publish lifecycle envelopes.
> 2. **FOLLOWUP-B** — even with FOLLOWUP-A applied, the bridge attaches cleanly per its own logs and the SSE GET against the langgraph-runner sidecar returns HTTP 200, but **zero outbound envelopes** ever land on the wire. Hypothesis: the autobuild_runner subagent does not drive the `_update_state` transitions the bridge translator requires.
>
> **Phase 7 is therefore expected to FAIL today**, with one of two specific signatures depending on whether FOLLOWUP-A has landed. The runbook's job in this wave is to (a) make the FAIL **deterministic** (so the operator can recognise it on sight), and (b) make the **next** step (forge follow-up landing → rerun) clear. Do not interpret a Phase 7 FAIL today as an operator-side setup mistake.
>
> **Historical note** (kept for archeology): the wave-1 walkthrough failed Phase 7 because the daemon was on the receipt-only stub; the FEAT-FORGE-010 (orchestrator-wiring) framing was the contemporary explanation. PEBR-WIREUP at HEAD `1b82236` supersedes that framing; FEAT-FORGE-010 / abandoned-FRR-001 references are no longer load-bearing for this section.

The REPL from 6.1 should still be open. With wave-2 forge HEAD `1b82236` running, the daemon dequeues the inbound `pipeline.build-queued.*` and dispatches autobuild via the SSE channel against the §2.0 sidecar — but, per FOLLOWUP-A / -B, no per-stage lifecycle envelopes flow back yet. The chat REPL still drains `pending_notifications(session_id)` before each new input prompt; in wave 2 that drain is empty, which is itself the evidence trail.

### 7.1 Confirm forge consumed, acked, and that the FAIL signature matches

In the REPL, type a small follow-up — anything that produces a new prompt cycle:

```text
> What's happening with that build?
```

**Wave-2 expected outcome — Phase 7 FAILs deterministically with one of two signatures:**

The chat REPL drains zero notifications and the reasoner narrates accordingly (e.g. *"I haven't received any updates yet"*). This is **expected** in wave 2 until FOLLOWUP-A and FOLLOWUP-B both land. Hit Ctrl+C to exit the REPL cleanly, then capture the failure signature for the evidence trail using §7.2 + §7.3 below.

**The two expected wave-2 FAIL signatures:**

- **Signature A — FOLLOWUP-A not landed yet** (the most common state today):
  - **`docker logs forge-prod`** (filtered to the correlation_id from 6.2) shows, on every dispatch:
    ```text
    pipeline_consumer: register_ack_handle raised
      (no such table: lifecycle_bridge_registry)
      for feature_id=FEAT-43DE correlation_id=…;
      continuing with legacy ack_callback fallback
    ```
  - **`nats sub "pipeline.>" --raw`** shows the inbound `pipeline.build-queued.FEAT-43DE` only; no outbound `pipeline.build-started.*` / `stage-complete.*` / terminal envelope.
  - **`nats consumer info PIPELINE forge-serve -j`** shows `ack_floor` did not advance (delivered increments, but `ack_floor` is unchanged from pre-publish baseline).

- **Signature B — FOLLOWUP-A landed, FOLLOWUP-B pending**:
  - **`docker logs forge-prod`** is clean of the `register_ack_handle raised` warning and includes:
    ```text
    forge.lifecycle_bridge.bridge: lifecycle_bridge.attach feature_id=FEAT-43DE correlation_id=… thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE
    forge.lifecycle_bridge.wireup: wireup.register_ack_handle: attached feature_id=FEAT-43DE correlation_id=…; observer task scheduled (deadline_at=…)
    httpx: HTTP Request: GET http://localhost:8124/threads/<task_id>/runs/<run_id>/stream?cancel_on_disconnect=false&stream_mode=values "HTTP/1.1 200 OK"
    ```
  - **`nats sub "pipeline.>" --raw`** still shows zero outbound envelopes after the bridge attach.
  - **`nats consumer info PIPELINE forge-serve -j`** still shows `ack_floor` unchanged.
  - **Refined two-cycle fingerprint** (forge HEAD `e1eef81`+ adds FOLLOWUP-B SSE instrumentation that exposes per-part bridge translator state — `parts_received=N` per cycle in `forge.lifecycle_bridge.translator` log lines): **cycle 1** produces `parts_received=N>0` (the autobuild_runner SSE stream IS producing `event='values'` parts; the bridge translator simply emits zero outbound lifecycle envelopes from them — that's the FOLLOWUP-B defect surface). **Cycles 2+** produce `parts_received=0` because the original autobuild run is already drained — *not* because the original run was empty. Earlier framings of Signature B conflated these two cases; the two-cycle fingerprint is the precise expected signature today.
  - **The 5-min deferred-ack deadline does NOT publish `build-failed` in this signature.** The deadline path (`observer task scheduled (deadline_at=…)` on the wireup line above) is gated on **SSE stream unreachability** (TCP reset / 5xx / connection refused) — *not* on stream silence. With a reachable-but-translator-silent stream (today's signature), the deadline expires without any terminal envelope being published. This is correct contract behaviour (don't publish failure if we don't actually know the build failed), but worth knowing so the operator does not wait out the 5-min deadline expecting a `build-failed` to "rescue" Signature B — it won't. The terminal envelope only arrives once FOLLOWUP-B lands.

**Either signature is "expected FAIL today" — do NOT treat as an operator setup mistake.** Capture which signature you're seeing in RESULTS along with verbatim log excerpts, and forward-reference FOLLOWUP-A or FOLLOWUP-B as the unblocker. Do **not** hot-fix the migration in-flight from inside the runbook execution — the hot-fix is documented in [RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md) for forensic reference but the canonical fix lives in the forge follow-up.

**Hard rejects (capture verbatim and stop — these are NOT expected wave-2 signatures):**

- Any rendered notification line whose `correlation_id` does not equal the `correlation_id` jarvis published in 6.2 — breaks DDR-029's notification-thread contract. (Note: in wave 2 there should be **no** rendered notifications at all, so any rendered line is itself worth investigating.)
- Notifications arrive but are not drained before the supervisor's response — breaks the between-prompt rendering contract jarvis-side (see DDR-030).
- A `register_ack_handle raised` warning that **persists across container restarts** even after the host-mounted `~/forge-prod-state/.forge/forge.db` has had `lifecycle_bridge_registry.apply()` run against it (per the §2.2 host DB mount). If the warning persists, the host DB mount is not actually reaching the container's `/home/forge/.forge/forge.db` — re-check the bind-mount and uid 1000 chown in §2.2 pre-flight 2.

**Once both FOLLOWUP-A and FOLLOWUP-B land**, this section will need to be re-anchored again to the full per-stage envelope sequence (`build-started`, one or more `stage-complete`, terminal `build-complete` or `build-failed`) — that's the wave-3 success criterion. The historical wave-1 / FEAT-FORGE-010 framing of this section described that target shape; the language was correct for the eventual end-state but premature for today.

### 7.2 Verify the envelope sequence on the wire (forge side)

In a third SSH session, tail the published lifecycle envelopes directly off JetStream rather than relying on the forge container's stdout:

```bash
ssh promaxgb10-41b1 'nats sub "pipeline.>" --raw' | \
    grep -i "<correlation_id_from_6.2>" | \
    tee /tmp/forge-pipeline-envelopes-phase7.log
```

**Pass:** The wire shows the same lifecycle sequence the chat REPL rendered in 7.1, in the same order, with the same `correlation_id`. Specifically:

```
pipeline.build-started.FEAT-JARVIS-INTERNAL-001
pipeline.stage-complete.FEAT-JARVIS-INTERNAL-001       (one per stage transition; N >= 1)
pipeline.stage-complete.FEAT-JARVIS-INTERNAL-001
...
pipeline.build-complete.FEAT-JARVIS-INTERNAL-001       (or build-failed)
```

`nats consumer info PIPELINE forge-serve -j` should also show `delivered=1, acked=1, num_pending=0, num_redelivered=0` for the inbound `build-queued` message — the deferred-ack contract means the message is acked only on the **terminal** lifecycle transition, so this confirms the orchestrator drove the build all the way through.

### 7.3 Tail the forge container logs for the same correlation_id

In a fourth session:

```bash
jq '{delivered: .delivered.consumer_seq, pending: .num_pending, redelivered: .num_redelivered}' \
    /tmp/jarvis-forge-serve-consumer.json
```

**Pass (when the runbook eventually goes green — wave 3):** Forge logs show the correlation_id consuming from JetStream, the autobuild_runner subagent launch, each per-stage `emit_stage_complete` call, and the terminal `build-complete`/`build-failed` publish. Capture log tail.

**Wave-2 expected (FAIL signatures — these are the contemporary failure modes, not regressions):**

| Symptom | Cause | Action |
|---|---|---|
| **`register_ack_handle raised (no such table: lifecycle_bridge_registry)` on every dispatch**; no outbound envelopes; `nats consumer info` shows `ack_floor` stuck at the pre-publish baseline | **FOLLOWUP-A** not landed. `bind_production_serve` does not call `forge.persistence.migrations.lifecycle_bridge_registry.apply()` at boot. The bridge falls back to legacy ack_callback that doesn't translate SSE → envelope publishes. | **Expected FAIL today, do NOT treat as operator setup mistake.** Capture log excerpt + consumer-info JSON in RESULTS. Forward-reference TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A. Rerun the runbook from §2.2 onwards once FOLLOWUP-A lands and the image is rebuilt. |
| **`docker logs forge-prod` is clean of the `register_ack_handle` warning, shows `lifecycle_bridge.attach … observer task scheduled` followed by SSE GET HTTP 200**, but `nats sub "pipeline.>"` captures **zero outbound envelopes** for >5 minutes | **FOLLOWUP-B** not landed (FOLLOWUP-A has landed). Bridge attaches and opens the SSE stream cleanly, but the autobuild_runner subagent does not drive the `_update_state` transitions the bridge translator looks for. | **Expected FAIL today, do NOT treat as operator setup mistake.** Capture the bridge-attach + SSE-200 log excerpts and the empty wire-tap in RESULTS. Forward-reference TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B. Rerun once FOLLOWUP-B lands. |

**Wave-3+ failure modes (will be relevant once FOLLOWUP-A and FOLLOWUP-B both land — kept here so the operator after you can interpret them):**

| Symptom | Likely cause | Action |
|---|---|---|
| **`build-started` arrives but no per-stage `stage-complete`**; long delay then `build-failed` | The autobuild_runner subagent dispatched but failed internally | Capture forge container logs for the autobuild traceback. Fold to a follow-up against the autobuild_runner. |
| **Per-stage `stage-complete` arrives but no terminal `build-complete` / `build-failed`** | The autobuild reached its terminal state but `emit_build_complete` / `emit_build_failed` did not fire. The deferred-ack contract means JetStream will redeliver the inbound `build-queued` message after `ack_wait` (1 hour). | Capture forge logs; the orchestrator's terminal-transition path is broken. Fold to a follow-up. |
| **All envelopes arrive but `correlation_id` does not match what jarvis published** | The publisher is not threading `correlation_id` through the lifecycle emitter | Capture both the inbound and outbound envelopes; reproduce the LES1 CMDW pattern. Stop and fix before re-running. |
| **The wave-1 receipt-only-stub baseline reappears** (consumer info `delivered=1, acked=1`, no envelopes, no `lifecycle_bridge.attach` log lines at all, no `register_ack_handle` warnings — i.e. the dispatch chain is silently bypassing PEBR-WIREUP) | The deployed image was built before PEBR-WIREUP merged | Confirm `git log` on the forge image's source includes commit `1b82236`. If not, the runbook's preconditions row was not satisfied; stop and re-run §2.1 to rebuild the image. |

---

## Phase 8: Capture evidence

### 8.1 Save the chat transcript

The REPL doesn't auto-persist the transcript. Copy from terminal scrollback or use the `tee` log captured in 6.1:

```bash
cp /tmp/jarvis-chat-phase6.log \
    ~/.jarvis/transcripts/<correlation_id_from_6.2>.txt
```

### 8.2 Dump the Graphiti routing-history entry

If Graphiti was reachable in Phase 4:

```bash
ssh promaxgb10-41b1 'curl -s "http://localhost:8080/v1/episodes?group_id=jarvis_routing_history&limit=20" | \
    jq ".[] | select(.content | contains(\"<correlation_id_from_6.2>\"))"' | \
    tee /tmp/jarvis-graphiti-trace.json
```

> The exact endpoint may vary by Graphiti version — adjust to whatever your deployment exposes. The DDR-029 schema is `JarvisRoutingHistoryEntry` with `outcome_type: forge_build_queue`.

**Pass:** At least one episode with the saved correlation_id, plus any subsequent stage-complete edges that landed on the same group_id.

### 8.3 If Graphiti soft-failed in Phase 4 — capture the offload trace

> **Precondition (until [TASK-FRR-003](../../tasks/completed/feat-jarvis-internal-001-followups/TASK-FRR-003-ddr-019-trace-offload-autocreate-and-non-silent-drop.md) lands):** the DDR-019 soft-fail path silently drops the trace if `~/.jarvis/traces/` doesn't exist. `mkdir -p` it before booting `jarvis chat` in §6.1, so the offload has somewhere to land.
>
> ```bash
> ssh promaxgb10-41b1 'mkdir -p ~/.jarvis/traces'
> ```
>
> When TASK-FRR-003 lands, the runtime will autocreate the directory and log loudly on every soft-fail.

```bash
ssh promaxgb10-41b1 'ls -la ~/.jarvis/traces/ && \
    cat ~/.jarvis/traces/<correlation_id_from_6.2>.json'
```

**Pass:** A JSON file with the routing-history entry persisted locally per DDR-019.

**If the directory is empty** despite the chat log showing `routing_history_write_failed`: that's the silent-drop bug TASK-FRR-003 fixes. Note in RESULTS as evidence the bug still reproduces.

### 8.4 `command_history.md` entry per LES1 §8

In `jarvis/docs/history/command_history.md` (note: underscore, not hyphen — match the on-disk filename), append a section with:
- Date + machine (`GB10` or `MacBook over Tailscale`)
- Every shell block in this runbook executed verbatim
- Annotate any block that required workarounds with `[as of commit <sha>]`
- Final pass/fail verdict per phase

---

## Phase 9: Phase 3 close

### 9.1 Write `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`

Mirror the runbook's phase structure with a `Phase | Gate | Outcome | Evidence` table. Use this skeleton:

```markdown
# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run

**Date:** <YYYY-MM-DD>
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident first walkthrough
**correlation_id:** <uuid_from_6.2>
**Outcome:** ✅ Phase 3 closed | ❌ deferred | ⏸ partial

## Per-phase outcomes

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | `git log --oneline -5` output |
| 0.2 | GB10 reachable | ✅ | ping/ssh output |
| 0.3 | forge nats-core symlink | ✅ | `ls -la` output |
| 0.4 | provider keys set | ✅ | masked env dump |
| 1.1 | NATS container up | ✅ | docker ps output |
| 1.2 | 7 streams + 4 KV buckets | ✅ | verify-nats.sh output |
| 1.3 | pipeline.build-queued bound | ✅ | stream info subjects |
| 2.1 | forge image built | ✅ | docker images output |
| 2.2 | forge serve running | ✅ | docker logs tail |
| 2.3 | /healthz green | ✅ | curl response |
| 3.1 | architect container up | ✅ | docker ps output |
| 3.2 | architect ping (optional) | ✅ / ⚠️ | nats request output |
| 4.1 | graphiti/falkordb up | ✅ / ⚠️ | docker ps output |
| 4.2 | embeddings reachable | ✅ / ⚠️ | curl response |
| 5.1 | jarvis chat boots | ✅ | /tmp/jarvis-chat-phase5.log |
| 5.2 | tool inventory smoke | ✅ | REPL transcript |
| 6.2 | queue_build returns success | ✅ | REPL transcript |
| 6.3 | message visible on PIPELINE stream | ✅ | nats stream view |
| 7.1 | between-prompt notifications render full lifecycle sequence (`build-started` + `stage-complete`×N + `build-complete`/`build-failed`, all threaded by same `correlation_id`) | ✅ | REPL transcript |
| 7.2 | wire shows the same lifecycle sequence on JetStream subjects in the same order | ✅ | /tmp/forge-pipeline-envelopes-phase7.log |
| 7.3 | forge container logs show autobuild_runner subagent launch + per-stage emit_stage_complete + terminal publish | ✅ | /tmp/forge-events-phase7.log |
| 8.x | evidence captured | ✅ | file paths |

## Runbook gaps discovered (gap-fold candidates)

| What needed manual adjustment | Suggested runbook fix |
|---|---|
| <e.g. supervisor asked clarifying questions in 6.2> | <e.g. tighten the prompt template in §6.2> |

## Decision

[ ] Phase 3 closed canonical — runbook is verbatim-runnable; no gap-folds needed
[ ] Phase 3 closed with gap-folds — runbook executed end-to-end but needs the fixes in the table above before the MacBook walkthrough
[ ] Partial — phase X failed at gate Y, follow-up task `TASK-…` filed
```

### 9.2 Append to phase 3 build plan

In `jarvis/docs/research/ideas/phase3-build-plan.md`, append a Status Log row marking Step 14 complete and Phase 3 closed (or partial). Cite the RESULTS file path.

### 9.3 Trigger the MacBook over-Tailscale follow-up walkthrough

Once GB10 is green, repeat **Phases 5–8 only** from the MacBook with these env-var differences (note that NATS auth credentials are still required — the multi-account auth is not Tailscale-IP-based):

- `JARVIS_NATS_URL=nats://rich:${RICH_NATS_PASSWORD}@promaxgb10-41b1:4222` (Tailscale-routed, with credentials)
- `JARVIS_GRAPHITI_ENDPOINT=http://promaxgb10-41b1:8080` (only if Phase 4 was green on GB10)

Append a second results section to the same RESULTS file. This matches forge's Phase 6.4 "clean MacBook + GB10" canonical-freeze pattern.

> **Walkthrough deferred until forge-followup-1 + TASK-FRR-001 land.** Without those, the MacBook walkthrough would only re-prove what GB10 already proved (publish → JetStream → forge consume + ack) — there's no new evidence in the network-isolated rerun until the stage-complete round-trip is structurally satisfiable. Re-evaluate when those follow-ups close.

---

## See also

- **Phase 3 build plan** — `jarvis/docs/research/ideas/phase3-build-plan.md` Step 14 (close criterion)
- **Forge first-real-run pattern** — `forge/docs/runbooks/RUNBOOK-FEAT-FORGE-008-finproxy-first-run.md` (this runbook mirrors its structure)
- **Forge symlink fix** — `forge/docs/runbooks/RUNBOOK-FEAT-FORGE-009-nats-core-symlink-fix.md` (one-time per-machine setup)
- **NATS canonical provisioning** — `nats-infrastructure/streams/provision-streams.sh` + `kv/provision-kv.sh` + `scripts/verify-nats.sh`
- **Routing-history schema** — `jarvis/src/jarvis/infrastructure/routing_history.py` (DDR-029 trace shape)
- **Forge notification rendering** — `jarvis/src/jarvis/infrastructure/forge_notifications.py:153–170` (`ForgeNotification.render_line`)
- **queue_build tool** — `jarvis/src/jarvis/tools/dispatch.py:956–1060` (signature + return shape)
