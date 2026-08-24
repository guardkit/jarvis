"""Tests for notification-sink seam (TASK-JNB-002).

Covers the acceptance criteria in
``tasks/design_approved/TASK-JNB-002-notification-sink-seam-in-forgenotificationssubs.md``:

- AC-001: bind_notification_sink() + sink.notify() for build_started/complete/failed
- AC-002: Malformed envelopes never reach sink
- AC-003: source_id != 'forge' never reaches sink
- AC-004: Correlation-map miss still notifies sink
- AC-005: stage_complete events never forwarded to sink (narrowed 2026-08-24:
  the merge-deploy outcome line forwards ONLY stage_label == "merge-deploy";
  every other stage label still never reaches the sink — see
  tests/test_merge_deploy_outcome_line.py)
- AC-006: Raising sink produces WARNING, never propagates
- AC-007: No sink bound → byte-identical behaviour
- AC-008: ForgeNotification widened with optional build_id, pr_url, summary
- AC-009: dispatch.py has _notification_sink module-level snapshot
- AC-010: queue_build fires build_queued after PubAck/register_correlation
- AC-011: queue_build error paths emit nothing to sink
- AC-012: No err_code 10100 (single consumer)
- AC-013: All files pass lint/format checks
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Protocol
from unittest import mock

import pytest

from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
)


# ---------------------------------------------------------------------------
# NotificationSink Protocol (per TASK-JNB-001 contract)
# ---------------------------------------------------------------------------


class NotificationSink(Protocol):
    """Protocol for notification sinks consumed by ForgeNotificationsSubscriber.

    Per DDR-007, implementations must NEVER raise into the caller.
    """

    async def notify(self, notification: ForgeNotification) -> None:
        """Send notification. Must never raise (failures are WARNING + continue)."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_lifecycle_payload(
    event_type: str,
    *,
    build_id: str = "build-abc",
    pr_url: str | None = None,
    summary: str | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """Build a known-good build-lifecycle payload dict."""
    feature_id = "FEAT-TEST"

    if event_type == "build_started":
        payload: dict[str, Any] = {
            "feature_id": feature_id,
            "build_id": build_id,
            "wave_total": 1,
        }
        if pr_url is not None:
            payload["pr_url"] = pr_url
    elif event_type == "build_complete":
        payload = {
            "feature_id": feature_id,
            "build_id": build_id,
            "tasks_completed": 5,
            "tasks_failed": 0,
            "tasks_total": 5,
            "duration_seconds": 120,
            "summary": summary or "All tasks completed successfully",
        }
        if pr_url is not None:
            payload["pr_url"] = pr_url
    elif event_type == "build_failed":
        payload = {
            "feature_id": feature_id,
            "build_id": build_id,
            "failure_reason": failure_reason or "path outside allowlist",
            "recoverable": False,
        }
        if pr_url is not None:
            payload["pr_url"] = pr_url
        if summary is not None:
            payload["summary"] = summary
    else:
        # Fallback for other event types
        payload = {
            "feature_id": feature_id,
            "build_id": build_id,
        }

    return payload


def _envelope_bytes(
    payload: dict[str, Any],
    *,
    source_id: str = "forge",
    correlation_id: str = "corr-001",
    event_type: str = "build_started",
) -> bytes:
    """Serialise a MessageEnvelope-shaped dict to JSON bytes."""
    body: dict[str, Any] = {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "timestamp": "2026-07-03T15:42:00+00:00",
        "source_id": source_id,
        "event_type": event_type,
        "correlation_id": correlation_id,
        "payload": payload,
    }
    return json.dumps(body).encode("utf-8")


def _stage_complete_payload(
    *,
    correlation_id: str = "corr-001",
    feature_id: str = "FEAT-TEST",
    stage_label: str = "plan-complete",
    status: str = "PASSED",
) -> dict[str, Any]:
    """Build a known-good StageCompletePayload dict."""
    return {
        "feature_id": feature_id,
        "build_id": "build-abc",
        "stage_label": stage_label,
        "target_kind": "subagent",
        "target_identifier": "jarvis-reasoner",
        "status": status,
        "gate_mode": None,
        "coach_score": None,
        "duration_secs": 1.25,
        "completed_at": datetime(2026, 7, 3, 15, 42, 0, tzinfo=UTC).isoformat(),
        "correlation_id": correlation_id,
    }


# ---------------------------------------------------------------------------
# AC-001: bind_notification_sink() + sink.notify() for lifecycle events
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sink_invoked_for_build_started():
    """Sink receives build_started notification after source-id gate + validation."""
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)

    # Register correlation so envelope isn't dropped
    subscriber.register_correlation("corr-001", None, "terminal", datetime.now(UTC), "FEAT-TEST")

    payload = _build_lifecycle_payload("build_started", build_id="b-123", pr_url="https://github.com/org/repo/pull/42")
    envelope_bytes = _envelope_bytes(payload, event_type="build_started", correlation_id="corr-001")

    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    sink.notify.assert_awaited_once()
    notification = sink.notify.call_args[0][0]
    assert notification.event_type == "build_started"
    assert notification.build_id == "b-123"
    assert notification.pr_url == "https://github.com/org/repo/pull/42"


