# ADR-ARCH-004: Jarvis registers on fleet.register for cross-agent delegation

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Jarvis needs to be discoverable by other fleet agents (Forge, specialists, future agents) for two reasons: (a) outbound notifications routed through known-as-Jarvis registration (Forge can emit `jarvis.notification.*` knowing Jarvis is the adapter-routing surface); (b) future cross-agent delegation of GPA-level tasks back to Jarvis.

## Decision

Jarvis publishes an `AgentManifest` to `fleet.register` with:
- `agent_id`: `jarvis`
- `intents`: GPA-level intent capabilities (e.g. `route-to-adapter`, `summarise-session`, `surface-user-preference`)
- `tools`: exposed tools that other agents may invoke
- Heartbeat per `nats-core` contract

Other agents discover Jarvis via the `agent-registry` KV bucket with 30s cache + watch invalidation.

## Alternatives considered

1. **Jarvis-as-special-case-non-registrant** *(rejected)*: Breaks the uniform pattern. Makes Forge and specialists treat Jarvis differently from other agents, adds conditional paths.

## Consequences

- Jarvis appears in fleet-discovery listings like any other agent.
- Future agents can delegate GPA-level reasoning to Jarvis (e.g. "Jarvis, summarise what Rich and I discussed last session") without hard-coding the `jarvis` agent_id.
- Aligns Jarvis with the fleet's capability-driven-dispatch pattern (Forge ADR-ARCH-015).
- Adds a small heartbeat overhead and requires Jarvis to handle inbound `agents.command.jarvis` messages.
