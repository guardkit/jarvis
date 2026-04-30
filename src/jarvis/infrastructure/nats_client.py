"""Async wrapper around ``nats-py`` providing connection lifecycle.

This module is the single canonical seam between Jarvis and the
``nats-py`` client library. It exposes :class:`NATSClient`, a thin
async wrapper that owns connect, request/reply, and drain semantics
for every other module in the codebase, so version churn and error-
hierarchy quirks of the upstream client never leak past this file.

Origin: FEAT-JARVIS-004 (Group A.2 row). The wrapper is intentionally
thin — its job is to:

1. Surface the **DDR-021 soft-fail invariant** at the connect boundary:
   :meth:`NATSClient.connect` returns ``None`` on connect failure
   (logged at ERROR but not raised) so ``build_app_state`` lifecycle
   continues. The supervisor process stays up; dispatch tools surface
   ``DEGRADED: transport_unavailable`` on each invocation.

2. Hide the ``nats-py``-version churn from the rest of the codebase —
   this is the **single place** where ``nats.connect(...)`` is called.
   Every other module receives the wrapper.

3. Provide a :meth:`drain` that ``lifecycle.shutdown`` can rely on,
   bounded by an explicit timeout and **idempotent** so re-entrant
   teardown paths don't double-drain or double-log.

4. Wire the reconnect-callback hooks (``error_cb``, ``reconnected_cb``,
   ``disconnected_cb``) into ``structlog``-bound logger fields per
   ADR-ARCH-020 — operator-actionable and trace-rich.

The :attr:`NATSClient.js` property exposes ``JetStreamContext`` for
FEAT-JARVIS-005's ``queue_build`` swap; FEAT-JARVIS-004 doesn't use it
but the surface is here for forward-compat (per the API-internal §1
contract).

References
----------
* ``docs/design/FEAT-JARVIS-004/contracts/API-internal.md`` §1 —
  authoritative class signature for the FEAT-JARVIS-004 design doc.
* ``docs/design/FEAT-JARVIS-004/decisions/DDR-021-nats-unavailable-soft-fail.md``
  — DDR-021 soft-fail invariant on connect failure.
* ``docs/architecture/decisions/ADR-ARCH-020-trace-richness-by-default.md``
  — structured-logging / trace-richness contract for transport events.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import nats
import structlog
from nats.errors import TimeoutError as _NatsTimeoutError

from jarvis.config.settings import JarvisConfig
from jarvis.shared.exceptions import NATSConnectionError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from nats.aio.client import Client as _NatsClient
    from nats.aio.msg import Msg
    from nats.js import JetStreamContext

# ---------------------------------------------------------------------------
# Module-level seam: tests patch this in place of ``nats.connect`` so the
# wrapper code never directly imports the bare top-level coroutine. The
# indirection also keeps a single, clearly-labelled call site for the
# DDR-021 soft-fail boundary — nothing else in the project calls
# ``nats.connect`` and grep on the symbol stays definitive.
# ---------------------------------------------------------------------------
_nats_connect = nats.connect

logger = structlog.get_logger(__name__)


__all__ = ["NATSClient", "NATSConnectionError"]


class NATSClient:
    """Thin async wrapper around ``nats.aio.client.Client``.

    Construction is private — call :meth:`connect` to obtain an
    instance. Direct construction is supported only for tests that
    inject a pre-built fake client.

    Attributes:
        _client: The underlying ``nats-py`` client. Exposed read-only
            via :attr:`client`.
        _drained: Latch flipped by :meth:`drain` so subsequent calls
            are no-ops (AC-005 idempotency).
    """

    __slots__ = ("_client", "_drained")

    def __init__(self, client: _NatsClient) -> None:
        self._client = client
        self._drained = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    async def connect(cls, config: JarvisConfig) -> NATSClient | None:
        """Connect to NATS using ``config.nats_url`` (and credentials).

        DDR-021 soft-fail: any failure during connect (resolution,
        TLS, auth, or transport) is caught, logged at ERROR with the
        URL we tried and the exception class, and the method returns
        ``None``. The supervisor lifecycle treats ``None`` as
        ``transport_unavailable`` and falls through to the stub
        capability registry.

        Args:
            config: The validated :class:`JarvisConfig`. Reads
                ``config.nats_url`` and ``config.nats_credentials_path``.

        Returns:
            A connected :class:`NATSClient` on success; ``None`` on any
            connect failure. Never raises.
        """
        kwargs: dict[str, Any] = {
            "servers": config.nats_url,
            "error_cb": _on_error,
            "disconnected_cb": _on_disconnect,
            "reconnected_cb": _on_reconnect,
            "closed_cb": _on_closed,
        }

        # ``nats-py`` accepts ``user_credentials`` as either a path or a
        # callable. Forwarding the configured ``Path`` keeps the file-
        # based ``.creds`` path working for production deployments;
        # ``None`` (dev / anonymous) is the default and we simply omit
        # the kwarg in that case.
        if config.nats_credentials_path is not None:
            kwargs["user_credentials"] = str(config.nats_credentials_path)

        try:
            client = await _nats_connect(**kwargs)
        except Exception as exc:
            # Catch-all is intentional: DDR-021 mandates soft-fail on
            # ANY connect failure so the supervisor stays up. The log
            # event names the URL and exception class so an operator
            # can diagnose without re-running with DEBUG enabled.
            logger.error(
                "nats_connect_failed",
                nats_url=config.nats_url,
                error_class=type(exc).__name__,
                error=str(exc),
            )
            return None

        logger.info(
            "nats_connect_success",
            nats_url=config.nats_url,
        )
        return cls(client)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def client(self) -> _NatsClient:
        """The underlying ``nats-py`` client. Read-only.

        Other modules consume the wrapper rather than the raw client;
        this property exists so ``fleet_registration`` /
        ``capabilities_registry`` (which speak the
        ``NATSKVManifestRegistry`` protocol) can pull the client they
        need without poking at private state.
        """
        return self._client

    @property
    def js(self) -> JetStreamContext:
        """The JetStream context bound to this connection.

        Used by FEAT-JARVIS-005's ``queue_build`` swap. FEAT-JARVIS-004
        does not consume JetStream but the surface is required by the
        API-internal §1 contract so the v1 → v1.5 transition is a
        no-op for the wrapper.
        """
        return self._client.jetstream()

    # ------------------------------------------------------------------
    # Request/reply
    # ------------------------------------------------------------------

    async def request(
        self,
        subject: str,
        payload: bytes,
        *,
        timeout: float,
    ) -> Msg:
        """Issue a NATS request/reply with a bounded timeout.

        Maps the ``nats-py`` error surface onto the project's
        domain-typed exception family per design §8:

        * Timeout → ``asyncio.TimeoutError`` (i.e. the built-in
          ``TimeoutError`` from Python 3.11+, which the dispatch
          sequence catches directly).
        * Transport failure (connection closed, draining, stale) →
          :class:`NATSConnectionError` so the dispatch tools can
          surface ``DEGRADED: transport_unavailable``.

        Args:
            subject: NATS subject to publish on.
            payload: Encoded request body.
            timeout: Per-call timeout (seconds). Forwarded to
                ``Client.request`` so reconnects and slow brokers
                are bounded at the transport layer.

        Returns:
            The reply :class:`Msg`.

        Raises:
            asyncio.TimeoutError: When the broker doesn't reply
                within ``timeout``.
            NATSConnectionError: On any transport-level failure.
        """
        try:
            return await self._client.request(subject, payload, timeout=timeout)
        except _NatsTimeoutError:
            # ``nats.errors.TimeoutError`` is a subclass of the built-in
            # ``TimeoutError`` (== ``asyncio.TimeoutError`` from 3.11),
            # so the design §8 ``except asyncio.TimeoutError`` clause
            # will catch it. We re-raise verbatim to preserve the
            # underlying class — operators reading the logs see the
            # nats-py-specific subclass and can grep for it.
            raise
        except TimeoutError:
            # Some nats-py paths surface a plain asyncio.TimeoutError
            # (e.g. when a future is cancelled by the inbox subscriber
            # rather than the request future). Pass through verbatim.
            raise
        except Exception as exc:
            # Any other failure — connection closed, drain in flight,
            # stale connection, server pool exhausted — is a transport
            # error from the supervisor's point of view. Wrap once so
            # callers don't have to know the nats-py error hierarchy.
            raise NATSConnectionError(
                f"NATS request failed on subject={subject!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Drain (idempotent shutdown)
    # ------------------------------------------------------------------

    async def drain(self, *, timeout: float = 5.0) -> None:
        """Drain in-flight messages, then close. Idempotent.

        The first call invokes the underlying client's ``drain()``
        bounded by ``timeout`` and emits an INFO ``nats_drain_complete``
        event. Subsequent calls are silent no-ops — no second log line,
        no second underlying drain, no exception.

        Args:
            timeout: Maximum seconds to wait for the drain to
                complete. ``asyncio.TimeoutError`` is raised if the
                drain doesn't finish in time so the lifecycle's
                shutdown path can decide whether to escalate to
                ``close()``.

        Raises:
            asyncio.TimeoutError: When the underlying drain doesn't
                complete within ``timeout`` (only on the first call —
                subsequent calls remain silent no-ops).
        """
        if self._drained:
            return

        try:
            await asyncio.wait_for(self._client.drain(), timeout=timeout)
        except TimeoutError:
            # We do NOT mark drained on timeout — the connection is in
            # an unknown state and a follow-up close() may still be
            # warranted. Re-raise so the lifecycle can decide.
            logger.warning(
                "nats_drain_timeout",
                timeout=timeout,
            )
            raise

        self._drained = True
        logger.info("nats_drain_complete", timeout=timeout)


# ---------------------------------------------------------------------------
# Module-level reconnect callbacks — bound to a structlog logger so every
# transport event lands as a JSON-renderable record under the canonical
# logger name. Module scope (not method scope) lets the tests pull the
# bound callbacks out of the ``_nats_connect`` mock kwargs and exercise
# them directly without instantiating a real client.
# ---------------------------------------------------------------------------


async def _on_reconnect() -> None:
    """Log a structured ``nats_reconnect`` event when nats-py reconnects."""
    logger.info("nats_reconnect")


async def _on_disconnect() -> None:
    """Log a structured ``nats_disconnect`` event on transport drop.

    Logged at WARNING because a disconnect is operator-relevant — even
    if the next event is a clean reconnect, the gap is worth surfacing.
    """
    logger.warning("nats_disconnect")


async def _on_error(exc: Exception) -> None:
    """Log a structured ``nats_error`` event for transient async errors.

    The nats-py client surfaces async errors (slow consumer, protocol
    blip, parser desync) via the ``error_cb`` rather than raising them
    out of in-flight calls. Without a bound callback they would be
    swallowed; with this hook they land in the structured log stream.
    """
    logger.warning(
        "nats_error",
        error_class=type(exc).__name__,
        error=str(exc),
    )


async def _on_closed() -> None:
    """Log a structured ``nats_closed`` event on connection close."""
    logger.info("nats_closed")
