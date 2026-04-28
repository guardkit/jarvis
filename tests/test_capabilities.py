"""Tests for ``jarvis.tools.capabilities`` Pydantic models and tool functions.

Validates DM-tool-types §1 contract:

* :class:`CapabilityToolSummary` — required fields, defaults, ``extra="ignore"``.
* :class:`CapabilityDescriptor` — kebab-case ``agent_id``, defaults, literal
  enums, ``extra="ignore"``.
* :meth:`CapabilityDescriptor.as_prompt_block` — byte-for-byte deterministic
  rendering matching DM-tool-types §"Prompt-block shape".
* Module-level invariant — no imports from forbidden domain packages
  (ADR-ARCH-002 leaf).

TASK-J002-012 — capability-catalogue ``@tool`` functions
(:func:`list_available_capabilities`, :func:`capabilities_refresh`,
:func:`capabilities_subscribe_updates`):

* AC-001 — three ``@tool(parse_docstring=True)`` functions exposed.
* AC-002 — docstrings match API-tools.md §2.1-2.3 byte-for-byte.
* AC-003 — list returns JSON snapshot copy with ASSUM-006 isolation.
* AC-004 — refresh returns the exact stub OK string.
* AC-005 — subscribe returns the exact stub OK string.
* AC-006 — every tool wraps internal errors as ``ERROR: registry_unavailable``.
* AC-007 — concurrent list / refresh leaves snapshots stable.
"""

from __future__ import annotations

import ast
import json
import pathlib
import threading
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from jarvis.tools import capabilities as capabilities_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
    capabilities_refresh,
    capabilities_subscribe_updates,
    list_available_capabilities,
)

# ---------------------------------------------------------------------------
# CapabilityToolSummary — AC-001
# ---------------------------------------------------------------------------


class TestCapabilityToolSummary:
    """AC-001 — model contract for CapabilityToolSummary."""

    def test_construct_with_required_fields_succeeds(self) -> None:
        summary = CapabilityToolSummary(
            tool_name="run_architecture_session",
            description="Drive a full /system-arch session.",
        )
        assert summary.tool_name == "run_architecture_session"
        assert summary.description == "Drive a full /system-arch session."
        assert summary.risk_level == "read_only"

    def test_risk_level_defaults_to_read_only(self) -> None:
        summary = CapabilityToolSummary(tool_name="t", description="d")
        assert summary.risk_level == "read_only"

    @pytest.mark.parametrize(
        "risk_level", ["read_only", "mutating", "destructive"]
    )
    def test_valid_risk_levels_accepted(self, risk_level: str) -> None:
        summary = CapabilityToolSummary(
            tool_name="t", description="d", risk_level=risk_level
        )
        assert summary.risk_level == risk_level

    def test_invalid_risk_level_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(
                tool_name="t", description="d", risk_level="catastrophic"
            )

    def test_empty_tool_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(tool_name="", description="d")

    def test_empty_description_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityToolSummary(tool_name="t", description="")

    def test_extra_fields_ignored(self) -> None:
        """ConfigDict(extra='ignore') — forward-compatible with new fields."""
        summary = CapabilityToolSummary.model_validate(
            {
                "tool_name": "t",
                "description": "d",
                "risk_level": "mutating",
                "future_field": "should-not-raise",
            }
        )
        assert summary.tool_name == "t"
        assert not hasattr(summary, "future_field")


# ---------------------------------------------------------------------------
# CapabilityDescriptor — AC-002
# ---------------------------------------------------------------------------


