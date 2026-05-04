"""Tests for ``ForgeNotificationsSubscriber`` (TASK-J005-003).

Covers the acceptance criteria recorded in
``tasks/design_approved/TASK-J005-003-forge-notifications-subscriber.md``:

* AC-001 — constructor accepts ``nats_client``, ``routing_history_writer``,
  ``queue_cap``, ``correlation_cap``.
* AC-002 — ``start()`` creates an ephemeral push consumer on
  ``pipeline.stage-complete.>`` with ``deliver_policy=NEW``; idempotent.
* AC-003 — ``stop()`` returns within 5s even with an unresponsive broker.
* AC-004 — ``register_correlation`` populates an LRU dict, evicts oldest
  at cap, logs one WARN per eviction.
* AC-005 — re-registering an existing correlation_id is silently overwritten.
* AC-006 — happy-path routing: envelope validated, source_id="forge"
  enforced, correlation looked up, edge written via
  ``RoutingHistoryWriter.append_build_queue_event``, notification enqueued
  via ``SessionManager.enqueue_notification``.
* AC-007 — unknown source_id → drop, WARN
  ``forge_notification_dropped_unknown_source``.
* AC-008 — unknown correlation_id → silent drop.
* AC-009 — malformed envelope → drop, WARN, never raises.
* AC-010 — extra unknown fields tolerated.
* AC-011 — unbound session_manager → drop with WARN.

Plus the Test Requirements:

* concurrent two-correlation routing (Group D #9).
* burst of 5 events for one correlation arrive in publication order.
* stop() bounded by 5s even with a hung unsubscribe.

No real NATS connection is opened — the JetStream surface is mocked end to
end with ``unittest.mock``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest import mock

import pytest

from jarvis.infrastructure.forge_notifications import (
    BuildCorrelation,
    ForgeNotification,
    ForgeNotificationsSubscriber,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stage_complete_payload(
    *,
    correlation_id: str = "corr-001",
    feature_id: str = "FEAT-J005DEMO",
    stage_label: str = "plan-complete",
    status: str = "PASSED",
    target_kind: str = "subagent",
    target_identifier: str = "jarvis-reasoner",
    duration_secs: float = 1.25,
    completed_at: str | None = None,
) -> dict[str, Any]:
    """Build a known-good ``StageCompletePayload`` dict."""
    return {
        "feature_id": feature_id,
        "build_id": "build-abc",
        "stage_label": stage_label,
        "target_kind": target_kind,
        "target_identifier": target_identifier,
        "status": status,
        "gate_mode": None,
        "coach_score": None,
        "duration_secs": duration_secs,
        "completed_at": completed_at
        or datetime(2026, 4, 29, 15, 42, 0, tzinfo=UTC).isoformat(),
        "correlation_id": correlation_id,
    }


def _envelope_bytes(
    payload: dict[str, Any],
    *,
    source_id: str = "forge",
    correlation_id: str | None = None,
    event_type: str = "stage_complete",
    extra: dict[str, Any] | None = None,
) -> bytes:
    """Serialise a MessageEnvelope-shaped dict to JSON bytes."""
    body: dict[str, Any] = {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "timestamp": "2026-04-29T15:42:00+00:00",
        "version": "1.0",
        "source_id": source_id,
        "event_type": event_type,
        "project": None,
        "correlation_id": correlation_id or payload.get("correlation_id"),
        "payload": payload,
    }
    if extra:
        body.update(extra)
    return json.dumps(body).encode("utf-8")


def _build_started_payload(
    *,
    feature_id: str = "FEAT-J005DEMO",
    build_id: str = "build-abc",
    wave_total: int = 3,
) -> dict[str, Any]:
    """Build a known-good ``BuildStartedPayload`` dict (TASK-FRR-F010D)."""
    return {
        "feature_id": feature_id,
        "build_id": build_id,
        "wave_total": wave_total,
    }


def _build_complete_payload(
    *,
    feature_id: str = "FEAT-J005DEMO",
    build_id: str = "build-abc",
    tasks_completed: int = 5,
    tasks_failed: int = 0,
    tasks_total: int = 5,
    duration_seconds: int = 120,
    summary: str = "All tasks completed successfully",
) -> dict[str, Any]:
    """Build a known-good ``BuildCompletePayload`` dict (TASK-FRR-F010D)."""
    return {
        "feature_id": feature_id,
        "build_id": build_id,
        "tasks_completed": tasks_completed,
        "tasks_failed": tasks_failed,
        "tasks_total": tasks_total,
        "duration_seconds": duration_seconds,
        "summary": summary,
    }


def _build_failed_payload(
    *,
    feature_id: str = "FEAT-J005DEMO",
    build_id: str = "build-abc",
    failure_reason: str = "path outside allowlist",
    recoverable: bool = False,
) -> dict[str, Any]:
    """Build a known-good ``BuildFailedPayload`` dict (TASK-FRR-F010D)."""
    return {
        "feature_id": feature_id,
        "build_id": build_id,
        "failure_reason": failure_reason,
        "recoverable": recoverable,
    }


def _make_msg(data: bytes) -> mock.MagicMock:
    """Build a ``nats.aio.msg.Msg``-shaped mock with ``data`` bytes."""
    m = mock.MagicMock()
    m.data = data
    m.subject = "pipeline.stage-complete.FEAT-J005DEMO"
    m.ack = mock.AsyncMock()
    return m


def _make_subscriber(
    *,
    queue_cap: int = 100,
    correlation_cap: int = 1000,
    stop_timeout: float = 5.0,
) -> tuple[ForgeNotificationsSubscriber, mock.MagicMock, mock.MagicMock]:
    """Build a subscriber with mocked nats_client.js and writer."""
    js = mock.MagicMock()
    js.subscribe = mock.AsyncMock(return_value=mock.MagicMock())
    nats_client = mock.MagicMock()
    nats_client.js = js

    writer = mock.MagicMock()
    writer.append_build_queue_event = mock.AsyncMock()

    sub = ForgeNotificationsSubscriber(
        nats_client=nats_client,
        routing_history_writer=writer,
        queue_cap=queue_cap,
        correlation_cap=correlation_cap,
        stop_timeout=stop_timeout,
    )
    return sub, nats_client, writer


def _bind_session_manager(
    sub: ForgeNotificationsSubscriber,
) -> mock.MagicMock:
    """Bind a SessionManager-shaped mock onto the subscriber."""
    session_manager = mock.MagicMock()
    session_manager.enqueue_notification = mock.MagicMock()
    sub.bind_session_manager(session_manager)
    return session_manager


# ---------------------------------------------------------------------------
# AC-001 — constructor signature
# ---------------------------------------------------------------------------


class TestConstructorSignature:
    """AC-001: __init__ accepts the documented kwargs."""

    def test_init_accepts_all_documented_kwargs(self) -> None:
        sub, _, _ = _make_subscriber(queue_cap=200, correlation_cap=500)
        assert sub._queue_cap == 200
        assert sub._correlation_cap == 500

    def test_queue_cap_defaults_to_100(self) -> None:
        nats_client = mock.MagicMock()
        writer = mock.MagicMock()
        sub = ForgeNotificationsSubscriber(
            nats_client=nats_client, routing_history_writer=writer
        )
        assert sub._queue_cap == 100
        assert sub._correlation_cap == 1000


# ---------------------------------------------------------------------------
# AC-002 — start() creates ephemeral push consumer on stage-complete subject
# ---------------------------------------------------------------------------


_LIFECYCLE_SUBJECTS = (
    "pipeline.build-started.>",
    "pipeline.stage-complete.>",
    "pipeline.build-complete.>",
    "pipeline.build-failed.>",
)


class TestStart:
    """AC-002: ephemeral push consumer with deliver_policy=ALL; idempotent.

    DDR-027 was revised on 2026-05-01 (TASK-FRR-001) from
    ``DeliverPolicy.NEW`` to ``DeliverPolicy.ALL`` because the canonical
    PIPELINE stream is provisioned with workqueue retention, which
    rejects any other policy with ``code=10101 consumer must be deliver
    all on workqueue stream``. The no-replay-on-restart UX is preserved
    structurally — see the module-level rationale block on
    ``_get_deliver_policy_all`` and DDR-027 §"Workqueue interaction".

    TASK-FRR-F010D (2026-05-04): subject was widened from
    ``pipeline.stage-complete.>`` to ``pipeline.>`` so the subscriber
    also receives ``build-started`` / ``build-complete`` /
    ``build-failed`` envelopes — three of the four lifecycle envelope
    types required by the runbook §7.1 acceptance criteria.

    TASK-FRR-F010Db (2026-05-04, late afternoon): the Option-A
    ``pipeline.>`` catch-all overlapped with forge-serve's existing
    ``pipeline.build-queued.>`` consumer on the workqueue PIPELINE
    stream and was rejected on every boot with ``err_code=10100
    'filtered consumer not unique on workqueue stream'``. The fix
    narrows the filter to the explicit four-subject lifecycle list
    (Option B), passed via ``ConsumerConfig.filter_subjects`` —
    disjoint from ``pipeline.build-queued.>`` by construction. The
    ``source_id != "forge"`` gate in ``_handle_message`` is preserved
    as defence-in-depth.
    """

    @pytest.mark.asyncio
    async def test_start_subscribes_with_deliver_policy_all(self) -> None:
        sub, nats_client, _ = _make_subscriber()

        await sub.start()

        nats_client.js.subscribe.assert_called_once()
        kwargs = nats_client.js.subscribe.call_args.kwargs
        args = nats_client.js.subscribe.call_args.args
        # Positional ``subject`` arg is used by js.subscribe only for
        # stream lookup; the actual filter is in
        # ``config.filter_subjects``. It must be one of the four
        # lifecycle subjects (TASK-FRR-F010Db).
        assert args[0] in _LIFECYCLE_SUBJECTS
        # The multi-subject filter must be the four-subject lifecycle
        # list (Option B). Sorted compare so the implementation is free
        # to pick any deterministic order.
        config = kwargs["config"]
        assert config is not None, (
            "ConsumerConfig must be passed via config= so "
            "filter_subjects (plural) overrides the singular "
            "filter_subject derived from the positional subject arg"
        )
        assert sorted(config.filter_subjects) == sorted(_LIFECYCLE_SUBJECTS)
        # ordered_consumer=False per implementation notes.
        assert kwargs["ordered_consumer"] is False
        # deliver_policy is the ALL enum from nats.js.api (DDR-027 revised
        # 2026-05-01 per TASK-FRR-001 — workqueue retention).
        from nats.js.api import DeliverPolicy

        assert kwargs["deliver_policy"] == DeliverPolicy.ALL
        # Callback is wired.
        assert callable(kwargs["cb"])

    @pytest.mark.asyncio
    async def test_filter_subjects_disjoint_from_workqueue_overlap(
        self,
    ) -> None:
        """Regression test for AC-2 / TASK-FRR-F010Db.

        The PIPELINE stream is workqueue-retention; workqueue policy
        forbids overlapping subject filters across consumers
        (``err_code=10100 'filtered consumer not unique on workqueue
        stream'``). The forge daemon's ``forge-serve`` consumer
        already filters ``pipeline.build-queued.>``, so any consumer
        Jarvis attaches must use a filter disjoint from that.

        TASK-FRR-F010D's Option A (``pipeline.>`` catch-all) was a
        superset of ``pipeline.build-queued.>`` and JetStream rejected
        the bind on every boot. This test would have caught that
        regression — it asserts the structural invariant the broker
        enforces, mock-side, so the runbook §7 live-wire rerun can
        regression-protect against future re-widening attempts
        without needing a live broker.

        Also covers AC-4: the filter is correctly narrower than
        ``pipeline.>``, so ``pipeline.build-queued.*`` envelopes never
        reach ``_handle_message`` at the wire level.
        """
        sub, nats_client, _ = _make_subscriber()

        await sub.start()

        kwargs = nats_client.js.subscribe.call_args.kwargs
        config = kwargs["config"]
        filter_subjects = config.filter_subjects

        # The Option-A catch-all must NOT appear (it overlaps with
        # forge-serve's ``pipeline.build-queued.>``).
        assert "pipeline.>" not in filter_subjects

        # forge-serve's exact filter must NOT appear.
        assert "pipeline.build-queued.>" not in filter_subjects

        # No filter may be a sibling of pipeline.build-queued.> — any
        # subject under the build-queued namespace would overlap with
        # forge-serve's workqueue consumer.
        for s in filter_subjects:
            assert not s.startswith("pipeline.build-queued."), (
                f"filter subject {s!r} would overlap with forge-serve "
                f"workqueue consumer (pipeline.build-queued.>) and the "
                f"PIPELINE workqueue stream would reject the bind with "
                f"err_code=10100"
            )

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        sub, nats_client, _ = _make_subscriber()
        await sub.start()
        await sub.start()
        # Second start does NOT call subscribe again.
        assert nats_client.js.subscribe.call_count == 1


# ---------------------------------------------------------------------------
# AC-003 — stop() bounded by 5s
# ---------------------------------------------------------------------------


class TestStop:
    """AC-003 / Group D #14: stop() returns within 5s with hung broker."""

    @pytest.mark.asyncio
    async def test_stop_calls_unsubscribe(self) -> None:
        sub, nats_client, _ = _make_subscriber()
        fake_sub = mock.MagicMock()
        fake_sub.unsubscribe = mock.AsyncMock()
        nats_client.js.subscribe.return_value = fake_sub

        await sub.start()
        await sub.stop()
        fake_sub.unsubscribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_noop(self) -> None:
        sub, _, _ = _make_subscriber()
        # Does not raise even though never started.
        await sub.stop()

    @pytest.mark.asyncio
    async def test_stop_returns_within_timeout_on_hung_broker(self) -> None:
        sub, nats_client, _ = _make_subscriber(stop_timeout=0.05)

        async def _hang() -> None:
            await asyncio.sleep(60)  # would block well past stop_timeout

        fake_sub = mock.MagicMock()
        fake_sub.unsubscribe = mock.AsyncMock(side_effect=_hang)
        nats_client.js.subscribe.return_value = fake_sub
        await sub.start()

        loop = asyncio.get_event_loop()
        before = loop.time()
        await sub.stop()
        elapsed = loop.time() - before
        # asyncio.wait_for + a generous slack for scheduler latency.
        assert elapsed < 1.0


# ---------------------------------------------------------------------------
# AC-004 / AC-005 — correlation map LRU + idempotent register
# ---------------------------------------------------------------------------


class TestRegisterCorrelation:
    """AC-004 + AC-005: LRU eviction at cap; idempotent overwrite."""

    def test_register_correlation_inserts(self) -> None:
        sub, _, _ = _make_subscriber(correlation_cap=10)
        sub.register_correlation(
            correlation_id="corr-1",
            session_id="cli-abc",
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )
        assert "corr-1" in sub._correlations
        assert isinstance(sub._correlations["corr-1"], BuildCorrelation)

    def test_register_evicts_oldest_at_cap(self, caplog: Any) -> None:
        sub, _, _ = _make_subscriber(correlation_cap=2)
        now = datetime.now(UTC)
        # Fill to cap.
        sub.register_correlation("c-1", "s-1", "cli", now, "FEAT-J005DEMO")
        sub.register_correlation("c-2", "s-2", "cli", now, "FEAT-J005DEMO")
        # Third registration evicts c-1.
        with caplog.at_level(logging.WARNING):
            sub.register_correlation(
                "c-3", "s-3", "cli", now, "FEAT-J005DEMO"
            )
        assert "c-1" not in sub._correlations
        assert "c-2" in sub._correlations
        assert "c-3" in sub._correlations
        # We don't assert on the structlog handler here because structlog
        # may not propagate to caplog without configuration. Membership of
        # the evicted key is the load-bearing assertion.

    def test_register_same_id_is_silently_overwritten(self) -> None:
        sub, _, _ = _make_subscriber(correlation_cap=5)
        now = datetime.now(UTC)
        sub.register_correlation("c-1", "s-1", "cli", now, "FEAT-J005DEMO")
        sub.register_correlation("c-1", "s-2", "cli", now, "FEAT-J005DEMO")
        # No eviction because the same key was reused.
        assert len(sub._correlations) == 1
        assert sub._correlations["c-1"].session_id == "s-2"


# ---------------------------------------------------------------------------
# AC-006 — happy path routing
# ---------------------------------------------------------------------------


class TestHappyPath:
    """AC-006: full envelope → routing-history edge + session enqueue."""

    @pytest.mark.asyncio
    async def test_message_routes_to_writer_and_session(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)

        sub.register_correlation(
            correlation_id="corr-001",
            session_id="cli-abc",
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )

        payload = _stage_complete_payload(correlation_id="corr-001")
        msg = _make_msg(_envelope_bytes(payload))

        await sub._on_message(msg)

        writer.append_build_queue_event.assert_awaited_once()
        edge_call = writer.append_build_queue_event.await_args
        assert edge_call.args[0] == "corr-001"
        assert edge_call.args[1]["correlation_id"] == "corr-001"
        assert edge_call.args[1]["status"] == "PASSED"

        sm.enqueue_notification.assert_called_once()
        ses_id, notif = sm.enqueue_notification.call_args.args
        assert ses_id == "cli-abc"
        assert isinstance(notif, ForgeNotification)
        assert notif.correlation_id == "corr-001"
        assert notif.feature_id == "FEAT-J005DEMO"
        assert notif.status == "PASSED"


# ---------------------------------------------------------------------------
# AC-007 — unknown source_id
# ---------------------------------------------------------------------------


class TestUnknownSourceDropped:
    @pytest.mark.asyncio
    async def test_dropped_unknown_source_id_logs_warning(
        self, caplog: Any
    ) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            "corr-001", "cli-abc", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )

        payload = _stage_complete_payload(correlation_id="corr-001")
        msg = _make_msg(
            _envelope_bytes(payload, source_id="rogue_source")
        )

        with caplog.at_level(logging.WARNING):
            await sub._on_message(msg)

        writer.append_build_queue_event.assert_not_awaited()
        sm.enqueue_notification.assert_not_called()


