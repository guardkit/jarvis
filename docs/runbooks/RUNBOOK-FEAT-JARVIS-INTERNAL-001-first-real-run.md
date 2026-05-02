# Runbook: FEAT-JARVIS-INTERNAL-001 First Real Run — Jarvis Phase 3 Close

**Status:** Ready for execution. FEAT-JARVIS-INTERNAL-001 merged to `main` (`81bb792` → `47ec4e5` → `2864173`). All cross-repo prerequisites verified shipped (cross-repo state audit 2026-05-01). What remains is operator runtime: bring up NATS + Forge + specialist-agent on GB10, then publish one `BuildQueuedPayload` from `jarvis chat` and observe stage-complete events flow back as between-prompt notifications.

**Purpose:** Drive the first real `jarvis chat → queue_build → JetStream → forge serve → autobuild → stage-complete events → jarvis CLI render` round-trip end-to-end on GB10. This is the **Phase 3 close criterion** per `docs/research/ideas/phase3-build-plan.md` Step 14.

**Machines:**
- **GB10** (`promaxgb10-41b1`) — primary host. Runs NATS (JetStream + KV), FalkorDB/Graphiti, `forge serve` daemon, specialist-agent fleet (architect minimum), and (recommended for first walkthrough) `jarvis chat` itself.
- **Local MacBook** — secondary walkthrough host. Repeat the e2e against GB10 NATS over Tailscale once the GB10-resident pass is green.

> **GB10 first, MacBook second:** Co-resident services on the first walkthrough remove network variables when the wire goes red. The MacBook-over-Tailscale walkthrough is the *second* pass and matches the shape of forge's Phase 6.4 "clean MacBook + GB10" gate. Don't try to do both in one session.

**Predecessors (all verified shipped before walkthrough — see `Cross-repo state preconditions` below):**
- ✅ FEAT-JARVIS-INTERNAL-001 merged to `jarvis` `main`
- ✅ FCH-001 canonical NATS provisioning artefacts shipped in `nats-infrastructure` (compose, provision-streams.sh, provision-kv.sh)
- ✅ FEAT-FORGE-009 production image + `forge serve` daemon merged to `forge` `main` (`732408f`, 2026-05-01)
- ⚠️ **FEAT-FORGE-XXX (orchestrator wiring) — REQUIRED for Phase 7 close** — currently being scoped through `/feature-spec` + `/feature-plan` against `forge/docs/research/forge-orchestrator-wiring-gap.md`. F009 alone ships only the daemon process container; the orchestrator chain (Supervisor + dispatchers + autobuild_runner subagent + PipelineLifecycleEmitter) that actually runs autobuilds and publishes lifecycle events is wired by this new feature. **Do not run this runbook expecting Phase 7 to pass until FEAT-FORGE-XXX has merged.** See "Phase 7 expectations" below for the per-stage envelope sequence the new feature delivers.
- ✅ specialist-agent architect role NATS-callable (live verification per TASK-REV-B8E4)
- ✅ nats-core 0.2.0 with `BuildQueuedPayload` schema (`pipeline.build-queued.{feature_id}`)

**Expected wall-clock:** ~60–90 minutes for a clean GB10 walkthrough. ~30 minutes for the follow-up MacBook-over-Tailscale walkthrough once GB10 is green.

**Outputs:**
- `docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md` capturing per-phase outcomes, evidence pointers, and any runbook gap-folds
- A chat transcript saved at `~/.jarvis/transcripts/<correlation_id>.txt` (or equivalent — capture verbatim from terminal scrollback if no auto-save)
- A Graphiti trace dump for the routing-history entry + stage-complete edges (proves DDR-029 append-only edges are landing as designed)
- A `command-history.md` entry per LES1 §8 — every shell block in this runbook executed verbatim with timestamps
- A row appended to `docs/research/ideas/phase3-build-plan.md` Status Log declaring **Phase 3 closed**

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
| `forge` | `main` includes `732408f` (FEAT-FORGE-009 production image + `forge serve`) and `225d279` (feat-complete chore). `pyproject.toml` declares `nats-core>=0.3.0,<0.4` but the active install resolves via `[tool.uv.sources] nats-core = "../nats-core"` (editable). **For Phase 7 to close, also requires the orchestrator-wiring feature merge** — see "FEAT-FORGE-XXX" predecessor row above. F009 alone ships only the daemon process; the orchestrator chain it hosts (Supervisor + dispatchers + autobuild_runner subagent + PipelineLifecycleEmitter) is wired by the new feature. As of 2026-05-02 the new feature is being scoped through `/feature-spec`; until it merges, expect Phase 7 to fail in the way RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md captures (consumer info shows `delivered=N, acked=N`, but `pipeline.stage-complete.*` is empty and the chat REPL drains zero notifications). | 2026-05-01 (F009 portion); pending (orchestrator-wiring portion) |
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

