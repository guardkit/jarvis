# Phase 1 Build Plan — Project Scaffolding, Supervisor Skeleton & Session Lifecycle

## For: Laying the foundation for v1 Jarvis — the attended DeepAgent with dispatch tools. Every subsequent feature in v1 (FEAT-JARVIS-002..007) compounds on this one.
## Date: 20 April 2026
## Status: `guardkit init` complete (20 April). `/system-arch` **complete** (21 April) — 30 ADRs `ADR-ARCH-001..030`, C4 (`system-context.md`, `container.md`), `domain-model.md`, `ARCHITECTURE.md`, `assumptions.yaml`. `/system-design FEAT-JARVIS-001` **complete** (21 April) — `docs/design/FEAT-JARVIS-001/` (`design.md`, `diagrams/`, `contracts/`, `decisions/`, `models/`), C4 L3 diagram approved, Graphiti seeding landed. `/feature-spec FEAT-JARVIS-001` **complete** (21 April) — `features/project-scaffolding-supervisor-sessions/` (35 scenarios across 7 groups; 6 assumptions all confirmed; `review_required: false`). `/feature-plan FEAT-JARVIS-001` **complete** (21 April) — 11 subtasks across 6 waves in `tasks/backlog/project-scaffolding-supervisor-sessions/`, structured YAML at `.guardkit/features/FEAT-JARVIS-001.yaml`, IMPLEMENTATION-GUIDE.md with data-flow + integration-contract + task-dependency Mermaid diagrams + §4 Integration Contracts. AutoBuild (Step 5) **complete** (21 April, ~57 min wall-clock) — all 11 tasks Player→Coach approved (10 in one turn, TASK-J001-002 in two turns after a src-layout sys.path fix). `/task-review FEAT-JARVIS-001` (Step 6) **complete** (22 April) — score 82/100, decision `revise → [I]mplement`. Report at `.claude/reviews/FEAT-JARVIS-001-review-report.md`; 4 remediation subtasks across 2 waves landed in `tasks/backlog/phase1-review-fixes/`. Phase 1 review-fixes wave (FIX-001..004) **complete** (22 April) — FIX-001 mypy-clean on `src/jarvis/`, FIX-002 Python 3.12 pin + dev deps moved to PEP 735 `[dependency-groups].dev` (bare `uv sync` now hydrates `.venv/bin/pytest`; `test_returns_compiled_state_graph` patched with `fake_llm` per AC-001 "no network"), FIX-003 `AppState` typing + logging moved to CLI entry, FIX-004 cosmetic polish (F5/F6/F8). Step 7 regression check **complete** (22 April) — `uv run pytest` 341/341 pass, `uv run ruff check` clean, `uv run mypy src/jarvis/` clean (0 errors in 26 files), coverage 90%. Success Criteria #5 + #6 now met. Step 8 day-1 validation (22 April) surfaced two late bugs — (a) `.env` was ignored by langchain because `JarvisConfig` reads it via pydantic-settings which does not export to `os.environ` (fix: `load_dotenv(override=False)` bridge at CLI entry + autouse conftest chdir for test isolation), and (b) within-session multi-turn recall was broken because `build_supervisor` compiled the graph without a checkpointer, making `SessionManager`'s `thread_id` plumbing a no-op (fix: `checkpointer=InMemorySaver()` + `TestWithinSessionRecall` ×4, captured as TASK-J001-FIX-005). Test count 341 → 348. Live `uv run jarvis chat` now holds multi-turn context on `openai:gpt-4o-mini`. Cross-session recall (#4 as originally written) still requires a persistent saver + persistent store, legitimately deferred to FEAT-JARVIS-007. **Next: Phase 1 closeout — commit the FIX-005 + .env-bridge change, push to `origin/main`, move to FEAT-JARVIS-002 (dispatch tools, Phase 2).**
## Repo: `guardkit/jarvis`
## Machine: MacBook Pro M2 Max (planning + build via Claude Code)

---

## Status Log

