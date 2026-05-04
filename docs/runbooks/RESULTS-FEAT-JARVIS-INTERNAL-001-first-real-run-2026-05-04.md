# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run — Rerun (post-FRR follow-ups)

**Date:** 2026-05-04
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident (host = `127.0.0.1` per `/etc/hosts`)
**correlation_id:** `18036705-2bb7-4564-8363-315bf7716a48`
**Outcome:** ⏸ **Same overall shape as 2026-05-01** (forge consume+ack proven; per-stage envelope sequence still does not flow back) — **but every jarvis-side gap from the 2026-05-01 RESULTS is now resolved.** The remaining failure is forge-side and discovered new: `forge serve_cmd` does not rebind `compose_dispatch_chain` to the production composer, so even with FEAT-FORGE-010 (FEAT-DEA8) merged on 2026-05-02 the receipt-only `_default_dispatch` stub still wins on the daemon's hot path.

**Companion document:** [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) (2026-05-01 baseline). This file records the rerun executed once all four jarvis-side follow-ups (TASK-FRR-001…004) merged.

---

## Summary in one paragraph

`queue_build` succeeded end-to-end on the wire again — a `BuildQueuedPayload` was published to JetStream subject `pipeline.build-queued.FEAT-43DE`, the `forge-serve` durable consumer dequeued and acked it (`delivered: 2, num_pending: 0, num_redelivered: 0`), and the chat REPL reported the queue ack with the correlation_id back to the operator. The headline improvements vs the 2026-05-01 run are all **on the jarvis side**: (1) the three startup-time NATS subscription failures (fleet register, agent-registry KV bind, `forge_subscriber` consumer attach) are gone — the boot log shows `fleet_register_published`, `forge_notifications_subscribed` on `pipeline.stage-complete.>`, `jarvis_forge_subscriber_started`, and `jarvis_forge_subscriber_bound_session_manager` all clean (TASK-FRR-001 win); (2) the DDR-019 soft-fail trace offload now lands locally — `~/.jarvis/traces/18036705-2bb7-4564-8363-315bf7716a48.json` was written with the full DDR-029 schema and a clear `routing_history_offloaded_locally` log line, instead of being silently dropped (TASK-FRR-003 win); (3) the runbook executed verbatim apart from one already-known forge-followup-3 buildx invocation workaround (TASK-FRR-004 win — all 13 gaps from 2026-05-01 are folded). Forge also improved on its side: `_configure_logging` now runs at startup so `docker logs forge-prod` actually shows what the daemon is doing (forge-followup-2 landed via FEAT-FORGE-010). The remaining gap is forge-only: even with FEAT-FORGE-010 merged, the `serve_cmd` entry-point never rebinds `compose_dispatch_chain` to `bind_production_dispatch_chain(...)`, so the daemon falls through to the receipt-only stub. Discovered new — needs a forge follow-up.

## Per-phase outcomes

