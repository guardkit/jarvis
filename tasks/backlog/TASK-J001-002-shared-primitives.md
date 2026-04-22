---
id: TASK-J001-002
title: Shared primitives — constants, Adapter enum, exception hierarchy
task_type: declarative
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: pending
tags: [declarative, shared-layer, exceptions, adapters, adr-arch-006]
---

# Task: `src/jarvis/shared/` — constants, Adapter enum, exception hierarchy

The "safe-to-import-from-anywhere" tier per ADR-ARCH-006. Zero dependencies on supervisor/sessions/config/I/O.

## Context

- [ADR-ARCH-006](../../../docs/architecture/decisions/ADR-ARCH-006-five-group-module-layout.md): five-group layout; `shared/` is the primitives floor
- [DM-jarvis-reasoning.md §6](../../../docs/design/FEAT-JARVIS-001/models/DM-jarvis-reasoning.md): exception hierarchy shape
- ASSUM-006: non-CLI adapters raise `JarvisError`

## Scope

**Files (NEW):**

- `src/jarvis/__init__.py` — `__version__ = "0.1.0"` exported
- `src/jarvis/shared/__init__.py`
- `src/jarvis/shared/constants.py`:
  - `VERSION: str` (re-export `__version__`)
  - `Adapter(str, Enum)` with members `CLI`, `TELEGRAM`, `DASHBOARD`, `REACHY`
  - `DEFAULT_ADAPTER = Adapter.CLI`
- `src/jarvis/shared/exceptions.py`:
  - `class JarvisError(Exception)` — root
  - `class SessionNotFoundError(JarvisError)`
  - `class ConfigurationError(JarvisError)`

## Acceptance Criteria

- `from jarvis import __version__` returns `"0.1.0"`.
- `from jarvis.shared.constants import Adapter; Adapter.CLI.value == "cli"`.
- `JarvisError`, `SessionNotFoundError`, `ConfigurationError` all importable; subclass relationship holds.
- No imports from `jarvis.config`, `jarvis.sessions`, `jarvis.agents`, `jarvis.infrastructure`, `jarvis.cli` (enforced by import graph test in TASK-J001-009).
- All modified files pass project-configured lint/format checks with zero errors.

## Coach Validation

- `grep -R "from jarvis\." src/jarvis/shared/` returns no hits (shared imports nothing from the rest of jarvis).
- Adapter enum values are lowercase strings matching the adapter names used in `SessionManager.start_session` tests.
