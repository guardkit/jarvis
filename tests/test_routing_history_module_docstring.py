"""Tests for the ``routing_history`` module docstring contract (TASK-DOC-004).

Acceptance Criteria:
    AC-001: First paragraph of the module docstring describes the module's
            purpose.
    AC-002: Module docstring references ``FEAT-JARVIS-004`` as origin.
    AC-003/AC-004: Module docstring cites at least one DDR identifier
            resolving under ``docs/design/FEAT-JARVIS-004/decisions/``,
            including ``DDR-019`` (Memory fire-and-forget writes).
    AC-005: Module docstring references the feature/data-model design doc.
    AC-006: Each cited design-doc / DDR file exists on disk and is readable.
    AC-007: Entire file contains no token matching ``TASK-J\\d{3}-\\d{3}``.
    AC-008: Module docstring line count is ≥ 20 and ≤ 250.
    AC-009: No executable Python statement is modified (covered indirectly
            by the still-passing schema/writer test suites).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import jarvis.infrastructure.routing_history as routing_history

MODULE_PATH = Path(routing_history.__file__).resolve()
REPO_ROOT = MODULE_PATH.parents[3]


@pytest.fixture(scope="module")
def module_docstring() -> str:
    docstring = routing_history.__doc__
    assert docstring is not None, "routing_history module must have a docstring"
    return docstring


@pytest.fixture(scope="module")
def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


class TestModuleDocstringContract:
    """AC-001 through AC-009 for the routing_history module docstring."""

    def test_first_paragraph_describes_module_purpose(
        self, module_docstring: str
    ) -> None:
        """AC-001: first paragraph describes the module's purpose."""
        first_paragraph = module_docstring.strip().split("\n\n", 1)[0]
        # Purpose-describing keywords expected in the first paragraph.
        for keyword in ("Routing-history", "schema", "writer"):
            assert keyword in first_paragraph, (
                f"first paragraph must mention {keyword!r}"
            )

    def test_references_feat_jarvis_004(self, module_docstring: str) -> None:
        """AC-002: module docstring references FEAT-JARVIS-004 as origin."""
        assert "FEAT-JARVIS-004" in module_docstring

    def test_cites_ddr_under_feat_jarvis_004(
        self, module_docstring: str
    ) -> None:
        """AC-003: module docstring cites at least one DDR resolving under
        ``docs/design/FEAT-JARVIS-004/decisions/``."""
        ddr_refs = re.findall(
            r"docs/design/FEAT-JARVIS-004/decisions/DDR-\d{3}[A-Za-z0-9\-]*\.md",
            module_docstring,
        )
        assert ddr_refs, "expected at least one DDR file path in docstring"

    def test_cites_ddr_019(self, module_docstring: str) -> None:
        """AC-004: module docstring explicitly cites DDR-019 (Memory
        fire-and-forget writes)."""
        assert "DDR-019" in module_docstring

    def test_references_design_doc(self, module_docstring: str) -> None:
        """AC-005: module docstring references the FEAT-JARVIS-004 design doc
        (either ``design.md`` or the ``DM-routing-history.md`` data model)."""
        assert (
            "FEAT-JARVIS-004/design.md" in module_docstring
            or "DM-routing-history.md" in module_docstring
        )

    def test_cited_files_exist_and_are_readable(
        self, module_docstring: str
    ) -> None:
        """AC-006: each cited design-doc / DDR / ADR file exists on disk and
        is readable."""
        # Strip the relative-path leading "../../../" used in :doc:/role refs
        # — the docstring renders relative to the module's package root, so
        # paths are anchored either to the repo root or to ``docs/...``.
        candidate_paths = re.findall(
            r"(docs/[A-Za-z0-9_\-/\.]+\.md)", module_docstring
        )
        assert candidate_paths, "expected at least one cited doc path"

        for relative in candidate_paths:
            target = REPO_ROOT / relative
            assert target.exists(), f"cited file missing: {target}"
            # Readable check: a successful read_text exercises the OS-level
            # readable bit and the encoding, all in one shot.
            target.read_text(encoding="utf-8")

    def test_no_task_j_tokens_in_entire_file(
        self, module_source: str
    ) -> None:
        """AC-007: entire file contains no token matching TASK-J\\d{3}-\\d{3}."""
        matches = re.findall(r"TASK-J\d{3}-\d{3}", module_source)
        assert matches == [], (
            f"expected zero TASK-J###-### tokens, found: {matches}"
        )

    def test_docstring_line_count_within_bounds(
        self, module_docstring: str
    ) -> None:
        """AC-008: module docstring line count is between 20 and 250."""
        line_count = len(module_docstring.splitlines())
        assert 20 <= line_count <= 250, (
            f"docstring must be 20..250 lines; got {line_count}"
        )

    def test_no_executable_statements_modified(
        self, module_source: str
    ) -> None:
        """AC-009: parsing the module still yields a valid AST and the same
        public top-level executable surface (sanity check that we only
        touched docstrings and comments)."""
        tree = ast.parse(module_source)
        # Top-level executable surface stays stable.
        names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for required in {
            "TraceRef",
            "ToolCallRecord",
            "ModelCallRecord",
            "CapabilityDescriptorRef",
            "ConcurrentWorkloadSnapshot",
            "RedirectAttempt",
            "JarvisRoutingHistoryEntry",
            "MemoryClientProtocol",
            "RoutingHistoryWriter",
        }:
            assert required in names, (
                f"top-level definition missing: {required}"
            )
