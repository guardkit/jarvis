# DDR-015: Swap-aware read path lives in `jarvis.adapters.llamaswap`; Phase 2 stubs the health reads

**Status:** Accepted
**Date:** 2026-04-23
**Deciders:** Rich + `/system-design FEAT-JARVIS-003` session
**Related context:** FEAT-JARVIS-003
**Related components:** `jarvis.adapters.llamaswap`, `jarvis.agents.supervisor`, `jarvis.sessions.manager`
**Depends on:** [ADR-ARCH-012](../../../architecture/decisions/ADR-ARCH-012-swap-aware-voice-latency-policy.md), [ADR-ARCH-001](../../../architecture/decisions/ADR-ARCH-001-local-first-inference-via-llama-swap.md), [DDR-010](DDR-010-single-async-subagent-supersedes-four-roster.md)
**Retires:** Phase 2 scope doc's "`quick_local` fallback hook" (JA6 cloud cheap-tier fallback — retired by ADR-ARCH-012)

## Context

The Phase 2 scope doc's FEAT-JARVIS-003 Change 5 asked: *"What happens to `quick_local` when AutoBuild is hammering the GB10 GPU? Phase 2 does not solve JA6 (the full policy lands as an ADR the `/system-design` step produces), but it lands the hook."*

The `/system-arch` session accepted **ADR-ARCH-012** which superseded JA6 directly: swap-aware supervisor behaviour (query `/running`, ack "one moment" if swap ETA > 30s) replaces cloud-cheap-tier fallback. Simultaneously, DDR-010 retired the `quick_local` subagent itself.

That leaves one actual concrete need: the supervisor must be able to **read** llama-swap's `/running` + `/log` endpoints to implement the swap-aware voice-latency policy. Two questions:

1. **Where does that read path live?** — inline in the supervisor factory vs dedicated adapter module.
2. **Does Phase 2 wire live reads or stub them?**

## Decision

### Location — dedicated Group-D adapter

A new adapter module `src/jarvis/adapters/llamaswap.py` lands in this feature. It is the **first** populated module in Jarvis's Group D (Adapters) layer per [ADR-ARCH-006](../../../architecture/decisions/ADR-ARCH-006-five-group-module-layout.md); Phase 1 reserved the `adapters/` package empty. The adapter exposes:

```python
from __future__ import annotations

from typing import Protocol
from pydantic import BaseModel, Field


class SwapStatus(BaseModel):
    """Current llama-swap builders-group state."""
    loaded_model: str | None = Field(..., description="Alias currently loaded (None = no model loaded)")
    eta_seconds: int = Field(..., ge=0, description="Estimated seconds until requested model is ready")
    source: Literal["live", "stub"] = "stub"


class LlamaSwapAdapterProtocol(Protocol):
    def current_status(self, *, wanted_alias: str) -> SwapStatus: ...


class LlamaSwapAdapter(LlamaSwapAdapterProtocol):
    def __init__(self, *, base_url: str, stub_responses: dict[str, SwapStatus] | None = None) -> None: ...
    def current_status(self, *, wanted_alias: str) -> SwapStatus: ...
```

The supervisor's voice-reactive path receives the adapter via `AppState` (passed by `lifecycle.startup`) and queries it before dispatching to `jarvis-reasoner`. If `SwapStatus.eta_seconds > 30` and the session's adapter is voice-reactive (`Adapter.REACHY` in v1), the supervisor emits a TTS ack stub (FEAT-JARVIS-009 wires real TTS) and queues the request per ADR-ARCH-012. Non-voice adapters (`TELEGRAM`, `CLI`, `DASHBOARD`) use standard latency — no ack.

### Transport — Phase 2 stubs, FEAT-JARVIS-004 goes live

Phase 2 ships the adapter with **stubbed responses only**. The Phase 2 implementation of `LlamaSwapAdapter.current_status()` reads from the `stub_responses` dict keyed by `wanted_alias`; the default is `SwapStatus(loaded_model=wanted_alias, eta_seconds=0, source="stub")` for any alias (i.e. "always ready"). Tests override the dict to simulate the >30s-ETA branch.

