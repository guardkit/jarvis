"""pytest-bdd collection bridge for ``features/`` (TASK-OPS-J002-BDD).

Two responsibilities:

1. **Collection bridge** — pytest-bdd v8 does not register a
   ``pytest_collect_file`` hook for ``.feature`` files. GuardKit's
   ``bdd_runner.run_bdd_for_task`` (TASK-OPS-BDDM-9) invokes pytest with
   the literal ``.feature`` path as a positional argv:

       pytest --gherkin-terminal-reporter --junitxml=... \
              -m <sanitised_tag> features/<slug>/<slug>.feature

   Without a bridge pytest exits 4 ("not found") because the file has no
   registered collector. The :func:`pytest_collect_file` hook below
   redirects ``.feature`` argv to the sibling ``test_<slug>.py`` glue
   module that calls :func:`pytest_bdd.scenarios` to bind the file. The
   glue module is what actually produces the pytest items; the hook just
   makes sure pytest does not bail out before pytest-bdd's machinery runs.

2. **Tag → marker sanitisation** — pytest-bdd's default
   :func:`pytest_bdd_apply_tag` registers a marker with the literal tag
   string (so ``@task:TASK-J002-008`` becomes ``pytest.mark["task:TASK-J002-008"]``).
   GuardKit's ``bdd_runner._build_pytest_argv`` sanitises the same tag to
   ``task_TASK_J002_008`` for the ``-m`` filter (``:`` and ``-`` are not
   valid identifier chars in pytest marker expressions). The override
   below applies the same sanitisation so the ``-m`` filter actually
   matches the registered markers.

See ``tasks/in_progress/TASK-OPS-J002-BDD-pytest-collection-wiring.md`` and
``guardkit/orchestrator/quality_gates/bdd_runner.py`` for the full contract.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest


def _sanitise_tag(tag: str) -> str:
    """Mirror ``bdd_runner._build_pytest_argv``'s tag normalisation.

    Strips a leading ``@`` (Gherkin tags carry it; pytest markers don't),
    then replaces ``:`` and ``-`` with ``_`` so the result is a valid
    pytest marker identifier.
    """
    return tag.lstrip("@").replace(":", "_").replace("-", "_")


def pytest_bdd_apply_tag[T: Callable[..., object]](tag: str, function: T) -> T:
    """Register Gherkin tags as sanitised pytest markers.

    Returning a non-``None`` value short-circuits pytest-bdd's default
    implementation (which uses the literal tag as the marker name). See
    module docstring for why sanitisation is required.
    """
    mark = getattr(pytest.mark, _sanitise_tag(tag))
    return cast(T, mark(function))


class _FeatureFile(pytest.File):
    """Collector whose ``path`` matches the ``.feature`` argv.

    pytest's args resolver matches positional argv against collector
    ``path`` attributes. Returning a :class:`pytest.Module` whose path is
    the sibling ``.py`` glue makes pytest report "not found" for the
    original ``.feature`` arg even though the hook fired. Subclassing
    :class:`pytest.File` keeps the ``.feature`` path on the collector
    while delegating actual item collection to the glue module via
    :class:`pytest.Module`'s normal import machinery.
    """

    def collect(self) -> Iterator[Any]:
        glue = self.path.with_name(f"test_{self.path.stem.replace('-', '_')}.py")
        if not glue.is_file():
            return
        module_collector = pytest.Module.from_parent(self.parent, path=glue)
        yield from module_collector.collect()


def pytest_collect_file(parent: pytest.Collector, file_path: Path) -> pytest.Collector | None:
    """Bridge ``.feature`` argv to the sibling ``test_<slug>.py`` glue.

    pytest does not natively know how to collect ``.feature`` files.
    Without this hook, ``pytest features/.../x.feature`` exits 4
    ("not found") even when a glue module exists, because pytest's args
    resolver looks for a collector whose path matches the argv.

    The glue file naming convention is ``test_<feature_stem>.py`` with
    hyphens converted to underscores (Python identifier rules). The glue
    module is responsible for calling :func:`pytest_bdd.scenarios` to bind
    the feature file; the :class:`_FeatureFile` collector above forwards
    pytest's collection to that glue while keeping the ``.feature`` path
    on the collector so the arg resolver succeeds.

    Returning ``None`` for paths without a sibling glue lets pytest fall
    through to its default handling (and surface the original "not found"
    error), so missing-glue cases are not silently swallowed.
    """
    if file_path.suffix != ".feature":
        return None
    glue = file_path.with_name(f"test_{file_path.stem.replace('-', '_')}.py")
    if not glue.is_file():
        return None
    return _FeatureFile.from_parent(parent, path=file_path)
