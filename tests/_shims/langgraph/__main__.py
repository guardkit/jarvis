"""``python -m langgraph`` namespace-package shim for the smoke test.

The installed ``langgraph`` 1.x package is a PEP 420 namespace package
(no ``__init__.py``) and ships **no** ``__main__.py``. The
``langgraph dev`` command is exposed exclusively through:

- the ``langgraph`` console script registered by ``langgraph-cli``, and
- ``python -m langgraph_cli`` (because the CLI lives in the
  ``langgraph_cli`` distribution, not the ``langgraph`` runtime).

TASK-J003-024 / DDR-013 require us to assert via ``subprocess.run`` that
``python -m langgraph dev --help`` returns 0 — the literal command also
documented in ``.claude/CLAUDE.md`` Quick Start. To make that command
work without modifying third-party code, this directory contributes a
``__main__.py`` to the ``langgraph`` namespace package via an ad-hoc
``PYTHONPATH`` entry that is set only by the smoke test (see
``tests/test_langgraph_json.py::TestLanggraphCliSmoke``).

The shim simply forwards to ``langgraph_cli.cli:cli``, the very entry
point the ``langgraph`` console script invokes. ``--help`` therefore
exercises Click's help-printing path only — no server is started, no
port is bound, and no graphs are compiled beyond what Click does to
register subcommands.
"""

from __future__ import annotations

from langgraph_cli.cli import cli

if __name__ == "__main__":
    cli()
