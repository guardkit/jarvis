# Runbook: Jarvis → Forge Autobuild — `/version` endpoint demo (FEAT-9E59)

**Status:** Preflight green (2026-05-14, guardkit standalone, ~18 min). Wire-mediated rehearsal pending. Demo date: **2026-05-16** (DDD South West). Dress rehearsal slot: **2026-05-15**. Update Status to **Verified** after the first green wire-mediated walkthrough. See §0.8 (Known caveats) for the live-bridge fast-fail bug that does NOT block the happy path but constrains fallback behaviour.

**Purpose:** Drive a **real** Forge autobuild end-to-end from a Jarvis chat session — not a no-op replay. The 2026-05-13 multi-specialist demo (see [RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md](RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md)) proved the wire end-to-end against `FEAT-EC3C` but EC3C was already-completed state, so Forge round-tripped in <1s with no actual build work. This runbook completes the loop by autobuilding a **fresh** feature — a single `GET /version` endpoint in `appmilla/api_test` on the disposable `ddd-demo` branch — so the audience sees the autobuilder actually produce code, run tests, and stage-complete back into the chat.

```
human prompt in jarvis (OpenWebUI or CLI chat)
  → supervisor recognises queue_build pattern
  → queue_build(FEAT-9E59, .guardkit/features/FEAT-9E59.yaml, appmilla/api_test, ddd-demo)
  → JetStream pipeline.build-queued.FEAT-9E59 (workqueue)
  → forge-prod durable consumer (forge-serve) dequeues
  → autobuild_runner subagent on langgraph-runner sidecar
  → Player-Coach loop writes src/version/router.py + test + main.py wiring
  → guardkit-checkpoint commits land on autobuild/FEAT-9E59 worktree branch
  → lifecycle bridge emits pipeline.build-started + stage-complete + build-complete
  → jarvis chat handler drains notifications into next REPL turn
```

Zero cloud LLM on the path. The build itself runs on the same Blackwell box as the supervisor; the marginal cost is GPU-time on hardware you already paid for.

