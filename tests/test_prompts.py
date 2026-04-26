"""Tests for jarvis.prompts — supervisor system prompt and test scaffolding.

Covers acceptance criteria for TASK-J001-004:
  AC-001: SUPERVISOR_SYSTEM_PROMPT importable and non-empty
  AC-002: pytest tests/ collects successfully
  AC-003: fake_llm fixture returns canned responses without network
  AC-004: test_config fixture validates cleanly (no ConfigurationError)
  AC-005: Scope invariant — no forbidden tool/subagent names in prompt
"""

from __future__ import annotations

import re
from typing import Any, ClassVar


# ---------------------------------------------------------------------------
# AC-001: SUPERVISOR_SYSTEM_PROMPT is importable and non-empty
# ---------------------------------------------------------------------------
class TestAC001SupervisorPromptImportable:
    """from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT works."""

    def test_import_from_module(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert isinstance(SUPERVISOR_SYSTEM_PROMPT, str)

    def test_import_from_package(self) -> None:
        from jarvis.prompts import SUPERVISOR_SYSTEM_PROMPT

        assert isinstance(SUPERVISOR_SYSTEM_PROMPT, str)

    def test_prompt_is_non_empty(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert len(SUPERVISOR_SYSTEM_PROMPT.strip()) > 0

    def test_prompt_is_str_type(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert type(SUPERVISOR_SYSTEM_PROMPT) is str

    def test_prompt_has_date_placeholder(self) -> None:
        """Prompt contains {date} placeholder for runtime injection."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "{date}" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_has_domain_prompt_placeholder(self) -> None:
        """Prompt contains {domain_prompt} placeholder for runtime injection."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "{domain_prompt}" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_format_resolves_without_error(self) -> None:
        """str.format() with all three placeholders does not raise KeyError."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        result = SUPERVISOR_SYSTEM_PROMPT.format(
            date="2026-04-21",
            available_capabilities="No capabilities currently registered.",
            domain_prompt="Test domain guidelines.",
        )
        assert "2026-04-21" in result
        assert "No capabilities currently registered." in result
        assert "Test domain guidelines." in result
        assert "{date}" not in result
        assert "{available_capabilities}" not in result
        assert "{domain_prompt}" not in result

    def test_prompt_mentions_jarvis(self) -> None:
        """Prompt identifies the agent as Jarvis."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "Jarvis" in SUPERVISOR_SYSTEM_PROMPT

    def test_prompt_states_attended_conversation_posture(self) -> None:
        """Prompt explicitly states the attended-conversation posture."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "attended" in lower or "conversation with a human" in lower

    def test_prompt_states_cheapest_that_fits(self) -> None:
        """Prompt mentions cheapest-that-fits / escalate on need philosophy."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "cheapest" in lower or "escalate" in lower

    def test_package_all_includes_prompt(self) -> None:
        """__all__ in prompts/__init__.py includes SUPERVISOR_SYSTEM_PROMPT."""
        import jarvis.prompts as prompts_pkg

        assert "SUPERVISOR_SYSTEM_PROMPT" in prompts_pkg.__all__


# ---------------------------------------------------------------------------
# TASK-J002-016 — Tool-Usage section + {available_capabilities} placeholder
# ---------------------------------------------------------------------------
class TestJ002016AvailableCapabilitiesPlaceholder:
    """TASK-J002-016 AC-001 / AC-004 — placeholder location and ordering."""

    def test_prompt_has_available_capabilities_placeholder(self) -> None:
        """SUPERVISOR_SYSTEM_PROMPT contains the {available_capabilities} placeholder."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "{available_capabilities}" in SUPERVISOR_SYSTEM_PROMPT

    def test_placeholder_after_attended_conversation(self) -> None:
        """{available_capabilities} appears after the Attended-Conversation section."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        attended_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Attended-Conversation Posture")
        placeholder_idx = SUPERVISOR_SYSTEM_PROMPT.index("{available_capabilities}")
        assert attended_idx < placeholder_idx

    def test_placeholder_before_trace_richness(self) -> None:
        """{available_capabilities} appears before the Trace Richness section."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        placeholder_idx = SUPERVISOR_SYSTEM_PROMPT.index("{available_capabilities}")
        trace_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Trace Richness")
        assert placeholder_idx < trace_idx

    def test_available_capabilities_section_heading_present(self) -> None:
        """The capability catalogue is introduced by a markdown heading."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "## Available Capabilities" in SUPERVISOR_SYSTEM_PROMPT

    def test_domain_prompt_placeholder_remains_at_bottom(self) -> None:
        """AC-004 — {domain_prompt} stays at the very bottom of the prompt."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        domain_idx = SUPERVISOR_SYSTEM_PROMPT.index("{domain_prompt}")
        # No other section heading may appear after the domain prompt.
        assert "##" not in SUPERVISOR_SYSTEM_PROMPT[domain_idx:]
        # And the domain prompt is preceded by its own heading.
        assert "## Domain-Specific Instructions" in SUPERVISOR_SYSTEM_PROMPT
        heading_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Domain-Specific Instructions")
        assert heading_idx < domain_idx


class TestJ002016ToolUsageSection:
    """TASK-J002-016 AC-002 — Tool Usage preference list from design §10."""

    def test_tool_usage_section_present(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "## Tool Usage" in SUPERVISOR_SYSTEM_PROMPT

    def test_tool_usage_after_attended_conversation(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        attended_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Attended-Conversation Posture")
        tool_usage_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Tool Usage")
        assert attended_idx < tool_usage_idx

    def test_tool_usage_before_trace_richness(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        tool_usage_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Tool Usage")
        trace_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Trace Richness")
        assert tool_usage_idx < trace_idx

    def test_tool_usage_mentions_calculate(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "calculate" in SUPERVISOR_SYSTEM_PROMPT
        # Preference statement: prefer calculate over mental arithmetic
        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "mental arithmetic" in lower

    def test_tool_usage_mentions_list_available_capabilities_once_per_session(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "list_available_capabilities" in SUPERVISOR_SYSTEM_PROMPT
        assert "once per session" in SUPERVISOR_SYSTEM_PROMPT.lower()

    def test_tool_usage_mentions_dispatch_by_capability(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "dispatch_by_capability" in SUPERVISOR_SYSTEM_PROMPT

    def test_tool_usage_mentions_queue_build_with_explicit_naming(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "queue_build" in SUPERVISOR_SYSTEM_PROMPT
        # The preference list scopes queue_build to the explicit-feature case.
        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "explicitly" in lower

    def test_tool_usage_mentions_structured_error_passthrough(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "structured-error" in lower or "structured error" in lower
        assert "as-is" in lower or "as is" in lower


class TestJ002016Phase1ScopePreserved:
    """TASK-J002-016 AC-003 — Phase 1 content preserved verbatim."""

    PHASE1_IDENTITY_LINES: ClassVar[list[str]] = [
        "## Identity",
        "- You are conversational, concise, and direct.",
        "- You prefer clarity over verbosity.",
        "- When uncertain, you say so and ask for guidance rather than guessing.",
    ]

    PHASE1_ATTENDED_LINES: ClassVar[list[str]] = [
        "## Attended-Conversation Posture",
        "You are **always** in a conversation with a human.",
        "- For quick questions, give quick answers.",
        "- For complex requests, think step-by-step and show your reasoning.",
    ]

    PHASE1_MODEL_SELECTION_LINES: ClassVar[list[str]] = [
        "## Model-Selection Philosophy",
        "Follow the principle of **cheapest-that-fits, escalate on need**:",
        "- Start with the least expensive reasoning approach that can handle the request.",
        "- If the current approach is insufficient, escalate to a more capable one.",
    ]

    def test_identity_section_preserved_verbatim(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        for line in self.PHASE1_IDENTITY_LINES:
            assert line in SUPERVISOR_SYSTEM_PROMPT, f"Phase 1 Identity line missing: {line!r}"

    def test_attended_conversation_section_preserved_verbatim(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        for line in self.PHASE1_ATTENDED_LINES:
            assert line in SUPERVISOR_SYSTEM_PROMPT, (
                f"Phase 1 Attended-Conversation line missing: {line!r}"
            )

    def test_model_selection_philosophy_preserved_verbatim(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        for line in self.PHASE1_MODEL_SELECTION_LINES:
            assert line in SUPERVISOR_SYSTEM_PROMPT, (
                f"Phase 1 Model-Selection line missing: {line!r}"
            )

    def test_no_call_specialist_reference(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "call_specialist" not in SUPERVISOR_SYSTEM_PROMPT.lower()

    def test_no_start_async_task_reference(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "start_async_task" not in SUPERVISOR_SYSTEM_PROMPT.lower()

    def test_no_morning_briefing_reference(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "morning-briefing" not in lower
        assert "morning_briefing" not in lower

    def test_no_named_subagents(self) -> None:
        """No mention of orchestrator-template subagent role names.

        FEAT-JARVIS-003 introduces the ``jarvis-reasoner`` async subagent
        per ADR-ARCH-011, so that name is no longer forbidden in this
        prompt.  The orchestrator-template names ``implementer``,
        ``evaluator`` and ``builder`` remain forbidden — they belong to a
        different agent topology.
        """
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        for name in ["implementer", "evaluator", "builder"]:
            assert name not in lower, f"Forbidden subagent name leaked: {name!r}"

    def test_no_skill_references(self) -> None:
        """No mention of named skills (skills land via FEAT-JARVIS-007)."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        for skill in ["talk_prep", "morning-briefing", "morning_briefing"]:
            assert skill not in lower, f"Forbidden skill name leaked: {skill!r}"


class TestJ002016BuildSupervisorFormatCompat:
    """TASK-J002-016 AC-005 — adding the placeholder doesn't break callers.

    The Phase 1 ``build_supervisor`` factory passes ``date`` and
    ``domain_prompt`` to ``SUPERVISOR_SYSTEM_PROMPT.format(...)``; once we add
    a third placeholder it must also supply ``available_capabilities`` (or the
    format call would raise ``KeyError``).  Verify the factory module ships a
    safe default.
    """

    def test_supervisor_module_exposes_default_capabilities(self) -> None:
        from jarvis.agents import supervisor as supervisor_mod

        assert hasattr(supervisor_mod, "_DEFAULT_AVAILABLE_CAPABILITIES")
        assert isinstance(supervisor_mod._DEFAULT_AVAILABLE_CAPABILITIES, str)
        assert supervisor_mod._DEFAULT_AVAILABLE_CAPABILITIES.strip() != ""


# ---------------------------------------------------------------------------
# AC-003: fake_llm fixture returns canned responses (no network)
# ---------------------------------------------------------------------------
class TestAC003FakeLlm:
    """fake_llm fixture is callable and returns canned responses."""

    def test_fake_llm_is_not_none(self, fake_llm: Any) -> None:
        assert fake_llm is not None

    def test_fake_llm_invoke_returns_canned_response(self, fake_llm: Any) -> None:
        result = fake_llm.invoke("Hello")
        assert hasattr(result, "content")
        assert result.content == "Canned response 1"

    def test_fake_llm_second_invoke_returns_next_response(self, fake_llm: Any) -> None:
        first = fake_llm.invoke("First")
        second = fake_llm.invoke("Second")
        assert first.content == "Canned response 1"
        assert second.content == "Canned response 2"

    def test_fake_llm_is_base_chat_model(self, fake_llm: Any) -> None:
        from langchain_core.language_models.chat_models import BaseChatModel

        assert isinstance(fake_llm, BaseChatModel)


# ---------------------------------------------------------------------------
# AC-005: Scope invariant — no forbidden terms in the supervisor prompt
# ---------------------------------------------------------------------------
class TestAC005ScopeInvariant:
    """No mention of tools or subagent names that do not exist yet."""

    # FEAT-JARVIS-002 brings ``queue_build`` and ``dispatch_by_capability`` into
    # scope (design §10), so they are *not* forbidden any more.  The terms below
    # remain forbidden — they belong to FEAT-JARVIS-003 (subagent routing) and
    # FEAT-JARVIS-007 (skills) and have not yet landed.
    FORBIDDEN_TERMS: ClassVar[list[str]] = [
        "call_specialist",
        "start_async_task",
        "morning-briefing",
        "morning_briefing",
        "talk_prep",
    ]

    def test_no_forbidden_terms_in_prompt(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        for term in self.FORBIDDEN_TERMS:
            assert term.lower() not in lower, (
                f"Forbidden term '{term}' found in SUPERVISOR_SYSTEM_PROMPT"
            )

    def test_no_task_as_tool_reference_in_prompt(self) -> None:
        """The word 'task' as a tool/subagent name must not appear.

        We check for patterns like ``task(`` or ``"task"`` that would indicate
        a tool reference, while allowing the general word 'task' in prose.
        """
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        # Check for tool-like references: task(, "task", 'task'
        assert "task(" not in SUPERVISOR_SYSTEM_PROMPT.lower()
        # Check there are no subagent-named references like subagent_name="task"
        assert re.search(r'subagent.*["\']task["\']', SUPERVISOR_SYSTEM_PROMPT.lower()) is None

    def test_no_subagent_names_in_prompt(self) -> None:
        """No orchestrator-template subagent names in the supervisor prompt.

        FEAT-JARVIS-003 makes ``jarvis-reasoner`` a first-class member of
        the supervisor prompt (TASK-J003-014 ``## Subagent Routing``
        section), so it is no longer forbidden.  The
        ``implementer``/``evaluator``/``builder`` triple from the
        ``langchain-deepagents-orchestrator`` template remains forbidden.
        """
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        for name in ["implementer", "evaluator", "builder"]:
            assert name not in lower, f"Subagent name '{name}' found in SUPERVISOR_SYSTEM_PROMPT"


# ---------------------------------------------------------------------------
# AC-004: test_config fixture validates cleanly (no ConfigurationError)
# ---------------------------------------------------------------------------
class TestAC004TestConfigFixture:
    """test_config fixture provides a JarvisConfig that validates cleanly."""

    def test_test_config_is_not_none(self, test_config: Any) -> None:
        assert test_config is not None

    def test_test_config_is_jarvis_config(self, test_config: Any) -> None:
        from jarvis.config.settings import JarvisConfig

        assert isinstance(test_config, JarvisConfig)

    def test_test_config_has_openai_base_url(self, test_config: Any) -> None:
        assert test_config.openai_base_url == "http://fake-endpoint/v1"

    def test_test_config_default_log_level(self, test_config: Any) -> None:
        assert test_config.log_level == "INFO"

    def test_test_config_default_supervisor_model(self, test_config: Any) -> None:
        assert test_config.supervisor_model == "openai:jarvis-reasoner"

    def test_test_config_default_memory_backend(self, test_config: Any) -> None:
        assert test_config.memory_store_backend == "in_memory"

    def test_test_config_validate_provider_keys_succeeds(self, test_config: Any) -> None:
        """Calling validate_provider_keys() a second time still succeeds."""
        test_config.validate_provider_keys()  # Should not raise


# ---------------------------------------------------------------------------
# AC-002: pytest collection works — this file existing and being collected
# is itself evidence.  Add an explicit meta-test.
# ---------------------------------------------------------------------------
class TestAC002PytestCollection:
    """pytest tests/ collects successfully."""

    def test_collection_works(self) -> None:
        """If this test runs, pytest collection succeeded."""
        assert True

    def test_conftest_fixtures_are_discoverable(self, fake_llm: Any) -> None:
        """Fixtures from conftest.py are discoverable by pytest."""
        assert fake_llm is not None


# ---------------------------------------------------------------------------
# InMemoryStore fixture smoke test
# ---------------------------------------------------------------------------
class TestInMemoryStoreFixture:
    """in_memory_store fixture provides a fresh store."""

    def test_in_memory_store_is_not_none(self, in_memory_store: Any) -> None:
        assert in_memory_store is not None

    def test_in_memory_store_is_langgraph_store(self, in_memory_store: Any) -> None:
        from langgraph.store.memory import InMemoryStore

        assert isinstance(in_memory_store, InMemoryStore)


# ---------------------------------------------------------------------------
# app_state fixture smoke test
# ---------------------------------------------------------------------------
class TestAppStateFixture:
    """app_state fixture provides a placeholder dict."""

    def test_app_state_is_dict(self, app_state: dict[str, Any]) -> None:
        assert isinstance(app_state, dict)

    def test_app_state_has_config_key(self, app_state: dict[str, Any]) -> None:
        assert "config" in app_state

    def test_app_state_has_store_key(self, app_state: dict[str, Any]) -> None:
        assert "store" in app_state


# ---------------------------------------------------------------------------
# TASK-J003-014 — ## Subagent Routing section
# ---------------------------------------------------------------------------
class TestJ003014SubagentRoutingSection:
    """TASK-J003-014 AC-001 — Subagent Routing section content invariants."""

    def test_subagent_routing_section_present(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "## Subagent Routing" in SUPERVISOR_SYSTEM_PROMPT

    def test_subagent_routing_after_tool_usage(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        tool_usage_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Tool Usage")
        routing_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Subagent Routing")
        assert tool_usage_idx < routing_idx

    def test_subagent_routing_before_model_selection(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        routing_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Subagent Routing")
        model_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Model-Selection Philosophy")
        assert routing_idx < model_idx

    def test_subagent_routing_names_jarvis_reasoner_verbatim(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "jarvis-reasoner" in SUPERVISOR_SYSTEM_PROMPT

    def test_subagent_routing_states_local_gpt_oss_120b(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "gpt-oss-120b" in SUPERVISOR_SYSTEM_PROMPT
        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "locally" in lower or "local" in lower

    def test_subagent_routing_lists_three_role_modes(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        for role in ("critic", "researcher", "planner"):
            assert role in SUPERVISOR_SYSTEM_PROMPT, f"Role '{role}' missing"

    def test_subagent_routing_describes_role_postures(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "adversarial" in lower
        # researcher posture — open-ended / investigation
        assert "open-ended" in lower or "investigation" in lower
        # planner posture — multi-step / decompose
        assert "multi-step" in lower or "decompose" in lower

    def test_subagent_routing_warns_against_arithmetic_lookups_files(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "arithmetic" in lower
        assert "lookups" in lower or "lookup" in lower
        assert "file reads" in lower or "file read" in lower

    def test_subagent_routing_mentions_llamaswap_cold_warm_ack(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "llama-swap" in lower
        assert "cold-warm" in lower or ("cold" in lower and "warm" in lower)
        assert "acknowledge" in lower or "ack" in lower


# ---------------------------------------------------------------------------
# TASK-J003-014 — ## Frontier Escalation section
# ---------------------------------------------------------------------------
class TestJ003014FrontierEscalationSection:
    """TASK-J003-014 AC-002 — Frontier Escalation section content invariants."""

    def test_frontier_escalation_section_present(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "## Frontier Escalation" in SUPERVISOR_SYSTEM_PROMPT

    def test_frontier_escalation_after_subagent_routing(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        routing_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Subagent Routing")
        frontier_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Frontier Escalation")
        assert routing_idx < frontier_idx

    def test_frontier_escalation_before_model_selection(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        frontier_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Frontier Escalation")
        model_idx = SUPERVISOR_SYSTEM_PROMPT.index("## Model-Selection Philosophy")
        assert frontier_idx < model_idx

    def test_frontier_escalation_names_tool_verbatim(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "escalate_to_frontier" in SUPERVISOR_SYSTEM_PROMPT

    def test_frontier_escalation_requires_explicit_rich_request(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "Rich" in SUPERVISOR_SYSTEM_PROMPT
        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "explicitly" in lower

    def test_frontier_escalation_lists_trigger_phrases(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "ask gemini" in lower
        assert "frontier opinion" in lower
        assert "cloud model" in lower

    def test_frontier_escalation_states_not_default_path(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "not" in lower and "default" in lower

    def test_frontier_escalation_refuses_ambient_learning(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "refuse" in lower or "reject" in lower
        assert "ambient" in lower
        assert "learning" in lower

    def test_frontier_escalation_default_target_gemini_3_1_pro(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "Gemini 3.1 Pro" in SUPERVISOR_SYSTEM_PROMPT

    def test_frontier_escalation_opus_target_for_adversarial_critique(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert "OPUS_4_7" in SUPERVISOR_SYSTEM_PROMPT
        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "adversarial" in lower

    def test_frontier_escalation_states_budget_envelope(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        # Allow either the en-dash (U+2013) or a plain hyphen between the
        # bounds, but require both numeric endpoints and the £ symbol.
        assert "£20" in SUPERVISOR_SYSTEM_PROMPT
        assert "£50" in SUPERVISOR_SYSTEM_PROMPT or "50" in SUPERVISOR_SYSTEM_PROMPT
        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        assert "month" in lower
        assert "fleet-wide" in lower or "fleet wide" in lower


# ---------------------------------------------------------------------------
# TASK-J003-014 AC-003 — additive: Phase 1 + FEAT-J002 content unchanged above
# the insertion point.
# ---------------------------------------------------------------------------
class TestJ003014AdditiveAboveInsertionPoint:
    """The two new sections are appended after ``## Tool Usage``; everything
    above that insertion point must be byte-for-byte identical to the
    pre-FEAT-J003 prompt.
    """

    # Pre-FEAT-J003 substring of SUPERVISOR_SYSTEM_PROMPT, ending at the close
    # of the FEAT-J002 ``## Tool Usage`` section.  Built via concatenation so
    # this test reads as a literal byte-for-byte assertion.
    PRE_J003_HEAD: ClassVar[str] = (
        "You are **Jarvis** — a general-purpose reasoning agent built on the DeepAgents\n"
        "framework.  You operate as an attended conversation partner: there is always a\n"
        "human on the other side of this interaction, and your primary job is to help\n"
        "them think, decide, and act effectively.\n\n"
        "Today's date: {date}\n\n"
        "## Identity\n\n"
        "- You are conversational, concise, and direct.\n"
        "- You prefer clarity over verbosity.\n"
        "- When uncertain, you say so and ask for guidance rather than guessing.\n\n"
        "## Attended-Conversation Posture\n\n"
        "You are **always** in a conversation with a human.  Every response you produce\n"
        "will be read by a person.  Adjust your tone, length, and level of detail to\n"
        "what serves them best in the moment.\n\n"
        "- For quick questions, give quick answers.\n"
        "- For complex requests, think step-by-step and show your reasoning.\n"
        "- Never produce output intended only for machine consumption unless explicitly\n"
        "  asked.\n\n"
        "## Available Capabilities\n\n"
        "The following capabilities are registered for this session.  This list is\n"
        "authoritative — prefer it over re-discovering the catalogue at runtime.\n\n"
        "{available_capabilities}\n\n"
        "## Tool Usage\n\n"
        "Follow these preferences when selecting and invoking tools:\n\n"
        "- Prefer the `calculate` tool over mental arithmetic for any non-trivial\n"
        "  numeric work.\n"
        "- Call `list_available_capabilities` at most once per session — the catalogue\n"
        "  injected above is authoritative for the rest of the conversation.\n"
        "- Prefer `dispatch_by_capability` over repeating specialist work in-process\n"
        "  when the request matches a registered capability.\n"
        "- Use `queue_build` only when the user's request explicitly names a feature\n"
        "  to build.\n"
        "- When a tool returns a structured-error string, return it to the user as-is\n"
        "  rather than re-invoking the same tool on the failure.\n\n"
    )

    def test_pre_j003_head_byte_for_byte_unchanged(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert SUPERVISOR_SYSTEM_PROMPT.startswith(self.PRE_J003_HEAD), (
            "Phase 1 + FEAT-J002 head of SUPERVISOR_SYSTEM_PROMPT was modified; "
            "TASK-J003-014 must be additive only."
        )

    def test_subagent_routing_immediately_follows_tool_usage(self) -> None:
        """``## Subagent Routing`` is the first new section after ``## Tool Usage``."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        assert SUPERVISOR_SYSTEM_PROMPT.startswith(self.PRE_J003_HEAD)
        tail = SUPERVISOR_SYSTEM_PROMPT[len(self.PRE_J003_HEAD) :]
        assert tail.startswith("## Subagent Routing"), (
            f"Expected ## Subagent Routing immediately after ## Tool Usage, got: {tail[:80]!r}"
        )


# ---------------------------------------------------------------------------
# TASK-J003-014 AC-004 + AC-005 — retired roster + cloud-fallback language gone
# ---------------------------------------------------------------------------
class TestJ003014RetiredRosterAbsent:
    """No mention of the four-roster names superseded by ADR-ARCH-011."""

    RETIRED_ROSTER_NAMES: ClassVar[list[str]] = [
        "deep_reasoner",
        "adversarial_critic",
        "long_research",
        "quick_local",
    ]

    def test_no_retired_roster_names(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        for name in self.RETIRED_ROSTER_NAMES:
            assert name not in lower, (
                f"Retired roster name '{name}' must not appear in SUPERVISOR_SYSTEM_PROMPT"
            )

    def test_no_cloud_fallback_for_quick_local_language(self) -> None:
        """No cloud-fallback-for-quick_local phrasing."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        # The retired phrases from JA6 cloud-fallback design.
        forbidden_phrases = [
            "vllm fallback",
            "gemini-flash-latest",
            "cloud cheap-tier",
            "fallback to cloud",
            "quick_local fallback",
        ]
        for phrase in forbidden_phrases:
            assert phrase not in lower, f"Retired cloud-fallback phrase leaked: {phrase!r}"


# ---------------------------------------------------------------------------
# TASK-J003-014 AC-006 — rendered prompt for a new session includes both
# new sections verbatim.
# ---------------------------------------------------------------------------
class TestJ003014RenderedPromptIncludesNewSections:
    """Format-time render must preserve both new section headers verbatim."""

    def test_rendered_prompt_contains_subagent_routing_heading(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        rendered = SUPERVISOR_SYSTEM_PROMPT.format(
            date="2026-04-26",
            available_capabilities="No capabilities currently registered.",
            domain_prompt="Test domain.",
        )
        assert "## Subagent Routing" in rendered

    def test_rendered_prompt_contains_frontier_escalation_heading(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        rendered = SUPERVISOR_SYSTEM_PROMPT.format(
            date="2026-04-26",
            available_capabilities="No capabilities currently registered.",
            domain_prompt="Test domain.",
        )
        assert "## Frontier Escalation" in rendered

    def test_rendered_prompt_keeps_jarvis_reasoner_token(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        rendered = SUPERVISOR_SYSTEM_PROMPT.format(
            date="2026-04-26",
            available_capabilities="No capabilities currently registered.",
            domain_prompt="Test domain.",
        )
        assert "jarvis-reasoner" in rendered

    def test_rendered_prompt_keeps_escalate_to_frontier_token(self) -> None:
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        rendered = SUPERVISOR_SYSTEM_PROMPT.format(
            date="2026-04-26",
            available_capabilities="No capabilities currently registered.",
            domain_prompt="Test domain.",
        )
        assert "escalate_to_frontier" in rendered

    def test_build_supervisor_renders_new_sections(self, test_config: Any) -> None:
        """The full build_supervisor pipeline emits both new sections."""
        from unittest.mock import patch

        captured: dict[str, str] = {}

        def fake_create_deep_agent(**kwargs: Any) -> Any:
            captured["system_prompt"] = kwargs["system_prompt"]
            from unittest.mock import MagicMock

            return MagicMock()

        with (
            patch(
                "jarvis.agents.supervisor.create_deep_agent",
                side_effect=fake_create_deep_agent,
            ),
            patch("jarvis.agents.supervisor.init_chat_model"),
        ):
            from jarvis.agents.supervisor import build_supervisor

            build_supervisor(test_config)

        assert "## Subagent Routing" in captured["system_prompt"]
        assert "## Frontier Escalation" in captured["system_prompt"]
        assert "jarvis-reasoner" in captured["system_prompt"]
        assert "escalate_to_frontier" in captured["system_prompt"]
