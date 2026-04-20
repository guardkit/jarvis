# Phase 1: Project Scaffolding, Supervisor Skeleton & Session Lifecycle — Scope Document

## For: Claude Code `/system-arch` → `/system-design FEAT-JARVIS-001` → `/feature-spec FEAT-JARVIS-001` → `/feature-plan FEAT-JARVIS-001` → AutoBuild
## Date: 20 April 2026
## Status: Ready for `/system-arch` (target 21 April 2026), then `/feature-spec FEAT-JARVIS-001`
## Context: `guardkit init langchain-deepagents-orchestrator` complete (20 April). Fleet v3 + Jarvis vision v2 + conversation-starter v2 settled. `/system-arch` has not yet run — the Phase 1 build plan's Step 1 invokes it. Phase 1 scope absorbs what the 20 April conversation reframed away from a pre-feature "pin bump": all Python scaffolding lands inside this feature.

---

## Motivation

Jarvis is the attended-surface of the fleet — the Tony Stark mini-Jarvis. Per fleet v3 D40, Jarvis IS the General Purpose DeepAgent with dispatch tools; routing is tool selection, not a separate process. Everything subsequent — dispatch tools (FEAT-JARVIS-002), async subagents (003), NATS specialist dispatch (004), Forge queue dispatch (005), Telegram adapter (006), skills + Memory Store (007) — depends on the supervisor skeleton and session lifecycle landing cleanly first.

FEAT-JARVIS-001 is foundational for three reasons:

1. **The Python scaffold does not yet exist.** `guardkit init` landed `.claude/` agents, rules, CLAUDE.md and `.guardkit/graphiti.yaml` — but no `src/`, no `tests/`, no `pyproject.toml`. The template's 20 pattern-layer scaffold files are consumed by AutoBuild, not at init time. So the very first feature creates the directory structure every other feature will extend.

2. **The DeepAgents 0.5.3 pin lives in the feature that creates the dependency file.** Per the 20 April reframing, the pin is no longer a pre-feature step — `pyproject.toml` is created *here*, with `deepagents>=0.5.3,<0.6` as an explicit scaffolding subtask. The pin is recorded as an ADR by tomorrow's `/system-arch` and implemented in this feature. Same pattern Forge and Study Tutor used.

3. **The "useful conversation before anything fancy works" success criterion lives here.** Parting thought in §14 of the conversation starter: Jarvis v1 isn't about batch correctness like Forge — it's about Rich having a useful conversation with it on day 1, even if it can't dispatch to anything yet. FEAT-JARVIS-001 is that day-1 surface.

The DDD Southwest talk (16 May 2026) needs Jarvis v1 shipping *attended dispatch* by May. Phase 1 is the 3–4-day pressure valve that converts the 20 April decisions into a runnable shell the rest of the v1 features compound on.

---

## Scope: One Feature

### FEAT-JARVIS-001: Project Scaffolding, Supervisor Skeleton & Session Lifecycle

**Problem:** Post-`guardkit init`, the Jarvis repo has `.claude/` agents, rules, `CLAUDE.md`, and `.guardkit/graphiti.yaml` — but no Python scaffold. Nothing is importable, nothing is testable, nothing is runnable. Every subsequent v1 feature depends on: a `src/jarvis/` package tree matching the `langchain-deepagents-orchestrator` template's layer structure; a `pyproject.toml` pinning `deepagents>=0.5.3,<0.6` (the minimum version with `AsyncSubAgentMiddleware` preview support); a `jarvis` CLI entrypoint; a `create_deep_agent()`-produced supervisor that can hold a conversation; a session type + thread-per-session model per ADR-J-P3; Memory Store integration per DeepAgents 0.5.3; and startup/shutdown lifecycle that's clean enough to extend with NATS, subagents, adapters, and skills in later features without churn. None of this exists yet. The exact shapes of these pieces — module boundaries, the `jarvis.config` surface, the supervisor factory function signature, whether `create_agent()` or `create_deep_agent()` is the right factory — are decisions tomorrow's `/system-arch` will produce ADRs for (notably the DeepAgents pin ADR and the supervisor factory ADR). This feature is the first consumer of those ADRs.

**Changes required:**

#### 1. Python project scaffolding (`pyproject.toml`, `src/jarvis/`, `tests/`)

Create the minimal but template-faithful Python project:

