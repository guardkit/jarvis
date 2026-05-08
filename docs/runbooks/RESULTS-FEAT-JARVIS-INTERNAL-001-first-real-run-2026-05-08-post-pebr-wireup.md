# RESULTS: FEAT-JARVIS-INTERNAL-001 First Real Run — Rerun (post-PEBR-WIREUP)

**Date:** 2026-05-08 (~10:43 → ~10:55 UTC)
**Machine:** GB10 (`promaxgb10-41b1`) — co-resident (host = `127.0.0.1` per `/etc/hosts`)
**correlation_ids captured:**
- `af772739-9ebf-473b-b8b7-32c234ccdb73` — first queue, pre-hot-fix
- `7657ed5a-8d24-4c78-b615-aef7bf835b74` — second queue, post-hot-fix-attempt-1 (still no envelopes)
- The `5673965b-...` and `e9433033-...` correlation_ids are residual redeliveries from earlier sessions
**Forge HEAD:** `1b82236` (`fix(FEAT-PEBR): compose LifecycleBridgeWireup in bind_production_serve`)
**Jarvis HEAD:** `60cee6b` (post-DSR-004 W3 partial)
**Image rebuilt:** `forge:latest` = `forge:production-validation` (sha `2705612d4635`, built 2026-05-08 11:36 BST from `1b82236`)
**Sidecar:** `langgraph dev` from `~/Projects/appmilla_github/forge/.venv/bin/langgraph` against a stripped `langgraph.json` containing only the `autobuild_runner` graph (the canonical `langgraph.json` couldn't load — `orchestrator` graph fails with `No module named 'agents'`, unrelated to this run).

**Outcome:** ⏸ **Phases 0–6 GREEN; Phase 7 FAIL with a new failure mode discovered.** The runbook revalidation (AC-11 of TASK-FORGE-FRR-PEBR-WIREUP) caught **two distinct integration gaps** that block the per-stage envelope sequence on the wire:

1. **Boot-time migration drift (the AC-11 catch).** `bind_production_serve` applies the canonical 5 tables and the `lifecycle_bridge_terminal_publishes` table, but does **not** apply `forge.persistence.migrations.lifecycle_bridge_registry.apply()`. The bridge falls back to legacy ack_callback on every dispatch, which does not publish lifecycle envelopes.
2. **Bridge↔autobuild_runner state-update contract (the surprise).** Even after the missing migration is hot-fixed and a fresh forge-prod boot shows `lifecycle_bridge.attach … observer task scheduled` followed by a successful SSE stream open against the autobuild_runner sidecar, **zero `pipeline.build-started.*` / `stage-complete.*` envelopes** appear on the wire. The autobuild_runner subagent makes hundreds of llama-swap model calls (deepagents tool loop) without producing the `_update_state` transitions the bridge translates to NATS publishes.

**Decision:** Phase 3 close criterion **NOT** advanced. AC-11 of TASK-FORGE-FRR-PEBR-WIREUP **NOT** met (no `pipeline.build-started.FEAT-*` envelope captured on the wire; JetStream `ack_floor` did not advance — stuck at 11). Recommend two follow-up tasks before re-running.

---

## Summary in one paragraph

The PEBR-WIREUP commit (`1b82236`) **does** compose `LifecycleBridgeWireup` into `bind_production_serve`'s middleware chain — that fix landed and the daemon's `forge-serve: dispatch chain composed; _serve_daemon.dispatch_payload rebound to handle_message dispatcher (receipt-only stub no longer reachable)` log line proves it. But the matching SQLite migration was not added to the boot path, so the very first `register_ack_handle` call inside `pipeline_consumer.dispatch` fails with `no such table: lifecycle_bridge_registry` and silently degrades to a legacy ack_callback that doesn't translate SSE → envelope publishes. After hot-fixing the migration (apply against a host-mounted `forge.db`, then restart forge-prod), the bridge wires up cleanly per its own logs but no envelopes flow — the autobuild_runner subagent runs but doesn't appear to drive the `_update_state` transitions the bridge depends on. Two source-level fixes are required before a third rerun.

---

## Per-phase outcomes

| Phase | Gate | Outcome | Evidence |
|---|---|---|---|
| 0.1 | jarvis main on FEAT-JARVIS-INTERNAL-001 close | ✅ | `2864173` reachable from `60cee6b` |
| 0.2 | GB10 reachable | ✅ (host) | `uname -a` returns `promaxgb10-41b1` |
| 0.3 | forge nats-core symlink | ✅ | `.guardkit/worktrees/nats-core → ../../../nats-core` |
| 0.4 | provider keys + NATS auth + supervisor model | ✅ | `JARVIS_SUPERVISOR_MODEL=openai:qwen36-workhorse`, `RICH_NATS_PASSWORD` sourced from `nats-infrastructure/.env` |
| 1.1 | NATS container up | ✅ | `ships-computer-nats` Up 26h healthy |
| 1.2 | 7 streams + 4 KV buckets | ✅ | `verify-nats.sh` 7/7 passed; `nats kv ls` shows agent-status / agent-registry (3 values) / pipeline-state / jarvis-session |
| 1.3 | `pipeline.build-queued.*` bound | ✅ | PIPELINE subjects: `pipeline.>` |
| 2.1 | forge image rebuilt from `1b82236` | ✅ | `forge:latest sha:2705612d4635` (was `e3981c13ff2b` from 06:51) |
| 2.2 | forge serve running | ✅ (with two undocumented requirements) | `forge-prod` Up healthy. **Runbook gaps** — see §Runbook gaps. |
| 2.3 | `/healthz` green + consumer attached | ✅ | `{"status":"healthy"}`; `forge-serve` durable consumer present on PIPELINE |
| 3.1 | architect container up | ✅ | `specialist-agent-architect-agent-1` Up 5h |
| 3.2 | architect ping (optional) | ✅ | rtt 1.3 ms; reply `{"stream":"AGENTS","seq":5}` |
| 4.1 | graphiti container up | ✅ | `graphiti-mcp` Up 24h **healthy** (improvement vs 2026-05-01 baseline) |
| 4.2 | Graphiti HTTP probe | ⚠️ | `localhost:8080` is open-webui (port hijack); `JARVIS_GRAPHITI_ENDPOINT` left unset → DDR-019 trace offload engaged |
| 4.3 | llama-swap embeddings | ✅ | `nomic-embed` returned `data[0].index = 0` |
| 5.1 | jarvis chat boots | ✅ — **major improvement** | None of the documented "expected boot warnings" appeared; `jarvis_startup_complete` with `nats_available=true, capabilities_mode=live`. **TASK-FRR-001 reconciliation has landed.** |
| 5.2 | tool inventory smoke | (skipped — folded into 6.2) | 10 attended tools / 9 ambient tools assembled |
| 6.2 | `queue_build` returns success | ✅ | Two queues issued; both returned `status: queued` with publish target `pipeline.build-queued.FEAT-43DE`. correlation_ids `af772739-...` and `7657ed5a-...` |
| 6.3 | message visible on PIPELINE | ✅ | `last_seq` advanced 19→21 (two new publishes); consumer `ack_pending` rose accordingly |
| 7.1 | between-prompt notifications render full lifecycle sequence | ❌ | No `build-started`/`stage-complete`/terminal lines rendered — REPL exited cleanly after the queue ack but no notifications were drained because none were published |
| 7.2 | wire shows lifecycle sequence on JetStream | ❌ | Wire-tap (`nats sub pipeline.>`) captured **only** the two inbound `pipeline.build-queued.FEAT-43DE` envelopes. Zero outbound. |
| 7.3 | forge container shows autobuild + emit + terminal | ❌ (partial) | Autobuild_runner sidecar dispatched, model calls flowing, but no `emit_*` / `publish_lifecycle_*` log lines from the bridge. After hot-fixing migration: `lifecycle_bridge.attach` + observer scheduled appears but never produces an envelope. |
| 8.1 | chat transcript saved | ✅ | `/tmp/jarvis-runbook-evidence/phase6-chat.log` + `phase6-chat-2.log` |
| 8.2 | Graphiti routing-history dump | (skipped) | Endpoint unreachable, fell to 8.3 |
| 8.3 | offload trace captured | ✅ | `~/.jarvis/traces/af772739-…json` and `~/.jarvis/traces/7657ed5a-…json` (DDR-019 soft-fail path) |
| 8.4 | `command_history.md` entry | (deferred) | This document fulfills the evidence trail; a separate `command_history.md` append is recommended in a follow-up |

---

## The two gaps in detail

### Gap A — `lifecycle_bridge_registry` migration not applied at boot (the AC-11 catch)

**Symptom on the wire:** Every inbound `pipeline.build-queued.*` is dequeued by `forge-serve` but no outbound `pipeline.build-started.*` / `stage-complete.*` / terminal envelope ever appears. JetStream `ack_floor` does not advance.

**Symptom in the forge log (every dispatch):**
```
[WARNING] forge.adapters.nats.pipeline_consumer:
  pipeline_consumer: register_ack_handle raised
  (no such table: lifecycle_bridge_registry)
  for feature_id=FEAT-43DE correlation_id=…;
  continuing with legacy ack_callback fallback
```

**Root cause:** `bind_production_serve` in `forge.cli._serve_production` calls two migration helpers at boot:

- `apply_at_boot(connection)` (`forge.lifecycle.migrations`) — ships the canonical 5 tables (`builds`, `stage_log`, etc.).
- `_bridge_coexistence.apply_migration(connection)` (`forge.lifecycle_bridge.coexistence`) — ships the `lifecycle_bridge_terminal_publishes` table required by `TerminalPublishLedger`.

It does **not** call `forge.persistence.migrations.lifecycle_bridge_registry.apply(connection)`, which is what creates the `lifecycle_bridge_registry` table that `BridgeRegistry` writes through to. Without the table, `register_ack_handle` raises on first use and the consumer falls back to a legacy ack_callback that never publishes lifecycle envelopes.

**Hot-fix performed in this run** (proves the migration is the missing piece):
```bash
docker exec forge-prod python -c "
import sqlite3
from forge.persistence.migrations import lifecycle_bridge_registry
conn = sqlite3.connect('/home/forge/.forge/forge.db', timeout=15)
lifecycle_bridge_registry.apply(conn)
conn.commit()
conn.close()
"
```

After hot-fix:
- The `(no such table: lifecycle_bridge_registry)` warning **disappears** on subsequent dispatches.
- A clean restart of `forge-prod` against a host-mounted, pre-migrated `forge.db` shows the bridge attaching correctly: `lifecycle_bridge.attach feature_id=… correlation_id=…` followed by `wireup.register_ack_handle: attached … observer task scheduled (deadline_at=…)`.

**Suggested source fix** — `forge/src/forge/cli/_serve_production.py` Step 3.5b:

```python
# existing
_bridge_coexistence.apply_migration(connection)

# add
from forge.persistence.migrations import lifecycle_bridge_registry as _bridge_registry_migration
_bridge_registry_migration.apply(connection)
```

The `apply()` call is idempotent (`CREATE TABLE IF NOT EXISTS`) and chain-applies `lifecycle_bridge_published_lifecycles`, mirroring how the existing test fixtures bootstrap the table.

### Gap B — bridge attaches but never emits a `build-started` envelope

**Symptom on the wire:** Same as Gap A — wire-tap captures **zero outbound envelopes** — but the forge log is now clean (no `register_ack_handle` warning) and shows:

```
forge.lifecycle_bridge.bridge: lifecycle_bridge.attach feature_id=FEAT-43DE correlation_id=… thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE
forge.lifecycle_bridge.wireup: wireup.register_ack_handle: attached feature_id=FEAT-43DE correlation_id=…; observer task scheduled (deadline_at=…)
forge.pipeline.dispatchers.autobuild_async: dispatch_autobuild_async: launched task_id=… build_id=… feature_id=FEAT-43DE correlation_id=…
httpx: HTTP Request: GET http://localhost:8124/threads/<task_id>/runs/<run_id>/stream?cancel_on_disconnect=false&stream_mode=values "HTTP/1.1 200 OK"
```

So the bridge:
- Attaches with placeholder `thread_id=pending-FEAT-43DE run_id=pending-FEAT-43DE`
- Registers an observer with a 5-min deadline
- Opens the SSE stream against the langgraph sidecar successfully (HTTP 200)

**But:** the autobuild_runner subagent then runs a deepagents tool loop (~10+ minutes of llama-swap model calls observed in the sidecar log) without the bridge logging any `emit_*` or `publish_lifecycle_*` events, and without any envelope landing on the `pipeline.>` wire-tap.

**Hypotheses (not yet investigated — requires forge-side tracing):**
1. The bridge is initialised with `pending-FEAT-43DE` placeholders and never receives the actual `task_id`/`run_id` from the dispatcher, so it's listening on the wrong SSE stream.
2. The autobuild_runner subagent runs but never calls `_update_state` with `stage_log` updates the bridge translator looks for (the bridge needs structured stage transitions, not free-form deepagents tool messages).
3. The autobuild_runner DDR-006/007 contract (`_update_state` shape) doesn't match what the bridge translator expects — possible drift between the FRR-PEB feature spec and what the runner actually emits.
4. The dispatch path's `run_id` thread doesn't reach the bridge's observer; the SSE GET is for the **dispatcher's** httpx client cache (the run launch round-trip), not the bridge's observer task.

**Suggested next steps:**
- Add structured logging to `forge.lifecycle_bridge.bridge` and `forge.lifecycle_bridge.translator` covering: SSE event received, candidate state diff, envelope emit decision (with `because: …` reason).
- Run the existing `tests/integration/test_lifecycle_bridge_sidecar_e2e.py` against the same image and check whether it actually exercises the autobuild_runner's update-state contract end-to-end (it spins up the sidecar, but if the test stubs the runner's state transitions it would mask this gap).
- Consider whether the bridge needs to be re-registered with the *real* `task_id`/`run_id` after dispatch (rather than starting with placeholders).

