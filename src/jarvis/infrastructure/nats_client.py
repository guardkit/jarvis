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
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import nats
import structlog
from nats.errors import TimeoutError as _NatsTimeoutError
from nats_core.envelope import MessageEnvelope
from nats_core.events import CommandPayload

from jarvis.config.settings import JarvisConfig
from jarvis.shared.exceptions import BrokerUnreachableError, NATSConnectionError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from nats.aio.client import Client as _NatsClient
    from nats.aio.msg import Msg
    from nats.aio.subscription import Subscription
    from nats.js import JetStreamContext

# Type alias for the user-facing handler signature. The handler receives
# both the decoded ``CommandPayload`` AND the raw NATS ``reply`` inbox so
# the caller can publish the ``ResultPayload`` back to the requester
# (Bug #1 fix — a plain ``subscribe(payload)`` shape drops the reply
# inbox and the requester's request-future never resolves).
CommandReplyHandler = Callable[[CommandPayload, str], Awaitable[None]]

# ---------------------------------------------------------------------------
# Module-level seam: tests patch this in place of ``nats.connect`` so the
# wrapper code never directly imports the bare top-level coroutine. The
# indirection also keeps a single, clearly-labelled call site for the
# DDR-021 soft-fail boundary — nothing else in the project calls
# ``nats.connect`` and grep on the symbol stays definitive.
# ---------------------------------------------------------------------------
_nats_connect = nats.connect

logger = structlog.get_logger(__name__)


