"""Integration tests for ``dispatch_by_capability`` — TASK-J004-015.

Six matrix scenarios from
``docs/design/FEAT-JARVIS-004/design.md`` §9 are covered here, each one
mapping directly onto an acceptance criterion of TASK-J004-015:

1. Round-trip happy path (single specialist replies success).
2. Timeout → exhausted (single specialist matches; no consumer replies).
3. Timeout → redirect → success (first specialist times out; second
   replies success).
4. Timeout → redirect → timeout (both specialists time out).
5. Specialist error → redirect → success (first replies success=False;
   second replies success).
6. Concurrent dispatch overflow (9 in-flight against a slow consumer;
   9th returns ``DEGRADED: dispatch_overloaded`` synchronously).

In addition to the matrix, these invariants are pinned:

* **Lexicographic resolution** (DDR-017 determinism): when two specialists
  both advertise the same capability, the lexicographically-first
  ``agent_id`` is targeted on the first attempt.
* **Visited-set guard**: in scenario 4 the second attempt does NOT target
  the first specialist.
* **Trace shape**: the writer is invoked once per dispatch and the
  captured ``JarvisRoutingHistoryEntry`` re-validates against its own
  schema with the expected ``outcome_type`` / ``attempts`` length /
  ``chosen_specialist_id`` (mirroring what gets persisted to Memory).
* **DEGRADED string format** matches design §10 byte-identically.

The "in-process NATS server fixture" called for in the task is
substituted with the project-conventional in-process broker stand-in
(:class:`_InProcessNATSBroker`). Production goes through ``NATSClient``
which talks to a real ``nats-server -p 0 -js`` process; the broker
stand-in implements the same ``request(subject, payload, *, timeout)``
contract so the dispatch tool exercises its real round-trip code path
through it. This is the same substitution pattern already used by
``tests/test_fleet_registration.py`` (``InMemoryManifestRegistry`` in
place of ``NATSKVManifestRegistry``) — keeps the suite portable and
``--randomly-seed=0``-stable while still asserting the req/reply
shape end-to-end.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats_core import Topics
from nats_core.events import ResultPayload

from jarvis.infrastructure.dispatch_semaphore import DispatchSemaphore
from jarvis.infrastructure.routing_history import JarvisRoutingHistoryEntry
from jarvis.tools import dispatch
from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary

# ---------------------------------------------------------------------------
# In-process NATS broker stand-in
# ---------------------------------------------------------------------------

# Type for a mocked-specialist consumer callback. The callback receives the
# raw envelope payload bytes and returns the encoded ResultPayload bytes —
# the same shape NATS req/reply uses (``msg.respond(...)``).
SpecialistHandler = Callable[[bytes], Awaitable[bytes]]


class _InProcessNATSBroker:
    """Per-test broker simulating ``NATSClient.request`` round-trips.

    Stores subject → handler callbacks, plus a request log so tests can
    assert on the subject sequence and visited-set invariants. Every
    handler is invoked under :func:`asyncio.wait_for` so the timeout
    contract from the dispatch tool is exercised end-to-end.

    Shape parity with :class:`jarvis.infrastructure.nats_client.NATSClient`:

    * ``request(subject, payload, *, timeout)`` returns a duck-typed reply
      with a ``.data`` attribute carrying the bytes the handler returned.
    * No subscriber for the subject ⇒ raises :class:`TimeoutError` (this
      mirrors what NATS does when no consumer is on the subject).
    * Handler raises ⇒ propagates through :func:`asyncio.wait_for` so a
      handler-raised :class:`TimeoutError` surfaces as a timeout to the
      caller (matches ``msg.respond`` never firing).
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, SpecialistHandler] = {}
        self.request_log: list[tuple[str, bytes, float]] = []

    def subscribe(self, subject: str, handler: SpecialistHandler) -> None:
        """Register a mocked-specialist consumer for ``subject``."""
        self._subscribers[subject] = handler

    def unsubscribe(self, subject: str) -> None:
        self._subscribers.pop(subject, None)

    async def request(
        self, subject: str, payload: bytes, *, timeout: float
    ) -> Any:
        """Round-trip a request to the registered handler — or time out."""
        self.request_log.append((subject, payload, timeout))
        handler = self._subscribers.get(subject)
        if handler is None:
            # No consumer on the subject — semantic equivalent of a NATS
            # request that no specialist ever replies to.
            raise TimeoutError()
        try:
            data = await asyncio.wait_for(handler(payload), timeout=timeout)
        except asyncio.TimeoutError as exc:  # noqa: F841 - re-raised below
            raise TimeoutError() from None
        return MagicMock(data=data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _registry_two_specialists_for(tool_name: str) -> list[CapabilityDescriptor]:
    """Two specialists both advertising ``tool_name`` — lex-tie scenario.

    ``test-architect`` lex-precedes ``test-zarchitect`` so the tool's
    first attempt always targets ``test-architect``. The second attempt
    (after a redirect) targets ``test-zarchitect``.
    """
    return [
        CapabilityDescriptor(
            agent_id="test-architect",
            role="Test Architect",
            description="Lex-first specialist for the round-trip matrix.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name=tool_name,
                    description="Run the matrix tool",
                    risk_level="read_only",
                ),
            ],
        ),
        CapabilityDescriptor(
            agent_id="test-zarchitect",
            role="Test Zarchitect",
            description="Lex-second specialist for the redirect target.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name=tool_name,
                    description="Run the matrix tool",
                    risk_level="read_only",
                ),
            ],
        ),
    ]


