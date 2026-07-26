# Runbook: Jarvis → Forge Autobuild — `/uptime` endpoint demo (FEAT-UPT1)

**Status: Verified 2026-07-26.** The attended forge end-to-end rehearsal
(`build-FEAT-UPT1-20260726112342`) drove this path end-to-end: one chat
sentence → `queue_build` → JetStream → forge → local Player + config-baked
coach-ft-v4 turn-1 approve (0 issues) → human merge api_test `c5a04be`, with
**ZERO frontier calls on the critical path** (the merge stayed human — mission
law). This is the plan-of-record step-1 proof run and the first datum for the
mission's M0 measurable: a routine feature CAN ship frontier-free.

**Primary audience: the operator re-running the rehearsal.** The stage-demo
talk track survives as an appendix (§ Demo narrative) but is no longer the
point — the point is a repeatable, frontier-free autobuild. See §0.8 (Known
caveats) for the live-bridge fast-fail bug that does NOT block the happy path.

> **OPERATOR SILENCE LAW (read before you start).** During a build, take **NO
> chat turns.** The jarvis supervisor shares the single local workhorse seat
> with the Player-Coach loop; a side turn starves it and swap-thrashes the seat
> (receipt: build `110235` died on `API rate limit exceeded` after 2 real turns,
> 2026-07-26 — which also proved the chain writes real code: `src/uptime/`
> already existed on disk). The drain-needs-a-next-turn fact still holds — but
> the drain turn happens **AFTER** `build-complete`, not during the build. Queue
> the build, then stay silent and watch the wire (§3.1) until terminal; drain in
> §5 once the build is done.

**Purpose:** Drive a **real** Forge autobuild end-to-end from a Jarvis chat
session — not a no-op replay. The 2026-05-13 multi-specialist demo (see
[RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md](RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md))
proved the wire against `FEAT-EC3C`, but EC3C was already-completed state, so
Forge round-tripped in <1s with no actual build work. This runbook completes
the loop by autobuilding a **fresh** feature — a single `GET /uptime` endpoint
in `appmilla/api_test` on the disposable `ddd-demo` branch — so you see the
autobuilder actually produce code, run tests, and stage-complete back into the
chat.

```
human prompt in jarvis (OpenWebUI or CLI chat)
  → supervisor recognises queue_build pattern
  → queue_build(FEAT-UPT1, .guardkit/features/FEAT-UPT1.yaml, appmilla/api_test, ddd-demo)
  → JetStream pipeline.build-queued.FEAT-UPT1 (workqueue)
  → forge-prod durable consumer (forge-serve) dequeues
  → autobuild_runner subagent on langgraph-runner sidecar
  → Player-Coach loop writes src/uptime/router.py + src/uptime/schemas.py + tests + app wiring
  → guardkit-checkpoint commits land on autobuild/FEAT-UPT1 worktree branch
  → lifecycle bridge emits pipeline.build-started + stage-complete + build-complete
  → jarvis chat handler drains notifications into the next REPL turn (after build-complete)
```

Zero cloud LLM on the path. The build itself runs on the same Blackwell box as
the supervisor; the marginal cost is GPU-time on hardware you already paid for.

