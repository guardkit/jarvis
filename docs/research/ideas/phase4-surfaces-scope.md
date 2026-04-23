# Phase 4: Surfaces — Telegram Adapter + Skills & Memory Store Activation — Scope Document

## For: Claude Code `/system-design` → `/feature-spec` → `/feature-plan` → AutoBuild (per feature)
## Date: 20 April 2026
## Status: Blocked on Phase 3 completion (FEAT-JARVIS-004 + FEAT-JARVIS-005 merged, end-to-end test against real Forge green, first `jarvis_routing_history` trace-rich writes landed). Ready for `/system-design FEAT-JARVIS-006` once Phase 3 closes.
## Context: Phase 3 made dispatch real. After Phase 3, Jarvis can reason about a problem, pick a brain (subagent), dispatch to a specialist, queue a Forge build, and receive stage-complete notifications — all via the CLI adapter. Phase 4 adds the two surfaces that make Jarvis genuinely *ambient*: Telegram (so Jarvis reaches Rich on his phone) and skills (so Jarvis has a named, composable vocabulary of higher-order tasks that activate the Memory Store wired in Phase 1). After Phase 4, Jarvis v1 ships.

---

## Motivation

Phase 3 closed with Jarvis doing real work through the CLI. But the CLI is one surface, and `jarvis chat` with a REPL running on the MacBook is a laptop-bound posture. The day Rich steps away from the laptop, the attended-agent value proposition stalls unless Jarvis can reach him on his phone. And the supervisor, powerful as it is, is still one-shot per invocation — every morning briefing, every talk-prep nudge, every project-status summary has to be re-hand-crafted by the reasoning model from first principles, with no composable vocabulary of *higher-order work* the supervisor (or Rich, or future adapters) can invoke by name.

Phase 4 solves both. Two features:

1. **FEAT-JARVIS-006** lands the Telegram adapter. Per Q10.3 (20 April decision), Telegram is the *only* non-CLI adapter shipping in v1 — Dashboard and Reachy are FEAT-JARVIS-009 (v1.5). Telegram is a `nats-asyncio-service`-patterned adapter process (per `jarvis-vision.md` §9) that publishes incoming Telegram messages to `jarvis.command.telegram` and consumes outgoing messages from `jarvis.notification.telegram`. Jarvis's supervisor is adapter-agnostic: it doesn't know or care whether a session is driven from CLI or Telegram. The adapter bridges the transport, and the `SessionManager` (Phase 1) + notification router (Phase 3) already understand the notion of "this session is talking via adapter X." Forge stage-complete events bridged through Phase 3's `jarvis.notification.forge-stage-complete.*` flow through to Telegram sessions the same way they flow through to CLI sessions — the plumbing is adapter-agnostic by construction.

2. **FEAT-JARVIS-007** lands three launch skills — `morning-briefing`, `talk-prep`, `project-status` — and activates the Memory Store (wired in Phase 1, unused since) for cross-session recall. Skills are the Jarvis-level analogue of GuardKit's slash commands: named, composable units that the supervisor can invoke via natural-language dispatch ("Jarvis, morning briefing please") or Rich can invoke via command syntax (`/skill morning-briefing`). Each skill is a composable *tool unit* — a small function plus a system-prompt fragment plus a capability signature — that the supervisor loads on demand. Skills can chain tools and subagents from Phases 2–3; they're not a parallel universe. This is the first phase where ADR-J-P3 ("skills are the Jarvis-level slash-command analogue") is concretely realised. `talk-prep` additionally reserves the slot for Pattern C ambient nudges per Q10.5 — the v1 ship is command-pattern form only; the ambient logic lands in FEAT-JARVIS-010 (v1.5) targeting DDD Southwest prep on 16 May 2026.

Phase 4 pairs these because they're *independent on the dependency graph but coupled on the user-value story*. Telegram without skills is a chat transport for a still-one-shot agent. Skills without Telegram are useful-but-laptop-bound. Shipping them together delivers the attended-surface value proposition in full: Rich opens Telegram in the morning, sends "morning briefing," Jarvis composes the briefing from calendar + project status + recent routing-history + pending Forge stage-completes, and replies — on the phone, before Rich is at the laptop. That is Jarvis v1 ship criterion.

