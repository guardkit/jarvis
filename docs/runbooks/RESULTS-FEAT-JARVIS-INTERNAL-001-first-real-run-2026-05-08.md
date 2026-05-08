# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run — Rerun (post-FEAT-PEBR merge)

**Date:** 2026-05-08
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident (host = `127.0.0.1` per `/etc/hosts`)
**correlation_id:** `5673965b-e302-4a10-89cb-ceb430e64995`
**Forge HEAD:** `e50241e` (post `5d84d94 merge(FEAT-PEBR): autobuild_runner pipeline-emitter bridge — code-only`, 2026-05-07)
**Jarvis HEAD:** `ca2ba6b` (post `dcaa8eb` lifecycle subscriber widening + `6071fe0` TASK-FRR-F010Db disjoint filter narrowing)
**Image rebuilt:** `forge:latest` = `forge:production-validation` (sha 2026-05-08 06:51)

**Outcome:** ⏸ **Same overall shape as 2026-05-04 Addendum 5** — wire e2e proven up to forge-consume + sidecar autobuild succeeds, but **no outbound lifecycle envelopes reach JetStream**. The PEBR pipeline-emitter bridge code (TASK-FRR-PEB-001…014) is merged and marked `completed`, but the **production composer (`forge.cli._serve_production.bind_production_serve`) does not compose `LifecycleBridgeWireup` / `TerminalPublishLedger`** — the daemon's own runtime log openly states this on every boot:

```
build_pipeline_consumer_deps: composed PipelineConsumerDeps
  (async_task_starter=wired, ack_bridge=deferred (TASK-FRR-PEB-002),
   terminal_publish_ledger=deferred (TASK-FRR-PEB-005))
```

**Companion documents:**
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) (2026-05-01 baseline)
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md) (2026-05-04 with five addenda — F010.A-G journey)

This file records the rerun executed after the user reported "we have implemented the two feature gaps from the last run":
1. ✅ **Forge FEAT-PEBR (autobuild_runner pipeline-emitter bridge)** — merged on 2026-05-07. Closes Gap F010.G ("autobuild_runner has no URL configured for ASGI transport") via TASK-FORGE-FRR-F010J wiring `FORGE_AUTOBUILD_RUNNER_URL` into the `AsyncSubAgent` registration. The sidecar now actually runs.
2. ✅ **Jarvis F010Db / lifecycle subscriber filter** — already shipped on 2026-05-04; verified clean boot here.

A *third* gap discovered at runtime is the headline finding: **PEBR's bridge wiring tasks (PEB-002 / PEB-005) are marked `completed` but the production composer never instantiates them**, so even with the autobuild_runner sidecar running and succeeding, no `pipeline.build-started.*` / `pipeline.stage-complete.*` / `pipeline.build-complete.*` envelopes reach JetStream.

---

## Summary in one paragraph

`queue_build` succeeded end-to-end on the wire — a `BuildQueuedPayload` was published to JetStream subject `pipeline.build-queued.FEAT-43DE`, the `forge-serve` durable consumer dequeued it, persisted a QUEUED row at `build_id=build-FEAT-43DE-20260508055823`, and dispatched the build via HTTP POST to the `langgraph-runner` sidecar at `http://localhost:8124/threads/.../runs` with `task_id=019e062a-6b8c-7be0-986c-ce9243734e22`. The sidecar's `autobuild_runner` graph executed asynchronously and **succeeded** after 37 seconds (`Background run succeeded run_completed_in_ms=37179`), driving 12 LLM calls against the local llama-swap `qwen36-workhorse` model. **But zero outbound lifecycle envelopes flowed back to JetStream**: a co-resident `nats sub "pipeline.>"` tail captured only the inbound `build_queued` envelope, no `build-started` / `stage-complete` / `build-complete`. As a side-effect, the inbound `build-queued` envelope was **never acked**, causing JetStream redelivery every 30s with the daemon emitting "duplicate active build" warnings on every redelivery (`delivered=7277, redelivered=2, ack_floor=11` on `forge-serve` consumer). Root cause: `forge.cli._serve_production.bind_production_serve` does not compose `LifecycleBridgeWireup` (the SSE→envelope translator) or `TerminalPublishLedger` into `build_pipeline_consumer_deps`; both arguments default to `None` and the deps composer correctly logs them as `deferred (TASK-FRR-PEB-002)` and `deferred (TASK-FRR-PEB-005)` even though those task files are filed under `tasks/completed/`.

