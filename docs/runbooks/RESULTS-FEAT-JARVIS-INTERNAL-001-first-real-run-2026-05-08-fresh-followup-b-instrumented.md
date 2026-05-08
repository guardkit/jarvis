# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run — Fresh GB10 walkthrough, FOLLOWUP-A landed, FOLLOWUP-B instrumented

**Date:** 2026-05-08 (~14:13 → ~14:26 BST / 13:13 → 13:25 UTC)
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident first walkthrough
**Operator:** Claude (assistant-driven, runbook-following — fresh teardown then rebuild per operator instruction)
**Jarvis HEAD:** `30e4ae4`
**Forge HEAD:** `e1eef81` (`chore(FEAT-PEBR): instrument lifecycle_bridge for FOLLOWUP-B silent-stream spike`) — includes FOLLOWUP-A migration patch (`55f7804`) **and** FOLLOWUP-B SSE instrumentation
**Forge image:** `forge:latest` (rebuilt 4 minutes before this run by operator; sha `91ec963896`)
**correlation_id:** `1506e6c4-cc6a-4591-8dc0-d9258b231b11`
**Session id:** `cli-531ef2fe7b964ba3a2a7d906535dcb8b`

**Outcome:** ⏸ **Phases 0–6 GREEN; Phase 7 FAILs with refined-Signature-B fingerprint.** FOLLOWUP-A's migration is verified live (`forge-serve: applied 2 SQLite migration(s) at boot` + 0 `no such table` warnings under load); FOLLOWUP-B reproduces in its newly-instrumented form (autobuild_runner SSE stream IS producing `event='values'` parts, but the bridge translator emits zero outbound lifecycle envelopes).

---

## What this run did differently from the 2026-05-08 dryrun

