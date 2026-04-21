# Data Model — Config (cross-cutting)

**Feature:** FEAT-JARVIS-001
**Bounded context:** Cross-cutting — `jarvis.config`
**Version:** 0.1.0
**Status:** Proposed

---

## 1. Entity

### `JarvisConfig` (pydantic-settings `BaseSettings`)

```python
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from jarvis.shared.exceptions import ConfigurationError


class JarvisConfig(BaseSettings):
    log_level: str = Field(
        default="INFO",
        description="Python logging level name; passed to structlog.configure.",
    )
    supervisor_model: str = Field(
        default="openai:jarvis-reasoner",
        description=(
            "init_chat_model model spec in 'provider:alias' form. "
            "Default targets llama-swap via the OpenAI-compatible front door "
            "(requires OPENAI_BASE_URL=http://promaxgb10-41b1:9000/v1). "
            "Override to e.g. 'anthropic:claude-haiku-4-5' for dev without llama-swap."
        ),
    )
    memory_store_backend: Literal["in_memory", "file", "graphiti"] = Field(
        default="in_memory",
        description=(
            "Which BaseStore to instantiate. "
            "Phase 1: only 'in_memory' is implemented; 'file' → v1.5; 'graphiti' → v2."
        ),
    )
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".jarvis",
        description="Reserved for v1.5 file-backed store location.",
    )

    # Provider keys — NOT prefixed with JARVIS_ (init_chat_model reads bare names)
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    anthropic_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_prefix="JARVIS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    def validate_provider_keys(self) -> None:
        """Raise ConfigurationError if the selected model lacks its provider key."""
        provider, _, _ = self.supervisor_model.partition(":")
        required = {
            "openai":       self.openai_api_key,
            "anthropic":    self.anthropic_api_key,
            "google_genai": self.google_api_key,
        }
        if provider in required and required[provider] is None:
            raise ConfigurationError(
                f"supervisor_model '{self.supervisor_model}' requires "
                f"{provider.upper()}_API_KEY to be set."
            )
        if provider == "openai" and "jarvis-reasoner" in self.supervisor_model:
            if self.openai_base_url is None:
                raise ConfigurationError(
                    "supervisor_model defaults to llama-swap alias 'jarvis-reasoner' "
                    "but OPENAI_BASE_URL is unset. "
                    "Set OPENAI_BASE_URL=http://promaxgb10-41b1:9000/v1 "
                    "or override supervisor_model."
                )
```

---

## 2. Environment variable mapping

Pydantic-settings resolves fields in precedence order: (1) explicit constructor kwargs → (2) env vars → (3) `.env` file → (4) defaults.

| Field | Env var | Type | Default |
|---|---|---|---|
| `log_level` | `JARVIS_LOG_LEVEL` | str | `INFO` |
| `supervisor_model` | `JARVIS_SUPERVISOR_MODEL` | str | `openai:jarvis-reasoner` |
| `memory_store_backend` | `JARVIS_MEMORY_STORE_BACKEND` | enum | `in_memory` |
| `data_dir` | `JARVIS_DATA_DIR` | Path | `~/.jarvis` |
| `openai_api_key` | `OPENAI_API_KEY` | SecretStr | `None` |
| `openai_base_url` | `OPENAI_BASE_URL` | str | `None` |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | SecretStr | `None` |
| `google_api_key` | `GOOGLE_API_KEY` | SecretStr | `None` |

Provider keys use their **unprefixed** env var names so that `init_chat_model(...)` picks them up directly without Jarvis having to re-export them.

---

## 3. `.env.example` contract