**Companion / source-of-truth references:**
- [`RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md`](RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md) — the parent runbook this one specialises; Turn 3 is the forge dispatch path proven on 2026-05-13.
- [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`](RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md) — last known-green forge wire (FOLLOWUP-A and FOLLOWUP-B both resolved).
- [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — canonical forensic doc for the forge dispatch wire (deeper failure-mode table; consult if anything goes red).
- [`autobuild-orchestration.md`](autobuild-orchestration.md) — operational lessons for re-running an autobuild against the same feature (the `--fresh` vs worktree-edit footgun).
- `api_test/.guardkit/features/FEAT-9E59.yaml` (created via `/feature-plan` 2026-05-14) — single task TASK-VER-001, planned 33 min wall-clock; **2026-05-14 preflight measured 18 min** end-to-end (single Player turn, Coach approved, 151 tests pass on the worktree).

**Machine layout (single-host GB10, `promaxgb10-41b1`):** identical to the multi-specialist runbook. NATS JetStream + llama-swap (host) + specialist-agent + study-tutor + forge-prod + OpenWebUI + jarvis serve-nats. Nothing new spun up for this demo.

**Stage timing (important — read this before picking a slot):**

The autobuild is **estimated at 33 minutes** of wall-clock. A stage demo cannot wait for `build-complete`. Three viable framings:

1. **"Watch the queue + first stage-complete arrive"** *(recommended for stage)*. ~3 min: queue_build acks immediately, supervisor reasoning ~5-10s, then take one more chat turn (e.g. a quick architect_align) while forge runs in the background; `build-started` drains into the next reply via `ForgeNotification.render_line()` (per the FEAT-EC3C inline-drain proof on 5/13). Build completes off-stage; the post-talk write-up shows the full transcript.
2. **"Pre-warm the autobuild before stage, drain on stage"**. Run `queue_build` from a rehearsal session ~25 min before the talk; the actual chat turn on stage drains the `build-complete` envelope that arrived during the pre-warm window. Tight to coordinate, but lands the "look, forge built it" reveal in a single stage minute.
3. **"Just show the queue, narrate the rest"**. ~1 min on stage: paste the prompt, point at the wire envelope on a second screen, narrate "this will take ~30 min, the rendered diff will be on the blog post tomorrow." Lowest stage cost; weakest payoff.

Pick framing in §0.9 before stepping on stage. **Recommended: framing 1.**

**Expected wall-clock for a clean rehearsal (full path, off-stage):** ~45-60 min including the 33-min build window.

**Outputs:**
- `docs/runbooks/RESULTS-jarvis-forge-autobuild-version-endpoint-demo-<YYYY-MM-DD>.md` per-phase outcomes
- `docs/runbooks/evidence/version-endpoint-demo/<correlation_id>-pipeline.json` — captured `pipeline.*` envelopes (build-queued, build-started, stage-complete×N, build-complete)
- `docs/runbooks/evidence/version-endpoint-demo/<correlation_id>-queue-payload.json` — the `queue_build` tool result
- `~/.jarvis/transcripts/<correlation_id>.txt` — chat transcript
- `appmilla/api_test` worktree on branch `autobuild/FEAT-9E59` with the Player-Coach commits — the **actual code produced** by Forge, capturable as a slide diff

---

## What this runbook does NOT cover

- **Long-running build orchestration** (architect-align → human review → patch → re-run). Out of scope; the demo is a one-shot autobuild end-to-end.
- **Failure recovery (`--fresh` reseed, worktree surgery).** Carried by [`autobuild-orchestration.md`](autobuild-orchestration.md). If the build fails mid-flight, do not try to repair on stage — fall back to framing 3.
- **Architect / tutor specialist dispatches.** They're the parent runbook's job; this one focuses on the forge path alone (though framing 1 piggy-backs on a quick architect_align during the wait window).

---

## Demo narrative (talk track)

The runbook below is the operator script. The talk track is what the operator says aloud while it runs. Roughly (framing 1):

1. **Frame** (~30s): "I'm going to type one sentence into chat. Jarvis will recognise it as a build request, queue it on the NATS pipeline, Forge will pick it up, and start running an actual autonomous build of a new endpoint into a FastAPI repo. We'll see the build-started envelope flow back into this chat session in a moment."
2. **Show topology slide** (~30s): chat box → JetStream PIPELINE stream → forge-prod container → langgraph-runner sidecar → Player-Coach loop → JetStream lifecycle envelopes back. "All on this Blackwell box. No cloud."
3. **Type the prompt** (~10s): one line (§4.1).
4. **`queue_build` acks** (~5s): point at the response — "Queued. Correlation id `<uuid>`. The build is now running in the background. The chat is not blocked."
5. **While we wait** (~60-90s): take a side turn (a small architect_align question, or just ask "what tools do you have available?") to fill time and let the next REPL turn drain whatever's arrived.
6. **`build-started` drains into the reply** (~5s): point at the rendered notification line — "Forge has begun. The build will take ~30 minutes; we won't see build-complete on stage, but the transcript will be in the post-talk write-up."
7. **Land the point** (~30s): "From one chat sentence to a real autonomous build that's writing code into a repo and committing checkpoint commits on a feature branch. This is the agent shape — the wire is doing the boring part so the human can stay in the conversation."

Total: ~3-4 minutes on stage. Buffer for first-token latency.

---

## Phase 0: Go/no-go pre-flight

Phases 0-3 piggy-back on the multi-specialist runbook. If you've just run that runbook clean, you can skip ahead to §4.

### 0.1 Confirm jarvis main + clean tree

```bash
cd ~/Projects/appmilla_github/jarvis
git fetch origin && git status -s -uno && git log --oneline -5
```

**Pass:** Top of log includes `076b9353` (TASK-J006-010, the envelope-unwrap + bounded-startup-reconnect fixes) or a descendant on `main`. Working tree clean.

### 0.2 Confirm api_test on the demo branch

```bash
cd ~/Projects/appmilla_github/api_test
git fetch origin
git status -s -uno
git branch --show-current
git log --oneline -5
ls -la .guardkit/features/FEAT-9E59.yaml
```

**Pass:** Branch is `ddd-demo` (not `main`). Working tree clean. `FEAT-9E59.yaml` exists at the path shown.

> **Why a branch, not main:** the autobuild commits onto `autobuild/FEAT-9E59` (a separate worktree branch under `.guardkit/worktrees/FEAT-9E59`). Targeting `ddd-demo` as the *source* branch means the autobuild's merge target is also `ddd-demo`, isolating the demo from `main`. Per [`autobuild-orchestration.md`](autobuild-orchestration.md): main-repo edits to FEAT-9E59 between runs are footguns — edit the worktree, or `--fresh`.

### 0.3 Confirm NATS broker + auth env sourced

```bash
docker ps --filter name=ships-computer-nats --format '{{.Names}}\t{{.Status}}'
set -a && source ~/Projects/appmilla_github/nats-infrastructure/.env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
nats --server "$NATS_URL" stream ls 2>&1 | head -5
```

**Pass:** `ships-computer-nats` Up (healthy). `nats stream ls` returns ≥7 streams. If `Authorization Violation`, redo the `source` line in this shell.

### 0.4 Confirm llama-swap is serving the supervisor model

```bash
ss -tlnp 2>/dev/null | grep :9000
curl -sf http://localhost:9000/v1/models | jq -r '.data[].id' | sort | grep -E 'qwen36-workhorse|gemma4-tutor|architect-agent'
```

**Pass:** `qwen36-workhorse` (or `gemma4-tutor` if that's the configured supervisor) is in the list. The autobuild's Player-Coach loop calls back into llama-swap for code generation; the rest of the model list matters only if you take framing 1's side-turn.

### 0.5 Confirm forge-prod is up + healthy

```bash
docker ps --filter name=forge-prod --format 'table {{.Names}}\t{{.Status}}'
curl -s http://localhost:8088/healthz | jq .
```

**Pass:** `forge-prod` Up; `/healthz` returns `{"status":"healthy"}`. The PIPELINE consumer is named `forge-serve` (post-5/13 — earlier runbooks called it `forge_subscriber`; confirmed renamed):

```bash
nats --server "$NATS_URL" consumer info PIPELINE forge-serve -j \
  | jq '{durable: .config.durable_name, pending: .num_pending, delivered: .delivered.consumer_seq, ack_floor: .ack_floor.consumer_seq}'
```

**Pass:** `durable: "forge-serve"`, `pending: 0`, `delivered == ack_floor` (steady state). Note the `delivered` baseline — you'll cross-reference §5.1 against it.

> **If `forge-prod` is Exited:** consult the multi-specialist runbook §1.4 for the canonical bring-up. The most common cause is a NATS broker bounce; `docker start forge-prod` usually recovers it. If it crash-loops, the FOLLOWUP-A `lifecycle_bridge_registry` migration may have been lost on a container restart — see [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-followup-b-landed.md`](RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-followup-b-landed.md) for the symptom signature.

