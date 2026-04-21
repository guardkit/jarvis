# API Contract — CLI

**Feature:** FEAT-JARVIS-001
**Bounded context:** Adapter Interface Context (CLI adapter only, Phase 1 stub)
**Protocol:** stdin/stdout via Click
**Consumers:** Rich (human operator); test suite via Click `CliRunner`
**Version:** 0.1.0
**Status:** Proposed

---

## 1. Overview

The `jarvis` CLI is the Phase 1 user-facing surface. It exposes three commands — `chat`, `version`, `health` — sufficient to meet the [Phase 1 day-1 success criterion](../../../research/ideas/phase1-supervisor-scaffolding-scope.md) ("Rich can have a useful conversation with it on day 1, even if it can't dispatch to anything yet").

No `--scope`, no `--docs`, no `--output`. No subcommands beyond these three. Later features (FEAT-JARVIS-007 skills; operator CLI commands per ADR-ARCH-018) extend this surface; they do not rewrite it.

---

## 2. Entrypoint

```
jarvis [--version] <command> [<args>...]
```

Registered via `[project.scripts] jarvis = "jarvis.cli.main:main"` in `pyproject.toml`.

All commands respect `JARVIS_LOG_LEVEL` and read config from env vars + `.env` via `jarvis.config.settings.JarvisConfig`.

---

## 3. Commands

### 3.1 `jarvis version`

Prints the package version and exits.

**Arguments:** none.
**Stdout:** `jarvis 0.1.0` (single line, trailing newline).
**Stderr:** nothing on success.
**Exit codes:** `0` always (no failure path).
**Side effects:** none. Does not load config, does not build the supervisor.

### 3.2 `jarvis health`

Loads `JarvisConfig`, attempts to build the supervisor (no LLM call), prints a status summary.

**Arguments:** none.
**Stdout:** multi-line status report:

```
jarvis 0.1.0
config:
  log_level: INFO
  supervisor_model: openai:jarvis-reasoner
  memory_store_backend: in_memory
  data_dir: /home/rich/.jarvis
  provider keys: openai=set google=unset anthropic=unset
supervisor: builds successfully
memory store: InMemoryStore ready
```

**Stderr:** validation error messages on config failure.
**Exit codes:**
- `0` — config loaded and supervisor built successfully.
- `1` — `ConfigurationError` (missing required env var, malformed model string).
- `2` — supervisor build failed (import error, DeepAgents incompatibility).

**Side effects:** reads env + `.env`; instantiates supervisor without invoking the model. `health` is the Phase 1 wiring-debug primitive.

### 3.3 `jarvis chat`

Starts an interactive REPL session using `SessionManager`.

**Arguments:** none (Phase 1).
**Stdin:** one user turn per line. EOF (`Ctrl-D`) or `/exit` ends the session cleanly.
**Stdout:**
- Banner on start: `jarvis chat — session {session_id} — type /exit or Ctrl-D to end`
- Per turn: supervisor response text, trailing newline.
- Banner on end: `session ended.`

**Stderr:**
- Structured trace logs at `JARVIS_LOG_LEVEL` (JSON when non-TTY, console when TTY).
- Provider errors surface as `[error] {message}` lines; the REPL continues.

**Exit codes:**
- `0` — clean exit (EOF / `/exit`).
- `1` — config/build error before REPL started.
- `130` — `SIGINT` (Ctrl-C during REPL).

**Side effects:**
- Creates one `Session` via `SessionManager.start_session(adapter=Adapter.CLI, user_id="rich")`.
- Calls `SessionManager.invoke(session, user_input)` per turn.
- Calls `SessionManager.end_session(session_id)` on exit.
- Writes structlog events to stderr per [ADR-ARCH-020](../../../architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md) — trace-richness schema shape is committed but the full `jarvis_routing_history` write path lands at FEAT-JARVIS-004.

### 3.4 Reserved commands (NOT in Phase 1)

| Command | Feature | Notes |
|---|---|---|
| `jarvis status` | FEAT-JARVIS-004 | Operator CLI — lists active sessions + dispatches |
| `jarvis approve-adjustment` | FEAT-JARVIS-008 (v1.5) | CalibrationAdjustment approval round-trip (ADR-ARCH-018) |
| `jarvis confirm-adjustment` | FEAT-JARVIS-008 (v1.5) | Alias for above |
| `jarvis purge-traces` | FEAT-JARVIS-011 (v1.1) | Graphiti trace deletion |

These names are reserved — Phase 1 must not shadow them.

---

## 4. Environment variable contract

All config reads via `JarvisConfig` (`env_prefix="JARVIS_"`). The CLI surfaces these variables by reference, never directly.

| Env var | Required? | Default | Consumed by |
|---|---|---|---|
| `JARVIS_LOG_LEVEL` | No | `INFO` | `jarvis.infrastructure.logging` |
| `JARVIS_SUPERVISOR_MODEL` | No | `openai:jarvis-reasoner` | `jarvis.agents.supervisor` |
| `JARVIS_MEMORY_STORE_BACKEND` | No | `in_memory` | `jarvis.sessions.manager` |
| `JARVIS_DATA_DIR` | No | `~/.jarvis` | Reserved (file-backed Memory Store, v1.5) |
| `OPENAI_API_KEY` | Conditional | unset | `init_chat_model` — required when model prefix is `openai:` |
| `OPENAI_BASE_URL` | Conditional | unset | Required for llama-swap: `http://promaxgb10-41b1:9000/v1` |
| `ANTHROPIC_API_KEY` | Conditional | unset | `init_chat_model` when model prefix is `anthropic:` |
| `GOOGLE_API_KEY` | Conditional | unset | `init_chat_model` when model prefix is `google_genai:` |

Validation: if the selected supervisor model requires a provider key that is unset, `health` and `chat` both exit `1` with a clear `ConfigurationError` naming the missing variable.

---

## 5. Test surface

Exercised via `click.testing.CliRunner` in `tests/test_cli.py`:

- `version` — prints version, exits 0.
- `health` — builds supervisor with `FakeListChatModel`, prints summary, exits 0.
- `chat` — stdin fed a canned turn, supervisor returns canned response, EOF ends session, exits 0.
- `chat` with missing required provider key → exits 1, stderr contains env var name.
- `chat` interrupted with `SIGINT` → exits 130, session cleanup logged.

---

## 6. Non-goals for Phase 1

- No authentication (single-user local CLI; ADR-ARCH-029 compliance posture).
- No TTY coloring / progress indicators (deferred — add as polish later).
- No streaming token output (Phase 1 invokes `ainvoke` not `astream`; FEAT-JARVIS-006 may add streaming for Telegram).
- No trace-viewer on CLI (dashboard is the trace viewport per ADR-ARCH-019).
- No multi-line input or paste mode (keep surface minimal).

---

## 7. Related

- [API-internal.md](API-internal.md) — the Python module contracts the CLI consumes
- [DM-jarvis-reasoning.md](../models/DM-jarvis-reasoning.md) — `Session` + `Adapter` types
- [DDR-003-cli-minimal-surface.md](../decisions/DDR-003-cli-minimal-surface.md) — why only these three commands
- [ADR-ARCH-016](../../../architecture/decisions/ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md) — CLI is one of six consumer surfaces
- [ADR-ARCH-018](../../../architecture/decisions/ADR-ARCH-018-calibration-approvals-cli-only-v1.md) — CLI is the approval surface (future commands)
