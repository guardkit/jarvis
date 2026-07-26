"""Tests for ``NATSClient.connect`` boot-path hard-fail behaviour (TASK-J006-010).

Covers the boot-path AC family of TASK-J006-010:

  AC-010-01: ``serve-nats`` exits within ``startup_connect_timeout_seconds``
             on an unreachable broker (driver: asyncio.wait_for bound).
  AC-010-02: Single terminal ``nats_connect_failed`` event (level=error)
             names the URL, error class, and elapsed wall-clock.
  AC-010-05: Wrapper raises a typed :class:`BrokerUnreachableError` when
             ``nats.connect`` raises ``ConnectionRefusedError`` directly
             (test-only path simulating immediate TCP refusal).

The runbook AC-005-08 / GB10 live verification (AC-010-06) is covered by
the integration runbook, not by this file.

These tests are deliberately separated from ``test_nats_client.py`` so
the DDR-021 soft-fail tests there (``NoServersError`` → ``None``, bare
``OSError`` → ``None``) stay grouped with the rest of the legacy
contract. The hard-fail surface is a narrow refinement to the boot path
only — every other connect failure mode still soft-fails per DDR-021.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import pytest
import structlog

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure import nats_client as nats_client_module
from jarvis.infrastructure.nats_client import NATSClient
from jarvis.shared.exceptions import BrokerUnreachableError


@pytest.fixture(autouse=True)
def _capture_structlog() -> Any:
    """Route structlog events through pytest's stdout capture.

    Mirrors ``tests/test_nats_client.py`` so the ``nats_connect_failed``
    terminal log line lands on stdout where ``capsys`` can grep it.
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


def _make_config(**overrides: Any) -> JarvisConfig:
    """Construct a JarvisConfig that bypasses environment lookup.

    Tests override ``startup_connect_timeout_seconds`` to keep the
    bounded-wait path fast (1s) — the production default (10s) is
    asserted in :class:`JarvisConfig` itself, not here.
    """
    base: dict[str, Any] = {
        "nats_url": "nats://localhost:4222",
        "nats_credentials_path": None,
        "startup_connect_timeout_seconds": 1,
    }
    base.update(overrides)
    return JarvisConfig(_env_file=None, **base)  # type: ignore[arg-type]


# ===========================================================================
# AC-010-05 — ConnectionRefusedError → BrokerUnreachableError
# ===========================================================================


class TestAC010_05ConnectionRefusedRaisesBrokerUnreachable:
    """When ``nats.connect`` raises ``ConnectionRefusedError`` directly,
    the wrapper raises :class:`BrokerUnreachableError`."""

    async def test_connect_raises_broker_unreachable_on_connection_refused(self) -> None:
        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(
                side_effect=ConnectionRefusedError(
                    "[Errno 111] Connect call failed ('127.0.0.1', 4222)"
                )
            ),
        ), pytest.raises(BrokerUnreachableError) as exc_info:
            await NATSClient.connect(_make_config(nats_url="nats://localhost:4222"))

        # The exception message must name the URL and the underlying
        # exception class so log aggregators can grep on either field
        # without parsing the stack trace.
        assert "nats://localhost:4222" in str(exc_info.value)
        assert "ConnectionRefusedError" in str(exc_info.value)
        # The original exception must be chained via ``__cause__`` so the
        # operator-facing stack trace points back to nats-py's error.
        assert isinstance(exc_info.value.__cause__, ConnectionRefusedError)

    async def test_broker_unreachable_message_redacts_url_credentials(self) -> None:
        """F10: an inline-credential ``nats_url`` is redacted in the
        BrokerUnreachableError message — host:port survives, the password
        never does. The ``secret`` token here is a dummy, not a real cred."""
        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=ConnectionRefusedError("refused")),
        ), pytest.raises(BrokerUnreachableError) as exc_info:
            await NATSClient.connect(
                _make_config(nats_url="nats://user:secret@localhost:4222")
            )

        msg = str(exc_info.value)
        assert "localhost:4222" in msg
        assert "secret" not in msg
        assert "user:secret" not in msg


# ===========================================================================
# AC-010-01 — Bounded wait fires within startup_connect_timeout_seconds
# ===========================================================================


