# Graphiti Knowledge Query Integration

## Description

Jarvis ecosystem components must be able to query Graphiti for prior decisions, architectural memory, and other stored context when a request needs recall rather than fresh generation. In the documented design this capability is primarily surfaced through the General Purpose Agent's Knowledge Query tool and through architecture-oriented workflows that benefit from persistent memory.

## Bounded Context

Knowledge Context

## Source Documents

- general-purpose-agent.md
- jarvis-architecture-conversation-starter.md
- jarvis-vision.md

## Constraints

- Graphiti is an external knowledge backend in the documented C4 views.
- Knowledge query is a cross-agent tool rather than a replacement for routing.
- Jarvis conversation context strategy remains an open decision.

## Dependencies

None

## Suggested Context Files

- general-purpose-agent.md
- jarvis-architecture-conversation-starter.md
- jarvis-vision.md
