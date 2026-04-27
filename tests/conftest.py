"""Root conftest — shared fixtures for the Jarvis test suite.

This is the standard approach for src-layout projects: pytest discovers this
conftest.py at startup and prepends ``<project-root>/src`` to ``sys.path`` so
that ``import jarvis`` resolves to the local source tree regardless of whether
the package has been installed in the active environment.

Fixtures provided:

- :func:`_isolate_dotenv` (autouse) — chdirs to a tmp dir so ``JarvisConfig``'s
  ``env_file=".env"`` cannot pick up the operator's real ``.env`` during test
  runs
- :func:`fake_llm` — deterministic ``FakeListChatModel`` (no network)
- :func:`test_config` — ``JarvisConfig`` with sensible defaults and a fake endpoint
- :func:`in_memory_store` — fresh ``InMemoryStore``, cleared after each test
- :func:`app_state` — placeholder for composed application state (future)
"""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Inject src/ into sys.path so tests can ``from jarvis import ...`` even
# when running bare ``pytest`` without an editable install.
# ---------------------------------------------------------------------------
_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)


# ---------------------------------------------------------------------------
# Pre-seed a stub OPENAI_API_KEY at conftest module load so the OpenAI SDK
# does not crash during test collection.
#
# DDR-012 mandates that ``jarvis_reasoner`` compile its LangGraph at module
# import time, which calls ``init_chat_model("openai:jarvis-reasoner")``,
# which constructs ``ChatOpenAI(...)``, which raises ``openai.OpenAIError``
# if ``OPENAI_API_KEY`` is not in the process environment. Test modules
# that import anything from ``jarvis.agents.subagents`` (directly or via
# the package ``__init__``) trigger that import chain during pytest's
# collection phase — *before* any fixture, autouse or otherwise, has had
# a chance to run.
#
# Setting it here (at conftest module load, which pytest evaluates before
# collecting any test module) is the only safe place to pre-seed the stub.
# The value is obviously fake so it cannot be confused with a real key, and
# no test in this suite makes a real network call against the production
# OpenAI endpoint (fakes are routed via ``FakeListChatModel`` or the
# ``http://fake-endpoint/v1`` base URL). Production environments inject
# real keys via ``.env``; ``langgraph dev`` continues to fail loudly when
# the operator has not configured one (DDR-012's "fail fast" promise — the
# fix is scoped to the test environment only).
#
# Use ``setdefault`` so a real key in the developer's shell environment
# (e.g. someone debugging a single test against the live SDK) is not
# clobbered. The autouse ``_isolate_dotenv`` fixture below then re-asserts
# the stub per-test via ``monkeypatch.setenv`` so individual tests start
# from a known stub value, while still honouring per-test ``patch.dict``
# overrides (which wrap the test body and therefore win for that test).
# ---------------------------------------------------------------------------
_OPENAI_API_KEY_TEST_STUB = "stub-for-tests-no-real-calls-do-not-use-in-prod"
os.environ.setdefault("OPENAI_API_KEY", _OPENAI_API_KEY_TEST_STUB)


# ---------------------------------------------------------------------------
# Autouse: isolate every test from the operator's real ``.env`` file.
#
# ``JarvisConfig`` is a ``pydantic_settings.BaseSettings`` subclass with
# ``env_file=".env"``, resolved relative to the current working directory.
# When pytest runs from the project root and the operator has populated
# ``.env`` with their live provider credentials, every ``JarvisConfig()``
# call silently absorbs those values — breaking tests that assert
# missing-config failure paths (e.g. ``TestAC005ValidateProviderKeys``).
#
# ``monkeypatch.chdir(tmp_path)`` resolves pydantic's relative ``.env``
# lookup to a nonexistent file for the duration of each test, restoring the
# original cwd on teardown. Tests that need a specific file layout (subprocess
# tests in ``test_build_system.py`` / ``test_developer_surface.py``) either
# pass ``cwd=str(ROOT)`` explicitly or use absolute path constants, so chdir
# does not disturb them.
#
# The fixture also re-asserts the stub ``OPENAI_API_KEY`` per-test via
# ``monkeypatch.setenv`` so individual tests start from a known stub value
# even after a previous test cleared the env. See the module-level
# ``setdefault`` block above for the rationale; per-test ``patch.dict``
# overrides still win because they wrap the test body and the inner
# clear-and-replace runs after fixture setup.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", _OPENAI_API_KEY_TEST_STUB)


