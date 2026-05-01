"""TDD tests for DDR-019 trace-offload autocreate and non-silent drop.

TASK-FRR-003 — When ``JARVIS_GRAPHITI_ENDPOINT`` is unset, the
routing-history writer must fall back to writing the trace JSON locally
to ``<JARVIS_TRACES_DIR>/<correlation_id>.json``. The directory is
autocreated on first use. If both the graphiti write AND the local
offload fail, emit ``routing_history_offload_failed`` with both error
paths — never silently drop the trace.

Acceptance Criteria (from
``tasks/in_progress/feat-jarvis-internal-001-followups/TASK-FRR-003-...``):

* Graphiti unset + non-existent traces dir → autocreate dir + write
  ``<traces_dir>/<correlation_id>.json`` containing a payload that
  round-trips through ``JarvisRoutingHistoryEntry.model_validate_json``.
* Graphiti unset + uncreatable traces dir → log a structured
  ``routing_history_offload_failed`` event with both the graphiti error
  AND the local-write error. The trace is never silently dropped.
* Successful local offload emits ``routing_history_offloaded_locally``
  with ``correlation_id``, ``traces_dir``, ``path``, and the graphiti
  error.
* The happy path (graphiti reachable + writes succeed) is unchanged —
  no offload file is written.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from jarvis.infrastructure.routing_history import (
    JarvisRoutingHistoryEntry,
    RoutingHistoryWriter,
)

# Re-use shared helpers from the existing writer test module so the soft-
# fail tests build on the same fixture surface — _make_config wires
# JarvisConfig with a dotenv-isolated ``patch.dict`` and _build_entry
# returns a minimal valid entry.
from tests.test_routing_history_writer import (
    _RecordingGraphitiClient,
    _build_entry,
    _make_config,
)


class TestSoftFailOffload:
    """DDR-019 soft-fail path autocreates traces_dir and writes locally."""

    async def test_unset_graphiti_autocreates_traces_dir_and_writes_file(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Graphiti unset + traces_dir does not exist → autocreate + write."""
        traces_dir = tmp_path / "traces"
        assert not traces_dir.exists(), "Pre-condition: traces_dir absent"

        config = _make_config(traces_dir)
        writer = RoutingHistoryWriter(None, config)  # graphiti unreachable

        correlation_id = "a58ec9a7-27c6-485a-beac-e18675639a10"
        entry = _build_entry(subagent_task_id=correlation_id)

        with caplog.at_level(logging.WARNING):
            await writer.write_specialist_dispatch(entry)

        # The traces dir was autocreated.
        assert traces_dir.exists(), "traces_dir must be autocreated on first write"
        # The trace file exists at <traces_dir>/<correlation_id>.json.
        trace_file = traces_dir / f"{correlation_id}.json"
        assert trace_file.exists(), (
            f"Trace file {trace_file} must be written to disk"
        )

        # Round-trip through model_validate_json — DDR-029 canonical schema.
        content = trace_file.read_text(encoding="utf-8")
        loaded = JarvisRoutingHistoryEntry.model_validate_json(content)
        assert loaded.subagent_task_id == correlation_id
        assert loaded.subagent_type == entry.subagent_type
        assert loaded.decision_id == entry.decision_id

    async def test_unset_graphiti_logs_routing_history_offloaded_locally(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Successful local offload emits the per-write ``offloaded_locally`` event."""
        traces_dir = tmp_path / "traces"
        config = _make_config(traces_dir)
        writer = RoutingHistoryWriter(None, config)

        correlation_id = "11111111-2222-3333-4444-555555555555"
        entry = _build_entry(subagent_task_id=correlation_id)

        with caplog.at_level(logging.WARNING):
            await writer.write_specialist_dispatch(entry)

        offloaded_logs = [
            rec
            for rec in caplog.records
            if rec.message == "routing_history_offloaded_locally"
        ]
        assert len(offloaded_logs) == 1, (
            f"Expected exactly one routing_history_offloaded_locally event, "
            f"got {len(offloaded_logs)}: {[r.message for r in caplog.records]}"
        )
        log = offloaded_logs[0]
        assert log.__dict__.get("correlation_id") == correlation_id
        assert log.__dict__.get("traces_dir") == str(traces_dir)
        assert log.__dict__.get("path") == str(
            traces_dir / f"{correlation_id}.json"
        )
        # The graphiti error is reported alongside so operators can correlate
        # the local offload with why graphiti was unreachable.
        assert log.__dict__.get("graphiti_error") is not None

    async def test_build_queue_unset_graphiti_writes_local_file(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``write_build_queue_dispatch`` follows the same offload contract."""
        traces_dir = tmp_path / "traces"
        config = _make_config(traces_dir)
        writer = RoutingHistoryWriter(None, config)

        correlation_id = "9f8e7d6c-5b4a-3210-fedc-ba9876543210"
        entry = _build_entry(
            subagent_type="forge_build_queue",
            subagent_task_id=correlation_id,
        )

        with caplog.at_level(logging.WARNING):
            await writer.write_build_queue_dispatch(entry)

        trace_file = traces_dir / f"{correlation_id}.json"
        assert trace_file.exists()
        loaded = JarvisRoutingHistoryEntry.model_validate_json(
            trace_file.read_text(encoding="utf-8")
        )
        assert loaded.subagent_type == "forge_build_queue"
        assert loaded.subagent_task_id == correlation_id

    async def test_uncreatable_traces_dir_emits_offload_failed_with_both_errors(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Both paths failed → ``routing_history_offload_failed`` with details.

        The new event distinguishes operationally-recoverable graphiti
        outages (we wrote the trace locally) from genuinely-lost traces
        (graphiti AND local both failed). The payload must surface BOTH
        error paths so on-call can triage without reading source.
        """
        # macOS root can sometimes still write to 0o555 dirs. Skip the test
        # under root to keep the unprivileged-user invariant honest.
        if os.geteuid() == 0:  # pragma: no cover — CI-shape skip
            pytest.skip("read-only-parent test requires unprivileged user")

        ro_parent = tmp_path / "readonly"
        ro_parent.mkdir()
        traces_dir = ro_parent / "traces"
        try:
            ro_parent.chmod(0o555)  # read + execute, no write

            config = _make_config(traces_dir)
            writer = RoutingHistoryWriter(None, config)

            correlation_id = "deadbeef-1111-2222-3333-444455556666"
            entry = _build_entry(subagent_task_id=correlation_id)

            with caplog.at_level(logging.WARNING):
                # Must not raise — DDR-019 fire-and-forget invariant.
                await writer.write_specialist_dispatch(entry)

            # No file landed on disk (the parent was un-writable).
            assert not (traces_dir / f"{correlation_id}.json").exists()

            failed_logs = [
                rec
                for rec in caplog.records
                if rec.message == "routing_history_offload_failed"
            ]
            assert len(failed_logs) == 1, (
                f"Expected one routing_history_offload_failed event, got "
                f"{len(failed_logs)}: {[r.message for r in caplog.records]}"
            )
            log = failed_logs[0]
            assert log.__dict__.get("correlation_id") == correlation_id
            assert log.__dict__.get("traces_dir") == str(traces_dir)
            # Both error paths reported in a single structured event.
            assert log.__dict__.get("graphiti_error") is not None, (
                "graphiti_error must be populated even when local offload fails"
            )
            local_err = log.__dict__.get("local_error")
            assert local_err is not None, (
                "local_error must be populated when local offload fails"
            )
            # Loose check: the local error should mention permission-shape
            # exceptions (PermissionError on POSIX, OSError on Windows).
            assert (
                "Permission" in local_err
                or "permission" in local_err.lower()
                or "OSError" in local_err
            ), f"Expected permission-shape local_error, got {local_err!r}"
        finally:
            # Restore permissions so tmp_path teardown can clean up.
            ro_parent.chmod(0o755)

    async def test_existing_traces_dir_is_idempotent(
        self, tmp_path: Path
    ) -> None:
        """When traces_dir already exists, the autocreate is a no-op (mkdir exist_ok)."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir()  # pre-create

        config = _make_config(traces_dir)
        writer = RoutingHistoryWriter(None, config)

        correlation_id = "cafebabe-aaaa-bbbb-cccc-dddddddddddd"
        entry = _build_entry(subagent_task_id=correlation_id)

        await writer.write_specialist_dispatch(entry)

        trace_file = traces_dir / f"{correlation_id}.json"
        assert trace_file.exists()
        # Round-trip still works on an existing dir.
        JarvisRoutingHistoryEntry.model_validate_json(
            trace_file.read_text(encoding="utf-8")
        )

    async def test_happy_path_graphiti_reachable_writes_no_local_file(
        self, tmp_path: Path
    ) -> None:
        """When graphiti succeeds, no local offload file is written."""
        traces_dir = tmp_path / "traces"
        client = _RecordingGraphitiClient()
        config = _make_config(traces_dir)
        writer = RoutingHistoryWriter(client, config)

        await writer.write_specialist_dispatch(_build_entry())
        await writer.flush()

        # Either traces_dir was never created (preferred) or it's empty.
        if traces_dir.exists():
            assert list(traces_dir.glob("*.json")) == [], (
                "No local offload file should be written when graphiti succeeds"
            )
        # And graphiti got the entry.
        assert client.add_episode_calls == 1

    async def test_offload_per_write_not_warn_once(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Each soft-fail write emits its own offload event (no log dedup).

        The previous design emitted one ``routing_history_write_failed
        reason=graphiti_unavailable`` per writer instance. That meant
        operators learned that graphiti was down once, and then every
        subsequent trace was dropped silently. The new design writes
        each trace locally and emits one event per write so the audit
        trail matches the on-disk file count.
        """
        traces_dir = tmp_path / "traces"
        config = _make_config(traces_dir)
        writer = RoutingHistoryWriter(None, config)

        n = 3
        with caplog.at_level(logging.WARNING):
            for i in range(n):
                entry = _build_entry(
                    subagent_task_id=f"corr-{i:08x}-1111-2222-3333-444444444444"
                )
                await writer.write_specialist_dispatch(entry)

        offloaded_logs = [
            rec
            for rec in caplog.records
            if rec.message == "routing_history_offloaded_locally"
        ]
        assert len(offloaded_logs) == n, (
            f"Expected {n} offload events (one per write), got "
            f"{len(offloaded_logs)}"
        )
        # And n distinct files on disk.
        files = sorted(traces_dir.glob("*.json"))
        assert len(files) == n
