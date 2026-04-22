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
