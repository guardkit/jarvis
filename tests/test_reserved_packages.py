"""Tests for TASK-J001-010: Reserved-empty package namespaces per ADR-ARCH-006.

Validates that all eight reserved-empty packages are importable,
export nothing, and contain at most one line of content.
"""

from __future__ import annotations

import importlib
import pathlib
import sys
from types import ModuleType

import pytest

# Reserved-empty packages per ADR-ARCH-006.
#
# ``jarvis.tools`` was reserved-empty during Phase 1 but is **populated**
# in Phase 2 (FEAT-JARVIS-002): TASK-J002-015 wires the public tool
# surface (``assemble_tool_list``, re-exports from ``general``,
# ``capabilities``, ``dispatch``) into ``__init__.py``, so the empty-
# namespace contract no longer applies to it. The boundary discipline —
# domain modules consume the package surface, never the submodules —
# is enforced by :mod:`tests.test_import_graph` instead.
#
# ``jarvis.adapters`` followed the same trajectory in FEAT-JARVIS-003:
# TASK-J003-003 introduced ``jarvis.adapters.types.SwapStatus`` and
# TASK-J003-007 added ``LlamaSwapAdapter`` plus the public re-exports
# in ``__init__.py``. The empty-namespace contract no longer applies.
RESERVED_PACKAGES = [
    "jarvis.subagents",
    "jarvis.skills",
    "jarvis.routing",
    "jarvis.watchers",
    "jarvis.discovery",
    "jarvis.learning",
]

# Locate the src directory so we can inspect __init__.py files
_SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"


class TestAC001_AllPackagesImportable:
    """AC-001: All eight packages are importable — none raise ModuleNotFoundError."""

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_import_succeeds(self, package: str) -> None:
        """Importing the reserved package must not raise ModuleNotFoundError."""
        mod = importlib.import_module(package)
        assert mod is not None

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_package_in_sys_modules(self, package: str) -> None:
        """After import, the package should appear in sys.modules."""
        importlib.import_module(package)
        assert package in sys.modules


def _is_own_submodule(value: object, package: str) -> bool:
    """Return True if ``value`` is a submodule of ``package``.

    Loaded submodules become attributes of their parent package (Python
    import-system behaviour). They are *not* public symbols defined by
    ``__init__.py``, so they should be filtered out before asserting the
    package's namespace is empty.
    """
    return (
        isinstance(value, ModuleType)
        and getattr(value, "__name__", "").startswith(package + ".")
    )


class TestAC002_EmptyNamespace:
    """AC-002: ``__init__.py`` itself defines no public symbols.

    Submodules attached to the package by other imports (e.g.
    ``jarvis.tools.capabilities`` after TASK-J002-003) are filtered out —
    they are not "exports" of the package's ``__init__.py`` and would not
    be pulled in by ``from jarvis.<pkg> import *`` without ``__all__``.
    """

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_star_import_yields_nothing(self, package: str) -> None:
        """The package's own namespace (excl. submodules) must be empty.

        Either __all__ is not defined or __all__ is an empty list.
        """
        mod = importlib.import_module(package)
        all_exports = getattr(mod, "__all__", None)
        if all_exports is not None:
            assert all_exports == [], (
                f"{package}.__all__ should be empty, got {all_exports}"
            )
        else:
            public_names = [
                n
                for n in dir(mod)
                if not n.startswith("_")
                and not _is_own_submodule(getattr(mod, n, None), package)
            ]
            assert public_names == [], (
                f"{package} should have no public names, found {public_names}"
            )

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_dict_has_no_public_symbols(self, package: str) -> None:
        """Module __dict__ should contain no public non-submodule symbols."""
        mod = importlib.import_module(package)
        public = {
            k
            for k, v in mod.__dict__.items()
            if not k.startswith("_") and not _is_own_submodule(v, package)
        }
        assert public == set(), (
            f"{package} should have no public symbols, found {public}"
        )


class TestAC003_InitPyContentLimit:
    """AC-003: Each __init__.py is <=1 line of content (reserved comment only, no code)."""

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_init_py_at_most_one_line(self, package: str) -> None:
        """Each reserved package's __init__.py must have at most 1 non-blank line."""
        parts = package.split(".")
        init_path = _SRC_DIR / pathlib.Path(*parts) / "__init__.py"
        assert init_path.exists(), f"Missing {init_path}"

        content = init_path.read_text(encoding="utf-8")
        # Filter out blank/whitespace-only lines
        non_blank_lines = [
            line for line in content.splitlines() if line.strip()
        ]
        assert len(non_blank_lines) <= 1, (
            f"{init_path} has {len(non_blank_lines)} non-blank lines, "
            f"expected <=1. Content:\n{content}"
        )

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_init_py_contains_no_code(self, package: str) -> None:
        """__init__.py should contain only a comment (starting with #) or be empty."""
        parts = package.split(".")
        init_path = _SRC_DIR / pathlib.Path(*parts) / "__init__.py"
        content = init_path.read_text(encoding="utf-8").strip()
        if content:
            assert content.startswith("#"), (
                f"{init_path} contains non-comment content: {content!r}"
            )

    @pytest.mark.parametrize("package", RESERVED_PACKAGES)
    def test_init_py_no_imports(self, package: str) -> None:
        """__init__.py must not contain any import statements."""
        parts = package.split(".")
        init_path = _SRC_DIR / pathlib.Path(*parts) / "__init__.py"
        content = init_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                assert not stripped.startswith("import "), (
                    f"{init_path} contains import statement: {stripped}"
                )
                assert not stripped.startswith("from "), (
                    f"{init_path} contains from-import statement: {stripped}"
                )