| Phase | Gate | 2026-05-01 | 2026-05-04 | Evidence |
|---|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | ✅ | top: `bb6056c` (Phase 7 rewrite merge); FRR-001/2/3/4 + FW10-merge dependencies all in log |
| 0.2 | GB10 reachable | ✅ (we are GB10) | ✅ (we are GB10) | `uname -a` → `Linux promaxgb10-41b1`; ping `127.0.0.1` |
| 0.3 | forge nats-core symlink | ✅ | ✅ | `.guardkit/worktrees/nats-core -> ../../../nats-core` resolves |
| 0.4 | provider keys + NATS auth + llama-swap model | ✅ with notes | ✅ | `JARVIS_NATS_URL` set with `rich:${RICH_NATS_PASSWORD}@localhost:4222`; `JARVIS_SUPERVISOR_MODEL=openai:qwen36-workhorse`; `JARVIS_GRAPHITI_ENDPOINT` left unset (FRR-003 path); deprecated `JARVIS_OPENAI_BASE_URL` still present in operator's local `.env` but **silently ignored** by post-FRR-002 settings schema |
| 1.1 | NATS container up | ✅ | ✅ | `ships-computer-nats` Up 44 hours (healthy); 4222/8222 bound |
| 1.2 | 7 streams + 4 KV buckets | ✅ | ✅ | `verify-nats.sh` reports 7/0; KV inventory matches canonical 4 |
| 1.3 | `pipeline.build-queued.>` bound | ✅ | ✅ | `subjects=["pipeline.>"]`, `retention=workqueue` |
| 2.1 | forge image built | ✅ with workaround | ✅ with **same** workaround | `forge:latest` rebuilt from `de23557` (post FEAT-DEA8 merge); 430MB; `scripts/build-image.sh` cwd bug still unfixed forge-side, runbook documents the buildx-from-inside-`forge/` workaround. `--no-cache` not used — buildx layer cache valid since the editable `nats-core` sibling was untouched |
| 2.2 | forge serve running | ✅ with workaround (no logs) | ✅ **with logs visible** | `forge-prod` Up (healthy); first log line is `2026-05-04T06:12:20 [INFO] forge.cli._serve_healthz: healthz server listening on 0.0.0.0:8088 (durable=forge-serve)` — **forge-followup-2 fix landed via FEAT-FORGE-010 / TASK-FORGE-FRR-002** (`_configure_logging` runs at startup) |
| 2.3 | /healthz green | ✅ | ✅ | `curl http://localhost:8088/healthz` → `{"status":"healthy"}`; `consumer ls PIPELINE` shows `forge-serve` |
| 3.1 | architect container up | ⚠️ skipped | ⚠️ skipped | non-blocking: doc-only feature; matches 2026-05-01 |
| 3.2 | architect ping | ⚠️ skipped | ⚠️ skipped | n/a |
| 4.1 | graphiti/falkordb up | ⚠️ partial (unhealthy) | ⚠️ partial (healthy container, port shadowed) | `graphiti-mcp` Up 23h **healthy** this time (improvement vs 2026-05-01 unhealthy); but `:8080` returns **open-webui's HTML** — Graphiti is not actually exposed on this port. Real Graphiti endpoint unknown; runbook §4.2 fall-back path applies — leave `JARVIS_GRAPHITI_ENDPOINT` unset, rely on FRR-003 offload |
| 4.2 | embeddings reachable | ✅ (different surface) | ✅ (same) | `curl :9000/v1/embeddings` with `nomic-embed` returned 768-dim vector — llama-swap, not Graphiti |
| 5.1 | jarvis chat boots | ✅ with caveat (3 NATS errors at boot) | ✅ **clean** | **TASK-FRR-001 win.** Boot log shows `fleet_register_published`, `jarvis_dispatch_semaphore_ready`, `forge_notifications_subscribed subject=pipeline.stage-complete.>`, `jarvis_forge_subscriber_started`, `jarvis_forge_subscriber_bound_session_manager`, `jarvis_startup_complete nats_available=true graphiti_available=false capabilities_mode=live`. **Zero NATS subscription errors.** The DDR-030 between-prompt notification path is alive |
| 5.2 | tool inventory smoke | ✅ | ✅ | Reasoner enumerated `queue_build`, `dispatch_by_capability`, `build_feature`, `escalate_to_frontier`, async-task surface, etc. without prompting |
| 6.2 | `queue_build` returns success | ✅ (FEAT-43DE) | ✅ (FEAT-43DE) | `correlation_id=18036705-2bb7-4564-8363-315bf7716a48`; assistant text: *"FEAT-43DE is queued for build. Correlation ID: `18036705-…`. Forge will pick it up from the JetStream topic `pipeline.build-queued.FEAT-43DE` — I'll notify you via events as it progresses."* |
| 6.3 | message visible on PIPELINE stream | ✅ via state | ✅ via state + **raw envelope** | `state.last_seq=2`, `state.messages=0` (workqueue retention drained on ack). The `nats sub "pipeline.>"` tail also captured the inbound `BuildQueuedPayload` JSON envelope verbatim — `event_type=build_queued`, `mode=mode-a`, `feature_id=FEAT-43DE` |
| 7.1 | between-prompt notifications render full lifecycle sequence | ❌ as expected | ❌ same shape | **No notifications drained.** Supervisor's second-turn answer was honest: *"Progress events (like `pipeline.*`) should arrive via notifications as Forge processes it, but I don't have a way to actively poll the build pipeline's current state right now."* — the chat code is correctly not fabricating events that didn't arrive |
| 7.2 | wire shows the same lifecycle sequence on JetStream subjects | ❌ | ❌ same shape | `consumer info forge-serve`: `delivered=2, pending=0, redelivered=0` (forge consumed + acked). `pipeline.>` tail captured **only** the inbound `pipeline.build-queued.FEAT-43DE` envelope — no outbound `pipeline.build-started.*` / `pipeline.stage-complete.*` / `pipeline.build-complete.*` envelopes published. **forge-side gap discovered new** — see "Forge gap discovered" below |
| 7.3 | forge container logs show autobuild_runner subagent launch | ❌ | ❌ partial | forge logs (now visible thanks to forge-followup-2 fix): `forge-serve: received build-queued envelope feature_id=FEAT-43DE correlation_id=18036705-...` — that's the receipt-only stub's log line at `_serve_daemon.py:209-214`. **No** `forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher` line — confirming `compose_dispatch_chain` is still the no-op default, not the production composer |
| 8.1 | chat transcript saved | ✅ | ✅ | `~/.jarvis/transcripts/18036705-2bb7-4564-8363-315bf7716a48.txt` (269KB) |
| 8.2 | Graphiti routing-history dump | ⚠️ skipped | ⚠️ skipped | `JARVIS_GRAPHITI_ENDPOINT` not set; relied on §8.3 instead |
| 8.3 | local trace offload | ⚠️ none written | ✅ **trace landed** | **TASK-FRR-003 win.** `~/.jarvis/traces/` autocreated on first soft-fail write (the directory did not exist before the chat session started); `~/.jarvis/traces/18036705-2bb7-4564-8363-315bf7716a48.json` contains the full DDR-029 `JarvisRoutingHistoryEntry` (decision_id, outcome_type=`success`, outcome_detail with feature_id/subject, supervisor_reasoning_summary=`queue_build`, capability_snapshot_hash, etc.). The `routing_history_offloaded_locally` log event fired loudly instead of silently dropping the trace |
| 8.4 | `command_history.md` entry | ✅ (filename gap-folded) | ✅ | Appended a 2026-05-04 section to `docs/history/command_history.md` mirroring this rerun |