## Per-phase outcomes

| Phase | Gate | 2026-05-04 (Addendum 5) | 2026-05-08 (this rerun) | Evidence |
|---|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | ✅ | top: `ca2ba6b` (history+results updated); FRR-001..004 + F010Db all in log; tree clean |
| 0.2 | GB10 reachable | ✅ (we are GB10) | ✅ (we are GB10) | `uname -a` → `Linux promaxgb10-41b1`; `/etc/hosts` 127.0.0.1 mapping |
| 0.3 | forge nats-core symlink | ✅ | ✅ | `.guardkit/worktrees/nats-core -> ../../../nats-core` resolves |
| 0.4 | env vars + llama-swap model | ✅ | ✅ with note | `JARVIS_NATS_URL` not in `.env`; sourced inline from `nats-infrastructure/.env` per runbook §0.4. `JARVIS_SUPERVISOR_MODEL=openai:qwen36-workhorse`. `JARVIS_GRAPHITI_ENDPOINT` deliberately unset (FRR-003 offload path) |
| 1.1 | NATS container up | ✅ | ✅ | `ships-computer-nats` Up 21 hours (healthy); 4222/8222 bound |
| 1.2 | 7 streams + 4 KV buckets | ✅ | ✅ | `verify-nats.sh` reports 7/0; KV inventory matches canonical 4. Stream had 1 leftover undrained envelope from 2026-05-04 20:12 (`e9433033-...`) — see Phase 7 below |
| 1.3 | `pipeline.build-queued.>` bound | ✅ | ✅ | `subjects=["pipeline.>"]`, `retention=workqueue`, `last_seq=18` pre-run / `19` post-run |
| 2.1 | forge image built (post-FEAT-PEBR) | ✅ | ✅ with same workaround | Rebuilt `forge:latest` from `e50241e` (2026-05-08 06:51, 507MB). Same `docker buildx build --build-context nats-core=../nats-core` workaround the runbook documents (forge-followup-3 still not landed) |
| 2.2 | forge serve running | ✅ + production composer + migrations + StageLogReader | ✅ + **autobuild_runner_url wired** | New env var required at boot: `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124` (see "Operator-side prerequisites" below). `bind_production_serve` succeeds; daemon log includes the canonical post-F010J line: `forge-serve: production composer bound (db_path=/home/forge/.forge/forge.db)`. **But:** the same boot log also says `composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=deferred (TASK-FRR-PEB-002), terminal_publish_ledger=deferred (TASK-FRR-PEB-005))` — the bridge is **not** wired in production |
| 2.3 | /healthz green | ✅ | ✅ | `curl http://localhost:8088/healthz` → `{"status":"healthy"}`; `consumer ls PIPELINE` shows `forge-serve` |
| 3.1 | architect container up | ⚠️ skipped | ⚠️ skipped | non-blocking: doc-only feature; matches prior runs |
| 3.2 | architect ping | ⚠️ skipped | ⚠️ skipped | n/a |
| 4.1 | graphiti/falkordb up | ⚠️ partial | ⚠️ partial (still healthy, port still shadowed by open-webui) | `graphiti-mcp` Up 19h **healthy**; `:8080` returns 200 from open-webui rather than Graphiti — same as Addendum 1 |
| 4.2 | Graphiti probe | ⚠️ | ⚠️ | left unset; relied on §8.3 offload (FRR-003 path) |
| 4.3 | embeddings reachable (llama-swap) | ✅ | ✅ | `nomic-embed` returned vector index `0` |
| 5.1 | jarvis chat boots | ✅ clean (post F010Db) | ✅ **clean** | Boot log: `nats_connect_success`, `fleet_register_published`, `forge_notifications_subscribed subjects=[pipeline.build-started.>, pipeline.stage-complete.>, pipeline.build-complete.>, pipeline.build-failed.>] correlation_cap=1000`, `jarvis_forge_subscriber_started`, `jarvis_forge_subscriber_bound_session_manager`, `jarvis_startup_complete nats_available=true graphiti_available=false capabilities_mode=live`. **Zero NATS subscription errors.** F010Db disjoint filter holds against workqueue PIPELINE alongside `forge-serve`'s `pipeline.build-queued.>` |
| 5.2 | tool inventory smoke | ✅ | ✅ | Reasoner enumerated `queue_build`, `dispatch_by_capability`, `escalate_to_frontier`, async-task surface, etc., without prompting |
| 6.2 | `queue_build` returns success | ✅ ×4 | ✅ | `correlation_id=5673965b-e302-4a10-89cb-ceb430e64995`; assistant: *"FEAT-43DE is queued for build... Correlation ID: `5673965b-...` Queued at: 2026-05-08T05:58:23Z. Publish target: `pipeline.build-queued.FEAT-43DE`. Forge will pick up the build request asynchronously. Progress events will arrive via notifications — there's nothing more to do from this side."* |
| 6.3 | message visible on PIPELINE stream | ✅ via state | ✅ via state + raw envelope | `stream info -j`: `last_seq=19, messages=2, last_ts=2026-05-08T05:58:23.879Z`. Raw `pipeline.>` tail captured the inbound envelope verbatim (`event_type=build_queued, mode=mode-a, feature_id=FEAT-43DE, correlation_id=5673965b-...`) |
| 7.1 | between-prompt notifications render full lifecycle | ✅ (build-failed terminal via F010F safety net) | ❌ **regression — zero notifications** | The Addendum 3 result that rendered `[14:38] Forge FEAT-43DE: build-failed (RuntimeError: ...)` in chat was driven by F010F's safety-net publish from `dispatch_build`'s sync raise. With FEAT-PEBR merged, F010.G closed, and the autobuild now succeeding asynchronously in the sidecar, F010F's safety net **does not fire** (no sync raise) — and the bridge that *should* publish the success/per-stage envelopes from inside the sidecar is not wired. So the chat REPL drained zero notifications |
| 7.2 | wire shows lifecycle envelope sequence on JetStream | ⚠️ partial (build-failed for sync raises) | ❌ **inbound only** | `nats sub "pipeline.>" --raw` captured **exactly 1 line** in 4 minutes of subscription — the inbound `pipeline.build-queued.FEAT-43DE` envelope my session published. Zero `pipeline.build-started.*`, zero `pipeline.stage-complete.*`, zero `pipeline.build-complete.*`, zero `pipeline.build-failed.*` |
| 7.3 | forge logs show autobuild_runner subagent launch + per-stage emit + terminal | ⚠️ reaches dispatcher | ⚠️ reaches sidecar; autobuild succeeds; **no terminal-publish path** | Forge logs (visible thanks to forge-followup-2): `dispatching build feature_id=FEAT-43DE correlation_id=5673965b-... originating_adapter=terminal **bridge=fallback**` → `persisted QUEUED row build_id=build-FEAT-43DE-20260508055823` → `httpx: POST http://localhost:8124/threads HTTP/1.1 200 OK` → `httpx: POST .../runs HTTP/1.1 200 OK` → `dispatch_autobuild_async: launched task_id=019e062a-...`. Sidecar log confirms: `Background run succeeded run_completed_in_ms=37179` for the same run_id. **No subsequent forge-side log line about a per-stage emit, build-complete publish, or ack** — because the bridge isn't composed |
| 8.1 | chat transcript saved | ✅ | ✅ | `~/.jarvis/transcripts/5673965b-e302-4a10-89cb-ceb430e64995.txt` (216KB DEBUG-level) |
| 8.2 | Graphiti routing-history dump | ⚠️ skipped | ⚠️ skipped | `JARVIS_GRAPHITI_ENDPOINT` not set; relied on §8.3 |
| 8.3 | local trace offload | ✅ | ✅ | `~/.jarvis/traces/5673965b-e302-4a10-89cb-ceb430e64995.json` (1124B; full DDR-029 schema; `outcome_type=success`, `outcome_detail.subject=pipeline.build-queued.FEAT-43DE`, `supervisor_reasoning_summary=queue_build`); `routing_history_offloaded_locally` log line emitted as expected (FRR-003 path) |
| 8.4 | `command_history.md` entry | ✅ | ⏳ | Append a 2026-05-08 section after this RESULTS file lands |

