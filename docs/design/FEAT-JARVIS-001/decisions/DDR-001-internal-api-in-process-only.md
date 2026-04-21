# DDR-001: Internal Python API only — no network protocols in Phase 1

**Status:** Accepted
**Date:** 2026-04-21
**Feature:** FEAT-JARVIS-001
**Deciders:** Rich + /system-design session

---

## Context

`/system-design` by default enumerates REST, GraphQL, MCP, A2A, ACP, and Events as candidate protocol surfaces for each bounded context. FEAT-JARVIS-001 is the Phase 1 scaffolding feature — supervisor skeleton, session lifecycle, CLI, smoke tests. It exposes no network endpoints and its "Do-Not-Change" list explicitly forbids NATS, Telegram, Graphiti, subagents, and custom tools until later features.

The design question: which protocols belong in the Phase 1 design artefact set?

## Decision

Phase 1 ships **two surfaces only**:

1. **CLI** (stdin/stdout via Click) — `jarvis chat | version | health`. Documented in [API-cli.md](../contracts/API-cli.md).
2. **Internal Python API** (in-process module contracts) — `build_supervisor`, `SessionManager`, `JarvisConfig`, `AppState`, lifecycle hooks. Documented in [API-internal.md](../contracts/API-internal.md).

**Explicitly NOT shipped in Phase 1:**

| Protocol | Phase | ADR / reference |
|---|---|---|
| REST | Never at Jarvis level | [ADR-ARCH-016](../../../architecture/decisions/ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md) — NATS-only transport |
| GraphQL | Never | Same |
| MCP | Never at Jarvis level | [ARCHITECTURE.md §7](../../../architecture/ARCHITECTURE.md) — "would overflow context; matches Forge ADR-ARCH-012" |
| A2A / ACP | Never | Same — NATS req/reply is the fleet-level delegation protocol |
| NATS events (publish) | FEAT-JARVIS-004 onwards | [phase1-build-plan Do-Not-Change](../../../research/ideas/phase1-build-plan.md) rule 9 |
| NATS events (consume) | FEAT-JARVIS-004 (`jarvis.command.*`) / FEAT-JARVIS-006 (Telegram adapter) | Same |

Consequently: no OpenAPI spec, no MCP tool definitions, no A2A task schemas are generated as Phase 1 artefacts. The `/system-design` command would normally produce `docs/design/openapi.yaml`, `mcp-tools.json`, `a2a-schemas.yaml` — this DDR is the explicit record of their non-applicability.

## Rationale

- Phase 1's goal is *"Rich can have a useful conversation with it on day 1, even if it can't dispatch to anything yet"* — the CLI `chat` REPL suffices. Adding network surfaces before that bar is met delays the day-1 criterion without adding user-facing value.
- Every network surface Jarvis will ever expose is NATS-based (ADR-ARCH-016). Adding REST/GraphQL/MCP contracts would contradict the architecture, not just anticipate it.
- Internal module contracts are still worth documenting because FEAT-JARVIS-002..007 are consumers of them. Getting the `SessionManager` signature right in Phase 1 avoids churn when FEAT-JARVIS-006 Telegram adapter integrates.

## Alternatives considered

1. **Generate an OpenAPI spec covering the CLI as a "command API".** *(Rejected)* — OpenAPI is a HTTP contract format; CLI-over-stdin is not a fit. The CLI contract is better expressed as command + stdout/stderr / exit-code tables.
2. **Pre-declare NATS subjects Phase 1 will eventually publish/consume** (`jarvis.command.cli`, `notifications.cli`). *(Rejected for Phase 1)* — matches [FEAT-JARVIS-006 adapter scope](../../../research/ideas/phase1-build-plan.md). Declaring subjects without the adapter that publishes them is speculation; FEAT-JARVIS-004 will declare them with the wiring in the same feature.
3. **Ship a minimal MCP tool definition so Claude Code can talk to Jarvis.** *(Considered, deferred)* — plausible v1.5 integration, but requires MCP server scaffolding that contradicts ADR-ARCH-016. Revisit if fleet-wide MCP surfaces land.

## Consequences

- The `/system-design` command's `openapi.yaml` / `mcp-tools.json` / `a2a-schemas.yaml` artefacts are intentionally absent. Review tools that check for their presence must be told this DDR exists.
- FEAT-JARVIS-006 Telegram adapter is the first feature to publish on NATS — its design session will produce the first genuine `Events` protocol surface for Jarvis. Expect that design pass to generate a subject-registry artefact.
- The internal Python API surface (`API-internal.md`) becomes the binding contract between Phase 1 and Phase 2+ features. Any change to `SessionManager` or `build_supervisor` signature between features requires updating this design doc + a successor DDR.

## Related

- [API-cli.md](../contracts/API-cli.md)
- [API-internal.md](../contracts/API-internal.md)
- [ADR-ARCH-016](../../../architecture/decisions/ADR-ARCH-016-six-consumer-surfaces-nats-only-transport.md)
- [phase1-build-plan.md Do-Not-Change rule 9](../../../research/ideas/phase1-build-plan.md)
