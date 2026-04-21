# ADR-ARCH-006: Five-group module layout mirroring Forge

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Clean/Hexagonal (ADR-ARCH-002) gives a pattern; module organisation gives a concrete layout. Forge uses five module groups (DeepAgents Shell / Domain Core / Tool Layer / Adapters / Cross-cutting). Jarvis benefits from the same layout for fleet-coherence and developer ergonomics.

## Decision

Five groups:

**A. DeepAgents Shell:** `jarvis.agent`, `jarvis.prompts`, `jarvis.subagents` (one: `jarvis_reasoner`), `jarvis.skills`

**B. Domain Core** (pure, no I/O imports): `jarvis.routing`, `jarvis.watchers`, `jarvis.learning`, `jarvis.discovery`, `jarvis.sessions`

**C. Tool Layer** (`@tool(parse_docstring=True)` functions): `jarvis.tools.dispatch`, `jarvis.tools.graphiti`, `jarvis.tools.external`, `jarvis.tools.notifications`

**D. Adapters** (I/O edges): `jarvis.adapters.nats`, `jarvis.adapters.graphiti`, `jarvis.adapters.llamaswap`. Plus separate containers for adapter services (`telegram`, `cli`, `dashboard`, `reachy`) built from `nats-asyncio-service` template.

**E. Cross-cutting:** `jarvis.config`, `jarvis.fleet`, `jarvis.cli`

## Alternatives considered

1. **Flat module layout** *(rejected)*: Loses the hexagonal boundary at code level; harder to enforce domain-purity lint rules.
2. **Different grouping (e.g. one module per bounded context)** *(rejected)*: Context-to-module is not 1:1 (e.g. Ambient Monitoring spans `jarvis.watchers` + `jarvis.subagents` + `jarvis.tools.dispatch`). Layer grouping is orthogonal and compatible with context grouping via naming.

## Consequences

- Lint rules can enforce "group B may not import from groups C/D" (pure domain).
- Fleet-wide coherence — Forge developers onboard to Jarvis quickly.
- Module additions land in obvious groups; reviewers check the group-constraint during PR review.
