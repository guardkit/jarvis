"""Group mapping for the Jarvis → fleet-memory routing-history write path.

Jarvis writes exactly two kinds of routing-history record to the graph:

* **routing-history entries** — one :class:`JarvisRoutingHistoryEntry` per
  dispatch decision (``source_description="jarvis-routing-history"``).
* **stage-complete edges** — one append-only edge per Forge
  ``pipeline.stage-complete.*`` event
  (``source_description="jarvis-routing-history-edge"``).

Both land in fleet-memory as ``document`` episodes under ``project="jarvis"``.
There is no typed fleet-memory payload model for routing traces (they are free
-shape JSON), so they take the relay's prose/chunk path — see
:mod:`jarvis.infrastructure.fleet_memory.payloads`.

This mirrors guardkit's ``guardkit/knowledge/fleet_memory_mapping.py`` (the sole
migrated reference in the fleet), trimmed to the two write-only groups Jarvis
emits. The ``project`` here is the mapping's back-compat default; the live
project is threaded in at write time from
:attr:`~jarvis.config.settings.JarvisConfig.fleet_memory_project`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# The seven registered fleet-memory payload types (see the relay's payload
# registry). Jarvis only ever writes ``document`` (prose path); the alias is
# kept as a Literal so a typo in a future group is caught at type-check time.
PayloadType = Literal[
    "adr",
    "review_report",
    "build_outcome",
    "pattern",
    "warning",
    "seed_module",
    "document",
]


@dataclass(frozen=True)
class GroupMapping:
    """Fleet-memory identity mapping for a Jarvis routing-history group.

    Attributes:
        project: Fleet-memory project namespace (back-compat default; the
            live value is threaded from ``JarvisConfig.fleet_memory_project``).
        payload_type: One of the registered fleet-memory payload types.
        domain_tags: Domain-specific tags carried as forward-compat ingest
            hints for future group-scoped reads (FEAT-JARVIS-008).
        disposition: ``"migrate"`` (publish) or ``"retire"`` (no-op).
    """

    project: str
    payload_type: PayloadType
    domain_tags: list[str]
    disposition: Literal["migrate", "retire"]


# Authoritative map: routing-history group → fleet-memory identity.
GROUP_ID_MAP: dict[str, GroupMapping] = {
    "routing_history": GroupMapping(
        project="jarvis",
        payload_type="document",
        domain_tags=["routing", "dispatch"],
        disposition="migrate",
    ),
    "routing_history_edge": GroupMapping(
        project="jarvis",
        payload_type="document",
        domain_tags=["routing", "stage"],
        disposition="migrate",
    ),
}

# Maps the writer's ``source_description`` label to a group_id so the writer's
# existing keyword-only ``add_episode`` surface does not have to change — the
# fleet-memory client derives the group internally. See
# :meth:`jarvis.infrastructure.fleet_memory.client.FleetMemoryClient.add_episode`.
_SOURCE_TO_GROUP: dict[str, str] = {
    "jarvis-routing-history": "routing_history",
    "jarvis-routing-history-edge": "routing_history_edge",
}


def _normalize_group_id(group_id: str) -> str:
    """Normalize a group_id to lowercase-with-underscores (PEP 503 style)."""
    return group_id.lower().replace("-", "_")


def resolve(group_id: str) -> GroupMapping | None:
    """Resolve a group_id to its fleet-memory mapping.

    Args:
        group_id: Routing-history group identifier (normalized before lookup).

    Returns:
        The :class:`GroupMapping` if mapped, else ``None`` (fail-open — callers
        skip unmapped groups).
    """
    return GROUP_ID_MAP.get(_normalize_group_id(group_id))


def group_for_source(source_description: str) -> str:
    """Derive the group_id from a writer ``source_description`` label.

    Falls back to ``"routing_history"`` for any unrecognised label (the writer
    only ever emits the two known values, but a defensive default keeps a stray
    label on the publish path rather than silently dropped).
    """
    return _SOURCE_TO_GROUP.get(source_description, "routing_history")