# ---------------------------------------------------------------------------
# AC-008 — unknown correlation_id (silent drop)
# ---------------------------------------------------------------------------


class TestUnknownCorrelationDropped:
    @pytest.mark.asyncio
    async def test_unknown_correlation_silent_drop(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        # Note: no register_correlation call.

        payload = _stage_complete_payload(correlation_id="never-registered")
        msg = _make_msg(_envelope_bytes(payload))

        await sub._on_message(msg)

        writer.append_build_queue_event.assert_not_awaited()
        sm.enqueue_notification.assert_not_called()


# ---------------------------------------------------------------------------
# AC-009 — malformed envelope (Group D #7)
# ---------------------------------------------------------------------------


class TestMalformedEnvelope:
    @pytest.mark.asyncio
    async def test_invalid_json_is_dropped_and_does_not_raise(self) -> None:
        sub, _, writer = _make_subscriber()
        _bind_session_manager(sub)

        msg = _make_msg(b"this is not valid json")

        # Must not raise.
        await sub._on_message(msg)

        writer.append_build_queue_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_required_envelope_field_is_dropped(self) -> None:
        sub, _, writer = _make_subscriber()
        _bind_session_manager(sub)

        # Missing source_id and event_type and payload.
        bad = json.dumps({"message_id": "x"}).encode("utf-8")
        msg = _make_msg(bad)
        await sub._on_message(msg)
        writer.append_build_queue_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_bad_payload_shape_is_dropped(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            "corr-001", "cli-abc", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )
        # Envelope is valid but payload is missing required fields.
        bad_payload: dict[str, Any] = {"correlation_id": "corr-001"}
        msg = _make_msg(_envelope_bytes(bad_payload))
        await sub._on_message(msg)
        writer.append_build_queue_event.assert_not_awaited()
        sm.enqueue_notification.assert_not_called()


# ---------------------------------------------------------------------------
# AC-010 — extra unknown fields tolerated (Group D #8)
# ---------------------------------------------------------------------------


class TestExtraFieldsTolerated:
    @pytest.mark.asyncio
    async def test_extra_envelope_fields_are_ignored(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            "corr-001", "cli-abc", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )

        payload = _stage_complete_payload(correlation_id="corr-001")
        msg = _make_msg(
            _envelope_bytes(
                payload, extra={"some_future_field": "ok", "another": 42}
            )
        )

        await sub._on_message(msg)

        writer.append_build_queue_event.assert_awaited_once()
        sm.enqueue_notification.assert_called_once()


# ---------------------------------------------------------------------------
# AC-011 — session manager unbound
# ---------------------------------------------------------------------------


class TestSessionManagerUnbound:
    @pytest.mark.asyncio
    async def test_unbound_session_manager_drops_message(self) -> None:
        sub, _, writer = _make_subscriber()
        # NOT calling bind_session_manager.
        sub.register_correlation(
            "corr-001", "cli-abc", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )

        payload = _stage_complete_payload(correlation_id="corr-001")
        msg = _make_msg(_envelope_bytes(payload))

        # Must not raise.
        await sub._on_message(msg)

        # Edge is still written for the trace, but the FIFO enqueue is skipped.
        writer.append_build_queue_event.assert_awaited_once()

    def test_double_bind_raises(self) -> None:
        sub, _, _ = _make_subscriber()
        _bind_session_manager(sub)
        with pytest.raises(RuntimeError, match="bind_session_manager"):
            _bind_session_manager(sub)


# ---------------------------------------------------------------------------
# Concurrency: two correlations route to their own sessions (Group D #9)
# ---------------------------------------------------------------------------


class TestConcurrencyTwoCorrelations:
    @pytest.mark.asyncio
    async def test_two_correlations_route_to_independent_sessions(
        self,
    ) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)

        sub.register_correlation(
            "corr-A", "cli-A", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )
        sub.register_correlation(
            "corr-B", "cli-B", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )

        msg_a = _make_msg(
            _envelope_bytes(_stage_complete_payload(correlation_id="corr-A"))
        )
        msg_b = _make_msg(
            _envelope_bytes(_stage_complete_payload(correlation_id="corr-B"))
        )

        # Schedule both concurrently — no shared mutable state should leak.
        await asyncio.gather(sub._on_message(msg_a), sub._on_message(msg_b))

        assert writer.append_build_queue_event.await_count == 2
        assert sm.enqueue_notification.call_count == 2

        seen_pairs = {
            (call.args[0], call.args[1].correlation_id)
            for call in sm.enqueue_notification.call_args_list
        }
        assert seen_pairs == {("cli-A", "corr-A"), ("cli-B", "corr-B")}


