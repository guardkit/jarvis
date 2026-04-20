# Phase 3 Build Plan — Fleet Integration: NATS Specialist Dispatch & Build Queue Dispatch to Forge

## For: Swapping Phase 2's stubbed transports for real NATS — Jarvis registers on `fleet.register`, dispatches via `agents.command.*`, publishes to `pipeline.build-queued.*`, and writes its first ADR-FLEET-001 trace-rich records to `jarvis_routing_history`. After Phase 3, Jarvis v1 is functionally complete for dispatch.
## Date: 20 April 2026
## Status: Blocked on Phase 2 completion. Ready for `/system-design FEAT-JARVIS-004` once Phase 2 closes.
## Repo: `guardkit/jarvis`
## Machine: MacBook Pro M2 Max (planning + build via Claude Code). Integration tests use in-process NATS/Graphiti; end-to-end test requires NATS on GB10 + Forge running + Graphiti on GB10.

---

## Status Log

| Date | Step | Outcome |
|------|------|---------|
| 2026-04-20 | `phase3-fleet-integration-scope.md` written | Scope doc — input to `/system-design FEAT-JARVIS-004` and `/system-design FEAT-JARVIS-005`. |
| 2026-04-20 | `phase3-build-plan.md` written | This document. |
| *pending* | Phase 2 close | FEAT-JARVIS-002 + FEAT-JARVIS-003 merged, routing-e2e test green, `langgraph dev` spinning 5 graphs cleanly. |
| *pending* | Soft-prereq check — NATS on GB10 + Forge running | End-to-end test (Step 14 below) requires both. Integration tests up to Step 13 use in-process test servers and are unaffected. |
| *pending* | Rich selects FEAT-JARVIS-INTERNAL-*** candidate | Per Q10.6 — choose from: (a) docstring/README polish, (b) trace-schema refinement, (c) skill scaffolding. Resolve before Step 14. |
| *pending* | `/system-design FEAT-JARVIS-004` | Design doc. |
| *pending* | `/system-design FEAT-JARVIS-005` | Design doc. |
| *pending* | `/feature-spec FEAT-JARVIS-004` | Gherkin scenarios. |
| *pending* | `/feature-spec FEAT-JARVIS-005` | Gherkin scenarios. |
| *pending* | `/feature-plan FEAT-JARVIS-004` | Task breakdown. |
| *pending* | `/feature-plan FEAT-JARVIS-005` | Task breakdown. |

---

## What Phase 3 IS

The phase where Jarvis joins the fleet for real. Two features, tightly coupled:

