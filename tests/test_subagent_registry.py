"""Tests for ``jarvis.agents.subagent_registry`` — AsyncSubAgent factory.

Covers TASK-J003-009 acceptance criteria:

- AC-001 — ``build_async_subagents(config) -> list[AsyncSubAgent]`` is exposed.
- AC-002 — returns a list of *exactly one* element.
- AC-003 — element fields: ``name == "jarvis-reasoner"``,
  ``graph_id == "jarvis_reasoner"``, ``description`` non-empty.
- AC-004 — description contains all routing-signal substrings
  (``gpt-oss-120b``, ``on the premises``, ``sub-second``,
  ``two to four minutes``, ``critic``, ``researcher``, ``planner``).
- AC-005 — description does NOT mention any of the four-roster
  legacy names or cloud-tier promises (deep_reasoner,
  adversarial_critic, long_research, quick_local, cloud).
- AC-006 — ``AsyncSubAgent`` is imported from ``deepagents``; no
  redefinition.
- AC-007 — function is pure / deterministic — same config →
  identical description text on repeat calls.
- AC-008 — ``jarvis.agents.subagents`` re-exports the
  ``jarvis_reasoner`` ``graph`` symbol so ``langgraph.json`` can bind
  ``jarvis_reasoner`` by module path.
- AC-009 — no LLM calls; no I/O beyond reading config.

Tests deliberately do not invoke the inner reasoner graph — only the
spec dict produced by ``build_async_subagents`` is exercised. The
existing ``jarvis_reasoner`` import side-effect is unavoidable because
DDR-012 mandates compile-at-import; the AC-009 test instead asserts
that ``init_chat_model`` is *not* invoked by ``build_async_subagents``
itself.
"""

from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import patch

import deepagents

from jarvis.agents import subagent_registry
from jarvis.agents.subagent_registry import build_async_subagents
from jarvis.config.settings import JarvisConfig

# ---------------------------------------------------------------------------
# Substrings the description MUST contain — routing signals (DDR-010).
# ---------------------------------------------------------------------------
_REQUIRED_SUBSTRINGS: tuple[str, ...] = (
    "gpt-oss-120b",
    "on the premises",
    "sub-second",
    "two to four minutes",
    "critic",
    "researcher",
    "planner",
)

# ---------------------------------------------------------------------------
# Substrings the description MUST NOT contain — four-roster legacy names
# plus generic cloud-tier promise tokens (Context A concern #3 /
# TASK-J003-020 regression test).
# ---------------------------------------------------------------------------
_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "deep_reasoner",
    "adversarial_critic",
    "long_research",
    "quick_local",
    "cloud",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config() -> JarvisConfig:
    """Build a clean ``JarvisConfig`` insensitive to ambient env vars."""
    with patch.dict("os.environ", {}, clear=True):
        return JarvisConfig(openai_base_url="http://fake-endpoint/v1")


# ---------------------------------------------------------------------------
# AC-001 — public factory exists with the agreed signature.
# ---------------------------------------------------------------------------
class TestAC001PublicFactory:
    """``build_async_subagents`` is exposed at the documented import path."""

    def test_module_exports_build_async_subagents(self) -> None:
        assert hasattr(subagent_registry, "build_async_subagents")
        assert callable(subagent_registry.build_async_subagents)

    def test_returns_list(self) -> None:
        result = build_async_subagents(_config())
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# AC-002 — exactly one element (single local AsyncSubAgent per ADR-ARCH-011).
# ---------------------------------------------------------------------------
class TestAC002SingleElement:
    """The list must contain exactly one entry — no fleet, no roster."""

    def test_returns_single_entry(self) -> None:
        result = build_async_subagents(_config())
        assert len(result) == 1


# ---------------------------------------------------------------------------
# AC-003 — name / graph_id / description core fields.
# ---------------------------------------------------------------------------
class TestAC003CoreFields:
    """Name, graph_id, and description satisfy the contract."""

    def test_name_is_jarvis_reasoner(self) -> None:
        spec = build_async_subagents(_config())[0]
        assert spec["name"] == "jarvis-reasoner"

    def test_graph_id_is_jarvis_reasoner(self) -> None:
        spec = build_async_subagents(_config())[0]
        assert spec["graph_id"] == "jarvis_reasoner"

    def test_description_is_non_empty_string(self) -> None:
        spec = build_async_subagents(_config())[0]
        description = spec["description"]
        assert isinstance(description, str)
        assert description.strip() != ""


# ---------------------------------------------------------------------------
# AC-004 — description carries all required routing signals.
# ---------------------------------------------------------------------------
class TestAC004RequiredRoutingSignals:
    """Every routing-signal substring is present in the description."""

    def test_description_contains_required_substrings(self) -> None:
        spec = build_async_subagents(_config())[0]
        description = spec["description"]
        missing = [s for s in _REQUIRED_SUBSTRINGS if s not in description]
        assert not missing, (
            f"description missing required routing signals: {missing}\ndescription: {description!r}"
        )