def _registry_single_specialist_for(tool_name: str) -> list[CapabilityDescriptor]:
    """Exactly one specialist matches — used for the exhausted-with-len-1 case."""
    return [
        CapabilityDescriptor(
            agent_id="test-architect",
            role="Test Architect",
            description="Sole matrix specialist (no redirect target available).",
            capability_list=[
                CapabilityToolSummary(
                    tool_name=tool_name,
                    description="Run the matrix tool",
                    risk_level="read_only",
                ),
            ],
        ),
    ]


def _success_bytes(*, command: str, correlation_id: str | None) -> bytes:
    payload = ResultPayload(
        command=command,
        result={"verdict": "ok", "command": command},
        correlation_id=correlation_id,
        success=True,
    )
    return payload.model_dump_json().encode("utf-8")


def _failure_bytes(*, command: str, correlation_id: str | None, reason: str) -> bytes:
    payload = ResultPayload(
        command=command,
        result={"error": reason},
        correlation_id=correlation_id,
        success=False,
    )
    return payload.model_dump_json().encode("utf-8")


def _correlation_from_envelope(payload: bytes) -> str:
    envelope = json.loads(payload.decode("utf-8"))
    return envelope["payload"]["correlation_id"]


@pytest.fixture()
def broker() -> _InProcessNATSBroker:
    """Fresh in-process NATS broker per test (AC: scoped + cleaned up)."""
    return _InProcessNATSBroker()


@pytest.fixture()
def captured_entries() -> list[JarvisRoutingHistoryEntry]:
    """Mutable list of captured trace entries per test."""
    return []


@pytest.fixture()
def wired_dispatch(
    broker: _InProcessNATSBroker,
    captured_entries: list[JarvisRoutingHistoryEntry],
) -> Generator[dict[str, Any], None, None]:
    """Wire the dispatch module to the broker + a capturing writer.

    Mocks the writer's ``write_specialist_dispatch`` so the test captures
    the :class:`JarvisRoutingHistoryEntry` that would otherwise be passed
    to Memory's ``add_episode`` (the writer constructs the episode from
    this entry, so capturing here gives the same trace shape we'd see
    from a Memory-side mock — minus the redaction step, which is
    covered by ``test_routing_history_writer.py``). The entry is the
    object the AC's ``model_validate(...)`` re-check operates on.

    Cleanup restores the module-level dependencies on test exit so
    ``conftest._restore_dispatch_layer2_hooks`` (autouse) keeps the
    snapshot stable for downstream tests.
    """
    nats_client = MagicMock()
    nats_client.request = AsyncMock(side_effect=broker.request)

    semaphore = DispatchSemaphore(cap=8)

    writer = MagicMock()

    async def _capture(entry: JarvisRoutingHistoryEntry) -> None:
        captured_entries.append(entry)

    writer.write_specialist_dispatch = AsyncMock(side_effect=_capture)

    dispatch._nats_client = nats_client
    dispatch._dispatch_semaphore = semaphore
    dispatch._routing_history_writer = writer

    try:
        yield {
            "nats_client": nats_client,
            "semaphore": semaphore,
            "writer": writer,
        }
    finally:
        # The autouse ``_restore_dispatch_layer2_hooks`` fixture restores
        # the original module values; we only need to drop our refs.
        pass