class TestCapabilityDescriptor:
    """AC-002 — model contract for CapabilityDescriptor."""

    def test_construct_with_required_fields_succeeds(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description="Designs systems.",
        )
        assert descriptor.agent_id == "architect-agent"
        assert descriptor.role == "Architect"
        assert descriptor.description == "Designs systems."
        assert descriptor.capability_list == []
        assert descriptor.cost_signal == "unknown"
        assert descriptor.latency_signal == "unknown"
        assert descriptor.last_heartbeat_at is None
        assert descriptor.trust_tier == "specialist"

    @pytest.mark.parametrize(
        "agent_id",
        ["a", "ab", "abc-def", "agent1", "a1-b2-c3", "architect-agent"],
    )
    def test_valid_kebab_case_agent_ids_accepted(self, agent_id: str) -> None:
        descriptor = CapabilityDescriptor(
            agent_id=agent_id, role="r", description="d"
        )
        assert descriptor.agent_id == agent_id

    @pytest.mark.parametrize(
        "agent_id",
        [
            "",  # empty
            "1agent",  # leading digit
            "-agent",  # leading hyphen
            "Agent",  # uppercase
            "agent_id",  # underscore
            "agent.id",  # dot
            "agent id",  # space
            "AGENT",  # all caps
        ],
    )
    def test_invalid_agent_ids_rejected(self, agent_id: str) -> None:
        with pytest.raises(ValidationError):
            CapabilityDescriptor(agent_id=agent_id, role="r", description="d")

    @pytest.mark.parametrize(
        "trust_tier", ["core", "specialist", "extension"]
    )
    def test_valid_trust_tiers_accepted(self, trust_tier: str) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="r", description="d", trust_tier=trust_tier
        )
        assert descriptor.trust_tier == trust_tier

    def test_invalid_trust_tier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CapabilityDescriptor(
                agent_id="a", role="r", description="d", trust_tier="rogue"
            )

    def test_capability_list_holds_summaries(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a",
            role="r",
            description="d",
            capability_list=[
                CapabilityToolSummary(tool_name="t1", description="d1"),
                CapabilityToolSummary(tool_name="t2", description="d2"),
            ],
        )
        assert len(descriptor.capability_list) == 2
        assert descriptor.capability_list[0].tool_name == "t1"

    def test_capability_list_coerces_dicts(self) -> None:
        descriptor = CapabilityDescriptor.model_validate(
            {
                "agent_id": "a",
                "role": "r",
                "description": "d",
                "capability_list": [
                    {"tool_name": "t1", "description": "d1"},
                ],
            }
        )
        assert isinstance(descriptor.capability_list[0], CapabilityToolSummary)

    def test_last_heartbeat_at_accepts_datetime(self) -> None:
        ts = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
        descriptor = CapabilityDescriptor(
            agent_id="a", role="r", description="d", last_heartbeat_at=ts
        )
        assert descriptor.last_heartbeat_at == ts

    def test_extra_fields_ignored(self) -> None:
        """ConfigDict(extra='ignore') — forward-compatible with new manifest fields."""
        descriptor = CapabilityDescriptor.model_validate(
            {
                "agent_id": "a",
                "role": "r",
                "description": "d",
                "container_id": "must-be-stripped",  # infrastructure leak
                "future_field": 42,
            }
        )
        assert not hasattr(descriptor, "container_id")
        assert not hasattr(descriptor, "future_field")


# ---------------------------------------------------------------------------
# as_prompt_block — AC-003
# ---------------------------------------------------------------------------


class TestAsPromptBlock:
    """AC-003 — deterministic prompt-block rendering matching DM-tool-types."""

    def test_byte_for_byte_matches_dm_tool_types_example(self) -> None:
        """Render the exact example from DM-tool-types.md §Prompt-block shape."""
        descriptor = CapabilityDescriptor(
            agent_id="architect-agent",
            role="Architect",
            description=(
                "Produces architecture sessions, C4 diagrams, and ADRs for "
                "features. Prefers\nevidence-based decisions grounded in the "
                "existing ARCHITECTURE.md."
            ),
            cost_signal="moderate",
            latency_signal="5-30s",
            trust_tier="specialist",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="run_architecture_session",
                    description=(
                        "Drive a full /system-arch\nsession end-to-end "
                        "from a scope document."
                    ),
                    risk_level="read_only",
                ),
                CapabilityToolSummary(
                    tool_name="draft_adr",
                    description=(
                        "Produce a new ADR file given context + decision."
                    ),
                    risk_level="mutating",
                ),
            ],
        )

        expected = (
            "### architect-agent — Architect "
            "(trust: specialist, cost: moderate, latency: 5-30s)\n"
            "\n"
            "Produces architecture sessions, C4 diagrams, and ADRs for "
            "features. Prefers\n"
            "evidence-based decisions grounded in the existing "
            "ARCHITECTURE.md.\n"
            "\n"
            "Tools:\n"
            "  - run_architecture_session (read_only) — "
            "Drive a full /system-arch\n"
            "    session end-to-end from a scope document.\n"
            "  - draft_adr (mutating) — Produce a new ADR file given "
            "context + decision."
        )

        assert descriptor.as_prompt_block() == expected

    def test_render_is_deterministic(self) -> None:
        """Same descriptor renders to the same bytes every call."""
        descriptor = CapabilityDescriptor(
            agent_id="a",
            role="r",
            description="d",
            capability_list=[
                CapabilityToolSummary(tool_name="t", description="td"),
            ],
        )
        assert descriptor.as_prompt_block() == descriptor.as_prompt_block()

    def test_no_capabilities_renders_tools_header_only(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="R", description="d"
        )
        block = descriptor.as_prompt_block()
        assert block.endswith("\nTools:")
        assert (
            block
            == "### a — R (trust: specialist, cost: unknown, latency: unknown)"
            "\n\nd\n\nTools:"
        )

    def test_default_signals_render_unknown(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="x-y", role="X-Role", description="desc"
        )
        first_line = descriptor.as_prompt_block().splitlines()[0]
        assert (
            first_line
            == "### x-y — X-Role (trust: specialist, cost: unknown, "
            "latency: unknown)"
        )

    def test_trust_tier_appears_in_header(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="x",
            role="R",
            description="d",
            trust_tier="core",
        )
        first_line = descriptor.as_prompt_block().splitlines()[0]
        assert "trust: core" in first_line

    def test_returns_str(self) -> None:
        descriptor = CapabilityDescriptor(
            agent_id="a", role="r", description="d"
        )
        assert isinstance(descriptor.as_prompt_block(), str)


