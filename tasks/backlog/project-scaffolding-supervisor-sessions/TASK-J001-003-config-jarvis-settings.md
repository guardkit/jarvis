---
id: TASK-J001-003
title: "config/ \u2014 JarvisConfig (BaseSettings) + validate_provider_keys"
task_type: declarative
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 2
implementation_mode: task-work
complexity: 5
dependencies:
- TASK-J001-001
- TASK-J001-002
status: in_review
tags:
- declarative
- config
- pydantic-settings
- secrets
- adr-arch-001
autobuild_state:
  current_turn: 1
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T22:42:27.962133'
  last_updated: '2026-04-21T22:49:30.634938'
  turns:
  - turn: 1
    decision: approve
    feedback: null
    timestamp: '2026-04-21T22:42:27.962133'
    player_summary: Implementation via task-work delegation
    player_success: true
    coach_success: true
---

# Task: `src/jarvis/config/settings.py` — `JarvisConfig` (pydantic-settings)

The cross-cutting config model (ADR-ARCH-006 Group E). Validates provider keys at load time and surfaces clear `ConfigurationError` on miss. Default model routes through llama-swap (user memory: local-first inference — `promaxgb10-41b1:9000` is the single front door).

## Context

- [DM-config.md](../../../docs/design/FEAT-JARVIS-001/models/DM-config.md)
- [ADR-ARCH-001 local-first inference](../../../docs/architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md) (referenced)
- User memory: llama-swap at `promaxgb10-41b1:9000` is the single inference front door for Jarvis/Forge/agents
- ASSUM-005: pydantic `ValidationError` at config load exits CLI with code 1

## Scope

**Files (NEW):**

- `src/jarvis/config/__init__.py`
- `src/jarvis/config/settings.py`:

```python
class JarvisConfig(BaseSettings):
    log_level: Literal["DEBUG","INFO","WARNING","ERROR","CRITICAL"] = "INFO"
    supervisor_model: str = "openai:jarvis-reasoner"  # default → llama-swap via OPENAI_BASE_URL
    memory_store_backend: Literal["in_memory", "file", "graphiti"] = "in_memory"
    data_dir: Path = Path.home() / ".jarvis"

    # Provider keys (SecretStr so repr/logs are masked)
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    google_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",  # JARVIS_LOG_LEVEL, JARVIS_SUPERVISOR_MODEL, JARVIS_OPENAI_BASE_URL, ...
        env_file=".env",
        env_file_encoding="utf-8",
    )

    def validate_provider_keys(self) -> None:
        """Raise ConfigurationError naming the missing env var for the selected model."""
```

- `validate_provider_keys()` logic (per feature file @negative scenarios):
  - `openai:*` model → require `openai_base_url` (names `OPENAI_BASE_URL` in the error)
  - `anthropic:*` model → require `anthropic_api_key` (names `ANTHROPIC_API_KEY`)
  - `google_genai:*` model → require `google_api_key` (names `GOOGLE_API_KEY`)
  - Raise `ConfigurationError` with clear message

- Supervisor model string must be provider-prefixed — enforce via pydantic `field_validator` (raises `ValidationError` on bare strings like `"jarvis-reasoner"`, per ASSUM-005).

- `memory_store_backend != "in_memory"` raises `ConfigurationError("<backend> backend is not implemented in Phase 1")` at `validate_provider_keys` time (feature file @negative scenario).

## Acceptance Criteria

- `JarvisConfig()` with no env vars set loads with documented defaults (log_level=INFO, backend=in_memory, model=openai:jarvis-reasoner).
- `JARVIS_SUPERVISOR_MODEL=jarvis-reasoner` (no provider prefix) raises pydantic `ValidationError` at construction.
- `JARVIS_LOG_LEVEL=bogus` raises pydantic `ValidationError` at construction.
- `str(config)` and `repr(config)` do not disclose SecretStr values (they render as `**********` / `SecretStr('**********')`).
- `validate_provider_keys()` raises `ConfigurationError` naming the missing env var when the selected model's key is absent.
- All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

- Coach greps for literal provider key values in structured log output under `--log-level=DEBUG` — none must appear.
- Coach verifies `supervisor_model` default is `openai:jarvis-reasoner` (not any cloud model) to honour local-first inference.
- Coach verifies `SettingsConfigDict(env_prefix="JARVIS_")` is set (env var scoping invariant).

## Seam Tests

Contract: consumer of `SUPERVISOR_MODEL_ENDPOINT` from TASK-J001-006 (supervisor factory) — this task is the **producer**. Seam test belongs on the consumer side (see TASK-J001-006 §Seam Tests).
