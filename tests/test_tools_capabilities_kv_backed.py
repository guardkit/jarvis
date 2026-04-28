"""KV-backed capability tools — TASK-J004-012 acceptance tests.

This suite covers the FEAT-JARVIS-004 swap of the three capability tools in
:mod:`jarvis.tools.capabilities` from Phase 2 stubs to KV-backed bodies.

Acceptance criteria covered:

* AC-001 — ``list_available_capabilities`` body reads via
  ``_capability_registry.snapshot()`` only — never branches on Live vs Stub
  and never directly touches NATS or the stub YAML.
* AC-002 — ``capabilities_refresh`` returns the success string on the
  no-exception path; the DEGRADED string when ``.refresh()`` raises a
  transport-related exception.
* AC-003 — ``capabilities_subscribe_updates`` is idempotent: calling more
  than once during a session returns the same OK string and does not
  double-subscribe (the registry's ``subscribe_updates`` is invoked at most
  once per process lifetime).
* AC-004 — Phase 2 stub paragraphs deleted from all three docstrings;
  ``_REFRESH_OK_MESSAGE`` constant deleted.
* AC-005 — Tool signatures + docstring shape are byte-identical modulo the
  documented deltas (Phase 2 paragraphs replaced by API-tools.md §3-§5
  return-shape lines).
* Seam test — verifies the CAPABILITIES_REGISTRY_PROTOCOL contract from
  TASK-J004-009: the tools speak only the Protocol surface
  (``snapshot/refresh/subscribe_updates/close``).
"""

from __future__ import annotations

import inspect
import json
import pathlib
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools import capabilities as caps_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
    capabilities_refresh,
    capabilities_subscribe_updates,
    list_available_capabilities,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

EXPECTED_REFRESH_OK = "OK: refresh queued — registry resynchronised"
EXPECTED_REFRESH_DEGRADED = (
    "DEGRADED: transport_unavailable — NATS connection failed"
)
EXPECTED_SUBSCRIBE_OK = "OK: subscribed (stubbed in Phase 2 — no live updates)"


def _sample_descriptors() -> list[CapabilityDescriptor]:
    """Return a small, realistic descriptor list used by snapshot tests."""
    return [
        CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description="Generates C4 architecture diagrams and ADRs.",
            cost_signal="moderate",
            latency_signal="5-30s",
            trust_tier="specialist",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="run_architecture_session",
                    description="Drive a /system-arch session.",
                    risk_level="read_only",
                ),
            ],
        ),
        CapabilityDescriptor(
            agent_id="forge",
            role="Forge",
            description="Builds features end to end.",
            cost_signal="high",
            latency_signal="hours",
            trust_tier="core",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="build_feature",
                    description="Queue a Forge build.",
                    risk_level="mutating",
                ),
            ],
        ),
    ]


@pytest.fixture()
def reset_module_state() -> Generator[None, None, None]:
    """Reset the module-level swap-point + idempotency flag between tests."""
    saved_registry = caps_module._capability_registry
    saved_subscribed = caps_module._subscribe_invoked
    caps_module._capability_registry = None
    caps_module._subscribe_invoked = False
    try:
        yield
    finally:
        caps_module._capability_registry = saved_registry
        caps_module._subscribe_invoked = saved_subscribed


@pytest.fixture()
def mock_registry(reset_module_state: None) -> MagicMock:
    """Bind a fresh MagicMock registry into the capabilities module.

    The mock satisfies the CapabilitiesRegistry Protocol surface:
      - ``snapshot()`` returns a list copy (sync).
      - ``refresh()`` is an :class:`AsyncMock` returning ``None``.
      - ``subscribe_updates(cb)`` is an :class:`AsyncMock` returning ``None``.
      - ``close()`` is an :class:`AsyncMock`.

    Per-test customisation overrides ``side_effect`` / ``return_value``.
    """
    mock = MagicMock(name="CapabilitiesRegistry")
    mock.snapshot = MagicMock(return_value=_sample_descriptors())
    mock.refresh = AsyncMock(return_value=None)
    mock.subscribe_updates = AsyncMock(return_value=None)
    mock.close = AsyncMock(return_value=None)
    caps_module._capability_registry = mock
    return mock


# ---------------------------------------------------------------------------
# AC-001 — list_available_capabilities reads via Protocol .snapshot() only
# ---------------------------------------------------------------------------


