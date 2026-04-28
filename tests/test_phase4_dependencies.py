"""Tests for TASK-J004-002: pyproject.toml — nats-py and graphiti-core
extras (Phase 4 / FEAT-JARVIS-004).

Covers all six acceptance criteria recorded in
``tasks/backlog/feat-jarvis-004-fleet-registration-and-specialist-dispatch/
TASK-J004-002-pyproject-extras-nats-py-and-graphiti-core.md``:

  AC-001: ``[project.optional-dependencies]`` gains ``nats`` and
          ``graphiti`` groups.
  AC-002: The ``[providers]`` umbrella includes both new groups (re-exported
          via PEP 631 self-extras references).
  AC-003: ``uv sync`` succeeds against the updated pyproject.
  AC-004: ``uv run python -c "import nats; import graphiti_core"`` succeeds
          after ``uv sync --extra providers``.
  AC-005: Version pins explicitly bound — lower bound matches the
          ``nats-core`` / forge convention; upper bound is the next major.
  AC-006: All modified files pass project-configured lint/format checks
          (ruff) with zero errors. (Validated by the project's CI lint
          stage; this module enforces the structural shape ruff/Black
          would otherwise have to re-discover.)

The shape of these tests intentionally mirrors
``tests/test_phase2_dependencies.py`` — same helpers, same class-per-AC
layout — so reviewers can diff Phase 2 → Phase 4 invariants in a single
side-by-side read.
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
# Helpers (kept local so this file is self-contained — Phase 2 helpers are
# private to that module).
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


# ===========================================================================
# AC-001: `[nats]` and `[graphiti]` groups exist
# ===========================================================================


class TestAC001OptionalGroupsAdded:
    """AC-001: pyproject.toml gains ``nats`` and ``graphiti`` optional groups."""

    REQUIRED_PHASE4_GROUPS: ClassVar[list[str]] = ["nats", "graphiti"]

    @pytest.mark.parametrize("group", REQUIRED_PHASE4_GROUPS)
    def test_group_exists_in_optional_dependencies(self, group: str) -> None:
        """Each Phase 4 group is present under [project.optional-dependencies]."""
        opt = _optional_deps()
        assert group in opt, (
            f"Phase 4 optional-extras group '{group}' missing from "
            f"[project.optional-dependencies]. Got groups: {sorted(opt.keys())!r}"
        )

    def test_nats_group_lists_nats_py(self) -> None:
        """The `[nats]` group declares ``nats-py``."""
        nats_specs = _optional_deps()["nats"]
        names = [_dep_name(spec) for spec in nats_specs]
        assert "nats-py" in names, f"`[nats]` group missing nats-py — got: {nats_specs!r}"

    def test_graphiti_group_lists_graphiti_core(self) -> None:
        """The `[graphiti]` group declares ``graphiti-core``."""
        graphiti_specs = _optional_deps()["graphiti"]
        names = [_dep_name(spec) for spec in graphiti_specs]
        assert "graphiti-core" in names, (
            f"`[graphiti]` group missing graphiti-core — got: {graphiti_specs!r}"
        )


# ===========================================================================
# AC-002: `[providers]` umbrella includes both new groups
# ===========================================================================


class TestAC002ProvidersUmbrellaReExportsBothGroups:
    """AC-002: `[providers]` umbrella resolves to both new groups so a single
    ``pip install .[providers]`` / ``uv sync --extra providers`` installs
    every provider/integration this project can be configured to use (LCOI
    policy — TASK-REV-LES1 / LES1 §3).
    """

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

    def test_providers_self_references_graphiti_extra(self) -> None:
        """`[providers]` re-exports `[graphiti]` via a PEP 631 self-extras ref
        (`jarvis[graphiti]`) OR by listing the underlying packages directly.
        """
        providers = _optional_deps()["providers"]
        graphiti_referenced = any(
            spec.startswith("jarvis[graphiti]") or _dep_name(spec) == "graphiti-core"
            for spec in providers
        )
        assert graphiti_referenced, (
            "`[providers]` umbrella does not re-export `[graphiti]` — expected "
            "either `jarvis[graphiti]` self-reference or a direct graphiti-core "
            f"entry. Got: {providers!r}"
        )

    def test_providers_still_includes_phase1_phase3_pins(self) -> None:
        """The Phase 1 / Phase 3 provider pins remain in `[providers]` —
        Phase 4 is additive, never destructive."""
        providers = _optional_deps()["providers"]
        names = {_dep_name(spec) for spec in providers}
        for required in (
            "langchain-anthropic",
            "langchain-google-genai",
            "google-genai",
        ):
            assert required in names, (
                f"`[providers]` lost Phase 1/3 pin for {required!r} — Phase 4 "
                f"must be additive. Got: {providers!r}"
            )


# ===========================================================================
# AC-003: `uv sync` succeeds against the updated pyproject
# ===========================================================================


class TestAC003UvSyncSucceeds:
    """AC-003: ``uv sync`` succeeds (no resolution errors, no drift)."""

    def test_uv_lock_exists(self) -> None:
        """The lock file is present after `uv sync`."""
        assert UV_LOCK.exists(), "uv.lock must exist after `uv sync`"

    def test_uv_lock_resolves_phase4_packages(self) -> None:
        """The lock file resolved each Phase 4 package."""
        lock_text = UV_LOCK.read_text()
        for pkg in ("nats-py", "graphiti-core"):
            assert f'name = "{pkg}"' in lock_text, (
                f"uv.lock missing entry for {pkg!r} — was `uv sync --extra "
                f"providers` run after editing pyproject.toml?"
            )

    def test_uv_sync_completes_clean(self) -> None:
        """A fresh `uv sync` exits zero and reports no env drift on re-run.

        Two-phase pattern (mirrors Phase 2): the first call ensures the env
        matches the lock; the second must be a no-op. Any drift between
        pyproject.toml, uv.lock, and the venv shows up as a non-zero exit
        or an extra `+`/`-` line.
        """
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
# AC-004: import smoke check after `uv sync --extra providers`
# ===========================================================================


class TestAC004ImportSmokeCheck:
    """AC-004: ``import nats; import graphiti_core`` succeeds after
    ``uv sync --extra providers``.
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

    @pytest.mark.parametrize("module", ["nats", "graphiti_core"])
    def test_module_importable_in_active_venv(self, module: str) -> None:
        """Each Phase 4 module imports in the test venv (which `pytest` runs in
        after `uv sync --extra providers`).
        """
        mod = importlib.import_module(module)
        assert mod is not None


