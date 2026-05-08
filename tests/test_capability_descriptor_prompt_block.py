"""Snapshot tests for ``CapabilityDescriptor.as_prompt_block`` — TASK-CAPS-PROMPT-001 / R2.

Closes the prompt-side fidelity gap surfaced by TASK-REV-9939: the supervisor
prompt's ``{available_capabilities}`` block now carries the tool parameter
schema as an ``Args (required):`` block under each tool, so the reasoning
model can construct ``payload_json`` for ``dispatch_by_capability`` from
declared keys rather than guessing them.

Pinned against the architect-agent shape (one manifest, three required
string args — ``context``, ``proposal``, ``question``) so the snapshot
doesn't churn every time another fleet manifest's description text is
tweaked. Fleet-wide tests (``test_capabilities.py::TestAsPromptBlock``)
stay shape-only.

These tests are **regression tests** for the two-layer drop:
1. ``test_args_required_block_present_for_architect_align`` — pre-fix red,
   post-fix green; verifies the rendered block contains
   ``Args (required):`` and the three keys in manifest-declared order.
2. ``test_args_block_omitted_when_parameters_is_none`` — back-compat for
   older manifests / skinny stubs that don't carry parameters.
3. ``test_args_block_omitted_when_required_is_empty`` — guard against
   spurious empty headers when ``parameters`` is present but ``required``
   is missing or empty.
"""

from __future__ import annotations

from jarvis.tools.capabilities import (
    CapabilityDescriptor,
    CapabilityToolSummary,
)


# Source of truth: specialist-agent/src/specialist_agent/adapters/manifest.py
# _architect_manifest_factory — architect_align ToolCapability.parameters.
# Copied verbatim so a future drift in the upstream schema is visible here
# rather than silent in production.
_ARCHITECT_ALIGN_PARAMETERS: dict = {
    "type": "object",
    "properties": {
        "context": {
            "type": "string",
            "description": "Background: existing architecture, constraints",
        },
        "proposal": {
            "type": "string",
            "description": "The proposal or design to evaluate",
        },
        "question": {
            "type": "string",
            "description": "Specific question to answer",
        },
    },
    "required": ["context", "proposal", "question"],
}


def _architect_align_descriptor(
    *,
    parameters: dict | None = _ARCHITECT_ALIGN_PARAMETERS,
) -> CapabilityDescriptor:
    """Build a single-tool architect-agent descriptor for snapshot tests."""
    return CapabilityDescriptor(
        agent_id="architect-agent",
        role="Architect",
        description="Architectural reasoning, judgment, and exploration.",
        cost_signal="moderate",
        latency_signal="5-30s",
        trust_tier="specialist",
        capability_list=[
            CapabilityToolSummary(
                tool_name="architect_align",
                description=(
                    "Provide architectural judgment on a proposal or "
                    "question (Mode 2). Synchronous — returns immediately."
                ),
                risk_level="read_only",
                parameters=parameters,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# AC-006 — snapshot fails on a clean checkout of main, passes after the fix.
# ---------------------------------------------------------------------------


class TestArgsRequiredBlock:
    """R2 (Typed Args) renders ``Args (required):`` per Step 3 render rules."""

    def test_args_required_block_present_for_architect_align(self) -> None:
        """The rendered block names the literal substring + the three keys.

        Pre-fix this assertion fails on ``main`` because ``as_prompt_block``
        emits only ``  - architect_align (read_only) — ...``. Post-fix it
        passes because R2 appends an ``Args (required):`` subblock.
        """
        descriptor = _architect_align_descriptor()
        rendered = descriptor.as_prompt_block()

        # Header is present.
        assert "Args (required):" in rendered

        # All three keys appear with their JSON-Schema type and description.
        assert "context (string): Background: existing architecture, constraints" in rendered
        assert "proposal (string): The proposal or design to evaluate" in rendered
        assert "question (string): Specific question to answer" in rendered

        # Manifest-declared order is preserved (context → proposal → question).
        idx_context = rendered.index("context (string)")
        idx_proposal = rendered.index("proposal (string)")
        idx_question = rendered.index("question (string)")
        assert idx_context < idx_proposal < idx_question

    def test_args_block_indented_under_parent_tool_line(self) -> None:
        """6-space indent on each arg bullet, 4-space indent on the header.

        Matches the existing tool-line indent (``  - tool_name`` is 2-space)
        so the args nest visually under their parent tool when the supervisor
        skims the catalogue.
        """
        descriptor = _architect_align_descriptor()
        rendered = descriptor.as_prompt_block()

        assert "    Args (required):" in rendered
        assert "      - context (string)" in rendered
        assert "      - proposal (string)" in rendered
        assert "      - question (string)" in rendered

    def test_args_block_renders_after_tool_line(self) -> None:
        """``Args (required):`` appears after the ``  - architect_align`` line."""
        descriptor = _architect_align_descriptor()
        rendered = descriptor.as_prompt_block()

        idx_tool_line = rendered.index("  - architect_align (read_only) —")
        idx_args_header = rendered.index("    Args (required):")
        assert idx_tool_line < idx_args_header


# ---------------------------------------------------------------------------
# Back-compat — older manifests without parameters render unchanged.
# ---------------------------------------------------------------------------


class TestArgsBlockBackCompat:
    """Older manifests + skinny stubs render exactly as they did pre-R2."""

    def test_args_block_omitted_when_parameters_is_none(self) -> None:
        """``parameters=None`` → no ``Args (required):`` block."""
        descriptor = _architect_align_descriptor(parameters=None)
        rendered = descriptor.as_prompt_block()

        assert "Args (required):" not in rendered
        # The tool line itself is still present.
        assert "  - architect_align (read_only) —" in rendered

    def test_args_block_omitted_when_required_is_empty(self) -> None:
        """``required: []`` → no ``Args (required):`` block, no spurious header."""
        descriptor = _architect_align_descriptor(
            parameters={
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "..."},
                },
                "required": [],
            }
        )
        rendered = descriptor.as_prompt_block()

        assert "Args (required):" not in rendered

    def test_args_block_omitted_when_required_is_missing(self) -> None:
        """``required`` key absent → no header (treated as empty)."""
        descriptor = _architect_align_descriptor(
            parameters={
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "..."},
                },
            }
        )
        rendered = descriptor.as_prompt_block()

        assert "Args (required):" not in rendered


# ---------------------------------------------------------------------------
# Defensive — manifest hygiene gaps surface visibly rather than silently.
# ---------------------------------------------------------------------------


class TestArgsBlockDefensive:
    """Render rules surface manifest hygiene gaps for operator visibility."""

    def test_required_key_missing_from_properties_renders_unknown_type(self) -> None:
        """Required key with no ``properties`` entry → ``(unknown):`` per render rules.

        Should not happen in practice (the upstream Pydantic model should
        enforce shape), but the renderer surfaces the gap visibly so an
        operator sees the missing schema in the prompt rather than silent
        omission.
        """
        descriptor = _architect_align_descriptor(
            parameters={
                "type": "object",
                "properties": {
                    "context": {"type": "string", "description": "Background"},
                    # ``proposal`` deliberately omitted from properties.
                },
                "required": ["context", "proposal"],
            }
        )
        rendered = descriptor.as_prompt_block()

        assert "      - context (string): Background" in rendered
        assert "      - proposal (unknown):" in rendered
