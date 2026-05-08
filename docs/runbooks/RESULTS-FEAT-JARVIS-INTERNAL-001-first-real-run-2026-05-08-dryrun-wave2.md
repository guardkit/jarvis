# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run — Dry-run of wave-2 runbook fold

**Date:** 2026-05-08 (~13:00 → ~13:27 BST / 12:00 → 12:27 UTC)
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident
**Operator:** Claude (assistant-driven dry-run; AC-12 partial validation only — see "AC-12 self-validation caveat")
**Purpose:** Validate the wave-2 fold of [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) committed in `30e4ae4` (TASK-FRR-RUNBOOK-002), measuring AC-12: *"A second operator on a clean GB10 (or near-clone over Tailscale) can execute the runbook from cold through Phase 6 with no manual gap-fold, only env-pointing differences."*
**Forge HEAD:** `1b82236` (PEBR-WIREUP) plus an uncommitted FOLLOWUP-A patch on `_serve_production.py` (mtime 12:47 BST today, completed task file 12:52 BST)
**Jarvis HEAD:** `30e4ae4` (the wave-2 runbook fold)
**Image used:** `forge:latest sha 2705612d4635` — built 11:36 BST today **before** the FOLLOWUP-A patch was applied; therefore the running container is pre-FOLLOWUP-A even though the source tree has the patch staged
**Persistent DB:** `~/forge-prod-state/.forge/forge.db` — already had `lifecycle_bridge_registry` table from the 2026-05-08 hot-fix; this means the running pre-FOLLOWUP-A image effectively bypasses the FOLLOWUP-A failure mode at runtime via persistent DB state

**Outcome:** ⏸ **Phases 0–5 GREEN; Phase 6 BLOCKED by environmental contention; Phase 7 expected-FAIL Signature B is fully reproduced from existing forge-prod state.** Wave-2 runbook fold validates with **zero manual gap-folds during execution**, three minor wave-3 polish candidates flagged.

---

## AC-12 self-validation caveat

The dry-run was driven by the same agent that authored the wave-2 fold (per the Phase 5 decision-checkpoint preamble in TASK-FRR-RUNBOOK-002). This means **AC-12 is only partially validated** — a fresh-eyes operator may still trip on documentation that this agent silently smoothed over from full context. The findings below honestly flag every place I deviated from the runbook text or had to consult §0.4 mid-flight, so a future fresh-operator dry-run can target those known soft spots first.

---

## Per-phase outcomes

