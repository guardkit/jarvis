"""Behavioural tests for ``dispatch_by_capability`` — TASK-J004-011.

Phase 2's stub-path coverage (``_stub_response_hook`` + ``LOG_PREFIX_DISPATCH``
log anchor) is retired here. The dispatch tool now performs a real NATS
request/reply round-trip per design §8 and writes routing-history traces
fire-and-forget per DDR-019.

Each test class maps to one acceptance criterion in
``tasks/design_approved/TASK-J004-011-dispatch-tool-real-transport-swap.md``.

Validation tests (timeout range, payload shape) survive the swap as
tool-boundary invariants; transport tests use mocked ``NATSClient`` /
``DispatchSemaphore`` / ``RoutingHistoryWriter`` substitutes.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from nats_core.events import ResultPayload

from jarvis.shared.exceptions import NATSConnectionError
from jarvis.tools import dispatch
from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_registry() -> list[CapabilityDescriptor]:
    """Realistic capability registry covering the resolution rules."""
    return [
        CapabilityDescriptor(
            agent_id="architect",
            role="Architect",
            description="Generates C4 architecture diagrams and ADRs.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="run_architecture_session",
                    description="Run an architecture session",
                    risk_level="read_only",
                ),
            ],
        ),
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
        CapabilityDescriptor(
            agent_id="zeta-agent",
            role="Zeta Specialist",
            description="A dummy specialist for tie-breaker tests.",
            capability_list=[
                CapabilityToolSummary(
                    tool_name="run_architecture_session",
                    description="Duplicate handler for tie-break tests",
                    risk_level="read_only",
                ),
                CapabilityToolSummary(
                    tool_name="review_spec",
                    description="Backup reviewer for redirect tests",
                    risk_level="read_only",
                ),
            ],
        ),
    ]


def _success_result(*, command: str, correlation_id: str | None) -> bytes:
    """Encoded ``ResultPayload`` for a happy-path round-trip."""
    payload = ResultPayload(
        command=command,
        result={"verdict": "ok", "command": command},
        correlation_id=correlation_id,
        success=True,
    )
    return payload.model_dump_json().encode("utf-8")


def _failure_result(*, command: str, correlation_id: str | None, reason: str) -> bytes:
    """Encoded ``ResultPayload`` with ``success=False`` and a structured reason."""
    payload = ResultPayload(
        command=command,
        result={"error": reason},
        correlation_id=correlation_id,
        success=False,
    )
    return payload.model_dump_json().encode("utf-8")


@pytest.fixture()
def bound_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a fresh registry into the dispatch module for the test scope."""
    saved = dispatch._capability_registry
    dispatch._capability_registry = _make_registry()
    try:
        yield dispatch._capability_registry
    finally:
        dispatch._capability_registry = saved


@pytest.fixture()
def mock_dispatch_deps() -> Generator[dict[str, Any], None, None]:
    """Wire mock ``NATSClient`` + ``DispatchSemaphore`` + ``RoutingHistoryWriter``.

    The fixture sets ``_nats_client.request`` to an :class:`AsyncMock` that
    by default returns a ``ResultPayload(success=True)`` reply, an
    :class:`unittest.mock.MagicMock` semaphore whose ``try_acquire`` returns
    ``True`` (with ``release`` recorded for AC-008), and a writer whose
    ``write_specialist_dispatch`` is an :class:`AsyncMock` so the dispatch
    body's ``asyncio.create_task(...)`` schedule succeeds in the test loop.
    """
    saved = (
        dispatch._nats_client,
        dispatch._dispatch_semaphore,
        dispatch._routing_history_writer,
    )

    nats_client = MagicMock()
    nats_client.request = AsyncMock()

    semaphore = MagicMock()
    semaphore.try_acquire = MagicMock(return_value=True)
    semaphore.release = MagicMock()
    semaphore.in_flight = 0

    writer = MagicMock()
    writer.write_specialist_dispatch = AsyncMock(return_value=None)

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
        (
            dispatch._nats_client,
            dispatch._dispatch_semaphore,
            dispatch._routing_history_writer,
        ) = saved


async def _ainvoke(**kwargs: Any) -> str:
    """Invoke the @tool-wrapped async ``dispatch_by_capability`` and return."""
    return await dispatch.dispatch_by_capability.ainvoke(kwargs)


