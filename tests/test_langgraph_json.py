"""Tests for the repo-root ``langgraph.json`` manifest (TASK-J003-016 / DDR-013).

The repo-root ``langgraph.json`` is the LangGraph CLI manifest that
``python -m langgraph dev`` consumes to compile and serve the two Jarvis
graphs (``jarvis`` and ``jarvis_reasoner``) with ASGI transport per
ADR-ARCH-031. These tests pin every acceptance criterion from the task so
that future refactors cannot silently regress the manifest shape.

Acceptance criteria covered (see TASK-J003-016):

- AC-001: ``langgraph.json`` lives at the repo root (NOT under ``src/``).
- AC-002: file is valid JSON (parses with ``json.loads``).
- AC-003: declares a graph named ``jarvis`` bound to the supervisor module
  via a path the langgraph CLI can resolve.
- AC-004: declares a graph named ``jarvis_reasoner`` bound to
  ``./src/jarvis/agents/subagents/jarvis_reasoner.py:graph``.
- AC-005: both graphs declare ASGI transport.
- AC-006: ``dependencies`` lists ``.`` so the local package is installable.
- AC-007: environment block references ``.env`` so provider keys load.
- AC-009: lint/format — JSON conventionally formatted with 2-space indent
  and no trailing commas.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
LANGGRAPH_JSON: Path = REPO_ROOT / "langgraph.json"


@pytest.fixture(scope="module")
def manifest_text() -> str:
    """Read the raw ``langgraph.json`` file as text once per test module."""
    return LANGGRAPH_JSON.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def manifest(manifest_text: str) -> dict:
    """Parse ``langgraph.json`` as a dict once per test module."""
    return json.loads(manifest_text)


class TestLanggraphJsonLocation:
    """AC-001 — ``langgraph.json`` lives at repo root (not under ``src/``)."""

    def test_manifest_exists_at_repo_root(self) -> None:
        """File must exist at the repo root path."""
        assert LANGGRAPH_JSON.exists(), (
            f"langgraph.json must exist at repo root: {LANGGRAPH_JSON}"
        )
        assert LANGGRAPH_JSON.is_file(), "langgraph.json must be a regular file"

    def test_manifest_is_not_under_src(self) -> None:
        """No ``langgraph.json`` should exist under ``src/`` (DDR-013)."""
        src_dir = REPO_ROOT / "src"
        rogue_manifests = list(src_dir.rglob("langgraph.json"))
        assert rogue_manifests == [], (
            f"langgraph.json must NOT live under src/ (DDR-013); found: "
            f"{rogue_manifests}"
        )

    def test_manifest_sits_next_to_pyproject(self) -> None:
        """Repo-root placement is validated by co-location with pyproject.toml."""
        assert (REPO_ROOT / "pyproject.toml").exists(), (
            "Test premise: pyproject.toml should exist at repo root"
        )
        assert LANGGRAPH_JSON.parent == REPO_ROOT, (
            "langgraph.json must sit next to pyproject.toml at the repo root"
        )


class TestLanggraphJsonValidity:
    """AC-002 — file is valid JSON (parses with ``json.loads``)."""

    def test_manifest_parses_as_json(self, manifest_text: str) -> None:
        """``json.loads`` must succeed without raising."""
        parsed = json.loads(manifest_text)
        assert isinstance(parsed, dict), "Top-level manifest must be a JSON object"

    def test_manifest_has_no_trailing_commas(self, manifest_text: str) -> None:
        """Strict JSON forbids trailing commas — guard against accidental drift.

        ``json.loads`` already rejects them, but we add an explicit regex
        check so the diagnostic is precise when someone drafts a comma-laden
        edit by hand.
        """
        # Match a comma followed (after optional whitespace) by ``}`` or ``]``.
        trailing_comma_pattern = re.compile(r",\s*[}\]]")
        assert not trailing_comma_pattern.search(manifest_text), (
            "langgraph.json must not contain trailing commas"
        )


class TestJarvisGraphDeclaration:
    """AC-003 — declares ``jarvis`` graph bound to the supervisor module."""

    def test_graphs_section_present(self, manifest: dict) -> None:
        assert "graphs" in manifest, "Manifest must declare a 'graphs' section"
        assert isinstance(manifest["graphs"], dict)

    def test_jarvis_graph_declared(self, manifest: dict) -> None:
        assert "jarvis" in manifest["graphs"], (
            "Manifest must declare a graph named 'jarvis'"
        )

    def test_jarvis_graph_path_resolves_to_supervisor_module(
        self, manifest: dict
    ) -> None:
        """The path component must reference the supervisor module file."""
        entry = manifest["graphs"]["jarvis"]
        path_str = entry["path"] if isinstance(entry, dict) else entry
        module_str, _, attr_str = path_str.partition(":")
        assert attr_str, (
            f"Jarvis graph spec must use 'module:variable' format; got {path_str!r}"
        )
        # Module portion must reference the supervisor module
        assert module_str.endswith("supervisor.py"), (
            f"Jarvis graph must bind to the supervisor module; got {module_str!r}"
        )
        # The referenced file must exist on disk so langgraph CLI can resolve it.
        resolved = (REPO_ROOT / module_str).resolve()
        assert resolved.exists(), (
            f"Supervisor module path must exist on disk: {resolved}"
        )


class TestJarvisReasonerGraphDeclaration:
    """AC-004 — declares ``jarvis_reasoner`` graph bound to the subagent module."""

    def test_jarvis_reasoner_graph_declared(self, manifest: dict) -> None:
        assert "jarvis_reasoner" in manifest["graphs"], (
            "Manifest must declare a graph named 'jarvis_reasoner'"
        )

    def test_jarvis_reasoner_path_matches_ddr013(self, manifest: dict) -> None:
        """Per DDR-013 the subagent path is fixed to the canonical module."""
        entry = manifest["graphs"]["jarvis_reasoner"]
        path_str = entry["path"] if isinstance(entry, dict) else entry
        expected = "./src/jarvis/agents/subagents/jarvis_reasoner.py:graph"
        assert path_str == expected, (
            f"jarvis_reasoner graph must bind to {expected!r}; got {path_str!r}"
        )

    def test_jarvis_reasoner_module_exists(self, manifest: dict) -> None:
        entry = manifest["graphs"]["jarvis_reasoner"]
        path_str = entry["path"] if isinstance(entry, dict) else entry
        module_str, _, _ = path_str.partition(":")
        resolved = (REPO_ROOT / module_str).resolve()
        assert resolved.exists(), (
            f"jarvis_reasoner module path must exist on disk: {resolved}"
        )


class TestAsgiTransport:
    """AC-005 — both graphs declare ASGI transport (ADR-ARCH-031 default)."""

    @pytest.mark.parametrize("graph_id", ["jarvis", "jarvis_reasoner"])
    def test_graph_declares_asgi_transport(
        self, manifest: dict, graph_id: str
    ) -> None:
        """Each graph entry must explicitly declare ``transport: 'asgi'``."""
        entry = manifest["graphs"][graph_id]
        assert isinstance(entry, dict), (
            f"Graph '{graph_id}' must use the dict form so it can declare "
            f"transport explicitly; got {type(entry).__name__}"
        )
        assert entry.get("transport") == "asgi", (
            f"Graph '{graph_id}' must declare transport='asgi' (ADR-ARCH-031); "
            f"got {entry.get('transport')!r}"
        )


class TestDependenciesAndEnv:
    """AC-006 / AC-007 — dependencies lists '.' and env references '.env'."""

    def test_dependencies_lists_dot(self, manifest: dict) -> None:
        """``"."`` must appear in dependencies so the local package installs."""
        deps = manifest.get("dependencies")
        assert isinstance(deps, list), "'dependencies' must be a JSON array"
        assert "." in deps, (
            "'dependencies' must include '.' so the local package is installable"
        )

    def test_env_references_dotenv(self, manifest: dict) -> None:
        """``env`` must reference ``.env`` so provider keys load at startup."""
        env_value = manifest.get("env")
        assert env_value == ".env", (
            f"'env' must reference '.env' so provider keys load; got {env_value!r}"
        )


class TestLintAndFormat:
    """AC-009 — JSON conventionally formatted (2-space indent; no trailing commas)."""

    def test_uses_two_space_indent(self, manifest_text: str) -> None:
        """Check that indented lines use multiples of 2 spaces (not tabs / 4 spaces)."""
        # Find any indented (non-blank, non-leading) line and assert its indent
        # width is a multiple of 2 spaces, and that no tabs are used.
        for lineno, raw_line in enumerate(manifest_text.splitlines(), start=1):
            if not raw_line.strip():
                continue
            stripped = raw_line.lstrip(" ")
            indent_len = len(raw_line) - len(stripped)
            assert "\t" not in raw_line, (
                f"Line {lineno} contains a tab; expected spaces only"
            )
            assert indent_len % 2 == 0, (
                f"Line {lineno} indent ({indent_len} spaces) is not a multiple "
                f"of 2: {raw_line!r}"
            )

    def test_no_trailing_commas(self, manifest_text: str) -> None:
        """Trailing commas before ``}`` / ``]`` are forbidden in strict JSON."""
        trailing_comma_pattern = re.compile(r",\s*[}\]]")
        assert not trailing_comma_pattern.search(manifest_text), (
            "langgraph.json must not contain trailing commas"
        )

    def test_json_round_trips_with_two_space_indent(
        self, manifest: dict, manifest_text: str
    ) -> None:
        """Re-serialising with ``indent=2`` should match the on-disk text.

        This confirms the file is *conventionally* formatted with 2-space
        indent (the langchain-deepagents-orchestrator template uses 4, but
        DDR-013 / AC-009 explicitly requires 2 for parity with the Forge
        manifest under ADR-ARCH-031).
        """
        re_serialised = json.dumps(manifest, indent=2) + "\n"
        assert re_serialised == manifest_text, (
            "langgraph.json content must equal json.dumps(..., indent=2) + '\\n'"
        )


class TestScenarioAnchor:
    """AC-008 — Scenario anchor: the manifest declares both graphs with ASGI."""

    def test_scenario_anchor_repo_root_manifest_declares_both_graphs_with_asgi(
        self, manifest: dict
    ) -> None:
        """Single end-to-end check encoding the full scenario anchor sentence.

        The manifest at the repo root simultaneously:
          - declares the ``jarvis`` graph,
          - declares the ``jarvis_reasoner`` graph,
          - and pins ASGI transport on both.
        """
        assert LANGGRAPH_JSON.parent == REPO_ROOT
        graphs = manifest["graphs"]
        assert {"jarvis", "jarvis_reasoner"}.issubset(graphs.keys())
        for graph_id in ("jarvis", "jarvis_reasoner"):
            entry = graphs[graph_id]
            assert isinstance(entry, dict)
            assert entry.get("transport") == "asgi"
            assert "path" in entry and entry["path"].endswith(":graph")