## Forge gap discovered (new — not in the 2026-05-01 RESULTS)

The 2026-05-01 RESULTS recommended forge-followup-1: "wire `dispatch_payload` to the real `pipeline_consumer` orchestrator + stage-complete publish path." That follow-up was scoped up into FEAT-FORGE-010 (FEAT-DEA8, "wire pipeline orchestrator into forge serve") and merged on 2026-05-02 (`forge` `9a93808` … `de23557`). The merge ships:

- `forge/src/forge/cli/_serve_dispatcher.py::make_handle_message_dispatcher` — production dispatcher closure (TASK-FW10-007)
- `forge/src/forge/cli/serve.py::bind_production_dispatch_chain(forge_config, sqlite_pool, async_task_starter=None)` — factory returning an `async (client) -> None` `_compose` closure that builds `PipelineConsumerDeps`, wraps it in `make_handle_message_dispatcher`, and rebinds `_serve_daemon.dispatch_payload` (TASK-FW10-007 docstring AC: *"receipt-only stub no longer reachable"*)
- `_run_serve(...)` calls `await compose_dispatch_chain(client)` at line 539, before `state.set_chain_ready(True)` and the daemon's first fetch

But: `serve_cmd` (the `@click.command(name="serve")` entry-point that the production container actually invokes) **does not rebind** `compose_dispatch_chain` to `bind_production_dispatch_chain(...)`. As-shipped, `serve_cmd` is:

```python
@click.command(name="serve")
def serve_cmd() -> None:
    config = ServeConfig.from_env()
    _configure_logging(config.log_level)
    state = SubscriptionState()
    asyncio.run(_run_serve(config, state))
```

So `_run_serve` calls `compose_dispatch_chain(client)` against the module-level default `_default_compose_dispatch_chain` (a logged DEBUG no-op), which leaves `_serve_daemon.dispatch_payload` as `_default_dispatch` — the receipt-only stub at `_serve_daemon.py:166`. Every inbound `pipeline.build-queued.*` envelope gets logged + acked, no autobuild runs, no lifecycle envelopes are published.

Wave 4 capstone task `TASK-FW10-011 — End-to-end lifecycle integration test (build-queued → terminal envelope, all subjects)` is at status `design_approved` (not implemented) — that's the integration test against the wired-in-production stack which would have caught this. It depends on FW10-007 / 008 / 009 / 010 (all `completed`), so it's the last unimplemented piece of FEAT-FORGE-010.

**Recommended new forge follow-up:** add a single-line rebind to `serve_cmd` (or to a thin ops wrapper that wraps `serve_cmd`) so the production composition actually runs at boot. Indicative shape:

```python
@click.command(name="serve")
def serve_cmd() -> None:
    config = ServeConfig.from_env()
    _configure_logging(config.log_level)
    sqlite_pool = build_sqlite_pool(config)               # already exists in deps factory
    forge_config = build_forge_config(config)             # already exists in deps factory
    async_task_starter = _build_async_subagent_middleware()  # already exists at serve.py:262
    serve_module = sys.modules[__name__]
    serve_module.compose_dispatch_chain = bind_production_dispatch_chain(
        forge_config=forge_config,
        sqlite_pool=sqlite_pool,
        async_task_starter=async_task_starter,
    )
    state = SubscriptionState()
    asyncio.run(_run_serve(config, state))
```

…and then close out FW10-011 to lock this in with an integration test.

**Why the existing FW10 unit/contract tests didn't catch it:** the `bind_production_dispatch_chain` factory is unit-tested in isolation (rebinds correctly when invoked with real deps), but no test invokes the `forge serve` CLI entry-point and asserts that the rebind has happened by the time the daemon's first fetch runs. FW10-011 is exactly that test.

## What changed vs 2026-05-01 — verbatim diff of follow-up status