async def _drain_pending() -> None:
    """Yield to the loop so fire-and-forget ``create_task`` callbacks run.

    ``dispatch_by_capability`` schedules the trace write via
    ``asyncio.create_task`` and never awaits it — the test suite needs to
    let those tasks run so writer-call assertions become observable.
    """
    await asyncio.sleep(0)
    await asyncio.sleep(0)


# ---------------------------------------------------------------------------
# AC: tool exposure + validation invariants survive the transport swap
# ---------------------------------------------------------------------------


class TestToolExposureAndDocstring:
    """The @tool surface must remain byte-identical for the reasoning model."""

    def test_dispatch_by_capability_is_module_attribute(self) -> None:
        assert hasattr(dispatch, "dispatch_by_capability")

    def test_dispatch_by_capability_is_a_basetool(self) -> None:
        from langchain_core.tools import BaseTool

        assert isinstance(dispatch.dispatch_by_capability, BaseTool)

    def test_args_schema_lists_documented_args(self) -> None:
        schema = dispatch.dispatch_by_capability.args_schema.model_json_schema()
        props = schema["properties"]
        assert {"tool_name", "payload_json", "intent_pattern", "timeout_seconds"} <= set(props)

    def test_docstring_carries_resolution_order_heading(self) -> None:
        doc = dispatch.dispatch_by_capability.description or ""
        assert "Resolution order" in doc
        assert "Use this tool when" in doc

    @staticmethod
    def _underlying_doc() -> str:
        tool = dispatch.dispatch_by_capability
        underlying = tool.func or tool.coroutine
        return (underlying.__doc__ or "") if underlying is not None else ""

    def test_docstring_lists_new_degraded_strings(self) -> None:
        doc = self._underlying_doc()
        # Phase-2 stub mention is gone.
        assert "transport_stub" not in doc
        # New DEGRADED strings per design §10.
        assert "DEGRADED: dispatch_overloaded" in doc
        assert "DEGRADED: transport_unavailable" in doc

    def test_docstring_still_lists_validation_error_strings(self) -> None:
        doc = self._underlying_doc()
        assert "ERROR: unresolved" in doc
        assert "ERROR: invalid_payload" in doc
        assert "ERROR: invalid_timeout" in doc
        assert "TIMEOUT: agent_id" in doc


# ---------------------------------------------------------------------------
# AC: payload + timeout validation (boundary invariants)
# ---------------------------------------------------------------------------


class TestPayloadValidation:
    @pytest.mark.parametrize(
        "bad",
        ["[1, 2, 3]", '"a string"', "42", "null", "not json", "", "  {bad"],
    )
    async def test_non_object_payload_returns_invalid_payload(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
        bad: str,
    ) -> None:
        result = await _ainvoke(tool_name="review_spec", payload_json=bad)
        assert result == ("ERROR: invalid_payload — payload_json is not a JSON object literal")
        # No NATS call made.
        mock_dispatch_deps["nats_client"].request.assert_not_called()


class TestTimeoutValidation:
    @pytest.mark.parametrize("bad", [0, 1, 4, 601, 10_000, -1])
    async def test_out_of_range_timeout_returns_invalid_timeout(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
        bad: int,
    ) -> None:
        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=bad,
        )
        assert result == (f"ERROR: invalid_timeout — timeout_seconds must be 5..600, got {bad}")
        mock_dispatch_deps["nats_client"].request.assert_not_called()

    @pytest.mark.parametrize("good", [5, 60, 600])
    async def test_in_range_timeouts_proceed_to_nats(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
        good: int,
    ) -> None:
        mock_dispatch_deps["nats_client"].request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id="x")
        )
        result = await _ainvoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=good,
        )
        assert "ERROR: invalid_timeout" not in result
        mock_dispatch_deps["nats_client"].request.assert_awaited()


# ---------------------------------------------------------------------------
# AC: transport — NATSClient.request is called with the contract shape
# ---------------------------------------------------------------------------


