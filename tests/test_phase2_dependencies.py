"""Tests for TASK-J002-023: pyproject + dependency management (Phase 2).

Covers all four acceptance criteria:
  AC-001: pyproject.toml adds langchain-tavily (DDR-006), asteval (DDR-007),
          nats-core (Pydantic payload imports), and pyyaml.
  AC-002: nats-py is NOT in [project.dependencies] — Phase 2 scope invariant.
  AC-003: uv lock is regenerated; uv sync completes clean.
  AC-004: Phase 1 dependencies are untouched (no removals, no version-pin
          changes).
"""

from __future__ import annotations

import importlib
import pathlib
import re
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
UV_LOCK = ROOT / "uv.lock"


def _load_pyproject() -> dict[str, Any]:
    """Load and return the parsed pyproject.toml."""
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _dep_name(spec: str) -> str:
    """Extract the canonical package name from a PEP 508 dependency string.

    >>> _dep_name("langchain-tavily>=0.2")
    'langchain-tavily'
    >>> _dep_name("deepagents>=0.5.3,<0.6")
    'deepagents'
    """
    # Stop at the first marker / comparator / whitespace.
    return re.split(r"[<>=!~;\[\s]", spec, maxsplit=1)[0].strip()


def _runtime_deps() -> list[str]:
    """Return the [project].dependencies list from pyproject.toml."""
    deps = _load_pyproject()["project"]["dependencies"]
    assert isinstance(deps, list)
    return deps


def _runtime_dep_names() -> list[str]:
    return [_dep_name(d) for d in _runtime_deps()]


# ===========================================================================
# AC-001: Phase 2 runtime dependencies are added
# ===========================================================================


class TestAC001Phase2DependenciesAdded:
    """AC-001: pyproject.toml adds langchain-tavily, asteval, nats-core, pyyaml."""

    REQUIRED_PHASE2_DEPS: ClassVar[list[str]] = [
        "langchain-tavily",
        "asteval",
        "nats-core",
        "pyyaml",
    ]

    @pytest.mark.parametrize("pkg", REQUIRED_PHASE2_DEPS)
    def test_dep_listed_in_runtime(self, pkg: str) -> None:
        """Each Phase 2 dep appears in [project].dependencies."""
        names = _runtime_dep_names()
        assert pkg in names, (
            f"Phase 2 dependency '{pkg}' missing from [project].dependencies. "
            f"Got: {names}"
        )

    def test_langchain_tavily_pin_lower_bound(self) -> None:
        """langchain-tavily has a sane lower bound (DDR-006 pinned equivalent)."""
        deps = _runtime_deps()
        spec = next(d for d in deps if _dep_name(d) == "langchain-tavily")
        assert ">=" in spec, f"langchain-tavily needs a lower bound: {spec!r}"

    def test_asteval_pin_satisfies_ddr_007(self) -> None:
        """asteval lower bound is at least 0.9.33 (DDR-007 §Consequences)."""
        deps = _runtime_deps()
        spec = next(d for d in deps if _dep_name(d) == "asteval")
        match = re.search(r">=\s*(\d+)\.(\d+)\.(\d+)", spec)
        assert match, f"asteval pin missing >=X.Y.Z lower bound: {spec!r}"
        major, minor, patch = (int(g) for g in match.groups())
        assert (major, minor, patch) >= (0, 9, 33), (
            f"asteval pin {spec!r} is below DDR-007's 0.9.33 floor"
        )

    def test_nats_core_path_source_for_sibling_install(self) -> None:
        """nats-core resolves to the sibling repo per ADR-ARCH-010.

        ADR-ARCH-010 records that nats-core is "installed from sibling repo
        (pip-installed wheel)". The PyPI build of nats-core requires Python
        >=3.13 which is incompatible with our 3.12 pin (ADR-ARCH-010), so
        pyproject.toml must declare a path source under [tool.uv.sources].
        """
        data = _load_pyproject()
        sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        assert "nats-core" in sources, (
            "[tool.uv.sources].nats-core missing — nats-core PyPI build "
            "requires Python>=3.13 and conflicts with the 3.12 pin."
        )
        nc = sources["nats-core"]
        assert isinstance(nc, dict), "nats-core source must be a table"
        assert "path" in nc, f"nats-core source must declare a path: {nc!r}"
        assert "../nats-core" in nc["path"], (
            f"nats-core path should point at the sibling repo: {nc!r}"
        )

    def test_pyyaml_present(self) -> None:
        """pyyaml is present (it was already in Phase 1; AC-001 says 'if not
        already present', so existence is sufficient)."""
        assert "pyyaml" in _runtime_dep_names()

    def test_phase2_deps_importable(self) -> None:
        """The Phase 2 deps are importable in the current venv (uv sync ran)."""
        for module in ("langchain_tavily", "asteval", "nats_core", "yaml"):
            mod = importlib.import_module(module)
            assert mod is not None


