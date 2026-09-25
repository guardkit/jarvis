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
* **The candidate checked before the merge (protect-main, 2026-09-07).**
  Forge now builds a candidate from the feature branch, runs the live
  checks against it, and only then merges and promotes that exact build.
  It says so with a ``gate_before_merge`` block and, on a refusal, the
  result ``candidate-refused`` and the repair row's number. Three new
  sentences, pinned byte for byte from the spec: the green run, the
  refusal, and the main that moved under a passing check. Every one of
  them needs the block; an older forge that sends none keeps every line
  exactly as it read before.
* **Where the merge landed (sandbox first, 2026-09-07).** When a
  repository's factory runs in its own sandbox, the merge lands in the
  factory's copy of the repository and not in the operator's checkout.
  Forge sends a ``sandbox_merge`` block holding one plain sentence that
  says so and gives the exact command that brings the merge over; jarvis
  adds that sentence to the end of the green line, word for word, and
  changes nothing else. No block, or a block with nothing to say, and
  every line reads exactly as it did.
* **The reason a person reads is the reason it happened (2026-09-10).**
  A merge turned away after a passing check is only called a moved main
  when forge's own report says main moved. Every other refusal — a
  branch that is not there, a dirty working tree, a conflict — names the
  step forge stopped at and repeats forge's own reason, so the owner can
  see what stopped it without opening a log and is never sent to fix
  something that is not broken.
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

# The three sentences of the candidate-before-merge order (protect-main
# spec, 2026-09-07), pinned byte-for-byte exactly as the spec writes them.
_CHECKED_LINE = (
    f"[{_HHMM}] Pipeline FEAT-E613: checked in the sandbox (7 of 7), merged, and running."
)
_REFUSED_LINE = (
    f"[{_HHMM}] Pipeline FEAT-E613: checked in the sandbox before merging — "
    "failed 2 of 7 checks (users_roundtrip, count_by_domain), so nothing was "
    "merged. The branch is kept; repair row #12 is filed."
)
_MOVED_LINE = (
    f"[{_HHMM}] Pipeline FEAT-E613: the checks passed but main had moved since "
    "this was built, so nothing was merged; send the sentence again."
)

# Forge's own sentence when main moved during the build, copied from its
# side (its merge executor writes it and puts it on the report as the
# detail) so the two cannot drift apart. It is the ONLY thing that says
# main moved: nothing in the check block names which guard turned the
# merge away, so a report that does not say this gets the honest line
# naming the step and forge's own reason instead.
_MOVED_MAIN_DETAIL = (
    "FEAT-E613 passed its sandbox check, but main had moved since this was "
    "built (a1b2c3d4e5 is not in the branch); nothing was merged and the "
    "branch is kept. Send the sentence again."
)

# The other sentence for the same event, copied from the merge command's
# own check just before it merges (its merge executor writes it) and
# passed onto the report by forge word for word. This is the ORDINARY
# way a moved main is refused: main moved on after the offer was made,
# so the branch still holds the commit forge looks for and forge's own
# check lets it through. The owner must read the same line for it.
_MOVED_MAIN_PREFLIGHT_DETAIL = (
    "main has moved since the checks ran "
    "(expected 9f1c0b2ad3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8, "
    "found 0e1d2c3b4a5968778695a4b3c2d1e0f9a8b7c6d5)"
)


def _gate(**overrides: Any) -> dict[str, Any]:
    """A ``gate_before_merge`` block as forge sends it; overrides edit it."""
    block: dict[str, Any] = {
        "verdict": "pass",
        "checks_passed": 7,
        "checks_total": 7,
        "candidate_sha": "c0ffee1234567890",
        "candidate_tree": "tree-aaaa1111",
        "merged_tree": "tree-aaaa1111",
    }
    block.update(overrides)
    return block


def _refused_gate(**overrides: Any) -> dict[str, Any]:
    """The block for a candidate that failed two of seven checks."""
    block: dict[str, Any] = {
        "verdict": "fail",
        "checks_passed": 5,
        "checks_total": 7,
        "merged_tree": None,
        "failed_checks": ["users_roundtrip", "count_by_domain"],
    }
    block.update(overrides)
    return _gate(**block)


# The sandbox-first block (2026-09-07): forge writes the whole sentence,
# command and all, and jarvis prints it as it stands. These are forge's own
# words, copied from its side so the two cannot drift apart.
_SANDBOX_NAME = "api-test-factory"
_CHECKOUT = "/a/checkout/of/api_test"
_FETCH_COMMAND = (
    f"git -C {_CHECKOUT} fetch sandbox-{_SANDBOX_NAME} main && "
    f"git -C {_CHECKOUT} merge --ff-only sandbox-{_SANDBOX_NAME}/main"
)
_LANDED_SENTENCE = (
    "This merge landed in the factory's own copy of the repository, inside "
    f"the sandbox {_SANDBOX_NAME} — not in your checkout at {_CHECKOUT}. To "
    f"bring it to your checkout, run: {_FETCH_COMMAND}"
)


