# DM-stub-registry — `stub_capabilities.yaml` Schema

> **Path:** `src/jarvis/config/stub_capabilities.yaml`
> **Lifetime:** Phase 2 only. Removed when FEAT-JARVIS-004 wires `NATSKVManifestRegistry`.
> **Loader:** `jarvis.tools.capabilities.load_stub_registry(path) -> list[CapabilityDescriptor]`.

---

## Why a file, not a constant

A YAML file rather than a Python constant lets tests swap the registry without monkeypatching, and keeps the stub data in a format **identical** to what an operator would paste into a debug fixture when investigating a production issue once the real registry arrives. YAML was chosen over JSON for comment support — the stub entries include justification comments linking to the specialist-agent role that inspired each.

---

## Schema

Root is a mapping with two keys:

```yaml
version: "1.0"
capabilities:
  - agent_id: <kebab-case>
    role: <free-form>
    description: <free-form, 1+ paragraphs>
    capability_list:
      - tool_name: <snake_case>
        description: <free-form>
        risk_level: read_only | mutating | destructive  # optional, default read_only
    cost_signal: <free-form>                            # e.g. "low", "~$0.10/call"
    latency_signal: <free-form>                         # e.g. "5-30s", "sub-second"
    last_heartbeat_at: null                             # always null in Phase 2
    trust_tier: core | specialist | extension           # default specialist
```

Each element under `capabilities` is validated against `CapabilityDescriptor` on load. Missing required fields or malformed `agent_id` raise `pydantic.ValidationError` at startup — this is startup-fatal (same posture as a missing model API key in Phase 1).

---

## Canonical Phase 2 content (AutoBuild starting point)

This is the shape AutoBuild produces for Phase 2. Values are informed by [phase2-dispatch-foundations-scope.md §2.2](../../research/ideas/phase2-dispatch-foundations-scope.md) — "four stubbed descriptors (architect, product-owner, ideation shapes) plus one for Forge". Feature-spec MAY refine descriptions but the agent_id + tool_name keys must remain stable for the routing e2e test in FEAT-JARVIS-003.

```yaml
version: "1.0"
capabilities:

  - agent_id: architect-agent
    role: Architect
    description: >
      Produces architecture sessions, C4 diagrams, and ADRs for features. Best
      for "design the system for X", "generate a C4 diagram", "review this
      architecture against the ADR set". Not for implementation.
    capability_list:
      - tool_name: run_architecture_session
        description: Drive a full /system-arch session from a scope document and emit ARCHITECTURE.md + ADRs.
        risk_level: read_only
      - tool_name: draft_adr
        description: Given a decision + context, emit a single ADR file.
        risk_level: mutating
    cost_signal: "moderate (~$0.50-$2 per session)"
    latency_signal: "5-30 minutes per session"
    last_heartbeat_at: null
    trust_tier: specialist

  - agent_id: product-owner-agent
    role: Product Owner
    description: >
      Reviews feature specifications, prioritises work, and refines acceptance
      criteria. Best for "is this spec complete?", "what's missing from this
      feature?", "should we build X or Y first?". Not for architectural
      decisions.
    capability_list:
      - tool_name: review_specification
        description: Evaluate a feature spec for completeness, clarity, and priority.
        risk_level: read_only
      - tool_name: refine_acceptance_criteria
        description: Expand or tighten the Given/When/Then scenarios in a feature spec.
        risk_level: mutating
    cost_signal: "low (~$0.10/call)"
    latency_signal: "30s-2min"
    last_heartbeat_at: null
    trust_tier: specialist

  - agent_id: ideation-agent
    role: Ideation
    description: >
      Generates candidate solutions, alternatives, and counter-examples. Best
      for "what are our options here?", "steelman the opposing view", "what
      could go wrong?". Not for committing to a decision — delegate that back
      to Rich or to the architect.
    capability_list:
      - tool_name: generate_alternatives
        description: Produce 3-5 distinct candidate approaches to a stated problem.
        risk_level: read_only
      - tool_name: steelman
        description: Construct the strongest possible argument for the opposing position.
        risk_level: read_only
    cost_signal: "low (~$0.05/call)"
    latency_signal: "10-30s"
    last_heartbeat_at: null
    trust_tier: specialist

  - agent_id: forge
    role: Build Pipeline
    description: >
      Executes feature builds end-to-end given a feature YAML. Consumes
      pipeline.build-queued.{feature_id} from JetStream. Jarvis queues; Forge
      does the work. Fire-and-forget — progress events arrive via
      notifications, not by awaiting this dispatch.
    capability_list:
      - tool_name: build_feature
        description: >
          Synonym surfacing the queue_build tool's semantics into the catalogue so the
          reasoning model can reason about "Forge" as a dispatch target
          alongside specialist agents. In practice the reasoning model will
          invoke the dedicated queue_build tool rather than dispatch_by_capability.
        risk_level: mutating
    cost_signal: "high (full GuardKit AutoBuild run)"
    latency_signal: "15-180min"
    last_heartbeat_at: null
    trust_tier: core
```

---

## Rationale for the fourth entry (Forge)

Including `forge` as a capability entry even though `queue_build` is a dedicated tool (not `dispatch_by_capability`) serves two purposes:

1. **Routing test coverage** — FEAT-JARVIS-003's `test_routing_e2e.py` asserts the reasoning model reads the catalogue before picking a dispatch target. Having Forge visible in the catalogue exercises the case where the model sees multiple dispatch targets side-by-side and correctly uses the dedicated `queue_build` tool rather than `dispatch_by_capability`.
2. **FEAT-JARVIS-005 continuity** — when the real `NATSKVManifestRegistry` lights up, Forge already registers itself on `fleet.register`. The catalogue will include Forge automatically. Having a stub entry keeps Phase 2's reasoning-model behaviour identical to Phase 3+.

---

## Validation tests

- Roundtrip: YAML → `list[CapabilityDescriptor]` → dump → compare.
- Reject malformed `agent_id` (e.g. `Architect` with capital).
- Reject unknown `risk_level`.
- Reject `last_heartbeat_at` set to a non-ISO-8601 value (but `null` always valid).
- Reject duplicate `agent_id` entries (deduplication is the loader's job; violates the CapabilityDescriptor's implicit identity).
- Tolerate unknown keys (ConfigDict extra="ignore") so a future field published by a real AgentManifest doesn't break Phase 2 loaders.
