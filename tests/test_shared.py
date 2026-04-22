"""Tests for jarvis.shared — constants, Adapter enum, and exception hierarchy.

Covers acceptance criteria for TASK-J001-002:
  AC-001: `from jarvis import __version__` returns "0.1.0"
  AC-002: `from jarvis.shared.constants import Adapter; Adapter.CLI.value == "cli"`
  AC-003: Exception hierarchy importable and subclass relationships hold
  AC-004: No forbidden imports from config, sessions, agents, infrastructure, cli
  AC-005: Lint/format clean (verified separately via ruff)
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# AC-001: __version__
# ---------------------------------------------------------------------------
class TestVersion:
    """Verify jarvis.__version__ is set correctly."""

    def test_version_string(self) -> None:
        from jarvis import __version__

        assert __version__ == "0.1.0"

    def test_version_is_str(self) -> None:
        from jarvis import __version__

        assert isinstance(__version__, str)

    def test_version_matches_constants(self) -> None:
        from jarvis import __version__
        from jarvis.shared.constants import VERSION

        assert __version__ == VERSION


# ---------------------------------------------------------------------------
# AC-002: Adapter enum
# ---------------------------------------------------------------------------
class TestAdapter:
    """Verify the Adapter enum members and their values."""

    def test_cli_value(self) -> None:
        from jarvis.shared.constants import Adapter

        assert Adapter.CLI.value == "cli"

    def test_telegram_value(self) -> None:
        from jarvis.shared.constants import Adapter

        assert Adapter.TELEGRAM.value == "telegram"

    def test_dashboard_value(self) -> None:
        from jarvis.shared.constants import Adapter

        assert Adapter.DASHBOARD.value == "dashboard"

    def test_reachy_value(self) -> None:
        from jarvis.shared.constants import Adapter

        assert Adapter.REACHY.value == "reachy"

    def test_adapter_is_str_enum(self) -> None:
        from jarvis.shared.constants import Adapter

        # str enum means members are also strings
        assert isinstance(Adapter.CLI, str)
        assert Adapter.CLI == "cli"

    def test_adapter_members_count(self) -> None:
        from jarvis.shared.constants import Adapter

        assert len(Adapter) == 4

    def test_default_adapter_is_cli(self) -> None:
        from jarvis.shared.constants import DEFAULT_ADAPTER, Adapter

        assert DEFAULT_ADAPTER is Adapter.CLI

    def test_adapter_from_value(self) -> None:
        from jarvis.shared.constants import Adapter

        assert Adapter("cli") is Adapter.CLI
        assert Adapter("telegram") is Adapter.TELEGRAM

    def test_adapter_importable_from_shared(self) -> None:
        from jarvis.shared import Adapter

        assert Adapter.CLI.value == "cli"


# ---------------------------------------------------------------------------
# AC-003: Exception hierarchy
# ---------------------------------------------------------------------------
class TestExceptions:
    """Verify exception classes and their subclass relationships."""

    def test_jarvis_error_importable(self) -> None:
        from jarvis.shared.exceptions import JarvisError

        assert issubclass(JarvisError, Exception)

    def test_configuration_error_is_jarvis_error(self) -> None:
        from jarvis.shared.exceptions import ConfigurationError, JarvisError

        assert issubclass(ConfigurationError, JarvisError)
        assert issubclass(ConfigurationError, Exception)

    def test_session_not_found_error_is_jarvis_error(self) -> None:
        from jarvis.shared.exceptions import JarvisError, SessionNotFoundError

        assert issubclass(SessionNotFoundError, JarvisError)
        assert issubclass(SessionNotFoundError, Exception)

    def test_jarvis_error_is_not_configuration_error(self) -> None:
        from jarvis.shared.exceptions import ConfigurationError, JarvisError

        assert not issubclass(JarvisError, ConfigurationError)

    def test_jarvis_error_is_not_session_not_found_error(self) -> None:
        from jarvis.shared.exceptions import JarvisError, SessionNotFoundError

        assert not issubclass(JarvisError, SessionNotFoundError)

    def test_exceptions_are_catchable(self) -> None:
        from jarvis.shared.exceptions import ConfigurationError, JarvisError, SessionNotFoundError

        # ConfigurationError caught by JarvisError
        try:
            raise ConfigurationError("bad config")
        except JarvisError as exc:
            assert str(exc) == "bad config"

        # SessionNotFoundError caught by JarvisError
        try:
            raise SessionNotFoundError("missing session")
        except JarvisError as exc:
            assert str(exc) == "missing session"

    def test_exceptions_importable_from_shared(self) -> None:
        from jarvis.shared import ConfigurationError, JarvisError, SessionNotFoundError

        assert issubclass(ConfigurationError, JarvisError)
        assert issubclass(SessionNotFoundError, JarvisError)

    def test_configuration_error_instantiation(self) -> None:
        from jarvis.shared.exceptions import ConfigurationError

        exc = ConfigurationError("API key missing")
        assert str(exc) == "API key missing"
        assert isinstance(exc, Exception)

    def test_session_not_found_error_instantiation(self) -> None:
        from jarvis.shared.exceptions import SessionNotFoundError

        exc = SessionNotFoundError("cli-abc123def456")
        assert str(exc) == "cli-abc123def456"
        assert isinstance(exc, Exception)

    def test_exceptions_siblings_not_related(self) -> None:
        """ConfigurationError and SessionNotFoundError are siblings, not parent/child."""
        from jarvis.shared.exceptions import ConfigurationError, SessionNotFoundError

        assert not issubclass(ConfigurationError, SessionNotFoundError)
        assert not issubclass(SessionNotFoundError, ConfigurationError)


# ---------------------------------------------------------------------------
# AC-004: No forbidden imports
# ---------------------------------------------------------------------------
class TestImportBoundaries:
    """Verify that shared/ does not import from forbidden jarvis subpackages.

    Forbidden: jarvis.config, jarvis.sessions, jarvis.agents,
               jarvis.infrastructure, jarvis.cli
    """

    FORBIDDEN_PREFIXES = (
        "jarvis.config",
        "jarvis.sessions",
        "jarvis.agents",
        "jarvis.infrastructure",
        "jarvis.cli",
    )

    SHARED_MODULES = (
        "jarvis.shared",
        "jarvis.shared.constants",
        "jarvis.shared.exceptions",
    )

    def test_no_forbidden_runtime_imports(self) -> None:
        """After importing shared modules, no forbidden modules should appear in sys.modules."""
        # Take a snapshot before importing
        before = set(sys.modules.keys())

        # Force re-import of shared modules
        for mod_name in self.SHARED_MODULES:
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
            else:
                importlib.import_module(mod_name)

        after = set(sys.modules.keys())
        new_modules = after - before

        for mod in new_modules:
            for prefix in self.FORBIDDEN_PREFIXES:
                assert not mod.startswith(prefix), (
                    f"Importing shared modules pulled in forbidden module: {mod}"
                )

    def test_no_forbidden_static_imports_in_constants(self) -> None:
        """Parse constants.py AST and verify no forbidden import statements."""
        self._check_ast_imports("constants.py")

    def test_no_forbidden_static_imports_in_exceptions(self) -> None:
        """Parse exceptions.py AST and verify no forbidden import statements."""
        self._check_ast_imports("exceptions.py")

    def test_no_forbidden_static_imports_in_init(self) -> None:
        """Parse __init__.py AST and verify no forbidden import statements."""
        self._check_ast_imports("__init__.py")

    def _check_ast_imports(self, filename: str) -> None:
        shared_dir = Path(__file__).resolve().parent.parent / "src" / "jarvis" / "shared"
        filepath = shared_dir / filename
        assert filepath.exists(), f"{filepath} does not exist"

        tree = ast.parse(filepath.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in self.FORBIDDEN_PREFIXES:
                        assert not alias.name.startswith(prefix), (
                            f"{filename}: forbidden import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                for prefix in self.FORBIDDEN_PREFIXES:
                    assert not node.module.startswith(prefix), (
                        f"{filename}: forbidden from-import {node.module}"
                    )


# ---------------------------------------------------------------------------
# Shared __init__.py re-exports
# ---------------------------------------------------------------------------
class TestSharedReexports:
    """Verify that jarvis.shared.__init__.py re-exports all public names."""

    def test_all_exports(self) -> None:
        import jarvis.shared

        expected = {
            "Adapter",
            "ConfigurationError",
            "DEFAULT_ADAPTER",
            "JarvisError",
            "SessionNotFoundError",
            "VERSION",
        }
        assert set(jarvis.shared.__all__) == expected

    def test_version_reexport(self) -> None:
        from jarvis.shared import VERSION

        assert VERSION == "0.1.0"

    def test_default_adapter_reexport(self) -> None:
        from jarvis.shared import DEFAULT_ADAPTER, Adapter

        assert DEFAULT_ADAPTER is Adapter.CLI
