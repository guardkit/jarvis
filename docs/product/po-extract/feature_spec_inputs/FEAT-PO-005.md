# Dynamic Agent Registration and Routing Table

## Description

Fleet agents must self-register on startup through `fleet.register`, advertise intents, signals, confidence, concurrency, and status, and have their routing metadata persisted in the `agent-registry` KV bucket. Jarvis must treat this registration substrate as authoritative so agents can be added or scaled without changing router code.

## Bounded Context

Fleet Coordination

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Dynamic registration via NATS is a resolved architectural decision.
- Routing table must survive router restarts through the `agent-registry` KV bucket.
- Bad registrations can poison routing unless payloads are validated.

## Dependencies

None

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