def _landed(**overrides: Any) -> dict[str, Any]:
    """A ``sandbox_merge`` block as forge sends it; overrides edit it."""
    block: dict[str, Any] = {
        "sandbox": _SANDBOX_NAME,
        "remote": f"sandbox-{_SANDBOX_NAME}",
        "checkout": _CHECKOUT,
        "fetch_command": _FETCH_COMMAND,
        "sentence": _LANDED_SENTENCE,
    }
    block.update(overrides)
    return block


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


class TestGateBeforeMergeProjection:
    """The candidate check's record rides the raw payload into the sink."""

    @pytest.mark.asyncio
    async def test_the_block_projects_every_field(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="candidate-refused",
            status="FAILED",
            gate_before_merge=_refused_gate(),
            repair_row=12,
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        n = sink.notify.await_args.args[0]
        assert n.result == "candidate-refused"
        gate = n.gate_before_merge
        assert gate is not None
        assert gate.verdict == "fail"
        assert gate.checks_passed == 5
        assert gate.checks_total == 7
        assert gate.candidate_sha == "c0ffee1234567890"
        assert gate.candidate_tree == "tree-aaaa1111"
        assert gate.merged_tree is None
        assert gate.failed_checks == ("users_roundtrip", "count_by_domain")
        assert n.repair_row == "12"

    @pytest.mark.asyncio
    async def test_an_older_forge_that_sends_no_block_projects_none(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", checks_passed=7, checks_total=7)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        n = sink.notify.await_args.args[0]
        assert n.gate_before_merge is None
        assert n.repair_row is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("junk", [42, "pass", [], ["pass"], True, None, ""])
    async def test_a_block_that_is_not_a_mapping_projects_none(self, junk: Any) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", gate_before_merge=junk)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        assert sink.notify.await_args.args[0].gate_before_merge is None

    @pytest.mark.asyncio
    async def test_junk_inside_the_block_degrades_field_by_field(self) -> None:
        """Each field costs itself, never its neighbours or the line."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="candidate-refused",
            status="FAILED",
            gate_before_merge={
                "verdict": 7,
                "checks_passed": "five",
                "checks_total": 7,
                "candidate_sha": "   ",
                "candidate_tree": None,
                "merged_tree": ["tree"],
                "failed_checks": "users_roundtrip",
                "something_new": {"ignored": True},
            },
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        gate = sink.notify.await_args.args[0].gate_before_merge
        assert gate is not None
        assert gate.verdict is None
        assert gate.checks_passed is None
        assert gate.checks_total == 7
        assert gate.candidate_sha is None
        assert gate.candidate_tree is None
        assert gate.merged_tree is None
        assert gate.failed_checks == ()

    @pytest.mark.asyncio
    async def test_junk_items_in_the_names_list_are_dropped(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="candidate-refused",
            status="FAILED",
            gate_before_merge=_refused_gate(
                failed_checks=["users_roundtrip", "", "   ", 3, None, " health "]
            ),
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        gate = sink.notify.await_args.args[0].gate_before_merge
        assert gate is not None
        assert gate.failed_checks == ("users_roundtrip", "health")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("sent", "expected"),
        [
            (12, "12"),
            ("12", "12"),
            ("#12", "12"),
            (" # 12 ", "12"),
            (0, None),
            (-3, None),
            (True, None),
            ("twelve", None),
            ("", None),
            ("#", None),
            (None, None),
            ([12], None),
        ],
    )
    async def test_the_repair_row_number_in_every_shape_forge_might_send(
        self, sent: Any, expected: str | None
    ) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="candidate-refused", status="FAILED", repair_row=sent)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        assert sink.notify.await_args.args[0].repair_row == expected

    @pytest.mark.asyncio
    async def test_a_refused_candidate_still_reaches_the_sink(self) -> None:
        """A new result word is not 'rejected': the line is owed."""
        sub, sink, session_manager = _subscriber()
        payload = _merge_payload(result="candidate-refused", status="FAILED")

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        assert session_manager.enqueue_notification.call_count == 1


class TestSandboxMergeProjection:
    """Where the merge landed rides the raw payload into the sink."""

    @pytest.mark.asyncio
    async def test_the_block_projects_every_field(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", sandbox_merge=_landed())

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        landed = sink.notify.await_args.args[0].sandbox_merge
        assert landed is not None
        assert landed.sandbox == _SANDBOX_NAME
        assert landed.remote == f"sandbox-{_SANDBOX_NAME}"
        assert landed.checkout == _CHECKOUT
        assert landed.fetch_command == _FETCH_COMMAND
        assert landed.sentence == _LANDED_SENTENCE

    @pytest.mark.asyncio
    async def test_a_forge_that_sends_no_block_projects_none(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", checks_passed=7, checks_total=7)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        assert sink.notify.await_args.args[0].sandbox_merge is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("junk", [42, "a sentence", [], [{}], True, None, "", {}])
    async def test_a_block_of_the_wrong_shape_projects_none(self, junk: Any) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(result="merged-and-running", sandbox_merge=junk)

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        assert sink.notify.await_args.args[0].sandbox_merge is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("sentence", [None, "", "   ", 7, ["a sentence"], {"a": 1}])
    async def test_a_block_with_nothing_to_say_projects_none(self, sentence: Any) -> None:
        """The sentence is the whole point; without one there is no block."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running", sandbox_merge=_landed(sentence=sentence)
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        sink.notify.assert_awaited_once()
        assert sink.notify.await_args.args[0].sandbox_merge is None

    @pytest.mark.asyncio
    async def test_junk_in_the_other_fields_never_costs_the_sentence(self) -> None:
        """Each field costs itself, never the sentence a person reads."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            sandbox_merge={
                "sandbox": 7,
                "remote": "   ",
                "checkout": None,
                "fetch_command": ["git"],
                "sentence": _LANDED_SENTENCE,
                "something_new": {"ignored": True},
            },
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        landed = sink.notify.await_args.args[0].sandbox_merge
        assert landed is not None
        assert landed.sandbox is None
        assert landed.remote is None
        assert landed.checkout is None
        assert landed.fetch_command is None
        assert landed.sentence == _LANDED_SENTENCE

    def test_the_block_survives_the_notification_round_trip(self) -> None:
        """Dumped and read back, the notification still carries the words."""
        notification = _outcome(sandbox_merge=_landed())

        again = ForgeNotification.model_validate(notification.model_dump(mode="json"))

        assert again.sandbox_merge == notification.sandbox_merge
        assert again.sandbox_merge is not None
        assert again.sandbox_merge.sentence == _LANDED_SENTENCE
        assert again.sandbox_merge.fetch_command == _FETCH_COMMAND

    def test_a_notification_without_the_block_round_trips_to_none(self) -> None:
        again = ForgeNotification.model_validate(_outcome().model_dump(mode="json"))

        assert again.sandbox_merge is None


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
# The copy since the candidate is checked before the merge (2026-09-07)
# ---------------------------------------------------------------------------


class TestTheProtectMainLines:
    """The spec's three sentences, byte for byte; today's words otherwise."""

    # --- the green run -----------------------------------------------------

    def test_checked_merged_and_running_line_exact(self) -> None:
        text = _notifier()._render(_outcome(gate_before_merge=_gate()))
        assert text == _CHECKED_LINE

    def test_the_green_line_does_not_name_the_sandbox_twice(self) -> None:
        """``deployed_in`` shaped the old sentence; the new one already
        says where the check ran, so the field changes nothing."""
        text = _notifier()._render(
            _outcome(gate_before_merge=_gate(), deployed_in="docker-sandbox")
        )
        assert text == _CHECKED_LINE

    def test_the_gates_counts_win_over_the_reports_counts(self) -> None:
        text = _notifier()._render(
            _outcome(gate_before_merge=_gate(), checks_passed=5, checks_total=5)
        )
        assert text == _CHECKED_LINE

    def test_the_reports_counts_fill_in_when_the_block_carries_none(self) -> None:
        text = _notifier()._render(
            _outcome(gate_before_merge=_gate(checks_passed=None, checks_total=None))
        )
        assert text == _CHECKED_LINE

    def test_a_block_with_no_counts_anywhere_keeps_todays_words(self) -> None:
        """The spec's sentence carries a tally; without one, no claim of a
        tally is invented — the report reads as it did before."""
        text = _notifier()._render(
            _outcome(
                gate_before_merge=_gate(checks_passed=None, checks_total=None),
                checks_passed=None,
                checks_total=None,
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged and running. "
            "Rollback is one command; the branch is kept."
        )

    def test_a_passed_stage_with_an_unrecognised_result_still_reads_as_checked(self) -> None:
        text = _notifier()._render(_outcome(result=None, gate_before_merge=_gate()))
        assert text == _CHECKED_LINE

    def test_no_block_keeps_the_old_green_lines_byte_for_byte(self) -> None:
        assert _notifier()._render(_outcome()) == _RUNNING_LINE
        assert _notifier()._render(_outcome(deployed_in="docker-sandbox")) == _SANDBOX_RUNNING_LINE

    # --- the refusal ---------------------------------------------------------

    def _refused(self, **overrides: Any) -> ForgeNotification:
        fields: dict[str, Any] = {
            "result": "candidate-refused",
            "status": "FAILED",
            "checks_passed": None,
            "checks_total": None,
            "gate_before_merge": _refused_gate(),
            "repair_row": "12",
            "failed_step": "the candidate check",
            "detail": "2 of 7 live checks failed against the candidate",
        }
        fields.update(overrides)
        return _outcome(**fields)

    def test_refused_line_exact(self) -> None:
        assert _notifier()._render(self._refused()) == _REFUSED_LINE

    def test_without_a_repair_row_the_sentence_ends_at_the_branch_is_kept(self) -> None:
        """Forge carries the row's number when it filed one; when the report
        has none, jarvis names no row — the sentence simply ends."""
        text = _notifier()._render(self._refused(repair_row=None))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: checked in the sandbox before merging — "
            "failed 2 of 7 checks (users_roundtrip, count_by_domain), so nothing "
            "was merged. The branch is kept."
        )

    def test_without_names_the_names_clause_is_dropped(self) -> None:
        text = _notifier()._render(self._refused(gate_before_merge=_refused_gate(failed_checks=[])))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: checked in the sandbox before merging — "
            "failed 2 of 7 checks, so nothing was merged. The branch is kept; "
            "repair row #12 is filed."
        )

    def test_one_failed_check_counts_as_one(self) -> None:
        text = _notifier()._render(
            self._refused(
                gate_before_merge=_refused_gate(checks_passed=6, failed_checks=["health"]),
                repair_row=None,
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: checked in the sandbox before merging — "
            "failed 1 of 7 checks (health), so nothing was merged. The branch is kept."
        )

    def test_the_gates_tally_wins_over_the_reports_tally_on_a_refusal(self) -> None:
        text = _notifier()._render(self._refused(checks_passed=7, checks_total=7))
        assert text == _REFUSED_LINE

    def test_a_refusal_without_a_tally_keeps_todays_stopped_line(self) -> None:
        """No counts anywhere: no tally is invented. Forge's own step and
        reason carry the line, in the shape every stop has always had."""
        text = _notifier()._render(
            self._refused(
                gate_before_merge=_gate(verdict="fail", checks_passed=None, checks_total=None)
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at the "
            "candidate check — 2 of 7 live checks failed against the candidate. "
            "Nothing half-done; the branch is kept."
        )

    def test_a_refusal_without_the_block_keeps_todays_stopped_line(self) -> None:
        text = _notifier()._render(self._refused(gate_before_merge=None))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at the "
            "candidate check — 2 of 7 live checks failed against the candidate. "
            "Nothing half-done; the branch is kept."
        )

    def test_a_refusal_whose_tally_shows_nothing_failed_keeps_todays_stopped_line(self) -> None:
        """A candidate that could not even come up has a 7/7-shaped tally
        and a refusal; 'failed 0 of 7' would be a lie, so the stop line
        with forge's reason stands instead."""
        text = _notifier()._render(
            self._refused(
                gate_before_merge=_gate(
                    verdict="environment_fail", checks_passed=7, checks_total=7
                ),
                detail="the candidate never became healthy",
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at the "
            "candidate check — the candidate never became healthy. "
            "Nothing half-done; the branch is kept."
        )

    def test_a_refusal_is_never_read_as_success_whatever_the_status_says(self) -> None:
        text = _notifier()._render(self._refused(status="PASSED"))
        assert text == _REFUSED_LINE

    # --- a main that moved ---------------------------------------------------

    def test_moved_main_line_exact(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                failed_step="merge",
                detail=_MOVED_MAIN_DETAIL,
                gate_before_merge=_gate(merged_tree=None),
            )
        )
        assert text == _MOVED_LINE

    def test_tree_mismatch_line_exact(self) -> None:
        """The exact-tree guard refused the promote: the same sentence."""
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="promote",
                detail="the merged tree differs from the candidate's tree",
                gate_before_merge=_gate(merged_tree="tree-bbbb2222"),
            )
        )
        assert text == _MOVED_LINE

    def test_a_refused_merge_without_the_block_keeps_todays_words(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                detail="main moved since the checks ran",
                checks_passed=None,
                checks_total=None,
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "the merge — main moved since the checks ran. Nothing half-done; "
            "the branch is kept."
        )

    def test_a_refused_merge_whose_block_does_not_say_pass_keeps_todays_words(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                detail="a merge step is already on record for this build",
                gate_before_merge=_gate(verdict=None, merged_tree=None),
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "the merge — a merge step is already on record for this build. "
            "Nothing half-done; the branch is kept."
        )

    def test_matching_trees_keep_todays_stopped_line(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="promote",
                detail="the promote runbook exited 1",
                gate_before_merge=_gate(),
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "promote — the promote runbook exited 1. Nothing half-done; "
            "the branch is kept."
        )

    def test_one_tree_missing_is_not_a_mismatch(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="promote",
                gate_before_merge=_gate(verdict=None, merged_tree=None),
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at "
            "promote. Nothing half-done; the branch is kept."
        )

    # --- every other result keeps its words ----------------------------------

    def test_the_reverted_line_is_unchanged_with_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-reverted",
                status="FAILED",
                gate_before_merge=_gate(),
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged, then the deploy failed its "
            "checks and rolled back automatically — the live copy was never "
            "broken. The branch is kept."
        )

    def test_a_rejected_outcome_ignores_the_block(self) -> None:
        text = _notifier()._render(_outcome(result="rejected", gate_before_merge=_gate()))
        assert text == f"[{_HHMM}] Pipeline FEAT-E613: stage merge-deploy (PASSED)"

    def test_an_ordinary_stage_line_ignores_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(
                stage_label="plan-complete",
                result=None,
                checks_passed=None,
                checks_total=None,
                gate_before_merge=_gate(),
            )
        )
        assert text == f"[{_HHMM}] Pipeline FEAT-E613: stage plan-complete (PASSED)"

    # --- the mention and the inert-text posture ------------------------------

    def test_the_refusal_rides_the_mention_chain(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(self._refused())
        assert text == f"<@U0RICH> {_REFUSED_LINE}"

    def test_a_hostile_check_name_is_inert_on_a_mentioned_line(self) -> None:
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(
            self._refused(
                gate_before_merge=_refused_gate(
                    failed_checks=["<http://evil.com|clickme>", "<!here>"]
                )
            )
        )
        assert text.startswith("<@U0RICH> ")
        assert "<http://evil.com|clickme>" not in text
        assert "<!here>" not in text
        assert "(&lt;http://evil.com|clickme&gt;, &lt;!here&gt;)" in text

    def test_a_hostile_repair_row_is_inert_on_a_mentioned_line(self) -> None:
        """The projection only ever admits digits; the renderer escapes the
        field anyway, so a directly built notification cannot slip markup
        through it either."""
        registry = BuildAudienceRegistry()
        registry.record_planning_target(_CORR, "U0RICH")
        text = _notifier(audience=registry)._render(self._refused(repair_row="<!here>"))
        assert "<!here>" not in text
        assert "repair row #&lt;!here&gt; is filed." in text

    def test_the_unmentioned_refusal_keeps_forge_bytes_verbatim(self) -> None:
        hostile = "<http://evil.com|clickme>"
        text = _notifier()._render(
            self._refused(gate_before_merge=_refused_gate(failed_checks=[hostile]))
        )
        assert hostile in text
        assert "&lt;" not in text

    # --- end to end: forge's raw payload → the exact line ---------------------

    @pytest.mark.asyncio
    async def test_the_wire_payload_renders_the_checked_line_end_to_end(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            merged_sha="0abc123",
            checks_passed=7,
            checks_total=7,
            deployed_in="docker-sandbox",
            gate_before_merge=_gate(),
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == _CHECKED_LINE

    @pytest.mark.asyncio
    async def test_the_wire_payload_renders_the_refusal_end_to_end(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="candidate-refused",
            status="FAILED",
            failed_step="the candidate check",
            detail="2 of 7 live checks failed against the candidate",
            gate_before_merge=_refused_gate(),
            repair_row=12,
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == _REFUSED_LINE

    @pytest.mark.asyncio
    async def test_the_wire_payload_renders_the_moved_main_end_to_end(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merge-refused",
            status="FAILED",
            failed_step="merge",
            detail=_MOVED_MAIN_DETAIL,
            gate_before_merge=_gate(merged_tree=None),
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == _MOVED_LINE

    @pytest.mark.asyncio
    async def test_the_posted_refusal_is_plain_text(self) -> None:
        notifier = _notifier()
        client = AsyncMock()
        notifier._client = client
        await notifier.start()
        try:
            await notifier.notify(self._refused())
            for _ in range(200):
                if client.chat_postMessage.await_count:
                    break
                await asyncio.sleep(0.01)
        finally:
            await notifier.stop()
        kwargs = dict(client.chat_postMessage.await_args.kwargs)
        assert kwargs["text"] == _REFUSED_LINE
        assert "blocks" not in kwargs
        assert kwargs["mrkdwn"] is False


# ---------------------------------------------------------------------------
# The reason a person reads is the reason it happened (2026-09-10)
# ---------------------------------------------------------------------------


class TestTheRefusalNamesItsOwnReason:
    """A merge turned away after a passing check says WHY it was turned
    away, in forge's own words.

    On 2026-09-10 the owner said merge on FEAT-39F6, the candidate passed
    all eight of its checks, and the merge was refused because the branch
    the merge needed was not there — the fix journey's commits were on a
    fix branch. Slack told him main had moved. Main had not moved: the
    ancestry was intact and forge's own report said "branch
    autobuild/FEAT-39F6 does not exist". He read the sentence, believed
    it, and went looking for a problem that did not exist while the real
    one stayed hidden.

    The cause was reading the SHAPE of the report — a candidate that
    passed plus a merge that was refused — as proof that main had moved,
    when that shape is equally true of a missing branch, a dirty working
    tree and a conflict. Nothing on the report names which guard turned
    the merge away, so the moved-main sentence now waits for forge to say
    main moved, and every other refusal repeats the step and the reason
    forge already wrote.
    """

    # The real refusal, as forge reported it that day.
    _REAL_DETAIL = "branch autobuild/FEAT-39F6 does not exist"

    def _the_real_refusal(self, **overrides: Any) -> ForgeNotification:
        fields: dict[str, Any] = {
            "feature_id": "FEAT-39F6",
            "build_id": "build-FEAT-39F6-20260910110821",
            "result": "merge-refused",
            "status": "FAILED",
            "failed_step": "merge",
            "detail": self._REAL_DETAIL,
            "gate_before_merge": _gate(checks_passed=8, checks_total=8, merged_tree=None),
        }
        fields.update(overrides)
        return _outcome(**fields)

    def test_the_missing_branch_is_named_and_main_is_not(self) -> None:
        text = _notifier()._render(self._the_real_refusal())
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-39F6: merge-and-deploy stopped at "
            "merge — branch autobuild/FEAT-39F6 does not exist. Nothing "
            "half-done; the branch is kept."
        )
        assert "main" not in text.removeprefix(f"[{_HHMM}] Pipeline FEAT-39F6: ")

    @pytest.mark.asyncio
    async def test_the_real_wire_payload_reads_the_same_end_to_end(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            feature_id="FEAT-39F6",
            result="merge-refused",
            status="FAILED",
            failed_step="merge",
            detail=self._REAL_DETAIL,
            gate_before_merge=_gate(checks_passed=8, checks_total=8, merged_tree=None),
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == (
            f"[{_HHMM}] Pipeline FEAT-39F6: merge-and-deploy stopped at "
            "merge — branch autobuild/FEAT-39F6 does not exist. Nothing "
            "half-done; the branch is kept."
        )

    def test_a_dirty_working_tree_is_named_too(self) -> None:
        text = _notifier()._render(
            self._the_real_refusal(
                detail="the working tree has uncommitted changes",
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-39F6: merge-and-deploy stopped at "
            "merge — the working tree has uncommitted changes. Nothing "
            "half-done; the branch is kept."
        )

    def test_a_conflict_is_named_too(self) -> None:
        text = _notifier()._render(
            self._the_real_refusal(detail="the merge conflicted in src/app.py")
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-39F6: merge-and-deploy stopped at "
            "merge — the merge conflicted in src/app.py. Nothing half-done; "
            "the branch is kept."
        )

    def test_a_refusal_with_no_detail_invents_no_cause(self) -> None:
        """Forge said nothing about why, so neither does the line — and it
        certainly does not say main moved."""
        text = _notifier()._render(self._the_real_refusal(detail=None))
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-39F6: merge-and-deploy stopped at "
            "merge. Nothing half-done; the branch is kept."
        )

    def test_a_main_that_really_moved_keeps_todays_sentence(self) -> None:
        """Forge's own detail says main moved, so the owner reads exactly
        what he read before — byte for byte."""
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                failed_step="merge",
                detail=_MOVED_MAIN_DETAIL,
                gate_before_merge=_gate(merged_tree=None),
            )
        )
        assert text == _MOVED_LINE

    def test_a_main_that_moved_before_the_merge_keeps_todays_sentence_too(self) -> None:
        """The ordinary moved main: main moved on between the offer and
        the merge, so the merge command's own check turned it away and
        said so in its own words. Same event, same line — and the owner
        still reads the one thing he has to do."""
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                failed_step="merge",
                detail=_MOVED_MAIN_PREFLIGHT_DETAIL,
                gate_before_merge=_gate(merged_tree=None),
            )
        )
        assert text == _MOVED_LINE

    def test_the_tree_that_differs_keeps_its_own_words(self) -> None:
        """The other guard states its case in the report itself — the two
        tree ids differ — so it is unaffected by what the detail says."""
        text = _notifier()._render(
            _outcome(
                result="merged-deploy-failed",
                status="FAILED",
                failed_step="promote",
                detail="the merged commit's tree is not the tree that was checked",
                gate_before_merge=_gate(merged_tree="tree-bbbb2222"),
            )
        )
        assert text == _MOVED_LINE

    def test_a_green_merge_is_byte_identical(self) -> None:
        assert _notifier()._render(_outcome(gate_before_merge=_gate())) == _CHECKED_LINE

    def test_a_failed_candidate_is_byte_identical(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="candidate-refused",
                status="FAILED",
                failed_step="the candidate check",
                detail="2 of 7 live checks failed against the candidate",
                gate_before_merge=_refused_gate(),
                repair_row="12",
            )
        )
        assert text == _REFUSED_LINE