**Companion / source-of-truth references:**
- [`RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md`](RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md) — the parent runbook this one specialises; Turn 3 is the forge dispatch path proven on 2026-05-13.
- [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`](RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md) — last known-green forge wire (FOLLOWUP-A and FOLLOWUP-B both resolved).
- [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — canonical forensic doc for the forge dispatch wire (deeper failure-mode table; consult if anything goes red).
- [`autobuild-orchestration.md`](autobuild-orchestration.md) — operational lessons for re-running an autobuild against the same feature (the `--fresh` vs worktree-edit footgun).
- `api_test/.guardkit/features/FEAT-UPT1.yaml` — the living demo feature (spec commit `77dadce`), single task **TASK-UPT-001**. Built and merged 2026-07-26: coach-ft-v4 approved turn 1, human merge `c5a04be` on `ddd-demo`.

**Machine layout (single-host GB10, `promaxgb10-41b1`):** identical to the multi-specialist runbook. NATS JetStream + llama-swap (host) + specialist-agent + study-tutor + forge-prod + OpenWebUI + jarvis serve-nats. Nothing new spun up for this demo.

**Stage timing (if you are running this as a stage demo — read before picking a slot):**

The autobuild is **~15-35 min** of wall-clock. A stage demo cannot wait for
`build-complete`. But note the SILENCE LAW: you cannot fill the wait with chat
turns — a side turn starves the seat and can kill the build. Two honest framings:

1. **"Watch the queue, narrate the build, drain after."** ~2-3 min on stage:
   `queue_build` acks immediately (correlation id in the reply), then you go
   **silent** and point at the §3.1 wire pane where `build-started` and
   `stage-complete` envelopes land live. Do NOT take a chat turn to force a
   drain — the notifications drain into the **next** chat turn you take, which
   you take only **after** `build-complete` (off-stage, or in the post-talk
   write-up). The wire pane is the live proof; the chat drain is the epilogue.
2. **"Pre-warm before stage, drain on stage."** Run `queue_build` from a
   rehearsal session ~25 min before the talk and stay silent while it builds.
   By stage time `build-complete` has arrived; your single on-stage chat turn
   drains the terminal notifications in one reveal. Tight to coordinate, but it
   lands the "look, forge built it" moment in a single stage minute — and it
   never takes a chat turn during the build.

**Expected wall-clock for a clean re-run (full path):** ~30-60 min including the
build window.

**Outputs:**
- `docs/runbooks/RESULTS-jarvis-forge-autobuild-version-endpoint-demo-<YYYY-MM-DD>.md` per-phase outcomes
- `docs/runbooks/evidence/version-endpoint-demo/<correlation_id>-pipeline.json` — captured `pipeline.*` envelopes (build-queued, build-started, stage-complete×N, build-complete)
- `docs/runbooks/evidence/version-endpoint-demo/<correlation_id>-queue-payload.json` — the `queue_build` tool result
- `appmilla/api_test` worktree on branch `autobuild/FEAT-UPT1` with the Player-Coach commits — the **actual code produced** by Forge, capturable as a slide diff

---

## What this runbook does NOT cover

- **Long-running build orchestration** (architect-align → human review → patch → re-run). Out of scope; this is a one-shot autobuild end-to-end.
- **Failure recovery (`--fresh` reseed, worktree surgery).** Carried by [`autobuild-orchestration.md`](autobuild-orchestration.md). If the build fails mid-flight, do not try to repair it live — see §7. And per the F11 forensics law (§7), never re-run guardkit inside a kept evidence worktree.
- **Architect / tutor specialist dispatches.** They're the parent runbook's job; this one focuses on the forge path alone. And per the SILENCE LAW you would not dispatch a specialist mid-build anyway — it competes for the same seat.

---

## Demo narrative (talk track — appendix; the primary flow is the operator re-run above)

The runbook below is the operator script. The talk track is what the operator
says aloud while it runs. Roughly (framing 1):

1. **Frame** (~30s): "I'm going to type one sentence into chat. Jarvis will recognise it as a build request, queue it on the NATS pipeline, Forge will pick it up, and start running an actual autonomous build of a new endpoint into a FastAPI repo. We'll watch the envelopes flow on the wire pane."
2. **Show topology slide** (~30s): chat box → JetStream PIPELINE stream → forge-prod container → langgraph-runner sidecar → Player-Coach loop → JetStream lifecycle envelopes back. "All on this Blackwell box. No cloud."
3. **Type the prompt** (~10s): one line (§4.1).
4. **`queue_build` acks** (~5s): point at the response — "Queued. Correlation id `<uuid>`. The build is now running in the background."
5. **Go silent and watch the wire** (~the build window): DO NOT take another chat turn — the supervisor and the build share one seat. Point at the §3.1 pane as `build-started` and `stage-complete` land. "Forge is writing code into a repo and committing checkpoint commits on a feature branch — live, on this box, no cloud."
6. **Land the point** (~30s): "From one chat sentence to a real autonomous build. The notifications will drain back into the chat on my next turn — which I take once the build is done, because taking a turn mid-build would starve the model seat the builder is using."

Total on-stage narration: ~3-4 minutes plus the silent build-watch. Buffer for
first-token latency.

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
ls -la .guardkit/features/FEAT-UPT1.yaml
```

**Pass:** Branch is `ddd-demo` (not `main`). Working tree clean. `FEAT-UPT1.yaml` exists at the path shown.

> **Why a branch, not main:** the autobuild commits onto `autobuild/FEAT-UPT1` (a separate worktree branch under `.guardkit/worktrees/FEAT-UPT1`). Targeting `ddd-demo` as the *source* branch means the autobuild's merge target is also `ddd-demo`, isolating the demo from `main`. Per [`autobuild-orchestration.md`](autobuild-orchestration.md): main-repo edits to FEAT-UPT1 between runs are footguns — edit the worktree, or `--fresh`.

### 0.2a Confirm the tier-1 pass bar is pinned BEFORE implementation

api_test's `.guardkit/config.yaml` sets `qa.enforce_tier1: true`. That gate
(`guardkit/qa/enforcement.py`) refuses to start the task unless a pass bar for
the task exists and was committed **before** the implementation commits. For
this feature that file is **`qa/pass-bar-TASK-UPT-001.yaml`** — pinned at
`45f67eb` and schema-fixed at `5018f5c`, both ahead of the `c5a04be`
implementation checkpoint.

The bar's schema is `PassBar` (`guardkit/qa/formats/pass_bar.py`). Two rules
that bit during the rehearsal (F5):

- `dependency_down_degradation` is **mandatory on every bar** — even with
  `auth_surface_bearing: false`. An authless feature drops the four auth-shaped
  negative paths but never this one (`UNIVERSAL_NEGATIVE_PATHS` in pass_bar.py).
  For `/uptime` it is honest: the endpoint has no DB dependency, so the bar
  asserts it stays 200 and fully-shaped **while the database is down**.
- **Validate before queueing, never by trial.** Run the schema validator
  directly rather than discovering a `too_short` / missing-flag error from a
  failed build:

  ```bash
  cd ~/Projects/appmilla_github/api_test
  python3 -c "
  import sys, yaml
  from guardkit.qa.formats.pass_bar import PassBar
  d = yaml.safe_load(open('qa/pass-bar-TASK-UPT-001.yaml'))
  PassBar.model_validate(d); print('pass bar OK')
  "
  ```

**Pass:** prints `pass bar OK`. If you are authoring a bar for a NEW task,
`registered_at.{sha,date}` must predate the implementation commit.

### 0.3 Confirm NATS broker + auth env sourced

```bash
docker ps --filter name=ships-computer-nats --format '{{.Names}}\t{{.Status}}'
set -a && source ~/Projects/appmilla_github/nats-infrastructure/.env && set +a
export NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222"
nats --server "$NATS_URL" stream ls 2>&1 | head -5
```

**Pass:** `ships-computer-nats` Up (healthy). `nats stream ls` returns ≥7 streams. If `Authorization Violation`, redo the `source` line in this shell. (The password lives only in that `.env` — never paste it into a shell history you keep, a doc, or a commit.)

### 0.4 Confirm llama-swap is serving the supervisor model

```bash
ss -tlnp 2>/dev/null | grep :9000
curl -sf http://localhost:9000/v1/models | jq -r '.data[].id' | sort | grep -E 'qwen36-workhorse|coach-ft-v4|architect-agent'
```

**Pass:** `qwen36-workhorse` (the Player seat) is in the list, and `coach-ft-v4` (the config-baked coach) resolves. The autobuild's Player-Coach loop calls back into llama-swap for both — LOCAL, by design. Remember the SILENCE LAW: the supervisor shares the `qwen36-workhorse` seat with the Player, so do not fire specialist turns during a build.

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

### 0.6 Confirm langgraph-runner sidecar is reachable — AND carries the model env

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

> **ENV LAW — the May exit-3 wall (F4).** The runner subprocess inherits the
> sidecar's environment and the runner spawns `guardkit` with
> `env=os.environ.copy()`, so the sidecar's `[Service]` block is the durable
> seam that carries the model seat into the build. Two lines are **load-bearing
> and non-negotiable**:
>
> - `OPENAI_BASE_URL=http://localhost:9000/v1` — the Player's OpenAI-shaped
>   client talks to the local llama-swap seat here, never to cloud.
> - `OPENAI_API_KEY=dummy` — satisfies that client's key check; it is NOT a
>   secret and NOT a real credential.
>
> Without this pair the build fast-fails trying to reach a real OpenAI endpoint
> — this was THE May exit-3 wall. **After ANY sidecar restart, verify the
> running process actually carries them:**
>
> ```bash
> tr '\0' '\n' < /proc/$(systemctl --user show -p MainPID --value forge-langgraph-sidecar)/environ \
>   | grep -E '^OPENAI_BASE_URL=|^OPENAI_API_KEY='
> ```
>
> **Pass:** both lines print, with `OPENAI_BASE_URL=http://localhost:9000/v1`
> and `OPENAI_API_KEY=dummy`. If either is missing the runner will reach for
> cloud — stop and fix the unit before queueing.
>
> **Source of truth for the unit:** the version-controlled unit at
> `forge/ops/systemd/forge-langgraph-sidecar.service` carries these
> `Environment=` lines and is the durable, reproducible copy of the running
> unit (the installed unit historically lived ONLY under
> `~/.config/systemd/user`, so a box rebuild would silently lose the env). A
> forge lane is landing/reconciling these env lines onto the installed unit
> (2026-07-26) — treat the version-controlled file as the reference the running
> unit should match, and re-run the `/proc/<MainPID>/environ` check after any
> reconcile or restart.

**Coach resolution:** the coach is NOT pinned by an argv flag. It resolves from
the repo-baked config — `.guardkit/config.yaml` sets
`autobuild.coach.contract: v4` + `autobuild.coach.model: coach-ft-v4`
(api_test commit `562df96`; the same pairing is baked in all five build repos
since 2026-07-26). `GUARDKIT_COACH_CONTRACT` / `--coach-model` still override,
but the default needs no flags.

**Env-var contract (baked into the unit):** in addition to the two model-seat
lines above, the `autobuild_runner` needs:

- `FORGE_DEFAULT_REPO=appmilla/api_test` — the **fallback default used when
  `payload.repo` is absent**. It is no longer load-bearing for the wire path:
  the dispatcher DOES now forward `repo` and `branch` from the consumed
  `BuildQueuedPayload` into the launch payload (verified
  `forge/src/forge/pipeline/dispatchers/autobuild_async.py:530-533` — each key
  is added only when a value was threaded, so the legacy CLI / boot-rearm launch
  stays byte-compatible). `FORGE_DEFAULT_REPO` remains as the resolver's fallback
  for launches with no `payload.repo` in scope.
- `FORGE_CONFIG_PATH=~/forge-state/forge.yaml` — makes the resolver's allowlist
  check read the same config as forge-prod (rather than base-dir-only).
- `FORGE_GUARDKIT_PATH=~/.agentecflow/bin/guardkit` — the absolute path to the
  `guardkit` binary. **Required under systemd:** a user service gets systemd's
  minimal PATH (`/usr/local/bin:/usr/bin:/bin`), which does *not* include
  `~/.agentecflow/bin`, so the runner's `shutil.which("guardkit")` fallback
  fails without it (build fast-fails on `guardkit binary not found`).
- `PATH=~/.agentecflow/bin:~/.local/bin:/usr/local/bin:/usr/bin:/bin` — the
  `autobuild_runner` spawns `guardkit` with `env=os.environ.copy()`, so the
  guardkit subprocess inherits this PATH for its own tool calls (git, the
  bundled claude CLI, etc.).
- `GUARDKIT_HARNESS=langgraph` — the mission default harness; the 2026-07-26
  rehearsal ran with it unset, which resolves to the same `langgraph` default.

**After any `autobuild_runner.py` code change** — `langgraph dev` runs with
`--no-reload`, so restart the service to pick it up. Use an explicit
stop → wait → start: a bare `systemctl --user restart` can crash-loop on a
port-8124 release race (the outgoing process holds the port past the new
one's bind attempt; the service then stays `activating`, never `active`).

```bash
systemctl --user stop forge-langgraph-sidecar
sleep 5
systemctl --user start forge-langgraph-sidecar
sleep 10
systemctl --user is-active forge-langgraph-sidecar
curl -sf http://localhost:8124/openapi.json | jq -r '.info.title'
journalctl --user -u forge-langgraph-sidecar --since "1 min ago" \
    | grep "Application started up" | head -1
# THEN re-run the ENV LAW /proc check above — a restart is exactly when the env can go missing.
```

If a bare `restart` left it stuck `activating`: `stop`, confirm port 8124
is free (`ss -lntp | grep :8124`), then `start`.

### 0.7 Confirm forge filesystem allowlist covers api_test

Forge's `forge.yaml` allowlist must include a path that contains the api_test worktree root.

```bash
docker exec forge-prod cat /var/forge/forge.yaml 2>/dev/null \
  | python3 -c "import sys, yaml; d=yaml.safe_load(sys.stdin); print('\n'.join(d['permissions']['filesystem']['allowlist']))"
```

**Pass:** Output includes a path that's a prefix of `~/Projects/appmilla_github/api_test` (e.g. `/home/forge/build-workspace` if that's where forge clones, or `/home/richardwoollcott/Projects/appmilla_github` if a host-mounted layout). If the path doesn't cover api_test, the autobuild will fail at the Player's first write with a permissions error. Edit `~/forge-state/forge.yaml`, `docker restart forge-prod`, recheck §0.5.

**State of allowlist:** `/home/richardwoollcott/Projects/appmilla_github/api_test` is on the list (added during the TASK-ABW-OPS handoff; confirmed present during the 2026-07-26 rehearsal). The `autobuild_runner` resolver applies the same check to the **host-side** repo path, so the allowlist now serves both forge-prod's `feature_yaml_path` check *and* the sidecar's repo-checkout check. Re-verify after any `forge.yaml` edit + `docker restart forge-prod`.

### 0.8 Known caveats — read before running

1. **Bridge fast-fail bug (does NOT block the happy path).** Forge-prod's
   lifecycle bridge fetches the sidecar run's terminal snapshot via the
   langgraph thread API *after* the run finishes. With the in-memory
   `--allow-blocking` backend, the thread state is evicted ~immediately after
   the terminal node fires. For runs that complete in < ~2 s, the bridge misses
   the snapshot, leaves the message un-acked, and JetStream redelivers in a 30 s
   loop until the per-attach deadline timer (5 min) eventually publishes a
   synthetic `build-failed`. **Mitigation:** the FEAT-UPT1 build takes ~15 min
   (single Player turn), so the bridge has ample time to observe transitions
   live. If anything in the Player turn fails fast (e.g., missing task file,
   missing dep), you'll see no envelopes beyond `build-queued` until the 5-min
   deadline timer fires. Tracked as TASK-ABW-003 (bridge identity provider) and
   TASK-ABW-004 (langgraph backend persistence). **Fix in flight 2026-07-26 (F6,
   forge lane):** the failed-build terminal ledger write (a failed build
   currently shows RUNNING in `forge status`).
2. **`repo`/`branch` plumbing — now forwarded.** The dispatcher forwards `repo`
   and `branch` from `BuildQueuedPayload` into the launch payload
   (`autobuild_async.py:530-533`); the runner's branch-aware isolated-worktree
   path engages on `payload["branch"]`. `FORGE_DEFAULT_REPO` (see §0.6) remains
   only as the fallback for a launch with no `payload.repo` in scope. **AC-OPS-04
   note:** TASK-ABW-001 closed the stubbed runner — real `guardkit autobuild`
   now runs against the resolved repo cwd (no "this is a stub, no code is
   written" caveat remains true).
3. **Coach's SDK test execution may log an error and still approve.** The
   2026-05-14 preflight showed `SDK coach test execution failed (exit code 1)`
   immediately followed by `Coach approved`; tests actually pass when run via
   `pytest` directly. **This pertains to the SDK harness path.** The proven
   default is `langgraph` + the config-baked `coach-ft-v4` (the 2026-07-26
   rehearsal ran that pairing and coach-ft-v4 approved turn 1 with 0 issues).
   Cosmetic-grade log noise on the SDK path only; tracked as TASK-ABW-005.

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

> **PIPELINE retention is `workqueue` (verified against the live broker
> 2026-07-26).** Consumers on this stream must use `DeliverPolicy.NEW` semantics
> where the app builds its own consumer — `DeliverPolicy.All` is REJECTED with
> error `10101` on a workqueue stream. Server-side `Nats-Msg-Id` dedup is armed
> (`duplicate_window=120s`), so a re-published envelope inside that window is
> deduped by the broker. Do NOT purge or edit the live stream from this runbook.

---

## Phase 2: Jarvis up + chat surface ready

Pick **one** of the two front-end paths. Both have been proven green.

### 2.A OpenWebUI (visually richest)

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

**Pass:** banner renders, `>` prompt appears, boot log includes `forge_notifications_subscribed subjects=[pipeline.build-started.>, pipeline.stage-complete.>, pipeline.build-complete.>, pipeline.build-failed.>]`. Without that subscription line the §5 notification drain won't fire.

---

## Phase 3: Wire-level evidence panes (run BEFORE §4)

Open these in separate SSH/terminal panes before issuing the prompt — the envelopes land within seconds and you want them on tape from the start. Mirrors the multi-specialist runbook §3.3 pattern. **This is the pane you watch during the build** (the SILENCE LAW keeps you out of the chat, so the wire is where you follow progress).

### 3.1 Tail `pipeline.>` (captures the entire forge lifecycle)

```bash
cd ~/Projects/appmilla_github/nats-infrastructure
set -a && source .env && set +a
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "pipeline.>" --raw \
  | tee /tmp/version-demo-pipeline.log
```

**Expected during §4 (and the subsequent build window):**
1. `pipeline.build-queued.FEAT-UPT1` (jarvis publishes — within ~1s of §4.1)
2. `pipeline.build-started.FEAT-UPT1` (forge emits on dequeue — within ~5-10s)
3. `pipeline.stage-complete.FEAT-UPT1` ×N (forge emits per Player-Coach turn — N≥1, expected 1 for this 1-task feature; the rehearsal completed in one turn)
4. `pipeline.build-complete.FEAT-UPT1` (forge emits at terminal success)

All four sharing the same `correlation_id` (a fresh pipeline-side uuid; **distinct from** the jarvis-side `correlation_id` returned by `queue_build` — see the 5/13 RESULTS cross-correlation table for the two-uuid pattern).

### 3.2 Tail the inbound `agents.command.jarvis` traffic (OpenWebUI only)

Only needed if you're on path 2.A. Confirms the user prompt landed on the fleet pipe:

```bash
nats --server "nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
    sub "agents.command.jarvis" --raw \
  | tee /tmp/version-demo-command.log
```

---

## Phase 4: The demo turn — `queue_build` for FEAT-UPT1

### 4.1 The exact prompt to paste

In OpenWebUI's chat (model: Jarvis) or in the CLI `>` prompt:

```text
Queue a forge build for FEAT-UPT1 from .guardkit/features/FEAT-UPT1.yaml in appmilla/api_test on the ddd-demo branch. I want to walk through the autobuild end-to-end and see notifications come back through this chat.
```

The supervisor should:

1. Recognise the request as `queue_build` (pattern-A fire-and-forget per ADR-SP-014).
2. Construct the call: `queue_build(feature_id="FEAT-UPT1", feature_yaml_path=".guardkit/features/FEAT-UPT1.yaml", repo="appmilla/api_test", branch="ddd-demo", originating_adapter="<auto-from-session-adapter>")`.
3. Receive the `BuildQueuedPayload` ack from the JetStream publish.
4. Render a markdown-bullet reply with the `correlation_id` + `publish_target`.

**Then go silent.** This is the last chat turn you take until §5 (after
`build-complete`). Watch the §3.1 wire pane, not the chat.

### 4.2 What the reply should look like (load-bearing lines)

```text
FEAT-UPT1 has been queued for build.

- **Correlation ID:** `<uuid>`             ← capture this
- **Publish target:** `pipeline.build-queued.FEAT-UPT1`
- **Feature YAML:** `.guardkit/features/FEAT-UPT1.yaml`
- **Repo:** `appmilla/api_test`
- **Branch:** `ddd-demo`

Forge will pick it up from the JetStream PIPELINE stream. I'll surface stage-complete events as they arrive.
```

**Match these two lines as the load-bearing evidence:**
- `- **Correlation ID:** \`<uuid>\``
- `- **Publish target:**` (or `- **Target:**`) `pipeline.build-queued.FEAT-UPT1`

Prose around them varies; the two bullets are the contract per [first-real-run §6.2](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md#62-issue-the-queue-request).

**Save `<correlation_id>` from the first bullet** — call it `JARVIS_CID` (the jarvis-side request thread). A **second** `correlation_id` (the **pipeline** correlation id, call it `PIPELINE_CID`) appears on the wire envelopes captured by §3.1; the two are distinct and both worth recording. The 5/13 demo captured `JARVIS_CID=4c8c47ef-…` and `PIPELINE_CID=f29b5840-…` for FEAT-EC3C as the canonical example.

### 4.3 What's happening in the background (watch §3.1 — do NOT chat)

While the build runs, stay out of the chat (SILENCE LAW) and watch the §3.1 pane:

| Wire event | Typical latency from §4.1 | What forge is doing |
|---|---|---|
| `pipeline.build-queued.FEAT-UPT1` | <1s | Jarvis published; forge-serve consumer about to dequeue |
| `pipeline.build-started.FEAT-UPT1` | 5-10s | Forge has dequeued, run_id minted, langgraph-runner started the autobuild_runner graph |
| `pipeline.stage-complete.FEAT-UPT1` #1 | ~2-15 min | Player turn finished (wrote files), Coach turn approved (the rehearsal: coach-ft-v4 approved turn 1, 0 issues) |
| `pipeline.build-complete.FEAT-UPT1` | ~15-35 min | Terminal — feature yaml flipped to `completed`, `autobuild/FEAT-UPT1` branch ready to merge |

If `build-complete` doesn't arrive within 60 min, treat as failure mode (see §7).

---

## Phase 5: Drain notifications into the next REPL turn — AFTER build-complete

This is the visible chat payoff, and it is an **epilogue, not a mid-build move.**
Jarvis's chat handler drains `pending_notifications(session_id)` before
assembling each next reply — so the notifications flow back on the **next chat
turn you take.** Per the SILENCE LAW you take that turn only **after**
`build-complete` has landed on the §3.1 pane; a turn taken during the build
would starve the shared workhorse seat and can kill the build (F7).

### 5.1 The drain turn (take it once §3.1 shows `build-complete`)

Confirm terminal on the wire first:

```bash
grep 'pipeline.build-complete.FEAT-UPT1' /tmp/version-demo-pipeline.log
```

Then — and only then — take one chat turn in the same session to drain the
queued notifications:

```text
Has forge reported back on the FEAT-UPT1 build yet? Give me a one-line summary of what landed.
```

### 5.2 What you should see (load-bearing)

The supervisor's reply should include the drained lifecycle lines, e.g.:

```text
Forge finished the FEAT-UPT1 build. Here's what landed:

- **[HH:MM] Forge FEAT-UPT1:** build-started (run_id=<...>)
- **[HH:MM] Forge FEAT-UPT1:** stage-complete
- **[HH:MM] Forge FEAT-UPT1:** build-complete
```

The `Forge FEAT-UPT1:` lines are rendered by `ForgeNotification.render_line()`. **One or more bulleted notification lines threaded by the same `PIPELINE_CID`** = drain works = demo passes.

Cross-check against the log:

```bash
grep -E 'chat_invoke_complete.*notifications_drained=[1-9]' /tmp/jarvis-serve-nats-version-demo.log | tail -3
# CLI path: same grep against /tmp/jarvis-chat-version-demo.log
```

**Pass:** at least one `notifications_drained=N` line where `N≥1`. Because you stayed silent through the build, a single post-`build-complete` turn typically drains the whole sequence (build-started + stage-complete + build-complete) at once.

### 5.3 Inspect the built code

`build-complete` means the `autobuild/FEAT-UPT1` worktree branch in api_test now
carries the Player-Coach commits with the actual `src/uptime/` implementation.
Verify:

```bash
cd ~/Projects/appmilla_github/api_test
git fetch origin
git log --oneline origin/autobuild/FEAT-UPT1 -10 2>/dev/null \
  || git log --oneline -10 .guardkit/worktrees/FEAT-UPT1 2>/dev/null
ls -la .guardkit/worktrees/FEAT-UPT1/src/uptime/ 2>/dev/null
```

**Pass:** `src/uptime/router.py` (the `GET /uptime` handler) and `src/uptime/schemas.py` (the `UptimeResponse` model — fields `service`, `started_at`, `uptime_seconds`) exist in the worktree, on `autobuild/FEAT-UPT1`. Smoke-test:

```bash
cd ~/Projects/appmilla_github/api_test/.guardkit/worktrees/FEAT-UPT1
git status
# run the endpoint's tests
uv run --no-sync pytest tests/test_uptime.py -v
```

> **F11 forensics law (coordinator):** if the build FAILED, the kept worktree is
> **READ-ONLY** for the post-mortem. Do NOT run `guardkit autobuild` (or
> `--fresh`) inside a kept evidence worktree — it OVERWRITES the tracker yaml +
> `progress.log` and burns the autopsy. Copy evidence out; re-run only in a
> fresh worktree.

---

## Phase 6: Capture evidence

### 6.1 Save the pipeline envelopes

```bash
mkdir -p ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo
cp /tmp/version-demo-pipeline.log \
   ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${PIPELINE_CID}-pipeline.log

# Filter to just the FEAT-UPT1 envelopes for the slide
jq -c 'select(.subject | test("FEAT-UPT1"))' /tmp/version-demo-pipeline.log \
  > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${PIPELINE_CID}-feat-upt1-only.json
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
grep -A 8 "FEAT-UPT1 has been queued" /tmp/jarvis-chat-version-demo.log \
  > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/${JARVIS_CID}-queue-reply.txt
```

### 6.3 Save the chat transcript

```bash
cp /tmp/jarvis-chat-version-demo.log \
   ~/.jarvis/transcripts/${JARVIS_CID}.txt
# Or for serve-nats path, screenshot/paste the OpenWebUI thread.
```

### 6.4 Save the autobuild worktree diff (post-build, for slide)

Once `build-complete` lands:

```bash
cd ~/Projects/appmilla_github/api_test
git fetch origin
git diff origin/ddd-demo..origin/autobuild/FEAT-UPT1 -- src/uptime/ src/main.py \
  > ~/Projects/appmilla_github/jarvis/docs/runbooks/evidence/version-endpoint-demo/feat-upt1-diff.patch
```

**This is the punchline slide:** the actual code Forge wrote, framed against the `ddd-demo` source.

### 6.5 Write the RESULTS file

`docs/runbooks/RESULTS-jarvis-forge-autobuild-version-endpoint-demo-<YYYY-MM-DD>.md` mirroring this runbook's phase structure with a `Phase | Gate | Outcome | Evidence` table. Use the multi-specialist 5/13 RESULTS as the template.

---

## Phase 7: Failure modes — fast triage

| Symptom | Likely cause | Fix |
|---|---|---|
| `queue_build` returns `status: validation_error` | `feature_id` failed the `^FEAT-[A-Z0-9]{3,12}$` regex; or yaml path/branch malformed | Re-paste with `FEAT-UPT1` exactly. The regex passes `FEAT-UPT1` (4 alphanumeric chars in the tail). |
| `queue_build` returns `status: degraded` | NATS publish failed | Re-check §0.3 — auth env not sourced in this shell, or PIPELINE stream subjects don't cover `pipeline.build-queued.>`. |
| §3.1 pane shows `build-queued` but no `build-started` within 30s | Forge-prod consumer not attached, or container Exited | Re-check §0.5. `docker logs forge-prod | tail -50` will show the cause. Most common: NATS broker bounced since forge last started → restart the container. |
| Build fast-fails, no files, runner reaches for a cloud endpoint | Sidecar lost `OPENAI_BASE_URL` / `OPENAI_API_KEY` on a restart (F4, the May exit-3 wall) | Re-run the §0.6 ENV LAW `/proc/<MainPID>/environ` check; fix the unit and restart. This is the single most common silent build death. |
| §3.1 pane shows `build-started` but no `stage-complete` within 60 min | Player-Coach loop stuck (the FEAT-3CC2 timeout failure mode from Feb 2026); OR the seat was starved by a chat turn during the build (F7 — SILENCE LAW violation) | Capture forge-prod logs + the sidecar log. The build is unrecoverable mid-run — fall back to a `--fresh` re-run **in a clean worktree** (F11: never inside the evidence worktree). If a chat turn was taken during the build, that is the likely cause. |
| `stage-complete` arrives but no `build-complete` after 60 min | Player-Coach finished but terminal-publish path broke | Inspect `nats consumer info PIPELINE forge-serve -j` — if `ack_floor` advanced past the build-queued seq, forge thinks it completed. Check `.guardkit/worktrees/FEAT-UPT1/.guardkit/features/FEAT-UPT1.yaml` for the status field. Likely a forge-side bug (see §0.8 caveat 1, F6 fix in flight); file a follow-up. |
| Drain turn renders but no `Forge FEAT-UPT1:` notification line | `forge_notifications_subscribed` log line missing at boot, or the drain path silently skipped | Re-check §2's boot log for the four-subject subscription. If absent, jarvis post-F010Db disjoint filter isn't applied — capture log and stop. |
| Build fails the tier-1 gate before any code | Pass bar missing / malformed / committed after implementation (`qa.enforce_tier1`) | Re-run the §0.2a `PassBar.model_validate` check. `dependency_down_degradation` is mandatory on every bar; `registered_at` must predate the implementation commit. |
| Build fails with `PermissionError` writing to the worktree | §0.7 allowlist doesn't cover the worktree path | Edit `~/forge-state/forge.yaml` to include a parent of the api_test worktree path, `docker restart forge-prod`, re-run. |

> **F11 (coordinator law) — destructive forensics.** Re-running `guardkit
> autobuild` inside a kept evidence worktree OVERWRITES the tracker yaml +
> `progress.log` (this burned the 110453 autopsy on 2026-07-26). Post-mortems on
> kept worktrees are **READ-ONLY**. Copy evidence out and re-run only in a fresh
> worktree.

---

## Phase 8: Close

Once §4 has rendered the `queue_build` ack, the §3.1 pane has shown the full
lifecycle to `build-complete`, and §5's post-build drain turn surfaced the
notifications:

- [ ] `pipeline.build-queued.FEAT-UPT1` envelope captured in §3.1 tap with a `PIPELINE_CID`
- [ ] Supervisor's reply in §4.2 carries a `JARVIS_CID` (markdown bullet) and `Publish target: pipeline.build-queued.FEAT-UPT1`
- [ ] `pipeline.build-complete.FEAT-UPT1` observed on the §3.1 pane (no chat turns taken during the build — SILENCE LAW held)
- [ ] §5's post-`build-complete` drain turn rendered at least one `[HH:MM] Forge FEAT-UPT1: ...` notification line, threaded by `PIPELINE_CID`
- [ ] `notifications_drained=N` (N≥1) line present in the jarvis log

If all check, the run is **green**. Take down nothing on the GB10 — other work depends on the broker, llama-swap, and forge-prod.

---

## See also

- **Multi-specialist parent runbook** (Turn 3 is the forge wire this runbook specialises): [`RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md`](RUNBOOK-jarvis-multi-specialist-openwebui-dddsw-demo.md)
- **Last known-green forge wire** (FOLLOWUP-A and FOLLOWUP-B both resolved): [`RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md`](RESULTS-jarvis-multi-specialist-openwebui-dddsw-demo-2026-05-13.md)
- **Forensic first-real-run runbook** (deeper failure tables): [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Autobuild operational lessons** (worktree footgun, `--fresh` semantics): [`autobuild-orchestration.md`](autobuild-orchestration.md)
- **Feature plan output:** `api_test/.guardkit/features/FEAT-UPT1.yaml`, `api_test/tasks/backlog/uptime-endpoint/`
- **queue_build tool surface:** [`jarvis/src/jarvis/tools/dispatch.py`](../../src/jarvis/tools/dispatch.py) `queue_build` (signature + return shape)
- **ForgeNotification rendering** (the `[HH:MM] Forge FEAT-…:` line format): [`jarvis/src/jarvis/infrastructure/forge_notifications.py`](../../src/jarvis/infrastructure/forge_notifications.py)
