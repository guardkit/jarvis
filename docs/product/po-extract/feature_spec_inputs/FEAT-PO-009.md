# Stateless Multi-Adapter Translation Layer

## Description

Jarvis must support Reachy Mini, Telegram, Slack, Dashboard, CLI, and PM webhooks as thin `nats-asyncio-service` translators between native protocols and NATS messages. These adapters must remain stateless and avoid embedding routing or business logic so the router and agents remain the only intelligence-bearing components.

## Bounded Context

Adapter Interface

## Source Documents

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md

## Constraints

- Adapters are stateless translators by design.
- Supported adapters include voice, messaging, dashboard, CLI, and PM webhooks.
- The template pattern is `nats-asyncio-service`.

## Dependencies

- FEAT-PO-007

## Suggested Context Files

- jarvis-vision.md
- jarvis-architecture-conversation-starter.md