## What changed vs 2026-05-04 Addendum 5

| Source-of-truth | Addendum 5 status | 2026-05-08 status | Evidence |
|---|---|---|---|
| F010.G — autobuild_runner ASGI URL | open (sidecar in-process fallback raised `'NoneType' object is not callable'`) | **closed** via TASK-FORGE-FRR-F010J (`cad26608 fix(serve): wire FORGE_AUTOBUILD_RUNNER_URL into AsyncSubAgent registration`) | `bind_production_serve` Step 1.5 fail-fast guard rejects empty `autobuild_runner_url`; `_build_async_subagent_middleware(autobuild_runner_url=...)` threads URL through. Runtime: sidecar received POST /threads/.../runs (HTTP 200), autobuild ran 37s, succeeded |
| FEAT-PEBR (pipeline-emitter bridge code) | scope filed | **merged** (`5d84d94`, 2026-05-07; PEB-001..014 all in `tasks/completed/`) — code shipped: `lifecycle_bridge/{bridge,wireup,translation,coexistence,reconnect,recovery,version_check}.py` | Source files exist; `LifecycleBridgeWireup` class fully implemented in `src/forge/lifecycle_bridge/wireup.py` |
| Production composer wires the bridge | n/a (gap not yet visible) | **NOT wired** — see "Forge gap discovered (NEW)" below | `_serve_production.bind_production_serve` never imports `LifecycleBridgeWireup`; passes `None` for `register_ack_handle` and `terminal_publish_ledger` to `build_pipeline_consumer_deps`. Daemon boot log proves it: `ack_bridge=deferred (TASK-FRR-PEB-002), terminal_publish_ledger=deferred (TASK-FRR-PEB-005)` |

