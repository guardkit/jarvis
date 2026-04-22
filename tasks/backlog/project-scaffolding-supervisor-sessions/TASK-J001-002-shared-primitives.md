---
id: TASK-J001-002
title: "Shared primitives \u2014 constants, Adapter enum, exception hierarchy"
task_type: declarative
parent_review: TASK-REV-J001
feature_id: FEAT-JARVIS-001
wave: 1
implementation_mode: direct
complexity: 3
dependencies: []
status: in_review
tags:
- declarative
- shared-layer
- exceptions
- adapters
- adr-arch-006
autobuild_state:
  current_turn: 2
  max_turns: 30
  worktree_path: /Users/richardwoollcott/Projects/appmilla_github/jarvis/.guardkit/worktrees/FEAT-JARVIS-001
  base_branch: main
  started_at: '2026-04-21T22:31:06.696957'
  last_updated: '2026-04-21T22:42:26.125438'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Tests failed due to infrastructure/environment issues (not code defects).\
      \ Test command: pytest tests/test_shared.py -v --tb=short. Remediation options:\
      \ (1) Add mock fixtures for external services, (2) Use SQLite for test database,\
      \ (3) Mark integration tests with @pytest.mark.integration and exclude via -m\
      \ 'not integration'. Error detail: Error detail:\n    from jarvis import __version__\n\
      E   ModuleNotFoundError: No module named 'jarvis'\n_______________________ TestVersion.test_version_is_str\
      \ ________________________\ntests/test_shared.py:31: in test_version_is_str\n\
      \    from jarvis import __version__\nResult:\nFAILED tests/test_shared.py::TestImportBoundaries::test_no_forbidden_runtime_imports\n\
      FAILED tests/test_shared.py::TestSharedReexports::test_all_exports - ModuleNo...\n\
      FAILED tests/test_shared.py::TestSharedReexports::test_versi...:\n  Error detail:\n\
      \    from jarvis import __version__\nE   ModuleNotFoundError: No module named\
      \ 'jarvis'\n_______________________ TestVersion.test_version_is_str ________________________\n\
      tests/test_shared.py:31: in test_version_is_str\n    from jarvis import __version__\n\
      Result:\nFAILED tests/test_shared.py::TestImportBoundaries::test_no_forbidden_runtime_imports\n\
      FAILED tests/test_shared.py::TestSharedReexports::test_all_exports - ModuleNo...\n\
      FAILED tests/test_shared.py::TestSharedReexports::test_version_reexport - Mod...\n\
      FAILED tests/test_shared.py::TestSharedReexports::test_default_adapter_reexport\n\
      ========================= 26 failed, 3 passed in 0.12s ========================="
    timestamp: '2026-04-21T22:31:06.696957'
    player_summary: Implemented src/jarvis/shared/ package with constants.py (VERSION,
      Adapter StrEnum, DEFAULT_ADAPTER), exceptions.py (JarvisError, ConfigurationError,
      SessionNotFoundError), and __init__.py re-exporting all public names. Updated
      src/jarvis/__init__.py to export __version__ = '0.1.0'. Fixed pyproject.toml
      build-backend typo (hatchling.backends -> hatchling.build) and types-click version
      constraint (>=8 -> >=7.1) inherited from TASK-J001-001. All files pass ruff
      lint, ruff format, and mypy strict c
    player_success: true
    coach_success: true
  - turn: 2
    decision: approve
    feedback: null
    timestamp: '2026-04-21T22:39:56.464188'
    player_summary: "Root cause of Turn 1 failures: the coach's test runner executes\
      \ `pytest` without `pip install -e .`, so in a src-layout project `import jarvis`\
      \ fails with ModuleNotFoundError. Fix: created tests/conftest.py that prepends\
      \ `<project-root>/src` to `sys.path` at pytest startup, which is the standard\
      \ solution for src-layout projects. All implementation files from Turn 1 are\
      \ unchanged and correct. Verified fix by creating a fresh venv with only pytest\
      \ installed (no editable install) \u2014 all 29 tests pas"
    player_success: true
    coach_success: true
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
