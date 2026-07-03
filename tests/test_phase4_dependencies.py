"""Dependency-contract tests for the live-transport + memory write path.

Originally TASK-J004-002 (Phase 4 / FEAT-JARVIS-004) declared a ``nats`` extra
(``nats-py``) and a ``graphiti`` extra (``graphiti-core``). The FEAT-MEM-09
fleet-wide cutover migrated Jarvis's routing-history writes off Graphiti to
fleet-memory (published as ``MemoryEpisodeV1`` events over NATS via the
already-declared ``nats-core`` base dependency), so ``graphiti-core`` and the
``[graphiti]`` extra were **removed**. This module now asserts:

  AC-001: ``[project.optional-dependencies]`` declares the ``nats`` group, and
          the retired ``graphiti`` group is absent.
  AC-002: The ``[providers]`` umbrella re-exports ``[nats]`` and no longer
          references ``graphiti-core``.
  AC-003: ``uv sync`` succeeds and the lock resolves the NATS packages.
  AC-004: ``import nats`` and ``import nats_core`` succeed in the active venv;
          ``graphiti-core`` is no longer a declared dependency.
  AC-005: The ``nats-py`` pin is explicitly lower/upper bounded.
  AC-006: All modified files pass ruff and pyproject.toml is valid TOML.
"""

from __future__ import annotations

import importlib
import pathlib
import re
import subprocess
import tomllib
from typing import Any, ClassVar

import pytest

# ---------------------------------------------------------------------------
# Helpers (kept local so this file is self-contained).
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
UV_LOCK = ROOT / "uv.lock"