### Migration drift signature in the consumer info JSON

Pre-publish (10:43): `last_seq=19, ack_floor=11, ack_pending=2, redelivered=2`
Post-publish 1 (10:45 — first jarvis queue, gap A active): `last_seq=20, ack_floor=11, ack_pending=3, redelivered=2`
Post-publish 2 (10:50 — second jarvis queue, hot-fix in flight): `last_seq=21, ack_floor=11, ack_pending=4, redelivered=4`
Final (10:55 — bridge attached cleanly post-restart, gap B active): `last_seq=21, ack_floor=11, ack_pending=4, redelivered=4, delivered=7380`

**`ack_floor` never advanced.** That alone is the AC-11 fail signature.

---

## Runbook gaps discovered (gap-fold candidates)

| What needed manual adjustment | Suggested runbook fix |
|---|---|
| `forge serve` now requires `--config <path>` between the `forge` parent group and the `serve` subcommand. The container ships without a default `forge.yaml`, so the runbook's `forge:latest serve` invocation crashes with `Error: forge serve requires a forge.yaml — pass --config <path>...`. | §2.2 should mount `~/forge-state/forge.yaml` (or equivalent) and invoke `forge:latest --config /var/forge/forge.yaml serve`. The runbook should also document the minimal `forge.yaml` schema (one required block: `permissions.filesystem.allowlist` with absolute paths). |
| `forge serve` now requires `FORGE_AUTOBUILD_RUNNER_URL` pointing at a langgraph-runner sidecar (TASK-FORGE-FRR-F010I/J). With it unset, `bind_production_serve` raises `ValueError: bind_production_serve: 'autobuild_runner_url' is required but missing/empty`. The deployment topology is now: forge-serve container + langgraph-runner sidecar (typically `langgraph dev` against the forge repo). | Add a new §2.0 "Start the langgraph-runner sidecar" with a `langgraph dev --host 127.0.0.1 --port 8124 --no-browser` invocation from the forge repo root, and update §2.2 to set `FORGE_AUTOBUILD_RUNNER_URL=http://localhost:8124`. **Note:** the canonical `forge/langgraph.json` declares an `orchestrator` graph that fails to import (`No module named 'agents'`), so the sidecar must be started with a stripped config containing only `autobuild_runner` — file it as a forge follow-up. |
| The forge daemon now persists its DB at `/home/forge/.forge/forge.db` inside the container's writable layer, **not** in the existing `~/forge-state` volume mounted at `/var/forge`. Without an additional `-v ~/forge-prod-state/.forge:/home/forge/.forge` mount, every container restart is a fresh DB and any operator-applied migrations are lost. | §2.2 docker run command should add `-v ~/forge-prod-state/.forge:/home/forge/.forge` (with host directory pre-created and chowned to uid 1000). |
| Runbook §6.2 expects `queue_build` to return a JSON payload starting with `status: queued / feature_id: ... / correlation_id: ...`. The supervisor's actual rendered output is a markdown bullet list (`- **Correlation ID:** ...`). | Loosen §6.2 to accept either shape, or update the prompt template so the supervisor returns the raw tool result. |
| Runbook §5.1's documented "expected boot warnings until TASK-FRR-001 lands" no longer reproduce — the JARVIS stream / agent-registry / forge_subscriber subscriptions now bind cleanly. The forward-reference to TASK-FRR-001 should be retired. | Move TASK-FRR-001 from the §"Known issues" table to a "✅ resolved 2026-05-08" footnote and remove the boot-warning expectation from §5.1. |
| Phase 4 says "Probe the actual Graphiti HTTP endpoint" with `curl http://localhost:8080/healthz`. On GB10, port 8080 is held by `open-webui` (host-network). The probe returns open-webui's HTML splash, which **looks like** a 200 reply but is not Graphiti. | §4.2 should detect the response body's Content-Type / first line and reject HTML responses, or update the runbook to use the actual `graphiti-mcp` exposed port (which on this box is **not** mapped to host — graphiti-mcp is on the docker-internal network only). |

