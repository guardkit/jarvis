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

This runbook has been gap-folded against the 2026-05-01 GB10 first-real-run RESULTS (correlation_id `a58ec9a7-27c6-485a-beac-e18675639a10`). Several of the underlying issues have source-code fixes tracked as follow-up tasks but not yet landed; the runbook documents the workaround inline and forward-references the fix here.

| ID | Repo | Summary | Affects phase | Workaround in runbook? |
|---|---|---|---|---|
| [TASK-FRR-001](../../tasks/backlog/feat-jarvis-internal-001-followups/TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md) | jarvis | Reconcile `JARVIS` stream / `agent-registry` KV / `forge_subscriber` consumer config with canonical `nats-infrastructure` provisioning. Until landed, jarvis cannot subscribe to stage-complete events at all (DDR-030 between-prompt notification path is dead). | §5.1 (boot warnings), §7 (notification render) | Yes — close criterion narrowed to "forge consumed and acked" until subscriptions reconcile |
| [TASK-FRR-002](../../tasks/completed/feat-jarvis-internal-001-followups/TASK-FRR-002-drop-misleading-jarvis-openai-base-url-field.md) | jarvis | `lifecycle.py:569-570` unconditionally clobbers `OPENAI_BASE_URL` to llama-swap regardless of operator-set `JARVIS_OPENAI_BASE_URL`; the `.env.example` field is misleading. Local-only ethos = llama-swap is mandatory. | §0.4 (provider keys) | Yes — §0.4 documents the local-only mandate and llama-swap-served model list |
| [TASK-FRR-003](../../tasks/completed/feat-jarvis-internal-001-followups/TASK-FRR-003-ddr-019-trace-offload-autocreate-and-non-silent-drop.md) | jarvis | DDR-019 soft-fail trace offload silently drops when `JARVIS_GRAPHITI_ENDPOINT` unset AND `~/.jarvis/traces/` doesn't exist. Should autocreate + log loudly. | §8.3 (offload trace capture) | Yes — §8.3 includes `mkdir -p` precondition and warns on empty offload dir |
| forge-followup-1 | forge | Wire `forge serve`'s `dispatch_payload` to the real `pipeline_consumer` orchestrator + stage-complete publish path. Today's default is a receipt-only stub (`_serve_daemon.py:146-180`) — logs and returns, no autobuild, no publish-back. | §7.1 (close criterion) | Yes — close criterion narrowed to "forge consumed and acked" |
| forge-followup-2 | forge | `forge serve` parses `FORGE_LOG_LEVEL` into `ServeConfig.log_level` but doesn't call `logging.basicConfig()`, so `_default_dispatch`'s `logger.info` calls go nowhere. `docker logs forge-prod` is empty even on successful consume. | §2.2 (forge logs), §7.2 (forge log tail) | Yes — §7.2 uses `nats consumer info -j` to prove consume+ack instead of trusting `docker logs` |
| forge-followup-3 | forge | `scripts/build-image.sh` cd's to forge's parent and runs `--build-context nats-core=../nats-core`, which from the parent resolves to `~/Projects/nats-core` (does not exist on the canonical layout). | §2.1 (image build) | Yes — §2.1 invokes `docker buildx build` directly from inside `forge/` |

**For the operator:** read this section before executing. None of the items above block the GB10 walkthrough (or the MacBook-over-Tailscale follow-up); they only narrow what "Phase 3 closed" can mean today. The close criterion that this runbook actually proves is **"forge consumed and acked"** — the structural roundtrip back into the chat REPL as between-prompt notifications is deferred to TASK-FRR-001 + forge-followup-1 landing.

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

## Cross-repo state preconditions (verified 2026-05-01)

Confirm the assumptions baked into this runbook still hold before executing:

