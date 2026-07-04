"""NATS publisher for Jarvis fleet-memory episodes.

Connects a dedicated ``nats_core.NATSClient`` (``jarvis-memory``) and publishes
``MemoryEpisodeV1`` episodes via ``publish_episode`` — the same cross-repo write
contract guardkit's harvest publisher uses. Oversized episodes (>900KB) are
caught per-episode and skipped without aborting the batch; JetStream dedup is
server-side via the deterministic ``episode_id`` → ``Nats-Msg-Id`` header.

The memory-write connection is intentionally **separate** from the supervisor's
long-lived :class:`jarvis.infrastructure.nats_client.NATSClient` (connect-per
-batch), mirroring guardkit's ``harvest_publisher.publish_episodes``. It reuses
Jarvis's existing NATS identity — ``config.nats_url``,
``config.nats_credentials_path``, and the optional
``config.nats_user`` / ``config.nats_password`` user/password pair
(``nats_core.NATSConfig`` supports ``creds_file`` + ``user`` / ``password``) —
so it shares the supervisor's broker credentials with no dedicated memory
identity.
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
from pydantic import SecretStr

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

    Reuses the supervisor's NATS endpoint + credentials — the ``.creds`` file
    when set, otherwise the optional ``nats_user`` / ``nats_password`` account
    pair (forwarded only when both are set and non-blank, via the shared
    :meth:`JarvisConfig.resolve_nats_user_password` gate). No dedicated memory
    identity.

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
    # User/password account auth (JARVIS_NATS_USER / JARVIS_NATS_PASSWORD).
    # ``resolve_nats_user_password`` is the shared gate with the supervisor
    # connect — it returns the pair ONLY when both are set, non-blank, and no
    # creds file is configured. Passing a lone half, a blank, or a pair
    # alongside ``creds_file`` straight into ``NATSConfig`` would trip its
    # ``auth_fields_are_consistent`` validator (ValueError), which — since
    # ``build_nats_client`` runs before ``publish_episodes``' try/except —
    # would propagate into ``FleetMemoryClient``'s fail-open and silently drop
    # every routing-history write. ``None`` here means creds_file / URL /
    # anonymous auth stays authoritative, matching the supervisor exactly.
    user_password = config.resolve_nats_user_password()
    nats_config = NATSConfig(
        url=config.nats_url,
        creds_file=creds_file,
        user=user_password[0] if user_password is not None else None,
        # NATSConfig.password is a SecretStr | None; re-wrap the resolved
        # plaintext (the shared gate returns plaintext for the supervisor's
        # nats.connect kwargs, which need the raw value).
        password=SecretStr(user_password[1]) if user_password is not None else None,
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