- **FEAT-JARVIS-004** — NATS integration: Jarvis registers on `fleet.register` (ADR-J-P4), discovers specialists via `NATSKVManifestRegistry`, dispatches via `agents.command.{agent_id}` / `agents.result.{agent_id}` with timeout + retry-with-redirect. Phase 2's stubbed `call_specialist` becomes real.
- **FEAT-JARVIS-005** — Forge integration: `queue_build` publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` per ADR-SP-014 Pattern A. Jarvis subscribes to `pipeline.stage-complete.*` and surfaces matching notifications back to Rich via the CLI adapter.

Phase 3 also lights up the **first live ADR-FLEET-001 trace-rich writes** to `jarvis_routing_history`. Every specialist dispatch and every build queue writes a schema-compliant decision record. The schema is authoritative from here onward — retrofits are expensive and `jarvis.learning` (FEAT-JARVIS-008, v1.5) reads these records.

The Phase 3 close criterion is the end-to-end test: Jarvis queues a Rich-chosen FEAT-JARVIS-INTERNAL-*** feature, Forge consumes it, stage-complete notifications flow back, Rich sees progress in `jarvis chat`.

## What Phase 3 IS NOT

- Not Telegram, Dashboard, or Reachy adapters. Still CLI-only. FEAT-JARVIS-006 (Phase 4) adds Telegram.
- Not skills. FEAT-JARVIS-007 (Phase 4) adds `morning-briefing`, `talk-prep`, `project-status`.
- Not `jarvis.learning`. Writes to `jarvis_routing_history` land for the first time, but the *reader* defers to v1.5 (FEAT-JARVIS-008).
- Not the real `system.health.vllm` signal for `quick_local` fallback. Still stubbed from Phase 2. Real health-signal producer is v1.5.
- Not GDPR trace purge (`jarvis purge-traces`). FEAT-JARVIS-011 (v1.1).
- Not horizontal scaling. Single Jarvis process per user, per GB10 (mirrors Forge ADR-ARCH-027).

## Success Criteria

1. All Phase 1 + Phase 2 tests still pass (zero regressions).
2. Jarvis registers on `fleet.register` at startup; registration is visible in the in-process test NATS server.
3. `list_available_capabilities` returns real capabilities from `NATSKVManifestRegistry`.
4. `call_specialist` round-trips with a mocked specialist consumer in integration tests (request → response; timeout → retry-with-redirect; all-specialists-exhausted → structured error).
5. `queue_build` publishes real `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` in integration tests.
6. `pipeline.stage-complete.*` subscription routes correlation-matched notifications to `jarvis.notification.forge-stage-complete.*`; CLI adapter surfaces them between prompts.
7. `jarvis_routing_history` trace-rich writes land for every specialist dispatch and every build queue; schema matches ADR-FLEET-001 + Jarvis-specific extensions.
8. Graphiti-unavailable fallback: Jarvis starts, dispatches succeed, trace writes logged as WARN (not ERROR).
9. NATS-unavailable fallback: Jarvis starts, dispatch tools return structured errors Rich can see in `jarvis chat`.
10. End-to-end test against real Forge passes: Rich-chosen FEAT-JARVIS-INTERNAL feature queued, consumed, stage-complete notifications flowed, result in `jarvis chat`.
11. Contract tests against `nats-core` payloads all green.
12. Ruff + mypy clean on new `src/jarvis/` modules.

---

## Phase 2 Results (Context)

Expected at Phase 3 start:

- 10 tools registered on supervisor (4 general + 3 capability + 2 dispatch + implicit subagent primitives)
- 4 async subagents declared at startup (`deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`)
- Supervisor system prompt teaches "cheapest-that-fits, escalate on need" across tools + subagents
- `langgraph.json` + ASGI transport spinning 5 graphs
- Routing-e2e test passes: 7 canned prompts route to expected tools/subagents
- `call_specialist` and `queue_build` are stubbed transport but build real `nats-core` payloads
- `CapabilityDescriptor` Pydantic shape landed — designed for Phase 3's stub-to-real swap
- `quick_local` fallback hook landed with stubbed health signal

**Gaps Phase 3 closes:**

| Gap | Impact | Source |
|-----|--------|--------|
| Phase 2 dispatch transports are stubs | Jarvis does not actually talk to the fleet — ADR-J-P1 still aspirational at the transport layer | Phase 2 scope doc (stubs explicit) |
| Jarvis does not register on `fleet.register` | Symmetric fleet contract broken — other agents cannot discover Jarvis's GPA-level tools | ADR-J-P4 |
| Capability catalogue is stubbed YAML | Not connected to real fleet state; new specialists coming online are invisible | Fleet v3 §3; ADR-ARCH-015/016 inheritance |
| No `jarvis_routing_history` writes | Learning flywheel has no data to learn from once it ships in v1.5 | ADR-FLEET-001; fleet v3 §7 |
| No Forge progress feedback loop | Rich queues a build and has no way to know when it completes without checking Forge directly | ADR-SP-014 Pattern A full round-trip |

---

## Feature Summary

| # | Feature | Depends On | Est. Complexity | Priority |
|---|---------|-----------|-----------------|----------|
| FEAT-JARVIS-004 | NATS Fleet Registration & Specialist Dispatch | FEAT-JARVIS-002 | Medium-High (real NATS + Graphiti + trace schema) | **High** (unblocks 005 and real attended dispatch) |
| FEAT-JARVIS-005 | Build Queue Dispatch to Forge | FEAT-JARVIS-004 | Medium (piggybacks on 004's NATS wiring) | **High** (closes the Jarvis→Forge loop) |

**Dependency graph:**

```
FEAT-JARVIS-002, -003 (Phase 2 — merged)
         │
         ▼
FEAT-JARVIS-004 (NATS fleet + specialist dispatch + trace writes)
         │
         ▼
FEAT-JARVIS-005 (Forge queue publish + stage-complete subscribe + trace writes)
         │
         ▼