# ---------------------------------------------------------------------------
# Import-graph leaf invariant — AC-004
# ---------------------------------------------------------------------------


class TestModuleIsLeaf:
    """AC-004 — capabilities.py must not import from agents/infrastructure/cli."""

    FORBIDDEN_PREFIXES = (
        "jarvis.agents",
        "jarvis.infrastructure",
        "jarvis.cli",
    )

    def _capabilities_path(self) -> pathlib.Path:
        return (
            pathlib.Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "tools"
            / "capabilities.py"
        )

    def test_no_forbidden_static_imports(self) -> None:
        """capabilities.py must be a leaf at *runtime* — TYPE_CHECKING imports
        are excluded from this check (FEAT-JARVIS-004 references the
        ``CapabilitiesRegistry`` Protocol type only under ``TYPE_CHECKING``)."""
        tree = ast.parse(self._capabilities_path().read_text(encoding="utf-8"))

        def _is_type_checking_guard(node: ast.AST) -> bool:
            if not isinstance(node, ast.If):
                return False
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                return True
            if isinstance(test, ast.Attribute):
                return test.attr == "TYPE_CHECKING"
            return False

        imports: list[str] = []
        for node in tree.body:
            if _is_type_checking_guard(node):
                # Skip the TYPE_CHECKING block — those imports do not
                # create a runtime dependency.
                continue
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        violations = [
            imp
            for imp in imports
            for prefix in self.FORBIDDEN_PREFIXES
            if imp == prefix or imp.startswith(prefix + ".")
        ]
        assert violations == [], (
            f"capabilities.py must be a leaf — forbidden imports: {violations}"
        )


# ---------------------------------------------------------------------------
# Capability-catalogue tools — TASK-J002-012
# ---------------------------------------------------------------------------

# Exact strings from API-tools.md (FEAT-JARVIS-002 §2.3 + FEAT-JARVIS-004
# §4). Kept as module-level constants so a docstring drift in API-tools.md
# is caught by the tests, not silently shipped.
#
# FEAT-JARVIS-004 (TASK-J004-012) swapped the ``capabilities_refresh``
# return surface from the Phase 2 acknowledgement to the KV-backed
# OK / DEGRADED pair. The subscribe OK string is unchanged across phases.
EXPECTED_REFRESH_OK = "OK: refresh queued — registry resynchronised"
EXPECTED_REFRESH_DEGRADED = (
    "DEGRADED: transport_unavailable — NATS connection failed"
)
EXPECTED_SUBSCRIBE_OK = "OK: subscribed (stubbed in Phase 2 — no live updates)"


def _sample_registry() -> list[CapabilityDescriptor]:
    """Construct a small but realistic two-entry registry for tool tests."""
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


