---
complexity: 5
consumer_context:
- consumes: JARVIS_CONFIG
  driver: pydantic>=2
  format_note: AppState accepts the validated JarvisConfig instance; startup calls
    config.validate_provider_keys() AFTER logging is configured
  framework: pydantic-settings BaseSettings
  task: TASK-J001-003
dependencies:
- TASK-J001-003
- TASK-J001-002
feature_id: FEAT-JARVIS-001
id: TASK-J001-005
implementation_mode: task-work
parent_review: TASK-REV-J001
status: design_approved
tags:
- feature
- logging
- lifecycle
- structlog
- secret-redaction
- adr-arch-020
task_type: feature
title: infrastructure/ — structlog setup + lifecycle (startup/shutdown + AppState)
wave: 3
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