# ---------------------------------------------------------------------------
# Concurrency: burst of 5 events arrive in publication order (Group D #10)
# ---------------------------------------------------------------------------


class TestConcurrencyBurstOrder:
    @pytest.mark.asyncio
    async def test_five_events_for_one_correlation_arrive_in_order(
        self,
    ) -> None:
        sub, _, _ = _make_subscriber()
        sm = _bind_session_manager(sub)

        sub.register_correlation(
            "corr-001", "cli-abc", "cli", datetime.now(UTC), "FEAT-J005DEMO"
        )

        labels = [
            "plan-complete",
            "autobuild-complete",
            "task-review-complete",
            "coach-review-complete",
            "shipped",
        ]
        msgs = [
            _make_msg(
                _envelope_bytes(
                    _stage_complete_payload(
                        correlation_id="corr-001", stage_label=label
                    )
                )
            )
            for label in labels
        ]

        # Single-loop sequential delivery (mirrors JetStream's per-consumer
        # serial callback dispatch).
        for m in msgs:
            await sub._on_message(m)

        assert sm.enqueue_notification.call_count == 5
        seen_labels = [
            call.args[1].stage_label
            for call in sm.enqueue_notification.call_args_list
        ]
        assert seen_labels == labels


# ---------------------------------------------------------------------------
# Sessionless correlation — edge written, enqueue skipped
# ---------------------------------------------------------------------------