### 0.6 Confirm langgraph-runner sidecar is reachable

The autobuild_runner subagent runs on the sidecar, not inside forge-prod itself.
Since 2026-05-15 the sidecar is a **user systemd service** —
`forge-langgraph-sidecar.service` (unit:
`~/.config/systemd/user/forge-langgraph-sidecar.service`). It is `enabled`, so
it auto-starts at boot alongside `llama-swap` and `jarvis-serve-nats`, and
`Restart=on-failure` self-heals a crash.

```bash
systemctl --user is-active forge-langgraph-sidecar
curl -sf http://localhost:8124/openapi.json | jq -r '.info.title // empty'
```

**Pass:** `is-active` returns `active`; `curl` returns a non-empty title. If
inactive: `systemctl --user restart forge-langgraph-sidecar`, then
`journalctl --user -u forge-langgraph-sidecar -n 30` for the cause.

**Env-var contract (baked into the unit):** the sidecar's `autobuild_runner`
reads two env vars its parent forge-prod does not yet plumb — both are set as
`Environment=` lines in the service unit, so there is no shell-export step:

- `FORGE_DEFAULT_REPO=appmilla/api_test` — the temporary fallback added in
  forge.git commit `7006c7d`; the resolver uses it when `payload.repo` is
  missing, which it currently always is because `dispatch_autobuild_async`
  doesn't yet forward `repo`/`branch`/`feature_yaml_path` from
  `BuildQueuedPayload`. Tracked as TASK-ABW-002 (proper plumbing). Without it,
  every wire-mediated dispatch fast-fails on `missing repo in launch payload`.
