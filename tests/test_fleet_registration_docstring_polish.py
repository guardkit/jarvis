"""Docstring polish acceptance tests for ``fleet_registration.py``.

Validates TASK-DOC-002 acceptance criteria:

- AC-001: First paragraph of the module docstring describes the
  module's purpose.
- AC-002: Module docstring references ``FEAT-JARVIS-004`` as origin.
- AC-003: Module docstring cites at least one DDR identifier
  (``DDR-NNN``) resolving under
  ``docs/design/FEAT-JARVIS-004/decisions/``.
- AC-004: Module docstring references the design doc at
  ``docs/design/FEAT-JARVIS-004/design.md``.
- AC-005: Each cited design-doc / DDR / ADR file exists on disk and is
  readable.
- AC-006: **Entire file** contains **no** token matching
  ``TASK-J\\d{3}-\\d{3}``.
- AC-007: Module docstring line count is between 20 and 250 inclusive.
- AC-008: No executable Python statement is modified — file still
  parses and the module's public surface still imports correctly.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = (
    REPO_ROOT / "src" / "jarvis" / "infrastructure" / "fleet_registration.py"
)


@pytest.fixture(scope="module")
def source_text() -> str:
    """Return the raw source text of the module under test."""
    return MODULE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def module_ast(source_text: str) -> ast.Module:
    """Return the parsed AST for the module under test."""
    return ast.parse(source_text)


@pytest.fixture(scope="module")
def module_docstring(module_ast: ast.Module) -> str:
    """Return the module docstring (raises if absent)."""
    docstring = ast.get_docstring(module_ast)
    assert docstring is not None, "Module docstring is missing"
    return docstring


def _extract_doc_paths(docstring: str) -> list[str]:
    """Return every ``docs/...md`` path referenced in *docstring*."""
    rst_paths = re.findall(r":doc:`([^`]+)`", docstring)
    bare_paths = re.findall(r"docs/[\w/\-.]+\.md", docstring)
    return list(dict.fromkeys(rst_paths + bare_paths))


# ---------------------------------------------------------------------------
# AC-001 — first paragraph describes module purpose
# ---------------------------------------------------------------------------


class TestFirstParagraphDescribesPurpose:
    """AC-001: First paragraph describes the module's purpose."""

    def test_first_paragraph_is_present(self, module_docstring: str) -> None:
        first = module_docstring.split("\n\n", 1)[0].strip()
        assert first, "First paragraph must not be empty"

    def test_first_paragraph_describes_fleet_registration(
        self, module_docstring: str
    ) -> None:
        first = module_docstring.split("\n\n", 1)[0].lower()
        # The module's purpose is fleet registration / heartbeat /
        # deregistration on the NATS bus — the first paragraph must
        # convey at least the registration aspect.
        assert (
            "fleet" in first
            or "registration" in first
            or "register" in first
        ), "First paragraph should describe fleet registration purpose"


# ---------------------------------------------------------------------------
# AC-002 — references FEAT-JARVIS-004 as origin
# ---------------------------------------------------------------------------


class TestReferencesFeatJarvis004:
    """AC-002: Module docstring names ``FEAT-JARVIS-004`` as origin."""

    def test_feat_jarvis_004_token_present(
        self, module_docstring: str
    ) -> None:
        assert "FEAT-JARVIS-004" in module_docstring


# ---------------------------------------------------------------------------
# AC-003 — cites at least one DDR identifier
# ---------------------------------------------------------------------------


class TestCitesDdrIdentifier:
    """AC-003: Cites at least one DDR-NNN identifier under
    ``docs/design/FEAT-JARVIS-004/decisions/``."""

    def test_at_least_one_ddr_identifier(
        self, module_docstring: str
    ) -> None:
        assert re.search(r"\bDDR-\d{3}\b", module_docstring), (
            "Module docstring must cite at least one DDR identifier"
        )

    def test_cited_ddr_resolves_under_feat_jarvis_004_decisions(
        self, module_docstring: str
    ) -> None:
        cited_paths = _extract_doc_paths(module_docstring)
        ddr_paths = [
            p
            for p in cited_paths
            if "FEAT-JARVIS-004/decisions/DDR-" in p and p.endswith(".md")
        ]
        assert ddr_paths, (
            "Module docstring must cite a DDR file under "
            "docs/design/FEAT-JARVIS-004/decisions/"
        )