class TestAC010_01BoundedWaitOnHangingConnect:
    """When ``nats.connect`` hangs (broker unreachable, internal retry
    loop), the wrapper's ``asyncio.wait_for`` budget fires and the
    wrapper raises :class:`BrokerUnreachableError`."""

    async def test_connect_raises_broker_unreachable_on_timeout(self) -> None:
        async def _hang(**_kwargs: Any) -> None:
            # Sleep longer than the bounded wait so the wrapper's
            # ``asyncio.wait_for`` fires before this completes.
            await asyncio.sleep(60)

        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=_hang),
        ), pytest.raises(BrokerUnreachableError) as exc_info:
            # The fixture sets ``startup_connect_timeout_seconds=1``
            # so the test completes in ~1s rather than 10s.
            await NATSClient.connect(_make_config())

        # Message names the URL, elapsed time, and timeout class so
        # operators reading the log line know it was the bounded wait
        # that fired (not an upstream exception).
        assert "nats://localhost:4222" in str(exc_info.value)
        assert "TimeoutError" in str(exc_info.value)
        assert "startup_connect_timeout_seconds=1" in str(exc_info.value)

    async def test_connect_respects_startup_connect_timeout_seconds_budget(self) -> None:
        async def _hang(**_kwargs: Any) -> None:
            await asyncio.sleep(60)

        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=_hang),
        ):
            loop = asyncio.get_running_loop()
            started_at = loop.time()
            with pytest.raises(BrokerUnreachableError):
                await NATSClient.connect(_make_config(startup_connect_timeout_seconds=1))
            elapsed = loop.time() - started_at

        # The wait must fire within ~1s (budget) + small overhead — we
        # assert <3s to absorb scheduler jitter without making the test
        # flaky. Anything substantially over 3s would mean the bound is
        # not being honoured.
        assert elapsed < 3.0, (
            f"bounded wait should fire within ~1s of the budget, got {elapsed:.3f}s"
        )


# ===========================================================================
# AC-010-02 — Terminal nats_connect_failed event at level=error
# ===========================================================================


class TestAC010_02TerminalLogEvent:
    """Hard-fail path emits a single ``nats_connect_failed`` event at
    level=error naming the URL, exception class, and elapsed time."""

    async def test_terminal_log_event_on_connection_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(
                side_effect=ConnectionRefusedError("Connect call failed")
            ),
        ), pytest.raises(BrokerUnreachableError):
            await NATSClient.connect(_make_config(nats_url="nats://down:4222"))

        out = capsys.readouterr().out
        # Operator-actionable fields the log line MUST include.
        assert "nats_connect_failed" in out
        assert "level='error'" in out
        assert "nats://down:4222" in out
        assert "ConnectionRefusedError" in out
        assert "elapsed_seconds=" in out
        assert "startup_connect_timeout_seconds=" in out

    async def test_terminal_log_event_on_bounded_wait_timeout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        async def _hang(**_kwargs: Any) -> None:
            await asyncio.sleep(60)

        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=_hang),
        ), pytest.raises(BrokerUnreachableError):
            await NATSClient.connect(
                _make_config(nats_url="nats://hang:4222", startup_connect_timeout_seconds=1)
            )

        out = capsys.readouterr().out
        assert "nats_connect_failed" in out
        assert "level='error'" in out
        assert "nats://hang:4222" in out
        # On Python 3.11+ ``asyncio.TimeoutError`` is an alias for the
        # builtin ``TimeoutError`` — either name is acceptable in the
        # ``error_class`` field, but at least one must appear so log
        # aggregators can grep for the timeout cause.
        assert "TimeoutError" in out
        assert "startup_connect_timeout_seconds=1" in out


# ===========================================================================
# AC-010-04 (negative) — DDR-021 soft-fail preserved for non-unreachable
# errors. Belt-and-braces with tests/test_nats_client.py — kept here so a
# refactor that accidentally tightens the hard-fail surface fails noisily.
# ===========================================================================


class TestDDR021SoftFailPreserved:
    """DDR-021 soft-fail is preserved for non-unreachable errors —
    ``NoServersError`` and bare ``OSError`` still return ``None``."""

    async def test_no_servers_error_still_soft_fails(self) -> None:
        from nats.errors import NoServersError

        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=NoServersError()),
        ):
            wrapper = await NATSClient.connect(_make_config())

        # NoServersError is NOT in the hard-fail set — DDR-021 soft-fail
        # applies and the wrapper returns None.
        assert wrapper is None

    async def test_bare_os_error_still_soft_fails(self) -> None:
        # Bare ``OSError`` (e.g. DNS failure) is NOT
        # ``ConnectionRefusedError`` (which is a subclass). DDR-021
        # soft-fail applies — wrapper returns None.
        with mock.patch.object(
            nats_client_module,
            "_nats_connect",
            new=mock.AsyncMock(side_effect=OSError("dns lookup failed")),
        ):
            wrapper = await NATSClient.connect(_make_config())

        assert wrapper is None