End-to-end test with real Forge (Rich-chosen FEAT-JARVIS-INTERNAL-*** feature)
```

FEAT-JARVIS-005 is sequential on -004 — it consumes the NATS client, fleet registration, `routing_history.py`, and notification-routing plumbing established in 004. Parallel builds would risk rework. **Sequential: 004 first, then 005.**

---

## FEAT-JARVIS-004: NATS Fleet Registration & Specialist Dispatch

**Purpose:** Replace Phase 2's stub transports with real NATS; establish Jarvis's fleet membership; land the ADR-FLEET-001 trace-richness schema for live writes.

### Change 1: NATS client wiring (`src/jarvis/infrastructure/nats_client.py`)

**Files (NEW):**

- `src/jarvis/infrastructure/nats_client.py` — thin wrapper around `nats-py`:
  - Async connection lifecycle (connect on startup, drain on shutdown)
  - Config from `JarvisConfig`: `nats_url`, `nats_credentials_path`, reconnect policy
  - Exposes `nats.aio.client.Client` + JetStream context
  - Structured connect/disconnect/reconnect logging

`pyproject.toml` gains `nats-py`.

### Change 2: Fleet registration (`src/jarvis/infrastructure/fleet_registration.py`)

**Files (NEW):**

- `src/jarvis/infrastructure/fleet_registration.py`:
  - `register_jarvis(nats_client, config) -> None` — builds Jarvis's `AgentManifest` from config + publishes via `NATSKVManifestRegistry`
  - Heartbeat loop (asyncio task) — periodic republish per `nats-core` convention
  - Clean deregister on shutdown

Manifest contents: `agent_id="jarvis"`, `role="general_purpose_agent"`, capabilities (conversational, dispatch, memory recall), `trust_tier` per convention, intent signatures for GPA tasks + meta-dispatch.

### Change 3: `NATSKVManifestRegistry` integration (`src/jarvis/tools/capabilities.py`)

**File:** `src/jarvis/tools/capabilities.py` (UPDATED — Phase 2 created stub-backed version)

- `list_available_capabilities()` now reads from `NATSKVManifestRegistry` (30-second cache + KV watch invalidation per ADR-ARCH-017).
- `capabilities_refresh()` forces cache refresh.
- `capabilities_subscribe_updates()` wires KV-watch callback.
- Stub YAML (`stub_capabilities.yaml`) stays in-tree as a test + local-dev fallback; production uses NATS.
- `CapabilityDescriptor` Pydantic shape unchanged from Phase 2.

### Change 4: Real `call_specialist` (`src/jarvis/tools/dispatch.py`)

**File:** `src/jarvis/tools/dispatch.py` (UPDATED)

- Publishes `CommandPayload` to `agents.command.{agent_id}` (singular).
- Awaits `ResultPayload` on `agents.result.{agent_id}` with configurable timeout (ADR-pinned default at `/system-design`).
- `correlation_id` correlates request/response.
- Timeout path: retry-with-redirect — find alternative specialist via `list_available_capabilities` matching the same capability; if none, structured timeout error.
- Tool signature, docstring, Pydantic return type unchanged from Phase 2. Reasoning model behaviour identical.

### Change 5: ADR-FLEET-001 trace-rich writes (`src/jarvis/infrastructure/routing_history.py`)

**Files (NEW):**

- `src/jarvis/infrastructure/routing_history.py`:
  - `JarvisRoutingHistoryEntry` Pydantic model — full ADR-FLEET-001 base schema + Jarvis-specific extensions (`chosen_specialist_id`, `alternatives_considered`, `supervisor_reasoning_summary`)
  - `write_specialist_dispatch(entry) -> None` — fire-and-forget async Graphiti write
  - Failures → `WARN` log, not `ERROR`; dispatch unaffected
  - Graphiti client from `JarvisConfig` (`graphiti_endpoint`, `graphiti_api_key`)

`pyproject.toml` gains `graphiti-core`.

Writes live at the `call_specialist` + `queue_build` call boundaries — wrapped around the dispatch so success / timeout / redirect outcomes are all captured.

### Change 6: Lifecycle integration (`src/jarvis/infrastructure/lifecycle.py`)

**File:** `src/jarvis/infrastructure/lifecycle.py` (UPDATED — Phase 1 created)

- Startup: connect NATS → connect Graphiti → register on `fleet.register` → start heartbeat loop.
- Shutdown: stop heartbeat → deregister → drain NATS → close Graphiti client.
- Partial-mode handling: Graphiti unavailable → start anyway, log WARN; NATS unavailable → start anyway, dispatch tools return structured errors; neither is a hard startup failure except NATS for `queue_build` in Phase 4 (TBD in scope doc for Phase 4).

### Change 7: Config extensions (`src/jarvis/config/settings.py`)

**File:** `src/jarvis/config/settings.py` (UPDATED)

New fields: `nats_url`, `nats_credentials_path`, `graphiti_endpoint`, `graphiti_api_key`, `specialist_dispatch_timeout_seconds`.

### Change 8: Tests

**Files (NEW):**

- `tests/test_fleet_registration.py` — register at startup, heartbeat fires, deregister on shutdown
- `tests/test_capabilities_real.py` — `NATSKVManifestRegistry`-backed catalogue reads; cache behaviour; KV watch invalidation
- `tests/test_dispatch_call_specialist.py` (UPDATED from Phase 2) — round-trip with mocked specialist consumer; timeout; retry-with-redirect; exhausted-alternatives error
- `tests/test_routing_history_writes.py` — schema-compliant writes on happy/timeout/redirect paths against in-memory Graphiti stub
- `tests/test_graphiti_unavailable.py` — Jarvis starts; dispatches succeed; traces logged WARN
- `tests/test_nats_unavailable.py` — Jarvis starts; dispatch tools return structured errors Rich can see
- `tests/test_contract_nats_core.py` (UPDATED or NEW) — contract tests: Jarvis's emitted `CommandPayload` + consumed `ResultPayload` match `nats-core` schemas exactly

In-process NATS server (e.g. `nats-server -p 0 -js`) used for integration tests. No GB10 dependency at this layer.

### Invariants

- Phase 1 + Phase 2 test modules unchanged.
- `CapabilityDescriptor`, `SpecialistResult`, `QueueBuildAck` Pydantic shapes unchanged.
- Tool docstrings unchanged — reasoning model behaviour identical between Phase 2 (stubbed) and Phase 3 (real NATS).
- Singular topic convention (ADR-SP-016) for all topic strings.

---

## FEAT-JARVIS-005: Build Queue Dispatch to Forge

**Purpose:** Real `queue_build` + stage-complete notification subscription + Phase 3 close via end-to-end test with real Forge.

### Change 1: Real `queue_build` (`src/jarvis/tools/dispatch.py`)

**File:** `src/jarvis/tools/dispatch.py` (UPDATED — FEAT-JARVIS-004 updated it first)

- Publishes `BuildQueuedPayload` to `pipeline.build-queued.{feature_id}` via JetStream per ADR-SP-014 Pattern A.
- `triggered_by="jarvis"`, `originating_adapter` from session metadata, fresh `correlation_id`, `parent_request_id` from session metadata if present.
- Returns `QueueBuildAck` with `correlation_id` so Rich can follow progress.
- Fire-and-forget; durable in JetStream per ADR-SP-017.

### Change 2: Forge notification subscription (`src/jarvis/infrastructure/forge_notifications.py`)

**Files (NEW):**

- `src/jarvis/infrastructure/forge_notifications.py`:
  - Subscribes to `pipeline.stage-complete.*` at startup
  - Maintains a local correlation map (`correlation_id → session_id`) of queued builds Jarvis originated
  - Filters incoming stage-complete events by correlation_id
  - Bridges matched events to `jarvis.notification.forge-stage-complete.{correlation_id}` (internal router)
  - Session manager consumes the bridged notifications on next CLI prompt cycle

### Change 3: Trace-rich writes for build queues (`src/jarvis/infrastructure/routing_history.py`)

**File:** `src/jarvis/infrastructure/routing_history.py` (UPDATED — FEAT-JARVIS-004 created it)

- `write_build_queue_dispatch(entry) -> None` — same schema, `subagent_type="forge_build_queue"`, `subagent_task_id=correlation_id`.
- Append-only updates as stage-complete events arrive (each event adds an edge to the original decision record, doesn't overwrite).

### Change 4: CLI notification rendering (`src/jarvis/cli/main.py`)

**File:** `src/jarvis/cli/main.py` (UPDATED — Phase 1 created)

- `jarvis chat` REPL checks for pending `jarvis.notification.forge-stage-complete.*` events between prompts (via `SessionManager`).
- Renders them as timestamped lines above the next prompt — e.g. `[15:42] Forge FEAT-JARVIS-INTERNAL-001: stage plan-complete`.
- Non-blocking; does not delay user input.

### Change 5: Session manager notification integration (`src/jarvis/sessions/manager.py`)

**File:** `src/jarvis/sessions/manager.py` (UPDATED — Phase 1 created)

- `SessionManager` gains a `pending_notifications(session_id) -> list[Notification]` method.
- `end_session` clears pending notifications for the session.

### Change 6: Rich's FEAT-JARVIS-INTERNAL-*** feature spec

Not code — a feature spec written as the *payload* for the end-to-end test (Step 14 below). Rich picks one of three candidates before Step 14:

- **(a) Docstring/README polish.** Low-risk, broad-but-shallow edits across `src/jarvis/`. Good first exercise of the pipeline.
- **(b) Trace-schema refinement.** Extends `jarvis_routing_history` schema with 1–2 fields Rich finds useful after a few days of Phase 3 writes. Nicely recursive; proves the schema isn't frozen.
- **(c) Skill scaffolding.** Pre-stages FEAT-JARVIS-007 by landing empty-but-importable skill module stubs. Flag if chosen — Phase 4 might want to own skill scaffolding entirely.

The chosen feature spec is written using the normal `/feature-spec` pipeline (but against the Jarvis repo itself) before Step 14.

### Change 7: Tests

**Files (NEW or UPDATED):**

- `tests/test_dispatch_queue_build.py` (UPDATED from Phase 2) — real JetStream publish; mock Forge consumer reads; payload shape assertions
- `tests/test_forge_notifications.py` — stage-complete subscription; correlation-filter; `jarvis.notification.forge-stage-complete.*` routing; CLI rendering
- `tests/test_end_to_end_forge_roundtrip.py` — **soft-prereq test**: requires real Forge + NATS + Graphiti. Queues Rich-chosen FEAT-JARVIS-INTERNAL-*** feature; asserts Forge picks up the payload; asserts stage-complete notifications flow; asserts Rich can see progress in `jarvis chat`; asserts trace-rich records for both the queue-build dispatch and each stage-complete event
- Update `tests/test_routing_history_writes.py` (from FEAT-JARVIS-004) to cover build-queue write paths

### Invariants

- FEAT-JARVIS-004 outputs unchanged.
- `BuildQueuedPayload` emitted matches Forge's `nats-core` consumer expectations exactly.
- `pipeline.build-queued.{feature_id}`, `pipeline.stage-complete.*` — singular convention (ADR-SP-016).
- No changes to Phase 2's `queue_build` tool signature or docstring.

---

## GuardKit Command Sequence

### Step 1: /system-design FEAT-JARVIS-004

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis

/system-design FEAT-JARVIS-004 \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context docs/research/ideas/phase2-dispatch-foundations-scope.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/design/FEAT-JARVIS-002/design.md \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-017-live-kv-watch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../nats-core/docs/design/specs/nats-core-system-spec.md \
  --context ../nats-core/docs/design/contracts/agent-manifest-contract.md \
  --context ../nats-core/src/nats_core/manifest.py \
  --context ../nats-core/src/nats_core/topics.py \
  --context ../nats-core/src/nats_core/payloads/ \
  --context ../nats-infrastructure/docs/design/decisions/ADR-001-standalone-infra-repo.md \
  --context src/jarvis/tools/dispatch.py \
  --context src/jarvis/tools/capabilities.py \
  --context src/jarvis/infrastructure/lifecycle.py \
  --context .guardkit/context-manifest.yaml
```

