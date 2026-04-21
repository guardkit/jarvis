# ADR-ARCH-016: Six consumer surfaces; NATS-only transport at Jarvis level

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session

## Context

Jarvis serves multiple consumer types (Rich through adapters, fleet peers, future cross-agent delegators). The question is transport: one per consumer type, or uniform NATS everywhere?

## Decision

**Uniform NATS transport** at the Jarvis level. Six consumer surfaces:

1. **Rich via Telegram** — `jarvis.command.telegram` / `notifications.telegram`
2. **Rich via CLI** — `jarvis.command.cli` / `notifications.cli`
3. **Rich via Dashboard** — `jarvis.command.dashboard` / `notifications.dashboard` + read-only subscribe to trace streams
4. **Rich via Reachy** — `jarvis.command.reachy` / `notifications.reachy`
5. **Operator CLI** — Click CLI (reads Graphiti directly; writes via NATS)
6. **Fleet peers** — `agents.command.jarvis` (inbound delegation); `agents.command.{specialist_id}` + `pipeline.build-queued.*` (outbound dispatch)

The adapter services (Telegram/CLI/Dashboard/Reachy) bridge native protocols to NATS. Jarvis itself speaks NATS for commands, dispatches, notifications, and fleet integration.

**Explicitly NOT used at Jarvis level:**
- **MCP** — Jarvis-level MCP would overflow context (matches Forge ADR-ARCH-012). Individual `@tool`s may later be re-exposed as MCP to external clients, but not as a Jarvis-level interface.
- **HTTP/REST** — No direct HTTP server in Jarvis. The Dashboard adapter service bridges WebSocket↔NATS.
- **gRPC** — No need; NATS covers the performance envelope.

## Alternatives considered

1. **HTTP/REST API for human surfaces + NATS for fleet** *(rejected)*: Duplicates transport; two sets of auth/authz concerns; adapters already bridge native protocols.
2. **MCP at Jarvis level** *(rejected)*: Context-window overflow risk (same as Forge); tools-as-MCP is compatible later.

## Consequences

- One transport, one auth model (NATS account-based — APPMILLA account).
- Fleet peers and adapters share the same bus — Rich's Telegram message and Forge's build completion notification use the same publish/subscribe primitives.
- Adapter services become the compatibility layer with native modality protocols; Jarvis stays transport-clean.
- Future MCP re-exposure of individual tools (e.g. for Claude Desktop access to Jarvis's knowledge queries) remains available without rearchitecting.