| Date | Step | Outcome |
|------|------|---------|
| 2026-04-19 | `.guardkit/context-manifest.yaml` landed | Cross-repo dependency map for Jarvis — references `nats-core`, `forge` (incl. fleet v3 + ADR-FLEET-001), `specialist-agent`, `nats-infrastructure`, `guardkit`. Internal always-include list: `jarvis-vision.md` v2, `jarvis-architecture-conversation-starter.md` v2. |
| 2026-04-19 | Fleet v3 keystone doc accepted | `fleet-architecture-v3-coherence-via-flywheel.md` with D40-D46 becomes the framing document for Jarvis v1 scope. |
| 2026-04-19 | ADR-FLEET-001 (trace-richness) accepted | Fleet-wide trace schema commitment. Constrains `jarvis_routing_history` from FEAT-JARVIS-004 onward. |
| 2026-04-19 | `jarvis-vision.md` v2 written | Rewritten from "thin router with GPA as specialist" → "DeepAgent with dispatch tools". |
| 2026-04-19 | `jarvis-architecture-conversation-starter.md` v2 written | Produced ADR-J-P1..P10 preferred directions + JA1..JA9 open questions for `/system-arch`. |
| 2026-04-20 | `guardkit init langchain-deepagents-orchestrator` executed | Landed `.claude/` (14 agent files, 15 rules, CLAUDE.md, commands, manifest, rules, task-plans), `.guardkit/.mcp.json`, `.guardkit/graphiti.yaml`, `CLAUDE.md` (root). No `src/`, `tests/`, `pyproject.toml` — those defer to FEAT-JARVIS-001 per the 20 April reframing. Graphiti seeding skipped (`GOOGLE_API_KEY` not set). |
| 2026-04-20 | `jarvis-build-plan-conversation-starter.md` revised | 20 April decisions captured: FEAT-JARVIS-008 (learning) deferred to v1.5, FEAT-JARVIS-006 narrowed to Telegram-only, scaffolding absorbed into FEAT-JARVIS-001, `talk-prep` Pattern C slot reserved, `jarvis purge-traces` deferred to v1.1. Timeline revised to 11–12 working days. |
| 2026-04-20 | `phase1-supervisor-scaffolding-scope.md` written | This document's companion scope doc — input to `/feature-spec FEAT-JARVIS-001`. |
| 2026-04-20 | `phase1-build-plan.md` written | This document. |
| 2026-04-21 | `/system-arch` **complete** (Step 1) | Commit `2e96b24`. Produced `docs/architecture/ARCHITECTURE.md`, `system-context.md`, `container.md`, `domain-model.md`, `assumptions.yaml`, and **30 ADRs** `ADR-ARCH-001..030` (actual IDs, not the tentative `ADR-J-001..N`). Key ADRs for Phase 1: `ADR-ARCH-001` (local-first inference via llama-swap), `ADR-ARCH-002` (clean hexagonal in DeepAgents supervisor), `ADR-ARCH-003` (Jarvis is the GPA), `ADR-ARCH-005` (seven bounded contexts), `ADR-ARCH-006` (five-group module layout — supersedes the eight-layer sketch in this plan), `ADR-ARCH-009` (thread-per-session with Memory Store summary bridge), `ADR-ARCH-010` (Python 3.12 + DeepAgents pin), `ADR-ARCH-011` (single Jarvis reasoner subagent), `ADR-ARCH-015` (CI: ruff + mypy + pytest), `ADR-ARCH-020` (trace-richness by default), `ADR-ARCH-025` (DeepAgents 0.6 upgrade gated). Session transcript: `docs/history/system-arch-history.md`. |
| 2026-04-21 | `/system-design FEAT-JARVIS-001` **complete** (Step 2) | Commits `b259206` (design artefacts) and `7c8cdeb` (C4 L3 diagram approval). Produced `docs/design/FEAT-JARVIS-001/design.md` plus `diagrams/`, `contracts/`, `decisions/`, `models/` subtrees. Approval gate passed; Graphiti seeding completed. Session transcript: `docs/history/system-design-history.md`. |
| 2026-04-21 | Design artefacts + approval + Graphiti seeding landed | FEAT-JARVIS-001 design phase closed. Branch is 4 commits ahead of `origin/main`, nothing pushed. Ready for Step 3 (`/feature-spec FEAT-JARVIS-001 --context docs/design/FEAT-JARVIS-001/design.md ...`). |
| 2026-04-21 | `/feature-spec FEAT-JARVIS-001` **complete** (Step 3) | Produced `features/project-scaffolding-supervisor-sessions/` — `project-scaffolding-supervisor-sessions.feature` (35 scenarios across 7 groups: 8 @key-example, 7 @boundary, 8 @negative, 12 @edge-case incl. 3 @security / 2 @concurrency / 2 @integration; 6 @smoke, 3 @regression), `_assumptions.yaml` (6 assumptions — 4 medium, 2 low — all confirmed), `_summary.md`. All four initial Propose-Review groups + all three edge-case-expansion sub-groups (security/concurrency/integration) accepted. Defaults taken for all 6 assumptions, with ASSUM-002 (`/exit` matching) and ASSUM-003 (concurrent invoke refusal) explicitly re-reviewed and signed off — `review_required: false`. Two tentative `ADR-J-*` paths in the original invocation were automatically mapped to actual `ADR-ARCH-*` IDs; two unreachable `--context` paths (`../forge/src/forge/cli/main.py`, `../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md`) were skipped without harm. Ready for Step 4 (`/feature-plan FEAT-JARVIS-001`). |
| 2026-04-21 | Phase 5 design decisions pinned via assumption resolution | Six previously-unstated behaviours became part of the specification contract: (1) ASSUM-001 blank-line chat turn is silently skipped; (2) ASSUM-002 `/exit` is case-sensitive lowercase with whitespace trimmed; (3) ASSUM-003 concurrent `invoke` on the same session is refused with a clear error (not silently serialised); (4) ASSUM-004 REPL reads the next stdin line only after the prior reply is printed; (5) ASSUM-005 `pydantic.ValidationError` at config load exits the CLI with code 1 (same as `ConfigurationError`); (6) ASSUM-006 non-CLI adapters (`telegram`/`dashboard`/`reachy`) raise `JarvisError` from `SessionManager.start_session`. These pins are load-bearing for Step 4 task decomposition and Step 5 AutoBuild — do not re-litigate without updating the feature file. |
| 2026-04-22 | `/task-review FEAT-JARVIS-001` **complete** (Step 6) | Architectural post-build review (standard depth, focus=all, tradeoff=balanced). Quality gates: `pytest` 340/341 pass, `ruff` clean on `src/jarvis/`, `mypy` 5 errors on `src/jarvis/`. **Score 82/100.** All six ASSUM-* pins + DDR-002/003/004 verified in code; scope invariants clean (no NATS/Telegram/Graphiti/subagent/custom-tool imports; 8 reserved packages stubbed). 8 findings: 2 HIGH (mypy, env-fragile test — block Success Criteria #5/#6), 2 MEDIUM (`AppState.Any` + stale comments; logging configured after config validation), 4 LOW (`correlation_id` ULID-vs-UUID docstring drift, 7 ruff errors in `tests/`, implicit asyncio-single-loop concurrency model, function-scoped `HumanMessage` import). Decision: `[I]mplement` — 4 remediation subtasks created at `tasks/backlog/phase1-review-fixes/` across 2 parallel waves, ~75 min sequential / ~50 min wall-clock. Review report: `.claude/reviews/FEAT-JARVIS-001-review-report.md`. |
| 2026-04-21 | `/feature-plan FEAT-JARVIS-001` **complete** (Step 4) | Review task `TASK-REV-J001` created (decision=implement) and moved to `tasks/in_review/`. Produced `tasks/backlog/project-scaffolding-supervisor-sessions/` — README.md, IMPLEMENTATION-GUIDE.md (with mandatory Data Flow, Integration Contract sequence, and Task Dependency Mermaid diagrams + §4 Integration Contracts for `SUPERVISOR_MODEL_ENDPOINT`, `COMPILED_SUPERVISOR_GRAPH`, `APP_STATE`), and 11 subtask files `TASK-J001-001..011`. Structured YAML at `.guardkit/features/FEAT-JARVIS-001.yaml` with 6-wave orchestration (waves 1/2/3/6 parallel; waves 4/5 serial; pre-flight caught an intra-wave-5 dependency and split into waves 5+6 before AutoBuild). Context A defaults (all/standard/balanced/extensibility=yes); Context B recommended-path / auto-detect / standard-testing. |
| 2026-04-21 | AutoBuild FEAT-JARVIS-001 **complete** (Step 5) | All 11 tasks ran Player→Coach under `guardkit autobuild` in a single worktree (`.guardkit/worktrees/FEAT-JARVIS-001`), wave-ordered, 22:31–23:28 (~57 min wall-clock — well inside the 3–4-day budget). Ten tasks approved in one turn. TASK-J001-002 took two turns: Turn 1 passed lint/mypy/format but the coach's test runner ran `pytest` without an editable install in a src-layout project, so every test failed with `ModuleNotFoundError: No module named 'jarvis'`; Turn 2 added `tests/conftest.py` that prepends `<project-root>/src` to `sys.path` at pytest startup (the standard src-layout fix) and all 29 tests passed. Every task is currently `status: in_review` with `player_success: true` and `coach_success: true`. |
| 2026-04-22 | Phase 1 review-fixes wave **complete** (FIX-001..004) | All four remediation subtasks from `tasks/backlog/phase1-review-fixes/` landed: FIX-001 mypy-clean on `src/jarvis/` (commit `2fc9ab7`); FIX-002 Python 3.12 pin + `test_jarvis_version_command` env-stabilisation (commit `84daf08` — additionally moved dev deps from `[project.optional-dependencies].dev` to PEP 735 `[dependency-groups].dev` so bare `uv sync` now hydrates `.venv/bin/pytest`, closing the root cause of why `uv run pytest` was falling through to the system 3.14 interpreter; also patched `test_returns_compiled_state_graph` with the `fake_llm` fixture to honour AC-001 "no network"); FIX-003 tightened `AppState` typing + moved structlog configuration into the CLI entry path; FIX-004 cosmetic polish (correlation_id docstring, HumanMessage import hoist, ruff-fix on `tests/` — commit `b82bd72`). |
| 2026-04-22 | Step 7 regression check **complete** | Phase 1 regression gate green on a clean `.venv`: `rm -rf .venv && uv sync && uv run pytest` yields **341/341 passing**, `uv run ruff check src/jarvis/ tests/` clean, `uv run mypy src/jarvis/` clean (0 errors in 26 files), coverage 90%. The two HIGH findings from `/task-review` (mypy + env-fragile pytest) are closed; Success Criteria #5 ("all Phase 1 smoke tests pass") and #6 ("ruff + mypy clean on `src/jarvis/`") now both met. FEAT-JARVIS-001 is ready for merge/push and Phase 1 is effectively closed — the remaining pre-existing uncommitted edits in `src/jarvis/cli/main.py` and `src/jarvis/infrastructure/` are the FIX-003 bootstrap refactor awaiting a separate commit. |
| 2026-04-22 | Step 8 day-1 validation surfaced 2 late bugs → **FIX-005 + .env bridge** landed | Live `uv run jarvis chat` exposed two gaps no test caught: (1) `.env` was populated but ignored by langchain's OpenAI client — `JarvisConfig` reads `.env` via pydantic-settings but that does NOT export to `os.environ`, so `init_chat_model` failed with "api_key must be set" despite the key being on disk; fix is a `load_dotenv(override=False)` bridge at the Click group callback plus an autouse conftest fixture (`_isolate_dotenv`) that chdirs tests to a tmp dir so pydantic's relative `env_file=".env"` can't absorb the operator's real `.env` during test runs. (2) Within-session multi-turn recall was broken — `build_supervisor` called `create_deep_agent(...)` without a `checkpointer=` kwarg, so `SessionManager`'s `thread_id` plumbing had no saver to key against and every turn started from a blank slate; fix is `checkpointer=InMemorySaver()` + a new `TestWithinSessionRecall` class (4 regression guards) captured as TASK-J001-FIX-005. Test count: 341 → 344 (`TestDotenvBridge` ×3) → **348** (`TestWithinSessionRecall` ×4). |
| 2026-04-22 | Step 8 day-1 conversation **complete** | Live multi-turn conversation via `uv run jarvis chat` against `openai:gpt-4o-mini`: supervisor holds context across turns within a session (DDD Southwest talk fact recalled after FIX-005 landed), `/exit` closes cleanly. Cross-session recall remains deferred to FEAT-JARVIS-007 (requires a persistent checkpointer + persistent store) — Phase 1 Success Criterion #4 is partially met as written; the within-session half is done and the cross-session half is a documented FEAT-JARVIS-007 responsibility. Phase 1 is now functionally closed. |

---

## What Phase 1 IS

The foundation phase: project scaffolding (`pyproject.toml`, `src/jarvis/` layer structure, `tests/`), supervisor skeleton (`create_deep_agent()`- or `create_agent()`-produced DeepAgent with DeepAgents built-ins only), session lifecycle (thread-per-session per ADR-J-P3, Memory Store for cross-session recall), `jarvis` CLI entrypoint (`chat`/`version`/`health`), and enough smoke tests to prove the shell is structurally sound.

This is the 3–4-day pressure valve that converts the 20 April decisions — `guardkit init` landed, DeepAgents pin settled, scaffolding absorbed into the feature — into a runnable skeleton. The "useful conversation on day 1" success criterion from §14 of the conversation starter lands here.

Phase 1 is a *precondition* for every other v1 feature. Dispatch tools (002), async subagents (003), NATS specialist dispatch (004), Forge queue dispatch (005), Telegram adapter (006), skills + Memory Store (007) all sit on top of Phase 1's foundation. Getting this right is the single most leveraged Phase in v1.

## What Phase 1 IS NOT

- Not the dispatch tools (that's FEAT-JARVIS-002, Phase 2).
- Not the four async subagents (`deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local` — FEAT-JARVIS-003, Phase 2).
- Not NATS fleet registration or specialist dispatch (FEAT-JARVIS-004, Phase 3).
- Not Forge build-queue dispatch (FEAT-JARVIS-005, Phase 3).
- Not the Telegram adapter (FEAT-JARVIS-006, Phase 4).
- Not skills (FEAT-JARVIS-007, Phase 4).
- Not the learning flywheel (FEAT-JARVIS-008, deferred to v1.5).
- Not Pattern C ambient behaviours (FEAT-JARVIS-010, v1.5).
- Not `jarvis purge-traces` (FEAT-JARVIS-011, v1.1).

## Success Criteria

1. `uv sync` succeeds in a clean venv on the MacBook Pro M2 Max (installs runtime deps + `[dependency-groups].dev`).
2. `jarvis version`, `jarvis health`, `jarvis chat` work without unhandled exceptions.
3. `jarvis chat` holds a useful multi-turn conversation with a real supervisor model — the day-1 criterion.
4. Memory Store round-trips: within a single `jarvis chat` session, a fact stated on turn N is recallable on turn N+K (closed by FIX-005's `InMemorySaver` wiring). **Cross-session recall** (fact stated in session A, recalled in a later session B for the same user) requires a persistent checkpointer + persistent store and is legitimately deferred to FEAT-JARVIS-007 — Phase 1 deliberately ships with `in_memory` only per `.env.example` / ADR.
5. All Phase 1 smoke tests pass.
6. Ruff + mypy clean on `src/jarvis/`.
7. `pyproject.toml` pins `deepagents>=0.5.3,<0.6`, matching the `/system-arch`-produced ADR.
8. `src/jarvis/` layer structure matches the `langchain-deepagents-orchestrator` template and the `/system-design FEAT-JARVIS-001` output.
9. No regression in pre-existing `.claude/`, `.guardkit/`, `docs/` trees (everything that landed at `guardkit init` close on 20 April stays present and unchanged).
10. FEAT-JARVIS-001 commit history is clean enough to replay (one commit per logical step, not one mega-commit).

---

## Pre-Phase-1 Context

**Fleet substrate state (19–20 April 2026):**

- `nats-core` shipping, 98% coverage, production-used by Forge and specialist-agent
- `nats-infrastructure` configured (not yet running on GB10 — not a Phase 1 blocker)
- Forge: 30 ADRs + ARCHITECTURE.md shipping, ADR-ARCH-031 (async subagents) amended 19 April
- specialist-agent: shipping; Phase 3 (NATS fleet integration) in progress
- Study Tutor: runnable; not a Phase 1 dependency
- Fleet-wide decisions D1–D46 resolved (D40–D46 new from fleet v3)
- ADR-FLEET-001 (trace-richness) accepted
- DeepAgents 0.5.3 released 15 April 2026 — `AsyncSubAgentMiddleware` preview feature confirmed live (per specialist-agent SDK review 19 April)

**Gaps identified that Phase 1 closes:**

| Gap | Impact | Source |
|-----|--------|--------|
| No Python scaffold post-`guardkit init` | Blocks every other v1 feature — nothing is importable or testable | Observed 20 April `guardkit init` output (§1.6 of conversation starter) |
| No `pyproject.toml` with DeepAgents 0.5.3 pin | Supervisor cannot be built, `AsyncSubAgentMiddleware` unavailable to FEAT-JARVIS-003 | 20 April reframing (§0 intro, §1 pin requirement) |
| No session lifecycle | No thread-per-session, no Memory Store integration, cross-session recall impossible | ADR-J-P3 (conversation starter v2) |
| No CLI surface | Rich cannot have a day-1 conversation — blocks attended-surface value proposition | §14 parting thought ("useful conversation before anything fancy works") |
| No smoke tests | No structural floor for subsequent features — regressions slip in silently | Lesson from Forge build + specialist-agent build |

---

## Feature Summary

| # | Feature | Depends On | Est. Complexity | Priority |
|---|---------|-----------|-----------------|----------|
| FEAT-JARVIS-001 | Project Scaffolding, Supervisor Skeleton & Session Lifecycle | `guardkit init` (✅), `/system-arch` outputs (pending) | Medium-High (broad surface, low per-piece complexity) | **Foundational** (blocks 002..007) |

**Dependency graph:**

```
guardkit init (✅ 20 April 2026) + ADR-FLEET-001 (✅)
         │
         ▼
/system-arch (pending, 21 April 2026)
         │  produces ARCHITECTURE.md, C4, ADR-J-001..N (incl. DeepAgents pin ADR, supervisor factory ADR)
         ▼
FEAT-JARVIS-001 (this phase)
         │
         ├──→ FEAT-JARVIS-002 (core tools + dispatch tools) ─── Phase 2
         ├──→ FEAT-JARVIS-003 (async subagents) ──────────────── Phase 2
         ├──→ FEAT-JARVIS-006 (Telegram adapter) ─────────────── Phase 4 (depends only on 001)
         └──→ FEAT-JARVIS-007 (skills + Memory Store) ────────── Phase 4 (depends only on 001)

         (FEAT-JARVIS-004, -005 depend on FEAT-JARVIS-002 → Phase 3)
```

FEAT-JARVIS-001 is the single gating feature for all of v1.

---

## FEAT-JARVIS-001: Project Scaffolding, Supervisor Skeleton & Session Lifecycle

**Purpose:** Establish the runnable skeleton of Jarvis. Python project scaffold, DeepAgents 0.5.3 supervisor, thread-per-session model with Memory Store, `jarvis` CLI, enough tests to prove the shell works. Day-1 Rich-has-a-conversation criterion met.

### Change 1: `pyproject.toml` + project metadata

**File:** `pyproject.toml` (NEW)

Minimal but template-faithful project file:

- `[project]`: `name = "jarvis"`, description from `CLAUDE.md`, `requires-python = ">=3.12"`, authors
- `[project.dependencies]`:
  - `deepagents>=0.5.3,<0.6` — **the pin from the `/system-arch` ADR**. Matches specialist-agent's SDK review (19 April) and is the minimum version with `AsyncSubAgentMiddleware` preview. Upper bound guards against preview-API changes in 0.6.
  - `langchain-core`, `langgraph>=0.3`, `pydantic>=2`, `pydantic-settings`, `structlog`, `python-dotenv`, `click`
  - Provider-specific model packages that the selected supervisor model needs (added as `/system-arch` pins the default model)
  - **Not added in Phase 1:** `nats-py`, `nats-core` (arrives at FEAT-JARVIS-004), `graphiti-core` (arrives at the Graphiti integration feature, v1.5), Telegram SDK (FEAT-JARVIS-006)
- `[dependency-groups].dev` (PEP 735): `pytest>=8`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `types-*` as needed — installed by default on bare `uv sync`.
- `[project.scripts]`: `jarvis = "jarvis.cli.main:main"`
- `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` — config matching specialist-agent's style (line length 100, strict mypy, `asyncio_mode = "auto"`, coverage config)
- `[build-system]`: `hatchling` (same as Forge + specialist-agent)

### Change 2: `src/jarvis/` package structure

**Files (NEW):**

- `src/jarvis/__init__.py` — `__version__ = "0.1.0"`
- `src/jarvis/shared/__init__.py`
- `src/jarvis/shared/constants.py` — `DEFAULT_ADAPTER`, `VERSION`, adapter enum
- `src/jarvis/shared/exceptions.py` — `JarvisError`, `SessionNotFoundError`, `ConfigurationError`

This layer is the "safe to import from anywhere" tier — no dependencies on supervisor, sessions, config, or I/O.

### Change 3: Config module (`src/jarvis/config/`)

**Files (NEW):**

- `src/jarvis/config/__init__.py`
- `src/jarvis/config/settings.py` — `JarvisConfig(BaseSettings)` with:

```python
class JarvisConfig(BaseSettings):
    log_level: str = "INFO"
    supervisor_model: str  # default from /system-arch ADR
    memory_store_backend: Literal["in_memory", "file", "graphiti"] = "in_memory"
    data_dir: Path = Path.home() / ".jarvis"

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
```

- Loaded once at startup, passed explicitly — no global state.
- Validation: config raises `ConfigurationError` (clear message) if the selected supervisor model requires a provider key that isn't set.

### Change 4: Prompts module (`src/jarvis/prompts/`)

**Files (NEW):**

- `src/jarvis/prompts/__init__.py`
- `src/jarvis/prompts/supervisor_prompt.py` — `SUPERVISOR_SYSTEM_PROMPT: str` constant

Phase 1's supervisor prompt is minimal-but-correct:

- States Jarvis's purpose (general purpose DeepAgent for Rich, attended conversation surface)
- States the "cheapest-that-fits, escalate on need" preference (dormant until FEAT-JARVIS-003 ships subagents)
- States the attended-conversation posture ("you are always in a conversation with a human; they are in the loop")
- Does **not** yet teach dispatch to specialists or build queue (that prompt surface area lands at FEAT-JARVIS-002 and -004)
- Does **not** yet teach skill invocation (lands at FEAT-JARVIS-007)

Later features *extend* this prompt (add sections). They do not rewrite it from scratch.

### Change 5: Supervisor factory (`src/jarvis/agents/`)

**Files (NEW):**

- `src/jarvis/agents/__init__.py`
- `src/jarvis/agents/supervisor.py` — `build_supervisor(config: JarvisConfig) -> CompiledStateGraph`

The factory:

- Selects `create_deep_agent()` or `create_agent()` per the `/system-arch` ADR (Phase 1 default preference: `create_deep_agent()`, matching Forge's ADR-ARCH-020)
- Passes `model=config.supervisor_model`
- Passes the supervisor system prompt from `prompts.supervisor_prompt`
- Enables DeepAgents built-ins: `write_todos`, virtual filesystem, `task`. `execute` is disabled (no shell access in Phase 1 — FEAT-JARVIS-002 may enable it with a sandbox policy from the relevant ADR).
- Does **not** add subagents (FEAT-JARVIS-003's job)
- Does **not** add custom tools (FEAT-JARVIS-002's job)
- Wires the Memory Store into the compiled graph per DeepAgents 0.5.3 pattern

### Change 6: Sessions (`src/jarvis/sessions/`)

**Files (NEW):**

- `src/jarvis/sessions/__init__.py`
- `src/jarvis/sessions/session.py` — `Session(BaseModel)` with `session_id`, `adapter`, `user_id`, `thread_id`, `started_at`, `correlation_id`, `metadata`
- `src/jarvis/sessions/manager.py` — `SessionManager`:

```python
class SessionManager:
    def __init__(self, supervisor: CompiledStateGraph, store: BaseStore):
        self._supervisor = supervisor
        self._store = store
        self._sessions: dict[str, Session] = {}

    def start_session(self, adapter: Adapter, user_id: str) -> Session: ...
    def resume_session(self, session_id: str) -> Session: ...
    def end_session(self, session_id: str) -> None: ...

    async def invoke(self, session: Session, user_input: str) -> str:
        config = {"configurable": {"thread_id": session.thread_id}}
        result = await self._supervisor.ainvoke(
            {"messages": [HumanMessage(user_input)]},
            config=config,
            store=self._store,
        )
        return result["messages"][-1].content
```

- `BaseStore` is LangGraph's Memory Store interface; Phase 1 uses `InMemoryStore`.
- Thread IDs unique per session; Memory Store keyed by `user_id` so recall works across sessions for the same user.
- **No NATS wiring.** CLI is the only adapter in Phase 1; future adapters hook in via the same `start_session(adapter=...)` signature.

### Change 7: Infrastructure (`src/jarvis/infrastructure/`)

**Files (NEW):**

- `src/jarvis/infrastructure/__init__.py`
- `src/jarvis/infrastructure/logging.py` — structlog setup (JSON in non-TTY, console in TTY)
- `src/jarvis/infrastructure/lifecycle.py` — `async def startup(config) -> AppState` and `async def shutdown(state) -> None`

`AppState` holds `config`, `supervisor`, `store`, `session_manager`. Lifecycle is deliberately thin — NATS connection lifecycle arrives in FEAT-JARVIS-004; the *shape* of the lifecycle module is fixed in Phase 1 so later features extend rather than restructure.

Shutdown hooks: cancel outstanding sessions, flush Memory Store writes, log a clean shutdown message.

### Change 8: CLI (`src/jarvis/cli/`)

**Files (NEW):**

- `src/jarvis/cli/__init__.py`
- `src/jarvis/cli/main.py` — click-based CLI:

```python
@click.group()
def main(): ...

@main.command()
def version(): ...

@main.command()
def health(): ...  # load config, attempt to build supervisor (no LLM call), print summary

@main.command()
def chat(): ...  # REPL: read stdin, SessionManager.invoke, print, loop until EOF
```

- `chat` internally creates an asyncio loop (no async complexity exposed to the user)
- Session ends cleanly on EOF, `Ctrl-D`, or `/exit`
- All three commands respect `JARVIS_LOG_LEVEL`
- Implementation patterns mirror specialist-agent's `cli/main.py` for family resemblance

### Change 9: `tools/` empty package

**File:** `src/jarvis/tools/__init__.py` (NEW, empty module)

Reserves the namespace. FEAT-JARVIS-002 populates it with `call_specialist`, `queue_build`, file read, web search stub, etc. Creating the package in Phase 1 means 002 doesn't have to also create the parent directory and worry about import path ordering.

### Change 10: Smoke tests (`tests/`)

**Files (NEW):**

- `tests/__init__.py`
- `tests/conftest.py` — shared fixtures:
  - `fake_llm` — `FakeListChatModel` with canned responses for deterministic tests
  - `test_config` — `JarvisConfig` with sensible defaults + in-memory store
  - `in_memory_store` — fresh `InMemoryStore` per test
- `tests/test_config.py` — env var loading, default values, missing-key validation error
- `tests/test_sessions.py` — `SessionManager.start_session()` returns unique thread IDs, `resume_session()` finds the existing session, Memory Store write-in-session-A → read-in-session-B works, `end_session()` cleans up
- `tests/test_supervisor.py` — `build_supervisor(test_config)` returns a `CompiledStateGraph`; structural assertions on nodes + tools (DeepAgents built-ins present, no subagents, no custom tools); **no LLM calls** (use `fake_llm` fixture)
- `tests/test_cli.py` — `jarvis version` prints version and exits 0; `jarvis health` prints summary and exits 0; `jarvis chat` starts and exits cleanly on EOF (using `CliRunner`)
- `tests/test_smoke_end_to_end.py` — CLI start → user input → mocked LLM response → output printed → session ends. The smallest possible "Rich-can-have-a-conversation" acceptance test.

Target: **30–40 tests.** Enough to cover the scaffold; not so many that they over-specify what later features will change.

### Change 11: Developer surface (`.env.example`, `README.md`)

**Files (UPDATED / NEW):**

- `.env.example` (NEW) — documented env vars with comments
- `README.md` (UPDATED) — Quickstart section: `clone → uv sync → jarvis chat`, not a comprehensive manual. `.gitignore` checked for `.venv/`, `.env`, `__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `dist/`, `build/`.

### Invariants (must not change)

- All fleet v3 D40–D46 decisions stand — no re-litigation in Phase 1.
- ADR-J-P1..P10 preferred directions stand.
- `.claude/`, `.guardkit/` trees untouched — orchestrator specialist agents, rules, graphiti.yaml all stay.
- Pre-existing `docs/research/`, `docs/product/` trees untouched (`docs/product/architect-greenfield/architecture.md` flagged-as-superseded by `/system-arch` output but not deleted).
- No NATS imports. No Telegram imports. No Graphiti imports. No subagent definitions. No custom tools.
- Supervisor system prompt is *minimal* — the "cheapest-that-fits" preference is stub-present but dispatch/skill/subagent guidance is deferred.

---

## GuardKit Command Sequence

### Step 1: /system-arch — produce Jarvis architecture ✅ COMPLETE (21 April 2026)

**Completed 21 April 2026** (commit `2e96b24`). Session transcript: `docs/history/system-arch-history.md`. Delivered: `docs/architecture/ARCHITECTURE.md`, `system-context.md`, `container.md`, `domain-model.md`, `assumptions.yaml`, and 30 ADRs `ADR-ARCH-001..030` (under `docs/architecture/decisions/`). The actual ADR namespace is `ADR-ARCH-*`, not the tentative `ADR-J-*` used elsewhere in this plan — downstream Step 3/4 `--context` lists below should be read with that substitution in mind. The original Step 1 invocation is preserved below for traceability.

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis

/system-arch "Jarvis: General Purpose DeepAgent with dispatch tools — attended surface of the three-surface fleet" \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-build-plan-conversation-starter.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/general-purpose-agent.md \
  --context docs/research/ideas/reachy-mini-integration.md \
  --context docs/research/ideas/nemoclaw-assessment.md \
  --context ../forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-015-capability-driven-dispatch.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-016-fleet-is-the-catalogue.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-019-no-static-behavioural-config.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md \
  --context ../forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md \
  --context ../forge/docs/research/forge-pipeline-architecture.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context .guardkit/context-manifest.yaml
```

**Watch-points for `/system-arch`** (per conversation starter §7):

- May re-open D11 (intent classification) or D12 (GPA location) — both resolved by D40. Hold the line.
- May propose meta-agent split — D45 defers. Hold the line.
- May propose static gate/threshold config — ADR-ARCH-019 inherited. Hold the line.
- May propose polling for Jarvis status — redirect to `list_async_tasks` (DeepAgents 0.5.3 primitive).

**Expected Step 1 outputs:**

- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/context-diagram.md` + `container-diagram.md` (Mermaid C4)
- `docs/architecture/decisions/ADR-J-001-deepagents-pin.md` (pin `>=0.5.3,<0.6`)
- `docs/architecture/decisions/ADR-J-002-supervisor-factory.md` (`create_deep_agent` vs `create_agent`)
- `docs/architecture/decisions/ADR-J-003-layer-structure.md`
- `docs/architecture/decisions/ADR-J-004-supervisor-model-default.md`
- `docs/architecture/decisions/ADR-J-005-memory-store-backend.md`
- Additional ADRs covering ADR-J-P1..P10 preferred directions + responses to JA1..JA9
- `docs/architecture/ddd-context-map.md`

(ADR numbering is tentative — `/system-arch` may reorder.)

After Step 1, **update this build plan's Status Log** with the actual ADR IDs before proceeding to Step 2. *(Done 21 April — actual IDs are `ADR-ARCH-001..030`; see Status Log above.)*

### Step 2: /system-design FEAT-JARVIS-001 ✅ COMPLETE (21 April 2026)

**Completed 21 April 2026** (commits `b259206` + `7c8cdeb`). Session transcript: `docs/history/system-design-history.md`. Delivered: `docs/design/FEAT-JARVIS-001/design.md` plus `diagrams/`, `contracts/`, `decisions/`, `models/` subtrees. C4 L3 diagram approved; Graphiti seeding landed. The original Step 2 invocation is preserved below for traceability — note that the context list should be read against the actual `ADR-ARCH-*` files (not the tentative `ADR-J-*` names).

```bash
/system-design FEAT-JARVIS-001 \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/architecture/decisions/ADR-J-004-supervisor-model-default.md \
  --context docs/architecture/decisions/ADR-J-005-memory-store-backend.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context ../forge/docs/architecture/ARCHITECTURE.md \
  --context ../specialist-agent/pyproject.toml \
  --context ../forge/pyproject.toml \
  --context .guardkit/context-manifest.yaml
```

Expected output: `docs/design/FEAT-JARVIS-001/design.md` — component boundaries for the eight layers (`agents/`, `tools/`, `prompts/`, `config/`, `infrastructure/`, `sessions/`, `cli/`, `shared/`), the `Session` type's exact Pydantic fields, the `SessionManager` interface, the `build_supervisor` factory signature, the `JarvisConfig` schema, test fixture boundaries.

### Step 3: /feature-spec FEAT-JARVIS-001 ✅ COMPLETE (21 April 2026)

**Completed 21 April 2026.** Delivered: `features/project-scaffolding-supervisor-sessions/` — `project-scaffolding-supervisor-sessions.feature` (35 scenarios; 6 @smoke, 3 @regression), `_assumptions.yaml` (6 assumptions, all confirmed; `review_required: false`), `_summary.md`. Six behaviours previously unstated in design contracts were pinned via assumption resolution — see Status Log row above for the full list. The original invocation is preserved below for traceability; when replaying, note that the tentative `ADR-J-*` context paths were auto-mapped to actual `ADR-ARCH-*` files and two unreachable sibling-repo paths were skipped.

```bash
/feature-spec "Project Scaffolding, Supervisor Skeleton & Session Lifecycle: pyproject.toml with deepagents>=0.5.3,<0.6 pin, src/jarvis/ layer structure, DeepAgents supervisor via create_deep_agent(), thread-per-session with Memory Store, jarvis CLI (chat/version/health), smoke tests" \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-J-001-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-J-002-supervisor-factory.md \
  --context docs/architecture/decisions/ADR-J-003-layer-structure.md \
  --context docs/architecture/decisions/ADR-J-004-supervisor-model-default.md \
  --context docs/architecture/decisions/ADR-J-005-memory-store-backend.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context docs/research/ideas/jarvis-vision.md \
  --context docs/research/ideas/jarvis-architecture-conversation-starter.md \
  --context ../forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md \
  --context ../specialist-agent/docs/reviews/deepagents-sdk-2026-04.md \
  --context ../forge/src/forge/cli/main.py \
  --context ../specialist-agent/src/specialist_agent/cli/main.py \
  --context .guardkit/context-manifest.yaml
```

Actual output: `features/project-scaffolding-supervisor-sessions/` — `project-scaffolding-supervisor-sessions.feature` + `_assumptions.yaml` + `_summary.md`. All low-confidence assumptions were resolved (ASSUM-002, ASSUM-003 explicitly re-reviewed and signed off).

### Step 4: /feature-plan FEAT-JARVIS-001 ✅ COMPLETE (21 April 2026)

**Completed 21 April 2026.** Delivered: (a) review task `TASK-REV-J001` (decision=implement) in `tasks/in_review/`; (b) `tasks/backlog/project-scaffolding-supervisor-sessions/` with README.md, IMPLEMENTATION-GUIDE.md, and 11 subtask files `TASK-J001-001..011`; (c) structured YAML at `.guardkit/features/FEAT-JARVIS-001.yaml`. IMPLEMENTATION-GUIDE.md carries the three mandatory Mermaid diagrams (data flow, integration-contract sequence, task-dependency graph) plus a §4 Integration Contracts section pinning `SUPERVISOR_MODEL_ENDPOINT`, `COMPILED_SUPERVISOR_GRAPH`, and `APP_STATE`. Pre-flight validation caught one intra-wave dependency (TASK-J001-009 and -011 both depended on TASK-J001-008 while sharing wave 5); fixed by splitting into waves 5 (TASK-J001-008 alone) and 6 (parallel: -009 + -011). The original Step 4 invocation is preserved below for traceability.

```bash
/feature-plan "Project Scaffolding, Supervisor Skeleton & Session Lifecycle" \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_summary.md \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions.feature \
  --context features/project-scaffolding-supervisor-sessions/project-scaffolding-supervisor-sessions_assumptions.yaml \
  --context docs/design/FEAT-JARVIS-001/design.md \
  --context docs/architecture/ARCHITECTURE.md \
  --context docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md \
  --context docs/architecture/decisions/ADR-ARCH-002-clean-hexagonal-in-deepagents-supervisor.md \
  --context docs/architecture/decisions/ADR-ARCH-006-five-group-module-layout.md \
  --context docs/architecture/decisions/ADR-ARCH-009-thread-per-session-with-memory-store-summary-bridge.md \
  --context docs/architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md \
  --context docs/architecture/decisions/ADR-ARCH-015-ci-ruff-mypy-pytest.md \
  --context docs/architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md \
  --context docs/architecture/decisions/ADR-ARCH-021-tools-return-structured-errors.md \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md \
  --context ../specialist-agent/pyproject.toml \
  --context .guardkit/context-manifest.yaml
```

Actual output: review task `TASK-REV-J001` in `tasks/in_review/`; feature folder `tasks/backlog/project-scaffolding-supervisor-sessions/` with 11 subtasks (`TASK-J001-001..011`) + README.md + IMPLEMENTATION-GUIDE.md; structured YAML `.guardkit/features/FEAT-JARVIS-001.yaml`. Wave structure (as-planned, after pre-flight fix): **W1** parallel — pyproject, shared, reserved-empty packages · **W2** parallel — config, prompts+conftest · **W3** parallel — infrastructure, supervisor · **W4** serial — sessions · **W5** serial — CLI · **W6** parallel — E2E smoke, docs. All six assumption-resolved behaviours (empty-turn skip, `/exit` matching, concurrent-invoke refusal, REPL serialisation, config-error exit code 1, non-CLI-adapter `JarvisError`) are explicit in the subtask Acceptance Criteria and Coach Validation blocks.

### Step 5: AutoBuild FEAT-JARVIS-001 ✅ COMPLETE (21 April 2026)

**Completed 21 April 2026** under `guardkit autobuild` in a single shared worktree `.guardkit/worktrees/FEAT-JARVIS-001` from `main`. Total wall-clock: **~57 minutes** (22:31:06 → 23:28:43 UTC), well inside the 3–4-day budget. All 11 tasks reached Player→Coach approval; all are now `status: in_review` with `player_success: true` and `coach_success: true` in their `autobuild_state.turns[*]`.

Per-wave timings:

| Wave | Tasks | Turns total | Wall-clock |
|------|-------|-------------|-----------|
| 1 | TASK-J001-001, -002, -010 | 4 (1+2+1) | ~11 min |
| 2 | TASK-J001-003, -004 | 2 | ~8 min |
| 3 | TASK-J001-005, -006 | 2 | ~9 min |
| 4 | TASK-J001-007 | 1 | ~10 min |
| 5 | TASK-J001-008 | 1 | ~8 min |
| 6 | TASK-J001-009, -011 | 2 | ~11 min |
| — | **Total** | **12** | **~57 min** |

The only two-turn task was **TASK-J001-002** (shared primitives). Turn 1 passed lint/mypy/format and implemented the module correctly, but the coach's test runner ran `pytest` without an editable install in a src-layout project — every test failed with `ModuleNotFoundError: No module named 'jarvis'`. Turn 2 added `tests/conftest.py` that prepends `<project-root>/src` to `sys.path` at pytest startup (the standard src-layout fix); all 29 tests passed. Worth capturing as a lesson: **AutoBuild's test runner in src-layout projects needs either an editable install or a `conftest.py` sys.path shim in place before the first wave lands.**

No scope drift; no invariant violations observed in the coach summaries.

### Step 6: /task-review FEAT-JARVIS-001 ✅ COMPLETE (22 April 2026)

**Completed 22 April 2026.** Architectural post-build review of FEAT-JARVIS-001; score **82/100**, decision `[I]mplement`. Quality gates run: `pytest` 340/341 pass, `ruff` clean on `src/jarvis/`, `mypy` 5 errors on `src/jarvis/`. All six ASSUM-* pins and DDR-002/003/004 verified in code; scope invariants clean (no NATS/Telegram/Graphiti/subagent/custom-tool imports in `src/jarvis/`; 8 reserved packages properly stubbed with `# Reserved for FEAT-JARVIS-00N` markers). Review report: [`.claude/reviews/FEAT-JARVIS-001-review-report.md`](../../../.claude/reviews/FEAT-JARVIS-001-review-report.md). Original invocation preserved below for traceability.

```bash
/task-review FEAT-JARVIS-001 \
  --context tasks/backlog/project-scaffolding-supervisor-sessions/IMPLEMENTATION-GUIDE.md \
  --context .guardkit/features/FEAT-JARVIS-001.yaml \
  --context docs/research/ideas/phase1-supervisor-scaffolding-scope.md \
  --context docs/research/ideas/phase1-build-plan.md
```

**Findings summary** (8 total):

| ID | Severity | Summary | Success-criterion impact |
|---|---|---|---|
| F1 | HIGH | mypy 5 errors in `src/jarvis/` (`CompiledStateGraph` missing type params × 3, `_redact_secrets` signature, unused `type: ignore`) | Blocks SC #6 |
| F2 | HIGH | `test_jarvis_version_command` env-fragile — `sys.executable`-based subprocess fails when ambient venv ≠ project `.venv` (Py3.14 vs Py3.12) | Blocks SC #5 |
| F3 | MEDIUM | `AppState.supervisor` / `session_manager` typed `Any` with stale "*(None until TASK-J001-…)*" comments; CLI stitches them in via `dataclasses.replace` | None directly; bootstrap smell |
| F4 | MEDIUM | `JarvisConfig()` pydantic validation runs before `structlog` is configured; config-failure scenario wants structured log events for those failures too | None directly; scenario gap |
| F5 | LOW | `correlation_id` docstring says ULID, code uses `uuid.uuid4().hex` | None |
| F6 | LOW | 7 ruff errors in `tests/` (scoped outside SC #6 but indicates drift) | None |
| F7 | LOW | `SessionManager._in_flight: dict[str, bool]` — safe under asyncio single-loop; fragile when FEAT-006 adds a second task source | Defer to FEAT-JARVIS-006 |
| F8 | LOW | `from langchain_core.messages import HumanMessage` imported inside `invoke()` instead of module top | None |

**[I]mplement outcome:** 4 remediation subtasks created at [`tasks/backlog/phase1-review-fixes/`](../../../tasks/backlog/phase1-review-fixes/):

| Task | Wave | Mode | Fixes | Est. |
|---|---|---|---|---|
| TASK-J001-FIX-001 | 1 | direct | F1 (mypy clean) | 15 min |
| TASK-J001-FIX-002 | 1 | direct | F2 (Python pin + subprocess hardening) | 10 min |
| TASK-J001-FIX-003 | 2 | task-work | F3 + F4 (AppState + logging bootstrap) | 35 min |
| TASK-J001-FIX-004 | 2 | direct | F5 + F6 + F8 (cosmetic) | 15 min |

F7 is explicitly deferred to FEAT-JARVIS-006 (first consumer that stresses multi-task-per-session).

**Next:** execute `tasks/backlog/phase1-review-fixes/` (Wave 1 parallel, then Wave 2 parallel), then Step 7 regression check.

### Step 7: Regression check

```bash
cd /Users/richardwoollcott/Projects/appmilla_github/jarvis
uv sync
uv run pytest tests/ -v --tb=short --cov=src/jarvis
uv run ruff check src/jarvis/ tests/
uv run mypy src/jarvis/
```

All Phase 1 smoke tests must pass. Ruff + mypy clean. Coverage report recorded for baseline (target: >=80% on scaffolded modules; some modules are pure definitions and will report high naturally).

### Step 8: Day-1 conversation validation

Manually run the day-1 success criterion:

```bash
export JARVIS_SUPERVISOR_MODEL="<ADR-pinned default>"
export <provider API key env var>="..."

jarvis version   # should print 0.1.0
jarvis health    # should print config summary + "supervisor builds successfully"
jarvis chat      # start a conversation
  > Hi Jarvis
  [supervisor response]
  > What's the date today?
  [supervisor response]
  > Remember that my DDD Southwest talk is on 16 May.
  [supervisor response]
  /exit

# Start a new session
jarvis chat
  > What was my DDD Southwest talk date again?
  [supervisor response — should recall 16 May from Memory Store]
```

Record the conversation as evidence the day-1 criterion is met. Commit the evidence as a Phase 1 validation note (optional — can live as a markdown file under `docs/validation/` or in the commit message).

---

## Files That Will Change

| File | Change Type |
|------|------------|
| `pyproject.toml` | **NEW** — project metadata, `deepagents>=0.5.3,<0.6` pin, ruff + mypy + pytest config |
| `src/jarvis/__init__.py` | **NEW** — package marker, version |
| `src/jarvis/shared/{__init__,constants,exceptions}.py` | **NEW** — shared-layer primitives |
| `src/jarvis/config/{__init__,settings}.py` | **NEW** — `JarvisConfig` |
| `src/jarvis/prompts/{__init__,supervisor_prompt}.py` | **NEW** — supervisor system prompt |
| `src/jarvis/agents/{__init__,supervisor}.py` | **NEW** — `build_supervisor` factory |
| `src/jarvis/infrastructure/{__init__,logging,lifecycle}.py` | **NEW** — logging, startup/shutdown |
| `src/jarvis/sessions/{__init__,session,manager}.py` | **NEW** — `Session`, `SessionManager`, Memory Store integration |
| `src/jarvis/cli/{__init__,main}.py` | **NEW** — `jarvis` CLI (`chat`, `version`, `health`) |
| `src/jarvis/tools/__init__.py` | **NEW** — empty package (reserved for FEAT-JARVIS-002) |
| `tests/__init__.py`, `tests/conftest.py` | **NEW** — test package + shared fixtures |
| `tests/test_config.py` | **NEW** |
| `tests/test_supervisor.py` | **NEW** |
| `tests/test_sessions.py` | **NEW** |
| `tests/test_cli.py` | **NEW** |
| `tests/test_smoke_end_to_end.py` | **NEW** |
| `.env.example` | **NEW** — documented env vars |
| `README.md` | **UPDATED** — Quickstart section |
| `.gitignore` | **UPDATED** — `.venv/`, `.env`, `__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `dist/`, `build/` if not already present |
| `docs/architecture/ARCHITECTURE.md` | **NEW** — produced by `/system-arch` (Step 1) |
| `docs/architecture/decisions/ADR-J-001..N.md` | **NEW** — produced by `/system-arch` (Step 1) |
| `docs/architecture/{context,container}-diagram.md` | **NEW** — produced by `/system-arch` (Step 1) |
| `docs/design/FEAT-JARVIS-001/design.md` | **NEW** — produced by `/system-design` (Step 2) |
| `features/feat-jarvis-001-*/feat-jarvis-001-*.{feature,_assumptions.yaml,_summary.md}` | **NEW** — produced by `/feature-spec` (Step 3) |
| `tasks/FEAT-JARVIS-001-*.md` | **NEW** — produced by `/feature-plan` (Step 4) |

All paths relative to `/Users/richardwoollcott/Projects/appmilla_github/jarvis/`.

---

## Do-Not-Change

These are settled from fleet v3, conversation-starter v2, and the 20 April reframing. Do not re-litigate during Phase 1.

1. **Fleet v3 decisions D40–D46.** Three surfaces one substrate (D40), flywheel-via-calibration-loop fleet-wide (D41), trace-richness by default (D42), model routing is a reasoning decision (D43), selectively ambient A+B for v1 (D44), meta-agent split deferred (D45), NemoClaw hooks named but not built (D46).
2. **ADR-J-P1..P10 preferred directions** from the architecture conversation-starter v2. Phase 1 implements P1 (DeepAgent with dispatch tools), P3 (thread-per-session with shared Memory Store), P10 (`deepagents>=0.5.3,<0.6` pin); commits to the *schema shape* of P6 (trace-richness) even though the writes land at FEAT-JARVIS-004.
3. **Template choice.** `langchain-deepagents-orchestrator`. Do not revisit. The seven orchestrator specialist agents under `.claude/agents/` are authoritative pattern sources — use them during AutoBuild.
4. **DeepAgents 0.5.3 pin (`>=0.5.3,<0.6`).** Justified by specialist-agent's SDK review (19 April). Lower bound: `AsyncSubAgentMiddleware` preview availability. Upper bound: preview-API change risk in 0.6.
5. **Trace-richness schema shape (ADR-FLEET-001).** Phase 1 does not write to `jarvis_routing_history` (no dispatch decisions yet — FEAT-JARVIS-004's job), but the `Session` type and `SessionManager` model commit to emitting a session-record compatible with the ADR-FLEET-001 schema when FEAT-JARVIS-004 ships. No "add fields later" shortcuts.
6. **Singular topic convention (ADR-SP-016).** Not exercised in Phase 1 (no NATS) but any planning-level topic reference uses singular form.
7. **Phase 1 scope boundary.** No custom tools, no subagents, no NATS, no Telegram, no skills, no `jarvis.learning`. Each is a future-feature concern. If AutoBuild drift pushes any of these into Phase 1, stop and re-scope.
8. **`.claude/` + `.guardkit/` trees.** 14 agent files, 15 rules, `CLAUDE.md`, `.mcp.json`, `graphiti.yaml` all landed at `guardkit init`. Phase 1 does not modify these.
9. **Pre-existing `docs/research/` + `docs/product/` trees.** The 30 `po-extract/` outputs, 7 `gpa-idea/` outputs, and the pre-fleet-v3 `architect-greenfield/architecture.md` all stay where they are. `architecture.md` is flagged as superseded by `/system-arch` output but not deleted.
10. **Scope-preserving rules from the conversation starter §2.** No new agent repos until v1 ships; no changes to fleet v3 decisions D1–D46 mid-build; trace-richness from day one; Rich-in-the-loop for any learning work (though Phase 1 does no learning work).
11. **Context manifest.** `.guardkit/context-manifest.yaml` is authoritative for cross-repo dependencies. Update it only if a genuine new dependency emerges; note the minor `langchain-deepagents` vs `langchain-deepagents-orchestrator` reference as a *later* touch-up, not a Phase 1 change.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| `/system-arch` reveals gaps this build plan doesn't anticipate (e.g., layer names, supervisor factory choice, or open-question JA resolution pushing scope into Phase 1) | Update this build plan's Status Log + Change descriptions between Step 1 and Step 2. Do not start Step 2 (`/system-design`) until the Phase 1 plan matches the `/system-arch` outputs. |
| DeepAgents 0.5.3 preview features prove unstable during supervisor build | Phase 1 uses *no* preview features — supervisor is built-ins-only. `AsyncSubAgentMiddleware` risk deferred to FEAT-JARVIS-003. |
| `create_deep_agent()` vs `create_agent()` choice lands wrong in the ADR | Smoke tests in `tests/test_supervisor.py` are factory-agnostic (they check *structure*, not factory identity). Switching factories between Step 1 and Step 5 costs one edit to `agents/supervisor.py`. |
| Supervisor model choice (ADR-J-004) requires a provider key Rich doesn't have handy | `health` command reports which provider key is missing; fallback is to set `JARVIS_SUPERVISOR_MODEL` to a local model (vLLM on GB10) if available, otherwise flag to Rich for a provider-key step. |
| Memory Store in-memory semantics subtly break cross-session recall | `tests/test_sessions.py` includes an explicit write-in-session-A / read-in-session-B test with `InMemoryStore`. If that passes, the pattern is sound. File-backed + Graphiti-backed come later — Phase 1 doesn't need them. |
| Ruff or mypy rules imported from specialist-agent are too strict for a 40-file scaffold | Start with specialist-agent's config; relax per-module if needed with `# noqa` or targeted `[[tool.mypy.overrides]]` — but keep the invariant that `src/jarvis/` is clean. |
| AutoBuild produces a mega-commit instead of per-step commits | `/feature-plan` output enumerates commit boundaries; if AutoBuild ignores them, split at `/task-review`. |
| `jarvis chat` works for Rich but fails for a future Mark-style scoped user | Phase 1 is single-user by design. Multi-user is a v2 concern. |
| Memory Store keyed by `user_id` conflicts with thread-scoped state later | ADR-J-005 (Memory Store backend) covers the `user_id` keying choice explicitly; if the ADR lands a different key, update `SessionManager.invoke` accordingly before Step 5. |

---

## Expected Timeline

| Day | Activity | Output |
|-----|----------|--------|
| 1 (21 Apr) ✅ | Steps 1, 2, **and** 3 — `/system-arch` + `/system-design FEAT-JARVIS-001` + `/feature-spec FEAT-JARVIS-001` all landed same day (a day ahead of the original schedule). | `ARCHITECTURE.md`, C4 diagrams, domain model, `ADR-ARCH-001..030` (30 ADRs, actual IDs); `docs/design/FEAT-JARVIS-001/design.md` + `diagrams/` + `contracts/` + `decisions/` + `models/`; `features/project-scaffolding-supervisor-sessions/` (35 scenarios, 6 assumptions confirmed, `review_required: false`). C4 L3 approval + Graphiti seeding done. |
| 1 (21 Apr) ✅ | Step 4 — `/feature-plan FEAT-JARVIS-001` (also bumped forward to 21 Apr following same-day Step 3). | `tasks/in_review/TASK-REV-J001-*.md`; `tasks/backlog/project-scaffolding-supervisor-sessions/` (README + IMPLEMENTATION-GUIDE + 11 subtasks); `.guardkit/features/FEAT-JARVIS-001.yaml` (6-wave orchestration). |
| 1 (21 Apr) ✅ | Step 5 — AutoBuild FEAT-JARVIS-001 (also collapsed to 21 Apr). | All 11 tasks Player→Coach approved in ~57 min wall-clock (22:31–23:28 UTC), single worktree `.guardkit/worktrees/FEAT-JARVIS-001`. One two-turn task (TASK-J001-002, src-layout sys.path fix). All tasks `status: in_review`. |
| 2 (22 Apr) ✅ | Step 6 — `/task-review FEAT-JARVIS-001` (standard depth, architectural mode). | Review pass **with findings**; score 82/100; 2 HIGH (block SC #5/#6), 2 MEDIUM, 4 LOW; decision `[I]mplement`. Report at `.claude/reviews/FEAT-JARVIS-001-review-report.md`. 4 remediation subtasks generated at `tasks/backlog/phase1-review-fixes/` (2 parallel waves, ~50 min wall-clock). |
| 2 (22 Apr) ⬅ | Execute `tasks/backlog/phase1-review-fixes/` — Wave 1 (FIX-001 ∥ FIX-002) then Wave 2 (FIX-003 ∥ FIX-004). | mypy clean on `src/jarvis/`, 341/341 pytest pass, `AppState` tightened, logging configured at CLI entry, cosmetic polish landed. |
| 2 (22 Apr) | Step 7 — regression check (ruff + mypy + pytest + coverage baseline). | CI green locally; coverage baseline recorded. |
| 2 (22 Apr) | Step 8 — day-1 conversation validation. | Conversation recorded as evidence; Phase 1 closed. |

**Revised target: Phase 1 complete in 2 working days (21–22 April 2026) — faster than the 3–4-day original estimate because Steps 1–5 all landed on day 1.**

Realistic given no NATS dependencies, no preview-feature risk, no external integration. The broader v1 timeline (~11–12 working days per conversation starter §5) flows from here — and now has ~2 days of slack banked.

---

## After Phase 1: What Comes Next

| Priority | Phase | Content | Proposed Grouping |
|----------|-------|---------|-------------------|
| **Next** | Phase 2 | FEAT-JARVIS-002 (Core Tools & Dispatch Tools) + FEAT-JARVIS-003 (Async Subagents) | Both depend only on 001; both are about giving the supervisor its dispatch *vocabulary* — tools it can call and subagents it can delegate to. Natural pairing. |
| **Then** | Phase 3 | FEAT-JARVIS-004 (NATS Fleet Registration & Specialist Dispatch) + FEAT-JARVIS-005 (Build Queue Dispatch to Forge) | 004 establishes the fleet contract (register, discover, dispatch via `agents.command.*`); 005 consumes it (publish `BuildQueuedPayload` to `pipeline.build-queued.*`). 005 also lights up the ADR-FLEET-001 trace-richness writes on `jarvis_routing_history` for the first time. |
| **Last for v1** | Phase 4 | FEAT-JARVIS-006 (Telegram Adapter) + FEAT-JARVIS-007 (Skills & Memory Store) | Both user-facing surfaces rather than infrastructure. Memory Store already wired in Phase 1 — FEAT-JARVIS-007 activates it with the three launch skills (`morning-briefing`, `talk-prep`, `project-status`). `talk-prep` module scaffolds the Pattern C ambient slot reserved for v1.5. |
| **v1.5** | Phase 5 | FEAT-JARVIS-008 (Learning Flywheel) | Deferred per 20 April Q10.2. Returns when v1 has shipped and real routing history exists to learn from. Its own phase pair when it returns. |
| **v1.5** | — | FEAT-JARVIS-009 (CLI + Dashboard adapters), FEAT-JARVIS-010 (`talk-prep` Pattern C ambient nudges), FEAT-JARVIS-011 (`jarvis purge-traces`) | Deferred per 20 April updates. Each gets its own phase pair when they return. |

Rich — please confirm the Phase 2 / 3 / 4 grouping above before I produce those phase pairs. The grouping matches the conversation starter's §0 suggestion. If you want finer slices (e.g. FEAT-JARVIS-002 and FEAT-JARVIS-003 in separate phases), coarser slices (e.g. combining Phase 3 and Phase 4), or a different sequencing (e.g. Telegram adapter earlier for faster feedback), flag it and I'll adjust before generating Phase 2+ pairs.

---

*Phase 1 build plan: 20 April 2026 (status updated 22 April 2026).*
*Predecessor: `guardkit init langchain-deepagents-orchestrator` (20 April 2026); `.guardkit/context-manifest.yaml` landed 19 April 2026; ADR-FLEET-001 + fleet v3 keystone doc 19 April 2026.*
*Steps complete: `/system-arch` (Step 1) ✅ 21 April · `/system-design FEAT-JARVIS-001` (Step 2) ✅ 21 April · `/feature-spec FEAT-JARVIS-001` (Step 3) ✅ 21 April · `/feature-plan FEAT-JARVIS-001` (Step 4) ✅ 21 April · AutoBuild (Step 5) ✅ 21 April.*
*Next: `/task-review FEAT-JARVIS-001` (Step 6) — tasks are in `status: in_review`.*
*"Rich can have a useful conversation with it on day 1, even if it can't dispatch to anything yet."*