- `pyproject.toml` with:
  - Project metadata (`name = "jarvis"`, description from `CLAUDE.md`)
  - `requires-python = ">=3.12"` (matches Forge and specialist-agent)
  - Runtime dependency: **`deepagents>=0.5.3,<0.6`** — the pin from the `/system-arch` ADR (likely ADR-J-001 or similar; exact ID resolved at `/system-arch` time)
  - Runtime dependencies: `langchain-core`, `langgraph`, `pydantic>=2`, `pydantic-settings`, `structlog`, `python-dotenv` (minimum needed for supervisor + config + logging — NATS, nats-core, graphiti-core are added by the features that use them)
  - Dev dependencies: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
  - `[project.scripts]` entry: `jarvis = "jarvis.cli.main:main"`
  - Ruff + mypy config inline or in adjacent files matching specialist-agent's and Forge's style
- `src/jarvis/__init__.py` with package version
- `src/jarvis/` layer structure per the `langchain-deepagents-orchestrator` template — exact layer names and boundaries are for `/system-arch` and `/system-design` to fix, but the expected shape is:
  - `agents/` — supervisor factory + (in future features) async subagent graphs
  - `tools/` — (empty in Phase 1; populated by FEAT-JARVIS-002)
  - `prompts/` — supervisor system prompt
  - `config/` — `pydantic-settings`-based config loader + environment schema
  - `infrastructure/` — logging, lifecycle hooks, (in future features) NATS client wrapper
  - `sessions/` — session type, thread state, Memory Store wrapper
  - `cli/` — CLI entrypoint (`jarvis` command)
  - `shared/` — constants, exceptions, version
- `tests/` with the same shape, at least one smoke test module per layer, `conftest.py` with shared fixtures

The exact layer names follow from `/system-arch`'s architecture outputs — the feature spec and plan will pin them. This scope doc commits to the template pattern without pre-empting ADR wording.

#### 2. Supervisor factory (`src/jarvis/agents/supervisor.py` or similar)