# ===========================================================================
# AC-002: nats-py is NOT in [project].dependencies (scope invariant)
# ===========================================================================


class TestAC002NatsPyNotDeclared:
    """AC-002: `nats-py` does not appear in [project].dependencies until
    FEAT-JARVIS-004 (phase2-dispatch-foundations-scope §Scope Invariants ¶5)."""

    def test_nats_py_not_in_runtime_dependencies(self) -> None:
        names = _runtime_dep_names()
        assert "nats-py" not in names, (
            "nats-py must NOT appear in [project].dependencies in Phase 2 — "
            "Phase 2 scope invariant. It enters the manifest in FEAT-JARVIS-004."
        )

    def test_nats_py_not_in_optional_dependencies(self) -> None:
        """nats-py must not be smuggled in via an optional-extras group either."""
        opt = _load_pyproject()["project"].get("optional-dependencies", {})
        for group, specs in opt.items():
            for spec in specs:
                assert _dep_name(spec) != "nats-py", (
                    f"nats-py found in [project.optional-dependencies].{group} — "
                    "Phase 2 scope invariant forbids it as a direct dependency."
                )

    def test_nats_py_not_in_dev_group(self) -> None:
        """nats-py must not be in [dependency-groups].dev either."""
        dev = _load_pyproject().get("dependency-groups", {}).get("dev", [])
        for spec in dev:
            assert _dep_name(spec) != "nats-py", (
                "nats-py found in [dependency-groups].dev — "
                "Phase 2 scope invariant forbids it as a direct dependency."
            )

    def test_uv_sources_does_not_pin_nats_py(self) -> None:
        """nats-py must not be declared as a uv path/git source either."""
        sources = _load_pyproject().get("tool", {}).get("uv", {}).get("sources", {})
        assert "nats-py" not in sources


# ===========================================================================
# AC-003: uv lock is regenerated; uv sync completes clean
# ===========================================================================