# ===========================================================================
# AC-005: explicit lower / upper bounds on each Phase 4 pin
# ===========================================================================


class TestAC005VersionPinsExplicitlyBound:
    """AC-005: Each Phase 4 pin declares both a lower and an upper bound.

    Lower bounds:
      - nats-py: matches the sibling `nats-core/pyproject.toml` runtime dep
        (`nats-py>=2.0`). Mismatched majors are the FEAT-J004 #1 likely
        contract-test failure mode (TASK-J004-002 implementation notes).
      - graphiti-core: 0.x line; lower bound `>=0.9` is the first minor
        shipping the pydantic-2 / FalkorDB combo Jarvis relies on.

    Upper bounds: the *next major* in both cases, matching the Phase 1
    `<2` convention applied across the langchain-* pins.
    """

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
            f"nats-py pin {spec!r} missing `<3` next-major cap — every "
            "Phase 4 pin must explicitly bound the upper edge to protect "
            "against the next major-bump churn (Phase 1 langchain-* convention)."
        )

    def test_graphiti_core_lower_bound_present(self) -> None:
        """`graphiti-core` declares an explicit lower bound."""
        spec = self._spec_for("graphiti", "graphiti-core")
        assert ">=" in spec, f"graphiti-core needs an explicit lower bound: {spec!r}"
        match = re.search(r">=\s*(\d+)\.(\d+)", spec)
        assert match, f"graphiti-core pin missing >=X.Y lower bound: {spec!r}"

    def test_graphiti_core_upper_bound_caps_at_next_major(self) -> None:
        """`graphiti-core` upper bound caps at `<1` (the next major after 0.x)."""
        spec = self._spec_for("graphiti", "graphiti-core")
        assert "<1" in spec, (
            f"graphiti-core pin {spec!r} missing `<1` next-major cap — "
            "graphiti-core is on its 0.x stabilisation path and a 1.0 bump "
            "is expected to ship breaking surface changes."
        )


# ===========================================================================
# AC-006: lint/format hygiene on the modified files
# ===========================================================================


class TestAC006LintFormatPasses:
    """AC-006: ``ruff check`` reports zero errors against the touched files.

    `pyproject.toml` has no lintable code surface (it is TOML, not Python),
    but the test files in this commit pass ruff's configured ruleset.
    """

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
        """`pyproject.toml` round-trips through `tomllib` — i.e. it is
        syntactically valid TOML, which is the lint contract for `.toml`
        files (no ruff equivalent)."""
        data = _load_pyproject()
        assert "project" in data
        assert "optional-dependencies" in data["project"]
