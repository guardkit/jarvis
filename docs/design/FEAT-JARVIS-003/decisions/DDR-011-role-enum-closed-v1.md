# DDR-011: `RoleName` is a closed enum for v1 — `CRITIC`, `RESEARCHER`, `PLANNER`

**Status:** Accepted
**Date:** 2026-04-23
**Deciders:** Rich + `/system-design FEAT-JARVIS-003` session
**Related context:** FEAT-JARVIS-003
**Related components:** `jarvis.agents.subagents.prompts.RoleName`, `jarvis.agents.subagents.prompts.ROLE_PROMPTS`, `jarvis.agents.subagents.jarvis_reasoner`
**Depends on:** [DDR-010](DDR-010-single-async-subagent-supersedes-four-roster.md), [ADR-ARCH-011](../../../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md), [ADR-ARCH-017](../../../architecture/decisions/ADR-ARCH-017-static-skill-declaration-v1.md)

## Context

[DDR-010](DDR-010-single-async-subagent-supersedes-four-roster.md) collapses FEAT-JARVIS-003's subagent cardinality to one (`jarvis-reasoner`) and restores role specialisation via a `role` input kwarg. That leaves the role-set design undefined. Options span:

- **Open string** — any string is accepted; the subagent graph looks it up in a dict, returns `ERROR: unknown_role` on miss.
- **Closed enum** — `RoleName(Enum)` with a fixed member set; the graph validates via `RoleName(value)` at entry.
- **Declaration file** — roles declared in YAML, loaded at startup, iterated from Pydantic.

The architecture conversation starter's ADR-J-P2 names three kinds of cognitive work the routing surface should distinguish: long-form reasoning (depth), adversarial evaluation (flaw detection), open-ended research (breadth). ADR-ARCH-011 re-lists these as "critic, researcher, planner" with "planner" taking the place of ADR-J-P2's "deep_reasoner" because planning (multi-step, gated) is the more common supervisor need than raw chain-of-thought.

ADR-ARCH-017 sets the v1 precedent that *declared* surfaces (skills) ship as static declarations, not dynamic registration. Open-string roles would be the opposite: no declaration at all.

## Decision

`RoleName` is a Python `Enum` with exactly three members in v1:

```python
class RoleName(str, Enum):
    CRITIC = "critic"
    RESEARCHER = "researcher"
    PLANNER = "planner"
```

`ROLE_PROMPTS: Mapping[RoleName, str]` is a complete mapping over `RoleName` members (exhaustiveness asserted in `test_subagent_prompts.py`). The `jarvis_reasoner` graph validates `input["role"]` via `RoleName(input["role"])` at its first node; invalid values return `ERROR: unknown_role — expected one of {critic, researcher, planner}` via the `async_tasks` channel per ADR-ARCH-021.

Role postures at v1:

| Role | Posture |
|---|---|
| **CRITIC** | Adversarial evaluation. Coach-style flaw detection, calibrated scoring, "what would fail this" framing. Intended for design reviews, architecture critique, pre-PR code review. |
| **RESEARCHER** | Open-ended research. Web search (via `search_web` tool from FEAT-JARVIS-002), synthesis, multi-source summarisation. No hard latency budget. Intended for literature scans, fact-finding, "what do we know about X" queries. |
| **PLANNER** | Multi-step planning. Sequential-task decomposition, dependency identification, gate-identification. Intended for "break down this feature", "what's the build order", "what could go wrong with this plan" questions. |

Additive members (e.g. `EDUCATOR`, `DEBUGGER`) may be added in later features without breaking the enum contract, but changes require a commit-message justification per the subagent-descriptions-are-the-contract invariant from the Phase 2 scope doc. Closing the enum v1 and allowing non-breaking additions matches [ADR-ARCH-017](../../../architecture/decisions/ADR-ARCH-017-static-skill-declaration-v1.md)'s static-declaration posture for skills.

## Rationale

- **Learning flywheel (FEAT-JARVIS-008, v1.5) needs a fixed label space.** Pattern detection over `jarvis_routing_history` compares *choice distributions* across sessions. An open-string role set produces an unbounded label space and prevents meaningful cross-session comparison. A closed enum gives `jarvis.learning` a countable set to measure role-redirect frequencies over.
- **Typed supervisor prompt.** The supervisor's prompt-level routing section can enumerate the three roles explicitly ("critic for evaluation, researcher for synthesis, planner for decomposition"). An open string list makes the prompt hand-wave ("whatever role seems right"), which a small reasoning model fails at.
- **Exhaustiveness guard.** `test_subagent_prompts.py` asserts `set(ROLE_PROMPTS.keys()) == set(RoleName)`, preventing a missing prompt from landing silently. With open strings, the miss surfaces only at runtime.
- **Mypy `--strict` ergonomics.** `RoleName(str, Enum)` interoperates with both JSON payloads (`.value` serialisation) and typed function signatures — no manual `Literal[…]` maintenance as roles grow.

## Alternatives considered

1. **Open string with runtime dict lookup.** Rejected. Loses the label-space property above, loses mypy safety, silently degrades on typos.

2. **Four roles from day one (add `EDUCATOR` for the `Study Tutor` system context mention).** Deferred. `Study Tutor` is a separate agent on the fleet bus (per system-context.md), not a Jarvis role. Educator-shaped questions route via `dispatch_by_capability(tool_name="tutor:…")` to the Study Tutor, not through this enum. Adding `EDUCATOR` here would duplicate a fleet capability inside a single-agent subagent — violates ADR-ARCH-005's bounded-context separation.

3. **Roles loaded from YAML declaration file (`config/roles.yaml`).** Rejected for v1. Three roles don't justify a declaration-file pattern; YAML adds loading + validation code without reducing the prompt-writing work (role prompts still live in Python `ROLE_PROMPTS`). Revisit if the role count passes ~6.

4. **One role per subagent (reinstates multi-subagent shape).** Rejected — re-opens DDR-010.

## Consequences

**Positive:**
- Three role-prompts live in `src/jarvis/agents/subagents/prompts.py` as Python constants next to the enum — single place to author, single place to diff in commit messages.
- Role-miss errors are structured and observable; no silent route-to-default-prompt behaviour.
- Commit-message-justified enum additions create a visible record of role-taxonomy evolution — valuable for the learning flywheel's post-hoc analysis.

**Negative:**
- Adding a role requires a source-code change, a new prompt constant, a test update, and a commit-message justification. Slightly heavier than an open string, deliberately so.
- The three roles don't map 1-to-1 with the scope doc's four categories — `quick_local` has no equivalent (retired by DDR-010 + ADR-ARCH-012). Supervisor prompt needs to teach the reasoning model that "quick low-stakes work" is *not* a role — it's a direct-tool call (`calculate`, `search_web`, `read_file`) or a one-turn supervisor response.

## Links

- DDR-010 — single async subagent
- ADR-ARCH-011 — role-driven prompts on single subagent
- ADR-ARCH-017 — static declaration for v1
- ADR-ARCH-021 — tools return structured errors
