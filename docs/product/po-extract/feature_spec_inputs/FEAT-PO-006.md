# Heartbeat, Availability, and Load-Aware Selection

## Description

Registered agents must heartbeat every 30 seconds on `fleet.heartbeat.{agent_id}` with queue depth and active task data so Jarvis can track availability and balance load. Jarvis must mark agents unavailable when heartbeat policy is exceeded and use queue depth to break ties between equally suitable agents.

## Bounded Context

Fleet Coordination

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Default documented heartbeat interval is 30 seconds.
- Current documented timeout example is 90 seconds, though policy remains open.
- Queue depth and active tasks are required for load-aware selection.

## Dependencies

- FEAT-PO-005

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