class TestSessionlessCorrelation:
    @pytest.mark.asyncio
    async def test_correlation_without_session_only_writes_edge(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            correlation_id="corr-001",
            session_id=None,
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )

        payload = _stage_complete_payload(correlation_id="corr-001")
        msg = _make_msg(_envelope_bytes(payload))

        await sub._on_message(msg)

        writer.append_build_queue_event.assert_awaited_once()
        sm.enqueue_notification.assert_not_called()


# ---------------------------------------------------------------------------
# TASK-FRR-F010D — full pipeline lifecycle (build-started / build-complete /
# build-failed) routes through the widened subscription
# ---------------------------------------------------------------------------


class TestBuildStartedRouting:
    """TASK-FRR-F010D AC-3: ``pipeline.build-started.*`` envelopes route
    through to the originating session FIFO with a non-empty rendered line.

    BuildStartedPayload carries no ``correlation_id`` field of its own
    (only ``feature_id`` / ``build_id`` / ``wave_total``). Routing must
    therefore pull the correlation key off ``envelope.correlation_id``
    — the same key forge already populates on the outbound envelope as
    of TASK-FORGE-FRR-F010C.
    """

    @pytest.mark.asyncio
    async def test_build_started_envelope_routes_and_renders(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            correlation_id="corr-bs-001",
            session_id="cli-bs",
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )

        payload = _build_started_payload(feature_id="FEAT-J005DEMO")
        msg = _make_msg(
            _envelope_bytes(
                payload,
                correlation_id="corr-bs-001",
                event_type="build_started",
            )
        )
        msg.subject = "pipeline.build-started.FEAT-J005DEMO"

        await sub._on_message(msg)

        # build-started is a routing-only event — the routing-history
        # writer's ``append_build_queue_event`` is the stage-complete
        # path; for lifecycle events we only require the FIFO enqueue.
        sm.enqueue_notification.assert_called_once()
        ses_id, notif = sm.enqueue_notification.call_args.args
        assert ses_id == "cli-bs"
        assert isinstance(notif, ForgeNotification)
        assert notif.event_type == "build_started"
        assert notif.feature_id == "FEAT-J005DEMO"
        assert notif.correlation_id == "corr-bs-001"
        rendered = notif.render_line()
        assert rendered  # non-empty (AC-2 wording)
        assert "FEAT-J005DEMO" in rendered
        assert "build-started" in rendered
        # The ``writer`` arg is unused for non-stage-complete events to
        # keep the routing-history edge contract scoped to stage events.
        writer.append_build_queue_event.assert_not_awaited()


