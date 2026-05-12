# RESULTS — FEAT-JARVIS-006 first-run verification (2026-05-12)

**Operator:** Claude Code (Opus 4.7 1M context) under richardwoollcott's instruction
**Date:** 2026-05-12
**Commit verified:** `c7b0fefc68403dd3532299cb15f3303d7cf6f470` (descendant of `51f65e2` FEAT-JARVIS-006 squash-merge)
**Demo deadline:** 2026-05-16 DDD Southwest
**Runbook executed:** [docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md](RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md)
**Task:** [TASK-J006-005](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-005-live-openwebui-demo-verification.md) (Live Open WebUI ↔ jarvis serve-nats multi-turn demo verification)
**Verdict:** **PARTIAL — 3/8 ACs PASS, 1/8 PASS-with-caveat, 4/8 FAIL/BLOCKED.** Two P0 demo-blockers filed (TASK-J006-009, TASK-J006-010). Runbook patched with five GB10-specific divergences. Demo on 2026-05-16 is **at risk** unless TASK-J006-009 lands.

## Executive summary

The chat-gateway boots cleanly, registers, heartbeats, and answers a hand-crafted flat-`CommandPayload` request end-to-end via the supervisor — that wire path works. **The production wire path (OpenWebUI → fleet-gateway pipe → jarvis) is broken** by a decode-strictness regression in `nats_client.subscribe_with_reply`: jarvis decodes raw bytes as flat `CommandPayload`, the pipe publishes wrapped `MessageEnvelope`. The study-tutor template (cited by the runbook as authoritative) uses the envelope-unwrap-then-validate pattern; jarvis diverges. Fix is ~10 LoC (see TASK-J006-009).

Separately, **AC-005-08 (broker-as-hard-dependency) fails**: serve-nats retries `ConnectionRefusedError` indefinitely on boot rather than exiting non-zero. Fix scope: bound the startup connect in `nats_client.py` with `asyncio.wait_for` + a terminal `nats_connect_failed` log line (see TASK-J006-010).

## TASK-J006-005 acceptance criteria — outcomes