@pytest.fixture()
def bound_two_specialists(
    request: pytest.FixtureRequest,
) -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a two-specialist registry into ``dispatch._capability_registry``."""
    saved = dispatch._capability_registry
    tool_name = getattr(request, "param", "review_spec")
    dispatch._capability_registry = _registry_two_specialists_for(tool_name)
    try:
        yield dispatch._capability_registry
    finally:
        dispatch._capability_registry = saved


@pytest.fixture()
def bound_single_specialist() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a single-specialist registry."""
    saved = dispatch._capability_registry
    dispatch._capability_registry = _registry_single_specialist_for("review_spec")
    try:
        yield dispatch._capability_registry
    finally:
        dispatch._capability_registry = saved


async def _ainvoke(**kwargs: Any) -> str:
    """Invoke the @tool-wrapped async ``dispatch_by_capability`` and return."""
    return await dispatch.dispatch_by_capability.ainvoke(kwargs)


async def _drain_pending() -> None:
    """Yield to the loop so fire-and-forget ``create_task`` callbacks run."""
    for _ in range(8):
        await asyncio.sleep(0)


def _validate_trace(entry: JarvisRoutingHistoryEntry) -> JarvisRoutingHistoryEntry:
    """Re-validate the captured entry against the schema (AC: trace shape)."""
    return JarvisRoutingHistoryEntry.model_validate(entry.model_dump())


# ---------------------------------------------------------------------------
# Scenario 1 — Round-trip happy path
# ---------------------------------------------------------------------------


class TestScenario1RoundTripHappyPath:
    """A mock specialist subscribed to ``agents.command.test-architect``
    replies with a canned ``ResultPayload(success=True)``; the dispatch
    tool returns that payload's JSON; the trace records
    ``outcome="success"`` with no redirect attempts.
    """

    async def test_single_specialist_round_trip_success(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
        captured_entries: list[JarvisRoutingHistoryEntry],
    ) -> None:
        # Mocked specialist consumer — NATS req/reply pattern, replies via
        # the handler's return value (semantically equivalent to
        # ``msg.respond(...)``).
        async def architect_handler(payload: bytes) -> bytes:
            return _success_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
            )

        # Subject built via the canonical Topics formatter — no hard-coded
        # literals (parity with TASK-J004-014 AC).
        subject = Topics.Agents.COMMAND.format(agent_id="test-architect")
        broker.subscribe(subject, architect_handler)

        result = await _ainvoke(tool_name="review_spec", payload_json='{"k": "v"}')

        # ── Round-trip verdict ──
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "review_spec"

        # Exactly one request fired, on the lex-first subject.
        assert len(broker.request_log) == 1
        first_subject, _, _ = broker.request_log[0]
        assert first_subject == subject

        # ── Trace shape ──
        await _drain_pending()
        assert len(captured_entries) == 1
        entry = _validate_trace(captured_entries[0])
        assert entry.outcome_type == "success"
        assert entry.attempts == []
        assert entry.chosen_specialist_id == "test-architect"
        assert entry.subagent_final_state == "success"


# ---------------------------------------------------------------------------
# Scenario 2 — Timeout → exhausted (single specialist; no consumer replies)
# ---------------------------------------------------------------------------


