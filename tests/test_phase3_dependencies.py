"""Tests for TASK-J003-006: pyproject — provider SDKs + langgraph dev dep.

Covers all seven acceptance criteria:

  AC-001: [project.optional-dependencies].providers includes
          `google-genai>=0.3.0` (Gemini SDK).
  AC-002: `anthropic` is in base [project].dependencies.
  AC-003: [project.optional-dependencies].dev includes `langgraph-cli`.
  AC-004: `deepagents` pin remains `>=0.5.3,<0.6` (gated by ADR-ARCH-025).
  AC-005: `uv sync` completes; `google-genai`, `anthropic`, `langgraph`,
          `deepagents` are all installed.
  AC-006: No runtime code change — manifest-only task.
  AC-007: pyproject.toml is conventionally exempt from formatter; the
          task is green if `uv sync` succeeds.

The test class structure mirrors the AC list one-to-one so completion
promises in `player_turn_*.json` map directly onto pytest nodeids.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import subprocess
import sys
import tomllib
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Helpers (kept local — `test_phase2_dependencies.py` defines a similar set
# but cross-test-module imports are brittle and the helpers are tiny).
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"


def _load_pyproject() -> dict[str, Any]:
    """Load and return the parsed pyproject.toml."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _dep_name(spec: str) -> str:
    """Extract the canonical package name from a PEP 508 dependency string."""
    return re.split(r"[<>=!~;\[\s]", spec, maxsplit=1)[0].strip()


def _runtime_deps() -> list[str]:
    deps = _load_pyproject()["project"]["dependencies"]
    assert isinstance(deps, list)
    return deps


def _providers_extras() -> list[str]:
    opt = _load_pyproject()["project"]["optional-dependencies"]
    return list(opt.get("providers", []))


def _dev_extras() -> list[str]:
    opt = _load_pyproject()["project"]["optional-dependencies"]
    return list(opt.get("dev", []))


def _lower_bound(spec: str) -> tuple[int, ...]:
    """Parse the `>=X[.Y[.Z]]` lower bound from a PEP 508 spec.

    Returns a tuple of ints suitable for chronological comparison; raises
    AssertionError if no lower bound is present.
    """
    match = re.search(r">=\s*(\d+(?:\.\d+)*)", spec)
    assert match, f"no >= lower bound in {spec!r}"
    return tuple(int(p) for p in match.group(1).split("."))


# ===========================================================================
# AC-001: providers extras include google-genai
# ===========================================================================


class TestAC001ProvidersIncludesGoogleGenai:
    """AC-001: providers includes google-genai>=0.3.0 (the Gemini SDK)."""

    def test_google_genai_listed_in_providers(self) -> None:
        names = [_dep_name(s) for s in _providers_extras()]
        assert "google-genai" in names, (
            "[project.optional-dependencies].providers must include "
            f"`google-genai>=0.3.0`. Got: {names}"
        )

    def test_google_genai_lower_bound_at_least_0_3_0(self) -> None:
        spec = next(
            s for s in _providers_extras() if _dep_name(s) == "google-genai"
        )
        assert _lower_bound(spec) >= (0, 3, 0), (
            f"google-genai pin {spec!r} is below the AC-001 floor of 0.3.0"
        )

    def test_google_genai_distinct_from_langchain_google_genai(self) -> None:
        """The direct Gemini SDK (`google-genai`) is a separate package from
        the `langchain-google-genai` adapter; both must appear."""
        names = [_dep_name(s) for s in _providers_extras()]
        assert "google-genai" in names
        assert "langchain-google-genai" in names


# ===========================================================================
# AC-002: anthropic is in base dependencies
# ===========================================================================


class TestAC002AnthropicInBaseDependencies:
    """AC-002: `anthropic` is present in [project].dependencies."""

    def test_anthropic_listed_in_runtime_dependencies(self) -> None:
        names = [_dep_name(s) for s in _runtime_deps()]
        assert "anthropic" in names, (
            "[project].dependencies must include `anthropic`. "
            f"Got: {names}"
        )

    def test_anthropic_has_lower_bound(self) -> None:
        """Defensive: every base dep must pin a lower bound to avoid the
        well-known unbounded-import resolution drift (see TASK-REV-LES1)."""
        spec = next(s for s in _runtime_deps() if _dep_name(s) == "anthropic")
        assert ">=" in spec, f"anthropic pin missing lower bound: {spec!r}"

    def test_anthropic_module_importable(self) -> None:
        """`uv sync` must have made `anthropic` importable in the active venv."""
        mod = importlib.import_module("anthropic")
        assert mod is not None


# ===========================================================================
# AC-003: dev extras include langgraph-cli
# ===========================================================================


class TestAC003DevExtrasIncludesLanggraphCli:
    """AC-003: [project.optional-dependencies].dev includes `langgraph-cli`."""

    def test_dev_extras_group_exists(self) -> None:
        opt = _load_pyproject()["project"].get("optional-dependencies", {})
        assert "dev" in opt, (
            "[project.optional-dependencies].dev must exist (AC-003). "
            f"Got groups: {list(opt.keys())}"
        )

    def test_langgraph_cli_listed_in_dev_extras(self) -> None:
        names = [_dep_name(s) for s in _dev_extras()]
        assert "langgraph-cli" in names, (
            "[project.optional-dependencies].dev must include "
            f"`langgraph-cli`. Got: {names}"
        )

    def test_langgraph_cli_module_importable(self) -> None:
        """`uv sync --all-extras` must have made `langgraph_cli` importable."""
        mod = importlib.import_module("langgraph_cli")
        assert mod is not None


