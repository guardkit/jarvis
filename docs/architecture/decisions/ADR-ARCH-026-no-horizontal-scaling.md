# ADR-ARCH-026: No horizontal scaling — single instance per user per GB10

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Mirrors:** Forge ADR-ARCH-027

## Context

Jarvis is Rich's personal assistant. Horizontal scaling (multiple supervisor instances behind a load balancer) would require distributed state coordination (shared Memory Store, cross-instance session routing, cross-instance ambient-watcher deduplication), none of which Jarvis needs.

## Decision

**One Jarvis supervisor per user per GB10.** Fleet growth means adding more operators (each with their own Jarvis), not scaling one Jarvis across multiple hosts or processes.

Single-instance constraints:
- Single `langgraph.json` deployment
- Single supervisor container
- Single per-user Memory Store on local disk
- Ambient watchers live in the single supervisor process (non-durable across restart — ADR-ARCH-028)

## Alternatives considered

1. **Active-passive failover** *(rejected)*: No availability requirement justifies it; best-effort SLA posture.
2. **Sharding by session id** *(rejected)*: Single operator; single machine; no sharding value.

## Consequences

- Simple deployment model.
- Single point of failure — GB10 uptime / llama-swap uptime are the bounds on Jarvis availability.
- Future multi-user (James, Mark) means deploying separate Jarvis instances per user, not scaling one.
