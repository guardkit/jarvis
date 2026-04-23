# DDR-005: Dispatch tool is `dispatch_by_capability`, superseding scope-doc `call_specialist`

- **Status:** Accepted
- **Date:** 2026-04-23
- **Session:** `/system-design FEAT-JARVIS-002`
- **Related components:** Fleet Dispatch Context; `jarvis.tools.dispatch`
- **Supersedes (within scope doc only):** [phase2-dispatch-foundations-scope.md §1.3](../../../research/ideas/phase2-dispatch-foundations-scope.md) `call_specialist(agent_id, instruction, context={})`
- **Related ADRs:** ADR-ARCH-003 (Jarvis-IS-GPA); ADR-ARCH-016 (NATS-only transport); Forge ADR-ARCH-015 (capability-driven dispatch, adopted fleet-wide); Forge ADR-ARCH-016 (fleet-is-the-catalogue)

## Context

The Phase 2 scope document (20 April 2026) predates the final `/system-arch` session (also 20 April, produced ADR-ARCH-001..030). Between the scope being drafted and ARCHITECTURE.md v1.0 being signed off, the fleet-wide pattern was pinned:

- [ARCHITECTURE.md §3.C](../../../architecture/ARCHITECTURE.md) calls the tool `dispatch_by_capability`.
- Forge's ADR-ARCH-015 (19 April) forbids hardcoded `agent_id`: *"one generic dispatch tool covers every specialist, present and future"*.
- Forge's ADR-ARCH-016 requires the catalogue to be the fleet, not a declared list in code.

The scope doc's proposed signature — `call_specialist(agent_id: str, instruction: str, context: dict = {})` — conflicts with those constraints in two ways:

1. The first parameter is a hardcoded `agent_id` — the reasoning model would need to know which agent to talk to before it can dispatch. That inverts the capability-driven pattern.
2. The `instruction: str, context: dict` shape is an agent-generic envelope; it cannot pre-declare a tool name on the target agent, so the target agent has to do intent-extraction in addition to whatever it's being asked to do. The same `ToolCapability` primitive is available in `nats-core` and solves this cleanly.

## Decision

**Adopt `dispatch_by_capability(tool_name, payload_json, intent_pattern=None, timeout_seconds=60)` as the single generic dispatch tool for Jarvis, matching Forge ADR-ARCH-015's pattern verbatim.**

Key shape decisions:

- `tool_name: str` — maps to `nats_core.ToolCapability.name`. The reasoning model picks this by reading the prompt-injected `{available_capabilities}` block (or via `list_available_capabilities()` if mid-session refresh is needed per DDR-008).
- `payload_json: str` — a JSON-object-literal string matching the target tool's `ToolCapability.parameters` schema. Passing as a string (not a dict) preserves tool docstring readability — the reasoning model is used to constructing JSON strings for tool arguments; a structured parameter pollutes the displayed signature with a nested schema.
- `intent_pattern: str | None` — optional fallback for `IntentCapability.pattern` resolution when no exact tool match exists.
- `timeout_seconds: int = 60` — fleet-normal timeout; tests may override. Out-of-range values return a structured error rather than raising.
- No `agent_id` parameter. The tool resolves internally against the capability registry.

**Phase 2 implementation is stubbed** — see [DDR-009](DDR-009-dispatch-stub-transport-semantics.md) for transport semantics. FEAT-JARVIS-004 replaces the stub with real NATS round-trips without changing this signature.

## Alternatives considered

1. **Keep `call_specialist(agent_id, …)` as written in the scope doc.**
   Rejected — violates ADR-ARCH-015-equivalent's "no per-role tools, no hardcoded `agent_id`". Every specialist addition would require a prompt update; the learning flywheel (FEAT-JARVIS-008) couldn't measure the reasoning model's routing choices because the "which agent" decision would be baked into the tool call.

2. **Ship both `call_specialist(agent_id, …)` AND `dispatch_by_capability(...)`.**
   Rejected — doubles the surface area of the prompt ("## Tool Usage") without adding value. The reasoning model would need to be told when to prefer one over the other, which is a rule the capability pattern already subsumes.

3. **Keep the scope-doc name `call_specialist` but change the signature to match `dispatch_by_capability`.**
   Rejected — aesthetics-only. The name `dispatch_by_capability` is what ARCHITECTURE.md §3.C already uses and the specialist-agent side of the fleet expects Jarvis to call.

4. **Split `dispatch_by_capability` into two tools: one for `tool_name` exact match, one for `intent_pattern` fuzzy match.**
   Rejected — would surface a resolution-strategy choice to the reasoning model that shouldn't be its concern. The `intent_pattern` parameter is a fallback knob inside one tool, not a separate tool.

## Consequences

- **+** Jarvis's dispatch tool is name- and shape-identical to Forge's. Specialist agents and the fleet registry see one consumer contract across the two upstream surfaces.
- **+** New specialist agents register, and Jarvis picks them up without code changes. Matches the fleet-wide capability-driven pattern.
- **+** The learning flywheel (v1.5) can measure routing decisions at the capability level — the reasoning model's choice of `tool_name` is data.
- **+** The stubbed Phase 2 and real Phase 3 tool look identical to the reasoning model. Behaviour depends on docstring; transport depends on implementation.
- **−** The scope doc is now out of sync with this design. Mitigation: this DDR is the durable record; the scope doc will be updated only if a future refactor warrants.
- **−** The reasoning model must construct a valid `payload_json` for each capability. Mitigation: each `ToolCapability.description` in the injected catalogue is required to state the JSON shape — the `agent-manifest-contract` pattern already enforces this.
