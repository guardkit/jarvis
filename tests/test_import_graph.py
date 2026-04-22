"""Import-graph invariant tests — catch forbidden cross-layer imports.

TASK-J001-009 acceptance criteria:
    AC-002: pytest tests/test_import_graph.py -v passes; any accidental
            ``from jarvis.adapters ...`` or ``from jarvis.tools ...`` in
            domain modules is caught.

Domain modules (core logic) MUST NOT import from reserved-empty packages
(``jarvis.adapters``, ``jarvis.tools``, ``jarvis.subagents``,
``jarvis.skills``, ``jarvis.routing``, ``jarvis.watchers``,
``jarvis.discovery``, ``jarvis.learning``).

This invariant protects the hexagonal architecture boundary (ADR-ARCH-002,
ADR-ARCH-006): domain logic never depends on adapter/tool implementations
that have not yet been created.

Two complementary strategies are used:

1. **Static analysis** — parse the AST of every ``.py`` file in domain
   packages and assert no ``import`` or ``from`` statement references a
   reserved package.

2. **Runtime analysis** — import each domain module and verify that no
   reserved package appears in ``sys.modules`` as a side-effect.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import sys
from typing import ClassVar

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SRC_DIR = pathlib.Path(__file__).resolve().parent.parent / "src"
_JARVIS_DIR = _SRC_DIR / "jarvis"

# Domain modules — core logic that must not import from reserved packages
DOMAIN_PACKAGES = [
    "jarvis.shared",
    "jarvis.config",
    "jarvis.prompts",
    "jarvis.agents",
    "jarvis.sessions",
    "jarvis.infrastructure",
    "jarvis.cli",
]

# Reserved-empty packages — adapter/tool layer that domain must not import
RESERVED_PACKAGES = [
    "jarvis.adapters",
    "jarvis.tools",
    "jarvis.subagents",
    "jarvis.skills",
    "jarvis.routing",
    "jarvis.watchers",
    "jarvis.discovery",
    "jarvis.learning",
]

# Flattened prefixes for matching import targets
FORBIDDEN_PREFIXES = tuple(RESERVED_PACKAGES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _python_files_in_package(package_dotpath: str) -> list[pathlib.Path]:
    """Return all .py files in a package directory (recursively)."""
    parts = package_dotpath.split(".")
    pkg_dir = _JARVIS_DIR / pathlib.Path(*parts[1:])  # strip 'jarvis.' prefix
    if not pkg_dir.exists():
        return []
    return sorted(pkg_dir.rglob("*.py"))


def _extract_imports(filepath: pathlib.Path) -> list[str]:
    """Parse a .py file and return all imported module names."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


# ---------------------------------------------------------------------------
# Static AST analysis
# ---------------------------------------------------------------------------

class TestStaticImportGraph:
    """Verify no domain module statically imports from reserved packages."""

    @pytest.mark.parametrize("domain_package", DOMAIN_PACKAGES)
    def test_no_forbidden_static_imports(self, domain_package: str) -> None:
        """Parse all .py files in the domain package and check imports."""
        py_files = _python_files_in_package(domain_package)
        assert len(py_files) > 0, (
            f"Expected .py files in {domain_package}"
        )

        violations: list[str] = []
        for filepath in py_files:
            imports = _extract_imports(filepath)
            for imp in imports:
                for prefix in FORBIDDEN_PREFIXES:
                    if imp == prefix or imp.startswith(prefix + "."):
                        rel = filepath.relative_to(_SRC_DIR)
                        violations.append(
                            f"{rel}: imports {imp!r} (forbidden prefix {prefix!r})"
                        )

        assert violations == [], (
            f"Forbidden imports found in {domain_package}:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize(
        "reserved_name",
        ["jarvis.adapters", "jarvis.tools"],
    )
    def test_specific_reserved_not_imported_by_any_domain_module(
        self, reserved_name: str
    ) -> None:
        """Explicitly test that jarvis.adapters and jarvis.tools are never imported."""
        violations: list[str] = []
        for domain_package in DOMAIN_PACKAGES:
            for filepath in _python_files_in_package(domain_package):
                imports = _extract_imports(filepath)
                for imp in imports:
                    if imp == reserved_name or imp.startswith(reserved_name + "."):
                        rel = filepath.relative_to(_SRC_DIR)
                        violations.append(f"{rel}: imports {imp!r}")

        assert violations == [], (
            f"{reserved_name} must not be imported by domain modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Runtime import analysis
# ---------------------------------------------------------------------------

class TestRuntimeImportGraph:
    """Verify no domain module transitively pulls in reserved packages at runtime."""

    @pytest.mark.parametrize("domain_package", DOMAIN_PACKAGES)
    def test_no_forbidden_runtime_imports(self, domain_package: str) -> None:
        """Importing the domain package must not pull reserved packages into sys.modules."""
        # Snapshot current modules
        before = set(sys.modules.keys())

        # Force import (or reload if already imported)
        mod = importlib.import_module(domain_package)
        assert mod is not None

        after = set(sys.modules.keys())
        new_modules = after - before

        for new_mod in new_modules:
            for prefix in FORBIDDEN_PREFIXES:
                if new_mod == prefix or new_mod.startswith(prefix + "."):
                    pytest.fail(
                        f"Importing {domain_package} pulled in {new_mod!r} "
                        f"(forbidden reserved package {prefix!r})"
                    )


# ---------------------------------------------------------------------------
# Shared module boundary — shared must not import from higher-level modules
# ---------------------------------------------------------------------------

class TestSharedModuleBoundary:
    """jarvis.shared must not import from any other jarvis subpackage."""

    HIGHER_PACKAGES: ClassVar[list[str]] = [
        "jarvis.config",
        "jarvis.sessions",
        "jarvis.agents",
        "jarvis.infrastructure",
        "jarvis.cli",
        "jarvis.prompts",
    ]

    def test_shared_does_not_import_from_higher_packages(self) -> None:
        """Parse shared/ AST and verify no imports from higher-level packages."""
        py_files = _python_files_in_package("jarvis.shared")
        violations: list[str] = []

        for filepath in py_files:
            imports = _extract_imports(filepath)
            for imp in imports:
                for higher in self.HIGHER_PACKAGES:
                    if imp == higher or imp.startswith(higher + "."):
                        rel = filepath.relative_to(_SRC_DIR)
                        violations.append(f"{rel}: imports {imp!r}")

        assert violations == [], (
            "jarvis.shared must not import from higher-level packages:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


# ---------------------------------------------------------------------------
# Cross-check: reserved packages themselves are empty (no outbound imports)
# ---------------------------------------------------------------------------

class TestReservedPackagesAreLeaves:
    """Reserved packages must not import any jarvis subpackages."""

    @pytest.mark.parametrize("reserved", RESERVED_PACKAGES)
    def test_reserved_package_has_no_jarvis_imports(self, reserved: str) -> None:
        """Reserved packages __init__.py must not import from jarvis.*."""
        parts = reserved.split(".")
        init_path = _JARVIS_DIR / pathlib.Path(*parts[1:]) / "__init__.py"
        if not init_path.exists():
            pytest.skip(f"{init_path} does not exist")

        imports = _extract_imports(init_path)
        jarvis_imports = [i for i in imports if i.startswith("jarvis")]
        assert jarvis_imports == [], (
            f"{reserved}/__init__.py must not import jarvis modules, "
            f"found: {jarvis_imports}"
        )