- `FORGE_CONFIG_PATH=~/forge-state/forge.yaml` — makes the resolver's
  allowlist check read the same config as forge-prod (rather than falling back
  to base-dir-only).

**After any `autobuild_runner.py` code change** — `langgraph dev` runs with
`--no-reload`, so restart the service to pick it up:

```bash
systemctl --user restart forge-langgraph-sidecar
sleep 10
systemctl --user is-active forge-langgraph-sidecar
curl -sf http://localhost:8124/openapi.json | jq -r '.info.title'
journalctl --user -u forge-langgraph-sidecar --since "1 min ago" \
    | grep "Application started up" | head -1
```

### 0.7 Confirm forge filesystem allowlist covers api_test

Forge's `forge.yaml` allowlist must include a path that contains the api_test worktree root.

```bash
docker exec forge-prod cat /var/forge/forge.yaml 2>/dev/null \
  | python3 -c "import sys, yaml; d=yaml.safe_load(sys.stdin); print('\n'.join(d['permissions']['filesystem']['allowlist']))"
```

**Pass:** Output includes a path that's a prefix of `~/Projects/appmilla_github/api_test` (e.g. `/home/forge/build-workspace` if that's where forge clones, or `/home/richardwoollcott/Projects/appmilla_github` if a host-mounted layout). If the path doesn't cover api_test, the autobuild will fail at the Player's first write with a permissions error. Edit `~/forge-state/forge.yaml`, `docker restart forge-prod`, recheck §0.5.

**2026-05-14 state of allowlist:** `/home/richardwoollcott/Projects/appmilla_github/api_test` is on the list (added during the TASK-ABW-OPS handoff). The new `autobuild_runner` resolver applies the same check to the **host-side** repo path, so the allowlist now serves both forge-prod's `feature_yaml_path` check *and* the sidecar's repo-checkout check. Re-verify after any `forge.yaml` edit + `docker restart forge-prod`.

### 0.8 Known caveats — read before going on stage

1. **Bridge fast-fail bug (does NOT block the happy path).** Forge-prod's lifecycle bridge fetches the sidecar run's terminal snapshot via the langgraph thread API *after* the run finishes. With the in-memory `--allow-blocking` backend, the thread state is evicted ~immediately after the terminal node fires. For runs that complete in < ~2 s, the bridge misses the snapshot, leaves the message un-acked, and JetStream redelivers in a 30 s loop until the per-attach deadline timer (5 min) eventually publishes a synthetic `build-failed`. **Mitigation:** the FEAT-9E59 build takes ~18 min, so the bridge has ample time to observe transitions live during the run. If anything in the Player turn fails fast (e.g., missing task file, missing dep), the demo will show no envelopes beyond `build-queued` until the 5-min deadline timer fires. Tracked as TASK-ABW-003 (bridge identity provider) and TASK-ABW-004 (langgraph backend persistence).
2. **`repo`/`branch`/`feature_yaml_path` not plumbed end-to-end.** The new `autobuild_runner` reads `payload.repo` but `dispatch_autobuild_async` doesn't forward it. Hotfix in place via `FORGE_DEFAULT_REPO` env var (see §0.6). For multi-repo demos this won't scale; for FEAT-9E59 (single repo) it works. Tracked as TASK-ABW-002.
3. **Coach's SDK test execution may log an error and still approve.** The 2026-05-14 preflight showed `SDK coach test execution failed (exit code 1)` immediately followed by `Coach approved`. Tests actually pass when run via `pytest` directly. Cosmetic-grade log noise, not a code-quality red. Tracked as TASK-ABW-005.

### 0.9 Pick stage framing

Per the table at top — recommended: framing 1. Capture in your RESULTS scratch.

---

## Phase 1: Canonical NATS provisioning verified

Same as the parent runbook §0.4 / first-real-run §1. Quick sanity gate — the PIPELINE stream covers `pipeline.>` and the `forge-serve` durable is bound.

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
bash scripts/verify-nats.sh
```

**Pass:** All 7 streams + 4 KV buckets present.

```bash
nats --server "$NATS_URL" stream info PIPELINE -j \
  | jq -r '.config.subjects[]'
