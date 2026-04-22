"""Session model for Jarvis.

Defines the :class:`Session` Pydantic model representing an active user session.
Each session has a 1:1 mapping with a LangGraph thread (DDR-004).

This module belongs to the sessions package (Group D) per ADR-ARCH-006.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from jarvis.shared.constants import Adapter


class Session(BaseModel):
    """Immutable representation of a user session.

    Attributes:
        session_id: Adapter-prefixed unique identifier (e.g. ``cli-01HA...``).
        adapter: The adapter surface that created this session.
        user_id: The user who owns this session.
        thread_id: LangGraph thread identifier — equals ``session_id`` in Phase 1
            per DDR-004.
        started_at: UTC timestamp when the session was created.
        correlation_id: ULID reserved for FEAT-004 trace-richness (ADR-ARCH-020).
        metadata: Arbitrary key-value pairs for adapter-specific data.
    """

    session_id: str
    adapter: Adapter
    user_id: str
    thread_id: str
    started_at: datetime
    correlation_id: str
    metadata: dict[str, Any] = {}
