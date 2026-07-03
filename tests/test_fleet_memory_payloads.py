"""Unit tests for Jarvis fleet-memory episode construction.

Covers ``sanitize_identifier`` and ``build_memory_episode`` — the translation
from a routing-history record (name + JSON body + reference time) into a typed
``MemoryEpisodeV1`` on the relay's prose/markdown path. These assert the
outbound episode shape without any live store (no publish).
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime

import pytest

from jarvis.infrastructure.fleet_memory.mapping import resolve
from jarvis.infrastructure.fleet_memory.payloads import (
    build_memory_episode,
    sanitize_identifier,
)

# The write path builds a ``nats_core.events.MemoryEpisodeV1``; skip cleanly if
# the memory extra is absent from a minimal env.
_HAS_NATS_CORE = importlib.util.find_spec("nats_core") is not None
pytestmark = pytest.mark.skipif(
    not _HAS_NATS_CORE, reason="nats_core (memory write dep) not installed"
)


class TestSanitizeIdentifier:
    """Identifiers are coerced to fleet-memory's ``^[a-zA-Z0-9_]+$`` contract."""

    def test_colons_and_hyphens_become_underscores(self) -> None:
        result = sanitize_identifier(
            "jarvis_routing_history:11111111-2222-4333-8444-555555555555"
        )
        assert result == "jarvis_routing_history_11111111_2222_4333_8444_555555555555"
        assert all(c.isalnum() or c == "_" for c in result)

    def test_empty_becomes_unknown(self) -> None:
        assert sanitize_identifier("") == "unknown"

    def test_leading_trailing_separators_stripped(self) -> None:
        assert sanitize_identifier("::x::") == "x"


class TestBuildMemoryEpisode:
    """``build_memory_episode`` emits a prose-path ``document`` episode."""

    def _episode(self, *, source: str = "jarvis-routing-history", project: str = "jarvis"):
        group = "routing_history_edge" if source.endswith("-edge") else "routing_history"
        mapping = resolve(group)
        assert mapping is not None
        return build_memory_episode(
            mapping,
            name="jarvis_routing_history:11111111-2222-4333-8444-555555555555",
            episode_body='{"decision_id": "abc", "outcome_type": "success"}',
            source=source,
            project=project,
            occurred_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )

    def test_prose_path_document_shape(self) -> None:
        ep = self._episode()
        assert ep is not None
        assert ep.project_id == "jarvis"
        assert ep.episode_type == "document"
        assert ep.content_format == "markdown"  # → relay prose/chunk path
        assert ep.payload_type is None
        assert ep.source == "jarvis-routing-history"

    def test_body_is_the_json_trace_verbatim(self) -> None:
        ep = self._episode()
        assert ep.body == '{"decision_id": "abc", "outcome_type": "success"}'

    def test_episode_id_is_deterministic_natural_key(self) -> None:
        """episode_id == ``document:{project}:{sanitised name}`` (JetStream dedup)."""
        ep = self._episode()
        assert ep.episode_id == (
            "document:jarvis:jarvis_routing_history_11111111_2222_4333_8444_555555555555"
        )
        # Deterministic: same inputs → same key (idempotent replay).
        assert self._episode().episode_id == ep.episode_id

    def test_reference_time_becomes_occurred_at(self) -> None:
        ep = self._episode()
        assert ep.occurred_at == datetime(2026, 7, 3, 12, 0, tzinfo=UTC)

    def test_domain_tags_carried_as_ingest_hint(self) -> None:
        assert self._episode().ingest_hints == {"domain_tags": ["routing", "dispatch"]}
        assert self._episode(source="jarvis-routing-history-edge").ingest_hints == {
            "domain_tags": ["routing", "stage"]
        }

    def test_explicit_project_overrides_mapping_default(self) -> None:
        ep = self._episode(project="jarvis-staging")
        assert ep.project_id == "jarvis-staging"
        assert ep.episode_id.startswith("document:jarvis-staging:")