class _ListBackedRegistry:
    """Test adapter wrapping a ``list[CapabilityDescriptor]`` as a
    :class:`jarvis.infrastructure.capabilities_registry.CapabilitiesRegistry`.

    FEAT-JARVIS-004 (TASK-J004-012) swapped ``_capability_registry``'s type
    from ``list[CapabilityDescriptor]`` to ``CapabilitiesRegistry | None``.
    The legacy Phase 2 tests in this module want to assert on a known list
    of descriptors; this adapter exposes them through the new Protocol
    surface (``snapshot/refresh/subscribe_updates/close``) so the tools'
    new bodies can call ``.snapshot()`` on them unchanged.
    """

    def __init__(self, descriptors: list[CapabilityDescriptor]) -> None:
        self._descriptors = descriptors
        self.refresh_calls = 0
        self.subscribe_calls = 0

    def snapshot(self) -> list[CapabilityDescriptor]:
        # Return a fresh ``list`` copy on every call to satisfy the
        # ASSUM-006 snapshot-isolation contract.
        return list(self._descriptors)

    async def refresh(self) -> None:
        self.refresh_calls += 1

    async def subscribe_updates(self, callback: object) -> None:
        self.subscribe_calls += 1

    async def close(self) -> None:
        return None


@pytest.fixture()
def bound_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a fresh registry into the capabilities module for the test scope.

    The fixture yields the underlying ``list[CapabilityDescriptor]`` (so
    tests can assert against the descriptors directly) and resets the
    module-level subscribe-idempotency flag on entry/exit so tests stay
    isolated.
    """
    saved = capabilities_module._capability_registry
    saved_subscribed = capabilities_module._subscribe_invoked
    descriptors = _sample_registry()
    capabilities_module._capability_registry = _ListBackedRegistry(descriptors)
    capabilities_module._subscribe_invoked = False
    try:
        yield descriptors
    finally:
        capabilities_module._capability_registry = saved
        capabilities_module._subscribe_invoked = saved_subscribed


@pytest.fixture()
def empty_registry() -> Generator[None, None, None]:
    """Bind an empty registry into the capabilities module for the test scope."""
    saved = capabilities_module._capability_registry
    saved_subscribed = capabilities_module._subscribe_invoked
    capabilities_module._capability_registry = _ListBackedRegistry([])
    capabilities_module._subscribe_invoked = False
    try:
        yield
    finally:
        capabilities_module._capability_registry = saved
        capabilities_module._subscribe_invoked = saved_subscribed


@pytest.fixture()
def configured_registry() -> Generator[None, None, None]:
    """Ensure a non-None registry is wired (used by refresh/subscribe tests
    that don't care about the descriptor contents)."""
    saved = capabilities_module._capability_registry
    saved_subscribed = capabilities_module._subscribe_invoked
    capabilities_module._capability_registry = _ListBackedRegistry(
        _sample_registry()
    )
    capabilities_module._subscribe_invoked = False
    try:
        yield
    finally:
        capabilities_module._capability_registry = saved
        capabilities_module._subscribe_invoked = saved_subscribed


# ---------------------------------------------------------------------------
# AC-001 — module-level @tool exposure
# ---------------------------------------------------------------------------


class TestAC001ToolExposure:
    """AC-001 — three ``@tool(parse_docstring=True)`` functions are exposed."""

    @pytest.mark.parametrize(
        "name",
        [
            "list_available_capabilities",
            "capabilities_refresh",
            "capabilities_subscribe_updates",
        ],
    )
    def test_tool_is_module_attribute(self, name: str) -> None:
        assert hasattr(capabilities_module, name)

    @pytest.mark.parametrize(
        "tool_obj",
        [
            list_available_capabilities,
            capabilities_refresh,
            capabilities_subscribe_updates,
        ],
    )
    def test_tool_has_invoke_method(self, tool_obj: object) -> None:
        """``@tool`` produces a BaseTool with an ``invoke`` method."""
        assert hasattr(tool_obj, "invoke")
        assert callable(tool_obj.invoke)

    @pytest.mark.parametrize(
        ("tool_obj", "expected_name"),
        [
            (list_available_capabilities, "list_available_capabilities"),
            (capabilities_refresh, "capabilities_refresh"),
            (capabilities_subscribe_updates, "capabilities_subscribe_updates"),
        ],
    )
    def test_tool_carries_documented_name(
        self, tool_obj: object, expected_name: str
    ) -> None:
        assert getattr(tool_obj, "name", None) == expected_name


# ---------------------------------------------------------------------------
# AC-002 — docstrings match API-tools.md §2.1-2.3
# ---------------------------------------------------------------------------


class TestAC002DocstringContract:
    """AC-002 — docstrings match the authoritative API-tools.md text."""

    def test_list_available_capabilities_docstring_phrases(self) -> None:
        """Spot-check the §3 (FEAT-J004) contract phrases the reasoning
        model relies on."""
        # ``parse_docstring=True`` strips the Returns: section out of
        # ``tool.description`` (it becomes the schema), so we check both the
        # truncated description and the full ``func.__doc__`` original.
        description = list_available_capabilities.description or ""
        full_doc = list_available_capabilities.func.__doc__ or ""
        assert "Return the current fleet capability catalogue as JSON." in description
        assert "## Available Capabilities" in description
        # FEAT-JARVIS-004 (TASK-J004-012) replaced the Phase 2 stub
        # paragraph with the new latency line — the model now sees the
        # cached-live-registry timing instead of the in-memory stub note.
        assert "in-memory stub registry" not in description
        assert "<30ms (cached live registry" in description
        # The Returns: section names the only contract-defined error string.
        assert "ERROR: registry_unavailable" in full_doc

    def test_capabilities_refresh_docstring_phrases(self) -> None:
        """Spot-check the FEAT-J004 §4 contract phrases."""
        description = capabilities_refresh.description or ""
        full_doc = capabilities_refresh.func.__doc__ or ""
        assert "Invalidate the cached capability catalogue" in description
        # FEAT-JARVIS-004: Phase 2 stub paragraph deleted; replaced by the
        # NATS KV re-read behavioural line.
        assert "STUB in Phase 2" not in description
        assert "NATSKVManifestRegistry" in description
        # The exact OK / DEGRADED strings live in the Returns: section.
        assert EXPECTED_REFRESH_OK in full_doc
        assert EXPECTED_REFRESH_DEGRADED in full_doc

    def test_capabilities_subscribe_updates_docstring_phrases(self) -> None:
        """Spot-check the FEAT-J004 §5 contract phrases."""
        description = capabilities_subscribe_updates.description or ""
        full_doc = capabilities_subscribe_updates.func.__doc__ or ""
        assert "Subscribe the current session" in description
        # FEAT-JARVIS-004: Phase 2 stub paragraph deleted; replaced by the
        # NATS KV watcher / idempotency behavioural line.
        assert "STUB in Phase 2" not in description
        assert "NATS KV watcher" in description
        assert "Idempotent" in description
        assert EXPECTED_SUBSCRIBE_OK in full_doc

    def test_phase2_swap_targets_were_removed(self) -> None:
        """FEAT-JARVIS-004 swapped the Phase 2 stubs; the grep-anchor is gone.

        TASK-J002-021's pre-FEAT-J004 invariant required at least two
        ``stubbed in Phase 2`` substrings in the module (the constant and
        the docstrings). FEAT-J004 §3-§5 deleted those paragraphs and the
        ``_REFRESH_OK_MESSAGE`` constant; the only surviving occurrence is
        the ``_SUBSCRIBE_OK_MESSAGE`` literal that the model has been
        reading byte-identical since Phase 2."""
        path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "tools"
            / "capabilities.py"
        )
        text = path.read_text(encoding="utf-8")
        # The deleted Phase 2 paragraphs each contained
        # ``stubbed in Phase 2``; only the literal in the SUBSCRIBE
        # constant should remain (count ≤ 2 — the value AND its repeat in
        # the docstring's Returns: line).
        assert "STUB in Phase 2" not in text
        # The deleted ``_REFRESH_OK_MESSAGE`` constant must not survive.
        assert "_REFRESH_OK_MESSAGE" not in text


