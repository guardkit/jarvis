# ADR-ARCH-025: DeepAgents 0.6 upgrade gated by compatibility review

**Status:** Accepted
**Date:** 2026-04-20
**Deciders:** Rich + /system-arch session
**Resolves:** JA8 (preview-feature migration strategy)

## Context

Jarvis depends on DeepAgents 0.5.3's `AsyncSubAgent` primitive (preview feature). Preview features may change API in minor version bumps. ADR-ARCH-010 pins `>=0.5.3, <0.6` to prevent accidental breakage.

## Decision

Before unpinning to 0.6.x:

1. **Compatibility review** — read the DeepAgents 0.6 changelog; identify all breaking changes affecting Jarvis (especially `AsyncSubAgent`, Memory Store, Skills, `task()`, permissions).
2. **Regression suite dry-run** — run the full Jarvis test suite against a 0.6 pre-release on a branch; fix any breaks.
3. **Trace-rich smoke test** — run 2–3 real Jarvis sessions end-to-end (including a Pattern B watcher firing) against 0.6 on a branch; confirm `jarvis_routing_history` entries preserve the expected schema.
4. **Single-PR unpin** — once green, one PR bumps the pin and merges.

If `AsyncSubAgent` leaves preview in 0.6 with API changes, the compatibility review includes a migration-path document before merging.

## Alternatives considered

1. **Follow DeepAgents main (eager upgrade)** *(rejected)*: Preview-feature breakage would corrupt trace continuity across behaviour changes — `jarvis.learning` priors lose comparability.
2. **Stay on 0.5.x indefinitely** *(rejected)*: Accumulating incompatibility debt; miss out on new primitives (Skills v2, Memory Store improvements, etc.).

## Consequences

- Scheduled re-verification when 0.6 ships (sometime after April 2026).
- Explicit migration gate prevents accidental breakage.
- Captured as `ASSUM-011`.