| Source-of-truth | 2026-05-01 status | 2026-05-04 status | Evidence in this rerun |
|---|---|---|---|
| TASK-FRR-001 (jarvis NATS reconciliation) | filed | **landed** (`5391f35`, `b8fe322`, `e995f49`, `620a51c`) | Phase 5.1 boot is clean — three NATS errors gone |
| TASK-FRR-002 (drop misleading `JARVIS_OPENAI_BASE_URL`) | filed | **landed** (`75b8ca0`) | `.env.example` no longer lists the field; deprecated value still in operator's local `.env` is silently ignored by settings schema (verified by clean boot with the stale `.env` line still present) |
| TASK-FRR-003 (DDR-019 trace-offload autocreate + non-silent drop) | filed | **landed** (`aae6e36`, `a3f13e2`, `1eba440`, `d598a57`) | Phase 8.3 — `~/.jarvis/traces/` autocreated, full trace JSON landed, `routing_history_offloaded_locally` log line emitted |
| TASK-FRR-004 (runbook gap-fold rewrite) | filed | **landed** (`5076b02`, `ee9478d`) plus subsequent Phase 7 rewrite for FEAT-FORGE-010 | Runbook executed verbatim apart from the one forge-side workaround (forge-followup-3 buildx cwd) it explicitly forward-references — no fresh gaps discovered for the runbook itself |
| forge-followup-1 (real `dispatch_payload`) | filed | partially closed by FEAT-FORGE-010 wave 1-3 (`9a93808` … `de23557`); **but `serve_cmd` doesn't bind the seam yet — see "Forge gap discovered"** | Phase 7.2 — daemon still falls through to receipt-only stub |
| forge-followup-2 (`logging.basicConfig` in serve.py) | filed | **landed via FEAT-FORGE-010 / TASK-FORGE-FRR-002** (`_configure_logging` is called from `serve_cmd`) | Phase 2.2 — `docker logs forge-prod` now shows healthz line, receipt-only-dispatch line, etc. |
| forge-followup-3 (build-image.sh cwd) | filed | **not landed** | Phase 2.1 — same buildx-from-inside-`forge/` workaround the runbook documents inline |

## Cross-machine state observed

- **NATS** (`ships-computer-nats`, host-network): up 44h healthy, 7 canonical streams + 4 KV buckets present (PIPELINE / AGENTS / JARVIS / NOTIFICATIONS / SYSTEM / FLEET / FINPROXY; agent-status / agent-registry / pipeline-state / jarvis-session). Three leftover test streams from 2026-04-16 (PERSISTENCE_TEST / RETRIEVAL_TEST / SURVIVAL_TEST) still present — same drift as 2026-05-01, not blocking.
- **forge-prod** (host-network, `forge:latest` = `forge:production-validation` rebuilt 2026-05-04): up healthy, durable consumer `forge-serve` attached on PIPELINE, healthz on `:8088` (FORGE_HEALTHZ_PORT override), logs now visible.
- **graphiti-mcp**: up 23h **healthy** this time (improvement vs 2026-05-01 unhealthy). Real Graphiti HTTP endpoint not located on this host — `:8080` is held by `open-webui`. Did not exercise; relied on §8.3 offload.
- **open-webui**: up host-network on 8080 (same conflict that drives `FORGE_HEALTHZ_PORT=8088`).
- **llama-swap**: up via systemd, serving on `:9000` with `gemma4-tutor`, `nomic-embed`, `qwen-graphiti`, `qwen36-workhorse`. Used `qwen36-workhorse` for the supervisor.

## Decision

- [ ] Phase 3 closed canonical
- [x] **Phase 3 closed with gap-folds (jarvis-side fully closed; forge-side gap remaining)** — every jarvis follow-up from the 2026-05-01 RESULTS landed and is verified by this rerun. The remaining gap (`compose_dispatch_chain` not bound in `serve_cmd`) is a fresh forge-side discovery; FEAT-FORGE-010 is 7/8 of the way home but the production binding plus FW10-011's integration test still need to land before a true stage-complete round-trip can be proven on the wire.
- [ ] Partial — single-phase failure with follow-up task

## Recommended follow-ups (delta vs 2026-05-01)

1. **forge (NEW):** Rebind `compose_dispatch_chain` to `bind_production_dispatch_chain(...)` in `forge.cli.serve.serve_cmd` (or in a thin ops wrapper) so the production composition runs at boot. Indicative shape in "Forge gap discovered" above.
2. **forge:** Land TASK-FW10-011 (`design_approved` → `in_progress` → `completed`) — the wired-in-production end-to-end integration test that asserts a single inbound `pipeline.build-queued.<feature_id>` produces the full lifecycle envelope sequence threaded by `correlation_id`. This is the test that would have caught (1).
3. **forge:** Fix `scripts/build-image.sh` cwd / build-context path so the runbook can revert from the manual buildx workaround to a single-line invocation (forge-followup-3 from 2026-05-01; not yet landed).
4. **jarvis:** Operator's local `.env` still carries the deprecated `JARVIS_OPENAI_BASE_URL=http://localhost:9000/v1` — silently ignored, but worth a cleanup (`sed -i '/^JARVIS_OPENAI_BASE_URL=/d' .env`). Not a code change.
5. **infrastructure:** Either rebind `graphiti-mcp` off `:8080` (which open-webui holds) or document its actual HTTP endpoint — TASK-INFRA-001 (filed 2026-05-01) covers this; status unverified.
6. **MacBook over Tailscale walkthrough:** still deferred. Until (1) and (2) land, the MacBook walkthrough can only re-prove what GB10 already proved (publish → consume + ack); there's no new evidence in the network-isolated rerun until the stage-complete round-trip is structurally satisfiable. Re-evaluate when the forge follow-up closes.