class TestAC003UvLockAndSync:
    """AC-003: uv lock is regenerated; uv sync completes clean."""

    def test_uv_lock_exists(self) -> None:
        assert UV_LOCK.exists(), "uv.lock must exist after `uv lock`"

    def test_uv_lock_contains_phase2_packages(self) -> None:
        """The lock file resolved each Phase 2 package."""
        lock_text = UV_LOCK.read_text()
        for pkg in ("langchain-tavily", "asteval", "nats-core"):
            # `name = "<pkg>"` is the canonical TOML form uv writes.
            assert f'name = "{pkg}"' in lock_text, (
                f"uv.lock missing entry for {pkg!r} — was `uv lock` run?"
            )

    def test_uv_sync_completes_clean(self) -> None:
        """`uv sync` exits zero and reports no changes after a fresh sync.

        Running `uv sync` twice in a row: the first call ensures the env is in
        sync with the lock file; the second must be a no-op. Any drift between
        pyproject.toml, uv.lock, and the venv shows up as a non-zero exit or
        an extra `+`/`-` line.
        """
        # Prime the env (idempotent).
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
        # Second call must report the env as already in sync.
        second = subprocess.run(
            ["uv", "sync"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=300,
        )
        assert second.returncode == 0, (
            f"second `uv sync` failed:\n{second.stdout}\n{second.stderr}"
        )
        combined = second.stdout + second.stderr
        # When already in sync, uv prints "Resolved … packages" and
        # "Audited … packages" / "Checked … packages" with no `+`/`-` lines.
        assert " + " not in combined and " - " not in combined, (
            f"second `uv sync` showed package changes — env drifted:\n{combined}"
        )


# ===========================================================================
# AC-004: Phase 1 dependencies are untouched
# ===========================================================================


class TestAC004Phase1DependenciesUntouched:
    """AC-004: Phase 1 dependencies (and their version pins) are untouched.

    The Phase 1 pin set is recorded in pyproject.toml as it shipped at the
    end of FEAT-JARVIS-001 (TASK-J001-001) and tightened by ADR-ARCH-010 for
    the deepagents pin. Each entry below must appear *verbatim* — no
    relaxation, no tightening, no removal.

    Rev2 rebaseline (2026-04-27, ADR-ARCH-010-rev2 / TASK-REV-FA04 follow-up):
    the langchain ecosystem (langchain-core / langchain / langgraph /
    langchain-openai and the providers langchain-anthropic /
    langchain-google-genai) jumped from coordinated 0.x to coordinated 1.x.
    The 0.x langchain-core stopped publishing the `block_translators.langchain_v0`
    compat helpers that 0.x langchain agents still imported, leaving the
    open-floor `>=0.3` / `>=0.2` pins free to resolve mismatched 0.x/1.x
    pairs. The pins below have been rebaselined to coherent 1.x with `<2`
    caps. `langchain` itself is now an explicit runtime dep (was implicit
    transitively). Non-langchain Phase 1 pins are unchanged.
    """

    PHASE_1_RUNTIME_PINS: ClassVar[dict[str, str]] = {
        "deepagents": "deepagents>=0.5.3,<0.6",
        "langchain-core": "langchain-core>=1.3,<2",
        "langchain": "langchain>=1.2,<2",
        "langgraph": "langgraph>=1.1,<2",
        "langchain-openai": "langchain-openai>=1.2,<2",
        "pydantic": "pydantic>=2",
        "pydantic-settings": "pydantic-settings>=2",
        "structlog": "structlog>=24.1",
        "python-dotenv": "python-dotenv>=1.0",
        "click": "click>=8.1",
        "pyyaml": "pyyaml>=6.0",
    }

    PHASE_1_OPTIONAL_PROVIDERS: ClassVar[list[str]] = [
        "langchain-anthropic>=1.4,<2",
        "langchain-google-genai>=4.2,<5",
    ]

    PHASE_1_DEV_PINS: ClassVar[list[str]] = [
        "pytest>=8",
        "pytest-asyncio>=0.24",
        "pytest-cov>=5",
        # TASK-OPS-BDDM-9 / FEAT-BDDM (2026-04-25): pytest-bdd added to
        # activate BDD verification for the @task:-tagged Gherkin scenarios
        # under `features/`. Without it, GuardKit's bdd_runner silently
        # bypassed BDD results — see jarvis/docs/history/autobuild-FEAT-J002-history.md
        # for empirical proof. AC-004 still asserts the Phase 1 pins are
        # not relaxed, tightened, or removed; this addition is permitted.
        "pytest-bdd>=8.1,<9",
        "ruff>=0.4",
        "mypy>=1.10",
        "types-PyYAML>=6",
        "types-click>=7.1",
    ]

    @pytest.mark.parametrize(
        ("pkg", "expected"), list(PHASE_1_RUNTIME_PINS.items())
    )
    def test_phase1_runtime_pin_unchanged(self, pkg: str, expected: str) -> None:
        deps = _runtime_deps()
        actual = next((d for d in deps if _dep_name(d) == pkg), None)
        assert actual is not None, f"Phase 1 dep '{pkg}' was removed"
        assert actual == expected, (
            f"Phase 1 dep pin changed: expected {expected!r}, got {actual!r}"
        )

    def test_python_pin_unchanged(self) -> None:
        """ADR-ARCH-010-rev2: requires-python = '>=3.11'.

        Rebaselined 2026-04-27 from `>=3.12,<3.13` (TASK-REV-FA04 follow-up).
        The original tight upper bound was driven by the 2025-10 PyPI publication
        of `nats-core` requiring `>=3.13`; that constraint resolved upstream
        (verified 2026-04-27: `nats-core` PyPI now declares `>=3.10`). The
        stale upper bound caused a 33-min GuardKit AutoBuild stall on consumer
        machines whose default Python had advanced to 3.14, hence the
        rebaseline. `>=3.11` aligns with the rest of the LangChain DeepAgents
        portfolio (forge, study-tutor, agentic-dataset-factory, specialist-agent).
        """
        rp = _load_pyproject()["project"]["requires-python"]
        assert rp == ">=3.11", (
            f"requires-python changed from ADR-ARCH-010-rev2 pin: {rp!r}"
        )

    def test_phase1_providers_untouched(self) -> None:
        """Phase 1 provider entries are still present with their original pins.

        Phase 3 (TASK-J003-006) appends `google-genai>=0.3.0` to this group,
        so the assertion is a *superset* check rather than an exact-list match
        — Phase 1 pins must not be relaxed, tightened, or removed, but Phase 3
        is allowed to extend the group additively.
        """
        opt = _load_pyproject()["project"]["optional-dependencies"]
        for pin in self.PHASE_1_OPTIONAL_PROVIDERS:
            assert pin in opt["providers"], (
                f"Phase 1 provider pin {pin!r} was relaxed/tightened/removed "
                f"from [project.optional-dependencies].providers: {opt['providers']!r}"
            )

    def test_phase1_dev_group_untouched(self) -> None:
        """Phase 1 dev pins are still present with their original values.

        Phase 3 (TASK-J003-006) appends `langgraph-cli>=0.1` to the dev
        group, so the assertion is a *superset* check rather than an
        exact-list match — Phase 1 pins must not be relaxed, tightened,
        or removed, but Phase 3 is allowed to extend the group additively.
        """
        dev = _load_pyproject()["dependency-groups"]["dev"]
        for pin in self.PHASE_1_DEV_PINS:
            assert pin in dev, (
                f"Phase 1 dev pin {pin!r} was relaxed/tightened/removed "
                f"from [dependency-groups].dev: {dev!r}"
            )

    def test_project_metadata_untouched(self) -> None:
        """Name, version, build backend, hatch wheel layout are untouched."""
        data = _load_pyproject()
        assert data["project"]["name"] == "jarvis"
        assert data["project"]["version"] == "0.1.0"
        assert data["build-system"]["build-backend"] == "hatchling.build"
        assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
            "src/jarvis"
        ]


# ===========================================================================
# Hygiene: importable Phase 1 surface still works after the new pins
# ===========================================================================


class TestPhase1ImportSurfaceStillWorks:
    """Sanity check: the Phase 1 import surface is still healthy after the
    new pins. If a Phase 2 dep dragged in an incompatible transitive (e.g.
    older pydantic), this catches it at test time rather than at runtime."""

    @pytest.mark.parametrize(
        "module",
        [
            "deepagents",
            "langchain_core",
            "langgraph",
            "langchain_openai",
            "pydantic",
            "pydantic_settings",
            "structlog",
            "dotenv",
            "click",
            "yaml",
        ],
    )
    def test_phase1_module_imports(self, module: str) -> None:
        mod = importlib.import_module(module)
        assert mod is not None

    def test_jarvis_package_imports(self) -> None:
        """The jarvis package itself still imports under the new pins."""
        result = subprocess.run(
            [sys.executable, "-c", "import jarvis; print(jarvis.__version__)"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=ROOT,
        )
        assert result.returncode == 0, (
            f"`import jarvis` regressed under the Phase 2 pins.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "0.1.0" in result.stdout