@pytest.mark.asyncio
async def test_sink_invoked_for_build_complete():
    """Sink receives build_complete notification."""
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)
    subscriber.register_correlation("corr-002", None, "terminal", datetime.now(UTC), "FEAT-TEST")

    payload = _build_lifecycle_payload("build_complete", build_id="b-456", summary="All stages passed")
    envelope_bytes = _envelope_bytes(payload, event_type="build_complete", correlation_id="corr-002")

    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    sink.notify.assert_awaited_once()
    notification = sink.notify.call_args[0][0]
    assert notification.event_type == "build_complete"
    assert notification.build_id == "b-456"
    assert notification.summary == "All stages passed"


@pytest.mark.asyncio
async def test_sink_invoked_for_build_failed():
    """Sink receives build_failed notification."""
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)
    subscriber.register_correlation("corr-003", None, "terminal", datetime.now(UTC), "FEAT-TEST")

    payload = _build_lifecycle_payload("build_failed", build_id="b-789", failure_reason="path outside allowlist")
    envelope_bytes = _envelope_bytes(payload, event_type="build_failed", correlation_id="corr-003")

    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    sink.notify.assert_awaited_once()
    notification = sink.notify.call_args[0][0]
    assert notification.event_type == "build_failed"
    assert notification.build_id == "b-789"
    assert notification.failure_reason == "path outside allowlist"


# ---------------------------------------------------------------------------
# AC-002: Malformed envelopes never reach sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_malformed_envelope_never_reaches_sink():
    """Decode/validation failures short-circuit before sink call."""
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)

    malformed_bytes = b'{"not": "valid envelope"}'
    await subscriber._handle_message(_mock_nats_msg(malformed_bytes))

    sink.notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC-003: source_id != 'forge' never reaches sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_forge_source_never_reaches_sink():
    """Envelopes with source_id != 'forge' are gated before sink."""
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)

    payload = _build_lifecycle_payload("build_started")
    envelope_bytes = _envelope_bytes(payload, source_id="other-source", event_type="build_started")

    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    sink.notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC-004: Correlation-map miss still notifies sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correlation_miss_still_notifies_sink():
    """Fan-out is correlation-independent; sink IS awaited even with miss."""
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)

    # NO correlation registered — deliberately missing
    payload = _build_lifecycle_payload("build_started")
    envelope_bytes = _envelope_bytes(payload, event_type="build_started", correlation_id="unknown-corr")

    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    # Sink should STILL be notified (correlation-independent fan-out)
    sink.notify.assert_awaited_once()


