"""Tests for ``jarvis.agents.subagents.prompts`` — ROLE_PROMPTS registry.

Covers TASK-J003-017 acceptance criteria for ``test_subagent_prompts.py``:

- ``ROLE_PROMPTS`` is a complete mapping over :class:`RoleName` —
  ``len == 3`` and ``set(keys) == set(RoleName)``.
- Each prompt is non-empty and at least 40 characters long.
- Each prompt contains the expected posture keyword:

  * ``RoleName.CRITIC``    → ``"adversarial"``
  * ``RoleName.RESEARCHER`` → ``"open-ended research"``
  * ``RoleName.PLANNER``    → ``"multi-step planning"``

- All assertions are structural; no LLM invocation, no
  :class:`FakeListChatModel` is required because ``ROLE_PROMPTS`` is a
  pure data registry (DDR-011 final-form prompts, no placeholders).

These tests deliberately avoid depending on internal prompt text
beyond the per-role posture keyword, so future copy refinements only
break this suite when they actually drop the contractual posture word.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

import pytest

from jarvis.agents.subagents.prompts import ROLE_PROMPTS
from jarvis.agents.subagents.types import RoleName

# ---------------------------------------------------------------------------
# Per-role posture keywords (from TASK-J003-017 AC).
# ---------------------------------------------------------------------------
_POSTURE_KEYWORDS: dict[RoleName, str] = {
    RoleName.CRITIC: "adversarial",
    RoleName.RESEARCHER: "open-ended research",
    RoleName.PLANNER: "multi-step planning",
}


# ---------------------------------------------------------------------------
# AC: ROLE_PROMPTS is a complete mapping over RoleName.
# ---------------------------------------------------------------------------
class TestRolePromptsRegistryShape:
    """ROLE_PROMPTS exhaustively covers RoleName, no missing or extra keys."""

    def test_role_prompts_is_a_mapping(self) -> None:
        assert isinstance(ROLE_PROMPTS, Mapping)

    def test_role_prompts_has_exactly_three_entries(self) -> None:
        assert len(ROLE_PROMPTS) == 3

    def test_role_prompts_keys_match_role_name_members(self) -> None:
        assert set(ROLE_PROMPTS.keys()) == set(RoleName)

    def test_role_prompts_keys_are_role_name_instances(self) -> None:
        # Pure-string keys would silently break the resolver's enum lookup.
        for key in ROLE_PROMPTS:
            assert isinstance(key, RoleName), (
                f"ROLE_PROMPTS key {key!r} is not a RoleName instance"
            )


# ---------------------------------------------------------------------------
# AC: each prompt is non-empty ≥ 40 chars.
# ---------------------------------------------------------------------------
class TestEachPromptLength:
    """Every prompt has enough room to carry a meaningful posture."""

    @pytest.mark.parametrize("role", list(RoleName))
    def test_prompt_is_non_empty_string(self, role: RoleName) -> None:
        prompt = ROLE_PROMPTS[role]
        assert isinstance(prompt, str)
        assert prompt.strip() != "", f"prompt for {role!r} is blank"

    @pytest.mark.parametrize("role", list(RoleName))
    def test_prompt_length_at_least_40_chars(self, role: RoleName) -> None:
        prompt = ROLE_PROMPTS[role]
        assert len(prompt) >= 40, (
            f"prompt for {role!r} is shorter than 40 chars: len={len(prompt)}"
        )


# ---------------------------------------------------------------------------
# AC: each prompt contains the expected posture keyword.
# ---------------------------------------------------------------------------
class TestEachPromptPostureKeyword:
    """Each prompt surfaces the role-specific posture keyword verbatim."""

    @pytest.mark.parametrize(
        ("role", "keyword"),
        list(_POSTURE_KEYWORDS.items()),
        ids=[role.value for role in _POSTURE_KEYWORDS],
    )
    def test_prompt_contains_expected_posture_keyword(
        self, role: RoleName, keyword: str
    ) -> None:
        prompt = ROLE_PROMPTS[role]
        assert keyword in prompt, (
            f"prompt for {role!r} must contain posture keyword {keyword!r}; "
            f"got prompt={prompt!r}"
        )

    def test_critic_posture_word_is_a_standalone_token(self) -> None:
        # Sanity: 'adversarial' must appear as its own word, not e.g.
        # 'adversariale' or as part of a different morpheme.
        assert (
            re.search(r"\badversarial\b", ROLE_PROMPTS[RoleName.CRITIC]) is not None
        )

    def test_researcher_posture_phrase_is_verbatim(self) -> None:
        # The phrase has a hyphen — guard against future re-wording that
        # spaces it out ('open ended research') and breaks the routing
        # contract.
        assert "open-ended research" in ROLE_PROMPTS[RoleName.RESEARCHER]

    def test_planner_posture_phrase_is_verbatim(self) -> None:
        assert "multi-step planning" in ROLE_PROMPTS[RoleName.PLANNER]


# ---------------------------------------------------------------------------
# Cross-role hygiene — each prompt's posture word does NOT leak into the
# other two prompts. Without this, a future copy edit could turn the
# registry into an indistinguishable role soup at the resolver layer.
# ---------------------------------------------------------------------------
class TestPosturesDoNotLeakAcrossRoles:
    """Per-role posture keywords stay scoped to their owning role."""

    @pytest.mark.parametrize("owner", list(_POSTURE_KEYWORDS))
    def test_posture_keyword_absent_from_other_role_prompts(
        self, owner: RoleName
    ) -> None:
        keyword = _POSTURE_KEYWORDS[owner]
        for role in RoleName:
            if role is owner:
                continue
            other_prompt = ROLE_PROMPTS[role]
            assert keyword not in other_prompt, (
                f"posture keyword {keyword!r} leaked from {owner!r} into "
                f"{role!r} prompt: {other_prompt!r}"
            )


# ---------------------------------------------------------------------------
# Side-effect free import — no LLM calls (no FakeListChatModel needed
# because the prompts module is pure data).
# ---------------------------------------------------------------------------
class TestImportIsPureData:
    """Re-importing the prompts module performs no LLM I/O."""

    def test_prompts_module_imports_without_chat_model_invocation(self) -> None:
        # The prompts module deliberately depends only on RoleName — no
        # langchain.chat_models / deepagents imports at module top. This
        # test is a structural guard: if a future refactor adds an LLM
        # dependency, this assertion fails fast.
        import importlib
        import sys

        sys.modules.pop("jarvis.agents.subagents.prompts", None)
        module = importlib.import_module("jarvis.agents.subagents.prompts")

        # The module's source must not import init_chat_model or any
        # deepagents factory — those would imply network-capable code on
        # an otherwise pure-data registry.
        from pathlib import Path

        module_file = getattr(module, "__file__", None)
        source = Path(module_file).read_text(encoding="utf-8") if module_file else ""
        assert "init_chat_model" not in source
        assert "create_deep_agent" not in source

    def test_role_prompts_re_export_via_public_path(self) -> None:
        from jarvis.agents.subagents.prompts import ROLE_PROMPTS as registry

        assert isinstance(registry, Mapping)
        assert set(registry.keys()) == set(RoleName)