### 0.4 Confirm provider keys are present in the operator's environment

```bash
ssh promaxgb10-41b1 'env | grep -E "ANTHROPIC|OPENAI|GOOGLE|GEMINI|JARVIS_NATS|JARVIS_GRAPHITI" | sed "s/=.*/=<set>/"'
```

**Pass:** At least the following are set (values masked is fine):
- `ANTHROPIC_API_KEY` (or `JARVIS_ANTHROPIC_API_KEY`)
- `OPENAI_API_KEY` (or `JARVIS_OPENAI_API_KEY`) — also used by jarvis-reasoner via llama-swap
- `GOOGLE_API_KEY` (or `JARVIS_GEMINI_API_KEY`)
- `JARVIS_NATS_URL` — must point at GB10's NATS (e.g. `nats://localhost:4222` if running on GB10, `nats://promaxgb10-41b1:4222` from MacBook)
- `JARVIS_GRAPHITI_ENDPOINT` — Graphiti HTTP endpoint (e.g. `http://localhost:8080` on GB10)

> **Llama-swap note:** `JARVIS_OPENAI_BASE_URL` should point at the llama-swap reasoner endpoint (`http://localhost:9000/v1` on GB10 per the recent migration commits in jarvis/nats-core). The `OPENAI_API_KEY` value is used as a bearer token; llama-swap accepts any non-empty string.

**If a key is missing:** stop. Source the env file or export the missing key. The supervisor will fail at first dispatch otherwise.

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

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    bash scripts/verify-nats.sh'
```

**Pass:** `verify-nats.sh` reports all 7 streams present (PIPELINE, AGENTS, JARVIS, FLEET, NOTIFICATIONS, SYSTEM, FINPROXY) and all 4 KV buckets present (agent-status, agent-registry, pipeline-state, jarvis-session).

**If a stream or bucket is missing** (typically because the JetStream volume is fresh — see LES1 §7 / TASK-NI-PSBUG):
```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/nats-infrastructure && \
    bash streams/provision-streams.sh && \
    bash kv/provision-kv.sh && \
    bash scripts/verify-nats.sh'
```

The provisioning scripts are idempotent. Re-run `verify-nats.sh` afterward to confirm green.

> **Critical (LES1 §7 / TASK-MDF-PRVS):** A fresh-volume NATS without provisioning will accept publishes (PubAck) but **not retain or deliver them** — exactly the failure mode that masked the MacBook reds. If `verify-nats.sh` is green you're past this trap.

### 1.3 Confirm `pipeline.build-queued.*` is bound to the PIPELINE stream

```bash
ssh promaxgb10-41b1 'docker exec -i $(docker ps -qf name=nats) \
    nats --server nats://localhost:4222 stream info PIPELINE -j' | \
    jq -r '.config.subjects[]'
```

**Pass:** Output includes `pipeline.build-queued.>` (or `pipeline.>`).

---

## Phase 2: Forge `serve` daemon running and subscribed

### 2.1 Build (or pull) the forge production image on GB10

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/forge && \
    git pull --ff-only && \
    bash scripts/build-image.sh'
```

**Pass:** Build completes. `docker images forge` shows a fresh tag.

### 2.2 Start `forge serve` against canonical NATS

```bash
ssh promaxgb10-41b1 '
    docker rm -f forge-prod 2>/dev/null
    docker run -d --name forge-prod \
        --network host \
        -e NATS_URL=nats://localhost:4222 \
        -e FORGE_LOG_LEVEL=info \
        -v ~/forge-state:/var/forge \
        forge:latest serve
    sleep 3
    docker logs --tail 30 forge-prod
'
```

