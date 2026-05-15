# DEMO CARD — FEAT-9E59 `/version` endpoint autobuild

**Purpose:** one-page operator card for **dress rehearsal (2026-05-15)** and **demo proper (2026-05-16, DDD South West)**. Top-to-bottom is the order of operations. Copy-paste blocks are inside fences; OpenWebUI prompts are in quote blocks.

For the deeper "why" + topology + talk track, see the parent runbook: [RUNBOOK-jarvis-forge-autobuild-version-endpoint-demo.md](RUNBOOK-jarvis-forge-autobuild-version-endpoint-demo.md). For the most recent preflight evidence: [RESULTS-jarvis-forge-autobuild-version-endpoint-demo-2026-05-14-preflight.md](RESULTS-jarvis-forge-autobuild-version-endpoint-demo-2026-05-14-preflight.md).

**Status (2026-05-14):** preflight green, ~18 min end-to-end. Wire-mediated rehearsal still pending. **One known caveat:** if anything in the Player turn fast-fails (< ~2 s), forge-prod's bridge will miss the snapshot, hit the JetStream redelivery loop, and only emit a synthetic `build-failed` after a 5-min deadline timer. For an 18-min happy-path build this does not bite. See [TASKS-ABW-002-005-DRAFT.md](TASKS-ABW-002-005-DRAFT.md) §ABW-003/004 for the architectural follow-up.

---

## Phase A — Reset state (run **before** rehearsal and before demo proper)

A clean reset takes ~60 s. Run all of this from a fresh terminal on the GB10.

### A.1 Reset api_test to "ready to demo" state

```bash
cd ~/Projects/appmilla_github/api_test

# 1. Confirm we're on ddd-demo. If the previous run left us on after-demo, switch back.
git checkout ddd-demo

# 2. Restore the feature spec + task file if guardkit stamped status: completed onto them.
git checkout -- .guardkit/features/FEAT-9E59.yaml \
                  tasks/backlog/version-endpoint/TASK-VER-001-add-version-endpoint.md

# 3. Remove any autobuild runtime artefacts from the main checkout.
rm -rf .guardkit/autobuild/FEAT-9E59 \
       .guardkit/autobuild/TASK-VER-001 \
       .guardkit/graphiti-query-log.jsonl

# 4. Tear down any leftover autobuild worktree + branch from a prior run.
git worktree list | grep -q "FEAT-9E59" && \
    git worktree remove .guardkit/worktrees/FEAT-9E59 --force
git branch -D autobuild/FEAT-9E59 2>/dev/null || true

# 5. Verify the spec is back to status: planned and the task is back to status: pending.
grep -E "^status:" .guardkit/features/FEAT-9E59.yaml
grep "  status:" tasks/backlog/version-endpoint/TASK-VER-001-add-version-endpoint.md | head -2
# Expected: spec status=planned, task frontmatter status=pending

# 6. Working tree should now be clean.
git status -s -uno
```

The `after-demo` branch (snapshot of "what forge built last time") stays untouched. It's your live evidence slide if needed.

### A.2 Purge any stuck JetStream messages + reset forge-prod dedup memory

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"

# 1. Drop any pending pipeline.build-queued messages from prior runs.
nats --server "$NATS_URL" stream purge PIPELINE --force

# 2. Restart forge-prod to clear its in-memory "duplicate active build" dedup set.
docker restart forge-prod && sleep 6
docker ps --filter name=forge-prod --format '{{.Names}}\t{{.Status}}'
curl -sf http://localhost:8088/healthz
```

### A.3 Restart the langgraph sidecar

The sidecar runs as a **user systemd service** — `forge-langgraph-sidecar.service`
(unit: `~/.config/systemd/user/forge-langgraph-sidecar.service`). The unit
already carries the two env vars `autobuild_runner` needs (`FORGE_CONFIG_PATH`,
`FORGE_DEFAULT_REPO`) — there is no shell-export dance, and it auto-starts at
boot alongside `llama-swap` and `jarvis-serve-nats`.

```bash
# 1. Restart the sidecar (one command — systemd handles port release + relaunch).
systemctl --user restart forge-langgraph-sidecar
sleep 10

