# DDR-010: Single `jarvis-reasoner` AsyncSubAgent supersedes the four-subagent roster

**Status:** Accepted
**Date:** 2026-04-23
**Deciders:** Rich + `/system-design FEAT-JARVIS-003` session
**Related context:** FEAT-JARVIS-003 (this feature)
**Related components:** `jarvis.agents.subagent_registry`, `jarvis.agents.subagents.jarvis_reasoner`
**Supersedes:** [phase2-dispatch-foundations-scope.md §FEAT-JARVIS-003 Change 1-2](../../../research/ideas/phase2-dispatch-foundations-scope.md) — four `AsyncSubAgent` instances
**Depends on:** [ADR-ARCH-001](../../../architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md), [ADR-ARCH-011](../../../architecture/decisions/ADR-ARCH-011-single-jarvis-reasoner-subagent.md), [ADR-ARCH-027](../../../architecture/decisions/ADR-ARCH-027-attended-only-cloud-escape-hatch.md), [FEAT-JARVIS-002 DDR-005 C2](../../FEAT-JARVIS-002/design.md)

## Context

The Phase 2 scope document (20 April 2026) specified four `AsyncSubAgent` instances for FEAT-JARVIS-003:

| Name | Model | Role |
|---|---|---|
| `deep_reasoner` | `google_genai:gemini-3.1-pro` | long-form reasoning |
| `adversarial_critic` | `anthropic:claude-opus-4-7` | quality evaluation |
| `long_research` | `openai:gpt-5.4` | open-ended research |
| `quick_local` | `vllm:qwen3-coder-next` | quick local lookups |

The `/system-arch` session held later the same day (20 April 2026) accepted four ADRs that retire three of those subagents and collapse the fourth:

- **ADR-ARCH-001** (foundational, local-first) — *no cloud LLMs on unattended paths.* AsyncSubAgents run unattended on every turn of the supervisor's reasoning loop. `deep_reasoner`, `adversarial_critic`, and `long_research` are therefore forbidden as unattended cloud calls.
- **ADR-ARCH-011** (single jarvis-reasoner) — *Jarvis ships with one async subagent, `jarvis-reasoner`, backed by `gpt-oss-120b` via llama-swap.* Specialist roles (critic, researcher, planner) are prompt-driven modes of the same model, not separate subagents.
- **ADR-ARCH-027** — frontier cloud reasoning is available *only* through the `escalate_to_frontier` tool on attended sessions; it is not a subagent and not available to ambient / learning / Pattern-C reasoning.
- **ADR-ARCH-012** — swap-aware voice-latency policy supersedes the `quick_local` fallback (JA6); no cloud fallback on the unattended path.

FEAT-JARVIS-002's design captured this as contradiction **C2** and deferred resolution: *"Out of scope for this design — flagged for `/system-design FEAT-JARVIS-003`. This design leaves a reserved slot in `jarvis.tools.dispatch` for `escalate_to_frontier` but does not implement it here."*

## Decision

FEAT-JARVIS-003 ships **one** `AsyncSubAgent`:

```python
AsyncSubAgent(
    name="jarvis-reasoner",
    graph_id="jarvis_reasoner",
    description=(
        "Local reasoning subagent backed by gpt-oss-120b (MXFP4, Blackwell-optimised) "
        "via llama-swap on GB10. Accepts a `role` input ∈ {critic, researcher, planner} "
        "that selects the system prompt for this invocation. No cloud cost, no privacy "
        "risk. Latency: sub-second per turn once warm; 2–4 min cold swap if "
        "qwen-coder-next was previously loaded (supervisor emits voice ack if so). "
        "Prefer for any sustained reasoning task beyond a single tool call; do not use "
        "for arithmetic (calculate), factual lookups (search_web), or file reads "
        "(read_file)."
    ),
)
```

The three scope-doc cloud subagents (`deep_reasoner`, `adversarial_critic`, `long_research`) are **not** created as subagents. Their reasoning capability surfaces through **two substitute paths**:

1. **Role-dispatch on the single subagent** — `start_async_task(name="jarvis-reasoner", input={"role": "critic", ...})` and the `researcher` / `planner` equivalents (see [DDR-011](DDR-011-role-enum-closed-v1.md)).
2. **`escalate_to_frontier` tool on attended sessions** — when Rich explicitly asks for a frontier opinion, per ADR-ARCH-027 (see [DDR-014](DDR-014-escalate-to-frontier-in-dispatch-tool-module.md)).

The scope-doc `quick_local` subagent is retired; its original problem (GB10 pressure under AutoBuild) is addressed by the swap-aware read path in [DDR-015](DDR-015-llamaswap-adapter-with-stubbed-health.md) per ADR-ARCH-012, not a cloud fallback.

