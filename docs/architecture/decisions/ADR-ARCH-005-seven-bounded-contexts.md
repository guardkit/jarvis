# ADR-ARCH-005: Seven bounded contexts with DDD context map

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Jarvis's responsibilities span multiple domains — adapter translation, reasoning, dispatch, ambient monitoring, learning, knowledge storage, external integrations. Treating these as one undifferentiated module leads to cross-cutting concerns everywhere and no clear ownership.

## Decision

Seven bounded contexts, applied within the Clean/Hexagonal shell (see ADR-ARCH-002):

1. **Adapter Interface** — stateless translators (Telegram / CLI / Dashboard / Reachy)
2. **Jarvis Reasoning** — supervisor, sessions, skills, routing decisions
3. **Fleet Dispatch** — three-target dispatch (async subagents / NATS / Forge)
4. **Ambient Monitoring** — Pattern B triggered watchers, Pattern C opt-in skill seed
5. **Learning** — `jarvis.learning` module, `CalibrationAdjustment` proposals
6. **Knowledge** — Graphiti groups (`jarvis_routing_history`, `jarvis_ambient_history`, general)
7. **External Tool / API** — calendar / email / weather / HA / web search (ACL)

Context relationships (see [../domain-model.md](../domain-model.md)):
- Adapter Interface → Jarvis Reasoning (Open Host Service)
- Jarvis Reasoning → Fleet Dispatch (Customer-Supplier)
- Fleet Dispatch → Jarvis Reasoning (Published Language — `BuildQueuedPayload`, `AgentManifest`)
- Jarvis Reasoning ↔ Ambient Monitoring (Shared Kernel)
- Jarvis Reasoning + Ambient Monitoring ↔ Learning (Shared Kernel)
- Learning → Knowledge (Published Language — `CalibrationAdjustment`)
- Jarvis Reasoning → External Tool (ACL)

Aggregate roots: `Session`, `DispatchDecision`, `Watcher`, `CalibrationAdjustment`.

## Alternatives considered

1. **Single "Jarvis" context** *(rejected)*: Monolithic; no ownership; cross-cutting sprawl.
2. **Smaller set (merge Learning into Jarvis Reasoning)** *(rejected)*: Learning has distinct lifecycle (proposal → confirmation) that warrants its own aggregate root.
3. **Larger set (split Adapter Interface per adapter)** *(rejected)*: Adapters share a common domain shape (stateless translation); splitting multiplies context boundaries without clarity gain.

## Consequences

- Each module has a clear home context. Cross-context interactions follow named DDD relationship patterns.
- Testing boundaries are legible — unit tests per context, integration tests across context boundaries.
- Published Language (`nats-core` types) prevents duplicate schema definitions across contexts.
- New features land in an obvious context; cross-cutting features are explicit shared-kernel extensions.
