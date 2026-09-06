"""The merge-deploy outcome line (make-merge-work spec, 2026-08-24).

The spec's step 5: after the owner presses [ Merge & deploy ], code runs
merge → re-check → sandbox deploy → live verify → **report in one line**.
Forge publishes the outcome as a ``pipeline.stage-complete.{feature_id}``
event with ``stage_label == "merge-deploy"`` and additive raw fields
(``result``, ``merged_sha``, ``failed_step``, ``verdict``,
``checks_passed``, ``checks_total``, ``detail``). Before this lane,
jarvis consumed every stage-complete but NEVER sent one to the Slack
sink — the outcome of the owner's own button press went unreported.

What is fenced here:

* **The projection.** Only ``stage_label == "merge-deploy"`` reaches the
  sink; every other stage label keeps the no-sink behaviour and its CLI
  line byte-identically. The seam sits BEFORE the correlation lookup, so
  a jarvis restart between build and merge press cannot cost the owner
  the line. The additive fields are read defensively off the raw payload
  dict — absent or junk values degrade to None, a malformed
  ``completed_at`` falls back to the envelope timestamp, and a raising
  sink is WARNING-only (DDR-007).
* **The copy.** Four result classes, plain sentences per the owner's
  language law: merged-and-running (with the checks tally), the
  automatic-rollback story, the stopped-at-a-step story, and NO line for
  "rejected" — the card already shows that decision. Since the
  deploy-into-Docker-Sandboxes spec (2026-09-06) the success sentence
  also says where the deploy ran, but only when forge says
  ``deployed_in: "docker-sandbox"``; every other value, and no value at
  all, leaves every line byte-identical to before.
* **The mention.** The outcome line answers the owner's own press, so it
  rides the existing terminal-line mention chain (planning target →
  gate clicker → sole operator → nobody), with forge-authored strings
  escaped on the one path where markup parsing is on.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest

from jarvis.infrastructure.build_audience import BuildAudienceRegistry
from jarvis.infrastructure.forge_notifications import (
    ForgeNotification,
    ForgeNotificationsSubscriber,
)
from jarvis.infrastructure.slack_notifier import SlackNotifier

_AT = datetime(2026, 8, 24, 12, 2, tzinfo=UTC)
_HHMM = _AT.astimezone().strftime("%H:%M")
_ENVELOPE_TS = "2026-08-24T11:02:00+00:00"
_CORR = "corr-e613-merge"
_BUILD = "build-FEAT-E613-20260824"


# ---------------------------------------------------------------------------
# Helpers — the wire side (payload dict → envelope bytes → subscriber)
# ---------------------------------------------------------------------------


def _merge_payload(
    *,
    correlation_id: str = _CORR,
    feature_id: str = "FEAT-E613",
    stage_label: str = "merge-deploy",
    status: str = "PASSED",
    completed_at: str | None = None,
    **raw: Any,
) -> dict[str, Any]:
    """A StageCompletePayload dict; ``**raw`` adds the additive fields."""
    payload: dict[str, Any] = {
        "feature_id": feature_id,
        "build_id": _BUILD,
        "stage_label": stage_label,
        "target_kind": "local_tool",
        "target_identifier": "merge-executor",
        "status": status,
        "gate_mode": None,
        "coach_score": None,
        "duration_secs": 42.0,
        "completed_at": completed_at or _AT.isoformat(),
        "correlation_id": correlation_id,
    }
    payload.update(raw)
    return payload


def _envelope_bytes(
    payload: dict[str, Any],
    *,
    source_id: str = "forge",
    correlation_id: str | None = None,
) -> bytes:
    body: dict[str, Any] = {
        "message_id": "11111111-1111-1111-1111-111111111111",
        "timestamp": _ENVELOPE_TS,
        "version": "1.0",
        "source_id": source_id,
        "event_type": "stage_complete",
        "project": None,
        "correlation_id": correlation_id or payload.get("correlation_id"),
        "payload": payload,
    }
    return json.dumps(body).encode("utf-8")


def _msg(data: bytes) -> mock.MagicMock:
    m = mock.MagicMock()
    m.data = data
    m.subject = "pipeline.stage-complete.FEAT-E613"
    m.ack = mock.AsyncMock()
    return m


def _subscriber(
    *,
    bind_sink: bool = True,
    register: bool = True,
) -> tuple[ForgeNotificationsSubscriber, mock.MagicMock, mock.MagicMock]:
    """A subscriber with mocked broker/writer, a sink mock, and a session."""
    js = mock.MagicMock()
    js.subscribe = mock.AsyncMock(return_value=mock.MagicMock())
    nats_client = mock.MagicMock()
    nats_client.js = js

    writer = mock.MagicMock()
    writer.append_build_queue_event = mock.AsyncMock()

    sub = ForgeNotificationsSubscriber(
        nats_client=nats_client,
        routing_history_writer=writer,
        queue_cap=100,
        correlation_cap=1000,
    )

    sink = mock.MagicMock()
    sink.notify = mock.AsyncMock()
    if bind_sink:
        sub.bind_notification_sink(sink)

    session_manager = mock.MagicMock()
    session_manager.enqueue_notification = mock.MagicMock()
    sub.bind_session_manager(session_manager)

    if register:
        sub.register_correlation(_CORR, "sess-1", "cli", datetime.now(UTC), "FEAT-E613")

    return sub, sink, session_manager


# ---------------------------------------------------------------------------
# Helpers — the Slack side (notification → rendered line)
# ---------------------------------------------------------------------------


def _notifier(
    *,
    audience: BuildAudienceRegistry | None = None,
    operator_ids: frozenset[str] = frozenset(),
) -> SlackNotifier:
    """A SlackNotifier with a fully mocked web client — no network."""
    with patch("slack_sdk.web.async_client.AsyncWebClient") as mock_cls:
        mock_cls.return_value = AsyncMock()
        return SlackNotifier(
            bot_token="xoxb-test",
            channel_id="C123456",
            audience=audience,
            operator_ids=operator_ids,
        )


def _outcome(**overrides: Any) -> ForgeNotification:
    fields: dict[str, Any] = {
        "event_type": "stage_complete",
        "correlation_id": _CORR,
        "feature_id": "FEAT-E613",
        "stage_label": "merge-deploy",
        "status": "PASSED",
        "completed_at": _AT,
        "build_id": _BUILD,
        "result": "merged-and-running",
        "checks_passed": 7,
        "checks_total": 7,
    }
    fields.update(overrides)
    return ForgeNotification(**fields)


_RUNNING_LINE = (
    f"[{_HHMM}] Pipeline FEAT-E613: merged and running — checks 7/7. "
    "Rollback is one command; the branch is kept."
)

# The one new sentence (deploy-into-Docker-Sandboxes spec, 2026-09-06),
# pinned byte-for-byte exactly as the spec writes it.
_SANDBOX_RUNNING_LINE = (
    f"[{_HHMM}] Pipeline FEAT-E613: merged and running in its Docker Sandbox "
    "— checks 7/7. Rollback is one command; the branch is kept."
)


# ---------------------------------------------------------------------------
# The projection: what reaches the sink, and what never does
# ---------------------------------------------------------------------------


class TestSinkProjection:
    """forge's merge-deploy stage-complete → one sink notification."""

    @pytest.mark.asyncio
    async def test_merged_and_running_projects_every_field(self) -> None:
        sub, sink, session_manager = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            merged_sha="0abc123",
            verdict="GREEN",
            checks_passed=7,
            checks_total=7,
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.event_type == "stage_complete"
        assert n.stage_label == "merge-deploy"
        assert n.status == "PASSED"
        assert n.result == "merged-and-running"
        assert n.checks_passed == 7
        assert n.checks_total == 7
        assert n.feature_id == "FEAT-E613"
        assert n.correlation_id == _CORR
        assert n.build_id == _BUILD
        assert n.completed_at == _AT
        # The CLI path is untouched: the registered correlation still
        # gets today's stage line enqueued.
        assert session_manager.enqueue_notification.call_count == 1

    @pytest.mark.asyncio
    async def test_correlation_miss_still_notifies_sink(self) -> None:
        """A jarvis restart between build and press must not eat the line."""
        sub, sink, session_manager = _subscriber(register=False)
        payload = _merge_payload(result="merged-and-running")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        session_manager.enqueue_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_rejected_sends_no_line_but_cli_path_is_untouched(self) -> None:
        """The card already shows the decision — no Slack line is owed."""
        sub, sink, session_manager = _subscriber()
        payload = _merge_payload(result="rejected")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_not_awaited()
        assert session_manager.enqueue_notification.call_count == 1

    @pytest.mark.asyncio
    async def test_other_stage_labels_never_reach_the_sink(self) -> None:
        """Byte-identical: an ordinary stage keeps today's behaviour whole."""
        sub, sink, session_manager = _subscriber()
        # Even a hostile payload carrying a result field stays sink-less
        # when the label is not merge-deploy.
        payload = _merge_payload(stage_label="plan-complete", result="merged-and-running")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_not_awaited()
        assert session_manager.enqueue_notification.call_count == 1
        queued = session_manager.enqueue_notification.call_args.args[1]
        # The CLI projection never reads the raw outcome fields.
        assert queued.result is None
        assert queued.render_line() == (
            f"[{_HHMM}] Forge FEAT-E613: stage plan-complete (PASSED)"
        )

    @pytest.mark.asyncio
    async def test_absent_additive_fields_degrade_to_none(self) -> None:
        """An older forge that sends none of the new fields still reports."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload()  # no result / checks / detail at all

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.result is None
        assert n.failed_step is None
        assert n.detail is None
        assert n.checks_passed is None
        assert n.checks_total is None
        assert n.status == "PASSED"

    @pytest.mark.asyncio
    async def test_junk_additive_fields_degrade_to_none(self) -> None:
        """Junk in the raw dict costs a clause, never the line."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result=42,
            checks_passed="seven",
            checks_total=True,
            failed_step="   ",
            detail="",
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.result is None
        assert n.checks_passed is None
        assert n.checks_total is None
        assert n.failed_step is None
        assert n.detail is None

    @pytest.mark.asyncio
    async def test_deployed_in_reaches_the_sink(self) -> None:
        """Where the deploy ran travels with the outcome (2026-09-06)."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            checks_passed=7,
            checks_total=7,
            deployed_in="docker-sandbox",
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.deployed_in == "docker-sandbox"

    @pytest.mark.asyncio
    async def test_absent_deployed_in_degrades_to_none(self) -> None:
        """An older forge that never sends the field still reports."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        n = sink.notify.await_args.args[0]
        assert n.deployed_in is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("junk", [42, True, "", "   ", None, ["docker-sandbox"], {}])
    async def test_junk_deployed_in_degrades_to_none(self, junk: Any) -> None:
        """Junk costs the clause, never the line — same posture as the rest."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", deployed_in=junk)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.deployed_in is None

    @pytest.mark.asyncio
    async def test_negative_counts_are_refused(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", checks_passed=-1, checks_total=7)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        n = sink.notify.await_args.args[0]
        assert n.checks_passed is None
        assert n.checks_total == 7

    @pytest.mark.asyncio
    async def test_bad_completed_at_falls_back_to_envelope_timestamp(self) -> None:
        """A malformed timestamp costs precision, never the line."""
        sub, sink, session_manager = _subscriber()
        payload = _merge_payload(result="merged-and-running", completed_at="not-a-timestamp")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.completed_at == datetime(2026, 8, 24, 11, 2, tzinfo=UTC)
        # Today's CLI behaviour for a bad completed_at (drop with WARN)
        # is preserved byte-identically.
        session_manager.enqueue_notification.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_raising_sink_never_propagates_and_the_cli_path_survives(self) -> None:
        sub, sink, session_manager = _subscriber()
        sink.notify.side_effect = RuntimeError("boom")
        payload = _merge_payload(result="merged-and-running")

        await sub._handle_message(_msg(_envelope_bytes(payload)))  # must not raise

        assert session_manager.enqueue_notification.call_count == 1

    @pytest.mark.asyncio
    async def test_no_sink_bound_is_harmless(self) -> None:
        sub, sink, session_manager = _subscriber(bind_sink=False)
        payload = _merge_payload(result="merged-and-running")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_not_awaited()
        assert session_manager.enqueue_notification.call_count == 1


# ---------------------------------------------------------------------------
# The copy: one exact line per result class
# ---------------------------------------------------------------------------


class TestTheOutcomeLines:
    """Plain sentences, the owner's language law — pinned byte-for-byte."""

    def test_merged_and_running_line_exact(self) -> None:
        assert _notifier()._render(_outcome()) == _RUNNING_LINE

    def test_missing_counts_drop_the_checks_clause(self) -> None:
        text = _notifier()._render(_outcome(checks_passed=None, checks_total=None))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged and running. "
            "Rollback is one command; the branch is kept."
        )

    def test_one_sided_counts_also_drop_the_clause(self) -> None:
        text = _notifier()._render(_outcome(checks_total=None))
        assert "checks" not in text

    def test_sandbox_running_line_exact(self) -> None:
        """The spec's sentence, byte-for-byte (2026-09-06)."""
        text = _notifier()._render(_outcome(deployed_in="docker-sandbox"))
        assert text == _SANDBOX_RUNNING_LINE

    def test_sandbox_line_without_counts_still_drops_the_checks_clause(self) -> None:
        text = _notifier()._render(
            _outcome(deployed_in="docker-sandbox", checks_passed=None, checks_total=None)
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged and running in its Docker "
            "Sandbox. Rollback is one command; the branch is kept."
        )

    def test_sandbox_wording_survives_an_unrecognised_result_on_a_passed_stage(
        self,
    ) -> None:
        """The success branch is claimed by status as well as by result."""
        text = _notifier()._render(_outcome(result=None, deployed_in="docker-sandbox"))
        assert text == _SANDBOX_RUNNING_LINE

    @pytest.mark.parametrize(
        ("deployed_in", "expected"),
        [
            ("docker-sandbox", _SANDBOX_RUNNING_LINE),
            (None, _RUNNING_LINE),
            ("Docker-Sandbox", _RUNNING_LINE),
            ("DOCKER-SANDBOX", _RUNNING_LINE),
            ("docker-sandbox ", _RUNNING_LINE),
            ("docker", _RUNNING_LINE),
            ("docker-sandboxes", _RUNNING_LINE),
            ("host-docker", _RUNNING_LINE),
            ("gvisor", _RUNNING_LINE),
        ],
    )
    def test_only_the_exact_docker_sandbox_value_changes_the_line(
        self, deployed_in: str | None, expected: str
    ) -> None:
        """One value names the sandbox; every other value, and none at all,
        leaves the sentence exactly as it read before this lane."""
        assert _notifier()._render(_outcome(deployed_in=deployed_in)) == expected

    def test_the_reverted_line_is_unchanged_inside_a_sandbox(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-reverted",
                status="FAILED",
                deployed_in="docker-sandbox",
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged, then the deploy failed its "
            "checks and rolled back automatically — the live copy was never "
            "broken. The branch is kept."
        )

    def test_the_stopped_line_is_unchanged_inside_a_sandbox(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="re-check",
                detail="two tests failed by name",
                deployed_in="docker-sandbox",
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "re-check — two tests failed by name. Nothing half-done; the "
            "branch is kept."
        )

    def test_an_ordinary_stage_line_ignores_deployed_in(self) -> None:
        text = _notifier()._render(
            _outcome(
                stage_label="plan-complete",
                result=None,
                checks_passed=None,
                checks_total=None,
                deployed_in="docker-sandbox",
            )
        )
        assert text == f"[{_HHMM}] Pipeline FEAT-E613: stage plan-complete (PASSED)"

    def test_a_rejected_outcome_ignores_deployed_in_too(self) -> None:
        text = _notifier()._render(_outcome(result="rejected", deployed_in="docker-sandbox"))
        assert text == f"[{_HHMM}] Pipeline FEAT-E613: stage merge-deploy (PASSED)"

    def test_a_hostile_deployed_in_never_reaches_the_line(self) -> None:
        """The field is compared to one literal, never interpolated — so
        forge's bytes cannot land on the owner's line through it."""
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(
            _outcome(deployed_in="<!here> <http://evil.com|clickme>")
        )
        assert text == f"<@U0RICH> {_RUNNING_LINE}"
        assert "evil.com" not in text
        assert "<!here>" not in text

    def test_reverted_line_exact(self) -> None:
        text = _notifier()._render(_outcome(result="merged-deploy-reverted", status="FAILED"))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged, then the deploy failed its "
            "checks and rolled back automatically — the live copy was never "
            "broken. The branch is kept."
        )

    def test_deploy_failed_line_exact(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="re-check",
                detail="two tests failed by name",
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "re-check — two tests failed by name. Nothing half-done; the "
            "branch is kept."
        )

    def test_merge_refused_defaults_to_the_merge_step(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                detail="main moved since the checks ran",
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "the merge — main moved since the checks ran. Nothing half-done; "
            "the branch is kept."
        )

    def test_stopped_without_detail_drops_the_why_clause(self) -> None:
        text = _notifier()._render(_outcome(result="merged-deploy-failed", status="FAILED"))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "the merge. Nothing half-done; the branch is kept."
        )

    def test_unknown_result_on_a_passed_stage_reads_as_running(self) -> None:
        """The validated status field carries an unrecognised result value."""
        text = _notifier()._render(_outcome(result="something-new"))
        assert text == _RUNNING_LINE

    def test_absent_result_on_a_passed_stage_reads_as_running(self) -> None:
        text = _notifier()._render(_outcome(result=None))
        assert text == _RUNNING_LINE

    def test_unknown_result_on_a_failed_stage_reads_as_stopped(self) -> None:
        text = _notifier()._render(
            _outcome(result=None, status="FAILED", checks_passed=None, checks_total=None)
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "the merge. Nothing half-done; the branch is kept."
        )

    def test_a_rejected_outcome_reaching_the_renderer_falls_back_to_the_stage_line(
        self,
    ) -> None:
        """Defence in depth: the subscriber never forwards a rejected
        outcome, but if one arrives the renderer invents no claim."""
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(_outcome(result="rejected"))
        assert text == f"[{_HHMM}] Pipeline FEAT-E613: stage merge-deploy (PASSED)"
        assert "<@" not in text

    def test_ordinary_stage_lines_are_byte_identical(self) -> None:
        text = _notifier()._render(
            _outcome(
                stage_label="plan-complete",
                result=None,
                checks_passed=None,
                checks_total=None,
            )
        )
        assert text == f"[{_HHMM}] Pipeline FEAT-E613: stage plan-complete (PASSED)"

    def test_ordinary_stage_lines_never_gain_a_mention(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry, operator_ids=frozenset({"U0SOLE"}))._render(
            _outcome(stage_label="plan-complete", result=None)
        )
        assert "<@" not in text