```dotenv
# --- Jarvis — Phase 1 (FEAT-JARVIS-001) ---

# Log level (DEBUG | INFO | WARNING | ERROR)
JARVIS_LOG_LEVEL=INFO

# Supervisor model — 'provider:alias' form for init_chat_model.
# Default targets llama-swap on GB10 (see ADR-ARCH-001). Requires OPENAI_BASE_URL.
JARVIS_SUPERVISOR_MODEL=openai:jarvis-reasoner

# Memory Store backend — 'in_memory' only in Phase 1.
JARVIS_MEMORY_STORE_BACKEND=in_memory

# Reserved for v1.5 file-backed store.
# JARVIS_DATA_DIR=~/.jarvis

# --- Provider credentials (pick the one matching JARVIS_SUPERVISOR_MODEL) ---

# Local llama-swap on GB10 — OpenAI-compatible, API key not validated.
OPENAI_BASE_URL=http://promaxgb10-41b1:9000/v1
OPENAI_API_KEY=llama-swap-local

# Anthropic (attended cloud escape or dev fallback).
# ANTHROPIC_API_KEY=

# Google GenAI (alternate attended fallback).
# GOOGLE_API_KEY=
```

---

## 4. Validation rules

| Rule | Where | Failure |
|---|---|---|
| `log_level` is a valid logging level name | Pydantic field validator | `ValidationError` |
| `supervisor_model` matches `^(openai\|anthropic\|google_genai):.+$` | Pydantic field validator | `ValidationError` |
| `memory_store_backend == "in_memory"` in Phase 1 | `lifecycle.startup` | `ConfigurationError` — "file/graphiti backends not implemented until v1.5" |
| Provider key required by model prefix is set | `validate_provider_keys()` | `ConfigurationError` |
| `OPENAI_BASE_URL` set when model is `jarvis-reasoner` | `validate_provider_keys()` | `ConfigurationError` |

`validate_provider_keys()` is called once in `lifecycle.startup`. The CLI `health` command also calls it to give a clean pre-flight readout.

---

## 5. Secret handling

- All API-key fields use `SecretStr` — logging a `JarvisConfig` never prints the secret.
- `structlog.configure` in `jarvis.infrastructure.logging` installs a redaction processor that strips keys matching `*_key` / `*_token` from log events — belt-and-braces with `SecretStr.__repr__`.
- `.env` is git-ignored. `.env.example` ships only placeholder values.
- Per agent-manifest-contract ([context-manifest.yaml](../../../../.guardkit/context-manifest.yaml)), secrets never appear in `AgentManifest` payloads — but Phase 1 publishes no manifests (FEAT-JARVIS-004).

---

## 6. Non-goals for Phase 1

- **No YAML config file.** Config is env-only. [ADR-ARCH-019 adopted from Forge](../../../architecture/decisions/ADR-ARCH-019-dashboard-read-only-live-trace-viewport.md) / ADR-ARCH-011 rationale: behavioural config lives in Graphiti (calibration adjustments), not YAML. Phase 1 has no calibration yet, so infrastructure-only env config is sufficient.
- **No runtime config hot-reload.** Changing env requires restart — acceptable for v1.
- **No per-adapter config sections.** Adapters are separate containers (ADR-ARCH-007); each owns its own env.
- **No `jarvis.yaml` loader.** Mentioned in [ARCHITECTURE.md §3E](../../../architecture/ARCHITECTURE.md) but that's v1.5+ — Phase 1 ships env-only.

---

## 7. Test coverage surface

Exercised in `tests/test_config.py`:

- `JarvisConfig()` loads from env with all defaults → valid.
- `JarvisConfig(supervisor_model="openai:jarvis-reasoner")` without `OPENAI_BASE_URL` → `validate_provider_keys()` raises `ConfigurationError`.
- `JarvisConfig(supervisor_model="anthropic:claude-haiku-4-5")` without `ANTHROPIC_API_KEY` → `ConfigurationError`.
- `JarvisConfig(memory_store_backend="graphiti")` → `lifecycle.startup` raises `ConfigurationError`.
- Setting `JARVIS_LOG_LEVEL=bogus` → `ValidationError`.
- `SecretStr.get_secret_value()` required to read API keys — `str(config)` does not leak them.

---

## 8. Related

- [API-internal.md §5](../contracts/API-internal.md) — how `JarvisConfig` is consumed
- [DM-jarvis-reasoning.md](DM-jarvis-reasoning.md) — `AppState` holds a `JarvisConfig`
- [ADR-ARCH-010](../../../architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md)
- [ADR-ARCH-011](../../../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md) — llama-swap alias registry
- [ADR-ARCH-001](../../../architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md) — rationale for the llama-swap default