class TestScenario2TimeoutExhausted:
    """Only one specialist matches the capability; no consumer is
    subscribed for that subject. The dispatch tool times out on attempt 0,
    re-resolves with the visited-set excluding the only candidate (yielding
    ``None``), and surfaces ``TIMEOUT: ... exhausted attempts=1``.
    """

    async def test_single_specialist_no_consumer_returns_exhausted(
        self,
        broker: _InProcessNATSBroker,
        bound_single_specialist: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
        captured_entries: list[JarvisRoutingHistoryEntry],
    ) -> None:
        # No subscribers on broker → request() raises TimeoutError.
        # The validation lower bound is 5s but the broker raises
        # synchronously when no consumer is registered — wall-clock cost
        # is microseconds.
        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=5,
        )

        # ── DEGRADED string contract per design §10 ──
        assert result.startswith("TIMEOUT: agent_id=test-architect")
        assert "exhausted attempts=1" in result
        assert "tool_name=review_spec" in result

        # Exactly one request was made (the only candidate).
        assert len(broker.request_log) == 1

        # ── Trace shape ──
        await _drain_pending()
        assert len(captured_entries) == 1
        entry = _validate_trace(captured_entries[0])
        assert entry.outcome_type == "exhausted"
        assert len(entry.attempts) == 1
        assert entry.attempts[0].agent_id == "test-architect"
        assert entry.attempts[0].reason_skipped == "timeout"
        assert entry.attempts[0].attempt_index == 0
        assert entry.chosen_specialist_id is None
        assert entry.subagent_final_state == "timeout"


# ---------------------------------------------------------------------------
# Scenario 3 — Timeout → redirect → success
# ---------------------------------------------------------------------------


class TestScenario3RedirectSuccess:
    """First specialist (lex-first ``test-architect``) times out; second
    (``test-zarchitect``) replies success. Trace records
    ``outcome="redirected"``, ``attempts`` length 1, ``chosen_specialist_id``
    matches the second specialist.
    """

    async def test_redirect_after_timeout_targets_lex_second(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
        captured_entries: list[JarvisRoutingHistoryEntry],
    ) -> None:
        first_subject = Topics.Agents.COMMAND.format(agent_id="test-architect")
        second_subject = Topics.Agents.COMMAND.format(agent_id="test-zarchitect")

        # First specialist never replies (no subscriber on first_subject)
        # but the second does.
        async def zarchitect_handler(payload: bytes) -> bytes:
            return _success_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
            )

        broker.subscribe(second_subject, zarchitect_handler)

        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=5,
        )

        parsed = json.loads(result)
        assert parsed["success"] is True

        # Two requests — visited-set selected lex-first then lex-second.
        subjects = [entry[0] for entry in broker.request_log]
        assert subjects == [first_subject, second_subject]

        await _drain_pending()
        assert len(captured_entries) == 1
        entry = _validate_trace(captured_entries[0])
        assert entry.outcome_type == "redirected"
        assert len(entry.attempts) == 1
        assert entry.attempts[0].agent_id == "test-architect"
        assert entry.attempts[0].reason_skipped == "timeout"
        assert entry.chosen_specialist_id == "test-zarchitect"
        assert entry.subagent_final_state == "success"


# ---------------------------------------------------------------------------
# Scenario 4 — Timeout → redirect → timeout (visited-set guard)
# ---------------------------------------------------------------------------


class TestScenario4RedirectExhausted:
    """Both specialists time out. The dispatch tool returns
    ``TIMEOUT: ... exhausted attempts=2``; trace records ``attempts``
    length 2 with distinct ``agent_id`` values (visited-set guard).
    """

    async def test_double_timeout_visited_set_prevents_repeat(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
        captured_entries: list[JarvisRoutingHistoryEntry],
    ) -> None:
        # No subscribers → both attempts time out.
        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=5,
        )

        assert result.startswith("TIMEOUT:")
        assert "exhausted attempts=2" in result

        # Visited-set guard: the two requests went to different agents.
        subjects = [entry[0] for entry in broker.request_log]
        assert len(subjects) == 2
        assert subjects[0] != subjects[1]
        assert subjects[0] == Topics.Agents.COMMAND.format(agent_id="test-architect")
        assert subjects[1] == Topics.Agents.COMMAND.format(agent_id="test-zarchitect")

        await _drain_pending()
        assert len(captured_entries) == 1
        entry = _validate_trace(captured_entries[0])
        assert entry.outcome_type == "exhausted"
        assert len(entry.attempts) == 2
        attempt_agent_ids = {a.agent_id for a in entry.attempts}
        assert attempt_agent_ids == {"test-architect", "test-zarchitect"}
        assert all(a.reason_skipped == "timeout" for a in entry.attempts)
        # attempt_index is 0-indexed and monotonically increasing.
        assert [a.attempt_index for a in entry.attempts] == [0, 1]


