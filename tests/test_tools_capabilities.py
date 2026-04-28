"""Unit tests for capability tools + snapshot isolation (TASK-J002-020).

Focused, self-contained pytest suite that exercises the stub registry loader
and the three capability ``@tool`` functions documented in
``DM-stub-registry.md`` and ``API-tools.md`` §2:

* :func:`load_stub_registry` — loads + validates the canonical Phase 2 YAML.
* :func:`list_available_capabilities` — returns JSON snapshot of registry.
* :func:`capabilities_refresh` — Phase 2 stub OK acknowledgement.
* :func:`capabilities_subscribe_updates` — Phase 2 stub OK acknowledgement.

Acceptance criteria covered:

* AC-001: ``tests/test_tools_capabilities.py`` covers — stub YAML loads into
  4 descriptors; ``list_available_capabilities`` returns JSON of 4 descriptors;
  refresh/subscribe OK acks; startup-fatal on missing YAML; startup-fatal on
  malformed YAML (invalid uppercase ``agent_id``); snapshot isolation via
  ``concurrent.futures`` (both calls succeed, snapshot unchanged).
* AC-002: Byte-equal check on the ``OK:`` strings from refresh and subscribe
  (identical to the constants documented in API-tools.md §2.2 / §2.3).
* AC-003: Duplicate ``agent_id`` YAML is rejected by the loader with a
  ``ValueError``.
"""

from __future__ import annotations

import concurrent.futures
import json
import threading
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from jarvis.tools import capabilities as capabilities_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    capabilities_refresh,
    capabilities_subscribe_updates,
    list_available_capabilities,
    load_stub_registry,
)

# ---------------------------------------------------------------------------
# Path to the canonical Phase 2 stub registry. The loader is exercised
# against this file directly so a real on-disk round trip is part of the
# suite (and a regression in either capabilities.py or the YAML asset is
# caught here, not only at startup).
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STUB_YAML_PATH = (
    PROJECT_ROOT / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
)

EXPECTED_AGENT_IDS: list[str] = [
    "architect-agent",
    "product-owner-agent",
    "ideation-agent",
    "forge",
]

# Exact ``OK:`` strings the reasoning model relies on. Kept verbatim here so
# any drift in the production constants (or in API-tools.md §3-§5) fails
# this test rather than silently propagating to the model.
#
# FEAT-JARVIS-004 (TASK-J004-012) swapped the refresh OK shape from the
# Phase 2 acknowledgement to the KV-backed string; subscribe OK is
# preserved byte-identical across the swap.
EXPECTED_REFRESH_OK = "OK: refresh queued — registry resynchronised"
EXPECTED_SUBSCRIBE_OK = "OK: subscribed (stubbed in Phase 2 — no live updates)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _write_yaml(path: Path, data: Any) -> Path:
    """Dump ``data`` to ``path`` as YAML and return the path."""
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


class _ListBackedRegistry:
    """Test adapter exposing a ``list[CapabilityDescriptor]`` through the
    FEAT-JARVIS-004 ``CapabilitiesRegistry`` Protocol surface.

    The Protocol's contract:
      - ``snapshot()`` (sync) returns a fresh ``list`` copy.
      - ``refresh()`` (async) re-reads the source of truth.
      - ``subscribe_updates(callback)`` (async) attaches a watcher.
      - ``close()`` (async) releases handles.
    """

    def __init__(self, descriptors: list[CapabilityDescriptor]) -> None:
        self._descriptors = descriptors

    def snapshot(self) -> list[CapabilityDescriptor]:
        return list(self._descriptors)

    async def refresh(self) -> None:  # no-op for the canonical-stub fixture
        return None

    async def subscribe_updates(self, callback: object) -> None:
        return None

    async def close(self) -> None:
        return None


