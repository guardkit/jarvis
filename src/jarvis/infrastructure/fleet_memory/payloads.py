"""Build typed ``MemoryEpisodeV1`` episodes from Jarvis routing-history records.

The fleet-memory relay routes an incoming ``MemoryEpisodeV1`` by
``content_format``: ``"json"`` (with ``payload_type`` set) goes to the typed
path (parsed against a registered payload model, natural-keyed, content-hash
upsert); ``"markdown"``/``"text"`` goes to the prose path (chunked + embedded,
no natural key).

Jarvis routing-history records are free-shape JSON dispatch traces with no
registered typed payload model, so they take the **prose/markdown path** —
the whole JSON body is embedded as a retrievable chunk. This mirrors the
``_build_prose_episode`` fallback in guardkit's
``guardkit/knowledge/fleet_memory_payloads.py`` (the migrated reference).

Identifiers are sanitised to fleet-memory's ``^[a-zA-Z0-9_]+$`` contract
(``fleet_memory.payloads.base.BasePayload`` rejects hyphens/colons →
``PoisonEpisodeError`` → DLQ), so the deterministic ``episode_id`` doubles as
the JetStream ``Nats-Msg-Id`` for idempotent replay.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jarvis.infrastructure.fleet_memory.mapping import GroupMapping

logger = logging.getLogger(__name__)


def sanitize_identifier(value: str) -> str:
    """Coerce an episode name to fleet-memory's identifier contract.

    fleet-memory validates ``project`` and ``identifier`` against
    ``^[a-zA-Z0-9_]+$`` (underscores only — no hyphens, colons, or spaces); a
    non-conforming identifier is DLQ'd by the relay. The mapping is
    deterministic so writes and audits agree on the same key
    (``"jarvis_routing_history:<uuid>"`` → ``"jarvis_routing_history_<uuid>"``).
    """
    if not value:
        return "unknown"
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return cleaned or "unknown"


def build_memory_episode(
    mapping: GroupMapping,
    name: str,
    episode_body: str,
    *,
    source: str = "jarvis-routing-history",
    project: str | None = None,
    occurred_at: datetime | None = None,
) -> Any:
    """Build a ``MemoryEpisodeV1`` for a Jarvis routing-history record.

    Returns a ``nats_core.events.MemoryEpisodeV1`` ready to publish on the
    prose/markdown path. Never raises — callers fail open.

    Args:
        mapping: The resolved :class:`GroupMapping` (payload type + domain tags).
        name: Episode name carrying the record id (e.g.
            ``"jarvis_routing_history:<decision_id>"`` or
            ``"stage_complete:<correlation_id>:<seq>"``).
        episode_body: The JSON-encoded routing-history record (embedded as prose).
        source: Source label — the writer's ``source_description``.
        project: Fleet-memory project namespace; an explicit value wins,
            else the mapping's back-compat default.
        occurred_at: The record's reference time → the episode ``occurred_at``.

    Returns:
        A ``MemoryEpisodeV1`` instance, or ``None`` if construction fails.
    """
    from nats_core.events import MemoryEpisodeV1

    project = project or mapping.project
    payload_type = mapping.payload_type
    identifier = sanitize_identifier(name)
    natural_key = f"{payload_type}:{project}:{identifier}"

    try:
        return MemoryEpisodeV1(
            # Deterministic → Nats-Msg-Id dedup; mirrors the relay's uuid5 input.
            episode_id=natural_key,
            # Subject segment: memory.episode.{project_id}.{episode_type}.
            project_id=project,
            episode_type=payload_type,  # "document" — a NATS-safe subject segment
            content_format="markdown",  # → relay prose/chunk path (_ingest_prose)
            payload_type=None,  # prose path takes no typed payload
            body=episode_body,  # the JSON trace, embedded as a retrievable chunk
            name=name,
            source=source,
            occurred_at=occurred_at,
            # Forward-compat: carry the group's domain tags so a future
            # group-scoped read (FEAT-JARVIS-008) can filter routing traces.
            # Ignored by relays that do not understand the hint (extra="ignore").
            ingest_hints={"domain_tags": list(mapping.domain_tags)},
        )
    except Exception as exc:  # pragma: no cover - defensive; construction is total
        logger.warning(
            "Failed to build fleet-memory episode for %r: %s", name, exc
        )
        return None
