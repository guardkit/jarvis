"""Fleet-memory write path for Jarvis routing-history telemetry.

Replaces the retired Graphiti write client (FEAT-MEM-09 fleet-wide cutover).
Jarvis is write-only to the graph: routing-history entries and stage-complete
edges are published as ``document`` episodes under ``project="jarvis"`` via NATS
(the fleet-memory relay ingests them into Postgres + embeddings). The public
entry point is :class:`FleetMemoryClient`, whose ``add_episode`` surface matches
the routing-history writer's existing call sites.
"""

from __future__ import annotations

from jarvis.infrastructure.fleet_memory.client import FleetMemoryClient
from jarvis.infrastructure.fleet_memory.mapping import (
    GroupMapping,
    group_for_source,
    resolve,
)
from jarvis.infrastructure.fleet_memory.payloads import (
    build_memory_episode,
    sanitize_identifier,
)
from jarvis.infrastructure.fleet_memory.publisher import (
    PublishSummary,
    build_nats_client,
    publish_episodes,
)

__all__ = [
    "FleetMemoryClient",
    "GroupMapping",
    "PublishSummary",
    "build_memory_episode",
    "build_nats_client",
    "group_for_source",
    "publish_episodes",
    "resolve",
    "sanitize_identifier",
]
