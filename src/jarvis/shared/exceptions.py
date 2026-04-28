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
