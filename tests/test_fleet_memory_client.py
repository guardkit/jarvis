"""Boundary + live tests for the Jarvis fleet-memory write client.

Follows the FEAT-MEM-09 §3 two-test contract:

1. **Boundary tests** — build a *real* :class:`FleetMemoryClient` (not a
   MagicMock) and stub only the external publish edge
   (``fleet_memory.client.publish_episodes``). The real ``group_for_source`` →
   ``resolve`` → ``build_memory_episode`` chain runs, so the published
   ``MemoryEpisodeV1`` shape (project, episode_type, natural key, body, tags) is
   exercised end-to-end without a live NATS broker. Runs everywhere.
2. **A ``@pytest.mark.live`` round-trip** — publishes a real episode against a
   live fleet-memory store; ``pytest.skip``s when the store is disabled. This is
   the operator's post-merge proof.

The client's ``add_episode`` keeps the retired Graphiti client's keyword-only
surface, so the routing-history writer body did not change on cutover.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.fleet_memory.client import FleetMemoryClient
from jarvis.infrastructure.fleet_memory.publisher import PublishSummary, build_nats_client

# The write path builds a ``nats_core.events.MemoryEpisodeV1``; skip cleanly if
# the memory extra is absent from a minimal env (mirrors guardkit §3).
_HAS_NATS_CORE = importlib.util.find_spec("nats_core") is not None

# Where the client resolves ``publish_episodes`` — the name is imported INTO the
# client module, so the boundary patch must target the client namespace, not
# the publisher module (else the already-bound reference is untouched).
_PUBLISH_EDGE = "jarvis.infrastructure.fleet_memory.client.publish_episodes"


def _enabled_config(project: str = "jarvis") -> JarvisConfig:
    """A real ``JarvisConfig`` with the memory write path enabled."""
    with patch.dict("os.environ", {}, clear=True):
        return JarvisConfig(
            llama_swap_base_url="http://fake-endpoint",
            fleet_memory_enabled=True,
            fleet_memory_project=project,
        )


def _summary(published: int = 1, skipped: int = 0) -> PublishSummary:
    return PublishSummary(
        published=published, skipped_oversized=skipped, counts_per_type={}
    )


@pytest.mark.skipif(not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed")
class TestFleetMemoryClientAddEpisodeBoundary:
    """``add_episode`` builds + publishes a real typed episode (edge stubbed)."""

    async def test_publishes_routing_history_document(self) -> None:
        """An entry write publishes a content_format=markdown ``document`` episode
        under project=jarvis with the dispatch domain tags and the JSON body."""
        client = FleetMemoryClient(_enabled_config())
        body = '{"decision_id": "d1", "outcome_type": "success"}'

        with patch(_PUBLISH_EDGE, new=AsyncMock(return_value=_summary(1))) as mock_pub:
            result = await client.add_episode(
                name="jarvis_routing_history:11111111-2222-4333-8444-555555555555",
                episode_body=body,
                source_description="jarvis-routing-history",
                reference_time=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
            )

        mock_pub.assert_awaited_once()
        episodes = mock_pub.call_args.args[0]
        assert len(episodes) == 1
        ep = episodes[0]
        assert ep.project_id == "jarvis"
        assert ep.episode_type == "document"
        assert ep.content_format == "markdown"
        assert ep.payload_type is None
        assert ep.body == body
        assert ep.occurred_at == datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
        assert ep.ingest_hints == {"domain_tags": ["routing", "dispatch"]}
        # Return value is the deterministic natural key.
        assert result == ep.episode_id
        assert ep.episode_id.startswith("document:jarvis:jarvis_routing_history_")

    async def test_edge_source_maps_to_stage_tags(self) -> None:
        """A stage-complete edge write carries the ``[routing, stage]`` tags."""
        client = FleetMemoryClient(_enabled_config())

        with patch(_PUBLISH_EDGE, new=AsyncMock(return_value=_summary(1))) as mock_pub:
            result = await client.add_episode(
                name="stage_complete:corr-1:0",
                episode_body='{"stage": "plan-complete"}',
                source_description="jarvis-routing-history-edge",
            )

        episodes = mock_pub.call_args.args[0]
        assert episodes[0].ingest_hints == {"domain_tags": ["routing", "stage"]}
        assert result is not None

    async def test_project_threaded_from_config(self) -> None:
        """``fleet_memory_project`` reaches the published episode's project_id."""
        client = FleetMemoryClient(_enabled_config(project="jarvis-staging"))

        with patch(_PUBLISH_EDGE, new=AsyncMock(return_value=_summary(1))) as mock_pub:
            await client.add_episode(
                name="jarvis_routing_history:abc",
                episode_body="{}",
                source_description="jarvis-routing-history",
            )

        episodes = mock_pub.call_args.args[0]
        assert episodes[0].project_id == "jarvis-staging"
        assert episodes[0].episode_id.startswith("document:jarvis-staging:")

    async def test_returns_none_when_nats_unavailable(self) -> None:
        """No ``nats_core`` → no publish attempt, returns None (fail-open)."""
        client = FleetMemoryClient(_enabled_config())
        client._nats_available = False

        with patch(_PUBLISH_EDGE, new=AsyncMock()) as mock_pub:
            result = await client.add_episode(
                name="jarvis_routing_history:abc",
                episode_body="{}",
                source_description="jarvis-routing-history",
            )

        assert result is None
        mock_pub.assert_not_awaited()

    async def test_failopen_on_publish_error(self) -> None:
        """A raising publish edge is swallowed → returns None, never raises."""
        client = FleetMemoryClient(_enabled_config())

        with patch(_PUBLISH_EDGE, new=AsyncMock(side_effect=RuntimeError("nats down"))):
            result = await client.add_episode(
                name="jarvis_routing_history:abc",
                episode_body="{}",
                source_description="jarvis-routing-history",
            )

        assert result is None

    async def test_returns_none_when_publish_incomplete(self) -> None:
        """published=0 (e.g. oversized skip) → returns None."""
        client = FleetMemoryClient(_enabled_config())

        with patch(_PUBLISH_EDGE, new=AsyncMock(return_value=_summary(published=0, skipped=1))):
            result = await client.add_episode(
                name="jarvis_routing_history:abc",
                episode_body="{}",
                source_description="jarvis-routing-history",
            )

        assert result is None


