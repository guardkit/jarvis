# DDR-021 — NATS unavailable → soft-fail at startup; capability registry falls back to stub YAML

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** ADR-ARCH-021 (tools return structured errors), ADR-ARCH-016 (NATS-only transport), ADR-ARCH-026 (single instance), [DDR-019](DDR-019-graphiti-fire-and-forget-writes.md), [FEAT-JARVIS-002 stub_capabilities.yaml](../../../../src/jarvis/config/stub_capabilities.yaml)

## Context

NATS on GB10 is the foundation of Jarvis's outbound dispatch surface. But:

- It might be down (GB10 reboot, network blip, NATS upgrade).
- The user might run Jarvis on a laptop without Tailscale connectivity.
- Tests run in environments without a NATS server.

If NATS is unavailable at startup:
- Hard-failing breaks the "Jarvis is at minimum a useful chat surface" UX.
- Silent-failing breaks the "no silent failures" promise from the scope-doc Do-Not-Change list.
- The capability catalogue becomes invisible (no live KV reads).

ADR-ARCH-021 says tools return structured errors. The NATS-unavailable case must produce one — visible to the reasoning model, parseable, ADR-compliant.

The Phase 2 stub YAML at `src/jarvis/config/stub_capabilities.yaml` was scoped as a fallback for tests + local dev. Phase 3's NATS soft-fail path is the production reuse of that fallback.

## Decision

1. **NATS unavailable at startup → soft-fail.**
   - `NATSClient.connect(config)` returns `None` on connection failure (exceptions logged as `ERROR nats_connect_failed reason=<exc-class>` once at startup).
   - Lifecycle continues — supervisor builds, sessions start, attended chat works.
2. **Dispatch tools return structured errors when NATS is `None`:**
   - `dispatch_by_capability` → `"DEGRADED: transport_unavailable — NATS connection failed"`
   - `queue_build` (after FEAT-J005 swap) → similar `DEGRADED: transport_unavailable — JetStream publish failed`
3. **Capability registry falls back to the stub YAML.**
   - `LiveCapabilitiesRegistry.create(...)` is not constructed when NATS is `None`.
   - `StubCapabilitiesRegistry(config.stub_capabilities_path)` is used instead — same `CapabilitiesRegistry` Protocol, transparent to the rest of the system.
   - `list_available_capabilities` returns the stub list (not empty); the reasoning model still sees a non-trivial catalogue.
   - `capabilities_refresh()` returns `"DEGRADED: transport_unavailable — NATS connection failed"`.
   - `capabilities_subscribe_updates()` returns `"OK: subscribed (stub mode — no live updates)"` (no-op semantics preserved).
4. **Fleet registration is skipped.** Jarvis cannot publish to `fleet.register` without NATS. A WARN log records the skip; heartbeat task is `None`.
5. **Frontier escape (`escalate_to_frontier`) still works** — it has no NATS dependency. Attended sessions can still ask Gemini / Opus directly.
6. **Local subagent dispatch (`start_async_task` / `jarvis_reasoner`) still works** — local llama-swap is independent of NATS.
7. **Reconnect at runtime is NOT attempted in v1.** Once Jarvis starts in "no-NATS" mode, it stays there until restart. A reconnect strategy is operator-driven (restart Jarvis after fixing NATS).

## Rationale

- **Soft-fail preserves the attended-chat UX.** Rich can still talk to Jarvis, ask local-subagent questions, escalate to frontier, calculate, read files, search the web — only outbound fleet dispatch is dead. That's a useful subset.
- **Falling back to the stub YAML is the right fallback shape.** It already exists, has a documented schema, and the tests already exercise it. Reusing it as the production-soft-fail catalogue costs nothing and gives a non-empty list to the reasoning model.
- **Visible structured errors over silent failures.** The DEGRADED string is parsable; the reasoning model handles it the same way it handles every other DEGRADED branch (per the FEAT-J002 supervisor prompt teaching).
- **No runtime reconnect in v1** — adds complexity (when to retry? exponential backoff parameters? does the catalogue refresh when reconnect succeeds?) without proportional value. v1 is "operator restart on infrastructure changes"; v1.5 can add reconnect if real-world operational pain warrants.
- **Skip fleet registration** rather than buffering — re-publishing on reconnect would need a buffer; v1 has no reconnect.
- **Frontier + local subagent independence** is a free property — no design effort to preserve, but worth calling out so the reasoning model's tool surface is documented under degraded modes.

## Alternatives considered

| Option | Why not |
|---|---|
| Hard-fail on NATS unreachable | Breaks the "minimum useful chat surface" UX; an operator-friendly system stays up where it can |
| Empty capability registry on soft-fail | Reasoning model sees no capabilities; degrades the dispatch reasoning quality even when the user isn't asking for fleet work |
| Runtime reconnect with exponential backoff | Adds complexity; reconnection-on-fleet-membership-change semantics are non-trivial; v1.5 territory |
| Cache the last live registry snapshot to disk (warm restart) | Adds state; ADR-ARCH-008 (no SQLite) implies "no persistent state outside Graphiti / Memory Store"; contradicts that posture |
| Warn-only (no DEGRADED return) on dispatch | Reasoning model has no way to know dispatch failed; tries again; same outcome |

## Consequences

- `infrastructure/nats_client.py::NATSClient.connect` returns `Optional[NATSClient]`; lifecycle handles `None`.
- `infrastructure/capabilities_registry.py` exposes `LiveCapabilitiesRegistry` + `StubCapabilitiesRegistry` behind the `CapabilitiesRegistry` Protocol.
- `tools/dispatch.py` checks `if _nats_client is None` early in dispatch and returns DEGRADED string.
- `tests/test_nats_unavailable.py` is the soft-fail acceptance gate: Jarvis starts; chat works; dispatch returns DEGRADED; capabilities returns stub list; frontier works on attended sessions; trace writes work or skip correctly per DDR-019.
- The supervisor prompt's existing teaching about DEGRADED responses requires no edit — the new strings follow the same shape the reasoning model already handles.
- Combined NATS-down + Graphiti-down scenario (see `tests/test_lifecycle_partial_failure.py`) — Jarvis still starts; only attended chat + frontier escape + local subagent + Phase 2 deterministic tools function. Trace writes degrade per DDR-019; dispatch degrades per DDR-021.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. Reconnect strategy is a v1.5 candidate if operational pain warrants — append-only DDR.
