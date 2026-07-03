"""Unit tests for the Jarvis fleet-memory group mapping.

Covers ``resolve`` (group_id → GroupMapping) and ``group_for_source``
(writer source_description → group_id) — the Rosetta stone the routing-history
writer's two write kinds resolve through on the fleet-memory write path.
"""

from __future__ import annotations

from jarvis.infrastructure.fleet_memory.mapping import (
    GROUP_ID_MAP,
    GroupMapping,
    group_for_source,
    resolve,
)


class TestResolve:
    """``resolve`` maps the two routing-history groups; else ``None``."""

    def test_routing_history_maps_to_document_dispatch(self) -> None:
        mapping = resolve("routing_history")
        assert mapping is not None
        assert mapping.project == "jarvis"
        assert mapping.payload_type == "document"
        assert mapping.domain_tags == ["routing", "dispatch"]
        assert mapping.disposition == "migrate"

    def test_routing_history_edge_maps_to_document_stage(self) -> None:
        mapping = resolve("routing_history_edge")
        assert mapping is not None
        assert mapping.payload_type == "document"
        assert mapping.domain_tags == ["routing", "stage"]
        assert mapping.disposition == "migrate"

    def test_normalizes_hyphens_and_case(self) -> None:
        """Hyphenated / mixed-case group ids normalise to the underscore form."""
        assert resolve("Routing-History") is resolve("routing_history")
        assert resolve("ROUTING_HISTORY_EDGE") is resolve("routing_history_edge")

    def test_unknown_group_returns_none(self) -> None:
        assert resolve("task_outcomes") is None
        assert resolve("nonsense") is None

    def test_all_mapped_groups_are_migrate_documents(self) -> None:
        """Every declared group publishes (no retired groups in Jarvis)."""
        for group, mapping in GROUP_ID_MAP.items():
            assert isinstance(mapping, GroupMapping), group
            assert mapping.disposition == "migrate", group
            assert mapping.payload_type == "document", group
            assert mapping.project == "jarvis", group


class TestGroupForSource:
    """``group_for_source`` maps the writer's source_description label."""

    def test_entry_source_maps_to_routing_history(self) -> None:
        assert group_for_source("jarvis-routing-history") == "routing_history"

    def test_edge_source_maps_to_routing_history_edge(self) -> None:
        assert group_for_source("jarvis-routing-history-edge") == "routing_history_edge"

    def test_unknown_source_defaults_to_routing_history(self) -> None:
        """A stray label routes to the entry group rather than being dropped."""
        assert group_for_source("something-else") == "routing_history"

    def test_derived_group_always_resolves(self) -> None:
        """Every group_for_source output is a resolvable, migrate mapping."""
        for source in (
            "jarvis-routing-history",
            "jarvis-routing-history-edge",
            "unrecognised",
        ):
            mapping = resolve(group_for_source(source))
            assert mapping is not None
            assert mapping.disposition == "migrate"
