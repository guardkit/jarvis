"""Sessions package — Session model and SessionManager.

Re-exports:
    :class:`Session` — Pydantic model for a user session.
    :class:`SessionManager` — Manages session lifecycle and supervisor invocation.
"""

from jarvis.sessions.manager import SessionManager
from jarvis.sessions.session import Session

__all__ = ["Session", "SessionManager"]