| Phase | Gate | Outcome | Notes |
|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | HEAD `30e4ae4`, 37 commits past `2864173` (close commit), clean working tree |
| 0.2 | GB10 reachable | ✅ | Running directly on GB10 (`hostname=promaxgb10-41b1`, `/etc/hosts` → `127.0.0.1`); SSH prefix dropped per runbook §0.2 note |
| 0.3 | forge nats-core symlink | ✅ | Symlink in place from 2026-05-01 (one-time fix) |
| 0.4 | Provider keys + NATS auth + supervisor model | ✅ (with wave-3 candidate) | `JARVIS_SUPERVISOR_MODEL=openai:qwen36-workhorse` in `.env`. **`JARVIS_NATS_URL` not in `.env`** — required sourcing `nats-infrastructure/.env` and exporting inline (per §0.4 guidance). Wave-3 candidate: §5.1 boot recipe doesn't cross-reference §0.4's NATS-URL guidance |
| 1.1 | NATS container up | ✅ | `ships-computer-nats Up 27 hours (healthy)` |
| 1.2 | 7 streams + 4 KV buckets verified | ✅ (with wave-3 candidate) | `verify-nats.sh` self-reports `7 passed, 0 failed` per runbook pass criterion. **However**, Check 5 (stream-count) silently reports all 7 streams MISSING due to a script-internal auth-passthrough bug; direct `nats stream ls` query confirms streams ARE present. Wave-3 candidate: fix `verify-nats.sh` Check 5 to accept the same NATS_URL/creds as the rest of the script |
| 1.3 | `pipeline.build-queued.*` bound to PIPELINE | ✅ | `Subjects: pipeline.>` (covers `build-queued.>`) |
| 2.0 | langgraph-runner sidecar (NEW) | ✅ | **First real validation of the wave-2 §2.0 fold.** Stripped `langgraph.json` written, sidecar booted on `:8124`, openapi probe returned `"LangSmith Deployment"` (runbook expected `"LangGraph API"` — both satisfy the "non-empty title" pass criterion; minor wave-3 polish: update §2.0 expected-title text). `Application started up in 1.063s`, `graph_id=autobuild_runner` loaded |
| 2.1 | forge image rebuilt at HEAD `1b82236` | ✅ (DEVIATION) | Skipped the literal `git pull --ff-only && docker buildx build` rebuild — image was already at sha `2705612d4635` from HEAD `1b82236`. A fresh-clean-GB10 operator would need to run the rebuild for real. Verifiable precondition met; honest deviation flagged |
| 2.2 | `forge serve` running | ✅ (DEVIATION) | Existing `forge-prod` container already had the wave-2 config (`--config /var/forge/forge.yaml`, `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124`, `-v ~/forge-prod-state/.forge:/home/forge/.forge`) — the recipe had been executed earlier today. Skipped destructive `docker rm -f forge-prod` + re-`docker run` since it would reproduce the same state. Pre-flights validated by inspection: `forge.yaml` schema correct, host DB dir exists with uid 1000 ownership |
| 2.3 | `/healthz` green + consumer attached + dispatch chain composed | ✅ | `{"status":"healthy"}` on `:8088`. `forge-serve` durable consumer present. Daemon log shows `forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)` — proves PEBR-WIREUP is in the running image |
| 3.1 | Architect container up | ✅ | `specialist-agent-architect-agent-1 Up 6 hours` |
| 3.2 | Architect ping (optional) | ✅ | rtt 1.4 ms, response `{"stream":"AGENTS","seq":6}` |
| 4.1 | graphiti container up | ✅ | `graphiti-mcp Up 26 hours (healthy)` — wave-2 §4.1 caveat refresh accurately reflects current state |
| 4.2 | Content-Type-guarded graphiti probe (NEW) | ✅ | **First real validation of the wave-2 §4.2 fold.** Probe correctly returned `"graphiti unreachable (got HTML — likely port hijack by another service such as open-webui)"` against `localhost:8080`. The historical bare `curl -sf` would have returned 200 OK from open-webui's splash and falsely reported success. Soft-fail offload path engaged (DDR-019) |
| 4.3 | llama-swap embeddings | ✅ | `nomic-embed` returned `data[0].index = 0` |
| 5.1 | jarvis chat boots clean | ✅ | **Wave-2 §5.1 fold validated.** `jarvis_startup_complete` with `nats_available=true, capabilities_mode=live` and **zero `nats_*` warnings**. Only the two documented non-NATS lines (TAVILY_API_KEY missing + `graphiti_skipped_no_endpoint`). TASK-FRR-001's resolution holds. Evidence: [`phase5-boot.log`](/tmp/jarvis-runbook-evidence-dryrun-20260508-120044/phase5-boot.log) |
| 5.2 | tool inventory smoke | (folded into 6) | 10 attended tools / 9 ambient tools assembled per startup log |
| 6.1 | Boot a fresh chat REPL with full tracing | ✅ | Booted with `JARVIS_LOG_LEVEL=DEBUG`, non-interactive `printf | jarvis chat` pattern from §6.1 |
| 6.2 | `queue_build` returns success | ⏸ **BLOCKED** | **Did not complete in 180s.** `qwen36-workhorse` model has `-np 1` (single parallel slot per `llama-server` config); the langgraph sidecar's autobuild_runner backlog (residual from earlier today's FOLLOWUP-A development — 7 pending runs at sidecar boot, run-queue wait time 4992s) is making continuous `POST /v1/responses` calls every ~5s, holding the qwen36-workhorse slot. Interactive REPL queues behind. **Wave-3 candidate**: runbook should warn that an active autobuild_runner backlog blocks the §6.x interactive REPL on `np=1` model fleets, and suggest stopping/draining the sidecar before queue tests. **Phase 6 markdown-bullet shape was already validated against the 2026-05-08 walkthrough's `phase6-chat.log` during the review pass; not re-validated this session** |
| 6.3 | Wire shows publish | ⏸ **N/A** | No new publish from this session. Existing wire state captured |
| 7.1 | Confirm forge consumed and acked + FAIL signature matches | ✅ **Signature B reproduced** | Existing forge-prod state (from prior 2026-05-08 walkthrough's still-cycling redeliveries) shows: 254 `lifecycle_bridge.attach` / `observer task scheduled` / `already has a live observer` log lines across 30-min window, **zero outbound envelopes**, `ack_floor=11` stuck (matches the 2026-05-08 walkthrough's AC-11 fail signature). **No `register_ack_handle raised (no such table: lifecycle_bridge_registry)` errors** — Signature A does not reproduce because the host-mounted `forge.db` already had the migration applied via the 2026-05-08 hot-fix. The runbook's "either signature is expected FAIL today" framing handled this correctly |
| 7.2 | Verify envelope sequence on the wire | ✅ (from existing state) | Wire-tap captured 0 outbound envelopes during 30-min window — consistent with FOLLOWUP-B (bridge attaches but never publishes terminal envelope). The observer loop logs `stream for feature_id=FEAT-43DE ended without a terminal envelope` repeatedly — exactly the FOLLOWUP-B hypothesis the runbook documents |
| 7.3 | Tail forge logs for same correlation_id | ✅ | Captured `phase7-forge-prod-logs.log` (195 KiB, 30-min window). Includes the bridge-attach signature, observer timeouts, and zero `emit_*` / `publish_lifecycle_*` log lines |
| 8.1-8.4 | Evidence capture | ✅ (partial) | `phase5-boot.log`, `phase6-chat.log`, `phase6-pre-{stream,consumer}-info.json`, `phase7-final-{stream,consumer}-info.json`, `phase7-forge-prod-logs.log` saved at `/tmp/jarvis-runbook-evidence-dryrun-20260508-120044/`. `phase6-pipeline-tap.log` empty (0 bytes) — no new publishes captured this session, but tap was alive for ~3 min before being killed in cleanup |