__all__ = ["BrokerUnreachableError", "NATSClient", "NATSConnectionError"]


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
        _in_flight: Number of currently-executing
            :meth:`subscribe_with_reply` handler invocations. Used by
            :meth:`drain` to wait for graceful handler completion before
            tearing down the underlying nats-py connection (Bug #1
            related — without the counter the broker would close mid-
            handler and the ``ResultPayload`` reply would never be
            published).
    """

    __slots__ = ("_client", "_drained", "_in_flight")

    def __init__(self, client: _NatsClient) -> None:
        self._client = client
        self._drained = False
        self._in_flight = 0

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    async def connect(cls, config: JarvisConfig) -> NATSClient | None:
        """Connect to NATS using ``config.nats_url`` (and credentials).

        Two posture lanes at the boot boundary:

        * **Hard-fail (TASK-J006-010 / runbook §3.8 / AC-005-08):**
          when the broker is physically unreachable — the initial
          ``nats.connect()`` either hangs past
          ``config.startup_connect_timeout_seconds`` (default 10s) and
          ``asyncio.wait_for`` raises ``TimeoutError``, or
          ``nats.connect()`` raises ``ConnectionRefusedError`` directly
          — a single terminal ``nats_connect_failed`` event is logged
          at ERROR and :class:`BrokerUnreachableError` is raised so the
          CLI exits non-zero via the standard ``asyncio.run`` error
          path. The per-retry ``nats_error`` warnings emitted by the
          underlying ``error_cb`` are capped by the bounded wait — they
          stop firing once the budget expires.

        * **Soft-fail (DDR-021):** any other connect failure
          (``NoServersError``, auth, TLS, DNS, ``OSError``) is caught,
          logged at ERROR with the URL and exception class, and the
          method returns ``None``. The supervisor lifecycle treats
          ``None`` as ``transport_unavailable`` and falls through to
          the stub capability registry.

        The narrow hard-fail trigger surface (``TimeoutError`` +
        ``ConnectionRefusedError``) is intentional: only the two
        "broker physically unreachable at boot" signals flip the boot
        path from soft-fail to hard-fail. Steady-state reconnect after
        a successful boot is unchanged — once :meth:`connect` returns,
        nats-py's own reconnect loop continues to absorb transient
        broker hiccups via the ``reconnected_cb`` / ``disconnected_cb``
        hooks.

        Args:
            config: The validated :class:`JarvisConfig`. Reads
                ``config.nats_url``, ``config.nats_credentials_path``,
                and ``config.startup_connect_timeout_seconds``.

        Returns:
            A connected :class:`NATSClient` on success; ``None`` on
            DDR-021 soft-fail failures (auth, TLS, ``NoServersError``,
            …).

        Raises:
            BrokerUnreachableError: When the broker is unreachable at
                boot — either the bounded wait
                (``startup_connect_timeout_seconds``) expires or
                ``nats.connect()`` raises ``ConnectionRefusedError``.
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

        budget_seconds = config.startup_connect_timeout_seconds
        started_at = time.monotonic()
        try:
            client = await asyncio.wait_for(
                _nats_connect(**kwargs),
                timeout=budget_seconds,
            )
        except (TimeoutError, ConnectionRefusedError) as exc:
            # TASK-J006-010 hard-fail at boot. ``TimeoutError`` covers
            # nats-py's internal reconnect loop exhausting the bounded
            # wait (the real-world GB10 evidence path —
            # ``ConnectionRefusedError`` raised from ``error_cb`` is
            # absorbed by nats-py's retry, so the outer ``connect()``
            # only ever times out). ``ConnectionRefusedError`` covers
            # immediate TCP refusal (the unit-test path where
            # ``nats.connect`` is monkeypatched to raise directly).
            # Either way the operator sees one terminal log line and the
            # process exits non-zero via the CLI's ``asyncio.run``
            # boundary.
            elapsed = round(time.monotonic() - started_at, 3)
            logger.error(
                "nats_connect_failed",
                nats_url=config.nats_url,
                startup_connect_timeout_seconds=budget_seconds,
                elapsed_seconds=elapsed,
                error_class=type(exc).__name__,
                error=str(exc),
            )
            raise BrokerUnreachableError(
                f"NATS broker unreachable at {config.nats_url} "
                f"after {elapsed}s "
                f"(startup_connect_timeout_seconds={budget_seconds}): "
                f"{type(exc).__name__}"
            ) from exc
        except Exception as exc:
            # DDR-021 soft-fail for non-unreachable failures
            # (``NoServersError``, auth, TLS, DNS, bare ``OSError``).
            # The log event names the URL and exception class so an
            # operator can diagnose without re-running with DEBUG
            # enabled. The supervisor stays up; dispatch tools surface
            # ``DEGRADED: transport_unavailable`` per ADR-ARCH-021.
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

    @property
    def in_flight(self) -> int:
        """Number of currently-executing reply-handler invocations.

        Bumped by :meth:`subscribe_with_reply` before each handler call
        and decremented (in a ``try``/``finally``) once the handler
        completes or raises. :meth:`drain` reads this to decide whether
        it is safe to close the underlying connection.
        """
        return self._in_flight

    # ------------------------------------------------------------------
    # Subscription (CommandPayload + reply-to inbox)
    # ------------------------------------------------------------------

    async def subscribe_with_reply(
        self,
        subject: str,
        handler: CommandReplyHandler,
    ) -> Subscription:
        """Subscribe to ``subject`` with a handler that receives ``(payload, reply_to)``.

        The wrapper:

        1. Validates ``subject`` is **flat** — wildcard tokens (``*``,
           ``>``) are rejected with :class:`ValueError` (Bug #4: a
           wildcard subscription would collect commands intended for
           other agents and break the per-agent routing contract).
        2. Registers an internal callback against the underlying
           ``nats-py`` client. The callback decodes the raw bytes into a
           :class:`CommandPayload`, extracts the ``msg.reply`` inbox,
           bumps :attr:`in_flight`, invokes ``handler(payload, reply_to)``,
           and decrements the counter in a ``try``/``finally``. Handler
           exceptions are logged and absorbed so the nats-py reader
           task is not torn down by a faulty handler.

        Args:
            subject: NATS subject to subscribe on. Must be a flat
                subject string with no ``*`` or ``>`` tokens.
            handler: Async callable receiving the decoded
                :class:`CommandPayload` and the raw ``reply_to`` inbox
                string (Bug #1 — the reply inbox is required for the
                ``ResultPayload`` to reach the requester's future).

        Returns:
            The :class:`~nats.aio.subscription.Subscription` object
            returned by the underlying client so the caller can manage
            unsubscribe / drain lifecycle.

        Raises:
            ValueError: When ``subject`` contains wildcard tokens.
        """
        if "*" in subject or ">" in subject:
            # Bug #4: only flat subjects — wildcards would collect
            # commands intended for other agents and the handler would
            # publish ``ResultPayload`` envelopes with mismatched
            # correlation IDs back to the wrong inbox.
            raise ValueError(
                "subscribe_with_reply requires a flat subject; "
                f"wildcard tokens are forbidden (Bug #4). got: {subject!r}"
            )

        client = self._client

        async def _on_message(msg: Msg) -> None:
            # Decode bytes -> CommandPayload at the wrapper boundary so
            # the handler stays domain-typed. Two wire shapes are
            # accepted (TASK-J006-009):
            #
            #   1. ``MessageEnvelope`` wrapping a ``CommandPayload`` — the
            #      production wire format published by fleet-gateway and
            #      every other agent (matches the study-tutor
            #      ``command_router`` template).
            #   2. Flat ``CommandPayload`` bytes — the runbook §2.3
            #      ``nats request`` smoke contract, preserved
            #      intentionally so operators can probe the bus without
            #      hand-building an envelope.
            #
            # Bad envelopes are logged and dropped — the alternative
            # (raising) would kill the subscription's reader task.
            try:
                envelope = MessageEnvelope.model_validate_json(msg.data)
            except Exception:
                envelope = None

            try:
                if envelope is not None:
                    payload = CommandPayload.model_validate(envelope.payload)
                else:
                    # Fallback: flat CommandPayload (runbook §2.3 smoke contract).
                    payload = CommandPayload.model_validate_json(msg.data)
            except Exception as exc:
                logger.error(
                    "nats_subscribe_decode_failed",
                    subject=subject,
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
                return

            # ``msg.reply`` is the raw NATS inbox; nats-py uses the
            # empty string (not ``None``) when no reply was set. Pass
            # through verbatim so callers can detect a fire-and-forget
            # command by checking ``reply_to == ""``.
            reply_to = msg.reply or ""

            self._in_flight += 1
            try:
                await handler(payload, reply_to)
            except Exception as exc:
                # Handler exceptions MUST NOT propagate into the nats-py
                # reader coroutine — that would tear down the
                # subscription and silently drop subsequent commands.
                logger.error(
                    "nats_handler_exception",
                    subject=subject,
                    error_class=type(exc).__name__,
                    error=str(exc),
                )
            finally:
                self._in_flight -= 1

        return await client.subscribe(subject, cb=_on_message)

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
                f"NATS request failed on subject={subject!r}: {type(exc).__name__}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Drain (idempotent shutdown)
    # ------------------------------------------------------------------

    async def drain(self, *, timeout: float = 30.0) -> None:
        """Drain in-flight handlers, then the underlying connection. Idempotent.

        Two-phase shutdown bounded by a single ``timeout`` budget:

        1. **Handler drain** — poll :attr:`in_flight` until it reaches
           zero. This lets active :meth:`subscribe_with_reply` handlers
           finish publishing their ``ResultPayload`` reply before the
           NATS connection goes away (Bug #1 related — closing the
           connection mid-handler drops the reply silently). If the
           counter does not reach zero within the timeout budget, a
           ``nats_drain_timeout`` warning is logged with the count of
           still-running handlers and the method **returns** without
           tearing down the connection — the lifecycle can decide
           whether to escalate to ``close()``.

        2. **Connection drain** — invoke the underlying client's
           ``drain()`` with the remaining budget. On underlying timeout
           a ``nats_drain_timeout`` warning is logged and the
           ``asyncio.TimeoutError`` is **re-raised** so the lifecycle
           shutdown path can decide whether to escalate.

        The default timeout (30.0s) matches the study-tutor adapter
        template. Subsequent calls after a successful drain are silent
        no-ops — no second log line, no second underlying drain, no
        exception.

        Args:
            timeout: Maximum seconds to wait across both phases. The
                handler drain consumes part of this budget; the
                remainder is forwarded to the underlying ``drain()``.

        Raises:
            asyncio.TimeoutError: When the **underlying** drain (phase
                2) doesn't complete within the remaining budget. Phase
                1 (handler drain) timeout is soft — logs a warning and
                returns.
        """
        if self._drained:
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout

        # Phase 1: wait for active subscribe_with_reply handlers.
        # Poll cadence is small (10 ms) so the wait wakes promptly when
        # the last handler decrements the counter.
        while self._in_flight > 0:
            if loop.time() >= deadline:
                logger.warning(
                    "nats_drain_timeout",
                    timeout=timeout,
                    in_flight=self._in_flight,
                )
                return
            await asyncio.sleep(0.01)

        # Phase 2: drain the underlying nats-py connection with the
        # remaining budget. ``remaining`` may be ~timeout (no in-flight
        # tasks) or noticeably smaller (we just spent budget waiting).
        remaining = max(0.0, deadline - loop.time())
        try:
            await asyncio.wait_for(self._client.drain(), timeout=remaining)
        except TimeoutError:
            # We do NOT mark drained on timeout — the connection is in
            # an unknown state and a follow-up close() may still be
            # warranted. Re-raise so the lifecycle can decide.
            logger.warning(
                "nats_drain_timeout",
                timeout=timeout,
                in_flight=self._in_flight,
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
