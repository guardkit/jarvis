"""Write-only fleet-memory client for the Jarvis routing-history writer.

This is the fleet-memory replacement for the retired Graphiti client. It keeps
the exact keyword-only ``add_episode`` surface the
:class:`~jarvis.infrastructure.routing_history.RoutingHistoryWriter` already
calls (``name`` / ``episode_body`` / ``source_description`` / ``reference_time``)
so the writer body is unchanged on cutover — the group→payload mapping is
derived internally from ``source_description``.

Flow (mirrors guardkit's ``FleetMemoryClient.add_episode``, write-only):
``source_description`` → :func:`group_for_source` → :func:`resolve` →
:func:`build_memory_episode` → :func:`publish_episodes`. **Fail-open**: every
error path returns ``None`` and never raises into the caller's fire-and-forget
task (DDR-019). Jarvis does not read from fleet-memory (reads are FEAT-JARVIS
-008), so there is no ``search`` surface.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from jarvis.infrastructure.fleet_memory.mapping import group_for_source, resolve
from jarvis.infrastructure.fleet_memory.payloads import build_memory_episode
from jarvis.infrastructure.fleet_memory.publisher import publish_episodes

if TYPE_CHECKING:
    from jarvis.config.settings import JarvisConfig

logger = logging.getLogger(__name__)


class FleetMemoryClient:
    """Fleet-memory write client with the routing-history writer's interface.

    Structurally satisfies
    :class:`~jarvis.infrastructure.routing_history.MemoryClientProtocol` so the
    writer can hold it interchangeably with the (test) recording double.

    Args:
        config: The validated :class:`JarvisConfig`. Reads
            ``fleet_memory_enabled``, ``fleet_memory_project``, ``nats_url``,
            and ``nats_credentials_path``.
    """

    def __init__(self, config: JarvisConfig) -> None:
        self._config = config
        self._nats_available = self._check_nats_available()

    @property
    def enabled(self) -> bool:
        """Whether fleet-memory writes are enabled (``JARVIS_FLEET_MEMORY_ENABLED``)."""
        return bool(self._config.fleet_memory_enabled)

    async def close(self) -> None:
        """Close the client (no-op — the publisher connects per batch).

        Present for parity with the retired Graphiti client's ``aclose()`` so
        the lifecycle shutdown step can call it unconditionally.
        """
        return None

    @staticmethod
    def _check_nats_available() -> bool:
        """Whether ``nats_core`` (the write dependency) is importable."""
        try:
            import nats_core  # noqa: F401

            return True
        except ImportError:
            return False

    async def add_episode(
        self,
        *,
        name: str,
        episode_body: str,
        source_description: str = "jarvis-routing-history",
        reference_time: datetime | None = None,
    ) -> str | None:
        """Publish a routing-history record to fleet-memory (fail-open).

        Derives the group from ``source_description``, resolves it to a
        fleet-memory payload identity, builds a ``MemoryEpisodeV1``, and
        publishes it via NATS as the ``jarvis`` project. Returns the episode's
        natural key on success, else ``None`` (unmapped/retired group,
        ``nats_core`` unavailable, episode-build failure, or publish failure).
        Never raises — a memory write must not break the writer's task flow.

        Args:
            name: Episode name carrying the record id.
            episode_body: JSON-encoded routing-history record.
            source_description: Writer label — selects the group
                (``"jarvis-routing-history"`` vs ``"jarvis-routing-history-edge"``).
            reference_time: The record's timestamp → episode ``occurred_at``.

        Returns:
            The natural key (``"document:jarvis:<identifier>"``) on a successful
            publish, else ``None``.
        """
        try:
            group_id = group_for_source(source_description)
            mapping = resolve(group_id)
            if mapping is None or mapping.disposition == "retire":
                logger.debug(
                    "Group %r unmapped or retired, skipping write", group_id
                )
                return None

            if not self._nats_available:
                logger.warning(
                    "nats_core not available, cannot write %r episode", group_id
                )
                return None

            episode = build_memory_episode(
                mapping,
                name=name,
                episode_body=episode_body,
                source=source_description,
                project=self._config.fleet_memory_project,
                occurred_at=reference_time,
            )
            if episode is None:
                logger.warning(
                    "Could not build fleet-memory episode for %r (%r)",
                    group_id,
                    name,
                )
                return None

            summary = await publish_episodes([episode], self._config)
            # ``episode`` is typed ``Any`` (MemoryEpisodeV1 is a lazy write-path
            # import); ``episode_id`` is a ``str`` field, so coerce explicitly to
            # satisfy the ``str | None`` return contract under mypy strict.
            episode_id: str = str(episode.episode_id)
            if summary.published >= 1:
                logger.info(
                    "routing_history_published",
                    extra={
                        "episode_id": episode_id,
                        "payload_type": mapping.payload_type,
                    },
                )
                return episode_id

            logger.warning(
                "routing_history_publish_incomplete",
                extra={
                    "episode_id": episode_id,
                    "published": summary.published,
                    "skipped_oversized": summary.skipped_oversized,
                },
            )
            return None

        except Exception as exc:
            # Fail-open: a memory write must never break the caller's task flow.
            logger.warning(
                "routing_history_write_failed",
                extra={"reason": type(exc).__name__, "detail": str(exc)},
            )
            return None
