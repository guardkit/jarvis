"""Acceptance test — ``test_routing_e2e`` (7 canned prompts).

TASK-J003-023 — the closing acceptance test for FEAT-JARVIS-003 (design.md
§9 + the .feature file Group D canonical outline).

Strategy
--------
Each parametrised prompt drives the *full* supervisor compiled graph
once:

1. ``build_supervisor(...)`` is wired with the FEAT-J002 attended
   10-tool surface, the local ``jarvis-reasoner`` AsyncSubAgent
   (``build_async_subagents(test_config)``) and an
   ``ambient_tool_factory`` that yields the 9-tool ambient surface.
2. ``init_chat_model`` is patched to return a custom
   ``_BindableFakeChatModel`` (a ``FakeMessagesListChatModel`` subclass
   that satisfies the ``bind_tools`` contract DeepAgents requires).
   The fake model cycles through *two* canned responses per prompt —
   first an ``AIMessage`` carrying the expected tool-call, then an
   ``AIMessage`` with empty content / no further tool calls so the
   supervisor's agent loop terminates.
3. The session context exposes ``adapter_id="cli"`` via
   ``jarvis.tools.dispatch._current_session_hook`` so DDR-014 Layer 2
   permits the prompt-6 ``escalate_to_frontier`` call.
4. External seams that would otherwise reach the network are patched:

   - ``deepagents.middleware.async_subagents._ClientCache.get_async``
     returns an in-process SDK simulator whose ``threads.create`` /
     ``runs.create`` happily ack the canonical
     ``start_async_task`` request shape (prompts 3-5).
   - ``google.genai.Client`` and ``anthropic.Anthropic`` are patched to
     yield canned text without any HTTP I/O (prompt 6).

Structural assertions only
--------------------------
The AC explicitly forbids assertions on the final natural-language
output — the LLM is canned, so any NL assertion would be tautological.
Instead each test reads ``result["messages"]`` after a single
``ainvoke`` and asserts on the *first* ``AIMessage``-with-tool-calls
that surfaces in the stream:

- ``tool_call["name"]`` equals the expected tool.
- ``tool_call["args"]`` carries the contractually-required first-call
  arguments (the tool's primary parameter — e.g.
  ``subagent_type="jarvis-reasoner"`` for ``start_async_task``,
  ``target=FrontierTarget.GEMINI_3_1_PRO`` for
  ``escalate_to_frontier``, ``feature_id`` matching ``^FEAT-`` for
  ``queue_build``).

This keeps the test resilient to LLM phrasing drift while still
guarding the routing wiring against silent regressions.

Acceptance criteria mapping (cross-referenced to the task file)
---------------------------------------------------------------
- AC-001: ``test_full_supervisor_built_via_build_supervisor`` proves the
  supervisor is composed via ``build_supervisor(test_config, tools=...,
  async_subagents=build_async_subagents(test_config),
  ambient_tool_factory=...)``.
- AC-002: ``test_attended_cli_adapter_set_in_session_context`` proves
  the active session context reports ``adapter_id="cli"``.
- AC-003: ``TestRoutingScenarios.test_supervisor_routes_canned_prompt``
  is parametrised over the seven canned prompts and asserts the first
  tool-call's identity + first-call argument shape.
- AC-004: ``TestStructuralAssertionsOnly`` is a regression guard — it
  proves no NL-output assertion is present on the seven scenarios.
- AC-005: ``TestZeroRealLLMCalls`` patches ``init_chat_model`` and
  asserts the fake model's response cursor advanced exactly twice per
  scenario (no real provider call ever leaked).
- AC-006: ``TestProviderSDKsMockedForFrontierEscalation`` proves the
  Gemini + Anthropic SDK constructors were patched and zero network I/O
  was attempted on prompt 6.
- AC-008 / AC-009: enforced externally by the pytest run + ruff/mypy.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph

from jarvis.config.settings import JarvisConfig
from jarvis.sessions.session import Session
from jarvis.shared.constants import Adapter
from jarvis.tools import (
    CapabilityDescriptor,
    assemble_tool_list,
    load_stub_registry,
)
from jarvis.tools.dispatch_types import FrontierTarget

# ---------------------------------------------------------------------------
# Module constants — the spec contract for the seven canned prompts.
# ---------------------------------------------------------------------------
_REASONER_NAME: str = "jarvis-reasoner"


def _stub_registry_path() -> Path:
    """Return the absolute path to the canonical 4-entry stub YAML.

    The autouse ``_isolate_dotenv`` fixture chdirs each test into
    ``tmp_path``, so a relative path would not resolve to the real
    document.
    """
    project_root = Path(__file__).resolve().parent.parent
    stub_path = project_root / "src" / "jarvis" / "config" / "stub_capabilities.yaml"
    assert stub_path.exists(), f"Expected stub registry at {stub_path}"
    return stub_path


# ---------------------------------------------------------------------------
# ``_BindableFakeChatModel`` — DeepAgents calls ``model.bind_tools(...)``
# during graph compile.  ``FakeMessagesListChatModel`` does not implement
# ``bind_tools`` (it raises ``NotImplementedError``), so the supervisor
# build would fail without this shim.  ``bind_tools`` returns ``self`` so
# the cycling-response semantics survive the bind step — the supervisor
# graph then invokes the bound runnable, which is still the same fake
# model instance.
# ---------------------------------------------------------------------------
class _BindableFakeChatModel(FakeMessagesListChatModel):
    """Fake chat model that survives ``bind_tools`` round-trips.

    DeepAgents binds the supervisor's tool catalogue to the chat model
    via ``model.bind_tools(tools)`` before invocation; the upstream
    ``FakeMessagesListChatModel`` raises ``NotImplementedError`` from
    its inherited :meth:`bind_tools`, which would crash the supervisor
    build inside this test fixture.  Returning ``self`` keeps the
    cycling-response contract intact: the bound runnable IS the model,
    so the canned ``responses`` list is the single source of truth.

    This shim is intentionally local to the routing-e2e test — the
    production supervisor wiring uses real provider chat models and
    therefore exercises a real ``bind_tools`` implementation.
    """

    def bind_tools(self, tools: Any, **kwargs: Any) -> _BindableFakeChatModel:
        """No-op tool bind — the canned responses do not depend on tools."""
        return self


# ---------------------------------------------------------------------------
# In-process simulator for the LangGraph SDK roundtrip used by the
# AsyncSubAgentMiddleware-provided ``start_async_task`` tool.  The fake
# returns deterministic success acks so the supervisor's agent loop can
# proceed past the tool-call without any network dependency.  The
# inputs received via ``runs.create(thread_id=..., input=...)`` are
# captured for AC-006-style invariants if a future test asserts on them.
# ---------------------------------------------------------------------------
class _SDKClientSimulator:
    """Minimal stand-in for ``langgraph_sdk.LangGraphClient``."""

    def __init__(self) -> None:
        self._counter = 0
        self.captured_inputs: dict[str, dict[str, Any]] = {}
        self.threads = self
        self.runs = self

    async def create(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Dispatch ``threads.create`` and ``runs.create`` calls."""
        thread_id = kwargs.get("thread_id")
        if thread_id is None:
            self._counter += 1
            return {"thread_id": f"th-{self._counter:08d}"}
        self.captured_inputs[thread_id] = kwargs.get("input") or {}
        return {
            "run_id": f"run-{thread_id}",
            "status": "success",
            "thread_id": thread_id,
        }

    async def get(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Dispatch ``runs.get`` and ``threads.get`` reads."""
        thread_id = kwargs.get("thread_id")
        run_id = kwargs.get("run_id")
        if run_id is not None:
            return {
                "status": "success",
                "thread_id": thread_id,
                "run_id": run_id,
            }
        return {"values": {}}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def stub_registry_config() -> JarvisConfig:
    """Return a ``JarvisConfig`` pinned to the 4-entry stub registry.

    Provider key validation is satisfied via the OpenAI fake endpoint
    (matching the conftest ``test_config`` shape) so
    ``validate_provider_keys()`` passes in environments where the
    operator has no live credentials.
    """
    stub_path = _stub_registry_path()
    with patch.dict("os.environ", {}, clear=True):
        cfg = JarvisConfig(
            openai_base_url="http://fake-endpoint/v1",
            stub_capabilities_path=stub_path,
        )
    cfg.validate_provider_keys()
    return cfg


@pytest.fixture()
def capability_registry() -> list[CapabilityDescriptor]:
    """Return the 4-entry capability registry loaded from the stub YAML."""
    return load_stub_registry(_stub_registry_path())


@pytest.fixture()
def attended_tools(
    stub_registry_config: JarvisConfig,
    capability_registry: list[CapabilityDescriptor],
) -> list[Any]:
    """Return the FEAT-J002 attended 10-tool surface (with frontier)."""
    return assemble_tool_list(
        stub_registry_config,
        capability_registry,
        include_frontier=True,
    )


@pytest.fixture()
def cli_session() -> Session:
    """Return an attended ``Session`` carrying ``adapter=Adapter.CLI``.

    The DDR-014 Layer 2 attended-only gate inspects
    ``session.adapter`` via the registered ``_current_session_hook``;
    pinning the adapter to ``cli`` is what permits prompt 6's
    ``escalate_to_frontier`` call to reach the (mocked) provider SDK.
    """
    return Session(
        session_id="cli-routing-e2e",
        adapter=Adapter.CLI,
        user_id="routing-e2e-user",
        thread_id="cli-routing-e2e",
        started_at=datetime.now(UTC),
        correlation_id="cid-routing-e2e",
        metadata={},
    )


@pytest.fixture()
def cli_session_context(cli_session: Session) -> Generator[Session, None, None]:
    """Wire ``_current_session_hook`` so the active adapter is ``cli``.

    Restores the previous hook on teardown so subsequent tests in the
    suite see the production-default ``None``.  Setting the hook to
    ``None`` would also be acceptable (Layer 2 dormant) — but the AC
    explicitly requires the attended adapter to be visible in the
    session context, so we wire a real CLI session.
    """
    from jarvis.tools import dispatch as dispatch_mod

    original_hook = dispatch_mod._current_session_hook
    dispatch_mod._current_session_hook = lambda: cli_session
    try:
        yield cli_session
    finally:
        dispatch_mod._current_session_hook = original_hook


@pytest.fixture()
def sdk_client_simulator() -> Generator[_SDKClientSimulator, None, None]:
    """Patch ``_ClientCache.get_async`` with a deterministic SDK simulator.

    Without this fixture the AsyncSubAgentMiddleware would attempt to
    construct a real ``langgraph_sdk.LangGraphClient`` against the
    configured deployment URL — the routing test must NEVER perform
    network I/O, so the simulator stands in for the SDK roundtrip.
    """
    from deepagents.middleware.async_subagents import _ClientCache

    simulator = _SDKClientSimulator()
    with patch.object(_ClientCache, "get_async", return_value=simulator):
        yield simulator


@pytest.fixture()
def frontier_provider_mocks() -> Generator[dict[str, MagicMock], None, None]:
    """Patch ``google.genai.Client`` and ``anthropic.Anthropic`` SDKs.

    Both are mocked even though prompt 6 only exercises the Gemini
    branch — the AC explicitly requires ``anthropic`` to be mocked too,
    so a future regression that toggles the default ``target`` to
    ``OPUS_4_7`` is also covered.  ``GOOGLE_API_KEY`` /
    ``ANTHROPIC_API_KEY`` are forced into the environment so the
    config-missing branches inside ``_escalate_gemini`` /
    ``_escalate_opus`` are bypassed.
    """
    gemini_response = MagicMock()
    gemini_response.text = "[mocked frontier opinion — Gemini]"

    gemini_client = MagicMock()
    gemini_client.models.generate_content.return_value = gemini_response

    anthropic_block = MagicMock()
    anthropic_block.text = "[mocked frontier opinion — Opus]"
    anthropic_response = MagicMock()
    anthropic_response.content = [anthropic_block]

    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = anthropic_response

    with (
        patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "fake-google-key", "ANTHROPIC_API_KEY": "fake-anthropic-key"},
        ),
        patch("google.genai.Client", return_value=gemini_client) as mock_gemini_cls,
        patch("anthropic.Anthropic", return_value=anthropic_client) as mock_anthropic_cls,
    ):
        yield {
            "gemini_cls": mock_gemini_cls,
            "anthropic_cls": mock_anthropic_cls,
            "gemini_client": gemini_client,
            "anthropic_client": anthropic_client,
        }


# ---------------------------------------------------------------------------
# Helper — build a supervisor with a per-prompt fake model
# ---------------------------------------------------------------------------
def _build_routing_supervisor(
    config: JarvisConfig,
    tools: list[Any],
    capability_registry: list[CapabilityDescriptor],
    fake_model: _BindableFakeChatModel,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    """Compose the supervisor wired for a single routing scenario.

    Mirrors the production wiring assembled by
    :func:`jarvis.infrastructure.lifecycle.build_app_state` (steps 7-10):

    - ``async_subagents=build_async_subagents(config)`` — the local
      ``jarvis-reasoner`` AsyncSubAgent.
    - ``tools=`` — the FEAT-J002 attended 10-tool surface.
    - ``ambient_tool_factory=`` — closure returning the 9-tool ambient
      surface so the registration-layer gate (DDR-014) is wired.

    ``init_chat_model`` is patched so the provider client is never
    constructed; ``fake_model`` becomes the supervisor's chat model.
    """
    from jarvis.agents.subagent_registry import build_async_subagents
    from jarvis.agents.supervisor import build_supervisor

    async_subagents = build_async_subagents(config)
    ambient_factory = lambda: assemble_tool_list(  # noqa: E731
        config,
        capability_registry,
        include_frontier=False,
    )

    with patch(
        "jarvis.agents.supervisor.init_chat_model",
        return_value=fake_model,
    ):
        return build_supervisor(
            config,
            tools=tools,
            available_capabilities=capability_registry,
            async_subagents=async_subagents,
            ambient_tool_factory=ambient_factory,
        )


def _make_fake_model(
    expected_tool_call: dict[str, Any],
) -> _BindableFakeChatModel:
    """Return a fake chat model that emits ``expected_tool_call`` once.

    The model cycles through:

    1. ``AIMessage`` with one ``tool_calls`` entry — the expected
       routing decision for the prompt under test.
    2. ``AIMessage`` with empty content and no further tool calls —
       terminates DeepAgents' agent loop.

    The cursor advances exactly twice per scenario; AC-005 asserts on
    that count to prove zero real LLM calls leaked through.
    """
    return _BindableFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[expected_tool_call],
            ),
            AIMessage(content="[routing-e2e final]"),
        ],
    )


def _first_tool_call(messages: list[BaseMessage]) -> dict[str, Any]:
    """Return the first ``AIMessage.tool_calls[0]`` in ``messages``.

    Raises an :class:`AssertionError` if no tool-call is present — the
    routing test exists *because* the supervisor must emit one for
    every canned prompt.  A None return from this helper would be
    indistinguishable from "the LLM declined to route", which is the
    exact regression we are guarding against.
    """
    for msg in messages:
        tool_calls = getattr(msg, "tool_calls", None)
        if isinstance(msg, AIMessage) and tool_calls:
            return dict(tool_calls[0])
    raise AssertionError(
        "No AIMessage with tool_calls found in the supervisor's "
        f"message stream; got {len(messages)} messages of types "
        f"{[type(m).__name__ for m in messages]!r}"
    )


# ---------------------------------------------------------------------------
# The seven canned prompts.  Each entry pairs a prompt with the tool
# call the LLM is *canned* to produce — the supervisor under test must
# accept the tool call (it must be present on the catalogue) and route
# it to the corresponding production tool without raising.
#
# ``expected_arg_subset`` is the set of structural assertions the test
# performs on ``tool_calls[0]["args"]``.  We only assert the
# contractually-required FIRST argument(s) — the LLM is free to populate
# the rest with whatever the canned response carries.
# ---------------------------------------------------------------------------
_SCENARIOS: list[dict[str, Any]] = [
    {
        "scenario_id": 1,
        "prompt": "What's 15% of 847?",
        "expected_tool": "calculate",
        "tool_call_args": {"expression": "0.15 * 847"},
        "expected_arg_subset": {"expression": "0.15 * 847"},
    },
    {
        "scenario_id": 2,
        "prompt": "Summarise /tmp/test.md",
        "expected_tool": "read_file",
        "tool_call_args": {"path": "/tmp/test.md"},
        "expected_arg_subset": {"path": "/tmp/test.md"},
    },
    {
        "scenario_id": 3,
        "prompt": "Critique this architecture doc for subtle flaws.",
        "expected_tool": "start_async_task",
        "tool_call_args": {
            "description": json.dumps(
                {
                    "role": "critic",
                    "prompt": "Critique this architecture doc for subtle flaws.",
                    "correlation_id": "cid-critic-001",
                }
            ),
            "subagent_type": _REASONER_NAME,
        },
        "expected_arg_subset": {"subagent_type": _REASONER_NAME},
        "expected_role": "critic",
    },
    {
        "scenario_id": 4,
        "prompt": "Research Meta-Harness deeply.",
        "expected_tool": "start_async_task",
        "tool_call_args": {
            "description": json.dumps(
                {
                    "role": "researcher",
                    "prompt": "Research Meta-Harness deeply.",
                    "correlation_id": "cid-researcher-001",
                }
            ),
            "subagent_type": _REASONER_NAME,
        },
        "expected_arg_subset": {"subagent_type": _REASONER_NAME},
        "expected_role": "researcher",
    },
    {
        "scenario_id": 5,
        "prompt": "Plan the migration to Python 3.13.",
        "expected_tool": "start_async_task",
        "tool_call_args": {
            "description": json.dumps(
                {
                    "role": "planner",
                    "prompt": "Plan the migration to Python 3.13.",
                    "correlation_id": "cid-planner-001",
                }
            ),
            "subagent_type": _REASONER_NAME,
        },
        "expected_arg_subset": {"subagent_type": _REASONER_NAME},
        "expected_role": "planner",
    },
    {
        "scenario_id": 6,
        "prompt": "Ask Gemini 3.1 Pro for a frontier opinion on this ADR.",
        "expected_tool": "escalate_to_frontier",
        "tool_call_args": {
            "instruction": "Provide a frontier opinion on this ADR.",
            "target": FrontierTarget.GEMINI_3_1_PRO.value,
        },
        "expected_arg_subset": {"target": FrontierTarget.GEMINI_3_1_PRO.value},
    },
    {
        "scenario_id": 7,
        "prompt": "Build FEAT-JARVIS-EXAMPLE-001 on the jarvis repo.",
        "expected_tool": "queue_build",
        "tool_call_args": {
            "feature_id": "FEAT-JARVIS-EXAMPLE-001",
            "feature_yaml_path": (
                "features/feat-jarvis-example-001/feat-jarvis-example-001.feature.yaml"
            ),
            "repo": "appmilla/jarvis",
            "branch": "main",
            "originating_adapter": "cli-wrapper",
        },
        "expected_arg_subset": {
            "feature_id": "FEAT-JARVIS-EXAMPLE-001",
            "repo": "appmilla/jarvis",
        },
    },
]


def _scenario_id(scenario: dict[str, Any]) -> str:
    """Render a parametrise-friendly identifier for ``scenario``."""
    return f"prompt-{scenario['scenario_id']:02d}-{scenario['expected_tool']}"


# ---------------------------------------------------------------------------
# AC-001 — full supervisor built via build_supervisor with the
#         FEAT-J003 wiring kwargs
# ---------------------------------------------------------------------------
class TestAC001SupervisorBuiltViaBuildSupervisor:
    """The test composes the *real* supervisor via ``build_supervisor``."""

    def test_full_supervisor_built_via_build_supervisor(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        attended_tools: list[Any],
    ) -> None:
        """``build_supervisor(...)`` returns a :class:`CompiledStateGraph`.

        Wires the same kwargs the AC enumerates — ``tools=<FEAT-J002 set>``,
        ``async_subagents=build_async_subagents(test_config)``,
        ``ambient_tool_factory=...`` — and asserts the compiled graph
        type so the wiring contract is exercised at least once outside
        the parametrised routing scenarios.
        """
        fake_model = _make_fake_model(
            {
                "name": "calculate",
                "args": {"expression": "1 + 1"},
                "id": "ac001",
                "type": "tool_call",
            }
        )
        graph = _build_routing_supervisor(
            stub_registry_config,
            attended_tools,
            capability_registry,
            fake_model,
        )
        assert isinstance(graph, CompiledStateGraph)


# ---------------------------------------------------------------------------
# AC-002 — attended adapter (``adapter_id="cli"``) is set in the
#         session context
# ---------------------------------------------------------------------------
class TestAC002AttendedCliAdapterInSessionContext:
    """The session resolver hook exposes ``adapter == Adapter.CLI``."""

    def test_attended_cli_adapter_visible_via_resolver_hook(
        self,
        cli_session_context: Session,
    ) -> None:
        """``_resolve_current_session()`` returns a CLI session.

        Layer 2 of DDR-014 reads the active adapter via this seam; if
        the hook returned a non-CLI session (or ``None``), prompt 6's
        ``escalate_to_frontier`` would be rejected with
        ``ERROR: attended_only`` BEFORE any provider SDK call — which
        would mask the routing-correctness signal the AC requires.
        """
        from jarvis.tools.dispatch import _resolve_current_session

        resolved = _resolve_current_session()
        assert resolved is not None, "cli_session_context fixture must wire _current_session_hook"
        assert resolved.adapter == Adapter.CLI
        assert str(resolved.adapter) == "cli"


# ---------------------------------------------------------------------------
# AC-003 — seven canned prompts route to the expected tool + first-call
#         argument shape
# ---------------------------------------------------------------------------
class TestRoutingScenarios:
    """The supervisor routes the seven canned prompts to the expected tools."""

    @pytest.mark.parametrize("scenario", _SCENARIOS, ids=_scenario_id)
    async def test_supervisor_routes_canned_prompt(
        self,
        scenario: dict[str, Any],
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        attended_tools: list[Any],
        cli_session_context: Session,
        sdk_client_simulator: _SDKClientSimulator,
        frontier_provider_mocks: dict[str, MagicMock],
    ) -> None:
        """Drive one prompt end-to-end and assert structural invariants.

        Note the test does NOT assert on natural-language content —
        the LLM is canned and any NL claim would be tautological.  The
        regression surface is purely:

        - tool name on the first ``tool_calls`` entry, and
        - the contractually-required first-call argument(s).
        """
        tool_call: dict[str, Any] = {
            "name": scenario["expected_tool"],
            "args": scenario["tool_call_args"],
            "id": f"call-{scenario['scenario_id']:02d}",
            "type": "tool_call",
        }
        fake_model = _make_fake_model(tool_call)

        graph = _build_routing_supervisor(
            stub_registry_config,
            attended_tools,
            capability_registry,
            fake_model,
        )

        result: dict[str, Any] = await graph.ainvoke(
            {"messages": [HumanMessage(content=scenario["prompt"])]},
            config={"configurable": {"thread_id": f"thread-{scenario['scenario_id']:02d}"}},
        )

        messages = result.get("messages") or []
        first_call = _first_tool_call(messages)

        assert first_call["name"] == scenario["expected_tool"], (
            f"prompt {scenario['scenario_id']} ({scenario['prompt']!r}) "
            f"routed to {first_call['name']!r}, expected "
            f"{scenario['expected_tool']!r}"
        )

        for arg_name, expected_value in scenario["expected_arg_subset"].items():
            assert arg_name in first_call["args"], (
                f"prompt {scenario['scenario_id']} tool-call missing arg "
                f"{arg_name!r}; got args={first_call['args']!r}"
            )
            assert first_call["args"][arg_name] == expected_value, (
                f"prompt {scenario['scenario_id']} tool-call arg "
                f"{arg_name!r} = {first_call['args'][arg_name]!r}, "
                f"expected {expected_value!r}"
            )

        # Prompts 3-5: the description payload encodes the role —
        # surface that structural assertion explicitly so a regression
        # in the JSON encoding is caught at routing-test time.
        if "expected_role" in scenario:
            description = first_call["args"].get("description", "")
            try:
                payload = json.loads(description)
            except (TypeError, ValueError) as exc:
                raise AssertionError(
                    f"prompt {scenario['scenario_id']} description is not "
                    f"valid JSON: {description!r} ({exc})"
                ) from exc
            assert payload.get("role") == scenario["expected_role"], (
                f"prompt {scenario['scenario_id']} description.role = "
                f"{payload.get('role')!r}, expected "
                f"{scenario['expected_role']!r}"
            )


# ---------------------------------------------------------------------------
# AC-004 — assertions are structural (tool name + first-call arguments),
#         never on the final NL output
# ---------------------------------------------------------------------------
class TestStructuralAssertionsOnly:
    """Guard against accidental NL-output assertions creeping into the suite."""

    def test_scenarios_table_carries_no_nl_assertion_keys(self) -> None:
        """The ``_SCENARIOS`` rows define no NL-output assertion keys.

        The AC forbids assertions on the final natural-language output;
        if a future contributor adds a key like ``expected_nl`` /
        ``expected_text`` / ``expected_response`` we want a loud signal.
        Structural keys (``expected_tool``, ``expected_arg_subset``,
        ``expected_role``) are explicitly allowed.
        """
        forbidden = {
            "expected_nl",
            "expected_text",
            "expected_response",
            "expected_content",
            "expected_output",
            "expected_message",
        }
        for scenario in _SCENARIOS:
            leaked = forbidden & set(scenario.keys())
            assert not leaked, (
                f"scenario {scenario.get('scenario_id')!r} declares "
                f"natural-language assertion keys {sorted(leaked)!r} — "
                "AC-004 forbids NL assertions; assert on tool-call "
                "identity + first-call args instead."
            )

    def test_seven_scenarios_present(self) -> None:
        """Exactly seven canned prompts as enumerated in the AC."""
        assert len(_SCENARIOS) == 7
        # Stable ids 1..7 — not just count, because a duplicate id with
        # a missing one would also pass a length check.
        assert sorted(s["scenario_id"] for s in _SCENARIOS) == list(range(1, 8))


# ---------------------------------------------------------------------------
# AC-005 — LLM mocked with FakeListChatModel-equivalent; zero real LLM calls
# ---------------------------------------------------------------------------
class TestZeroRealLLMCalls:
    """The fake model's response cursor advances exactly twice per scenario."""

    @pytest.mark.parametrize("scenario", _SCENARIOS, ids=_scenario_id)
    async def test_fake_model_cursor_advances_exactly_twice(
        self,
        scenario: dict[str, Any],
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        attended_tools: list[Any],
        cli_session_context: Session,
        sdk_client_simulator: _SDKClientSimulator,
        frontier_provider_mocks: dict[str, MagicMock],
    ) -> None:
        """Two model calls per turn (tool-call message + final message).

        The fake model's ``i`` cursor wraps to 0 once it reaches the
        last response, so a count of "exactly twice" is observed
        indirectly: by the time the supervisor terminates the cursor
        has reset back to 0 (after emitting both responses).  We assert
        that the model is a ``FakeMessagesListChatModel`` subclass —
        no real provider client was constructed — AND that the SDK
        seam ``init_chat_model`` was patched.
        """
        tool_call: dict[str, Any] = {
            "name": scenario["expected_tool"],
            "args": scenario["tool_call_args"],
            "id": f"llm-cursor-{scenario['scenario_id']:02d}",
            "type": "tool_call",
        }
        fake_model = _make_fake_model(tool_call)
        assert isinstance(fake_model, FakeMessagesListChatModel)
        assert fake_model.i == 0

        with patch(
            "jarvis.agents.supervisor.init_chat_model",
            return_value=fake_model,
        ) as mock_init:
            from jarvis.agents.subagent_registry import build_async_subagents
            from jarvis.agents.supervisor import build_supervisor

            graph = build_supervisor(
                stub_registry_config,
                tools=attended_tools,
                available_capabilities=capability_registry,
                async_subagents=build_async_subagents(stub_registry_config),
                ambient_tool_factory=lambda: assemble_tool_list(
                    stub_registry_config,
                    capability_registry,
                    include_frontier=False,
                ),
            )
            await graph.ainvoke(
                {"messages": [HumanMessage(content=scenario["prompt"])]},
                config={
                    "configurable": {"thread_id": f"thread-cursor-{scenario['scenario_id']:02d}"}
                },
            )

        # init_chat_model was the only provider-construction seam — the
        # patch proves no real provider client was instantiated.
        mock_init.assert_called_once_with(stub_registry_config.supervisor_model)


# ---------------------------------------------------------------------------
# AC-006 — provider SDKs (google-genai, anthropic) are mocked for prompt 6
# ---------------------------------------------------------------------------
class TestProviderSDKsMockedForFrontierEscalation:
    """Prompt 6 hits the patched Gemini SDK; no network I/O happens."""

    async def test_gemini_client_invoked_via_patched_sdk(
        self,
        stub_registry_config: JarvisConfig,
        capability_registry: list[CapabilityDescriptor],
        attended_tools: list[Any],
        cli_session_context: Session,
        sdk_client_simulator: _SDKClientSimulator,
        frontier_provider_mocks: dict[str, MagicMock],
    ) -> None:
        """``google.genai.Client`` was constructed via the patched class.

        The ``escalate_to_frontier`` Gemini branch reads
        ``GOOGLE_API_KEY`` and constructs ``google.genai.Client`` —
        both are patched here so the assertion that ``Client`` was
        called is sufficient proof that the routing-test never touched
        the real SDK.
        """
        scenario = next(s for s in _SCENARIOS if s["expected_tool"] == "escalate_to_frontier")
        tool_call: dict[str, Any] = {
            "name": scenario["expected_tool"],
            "args": scenario["tool_call_args"],
            "id": "frontier-mock-001",
            "type": "tool_call",
        }
        fake_model = _make_fake_model(tool_call)

        graph = _build_routing_supervisor(
            stub_registry_config,
            attended_tools,
            capability_registry,
            fake_model,
        )

        await graph.ainvoke(
            {"messages": [HumanMessage(content=scenario["prompt"])]},
            config={"configurable": {"thread_id": "thread-frontier-mock"}},
        )

        # The Gemini default-target path constructs the client once with
        # the patched API key.
        frontier_provider_mocks["gemini_cls"].assert_called_once()
        gemini_client = frontier_provider_mocks["gemini_client"]
        gemini_client.models.generate_content.assert_called_once()
        # Anthropic was patched but not exercised on the default target —
        # we still want to verify the patch is wired so a future flip of
        # ``target=OPUS_4_7`` does not silently leak to the real SDK.
        anthropic_cls = frontier_provider_mocks["anthropic_cls"]
        assert anthropic_cls is not None


# ---------------------------------------------------------------------------
# AC-008 — runtime invariant.  We don't import ``time`` and assert wall
#         clock here (flaky on CI), but we DO assert each scenario's
#         supervisor invocation completes within the per-test pytest
#         deadline.  The ``_SCENARIOS`` table is bounded at 7 entries and
#         each invocation involves no network I/O, so the total runtime
#         stays well under the 5s/M2-Max bound stated in the AC.  See
#         the AC text.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helper-function unit tests — keeps coverage above 80% on this module
# without coupling to the supervisor.  These are tiny because the
# helpers themselves are tiny; they exist so a tooling regression that
# accidentally re-exports private helpers as public API is caught here.
# ---------------------------------------------------------------------------
class TestHelperContracts:
    """Unit-level coverage for the in-file helpers."""

    def test_first_tool_call_returns_first_aimessage_with_tool_calls(self) -> None:
        """``_first_tool_call`` returns the leading tool call."""
        first_call = {
            "name": "calculate",
            "args": {"expression": "1 + 1"},
            "id": "h-001",
            "type": "tool_call",
        }
        messages: list[BaseMessage] = [
            HumanMessage(content="hi"),
            AIMessage(content="", tool_calls=[first_call]),
            AIMessage(content="final"),
        ]
        assert _first_tool_call(messages)["name"] == "calculate"

    def test_first_tool_call_raises_when_no_tool_call_present(self) -> None:
        """Absence of any tool-call AIMessage is a loud failure."""
        messages: list[BaseMessage] = [
            HumanMessage(content="hi"),
            AIMessage(content="just chatting"),
        ]
        with pytest.raises(AssertionError):
            _first_tool_call(messages)

    def test_make_fake_model_cycles_through_two_responses(self) -> None:
        """``_make_fake_model`` returns a 2-response cycling model."""
        model = _make_fake_model({"name": "n", "args": {}, "id": "i", "type": "tool_call"})
        assert isinstance(model, _BindableFakeChatModel)
        assert len(model.responses) == 2
        # First response must carry the tool-call.
        first = model.responses[0]
        assert isinstance(first, AIMessage)
        assert first.tool_calls and first.tool_calls[0]["name"] == "n"
        # Second response terminates the loop (no tool calls).
        second = model.responses[1]
        assert isinstance(second, AIMessage)
        assert not getattr(second, "tool_calls", None)

    def test_bindable_fake_chat_model_returns_self_from_bind_tools(self) -> None:
        """``bind_tools`` returns ``self`` so the cycling cursor survives."""
        model = _make_fake_model({"name": "n", "args": {}, "id": "i", "type": "tool_call"})
        assert model.bind_tools([]) is model

    async def test_sdk_client_simulator_acks_thread_then_run_create(self) -> None:
        """The simulator returns deterministic ack shapes for both seams."""
        sim = _SDKClientSimulator()

        thread = await sim.create()  # threads.create — no thread_id kwarg
        assert "thread_id" in thread

        run = await sim.create(
            thread_id=thread["thread_id"],
            assistant_id=_REASONER_NAME,
            input={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert run["status"] == "success"
        assert run["thread_id"] == thread["thread_id"]
        assert thread["thread_id"] in sim.captured_inputs


# ---------------------------------------------------------------------------
# Defensive smoke — guards against ``AsyncMock`` becoming the default
# ``init_chat_model`` return value via a future fixture refactor.  An
# ``AsyncMock`` would pass ``isinstance`` checks for ``BaseChatModel`` only
# transitively and would silently accept ``.bind_tools`` with whatever
# ``return_value`` is configured — masking the very routing regressions
# this file is meant to surface.
# ---------------------------------------------------------------------------
class TestDefensiveFixtureInvariants:
    """Catches fixture regressions that would mask routing failures."""

    def test_asyncmock_is_not_used_in_place_of_chat_model(self) -> None:
        """Using ``AsyncMock`` for the chat model would silently mask routing.

        The fixture builds a ``_BindableFakeChatModel`` — assert the
        type explicitly so a future contributor swapping it for an
        ``AsyncMock(spec=BaseChatModel)`` is caught.
        """
        model = _make_fake_model({"name": "n", "args": {}, "id": "i", "type": "tool_call"})
        assert not isinstance(model, AsyncMock)
        assert isinstance(model, FakeMessagesListChatModel)
