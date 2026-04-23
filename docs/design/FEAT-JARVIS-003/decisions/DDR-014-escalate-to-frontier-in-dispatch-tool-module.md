# DDR-014: `escalate_to_frontier` lands in `jarvis.tools.dispatch`; belt+braces gating across three layers

**Status:** Accepted
**Date:** 2026-04-23
**Deciders:** Rich + `/system-design FEAT-JARVIS-003` session
**Related context:** FEAT-JARVIS-003
**Related components:** `jarvis.tools.dispatch.escalate_to_frontier`, `jarvis.infrastructure.lifecycle.assemble_tool_list`, `jarvis.agents.supervisor.build_supervisor`
**Depends on:** [FEAT-JARVIS-002 DDR-005 C2 slot reservation](../../FEAT-JARVIS-002/design.md), [ADR-ARCH-027](../../../architecture/decisions/ADR-ARCH-027-attended-only-cloud-escape-hatch.md), [ADR-ARCH-022](../../../architecture/decisions/ADR-ARCH-022-constitutional-rules-belt-and-braces.md), [ADR-ARCH-023](../../../architecture/decisions/ADR-ARCH-023-permissions-constitutional-not-reasoning-adjustable.md)

## Context

[ADR-ARCH-027](../../../architecture/decisions/ADR-ARCH-027-attended-only-cloud-escape-hatch.md) mandates that cloud frontier reasoning is available only on attended sessions, gated both at prompt level and via executor assertion (two-layer belt+braces). The ADR also specifies the tool is **removed** from the tool set passed to Pattern B watcher AsyncSubAgents, `jarvis.learning` reasoning paths, and Pattern C opt-in skill seeds.

FEAT-JARVIS-002 deferred implementation with a reserved slot: *"This design leaves a reserved slot in `jarvis.tools.dispatch` for `escalate_to_frontier` (attended-path-only, constitutionally gated per ADR-ARCH-022/023) but does not implement it here."*

Three implementation questions:

1. **Where does it live?** — `jarvis.tools.dispatch` (FEAT-JARVIS-002's module) vs a new `jarvis.tools.frontier` module.
2. **How is the tool-set-removal layer implemented?** — Convention (build the list manually for each caller) vs a typed factory (one place, one rule).
3. **What's the executor-assertion fallback when `AsyncSubAgentMiddleware` metadata is unavailable?** — Fail-closed vs session-state lookup.

## Decision

### Layer 1 — Module placement

`escalate_to_frontier` lives in **`jarvis.tools.dispatch`** alongside `dispatch_by_capability` and `queue_build`. The module's ownership is "tools that route reasoning off this process", which is what the frontier tool does (even though its target is a cloud LLM rather than a fleet agent or Forge). Co-location concentrates the three dispatch-shaped tools in one module for audit-ability, and matches the reservation FEAT-JARVIS-002 DDR-005 already stamped into the file layout.

### Layer 2 — Belt+braces constitutional gating, three layers

Per **ADR-ARCH-022** (belt+braces) and **ADR-ARCH-023** (permissions are constitutional, not reasoning-adjustable), the tool enforces at **three** layers — one more than the ADR's two-layer minimum — because cloud spend is irrecoverable once issued:

1. **Prompt-level prohibition (reasoning layer).** The supervisor system prompt's `## Frontier Escalation` section (see [design.md §10](../design.md)) states: *"The `escalate_to_frontier` tool is available only when I ask for it explicitly… not a default escalation path… will refuse invocation from ambient or learning contexts."* The tool's `@tool` docstring repeats this explicitly so the reasoning model sees the rule even if the prompt is truncated under compaction.

2. **Executor assertion (tool-boundary layer).** The tool body asserts, at invocation time:
   ```python
   session = _current_session()  # from jarvis.sessions.manager
   if session.adapter not in ATTENDED_ADAPTERS:
       return "ERROR: attended_only — escalate_to_frontier rejected (adapter=%s)" % session.adapter
   if _caller_is_async_subagent():
       return "ERROR: attended_only — escalate_to_frontier rejected (async-subagent frame)"
   ```
   `ATTENDED_ADAPTERS = {Adapter.TELEGRAM, Adapter.CLI, Adapter.DASHBOARD, Adapter.REACHY}`. `_caller_is_async_subagent()` inspects `AsyncSubAgentMiddleware` metadata; if unavailable (preview-feature divergence), it **fails closed** — returns the rejection rather than trusting the call. See `ASSUM-FRONTIER-CALLER-FRAME` in [design.md §12](../design.md).

3. **Registration absence (tool-set layer).** `assemble_tool_list(config, ..., include_frontier: bool)` is the single place in the codebase that builds a tool list. It appends `escalate_to_frontier` **iff** `include_frontier=True`. Two call sites:
   - `lifecycle.startup()` builds the *attended* tool list with `include_frontier=True`.
   - `build_supervisor(ambient_tool_factory=...)` receives a factory that builds the *ambient* tool list with `include_frontier=False`.
   The reasoning model in an ambient context cannot invoke a tool it cannot see — the absence is structural, not a runtime check.

Any one of the three layers is sufficient to block a rogue invocation; all three together provide defence-in-depth that matches ADR-ARCH-022's spirit.

### Layer 3 — Target selection

Default target is `FrontierTarget.GEMINI_3_1_PRO` → `google_genai:gemini-3.1-pro`. Alternative: `FrontierTarget.OPUS_4_7` → `anthropic:claude-opus-4-7`. Chosen via `target=` kwarg; the reasoning model can pass either based on docstring guidance ("Gemini for breadth; Opus for adversarial evaluation"). Tool uses `init_chat_model(target.value)` to reach the provider directly — no llama-swap routing (llama-swap only fronts local models).

Budget monitoring is trace-based per ADR-ARCH-027: invocations log at INFO with a canonical `JARVIS_FRONTIER_ESCALATION` prefix and include `model_alias=<target>`, `session_id=<id>`, `correlation_id=<id>`. When FEAT-JARVIS-004 writes go live, these records flow into `jarvis_routing_history` tagged `model_alias=cloud-frontier`.

## Rationale

- **Three braces instead of two.** ADR-ARCH-022 requires at least two enforcement layers; cloud spend's irreversibility justifies the third. The registration-absence layer (Layer 3) is the strongest — it makes a rogue invocation physically impossible from ambient contexts rather than runtime-blocked.
- **Fail-closed fallback on preview-feature divergence.** `_caller_is_async_subagent()` returning an unknown answer defaults to rejection. If DeepAgents 0.6 changes the middleware metadata, the tool degrades to over-rejecting (false positives on attended async-subagent frames that don't exist yet in v1), not under-rejecting.
- **Factory-pattern tool list.** One function (`assemble_tool_list`) is the only place `escalate_to_frontier` is appended to a list. Greppable, auditable, single-change-site.
- **Co-location with `dispatch_by_capability` + `queue_build`.** All three are "tools that hand off reasoning"; all three deserve one security audit pass in one module.

## Alternatives considered

1. **Two-layer gating only (prompt + executor assertion).** Rejected. ADR-ARCH-027 explicitly lists tool-set removal as a requirement ("**Tool is removed** from the tool set passed to: Pattern B watcher AsyncSubAgents, `jarvis.learning` reasoning paths, Pattern C opt-in skill seed"). A design that only implemented prompt + assertion would violate that ADR.

2. **New module `jarvis.tools.frontier`.** Rejected. One-tool module is low-value; fragments the dispatch-tools audit surface.

3. **Accept DeepAgents' default tool-registration mechanism and filter at dispatch.** Rejected. Requires the reasoning model to *see* a tool it's been told not to use — works against ADR-ARCH-023's "constitutional, not reasoning-adjustable" framing. The tool should be literally absent.

4. **Dynamic tool list per `start_async_task` call.** Rejected. The supervisor's tool list is bound at graph compile; changing it per-invocation breaks DeepAgents' caching and middleware wiring.

5. **Rich-confirmed `interrupt()` on every invocation.** Rejected for v1 per ADR-ARCH-027 §Alternatives §2 — highest UX friction. Revisit if escalations drift up in cost.

## Consequences

**Positive:**
- Cloud spend cannot leak via ambient/learning loops — the three layers combine to make it architecturally impossible.
- `assemble_tool_list` becomes the single audit point for constitutional tool registration; future additions to the attended-only tool set (e.g. FEAT-JARVIS-009 hardware-privileged tools for Reachy) plug in the same way.
- Trace-tagged frontier invocations feed the learning flywheel cleanly — Rich's explicit-frontier-ask patterns become observable priors.

**Negative:**
- Two tool lists (attended vs ambient) mean the supervisor factory has to accept both shapes. DDR-010's single-subagent design keeps this manageable; if subagent cardinality grows, the factory surface may need a `tool_context: Literal["attended", "ambient"]` parameter instead of explicit list passing.
- The third brace (registration absence) is defensive against bugs in the first two but duplicates work at audit time. Acceptable — the extra check is cheap and the property it buys (attended-only is a compile-time invariant, not a runtime check) is load-bearing.
- If FEAT-JARVIS-006 (Telegram adapter) changes `Adapter.TELEGRAM` semantics (e.g. per-user sub-adapters), the `ATTENDED_ADAPTERS` set needs revision. Flagged as `ASSUM-ATTENDED-ADAPTER-ID` in [design.md §12](../design.md).

## Links

- ADR-ARCH-027 — attended-only cloud escape hatch
- ADR-ARCH-022 — belt+braces constitutional rules
- ADR-ARCH-023 — permissions constitutional, not reasoning-adjustable
- ADR-ARCH-030 — budget envelope (£20–£50/month attended)
- FEAT-JARVIS-002 design §5 DDR-005 — reserved slot note
