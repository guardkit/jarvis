"""NATS publisher for Jarvis fleet-memory episodes.

Connects a dedicated ``nats_core.NATSClient`` (``jarvis-memory``) and publishes
``MemoryEpisodeV1`` episodes via ``publish_episode`` — the same cross-repo write
contract guardkit's harvest publisher uses. Oversized episodes (>900KB) are
caught per-episode and skipped without aborting the batch; JetStream dedup is
server-side via the deterministic ``episode_id`` → ``Nats-Msg-Id`` header.

The memory-write connection is intentionally **separate** from the supervisor's
long-lived :class:`jarvis.infrastructure.nats_client.NATSClient` (connect-per
-batch), mirroring guardkit's ``harvest_publisher.publish_episodes``. It reuses
Jarvis's existing NATS identity — ``config.nats_url`` +
``config.nats_credentials_path`` (``nats_core.NATSConfig`` supports
``creds_file``) — so no new NATS user or password is required.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nats_core.client import NATSClient
from nats_core.config import NATSConfig

if TYPE_CHECKING:
    from nats_core.events import MemoryEpisodeV1

    from jarvis.config.settings import JarvisConfig

logger = logging.getLogger(__name__)

# Hard ceiling on the one-shot connect for a fire-and-forget memory write. Bounds
# the whole connect (including any nats-py retry) the same way the supervisor's
# NATSClient.connect uses ``asyncio.wait_for`` — so an unreachable / unauthorized
# broker fails open in seconds instead of a minutes-long background retry-storm
# (DDR-019 fail-open; live-proof finding 2026-07-03).
_CONNECT_TIMEOUT_SECONDS = 6.0


@dataclass
class PublishSummary:
    """Summary of an episode-publishing batch.

    Attributes:
        published: Number of episodes successfully published.
        skipped_oversized: Number skipped for exceeding the 900KB body guard.
        counts_per_type: Count of published episodes by ``episode_type``.
    """

    published: int
    skipped_oversized: int
    counts_per_type: dict[str, int]


def build_nats_client(config: JarvisConfig) -> NATSClient:
    """Build a ``nats_core.NATSClient`` for memory writes from Jarvis config.

    Reuses the supervisor's NATS endpoint + credentials file; no dedicated
    user/password is introduced.

    Args:
        config: The validated :class:`JarvisConfig`.

    Returns:
        A configured ``NATSClient`` ready for ``connect()``.
    """
    creds_file = (
        str(config.nats_credentials_path)
        if config.nats_credentials_path is not None
        else None
    )
    nats_config = NATSConfig(
        url=config.nats_url,
        creds_file=creds_file,
        name="jarvis-memory",
        # Fail fast — this is a fire-and-forget, fail-open publisher (DDR-019).
        # NATSConfig defaults to ``max_reconnect_attempts=60`` (~2 min of retries
        # at the 2s ``reconnect_time_wait``); against an unreachable or
        # unauthorized broker that would spawn a 2-minute background retry-storm
        # per routing-history write. A one-shot connect-publish-disconnect never
        # needs reconnection, so disable retries and bound the initial connect.
        max_reconnect_attempts=0,
        connect_timeout=5.0,
    )
    return NATSClient(nats_config, source_id="jarvis-memory")


async def publish_episodes(
    episodes: list[MemoryEpisodeV1],
    config: JarvisConfig,
    client: NATSClient | None = None,
) -> PublishSummary:
    """Publish memory episodes to NATS with a 900KB guard and idempotent retry.

    Connects, publishes each episode, and disconnects. Oversized episodes are
    caught per-episode, logged with actionable guidance, and skipped without
    aborting the batch. Idempotency is server-side via deterministic
    ``episode_id`` → ``Nats-Msg-Id`` JetStream deduplication.

    Args:
        episodes: The ``MemoryEpisodeV1`` episodes to publish.
        config: The :class:`JarvisConfig` used to build the client (when
            ``client`` is ``None``).
        client: Optional pre-configured ``NATSClient`` (primarily for testing).

    Returns:
        A :class:`PublishSummary` with published / skipped / per-type counts.

    Raises:
        Exception: Connection or unexpected publish errors propagate — the
            caller (:class:`FleetMemoryClient`) wraps this fail-open.
    """
    if client is None:
        client = build_nats_client(config)

    published = 0
    skipped_oversized = 0
    type_counts: Counter[str] = Counter()

    connected = False
    try:
        # Bound the connect so a bad/unauthorized broker fails open in seconds
        # rather than triggering nats-py's multi-minute reconnect loop.
        await asyncio.wait_for(client.connect(), timeout=_CONNECT_TIMEOUT_SECONDS)
        connected = True

        for episode in episodes:
            try:
                await client.publish_episode(episode)
                published += 1
                type_counts[episode.episode_type] += 1
                logger.debug(
                    "Published episode %s (type=%s, size=%d bytes)",
                    episode.episode_id,
                    episode.episode_type,
                    len(episode.body.encode()),
                )
            except ValueError as exc:
                # Per-episode oversized guard (>900KB) — skip, do not abort.
                if "exceeding the" in str(exc) and "byte" in str(exc):
                    skipped_oversized += 1
                    logger.warning(
                        "Skipped oversized episode %s (type=%s, size=%d bytes): "
                        "%s. Offload the trace upstream to stay under 900KB.",
                        episode.episode_id,
                        episode.episode_type,
                        len(episode.body.encode()),
                        str(exc),
                    )
                else:
                    raise
    finally:
        # Disconnect only if the connect succeeded; a never-connected client
        # has no live connection to drain. Swallow teardown errors — the caller
        # fails open regardless.
        if connected:
            with contextlib.suppress(Exception):
                await client.disconnect()

    return PublishSummary(
        published=published,
        skipped_oversized=skipped_oversized,
        counts_per_type=dict(type_counts),
    )
