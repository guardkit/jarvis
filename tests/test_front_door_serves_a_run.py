"""The front door's graph factory, driven the way its server drives it.

Written 26 September 2026, after a rehearsal of the estate found that the
front door answered its health route and failed EVERY run asked of its API.
Two faults, both of them in this repository, both of them about the same
thing — the server builds the graph on its own running event loop:

1. ``supervisor.make_graph`` called ``asyncio.run(build_app_state(...))``,
   and ``asyncio.run`` refuses to be called from inside a running loop.
2. ``jarvis.config.settings`` resolved a relative path in its class body, so
   importing it asked the operating system for the current directory. The
   server's blocking-call detector refuses that on its loop, and the import
   happens there because the factory imports the module lazily.

Neither fault can be caught by a test that calls the factory from a
synchronous test body, which is why the whole of this file is about calling it
the way the server does. There are two ways to read "the way the server
does", and both are here:

* the real dispatch of the pinned runtime — ``classify_factory`` +
  ``invoke_factory`` + ``as_asynccontextmanager`` from ``langgraph-api``,
  which is the code path a run actually takes;
* a plain running loop, so the contract still has a test on a machine where
  the front-door extra is not installed.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
STUB_CAPABILITIES: Path = (
    REPO_ROOT / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
)


# ---------------------------------------------------------------------------
# A stand-in application state. These tests are about the SHAPE of the call —
# that the factory can be driven from inside a running loop and that it builds
# its state once — not about what ``build_app_state`` wires, which its own
# tests cover and which would want a bus and a model seat.
# ---------------------------------------------------------------------------
class _FakeSupervisor:
    """Stands in for the compiled graph ``build_app_state`` returns."""


class _FakeAppState:
    def __init__(self) -> None:
        self.supervisor = _FakeSupervisor()


@pytest.fixture
def factory_module() -> Any:
    """A fresh copy of the supervisor module, with its state cache empty.

    The module caches the application state it builds, so a test that left a
    built state behind would change what the next test measures. Importing a
    fresh copy is cheaper and clearer than reaching in to reset it.
    """
    saved = sys.modules.pop("jarvis.agents.supervisor", None)
    try:
        module = importlib.import_module("jarvis.agents.supervisor")
        yield module
    finally:
        if saved is not None:
            sys.modules["jarvis.agents.supervisor"] = saved
        else:
            sys.modules.pop("jarvis.agents.supervisor", None)


class TestTheFactoryWorksInsideARunningLoop:
    """The fault that stopped every run, and the contract that closes it."""

    def test_the_factory_is_a_coroutine_function(self, factory_module: Any) -> None:
        """A synchronous factory cannot await the lifecycle.

        ``build_app_state`` is a coroutine, the server has a loop running, and
        the only ways to get from one to the other are to await it (this) or
        to start a second loop (which raises, or leaves the state on a loop
        that will never run the graph).
        """
        assert asyncio.iscoroutinefunction(factory_module.make_graph)

    def test_the_factory_returns_a_graph_from_inside_a_running_loop(
        self, factory_module: Any
    ) -> None:
        built: list[Any] = []

        async def fake_build_app_state(config: Any) -> Any:
            built.append(config)
            return _FakeAppState()

        async def drive() -> Any:
            # Proves there IS a loop running when the factory is called — the
            # condition under which the old factory raised RuntimeError.
            assert asyncio.get_running_loop() is not None
            return await factory_module.make_graph()

        with (
            patch(
                "jarvis.infrastructure.lifecycle.build_app_state",
                new=fake_build_app_state,
            ),
            patch("jarvis.config.settings.JarvisConfig", return_value=object()),
        ):
            graph = asyncio.run(drive())

        assert isinstance(graph, _FakeSupervisor)
        assert len(built) == 1

    def test_the_state_is_built_once_however_many_runs_arrive(
        self, factory_module: Any
    ) -> None:
        """One bus connection and one Slack session, not one per run.

        ``build_app_state`` opens this process's bus connection, registers on
        the fleet, starts a heartbeat and opens the one Slack Socket Mode
        session. The server asks for a graph on every run, so a factory that
        rebuilt each time would open a second Slack socket on the second run.
        """
        calls: list[Any] = []

        async def fake_build_app_state(config: Any) -> Any:
            calls.append(config)
            await asyncio.sleep(0)
            return _FakeAppState()

        async def drive() -> list[Any]:
            # Together, so the lock is doing the work rather than luck.
            first, second = await asyncio.gather(
                factory_module.make_graph(), factory_module.make_graph()
            )
            third = await factory_module.make_graph()
            return [first, second, third]

        with (
            patch(
                "jarvis.infrastructure.lifecycle.build_app_state",
                new=fake_build_app_state,
            ),
            patch("jarvis.config.settings.JarvisConfig", return_value=object()),
        ):
            graphs = asyncio.run(drive())

        assert len(calls) == 1, (
            f"the lifecycle was built {len(calls)} times; the front door has one "
            f"bus connection and one Slack session, so it must be built once"
        )
        assert graphs[0] is graphs[1] is graphs[2]

    def test_the_pinned_server_dispatch_awaits_this_factory(
        self, factory_module: Any
    ) -> None:
        """Driven through ``langgraph-api``'s own factory dispatch.

        This is the code a run really goes through: the runtime classifies the
        factory by its signature, calls it with what that signature declares,
        and normalises the result — awaiting a coroutine, entering an async
        context manager, or passing a plain value on. If a future runtime
        stopped awaiting coroutine factories, this test is what would say so.
        """
        factory_utils = pytest.importorskip("langgraph_api._factory_utils")
        lg_asyncio = pytest.importorskip("langgraph_api.asyncio")

        async def fake_build_app_state(config: Any) -> Any:
            return _FakeAppState()

        graph_id = "jarvis-under-test"
        factory_utils.FACTORY_KWARGS.pop(graph_id, None)
        factory_utils.classify_factory(factory_module.make_graph, graph_id)

        async def drive() -> Any:
            produced = factory_utils.invoke_factory(
                factory_module.make_graph,
                graph_id,
                {"configurable": {}},
                None,
            )
            async with lg_asyncio.as_asynccontextmanager(produced) as graph:
                return graph

        try:
            with (
                patch(
                    "jarvis.infrastructure.lifecycle.build_app_state",
                    new=fake_build_app_state,
                ),
                patch("jarvis.config.settings.JarvisConfig", return_value=object()),
            ):
                graph = asyncio.run(drive())
        finally:
            factory_utils.FACTORY_KWARGS.pop(graph_id, None)

        assert isinstance(graph, _FakeSupervisor)


class TestImportingTheSettingsTouchesNoFilesystem:
    """The second fault: a default that asked the operating system a question.

    ``Path(".").resolve()`` in the class body calls ``os.getcwd``. The
    front door's server refuses that on its event loop, and it imports this
    module there. So the test breaks both calls and imports the module fresh:
    an import that needs either of them raises, and the test fails.
    """

    @staticmethod
    def _import_fresh_with_the_filesystem_broken() -> Any:
        def refuse_getcwd() -> str:
            raise AssertionError(
                "importing jarvis.config.settings asked for the current working "
                "directory. The front door's server refuses that call on its own "
                "event loop, which is where this module is imported, and every run "
                "asked of the front door failed on it."
            )

        def refuse_resolve(self: Path, *args: Any, **kwargs: Any) -> Path:
            raise AssertionError(
                "importing jarvis.config.settings resolved a path. Resolving a "
                "relative path asks for the current working directory, which the "
                "front door's server refuses on its own event loop."
            )

        saved = {
            name: module
            for name, module in sys.modules.items()
            if name == "jarvis.config.settings"
        }
        for name in saved:
            del sys.modules[name]
        try:
            with (
                patch.object(os, "getcwd", refuse_getcwd),
                patch.object(Path, "resolve", refuse_resolve),
            ):
                return importlib.import_module("jarvis.config.settings")
        finally:
            sys.modules.pop("jarvis.config.settings", None)
            sys.modules.update(saved)

    def test_the_import_does_no_filesystem_work(self) -> None:
        module = self._import_fresh_with_the_filesystem_broken()
        assert module.JarvisConfig is not None

    def test_constructing_the_config_does_no_filesystem_work(self) -> None:
        """Not only the import — a ``default_factory`` would move the same
        call to this moment, which is also on the server's loop.
        """

        def refuse_getcwd() -> str:
            raise AssertionError(
                "constructing JarvisConfig asked for the current working "
                "directory; the front door's server refuses that on its loop"
            )

        from jarvis.config.settings import JarvisConfig

        with (
            patch.dict("os.environ", {}, clear=True),
            patch.object(os, "getcwd", refuse_getcwd),
        ):
            config = JarvisConfig()

        assert config.workspace_root == Path(".")

    def test_the_stub_capabilities_default_is_still_relative(self) -> None:
        """A sibling of the same defect, named so it stays fixed.

        This default is a relative path and reading it happens later, in a
        worker thread. It is asserted here so that "make it absolute at
        import" is not tried as a tidy-up.
        """
        from jarvis.config.settings import JarvisConfig

        with patch.dict("os.environ", {}, clear=True):
            config = JarvisConfig()
        assert not config.stub_capabilities_path.is_absolute()
        assert STUB_CAPABILITIES.exists()
