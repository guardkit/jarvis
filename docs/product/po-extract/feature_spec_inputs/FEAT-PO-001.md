# Adapter Command Ingress and Correlation Handling

## Description

Jarvis must consume `jarvis.command.{adapter}` requests from all supported adapters and normalise them into a common command envelope with correlation and session metadata. This ingress path is the front door of the intent router and is responsible for preserving the originating adapter so results can be routed back through the correct modality.

## Bounded Context

Intent Routing

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Jarvis must remain a thin orchestration layer rather than a monolithic agent.
- Adapters are stateless translators and should not own business logic.
- Requests originate from multiple modalities and must preserve adapter identity for return-path routing.

## Dependencies

None

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
- reachy-mini-integration.md
