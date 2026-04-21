# ADR-ARCH-017: Static skill declaration for v1

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Resolves:** JA4 (skill discoverability)

## Context

DeepAgents 0.5.3 exposes Skills as first-class capability — reusable workflows, domain knowledge, and custom instructions the agent can invoke. Jarvis v1 ships with three: `morning-briefing`, `talk-prep`, `project-status`. The question is static declaration vs dynamic registration (symmetric with fleet.register).

## Decision

**Static declaration for v1.** Skills are declared as Python modules or static YAML at supervisor startup. No dynamic KV-based registration.

Skill authoring format: aligns with DeepAgents' native Skills primitive. Each skill composes existing dispatch targets + Memory Store reads + Graphiti queries into a named capability.

Revisit dynamic-registration (JA4) once skill count grows beyond ~5–7 or cross-repo skill sharing becomes a real pattern.

## Alternatives considered

1. **Dynamic registration via NATS KV (like fleet)** *(rejected for v1)*: Symmetric with `agent-registry` KV. More powerful (hot-swap new skills without restart). Substantial infrastructure for three launch skills.
2. **DeepAgents native Skills primitive only** *(accepted as underlying mechanism)*: Use whatever DeepAgents 0.5.3 exposes; don't wrap.

## Consequences

- Three launch skills (`morning-briefing`, `talk-prep`, `project-status`) declared in Python — versioned in source control, tested in CI.
- Adding a skill requires a supervisor restart (acceptable for v1 skill cadence).
- `morning-briefing` is the candidate Pattern C graduation target — initially Rich-triggered, potentially scheduled later (ADR-J-P8).
- Dynamic-registration option stays open for v1.5+.