def _load_pyproject() -> dict[str, Any]:
    """Load and return the parsed ``pyproject.toml``."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _dep_name(spec: str) -> str:
    """Extract the canonical package name from a PEP 508 dependency string."""
    return re.split(r"[<>=!~;\[\s]", spec, maxsplit=1)[0].strip()


def _optional_deps() -> dict[str, list[str]]:
    """Return ``[project.optional-dependencies]`` as a plain mapping."""
    opt = _load_pyproject()["project"].get("optional-dependencies", {})
    assert isinstance(opt, dict)
    return opt


def _base_deps() -> list[str]:
    """Return ``[project.dependencies]`` as a list of PEP 508 specs."""
    return list(_load_pyproject()["project"].get("dependencies", []))


# ===========================================================================
# AC-001: `[nats]` group exists; retired `[graphiti]` group is gone
# ===========================================================================


class TestAC001OptionalGroups:
    """AC-001: the ``nats`` extra remains; the ``graphiti`` extra was retired."""

    def test_nats_group_exists(self) -> None:
        """The `[nats]` group is present under [project.optional-dependencies]."""
        opt = _optional_deps()
        assert "nats" in opt, (
            "optional-extras group 'nats' missing from "
            f"[project.optional-dependencies]. Got: {sorted(opt.keys())!r}"
        )

    def test_nats_group_lists_nats_py(self) -> None:
        """The `[nats]` group declares ``nats-py``."""
        nats_specs = _optional_deps()["nats"]
        names = [_dep_name(spec) for spec in nats_specs]
        assert "nats-py" in names, f"`[nats]` group missing nats-py — got: {nats_specs!r}"

    def test_graphiti_group_removed(self) -> None:
        """The retired `[graphiti]` group must NOT exist (FEAT-MEM-09 cutover)."""
        opt = _optional_deps()
        assert "graphiti" not in opt, (
            "`[graphiti]` optional-extras group must be removed after the "
            f"fleet-memory cutover. Got groups: {sorted(opt.keys())!r}"
        )


# ===========================================================================
# AC-002: `[providers]` umbrella re-exports [nats]; no graphiti-core
# ===========================================================================


class TestAC002ProvidersUmbrella:
    """AC-002: `[providers]` re-exports `[nats]` and drops graphiti-core."""

    def test_providers_self_references_nats_extra(self) -> None:
        """`[providers]` re-exports `[nats]` via a PEP 631 self-extras ref
        (`jarvis[nats]`) OR by listing the underlying packages directly.
        """
        providers = _optional_deps()["providers"]
        nats_referenced = any(
            spec.startswith("jarvis[nats]") or _dep_name(spec) == "nats-py" for spec in providers
        )
        assert nats_referenced, (
            "`[providers]` umbrella does not re-export `[nats]` — expected "
            "either `jarvis[nats]` self-reference or a direct nats-py entry. "
            f"Got: {providers!r}"
        )

    def test_providers_does_not_reference_graphiti(self) -> None:
        """`[providers]` must not re-export the retired `[graphiti]` extra."""
        providers = _optional_deps()["providers"]
        offenders = [
            spec
            for spec in providers
            if spec.startswith("jarvis[graphiti]") or _dep_name(spec) == "graphiti-core"
        ]
        assert not offenders, (
            "`[providers]` still references the retired graphiti extra: "
            f"{offenders!r}"
        )

    def test_providers_still_includes_phase1_phase3_pins(self) -> None:
        """The Phase 1 / Phase 3 provider pins remain in `[providers]`."""
        providers = _optional_deps()["providers"]
        names = {_dep_name(spec) for spec in providers}
        for required in (
            "langchain-anthropic",
            "langchain-google-genai",
            "google-genai",
        ):
            assert required in names, (
                f"`[providers]` lost the pin for {required!r} — got: {providers!r}"
            )


# ===========================================================================
# AC-003: `uv sync` succeeds against the updated pyproject
# ===========================================================================


class TestAC003UvSyncSucceeds:
    """AC-003: ``uv sync`` succeeds (no resolution errors, no drift)."""

    def test_uv_lock_exists(self) -> None:
        """The lock file is present after `uv sync`."""
        assert UV_LOCK.exists(), "uv.lock must exist after `uv sync`"

    def test_uv_lock_resolves_nats_packages(self) -> None:
        """The lock file resolved the NATS packages (live + core)."""
        lock_text = UV_LOCK.read_text()
        for pkg in ("nats-py", "nats-core"):
            assert f'name = "{pkg}"' in lock_text, (
                f"uv.lock missing entry for {pkg!r} — was `uv sync` run after "
                f"editing pyproject.toml?"
            )

    def test_uv_sync_completes_clean(self) -> None:
        """A fresh `uv sync` exits zero and reports no env drift on re-run."""
        first = subprocess.run(
            ["uv", "sync"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=300,
        )
        assert first.returncode == 0, (
            f"`uv sync` failed with exit {first.returncode}.\n"
            f"stdout:\n{first.stdout}\nstderr:\n{first.stderr}"
        )
        second = subprocess.run(
            ["uv", "sync"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=300,
        )
        assert second.returncode == 0, f"second `uv sync` failed:\n{second.stdout}\n{second.stderr}"
        combined = second.stdout + second.stderr
        assert " + " not in combined and " - " not in combined, (
            f"second `uv sync` showed package changes — env drifted:\n{combined}"
        )


# ===========================================================================
# AC-004: import smoke check + graphiti-core removal
# ===========================================================================


class TestAC004ImportSmokeCheck:
    """AC-004: ``import nats`` and ``import nats_core`` succeed; graphiti-core
    is no longer a declared dependency.
    """

    def test_uv_sync_extra_providers_succeeds(self) -> None:
        """The `--extra providers` flag resolves cleanly."""
        result = subprocess.run(
            ["uv", "sync", "--extra", "providers"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"`uv sync --extra providers` failed with exit {result.returncode}.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    @pytest.mark.parametrize("module", ["nats", "nats_core"])
    def test_module_importable_in_active_venv(self, module: str) -> None:
        """The NATS live client and the memory-write helper both import."""
        mod = importlib.import_module(module)
        assert mod is not None

    def test_graphiti_core_not_a_declared_dependency(self) -> None:
        """``graphiti-core`` must not appear in base deps or any extra."""
        base = [_dep_name(s) for s in _base_deps()]
        assert "graphiti-core" not in base, (
            f"graphiti-core must be removed from base dependencies — got: {base!r}"
        )
        for group, specs in _optional_deps().items():
            names = [_dep_name(s) for s in specs]
            assert "graphiti-core" not in names, (
                f"graphiti-core must be removed from the `[{group}]` extra — "
                f"got: {specs!r}"
            )


# ===========================================================================
# AC-005: explicit lower / upper bounds on the nats-py pin
# ===========================================================================


class TestAC005VersionPinsExplicitlyBound:
    """AC-005: the ``nats-py`` pin declares both a lower and an upper bound."""

    def _spec_for(self, group: str, pkg: str) -> str:
        specs = _optional_deps()[group]
        return next(s for s in specs if _dep_name(s) == pkg)

    def test_nats_py_lower_bound_matches_nats_core_convention(self) -> None:
        """`nats-py` lower bound is `>=2.0` (sibling `nats-core` convention)."""
        spec = self._spec_for("nats", "nats-py")
        match = re.search(r">=\s*(\d+)\.(\d+)", spec)
        assert match, f"nats-py pin missing >=X.Y lower bound: {spec!r}"
        major, minor = int(match.group(1)), int(match.group(2))
        assert (major, minor) >= (2, 0), f"nats-py pin {spec!r} below nats-core convention (>=2.0)"

    def test_nats_py_upper_bound_caps_at_next_major(self) -> None:
        """`nats-py` upper bound caps at `<3` (the next major)."""
        spec = self._spec_for("nats", "nats-py")
        assert "<3" in spec, (
            f"nats-py pin {spec!r} missing `<3` next-major cap — every pin "
            "must explicitly bound the upper edge (Phase 1 langchain-* convention)."
        )


# ===========================================================================
# AC-006: lint/format hygiene on the modified files
# ===========================================================================


class TestAC006LintFormatPasses:
    """AC-006: ``ruff check`` reports zero errors against the touched files."""

    TOUCHED_PYTHON_FILES: ClassVar[list[str]] = [
        "tests/test_phase2_dependencies.py",
        "tests/test_phase4_dependencies.py",
    ]

    @pytest.mark.parametrize("rel_path", TOUCHED_PYTHON_FILES)
    def test_ruff_check_clean(self, rel_path: str) -> None:
        """`ruff check <file>` exits zero against each touched Python file."""
        target = ROOT / rel_path
        result = subprocess.run(
            ["uv", "run", "ruff", "check", str(target)],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"`ruff check {rel_path}` reported issues:\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_pyproject_toml_parseable(self) -> None:
        """`pyproject.toml` round-trips through `tomllib` (valid TOML)."""
        data = _load_pyproject()
        assert "project" in data
        assert "optional-dependencies" in data["project"]
