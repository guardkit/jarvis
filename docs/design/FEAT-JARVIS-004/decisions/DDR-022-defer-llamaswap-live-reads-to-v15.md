# DDR-022 — Defer `LlamaSwapAdapter` live `/running` + `/log` reads to v1.5

- **Status:** Accepted
- **Date:** 2026-04-27
- **Feature:** FEAT-JARVIS-004 (Phase 3 / Fleet Integration)
- **Related:** ADR-ARCH-012 (swap-aware voice latency policy), [DDR-015](../../FEAT-JARVIS-003/decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md), ASSUM-LLAMASWAP-API
- **Affects:** [phase3-build-plan.md §"What Phase 3 IS NOT"](../../../research/ideas/phase3-build-plan.md)

## Context

ADR-ARCH-012 specifies a swap-aware voice-latency policy: when Reachy adapters dispatch to a model that needs llama-swap to swap (estimated ETA > 30s), the supervisor speaks a TTS acknowledgement before the substantive response.

FEAT-JARVIS-003 ([DDR-015](../../FEAT-JARVIS-003/decisions/DDR-015-llamaswap-adapter-with-stubbed-health.md)) shipped `LlamaSwapAdapter` with stubbed `/running` + `/log` reads. The voice-ack helper (`emit_voice_ack_and_queue` in `infrastructure/lifecycle.py`) is wired to the stubbed reads — it returns deterministic test outputs.

The phase-3 scope-doc says: *"Live llama-swap `/running` + `/log` reads land with FEAT-JARVIS-004's transport swap if scheduled; otherwise v1.5."*

Two reasons to schedule it here:
1. We're already in the infrastructure modules (NATS + Graphiti).
2. The voice-ack policy is dead until live reads land.

Two reasons to defer:
1. ASSUM-LLAMASWAP-API — the `/running` + `/log` endpoint shape is **not formally contracted** by the llama-swap project. ADR-ARCH-012 references them by behaviour. We'd be reverse-engineering a contract while also lighting up NATS, Graphiti, and the first ADR-FLEET-001 writes — three independent risks in one feature.
2. Phase 3 is already medium-high complexity (per build-plan §"Feature Summary"). Adding HTTP probes against an undocumented endpoint multiplies the implement-and-debug surface.

The voice-ack policy is **dormant** in v1 anyway — the Reachy adapter (FEAT-JARVIS-006) doesn't ship until Phase 4. There's no production user of swap-aware voice ack until that lands.

## Decision

1. **`LlamaSwapAdapter` `/running` and `/log` reads remain stubbed** through FEAT-JARVIS-004.
2. **Live reads land in v1.5**, in a separate feature (provisionally `FEAT-JARVIS-008-bis` or its own FEAT-J0XX). The feature owns:
   - Reverse-engineering the `/running` + `/log` endpoint contract (a brief endpoint-discovery research pass).
   - HTTP probe wiring with retry + cache.
   - Integration tests against a real GB10 llama-swap instance.
   - Voice-ack policy regression tests once live reads exist.
3. **No supervisor-level changes required.** The voice-ack helper API is unchanged; it continues to consume `SwapStatus` from `LlamaSwapAdapter`. When the live-reads feature lands, the helper's behaviour matches reality automatically.
4. **The Reachy adapter (FEAT-JARVIS-006)** does not block on this — Phase 4 ships the Reachy adapter against the stubbed reads (ETA always 0 → no ack ever fires); the voice-ack policy lights up properly when the live-reads feature follows.

## Rationale

- **Independent risk, independent feature.** ASSUM-LLAMASWAP-API is a real risk — undocumented endpoints can change between llama-swap releases. Putting that risk in the same feature as NATS-first + Graphiti-first creates compounding uncertainty during the Phase 3 close criterion's end-to-end test.
- **Voice-ack policy is dormant in v1.** No Reachy adapter, no real consumer. The TTS ack stub never fires in production today. Live reads have no Phase 3 user.
- **No supervisor / tool surface change** when live reads land — the swap is purely inside `LlamaSwapAdapter`. So deferring costs nothing in compatibility; it's purely a sequencing call.
- **Phase 3 close criterion is more important than completeness.** The end-to-end test (Step 14 of build-plan) hinges on real Forge round-trip; live llama-swap reads are unrelated to that close criterion.

## Alternatives considered

| Option | Why not |
|---|---|
| Land live reads in FEAT-JARVIS-004 | Adds an undocumented-endpoint risk on top of NATS + Graphiti + first ADR-FLEET-001 writes; complicates the Phase 3 close criterion test |
| Land live reads in FEAT-JARVIS-005 | Same risk concentration as 004; FEAT-J005 is already adding queue-build + Forge notifications + end-to-end test |
| Land live reads in FEAT-JARVIS-006 (Reachy adapter) | Couples the Reachy ship to llama-swap probe risk; if the probe contract shifts, Reachy ships late |
| Replace the stub with a hard-fail "NotImplementedError" until live reads land | The stub is correct under the v1 invariant (no real consumer); replacing it with a failure removes the FEAT-J003 test coverage that already exists |
| Move live reads into v1 critical path with mock-everything tests | Doesn't reduce the contract risk; tests against mocks don't validate the real endpoint shape; we'd ship believing it works and discover otherwise during Reachy integration |

## Consequences

- `LlamaSwapAdapter` (`adapters/llamaswap.py`) is unchanged in FEAT-JARVIS-004. Tests from FEAT-J003 continue to pass.
- `voice_ack_emitted` log lines remain test-only — no production firings until v1.5 + Reachy.
- The phase-3 scope-doc's "land if scheduled" condition resolves to **not scheduled here**. Build-plan §"What Phase 3 IS NOT" updated to add "live `/running` + `/log` reads".
- A new feature ticket lands for v1.5: "Live llama-swap health probe + voice-ack production wiring".
- ASSUM-LLAMASWAP-API stays open through v1.

## Status

Accepted at FEAT-JARVIS-004 `/system-design`. Re-evaluation gate: when FEAT-JARVIS-006 (Reachy adapter) reaches `/system-design`, verify whether the v1.5 feature has landed; if not, ship Reachy against the stub and queue the live-reads feature ahead of Reachy's first real-user round-trip.
