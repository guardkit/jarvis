"""Shared constants for the Jarvis project.

This module defines project-wide constants including the version string
and the Adapter enum. It MUST NOT import from any other jarvis subpackage
(config, sessions, agents, infrastructure, cli).
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Version — single source of truth re-exported by jarvis.__init__
# ---------------------------------------------------------------------------
VERSION: str = "0.1.0"

# ---------------------------------------------------------------------------
# Adapter enum — identifies the surface that minted a session
# ---------------------------------------------------------------------------


class Adapter(StrEnum):
    """Adapter types supported by Jarvis.

    Phase 1 only supports CLI; the remaining members are reserved
    for future features (Telegram FEAT-006, Dashboard/Reachy FEAT-009).
    """

    CLI = "cli"
    TELEGRAM = "telegram"
    DASHBOARD = "dashboard"
    REACHY = "reachy"


# ---------------------------------------------------------------------------
# Default adapter for Phase 1
# ---------------------------------------------------------------------------
DEFAULT_ADAPTER: Adapter = Adapter.CLI
