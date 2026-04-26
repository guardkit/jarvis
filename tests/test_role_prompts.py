"""Tests for jarvis.agents.subagents.prompts — role-prompt registry.

Covers acceptance criteria for TASK-J003-005:
  AC-001: Module defines CRITIC_PROMPT, RESEARCHER_PROMPT, PLANNER_PROMPT
  AC-002: CRITIC_PROMPT contains the verbatim word "adversarial"
  AC-003: RESEARCHER_PROMPT contains the verbatim phrase "open-ended research"
  AC-004: PLANNER_PROMPT contains the verbatim phrase "multi-step planning"
  AC-005: ROLE_PROMPTS: Mapping[RoleName, str] has exactly one entry per RoleName
  AC-006: Each prompt is non-empty, >= 40 chars, no concrete tool names
  AC-007: Prompts are plain strings with no {placeholders}
  AC-008: Importing the module is side-effect free (no I/O, no LLM calls)
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from jarvis.agents.subagents.prompts import (
    CRITIC_PROMPT,
    PLANNER_PROMPT,
    RESEARCHER_PROMPT,
    ROLE_PROMPTS,
)
from jarvis.agents.subagents.types import RoleName


# ---------------------------------------------------------------------------
# AC-001: Module defines three module-level string constants
# ---------------------------------------------------------------------------
class TestAC001ConstantsExist:
    """The three role-prompt constants are importable and are str."""

    def test_critic_prompt_is_str(self) -> None:
        assert isinstance(CRITIC_PROMPT, str)

    def test_researcher_prompt_is_str(self) -> None:
        assert isinstance(RESEARCHER_PROMPT, str)

    def test_planner_prompt_is_str(self) -> None:
        assert isinstance(PLANNER_PROMPT, str)

    def test_constants_are_module_level(self) -> None:
        from jarvis.agents.subagents import prompts as prompts_module

        for name in ("CRITIC_PROMPT", "RESEARCHER_PROMPT", "PLANNER_PROMPT"):
            assert hasattr(prompts_module, name)
            assert isinstance(getattr(prompts_module, name), str)


# ---------------------------------------------------------------------------
# AC-002: CRITIC_PROMPT — adversarial-evaluation posture, "adversarial" verbatim
# ---------------------------------------------------------------------------
class TestAC002CriticPromptAdversarial:
    """The literal word 'adversarial' appears in CRITIC_PROMPT."""

    def test_contains_word_adversarial_verbatim(self) -> None:
        assert "adversarial" in CRITIC_PROMPT

    def test_word_adversarial_is_lowercase_token(self) -> None:
        # Must appear as a standalone word, not e.g. "Adversarialize".
        assert re.search(r"\badversarial\b", CRITIC_PROMPT) is not None


# ---------------------------------------------------------------------------
# AC-003: RESEARCHER_PROMPT — open-ended research posture, phrase verbatim
# ---------------------------------------------------------------------------
class TestAC003ResearcherPromptOpenEnded:
    """The phrase 'open-ended research' appears verbatim in RESEARCHER_PROMPT."""

    def test_contains_phrase_open_ended_research_verbatim(self) -> None:
        assert "open-ended research" in RESEARCHER_PROMPT


# ---------------------------------------------------------------------------
# AC-004: PLANNER_PROMPT — multi-step planning posture, phrase verbatim
# ---------------------------------------------------------------------------
class TestAC004PlannerPromptMultiStep:
    """The phrase 'multi-step planning' appears verbatim in PLANNER_PROMPT."""

    def test_contains_phrase_multi_step_planning_verbatim(self) -> None:
        assert "multi-step planning" in PLANNER_PROMPT


# ---------------------------------------------------------------------------
# AC-005: ROLE_PROMPTS exhaustively covers RoleName, no extra keys
# ---------------------------------------------------------------------------
class TestAC005RolePromptsRegistryShape:
    """ROLE_PROMPTS keys match RoleName members exactly — no missing, no extras."""

    def test_role_prompts_is_mapping(self) -> None:
        assert isinstance(ROLE_PROMPTS, Mapping)

    def test_role_prompts_has_exactly_three_entries(self) -> None:
        assert len(ROLE_PROMPTS) == 3

    def test_role_prompts_keys_match_role_name_members(self) -> None:
        assert set(ROLE_PROMPTS.keys()) == set(RoleName)

    def test_role_prompts_no_extra_keys(self) -> None:
        # No string key sneaking past the RoleName contract.
        for key in ROLE_PROMPTS:
            assert isinstance(key, RoleName)

    def test_role_prompts_values_are_str(self) -> None:
        for value in ROLE_PROMPTS.values():
            assert isinstance(value, str)

    def test_role_prompts_critic_value_is_critic_prompt(self) -> None:
        assert ROLE_PROMPTS[RoleName.CRITIC] is CRITIC_PROMPT

    def test_role_prompts_researcher_value_is_researcher_prompt(self) -> None:
        assert ROLE_PROMPTS[RoleName.RESEARCHER] is RESEARCHER_PROMPT

    def test_role_prompts_planner_value_is_planner_prompt(self) -> None:
        assert ROLE_PROMPTS[RoleName.PLANNER] is PLANNER_PROMPT


# ---------------------------------------------------------------------------
# AC-006: Each prompt is non-empty, >= 40 chars, no concrete tool names
# ---------------------------------------------------------------------------
class TestAC006PromptLengthAndPosture:
    """Each prompt carries enough role posture but does not prescribe tools."""

    PROMPTS: tuple[tuple[str, str], ...] = (
        ("CRITIC_PROMPT", CRITIC_PROMPT),
        ("RESEARCHER_PROMPT", RESEARCHER_PROMPT),
        ("PLANNER_PROMPT", PLANNER_PROMPT),
    )

    # Tool names declared by the supervisor / capability registry. The
    # reasoner subagent is leaf per design §8 and must not prescribe these.
    FORBIDDEN_TOOL_NAMES: tuple[str, ...] = (
        "read_file",
        "search_web",
        "calculate",
        "list_available_capabilities",
        "refresh_capabilities",
        "subscribe_capabilities",
        "dispatch_by_capability",
        "start_async_task",
        "escalate_to_frontier",
    )

    def test_all_prompts_non_empty(self) -> None:
        for name, prompt in self.PROMPTS:
            assert prompt.strip(), f"{name} is empty"

    def test_all_prompts_at_least_40_chars(self) -> None:
        for name, prompt in self.PROMPTS:
            assert len(prompt) >= 40, f"{name} is shorter than 40 chars: {len(prompt)}"

    def test_no_prompt_prescribes_a_concrete_tool_name(self) -> None:
        for name, prompt in self.PROMPTS:
            for tool in self.FORBIDDEN_TOOL_NAMES:
                assert tool not in prompt, (
                    f"{name} mentions concrete tool '{tool}' — "
                    "the reasoner subagent is leaf per design §8"
                )


# ---------------------------------------------------------------------------
# AC-007: Prompts are plain strings — no {placeholders}
# ---------------------------------------------------------------------------
class TestAC007NoFormatPlaceholders:
    """Prompts must be final, not templates — no str.format() placeholders."""

    PLACEHOLDER_RE: re.Pattern[str] = re.compile(r"\{[^{}]*\}")

    def test_critic_prompt_has_no_placeholders(self) -> None:
        assert self.PLACEHOLDER_RE.search(CRITIC_PROMPT) is None

    def test_researcher_prompt_has_no_placeholders(self) -> None:
        assert self.PLACEHOLDER_RE.search(RESEARCHER_PROMPT) is None

    def test_planner_prompt_has_no_placeholders(self) -> None:
        assert self.PLACEHOLDER_RE.search(PLANNER_PROMPT) is None

    def test_role_prompts_values_have_no_placeholders(self) -> None:
        for role, value in ROLE_PROMPTS.items():
            assert self.PLACEHOLDER_RE.search(value) is None, (
                f"ROLE_PROMPTS[{role!r}] contains a {{placeholder}}"
            )


# ---------------------------------------------------------------------------
# AC-008: Importing the module is side-effect free — no I/O, no LLM calls
# ---------------------------------------------------------------------------
class TestAC008ImportIsSideEffectFree:
    """Re-importing the module performs no I/O, no LLM calls, no network."""

    def test_reimport_does_not_perform_io(
        self,
        monkeypatch: object,  # pytest fixture, type erased to avoid extra imports
    ) -> None:
        import builtins
        import importlib
        import sys

        # Forbid filesystem opens during the (re)import.
        original_open = builtins.open
        opened_paths: list[str] = []

        def _tracking_open(*args: object, **kwargs: object) -> object:
            if args:
                opened_paths.append(str(args[0]))
            return original_open(*args, **kwargs)  # type: ignore[arg-type]

        builtins.open = _tracking_open  # type: ignore[assignment]
        try:
            # Force a true reimport so module-body side effects (if any)
            # would re-fire and any forbidden open() would be observed.
            sys.modules.pop("jarvis.agents.subagents.prompts", None)
            module = importlib.import_module("jarvis.agents.subagents.prompts")
        finally:
            builtins.open = original_open  # type: ignore[assignment]

        assert hasattr(module, "ROLE_PROMPTS")
        # The prompts module itself must not have triggered any open() —
        # standard-library imports legitimately may, so we filter to
        # paths that look like project- or runtime-data files.
        suspicious = [p for p in opened_paths if p.endswith((".md", ".yaml", ".yml", ".json"))]
        assert suspicious == [], f"Module import opened data files: {suspicious}"

    def test_role_prompts_importable_via_documented_path(self) -> None:
        # AC-008 uses this exact import path verbatim.
        from jarvis.agents.subagents.prompts import ROLE_PROMPTS as registry

        assert isinstance(registry, Mapping)
        assert len(registry) == 3
