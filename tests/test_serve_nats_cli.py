"""Tests for ``jarvis serve-nats`` CLI command + ``_serve_adapter`` lifecycle.

TASK-J006-004 acceptance criteria coverage:

* AC-001: ``jarvis serve-nats --nats nats://localhost:4222`` starts and
  subscribes to ``agents.command.jarvis``.
* AC-002: Bootstrap reuses ``_create_app_state`` exactly — no duplicate
  ``register_on_fleet``, no duplicate ``heartbeat_loop`` (Risk #5).
* AC-003: Broker-unreachable case (``state.nats_client is None``) exits
  non-zero with a clear error message — no soft-fail.
* AC-004: SIGINT and SIGTERM both trigger graceful shutdown via the
  shared :class:`asyncio.Event`.
* AC-005: Shutdown order — unsubscribe → drain → cancel heartbeat →
  deregister → disconnect.
* AC-006: Existing CLI tests (chat/health/version) keep passing — the
  pre-existing test suite covers that; this module focuses on the new
  command surface.
* AC-007: ``--log-level`` option mutates ``JARVIS_LOG_LEVEL`` env var.

The unit tests stub :func:`_create_app_state` so they exercise the click
plumbing and the ``_serve_adapter`` shutdown ordering without spinning
up a real NATS broker. The integration test uses the conftest
``nats_test_server`` fixture so the end-to-end publish/result loop
travels real bytes through an in-process broker.
"""

from __future__ import annotations

import asyncio
import functools
import signal
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner
from nats_core.envelope import EventType, MessageEnvelope
from nats_core.events._agent import CommandPayload, ResultPayload

from jarvis.cli.main import _run_serve_nats, _serve_adapter, main, serve_nats
from jarvis.sessions.session import Session
from jarvis.shared.constants import Adapter

# ---------------------------------------------------------------------------
# Stub the dotenv bridge so test runs cannot accidentally pick up the
# operator's real ``.env`` while invoking the CLI. Mirrors the autouse
# fixture in ``tests/test_cli.py`` so the serve-nats tests have the same
# isolation profile.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_load_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("jarvis.cli.main.load_dotenv", lambda **kw: None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(*, nats_client: Any | None) -> MagicMock:
    """Return a mock :class:`AppState` wired for ``_serve_adapter`` tests.

    The ``nats_client`` argument is intentionally explicit so each test
    can control the broker-availability branch.
    """
    state = MagicMock()
    state.config = MagicMock()
    state.config.nats_url = "nats://localhost:4222"

    state.session_manager = MagicMock()

    # The session manager's ``start_session`` must return a usable
    # Session — the ``_serve_adapter`` body reads ``session_id`` for
    # logging and threads it into ``handle_chat_command``.
    state.session_manager.start_session.return_value = Session(
        session_id="nats-shared-test",
        adapter=Adapter.NATS,
        user_id="nats-shared",
        thread_id="nats-shared-test",
        started_at=datetime.now(UTC),
        correlation_id="serve-nats-corr",
        metadata={},
    )

    state.nats_client = nats_client
    state.fleet_heartbeat_task = None
    return state


def _make_nats_client_mock() -> MagicMock:
    """Build a NATSClient double exposing the surface ``_serve_adapter`` uses."""
    nats_client = MagicMock()
    nats_client.client = MagicMock()
    nats_client.client.publish = AsyncMock(return_value=None)
    nats_client.in_flight = 0
    nats_client.subscribe_with_reply = AsyncMock()
    nats_client.drain = AsyncMock(return_value=None)
    return nats_client