## Evidence files

All under `/tmp/runbook-evidence-rerun-2026-05-04/`:

- `phase0.1-git-status.log`, `phase0.1-git-log.log`, `phase0.2-host.log`, `phase0.3-symlink.log`, `phase0.4-env.log`
- `phase1.1-compose-ps.log`, `phase1.2-verify-nats.log`, `phase1.2-kv-ls.log`, `phase1.3-pipeline-info.json`
- `phase2.0-forge-ps.log`, `phase2.1-images.log`, `phase2.1-build-image.log`, `phase2.2-docker-run.log`, `phase2.2-forge-logs.log`, `phase2.3-healthz.json`, `phase2.3-consumers.log`
- `phase3.1-specialist.log` (empty — no containers; expected)
- `phase4.1-graphiti.log`, `phase4.2-graphiti-probe.log`, `phase4.3-embeddings.log`
- `phase5-toolinv.log`
- `phase6-prompt.txt`, `phase6-7-chat.log` (full DEBUG-level chat transcript)
- `phase7-pipeline-tail.log` (raw inbound build-queued envelope captured by `nats sub "pipeline.>"`)
- `phase7-forge-logs.log`, `phase7-consumer-info.json`
- Transcript copy: `~/.jarvis/transcripts/18036705-2bb7-4564-8363-315bf7716a48.txt`
- Routing-history offload (FRR-003): `~/.jarvis/traces/18036705-2bb7-4564-8363-315bf7716a48.json`

---

# Addendum: Same-day post-TASK-FIX-F010 rerun (2026-05-04, evening)

**Forge HEAD when re-run:** `af62d5c` (post-`32b67f8 fix(serve): bind compose_dispatch_chain to production composer (TASK-FIX-F010)`)
**Image rebuilt:** `forge:latest` = `forge:production-validation` = sha256 `ebc4311026cc...`
**Run window:** 2026-05-04 ~07:23 UTC → ~07:39 UTC (4 successive jarvis-chat queues)
**correlation_ids (in order):**
1. `21df1258-63cb-4e8a-9bef-89234833b68e` — relative path, default forge.yaml allowlist
2. `b5c5e1e2-dd5d-4df9-bc26-a5ec36f6db8f` — explicit absolute path (supervisor normalised back to relative — queue_build docstring says "relative to repo root")
3. `a55df422-dd03-4562-9326-0278f3eeb764` — widened forge.yaml allowlist to include `/home/forge`; passed validation, hit fresh-DB schema gap
4. `f876fd47-5e3c-4851-8f89-a7b7bcab8464` — schema bootstrapped via `apply_at_boot`; consumer dispatched build, persisted QUEUED row, then bombed on missing persistence method
**Outcome:** 🟢 **Phase 7 row 7.x flips ❌ → 🟢 partial-pass.** TASK-FIX-F010's production-binding wiring is **demonstrably live** — every queue_build envelope now flows through `pipeline_consumer.handle_message` (the receipt-only stub is gone) and at least one outbound `pipeline.build-failed` envelope was observed on the wire in the live walkthrough. The full `build-started + stage-complete*N + build-complete` sequence does NOT yet reach the wire — four cascading new forge-side gaps surfaced once the production composer was actually exercised end-to-end. Documented below as **Gaps F010.A — F010.D**.

## Headline win (TASK-FIX-F010)

The single log line the previous rerun was missing now appears at every forge-prod boot:

```
2026-05-04T07:32:02 [INFO] forge.cli._serve_production: forge-serve: production composer bound (db_path=/var/forge/forge.db)
2026-05-04T07:32:02 [INFO] forge.cli._serve_deps_state_channel: build_autobuild_state_initialiser: composed SQLite-backed AutobuildStateInitialiser against pool db_path=/var/forge/forge.db
2026-05-04T07:32:02 [INFO] forge.cli._serve_deps: build_pipeline_consumer_deps: composed PipelineConsumerDeps (async_task_starter=wired)
2026-05-04T07:32:02 [INFO] forge.cli.serve: forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)
2026-05-04T07:32:02 [INFO] forge.cli._serve_healthz: healthz server listening on 0.0.0.0:8088 (durable=forge-serve)
```