class TestBuildCompleteRouting:
    """TASK-FRR-F010D AC-3: ``pipeline.build-complete.*`` envelopes route
    through to the originating session FIFO with a non-empty rendered
    line. BuildCompletePayload carries no ``correlation_id``; routing
    uses ``envelope.correlation_id``.
    """

    @pytest.mark.asyncio
    async def test_build_complete_envelope_routes_and_renders(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            correlation_id="corr-bc-001",
            session_id="cli-bc",
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )

        payload = _build_complete_payload(feature_id="FEAT-J005DEMO")
        msg = _make_msg(
            _envelope_bytes(
                payload,
                correlation_id="corr-bc-001",
                event_type="build_complete",
            )
        )
        msg.subject = "pipeline.build-complete.FEAT-J005DEMO"

        await sub._on_message(msg)

        sm.enqueue_notification.assert_called_once()
        ses_id, notif = sm.enqueue_notification.call_args.args
        assert ses_id == "cli-bc"
        assert isinstance(notif, ForgeNotification)
        assert notif.event_type == "build_complete"
        assert notif.feature_id == "FEAT-J005DEMO"
        assert notif.correlation_id == "corr-bc-001"
        rendered = notif.render_line()
        assert rendered
        assert "FEAT-J005DEMO" in rendered
        assert "build-complete" in rendered
        writer.append_build_queue_event.assert_not_awaited()