| Repo | Required state | Last verified |
|---|---|---|
| `jarvis` | `main` includes `2864173` (FEAT-JARVIS-INTERNAL-001 close) | 2026-05-01 |
| `nats-infrastructure` | Has `docker-compose.yml` + `streams/provision-streams.sh` + `kv/provision-kv.sh`. Streams: PIPELINE, AGENTS, JARVIS, FLEET, NOTIFICATIONS, SYSTEM, FINPROXY. KV: agent-status, agent-registry, pipeline-state, jarvis-session. | 2026-05-01 |
| `forge` | `main` includes `732408f` (FEAT-FORGE-009 production image + `forge serve`) and `225d279` (feat-complete chore). `pyproject.toml` declares `nats-core>=0.3.0,<0.4` but the active install resolves via `[tool.uv.sources] nats-core = "../nats-core"` (editable). | 2026-05-01 |
| `nats-core` | Sibling of forge. Version `0.2.0`. `BuildQueuedPayload` defined at `src/nats_core/events/_pipeline.py:265`. **Note:** the formal schema does not declare `task_id`/`mode` — `ConfigDict(extra="allow")` permits them as untyped extras. **Not relevant for FEAT-JARVIS-INTERNAL-001 (Mode B).** | 2026-05-01 |
| `specialist-agent` | Architect role NATS-callable (verified TASK-REV-B8E4). PO role recently fixed (TASK-MDF-PORT/POLR Apr 17) but **not required for this run** — FEAT-JARVIS-INTERNAL-001 is documentation-only and dispatches no PO work. | 2026-05-01 |

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

> **Two daemon-config gotchas folded here:**
> 1. **`FORGE_NATS_URL`, not `NATS_URL`.** The `forge serve` daemon reads `FORGE_NATS_URL` exclusively; a bare `NATS_URL` is silently ignored. Must include credentials per Phase 0.4.
> 2. **`FORGE_HEALTHZ_PORT=8088`.** The daemon defaults to port 8080, but `open-webui` holds 8080 host-network on the GB10. Override to 8088 (or any free port) to avoid a bind conflict.
>
> Note that `FORGE_LOG_LEVEL=info` is accepted but currently has **no observable effect** — `forge serve` parses it into `ServeConfig.log_level` but doesn't call `logging.basicConfig()`, so `docker logs forge-prod` will be empty even on successful consume. Tracked as forge-followup-2; until it lands, use Phase 7.2's `nats consumer info -j` to prove consume+ack instead of trusting `docker logs`.

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    set -a && source .env && set +a && \
    docker rm -f forge-prod 2>/dev/null
    docker run -d --name forge-prod \
        --network host \
        -e FORGE_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
        -e FORGE_HEALTHZ_PORT=8088 \
        -e FORGE_LOG_LEVEL=info \
        -v ~/forge-state:/var/forge \
        forge:latest serve
    sleep 3
    docker logs --tail 30 forge-prod
