# NATS JetStream Backbone Provisioning

## Description

Jarvis must run on NATS JetStream as the backbone for commands, dispatches, fleet lifecycle events, notifications, approvals, and health monitoring. The runtime needs streams, consumers, and KV buckets that support the documented CAN bus registration pattern and persistent routing metadata across restarts.

## Bounded Context

Infrastructure and Runtime

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- NATS JetStream is a resolved architectural decision that should not be reopened.
- The `agent-registry` KV bucket is part of the authoritative routing substrate.
- Subject structure must support commands, dispatch, registration, heartbeat, results, notifications, and health.

## Dependencies

- FEAT-PO-007

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
