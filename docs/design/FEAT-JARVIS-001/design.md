# FEAT-JARVIS-001 — Design

> **Feature:** Project Scaffolding, Supervisor Skeleton & Session Lifecycle
> **Phase:** 1 (Foundation)
> **Generated:** 2026-04-21 via `/system-design FEAT-JARVIS-001`
> **Status:** Proposed — input to `/feature-spec FEAT-JARVIS-001`
> **Architecture source:** [docs/architecture/ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) (2026-04-20, 30 ADRs)
> **Scope source:** [docs/research/ideas/phase1-supervisor-scaffolding-scope.md](../../research/ideas/phase1-supervisor-scaffolding-scope.md) (2026-04-20)

---

## 1. Purpose

FEAT-JARVIS-001 is the Phase 1 scaffolding feature — the runnable skeleton every subsequent v1 feature (FEAT-JARVIS-002..007) depends on. This design pins the component boundaries, public API shapes, data models, and CLI surface so AutoBuild, code review, and future features land consistently.

One-line success criterion: *"Rich can have a useful conversation with Jarvis on day 1, even though it can't dispatch to anything yet."*

## 2. Scope in-context

Jarvis has seven bounded contexts ([domain-model.md](../../architecture/domain-model.md)). FEAT-JARVIS-001 covers three; the remainder ship with later features.

| Bounded context | FEAT-JARVIS-001? | Deferred to |
|---|---|---|
| **Jarvis Reasoning Context** | **IN** (core of this feature) | — |
| **Adapter Interface Context** | Partial — CLI stub only | 006 Telegram, 009 Dashboard/Reachy |
| **Config (cross-cutting)** | **IN** | — |
| Fleet Dispatch Context | — | 002, 004, 005 |
| Ambient Monitoring Context | — | 003, 010 |
| Learning Context | — | 008 (v1.5) |
| Knowledge Context | — | 004 |
| External Tool Context | — | 002 |

See [phase1-supervisor-scaffolding-scope.md Do-Not-Change](../../research/ideas/phase1-supervisor-scaffolding-scope.md) for the exclusion list.

## 3. Surfaces shipped

| Surface | Type | Artefact |
|---|---|---|
| CLI (`jarvis chat`/`version`/`health`) | stdin/stdout + Click | [contracts/API-cli.md](contracts/API-cli.md) |
| Internal Python API | In-process module contracts | [contracts/API-internal.md](contracts/API-internal.md) |

No network protocols — no REST / GraphQL / MCP / A2A / ACP / NATS events. See [decisions/DDR-001-internal-api-in-process-only.md](decisions/DDR-001-internal-api-in-process-only.md). Consequently: no `openapi.yaml`, no `mcp-tools.json`, no `a2a-schemas.yaml` in this design output.

## 4. Data models

| Model | Purpose | Artefact |
|---|---|---|
| `Session`, `Adapter`, `AppState`, exception hierarchy | Jarvis Reasoning aggregate + composite + errors | [models/DM-jarvis-reasoning.md](models/DM-jarvis-reasoning.md) |
| `JarvisConfig` | pydantic-settings config schema | [models/DM-config.md](models/DM-config.md) |

## 5. Design decisions captured

| DDR | Decision | Why it's here |
|---|---|---|
| [DDR-001](decisions/DDR-001-internal-api-in-process-only.md) | Phase 1 exposes only CLI + internal Python API — no network protocols | Records why standard `/system-design` outputs (OpenAPI, MCP, A2A) are absent |
| [DDR-002](decisions/DDR-002-memory-store-keyed-by-user-id.md) | Memory Store namespace = `("user", user_id)` | ADR-ARCH-009 left the namespace layout open; this pins it |
| [DDR-003](decisions/DDR-003-cli-minimal-surface.md) | CLI ships exactly `chat` / `version` / `health` | Reserves future command names without implementing them |
| [DDR-004](decisions/DDR-004-session-thread-1to1.md) | `thread_id == session_id` 1:1 in Phase 1 | LangGraph thread primitive mapped to Jarvis session identity |

## 6. Component diagram

