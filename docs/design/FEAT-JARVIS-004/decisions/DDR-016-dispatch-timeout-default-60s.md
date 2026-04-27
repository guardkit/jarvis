# DDR-016 — `dispatch_by_capability` default timeout = 60s

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** ADR-ARCH-015 (capability-driven dispatch — Forge), ADR-ARCH-021 (tools return structured errors), [DDR-005](../../FEAT-JARVIS-002/decisions/DDR-005-dispatch-by-capability-supersedes-call-specialist.md), [DDR-017](DDR-017-retry-with-redirect-policy.md), [DDR-020](DDR-020-concurrent-dispatch-cap-8.md)
- **Supersedes:** none

## Context

Phase 2 ([FEAT-JARVIS-002](../../FEAT-JARVIS-002/design.md)) shipped `dispatch_by_capability` with `timeout_seconds: int = 60` and validation range 5..600. The body was stubbed — the timeout was not exercised against real transport.

Phase 3 lights up the real NATS round-trip. The scope-doc names the timeout default as an open question for `/system-design`: "30s? 60s? 120s? Depends on specialist-agent typical response latency."

The Forge ARCH-015 capability-driven dispatch pattern (which Jarvis inherits) targets specialists that typically reply within 5–60s of "real work". Architects generating C4 diagrams take ~30s. Product owners reviewing specs take ~15s. Ideation runs are the longest at ~45–60s. The 600s ceiling exists for outliers (long-running architecture sessions on complex domains).

The retry-with-redirect policy (DDR-017) caps wall-clock at ~2× timeout for the worst case (timeout → redirect → second-specialist-also-times-out → exhausted). At 60s default that's 120s — within the conversational-attention window for an attended session.

## Decision

`dispatch_by_capability`'s default `timeout_seconds` is **60**. Validation range stays 5..600 (Phase 2 invariant). The reasoning model can override per-call when the dispatch is known to be quick (e.g. `timeout_seconds=15` for trivial lookups) or known to be slow (e.g. `timeout_seconds=180` for long ideation runs).

The default lives on the `@tool` parameter literal — **not** on `JarvisConfig.specialist_dispatch_timeout_seconds`. The config field is a **hint** the supervisor prompt teaches the reasoning model about ("typical timeout"); the actual per-call timeout is reasoning-controlled. This preserves the ADR-ARCH-023 stance that reasoning-tunable parameters belong in tool args, not behavioural config.

## Rationale

- **60s covers the typical specialist round-trip.** Architects, product owners, and ideation specialists all reply within this envelope per Forge's observed latencies.
- **Headroom for retry-with-redirect.** With 1 redirect (DDR-017), worst-case wall-clock is 120s — still within attended-conversation tolerance.
- **30s is too aggressive.** Long C4 generations would consistently timeout-and-redirect, burning a redirect attempt on a successful specialist.
- **120s is too long.** Doubles the worst-case wall-clock to 240s; degrades the attended UX without proportional reliability gain.
- **The 5..600 range is preserved.** Reasoning can opt into either extreme per-call without DDR change.

## Alternatives considered

| Option | Why not |
|---|---|
| 30s default | Too aggressive — would fire retry-with-redirect on architects' typical 30s replies; high false-timeout rate |
| 120s default | Doubles worst-case wall-clock for negligible reliability gain; degrades attended UX |
| Move default to `JarvisConfig` | Conflicts with ADR-ARCH-023 (reasoning-tunable parameters belong in tool args). Config can carry a *hint* the prompt teaches ("typical timeout"), not the runtime default |
| Per-capability defaults | Premature — the catalogue is small in v1; per-cap timeouts would multiply DDRs without observable gain. Revisit when `jarvis.learning` lands (FEAT-J008) and per-spec timeout patterns surface |

## Consequences

- The Phase 2 tool docstring's `timeout_seconds: …Default 60.` line is unchanged. Reasoning-model behaviour is unaffected by the body swap.
- DDR-017's retry policy is bounded by this timeout × max-redirects → 120s worst case.
- Tests in `tests/test_dispatch_by_capability_integration.py` use a reduced timeout (e.g. 1s) for the timeout-path scenarios; the production default is asserted by `tests/test_dispatch_by_capability.py::test_default_timeout_is_60`.
- `JarvisConfig.specialist_dispatch_timeout_seconds` (default 60, range 5..600) is added as a hint surface — not consumed by the tool body in v1; reserved for the supervisor prompt's "typical timeout" teaching once `jarvis.learning` lands.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. Append-only — change requires a new DDR.