## Forge gap discovered (NEW — 2026-05-08)

**Gap PEBR-WIREUP — `bind_production_serve` does not compose the LifecycleBridge into the running daemon.**

**Symptom (forge-prod boot log, every boot):**

```
2026-05-08T05:54:02 [INFO] forge.cli._serve_deps: build_pipeline_consumer_deps:
  composed PipelineConsumerDeps
  (async_task_starter=wired,
   ack_bridge=deferred (TASK-FRR-PEB-002),
   terminal_publish_ledger=deferred (TASK-FRR-PEB-005))
```

**Symptom on the wire:** `nats sub "pipeline.>" --raw` for the duration of the rerun captured **exactly one** envelope — the inbound `pipeline.build-queued.FEAT-43DE` jarvis published. The autobuild_runner sidecar's `Background run succeeded` log line never produced any outbound `pipeline.build-started.*` / `pipeline.stage-complete.*` / `pipeline.build-complete.*` envelope on JetStream.

**Co-symptom (consumer state):** because no `register_ack_handle` is wired, the inbound `build-queued` Msg is held but never acked. JetStream's deferred-ack contract (per the original DDR-007 design and TASK-FRR-PEB-001) was meant to wait until the *terminal* lifecycle envelope before acking — but with the bridge unwired, no terminal ever fires from forge's side, so the Msg redelivers every 30s. Real consumer state at end of rerun:

```json
{
  "delivered": 7277,
  "pending": 0,
  "redelivered": 2,
  "ack_floor": 11
}
```

The `delivered=7277` count is nonsensical at first glance (only 2 envelopes were ever published into the stream during this run + 1 leftover from prior). It's the redelivery counter incrementing on every 30s `ack_wait` expiry × number of held envelopes. The `ack_floor=11` shows the consumer's ack pointer never advanced past seq 11 — the leftover envelope from 2026-05-04 20:12 (`e9433033-...`) and my new envelope at seq 19 (`5673965b-...`) are both held permanently, redelivering every 30s and producing the `dispatch_build: duplicate active build for feature_id=FEAT-43DE; skipping dispatch` warnings on every redelivery.

**Root cause (code-level):**