[diagrams/supervisor-container-l3.md](diagrams/supervisor-container-l3.md) — C4 Level 3 view of the Jarvis Supervisor container showing the 8 active Phase 1 modules + 8 reserved-empty packages. Requires explicit approval per `/system-design` Phase 3.5 gate.

## 7. Module layout — eight active modules + reserved

Per [ADR-ARCH-006 five-group layout](../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md):

```
src/jarvis/
├── __init__.py                 # VERSION
├── agents/                     # Group A — Shell
│   ├── __init__.py
│   └── supervisor.py           # build_supervisor(config) -> CompiledStateGraph
├── prompts/                    # Group A — Shell
│   ├── __init__.py
│   └── supervisor_prompt.py    # SUPERVISOR_SYSTEM_PROMPT constant
├── subagents/                  # Group A — RESERVED (FEAT-003)
│   └── __init__.py
├── skills/                     # Group A — RESERVED (FEAT-007)
│   └── __init__.py
├── sessions/                   # Group B — Domain
│   ├── __init__.py
│   ├── session.py              # Session Pydantic model
│   └── manager.py              # SessionManager
├── routing/                    # Group B — RESERVED (FEAT-002)
│   └── __init__.py
├── watchers/                   # Group B — RESERVED (FEAT-003)
│   └── __init__.py
├── discovery/                  # Group B — RESERVED (FEAT-004)
│   └── __init__.py
├── learning/                   # Group B — RESERVED (FEAT-008, v1.5)
│   └── __init__.py
├── tools/                      # Group C — RESERVED empty (FEAT-002)
│   └── __init__.py
├── adapters/                   # Group D — RESERVED (FEAT-004+)
│   └── __init__.py
├── config/                     # Group E — Cross-cutting
│   ├── __init__.py
│   └── settings.py             # JarvisConfig BaseSettings
├── infrastructure/             # Group E — Cross-cutting
│   ├── __init__.py
│   ├── logging.py              # structlog configuration
│   └── lifecycle.py            # startup/shutdown + AppState
├── cli/                        # Group E — Cross-cutting
│   ├── __init__.py
│   └── main.py                 # click group: chat/version/health
└── shared/                     # Shared primitives
    ├── __init__.py
    ├── constants.py            # VERSION, Adapter enum
    └── exceptions.py           # JarvisError hierarchy
```

Plus mirror under `tests/` — one test module per active module + `conftest.py` with `fake_llm`, `test_config`, `in_memory_store` fixtures per [phase1-build-plan.md §Change 10](../../research/ideas/phase1-build-plan.md).

## 8. Wiring — how the pieces compose at startup

```
env + .env
    │
    ▼
JarvisConfig()                            ← jarvis.config.settings
    │
    ▼
lifecycle.startup(config):                ← jarvis.infrastructure.lifecycle
    │
    ├── logging.configure(config.log_level)
    ├── config.validate_provider_keys()
    ├── supervisor = build_supervisor(config)     ← jarvis.agents.supervisor
    ├── store = InMemoryStore()                   ← langgraph.store
    └── session_manager = SessionManager(supervisor, store)
    │
    ▼
AppState(config, supervisor, store, session_manager)
    │
    ▼
cli.main runs its subcommand
    │
    ├── version: prints VERSION, exits 0
    ├── health:  prints AppState summary, exits 0
    └── chat:    REPL loop:
                 session = session_manager.start_session(Adapter.CLI, "rich")
                 while stdin:
                     response = await session_manager.invoke(session, line)
                     print(response)
                 session_manager.end_session(session.session_id)
```

## 9. Test shape

Per [phase1-supervisor-scaffolding-scope.md §Success Criteria](../../research/ideas/phase1-supervisor-scaffolding-scope.md):

- `tests/test_config.py` — env loading, defaults, `validate_provider_keys` failure cases.
- `tests/test_sessions.py` — `SessionManager` lifecycle; cross-session Memory Store recall test (write in session A, read in session B, same `user_id`).
- `tests/test_supervisor.py` — `build_supervisor(test_config)` returns `CompiledStateGraph`; structural assertions on nodes; no LLM call (uses `FakeListChatModel`).
- `tests/test_cli.py` — each subcommand via `CliRunner`.
- `tests/test_smoke_end_to_end.py` — CLI → supervisor → canned LLM response → stdout.