# ---------------------------------------------------------------------------
# AC-003 — list_available_capabilities returns a JSON snapshot copy
# ---------------------------------------------------------------------------


class TestAC003ListReturnsJsonSnapshot:
    """AC-003 — JSON serialisation + ASSUM-006 snapshot isolation."""

    def test_returns_json_string(self, bound_registry: list[CapabilityDescriptor]) -> None:
        result = list_available_capabilities.invoke({})
        assert isinstance(result, str)
        # Parse round-trip — the contract surface is JSON.
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == len(bound_registry)

    def test_payload_shape_matches_descriptor_dump(
        self, bound_registry: list[CapabilityDescriptor]
    ) -> None:
        parsed = json.loads(list_available_capabilities.invoke({}))
        for entry, descriptor in zip(parsed, bound_registry, strict=True):
            assert entry["agent_id"] == descriptor.agent_id
            assert entry["role"] == descriptor.role
            assert entry["trust_tier"] == descriptor.trust_tier
            assert isinstance(entry["capability_list"], list)
            for cap_entry, cap in zip(
                entry["capability_list"], descriptor.capability_list, strict=True
            ):
                assert cap_entry["tool_name"] == cap.tool_name
                assert cap_entry["risk_level"] == cap.risk_level

    def test_empty_registry_returns_empty_json_array(
        self, empty_registry: None
    ) -> None:
        assert list_available_capabilities.invoke({}) == "[]"

    def test_snapshot_isolation_against_post_call_rebind(
        self, bound_registry: list[CapabilityDescriptor]
    ) -> None:
        """Rebinding ``_capability_registry`` after the call must not retro-mutate the JSON."""
        before = list_available_capabilities.invoke({})
        # Swap the registry handle out for an empty-list-backed adapter
        # (FEAT-JARVIS-004: the swap-point now holds a Protocol object,
        # not a list).
        capabilities_module._capability_registry = _ListBackedRegistry([])
        after = list_available_capabilities.invoke({})
        # The first call's serialised string is captured as a value — no
        # references back into the registry list — so it is unaffected by
        # the post-call rebinding.
        assert before != after
        assert after == "[]"
        # The first snapshot still names the originally-bound agents.
        first_payload = json.loads(before)
        agent_ids = [entry["agent_id"] for entry in first_payload]
        assert agent_ids == [d.agent_id for d in bound_registry]


