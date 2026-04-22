---
id: TASK-J001-001
title: pyproject.toml with deepagents>=0.5.3,<0.6 pin and tool config
task_type: scaffolding
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 1
implementation_mode: direct
complexity: 4
dependencies: []
status: pending
tags: [scaffolding, build-system, deepagents-pin, adr-arch-010]
---

# Task: `pyproject.toml` + build system + tool config

Establish the Python 3.12 project file with the DeepAgents pin from ADR-ARCH-010 and tool configurations (ruff, mypy, pytest) from ADR-ARCH-015.

## Context

- [ADR-ARCH-010](../../../docs/architecture/decisions/ADR-ARCH-010-python-312-and-deepagents-pin.md): Python 3.12 + `deepagents>=0.5.3,<0.6`
- [ADR-ARCH-015](../../../docs/architecture/decisions/ADR-ARCH-015-ci-ruff-mypy-pytest.md): ruff + mypy (strict) + pytest
- Style reference: `../specialist-agent/pyproject.toml`
- [phase1-build-plan.md §Change 1](../../../docs/research/ideas/phase1-build-plan.md)

## Scope

- `pyproject.toml` (NEW) with:
  - `[project]`: `name="jarvis"`, `requires-python=">=3.12"`, authors, description from `CLAUDE.md`
  - `[project.dependencies]`:
    - `deepagents>=0.5.3,<0.6` — **mandatory pin** per ADR-ARCH-010
    - `langchain-core`, `langgraph>=0.3`, `pydantic>=2`, `pydantic-settings`, `structlog`, `python-dotenv`, `click`
    - `langchain-openai` (for init_chat_model `openai:` prefix → llama-swap via OPENAI_BASE_URL)
  - `[project.optional-dependencies].dev`: `pytest>=8`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`, `types-*` as needed
  - `[project.optional-dependencies].providers`: `langchain-anthropic`, `langchain-google-genai` — per template LES1 §3 LCOI rule (declare every integration this template can be configured to use)
  - `[project.scripts]`: `jarvis = "jarvis.cli.main:main"`
  - `[tool.ruff]`: line length 100, target `py312`
  - `[tool.mypy]`: strict, `python_version = "3.12"`, `warn_unused_ignores = true`
  - `[tool.pytest.ini_options]`: `asyncio_mode = "auto"`, coverage config
  - `[build-system]`: `hatchling` (matches Forge + specialist-agent)
- `.gitignore` updates: `.venv/`, `.env`, `__pycache__/`, `.ruff_cache/`, `.mypy_cache/`, `dist/`, `build/`, `.pytest_cache/`

## Acceptance Criteria

- `pyproject.toml` parses; `pip install -e ".[dev]"` succeeds in a clean Python 3.12 venv.
- `pip show deepagents` reports a version in `[0.5.3, 0.6)`.
- `ruff --version`, `mypy --version`, `pytest --version` all resolve after dev install.
- `jarvis` script entry-point resolves (even if it errors — the entry-point wiring itself is correct).
- `.gitignore` contains all required patterns and `.env` is not accidentally committable.

## Coach Validation

- Verify `deepagents` line reads exactly `deepagents>=0.5.3,<0.6` (not `~=`, not `==`).
- Verify `[project.optional-dependencies].providers` lists every provider used by `init_chat_model` prefixes anywhere in the tree (LCOI).
- Verify `[tool.mypy]` has `strict = true` (or equivalent explicit flag set).
