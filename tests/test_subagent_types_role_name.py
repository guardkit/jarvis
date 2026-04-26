"""Unit tests for ``RoleName`` and ``FrontierTarget`` closed enums.

Covers TASK-J003-002 acceptance criteria:

* AC-001 — ``jarvis.agents.subagents.types.RoleName`` exposes a closed
  ``str``-valued enum with exactly three members:
  ``CRITIC = "critic"``, ``RESEARCHER = "researcher"``,
  ``PLANNER = "planner"``.
* AC-002 — ``jarvis.tools.dispatch_types.FrontierTarget`` exposes a
  closed ``str``-valued enum with exactly two members:
  ``GEMINI_3_1_PRO = "GEMINI_3_1_PRO"`` and
  ``OPUS_4_7 = "OPUS_4_7"``.
* AC-003 — Both enums inherit from ``(str, Enum)`` so
  ``@tool(parse_docstring=True)`` literal-string coercion works:
  ``Enum(value)`` round-trips and instances compare equal to their
  ``.value`` strings.
* AC-004 — ``RoleName("")`` raises ``ValueError`` (default Python enum
  behaviour) — there is no custom ``__missing__`` on either class.
* AC-005 — Importing the modules triggers no I/O and no LLM
  construction.
"""

from __future__ import annotations

import importlib
from enum import Enum
from unittest.mock import patch

import pytest

from jarvis.agents.subagents.types import RoleName
from jarvis.tools.dispatch_types import FrontierTarget


# ---------------------------------------------------------------------------
# AC-001 — RoleName has exactly three members with the documented values
# ---------------------------------------------------------------------------
class TestRoleNameMembers:
    """``RoleName`` member set + value mapping."""

    def test_role_name_inherits_from_str_and_enum(self) -> None:
        assert issubclass(RoleName, str)
        assert issubclass(RoleName, Enum)

    def test_role_name_has_exactly_three_members(self) -> None:
        assert len(list(RoleName)) == 3

    def test_role_name_member_names_are_critic_researcher_planner(self) -> None:
        assert {member.name for member in RoleName} == {
            "CRITIC",
            "RESEARCHER",
            "PLANNER",
        }

    def test_role_name_member_values_are_lowercase_strings(self) -> None:
        assert RoleName.CRITIC.value == "critic"
        assert RoleName.RESEARCHER.value == "researcher"
        assert RoleName.PLANNER.value == "planner"


# ---------------------------------------------------------------------------
# AC-002 — FrontierTarget has exactly two members with the documented values
# ---------------------------------------------------------------------------
class TestFrontierTargetMembers:
    """``FrontierTarget`` member set + value mapping."""

    def test_frontier_target_inherits_from_str_and_enum(self) -> None:
        assert issubclass(FrontierTarget, str)
        assert issubclass(FrontierTarget, Enum)

    def test_frontier_target_has_exactly_two_members(self) -> None:
        assert len(list(FrontierTarget)) == 2

    def test_frontier_target_member_names_are_gemini_and_opus(self) -> None:
        assert {member.name for member in FrontierTarget} == {
            "GEMINI_3_1_PRO",
            "OPUS_4_7",
        }

    def test_frontier_target_member_values_match_documented_strings(self) -> None:
        assert FrontierTarget.GEMINI_3_1_PRO.value == "GEMINI_3_1_PRO"
        assert FrontierTarget.OPUS_4_7.value == "OPUS_4_7"


# ---------------------------------------------------------------------------
# AC-003 — str-valued so @tool(parse_docstring=True) coercion works
# ---------------------------------------------------------------------------
class TestStrCoercionRoundTrip:
    """``Enum(value)`` round-trips and instance == value comparisons hold."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("critic", RoleName.CRITIC),
            ("researcher", RoleName.RESEARCHER),
            ("planner", RoleName.PLANNER),
        ],
    )
    def test_role_name_value_lookup_returns_member(self, value: str, expected: RoleName) -> None:
        assert RoleName(value) is expected

    @pytest.mark.parametrize(
        "member",
        list(RoleName),
    )
    def test_role_name_instance_equals_value_string(self, member: RoleName) -> None:
        assert member == member.value

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("GEMINI_3_1_PRO", FrontierTarget.GEMINI_3_1_PRO),
            ("OPUS_4_7", FrontierTarget.OPUS_4_7),
        ],
    )
    def test_frontier_target_value_lookup_returns_member(
        self, value: str, expected: FrontierTarget
    ) -> None:
        assert FrontierTarget(value) is expected

    @pytest.mark.parametrize(
        "member",
        list(FrontierTarget),
    )
    def test_frontier_target_instance_equals_value_string(self, member: FrontierTarget) -> None:
        assert member == member.value


# ---------------------------------------------------------------------------
# AC-004 — RoleName("") raises ValueError; no custom __missing__
# ---------------------------------------------------------------------------
class TestUnknownValueRaisesValueError:
    """Unknown values raise ``ValueError`` per default enum behaviour."""

    def test_role_name_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            RoleName("")

    @pytest.mark.parametrize(
        "value",
        ["", "CRITIC", "Critic", "unknown_role", "deep_reasoner"],
    )
    def test_role_name_non_member_value_raises_value_error(self, value: str) -> None:
        with pytest.raises(ValueError):
            RoleName(value)

    def test_role_name_has_no_custom_missing_override(self) -> None:
        # ``Enum.__missing__`` is the inherited one when no override is
        # declared. A custom override on the subclass would shadow it on
        # ``RoleName.__dict__`` directly.
        assert "_missing_" not in RoleName.__dict__
        assert "__missing__" not in RoleName.__dict__

    @pytest.mark.parametrize(
        "value",
        ["", "GEMINI", "gemini_3_1_pro", "opus_4_7", "claude-opus-4-7"],
    )
    def test_frontier_target_non_member_value_raises_value_error(self, value: str) -> None:
        with pytest.raises(ValueError):
            FrontierTarget(value)

    def test_frontier_target_has_no_custom_missing_override(self) -> None:
        assert "_missing_" not in FrontierTarget.__dict__
        assert "__missing__" not in FrontierTarget.__dict__


# ---------------------------------------------------------------------------
# AC-005 — No I/O, no LLM calls at import time
# ---------------------------------------------------------------------------
class TestImportPurity:
    """Re-importing the modules performs no filesystem or socket I/O."""

    def test_subagent_types_reimport_makes_no_filesystem_or_network_call(
        self,
    ) -> None:
        with (
            patch("builtins.open") as open_mock,
            patch("socket.socket") as socket_mock,
        ):
            importlib.reload(importlib.import_module("jarvis.agents.subagents.types"))
        open_mock.assert_not_called()
        socket_mock.assert_not_called()

    def test_dispatch_types_reimport_makes_no_filesystem_or_network_call(
        self,
    ) -> None:
        with (
            patch("builtins.open") as open_mock,
            patch("socket.socket") as socket_mock,
        ):
            importlib.reload(importlib.import_module("jarvis.tools.dispatch_types"))
        open_mock.assert_not_called()
        socket_mock.assert_not_called()
