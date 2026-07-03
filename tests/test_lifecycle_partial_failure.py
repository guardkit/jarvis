"""Cross-product soft-fail tests — DDR-019 + DDR-021 (TASK-J004-016).

Three lifecycle scenarios that combine the NATS-down (DDR-021) and
Memory-down (DDR-019) invariants on the same supervisor:

* **NATS up + Memory down** — dispatches succeed end-to-end against the
  mocked broker; trace persistence is skipped and the writer emits one
  ``WARN routing_history_write_failed`` per writer instance.
* **NATS down + Memory up** — dispatches return
  ``DEGRADED: transport_unavailable``; no specialist round-trip occurs.
* **Both down** — Jarvis still starts. ``escalate_to_frontier`` (the
  attended-only escape), the ``jarvis-reasoner`` AsyncSubAgent, and the
  Phase 2 deterministic tools (no NATS / Memory dependency) remain
  functional. Demo-day robustness gate.

Every scenario asserts process-still-alive at the end. WARN assertions
go through ``caplog.records`` filtered on the routing-history logger
name and ``WARNING`` level — never via stderr / stdout matching.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.lifecycle import AppState, build_app_state
from jarvis.infrastructure.routing_history import (
    ConcurrentWorkloadSnapshot,
    JarvisRoutingHistoryEntry,
    RoutingHistoryWriter,
)
from jarvis.shared.constants import Adapter
from jarvis.tools import dispatch as dispatch_module
from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
)
from jarvis.tools.dispatch import dispatch_by_capability, escalate_to_frontier
from jarvis.tools.dispatch_types import FrontierTarget

ROUTING_HISTORY_LOGGER = "jarvis.infrastructure.routing_history"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _stub_yaml_path() -> Path:
    return _project_root() / "src" / "jarvis" / "config" / "stub_capabilities.yaml"


@pytest.fixture()
def cross_product_config(tmp_path: Path) -> JarvisConfig:
    """A :class:`JarvisConfig` suitable for the partial-failure scenarios."""
    stub_path = _stub_yaml_path()
    assert stub_path.exists()

    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            stub_capabilities_path=stub_path,
            llama_swap_base_url="http://fake-llama-swap:9000",
            fleet_memory_enabled=True,
            jarvis_traces_dir=tmp_path / "traces",
            nats_url="nats://203.0.113.1:4222",
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def bound_capability_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a deterministic single-specialist registry into the dispatch seam."""
    saved = dispatch_module._capability_registry
    registry = [
        CapabilityDescriptor(
            agent_id="product-owner",
            role="Product Owner",
            description="Reviews specs against acceptance criteria.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="review_spec",
                    description="Review a feature spec",
                    risk_level="read_only",
                ),
            ],
        ),
    ]
    dispatch_module._capability_registry = registry
    try:
        yield registry
    finally:
        dispatch_module._capability_registry = saved


