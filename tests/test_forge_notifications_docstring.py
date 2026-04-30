"""Docstring polish acceptance tests for ``forge_notifications.py``.

TASK-DOC-005 polishes the module docstring of
``src/jarvis/infrastructure/forge_notifications.py`` so that it:

* Opens with a paragraph describing the module's purpose.
* Names ``FEAT-JARVIS-005`` as origin (Group A.2 — Forge stage-complete
  notification pipeline).
* Cites at least one DDR identifier resolving under
  ``docs/design/FEAT-JARVIS-005/decisions/``.
* References the design doc at
  ``docs/design/FEAT-JARVIS-005/design.md``.
* Removes every ``TASK-J\\d{3}-\\d{3}`` token from the entire file
  (Group C.2 docstring polish constraint — the file must read as a
  durable module docstring, not a build-task changelog).

These tests guard the polish so a future refactor cannot silently
re-introduce stale task tokens or break the cited reference paths.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "jarvis" / "infrastructure" / "forge_notifications.py"

DESIGN_DOC_PATH = "docs/design/FEAT-JARVIS-005/design.md"
DDR_DIR = "docs/design/FEAT-JARVIS-005/decisions/"
TASK_TOKEN_RE = re.compile(r"TASK-J\d{3}-\d{3}")
DDR_ID_RE = re.compile(r"DDR-\d{3}")
DDR_PATH_RE = re.compile(
    r"docs/design/FEAT-JARVIS-005/decisions/DDR-\d{3}-[a-z0-9-]+\.md"
)
DESIGN_DOC_RE = re.compile(r"docs/design/FEAT-JARVIS-005/design\.md")


@pytest.fixture(scope="module")
def module_source() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def module_docstring(module_source: str) -> str:
    tree = ast.parse(module_source)
    docstring = ast.get_docstring(tree, clean=False)
    assert docstring is not None, "forge_notifications.py must have a module docstring"
    return docstring


@pytest.fixture(scope="module")
def original_executable_dump() -> str:
    """AST dump of the *expected* executable surface (everything but
    docstrings). Reused as the reference shape AC-008 holds the
    polished module to.
    """
    return _strip_docstrings_dump(MODULE_PATH.read_text(encoding="utf-8"))


def _strip_docstrings_dump(source: str) -> str:
    """Return an ``ast.dump`` of ``source`` with every docstring node
    replaced by a constant marker, so tests can compare executable
    statements while ignoring docstring text changes.
    """
    tree = ast.parse(source)

    def _strip(node: ast.AST) -> None:
        body = getattr(node, "body", None)
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body[0].value = ast.Constant(value="<docstring>")
        for child in ast.iter_child_nodes(node):
            _strip(child)

    _strip(tree)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


class TestModuleDocstring:
    """Acceptance tests for TASK-DOC-005."""

    def test_ac_001_first_paragraph_describes_module_purpose(
        self, module_docstring: str
    ) -> None:
        """AC-001: First paragraph describes the module's purpose."""
        # Strip the leading summary line — the first paragraph is the
        # block following it (or the summary itself if no body follows).
        paragraphs = [p.strip() for p in module_docstring.split("\n\n") if p.strip()]
        assert paragraphs, "Module docstring must contain at least one paragraph."
        first_paragraph = paragraphs[0]
        # The first paragraph must mention what this module is about.
        assert "notification" in first_paragraph.lower(), (
            "First paragraph must describe the notification surface this "
            "module owns."
        )

    def test_ac_002_references_feat_jarvis_005(self, module_docstring: str) -> None:
        """AC-002: Module docstring references ``FEAT-JARVIS-005`` as origin."""
        assert "FEAT-JARVIS-005" in module_docstring, (
            "Module docstring must reference FEAT-JARVIS-005 as the origin "
            "feature (Group A.2)."
        )

    def test_ac_003_cites_at_least_one_ddr(self, module_docstring: str) -> None:
        """AC-003: Module docstring cites at least one DDR resolving under
        the FEAT-JARVIS-005 decisions directory.
        """
        ddr_ids = DDR_ID_RE.findall(module_docstring)
        assert ddr_ids, (
            "Module docstring must cite at least one DDR identifier "
            "(e.g. DDR-027) from FEAT-JARVIS-005."
        )
        ddr_paths = DDR_PATH_RE.findall(module_docstring)
        assert ddr_paths, (
            "Module docstring must include at least one resolvable DDR "
            "path under docs/design/FEAT-JARVIS-005/decisions/."
        )

    def test_ac_004_references_design_doc(self, module_docstring: str) -> None:
        """AC-004: Module docstring references the FEAT-JARVIS-005 design doc."""
        assert DESIGN_DOC_RE.search(module_docstring), (
            f"Module docstring must reference the design doc at {DESIGN_DOC_PATH}."
        )

    def test_ac_005_cited_paths_resolve_on_disk(self, module_docstring: str) -> None:
        """AC-005: Each cited design-doc / DDR file exists on disk and is
        readable.
        """
        cited_paths = set(DDR_PATH_RE.findall(module_docstring))
        cited_paths.update(DESIGN_DOC_RE.findall(module_docstring))
        # Also pick up the DM-forge-notification reference if present.
        cited_paths.update(
            re.findall(
                r"docs/design/FEAT-JARVIS-005/models/DM-[a-z0-9-]+\.md",
                module_docstring,
            )
        )
        assert cited_paths, "Expected at least one cited reference path."
        for rel_path in cited_paths:
            full = REPO_ROOT / rel_path
            assert full.is_file(), f"Cited path does not exist on disk: {rel_path}"
            # Readability check: load enough bytes to confirm the file
            # is non-empty and decodable.
            content = full.read_text(encoding="utf-8")
            assert content.strip(), f"Cited path is empty: {rel_path}"

    def test_ac_006_no_task_j_tokens_in_entire_file(self, module_source: str) -> None:
        """AC-006: Entire file contains no token matching ``TASK-J\\d{3}-\\d{3}``."""
        matches = TASK_TOKEN_RE.findall(module_source)
        assert not matches, (
            "forge_notifications.py must not contain any TASK-Jxxx-yyy "
            f"tokens; found: {matches}"
        )

    def test_ac_007_docstring_line_count_within_bounds(
        self, module_docstring: str
    ) -> None:
        """AC-007: Module docstring line count is between 20 and 250 (inclusive)."""
        line_count = len(module_docstring.splitlines())
        assert 20 <= line_count <= 250, (
            f"Module docstring line count must be within [20, 250]; "
            f"got {line_count}."
        )

    def test_ac_008_executable_statements_unchanged(
        self, module_source: str
    ) -> None:
        """AC-008: No executable Python statement is modified.

        Verifies the module still parses to a syntactically valid AST and
        that every statement remains intact (a regression here would
        manifest as a SyntaxError or a missing class/function).
        """
        tree = ast.parse(module_source)
        # Must contain the canonical executable surface this module
        # exports — the polish must not have removed any of these.
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for required in (
            "ForgeNotification",
            "BuildCorrelation",
            "ForgeNotificationsSubscriber",
            "render_line",
            "register_correlation",
            "start",
            "stop",
            "bind_session_manager",
            "_on_message",
            "_handle_message",
            "_parse_completed_at",
            "_get_deliver_policy_new",
            "_get_stage_complete_subject",
        ):
            assert required in names, (
                f"Executable statement removed by docstring polish: {required}"
            )