# ---------------------------------------------------------------------------
# AC-004 / AC-005 — Phase-2 OK acknowledgements (byte-exact)
# ---------------------------------------------------------------------------


class TestAC004CapabilitiesRefreshOk:
    """AC-004 — refresh returns the FEAT-JARVIS-004 KV-backed OK string."""

    def test_returns_exact_ok_string(
        self, configured_registry: None
    ) -> None:
        assert capabilities_refresh.invoke({}) == EXPECTED_REFRESH_OK

    def test_call_is_idempotent(
        self, configured_registry: None
    ) -> None:
        """Repeated calls return the same byte-exact string."""
        first = capabilities_refresh.invoke({})
        second = capabilities_refresh.invoke({})
        assert first == second == EXPECTED_REFRESH_OK


class TestAC005CapabilitiesSubscribeUpdatesOk:
    """AC-005 — subscribe returns the OK acknowledgement (unchanged across phases)."""

    def test_returns_exact_ok_string(
        self, configured_registry: None
    ) -> None:
        assert capabilities_subscribe_updates.invoke({}) == EXPECTED_SUBSCRIBE_OK

    def test_call_is_idempotent(
        self, configured_registry: None
    ) -> None:
        first = capabilities_subscribe_updates.invoke({})
        second = capabilities_subscribe_updates.invoke({})
        assert first == second == EXPECTED_SUBSCRIBE_OK


# ---------------------------------------------------------------------------
# AC-006 — never-raise envelope; structured ERROR on internal failure
# ---------------------------------------------------------------------------