---

## Decision

- [ ] Phase 3 closed canonical
- [ ] Phase 3 closed with gap-folds
- [x] **Partial — Phase 7 failed** at the wire-level envelope gate (Gap A migration drift, Gap B bridge↔runner contract). AC-11 of TASK-FORGE-FRR-PEBR-WIREUP **NOT met**.

**Recommended follow-up tasks (forge side):**

1. **TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-A: Wire `lifecycle_bridge_registry` migration into `bind_production_serve`.** ~5-line patch in `forge/src/forge/cli/_serve_production.py` Step 3.5b. **This is the AC-11 catch.**
2. **TASK-FORGE-FRR-PEBR-WIREUP-FOLLOWUP-B: Investigate why the bridge attaches but never publishes `build-started`.** Hypotheses listed above; recommend starting with structured logging in `bridge.translator` and a re-run of `tests/integration/test_lifecycle_bridge_sidecar_e2e.py`.

**Recommended follow-up task (jarvis side):**

3. **TASK-FRR-RUNBOOK-002: Gap-fold the runbook for the post-PEBR-WIREUP deployment topology.** All six runbook gaps in the table above. Prerequisite for any future operator using this runbook to onboard.

---

## Evidence index

All evidence files preserved at `/tmp/jarvis-runbook-evidence/`:

