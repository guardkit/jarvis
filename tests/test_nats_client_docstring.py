"""Acceptance tests for TASK-DOC-001 — nats_client.py docstring polish.

Validates each AC:
- AC-001: First paragraph describes module's purpose.
- AC-002: References ``FEAT-JARVIS-004`` as origin.
- AC-003: Cites at least one DDR identifier (DDR-NNN).
- AC-004: References the design doc at the FEAT-JARVIS-004 path.
- AC-005: Each cited design-doc / DDR / ADR file exists on disk and is
  readable.
- AC-006: Polished docstring contains no ``TASK-J\\d{3}-\\d{3}`` token.
- AC-007: Docstring line count is within [20, 250].
- AC-008: No executable Python statement was modified — guarded
  indirectly here by importing the module and exercising its public
  surface (a syntax-broken module would fail to import).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from jarvis.infrastructure import nats_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_DOCSTRING = nats_client.__doc__ or ""
DOCSTRING_LINES = MODULE_DOCSTRING.splitlines()


def _extract_referenced_doc_paths(docstring: str) -> list[str]:
    """Return every ``docs/...md`` path mentioned in the docstring."""
    return re.findall(r"docs/[^\s`]+\.md", docstring)


# ---------------------------------------------------------------------------
# AC-001 — first paragraph describes module purpose
# ---------------------------------------------------------------------------


def test_ac001_first_paragraph_describes_purpose() -> None:
    assert MODULE_DOCSTRING, "module docstring must be present"
    first_para = MODULE_DOCSTRING.split("\n\n", 1)[0].strip()
    # The first line / paragraph should mention the wrapper purpose.
    assert "nats" in first_para.lower()
    assert (
        "wrapper" in first_para.lower()
        or "connection" in first_para.lower()
        or "lifecycle" in first_para.lower()
    )


# ---------------------------------------------------------------------------
# AC-002 — references FEAT-JARVIS-004 as origin
# ---------------------------------------------------------------------------


def test_ac002_references_feat_jarvis_004() -> None:
    assert "FEAT-JARVIS-004" in MODULE_DOCSTRING


# ---------------------------------------------------------------------------
# AC-003 — cites at least one DDR identifier
# ---------------------------------------------------------------------------


def test_ac003_cites_at_least_one_ddr() -> None:
    matches = re.findall(r"DDR-\d{3}", MODULE_DOCSTRING)
    assert matches, "expected at least one DDR-NNN identifier"


# ---------------------------------------------------------------------------
# AC-004 — references the design doc
# ---------------------------------------------------------------------------


def test_ac004_references_design_doc() -> None:
    paths = _extract_referenced_doc_paths(MODULE_DOCSTRING)
    feat_paths = [p for p in paths if "FEAT-JARVIS-004" in p]
    assert feat_paths, "expected at least one FEAT-JARVIS-004 design doc path"


# ---------------------------------------------------------------------------
# AC-005 — every cited design-doc / DDR file exists and is readable
# ---------------------------------------------------------------------------


def test_ac005_cited_files_exist_and_are_readable() -> None:
    paths = _extract_referenced_doc_paths(MODULE_DOCSTRING)
    assert paths, "expected at least one docs/ path in the docstring"
    for rel_path in paths:
        full = REPO_ROOT / rel_path
        assert full.is_file(), f"cited path missing on disk: {rel_path}"
        # Readability: open and read a byte to confirm permissions.
        with full.open("r", encoding="utf-8") as fh:
            assert fh.read(1) != ""


# ---------------------------------------------------------------------------
# AC-006 — no TASK-J\d{3}-\d{3} token in docstring
# ---------------------------------------------------------------------------


def test_ac006_no_task_token_in_docstring() -> None:
    assert not re.search(r"TASK-J\d{3}-\d{3}", MODULE_DOCSTRING)


# ---------------------------------------------------------------------------
# AC-007 — line count within [20, 250]
# ---------------------------------------------------------------------------


def test_ac007_docstring_line_count_in_range() -> None:
    n = len(DOCSTRING_LINES)
    assert 20 <= n <= 250, f"docstring line count={n} outside [20, 250]"


# ---------------------------------------------------------------------------
# AC-008 — executable statements unmodified (smoke import + symbol check)
# ---------------------------------------------------------------------------


def test_ac008_executable_surface_intact() -> None:
    # If any executable statement was broken, the import at the top of
    # this file would have failed. Beyond that, assert the public
    # surface is intact.
    assert hasattr(nats_client, "NATSClient")
    assert hasattr(nats_client, "NATSConnectionError")
    assert callable(nats_client.NATSClient.connect)
    assert callable(nats_client.NATSClient.drain)
    assert callable(nats_client.NATSClient.request)
    # Module-level callbacks are still present.
    assert callable(nats_client._on_reconnect)
    assert callable(nats_client._on_disconnect)
    assert callable(nats_client._on_error)
    assert callable(nats_client._on_closed)
    # And the seam is preserved.
    assert hasattr(nats_client, "_nats_connect")


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
