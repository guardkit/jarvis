"""The Linear door: issues moved to Todo in Linear become factory requests.

See the Linear front door design (18 October 2026). Stage 3 is Linear →
factory: :mod:`.client` talks to Linear, :mod:`.mapping` turns issues into
requests, :mod:`.store` is the door's own record, and :mod:`.door` polls.
``jarvis serve-linear`` runs it.
"""

from jarvis.infrastructure.linear.client import (
    LinearAuthError,
    LinearClient,
    LinearError,
    LinearRateLimited,
)
from jarvis.infrastructure.linear.door import (
    AssumeAttemptsOpen,
    AttemptRecord,
    AttemptRecordUnavailable,
    DoorSettings,
    LinearDoor,
    door_config,
)
from jarvis.infrastructure.linear.store import DoorStore

__all__ = [
    "AssumeAttemptsOpen",
    "AttemptRecord",
    "AttemptRecordUnavailable",
    "DoorSettings",
    "DoorStore",
    "LinearAuthError",
    "LinearClient",
    "LinearDoor",
    "LinearError",
    "LinearRateLimited",
    "door_config",
]