class TestAC001ListReadsViaSnapshotOnly:
    """``list_available_capabilities`` consumes only ``registry.snapshot()``."""

    def test_calls_registry_snapshot_exactly_once(
        self, mock_registry: MagicMock
    ) -> None:
        list_available_capabilities.invoke({})

        mock_registry.snapshot.assert_called_once_with()

    def test_does_not_invoke_other_protocol_methods(
        self, mock_registry: MagicMock
    ) -> None:
        list_available_capabilities.invoke({})

        mock_registry.refresh.assert_not_called()
        mock_registry.subscribe_updates.assert_not_called()
        mock_registry.close.assert_not_called()

    def test_returns_json_serialisation_of_snapshot(
        self, mock_registry: MagicMock
    ) -> None:
        result = list_available_capabilities.invoke({})

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert [entry["agent_id"] for entry in parsed] == [
            "architect-agent",
            "forge",
        ]

    def test_empty_snapshot_returns_empty_json_array(
        self, mock_registry: MagicMock
    ) -> None:
        mock_registry.snapshot.return_value = []

        assert list_available_capabilities.invoke({}) == "[]"

    def test_unconfigured_registry_returns_structured_error(
        self, reset_module_state: None
    ) -> None:
        """When ``_capability_registry`` is ``None`` (no assemble_tool_list
        has run), the tool must surface a structured ERROR string rather
        than crash."""
        # ``reset_module_state`` already nulls the registry handle.
        result = list_available_capabilities.invoke({})

        assert isinstance(result, str)
        assert result.startswith("ERROR: registry_unavailable")

    def test_snapshot_failure_returns_structured_error(
        self, mock_registry: MagicMock
    ) -> None:
        mock_registry.snapshot.side_effect = RuntimeError(
            "synthetic registry failure"
        )

        result = list_available_capabilities.invoke({})

        assert result.startswith("ERROR: registry_unavailable")
        assert "synthetic registry failure" in result

    def test_does_not_import_yaml_or_nats_in_call_path(
        self, mock_registry: MagicMock
    ) -> None:
        """Belt-and-braces: ensure the body does not read the stub YAML.

        The mock registry's ``snapshot`` returns a list directly — if the
        tool secretly fell back to reading
        ``src/jarvis/config/stub_capabilities.yaml`` we would observe four
        descriptors here rather than the two from the mock.
        """
        result = list_available_capabilities.invoke({})

        parsed = json.loads(result)
        assert len(parsed) == 2  # mock has 2; YAML has 4 (architect, po, …)


# ---------------------------------------------------------------------------
# AC-002 — capabilities_refresh — OK / DEGRADED return strings
# ---------------------------------------------------------------------------


class TestAC002CapabilitiesRefresh:
    """``capabilities_refresh`` drives ``.refresh()`` and renders OK/DEGRADED."""

    def test_returns_ok_string_on_success(
        self, mock_registry: MagicMock
    ) -> None:
        result = capabilities_refresh.invoke({})

        assert result == EXPECTED_REFRESH_OK

    def test_calls_registry_refresh_exactly_once(
        self, mock_registry: MagicMock
    ) -> None:
        capabilities_refresh.invoke({})

        mock_registry.refresh.assert_awaited_once_with()

    def test_returns_degraded_string_on_nats_connection_error(
        self, mock_registry: MagicMock
    ) -> None:
        mock_registry.refresh.side_effect = NATSConnectionError(
            "synthetic transport failure"
        )

        result = capabilities_refresh.invoke({})

        assert result == EXPECTED_REFRESH_DEGRADED

    def test_returns_degraded_string_on_generic_transport_failure(
        self, mock_registry: MagicMock
    ) -> None:
        """Any exception raised by ``.refresh()`` surfaces as DEGRADED.

        ``.refresh()`` only fails when the underlying KV read fails; from
        the tool's perspective every such failure is a transport
        degradation per DDR-021.
        """
        mock_registry.refresh.side_effect = ConnectionError("broker dropped")

        result = capabilities_refresh.invoke({})

        assert result == EXPECTED_REFRESH_DEGRADED

    def test_unconfigured_registry_returns_degraded(
        self, reset_module_state: None
    ) -> None:
        result = capabilities_refresh.invoke({})

        assert result == EXPECTED_REFRESH_DEGRADED

    def test_never_raises_on_unexpected_failure(
        self, mock_registry: MagicMock
    ) -> None:
        mock_registry.refresh.side_effect = RuntimeError("boom")

        # ADR-ARCH-021: tools must not raise across the boundary.
        try:
            result = capabilities_refresh.invoke({})
        except Exception as exc:  # pragma: no cover - regression guard
            pytest.fail(f"capabilities_refresh raised {exc!r}")

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# AC-003 — capabilities_subscribe_updates idempotency
# ---------------------------------------------------------------------------