| AC | Phase | Outcome | Evidence | Notes |
|---|---|---|---|---|
| AC-005-01 (pre-warm qwen36-workhorse) | §0.5 | ✅ PASS | [`jarvis-warmup-response.json`](evidence/feat-jarvis-006-first-run/jarvis-warmup-response.json) | Warmup wall-clock: 0.4s (model already loaded from prior fleet activity). Reply: `"Ping received! 🏓\n\nHow"` (truncated at max_tokens=8). |
| AC-005-02 (boot + heartbeat) | §2.1 | ✅ PASS (heartbeat via KV-revision tick, **runbook divergence patched**) | [`jarvis-serve-nats-smoke.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-smoke.log) lines 1-21 | Boot at 13:08:11 UTC; `nats_connect_success`, `fleet_register_published`, `jarvis_startup_complete (nats_available=true)`, `jarvis_serve_nats_subscribed (agents.command.jarvis)`, `jarvis_serve_nats_ready` — all present. Heartbeat verified by KV revision tick 407→408 over 30s. The runbook's expected `fleet.heartbeat.jarvis` subject does **not** exist; jarvis re-publishes the manifest to `agent-registry` KV (DEBUG `fleet_heartbeat_published`). Runbook updated with KV-revision verification recipe. |
| AC-005-03 (Open WebUI E2E reply) | §3.4 turn 1 | ❌ **BLOCKED** | [`jarvis-serve-nats-smoke.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-smoke.log) lines 25-29 (`nats_subscribe_decode_failed`); [`jarvis-serve-nats-e2e-command.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-e2e-command.log) line 2 (envelope-wrapped command on bus) | Real wire path is broken: pipe publishes `MessageEnvelope{payload: CommandPayload}`, jarvis subscriber decodes raw bytes as flat `CommandPayload`, `pydantic.ValidationError: command — Field required`. Five attempts over ~5min, identical failure mode. See [TASK-J006-009](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-009-fix-subscribe-with-reply-envelope-unwrap.md) for the ~10-LoC fix in `src/jarvis/infrastructure/nats_client.py:266-280`. |
| AC-005-04 (multi-turn session retention ≥3) | §3.4 turns 2-3 | ❌ **BLOCKED** | Same as AC-005-03 — never reached the chat handler | Cannot exercise session retention until TASK-J006-009 lands. |
| AC-005-05 (specialist dispatch) | §3.5 | ❌ **BLOCKED** | Same as AC-005-03 — wire never reached supervisor for OpenWebUI traffic. **Note:** specialist dispatch IS proven to work via the §2.3 nats-cli smoke (flat `CommandPayload`): supervisor listed `dispatch_by_capability` + `Architect/Ideation/Product Owner` specialists in its reply text. The dispatch *capability* is wired; only the inbound envelope path blocks evidencing it via OpenWebUI. | See [`jarvis-serve-nats-request-001.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-request-001.log) for the §2.3 evidence of supervisor + specialist surface. |
| AC-005-06 (forge notification drain, Risk #3) | §3.6 | ❌ **BLOCKED** | Same as AC-005-03 | Cannot exercise notification drain until TASK-J006-009 lands. |
| AC-005-07 (SIGINT graceful shutdown) | §3.7 | ⚠️ **PASS-with-caveat** (behaviour ✅, observability gap ⚠) | [`jarvis-serve-nats-smoke.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-smoke.log) lines 40-46 (teardown sequence); KV `nats: key not found` confirms deregister | SIGINT received at 13:42:39.289Z; full shutdown at 13:42:39.292Z (3ms total). Process exit detected at 13:42:45 (6s wall-clock end-to-end including os reap). Behaviour: 5a unsubscribe → 5b drain → 5c heartbeat cancel → 5d deregister → 5e nats drain/disconnect — verified by reading [`src/jarvis/cli/main.py:498-565`](../../src/jarvis/cli/main.py#L498-L565). **Observability gap:** steps 5a (unsubscribe) and 5b (drain in-flight when empty) emit no log line; the runbook's expected `unsubscribe` grep token is missing. KV deregister behaviour verified (`agent-registry/jarvis` returns `key not found` post-SIGINT). Minor follow-up: add explicit log lines for 5a/5b (~3 LoC). |
| AC-005-08 (broker-down hard-fail) | §3.8 | ❌ **FAIL** | [`jarvis-serve-nats-broker-down.log`](evidence/feat-jarvis-006-first-run/jarvis-serve-nats-broker-down.log) (15 retries over 28s, killed by external `timeout`) | Process retries `ConnectionRefusedError [Errno 111]` to `127.0.0.1:4222` every 2s indefinitely, never exits. Killed externally by `timeout 30 jarvis serve-nats ...` (exit 124). No `nats_connect_failed` terminal log; no `jarvis_startup_aborted`. **Violates broker-as-hard-dependency posture.** Fix scope: bound `nats_client.connect(...)` with `asyncio.wait_for(timeout=10s)`; emit terminal `nats_connect_failed` event. See [TASK-J006-010](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-010-bound-startup-reconnect-broker-hard-fail.md). |

## Runbook divergences patched (5)

All patches landed in `docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md` during this session:

1. **§0.5 fail-mode hint** — llama-swap on GB10 is a native process (pid `pgrep -a llama-swap`), not a docker container. Added `journalctl` / process-log fallback.
2. **§2.1 / AC-005-02 heartbeat evidence** — runbook expected subject traffic on `fleet.heartbeat.jarvis`; jarvis uses KV-only heartbeat (re-publishes manifest to `agent-registry` KV bucket; DEBUG log line). Replaced with KV-revision-tick verification recipe.
3. **§3.2 OpenWebUI URL** — runbook said `:3000` (upstream OpenWebUI default for bridge networking); GB10 deployment uses `network: host` on `:8080`. Added GB10 port note.
4. **§3.2 pipe deployment + Valves** — runbook only said "verify pipe listed and toggled on"; this session discovered three load-bearing gaps: (a) `nats-py` is not pre-installed in `open-webui` container; (b) pipe must be pasted from `fleet-gateway/openwebui/nats_fleet_pipe.deploy.py` not the source-of-truth file; (c) `NATS_URL` Valve defaults to no-credentials, gets `Authorization Violation` from the authenticated GB10 broker. Patched with explicit recipe + verification SQLite query.
5. **§3.8 broker container name** — runbook said `docker stop nats`; GB10 container is `ships-computer-nats`. Parameterised as `${NATS_CONTAINER:-ships-computer-nats}` with blast-radius warning (specialist-agents + fleet-gateway briefly disconnect during the test).

## Other findings (not patched into runbook)

- **KV manifest content divergence (not a bug, but worth flagging):** the KV `agent-registry/jarvis` entry is produced by the existing `infrastructure/fleet_registration.build_jarvis_manifest()` factory (4 generic intents — `conversational.gpa`, `dispatch.by_capability`, `meta.dispatch`, `memory.recall`; 0 tools; template `general_purpose_agent`), NOT by the new FEAT-JARVIS-006 `infrastructure/manifest.py:build_manifest()` factory (1 `chat` tool, 1 `general.*` intent). The new factory exists in source but is not wired into the publish path. This may be intentional (avoid double-registration with the existing factory — see the new factory's own docstring noting "agent_id byte-compatible with existing fleet_registration"), or it may be a wiring gap. Not demo-blocking either way; behavioural smoke shows the supervisor reaches the same tool surface. Worth a brief design review post-demo.

## Multi-turn transcript (AC-005-04 evidence — not captured)

AC-005-04 was BLOCKED before turn-1 reply rendered. No multi-turn transcript exists. Once TASK-J006-009 lands, re-run §3.4 turns 1-3 verbatim and append the transcript to a new RESULTS file dated the rerun day.

## Working wire paths (proven this session)

- **Phase 0.5 llama-swap warmup:** `curl http://localhost:9000/v1/chat/completions` → 200 in 0.4s ✅
- **Phase 2.1 jarvis boot:** clean lifecycle, KV register, KV-heartbeat tick, NATS subscribe on `agents.command.jarvis` ✅
- **Phase 2.3 flat-`CommandPayload` smoke:** `nats request agents.command.jarvis '{"command":"chat","args":{...}}'` → supervisor reply listing full tool surface, RTT 9.8s warm ✅
- **Phase 3.3 Bug #1 dual-publish:** result tap on `agents.result.jarvis` captures the canonical envelope **and** the `reply_to` inbox delivers the same payload to the requester ✅

## Broken wire paths (this session)

- **OpenWebUI → jarvis chat gateway:** envelope decode regression (TASK-J006-009).
- **broker-down boot probe:** unbounded reconnect (TASK-J006-010).

## Failures and follow-ups

| Failure | Severity | Follow-up |
|---|---|---|
| `subscribe_with_reply` decodes flat `CommandPayload` only; pipe publishes `MessageEnvelope` → OpenWebUI traffic rejected | **P0 demo-blocker** | [TASK-J006-009](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-009-fix-subscribe-with-reply-envelope-unwrap.md) — fix `nats_client.py:266-280`, ~10 LoC + unit test |
| Startup reconnect to NATS is unbounded → broker-down hard-fail probe never terminates | **P0 demo-blocker (if broker hiccups)** | [TASK-J006-010](../../tasks/backlog/feat-jarvis-006-nats-chat-gateway/TASK-J006-010-bound-startup-reconnect-broker-hard-fail.md) — wrap connect in `asyncio.wait_for(10s)`, emit `nats_connect_failed` terminal log |
| Shutdown steps 5a (unsubscribe) and 5b (drain in-flight when empty) emit no log lines; runbook's grep-for-unsubscribe AC-005-07 evidence pattern can't find them | Low (observability only — behaviour verified by code reading + KV deregister) | Future small task: add `log.info("jarvis_serve_nats_unsubscribed")` after `subscription.unsubscribe()` and `log.info("jarvis_serve_nats_drain_in_flight_complete", waited_seconds=...)` after the 5b loop in `cli/main.py`. ~3 LoC. |
| OpenWebUI `nats-py` install drift: not in base image, installed ad-hoc this session via `docker exec open-webui pip install nats-py` (lost on container restart) | Medium | Fold `nats-py` into the open-webui image build, or add to a `requirements.txt` mounted into the container. Owner: fleet-gateway / OpenWebUI deployment team. |
| OpenWebUI pipe NATS_URL Valve default ships without credentials (`nats://localhost:4222`) — Authorization Violation on auth-enabled brokers | Medium | Either (a) make the Valve default read `${NATS_URL}` from env; (b) document the required credentialed URL in the OpenWebUI pipe description text so it's visible at deploy time; (c) ship a deployment script that pre-fills the Valve. Owner: fleet-gateway team. |

## Demo-day notes (2026-05-16)

- **Critical path:** TASK-J006-009 MUST land before 2026-05-16. Without it, no OpenWebUI demo is possible.
- **Strongly recommended:** TASK-J006-010 lands before 2026-05-16. If the broker hiccups during demo prep, the gateway will silently hang without the fix.
- **Workaround if TASK-J006-009 slips:** the demo can fall back to a `nats request` CLI session driven by the operator from a side terminal. This proves the supervisor + dispatch chain end-to-end (Phase 2.3 evidence already captured) but loses the visual OpenWebUI chat experience. Not advisable.
- **Pre-flight rerun:** after TASK-J006-009 + TASK-J006-010 land, rerun this entire runbook (Phases 0-4) on GB10 and write a fresh RESULTS file with `git rev-parse HEAD` from the post-fix tree. AC-005-03..06 must flip ✅, AC-005-08 must flip ✅. Only then run `/task-complete TASK-J006-005`.

## Session housekeeping

- One-off `pip install nats-py` performed in `open-webui` container during §3.1 (operator approved via prompt). Lost on container restart; flagged for fleet-gateway team.
- `ships-computer-nats` was stopped briefly (37s wall-clock) during §3.8; broker is back up and healthy. Specialist-agents (`specialist-agent-architect-agent-1`, `specialist-agent-product-owner-agent-1`) were both up before and after; their reconnect behaviour was not separately verified.
- Wire-tap subscriptions on `agents.command.>`, `agents.result.>`, `pipeline.>` were torn down before broker stop in §3.8.
- All log artefacts copied into `docs/runbooks/evidence/feat-jarvis-006-first-run/` as listed in the AC table above.