The chosen design from TASK-REV-F010 (D1.B — thin ops wrapper module `forge.cli._serve_production`; D2.A — extend `ServeConfig` with `db_path` reusing `FORGE_DB_PATH`; D3.A — eager middleware construction; D5.A — testable helper) is what the on-the-wire behaviour now reflects.

## Phase 7 rewrite — line-by-line outcome

For run 4 (the deepest one — schema bootstrapped, autobuild dispatcher reached):

| Hard-reject criterion (from runbook §7.1) | Run 4 observation | Verdict |
|---|---|---|
| Receipt-only `_default_dispatch` is reachable on hot path | **Not reachable** — log: `_serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)` | ✅ pass |
| Inbound `pipeline.build-queued.<feature_id>` reaches the production consumer | Yes — log: `pipeline_consumer: dispatching build feature_id=FEAT-43DE correlation_id=f876fd47-... originating_adapter=terminal` | ✅ pass |
| SQLite QUEUED row written by `dispatch_build` | Yes — log: `dispatch_build: persisted QUEUED row build_id=build-FEAT-43DE-20260504073635 feature_id=FEAT-43DE correlation_id=f876fd47-...` | ✅ pass |
| Subsequent `pipeline.build-started.<feature_id>` envelope published | **No** — autobuild dispatcher raises before publishing (Gap F010.B) | ❌ fail |
| `pipeline.stage-complete.<feature_id>` envelopes per stage | **No** — autobuild never starts | ❌ fail |
| Terminal `pipeline.build-complete.*` or `pipeline.build-failed.*` published | **No** for run 4; **yes** for runs 1+2 (path-rejection produces a `build-failed`, but with `correlation_id: null` — Gap F010.C) | ⚠️ partial |
| All envelopes thread the same `correlation_id` jarvis published in 6.2 | Run-2 build-failed envelope had `correlation_id: null` instead of `21df1258-...` | ❌ fail (Gap F010.C) |
| Notifications drained in chat REPL between prompts | **No** — jarvis only subscribes to `pipeline.stage-complete.>`, can't see `pipeline.build-failed.>` envelopes (Gap F010.D) | ❌ fail |

## Gaps surfaced on the wire (NEW — post-FIX-F010)

### Gap F010.A — Daemon doesn't apply SQLite migrations on a fresh `FORGE_DB_PATH`

**Symptom (run 3):**
```
[WARNING] forge.cli._serve_deps: is_duplicate_terminal: SQLite read failed for feature_id=FEAT-43DE correlation_id=a55df422-... (no such table: builds); treating as non-duplicate
[INFO] forge.adapters.nats.pipeline_consumer: pipeline_consumer: dispatching build feature_id=FEAT-43DE correlation_id=a55df422-... originating_adapter=terminal
[WARNING] forge.adapters.nats.pipeline_consumer: pipeline_consumer: dispatch_build raised (no such table: builds) for feature_id=FEAT-43DE correlation_id=a55df422-...; acking and continuing so the next build can be processed
```

**Root cause:** `forge.lifecycle.migrations.apply_at_boot` is called from `forge.cli.queue` (the `forge queue` CLI subcommand) but **not** from `forge.cli._serve_production.bind_production_serve` — so a fresh `/var/forge/forge.db` volume mounted into the daemon stays schemaless until something else creates the tables. The daemon happily attaches to the (empty) DB, fails every `dispatch_build`, and acks the inbound envelope without publishing any outbound lifecycle envelope.

**Workaround used in this rerun:** `docker exec forge-prod python -c "from forge.lifecycle.migrations import apply_at_boot; ..."` against the mounted DB. Returns `2` (versions applied: schema.sql + schema_v2.sql). Tables: `async_tasks`, `builds`, `stage_log`, `sqlite_sequence`, `schema_version`.

**Fix shape:** call `apply_at_boot(connection)` inside `bind_production_serve` immediately after `connect_writer(...)`. Mirror the `forge queue` invocation pattern. One-line change.

### Gap F010.B — `dispatch_build` raises `AttributeError: 'SqliteLifecyclePersistence' object has no attribute 'get_approved_stage_entry'`

**Symptom (run 4 — after schema bootstrapped):**
```
[INFO] forge.adapters.nats.pipeline_consumer: pipeline_consumer: dispatching build feature_id=FEAT-43DE correlation_id=f876fd47-... originating_adapter=terminal
[INFO] forge.cli._serve_deps: dispatch_build: persisted QUEUED row build_id=build-FEAT-43DE-20260504073635 feature_id=FEAT-43DE correlation_id=f876fd47-...; dispatching autobuild
[WARNING] forge.adapters.nats.pipeline_consumer: pipeline_consumer: dispatch_build raised ('SqliteLifecyclePersistence' object has no attribute 'get_approved_stage_entry') for feature_id=FEAT-43DE correlation_id=f876fd47-...; acking and continuing so the next build can be processed
```

