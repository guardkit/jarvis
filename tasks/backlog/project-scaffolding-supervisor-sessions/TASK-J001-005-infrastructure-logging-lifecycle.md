---
id: TASK-J001-005
title: "infrastructure/ \u2014 structlog setup + lifecycle (startup/shutdown + AppState)"
task_type: feature
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 3
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-J001-003
- TASK-J001-002
status: in_review
tags:
- feature
- logging
- lifecycle
- structlog
- secret-redaction
- adr-arch-020
consumer_context:
- task: TASK-J001-003
  consumes: JARVIS_CONFIG
  framework: pydantic-settings BaseSettings
  driver: pydantic>=2
  format_note: AppState accepts the validated JarvisConfig instance; startup calls
    config.validate_provider_keys() AFTER logging is configured
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T22:50:54.322901'
  last_updated: '2026-04-21T22:57:58.800068'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-21T22:50:54.322901'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: `src/jarvis/infrastructure/` — structlog + lifecycle

Structured logging (with secret-redaction processors) + `startup(config) -> AppState` / `shutdown(state)` lifecycle helpers.

## Context

- [phase1-build-plan.md §Change 7](../../../docs/research/ideas/phase1-build-plan.md)
- [ADR-ARCH-020 trace-richness by default](../../../docs/architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md)
- Feature file @edge-case: "Startup configures logging before validating configuration"
- Feature file @edge-case @security @regression: "Structured log events redact provider-key and token fields"

## Scope

**Files (NEW):**

- `src/jarvis/infrastructure/__init__.py`
- `src/jarvis/infrastructure/logging.py`:
  - `configure(log_level: str) -> None` — sets up structlog (JSON in non-TTY, console in TTY)
  - Redaction processor that masks any dict key ending `_key` or `_token`
  - Must run before config validation so config-load errors are captured as structured events
- `src/jarvis/infrastructure/lifecycle.py`:
  - `@dataclass class AppState`: `config`, `supervisor`, `store`, `session_manager`
  - `async def startup(config: JarvisConfig) -> AppState`:
    1. Configure logging (first, before any validation)
    2. `config.validate_provider_keys()` — raises `ConfigurationError` if missing
    3. Build supervisor (from TASK-J001-006)
    4. Build `InMemoryStore` (later backends via `memory_store_backend` dispatcher)
    5. Build `SessionManager` (from TASK-J001-007)
    6. Return `AppState`
  - `async def shutdown(state: AppState) -> None`: cancel sessions, flush store, log clean shutdown

## Acceptance Criteria

- `infrastructure.logging.configure("INFO")` produces JSON-formatted events on a pipe, console-formatted on a TTY.
- A log event emitted with `config.model_dump()` as payload redacts all `*_key` and `*_token` values (literal secret values must not appear in the emitted event).
- `startup()` raises `ConfigurationError` with the configured logging system already emitting structured events (i.e., the error is logged as a structured event before being re-raised).
- `shutdown(state)` is idempotent — calling it twice does not raise.
- All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

- Coach verifies `configure()` is called before `validate_provider_keys()` in `startup()` (order invariant).
- Coach greps structured log emit sites for raw secret values — none must appear.
- Coach verifies `AppState` is a `@dataclass(frozen=True)` (or equivalent immutability).