# ---------------------------------------------------------------------------
# AC-007: ``serve-nats`` is a registered click command with the right options
# ---------------------------------------------------------------------------
class TestServeNatsCommandRegistered:
    """Smoke tests that the click command surface matches the AC."""

    def test_serve_nats_command_appears_in_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "serve-nats" in result.output

    def test_serve_nats_help_lists_required_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve-nats", "--help"])
        assert result.exit_code == 0
        assert "--nats" in result.output
        assert "--agent-id" in result.output
        assert "--log-level" in result.output

    def test_log_level_option_exports_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-007: ``--log-level DEBUG`` sets ``JARVIS_LOG_LEVEL`` before bootstrap."""
        monkeypatch.delenv("JARVIS_LOG_LEVEL", raising=False)
        observed: dict[str, Any] = {}

        async def fake_run(*, agent_id: str) -> None:
            observed["log_level"] = __import__("os").environ.get("JARVIS_LOG_LEVEL")
            observed["agent_id"] = agent_id

        runner = CliRunner()
        with patch("jarvis.cli.main._run_serve_nats", new=fake_run):
            result = runner.invoke(main, ["serve-nats", "--log-level", "DEBUG"])

        assert result.exit_code == 0
        assert observed["log_level"] == "DEBUG"

    def test_nats_option_exports_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("JARVIS_NATS_URL", raising=False)
        observed: dict[str, Any] = {}

        async def fake_run(*, agent_id: str) -> None:
            observed["nats_url"] = __import__("os").environ.get("JARVIS_NATS_URL")

        runner = CliRunner()
        with patch("jarvis.cli.main._run_serve_nats", new=fake_run):
            result = runner.invoke(main, ["serve-nats", "--nats", "nats://example:4222"])

        assert result.exit_code == 0
        assert observed["nats_url"] == "nats://example:4222"

    def test_agent_id_option_threads_to_runner(self) -> None:
        observed: dict[str, Any] = {}

        async def fake_run(*, agent_id: str) -> None:
            observed["agent_id"] = agent_id

        runner = CliRunner()
        with patch("jarvis.cli.main._run_serve_nats", new=fake_run):
            result = runner.invoke(main, ["serve-nats", "--agent-id", "jarvis-alt"])

        assert result.exit_code == 0
        assert observed["agent_id"] == "jarvis-alt"


# ---------------------------------------------------------------------------
# AC-003: broker-unreachable case — exit non-zero with clear error
# ---------------------------------------------------------------------------
class TestBrokerUnreachableFailsFast:
    """AC-003: refuse to start when ``state.nats_client is None``."""

    def test_serve_nats_with_no_nats_client_exits_one(self) -> None:
        state = _make_state(nats_client=None)
        runner = CliRunner()
        with patch(
            "jarvis.cli.main._create_app_state",
            new=AsyncMock(return_value=state),
        ):
            result = runner.invoke(main, ["serve-nats"])
        assert result.exit_code == 1

    def test_serve_nats_no_broker_emits_clear_error(self) -> None:
        state = _make_state(nats_client=None)
        runner = CliRunner()
        with patch(
            "jarvis.cli.main._create_app_state",
            new=AsyncMock(return_value=state),
        ):
            result = runner.invoke(main, ["serve-nats"])
        # The error must name the NATS URL so the operator can diagnose
        # without rerunning under DEBUG.
        assert "nats://localhost:4222" in result.output
        assert "unreachable" in result.output.lower()

    def test_no_subscribe_attempted_when_nats_client_none(self) -> None:
        state = _make_state(nats_client=None)
        runner = CliRunner()
        with patch(
            "jarvis.cli.main._create_app_state",
            new=AsyncMock(return_value=state),
        ):
            runner.invoke(main, ["serve-nats"])
        # Session was NEVER created either — fail BEFORE any side-effects.
        state.session_manager.start_session.assert_not_called()


# ---------------------------------------------------------------------------
# AC-001 + AC-002 (Risk #5): bootstrap calls ``_create_app_state`` exactly
# once, ``_serve_adapter`` does NOT call ``register_on_fleet``.
# ---------------------------------------------------------------------------
class TestNoDoubleRegistration:
    """Risk #5 — ``_serve_adapter`` must NOT re-register on the fleet."""

    @pytest.mark.asyncio
    async def test_serve_adapter_does_not_call_register_on_fleet(self) -> None:
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        # ``register_on_fleet`` is owned by the lifecycle wiring (the
        # caller of ``_serve_adapter``), NOT by ``_serve_adapter`` itself
        # — patching the canonical import surface and asserting zero
        # calls is the Risk #5 invariant.
        with patch(
            "jarvis.infrastructure.fleet_registration.register_on_fleet",
            new=AsyncMock(return_value=None),
        ) as mock_register_canonical:
            task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
            await asyncio.sleep(0.01)
            signal.raise_signal(signal.SIGINT)
            await asyncio.wait_for(task, timeout=2.0)

        mock_register_canonical.assert_not_called()

    @pytest.mark.asyncio
    async def test_serve_adapter_subscribes_to_canonical_command_subject(self) -> None:
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
        await asyncio.sleep(0.01)
        signal.raise_signal(signal.SIGINT)
        await asyncio.wait_for(task, timeout=2.0)

        nats_client.subscribe_with_reply.assert_awaited_once()
        call_args = nats_client.subscribe_with_reply.await_args
        subject = call_args.args[0]
        assert subject == "agents.command.jarvis"

    @pytest.mark.asyncio
    async def test_serve_adapter_binds_handler_via_functools_partial(self) -> None:
        """Implementation note: bound via ``functools.partial`` for testability."""
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
        await asyncio.sleep(0.01)
        signal.raise_signal(signal.SIGINT)
        await asyncio.wait_for(task, timeout=2.0)

        handler = nats_client.subscribe_with_reply.await_args.args[1]
        # ``functools.partial`` exposes the bound kwargs verbatim — the
        # readiness contract of the AC ("handler closure must capture
        # the bound session and AppState").
        assert isinstance(handler, functools.partial)
        assert "session_manager" in handler.keywords
        assert "session" in handler.keywords
        assert "nats_client" in handler.keywords
        assert "agent_id" in handler.keywords
        assert handler.keywords["agent_id"] == "jarvis"

    @pytest.mark.asyncio
    async def test_serve_adapter_uses_shared_nats_adapter_session(self) -> None:
        """``start_session`` is called with ``Adapter.NATS``, ``"nats-shared"``."""
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
        await asyncio.sleep(0.01)
        signal.raise_signal(signal.SIGINT)
        await asyncio.wait_for(task, timeout=2.0)

        state.session_manager.start_session.assert_called_once_with(
            Adapter.NATS, "nats-shared"
        )


