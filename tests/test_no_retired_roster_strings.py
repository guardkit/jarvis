"""Regression test — retired four-roster names + JA6 cloud-fallback phrases
+ Phase 2 dispatch stub anchors.

This test guards against accidental reintroduction of legacy strings that
were superseded by FEAT-JARVIS-003 (ADR-ARCH-011 — single ``jarvis-reasoner``
async subagent), the JA6 reset that removed the cloud-cheap-tier
fallback chain, and FEAT-JARVIS-004 (TASK-J004-011 dispatch transport
swap) which retired the Phase 2 stub anchors that pinned the swap point.

Acceptance criteria covered (TASK-J003-020):

- AC-001: walks ``src/jarvis/`` recursively and asserts the four retired
  roster names do NOT appear in any ``.py``, ``.yaml``, or ``.txt`` file.
- AC-002: asserts the rendered :data:`SUPERVISOR_SYSTEM_PROMPT` contains
  none of those four retired names.
- AC-003: asserts :data:`SUPERVISOR_SYSTEM_PROMPT` contains none of the
  retired JA6 cloud-fallback phrases.

Acceptance criteria covered (TASK-J004-020):

- AC-001/AC-002: ``test_no_phase_2_stub_anchors`` walks ``src/jarvis/``
  (with the ``transport_stub`` DEGRADED return-string scoped to
  ``src/jarvis/tools/``) and asserts the four Phase 2 dispatch stub
  anchors do NOT appear, naming the offending file + line on failure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.prompts import SUPERVISOR_SYSTEM_PROMPT

# ---------------------------------------------------------------------------
# Forbidden tokens — kept here (and ONLY here, in the test tree) so the
# source tree itself stays free of them. The walk in
# ``test_src_tree_free_of_retired_names`` therefore reads the fixture from
# this module's globals rather than literal strings inline.
# ---------------------------------------------------------------------------
_RETIRED_ROSTER_NAMES: tuple[str, ...] = (
    "deep_reasoner",
    "adversarial_critic",
    "long_research",
    "quick_local",
)

_RETIRED_JA6_CLOUD_FALLBACK_PHRASES: tuple[str, ...] = (
    "vllm fallback",
    "gemini-flash-latest",
    "cloud cheap-tier",
)

# Project root resolved relative to this test file: tests/<file>.py →
# project root is two ``parent`` hops up.
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_SRC_JARVIS: Path = _PROJECT_ROOT / "src" / "jarvis"

# Extensions covered by the regression walk.
_EXTENSIONS: tuple[str, ...] = (".py", ".yaml", ".yml", ".txt")


def _iter_source_files() -> list[Path]:
    """Recursively enumerate ``.py``/``.yaml``/``.txt`` files under ``src/jarvis``.

    ``__pycache__`` directories are skipped — compiled bytecode files are
    not part of the source tree the regression guards.
    """
    files: list[Path] = []
    for path in _SRC_JARVIS.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in _EXTENSIONS:
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def _render_supervisor_prompt() -> str:
    """Fill the supervisor prompt's runtime placeholders with placeholder text.

    The asserted forbidden tokens are independent of the runtime values
    that get injected at agent build time, so we substitute neutral
    sentinel strings rather than reaching for the live ``build_supervisor``
    pipeline.
    """
    return SUPERVISOR_SYSTEM_PROMPT.format(
        date="2026-04-26",
        available_capabilities="<capabilities-block>",
        domain_prompt="<domain-prompt-block>",
    )


# ---------------------------------------------------------------------------
# AC-001 — source tree is free of the four retired roster names.
# ---------------------------------------------------------------------------
class TestAC001SourceTreeFreeOfRetiredRosterNames:
    """Walk ``src/jarvis/`` and assert no retired roster name appears."""

    def test_src_tree_exists(self) -> None:
        # Fail fast with a clear message if the layout has shifted.
        assert _SRC_JARVIS.is_dir(), f"Expected src tree at {_SRC_JARVIS}; layout has changed."

    @pytest.mark.parametrize("forbidden", _RETIRED_ROSTER_NAMES)
    def test_retired_name_not_in_any_source_file(self, forbidden: str) -> None:
        offenders: list[str] = []
        for path in _iter_source_files():
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # Binary or unreadable files are not the regression target.
                continue
            if forbidden in content:
                offenders.append(str(path.relative_to(_PROJECT_ROOT)))
        assert not offenders, (
            f"Retired roster name {forbidden!r} found in source files: {offenders}"
        )


# ---------------------------------------------------------------------------
# AC-002 — rendered SUPERVISOR_SYSTEM_PROMPT contains none of the four
# retired roster names.
# ---------------------------------------------------------------------------
class TestAC002SupervisorPromptFreeOfRetiredNames:
    """Rendered supervisor prompt must not mention the four-roster legacy."""

    @pytest.mark.parametrize("forbidden", _RETIRED_ROSTER_NAMES)
    def test_rendered_prompt_excludes_retired_name(self, forbidden: str) -> None:
        rendered = _render_supervisor_prompt()
        assert forbidden not in rendered, (
            f"SUPERVISOR_SYSTEM_PROMPT mentions retired roster name {forbidden!r}"
        )


# ---------------------------------------------------------------------------
# AC-003 — rendered SUPERVISOR_SYSTEM_PROMPT contains no retired JA6
# cloud-fallback phrase.
# ---------------------------------------------------------------------------
class TestAC003SupervisorPromptFreeOfJA6CloudFallback:
    """Rendered supervisor prompt must not mention the retired JA6 fallbacks."""

    @pytest.mark.parametrize("forbidden", _RETIRED_JA6_CLOUD_FALLBACK_PHRASES)
    def test_rendered_prompt_excludes_cloud_fallback_phrase(self, forbidden: str) -> None:
        rendered = _render_supervisor_prompt().lower()
        assert forbidden.lower() not in rendered, (
            f"SUPERVISOR_SYSTEM_PROMPT mentions retired JA6 cloud-fallback phrase {forbidden!r}"
        )


# ---------------------------------------------------------------------------
# TASK-J004-020 — Phase 2 dispatch stub anchors retirement gate.
#
# TASK-J002-021 originally landed a grep test that pinned the presence of
# ``LOG_PREFIX_DISPATCH = "JARVIS_DISPATCH_STUB"`` in
# ``src/jarvis/tools/dispatch.py`` as the DDR-009 swap-point anchor for the
# Phase 2 stub. FEAT-JARVIS-004 (TASK-J004-011) swapped the dispatch body
# to a real NATS round-trip and deleted the four anchors that pinned the
# old transport. This test is the *flipped* invariant: assert the four
# anchors are GONE.
#
# Forbidden tokens (paired with their search root):
#
# - ``LOG_PREFIX_DISPATCH``    — the retired swap-point constant name.
# - ``_stub_response_hook``    — the retired Phase 2 test stub callable.
# - ``JARVIS_DISPATCH_STUB``   — the retired log-prefix grep token.
# - ``DEGRADED: transport_stub`` — the retired DEGRADED return-shape that
#   the Phase 2 stub emitted; bare ``transport_stub`` is preserved as a
#   stable :class:`~jarvis.tools.types.DispatchError` vocabulary entry per
#   DDR-009, so the assertion targets the full DEGRADED literal that was
#   actually retired.
#
# The ``transport_stub`` check is scoped to ``src/jarvis/tools/`` per the
# task AC; the other three are scoped to all of ``src/jarvis/``.
# ---------------------------------------------------------------------------
_RETIRED_PHASE_2_STUB_ANCHORS: tuple[tuple[str, str], ...] = (
    ("LOG_PREFIX_DISPATCH", "src/jarvis"),
    ("_stub_response_hook", "src/jarvis"),
    ("JARVIS_DISPATCH_STUB", "src/jarvis"),
    ("DEGRADED: transport_stub", "src/jarvis/tools"),
)


def _iter_files_under(root: Path) -> list[Path]:
    """Recursively enumerate ``.py``/``.yaml``/``.yml``/``.txt`` files under ``root``.

    Mirrors :func:`_iter_source_files` but with a configurable root so the
    Phase 2 stub-anchor walk can scope ``transport_stub`` to
    ``src/jarvis/tools/`` without re-implementing the traversal.
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


