"""Shared primitives — safe to import from anywhere in the Jarvis package.

Re-exports the public surface of :mod:`jarvis.shared.constants` and
:mod:`jarvis.shared.exceptions` for convenience.
"""

from jarvis.shared.constants import DEFAULT_ADAPTER, VERSION, Adapter
from jarvis.shared.exceptions import ConfigurationError, JarvisError, SessionNotFoundError

__all__ = [
    "DEFAULT_ADAPTER",
    "VERSION",
    "Adapter",
    "ConfigurationError",
    "JarvisError",
    "SessionNotFoundError",
]