# ---------------------------------------------------------------------------
# AC-004 + AC-005: signal handling + shutdown ordering
# ---------------------------------------------------------------------------
class TestShutdownOrdering:
    """AC-005: unsubscribe → drain → cancel heartbeat → deregister → disconnect."""

    @pytest.mark.asyncio
    async def test_sigint_drives_graceful_shutdown(self) -> None:
        """AC-004: SIGINT triggers the shutdown event."""
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        subscription = AsyncMock()
        nats_client.subscribe_with_reply = AsyncMock(return_value=subscription)

        task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
        await asyncio.sleep(0.01)
        signal.raise_signal(signal.SIGINT)
        await asyncio.wait_for(task, timeout=2.0)

        subscription.unsubscribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sigterm_drives_graceful_shutdown(self) -> None:
        """AC-004: SIGTERM also triggers the shutdown event."""
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        subscription = AsyncMock()
        nats_client.subscribe_with_reply = AsyncMock(return_value=subscription)

        task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
        await asyncio.sleep(0.01)
        signal.raise_signal(signal.SIGTERM)
        await asyncio.wait_for(task, timeout=2.0)

        subscription.unsubscribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_order_unsubscribe_then_deregister_then_drain(self) -> None:
        """AC-005: assert call ordering on a single MagicMock.

        ``MagicMock.mock_calls`` records every call on the mock AND its
        children, in temporal order. We attach the heartbeat task's
        cancel + the subscription's unsubscribe + the nats_client's
        drain + the deregister helper to a single parent mock so the
        ordering assertion is a single equality check.
        """
        calls: list[str] = []

        nats_client = _make_nats_client_mock()
        subscription = MagicMock()

        async def _record_unsubscribe() -> None:
            calls.append("unsubscribe")

        subscription.unsubscribe = AsyncMock(side_effect=_record_unsubscribe)
        nats_client.subscribe_with_reply = AsyncMock(return_value=subscription)

        async def _record_drain(*_a: Any, **_kw: Any) -> None:
            calls.append("drain")

        nats_client.drain = AsyncMock(side_effect=_record_drain)

        # Heartbeat task wired as a real asyncio.Task we can observe.
        async def _heartbeat() -> None:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                calls.append("cancel_heartbeat")
                raise

        heartbeat_task = asyncio.create_task(_heartbeat())
        state = _make_state(nats_client=nats_client)
        state.fleet_heartbeat_task = heartbeat_task

        async def _record_deregister(*_a: Any, **_kw: Any) -> None:
            calls.append("deregister")

        with patch(
            "jarvis.cli.main.deregister_from_fleet",
            new=AsyncMock(side_effect=_record_deregister),
        ):
            task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
            await asyncio.sleep(0.01)
            signal.raise_signal(signal.SIGINT)
            await asyncio.wait_for(task, timeout=2.0)

        # Order per AC-005: unsubscribe → drain (in-flight) → cancel
        # heartbeat → deregister → disconnect (drain). The "drain
        # in-flight" leg is a no-op when ``in_flight == 0`` (no recorded
        # event), so the observable ordering reduces to:
        assert calls == ["unsubscribe", "cancel_heartbeat", "deregister", "drain"]

    @pytest.mark.asyncio
    async def test_drain_in_flight_waits_for_handlers(self) -> None:
        """Phase-1 drain polls ``in_flight`` until it reaches zero."""
        # The base helper is invoked for parity with the other tests; the
        # variant below uses a hand-rolled ``_Client`` so we can flip
        # ``in_flight`` from inside a sleep-side-effect.
        _ = _make_nats_client_mock()
        # Simulate one in-flight handler that completes after the first
        # poll cycle.
        in_flight_values = iter([1, 1, 0, 0])

        # Use ``type(...)`` so the attribute can be a descriptor; mock
        # property assignment via ``side_effect`` is simpler.
        class _Client:
            in_flight = 1
            client = MagicMock()
            subscribe_with_reply = AsyncMock()
            drain = AsyncMock()

        client = _Client()
        client.client.publish = AsyncMock()
        subscription = AsyncMock()
        client.subscribe_with_reply = AsyncMock(return_value=subscription)

        # Tick the in_flight counter down each time ``asyncio.sleep`` is
        # awaited inside the drain loop. We use a side-effect on a real
        # ``asyncio.sleep`` wrapper to keep the loop honest.
        original_sleep = asyncio.sleep

        async def _ticking_sleep(secs: float) -> None:
            try:
                client.in_flight = next(in_flight_values)
            except StopIteration:
                client.in_flight = 0
            await original_sleep(0)

        state = _make_state(nats_client=client)

        with patch("jarvis.cli.main.asyncio.sleep", new=_ticking_sleep):
            task = asyncio.create_task(_serve_adapter(state, drain_timeout=2.0))
            # Allow subscribe to land before signalling shutdown.
            await original_sleep(0.01)
            signal.raise_signal(signal.SIGINT)
            await asyncio.wait_for(task, timeout=5.0)

        # Drain loop ran at least once before the in_flight counter hit
        # zero — the underlying drain() must still have been called.
        client.drain.assert_awaited()

    @pytest.mark.asyncio
    async def test_drain_timeout_warns_but_continues(self) -> None:
        """Drain budget exceeded → log a warning, then proceed to deregister.

        The shutdown sequence must not stall if a handler hangs — drain
        is bounded and the remaining steps still run.
        """
        nats_client = _make_nats_client_mock()
        # in_flight pinned > 0 — drain phase 1 will time out.
        nats_client.in_flight = 5
        subscription = AsyncMock()
        nats_client.subscribe_with_reply = AsyncMock(return_value=subscription)

        state = _make_state(nats_client=nats_client)

        with patch("jarvis.cli.main.deregister_from_fleet", new=AsyncMock()) as dereg:
            task = asyncio.create_task(_serve_adapter(state, drain_timeout=0.05))
            await asyncio.sleep(0.01)
            signal.raise_signal(signal.SIGINT)
            await asyncio.wait_for(task, timeout=2.0)

        # Even though drain timed out, deregister + drain were still
        # called so the fleet view stays consistent.
        dereg.assert_awaited_once()
        nats_client.drain.assert_awaited_once()


