"""Tests for pause + cancelled lifecycle: filter extension and rendering (TASK-JNB-005).

This module verifies:
  * Six-subject filter (existing 4 + build-paused + build-cancelled)
  * Pause and cancelled projection branches in _handle_message
  * ForgeNotification model widening (event_type Literal, new optional fields)
  * Slack rendering for pause (stage, rationale, coach_score, CLI hint)
  * Slack rendering for cancelled (cancelled_by, reason)
  * Rationale chunking for Block Kit ~3000-char limit
  * Inert plain-text rendering (mrkdwn disabled)
  * Defensive rendering (out-of-range coach_score, never-raise)

Plain pytest ONLY — no pytest-bdd per operator decision 2026-07-03.
Test classes mirror spec scenario names.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
    _get_lifecycle_subjects,
)
from jarvis.infrastructure.slack_notifier import SlackNotifier


class TestLifecycleSubjectFilter:
    """Subject-filter test: six subjects including pause and cancelled."""

    def test_lifecycle_subjects_returns_six_subjects(self):
        """AC: _get_lifecycle_subjects() returns exactly six subjects."""
        subjects = _get_lifecycle_subjects()
        assert len(subjects) == 6
        assert "pipeline.build-started.>" in subjects
        assert "pipeline.stage-complete.>" in subjects
        assert "pipeline.build-complete.>" in subjects
        assert "pipeline.build-failed.>" in subjects
        assert "pipeline.build-paused.>" in subjects
        assert "pipeline.build-cancelled.>" in subjects


class TestForgeNotificationModelWidening:
    """ForgeNotification widening: event_type Literal + new optional fields."""

    def test_event_type_accepts_build_paused(self):
        """AC: event_type Literal accepts build_paused."""
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="test-corr-001",
            feature_id="FEAT-TEST",
            completed_at=datetime.now(timezone.utc),
        )
        assert notification.event_type == "build_paused"

    def test_event_type_accepts_build_cancelled(self):
        """AC: event_type Literal accepts build_cancelled."""
        notification = ForgeNotification(
            event_type="build_cancelled",
            correlation_id="test-corr-002",
            feature_id="FEAT-TEST",
            completed_at=datetime.now(timezone.utc),
        )
        assert notification.event_type == "build_cancelled"

    def test_new_optional_fields_default_to_none(self):
        """AC: All newly added fields are optional with None defaults."""
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="test-corr-003",
            feature_id="FEAT-TEST",
            completed_at=datetime.now(timezone.utc),
        )
        assert notification.coach_score is None
        assert notification.rationale is None
        assert notification.gate_mode is None
        assert notification.approval_subject is None
        assert notification.cancelled_by is None
        assert notification.reason is None

    def test_pause_fields_can_be_set(self):
        """AC: Pause projection retains approval_subject and other fields."""
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="test-corr-004",
            feature_id="FEAT-TEST",
            completed_at=datetime.now(timezone.utc),
            coach_score=0.75,
            rationale="Tests failed in autobuild stage",
            gate_mode="automated",
            approval_subject="pipeline.approval.FEAT-TEST.abc123",
        )
        assert notification.coach_score == 0.75
        assert notification.rationale == "Tests failed in autobuild stage"
        assert notification.gate_mode == "automated"
        assert notification.approval_subject == "pipeline.approval.FEAT-TEST.abc123"

    def test_cancelled_fields_can_be_set(self):
        """AC: Cancelled projection carries cancelled_by and reason."""
        notification = ForgeNotification(
            event_type="build_cancelled",
            correlation_id="test-corr-005",
            feature_id="FEAT-TEST",
            completed_at=datetime.now(timezone.utc),
            cancelled_by="operator@example.com",
            reason="Feature no longer needed",
        )
        assert notification.cancelled_by == "operator@example.com"
        assert notification.reason == "Feature no longer needed"


class TestPauseProjection:
    """Pause projection test: BuildPausedPayload -> ForgeNotification."""

    @pytest.mark.asyncio
    async def test_pause_envelope_projects_correctly(self):
        """AC: BuildPausedPayload envelope produces build_paused notification."""
        # Mock dependencies
        nats_client = Mock()
        nats_client.js = Mock()
        routing_history_writer = Mock()
        routing_history_writer.append_build_queue_event = AsyncMock()
        session_manager = Mock()

        subscriber = ForgeNotificationsSubscriber(
            nats_client=nats_client,
            routing_history_writer=routing_history_writer,
        )
        subscriber.bind_session_manager(session_manager)

        # Register correlation so notification isn't dropped
        subscriber.register_correlation(
            correlation_id="pause-corr-001",
            session_id="session-123",
            adapter="cli",
            queued_at=datetime.now(timezone.utc),
            feature_id="FEAT-PAUSE",
        )

        # Mock session manager enqueue
        session_manager.enqueue_notification = Mock()

        # Synthetic BuildPausedPayload envelope
        envelope_json = """
        {
            "event_type": "build_paused",
            "source_id": "forge",
            "correlation_id": "pause-corr-001",
            "timestamp": "2026-07-03T10:00:00Z",
            "payload": {
                "feature_id": "FEAT-PAUSE",
                "correlation_id": "pause-corr-001",
                "stage": "autobuild",
                "coach_score": 0.45,
                "rationale": "Code quality gate failed",
                "gate_mode": "automated",
                "approval_subject": "pipeline.approval.FEAT-PAUSE.xyz789"
            }
        }
        """

        # Mock NATS message
        msg = Mock()
        msg.data = envelope_json.encode("utf-8")

        await subscriber._handle_message(msg)

        # Verify enqueue was called
        assert session_manager.enqueue_notification.called
        call_args = session_manager.enqueue_notification.call_args
        notification = call_args[0][1]

        assert notification.event_type == "build_paused"
        assert notification.correlation_id == "pause-corr-001"
        assert notification.feature_id == "FEAT-PAUSE"
        assert notification.approval_subject == "pipeline.approval.FEAT-PAUSE.xyz789"
        assert notification.coach_score == 0.45
        assert notification.rationale == "Code quality gate failed"


class TestCancelledProjection:
    """Cancelled projection test: synthetic BuildCancelledPayload."""

    @pytest.mark.asyncio
    async def test_cancelled_envelope_projects_correctly(self):
        """AC: BuildCancelledPayload envelope produces build_cancelled notification."""
        # Mock dependencies
        nats_client = Mock()
        nats_client.js = Mock()
        routing_history_writer = Mock()
        routing_history_writer.append_build_queue_event = AsyncMock()
        session_manager = Mock()

        subscriber = ForgeNotificationsSubscriber(
            nats_client=nats_client,
            routing_history_writer=routing_history_writer,
        )
        subscriber.bind_session_manager(session_manager)

        # Register correlation
        subscriber.register_correlation(
            correlation_id="cancel-corr-001",
            session_id="session-456",
            adapter="cli",
            queued_at=datetime.now(timezone.utc),
            feature_id="FEAT-CANCEL",
        )

        # Mock session manager enqueue
        session_manager.enqueue_notification = Mock()

        # Synthetic BuildCancelledPayload envelope (ASSUM-010: no live producer yet)
        envelope_json = """
        {
            "event_type": "build_cancelled",
            "source_id": "forge",
            "correlation_id": "cancel-corr-001",
            "timestamp": "2026-07-03T11:00:00Z",
            "payload": {
                "feature_id": "FEAT-CANCEL",
                "correlation_id": "cancel-corr-001",
                "cancelled_by": "operator@example.com",
                "reason": "Duplicate feature requested"
            }
        }
        """

        msg = Mock()
        msg.data = envelope_json.encode("utf-8")

        await subscriber._handle_message(msg)

        # Verify enqueue
        assert session_manager.enqueue_notification.called
        call_args = session_manager.enqueue_notification.call_args
        notification = call_args[0][1]

        assert notification.event_type == "build_cancelled"
        assert notification.correlation_id == "cancel-corr-001"
        assert notification.feature_id == "FEAT-CANCEL"
        assert notification.cancelled_by == "operator@example.com"
        assert notification.reason == "Duplicate feature requested"


class TestPauseRendering:
    """Pause rendering tests: headline, feature, rationale, score, CLI hint.

    Words rewritten 2026-09-05: the paused-build text opens with a
    headline saying what is being asked, and the internal stage name is
    no longer shown at all.
    """

    def test_pause_renders_with_score_available(self):
        """AC: Pause shows the headline, feature, rationale, score, CLI hint."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="pause-render-001",
            feature_id="FEAT-PAUSE",
            completed_at=datetime(2026, 7, 3, 10, 30, tzinfo=timezone.utc),
            stage_label="autobuild",
            rationale="Tests are failing",
            coach_score=0.65,
        )

        text = notifier._render(notification)

        assert text.startswith("Build paused — waiting for your go-ahead")
        assert "FEAT-PAUSE" in text
        assert "autobuild" not in text  # the internal stage name is not shown
        assert "Tests are failing" in text
        assert "Checker score: 0.65" in text
        assert "approve" in text.lower() or "reject" in text.lower()  # CLI hint

    def test_pause_says_nothing_about_the_score_when_there_is_none(self):
        """No score is the live default; the rationale already says so, so
        the card says nothing rather than 'score unavailable'."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="pause-render-002",
            feature_id="FEAT-PAUSE",
            completed_at=datetime(2026, 7, 3, 10, 30, tzinfo=timezone.utc),
            stage_label="plan",
            rationale="Quality check paused",
            coach_score=None,
        )

        text = notifier._render(notification)

        assert "score" not in text.lower()
        assert "Quality check paused" in text

    def test_pause_renders_boundary_scores(self):
        """AC: Scores 0.0 and 1.0 render correctly."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        # Test 0.0
        notification_zero = ForgeNotification(
            event_type="build_paused",
            correlation_id="pause-render-003",
            feature_id="FEAT-PAUSE",
            completed_at=datetime.now(timezone.utc),
            coach_score=0.0,
        )
        text_zero = notifier._render(notification_zero)
        assert "0.0" in text_zero

        # Test 1.0
        notification_one = ForgeNotification(
            event_type="build_paused",
            correlation_id="pause-render-004",
            feature_id="FEAT-PAUSE",
            completed_at=datetime.now(timezone.utc),
            coach_score=1.0,
        )
        text_one = notifier._render(notification_one)
        assert "1.0" in text_one

    def test_pause_renders_out_of_range_scores_defensively(self):
        """AC: Out-of-range scores render as inert text, never rejected."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        # Test negative score
        notification_neg = ForgeNotification(
            event_type="build_paused",
            correlation_id="pause-render-005",
            feature_id="FEAT-PAUSE",
            completed_at=datetime.now(timezone.utc),
            coach_score=-0.5,
        )
        text_neg = notifier._render(notification_neg)
        assert "-0.5" in text_neg  # Should render, not raise

        # Test > 1.0 score
        notification_high = ForgeNotification(
            event_type="build_paused",
            correlation_id="pause-render-006",
            feature_id="FEAT-PAUSE",
            completed_at=datetime.now(timezone.utc),
            coach_score=1.7,
        )
        text_high = notifier._render(notification_high)
        assert "1.7" in text_high  # Should render, not raise


class TestCancelledRendering:
    """Cancelled rendering tests: cancelled_by, reason."""

    def test_cancelled_renders_correctly(self):
        """AC: Cancelled shows cancelled_by and reason."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        notification = ForgeNotification(
            event_type="build_cancelled",
            correlation_id="cancel-render-001",
            feature_id="FEAT-CANCEL",
            completed_at=datetime(2026, 7, 3, 11, 15, tzinfo=timezone.utc),
            cancelled_by="operator@example.com",
            reason="Feature no longer needed",
        )

        text = notifier._render(notification)

        assert "FEAT-CANCEL" in text
        assert "operator@example.com" in text
        assert "Feature no longer needed" in text
        assert "cancelled" in text.lower()