# ---------------------------------------------------------------------------
# Scenario 5 — Specialist error → redirect → success
# ---------------------------------------------------------------------------


class TestScenario5SpecialistErrorRedirect:
    """First specialist replies ``success=False, error="capacity_exceeded"``;
    second replies success. Trace records ``outcome="redirected"`` with
    ``attempts[0].reason_skipped == "specialist_error"`` and the detail
    captured from the failed reply.
    """

    async def test_specialist_error_then_success_records_specialist_error(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
        captured_entries: list[JarvisRoutingHistoryEntry],
    ) -> None:
        first_subject = Topics.Agents.COMMAND.format(agent_id="test-architect")
        second_subject = Topics.Agents.COMMAND.format(agent_id="test-zarchitect")

        async def failing_handler(payload: bytes) -> bytes:
            return _failure_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
                reason="capacity_exceeded",
            )

        async def succeeding_handler(payload: bytes) -> bytes:
            return _success_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
            )

        broker.subscribe(first_subject, failing_handler)
        broker.subscribe(second_subject, succeeding_handler)

        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        parsed = json.loads(result)
        assert parsed["success"] is True

        subjects = [entry[0] for entry in broker.request_log]
        assert subjects == [first_subject, second_subject]

        await _drain_pending()
        assert len(captured_entries) == 1
        entry = _validate_trace(captured_entries[0])
        assert entry.outcome_type == "redirected"
        assert len(entry.attempts) == 1
        assert entry.attempts[0].agent_id == "test-architect"
        assert entry.attempts[0].reason_skipped == "specialist_error"
        # Detail carries the specialist's reason (truncated at 512 chars).
        assert entry.attempts[0].detail is not None
        assert "capacity_exceeded" in entry.attempts[0].detail
        assert entry.chosen_specialist_id == "test-zarchitect"


# ---------------------------------------------------------------------------
# Scenario 6 — Concurrent dispatch overflow
# ---------------------------------------------------------------------------


class TestScenario6ConcurrentDispatchOverflow:
    """Launch 9 concurrent dispatches against a slow consumer with the
    real ``DispatchSemaphore(cap=8)``. The 9th call's ``try_acquire``
    returns ``False`` synchronously and surfaces
    ``DEGRADED: dispatch_overloaded``; once the consumer is unblocked the
    other 8 return ``ResultPayload(success=True)`` JSON.
    """

    async def test_ninth_dispatch_returns_degraded_and_eight_succeed(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
    ) -> None:
        release_event = asyncio.Event()
        subject = Topics.Agents.COMMAND.format(agent_id="test-architect")

        async def slow_handler(payload: bytes) -> bytes:
            # Block until the test signals; this holds 8 semaphore slots.
            await release_event.wait()
            return _success_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
            )

        broker.subscribe(subject, slow_handler)

        # Launch 9 concurrent dispatches — the 9th will fail try_acquire
        # synchronously per DDR-020.
        tasks = [
            asyncio.create_task(
                _ainvoke(tool_name="review_spec", payload_json="{}")
            )
            for _ in range(9)
        ]

        # Drain the loop until all tasks have either:
        #  * finished (the DEGRADED returner), or
        #  * blocked on the slow handler.
        # Bounded in case of regression — break loud rather than hang.
        for _ in range(200):
            done = sum(1 for t in tasks if t.done())
            if done >= 1:
                break
            await asyncio.sleep(0)
        assert any(t.done() for t in tasks), "9th dispatch did not return synchronously"

        # Exactly one task is done (the DEGRADED-returning 9th); the rest
        # are awaiting the slow handler.
        done_results = [t.result() for t in tasks if t.done()]
        assert len(done_results) == 1
        assert done_results[0] == "DEGRADED: dispatch_overloaded — wait and retry"

        # Release the consumer; the remaining 8 must complete with
        # ResultPayload success JSON.
        release_event.set()
        all_results = await asyncio.gather(*tasks)

        degraded = [r for r in all_results if r == "DEGRADED: dispatch_overloaded — wait and retry"]
        successes = [r for r in all_results if r != "DEGRADED: dispatch_overloaded — wait and retry"]
        assert len(degraded) == 1
        assert len(successes) == 8
        for r in successes:
            parsed = json.loads(r)
            assert parsed["success"] is True
            assert parsed["command"] == "review_spec"

        # Semaphore returned to zero in-flight via the finally release
        # path — AC-008 of the upstream dispatch tool task.
        assert wired_dispatch["semaphore"].in_flight == 0