Expected output: `docs/design/FEAT-JARVIS-004/design.md` — NATS client wiring, fleet-registration lifecycle, `NATSKVManifestRegistry` integration, `call_specialist` timeout/retry/redirect policy, `JarvisRoutingHistoryEntry` full Pydantic shape (resolves JA1), Graphiti write fire-and-forget pattern, fallback behaviour ADRs (Graphiti-unavailable, NATS-unavailable).

### Step 2: /system-design FEAT-JARVIS-005

```bash
/system-design FEAT-JARVIS-005 \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-014-build-queue-pattern-a.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../nats-core/src/nats_core/payloads/ \
  --context src/jarvis/tools/dispatch.py \
  --context src/jarvis/infrastructure/nats_client.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context src/jarvis/cli/main.py \
  --context src/jarvis/sessions/manager.py \
  --context .guardkit/context-manifest.yaml
```

Expected output: `docs/design/FEAT-JARVIS-005/design.md` — `queue_build` real transport details, `pipeline.stage-complete.*` subscription + filter, `jarvis.notification.forge-stage-complete.*` router location (module vs `SessionManager` method), CLI rendering pattern for mid-REPL notifications.

### Step 3: /feature-spec FEAT-JARVIS-004

```bash
/feature-spec "NATS Fleet Registration & Specialist Dispatch: Jarvis registers on fleet.register, discovers specialists via NATSKVManifestRegistry, dispatches via agents.command.{agent_id}/agents.result.{agent_id} with timeout + retry-with-redirect; first live jarvis_routing_history trace-rich writes per ADR-FLEET-001" \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../nats-core/src/nats_core/payloads/ \
  --context ../nats-core/src/nats_core/manifest.py \
  --context src/jarvis/tools/capabilities.py \
  --context src/jarvis/tools/dispatch.py \
  --context .guardkit/context-manifest.yaml
```

