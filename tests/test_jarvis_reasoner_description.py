"""Description invariants for the ``jarvis-reasoner`` AsyncSubAgent.

The ``description`` field returned by
:func:`jarvis.agents.subagent_registry.build_async_subagents` is the
DDR-010 routing contract — the reasoning model uses it to choose when
to delegate. This regression test pins the contract from two
directions:

- AC-004: the description MUST contain a fixed set of routing-signal
  substrings (model name, locality, latency, role names).
- AC-005: the description MUST NOT promise cloud-tier reasoning. The
  forbidden tokens are matched with a hyphen-aware word-boundary regex
  so the model-name substring ``gpt-oss-120b`` (which is local-fleet,
  not cloud) does not trigger on the bare ``gpt`` token.
- AC-006: the regex shape used for AC-005 is exercised explicitly so a
  future tightening cannot silently downgrade the boundary handling.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from jarvis.agents.subagent_registry import build_async_subagents

# ---------------------------------------------------------------------------
# Required routing-signal substrings (DDR-010).
# ---------------------------------------------------------------------------
_REQUIRED_SIGNALS: tuple[str, ...] = (
    "gpt-oss-120b",
    "on the premises",
    "sub-second",
    "two to four minutes",
    "critic",
    "researcher",
    "planner",
)

# ---------------------------------------------------------------------------
# Forbidden cloud-tier tokens (AC-005). Matched case-insensitively with a
# hyphen-aware boundary so ``gpt`` does not match inside ``gpt-oss-120b``.
# ---------------------------------------------------------------------------
_FORBIDDEN_CLOUD_TOKENS: tuple[str, ...] = (
    "cloud",
    "GPT",
    "Claude",
    "Gemini",
    "OpenAI",
    "Anthropic",
)


def _hyphen_aware_word_regex(token: str) -> re.Pattern[str]:
    """Return a regex matching ``token`` only when it stands alone.

    A hyphen is treated as part of the surrounding token, so
    ``gpt-oss-120b`` does NOT contain a standalone ``gpt`` match. The
    regex is case-insensitive — the AC tokens are author-cased
    (``GPT``, ``Gemini`` …) but a description that lower-cased them
    would still be a violation.
    """
    return re.compile(
        rf"(?<![A-Za-z0-9-]){re.escape(token)}(?![A-Za-z0-9-])",
        re.IGNORECASE,
    )


def _description(test_config: Any) -> str:
    """Return the ``description`` string for the single AsyncSubAgent spec."""
    spec = build_async_subagents(test_config)[0]
    return spec["description"]


# ---------------------------------------------------------------------------
# AC-004 — required signal substrings are present.
# ---------------------------------------------------------------------------
class TestAC004RequiredRoutingSignals:
    """Every routing-signal substring must appear in the description."""

    @pytest.mark.parametrize("signal", _REQUIRED_SIGNALS)
    def test_description_contains_required_signal(self, signal: str, test_config: Any) -> None:
        description = _description(test_config)
        assert signal in description, (
            f"description missing required routing signal {signal!r}; "
            f"got description={description!r}"
        )

    def test_description_contains_all_required_signals_at_once(self, test_config: Any) -> None:
        description = _description(test_config)
        missing = [s for s in _REQUIRED_SIGNALS if s not in description]
        assert not missing, (
            f"description missing required signals: {missing}; got description={description!r}"
        )


# ---------------------------------------------------------------------------
# AC-005 — description does NOT promise cloud-tier reasoning. The regex
# must accept the local-fleet ``gpt-oss-120b`` model name without raising
# the ``GPT`` violation.
# ---------------------------------------------------------------------------
class TestAC005NoCloudTierPromise:
    """Forbidden cloud tokens are absent under hyphen-aware word boundaries."""

    @pytest.mark.parametrize("token", _FORBIDDEN_CLOUD_TOKENS)
    def test_description_excludes_cloud_token(self, token: str, test_config: Any) -> None:
        description = _description(test_config)
        pattern = _hyphen_aware_word_regex(token)
        match = pattern.search(description)
        assert match is None, (
            f"description contains forbidden cloud-tier token {token!r} "
            f"at position {None if match is None else match.span()} — "
            f"got description={description!r}"
        )


# ---------------------------------------------------------------------------
# AC-006 — the hyphen-aware boundary regex is correct: ``gpt`` inside
# ``gpt-oss-120b`` does NOT match, even though plain ``\bgpt\b`` would.
# ---------------------------------------------------------------------------
class TestAC006HyphenAwareWordBoundary:
    """The regex tolerates ``gpt-oss-120b`` and rejects standalone ``gpt``."""

    def test_hyphenated_model_name_does_not_match_gpt(self) -> None:
        # The model-name substring is intentionally allowed even though it
        # contains the literal token ``gpt`` — the AC-006 contract.
        pattern = _hyphen_aware_word_regex("GPT")
        sample = "Local Jarvis reasoning subagent backed by the gpt-oss-120b model."
        assert pattern.search(sample) is None

    def test_standalone_gpt_does_match(self) -> None:
        # Sanity check the negative — a real cloud-tier promise would
        # use ``GPT`` (or any case) as a standalone word and that MUST
        # be rejected.
        pattern = _hyphen_aware_word_regex("GPT")
        for sample in (
            "Escalates to GPT for harder problems.",
            "Falls back to gpt when local capacity is insufficient.",
            "Defaults to GPT, plain.",
        ):
            assert pattern.search(sample) is not None, f"expected match for sample={sample!r}"

    def test_other_cloud_tokens_match_only_as_standalone(self) -> None:
        # Cross-check the regex shape on the remaining cloud tokens —
        # protects against a future change that introduces a substring
        # like ``gemini-flash`` and then trips a bare ``\bgemini\b``.
        for token, accepted, rejected in (
            (
                "Gemini",
                # ``gemini-3.1-pro`` is a hyphenated identifier — the
                # regex MUST tolerate it (same shape as ``gpt-oss-120b``).
                "Local-only reasoning over gemini-3.1-pro is not implied.",
                "Escalate to Gemini for second opinions.",
            ),
            (
                "Claude",
                "Token ``claude-3.5`` is a hyphenated identifier.",
                "Falls back to Claude on cloud overflow.",
            ),
        ):
            pattern = _hyphen_aware_word_regex(token)
            assert pattern.search(accepted) is None, (
                f"unexpected match for token={token!r} in {accepted!r}"
            )
            assert pattern.search(rejected) is not None, (
                f"expected match for token={token!r} in {rejected!r}"
            )
