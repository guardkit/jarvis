# Containerised Fleet Deployment Sequence

## Description

Jarvis and its fleet must be deployable as Docker containers with NATS infrastructure, streams, KV buckets, and fleet compose support in the documented build order. The deployment sequence needs to enable overlapping delivery after NATS is available while preserving the expectation that agents auto-register on startup.

## Bounded Context

Fleet Coordination

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Containerisation in Docker is a carried-forward decision.
- The router depends on at least one agent being dispatchable.
- Build order starts with GuardKit Factory and NATS infrastructure before Jarvis router and broader fleet expansion.

## Dependencies

- FEAT-PO-005
- FEAT-PO-007

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