class TestNATSRequestContract:
    """Seam test from TASK-J004-011 — NATS_CLIENT_API contract from TASK-J004-006."""

    async def test_request_called_with_subject_payload_timeout(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id="abc")
        )

        await _ainvoke(
            tool_name="review_spec",
            payload_json='{"x": 1}',
            timeout_seconds=30,
        )

        nats_client.request.assert_awaited_once()
        args, kwargs = nats_client.request.call_args
        subject = args[0] if args else kwargs.get("subject")
        payload = args[1] if len(args) > 1 else kwargs.get("payload")
        assert isinstance(subject, str), "subject must be str"
        assert isinstance(payload, bytes), "payload must be bytes"
        assert "timeout" in kwargs, "timeout must be keyword-only"
        assert kwargs["timeout"] == 30
        assert subject == "agents.command.product-owner"

    async def test_subject_built_via_topics_helper_not_hardcoded(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="run_architecture_session", correlation_id=None)
        )
        await _ainvoke(
            tool_name="run_architecture_session",
            payload_json="{}",
        )
        subject = nats_client.request.call_args[0][0]
        # Lexicographic resolution → "architect".
        assert subject == "agents.command.architect"

    async def test_envelope_carries_source_id_jarvis(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id=None)
        )
        await _ainvoke(tool_name="review_spec", payload_json="{}")
        payload_bytes = nats_client.request.call_args[0][1]
        envelope = json.loads(payload_bytes.decode("utf-8"))
        assert envelope["source_id"] == "jarvis"
        assert envelope["event_type"] == "command"
        # Inner CommandPayload carries the same correlation_id as the envelope.
        assert envelope["correlation_id"] == envelope["payload"]["correlation_id"]


# ---------------------------------------------------------------------------
# AC: happy path round-trip
# ---------------------------------------------------------------------------


