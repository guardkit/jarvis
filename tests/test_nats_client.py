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
