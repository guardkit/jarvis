# Phase 3: Fleet Integration — NATS Specialist Dispatch & Build Queue Dispatch to Forge — Scope Document

## For: Claude Code `/system-design` → `/feature-spec` → `/feature-plan` → AutoBuild (per feature)
## Date: 20 April 2026
## Status: Blocked on Phase 2 completion (FEAT-JARVIS-002 + FEAT-JARVIS-003 merged, routing-e2e test green, `langgraph dev` spinning 5 graphs cleanly). Ready for `/system-design FEAT-JARVIS-004` once Phase 2 closes.
## Context: Phase 2 shipped the dispatch tools with stubbed transports. Phase 3 swaps the stubs for real NATS — Jarvis registers on `fleet.register`, discovers specialist capabilities via `NATSKVManifestRegistry`, dispatches via `agents.command.{agent_id}`, and publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}`. This is also where ADR-FLEET-001 trace-richness writes to `jarvis_routing_history` go live for the first time.

---

## Motivation

After Phase 2, Jarvis's supervisor can reason about dispatch — it picks `call_specialist` vs `queue_build` vs subagent, and the reasoning over tool descriptions works. But the dispatch tools are stubs. Nothing actually reaches the specialist-agent fleet or the Forge pipeline. Phase 3 fixes that.

Two features, tightly coupled:

1. **FEAT-JARVIS-004** establishes the fleet contract. Jarvis registers itself via `fleet.register` (making it visible to other agents), discovers specialists via live reads of `NATSKVManifestRegistry` (same pattern Forge uses per ADR-ARCH-015/016), and round-trips `agents.command.{agent_id}` / `agents.result.{agent_id}` per ADR-SP-016. The capability catalogue stub from Phase 2 is replaced with real `NATSKVManifestRegistry` integration — the `CapabilityDescriptor` shape landed in Phase 2 was designed for exactly this swap.
2. **FEAT-JARVIS-005** consumes 004's plumbing to publish build intent. One pattern: publish `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per Forge ADR-SP-014 Pattern A, with the full `triggered_by="jarvis"`, `originating_adapter`, `correlation_id`, `parent_request_id` set correctly. Plus a notification subscription to `pipeline.stage-complete.*` so Jarvis can surface Forge progress back to Rich.

Phase 3 is also where ADR-FLEET-001 trace-richness writes light up for the first time. Every specialist dispatch and every build-queue publish writes a trace-rich record to `jarvis_routing_history` Graphiti group. The schema was committed in Phase 1 (shape-only) and Phase 2 (via subagent dispatch sequences compatible with it). Phase 3 makes it real. This is cheap now and nearly impossible to retrofit later — trace-rich records compound, `jarvis.learning` (FEAT-JARVIS-008, v1.5) reads them.

The first real FEAT-JARVIS-005 test case is **not** a canned `hello-world` (per Q10.6). It's a genuinely useful Jarvis internal improvement — Rich selects the candidate at Phase 3 time. Three candidates to pick from: (a) a Jarvis-side docstring cleanup or README polish task packaged as a feature spec, (b) a trace-schema refinement for `jarvis_routing_history` that Jarvis dogfoods on its own plumbing, (c) a small skill scaffolding task that pre-stages FEAT-JARVIS-007's Phase 4 work. Whichever Rich picks, the test proves the full round trip: Jarvis queues a real build, Forge consumes it, stage-complete notifications flow back, and Rich sees progress surface in `jarvis chat`.

After Phase 3, Jarvis v1 is *functionally complete for dispatch*. The supervisor can reason about a problem, pick a brain (subagent), pick a specialist (architect / PO / ideation via NATS), or queue a build (Forge via JetStream). The attended-surface value proposition is real. Only Phase 4 — adapters beyond CLI, skills, Memory Store activation — remains.

---

## Scope: Two Features

### FEAT-JARVIS-004: NATS Fleet Registration & Specialist Dispatch

**Problem:** Phase 2's `call_specialist` is stubbed transport. The tool builds a real `CommandPayload` (via `nats-core`), logs as if publishing, and returns a stubbed `SpecialistResult`. Phase 2's `list_available_capabilities` reads from a 4-row YAML stub. Neither talks to NATS. Phase 3 replaces both with real NATS integration, and — critically — establishes Jarvis's own fleet membership by registering an `AgentManifest` on `fleet.register`. Fleet registration matters: ADR-J-P4 (Jarvis registers on `fleet.register`) is what lets other agents (Forge emitting `jarvis.notification.*`, future agents wanting Jarvis's GPA-level tools) discover Jarvis. It's not a nice-to-have; it's the symmetric property of the fleet contract.

