"""Seam tests for the repo-root ``README.md`` rewrite (TASK-DOC-006).

Per Context B Q3 of the task spec, these are minimal grep/seam tests only.
Each test mirrors one of the 9 acceptance criteria (AC-001 … AC-009) and
the 15 grep invariants from the task's ``Test Requirements`` section.

Full pytest / mypy / ruff / ``langgraph dev`` regression is deferred to
TASK-DOC-007 — that's intentional, do not add it here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"


@pytest.fixture(scope="module")
def readme_text() -> str:
    """Read the repo-root README.md once per module."""
    assert README.exists(), f"README.md not found at {README}"
    return README.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_lines(readme_text: str) -> list[str]:
    """Split README into lines (no trailing newline normalisation)."""
    return readme_text.splitlines()


class TestAC001FirstHeadingIsJarvis:
    """AC-001: First heading is a level-1 (``#``) heading containing ``Jarvis``."""

    def test_first_line_is_h1_with_jarvis(self, readme_lines: list[str]) -> None:
        first_line = readme_lines[0]
        assert re.match(r"^# .*Jarvis", first_line), (
            f"First line must be an H1 containing 'Jarvis'; got: {first_line!r}"
        )


class TestAC002StatusSectionReferencesPhase3:
    """AC-002: ``## Status`` section references Phase 3 + end-to-end Forge round-trip."""

    def test_has_status_h2(self, readme_text: str) -> None:
        assert re.search(r"^## Status\b", readme_text, re.MULTILINE), (
            "README must have a '## Status' H2 section"
        )

    def test_mentions_phase_3(self, readme_text: str) -> None:
        assert "Phase 3" in readme_text, (
            "README must reference 'Phase 3' by name (ASSUM-006)"
        )

    def test_status_describes_forge_round_trip_close_criterion(
        self, readme_text: str
    ) -> None:
        # Look for the close-criterion phrasing — Phase 3 close + Forge round-trip.
        assert re.search(
            r"end-to-end Forge round-trip", readme_text, re.IGNORECASE
        ), "Status section must describe the end-to-end Forge round-trip"
        assert re.search(
            r"close criterion", readme_text, re.IGNORECASE
        ), "Status section must mention the Phase 3 close criterion"


class TestAC003QuickStartHasCanonicalCommands:
    """AC-003: ``## Quick Start`` includes ``uv sync`` and ``python -m langgraph dev``."""

    def test_has_quick_start_h2(self, readme_text: str) -> None:
        assert re.search(r"^## Quick Start\b", readme_text, re.MULTILINE), (
            "README must have a '## Quick Start' H2 section"
        )

    def test_has_uv_sync_command(self, readme_text: str) -> None:
        assert "uv sync" in readme_text, (
            "Quick Start must include the canonical install command 'uv sync'"
        )

    def test_has_langgraph_dev_command(self, readme_text: str) -> None:
        assert "python -m langgraph dev" in readme_text, (
            "Quick Start must include 'python -m langgraph dev' (canonical runtime)"
        )


class TestAC004ArchitectureSectionLinksToArchitectureDoc:
    """AC-004: ``## Architecture`` links to ``docs/architecture/ARCHITECTURE.md``."""

    def test_has_architecture_h2(self, readme_text: str) -> None:
        assert re.search(r"^## Architecture\b", readme_text, re.MULTILINE), (
            "README must have an '## Architecture' H2 section"
        )

    def test_architecture_section_links_to_arch_doc(
        self, readme_text: str
    ) -> None:
        # Markdown link form: [text](docs/architecture/ARCHITECTURE.md)
        assert re.search(
            r"\]\(docs/architecture/ARCHITECTURE\.md\)", readme_text
        ), "Architecture section must contain a relative markdown link to docs/architecture/ARCHITECTURE.md"


class TestAC005DesignDecisionsLinksAllThreeDirs:
    """AC-005: ``## Design Decisions`` references ADR + J004 DDR + J005 DDR dirs."""

    def test_has_design_decisions_h2(self, readme_text: str) -> None:
        assert re.search(
            r"^## Design Decisions\b", readme_text, re.MULTILINE
        ), "README must have a '## Design Decisions' H2 section"

    def test_links_to_adr_directory(self, readme_text: str) -> None:
        assert "docs/architecture/decisions" in readme_text, (
            "Design Decisions must reference docs/architecture/decisions/"
        )

    def test_links_to_feat_004_ddr_directory(self, readme_text: str) -> None:
        assert "docs/design/FEAT-JARVIS-004/decisions" in readme_text, (
            "Design Decisions must reference docs/design/FEAT-JARVIS-004/decisions/"
        )

    def test_links_to_feat_005_ddr_directory(self, readme_text: str) -> None:
        assert "docs/design/FEAT-JARVIS-005/decisions" in readme_text, (
            "Design Decisions must reference docs/design/FEAT-JARVIS-005/decisions/"
        )


class TestAC006NoPreArchitecturePhrase:
    """AC-006: README does NOT contain the literal phrase ``Pre-Architecture``."""

    def test_pre_architecture_phrase_absent(self, readme_text: str) -> None:
        assert "Pre-Architecture" not in readme_text, (
            "README must not contain the stale 'Pre-Architecture' phrase"
        )


class TestAC007NoStaleTestCount:
    """AC-007: README does NOT declare a hard-coded passing-test count below 2105.

    The previous README claimed '341 passing' — that exact phrase + that
    exact integer must be gone. A future, larger count is acceptable;
    the rule is "no stale undercount".
    """

    def test_no_341_passing_phrase(self, readme_text: str) -> None:
        assert "341 passing" not in readme_text, (
            "README must not declare the stale '341 passing' test count"
        )

    def test_no_isolated_341_count(self, readme_text: str) -> None:
        # Defensive: any stand-alone reference to 341 in the README is
        # almost certainly the stale count — there's no other reason
        # the integer 341 would appear.
        assert not re.search(r"\b341\b", readme_text), (
            "README must not contain the stale integer 341"
        )


class TestAC008OnlyRelativeMarkdownLinks:
    """AC-008: All in-repo markdown links use relative paths — no leading ``/``."""

    def test_no_absolute_markdown_link_paths(self, readme_text: str) -> None:
        # Match any markdown link target that begins with `/` — that's
        # an absolute filesystem path and is forbidden in this README.
        absolute_links = re.findall(r"\]\(/[^)]*\)", readme_text)
        assert not absolute_links, (
            f"README markdown links must be relative; found absolute: "
            f"{absolute_links}"
        )


class TestAC009LineCountWithinBudget:
    """AC-009: README line count is in [100, 300] (Group B.1, ASSUM-004/005)."""

    def test_line_count_in_range(self, readme_lines: list[str]) -> None:
        n = len(readme_lines)
        assert 100 <= n <= 300, (
            f"README line count must be between 100 and 300 (got {n})"
        )
