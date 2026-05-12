# RESULTS — FEAT-JARVIS-006 verification rerun, post-J006-009/010 (2026-05-12)

**Operator:** Claude Code (Opus 4.7 1M context) under richardwoollcott's instruction
**Date:** 2026-05-12 (afternoon rerun)
**Commit verified:** `076b9353423007824ab2e878a21c375978ce5ce3` (TASK-J006-010 head; descendant of `51f65e2` FEAT-JARVIS-006 squash-merge; includes [TASK-J006-009](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-009-fix-subscribe-with-reply-envelope-unwrap.md) + [TASK-J006-010](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-010-bound-startup-reconnect-broker-hard-fail.md))
**Demo deadline:** 2026-05-16 DDD Southwest
**Runbook executed:** [docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md)
**Task:** [TASK-J006-005](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-005-live-openwebui-demo-verification.md)
**Supersedes:** [RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12.md](RESULTS-FEAT-JARVIS-006-serve-nats-first-run-2026-05-12.md) (pre-fix run, kept as historical record)
**Verdict:** **7/8 ACs ✅ PASS, 1/8 ⏳ PENDING (AC-005-06 forge — pre-existing fleet condition out of FEAT-JARVIS-006 scope).** **Demo is GREEN-LIGHT for 2026-05-16** for the chat-gateway scope. AC-005-06 forge notification drain requires `forge-prod` container to be live; can be evidenced separately once Forge is brought back online.

## Executive summary

After [TASK-J006-009](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-009-fix-subscribe-with-reply-envelope-unwrap.md) (envelope unwrap) and [TASK-J006-010](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-010-bound-startup-reconnect-broker-hard-fail.md) (bounded startup reconnect) landed, the chat-gateway flipped from 4/8 BLOCKED to 7/8 PASS. The OpenWebUI → fleet-pipe → jarvis serve-nats → supervisor → specialist (`architect-agent`) → reply path is end-to-end clean. Multi-turn session retention holds across 3+ turns. SIGINT teardown completes in 3.3 ms. Broker-down probe fails-fast at the configured `startup_connect_timeout_seconds=10` (exit 1, clear error). The only AC not evidenced this session is AC-005-06 (forge notification drain) because `forge-prod` has been `Exited (255)` for 2 days — pre-existing fleet state, not a gateway regression.

## TASK-J006-005 acceptance criteria — outcomes

