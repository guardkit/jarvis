"""Tests for TASK-J003-015 — extend ``lifecycle.startup`` for FEAT-JARVIS-003.

Acceptance criteria covered (cross-referenced to the task file):

    AC-001: ``lifecycle.startup(config)`` constructs
            ``llamaswap_adapter = LlamaSwapAdapter(base_url=config.llama_swap_base_url)``.
    AC-002: ``startup`` calls ``async_subagents = build_async_subagents(config)``
            and threads it into
            ``build_supervisor(..., async_subagents=async_subagents, ...)``.
    AC-003: ``startup`` assembles attended AND ambient tool lists via
            ``assemble_tool_list(...)`` with ``include_frontier=True`` /
            ``False`` respectively, and passes
            ``ambient_tool_factory=lambda: tool_list_ambient`` into
            ``build_supervisor``.
    AC-004: ``OPENAI_BASE_URL`` environment variable is set to
            ``<config.llama_swap_base_url>/v1`` before
            ``build_async_subagents`` runs.
    AC-005: ``AppState`` is extended to carry
            ``llamaswap_adapter: LlamaSwapAdapter``.
    AC-006: ``should_emit_voice_ack(adapter_id, swap_status)`` returns
            ``True`` iff ``adapter_id`` is voice-reactive AND
            ``swap_status.eta_seconds > 30``.  Boundary table — ETA
            0/30/31/240 → False/False/True/True.
    AC-007: When ``should_emit_voice_ack`` returns ``True`` the
            supervisor emits the TTS ack stub and queues the request
            for dispatch once the swap completes.
    AC-008: Phase 1 + FEAT-J002 startup behaviour preserved — the
            existing AppState fields (config, supervisor, store,
            session_manager, capability_registry) are still wired and
            non-None.

The lint/format AC (AC-009) is verified externally via ``ruff`` /
``ruff format`` and is not asserted here.

Test layout follows the class-per-AC convention used by the rest of
the FEAT-JARVIS-002 / FEAT-JARVIS-003 suite (see
``tests/test_supervisor_lifecycle_wiring.py`` for the canonical
shape).  Network-free invariants are enforced by patching
``init_chat_model`` to return a deterministic ``FakeListChatModel``.
"""

from __future__ import annotations