def _routing_history_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Filter ``caplog.records`` to the routing-history logger at WARNING+."""
    return [
        record
        for record in caplog.records
        if record.name == ROUTING_HISTORY_LOGGER and record.levelno == logging.WARNING
    ]


def _make_entry(decision_id: str = "11111111-2222-4333-8444-555555555555") -> JarvisRoutingHistoryEntry:
    return JarvisRoutingHistoryEntry(
        decision_id=decision_id,
        session_id="sess-cross-product",
        timestamp=datetime.now(UTC),
        supervisor_tool_call_sequence=[],
        capability_snapshot_hash="0" * 64,
        subagent_type="specialist",
        subagent_task_id="corr-cross-product",
        subagent_final_state="success",
        wall_clock_ms=42,
        total_cost_usd=0.0,
        outcome_type="success",
        local_time_of_day="12:00",
        concurrent_workload=ConcurrentWorkloadSnapshot(
            in_flight_dispatches=0,
            in_flight_watchers=0,
            in_flight_subagents=0,
        ),
        supervisor_reasoning_summary="ok",
    )


def _assert_process_alive(state: AppState) -> None:
    assert state is not None
    assert isinstance(state, AppState)
    assert state.supervisor is not None


# ===========================================================================
# AC: NATS up + Memory down — dispatches succeed; traces lost; WARN
# ===========================================================================
class TestNATSUpMemoryDown:
    """Dispatch round-trips succeed end-to-end; one WARN per writer instance."""

    @pytest.mark.asyncio
    async def test_dispatches_succeed_traces_lost_warn_emitted(
        self,
        cross_product_config: JarvisConfig,
        bound_capability_registry: list[CapabilityDescriptor],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Round-trip succeeds; degraded writer emits a single WARN."""
        from nats_core.events import ResultPayload

        caplog.set_level(logging.WARNING, logger=ROUTING_HISTORY_LOGGER)

        async def _request(subject: str, payload: bytes, *, timeout: float) -> Any:
            del subject, payload, timeout
            success_body = ResultPayload(
                command="review_spec",
                result={"verdict": "ok"},
                correlation_id=None,
                success=True,
            )
            return MagicMock(data=success_body.model_dump_json().encode("utf-8"))

        nats_client = MagicMock()
        nats_client.request = AsyncMock(side_effect=_request)

        # Writer in DDR-019 degraded mode (no Memory client).
        writer = RoutingHistoryWriter(
            memory_client=None,
            config=cross_product_config,
        )

        saved_nats = dispatch_module._nats_client
        saved_writer = dispatch_module._routing_history_writer
        saved_sem = dispatch_module._dispatch_semaphore
        dispatch_module._nats_client = nats_client
        dispatch_module._routing_history_writer = writer
        dispatch_module._dispatch_semaphore = None

        try:
            result = await dispatch_by_capability.ainvoke(
                {"tool_name": "review_spec", "payload_json": "{}"}
            )
            # Yield twice so the fire-and-forget trace task runs and the
            # writer's WARN-once ratchet fires inside the test scope.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
        finally:
            dispatch_module._nats_client = saved_nats
            dispatch_module._routing_history_writer = saved_writer
            dispatch_module._dispatch_semaphore = saved_sem

        # Dispatch returned the specialist's success payload (real round-trip).
        assert "DEGRADED" not in result
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "review_spec"

        # Trace was attempted; Memory is down so the writer offloaded
        # to <traces_dir>/<correlation_id>.json per TASK-FRR-003 instead
        # of dropping the trace on the floor. The structured WARN now
        # carries the local-offload contract — see TestRatchetWarnOnceThenSilent
        # in tests/test_memory_unavailable.py for the full contract.
        warnings = _routing_history_warnings(caplog)
        offloaded = [
            rec
            for rec in warnings
            if rec.getMessage() == "routing_history_offloaded_locally"
        ]
        assert len(offloaded) == 1, (
            f"Expected one routing_history_offloaded_locally WARN per "
            f"dispatch (TASK-FRR-003 supersedes the warn-once ratchet), "
            f"got {len(offloaded)}"
        )
        # The dispatch-side trace is no longer "lost" — it lives at
        # <traces_dir>/<correlation_id>.json on disk for future
        # rehydration into Memory.
        offload_path = getattr(offloaded[0], "path", None)
        assert offload_path is not None, (
            "routing_history_offloaded_locally must carry the on-disk path"
        )
        from pathlib import Path as _Path
        assert _Path(offload_path).exists(), (
            f"Soft-fail offload file must exist on disk: {offload_path}"
        )