# ---------------------------------------------------------------------------
# Where the merge landed (sandbox first, 2026-09-07)
# ---------------------------------------------------------------------------


class TestTheSandboxMergeSentence:
    """A repository whose factory runs in its own sandbox has its merge
    land in the factory's copy of the repository, not in the operator's
    checkout. Forge writes that sentence, command and all; jarvis adds it
    to the end of the green line exactly as forge wrote it, and adds
    nothing anywhere else."""

    def test_the_checked_line_ends_with_forges_sentence(self) -> None:
        text = _notifier()._render(_outcome(gate_before_merge=_gate(), sandbox_merge=_landed()))
        assert text == f"{_CHECKED_LINE} {_LANDED_SENTENCE}"
        assert text.endswith(_LANDED_SENTENCE)

    def test_the_older_success_line_ends_with_forges_sentence(self) -> None:
        text = _notifier()._render(_outcome(sandbox_merge=_landed()))
        assert text == f"{_RUNNING_LINE} {_LANDED_SENTENCE}"
        assert text.endswith(_LANDED_SENTENCE)

    def test_the_docker_sandbox_success_line_ends_with_it_too(self) -> None:
        text = _notifier()._render(_outcome(deployed_in="docker-sandbox", sandbox_merge=_landed()))
        assert text == f"{_SANDBOX_RUNNING_LINE} {_LANDED_SENTENCE}"

    def test_the_success_line_without_counts_ends_with_it_too(self) -> None:
        text = _notifier()._render(
            _outcome(checks_passed=None, checks_total=None, sandbox_merge=_landed())
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged and running. "
            f"Rollback is one command; the branch is kept. {_LANDED_SENTENCE}"
        )

    def test_the_sentence_is_added_word_for_word_and_nothing_else(self) -> None:
        """jarvis never rewrites forge's sentence, and never invents one."""
        text = _notifier()._render(_outcome(gate_before_merge=_gate(), sandbox_merge=_landed()))
        assert text.count(_LANDED_SENTENCE) == 1
        assert text == f"{_CHECKED_LINE} {_LANDED_SENTENCE}"
        assert _FETCH_COMMAND in text

    def test_no_block_keeps_the_green_lines_byte_for_byte(self) -> None:
        notifier = _notifier()
        assert notifier._render(_outcome()) == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged and running — checks 7/7. "
            "Rollback is one command; the branch is kept."
        )
        assert notifier._render(_outcome(deployed_in="docker-sandbox")) == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged and running in its Docker "
            "Sandbox — checks 7/7. Rollback is one command; the branch is kept."
        )
        assert notifier._render(_outcome(gate_before_merge=_gate())) == (
            f"[{_HHMM}] Pipeline FEAT-E613: checked in the sandbox (7 of 7), merged, and running."
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "malformed",
        ["a sentence", 42, [], None, {}, {"sandbox": "api-test-factory"}],
    )
    async def test_a_malformed_block_leaves_the_line_exactly_as_it_was(
        self, malformed: Any
    ) -> None:
        """Words on a line must never be the thing that costs the line."""
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            checks_passed=7,
            checks_total=7,
            sandbox_merge=malformed,
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == _RUNNING_LINE

    @pytest.mark.asyncio
    async def test_a_block_with_an_empty_sentence_leaves_the_checked_line_alone(
        self,
    ) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            gate_before_merge=_gate(),
            sandbox_merge=_landed(sentence="   "),
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == _CHECKED_LINE

    @pytest.mark.asyncio
    async def test_the_wire_payload_renders_the_landed_line_end_to_end(self) -> None:
        sub, sink, _ = _subscriber()
        payload = _merge_payload(
            result="merged-and-running",
            merged_sha="0abc123",
            checks_passed=7,
            checks_total=7,
            deployed_in="docker-sandbox",
            gate_before_merge=_gate(),
            sandbox_merge=_landed(),
        )

        await sub._handle_message(_msg(_envelope_bytes(payload)))

        notification = sink.notify.await_args.args[0]
        assert _notifier()._render(notification) == f"{_CHECKED_LINE} {_LANDED_SENTENCE}"

    # --- everything that is not a green merge is untouched --------------------

    def test_the_refusal_line_ignores_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="candidate-refused",
                status="FAILED",
                gate_before_merge=_refused_gate(),
                repair_row="12",
                sandbox_merge=_landed(),
            )
        )
        assert text == _REFUSED_LINE

    def test_the_moved_main_line_ignores_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merge-refused",
                status="FAILED",
                detail=_MOVED_MAIN_DETAIL,
                gate_before_merge=_gate(merged_tree=None),
                sandbox_merge=_landed(),
            )
        )
        assert text == _MOVED_LINE

    def test_the_reverted_line_ignores_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(result="merged-deploy-reverted", sandbox_merge=_landed())
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merged, then the deploy failed its "
            "checks and rolled back automatically — the live copy was never "
            "broken. The branch is kept."
        )

    def test_the_stopped_line_ignores_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(
                result="merge-failed",
                status="FAILED",
                failed_step="merge",
                detail="a conflict in src/app.py",
                sandbox_merge=_landed(),
            )
        )
        assert text == (
            f"[{_HHMM}] Pipeline FEAT-E613: merge-and-deploy stopped at merge — "
            "a conflict in src/app.py. Nothing half-done; the branch is kept."
        )

    def test_an_ordinary_stage_line_ignores_the_block(self) -> None:
        text = _notifier()._render(
            _outcome(stage_label="build", result=None, sandbox_merge=_landed())
        )
        assert _LANDED_SENTENCE not in text


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


