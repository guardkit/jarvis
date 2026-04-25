"""Behavioural tests for ``dispatch_by_capability`` (TASK-J002-013).

Each test class maps to one acceptance criterion in
``tasks/design_approved/TASK-J002-013-implement-dispatch-by-capability-tool.md``.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Generator

import pytest
from nats_core.events import CommandPayload, ResultPayload

from jarvis.tools import dispatch
from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_registry() -> list[CapabilityDescriptor]:
    """Return a small but realistic capability registry."""
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
            ],
        ),
    ]


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
def reset_hook() -> Generator[None, None, None]:
    """Ensure ``_stub_response_hook`` is restored after each test."""
    saved = dispatch._stub_response_hook
    try:
        yield
    finally:
        dispatch._stub_response_hook = saved


def _invoke(**kwargs: object) -> str:
    """Invoke the @tool-wrapped dispatch_by_capability via the BaseTool API."""
    return dispatch.dispatch_by_capability.invoke(kwargs)


# ---------------------------------------------------------------------------
# AC-001 — Module-level @tool exposed with the documented signature
# ---------------------------------------------------------------------------
class TestAC001ToolExposure:
    def test_dispatch_by_capability_is_module_attribute(self) -> None:
        assert hasattr(dispatch, "dispatch_by_capability")

    def test_dispatch_by_capability_is_a_basetool(self) -> None:
        from langchain_core.tools import BaseTool

        assert isinstance(dispatch.dispatch_by_capability, BaseTool)

    def test_dispatch_by_capability_args_schema_lists_documented_args(
        self,
    ) -> None:
        schema = dispatch.dispatch_by_capability.args_schema.model_json_schema()
        props = schema["properties"]
        assert {"tool_name", "payload_json", "intent_pattern", "timeout_seconds"} <= set(props)


# ---------------------------------------------------------------------------
# AC-002 — Docstring carries documented headings
# ---------------------------------------------------------------------------
class TestAC002Docstring:
    def test_description_contains_resolution_order_heading(self) -> None:
        doc = dispatch.dispatch_by_capability.description or ""
        assert "Resolution order" in doc
        assert "Use this tool when" in doc

    def test_underlying_docstring_lists_error_strings(self) -> None:
        # ``@tool(parse_docstring=True)`` parses the Args/Returns sections out
        # of the description, so we read the raw underlying-function docstring
        # to verify the documented return-shape strings.
        underlying = dispatch.dispatch_by_capability.func
        doc = underlying.__doc__ or ""
        assert "ERROR: unresolved" in doc
        assert "ERROR: invalid_payload" in doc
        assert "ERROR: invalid_timeout" in doc
        assert "TIMEOUT: agent_id" in doc


# ---------------------------------------------------------------------------
# AC-003 — Resolution: exact, then intent fallback, then unresolved
# ---------------------------------------------------------------------------
class TestAC003Resolution:
    def test_exact_match_wins(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            result = _invoke(
                tool_name="review_spec",
                payload_json='{"spec": "x"}',
            )
        # Resolved → success canned ResultPayload JSON.
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["result"] == {"stub": True, "tool_name": "review_spec"}
        # The log line names the resolved agent_id.
        assert any("agent_id=product-owner" in r.message for r in caplog.records)

    def test_lexicographic_order_breaks_exact_match_ties(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Both ``architect`` and ``zeta-agent`` expose ``run_architecture_session``.
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            _invoke(
                tool_name="run_architecture_session",
                payload_json="{}",
            )
        # Lexicographic agent_id order picks ``architect`` (a < z).
        assert any("agent_id=architect" in r.message for r in caplog.records)

    def test_intent_pattern_fallback_when_no_exact_match(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            result = _invoke(
                tool_name="this_tool_does_not_exist",
                payload_json="{}",
                intent_pattern="C4 architecture",
            )
        # The intent_pattern matches ``architect.description``.
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert any("agent_id=architect" in r.message for r in caplog.records)

    def test_unknown_capability_returns_unresolved_error(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        result = _invoke(
            tool_name="nonexistent_tool",
            payload_json="{}",
        )
        assert result == (
            "ERROR: unresolved — no capability matches "
            "tool_name=nonexistent_tool intent_pattern=None"
        )

    def test_unknown_capability_with_unmatched_intent_pattern(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        result = _invoke(
            tool_name="nope",
            payload_json="{}",
            intent_pattern="totally-not-anywhere",
        )
        assert "ERROR: unresolved" in result
        assert "tool_name=nope" in result
        assert "intent_pattern=totally-not-anywhere" in result


# ---------------------------------------------------------------------------
# AC-004 — payload_json must be a JSON object literal
# ---------------------------------------------------------------------------
class TestAC004PayloadValidation:
    @pytest.mark.parametrize(
        "bad",
        [
            "[1, 2, 3]",  # JSON array
            '"a string"',  # JSON string
            "42",  # JSON number
            "null",  # JSON null
            "not json at all",  # not JSON
            "",  # empty
            "  {bad",  # malformed
        ],
    )
    def test_non_object_payload_returns_invalid_payload(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        bad: str,
    ) -> None:
        result = _invoke(
            tool_name="review_spec",
            payload_json=bad,
        )
        assert result == ("ERROR: invalid_payload — payload_json is not a JSON object literal")

    def test_valid_object_payload_round_trips_into_command_args(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        captured: list[CommandPayload] = []

        def hook(cmd: CommandPayload) -> tuple:
            captured.append(cmd)
            return (
                "success",
                ResultPayload(
                    command=cmd.command,
                    result={"echoed": cmd.args},
                    correlation_id=cmd.correlation_id,
                    success=True,
                ),
            )

        dispatch._stub_response_hook = hook
        result = _invoke(
            tool_name="review_spec",
            payload_json='{"spec_id": "FEAT-001", "depth": 2}',
        )
        assert captured, "hook must have received the constructed CommandPayload"
        assert captured[0].args == {"spec_id": "FEAT-001", "depth": 2}
        # Round-trip via the canned ResultPayload.
        parsed = json.loads(result)
        assert parsed["result"] == {"echoed": {"spec_id": "FEAT-001", "depth": 2}}


# ---------------------------------------------------------------------------
# AC-005 — timeout_seconds must be 5..600
# ---------------------------------------------------------------------------
class TestAC005TimeoutValidation:
    @pytest.mark.parametrize("bad", [0, 1, 4, 601, 10_000, -1])
    def test_out_of_range_timeout_returns_invalid_timeout(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        bad: int,
    ) -> None:
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=bad,
        )
        assert result == (f"ERROR: invalid_timeout — timeout_seconds must be 5..600, got {bad}")

    @pytest.mark.parametrize("good", [5, 60, 600])
    def test_in_range_timeout_proceeds(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        good: int,
    ) -> None:
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=good,
        )
        # In-range → resolution proceeds → canned success returned.
        assert "ERROR: invalid_timeout" not in result


# ---------------------------------------------------------------------------
# AC-006 — Real nats-core CommandPayload constructed with new_correlation_id()
# ---------------------------------------------------------------------------
class TestAC006CommandPayloadConstruction:
    def test_stub_hook_sees_a_real_command_payload(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        seen: list[CommandPayload] = []

        def hook(cmd: CommandPayload) -> tuple:
            seen.append(cmd)
            return (
                "success",
                ResultPayload(
                    command=cmd.command,
                    result={},
                    correlation_id=cmd.correlation_id,
                    success=True,
                ),
            )

        dispatch._stub_response_hook = hook
        _invoke(
            tool_name="review_spec",
            payload_json='{"x": 1}',
        )
        assert len(seen) == 1
        cmd = seen[0]
        assert isinstance(cmd, CommandPayload)
        assert cmd.command == "review_spec"
        assert cmd.args == {"x": 1}
        assert cmd.correlation_id is not None
        assert UUID_RE.match(cmd.correlation_id), (
            f"correlation_id {cmd.correlation_id!r} must be a UUID4 string"
        )


# ---------------------------------------------------------------------------
# AC-007 — Log line shape and grep anchor
# ---------------------------------------------------------------------------
class TestAC007LogLineShape:
    def test_emits_exactly_one_log_line_per_invocation(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            _invoke(tool_name="review_spec", payload_json="{}")
        anchored = [r for r in caplog.records if dispatch.LOG_PREFIX_DISPATCH in r.getMessage()]
        assert len(anchored) == 1

    def test_log_line_contains_required_fields(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            _invoke(
                tool_name="review_spec",
                payload_json='{"a": 1}',
            )
        rendered = next(
            r.getMessage() for r in caplog.records if dispatch.LOG_PREFIX_DISPATCH in r.getMessage()
        )
        assert rendered.startswith(dispatch.LOG_PREFIX_DISPATCH)
        assert "tool_name=review_spec" in rendered
        assert "agent_id=product-owner" in rendered
        assert "correlation_id=" in rendered
        assert "topic=agents.command.product-owner" in rendered
        assert "payload_bytes=" in rendered


# ---------------------------------------------------------------------------
# AC-008 — _stub_response_hook variants
# ---------------------------------------------------------------------------
class TestAC008StubResponseHook:
    def test_unset_hook_returns_canned_success(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        dispatch._stub_response_hook = None
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
        )
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "review_spec"
        assert parsed["result"] == {"stub": True, "tool_name": "review_spec"}
        assert UUID_RE.match(parsed["correlation_id"])

    def test_timeout_hook_returns_timeout_error(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        dispatch._stub_response_hook = lambda _cmd: ("timeout",)
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=30,
        )
        assert result == (
            "TIMEOUT: agent_id=product-owner tool_name=review_spec timeout_seconds=30"
        )

    def test_specialist_error_hook_returns_specialist_error(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        dispatch._stub_response_hook = lambda _cmd: ("specialist_error", "boom")
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
        )
        assert result == ("ERROR: specialist_error — agent_id=product-owner detail=boom")

    def test_success_hook_returns_result_payload_json(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        dispatch._stub_response_hook = lambda cmd: (
            "success",
            ResultPayload(
                command=cmd.command,
                result={"verdict": "ok"},
                correlation_id=cmd.correlation_id,
                success=True,
            ),
        )
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
        )
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["result"] == {"verdict": "ok"}


# ---------------------------------------------------------------------------
# AC-009 — Concurrent dispatches: distinct correlation IDs and log lines
# ---------------------------------------------------------------------------
class TestAC009Concurrency:
    def test_concurrent_dispatches_emit_distinct_correlation_ids(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            r = _invoke(tool_name="review_spec", payload_json="{}")
            with lock:
                results.append(r)

        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        anchored = [
            r.getMessage() for r in caplog.records if dispatch.LOG_PREFIX_DISPATCH in r.getMessage()
        ]
        assert len(anchored) == 5
        # Extract correlation_id from each line.
        cids = [re.search(r"correlation_id=([0-9a-f-]+)", line).group(1) for line in anchored]
        assert len(set(cids)) == 5, (
            f"Concurrent calls must yield distinct correlation_ids; got {cids}"
        )
        # Every returned ResultPayload also carries a distinct correlation_id.
        result_cids = [json.loads(r)["correlation_id"] for r in results]
        assert len(set(result_cids)) == 5


# ---------------------------------------------------------------------------
# AC-010 — Never raises; ValidationError → ERROR: validation
# ---------------------------------------------------------------------------
class TestAC010NeverRaises:
    def test_hook_raising_is_caught_as_specialist_error(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        def boom(_cmd: CommandPayload) -> tuple:
            raise RuntimeError("kaboom")

        dispatch._stub_response_hook = boom
        result = _invoke(
            tool_name="review_spec",
            payload_json="{}",
        )
        assert result.startswith("ERROR: specialist_error — agent_id=product-owner")
        assert "kaboom" in result

    def test_invalid_args_type_does_not_raise(
        self,
        bound_registry: list[CapabilityDescriptor],
        reset_hook: None,
    ) -> None:
        # The @tool wrapper coerces, but this verifies bad shape is graceful.
        result = _invoke(
            tool_name="review_spec",
            payload_json="not-json",
        )
        assert "ERROR: invalid_payload" in result


# ---------------------------------------------------------------------------
# AC-011 — Empty registry yields ERROR: unresolved (does not raise)
# ---------------------------------------------------------------------------
class TestAC011EmptyRegistry:
    def test_empty_registry_returns_unresolved(self, reset_hook: None) -> None:
        saved = dispatch._capability_registry
        dispatch._capability_registry = []
        try:
            result = _invoke(
                tool_name="anything",
                payload_json="{}",
            )
            assert "ERROR: unresolved" in result
        finally:
            dispatch._capability_registry = saved