---

## Decisive evidence for the wave-2 expected FAIL

```json
{
  "delivered": 8110,
  "ack_floor": 11,         <-- never advanced; this alone is the AC-11 fail signature
  "num_pending": 0,
  "num_redelivered": 4
}
```

(`/tmp/jarvis-runbook-evidence-dryrun-20260508-120044/phase7-final-consumer-info.json`)

```text
2026-05-08T12:00:55 [WARNING] forge.lifecycle_bridge.wireup: wireup._observer_loop:
  stream for feature_id=FEAT-43DE ended without a terminal envelope;
  leaving inbound queued message un-acked
  (JetStream will redeliver, deadline timer will publish build-failed if the sidecar stays unreachable)
```

(repeated 15× across 30 min, one per redelivery cycle for each of 4 unacked feature_ids)

```text
2026-05-08T11:57:31 [INFO] forge.lifecycle_bridge.bridge:
  lifecycle_bridge.attach feature_id=FEAT-43DE
  correlation_id=5673965b-e302-4a10-89cb-ceb430e64995
  thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE
```

(`pending-FEAT-43DE` placeholders never replaced — exactly the FOLLOWUP-B hypothesis: bridge initialised with placeholders, autobuild_runner subagent never drives the `_update_state` transitions the bridge translator needs to thread real `task_id`/`run_id` through)

---

## Wave-3 candidates discovered during this dry-run

The wave-2 fold validates as written, but the dry-run surfaced **five operator-facing polish candidates** for a future wave-3 pass. None block AC-12; all are quality-of-life improvements.

| # | Section | Wave-3 candidate | Severity |
|---|---|---|---|
| W3-1 | §5.1 boot recipe | Doesn't inline-reference §0.4's `JARVIS_NATS_URL` guidance; a fresh operator who skipped past §0.4 carefully might hit the "missing JARVIS_NATS_URL credentials" failure mode the §5.1 fallback already documents. Add a one-line cross-reference at the top of §5.1: *"Pre-flight: confirm `JARVIS_NATS_URL` is exported per §0.4."* | Low |
| W3-2 | §1.2 verify-nats.sh | Self-reports `7 passed, 0 failed` per the runbook's pass criterion, but Check 5 (stream count) silently reports all 7 streams MISSING because the check doesn't pass the same NATS_URL/creds as the rest of the script. The streams ARE present (verified via direct `nats stream ls` query). Either fix `nats-infrastructure/scripts/verify-nats.sh` Check 5, or add a runbook step to cross-check stream presence with `nats stream ls --server "nats://rich:..."` | Low (false-PASS not false-FAIL) |
| W3-3 | §2.0 expected sidecar title | Runbook says: *"`curl` returns a non-empty title (`"LangGraph API"` or similar)"*. Actual title against current `langgraph dev` is `"LangSmith Deployment"`. Both satisfy "non-empty title" — minor polish to update the example | Cosmetic |
| W3-4 | §6.x autobuild-runner backlog warning | An active autobuild_runner backlog (which can build up due to FOLLOWUP-A/-B causing un-acked redeliveries, OR from prior development sessions) holds the supervisor model's single `np=1` slot and blocks the §5.1/§6.x interactive REPL indefinitely. The runbook should add a §1.x or §2.x "Pre-flight: confirm no active sidecar with backlog" check (e.g. *"`curl -s http://localhost:8124/runs | jq '.[] | select(.status == "pending" or .status == "running")' | wc -l` should return 0; if non-zero, restart the sidecar with a fresh in-memory queue before proceeding"*) | ✅ **Resolved 2026-05-08** — see follow-up fold below |
| W3-5 | Known-issues table | My fold's "Known issues" table says FOLLOWUP-A is "filed but not landed". As of today **2026-05-08 12:52 BST**, the FOLLOWUP-A patch has been completed (in `tasks/completed/forge-autobuild-runner-pipeline-emitter-bridge/`) and the source patch is staged in the forge working tree, though the running image was built before the patch. **Once the FOLLOWUP-A patch image-rebuilds**, the runbook's Phase 7 expected-signature framing should demote Signature A and promote Signature B as the primary expected-FAIL signature. Wave-3 timing depends on when the image rebuild ships | Low (documentation freshness) |