**Pass:** Logs show:
- JetStream connection succeeded
- Durable consumer created/attached on stream `PIPELINE` for filter `pipeline.build-queued.*`
- HTTP `/healthz` listener up

### 2.3 Confirm `/healthz` reports JetStream subscription healthy

```bash
ssh promaxgb10-41b1 'curl -s http://localhost:8088/healthz | jq .'
```

> Adjust the port to whatever `forge serve` actually binds — check the container logs for the literal port.

**Pass:** JSON response shows `subscription.connected: true` (or equivalent) and the durable consumer name matches what was created in 2.2.

**If `/healthz` returns "subscription disconnected":** this is exactly the LES1 CMDW failure mode (production image silently fails to subscribe). Stop. Do not proceed to Phase 6 — investigate the container's NATS reachability and credentials before publishing anything real.

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

### 4.1 Graphiti / FalkorDB up

```bash
ssh promaxgb10-41b1 'docker ps --format "{{.Names}}\t{{.Status}}" | grep -E "graphiti|falkor"'
```

**Pass:** Both containers running (`graphiti` + `falkordb` typically; names may vary).

### 4.2 Graphiti embeddings endpoint reachable

```bash
ssh promaxgb10-41b1 'curl -sf -X POST http://localhost:9000/v1/embeddings \
    -H "Content-Type: application/json" \
    -d "{\"input\": \"runbook smoke\", \"model\": \"text-embedding-3-small\"}" \
    | jq .data[0].index'
```

> Adjust port if your llama-swap is on a different one. The recent jarvis commits show migration to `:9000` for the central HTTP MCP endpoint.

**Pass:** Returns `0` (the index of the first/only embedding).

**If unreachable:** `JARVIS_GRAPHITI_ENDPOINT` will be unable to write routing-history entries. Per DDR-019, jarvis falls back to `JARVIS_TRACES_DIR` (default `~/.jarvis/traces`) — the runbook will still complete, but **note this in RESULTS** and capture the offload directory contents in Phase 8 instead of querying Graphiti.

---

## Phase 5: Jarvis chat REPL smoke (no NATS publish yet)

### 5.1 Boot `jarvis chat`

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/jarvis && \
    git pull --ff-only && \
    .venv/bin/jarvis chat --log-level INFO 2>&1 | tee /tmp/jarvis-chat-phase5.log'
```

**Pass:** Banner prints, supervisor builds without error, prompt renders, tool list includes `queue_build` and `dispatch_by_capability`.

**If supervisor fails to build:** the most common cause is missing provider keys (Phase 0.4) or wrong `JARVIS_OPENAI_BASE_URL` (must point at llama-swap, not the public OpenAI endpoint). Hit Ctrl+C (exit code 130 expected) and resolve.

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

```bash
ssh promaxgb10-41b1 'cd ~/Projects/appmilla_github/jarvis && \
    JARVIS_LOG_LEVEL=DEBUG \
    .venv/bin/jarvis chat 2>&1 | tee /tmp/jarvis-chat-phase6.log'
```

### 6.2 Issue the queue request

In the REPL, type:

```text
> Queue FEAT-JARVIS-INTERNAL-001 for build. The feature YAML is at .guardkit/features/FEAT-JARVIS-INTERNAL-001.yaml on the main branch of guardkit/jarvis.
```

> Adjust the YAML path / repo / branch arguments to match what `queue_build`'s docstring requires; the supervisor should fill these from your prompt. If it asks clarifying questions, answer them — and **note the questions in RESULTS** as a gap-fold candidate (the runbook's prompt above should have been complete enough).

**Pass — the supervisor returns a JSON-shaped acknowledgement containing:**
- `status: queued`
- `feature_id: FEAT-JARVIS-INTERNAL-001`
- `correlation_id: <uuid>` ← **save this verbatim** — it threads through every subsequent stage event and the Graphiti trace dump
- `publish_target: pipeline.build-queued.FEAT-JARVIS-INTERNAL-001`
- `queued_at: <ISO 8601>`

**If `status: validation_error`:** the YAML path or repo arg is wrong. Re-check.

**If `status: degraded`:** NATS publish failed. Most likely Phase 1 isn't actually green — re-run 1.2 and verify the PIPELINE stream is bound to `pipeline.build-queued.>`.

### 6.3 Capture proof of publication on the wire

In a second SSH session to GB10:

```bash
ssh promaxgb10-41b1 'docker exec -i $(docker ps -qf name=nats) \
    nats --server nats://localhost:4222 \
    stream view PIPELINE --subject="pipeline.build-queued.FEAT-JARVIS-INTERNAL-001" \
    --headers' | tee /tmp/jarvis-nats-published.log
