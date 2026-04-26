"""Unit tests for ``escalate_to_frontier`` Layer 1 — TASK-J003-010.

Layer 1 covers the tool body, docstring contract, and config / provider
branches per DDR-014. Layer 2 (executor attended-only assertion) and
Layer 3 (tool-registry absence) land in TASK-J003-011 / -012 and are out
of scope here.

Test class layout mirrors the acceptance-criteria list one-to-one:

* :class:`TestToolDecoration` — ``@tool(parse_docstring=True)`` wired in
  ``jarvis.tools.dispatch`` (AC-001, AC-002 partial).
* :class:`TestDocstringContract` — verbatim ATTENDED-ONLY warning in the
  docstring (AC-002).
* :class:`TestTargetCoercion` — out-of-enum ``target`` rejected before
  the function body runs (AC-004).
* :class:`TestConfigMissingGemini` — missing ``GOOGLE_API_KEY`` returns
  the structured ``ERROR: config_missing —`` string and emits exactly
  one INFO log with ``outcome="config_missing"`` (AC-005).
* :class:`TestConfigMissingAnthropic` — missing ``ANTHROPIC_API_KEY``
  symmetric to Gemini (AC-005).
* :class:`TestProviderUnavailable` — provider SDK exceptions map to the
  ``DEGRADED: provider_unavailable`` string with no instruction body
  echoed (AC-006, AC-009).
* :class:`TestDegradedEmpty` — empty provider body maps to
  ``DEGRADED: provider_unavailable — empty response`` and emits one
  INFO log with ``outcome="degraded_empty"`` (AC-007).
* :class:`TestHappyPath` — happy path returns provider text and emits
  one INFO log with ``outcome="success"`` (AC-003, AC-008).
* :class:`TestStructuredLog` — every successful or degraded call emits
  exactly one structured INFO record carrying the ``model_alias=
  cloud-frontier`` budget tag (AC-008, AC-009).
* :class:`TestNeverRaises` — the tool never propagates an exception
  (AC-010).
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from jarvis.tools import dispatch
from jarvis.tools.dispatch_types import FrontierTarget


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _invoke(
    instruction: str = "hello",
    target: str | FrontierTarget | None = None,
) -> str:
    """Invoke the @tool-wrapped ``escalate_to_frontier`` and return the str."""
    kwargs: dict[str, Any] = {"instruction": instruction}
    if target is not None:
        kwargs["target"] = target
    return dispatch.escalate_to_frontier.invoke(kwargs)


def _make_gemini_client(text: str) -> MagicMock:
    """Build a MagicMock standing in for ``google.genai.Client``.

    The mock is shaped so ``client.models.generate_content(...)`` returns
    an object with a ``.text`` attribute equal to ``text``.
    """
    response = MagicMock()
    response.text = text
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def _make_opus_client(text: str) -> MagicMock:
    """Build a MagicMock standing in for ``anthropic.Anthropic``.

    The mock is shaped so ``client.messages.create(...).content[0].text``
    equals ``text`` — matching the v0.40 Anthropic SDK response shape.
    """
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


# ===========================================================================
# AC-001 — escalate_to_frontier tool exists and is decorated
# ===========================================================================
class TestToolDecoration:
    """Tool object exposed via ``jarvis.tools.dispatch``."""

    def test_escalate_to_frontier_is_basetool(self) -> None:
        from langchain_core.tools import BaseTool

        assert isinstance(dispatch.escalate_to_frontier, BaseTool)

    def test_tool_name_is_escalate_to_frontier(self) -> None:
        assert dispatch.escalate_to_frontier.name == "escalate_to_frontier"

    def test_tool_args_schema_includes_instruction_and_target(self) -> None:
        args = dispatch.escalate_to_frontier.args
        assert "instruction" in args
        assert "target" in args


# ===========================================================================
# AC-002 — Docstring contract (verbatim ATTENDED-ONLY warning)
# ===========================================================================
class TestDocstringContract:
    """Verbatim ATTENDED-ONLY warning per DDR-005 precedent."""

    REQUIRED: str = (
        "ATTENDED-ONLY — cloud escape hatch. Never invoke from ambient, "
        "learning, or async-subagent contexts."
    )

    def test_docstring_contains_required_attended_only_text(self) -> None:
        doc = dispatch.escalate_to_frontier.func.__doc__ or ""
        assert self.REQUIRED in doc

    def test_description_carries_required_attended_only_text(self) -> None:
        # langchain's @tool(parse_docstring=True) lifts the description
        # paragraph(s) onto BaseTool.description — the string the
        # reasoning model sees in its tool catalogue.
        description = dispatch.escalate_to_frontier.description or ""
        assert self.REQUIRED in description


# ===========================================================================
# AC-004 — Out-of-enum target rejected before function body runs
# ===========================================================================
class TestTargetCoercion:
    """``@tool(parse_docstring=True)`` validates ``target`` via pydantic."""

    def test_invalid_target_does_not_contact_any_provider(self) -> None:
        # ``@tool(parse_docstring=True)`` validates ``target`` through a
        # pydantic schema built from the type hint; an out-of-enum value
        # raises ``pydantic.ValidationError`` before the function body
        # runs. The constitutional invariant we assert here is the
        # behavioural one: no provider client is ever constructed.
        from pydantic import ValidationError

        with (
            patch("google.genai.Client") as gemini_cls,
            patch("anthropic.Anthropic") as opus_cls,
            pytest.raises(ValidationError),
        ):
            _invoke(target="NOT_A_VALID_TARGET")
        gemini_cls.assert_not_called()
        opus_cls.assert_not_called()


# ===========================================================================
# AC-005 — Missing GOOGLE_API_KEY for Gemini target
# ===========================================================================
class TestConfigMissingGemini:
    """Gemini path returns config_missing without contacting the provider."""

    def test_returns_config_missing_string_for_gemini_without_key(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("google.genai.Client") as gemini_cls,
        ):
            result = _invoke(target="GEMINI_3_1_PRO", instruction="hello")
            gemini_cls.assert_not_called()
        assert result == "ERROR: config_missing — GOOGLE_API_KEY not set"

    def test_emits_one_info_log_with_config_missing_outcome(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"),
        ):
            _invoke(target="GEMINI_3_1_PRO", instruction="hello")
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        assert getattr(records[0], "outcome", None) == "config_missing"
        assert getattr(records[0], "model_alias", None) == "cloud-frontier"
        assert getattr(records[0], "target", None) == "GEMINI_3_1_PRO"

    def test_config_missing_string_does_not_echo_instruction_body(self) -> None:
        secret = "this-is-a-secret-prompt-body"
        with patch.dict("os.environ", {}, clear=True):
            result = _invoke(target="GEMINI_3_1_PRO", instruction=secret)
        assert secret not in result


# ===========================================================================
# AC-005 — Missing ANTHROPIC_API_KEY for Opus target
# ===========================================================================
class TestConfigMissingAnthropic:
    """Opus path returns config_missing without contacting the provider."""

    def test_returns_config_missing_string_for_opus_without_key(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("anthropic.Anthropic") as opus_cls,
        ):
            result = _invoke(target="OPUS_4_7", instruction="hello")
            opus_cls.assert_not_called()
        assert result == "ERROR: config_missing — ANTHROPIC_API_KEY not set"

    def test_emits_one_info_log_with_config_missing_outcome(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"),
        ):
            _invoke(target="OPUS_4_7", instruction="hello")
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        assert getattr(records[0], "outcome", None) == "config_missing"
        assert getattr(records[0], "target", None) == "OPUS_4_7"
        assert getattr(records[0], "adapter", None) == "anthropic"

    def test_config_missing_string_does_not_echo_instruction_body(self) -> None:
        secret = "another-secret-body"
        with patch.dict("os.environ", {}, clear=True):
            result = _invoke(target="OPUS_4_7", instruction=secret)
        assert secret not in result


# ===========================================================================
# AC-006 / AC-009 — Provider unavailable returns DEGRADED, body redacted
# ===========================================================================
class TestProviderUnavailable:
    """SDK exceptions never propagate; instruction body is never echoed."""

    def test_gemini_sdk_exception_returns_degraded(self) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
        ):
            cls.side_effect = ConnectionError("dns failure")
            result = _invoke(
                target="GEMINI_3_1_PRO",
                instruction="my-private-prompt",
            )
        assert result.startswith("DEGRADED: provider_unavailable —")
        assert "my-private-prompt" not in result

    def test_opus_sdk_exception_returns_degraded(self) -> None:
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=True),
            patch("anthropic.Anthropic") as cls,
        ):
            cls.side_effect = ConnectionError("dns failure")
            result = _invoke(
                target="OPUS_4_7",
                instruction="my-other-secret-prompt",
            )
        assert result.startswith("DEGRADED: provider_unavailable —")
        assert "my-other-secret-prompt" not in result

    def test_provider_unavailable_emits_one_info_log(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
            caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"),
        ):
            cls.side_effect = TimeoutError("upstream slow")
            _invoke(target="GEMINI_3_1_PRO", instruction="hi")
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        assert getattr(records[0], "outcome", None) == "provider_unavailable"


# ===========================================================================
# AC-007 — Empty provider body maps to DEGRADED: provider_unavailable
# ===========================================================================
class TestDegradedEmpty:
    """Provider returns no text → degraded_empty branch."""

    def test_gemini_empty_text_returns_empty_response_string(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
            caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"),
        ):
            cls.return_value = _make_gemini_client(text="")
            result = _invoke(target="GEMINI_3_1_PRO", instruction="hi")
        assert result == "DEGRADED: provider_unavailable — empty response"
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        assert getattr(records[0], "outcome", None) == "degraded_empty"

    def test_opus_empty_text_returns_empty_response_string(self) -> None:
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=True),
            patch("anthropic.Anthropic") as cls,
        ):
            cls.return_value = _make_opus_client(text="")
            result = _invoke(target="OPUS_4_7", instruction="hi")
        assert result == "DEGRADED: provider_unavailable — empty response"

    def test_opus_no_content_blocks_returns_empty_response_string(self) -> None:
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=True),
            patch("anthropic.Anthropic") as cls,
        ):
            client = MagicMock()
            response = MagicMock()
            response.content = []
            client.messages.create.return_value = response
            cls.return_value = client
            result = _invoke(target="OPUS_4_7", instruction="hi")
        assert result == "DEGRADED: provider_unavailable — empty response"


# ===========================================================================
# AC-003 / AC-008 — Happy path returns provider text
# ===========================================================================
class TestHappyPath:
    """Successful provider call returns the response text as ``str``."""

    def test_gemini_happy_path_returns_response_text(self) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
        ):
            cls.return_value = _make_gemini_client(text="Hello from Gemini")
            result = _invoke(target="GEMINI_3_1_PRO", instruction="hi")
        assert result == "Hello from Gemini"

    def test_gemini_happy_path_calls_correct_model(self) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
        ):
            client = _make_gemini_client(text="ok")
            cls.return_value = client
            _invoke(target="GEMINI_3_1_PRO", instruction="hi")
        # Validate the model alias passed to generate_content matches AC-003.
        kwargs = client.models.generate_content.call_args.kwargs
        assert kwargs["model"] == "gemini-3.1-pro"

    def test_opus_happy_path_returns_response_text(self) -> None:
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=True),
            patch("anthropic.Anthropic") as cls,
        ):
            cls.return_value = _make_opus_client(text="Hello from Opus")
            result = _invoke(target="OPUS_4_7", instruction="hi")
        assert result == "Hello from Opus"

    def test_opus_happy_path_calls_correct_model(self) -> None:
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=True),
            patch("anthropic.Anthropic") as cls,
        ):
            client = _make_opus_client(text="ok")
            cls.return_value = client
            _invoke(target="OPUS_4_7", instruction="hi")
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-opus-4-7"

    def test_default_target_routes_to_gemini(self) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as gemini_cls,
            patch("anthropic.Anthropic") as opus_cls,
        ):
            gemini_cls.return_value = _make_gemini_client(text="ok")
            _invoke(instruction="hi")
            gemini_cls.assert_called_once()
            opus_cls.assert_not_called()


# ===========================================================================
# AC-008 / AC-009 — Structured INFO log on every success / degraded path
# ===========================================================================
class TestStructuredLog:
    """``log_frontier_escalation`` records the budget-trace tag + redacts."""

    def test_success_emits_exactly_one_info_record(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
            caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"),
        ):
            cls.return_value = _make_gemini_client(text="ok")
            _invoke(target="GEMINI_3_1_PRO", instruction="instr")
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert len(records) == 1
        rec = records[0]
        assert getattr(rec, "outcome", None) == "success"
        assert getattr(rec, "model_alias", None) == "cloud-frontier"
        assert getattr(rec, "target", None) == "GEMINI_3_1_PRO"
        assert getattr(rec, "instruction_length", None) == len("instr")

    def test_log_does_not_carry_instruction_body(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        secret = "my-secret-prompt-body-token"
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
            caplog.at_level(logging.INFO, logger="jarvis.tools.dispatch"),
        ):
            cls.return_value = _make_gemini_client(text="ok")
            _invoke(target="GEMINI_3_1_PRO", instruction=secret)
        records = [r for r in caplog.records if r.name == "jarvis.tools.dispatch"]
        assert records, "expected at least one INFO record"
        for rec in records:
            for banned in (
                "instruction",
                "instruction_body",
                "body",
                "prompt",
                "text",
            ):
                # Either the attribute does not exist on the record, or it
                # exists but is not the instruction body. We require the
                # stronger guarantee: never present in extra.
                assert not hasattr(rec, banned) or getattr(rec, banned) != secret
            assert secret not in rec.getMessage()


# ===========================================================================
# AC-010 — Tool never raises
# ===========================================================================
class TestNeverRaises:
    """Every error path produces a structured string per ADR-ARCH-021."""

    def test_runtime_error_inside_provider_call_is_caught(self) -> None:
        with (
            patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True),
            patch("google.genai.Client") as cls,
        ):
            client = MagicMock()
            client.models.generate_content.side_effect = RuntimeError("boom")
            cls.return_value = client
            result = _invoke(target="GEMINI_3_1_PRO", instruction="hi")
        assert result.startswith("DEGRADED: provider_unavailable")

    def test_value_error_inside_opus_call_is_caught(self) -> None:
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}, clear=True),
            patch("anthropic.Anthropic") as cls,
        ):
            client = MagicMock()
            client.messages.create.side_effect = ValueError("bad request")
            cls.return_value = client
            result = _invoke(target="OPUS_4_7", instruction="hi")
        assert result.startswith("DEGRADED: provider_unavailable")