@pytest.mark.skipif(not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed")
class TestPublisherFailFast:
    """The memory publisher connects with fail-fast settings (DDR-019).

    Regression guard for the live-proof finding: the default
    ``NATSConfig.max_reconnect_attempts=60`` caused a ~2-minute background
    retry-storm per fire-and-forget write against an unreachable / unauthorized
    broker. A one-shot fail-open publish must not retry.
    """

    def test_build_nats_client_disables_reconnect_retries(self) -> None:
        client = build_nats_client(_enabled_config())
        assert client._config.max_reconnect_attempts == 0
        assert client._config.connect_timeout <= 5.0

    def test_build_nats_client_reuses_config_creds_and_url(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            cfg = JarvisConfig(
                llama_swap_base_url="http://fake",
                nats_url="nats://broker.example:4222",
            )
        client = build_nats_client(cfg)
        assert client._config.url == "nats://broker.example:4222"
        assert client._config.creds_file is None  # nats_credentials_path unset


@pytest.mark.skipif(not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed")
class TestPublisherUserPasswordAuth:
    """``build_nats_client`` threads the optional user/password account pair
    (JARVIS_NATS_USER / JARVIS_NATS_PASSWORD) into ``NATSConfig`` — shared with
    the supervisor's connect — so creds need not live inline in ``nats_url``.

    Regression guard: a half-pair / blank / creds-file-coexistence config must
    NOT reach ``NATSConfig`` raw, because its ``auth_fields_are_consistent``
    validator raises on those combinations — and ``build_nats_client`` runs
    before ``publish_episodes``' try, so the raise would propagate into
    ``FleetMemoryClient``'s fail-open and silently drop EVERY routing-history
    write. The shared ``resolve_nats_user_password`` gate must absorb them all.
    """

    @staticmethod
    def _cfg(**overrides: object) -> JarvisConfig:
        with patch.dict("os.environ", {}, clear=True):
            return JarvisConfig(  # type: ignore[arg-type]
                llama_swap_base_url="http://fake",
                nats_url="nats://broker.example:4222",
                **overrides,
            )

    def test_threads_user_password_into_config(self) -> None:
        client = build_nats_client(self._cfg(nats_user="jarvis", nats_password="s3cr3t"))
        assert client._config.user == "jarvis"
        # NATSConfig stores the password as a SecretStr; unwrap to compare.
        assert client._config.password is not None
        assert client._config.password.get_secret_value() == "s3cr3t"
        # …and both reach nats-py's connect kwargs (the both-set gate).
        kwargs = client._config.to_connect_kwargs()
        assert kwargs["user"] == "jarvis"
        assert kwargs["password"] == "s3cr3t"

    def test_omits_auth_when_user_password_unset(self) -> None:
        client = build_nats_client(_enabled_config())
        assert client._config.user is None
        assert client._config.password is None
        kwargs = client._config.to_connect_kwargs()
        assert "user" not in kwargs
        assert "password" not in kwargs

    def test_lone_user_does_not_raise_and_omits_auth(self) -> None:
        # NATSConfig raises "user and password must be provided together" on a
        # half-pair; the gate must drop it so build_nats_client never raises.
        client = build_nats_client(self._cfg(nats_user="jarvis"))
        assert client._config.user is None
        assert client._config.password is None

    def test_lone_password_does_not_raise_and_omits_auth(self) -> None:
        client = build_nats_client(self._cfg(nats_password="s3cr3t"))
        assert client._config.user is None
        assert client._config.password is None

    def test_blank_user_password_omitted(self) -> None:
        # Blank env placeholders (JARVIS_NATS_USER= / JARVIS_NATS_PASSWORD=)
        # coerce to "" / SecretStr("") — non-None — and must NOT clobber auth.
        client = build_nats_client(self._cfg(nats_user="", nats_password=""))
        assert client._config.user is None
        assert client._config.password is None

    def test_creds_file_takes_precedence_over_user_password(self) -> None:
        # NATSConfig treats password auth + creds_file as mutually exclusive;
        # the .creds file wins and the user/password pair is dropped (no raise).
        client = build_nats_client(
            self._cfg(
                nats_credentials_path="/etc/jarvis/nats.creds",
                nats_user="jarvis",
                nats_password="s3cr3t",
            )
        )
        assert client._config.creds_file == "/etc/jarvis/nats.creds"
        assert client._config.user is None
        assert client._config.password is None


class TestFleetMemoryClientInterface:
    """Interface parity with the routing-history writer's expectations."""

    def test_enabled_reflects_config(self) -> None:
        assert FleetMemoryClient(_enabled_config()).enabled is True
        with patch.dict("os.environ", {}, clear=True):
            disabled = JarvisConfig(llama_swap_base_url="http://fake")
        assert FleetMemoryClient(disabled).enabled is False

    async def test_close_is_noop(self) -> None:
        """``close()`` is an async no-op (parity with the retired aclose)."""
        assert await FleetMemoryClient(_enabled_config()).close() is None


# ===========================================================================
# Live round-trip — operator post-merge proof (skips when the store is off)
# ===========================================================================


@pytest.mark.live
@pytest.mark.skipif(not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed")
class TestFleetMemoryLiveRoundTrip:
    """Publishes a real routing-history episode to a live fleet-memory store."""

    async def test_routing_history_publish_live(self) -> None:
        """With the store ENABLED, a real ``add_episode`` publishes an episode.

        Jarvis is write-only, so the proof is a successful publish (the natural
        key is returned). Skips cleanly when disabled — the FEAT-MEM-08-style
        operator acceptance gate. Run with:

            JARVIS_FLEET_MEMORY_ENABLED=true \\
              .venv/bin/python -m pytest -m live tests/test_fleet_memory_client.py -v
        """
        config = JarvisConfig()  # read the operator's live env (do NOT clear)
        if not config.fleet_memory_enabled:
            pytest.skip("fleet-memory store not enabled (JARVIS_FLEET_MEMORY_ENABLED unset)")

        client = FleetMemoryClient(config)
        result: Any = await client.add_episode(
            name="jarvis_routing_history:live-roundtrip-probe",
            episode_body='{"decision_id": "live-roundtrip-probe", "outcome_type": "success"}',
            source_description="jarvis-routing-history",
            reference_time=datetime.now(UTC),
        )
        assert result is not None, (
            "expected a natural key from a live publish — check NATS is reachable "
            "and the fleet-memory relay is running for project=jarvis"
        )
