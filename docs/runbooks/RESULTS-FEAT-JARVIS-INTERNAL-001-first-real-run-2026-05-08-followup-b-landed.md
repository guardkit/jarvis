# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run — wave 3, FOLLOWUP-B-FIX landed

**Date:** 2026-05-08 (~17:29 → ~17:43 BST / 16:29 → 16:43 UTC)
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident, executed directly on host (SSH prefixes dropped per §0.2)
**Operator:** Claude (assistant-driven, runbook-following — full teardown then rebuild against current main)
**Jarvis HEAD:** `5fb4159` (`build(deps): bump nats-core floor to >=0.4 (v0.4.0)`)
**Forge HEAD:** `1b04b89` — includes FOLLOWUP-A migration (`55f7804`), PEBR-WIREUP (`1b82236`), and **FOLLOWUP-B-FIX (`b9e9585` — "wire async_tasks channel into autobuild_runner StateGraph")**, plus the spike-instrumentation removal that came with `b9e9585`.
**Forge image:** `forge:latest` (rebuilt fresh during this run; sha `c0275b3df2c8`)
**Specialist-agent HEAD:** `82ce8a6` (nats-core 0.4 bump landed in main); architect/PO containers still running pre-bump image (Up 10h) — not exercised by FEAT-JARVIS-INTERNAL-001 (mode B / documentation-only) so not blocking.
**correlation_id:** `10c80f94-ce1f-41bf-97e5-50b5d67faba5`
**Session id:** `cli-ff6ffa2247fc45ea844657de598fbfcb`

**Outcome:** ⏸ **Phases 0–6 GREEN; Phase 7 FAILs with a NEW signature ("Signature C") not anticipated by the runbook.** FOLLOWUP-B-FIX's wiring is verified live — the daemon boots with `composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired)`, FOLLOWUP-A migration applies cleanly, and the autobuild_runner StateGraph (from `b9e9585`) executes successfully end-to-end inside `langgraph dev` (`Background run succeeded`, `run_exec_ms=16`). **But** the placeholder lifecycle node bodies that landed alongside the fix execute so fast (~16 ms) that by the time forge-prod's bridge GETs `langgraph_sdk.runs.join_stream`, the run has already completed — and `join_stream` against a finished run returns an empty stream rather than replaying buffered values. Result: **zero outbound `pipeline.*` envelopes** on the wire, even though the state-shape contract is now satisfied at the runner side.

This is **not** the wave-3 success criterion the runbook anticipated (`build-started → stage-complete×N → build-complete/build-failed`). It is, however, exactly the surface the FOLLOWUP-B-FIX commit message flagged when it deferred AC-3: *"AC-3 end-to-end runbook revalidation: deferred — gated on a fresh forge:latest image rebuild + runbook re-run."* This run is that revalidation, and it surfaces the next-after-FOLLOWUP-B gap.

---

## What this run did differently from the 2026-05-08 fresh-followup-b-instrumented run