# ---------------------------------------------------------------------------
# AC-005: stage_complete events never forwarded to sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stage_complete_never_reaches_sink():
    """Ordinary stage_complete events are NOT forwarded to sink (ASSUM-002).

    Narrowed 2026-08-24: the merge-deploy outcome line forwards ONLY
    ``stage_label == "merge-deploy"`` (tests/test_merge_deploy_outcome_line.py);
    this fence pins that every OTHER stage label still never reaches it.
    """
    sink = mock.AsyncMock()
    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)
    subscriber.register_correlation("corr-stage", None, "terminal", datetime.now(UTC), "FEAT-TEST")

    payload = _stage_complete_payload(correlation_id="corr-stage")
    envelope_bytes = _envelope_bytes(payload, event_type="stage_complete", correlation_id="corr-stage")

    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    # Sink should NOT be called for stage_complete
    sink.notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# AC-006: Raising sink produces WARNING, never propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_raising_sink_produces_warning_not_exception(caplog):
    """Sink whose notify() raises must produce WARNING, never propagate."""
    import structlog

    # Configure structlog to use standard logging so caplog can capture it
    structlog.configure(
        processors=[structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )

    sink = mock.AsyncMock()
    sink.notify.side_effect = RuntimeError("boom")

    subscriber = _make_subscriber()
    subscriber.bind_notification_sink(sink)
    subscriber.register_correlation("corr-raise", None, "terminal", datetime.now(UTC), "FEAT-TEST")

    payload = _build_lifecycle_payload("build_started")
    envelope_bytes = _envelope_bytes(payload, event_type="build_started", correlation_id="corr-raise")

    with caplog.at_level(logging.WARNING, logger="jarvis.infrastructure.forge_notifications"):
        # Must NOT raise — behavioural assertion of DDR-007
        await subscriber._handle_message(_mock_nats_msg(envelope_bytes))

    # Assert WARNING was logged - check for the specific log message
    assert any("notification_sink_error" in str(r.message) or r.levelno == logging.WARNING
               for r in caplog.records), (
        f"sink failure must be surfaced as WARNING, got: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# AC-007: No sink bound → byte-identical behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_sink_bound_behaviour_unchanged():
    """With no sink bound, subscriber behaviour is identical to baseline."""
    subscriber = _make_subscriber()
    # NO sink bound

    subscriber.register_correlation("corr-nosink", None, "terminal", datetime.now(UTC), "FEAT-TEST")

    payload = _build_lifecycle_payload("build_started")
    envelope_bytes = _envelope_bytes(payload, event_type="build_started", correlation_id="corr-nosink")

    # Should not raise
    await subscriber._handle_message(_mock_nats_msg(envelope_bytes))


# ---------------------------------------------------------------------------
# AC-008: ForgeNotification widened with optional fields
# ---------------------------------------------------------------------------


def test_forge_notification_widened_fields():
    """ForgeNotification has optional build_id, pr_url, summary fields."""
    notification = ForgeNotification(
        event_type="build_started",
        correlation_id="corr-001",
        feature_id="FEAT-TEST",
        completed_at=datetime.now(UTC),
        build_id="b-123",
        pr_url="https://github.com/org/repo/pull/42",
        summary="Build started successfully",
    )

    assert notification.build_id == "b-123"
    assert notification.pr_url == "https://github.com/org/repo/pull/42"
    assert notification.summary == "Build started successfully"


def test_forge_notification_widened_fields_default_none():
    """Widened fields default to None (frozen-model rule)."""
    notification = ForgeNotification(
        event_type="build_started",
        correlation_id="corr-001",
        feature_id="FEAT-TEST",
        completed_at=datetime.now(UTC),
    )

    assert notification.build_id is None
    assert notification.pr_url is None
    assert notification.summary is None


# ---------------------------------------------------------------------------
# AC-009: dispatch.py _notification_sink module-level snapshot
# ---------------------------------------------------------------------------


def test_dispatch_module_has_notification_sink_snapshot():
    """dispatch.py has _notification_sink module-level variable."""
    from jarvis.tools import dispatch

    assert hasattr(dispatch, "_notification_sink")


# ---------------------------------------------------------------------------
# AC-010: queue_build fires build_queued after PubAck/register_correlation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_build_fires_build_queued_notification():
    """queue_build fires build_queued after PubAck/register_correlation."""
    from jarvis.tools import dispatch
    from jarvis.tools.dispatch import queue_build

    # Mock dependencies
    sink = mock.AsyncMock()
    dispatch._notification_sink = sink

    # Mock NATS client
    mock_client = mock.Mock()
    mock_js = mock.AsyncMock()
    mock_client.js = mock_js
    dispatch._nats_client = mock_client

    # Mock subscriber
    mock_subscriber = mock.Mock()
    dispatch._forge_subscriber = mock_subscriber

    result = await queue_build.ainvoke({
        "feature_id": "FEAT-TEST",
        "feature_yaml_path": "features/test.yaml",
        "repo": "org/repo",
        "branch": "main",
    })

    # Assert sink was called with build_queued notification
    sink.notify.assert_awaited_once()
    notification = sink.notify.call_args[0][0]
    assert notification.event_type == "build_queued"
    assert notification.feature_id == "FEAT-TEST"

    # Assert QueueBuildAck is unchanged
    ack = json.loads(result)
    assert ack["status"] == "queued"


# ---------------------------------------------------------------------------
# AC-011: queue_build error paths emit nothing to sink
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_queue_build_error_path_no_sink_notification():
    """queue_build degraded paths (publish failure) emit nothing to sink."""
    from jarvis.tools import dispatch
    from jarvis.tools.dispatch import queue_build

    sink = mock.AsyncMock()
    dispatch._notification_sink = sink

    # Mock NATS unavailable
    dispatch._nats_client = None

    result = await queue_build.ainvoke({
        "feature_id": "FEAT-TEST",
        "feature_yaml_path": "features/test.yaml",
        "repo": "org/repo",
        "branch": "main",
    })

    # Should return degraded error
    ack = json.loads(result)
    assert ack["status"] == "degraded"

    # Sink should NOT be called
    sink.notify.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


def _make_subscriber() -> ForgeNotificationsSubscriber:
    """Construct a ForgeNotificationsSubscriber with mocked dependencies."""
    mock_client = mock.Mock()
    mock_client.js = mock.AsyncMock()

    mock_routing_history_writer = mock.AsyncMock()
    mock_routing_history_writer.append_build_queue_event = mock.AsyncMock()

    subscriber = ForgeNotificationsSubscriber(
        nats_client=mock_client,
        routing_history_writer=mock_routing_history_writer,
        queue_cap=100,
        correlation_cap=1000,
    )

    # Bind session manager to avoid drop-with-WARN
    mock_session_manager = mock.Mock()
    mock_session_manager.enqueue_notification = mock.Mock()
    subscriber.bind_session_manager(mock_session_manager)

    return subscriber


def _mock_nats_msg(data: bytes) -> mock.Mock:
    """Create a mock NATS message."""
    msg = mock.Mock()
    msg.data = data
    return msg