```python
# forge/src/forge/cli/_serve_production.py:bind_production_serve (current)
# Step 7 — build the production composer and rebind the seam.
composer = serve_module.bind_production_dispatch_chain(
    forge_config=forge_config,
    sqlite_pool=sqlite_pool,
    async_task_starter=async_task_starter,
)
serve_module.compose_dispatch_chain = composer
```

There is **no Step 6.5** that constructs a `LifecycleBridgeWireup`, derives the `register_ack_handle` Protocol, derives the `TerminalPublishLedger`, and threads them into `bind_production_dispatch_chain` — even though `_serve_deps.build_pipeline_consumer_deps` already accepts both as named parameters and the bridge code (PEB-002 / PEB-003 / PEB-005) is fully implemented with passing unit tests. The "deferred" log line is a pre-baked operator hint that the production composer is the missing link — the underlying machinery is ready and the deps composer would happily wire it, but `bind_production_serve` simply doesn't.

**Why FEAT-PEBR's tests didn't catch this:** PEB-001..014 are unit + contract tests against the bridge components in isolation. PEB-013 ("sidecar-aware-e2e-integration-test") is the test that *would* have caught the production-composer gap — the test name implies it exercises the full sidecar→bridge→JetStream path — but it must have been written against an in-test composer that *does* construct `LifecycleBridgeWireup`, not against `bind_production_serve` itself. The pattern is identical to the F010 family of gaps (TASK-FIX-F010 caught precisely this — `serve_cmd` not rebinding the production composer; this gap is the same shape one layer deeper).

**Fix shape (indicative, single function):**

```python
# Inside bind_production_serve, after Step 5 (middleware) and before Step 7:
from forge.lifecycle_bridge.wireup import LifecycleBridgeWireup
from forge.lifecycle_bridge.langgraph_stream_source import (
    langgraph_stream_source,  # PEB-005 ships this
)
# ...
publisher = build_pipeline_publisher(forge_config)             # already exists
ledger = TerminalPublishLedger(connection=connection)          # PEB-005 type
bridge = LifecycleBridge.from_sqlite_pool(sqlite_pool)         # PEB-002 type
stream_source = langgraph_stream_source(
    runner_url=config.autobuild_runner_url,                    # already validated non-empty
)
wireup = LifecycleBridgeWireup(
    bridge=bridge,
    publisher=publisher,
    stream_source=stream_source,
    terminal_publish_ledger=ledger,
)

composer = serve_module.bind_production_dispatch_chain(
    forge_config=forge_config,
    sqlite_pool=sqlite_pool,
    async_task_starter=async_task_starter,
    register_ack_handle=wireup.register_ack_handle,            # ← the missing wire
    terminal_publish_ledger=ledger,                            # ← the missing wire
)
```

…plus a graceful-shutdown hook calling `await wireup.shutdown(timeout=5.0)` from `_run_serve`'s SIGTERM handler. The exact module/factory imports are subject to whatever PEB-005 actually exposed for the production stream-source factory — audit the wireup module's public API.