The earlier same-day run ([`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md)) ran against forge HEAD `e1eef81` — the FOLLOWUP-B *spike* (instrumented but no behavioural fix). This run executed against forge HEAD `1b04b89`, which **includes the FOLLOWUP-B-FIX commit `b9e9585`** that:

* dropped `create_deep_agent` from the autobuild_runner and built a 4-node `StateGraph` directly so `async_tasks` can live in the state schema,
* wired `_update_state` / `LifecycleEmitterAdapter` / `AutobuildState` / `StateChannelWriter` into the runner (these were dormant pre-fix),
* added `LIFECYCLE_TO_PIPELINE_EMIT` mapping (`completed→emit_complete`, `failed→emit_failed`, `awaiting_approval→emit_paused`, etc.),
* added the four placeholder node bodies (`_node_starting`, `_node_planning_waves`, `_node_running_wave`, `_node_completed`) that walk the lifecycle progression but do no real autobuild work,
* and **removed** the spike instrumentation in `forge.lifecycle_bridge.translator` / `wireup` that produced the `stream_part received n=N event='values' data_keys=…` logs the prior run captured.

Teardown executed cleanly:

| Component | Action |
|---|---|
| `forge-prod` container | `docker rm -f` |
| `~/forge-prod-state/.forge/forge.db*` | wiped — bridge_registry migration applied fresh on first boot (`applied 2 SQLite migration(s) at boot`) |
| `langgraph dev` sidecar | killed; `~/Projects/appmilla_github/forge/.langgraph_api/` cleared |
| `forge-serve` durable consumer on PIPELINE | deleted via `nats consumer rm PIPELINE forge-serve` |
| PIPELINE stream messages | `nats stream purge PIPELINE -f` (cleared 1 leftover redelivery from the prior run, where `delivered=385, ack_floor=0`) |
| Forge image | **rebuilt** from current main via `docker buildx build --build-context nats-core=../nats-core -t forge:latest -t forge:production-validation -f Dockerfile .` — produced sha `c0275b3df2c8`, ~507 MB, ~80 s build |
| NATS server, KV buckets, specialist-agent containers, graphiti-mcp, llama-swap | left running |

---

## Per-phase outcomes

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | jarvis HEAD `5fb4159`; clean tree |
| 0.2 | GB10 reachable | ✅ | `hostname=promaxgb10-41b1`; SSH prefix dropped per §0.2 |
| 0.3 | forge nats-core symlink | ✅ | symlink already in place |
| 0.4 | provider keys + NATS auth + supervisor model | ✅ | `JARVIS_SUPERVISOR_MODEL=openai:qwen36-workhorse`; `JARVIS_NATS_URL` constructed inline from sourced `nats-infrastructure/.env` |
| 1.1 | NATS container up | ✅ | `ships-computer-nats Up 32 hours (healthy)` |
| 1.2 | 7 streams + 4 KV buckets | ✅ | `verify-nats.sh` reports `7 passed, 0 failed`; `nats kv ls` shows all 4 buckets |
| 1.3 | `pipeline.build-queued.*` bound to PIPELINE | ✅ | `Subjects: pipeline.>` (host-side `nats` CLI; runbook's `docker exec ... nats` pattern fails on this host — see W3-D below) |
| 2.0 | langgraph-runner sidecar | ✅ | Pre-flight 1 (kill + clear `.langgraph_api/`) ran; pre-flight 2's stripped config already on disk; sidecar booted on `:8124`; `Application started up in 0.159s`; `n_pending=0` (clean queue); openapi probe returned `"LangSmith Deployment"`; graph profile resolved at `./src/forge/subagents/autobuild_runner.py:graph` (the new StateGraph) |
| 2.1 | forge image rebuilt | ✅ | rebuilt from current main `1b04b89`; new sha `c0275b3df2c8`, `forge:latest` + `forge:production-validation` |
| 2.2 | `forge serve` running against new image | ✅ | Container booted with `--config /var/forge/forge.yaml`, `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124`, host-mounted DB at `/home/forge/.forge`. Boot signature: `applied 2 SQLite migration(s) at boot` (FOLLOWUP-A) + `production composer bound (db_path=/home/forge/.forge/forge.db)` + `composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired)` + `dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher` (PEBR-WIREUP) |
| 2.3 | `/healthz` green + consumer attached | ✅ | `{"status":"healthy"}` on `:8088`; fresh `forge-serve` durable on PIPELINE (created 2026-05-08 17:34:09, 0 ack-pending, 0 unprocessed) |
| 3.1 | architect container up | ✅ | `specialist-agent-architect-agent-1 Up 10 hours` + `specialist-agent-product-owner-agent-1 Up 10 hours`. Note: containers predate the `82ce8a6` nats-core 0.4 bump on specialist-agent main, but FEAT-JARVIS-INTERNAL-001 dispatches no specialist work, so not exercised. |
| 3.2 | architect ping (optional) | ⚠️ skipped (FEAT-JARVIS-INTERNAL-001 mode B is documentation-only) |
| 4.1 | graphiti container up | ✅ | `graphiti-mcp Up 30 hours (healthy)` |
| 4.2 | Content-Type-guarded graphiti probe | ⚠️ HTML hijack (open-webui on :8080) — DDR-019 soft-fail offload path engaged as expected on GB10 |
| 4.3 | llama-swap embeddings | ✅ | `nomic-embed` returned `data[0].index = 0` |
| 5.1 | jarvis chat boots clean | ✅ | `jarvis_startup_complete` with `nats_available=true, capabilities_mode=live`, **zero `nats_*` warnings**. Two documented soft-fails reproduced (TAVILY_API_KEY + `graphiti_skipped_no_endpoint`). Evidence: [`/tmp/jarvis-runbook-evidence/phase5-boot.log`](/tmp/jarvis-runbook-evidence/phase5-boot.log) |
| 5.2 | tool inventory smoke | ✅ | Supervisor narrated `forge` capability + `dispatch_by_capability`, plus 9 ambient tools |
| 6.1 | Boot fresh chat REPL with full tracing | ✅ | Non-interactive `printf | jarvis chat` pattern, `JARVIS_LOG_LEVEL=DEBUG`. Exit code 0 |
| 6.2 | `queue_build` returns success | ✅ (with narration variance) | Supervisor returned an **inline-prose** ack rather than the runbook's documented bullet shape: *"FEAT-43DE is queued for build. Correlation ID: \`10c80f94-ce1f-41bf-97e5-50b5d67faba5\`. Forge will pick it up from the JetStream topic \`pipeline.build-queued.FEAT-43DE\`."* The two load-bearing strings (correlation_id UUID + `pipeline.build-queued.FEAT-43DE` subject) are present; the runbook's example bullets (`- **Correlation ID:**`, `- **Target:**`/`- **Publish target:**`) are absent. See W3-C below. Evidence: [`/tmp/jarvis-runbook-evidence/phase6-chat-narration.txt`](/tmp/jarvis-runbook-evidence/phase6-chat-narration.txt) |
| 6.3 | Wire shows publish on PIPELINE | ✅ | Wire-tap captured exactly 1 `BuildQueuedPayload` (760 B). PIPELINE last_seq advanced 22 → 23. Pre-publish consumer baseline `delivered=0, ack_floor=0, pending=0, redelivered=0` |
| 7.1 | Between-prompt notification narration | ✅ (in form — narration matches expected wave-2/3 FAIL framing) | Supervisor follow-up to "What is happening with that build?" narrated awareness that no events have arrived: *"I don't have a direct tool to poll the Forge pipeline status in real-time, but I can check if there are any notifications…"* — exactly the runbook's expected behavior on a Phase 7 FAIL (chat REPL drains zero notifications and reasoner narrates accordingly) |
| 7.2 | Wire shows envelope sequence | ❌ **expected FAIL — new "Signature C"** | Across a 6m+ capture window: **1 inbound `BuildQueuedPayload`, 0 outbound `pipeline.build-started.*` / `stage-complete.*` / `build-complete.*` / `build-failed.*` envelopes**. Final consumer state: `delivered=14, ack_floor=0, num_pending=0, num_redelivered=1`. `ack_floor` never advanced — same fail fingerprint as wave-2 Signature B at the consumer level, but with a fundamentally different forge-side log story (see "Signature C forge log story" below) |
| 7.3 | Forge logs show autobuild flow | ❌ **expected FAIL — new "Signature C"** | Bridge attaches cleanly; dispatch chain composes cleanly; `langgraph dev` queues, runs, and **completes** the autobuild in 16 ms; bridge GETs the SSE stream ~1 s later and observes zero events because `join_stream` does not replay completed runs. See "Signature C forge log story" below. **Also new: the spike instrumentation that wave-2 captured (`stream_part received n=N event='values' data_keys=…`) is gone in `b9e9585` — `docker logs forge-prod` no longer surfaces per-part visibility, so the failure is observable only via the wire-tap + LangGraph sidecar log + a direct curl probe of `join_stream`.** |
| 8.1 | Save chat transcript | ✅ | `~/.jarvis/transcripts/10c80f94-ce1f-41bf-97e5-50b5d67faba5.txt` (382 KB DEBUG-level transcript copied from `/tmp/jarvis-runbook-evidence/phase6-chat.log`) |
| 8.2 | Graphiti routing-history dump | N/A (Graphiti port hijacked — soft-fail offload path) |
| 8.3 | DDR-019 offload trace | ✅ | `~/.jarvis/traces/10c80f94-ce1f-41bf-97e5-50b5d67faba5.json` — full DDR-029 routing-history schema with `outcome_type=success`, `outcome_detail.subject=pipeline.build-queued.FEAT-43DE`, `subagent_final_state=success` |
| 8.4 | command_history.md | ✅ (this run appended) |

---

## Decisive evidence for Phase 7 expected FAIL (Signature C)

### Final wire state (after 6m+ post-publish window)

```json
{ "delivered": 14, "ack_floor": 0, "pending": 0, "redelivered": 1 }
```

(`/tmp/jarvis-runbook-evidence/phase7-final-consumer-info.json`)

`ack_floor=0` is the same load-bearing fingerprint as wave-2 — JetStream redelivered the inbound message 13 times after the original delivery without ever seeing a terminal ack from forge.

### Wire-tap content (`pipeline.>` for ~6m)

```json
{
  "message_id": "7487f1e5-fd4f-40e5-8ed7-b11e95e98ae3",
  "timestamp": "2026-05-08T16:35:59.770861Z",
  "version": "1.0",
  "source_id": "jarvis",
  "event_type": "build_queued",
  "correlation_id": "10c80f94-ce1f-41bf-97e5-50b5d67faba5",
  "payload": { "feature_id": "FEAT-43DE", "repo": "guardkit/jarvis", "branch": "main", ... }
}
```

(one and only one envelope; zero `build-started` / `stage-complete` / `build-complete` / `build-failed` follow-ups)

### Direct curl probe of `join_stream` against the completed run

```text
$ curl -N --max-time 8 "http://localhost:8124/threads/<thread>/runs/<run>/stream?cancel_on_disconnect=false&stream_mode=values"
(returns immediately with empty body — no SSE events at all)
```

This is the smoking gun for Signature C: `langgraph dev`'s `client.runs.join_stream` does **not** replay buffered values for an already-completed run. It returns an empty async iterator and closes the connection. The bridge's `_drive_stream_session` consumes those zero events, the translator's `_extract_state` is never called, and the observer reaches its "stream ended without a terminal envelope" branch.

---

## Signature C forge log story

This run's forge log signature is **substantially leaner** than the runbook's wave-2 Signature B, because forge HEAD `1b04b89` removed the spike instrumentation that gave per-part visibility. Below is the entire log content for one dispatch cycle (the rest of the cycles are byte-identical modulo timestamps and the `duplicate active build` skip):

```text
17:34:09 forge.cli._serve_production: forge-serve: applied 2 SQLite migration(s) at boot
17:34:09 forge.cli._serve_production: forge-serve: production composer bound (db_path=/home/forge/.forge/forge.db)
17:34:09 forge.cli._serve_deps: build_pipeline_consumer_deps: composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired)
17:34:09 forge.cli.serve: forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)
17:34:09 forge.cli._serve_healthz: healthz server listening on 0.0.0.0:8088 (durable=forge-serve)