Critically, Phase 4 does *not* add real-calendar integration (still stubbed from Phase 2 for `morning-briefing`), does *not* add the learning flywheel reader (`jarvis.learning` → FEAT-JARVIS-008, v1.5), does *not* add the Pattern C ambient watcher loop (→ FEAT-JARVIS-010, v1.5). The v1 ship is the *command-pattern attended agent on CLI + Telegram with three skills and an active Memory Store*. Everything else earns its way in as v1.5 / v1.1 features after v1 has soaked in daily use.

---

## Scope: Two Features

### FEAT-JARVIS-006: Telegram Adapter

**Problem:** Jarvis's attended value proposition collapses the moment Rich is away from his laptop. The CLI adapter is fine for coding-sessions-at-the-desk, but morning briefings, talk-prep reminders, project-status check-ins, and between-meeting redirect requests all happen on the phone. The supervisor (Phase 1), dispatch surface (Phases 2–3), and notification router (Phase 3) are all adapter-agnostic — a Telegram adapter drops in as a peer to CLI without changing any of them.

Per Q10.3 (20 April decision), Telegram is the *only* non-CLI adapter in v1. Dashboard and Reachy come later. Per `jarvis-vision.md` §9, the adapter follows the `nats-asyncio-service` pattern: a separate long-running process (not embedded in the Jarvis supervisor) that bridges Telegram's Bot API to NATS topics. Session correlation uses the `session_id` carried in payload metadata — Jarvis's supervisor invocations on behalf of a Telegram session quote that `session_id` back on all outbound notifications, and the adapter knows which Telegram chat to deliver to.

**Changes required:**

#### 1. Telegram adapter process (`adapters/telegram/`)

A separate process, *not* inside `src/jarvis/`. Adapters live in a sibling directory so the Jarvis supervisor can be imported cleanly without pulling adapter deps:

- `adapters/telegram/pyproject.toml` — adapter-local Python project. Dependencies: `nats-py`, `nats-core` (shared Pydantic payloads), `python-telegram-bot` (or the ADR-pinned Telegram library), `pydantic-settings`.
- `adapters/telegram/src/jarvis_telegram_adapter/main.py` — the `nats-asyncio-service`-patterned entry point. On startup: connect to NATS, register the adapter's manifest on `fleet.register` (so it's discoverable), connect to Telegram Bot API via long-polling (or webhook — ADR-pinned), start inbound + outbound loops.
- `adapters/telegram/src/jarvis_telegram_adapter/inbound.py` — Telegram → NATS. Each incoming Telegram message becomes a `JarvisCommandPayload` (new payload shape in `nats-core`; see Change 4) published to `jarvis.command.telegram`. The adapter generates a fresh `session_id` on first contact from a given Telegram `chat_id` and persists the mapping for session continuity (stateful adapter, disk-backed SQLite or similar — ADR-pinned).
- `adapters/telegram/src/jarvis_telegram_adapter/outbound.py` — NATS → Telegram. Subscribes to `jarvis.notification.telegram` + `jarvis.notification.forge-stage-complete.*`; filters by `session_id` against the adapter's local `session_id` → `chat_id` map; sends matched messages to Telegram.
- `adapters/telegram/src/jarvis_telegram_adapter/config.py` — `TelegramAdapterConfig` pydantic settings. `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` (allowlist — Rich's Telegram chat is the only allowed one for v1; see Change 6 on trust), NATS URL, session-map DB path.
- `adapters/telegram/README.md` — run instructions, env vars, how to pair with a running Jarvis supervisor.

The adapter never imports from `src/jarvis/`. They communicate *only* via NATS payloads defined in `nats-core`. This preserves the ability to ship Jarvis without the adapter, or the adapter on a different machine from the supervisor.

#### 2. Jarvis-side adapter receiver (`src/jarvis/infrastructure/adapter_ingress.py`)

The supervisor-side counterpart: a subscriber to `jarvis.command.*` that routes incoming adapter commands into a fresh or ongoing session:

- On `jarvis.command.telegram` receipt, `SessionManager.get_or_create_session(adapter="telegram", session_id=payload.session_id)` either resumes the session (carrying Memory Store state, thread continuity) or creates a new one.
- The message body is fed into the supervisor graph as the next user turn.
- Supervisor's streaming response becomes zero or more `jarvis.notification.telegram` publishes, with `session_id` metadata set so the adapter can route back.
- CLI adapter (which has been the only adapter through Phases 1–3) is refactored to use the *same* pattern — CLI becomes an in-process adapter publishing to an internal `jarvis.command.cli` equivalent, so the supervisor-side code is uniform. `/system-design` pins whether CLI fully joins the NATS bus or stays in-process-only via a shared interface — the latter is simpler but skews the symmetry.

#### 3. Notification router update (`src/jarvis/infrastructure/forge_notifications.py`)

Phase 3 landed the `pipeline.stage-complete.*` → `jarvis.notification.forge-stage-complete.*` bridge routed to the CLI by `SessionManager.pending_notifications`. Phase 4 generalises this:

- Adapter-tagged notifications: the internal router now tags each outbound notification with the session's adapter (`cli`, `telegram`) based on the session's metadata.
- `SessionManager.pending_notifications(session_id)` still works for CLI. For Telegram sessions, notifications are published directly to `jarvis.notification.telegram` (+ the Forge-stage-complete bridge if applicable), tagged with the `session_id` so the Telegram adapter's outbound loop picks them up.
- The adapter-agnostic property is explicit: stage-complete events surface to Rich on *whichever adapter owns the queuing session*, not necessarily the CLI. If Rich queues a build from Telegram ("Jarvis, build FEAT-X"), the stage-complete notifications come back to Telegram.

#### 4. New `nats-core` payload shapes (cross-repo touch)

Minor additions to `nats-core` — the first time Phase 4 touches a sibling repo:

- `JarvisCommandPayload`: `session_id`, `adapter` (`"cli" | "telegram"`), `user_message_text`, `user_id` (adapter-scoped — Telegram user ID for Telegram, OS username for CLI), `timestamp`, `correlation_id`.
- `JarvisNotificationPayload`: `session_id`, `adapter`, `message_body` (text), `attachments` (optional, for future media), `timestamp`, `correlation_id`, `parent_request_id` (optional).
- Topic constants added to `nats-core/src/nats_core/topics.py`: `JARVIS_COMMAND_CLI`, `JARVIS_COMMAND_TELEGRAM`, `JARVIS_NOTIFICATION_CLI`, `JARVIS_NOTIFICATION_TELEGRAM`, `JARVIS_NOTIFICATION_FORGE_STAGE_COMPLETE_PREFIX` (already landed in Phase 3 — mentioned here for completeness).

These are minor, additive, and backward-compatible. `nats-core` version bumps to the next minor; Jarvis and the adapter both pin to it.

#### 5. Adapter-side trust model

Per fleet v3 §10, adapters must not be credulous about messages they receive:

- The Telegram adapter enforces a strict `TELEGRAM_ALLOWED_CHAT_IDS` allowlist. v1 ships with a single-entry allowlist (Rich's Telegram chat).
- Any message from a non-allowlisted `chat_id` is logged and silently dropped (no reply — avoid revealing bot existence to random scanners).
- No one-click approvals for sensitive actions via Telegram in v1. If the supervisor's dispatch reasoning decides on a `queue_build`, the build queues with `originating_adapter="telegram"` — but a Telegram-originated `queue_build` is just a normal queue (AutoBuild's existing guardrails on the Forge side handle the actual build safety). Sensitive-action gating from Telegram is a v1.5 hardening.
- Adapter process logs (including message bodies) stay on the user's machine and are never forwarded to other machines without explicit config change.

#### 6. Tests

- Integration test: in-process Telegram-adapter-stub + real NATS test server + Jarvis supervisor-with-stubbed-LLM. Rich simulates sending a Telegram message; it becomes `jarvis.command.telegram`; supervisor processes it; response comes back on `jarvis.notification.telegram`; adapter stub "delivers" it.
- Cross-adapter notification routing: queue a build from a Telegram session, assert stage-complete notifications route to Telegram not CLI. Queue a build from CLI, assert they route to CLI not Telegram.
- Allowlist test: non-allowlisted `chat_id` → silent drop.
- Session continuity test: same `chat_id` across two messages hits the same `session_id`; Memory Store state from turn 1 is available in turn 2.
- Contract tests: the two new `nats-core` payload shapes round-trip correctly.

---

### FEAT-JARVIS-007: Skills & Memory Store Activation

**Problem:** The supervisor after Phase 3 is powerful but has no named, higher-order vocabulary. Every morning Rich wants a briefing, the supervisor has to be re-prompted from scratch to remember what a briefing consists of. Every time Rich thinks about the DDD Southwest talk, the supervisor re-derives what "talk prep" means. Skills fix this by giving the supervisor (and Rich) a composable, named vocabulary of higher-order tasks — each one a small function + system-prompt fragment + capability signature. Skills chain tools and subagents from Phases 2–3; they're additive composition, not a parallel path.

Phase 1 wired the Memory Store (in-memory backend) into the supervisor but nothing in Phases 1–3 *used* it. Phase 4 activates it: skills write and read Memory Store state, so `morning-briefing` today knows what yesterday's briefing highlighted, `project-status` knows which projects Rich asked about last, and `talk-prep` accumulates prep material over days.

**Changes required:**

#### 1. Skill framework (`src/jarvis/skills/__init__.py` + `src/jarvis/skills/base.py`)

A minimal `Skill` abstraction:

- `SkillDescriptor` Pydantic model: `name`, `description` (for supervisor docstring-style dispatch), `intent_signatures` (natural-language patterns that trigger the skill), `command_alias` (e.g. `/morning-briefing`), `required_tools` (list of tool names the skill composes), `required_subagents` (list of subagent names), `memory_store_keys` (the keys the skill reads + writes).
- `Skill` abstract base with `run(session, supervisor, inputs) -> SkillResult` async method. `run` is the skill's imperative core — it orchestrates tool + subagent calls and writes to Memory Store.
- `SkillRegistry`: holds the set of loaded skills, indexed by name and by intent signature.
- Skills are *not* tools. Tools are atomic capabilities the supervisor reasons over; skills are named compositions the supervisor invokes as coherent units. A skill internally *uses* tools and subagents.

#### 2. The three launch skills

Each skill in its own module under `src/jarvis/skills/`:

**`src/jarvis/skills/morning_briefing.py`** — `MorningBriefingSkill`:
- Intent: "morning briefing", "what's on today", "brief me", "catch me up on today".
- Composes: `get_calendar_events(window="today")` (still stubbed from Phase 2 — v1 returns canned or empty list; v1.5 wires real calendar), `list_available_capabilities()` (to note any newly-online specialists), `SessionManager.recent_sessions_summary()` (a new Phase 4 addition — see Change 4), Graphiti read of recent `jarvis_routing_history` entries for yesterday (fed through `jarvis-reasoner` with `role=critic` if Rich asked for evaluation, else `role=planner` for default summarisation — per [FEAT-JARVIS-003 DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md) / [DDR-011](../../design/FEAT-JARVIS-003/decisions/DDR-011-role-enum-closed-v1.md); the scope-doc `adversarial_critic` + `quick_local` subagents are retired).
- Memory Store: writes `last_morning_briefing_date`, `last_morning_briefing_highlights` (list of 3-5 items); reads `last_morning_briefing_highlights` to note continuity ("yesterday's top item was X — update?").
- Returns a structured briefing the supervisor renders as markdown.

**`src/jarvis/skills/talk_prep.py`** — `TalkPrepSkill`:
- Intent: "talk prep", "DDD Southwest prep", "prep the talk", "what should I practise for the talk".
- Composes: Graphiti read of `jarvis_routing_history` entries tagged with the talk project, `jarvis-reasoner` with `role=researcher` for any requested research on DDD-Southwest-relevant topics, `role=planner` for quick summaries (per [FEAT-JARVIS-003 DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md) / [DDR-011](../../design/FEAT-JARVIS-003/decisions/DDR-011-role-enum-closed-v1.md); the scope-doc `long_research` + `quick_local` subagents are retired).
- Memory Store: writes `talk_prep_sessions` (append-only list of what each prep session covered, with dates), `talk_prep_open_questions` (running list), `talk_prep_rehearsal_count`; reads all of these on each invocation so the skill knows what's been covered and what's outstanding.
- **Pattern C slot reservation (Q10.5):** the skill module includes a clearly marked `# --- FEAT-JARVIS-010 Pattern C ambient nudges land here (v1.5) ---` section with a no-op stub `async def maybe_emit_ambient_nudge(...)`. v1 `talk-prep` is command-pattern only; the ambient watcher loop that calls `maybe_emit_ambient_nudge` on a schedule/trigger is the v1.5 FEAT-JARVIS-010 feature.

**`src/jarvis/skills/project_status.py`** — `ProjectStatusSkill`:
- Intent: "project status", "how is X doing", "status update on Y", "where am I on Z".
- Composes: Graphiti read of `jarvis_routing_history` entries scoped to the mentioned project, `dispatch_by_capability(tool_name="<architect-capability>", ...)` optionally for a C4-view freshness check if project context suggests architecture questions (renamed from `call_specialist` per [FEAT-JARVIS-002 DDR-005](../../design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md)), `jarvis-reasoner` with `role=planner` for synthesis (per [FEAT-JARVIS-003 DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md)).
- Memory Store: reads `active_projects` (list of project IDs Rich has interacted with), `project_last_status_query` (per-project timestamp); writes updates to both.
- Returns a structured status summary per project.

#### 3. Supervisor integration (`src/jarvis/agents/supervisor.py` + `src/jarvis/prompts/supervisor_prompt.py`)

- Skills registered at supervisor startup via `SkillRegistry.load_launch_skills()`.
- Supervisor system prompt gains a "skills" section that enumerates available skills + their intent signatures. The supervisor learns to recognise skill-intent phrases in user messages and dispatch via a new tool `invoke_skill(name: str, inputs: dict = {}) -> SkillResult`.
- Command dispatch: CLI (and Telegram via the adapter) also accept `/skill <name>` syntax. The adapter ingress parses `/skill ...` commands and dispatches directly via `SkillRegistry` without going through supervisor reasoning — the user's command *is* the disambiguation. This is the only case where the supervisor's reasoning is bypassed on purpose; it matches the GuardKit slash-command model.
- Supervisor prompt preserves all Phase 1–3 sections; skills section is additive.

#### 4. Memory Store activation (`src/jarvis/sessions/memory_store.py`)

Phase 1 wired the Memory Store abstraction + in-memory backend. Phase 4 uses it:

- Skills read + write via typed `MemoryKey` helpers. Each skill declares its keys in `SkillDescriptor.memory_store_keys`.
- `SessionManager.recent_sessions_summary()` — a Phase 4 addition that queries the Memory Store for recent-session metadata (last N session IDs, last active timestamps, skills invoked) without reading full message history. Used by `morning-briefing`.
- Backend remains in-memory for v1. Backend swap to persistent (SQLite, Redis, or Memory Store → LangGraph store) is a v1.5 concern — for v1, Memory Store is reset on Jarvis restart, which is acceptable because Rich restarts Jarvis infrequently and morning briefings over restart boundaries simply lack yesterday's highlights on day one after a restart.

#### 5. Skill invocation via `invoke_skill` tool

- `src/jarvis/tools/skills.py` (NEW): `invoke_skill(name: str, inputs: dict = {}) -> SkillResult` — looks up the skill in the registry, runs it, returns result.
- This tool is registered on the supervisor like any other tool (FEAT-JARVIS-002 pattern). Its docstring teaches the supervisor: "Prefer `invoke_skill` over re-deriving higher-order tasks from scratch. If the user's intent matches a skill's intent signatures, invoke it directly."
- The tool adds a single row to `jarvis_routing_history` per invocation with `subagent_type="skill"`, `subagent_task_id=skill_run_id`, populated Jarvis-specific extensions (e.g. `skill_name` added to `supervisor_reasoning_summary`).

#### 6. Trace-rich writes for skills

Per ADR-FLEET-001, skill invocations are trace-rich records:

- Every skill invocation writes a `jarvis_routing_history` entry with `subagent_type="skill"`.
- The skill's internal tool + subagent dispatches are *separate* trace records (they happen via the normal tool/subagent infrastructure from Phases 2–3, so they self-trace).
- An edge from the skill's outer record to each inner tool/subagent record preserves the composition structure so the v1.5 learning reader can analyse skill-level patterns.

#### 7. Tests

- Unit tests per skill: skill registers correctly, intent signatures match, Memory Store reads + writes hit expected keys.
- Integration test: `invoke_skill("morning_briefing")` with a mocked LLM (deterministic tool calls), assert the composed tool + subagent dispatches happen in the right order, assert Memory Store state mutated correctly, assert the returned `SkillResult` shape.
- Memory Store continuity test: invoke `morning-briefing` twice in the same session, assert turn 2 sees turn 1's highlights.
- Cross-session Memory Store test: end session, start new session with same `user_id`, invoke `project-status`, assert prior session's `active_projects` are visible.
- Command dispatch test: `/skill morning-briefing` from CLI bypasses supervisor reasoning and hits the registry directly.
- `talk-prep` Pattern C slot test: `maybe_emit_ambient_nudge` is importable, is a no-op, does not break imports — proves the slot is reserved without active behaviour.
- Trace-rich writes test: skill invocation creates the outer record + edges to inner records.

---

## Do-Not-Change

1. **Fleet v3 D40–D46, ADR-J-P1..P10, ADR-FLEET-001, ADR-SP-014/016/017.** Phase 4 is first real consumer of P3 (skills) and P5 (adapters).
2. **Phase 1 + Phase 2 + Phase 3 outputs.** Tools, subagent (single `jarvis-reasoner` with role-dispatch per [FEAT-JARVIS-003 DDR-010](../../design/FEAT-JARVIS-003/decisions/DDR-010-single-async-subagent-supersedes-four-roster.md)), `dispatch_by_capability` / `queue_build` transports (renamed from `call_specialist` per [FEAT-JARVIS-002 DDR-005](../../design/FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md)), supervisor prompt sections, `CapabilityDescriptor`, `JarvisRoutingHistoryEntry` Pydantic shapes.
3. **`nats-core` Pydantic models already defined.** Additions to `nats-core` in Change 4 are strictly additive (new payloads, new topic constants) — no modifications to existing shapes.
4. **Singular topic convention (ADR-SP-016).** `jarvis.command.cli`, `jarvis.command.telegram`, `jarvis.notification.cli`, `jarvis.notification.telegram` — singular throughout.
5. **`ADR-FLEET-001` schema authoritative.** Skill trace records use the existing schema + existing Jarvis-specific extensions + a new `skill_name` field added via an explicit `ADR-FLEET-00X` append-only extension, not via silent schema change.
6. **Telegram adapter process isolation.** Adapter never imports from `src/jarvis/`. Communication is NATS-only. This preserves deployment flexibility + keeps the Jarvis supervisor pure.
7. **No calendar integration in Phase 4.** `get_calendar_events` stays stubbed from Phase 2; `morning-briefing` composes around the stub. Real calendar is v1.5.
8. **No `jarvis.learning` reader.** Writes from skills land in `jarvis_routing_history`; the reader is still FEAT-JARVIS-008 (v1.5).
9. **No Pattern C ambient watcher loop.** Only the slot reservation in `talk_prep.py`. Active ambient behaviour is FEAT-JARVIS-010 (v1.5).
10. **Memory Store backend stays in-memory for v1.** Persistent backend is v1.5. Restart boundary behaviour is accepted as a v1 limitation.
11. **Dashboard + Reachy adapters stay deferred.** FEAT-JARVIS-009 (v1.5). Phase 4 does not scaffold them.
12. **Adapter trust model.** Allowlist enforcement is strict; no relaxation paths in v1.

---

## Success Criteria

1. All Phase 1 + Phase 2 + Phase 3 tests still pass (zero regressions).
2. Telegram adapter process runs against a live Telegram bot token + connects to NATS on GB10.
3. Round-trip: Rich sends a Telegram message → Jarvis supervisor processes → reply arrives in Telegram. Session continuity across multiple messages in the same chat.
4. Queuing a build from Telegram surfaces stage-complete notifications back to Telegram (not CLI). Queuing from CLI still surfaces to CLI.
5. Allowlist enforcement: non-allowlisted `chat_id` is silently dropped.
6. Three launch skills (`morning-briefing`, `talk-prep`, `project-status`) are registered at supervisor startup.
7. Supervisor recognises skill-intent phrases and dispatches via `invoke_skill` (test with mocked LLM + canned prompts: "morning briefing please" → `invoke_skill("morning_briefing")`; "talk prep" → `invoke_skill("talk_prep")`; "how's the jarvis project" → `invoke_skill("project_status", inputs={"project": "jarvis"})`).
8. `/skill <name>` command syntax works from CLI (and from Telegram via the adapter).
9. Memory Store round-trip: skills read + write to expected keys; cross-session recall works within the in-memory backend's lifetime.
10. `talk-prep`'s Pattern C slot is present, clearly marked, and a no-op — imports cleanly, does not emit anything.
11. `jarvis_routing_history` trace-rich writes for skill invocations land per ADR-FLEET-001 + the new `skill_name` extension.
12. End-to-end Phase 4 close: Rich sends "morning briefing" to the Telegram bot; the reply arrives in Telegram; the reply composes calendar stub + project status + recent routing history + Memory Store continuity; the trace record for the skill invocation + its inner dispatches is visible in Graphiti.
13. Ruff + mypy clean on all new modules (both in `src/jarvis/` and in `adapters/telegram/`).

---

## Files That Will Change

| File | Feature | Change Type |
|------|---------|------------|
| `pyproject.toml` | FEAT-JARVIS-007 | **UPDATED** — no new deps expected for skills themselves (they reuse existing infrastructure) |
| `adapters/telegram/pyproject.toml` | FEAT-JARVIS-006 | **NEW** — separate Python project for the adapter |
| `adapters/telegram/src/jarvis_telegram_adapter/{__init__,main,inbound,outbound,config}.py` | FEAT-JARVIS-006 | **NEW** — adapter process |
| `adapters/telegram/README.md` | FEAT-JARVIS-006 | **NEW** — run instructions |
| `adapters/telegram/tests/test_*.py` | FEAT-JARVIS-006 | **NEW** — adapter-local tests |
| `src/jarvis/infrastructure/adapter_ingress.py` | FEAT-JARVIS-006 | **NEW** — supervisor-side `jarvis.command.*` subscriber + session routing |
| `src/jarvis/infrastructure/forge_notifications.py` | FEAT-JARVIS-006 | **UPDATED** — adapter-tagged outbound routing |
| `src/jarvis/infrastructure/lifecycle.py` | FEAT-JARVIS-006 | **UPDATED** — start adapter_ingress subscriber on startup |
| `src/jarvis/sessions/manager.py` | FEAT-JARVIS-006, -007 | **UPDATED** — `get_or_create_session(adapter=...)`, `recent_sessions_summary()` |
| `src/jarvis/sessions/memory_store.py` | FEAT-JARVIS-007 | **UPDATED** — typed `MemoryKey` helpers, skill-keyed accessors |
| `src/jarvis/skills/__init__.py` | FEAT-JARVIS-007 | **NEW** |
| `src/jarvis/skills/base.py` | FEAT-JARVIS-007 | **NEW** — `Skill` base, `SkillDescriptor`, `SkillRegistry`, `SkillResult` |
| `src/jarvis/skills/morning_briefing.py` | FEAT-JARVIS-007 | **NEW** |
| `src/jarvis/skills/talk_prep.py` | FEAT-JARVIS-007 | **NEW** — includes Pattern C slot reservation |
| `src/jarvis/skills/project_status.py` | FEAT-JARVIS-007 | **NEW** |
| `src/jarvis/tools/skills.py` | FEAT-JARVIS-007 | **NEW** — `invoke_skill` tool |
| `src/jarvis/agents/supervisor.py` | FEAT-JARVIS-007 | **UPDATED** — register `invoke_skill`, load skill registry |
| `src/jarvis/prompts/supervisor_prompt.py` | FEAT-JARVIS-007 | **UPDATED** — skills section (additive) |
| `src/jarvis/cli/main.py` | FEAT-JARVIS-007 | **UPDATED** — `/skill <name>` command parsing |
| `src/jarvis/infrastructure/routing_history.py` | FEAT-JARVIS-007 | **UPDATED** — `write_skill_invocation` + edge writes to inner records; `skill_name` Jarvis extension |
| `../nats-core/src/nats_core/payloads/jarvis_command.py` | FEAT-JARVIS-006 | **NEW** — `JarvisCommandPayload` in `nats-core` |
| `../nats-core/src/nats_core/payloads/jarvis_notification.py` | FEAT-JARVIS-006 | **NEW** — `JarvisNotificationPayload` in `nats-core` |
| `../nats-core/src/nats_core/topics.py` | FEAT-JARVIS-006 | **UPDATED** — new topic constants |
| `tests/test_adapter_ingress.py` | FEAT-JARVIS-006 | **NEW** |
| `tests/test_telegram_roundtrip_integration.py` | FEAT-JARVIS-006 | **NEW** — cross-process integration |
| `tests/test_cross_adapter_notification_routing.py` | FEAT-JARVIS-006 | **NEW** |
| `tests/test_skill_registry.py` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_skill_morning_briefing.py` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_skill_talk_prep.py` | FEAT-JARVIS-007 | **NEW** — includes Pattern C slot no-op test |
| `tests/test_skill_project_status.py` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_memory_store_cross_session.py` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_invoke_skill_tool.py` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_skill_dispatch_via_command.py` | FEAT-JARVIS-007 | **NEW** |
| `tests/test_skill_trace_writes.py` | FEAT-JARVIS-007 | **NEW** |
| `docs/design/FEAT-JARVIS-006/design.md` | FEAT-JARVIS-006 | **NEW** |
| `docs/design/FEAT-JARVIS-007/design.md` | FEAT-JARVIS-007 | **NEW** |
| `docs/architecture/decisions/ADR-FLEET-00X-skill-name-extension.md` | FEAT-JARVIS-007 | **NEW** — append-only extension to `jarvis_routing_history` |
| `features/feat-jarvis-006-*/...` | FEAT-JARVIS-006 | **NEW** |
| `features/feat-jarvis-007-*/...` | FEAT-JARVIS-007 | **NEW** |
| `tasks/FEAT-JARVIS-006-*.md` | FEAT-JARVIS-006 | **NEW** |
| `tasks/FEAT-JARVIS-007-*.md` | FEAT-JARVIS-007 | **NEW** |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/` unless prefixed with `../`.

---

## Open Questions `/system-design` Resolves (for Phase 4's benefit)

- **Telegram library choice.** `python-telegram-bot` (most popular) vs `aiogram` (async-native, cleaner ergonomics). ADR-pinned.
- **Telegram transport.** Long-polling (simpler, no public endpoint needed) vs webhook (lower latency, needs public URL). v1 default: long-polling — Rich's machine may not have a public endpoint.
- **Adapter session-map persistence.** SQLite (simple), filesystem-backed (simplest), Memory Store (consistent with Jarvis-side but coupling). ADR-pinned; SQLite is the default recommendation for isolation.
- **CLI adapter refactor scope.** Does CLI fully join the NATS bus via `jarvis.command.cli` / `jarvis.notification.cli`, or does it stay in-process via a shared interface? In-process is simpler; on-the-bus is symmetric. ADR choice affects how much Phase 4 touches Phase 1–3 code.
- **Skill invocation routing mid-session.** When the supervisor is mid-turn and a skill intent triggers, does it invoke the skill synchronously (blocking the turn) or spawn an async subagent for the skill (non-blocking)? Recommendation: synchronous for v1 — skills are fast enough; async is a v1.5 consideration.
- **Exact Memory Store key schema.** Each skill's `memory_store_keys` list — pinned by `/system-design FEAT-JARVIS-007` to avoid key collisions.
- **Ambient slot API shape for FEAT-JARVIS-010.** Even though v1 only reserves the slot, the slot's function signature is the contract FEAT-JARVIS-010 will implement against. Pin the signature now so FEAT-JARVIS-010 is additive, not a rework.

---

*Scope document: 20 April 2026*
*Input to: `/system-design FEAT-JARVIS-006`, `/system-design FEAT-JARVIS-007`.*
*"Skills are the Jarvis-level slash-command analogue."*