### Step 4: /feature-spec FEAT-JARVIS-005

```bash
/feature-spec "Build Queue Dispatch to Forge: queue_build publishes BuildQueuedPayload to pipeline.build-queued.{feature_id} per ADR-SP-014 Pattern A; Jarvis subscribes to pipeline.stage-complete.* and surfaces correlation-matched notifications to Rich via CLI adapter; trace-rich writes for build-queue dispatch" \
  --context docs/design/FEAT-JARVIS-005/design.md \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-014-build-queue-pattern-a.md \
  --context ../nats-core/src/nats_core/payloads/ \
  --context src/jarvis/tools/dispatch.py \
  --context src/jarvis/cli/main.py \
  --context .guardkit/context-manifest.yaml
```

### Step 5: /feature-plan FEAT-JARVIS-004

```bash
/feature-plan "NATS Fleet Registration & Specialist Dispatch" \
  --context features/feat-jarvis-004-*/feat-jarvis-004-*_summary.md \
  --context features/feat-jarvis-004-*/feat-jarvis-004-*.feature \
  --context features/feat-jarvis-004-*/feat-jarvis-004-*_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context .guardkit/context-manifest.yaml
```

Resolve low-confidence assumptions before Step 7.

### Step 6: /feature-plan FEAT-JARVIS-005

```bash
/feature-plan "Build Queue Dispatch to Forge" \
  --context features/feat-jarvis-005-*/feat-jarvis-005-*_summary.md \
  --context features/feat-jarvis-005-*/feat-jarvis-005-*.feature \
  --context features/feat-jarvis-005-*/feat-jarvis-005-*_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-005/design.md \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md \
  --context .guardkit/context-manifest.yaml
```

Resolve low-confidence assumptions before Step 9.

### Step 7: AutoBuild FEAT-JARVIS-004

Suggested commit order:

1. Config extensions (NATS + Graphiti env vars).
2. `infrastructure/nats_client.py` + config-level tests.
3. `infrastructure/fleet_registration.py` + `tests/test_fleet_registration.py`.
4. `infrastructure/routing_history.py` — Pydantic schema, write function, Graphiti client + schema unit tests.
5. `tools/capabilities.py` update: stub → `NATSKVManifestRegistry`; integration tests.
6. `tools/dispatch.py` update: `call_specialist` real transport (round-trip + timeout + redirect); integration tests + trace-write integration.
7. `infrastructure/lifecycle.py` update: NATS connect → Graphiti connect → register → heartbeat; drain + deregister.
8. Fallback tests (`test_graphiti_unavailable.py`, `test_nats_unavailable.py`).
9. Contract tests against `nats-core` (`test_contract_nats_core.py`).

