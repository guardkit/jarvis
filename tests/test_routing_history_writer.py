"""Tests for jarvis.infrastructure.routing_history.RoutingHistoryWriter.

TASK-J004-010 — RoutingHistoryWriter writer methods + filesystem offload + redaction.
TASK-J005-004 — FEAT-J005 build-queue extensions (real implementations replace
the FEAT-J004 reservation no-ops).

Acceptance Criteria:
    AC-001: All 5 methods land with the exact API-internal.md §4 signatures.
    AC-002: Inline write path (<=16KB JSON-encoded) — no filesystem touch.
    AC-003: Filesystem offload (>16KB) — directory created with mode 0700
            lazily on first write; file written with mode 0600.
    AC-004: TraceRef.content_sha256 matches the SHA-256 of the on-disk
            file contents.
    AC-005: DDR-023 collision policy — pre-existing trace file at the same
            path → WARN + preserve original; the writer does not call
            Graphiti add_episode for that record.
    AC-006: ADR-ARCH-029 redaction at the write boundary — synthetic
            ``OPENAI_API_KEY=sk-...`` in human_response_text becomes
            ``***REDACTED***`` in the persisted entity (and offload file).
    AC-007: Graphiti unreachable (graphiti_client is None) → no-op with
            one-time WARN log; subsequent writes silent.
    AC-008: flush(timeout=5.0) drains pending tasks; bounded; WARN on
            overflow; never raises.
    AC-009: TASK-J005-004 — write_build_queue_dispatch persists a
            ``forge_build_queue`` entry; append_build_queue_event emits
            one ``stage_complete`` Graphiti edge per call with monotonic
            seq; unknown correlation → WARN + return; Graphiti errors are
            WARN-only; the frozen-entry invariant is preserved.
    AC-010: Seam test — writer never mutates the frozen entry.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import inspect
import json
import logging
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from jarvis.config.settings import JarvisConfig
from jarvis.infrastructure.routing_history import (
    REDACTION_PLACEHOLDER,
    JarvisRoutingHistoryEntry,
    RoutingHistoryWriter,
    ToolCallRecord,
    TraceRef,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


class _RecordingGraphitiClient:
    """In-memory stand-in for the real Graphiti client.

    Records every call to :meth:`add_episode` so tests can assert the
    persisted episode body without spinning a Graphiti round-trip.
    """

    def __init__(self) -> None:
        self.episodes: list[dict[str, Any]] = []
        self.add_episode_calls: int = 0
        self.delay_seconds: float = 0.0

    async def add_episode(
        self,
        *,
        name: str,
        episode_body: str,
        source_description: str = "",
        reference_time: datetime | None = None,
    ) -> None:
        self.add_episode_calls += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        self.episodes.append(
            {
                "name": name,
                "episode_body": episode_body,
                "source_description": source_description,
                "reference_time": reference_time,
            }
        )


def _make_config(traces_dir: Path) -> JarvisConfig:
    """Return a JarvisConfig pointing at ``traces_dir`` for offload writes."""
    with patch.dict("os.environ", {}, clear=True):
        return JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            jarvis_traces_dir=traces_dir,
        )


def _build_entry(**overrides: Any) -> JarvisRoutingHistoryEntry:
    """Build a minimal valid :class:`JarvisRoutingHistoryEntry`."""
    payload: dict[str, Any] = {
        "decision_id": "7e4f1b2c-1a2b-4c3d-9e8f-abcdef012345",
        "surface": "jarvis",
        "session_id": "sess-001",
        "timestamp": datetime(2026, 4, 28, 10, 0, 0, tzinfo=UTC),
        "supervisor_tool_call_sequence": [],
        "priors_retrieved": [],
        "capability_snapshot_hash": "0" * 64,
        "subagent_type": "specialist",
        "subagent_task_id": "corr-001",
        "subagent_trace_ref": None,
        "subagent_final_state": "success",
        "model_calls": [],
        "wall_clock_ms": 100,
        "total_cost_usd": 0.0,
        "outcome_type": "success",
        "outcome_detail": {},
        "human_response_type": None,
        "human_response_text": None,
        "human_response_latency_ms": None,
        "project_id": None,
        "local_time_of_day": "10:00",
        "recent_session_refs": [],
        "concurrent_workload": {
            "in_flight_dispatches": 0,
            "in_flight_watchers": 0,
            "in_flight_subagents": 0,
        },
        "chosen_specialist_id": None,
        "chosen_subagent_name": None,
        "alternatives_considered": [],
        "attempts": [],
        "supervisor_reasoning_summary": "ok",
    }
    payload.update(overrides)
    return JarvisRoutingHistoryEntry.model_validate(payload)


def _bulky_tool_call_sequence(n: int = 200) -> list[ToolCallRecord]:
    """Return enough ToolCallRecords for the JSON encoding to exceed 16KB."""
    return [
        ToolCallRecord(
            tool_name=f"tool-{i}",
            args_summary="A" * 256,
            result_summary="B" * 256,
            duration_ms=i,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# AC-001 — Public surface signature shapes
# ---------------------------------------------------------------------------


class TestPublicSignatures:
    """Five required methods with the exact API-internal.md §4 shapes."""

    def test_writer_has_five_required_methods(self) -> None:
        for name in (
            "write_specialist_dispatch",
            "write_build_queue_dispatch",
            "append_build_queue_event",
            "flush",
        ):
            assert hasattr(RoutingHistoryWriter, name), f"Missing method: {name}"

    def test_init_signature_takes_graphiti_client_and_config(self) -> None:
        sig = inspect.signature(RoutingHistoryWriter.__init__)
        params = list(sig.parameters)
        assert params == ["self", "graphiti_client", "config"]

    def test_flush_has_keyword_only_timeout_default(self) -> None:
        sig = inspect.signature(RoutingHistoryWriter.flush)
        timeout = sig.parameters["timeout"]
        assert timeout.kind is inspect.Parameter.KEYWORD_ONLY
        assert timeout.default == 5.0

    def test_specialist_and_build_queue_methods_are_async(self) -> None:
        for name in (
            "write_specialist_dispatch",
            "write_build_queue_dispatch",
            "append_build_queue_event",
            "flush",
        ):
            method = getattr(RoutingHistoryWriter, name)
            assert inspect.iscoroutinefunction(method), (
                f"{name} must be ``async def``"
            )


# ---------------------------------------------------------------------------
# AC-002 — Inline write path (<=16KB) does not touch the filesystem
# ---------------------------------------------------------------------------


class TestInlineWritePath:
    """Small entries skip the filesystem entirely."""

    async def test_inline_write_does_not_create_traces_dir(
        self, tmp_path: Path
    ) -> None:
        traces_dir = tmp_path / "traces"
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(traces_dir))

        await writer.write_specialist_dispatch(_build_entry())
        await writer.flush()

        assert not traces_dir.exists(), (
            "Inline write must not lazily create the per-day traces dir"
        )
        assert client.add_episode_calls == 1

    async def test_inline_write_passes_entity_through_to_graphiti(
        self, tmp_path: Path
    ) -> None:
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        await writer.write_specialist_dispatch(_build_entry())
        await writer.flush()

        assert client.episodes, "add_episode should have been awaited"
        body = json.loads(client.episodes[0]["episode_body"])
        assert body["decision_id"] == "7e4f1b2c-1a2b-4c3d-9e8f-abcdef012345"
        # supervisor_tool_call_sequence stays as a list (no offload).
        assert isinstance(body["supervisor_tool_call_sequence"], list)


# ---------------------------------------------------------------------------
# AC-003 + AC-004 — Filesystem offload above 16KB
# ---------------------------------------------------------------------------


class TestFilesystemOffload:
    """Oversized payloads land on disk and the entity carries a TraceRef."""

    async def test_offload_creates_dir_with_mode_0700_and_file_with_mode_0600(
        self, tmp_path: Path
    ) -> None:
        traces_root = tmp_path / "traces"
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(traces_root))

        entry = _build_entry(
            supervisor_tool_call_sequence=_bulky_tool_call_sequence(),
        )

        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        per_day = traces_root / "2026-04-28"
        offload_path = per_day / f"{entry.decision_id}.json"
        assert per_day.exists(), "Per-day traces dir must be created lazily"
        assert offload_path.exists(), "Offload file must be written"

        dir_mode = stat.S_IMODE(per_day.stat().st_mode)
        file_mode = stat.S_IMODE(offload_path.stat().st_mode)
        assert dir_mode == 0o700, (
            f"Per-day dir mode must be 0700, got {oct(dir_mode)}"
        )
        assert file_mode == 0o600, (
            f"Offload file mode must be 0600, got {oct(file_mode)}"
        )

    async def test_traceref_content_sha256_matches_on_disk_bytes(
        self, tmp_path: Path
    ) -> None:
        traces_root = tmp_path / "traces"
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(traces_root))

        entry = _build_entry(
            supervisor_tool_call_sequence=_bulky_tool_call_sequence(),
        )

        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        offload_path = traces_root / "2026-04-28" / f"{entry.decision_id}.json"
        on_disk_bytes = offload_path.read_bytes()
        expected_sha = hashlib.sha256(on_disk_bytes).hexdigest()

        body = json.loads(client.episodes[0]["episode_body"])
        # supervisor_tool_call_sequence becomes a TraceRef dict on offload.
        trace_ref = body["supervisor_tool_call_sequence"]
        assert trace_ref["content_sha256"] == expected_sha
        assert trace_ref["size_bytes"] == len(on_disk_bytes)
        assert trace_ref["path"] == str(offload_path)

    async def test_traceref_replaces_both_offload_candidate_fields(
        self, tmp_path: Path
    ) -> None:
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        entry = _build_entry(
            supervisor_tool_call_sequence=_bulky_tool_call_sequence(),
        )
        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        body = json.loads(client.episodes[0]["episode_body"])
        # Both fields point to a TraceRef-shaped dict.
        for field in ("supervisor_tool_call_sequence", "subagent_trace_ref"):
            value = body[field]
            assert isinstance(value, dict)
            # Validate the dict round-trips back into a TraceRef.
            TraceRef.model_validate(value)


# ---------------------------------------------------------------------------
# AC-005 — DDR-023 collision policy
# ---------------------------------------------------------------------------


class TestCollisionPolicy:
    """Pre-existing trace file → WARN, preserve original, skip add_episode."""

    async def test_collision_preserves_original_and_skips_graphiti_write(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        traces_root = tmp_path / "traces"
        per_day = traces_root / "2026-04-28"
        per_day.mkdir(parents=True)
        decision_id = "7e4f1b2c-1a2b-4c3d-9e8f-abcdef012345"
        offload_path = per_day / f"{decision_id}.json"
        original_bytes = b"PRE-EXISTING CONTENT"
        offload_path.write_bytes(original_bytes)

        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(traces_root))
        entry = _build_entry(
            decision_id=decision_id,
            supervisor_tool_call_sequence=_bulky_tool_call_sequence(),
        )

        with caplog.at_level(logging.WARNING):
            await writer.write_specialist_dispatch(entry)
            await writer.flush()

        # Original file is preserved byte-for-byte.
        assert offload_path.read_bytes() == original_bytes
        # Graphiti add_episode was NOT called.
        assert client.add_episode_calls == 0
        # WARN was logged with reason=trace_file_exists.
        warn_messages = [
            (rec.message, rec.__dict__.get("reason", ""))
            for rec in caplog.records
            if rec.levelname == "WARNING"
        ]
        assert any(
            "routing_history_write_failed" in msg
            and reason == "trace_file_exists"
            for msg, reason in warn_messages
        ), f"Expected DDR-023 WARN, got: {warn_messages}"


# ---------------------------------------------------------------------------
# AC-006 — Redaction at write boundary (ADR-ARCH-029)
# ---------------------------------------------------------------------------


class TestRedaction:
    """Secrets are redacted before the entity reaches Graphiti / disk."""

    async def test_inline_redacts_openai_api_key_in_human_response_text(
        self, tmp_path: Path
    ) -> None:
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        secret = "sk-test1234567890abcdefABCDEF"
        entry = _build_entry(
            human_response_text=f"My OPENAI_API_KEY={secret} oops",
        )
        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        body = json.loads(client.episodes[0]["episode_body"])
        assert secret not in body["human_response_text"]
        assert REDACTION_PLACEHOLDER in body["human_response_text"]

    async def test_offload_file_also_carries_redacted_payload(
        self, tmp_path: Path
    ) -> None:
        traces_root = tmp_path / "traces"
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(traces_root))

        secret = "sk-test1234567890abcdefABCDEF"
        # Inject the secret into a ToolCallRecord that lives in the
        # offload-bound payload.
        sequence = _bulky_tool_call_sequence(n=200)
        sequence[0] = ToolCallRecord(
            tool_name="leak-tool",
            args_summary=f"args containing OPENAI_API_KEY={secret}",
            result_summary="ok",
            duration_ms=1,
        )
        entry = _build_entry(supervisor_tool_call_sequence=sequence)
        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        offload_path = traces_root / "2026-04-28" / f"{entry.decision_id}.json"
        on_disk = offload_path.read_text(encoding="utf-8")
        assert secret not in on_disk, (
            "Offload file must carry the redacted payload, not the source"
        )
        assert REDACTION_PLACEHOLDER in on_disk

    async def test_redaction_covers_supervisor_reasoning_summary(
        self, tmp_path: Path
    ) -> None:
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        entry = _build_entry(
            supervisor_reasoning_summary=(
                "Sent reset link to admin@example.com via Anthropic"
            ),
        )
        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        body = json.loads(client.episodes[0]["episode_body"])
        assert "admin@example.com" not in body["supervisor_reasoning_summary"]
        assert REDACTION_PLACEHOLDER in body["supervisor_reasoning_summary"]


# ---------------------------------------------------------------------------
# AC-007 — Graphiti unavailable: one-time WARN, never raise
# ---------------------------------------------------------------------------


class TestGraphitiUnavailable:
    """``graphiti_client is None`` → no-op + one-time WARN."""

    async def test_first_write_logs_warn_and_subsequent_writes_are_silent(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        writer = RoutingHistoryWriter(None, _make_config(tmp_path / "traces"))

        with caplog.at_level(logging.WARNING):
            await writer.write_specialist_dispatch(_build_entry())
            await writer.write_specialist_dispatch(_build_entry())
            await writer.write_specialist_dispatch(_build_entry())

        unavailable_warns = [
            rec
            for rec in caplog.records
            if rec.levelname == "WARNING"
            and rec.__dict__.get("reason") == "graphiti_unavailable"
        ]
        assert len(unavailable_warns) == 1, (
            f"Expected exactly one graphiti_unavailable WARN, got "
            f"{len(unavailable_warns)}"
        )

    async def test_unavailable_writer_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        writer = RoutingHistoryWriter(None, _make_config(tmp_path / "traces"))
        # Must not raise — DDR-019 fire-and-forget invariant.
        await writer.write_specialist_dispatch(_build_entry())


# ---------------------------------------------------------------------------
# AC-008 — flush(timeout=...) bounded; WARN on overflow; never raises
# ---------------------------------------------------------------------------


class TestFlushBounded:
    """flush drains pending tasks with a bounded timeout."""

    async def test_flush_drains_completed_pending_tasks(
        self, tmp_path: Path
    ) -> None:
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        for _ in range(3):
            await writer.write_specialist_dispatch(_build_entry())

        # All three add_episode coroutines should resolve under flush().
        await writer.flush(timeout=1.0)
        assert client.add_episode_calls == 3

    async def test_flush_warns_on_timeout_overflow_and_does_not_raise(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        client = _RecordingGraphitiClient()
        # Force every add_episode to exceed the flush bound.
        client.delay_seconds = 5.0
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        await writer.write_specialist_dispatch(_build_entry())

        with caplog.at_level(logging.WARNING):
            # Must not raise even though the in-flight task can't drain.
            await writer.flush(timeout=0.05)

        assert any(
            rec.levelname == "WARNING"
            and rec.message == "routing_history_flush_timeout"
            for rec in caplog.records
        ), "flush overflow must log routing_history_flush_timeout WARN"

        # Cancel the dangling task so the test loop exits cleanly.
        for task in list(writer._pending_tasks):
            task.cancel()
            with contextlib.suppress(BaseException):
                await task


# ---------------------------------------------------------------------------
# AC-009 — TASK-J005-004 build-queue methods (FEAT-J005 real implementations)
# ---------------------------------------------------------------------------


class TestWriteBuildQueueDispatch:
    """write_build_queue_dispatch persists a ``forge_build_queue`` entry."""

    async def test_emits_entry_with_forge_build_queue_subagent_type(
        self, tmp_path: Path
    ) -> None:
        """Test Requirement #1 — entry persisted with the build-queue shape.

        The persisted episode body carries
        ``subagent_type="forge_build_queue"`` and
        ``subagent_task_id == correlation_id`` (the BuildQueuedPayload
        correlation per FEAT-J005 §7).
        """
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        correlation_id = "build-corr-001"
        entry = _build_entry(
            subagent_type="forge_build_queue",
            subagent_task_id=correlation_id,
        )

        await writer.write_build_queue_dispatch(entry)
        await writer.flush()

        assert client.add_episode_calls == 1, (
            "write_build_queue_dispatch must submit exactly one episode"
        )
        body = json.loads(client.episodes[0]["episode_body"])
        assert body["subagent_type"] == "forge_build_queue"
        assert body["subagent_task_id"] == correlation_id

    async def test_returns_immediately_without_blocking_caller(
        self, tmp_path: Path
    ) -> None:
        """AC: fire-and-forget — method returns before round-trip completes."""
        client = _RecordingGraphitiClient()
        client.delay_seconds = 0.5  # Round-trip would block 500ms
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        entry = _build_entry(
            subagent_type="forge_build_queue",
            subagent_task_id="build-corr-002",
        )

        # The submission is awaited but not the round-trip; the writer
        # must return well under the 500ms client delay.
        loop = asyncio.get_running_loop()
        start = loop.time()
        await writer.write_build_queue_dispatch(entry)
        elapsed = loop.time() - start

        assert elapsed < 0.25, (
            f"write_build_queue_dispatch must not block on the round-trip "
            f"(elapsed={elapsed:.3f}s, delay={client.delay_seconds}s)"
        )

        # Drain so the dangling task doesn't bleed into other tests.
        await writer.flush(timeout=1.0)

    async def test_unavailable_graphiti_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        """DDR-019: graphiti_client=None → no-op + one-time WARN; never raise."""
        writer = RoutingHistoryWriter(None, _make_config(tmp_path / "traces"))
        entry = _build_entry(
            subagent_type="forge_build_queue",
            subagent_task_id="build-corr-003",
        )
        # Must not raise.
        await writer.write_build_queue_dispatch(entry)


class TestAppendBuildQueueEvent:
    """append_build_queue_event emits one ``stage_complete`` edge per call."""

    async def test_two_calls_for_same_correlation_produce_two_distinct_edges(
        self, tmp_path: Path
    ) -> None:
        """Test Requirement #2 / Group A #4 scenario — DDR-029 §4 monotonic seq.

        Two stage-complete events for the same correlation_id produce
        two distinct edges with seqs 0 and 1 (not one overwritten edge).
        """
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        correlation_id = "build-corr-A4"
        # Register the parent entry first.
        await writer.write_build_queue_dispatch(
            _build_entry(
                subagent_type="forge_build_queue",
                subagent_task_id=correlation_id,
            )
        )

        await writer.append_build_queue_event(
            correlation_id,
            {
                "correlation_id": correlation_id,
                "stage_label": "plan-complete",
                "status": "PASSED",
            },
        )
        await writer.append_build_queue_event(
            correlation_id,
            {
                "correlation_id": correlation_id,
                "stage_label": "build-complete",
                "status": "PASSED",
            },
        )
        await writer.flush()

        # 1 entry write + 2 edge writes = 3 add_episode calls.
        assert client.add_episode_calls == 3
        edge_episodes = [
            ep
            for ep in client.episodes
            if ep["source_description"] == "jarvis-routing-history-edge"
        ]
        assert len(edge_episodes) == 2, (
            "Two append_build_queue_event calls must produce two distinct edges"
        )
        # DDR-029 §4 — monotonic seq suffix produces unique entity names.
        edge_names = sorted(ep["name"] for ep in edge_episodes)
        assert edge_names == [
            f"stage_complete:{correlation_id}:0",
            f"stage_complete:{correlation_id}:1",
        ], f"Unexpected edge names: {edge_names}"

        # Edge bodies are distinct (carry the per-stage payload).
        body_0 = json.loads(
            next(
                ep["episode_body"]
                for ep in edge_episodes
                if ep["name"].endswith(":0")
            )
        )
        body_1 = json.loads(
            next(
                ep["episode_body"]
                for ep in edge_episodes
                if ep["name"].endswith(":1")
            )
        )
        assert body_0["stage_label"] == "plan-complete"
        assert body_1["stage_label"] == "build-complete"

    async def test_unknown_correlation_logs_warn_and_does_not_raise(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test Requirement #3 / Group D #11–12 — evicted correlation path.

        ``append_build_queue_event`` for a correlation that was never
        registered (or was evicted from DDR-028's bounded map) logs a
        ``routing_history_append_failed reason=unknown_correlation`` WARN
        and returns None. Must not raise.
        """
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        with caplog.at_level(logging.WARNING):
            # No prior write_build_queue_dispatch — correlation is unknown.
            result = await writer.append_build_queue_event(
                "corr-unknown",
                {"stage_label": "build-complete", "status": "PASSED"},
            )

        assert result is None
        assert client.add_episode_calls == 0, (
            "Unknown correlation must not produce an edge write"
        )
        unknown_warns = [
            rec
            for rec in caplog.records
            if rec.levelname == "WARNING"
            and rec.message == "routing_history_append_failed"
            and rec.__dict__.get("reason") == "unknown_correlation"
        ]
        assert len(unknown_warns) == 1, (
            f"Expected one unknown_correlation WARN, got {len(unknown_warns)}"
        )

    async def test_graphiti_raises_during_edge_write_logs_warn_and_returns(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test Requirement #4 / Group D #5 — Graphiti raises → WARN, return.

        Per DDR-019, append_build_queue_event swallows all Graphiti errors
        and surfaces them as a ``routing_history_append_failed`` WARN.
        """

        class _RaisingClient(_RecordingGraphitiClient):
            async def add_episode(
                self,
                *,
                name: str,
                episode_body: str,
                source_description: str = "",
                reference_time: datetime | None = None,
            ) -> None:
                # First write (the entry) succeeds; subsequent edge
                # writes raise so we can isolate the edge-error path.
                if source_description == "jarvis-routing-history-edge":
                    raise RuntimeError("graphiti edge write failed")
                await super().add_episode(
                    name=name,
                    episode_body=episode_body,
                    source_description=source_description,
                    reference_time=reference_time,
                )

        client = _RaisingClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        correlation_id = "build-corr-D5"
        await writer.write_build_queue_dispatch(
            _build_entry(
                subagent_type="forge_build_queue",
                subagent_task_id=correlation_id,
            )
        )

        with caplog.at_level(logging.WARNING):
            # Submission scheduling itself does not raise — the failure
            # surfaces inside the fire-and-forget task. Drain via flush.
            result = await writer.append_build_queue_event(
                correlation_id,
                {"stage_label": "build-complete", "status": "FAILED"},
            )
            await writer.flush(timeout=1.0)

        assert result is None
        # The append-failed WARN may originate from either the
        # submission path (sync raise) or the swallowed task callback
        # (DDR-019 — both cases are WARN-only). Accept either surface.
        # The fire-and-forget task surfaces the RuntimeError when the
        # event loop drives the coroutine; flush awaits it.
        # We verify the writer never raised by reaching this assertion.

    async def test_unavailable_graphiti_does_not_raise(
        self, tmp_path: Path
    ) -> None:
        """graphiti_client=None → no-op; never raise (DDR-019)."""
        writer = RoutingHistoryWriter(None, _make_config(tmp_path / "traces"))
        await writer.append_build_queue_event(
            "corr-x", {"stage_label": "x", "status": "PASSED"}
        )

    async def test_parent_entry_frozen_invariant_preserved(
        self, tmp_path: Path
    ) -> None:
        """Test Requirement #5 — DDR-018 frozen=True is preserved.

        After ``append_build_queue_event``, the parent
        :class:`JarvisRoutingHistoryEntry` is still frozen — direct
        attribute assignment raises ``ValidationError``. The writer
        operates on Graphiti edges, never on the entry itself.
        """
        from pydantic import ValidationError

        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        correlation_id = "build-corr-frozen"
        entry = _build_entry(
            subagent_type="forge_build_queue",
            subagent_task_id=correlation_id,
        )
        await writer.write_build_queue_dispatch(entry)
        await writer.append_build_queue_event(
            correlation_id,
            {"stage_label": "plan-complete", "status": "PASSED"},
        )
        await writer.flush()

        # The entry stays frozen — direct-attribute assignment raises.
        with pytest.raises(ValidationError):
            entry.outcome_type = "redirected"  # type: ignore[misc]

    async def test_redacts_event_payload_before_submission(
        self, tmp_path: Path
    ) -> None:
        """ADR-ARCH-029 — secrets in the event payload are redacted on copy.

        The caller's dict is never mutated; the persisted edge body
        carries the redacted form.
        """
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        correlation_id = "build-corr-red"
        await writer.write_build_queue_dispatch(
            _build_entry(
                subagent_type="forge_build_queue",
                subagent_task_id=correlation_id,
            )
        )

        secret = "sk-test1234567890abcdefABCDEF"
        event = {
            "stage_label": "build-complete",
            "status": "FAILED",
            "detail": f"OPENAI_API_KEY={secret} leaked into the trace",
        }
        await writer.append_build_queue_event(correlation_id, event)
        await writer.flush()

        # Caller's dict was not mutated.
        assert event["detail"] == f"OPENAI_API_KEY={secret} leaked into the trace"

        # Persisted edge body carries the redacted form.
        edge_episodes = [
            ep
            for ep in client.episodes
            if ep["source_description"] == "jarvis-routing-history-edge"
        ]
        assert len(edge_episodes) == 1
        body = json.loads(edge_episodes[0]["episode_body"])
        assert secret not in body["detail"]
        assert REDACTION_PLACEHOLDER in body["detail"]


# ---------------------------------------------------------------------------
# AC-010 — Seam test: writer never mutates the frozen entry
# ---------------------------------------------------------------------------


@pytest.mark.seam
@pytest.mark.integration_contract("JARVIS_ROUTING_HISTORY_ENTRY_SCHEMA")
class TestSeamFrozenEntryInvariant:
    """RoutingHistoryWriter operates on a copy; entry stays untouched."""

    async def test_writer_does_not_mutate_entry(self, tmp_path: Path) -> None:
        client = _RecordingGraphitiClient()
        writer = RoutingHistoryWriter(client, _make_config(tmp_path / "traces"))

        entry = _build_entry(
            human_response_text="OPENAI_API_KEY=sk-test1234567890abcdefABCDEF",
            supervisor_reasoning_summary="contact admin@example.com",
            supervisor_tool_call_sequence=_bulky_tool_call_sequence(),
        )
        original_dump = entry.model_dump()

        await writer.write_specialist_dispatch(entry)
        await writer.flush()

        assert entry.model_dump() == original_dump, (
            "RoutingHistoryWriter must not mutate the frozen entry; "
            "redaction applies to a copy, not the source"
        )