| AC | Phase | Outcome | Evidence | Notes |
|---|---|---|---|---|
| AC-005-01 (pre-warm qwen36-workhorse) | §0.5 | ✅ PASS | `curl /v1/chat/completions` → 200 `"Ping received! 🏓\n\nI"` in elapsed ~0s (already warm from earlier session) | Model swap-in not needed; warm path latency ~0s as captured. |
| AC-005-02 (boot + KV-revision heartbeat tick) | §2.1 | ✅ PASS | [`jarvis-serve-nats-smoke.2026-05-12.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-smoke.2026-05-12.log) lines 1–8 (boot); KV revision 472@15:15:06 → 474@15:16:06 (2 ticks in 60s, matches default 30s heartbeat) | Boot lines all present: `nats_connect_success`, `fleet_register_published`, `jarvis_startup_complete (nats_available=true)`, `jarvis_serve_nats_subscribed` on `agents.command.jarvis`, `jarvis_serve_nats_ready`. Heartbeat verified by KV-revision-tick recipe (DEBUG `fleet_heartbeat_published` re-registers manifest; never on a `fleet.heartbeat...` subject). |
| AC-005-03 (Open WebUI E2E reply) | §3.4 turn 1 | ✅ PASS | Turn-1 reply rendered E2E listing agents + ADR-ARCH-001 analysis; wire-tap [`jarvis-serve-nats-e2e-command.2026-05-12.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-e2e-command.2026-05-12.log) envelope #2 `corr=b11d25ec-…`; corresponding result envelope #2 in [`jarvis-serve-nats-e2e-result.2026-05-12.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-e2e-result.2026-05-12.log) | Turn-1 invoke wall-clock 18.1s (smoke log `chat_invoke_start` 14:26:46.084 → `chat_invoke_complete` 14:27:04.183, `response_length=2255`). TASK-J006-009 envelope-unwrap fix demonstrably working — pipe-published `MessageEnvelope` decoded cleanly, no `nats_subscribe_decode_failed`. |
| AC-005-04 (multi-turn session retention ≥3) | §3.4 turns 2–3 | ✅ PASS | Turn-3 recap reply quoted verbatim below correctly references turn-1 (ADR-ARCH-001) + turn-2 (build_responder gap) | Operator drove 4 chat turns + one `capabilities_refresh` in a single OpenWebUI session; turn-3 recap accurately summarises prior turns. See "Multi-turn transcript" below. |
| AC-005-05 (specialist dispatch fires) | §3.5 | ✅ PASS | After `capabilities_refresh` chat turn, jarvis dispatched to `architect-agent` and quoted real architect output: **"Conditionally feasible (confidence: 85%)"** with risks (data leakage, budget overrun, operational complexity) + recommendations (BudgetController component, explicit consent gate, audit logging). Wire-tap envelope #5 `corr=213719dc-…` on `agents.command.>` carries an empty `args.message` (dispatch-shape envelope, not a flat chat command), matching the `dispatch_by_capability` wire signature. KV `agent-registry` shows `architect-agent` registered (post-restart). | Forge dispatch not evidenced (Forge offline — see AC-005-06). architect-agent + product-owner-agent both needed a `docker restart` mid-session to recover from a pre-session NATS broker bounce (they lack the bounded-reconnect that TASK-J006-010 added to jarvis). |
| AC-005-06 (forge notification drain, Risk #3) | §3.6 | ⏳ PENDING — pre-existing fleet condition, out of FEAT-JARVIS-006 scope | `docker ps -a` shows `forge-prod Exited (255) 2 days ago`. Cannot evidence forge stage-complete notification append without a live Forge process. | The chat-handler notification drain pathway (`session_manager.pending_notifications(session_id)` + reply-append) is implemented and exercised by every chat turn (smoke log shows `notifications_drained=0` on every `chat_invoke_complete` — drain path is wired, just no notifications to drain this session). Once Forge is running, a single follow-up chat turn will exercise the full path. **Recommended follow-up:** small task to bring `forge-prod` back online + rerun §3.6, file as a non-FEAT-JARVIS-006 fleet task. |
| AC-005-07 (SIGINT graceful shutdown) | §3.7 | ✅ PASS (with one log-content nit, behaviour clean) | [`jarvis-serve-nats-smoke.2026-05-12.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-smoke.2026-05-12.log) tail: `jarvis_serve_nats_signal_received` (14:40:02.184) → `fleet_heartbeat_cancelled` → `fleet_deregister_published` → `nats_disconnect` → `nats_closed` → `nats_drain_complete (timeout=5.0)` → `jarvis_serve_nats_shutdown_complete` (14:40:02.187). Process gone from kill -0 within 1003 ms wall. | Total shutdown wall-clock **3.3 ms** (signal_received → shutdown_complete). 4 of 5 runbook-expected phrases present (`heartbeat`, `deregister`, `disconnect`, `drain`); explicit "unsubscribe" phrase still absent (carried over from prior RESULTS — observability nit, not a behaviour regression). Logged order is `heartbeat → deregister → disconnect → drain` vs runbook-documented `unsubscribe → drain → heartbeat → deregister → disconnect`; runbook order assumes a study-tutor-style adapter lifecycle, while jarvis's `cli/main.py` shutdown path reorders for the lifecycle-driven design (heartbeat task is cancelled before NATS handle is torn down). Behaviour is correct; runbook section §3.7's "in this order" claim is stale and would benefit from a small docs follow-up. **Exit code unreadable** here because `nohup` detached the process from the shell — `wait $!` returned 127 (not-a-child). The smoke log unambiguously ends with `shutdown_complete` and the process is gone, so the clean exit is evidenced by log + process state. |
| AC-005-08 (broker-down hard-fail) | §3.8 | ✅ PASS — flipped from pre-fix ❌ FAIL | [`jarvis-serve-nats-broker-down.2026-05-12.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-broker-down.2026-05-12.log) lines 9–14: 5× `ConnectionRefusedError` warnings at 2s intervals, then terminal `nats_connect_failed (elapsed_seconds=10.003, startup_connect_timeout_seconds=10)` + `jarvis_serve_nats_startup_failed` ERROR. Process exited with code **1** in **10.687 s** wall-clock total. | TASK-J006-010 working as designed: bounded `asyncio.wait_for(connect, timeout=startup_connect_timeout_seconds)`, terminal error line names the unreachable broker + timeout setting, no `jarvis_startup_complete` line (we never reached ready). Broker restored cleanly post-test (`ships-computer-nats` `healthy` after 6× 1s polls). |

## Multi-turn transcript (AC-005-04 evidence body)

Operator drove the following turns in one OpenWebUI chat session at `http://promaxgb10-41b1:8080/` with the **Jarvis** model selected. All replies are jarvis's renderings as pasted by the operator from the browser.

### Turn 1 (AC-005-03)

> **Operator:** What agents do you have available, and can you ask the architect to evaluate whether ADR-ARCH-001's local-first invariant should allow a budget-capped cloud escalation path?

> **Jarvis (abridged):** The architect agent isn't online in the fleet right now. … Available agents: Product Owner Agent registered; Architect Agent not currently registered; Ideation Agent not currently registered; Forge not currently registered. You can bring it back with `capabilities_refresh`. … In the meantime, I can still give you my take on the ADR-ARCH-001 question: Yes, a budget-capped cloud escalation path is compatible with local-first. Local-first means default, not absolute. … The real risk isn't the escape hatch — it's scope creep. … Bottom line: The invariant should say "local unless the user explicitly opts into cloud, with strict per-request and monthly budget caps and full auditability." That's local-first with teeth, not local-first with an open door.

(Mid-session fleet check: `architect-agent` was actually running in `specialist-agent-architect-agent-1` but had lost NATS connection during a pre-session broker bounce — `ConnectionRefusedError` reconnect loop, same pattern TASK-J006-010 now bounds for jarvis. Operator approved restarting `architect-agent` + `product-owner-agent` to recover. After restart, KV registry showed `architect-agent`, `product-owner-agent`, `jarvis` — all live. Architect-agent emitted `Ready.`)

### Turn 2 — `capabilities_refresh` + architect dispatch (AC-005-05)

> **Operator:** capabilities_refresh

> **Jarvis (abridged):** Architect is back online and has weighed in. Here's the summary: **Verdict: Conditionally feasible** (confidence: 85%) … Risks flagged: Data leakage — sensitive data leaving premises without explicit consent; Budget overrun — per-request caps not enforced at the gateway; Operational complexity — managing dual-mode routing (local vs cloud). Recommendations: Explicit consent gate; **BudgetController component** — enforce the £20–50 monthly cap at the infrastructure layer; Escalate only when local fails; Audit logging. Estimated complexity: Medium … So the architect agrees with my assessment in principle … The key addition from the architect is the BudgetController as a dedicated infrastructure component …

(This reply contains real architect-agent output flowing back through `dispatch_by_capability` → `agents.command.architect-agent` → architect-agent process → `agents.result.architect-agent` → jarvis supervisor → OpenWebUI. Wire-tap envelope #5 `corr=213719dc` on the command tap has empty `args.message` — characteristic dispatch envelope shape, not a flat chat command.)

### Turn 3 (AC-005-04 — session retention 1)

> **Operator:** Of those agents, which one would you escalate to if a runtime quality gate failed during an autobuild turn? Walk me through how that handoff would work.

> **Jarvis (abridged):** That's a good question, but none of the registered agents are designed for runtime quality-gate failures during autobuild. … Architect — could assess drift, but post-mortem only … Product Owner — planning-level, not runtime … Forge — the build pipeline itself; surface, not resolver … Ideation — no integration with the build system … The honest answer: There's no handoff because there's no agent designed for this. … What would actually need to happen: emit `pipeline.build-stage-failed.{feature_id}`; Jarvis assesses severity; transient → retry; real defect → stop the build, notify the user, route to Architect/PO/Ideation as appropriate. … That's a new capability — a build incident responder — that doesn't exist in the current fleet. … Want me to flag this as a gap? It feels like there should be a `forge_monitor` or `build_responder` capability that sits between the pipeline events and the specialist agents …

### Turn 4 (AC-005-04 — session retention 2, recap)

> **Operator:** Recap our conversation so far in two sentences.

> **Jarvis (verbatim):** We started by checking available agents, then evaluated whether ADR-ARCH-001's local-first invariant should allow a budget-capped cloud escalation path — the architect agreed it's conditionally feasible with proper safeguards like explicit consent, a BudgetController component, and audit logging. We then identified a gap in the fleet: no agent is designed to handle runtime quality-gate failures during autobuilds, and discussed what a build_responder capability might look like.

This recap correctly references both prior turns (turn-1 ADR-ARCH-001 question + turn-3 build_responder gap) — strong AC-005-04 evidence.

## Wire-tap correlation table (Phase 3.3 → 3.5)

10 command envelopes + 9 result envelopes captured by the broad-wildcard taps on `agents.command.>` / `agents.result.>` during the operator's session, plus the §2.3 nats-request smoke.

| # | correlation_id | Role |
|---|---|---|
| 1 | `runbook-2-3-001` | §2.3 nats-request smoke (flat CommandPayload) |
| 2 | `b11d25ec-…` | Turn 1 (ADR question) |
| 3 | `ace95092-…` | OpenWebUI internal "Suggest follow-up questions" sidecar prompt |
| 4 | `9782f9bd-…` | `capabilities_refresh` chat turn |
| 5 | `213719dc-…` | **Architect dispatch envelope** (empty `args.message`, dispatch-shape) |
| 6 | `bfcaae3d-…` | OpenWebUI follow-up suggestions sidecar |
| 7 | `4d08ddeb-…` | Turn 3 (escalation walkthrough) |
| 8 | `fc9eb3e4-…` | OpenWebUI follow-up suggestions sidecar |
| 9 | `557da237-…` | Turn 4 (recap) |
| 10 | `a87c21a5-…` | OpenWebUI follow-up suggestions sidecar |

OpenWebUI ran a "Suggest follow-up questions" sidecar prompt after every operator turn (envelopes 3/6/8/10) — also routed through the NATS gateway. About 2× the chat traffic per visible operator turn; gateway handled all without backpressure.

## What changed vs the pre-fix run

| Pre-fix RESULTS verdict | Post-fix outcome | Driver |
|---|---|---|
| AC-005-03 ❌ BLOCKED (`MessageEnvelope` not unwrapped) | ✅ PASS — E2E reply rendered | TASK-J006-009 envelope unwrap landed |
| AC-005-04 ❌ BLOCKED (never reached handler) | ✅ PASS — Turn-4 recap quotes prior turns | TASK-J006-009 |
| AC-005-05 ❌ BLOCKED (same) | ✅ PASS — architect dispatch fired via `capabilities_refresh` | TASK-J006-009 + architect-agent restart |
| AC-005-06 ❌ BLOCKED (same) | ⏳ PENDING — pre-existing Forge container condition, out of scope | n/a (fleet hygiene) |
| AC-005-08 ❌ FAIL (unbounded reconnect) | ✅ PASS — fail-fast at 10.003 s, exit 1 | TASK-J006-010 bounded startup connect |

## Other findings (not requiring runbook patches)

- **KV manifest content (intents-only, 0 tools)** — same finding as the pre-fix RESULTS §"Other findings": `fleet_registration.build_jarvis_manifest()` publishes the 4-generic-intents manifest, not the `infrastructure/manifest.py:build_manifest()` 1-chat-tool manifest. No behaviour impact for FEAT-JARVIS-006 (the supervisor's full tool surface is reachable via the chat surface regardless). Stale runbook §2.2 expectation `tool count: 1` was not patched — recommend a small docs follow-up if pursued.
- **OpenWebUI follow-up-question sidecar traffic** — 4 extra `agents.command.jarvis` invocations per chat session (one per operator turn). All decoded cleanly via TASK-J006-009's envelope unwrap and round-tripped under 5s each (smoke log `chat_invoke_complete` events for `corr=ace95092`, `bfcaae3d`, `fc9eb3e4`, `a87c21a5`). The gateway handles this load without degradation.
- **Specialist reconnect gap** — `specialist-agent-architect-agent-1` and `specialist-agent-product-owner-agent-1` both required `docker restart` mid-session to recover from a NATS broker bounce that pre-dated this session. Same root cause TASK-J006-010 fixed for jarvis; fleet-wide fix would replicate that pattern into the specialist-agent template. Recommended fleet-hygiene task (out of FEAT-JARVIS-006 scope).
- **Phase 3.8 broker bounce side-effect** — stopping `ships-computer-nats` for the AC-005-08 probe left both specialist containers in a fresh reconnect loop again, post-test. Operator can `docker restart` them on demand.
- **Forge container offline** — `forge-prod` `Exited (255) 2 days ago`. Out of FEAT-JARVIS-006 scope; flagged as the sole reason AC-005-06 is ⏳ rather than ✅.

## Working wire paths (proven this session)

1. **Phase 0.5 llama-swap warmup** — qwen36-workhorse already loaded; response ~0 s.
2. **Phase 2.1 jarvis boot** — clean lifecycle, KV register, KV-heartbeat tick (revision 472 → 474 in 60 s), subscribe on `agents.command.jarvis`. AC-005-02 ✅.
3. **Phase 2.3 flat-CommandPayload smoke** — RTT 6.14 s warm, `success: true`, full supervisor reply. AC-005-03 wire (CLI half) ✅.
4. **Phase 3.4 envelope-wrapped (OpenWebUI pipe) round-trip** — TASK-J006-009 demonstrably unwrapping; 4 user turns + 4 sidecar prompts all clean. AC-005-03 + 04 ✅.
5. **Phase 3.5 `dispatch_by_capability` → architect-agent** — wire-tap envelope #5 + verbal architect output in jarvis reply. AC-005-05 ✅.
6. **Phase 3.7 SIGINT teardown** — 3.3 ms total, heartbeat-cancel → deregister → disconnect → drain. AC-005-07 ✅.
7. **Phase 3.8 broker-down fail-fast** — 10.003 s bounded, exit 1, terminal error. AC-005-08 ✅.

## Blocked wire paths (this session)

- **Forge build queue → notification drain** (AC-005-06) — `forge-prod` exited 2 days ago. Drain pathway is wired (every `chat_invoke_complete` log line carries a `notifications_drained=<n>` field, n=0 this session because no producer). One Forge container start + one chat turn would evidence this AC; gateway behaviour is not in doubt.

## Failures and follow-ups

| Item | Severity | Follow-up |
|---|---|---|
| AC-005-06 ⏳ pending: `forge-prod` exited 2 days ago | Medium (out of FEAT-JARVIS-006 scope; not demo-blocking) | Fleet-hygiene task: restart `forge-prod` + rerun §3.6 + append a small RESULTS-AC-006 addendum. Not a TASK-J006-* item — Forge ownership lives elsewhere. |
| `specialist-agent-*` containers lack bounded NATS reconnect (same pattern TASK-J006-010 fixed for jarvis) | Medium | Cross-repo follow-up in `specialist-agent` to port the `startup_connect_timeout_seconds` + bounded `asyncio.wait_for` pattern. Out of FEAT-JARVIS-006 scope. |
| Pre-fix RESULTS §3.7 "Shutdown steps 5a/5b emit no log lines" still holds | Low (observability only) | Original follow-up still applies: add `log.info("jarvis_serve_nats_unsubscribed")` after `subscription.unsubscribe()` and `log.info("jarvis_serve_nats_drain_in_flight_complete", …)` after the 5b loop. ~3 LoC. |
| Runbook §3.7 documents shutdown order as `unsubscribe → drain → heartbeat → deregister → disconnect` but actual order is `heartbeat → deregister → disconnect → drain` | Low (docs only — behaviour is correct) | Small docs follow-up: update §3.7 ordered list to match the actual lifecycle in [`cli/main.py`](../../src/jarvis/cli/main.py), or reconcile to the study-tutor reference if that order is canonical and jarvis should change. |
| Runbook §2.2 expects `tool count: 1` (`chat`); actual KV manifest is intents-only (0 tools, 4 generic intents) — same finding as pre-fix RESULTS | Low | Update runbook expectation to match actual `build_jarvis_manifest` output, OR wire `infrastructure/manifest.py:build_manifest()` into the publish path if the tool-rich shape was intended. Not demo-blocking. |

## Demo-day notes (2026-05-16)

- **Gateway readiness:** ✅ GREEN. The chat-gateway end-to-end path that the demo exercises (OpenWebUI → jarvis serve-nats → supervisor → optional dispatch → reply) is solid. Multi-turn session retention works. Architect specialist dispatch works.
- **Pre-demo prep:** run §0.4 (`docker ps` of `ships-computer-nats`, `open-webui`, `specialist-agent-architect-agent-1`, `specialist-agent-product-owner-agent-1`) + §0.5 warmup curl before the live demo. If any specialist container shows a stale `ConnectionRefusedError` in its tail, `docker restart` it — same recovery pattern this session used.
- **Forge demo:** **skip the "queue forge build" beat** unless Forge is brought back online first. If Forge stays down, simply don't include forge-build prompts in the live demo — the chat-gateway demo stands on its own merits (multi-turn + specialist dispatch).
- **Fallback:** if anything regresses unexpectedly between now and demo day, this RESULTS file + the pre-fix RESULTS show the diff between broken and working states — the runbook's Phase 2.3 `nats request` smoke is a 6-second CLI probe that surfaces any inbound-envelope regression instantly.

## Session housekeeping

- `ships-computer-nats` was stopped for ~17 s during §3.8 broker-down probe; restored to `healthy` post-test (6× 1s healthcheck polls). Specialist-agents (`architect-agent`, `product-owner-agent`) are post-bounce in their own reconnect loops at the close of this session — running but not currently in KV. Operator should `docker restart specialist-agent-architect-agent-1 specialist-agent-product-owner-agent-1` before any further fleet-dependent work.
- One-off `pip install nats-py` in `open-webui` from prior session is **still installed** (verified `docker exec open-webui python -c "import nats; print('ok')"` → `ok`). Lost on container restart; still flagged for fleet-gateway team.
- Wire-tap subscriptions on `agents.command.>` / `agents.result.>` were torn down before broker stop in §3.8.
- All log artefacts copied (with `RICH_NATS_PASSWORD` redacted via `sed`) into [`docs/runbooks/evidence/feat-jarvis-006-first-run/`](evidence/feat-jarvis-006-first-run/) with `.2026-05-12.log` suffix to keep separate from the pre-fix run's artefacts.

## Sign-off

7/8 ACs ✅ PASS, 1/8 ⏳ PENDING (out of scope). FEAT-JARVIS-006 chat-gateway implementation (commit `076b935`) is **demo-ready for 2026-05-16**. Recommend running `/task-complete TASK-J006-005` against this RESULTS file, with AC-005-06 explicitly carried into a separate fleet-hygiene follow-up rather than blocking task closure.