Then add the missing integration test (most likely the canonical home is `tests/forge/cli/test_serve_production_seam.py` or similar, matching TASK-FIX-F010's regression-test home) that asserts:

1. `bind_production_serve(...)` produces a daemon where `_serve_deps.build_pipeline_consumer_deps`'s call has both `register_ack_handle` and `terminal_publish_ledger` set to non-None values.
2. Boot log does NOT contain the substring `deferred (TASK-FRR-PEB-002)` or `deferred (TASK-FRR-PEB-005)` — these strings should fail the test, locking the bind.

This is the test that would have caught Gap PEBR-WIREUP, and it's the test PEB-013 was supposed to be — audit whether PEB-013 actually invokes `bind_production_serve` end-to-end or only constructs a hand-rolled composer.

## Operator-side prerequisites discovered (NEW)

The runbook needs three new prerequisites folded for the post-FEAT-PEBR shape:

### Prerequisite A — Sidecar config + langgraph dev process

`forge serve` will refuse to boot without `FORGE_AUTOBUILD_RUNNER_URL` (TASK-FORGE-FRR-F010J fail-fast guard). The URL must point at a running `langgraph-runner` sidecar that exposes the `autobuild_runner` graph. Bring it up before `forge serve`:

```bash
cd ~/Projects/appmilla_github/forge && \
nohup .venv/bin/langgraph dev \
  --config forge.langgraph.json \
  --port 8124 --host 0.0.0.0 \
  --no-browser --allow-blocking --no-reload \
  > /tmp/sidecar.log 2>&1 &
```

`forge.langgraph.json` registers **only** `autobuild_runner` (the default `langgraph.json` also registers `orchestrator`, which fails to import — `No module named 'agents'`).

### Prerequisite B — Forge venv must have the `[providers]` extras installed

`autobuild_runner` graph imports use `init_chat_model` which needs `langchain-openai` (and on the canonical setup also `langchain-google-genai`). On a fresh forge venv these aren't installed; the sidecar emits a placeholder graph at boot if missing:

```
WARNING __src__forge__subagents__autobuild_runner: autobuild_runner: create_deep_agent
  raised Initializing ChatOpenAI requires the langchain-openai package. Please install
  it with `pip install langchain-openai` — exporting placeholder graph so langgraph.json
  still parses; investigate the underlying cause before relying on the subagent
```

Install before bringing the sidecar up:

```bash
~/Projects/appmilla_github/forge/.venv/bin/pip install \
  "langchain-openai>=1.2,<2" "langchain-google-genai>=4.2,<5"
```

### Prerequisite C — `forge serve` Docker run needs the new env var

```bash
docker run -d --name forge-prod \
  --network host \
  -e FORGE_NATS_URL="nats://rich:${RICH_NATS_PASSWORD}@localhost:4222" \
  -e FORGE_HEALTHZ_PORT=8088 \
  -e FORGE_LOG_LEVEL=info \
  -e FORGE_AUTOBUILD_RUNNER_URL="http://localhost:8124" \   # ← NEW (post-F010J)
  -v ~/forge-state:/var/forge \
  -v ~/forge-state/forge.yaml:/home/forge/forge.yaml:ro \
  -v ~/Projects/appmilla_github/jarvis:~/Projects/appmilla_github/jarvis:ro \
  forge:latest serve
```

These three need folding into runbook §2 before the next walkthrough — flag for TASK-FRR-RUNBOOK-PEBR-FOLD.

## Decision

- [ ] Phase 3 closed canonical
- [x] **Phase 3 closed with gap-folds (forge-side gap remaining)** — Every gap from Addendum 5 (F010.G + jarvis F010Db) is closed and verified by this rerun. The autobuild_runner sidecar dispatch path now functions end-to-end up to and including a successful background run. **The remaining gap is forge-side, freshly discovered, and one-task-deep**: `bind_production_serve` doesn't compose `LifecycleBridgeWireup` so the SSE→envelope translation never runs, no outbound lifecycle envelopes reach JetStream, and the inbound `build-queued` Msg is never acked. Once Gap PEBR-WIREUP closes, the next rerun should produce the canonical `build-started + stage-complete*N + build-complete` sequence on the wire and as rendered chat lines.
- [ ] Partial — single-phase failure with follow-up task

## Recommended follow-ups

1. **forge — Gap PEBR-WIREUP (NEW):** In `forge.cli._serve_production.bind_production_serve`, instantiate `LifecycleBridgeWireup` (with the bridge, publisher, stream-source, and terminal-publish-ledger PEB-005 ships) and thread `wireup.register_ack_handle` + `terminal_publish_ledger` into `bind_production_dispatch_chain(...)`. Add the missing seam test (most likely home: `tests/forge/cli/test_serve_production_seam.py`) that asserts the deps composer's runtime log does NOT contain `deferred (TASK-FRR-PEB-002)` or `deferred (TASK-FRR-PEB-005)`. This is the regression-protection test that would have caught the gap. Audit TASK-FRR-PEB-013 ("sidecar-aware-e2e-integration-test") — confirm whether it actually exercises `bind_production_serve` or a hand-rolled composer; if the latter, that's why the gap shipped through.
2. **runbook (TASK-FRR-RUNBOOK-PEBR-FOLD):** Fold Prerequisites A, B, C from this RESULTS into runbook §2 (forge image build / serve startup). The post-FEAT-PEBR shape requires a langgraph-runner sidecar running ahead of the daemon, the forge venv must have `[providers]` extras, and the daemon needs `FORGE_AUTOBUILD_RUNNER_URL`. None of these are documented in the current runbook §2.
3. **forge:** Fix `scripts/build-image.sh` cwd / build-context path so the runbook can revert from the manual `docker buildx build` workaround to a single-line invocation (forge-followup-3 from 2026-05-01; not yet landed; trivial fix).
4. **MacBook over Tailscale walkthrough:** still deferred. Until (1) lands, the MacBook walkthrough can only re-prove what GB10 already proved (publish → consume + ack-deferred); there's no new evidence in the network-isolated rerun until the stage-complete round-trip is structurally satisfiable. Re-evaluate when (1) closes.

## Cross-machine state observed

- **NATS** (`ships-computer-nats`, host-network): up 21h healthy, 7 canonical streams + 4 KV buckets present. Two leftover undrained `pipeline.build-queued.FEAT-43DE` envelopes on the workqueue PIPELINE — the 2026-05-04 20:12 envelope (`e9433033-...`) and this rerun's envelope (`5673965b-...`). Both will redeliver indefinitely until Gap PEBR-WIREUP closes (deferred-ack never fires its terminal trigger).
- **forge-prod** (host-network, `forge:latest` rebuilt 2026-05-08 06:51, 507MB, post-`e50241e`): up healthy, durable consumer attached, production composer bound, `autobuild_runner_url` validated, **but `ack_bridge` and `terminal_publish_ledger` deferred at runtime**.
- **langgraph-runner sidecar** (host process, port 8124): up via `langgraph dev`; `autobuild_runner` graph loaded successfully (no placeholder) after `langchain-openai` was installed into forge's venv. Successfully ran two autobuilds during this rerun (the leftover `e9433033-...` build at 05:54 and our new `5673965b-...` build at 05:58–05:59), each ~34–37 seconds end-to-end against `qwen36-workhorse` on llama-swap. Both `Background run succeeded` confirmed in sidecar log.
- **graphiti-mcp**: up 19h healthy. `:8080` returns open-webui's HTML rather than Graphiti — same shadow as Addendum 1; not exercised; relied on §8.3 offload.
- **open-webui**: up host-network on 8080 (drives the `FORGE_HEALTHZ_PORT=8088` override).
- **llama-swap**: up via systemd, serving on `:9000` with `gemma4-tutor`, `nomic-embed`, `qwen-graphiti`, `qwen36-workhorse`. Used `qwen36-workhorse` for both the supervisor and the autobuild_runner subagent.

## Evidence files

All under `/tmp/runbook-evidence-2026-05-08/`:

- `phase1.1-compose-ps.log`, `phase1.2-verify-nats.log`, `phase1.2-kv-ls.log`, `phase1.3-pipeline-info.json`
- `phase2.1-build-image.log`, `phase2.1-images.log`, `phase2.2-docker-run.log`, `phase2.2-forge-logs.log`, `phase2.3-healthz.json`, `phase2.3-consumers.log`
- `phase3.1-specialist.log` (empty — no containers; expected)
- `phase4.1-graphiti.log`, `phase4.2-graphiti-probe.log`, `phase4.3-embeddings.log`
- `phase5-toolinv.log` (clean boot smoke + tool inventory)
- `phase6-7-chat.log` (full DEBUG-level chat transcript — the post-`queue_build` REPL session)
- `phase6.3-stream-state.json`, `phase7-pipeline-tail.log` (raw `nats sub "pipeline.>"` capture — exactly 1 line, the inbound `build_queued` envelope)
- `phase7-forge-logs.log` (forge daemon log filtered to the rerun timestamps and our correlation_id)
- `phase7-consumer-info.json` (`forge-serve` consumer state showing `delivered=7277, redelivered=2, ack_floor=11`)
- `sidecar.log` (langgraph-runner sidecar log including both `Background run succeeded` lines)
- Transcript copy: `~/.jarvis/transcripts/5673965b-e302-4a10-89cb-ceb430e64995.txt` (216KB)
- Routing-history offload (FRR-003): `~/.jarvis/traces/5673965b-e302-4a10-89cb-ceb430e64995.json` (1124B; full DDR-029 schema)