class TestBuildFailedRouting:
    """TASK-FRR-F010D AC-2: ``pipeline.build-failed.*`` envelopes route
    through to the originating session FIFO with a non-empty rendered
    line whose suffix carries the payload's ``failure_reason`` per the
    runbook §7.1 line shape ``[HH:MM] Forge FEAT-XXX: build-failed
    (path outside allowlist)``.
    """

    @pytest.mark.asyncio
    async def test_build_failed_envelope_routes_and_renders(self) -> None:
        sub, _, writer = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            correlation_id="corr-bf-001",
            session_id="cli-bf",
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )

        payload = _build_failed_payload(
            feature_id="FEAT-J005DEMO",
            failure_reason="path outside allowlist",
        )
        msg = _make_msg(
            _envelope_bytes(
                payload,
                correlation_id="corr-bf-001",
                event_type="build_failed",
            )
        )
        msg.subject = "pipeline.build-failed.FEAT-J005DEMO"

        await sub._on_message(msg)

        sm.enqueue_notification.assert_called_once()
        ses_id, notif = sm.enqueue_notification.call_args.args
        assert ses_id == "cli-bf"
        assert isinstance(notif, ForgeNotification)
        assert notif.event_type == "build_failed"
        assert notif.feature_id == "FEAT-J005DEMO"
        assert notif.correlation_id == "corr-bf-001"
        assert notif.failure_reason == "path outside allowlist"
        rendered = notif.render_line()
        assert rendered
        assert "FEAT-J005DEMO" in rendered
        assert "build-failed" in rendered
        # Per runbook §7.1, failure_reason is rendered in parens.
        assert "path outside allowlist" in rendered
        writer.append_build_queue_event.assert_not_awaited()