Target: 30–40 tests, 80% coverage on scaffolded modules.

## 10. Contradiction detection (against existing ADRs)

Proposed contracts were checked against all 30 accepted ADRs in `docs/architecture/decisions/`. **No contradictions detected.**

Notes:
- DDR-001 (no network protocols Phase 1) is *consistent* with ADR-ARCH-016 (NATS-only when transport lands) — the ADR does not mandate transport in Phase 1.
- DDR-002 (`user_id` keying) is a direct implementation of ADR-ARCH-009's stated intent.
- DDR-003 (minimal CLI) does not pre-empt ADR-ARCH-018's approval surface requirement — `approve-adjustment` remains reserved.
- DDR-004 (1:1 thread mapping) is compatible with ADR-ARCH-009 and does not constrain the future summary-bridge behaviour (that's a Memory Store concern, not a thread-mapping concern).

The default `JARVIS_SUPERVISOR_MODEL=openai:jarvis-reasoner` honours the *local-first inference* memory rule — the OpenAI prefix is only the init_chat_model convention; traffic goes to llama-swap on GB10 via `OPENAI_BASE_URL=http://promaxgb10-41b1:9000/v1` per ADR-ARCH-001.

## 11. Assumptions carried forward

| Assumption | Reason it's not settled here |
|---|---|
| `ASSUM-ROUTING-HISTORY-SCHEMA` | Exact `jarvis_routing_history` Pydantic shape lands at FEAT-JARVIS-004. This design ensures `Session.correlation_id` field is present so the schema can extend without rework. |
| `ASSUM-013` (Memory Store retrieval quality sufficient for cross-adapter continuity) | ADR-ARCH-009's carried assumption. Phase 1 ships `InMemoryStore` which satisfies the mechanical requirement; semantic recall quality is an empirical question for FEAT-JARVIS-006 Telegram when cross-adapter flows arrive. |
| `ASSUM-CLI-SIGNAL-HANDLING` | SIGINT during `chat` should exit 130 with session cleanup. Implementation detail; spec-able at `/feature-spec`. |

## 12. Next steps

1. **Approve the C4 L3 diagram** at [diagrams/supervisor-container-l3.md §Review gate](diagrams/supervisor-container-l3.md).
2. **Seed design to Graphiti** (commands offered at the end of this `/system-design` run — `project_design` + `architecture_decisions` groups).
3. **Proceed to `/feature-spec FEAT-JARVIS-001`** per [phase1-build-plan.md Step 3](../../research/ideas/phase1-build-plan.md) — this design is its primary context input.
4. **Then `/feature-plan FEAT-JARVIS-001`** — produce `tasks/FEAT-JARVIS-001-*.md`.
5. **Then AutoBuild** — commit order per [phase1-build-plan.md Step 5](../../research/ideas/phase1-build-plan.md): shared → config → pyproject → prompts+supervisor → infrastructure → sessions → CLI → end-to-end smoke → docs.

## 13. File manifest

```
docs/design/FEAT-JARVIS-001/
├── design.md                                        ← this file
├── contracts/
│   ├── API-cli.md                                   ← CLI surface
│   └── API-internal.md                              ← Python module contracts
├── models/
│   ├── DM-jarvis-reasoning.md                       ← Session + Adapter + AppState + exceptions
│   └── DM-config.md                                 ← JarvisConfig schema
├── diagrams/
│   └── supervisor-container-l3.md                   ← C4 L3 (mandatory review gate)
└── decisions/
    ├── DDR-001-internal-api-in-process-only.md
    ├── DDR-002-memory-store-keyed-by-user-id.md
    ├── DDR-003-cli-minimal-surface.md
    └── DDR-004-session-thread-1to1.md
```

---

*"One local reasoning model that knows which role to apply, which specialist to invoke, and when to escalate."* — [ARCHITECTURE.md §1](../../architecture/ARCHITECTURE.md)