class TestAC003SubscribeUpdatesIdempotent:
    """``capabilities_subscribe_updates`` is idempotent within a session."""

    def test_first_call_invokes_subscribe_on_registry(
        self, mock_registry: MagicMock
    ) -> None:
        result = capabilities_subscribe_updates.invoke({})

        mock_registry.subscribe_updates.assert_awaited_once()
        assert result == EXPECTED_SUBSCRIBE_OK

    def test_second_call_returns_same_ok_without_re_subscribing(
        self, mock_registry: MagicMock
    ) -> None:
        first = capabilities_subscribe_updates.invoke({})
        second = capabilities_subscribe_updates.invoke({})

        assert first == second == EXPECTED_SUBSCRIBE_OK
        # The registry's subscribe_updates was called exactly once.
        assert mock_registry.subscribe_updates.await_count == 1

    def test_repeated_calls_remain_idempotent(
        self, mock_registry: MagicMock
    ) -> None:
        results = [capabilities_subscribe_updates.invoke({}) for _ in range(5)]

        assert all(r == EXPECTED_SUBSCRIBE_OK for r in results)
        assert mock_registry.subscribe_updates.await_count == 1

    def test_unconfigured_registry_returns_structured_error(
        self, reset_module_state: None
    ) -> None:
        result = capabilities_subscribe_updates.invoke({})

        assert result.startswith("ERROR: registry_unavailable")

    def test_never_raises_on_subscribe_failure(
        self, mock_registry: MagicMock
    ) -> None:
        mock_registry.subscribe_updates.side_effect = RuntimeError("boom")

        try:
            result = capabilities_subscribe_updates.invoke({})
        except Exception as exc:  # pragma: no cover - regression guard
            pytest.fail(f"capabilities_subscribe_updates raised {exc!r}")

        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# AC-004 — Phase 2 paragraphs + ``_REFRESH_OK_MESSAGE`` constant deleted
# ---------------------------------------------------------------------------


class TestAC004Phase2VestigesRemoved:
    """The Phase 2 stub paragraphs and the ``_REFRESH_OK_MESSAGE`` constant
    must not survive in the FEAT-JARVIS-004 module."""

    def test_refresh_ok_message_constant_deleted(self) -> None:
        assert not hasattr(caps_module, "_REFRESH_OK_MESSAGE"), (
            "task TASK-J004-012 deletes _REFRESH_OK_MESSAGE; module still has it"
        )

    def test_list_available_capabilities_docstring_omits_phase2_paragraph(
        self,
    ) -> None:
        doc = list_available_capabilities.func.__doc__ or ""
        assert "in-memory stub registry" not in doc, (
            "Phase 2 stub paragraph must be deleted from list "
            "docstring per API-tools.md §3"
        )
        # The new latency line replaces the Phase 2 latency line.
        assert "<30ms (cached live registry" in doc
        assert "stub fallback" in doc

    def test_capabilities_refresh_docstring_omits_phase2_paragraph(self) -> None:
        doc = capabilities_refresh.func.__doc__ or ""
        assert "STUB in Phase 2" not in doc, (
            "Phase 2 stub paragraph must be deleted from capabilities_refresh "
            "docstring per API-tools.md §4"
        )
        # The new return-shape line is documented.
        assert "OK: refresh queued — registry resynchronised" in doc
        assert "DEGRADED: transport_unavailable — NATS connection failed" in doc

    def test_capabilities_subscribe_updates_docstring_omits_phase2_paragraph(
        self,
    ) -> None:
        doc = capabilities_subscribe_updates.func.__doc__ or ""
        assert "STUB in Phase 2" not in doc, (
            "Phase 2 stub paragraph must be deleted from "
            "capabilities_subscribe_updates docstring per API-tools.md §5"
        )
        # The new behavioural line names the watcher + idempotency.
        assert "NATS KV watcher" in doc
        assert "Idempotent" in doc