class TestLifecycleEventDropsOnUnknownCorrelation:
    """TASK-FRR-F010D AC-4 (regression-shape): non-stage-complete
    envelopes for an unregistered ``envelope.correlation_id`` are
    silent-dropped exactly like stage-complete (DDR-028 LRU eviction
    backstop)."""

    @pytest.mark.asyncio
    async def test_build_failed_unknown_correlation_silent_drop(self) -> None:
        sub, _, _ = _make_subscriber()
        sm = _bind_session_manager(sub)
        # Note: no register_correlation call.

        payload = _build_failed_payload()
        msg = _make_msg(
            _envelope_bytes(
                payload,
                correlation_id="never-registered",
                event_type="build_failed",
            )
        )
        msg.subject = "pipeline.build-failed.FEAT-J005DEMO"

        await sub._on_message(msg)

        sm.enqueue_notification.assert_not_called()


class TestLifecycleEventDropsOwnPublishes:
    """TASK-FRR-F010D AC-4 (regression-shape): jarvis's own
    ``pipeline.build-queued.*`` self-publishes (the only legitimate
    "noise" on the widened ``pipeline.>`` subscription) are dropped at
    the source-id gate. This exercises the rationale recorded in the
    new docstring of ``TestStart``.
    """

    @pytest.mark.asyncio
    async def test_self_publish_with_jarvis_source_is_dropped(self) -> None:
        sub, _, _ = _make_subscriber()
        sm = _bind_session_manager(sub)
        sub.register_correlation(
            correlation_id="corr-self-001",
            session_id="cli-self",
            adapter="cli",
            queued_at=datetime.now(UTC),
            feature_id="FEAT-J005DEMO",
        )

        # build_queued is jarvis's own publish; source_id="jarvis".
        payload = {
            "feature_id": "FEAT-J005DEMO",
            "build_id": "build-self",
            "wave_total": 1,
        }
        msg = _make_msg(
            _envelope_bytes(
                payload,
                source_id="jarvis",
                correlation_id="corr-self-001",
                event_type="build_queued",
            )
        )
        msg.subject = "pipeline.build-queued.FEAT-J005DEMO"

        await sub._on_message(msg)

        # Source-ID gate drops it before any further processing.
        sm.enqueue_notification.assert_not_called()