# ===========================================================================
# AC-004: deepagents pin is unchanged (gated by ADR-ARCH-025)
# ===========================================================================


class TestAC004DeepAgentsPinUnchanged:
    """AC-004: `deepagents` pin remains `>=0.5.3,<0.6` (no upgrade)."""

    EXPECTED_PIN = "deepagents>=0.5.3,<0.6"

    def test_deepagents_pin_exact_match(self) -> None:
        deps = _runtime_deps()
        spec = next((s for s in deps if _dep_name(s) == "deepagents"), None)
        assert spec is not None, "deepagents missing from [project].dependencies"
        assert spec == self.EXPECTED_PIN, (
            f"deepagents pin changed from ADR-ARCH-025: "
            f"expected {self.EXPECTED_PIN!r}, got {spec!r}"
        )

    def test_deepagents_not_promoted_or_relaxed_in_extras(self) -> None:
        """deepagents must not be smuggled in via an extras group with a
        looser pin that would shadow the base [project].dependencies pin."""
        opt = _load_pyproject()["project"].get("optional-dependencies", {})
        for group, specs in opt.items():
            for spec in specs:
                assert _dep_name(spec) != "deepagents", (
                    f"deepagents found in [project.optional-dependencies].{group} "
                    f"— ADR-ARCH-025 pins it in base dependencies only."
                )


# ===========================================================================
# AC-005: uv sync clean + four packages installed
# ===========================================================================


class TestAC005UvSyncAndPackagesInstalled:
    """AC-005: `uv sync` completes; the four AC packages are present."""

    REQUIRED_INSTALLED_PACKAGES = (
        "google-genai",
        "anthropic",
        "langgraph",
        "deepagents",
    )

    @pytest.mark.parametrize("pkg", REQUIRED_INSTALLED_PACKAGES)
    def test_required_package_in_uv_pip_list(self, pkg: str) -> None:
        """Mirrors the AC-005 grep:
        `uv pip list | grep -iE "(google-genai|anthropic|langgraph|deepagents)"`.
        """
        result = subprocess.run(
            ["uv", "pip", "list", "--format=freeze"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"`uv pip list` failed: {result.stderr}"
        )
        installed_names = {
            line.split("==", 1)[0].strip().lower()
            for line in result.stdout.splitlines()
            if "==" in line
        }
        assert pkg.lower() in installed_names, (
            f"required package {pkg!r} not found in `uv pip list`. "
            f"Installed (sample): {sorted(installed_names)[:10]}"
        )

    def test_uv_sync_with_all_extras_completes_clean(self) -> None:
        """`uv sync --all-extras` exits zero — the AC-005 baseline check."""
        result = subprocess.run(
            ["uv", "sync", "--all-extras"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=600,
        )
        assert result.returncode == 0, (
            f"`uv sync --all-extras` failed with exit {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# AC-006: no runtime code change
# ===========================================================================


class TestAC006NoRuntimeCodeChange:
    """AC-006: this is a manifest-only task; runtime code is unchanged.

    We assert this by importing a representative slice of the runtime
    package surface; if the manifest change inadvertently regressed any
    Phase 1/2 importable, this catches it.
    """

    @pytest.mark.parametrize(
        "module",
        [
            "jarvis",
            "deepagents",
            "langchain_core",
            "langgraph",
            "anthropic",
        ],
    )
    def test_runtime_module_imports(self, module: str) -> None:
        mod = importlib.import_module(module)
        assert mod is not None

    def test_jarvis_version_unchanged(self) -> None:
        """`jarvis.__version__` is set by the manifest's [project].version,
        which AC-006 says must not change."""
        result = subprocess.run(
            [sys.executable, "-c", "import jarvis; print(jarvis.__version__)"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT,
        )
        assert result.returncode == 0, (
            f"`import jarvis` regressed.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert result.stdout.strip() == "0.1.0", (
            f"jarvis.__version__ changed unexpectedly: {result.stdout!r}"
        )


# ===========================================================================
# AC-007: pyproject parses cleanly + uv sync still works
# ===========================================================================


class TestAC007PyprojectParsesCleanly:
    """AC-007: pyproject.toml is conventionally exempt from formatter; the
    task is green if it parses and `uv sync` succeeds."""

    def test_pyproject_parses_as_valid_toml(self) -> None:
        """If the manifest edits broke TOML syntax, `tomllib.load` raises."""
        with PYPROJECT.open("rb") as fh:
            data = tomllib.load(fh)
        assert "project" in data
        assert "dependencies" in data["project"]
        assert "optional-dependencies" in data["project"]

    def test_required_top_level_tables_intact(self) -> None:
        """Sanity check: build-system, hatch wheel layout, ruff/mypy/pytest
        config are still present after the manifest edits."""
        data = _load_pyproject()
        assert data["build-system"]["build-backend"] == "hatchling.build"
        assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
            "src/jarvis"
        ]
        assert "ruff" in data["tool"]
        assert "mypy" in data["tool"]
        assert "pytest" in data["tool"]
