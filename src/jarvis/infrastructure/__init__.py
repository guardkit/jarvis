"""Infrastructure package — structured logging and application lifecycle.

Provides:
    - :func:`configure` — structlog setup (JSON on pipes, console on TTYs)
    - :func:`build_app_state` — async bootstrap returning a fully-wired :class:`AppState`
    - :func:`startup` — backwards-compatible alias for :func:`build_app_state`
    - :func:`shutdown` — async graceful teardown (idempotent)
    - :class:`AppState` — frozen dataclass holding runtime dependencies
"""

from jarvis.infrastructure.lifecycle import AppState, build_app_state, shutdown, startup
from jarvis.infrastructure.logging import configure

__all__ = [
    "AppState",
    "build_app_state",
    "configure",
    "shutdown",
    "startup",
]
