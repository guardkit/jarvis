"""Tests for TASK-J003-012 — assemble_tool_list session-aware gating (Layer 3).

Layer 3 of the belt+braces gate (DDR-014). Validates the
``include_frontier: bool = True`` keyword-only parameter that
``jarvis.tools.assemble_tool_list`` exposes so the attended (10-tool) and
ambient (9-tool) tool surfaces diverge by registry membership, not by a
runtime check the reasoning model could hypothetically subvert.

Acceptance criteria mapped to test classes:

- AC-001: ``include_frontier`` is a keyword-only parameter with default
  ``True``. (:class:`TestAC001IncludeFrontierKeywordOnly`)
- AC-002: When ``include_frontier=True`` the returned list contains
  ``escalate_to_frontier`` alongside every FEAT-JARVIS-002 tool.
  (:class:`TestAC002IncludeFrontierTrue`)
- AC-003: When ``include_frontier=False`` the returned list omits
  ``escalate_to_frontier`` entirely and still includes every other
  FEAT-JARVIS-002 tool. (:class:`TestAC003IncludeFrontierFalse`)
- AC-004: A new ``list`` object is returned each call so the reasoning
  model cannot mutate a shared list to add ``escalate_to_frontier`` at
  runtime. (:class:`TestAC004NoMutableAliasing`)
- AC-005: ``include_frontier`` is decoupled from session state — purely a
  lifecycle-time flag set by the caller.
  (:class:`TestAC005NoSessionCoupling`)
- AC-006: Identity check — ``escalate_to_frontier in result`` matches the
  ``include_frontier`` flag. (:class:`TestAC006IdentityCheck`)

ADR cross-references:

- **ADR-ARCH-022**: belt+braces constitutional gates.
- **ADR-ARCH-023**: not reasoning-adjustable.
- **ADR-ARCH-027**: attended-only cloud escape hatch.
- **DDR-014**: ``escalate_to_frontier`` lives in the dispatch tool module.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
from langchain_core.tools import BaseTool

from jarvis.config.settings import JarvisConfig
from jarvis.tools import (
    CapabilityDescriptor,
    assemble_tool_list,
)
from jarvis.tools import capabilities as capabilities_module
from jarvis.tools import dispatch as dispatch_module
from jarvis.tools import general as general_module
from jarvis.tools.dispatch import escalate_to_frontier


# ---------------------------------------------------------------------------
# Constants — the FEAT-J002 9-tool surface plus the FEAT-J003 escalation.
# ---------------------------------------------------------------------------
FEAT_J002_TOOL_NAMES: list[str] = [
    "calculate",
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "dispatch_by_capability",
    "get_calendar_events",
    "list_available_capabilities",
    "queue_build",
    "read_file",
    "search_web",
]

# Alphabetical insertion of ``escalate_to_frontier`` between
# ``dispatch_by_capability`` and ``get_calendar_events``.
FEAT_J003_ATTENDED_TOOL_NAMES: list[str] = [
    "calculate",
    "capabilities_refresh",
    "capabilities_subscribe_updates",
    "dispatch_by_capability",
    "escalate_to_frontier",
    "get_calendar_events",
    "list_available_capabilities",
    "queue_build",
    "read_file",
    "search_web",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def descriptor_alpha() -> CapabilityDescriptor:
    """Return a minimal valid descriptor."""
    return CapabilityDescriptor(
        agent_id="alpha",
        role="Alpha Agent",
        description="Handles alpha capabilities for tests.",
    )


@pytest.fixture()
def reset_tool_state() -> Any:
    """Snapshot and restore tool-module state around each test.

    ``assemble_tool_list`` mutates ``general._config`` plus the two
    ``_capability_registry`` attributes; the snapshot/restore guard keeps
    Layer-3 tests from leaking state into siblings (mirrors the FEAT-J002
    test fixture in ``test_assemble_tool_list.py``).
    """
    saved_general = general_module._config
    saved_caps = list(capabilities_module._capability_registry)
    saved_dispatch = list(dispatch_module._capability_registry)
    yield
    general_module._config = saved_general
    capabilities_module._capability_registry = saved_caps
    dispatch_module._capability_registry = saved_dispatch


# ---------------------------------------------------------------------------
# AC-001 — include_frontier is a keyword-only parameter with default True
# ---------------------------------------------------------------------------
class TestAC001IncludeFrontierKeywordOnly:
    """``include_frontier`` is keyword-only, typed ``bool``, default ``True``."""

    def test_include_frontier_parameter_exists(self) -> None:
        """``assemble_tool_list`` exposes a parameter named ``include_frontier``."""
        sig = inspect.signature(assemble_tool_list)
        assert "include_frontier" in sig.parameters

    def test_include_frontier_default_is_true(self) -> None:
        """Default value of ``include_frontier`` is ``True``."""
        sig = inspect.signature(assemble_tool_list)
        param = sig.parameters["include_frontier"]
        assert param.default is True

    def test_include_frontier_is_keyword_only(self) -> None:
        """``include_frontier`` is KEYWORD_ONLY (cannot be set positionally)."""
        sig = inspect.signature(assemble_tool_list)
        param = sig.parameters["include_frontier"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY

    def test_include_frontier_annotation_is_bool(self) -> None:
        """The parameter is annotated ``bool``.

        ``jarvis.tools.__init__`` uses ``from __future__ import
        annotations`` so the raw annotation comes back as a string
        rather than the resolved type object. The string spelling is the
        contract surface that survives the PEP 563 deferred-evaluation
        regime, so the assertion accepts either the resolved ``bool``
        type or its ``"bool"`` string form.
        """
        sig = inspect.signature(assemble_tool_list)
        param = sig.parameters["include_frontier"]
        assert param.annotation in (bool, "bool")

    def test_include_frontier_rejects_positional_argument(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Passing ``include_frontier`` positionally raises ``TypeError``."""
        with pytest.raises(TypeError):
            # 3rd positional argument must not bind to ``include_frontier``.
            assemble_tool_list(test_config, [descriptor_alpha], False)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# AC-002 — include_frontier=True yields the attended 10-tool surface