### Step 8: /task-review FEAT-JARVIS-004

```bash
/task-review FEAT-JARVIS-004 \
  --context tasks/FEAT-JARVIS-004-*.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md
```

### Step 9: AutoBuild FEAT-JARVIS-005

Suggested commit order:

1. `tools/dispatch.py` update: `queue_build` real JetStream publish; integration tests.
2. `infrastructure/forge_notifications.py` + `tests/test_forge_notifications.py`.
3. `sessions/manager.py` update: `pending_notifications` method.
4. `cli/main.py` update: render notifications between prompts; CLI tests.
5. `infrastructure/routing_history.py` update: `write_build_queue_dispatch` + append-only edge writes; tests.

### Step 10: /task-review FEAT-JARVIS-005

```bash
/task-review FEAT-JARVIS-005 \
  --context tasks/FEAT-JARVIS-005-*.md \
  --context docs/research/ideas/phase3-fleet-integration-scope.md \
  --context docs/research/ideas/phase3-build-plan.md
```

### Step 11: Regression check

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
uv sync --dev
uv run pytest tests/ -v --tb=short --cov=src/jarvis
uv run ruff check src/jarvis/ tests/
uv run mypy src/jarvis/
uv run langgraph dev --no-browser  # re-validate langgraph.json
```

### Step 12: Integration-server check (in-process NATS + Graphiti stub)

Run the full integration-test suite against the in-process test servers. This is the portable Phase 3 floor — it does not require GB10.

### Step 13: Rich selects FEAT-JARVIS-INTERNAL-*** candidate + writes its feature spec

Before Step 14:

1. Rich chooses (a) docstring polish / (b) trace-schema refinement / (c) skill scaffolding.
2. Run the normal GuardKit pipeline on the chosen candidate against the Jarvis repo — a short `/feature-spec` + `/feature-plan` producing a real `FEAT-JARVIS-INTERNAL-001` feature in `features/` + `tasks/`.
3. This feature becomes the *payload* for Step 14's end-to-end test. Forge consumes it; Forge builds it; stage-complete events flow.

### Step 14: End-to-end test with real Forge (Phase 3 close criterion)

Hard prereqs:

- NATS running on GB10 (connectable from MacBook over Tailscale)
- Forge running and subscribed to `pipeline.build-queued.*`
- Graphiti / FalkorDB running on GB10
- All 4 subagent provider keys set (for any subagent dispatch the feature's build entails)

```bash
export JARVIS_NATS_URL="nats://100.x.y.z:4222"
export JARVIS_GRAPHITI_ENDPOINT="http://100.x.y.z:8080"
# ... other keys

jarvis chat
  > Queue FEAT-JARVIS-INTERNAL-001 for build
  [supervisor → queue_build → BuildQueuedPayload published]
  [ack rendered to Rich: "Queued FEAT-JARVIS-INTERNAL-001, correlation ..."]
  [Forge consumes, begins build]
  [stage-complete events flow back]
  [Jarvis renders between-prompt notifications:]
  [15:42] Forge FEAT-JARVIS-INTERNAL-001: plan-complete
  [15:44] Forge FEAT-JARVIS-INTERNAL-001: autobuild-complete
  [15:45] Forge FEAT-JARVIS-INTERNAL-001: task-review-complete — build succeeded
  > thanks Jarvis
  [supervisor responds]
  /exit

