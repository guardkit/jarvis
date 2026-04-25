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
        tree = ast.parse(self._capabilities_path().read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
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

# Exact strings from API-tools.md §2.2 / §2.3 (and the matching task
# acceptance criteria). Kept as module-level constants so a docstring drift
# in API-tools.md is caught by the tests, not silently shipped.
EXPECTED_REFRESH_OK = (
    "OK: refresh queued (stubbed in Phase 2 — in-memory registry is always fresh)"
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


@pytest.fixture()
def bound_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a fresh registry into the capabilities module for the test scope."""
    saved = capabilities_module._capability_registry
    fresh = _sample_registry()
    capabilities_module._capability_registry = fresh
    try:
        yield fresh
    finally:
        capabilities_module._capability_registry = saved


@pytest.fixture()
def empty_registry() -> Generator[None, None, None]:
    """Bind an empty registry into the capabilities module for the test scope."""
    saved = capabilities_module._capability_registry
    capabilities_module._capability_registry = []
    try:
        yield
    finally:
        capabilities_module._capability_registry = saved


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
        """Spot-check the §2.1 contract phrases the reasoning model relies on."""
        # ``parse_docstring=True`` strips the Returns: section out of
        # ``tool.description`` (it becomes the schema), so we check both the
        # truncated description and the full ``func.__doc__`` original.
        description = list_available_capabilities.description or ""
        full_doc = list_available_capabilities.func.__doc__ or ""
        assert "Return the current fleet capability catalogue as JSON." in description
        assert "## Available Capabilities" in description
        assert "in-memory stub registry" in description
        # The Returns: section names the only contract-defined error string.
        assert "ERROR: registry_unavailable" in full_doc

    def test_capabilities_refresh_docstring_phrases(self) -> None:
        """Spot-check the §2.2 contract phrases."""
        description = capabilities_refresh.description or ""
        full_doc = capabilities_refresh.func.__doc__ or ""
        assert "Invalidate the cached capability catalogue" in description
        assert "STUB in Phase 2" in description
        # The exact OK string lives in the Returns: section.
        assert EXPECTED_REFRESH_OK in full_doc

    def test_capabilities_subscribe_updates_docstring_phrases(self) -> None:
        """Spot-check the §2.3 contract phrases."""
        description = capabilities_subscribe_updates.description or ""
        full_doc = capabilities_subscribe_updates.func.__doc__ or ""
        assert "Subscribe the current session" in description
        assert "STUB in Phase 2" in description
        assert EXPECTED_SUBSCRIBE_OK in full_doc

    def test_swap_point_grep_anchor_present(self) -> None:
        """The ``stubbed in Phase 2`` swap-point grep anchor must be in the file."""
        path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "src"
            / "jarvis"
            / "tools"
            / "capabilities.py"
        )
        text = path.read_text(encoding="utf-8")
        # Per task swap_point_note: a future Phase-3 patch greps for this
        # exact substring inside capabilities.py to find the swap targets.
        assert text.count("stubbed in Phase 2") >= 2


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
        capabilities_module._capability_registry = []
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
    """AC-004 — refresh returns the exact stub acknowledgement."""

    def test_returns_exact_ok_string(self) -> None:
        assert capabilities_refresh.invoke({}) == EXPECTED_REFRESH_OK

    def test_call_is_idempotent(self) -> None:
        """Repeated calls return the same byte-exact string."""
        first = capabilities_refresh.invoke({})
        second = capabilities_refresh.invoke({})
        assert first == second == EXPECTED_REFRESH_OK


class TestAC005CapabilitiesSubscribeUpdatesOk:
    """AC-005 — subscribe returns the exact stub acknowledgement."""

    def test_returns_exact_ok_string(self) -> None:
        assert capabilities_subscribe_updates.invoke({}) == EXPECTED_SUBSCRIBE_OK

    def test_call_is_idempotent(self) -> None:
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
        saved = capabilities_module._capability_registry
        capabilities_module._capability_registry = [_BoomDescriptor()]  # type: ignore[list-item]
        try:
            result = list_available_capabilities.invoke({})
        finally:
            capabilities_module._capability_registry = saved
        assert isinstance(result, str)
        assert result.startswith("ERROR: registry_unavailable — ")
        assert "synthetic registry failure" in result

    def test_list_available_capabilities_never_raises(self) -> None:
        saved = capabilities_module._capability_registry
        capabilities_module._capability_registry = [_BoomDescriptor()]  # type: ignore[list-item]
        try:
            list_available_capabilities.invoke({})  # must not raise
        except Exception as exc:  # pragma: no cover - guard regression
            pytest.fail(f"list_available_capabilities raised {exc!r}")
        finally:
            capabilities_module._capability_registry = saved

    def test_refresh_never_raises(self) -> None:
        try:
            capabilities_refresh.invoke({})
        except Exception as exc:  # pragma: no cover - guard regression
            pytest.fail(f"capabilities_refresh raised {exc!r}")

    def test_subscribe_never_raises(self) -> None:
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