@pytest.fixture()
def bound_canonical_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind the canonical Phase 2 stub registry into the module under test.

    The fixture mirrors what ``assemble_tool_list`` does at supervisor build
    time: it wraps a freshly-loaded ``list[CapabilityDescriptor]`` in a
    Protocol-compatible adapter and assigns it to the module-level
    ``_capability_registry`` attribute. The original registry binding is
    restored on teardown so this fixture composes cleanly with other tests
    that mutate the same global.
    """
    saved = capabilities_module._capability_registry
    saved_subscribed = capabilities_module._subscribe_invoked
    fresh = load_stub_registry(STUB_YAML_PATH)
    capabilities_module._capability_registry = _ListBackedRegistry(fresh)
    capabilities_module._subscribe_invoked = False
    try:
        yield fresh
    finally:
        capabilities_module._capability_registry = saved
        capabilities_module._subscribe_invoked = saved_subscribed


# ---------------------------------------------------------------------------
# AC-001 / AC-003 — loader contract
# ---------------------------------------------------------------------------


class TestStubYamlLoadsFourDescriptors:
    """AC-001 — the canonical stub YAML loads into exactly four descriptors."""

    def test_canonical_yaml_loads_into_four_descriptors(self) -> None:
        descriptors = load_stub_registry(STUB_YAML_PATH)

        assert isinstance(descriptors, list)
        assert len(descriptors) == 4
        assert all(
            isinstance(descriptor, CapabilityDescriptor)
            for descriptor in descriptors
        )

    def test_canonical_yaml_preserves_documented_agent_ids(self) -> None:
        descriptors = load_stub_registry(STUB_YAML_PATH)

        assert [d.agent_id for d in descriptors] == EXPECTED_AGENT_IDS


class TestStartupFatalOnMissingYaml:
    """AC-001 — a missing YAML file is startup-fatal (FileNotFoundError)."""

    def test_missing_path_raises_file_not_found_error(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does-not-exist.yaml"

        with pytest.raises(FileNotFoundError):
            load_stub_registry(missing)

    def test_file_not_found_error_names_offending_path(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "missing-registry.yaml"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_stub_registry(missing)

        assert str(missing) in str(exc_info.value)


class TestStartupFatalOnMalformedYaml:
    """AC-001 — malformed YAML (uppercase agent_id) is startup-fatal."""

    def test_uppercase_agent_id_raises_validation_error(
        self, tmp_path: Path
    ) -> None:
        path = _write_yaml(
            tmp_path / "malformed.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    # agent_id MUST match ``^[a-z][a-z0-9-]*$`` — uppercase
                    # ``Architect`` deliberately violates this contract so
                    # we can assert the loader fails fast at startup.
                    {
                        "agent_id": "Architect",
                        "role": "Architect",
                        "description": "Designs systems.",
                    },
                ],
            },
        )

        with pytest.raises(ValidationError):
            load_stub_registry(path)


class TestDuplicateAgentIdRejected:
    """AC-003 — duplicate ``agent_id`` YAML is rejected by the loader."""

    def test_duplicate_agent_id_raises_value_error_naming_offender(
        self, tmp_path: Path
    ) -> None:
        path = _write_yaml(
            tmp_path / "duplicate.yaml",
            {
                "version": "1.0",
                "capabilities": [
                    {"agent_id": "twin", "role": "R", "description": "d"},
                    {"agent_id": "other", "role": "R", "description": "d"},
                    {"agent_id": "twin", "role": "R", "description": "d"},
                ],
            },
        )

        with pytest.raises(ValueError) as exc_info:
            load_stub_registry(path)

        assert "twin" in str(exc_info.value)


# ---------------------------------------------------------------------------
# AC-001 — list_available_capabilities returns JSON of 4 descriptors
# ---------------------------------------------------------------------------


class TestListAvailableCapabilitiesReturnsFourDescriptors:
    """AC-001 — the catalogue tool surfaces all four canonical descriptors."""

    def test_returns_json_array_of_four_descriptors(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        result = list_available_capabilities.invoke({})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 4
        assert [entry["agent_id"] for entry in parsed] == EXPECTED_AGENT_IDS

    def test_payload_shape_matches_descriptor_dump(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        parsed = json.loads(list_available_capabilities.invoke({}))

        for entry, descriptor in zip(
            parsed, bound_canonical_registry, strict=True
        ):
            assert entry["agent_id"] == descriptor.agent_id
            assert entry["role"] == descriptor.role
            assert entry["trust_tier"] == descriptor.trust_tier
            assert isinstance(entry["capability_list"], list)


# ---------------------------------------------------------------------------
# AC-001 / AC-002 — refresh and subscribe return byte-exact OK strings
# ---------------------------------------------------------------------------


class TestRefreshAndSubscribeOkAcks:
    """AC-001 / AC-002 — refresh and subscribe return byte-exact OK strings.

    All four refresh / subscribe tests now require a wired
    ``_capability_registry`` because FEAT-JARVIS-004 routes the tool bodies
    through the Protocol surface. The shared ``bound_canonical_registry``
    fixture supplies one with the canonical Phase 2 stub descriptors.
    """

    def test_refresh_returns_byte_exact_ok_string(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        result = capabilities_refresh.invoke({})

        # Byte-equal: a substring or prefix match would let drift slip
        # past — the model relies on the literal contract surface.
        assert result == EXPECTED_REFRESH_OK

    def test_subscribe_returns_byte_exact_ok_string(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        result = capabilities_subscribe_updates.invoke({})

        assert result == EXPECTED_SUBSCRIBE_OK

    def test_refresh_ok_string_is_idempotent(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        first = capabilities_refresh.invoke({})
        second = capabilities_refresh.invoke({})

        assert first == second == EXPECTED_REFRESH_OK

    def test_subscribe_ok_string_is_idempotent(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        first = capabilities_subscribe_updates.invoke({})
        second = capabilities_subscribe_updates.invoke({})

        assert first == second == EXPECTED_SUBSCRIBE_OK

    def test_module_constants_match_expected_ok_strings(self) -> None:
        """A drift in the module-level subscribe constant is caught here too.

        The Phase 2 ``_REFRESH_OK_MESSAGE`` constant was deleted in
        FEAT-JARVIS-004 (TASK-J004-012); the new OK / DEGRADED return
        strings live inline in the tool body.
        """
        assert not hasattr(capabilities_module, "_REFRESH_OK_MESSAGE")
        assert capabilities_module._SUBSCRIBE_OK_MESSAGE == EXPECTED_SUBSCRIBE_OK


# ---------------------------------------------------------------------------
# AC-001 — snapshot isolation under concurrent list + refresh
# ---------------------------------------------------------------------------


class TestSnapshotIsolationUnderConcurrentRefresh:
    """AC-001 — concurrent list + refresh both succeed; snapshot unchanged.

    ASSUM-006: ``list_available_capabilities`` captures a *local* reference
    to ``_capability_registry`` at call start so a concurrent rebind (here,
    a ``capabilities_refresh`` invocation in another thread) cannot mutate
    the JSON the in-flight call is about to render.
    """

    def test_concurrent_list_and_refresh_both_succeed(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        barrier = threading.Barrier(2)

        def run_list() -> str:
            barrier.wait(timeout=5)
            return list_available_capabilities.invoke({})

        def run_refresh() -> str:
            barrier.wait(timeout=5)
            return capabilities_refresh.invoke({})

        # ``concurrent.futures`` per the AC text — the barrier ensures the
        # two callables really overlap rather than serialising on the
        # executor's submit ordering.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list_future = pool.submit(run_list)
            refresh_future = pool.submit(run_refresh)
            list_result = list_future.result(timeout=10)
            refresh_result = refresh_future.result(timeout=10)

        # Both calls must have returned successfully — no exceptions
        # bubbling out, no ERROR:-prefixed degraded responses.
        assert refresh_result == EXPECTED_REFRESH_OK
        assert isinstance(list_result, str)
        assert not list_result.startswith("ERROR:")

        # The snapshot returned by list_available_capabilities is still
        # the four canonical descriptors (registry unchanged).
        payload = json.loads(list_result)
        observed_ids = [entry["agent_id"] for entry in payload]
        assert observed_ids == EXPECTED_AGENT_IDS

        # And the underlying descriptor contents are unchanged — refresh
        # against the canonical-stub adapter is a no-op (it does not
        # rebuild the descriptor list).
        registry = capabilities_module._capability_registry
        assert registry is not None
        assert registry.snapshot() == bound_canonical_registry

    def test_repeated_concurrent_pairs_keep_snapshot_stable(
        self, bound_canonical_registry: list[CapabilityDescriptor]
    ) -> None:
        """Repeating the race many times must not corrupt the snapshot."""

        def list_call(barrier: threading.Barrier) -> str:
            barrier.wait(timeout=5)
            return list_available_capabilities.invoke({})

        def refresh_call(barrier: threading.Barrier) -> str:
            barrier.wait(timeout=5)
            return capabilities_refresh.invoke({})

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for _ in range(8):
                barrier = threading.Barrier(2)
                list_future = pool.submit(list_call, barrier)
                refresh_future = pool.submit(refresh_call, barrier)

                list_result = list_future.result(timeout=10)
                refresh_result = refresh_future.result(timeout=10)

                assert refresh_result == EXPECTED_REFRESH_OK
                payload = json.loads(list_result)
                assert [entry["agent_id"] for entry in payload] == (
                    EXPECTED_AGENT_IDS
                )

        # The registry's descriptor contents are unchanged after the
        # repeated race — ASSUM-006 invariant holds across iterations.
        registry = capabilities_module._capability_registry
        assert registry is not None
        assert registry.snapshot() == bound_canonical_registry