---

## Decision

- [x] **Wave-2 runbook fold validated** for Phases 0–5 (with explicit deviations flagged) and Phase 7 expected-FAIL signature (from existing forge-prod state)
- [ ] Phase 6.2 (fresh-publish from this session) **NOT validated** due to environmental contention (W3-4)
- [x] **AC-12 partial-pass** — the wave-2 fold is sufficient for a fresh operator to execute Phases 0–5 without manual gap-folds; Phase 6 has a non-runbook environmental gating issue that should be flagged in a wave-3 update

**Recommended next steps** (operator decision, not assistant-driven):

1. ~~**Apply the W3-4 §6.x backlog warning fold**~~ — ✅ done in same session (see W3-4 follow-up fold below).
2. **Apply the W3-1 / W3-2 / W3-3 polish folds** when convenient.
3. **Defer W3-5** until the FOLLOWUP-A patch image-rebuilds; then refresh the Known issues table to demote Signature A.
4. **Run a fresh-eyes operator dry-run** (different person from the wave-2 fold author) to validate AC-12 with full credibility — this dry-run can only attest to "no obviously broken text".
5. **Close TASK-FRR-RUNBOOK-002** when the operator agrees the partial-pass is enough — this assistant declined to invoke `/task-complete` automatically given the AC-12 self-validation caveat.

---

## W3-4 follow-up fold (2026-05-08, same session)

User directed an immediate fix for W3-4 (the only blocking wave-3 candidate). Applied to `RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`:

1. **§2.0 — Pre-flight 1 (NEW)**: kills any pre-existing `langgraph dev` process and clears `~/Projects/appmilla_github/forge/.langgraph_api/` (where `langgraph dev` persists its in-memory queue across restarts via pickle files — `.langgraph_checkpoint.*.pckl`, `.langgraph_ops.pckl`). Ensures the §6.x interactive REPL has a clean supervisor-model slot. With explicit operator opt-out language for those who are actively using `langgraph dev` for parallel forge dev work and need to preserve in-flight state.