```

**Pass:** One message visible with the `correlation_id` you saved in 6.2 in either body or headers. Capture this output as evidence.

---

## Phase 7: Real per-stage lifecycle events arrive in chat as between-prompt notifications

> **What this phase tests changed on 2026-05-02.** The 2026-05-01 walkthrough (results captured in `RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`) failed Phase 7 because nothing on the forge side publishes any lifecycle envelope back today — F009 ships a receipt-only stub at `_serve_daemon._default_dispatch`. The follow-up forge-side task FRR-001 was filed assuming "wire dispatch_payload" was a one-day fix; Phase 2.8 design investigation discovered the entire orchestration chain is unwired in production and re-scoped the work to a feature (`forge/docs/research/forge-orchestrator-wiring-gap.md`). Phase 7 now tests for the **real per-stage envelope sequence** that feature delivers, not the receipt-only behaviour F009 actually shipped or the synthetic single-envelope FRR-001 was originally going to ship. **If FEAT-FORGE-XXX (orchestrator wiring) has not merged, expect Phase 7 to fail in the same shape as the 2026-05-01 run** — capture verbatim and stop.

The REPL from 6.1 should still be open. Forge is now autobuilding (or short-circuiting cleanly via the supervisor's "no work to do" terminal path — see operator decision note in 6.1). Either way, the **full lifecycle envelope sequence** should flow back from `pipeline_consumer.handle_message` → `Supervisor.process_build` → `autobuild_runner` AsyncSubAgent → `PipelineLifecycleEmitter`, and the chat REPL drains `pending_notifications(session_id)` before each new input prompt.

### 7.1 Trigger a notification drain

In the REPL, type a small follow-up — anything that produces a new prompt cycle:

```text
> What's happening with that build?
```

**Pass criteria — the rendered notification sequence must include all three of:**

1. **At least one `build-started` line**, fired when the autobuild dispatch begins (one per build):

   ```text
   [HH:MM] Forge FEAT-JARVIS-INTERNAL-001: build-started (RUNNING)
   ```

2. **One or more `stage-complete` lines**, one per real stage transition the autobuild orchestrator records in `stage_log`. The exact stage-label sequence depends on the build mode (Mode A / B / C) and what the autobuild actually does on this feature, but the format is:

   ```text
   [HH:MM] Forge FEAT-JARVIS-INTERNAL-001: stage <stage_label> (<status>)
   ```

   Where `<stage_label>` is a `forge.pipeline.stage_taxonomy.StageClass` value (e.g. `PLAN`, `AUTOBUILD`, `PR_REVIEW`) and `<status>` is one of `PASSED`, `FAILED`, `GATED`, `SKIPPED` per the `StageCompletePayload` schema.

3. **One terminal line** — either `build-complete` (status `PASSED`) or `build-failed` (with `failure_reason`) — fired when the autobuild reaches a terminal lifecycle state. Format:

   ```text
   [HH:MM] Forge FEAT-JARVIS-INTERNAL-001: build-complete (PASSED)
   ```

   or

   ```text
   [HH:MM] Forge FEAT-JARVIS-INTERNAL-001: build-failed (<failure_reason>)
   ```

**Capture every line verbatim, in order.** This is the sequence the new orchestrator-wiring feature commits the chat REPL to threading by `correlation_id` — anything other than this shape (e.g. only one envelope, or out-of-order envelopes, or the `build-started` envelope missing) is a regression worth folding to a follow-up.

**Hard rejects (do NOT mark Phase 7 as passing if any of these is true):**
- Only one `stage-complete` envelope arrives, with `stage_label="dispatch"` — that was the **synthetic placeholder** the abandoned FRR-001 design was going to ship. The real feature must publish per-stage transitions from inside the autobuild_runner subagent, not a single envelope from the daemon dispatcher. If you see only the dispatch-stage envelope, check that the merge actually included the orchestrator-wiring feature (not just a partial FRR-001 reset).
- The `correlation_id` on any of the rendered envelopes does not equal the `correlation_id` jarvis published in 6.2 — breaks DDR-029's notification-thread contract.
- Notifications arrive but are not drained before the supervisor's response — breaks the between-prompt rendering contract jarvis-side (see DDR-030).

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
ssh promaxgb10-41b1 'docker logs -f forge-prod 2>&1 | grep -i "<correlation_id_from_6.2>"' | \
    tee /tmp/forge-events-phase7.log
```