# ---------------------------------------------------------------------------
# The mention: the line answers the owner's own press
# ---------------------------------------------------------------------------


class TestTheMentionChain:
    """The existing terminal-line chain, reused rung for rung."""

    def test_planning_target_is_mentioned(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(_outcome())
        assert text == f"<@U0RICH> {_RUNNING_LINE}"

    def test_gate_clicker_answers_by_build_id(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_gate_clicker(_BUILD, "U0CLICK")
        text = _notifier(audience=registry)._render(_outcome())
        assert text.startswith("<@U0CLICK> ")

    def test_sole_operator_is_mentioned(self) -> None:
        text = _notifier(operator_ids=frozenset({"U0SOLE"}))._render(_outcome())
        assert text.startswith("<@U0SOLE> ")

    def test_nobody_wired_means_an_unmentioned_line(self) -> None:
        text = _notifier()._render(_outcome())
        assert text == _RUNNING_LINE

    def test_hostile_detail_is_inert_on_a_mentioned_line(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="live checks",
                detail="<http://evil.com|clickme>",
            )
        )
        assert text.startswith("<@U0RICH> ")
        assert "<http://evil.com|clickme>" not in text
        assert "&lt;http://evil.com|clickme&gt;" in text

    def test_hostile_failed_step_is_inert_on_a_mentioned_line(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(
            _outcome(result="merge-refused", status="FAILED", failed_step="<!here>")
        )
        assert "<!here>" not in text
        assert "&lt;!here&gt;" in text

    def test_the_unmentioned_line_keeps_forge_bytes_verbatim(self) -> None:
        """No mention, no parsing, no escaping — the inert-text posture."""
        hostile = "<http://evil.com|clickme>"
        text = _notifier()._render(
            _outcome(result="merged-deploy-failed", status="FAILED", detail=hostile)
        )
        assert hostile in text
        assert "&lt;" not in text


# ---------------------------------------------------------------------------
# Delivery and dedup: through notify() and the worker, no network
# ---------------------------------------------------------------------------


class TestDeliveryAndDedup:
    @staticmethod
    async def _post_kwargs(notifier: SlackNotifier, notification: Any) -> dict[str, Any]:
        client = AsyncMock()
        notifier._client = client
        await notifier.start()
        try:
            await notifier.notify(notification)
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
        finally:
            await notifier.stop()
        return dict(client.chat_postMessage.await_args.kwargs)

    @pytest.mark.asyncio
    async def test_the_posted_sandbox_line_is_plain_text_too(self) -> None:
        kwargs = await self._post_kwargs(_notifier(), _outcome(deployed_in="docker-sandbox"))
        assert kwargs["text"] == _SANDBOX_RUNNING_LINE
        assert "blocks" not in kwargs
        assert kwargs["mrkdwn"] is False

    @pytest.mark.asyncio
    async def test_the_wire_payload_renders_the_sandbox_line_end_to_end(self) -> None:
        """forge's raw payload → the subscriber → the exact owner-facing line."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            checks_passed=7,
            checks_total=7,
            deployed_in="docker-sandbox",
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == _SANDBOX_RUNNING_LINE

    @pytest.mark.asyncio
    async def test_the_posted_line_is_plain_text_with_no_action_surface(self) -> None:
        kwargs = await self._post_kwargs(_notifier(), _outcome())
        assert kwargs["text"] == _RUNNING_LINE
        assert "blocks" not in kwargs
        assert kwargs["mrkdwn"] is False

    @pytest.mark.asyncio
    async def test_a_mentioned_outcome_posts_with_markup_parsing_on(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        kwargs = await self._post_kwargs(_notifier(audience=registry), _outcome())
        assert kwargs["text"].startswith("<@U0RICH> ")
        assert kwargs["mrkdwn"] is True

    def test_two_runs_outcomes_never_share_a_dedup_key(self) -> None:
        """Keyed on correlation_id: blank build ids can never collide."""
        notifier = _notifier()
        k1 = notifier._make_dedup_key(_outcome(build_id=None))
        k2 = notifier._make_dedup_key(_outcome(build_id=None, correlation_id="corr-other-run"))
        assert k1 != k2

    def test_a_redelivered_outcome_shares_its_dedup_key(self) -> None:
        notifier = _notifier()
        assert notifier._make_dedup_key(_outcome()) == notifier._make_dedup_key(_outcome())