# ---------------------------------------------------------------------------
# AC-005 — Tool signatures unchanged
# ---------------------------------------------------------------------------


class TestAC005SignaturesUnchanged:
    """All three tools preserve their FEAT-JARVIS-002 signatures."""

    @pytest.mark.parametrize(
        "tool_obj",
        [
            list_available_capabilities,
            capabilities_refresh,
            capabilities_subscribe_updates,
        ],
    )
    def test_no_positional_or_keyword_arguments(self, tool_obj: Any) -> None:
        signature = inspect.signature(tool_obj.func)
        assert list(signature.parameters) == []
        # ``from __future__ import annotations`` defers annotations as
        # strings, so accept either the str type itself or the string
        # literal ``"str"``.
        assert signature.return_annotation in (str, "str")

    @pytest.mark.parametrize(
        ("tool_obj", "expected_name"),
        [
            (list_available_capabilities, "list_available_capabilities"),
            (capabilities_refresh, "capabilities_refresh"),
            (capabilities_subscribe_updates, "capabilities_subscribe_updates"),
        ],
    )
    def test_tool_name_unchanged(
        self, tool_obj: Any, expected_name: str
    ) -> None:
        assert getattr(tool_obj, "name", None) == expected_name


# ---------------------------------------------------------------------------
# Seam test — CAPABILITIES_REGISTRY_PROTOCOL contract (from task spec)
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("CAPABILITIES_REGISTRY_PROTOCOL")
class TestSeamCapabilitiesRegistryProtocol:
    """Verify CAPABILITIES_REGISTRY_PROTOCOL contract from TASK-J004-009."""

    def test_list_available_capabilities_reads_via_protocol_only(
        self, reset_module_state: None
    ) -> None:
        """The tool consumes only the Protocol surface.

        Contract: CapabilitiesRegistry Protocol —
        snapshot/refresh/subscribe_updates/close.
        Producer: TASK-J004-009; consumer: this task.
        """
        registry = MagicMock()
        registry.snapshot.return_value = []
        caps_module._capability_registry = registry

        result = list_available_capabilities.invoke({})

        registry.snapshot.assert_called_once()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Module sanity — capabilities.py is still a leaf in the import graph
# (ADR-ARCH-002). The TYPE_CHECKING-only ``CapabilitiesRegistry`` import
# from jarvis.infrastructure.* must NOT escape into runtime imports.
# ---------------------------------------------------------------------------


class TestModuleLeafInvariant:
    """capabilities.py must not import from jarvis.infrastructure / jarvis.cli /
    jarvis.agents at runtime — the Protocol type is referenced only under
    ``TYPE_CHECKING``."""

    FORBIDDEN_PREFIXES = (
        "jarvis.agents",
        "jarvis.infrastructure",
        "jarvis.cli",
    )

    def _module_path(self) -> pathlib.Path:
        return (
            pathlib.Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "tools"
            / "capabilities.py"
        )

    def test_no_runtime_imports_from_forbidden_packages(self) -> None:
        import ast

        tree = ast.parse(self._module_path().read_text(encoding="utf-8"))

        runtime_imports: list[str] = []

        # Walk the top-level body collecting only RUNTIME imports — anything
        # nested under an ``if TYPE_CHECKING:`` guard is excluded.
        def _is_type_checking_guard(node: ast.AST) -> bool:
            if not isinstance(node, ast.If):
                return False
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                return True
            if isinstance(test, ast.Attribute):
                return test.attr == "TYPE_CHECKING"
            return False

        def _walk(body: list[ast.stmt]) -> None:
            for node in body:
                if _is_type_checking_guard(node):
                    continue
                if isinstance(node, ast.Import):
                    runtime_imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    runtime_imports.append(node.module)

        _walk(tree.body)

        violations = [
            imp
            for imp in runtime_imports
            for prefix in self.FORBIDDEN_PREFIXES
            if imp == prefix or imp.startswith(prefix + ".")
        ]
        assert violations == [], (
            f"capabilities.py must be a leaf — forbidden runtime imports: "
            f"{violations}"
        )