# ---------------------------------------------------------------------------
# AC-002: _run_serve_nats reuses _create_app_state — no second supervisor.
# ---------------------------------------------------------------------------
class TestRunServeNatsCallsCreateAppStateExactlyOnce:
    @pytest.mark.asyncio
    async def test_create_app_state_called_exactly_once(self) -> None:
        nats_client = _make_nats_client_mock()
        state = _make_state(nats_client=nats_client)

        with (
            patch(
                "jarvis.cli.main._create_app_state",
                new=AsyncMock(return_value=state),
            ) as mock_create,
            # Use a small drain so the shutdown leg is quick.
            patch("jarvis.cli.main._serve_adapter", new=AsyncMock()) as serve,
        ):
            await _run_serve_nats(agent_id="jarvis")

        mock_create.assert_awaited_once()
        serve.assert_awaited_once()


# ---------------------------------------------------------------------------
# Integration test: end-to-end with an in-process NATS broker.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_integration_serve_nats_end_to_end_with_fake_broker(
    nats_test_server: Any,
) -> None:
    """End-to-end: publish ``CommandPayload`` → assert ``ResultPayload``.

    Wires ``_serve_adapter`` against the in-process NATS broker spun up
    by the ``nats_test_server`` fixture. The session manager's
    ``invoke`` is mocked so the supervisor is not exercised — the test
    asserts the wiring of subscribe_with_reply + dual-publish, not the
    LLM.

    Verifies:
      * AC-001: the subscription on ``agents.command.jarvis`` actually
        accepts a published command.
      * Risk #5 (no double registration): ``_serve_adapter`` does NOT
        call ``register_on_fleet``. The integration test asserts the
        broker has no second register hop by inspecting the call count
        of a patched helper.
      * Bug #1 dual-publish: a ``ResultPayload`` arrives BOTH on the
        reply inbox (``NATSClient.request`` future resolves) AND on
        ``agents.result.jarvis`` (event-stream consumers see it).
    """
    nats_client = nats_test_server

    # Build a minimal state shim — only the session_manager surface is
    # exercised by the handler. The supervisor mock returns a canned
    # reply so we can assert it round-trips.
    state = MagicMock()
    state.config = MagicMock()
    state.config.nats_url = "nats://in-process"
    state.nats_client = nats_client
    state.fleet_heartbeat_task = None
    state.session_manager = MagicMock()
    state.session_manager.start_session.return_value = Session(
        session_id="nats-shared-e2e",
        adapter=Adapter.NATS,
        user_id="nats-shared",
        thread_id="nats-shared-e2e",
        started_at=datetime.now(UTC),
        correlation_id="e2e-corr",
        metadata={},
    )
    state.session_manager.invoke = AsyncMock(return_value="hello from supervisor")
    state.session_manager.pending_notifications = MagicMock(return_value=[])

    # Spy on ``register_on_fleet`` to verify Risk #5 — must be called
    # exactly zero times from inside ``_serve_adapter`` itself.
    with patch(
        "jarvis.infrastructure.fleet_registration.register_on_fleet",
        new=AsyncMock(return_value=None),
    ) as mock_register:
        adapter_task = asyncio.create_task(
            _serve_adapter(state, drain_timeout=0.5)
        )
        try:
            # Give the subscription a beat to register on the broker.
            await asyncio.sleep(0.1)

            # Subscribe to the canonical result subject so we can prove
            # the second leg of the dual-publish fires.
            result_envelopes: list[bytes] = []
            result_sub_event = asyncio.Event()

            async def _on_result(msg: Any) -> None:
                result_envelopes.append(msg.data)
                result_sub_event.set()

            result_sub = await nats_client.client.subscribe(
                "agents.result.jarvis", cb=_on_result
            )
            await asyncio.sleep(0.05)

            # Issue the command via request/reply so we exercise the
            # raw reply-inbox leg of the dual-publish too.
            command = CommandPayload(
                command="chat",
                args={"message": "hi jarvis"},
                correlation_id="e2e-001",
            )
            reply_msg = await nats_client.request(
                "agents.command.jarvis",
                command.model_dump_json().encode(),
                timeout=5.0,
            )

            # Reply leg: raw ResultPayload JSON.
            reply_payload = ResultPayload.model_validate_json(reply_msg.data)
            assert reply_payload.success is True
            assert reply_payload.correlation_id == "e2e-001"
            assert "hello from supervisor" in reply_payload.result["response"]

            # Canonical leg: wait briefly for the envelope publish.
            try:
                await asyncio.wait_for(result_sub_event.wait(), timeout=2.0)
            except TimeoutError:  # pragma: no cover — diagnostic-only branch
                pytest.fail("agents.result.jarvis envelope never arrived")

            envelope = MessageEnvelope.model_validate_json(result_envelopes[0])
            assert envelope.event_type == EventType.RESULT
            assert envelope.source_id == "jarvis"
            assert envelope.correlation_id == "e2e-001"

            await result_sub.unsubscribe()
        finally:
            # Graceful shutdown — same path the SIGINT handler drives.
            signal.raise_signal(signal.SIGINT)
            await asyncio.wait_for(adapter_task, timeout=5.0)

    # AC-002 / Risk #5: ``_serve_adapter`` MUST NOT call
    # ``register_on_fleet`` on its own — the lifecycle owns registration.
    mock_register.assert_not_called()

    # The supervisor was actually called via the session manager — the
    # subscription wiring is real.
    state.session_manager.invoke.assert_awaited_once()
    assert state.session_manager.invoke.await_args.args[1] == "hi jarvis"


# ---------------------------------------------------------------------------
# Smoke: importing the click command doesn't blow up.
# ---------------------------------------------------------------------------
def test_serve_nats_callable_is_click_command() -> None:
    import click as _click

    assert isinstance(serve_nats, _click.Command)