class TestTheRefusalSaysWhatTheCheckSaw:
    """Forge has always sent what the failed check saw; nothing read it.

    On 2026-09-12 a refusal named "created-per-day" and stopped there. The
    endpoint had answered 503 from its own database-error handler, and only
    forge's log said so — an hour of digging for a fact that was already in
    the payload. These pin that the fact reaches the line, and that a report
    without it reads exactly as it did before.
    """

    _SAW = [
        {
            "gate_id": "created-per-day",
            "id": "created-per-day::status",
            "expected": 200,
            "observed": 503,
        }
    ]

    def _refused(self, **overrides: Any) -> ForgeNotification:
        return _outcome(
            result="candidate-refused",
            status="FAILED",
            checks_passed=None,
            checks_total=None,
            gate_before_merge=_refused_gate(
                checks_passed=6,
                failed_checks=["created-per-day"],
                **overrides,
            ),
            repair_row=None,
            failed_step="the candidate check",
            detail="1 of 7 live checks failed against the candidate",
        )

    def test_the_line_names_what_the_check_expected_and_what_it_saw(self) -> None:
        text = _notifier()._render(self._refused(failed_assertions=self._SAW))
        assert "expected 200, saw 503" in text
        assert "created-per-day (created-per-day::status)" in text
        # The sentence it already had is untouched, and the new clause follows it.
        assert "failed 1 of 7 checks (created-per-day), so nothing was merged" in text
        assert text.index("The branch is kept") < text.index("The first thing that failed")

    def test_it_says_how_many_more_the_report_holds(self) -> None:
        text = _notifier()._render(
            self._refused(
                failed_assertions=self._SAW + [dict(self._SAW[0], id="created-per-day::body")],
                failed_assertions_left_out=3,
            )
        )
        assert "The report lists 4 more." in text

    def test_a_check_that_said_nothing_is_named_as_such(self) -> None:
        text = _notifier()._render(
            self._refused(failed_assertions=[{"gate_id": "health", "id": "health"}])
        )
        assert "did not say what it saw" in text

    def test_without_the_detail_the_line_is_what_it_always_was(self) -> None:
        """An older forge, or a check that sent nothing, reads byte for byte."""
        text = _notifier()._render(self._refused())
        assert "The first thing that failed" not in text
        assert text.endswith("failed 1 of 7 checks (created-per-day), so nothing was merged. The branch is kept.")

    def test_junk_costs_the_clause_never_the_line(self) -> None:
        """Junk is dropped where every raw payload is read — the projector.

        A real report reaches jarvis as a raw mapping and is projected field
        by field; nothing that is not a mapping survives into the block, so
        the clause is simply absent and the sentence stands.
        """
        from jarvis.infrastructure.forge_notifications import _gate_before_merge

        block = _gate_before_merge(
            _refused_gate(
                checks_passed=6,
                failed_checks=["created-per-day"],
                failed_assertions=["nonsense", 5],
            )
        )
        assert block is not None
        assert block.failed_assertions == ()