import dataclasses
import io
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from jarvis.adapters.llamaswap import LlamaSwapAdapter
from jarvis.adapters.types import SwapStatus
from jarvis.config.settings import JarvisConfig
from jarvis.tools import CapabilityDescriptor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def stub_registry_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` whose ``stub_capabilities_path`` resolves to
    the canonical 4-entry stub document.

    Mirrors the fixture used in ``tests/test_supervisor_lifecycle_wiring.py``
    so the two suites stay aligned.
    """
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists(), f"Expected stub registry at {stub_path}"

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
        )
    cfg.validate_provider_keys()
    return cfg


# ---------------------------------------------------------------------------
# AC-001 — startup constructs LlamaSwapAdapter from config.llama_swap_base_url
# ---------------------------------------------------------------------------
class TestAC001LlamaSwapAdapterConstruction:
    """``startup`` constructs an ``LlamaSwapAdapter`` from the config URL."""

    @pytest.mark.asyncio
    async def test_llamaswap_adapter_is_attached_to_app_state(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """The returned ``AppState`` carries an ``LlamaSwapAdapter`` instance."""
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.llamaswap_adapter is not None
        assert isinstance(state.llamaswap_adapter, LlamaSwapAdapter)

    @pytest.mark.asyncio
    async def test_llamaswap_adapter_base_url_matches_config(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """The adapter's ``base_url`` reflects ``config.llama_swap_base_url``."""
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.llamaswap_adapter.base_url == stub_registry_config.llama_swap_base_url


# ---------------------------------------------------------------------------
# AC-002 — startup calls build_async_subagents(config) and threads it through
# ---------------------------------------------------------------------------
class TestAC002AsyncSubagentsThreadedThroughBuildSupervisor:
    """``startup`` builds async subagents and passes them to ``build_supervisor``."""

    @pytest.mark.asyncio
    async def test_build_async_subagents_called_with_config(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """``build_async_subagents(config)`` is called exactly once."""
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch("jarvis.infrastructure.lifecycle.build_async_subagents") as mock_build_async,
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            mock_build_async.return_value = []
            await build_app_state(stub_registry_config)

        mock_build_async.assert_called_once_with(stub_registry_config)

    @pytest.mark.asyncio
    async def test_async_subagents_threaded_into_build_supervisor(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """The list returned by ``build_async_subagents`` is forwarded verbatim."""
        from jarvis.infrastructure.lifecycle import build_app_state

        sentinel_subagents = [
            {
                "name": "jarvis-reasoner",
                "description": "stub",
                "graph_id": "jarvis_reasoner",
            }
        ]

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=sentinel_subagents,
            ),
            patch("jarvis.infrastructure.lifecycle.build_supervisor") as mock_build_supervisor,
        ):
            mock_build_supervisor.return_value = MagicMock()
            await build_app_state(stub_registry_config)

        _, kwargs = mock_build_supervisor.call_args
        assert kwargs.get("async_subagents") is sentinel_subagents


# ---------------------------------------------------------------------------
# AC-003 — startup assembles attended + ambient lists and passes ambient_tool_factory
# ---------------------------------------------------------------------------
class TestAC003AttendedAndAmbientToolListsAssembled:
    """``startup`` assembles both attended and ambient tool lists."""

    @pytest.mark.asyncio
    async def test_assemble_tool_list_called_twice_with_proper_kwargs(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """``assemble_tool_list`` is called once with ``include_frontier=True``
        (attended) and once with ``include_frontier=False`` (ambient)."""
        from jarvis.infrastructure.lifecycle import build_app_state

        sentinel_registry = [MagicMock(spec=CapabilityDescriptor)]

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle.load_stub_registry",
                return_value=sentinel_registry,
            ),
            patch("jarvis.infrastructure.lifecycle.assemble_tool_list") as mock_assemble,
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
        ):
            mock_assemble.return_value = []
            await build_app_state(stub_registry_config)

        # Two calls — attended (include_frontier=True) and ambient (=False).
        assert mock_assemble.call_count == 2
        flags = [call.kwargs.get("include_frontier") for call in mock_assemble.call_args_list]
        assert True in flags, "Attended call (include_frontier=True) missing."
        assert False in flags, "Ambient call (include_frontier=False) missing."

        # Each call receives (config, registry) positionally.
        for call in mock_assemble.call_args_list:
            assert call.args == (stub_registry_config, sentinel_registry)

    @pytest.mark.asyncio
    async def test_ambient_tool_factory_returns_ambient_list(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """The ``ambient_tool_factory`` lambda returns the ambient tool list
        (the one assembled with ``include_frontier=False``)."""
        from jarvis.infrastructure.lifecycle import build_app_state

        attended_marker = [MagicMock(name="attended_tool")]
        ambient_marker = [MagicMock(name="ambient_tool")]

        # Return different lists on each call so the test can verify which
        # one ends up exposed via the ambient factory.
        def fake_assemble(
            _config: JarvisConfig,
            _registry: list[CapabilityDescriptor],
            *,
            include_frontier: bool = True,
        ) -> list[Any]:
            return attended_marker if include_frontier else ambient_marker

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle.assemble_tool_list",
                side_effect=fake_assemble,
            ),
            patch("jarvis.infrastructure.lifecycle.build_supervisor") as mock_build_supervisor,
        ):
            mock_build_supervisor.return_value = MagicMock()
            await build_app_state(stub_registry_config)

        _, kwargs = mock_build_supervisor.call_args
        ambient_tool_factory = kwargs.get("ambient_tool_factory")
        assert callable(ambient_tool_factory)
        assert ambient_tool_factory() is ambient_marker

    @pytest.mark.asyncio
    async def test_attended_tool_list_passed_as_tools_kwarg(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """The attended (include_frontier=True) list is the ``tools=`` kwarg."""
        from jarvis.infrastructure.lifecycle import build_app_state

        attended_marker = [MagicMock(name="attended_tool")]
        ambient_marker = [MagicMock(name="ambient_tool")]

        def fake_assemble(
            _config: JarvisConfig,
            _registry: list[CapabilityDescriptor],
            *,
            include_frontier: bool = True,
        ) -> list[Any]:
            return attended_marker if include_frontier else ambient_marker

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle.assemble_tool_list",
                side_effect=fake_assemble,
            ),
            patch("jarvis.infrastructure.lifecycle.build_supervisor") as mock_build_supervisor,
        ):
            mock_build_supervisor.return_value = MagicMock()
            await build_app_state(stub_registry_config)

        _, kwargs = mock_build_supervisor.call_args
        assert kwargs.get("tools") is attended_marker


# ---------------------------------------------------------------------------
# AC-004 — OPENAI_BASE_URL env var set before build_async_subagents
# ---------------------------------------------------------------------------
class TestAC004OpenAIBaseUrlEnvVarSetBeforeAsyncSubagents:
    """``OPENAI_BASE_URL`` is set to ``<llama_swap_base_url>/v1`` before
    ``build_async_subagents`` is called."""

    @pytest.mark.asyncio
    async def test_env_var_set_to_llama_swap_url_with_v1_suffix(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """``os.environ['OPENAI_BASE_URL']`` ends with ``/v1`` after startup."""
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
            patch.dict(os.environ, {}, clear=False),
        ):
            # Explicitly remove any pre-existing var so we test the
            # write path, not a leak from another test.
            os.environ.pop("OPENAI_BASE_URL", None)
            await build_app_state(stub_registry_config)
            base_url = os.environ.get("OPENAI_BASE_URL")

        expected = f"{stub_registry_config.llama_swap_base_url}/v1"
        assert base_url == expected, f"OPENAI_BASE_URL must be {expected!r}, got {base_url!r}"

    @pytest.mark.asyncio
    async def test_env_var_set_before_build_async_subagents_runs(
        self, stub_registry_config: JarvisConfig
    ) -> None:
        """``OPENAI_BASE_URL`` is set BEFORE ``build_async_subagents`` is called."""
        from jarvis.infrastructure.lifecycle import build_app_state

        captured_env_value: dict[str, str | None] = {}

        def _capture_env_at_call_time(
            _config: JarvisConfig,
        ) -> list[Any]:
            captured_env_value["value"] = os.environ.get("OPENAI_BASE_URL")
            return []

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                side_effect=_capture_env_at_call_time,
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("OPENAI_BASE_URL", None)
            await build_app_state(stub_registry_config)

        expected = f"{stub_registry_config.llama_swap_base_url}/v1"
        assert captured_env_value.get("value") == expected, (
            f"OPENAI_BASE_URL must be {expected!r} at the moment "
            f"build_async_subagents is called, got "
            f"{captured_env_value.get('value')!r}"
        )


# ---------------------------------------------------------------------------
# AC-005 — AppState carries llamaswap_adapter
# ---------------------------------------------------------------------------
class TestAC005AppStateCarriesLlamaSwapAdapter:
    """``AppState`` exposes a ``llamaswap_adapter`` field."""

    def test_field_present_on_dataclass(self) -> None:
        """``llamaswap_adapter`` is a declared dataclass field."""
        from jarvis.infrastructure.lifecycle import AppState

        field_names = {f.name for f in dataclasses.fields(AppState)}
        assert "llamaswap_adapter" in field_names

    def test_field_type_annotation_is_llamaswap_adapter(self) -> None:
        """The field's type annotation references ``LlamaSwapAdapter``."""
        from jarvis.infrastructure.lifecycle import AppState

        # ``__annotations__`` may be a string when ``from __future__ import
        # annotations`` is in effect — accept either the class object or
        # the textual form.
        annotations = AppState.__annotations__
        ann = annotations.get("llamaswap_adapter")
        assert ann is not None
        if isinstance(ann, str):
            assert "LlamaSwapAdapter" in ann
        else:
            assert ann is LlamaSwapAdapter or LlamaSwapAdapter in getattr(ann, "__args__", ())


# ---------------------------------------------------------------------------
# AC-006 — should_emit_voice_ack boundary table
# ---------------------------------------------------------------------------
class TestAC006ShouldEmitVoiceAckBoundaryTable:
    """``should_emit_voice_ack`` boundary behaviour: ETA 0/30 → False; 31/240 → True."""

    @pytest.mark.parametrize(
        ("eta_seconds", "expected"),
        [
            (0, False),
            (30, False),
            (31, True),
            (240, True),
        ],
    )
    def test_boundary_table_for_voice_reactive_adapter(
        self, eta_seconds: int, expected: bool
    ) -> None:
        """For a voice-reactive adapter (``reachy``), the boundary table holds."""
        from jarvis.infrastructure.lifecycle import should_emit_voice_ack

        status = SwapStatus(
            loaded_model="jarvis-reasoner",
            eta_seconds=eta_seconds,
            source="stub",
        )

        assert should_emit_voice_ack("reachy", status) is expected

    def test_non_voice_reactive_adapter_never_triggers(self) -> None:
        """A non-voice-reactive adapter (``cli``) never emits, regardless of ETA."""
        from jarvis.infrastructure.lifecycle import should_emit_voice_ack

        status = SwapStatus(
            loaded_model="jarvis-reasoner",
            eta_seconds=240,
            source="stub",
        )
        assert should_emit_voice_ack("cli", status) is False
        assert should_emit_voice_ack("telegram", status) is False
        assert should_emit_voice_ack("dashboard", status) is False

    def test_custom_voice_reactive_set_overrides_default(self) -> None:
        """Caller can pass a ``voice_reactive_adapters`` override."""
        from jarvis.infrastructure.lifecycle import should_emit_voice_ack

        status = SwapStatus(
            loaded_model="jarvis-reasoner",
            eta_seconds=120,
            source="stub",
        )
        # ``cli`` is not in the default set — but the override puts it in.
        assert (
            should_emit_voice_ack(
                "cli",
                status,
                voice_reactive_adapters=frozenset({"cli"}),
            )
            is True
        )


# ---------------------------------------------------------------------------
# AC-007 — when should_emit_voice_ack returns True, supervisor emits TTS ack
# and queues the request for dispatch
# ---------------------------------------------------------------------------
class TestAC007EmitVoiceAckAndQueue:
    """When the policy fires, the ack stub is emitted and the request is queued."""

    def test_emit_returns_emitted_and_queued_flags_when_eta_above_threshold(
        self,
    ) -> None:
        """ETA=240 on ``reachy`` → ``emitted=True`` and ``queued=True``."""
        from jarvis.infrastructure.lifecycle import emit_voice_ack_and_queue

        status = SwapStatus(
            loaded_model="jarvis-reasoner",
            eta_seconds=240,
            source="stub",
        )
        outcome = emit_voice_ack_and_queue("reachy", status)

        assert outcome.emitted is True
        assert outcome.queued is True
        assert isinstance(outcome.ack_text, str)
        assert outcome.ack_text  # non-empty TTS ack stub

    def test_emit_does_not_fire_when_eta_below_threshold(self) -> None:
        """ETA=30 on ``reachy`` → ``emitted=False`` and ``queued=False``."""
        from jarvis.infrastructure.lifecycle import emit_voice_ack_and_queue

        status = SwapStatus(
            loaded_model="jarvis-reasoner",
            eta_seconds=30,
            source="stub",
        )
        outcome = emit_voice_ack_and_queue("reachy", status)

        assert outcome.emitted is False
        assert outcome.queued is False
        assert outcome.ack_text is None

    def test_emit_does_not_fire_for_non_voice_reactive_adapter(self) -> None:
        """``cli`` adapter at ETA=240 → no ack, no queueing."""
        from jarvis.infrastructure.lifecycle import emit_voice_ack_and_queue

        status = SwapStatus(
            loaded_model="jarvis-reasoner",
            eta_seconds=240,
            source="stub",
        )
        outcome = emit_voice_ack_and_queue("cli", status)

        assert outcome.emitted is False
        assert outcome.queued is False
        assert outcome.ack_text is None


# ---------------------------------------------------------------------------
# AC-008 — Phase 1 + FEAT-J002 startup behaviour preserved
# ---------------------------------------------------------------------------
class TestAC008Phase1AndFeatJ002BehaviourPreserved:
    """Existing AppState fields are still wired and non-None after startup."""

    @pytest.mark.asyncio
    async def test_existing_app_state_fields_remain_wired(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        """``config``, ``supervisor``, ``store``, ``session_manager``,
        ``capability_registry`` are all populated."""
        from jarvis.infrastructure.lifecycle import build_app_state

        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.agents.supervisor.init_chat_model",
                return_value=fake_llm,
            ),
        ):
            state = await build_app_state(stub_registry_config)

        assert state.config is stub_registry_config
        assert state.supervisor is not None
        assert state.store is not None
        assert state.session_manager is not None
        # The 4-entry stub registry shipped at
        # src/jarvis/config/stub_capabilities.yaml.
        assert len(state.capability_registry) == 4


# ---------------------------------------------------------------------------
# AC (TASK-J003-FIX-001) — DDR-014 Layer 2 hooks are wired by build_app_state.
# ---------------------------------------------------------------------------
class TestLayer2HooksWiredByBuildAppState:
    """``build_app_state`` populates the dispatch module's Layer-2 hooks.

    FEAT-JARVIS-003 review Finding F1: ``_current_session_hook`` and
    ``_async_subagent_frame_hook`` were dormant in production. The fix
    (TASK-J003-FIX-001) wires both during startup so the constitutional
    ``escalate_to_frontier`` gate runs all three layers (prompt +
    executor assertion + registration absence) instead of two.
    """

    @pytest.mark.asyncio
    async def test_current_session_hook_is_assigned(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state, shutdown
        from jarvis.tools import dispatch

        original_session_hook = dispatch._current_session_hook
        original_frame_hook = dispatch._async_subagent_frame_hook
        try:
            with (
                patch("sys.stderr", new=io.StringIO()),
                patch(
                    "jarvis.agents.supervisor.init_chat_model",
                    return_value=fake_llm,
                ),
            ):
                state = await build_app_state(stub_registry_config)
                assert dispatch._current_session_hook is not None, (
                    "build_app_state must wire dispatch._current_session_hook "
                    "(TASK-J003-FIX-001 / Finding F1)."
                )
                # Idle state: no session driving a turn → resolver returns None.
                assert dispatch._current_session_hook() is None
                await shutdown(state)
        finally:
            dispatch._current_session_hook = original_session_hook
            dispatch._async_subagent_frame_hook = original_frame_hook

    @pytest.mark.asyncio
    async def test_async_subagent_frame_hook_is_assigned_per_assum_frontier_caller_frame(
        self, stub_registry_config: JarvisConfig, fake_llm: Any
    ) -> None:
        from jarvis.infrastructure.lifecycle import build_app_state, shutdown
        from jarvis.tools import dispatch

        original_session_hook = dispatch._current_session_hook
        original_frame_hook = dispatch._async_subagent_frame_hook
        try:
            with (
                patch("sys.stderr", new=io.StringIO()),
                patch(
                    "jarvis.agents.supervisor.init_chat_model",
                    return_value=fake_llm,
                ),
            ):
                state = await build_app_state(stub_registry_config)
                hook = dispatch._async_subagent_frame_hook
                assert hook is not None, (
                    "build_app_state must wire dispatch._async_subagent_frame_hook "
                    "even when middleware metadata is unavailable — the hook "
                    "must exist so Layer 2 emerges from its dormant state."
                )
                # ASSUM-FRONTIER-CALLER-FRAME — DeepAgents 0.5.3 does not
                # expose the metadata, so the wired hook returns None and
                # Layer 2 falls through to the session-state fallback.
                assert hook() is None
                await shutdown(state)
        finally:
            dispatch._current_session_hook = original_session_hook
            dispatch._async_subagent_frame_hook = original_frame_hook
