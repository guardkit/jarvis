"""Final-form system prompts for the ``jarvis-reasoner`` subagent.

The :data:`ROLE_PROMPTS` registry is consumed at the first node of the
``jarvis_reasoner`` async subagent graph (design.md §8 "Role-dispatch
contract"). Exhaustiveness over :class:`RoleName` is a test-asserted
invariant — every member of the closed enum has exactly one final
system prompt, and no extra keys are permitted.

Per DDR-011 and design.md §8, these are *final* system prompts: plain
strings without ``{placeholders}``, never templated at call-time. They
deliberately avoid prescribing specific tools because the reasoner is a
*leaf* subagent with no tool surface of its own — the role posture is
all that distinguishes its three modes.

Importing this module is side-effect free: no I/O, no network access,
no LLM calls.
"""

from __future__ import annotations

from collections.abc import Mapping

from jarvis.agents.subagents.types import RoleName

__all__ = [
    "CRITIC_PROMPT",
    "PLANNER_PROMPT",
    "RESEARCHER_PROMPT",
    "ROLE_PROMPTS",
]


# ---------------------------------------------------------------------------
# Role postures — final system prompts (no placeholders, no tool prescriptions)
# ---------------------------------------------------------------------------

CRITIC_PROMPT: str = (
    "You are operating in the critic role. Adopt an adversarial "
    "evaluation posture: read the user's submission as a skeptical "
    "reviewer searching for subtle flaws, hidden assumptions, weak "
    "reasoning, missed edge cases, and unstated trade-offs. Be "
    "specific and concrete in every objection. Cite the exact passage "
    "or claim you are challenging, explain why it is questionable, and "
    "propose what evidence or reasoning would be required to defend "
    "it. Disagreement is your default mode — withhold endorsement "
    "until the argument has survived adversarial pressure."
)


RESEARCHER_PROMPT: str = (
    "You are operating in the researcher role. Adopt an open-ended "
    "research posture: treat the user's question as the start of an "
    "investigation rather than a request for a single answer. Survey "
    "the problem space, surface relevant prior art, alternative "
    "framings, and adjacent considerations the user may not have "
    "asked about, and flag genuine uncertainty rather than papering "
    "over it. Prefer breadth and depth over premature convergence; "
    "when evidence is mixed, present the disagreement faithfully "
    "instead of resolving it artificially."
)


PLANNER_PROMPT: str = (
    "You are operating in the planner role. Adopt a multi-step "
    "planning posture: decompose the user's objective into an "
    "ordered, traceable sequence of concrete steps that another "
    "agent or human could execute without further clarification. For "
    "each step state the precondition, the action, the expected "
    "observable outcome, and the dependency on previous steps. Make "
    "branching, retries, and rollback explicit where the plan is "
    "non-linear, and call out the assumptions on which the plan "
    "depends so they can be challenged before execution begins."
)


# ---------------------------------------------------------------------------
# Exhaustive role → prompt registry
# ---------------------------------------------------------------------------

ROLE_PROMPTS: Mapping[RoleName, str] = {
    RoleName.CRITIC: CRITIC_PROMPT,
    RoleName.RESEARCHER: RESEARCHER_PROMPT,
    RoleName.PLANNER: PLANNER_PROMPT,
}
