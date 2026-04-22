"""Infrastructure package — structured logging and application lifecycle.

Provides:
    - :func:`configure` — structlog setup (JSON on pipes, console on TTYs)
    - :func:`startup` — async application bootstrap returning :class:`AppState`
    - :func:`shutdown` — async graceful teardown (idempotent)
    - :class:`AppState` — frozen dataclass holding runtime dependencies
"""

from jarvis.infrastructure.lifecycle import AppState, shutdown, startup
from jarvis.infrastructure.logging import configure

__all__ = [
    "AppState",
    "configure",
    "shutdown",
    "startup",
]
