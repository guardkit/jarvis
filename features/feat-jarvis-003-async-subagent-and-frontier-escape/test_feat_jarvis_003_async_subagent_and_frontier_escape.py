"""pytest-bdd glue module for ``feat-jarvis-003-async-subagent-and-frontier-escape.feature``.

Binds the sibling ``.feature`` file's scenarios into pytest's collection
tree via :func:`pytest_bdd.scenarios`. This is the same shape as the
FEAT-JARVIS-002 glue (see
``features/feat-jarvis-002-core-tools-and-dispatch/test_feat_jarvis_002_core_tools_and_dispatch.py``)
and is required by ``features/conftest.py``'s ``_FeatureFile.collect``
hook — without a glue file at this path, ``pytest <slug>.feature`` exits
4 ("not found") and the GuardKit BDD runner reports zero scenarios
collected for the task.

No ``@given/@when/@then`` step-defs are implemented yet — every scenario
will surface as ``scenarios_pending`` in ``BDDResult`` (pytest-bdd raises
``StepDefinitionNotFoundError`` per the FEAT-BDDM convention). Filing
real step-defs is intentionally out of scope for the Layer-1 dispatch
work in TASK-J003-010; subsequent FEAT-J003 tasks (and the dedicated
BDD-step backlog) carry that load.
"""

from __future__ import annotations

from pytest_bdd import scenarios

scenarios("./feat-jarvis-003-async-subagent-and-frontier-escape.feature")