def _find_anchor_offenders(forbidden: str, search_root: Path) -> list[str]:
    """Return ``"<rel-path>:<line-no>"`` entries for every line containing ``forbidden``.

    Naming both the file *and* the line number satisfies AC-002 of
    TASK-J004-020 — a future regression that reintroduces a retired
    anchor must surface a descriptive failure pointing to the exact
    location.
    """
    offenders: list[str] = []
    for path in _iter_files_under(search_root):
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


class TestNoPhase2StubAnchors:
    """All four retired Phase 2 stub anchors are absent from the source tree.

    TASK-J004-020 acceptance criteria:

    - AC-001: ``tests/test_no_retired_roster_strings.py`` extended with
      ``test_no_phase_2_stub_anchors``; all 4 retired strings asserted
      absent from ``src/jarvis/`` (with the ``transport_stub`` DEGRADED
      string scoped to ``src/jarvis/tools/`` per the AC).
    - AC-002: Test fails (descriptively, naming the file + line) if any
      retired anchor reappears.
    """

    @pytest.mark.parametrize(
        ("forbidden", "search_root"),
        _RETIRED_PHASE_2_STUB_ANCHORS,
        ids=[token for token, _ in _RETIRED_PHASE_2_STUB_ANCHORS],
    )
    def test_no_phase_2_stub_anchors(self, forbidden: str, search_root: str) -> None:
        root = _PROJECT_ROOT / search_root
        assert root.is_dir(), f"Expected search root at {root}; layout has changed."
        offenders = _find_anchor_offenders(forbidden, root)
        assert not offenders, (
            f"Retired Phase 2 stub anchor {forbidden!r} reappeared in "
            f"{search_root!r} — TASK-J004-011 swap-point retirement broken. "
            f"Offending locations (file:line): {offenders}"
        )

    def test_all_four_anchors_enumerated(self) -> None:
        """Sanity guard: the AC enumerates exactly four retired anchors."""
        assert len(_RETIRED_PHASE_2_STUB_ANCHORS) == 4
        tokens = {token for token, _ in _RETIRED_PHASE_2_STUB_ANCHORS}
        assert tokens == {
            "LOG_PREFIX_DISPATCH",
            "_stub_response_hook",
            "JARVIS_DISPATCH_STUB",
            "DEGRADED: transport_stub",
        }