# Verify trace-rich writes landed in Graphiti:
# - One `jarvis_routing_history` entry for the queue_build dispatch
# - Edges added for each stage-complete event
# - Schema matches ADR-FLEET-001 + Jarvis extensions
```

Record the session and the Graphiti trace dump — this is Phase 3's evidence artefact.

---

## Files That Will Change

| File | Feature | Change Type |
|------|---------|------------|
| `pyproject.toml` | FEAT-JARVIS-004, -005 | **UPDATED** — `nats-py`, `graphiti-core` |
| `src/jarvis/config/settings.py` | FEAT-JARVIS-004 | **UPDATED** — `nats_url`, `nats_credentials_path`, `graphiti_endpoint`, `graphiti_api_key`, `specialist_dispatch_timeout_seconds` |
| `src/jarvis/infrastructure/nats_client.py` | FEAT-JARVIS-004 | **NEW** — async NATS connection lifecycle |
| `src/jarvis/infrastructure/fleet_registration.py` | FEAT-JARVIS-004 | **NEW** — Jarvis's `AgentManifest` registration + heartbeat |
| `src/jarvis/infrastructure/routing_history.py` | FEAT-JARVIS-004, -005 | **NEW** — `JarvisRoutingHistoryEntry` Pydantic + `write_specialist_dispatch` + `write_build_queue_dispatch` |
| `src/jarvis/infrastructure/forge_notifications.py` | FEAT-JARVIS-005 | **NEW** — `pipeline.stage-complete.*` subscriber + `jarvis.notification.*` router |
| `src/jarvis/infrastructure/lifecycle.py` | FEAT-JARVIS-004, -005 | **UPDATED** — NATS + Graphiti startup; register + heartbeat; drain + deregister; start notification subscriber |
| `src/jarvis/tools/capabilities.py` | FEAT-JARVIS-004 | **UPDATED** — stub → `NATSKVManifestRegistry` |
| `src/jarvis/tools/dispatch.py` | FEAT-JARVIS-004, -005 | **UPDATED** — `call_specialist` real transport; `queue_build` real JetStream publish |
| `src/jarvis/sessions/manager.py` | FEAT-JARVIS-005 | **UPDATED** — `pending_notifications()` |
| `src/jarvis/cli/main.py` | FEAT-JARVIS-005 | **UPDATED** — render between-prompt notifications |
| `tests/test_fleet_registration.py` | FEAT-JARVIS-004 | **NEW** |
| `tests/test_capabilities_real.py` | FEAT-JARVIS-004 | **NEW** |
| `tests/test_dispatch_call_specialist.py` | FEAT-JARVIS-004 | **UPDATED** — real transport integration tests |
| `tests/test_dispatch_queue_build.py` | FEAT-JARVIS-005 | **UPDATED** — real JetStream publish |
| `tests/test_forge_notifications.py` | FEAT-JARVIS-005 | **NEW** |
| `tests/test_routing_history_writes.py` | FEAT-JARVIS-004, -005 | **NEW** — both dispatch + queue-build paths |
| `tests/test_graphiti_unavailable.py` | FEAT-JARVIS-004 | **NEW** |
| `tests/test_nats_unavailable.py` | FEAT-JARVIS-004 | **NEW** |
| `tests/test_contract_nats_core.py` | FEAT-JARVIS-004, -005 | **NEW** or **UPDATED** |
| `tests/test_end_to_end_forge_roundtrip.py` | FEAT-JARVIS-005 | **NEW** — soft-prereq end-to-end |
| `docs/design/FEAT-JARVIS-004/design.md` | FEAT-JARVIS-004 | **NEW** |
| `docs/design/FEAT-JARVIS-005/design.md` | FEAT-JARVIS-005 | **NEW** |
| `features/feat-jarvis-004-*/...` | FEAT-JARVIS-004 | **NEW** |
| `features/feat-jarvis-005-*/...` | FEAT-JARVIS-005 | **NEW** |
| `features/feat-jarvis-internal-001-*/...` | FEAT-JARVIS-INTERNAL-001 | **NEW** — Rich's chosen candidate, written before Step 14 |
| `tasks/FEAT-JARVIS-004-*.md` | FEAT-JARVIS-004 | **NEW** |
| `tasks/FEAT-JARVIS-005-*.md` | FEAT-JARVIS-005 | **NEW** |
| `tasks/FEAT-JARVIS-INTERNAL-001-*.md` | FEAT-JARVIS-INTERNAL-001 | **NEW** — produced by Step 13 |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/`.

---

## Do-Not-Change

1. **Fleet v3 D40–D46, ADR-J-P1..P10, ADR-FLEET-001, ADR-SP-014 Pattern A, ADR-SP-016 singular topics, ADR-SP-017 retention.** Phase 3 is first real consumer of P4 (`fleet.register`), P6 (trace-richness), and SP-014 Pattern A.
2. **Phase 1 + Phase 2 outputs.** Tool docstrings, `CapabilityDescriptor`, `SpecialistResult`, `QueueBuildAck`, subagent descriptions, supervisor prompt sections. Phase 3 extends transports, does not change surfaces.
3. **`nats-core` Pydantic models.** `CommandPayload`, `ResultPayload`, `BuildQueuedPayload`, `AgentManifest`, `NotificationPayload`. Jarvis consumes and emits verbatim.
4. **Singular topic convention.** `agents.command.*`, `agents.result.*`, `pipeline.build-queued.*`, `pipeline.stage-complete.*`, `fleet.register`, `jarvis.notification.*`.
5. **ADR-FLEET-001 schema authoritative.** Once Phase 3 starts writing, additions are append-only via ADR-FLEET-00X. No overwrites of existing fields.
6. **No `jarvis.learning` reader.** Writes only. Deferred to v1.5 (FEAT-JARVIS-008).
7. **No new adapters.** CLI only. Telegram is Phase 4.
8. **Fallback behaviours are structural.** Graphiti-unavailable → WARN + continue. NATS-unavailable → structured error, not crash. These are design invariants; tests assert them.
9. **`quick_local` fallback health signal still stubbed.** Real signal is v1.5.
10. **Scope-preserving rules from conversation starter §2.** No new agent repos; no fleet-decision changes mid-build.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| `nats-infrastructure` on GB10 not running when Step 14 starts | Steps 7–13 use in-process NATS test server — full Phase 3 build + integration is GB10-independent. Only Step 14 end-to-end test requires GB10. If GB10 not ready, defer Step 14; rest of Phase 3 still closes. |
| `NATSKVManifestRegistry` cache behaviour differs from Forge's production usage | Use Forge's existing test fixtures if exportable; otherwise contract test the cache-plus-watch behaviour against the same `nats-core` primitives Forge uses. |
| `ADR-FLEET-001` schema field ambiguity when implementing | `/system-design FEAT-JARVIS-004` is where the full Pydantic shape lands (resolving JA1). If ambiguity remains post-design, raise via ADR-FLEET-002 before writing begins — retrofits are expensive. |
| Graphiti write latency hurts dispatch latency | Fire-and-forget async writes. Dispatch returns to supervisor without waiting. Write failures log WARN, not ERROR. |
| `call_specialist` timeout too short: legitimate specialists time out | ADR-pinned default from `/system-design`; test coverage for 30s, 60s, 120s boundaries; configurable per-invocation via context dict. |
| Retry-with-redirect causes loops if two specialists both time out | Max retry count (e.g. 2 total attempts); loop guard via visited-set on `agent_id`. |
| Forge end-to-end test fails because Rich-chosen feature is too ambitious | Prefer candidate (a) docstring polish — smallest, safest, most-obviously-succeeds first real run. Reserve (b) or (c) for a follow-up end-to-end test. |
| `pipeline.stage-complete.*` subscription leaks across sessions / users | Correlation-ID filter is mandatory; test covers "stage-complete for another correlation_id is ignored". |
| Mid-REPL notification rendering disrupts input | Render between prompts only; never interrupt an in-progress typing action. CLI test covers this. |
| JetStream durability / replay on restart surprises | Follow Forge ADR-SP-017 retention + ack semantics verbatim. Ack-on-consume + max_ack_pending=1 per Forge pattern. |

