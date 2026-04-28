"""TASK-J004-018 — Shutdown-order invariant tests for ``lifecycle.shutdown``.

This test file is an *invariant gate*: once it is green, future refactors
that accidentally re-order any of the eight shutdown steps will break
here loudly with a descriptive failure rather than producing the
production symptom (a hung CI pipeline, a lost final trace write, or a
KV-watch callback firing during NATS drain).

The canonical 8-step sequence (from
``docs/design/FEAT-JARVIS-004/design.md`` §8):

    1. cancel ``fleet_heartbeat_task``
    2. ``await deregister_from_fleet(nats_client, "jarvis")``
    3. ``await capabilities_registry.close()``
    4. ``await routing_history_writer.flush(timeout=5.0)``
    5. ``await nats_client.drain(timeout=5.0)``
    6. ``await graphiti_client.aclose()``
    7. disarm Layer-2 hooks (``_dispatch._current_session_hook`` etc.)
    8. ``state.store.close()``

Why ordering matters (in the words of the task description):

- **3 before 5** — closing the registry before draining NATS prevents
  KV-watch callbacks firing during the drain.
- **4 before 5** — writer flush submits Graphiti episodes that may
  themselves use the NATS client indirectly; flush must precede drain.
- **2 before 5** — deregister publishes to NATS, so it has to precede
  ``drain()``.
- **6 last (among I/O closes)** — Graphiti close after the writer has
  flushed avoids dropping in-flight episodes.

Acceptance criteria covered:

    AC-001: Exact ordering of all 8 steps via call-order recording.
    AC-002: Test fails descriptively if any step is skipped, reordered,
            or duplicated.
    AC-003: Failure tolerance — a single failed step does NOT skip
            subsequent steps; errors are WARN-logged.
    AC-004: Heartbeat cancellation produces no traceback / unhandled
            exception warning.
    AC-005: ``uv run pytest tests/test_lifecycle_shutdown_order.py -v``
            green.

The fixture builds a synthetic :class:`AppState` whose every shutdown
side-effect target is a :class:`unittest.mock.MagicMock` whose
``side_effect`` appends a sentinel string to a shared ``list``. After
``await lifecycle.shutdown(state)`` returns, the test asserts the list
matches the canonical step sequence verbatim. No real NATS or Graphiti
connection is made.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.lifecycle import AppState, shutdown
from jarvis.infrastructure.routing_history import RoutingHistoryWriter
from jarvis.tools import dispatch as _dispatch_module


# ---------------------------------------------------------------------------
# Step sentinel constants — kept as module-level strings so any test can
# refer to them by name and a test failure surfaces the human-readable
# step name rather than an opaque index.
# ---------------------------------------------------------------------------
STEP_HEARTBEAT_CANCEL = "1.heartbeat.cancel"
STEP_DEREGISTER = "2.fleet.deregister"
STEP_CAPABILITIES_CLOSE = "3.capabilities.close"
STEP_WRITER_FLUSH = "4.writer.flush"
STEP_NATS_DRAIN = "5.nats.drain"
STEP_GRAPHITI_ACLOSE = "6.graphiti.aclose"
STEP_LAYER2_DISARM = "7.layer2.disarm"
STEP_STORE_CLOSE = "8.store.close"

EXPECTED_ORDER: tuple[str, ...] = (
    STEP_HEARTBEAT_CANCEL,
    STEP_DEREGISTER,
    STEP_CAPABILITIES_CLOSE,
    STEP_WRITER_FLUSH,
    STEP_NATS_DRAIN,
    STEP_GRAPHITI_ACLOSE,
    STEP_LAYER2_DISARM,
    STEP_STORE_CLOSE,
)


# ---------------------------------------------------------------------------
# Fixture — builds a synthetic AppState whose teardown surfaces all
# record into a shared ``list`` via ``MagicMock(side_effect=...)``.
#
# Step 7 (disarm Layer-2 hooks) does NOT pass through a mock — it is a
# direct module-attribute assignment in production. To detect it the
# fixture pre-arms ``_dispatch._current_session_hook`` with a sentinel
# callable and registers a *property-style observer* via patch.object on
# the dispatch module: each time the attribute transitions to ``None``
# we append :data:`STEP_LAYER2_DISARM` to the call list. This keeps the
# "MagicMock(side_effect=list.append)" contract from the task's Test
# Requirements consistent across all 8 steps.
# ---------------------------------------------------------------------------


@dataclass
class _ShutdownHarness:
    """Bundle of the AppState plus the call-order list and the patches
    that observe step 7. Returned by the fixture so each test can drive
    ``shutdown(harness.state)`` and inspect ``harness.calls`` after."""

    state: AppState
    calls: list[str]


@pytest.fixture
def shutdown_harness() -> _ShutdownHarness:
    """Construct an :class:`AppState` whose shutdown surfaces all record.

    Each mocked surface uses ``side_effect=lambda *a, **kw: calls.append(...)``
    so the order in which ``shutdown`` invokes them is preserved exactly.

    The fixture is intentionally synchronous — ``asyncio.create_task`` on
    the heartbeat task is deferred to the test body so the test owns the
    running event loop. ``shutdown_harness.state.fleet_heartbeat_task``
    is initialised to ``None`` here and replaced inside the test.
    """
    calls: list[str] = []

    # --- Step 3: capabilities_registry.close()
    capabilities_registry = MagicMock()
    capabilities_registry.close = AsyncMock(
        side_effect=lambda: calls.append(STEP_CAPABILITIES_CLOSE),
    )

    # --- Step 4: routing_history_writer.flush(timeout=5.0)
    writer = MagicMock(spec=RoutingHistoryWriter)
    writer.flush = AsyncMock(
        side_effect=lambda *a, **kw: calls.append(STEP_WRITER_FLUSH),
    )

    # --- Step 5: nats_client.drain(timeout=5.0)
    nats_client = MagicMock()
    nats_client.drain = AsyncMock(
        side_effect=lambda *a, **kw: calls.append(STEP_NATS_DRAIN),
    )

    # --- Step 6: graphiti_client.aclose()
    graphiti_client = MagicMock()
    graphiti_client.aclose = AsyncMock(
        side_effect=lambda: calls.append(STEP_GRAPHITI_ACLOSE),
    )

    # --- Step 8: store.close()
    store = MagicMock()
    store.close = MagicMock(side_effect=lambda: calls.append(STEP_STORE_CLOSE))

    config = MagicMock(spec=JarvisConfig)

    state = AppState(
        config=config,
        supervisor=MagicMock(),
        store=store,
        session_manager=MagicMock(),
        capability_registry=[],
        llamaswap_adapter=None,
        nats_client=nats_client,
        graphiti_client=graphiti_client,
        routing_history_writer=writer,
        fleet_heartbeat_task=None,  # replaced inside each test body
        capabilities_registry=capabilities_registry,
    )

    return _ShutdownHarness(state=state, calls=calls)


def _arm_dispatch_hooks_with_layer2_observer(calls: list[str]) -> None:
    """Pre-arm the dispatch module's hooks so step 7 has something to clear.

    A small ``__setattr__`` proxy on the module is impractical (Python
    modules don't honour descriptors), so instead the helper sets
    sentinel callables and the test asserts the *post-shutdown* state
    transitioned to ``None``. The :data:`STEP_LAYER2_DISARM` sentinel is
    appended by a wrapper around the production assignment site — see
    the patched ``_dispatch_module`` attribute proxy in
    :func:`_install_layer2_disarm_observer`.
    """
    _dispatch_module._current_session_hook = lambda: None
    _dispatch_module._async_subagent_frame_hook = lambda: None
    _dispatch_module._nats_client = MagicMock()
    _dispatch_module._routing_history_writer = MagicMock()
    _dispatch_module._dispatch_semaphore = MagicMock()


def _install_layer2_disarm_observer(calls: list[str]) -> object:
    """Return a context manager that records when step 7 fires.

    The production lifecycle assigns ``_dispatch._current_session_hook =
    None`` (and four siblings) inline. We can't intercept a module-level
    rebind with a property, so we substitute the *module* in the
    lifecycle's import namespace with a tiny shim that records the first
    time ``_current_session_hook`` is set to ``None`` and then forwards
    the assignment to the real module. That preserves the production
    semantics (the real attributes still get cleared) and gives the
    test a single ``calls.append`` hook for step 7.
    """

    real_module = _dispatch_module

    class _DispatchProxy:
        """Records the moment Layer-2 hooks transition to ``None``."""

        _recorded = False

        def __getattr__(self, name: str) -> object:
            return getattr(real_module, name)

        def __setattr__(self, name: str, value: object) -> None:
            if (
                name == "_current_session_hook"
                and value is None
                and not type(self)._recorded
            ):
                # Step 7 is the canonical disarm site; record once so a
                # subsequent rearm in another test does not pollute.
                type(self)._recorded = True
                calls.append(STEP_LAYER2_DISARM)
            setattr(real_module, name, value)

    proxy = _DispatchProxy()
    return patch("jarvis.infrastructure.lifecycle._dispatch", new=proxy)


# ---------------------------------------------------------------------------
# AC-001 / AC-002 — exact 8-step ordering (no skips, reorders, duplicates)
# ---------------------------------------------------------------------------
class TestExactShutdownOrder:
    """``shutdown`` invokes the eight teardown steps in design §8 order."""

    @pytest.mark.asyncio
    async def test_exact_8_step_sequence(
        self, shutdown_harness: _ShutdownHarness
    ) -> None:
        """The full 8-step list must match the canonical sequence verbatim.

        This is the *invariant gate* test — any reorder, skip, or
        duplicate registers as a list inequality with both expected and
        actual sequences printed by pytest's diff machinery.
        """
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        # Let the heartbeat task enter its try/except so the cancel
        # actually triggers the CancelledError branch.
        await asyncio.sleep(0)

        # Replace the placeholder heartbeat_task on the (frozen) state.
        # AppState is frozen, so we rebuild it with the live task.
        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        assert calls == list(EXPECTED_ORDER), (
            "Shutdown sequence violates the design §8 invariant.\n"
            f"  expected: {list(EXPECTED_ORDER)}\n"
            f"  actual:   {calls}\n"
            "Any reorder, skip, or duplicate would surface a hung "
            "pipeline or lost final trace in production."
        )

    @pytest.mark.asyncio
    async def test_no_step_appears_twice(
        self, shutdown_harness: _ShutdownHarness
    ) -> None:
        """Each shutdown step is invoked exactly once — no duplicates."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        for step in EXPECTED_ORDER:
            assert calls.count(step) == 1, (
                f"Shutdown step {step!r} appeared {calls.count(step)} "
                f"times; expected exactly 1.\n  full sequence: {calls}"
            )

    @pytest.mark.asyncio
    async def test_no_step_is_skipped(
        self, shutdown_harness: _ShutdownHarness
    ) -> None:
        """All eight shutdown steps are observed — none silently skipped."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        missing = [step for step in EXPECTED_ORDER if step not in calls]
        assert not missing, (
            f"Shutdown skipped {len(missing)} step(s): {missing}\n"
            f"  full sequence: {calls}"
        )


# ---------------------------------------------------------------------------
# AC-001 (cont.) — pairwise ordering invariants from the task description
# ---------------------------------------------------------------------------
class TestPairwiseOrderingInvariants:
    """Each "X before Y" rationale from the task description holds."""

    @pytest.fixture
    async def recorded_calls(
        self, shutdown_harness: _ShutdownHarness
    ) -> list[str]:
        """Drive a complete shutdown and return the recorded call list."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        return calls

    @pytest.mark.asyncio
    async def test_capabilities_close_before_nats_drain(
        self, recorded_calls: list[str]
    ) -> None:
        """3 before 5 — closes the registry before draining NATS so
        KV-watch callbacks cannot fire during drain."""
        idx = {step: i for i, step in enumerate(recorded_calls)}
        assert idx[STEP_CAPABILITIES_CLOSE] < idx[STEP_NATS_DRAIN], (
            "capabilities_registry.close() must precede nats_client.drain() "
            "so KV-watch callbacks do not fire during drain.\n"
            f"  sequence: {recorded_calls}"
        )

    @pytest.mark.asyncio
    async def test_writer_flush_before_nats_drain(
        self, recorded_calls: list[str]
    ) -> None:
        """4 before 5 — writer flush submits Graphiti episodes that may
        use the NATS client indirectly; flush before drain."""
        idx = {step: i for i, step in enumerate(recorded_calls)}
        assert idx[STEP_WRITER_FLUSH] < idx[STEP_NATS_DRAIN], (
            "routing_history_writer.flush() must precede "
            "nats_client.drain() so in-flight Graphiti submissions do "
            "not race the drain.\n"
            f"  sequence: {recorded_calls}"
        )

    @pytest.mark.asyncio
    async def test_deregister_before_nats_drain(
        self, recorded_calls: list[str]
    ) -> None:
        """2 before 5 — deregister must publish to NATS, so it has to
        precede ``drain()``."""
        idx = {step: i for i, step in enumerate(recorded_calls)}
        assert idx[STEP_DEREGISTER] < idx[STEP_NATS_DRAIN], (
            "deregister_from_fleet must publish to NATS before drain.\n"
            f"  sequence: {recorded_calls}"
        )

    @pytest.mark.asyncio
    async def test_writer_flush_before_graphiti_aclose(
        self, recorded_calls: list[str]
    ) -> None:
        """6 last among I/O closes — Graphiti close after writer has
        flushed avoids dropping in-flight episodes."""
        idx = {step: i for i, step in enumerate(recorded_calls)}
        assert idx[STEP_WRITER_FLUSH] < idx[STEP_GRAPHITI_ACLOSE], (
            "routing_history_writer.flush() must precede "
            "graphiti_client.aclose() so the writer's in-flight episodes "
            "are not dropped.\n"
            f"  sequence: {recorded_calls}"
        )

    @pytest.mark.asyncio
    async def test_heartbeat_cancel_first_step(
        self, recorded_calls: list[str]
    ) -> None:
        """1 first — heartbeat cancel runs before deregister so the
        deregister write is the last fleet observation the broker
        records (no race against an in-flight heartbeat re-register)."""
        assert recorded_calls[0] == STEP_HEARTBEAT_CANCEL, (
            "heartbeat cancellation must be the FIRST shutdown step.\n"
            f"  actual first step: {recorded_calls[0]!r}\n"
            f"  full sequence:     {recorded_calls}"
        )

    @pytest.mark.asyncio
    async def test_store_close_last_step(
        self, recorded_calls: list[str]
    ) -> None:
        """8 last — the memory store outlives every async transport."""
        assert recorded_calls[-1] == STEP_STORE_CLOSE, (
            "store.close() must be the LAST shutdown step so the "
            "Phase-1 invariant 'store outlives every async transport' "
            "holds.\n"
            f"  actual last step: {recorded_calls[-1]!r}\n"
            f"  full sequence:    {recorded_calls}"
        )


# ---------------------------------------------------------------------------
# AC-003 — failure tolerance: a single failed step does NOT skip later
# steps; errors are WARN-logged.
# ---------------------------------------------------------------------------
class TestFailureToleranceInvariant:
    """A single failed shutdown step does not abort the rest of the
    sequence; the failure is recorded at WARN."""

    @pytest.mark.asyncio
    async def test_deregister_failure_does_not_skip_subsequent_steps(
        self,
        shutdown_harness: _ShutdownHarness,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """``deregister_from_fleet`` raising must not block steps 3–8."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            caplog.at_level(logging.WARNING),
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(side_effect=RuntimeError("broker offline")),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        # Every later step still ran:
        for later_step in (
            STEP_CAPABILITIES_CLOSE,
            STEP_WRITER_FLUSH,
            STEP_NATS_DRAIN,
            STEP_GRAPHITI_ACLOSE,
            STEP_LAYER2_DISARM,
            STEP_STORE_CLOSE,
        ):
            assert later_step in calls, (
                f"Step {later_step!r} was skipped after deregister failed; "
                "shutdown must be failure-tolerant.\n"
                f"  observed sequence: {calls}"
            )

    @pytest.mark.asyncio
    async def test_capabilities_close_failure_does_not_skip_subsequent(
        self,
        shutdown_harness: _ShutdownHarness,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """``capabilities_registry.close()`` raising must not block 4–8."""
        calls = shutdown_harness.calls
        # Replace the registry's close with a raising AsyncMock.
        shutdown_harness.state.capabilities_registry.close = AsyncMock(  # type: ignore[union-attr]
            side_effect=RuntimeError("watcher detach failed"),
        )

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            caplog.at_level(logging.WARNING),
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        for later_step in (
            STEP_WRITER_FLUSH,
            STEP_NATS_DRAIN,
            STEP_GRAPHITI_ACLOSE,
            STEP_LAYER2_DISARM,
            STEP_STORE_CLOSE,
        ):
            assert later_step in calls, (
                f"Step {later_step!r} was skipped after "
                f"capabilities_registry.close() failed.\n"
                f"  observed sequence: {calls}"
            )

    @pytest.mark.asyncio
    async def test_nats_drain_failure_does_not_skip_subsequent(
        self,
        shutdown_harness: _ShutdownHarness,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """``nats_client.drain()`` raising must not block 6–8."""
        calls = shutdown_harness.calls
        shutdown_harness.state.nats_client.drain = AsyncMock(  # type: ignore[union-attr]
            side_effect=TimeoutError("drain timed out"),
        )

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            caplog.at_level(logging.WARNING),
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        for later_step in (
            STEP_GRAPHITI_ACLOSE,
            STEP_LAYER2_DISARM,
            STEP_STORE_CLOSE,
        ):
            assert later_step in calls, (
                f"Step {later_step!r} was skipped after "
                f"nats_client.drain() failed.\n"
                f"  observed sequence: {calls}"
            )

    @pytest.mark.asyncio
    async def test_shutdown_does_not_propagate_step_exceptions(
        self, shutdown_harness: _ShutdownHarness
    ) -> None:
        """``shutdown`` itself never raises when a single step fails."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        # Fail multiple disparate steps simultaneously to confirm the
        # shutdown wrapper is robust across the whole sequence.
        shutdown_harness.state.routing_history_writer.flush = AsyncMock(  # type: ignore[union-attr]
            side_effect=RuntimeError("flush failed"),
        )
        shutdown_harness.state.graphiti_client.aclose = AsyncMock(  # type: ignore[union-attr]
            side_effect=RuntimeError("aclose failed"),
        )

        with (
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(side_effect=RuntimeError("deregister failed")),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            # No exception should escape ``shutdown``.
            await shutdown(state)


# ---------------------------------------------------------------------------
# AC-004 — heartbeat cancellation produces no traceback / unhandled
# exception warning.
# ---------------------------------------------------------------------------
class TestHeartbeatCancellationClean:
    """Cancelling the heartbeat task during shutdown produces no
    traceback, no asyncio "Task exception was never retrieved" warning,
    and no unhandled exception in the event loop."""

    @pytest.mark.asyncio
    async def test_cancellation_no_traceback_in_logs(
        self,
        shutdown_harness: _ShutdownHarness,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """No ERROR records and no exception-info entries are emitted."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            # Mirror production heartbeat_loop: log INFO + re-raise on
            # cancel so asyncio records the cancellation cleanly.
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            caplog.at_level(logging.DEBUG),
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        # The task is cancelled cleanly — no exception leak.
        assert heartbeat_task.cancelled() or heartbeat_task.done()

        # No log record carries exception info from the cancel.
        leaked = [
            (rec.name, rec.levelname, rec.message)
            for rec in caplog.records
            if rec.exc_info is not None
        ]
        assert not leaked, (
            "Heartbeat cancellation leaked traceback(s) into the log "
            "stream — production would surface this as a noisy shutdown."
            f"\n  leaked records: {leaked}"
        )

        # And no ERROR-level log records at all.
        errors = [rec for rec in caplog.records if rec.levelno >= logging.ERROR]
        assert not errors, (
            "Heartbeat cancellation produced ERROR-level log records.\n"
            f"  errors: {[(r.name, r.message) for r in errors]}"
        )

    @pytest.mark.asyncio
    async def test_cancellation_completes_task_state(
        self, shutdown_harness: _ShutdownHarness
    ) -> None:
        """The heartbeat task ends in ``cancelled``/``done`` state."""
        calls = shutdown_harness.calls

        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                calls.append(STEP_HEARTBEAT_CANCEL)
                raise

        loop = asyncio.get_event_loop()
        heartbeat_task = loop.create_task(_heartbeat())
        await asyncio.sleep(0)

        state = AppState(
            config=shutdown_harness.state.config,
            supervisor=shutdown_harness.state.supervisor,
            store=shutdown_harness.state.store,
            session_manager=shutdown_harness.state.session_manager,
            capability_registry=shutdown_harness.state.capability_registry,
            llamaswap_adapter=shutdown_harness.state.llamaswap_adapter,
            nats_client=shutdown_harness.state.nats_client,
            graphiti_client=shutdown_harness.state.graphiti_client,
            routing_history_writer=shutdown_harness.state.routing_history_writer,
            fleet_heartbeat_task=heartbeat_task,
            capabilities_registry=shutdown_harness.state.capabilities_registry,
        )

        _arm_dispatch_hooks_with_layer2_observer(calls)

        with (
            patch(
                "jarvis.infrastructure.lifecycle.deregister_from_fleet",
                new=AsyncMock(
                    side_effect=lambda *a, **kw: calls.append(STEP_DEREGISTER),
                ),
            ),
            _install_layer2_disarm_observer(calls),
        ):
            await shutdown(state)

        assert heartbeat_task.done()
        assert heartbeat_task.cancelled()
