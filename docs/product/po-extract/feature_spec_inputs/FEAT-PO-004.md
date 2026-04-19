# Dispatch and Result Return Routing

## Description

Jarvis must publish classified intents and dispatch messages to `jarvis.dispatch.{agent}`, then consume `agents.results.{agent}` and notifications so responses return through the originating adapter. This response router is what makes the fleet feel like one assistant rather than a disconnected set of containers.

## Bounded Context

Intent Routing

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Subject contracts are explicit architectural interfaces and not incidental implementation details.
- Response routing must preserve adapter and correlation context.
- Notifications and agent results must both be routable back to the correct adapter.

## Dependencies

- FEAT-PO-001
- FEAT-PO-003
- FEAT-PO-005

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