**Root cause:** The autobuild dispatcher (probably the `AutobuildStateInitialiser` or one of its forward-context builders) calls `persistence.get_approved_stage_entry(...)` but `SqliteLifecyclePersistence` doesn't expose that method. This is internal-to-forge wiring drift between FW10-005 (`AutobuildStateInitialiser` binding) and the persistence facade. The QUEUED row is successfully written *before* this raises, so partial state is persisted but no `build-started` envelope is ever published.

**Reproducer:** any build-queued envelope that passes path-and-originator validation, against a schema-bootstrapped DB. Deterministic.

**Fix shape:** either add `get_approved_stage_entry` to `SqliteLifecyclePersistence` (most likely the right answer, since the dispatcher already expects it) or rebind whichever caller is using that name to the actual method on the facade. Forge unit tests do not cover this path because the FW10-005 unit tests use a fake persistence object that satisfies the interface.

### Gap F010.C — Path-allowlist rejection publishes `build-failed` with `correlation_id: null`

**Symptom (runs 1, 2):**

Inbound (jarvis-published):
```json
{"correlation_id":"21df1258-63cb-4e8a-9bef-89234833b68e", "payload":{"feature_id":"FEAT-43DE", ...}}
```

Outbound (forge-published, on `pipeline.build-failed.FEAT-43DE`):
```json
{"correlation_id":null, "source_id":"forge", "event_type":"build_failed", "payload":{"feature_id":"FEAT-43DE","build_id":"FEAT-43DE","failure_reason":"path outside allowlist","recoverable":false,"failed_task_id":null}}
```

**Root cause:** `forge.adapters.nats.pipeline_consumer._failure_payload` (or whatever publishes the rejection envelope) does not thread the inbound `correlation_id` into the outbound envelope. The DDR-029 notification-thread contract requires every lifecycle envelope to carry the inbound `correlation_id` so jarvis can render it against the same chat session. Without it, even a jarvis-side subscription fix (Gap F010.D) wouldn't help — there'd be no way to route the notification to the right session.

**Fix shape:** thread `inbound_envelope.correlation_id` into the outbound `MessageEnvelope` at every publish site in `pipeline_consumer`. Cross-check FW10-009 ("validation surface and build-failed paths") — this is plausibly already on its AC list and just slipped.

### Gap F010.D — `forge_subscriber` only subscribes to `pipeline.stage-complete.>`

**Symptom:** jarvis boot log shows `forge_notifications_subscribed subject=pipeline.stage-complete.>` — but the spec calls for the chat REPL to render `build-started`, `stage-complete*N`, and `build-complete`/`build-failed`. So jarvis cannot see `pipeline.build-started.>`, `pipeline.build-complete.>`, or `pipeline.build-failed.>` envelopes at all.

**Where:** `src/jarvis/infrastructure/forge_notifications.py` (the subscriber) — the subject filter is hard-coded to `pipeline.stage-complete.>`.

**Fix shape:** widen the subscriber's subject filter to either `pipeline.>` (catch-all, cheapest) or to a list of specific subjects (`pipeline.build-started.>`, `pipeline.stage-complete.>`, `pipeline.build-complete.>`, `pipeline.build-failed.>`). The `ForgeNotification.render_line()` rendering already handles all four envelope types per the runbook §7.1 acceptance criteria — so the rendering is fine, it's just the subscription that's narrower than the rendering surface.

## Updated per-phase table delta (post-FIX-F010 only)

(Only rows that change from the morning rerun above.)

