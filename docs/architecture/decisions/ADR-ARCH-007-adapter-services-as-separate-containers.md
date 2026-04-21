# ADR-ARCH-007: Adapter services as separate containers

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Jarvis has four adapter surfaces (Telegram, CLI, Dashboard, Reachy Mini) with very different native-protocol dependencies — Telegram Bot API, stdin/stdout, WebSocket + React build, Whisper STT + TTS + USB hardware. Baking all of these into the Jarvis supervisor container would pull dozens of adapter-specific Python packages, node modules, and audio libraries into one image.

## Decision

Each adapter is a **separate container on GB10**, built from the `nats-asyncio-service` template. The adapter speaks the native modality protocol on one side and NATS on the other. Topics follow existing taxonomy:

- `jarvis.command.{adapter}` — inbound user input
- `notifications.{adapter}` — outbound proactive messages (routed by `correlation_id`)

Adapter services are stateless translators. Business logic lives in the Jarvis supervisor. Adapters never import `jarvis.*` modules — they only speak `nats-core` payloads.

## Alternatives considered

1. **Co-located modules in supervisor container** *(rejected)*: Pulls adapter-specific deps into the supervisor image; slow rebuild cycle; cross-adapter dependency conflicts.
2. **Split — CLI co-located, others separate** *(rejected)*: CLI is thin enough to compile in, but uniformity is more valuable than the marginal saving; the operator CLI already lives in `jarvis.cli` (different from the CLI-adapter service).

## Consequences

- Five containers on GB10: Jarvis supervisor + 4 adapter services (Reachy container ships when hardware arrives).
- Per-adapter deployment — updating the Telegram adapter doesn't require rebuilding Jarvis.
- Cross-container coordination via NATS — a natural fit since NATS is already the fleet substrate.
- Slight operational overhead (more containers to monitor) offset by dependency isolation.
