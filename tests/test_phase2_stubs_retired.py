"""Grep-invariant retire — assert Phase 2 ``queue_build`` stub anchors gone.

This module is the queue-build-side companion to TASK-J004-020's
dispatch-side retire test (``test_no_phase_2_stub_anchors`` in
``tests/test_no_retired_roster_strings.py``). It asserts that the
Phase 2 ``queue_build`` stub anchors retired by FEAT-JARVIS-005
(TASK-J005-005) cannot be silently restored by a future regression.

The Phase 2 ``queue_build`` stub used:

* a ``LOG_PREFIX_QUEUE_BUILD`` module-level constant — the DDR-009 grep
  token that pinned the swap-point seam during Phase 2.
* a ``logger.info(f"{LOG_PREFIX_QUEUE_BUILD} ...")`` anchor line tagged
  ``"queue_build stub"`` in ``src/jarvis/tools/dispatch.py``.

Both were removed by TASK-J005-005 once the tool body was swapped to a
real ``js.publish(...)`` round-trip per ADR-SP-014 Pattern A. This
module's tests are the *flipped* invariants: they assert the literals
are GONE from the source tree and fail with a file-naming message if
they reappear.

Acceptance criteria covered (TASK-J005-011):

- AC-001: walks ``src/jarvis/`` recursively (``.py`` / ``.yaml`` /
  ``.yml`` / ``.txt``) and asserts the literal ``LOG_PREFIX_QUEUE_BUILD``
  is absent from every file.
- AC-002: asserts the literal ``"queue_build stub"`` is absent from
  ``src/jarvis/tools/dispatch.py``.
- AC-003: walk is a ``Path.rglob`` + substring check; the test runs in
  well under 100 ms (the ``test_walk_runs_under_100_ms`` guard pins
  this with a generous 100 ms upper bound).
- AC-004: failure messages name the offending file (and line, for
  AC-001 / AC-002) so a reintroduction surfaces a self-explanatory
  diagnostic.
- AC-005: ``uv run pytest tests/test_phase2_stubs_retired.py -v``
  passes once TASK-J005-005's anchor removal lands.

Pattern: same shape as TASK-J004-020 dispatch-side retire — the
deliberate redundancy with TASK-J005-005's standard test suite is the
point, since this catches a regression at static-scan time rather than
at run time.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Project layout — resolve relative to this test file so the test is robust
# to checkout location (matches the convention in
# ``test_no_retired_roster_strings``).
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_SRC_JARVIS: Path = _PROJECT_ROOT / "src" / "jarvis"
_DISPATCH_PY: Path = _SRC_JARVIS / "tools" / "dispatch.py"

# Extensions covered by the source-tree walk — kept aligned with
# ``test_no_retired_roster_strings._EXTENSIONS`` so the two grep-invariant
# modules cover the same surface.
_EXTENSIONS: tuple[str, ...] = (".py", ".yaml", ".yml", ".txt")

# ---------------------------------------------------------------------------
# Forbidden tokens — kept here (and ONLY here, in the test tree) so the
# source tree itself stays free of them.
# ---------------------------------------------------------------------------
_RETIRED_QUEUE_BUILD_LOG_PREFIX: str = "LOG_PREFIX_QUEUE_BUILD"
_RETIRED_QUEUE_BUILD_STUB_LITERAL: str = "queue_build stub"


def _iter_source_files(root: Path) -> list[Path]:
    """Recursively enumerate ``.py``/``.yaml``/``.yml``/``.txt`` files under ``root``.

    ``__pycache__`` directories are skipped — compiled bytecode files are
    not part of the source tree the regression guards.
    """
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in _EXTENSIONS:
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def _find_literal_offenders(forbidden: str, search_root: Path) -> list[str]:
    """Return ``"<rel-path>:<line-no>"`` entries for every line containing ``forbidden``.

    Naming both the file *and* the line number satisfies AC-004 — a
    future regression that reintroduces a retired anchor must surface a
    descriptive failure pointing to the exact location.
    """
    offenders: list[str] = []
    for path in _iter_source_files(search_root):
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Binary or unreadable files are not the regression target.
            continue
        if forbidden not in content:
            continue
        rel = path.relative_to(_PROJECT_ROOT)
        for lineno, line in enumerate(content.splitlines(), start=1):
            if forbidden in line:
                offenders.append(f"{rel}:{lineno}")
    return offenders


def _find_literal_offenders_in_file(forbidden: str, file_path: Path) -> list[str]:
    """Return ``"<rel-path>:<line-no>"`` entries for ``forbidden`` in a single file.

    Mirrors :func:`_find_literal_offenders` but scoped to one file so
    AC-002's narrow ``src/jarvis/tools/dispatch.py`` assertion does not
    pay the cost of a full tree walk.
    """
    offenders: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return offenders
    if forbidden not in content:
        return offenders
    rel = file_path.relative_to(_PROJECT_ROOT)
    for lineno, line in enumerate(content.splitlines(), start=1):
        if forbidden in line:
            offenders.append(f"{rel}:{lineno}")
    return offenders


# ---------------------------------------------------------------------------
# AC-001 — ``LOG_PREFIX_QUEUE_BUILD`` is absent from ``src/jarvis/``.
# ---------------------------------------------------------------------------
class TestAC001NoQueueBuildLogPrefixAnchor:
    """Walk ``src/jarvis/`` and assert the queue-build log-prefix is gone."""

    def test_src_tree_exists(self) -> None:
        # Fail fast with a clear message if the layout has shifted.
        assert _SRC_JARVIS.is_dir(), (
            f"Expected src tree at {_SRC_JARVIS}; layout has changed."
        )

    def test_log_prefix_queue_build_absent_from_src_tree(self) -> None:
        offenders = _find_literal_offenders(
            _RETIRED_QUEUE_BUILD_LOG_PREFIX, _SRC_JARVIS
        )
        assert not offenders, (
            f"Retired Phase 2 anchor {_RETIRED_QUEUE_BUILD_LOG_PREFIX!r} "
            f"reappeared in 'src/jarvis/' — TASK-J005-005 anchor "
            f"retirement broken. Offending locations (file:line): "
            f"{offenders}"
        )


# ---------------------------------------------------------------------------
# AC-002 — ``"queue_build stub"`` is absent from
# ``src/jarvis/tools/dispatch.py``.
# ---------------------------------------------------------------------------
class TestAC002NoQueueBuildStubLiteralInDispatch:
    """The literal ``queue_build stub`` log-line tag is gone from dispatch."""

    def test_dispatch_module_exists(self) -> None:
        assert _DISPATCH_PY.is_file(), (
            f"Expected dispatch module at {_DISPATCH_PY}; layout has changed."
        )

    def test_queue_build_stub_literal_absent_from_dispatch(self) -> None:
        offenders = _find_literal_offenders_in_file(
            _RETIRED_QUEUE_BUILD_STUB_LITERAL, _DISPATCH_PY
        )
        assert not offenders, (
            f"Retired Phase 2 log-line tag "
            f"{_RETIRED_QUEUE_BUILD_STUB_LITERAL!r} reappeared in "
            f"'src/jarvis/tools/dispatch.py' — TASK-J005-005 anchor "
            f"retirement broken. Offending locations (file:line): "
            f"{offenders}"
        )


# ---------------------------------------------------------------------------
# AC-003 — the walk runs in <100 ms.
# ---------------------------------------------------------------------------
class TestAC003WalkPerformance:
    """The grep walk is cheap enough to run on every CI invocation."""

    def test_walk_runs_under_100_ms(self) -> None:
        start = time.perf_counter()
        _ = _find_literal_offenders(
            _RETIRED_QUEUE_BUILD_LOG_PREFIX, _SRC_JARVIS
        )
        _ = _find_literal_offenders_in_file(
            _RETIRED_QUEUE_BUILD_STUB_LITERAL, _DISPATCH_PY
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        # Generous upper bound — the AC pins <100 ms; in practice the
        # walk completes in single-digit ms on a warm filesystem.
        assert elapsed_ms < 100, (
            f"Phase 2 stub-retire grep walk took {elapsed_ms:.1f} ms; "
            f"the AC budget is <100 ms — investigate file-system or "
            f"source-tree growth."
        )


# ---------------------------------------------------------------------------
# AC-004 — failure messages name the offending file when the literal is
# present. Verified by exercising the helper against a synthetic offender
# tree (so the test does not rely on a real reintroduction to prove the
# diagnostic shape).
# ---------------------------------------------------------------------------
class TestAC004FailureNamesOffendingFile:
    """The helpers must surface the offending file (and line) on a hit."""

    def test_finder_reports_offender_path_and_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Build a synthetic mini-tree containing the forbidden literal.
        synthetic_root = tmp_path / "src" / "jarvis"
        synthetic_root.mkdir(parents=True)
        offender = synthetic_root / "offender.py"
        offender.write_text(
            "# leading comment\n"
            f"FOO = '{_RETIRED_QUEUE_BUILD_LOG_PREFIX}'  # leak\n"
            "BAR = 1\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "tests.test_phase2_stubs_retired._PROJECT_ROOT", tmp_path
        )

        offenders = _find_literal_offenders(
            _RETIRED_QUEUE_BUILD_LOG_PREFIX, synthetic_root
        )
        assert offenders == ["src/jarvis/offender.py:2"], (
            f"Expected a single 'src/jarvis/offender.py:2' offender; "
            f"got {offenders!r}"
        )

    def test_file_finder_reports_offender_path_and_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # AC-004 also covers the single-file helper used by AC-002.
        synthetic_dir = tmp_path / "src" / "jarvis" / "tools"
        synthetic_dir.mkdir(parents=True)
        offender = synthetic_dir / "dispatch.py"
        offender.write_text(
            '"""Module docstring."""\n'
            f'logger.info("{_RETIRED_QUEUE_BUILD_STUB_LITERAL} returned")\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(
            "tests.test_phase2_stubs_retired._PROJECT_ROOT", tmp_path
        )

        offenders = _find_literal_offenders_in_file(
            _RETIRED_QUEUE_BUILD_STUB_LITERAL, offender
        )
        assert offenders == ["src/jarvis/tools/dispatch.py:2"], (
            f"Expected a single 'src/jarvis/tools/dispatch.py:2' "
            f"offender; got {offenders!r}"
        )