# ---------------------------------------------------------------------------
# AC-005 — description contains none of the forbidden tokens.
# ---------------------------------------------------------------------------
class TestAC005ForbiddenTokensAbsent:
    """Four-roster legacy names and cloud-tier promises are absent."""

    def test_description_excludes_forbidden_substrings(self) -> None:
        spec = build_async_subagents(_config())[0]
        description = spec["description"].lower()
        present = [s for s in _FORBIDDEN_SUBSTRINGS if s in description]
        assert not present, (
            f"description contains forbidden tokens: {present}\ndescription: {description!r}"
        )


# ---------------------------------------------------------------------------
# AC-006 — AsyncSubAgent must be the deepagents TypedDict, not a redefinition.
# ---------------------------------------------------------------------------
class TestAC006UsesDeepAgentsAsyncSubAgent:
    """The module imports ``AsyncSubAgent`` from ``deepagents`` directly."""

    def test_module_uses_deepagents_async_subagent(self) -> None:
        # The symbol referenced by the module must be identical to the
        # one re-exported from the deepagents package.
        from jarvis.agents.subagent_registry import AsyncSubAgent as exported

        assert exported is deepagents.AsyncSubAgent

    def test_no_local_typeddict_redefinition(self) -> None:
        # Sanity check — re-importing should not produce a fresh TypedDict.
        module = importlib.reload(subagent_registry)
        assert module.AsyncSubAgent is deepagents.AsyncSubAgent


# ---------------------------------------------------------------------------
# AC-007 — deterministic / pure — same config produces identical text.
# ---------------------------------------------------------------------------
class TestAC007Deterministic:
    """Repeat invocations on identical inputs produce identical output."""

    def test_description_is_deterministic(self) -> None:
        config = _config()
        first = build_async_subagents(config)[0]
        second = build_async_subagents(config)[0]
        assert first == second

    def test_description_independent_of_config_instance_identity(self) -> None:
        a = build_async_subagents(_config())[0]
        b = build_async_subagents(_config())[0]
        assert a == b


# ---------------------------------------------------------------------------
# AC-008 — ``subagents`` package re-exports the compiled graph symbol.
# ---------------------------------------------------------------------------
class TestAC008GraphReExport:
    """``langgraph.json`` can bind ``jarvis_reasoner`` via the package path."""

    def test_graph_is_re_exported_from_subagents_package(self) -> None:
        from jarvis.agents import subagents as subagents_pkg
        from jarvis.agents.subagents.jarvis_reasoner import graph as inner_graph

        assert hasattr(subagents_pkg, "graph")
        assert subagents_pkg.graph is inner_graph

    def test_graph_listed_in_dunder_all(self) -> None:
        from jarvis.agents import subagents as subagents_pkg

        assert "graph" in subagents_pkg.__all__


# ---------------------------------------------------------------------------
# AC-009 — no LLM calls; no I/O beyond reading config.
# ---------------------------------------------------------------------------
class TestAC009NoNetworkAtBuildTime:
    """``build_async_subagents`` does not invoke ``init_chat_model``."""

    def test_does_not_call_init_chat_model(self) -> None:
        # Patch at the canonical import location used by langchain.
        with patch("langchain.chat_models.init_chat_model") as init_mock:
            build_async_subagents(_config())
        init_mock.assert_not_called()

    def test_does_not_call_create_deep_agent(self) -> None:
        # The factory composes a TypedDict; no graph compilation should
        # happen inside ``build_async_subagents`` itself.
        with patch("deepagents.create_deep_agent") as deep_mock:
            build_async_subagents(_config())
        deep_mock.assert_not_called()


# ---------------------------------------------------------------------------
# AC-routing-shape — structural checks that complement the substring
# assertions above (mentions of all three roles + the model alias).
# ---------------------------------------------------------------------------
class TestRoutingDescriptionShape:
    """The description must enumerate every role and the model anchor."""

    def test_description_mentions_each_role_word(self) -> None:
        spec = build_async_subagents(_config())[0]
        for role in ("critic", "researcher", "planner"):
            assert role in spec["description"], f"role token {role!r} missing from description"

    def test_description_mentions_model_alias_explicitly(self) -> None:
        spec = build_async_subagents(_config())[0]
        assert "gpt-oss-120b" in spec["description"]


# ---------------------------------------------------------------------------
# Smoke — typed dict satisfies the deepagents TypedDict shape (minimum
# required keys present).
# ---------------------------------------------------------------------------
class TestSpecDictShape:
    """The dict has the required AsyncSubAgent keys (name/description/graph_id)."""

    def test_spec_has_required_keys(self) -> None:
        spec = build_async_subagents(_config())[0]
        for key in ("name", "description", "graph_id"):
            assert key in spec, f"required key {key!r} missing from spec"

    def test_spec_values_are_strings(self) -> None:
        spec = build_async_subagents(_config())[0]
        assert isinstance(spec["name"], str)
        assert isinstance(spec["description"], str)
        assert isinstance(spec["graph_id"], str)

    def test_spec_values_are_not_blank(self) -> None:
        spec = build_async_subagents(_config())[0]
        for key in ("name", "description", "graph_id"):
            assert spec[key].strip(), f"value for {key!r} is blank"

    def test_returned_list_does_not_alias_module_constant(self) -> None:
        # Repeated calls return independent lists so the supervisor
        # cannot inadvertently mutate a shared module-level state.
        first: list[Any] = build_async_subagents(_config())
        second: list[Any] = build_async_subagents(_config())
        assert first is not second
