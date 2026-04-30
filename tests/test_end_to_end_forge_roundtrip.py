"""End-to-end Forge round-trip — Phase 3 close-criterion evidence test.

TASK-J005-012 — see ``tasks/design_approved/TASK-J005-012-end-to-end-forge-roundtrip.md``.

This is the **Phase 3 close-criterion** evidence test per
``docs/research/ideas/phase3-build-plan.md`` Step 14. It is a *soft-prereq*
test — it requires real Forge + real NATS + real Graphiti running on the
GB10 box, plus all subagent provider keys for any subagent dispatch the
chosen FEAT-JARVIS-INTERNAL-001 build entails. When the prereqs are not
present (CI default, MacBook-only, no operator-provisioned env-vars) the
test **skips with a clear reason** instead of failing — this is the AC-001
no-spurious-failures contract.

The full round-trip exercised:

    queue_build → BuildQueuedPayload published on JetStream
                → Forge consumes the build-queued event
                → Forge runs its pipeline stages
                → Forge publishes ``pipeline.stage-complete.*`` events
                → Jarvis ForgeNotificationsSubscriber routes each event
                → SessionManager per-session FIFO receives the
                  notification (CLI render shape per DDR-030)
                → RoutingHistoryWriter appends one Graphiti edge per
                  stage-complete event under the originating
                  JarvisRoutingHistoryEntry.

Acceptance criteria mapping (from the task file):

    AC-001  Test skips cleanly when GB10 env-vars absent.
    AC-002  When prereqs present, runs to completion within 10 minutes.
    AC-003  Asserts the full round-trip — queue_build → publish → Forge
            consumes → stage-complete events → subscriber routes →
            CLI queue → Graphiti edges.
    AC-004  Asserts ≥ 3 distinct stage-complete edges land in Graphiti
            (one per ``plan-complete`` / ``autobuild-complete`` /
            ``task-review-complete`` stage event observed).
    AC-005  Failure modes produce structured pytest output naming the
            failing assertion (correlation lookup miss, edge missing).
    AC-006  Records the session transcript and Graphiti trace dump as
            test attachments — the Phase 3 evidence artefact.

Marked ``@pytest.mark.e2e`` so it can be opted out of laptop / CI runs
via ``pytest -m "not e2e"``.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Module-level logger — used to write structured evidence attachments to the
# pytest output stream so a failing assertion gives Coach actionable diagnostics.
# ---------------------------------------------------------------------------
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-flight skip — AC-001
#
# The conftest.py autouse ``_stub_nats_and_graphiti_connect_seams`` fixture
# stubs the NATS + Graphiti connect seams to ``None`` for every test in the
# suite (so unit tests cannot accidentally hit a live broker). For the
# end-to-end test we *want* those seams to call the real connect path so the
# round-trip exercises a live JetStream + Graphiti deployment. The fixture
# below re-patches the seams back to their original implementations for the
# duration of the test, but only when the operator has set the GB10 env-vars
# — otherwise the test skips before any patching happens.
# ---------------------------------------------------------------------------
REQUIRED_ENV_VARS: tuple[str, ...] = (
    "JARVIS_NATS_URL",
    "JARVIS_GRAPHITI_ENDPOINT",
)

# Per phase3-build-plan §13: Rich selects a FEAT-JARVIS-INTERNAL-001
# candidate (docstring polish / trace-schema refinement / skill scaffolding)
# before this test runs and passes the feature_id via env var. Reproducible
# across operator runs.
DEFAULT_E2E_FEATURE_ID = "FEAT-JARVIS-INTERNAL-001"
E2E_FEATURE_ID_ENV = "JARVIS_E2E_FEATURE_ID"
E2E_FEATURE_YAML_ENV = "JARVIS_E2E_FEATURE_YAML"
E2E_REPO_ENV = "JARVIS_E2E_REPO"

# Stage-complete labels we expect Forge to emit (per task §7). At least three
# distinct labels must arrive for AC-004 to pass.
EXPECTED_STAGE_LABELS: frozenset[str] = frozenset(
    {"plan-complete", "autobuild-complete", "task-review-complete"}
)

# Bounded wait — the task's AC-002 is "≤ 10 minutes" total, and §6 states the
# stage-event wait specifically is "≤ 5 minutes". We honour the tighter
# bound so a hanging Forge instance produces a structured failure rather
# than a 10-minute timeout that masks the real symptom.
STAGE_WAIT_BUDGET_SECONDS: float = 300.0
POLL_INTERVAL_SECONDS: float = 1.0


def _missing_required_env_vars() -> list[str]:
    """Return the env-var names that are unset or empty.

    Both ``unset`` and the empty string are treated as "absent" so an
    operator who exports an empty value (e.g. ``export JARVIS_NATS_URL=``)
    sees the same skip as one who never set it at all.
    """
    return [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]


# ---------------------------------------------------------------------------
# Live-seam fixture — restore the real ``_connect_nats`` / ``_connect_graphiti``
# implementations for the duration of the e2e test, overriding the autouse
# stub from conftest.py.
# ---------------------------------------------------------------------------
@pytest.fixture()
def _live_connect_seams() -> Any:
    """Re-patch the lifecycle connect seams back to their real implementations.

    The autouse ``_stub_nats_and_graphiti_connect_seams`` fixture in
    ``tests/conftest.py`` replaces both seams with ``AsyncMock(return_value=None)``
    so unit tests never hit a live broker. The e2e test needs the opposite
    — it must talk to the real GB10 deployment. We restore the seam by
    patching it with the original module function (resolved via
    ``importlib.import_module`` to avoid capturing the stub) for the
    duration of the test.

    Yields once with both seams live; the inner ``patch`` context managers
    unwind on test teardown so subsequent unit tests retain the stub.
    """
    # Resolve the real implementations from the source module — these
    # references survive the autouse patch because the patch replaces
    # ``lifecycle._connect_nats`` (an attribute on the lifecycle module),
    # not the function objects themselves.
    from jarvis.infrastructure.lifecycle import (
        _connect_graphiti as _real_connect_graphiti,
    )
    from jarvis.infrastructure.lifecycle import _connect_nats as _real_connect_nats
    from jarvis.infrastructure.nats_client import NATSClient

    async def _live_nats(config: Any) -> Any:
        # Bypass the autouse stub by calling NATSClient.connect directly —
        # ``_real_connect_nats`` may itself have been replaced by the
        # autouse fixture in older pytest contexts, so use the class method
        # which the original lifecycle helper delegates to.
        return await NATSClient.connect(config)

    async def _live_graphiti(config: Any) -> Any:
        # Defer to the original module-level helper. Resolving via the
        # imported name (rather than ``getattr`` on the module) means the
        # autouse fixture's patch on ``lifecycle._connect_graphiti`` does
        # not affect this closure.
        return await _real_connect_graphiti(config)

    with (
        patch(
            "jarvis.infrastructure.lifecycle._connect_nats",
            new=_live_nats,
        ),
        patch(
            "jarvis.infrastructure.lifecycle._connect_graphiti",
            new=_live_graphiti,
        ),
    ):
        # The closures reference _real_connect_nats so the linter doesn't
        # flag it as unused — but we route NATS via NATSClient.connect to
        # match the production lifecycle path.
        del _real_connect_nats
        yield


# ---------------------------------------------------------------------------
# Evidence attachment helper — AC-006
#
# pytest captures stdout/stderr by default; structured records dropped on
# the failure path land in the captured output and surface in the JUnit XML
# / pytest summary as evidence. We also write the transcript + trace dump
# to ``tmp_path / "phase3-evidence-{correlation_id}.json"`` so the artefact
# survives beyond the test run when pytest is invoked with
# ``--basetemp=<dir>``.
# ---------------------------------------------------------------------------
def _write_evidence_attachment(
    tmp_path: Path,
    correlation_id: str,
    transcript: list[dict[str, Any]],
    trace_dump: dict[str, Any],
) -> Path:
    """Persist the Phase 3 evidence artefact for the operator to inspect.

    Args:
        tmp_path: pytest's per-test temp directory.
        correlation_id: BuildQueuedPayload correlation_id under test.
        transcript: Ordered list of ``{event, payload, timestamp}`` records
            captured during the round-trip.
        trace_dump: Best-effort snapshot of the routing-history writer's
            ``_correlation_edge_seq`` for the correlation under test.

    Returns:
        Absolute path to the JSON artefact.
    """
    artefact_path = tmp_path / f"phase3-evidence-{correlation_id}.json"
    artefact_path.write_text(
        json.dumps(
            {
                "task_id": "TASK-J005-012",
                "correlation_id": correlation_id,
                "transcript": transcript,
                "trace_dump": trace_dump,
                "captured_at": datetime.now().isoformat(),
            },
            indent=2,
            default=str,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return artefact_path


# ---------------------------------------------------------------------------
# §1 — The end-to-end test
# ---------------------------------------------------------------------------
@pytest.mark.e2e
@pytest.mark.asyncio
class TestEndToEndForgeRoundTrip:
    """AC-001..AC-006 — Phase 3 close-criterion evidence."""

    async def test_full_forge_round_trip(
        self,
        tmp_path: Path,
        _live_connect_seams: Any,  # noqa: PT019 — fixture name mirrors private intent
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Drive a real ``queue_build`` through Forge and assert the full round-trip.

        Skips cleanly (AC-001) when ``JARVIS_NATS_URL`` /
        ``JARVIS_GRAPHITI_ENDPOINT`` are absent — laptops, CI, and any
        environment without GB10 reachability hit this branch first. The
        test never fails as a side-effect of missing infrastructure.

        Body (only runs when prereqs are present):

        1. Build :class:`JarvisConfig` from env (no overrides — pydantic
           settings reads ``JARVIS_NATS_URL`` / ``JARVIS_GRAPHITI_ENDPOINT``
           directly from the operator's exported environment).
        2. ``await build_app_state(config)`` — full lifecycle wiring
           including the live ``ForgeNotificationsSubscriber`` bound to
           ``pipeline.stage-complete.>``.
        3. Start a CLI session so the dispatch session-hook resolves to a
           real attended adapter.
        4. Fire ``queue_build.ainvoke({...})`` with the operator-selected
           feature_id (``JARVIS_E2E_FEATURE_ID`` env var; defaults to
           ``FEAT-JARVIS-INTERNAL-001``).
        5. Parse the QueueBuildAck JSON; assert ``correlation_id`` is
           present and that the subscriber's correlation map registered
           the entry (AC-003 — round-trip head).
        6. Poll the per-session pending-notifications FIFO every 1s for
           up to 5 minutes until ≥ 3 distinct stage-complete labels have
           been observed (AC-004) or the budget expires.
        7. Assert the routing-history writer appended ≥ 3 stage-complete
           Graphiti edges under ``correlation_id`` (AC-003 — round-trip
           tail; AC-004 minimum count).
        8. Persist the transcript + trace dump as a JSON attachment under
           ``tmp_path`` for operator inspection (AC-006).
        9. ``await shutdown(state)`` — clean drain even on assertion
           failure (try/finally guards every step from #2 onwards).

        AC-005 — every assertion in this test names the failing
        invariant in its message string so a structured pytest output line
        identifies the broken hop without the operator having to grep
        through the captured log.
        """
        # AC-001 — skip BEFORE we touch anything live.
        missing = _missing_required_env_vars()
        if missing:
            pytest.skip(
                "End-to-end Forge round-trip requires real GB10 "
                f"infrastructure. Missing env-vars: {sorted(missing)}. "
                "Set JARVIS_NATS_URL=nats://promaxgb10-41b1:4222 and "
                "JARVIS_GRAPHITI_ENDPOINT=<falkordb-endpoint> on the operator "
                "host before re-running with -m e2e."
            )

        caplog.set_level(logging.INFO)

        # Imports deferred until after the skip check so a missing optional
        # extra (e.g. graphiti-core) on a laptop install does not break the
        # collection-time skip path. ``ImportError`` on the live path is
        # itself diagnostic and will surface as a structured pytest failure.
        from jarvis.config.settings import JarvisConfig
        from jarvis.infrastructure.lifecycle import build_app_state, shutdown
        from jarvis.shared.constants import Adapter
        from jarvis.tools.dispatch import queue_build

        # AC-002 — total wall budget. We track it ourselves so a hung
        # subscriber surfaces as a structured assertion rather than a
        # pytest test-timeout (which produces a less useful traceback).
        deadline = time.monotonic() + 600.0  # 10 minutes hard cap
        transcript: list[dict[str, Any]] = []

        def _log_event(event: str, **payload: Any) -> None:
            """Append a structured record to the transcript + caplog."""
            record = {
                "event": event,
                "timestamp": datetime.now().isoformat(),
                **payload,
            }
            transcript.append(record)
            _logger.info("e2e_forge_roundtrip", extra={"record": record})

        # 1. Build JarvisConfig from the operator's exported env. We do
        # NOT clear os.environ here — pydantic-settings reads the live
        # process env, which is exactly what we want for an e2e run.
        config = JarvisConfig()
        _log_event(
            "config_loaded",
            nats_url=config.nats_url,
            graphiti_endpoint=config.graphiti_endpoint,
            supervisor_model=config.supervisor_model,
        )

        # 2. Bring up the full Jarvis runtime against the real GB10 env.
        state = await build_app_state(config)
        _log_event(
            "app_state_built",
            nats_available=state.nats_client is not None,
            graphiti_available=state.graphiti_client is not None,
            forge_subscriber_started=state.forge_subscriber is not None,
        )

        try:
            # AC-003 — the round-trip starts at the subscriber. If the
            # subscriber failed to start, the soft-fail surfaces via
            # ``state.forge_subscriber is None`` and the test cannot
            # assert any of its downstream invariants — fail loud.
            assert state.forge_subscriber is not None, (
                "Round-trip pre-condition failed: ForgeNotificationsSubscriber "
                "did not start. NATS broker reachable but JetStream context "
                "rejected the subscribe — check JetStream is enabled "
                "and the pipeline.stage-complete.> stream is provisioned."
            )
            assert state.routing_history_writer is not None, (
                "Round-trip pre-condition failed: RoutingHistoryWriter is "
                "None. Graphiti soft-fail produced a degraded-mode writer "
                "but the e2e test requires a live Graphiti to assert edges."
            )
            assert state.graphiti_client is not None, (
                "Round-trip pre-condition failed: graphiti_client is None. "
                "JARVIS_GRAPHITI_ENDPOINT was set but the connect attempt "
                "soft-failed — check FalkorDB is up at the configured URL."
            )

            # 3. Start a CLI session so dispatch's session-hook returns a
            # real attended adapter. The adapter is "cli" — one of the
            # ATTENDED_ADAPTER_IDS — so queue_build will not be rejected
            # by Layer-2 attended-only gating.
            session = state.session_manager.start_session(
                adapter=Adapter.CLI,
                user_id="phase3-evidence-operator",
            )
            _log_event(
                "session_started",
                session_id=session.session_id,
                adapter=str(session.adapter),
            )

            # ``_current_session_var`` is a per-instance ContextVar; setting
            # it makes ``SessionManager.current_session()`` (and therefore
            # ``dispatch._resolve_current_session``) return the session for
            # the duration of this contextvars context. We do the equivalent
            # of ``SessionManager.invoke``'s wrapping but without invoking
            # the supervisor — the e2e test fires queue_build directly
            # so the round-trip is deterministic regardless of LLM weights.
            ctx = contextvars.copy_context()

            async def _run_in_session_context() -> str:
                token = state.session_manager._current_session_var.set(session)
                try:
                    feature_id = os.environ.get(
                        E2E_FEATURE_ID_ENV, DEFAULT_E2E_FEATURE_ID
                    )
                    feature_yaml_path = os.environ.get(
                        E2E_FEATURE_YAML_ENV,
                        f"features/{feature_id.lower()}/spec.yaml",
                    )
                    repo = os.environ.get(E2E_REPO_ENV, "appmilla/jarvis")

                    _log_event(
                        "queue_build_invoking",
                        feature_id=feature_id,
                        feature_yaml_path=feature_yaml_path,
                        repo=repo,
                    )

                    # ``queue_build`` is a ``@tool(parse_docstring=True)``
                    # coroutine — invoke via ``.ainvoke`` so the LangChain
                    # tool input-schema validation runs the same way it
                    # would when the supervisor calls it.
                    return await queue_build.ainvoke(
                        {
                            "feature_id": feature_id,
                            "feature_yaml_path": feature_yaml_path,
                            "repo": repo,
                            "branch": "main",
                            "originating_adapter": "cli",
                        }
                    )
                finally:
                    state.session_manager._current_session_var.reset(token)

            # 4. Fire queue_build inside the session context.
            ack_json: str = await asyncio.create_task(
                ctx.run(asyncio.ensure_future, _run_in_session_context())
            )
            ack = json.loads(ack_json)
            _log_event("queue_build_returned", ack=ack)

            # 5. AC-003 — head of the round-trip: ack must be a successful
            # QueueBuildAck (status="queued") with a correlation_id, and
            # the subscriber's correlation map must have registered it.
            assert ack.get("status") == "queued", (
                "Round-trip head failed: queue_build did not return "
                f"status='queued' — got {ack!r}. Likely cause: NATS "
                "publish failed or validation rejected the args."
            )
            correlation_id = ack.get("correlation_id")
            assert isinstance(correlation_id, str) and correlation_id, (
                "Round-trip head failed: queue_build ack missing "
                f"correlation_id — got {ack!r}."
            )

            # ``register_correlation`` is called synchronously after
            # publish-success, so the entry must already be in the map.
            assert correlation_id in state.forge_subscriber._correlations, (
                "Round-trip head failed: correlation_id "
                f"{correlation_id!r} not registered in subscriber "
                "correlation_map. queue_build returned success but the "
                "register_correlation hop dropped the entry — check the "
                "queue_build_register_correlation_failed log line."
            )
            _log_event(
                "correlation_registered",
                correlation_id=correlation_id,
                map_size=len(state.forge_subscriber._correlations),
            )

            # 6. Poll the per-session FIFO until we observe ≥ 3 distinct
            # stage-complete labels OR the 5-minute budget expires.
            stage_deadline = time.monotonic() + STAGE_WAIT_BUDGET_SECONDS
            observed_stage_labels: set[str] = set()
            observed_notifications: list[dict[str, Any]] = []

            while time.monotonic() < stage_deadline:
                # Bail if the overall 10-minute cap is reached even before
                # the per-stage budget. This protects AC-002.
                if time.monotonic() >= deadline:
                    break

                # Drain any queued notifications. ``pending_notifications``
                # is atomic and idempotent — repeated calls return [] until
                # a new notification arrives.
                drained = state.session_manager.pending_notifications(
                    session.session_id
                )
                for notification in drained:
                    # Only count notifications belonging to OUR build.
                    if notification.correlation_id != correlation_id:
                        continue
                    observed_stage_labels.add(notification.stage_label)
                    observed_notifications.append(
                        {
                            "stage_label": notification.stage_label,
                            "status": notification.status,
                            "target_kind": notification.target_kind,
                            "target_identifier": notification.target_identifier,
                            "completed_at": notification.completed_at.isoformat()
                            if isinstance(notification.completed_at, datetime)
                            else str(notification.completed_at),
                        }
                    )
                    _log_event(
                        "stage_notification_received",
                        correlation_id=correlation_id,
                        stage_label=notification.stage_label,
                        status=notification.status,
                    )

                if len(observed_stage_labels) >= 3:
                    break

                await asyncio.sleep(POLL_INTERVAL_SECONDS)

            # 7. AC-004 — assert the round-trip TAIL: at least 3 distinct
            # stage labels observed, and at least 3 Graphiti edges queued
            # by the routing-history writer for our correlation_id.
            assert len(observed_stage_labels) >= 3, (
                "Round-trip tail failed (AC-004): expected ≥ 3 distinct "
                "stage-complete labels for correlation_id "
                f"{correlation_id!r} within {STAGE_WAIT_BUDGET_SECONDS}s, "
                f"got {len(observed_stage_labels)}: "
                f"{sorted(observed_stage_labels)}. Likely cause: Forge "
                "did not progress past the queue-consume hop, OR the "
                "subscriber's source_id filter rejected the events. "
                f"Notifications observed: {observed_notifications!r}."
            )

            # The routing-history writer registers correlation_id at
            # seq=0 on ``write_build_queue_dispatch`` and increments seq
            # after each ``append_build_queue_event``. After 3+ stage
            # events the seq must be ≥ 3 (one per event) — the dispatch
            # write itself contributes the seq=0 anchor entry.
            edge_seq_map = (
                state.routing_history_writer._correlation_edge_seq
            )
            assert correlation_id in edge_seq_map, (
                "Round-trip tail failed: correlation_id "
                f"{correlation_id!r} not present in routing-history "
                "writer's edge-seq map. The build_queue_dispatch trace "
                "submission failed — check the "
                "routing_history_write_failed WARN log line for the "
                "underlying Graphiti exception."
            )
            edge_count = edge_seq_map[correlation_id]
            assert edge_count >= 3, (
                "Round-trip tail failed (AC-004): expected ≥ 3 stage-"
                "complete Graphiti edges appended under correlation_id "
                f"{correlation_id!r}, got {edge_count}. The subscriber "
                "received the events (transcript above) but the "
                "append_build_queue_event hop did not enqueue them — "
                "check the routing_history_append_failed WARN log line."
            )
            _log_event(
                "graphiti_edges_appended",
                correlation_id=correlation_id,
                edge_seq=edge_count,
            )

            # Best-effort: drain any in-flight Graphiti submission tasks
            # so the trace dump reflects the final edge count rather than
            # the not-yet-flushed state.
            await state.routing_history_writer.flush(timeout=5.0)

            # 8. AC-006 — write the evidence attachment.
            trace_dump = {
                "correlation_edge_seq": dict(
                    state.routing_history_writer._correlation_edge_seq
                ),
                "correlation_map_keys": list(
                    state.forge_subscriber._correlations.keys()
                ),
                "observed_stage_labels": sorted(observed_stage_labels),
                "observed_notifications": observed_notifications,
            }
            artefact_path = _write_evidence_attachment(
                tmp_path,
                correlation_id,
                transcript,
                trace_dump,
            )
            _log_event(
                "evidence_attachment_written",
                path=str(artefact_path),
                size_bytes=artefact_path.stat().st_size,
            )

            # Print the path so pytest's captured output shows the operator
            # exactly where to find the artefact (AC-006).
            print(  # noqa: T201 — intentional evidence surface
                f"\n[TASK-J005-012] Phase 3 evidence written to: "
                f"{artefact_path}\n"
                f"  correlation_id: {correlation_id}\n"
                f"  stage_labels:   {sorted(observed_stage_labels)}\n"
                f"  graphiti_edges: {edge_count}\n"
            )
        finally:
            # 9. Clean shutdown — runs even when an assertion above
            # failed so a flaky run doesn't leave NATS subscriptions or
            # background tasks dangling. ``shutdown`` is idempotent and
            # each step is independently failure-tolerant per the
            # lifecycle contract.
            try:
                await shutdown(state)
                _log_event("shutdown_complete")
            except Exception as exc:  # pragma: no cover — best-effort drain
                _logger.warning(
                    "e2e_shutdown_warning",
                    extra={
                        "error_class": type(exc).__name__,
                        "detail": str(exc),
                    },
                )