A `build_supervisor(config: JarvisConfig) -> CompiledStateGraph` function that returns a `create_deep_agent()`- (or `create_agent()`-) produced DeepAgent. Whether the factory is `create_deep_agent` or `create_agent` is an ADR for `/system-arch` (both are DeepAgents 0.5.3 factories; specialist-agent chose `create_agent` per its Phase 1 "Do-Not-Change" list, Forge chose `create_deep_agent` per ADR-ARCH-020 — Jarvis's choice falls out of whether the supervisor uses the full DeepAgents built-in toolset or a trimmed one).

For Phase 1:

- Supervisor is wired with the **DeepAgents built-ins only** (`write_todos`, filesystem-virtual, `execute` disabled or sandboxed, `task`). No custom tools yet — FEAT-JARVIS-002 adds those.
- No subagents yet — FEAT-JARVIS-003 adds async subagents.
- Supervisor system prompt lives in `src/jarvis/prompts/supervisor_prompt.py` — Phase 1 ships a minimal-but-correct prompt that states Jarvis's purpose, the "cheapest-that-fits, escalate on need" preference stub (even though no subagents exist yet — so the preference is dormant), and the attended-conversation posture. Later features extend the prompt with dispatch-tool guidance and skill guidance.
- Model selection via config: Phase 1 defaults the supervisor to a cheap cloud model (e.g. `gemini-3-flash` or equivalent) while leaving the constant discoverable for the ADR to pin. `/system-arch` may produce an ADR on supervisor model choice; Phase 1 honours whatever it lands.

#### 3. Session type + thread-per-session model (`src/jarvis/sessions/`)

Per ADR-J-P3 (thread-per-session with shared Memory Store):

- A `Session` Pydantic model carrying: `session_id`, `adapter` (enum: `cli`, `telegram`, `dashboard`, `reachy` — only `cli` meaningful in Phase 1), `user_id`, `thread_id` (LangGraph thread), `started_at`, `correlation_id`, and a `metadata` dict.
- A `SessionManager` class that creates sessions, manages thread lifecycle, and integrates with LangGraph's Memory Store for cross-session recall. `SessionManager` exposes `start_session(adapter, user_id) -> Session`, `resume_session(session_id) -> Session`, `end_session(session_id)`, and an async `invoke(session, user_input) -> str` method that runs the supervisor on the session's thread.
- Memory Store integration: sessions share a Memory Store instance so "last week we discussed…" works across adapters and threads. Memory Store entries are keyed by `user_id`, not `session_id`.

No NATS wiring yet — adapters come in FEAT-JARVIS-006. Phase 1's sessions are CLI-only; the data model is shaped so future adapters slot in without session-type changes.

#### 4. Config (`src/jarvis/config/`)

A `pydantic-settings`-based config that reads from env vars and `.env`:

- `JARVIS_LOG_LEVEL` (default `INFO`)
- `JARVIS_SUPERVISOR_MODEL` (default chosen by `/system-arch` ADR)
- `JARVIS_MEMORY_STORE_BACKEND` (default `in_memory`; file-backed and Graphiti-backed are future)
- `JARVIS_DATA_DIR` (default `~/.jarvis/`)
- Provider API key slots: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` — read but not required unless the selected model needs them

Config is loaded once at startup, passed explicitly into `build_supervisor` and `SessionManager` — no global state.

#### 5. `jarvis` CLI entrypoint (`src/jarvis/cli/main.py`)

A minimal CLI giving Rich a day-1 conversation surface:

- `jarvis chat` — starts an interactive REPL session using `SessionManager`. Reads stdin, runs `invoke()`, prints supervisor output. Session ends on EOF / `Ctrl-D` / `/exit`.
- `jarvis version` — prints package version.
- `jarvis health` — prints config summary and reports whether the supervisor builds (no LLM call). Useful for early-stage wiring debug.

Implementation uses `click` (same as specialist-agent and Forge) for consistency. No async complexity at the CLI layer — CLI spins an asyncio loop internally for `invoke()`.

No `--scope`, no `--docs`, no `--output`. Those are exploration/generation patterns for agents that produce deliverables; Jarvis *is* the conversation, it doesn't produce artefacts (yet — skills in FEAT-JARVIS-007 change that).

#### 6. Lifecycle hooks (`src/jarvis/infrastructure/lifecycle.py`)

Startup / shutdown orchestration:

- Structured logging configured (structlog, JSON output in non-TTY, console output in TTY)
- Config loaded and validated
- Supervisor built
- SessionManager initialised
- Graceful shutdown on SIGINT / SIGTERM (cancel outstanding sessions, flush Memory Store writes)

Phase 1's lifecycle is deliberately thin — NATS connection lifecycle arrives in FEAT-JARVIS-004, Memory Store persistence in FEAT-JARVIS-007. The shape of the lifecycle module is fixed in Phase 1 so later features extend rather than restructure.

#### 7. Smoke tests (`tests/`)

Sufficient test coverage to prove the scaffold works without over-specifying the supervisor's behaviour (which has a non-deterministic LLM in it):

- `tests/test_config.py` — config loads from env, validation fires on missing required vars, defaults work
- `tests/test_sessions.py` — `SessionManager` creates/resumes/ends sessions, thread IDs are unique, Memory Store integration stores and retrieves across sessions (using `InMemoryStore`)
- `tests/test_supervisor.py` — supervisor builds from config (no LLM call — use `FakeListChatModel` or equivalent); structural assertions on the compiled graph (has expected nodes, expected tools are the DeepAgents built-ins)
- `tests/test_cli.py` — `jarvis version` and `jarvis health` run; `jarvis chat` starts and exits cleanly on EOF (using `CliRunner`)
- `tests/test_smoke_end_to_end.py` — one end-to-end test with a mocked LLM that returns a canned response: CLI starts, user input goes in, supervisor response comes out, session ends. This is the "Rich can have a useful conversation with it" acceptance test at its smallest.

#### 8. `.env.example` and developer README additions

- `.env.example` at repo root listing every env var the config reads, with comments
- `README.md` updated with a "Quickstart" section: clone → `uv sync` → `jarvis chat`. No AutoBuild invocation noise — README stays human-focused.

---

## Do-Not-Change

These are settled and must not drift during Phase 1:

1. **Fleet v3 decisions D40–D46.** Jarvis IS the GPA (D40), flywheel-via-calibration-loop fleet-wide (D41), trace-richness by default (D42), model routing is a reasoning decision (D43), selectively ambient A+B for v1 (D44), meta-agent split deferred (D45), NemoClaw hooks named but not built (D46).
2. **Jarvis-specific preferred directions ADR-J-P1..P10** from `jarvis-architecture-conversation-starter.md` v2. Phase 1 is the first consumer of P1 (DeepAgent with dispatch tools), P3 (thread-per-session with shared Memory Store), P6 (trace-richness from day one — applies at FEAT-JARVIS-004 but the *schema shape* commits now), P10 (`deepagents>=0.5.3,<0.6` pin).
3. **Template-inherited patterns.** The seven orchestrator specialist agents under `.claude/agents/` are not modified; the 15 rules landed at init stay as-is.
4. **Singular topic convention (ADR-SP-016).** Not actually exercised in Phase 1 (no NATS), but any placeholder or planning reference to NATS topics uses singular (`agents.command.*`, not `agents.commands.*`).
5. **Context manifest.** `.guardkit/context-manifest.yaml` stays as landed on 19 April. One observation worth flagging: its `guardkit.installer.core.templates.langchain-deepagents` reference should arguably become `langchain-deepagents-orchestrator` to match the template actually used on 20 April — noted for a later touch-up, not a Phase 1 change.
6. **Pre-existing `docs/research/`, `docs/product/`, `.claude/`, `.guardkit/` trees.** Phase 1 does not disturb these. `docs/product/architect-greenfield/architecture.md` stays where it is (noted as superseded by tomorrow's `/system-arch`, not deleted).
7. **No custom tools.** FEAT-JARVIS-002 is where tools live. Phase 1 supervisor is built-ins-only.
8. **No subagents.** FEAT-JARVIS-003 is where the four async subagents live. Phase 1 supervisor has none.
9. **No NATS.** FEAT-JARVIS-004 and -005 are where NATS wiring lives. Phase 1 has no `nats-py` import, no `nats-core` dependency, no fleet registration.
10. **No adapters.** FEAT-JARVIS-006 is where the Telegram adapter lives. Phase 1 is CLI-only.
11. **No skills.** FEAT-JARVIS-007 is where skills live. Phase 1 supervisor has none.
12. **`jarvis.learning` does not land in Phase 1.** Deferred to v1.5 per the 20 April Q10.2 resolution.

---

## Success Criteria

1. `uv sync` (or `pip install -e ".[dev]"`) succeeds in a clean venv on Rich's MacBook Pro M2 Max.
2. `jarvis version`, `jarvis health`, `jarvis chat` all work from the CLI with no unhandled exceptions.
3. `jarvis chat` with a real supervisor model (Rich's provider of choice, driven by `JARVIS_SUPERVISOR_MODEL`) holds a useful multi-turn conversation — the day-1 success criterion from §14 of the conversation starter.
4. Memory Store round-trip works: fact stated in session A is recalled in session B when the user prompts for it.
5. All Phase 1 smoke tests pass (`pytest tests/ -v` green).
6. Ruff + mypy clean on `src/jarvis/`.
7. `pyproject.toml` pins `deepagents>=0.5.3,<0.6`, and that pin is the one referenced in the `/system-arch`-produced ADR (ADR-J-001 or whatever ID it lands as).
8. The `src/jarvis/` layer structure matches the `langchain-deepagents-orchestrator` template's expected layer boundaries and is explicitly referenced by the `/system-design FEAT-JARVIS-001` output.
9. No regression in pre-existing `.claude/`, `.guardkit/`, `docs/` trees — every file present at `guardkit init` close on 20 April is still present and unchanged.
10. Commit history for FEAT-JARVIS-001 is clean enough to replay — one commit per logical step (scaffold, supervisor, sessions, CLI, tests), not one mega-commit.

---

## Files That Will Change

| File | Change Type |
|------|------------|
| `pyproject.toml` | **NEW** — project metadata, `deepagents>=0.5.3,<0.6` pin, runtime + dev dependencies, `[project.scripts] jarvis` entry, ruff + mypy config |
| `src/jarvis/__init__.py` | **NEW** — package marker + version |
| `src/jarvis/agents/__init__.py` | **NEW** |
| `src/jarvis/agents/supervisor.py` | **NEW** — `build_supervisor(config)` factory |
| `src/jarvis/prompts/__init__.py` | **NEW** |
| `src/jarvis/prompts/supervisor_prompt.py` | **NEW** — minimal supervisor system prompt |
| `src/jarvis/config/__init__.py` | **NEW** |
| `src/jarvis/config/settings.py` | **NEW** — `pydantic-settings` config schema |
| `src/jarvis/infrastructure/__init__.py` | **NEW** |
| `src/jarvis/infrastructure/logging.py` | **NEW** — structlog setup |
| `src/jarvis/infrastructure/lifecycle.py` | **NEW** — startup/shutdown orchestration |
| `src/jarvis/sessions/__init__.py` | **NEW** |
| `src/jarvis/sessions/session.py` | **NEW** — `Session` Pydantic type |
| `src/jarvis/sessions/manager.py` | **NEW** — `SessionManager` + Memory Store integration |
| `src/jarvis/cli/__init__.py` | **NEW** |
| `src/jarvis/cli/main.py` | **NEW** — `jarvis` CLI entrypoint (`chat`, `version`, `health`) |
| `src/jarvis/tools/__init__.py` | **NEW** — empty package (populated by FEAT-JARVIS-002) |
| `src/jarvis/shared/__init__.py` | **NEW** |
| `src/jarvis/shared/constants.py` | **NEW** — version constant, adapter enum |
| `src/jarvis/shared/exceptions.py` | **NEW** — Jarvis-specific exceptions |
| `tests/__init__.py` | **NEW** |
| `tests/conftest.py` | **NEW** — shared fixtures (fake LLM, test config, in-memory store) |
| `tests/test_config.py` | **NEW** — config loading + validation |
| `tests/test_sessions.py` | **NEW** — `SessionManager` lifecycle + Memory Store |
| `tests/test_supervisor.py` | **NEW** — supervisor factory structural tests |
| `tests/test_cli.py` | **NEW** — `jarvis version`/`health`/`chat` CLI tests |
| `tests/test_smoke_end_to_end.py` | **NEW** — CLI → supervisor → response round-trip with mocked LLM |
| `.env.example` | **NEW** — documented env vars |
| `README.md` | **UPDATED** — Quickstart section |
| `.gitignore` | **UPDATED** — `.venv/`, `.env`, `__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `dist/`, `build/` if not already present |
| `docs/architecture/ARCHITECTURE.md` | **NEW** — produced by `/system-arch` (Step 1 of Phase 1 command sequence), not by FEAT-JARVIS-001's build itself |
| `docs/architecture/decisions/ADR-J-001..N.md` | **NEW** — produced by `/system-arch` (Step 1), consumed by FEAT-JARVIS-001 |
| `docs/design/FEAT-JARVIS-001/design.md` | **NEW** — produced by `/system-design FEAT-JARVIS-001` |
| `features/feat-jarvis-001-*/...` | **NEW** — produced by `/feature-spec FEAT-JARVIS-001` |
| `tasks/FEAT-JARVIS-001-*.md` | **NEW** — produced by `/feature-plan FEAT-JARVIS-001` |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/`.

---

## Open Questions `/system-arch` Resolves (for Phase 1's benefit)

Phase 1's build plan command sequence starts with `/system-arch`. The ADRs it produces must include answers to these, otherwise `/feature-spec FEAT-JARVIS-001` is operating on sand:

- **ADR-J-00? — DeepAgents pin.** `deepagents>=0.5.3,<0.6`. Rationale: `AsyncSubAgentMiddleware` preview, per specialist-agent's SDK review (19 April 2026).
- **ADR-J-00? — Supervisor factory.** `create_deep_agent()` vs `create_agent()`. Phase 1's default preference is `create_deep_agent()` (matches Forge's ADR-ARCH-020) but the ADR can revisit.
- **ADR-J-00? — Layer structure.** Exact layer names (`agents/`, `tools/`, `prompts/`, `config/`, `infrastructure/`, `sessions/`, `cli/`, `shared/`). The template provides the shape; the ADR names them.
- **ADR-J-00? — Supervisor model default for Phase 1.** A cheap cloud default is expected; the ADR pins which.
- **ADR-J-00? — Memory Store backend.** `InMemoryStore` for Phase 1; the ADR names the v1.5 graduation path (`InMemoryStore` → file-backed → Graphiti-backed).

Jarvis open questions JA1–JA9 from the conversation-starter v2 are *not* all Phase 1's concern. JA1 (`jarvis_routing_history` schema) lands at FEAT-JARVIS-004. JA3 (cross-adapter handoff) lands at FEAT-JARVIS-006. JA6 (`quick_local` fallback) lands at FEAT-JARVIS-003. JA9 (skill authoring format) lands at FEAT-JARVIS-007. Phase 1's `/system-arch` session may still touch them — but Phase 1's *feature build* depends only on the ADRs listed above.

---

*Scope document: 20 April 2026*
*Input to: `/system-arch` (Step 1 of the Phase 1 build plan), then `/feature-spec FEAT-JARVIS-001`*
*"Rich can have a useful conversation with it on day 1, even if it can't dispatch to anything yet."*
