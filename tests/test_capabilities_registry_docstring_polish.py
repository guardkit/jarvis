"""Docstring polish acceptance tests for ``capabilities_registry.py``.

Validates TASK-DOC-003 acceptance criteria:

- AC-001: First paragraph of the module docstring describes the module's
  purpose.
- AC-002: Module docstring references ``FEAT-JARVIS-004`` as origin.
- AC-003: Module docstring cites at least one DDR identifier.
- AC-004: Module docstring references the design doc.
- AC-005: Each cited design-doc / DDR file exists on disk and is
  readable.
- AC-006: Polished module docstring still cites ``DDR-021``.
- AC-007: Polished module docstring still cites ``ADR-ARCH-017``.
- AC-008: Entire file contains no token matching ``TASK-J\\d{3}-\\d{3}``.
- AC-009: Module docstring line count is between 20 and 250 inclusive.
- AC-010: No executable Python statement is modified — file still parses
  and the module's public surface still imports correctly.
"""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = (
    REPO_ROOT / "src" / "jarvis" / "infrastructure" / "capabilities_registry.py"
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


class TestModuleDocstringContent:
    """Content-level assertions on the module docstring."""

    def test_first_paragraph_describes_module_purpose(
        self, module_docstring: str
    ) -> None:
        """AC-001: The first paragraph describes the module's purpose."""
        first_paragraph = module_docstring.split("\n\n", 1)[0].strip()
        assert first_paragraph, "First paragraph must not be empty"
        # Purpose-describing first line should mention CapabilitiesRegistry.
        assert "CapabilitiesRegistry" in first_paragraph, (
            "First paragraph should describe the CapabilitiesRegistry module"
        )

    def test_references_feat_jarvis_004_as_origin(
        self, module_docstring: str
    ) -> None:
        """AC-002: The module docstring names ``FEAT-JARVIS-004``."""
        assert "FEAT-JARVIS-004" in module_docstring

    def test_cites_at_least_one_ddr_identifier(
        self, module_docstring: str
    ) -> None:
        """AC-003: At least one ``DDR-NNN`` identifier is cited."""
        assert re.search(r"\bDDR-\d{3}\b", module_docstring), (
            "Module docstring must cite at least one DDR identifier"
        )

    def test_references_a_design_doc(self, module_docstring: str) -> None:
        """AC-004: The module docstring references the design doc."""
        assert "docs/design/FEAT-JARVIS-004" in module_docstring, (
            "Module docstring must reference the FEAT-JARVIS-004 design doc"
        )

    def test_still_cites_ddr_021(self, module_docstring: str) -> None:
        """AC-006: The polished docstring still cites ``DDR-021``."""
        assert "DDR-021" in module_docstring

    def test_still_cites_adr_arch_017(self, module_docstring: str) -> None:
        """AC-007: The polished docstring still cites ``ADR-ARCH-017``."""
        assert "ADR-ARCH-017" in module_docstring


class TestCitedDocsExistOnDisk:
    """AC-005: Each cited design-doc / DDR file is readable on disk."""

    def _extract_doc_paths(self, docstring: str) -> list[str]:
        """Pull ``:doc:`...``` and bare ``docs/...md`` paths from text."""
        # `:doc:` directive paths.
        rst_paths = re.findall(r":doc:`([^`]+)`", docstring)
        # Bare paths.
        bare_paths = re.findall(r"docs/[\w/\-.]+\.md", docstring)
        return list(dict.fromkeys(rst_paths + bare_paths))

    def test_each_cited_doc_path_resolves_and_is_readable(
        self, module_docstring: str
    ) -> None:
        cited = self._extract_doc_paths(module_docstring)
        assert cited, "Module docstring must cite at least one doc path"
        for relative in cited:
            target = REPO_ROOT / relative
            assert target.is_file(), (
                f"Cited doc path does not exist on disk: {relative}"
            )
            # Read returns bytes/str; both confirm readability.
            target.read_text(encoding="utf-8")


class TestEntireFileHygiene:
    """AC-008: The entire file is free of TASK-J\\d{3}-\\d{3} tokens."""

    def test_file_has_no_task_j_token(self, source_text: str) -> None:
        match = re.search(r"TASK-J\d{3}-\d{3}", source_text)
        assert match is None, (
            f"File must not contain a TASK-J###-### token; found: "
            f"{match.group(0) if match else ''!r}"
        )


class TestDocstringLineCount:
    """AC-009: Module docstring line count is in [20, 250] inclusive."""

    def test_module_docstring_line_count_within_range(
        self, module_docstring: str
    ) -> None:
        # Splitting on '\n' gives the literal docstring line count.
        line_count = module_docstring.count("\n") + 1
        assert 20 <= line_count <= 250, (
            f"Module docstring line count {line_count} is outside [20, 250]"
        )


class TestNoExecutableStatementsModified:
    """AC-010: Executable Python statements remain intact."""

    def test_module_parses_as_valid_python(self, source_text: str) -> None:
        # ast.parse raises SyntaxError if anything is broken.
        ast.parse(source_text)

    def test_module_imports_cleanly(self) -> None:
        module = importlib.import_module(
            "jarvis.infrastructure.capabilities_registry"
        )
        # Public surface must still resolve.
        for symbol in (
            "CapabilitiesRegistry",
            "LiveCapabilitiesRegistry",
            "StubCapabilitiesRegistry",
        ):
            assert hasattr(module, symbol), (
                f"Public symbol missing after polish: {symbol}"
            )