# 2. Verify it is up and the autobuild_runner graph imported.
systemctl --user is-active forge-langgraph-sidecar
curl -sf http://localhost:8124/openapi.json | jq -r '.info.title'
journalctl --user -u forge-langgraph-sidecar --since "1 min ago" \
    | grep -E "Application started up|Importing graph profiling.*autobuild_runner" | head -3
```

Expected output:
- `is-active` returns `active`
- `curl` returns `LangSmith Deployment`
- The grep shows both `Importing graph profiling … graph_id=autobuild_runner` and `Application started up in 0.2xx s`

---

## Phase B — Pre-stage verification (run ~15 min before stage)

Single command checks that should all return green:

```bash
echo '--- jarvis main ---'
cd ~/Projects/appmilla_github/jarvis && git log --oneline -1

echo '--- forge main (must include 7006c7d hotfix) ---'
cd ~/Projects/appmilla_github/forge && git log --oneline -3 | grep -E "7006c7d|hotfix" \
    || echo "WARN: hotfix commit missing — re-check"

echo '--- api_test ddd-demo (spec status=planned) ---'
grep "^status:" ~/Projects/appmilla_github/api_test/.guardkit/features/FEAT-9E59.yaml

echo '--- forge-prod ---'
docker ps --filter name=forge-prod --format '{{.Names}} {{.Status}}'
curl -sf http://localhost:8088/healthz

echo '--- sidecar service ---'
systemctl --user is-active forge-langgraph-sidecar
curl -sf http://localhost:8124/openapi.json | jq -r '.info.title'

echo '--- allowlist (must contain api_test path) ---'
grep api_test ~/forge-state/forge.yaml \
    || echo "WARN: api_test not in allowlist — Phase A.2 may need re-running"

echo '--- NATS PIPELINE empty? ---'
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    stream info PIPELINE 2>&1 | grep -E "Messages:"
# Expected: Messages: 0
```

---

## Phase C — Wire-tap panes (open in separate terminals BEFORE the stage prompt)

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"

# Pane 1 — pipeline envelopes (build-queued, build-started, stage-complete, build-complete)
nats --server "$NATS_URL" sub "pipeline.>" --raw | tee /tmp/demo-pipeline.log

# Pane 2 (optional) — agent command bus (only useful on the OpenWebUI path)
nats --server "$NATS_URL" sub "agents.command.jarvis" --raw | tee /tmp/demo-command.log

# Pane 3 (optional) — sidecar log tail (autobuild_runner messages)
journalctl --user -u forge-langgraph-sidecar -f | grep --line-buffered \
    -E "autobuild_runner|FORGE_DEFAULT_REPO|launching subprocess|guardkit|transitioning"
```

---

## Phase D — Jarvis up + chat surface

Choose **one** of the two paths.

### D.1 (Recommended for stage) — OpenWebUI

```bash
# 1. Bring jarvis serve-nats up if not already running.
cd ~/Projects/appmilla_github/jarvis
set -a && source ../nats-infrastructure/.env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
set -a && source .env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
export JARVIS_LOG_LEVEL=INFO

(nohup .venv/bin/jarvis serve-nats > /tmp/jarvis-serve-nats.log 2>&1 &)
sleep 8

# 2. Verify boot.
grep -E "jarvis_serve_nats_ready|jarvis_startup_complete" /tmp/jarvis-serve-nats.log | tail -5
# Expected: jarvis_serve_nats_ready ... and jarvis_startup_complete nats_available=true capabilities_mode=live
```

Then open **http://localhost:8080/** in a browser, pick **Jarvis** in the model dropdown, and you're ready.

### D.2 (Easier debug — CLI) — `jarvis chat`

```bash
cd ~/Projects/appmilla_github/jarvis
set -a && source ../nats-infrastructure/.env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
set -a && source .env && set +a
export JARVIS_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
export JARVIS_LOG_LEVEL=INFO
.venv/bin/jarvis chat 2>&1 | tee /tmp/demo-jarvis-chat.log
```

Wait for the `>` prompt + the `forge_notifications_subscribed` line in the boot log.

---