class TestHappyPathRoundTrip:
    async def test_success_returns_result_payload_json(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        # Use the correlation_id the dispatch tool actually emitted so the
        # specialist's reply round-trips cleanly.
        captured: dict[str, str] = {}

        async def _record_request(subject: str, payload: bytes, *, timeout: float) -> Any:
            envelope = json.loads(payload.decode("utf-8"))
            cid = envelope["payload"]["correlation_id"]
            captured["correlation_id"] = cid
            return MagicMock(data=_success_result(command="review_spec", correlation_id=cid))

        nats_client.request.side_effect = _record_request
        result = await _ainvoke(tool_name="review_spec", payload_json='{"k": "v"}')
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "review_spec"
        assert parsed["correlation_id"] == captured["correlation_id"]
        assert UUID_RE.match(parsed["correlation_id"]), parsed["correlation_id"]


# ---------------------------------------------------------------------------
# AC: retry-with-redirect (visited set + MAX_REDIRECTS=1)
# ---------------------------------------------------------------------------


class TestRetryWithRedirect:
    async def test_timeout_redirect_to_alternate_specialist_succeeds(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        # First call (product-owner) times out; second call (zeta-agent)
        # — the next-lexicographic match for ``review_spec`` — succeeds.
        call_count = {"n": 0}

        async def _flaky(subject: str, payload: bytes, *, timeout: float) -> Any:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise TimeoutError()
            envelope = json.loads(payload.decode("utf-8"))
            return MagicMock(
                data=_success_result(
                    command="review_spec",
                    correlation_id=envelope["payload"]["correlation_id"],
                )
            )

        nats_client.request.side_effect = _flaky
        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        parsed = json.loads(result)
        assert parsed["success"] is True
        # Two attempts: first product-owner, then zeta-agent.
        assert call_count["n"] == 2
        first_subject = nats_client.request.call_args_list[0][0][0]
        second_subject = nats_client.request.call_args_list[1][0][0]
        assert first_subject == "agents.command.product-owner"
        assert second_subject == "agents.command.zeta-agent"

    async def test_double_timeout_returns_exhausted(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.side_effect = TimeoutError()
        result = await _ainvoke(tool_name="review_spec", payload_json="{}", timeout_seconds=10)
        assert result.startswith("TIMEOUT:")
        assert "exhausted attempts=2" in result
        # Visited-set prevented loops: distinct agents per attempt.
        first_subject = nats_client.request.call_args_list[0][0][0]
        second_subject = nats_client.request.call_args_list[1][0][0]
        assert first_subject != second_subject

    async def test_specialist_error_redirect_to_alternate_succeeds(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        call_count = {"n": 0}

        async def _flaky(subject: str, payload: bytes, *, timeout: float) -> Any:
            call_count["n"] += 1
            envelope = json.loads(payload.decode("utf-8"))
            cid = envelope["payload"]["correlation_id"]
            if call_count["n"] == 1:
                return MagicMock(
                    data=_failure_result(
                        command="review_spec",
                        correlation_id=cid,
                        reason="capacity_exceeded",
                    )
                )
            return MagicMock(data=_success_result(command="review_spec", correlation_id=cid))

        nats_client.request.side_effect = _flaky
        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert call_count["n"] == 2

    async def test_max_redirects_is_one(self) -> None:
        """DDR-017 invariant: at most 2 attempts per dispatch."""
        assert dispatch.MAX_REDIRECTS == 1


# ---------------------------------------------------------------------------
# AC: semaphore overflow → DEGRADED synchronously
# ---------------------------------------------------------------------------


class TestSemaphoreOverflow:
    async def test_overflow_returns_dispatch_overloaded(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        mock_dispatch_deps["semaphore"].try_acquire = MagicMock(return_value=False)
        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        assert result == "DEGRADED: dispatch_overloaded — wait and retry"
        # No NATS call made — DEGRADED is synchronous per DDR-020.
        mock_dispatch_deps["nats_client"].request.assert_not_called()
        # Release was NOT called — try_acquire returned False so the slot
        # was never held.
        mock_dispatch_deps["semaphore"].release.assert_not_called()

    async def test_release_called_in_every_outcome_path(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        # Success path
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id="z")
        )
        await _ainvoke(tool_name="review_spec", payload_json="{}")
        assert mock_dispatch_deps["semaphore"].release.call_count == 1

        # Reset and exercise transport-unavailable.
        mock_dispatch_deps["semaphore"].release.reset_mock()
        nats_client.request.side_effect = NATSConnectionError("boom")
        nats_client.request.return_value = None
        await _ainvoke(tool_name="review_spec", payload_json="{}")
        assert mock_dispatch_deps["semaphore"].release.call_count == 1

        # Reset and exercise unresolved (no NATS call → no release? Actually
        # the semaphore is acquired before resolution; release must still
        # fire).
        mock_dispatch_deps["semaphore"].release.reset_mock()
        nats_client.request.side_effect = None
        result = await _ainvoke(tool_name="totally_unknown", payload_json="{}")
        assert result.startswith("ERROR: unresolved")
        assert mock_dispatch_deps["semaphore"].release.call_count == 1


# ---------------------------------------------------------------------------
# AC: NATSConnectionError → DEGRADED: transport_unavailable
# ---------------------------------------------------------------------------


class TestTransportUnavailable:
    async def test_nats_connection_error_returns_degraded(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        mock_dispatch_deps["nats_client"].request.side_effect = NATSConnectionError("broker down")
        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        assert result == "DEGRADED: transport_unavailable — NATS connection failed"

    async def test_unwired_nats_client_returns_degraded(
        self,
        bound_registry: list[CapabilityDescriptor],
    ) -> None:
        # No mock_dispatch_deps fixture — _nats_client stays None.
        saved_sem = dispatch._dispatch_semaphore
        dispatch._dispatch_semaphore = None
        try:
            result = await _ainvoke(tool_name="review_spec", payload_json="{}")
            assert result == "DEGRADED: transport_unavailable — NATS connection failed"
        finally:
            dispatch._dispatch_semaphore = saved_sem


# ---------------------------------------------------------------------------
# AC: unresolved with empty registry never raises
# ---------------------------------------------------------------------------


class TestUnresolvedAndEmptyRegistry:
    async def test_unknown_capability_returns_unresolved(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        result = await _ainvoke(tool_name="nonexistent_tool", payload_json="{}")
        assert result == (
            "ERROR: unresolved — no capability matches "
            "tool_name=nonexistent_tool intent_pattern=None"
        )
        mock_dispatch_deps["nats_client"].request.assert_not_called()

    async def test_intent_pattern_fallback_resolves_when_no_exact_match(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="x", correlation_id=None)
        )
        await _ainvoke(
            tool_name="not_a_registered_tool",
            payload_json="{}",
            intent_pattern="C4 architecture",
        )
        # Intent matched architect.description.
        subject = nats_client.request.call_args[0][0]
        assert subject == "agents.command.architect"

    async def test_empty_registry_returns_unresolved(
        self,
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        saved = dispatch._capability_registry
        dispatch._capability_registry = []
        try:
            result = await _ainvoke(tool_name="anything", payload_json="{}")
            assert "ERROR: unresolved" in result
        finally:
            dispatch._capability_registry = saved


# ---------------------------------------------------------------------------
# AC: trace writes are fire-and-forget (asyncio.create_task, never awaited)
# ---------------------------------------------------------------------------


class TestTraceWritesFireAndForget:
    async def test_writer_invoked_via_create_task(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id=None)
        )
        await _ainvoke(tool_name="review_spec", payload_json="{}")
        # Yield to the loop so the scheduled trace task runs.
        await _drain_pending()
        mock_dispatch_deps["writer"].write_specialist_dispatch.assert_called()

    async def test_writer_failure_does_not_propagate(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        # Writer raises — dispatch must still return the specialist's result.
        async def _explode(_entry: Any) -> None:
            raise RuntimeError("memory down")

        mock_dispatch_deps["writer"].write_specialist_dispatch = AsyncMock(side_effect=_explode)
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id=None)
        )
        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        parsed = json.loads(result)
        assert parsed["success"] is True
        # Drain — the create_task wraps the failing coroutine, exception is
        # swallowed by the task itself (we never await it).
        await _drain_pending()

    async def test_unwired_writer_does_not_block_dispatch(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        dispatch._routing_history_writer = None
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="review_spec", correlation_id=None)
        )
        result = await _ainvoke(tool_name="review_spec", payload_json="{}")
        parsed = json.loads(result)
        assert parsed["success"] is True


# ---------------------------------------------------------------------------
# AC: lexicographic determinism (DDR-017 invariant) preserved on ties
# ---------------------------------------------------------------------------


class TestLexicographicDeterminism:
    async def test_lexicographic_first_wins_on_exact_match_ties(
        self,
        bound_registry: list[CapabilityDescriptor],
        mock_dispatch_deps: dict[str, Any],
    ) -> None:
        nats_client = mock_dispatch_deps["nats_client"]
        nats_client.request.return_value = MagicMock(
            data=_success_result(command="run_architecture_session", correlation_id=None)
        )
        await _ainvoke(
            tool_name="run_architecture_session",
            payload_json="{}",
        )
        subject = nats_client.request.call_args[0][0]
        # Both architect and zeta-agent advertise the tool; lex-first wins.
        assert subject == "agents.command.architect"

    def test_resolve_helper_skips_excluded_agent_ids(self) -> None:
        registry = _make_registry()
        # exclude=architect → next lex match is zeta-agent.
        agent_id = dispatch._resolve_agent_id(
            "run_architecture_session",
            None,
            registry,
            exclude={"architect"},
        )
        assert agent_id == "zeta-agent"

    def test_resolve_helper_returns_none_when_all_candidates_excluded(self) -> None:
        registry = _make_registry()
        agent_id = dispatch._resolve_agent_id(
            "run_architecture_session",
            None,
            registry,
            exclude={"architect", "zeta-agent"},
        )
        assert agent_id is None


# ---------------------------------------------------------------------------
# AC: retired anchors are gone (LOG_PREFIX_DISPATCH, _stub_response_hook)
# ---------------------------------------------------------------------------


class TestRetiredAnchors:
    """The Phase 2 swap-point grep anchors are deleted from this module.

    The TASK-J002-021 grep invariant is flipped to assert their absence in
    TASK-J004-020; here we pin the import-time view.
    """

    def test_log_prefix_dispatch_is_deleted(self) -> None:
        assert not hasattr(dispatch, "LOG_PREFIX_DISPATCH")

    def test_stub_response_hook_is_deleted(self) -> None:
        assert not hasattr(dispatch, "_stub_response_hook")

    def test_stub_response_alias_is_deleted(self) -> None:
        assert not hasattr(dispatch, "StubResponse")

    def test_new_module_attributes_exist(self) -> None:
        assert hasattr(dispatch, "_nats_client")
        assert hasattr(dispatch, "_routing_history_writer")
        assert hasattr(dispatch, "_dispatch_semaphore")