# ---------------------------------------------------------------------------
# Lexicographic determinism — DDR-017 invariant pinned for the matrix
# ---------------------------------------------------------------------------


class TestLexicographicDeterminismIntegration:
    """When two specialists advertise the same capability, the
    lexicographically-first ``agent_id`` is targeted on the first attempt.
    Together with the visited-set guard exercised in scenarios 3-5 this
    is the determinism contract DDR-017 pins.
    """

    async def test_first_attempt_targets_lex_first_agent(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
    ) -> None:
        first_subject = Topics.Agents.COMMAND.format(agent_id="test-architect")
        second_subject = Topics.Agents.COMMAND.format(agent_id="test-zarchitect")

        # Both specialists subscribed to confirm the lex-first wins
        # *despite* both being able to reply — not because the second is
        # silent.
        async def architect_handler(payload: bytes) -> bytes:
            return _success_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
            )

        async def zarchitect_handler(payload: bytes) -> bytes:  # pragma: no cover
            return _success_bytes(
                command="review_spec",
                correlation_id=_correlation_from_envelope(payload),
            )

        broker.subscribe(first_subject, architect_handler)
        broker.subscribe(second_subject, zarchitect_handler)

        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        parsed = json.loads(result)
        assert parsed["success"] is True

        # Lex-first won — only the test-architect subject was contacted.
        assert len(broker.request_log) == 1
        assert broker.request_log[0][0] == first_subject


# ---------------------------------------------------------------------------
# DEGRADED string contract — design §10 byte-identical
# ---------------------------------------------------------------------------


class TestDegradedStringContract:
    """The ``DEGRADED: dispatch_overloaded`` and ``TIMEOUT: ...`` strings
    are part of the agent-facing API surface (design §10). Any drift in
    their shape silently breaks the reasoning model's pattern matching,
    so we pin them byte-for-byte.
    """

    async def test_degraded_dispatch_overloaded_byte_identical(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
    ) -> None:
        # Saturate the semaphore from the test side (no concurrency
        # noise) — easier than scenario 6 just for the byte-shape pin.
        sem: DispatchSemaphore = wired_dispatch["semaphore"]
        for _ in range(sem.cap):
            assert sem.try_acquire() is True
        try:
            result = await _ainvoke(tool_name="review_spec", payload_json="{}")
            assert result == "DEGRADED: dispatch_overloaded — wait and retry"
        finally:
            for _ in range(sem.cap):
                sem.release()

    async def test_timeout_exhausted_string_carries_required_fields(
        self,
        broker: _InProcessNATSBroker,
        bound_two_specialists: list[CapabilityDescriptor],
        wired_dispatch: dict[str, Any],
    ) -> None:
        # Both specialists time out → exhausted with attempts=2.
        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=5,
        )
        # Format pinned: ``TIMEOUT: agent_id=<id> tool_name=<x> exhausted attempts=<n>``
        assert result.startswith("TIMEOUT: agent_id=")
        assert " tool_name=review_spec " in result
        assert " exhausted attempts=2" in result