class _BoomDescriptor:
    """A drop-in stand-in for :class:`CapabilityDescriptor` that explodes on dump.

    Used to exercise the never-raise guard in
    :func:`list_available_capabilities` — substituting one of these into
    ``_capability_registry`` triggers the ``except`` branch deterministically.
    """

    agent_id = "boom"

    def model_dump(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("synthetic registry failure")


class TestAC006NeverRaisesStructuredErrors:
    """AC-006 — every tool catches and renders ERROR strings on failure."""

    def test_list_available_capabilities_returns_structured_error_on_failure(
        self,
    ) -> None:
        # FEAT-JARVIS-004: the registry surface is a Protocol object whose
        # ``snapshot()`` returns descriptors. Wrap a boom descriptor so the
        # serialiser path explodes on ``model_dump`` deterministically.
        saved = capabilities_module._capability_registry
        capabilities_module._capability_registry = _ListBackedRegistry(
            [_BoomDescriptor()]  # type: ignore[list-item]
        )
        try:
            result = list_available_capabilities.invoke({})
        finally:
            capabilities_module._capability_registry = saved
        assert isinstance(result, str)
        assert result.startswith("ERROR: registry_unavailable — ")
        assert "synthetic registry failure" in result

    def test_list_available_capabilities_never_raises(self) -> None:
        saved = capabilities_module._capability_registry
        capabilities_module._capability_registry = _ListBackedRegistry(
            [_BoomDescriptor()]  # type: ignore[list-item]
        )
        try:
            list_available_capabilities.invoke({})  # must not raise
        except Exception as exc:  # pragma: no cover - guard regression
            pytest.fail(f"list_available_capabilities raised {exc!r}")
        finally:
            capabilities_module._capability_registry = saved

    def test_refresh_never_raises(self, configured_registry: None) -> None:
        try:
            capabilities_refresh.invoke({})
        except Exception as exc:  # pragma: no cover - guard regression
            pytest.fail(f"capabilities_refresh raised {exc!r}")

    def test_subscribe_never_raises(self, configured_registry: None) -> None:
        try:
            capabilities_subscribe_updates.invoke({})
        except Exception as exc:  # pragma: no cover - guard regression
            pytest.fail(f"capabilities_subscribe_updates raised {exc!r}")


# ---------------------------------------------------------------------------
# AC-007 — concurrent list + refresh preserves snapshot isolation
# ---------------------------------------------------------------------------


class TestAC007ConcurrentSnapshotIsolation:
    """AC-007 — list_available_capabilities + capabilities_refresh in parallel."""

    def test_concurrent_calls_return_consistent_results(
        self, bound_registry: list[CapabilityDescriptor]
    ) -> None:
        list_results: list[str] = []
        refresh_results: list[str] = []
        errors: list[BaseException] = []
        barrier = threading.Barrier(2)

        def run_list() -> None:
            try:
                barrier.wait(timeout=5)
                list_results.append(list_available_capabilities.invoke({}))
            except BaseException as exc:  # pragma: no cover - regression guard
                errors.append(exc)

        def run_refresh() -> None:
            try:
                barrier.wait(timeout=5)
                refresh_results.append(capabilities_refresh.invoke({}))
            except BaseException as exc:  # pragma: no cover - regression guard
                errors.append(exc)

        threads = [
            threading.Thread(target=run_list),
            threading.Thread(target=run_refresh),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        assert errors == []
        assert refresh_results == [EXPECTED_REFRESH_OK]
        assert len(list_results) == 1
        # The list_available_capabilities call returns the startup snapshot
        # — every agent in ``bound_registry`` must be present in the JSON.
        payload = json.loads(list_results[0])
        observed_ids = [entry["agent_id"] for entry in payload]
        assert observed_ids == [d.agent_id for d in bound_registry]

    def test_repeated_concurrent_pairs_remain_stable(
        self, bound_registry: list[CapabilityDescriptor]
    ) -> None:
        """Repeating the race many times must not corrupt the snapshot."""

        # Helpers defined at method scope (rather than per-iteration) so the
        # ``barrier`` and ``results`` they touch are passed in as default
        # arguments — sidesteps the B023 closure-over-loop-variable warning
        # while preserving the per-iteration race semantics.
        def list_and_collect(
            barrier: threading.Barrier, results: list[str]
        ) -> None:
            barrier.wait(timeout=5)
            results.append(list_available_capabilities.invoke({}))

        def refresh_and_collect(barrier: threading.Barrier) -> None:
            barrier.wait(timeout=5)
            # capabilities_refresh is a Phase-2 no-op, but still call it
            # so the test exercises the documented concurrent pairing.
            capabilities_refresh.invoke({})

        for _ in range(8):
            results: list[str] = []
            barrier = threading.Barrier(2)

            threads = [
                threading.Thread(
                    target=list_and_collect, args=(barrier, results)
                ),
                threading.Thread(
                    target=refresh_and_collect, args=(barrier,)
                ),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

            assert len(results) == 1
            payload = json.loads(results[0])
            assert [entry["agent_id"] for entry in payload] == [
                d.agent_id for d in bound_registry
            ]