## Rationale

- **Foundational constraint (ADR-ARCH-001) overrides feature scope.** The four-subagent design predates ADR-ARCH-001 and was rejected as part of that ADR's "Alternatives considered §1". FEAT-JARVIS-003 cannot reinstate what ADR-ARCH-001 rejected without re-opening a foundational ADR, which is out of scope for a `/system-design` step.
- **Preserves the routing-as-reasoning thesis.** The "one reasoning model that knows which reasoning model to use" framing survives at full strength: the reasoning model now chooses between (a) direct tools, (b) a role for `jarvis-reasoner`, (c) a fleet-dispatch to a specialist via `dispatch_by_capability`, (d) a build-queue via `queue_build`, and (e) `escalate_to_frontier` when Rich explicitly asks. The cardinality of subagents is orthogonal to the richness of the routing decision.
- **Avoids swap-thrash under load.** llama-swap's builders group is `swap: true, exclusive: true`. A heterogeneous-model AsyncSubAgent roster that routed across Gemini / Opus / GPT / local would — *if made local-first* — incur a 2–4 min cold swap per role change. One local model under `jarvis-reasoner` keeps the loaded-model identity stable across role changes (prompt-only differentiation is zero-cost).
- **Simpler supervisor prompt.** The supervisor's subagent-routing section becomes a three-role classification against one target, not a four-subagent cost/latency comparison. Lower chance of routing regressions when the supervisor reasoning model is small.

## Alternatives considered

1. **Preserve the four-subagent roster but re-target all four to local aliases.** Rejected. Two of the three role-mode distinctions (`deep_reasoner` vs `adversarial_critic`, `long_research`) are single-model-capable differences in prompt, not in model. `quick_local` distinct from `deep_reasoner` would be a local-vs-local split that ADR-ARCH-011 rejected directly. Creates Roster-vs-Model mismatch confusion (four subagent names, one backing model).

2. **Two subagents: `jarvis-reasoner` + `coder-assist`.** Considered and **deferred** per ADR-ARCH-011 §Alternatives §1. Code work flows through Forge AutoBuild in v1; Jarvis's own coder-assist work is rare. Promote `qwen-coder-next` to a named subagent only if a usage pattern emerges. Additive, non-breaking.

3. **Zero subagents — role dispatch becomes a prompt-prefix on the supervisor itself.** Rejected. Loses the parallelism, mid-flight steering, and separate-trace benefits of `AsyncSubAgent` (the same benefits Forge ADR-ARCH-031 cites for `autobuild_runner`). Also loses ADR-FLEET-001 trace-richness at the subagent-invocation level — role-dispatches would be buried in the supervisor's turn transcript rather than surfaced as first-class async-task entries.

4. **Defer the subagent entirely to v1.5; FEAT-JARVIS-003 ships only `escalate_to_frontier`.** Rejected. The subagent is the concrete realisation of ADR-J-P2 and fleet v3 D43 ("model routing as reasoning"). Deferring it leaves the thesis-defining behaviour unproved until after Phase 3 and forfeits the learning-flywheel's most valuable training data (role-choice priors).

## Consequences

**Positive:**
- Direct compliance with ADR-ARCH-001 + ADR-ARCH-011 without re-opening either.
- Single provider dependency on the unattended path (`openai:jarvis-reasoner` via llama-swap). No new provider SDKs in `pyproject.toml` for Phase 2 on account of subagents.
- Preview-feature risk contained — only one `AsyncSubAgent` surfaces the 0.5.3 preview API, keeping the ADR-ARCH-025 0.6 upgrade gate narrow.
- `test_routing_e2e.py` becomes meaningful sooner — three of seven canned prompts exercise role-dispatch on the single subagent.

**Negative:**
- Loses *model-heterogeneity* on the unattended path. If `gpt-oss-120b` turns out to be systematically weaker at one role (e.g. adversarial critique vs research), there is no in-subagent remedy short of adding a new llama-swap member (and accepting swap cost) or promoting a new named subagent.
- The supervisor's reasoning model must learn three-role classification from prompt descriptions alone — no cost/latency differentiator between role modes. If confusion appears, [DDR-011](DDR-011-role-enum-closed-v1.md)'s closed enum is the constraint, and role-prompt text is the authoring surface.

## Links

- ADR-ARCH-001 — Local-first inference via llama-swap
- ADR-ARCH-011 — Single jarvis-reasoner subagent
- ADR-ARCH-012 — Swap-aware voice latency policy (retires JA6)
- ADR-ARCH-027 — Attended-only `escalate_to_frontier`
- FEAT-JARVIS-002 design — C2 contradiction deferred to here
- phase2-dispatch-foundations-scope.md — superseded four-subagent roster