**Pass:** Forge logs show the correlation_id consuming from JetStream, the autobuild_runner subagent launch, each per-stage emit_stage_complete call, and the terminal build-complete/build-failed publish. Capture log tail.

**If the lifecycle envelope sequence is missing or incomplete after ~5 minutes**, the failure mode tells you where the gap is:

| Symptom on the wire | Likely cause | Action |
|---|---|---|
| **No envelopes at all**; consumer info shows `delivered=1, acked=1` (the F009-only baseline from 2026-05-01) | The orchestrator-wiring feature has not merged. The daemon is still on the receipt-only `_default_dispatch` stub. | Confirm `git log` on the forge image's source includes the FEAT-FORGE-XXX commits. If not, the runbook's preconditions row was not satisfied; stop and re-build the image. |
| **Only one `stage-complete` envelope** with `stage_label="dispatch"`, no `build-started`, no terminal | A stub of the abandoned FRR-001 design was deployed instead of the real feature. | Check the deployed image — should NOT contain the synthetic dispatch-stage publish. If it does, that's a misroll; redeploy with the real feature image. |
| **`build-started` arrives but no per-stage `stage-complete`**; long delay then `build-failed` | The autobuild_runner subagent dispatched but failed internally. | Capture the forge container logs (Phase 7.3) for the autobuild traceback. Fold to a follow-up against the autobuild_runner. |
| **Per-stage `stage-complete` arrives but no terminal** | The autobuild reached its terminal state but `emit_build_complete`/`emit_build_failed` did not fire. The deferred-ack contract means JetStream will redeliver the inbound `build-queued` message after `ack_wait` (1 hour). | Capture forge logs; the orchestrator's terminal-transition path is broken. Fold to a follow-up. |
| **All envelopes arrive but `correlation_id` doesn't match what jarvis published** | The publisher is not threading `correlation_id` through the lifecycle emitter. | Capture both the inbound and outbound envelopes; reproduce the LES1 CMDW pattern. Stop and fix before re-running. |

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

```bash
ssh promaxgb10-41b1 'ls -la ~/.jarvis/traces/ && \
    cat ~/.jarvis/traces/<correlation_id_from_6.2>.json'
```

**Pass:** A JSON file with the routing-history entry persisted locally per DDR-019.

### 8.4 `command-history.md` entry per LES1 §8

In `jarvis/docs/history/command-history.md`, append a section with:
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

Once GB10 is green, repeat **Phases 5–8 only** from the MacBook with these env-var differences:
- `JARVIS_NATS_URL=nats://promaxgb10-41b1:4222` (Tailscale-routed)
- `JARVIS_GRAPHITI_ENDPOINT=http://promaxgb10-41b1:8080`

Append a second results section to the same RESULTS file. This matches forge's Phase 6.4 "clean MacBook + GB10" canonical-freeze pattern.

---

## See also

- **Phase 3 build plan** — `jarvis/docs/research/ideas/phase3-build-plan.md` Step 14 (close criterion)
- **Forge first-real-run pattern** — `forge/docs/runbooks/RUNBOOK-FEAT-FORGE-008-finproxy-first-run.md` (this runbook mirrors its structure)
- **Forge symlink fix** — `forge/docs/runbooks/RUNBOOK-FEAT-FORGE-009-nats-core-symlink-fix.md` (one-time per-machine setup)
- **NATS canonical provisioning** — `nats-infrastructure/streams/provision-streams.sh` + `kv/provision-kv.sh` + `scripts/verify-nats.sh`
- **Routing-history schema** — `jarvis/src/jarvis/infrastructure/routing_history.py` (DDR-029 trace shape)
- **Forge notification rendering** — `jarvis/src/jarvis/infrastructure/forge_notifications.py:153–170` (`ForgeNotification.render_line`)
- **queue_build tool** — `jarvis/src/jarvis/tools/dispatch.py:956–1060` (signature + return shape)