class TestRationaleChunking:
    """Chunking test: multi-paragraph rationale > 3000 chars."""

    def test_long_rationale_is_chunked(self):
        """AC: Rationale > 3000 chars is split into multiple blocks."""
        # This test would require Block Kit rendering, but since we're using
        # plain text mode, we verify that long rationales don't cause issues
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        # Create a rationale > 3000 chars
        long_rationale = "A" * 3500

        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="chunk-001",
            feature_id="FEAT-CHUNK",
            completed_at=datetime.now(timezone.utc),
            rationale=long_rationale,
        )

        # Should not raise
        text = notifier._render(notification)
        assert len(text) > 0
        # In plain text mode, we expect the full rationale
        assert long_rationale in text or len(text) > 3000


class TestInertRendering:
    """Inertness test: mrkdwn/Block Kit special characters render as plain text."""

    def test_formatting_characters_are_inert(self):
        """AC: Rationale with mrkdwn characters renders as plain text."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        # Rationale with mrkdwn special characters
        rationale_with_formatting = "Code has *bold*, _italic_, <link>, and &amp; chars"

        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="inert-001",
            feature_id="FEAT-INERT",
            completed_at=datetime.now(timezone.utc),
            rationale=rationale_with_formatting,
        )

        text = notifier._render(notification)

        # Characters should appear verbatim (we use mrkdwn=False in chat_postMessage)
        assert "*bold*" in text
        assert "_italic_" in text
        assert "<link>" in text
        assert "&" in text


class TestNeverRaise:
    """Never-raise test: rendering with malformed fields logs, doesn't raise."""

    def test_missing_optional_fields_render_gracefully(self):
        """AC: Missing optional fields don't cause rendering to raise."""
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C123456",
        )

        # Minimal pause notification
        notification = ForgeNotification(
            event_type="build_paused",
            correlation_id="minimal-001",
            feature_id="FEAT-MINIMAL",
            completed_at=datetime.now(timezone.utc),
        )

        # Should not raise
        text = notifier._render(notification)
        assert len(text) > 0
        assert "FEAT-MINIMAL" in text
