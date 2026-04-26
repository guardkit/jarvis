"""Regression test — retired four-roster names + JA6 cloud-fallback phrases.

This test guards against accidental reintroduction of legacy strings that
were superseded by FEAT-JARVIS-003 (ADR-ARCH-011 — single ``jarvis-reasoner``
async subagent) and the JA6 reset that removed the cloud-cheap-tier
fallback chain.

Acceptance criteria covered (TASK-J003-020):

- AC-001: walks ``src/jarvis/`` recursively and asserts the four retired
  roster names do NOT appear in any ``.py``, ``.yaml``, or ``.txt`` file.
- AC-002: asserts the rendered :data:`SUPERVISOR_SYSTEM_PROMPT` contains
  none of those four retired names.
- AC-003: asserts :data:`SUPERVISOR_SYSTEM_PROMPT` contains none of the
  retired JA6 cloud-fallback phrases.
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