# ---------------------------------------------------------------------------
class TestAC002IncludeFrontierTrue:
    """When ``include_frontier=True`` the result contains every attended tool."""

    def test_includes_escalate_to_frontier(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """``escalate_to_frontier`` is present in the attended list."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        names = [t.name for t in result]
        assert "escalate_to_frontier" in names

    def test_returns_ten_tools(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Attended surface is the FEAT-J002 9-tool set plus the escalation."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        assert len(result) == 10

    def test_includes_all_feat_j002_tools(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Every FEAT-J002 tool name is still present alongside the escalation."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        names = {t.name for t in result}
        for tool_name in FEAT_J002_TOOL_NAMES:
            assert tool_name in names, f"FEAT-J002 tool {tool_name!r} missing"

    def test_attended_tool_order_is_alphabetical(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Attended list order is the canonical alphabetical sequence."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        names = [t.name for t in result]
        assert names == FEAT_J003_ATTENDED_TOOL_NAMES

    def test_default_argument_matches_include_frontier_true(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Calling without ``include_frontier`` matches the explicit-True call."""
        explicit = [
            t.name
            for t in assemble_tool_list(
                test_config, [descriptor_alpha], include_frontier=True
            )
        ]
        default = [
            t.name for t in assemble_tool_list(test_config, [descriptor_alpha])
        ]
        assert default == explicit

    def test_returned_objects_are_basetools(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Every entry — including the escalation — is a ``BaseTool``."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        for tool in result:
            assert isinstance(tool, BaseTool)


# ---------------------------------------------------------------------------
# AC-003 — include_frontier=False yields the FEAT-J002 9-tool surface
# ---------------------------------------------------------------------------
class TestAC003IncludeFrontierFalse:
    """When ``include_frontier=False`` the result omits ``escalate_to_frontier``."""

    def test_omits_escalate_to_frontier(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """``escalate_to_frontier`` is absent from the ambient list."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        names = [t.name for t in result]
        assert "escalate_to_frontier" not in names

    def test_returns_nine_tools(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Ambient surface is exactly the FEAT-J002 9-tool count."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        assert len(result) == 9

    def test_includes_all_feat_j002_tools(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Every FEAT-J002 tool name is still present, unchanged."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        names = [t.name for t in result]
        assert names == FEAT_J002_TOOL_NAMES

    def test_escalate_tool_object_is_not_present_by_identity(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """No tool in the ambient list is the ``escalate_to_frontier`` object."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        assert all(t is not escalate_to_frontier for t in result)


# ---------------------------------------------------------------------------
# AC-004 — fresh list each call (no mutable aliasing the model could exploit)
# ---------------------------------------------------------------------------
class TestAC004NoMutableAliasing:
    """Each call returns a new ``list`` object — model cannot mutate-add."""

    def test_two_calls_return_distinct_list_objects(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Repeated calls produce different list instances."""
        first = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        second = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        assert first is not second

    def test_attended_and_ambient_lists_are_distinct_objects(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Attended and ambient calls produce independent list instances."""
        attended = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        ambient = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        assert attended is not ambient

    def test_mutating_ambient_list_does_not_add_escalate_to_subsequent_calls(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """Appending to a returned list cannot smuggle the escalation in.

        Models the ADR-ARCH-023 threat: a reasoning model that obtains
        the ambient ``list`` reference and ``.append(escalate_to_frontier)``
        must NOT see that mutation reflected in any later ambient call.
        """
        ambient = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        # Hostile mutation — append the escalation to the returned list.
        ambient.append(escalate_to_frontier)

        fresh = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        fresh_names = [t.name for t in fresh]
        assert "escalate_to_frontier" not in fresh_names
        assert len(fresh) == 9


# ---------------------------------------------------------------------------
# AC-005 — flag is decoupled from session state (lifecycle-time only)
# ---------------------------------------------------------------------------
class TestAC005NoSessionCoupling:
    """``include_frontier`` is purely a caller-supplied lifecycle flag."""

    def test_call_without_session_resolver_succeeds_when_true(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """No session machinery is consulted to honour ``include_frontier=True``."""
        # Explicitly clear any layer-2 hooks so the call cannot consult a
        # session resolver — the flag must work as a pure lifecycle switch.
        dispatch_module._current_session_hook = None
        dispatch_module._async_subagent_frame_hook = None

        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        names = [t.name for t in result]
        assert "escalate_to_frontier" in names

    def test_call_without_session_resolver_succeeds_when_false(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """No session machinery is consulted to honour ``include_frontier=False``."""
        dispatch_module._current_session_hook = None
        dispatch_module._async_subagent_frame_hook = None

        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        names = [t.name for t in result]
        assert "escalate_to_frontier" not in names

    def test_attended_session_hook_does_not_force_include(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """An attended session resolver cannot override the caller's flag."""

        # Even with a fully attended session resolver wired, the flag is
        # honoured exactly as supplied — no coupling.
        def fake_session_hook() -> Any:  # pragma: no cover - shape only
            class _Sentinel:
                adapter = "telegram"

            return _Sentinel()

        dispatch_module._current_session_hook = fake_session_hook
        try:
            result = assemble_tool_list(
                test_config, [descriptor_alpha], include_frontier=False
            )
            names = [t.name for t in result]
            assert "escalate_to_frontier" not in names
        finally:
            dispatch_module._current_session_hook = None


# ---------------------------------------------------------------------------
# AC-006 — identity check on the actual tool object
# ---------------------------------------------------------------------------
class TestAC006IdentityCheck:
    """``escalate_to_frontier in result`` matches the ``include_frontier`` flag."""

    def test_identity_present_when_true(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """The exact ``escalate_to_frontier`` object appears when True."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=True
        )
        assert escalate_to_frontier in result

    def test_identity_absent_when_false(
        self,
        test_config: JarvisConfig,
        descriptor_alpha: CapabilityDescriptor,
        reset_tool_state: None,
    ) -> None:
        """The exact ``escalate_to_frontier`` object is absent when False."""
        result = assemble_tool_list(
            test_config, [descriptor_alpha], include_frontier=False
        )
        assert escalate_to_frontier not in result
