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
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)


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