## Phase E — The actual demo prompts (paste into OpenWebUI / CLI chat)

### E.1 The main stage prompt (paste this first)

> Queue a forge build for FEAT-9E59 from `.guardkit/features/FEAT-9E59.yaml` in `appmilla/api_test` on the `ddd-demo` branch. I want to walk through the autobuild end-to-end and see notifications come back through this chat.

**What jarvis should do** (visible in the reply):
- Recognise the intent → call `queue_build(feature_id="FEAT-9E59", feature_yaml_path=".guardkit/features/FEAT-9E59.yaml", repo="appmilla/api_test", branch="ddd-demo")`
- Receive the `BuildQueuedPayload` ack from JetStream
- Render a markdown reply with `correlation_id` + `publish_target` (`pipeline.build-queued.FEAT-9E59`)

**Wire envelopes Pane 1 should now see (in order):**
1. `pipeline.build-queued.FEAT-9E59` (jarvis publishes — within ~1 s of the prompt landing)
2. `pipeline.build-started.FEAT-9E59` (forge-prod emits on dequeue — within ~5-10 s)
3. `pipeline.stage-complete.FEAT-9E59` ×1 (forge emits on Player-Coach turn 1 approval — single-task feature)
4. `pipeline.build-complete.FEAT-9E59` (forge emits at terminal success — ~18 min after queue per the 2026-05-14 preflight)

All four share the **same `correlation_id`** (a fresh pipeline-side uuid, **distinct from** the jarvis-side `correlation_id` returned by `queue_build`).

### E.2 Drain prompt (paste ~60-90 s after E.1 — fills the wait window + surfaces notifications)

Any short conversational turn will drain pending notifications into the reply. Three variants — pick whichever feels natural:

**Option 1 (neutral, low cognitive load):**

> What's happening with that build?

**Option 2 (looks like a real working question):**

> While that's running, what tools do you have available right now?

**Option 3 (architecture-aligned — pairs well with the multi-specialist talk track):**

> While that's running, can you ask the architect to sanity-check whether exposing GET /version conflicts with anything in our ADRs?

Jarvis renders the side answer **and** appends any `ForgeNotification.render_line()` lines for envelopes that have arrived since the previous turn. The `build-started` line is the headline you want on screen.

### E.3 (Optional — if framing 1 has time budget) — second drain after another ~60 s

> Anything new from forge yet?

This will surface the first `stage-complete` envelope (per the 2026-05-14 preflight, fires ~8 min into the build after Coach approves turn 1).

### E.4 (Off-stage — after build-complete lands, ~18 min after E.1)

> Did that build finish? What did forge actually produce?

Drains the `build-complete` envelope and the supervisor will summarise the result (correlation_id, exit status, the files created).

---

## Phase F — Capture evidence (post-stage)

```bash
DATE=$(date -u +%Y-%m-%d)
EVIDENCE=~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo
mkdir -p "$EVIDENCE"

# 1. Pipeline envelopes captured during the run.
cp /tmp/demo-pipeline.log "$EVIDENCE/${DATE}-pipeline.log"

# 2. Sidecar autobuild trace.
journalctl --user -u forge-langgraph-sidecar --since "60 min ago" \
    | grep -E "autobuild_runner|guardkit|launching subprocess|transitioning|stage_complete" \
    > "$EVIDENCE/${DATE}-sidecar-autobuild.log"

# 3. Chat transcript (CLI path only — OpenWebUI keeps it in its own DB).
[ -f /tmp/demo-jarvis-chat.log ] && \
    cp /tmp/demo-jarvis-chat.log "$EVIDENCE/${DATE}-jarvis-chat-transcript.log"

# 4. The actual code forge built — branch reference, not a copy.
cd ~/Projects/appmilla_github/api_test
git log --oneline -3 autobuild/FEAT-9E59 > "$EVIDENCE/${DATE}-autobuild-branch-tip.txt" 2>&1 \
    || echo "autobuild/FEAT-9E59 branch absent (build did not complete or worktree already cleaned)"

echo "Evidence captured to $EVIDENCE/"
ls -la "$EVIDENCE/" | grep "$DATE"
```

---