```

**Pass:** Output includes `pipeline.>` (or explicitly `pipeline.build-queued.>` + `pipeline.build-started.>` + `pipeline.stage-complete.>` + `pipeline.build-complete.>` — the canonical PIPELINE stream covers them all under `pipeline.>`).

---

## Phase 2: Jarvis up + chat surface ready

Pick **one** of the two front-end paths. Both have been proven green.

### 2.A OpenWebUI (recommended for stage — visually richest)

Per the multi-specialist runbook §2 — bring up `jarvis serve-nats` and confirm OpenWebUI is at `http://localhost:8080/`:

```bash
cd ~/Projects/appmilla_github/jarvis
set -a && source ../nats-infrastructure/.env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
set -a && source .env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
export JARVIS_LOG_LEVEL=INFO
nohup .venv/bin/jarvis serve-nats > /tmp/jarvis-serve-nats-version-demo.log 2>&1 &
sleep 3
grep -E 'jarvis_serve_nats_ready|jarvis_startup_complete' /tmp/jarvis-serve-nats-version-demo.log | tail -5
```

**Pass:** log shows `jarvis_serve_nats_ready` and `jarvis_startup_complete nats_available=true capabilities_mode=live`. Open browser at `http://localhost:8080/`, pick the **Jarvis** model in OpenWebUI's model picker.

### 2.B CLI `jarvis chat` (lower visual cost, easier to debug)

```bash
cd ~/Projects/appmilla_github/jarvis
set -a && source ../nats-infrastructure/.env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
set -a && source .env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
export JARVIS_LOG_LEVEL=INFO
.venv/bin/jarvis chat 2>&1 | tee /tmp/jarvis-chat-version-demo.log
```

**Pass:** banner renders, `>` prompt appears, boot log includes `forge_notifications_subscribed subjects=[pipeline.build-started.>, pipeline.stage-complete.>, pipeline.build-complete.>, pipeline.build-failed.>]`. Without that subscription line the §6 notification drain won't fire.

---

## Phase 3: Wire-level evidence panes (run BEFORE §4)

Open these in separate SSH/terminal panes before issuing the prompt — the envelopes land within seconds and you want them on tape from the start. Mirrors the multi-specialist runbook §3.3 pattern.

### 3.1 Tail `pipeline.>` (captures the entire forge lifecycle)

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "pipeline.>" --raw \
  | tee /tmp/version-demo-pipeline.log
```

**Expected during §4 (and the subsequent ~33 min):**
1. `pipeline.build-queued.FEAT-9E59` (jarvis publishes — within ~1s of §4.1)
2. `pipeline.build-started.FEAT-9E59` (forge emits on dequeue — within ~5-10s)
3. `pipeline.stage-complete.FEAT-9E59` ×N (forge emits per Player-Coach turn — N≥1, expected 1-3 for this 1-task feature)
4. `pipeline.build-complete.FEAT-9E59` (forge emits at terminal success; ~33 min after queue)

All four sharing the same `correlation_id` (a fresh pipeline-side uuid; **distinct from** the jarvis-side `correlation_id` returned by `queue_build` — see the 5/13 RESULTS cross-correlation table for the two-uuid pattern).

### 3.2 Tail the inbound `agents.command.jarvis` traffic (OpenWebUI only)

Only needed if you're on path 2.A. Confirms the user prompt landed on the fleet pipe:

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.command.jarvis" --raw \
  | tee /tmp/version-demo-command.log
```

---

## Phase 4: The demo turn — `queue_build` for FEAT-9E59

### 4.1 The exact prompt to paste

In OpenWebUI's chat (model: Jarvis) or in the CLI `>` prompt:

```text
Queue a forge build for FEAT-9E59 from .guardkit/features/FEAT-9E59.yaml in appmilla/api_test on the ddd-demo branch. I want to walk through the autobuild end-to-end and see notifications come back through this chat.
```

The supervisor should:

1. Recognise the request as `queue_build` (pattern-A fire-and-forget per ADR-SP-014).
2. Construct the call: `queue_build(feature_id="FEAT-9E59", feature_yaml_path=".guardkit/features/FEAT-9E59.yaml", repo="appmilla/api_test", branch="ddd-demo", originating_adapter="<auto-from-session-adapter>")`.
3. Receive the `BuildQueuedPayload` ack from the JetStream publish.
4. Render a markdown-bullet reply with the `correlation_id` + `publish_target`.