17:35:59 forge.lifecycle_bridge.bridge: lifecycle_bridge.attach feature_id=FEAT-43DE correlation_id=10c80f94-… thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE
17:35:59 forge.lifecycle_bridge.wireup: wireup.register_ack_handle: attached … observer task scheduled (deadline_at=17:40:59)
17:35:59 forge.adapters.nats.pipeline_consumer: pipeline_consumer: dispatching build feature_id=FEAT-43DE … bridge=wired
17:35:59 forge.cli._serve_deps: dispatch_build: persisted QUEUED row build_id=build-FEAT-43DE-20260508163559 …
17:35:59 forge.pipeline.dispatchers.autobuild_async: dispatch_autobuild_async: launched task_id=019e0872-28cd-72e1-81d1-d47b704d5746 …

17:36:00 httpx: HTTP Request: GET http://localhost:8124/threads/<thread>/runs/<run>/stream?cancel_on_disconnect=false&stream_mode=values "HTTP/1.1 200 OK"
17:36:01 forge.lifecycle_bridge.wireup: wireup._observer_loop: stream for feature_id=FEAT-43DE ended without a terminal envelope; leaving inbound queued message un-acked (JetStream will redeliver, deadline timer will publish build-failed if the sidecar stays unreachable)
```

**Critical observations:**

* **`PipelineConsumerDeps` boot line is NEW vs wave-2** — it surfaces FOLLOWUP-B-FIX's dep-composition handshake (`async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired`). Wave-2 had no equivalent line. This is the most direct fingerprint that the new image is in production.
* **No `register_ack_handle raised (no such table)` warning** anywhere — FOLLOWUP-A continues to hold (consistent with the prior fresh-followup-b-instrumented run).
* **No `stream_part received n=N event=…` lines** — the spike instrumentation from `e1eef81` was removed by `b9e9585`. Wave-2's per-part fingerprint is no longer observable from `docker logs forge-prod`; you have to read the langgraph-sidecar log (or curl `join_stream` yourself) to see what the bridge sees.
* **`HTTP/1.1 200 OK` on the SSE GET** — the sidecar is reachable; this is unambiguously not the deadline-timer's "stream unreachable" branch.
* **`stream ended without a terminal envelope`** fires ~1 second after dispatch — i.e. the bridge's stream session opens, receives zero values events, and closes cleanly, without ever observing an `async_tasks` snapshot.

### LangGraph sidecar log story (NEW evidence surface, not previously load-bearing)

`/tmp/jarvis-runbook-evidence/langgraph-sidecar.log` shows the autobuild_runner StateGraph executing successfully:

```text
17:35:59 langgraph_api.models.run: Created run run_id=019e0872-28d0-7d30-9624-f6e8a3aa5710 stream_mode=['values']
17:36:00 langgraph_api.worker: Starting background run … run_queue_ms=918 …
17:36:00 langgraph_api.worker: Background run succeeded run_completed_in_ms=936 run_exec_ms=16
```

**`run_exec_ms=16`** is the load-bearing finding: the four placeholder lifecycle nodes (`_node_starting → _node_planning_waves → _node_running_wave → _node_completed`) execute in 16 milliseconds total. The sidecar's `client.runs.join_stream` API does not buffer or replay these values for late subscribers — by the time forge-prod's bridge connects, the run is over and the stream is empty.

### Deadline timer also did not fire (5 min observation window)

The 17:35:59 cycle's observer was scheduled with `deadline_at=17:40:59`. Tail of `docker logs forge-prod` covering 17:40:59 → 17:41:30 contains only the next redelivery cycle's `register_ack_handle: attached` + `dispatching build` + `duplicate active build … skipping dispatch` + `stream ended without a terminal envelope` — **no `deadline expired` / `publishing build-failed`** entry. This confirms the runbook's §7.1 "Signature B refinement" caveat: *"the deadline path is gated on SSE stream unreachability — not on stream silence. With a reachable-but-translator-silent stream … the deadline expires without any terminal envelope being published."* Today's stream is reachable-but-completed-before-we-listened, which is functionally equivalent to silence at the bridge translator boundary. Wave-3 fold candidate W3-B from the prior run carries forward unchanged.

### Counts across the full 7m session window (97 → 111 forge log lines)

| Marker | Count |
|---|---|
| `lifecycle_bridge.attach` | 7 (1 initial + 6 redelivery) |
| `wireup.register_ack_handle: attached` | 7 |
| `httpx: GET …/stream "HTTP/1.1 200 OK"` | 6 |
| `stream ended without a terminal envelope` | 7 |
| `duplicate active build for feature_id=FEAT-43DE` | 6 (every redelivery cycle after cycle 1) |
| `dispatch_build: persisted QUEUED row` | 1 (cycle 1 only) |
| `applied 2 SQLite migration(s) at boot` | 1 ✅ FOLLOWUP-A live |
| `composed PipelineConsumerDeps … wired` | 1 ✅ FOLLOWUP-B-FIX live |
| `dispatch chain composed … rebound` | 1 ✅ PEBR-WIREUP live |
| `register_ack_handle raised (no such table)` | **0** ✅ Signature A fully resolved |
| `stream_part received n=N` | **0** (instrumentation removed by `b9e9585`) |
| `publish.*pipeline\.(build|stage)` | **0** |
| `emit_*` | **0** |

---

## What this run validates (vs the prior fresh-followup-b-instrumented run)

1. **FOLLOWUP-B-FIX is in production** — the boot line `composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired)` is unique to `b9e9585`+ and proves the dep-composition path landed. The fresh image (sha `c0275b3df2c8`, built during this run) was the gate — pre-rebuild, the running container was on `91ec9638963c` which predates the fix.
2. **FOLLOWUP-A migration continues to hold** — fresh DB, `applied 2 SQLite migration(s) at boot`, zero `no such table: lifecycle_bridge_registry` warnings under 7 dispatch attempts.
3. **PEBR-WIREUP continues to hold** — same `dispatch chain composed; _serve_daemon.dispatch_payload rebound …` boot line as wave-2.
4. **The autobuild_runner StateGraph executes** — `Background run succeeded` from `langgraph dev`, `run_exec_ms=16`, full `starting → planning_waves → running_wave → completed` lifecycle progression in placeholder bodies. The state-shape contract this fix established (DDR-006 `async_tasks` channel keyed by `feature_id`, walked via `_snapshot_update`) is observably wired end-to-end inside the sidecar.
5. **Operator runbook is verbatim-runnable for Phases 0–6** — 0 manual gap-folds during execution. The wave-2 §2.0 pre-flights (kill + clear `.langgraph_api/`) prevented the qwen36-workhorse contention failure mode.

---

## What this run reveals beyond the runbook's documented expectations

### Signature C — `join_stream` race against placeholder-fast completion

The runbook's wave-3 success criterion (and §7.2 expected envelope sequence) assumed that landing FOLLOWUP-B's translator/runner contract fix would let the existing bridge↔sidecar wiring observe lifecycle transitions and publish envelopes. **The actual gap is one layer deeper:**

* The runner produces `async_tasks` snapshots correctly (`b9e9585` proves this in unit tests + the live `Background run succeeded` log line).
* The translator can interpret those snapshots correctly (existing `_extract_state` reads `data["async_tasks"][feature_id]` and the contract is satisfied; tests in `tests/forge/lifecycle_bridge/test_translation_contract.py` cover this).
* The bridge's stream source uses `langgraph_sdk.runs.join_stream(thread_id, run_id, stream_mode="values")` to subscribe to the run's value events.
* **`join_stream` is a *live* SSE subscription, not a *replay* of a completed run's history.** Direct curl evidence (above) shows that against an already-completed run, `join_stream` returns an empty stream and closes immediately. With placeholder bodies executing in 16 ms, the run is essentially always already complete by the time the bridge subscribes.

The fix surface for Signature C (a wave-3-after-this follow-up) is at least one of these:

| Location | Possible fix | Tradeoff |
|---|---|---|
| `forge.lifecycle_bridge.stream_source` | Switch from `runs.join_stream` to a replay-capable API. `langgraph_sdk` 0.3.14 exposes `runs.join` (returns final state) and `runs.list` / `threads.get_state_history` (snapshots) — combine to reconstruct the value sequence for completed runs. Or open the stream **before** dispatching the run rather than after. | The "open before dispatch" option requires changing the dispatcher to coordinate with the bridge before the run is created; the "replay via state history" option couples the bridge to a different SDK surface. |
| `forge.subagents.autobuild_runner` | Make placeholder bodies async-sleep briefly between transitions so the run takes longer than the dispatch→subscribe gap (~1 s on this hardware). | Synthetic delay is tech-debt; it would also collide with real bodies once they land. |
| `langgraph dev`-side | Configure the runtime so completed runs' values stay buffered for late subscribers (if the SDK supports it). | Out of scope — this is langgraph upstream. |

The cleanest fix is probably "subscribe before dispatch" inside the wireup's `dispatch_autobuild_async` path — it removes the race entirely without depending on placeholder timing or upstream behaviour. That's a forge-side task; this runbook can't move it.

### Specialist-agent companion (`82ce8a6`) is in main but not exercised here

`specialist-agent` HEAD is `82ce8a6` ("bump nats-core floor to >=0.4 (v0.4.0 — TASK-IMP-DDSW-001)"), but the running architect/PO containers are still on the pre-bump image (Up 10 hours when this run started). FEAT-JARVIS-INTERNAL-001 is mode B / documentation-only and dispatches no specialist work, so this is **not** in the path that Phase 7 exercises. The runbook's §3.1 already tolerates a stale architect image; flagging here only so the next operator knows.

---

## Wave-3 fold candidates (none blocking; all observational)

| # | Section | Wave-3 fold candidate | Severity |
|---|---|---|---|
| W3-A | §7 expected-FAIL framing | Add **Signature C** to the §7.1 / §7.3 fail-signature tables — *"Bridge attaches and dispatches cleanly, `langgraph dev` reports `Background run succeeded` with low `run_exec_ms`, forge-prod's `join_stream` GET returns 200 but yields zero values events, `stream ended without a terminal envelope` fires ~1 s after dispatch, `ack_floor=0`, deadline timer does not fire because the stream was reachable. Forward-references TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-C-RACE (or equivalent)."* This is the canonical FAIL signature today and the runbook should describe it explicitly so the next operator doesn't re-derive the diagnosis. | High (operator-experience — the runbook's current §7 framing is now stale) |
| W3-B | §7 deadline qualifier | Carries forward unchanged from the prior fresh-followup-b-instrumented run. The deadline timer is gated on stream **unreachability**, not stream **silence**. Today's stream is reachable but empty; deadline does not publish `build-failed`. The runbook's "deadline timer will publish build-failed if the sidecar stays unreachable" qualifier correctly anticipates this — the §7 narrative just needs to be clearer that *empty-but-reachable* and *unreachable* are different paths. | Medium (correctness of expectation) |
| W3-C | §6.2 narration variance | Today's supervisor produced **inline-prose narration** rather than the documented bullet shape (`- **Correlation ID:** \`<uuid>\``, `- **Target:** pipeline.build-queued.FEAT-43DE`). The two load-bearing strings (UUID + subject) are present, just not in the bulleted form. The runbook's tolerance comment already says *"narration prose may vary turn-to-turn; the bullet shape is load-bearing"* — but **inline-prose** is a third shape (alongside `- **Publish target:**` / `- **Target:**` already documented). Either widen the tolerance comment to allow inline-prose, or treat this as a supervisor-prompt-tightening follow-up (the JSON tool result is correct; the issue is purely the supervisor's reasoner choosing prose over bullets). | Cosmetic |
| W3-D | §1.3 / §6.3 / §7.2 `nats` CLI command shape | The runbook's `docker exec -i $(docker ps -qf name=nats) nats --server "…" stream info PIPELINE -j` pattern fails on this GB10: the running NATS container (`ships-computer-nats`, image `nats-infrastructure-nats`) does **not** have the `nats` CLI installed in the container — only `nats-server`. The host has `nats` (v0.3.2) at `/usr/local/bin/nats` and `verify-nats.sh` calls it directly without `docker exec`. Fold the runbook to use host-side `nats` (or `docker exec` against a different container that ships the CLI). Ran all of §1.3, §6.3, §7.2 against host-side `nats` with no behavioural difference. | Low (the host-side workaround is one fewer indirection and is what `verify-nats.sh` already does) |
| W3-E | §7 instrumentation references | The runbook's §7.1 Signature B references the FOLLOWUP-B SSE instrumentation (`stream_part received n=N event='values' data_keys=…`, `parts_received=N`, `stream session open` / `stream exhausted`). All of these were removed by `b9e9585` and no longer surface in `docker logs forge-prod`. The §7 narrative needs a sweep — Signature B's two-cycle fingerprint (`parts_received=30` cycle 1 / `parts_received=0` cycles 2+) is now archeological, not currently observable. | Medium (the §7 framing implies the operator can see these markers; they can't post-`b9e9585`) |
| W3-F | Boot-line signatures | Add `composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired)` to the §2.2 "Pass" list, alongside the existing `dispatch chain composed … rebound` line. This is the most direct on-boot fingerprint that the FOLLOWUP-B-FIX surface is in the running image. | Low (pure additivity; helps the next operator confirm the right image is live) |

None of these gate AC-12 (operator-runbook-verbatim-runnable) or change the close criterion. W3-A and W3-E are the substantive folds; W3-B / W3-C / W3-D / W3-F are minor.

---

## Decision

* [x] **Phases 0–6 close canonical** — runbook is verbatim-runnable on a freshly-torn-down GB10 + freshly-rebuilt forge image; zero manual gap-folds during execution
* [x] **Phase 7 expected-FAIL signature reproduces deterministically** — new "Signature C" with full forge-side log evidence + LangGraph sidecar evidence + direct curl evidence captured
* [x] **FOLLOWUP-A migration continues to hold post-rebuild** — `applied 2 SQLite migration(s) at boot`, zero `register_ack_handle raised`
* [x] **FOLLOWUP-B-FIX wiring is observably live** — `composed PipelineConsumerDeps (async_task_starter=wired, ack_bridge=wired, terminal_publish_ledger=wired)` boot line proves the dep-composition path; `langgraph dev`'s `Background run succeeded run_exec_ms=16` proves the StateGraph executes successfully
* [ ] **AC-3 / AC-11 (Phase 7 close-criterion that the wire shows the envelope sequence)** still NOT MET — gated on a new follow-up that closes the `join_stream` subscribe-after-completion race (Signature C)
* [x] **AC-12 (operator-fresh-runbook-runnable)** validated end-to-end through Phase 7 evidence capture; the wave-2 fold + the W3 candidates above are operator-runnable today

**Recommended follow-ups:**

1. **forge-followup `TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-C-RACE`** (or equivalent name): close the `join_stream` race. Most likely fix is to subscribe the bridge to the SSE stream **before** triggering `dispatch_autobuild_async` rather than after; alternatives are using a replay-capable API (`runs.join` + state history) or making placeholder bodies sleep. Once this lands, the autobuild_runner StateGraph's `starting → planning_waves → running_wave → completed` lifecycle should produce **`pipeline.build-started.FEAT-43DE` + `pipeline.build-complete.FEAT-43DE`** on the wire (per `LIFECYCLE_TO_PIPELINE_EMIT`: `running_wave` after `starting/planning_waves` emits `build-started`; `completed` emits `build-complete`). Note that with **placeholder** bodies you would expect 2 envelopes (build-started + build-complete), not the runbook's full per-stage sequence (`build-started → stage-complete×N → build-complete/build-failed`) — that latter sequence requires real wave/task execution inside the runner nodes (out-of-scope per the FOLLOWUP-B-FIX commit's "Real autobuild orchestration … is wired in a follow-up").
2. **wave-3 runbook fold**: pick up W3-A through W3-F when TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-C-RACE's resolution lands and the next walkthrough can refresh the §7 framing against the new ground truth (which will be either 2 envelopes from placeholders, or the full per-stage sequence once real autobuild bodies land — depending on which task lands first).
3. **Defer the MacBook-over-Tailscale walkthrough** until Signature C is closed — same reasoning as wave-2: the network-isolated rerun adds no new evidence today, only retests publish→consume which we just proved cleanly.
4. **Optional:** rebuild the specialist-agent image to pick up the `82ce8a6` nats-core 0.4 bump. Not gating for this runbook (no specialist dispatch in mode B), but worth doing on the next operator pass so cross-repo state doesn't drift further.

---

## Evidence index

All under `/tmp/jarvis-runbook-evidence/` (timestamps 17:29 → 17:43 BST; UTC 16:29 → 16:43):

| File | Phase | Description |
|---|---|---|
| `phase1-verify-nats.log` | 1.2 | `verify-nats.sh` self-report `7 passed, 0 failed` (auth sourced; uses host-side `nats` CLI per W3-D) |
| `phase5-boot.log` | 5.1 | Clean jarvis chat boot (`nats_available=true, capabilities_mode=live`, 0 NATS warnings) |
| `phase6-pre-stream-info.json` | 6.3 | PIPELINE pre-publish (`messages=0, last_seq=22, consumers=1`) |
| `phase6-pre-consumer-info.json` | 6.3 | forge-serve pre-publish (`delivered=0, ack_floor=0` — fully fresh) |
| `phase6-chat.log` | 6.1/6.2 | Full DEBUG-level chat transcript (382 KB) |
| `phase6-chat-narration.txt` | 6.2 | User-facing narration only — 14 lines including the inline-prose queue ack |
| `phase7-pipeline-tap.log` | 6.3/7.2 | Wire tap of `pipeline.>` for ~6m (760 B; 1 inbound `BuildQueuedPayload`, 0 outbound) |
| `phase7-final-stream-info.json` | 7.2 | PIPELINE post-window (`messages=1, last_seq=23`) |
| `phase7-final-consumer-info.json` | 7.2 | forge-serve post-window (`delivered=14, ack_floor=0, redelivered=1`) — Signature C fail fingerprint |
| `phase7-forge-prod-logs-final.log` | 7.3 | Full forge-prod docker logs (111 lines, 25 KiB) covering all 7 cycles |
| `langgraph-sidecar.log` | 2.0/7.3 | langgraph dev sidecar log (32 KiB) — captures `Background run succeeded run_exec_ms=16` for the autobuild_runner run |
| `~/.jarvis/transcripts/10c80f94-cc2…fed.txt` | 8.1 | Chat transcript (382 KB copy of phase6-chat.log) |
| `~/.jarvis/traces/10c80f94-…fed.json` | 8.3 | DDR-019 soft-fail offload trace (DDR-029 schema) |

---

## See also

* [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — the runbook executed (current HEAD on jarvis main; folds W3-A through W3-F are forward-referenced from this RESULTS file)
* [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-fresh-followup-b-instrumented.md) — the same-day prior run against forge HEAD `e1eef81` (FOLLOWUP-B spike, instrumented but no behavioural fix). Captures the canonical Signature B fingerprint (`stream_part received n=30, event_types={'values'}`).
* [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-dryrun-wave2.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-dryrun-wave2.md) — earlier same-day dryrun against stale forge state
* [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md) — human-driven walkthrough that drove the wave-2 fold
* Forge commit `b9e9585` — `fix(FEAT-PEBR): wire async_tasks channel into autobuild_runner StateGraph (FOLLOWUP-B-FIX)`. The commit message itself flagged AC-3 ("end-to-end runbook revalidation") as deferred — this RESULTS file is that revalidation.