2. **§2.0 — post-boot "Queue stats" verification (NEW)**: greps the first `Queue stats` line out of `/tmp/langgraph-sidecar.log` for `n_pending=0`. Three branches: `OK: no Queue stats line yet (queue is empty)`, `OK: queue starts clean (n_pending=0)`, or `FAIL: queue has N pending runs from a prior session — pre-flight 1 missed something`. The FAIL branch directs the operator to find the actual `.langgraph_api/` location (in case the runbook's assumed path was wrong on their host) and retry §2.0.

3. **§6 — symptom-recovery hint (NEW)**: short note at the top of Phase 6 explaining the contention symptom (REPL hangs at `session_started`) and the recovery (pkill, rm -rf, restart §2.0). Catches the recurrence case where §6 is re-run within the same runbook session and the sidecar has accumulated a fresh backlog from the *first* §6 run's un-acked redeliveries.

4. **§2.0 W3-3 cosmetic fix piggybacked**: the expected sidecar title was updated from `"LangGraph API"` to mention both `"LangSmith Deployment"` (current) and `"LangGraph API"` (older versions). Both satisfy the "non-empty title" pass criterion.

**Validation of the W3-4 fold:**

The new §2.0 Pre-flight 1 + post-boot verification was dry-run end-to-end on the same GB10 immediately after the fold:

```text
=== Pre-flight 1: kill stale sidecar + clear .langgraph_api/ ===
OK: port 8124 free, .langgraph_api/ cleared

=== Pre-flight 2: stripped langgraph.json present ===
-rw-rw-r-- 1 richardwoollcott richardwoollcott 192 May  8 12:04 /home/richardwoollcott/forge-runner-only-langgraph.json

=== sidecar boot ===
LISTEN 0   2048   127.0.0.1:8124   0.0.0.0:*   users:(("python3",pid=3244015,fd=5),("langgraph",pid=3244009,fd=5))

=== openapi probe ===
"LangSmith Deployment"

=== Queue stats grep ===
OK: no Queue stats line yet (queue is empty — no work has been enqueued)
```

All four checks pass. The fold works as written. The validation sidecar was killed and `.langgraph_api/` removed at the end (cleanup verified — port 8124 free, directory absent).

**Wave-3 status update**: W3-4 ✅ resolved; W3-3 ✅ resolved (piggybacked); W3-1 / W3-2 / W3-5 still open as polish candidates.

---

## Cleanup

The dry-run started a `langgraph dev` sidecar (pid 3152912 + 3152929) and a `nats sub` wire-tap (pid 3163232) that were not pre-existing on the GB10. Both were terminated at the end of this session via `pkill`. Verify with:

```bash
ss -lntp 2>/dev/null | grep ":8124"   # should be empty (sidecar gone)
ps aux | grep -E "langgraph dev|nats.*sub.*pipeline" | grep -v grep   # should be empty
```

The forge-prod container, NATS, graphiti-mcp, specialist-agent containers, and llama-swap services were **not modified** by this dry-run — they were already running and remain running.

The `~/forge-runner-only-langgraph.json` file written for §2.0 pre-flight remains on disk (intentional — operators will reuse it).

The `~/forge-prod-state/.forge/forge.db` was not modified.

---

## Evidence index

All evidence files preserved at `/tmp/jarvis-runbook-evidence-dryrun-20260508-120044/`:

| File | Phase | Description |
|---|---|---|
| `phase5-boot.log` | 5.1 | Clean jarvis chat boot (0 NATS warnings, `jarvis_startup_complete` clean) |
| `phase6-chat.log` | 6.1/6.2 | jarvis chat boot for Phase 6 — terminated at `session_started` due to qwen36-workhorse contention (W3-4); no model output captured |
| `phase6-pre-stream-info.json` | 6.3 | PIPELINE state pre-Phase-6 (`last_seq=21, messages=4`) |
| `phase6-pre-consumer-info.json` | 6.3 | forge-serve consumer state pre-Phase-6 (`ack_floor=11, delivered=7968, num_redelivered=4`) |
| `phase6-pipeline-tap.log` | 6.3/7.2 | Wire-tap output — 0 lines (no new publishes from this session) |
| `phase7-final-stream-info.json` | 7 | PIPELINE state at end (`last_seq=21` — unchanged) |
| `phase7-final-consumer-info.json` | 7 | forge-serve consumer at end (`delivered=8110, ack_floor=11, num_pending=0, num_redelivered=4` — `ack_floor` never advanced; AC-11 fail signature) |
| `phase7-forge-prod-logs.log` | 7.3 | Full forge-prod docker logs from 30-min window — 254 bridge-attach lines, 15 observer-loop "stream ended without terminal envelope" warnings, 0 outbound envelope publishes |

---

## See also

- [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — the runbook under test (HEAD `30e4ae4`, wave-2 fold)
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08-post-pebr-wireup.md) — the human-driven 2026-05-08 walkthrough that drove the wave-2 fold
- [`.claude/reviews/TASK-FRR-RUNBOOK-002-review-report.md`](../../.claude/reviews/TASK-FRR-RUNBOOK-002-review-report.md) — the TASK-FRR-RUNBOOK-002 review report (Phase 1-4 of `/task-review`)
- [`tasks/in_progress/feat-jarvis-internal-001-followups/TASK-FRR-RUNBOOK-002-gap-fold-runbook-for-post-pebr-wireup-topology.md`](../../tasks/in_progress/feat-jarvis-internal-001-followups/TASK-FRR-RUNBOOK-002-gap-fold-runbook-for-post-pebr-wireup-topology.md) — the task itself