**Changes required:**

#### 1. NATS client wiring (`src/jarvis/infrastructure/nats_client.py`)

Thin wrapper around `nats-py` providing:

- Async connection lifecycle (connect on startup, drain on shutdown) integrated with `infrastructure/lifecycle.py` from Phase 1.
- Connection config from `JarvisConfig`: `JARVIS_NATS_URL` (default `nats://localhost:4222`), credentials file path, reconnect policy.
- Exposes the underlying `nats.aio.client.Client` and JetStream context as properties.
- Structured logging on connect/disconnect/reconnect events.

`pyproject.toml` gains `nats-py` (first time — Phase 2 only imported `nats-core` Pydantic models without a network client).

#### 2. Fleet registration (`src/jarvis/infrastructure/fleet_registration.py`)

Per ADR-J-P4:

- On startup, Jarvis publishes its own `AgentManifest` to `fleet.register` via `NATSKVManifestRegistry` from `nats-core`. Manifest includes:
  - `agent_id="jarvis"`
  - `role="general_purpose_agent"`
  - Capability list: conversational, dispatch, skill invocation, memory recall (Phase 3 lists what's real; Phase 4 extends with skills)
  - `trust_tier` per `nats-core` convention
  - Intent signatures for GPA tasks + meta-dispatch (per `jarvis-vision.md` §8)
- Heartbeat loop: periodic republish per `nats-core`'s heartbeat convention.
- On shutdown, deregister cleanly.

Jarvis appearing in `fleet.register` means Forge can emit `jarvis.notification.*` knowing Jarvis is live. It also means future agents can discover Jarvis's GPA-level tools. It's the fleet contract's symmetric property.

#### 3. `NATSKVManifestRegistry` integration for catalogue reads (`src/jarvis/tools/capabilities.py`)

Phase 2's stub-backed `list_available_capabilities` becomes real:

- At supervisor startup, instantiate `NATSKVManifestRegistry` from `nats-core` with the JetStream context.
- The registry maintains a 30-second in-process cache with KV watch invalidation per ADR-ARCH-017 (inherited from Forge's `NATSKVManifestRegistry` usage).
- `list_available_capabilities()` queries the registry and renders `CapabilityDescriptor`s — **the Pydantic shape is identical to Phase 2's stub**; only the source changes.
- `capabilities_refresh()` forces a cache refresh.
- `capabilities_subscribe_updates()` wires a KV-watch callback so capability changes (new specialist role coming online, heartbeat timeout) are picked up without a restart.
- Stub `stub_capabilities.yaml` remains in-tree as a fallback for tests and for local dev when NATS is unavailable, but is no longer the production source.

#### 4. `call_specialist` real transport (`src/jarvis/tools/dispatch.py`)

Phase 2's stubbed `call_specialist` is rewritten:

- Publishes `CommandPayload` to `agents.command.{agent_id}` (singular per ADR-SP-016).
- Awaits `ResultPayload` on `agents.result.{agent_id}` with a configurable timeout (default from `/system-design` ADR — probable range: 30–120 seconds).
- Correlates request/response via `correlation_id` in the payload.
- On timeout: retries with redirect — picks an alternative specialist via `list_available_capabilities` if another agent matches the capability (same pattern as Forge's redirect policy). If no alternative, returns a structured timeout error the supervisor surfaces to Rich.
- Full payload shape compliance with `nats-core`'s `CommandPayload` + `ResultPayload`.

Tool signature, docstring, and Pydantic return type are unchanged from Phase 2. The reasoning model's behaviour is identical; the transport is now real.

#### 5. ADR-FLEET-001 trace-richness writes (`src/jarvis/infrastructure/routing_history.py`)

First live writes to `jarvis_routing_history` Graphiti group. Per ADR-FLEET-001, every specialist dispatch writes a decision record with:

- Decision identity: `decision_id`, `surface="jarvis"`, `session_id`, `timestamp`.
- Reasoning context: supervisor tool-call sequence leading to the dispatch, priors retrieved (empty in Phase 3 — learning isn't reading yet), capability snapshot at decision time (hash reference).
- Subagent delegation: `subagent_type="specialist"`, `agent_id`, `subagent_task_id` (the correlation ID), `subagent_trace_ref` (LangSmith link or NATS correlation ref), `subagent_final_state` (success/error/timeout/cancelled).
- Resource cost: model calls made during the supervisor's dispatch reasoning, wall-clock time.
- Outcome: approved/redirected/timed-out + structured detail.
- Human response: populated later if Rich redirects mid-conversation; blank at dispatch time.
- Environmental context: `project_id` (from session metadata), local time-of-day, recent session refs, concurrent workload (if discoverable).
- **Jarvis-specific extensions** per ADR-FLEET-001's "per-group extension" clause: `chosen_specialist_id`, `alternatives_considered` (list of capability descriptors the supervisor saw but didn't pick), `supervisor_reasoning_summary` (the supervisor's own rationale text from its tool-call sequence).

Writes are fire-and-forget async — the dispatch returns to the supervisor without waiting for the Graphiti write to complete. Failures to write are logged as `WARN` (not `ERROR`) so transient Graphiti unavailability doesn't break dispatch.

Graphiti client is configured from `JarvisConfig` (`JARVIS_GRAPHITI_ENDPOINT`, etc.). `pyproject.toml` gains `graphiti-core`. If Graphiti is unreachable at startup, Jarvis still starts — dispatches still work; the trace writes are lost for that outage window and logged as `WARN`.

The schema is authoritative for the rest of v1 and beyond. Retrofits are expensive. JA1 (exact Pydantic shape) from the architecture conversation-starter is resolved here.

#### 6. Tests

- Integration tests using an **in-process `nats-py` test server** (not real `nats-infrastructure` — a Phase 3 soft-prereq that's not yet running on GB10 per the conversation starter):
  - Jarvis registers on `fleet.register` at startup; manifest is queryable from the registry.
  - `list_available_capabilities` returns capabilities for agents registered on the test server.
  - `call_specialist` round-trips with a mocked specialist consumer — the consumer subscribes to `agents.command.jarvis-test-specialist`, returns a canned `ResultPayload`, and Jarvis's supervisor sees the result.
  - `call_specialist` timeout path: no consumer reply; Jarvis times out; if another registered agent matches the capability, retry-with-redirect fires; if not, structured error returned.
  - `jarvis_routing_history` trace-rich writes land to an in-memory Graphiti stub matching the ADR-FLEET-001 schema.
- Unit tests for `routing_history.py` schema construction — verify every field is populated correctly under happy path + timeout + redirect scenarios.
- Contract tests: assert the real `CommandPayload` / `ResultPayload` / `AgentManifest` from `nats-core` match what Jarvis emits + consumes.

---

### FEAT-JARVIS-005: Build Queue Dispatch to Forge

**Problem:** Phase 2's `queue_build` is stubbed — it builds a real `BuildQueuedPayload` but log-only. Phase 3 wires real JetStream publishes per Forge ADR-SP-014 Pattern A. Plus a notification subscription so Jarvis can tell Rich when Forge stages complete.

**Changes required:**

#### 1. `queue_build` real transport (`src/jarvis/tools/dispatch.py`)

- Phase 2's stubbed `queue_build` is rewritten to publish `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` via JetStream per ADR-SP-014 Pattern A.
- `triggered_by="jarvis"` (hardcoded).
- `originating_adapter` pulled from session metadata (CLI in Phase 3; Telegram/Dashboard/Reachy as FEAT-JARVIS-006+ lands).
- `correlation_id` generated fresh per queue.
- `parent_request_id` from session metadata if Rich's request has a prior request ID (e.g. a redirect from a `call_specialist` that rerouted to a build).
- Returns a `QueueBuildAck` with the `correlation_id` so Rich can follow progress.
- Fire-and-forget; no await for Forge to pick up the job. Durable in JetStream per ADR-SP-017 retention policy.

#### 2. Notification subscription (`src/jarvis/infrastructure/forge_notifications.py`)

- Jarvis subscribes to `pipeline.stage-complete.*` at startup. Payloads are Forge's progress events per ADR-SP-014.
- Subscription filter: only surface notifications whose `correlation_id` matches a queued build Jarvis originated (tracked in a local correlation map).
- Surface matching notifications back to Rich via the session's adapter. In Phase 3, adapters = CLI only, so the notification prints to the chat on the next prompt cycle. (Telegram / Dashboard / Reachy adapters pick this up in FEAT-JARVIS-006+ — the mechanism is adapter-agnostic.)
- Per fleet v3, the `jarvis.notification.*` topic pattern applies; stage-complete events are bridged into `jarvis.notification.forge-stage-complete.{correlation_id}` via an internal router so adapter-side subscription is uniform.

#### 3. Trace-rich writes for build queues (`src/jarvis/infrastructure/routing_history.py`)

Per ADR-FLEET-001, every `queue_build` dispatch writes a decision record to `jarvis_routing_history` with `subagent_type="forge_build_queue"`, `subagent_task_id=correlation_id`. Outcome fields populated from the stage-complete notifications as they flow in (writes are append-only — later events add edges, don't overwrite the original record). Same authoritative schema from FEAT-JARVIS-004.

#### 4. First real test case — Rich's pick

Per Q10.6: genuinely useful Jarvis internal improvement, not canned `hello-world`. Three candidates Rich selects from at Phase 3 time:

- **(a) Docstring/README polish feature.** A FEAT-JARVIS-INTERNAL-001 spec that cleans up docstrings across `src/jarvis/`, standardises README sections, or similar low-risk improvement work. Small surface, obviously safe, good first exercise of the build pipeline.
- **(b) Trace-schema refinement feature.** A FEAT-JARVIS-INTERNAL-002 spec that extends the `jarvis_routing_history` schema with one or two additional fields Rich finds useful in the first few days of trace capture — Jarvis dogfooding its own learning-infrastructure plumbing. Nicely recursive; proves the schema isn't frozen.
- **(c) Skill scaffolding feature.** A FEAT-JARVIS-INTERNAL-003 spec that pre-stages FEAT-JARVIS-007's Phase 4 work — scaffolds the `skills/` package, lands the three skill module stubs (`morning-briefing.py`, `talk-prep.py`, `project-status.py`) as empty-but-importable. Phase 4 then fills them in. Useful overlap but Phase 4 might want to own the skill package scaffold entirely; flag if chosen.

Whichever Rich picks, the end-to-end test is the same shape: Jarvis queues the feature via `queue_build`, Forge consumes it, stage-complete notifications flow back, Jarvis surfaces progress to Rich. Phase 3 includes a brief spec-writing step for the chosen feature — it becomes the concrete artefact `queue_build` is tested against.

Phase 3 scope note: this test case's FEAT-JARVIS-INTERNAL-*** feature is built by Forge, not by Jarvis. Phase 3 builds FEAT-JARVIS-004 and FEAT-JARVIS-005 on the Jarvis side; the internal-improvement feature is the *payload* of FEAT-JARVIS-005's acceptance test.

#### 5. Tests

- Integration: `queue_build` publishes to an in-process JetStream test server; a mock Forge consumer picks up the message; assert payload shape.
- Integration: Jarvis subscribes to `pipeline.stage-complete.*`; the mock Forge consumer emits a fake stage-complete; Jarvis bridges it to `jarvis.notification.forge-stage-complete.{correlation_id}`; CLI adapter surfaces it.
- Contract: `BuildQueuedPayload` emitted by Jarvis matches Forge's `forge_pipeline_state_machine` consumer expectations (this test uses Forge's test fixtures if exported; otherwise a handshake test against the `nats-core` Pydantic model).
- End-to-end against real Forge (soft-prereq; Forge must be running): queue the Rich-chosen FEAT-JARVIS-INTERNAL feature, observe real build progress, validate notifications surfaced.

---

## Do-Not-Change

1. **Fleet v3 D40–D46, ADR-J-P1..P10, ADR-FLEET-001, ADR-SP-014 Pattern A, ADR-SP-016 singular topics, ADR-SP-017 retention.** Phase 3 is the first real consumer of P4 (fleet.register), P6 (trace-richness), and SP-014 Pattern A; honour, don't re-litigate.
2. **Phase 1 + Phase 2 outputs.** Supervisor, sessions, tools, subagents, prompt. Phase 3 *extends* `tools/dispatch.py` and `tools/capabilities.py` with real transport but does not change their signatures or docstrings. The reasoning model's view of the world is identical.
3. **`CapabilityDescriptor` Pydantic shape.** Designed in Phase 2 for the stub-to-real swap. Any shape change during Phase 3 is a regression.
4. **Subagent descriptions (FEAT-JARVIS-003).** Phase 3 does not touch them.
5. **`nats-core` Pydantic models are the contract.** `CommandPayload`, `ResultPayload`, `BuildQueuedPayload`, `AgentManifest`, `NotificationPayload`. Jarvis consumes and emits them verbatim — no "just one extra field for Jarvis" shortcuts.
6. **Singular topic convention (ADR-SP-016).** `agents.command.*`, `agents.result.*`, `pipeline.build-queued.*`, `pipeline.stage-complete.*`. No plural forms anywhere.
7. **ADR-FLEET-001 schema.** Once Phase 3 starts writing, the schema is authoritative for v1 and beyond. JA1 resolves here — any post-Phase-3 schema extension is an append-only addition via ADR-FLEET-00X, not an overwrite.
8. **No new adapters in Phase 3.** CLI remains the only adapter. Telegram is FEAT-JARVIS-006 (Phase 4). Notifications from Forge surface via the CLI adapter in Phase 3.
9. **`jarvis.learning` does not start in Phase 3.** Writes to `jarvis_routing_history` land for the first time, but the *reader* (`jarvis.learning` module that detects patterns and proposes `CalibrationAdjustment` entities) is deferred to v1.5 (FEAT-JARVIS-008).
10. **Fallback behaviours.** Graphiti unavailable → Jarvis still starts, trace writes logged as `WARN`. NATS unavailable → Jarvis starts but dispatch tools return structured errors Rich can see. No silent failures. No partial-mode surprises.

---

## Success Criteria

1. All Phase 1 + Phase 2 tests still pass (no regressions).
2. Jarvis registers on `fleet.register` at startup; registration is visible to the in-process test NATS server + (when available) the GB10 NATS server.
3. `list_available_capabilities` returns real capabilities from `NATSKVManifestRegistry` (plus registered test specialists in integration tests).
4. `call_specialist` round-trips with a mocked specialist consumer in integration tests — request `CommandPayload`, response `ResultPayload`, supervisor surfaces result.
5. `call_specialist` timeout path + retry-with-redirect work as specified.
6. `queue_build` publishes real `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` in integration tests.
7. `pipeline.stage-complete.*` subscription routes matching notifications to `jarvis.notification.forge-stage-complete.*` and the CLI adapter surfaces them.
8. `jarvis_routing_history` trace-rich writes land for every specialist dispatch and every build queue dispatch — schema matches ADR-FLEET-001.
9. Graphiti-unavailable and NATS-unavailable fallback behaviours tested.
10. End-to-end test against real Forge: Rich-chosen FEAT-JARVIS-INTERNAL feature queued, consumed, stage-complete notifications flowed, result visible in `jarvis chat`. This is the Phase 3 close criterion.
11. Contract tests against `nats-core` payloads all green.
12. Ruff + mypy clean on new `src/jarvis/` modules.

---

## Files That Will Change

| File | Feature | Change Type |
|------|---------|------------|
| `pyproject.toml` | FEAT-JARVIS-004, -005 | **UPDATED** — add `nats-py`, `graphiti-core` (first real NATS client + Graphiti client) |
| `src/jarvis/config/settings.py` | FEAT-JARVIS-004, -005 | **UPDATED** — `nats_url`, `nats_credentials_path`, `graphiti_endpoint`, `graphiti_api_key`, specialist dispatch timeout default |
| `src/jarvis/infrastructure/nats_client.py` | FEAT-JARVIS-004 | **NEW** — async NATS connection lifecycle |
| `src/jarvis/infrastructure/fleet_registration.py` | FEAT-JARVIS-004 | **NEW** — Jarvis's own `AgentManifest` registration on `fleet.register` + heartbeat |
| `src/jarvis/infrastructure/routing_history.py` | FEAT-JARVIS-004, -005 | **NEW** — trace-rich writes to `jarvis_routing_history` Graphiti group |
| `src/jarvis/infrastructure/forge_notifications.py` | FEAT-JARVIS-005 | **NEW** — `pipeline.stage-complete.*` subscriber + `jarvis.notification.*` router |
| `src/jarvis/infrastructure/lifecycle.py` | FEAT-JARVIS-004, -005 | **UPDATED** — NATS connect on startup, Graphiti connect on startup, register on fleet, start notification subscriber; drain + deregister on shutdown |
| `src/jarvis/tools/capabilities.py` | FEAT-JARVIS-004 | **UPDATED** — stub replaced with `NATSKVManifestRegistry` integration; signatures + Pydantic shape unchanged |
| `src/jarvis/tools/dispatch.py` | FEAT-JARVIS-004, -005 | **UPDATED** — `call_specialist` real transport (round-trip + timeout + retry); `queue_build` real transport (JetStream publish + correlation tracking) |
| `src/jarvis/sessions/manager.py` | FEAT-JARVIS-005 | **UPDATED** — surfaces pending Forge notifications on next CLI prompt cycle |
| `src/jarvis/cli/main.py` | FEAT-JARVIS-005 | **UPDATED** — renders incoming `jarvis.notification.forge-stage-complete.*` between prompts in `jarvis chat` |
| `tests/test_fleet_registration.py` | FEAT-JARVIS-004 | **NEW** — registration + heartbeat + deregister |
| `tests/test_capabilities_real.py` | FEAT-JARVIS-004 | **NEW** — `NATSKVManifestRegistry`-backed catalogue reads |
| `tests/test_dispatch_call_specialist.py` | FEAT-JARVIS-004 | **UPDATED** — Phase 2 stub tests + new integration tests (round-trip, timeout, redirect) |
| `tests/test_dispatch_queue_build.py` | FEAT-JARVIS-005 | **UPDATED** — Phase 2 stub tests + new integration test (real JetStream publish) |
| `tests/test_forge_notifications.py` | FEAT-JARVIS-005 | **NEW** — stage-complete subscription + routing + correlation filter |
| `tests/test_routing_history_writes.py` | FEAT-JARVIS-004, -005 | **NEW** — schema-compliant writes on dispatch + queue-build + redirect paths |
| `tests/test_graphiti_unavailable.py` | FEAT-JARVIS-004 | **NEW** — Jarvis starts, dispatches succeed, traces logged as WARN |
| `tests/test_nats_unavailable.py` | FEAT-JARVIS-004 | **NEW** — Jarvis starts, dispatch tools return structured errors Rich can see |
| `tests/test_contract_nats_core.py` | FEAT-JARVIS-004, -005 | **NEW** — contract tests against `nats-core` payload schemas |
| `tests/test_end_to_end_forge_roundtrip.py` | FEAT-JARVIS-005 | **NEW** — soft-prereq end-to-end test (real Forge + real NATS); Rich-chosen FEAT-JARVIS-INTERNAL feature as payload |
| `docs/design/FEAT-JARVIS-004/design.md` | FEAT-JARVIS-004 | **NEW** |
| `docs/design/FEAT-JARVIS-005/design.md` | FEAT-JARVIS-005 | **NEW** |
| `features/feat-jarvis-004-*/...` | FEAT-JARVIS-004 | **NEW** |
| `features/feat-jarvis-005-*/...` | FEAT-JARVIS-005 | **NEW** |
| `tasks/FEAT-JARVIS-004-*.md` | FEAT-JARVIS-004 | **NEW** |
| `tasks/FEAT-JARVIS-005-*.md` | FEAT-JARVIS-005 | **NEW** |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/`.

---

## Open Questions `/system-design` Resolves (for Phase 3's benefit)

- **`call_specialist` timeout default.** 30s? 60s? 120s? Depends on specialist-agent typical response latency.
- **Redirect policy details.** When retry-with-redirect fires, does Jarvis prefer same-role with different `agent_id`, or different-role with matching capability? Per ADR-J-P4 spirit: prefer same-capability match.
- **Graphiti write batching.** Every dispatch write separately, or batched per session? Latency/cost tradeoff. Default recommendation: per-dispatch, fire-and-forget.
- **Concurrent dispatch cap.** How many in-flight `call_specialist` / `queue_build` invocations before throttling? Related to JA2 (ambient watcher ceiling) but distinct — this is for synchronous supervisor-initiated dispatch.
- **JA1 full resolution.** Exact Pydantic shape of `jarvis_routing_history` entries — Phase 3 commits the schema. `/system-design FEAT-JARVIS-004` is where the exact field list lands (building on ADR-FLEET-001's base + Jarvis-specific extensions noted above).
- **`jarvis.notification.forge-stage-complete.*` routing.** Is the router a dedicated module or a method on `SessionManager`? Impacts how FEAT-JARVIS-006 (Telegram) slots in.
- **Rich's FEAT-JARVIS-005 test case choice.** Which of the three candidates (docstring polish / trace-schema refinement / skill scaffolding) becomes FEAT-JARVIS-INTERNAL-001's concrete spec. Resolve before Step 11 (the end-to-end test).

---

*Scope document: 20 April 2026*
*Input to: `/system-design FEAT-JARVIS-004`, `/system-design FEAT-JARVIS-005`.*
*"The fleet contract is symmetric."*