## Phase G — Break-glass (something is broken, stage is happening in 5 min)

### G.1 Wire is silent after the queue_build prompt

Wire-tap shows only `pipeline.build-queued.FEAT-9E59` — no `build-started`. Most likely the sidecar didn't get the dispatch.

```bash
# Check sidecar is alive
systemctl --user is-active forge-langgraph-sidecar
curl -sf http://localhost:8124/openapi.json | jq -r '.info.title'

# Check sidecar log for the dispatched run
journalctl --user -u forge-langgraph-sidecar --since "5 min ago" \
    | grep -E "autobuild_runner|graph_id=autobuild_runner" | tail -10

# Check forge-prod for the dispatch attempt
docker logs forge-prod --since 5m 2>&1 | grep -E "FEAT-9E59|dispatch_build|build-queued" | tail -10
```

If sidecar didn't pick it up, restart it (Phase A.3) and re-run E.1.

### G.2 Forge-prod is in a JetStream redelivery loop (bug ABW-003/004)

Symptom: `docker logs forge-prod` shows repeated `duplicate active build for feature_id=FEAT-9E59` + `Thread with ID … not found` every ~30 s.

```bash
# Kill the loop: purge PIPELINE + restart forge-prod (clears dedup)
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" stream purge PIPELINE --force

docker restart forge-prod && sleep 6
docker ps --filter name=forge-prod --format '{{.Names}} {{.Status}}'

# Fall back to framing 3 narration: queue published successfully, build is running, post-talk write-up will carry the diff
```

### G.3 `missing repo in launch payload` in sidecar log

`FORGE_DEFAULT_REPO` is not reaching the sidecar. It is baked into the
`forge-langgraph-sidecar.service` unit (`Environment=FORGE_DEFAULT_REPO=...`),
so this should not happen — if it does, the unit was edited or the sidecar
is being run outside systemd. Check:

```bash
systemctl --user show forge-langgraph-sidecar -p Environment
systemctl --user restart forge-langgraph-sidecar
```

If the env line is missing, re-add it to
`~/.config/systemd/user/forge-langgraph-sidecar.service`, then
`systemctl --user daemon-reload && systemctl --user restart forge-langgraph-sidecar`.

### G.4 Drop to framing 3 (narration only)

If the wire breaks 1 min before stage and you can't recover:

> *"I'm going to type one sentence into chat. Jarvis recognises it as a build request and queues it on the NATS pipeline. Forge will pick that up off-stage and run a real autobuild — the version endpoint will be a Player-Coach loop writing FastAPI code, running pytest, and committing checkpoint commits to a feature branch. The output diff will be on the post-talk write-up."*

Paste E.1, point at the `pipeline.build-queued.FEAT-9E59` envelope on the wire-tap pane, and move on.

---

## Phase H — Post-demo cleanup

```bash
# 1. The autobuild produced a fresh `autobuild/FEAT-9E59` branch in api_test.
#    Optionally fast-forward `after-demo` onto it so you have an up-to-date snapshot of
#    "what forge built" for the next demo iteration.
cd ~/Projects/appmilla_github/api_test
git checkout after-demo
git merge autobuild/FEAT-9E59 --no-edit  # or rebase, your call
git checkout ddd-demo

# 2. Re-run Phase A entirely if you plan to re-demo.
```

---

## Reference — repo state expected at all times

| Repo | Branch | Tip | Meaning |
|---|---|---|---|
| `jarvis` | `main` | `8824a39` or descendant | Stable. No FEAT-9E59-specific code here. |
| `forge` | `main` | `7006c7d` or descendant (must include hotfix) | Autobuild-runner subprocess wireup + `FORGE_DEFAULT_REPO` env-var fallback. |
| `api_test` | `ddd-demo` | `87a2da1` | Feature spec + task plan, **no version endpoint code**. Ready for re-build. |
| `api_test` | `after-demo` | `bd251a6` or newer | Snapshot of the most recent successful FEAT-9E59 build — your "this is what forge built" evidence branch. |
| `api_test` | `autobuild/FEAT-9E59` | (transient) | Fresh autobuild branch produced by each run. Disappears on reset (Phase A.1 step 4). |