FEAT-JARVIS-004 replaces the stub with real HTTP reads against `http://promaxgb10-41b1:9000/running` and `/log`, wraps them in a 30s + watch-invalidation cache per Forge ADR-ARCH-017 convention, and returns `source="live"`. The stub surface stays for tests; the production path uses live reads.

### Rationale for stubbing

- **ADR-ARCH-012 requires the supervisor to query llama-swap, but llama-swap itself is not a Phase 2 dependency.** Rich's Phase 2 development machine (MacBook Pro M2 Max) does not run llama-swap. Live reads would require a GB10 tunnel from dev, which is FEAT-JARVIS-004's concern (that's when NATS also wires live).
- **The interaction tested in Phase 2 is the supervisor's policy.** Given `eta_seconds=180`, does the supervisor correctly emit the ack and queue the request? That's a pure policy test, stubbable.
- **The interaction tested in Phase 3 is the adapter's live contract.** Given llama-swap responding, does the adapter produce the right `SwapStatus`? That's integration-shaped; deferring keeps Phase 2 unit-testable.

## Rationale

- **Adapter separation per ADR-ARCH-002 / ADR-ARCH-006.** llama-swap is an I/O edge. Group D is the designated home. Inlining the reads in the supervisor factory would put HTTP code inside the reasoning-core container, a clean-hexagonal violation.
- **Stubbed reads match Phase 2's transport posture.** FEAT-JARVIS-002 already stubs `dispatch_by_capability` and `queue_build`'s NATS transport per DDR-009. Stubbed llama-swap reads match that posture; FEAT-JARVIS-004 lights all three live transports together.
- **Retires JA6 cleanly.** The "quick_local fallback hook" scope concept is *gone*. Nothing in Jarvis falls back to a cloud cheap-tier on GB10 pressure — the supervisor acks the swap and waits. Test shape becomes `test_swap_aware_voice_ack.py`, not `test_quick_local_fallback.py`.
- **Adapter is extensible.** FEAT-JARVIS-004 can add `LlamaSwapAdapter.prefetch(alias)` for pre-emptive warm-hold per ADR-ARCH-012 without breaking the v1 `current_status` contract.

## Alternatives considered

1. **Inline reads in the supervisor factory.** Rejected. Clean-hexagonal violation; untestable without monkey-patching HTTP.

2. **Live reads in Phase 2 against a local llama-swap mock.** Rejected. Adds a development-environment dependency (spinning up a mock server) for no Phase 2 test-value gain.

3. **Defer the adapter entirely to FEAT-JARVIS-004; Phase 2 hard-codes `eta_seconds=0`.** Rejected. The swap-aware policy in the supervisor is load-bearing for ADR-ARCH-012 compliance and for the voice-ack regression test. Shipping it with a hardcoded zero means Phase 2 tests cannot exercise the >30s branch, and FEAT-JARVIS-004 has to introduce *both* the adapter and the supervisor policy at once — bigger blast radius.

4. **Retain a cloud cheap-tier fallback for `quick_local`.** Rejected. Directly contradicts ADR-ARCH-012 §Decision (and, transitively, ADR-ARCH-001 — cloud on unattended path).

## Consequences

**Positive:**
- First Group-D adapter established; pattern proven for FEAT-JARVIS-004's NATS and Graphiti adapters.
- Swap-aware policy is unit-testable in Phase 2 with the `stub_responses` dict.
- Test module name (`test_swap_aware_voice_ack.py`) accurately reflects what is being exercised; no residual "quick_local" naming confusion.

**Negative:**
- `LlamaSwapAdapterProtocol` defines a small surface (one method). If the swap-aware policy grows (pre-emptive warm-hold, load prediction), the Protocol expands. Acceptable — Protocol is cheap to extend.
- Phase 2 stub means the "adapter's HTTP wire contract" is untested until FEAT-JARVIS-004. Mitigated by FEAT-JARVIS-004's plan to include an integration test against a real (or dockerised) llama-swap.

## Links

- ADR-ARCH-012 — swap-aware voice latency policy
- ADR-ARCH-001 — local-first inference
- ADR-ARCH-002 — clean/hexagonal
- ADR-ARCH-006 — five-group layout
- Phase 2 scope doc — retired JA6 hook
