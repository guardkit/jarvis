# Phase 4 Build Plan — Surfaces: Telegram Adapter + Skills & Memory Store Activation

## For: Shipping Jarvis v1 — Telegram reaches Rich on his phone, three launch skills give the supervisor a named vocabulary of higher-order tasks, and the Memory Store wired in Phase 1 finally does cross-session work. Phase 4 closes the v1 ship.
## Date: 20 April 2026
## Status: Blocked on Phase 3 completion (FEAT-JARVIS-004 + FEAT-JARVIS-005 merged, end-to-end test with real Forge green, first `jarvis_routing_history` writes landed). Ready for `/system-design FEAT-JARVIS-006` once Phase 3 closes.
## Repo: `guardkit/jarvis` (adapters in `jarvis/adapters/telegram/` as a sibling project)
## Cross-repo touch: `nats-core` gains two new payload shapes + topic constants (additive, backward-compatible, minor version bump).

---

## Status Log

| Date | Step | Outcome |
|------|------|---------|
| 2026-04-20 | `phase4-surfaces-scope.md` written | Scope doc — input to `/system-design FEAT-JARVIS-006` and `/system-design FEAT-JARVIS-007`. |
| 2026-04-20 | `phase4-build-plan.md` written | This document. |
| *pending* | Phase 3 close | FEAT-JARVIS-004 + FEAT-JARVIS-005 merged, end-to-end with real Forge green, first routing-history writes in Graphiti. |
| *pending* | `nats-core` PR for new payloads | Minor version bump; `JarvisCommandPayload`, `JarvisNotificationPayload`, new topic constants. |
| *pending* | Telegram bot token provisioned | Rich creates bot via @BotFather; token stored in `.env`; Rich's `chat_id` added to allowlist. |
| *pending* | `/system-design FEAT-JARVIS-006` | Design doc. |
| *pending* | `/system-design FEAT-JARVIS-007` | Design doc. |
| *pending* | `/feature-spec FEAT-JARVIS-006` | Gherkin scenarios. |
| *pending* | `/feature-spec FEAT-JARVIS-007` | Gherkin scenarios. |
| *pending* | `/feature-plan FEAT-JARVIS-006` | Task breakdown. |
| *pending* | `/feature-plan FEAT-JARVIS-007` | Task breakdown. |

---

## What Phase 4 IS

The phase that ships Jarvis v1. Two features:

- **FEAT-JARVIS-006** — Telegram adapter. Separate `nats-asyncio-service`-patterned process living in `adapters/telegram/`. Publishes incoming Telegram messages to `jarvis.command.telegram`; consumes outbound messages from `jarvis.notification.telegram` + `jarvis.notification.forge-stage-complete.*` (bridged). Adapter never imports `src/jarvis/` — pure NATS boundary. Allowlist enforcement (Rich's `chat_id` only). Supervisor side gains `adapter_ingress.py` that routes inbound adapter commands into fresh or ongoing sessions with adapter-tagged metadata so outbound notifications route back to the correct surface.
- **FEAT-JARVIS-007** — Skills + Memory Store activation. Three launch skills (`morning-briefing`, `talk-prep`, `project-status`), each a named composable unit reachable via natural-language dispatch (supervisor recognises intent signatures) or `/skill <n>` command. Skills compose tools + subagents from Phases 2–3 and use the Memory Store for cross-session state. `talk-prep` includes a clearly-marked Pattern C slot (no-op stub) reserving the v1.5 FEAT-JARVIS-010 extension point for DDD Southwest prep nudges.

After Phase 4, Rich can send "morning briefing" to the Telegram bot from his phone, get a composed reply drawing on calendar stub + project status + recent routing history + Memory Store continuity. That's the Jarvis v1 ship criterion.

## What Phase 4 IS NOT

- Not real calendar integration. `get_calendar_events` stays stubbed from Phase 2; v1.5 wires it.
- Not the learning flywheel (`jarvis.learning` reader). Skills write trace records; reader is FEAT-JARVIS-008 (v1.5).
- Not Pattern C ambient nudges. Only the slot reservation in `talk_prep.py`. Active ambient behaviour is FEAT-JARVIS-010 (v1.5).
- Not the Dashboard or Reachy adapters. FEAT-JARVIS-009 (v1.5).
- Not a persistent Memory Store backend. In-memory for v1. Persistent backend is v1.5.
- Not sensitive-action gating on Telegram. Any `queue_build` from Telegram queues the same as from CLI; Forge-side guardrails apply. Telegram-specific sensitive-action gating is a v1.5 hardening.
- Not GDPR trace purge (`jarvis purge-traces`). FEAT-JARVIS-011 (v1.1).

## Success Criteria

1. All Phase 1 + Phase 2 + Phase 3 tests still pass (zero regressions).
2. Telegram adapter process runs against a real bot token + connects to NATS on GB10.
3. Round-trip: Rich sends a Telegram message → Jarvis reply arrives in Telegram with session continuity across multiple messages in the same chat.
4. Queuing a build from Telegram surfaces stage-complete notifications back to Telegram. Queuing from CLI surfaces to CLI. Cross-contamination does not occur.
5. Allowlist enforcement: non-allowlisted `chat_id` → silent drop.
6. Three launch skills registered at supervisor startup; intent signatures + `/skill` aliases work.
7. Supervisor with canned mocked-LLM prompts routes to `invoke_skill(...)` with the right skill name for intent-matching phrases.
8. Memory Store round-trip: skills read + write expected keys; cross-session recall within the in-memory backend's lifetime.
9. `talk-prep` Pattern C slot present, clearly marked, is a no-op — proves the slot is reserved without active behaviour.
10. `jarvis_routing_history` trace-rich writes land for every skill invocation, with `skill_name` extension + edges to inner tool/subagent records.
11. End-to-end Phase 4 close: Rich sends "morning briefing" via Telegram; reply arrives composing calendar stub + project status + recent routing-history + Memory Store continuity; Graphiti shows the skill trace + inner dispatches.
12. Ruff + mypy clean on all new modules (both `src/jarvis/` and `adapters/telegram/`).

---

## Phase 3 Results (Context)

Expected at Phase 4 start:

- NATS client + fleet registration + `NATSKVManifestRegistry`-backed catalogue + real `dispatch_by_capability` round-trip (renamed from `call_specialist` per [FEAT-JARVIS-002 DDR-005](../../design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md))
- Real `queue_build` publish to JetStream + `pipeline.stage-complete.*` subscription + CLI rendering of between-prompt notifications
- `JarvisRoutingHistoryEntry` Pydantic shape + trace-rich writes for specialist dispatch + build-queue dispatch (schema authoritative per ADR-FLEET-001)
- Graphiti-unavailable + NATS-unavailable fallback behaviours
- Jarvis registered on `fleet.register`, discoverable by other agents
- End-to-end test with real Forge passed; evidence artefact recorded

**Gaps Phase 4 closes:**

| Gap | Impact | Source |
|-----|--------|--------|
| CLI is the only adapter | Jarvis's attended value proposition is laptop-bound | Q10.3; `jarvis-vision.md` §9 |
| Supervisor has no named higher-order vocabulary | Every higher-order task re-derived from scratch; no composition by name | ADR-J-P3; conversation starter §2 |
| Memory Store wired but unused | Cross-session continuity absent; "yesterday" is just a word | Phase 1 memory-store hook; fleet v3 D42 |
| No Pattern C ambient slot for FEAT-JARVIS-010 (v1.5) | v1.5 would need to retrofit the extension point | Q10.5; targeting DDD Southwest 16 May |

---

## Feature Summary

| # | Feature | Depends On | Est. Complexity | Priority |
|---|---------|-----------|-----------------|----------|
| FEAT-JARVIS-006 | Telegram Adapter | FEAT-JARVIS-001 (sessions), FEAT-JARVIS-004 (NATS+fleet), FEAT-JARVIS-005 (notification routing) | Medium (new process + cross-repo `nats-core` update + Telegram integration) | **High** (unlocks ambient posture) |
| FEAT-JARVIS-007 | Skills & Memory Store Activation | FEAT-JARVIS-001 (Memory Store), FEAT-JARVIS-002 (tools), FEAT-JARVIS-003 (subagents), FEAT-JARVIS-004 (Graphiti + routing history) | Medium | **High** (unlocks named composition; v1 ship criterion) |

**Dependency graph:**

```
FEAT-JARVIS-004, -005 (Phase 3 — merged)
         │
         ├──→ FEAT-JARVIS-006 (Telegram adapter — bridges 004+005 plumbing to a new surface)
         │
         └──→ FEAT-JARVIS-007 (Skills — composes 002+003 tools/subagents, uses 004 Graphiti)
```

FEAT-JARVIS-006 and FEAT-JARVIS-007 are independent on the dependency graph — each depends only on previous phases, not on each other. Both could be built in parallel, but **sequential build: 006 first, then 007** is preferred because: (a) `/skill <n>` command syntax from FEAT-JARVIS-007 needs to work from both CLI and Telegram, so having the Telegram adapter in place lets the adapter-ingress routing test cover the skill-via-Telegram path in one go; (b) the end-to-end Phase 4 close test ("send 'morning briefing' via Telegram") naturally comes last and needs both features present. Sequential also keeps AutoBuild contexts focused.

---

## FEAT-JARVIS-006: Telegram Adapter

**Purpose:** Bridge Telegram to Jarvis via the `nats-asyncio-service` pattern. Separate process, NATS-only communication, allowlisted.

### Change 1: `nats-core` payload additions (cross-repo)

**Files (NEW in `nats-core`):**

- `../nats-core/src/nats_core/payloads/jarvis_command.py` — `JarvisCommandPayload` Pydantic model.
- `../nats-core/src/nats_core/payloads/jarvis_notification.py` — `JarvisNotificationPayload` Pydantic model.

**File (UPDATED in `nats-core`):**

- `../nats-core/src/nats_core/topics.py` — new constants: `JARVIS_COMMAND_CLI`, `JARVIS_COMMAND_TELEGRAM`, `JARVIS_NOTIFICATION_CLI`, `JARVIS_NOTIFICATION_TELEGRAM`.

`nats-core` bumps to next minor version. Jarvis + adapter both pin to the new version. Additive, backward-compatible.

### Change 2: Telegram adapter process (`adapters/telegram/`)

**Files (NEW):**

- `adapters/telegram/pyproject.toml` — separate Python project. Deps: `nats-py`, `nats-core` (new version), Telegram library (ADR-pinned — `python-telegram-bot` or `aiogram`), `pydantic-settings`, `aiosqlite` (for session-map persistence).
- `adapters/telegram/src/jarvis_telegram_adapter/__init__.py`
- `adapters/telegram/src/jarvis_telegram_adapter/main.py` — entry point. `nats-asyncio-service`-patterned.
- `adapters/telegram/src/jarvis_telegram_adapter/inbound.py` — Telegram → NATS: receive message → look up or create `session_id` for the `chat_id` → build `JarvisCommandPayload` → publish to `jarvis.command.telegram`.
- `adapters/telegram/src/jarvis_telegram_adapter/outbound.py` — NATS → Telegram: subscribe to `jarvis.notification.telegram` + `jarvis.notification.forge-stage-complete.*` → filter by `session_id` against local `session_id → chat_id` map → send via Telegram API.
- `adapters/telegram/src/jarvis_telegram_adapter/session_map.py` — SQLite-backed `chat_id ↔ session_id` mapping with lifecycle.
- `adapters/telegram/src/jarvis_telegram_adapter/config.py` — `TelegramAdapterConfig` pydantic settings.
- `adapters/telegram/README.md` — run instructions.
- `adapters/telegram/tests/test_inbound.py`, `test_outbound.py`, `test_session_map.py`, `test_allowlist.py`, `test_config.py` — adapter-local tests.

The adapter registers its own `AgentManifest` on `fleet.register` so it's discoverable. Manifest: `agent_id="jarvis-telegram-adapter"`, role `adapter`, capabilities include `telegram_ingress`, `telegram_egress`.

### Change 3: Supervisor-side adapter ingress (`src/jarvis/infrastructure/adapter_ingress.py`)

**Files (NEW):**

- `src/jarvis/infrastructure/adapter_ingress.py`:
  - Subscribes to `jarvis.command.*` (wildcards for all adapter variants).
  - On receipt: `SessionManager.get_or_create_session(adapter=payload.adapter, session_id=payload.session_id)`.
  - Feeds `payload.user_message_text` into supervisor graph as next user turn.
  - Streaming response → zero or more `jarvis.notification.{adapter}` publishes tagged with `session_id`.

### Change 4: Session manager adapter awareness (`src/jarvis/sessions/manager.py`)

**File:** `src/jarvis/sessions/manager.py` (UPDATED — Phase 1 created, Phase 3 added `pending_notifications`)

- `Session` gains `adapter` field (`"cli" | "telegram"`).
- `get_or_create_session(adapter, session_id)` either resumes or creates a session tagged with the adapter.
- `pending_notifications` extended: for `cli` sessions, returns queue as before; for `telegram` sessions, always returns empty (Telegram notifications are pushed directly via NATS, not polled via SessionManager).
- `recent_sessions_summary()` — new for FEAT-JARVIS-007 too; returns N most recent session metadata (id, adapter, last_active_at, skills_invoked).

### Change 5: Notification router adapter-tagging (`src/jarvis/infrastructure/forge_notifications.py`)

**File:** `src/jarvis/infrastructure/forge_notifications.py` (UPDATED — Phase 3 created)

- `jarvis.notification.forge-stage-complete.{correlation_id}` bridge extended: when bridging, look up the originating session's adapter and *also* publish to `jarvis.notification.{adapter}` so the adapter's outbound loop picks it up.
- For `cli` sessions: existing `SessionManager.pending_notifications` behaviour preserved (CLI adapter is in-process).
- For `telegram` sessions: stage-complete events land on `jarvis.notification.telegram` with correct `session_id` tag.

### Change 6: Lifecycle integration (`src/jarvis/infrastructure/lifecycle.py`)

**File:** `src/jarvis/infrastructure/lifecycle.py` (UPDATED — Phase 3 updated)

- Startup: after NATS connect + Graphiti connect + fleet register, also start `adapter_ingress` subscriber as a background task.
- Shutdown: cancel `adapter_ingress` task as part of the ordered shutdown.

### Change 7: Tests

**Files (NEW):**

- `tests/test_adapter_ingress.py` — subscriber receives `JarvisCommandPayload`, session resolution works, supervisor invocation happens, outbound notification published with correct adapter tag.
- `tests/test_telegram_roundtrip_integration.py` — in-process NATS + Telegram-adapter-stub + Jarvis-with-mocked-LLM. Simulated Telegram message → command payload → supervisor → notification payload → adapter stub "delivers".
- `tests/test_cross_adapter_notification_routing.py` — queue a build from `telegram` session, assert stage-complete routes to `jarvis.notification.telegram`; queue from `cli`, assert it stays on CLI path. No cross-contamination.
- `tests/test_contract_nats_core_jarvis.py` — contract test against `JarvisCommandPayload`/`JarvisNotificationPayload` schemas in the new `nats-core` version.
- Adapter-local: `adapters/telegram/tests/test_allowlist.py` — non-allowlisted `chat_id` dropped silently.
- Adapter-local: `adapters/telegram/tests/test_session_map.py` — SQLite-backed persistence of `chat_id ↔ session_id`.

### Invariants

- Adapter never imports from `src/jarvis/`.
- All adapter↔supervisor communication via `nats-core` payloads.
- Allowlist enforcement is strict; no fallback, no logging of dropped message content at INFO level (DEBUG only).
- Singular topic convention: `jarvis.command.telegram` (not `.telegrams`).
- Fleet v3 §10 (adapters are non-credulous) honoured.

---

## FEAT-JARVIS-007: Skills & Memory Store Activation

**Purpose:** Give the supervisor a named, composable vocabulary of higher-order tasks; activate the Memory Store for cross-session state; reserve Pattern C extension point in `talk-prep`.

### Change 1: Skill framework (`src/jarvis/skills/base.py`)

**Files (NEW):**

- `src/jarvis/skills/__init__.py`
- `src/jarvis/skills/base.py`:
  - `SkillDescriptor` Pydantic model: `name`, `description`, `intent_signatures` (list[str]), `command_alias`, `required_tools`, `required_subagents`, `memory_store_keys`.
  - `SkillResult` Pydantic model: `skill_name`, `skill_run_id`, `outputs` (dict), `tool_dispatches` (list of references), `subagent_dispatches` (list of references), `memory_updates` (dict).
  - `Skill` abstract base: `descriptor` property, `run(session, supervisor, inputs) -> SkillResult` async method.
  - `SkillRegistry`: `register(skill)`, `get(name)`, `find_by_intent(phrase) -> Skill | None`, `load_launch_skills()`.

### Change 2: Three launch skills

**Files (NEW):**

- `src/jarvis/skills/morning_briefing.py` — `MorningBriefingSkill`. Intent signatures include "morning briefing", "what's on today", "brief me", "catch me up on today". Composes `get_calendar_events` + `list_available_capabilities` + `SessionManager.recent_sessions_summary` + Graphiti read of yesterday's routing history. Memory: writes `last_morning_briefing_{date, highlights}`; reads prior `highlights` for continuity.

- `src/jarvis/skills/talk_prep.py` — `TalkPrepSkill`. Intent signatures include "talk prep", "DDD Southwest prep", "prep the talk". Composes Graphiti read of talk-project-tagged entries + `jarvis-reasoner` with `role=researcher` for requested research + `role=planner` for summarisation (per [FEAT-JARVIS-003 DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md) / [DDR-011](../../design/FEAT-JARVIS-003/decisions/DDR-011-role-enum-closed-v1.md); the scope-doc `long_research` + `quick_local` subagents are retired). Memory: writes `talk_prep_sessions` (append), `talk_prep_open_questions`, `talk_prep_rehearsal_count`; reads all of these. **Pattern C slot reservation section** clearly marked with `# --- FEAT-JARVIS-010 Pattern C ambient nudges land here (v1.5) ---` and no-op `async def maybe_emit_ambient_nudge(session, memory_store): return None`.

- `src/jarvis/skills/project_status.py` — `ProjectStatusSkill`. Intent signatures include "project status", "how is X doing", "status update on Y". Composes Graphiti read scoped to project + optional `dispatch_by_capability(tool_name="<architect-capability>", ...)` (per [FEAT-JARVIS-002 DDR-005](../../design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md); renamed from `call_specialist`) + `jarvis-reasoner` with `role=planner` for synthesis (per [FEAT-JARVIS-003 DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md)). Memory: reads `active_projects`, `project_last_status_query`; writes updates.

### Change 3: `invoke_skill` tool (`src/jarvis/tools/skills.py`)

**Files (NEW):**

- `src/jarvis/tools/skills.py`: `invoke_skill(name, inputs={}) -> SkillResult` — looks up skill in registry, runs, returns result. Registered as a tool on the supervisor. Docstring teaches the supervisor when to prefer skills over re-derivation.

### Change 4: Supervisor integration (`src/jarvis/agents/supervisor.py`, `src/jarvis/prompts/supervisor_prompt.py`)

**File:** `src/jarvis/agents/supervisor.py` (UPDATED)

- Load `SkillRegistry.load_launch_skills()` at factory time.
- Register `invoke_skill` tool.

**File:** `src/jarvis/prompts/supervisor_prompt.py` (UPDATED)

- Add skills section: enumerates the three launch skills + their intent signatures; instructs supervisor to recognise skill-intent phrases and dispatch via `invoke_skill(...)` rather than re-deriving.
- Phase 1 + Phase 2 + Phase 3 prompt content preserved verbatim.

### Change 5: CLI `/skill` command (`src/jarvis/cli/main.py`)

**File:** `src/jarvis/cli/main.py` (UPDATED — Phase 1, 3 updated)

- Parse `/skill <n> [json-inputs]` before supervisor dispatch; bypass reasoning and call `SkillRegistry.get(name).run(...)` directly.
- Print `SkillResult.outputs` as markdown.
- Same parsing logic also applied in `adapter_ingress.py` for Telegram messages starting with `/skill`.

### Change 6: Memory Store helpers (`src/jarvis/sessions/memory_store.py`)

**File:** `src/jarvis/sessions/memory_store.py` (UPDATED — Phase 1 created)

- Typed `MemoryKey` wrapper with namespace prefixing (`morning_briefing.*`, `talk_prep.*`, `project_status.*`).
- Per-skill accessor helpers so skills don't hand-spell keys.
- `SessionManager.recent_sessions_summary()` helper that reads recent-session metadata from the Memory Store.

### Change 7: Routing-history skill extension (`src/jarvis/infrastructure/routing_history.py`)

**File:** `src/jarvis/infrastructure/routing_history.py` (UPDATED — Phase 3 created)

- New ADR: `ADR-FLEET-00X-skill-name-extension.md` — append-only extension to `jarvis_routing_history` adding `skill_name` (optional) to the Jarvis-specific extensions.
- `write_skill_invocation(entry)` writes outer skill record; inner tool/subagent records get edges referencing the outer record's `decision_id`.

### Change 8: Tests

**Files (NEW):**

- `tests/test_skill_registry.py` — registry loads three launch skills, intent matching, command-alias lookup.
- `tests/test_skill_morning_briefing.py` — skill composes expected tool + subagent dispatches with mocked LLM; Memory Store mutations match expected.
- `tests/test_skill_talk_prep.py` — same shape for talk-prep; **includes Pattern C slot test**: `from jarvis.skills.talk_prep import maybe_emit_ambient_nudge; assert await maybe_emit_ambient_nudge(session, memory) is None`.
- `tests/test_skill_project_status.py` — same shape for project-status.
- `tests/test_memory_store_cross_session.py` — end session, new session with same user, state read by skills.
- `tests/test_invoke_skill_tool.py` — supervisor routes intent-phrase prompt to `invoke_skill(name=...)` with mocked LLM returning deterministic tool call.
- `tests/test_skill_dispatch_via_command.py` — `/skill morning-briefing` bypasses supervisor reasoning, hits registry directly.
- `tests/test_skill_trace_writes.py` — skill invocation writes outer record + edges to inner records in Graphiti stub; `skill_name` extension populated.

### Invariants

- Skills are distinct from tools. The supervisor reasons over tools; skills are named compositions. Skills *use* tools and subagents.
- Skills chain existing Phase 2–3 infrastructure — no parallel universe.
- `talk-prep` Pattern C slot is a no-op in v1; only the contract (function signature) is committed.
- Memory Store keys are namespaced per skill; no collisions.
- `ADR-FLEET-001` schema extensions are additive via `ADR-FLEET-00X` — no overwrites.

---

## GuardKit Command Sequence

### Step 1: `nats-core` payload additions (cross-repo)

Done first, before any Jarvis-side design work, because both FEAT-JARVIS-006 and FEAT-JARVIS-007 (the latter indirectly via adapter-ingress code paths) depend on the new payloads.

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/nats-core

# Via the standard nats-core GuardKit pipeline
/feature-spec "JarvisCommandPayload and JarvisNotificationPayload shapes + jarvis.command.{cli,telegram}, jarvis.notification.{cli,telegram} topic constants — additive, backward-compatible, minor version bump" \
  --context docs/design/specs/nats-core-system-spec.md \
  --context src/nats_core/topics.py \
  --context src/nats_core/payloads/ \
  --context ../jarvis/docs/research/ideas/phase4-surfaces-scope.md \
  --context ../jarvis/docs/research/ideas/phase4-build-plan.md

/feature-plan "JarvisCommandPayload + JarvisNotificationPayload"
# AutoBuild + /task-review on nats-core side
# Bump nats-core version; publish
```

### Step 2: /system-design FEAT-JARVIS-006

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis

/system-design FEAT-JARVIS-006 \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/design/FEAT-JARVIS-005/design.md \
  --context src/jarvis/sessions/manager.py \
  --context src/jarvis/infrastructure/forge_notifications.py \
  --context src/jarvis/infrastructure/nats_client.py \
  --context src/jarvis/infrastructure/lifecycle.py \
  --context ../nats-core/src/nats_core/payloads/jarvis_command.py \
  --context ../nats-core/src/nats_core/payloads/jarvis_notification.py \
  --context ../nats-core/src/nats_core/topics.py \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context .guardkit/context-manifest.yaml
```

Expected output: `docs/design/FEAT-JARVIS-006/design.md` — Telegram library choice, transport mode, session-map persistence, CLI-adapter-refactor scope, allowlist enforcement details.

### Step 3: /system-design FEAT-JARVIS-007

```bash
/system-design FEAT-JARVIS-007 \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/design/FEAT-JARVIS-002/design.md \
  --context docs/design/FEAT-JARVIS-003/design.md \
  --context docs/design/FEAT-JARVIS-004/design.md \
  --context docs/design/FEAT-JARVIS-006/design.md \
  --context src/jarvis/agents/supervisor.py \
  --context src/jarvis/prompts/supervisor_prompt.py \
  --context src/jarvis/tools/general.py \
  --context src/jarvis/tools/dispatch.py \
  --context src/jarvis/sessions/manager.py \
  --context src/jarvis/sessions/memory_store.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context .guardkit/context-manifest.yaml
```

Expected output: `docs/design/FEAT-JARVIS-007/design.md` — `Skill` base shape, `SkillRegistry` behaviour, three launch-skill designs with Memory Store key schemas, `invoke_skill` tool, supervisor prompt additions, Pattern C slot API signature pinned.

### Step 4: /feature-spec FEAT-JARVIS-006

```bash
/feature-spec "Telegram Adapter: nats-asyncio-service-patterned process bridging Telegram Bot API to jarvis.command.telegram / jarvis.notification.telegram; allowlisted chat IDs; SQLite-backed session-map; adapter never imports src/jarvis; supervisor-side adapter_ingress subscribes to jarvis.command.* and routes into SessionManager" \
  --context docs/design/FEAT-JARVIS-006/design.md \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md \
  --context ../nats-core/src/nats_core/payloads/jarvis_command.py \
  --context ../nats-core/src/nats_core/payloads/jarvis_notification.py \
  --context src/jarvis/sessions/manager.py \
  --context .guardkit/context-manifest.yaml
```

### Step 5: /feature-spec FEAT-JARVIS-007

```bash
/feature-spec "Skills and Memory Store Activation: Skill base + SkillRegistry + three launch skills (morning-briefing, talk-prep, project-status) that compose tools and subagents from Phases 2-3 and use Memory Store for cross-session state; invoke_skill tool; /skill command syntax; talk-prep Pattern C slot reserved (no-op stub for v1.5 FEAT-JARVIS-010); trace-rich writes per ADR-FLEET-001 with skill_name extension" \
  --context docs/design/FEAT-JARVIS-007/design.md \
  --context docs/design/FEAT-JARVIS-006/design.md \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context src/jarvis/sessions/memory_store.py \
  --context src/jarvis/infrastructure/routing_history.py \
  --context .guardkit/context-manifest.yaml
```

### Step 6: /feature-plan FEAT-JARVIS-006

```bash
/feature-plan "Telegram Adapter" \
  --context features/feat-jarvis-006-*/feat-jarvis-006-*_summary.md \
  --context features/feat-jarvis-006-*/feat-jarvis-006-*.feature \
  --context features/feat-jarvis-006-*/feat-jarvis-006-*_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-006/design.md \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md \
  --context .guardkit/context-manifest.yaml
```

### Step 7: /feature-plan FEAT-JARVIS-007

```bash
/feature-plan "Skills and Memory Store Activation" \
  --context features/feat-jarvis-007-*/feat-jarvis-007-*_summary.md \
  --context features/feat-jarvis-007-*/feat-jarvis-007-*.feature \
  --context features/feat-jarvis-007-*/feat-jarvis-007-*_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-007/design.md \
  --context docs/design/FEAT-JARVIS-006/design.md \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md \
  --context .guardkit/context-manifest.yaml
```

### Step 8: AutoBuild FEAT-JARVIS-006

Suggested commit order:

1. `adapters/telegram/pyproject.toml` + config module.
2. Session-map module + tests.
3. Inbound module + tests.
4. Outbound module + tests.
5. Allowlist enforcement tests.
6. Adapter `main.py` + manifest registration.
7. Supervisor-side `adapter_ingress.py` + tests.
8. `SessionManager` adapter-awareness updates + tests.
9. `forge_notifications.py` adapter-tagging update + cross-adapter routing test.
10. `lifecycle.py` adapter-ingress integration.
11. Cross-process integration test (`test_telegram_roundtrip_integration.py`).

### Step 9: /task-review FEAT-JARVIS-006

```bash
/task-review FEAT-JARVIS-006 \
  --context tasks/FEAT-JARVIS-006-*.md \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md
```

### Step 10: AutoBuild FEAT-JARVIS-007

Suggested commit order:

1. `skills/base.py` (`Skill`, `SkillDescriptor`, `SkillResult`, `SkillRegistry`) + unit tests.
2. Memory Store helpers (`MemoryKey`, per-skill accessors) + tests.
3. `morning_briefing.py` + its test.
4. `talk_prep.py` (including clearly-marked Pattern C slot no-op) + its test + Pattern C slot test.
5. `project_status.py` + its test.
6. `SessionManager.recent_sessions_summary()` + test.
7. `tools/skills.py` (`invoke_skill`) + test.
8. Supervisor factory + prompt updates.
9. `/skill` command parsing in CLI + `adapter_ingress.py`.
10. `ADR-FLEET-00X-skill-name-extension.md`.
11. `routing_history.py` update (`write_skill_invocation`, edge writes).
12. `test_memory_store_cross_session.py`, `test_invoke_skill_tool.py`, `test_skill_dispatch_via_command.py`, `test_skill_trace_writes.py`.

### Step 11: /task-review FEAT-JARVIS-007

```bash
/task-review FEAT-JARVIS-007 \
  --context tasks/FEAT-JARVIS-007-*.md \
  --context docs/research/ideas/phase4-surfaces-scope.md \
  --context docs/research/ideas/phase4-build-plan.md
```

### Step 12: Regression check

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
uv sync
uv run pytest tests/ -v --tb=short --cov=src/jarvis
uv run ruff check src/jarvis/ tests/
uv run mypy src/jarvis/
uv run langgraph dev --no-browser

cd adapters/telegram
uv sync --dev
uv run pytest tests/ -v --tb=short
uv run ruff check src/ tests/
uv run mypy src/
```

### Step 13: Integration check (in-process adapter + in-process NATS)

All integration tests green against in-process servers. Confirms the cross-process shape works without needing GB10 or a real Telegram bot.

### Step 14: Telegram live check (soft-prereq: bot token)

```bash
# Create bot via @BotFather; capture token
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_ALLOWED_CHAT_IDS="<Rich's chat id>"
export JARVIS_NATS_URL="nats://100.x.y.z:4222"  # GB10 NATS
# ... other keys from Phase 3

# Terminal 1: Jarvis supervisor
jarvis chat  # CLI stays open; adapter-ingress runs in background

# Terminal 2: Telegram adapter
cd adapters/telegram
uv run python -m jarvis_telegram_adapter.main

# From Rich's phone:
# Open Telegram → @jarvis-bot → /start
# Send: "hello"
# Expected: supervisor reply in Telegram
# Send: "what's on today"
# Expected: morning-briefing skill composed reply
```

### Step 15: End-to-end Phase 4 close (v1 ship test)

With everything running from Step 14:

```text
Rich sends (from phone): "morning briefing"
Expected:
  - Telegram adapter publishes JarvisCommandPayload to jarvis.command.telegram
  - adapter_ingress resolves/creates session for the chat
  - Supervisor recognises intent → invoke_skill("morning_briefing")
  - Skill composes: get_calendar_events stub + recent_sessions_summary + Graphiti read of yesterday's routing history
  - jarvis-reasoner subagent (role=planner) summarises (per FEAT-JARVIS-003 DDR-010/011)
  - SkillResult returned
  - Supervisor formats as markdown reply
  - JarvisNotificationPayload published to jarvis.notification.telegram
  - Telegram adapter delivers to Rich's chat
  - jarvis_routing_history in Graphiti shows: outer skill record + edges to inner get_calendar_events, recent_sessions_summary, Graphiti-read, subagent dispatches
  - Memory Store: last_morning_briefing_date = today; highlights stored

Rich sends next day: "morning briefing"
Expected:
  - Same flow, but skill reads yesterday's highlights from Memory Store and includes continuity note
```

Record the session + Graphiti trace dump. This is Phase 4's evidence artefact. **Jarvis v1 ships.**

---

## Files That Will Change

| File | Feature | Change Type |
|------|---------|------------|
| `../nats-core/src/nats_core/payloads/jarvis_command.py` | FEAT-JARVIS-006 | **NEW** (cross-repo) |
| `../nats-core/src/nats_core/payloads/jarvis_notification.py` | FEAT-JARVIS-006 | **NEW** (cross-repo) |
| `../nats-core/src/nats_core/topics.py` | FEAT-JARVIS-006 | **UPDATED** (cross-repo) |
| `adapters/telegram/pyproject.toml` | FEAT-JARVIS-006 | **NEW** |
| `adapters/telegram/src/jarvis_telegram_adapter/{__init__,main,inbound,outbound,config,session_map}.py` | FEAT-JARVIS-006 | **NEW** |
| `adapters/telegram/README.md` | FEAT-JARVIS-006 | **NEW** |
| `adapters/telegram/tests/test_*.py` | FEAT-JARVIS-006 | **NEW** |
| `src/jarvis/infrastructure/adapter_ingress.py` | FEAT-JARVIS-006 | **NEW** |
| `src/jarvis/infrastructure/forge_notifications.py` | FEAT-JARVIS-006 | **UPDATED** |
| `src/jarvis/infrastructure/lifecycle.py` | FEAT-JARVIS-006 | **UPDATED** |
| `src/jarvis/sessions/manager.py` | FEAT-JARVIS-006, -007 | **UPDATED** — adapter-awareness + `recent_sessions_summary()` |
| `src/jarvis/sessions/memory_store.py` | FEAT-JARVIS-007 | **UPDATED** — typed `MemoryKey`, per-skill accessors |
| `src/jarvis/skills/{__init__,base,morning_briefing,talk_prep,project_status}.py` | FEAT-JARVIS-007 | **NEW** |
| `src/jarvis/tools/skills.py` | FEAT-JARVIS-007 | **NEW** |
| `src/jarvis/agents/supervisor.py` | FEAT-JARVIS-007 | **UPDATED** — register `invoke_skill`, load skill registry |
| `src/jarvis/prompts/supervisor_prompt.py` | FEAT-JARVIS-007 | **UPDATED** — skills section (additive) |
| `src/jarvis/cli/main.py` | FEAT-JARVIS-007 | **UPDATED** — `/skill` command parsing |
| `src/jarvis/infrastructure/routing_history.py` | FEAT-JARVIS-007 | **UPDATED** — `write_skill_invocation`, edge writes, `skill_name` |
| `docs/architecture/decisions/ADR-FLEET-00X-skill-name-extension.md` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_adapter_ingress.py`, `test_telegram_roundtrip_integration.py`, `test_cross_adapter_notification_routing.py`, `test_contract_nats_core_jarvis.py` | FEAT-JARVIS-006 | **NEW** |
| `tests/test_skill_registry.py`, `test_skill_morning_briefing.py`, `test_skill_talk_prep.py`, `test_skill_project_status.py`, `test_memory_store_cross_session.py`, `test_invoke_skill_tool.py`, `test_skill_dispatch_via_command.py`, `test_skill_trace_writes.py` | FEAT-JARVIS-007 | **NEW** |
| `docs/design/FEAT-JARVIS-006/design.md` | FEAT-JARVIS-006 | **NEW** |
| `docs/design/FEAT-JARVIS-007/design.md` | FEAT-JARVIS-007 | **NEW** |
| `features/feat-jarvis-006-*/...`, `features/feat-jarvis-007-*/...` | Both | **NEW** |
| `tasks/FEAT-JARVIS-006-*.md`, `tasks/FEAT-JARVIS-007-*.md` | Both | **NEW** |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/` unless prefixed with `../`.

---

## Do-Not-Change

1. **Fleet v3 D40–D46, ADR-J-P1..P10, ADR-FLEET-001, ADR-SP-014/016/017.** Phase 4 is first real consumer of P3 (skills) and P5 (adapters).
2. **Phase 1 + 2 + 3 outputs.** Tool signatures, subagent descriptions, `CapabilityDescriptor`, `JarvisRoutingHistoryEntry` Pydantic shapes, tool docstrings, dispatch transports. Phase 4 extends via new surfaces + skills, doesn't rewrite.
3. **`nats-core` Pydantic models existing in v1.x.** Phase 4 adds two new payloads + topic constants. No modifications to existing shapes.
4. **Singular topic convention.** `jarvis.command.telegram`, `jarvis.notification.telegram`, `jarvis.command.cli`, `jarvis.notification.cli`. No plurals anywhere.
5. **ADR-FLEET-001 schema.** Skill extension is additive via `ADR-FLEET-00X`. No overwrites of existing fields.
6. **Adapter process isolation.** Adapter never imports from `src/jarvis/`. NATS-only boundary.
7. **No calendar integration.** `get_calendar_events` stays stubbed; `morning-briefing` composes around the stub.
8. **No `jarvis.learning` reader.** Writes only; reader is FEAT-JARVIS-008 (v1.5).
9. **No Pattern C ambient watcher.** Only slot reservation in `talk_prep.py`. Active ambient logic is FEAT-JARVIS-010 (v1.5).
10. **Memory Store backend stays in-memory.** Persistent backend is v1.5. Restart boundary behaviour accepted for v1.
11. **Dashboard + Reachy adapters remain deferred.** FEAT-JARVIS-009 (v1.5).
12. **Allowlist strictly enforced.** No relaxation paths in v1.
13. **Scope-preserving rules from conversation starter §2.** No new agent repos; no fleet-decision changes mid-build.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| `nats-core` cross-repo update blocks Jarvis build | Step 1 is first; bump + publish `nats-core` before any `/system-design` on Phase 4. Jarvis + adapter both pin the new version explicitly. |
| Telegram library choice locks Phase 4 into specific async patterns | `/system-design FEAT-JARVIS-006` pins via ADR. Adapter abstractions isolate library specifics to `inbound.py` + `outbound.py`. |
| Session-map SQLite corruption on adapter crash | Atomic writes + recover-on-startup; crash during a message loses that single message but not session continuity; test coverage for restart-mid-session. |
| Allowlist mis-configuration exposes bot to the world | Default allowlist = empty; bot refuses all messages if unconfigured. Explicit error at startup if `TELEGRAM_ALLOWED_CHAT_IDS` is empty. |
| Cross-adapter notification leakage (Telegram notifications landing on CLI or vice versa) | `test_cross_adapter_notification_routing.py` explicitly covers both directions. Session adapter tag is the sole routing key. |
| Skill intent matching too loose (supervisor invokes skill when user wanted free-form conversation) | Intent signatures narrow; supervisor prompt instructs to dispatch via skills only for clear intent matches; test with adversarial phrases. Calibration is a v1.5 learning-flywheel concern. |
| Skill intent matching too tight (user says "morning briefing" variant and supervisor doesn't match) | `/skill morning-briefing` command fallback always works; users can bypass intent matching when needed. |
| Memory Store in-memory backend loses state on Jarvis restart | Accepted v1 behaviour; documented in README; persistent backend is v1.5. `morning-briefing` gracefully handles missing prior-highlights. |
| `talk-prep` Pattern C slot signature locks in the wrong API for FEAT-JARVIS-010 | `/system-design FEAT-JARVIS-007` pins the slot signature carefully; FEAT-JARVIS-010 gets a review gate to revise if the signature turns out wrong before shipping Pattern C. |
| Skill trace records lose composition info (inner dispatches not linked back) | Edge writes tested explicitly in `test_skill_trace_writes.py`; outer record's `decision_id` is the join key. |
| Cross-process integration tests flaky | In-process NATS + Telegram-adapter-stub keeps Steps 1–13 deterministic. Step 14 (live check) has manual verification; Step 15 acceptance is Rich-in-the-loop. |
| End-to-end Phase 4 close reveals missed integration (e.g. Telegram formatting breaking markdown) | Acceptance test covers real Telegram rendering; formatting issues are tuning, not architecture-level; fix in-place before shipping v1. |

---

## Expected Timeline

Building on Phase 3's timeline (Phase 3: 30 Apr – 6 May 2026):

| Day | Activity | Output |
|-----|----------|--------|
| 1 (7 May) | Step 1 — `nats-core` payload additions (cross-repo): `/feature-spec`, `/feature-plan`, AutoBuild, `/task-review`, version bump. | `nats-core` minor-version release. |
| 1 (7 May) | Step 2 — `/system-design FEAT-JARVIS-006`. | Design doc. |
| 2 (8 May) | Step 3 — `/system-design FEAT-JARVIS-007`. Step 4 — `/feature-spec FEAT-JARVIS-006`. Step 6 — `/feature-plan FEAT-JARVIS-006`. | Design + spec + plan for 006. |
| 3 (9 May) | Step 8 — AutoBuild FEAT-JARVIS-006 (adapter + supervisor-side ingress + session + notification-router updates). Step 9 — `/task-review`. | Telegram adapter code-complete. |
| 4 (10 May) | Step 5 — `/feature-spec FEAT-JARVIS-007`. Step 7 — `/feature-plan FEAT-JARVIS-007`. Step 10 — begin AutoBuild FEAT-JARVIS-007 (`Skill` base + first skill). | Spec + plan for 007; first skill shipping. |
| 5 (11 May) | Step 10 cont — complete AutoBuild FEAT-JARVIS-007 (remaining skills, `invoke_skill` tool, supervisor updates, trace writes). Step 11 — `/task-review`. | FEAT-JARVIS-007 code-complete. |
| 6 (12 May) | Step 12 — full regression across both projects. Step 13 — in-process integration check. | All tests green. |
| 7 (13 May) | Step 14 — Telegram live check (bot token, real chat, real Jarvis supervisor with GB10 NATS). Fix any formatting or session-continuity issues. | Adapter working with real Telegram. |
| 8 (14 May) | Step 15 — end-to-end Phase 4 close (morning briefing from phone). Evidence artefact recorded. **Jarvis v1 ships.** | v1 ship. |

**Target: Phase 4 complete within 7–8 working days (7–14 May 2026).** Comfortably clear of DDD Southwest (16 May) — Jarvis v1 is available for talk-prep usage + live demo material in the talk itself.

---

## After Phase 4: What Comes Next

| Priority | Phase | Content |
|----------|-------|---------|
| **v1 shipped** | — | Jarvis v1: supervisor + 1 async subagent with role-dispatch (`jarvis-reasoner` × critic/researcher/planner) + `escalate_to_frontier` attended-only tool + dispatch tools + fleet registration + specialist round-trip + Forge build queue + stage-complete notifications + Telegram adapter + three skills + Memory Store. Daily use begins. |
| **v1.1** | — | FEAT-JARVIS-011 (`jarvis purge-traces` CLI) — GDPR-clean per ADR-FLEET-001. Small, targeted hardening. |
| **v1.5 (post-DDD)** | Phase 5 | FEAT-JARVIS-008 (Learning Flywheel) — `jarvis.learning` reader on `jarvis_routing_history` data accumulated through Phase 3 + Phase 4 + v1 daily use. `CalibrationAdjustment` entities + Rich-in-the-loop CLI surface. |
| **v1.5** | — | FEAT-JARVIS-009 — Dashboard + Reachy adapters (same `nats-asyncio-service` pattern as Telegram; `jarvis.command.{dashboard,reachy}` / `jarvis.notification.{dashboard,reachy}`). |
| **v1.5** | — | FEAT-JARVIS-010 — `talk-prep` Pattern C ambient nudges. Implements the slot reserved in `talk_prep.py`. Target: retrospective support for DDD Southwest + next-talk prep. First real Pattern C graduation. |
| **v1.5** | — | Real calendar integration (replaces `get_calendar_events` stub), persistent Memory Store backend, live llama-swap `/running` + `/log` reads (replaces FEAT-JARVIS-003 DDR-015's stub) feeding the swap-aware voice-latency policy (ADR-ARCH-012). The scope-doc's `quick_local` cloud-cheap-tier fallback is retired. |

---

*Phase 4 build plan: 20 April 2026*
*Predecessor: Phase 3 (FEAT-JARVIS-004 + FEAT-JARVIS-005 — NATS specialist dispatch + build queue + first trace-rich writes).*
*Input to: `/system-design FEAT-JARVIS-006`, `/system-design FEAT-JARVIS-007`.*
*"Skills are the Jarvis-level slash-command analogue. Telegram reaches Rich where he actually is."*
*Phase 4 close = Jarvis v1 ship.*