The earlier dryrun ([`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-dryrun-wave2.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-dryrun-wave2.md)) ran against a stale `forge-prod` whose state carried 4 unacked redeliveries from earlier in the day. This run started **fully torn down** per operator request:

| Component | Action |
|---|---|
| `forge-prod` container | `docker rm -f` then re-`docker run` against the freshly-rebuilt image (`91ec963896`) |
| `~/forge-prod-state/.forge/forge.db*` | wiped — bridge_registry migration applied fresh on first boot (`applied 2 SQLite migration(s) at boot`) |
| `langgraph dev` sidecar | killed; `~/Projects/appmilla_github/forge/.langgraph_api/` cleared; rebooted on `:8124` with the stripped `langgraph.json` (autobuild_runner only) |
| `forge-serve` durable consumer on PIPELINE | deleted (`nats consumer rm PIPELINE forge-serve`) — fresh attach on next forge boot |
| PIPELINE stream messages | `nats stream purge PIPELINE -f` (cleared 4 redelivery-stuck messages) |
| NATS server, KV buckets, specialist-agent containers, graphiti-mcp, llama-swap | left running |
| Forge image build | NOT rerun (operator had just rebuilt) |

This is the cleanest possible reproduction: zero state carry-over from prior sessions on the forge side, full canonical NATS provisioning preserved.

---

## Per-phase outcomes

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | HEAD `30e4ae4`, working tree mods to runbook only |
| 0.2 | GB10 reachable | ✅ | Direct execution; `hostname=promaxgb10-41b1`; SSH prefix dropped per §0.2 |
| 0.3 | forge nats-core symlink | ✅ | Already in place from earlier setup |
| 0.4 | Provider keys + NATS auth + supervisor model | ✅ | `JARVIS_SUPERVISOR_MODEL=openai:qwen36-workhorse`; `JARVIS_NATS_URL` constructed inline from sourced `nats-infrastructure/.env` |
| 1.1 | NATS container up | ✅ | `ships-computer-nats Up 28 hours (healthy)` |
| 1.2 | 7 streams + 4 KV buckets | ✅ | `verify-nats.sh` reports `7 passed, 0 failed`; `nats kv ls` shows all 4 buckets |
| 1.3 | `pipeline.build-queued.*` bound to PIPELINE | ✅ | `Subjects: pipeline.>` |
| 2.0 | langgraph-runner sidecar (NEW in wave 2) | ✅ | Pre-flight 1 (kill + clear `.langgraph_api/`) ran; pre-flight 2's stripped config already on disk; sidecar booted on `:8124`; `Application started up in 0.632s`; `n_pending=0` (clean queue); openapi probe returned `"LangSmith Deployment"` |
| 2.1 | forge image rebuilt | ✅ (skipped — operator pre-built) | `forge:latest` 4 min old, 507MB; HEAD `e1eef81` |
| 2.2 | `forge serve` running | ✅ | Container booted with `--config /var/forge/forge.yaml`, `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124`, host-mounted DB at `/home/forge/.forge`. Boot log shows: `applied 2 SQLite migration(s) at boot` (FOLLOWUP-A) + `production composer bound (db_path=/home/forge/.forge/forge.db)` + `dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher` (PEBR-WIREUP) |
| 2.3 | `/healthz` green + consumer attached | ✅ | `{"status":"healthy"}` on `:8088`; fresh `forge-serve` durable on PIPELINE (created 14:16:23, 0 ack-pending, 0 unprocessed) |
| 3.1 | Architect container up | ✅ | `specialist-agent-architect-agent-1 Up 7 hours` + `specialist-agent-product-owner-agent-1 Up 7 hours` |
| 3.2 | Architect ping (optional) | ⚠️ skipped (not blocking; FEAT-JARVIS-INTERNAL-001 is documentation-only and triggers no specialist dispatch) |
| 4.1 | graphiti container up | ✅ | `graphiti-mcp Up 27 hours (healthy)` |
| 4.2 | Content-Type-guarded graphiti probe | ⚠️ HTML hijack (open-webui on :8080) — DDR-019 soft-fail offload path engaged as expected on GB10 |
| 4.3 | llama-swap embeddings | ✅ | `nomic-embed` returned `data[0].index = 0` |
| 5.1 | jarvis chat boots clean | ✅ | `jarvis_startup_complete` with `nats_available=true, capabilities_mode=live`, **zero `nats_*` warnings**. Two documented soft-fails reproduced (TAVILY_API_KEY + `graphiti_skipped_no_endpoint`). TASK-FRR-001's resolution holds. Evidence: [`/tmp/jarvis-runbook-evidence/phase5-boot.log`](/tmp/jarvis-runbook-evidence/phase5-boot.log) |
| 5.2 | tool inventory smoke | ✅ | Supervisor narrated `forge` capability (queue_build invocation path), `dispatch_by_capability`, plus 9 ambient tools |
| 6.1 | Boot fresh chat REPL with full tracing | ✅ | Non-interactive `printf | jarvis chat` pattern, `JARVIS_LOG_LEVEL=DEBUG`. Exit code 0 |
| 6.2 | `queue_build` returns success | ✅ | Supervisor returned the canonical bullet ack: `- **Correlation ID:**` `1506e6c4-…`, `- **Target:**` `pipeline.build-queued.FEAT-43DE`, `- **Queued at:**` `2026-05-08T13:19:45Z`. Slight prose variance from runbook example (`Target` vs `Publish target`) — runbook explicitly tolerates narration variance, only the bullet shape is load-bearing. Evidence: [`/tmp/jarvis-runbook-evidence/phase6-chat-narration.txt`](/tmp/jarvis-runbook-evidence/phase6-chat-narration.txt) |
| 6.3 | Wire shows publish on PIPELINE | ✅ | Wire-tap captured exactly 1 `BuildQueuedPayload` (760 B). PIPELINE last_seq advanced 21 → 22. Pre-publish consumer baseline `delivered=0, ack_floor=0` |
| 7.1 | Between-prompt notification narration | ✅ (in form — narration matches expected wave-2 FAIL framing) | Supervisor follow-up to "What is happening with that build?" narrated: *"Those events haven't arrived yet, which suggests Forge hasn't picked it up (or it's still processing)"* — exactly the runbook's expected behavior on a Phase 7 FAIL ("the chat REPL drains zero notifications and the reasoner narrates accordingly") |
| 7.2 | Wire shows envelope sequence | ❌ **expected FAIL** — refined Signature B | Across a 5m45s capture window: **1 inbound `BuildQueuedPayload`, 0 outbound `pipeline.build-started.*` / `stage-complete.*` / `build-complete.*` / `build-failed.*` envelopes**. Final consumer state: `delivered=12, ack_floor=0, num_pending=0, num_redelivered=1`. `ack_floor` never advanced — the canonical AC-11 fail signature |
| 7.3 | forge logs show autobuild flow | ❌ **expected FAIL** — refined Signature B | See "Refined-Signature-B forge log story" below. **Zero `emit_*` calls; zero outbound publishes; 5 lifecycle_bridge.attach cycles (1 initial + 4 redelivery); 30 stream parts received in cycle 1, 0 in cycles 2-5** |
| 8.1 | Save chat transcript | ✅ | `/home/richardwoollcott/.jarvis/transcripts/1506e6c4-cc6a-4591-8dc0-d9258b231b11.txt` (218 KB DEBUG-level transcript) |
| 8.2 | Graphiti routing-history dump | N/A (Graphiti port hijacked — soft-fail offload path) |
| 8.3 | DDR-019 offload trace | ✅ | `~/.jarvis/traces/1506e6c4-cc6a-4591-8dc0-d9258b231b11.json` — full DDR-029 routing-history schema with `outcome_type=success`, `subagent_type=forge_build_queue`, `outcome_detail.subject=pipeline.build-queued.FEAT-43DE` |
| 8.4 | command_history.md | ✅ (this run appended) |

---

## Decisive evidence for Phase 7 expected FAIL

### Final wire state (after 5m+ post-publish window)

```json
{ "delivered": 12, "ack_floor": 0, "pending": 0, "redelivered": 1 }
```

(`/tmp/jarvis-runbook-evidence/phase7-final-consumer-info.json`)

`ack_floor=0` is the load-bearing fingerprint — JetStream redelivered the inbound message 11 times after the original delivery without ever seeing a terminal ack from forge.

### Wire tap content (`pipeline.>` for 5m45s)

```json
{
  "message_id": "943ccf3e-3bcb-400c-8804-8561062decac",
  "timestamp": "2026-05-08T13:19:45.615946Z",
  "event_type": "build_queued",
  "source_id": "jarvis",
  "correlation_id": "1506e6c4-cc6a-4591-8dc0-d9258b231b11",
  "payload": { "feature_id": "FEAT-43DE", "repo": "guardkit/jarvis", "branch": "main", ... }
}
```

(one and only one envelope; zero `build-started` / `stage-complete` / `build-complete` / `build-failed` follow-ups)

---

## Refined-Signature-B forge log story

This run's forge log signature is **substantially richer** than the runbook's documented Signature B (`stream session open ... → stream exhausted parts_received=0`), because forge HEAD `e1eef81` adds the FOLLOWUP-B SSE instrumentation that exposes per-part details.

**Cycle 1 — fresh dispatch (13:19:45 → ~13:21:30):**

```text
13:19:45 lifecycle_bridge.attach feature_id=FEAT-43DE thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE
13:19:45 wireup.register_ack_handle: attached ... observer task scheduled (deadline_at=13:24:45)
13:19:45 pipeline_consumer: dispatching build ... bridge=wired
13:19:45 dispatch_build: persisted QUEUED row build_id=build-FEAT-43DE-20260508131945
13:19:45 httpx: POST http://localhost:8124/threads → 200
13:19:45 httpx: POST http://localhost:8124/threads/<thread>/runs → 200
13:19:45 dispatch_autobuild_async: launched task_id=019e07be-8000-77c1-a6b6-24feec32d330
13:19:46 wireup._observer_loop: identity resolved feature_id=FEAT-43DE thread_id=019e07be-8000-77c1-a6b6-24feec32d330 run_id=019e07be-8002-7ba2-b81a-0e1e3995271a
13:19:46 wireup._drive_stream_session: stream session open
13:19:46 httpx: GET http://localhost:8124/threads/<thread>/runs/<run>/stream → 200

13:19:51 stream_part received n=1 event='values' data_keys=['messages']
13:19:51 stream_part received n=2 event='values' data_keys=['messages', 'todos']
... (continuing through n=22 over ~2 minutes) ...
13:21:29 stream_part received n=30 event='values' data_keys=['files', 'messages', 'todos']
```

**Critical observation (NEW vs runbook expectation):**
- The runbook's Signature B says: *"stream session opens cleanly but **zero outbound envelopes** ever land on the wire. Hypothesis: the autobuild_runner subagent runs a long deepagents tool loop without producing the `_update_state` transitions the bridge translator looks for."*
- Today's evidence narrows that hypothesis: **the autobuild_runner IS producing state updates** (30 `event='values'` parts received with `data_keys=['files','messages','todos']`), but the bridge translator does not interpret deepagents' generic `values` events as stage-lifecycle transitions. **The gap is in the translator's recognition of `values`/`messages`/`todos` events as stage transitions, not in autobuild_runner's emission discipline.**
- `event_types` distinct across the entire run: `{'values'}` only — no `stage_started` / `stage_complete` / `build_complete` event names ever appear in the SSE stream.

**Cycles 2-5 — JetStream ack-wait redeliveries (every 30s after cycle 1's deadline):**

```text
13:25:16 stream exhausted feature_id=FEAT-43DE parts_received=0 event_types={} terminal_seen=False
13:25:16 stream for feature_id=FEAT-43DE ended without a terminal envelope; leaving inbound queued message un-acked
         (JetStream will redeliver, deadline timer will publish build-failed if the sidecar stays unreachable)
13:25:45 lifecycle_bridge.attach (redelivery 4) feature_id=FEAT-43DE thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE
13:25:45 dispatch_build: duplicate active build for feature_id=FEAT-43DE ... skipping dispatch
13:25:45 wireup._drive_stream_session: stream session open  ← reopens against original run_id
13:25:46 stream exhausted feature_id=FEAT-43DE parts_received=0 event_types={}  ← original run finished long ago, stream returns nothing
```

The `parts_received=0` on cycles 2-5 is **a different failure mode** than cycle 1's `parts_received=30`. Cycle 1 received 30 parts but the translator emitted nothing; cycles 2-5 received 0 parts because the original SSE stream was already drained (the autobuild_runner run had ended before the redelivery cycle re-attached). Both modes converge on `terminal_seen=False` → un-acked → redeliver.

**Counts across the full session window (60 → 156 lines):**

| Marker | Count |
|---|---|
| `lifecycle_bridge.attach` | 5 |
| `stream session open` | 5 |
| `stream exhausted` | 5 |
| `stream_part received` | 69 (cycle 1: 30; cycles 2-5: 0 each) |
| `duplicate active build` | 12 |
| `register_ack_handle: attached` | 5 (no `register_ack_handle raised`) |
| `no such table` (Signature A marker) | **0** ← FOLLOWUP-A confirmed live |
| `publish .* pipeline\.(build|stage)` | **0** |
| `emit_*` | **0** |

---

## What this run validates

1. **FOLLOWUP-A migration is in production** — the running `forge-prod` container, booted from a wiped `forge.db`, ran `applied 2 SQLite migration(s) at boot` and saw zero `register_ack_handle raised (no such table)` warnings under 12 dispatch attempts. Signature A is fully resolved.
2. **PEBR-WIREUP is in production** — the boot log carries the exact fingerprint from the runbook (`forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)`).
3. **Wave-2 expected Phase 7 FAIL is canonical** — the chat REPL renders zero notifications, the supervisor narrates accordingly, the wire confirms zero outbound envelopes, the consumer's `ack_floor=0` proves the deferred-ack contract held (forge correctly chose not to ack a build it couldn't terminate), and JetStream's redelivery cycle is functioning as designed.
4. **Operator runbook is verbatim-runnable** when freshly torn down — 0 manual gap-folds during execution. The wave-2 Pre-flight 1/2 + post-boot Queue stats verification (W3-4 fold) prevented the qwen36-workhorse contention failure mode that blocked Phase 6.2 in the dryrun.
5. **DDR-019 offload + transcripts capture cleanly** — both `~/.jarvis/traces/<correlation_id>.json` (DDR-029 schema) and `~/.jarvis/transcripts/<correlation_id>.txt` (218 KB DEBUG transcript) landed on first attempt.

---

## What this run reveals beyond the runbook's documented expectations

### Refines FOLLOWUP-B's hypothesis with evidence

The runbook's Signature B says *"the autobuild_runner subagent does not drive the `_update_state` transitions the bridge translator looks for"*. Today's evidence (forge HEAD `e1eef81`'s instrumentation) is more specific:

- The autobuild_runner IS streaming state updates over SSE (`event='values'` with `data_keys=['files', 'messages', 'todos']`)
- The bridge translator does NOT recognize these as stage-lifecycle transitions
- The translator appears to be looking for events with specific stage-lifecycle event names (e.g. `stage_started`, `stage_complete`), not deepagents' generic `values`-shaped state-update broadcasts

This suggests the FOLLOWUP-B fix surface is in **at least one of two places**:

| Location | Possible fix | Tradeoff |
|---|---|---|
| `forge.lifecycle_bridge.translator` | Teach the translator to interpret `event='values'` parts as stage transitions (e.g. infer stage from `messages` content, or emit a synthetic `build-started` on first `values` part and `build-complete` on stream end) | Couples the translator to deepagents' state shape; risks misinterpreting partial state updates |
| `forge.subagents.autobuild_runner` | Have autobuild_runner explicitly emit named stage-transition events (e.g. via a custom SSE event type `stage_started=<n>`) alongside the deepagents `values` updates | Requires autobuild_runner to know about the lifecycle envelope contract; couples it to the bridge consumer |

This is now an actionable surface for a focused FOLLOWUP-B sub-task, with concrete reproduction.

### The deferred-ack-deadline path doesn't fire when the SSE stream is reachable

The runbook says *"deadline timer will publish build-failed if the sidecar stays unreachable"*. In today's run the sidecar is fully reachable; the SSE stream just doesn't produce translator-recognized events. So **after the 5-min deadline at 13:24:45, no `build-failed` envelope was published** — the deadline-driven failure path appears gated on stream unreachability, not on stream silence. This is correct behavior given the contract (don't publish failure if we don't know the build failed) but worth noting for any wave-3 close-criterion update — the runbook's "deadline timer will publish build-failed" needs an "...if the SSE stream itself fails" qualifier.

---

## Wave-3 candidates (none blocking AC-12; observational)

| # | Section | Wave-3 candidate | Severity |
|---|---|---|---|
| W3-A | §7 expected-FAIL framing | Update Signature B description to reflect FOLLOWUP-B instrumentation now in place at HEAD `e1eef81`+: cycle 1 produces `parts_received=N>0` (not 0); cycles 2+ produce `parts_received=0` due to original-run-already-drained, not due to original-run-empty. The runbook conflates these | Low (cosmetic — both are "expected FAIL today") |
| W3-B | §7 deadline qualifier | Add an "...if the SSE stream itself fails (not merely silent)" qualifier to the deadline-timer note. With reachable-but-translator-silent streams, no `build-failed` is published even after the 5-min deadline expires | Low (correctness of expectation) |
| W3-C | §6.2 narration variance | Supervisor used `- **Target:**` rather than `- **Publish target:**`. Runbook already explicitly tolerates narration variance ("exact narration prose ... may vary turn-to-turn"); just adding a third example string to the prose-tolerance comment would be a minor polish | Cosmetic |

None of these gate AC-11 (Phase 7 close) or AC-12 (operator-runbook-verbatim-runnable). All three are forward-references for a wave-3 fold once FOLLOWUP-B's translator-vs-emission-discipline question is resolved.

---

## Decision

- [x] **Phases 0–6 close canonical** — runbook is verbatim-runnable on a freshly-torn-down GB10; zero manual gap-folds during execution
- [x] **Phase 7 expected-FAIL signature reproduces deterministically** — refined Signature B (FOLLOWUP-B SSE-instrumented) with full forge-side log evidence captured
- [ ] **AC-11 (Phase 7 close-criterion that the wire shows the envelope sequence)** still NOT MET — gated on FOLLOWUP-B translator/emission resolution
- [x] **AC-12 (operator-fresh-runbook-runnable)** validated end-to-end through Phase 7 evidence capture; the wave-2 fold is operator-runnable today

**Recommended follow-ups:**

1. **forge-followup-FOLLOWUP-B**: investigate whether the fix lives in `forge.lifecycle_bridge.translator` (interpret `event='values'` as transitions) or in `forge.subagents.autobuild_runner` (emit named stage events). Today's evidence narrows the hypothesis but doesn't choose between the two surfaces — that's a forge-side investigation. The 5-min deadline path also needs review for the "reachable but silent" case.
2. **wave-3 runbook fold**: pick up W3-A / W3-B / W3-C when FOLLOWUP-B's resolution lands and the next walkthrough can refresh the §7 framing against the new ground truth.
3. **Defer the MacBook-over-Tailscale walkthrough** until after FOLLOWUP-B lands — the wave-2 dryrun's recommendation still holds: the network-isolated rerun adds no new evidence today, only retests publish→consume which we just proved cleanly.

---

## Evidence index

All under `/tmp/jarvis-runbook-evidence/` (timestamps 14:13 → 14:26 BST):

| File | Phase | Description |
|---|---|---|
| `phase1-verify-nats.log` | 1.2 | `verify-nats.sh` self-report `7 passed, 0 failed` (auth sourced) |
| `phase5-boot.log` | 5.1 | Clean jarvis chat boot (`nats_available=true, capabilities_mode=live`, 0 NATS warnings) |
| `phase6-pre-stream-info.json` | 6.3 | PIPELINE pre-publish (`messages=0, last_seq=21, consumers=1`) |
| `phase6-pre-consumer-info.json` | 6.3 | forge-serve pre-publish (`delivered=0, ack_floor=0` — fully fresh) |
| `phase6-chat.log` | 6.1/6.2 | Full DEBUG-level chat transcript (218 KB) |
| `phase6-chat-narration.txt` | 6.2 | User-facing narration only (markdown bullets + supervisor narration) |
| `phase7-pipeline-tap.log` | 6.3/7.2 | Wire tap of `pipeline.>` for 5m45s (760 B; 1 inbound, 0 outbound) |
| `phase7-final-stream-info.json` | 7.2 | PIPELINE post-window (`messages=1, last_seq=22`) |
| `phase7-final-consumer-info.json` | 7.2 | forge-serve post-window (`delivered=12, ack_floor=0, redelivered=1`) — AC-11 fail fingerprint |
| `phase7-forge-prod-logs-final.log` | 7.3 | Full forge-prod docker logs (156 lines, 11 KiB) covering all 5 redelivery cycles |
| `~/.jarvis/transcripts/1506e6c4-cc6a-4591-8dc0-d9258b231b11.txt` | 8.1 | Chat transcript (copy of phase6-chat.log) |
| `~/.jarvis/traces/1506e6c4-cc6a-4591-8dc0-d9258b231b11.json` | 8.3 | DDR-019 soft-fail offload trace (DDR-029 schema) |

---

## See also

- [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — the runbook executed (HEAD `30e4ae4` wave-2 fold)
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-dryrun-wave2.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-dryrun-wave2.md) — the same-day dryrun against stale state
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md) — the human-driven walkthrough that drove the wave-2 fold
