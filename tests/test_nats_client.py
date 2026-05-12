"""Tests for ``jarvis.infrastructure.nats_client.NATSClient`` (TASK-J004-006).

Covers the seven acceptance criteria recorded in
``tasks/design_approved/TASK-J004-006-nats-client-async-wrapper.md``:

  AC-001: ``NATSClient.connect(config)`` returns ``NATSClient | None`` —
          never raises on connect failure.
  AC-002: Connect failure → ERROR log with ``nats_url`` and underlying
          exception, returns ``None``.
  AC-003: Connect success → INFO log; the returned wrapper exposes ``client``
          and ``js`` properties.
  AC-004: ``request(subject, payload, *, timeout)`` issues a NATS
          request/reply and raises ``asyncio.TimeoutError`` on timeout,
          ``NATSConnectionError`` on transport failure.
  AC-005: ``drain(timeout=5.0)`` is **idempotent** — second call after
          drain is a no-op (no second log line, no exception).
  AC-006: Reconnect events emit structured logs (``nats_reconnect``,
          ``nats_disconnect``) per ADR-ARCH-020.
  AC-007: Tests cover the full surface using ``unittest.mock`` in
          place of an in-process NATS server (Phase 3 floor).

The mock surface mirrors the real ``nats.aio.client.Client`` enough that
the wrapper code under test never branches on whether the client is
real — it just sees a typed shape with ``request`` / ``drain`` /
``jetstream`` attributes.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest
import structlog

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import nats_client as nats_client_module
from jarvis.infrastructure.nats_client import NATSClient
from jarvis.shared.exceptions import NATSConnectionError

if TYPE_CHECKING:
    pass


@pytest.fixture(autouse=True)
def _capture_structlog() -> Any:
    """Route structlog events through pytest's stdout capture.

    The wrapper logs via ``structlog.get_logger(__name__)``; without a
    test-time configuration step the events go to a console renderer
    that bypasses pytest's ``caplog``. Configuring structlog with
    ``KeyValueRenderer`` keeps the events on stdout (where ``capsys``
    can read them) and gives a stable ``key=value`` shape we can grep.
    """
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.KeyValueRenderer(
                key_order=["event", "level"],
                sort_keys=False,
            ),
        ],
        wrapper_class=structlog.BoundLogger,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
    yield
    structlog.reset_defaults()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**overrides: Any) -> JarvisConfig:
    """Construct a JarvisConfig that bypasses environment lookup."""
    base: dict[str, Any] = {
        "nats_url": "nats://localhost:4222",
        "nats_credentials_path": None,
    }
    base.update(overrides)
    # ``_env_file=None`` blocks the .env loader so tests stay hermetic.
    return JarvisConfig(_env_file=None, **base)  # type: ignore[arg-type]


class _FakeJetStream:
    """Stand-in for ``nats.js.JetStreamContext``."""


class _FakeSubscription:
    """Stand-in for ``nats.aio.subscription.Subscription``.

    The wrapper only forwards this object to the caller — it does not
    consume any attributes of it. A bare sentinel is sufficient.
    """


class _FakeMsg:
    """Stand-in for ``nats.aio.msg.Msg``.

    Only the two attributes the wrapper reads (``data`` and ``reply``)
    are populated. Other attribute access raises ``AttributeError`` so
    the tests notice if the wrapper grows an unexpected dependency on
    the Msg surface (e.g. headers, sid, metadata).
    """

    __slots__ = ("data", "reply")

    def __init__(self, data: bytes, reply: str = "") -> None:
        self.data = data
        self.reply = reply


class _FakeClient:
    """Mimics the public surface of ``nats.aio.client.Client`` enough to
    drive the wrapper code under test without touching the network.

    Only the methods the wrapper actually invokes are implemented; any
    extra access raises AttributeError so the tests notice if the
    wrapper grows an unexpected dependency."""

    def __init__(self) -> None:
        self.drain = mock.AsyncMock(name="drain")
        self.close = mock.AsyncMock(name="close")
        self.request = mock.AsyncMock(name="request")
        self.subscribe = mock.AsyncMock(name="subscribe", return_value=_FakeSubscription())
        self._jetstream = _FakeJetStream()
        self.is_connected = True

    def jetstream(self) -> _FakeJetStream:
        return self._jetstream


@pytest.fixture
def fake_client() -> _FakeClient:
    return _FakeClient()


@pytest.fixture
def patched_connect(fake_client: _FakeClient) -> Any:
    """Patch ``nats.connect`` (re-exported via the module) so the
    wrapper observes a ready ``Client``-shaped object."""
    with mock.patch.object(
        nats_client_module,
        "_nats_connect",
        new=mock.AsyncMock(return_value=fake_client),
    ) as patched:
        yield patched


# ===========================================================================
# AC-001 / AC-003 — successful connect
# ===========================================================================


class TestAC001ConnectSuccess:
    """AC-001 / AC-003: successful connect returns a wrapper exposing
    ``client`` and ``js`` properties; logs an INFO event."""

    async def test_connect_returns_wrapper_with_client_and_js_properties(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        config = _make_config()

        wrapper = await NATSClient.connect(config)

        assert wrapper is not None
        assert isinstance(wrapper, NATSClient)
        # ``client`` exposes the underlying nats-py Client.
        assert wrapper.client is fake_client
        # ``js`` exposes the JetStream context for FEAT-JARVIS-005.
        assert wrapper.js is fake_client.jetstream()

    async def test_connect_passes_nats_url_to_underlying_connect(
        self, patched_connect: mock.AsyncMock
    ) -> None:
        config = _make_config(nats_url="nats://broker.example:4222")

        await NATSClient.connect(config)

        # The wrapper must forward the configured URL — every other module
        # in the tree relies on this single connect site.
        kwargs = patched_connect.call_args.kwargs
        servers = kwargs.get("servers") or patched_connect.call_args.args[0]
        assert servers == "nats://broker.example:4222"

    async def test_connect_emits_info_log_on_success(
        self,
        patched_connect: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        config = _make_config()

        wrapper = await NATSClient.connect(config)

        assert wrapper is not None
        out = capsys.readouterr().out
        # structlog-bound INFO event with the canonical event name.
        assert "nats_connect_success" in out, (
            f"expected nats_connect_success INFO event in stdout; got: {out!r}"
        )


# ===========================================================================
# AC-001 / AC-002 — connect failure soft-fails to None
# ===========================================================================


class TestAC002ConnectFailureSoftFails:
    """DDR-021: on connect failure the wrapper logs ERROR and returns
    None — it never raises out of ``connect``."""

    async def test_connect_returns_none_when_underlying_connect_raises(self) -> None:
        from nats.errors import NoServersError

        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=NoServersError()),
        ):
            wrapper = await NATSClient.connect(_make_config())

        assert wrapper is None

    async def test_connect_logs_error_with_nats_url_and_exception_class(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from nats.errors import NoServersError

        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=NoServersError("no servers")),
        ):
            await NATSClient.connect(_make_config(nats_url="nats://down:4222"))

        out = capsys.readouterr().out
        # Operator-actionable — the log line MUST identify the URL we
        # tried plus the underlying exception class so the operator can
        # diagnose without re-running with DEBUG.
        assert "nats_connect_failed" in out
        assert "nats://down:4222" in out
        assert "NoServersError" in out

    async def test_connect_swallows_arbitrary_exceptions(self) -> None:
        # Any unexpected exception (e.g. OSError from a DNS failure)
        # must be soft-failed too, not just nats-py's typed errors.
        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=OSError("dns lookup failed")),
        ):
            wrapper = await NATSClient.connect(_make_config())

        assert wrapper is None


# ===========================================================================
# AC-004 — request raises asyncio.TimeoutError / NATSConnectionError
# ===========================================================================


class TestAC004RequestErrorMapping:
    """``request`` raises ``asyncio.TimeoutError`` on timeout and
    ``NATSConnectionError`` on transport failure (per design §8)."""

    async def test_request_returns_message_on_success(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        sentinel = mock.Mock(name="msg", data=b"reply")
        fake_client.request.return_value = sentinel

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        result = await wrapper.request("subject.x", b"payload", timeout=1.0)

        assert result is sentinel
        fake_client.request.assert_awaited_once()
        kwargs = fake_client.request.call_args.kwargs
        # Timeout is forwarded so reconnects and slow brokers are bounded.
        assert kwargs.get("timeout") == 1.0

    async def test_request_raises_asyncio_timeout_error_on_timeout(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        from nats.errors import TimeoutError as NatsTimeoutError

        fake_client.request.side_effect = NatsTimeoutError()

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        # ``nats.errors.TimeoutError`` is a subclass of the built-in
        # ``TimeoutError`` (which equals ``asyncio.TimeoutError`` from
        # Python 3.11), so a caller can ``except asyncio.TimeoutError``.
        with pytest.raises(asyncio.TimeoutError):
            await wrapper.request("subject.x", b"payload", timeout=0.1)

    async def test_request_raises_nats_connection_error_on_transport_failure(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        from nats.errors import ConnectionClosedError

        fake_client.request.side_effect = ConnectionClosedError()

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        with pytest.raises(NATSConnectionError):
            await wrapper.request("subject.x", b"payload", timeout=1.0)


# ===========================================================================
# AC-005 — drain is idempotent
# ===========================================================================


class TestAC005DrainIdempotent:
    """``drain(timeout=5.0)`` is idempotent — the second call is a no-op."""

    async def test_drain_calls_underlying_drain_once(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        await wrapper.drain()

        fake_client.drain.assert_awaited_once()

    async def test_drain_second_call_is_no_op(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        await wrapper.drain()
        await wrapper.drain()
        await wrapper.drain()

        # Single underlying drain — repeat calls are absorbed.
        fake_client.drain.assert_awaited_once()

    async def test_drain_second_call_does_not_log(
        self,
        patched_connect: mock.AsyncMock,
        fake_client: _FakeClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None
        # Drop the connect-success INFO line so the drain assertions
        # only see drain-related records.
        capsys.readouterr()

        # First drain → exactly one INFO line.
        await wrapper.drain()
        first_out = capsys.readouterr().out
        assert first_out.count("nats_drain_complete") == 1, (
            f"expected one nats_drain_complete record on first drain; got {first_out!r}"
        )

        # Second drain → no new log line.
        await wrapper.drain()
        second_out = capsys.readouterr().out
        assert "nats_drain_complete" not in second_out, (
            f"second drain emitted a record; expected silent no-op. got: {second_out!r}"
        )

    async def test_drain_respects_timeout(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        # If the underlying drain hangs forever, the wrapper must bound
        # the wait by the timeout argument.
        async def hang() -> None:
            await asyncio.sleep(60)

        fake_client.drain.side_effect = hang

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        with pytest.raises(asyncio.TimeoutError):
            await wrapper.drain(timeout=0.05)


# ===========================================================================
# AC-006 — reconnect-event structured logging
# ===========================================================================


class TestAC006ReconnectEventLogging:
    """Reconnect / disconnect callbacks emit structured logs per
    ADR-ARCH-020."""

    async def test_reconnect_callback_emits_structured_log(
        self,
        patched_connect: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        await NATSClient.connect(_make_config())
        capsys.readouterr()  # drop the connect-success line

        # Pull the kwargs the wrapper passed to ``nats.connect`` —
        # the reconnect callbacks must have been wired through.
        kwargs = patched_connect.call_args.kwargs
        reconnected_cb = kwargs["reconnected_cb"]

        await reconnected_cb()

        out = capsys.readouterr().out
        assert "nats_reconnect" in out, f"expected nats_reconnect record; got {out!r}"

    async def test_disconnect_callback_emits_structured_log(
        self,
        patched_connect: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        await NATSClient.connect(_make_config())
        capsys.readouterr()

        kwargs = patched_connect.call_args.kwargs
        disconnected_cb = kwargs["disconnected_cb"]

        await disconnected_cb()

        out = capsys.readouterr().out
        assert "nats_disconnect" in out, f"expected nats_disconnect record; got {out!r}"

    async def test_error_callback_emits_structured_log(
        self,
        patched_connect: mock.AsyncMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # A bound ``error_cb`` is required so transient async errors
        # surface as structured events instead of dropping silently.
        await NATSClient.connect(_make_config())
        capsys.readouterr()

        kwargs = patched_connect.call_args.kwargs
        error_cb = kwargs["error_cb"]

        await error_cb(RuntimeError("upstream blip"))

        out = capsys.readouterr().out
        assert "nats_error" in out, f"expected nats_error record; got {out!r}"


# ===========================================================================
# TASK-J006-002 — subscribe_with_reply + in-flight drain counter
# ===========================================================================


class TestSubscribeWithReply:
    """``subscribe_with_reply`` registers a flat subject and propagates the
    raw ``reply_to`` inbox alongside the decoded ``CommandPayload``
    (Bug #1). The in-flight counter wraps every handler invocation so
    ``drain`` can wait for graceful completion (Bug #1-adjacent — closing
    the connection mid-handler would silently drop the reply).
    """

    async def test_subscribe_with_reply_registers_subject_with_underlying_client(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        async def handler(payload: Any, reply_to: str) -> None:
            pass

        sub = await wrapper.subscribe_with_reply("agents.command.jarvis", handler)

        # Returns whatever the underlying subscribe returned (the
        # wrapper does not own subscription lifecycle).
        assert sub is fake_client.subscribe.return_value
        fake_client.subscribe.assert_awaited_once()
        args, kwargs = fake_client.subscribe.call_args
        subject = args[0] if args else kwargs.get("subject")
        assert subject == "agents.command.jarvis"

    async def test_subscribe_with_reply_rejects_wildcard_subject(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        # Bug #4: a wildcard subject would collect commands intended
        # for other agents and our handler would publish ResultPayload
        # envelopes back to mismatched correlation IDs.
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        async def handler(payload: Any, reply_to: str) -> None:
            pass

        with pytest.raises(ValueError, match="wildcard"):
            await wrapper.subscribe_with_reply("agents.command.*", handler)
        with pytest.raises(ValueError, match="wildcard"):
            await wrapper.subscribe_with_reply("agents.>", handler)

        # The underlying client must NOT have been called for an
        # invalid subject — the wrapper rejects before touching nats-py.
        fake_client.subscribe.assert_not_awaited()

    async def test_subscribe_with_reply_handler_receives_payload_and_reply_to(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        """Bug #1 contract: handler signature is ``(payload, reply_to)``."""
        from nats_core.events import CommandPayload

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        seen: list[tuple[CommandPayload, str]] = []

        async def handler(payload: CommandPayload, reply_to: str) -> None:
            seen.append((payload, reply_to))

        await wrapper.subscribe_with_reply("agents.command.jarvis", handler)

        # Recover the callback the wrapper registered with the client
        # so we can drive it with a synthetic Msg.
        kwargs = fake_client.subscribe.call_args.kwargs
        assert "cb" in kwargs, "wrapper must register the handler via cb="
        cb = kwargs["cb"]

        payload = CommandPayload(command="ping", args={"k": "v"})
        msg = _FakeMsg(
            data=payload.model_dump_json().encode(),
            reply="_INBOX.abc.42",
        )
        await cb(msg)

        assert len(seen) == 1
        delivered_payload, delivered_reply = seen[0]
        assert isinstance(delivered_payload, CommandPayload)
        assert delivered_payload.command == "ping"
        assert delivered_payload.args == {"k": "v"}
        # Bug #1: handler must receive the raw reply inbox so it can
        # publish the ResultPayload back to the requester's future.
        assert delivered_reply == "_INBOX.abc.42"

    async def test_in_flight_counter_increments_during_handler_execution(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        from nats_core.events import CommandPayload

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None
        assert wrapper.in_flight == 0

        gate = asyncio.Event()
        observed_counter_inside: list[int] = []

        async def handler(payload: CommandPayload, reply_to: str) -> None:
            observed_counter_inside.append(wrapper.in_flight)
            await gate.wait()

        await wrapper.subscribe_with_reply("agents.command.jarvis", handler)
        cb = fake_client.subscribe.call_args.kwargs["cb"]

        msg = _FakeMsg(
            data=CommandPayload(command="ping").model_dump_json().encode(),
            reply="_INBOX.r",
        )

        handler_task = asyncio.create_task(cb(msg))

        # Yield enough times for the handler to reach ``gate.wait()``.
        for _ in range(50):
            await asyncio.sleep(0)
            if observed_counter_inside:
                break

        assert observed_counter_inside == [1], (
            "in-flight counter must be incremented BEFORE the handler runs"
        )
        assert wrapper.in_flight == 1

        gate.set()
        await asyncio.wait_for(handler_task, timeout=1.0)

        assert wrapper.in_flight == 0, "counter must decrement after handler completes"

    async def test_in_flight_counter_decrements_when_handler_raises(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        from nats_core.events import CommandPayload

        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        async def boom(payload: CommandPayload, reply_to: str) -> None:
            raise RuntimeError("handler exploded")

        await wrapper.subscribe_with_reply("agents.command.jarvis", boom)
        cb = fake_client.subscribe.call_args.kwargs["cb"]

        msg = _FakeMsg(
            data=CommandPayload(command="ping").model_dump_json().encode(),
            reply="_INBOX.r",
        )

        # The wrapper absorbs handler exceptions (logged) so the
        # nats-py reader task is not torn down by a faulty handler.
        await cb(msg)

        # The try/finally must have run regardless of the exception.
        assert wrapper.in_flight == 0


class TestDrainInFlightCounter:
    """``drain()`` waits for in-flight handlers to finish before tearing
    down the underlying connection, and times out softly (warning +
    return) when handlers refuse to complete.
    """

    async def test_drain_waits_for_in_flight_counter_to_reach_zero(
        self, patched_connect: mock.AsyncMock, fake_client: _FakeClient
    ) -> None:
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None

        # Simulate a single in-flight handler; the underlying drain MUST
        # NOT fire until the counter goes back to zero.
        wrapper._in_flight = 1  # type: ignore[attr-defined]

        drain_task = asyncio.create_task(wrapper.drain(timeout=5.0))

        # Yield so the drain coroutine can poll the counter a few times.
        for _ in range(5):
            await asyncio.sleep(0.02)

        assert not drain_task.done(), "drain must block while in_flight > 0; it returned early"
        fake_client.drain.assert_not_awaited()

        # Release the in-flight slot — drain should now complete.
        wrapper._in_flight = 0  # type: ignore[attr-defined]
        await asyncio.wait_for(drain_task, timeout=1.0)

        fake_client.drain.assert_awaited_once()

    async def test_drain_timeout_logs_warning_and_returns(
        self,
        patched_connect: mock.AsyncMock,
        fake_client: _FakeClient,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        wrapper = await NATSClient.connect(_make_config())
        assert wrapper is not None
        capsys.readouterr()  # drop the connect-success line

        # Three handlers stuck in-flight that never complete.
        wrapper._in_flight = 3  # type: ignore[attr-defined]

        # AC: drain returns without raising when the in-flight counter
        # never reaches zero — the lifecycle layer is responsible for
        # deciding whether to escalate to ``close()``.
        await wrapper.drain(timeout=0.05)

        out = capsys.readouterr().out
        # AC: warning is logged.
        assert "nats_drain_timeout" in out, (
            f"expected nats_drain_timeout warning record; got {out!r}"
        )
        # AC: the warning NAMES the count of in-flight tasks.
        assert "in_flight=3" in out, (
            f"warning must name the in-flight count (in_flight=3); got {out!r}"
        )
        # The underlying drain MUST NOT be called while handlers are
        # still active — that would close the connection mid-reply.
        fake_client.drain.assert_not_awaited()


# ===========================================================================
# Module-level surface — re-exports keep the contract self-describing
# ===========================================================================


class TestModuleSurface:
    """``infrastructure.nats_client`` re-exports the public types."""

    def test_module_exports_NATSClient(self) -> None:
        assert hasattr(nats_client_module, "NATSClient")

    def test_module_exports_NATSConnectionError(self) -> None:
        # The exception is canonical in jarvis.shared.exceptions; the
        # module re-exports it so callers don't need to know which file
        # owns it.
        assert hasattr(nats_client_module, "NATSConnectionError")
        assert nats_client_module.NATSConnectionError is NATSConnectionError

    def test_structlog_logger_is_module_scoped(self) -> None:
        # Sanity: the module obtains a structlog-bound logger so
        # downstream JSON renderers see the canonical logger name.
        assert isinstance(nats_client_module.logger, structlog.stdlib.BoundLogger) or hasattr(
            nats_client_module.logger, "bind"
        )
