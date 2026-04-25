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
        """No specific subagent names (jarvis-reasoner, implementer, evaluator, builder)."""
        from jarvis.prompts.supervisor_prompt import SUPERVISOR_SYSTEM_PROMPT

        lower = SUPERVISOR_SYSTEM_PROMPT.lower()
        # These are subagent role names from the template — should not be in supervisor prompt
        for name in ["jarvis-reasoner", "implementer", "evaluator", "builder"]:
            assert name not in lower, (
                f"Subagent name '{name}' found in SUPERVISOR_SYSTEM_PROMPT"
            )


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