| File | Phase | Description |
|---|---|---|
| `phase5-boot.log` | 5 | Clean jarvis chat boot — no expected warnings (TASK-FRR-001 resolved) |
| `phase6-chat.log` | 6.2 | First queue REPL transcript (correlation `af772739-...`) |
| `phase6-chat-2.log` | 6.2 | Second queue REPL transcript (correlation `7657ed5a-...`) |
| `phase6-pre-stream-info.json` | 6.3 | PIPELINE state pre-publish (last_seq=19) |
| `phase6-pre-consumer-info.json` | 6.3 | forge-serve consumer state pre-publish (ack_floor=11) |
| `phase6-post-stream-info.json` | 6.3 | PIPELINE state post-publish 1 (last_seq=20) |
| `phase6-post-consumer-info.json` | 6.3 | forge-serve consumer state post-publish 1 (still ack_floor=11) |
| `phase6-pipeline-tap.log` | 6.3/7.2 | Wire-tap output — captures only the two inbound `pipeline.build-queued.FEAT-43DE`; **no outbound lifecycle envelopes** |
| `phase7-final-stream-info.json` | 7 | PIPELINE state at end (last_seq=21) |
| `phase7-final-consumer-info.json` | 7 | forge-serve consumer state at end (delivered=7380, ack_floor=11, ack_pending=4) — proves AC-11 not met |
| `phase7-forge-prod-logs.log` | 7.3 | Full forge-prod docker logs from clean boot through 13+ minutes runtime |
| `phase7-langgraph-sidecar.log` | 7.3 | autobuild_runner sidecar logs — long-running deepagents tool loop, ~250 KB |
| `phase8-trace-af772739.json` | 8.3 | DDR-019 offload trace for first queue |
| `phase8-trace-7657ed5a.json` | 8.3 | DDR-019 offload trace for second queue |
| `forge-runner-only-langgraph.json` | 2.0 (new) | The stripped `langgraph.json` used to boot the sidecar (orchestrator graph excluded due to import failure) |

---

## See also

- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-08.md) — pre-PEBR-WIREUP rerun (forge HEAD `e50241e`); PEBR bridge merged code-only, composer not wired.
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run-2026-05-04.md) — five-addendum F010.A-G journey.
- [`RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — 2026-05-01 baseline.
- [`RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md`](./RUNBOOK-FEAT-JARVIS-INTERNAL-001-first-real-run.md) — the runbook itself.
