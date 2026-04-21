# ADR-ARCH-002: Clean/Hexagonal modules within DeepAgents supervisor

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Jarvis needs a structural pattern that (a) makes the `create_deep_agent(...)` supervisor the shell, (b) keeps domain logic pure and testable, (c) matches Forge's structure for fleet-coherence, and (d) allows DDD elements (bounded contexts, context map) to be applied without ceremony overload.

## Decision

Clean/Hexagonal with DDD elements, mirroring Forge ADR-ARCH-001:

- The `create_deep_agent(...)` `CompiledStateGraph` is the shell — reasoning loop, built-in tools, AsyncSubAgent dispatch, Memory Store, Skills.
- Inside: pure domain modules (routing, watchers, learning, discovery, sessions) with **no I/O imports**.
- Thin adapters at the edges (NATS, Graphiti, llama-swap HTTP).
- Jarvis-specific `@tool` functions wrap adapters at the DeepAgents tool-layer boundary.
- **No transport abstraction** — NATS is the control-plane bus, llama-swap is the data-plane inference front door; neither is a replaceable plugin.
- DDD elements (seven bounded contexts, DDD context map, published language via `nats-core`) are applied **within** the Clean/Hexagonal shell.

## Alternatives considered

1. **Pure DDD with aggregates/repositories/domain-event bus** *(rejected)*: Higher ceremony; less consistent with Forge's pattern.
2. **Modular Monolith (no hex split)** *(rejected)*: Simpler, but loses testability and the swap-ability Forge's pattern provides.
3. **Add transport abstraction (swap NATS for Kafka later)** *(rejected)*: NATS is permanent substrate choice; abstraction would be speculative.

## Consequences

- Fleet-wide structural coherence — developers moving between Forge and Jarvis see the same module shape.
- Pure domain modules are fully unit-testable without mocks for NATS/Graphiti/LLM.
- Hexagonal boundary at code level is enforced by lint rules: domain modules may not import adapter modules.
- DDD context map keeps cross-module interaction legible as the codebase grows.