| Phase | Gate | Morning (pre-FIX) | Evening (post-FIX) | Evidence |
|---|---|---|---|---|
| 2.2 | forge serve running | ✅ with logs visible (forge-followup-2) | ✅ + production composer bound | New log: `forge-serve: production composer bound (db_path=/var/forge/forge.db)` + `dispatch chain composed` |
| 6.2 | `queue_build` returns success | ✅ | ✅ × 4 (correlation_ids `21df1258-…`, `b5c5e1e2-…`, `a55df422-…`, `f876fd47-…`) | `routing_history_offloaded_locally` for every one |
| 6.3 | message visible on PIPELINE stream | ✅ via state | ✅ via state + raw envelope tail | `last_seq=8`, `messages=2` (two undrained `build-failed` envelopes from runs 1+2) |
| 7.1 | between-prompt notifications render full lifecycle sequence | ❌ | ❌ — but for **different reasons** now | Notifications still don't drain, but root cause is no longer the receipt-only stub — it's Gap F010.D (subscription narrower than rendering surface) and Gap F010.B (autobuild can't start, so no envelopes are emitted to subscribe to in the first place). |
| 7.2 | wire shows the same lifecycle sequence on JetStream subjects | ❌ — receipt-only stub never published anything | ⚠️ **partial** — `pipeline.build-failed.FEAT-43DE` envelope **did** flow back in runs 1+2 (path-rejection codepath) | TASK-FIX-F010 verified in full: production composer is wired, real codepath runs, real publish happens. The remaining "no full sequence" is downstream of Gap F010.B. |
| 7.3 | forge container logs show autobuild_runner subagent launch | ❌ | ⚠️ **partial** — daemon logs show `dispatching build`, `persisted QUEUED row`, `dispatching autobuild`, then the missing-method exception | The autobuild *dispatch entry* fires; the autobuild *runner* never launches because Gap F010.B kills the dispatcher before it constructs the runner |
| 8.3 | local trace offload | ✅ | ✅ × 4 | All 4 correlation_ids landed in `~/.jarvis/traces/` |

## Decision delta

- [ ] Phase 3 closed canonical — runbook is verbatim-runnable; no gap-folds needed
- [x] **Phase 3 closed with gap-folds** — same as morning, but with a different residual gap-list (4 forge-side bugs surfaced once the production composer was actually exercised end-to-end)
- [ ] Partial — single-phase failure with follow-up task

## Recommended follow-ups (delta vs morning rerun)

The four jarvis-side FRR follow-ups + TASK-FIX-F010 + the `serve_cmd` rebind are **all closed**. Replace the recommended-follow-ups list from the morning rerun with the following four new ones:

1. **forge — F010.A:** Have `bind_production_serve` call `apply_at_boot(connection)` after `connect_writer(...)` so a fresh `FORGE_DB_PATH` volume gets the `builds`/`stage_log`/etc. tables on first boot. One-line fix; the migration runner is already idempotent.
2. **forge — F010.B:** Resolve the `'SqliteLifecyclePersistence' object has no attribute 'get_approved_stage_entry'` AttributeError in the autobuild dispatcher path. Add the method to the persistence facade or rename the caller; whichever side is the source of truth.
3. **forge — F010.C:** Thread `inbound_envelope.correlation_id` into every outbound lifecycle envelope (`build-failed`, `build-started`, `stage-complete`, `build-complete`) in `pipeline_consumer`. Cross-check against FW10-009 / FW10-010 ACs.
4. **jarvis — F010.D:** Widen `forge_subscriber`'s subject filter from `pipeline.stage-complete.>` to either `pipeline.>` or the explicit four-subject set so the chat REPL can render `build-started`, `build-complete`, and `build-failed` envelopes (it already knows how to — only the subscription is narrower).

Once those four close, a fifth re-run should produce the full `build-started + stage-complete*N + build-complete` sequence in the chat REPL — that's the canonical Phase 7 close.

## Updated cross-machine state (delta only)

- **forge-prod** (host-network, `forge:latest` = sha256 `ebc4311026cc...`, post-`32b67f8`): up healthy, durable consumer attached, **production composer bound**, SQLite db at `/var/forge/forge.db` (mounted from host `~/forge-state/forge.db`); `apply_at_boot` ran manually once to bootstrap schema (Gap F010.A).
- **forge.yaml** (mounted from `~/forge-state/forge.yaml` to `/home/forge/forge.yaml:ro`): allowlist widened to include `/home/forge` so the relative-path resolution from the daemon's cwd lands inside the allowlist for our test feature.
- **mounted volumes:** also `~/Projects/appmilla_github/jarvis:~/Projects/appmilla_github/jarvis:ro` so any file IO from forge against the absolute jarvis path resolves.

## Updated evidence files (post-FIX-F010 only)

All under `/tmp/runbook-evidence-rerun-2026-05-04-postfix/`:

- `phase2.1-build-image.log`, `phase2.2-docker-run.log`, `phase2.2-forge-logs.log`, `phase2.3-healthz.json`
- `phase6-prompt.txt` is implicit (4 sessions; commands captured in `phase6-7-chat-{1..4}.log` filenames)
- `phase6-7-chat.log`, `phase6-7-chat-2.log`, `phase6-7-chat-3.log`, `phase6-7-chat-4.log` — full DEBUG transcripts of all four chat sessions
- `phase7-pipeline-tail.log` (run 1 — captured both inbound `build_queued` and outbound `build_failed`), `phase7-pipeline-tail-2.log`, `phase7-pipeline-tail-3.log`, `phase7-pipeline-tail-4.log`
- `phase7-forge-logs.log` (run 1 — `pipeline_consumer ... outside allowlist`), `phase7-forge-logs-2.log`, `phase7-forge-logs-3.log` (run 3 — `no such table: builds`), `phase7-forge-logs-4.log` (run 4 — `dispatching autobuild` then `AttributeError`)
- `phase7-consumer-info.json`, `phase6.3-stream-state.json`
- Transcripts: `~/.jarvis/transcripts/{21df1258,b5c5e1e2,a55df422,f876fd47}-...txt` (4 files; the latest one — `f876fd47` — is the most informative because run 4 reached the deepest point in the dispatch chain)
- Routing-history offloads (FRR-003): `~/.jarvis/traces/{21df1258,b5c5e1e2,a55df422,f876fd47}-...json` (4 files, all 1124 bytes, full DDR-029 schema)