'
```

**Pass (despite the empty `docker logs`):**
- Container status `Up (healthy)` per `docker ps`
- `/healthz` is green (verified in 2.3)
- A `forge-serve` durable consumer is attached on stream `PIPELINE` (verified in 2.3 via `nats consumer info`)

If you do see log output, it should include JetStream connection success, durable-consumer attach, and HTTP listener up — but the absence of those lines is **not** a failure signal until forge-followup-2 lands.

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

> **As of 2026-05-01 the GB10 `graphiti-mcp` reports unhealthy.** That's not a blocker for this runbook — when `JARVIS_GRAPHITI_ENDPOINT` is unset (or the endpoint is unreachable), jarvis takes the DDR-019 trace-offload soft-fail path. Capture the offload trace in §8.3 instead of querying Graphiti, and note the unhealthy state in RESULTS.

### 4.2 Probe the actual Graphiti HTTP endpoint

```bash
ssh promaxgb10-41b1 'curl -sf "${JARVIS_GRAPHITI_ENDPOINT:-http://localhost:8080}/healthz" || echo "graphiti unreachable"'
```

**Pass:** A 200 response (any body). If you get `graphiti unreachable`, leave `JARVIS_GRAPHITI_ENDPOINT` unset and rely on the §8.3 soft-fail offload — the runbook still completes.

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

**Pass:** Banner prints, supervisor builds without error, prompt renders, tool list includes `queue_build` and `dispatch_by_capability`.

> **Expected boot warnings (not failures) until [TASK-FRR-001](../../tasks/backlog/feat-jarvis-internal-001-followups/TASK-FRR-001-reconcile-nats-subscriptions-with-canonical-provisioning.md) lands:** the boot log will show three NATS subscription failures: fleet register (`stream name already in use with a different configuration`), agent-registry KV bind (same), and `forge_subscriber` attach (`BadRequestError code=10101 description='consumer must be deliver all on workqueue stream'`). These are real DDR drift — the JARVIS stream / agent-registry KV / PIPELINE consumer config that jarvis tries to set up does not match what `nats-infrastructure` provisions. **Until TASK-FRR-001 lands, jarvis cannot subscribe to stage-complete events at all, and the DDR-030 between-prompt notification path is dead.** This runbook accommodates that by narrowing the Phase 7 close criterion to "forge consumed and acked"; do not treat the boot warnings as a stop signal.

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

**Pass — the supervisor returns a JSON-shaped acknowledgement containing:**
- `status: queued`
- `feature_id: FEAT-43DE`
- `correlation_id: <uuid>` ← **save this verbatim** — it threads through every subsequent stage event and the Graphiti trace dump
- `publish_target: pipeline.build-queued.FEAT-43DE`
- `queued_at: <ISO 8601>`

**If `status: validation_error`:** the most likely cause is the feature_id failing the `^FEAT-[A-Z0-9]{3,12}$` regex (hyphens or > 12 chars in the tail). Substitute the internal id and retry.

**If `status: degraded`:** NATS publish failed. Most likely Phase 1 isn't actually green — re-run 1.2 (with auth sourced!) and verify the PIPELINE stream is bound to `pipeline.build-queued.>`.

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

## Phase 7: Verify forge consumed and acked (narrowed close criterion)

> **Close criterion narrowed from "stage-complete events render in chat as notifications" to "forge consumed and acked".**
>
> The original Phase 7 expected `pipeline.stage-complete` messages to flow back from forge into the chat REPL's between-prompt notification drain. As of `forge:732408f` + jarvis `2864173`, that round-trip is **structurally unsatisfiable** for two independent reasons:
> 1. **forge-followup-1:** `forge serve`'s default `dispatch_payload` (`_serve_daemon.py:146-180`) is a receipt-only stub — it logs and returns, no autobuild, no stage-complete publish-back.
> 2. **TASK-FRR-001:** jarvis's `forge_subscriber` fails to attach during boot (`consumer must be deliver all on workqueue stream`), so even if forge published stage-complete events, jarvis would not receive them.
>
> When **both** of those land, this phase can revert to its original "between-prompt notifications render" framing. Until then, this phase verifies the achievable property: forge dequeued and acked the message that §6.2 published.

### 7.1 Confirm forge consumed and acked

You already captured this in §6.3 via `nats consumer info PIPELINE forge-serve -j`. Cross-reference:

```bash
jq '{delivered: .delivered.consumer_seq, pending: .num_pending, redelivered: .num_redelivered}' \
    /tmp/jarvis-forge-serve-consumer.json
```

**Pass:** `delivered >= 1`, `pending == 0`, `redelivered == 0`. This proves the wire-level path: jarvis published → JetStream retained → forge dequeued + acked.

### 7.2 (Deferred) Tail the forge container logs for the correlation_id

> **Deferred until forge-followup-2 lands** (`logging.basicConfig` in `serve.py`). Today, `docker logs forge-prod` is empty even on successful consume because the daemon never attaches a logging handler. The `nats consumer info` evidence in 7.1 is the source of truth for "consume + ack".

When forge-followup-2 lands, this block becomes:

```bash
ssh promaxgb10-41b1 'docker logs forge-prod 2>&1 | grep -i "<correlation_id_from_6.2>"' \
    | tee /tmp/forge-events-phase7.log
```

**Pass (post-fix):** at least one log line per stage referencing the correlation_id. Today: skip and note in RESULTS.

### 7.3 (Future) Stage-complete notifications render in chat

> **Deferred until both forge-followup-1 (real `dispatch_payload`) AND TASK-FRR-001 (forge_subscriber attach reconciliation) land.** When they do, the operator can issue a follow-up REPL turn and observe rendered notification lines:
>
> ```text
> [HH:MM] Forge FEAT-43DE: stage <stage_label> (<status>)
> ```
>
> Until then, no notification lines should be expected to drain — and their absence is **not** a failure signal for this runbook.

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
| 6.2 | queue_build returns success (FEAT-43DE) | ✅ | REPL transcript |
| 6.3 | publish landed + forge consumer state shows delivered+acked | ✅ | `/tmp/jarvis-pipeline-state.json` + `/tmp/jarvis-forge-serve-consumer.json` |
| 7.1 | forge consumed + acked (narrowed close criterion) | ✅ | `/tmp/jarvis-forge-serve-consumer.json` |
| 7.2 | forge logs show consume + publish-back | ⚠️ deferred (forge-followup-2) | n/a until logging.basicConfig lands |
| 7.3 | between-prompt notifications render | ⚠️ deferred (forge-followup-1 + TASK-FRR-001) | n/a until both land |
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
