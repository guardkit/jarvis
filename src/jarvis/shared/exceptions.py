"""Jarvis exception hierarchy.

All Jarvis-specific exceptions derive from :class:`JarvisError` so callers
can catch a single base class when appropriate.

This module MUST NOT import from any other jarvis subpackage
(config, sessions, agents, infrastructure, cli).
"""

from __future__ import annotations


class JarvisError(Exception):
    """Root exception for all Jarvis-specific errors."""


class ConfigurationError(JarvisError):
    """Configuration is invalid or a required key is missing."""


class SessionNotFoundError(JarvisError):
    """Raised when resume_session or end_session targets an unknown session_id."""


class NATSConnectionError(JarvisError):
    """Raised by ``NATSClient.request`` when the NATS transport is unusable.

    This wraps the family of nats-py transport-layer errors
    (``ConnectionClosedError``, ``StaleConnectionError``,
    ``ConnectionDrainingError`` …) into a single Jarvis-owned exception
    so downstream tools (``dispatch_by_capability``, ``queue_build``)
    can branch on transport-failure once and surface the
    ``DEGRADED: transport_unavailable`` structured error per
    ADR-ARCH-021 / DDR-021.

    Timeouts are NOT wrapped — ``NATSClient.request`` propagates
    ``asyncio.TimeoutError`` (== built-in ``TimeoutError``) verbatim so
    the timeout handling in the dispatch sequence (design §8) stays a
    direct ``except asyncio.TimeoutError`` clause.
    """


class BrokerUnreachableError(JarvisError):
    """Raised by ``NATSClient.connect`` when the broker is unreachable at boot.

    Distinct from :class:`NATSConnectionError` (which wraps mid-run
    transport failures): this exception signals the hard-dependency-at-
    boot posture documented in
    ``docs/runbooks/RUNBOOK-FEAT-JARVIS-006-serve-nats-implementation.md``
    §3.8 / AC-005-08 and fixed in TASK-J006-010.

    The boot path bounds the initial ``nats.connect()`` with
    ``asyncio.wait_for(timeout=config.startup_connect_timeout_seconds)``
    and raises this on either:

    * ``asyncio.TimeoutError`` — nats-py's internal reconnect loop
      exhausted the budget (e.g. broker container stopped).
    * ``ConnectionRefusedError`` — definitive TCP refusal at the
      configured ``nats_url``.

    Other connect failures (auth, TLS, ``NoServersError``, DNS) continue
    to soft-fail per DDR-021 — ``connect()`` returns ``None`` and the
    supervisor stays up in degraded mode. The narrow trigger surface is
    intentional: only the two "broker physically unreachable" signals
    flip the boot path from soft-fail to hard-fail.

    Callers receiving this exception should let it propagate to the CLI
    entry point so ``asyncio.run`` exits the process non-zero — the log
    line preceding the raise (``nats_connect_failed`` at level=error)
    carries the operator-actionable context.
    """
