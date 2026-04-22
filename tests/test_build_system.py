"""Tests for TASK-J001-001: pyproject.toml + build system + tool config.

Covers all five acceptance criteria:
  AC-001: pyproject.toml parses and editable install succeeds
  AC-002: deepagents version pin is in [0.5.3, 0.6)
  AC-003: ruff, mypy, pytest resolve after dev install
  AC-004: jarvis script entry-point resolves
  AC-005: .gitignore contains required patterns; .env not committable
"""

from __future__ import annotations

import importlib
import pathlib
import subprocess
import sys
import tomllib
from typing import Any, ClassVar

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
GITIGNORE = ROOT / ".gitignore"


def _load_pyproject() -> dict[str, Any]:
    """Load and return the parsed pyproject.toml."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


# ===================================================================
# AC-001: pyproject.toml parses; pip install -e ".[dev]" succeeds
# ===================================================================


class TestAC001PyprojectParses:
    """AC-001: pyproject.toml parses and contains required sections."""

    def test_pyproject_exists(self) -> None:
        assert PYPROJECT.exists(), "pyproject.toml must exist at project root"

    def test_pyproject_valid_toml(self) -> None:
        """pyproject.toml is valid TOML and can be parsed."""
        data = _load_pyproject()
        assert isinstance(data, dict)

    def test_has_build_system(self) -> None:
        data = _load_pyproject()
        assert "build-system" in data

    def test_build_backend_is_hatchling(self) -> None:
        data = _load_pyproject()
        assert data["build-system"]["build-backend"] == "hatchling.build"

    def test_hatchling_in_requires(self) -> None:
        data = _load_pyproject()
        requires = data["build-system"]["requires"]
        assert any("hatchling" in r for r in requires)

    def test_has_project_section(self) -> None:
        data = _load_pyproject()
        assert "project" in data

    def test_project_name_is_jarvis(self) -> None:
        data = _load_pyproject()
        assert data["project"]["name"] == "jarvis"

    def test_requires_python_312(self) -> None:
        data = _load_pyproject()
        rp = data["project"]["requires-python"]
        assert ">=3.12" in rp

    def test_has_dependencies(self) -> None:
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        assert isinstance(deps, list)
        assert len(deps) > 0


# ===================================================================
# AC-002: deepagents version pin in [0.5.3, 0.6)
# ===================================================================


class TestAC002DeepagentsPin:
    """AC-002: deepagents pin is exactly >=0.5.3,<0.6."""

    def test_deepagents_in_dependencies(self) -> None:
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        da_deps = [d for d in deps if d.startswith("deepagents")]
        assert len(da_deps) == 1, f"Expected exactly one deepagents dep, got {da_deps}"

    def test_deepagents_pin_lower_bound(self) -> None:
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        da_dep = next(d for d in deps if d.startswith("deepagents"))
        assert ">=0.5.3" in da_dep, f"Lower bound missing: {da_dep}"

    def test_deepagents_pin_upper_bound(self) -> None:
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        da_dep = next(d for d in deps if d.startswith("deepagents"))
        assert "<0.6" in da_dep, f"Upper bound missing: {da_dep}"

    def test_deepagents_pin_exact_format(self) -> None:
        """Coach validation: exact pin format is 'deepagents>=0.5.3,<0.6'."""
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        da_dep = next(d for d in deps if d.startswith("deepagents"))
        assert da_dep == "deepagents>=0.5.3,<0.6", f"Unexpected format: {da_dep}"

    def test_deepagents_importable(self) -> None:
        """deepagents is installed and importable."""
        deepagents = importlib.import_module("deepagents")
        assert deepagents is not None

    def test_deepagents_version_in_range(self) -> None:
        """Installed deepagents version is in [0.5.3, 0.6)."""
        from importlib.metadata import version as pkg_version

        ver = pkg_version("deepagents")
        parts = tuple(int(x) for x in ver.split(".")[:3])
        assert parts >= (0, 5, 3), f"deepagents {ver} < 0.5.3"
        assert parts < (0, 6, 0), f"deepagents {ver} >= 0.6"


# ===================================================================
# AC-003: ruff, mypy, pytest resolve after dev install
# ===================================================================


class TestAC003DevToolsResolve:
    """AC-003: ruff, mypy, pytest are available after dev install."""

    @pytest.mark.parametrize("tool", ["ruff", "mypy", "pytest"])
    def test_tool_version_resolves(self, tool: str) -> None:
        """Each dev tool's --version command succeeds."""
        result = subprocess.run(
            [sys.executable, "-m", tool, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Some tools use stdout, others stderr
        output = result.stdout + result.stderr
        assert result.returncode == 0, f"{tool} --version failed: {output}"

    def test_ruff_config_in_pyproject(self) -> None:
        data = _load_pyproject()
        assert "tool" in data
        assert "ruff" in data["tool"]
        assert data["tool"]["ruff"]["line-length"] == 100
        assert data["tool"]["ruff"]["target-version"] == "py312"

    def test_mypy_strict_in_pyproject(self) -> None:
        data = _load_pyproject()
        mypy = data["tool"]["mypy"]
        assert mypy["strict"] is True
        assert mypy["python_version"] == "3.12"
        assert mypy["warn_unused_ignores"] is True

    def test_pytest_config_in_pyproject(self) -> None:
        data = _load_pyproject()
        pytest_opts = data["tool"]["pytest"]["ini_options"]
        assert pytest_opts["asyncio_mode"] == "auto"
        assert "tests" in pytest_opts["testpaths"]

    def test_dev_extras_include_tools(self) -> None:
        """[project.optional-dependencies].dev includes ruff, mypy, pytest."""
        data = _load_pyproject()
        dev_deps = data["project"]["optional-dependencies"]["dev"]
        dep_names = [d.split(">")[0].split("<")[0].split("=")[0].strip() for d in dev_deps]
        for tool in ("pytest", "ruff", "mypy"):
            assert tool in dep_names, f"{tool} missing from [project.optional-dependencies].dev"


# ===================================================================
# AC-004: jarvis script entry-point resolves
# ===================================================================


class TestAC004EntryPoint:
    """AC-004: jarvis script entry-point wiring is correct."""

    def test_scripts_section_exists(self) -> None:
        data = _load_pyproject()
        assert "scripts" in data["project"]

    def test_jarvis_script_target(self) -> None:
        data = _load_pyproject()
        scripts = data["project"]["scripts"]
        assert scripts["jarvis"] == "jarvis.cli.main:main"

    def test_cli_module_importable(self) -> None:
        """The target module jarvis.cli.main can be imported."""
        mod = importlib.import_module("jarvis.cli.main")
        assert hasattr(mod, "main")

    def test_cli_main_is_callable(self) -> None:
        from jarvis.cli.main import main

        assert callable(main)

    def test_jarvis_version_command(self) -> None:
        """The version sub-command produces output."""
        result = subprocess.run(
            [sys.executable, "-m", "jarvis.cli.main", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "jarvis" in result.stdout.lower()
        assert "0.1.0" in result.stdout


# ===================================================================
# AC-005: .gitignore patterns; .env not committable
# ===================================================================


class TestAC005Gitignore:
    """AC-005: .gitignore contains all required patterns."""

    REQUIRED_PATTERNS: ClassVar[list[str]] = [
        ".venv/",
        ".env",
        "__pycache__/",
        ".ruff_cache/",
        ".mypy_cache/",
        "dist/",
        "build/",
        ".pytest_cache/",
    ]

    def test_gitignore_exists(self) -> None:
        assert GITIGNORE.exists(), ".gitignore must exist at project root"

    @pytest.mark.parametrize("pattern", REQUIRED_PATTERNS)
    def test_pattern_in_gitignore(self, pattern: str) -> None:
        content = GITIGNORE.read_text()
        lines = [line.strip() for line in content.splitlines()]
        assert pattern in lines, f"Pattern '{pattern}' missing from .gitignore"

    def test_env_not_committable(self) -> None:
        """Verify .env is in .gitignore (prevents accidental commit)."""
        content = GITIGNORE.read_text()
        lines = [line.strip() for line in content.splitlines()]
        # Must have '.env' as a standalone pattern (not just '.env.local')
        assert ".env" in lines, ".env must be in .gitignore as standalone pattern"


# ===================================================================
# Coach Validation extras
# ===================================================================


class TestCoachValidation:
    """Extra checks aligned with coach validation requirements."""

    def test_providers_has_all_init_chat_model_prefixes(self) -> None:
        """[project.optional-dependencies].providers lists required providers."""
        data = _load_pyproject()
        providers = data["project"]["optional-dependencies"]["providers"]
        provider_names = [p.split(">")[0].split("<")[0].split("=")[0].strip() for p in providers]
        assert "langchain-anthropic" in provider_names
        assert "langchain-google-genai" in provider_names

    def test_langchain_openai_in_main_deps(self) -> None:
        """langchain-openai is in main dependencies (default provider for llama-swap)."""
        data = _load_pyproject()
        deps = data["project"]["dependencies"]
        dep_names = [d.split(">")[0].split("<")[0].split("=")[0].strip() for d in deps]
        assert "langchain-openai" in dep_names

    def test_hatch_wheel_packages(self) -> None:
        """hatch build targets the src/jarvis layout."""
        data = _load_pyproject()
        packages = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
        assert "src/jarvis" in packages
