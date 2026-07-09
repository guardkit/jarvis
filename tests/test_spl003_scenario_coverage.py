"""FEAT-SPL-003 scenario-coverage guard (TASK-SPL003-J04).

Cross-checks the 25 ``.feature`` scenarios against ``@task:`` ownership (every
scenario owned by exactly one build task) and pins the scenario counts
collect-only, so a scenario cannot be silently added/removed/orphaned without
this guard failing. Pure text inspection — hermetic.
"""

from __future__ import annotations

import re
from pathlib import Path

_FEATURE = (
    Path(__file__).parent.parent
    / "features"
    / "feat-spl-003-assumption-dialogue"
    / "feat-spl-003-assumption-dialogue.feature"
)

# Collect-only pins (the frozen shape of the feature file).
_EXPECTED_TOTAL_SCENARIOS = 25
_EXPECTED_PER_TASK = {
    "TASK-SPL003-J01": 6,
    "TASK-SPL003-J02": 9,
    "TASK-SPL003-J03a": 9,
    "TASK-SPL003-J03b": 1,
}

_SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:", re.MULTILINE)
_TASK_TAG_RE = re.compile(r"@task:(TASK-SPL003-J0[0-9a-b]+)")


def _text() -> str:
    return _FEATURE.read_text(encoding="utf-8")


def test_feature_file_exists() -> None:
    assert _FEATURE.is_file(), f"missing feature file: {_FEATURE}"


def test_scenario_count_pinned() -> None:
    scenarios = _SCENARIO_RE.findall(_text())
    assert len(scenarios) == _EXPECTED_TOTAL_SCENARIOS


def test_every_scenario_is_task_tagged() -> None:
    """One @task: tag per scenario — no scenario orphaned, none double-owned."""
    task_tags = _TASK_TAG_RE.findall(_text())
    assert len(task_tags) == _EXPECTED_TOTAL_SCENARIOS


def test_per_task_scenario_counts_pinned() -> None:
    task_tags = _TASK_TAG_RE.findall(_text())
    counts: dict[str, int] = {}
    for tag in task_tags:
        counts[tag] = counts.get(tag, 0) + 1
    assert counts == _EXPECTED_PER_TASK


def test_all_tags_reference_known_tasks() -> None:
    task_tags = set(_TASK_TAG_RE.findall(_text()))
    assert task_tags == set(_EXPECTED_PER_TASK)
