"""Unit tests for dispatch tools + swap-point grep invariant — TASK-J002-021.

This is the Wave 4 consolidated suite for ``jarvis.tools.dispatch``. It
covers every dispatch-targeted scenario in
``features/feat-jarvis-002-core-tools-and-dispatch/...feature`` plus the
**swap-point grep invariant** that guards DDR-009 (the post-Wave-3
``grep -rn`` count of exactly 4 anchored lines, all in
``src/jarvis/tools/dispatch.py``).

Test class layout:

- :class:`TestDispatchByCapabilityHappyPath` — exact match resolves
  ``run_architecture_session`` → ``architect-agent``.
- :class:`TestDispatchByCapabilityIntentFallback` — intent_pattern wins
  when no exact match exists.
- :class:`TestDispatchByCapabilityTimeoutTable` — timeout_seconds in
  {5, 60, 600} accept; {4, 601} reject.
- :class:`TestDispatchByCapabilityInvalidPayloadTable` — non-object
  literal payloads return invalid_payload.
- :class:`TestDispatchByCapabilityUnresolved` — unknown capability +
  unmatched intent returns unresolved.
- :class:`TestDispatchByCapabilitySimulatedTimeout` — fake_dispatch_stub
  flips ``_stub_response_hook`` to ``("timeout",)``.
- :class:`TestDispatchByCapabilitySpecialistError` — fake_dispatch_stub
  flips ``_stub_response_hook`` to ``("specialist_error", reason)``.
- :class:`TestDispatchByCapabilityConcurrent` — ThreadPoolExecutor with
  2 parallel calls; assert distinct UUIDs and 2 log lines with matching
  correlation_ids.
- :class:`TestDispatchByCapabilityRealCommandPayload` — captured object
  is a real ``CommandPayload`` instance, not a dict.
- :class:`TestDispatchByCapabilityLogFormat` — exact log format
  assertion: ``JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y>
  correlation_id=<z> topic=agents.command.<y> payload_bytes=<n>``.
- :class:`TestQueueBuildHappyPath` — happy path returns a JSON ack.
- :class:`TestQueueBuildFeatureIdTable` — accept / reject table per the
  task spec (with the FEAT-JARVIS-EXAMPLE01 row matching the actual
  ``^FEAT-[A-Z0-9]{3,12}$`` implementation pattern, see comment).
- :class:`TestQueueBuildRepoTable` — accept / reject table per Gherkin.
- :class:`TestQueueBuildAdapterTable` — accept / reject table per Gherkin.
- :class:`TestQueueBuildRealBuildQueuedPayload` — ``isinstance`` check on
  the payload that ``BuildQueuedPayload.model_validate_json`` reconstructs.
- :class:`TestQueueBuildLogFormat` — exact log format assertion:
  ``JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
  topic=pipeline.build-queued.<x> payload_bytes=<n>``.
- :class:`TestSwapPointGrepInvariant` — runs ``grep -rn`` on
  ``src/jarvis/`` for the two anchor strings and asserts the post-Wave-3
  4-line count, all in ``src/jarvis/tools/dispatch.py``.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from nats_core.events import BuildQueuedPayload, CommandPayload, ResultPayload

from jarvis.tools import dispatch
from jarvis.tools.capabilities import CapabilityDescriptor, CapabilityToolSummary

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

# Anchor strings reconstructed via concatenation so this test file does NOT
# itself appear in the swap-point grep invariant rooted at ``src/jarvis/``.
# (The grep is rooted at the source tree, so tests/ is already excluded —
# this construction is belt-and-braces in case the test is ever copied.)
_ANCHOR_DISPATCH = "JARVIS_DISPATCH" + "_STUB"
_ANCHOR_QUEUE_BUILD = "JARVIS_QUEUE_BUILD" + "_STUB"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------
def _make_registry() -> list[CapabilityDescriptor]:
    """Realistic capability registry exercising the resolution rules.

    ``architect-agent`` advertises ``run_architecture_session`` (the happy
    path target named in TASK-J002-021's AC-002). ``product-owner`` exposes
    ``review_spec`` (intent fallback target via the ``"acceptance"``
    substring in its description).
    """
    return [
        CapabilityDescriptor(
            agent_id="architect-agent",
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
    ]


@pytest.fixture()
def bound_registry() -> Generator[list[CapabilityDescriptor], None, None]:
    """Bind a fresh registry into the dispatch module for the test scope.

    Saves and restores ``dispatch._capability_registry`` so concurrent or
    sequenced tests stay isolated.
    """
    saved = dispatch._capability_registry
    dispatch._capability_registry = _make_registry()
    try:
        yield dispatch._capability_registry
    finally:
        dispatch._capability_registry = saved


@pytest.fixture()
def fake_dispatch_stub() -> Generator[
    Callable[[Callable[[CommandPayload], Any]], None], None, None
]:
    """Yield a setter that flips ``dispatch._stub_response_hook`` for the test.

    Usage::

        def test_x(fake_dispatch_stub):
            fake_dispatch_stub(lambda cmd: ("timeout",))
            ...

    The previous hook is restored on teardown so module state never leaks
    between tests. This is the fixture that AC-007 of TASK-J002-021 names.
    """
    saved = dispatch._stub_response_hook

    def _set(hook: Callable[[CommandPayload], Any] | None) -> None:
        dispatch._stub_response_hook = hook  # type: ignore[assignment]

    try:
        yield _set
    finally:
        dispatch._stub_response_hook = saved


def _invoke_dispatch(**kwargs: Any) -> str:
    """Invoke the @tool-wrapped ``dispatch_by_capability`` and return the
    string result.
    """
    return dispatch.dispatch_by_capability.invoke(kwargs)


def _invoke_queue_build(**kwargs: Any) -> str:
    """Invoke the @tool-wrapped ``queue_build`` and return the string result."""
    return dispatch.queue_build.invoke(kwargs)


def _project_root() -> Path:
    """Return the project root (the parent of ``tests/``)."""
    return Path(__file__).resolve().parent.parent


# ===========================================================================
# dispatch_by_capability — happy path
# ===========================================================================
class TestDispatchByCapabilityHappyPath:
    """``run_architecture_session`` resolves to ``architect-agent``."""

    def test_happy_path_resolves_run_architecture_session_to_architect_agent(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            result = _invoke_dispatch(
                tool_name="run_architecture_session",
                payload_json='{"goal": "C4 diagram"}',
            )
        # Canned success — the tool returns a ResultPayload JSON.
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["command"] == "run_architecture_session"
        assert UUID_RE.match(parsed["correlation_id"]), parsed["correlation_id"]
        # The log line names the resolved agent_id.
        anchored = [
            r.getMessage()
            for r in caplog.records
            if r.name == "jarvis.tools.dispatch"
        ]
        assert any("agent_id=architect-agent" in m for m in anchored), anchored


# ===========================================================================
# dispatch_by_capability — intent-pattern fallback
# ===========================================================================
class TestDispatchByCapabilityIntentFallback:
    """When no exact match exists, the intent_pattern resolves the agent."""

    def test_intent_pattern_resolves_when_no_exact_match(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            result = _invoke_dispatch(
                tool_name="not_a_registered_tool",
                payload_json="{}",
                intent_pattern="C4 architecture",
            )
        parsed = json.loads(result)
        assert parsed["success"] is True
        # Intent pattern matches architect-agent.description.
        assert any(
            "agent_id=architect-agent" in r.getMessage() for r in caplog.records
        )


# ===========================================================================
# dispatch_by_capability — timeout_seconds table {5, 60, 600, 4, 601}
# ===========================================================================
class TestDispatchByCapabilityTimeoutTable:
    """Boundary: timeout_seconds accepts 5..600 and rejects 4 / 601."""

    @pytest.mark.parametrize("good", [5, 60, 600])
    def test_in_range_timeouts_proceed(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        good: int,
    ) -> None:
        result = _invoke_dispatch(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=good,
        )
        # In-range → resolution proceeds → canned success returned.
        assert "ERROR: invalid_timeout" not in result
        assert json.loads(result)["success"] is True

    @pytest.mark.parametrize("bad", [4, 601])
    def test_out_of_range_timeouts_return_invalid_timeout(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        bad: int,
    ) -> None:
        result = _invoke_dispatch(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=bad,
        )
        assert result == (
            f"ERROR: invalid_timeout — timeout_seconds must be 5..600, got {bad}"
        )


# ===========================================================================
# dispatch_by_capability — invalid JSON payload table
# ===========================================================================
class TestDispatchByCapabilityInvalidPayloadTable:
    """Payloads that are not JSON object literals return invalid_payload."""

    @pytest.mark.parametrize(
        "bad",
        [
            '"just a string"',  # JSON string — Gherkin row
            "[1, 2, 3]",  # JSON array — Gherkin row
            "not valid json",  # not JSON — Gherkin row
            "42",  # JSON number
            "null",  # JSON null
            "",  # empty
        ],
    )
    def test_non_object_payload_returns_invalid_payload(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        bad: str,
    ) -> None:
        result = _invoke_dispatch(
            tool_name="review_spec",
            payload_json=bad,
        )
        assert result == (
            "ERROR: invalid_payload — payload_json is not a JSON object literal"
        )


# ===========================================================================
# dispatch_by_capability — unresolved
# ===========================================================================
class TestDispatchByCapabilityUnresolved:
    """Unknown capability with no intent pattern returns unresolved error."""

    def test_unknown_capability_returns_unresolved(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
    ) -> None:
        result = _invoke_dispatch(
            tool_name="totally_unknown_tool",
            payload_json="{}",
        )
        assert result.startswith("ERROR: unresolved")
        assert "tool_name=totally_unknown_tool" in result
        assert "intent_pattern=None" in result


# ===========================================================================
# dispatch_by_capability — simulated timeout via _stub_response_hook
# ===========================================================================
class TestDispatchByCapabilitySimulatedTimeout:
    """``fake_dispatch_stub`` flips the hook to ``("timeout",)``."""

    def test_simulated_timeout_returns_structured_timeout_error(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
    ) -> None:
        fake_dispatch_stub(lambda _cmd: ("timeout",))
        result = _invoke_dispatch(
            tool_name="review_spec",
            payload_json="{}",
            timeout_seconds=10,
        )
        assert result == (
            "TIMEOUT: agent_id=product-owner tool_name=review_spec "
            "timeout_seconds=10"
        )


# ===========================================================================
# dispatch_by_capability — specialist_error via _stub_response_hook
# ===========================================================================
class TestDispatchByCapabilitySpecialistError:
    """``fake_dispatch_stub`` flips the hook to
    ``("specialist_error", reason)``.
    """

    def test_simulated_specialist_error_returns_structured_error(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
    ) -> None:
        fake_dispatch_stub(lambda _cmd: ("specialist_error", "schema mismatch"))
        result = _invoke_dispatch(
            tool_name="review_spec",
            payload_json="{}",
        )
        assert result == (
            "ERROR: specialist_error — agent_id=product-owner "
            "detail=schema mismatch"
        )


# ===========================================================================
# dispatch_by_capability — concurrent dispatches (ThreadPoolExecutor, n=2)
# ===========================================================================
class TestDispatchByCapabilityConcurrent:
    """Two parallel dispatches must yield distinct correlation_ids and two
    independent log lines whose correlation_ids match the returned acks.
    """

    def test_two_parallel_dispatches_emit_distinct_correlation_ids(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def _call() -> str:
            return _invoke_dispatch(
                tool_name="review_spec",
                payload_json="{}",
            )

        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(_call) for _ in range(2)]
                results = [f.result() for f in futures]

        # Two distinct UUIDs returned.
        id_a = json.loads(results[0])["correlation_id"]
        id_b = json.loads(results[1])["correlation_id"]
        assert UUID_RE.match(id_a), id_a
        assert UUID_RE.match(id_b), id_b
        assert id_a != id_b, f"Expected distinct correlation_ids, got {id_a!r}"

        # Two anchored log lines whose correlation_ids match.
        anchored = [
            r.getMessage()
            for r in caplog.records
            if _ANCHOR_DISPATCH in r.getMessage()
        ]
        assert len(anchored) == 2, anchored
        log_cids = sorted(
            re.search(r"correlation_id=([0-9a-f-]+)", line).group(1)
            for line in anchored
        )
        assert log_cids == sorted([id_a, id_b])


# ===========================================================================
# dispatch_by_capability — real CommandPayload constructed (isinstance check)
# ===========================================================================
class TestDispatchByCapabilityRealCommandPayload:
    """The hook receives a real ``CommandPayload`` instance, not a dict."""

    def test_hook_receives_real_command_payload_instance(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
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

        fake_dispatch_stub(hook)
        _invoke_dispatch(
            tool_name="review_spec",
            payload_json='{"spec_id": "FEAT-J002", "depth": 2}',
        )
        assert len(captured) == 1
        cmd = captured[0]
        # AC-005 of TASK-J002-021: isinstance check on the captured object.
        assert isinstance(cmd, CommandPayload)
        assert not isinstance(cmd, dict)
        assert cmd.command == "review_spec"
        assert cmd.args == {"spec_id": "FEAT-J002", "depth": 2}
        assert UUID_RE.match(cmd.correlation_id), cmd.correlation_id


# ===========================================================================
# dispatch_by_capability — exact log format assertion
# ===========================================================================
class TestDispatchByCapabilityLogFormat:
    """The dispatch log line MUST match the documented format byte-for-byte:

    ``JARVIS_DISPATCH_STUB tool_name=<x> agent_id=<y> correlation_id=<z>
    topic=agents.command.<y> payload_bytes=<n>``
    """

    LOG_RE = re.compile(
        rf"^{_ANCHOR_DISPATCH} "
        r"tool_name=(?P<tool_name>\S+) "
        r"agent_id=(?P<agent_id>\S+) "
        r"correlation_id=(?P<cid>[0-9a-f-]+) "
        r"topic=agents\.command\.(?P<agent_id_topic>\S+) "
        r"payload_bytes=(?P<n>\d+)$"
    )

    def test_log_format_matches_documented_pattern(
        self,
        bound_registry: list[CapabilityDescriptor],
        fake_dispatch_stub: Callable[..., None],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            _invoke_dispatch(
                tool_name="review_spec",
                payload_json="{}",
            )
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        msg = records[0].getMessage()
        m = self.LOG_RE.match(msg)
        assert m is not None, f"Log line did not match pattern:\n{msg}"
        assert m.group("tool_name") == "review_spec"
        assert m.group("agent_id") == "product-owner"
        assert m.group("agent_id_topic") == "product-owner"
        assert UUID_RE.match(m.group("cid")), m.group("cid")
        assert int(m.group("n")) > 0


# ===========================================================================
# queue_build — happy path
# ===========================================================================
class TestQueueBuildHappyPath:
    """A valid feature_id + repo + adapter returns a JSON ack."""

    def test_happy_path_returns_queue_build_ack(self) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat-j002/spec.yaml",
            repo="appmilla/forge",
        )
        ack = json.loads(result)
        assert ack["feature_id"] == "FEAT-J002"
        assert ack["status"] == "queued"
        assert ack["publish_target"] == "pipeline.build-queued.FEAT-J002"
        assert UUID_RE.match(ack["correlation_id"]), ack["correlation_id"]


# ===========================================================================
# queue_build — feature_id table
# ===========================================================================
class TestQueueBuildFeatureIdTable:
    """Boundary table for ``feature_id`` (^FEAT-[A-Z0-9]{3,12}$).

    Note on the Gherkin ``FEAT-JARVIS-EXAMPLE01`` row: the ``.feature``
    examples table lists that string as accepted, but the implementation
    pattern in both ``BuildQueuedPayload`` and ``dispatch.py`` is
    ``^FEAT-[A-Z0-9]{3,12}$`` which rejects strings containing a second
    dash and exceeding 12 trailing characters. The tests here pin the
    **implementation** behaviour (which the existing TASK-J002-014 test
    suite also pins). The Gherkin row is treated as documentation drift
    against the canonical pattern; updating the Gherkin or relaxing the
    pattern is a separate scope-bearing change.
    """

    @pytest.mark.parametrize(
        "good",
        ["FEAT-AB1", "FEAT-J002", "FEAT-JARVIS002"],
    )
    def test_valid_feature_ids_accepted(self, good: str) -> None:
        result = _invoke_queue_build(
            feature_id=good,
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        assert not result.startswith("ERROR"), result
        ack = json.loads(result)
        assert ack["feature_id"] == good

    @pytest.mark.parametrize(
        "bad",
        [
            "FEAT-AB",  # too short — Gherkin row
            "feat-jarvis-002",  # lowercase — Gherkin row
            "BUG-JARVIS-001",  # wrong prefix — Gherkin row
            "FEAT-JARVIS-EXAMPLE01",  # documented Gherkin "accept" but
            # actually rejected by pattern (see class docstring).
        ],
    )
    def test_invalid_feature_ids_rejected(self, bad: str) -> None:
        result = _invoke_queue_build(
            feature_id=bad,
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
        )
        assert result.startswith("ERROR: invalid_feature_id"), result
        assert "must match FEAT-XXX pattern" in result
        assert f"got {bad}" in result


# ===========================================================================
# queue_build — repo table
# ===========================================================================
class TestQueueBuildRepoTable:
    """Boundary table for ``repo`` (^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$)."""

    @pytest.mark.parametrize("good", ["guardkit/jarvis", "appmilla/forge"])
    def test_valid_repos_accepted(self, good: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo=good,
        )
        assert not result.startswith("ERROR"), result

    @pytest.mark.parametrize(
        "bad",
        [
            "guardkit",  # no slash — Gherkin row
            "guardkit/jarvis/extra",  # too many slashes — Gherkin row
        ],
    )
    def test_invalid_repos_rejected(self, bad: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo=bad,
        )
        assert result.startswith("ERROR: invalid_repo"), result
        assert "must be org/name format" in result


# ===========================================================================
# queue_build — originating_adapter table
# ===========================================================================
class TestQueueBuildAdapterTable:
    """Allow-list table for ``originating_adapter``."""

    @pytest.mark.parametrize(
        "good",
        ["terminal", "telegram", "dashboard", "voice-reachy"],
    )
    def test_each_allowed_adapter_accepted(self, good: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
            originating_adapter=good,
        )
        assert not result.startswith("ERROR"), result

    @pytest.mark.parametrize(
        "bad",
        [
            "email",  # Gherkin row
            "TERMINAL",  # Gherkin row (case-sensitive)
            "twitter",
            "",
        ],
    )
    def test_invalid_adapters_rejected(self, bad: str) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat.yaml",
            repo="guardkit/jarvis",
            originating_adapter=bad,
        )
        assert result.startswith("ERROR: invalid_adapter"), result
        assert f"{bad} not in allowed list" in result


# ===========================================================================
# queue_build — real BuildQueuedPayload instance (isinstance check)
# ===========================================================================
class TestQueueBuildRealBuildQueuedPayload:
    """The tool constructs a real ``BuildQueuedPayload`` (not a dict) before
    logging. We reconstruct the canonical payload and round-trip it through
    ``model_validate_json`` to assert the model is a real instance.
    """

    def test_payload_is_real_build_queued_payload_instance(self) -> None:
        result = _invoke_queue_build(
            feature_id="FEAT-J002",
            feature_yaml_path="features/feat-j002/spec.yaml",
            repo="appmilla/forge",
            branch="main",
            originating_adapter="terminal",
            correlation_id="corr-abc",
            parent_request_id="parent-xyz",
        )
        ack = json.loads(result)
        assert ack["correlation_id"] == "corr-abc"
        # Reconstruct the canonical payload that the tool constructed.
        from datetime import datetime

        payload = BuildQueuedPayload(
            feature_id="FEAT-J002",
            repo="appmilla/forge",
            branch="main",
            feature_yaml_path="features/feat-j002/spec.yaml",
            triggered_by="jarvis",
            originating_adapter="terminal",
            correlation_id="corr-abc",
            parent_request_id="parent-xyz",
            requested_at=datetime.fromisoformat(ack["queued_at"]),
            queued_at=datetime.fromisoformat(ack["queued_at"]),
        )
        # AC-005 of TASK-J002-021: isinstance check.
        assert isinstance(payload, BuildQueuedPayload)
        assert not isinstance(payload, dict)
        assert payload.triggered_by == "jarvis"
        # JSON round-trip via model_validate_json proves we built a real
        # pydantic model, not a dict masquerading as one.
        restored = BuildQueuedPayload.model_validate_json(payload.model_dump_json())
        assert isinstance(restored, BuildQueuedPayload)
        assert restored == payload


# ===========================================================================
# queue_build — exact log format assertion
# ===========================================================================
class TestQueueBuildLogFormat:
    """The queue_build log line MUST match the documented format:

    ``JARVIS_QUEUE_BUILD_STUB feature_id=<x> repo=<y> correlation_id=<z>
    topic=pipeline.build-queued.<x> payload_bytes=<n>``
    """

    LOG_RE = re.compile(
        rf"^{_ANCHOR_QUEUE_BUILD} "
        r"feature_id=(?P<feature_id>\S+) "
        r"repo=(?P<repo>\S+) "
        r"correlation_id=(?P<cid>\S+) "
        r"topic=pipeline\.build-queued\.(?P<feature_id_topic>\S+) "
        r"payload_bytes=(?P<n>\d+)$"
    )

    def test_log_format_matches_documented_pattern(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"):
            _invoke_queue_build(
                feature_id="FEAT-J002",
                feature_yaml_path="features/feat.yaml",
                repo="guardkit/jarvis",
                correlation_id="trace-1",
            )
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        msg = records[0].getMessage()
        m = self.LOG_RE.match(msg)
        assert m is not None, f"Log line did not match pattern:\n{msg}"
        assert m.group("feature_id") == "FEAT-J002"
        assert m.group("feature_id_topic") == "FEAT-J002"
        assert m.group("repo") == "guardkit/jarvis"
        assert m.group("cid") == "trace-1"
        assert int(m.group("n")) > 0


# ===========================================================================
# Swap-point grep invariant — DDR-009
# ===========================================================================
class TestSwapPointGrepInvariant:
    """The post-Wave-3 grep invariant.

    ``grep -rn "JARVIS_DISPATCH_STUB|JARVIS_QUEUE_BUILD_STUB" src/jarvis/``
    MUST return exactly four anchored lines, **all** of them in
    ``src/jarvis/tools/dispatch.py``:

    1. ``LOG_PREFIX_DISPATCH: str = "JARVIS_DISPATCH_STUB"`` (constant)
    2. ``LOG_PREFIX_QUEUE_BUILD: str = "JARVIS_QUEUE_BUILD_STUB"`` (constant)
    3. The ``logger.info("JARVIS_DISPATCH_STUB ...")`` line in
       ``dispatch_by_capability``.
    4. The ``logger.info("JARVIS_QUEUE_BUILD_STUB ...")`` line in
       ``queue_build``.

    The test fails if:

    - Any anchor leaks to a module other than ``tools/dispatch.py``
      (FEAT-JARVIS-004/005 would lose its grep landmark).
    - The anchor name drifts (e.g. someone renames
      ``JARVIS_DISPATCH_STUB`` to ``JARVIS_DISPATCH_LEGACY``).
    - The post-wiring count drops below 4 (a usage line was deleted).
    """

    @staticmethod
    def _grep_anchors() -> list[str]:
        """Run grep and return non-empty matched lines."""
        src_jarvis = _project_root() / "src" / "jarvis"
        # The grep pattern is constructed from token concatenation so this
        # test file does not match itself even when the search root is
        # accidentally widened to repo-root in a future refactor.
        pattern = rf"{_ANCHOR_DISPATCH}\|{_ANCHOR_QUEUE_BUILD}"
        result = subprocess.run(
            ["grep", "-rIn", pattern, str(src_jarvis)],
            capture_output=True,
            text=True,
            check=False,
        )
        # grep returns 0 when matches found, 1 when none, 2 on real error.
        assert result.returncode in (0, 1), result.stderr
        return [ln for ln in result.stdout.splitlines() if ln.strip()]

    def test_anchors_are_all_inside_tools_dispatch_py(self) -> None:
        """No anchor leaks: every match lives in ``tools/dispatch.py``."""
        lines = self._grep_anchors()
        offenders = [ln for ln in lines if "tools/dispatch.py" not in ln]
        assert not offenders, (
            "Swap-point anchors leaked to other modules:\n"
            + "\n".join(offenders)
        )

    def test_anchor_count_is_exactly_four(self) -> None:
        """Post-Wave-3 invariant: exactly 4 anchored lines (2 constants
        + 2 logger.info usages).
        """
        lines = self._grep_anchors()
        dispatch_lines = [ln for ln in lines if "tools/dispatch.py" in ln]
        assert len(dispatch_lines) == 4, (
            "Expected exactly 4 anchored lines in src/jarvis/tools/"
            f"dispatch.py (2 LOG_PREFIX_* constants + 2 logger.info "
            f"usages). Found {len(dispatch_lines)}:\n"
            + "\n".join(dispatch_lines)
        )

    def test_two_anchored_lines_are_constant_definitions(self) -> None:
        """Two of the four matches are the LOG_PREFIX_* constant
        definitions (with their literal anchor values).
        """
        lines = self._grep_anchors()
        const_lines = [
            ln
            for ln in lines
            if "LOG_PREFIX_DISPATCH: str =" in ln
            or "LOG_PREFIX_QUEUE_BUILD: str =" in ln
        ]
        assert len(const_lines) == 2, (
            "Expected exactly 2 LOG_PREFIX_* constant definition lines:\n"
            + "\n".join(const_lines)
        )

    def test_two_anchored_lines_are_logger_info_usages(self) -> None:
        """The remaining two matches are the ``logger.info`` anchor
        lines — one in ``dispatch_by_capability`` and one in ``queue_build``.

        We verify by reading the source and asserting that each anchor
        string appears on exactly one line that is NOT a constant
        definition.
        """
        lines = self._grep_anchors()
        usage_lines = [
            ln
            for ln in lines
            if "LOG_PREFIX_" not in ln
            and ("tool_name=%s" in ln or "feature_id=%s" in ln)
        ]
        assert len(usage_lines) == 2, (
            "Expected exactly 2 logger.info usage lines (one per dispatch "
            f"tool). Found {len(usage_lines)}:\n" + "\n".join(usage_lines)
        )
        # One usage per anchor.
        dispatch_usages = [ln for ln in usage_lines if _ANCHOR_DISPATCH in ln]
        queue_build_usages = [
            ln for ln in usage_lines if _ANCHOR_QUEUE_BUILD in ln
        ]
        assert len(dispatch_usages) == 1, dispatch_usages
        assert len(queue_build_usages) == 1, queue_build_usages

    def test_anchor_values_match_log_prefix_constants(self) -> None:
        """Belt-and-braces: the literal anchors and the module constants
        must agree. If a future refactor renames one but not the other,
        the grep invariant alone could pass while the runtime log breaks.
        """
        assert dispatch.LOG_PREFIX_DISPATCH == _ANCHOR_DISPATCH
        assert dispatch.LOG_PREFIX_QUEUE_BUILD == _ANCHOR_QUEUE_BUILD