# ===========================================================================
# AC: NATS down + Memory up — dispatches return DEGRADED; no specialist hops
# ===========================================================================
class TestNATSDownMemoryUp:
    """Dispatches surface DEGRADED transport; no specialist round-trip occurs."""

    @pytest.mark.asyncio
    async def test_dispatches_return_degraded(
        self,
        cross_product_config: JarvisConfig,
        bound_capability_registry: list[CapabilityDescriptor],
    ) -> None:
        """``dispatch_by_capability`` returns the DDR-021 DEGRADED string."""
        # Memory is "up" — give the writer a connected (mocked) client.
        fake_memory = MagicMock()
        fake_memory.add_episode = AsyncMock(return_value=None)
        writer = RoutingHistoryWriter(
            memory_client=fake_memory,
            config=cross_product_config,
        )

        saved_nats = dispatch_module._nats_client
        saved_writer = dispatch_module._routing_history_writer
        saved_sem = dispatch_module._dispatch_semaphore
        dispatch_module._nats_client = None  # NATS down — DDR-021 branch.
        dispatch_module._routing_history_writer = writer
        dispatch_module._dispatch_semaphore = None

        try:
            result = await dispatch_by_capability.ainvoke(
                {"tool_name": "review_spec", "payload_json": "{}"}
            )
            await asyncio.sleep(0)
        finally:
            dispatch_module._nats_client = saved_nats
            dispatch_module._routing_history_writer = saved_writer
            dispatch_module._dispatch_semaphore = saved_sem

        assert result == "DEGRADED: transport_unavailable — NATS connection failed"
        # No specialist round-trip occurred — Memory would only see the
        # diagnostic transport_unavailable trace, never a "success" entry.
        # Inspect the sole add_episode call (if any) and assert outcome_type.
        if fake_memory.add_episode.await_count > 0:
            kwargs = fake_memory.add_episode.await_args.kwargs
            episode_body = json.loads(kwargs["episode_body"])
            assert episode_body["outcome_type"] == "transport_unavailable", (
                "Only the transport_unavailable diagnostic trace may be written; "
                "no successful specialist trace is permitted on NATS-down path"
            )


# ===========================================================================
# AC: both down — Jarvis still starts; attended-only escape + local subagents
# ===========================================================================
class TestBothNATSAndMemoryDown:
    """Demo-day gate: supervisor stays usable when both transports degrade."""

    @pytest.mark.asyncio
    async def test_jarvis_still_starts_attended_escape_local_subagent_phase2_tools(
        self,
        cross_product_config: JarvisConfig,
    ) -> None:
        """Supervisor builds; frontier escape returns; nothing crashed."""
        from jarvis.tools import general

        # ---- Startup with both transports degraded --------------------------
        with (
            patch("sys.stderr", new=io.StringIO()),
            patch(
                "jarvis.infrastructure.lifecycle._connect_nats",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle._connect_memory",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_supervisor",
                return_value=MagicMock(),
            ),
            patch(
                "jarvis.infrastructure.lifecycle.build_async_subagents",
                return_value=[MagicMock(name="jarvis-reasoner")],
            ) as mock_async_sub,
        ):
            state = await build_app_state(cross_product_config)

        # Lifecycle invariants under both-down: no NATS, no Memory, but the
        # writer + the local AsyncSubAgent list still wired.
        assert state.nats_client is None
        assert state.memory_client is None
        assert state.fleet_heartbeat_task is None
        assert isinstance(state.routing_history_writer, RoutingHistoryWriter)
        assert state.routing_history_writer._memory_client is None
        # AsyncSubAgent list (jarvis-reasoner local subagent) was built.
        mock_async_sub.assert_called_once()
        _assert_process_alive(state)

        # ---- Attended-only frontier escape still works ---------------------
        attended_session = MagicMock()
        attended_session.adapter = Adapter.CLI
        attended_session.metadata = {"currently_in_subagent": False}

        saved_session_hook = dispatch_module._current_session_hook
        dispatch_module._current_session_hook = lambda: attended_session
        try:
            gemini_response = MagicMock()
            gemini_response.text = "frontier-canned-reply"
            gemini_client = MagicMock()
            gemini_client.models.generate_content.return_value = gemini_response

            with (
                patch.dict("os.environ", {"GOOGLE_API_KEY": "fake"}, clear=True),
                patch("google.genai.Client", return_value=gemini_client),
            ):
                escape_reply = escalate_to_frontier.invoke(
                    {
                        "instruction": "demo-day-fallback",
                        "target": FrontierTarget.GEMINI_3_1_PRO,
                    }
                )
        finally:
            dispatch_module._current_session_hook = saved_session_hook

        assert escape_reply == "frontier-canned-reply"

        # ---- Phase 2 deterministic tool still functional --------------------
        # ``calculate`` has no NATS / Memory dependency — DDR-019/021
        # soft-fail must not affect it.
        deterministic_result = general.calculate.invoke({"expression": "2 + 2"})
        # Tool returns either a JSON string or the answer string; both must be
        # truthy and not start with ERROR.
        assert isinstance(deterministic_result, str)
        assert not deterministic_result.startswith("ERROR")
        assert "4" in deterministic_result

        _assert_process_alive(state)