# ---------------------------------------------------------------------------
# Autouse: snapshot + restore the dispatch module's DDR-014 Layer-2 hooks
# around every test (TASK-J003-FIX-001).
#
# ``lifecycle.build_app_state`` now assigns ``dispatch._current_session_hook``
# and ``dispatch._async_subagent_frame_hook`` to close the FEAT-JARVIS-003
# review's Finding F1 ("Layer 2 dormant in production"). Tests that exercise
# ``build_app_state`` (e.g. ``tests/test_lifecycle_startup_phase3.py``)
# therefore mutate module-level state on the import-shared
# ``jarvis.tools.dispatch`` module — without a per-test save/restore the
# hooks bleed into downstream test modules whose Layer-1 assertions assume
# the dormant default (e.g. ``tests/test_escalate_to_frontier.py``).
#
# Per-file fixtures (``reset_layer2_hooks``) cover the modules that wire
# hooks intentionally; this autouse fixture covers every other test by
# default so a future ``build_app_state``-using test does not silently
# poison sibling modules. Cost is two attribute reads + two writes per
# test, which is negligible.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _restore_dispatch_layer2_hooks() -> Generator[None, None, None]:
    from jarvis.tools import dispatch as _dispatch

    original_session_hook = _dispatch._current_session_hook
    original_frame_hook = _dispatch._async_subagent_frame_hook
    yield
    _dispatch._current_session_hook = original_session_hook
    _dispatch._async_subagent_frame_hook = original_frame_hook


# ---------------------------------------------------------------------------
# fake_llm — deterministic chat model for unit tests
# ---------------------------------------------------------------------------
@pytest.fixture()
def fake_llm() -> Any:
    """Return a ``FakeListChatModel`` with canned responses.

    The model cycles through a predefined list of responses without making
    any network calls.  Useful for testing agent logic deterministically.

    Returns:
        A ``FakeListChatModel`` instance that returns ``"Canned response 1"``
        on the first invocation and ``"Canned response 2"`` on subsequent ones.
    """
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    return FakeListChatModel(
        responses=[
            "Canned response 1",
            "Canned response 2",
            "Canned response 3",
        ],
    )


# ---------------------------------------------------------------------------
# test_config — JarvisConfig with safe defaults (no real provider keys)
# ---------------------------------------------------------------------------
@pytest.fixture()
def test_config() -> Any:
    """Return a ``JarvisConfig`` with sensible test defaults.

    Uses ``openai_base_url="http://fake-endpoint/v1"`` so that
    ``validate_provider_keys()`` passes without requiring real credentials.

    Returns:
        A ``JarvisConfig`` instance that validates cleanly.
    """
    from jarvis.config.settings import JarvisConfig

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
        )
    # Validate provider keys to ensure no ConfigurationError
    cfg.validate_provider_keys()
    return cfg


# ---------------------------------------------------------------------------
# in_memory_store — fresh LangGraph InMemoryStore per test
# ---------------------------------------------------------------------------
@pytest.fixture()
def in_memory_store() -> Generator[Any, None, None]:
    """Yield a fresh ``InMemoryStore`` and clear it after the test.

    Provides test isolation: each test gets its own empty store that is
    cleaned up on teardown.
    """
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore()
    yield store
    # InMemoryStore has no explicit close; the reference is simply dropped.


# ---------------------------------------------------------------------------
# app_state — placeholder for composed application state
# ---------------------------------------------------------------------------
@pytest.fixture()
def app_state() -> dict[str, Any]:
    """Return a placeholder ``AppState`` dict.

    This fixture will be expanded when the full application state model
    is implemented.  For now it returns a minimal dictionary that downstream
    tests can extend.
    """
    return {
        "config": None,
        "store": None,
    }