# ---------------------------------------------------------------------------
# AC-004 — references the design doc at docs/design/FEAT-JARVIS-004/design.md
# ---------------------------------------------------------------------------


class TestReferencesDesignDoc:
    """AC-004: References ``docs/design/FEAT-JARVIS-004/design.md``."""

    def test_design_doc_path_present(self, module_docstring: str) -> None:
        assert "docs/design/FEAT-JARVIS-004/design.md" in module_docstring, (
            "Module docstring must reference the FEAT-JARVIS-004 design doc"
        )


# ---------------------------------------------------------------------------
# AC-005 — every cited design-doc / DDR / ADR file exists and is readable
# ---------------------------------------------------------------------------


class TestCitedDocsExistOnDisk:
    """AC-005: Each cited design-doc / DDR / ADR file is readable on disk."""

    def test_each_cited_doc_path_resolves_and_is_readable(
        self, module_docstring: str
    ) -> None:
        cited = _extract_doc_paths(module_docstring)
        assert cited, "Module docstring must cite at least one doc path"
        for relative in cited:
            target = REPO_ROOT / relative
            assert target.is_file(), (
                f"Cited doc path does not exist on disk: {relative}"
            )
            # Confirm read access by reading the bytes back.
            target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC-006 — entire file contains no TASK-J\d{3}-\d{3} token
# ---------------------------------------------------------------------------


class TestEntireFileFreeOfTaskTokens:
    """AC-006: The entire file contains no ``TASK-J###-###`` token."""

    def test_file_has_no_task_j_token(self, source_text: str) -> None:
        match = re.search(r"TASK-J\d{3}-\d{3}", source_text)
        assert match is None, (
            "File must not contain a TASK-J###-### token; found: "
            f"{match.group(0) if match else ''!r}"
        )


# ---------------------------------------------------------------------------
# AC-007 — module docstring line count is between 20 and 250 inclusive
# ---------------------------------------------------------------------------


class TestDocstringLineCount:
    """AC-007: Module docstring line count is in [20, 250] inclusive."""

    def test_module_docstring_line_count_within_range(
        self, module_docstring: str
    ) -> None:
        line_count = module_docstring.count("\n") + 1
        assert 20 <= line_count <= 250, (
            f"Module docstring line count {line_count} is outside [20, 250]"
        )


# ---------------------------------------------------------------------------
# AC-008 — no executable Python statement was modified
# ---------------------------------------------------------------------------


class TestNoExecutableStatementsModified:
    """AC-008: Executable Python statements remain intact."""

    def test_module_parses_as_valid_python(self, source_text: str) -> None:
        # ast.parse raises SyntaxError if anything is broken.
        ast.parse(source_text)

    def test_module_imports_cleanly(self) -> None:
        module = importlib.import_module(
            "jarvis.infrastructure.fleet_registration"
        )
        # Public surface must still resolve after the polish.
        for symbol in (
            "JARVIS_AGENT_ID",
            "JARVIS_AGENT_NAME",
            "JARVIS_TEMPLATE",
            "NATSConnectionError",
            "build_jarvis_manifest",
            "deregister_from_fleet",
            "heartbeat_loop",
            "register_on_fleet",
        ):
            assert hasattr(module, symbol), (
                f"Public symbol missing after polish: {symbol}"
            )

    def test_public_callables_remain_callable(self) -> None:
        module = importlib.import_module(
            "jarvis.infrastructure.fleet_registration"
        )
        assert callable(module.build_jarvis_manifest)
        assert callable(module.register_on_fleet)
        assert callable(module.heartbeat_loop)
        assert callable(module.deregister_from_fleet)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