### 4.2 What the reply should look like (load-bearing lines)

```text
FEAT-9E59 has been queued for build.

- **Correlation ID:** `<uuid>`             ← capture this
- **Publish target:** `pipeline.build-queued.FEAT-9E59`
- **Feature YAML:** `.guardkit/features/FEAT-9E59.yaml`
- **Repo:** `appmilla/api_test`
- **Branch:** `ddd-demo`

Forge will pick it up from the JetStream PIPELINE stream. I'll surface stage-complete events as they arrive.
```

**Match these two lines as the load-bearing evidence:**
- `- **Correlation ID:** \`<uuid>\``
- `- **Publish target:**` (or `- **Target:**`) `pipeline.build-queued.FEAT-9E59`

Prose around them varies; the two bullets are the contract per [first-real-run §6.2](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md#62-issue-the-queue-request).

**Save `<correlation_id>` from the first bullet** — call it `JARVIS_CID` (the jarvis-side request thread). A **second** `correlation_id` (the **pipeline** correlation id, call it `PIPELINE_CID`) appears on the wire envelopes captured by §3.1; the two are distinct and both worth recording. The 5/13 demo captured `JARVIS_CID=4c8c47ef-…` and `PIPELINE_CID=f29b5840-…` for FEAT-EC3C as the canonical example.

### 4.3 What's happening in the background

While you take §5's side-turn, expect (you can watch the §3.1 pane):

| Wire event | Typical latency from §4.1 | What forge is doing |
|---|---|---|
| `pipeline.build-queued.FEAT-9E59` | <1s | Jarvis published; forge-serve consumer about to dequeue |
| `pipeline.build-started.FEAT-9E59` | 5-10s | Forge has dequeued, run_id minted, langgraph-runner started the autobuild_runner graph |
| `pipeline.stage-complete.FEAT-9E59` #1 | ~2-15 min | Player turn finished (wrote files), Coach turn approved or asked for changes |
| `pipeline.stage-complete.FEAT-9E59` #2 (optional) | ~10-25 min | Second turn if Coach asked for a patch |
| `pipeline.build-complete.FEAT-9E59` | ~20-35 min | Terminal — feature yaml flipped to `completed`, autobuild/FEAT-9E59 branch ready to merge |

If `build-complete` doesn't arrive within 60 min, treat as failure mode (see §7).

---

## Phase 5: Drain notifications into the next REPL turn (framing 1)

This is the visible payoff. Jarvis's chat handler drains `pending_notifications(session_id)` before assembling each next reply. **Without a second chat turn, the audience sees nothing flow back.** Take one quick side-turn.

### 5.1 Side-turn prompt (any short conversational beat works)

In the same chat session, paste something light that's quick to answer — the goal is to trigger the drain, not to extract new information:

```text
While that runs — can you give me a one-line summary of what you just queued, and tell me if forge has reported back yet?
```

Or — if you want to fill stage time with a second specialist beat — paste a small architect_align question (e.g. "ask the architect whether adding a /version endpoint conflicts with ADR-ARCH-001"). That'll dispatch to architect-agent (~20-30s) and on its return, drain whatever forge envelopes have landed in the interim.

### 5.2 What you should see (load-bearing)

The supervisor's reply should include something like:

```text
I queued FEAT-9E59 a moment ago. Forge has started the build — here's what's landed so far:

- **[HH:MM] Forge FEAT-9E59:** build-started (run_id=<...>)

build-complete typically arrives in 20-35 minutes for a single-task feature; I'll surface stage-complete events as they come in.
```

The `Forge FEAT-9E59:` lines are rendered by `ForgeNotification.render_line()`. **One or more bulleted notification lines threaded by the same `PIPELINE_CID`** = drain works = demo passes.

Cross-check against the log:

```bash
grep -E 'chat_invoke_complete.*notifications_drained=[1-9]' /tmp/jarvis-serve-nats-version-demo.log | tail -3
# CLI path: same grep against /tmp/jarvis-chat-version-demo.log
```

**Pass:** at least one `notifications_drained=N` line where `N≥1`. (On 5/13 FEAT-EC3C drained both `build-started` and `build-complete` in a single turn because the build was an instant no-op; on FEAT-9E59 expect `N=1` for `build-started` only on the side-turn, with `stage-complete` and `build-complete` drainable on later turns or in the post-talk write-up.)

### 5.3 (Optional, off-stage) Wait for build-complete

If you're not on stage, leave the chat open and the §3.1 pane running. Roughly 20-35 min after §4.1, watch for:

```
pipeline.build-complete.FEAT-9E59
```

The Forge container's `autobuild/FEAT-9E59` worktree branch in api_test will now carry the Player-Coach commits with the actual `src/version/router.py` implementation. Verify:

```bash
cd ~/Projects/appmilla_github/api_test
git fetch origin
git log --oneline origin/autobuild/FEAT-9E59 -10 2>/dev/null \
  || git log --oneline -10 .guardkit/worktrees/FEAT-9E59 2>/dev/null
ls -la .guardkit/worktrees/FEAT-9E59/src/version/ 2>/dev/null
```

**Pass:** A `src/version/router.py` exists in the worktree with the `VersionResponse` schema and the GET /version handler. The worktree is on `autobuild/FEAT-9E59`. Smoke-test the endpoint:

```bash
cd ~/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-9E59
git status
# (optionally run the tests)
.venv/bin/pytest tests/test_version.py -v 2>/dev/null || pytest src/version/ -v
```

---

## Phase 6: Capture evidence

### 6.1 Save the pipeline envelopes

```bash
mkdir -p ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo
cp /tmp/version-demo-pipeline.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${PIPELINE_CID}-pipeline.log

# Filter to just the FEAT-9E59 envelopes for the slide
jq -c 'select(.subject | test("FEAT-9E59"))' /tmp/version-demo-pipeline.log \
  > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${PIPELINE_CID}-feat-9e59-only.json
```

### 6.2 Save the queue_build response payload

For the OpenWebUI path (path 2.A), filter the result tap by the JARVIS_CID:

```bash
# (Assumes you also tailed agents.result.> in pane 3 if going for full evidence)
jq -c --arg cid "$JARVIS_CID" \
   'select(.correlation_id == $cid) | .payload.result' \
   /tmp/jarvis-multi-specialist-e2e-result.log 2>/dev/null \
   > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${JARVIS_CID}-queue-payload.json
```

For the CLI path (2.B), the load-bearing markdown reply is already in the `tee` log:

```bash
grep -A 8 "FEAT-9E59 has been queued" /tmp/jarvis-chat-version-demo.log \
  > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${JARVIS_CID}-queue-reply.txt
```

### 6.3 Save the chat transcript

```bash
cp /tmp/jarvis-chat-version-demo.log \
   ~/.jarvis/transcripts/${JARVIS_CID}.txt
# Or for serve-nats path, screenshot/paste the OpenWebUI thread.
```

### 6.4 Save the autobuild worktree diff (post-build, for slide)

Once `build-complete` lands (off-stage):

```bash
cd ~/Projects/appmilla_github/api_test
git fetch origin
git diff origin/ddd-demo..origin/autobuild/FEAT-9E59 -- src/version/ src/main.py \
  > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/feat-9e59-diff.patch
```

**This is the punchline slide:** the actual code Forge wrote, framed against the `ddd-demo` source.

### 6.5 Write the RESULTS file

`docs/runbooks/RESULTS-jarvis-forge-autobuild-version-endpoint-demo-<YYYY-MM-DD>.md` mirroring this runbook's phase structure with a `Phase | Gate | Outcome | Evidence` table. Use the multi-specialist 5/13 RESULTS as the template.

---

## Phase 7: Failure modes — fast triage

Don't read this on stage. Internalise it.

| Symptom | Likely cause | Fix |
|---|---|---|
| `queue_build` returns `status: validation_error` | `feature_id` failed the `^FEAT-[A-Z0-9]{3,12}$` regex; or yaml path/branch malformed | Re-paste with `FEAT-9E59` exactly. The regex passes `FEAT-9E59` (4 alphanumeric chars in the tail). |
| `queue_build` returns `status: degraded` | NATS publish failed | Re-check §0.3 — auth env not sourced in this shell, or PIPELINE stream subjects don't cover `pipeline.build-queued.>`. |
| §3.1 pane shows `build-queued` but no `build-started` within 30s | Forge-prod consumer not attached, or container Exited | Re-check §0.5. `docker logs forge-prod | tail -50` will show the cause. Most common: NATS broker bounced since forge last started → restart the container. |
| §3.1 pane shows `build-started` but no `stage-complete` within 60 min | Player-Coach loop stuck (the FEAT-3CC2 timeout failure mode from Feb 2026) | Capture forge-prod logs + the langgraph-runner sidecar log. Off-stage: the build is unrecoverable mid-run — fall back to `--fresh` re-run, or accept the failure as a known capability boundary. On-stage: pivot to the talk-track "we have ~60 minutes of build wall-clock, here's what was happening at the 30-second mark" narration. |
| `stage-complete` arrives but no `build-complete` after 60 min | Player-Coach finished but terminal-publish path broke | Inspect `nats consumer info PIPELINE forge-serve -j` — if `ack_floor` advanced past the build-queued seq, forge thinks it completed. Check `.guardkit/worktrees/FEAT-9E59/.guardkit/features/FEAT-9E59.yaml` for the status field. Likely a forge-side bug; file a follow-up but do not block the demo on it. |
| Side-turn reply renders but no `Forge FEAT-9E59:` notification line | `forge_notifications_subscribed` log line missing at boot, or the drain path silently skipped | Re-check §2's boot log for the four-subject subscription. If absent, jarvis post-F010Db disjoint filter isn't applied — capture log and stop. |
| Worktree on `autobuild/FEAT-9E59` exists from a prior failed run, and the orchestrator picks up stale state | TASK-J006-006 footgun per [`autobuild-orchestration.md`](autobuild-orchestration.md) | **Off-stage only**: `guardkit autobuild feature FEAT-9E59 --fresh` in api_test to wipe the worktree + re-seed from `ddd-demo`. On stage: this should already be clean from rehearsal. |
| Build fails with `PermissionError` writing to the worktree | §0.7 allowlist doesn't cover the worktree path | Edit `~/forge-state/forge.yaml` to include a parent of the api_test worktree path, `docker restart forge-prod`, re-run. |

---

## Phase 8: Demo close

Once §4 has rendered the `queue_build` ack and §5 has drained at least one notification line:

- [ ] `pipeline.build-queued.FEAT-9E59` envelope captured in §3.1 tap with a `PIPELINE_CID`
- [ ] Supervisor's reply in §4.2 carries a `JARVIS_CID` (markdown bullet) and `Publish target: pipeline.build-queued.FEAT-9E59`
- [ ] §5.2 side-turn reply rendered at least one `[HH:MM] Forge FEAT-9E59: build-started ...` notification line, threaded by `PIPELINE_CID`
- [ ] `notifications_drained=N` (N≥1) line present in the jarvis log

If all four check, the stage-visible portion is **green**. Leave the chat session and §3.1 pane running until `build-complete` arrives off-stage (for the §6.4 slide); take down nothing on the GB10 — other work depends on the broker, llama-swap, and forge-prod.

---

## See also

- **Multi-specialist parent runbook** (Turn 3 is the forge wire this runbook specialises): [`RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md`](RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md)
- **Last known-green forge wire** (FOLLOWUP-A and FOLLOWUP-B both resolved): [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`](RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md)
- **Forensic first-real-run runbook** (deeper failure tables): [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Autobuild operational lessons** (worktree footgun, `--fresh` semantics): [`autobuild-orchestration.md`](autobuild-orchestration.md)
- **Feature plan output:** `api_test/.guardkit/features/FEAT-9E59.yaml`, `api_test/tasks/backlog/version-endpoint/`
- **queue_build tool surface:** [`jarvis/src/jarvis/tools/dispatch.py`](../../src/jarvis/tools/dispatch.py) `queue_build` (signature + return shape)
- **ForgeNotification rendering** (the `[HH:MM] Forge FEAT-…:` line format): [`jarvis/src/jarvis/infrastructure/forge_notifications.py`](../../src/jarvis/infrastructure/forge_notifications.py)
