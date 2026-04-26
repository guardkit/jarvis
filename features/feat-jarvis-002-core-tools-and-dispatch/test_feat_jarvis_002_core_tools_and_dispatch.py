"""pytest-bdd glue module for ``feat-jarvis-002-core-tools-and-dispatch.feature``.

Binds the sibling ``.feature`` file's scenarios into pytest's collection tree
via :func:`pytest_bdd.scenarios`. No ``@given/@when/@then`` step-defs are
implemented yet — every scenario will surface as ``scenarios_pending`` in
``BDDResult`` (pytest-bdd raises ``StepDefinitionNotFoundError`` per
TASK-OPS-J002-BDD acceptance criteria).

Implementing step-defs is intentionally NOT in scope here; per FEAT-BDDM
follow-up convention, scenarios that fail real assertions (vs missing
step-defs) get filed as their own follow-up tasks.
"""

from __future__ import annotations

from pytest_bdd import scenarios

scenarios("./feat-jarvis-002-core-tools-and-dispatch.feature")