---

## Expected Timeline

Building on Phase 2's timeline (Phase 2: 25–29 April 2026):

| Day | Activity | Output |
|-----|----------|--------|
| 1 (30 Apr) | Step 1 — `/system-design FEAT-JARVIS-004`. Step 3 — `/feature-spec FEAT-JARVIS-004`. | Design doc + Gherkin scenarios for FEAT-JARVIS-004. |
| 2 (1 May) | Step 5 — `/feature-plan FEAT-JARVIS-004`. Step 7 — begin AutoBuild FEAT-JARVIS-004 (NATS client + fleet registration + routing_history schema). | Task breakdown + first commits. |
| 3 (2 May) | Step 7 cont — complete AutoBuild FEAT-JARVIS-004 (capabilities integration + real `call_specialist` + fallback tests + contract tests). Step 8 — `/task-review`. Step 11 — regression check. | FEAT-JARVIS-004 closed. |
| 4 (3 May) | Step 2 — `/system-design FEAT-JARVIS-005`. Step 4 — `/feature-spec FEAT-JARVIS-005`. Step 6 — `/feature-plan FEAT-JARVIS-005`. | Design + spec + plan. |
| 5 (4 May) | Step 9 — AutoBuild FEAT-JARVIS-005 (real `queue_build` + forge notifications + CLI rendering). Step 10 — `/task-review`. | FEAT-JARVIS-005 code-complete. |
| 6 (5 May) | Step 11 — full regression. Step 12 — integration-server check. Step 13 — Rich picks FEAT-JARVIS-INTERNAL-*** candidate + `/feature-spec`/`plan` it. | Integration tests green; internal feature ready for Step 14. |
| 7 (6 May) | Step 14 — end-to-end test with real Forge. | Evidence artefact: chat transcript + Graphiti trace dump. Phase 3 closed. |

**Target: Phase 3 complete within 6–7 working days (30 April – 6 May 2026).** Higher complexity than Phase 2 justifies the larger budget — real NATS, real Graphiti, first ADR-FLEET-001 writes, cross-process end-to-end test.

---

## After Phase 3: What Comes Next

| Priority | Phase | Content |
|----------|-------|---------|
| **Next** | Phase 4 | FEAT-JARVIS-006 (Telegram adapter — Telegram-only per Q10.3; `nats-asyncio-service` pattern; `jarvis.command.telegram` / `notifications.telegram`). FEAT-JARVIS-007 (skills: `morning-briefing`, `talk-prep`, `project-status` — real use of Memory Store, `talk-prep` reserves Pattern C ambient slot for v1.5). |
| **v1.5** | Phase 5 | FEAT-JARVIS-008 (Learning Flywheel). Now has real `jarvis_routing_history` data from Phase 3 to read. `jarvis.learning` module + `CalibrationAdjustment` entities + Rich-in-the-loop CLI. |
| **v1.5** | — | FEAT-JARVIS-009 (CLI + Dashboard adapters). FEAT-JARVIS-010 (`talk-prep` Pattern C ambient nudges targeting DDD Southwest prep — first real Pattern C graduation). FEAT-JARVIS-011 (`jarvis purge-traces` CLI, GDPR-clean per ADR-FLEET-001). |

---

*Phase 3 build plan: 20 April 2026*
*Predecessor: Phase 2 (FEAT-JARVIS-002 + FEAT-JARVIS-003 — dispatch tools + async subagents with stubbed NATS transports).*
*Input to: `/system-design FEAT-JARVIS-004`, `/system-design FEAT-JARVIS-005`.*
*"The fleet contract is symmetric."*
