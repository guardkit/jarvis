# ADR-ARCH-014: Docker-on-GB10 single-instance deployment

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

The fleet runs on GB10 (128 GB unified memory, Blackwell SM121). Jarvis joins Forge, specialist-agent, NATS, llama-swap + model servers, FalkorDB, and ChromaDB as co-located services. Kubernetes is overkill for a single operator / single host.

## Decision

Deploy via **Docker on GB10**. One `docker compose` manifest covers:
- Jarvis supervisor container (includes NATS + Graphiti adapters)
- Four adapter service containers (telegram, cli, dashboard, reachy — last one hardware-gated)
- (Neighbours, managed separately but co-located: Forge, specialist-agent, llama-swap, vLLM, FalkorDB)

No Kubernetes, no horizontal scaling, no auto-scaling. Deployment is manual `docker compose up` by the operator (Rich). Single-instance constraint mirrors Forge ADR-ARCH-027.

## Alternatives considered

1. **Kubernetes (k3s / k8s)** *(rejected)*: Significant operational overhead for single-operator personal use; no scaling requirement.
2. **Bare metal processes with systemd** *(considered, partially adopted for llama-swap)*: llama-swap runs via systemd (ADR-ARCH-001 reference); Jarvis + adapters stay containerised for dependency isolation.
3. **Nomad or similar orchestrator** *(rejected)*: Same rationale as Kubernetes.

## Consequences

- Simple ops model: `docker compose up`, `docker compose logs`, `docker compose restart`.
- Tailscale mesh provides cross-host networking for MacBook Pro (operator CLI) and NAS (backup).
- Future multi-host (second GB10, second operator) requires a deployment rethink — deferred.
- Forge parity (ADR-ARCH-011/027) keeps fleet ops consistent.
